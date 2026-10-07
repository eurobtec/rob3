# ROB3 Firmware Reverse-Engineering

Reverse-engineering and documenting the onboard firmware of the **ROB3**, a
6-axis industrial robot whose controller is built around an **Intel 8031**
(MCS-51) running from an 8 KB **M2764A** EPROM. The goal is to recover and
faithfully document the *original* firmware behavior — verified against the ROM,
a simulator, and the hardware — rather than to redesign the system.

The original controller is a ROM-less 8031 plus an 8255 PPI, a 74LS138 address
decoder, an ADC0808/0809, and L293 H-bridges driving six DC-servo axes with
potentiometric position feedback.

## Status

What exists in this repository today:

- **Assembling 1:1 annotated disassembly** — the entire 8 KB ROM reassembled
  from 10 annotated `.asm` region files + 7 `inc/*.inc` equate files, with
  output **byte-identical** to the original EPROM
  (SHA-256 `1e94419d…`). Every instruction carries the raw bytes and a
  provenance tag; `system.inc` is the authoritative IRAM/flag-bit map.
- **Two-layer verification** — a *golden byte-match* (`make verify` in
  `firmware/src`: whole-image `cmp` against the ROM; all 10 regions also pass
  standalone via `make status`) plus *behavioral ucSim tests* (the real ROM run
  in `s51` with runtime state asserted). The behavioral test rig lives in its
  own repository, [eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim)
  (`simulator/`), and runs against any ROB3 ROM image (`ROB3_HEX`).
- **Reverse-engineered host serial protocol** — the RS-232 binary command set
  confirmed against the ROM (hidden digital-input-read commands found), the
  startup handshake (0x15/0xF1 reply semantics), and the stored-program
  interpreter + a "hello world" program, all `[SIM]`-verified.
- **Python protocol library** — the ROB3 RS-232 low-level protocol as a
  ROS-independent, pip-installable package (wire-protocol codec, serial
  transport, joint↔count calibration, a high-level `Rob3Client`, a byte-level
  fake robot, and a `rob3-teleop` example). Bytes verified against the ROM in
  ucSim. **Its own repository:**
  [eurobtec/rob3_py](https://github.com/eurobtec/rob3_py).
- **Python ROS 2 driver** — a UR-driver-style package built on `rob3_py`
  (JointState / FollowJointTrajectory / JointJog teleop / Trigger services,
  URDF/launch, Docker + RViz). Verified end-to-end against the ROM in ucSim.
  **Its own repository:**
  [eurobtec/rob3_ros2_driver](https://github.com/eurobtec/rob3_ros2_driver)
  (see `simulator/USING_UCSIM_MCP.md` for how it ties back to this firmware).
- **Hardware reference docs** for every board IC, plus compiled **ucSim
  peripheral modules** (`cl_hw`: teachbox, adc, loopback, rxd) for
  closer-to-real simulation — including a pin-level auto-baud driver.
- **ucSim simulation rig** — the ROB3-aware ucSim driver (`UCSimEngine` +
  firmware landmarks, `Plant` motor/pot model) built on the generic
  [pyucsim](https://github.com/eurobtec/pyucsim) client, plus the behavioral
  `simulator/` test rig (ucSim tests + `cl_hw` peripheral modules: teachbox /
  adc / loopback / rxd) that runs *this* ROM and reads back its state. The rig
  takes the ROM as an input (`ROB3_HEX`), so it works against any image. **Its
  own repository:** [eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim)
  (see its `simulator/USING_UCSIM_MCP.md` for how it ties back to this firmware).
- **TBPS compiler toolchain** — a ROM-faithful compiler, disassembler,
  source-level debugger, and native-8051 backend for the **Teach Box
  Programming System** language the robot runs from its SRAM program store.
  Every opcode is `[SIM]`-verified against this ROM in ucSim (direct SRAM load,
  RS-232 `0x81` upload-and-run, `0x80` readback, and native==interpreter
  equivalence). **Its own repository:**
  [eurobtec/tbps_compiler](https://github.com/eurobtec/tbps_compiler) (the
  interpreter equates `firmware/src/inc/tbps_isa.inc` stay here; the
  keypad-typing test `simulator/tests/test_teachbox_typing.py` lives in
  [eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim)).
- **Arduino bench bring-up rigs** that recreate the teachbox and a single robot
  axis to confirm hardware claims independently of the 8031.
- **Domain skills & steering** under `.kiro/` capturing the MCS-51 / ucSim /
  Arduino know-how and ROB3-specific maps.

> **C conversion is not started.** The original project charter
> ([`ROB3_FIRMWARE_REENGINEERING.md`](ROB3_FIRMWARE_REENGINEERING.md)) targets a
> C rewrite with SDCC; the current reality is annotated assembly + verification
> + documentation. The `mcs51-c-programming` skill and the charter capture the
> intended approach for when that work begins.

## Progress

For the chronological milestone-by-milestone history (with links to every dated
session log), see [`sessions/README.md`](sessions/README.md).

## Repository layout

```
rob3/
├── README.md                         # this file
├── ROB3_FIRMWARE_REENGINEERING.md    # project charter: goals, scope, success criteria
├── LICENSE
├── firmware/                         # the firmware itself (ROM + disassembly + annotations)
│   ├── src/                           #   assembling 1:1 annotated source (rob3.asm + *.asm + inc/*.inc + Makefile)
│   ├── legacy/                        #   originals: bin/ hex/ (ROM image) + src/main.asm (raw disasm)
│   ├── INSTALL.md                     #   toolchain prerequisites
│   #  (the behavioral ucSim test rig + cl_hw modules live in eurobtec/rob3_ucsim)
├── hardware/                         # board reverse-engineering
│   ├── board/                         #   per-chip docs (8031, 8255, 74LS138, EPROM, SRAM, ADC, L293, ...)
│   ├── teachbox/  motors/  connectors/#   subsystem docs + Arduino bring-up sketches
├── docs/                             # derived analysis
│   ├── reverse_engineering_notes.md   #   firmware map, ISRs, protocol, function table
│   ├── 8031_sfr_map.md  8255_mapping.md
│   └── axis_state_machine.md
├── sessions/                         # dated work logs
└── .kiro/                            # skills + steering (domain knowledge for agents)
```

## Quickstart

Install the toolchain (SDCC `sdas8051`/`sdld`, ucSim `s51`, binutils, make,
python3) — see [`firmware/INSTALL.md`](firmware/INSTALL.md) for per-OS steps.

```bash
# Golden byte-match: assembled transcription == ROM (prints SHA-256)
cd firmware/src
make verify     # whole-image cmp against the ROM
make status     # all 10 regions pass standalone
```

Behavioral ucSim tests (run the real ROM and assert state) live in the
[eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim) repo and take the
ROM as an input:

```bash
# in a rob3_ucsim checkout:
cd simulator
make test ROB3_HEX=<path-to>/firmware/legacy/hex/M2764A@DIP28.HEX
```

> **ucSim `@`-filename gotcha:** the shipped ROM is `firmware/legacy/hex/M2764A@DIP28.HEX`, and
> the `@` crashes `s51` (it parses `file@memoryspace`). The rig copies the
> image to a shell-safe `simulator/build/rob3.hex` automatically — you never
> need to rename anything by hand.

## Hardware at a glance

| Part | Role |
| :--- | :--- |
| Intel **8031** | ROM-less MCS-51 CPU; boots the external EPROM via `PSEN` |
| **M2764A** EPROM (8 KB) | program store (`0x0000–0x1FFF`) |
| **HM6264** SRAM (8 KB) | data workspace / stack / robot-program storage |
| **8255** PPI | parallel I/O: motor direction/enable (Ports A/C) + digital I/O (Port B) |
| **74LS138** | address decoder → device selects (`DPH` picks the MOVX window) |
| **74HC373** | address latch (AD0–7 off the multiplexed P0 bus) |
| **ADC0808/0809** | 8-ch ADC reading the axis feedback pots; EOC → INT1 |
| **L293** ×3 | H-bridges driving six DC-servo motors |

### Axis / joint reference

| Axis | Joint | Symbol | Range | Resolution |
| :--- | :---- | :----- | :---- | :--------- |
| 0 | Base rotation | q1 | +80° … −80° | 0–255 |
| 1 | Shoulder | q2 | +70° … −30° | 0–255 |
| 2 | Elbow | q3 | 0° … −100° | 0–255 |
| 3 | Wrist pitch | q4 | +100° … −100° | 0–255 |
| 4 | Wrist roll | q5 | +100° … −100° | 0–255 |
| 5 | Gripper | — | 0–60 mm | 0–255 |

Positions are 8-bit. The firmware numbers axes from 0; original robot
documentation numbers them from 1.

## How claims are verified (provenance)

Every firmware statement in the docs and annotations is tagged with how it was
established, and unproven claims are kept separate from verified ones:

- **[BYTE]** — verified from the ROM bytes (byte-exact / golden match)
- **[SIM]** — verified by running the ROM in ucSim and observing state
- **[HW]** — confirmed against a hardware doc or an Arduino bench bring-up
- **[INFER]** — hypothesis, not yet proven (never stated as fact)

## Documentation & skills

- **Charter / full spec:** [`ROB3_FIRMWARE_REENGINEERING.md`](ROB3_FIRMWARE_REENGINEERING.md)
- **Firmware build & tests:** [`firmware/INSTALL.md`](firmware/INSTALL.md) (golden match in `firmware/src`); behavioral ucSim tests in [eurobtec/rob3_ucsim](https://github.com/eurobtec/rob3_ucsim)
- **Analysis docs:** [`docs/`](docs/) — RE notes, SFR/8255 maps, axis state machine
- **Hardware docs:** [`hardware/`](hardware/) — per-chip board reference, teachbox, motors, connectors
- **Agent skills:** [`.kiro/skills/`](.kiro/skills/) — generic (`mcs51-assembly`,
  `mcs51-c-programming`, `mcs51-debugging`, `ucsim`, `arduino-hardware-bringup`)
  and ROB3-specific (`rob3-hardware`, `rob3-firmware-map`, `rob3-firmware-sim`,
  `rob3-arduino-bringup`)

## License

See [`LICENSE`](LICENSE).
