# TBPS — Formal Language Specification

*Teach Box Programming System* language for the ROB3 (Intel 8031 firmware).
This is the **authoritative** reference used by `tbps-compiler`: the grammar,
value ranges, and the **byte-level program encoding verified against the ROM**
(`firmware/src/annotated/program.asm`, `rs232.asm`) and in ucSim.

Provenance tags: `[BYTE]` ROM-exact · `[SIM]` observed in ucSim · `[INFER]`
hypothesis. See also the prose manual (`hardware/teachbox/README.md`) and the
original grammar sketch (`hardware/teachbox/language.md`).

---

## 1. Lexical structure

```
program    = { line } ;
line       = [ statement ] [ comment ] NEWLINE ;
comment    = ( ";" | "#" ) { any-char } ;      (* compiler extension *)
statement  = mnemonic { token } ;
token      = integer | "+" | "-" ;
mnemonic   = "STOP" | "MARK" | "POS" | "TIM" | "GOTO" | "IF"
           | "OUT" | "INS" | "DEL" | "CLR" | "." ;
integer    = decimal | "0x" hex ;
```

- Tokens are separated by whitespace and/or `.` (the Teach Box parameter
  separator); `POS 1 . 255` and `POS 1.255` are equivalent.
- `ENT` (the ENTER key) is accepted and ignored (it carries no bytes).
- Markdown code-fence lines (```` ``` ````) are ignored, so fenced examples in
  docs/`.txt` files compile unchanged.
- Mnemonics are case-insensitive.

### File extensions

| Extension | Role |
|:----------|:-----|
| **`.tbps`** | TBPS **source** — the primary, recommended extension |
| `.dat` | source **alias** — the original TBPS convention (TBINIT's example `TB.CNF` extension for control programs; the extension was user-configurable, 3 chars) |
| `.tb`, `.txt` | also accepted as source by the compiler |
| **`.ACT`** | **compiled program** — the original Teach Box binary program format (what `TBKONV` produced automatically); use for the compiled body/image when interoperating with original TBPS files |
| `.bin` / `.sram` / `.asm` | this compiler's outputs: body / full SRAM image / native 8051 asm |

The original DOS **TBPS** software stored PC-side control programs with a
user-chosen 3-character extension (TBINIT, example `dat`) and the robot/Teach
Box program files as `.ACT`. We adopt `.tbps` as the clear primary with `.dat`
as the authentic alias, and reserve `.ACT` for the compiled program.

---

## 2. Grammar (EBNF)

```ebnf
Instruction  = Header | Mark | PosStore | PosMove | Tim
             | Goto | If | Out | Nop | Halt | End | ModeClear ;

Header       = "STOP" [ "0" ] ;                 (* program header; emits no byte *)
ModeClear    = "CLR" ;                           (* mode change; emits no byte   *)
Mark         = "MARK" Label ;
PosStore     = "POS" ;                            (* store current position (all) *)
PosMove      = "POS" Axis [ "." ] Position ;      (* move axis to position         *)
Tim          = "TIM" Delay ;
Goto         = "GOTO" Label [ [ "." ] Counter ] ;
If           = "IF" InputPin [ [ "." ] Label ] ;
Out          = "OUT" OutputPin ( "+" | "-" ) ;
Nop          = "." ;
Halt         = "DEL" [ "." ] ;                    (* program separator / HALT      *)
End          = "INS" [ "." ] ;                    (* program end                   *)
```

### Value ranges

| Symbol | Meaning | Range |
|:-------|:--------|:------|
| `Label` | label index (`MARK`/`GOTO`/`IF`) | `0 … 118` |
| `Axis` | axis designator | `1 … 6` (firmware axis = Axis − 1) |
| `Position` | target step | `0 … 255`; gripper (axis 6) `0 … 100` |
| `Delay` | `TIM` value (× 100 ms) | `0 … 65535` |
| `Counter` | `GOTO` loop count | `0 … 255` |
| `InputPin` | digital input | `1 … 8` |
| `OutputPin` | digital output | `1 … 8` |

---

## 3. Program byte encoding (verified)

Programs are stored in external SRAM. Each instruction occupies a **fixed
8-byte slot**; the executor `prog_exec` (0x0941) decodes one opcode and advances
`PC += 8`. The opcode reuses the RS-232 command bit fields.

| Instruction | Opcode | Operand bytes | Effect | Prov. |
|:------------|:-------|:--------------|:-------|:------|
| `MARK m` | `0x1F` | `m` | label definition (preprocessor records PC in page-0x80 table) | [SIM] |
| `POS a . n` | `0x60 + (a−1)` | `n` | **move**: `target[0x40+axis] = n`, arms motion | [SIM] |
| `POS` | `0x07` | 6 bytes | store current position (all axes) | [INFER] |
| `TIM t` | `0x18` | `t`&0xFF, `t`>>8 | delay → IRAM `0x1A/0x1B` | [SIM] |
| `OUT k +` | `0x10 + (k−1)&3` | `0x00` | set output k LOW (active) | [SIM] |
| `OUT k −` | `0x10 + (k−1)&3` | `0x01` | clear output k HIGH | [SIM] |
| `GOTO m` | `0x34` | `m` | unconditional jump (operand[0]=label) | [SIM] |
| `GOTO m . n` | `0x36` | `m`, `n` | loop to m, n times (counted) | [SIM] |
| `IF i` | `0x32` | `m`, `1<<(i−1)` | wait until input i low | [SIM]/[BYTE] |
| `IF i . m` | `0x32` | `m`, `1<<(i−1)` | branch to m if input i low; op[0]=label, op[1]=mask; jump when `(mask & P1)==0` | [SIM]/[BYTE] |
| `INS .` | `0x80` (any bit7 set) | — | program end | [SIM] |
| `DEL .` | `0x36` | 3-byte special | HALT / program separator (**opcode collides with counted GOTO 0x36**; disambiguated by context/operands) | [BYTE] |
| `.` (NOP) | `0x40` | — | no-op | [BYTE] |
| `STOP 0`, `CLR` | — | — | header / mode change: **no stored byte** | [BYTE] |

> Branch opcodes verified [SIM]: the firmware branch handler (`prog_exec` 0x09F1
> → `L_0A0C`) is only reached for opcodes **≥ 0x32** with bit5=1, bit4=1, bit3=0
> (`add A,#0xCE ; jc`). `0x30`/`0x20` fall through and do **not** branch —
> operand[0] is always the label (resolved by `prog_goto` 0x0A33, `rl A` ×2 into
> the page-0x80 table). GOTO 0→0x8100, GOTO 2→0x8120, GOTO 5→0x8118 confirmed.

Trailing bytes in a slot are zero-padded and ignored by the executor.

### SRAM layout

| Region | Use |
|:-------|:----|
| `0x8000`–`0x80FF` (page 0x80) | **label table** — 2-byte LE PC per label at offset `2·m` |
| `0x80EE`–`0x80FF` | program **header / byte-count** + end-marker (`0x83`) |
| `0x8100`–`0x9FFF` (pages 0x81+) | program **body** — 8-byte slots; PC = IRAM `0x66:0x67` |

Program body capacity ≈ **7936 bytes** (≈ 992 slots). The store is
battery-backed / nonvolatile. Page base is in IRAM `0x3E` (= 0x80), body page in
`0x3F` (= 0x81).

---

## 4. Multiple programs in one image

Several programs may share the store, separated by `DEL .` (HALT). To reach a
program after a HALT, the caller jumps to a label at its start. **Labels are a
single global namespace** — a label may be defined only once across the whole
image (reusing a label is an error).

---

## 5. Static semantics (compiler-enforced)

The compiler rejects, at compile time:

- a label outside `0 … 118` (`MARK`/`GOTO`/`IF`);
- a duplicate label definition;
- a `GOTO`/`IF` reference to an **undefined** label (even if in range);
- an axis outside `1 … 6`, a position/gripper/delay/counter/port out of range;
- `OUT` without a `+`/`−` operator;
- a program body exceeding the SRAM capacity.

### Why these are errors (runtime consequences, [SIM]-verified)

- **Label > 118** — `prog_goto` does `rl A` (×2), so e.g. label 255 → table
  offset `0xFE`, which is the **SRAM header slot**, not a label; the jump lands
  on header garbage.
- **Undefined in-range label** — the table entry is zero, so `prog_goto` sets
  the program PC to **`0x0000`** → execution runs off outside the program store.
- **Out-of-range `OUT`** — the firmware masks the port with `anl A,#0x03`, so a
  bad port silently **aliases** onto ports 0–3.
- **Malformed / garbage program** — the preprocessor validates the header
  (low-3 bits must be 0) and the `0x83` end-sentinel; a program that fails
  **is not marked loaded (`0x28.1`)** and the executor treats any bit7-set byte
  as END, so garbage **stops safely** rather than running away.

---

## 6. Upload & run

Two equivalent ways to get a compiled program into the robot:

1. **Direct SRAM load** — write the body to `0x8100` and the label table to
   `0x8000` (e.g. `tbpsc --label-table`).
2. **RS-232 `0x81` block upload** — frame: `0x81`, pointer = payload length,
   count = `0`, program bytes, then the `0x83` stream sentinel. The firmware
   stores the bytes to SRAM via `MOVX`, verifies the sentinel, and sets
   program-loaded (`0x28.1`). *(Verified end-to-end: upload → `0x28.1` set →
   stored bytes match → `prog_exec` runs them.)*
