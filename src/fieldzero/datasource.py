"""
Acquisition for the QuSpin QZFM sensors.

Design notes, and why this differs from MEG_DSP/DataSource.py:

  * The DAQ task is built once over all channels and never reconfigured. MEG_DSP
    closed and rebuilt the task inside set_axis() while acquisition was live,
    which tore down the timing config and sample buffer underneath a reader
    already blocked in task.read(). Axis selection is a display concern and now
    lives entirely in the viewer.

  * get_data() does not touch the hardware. A dedicated thread drains the DAQ at
    full rate into a ring buffer; get_data() returns a snapshot of the tail of
    that buffer without blocking. A pull-based read straight from the task
    overruns the card's buffer (NI-DAQmx -200279) the moment the consumer is
    slower than the acquisition, which is what kills these scopes after a minute.

  * Samples are volts. Not picotesla. The V/nT constant is unverified and is a
    scaling concern, not an acquisition one — it is applied at display time.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from .config import Channel, DaqConfig

try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType, TerminalConfiguration

    _NIDAQMX_AVAILABLE = True
except ImportError:  # nidaqmx is absent off-hardware; MockSignal covers development
    _NIDAQMX_AVAILABLE = False


@dataclass(frozen=True)
class Snapshot:
    """
    A block of recent samples with its identity attached.

    Carrying the channel list and sample rate alongside the array means a
    consumer cannot mis-index a channel or transform at the wrong rate — the
    class of bug that produced all the shape-padding in MEG_DSP's displays.
    """

    data: np.ndarray            # (n_channels, n_samples), volts
    channels: tuple[Channel, ...]
    sample_rate: float
    t0: float                   # seconds, on a monotonic sample clock from start

    @property
    def n_samples(self) -> int:
        return self.data.shape[1]

    def index_of(self, name: str) -> int:
        for i, ch in enumerate(self.channels):
            if ch.name == name:
                return i
        raise KeyError(f"no channel named {name!r}")

    def channel(self, name: str) -> np.ndarray:
        return self.data[self.index_of(name)]


class RingBuffer:
    """
    Fixed-capacity circular store of the most recent samples, shared between the
    acquisition thread (writer) and any number of readers.

    Readers never block the writer for longer than a memcpy, so a stalled viewer
    cannot back-pressure the DAQ.
    """

    def __init__(self, n_channels: int, capacity: int):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._buf = np.zeros((n_channels, capacity), dtype=np.float64)
        self._capacity = capacity
        self._write = 0        # next column to write
        self._written = 0      # total samples ever written (monotonic sample clock)
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def total_written(self) -> int:
        with self._lock:
            return self._written

    def write(self, chunk: np.ndarray) -> None:
        """chunk: (n_channels, n). Samples beyond capacity overwrite the oldest."""
        chunk = np.atleast_2d(np.asarray(chunk, dtype=np.float64))
        presented = chunk.shape[1]
        if presented == 0:
            return
        n = presented
        if n > self._capacity:
            # More data than the buffer holds: keep only the newest capacity samples.
            # The dropped ones still happened, so they still count towards the sample
            # clock — otherwise t0 drifts backwards and every time axis lies.
            chunk = chunk[:, -self._capacity:]
            n = self._capacity

        with self._lock:
            end = self._write + n
            if end <= self._capacity:
                self._buf[:, self._write:end] = chunk
            else:
                split = self._capacity - self._write
                self._buf[:, self._write:] = chunk[:, :split]
                self._buf[:, : n - split] = chunk[:, split:]
            self._write = end % self._capacity
            self._written += presented

    def latest(self, n: int) -> tuple[np.ndarray, int]:
        """
        Return the most recent min(n, available) samples in chronological order,
        with the absolute sample index of the first one.
        """
        with self._lock:
            available = min(self._written, self._capacity)
            n = min(max(n, 0), available)
            if n == 0:
                return np.zeros((self._buf.shape[0], 0)), self._written
            start = (self._write - n) % self._capacity
            end = start + n
            if end <= self._capacity:
                out = self._buf[:, start:end].copy()
            else:
                split = self._capacity - start
                out = np.concatenate(
                    (self._buf[:, start:], self._buf[:, : n - split]), axis=1
                )
            return out, self._written - n


class DataSource(ABC):
    """
    Contract for anything that supplies samples.

    Implementations must be fully substitutable: the viewer is written against
    this interface alone, so running against MockSignal exercises the same code
    path that runs in the lab.
    """

    config: DaqConfig

    @abstractmethod
    def get_data(self, n_samples: int) -> Snapshot:
        """Most recent min(n_samples, available) samples, in volts. Non-blocking."""

    @abstractmethod
    def close(self) -> None: ...

    @property
    def channels(self) -> tuple[Channel, ...]:
        return self.config.channels

    @property
    def sample_rate(self) -> float:
        return self.config.sample_rate

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _ThreadedSource(DataSource):
    """Shared machinery: an acquisition thread feeding a ring buffer."""

    def __init__(self, config: DaqConfig):
        self.config = config
        capacity = max(1, int(round(config.buffer_seconds * config.sample_rate)))
        self._ring = RingBuffer(config.n_channels, capacity)
        self._stop = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _acquire(self, n: int) -> np.ndarray:
        """Produce one chunk, shape (n_channels, n). Blocks for ~n/sample_rate."""
        raise NotImplementedError

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._ring.write(self._acquire(self.config.read_chunk))
        except BaseException as exc:  # surfaced to the caller via check_error()
            self._error = exc

    def check_error(self) -> BaseException | None:
        """Non-fatal poll: the acquisition thread's exception, if it died."""
        return self._error

    def get_data(self, n_samples: int) -> Snapshot:
        data, first_index = self._ring.latest(n_samples)
        return Snapshot(
            data=data,
            channels=self.config.channels,
            sample_rate=self.config.sample_rate,
            t0=first_index / self.config.sample_rate,
        )

    def close(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)


class NIDAQ(_ThreadedSource):
    """
    Continuous acquisition from one NI-DAQ device across all configured channels.

    The channels are read as a single multiplexed task. On a non-simultaneous
    -sampling card the channels are skewed in time by the ADC scan interval;
    irrelevant for a DC field measurement, but it would matter to any
    cross-channel phase result.
    """

    _TERMINAL_CONFIGS = {}
    if _NIDAQMX_AVAILABLE:
        _TERMINAL_CONFIGS = {
            "RSE": TerminalConfiguration.RSE,
            "NRSE": TerminalConfiguration.NRSE,
            "DIFF": TerminalConfiguration.DIFF,
            "DEFAULT": TerminalConfiguration.DEFAULT,
        }

    def __init__(self, config: DaqConfig | None = None):
        if not _NIDAQMX_AVAILABLE:
            raise ImportError(
                "nidaqmx is not installed. Use MockSignal for offline development."
            )
        config = config or DaqConfig()
        super().__init__(config)

        if config.terminal_config not in self._TERMINAL_CONFIGS:
            raise ValueError(
                f"terminal_config {config.terminal_config!r} must be one of "
                f"{sorted(self._TERMINAL_CONFIGS)}"
            )

        vmin, vmax = config.voltage_range
        self._task = nidaqmx.Task()
        try:
            for ch in config.channels:
                self._task.ai_channels.add_ai_voltage_chan(
                    ch.device_channel,
                    terminal_config=self._TERMINAL_CONFIGS[config.terminal_config],
                    min_val=vmin,
                    max_val=vmax,
                )
            self._task.timing.cfg_samp_clk_timing(
                rate=config.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                # Card-side buffer of 10 chunks: absorbs scheduling jitter in the
                # acquisition thread without adding meaningful latency.
                samps_per_chan=config.read_chunk * 10,
            )
            self._task.start()
        except BaseException:
            self._task.close()
            raise

        self.start()

    def _acquire(self, n: int) -> np.ndarray:
        return np.asarray(self._task.read(number_of_samples_per_channel=n))

    def close(self) -> None:
        super().close()
        if self._task is not None:
            self._task.close()
            self._task = None


class MockSignal(_ThreadedSource):
    """
    Synthetic source for development and for lab dry-runs without the DAQ.

    Emits volts, so it sits behind exactly the same calibration and clipping as
    real hardware. The default signal is built to exercise every display:

      * a per-channel DC offset — the residual field this project exists to find
      * a shared common-mode component across both sensors, so a phase plot of
        S1 against S2 shows real correlation rather than a blob
      * 50 Hz mains and its third harmonic, for the spectrum plot
      * S1-Z offset beyond the rail, so the saturation indicator has something
        to catch and a clipped channel is visible in the stats table
    """

    def __init__(
        self,
        config: DaqConfig | None = None,
        dc_offsets_v: list[float] | None = None,
        seed: int | None = None,
    ):
        config = config or DaqConfig()
        super().__init__(config)

        n = config.n_channels
        if dc_offsets_v is None:
            # S1-Z (index 2) is driven past the +5 V rail on purpose.
            default = [1.8, -0.6, 6.0, 1.6, -0.5, 3.1]
            dc_offsets_v = (default * ((n // len(default)) + 1))[:n]
        self._dc = np.asarray(dc_offsets_v, dtype=float).reshape(-1, 1)

        self._rng = np.random.default_rng(seed)
        self._sample_index = 0
        self._vmin, self._vmax = config.voltage_range
        self._pace = threading.Event()

    def _acquire(self, n: int) -> np.ndarray:
        fs = self.config.sample_rate
        t = (self._sample_index + np.arange(n)) / fs
        self._sample_index += n

        common = 0.20 * np.sin(2 * np.pi * 50.0 * t) + 0.05 * np.sin(2 * np.pi * 150.0 * t)
        signal = np.tile(common, (self.config.n_channels, 1))
        signal += self._rng.normal(0.0, 0.02, (self.config.n_channels, n))
        signal += self._dc

        # Clip at the input range, exactly as the DAQ front end would.
        signal = np.clip(signal, self._vmin, self._vmax)

        # Pace to real time so the ring buffer fills at the configured rate.
        self._pace.wait(n / fs)
        return signal
