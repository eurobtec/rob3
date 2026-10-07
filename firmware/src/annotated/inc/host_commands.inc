;==============================================================================
; host_commands.inc — ROB3 host command set (ISA-style definition)
;------------------------------------------------------------------------------
; Symbolic definition of the Eurobtec ROB3 low-level host command set: the
; command-byte bit fields, the command keywords/classes, the status/ACK reply
; bytes, and the frame terminator. This is the command protocol the host speaks
; to the firmware (carried over RS-232, which is only the transport); rs232.asm
; is the processor that decodes it (the UART ISR 0x0300, the dispatch
; rx_dispatch 0x03A9 -> cmd_class0 0x0440, and the TX helper 0x0541).
;
; A command byte is decoded from its BIT FIELDS (not a flat opcode table):
;
;   bit7 : class   0 = axis / position / query / control (immediate)   [0x00..0x7F]
;                  1 = system / stored-program control                 [0x80..0xFF]
;   Within class-0, bit6/bit5/bit4 select the operation group and the low 3 bits
;   are the axis (0..5; 7 = "all axes"); bit3 is the acknowledge-request R bit.
;
; Values are [BYTE]/[SIM]-verified against the ROB3 8031 ROM (see
; hardware/host/command.md "ROM confirmation" + simulator/tests/sim_serial.sh).
; The stored-program *instruction* bytes reuse these same low-level bit fields;
; that program instruction set is defined separately in inc/tbps_isa.inc.
;
;   Syntax: SDAS/ASxxxx (sdas8051). Addresses [BYTE]; protocol SEMANTICS [SIM]
;   unless an [INFER] note says otherwise.
;==============================================================================

;------------------------------------------------------------------------------
; Command-byte bit fields  (ACC bit tests in rx_dispatch / cmd_class0)   [SIM]
;------------------------------------------------------------------------------
CMD_CLASS_BIT    = 0x80         ; bit7: 0 = class-0 (axis), 1 = system/program
CMD_BIT6         = 0x40         ; group select (position/query/control vs set)
CMD_BIT5         = 0x20         ; group select
CMD_BIT4         = 0x10         ; group select (query: read-digital; etc.)
CMD_ACK_BIT      = 0x08         ; bit3 = R: request acknowledge -> latched 0x23.1
CMD_AXIS_MASK    = 0x07         ; low 3 bits: axis 0..5 (7 = all axes)
CMD_AXIS_ALL     = 0x07         ; axis field == 7 means "all axes"

;------------------------------------------------------------------------------
; Class-0 command keywords (bit7=0: immediate axis/position/query/control) [SIM]
;   The low 3 bits carry the axis; the base values below are axis 0 / R=0.
;------------------------------------------------------------------------------
CMD_POS_SET      = 0x00         ; 0x00+axis  set position[0x50+axis] (0x07=all, 0x0F=all+R)
CMD_POS_QUERY    = 0x40         ; 0x40+axis  read feedback[0x58+axis] (0x4F = all axes)
CMD_READ_DIG     = 0x50         ; 0x50+sel   read digital inputs (bit4 set in query class)
CMD_CTRL         = 0x60         ; control block (bits3:2 ignored): see sub-values below
CMD_POS_SPEED    = 0x70         ; 0x70+axis  move target[0x40+axis] + speed (0x7F = all)

; Control-block sub-commands (CMD_CTRL | n; the dispatch ignores bits 3:2)  [SIM]
CMD_MOTOR_OFF    = 0x60         ; disable motor control
CMD_MOTOR_ON     = 0x61         ; enable motor control (sets axis-enable 0x20.0)
CMD_SHUTDOWN     = 0x62         ; positioning shutdown; snapshot feedback -> position
CMD_SERIAL_NUM   = 0x63         ; serial-number query -> keyword + S0,S1,S2 + ETX

;------------------------------------------------------------------------------
; Composed / all-axes command bytes (the exact wire values; axis field = 7, and
; the all-axes forms carry R=1 so the low nibble is 0x0F / 0x07 per the spec) [SIM]
;------------------------------------------------------------------------------
CMD_POS_SET_ALL  = 0x07         ; set-position, all axes (0x00|0x07)
CMD_POS_SET_ALL_R= 0x0F         ; set-position, all axes + ack R=1
CMD_QUERY_ALL    = 0x4F         ; position query, all axes (0x40|0x0F)
CMD_POS_SPEED_ALL= 0x7F         ; move+speed, all axes (0x70|0x0F)

;------------------------------------------------------------------------------
; System / stored-program class (bit7=1): header-0x80 + sub-code (sys_cmd)  [SIM]
;------------------------------------------------------------------------------
CMD_SYS_BASE     = 0x80         ; system command base (sub-code 0 = readback if loaded)
CMD_SYS_PROGOP   = 0x82         ; program-operation sub-command (-> status 0xF6)
CMD_BLOCK_UPLOAD = 0x81         ; 0x81 block-store upload (stream program to SRAM)

;------------------------------------------------------------------------------
; Read-digital-input selector bits (CMD_READ_DIG | sel; bit4 set)         [SIM]
;   e.g. 0x56 -> [56, DI(0x5F), P1, ETX]
;------------------------------------------------------------------------------
DIG_SEL_IN0      = 0x01         ; bit0 -> append RAM 0x5E (DI state)
DIG_SEL_IN1      = 0x02         ; bit1 -> append RAM 0x5F (DI state)
DIG_SEL_P1       = 0x04         ; bit2 -> append P1 (0x90)

;------------------------------------------------------------------------------
; Frame terminator + startup handshake                                   [SIM]
;------------------------------------------------------------------------------
CMD_ETX          = 0x03         ; End-of-Text frame terminator (cjne A,#0x03 @0x03AE)
CMD_INIT_BYTE    = 0x20         ; first host byte after reset (auto-baud training)

;------------------------------------------------------------------------------
; Status / acknowledgment reply bytes (the 0xFx family is NOT errors)    [SIM]
;------------------------------------------------------------------------------
ACK_INIT_OK      = 0x15         ; initialization OK (auto-baud lock, 0x0733)
ACK_ALREADY      = 0xF1         ; already-initialized (idle-timeout, 0x0793)
ACK_STEP_STATUS  = 0xF2         ; program single-step status (0x0437)
ACK_DEFAULT      = 0xF3         ; default class-0 ACK "command received" (0x03AC)
ACK_SYSTEM       = 0xF4         ; system-class ACK (0xF3+1, 0x03B8)
ACK_PROG_STATUS  = 0xF6         ; program-operation status (0x03F1)
ACK_MOTION_DONE  = 0xF7         ; motion-complete ACK, target reached (0x0776)

;------------------------------------------------------------------------------
; Dispatch / processing routine entry points (rs232.asm, the transport+decoder)                 [BYTE]
;------------------------------------------------------------------------------
RX_ISR           = 0x0300       ; UART receive ISR
RX_DISPATCH      = 0x03A9       ; whole-frame command dispatch (header in R6)
CMD_CLASS0       = 0x0440       ; class-0 (axis/position/query/control) dispatch
SYS_CMD          = 0x03E1       ; system-class (bit7=1) sub-command chain
SYS_READPROG     = 0x03C9       ; program readback (0x25.6 TX stream from SRAM)
TX_HELPER        = 0x0541       ; response TX helper (ETX-framed)

; NOTE: the stored-program instruction set (what the interpreter at 0x0941
; decodes) reuses these same command-byte bit fields; it is defined in the
; shared inc/tbps_isa.inc. This file is the host-facing command set (carried
; over RS-232).

; End of host_commands.inc
