"""
Lightweight matplotlib scope — the reliable fallback.

No server, no browser, no socket. A timer pulls straight from the ring buffer in
the same process, so there is nothing between acquisition and the screen that can
stall, congest or time out.

It reuses the same DataSource and the same reducers as the browser viewer, so the
DSP is identical — windowing, ASD scaling, the volts-based saturation check and
the correlation maths are all the tested code. Only the rendering differs. What
you give up is runtime reconfiguration: panes are chosen on the command line and
fixed for the session.

Rendering uses blitting, and it has to. A full matplotlib redraw of three panes
costs ~120 ms (~8 fps), and rewriting the titles each frame pushes it past 170 ms
— the redraw dominates completely, and no amount of thinning the data helps.
Blitting the traces over a cached background costs ~19 ms instead. So the static
furniture (axes, ticks, grid, labels) is drawn once, only the traces are redrawn,
and a full redraw happens solely when the axis limits genuinely need to move.

Usage:
    python -m fieldzero.scope --mock
    python -m fieldzero.scope --pane time:S1-X,S2-X --pane spectrum:S1-X
    python -m fieldzero.scope --pane phase:S1-X,S2-X --window 5
"""

from __future__ import annotations

import argparse
import sys
import time

import matplotlib.pyplot as plt
import numpy as np

from .config import AppConfig, ViewerConfig
from .datasource import DataSource, MockSignal, NIDAQ
from .reducers import PaneSpec, build, channel_stats

# Fewer points than the browser gets: on a plot a few hundred pixels wide there is
# nothing to see beyond this, and every point costs blit time.
SCOPE_POINTS = 500

# Rescale only when the data leaves the current limits, or rattles around in less
# than this fraction of them. Rescaling forces a full redraw, so doing it every
# frame would throw away everything blitting buys.
SHRINK_THRESHOLD = 0.5
GROW_MARGIN = 0.15

# Text is by far the most expensive thing to blit: rasterising the readout costs
# ~27 ms, against ~22 ms for every trace in every pane put together. So no text
# lives inside a pane's axes — the axes hold traces and nothing else — and the
# readout is a strip with its own bbox, blitted independently at this rate.
# Nobody reads numbers at 10 Hz anyway.
STATUS_HZ = 2.0

SERIES_COLORS = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd", "#17becf"]


class Pane:
    """One subplot, driven by one reducer. Owns only blittable artists."""

    def __init__(self, ax: plt.Axes, spec: PaneSpec, config: AppConfig):
        self.ax = ax
        self.spec = spec
        self.config = config
        self.viewer = ViewerConfig(decimation_points=SCOPE_POINTS,
                                   phase_points=SCOPE_POINTS)
        self.lines: list[plt.Line2D] = []
        self.fit_line: plt.Line2D | None = None
        self.legend = None
        self.readout = ""          # picked up by the status strip, not drawn here
        self._built = False

    @property
    def artists(self) -> list:
        """Traces only — deliberately no text. Everything else (legend, axis
        labels) sits in the cached background and is never redrawn."""
        out = list(self.lines)
        if self.fit_line is not None:
            out.append(self.fit_line)
        return out

    def _build(self, names: list[str], meta: dict) -> None:
        if self.spec.kind == "phase":
            (line,) = self.ax.plot([], [], linestyle="", marker=".", markersize=1.5,
                                   alpha=0.45, color=SERIES_COLORS[0])
            self.lines = [line]
            (self.fit_line,) = self.ax.plot([], [], color="#ff7f0e", linewidth=1.2)
        else:
            self.lines = [
                self.ax.plot([], [], linewidth=0.9, label=n,
                             color=SERIES_COLORS[i % len(SERIES_COLORS)])[0]
                for i, n in enumerate(names)
            ]
            if len(names) > 1:
                # Placed ABOVE the axes, deliberately. Blitting only restores
                # ax.bbox, so anything outside it is never overdrawn and can stay
                # baked into the cached background at zero cost per frame. A
                # legend inside the axes is painted through by the traces; and
                # re-blitting it each frame costs ~130 ms in text layout, which
                # is more than the entire rest of the redraw.
                # Right-aligned above the axes; the title takes the left, so the
                # two share the strip without colliding.
                self.legend = self.ax.legend(
                    loc="lower right", bbox_to_anchor=(1.0, 1.005), fontsize=7,
                    ncol=len(names), frameon=False, borderaxespad=0.0,
                    handlelength=1.4, columnspacing=1.4)
            if self.spec.kind == "spectrum":
                self.ax.set_yscale("log")

        # Titles sit above the axes, so they are outside ax.bbox and survive in the
        # cached background for free. They are set once and never change; anything
        # that varies (r, slope, means) goes to the status strip instead.
        if self.spec.kind == "spectrum":
            self.ax.set_title(
                f"{meta.get('mode', '')} — Δf {meta.get('resolution_hz', 0):.2f} Hz",
                fontsize=8, loc="left")
        elif self.spec.kind == "phase":
            self.ax.set_title(f"{names[0]} vs {names[1]}", fontsize=8, loc="left")

        self.ax.set_xlabel(meta.get("x_label", ""), fontsize=8)
        self.ax.set_ylabel(meta.get("y_label", ""), fontsize=8)
        self.ax.tick_params(labelsize=7)
        self.ax.grid(True, alpha=0.25, linewidth=0.5)
        self._built = True

    def _rescale_needed(self, lo: float, hi: float, cur: tuple[float, float]) -> bool:
        c0, c1 = cur
        if not np.isfinite([lo, hi, c0, c1]).all() or hi <= lo:
            return False
        if lo < c0 or hi > c1:
            return True
        return (hi - lo) < SHRINK_THRESHOLD * (c1 - c0)

    def update(self, snapshot) -> bool:
        """Refresh the traces. Returns True if the axis limits moved, meaning the
        caller must do a full redraw rather than a blit."""
        frame = build(self.spec, self.config.calibration, self.viewer).compute(snapshot)
        meta = frame.meta
        names = meta.get("series", [])

        x = frame.arrays.get("x")
        if x is None or x.size == 0:
            return False
        if not self._built:
            self._build(names, meta)
            return True                    # first draw must be a full one

        rescaled = False

        if self.spec.kind == "phase":
            y = frame.arrays["y"]
            self.lines[0].set_data(x, y)
            r, slope, icept = meta.get("r"), meta.get("slope"), meta.get("intercept")
            if slope is not None and x.size:
                edge = np.array([x.min(), x.max()])
                self.fit_line.set_data(edge, slope * edge + icept)
                self.readout = (f"{names[0]}/{names[1]}: r={r:+.4f} slope={slope:+.4f}")
            else:
                self.fit_line.set_data([], [])
                self.readout = f"{names[0]}/{names[1]}: r undefined (no variance)"
            for axis, data in (("x", x), ("y", y)):
                lo, hi = float(np.min(data)), float(np.max(data))
                cur = self.ax.get_xlim() if axis == "x" else self.ax.get_ylim()
                if self._rescale_needed(lo, hi, cur):
                    pad = max((hi - lo) * GROW_MARGIN, 1e-9)
                    setter = self.ax.set_xlim if axis == "x" else self.ax.set_ylim
                    setter(lo - pad, hi + pad)
                    rescaled = True
            return rescaled

        lo, hi = np.inf, -np.inf
        for line, name in zip(self.lines, names):
            y = frame.arrays[name]
            if self.spec.kind == "spectrum":
                # A log axis cannot draw a zero, and a railed channel's spectrum is
                # all zeros. Mask, so it cannot drag the scale down for everyone.
                y = np.where(y > 0, y, np.nan)
            line.set_data(x, y)
            if np.isfinite(y).any():
                lo = min(lo, float(np.nanmin(y)))
                hi = max(hi, float(np.nanmax(y)))

        self.ax.set_xlim(float(x[0]), float(x[-1]))

        if np.isfinite([lo, hi]).all() and hi > lo:
            if self.spec.kind == "spectrum":
                # Decades below the peak, snapped — same reasoning as the browser.
                top = 10 ** np.ceil(np.log10(hi))
                want = (top / 10**6, top)
                if not np.allclose(self.ax.get_ylim(), want, rtol=0.01):
                    self.ax.set_ylim(*want)
                    rescaled = True
            elif self._rescale_needed(lo, hi, self.ax.get_ylim()):
                pad = max((hi - lo) * GROW_MARGIN, 1e-9)
                self.ax.set_ylim(lo - pad, hi + pad)
                rescaled = True

        return rescaled


def parse_pane(text: str, config: AppConfig, window_s: float, units: str) -> PaneSpec:
    """`time:S1-X,S1-Y` -> a PaneSpec. Channels are optional for time/spectrum."""
    kind, _, chans = text.partition(":")
    kind = kind.strip().lower()
    if kind not in ("time", "spectrum", "phase"):
        raise argparse.ArgumentTypeError(
            f"pane kind must be time, spectrum or phase — got {kind!r}")

    known = [c.name for c in config.daq.channels]
    names = [c.strip() for c in chans.split(",") if c.strip()] or known
    for n in names:
        if n not in known:
            raise argparse.ArgumentTypeError(f"unknown channel {n!r}; known: {known}")
    if kind == "phase" and len(names) != 2:
        raise argparse.ArgumentTypeError(
            f"a phase pane needs exactly 2 channels, got {len(names)}")

    opts = {"mode": "asd"} if kind == "spectrum" else {}
    return PaneSpec(id=text, kind=kind, channels=tuple(names),
                    window_s=window_s, units=units, opts=opts)


class Scope:
    """Owns the figure and the blit loop."""

    def __init__(self, source: DataSource, config: AppConfig,
                 specs: list[PaneSpec], units: str, fps: float):
        self.source = source
        self.config = config
        self.units = units
        self.fps = fps

        rows = len(specs) + 1  # one thin strip at the top for the stats readout
        heights = [0.5] + [3.0] * len(specs)
        self.fig, axs = plt.subplots(
            rows, 1, figsize=(11, 1.0 + 2.6 * len(specs)), squeeze=False,
            gridspec_kw={"height_ratios": heights})
        self.fig.canvas.manager.set_window_title("FieldZero scope")

        self.status_ax = axs[0][0]
        self.status_ax.axis("off")
        self.status = self.status_ax.text(
            0.0, 0.5, "waiting for samples…", transform=self.status_ax.transAxes,
            va="center", fontsize=8, family="monospace")

        self.panes = [Pane(axs[i + 1][0], s, self.config) for i, s in enumerate(specs)]
        self.needed = int(round(max(s.window_s for s in specs) * config.daq.sample_rate))

        self._status_every = max(1, int(round(fps / STATUS_HZ)))
        self._ticks = 0

        self.fig.tight_layout()
        self._backgrounds: list = []
        # Recapture the cached backgrounds after ANY full redraw — our own, a
        # window resize, or a toolbar action. Without this a resize leaves the
        # blits painting onto a stale background.
        self.fig.canvas.mpl_connect("draw_event", self._capture)

    def _blit_axes(self) -> list[plt.Axes]:
        return [self.status_ax] + [p.ax for p in self.panes]

    def _capture(self, _event=None) -> None:
        self._backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox)
                             for ax in self._blit_axes()]

    def _status_text(self, snapshot) -> tuple[str, str]:
        stats = channel_stats(snapshot, self.config.calibration, self.units,
                              self.config.daq.voltage_range)
        railed = [s["name"] for s in stats if s["saturated"]]
        extra = "   ".join(p.readout for p in self.panes if p.readout)

        if railed:
            # A clipped channel still reports a plausible-looking mean. This
            # warning is the one thing that must never be missed.
            return (f"AT THE INPUT RAIL: {', '.join(railed)}  -  their {self.units} "
                    f"values are meaningless", "#d62728")
        body = "  ".join(f"{s['name']} {s['mean']:+8.1f}+-{s['std']:.1f}" for s in stats)
        return f"{self.units}: {body}    {extra}", "#333333"

    def tick(self) -> None:
        snapshot = self.source.get_data(self.needed)
        if snapshot.n_samples == 0:
            return

        full = False
        for pane in self.panes:
            full |= pane.update(snapshot)

        self._ticks += 1
        due = self._ticks % self._status_every == 0

        if full or not self._backgrounds:
            # Limits moved, so the cached background (ticks, gridlines) is stale.
            # Pay for one full redraw; _capture refreshes the cache via draw_event.
            text, color = self._status_text(snapshot)
            self.status.set_text(text)
            self.status.set_color(color)
            self.fig.canvas.draw_idle()
            return

        canvas = self.fig.canvas

        # The traces: every tick, and cheap, because the axes hold nothing else.
        for pane, bg in zip(self.panes, self._backgrounds[1:]):
            canvas.restore_region(bg)
            for artist in pane.artists:
                pane.ax.draw_artist(artist)
            canvas.blit(pane.ax.bbox)

        # The readout: its own bbox, so it can be left alone on the ticks where we
        # skip it. Untouched pixels simply persist from the last blit.
        if due:
            text, color = self._status_text(snapshot)
            self.status.set_text(text)
            self.status.set_color(color)
            canvas.restore_region(self._backgrounds[0])
            self.status_ax.draw_artist(self.status)
            canvas.blit(self.status_ax.bbox)

        canvas.flush_events()

    def _on_timer(self) -> None:
        # matplotlib's Tk timer re-arms with after(interval) only once the callback
        # has returned, so the real period is interval + work, not interval — at
        # 10 fps with 55 ms of drawing that yields about 6 fps. Tick faster than
        # the target and gate on elapsed time instead, so the requested rate is
        # actually met whenever the work fits inside it.
        now = time.perf_counter()
        if now - self._last_render < 1.0 / self.fps:
            return
        self._last_render = now
        self.tick()

    def run(self) -> None:
        self._last_render = 0.0
        timer = self.fig.canvas.new_timer(interval=max(5, int(250.0 / self.fps)))
        timer.add_callback(self._on_timer)
        timer.start()
        plt.show()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fieldzero.scope",
        description="Lightweight matplotlib scope (fallback for the browser viewer)")
    parser.add_argument("--mock", action="store_true", help="no DAQ hardware required")
    parser.add_argument("--pane", action="append", default=None, metavar="KIND[:CH,CH]",
                        help="repeatable, e.g. time:S1-X,S2-X | spectrum:S1-Z | phase:S1-X,S2-X")
    parser.add_argument("--window", type=float, default=5.0, help="seconds of history (default 5)")
    parser.add_argument("--units", choices=["pT", "V"], default="pT")
    parser.add_argument("--fps", type=float, default=10.0, help="redraw rate (default 10)")
    parser.add_argument("--sample-rate", type=float, default=None)
    args = parser.parse_args(argv)

    config = AppConfig()
    if args.sample_rate is not None:
        config = config.with_sample_rate(args.sample_rate)

    try:
        specs = [parse_pane(p, config, args.window, args.units)
                 for p in (args.pane or ["time"])]
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    source: DataSource
    if args.mock:
        source = MockSignal(config.daq)
        source.start()
    else:
        try:
            source = NIDAQ(config.daq)
        except Exception as exc:
            print(f"Could not open the NI-DAQ: {exc}", file=sys.stderr)
            print("Run with --mock to use the simulated source.", file=sys.stderr)
            return 1

    vmin, vmax = config.daq.voltage_range
    print(f"FieldZero scope — source={type(source).__name__} "
          f"fs={config.daq.sample_rate:g} Hz  range={vmin:+g}..{vmax:+g} V  "
          f"panes={len(specs)}")
    print("Close the window to stop.")

    try:
        Scope(source, config, specs, args.units, args.fps).run()
    except KeyboardInterrupt:
        pass
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
