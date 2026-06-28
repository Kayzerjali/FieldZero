# FieldZero — AI Session Context

## What this project is

Active magnetic field cancellation for two QuSpin QZFM-class zero-field magnetometers inside a mu-metal shielded enclosure at the QUBIC MEG lab. See `docs/context.md` for full project context.

**Engineer**: Kayzer Ali, solo with supervisor  
**Timeline**: ~2 weeks of working time from semester 2 start  
**Language**: Python  

## How to work with the engineer

- Thinking happens in conversation. Docs are a residue of settled decisions, not a planning tool. Don't scaffold documentation ahead of the work.
- The engineer reasons in problem → solution frames. Follow that structure.
- Push back on hand-waving. If a design choice isn't traceable to a measurement or a datasheet number, call it out.
- When something is settled in conversation, help write the minimum doc entry that records it. No more.
- Docs grow as work progresses. Do not front-load structure.

## What is settled

- This is a coarse acquisition problem. The QuSpin internal loop handles fine trim once it can acquire. The external system just needs to get the field into its capture range.
- Success criterion: both sensors zero and lock in under ~2 minutes.
- Deliverable: simple enough for any lab member to operate from a procedure.
- Closed-loop dynamic cancellation is out of scope.

## Hardware

| Item | Status |
|------|--------|
| QuSpin QZFM sensors × 2 | In lab — gen TBD (check label) |
| Cancellation coils | Unknown — check if installed |
| Current source | TBD |
| NI-DAQ (Dev1, ai0–ai5) | In lab and working |

## Acquisition interface

From prior project MEG_DSP (github.com/Kayzerjali/MEG_DSP, DataSource.py) — adapted into `src/fieldzero/datasource.py`:
- `NIDAQ` class via `nidaqmx`, reads ai0–ai5 as 2 sensors × 3 axes
- Conversion: `(voltage / 2.7) * 1000` → pT (verify 2.7 V/nT against datasheet for confirmed gen)
- `MockSignal` available for offline development

## Key unknowns to resolve in the lab

1. QuSpin gen — read from hardware label
2. Residual field magnitude and which axes are problematic — measure
3. Whether cancellation coils exist already
4. QuSpin capture range — from datasheet once gen is confirmed
