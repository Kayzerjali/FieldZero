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

```bash
pip install numpy scipy matplotlib pandas nidaqmx
pip install -e .
```

`environment.yml` records the exact package versions used during development. To reproduce that environment exactly:

```bash
conda env create -f environment.yml
conda activate fieldzero
pip install -e .
```

NI-DAQmx driver must be installed separately from National Instruments. Use `MockSignal` in `src/fieldzero/datasource.py` for offline development without hardware.

## Hardware

| Item | Status |
|------|--------|
| QuSpin QZFM sensors × 2 | In lab — gen TBD |
| Cancellation coils | Not yet installed |
| Current source | TBD |
| NI-DAQ (Dev1, ai0–ai5) | In lab |
