;==============================================================================
; ROB3 FIRMWARE — STORED-PROGRAM INTERPRETER data model
;   File: firmware/src/annotated/inc/tbps_interpreter.inc  (pairs with tbps_interpreter.asm)
;==============================================================================
;
; Stored-program (teachbox / RS-232-uploaded) interpreter workspace: the
; program page pointers, the 16-bit PC, the current-instruction descriptor, and
; the execution-control byte. Programs live in the external HM6264 SRAM
; (devices.inc DEV_SRAM, base page 0x80); the label table is page 0x80, the
; body is pages 0x81+. See inc/system.inc for the IRAM map and the 0x28 state
; flags (program-loaded/running/motion), and tbps_interpreter.asm for the executor.
;
;   Syntax: SDAS/ASxxxx (sdas8051). Addresses [BYTE]/[SIM]; opcode SEMANTICS
;   [INFER] unless a [SIM] note upgrades them.
;==============================================================================

;------------------------------------------------------------------------------
; External-SRAM program pointers
;------------------------------------------------------------------------------
PROG_PAGE       = 0x3E          ; ext-RAM program page hi (= 0x80, label table)
PROG_PAGE1      = 0x3F          ; ext-RAM program body page (= 0x81)
PC_LO           = 0x66          ; program counter (ext-RAM offset) lo
PC_HI           = 0x67          ; program counter (ext-RAM offset) hi
PROG_END_LO     = 0x76          ; program memory end pointer lo
PROG_END_HI     = 0x77          ; program memory end pointer hi

;------------------------------------------------------------------------------
; Execution control (in the 0x20..0x2F bit-addressable region)
;------------------------------------------------------------------------------
PROG_EXEC_CTRL  = 0x26          ; program execution control
PROG_INSTR_DESC = 0x27          ; current instruction opcode/descriptor (fetch dst)

;------------------------------------------------------------------------------
; TBPS program-byte opcodes
;------------------------------------------------------------------------------
; The opcode set is defined in the shared inc/tbps_isa.inc (included by rob3.asm,
; a verbatim copy of the standalone TBPS compiler's header). It is the single
; source of truth for the TBPS instruction set; this file keeps only the
; firmware-side interpreter workspace + routine entries below.

;------------------------------------------------------------------------------
; Interpreter routine entry points (prog_*)   [BYTE]
;------------------------------------------------------------------------------
PROG_PREPARE    = 0x0803        ; label-table preprocessor
PROG_EXEC       = 0x0941        ; instruction executor
PROG_GOTO       = 0x0A33        ; label -> PC resolver (rl A x2, page-0x80 table)

; End of inc/tbps_interpreter.inc
