# 2026-10-07 — TBPS compiler (ROM-faithful), toolchain (disasm/load/upload/readback/debug/native), keypad-typing + persistence RE, ucSim download-crash fix

A large session that built a **ROM-faithful TBPS compiler** (the ROB3 Teach Box
Programming System language) as a proper Python project, then grew a full
toolchain around it — all **verified against the real ROM in ucSim** — plus
several firmware reverse-engineering results and a ucSim bug fix.

## New in-repo project: `tools/tbps-compiler/`

A pip-installable package (`tbpsc` CLI) that compiles TBPS source to the exact
bytes the firmware interprets from its SRAM program store. Every opcode is
derived from and verified against the ROM (`firmware/src/annotated/program.asm`,
`rs232.asm`) — unlike the earlier ad-hoc `hardware/teachbox/tbps_compiler.py`
(fabricated opcodes), now **removed**.

- `isa.py` — authoritative, provenance-tagged encoding; `lexer.py` / `parser.py`
  (AST + range checks) / `codegen.py` (8-byte slots + page-0x80 label table).
- `disasm.py` — program bytes → TBPS source (round-trips).
- `simload.py` — `load_program` (direct xram), `upload_program` (RS-232 `0x81`
  block), `read_program`/`trigger_readback` (RS-232 `0x80` download).
- `debug.py` — `TbpsDebugger`: single-step a stored program **one TBPS
  instruction at a time** through the firmware interpreter (`prog_exec`).
- `native.py` — AOT backend: TBPS → **native MCS-51 (sdas8051) assembly**,
  hosted mode (reuses the firmware RAM map + `dout_write` 0x07D0).
- CLI: compile / `--hex` / `--label-table` / `--disasm` / `--trace` / `--native`
  / `--version`. Editor support: Vim + nano syntax highlighting (`editors/`).
- Tests: encoding, corner-cases, CLI, disasm, native, and ucSim-verification —
  all pass (one main-loop self-run skips without the loopback-reachable init).
- Formal spec `docs/TBPS_LANGUAGE.md` (grammar, ranges, verified byte encoding,
  corner-case semantics, upload protocol).

### Verified TBPS program byte encoding [SIM]
8-byte slots; `MARK=0x1F`, `POS a.n = 0x60+axis` (MOVE: writes `target[0x40+axis]`,
arms motion — corrected from an initial wrong `0x00+axis`, cross-checked against
`demo_hello_program.sh` and live), `TIM=0x18` (lo,hi), `OUT=0x10+(k-1)&3`
(`dout_write(A=opcode&3, R0=operand)`), `GOTO=0x30`/`IF=0x20` (label table),
`END`=bit7, `STOP 0`/`CLR` emit no byte. Operand ordering for GOTO/IF partly
[INFER].

### Program load/run/readback — all three paths verified [SIM]
- **Direct SRAM load** → `prog_exec` runs it (OUT→portb_write + 8-byte advance;
  TIM operand; POS→target).
- **RS-232 `0x81` upload → run** end-to-end: frame = `0x81`, ptr=len, count=0,
  bytes + `0x83` sentinel; firmware stores to 0x8100 byte-exact, sets
  program-loaded `0x28.1`, and the uploaded `POS 1 . 128` executes
  (target[0]=0x80).
- **RS-232 `0x80` readback** triggers `sys_readprog` (0x03C9): TX stream from
  SRAM, pointer `0x30:0x31`=0x80FD, length header+4.
- **Garbage upload** without a valid `0x83` is NOT marked loaded and runs safely
  (bit7 byte → END branch); malformed header → preprocessor bails to `prog_end`.

### TBPS source-level stepping + native equivalence [SIM]
- `tbpsc --trace` single-steps a program through the ROM (decoded instruction +
  PC advance + axis targets + state per step).
- `tbpsc --native` emits 8051 asm; running it in ucSim leaves the **same**
  firmware state (axis targets + dout shadow) as the interpreter — equivalence
  test passes.

## Firmware reverse-engineering results (annotated + skill updated)

### Teachbox PROGRAM TYPING works [SIM]
Typing `MARK 0 ENT` on the keypad (real scan→debounce→handle→store, unblocked by
the loopback module) stores opcode `0x1F` at 0x8100 and advances the program PC
one 8-byte slot. Store path = `kbd_handle`→`0x0DA5` (`mov DPL,0x66 / DPH,0x67 /
movx @DPTR,A`). Key index = `row+1 + (group−1)×8`; **ENT = (row 5, group 2)**
(index 0x0E) — this corrects `board.md`'s mislabelled "/Y5 grp1" ENT cell.
Annotated in `teachbox.asm`; `rob3-firmware-map` skill updated. Scaffold:
`simulator/tests/test_teachbox_typing.py`. (Per-instruction operand/commit
sequences for OUT/TIM/GOTO/IF and the STOP-header state still [INFER].)

### Program persistence across power-off [SIM]+[HW-doc]
Programs live in battery-backed external SRAM (page 0x80 = 0x8000–0x9FFF),
retained ~10 years (Teachbox manual). Verified: xram program survives a ucSim
`reset` and still executes afterward. At boot, init re-probes the SRAM (0x0639,
complement write/readback at 0x8000), records the page in `0x3E`=0x80/`0x3F`=0x81,
and an 8-byte header check keeps/clears `0x28.1`. Clarified **0x58 ≠ program
store**: the `MOV DPH,#0x58` at 0x0678 is the **ADC** device window, not NVRAM —
`board.md`'s "5800H" claim is stale. Recorded in the firmware-map skill.

### ucSim `reset` vs RAM
`cl_51core::reset()` only resets SFRs/PC (never clears iram/xram) — faithful to a
real 8051 warm reset. Modelling a cold power cycle = clear IRAM explicitly, keep
xram (battery-backed). No ucSim change needed.

## ucSim bug fixed: `download` segfault (issue 005)

The `download` command built an empty `cl_inspec("", this)`; the constructor
never initialized `mem` and `init()` early-returned before `mem = uc->rom`, so a
data record dereferenced a wild pointer in `set_rom` (`uc.cc:1489`, SIGSEGV).
**Fixed** in `src/core/sim.src/uc.cc` (init `mem` in the ctor + on the empty-spec
path); rebuilt and verified the repro now loads cleanly. Documented as
`simulator/issues/005-download-segfault-empty-inspec-mem/` (README + patch +
repro) and indexed.

## Docs / housekeeping
- `hardware/teachbox/SOURCES.md` marks `teachbox.md` (owner-maintained, renamed
  from README.md + extended) and `tbps.md` (verbatim PDF extraction) **read-only**
  for tooling; lists derived/editable files.
- `hardware/teachbox/hello_world.{txt→tbps}` cleaned (compiles with `tbpsc`;
  fixed the wrong "TIM 50 = 0.5 s" comment → 5 s) and renamed to the primary
  source extension.
- **File-extension convention** settled: **`.tbps`** primary source, **`.dat`**
  alias (the original TBPS convention — TBINIT's example `TB.CNF` extension),
  **`.ACT`** = compiled program (original Teach Box binary format). Applied
  across the CLI help, Vim `ftdetect` + nano syntax (`.tbps`/`.tb`/`.dat`),
  `docs/TBPS_LANGUAGE.md` (File extensions table), and the README. Vim/nano
  highlighting loading + verification documented and headless-tested.
- `hardware/host/command.md`: stored-program instruction encoding upgraded from
  [INFER] to a [SIM] table.
- The old `hardware/teachbox/tbps_compiler.py` + `program_loader.py` (fabricated
  opcodes/handshake) removed; superseded by `tools/tbps-compiler`.

## Provenance
Byte encoding, 8-byte slot, label table, upload/readback/typing/persistence, and
native equivalence are [BYTE]/[SIM] against the project's own `ucsim_51` build
and ROM; GOTO/IF operand ordering and the keypad per-instruction commit
sequences remain [INFER].
