# Drive Electronics Design

**Status**: Pre-design. Architecture decision (DAC vs. custom linear current source) pending — see ADR-003. Specifications pending coil sensitivity calibration and characterisation results.

---

## Specifications (to be derived)

| Parameter | Symbol | Value | Derived from |
|-----------|--------|-------|-------------|
| Output current range per axis | I_max | **[TBD]** mA | REQ-DRIVE-001 |
| Current resolution (LSB or trim step) | δI | **[TBD]** µA | REQ-DRIVE-002 |
| Current noise floor | I_n | **[TBD]** nA/√Hz | REQ-DRIVE-003 |
| Bandwidth | — | DC — **[TBD]** Hz | DC trim, no dynamic requirement |
| Prohibited frequency content | — | No switching artefacts in MEG band | REQ-DRIVE-004 |
| Number of independent channels | — | 3 (one per axis) | Coil system: 3 axes |
| Supply voltage | — | **[TBD]** V | Driven by coil resistance + I_max |

---

## Architecture options

> Decision recorded in ADR-003 once data supports it.

### Option A: DAC + off-the-shelf current source

Existing DAC in lab drives a voltage-controlled current source (VCCS).

**Pros**: fast to implement, calibrated, digitally addressable  
**Cons**:  
- DAC and/or downstream electronics may inject switching noise (clock, output filter ripple)  
- Must characterise DAC output noise in the MEG band before committing (REQ-DRIVE-004 gate)

**Risk**: if DAC switching noise floor exceeds REQ-DRIVE-003, this option is disqualified.

**Verification**: measure DAC output noise spectrum in the MEG band with a shunt resistor and spectrum analyser / NI-DAQ channel before routing to coils.

### Option B: Custom ultra-low-noise linear current source

Linear regulator topology (e.g. Howland current pump, or op-amp + sense resistor in linear region). Set point controlled by a potentiometer or precision resistor network.

**Pros**:  
- No switching frequencies  
- Noise floor set by op-amp voltage noise + resistor Johnson noise — can be designed to specification  
- Full control of spectral content

**Cons**:  
- Design and build time (within 2-week window)  
- Thermal drift of resistors sets long-term stability (sets REQ-SYS-003)  
- Requires a stable, low-noise supply rail

**Noise budget skeleton** (fill in after op-amp selection):

```
Op-amp voltage noise:      en = [TBD] nV/√Hz
Sense resistor:            Rs = [TBD] Ω
Johnson noise current:     In_R = sqrt(4kT/Rs) = [TBD] pA/√Hz at 300 K
Total current noise:       In ≈ en/Rs + In_R = [TBD] nA/√Hz
Field noise contribution:  Bn = In × (B/I) = [TBD] pT/√Hz
Requirement (REQ-DRIVE-003): [TBD] pT/√Hz
Margin:                    [TBD] dB
```

### Option C: Precision bench supply + manual potentiometer

Simplest. Manual coarse adjust via potentiometer on each axis. No electronics to build.

**Pros**: zero build time, zero switching noise if supply is linear  
**Cons**: no digital readback, repeatability depends on potentiometer quality, no automation path

**Note**: this is the supervisor's suggested baseline approach and fully satisfies the stated requirement. Options A and B are improvements, not prerequisites.

---

## Component selection

> **[TBD — after architecture decision]**

| Component | Parameter | Candidate | Notes |
|-----------|-----------|-----------|-------|
| Op-amp (Option B) | Voltage noise | TBD | Target: <10 nV/√Hz |
| Sense resistor (Option B) | Value, tolerance | TBD | Low tempco preferred (<25 ppm/°C) |
| Set-point potentiometer | Turns, linearity | TBD | Multi-turn preferred for resolution |
| Supply rail | Voltage, noise | TBD | Linear regulator, not switching |

---

## Thermal stability

For long-term stability (REQ-SYS-003), the dominant drift mechanism is resistor tempco. Estimate:

```
Set current:           I = V_set / Rs
Tempco drift:          δI/δT = I × (TCR_pot + TCR_Rs) [A/K]
Lab temperature variation: ΔT = [TBD] K over 4 h
Expected drift:        δI = [TBD] µA  →  δB = [TBD] nT
Requirement:           δB < QuSpin capture range = [TBD] nT
```

Fill in once resistors and tempco are selected.

---

## Open risks

- **Risk D-01**: DAC noise floor may disqualify Option A — gate on noise measurement before committing.
- **Risk D-02**: Custom current source build time may exceed schedule — assess after architecture decision.
- **Risk D-03**: Thermal drift of sense resistor may cause re-trimming more frequently than REQ-SYS-003 allows.
- **Risk D-04**: Coil resistance + required current may demand a supply voltage beyond bench supply capability. Check: V_supply > I_max × (R_coil + R_sense).
