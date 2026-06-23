# Noise Budget

**Status**: Framework only. Numbers are TBD pending characterisation and component selection.

The noise budget traces from current source noise floor through coil sensitivity to residual field noise at the sensor, and compares against the QuSpin capture range to confirm the design has sufficient margin.

---

## Noise chain

```
Current source noise                  [TBD] nA/√Hz
        ↓  × coil sensitivity
Field noise at sensor                 [TBD] pT/√Hz
        ↓  vs. QuSpin capture range
Required floor: field_noise << capture_range / √(measurement_BW)
```

For a DC trim system the relevant metric is not spectral density but total integrated drift over the hold time (REQ-SYS-003). Both are computed below.

---

## Budget table

| Noise source | Spectral density | In-band contribution | Notes |
|-------------|-----------------|---------------------|-------|
| Op-amp voltage noise (×Rs) | **[TBD]** nA/√Hz | **[TBD]** nT | Option B only |
| Sense resistor Johnson noise | **[TBD]** nA/√Hz | **[TBD]** nT | Rs = [TBD] Ω |
| DAC quantisation noise (effective) | **[TBD]** nA/√Hz | **[TBD]** nT | Option A only |
| DAC switching artefacts | — | **[TBD]** nT peak | Must be <10% of capture range |
| Supply rail noise | **[TBD]** nA/√Hz | **[TBD]** nT | PSRR of current source |
| **Total (RSS)** | **[TBD]** nA/√Hz | **[TBD]** nT | |
| **Requirement (REQ-DRIVE-003)** | **[TBD]** nA/√Hz | **[TBD]** nT | |
| **Margin** | — | **[TBD]** dB | Target: ≥10 dB |

---

## Drift budget (DC stability)

| Drift source | Mechanism | Estimated drift over [TBD] h | Notes |
|-------------|-----------|------------------------------|-------|
| Sense resistor tempco | TCR × ΔT × I | **[TBD]** nT | TCR = [TBD] ppm/°C |
| Op-amp offset drift | dVos/dT × gain | **[TBD]** nT | Vos_tc = [TBD] µV/°C |
| Potentiometer contact resistance | Temperature, vibration | **[TBD]** nT | |
| External field drift (lab environment) | Building, equipment | **[TBD]** nT | From M-03 |
| **Total drift** | | **[TBD]** nT | Must be < QuSpin capture range |
| **Requirement (REQ-SYS-003)** | | **[TBD]** nT over [TBD] h | |

---

## Fill-in sequence

This document can only be completed in this order:

1. Confirm QuSpin capture range from datasheet → sets the budget headroom
2. Complete characterisation (M-03 drift, M-04 AC) → sets external field drift contribution
3. Choose current source architecture (ADR-003) → determines which noise sources are relevant
4. Select components → fill in en, TCR, etc.
5. Compute budget → check margin
6. If margin < 10 dB, revise component selection or architecture
