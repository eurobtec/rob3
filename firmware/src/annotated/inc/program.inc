;==============================================================================
; ROB3 FIRMWARE — STORED-PROGRAM INTERPRETER data model
;   File: firmware/src/annotated/inc/program.inc  (pairs with program.asm)
;==============================================================================
;
; Stored-program (teachbox / RS-232-uploaded) interpreter workspace: the
; program page pointers, the 16-bit PC, the current-instruction descriptor, and
; the execution-control byte. Programs live in the external HM6264 SRAM
; (devices.inc DEV_SRAM, base page 0x80); the label table is page 0x80, the
; body is pages 0x81+. See inc/system.inc for the IRAM map and the 0x28 state
; flags (program-loaded/running/motion), and program.asm for the opcodes.
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
; Opcodes (from prog_prepare / prog_exec)   [SIM]-verified in tools/tbps-compiler
;------------------------------------------------------------------------------
OP_MARK         = 0x1F          ; MARK label definition (2-byte PC entry)
OP_POS_SET      = 0x00          ; set-position class (0x00+axis; 0x07 = all)
OP_POS_MOVE     = 0x60          ; POS a.n move: 0x60+axis -> target[0x40+axis]
OP_POS_SPEED    = 0x70          ; move + speed: 0x70+axis / 0x7F all (target+speed)
OP_OUT          = 0x10          ; OUT k: 0x10 + (k-1)&3 ; dout_write(A=op,R0=val)
OP_TIM          = 0x18          ; TIM t: operands lo,hi -> WAIT_CTR_LO/HI
OP_GOTO         = 0x34          ; GOTO m (unconditional); operand[0] = label
OP_GOTO_COUNTED = 0x36          ; GOTO m.n (counted) -- note: == OP_INSTR3
OP_IF           = 0x32          ; IF i[.m]: op[0]=label, op[1]=mask; jump (mask&P1)==0
OP_INSTR3       = 0x36          ; 3-byte instruction form (collides with GOTO.n)
OP_END_BIT      = 0x80          ; bit7 set = END of program
PROG_SLOT       = 0x08          ; default instruction slot size (PC += 8)
PROG_HDR_SENT   = 0x83          ; program header / end sentinel byte

;------------------------------------------------------------------------------
; Interpreter routine entry points (prog_*)   [BYTE]
;------------------------------------------------------------------------------
PROG_PREPARE    = 0x0803        ; label-table preprocessor
PROG_EXEC       = 0x0941        ; instruction executor
PROG_GOTO       = 0x0A33        ; label -> PC resolver (rl A x2, page-0x80 table)

; NOTE: these TBPS opcode + routine equates are mirrored in the standalone TBPS
; compiler's header (eurobtec/rob3_tbps : src/tbps_compiler/asm/tbps_isa.inc);
; THIS file is the source of truth for the firmware tree.

; End of inc/program.inc
