"""
Data acquisition interface for QuSpin QZFM sensors via NI-DAQ.

Adapted from MEG_DSP/DataSource.py (github.com/Kayzerjali/MEG_DSP).
Channel mapping: Dev1/ai0–ai5 → 2 sensors × 3 axes (X, Y, Z).
Conversion: voltage → pT using QZFM sensitivity 2.7 V/nT.

NOTE: Sensitivity of 2.7 V/nT is taken from the prior project. Verify against
the datasheet for the specific QuSpin gen in the lab before treating as calibrated.
"""

import threading
import queue
import numpy as np

try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType
    _NIDAQMX_AVAILABLE = True
except ImportError:
    _NIDAQMX_AVAILABLE = False

# QZFM analog output sensitivity — verify against datasheet for confirmed sensor gen
QZFM_SENSITIVITY_V_PER_NT = 2.7


class DataSource:
    """Abstract base: all data sources yield (num_channels, num_samples) arrays."""

    def data_stream(self, num_samples_per_read: int = 100):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class MockSignal(DataSource):
    """Offline signal source for development without hardware."""

    def __init__(
        self,
        sample_rate: int = 1000,
        dc_offsets_nT: list[float] | None = None,
        num_channels: int = 2,
    ):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self._t = 0.0

        if dc_offsets_nT is not None:
            self._dc_offsets = np.array(dc_offsets_nT, dtype=float).reshape(-1, 1)
        else:
            # Default: simulate both sensors saturated
            ceiling_pT = (QZFM_SENSITIVITY_V_PER_NT * 5.0) * 1000  # 5 V rail → pT
            self._dc_offsets = np.full((num_channels, 1), ceiling_pT)

        self._queue: queue.Queue = queue.Queue(maxsize=10)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _generate(self, n: int) -> np.ndarray:
        t = np.arange(n) / self.sample_rate + self._t
        self._t += n / self.sample_rate
        noise = np.random.normal(0, 3, (self.num_channels, n))
        return np.tile(np.zeros(n), (self.num_channels, 1)) + noise + self._dc_offsets

    def _producer(self, n: int):
        while not self._stop.is_set():
            self._queue.put(self._generate(n))
            threading.Event().wait(n / self.sample_rate)

    def data_stream(self, num_samples_per_read: int = 100):
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._producer, args=(num_samples_per_read,), daemon=True
            )
            self._thread.start()
        while True:
            try:
                yield self._queue.get_nowait()
            except queue.Empty:
                yield None

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)


class NIDAQ(DataSource):
    """
    NI-DAQ acquisition for two QuSpin QZFM sensors.

    Channel mapping (Dev1):
        X axis: ai0 (sensor 1), ai3 (sensor 2)
        Y axis: ai1 (sensor 1), ai4 (sensor 2)
        Z axis: ai2 (sensor 1), ai5 (sensor 2)

    Data returned in pT.
    """

    _AXIS_CHANNELS = {
        "x": ["Dev1/ai0", "Dev1/ai3"],
        "y": ["Dev1/ai1", "Dev1/ai4"],
        "z": ["Dev1/ai2", "Dev1/ai5"],
        "all": ["Dev1/ai0", "Dev1/ai1", "Dev1/ai2", "Dev1/ai3", "Dev1/ai4", "Dev1/ai5"],
    }

    def __init__(self, sample_rate: int = 1000, axis: str = "all"):
        if not _NIDAQMX_AVAILABLE:
            raise ImportError(
                "nidaqmx not installed. Use MockSignal for offline development."
            )
        self._sample_rate = sample_rate
        self._lock = threading.Lock()
        self._task = None
        self.set_axis(axis)

    def set_axis(self, axis: str):
        if axis not in self._AXIS_CHANNELS:
            raise ValueError(f"axis must be one of {list(self._AXIS_CHANNELS)}")
        with self._lock:
            if self._task:
                self._task.close()
            self._task = nidaqmx.Task()
            self._channels = self._AXIS_CHANNELS[axis]
            self._axis = axis
            self._task.ai_channels.add_ai_voltage_chan(", ".join(self._channels))
            self._task.timing.cfg_samp_clk_timing(
                rate=self._sample_rate, sample_mode=AcquisitionType.CONTINUOUS
            )

    def _volts_to_pT(self, data: np.ndarray) -> np.ndarray:
        return (data / QZFM_SENSITIVITY_V_PER_NT) * 1000.0

    def get_data(self, num_samples: int = 1) -> np.ndarray:
        """Returns (2, num_samples) array in pT for a single-axis read."""
        with self._lock:
            raw = np.array(self._task.read(num_samples))
        if raw.ndim == 1:
            raw = raw.reshape(-1, 1)
        return self._volts_to_pT(raw)

    def data_stream(self, num_samples_per_read: int = 100):
        while True:
            yield self.get_data(num_samples_per_read)

    def close(self):
        with self._lock:
            if self._task:
                self._task.close()
                self._task = None


def is_saturated(data: np.ndarray, ceiling_pT: float, tolerance_fraction: float = 0.02) -> np.ndarray:
    """
    Returns a bool array (num_channels,) indicating which channels appear saturated.

    A channel is considered saturated if its mean value is within tolerance_fraction
    of the ceiling value — i.e. it is railing at the analog output limit.

    ceiling_pT must be determined from M-01 (saturation baseline measurement).
    """
    channel_means = np.mean(np.abs(data), axis=-1)
    return channel_means >= ceiling_pT * (1.0 - tolerance_fraction)
