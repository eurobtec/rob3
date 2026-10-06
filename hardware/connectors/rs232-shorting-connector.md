# RS-232 Shorting Connector (9-pin)

The ROB3i manual lists a **"9-pin shorting connector"** as a hardware
requirement, plugged into the **RS-232 (DB9) port** whenever the robot is run
standalone with the Teachbox (`../teachbox/README.md`, "Hardware
Installation"):

> Plug the Teachbox's 25-pin male connector into the I/O port and the 9-pin
> shorting connector into the RS-232 port.

The manual states the *requirement* but **not the wiring**. This document
derives the wiring from the board reverse-engineering and — importantly —
distinguishes what is verified from what is still inferred.

## It is NOT an RS-232 data loopback

A commercial RS-232 loopback plug bridges the **data/handshake** lines
(TX↔RX = DB9 2↔3, and typically DTR↔DSR↔DCD = 4↔6↔1, RTS↔CTS = 7↔8). An
RS-232/422/485 adapter (e.g. the Delock part) additionally loops the
**differential pairs**, which do not exist on this DB9 at all.

Neither of those is what the ROB3 needs. On this board the DB9 pins do **not**
carry a normal PC handshake; they are tapped straight into **MM74C04N #1**
input-conditioning nodes (`../board/MM74C04N.md`,
`../board/resistor-pullup-array.md`). So "shorting connector" here means
*a plug that forces specific conditioning nodes to a defined level*, not a plug
that echoes serial traffic. This is why a generic loopback / 422-485 adapter
does not unblock the Teachbox.

## What the DB9 pins actually connect to  [HW-doc]

From `../board/MM74C04N.md` (MM74C04N #1) and `rs232.md`:

| DB9 pin | Board node | Series R | Node pulldown | Inverter | 8031 pin | Firmware role |
| :------ | :--------- | :------- | :------------ | :------- | :------- | :------------ |
| 2 | IN 6 (pin 13) | 10 kΩ | 100 kΩ → GND | OUT 6 (pin 12) | P3.0 / RXD (pin 10) | serial RX / baud strap |
| 3 | OUT 1 of M34004 | — | — | (TX driver out) | P3.1 / TXD (pin 11) | serial TX (host RX) |
| 4 | IN 4 (pin 9) | 10 kΩ | 100 kΩ → GND | OUT 4 (pin 8) | P3.4 / T0 (pin 14) | teach-poll enable gate |
| 5 | GND | — | — | — | — | ground |

Each conditioning input (pins 2 and 4) has a **100 kΩ pulldown to GND** and a
**10 kΩ series resistor** to the DB9 pin. So:

- **DB9 pin open** → the 100 kΩ pulldown wins → inverter INPUT LOW → inverter
  OUTPUT HIGH → the 8031 pin (P3.0 / P3.4) reads **HIGH**.
- **DB9 pin driven/shorted HIGH** → inverter INPUT HIGH → OUTPUT LOW → the
  8031 pin reads **LOW**.

Note the polarity is **inverting**: shorting these DB9 pins HIGH pulls the
corresponding P3 gate LOW.

## The two firmware gates  [SIM][BYTE]

The firmware only reaches the Teachbox poll (`tb_poll`, 0x07C4) when two Port-3
inputs are the right level (see `../../firmware/src/annotated/main.asm`
and `../../simulator/ucsim-modules/loopback/README.md`):

1. **P3.2 / INT0 = EMERGENCY-OFF**, active LOW → must be **HIGH** to run.
   This comes from the **DB25 STOP path** (MM74C04N #1 IN 1 ← DB25 pin 4 with a
   +5V pullup), **not** from the DB9. It idles HIGH when STOP is not pressed.
   The RS-232 connector does **not** set this. [HW]
2. **P3.4 / T0 = poll enable**, must be **HIGH** to pass the gate.
   The exact instruction is at 0x07AB in `../../firmware/src/main.asm`:
   `jb 0B0h.4, jump_07C4` — **JB P3.4, tb_poll**. The scanner
   (`LCALL 0x0BFF` = kbd_scan) is called **only when P3.4 = HIGH**; if P3.4 is
   LOW the ROM skips the poll. So **P3.4 must be HIGH**. [BYTE]
   Electrically P3.4 (8031 pin 14) = OUT4 (MM74C04N #1 pin 8) = NOT(IN4),
   IN4 = pin 9 = the DB9-pin-4 node. [HW-doc]

## TRACE RESULT — full DB9 pin inventory  [HW-doc]

Traced across `rs232.md`, `../board/MM74C04N.md`, `../board/M34004.md`,
`../board/resistor-pullup-array.md`:

| DB9 pin | Connection on the ROB3 board | Usable as a strap target? |
| :------ | :--------------------------- | :------------------------ |
| 1 | (no documented connection) | unknown — probe it |
| 2 | MM74C04N #1 IN6 (10k) → P3.0/RXD | yes (serial path) |
| 3 | M34004 OUT1 ← robot TXD | it's a driver OUTPUT |
| 4 | MM74C04N #1 IN4 (10k) → P3.4/T0 poll gate | **yes — the gate of interest** |
| 5 | GND | yes (ground reference) |
| 6 | (no documented connection) | unknown — probe it |
| 7 | (no documented connection) | unknown — probe it |
| 8 | (no documented connection) | unknown — probe it |
| 9 | M34004 ref (pins 3/12) via 22k — **PHYSICALLY CUT** on this board | **no — dead** |

**Two hard conclusions from the trace:**

- **No DB9 pin carries +5V** in any board doc. Therefore a passive plug cannot
  strap DB9 pin 4 to +5V — there is no +5V source pin on this connector. Any
  "short pin 4 to VCC" idea is dead unless a bench probe finds +5V on pin
  1/6/7/8 (undocumented).
- **DB9 pin 9 is cut** — cannot be used as a strap node.

## Bench evidence so far  [HW-bench]

- A commercial **RS-232/422/485 loopback** (Delock) bridging **DB9 2↔3** was
  installed and **did NOT unblock the Teachbox**. So "short TX↔RX" (the
  `rs232.md` pins-2/3/5 theory) is **confirmed insufficient**. The 422/485
  differential pairs are meaningless on this DB9.

## Full DB9 pinout — now reconciled across all board docs  [HW-doc]

The DB9 pinout in `rs232.md` has been completed and cross-checked against
`../board/MM74C04N.md` and `../board/M34004.md`. The two conditioning inputs
(pins 2 and 4) share the **identical** network:

```text
DB9 pin 2 ──[10 kΩ]──┬── MM74C04N #1 IN 6 (chip pin 13) ──(inv)──> OUT 6 (pin 12) ─> P3.0/RXD
                     └──[100 kΩ]── GND

DB9 pin 4 ──[10 kΩ]──┬── MM74C04N #1 IN 4 (chip pin 9)  ──(inv)──> OUT 4 (pin 8)  ─> P3.4/T0
                     └──[100 kΩ]── GND
```

Both are **100 kΩ pulldown** nodes (the `resistor-pullup-array.md` SIP array
does **not** list MM74C04N #1 pin 9 or pin 13 — only pins 1/3/5 — so IN4/IN6
are NOT pulled up). The earlier "IN4 is a pull-up to +5V" hypothesis is
therefore **closed**: the pulldown is now drawn explicitly on both pins in
`rs232.md`.

## Firmware init branches on these pins  [BYTE][SIM]

Verified against the ROM (`../../firmware/src/annotated/init.asm`,
`main.asm`):

| 8031 pin | DB9 pin OPEN → level | firmware consequence |
| :------- | :------------------- | :------------------- |
| **P3.0 / RXD** | HIGH (pulldown → IN6 LOW → inv HIGH) | `jb P3_RXD,baud_detect` (`20 B0 07`) → **auto-baud path** (the only working one: arms UART with ES, starts T1). P3.0 LOW would take the fixed-baud path that never sets ES/TR1 → serial dead. |
| **P3.4 / T0** | HIGH (same inversion) | `jb P3_T0,tb_poll` (`20 B4 16`) → keypad **scanned** (gate OPEN). P3.4 LOW skips the poll. |
| **P3.2 / INT0** | HIGH (via DB25 STOP pullup, not DB9) | not emergency-off; main loop runs. |

**Consequence of the completed trace:** with the RS-232 port **empty** (all DB9
pins open), the documented wiring already yields **P3.0 HIGH + P3.4 HIGH +
P3.2 HIGH** — i.e. all three firmware gates are satisfied and the ROM reaches
`tb_poll` with no connector. The `loopback` cl_hw module reproduces exactly this
"all gates open" state and the ROM reaches the Teachbox poll from a plain
`reset; run`. [SIM]

This is the real, now-sharpened contradiction: **the documented board does not
need a shorting connector to run the Teachbox, yet the manual requires one and a
bench loopback left it blocked.** Pin 2 additionally must stay **open** so it can
carry live RXD edges for auto-baud — so the connector cannot simply DC-short
pin 2 to anything.

## Remaining ambiguity — one bench measurement settles it  [INFER]

Two internally-consistent explanations remain; both are decided by probing the
real board:

1. **Floating-input hypothesis (most likely).** The physical pulldowns are
   absent/weak, so the CMOS inputs IN4/IN6 **float** when the port is open
   (illegal for CMOS). The plug exists to **tie them to a defined level** —
   grounding pin 4 (and giving pin 2 a defined idle) via **pin 5 (GND)** — so
   the gates read deterministically. Plug = **DB9 pins 4 (and/or 2) ↔ pin 5**.
2. **Undocumented route.** P3.4 is driven LOW on the real board by a path not in
   these docs, and the plug forces it HIGH. Only a probe reveals it.

**The single measurement** (RS-232 port empty, powered, just after RESET,
meter to GND):
1. 8031 **pin 14 (P3.4)** and **pin 10 (P3.0)** — HIGH or LOW?
   - Both HIGH ⇒ docs are right, connector is for signal-integrity / defined
     idle only → safe plug is **pins 4 (±2) ↔ 5 (GND)**.
   - Either LOW ⇒ a real-board route pulls it down → the plug must drive it;
     probe for the source.
2. DB9 **pin 4** voltage — ~0 V (pulldown, docs hold) or ~+5 V (pull-up).
3. Probe DB9 **pins 1, 6, 7, 8** for any **+5V** (would enable a pin-4→VCC strap).
4. Buzz out the **genuine ROB3 shorting plug** pin-to-pin — that directly yields
   the strap map and ends the ambiguity.

**Candidate plug to build/test first (uses only documented pins, no +5V
needed):** short **DB9 pin 4 → pin 5 (GND)**, optionally **pin 2 → pin 5** too.
Note this is explicitly **not** the 2↔3 data loopback that was bench-tested and
**failed** — that plug never grounds pins 2/4, which is consistent with why it
did not unblock the Teachbox.

**Provenance:** DB9→MM74C04N/M34004 wiring, both init branches (`jb P3_RXD`,
`jb P3_T0`), and the "2↔3 doesn't work" result are **[BYTE]/[HW-doc]/[HW-bench]**;
the resulting strap (pins 4,2 ↔ 5/GND) is **[INFER]** until the measurement
above.

## How to verify on the bench

1. With NO connector, meter 8031 **pin 14 (P3.4)** and **pin 12 (P3.2)** vs VCC
   right after RESET. If both are already HIGH, the trace (P3.4 idles HIGH) is
   right and the connector's role is the serial path (option 1 above).
2. Buzz out the genuine ROB3 shorting plug pin-to-pin (which DB9 pins are tied
   together, and to any +5V). That directly yields the correct strap map.
3. Cross-check by driving each candidate strap in ucSim (see the loopback
   module) and confirming the ROM reaches `tb_poll`.

Until step 2 is done, do **not** assume a store-bought loopback (data or
422/485) reproduces the ROB3 shorting connector — the evidence so far says it
does not.
