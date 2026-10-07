;==============================================================================
; ROB3 FIRMWARE — MOTION-EXECUTOR / PROGRAM-STEP GATE  (annotated disassembly)
;==============================================================================
;
; Source ROM image : firmware/bin/M2764A@DIP28.BIN  (8 KB, M2764A EPROM)
; CPU              : Intel 8031 / MCS-51, XTAL = 11.0592 MHz
; This file        : the main-loop MOTION gate at 0x0900. It is NOT the TBPS
;                    interpreter — it is the servo/motion tick that advances
;                    axis motion each main-loop pass and, only when the current
;                    step's motion (or a TIM/IF wait) has completed, hands off
;                    to the interpreter's instruction executor (prog_exec,
;                    0x0941, in tbps_interpreter.asm). Split out from the
;                    interpreter so tbps_interpreter.asm is interpreter-only.
;
; PROVENANCE TAGS: [BYTE] decoded from ROM; [SIM] confirmed in ucSim;
;   [INFER] inferred. Control flow + PC handling are [BYTE]/[SIM].
;
;==============================================================================
; motion_exec (0x0900) — main-loop gate: advances motion, on step completion
;   (or TIM/IF wait) fetches the next instruction via prog_exec (0x0941).
;==============================================================================
        .org    0x0900
        jb 0x44, L_0906                     ; 20 44 03  0900
        jnb 0x43, L_0940                    ; 30 43 3A  0903
L_0906:
        mov SFR_DPH, #0x51                     ; 75 83 51  0906
        mov A, 0x1F                         ; E5 1F  0909
        movx @DPTR, A                       ; F0  090B
        mov A, 0x26                         ; E5 26  090C
        jz L_0941                           ; 60 31  090E
        jnb 0xE0, L_091E                    ; 30 E0 0B  0910
        mov A, 0x21                         ; E5 21  0913
        cjne A, #0x3F, L_0940               ; B4 3F 28  0915
        mov A, 0x2B                         ; E5 2B  0918
        jnz L_0940                          ; 70 24  091A
        sjmp L_093B                         ; 80 1D  091C
L_091E:
        jnb 0xE1, L_092E                    ; 30 E1 0D  091E
        jnb 0x1D, L_0940                    ; 30 1D 1C  0921
        clr 0x1D                            ; C2 1D  0924
        djnz 0x1A, L_0940                   ; D5 1A 17  0926
        djnz 0x1B, L_0940                   ; D5 1B 14  0929
        sjmp L_093B                         ; 80 0D  092C
L_092E:
        mov A, 0x90                         ; E5 90  092E
        jnb 0x38, L_0937                    ; 30 38 04  0930
        anl A, R7                           ; 5F  0933
        jz L_093B                           ; 60 05  0934
        ret                                 ; 22  0936
L_0937:
        orl A, R7                           ; 4F  0937
        cjne A, #0xFF, L_0940               ; B4 FF 05  0938
L_093B:
        mov 0x26, #0x00                     ; 75 26 00  093B
        clr 0x44                            ; C2 44  093E
L_0940:
        ret                                 ; 22  0940
