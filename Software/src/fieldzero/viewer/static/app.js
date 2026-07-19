/*
 * Layout, controls and transport.
 *
 * The layout is a binary tree of splits and panes, rendered as nested flexboxes.
 * Splitting a pane replaces it in the tree with a split node holding the old pane
 * and a new one; closing a pane replaces its parent split with the surviving
 * sibling. That is the whole model, and it generalises from "split this in two"
 * to any arrangement without a grid to fight.
 *
 * The browser owns this state and pushes it to the server as a flat list of pane
 * specs. The server holds no display state at all.
 */

let SESSION = null;      // channel map, sample rate, ranges — from /api/session
let LAYOUT = null;       // the tree
let SOCKET = null;
const RENDERER_BY_ID = new Map();

const $ = (sel) => document.querySelector(sel);
let uid = 0;
const nextId = () => `p${++uid}`;

/* ------------------------------------------------------------------ tree ops */

function newPane(overrides = {}) {
  const kind = overrides.kind || "time";
  const ui = KIND_UI[kind];
  const opts = {};
  for (const c of ui.controls) if (c.default !== undefined) opts[c.key] = c.default;

  const names = SESSION.channels.map((c) => c.name);
  const defaultChannels = ui.channels === 2 ? names.slice(0, 2) : names.slice(0, 3);

  return {
    t: "pane",
    id: nextId(),
    kind,
    channels: defaultChannels,
    window_s: SESSION.default_window_s,
    units: "pT",
    opts,
    ...overrides,
  };
}

function findParent(node, id, parent = null) {
  if (node.t === "pane") return node.id === id ? parent : null;
  return findParent(node.a, id, node) || findParent(node.b, id, node);
}

function findPane(node, id) {
  if (node.t === "pane") return node.id === id ? node : null;
  return findPane(node.a, id) || findPane(node.b, id);
}

function splitPane(id, dir) {
  const pane = findPane(LAYOUT, id);
  const parent = findParent(LAYOUT, id);
  // The new pane inherits the old one's config: splitting is nearly always
  // "show me this again, but differently", not "start from nothing".
  const sibling = newPane({ kind: pane.kind, channels: [...pane.channels],
                            window_s: pane.window_s, units: pane.units,
                            opts: { ...pane.opts } });
  const split = { t: "split", dir, ratio: 0.5, a: pane, b: sibling };
  if (parent === null) LAYOUT = split;
  else if (parent.a === pane) parent.a = split;
  else parent.b = split;
  rerender();
}

function closePane(id) {
  const parent = findParent(LAYOUT, id);
  if (parent === null) return; // the last pane has no parent split; keep it
  const survivor = parent.a.t === "pane" && parent.a.id === id ? parent.b : parent.a;
  const grand = findSplitParent(LAYOUT, parent); // null when parent is the root
  if (grand === null) LAYOUT = survivor;
  else if (grand.a === parent) grand.a = survivor;
  else grand.b = survivor;
  rerender();
}

function findSplitParent(node, target, parent = null) {
  if (node === target) return parent;
  if (node.t === "pane") return null;
  return findSplitParent(node.a, target, node) || findSplitParent(node.b, target, node);
}

function allPanes(node = LAYOUT, out = []) {
  if (node.t === "pane") out.push(node);
  else { allPanes(node.a, out); allPanes(node.b, out); }
  return out;
}

/* ------------------------------------------------------------------ DOM */

// Renderers must be constructed after their element is in the document, so that
// they can measure it. buildNode collects them here and rerender instantiates
// them once the tree is attached.
//
// This is deliberately synchronous. An earlier version deferred construction to
// requestAnimationFrame, which Chrome throttles to zero in a background or
// unfocused tab: build a layout while the window is not focused and the plots
// never appear at all, while the stats table keeps updating and makes it look
// like the data is fine.
let PENDING_RENDERERS = [];

function rerender() {
  const root = $("#layout");
  for (const r of RENDERER_BY_ID.values()) r.destroy();
  RENDERER_BY_ID.clear();
  PENDING_RENDERERS = [];

  root.innerHTML = "";
  root.appendChild(buildNode(LAYOUT));

  for (const { pane, plotEl, readoutEl } of PENDING_RENDERERS) {
    const r = new RENDERERS[pane.kind](plotEl, pane, SESSION);
    r._readoutEl = readoutEl;
    r._plotEl = plotEl;
    RENDERER_BY_ID.set(pane.id, r);
  }
  PENDING_RENDERERS = [];

  saveLocal();
  pushSpecs();
}

function buildNode(node) {
  if (node.t === "pane") return buildPane(node);

  const el = document.createElement("div");
  el.className = `split ${node.dir}`;
  const a = buildNode(node.a);
  const b = buildNode(node.b);
  a.style.flexGrow = String(node.ratio * 2);
  b.style.flexGrow = String((1 - node.ratio) * 2);

  const divider = document.createElement("div");
  divider.className = "divider";
  divider.addEventListener("mousedown", (ev) => startDrag(ev, node, el, a, b));

  el.append(a, divider, b);
  return el;
}

function startDrag(ev, node, splitEl, aEl, bEl) {
  ev.preventDefault();
  const horizontal = node.dir === "row";
  const move = (e) => {
    const r = splitEl.getBoundingClientRect();
    const frac = horizontal
      ? (e.clientX - r.left) / r.width
      : (e.clientY - r.top) / r.height;
    node.ratio = Math.min(0.9, Math.max(0.1, frac));
    aEl.style.flexGrow = String(node.ratio * 2);
    bEl.style.flexGrow = String((1 - node.ratio) * 2);
  };
  const up = () => {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    saveLocal();
  };
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
}

function buildPane(pane) {
  const el = document.createElement("div");
  el.className = "pane";

  const head = document.createElement("div");
  head.className = "pane-head";

  // kind
  const kindSel = document.createElement("select");
  for (const k of Object.keys(KIND_UI)) {
    const o = document.createElement("option");
    o.value = k; o.textContent = KIND_UI[k].label;
    if (k === pane.kind) o.selected = true;
    kindSel.appendChild(o);
  }
  kindSel.onchange = () => {
    pane.kind = kindSel.value;
    const ui = KIND_UI[pane.kind];
    pane.opts = {};
    for (const c of ui.controls) if (c.default !== undefined) pane.opts[c.key] = c.default;
    if (ui.channels === 2 && pane.channels.length !== 2) {
      pane.channels = SESSION.channels.slice(0, 2).map((c) => c.name);
    }
    rerender();
  };
  head.appendChild(kindSel);

  head.appendChild(buildChannelPicker(pane));

  // window
  const win = document.createElement("input");
  win.type = "number"; win.min = "0.1"; win.step = "0.5"; win.style.width = "58px";
  win.value = String(pane.window_s);
  win.title = "window (s)";
  win.onchange = () => {
    const v = Math.max(0.1, Math.min(SESSION.buffer_seconds, Number(win.value) || 1));
    pane.window_s = v; win.value = String(v);
    rerenderPane(pane);
  };
  head.appendChild(labelled("win", win));

  // units
  const units = document.createElement("select");
  for (const u of ["pT", "V"]) {
    const o = document.createElement("option");
    o.value = u; o.textContent = u;
    if (u === pane.units) o.selected = true;
    units.appendChild(o);
  }
  units.onchange = () => { pane.units = units.value; rerenderPane(pane); };
  head.appendChild(units);

  // kind-specific controls
  for (const ctl of KIND_UI[pane.kind].controls) {
    if (ctl.showWhen && !ctl.showWhen(pane.opts)) continue;
    head.appendChild(buildControl(pane, ctl));
  }

  const spacer = document.createElement("span");
  spacer.className = "ctl-spacer";
  head.appendChild(spacer);

  const readout = document.createElement("span");
  readout.className = "readout";
  head.appendChild(readout);

  head.appendChild(iconBtn("▥", "split left/right", () => splitPane(pane.id, "row")));
  head.appendChild(iconBtn("▤", "split top/bottom", () => splitPane(pane.id, "col")));
  head.appendChild(iconBtn("✕", "close pane", () => closePane(pane.id)));

  const plot = document.createElement("div");
  plot.className = "plot";

  el.append(head, plot);
  PENDING_RENDERERS.push({ pane, plotEl: plot, readoutEl: readout });
  return el;
}

function rerenderPane(pane) {
  // Scales and axis labels are baked into the renderer at construction, so any
  // config change rebuilds it. This is user-initiated, never per-frame.
  rerender();
}

function labelled(text, node) {
  const w = document.createElement("label");
  w.style.display = "flex"; w.style.alignItems = "center"; w.style.gap = "4px";
  w.append(text, node);
  return w;
}

function iconBtn(glyph, title, fn) {
  const b = document.createElement("button");
  b.textContent = glyph; b.title = title; b.onclick = fn;
  return b;
}

function buildControl(pane, ctl) {
  if (ctl.type === "check") {
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = Boolean(pane.opts[ctl.key]);
    cb.onchange = () => { pane.opts[ctl.key] = cb.checked; rerenderPane(pane); };
    return labelled(ctl.label, cb);
  }
  if (ctl.type === "select") {
    const s = document.createElement("select");
    for (const [v, t] of ctl.options) {
      const o = document.createElement("option");
      o.value = v; o.textContent = t;
      if (pane.opts[ctl.key] === v) o.selected = true;
      s.appendChild(o);
    }
    s.onchange = () => { pane.opts[ctl.key] = s.value; rerenderPane(pane); };
    return ctl.label ? labelled(ctl.label, s) : s;
  }
  if (ctl.type === "number") {
    const i = document.createElement("input");
    i.type = "number"; i.style.width = "66px";
    i.value = pane.opts[ctl.key] ?? "";
    i.onchange = () => { pane.opts[ctl.key] = Number(i.value); rerenderPane(pane); };
    return labelled(ctl.label, i);
  }
  throw new Error(`unknown control type ${ctl.type}`);
}

function buildChannelPicker(pane) {
  const limit = KIND_UI[pane.kind].channels; // "many" or 2
  const wrap = document.createElement("span");
  wrap.className = "chan-picker";

  const btn = document.createElement("button");
  const label = () => {
    if (limit === 2) return `${pane.channels[0] ?? "—"} vs ${pane.channels[1] ?? "—"}`;
    if (pane.channels.length === 0) return "no channels";
    if (pane.channels.length === SESSION.channels.length) return "all channels";
    return pane.channels.join(", ");
  };
  btn.textContent = label();
  btn.title = "choose channels";

  const menu = document.createElement("div");
  menu.className = "chan-menu";

  // Keep the button label and every checkbox in step with pane.channels after
  // any change, whichever control drove it.
  const syncMenu = () => {
    btn.textContent = label();
    for (const other of menu.querySelectorAll("input[type=checkbox]")) {
      other.checked = pane.channels.includes(other.dataset.name);
    }
  };

  if (limit === 2) {
    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = "pick 2 — x, then y";
    menu.appendChild(hint);
  } else {
    // all / none, so going from six traces to one is not five unticks.
    const quick = document.createElement("div");
    quick.className = "chan-quick";
    const mk = (text, names) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "mini"; b.textContent = text;
      b.onclick = (e) => {
        e.stopPropagation();
        pane.channels = names();
        syncMenu();
        rerenderPane(pane);
      };
      return b;
    };
    quick.append(
      mk("all", () => SESSION.channels.map((c) => c.name)),
      mk("none", () => []),
    );
    menu.appendChild(quick);
  }

  for (const ch of SESSION.channels) {
    const row = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = pane.channels.includes(ch.name);
    cb.onchange = () => {
      if (cb.checked) {
        pane.channels.push(ch.name);
        // A phase plot takes exactly two: adding a third drops the oldest, so
        // the control never lands in an invalid state the server has to reject.
        if (limit === 2 && pane.channels.length > 2) pane.channels.shift();
      } else {
        pane.channels = pane.channels.filter((n) => n !== ch.name);
      }
      syncMenu();
      rerenderPane(pane);
    };
    cb.dataset.name = ch.name;
    // Swatch in the same colour the trace uses, so the name maps to a line.
    const sw = document.createElement("span");
    sw.className = "leg-sw";
    sw.style.background = colorForChannel(SESSION, ch.name);
    row.append(cb, sw, ch.name);
    menu.appendChild(row);
  }

  btn.onclick = (e) => {
    e.stopPropagation();
    document.querySelectorAll(".chan-menu.open").forEach((m) => {
      if (m !== menu) m.classList.remove("open");
    });
    menu.classList.toggle("open");
  };
  menu.onclick = (e) => e.stopPropagation();

  wrap.append(btn, menu);
  return wrap;
}

document.addEventListener("click", () => {
  document.querySelectorAll(".chan-menu.open").forEach((m) => m.classList.remove("open"));
});

/* ------------------------------------------------------------------ transport */

function decodeFrame(buffer) {
  const dv = new DataView(buffer);
  const headerLen = dv.getUint32(0, true);
  const header = JSON.parse(
    new TextDecoder().decode(new Uint8Array(buffer, 4, headerLen))
  );
  // The payload is not guaranteed to start on a 4-byte boundary, so slice
  // (which copies) rather than viewing in place, which would throw.
  let off = 4 + headerLen;
  for (const pane of header.panes) {
    pane.data = {};
    for (const a of pane.arrays) {
      pane.data[a.name] = new Float32Array(buffer.slice(off, off + a.n * 4));
      off += a.n * 4;
    }
  }
  return header;
}

function pushSpecs() {
  if (!SOCKET || SOCKET.readyState !== WebSocket.OPEN) return;
  SOCKET.send(JSON.stringify({
    panes: allPanes().map((p) => ({
      id: p.id, kind: p.kind, channels: p.channels,
      window_s: p.window_s, units: p.units, opts: p.opts,
    })),
    stats_units: $("#stats-units").value,
  }));
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  SOCKET = new WebSocket(`${proto}://${location.host}/ws`);
  SOCKET.binaryType = "arraybuffer";

  SOCKET.onopen = () => {
    setConn("live", "up");
    pushSpecs();
  };
  SOCKET.onclose = () => {
    setConn("disconnected — retrying", "down");
    setTimeout(connect, 1000);
  };
  SOCKET.onmessage = (ev) => {
    try {
      onFrame(decodeFrame(ev.data));
    } finally {
      // Acknowledge only after rendering. This is what paces the server: it
      // holds the next frame until we are ready for it, so the socket never
      // congests and pane-config messages always apply on the next frame.
      // Sent even if rendering threw, so one bad frame cannot wedge the stream.
      if (SOCKET && SOCKET.readyState === WebSocket.OPEN) {
        SOCKET.send(JSON.stringify({ ack: 1 }));
      }
    }
  };
}

function setConn(text, cls) {
  const el = $("#conn");
  el.textContent = text;
  el.className = cls;
}

function onFrame(frame) {
  for (const pane of frame.panes) {
    const r = RENDERER_BY_ID.get(pane.id);
    if (!r) continue; // renderer not constructed yet, or pane just closed
    if (pane.meta.error) {
      showPaneError(r, pane.meta.error);
      continue;
    }
    clearPaneError(r);
    r.update(pane);
    if (r._readoutEl) r._readoutEl.textContent = r.readout(pane);
  }
  renderStats(frame.stats);
  $("#warn-bar").textContent = frame.daq_error
    ? `Acquisition stopped: ${frame.daq_error}`
    : "";
}

function showPaneError(r, msg) {
  if (!r._errEl) {
    r._errEl = document.createElement("div");
    r._errEl.className = "err";
    r._plotEl.appendChild(r._errEl);
  }
  r._errEl.textContent = msg;
}

function clearPaneError(r) {
  if (r._errEl) { r._errEl.remove(); r._errEl = null; }
}

/* ------------------------------------------------------------------ stats */

function renderStats(stats) {
  const table = $("#stats");
  if (!stats || stats.length === 0) { table.innerHTML = ""; return; }
  const u = stats[0].units;

  // A railed channel reports a plausible-looking mean while being pure fiction,
  // and the row that says so scrolls at the bottom of a table. Raise it to a
  // banner that cannot be missed — this is the field-too-strong failure the
  // whole rig exists to catch.
  const railed = stats.filter((s) => s.saturated).map((s) => s.name);
  const banner = $("#rail-banner");
  if (railed.length) {
    banner.textContent =
      `⚠ RAILED: ${railed.join(", ")} — these readings are not real field values`;
    banner.classList.add("show");
  } else {
    banner.textContent = "";
    banner.classList.remove("show");
  }

  if (table.dataset.units !== u || table.rows.length !== stats.length + 1) {
    table.innerHTML = "";
    const head = table.insertRow();
    for (const h of ["channel", `mean (${u})`, `std (${u})`, `min (${u})`, `max (${u})`, ""]) {
      const th = document.createElement("th");
      th.textContent = h;
      head.appendChild(th);
    }
    for (const s of stats) {
      const row = table.insertRow();
      row.id = `stat-${s.name}`;
      for (let i = 0; i < 6; i++) row.insertCell();
      row.cells[0].textContent = s.name;
    }
    table.dataset.units = u;
  }

  for (const s of stats) {
    const row = document.getElementById(`stat-${s.name}`);
    if (!row) continue;
    row.cells[1].textContent = num(s.mean);
    row.cells[2].textContent = num(s.std);
    row.cells[3].textContent = num(s.min);
    row.cells[4].textContent = num(s.max);
    // Saturation is decided in volts against the DAQ input range. A pinned
    // channel still reports a plausible-looking mean, so this flag is the only
    // thing standing between you and a recorded number that is pure fiction.
    row.cells[5].textContent = s.saturated
      ? `⚠ RAILED ${(s.clipped_fraction * 100).toFixed(0)}%` : "";
    row.cells[5].className = "flag";
    row.className = s.saturated ? "sat" : "";
  }
}

function num(v) {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e5 || (a > 0 && a < 1e-3)) return v.toExponential(2);
  return v.toFixed(a >= 100 ? 1 : 3);
}

/* ------------------------------------------------------------------ persistence */

const LS_KEY = "fieldzero.layout.v1";

function saveLocal() {
  try { localStorage.setItem(LS_KEY, JSON.stringify(LAYOUT)); } catch {}
}

function loadLocal() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const tree = JSON.parse(raw);
    // Rebase the id counter so freshly created panes cannot collide with
    // restored ones.
    for (const p of allPanes(tree)) {
      const n = Number(String(p.id).slice(1));
      if (Number.isFinite(n)) uid = Math.max(uid, n);
    }
    return tree;
  } catch { return null; }
}

function wireTopbar() {
  $("#stats-units").onchange = pushSpecs;

  $("#reset-layout").onclick = () => {
    LAYOUT = newPane({ channels: SESSION.channels.map((c) => c.name) });
    rerender();
  };

  $("#save-layout").onclick = () => {
    const blob = new Blob([JSON.stringify(LAYOUT, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "fieldzero-layout.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  $("#load-layout").onclick = () => $("#file-input").click();
  $("#file-input").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      LAYOUT = JSON.parse(await file.text());
      for (const p of allPanes()) {
        const n = Number(String(p.id).slice(1));
        if (Number.isFinite(n)) uid = Math.max(uid, n);
      }
      rerender();
    } catch (err) {
      alert(`Could not load layout: ${err.message}`);
    }
    e.target.value = "";
  };
}

/* ------------------------------------------------------------------ boot */

async function boot() {
  SESSION = await (await fetch("/api/session")).json();

  const rail = SESSION.voltage_range;
  $("#session-info").textContent =
    `${SESSION.source} · ${SESSION.channels.length} ch · ${SESSION.sample_rate} Hz · ` +
    `±${Math.max(Math.abs(rail[0]), Math.abs(rail[1]))} V ${SESSION.terminal_config} · ` +
    `${SESSION.sensitivity_v_per_nT} V/nT (unverified)`;

  LAYOUT = loadLocal() || newPane({ channels: SESSION.channels.map((c) => c.name) });
  wireTopbar();
  rerender();
  connect();
}

boot();
