# ADR-003: Current Source Architecture — DAC vs. Custom Linear

**Date**: 2026-06-23  
**Status**: Open — decision pending noise measurement of available DAC

---

## Context

The cancellation coils require a stable, low-noise DC current source on each of three axes. Two candidate architectures are available:

- **Option A**: Use the existing DAC in the lab as a voltage-controlled current source (VCCS) front-end.
- **Option B**: Build a custom linear (non-switching) current source, set by potentiometers.

The principal risk with Option A is that a DAC and its downstream electronics may inject switching artefacts (clock harmonics, output ripple) into the sensor band, violating REQ-DRIVE-004. Option B avoids this risk but requires build time.

---

## Decision gate

**This decision cannot be made until the following test is completed:**

> Measure the noise spectrum of the available DAC output (with a representative load) in the MEG band (**[TBD]** Hz). Compare to REQ-DRIVE-003 (field noise floor) and REQ-DRIVE-004 (no switching artefacts in MEG band).

If the DAC passes both criteria: choose Option A.  
If the DAC fails either criterion: choose Option B (custom linear source).  
If timeline does not allow Option B build: default to Option C (bench supply + potentiometer — supervisor's baseline suggestion, always satisfies the requirement).

---

## Criteria for the decision

| Criterion | Weight | Option A (DAC) | Option B (Custom linear) | Option C (Bench + pot) |
|-----------|--------|----------------|--------------------------|------------------------|
| Switching artefacts in MEG band | Hard gate | Gate on measurement | None by design | None if supply is linear |
| Build time within schedule | High | Zero | **[TBD — estimate after design]** | Zero |
| Noise floor vs. REQ-DRIVE-003 | Hard gate | Gate on measurement | Designed to spec | Unknown — measure supply |
| Digital readback / automation path | Low | Yes (DAC value logged) | No (pot position not logged) | No |
| Repeatability | Medium | Excellent | Depends on pot | Depends on pot |

---

## Open actions

- [ ] Confirm MEG signal band with supervisor → sets REQ-DRIVE-004 frequency range
- [ ] Measure DAC output noise spectrum in MEG band (lab action, requires hardware access)
- [ ] If Option B: estimate build time; compare to schedule constraint
- [ ] Record decision outcome here once measurement data is available

---

## Notes

Option C (bench supply + potentiometer) is the minimal viable approach and the supervisor's suggestion. It is always a valid fallback if Options A and B are ruled out on timeline or noise grounds. Do not let the option analysis become a schedule risk — if in doubt, implement Option C and document the noise characterisation as future work.
