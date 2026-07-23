# FieldZero — Project Context

## The problem

The QUBIC MEG lab uses two QuSpin QZFM zero-field magnetometers inside a mu-metal shielded enclosure. The QuSpin has an internal field-zeroing loop but it has a limited capture range — it can only null the field if the residual field is already weak enough. The residual field inside the enclosure is strong enough that the internal zeroing either takes excessively long (~10 minutes) or fails entirely.

The lab previously spent time trying to fix this in software before realising the root cause was hardware: the residual field simply exceeds what the QuSpin internal coils can handle.

## The goal

Reduce the residual magnetic field inside the enclosure enough that the QuSpin internal zeroing acquires quickly and reliably. Once it locks, it handles the rest. This is a coarse acquisition problem, not a cancellation problem — the DC/quasi-static saturation-escape criterion is the core success bar.

**Architecture (scope shift from static trim)**: target moved from manual potentiometer set-and-forget to an active closed-loop PID cancellation system, per supervisor request. Not a one-time manual null.

**Success criterion**: both QuSpin sensors zero and lock in under ~2 minutes without intervention. This is not a strict requirement — it is a guide.

**Deliverable**: a system simple enough that any lab member can operate it following a procedure, without the original engineer present.

## Prior art

Holmes et al. 2023 (matrix coil active shielding for ambulatory MEG) is the direct predecessor: 48 unit coils on two planes, optical tracking for pose, spherical-harmonic projection (3 uniform + 5 gradient) via pseudo-inverse chained to a coil forward-model inverse, proportional feedback (Kp=0.4, 40 Hz, 25 ms latency), static shielding factor ~13.7×, moving ~5.2×. Their complexity (tracking + 48-coil inversion) solves a moving target over a whole-head volume — a problem we don't have with a small static 2-sensor enclosure. HFC (Tierney/Mellor) is the software-only version of the same harmonic projection; it's the lineage from the earlier 2-sensor common/differential PCA work → HFC → matrix coil.

## Field model and coil drive (worked through by hand, not yet bench-verified)

- Field over the region: B(r) = b₀ + G·(r−r₀) — uniform vector + gradient tensor. Needed because coils act over a region but we only measure at 2 points.
- Forward model y = H·b₀ (H from sensor geometry, not data), solved as b₀ = H⁺y. For two co-oriented triaxial sensors this collapses to: uniform = average of the two readings, gradient = difference / separation — the physics-derived version of the existing PCA common/differential split.
- **Observability limit**: 2 sensors separated along z can only observe ∂B/∂z (the z-column of G). Other gradient components are structurally invisible with this geometry.
- **Coil drive decomposition**: a biplanar pair has two natural modes — common mode (both coils same direction) → uniform field, differential mode (opposite) → gradient. This is a square, invertible 2×2 system: 2 observables (uniform Bz, ∂Bz/∂z), 2 knobs (common current, differential current). Physical currents I_T, I_B solved via M⁻¹ where M = [[p,q],[q,p]] (p,q = near/far coupling per amp, from Biot–Savart or bench).
- Currently z-axis only — a full uniform-vector cancellation needs 3 orthogonal coil pairs (Bx, By, Bz).

## Control architecture (settled)

The single-shot M⁻¹ solve applied every timeslice is itself a P-controller with Kp=1, but assumes a perfect forward model and static disturbance (both false — coil calibration is rough, field drifts). Fix: wrap the inversion in feedback — M⁻¹ gets close fast (feedforward), an integral term grinds to true zero (absorbs model error + drift). Practical form: PI, integral-dominant, one loop per drive mode (common-mode current, differential-mode current). D-term omitted — amplifies OPM noise, unnecessary for DC/quasi-static. Sign per axis must be verified on the bench (wrong sign → runaway).

Two nested loops in series: external coil loop = coarse acquisition into the QuSpin's ±few-nT capture range; QuSpin's internal null = fine trim. Bootstrapping: QuSpins are saturated on day 1, so the fluxgate does initial characterization until they come into range, then the OPMs become the loop sensor.

## Sensor data path (settled 2026-07-24)

How QZFM readings reach the coil driver. Each QZFM electronics module has **two independent outputs to the PC**: (1) **analog** — BNC per axis, ±5 V rail-to-rail, gain-selectable (2.7 V/nT default, 0.9 V/nT low, 8.1 V/nT high), read by the lab's NI DAQ (NI-9205, QuSpin's recommended unit); (2) **USB digital serial** — an FT232RL virtual COM port (115200 8N1) used by the QuSpin UI for calibration/zeroing/gain, which also streams 24-bit field values on the `Print ON` command (`(raw − 8388608) × 0.01 = pT`).

**Chosen path: PC-in-the-loop ("A1").** fields → NI-9205 (or QZFM USB serial) → PC (Python PID) → USB → Nano R4 → DAC8814 (SPI) → coils. The **MCU is a DAC bridge**, not the controller: it translates USB current commands to SPI DAC writes, holds the last-commanded current, and drops to safe-state (zero-current code) if the PC stops. Rationale: the loop is DC/quasi-static (<~few Hz), so the PC round-trip (~5–30 ms) is irrelevant — Holmes ran a harder moving-target loop at 40 Hz / 25 ms; **v010 already implements A1 with no board change**; and a PC is required in the room for the QuSpin UI regardless, so full MCU autonomy buys little (see [autonomous mode](#improvements--extensions-deferred) in Extensions).

**Ruled out: "NI DAQ → MCU directly."** An NI USB/cDAQ device is a USB peripheral requiring the NI-DAQmx driver stack on a host PC; the Nano R4 cannot host it. There is no DAQ→Arduino path.

**Capture-range caveat:** the QZFM analog output clips at ±1.85 nT (default gain) / ±5.5 nT (low gain), so the OPMs are only usable as the loop sensor once the field is already within range — the fluxgate must carry the bootstrap phase whichever routing is used.

## Electronics (settled)

Architecture: MCU → DAC → voltage-controlled current source (VCCS) per coil. Rejected DAC + series resistor (current = V/R_total drifts with coil copper temperature). VCCS uses a precision sense resistor inside the op-amp feedback loop so current is pinned at V_control/R_sense regardless of coil resistance.

Howland vs. series-sense is current-dependent, not a blanket call. Mrozowski et al. 2022 (Vernier Current Driver) show Howland current pumps degrade above ~50 mA — resistor self-heating unbalances the bridge, CMRR drops, and the drive stage's own heat couples into the control loop. Below that, their Howland-based LCD (DAC8814 + LTC6655 ref + OPA2210 pump) measures 14.6–15.1 ppb/√Hz, beating their series-sense HCD (16.5 ppb/√Hz at 250 mA). Our coil current for a ±10 nT trim field is expected well under 50 mA, so **adopting the LCD topology wholesale** (Howland pump, same op-amp/DAC/reference) rather than series-sense — revisit only if the coil transfer function (still unmeasured) demands more current than that.

Spec priority, in order:
1. Low current noise in-band — cheap to mitigate since the loop is <~few Hz, so filter hard / use a slow op-amp.
2. Short-term stability / low offset drift — use a chopper/auto-zero op-amp (offset appears as V_os/R_sense current error, kills it at DC).
3. Bipolar source-and-sink (currents go negative and flip sign — needs bipolar supply, no PWM/H-bridge switching noise).
4. Absolute accuracy matters least (feedback absorbs it).

R_sense: low-tempco foil/metal-film, sized so V_sense ≫ op-amp offset. DAC: ≥16-bit floor, resolution set by (total field span / capture range); possibly coarse+fine split.

## PCB (settled — as-built for first prototype, rev 0.1 / "v010")

The first prototype is board **rev 0.1** (schematic title-block `rev "0.1"`), referred to as **"v010"**; the next respin is **v011**. Working KiCad project: `Hardware/Low_Current_Driver/` — a duplicate of the Strathclyde Vernier LCD reference design, kept alongside its own copy of `Common/` since the lib tables use `${KIPRJMOD}/../Common/...` relative paths. The stray upstream clone under `docs/Vernier-Current-Driver/` is left untouched as reference — `Hardware/Low_Current_Driver/` is the only one that should be edited.

**Hierarchy (after the multichannel refactor):** root → `DAC` (→ `DAC_OPA` ×2, the A/B DAC buffers) · `MCU` · `Channel_Outputs` ×2 (`Coil_Drive_A`, `Coil_Drive_B`). The two coil drive channels are native KiCad multichannel instances of one `Channel_Outputs` sheet (z-axis common/differential — matches current single-axis scope). The reference design's `Power`, `Battery_Management`, and `Mounting_Holes` sheets were **removed** — see power entry below.

**Board specifics (settled, schematic-verified):**
- **MCU: Arduino Nano R4** (`A1`, replaces the reference design's ESP32-S3). The digital 5 V rail (`5VD`) is sourced from the Nano's own 5 V pin, not an on-board regulator. The ESP32-S3 symbol/footprint/STEP leftovers have been deleted and its `sym-lib-table` entry removed.
- **Power entry: external raw ±9 V through a 4-position Phoenix screw terminal** (`J3`, MKDS-1,5/4-5,08, MPN 1729144) carrying `+9V` / `−9V` / `GND` / `GNDA`, switched by a panel DPST switch (`SW1`, E-Switch RA83231100). The design source is **series 9 V batteries** (center-tapped for ground — the Vernier low-noise heritage; 9 V cells + snap leads are on the DigiKey list); a bench supply can substitute for characterization. **No on-board regulation or battery-management stage** — the reference design's ±12 V→±9 V LDOs (U4/U5/U6) and reverse-polarity front end are gone; raw ±9 V feeds the rails directly (down from the reference's ±12 V, adequate for the op-amp swing needed).
- **Coil connections: Molex Micro-Fit inline connectors** (`J1`, `J2`) — enamel coil wire spliced to a silicone-wire pigtail, crimped into a Micro-Fit, mated to a matching PCB-side connector.
- **Schematic ERC:** the two active drive channels (DAC A/B → buffers → coils) are clean. Two residual ERC errors remain on the DAC8814's **unused** C/D current outputs (`Iout_C`/`Iout_D` tied together and parked with a `PWR_FLAG`) — schematic-annotation only, no functional or copper impact; left as-is for the prototype.

**First-prototype scope cut (revisit before any lab-deployed build)**: the first board deliberately trades robustness for speed to get a characterization prototype on the bench. On-board power conditioning is omitted wholesale: no regulation (raw ±9 V comes straight from the battery pack), no reverse-polarity protection (MOSFET pair / polyfuses / TVS), no power-good LEDs or front-panel LED connector. A hard DPST switch (`SW1`) is the only power control — no soft on/off. Net effect: the board depends on a correctly-wired ±9 V source (battery pack or bench supply) and is unprotected against a reversed or over-voltage input. Acceptable for the bench-test/characterization build only; the project's own "operable by any lab member without the engineer present" deliverable goal implies regulation, protection, and idiot-proof power entry belong in whatever board actually ships to the lab.

## Protection — coil/op-amp side (settled by analysis)

Distinct from the reverse-polarity/idiot-proofing cuts above: the inductive-transient protection on the op-amp→coil side was analyzed on physics grounds and found genuinely unnecessary at this energy level — not a deadline compromise.

- **Stored coil energy is negligible.** E = ½LI² = ½(4 µH)(10 mA)² = **200 pJ** — seven orders of magnitude below a barely-perceptible ESD event.
- **SW1-off / brownout:** the coil sits in series with the sense resistor, so decay τ = L/R ≈ 4 µH / 1 kΩ ≈ 4 ns. The coil fully de-energizes ~a million times faster than the ±9 V rails can sag; the ~10 mA is far below any ESD-diode / latch-up threshold. **No op-amp output→rail clamp needed.**
- **Hot-unplug:** V_peak = I·√(L/C) into stray capacitance is only ~2–6 V — won't arc a connector and is trivially inside op-amp tolerance. A board-side clamp couldn't protect the coil anyway (it leaves on the far side of the break). **No coil-side TVS needed.**
- **Safe power-down is a firmware sequence, not hardware:** command all DAC channels to zero-current code (mid-scale for the bipolar output), assert `LDAC` so the op-amp ramps coil current to zero under closed-loop rail-bounded control, wait a few τ (ms is ample), *then* cut power. Coil energy is already zero before control is lost.
- **The one conditional item: MCU `D1` (VIN backfeed diode).** Only justified if the actual Nano R4 backfeeds its VIN pin when USB-powered with the ±9 V supply off. Decide by one measurement — power from USB only, bench supply off, read VIN: ~0 V → no protection diode needed at all; ~4–5 V → keep a series Schottky on VIN only. (The old `D2` 5 V-bridge diode was DNP — never populated, a no-op.)

## Fabrication — first prototype (settled 2026-07-23)

- **Board:** 4-layer, 127.75 × 53.0 mm, stackup F.Cu / GND / PWR / B.Cu. Ordered as a **bare PCB** (hand-assembled from the DigiKey BOM, not JLC PCBA).
- **Fab package:** `Hardware/Low_Current_Driver/fab1.zip` — gerbers + PTH/NPTH drills, regenerated 2026-07-23 08:16, byte-matches the current `.kicad_pcb`.
- **JLC quote:** $29.20 = $4.20 board + **$25 engineering (NRE) fee**, triggered by 4 layers **and** the >100 mm long edge (both push the order out of JLC's free-prototype tier). Not worth redesigning around — the GND/PWR planes are worth more than the fee.
- **DRC (KiCad 10.0.4, current board):** 0 errors, 0 unconnected, schematic parity clean; 1 cosmetic warning only (silk clipped by mask on an `HCP` test-point ref) — JLC auto-clips, non-blocking.
- **BOM / DigiKey:** MPN + DigiKey link live on each schematic symbol (no external BOM file); the curated purchase list is the DigiKey mylist **"FieldZero"** (7UCPWN2VGF), which also carries the 9 V batteries + snap leads (power source, not schematic symbols). All 15 schematic MPNs re-verified **Active** on DigiKey 2026-07-23, every one in stock except **J3 (Phoenix 1729144), Active-but-0-stock — deliberately off the order because the engineer has it at the UQ lab.** Parts ≈ $110/board at qty 1, dominated by DAC8814 $46.61, 4× OPA2210 $25.48, LTC6655 $14.63, Nano R4 $13.30.
- **Known metadata drift (harmless):** 100 nF caps carry Kemet `C0603C104K5RACTU` on the schematic vs Samsung `CL10B104KB8NNNC` on the PCB footprints — the orderable BOM exports from the schematic (Kemet). Test-point reference designators also differ between schematic (`TP15`…) and PCB (net-name labels). Neither affects the copper or the parts order.

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
- Whether gradient control is needed at all: uniform-only cancellation leaves each sensor at ±(gradient×a); if that residual is below QuSpin capture range (~few nT), differential control can be skipped. Sensors are close together so uniform-only likely suffices, but the fluxgate campaign must measure the actual gradient across the baseline before deciding.
- Actual QZFM triaxial output and sensor separation vector — fixes H and the true loop count
- Coil geometry — determines whether the op-amp drives the coil directly (tens of mA, simple) or needs a pass transistor / power op-amp (amps, op-amp becomes the controller with R_sense staying in loop). Working estimate (≈4 µH inductance, ≤10 mA full-scale for a ±10 nT trim) sits firmly in the direct-drive regime, so no pass transistor is planned — provisional until the coil transfer function is bench-measured.

## Improvements / Extensions (deferred)

Forward-looking work that is understood but deliberately **not** in v010. Consolidated here so a v011 respin has a single checklist. Each item is traceable to a decision or measurement gap above.

- **Autonomous mode (no PC in the control loop).** The chosen path is PC-in-the-loop (see [Sensor data path](#sensor-data-path-settled-2026-07-24)); autonomous mode moves the PID onto the MCU and reads the QZFM analog outputs directly, so the box cancels with the PC out of the loop (NI DAQ demoted to logging/characterization). Requires a v011 respin: a **6-channel bipolar analog front-end** (±5 V QZFM outputs → attenuate + offset + anti-alias into ADC range) feeding a **dedicated SPI ADC** (≥16-bit, e.g. ADS1256-class) rather than the Nano R4's 14-bit unipolar onboard ADC. Justified only if a standalone (PC-free) controller is wanted — the QuSpin UI already needs a PC in the room, so this is a feature, not a requirement. The ±1.85/±5.5 nT analog clip still applies: the fluxgate carries bootstrap regardless.
- **Power conditioning + protection** (the first-prototype scope cut, above). For any lab-deployed board: on-board regulation (reference design's ±12→±9 LDOs or equivalent), reverse-polarity protection (MOSFET pair / polyfuses / TVS), power-good LEDs + front-panel LED connector, and ideally soft on/off replacing the hard DPST switch. v010 depends on a correctly-wired ±9 V source and is unprotected against reversal/over-voltage — bench-only. The "operable by any lab member" deliverable implies these belong on the shipped board.
- **Full 3-axis uniform cancellation.** v010 is z-axis only (2 channels: common/differential Bz). A full uniform-vector null needs 3 orthogonal coil pairs (Bx, By, Bz). The native multichannel sheet structure makes replicating the drive channel cheap; the DAC8814 is quad (2 channels used, 2 spare — one more axis fits before a second DAC is needed). Real constraints are board area and coil connectors.
- **Gradient control — decide, then possibly drop.** Whether differential (gradient) drive is needed at all depends on the measured gradient across the sensor baseline. If uniform-only cancellation leaves each sensor below QuSpin capture range, differential drive can be dropped, halving channels per axis. Blocked on the fluxgate gradient measurement (see What is not yet known).
- **Drop the NI DAQ from the loop.** Read fields straight off the QZFM USB serial (`Print ON`, 24-bit) if the stream rate suffices for a few-Hz loop, removing the NI-9205 from the control path: QZFM USB → PC → MCU USB. Keep the DAQ only for characterization/logging. Confirm the serial stream rate in the lab before committing.
- **Higher coil current (pass transistor / power op-amp).** Direct-drive (≤10 mA, Howland pump) assumes the ≈4 µH / ±10 nT working estimate holds. If the bench-measured coil transfer function needs >~50 mA, Howland degrades (sense-resistor self-heating unbalances the bridge) — switch to series-sense and/or add a pass transistor with R_sense kept in the loop.
- **DAC coarse+fine split.** If the required resolution (total field span / capture range) exceeds a single 16-bit DAC's usable range, split into summed coarse+fine DACs. Not needed at current working numbers; revisit after the field magnitude is measured.
- **MCU VIN backfeed diode (D1).** Conditional item from the protection analysis: only if the Nano R4 backfeeds VIN when USB-powered with ±9 V off. One measurement decides (VIN under USB-only power: ~0 V → no diode; ~4–5 V → series Schottky on VIN). Cheap to add on a respin.

## Resources
- A working example or capturing data from the qzfms can be seen in the repo
"https://github.com/Kayzerjali/MEG_DSP.git".
- Vernier Current Driver (Strathclyde EQOP, Mrozowski & Chalmers) — open-source ultra-low-noise bipolar current source, reference design for the coil-driver electronics and PCB: https://github.com/Strathclyde-EQOP/Vernier-Current-Driver — paper: https://arxiv.org/abs/2207.10348
