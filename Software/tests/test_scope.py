"""
Tests for the matplotlib fallback scope.

The DSP is not retested here — the scope drives the same reducers as the browser
viewer, and those are covered in test_reducers.py. What matters is that the
command line maps onto the right panes, and that a tick actually puts the right
numbers on the right artists.

Rendering uses the Agg backend so this runs headless.
"""

import matplotlib

matplotlib.use("Agg")

import time

import numpy as np
import pytest

from fieldzero.config import AppConfig
from fieldzero.datasource import MockSignal
from fieldzero.scope import Pane, Scope, parse_pane


@pytest.fixture(scope="module")
def app() -> AppConfig:
    return AppConfig()


@pytest.fixture(scope="module")
def filled_source(app):
    """A MockSignal with a full window already in the ring buffer."""
    source = MockSignal(app.daq, seed=5)
    source.start()
    deadline = time.time() + 15
    while source.get_data(3000).n_samples < 3000 and time.time() < deadline:
        time.sleep(0.1)
    yield source
    source.close()


# ---------------------------------------------------------------- pane parsing

def test_bare_kind_defaults_to_every_channel(app):
    spec = parse_pane("time", app, 5.0, "pT")
    assert spec.kind == "time"
    assert spec.channels == tuple(c.name for c in app.daq.channels)


def test_channels_can_be_listed(app):
    spec = parse_pane("spectrum:S1-X,S2-Z", app, 5.0, "V")
    assert spec.kind == "spectrum"
    assert spec.channels == ("S1-X", "S2-Z")
    assert spec.units == "V"
    assert spec.opts["mode"] == "asd"


def test_unknown_kind_is_rejected(app):
    with pytest.raises(Exception, match="time, spectrum or phase"):
        parse_pane("waterfall:S1-X", app, 5.0, "pT")


def test_unknown_channel_is_rejected(app):
    with pytest.raises(Exception, match="unknown channel"):
        parse_pane("time:S9-Q", app, 5.0, "pT")


def test_phase_demands_exactly_two_channels(app):
    with pytest.raises(Exception, match="exactly 2 channels"):
        parse_pane("phase:S1-X", app, 5.0, "pT")
    with pytest.raises(Exception, match="exactly 2 channels"):
        parse_pane("phase:S1-X,S1-Y,S1-Z", app, 5.0, "pT")


# ---------------------------------------------------------------- rendering

def _scope(app, filled_source, panes, fps=10.0):
    specs = [parse_pane(p, app, 3.0, "pT") for p in panes]
    scope = Scope(filled_source, app, specs, "pT", fps)
    scope.tick()                      # first tick builds artists, forces a full draw
    scope.fig.canvas.draw()
    scope.tick()
    return scope


def test_a_tick_puts_data_on_every_trace(app, filled_source):
    scope = _scope(app, filled_source, ["time:S1-X,S2-X"])
    pane = scope.panes[0]
    assert len(pane.lines) == 2
    for line in pane.lines:
        x, y = line.get_data()
        assert len(x) > 0 and len(x) == len(y)
    # x runs from -window to 0, newest sample last
    x, _ = pane.lines[0].get_data()
    assert x[-1] == pytest.approx(0.0, abs=0.02)
    assert x[0] == pytest.approx(-3.0, abs=0.05)


def test_panes_hold_no_text_artists(app, filled_source):
    """The whole performance argument rests on this: text costs more to blit than
    every trace combined, so an axes must contain traces and nothing else."""
    scope = _scope(app, filled_source, ["time:S1-X", "phase:S1-X,S2-X"])
    for pane in scope.panes:
        assert all(isinstance(a, matplotlib.lines.Line2D) for a in pane.artists)


def test_phase_readout_reports_the_common_mode_correlation(app, filled_source):
    scope = _scope(app, filled_source, ["phase:S1-X,S2-X"])
    readout = scope.panes[0].readout
    assert "r=+0.9" in readout, readout          # mock's sensors share a mains signal
    assert "slope=" in readout


def test_status_strip_warns_about_the_railed_channel(app, filled_source):
    scope = _scope(app, filled_source, ["time"])
    scope.tick()
    text = scope.status.get_text()
    # MockSignal drives S1-Z past the +5 V rail on purpose.
    assert "AT THE INPUT RAIL" in text
    assert "S1-Z" in text


def test_steady_state_needs_no_full_redraws(app, filled_source):
    """
    Blitting only pays off if the axis limits settle. If a pane rescaled every
    frame it would force a full redraw each time and be slower than not blitting
    at all — so assert the hysteresis actually holds.
    """
    scope = _scope(app, filled_source, ["time:S1-X,S2-X", "spectrum:S1-X"])
    for _ in range(10):                       # let the limits settle
        scope.tick()
        scope.fig.canvas.draw()

    redraws = 0
    original = scope.fig.canvas.draw_idle

    def counting():
        nonlocal redraws
        redraws += 1
        return original()

    scope.fig.canvas.draw_idle = counting
    for _ in range(20):
        scope.tick()

    assert redraws == 0, f"{redraws}/20 ticks forced a full redraw"


def test_an_empty_buffer_does_not_raise(app):
    """Started before any samples exist, the scope must wait rather than crash."""
    source = MockSignal(app.daq, seed=1)      # deliberately not started
    scope = Scope(source, app, [parse_pane("time", app, 3.0, "pT")], "pT", 10.0)
    scope.tick()                              # no samples yet
    assert scope.panes[0].lines == []
    source.close()
