# TBPS Language Formal Description

> **Note — authoritative spec with the verified byte encoding:**
> This document is the original grammar/semantics sketch. The **byte-level
> program encoding** (opcodes, 8-byte slots, SRAM layout) and the
> static/runtime corner-case semantics are reverse-engineered and
> **[SIM]-verified** in
> [`tools/tbps-compiler/docs/TBPS_LANGUAGE.md`](../../tools/tbps-compiler/docs/TBPS_LANGUAGE.md),
> which the `tbps-compiler` implements and tests against the ROM in ucSim.
> (The former ad-hoc `tbps_compiler.py` in this directory used a **fabricated**
> opcode table and has been removed.)
> Use this file for the language overview; use the tools/ spec for exact bytes.

## 1. Lexical Tokens and Value Ranges
*   **Keywords / Instructions:** `MARK`, `POS`, `TIM`, `GOTO`, `IF`, `OUT`, `STOP`, `INS`, `DEL`, `CLR`, `ENT`.
*   **Separators:** 
    *   `.` (Decimal point / parameter separator).
    *   ` ` (White space / visual delimiter).
*   **Operators:** `+` (Set / Positive direction), `-` (Clear / Negative direction).
*   **Identifiers / Parameters:**
    *   `m` (Label address): Integer from `0` to `118`.
    *   `a` (Axis designator): Integer from `1` to `6`.
    *   `n` (Axis position): Integer from `0` to `511` (Axes 1–5), `0` to `100` (Electric Gripper), or `0` to `1` (Pneumatic Gripper).
    *   `t` (Time delay value): Integer from `0` to `65535` (Units of 100 ms).
    *   `i` (Digital input port): Integer from `1` to `8`.
    *   `k` (Digital output port): Integer from `1` to `8`.

---

## 2. Formal Grammar Rules (EBNF Representation)

```ebnf
Program         = ProgramHeader , { Instruction } , ProgramEnd ;

ProgramHeader   = "STOP" , "0" , "ENT" , "MARK" , "0" , "ENT" , "CLR" ;
ProgramEnd      = "INS" , "." , "ENT" ;

Instruction     = MarkInst | PosInst | DirectPosInst | TimInst | 
                  GotoUncond | GotoCond | IfWait | IfJump | OutInst | HaltInst ;

MarkInst        = "MARK" , Label , "ENT" ;
PosInst         = "POS" , "ENT" ;
DirectPosInst   = "POS" , Axis , "." , Position , "ENT" ;
TimInst         = "TIM" , Delay , "ENT" ;
GotoUncond      = "GOTO" , Label , "ENT" ;
GotoCond        = "GOTO" , Label , "." , Counter , "ENT" ;
IfWait          = "IF" , InputPin , "ENT" ;
IfJump          = "IF" , InputPin , "." , Label , "ENT" ;
OutInst         = "OUT" , OutputPin , ( "+" | "-" ) , "ENT" ;
HaltInst        = "DEL" , "." , "ENT" ;

Label           = integer_0_to_118 ;
Axis            = "1" | "2" | "3" | "4" | "5" | "6" ;
Position        = integer_0_to_511 ; (* Variant constraints apply based on Axis and Gripper *)
Delay           = integer_0_to_65535 ;
Counter         = integer_0_to_255 ;
InputPin        = "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" ;
OutputPin       = "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" ;
```

---

## 3. Instruction Semantics Reference

| Instruction Syntax | Execution Semantics |
| :--- | :--- |
| **`STOP 0 ENT`** | Erases all contents of the memory buffer and creates a new program header. |
| **`MARK m ENT`** | Allocates an absolute address label index `m` at the current memory line. |
| **`POS ENT`** | Captures and records the current spatial step configurations of all 6 axes simultaneously. |
| **`POS a . n ENT`** | Instructs axis `a` to transit directly to target coordinate step profile `n`. |
| **`TIM t ENT`** | Suspends pipeline execution threads for an absolute interval computed as t × 100 ms. |
| **`GOTO m ENT`** | Executes an unconditional jump to destination address marker label `m` (Infinite loop). |
| **`GOTO m . n ENT`** | Executes a conditional loop iteration to label `m` exactly `n` times. |
| **`IF i ENT`** | Halts program sequence advancement until digital hardware input `i` registers a `LOW` logic state. |
| **`IF i . m ENT`** | Branch command. Jumps to label `m` if input `i` is `LOW`; otherwise moves to the next immediate line. |
| **`OUT k + ENT`** | Drives physical digital output register line `k` to a `LOW` state (0V / Negative TTL logic). |
| **`OUT k - ENT`** | Resets physical digital output register line `k` to a `HIGH` state (+5V / Negative TTL logic). |
| **`DEL . ENT`** | Triggers an operational program execution halt and initializes the physical `RUN` indicator lamp. |
