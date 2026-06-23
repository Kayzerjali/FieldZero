# Verification Plan

**Status**: Framework defined. Test procedures require hardware in place.

This document defines the acceptance tests that demonstrate the system meets its requirements. Every requirement in `00_requirements.md` maps to at least one test here. No requirement is considered verified until its test is executed and its pass/fail recorded.

---

## Traceability matrix

| Requirement | Verification test | Method | Status |
|-------------|-----------------|--------|--------|
| REQ-SYS-001 (field in capture range) | VT-001 | Analysis + measurement | TBD |
| REQ-SYS-002 (DC/quasi-static only) | Architectural — no test needed | Scope definition | Satisfied by design |
| REQ-SYS-003 (stability over session) | VT-002 | Measurement | TBD |
| REQ-COIL-001 (coil authority) | VT-003 | Measurement | TBD |
| REQ-COIL-002 (field uniformity) | VT-004 | Measurement | TBD |
| REQ-COIL-003 (coil documentation) | VT-005 | Document review | TBD |
| REQ-DRIVE-001 (current range) | VT-006 | Measurement | TBD |
| REQ-DRIVE-002 (current resolution) | VT-007 | Measurement | TBD |
| REQ-DRIVE-003 (noise floor) | VT-008 | Measurement | TBD |
| REQ-DRIVE-004 (no switching artefacts) | VT-009 | Spectral measurement | TBD |
| REQ-VER-001 (sensors exit saturation) | VT-010 | Measurement | TBD |
| REQ-VER-002 (figures regeneratable) | VT-011 | Automated script test | TBD |
| REQ-VER-003 (raw data unmodified) | VT-012 | Git history check | TBD |

---

## Test procedures

### VT-001: System-level — sensors exit saturation

**Requirement**: REQ-SYS-001, REQ-VER-001

**Pre-conditions**: coils installed, current source operational, QuSpin sensors powered

**Procedure**:
1. Start data acquisition: `python scripts/characterisation/verify_acquisition.py`
2. With zero coil current, record 30 s baseline — confirm both sensors show saturation (flat line at ceiling value established in M-01).
3. Follow nulling procedure in `04_operating_procedure.md`.
4. Record 60 s after nulling is complete.
5. Confirm both sensor outputs show dynamic signal (not flat) and field magnitude < QuSpin capture range.

**Pass criterion**: both sensor outputs exit the saturation rail and remain dynamic for the full 60 s recording.

**Record**: coil current setpoints (mA per axis), timestamp, operator, raw data file path.

---

### VT-002: Temporal stability

**Requirement**: REQ-SYS-003

**Procedure**:
1. Complete VT-001 (sensors in linear range).
2. Record continuously for **[TBD — target session length, e.g. 4 h]** without adjusting setpoints.
3. Run `scripts/characterisation/analyse_drift.py` on recorded data.
4. Compute peak-to-peak field variation over the session.

**Pass criterion**: peak-to-peak variation < QuSpin capture range / 2 (i.e., system stays in linear range for the full session without re-trimming).

---

### VT-003: Coil authority

**Requirement**: REQ-COIL-001

**Procedure**:
1. From a null condition, apply +I_max to each axis coil in turn.
2. Record resulting field change at the sensor location.
3. Confirm: maximum achievable field change per axis ≥ REQ-COIL-001 value.

**Pass criterion**: coil authority (measured) ≥ B_res,max × margin.

---

### VT-004: Field uniformity

**Requirement**: REQ-COIL-002

**Procedure**:
1. Apply a known current to each axis in turn.
2. Record simultaneous field at both sensor locations (all 6 NI-DAQ channels).
3. Compute fractional field difference between sensors: `ΔB/B`.

**Pass criterion**: `ΔB/B < REQ-COIL-002` value.

---

### VT-008: Current source noise floor

**Requirement**: REQ-DRIVE-003

**Procedure**:
1. Connect current source output to a precision sense resistor (value: **[TBD]** Ω).
2. Measure voltage across sense resistor with NI-DAQ or spectrum analyser.
3. Compute current noise PSD.
4. Multiply by coil sensitivity to get field noise at sensor.

**Pass criterion**: field noise < REQ-DRIVE-003 value.

---

### VT-009: Switching artefact check

**Requirement**: REQ-DRIVE-004

**Procedure**:
1. With current source running (output connected to coil or resistive load):
2. Record 300 s of NI-DAQ data at full sample rate.
3. Compute PSD — run `scripts/characterisation/analyse_spectrum.py`.
4. Compare spectrum with current source **on** vs. **off**.
5. Check for any new peaks in the MEG band (**[TBD]** Hz range).

**Pass criterion**: no spectral peaks attributable to current source exceed noise floor + 3 dB in the MEG band.

---

### VT-011: Figure regeneration

**Requirement**: REQ-VER-002

**Procedure** (automated, run as part of CI or manual release check):
```bash
find docs -name "*.png" -o -name "*.pdf" -o -name "*.svg" | xargs rm -f
python scripts/figures/generate_all.py
git diff --stat  # should show only figure files added back, no content diffs
```

**Pass criterion**: all figures regenerate without error; no other files modified.

---

### VT-012: Raw data integrity

**Requirement**: REQ-VER-003

**Procedure**:
```bash
git log --follow --diff-filter=M data/raw/  # should return no commits
```

**Pass criterion**: no modifications to any file in `data/raw/` after initial commit.

---

## Acceptance sign-off

| Requirement | Test | Result | Date | Engineer |
|-------------|------|--------|------|----------|
| REQ-SYS-001 | VT-001 | TBD | | |
| REQ-SYS-003 | VT-002 | TBD | | |
| ... | | | | |
