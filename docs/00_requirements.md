# Requirements

All requirements must trace to a source: a measured value, a datasheet figure, or a physics derivation. Any requirement marked **[TBD]** is a placeholder pending characterisation or datasheet verification. No requirement marked TBD may be used as the basis for a design decision until it is filled in.

---

## System-level requirements

| ID | Requirement | Source | Status |
|----|-------------|--------|--------|
| REQ-SYS-001 | The external cancellation system shall reduce the residual DC magnetic field at each QuSpin sensor to within the sensor's internal nulling capture range | QuSpin capture range: **[TBD — from datasheet for confirmed gen]** | TBD |
| REQ-SYS-002 | The system shall operate in DC / quasi-static trim mode. It shall not be required to track field changes in real time | Scope decision — see ADR-001 | Agreed |
| REQ-SYS-003 | The external null shall be stable for **[TBD — duration, e.g. one lab session ~4 h]** without re-trimming, under normal lab thermal conditions | Drift characterisation: **[TBD — from measurement campaign]** | TBD |

---

## QuSpin sensor parameters (inputs to requirements)

> All values below must be confirmed against the datasheet for the specific QuSpin gen in the lab.

| Parameter | Nominal | Confirmed | Source |
|-----------|---------|-----------|--------|
| Gen | — | **[TBD — read from hardware label]** | Hardware |
| Internal capture range | **[TBD]** nT | — | Datasheet |
| Saturation threshold (external field) | **[TBD]** nT | — | Datasheet / measurement |
| Analog output sensitivity | 2.7 V/nT (from prior project code) | **[TBD — verify]** | MEG_DSP DataSource.py; confirm vs datasheet |
| Analog output full-scale | **[TBD]** V | — | Datasheet |

The **capture range** value directly sets REQ-SYS-001 and REQ-COIL-001. Fill this in before sizing coils or drive electronics.

---

## Residual field characterisation targets

> These are the pre-conditions that must be measured before requirements can be derived.

| Measurement | Symbol | Target | Status |
|-------------|--------|--------|--------|
| Residual field magnitude at sensor 1 | B_res,1 | — | **[TBD — measure]** |
| Residual field magnitude at sensor 2 | B_res,2 | — | **[TBD — measure]** |
| Residual field, X component | Bx | — | **[TBD — measure]** |
| Residual field, Y component | By | — | **[TBD — measure]** |
| Residual field, Z component | Bz | — | **[TBD — measure]** |
| Field difference between sensor locations | ΔB | — | **[TBD — measure]** |
| Temporal drift over 4 h | dB/dt | — | **[TBD — measure]** |
| 50 Hz / harmonics content | B_AC | — | **[TBD — measure]** |

These numbers drive REQ-COIL-001 (coil authority), REQ-DRIVE-001 (current range), and REQ-DRIVE-002 (resolution).

---

## Coil system requirements

| ID | Requirement | Derived from | Status |
|----|-------------|--------------|--------|
| REQ-COIL-001 | Coils shall provide cancellation authority of at least **[TBD = B_res,max × margin]** nT per axis | REQ-SYS-001 + characterisation | TBD |
| REQ-COIL-002 | Field uniformity across the sensor separation volume shall be **[TBD]** % | ΔB measurement + QuSpin capture range | TBD |
| REQ-COIL-003 | Coil geometry and axis alignment shall be documented with mechanical drawings or annotated photographs sufficient for reconstruction | Reproducibility standard | Required |

---

## Drive electronics requirements

| ID | Requirement | Derived from | Status |
|----|-------------|--------------|--------|
| REQ-DRIVE-001 | Current source shall provide range of **[TBD]** mA per axis | REQ-COIL-001 + coil sensitivity (T/A, TBD) | TBD |
| REQ-DRIVE-002 | Current source resolution shall be ≤ **[TBD]** µA (to set field to within 10% of QuSpin capture range) | REQ-SYS-001 + coil sensitivity | TBD |
| REQ-DRIVE-003 | Current source noise floor shall produce field noise ≤ **[TBD]** pT/√Hz at the sensor | Noise budget — see `02_design/noise_budget.md` | TBD |
| REQ-DRIVE-004 | Current source shall inject no switching frequencies into the sensor band | MEG frequency band: **[TBD]** Hz — confirm with supervisor | TBD |

> REQ-DRIVE-004 is the principal driver of the custom linear current source option. See ADR-003.

---

## Verification requirements

| ID | Requirement | Verification method | Status |
|----|-------------|---------------------|--------|
| REQ-VER-001 | Both QuSpin sensors shall show valid (non-railing) output following the nulling procedure | Read NI-DAQ output; compare to saturation value — see `03_verification_plan.md` | TBD |
| REQ-VER-002 | All figures in documentation shall be regeneratable from checked-in scripts without manual intervention | Delete figures, run `scripts/figures/generate_all.py`, diff outputs | Required |
| REQ-VER-003 | Raw data files in `data/raw/` shall be unmodified from instrument output | Git SHA verification; no post-hoc editing | Required |
