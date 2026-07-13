# FieldZero — Magnetic Field Cancellation for OPM MEG

System to reduce the residual magnetic field inside the QUBIC lab's mu-metal shielded enclosure, allowing the QuSpin QZFM sensors to zero and lock reliably.

See `docs/context.md` for full project context.

## Status

In development — lab access pending.

## Repository layout

```
docs/               Project documentation (grows as work progresses)
data/
  raw/              Unmodified instrument output (write-once)
  processed/        Script outputs only — never hand-edit
scripts/
  characterisation/ Field measurement and analysis
  coil_cal/         Coil sensitivity calibration
  nulling/          Nulling procedure support
  figures/          All figure generation
src/fieldzero/      Python package
tests/
```

## Setup

Python 3.11+. A venv is created per machine — **do not copy `.venv` between
machines**, it hardcodes absolute paths and platform-specific wheels. Recreate it
instead; it takes about a minute.

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -e ".[daq,dev]"
```

`[daq]` pulls in `nidaqmx`. Drop it on a machine with no card — `--mock` needs
nothing else. Drop `dev` if you are not running the tests. The NI-DAQmx driver
itself is a separate install from National Instruments and is not a pip package.

### Installing on a machine with no internet

Instrument PCs are often locked down. Build a wheelhouse **before** you go, on a
machine that does have network:

```powershell
.venv\Scripts\python.exe -m pip download -d wheels numpy scipy fastapi "uvicorn[standard]" nidaqmx
```

Copy `wheels/` across with the repo, then on the lab machine:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install --no-index --find-links wheels -e ".[daq]"
```

The front end needs no network either — uPlot is vendored into
`src/fieldzero/viewer/static/vendor/` rather than loaded from a CDN.

## Live viewer

```bash
python -m fieldzero.viewer            # against the NI-DAQ
python -m fieldzero.viewer --mock     # no hardware required
```

Opens a browser at `http://127.0.0.1:8000`. Split any pane left/right or
top/bottom and choose what goes in it: time domain, frequency domain (amplitude
or ASD), or phase (any channel against any other, with Pearson r and fitted
slope). The stats table below the panes gives per-channel mean and standard
deviation, and flags any channel sitting at the input rail.

Layouts persist across reloads and can be saved to / loaded from JSON.

Run `scripts/characterisation/verify_acquisition.py [--mock]` on arrival at the
lab to confirm the DAQ is reading every channel before starting a measurement.

The viewer binds to loopback, so a Windows firewall prompt on first run can be
declined. Use `--host 0.0.0.0` to watch from a laptop while the DAQ machine sits
in the shielded room — that one does need the firewall exception.

## Fallback scope

A plain matplotlib window. No server, no browser, no socket — a timer reads the
ring buffer in-process, so there is nothing between acquisition and the screen
that can stall, congest or time out. Use it if the browser viewer feels sluggish
on a given machine, or when you just want a scope up in one command.

It runs the same reducers as the browser viewer, so the DSP is identical: the
same windowing, the same ASD scaling, the same volts-based rail check, the same
correlation maths. Only the drawing differs.

### Running it

```bash
python -m fieldzero.scope                # against the NI-DAQ
python -m fieldzero.scope --mock         # no hardware required
```

With no `--pane`, you get one time-domain plot of all six channels. Close the
window to stop it.

### Choosing what to plot

`--pane` takes `KIND` or `KIND:CH,CH,...` and is **repeatable** — each one adds a
plot, stacked top to bottom in the order you give them.

| kind | channels | shows |
|------|----------|-------|
| `time` | any number (default: all six) | rolling time trace, newest sample at t=0 |
| `spectrum` | any number (default: all six) | amplitude spectral density, log axis |
| `phase` | **exactly two** | first against second, with a least-squares fit |

Channel names are `S1-X`, `S1-Y`, `S1-Z`, `S2-X`, `S2-Y`, `S2-Z` — the same names
the stats table uses. Get one wrong and it tells you the valid ones and exits.

```bash
# one time plot of two channels, and their spectrum underneath
python -m fieldzero.scope --pane time:S1-X,S2-X --pane spectrum:S1-X,S2-X

# is sensor 2 seeing the same field as sensor 1?
python -m fieldzero.scope --pane phase:S1-X,S2-X

# what is the residual on the Z axis, in raw volts, over 10 seconds?
python -m fieldzero.scope --pane time:S1-Z,S2-Z --units V --window 10
```

### The other flags

| flag | default | what it does |
|------|---------|--------------|
| `--mock` | off | simulated source; no DAQ needed |
| `--window N` | `5` | seconds of history each pane shows |
| `--units pT\|V` | `pT` | display units. **Volts are ground truth** — the V/nT figure is unverified |
| `--fps N` | `10` | redraw rate. Drop it to `5` on a slow machine |
| `--sample-rate N` | `1000` | samples/second per channel. Startup only |

### Reading the window

The red or grey strip along the top is the readout, updated twice a second:

- Normally it lists every channel's mean ± standard deviation in the chosen units.
- If **any channel is at the input rail** it turns red and says so, and it says
  nothing else. That warning takes priority because a clipped channel still
  reports a mean that looks like a perfectly reasonable field value. When you see
  it, the true field on that channel is larger than ±5 V can represent, and every
  number from it is fiction.

A phase pane also prints its Pearson *r* and fitted slope into that strip: *r*
near 1 means both channels are seeing the same field, and the slope is the gain
ratio between them.

### What you give up

Panes are fixed at launch. There is no clicking, no splitting, no changing
channels while it runs — to change the layout, close it and relaunch with
different `--pane` flags. That is the trade for having nothing that can go wrong.

### If you edit `scope.py`

Rendering uses blitting, and has to. A full matplotlib redraw of three panes
costs ~120 ms (~8 fps), and the cost is the redraw itself — thinning the data does
not help. Blitting the traces over a cached background costs ~20 ms instead. Two
consequences are load-bearing:

- **A pane's axes contain traces and nothing else.** Rasterising text costs more
  per frame than every trace in every pane put together (~27 ms vs ~22 ms), which
  is why all text lives in the status strip — it has its own bbox, so it can be
  redrawn at 2 Hz independently — and why legends and titles sit *above* the axes,
  outside the blitted region, where they survive in the cached background for free.
- **Axis limits use hysteresis.** They only move when the data leaves them, because
  a rescale forces a full redraw. Rescaling every frame would throw away
  everything blitting buys. `test_scope.py` asserts steady state needs none.

## Acquisition notes

Sample rate is a **startup** parameter (`--sample-rate`, default 1000 Hz), not a
runtime one: changing it means rebuilding the DAQ task, and doing that mid-run is
what made the previous project's axis switching unreliable. The task is opened
once over all six channels and never reconfigured; selecting an axis is purely a
display concern.

Acquisition yields **volts**. The V/nT conversion is applied at display time
(see below) — so saturation is detected against the known input range rather
than an unverified sensitivity figure.

## Hardware

| Item | Status |
|------|--------|
| QuSpin QZFM sensors × 2 | In lab — gen TBD |
| Cancellation coils | Not yet installed |
| Current source | TBD |
| NI-DAQ (Dev1, ai0–ai5) | In lab — model TBD, confirm in NI MAX |

Three acquisition settings in `src/fieldzero/config.py` need confirming against
the actual card. MEG_DSP never set them, so it silently ran on the `nidaqmx`
defaults:

| Setting | Value | Why it matters |
|---------|-------|----------------|
| `voltage_range` | ±5 V | Where a channel clips. This is the `nidaqmx` default, never a decision. At the inherited 2.7 V/nT that is a clip at ~1.85 nT — and the residual field is believed to be nT-scale, so channels may already be railing. |
| `terminal_config` | RSE | RSE vs differential materially changes the noise floor. |
| `sensitivity_v_per_nT` | 2.7 | **Unverified** — inherited from MEG_DSP, and the QZFM generation is still unconfirmed. Volts are ground truth until this is checked against the sensor label. |
