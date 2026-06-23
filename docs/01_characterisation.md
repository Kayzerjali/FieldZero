# Field Characterisation Campaign

**Status**: Planned — lab access pending.

This document defines the measurement campaign that produces the numbers filling in all TBD entries in `00_requirements.md`. No design work downstream of this document is valid until the relevant measurements are complete and recorded here.

---

## Objectives

1. Measure residual DC field vector at both sensor locations (X, Y, Z)
2. Characterise temporal stability (drift over a lab session)
3. Identify AC content (50 Hz, harmonics, other interference)
4. Establish field difference between the two sensor locations (sets uniformity requirement)
5. Confirm QuSpin saturation observable and recovery behaviour

---

## Pre-conditions

- [ ] QuSpin gen confirmed from hardware label → enter in `00_requirements.md`
- [ ] QuSpin datasheet values extracted (capture range, sensitivity, output full-scale)
- [ ] NI-DAQ acquisition confirmed working (run `scripts/characterisation/verify_acquisition.py`)
- [ ] Both sensors powered and warmed up (warm-up time: **[TBD — from datasheet]**)

---

## Measurement protocol

### M-01: Saturation confirmation

**Purpose**: establish what a saturated sensor looks like quantitatively in the NI-DAQ data stream.

**Procedure**:
1. Power both QuSpin sensors inside the shielded enclosure with no external cancellation.
2. Record 60 s of data from all 6 channels at **[TBD]** Hz sample rate.
3. Save raw file as `data/raw/YYYY-MM-DD_M01_saturation_baseline.csv`.
4. Plot time series — confirm flat line at ceiling. Record ceiling value in V and converted pT.

**Expected result**: constant output (within noise floor of NI-DAQ) at the rail value.

**Pass/fail**: if output is not flat, the sensors may not be saturated — investigate before proceeding.

---

### M-02: DC residual field estimation (saturated state)

**Purpose**: bound the residual field to the degree possible while sensors are saturated.

**Note**: while sensors are saturated, their output does not give the residual field directly. Field estimation in saturation must use an independent reference or inference from the QuSpin's nulling coil current if accessible.

> **[TBD]**: Determine whether QuSpin provides any accessible output (digital readback, LED status, internal coil current monitor) that can be used in saturation. Consult QuSpin documentation and supervisor.
>
> Alternative: use a calibrated handheld fluxgate or Hall probe at the sensor locations to measure residual field before the QuSpin internal loop acts.

**Save**: raw data to `data/raw/YYYY-MM-DD_M02_dc_residual_estimate.csv`

---

### M-03: Temporal drift

**Purpose**: characterise field stability over a lab session. Sets REQ-SYS-003.

**Procedure**:
1. Record continuously for **[TBD — target: 4 h]** at **[TBD]** Hz.
2. Save raw file as `data/raw/YYYY-MM-DD_M03_drift_Nh.csv`.
3. Run `scripts/characterisation/analyse_drift.py` → produces trend plot and drift rate figure.

**Metric**: peak-to-peak variation in equivalent field over the session.

---

### M-04: AC interference

**Purpose**: identify spectral content from mains, building systems, or other interference.

**Procedure**:
1. Record 300 s at **[TBD — high enough for 0.1 Hz resolution, minimum 1 kHz]** Hz.
2. Compute PSD using Welch method (script: `scripts/characterisation/analyse_spectrum.py`).
3. Flag all peaks above noise floor, record frequencies and amplitudes.
4. Save raw file: `data/raw/YYYY-MM-DD_M04_ac_spectrum.csv`.

**Metric**: field amplitude at 50 Hz and harmonics, and any other identified peaks.

**Relevance**: if AC content is significant, a pure DC trim is insufficient. This result gates the decision on whether any AC rejection capability is needed (currently out of scope — but must be confirmed, not assumed).

---

### M-05: Spatial uniformity (two-sensor comparison)

**Purpose**: confirm that both sensors experience the same field (or quantify the difference). Sets REQ-COIL-002.

**Procedure**:
1. Record simultaneous data from both sensors on all three axes.
2. Compute difference: `ΔB = |B_sensor1 - B_sensor2|` per axis.
3. Record `ΔB` — this is the field gradient across the sensor separation.

**Metric**: if `ΔB > [TBD]% of QuSpin capture range`, uniform coils cannot satisfy both sensors simultaneously. Decision required.

---

### M-06: Nulling recovery — QuSpin exit from saturation

**Purpose**: confirm that the QuSpin exits saturation and produces valid output when external field is reduced to within its capture range. This is the acceptance test condition.

**Procedure**:
> **[TBD]**: Requires cancellation coils and current source to be installed. This measurement cannot proceed until the coil system is in place. Document here as a planned test; execute during commissioning.

1. Apply coil current to null the residual field (initial values: rough estimate from M-02).
2. Record sensor output; observe transition from railing to dynamic signal.
3. Record the coil current setpoints at which both sensors exit saturation.
4. Record final residual field (sensor output after QuSpin internal loop settles).

---

## Data management

- All raw files: `data/raw/YYYY-MM-DD_<measurement-ID>_<description>.csv`
- Naming is date-first for chronological sort. Never rename or edit raw files after recording.
- Processed outputs (plots, statistics): `data/processed/` — generated by scripts, not committed to git.
- Analysis scripts: `scripts/characterisation/` — one script per measurement, plus shared utilities.

---

## Results summary

> Fill in after each measurement is complete.

| Measurement | Date | Key result | Notes |
|-------------|------|------------|-------|
| M-01 Saturation confirmation | TBD | — | |
| M-02 DC residual field | TBD | — | |
| M-03 Temporal drift | TBD | — | |
| M-04 AC interference | TBD | — | |
| M-05 Spatial uniformity | TBD | — | |
| M-06 Nulling recovery | TBD | — | After coils installed |
