;==============================================================================
; tbps_isa.inc — ROB3 Teach Box Programming System: TBPS instruction set
;------------------------------------------------------------------------------
; Symbolic equates for the TBPS opcode set, used by the compiled MCS-51 (sdas8051)
; code generated from TBPS by tools/tbps-compiler (`tbpsc --arch mcs51`). Replaces
; magic literals with named symbols for the TBPS program-byte opcodes.
;
; This file describes ONLY the TBPS instruction set. The firmware equates the
; hosted-mode compiled code reuses (IRAM map, routine entry points, SRAM program
; store) live in rob3_firmware.inc and rob3_sram.inc; the compiled backend
; includes those alongside this file.
;
; All values are [BYTE]/[SIM]-verified against the ROB3 8031 ROM and the TBPS
; compiler's ucSim tests.
;
; SOURCE OF TRUTH: the ROB3 8031 ROM. This file is a self-contained MIRROR of
; the verified opcode values so the standalone compiler repo needs no cross-repo
; include.
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

; End of tbps_isa.inc
