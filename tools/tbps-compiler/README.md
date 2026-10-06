# tbps-compiler

A **ROM-faithful compiler** for the ROB3 *Teach Box Programming System* (TBPS)
language. It turns TBPS source (the same instruction set the Teach Box keypad
produces — `MARK`, `POS`, `TIM`, `GOTO`, `IF`, `OUT`, …) into the exact bytes
the ROB3 8031 firmware interprets from its external SRAM program store.

Unlike the earlier ad-hoc script in `hardware/teachbox/`, every opcode here is
**derived from and verified against the ROM** (`firmware/src/annotated/program.asm`,
`rs232.asm`) and the real firmware running in ucSim.

## Why the earlier ad-hoc compiler was replaced

An earlier `hardware/teachbox/tbps_compiler.py` (now **removed**) had a
fabricated opcode table: it claimed `TIM=0x80`, `IF=0xC0`, `POS=0x40+axis`, and
emitted fixed **4-byte** records. The firmware actually:

- uses fixed **8-byte slots** (`prog_exec` advances `PC += 8`);
- treats any **bit7-set** opcode as program END (so `0x80`/`0xC0` are *not* TIM/IF);
- encodes `POS a . n` as the **move/target class `0x60+axis`** (writes
  `target[0x40+axis]` and arms motion);
- defines labels with **`MARK = 0x1F`**, resolved by a page-0x80 label table.

## Encoding (verified)

Full grammar, value ranges, SRAM layout, and corner-case semantics:
**[`docs/TBPS_LANGUAGE.md`](docs/TBPS_LANGUAGE.md)**.

| Instruction | Opcode | Operands (in the 8-byte slot) | Provenance |
|---|---|---|---|
| `MARK m` | `0x1F` | `m` (label; recorded in page-0x80 table) | [BYTE][SIM] |
| `POS a . n` | `0x60 + (a-1)` | `n` → `target[0x40+axis]`, arms motion | [SIM] |
| `POS` (store all) | `0x07` | 6 position bytes | [INFER] |
| `TIM t` | `0x18` | `t` lo, `t` hi → `0x1A/0x1B` | [BYTE] reads |
| `OUT k +/-` | `0x10 + (k-1)&3` | state (`+`=0x00 LOW, `-`=0x01 HIGH) | [BYTE] reads / [INFER] |
| `GOTO m [. n]` | `0x30` | `m`, `n` (count; 0 = endless) | [INFER] |
| `IF i [. m]` | `0x20` | input mask `1<<(i-1)`, `m` | [INFER] |
| `INS .` (END) | `0x80` | — | [BYTE] |
| `DEL .` (HALT) | `0x36` | 3-byte special | [BYTE] / [INFER] meaning |
| `STOP 0`, `CLR` | — | header / mode-change: no stored byte | [BYTE] |

Program store layout (external HM6264 SRAM, `xram` in ucSim):
`0x8000` page = label table (2 bytes LE PC per label at `2*m`),
`0x8100`+ = program body in 8-byte slots. PC = IRAM `0x66:0x67`.

Provenance tags: `[BYTE]` ROM-exact, `[SIM]` observed in ucSim, `[INFER]`
hypothesis (per-opcode operand ordering for TIM/OUT/GOTO/IF is partly inferred,
as the firmware annotations themselves tag it).

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Use

```bash
# compile to a hex dump on stdout
tbpsc program.tbps --hex

# write the program body (8-byte slots) as raw bytes
tbpsc program.tbps -o program.bin

# prepend the page-0x80 label table (full SRAM image, 0x8000..)
tbpsc program.tbps --label-table -o program.sram
```

```python
from tbps_compiler import compile_source

prog = compile_source(open("program.tbps").read(), raise_on_error=True)
prog.body_bytes()          # 8-byte-slot program body (loads at 0x8100)
prog.label_table_bytes()   # page-0x80 label table
prog.sram_writes()         # [(xram_addr, byte), ...] for loading into a sim
```

## Writing programs

A `.tbps` source is one instruction per line (the Teach Box key sequence,
`ENT` optional), with `;` or `#` line comments:

```tbps
STOP 0            ; clear memory, make header (emits no stored byte)
MARK 0            ; program start label
POS 1 . 128       ; move axis 1 to position 128
OUT 1 +           ; set output 1 LOW
TIM 50            ; wait 5 s (50 x 100 ms)
GOTO 0            ; loop forever
INS .             ; program end
```

Compiler-enforced rules (see `docs/TBPS_LANGUAGE.md` §5 for the runtime reason
behind each): labels `0..118` and single-definition; `GOTO`/`IF` must target a
**defined** label; axis `1..6`, ports `1..8`, position `0..255` (gripper
`0..100`); the body must fit the SRAM store. Multiple programs may be
concatenated, separated by `DEL .` (HALT), sharing one label namespace.

### Native 8051 backend (AOT)

Besides the bytecode (interpreted by the firmware), the compiler can emit
**native MCS-51 assembly** that performs each TBPS instruction's effect directly
— an ahead-of-time alternative to the interpreter.

```bash
tbpsc program.tbps --native            # sdas8051 asm to stdout
tbpsc program.tbps --native --org 0x2000 -o prog.asm
```

Mode is **hosted/subroutine**: the emitted code reuses the running firmware's
RAM map (axis targets `0x40+`, motion masks `0x2B`/`0x2C`, the digital-out
shadow `0x1F`) and the `dout_write` helper at `0x07D0`, mirroring exactly what
`prog_exec` does per instruction:

| TBPS | Native |
|---|---|
| `POS a . n` | `mov target[0x40+a],#n` + `orl` motion masks |
| `OUT k ±` | `mov R0,#operand ; mov A,#op ; lcall 0x07D0` |
| `TIM t` | load `0x1A/0x1B` + spin |
| `GOTO m` / `GOTO m . n` | `ljmp Lm` / counted `djnz` |
| `IF i [. m]` | poll/branch on the P1 input bit |
| `MARK m` / `INS .` | label / `ret` |

**Verified:** running the native code in ucSim leaves the **same firmware state**
(axis targets + digital-out shadow) as running the bytecode through the
interpreter — see `tests/test_native.py::test_native_equivalent_to_interpreter`.

> Note: native code runs from the **code-fetch space** (EPROM/0x0000–0x1FFF on
> real HW). It is useful for generating an 8051 program / a new ROM image or for
> running in the simulator's code space; it does **not** drop into the SRAM
> program store (which isn't in the code-fetch window). Needs `sdas8051`/`sdld`
> to assemble.

## Debugging / stepping
TBPS programs can be **single-stepped through the real ROM** in ucSim — one TBPS
instruction at a time (not one 8051 machine instruction). Each step re-enters the
firmware interpreter (`prog_exec`), runs exactly one program instruction, and
reports the decoded TBPS instruction, the program PC advance, the axis target
table, and the program-state byte.

CLI (needs `UCSIM_51` + `ROB3_HEX` and the `rob3_ucsim` package):

```bash
tbpsc program.tbps --trace
#  #1   0x8100: MARK 0        -> PC 0x8108  targets=[..]  0x28=0x0e
#  #2   0x8108: POS 1 . 128   -> PC 0x8110  targets=[80 ..]  0x28=0x0e
#  ...
#  #N   0x81..: INS .         -> ...  [END]
```

API:

```python
from tbps_compiler import compile_source
from tbps_compiler.simload import load_program
from tbps_compiler.debug import TbpsDebugger

prog = compile_source(src, raise_on_error=True)
load_program(eng, prog)                 # eng = rob3_ucsim/pyucsim engine
dbg = TbpsDebugger(eng, prog)
dbg.reset_to(prog.pc_of_label(0))
frame = dbg.step()        # execute one TBPS instruction
print(frame.text, frame.pc_after, frame.targets, frame.ended)
```

Lower level, you can still use ucSim breakpoints on the interpreter directly
(`prog_exec` 0x0941, the per-instruction `RET` 0x0A0B, the END branch 0x0950).

## Editor support
### Vim / Neovim syntax highlighting

Syntax + filetype files for `.tbps` (and `.tb`) live in `editors/vim/`.

Install (classic Vim):

```bash
mkdir -p ~/.vim/syntax ~/.vim/ftdetect
cp editors/vim/syntax/tbps.vim    ~/.vim/syntax/
cp editors/vim/ftdetect/tbps.vim  ~/.vim/ftdetect/
```

Neovim:

```bash
mkdir -p ~/.config/nvim/syntax ~/.config/nvim/ftdetect
cp editors/vim/syntax/tbps.vim    ~/.config/nvim/syntax/
cp editors/vim/ftdetect/tbps.vim  ~/.config/nvim/ftdetect/
```

Or add the directory to your `runtimepath` directly:

```vim
set rtp^=/path/to/rob3/tools/tbps-compiler/editors/vim
```

Highlights instructions (`MARK`/`POS`/`TIM`/`GOTO`/`IF`/`OUT`/`NOP`),
structure commands (`STOP`/`INS`/`DEL`/`CLR`), `ENT`, `+`/`-` operators, the
`.` separator, decimal/hex numbers, and `;`/`#` comments.

### GNU nano syntax highlighting

A nano syntax file is in `editors/nano/tbps.nanorc`. Add this line to your
`~/.nanorc`:

```
include "/path/to/rob3/tools/tbps-compiler/editors/nano/tbps.nanorc"
```

(Or copy it into nano's include dir, e.g. `/usr/share/nano/` or
`~/.nano/`.) It activates for `*.tbps` / `*.tb` files and colours the same token
classes as the Vim definition.

## Documentation map

| Doc | Scope |
|:----|:------|
| `docs/TBPS_LANGUAGE.md` | **formal spec**: grammar, ranges, verified byte encoding, corner-case semantics |
| `hardware/teachbox/teachbox.md` | Teach Box **user manual** — *read-only; owner-maintained (PDF extraction, extended)* |
| `hardware/teachbox/tbps.md` | DOS **TBPS software** manual — *read-only verbatim PDF extraction* |
| `hardware/teachbox/language.md` | original grammar sketch (points here for exact bytes) |
| `hardware/host/command.md` | RS-232 protocol incl. the `0x81` program-upload path |

> `teachbox.md` and `tbps.md` are owner-maintained manual docs — **do not edit
> them** (see `hardware/teachbox/SOURCES.md`). Record corrections in derived
> docs and cite the manual.

> A separate "programming guide" is **not** needed: the teaching material lives
> in `teachbox.md` (worked PROGRAM 1–4) and `tbps.md` (per-instruction
> reference); the formal/byte layer lives in `TBPS_LANGUAGE.md`. This section
> is the compiler-specific bridge between them.

## Tests

```bash
# unit tests only (no simulator needed)
.venv/bin/pytest tests/test_encoding.py

# + ucSim verification against the real ROM (needs the project's ucsim build)
export UCSIM_51=/path/to/ucsim/src/sims/s51.src/ucsim_51
export ROB3_HEX=/path/to/rob3/firmware/hex/M2764A@DIP28.HEX
.venv/bin/pytest
```

The ucSim tests (`tests/test_sim_ucsim.py`, built on `rob3_ucsim`/`pyucsim`)
load a compiled program into the simulator and run the firmware's own
interpreter (`prog_exec`, 0x0941) on it, asserting:

- `OUT` decodes to the Port-B writer and the PC advances by one 8-byte slot;
- `TIM`'s operand reaches the delay-store handler (`0x09E6`) in `ACC`;
- `POS a . n` writes the axis target (`target[0x40+axis]`).

Both load paths the user can use are covered: **direct SRAM load** (`set mem`)
and **RS-232 `0x81` block upload** framing.

## Status

- Unit + corner-case + CLI tests + ucSim verification tests pass; 1
  self-run-from-main-loop test skips unless the firmware init reaches the main
  loop (loopback module / pin gates — firmware-init territory, covered by the
  firmware repo's own `simulator/tests/demo_hello_program.sh`).

### Verified program-input paths

The compiler produces the program **bytes**; getting those bytes into the robot
has been verified against the ROM for:

- **Direct SRAM load** — bytes written to xram, run by `prog_exec` ✓ [SIM]
- **RS-232 `0x81` upload** — firmware stores to SRAM, marks loaded, runs ✓ [SIM]
- **RS-232 readback (`0x80`)** — firmware streams the stored program back ✓ [SIM]

**Not covered (out of scope — firmware RE gap):** *typing a program on the
Teachbox keypad.* The keypad **position-teaching** path (axis-select, +/- jog,
`POS a . n` digit entry → axis slot) is `[SIM]`-verified in the firmware repo,
but the **instruction-key → stored-program** path (pressing `MARK`/`GOTO`/`IF`/
`OUT`/`TIM` to build the SRAM program body) is **not yet reverse-engineered**
(the firmware annotations flag those key handlers `[INFER]`). This is a firmware
subsystem independent of the compiler; see
`firmware/src/annotated/teachbox.asm` and the `rob3-firmware-map` skill.
