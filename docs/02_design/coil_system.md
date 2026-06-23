# Coil System Design

**Status**: Pre-design — coils not yet installed. This document will be filled in after characterisation (M-01 through M-05 in `01_characterisation.md`) establishes field magnitude, spatial uniformity, and required cancellation authority.

**Prerequisite**: REQ-COIL-001 and REQ-COIL-002 must be filled in before any geometry is committed.

---

## Inputs required from characterisation

| Input | Symbol | Value | Source |
|-------|--------|-------|--------|
| Maximum residual field per axis | B_res,max | **[TBD]** nT | M-02 |
| Required cancellation authority (with margin) | B_auth | **[TBD]** nT | REQ-COIL-001 |
| Field difference between sensor locations | ΔB | **[TBD]** nT | M-05 |
| Sensor separation distance | d | **[TBD]** mm | Physical measurement |
| Shielded room internal dimensions | — | **[TBD]** mm × mm × mm | Physical measurement |

---

## Geometry selection

> **[TBD — decision to be made after characterisation]**

Candidate geometries:

| Geometry | Uniformity | Complexity | Notes |
|----------|-----------|------------|-------|
| Helmholtz pair (each axis) | Good on-axis, limited volume | 6 coils total (3 pairs) | Standard for MEG labs |
| Square coil pairs (Anderson/Barker optimised) | Better volume uniformity | Same count, more critical placement | May be needed if ΔB is significant |
| Single rectangular coils (per axis) | Poor | Low | Likely insufficient |

Selection criterion: field uniformity over the sensor separation volume must satisfy REQ-COIL-002.

**Chosen geometry**: **[TBD]**  
**Rationale**: **[TBD]**

---

## Coil sensitivity (B/I)

Once geometry is chosen:

- **Analytical estimate**: record formula + parameters here (coil radius, turns, spacing)
- **Measured calibration**: from `scripts/coil_cal/` — provides B_coil/I_coil per axis in T/A
- **Calibration method**: **[TBD — apply known current, measure field change at sensor or with reference probe]**

| Axis | Analytical B/I (T/A) | Measured B/I (T/A) | Measured date |
|------|---------------------|-------------------|---------------|
| X | TBD | TBD | TBD |
| Y | TBD | TBD | TBD |
| Z | TBD | TBD | TBD |

The measured calibration value feeds directly into REQ-DRIVE-001 (current range) and REQ-DRIVE-002 (current resolution).

---

## Mechanical design

> **[TBD]** — Annotated photographs or dimensioned drawings to be added here after installation.

Requirements for documentation:
- Photograph each coil pair with a scale reference
- Record coil centre positions relative to the sensor mount
- Record axis orientation (which physical direction is X, Y, Z)
- Record number of turns, wire gauge, coil form material

Reproducibility requirement: a future engineer must be able to reconstruct the coil geometry from this document alone.

---

## Decoupling between axes

Cross-coupling between X, Y, Z coils **[TBD — measure after installation]**:

| Drive axis | Field induced on X | Y | Z |
|------------|-------------------|---|---|
| X | 1.0 (nominal) | TBD % | TBD % |
| Y | TBD % | 1.0 | TBD % |
| Z | TBD % | TBD % | 1.0 |

If coupling coefficients are >**[TBD — threshold, suggest 5%]**, a decoupling matrix must be applied in the nulling procedure. Record decision in ADR-004 when data is available.

---

## Open risks

- **Risk C-01**: If ΔB exceeds the QuSpin capture range, a uniform coil set cannot simultaneously satisfy both sensors. Mitigation: independent per-sensor trim (increased scope) or accept that one sensor is primary. Decision required.
- **Risk C-02**: Coil installation may alter the shielding factor of the mu-metal enclosure if coil forms or brackets are ferromagnetic. Mitigation: use non-magnetic materials (aluminium, acrylic, brass).
- **Risk C-03**: Coil mechanical stability — vibration or thermal expansion may shift coil position and alter B/I. Mitigation: rigid mounting; post-installation re-calibration procedure.
