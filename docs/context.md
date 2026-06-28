# FieldZero — Project Context

## The problem

The QUBIC MEG lab uses two QuSpin QZFM zero-field magnetometers inside a mu-metal shielded enclosure. The QuSpin has an internal field-zeroing loop, but it has a limited capture range — it can only null the field if the residual field is already weak enough. The residual field inside the enclosure is strong enough that the internal zeroing either takes excessively long (~10 minutes) or fails entirely, leaving the sensors saturated and unusable.

The lab's previous attempts to solve this in software failed because they were treating a hardware acquisition problem as a software problem.

## The goal

Reduce the residual magnetic field inside the enclosure enough that the QuSpin internal zeroing can acquire quickly and reliably. Once the QuSpin locks, it handles the rest.

**Success criterion**: both QuSpin sensors zero and lock in a reasonable time without intervention.

## What is known

- The residual field is estimated to be in the nT range — strong enough to saturate the sensors, weak enough that modest external coils should be able to cancel it
- The QuSpin software and NI-DAQ acquisition (Dev1, ai0–ai5, 2 sensors × 3 axes) are already working from prior lab work
- The mu-metal shield provides passive attenuation but leaves a residual that exceeds the QuSpin capture range

## What is not yet known

- QuSpin gen — check hardware label when in lab (affects sensitivity spec and capture range)
- Exact residual field magnitude and direction — must be measured
- How many axes are problematic — may be one dominant axis or all three
- QuSpin internal capture range — need datasheet for confirmed gen

## Constraints

- Solo engineer with supervisor
- ~2 weeks of working time starting when semester 2 begins
- Deliverable must be usable by lab members without the original engineer present
