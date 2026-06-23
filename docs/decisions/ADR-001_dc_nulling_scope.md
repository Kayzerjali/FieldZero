# ADR-001: Manual DC Nulling as Primary Approach (Closed-Loop Cancellation Deferred)

**Date**: 2026-06-23  
**Status**: Decided  
**Decider**: Kayzer Ali (engineer), confirmed with supervisor

---

## Context

The QUBIC lab operates two QuSpin QZFM-class OPM sensors inside a mu-metal shielded enclosure. The residual DC magnetic field inside the enclosure exceeds the sensors' internal nulling capture range, causing saturation. An active cancellation system is needed to bring the sensors into their linear operating range.

Two classes of solution were considered:

1. **DC trim (quasi-static nulling)**: Set coil currents once, hold fixed. External field is nulled at one operating point. If the field drifts, the operator re-trims manually.
2. **Closed-loop dynamic cancellation**: Continuously read sensors as feedback, compute error, and adjust coil currents to track and cancel field changes in real time.

---

## Decision

**Use manual DC trim** — coil currents set by an operator following a documented procedure, held fixed during a measurement session.

Closed-loop dynamic cancellation is deferred to future work and documented as a potential upgrade.

---

## Rationale

| Criterion | DC trim | Closed-loop |
|-----------|---------|-------------|
| Timeline (2 weeks of working time) | Feasible | Not feasible in scope |
| Hardware complexity | Potentiometer or DAC current source | Same + real-time ADC→compute→DAC loop |
| Software complexity | Nulling procedure script | PID/control law + latency budget + stability analysis |
| Requirement satisfied | Yes — success criterion is "sensors out of saturation" | Over-specified for stated requirement |
| Failure modes | Simple: wrong current, drift | More: loop instability, latency, sensor noise injection |
| Verifiability | Straightforward | Requires closed-loop stability characterisation |

The stated success criterion — bring sensors out of saturation so they can read nT-level signals — is a DC acquisition problem, not a dynamic noise cancellation problem. Closed-loop control would solve a harder, unspecified requirement.

---

## Consequences

- Design effort focuses on coil geometry, current source noise/stability, and a repeatable nulling procedure.
- Closed-loop capability is explicitly not designed in, to avoid scope creep.
- If field drift between sessions proves significant (from characterisation M-03), re-trimming at the start of each session is the accepted mitigation — not loop closure.
- Future upgrade path to closed-loop is not blocked; the coil system and acquisition interface are compatible with a feedback loop if requirements change.
