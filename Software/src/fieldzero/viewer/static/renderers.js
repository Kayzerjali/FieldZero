/*
 * Renderer registry — the browser-side mirror of the Python reducer registry.
 *
 * A pane kind is a `kind` string on both sides: the reducer produces the arrays,
 * the renderer named by the same string draws them. Adding a pane type is one
 * Python class plus one class here; the layout, protocol and server never change.
 *
 * uPlot backs the time and spectrum panes, which are ordinary ascending-x series
 * and exactly what it is built for. The phase pane gets a hand-rolled canvas
 * scatter instead: uPlot assumes a sorted x axis, and a correlation cloud has no
 * such ordering, so fighting the library there would cost more than drawing it.
 */

const SERIES_COLORS = [
  "#4da3ff", "#4ade80", "#fbbf24", "#f472b6", "#a78bfa", "#22d3ee",
];

// Colour is a property of the channel, not of its position in a pane's series
// list. Keying on the channel's index in the session map means S1-Z is the same
// colour in every pane and every legend, so the swatch in the picker and the
// trace on the plot always agree — the one thing that lets you read a six-trace
// overlay at all.
function colorForChannel(session, name) {
  const i = session.channels.findIndex((c) => c.name === name);
  return SERIES_COLORS[(i < 0 ? 0 : i) % SERIES_COLORS.length];
}

// Auto-range that ignores flat (railed or dead) channels. A constant trace
// carries no scale information, and letting a channel pinned at the rail set the
// y-range squashes every healthy channel into a sliver. Excluding it lets the
// dead channel fall off-scale instead — the same honest choice the spectrum pane
// already makes. Falls back to the full span only when every channel is flat.
function robustRange(series) {
  let lo = Infinity, hi = -Infinity;        // over channels with real variation
  let loAll = Infinity, hiAll = -Infinity;  // fallback when all are flat
  for (const y of series) {
    let mn = Infinity, mx = -Infinity;
    for (let i = 0; i < y.length; i++) {
      const v = y[i];
      if (v < mn) mn = v;
      if (v > mx) mx = v;
    }
    if (mn < loAll) loAll = mn;
    if (mx > hiAll) hiAll = mx;
    const scale = Math.max(Math.abs(mn), Math.abs(mx), 1e-12);
    if (mx - mn > 1e-6 * scale) {           // has real variation
      if (mn < lo) lo = mn;
      if (mx > hi) hi = mx;
    }
  }
  if (!(lo < hi)) { lo = loAll; hi = hiAll; }   // all flat: show everything
  if (!(lo < hi)) return [null, null];          // no data: let uPlot decide
  const pad = (hi - lo) * 0.06 || Math.abs(hi) * 0.06 || 1;
  return [lo - pad, hi + pad];
}

const AXIS_STYLE = {
  stroke: "#8c98a8",
  grid: { stroke: "#232a34", width: 1 },
  ticks: { stroke: "#232a34", width: 1 },
};

class Renderer {
  constructor(el, spec, session) {
    this.el = el;
    this.spec = spec;
    this.session = session;
  }
  // pane: { meta, data: {name -> Float32Array} }
  update(pane) {}
  resize() {}
  destroy() {}
  // Optional short string shown in the pane header.
  readout(pane) { return ""; }
}

/* ------------------------------------------------------------------ uPlot base */

class UplotRenderer extends Renderer {
  constructor(el, spec, session) {
    super(el, spec, session);
    this.plot = null;
    this.seriesKey = null;
    // Our own legend, kept out of the plot so uPlot's built-in one — which lands
    // just under the canvas and is clipped away by the pane's overflow:hidden —
    // never has to be relied on. A sibling of uPlot's root, so plot.destroy()
    // leaves it alone.
    this._legendEl = document.createElement("div");
    this._legendEl.className = "plot-legend";
    el.appendChild(this._legendEl);
    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(el);
  }

  // Subclasses describe their axes/scales.
  options(names) { throw new Error("not implemented"); }

  _rebuild(names, data) {
    if (this.plot) { this.plot.destroy(); this.plot = null; }
    const opts = this.options(names);
    opts.width = this.el.clientWidth || 400;
    opts.height = this.el.clientHeight || 200;
    opts.series = [{}].concat(names.map((n) => ({
      label: n,
      stroke: colorForChannel(this.session, n),
      width: 1.2,
      points: { show: false },
    })));
    this.plot = new uPlot(opts, data, this.el);
    this.seriesKey = names.join("|");
    this._buildLegend(names);
  }

  // Shown only when more than one trace shares the pane; a single trace is named
  // by the pane's channel picker and the axis, so a legend would just cover data.
  _buildLegend(names) {
    this._legendEl.innerHTML = "";
    if (names.length < 2) return;
    for (const n of names) {
      const item = document.createElement("span");
      item.className = "leg-item";
      const sw = document.createElement("span");
      sw.className = "leg-sw";
      sw.style.background = colorForChannel(this.session, n);
      item.append(sw, document.createTextNode(n));
      this._legendEl.appendChild(item);
    }
  }

  // The plot is built from the first frame that actually carries points, never
  // from empty arrays. uPlot skips a scale's range() callback when there is no
  // data, so a log axis constructed empty gets a null minimum and tries to walk
  // infinitely many decades — it throws mid-construction, before it has sized
  // its canvas, and the plot is then permanently blank with no way to recover.
  update(pane) {
    const names = pane.meta.series || [];
    const x = pane.data.x;
    if (!x || x.length === 0) return;

    const series = names.map(
      (n) => this.transform(pane.data[n] || new Float32Array(x.length))
    );
    // Give subclasses the transformed series before the draw, so a managed scale
    // (see TimeRenderer) is up to date on the same frame rather than one behind.
    this.beforeSetData(series, names);
    const data = [x].concat(series);
    if (names.join("|") !== this.seriesKey) this._rebuild(names, data);
    if (this.plot) this.plot.setData(data);
  }

  transform(y) { return y; }
  beforeSetData(series, names) {}

  resize() {
    if (this.plot && this.el.clientWidth > 0 && this.el.clientHeight > 0) {
      this.plot.setSize({ width: this.el.clientWidth, height: this.el.clientHeight });
    }
  }

  destroy() {
    this._ro.disconnect();
    if (this.plot) this.plot.destroy();
    this.plot = null;
    if (this._legendEl) this._legendEl.remove();
  }
}

/* ------------------------------------------------------------------ time domain */

class TimeRenderer extends UplotRenderer {
  options(names) {
    const yr = this.spec.opts || {};
    const manual = yr.y_auto === false && yr.y_min != null && yr.y_max != null;
    this._manual = manual;
    this._autoRange = [null, null];
    return {
      padding: [8, 12, 0, 0],
      cursor: { drag: { x: true, y: false } },
      legend: { show: false },   // replaced by our own, unclipped, legend
      scales: {
        x: { time: false },
        // Even in "auto" we drive the range ourselves so a railed channel does
        // not dominate it (robustRange). uPlot's own auto has no per-series veto.
        y: manual
          ? { auto: false, range: [Number(yr.y_min), Number(yr.y_max)] }
          : { auto: false, range: () => this._autoRange },
      },
      axes: [
        { ...AXIS_STYLE, label: "time (s)", labelSize: 18 },
        { ...AXIS_STYLE, label: this.spec.units, labelSize: 18, size: 62 },
      ],
    };
  }

  // Optional AC coupling: subtract each channel's own mean so traces with very
  // different DC offsets (the residual field differs axis to axis) overlay on a
  // common fine scale instead of sitting decades apart. The stats table still
  // reports the true means.
  transform(y) {
    if (!(this.spec.opts || {}).remove_dc) return y;
    let sum = 0;
    for (let i = 0; i < y.length; i++) sum += y[i];
    const mean = sum / (y.length || 1);
    const out = new Float32Array(y.length);
    for (let i = 0; i < y.length; i++) out[i] = y[i] - mean;
    return out;
  }

  beforeSetData(series) {
    if (!this._manual) this._autoRange = robustRange(series);
  }

  readout(pane) {
    const n = pane.meta.n_raw || 0;
    return `${n} samples`;
  }
}

/* ------------------------------------------------------------------ spectrum */

// A log axis cannot plot a zero, and a railed channel is constant, so its entire
// spectrum is numerically zero. Left alone that drags the scale down fifteen
// decades and squashes every healthy channel into a sliver at the top. Show a
// fixed number of decades below the peak instead: the dead channel simply falls
// off the bottom, which is the honest depiction — it has no AC content.
const SPECTRUM_DECADES = 7;

class SpectrumRenderer extends UplotRenderer {
  options(names) {
    const logY = (this.spec.opts || {}).log_y !== false; // log by default
    return {
      padding: [8, 12, 0, 0],
      cursor: { drag: { x: true, y: false } },
      legend: { show: false },   // replaced by our own, unclipped, legend
      scales: {
        x: { time: false },
        y: logY
          ? {
              distr: 3,
              // Both bounds MUST be exact powers of ten. uPlot's log axis walks
              // minor ticks upward from the minimum, and starting off a decade
              // boundary its increment fails to grow — it then tries to build an
              // array of ~10^8 ticks and throws RangeError. That throw happens in
              // uPlot's deferred first draw, before it has sized its canvas, so
              // the pane goes permanently blank with nothing raised at the call
              // site. Snapping to decades is what `auto: true` does internally.
              range: (u, dataMin, dataMax) => {
                const top = Number.isFinite(dataMax) && dataMax > 0 ? dataMax : 1;
                const hiExp = Math.ceil(Math.log10(top));
                return [Math.pow(10, hiExp - SPECTRUM_DECADES), Math.pow(10, hiExp)];
              },
            }
          : { auto: true },
      },
      axes: [
        { ...AXIS_STYLE, label: "frequency (Hz)", labelSize: 18 },
        { ...AXIS_STYLE, label: this._yLabel, labelSize: 18, size: 62 },
      ],
    };
  }

  // Zeros need a positive stand-in so uPlot does not drop the point. Place it
  // just below the visible floor rather than at Number.MIN_VALUE — a denormal
  // that far from the data wrecks uPlot's internal scale arithmetic.
  transform(y) {
    const logY = (this.spec.opts || {}).log_y !== false;
    if (!logY) return y;
    let max = 0;
    for (let i = 0; i < y.length; i++) if (y[i] > max) max = y[i];
    const floor = max > 0 ? max / Math.pow(10, SPECTRUM_DECADES + 1) : 1e-30;
    const out = new Float64Array(y.length);
    for (let i = 0; i < y.length; i++) out[i] = y[i] > 0 ? y[i] : floor;
    return out;
  }

  update(pane) {
    this._yLabel = pane.meta.y_label || this.spec.units;
    super.update(pane);
  }

  readout(pane) {
    const df = pane.meta.resolution_hz;
    const mode = pane.meta.mode === "asd" ? "ASD" : "amplitude";
    return df ? `${mode} · Δf ${df.toFixed(2)} Hz` : mode;
  }
}

/* ------------------------------------------------------------------ phase */

class PhaseRenderer extends Renderer {
  constructor(el, spec, session) {
    super(el, spec, session);
    this.canvas = document.createElement("canvas");
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.display = "block";
    el.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d");
    this._ro = new ResizeObserver(() => { this._sized = false; this._draw(); });
    this._ro.observe(el);
    this._last = null;
  }

  _size() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.el.clientWidth, h = this.el.clientHeight;
    if (w === 0 || h === 0) return false;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this._w = w; this._h = h; this._sized = true;
    return true;
  }

  update(pane) { this._last = pane; this._draw(); }

  _draw() {
    if (!this._sized && !this._size()) return;
    const c = this.ctx, w = this._w, h = this._h;
    c.clearRect(0, 0, w, h);

    const pane = this._last;
    if (!pane || !pane.data.x || pane.data.x.length === 0) return;
    const xs = pane.data.x, ys = pane.data.y;

    const pad = { l: 62, r: 12, t: 10, b: 34 };
    const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
    if (pw <= 10 || ph <= 10) return;

    let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
    for (let i = 0; i < xs.length; i++) {
      if (xs[i] < xmin) xmin = xs[i];
      if (xs[i] > xmax) xmax = xs[i];
      if (ys[i] < ymin) ymin = ys[i];
      if (ys[i] > ymax) ymax = ys[i];
    }
    // A railed (constant) channel has zero span; give it a nominal one so the
    // cloud collapses to a visible line rather than dividing by zero.
    const spanX = (xmax - xmin) || 1, spanY = (ymax - ymin) || 1;
    xmin -= spanX * 0.05; xmax += spanX * 0.05;
    ymin -= spanY * 0.05; ymax += spanY * 0.05;

    const px = (v) => pad.l + ((v - xmin) / (xmax - xmin)) * pw;
    const py = (v) => pad.t + ph - ((v - ymin) / (ymax - ymin)) * ph;

    // frame + grid
    c.strokeStyle = "#232a34"; c.lineWidth = 1;
    c.fillStyle = "#8c98a8"; c.font = "11px ui-sans-serif, system-ui, sans-serif";
    for (let i = 0; i <= 4; i++) {
      const gx = pad.l + (pw * i) / 4, gy = pad.t + (ph * i) / 4;
      c.beginPath(); c.moveTo(gx, pad.t); c.lineTo(gx, pad.t + ph); c.stroke();
      c.beginPath(); c.moveTo(pad.l, gy); c.lineTo(pad.l + pw, gy); c.stroke();
      const xv = xmin + ((xmax - xmin) * i) / 4;
      const yv = ymax - ((ymax - ymin) * i) / 4;
      c.textAlign = "center"; c.fillText(fmt(xv), gx, pad.t + ph + 15);
      c.textAlign = "right";  c.fillText(fmt(yv), pad.l - 6, gy + 4);
    }

    // points
    c.fillStyle = "rgba(77,163,255,0.42)";
    for (let i = 0; i < xs.length; i++) {
      c.fillRect(px(xs[i]) - 1, py(ys[i]) - 1, 2, 2);
    }

    // least-squares fit, drawn across the visible x range
    const m = pane.meta;
    if (m.slope != null && m.intercept != null) {
      c.strokeStyle = "#fbbf24"; c.lineWidth = 1.4;
      c.beginPath();
      c.moveTo(px(xmin), py(m.slope * xmin + m.intercept));
      c.lineTo(px(xmax), py(m.slope * xmax + m.intercept));
      c.stroke();
    }

    c.fillStyle = "#8c98a8"; c.textAlign = "center";
    c.fillText(m.x_label || "x", pad.l + pw / 2, h - 4);
    c.save();
    c.translate(12, pad.t + ph / 2); c.rotate(-Math.PI / 2);
    c.fillText(m.y_label || "y", 0, 0);
    c.restore();
  }

  readout(pane) {
    const m = pane.meta;
    if (m.error) return "";
    if (m.r == null) return "r —  (channel has no variance)";
    return `r = ${m.r.toFixed(4)}   slope = ${m.slope.toFixed(4)}`;
  }

  destroy() { this._ro.disconnect(); this.canvas.remove(); }
}

function fmt(v) {
  const a = Math.abs(v);
  if (a === 0) return "0";
  if (a >= 1e5 || a < 1e-2) return v.toExponential(1);
  return v.toFixed(a >= 100 ? 0 : a >= 1 ? 1 : 3);
}

/* ------------------------------------------------------------------ registry */

const RENDERERS = {
  time: TimeRenderer,
  spectrum: SpectrumRenderer,
  phase: PhaseRenderer,
};

// Per-kind UI: which extra controls the pane header offers, and how many
// channels the kind accepts. Keeps app.js free of per-kind special-casing.
const KIND_UI = {
  time: {
    label: "Time",
    channels: "many",
    controls: [
      { key: "remove_dc", type: "check", label: "remove DC", default: false },
      { key: "y_auto", type: "check", label: "auto-y", default: true },
      { key: "y_min", type: "number", label: "min", showWhen: (o) => o.y_auto === false },
      { key: "y_max", type: "number", label: "max", showWhen: (o) => o.y_auto === false },
    ],
  },
  spectrum: {
    label: "Frequency",
    channels: "many",
    controls: [
      { key: "mode", type: "select", label: "", options: [["asd", "ASD"], ["amplitude", "amplitude"]], default: "asd" },
      { key: "log_y", type: "check", label: "log y", default: true },
      { key: "remove_dc", type: "check", label: "remove DC", default: false },
    ],
  },
  phase: {
    label: "Phase",
    channels: 2,
    controls: [],
  },
};
