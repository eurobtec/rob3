;==============================================================================
; tbps_isa.inc — ROB3 Teach Box Programming System: ISA + firmware equates
;------------------------------------------------------------------------------
; Symbolic equates for native MCS-51 (sdas8051) code generated from TBPS by
; tools/tbps-compiler (`tbpsc --native`). Replaces magic literals with named
; symbols: the TBPS opcode set, the firmware IRAM map the hosted-mode code
; reuses, and the firmware routine entry points it calls.
;
; All values are [BYTE]/[SIM]-verified against the ROB3 8031 ROM
; (firmware/src/annotated/program.asm, rs232.asm) and the TBPS compiler's ucSim
; tests. Mirrors the authoritative firmware equates in
; firmware/src/annotated/inc/ (servo.inc / system.inc / program.inc).
;
; SOURCE OF TRUTH: the firmware tree's inc/program.inc (opcodes + routine
; entries) and inc/system.inc + inc/servo.inc (IRAM map). This file is a
; self-contained MIRROR so the standalone compiler repo (eurobtec/rob3_tbps)
; needs no cross-repo include. The annotated firmware asm uses its own inc/*.inc
; directly; keep the two in sync (same addresses).
;
;   Syntax: SDAS/ASxxxx (sdas8051).  `.include "tbps_isa.inc"`.
;==============================================================================

;------------------------------------------------------------------------------
; TBPS program-byte opcodes  (prog_exec 0x0941 decode)              [SIM]
;------------------------------------------------------------------------------
TBPS_MARK        = 0x1F     ; label definition (preprocessor-only; operand = m)
TBPS_POS_SET     = 0x00     ; set-position class (0x00+axis; 0x07 = all axes)
TBPS_POS_MOVE    = 0x60     ; move axis to target (0x60+axis -> target[0x40+axis])
TBPS_POS_SPEED   = 0x70     ; move + speed (0x70+axis / 0x7F all): target + speed byte
TBPS_OUT         = 0x10     ; digital out (0x10 + (k-1)&3); dout_write(A=op,R0=val)
TBPS_TIM         = 0x18     ; delay; operands lo,hi -> WAIT_CTR_LO/HI
TBPS_GOTO        = 0x34     ; unconditional jump; operand[0] = label
TBPS_GOTO_COUNT  = 0x36     ; counted loop (collides w/ the 3-byte INSTR3 form)
TBPS_IF          = 0x32     ; input test; op[0]=label, op[1]=mask; jump if (mask&P1)==0
TBPS_END         = 0x80     ; program end (any opcode with bit7 set)
TBPS_SLOT        = 0x08     ; fixed instruction slot size (PC += 8)
TBPS_HDR_SENT    = 0x83     ; SRAM program header / end sentinel

AXIS_ALL         = 0x07     ; low-3 axis field == 7 means "all axes"

;------------------------------------------------------------------------------
; Firmware IRAM map the hosted-mode native code reuses  (see inc/system.inc)
;------------------------------------------------------------------------------
TARGET_BASE      = 0x40     ; 0x40+N per-axis commanded target (what POS writes)
CURPOS_BASE      = 0x50     ; 0x50+N per-axis current position
FEEDBACK_BASE    = 0x58     ; 0x58+N per-axis ADC feedback
SPEED_BASE       = 0x70     ; 0x70+N per-axis speed/step-rate
NEED_MOVE        = 0x2B     ; axis "needs to move" mask
MOVING           = 0x2C     ; axis "moving" mask
WAIT_CTR_LO      = 0x1A     ; TIM delay counter lo
WAIT_CTR_HI      = 0x1B     ; TIM delay counter hi
DOUT_SHADOW      = 0x1F     ; digital-out latch shadow (8255 Port B mirror)
PROG_PAGE        = 0x3E     ; ext-RAM program page hi (= 0x80, label table)
PROG_PAGE1       = 0x3F     ; ext-RAM program body page (= 0x81)
PC_LO            = 0x66     ; program counter (ext-RAM offset) lo
PC_HI            = 0x67     ; program counter (ext-RAM offset) hi
STATE_FLAGS      = 0x28     ; .1 loaded, .2 running, .3 motion, .4 conditional

SFR_P1           = 0x90     ; Port 1 (digital inputs read here)

;------------------------------------------------------------------------------
; Firmware routine entry points the native code CALLs / mirrors
;------------------------------------------------------------------------------
DOUT_WRITE       = 0x07D0   ; dout_write(A=op[0..3], R0=val) -> DOUT_SHADOW + Port B
PROG_EXEC        = 0x0941   ; stored-program instruction executor
PROG_PREPARE     = 0x0803   ; label-table preprocessor
PROG_GOTO        = 0x0A33   ; label -> PC resolver (rl A x2 into page-0x80 table)

;------------------------------------------------------------------------------
; External-SRAM program store
;------------------------------------------------------------------------------
SRAM_LABEL_BASE  = 0x8000   ; page 0x80: 2-byte-per-label PC table
SRAM_BODY_BASE   = 0x8100   ; page 0x81+: program body (8-byte slots)

; End of tbps_isa.inc
