# ADR-002: Two-Loop Architecture — External Coarse + QuSpin Internal Fine

**Date**: 2026-06-23  
**Status**: Decided  
**Decider**: Kayzer Ali (engineer)

---

## Context

The QuSpin QZFM sensor has an internal nulling loop with its own coil set. This loop operates within a limited capture range (exact value: **[TBD — from datasheet]** nT). Outside this range, the sensor saturates and produces no valid field reading.

The question is how to position the external cancellation system relative to the QuSpin's internal loop.

---

## Decision

Treat the system as two loops in series with a clean handoff:

1. **External loop (coarse)**: trim coils driven by the FieldZero current source, set manually. Responsibility: get the field within the QuSpin's capture range, with margin.
2. **QuSpin internal loop (fine)**: the sensor's own nulling. Responsibility: complete the null to zero-field and track small residual fluctuations.

The external system's job ends when both sensors are within their capture range. The handoff point is defined by the QuSpin capture range specification.

---

## Rationale

- The QuSpin internal loop has limited coil authority — it cannot acquire from a saturated state. External coarse acquisition is a prerequisite.
- Delegating fine trim to the QuSpin's own loop avoids the need to characterise or control the sensor to sub-nT accuracy externally, which would require a separate low-noise reference.
- The two-loop structure keeps the authority boundaries clean: external loop worries about nT-to-capture-range, internal loop worries about capture-range-to-zero.
- Cross-loop stability is not a concern because the loops operate on different timescales and authority ranges, and the external loop is static (DC trim).

---

## Consequences

- The external system only needs to achieve cancellation within the QuSpin capture range, not to zero. This relaxes the noise budget for the current source.
- The handoff must be defined quantitatively: the external trim must get the field to ≤ (capture range - margin), where margin is **[TBD — suggest 50% of capture range]**.
- If the QuSpin capture range is very small (e.g. ±1 nT), the external trim must achieve a tighter target, and the current source resolution and noise requirements tighten accordingly. This is why the capture range must be confirmed from the datasheet before sizing the drive electronics.
