"""
Reduction of raw snapshots into what a display pane needs.

Pure numpy: no hardware, no I/O, no sockets. Every function here is testable by
handing it an array.

Each pane kind is a Reducer subclass registered under a `kind` string. The server
looks the kind up and never branches on type, so adding a pane means adding a
class here and a renderer in the JS — the server, the wire protocol and the
layout code stay untouched. MEG_DSP's DisplayManager instead inferred a pane's
data source from its position in a list ("first half raw, second half filtered"),
so adding one display silently repartitioned all of them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np

from .config import Calibration, ViewerConfig
from .datasource import Snapshot


@dataclass(frozen=True)
class PaneSpec:
    """A pane's declarative request, as sent by the browser."""

    id: str
    kind: str
    channels: tuple[str, ...] = ()
    window_s: float = 10.0
    units: str = "pT"
    opts: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PaneSpec":
        return cls(
            id=str(d["id"]),
            kind=str(d["kind"]),
            channels=tuple(str(c) for c in d.get("channels", ())),
            window_s=float(d.get("window_s", 10.0)),
            units=str(d.get("units", "pT")),
            opts=dict(d.get("opts", {})),
        )


@dataclass
class PaneFrame:
    """
    One pane's payload for one frame.

    `meta` is JSON (labels, scalars, axis hints). `arrays` are float32 vectors
    sent as a raw binary block; the browser reads them back in this order with
    no parsing. Keeping bulk numbers out of JSON is what lets this run at 20 Hz
    with several panes open without the browser burning CPU on JSON.parse.
    """

    id: str
    kind: str
    meta: dict[str, Any]
    arrays: dict[str, np.ndarray]

    def header(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "meta": self.meta,
            "arrays": [{"name": k, "n": int(v.size)} for k, v in self.arrays.items()],
        }


class Reducer(ABC):
    """
    Turns a Snapshot into a PaneFrame for one pane.

    Reducers are stateless and constructed per frame, so a pane's config can
    change between frames with no reset logic and no stale state to leak.
    """

    kind: ClassVar[str]

    def __init__(self, spec: PaneSpec, calibration: Calibration, viewer: ViewerConfig):
        self.spec = spec
        self.calibration = calibration
        self.viewer = viewer

    @abstractmethod
    def compute(self, snapshot: Snapshot) -> PaneFrame: ...

    # -- helpers shared by subclasses -------------------------------------------------

    def _scale(self) -> float:
        return self.calibration.scale(self.spec.units)

    def _window_samples(self, snapshot: Snapshot) -> int:
        return max(1, int(round(self.spec.window_s * snapshot.sample_rate)))

    def _select(self, snapshot: Snapshot) -> tuple[list[str], np.ndarray]:
        """Rows for the requested channels, in the requested order, scaled to units."""
        names = [c for c in self.spec.channels if c in {ch.name for ch in snapshot.channels}]
        if not names:
            return [], np.zeros((0, snapshot.n_samples))
        rows = np.stack([snapshot.channel(n) for n in names])
        return names, rows * self._scale()


REDUCERS: dict[str, type[Reducer]] = {}


def register(cls: type[Reducer]) -> type[Reducer]:
    """Class decorator: make a Reducer addressable by its `kind` string."""
    if not getattr(cls, "kind", None):
        raise ValueError(f"{cls.__name__} must define a non-empty `kind`")
    if cls.kind in REDUCERS:
        raise ValueError(f"reducer kind {cls.kind!r} is already registered")
    REDUCERS[cls.kind] = cls
    return cls


def build(spec: PaneSpec, calibration: Calibration, viewer: ViewerConfig) -> Reducer:
    try:
        cls = REDUCERS[spec.kind]
    except KeyError:
        raise ValueError(
            f"unknown pane kind {spec.kind!r}; registered: {sorted(REDUCERS)}"
        ) from None
    return cls(spec, calibration, viewer)


def minmax_decimate(rows: np.ndarray, target_points: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Reduce each row to ~target_points while preserving its visual envelope.

    Buckets the samples and emits each bucket's min and max. Plain subsampling
    would drop spikes between the samples it keeps — a transient in the field
    would simply not appear on screen. Returns (positions, values) where
    positions index into the original sample axis, shared across all rows so the
    traces stay aligned.
    """
    rows = np.atleast_2d(rows)
    n = rows.shape[1]
    if n == 0:
        return np.zeros(0), np.zeros((rows.shape[0], 0))
    if target_points < 4 or n <= target_points:
        return np.arange(n, dtype=float), rows

    buckets = target_points // 2
    per = n // buckets
    usable = buckets * per
    # Drop the oldest remainder so every bucket is the same width.
    trimmed = rows[:, n - usable:]
    offset = n - usable

    blocks = trimmed.reshape(rows.shape[0], buckets, per)
    lows = blocks.min(axis=2)
    highs = blocks.max(axis=2)

    values = np.empty((rows.shape[0], buckets * 2), dtype=float)
    values[:, 0::2] = lows
    values[:, 1::2] = highs

    starts = offset + np.arange(buckets) * per
    positions = np.empty(buckets * 2, dtype=float)
    positions[0::2] = starts
    positions[1::2] = starts + per / 2.0
    return positions, values


@register
class TimeDomain(Reducer):
    """Rolling time trace. x is seconds relative to now, so 0 is the newest sample."""

    kind = "time"

    def compute(self, snapshot: Snapshot) -> PaneFrame:
        n = self._window_samples(snapshot)
        names, rows = self._select(snapshot)
        rows = rows[:, -n:] if rows.size else rows
        have = rows.shape[1] if rows.size else 0

        positions, values = minmax_decimate(rows, self.viewer.decimation_points)
        # Newest sample sits at t=0; older samples run negative.
        t = (positions - (have - 1)) / snapshot.sample_rate if have else positions

        arrays: dict[str, np.ndarray] = {"x": t.astype(np.float32)}
        for i, name in enumerate(names):
            arrays[name] = values[i].astype(np.float32)

        return PaneFrame(
            id=self.spec.id,
            kind=self.kind,
            meta={
                "series": names,
                "units": self.spec.units,
                "x_label": "time (s)",
                "y_label": self.spec.units,
                "n_raw": have,
            },
            arrays=arrays,
        )


@register
class Spectrum(Reducer):
    """
    One-sided amplitude spectrum or amplitude spectral density.

    Two departures from MEG_DSP's FFT display, both of which matter here:

      * A Hann window is applied. The old code took a bare rfft of a rectangular
        window, so every tone leaked across neighbouring bins.

      * The DC bin is kept by default. The old code zeroed it unconditionally,
        which is right for MEG but wrong for this project — the DC offset IS the
        residual field we are trying to measure. `remove_dc` is available as an
        option for when you want to see the AC noise floor unobscured.

    mode="asd" gives units/sqrt(Hz), which is the form a magnetometer noise floor
    is quoted in and so is directly comparable against the QuSpin spec sheet.
    """

    kind = "spectrum"

    def compute(self, snapshot: Snapshot) -> PaneFrame:
        n = self._window_samples(snapshot)
        names, rows = self._select(snapshot)
        rows = rows[:, -n:] if rows.size else rows

        mode = str(self.spec.opts.get("mode", "asd"))
        remove_dc = bool(self.spec.opts.get("remove_dc", False))
        fs = snapshot.sample_rate

        have = rows.shape[1] if rows.size else 0
        if have < 8:
            return PaneFrame(
                id=self.spec.id,
                kind=self.kind,
                meta={"series": names, "units": self.spec.units, "filling": True},
                arrays={"x": np.zeros(0, np.float32),
                        **{nm: np.zeros(0, np.float32) for nm in names}},
            )

        if remove_dc:
            rows = rows - rows.mean(axis=1, keepdims=True)

        w = np.hanning(have)
        spec = np.fft.rfft(rows * w, axis=1)
        freqs = np.fft.rfftfreq(have, 1.0 / fs)

        power = np.abs(spec) ** 2
        # One-sided: double everything except DC and (if present) Nyquist.
        double = np.ones(freqs.size)
        double[1:] = 2.0
        if have % 2 == 0 and freqs.size > 1:
            double[-1] = 1.0

        if mode == "asd":
            # V/sqrt(Hz): normalise by the window's noise power bandwidth.
            values = np.sqrt(power * double / (fs * np.sum(w**2)))
            y_label = f"{self.spec.units}/√Hz"
        elif mode == "amplitude":
            # Peak amplitude of a sinusoid: normalise by the window's coherent gain.
            values = np.sqrt(power) * double / np.sum(w)
            y_label = self.spec.units
        else:
            raise ValueError(f"spectrum mode must be 'asd' or 'amplitude', got {mode!r}")

        # Decimate exactly as the time trace does. A 10 s window at 1 kHz yields
        # 5001 bins per channel; sent raw for six channels that is ~140 kB every
        # frame, which saturates the socket and stalls the whole connection —
        # including the client's own pane-config messages, which then take
        # seconds to apply. min/max bucketing is what keeps the mains peak: plain
        # subsampling would step straight over a one-bin spike.
        positions, values = minmax_decimate(values, self.viewer.decimation_points)
        df = fs / have
        freqs_out = positions * df

        arrays: dict[str, np.ndarray] = {"x": freqs_out.astype(np.float32)}
        for i, name in enumerate(names):
            arrays[name] = values[i].astype(np.float32)

        return PaneFrame(
            id=self.spec.id,
            kind=self.kind,
            meta={
                "series": names,
                "units": self.spec.units,
                "mode": mode,
                "remove_dc": remove_dc,
                "x_label": "frequency (Hz)",
                "y_label": y_label,
                "resolution_hz": df,
                "n_raw": have,
            },
            arrays=arrays,
        )


@register
class Phase(Reducer):
    """
    One channel against another, to expose correlation between them.

    Not restricted to sensor 1 vs sensor 2: any two channels. S1-X against S2-X
    shows common-mode pickup shared by both sensors; S1-X against S1-Z shows
    cross-axis coupling within one sensor.

    Pearson r and the least-squares slope are returned with the cloud, because a
    number you can read off is the actual reason to look at a correlation plot —
    r near 1 means the two channels see the same field, and the slope is the
    gain ratio between them.
    """

    kind = "phase"

    def compute(self, snapshot: Snapshot) -> PaneFrame:
        n = min(self._window_samples(snapshot), self.viewer.phase_points)
        names, rows = self._select(snapshot)

        if len(names) < 2:
            return PaneFrame(
                id=self.spec.id,
                kind=self.kind,
                meta={"series": names, "units": self.spec.units,
                      "error": "phase needs exactly 2 channels"},
                arrays={"x": np.zeros(0, np.float32), "y": np.zeros(0, np.float32)},
            )

        x = rows[0, -n:]
        y = rows[1, -n:]

        r: float | None = None
        slope: float | None = None
        intercept: float | None = None
        # Pearson r is undefined if either channel is constant — a railed channel
        # has zero variance, so guard rather than emit a NaN the UI has to handle.
        if x.size >= 2 and x.std() > 0 and y.std() > 0:
            r = float(np.corrcoef(x, y)[0, 1])
            slope, intercept = (float(v) for v in np.polyfit(x, y, 1))

        return PaneFrame(
            id=self.spec.id,
            kind=self.kind,
            meta={
                "series": names,
                "units": self.spec.units,
                "x_label": f"{names[0]} ({self.spec.units})",
                "y_label": f"{names[1]} ({self.spec.units})",
                "r": r,
                "slope": slope,
                "intercept": intercept,
                "n_raw": int(x.size),
            },
            arrays={"x": x.astype(np.float32), "y": y.astype(np.float32)},
        )


def channel_stats(
    snapshot: Snapshot,
    calibration: Calibration,
    units: str,
    voltage_range: tuple[float, float],
) -> list[dict[str, Any]]:
    """
    Per-channel mean/std/min/max, plus a clipping flag.

    Saturation is decided in VOLTS against the DAQ input range, never in pT. The
    input range is a known quantity; the V/nT constant is not. A channel pinned
    at the rail reports a mean that looks like a perfectly good field value, so
    without this flag the stats table would quietly lie about the very number
    this project exists to measure.
    """
    if snapshot.n_samples == 0:
        return [
            {"name": ch.name, "sensor": ch.sensor, "axis": ch.axis, "units": units,
             "mean": None, "std": None, "min": None, "max": None,
             "saturated": False, "clipped_fraction": 0.0}
            for ch in snapshot.channels
        ]

    volts = snapshot.data
    scale = calibration.scale(units)
    scaled = volts * scale

    rail = max(abs(voltage_range[0]), abs(voltage_range[1]))
    threshold = calibration.saturation_fraction * rail
    clipped_fraction = np.mean(np.abs(volts) >= threshold, axis=1)

    out = []
    for i, ch in enumerate(snapshot.channels):
        out.append({
            "name": ch.name,
            "sensor": ch.sensor,
            "axis": ch.axis,
            "units": units,
            "mean": float(scaled[i].mean()),
            "std": float(scaled[i].std()),
            "min": float(scaled[i].min()),
            "max": float(scaled[i].max()),
            "saturated": bool(clipped_fraction[i] > 0.01),
            "clipped_fraction": float(clipped_fraction[i]),
        })
    return out
