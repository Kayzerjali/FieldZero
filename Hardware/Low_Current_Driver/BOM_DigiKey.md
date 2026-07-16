# Vernier Low Current Driver (LCD) — DigiKey BOM

Bill of materials for `Low_Current_Driver.kicad_sch` (rev 1.1.0), with an exact
DigiKey part and clickable link for every orderable line. Every link below was
opened and checked against DigiKey on **2026-07-16** (manufacturer part number,
package, and stock confirmed on the live product page).

**How to use:** click each DigiKey # to open the exact product page and add to
cart. The **Notes** column flags anything you should glance at (low stock,
backorder, marketplace-only). Passive part numbers are Cut-Tape (`CT`) DigiKey
SKUs — swap the `CT` suffix for `TR` if you want full reels.

Quantities are per single board.

---

## 1. Orderable parts (verified on DigiKey)

### Resistors — 0603, Yageo RC series, ±1%, 1/10 W

| Qty | Value | Ref(s) | Mfr Part # | DigiKey # | Notes |
|----|-------|--------|-----------|-----------|-------|
| 21 | 10 k | R1-R6, R11, R12, R15-R25, R29, R30 | RC0603FR-0710KL | [311-10.0KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-0710KL/726880) | 7.3M in stock |
| 12 | 1 k | R32, R33, R35, R36, R38-R41, R44-R47 | RC0603FR-071KL | [311-1.00KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-071KL/726843) | 1.9M in stock |
| 2 | 100 k | R8, R10 | RC0603FR-07100KL | [311-100KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-07100KL/726889) | 3.2M in stock |
| 1 | 120 k | R7 | RC0603FR-07120KL | [311-120KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-07120KL/726921) | 102k in stock |
| 2 | 133 k | R9, R53 | RC0603FR-07133KL | [311-133KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-07133KL/726937) | in stock |
| 1 | 549 k | R13 | RC0603FR-07549KL | [311-549KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-07549KL/727300) | 2.7k in stock |
| 1 | 102 k | R14 | RC0603FR-07102KL | [311-102KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-07102KL/726891) | DK-direct stock 0; 3.9M on Marketplace |
| 1 | 3 k | R51 | RC0603FR-073KL | [311-3.00KHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-073KL/727119) | 144k in stock |
| 1 | 2 M | R52 | RC0603FR-072ML | [311-2.00MHRCT-ND](https://www.digikey.com/en/products/detail/yageo/RC0603FR-072ML/727010) | 81k in stock |

### Capacitors — MLCC

| Qty | Value | Ref(s) | Package / Rating | Mfr Part # | DigiKey # | Notes |
|----|-------|--------|------------------|-----------|-----------|-------|
| 22 | 100 nF | C14-C20, C30, C34, C35, C37-C42, C56-C59, C62, C63 | 0603 50 V X7R | CL10B104KB8NNNC (Samsung) | [1276-1000-1-ND](https://www.digikey.com/en/products/detail/samsung-electro-mechanics/CL10B104KB8NNNC/3886658) | in stock |
| 15 | 1 µF | C1, C2, C7-C9, C21, C22, C24-C27, C49, C50, C52, C53 | 0603 25 V X7R | TMK107B7105KA-T (Taiyo Yuden) | [587-2984-1-ND](https://www.digikey.com/en/products/detail/taiyo-yuden/TMK107B7105KA-T/2714162) | 709k in stock |
| 2 | 10 nF | C10, C29 | 0603 50 V X7R | CL10B103KB8NNNC (Samsung) | [1276-1009-1-ND](https://www.digikey.com/en/products/detail/samsung-electro-mechanics/CL10B103KB8NNNC/3886667) | 2M in stock |
| 4 | 10 µF | C4-C6, C28 | 1206 25 V X5R | GRM319R61E106KA12D (Murata) | [490-5525-1-ND](https://www.digikey.com/en/products/detail/murata-electronics/GRM319R61E106KA12D/2334876) | 371k in stock |
| 4 | 47 µF | C11-C13, C23 | 1210 16 V X5R | CL32A476KOJNNNE (Samsung) | [1276-3376-1-ND](https://www.digikey.com/en/products/detail/samsung-electro-mechanics/CL32A476KOJNNNE/3889034) | on +5V rail, 16 V is fine; 522k in stock |

### Semiconductors & ICs

| Qty | Ref(s) | Value | Package | Mfr Part # | DigiKey # | Notes |
|----|--------|-------|---------|-----------|-----------|-------|
| 2 | D1, D2 | MBR0520LT | SOD-123 | MBR0520LT1G (onsemi) | [MBR0520LT1GOSCT-ND](https://www.digikey.com/en/products/detail/onsemi/MBR0520LT1G/918574) | only 95 in stock — order early / see substitutes |
| 4 | D3-D6 | SMBJ16A | SMB / DO-214AA | SMBJ16A (Littelfuse) | [SMBJ16ALFCT-ND](https://www.digikey.com/en/products/detail/littelfuse-inc/SMBJ16A/688274) | 62k in stock |
| 1 | Q1 | Si4447ADY | SO-8, P-ch | SI4447ADY-T1-GE3 (Vishay) | [SI4447ADY-T1-GE3CT-ND](https://www.digikey.com/en/products/detail/vishay-siliconix/SI4447ADY-T1-GE3/4496231) | 18.5k in stock |
| 2 | U1, U2 | LM4040DBZ-5 | SOT-23-3 | LM4040DIM3-5.0/NOPB (TI) | [LM4040DIM3-5.0NS/NOPBCT-ND](https://www.digikey.com/en/products/detail/texas-instruments/LM4040DIM3-5-0-NOPB/305140) | 5.0 V, ±1%; 8.1k in stock |
| 1 | U3 | LM393 | TSSOP-8 | LM393PWR (TI) | [296-14607-1-ND](https://www.digikey.com/en/products/detail/texas-instruments/LM393PWR/555703) | 6.6k in stock |
| 2 | U4, U5 | TPS7A470x | QFN-20 | TPS7A4700RGWR (TI) | [296-39503-1-ND](https://www.digikey.com/en/products/detail/texas-instruments/TPS7A4700RGWR/3588843) | 6.7k in stock |
| 1 | U6 | TPS7A33 | QFN-20 | TPS7A3301RGWR (TI) | [296-39502-1-ND](https://www.digikey.com/en/products/detail/texas-instruments/TPS7A3301RGWR/3675141) | 2.4k in stock |
| 1 | U7 | LTC6655-2.5 | MSOP-8 | LTC6655BHMS8-2.5#PBF (ADI) | [505-LTC6655BHMS8-2.5#PBF-ND](https://www.digikey.com/en/products/detail/analog-devices-inc/LTC6655BHMS8-2-5-PBF/2138766) | **stock 0 — ~11 wk lead**, or use `#TRPBF` reel version |
| 1 | U8 | DAC8814 | SSOP-28 | DAC8814IBDBT (TI) | [296-18608-1-ND](https://www.digikey.com/en/products/detail/texas-instruments/DAC8814IBDBT/296-18608-1-ND/863277) | 660 in stock |
| 4 | U9, U10, U12, U13 | OPA2210 | SOIC-8 | OPA2210IDR (TI) | [296-OPA2210IDRCT-ND](https://www.digikey.com/en/products/detail/texas-instruments/OPA2210IDR/10715389) | 1.7k in stock |

### Connectors, module & switch

| Qty | Ref(s) | Value | Mfr Part # | DigiKey # | Notes |
|----|--------|-------|-----------|-----------|-------|
| 1 | A1 | Arduino Nano Every | ABX00028 (Arduino) | [1050-ABX00028-ND](https://www.digikey.com/en/products/detail/arduino/ABX00028/10239971) | 1.8k in stock (no-header version) |
| 1 | J2 | RJ45 | 54602-908LF (Amphenol ICC) | [609-1046-ND](https://www.digikey.com/en/products/detail/amphenol-cs-fci/54602-908LF/1001360) | DK-direct stock 0; 1,470 on Marketplace |
| 1 | J3 | Screw terminal 4-pos 5.08 mm | ED120/4DS (On Shore) | [ED2227-ND](https://www.digikey.com/en/products/detail/on-shore-technology-inc/ED120-4DS/265402) | 1.7k in stock |
| 1 | J4 | IDC box header 2×7, 2.54 mm | 61201421621 (Würth) | [732-5397-ND](https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/61201421621/4846920) | 7.5k in stock |
| 1 | J9 | Header 1×2, 2.54 mm | 61300211121 (Würth) | [732-5315-ND](https://www.digikey.com/en/products/detail/w%C3%BCrth-elektronik/61300211121/4846823) | 231k in stock |

---

## 2. Placeholders — pick / confirm before ordering

These lines are **not** a clean single-click DigiKey buy. Per your call, they're
left as placeholders. A concrete direction is given for each.

| Ref(s) | Value | Why it's a placeholder | Suggested DigiKey direction |
|--------|-------|------------------------|-----------------------------|
| Q2 | IRF8707PbF | **Obsolete** — discontinued by Infineon, not made. It's a battery-path load switch (not signal-critical). | Any logic-level N-ch SO-8, ≥30 V, low R_DS(on). Confirm gate-drive voltage, then pick e.g. a Vishay Si4840-class part. Needs a one-line part choice, not a footprint change. |
| J5, J6, J7 | BNC (Amphenol B6252HB-NPP3G-50) | Not carried by DigiKey (Mouser/Newark only). | Substitute a DigiKey-stocked right-angle PCB BNC jack (Amphenol RF, e.g. 031-6575) — **requires a footprint edit**; none is pin-for-pin. |
| J8 | MS548-10F | Made by **Masach Technologies** — sold via Mouser/LCSC/Farnell, not DigiKey. This is the battery connector (large ~54×40 mm footprint), tied to the physical battery pack. | Re-choose the battery interconnect if DigiKey-only is required; not a drop-in. |
| SW1 | "DPDT_Hirose" | Value is a placeholder; the actual switch isn't identified. Footprint is a generic 2×3 0.1″ header. | Identify the real switch (size/actuation) and I'll match a DigiKey DPDT. |
| F1, F2 | 1 A fuse, 1812 | 1 A **one-time fuses are made in 1206, not 1812** — DigiKey has no clean 1 A/1812 chip fuse. | Either drop to an 1812-footprint PTC (resettable, common for battery input) or change the footprint to 1206 and use Bel Fuse `0685T1000-01` ([5923-0685T1000-01CT-ND](https://www.digikey.com/en/products/detail/bel-fuse-inc/0685T1000-01/4968263), 1 A 1206). |
| J1, J10 | Conn_01x02 (1.00 mm pitch) | Footprint is a project-custom 1.00 mm socket (`PinSocket_1x02_P1.00mm_Vertical_CUSTOM_CYD`); exact mating part unclear. | Confirm the intended 1.00 mm 2-pos socket/mate, then match a DigiKey part (Molex/JST/Harwin 1.0 mm families). |

---

## 3. Board features — no part to order

These appear in the netlist but are PCB artwork, not purchasable components:

- **Test points** TP1-TP36, TP40-TP44, TP47, TP48 (43×) — copper pads.
- **Mounting holes** H1-H5 (5×) — plated pads/vias.
- **Net-tie** NT1 — copper join.
- **Solder jumpers** JP1, JP2 — bare-copper jumper pads.

---

### Verification notes
- All Part Status values read **Active** except **Q2** (obsolete) and where noted.
- Stock figures are DigiKey-direct at time of check and move constantly — the
  link is the source of truth.
- Passive MPNs are concrete, in-stock choices matching the schematic value +
  footprint; any same-value/same-size/same-rating part is interchangeable.
