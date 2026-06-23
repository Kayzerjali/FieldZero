# FieldZero — Project Context for AI Sessions

## What this project is

Active DC magnetic field cancellation for two QuSpin QZFM-class zero-field magnetometers inside a mu-metal shielded room at the QUBIC MEG lab. The goal is narrow: bring the sensors out of saturation so they can operate. Not real-time noise cancellation. Not motion compensation.

**Engineer**: Kayzer Ali (solo, with supervisor)  
**Timeline**: ~2 weeks of working time (Level-1 constraint)  
**Primary language**: Python  

## Architecture

Two loops in series:
1. **External coarse** (this system): trim coils driven by a current source, set manually via a nulling procedure. Coarse acquisition — drives field into the QuSpin's capture range.
2. **QuSpin internal fine**: the sensor's own internal nulling loop. Handles residual trim within its capture range.

The handoff between loops must be clean: external system gets field into capture range with margin, QuSpin does the rest.

## What is settled — do not re-litigate

- Success criterion: DC/quasi-static trim to bring sensors out of saturation. Not closed-loop dynamic cancellation.
- Baseline approach: manual nulling (coil currents set by operator following a procedure). This fully satisfies the stated requirement.
- Automatic closed-loop and motion-compensation are documented future work, not current scope.
- Characterisation precedes requirements; requirements precede design. No invented numbers.

## Known hardware state

| Item | Status |
|------|--------|
| QuSpin QZFM sensors × 2 | In lab — gen **[TBD]** |
| Cancellation coils | Not yet installed — engineer's task |
| NI-DAQ card | In lab — Dev1, ai0–ai5 |
| Current source | DAC available; custom ultra-low-noise linear source under consideration |

## Saturation observable

In the QuSpin software, a saturated sensor shows as a **flat line at a ceiling value** on the field output. The analog voltage output (read via NI-DAQ) rails at a constant value. Normal operation resumes when the output leaves the rail and tracks a signal.

## Acquisition interface

From prior project `MEG_DSP` (github.com/Kayzerjali/MEG_DSP, DataSource.py):
- `NIDAQ` class via `nidaqmx` reads ai0–ai5 as 2 sensors × 3 axes
- Conversion: `(voltage / 2.7) * 1000` → pT  (2.7 V/nT QZFM sensitivity — **verify against datasheet for actual gen**)
- `MockSignal` class available for offline development without hardware

## Key open questions (as of project start)

1. QuSpin gen — verify from hardware label
2. Residual field magnitude and vector decomposition — **not yet measured**
3. Cancellation coil geometry, authority, and sensitivity — to be designed
4. Current source architecture — DAC vs custom linear (see ADR-003 when written)
5. Field spatial uniformity across the two sensor locations

## Engineering standards

- Every requirement traces to a measured number or datasheet figure
- Every design choice traces to a requirement
- Every figure regenerated from a checked-in script
- Raw data: never hand-edited
- Docs: Markdown in repo, TBD markers explicit — no invented values
- Reproducibility test: delete all figures and processed files, re-run scripts, get identical output
