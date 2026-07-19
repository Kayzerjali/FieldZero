"""
Reducer correctness against analytically known signals.

These are not smoke tests. A spectrum plot that runs without crashing but is off
by a factor of two, or that puts a 50 Hz tone in the wrong bin, is worse than no
plot at all — you would trust it. So every reduction here is fed a signal whose
answer is known in closed form and checked against that answer.
"""

import numpy as np
import pytest
from conftest import make_snapshot

from fieldzero.reducers import (
    PaneSpec,
    Phase,
    Spectrum,
    TimeDomain,
    build,
    channel_stats,
    minmax_decimate,
    REDUCERS,
)

FS = 1000.0
N = 2000          # 2 s at 1 kHz; 50 Hz lands exactly on bin 100, so no leakage
WINDOW_S = N / FS


def spec(kind, channels, **kw):
    return PaneSpec(id="p1", kind=kind, channels=tuple(channels),
                    window_s=kw.pop("window_s", WINDOW_S),
                    units=kw.pop("units", "V"), opts=kw)


# ---------------------------------------------------------------- registry

def test_registry_holds_the_three_kinds():
    assert set(REDUCERS) == {"time", "spectrum", "phase"}


def test_unknown_kind_raises_a_useful_error(calibration, viewer):
    with pytest.raises(ValueError, match="unknown pane kind"):
        build(spec("nonsense", ["S1-X"]), calibration, viewer)


# ---------------------------------------------------------------- decimation

def test_decimation_preserves_a_spike_that_subsampling_would_lose():
    y = np.zeros((1, 10_000))
    y[0, 4_321] = 7.5          # a single-sample transient
    y[0, 8_765] = -3.25
    _, values = minmax_decimate(y, 200)
    assert values.max() == pytest.approx(7.5)
    assert values.min() == pytest.approx(-3.25)


def test_decimation_hits_the_point_budget():
    y = np.random.default_rng(0).normal(size=(3, 50_000))
    positions, values = minmax_decimate(y, 2000)
    assert values.shape[0] == 3
    assert values.shape[1] <= 2000
    assert positions.size == values.shape[1]      # one x per y, shared across rows
    assert np.all(np.diff(positions) > 0)         # x stays ascending for uPlot


def test_short_input_passes_through_untouched():
    y = np.arange(10, dtype=float).reshape(1, 10)
    positions, values = minmax_decimate(y, 2000)
    assert np.array_equal(values, y)
    assert np.array_equal(positions, np.arange(10))


# ---------------------------------------------------------------- time domain

def test_time_axis_ends_at_now_and_spans_the_window(calibration, viewer):
    snap = make_snapshot(np.zeros((1, N)), FS)
    frame = build(spec("time", ["S1-X"]), calibration, viewer).compute(snap)
    x = frame.arrays["x"]
    assert x[-1] == pytest.approx(0.0, abs=1e-3)          # newest sample at t=0
    assert x[0] == pytest.approx(-WINDOW_S, abs=0.02)     # oldest at -window
    assert np.all(np.diff(x) > 0)


def test_time_domain_converts_volts_to_pT(calibration, viewer):
    snap = make_snapshot(np.full((1, 500), 2.7), FS)      # 2.7 V at 2.7 V/nT = 1 nT
    frame = build(spec("time", ["S1-X"], units="pT", window_s=0.5),
                  calibration, viewer).compute(snap)
    assert frame.arrays["S1-X"] == pytest.approx(1000.0, rel=1e-5)  # 1 nT = 1000 pT


def test_time_domain_ignores_unknown_channel_names(calibration, viewer):
    snap = make_snapshot(np.zeros((1, 100)), FS)
    frame = build(spec("time", ["S1-X", "NOPE"], window_s=0.1),
                  calibration, viewer).compute(snap)
    assert frame.meta["series"] == ["S1-X"]


# ---------------------------------------------------------------- spectrum

def _tone(amp=1.0, freq=50.0, dc=0.0, n=N, fs=FS):
    t = np.arange(n) / fs
    return (dc + amp * np.sin(2 * np.pi * freq * t)).reshape(1, n)


def test_amplitude_spectrum_recovers_the_tone_amplitude(calibration, viewer):
    snap = make_snapshot(_tone(amp=1.0, freq=50.0), FS)
    frame = build(spec("spectrum", ["S1-X"], mode="amplitude"),
                  calibration, viewer).compute(snap)
    freqs, mag = frame.arrays["x"], frame.arrays["S1-X"]

    peak = int(np.argmax(mag))
    assert freqs[peak] == pytest.approx(50.0, abs=0.5)   # right bin
    assert mag[peak] == pytest.approx(1.0, rel=0.02)     # right amplitude, not 2x or 0.5x


def test_dc_bin_is_preserved_by_default(calibration, viewer):
    """
    Regression guard. MEG_DSP zeroed the DC bin unconditionally. For this project
    the DC offset IS the residual field being measured, so silently discarding it
    would hide the entire signal of interest.
    """
    snap = make_snapshot(_tone(amp=0.1, freq=50.0, dc=2.0), FS)
    frame = build(spec("spectrum", ["S1-X"], mode="amplitude"),
                  calibration, viewer).compute(snap)
    assert frame.arrays["S1-X"][0] == pytest.approx(2.0, rel=0.02)


def test_remove_dc_option_clears_the_dc_bin(calibration, viewer):
    snap = make_snapshot(_tone(amp=0.1, freq=50.0, dc=2.0), FS)
    frame = build(spec("spectrum", ["S1-X"], mode="amplitude", remove_dc=True),
                  calibration, viewer).compute(snap)
    assert frame.arrays["S1-X"][0] == pytest.approx(0.0, abs=1e-3)
    # ...without disturbing the tone.
    peak = int(np.argmax(frame.arrays["S1-X"]))
    assert frame.arrays["x"][peak] == pytest.approx(50.0, abs=0.5)
    assert frame.arrays["S1-X"][peak] == pytest.approx(0.1, rel=0.03)


def test_asd_of_white_noise_matches_the_analytic_level(calibration):
    """
    For white noise of standard deviation sigma, the one-sided amplitude spectral
    density is sigma * sqrt(2/fs), flat in frequency. This pins the ASD scaling —
    a wrong window normalisation would show up here as a constant factor, and a
    noise floor quoted against the QuSpin spec sheet would then be wrong.

    Decimation is disabled here on purpose: this is a test of the FFT
    normalisation, and min/max bucketing reports an envelope, which sits above
    the true per-bin level by construction.
    """
    from fieldzero.config import ViewerConfig

    undecimated = ViewerConfig(decimation_points=10**9)
    rng = np.random.default_rng(7)
    sigma = 0.5
    noise = rng.normal(0, sigma, (1, 16384))
    snap = make_snapshot(noise, FS)
    frame = build(spec("spectrum", ["S1-X"], mode="asd", window_s=16384 / FS),
                  calibration, undecimated).compute(snap)

    asd = frame.arrays["S1-X"][1:-1]                 # drop DC and Nyquist
    rms = float(np.sqrt(np.mean(asd.astype(np.float64) ** 2)))
    expected = sigma * np.sqrt(2.0 / FS)
    assert rms == pytest.approx(expected, rel=0.05)


def test_spectrum_decimation_is_bounded_and_keeps_the_peak(calibration, viewer):
    """
    A 30 s window at 1 kHz is 15001 bins per channel. Those must be bucketed down
    before they go on the wire — but bucketing by plain subsampling would step
    straight over a one-bin mains spike and the tone would vanish from the plot.
    min/max keeps it.
    """
    n = 30_000
    tone = _tone(amp=1.0, freq=50.0, n=n)
    snap = make_snapshot(tone, FS)
    frame = build(spec("spectrum", ["S1-X"], mode="amplitude", window_s=n / FS),
                  calibration, viewer).compute(snap)

    freqs, mag = frame.arrays["x"], frame.arrays["S1-X"]
    assert mag.size <= viewer.decimation_points
    assert freqs.size == mag.size
    assert np.all(np.diff(freqs) > 0)          # x stays ascending for uPlot

    peak = int(np.argmax(mag))
    assert freqs[peak] == pytest.approx(50.0, abs=1.0)
    assert mag[peak] == pytest.approx(1.0, rel=0.05)


def test_spectrum_frequency_axis_is_correctly_scaled_after_decimation(calibration, viewer):
    """The decimator returns sample-axis positions; they must be mapped back to Hz
    with the right bin width or every frequency read off the plot is wrong."""
    n = 30_000
    snap = make_snapshot(_tone(amp=1.0, freq=137.0, n=n), FS)
    frame = build(spec("spectrum", ["S1-X"], mode="amplitude", window_s=n / FS),
                  calibration, viewer).compute(snap)

    freqs, mag = frame.arrays["x"], frame.arrays["S1-X"]
    assert freqs[0] == pytest.approx(0.0, abs=0.1)
    assert freqs[-1] == pytest.approx(FS / 2, rel=0.01)      # Nyquist at the end
    assert freqs[int(np.argmax(mag))] == pytest.approx(137.0, abs=1.0)


def test_hann_window_suppresses_leakage_from_a_non_integer_bin(calibration, viewer):
    """A tone deliberately placed between bins. With the rectangular window
    MEG_DSP used, energy smears across the whole spectrum; with a Hann window it
    stays local. Assert the skirt well away from the tone is small."""
    snap = make_snapshot(_tone(amp=1.0, freq=50.25), FS)
    frame = build(spec("spectrum", ["S1-X"], mode="amplitude"),
                  calibration, viewer).compute(snap)
    freqs, mag = frame.arrays["x"], frame.arrays["S1-X"]
    far = mag[np.abs(freqs - 50.25) > 5.0]
    assert far.max() < 0.01 * mag.max()


def test_spectrum_rejects_an_unknown_mode(calibration, viewer):
    snap = make_snapshot(_tone(), FS)
    with pytest.raises(ValueError, match="mode must be"):
        build(spec("spectrum", ["S1-X"], mode="bogus"), calibration, viewer).compute(snap)


def test_spectrum_survives_an_almost_empty_buffer(calibration, viewer):
    snap = make_snapshot(np.zeros((1, 3)), FS)
    frame = build(spec("spectrum", ["S1-X"], window_s=0.003),
                  calibration, viewer).compute(snap)
    assert frame.meta["filling"] is True
    assert frame.arrays["x"].size == 0


# ---------------------------------------------------------------- phase

def test_phase_recovers_a_known_slope_and_correlation(calibration, viewer):
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, 2000)
    y = 2.5 * x + 0.75                       # exactly correlated, known gain
    snap = make_snapshot(np.stack([x, y]), FS)

    frame = build(spec("phase", ["S1-X", "S1-Y"]), calibration, viewer).compute(snap)
    assert frame.meta["r"] == pytest.approx(1.0, abs=1e-6)
    assert frame.meta["slope"] == pytest.approx(2.5, rel=1e-6)
    assert frame.meta["intercept"] == pytest.approx(0.75, abs=1e-6)


def test_phase_reports_partial_correlation(calibration, viewer):
    rng = np.random.default_rng(11)
    common = rng.normal(0, 1, 4000)
    x = common + rng.normal(0, 0.5, 4000)
    y = common + rng.normal(0, 0.5, 4000)
    snap = make_snapshot(np.stack([x, y]), FS)

    frame = build(spec("phase", ["S1-X", "S1-Y"], window_s=4.0),
                  calibration, viewer).compute(snap)
    # Two channels sharing one common-mode source with independent noise:
    # r = var_common / (var_common + var_noise) = 1 / 1.25 = 0.8
    assert frame.meta["r"] == pytest.approx(0.8, abs=0.03)


def test_phase_on_a_railed_channel_returns_none_not_nan(calibration, viewer):
    """A clipped channel is constant, so Pearson r is undefined. It must come back
    as null rather than a NaN that JSON cannot encode and the UI cannot draw."""
    x = np.full(1000, 5.0)                   # pinned at the rail
    y = np.random.default_rng(0).normal(0, 1, 1000)
    snap = make_snapshot(np.stack([x, y]), FS)

    frame = build(spec("phase", ["S1-X", "S1-Y"], window_s=1.0),
                  calibration, viewer).compute(snap)
    assert frame.meta["r"] is None
    assert frame.meta["slope"] is None


def test_phase_with_too_few_channels_reports_an_error(calibration, viewer):
    snap = make_snapshot(np.zeros((1, 500)), FS)
    frame = build(spec("phase", ["S1-X"], window_s=0.5), calibration, viewer).compute(snap)
    assert "error" in frame.meta


def test_phase_is_capped_by_the_point_budget(calibration, viewer):
    snap = make_snapshot(np.random.default_rng(0).normal(size=(2, 50_000)), FS)
    frame = build(spec("phase", ["S1-X", "S1-Y"], window_s=50.0),
                  calibration, viewer).compute(snap)
    assert frame.arrays["x"].size == viewer.phase_points


# ---------------------------------------------------------------- stats

def test_stats_flags_a_railed_channel_and_not_a_clean_one(calibration):
    clean = np.random.default_rng(0).normal(0, 0.1, 1000)
    railed = np.full(1000, 5.0)              # sitting on the +5 V rail
    snap = make_snapshot(np.stack([clean, railed]), FS)

    stats = channel_stats(snap, calibration, "V", (-5.0, 5.0))
    assert stats[0]["saturated"] is False
    assert stats[1]["saturated"] is True
    assert stats[1]["clipped_fraction"] == pytest.approx(1.0)


def test_stats_does_not_flag_a_channel_just_below_the_rail(calibration):
    near = np.full(1000, 4.8)               # 96% of rail; threshold is 98%
    snap = make_snapshot(near.reshape(1, -1), FS)
    stats = channel_stats(snap, calibration, "V", (-5.0, 5.0))
    assert stats[0]["saturated"] is False


def test_stats_converts_units_and_keeps_saturation_in_volts(calibration):
    """The clipping decision must not depend on the (unverified) V/nT constant."""
    railed = np.full(1000, -5.0)
    snap = make_snapshot(railed.reshape(1, -1), FS)

    in_volts = channel_stats(snap, calibration, "V", (-5.0, 5.0))[0]
    in_pT = channel_stats(snap, calibration, "pT", (-5.0, 5.0))[0]

    assert in_volts["mean"] == pytest.approx(-5.0)
    assert in_pT["mean"] == pytest.approx(-5.0 / 2.7 * 1000)
    assert in_volts["saturated"] is True
    assert in_pT["saturated"] is True       # same verdict, different display units


def test_stats_on_empty_snapshot_is_all_none(calibration):
    snap = make_snapshot(np.zeros((3, 0)), FS)
    stats = channel_stats(snap, calibration, "pT", (-5.0, 5.0))
    assert len(stats) == 3
    assert all(s["mean"] is None for s in stats)
