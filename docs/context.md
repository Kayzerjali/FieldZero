# FieldZero — Project Context

## The problem

The QUBIC MEG lab uses two QuSpin QZFM zero-field magnetometers inside a mu-metal shielded enclosure. The QuSpin has an internal field-zeroing loop but it has a limited capture range — it can only null the field if the residual field is already weak enough. The residual field inside the enclosure is strong enough that the internal zeroing either takes excessively long (~10 minutes) or fails entirely.

The lab previously spent time trying to fix this in software before realising the root cause was hardware: the residual field simply exceeds what the QuSpin internal coils can handle.

## The goal

Reduce the residual magnetic field inside the enclosure enough that the QuSpin internal zeroing acquires quickly and reliably. Once it locks, it handles the rest. This is a coarse acquisition problem, not a cancellation problem.

**Success criterion**: both QuSpin sensors zero and lock in under ~2 minutes without intervention. This is not a strict requirement — it is a guide.

**Deliverable**: a system simple enough that any lab member can operate it following a procedure, without the original engineer present.

## What is known

- Residual field estimated in the nT range
- Enclosure is mu-metal, sized to comfortably fit a styrofoam head with sensors mounted
- QuSpin software and NI-DAQ acquisition (Dev1, ai0–ai5, 2 sensors × 3 axes) already working from prior lab work
- The mu-metal provides passive attenuation but leaves a residual that exceeds the QuSpin capture range

## What is not yet known

- QuSpin gen — check hardware label when in lab (determines capture range and sensitivity spec)
- Exact residual field magnitude and which axes are worst — must be measured
- QuSpin internal capture range — need datasheet for confirmed gen
- Whether existing cancellation coils are installed or enclosure is bare
