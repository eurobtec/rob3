# Session: ROB3 — DB9 pinout completed; shorting-connector analysis reconciled

**Date:** 2026-10-06
**Task:** The user had hand-added a complete DB9 (FB9) pinout to the RS-232 docs
and asked to (1) review it for consistency against the per-chip board docs, and
(2) nail down what the ROB3 "9-pin shorting connector" actually is. This builds
directly on the 2026-09-16 shorting-connector trace, which left the pin-4
pull-up-vs-pulldown question open and several DB9 pins marked "probe it".

Working method: verify against ROM/board docs before asserting; keep the
`[BYTE]`/`[SIM]`/`[HW]`/`[INFER]` provenance. This session involved **several
self-corrections driven by the user's bench knowledge** — the honest trail is
preserved in the commit history rather than silently rewritten.

## Commits (this session, on `main`, pushed)

- `49dea86` complete DB9 pinout + reconcile RS-232 shorting-connector analysis
- `2e542e5` confirm M34004 pin 14 (OUT4) → DB9 pin 5 (first "GND reference" take)
- `f1e04ca` correct DB9 pin 5 — driven M34004 OUT4 (P3.5/T1), not system GND
- `a85a142` correct DB9 pin 5 **again** — it IS Signal Ground (~0 V), buffered by OUT4
- `0ce14d7` lock DB9 pins 6/7/8 = n/c, pin 9 cut; add shorting-connector build summary
- `912e63c` clarify `loopback` is the shorting-connector stand-in (proves end-state, not wiring)
- `747d471` document why a wiring-accurate shorting-connector sim is deferred
- `927c02a` DB9 pin 1 is GND (revert my earlier "unknown" regression)
- _(this log)_

## 1. DB9 pinout — now complete and consistent  [HW-doc]

Reviewed the user's additions and reconciled `rs232.md`, `board/MM74C04N.md`,
`board/M34004.md` into one agreeing map:

| DB9 | Board connection | Role |
| :-- | :--------------- | :--- |
| 1 | **GND** | ground (same net as pin 5) |
| 2 | MM74C04N #1 IN6 (10k series, 100k pulldown) → P3.0/RXD | serial RX / baud strap |
| 3 | M34004 OUT1 ← robot TXD | serial TX (driver OUTPUT — never short) |
| 4 | MM74C04N #1 IN4 (10k series, 100k pulldown) → P3.4/T0 | teach-poll gate |
| 5 | **Signal GND (≈0 V)**, buffered by M34004 OUT4 | ground reference |
| 6/7/8 | **not connected** (confirmed by user) | dead |
| 9 | M34004 ref (pins 3/12) via 22k — **connected but CUT on the PCB** | dead |

Fixed a pin 2/3 **label swap** in the user's summary table (pin 2 feeds IN6, an
input; pin 3 is fed by OUT1, a driver output — the summary had them crossed).

## 2. DB9 pin 5 / M34004 pin 14 — three takes before it was right

A genuinely instructive back-and-forth, settled by the user's hardware facts:

1. First flagged "pin 14 (OUTPUT 4) → DB9 pin 5" as a **mis-trace** (an op-amp
   output can't be ground). User: "it is gnd" **and** "it is connected".
2. Traced channel 4: INPUT 4− (pin 13) ← 100k ← **8031 pin 15 = P3.5/T1**
   (confirmed both ways in `board/8031.md`), INPUT 4+ (pin 12) on the cut
   reference node, OUTPUT 4 (pin 14) → DB9 pin 5. Concluded it was a **driven
   ±9 V line**, not GND. [committed `f1e04ca`]
3. User's decisive objection: *"if it is not ground how can it connect to a
   normal RS-232 PC?"* — correct. On a straight cable DB9 pin 5 mates with the
   PC's 0 V. So OUTPUT 4 must sit at **≈0 V**: channel 4 is a **0 V reference /
   baseline buffer** (matches the M34004 cut-line section calling pins 3/12 the
   op-amp reference line at a 0 V baseline), presenting Signal Ground to the
   host. P3.5 being static (TMOD=0x21 uses T1 only as the baud generator; the
   ROM never writes the P3.5 bit — verified, no `0xB5` reference) fits a
   static reference-select input, not a data input. [committed `a85a142`]

**Net:** DB9 pin 5 = Signal Ground ≈0 V, **buffered by M34004 OUT4** (not a bare
GND tie). Exact pin-5 voltage marked `[INFER] ≈0 V until metered`. [BYTE: TMOD /
P3.5-never-written; HW: channel-4 wiring; INFER: 0 V until metered]

## 3. What the shorting connector looks like  [INFER, pending bench]

With pins 6/7/8 n/c, pin 9 cut, and pins 1/5 both GND, the only live pins are
**1, 2, 3, 4, 5** and **no DB9 pin carries +5 V** — so a passive plug can only
bridge among 1/2/4/5 (pin 3 is a driver output). The candidate plug is a bare
solder bridge:

```
   pin 2 (→ P3.0/RXD gate) ──┐
                             ├── ground (pin 5 and/or pin 1)
   pin 4 (→ P3.4/T0  gate) ──┘
```

Grounding pins 2/4 forces their MM74C04N inputs LOW → P3.0/P3.4 HIGH → auto-baud
path selected + teach-poll gate open. This is explicitly **NOT** the TX↔RX (2↔3)
data loopback, which was bench-tested earlier and **failed** (it never grounds
pins 2/4). Full build summary + ASCII sketch added to
`hardware/connectors/rs232-shorting-connector.md`.

**Still the same open contradiction (from 2026-09-16):** the documented 100 kΩ
*pulldowns* on IN4/IN6 say the gates idle HIGH with the port open → no plug
needed — yet the manual requires one and the bench stayed blocked. The pull-up
hypothesis is now **closed** (IN4/IN6 are not in the `resistor-pullup-array.md`
SIP list; both docs draw a pulldown), which *sharpens* rather than resolves the
contradiction. Only a bench measurement (meter P3.4/P3.0 with the port open, or
buzz out the genuine plug) can settle why the plug is required.

## 4. Simulation status: `loopback` is the stand-in (not `rxd`)

Clarified a user mix-up: the **`loopback`** cl_hw module is the
shorting-connector stand-in; **`rxd`** is the P3.0 bit-level serial driver for
auto-baud (unrelated to the teachbox gates). Documented precisely:

- ✅ `[SIM]` proven: forcing P3.2+P3.4 HIGH → ROM reaches `tb_poll` (keypad scans).
- ❌ NOT proven: that the candidate DB9 2,4→GND wiring produces that end-state —
  `loopback` drives the 8031 pins directly, bypassing the MM74C04N inversion.
- ⚠ `loopback` also forces P3.2, but P3.2 is the **DB25 STOP line**, not the DB9
  — a sim convenience, not connector behavior.

Decided (user chose option 1) to **keep `loopback` and defer** a wiring-accurate
`shorting_connector` module, with the rationale recorded in the doc: it can't
replace `loopback` (P3.2 isn't on the DB9), it would only re-confirm "the plug
is a no-op" under the documented pulldowns, and it can't reproduce the real
"blocked" symptom (which lives in the physical resistors). The decisive next
step is a bench measurement, not more simulation.

## Files changed

- `hardware/connectors/rs232.md` (pin 2/3 labels, pin 5 note, pins 6/7/8/9, pin 1)
- `hardware/connectors/rs232-shorting-connector.md` (pin-5 correction, trace table,
  build summary + ASCII plug, simulation-status + deferred-module notes)
- `hardware/board/M34004.md` (pin 14 → DB9 pin 5 derivation, cleanup)
- `hardware/board/MM74C04N.md` (IN4 / pin-9 node tidy)

## Open / next

- **Bench measurement** to resolve why a plug is required when the documented
  pulldowns say the gates idle HIGH: meter 8031 P3.4 (pin 14) and P3.0 (pin 10)
  with the RS-232 port empty after RESET; metering DB9 pin 5 ≈0 V to confirm the
  OUT4 reference buffer. [INFER → HW]
- **Buzz out the genuine ROB3 shorting plug** pin-to-pin — ends the strap-map
  ambiguity directly.
- If the measured topology differs from the docs, build a wiring-accurate
  `shorting_connector` cl_hw module on the *measured* resistors.
