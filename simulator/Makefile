# ROB3 firmware — behavioral simulation tests (ucSim)
#
# Toolchain (ucSim + optional loader build):
#   s51        8051 sim    (ucSim) for behavioral tests
#   ucsim_51   loader-enabled sim with the cl_hw modules (opt-in tests)
#
# The behavioral tests run the REAL ROM image in ucSim and assert runtime state
# matches the annotated .asm files under ../firmware/src/annotated/.
#
# The GOLDEN byte-match (assembled source == ROM) now lives with the annotated
# source itself: ../firmware/src/annotated/ (make verify there builds the whole
# 8 KB image and cmp's it against the ROM). This Makefile's `verify` target
# delegates to it, so `make test` still covers golden + behavioral.
#
# This Makefile lives in the top-level simulator/ directory. The firmware
# artifacts (ROM image + annotated sources) live in ../firmware/; the
# simulator sources, tests and build output are local to this directory.

# ---- Layout ------------------------------------------------------------------
FWDIR      := ../firmware
BIN        := $(FWDIR)/bin/M2764A@DIP28.BIN
HEX        := $(FWDIR)/hex/M2764A@DIP28.HEX
SIMDIR     := .
BUILD      := $(SIMDIR)/build
ANNDIR     := $(FWDIR)/src/annotated

# ---- Tools -------------------------------------------------------------------
SIM        := s51
SIMFLAGS   := -t 51 -X 11.0592M

# A hex copy with a shell-safe name (the shipped .hex has an '@' in its name)
SAFEHEX    := $(BUILD)/rob3.hex

# Bash-sourceable host command set, generated from the firmware's .inc (single
# source of truth) by inc2sh.py — the sim-serial* tests source it.
HOST_CMD_INC := $(ANNDIR)/inc/host_commands.inc
HOST_CMD_SH  := $(ANNDIR)/inc/host_commands.sh
$(HOST_CMD_SH): $(HOST_CMD_INC) $(ANNDIR)/inc2sh.py
	@python3 $(ANNDIR)/inc2sh.py $(HOST_CMD_INC) -o $(HOST_CMD_SH)
	@echo "generated $(HOST_CMD_SH) from $(HOST_CMD_INC)"

.PHONY: all verify \
        sim-init sim-run sim-teachbox sim-teachbox-module sim-adc sim-serial \
        sim-serial-autobaud sim-serial-e2e sim-autobaud-sweep sim-issue004-fix sim-ros2-live sim-teleop-ros2 sim-program sim-teachbox-axis demo-teachbox demo-hello-program test clean help

all: test ## Default: run all tests (golden + behavioral)

help: ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		sort | awk 'BEGIN{FS=":.*?## "}{printf "  %-16s %s\n", $$1, $$2}'

$(BUILD):
	@mkdir -p $(BUILD)

# ---- Golden byte-match (delegated to the annotated source tree) --------------
verify: ## GOLDEN: assembled annotated source == ROM (runs make -C ../firmware/src/annotated verify)
	@$(MAKE) -C $(ANNDIR) verify
$(SAFEHEX): $(HEX) | $(BUILD)
	cp "$(HEX)" $(SAFEHEX)

sim-init: $(SAFEHEX) ## Behavioral: run init in s51, assert annotated behavior
	@SAFEHEX=$(SAFEHEX) SIM="$(SIM)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_init.sh

sim-run: $(SAFEHEX) ## Run init past the ADC/INT1 gate (inject EOC) to main loop
	@SAFEHEX=$(SAFEHEX) SIM="$(SIM)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_run.sh

sim-serial: $(SAFEHEX) $(HOST_CMD_SH) ## Behavioral: RS-232 protocol dispatch/framing (read/write/ETX/reset-ACK)
	@SAFEHEX=$(SAFEHEX) SIM="$(SIM)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_serial.sh

sim-program: $(SAFEHEX) ## Behavioral: stored-program interpreter (fetch/decode/advance, store-pos, end, GOTO label)
	@SAFEHEX=$(SAFEHEX) SIM="$(SIM)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_program.sh

sim-serial-autobaud: $(SAFEHEX) ## Behavioral: software auto-baud brings UART up via the rxd cl_hw pin driver (opt-in; skips w/o loader ucsim_51 + adc/rxd modules)
	@SAFEHEX=$(SAFEHEX) UCSIM_51="$(UCSIM_51)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_serial_autobaud.sh

sim-serial-e2e: $(SAFEHEX) $(HOST_CMD_SH) ## Behavioral: FULL serial RX chain — auto-baud lock -> real byte over -S link -> SBUF/RI -> RX ISR (opt-in; skips w/o loader ucsim_51 + adc/rxd)
	@SAFEHEX=$(SAFEHEX) UCSIM_51="$(UCSIM_51)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_serial_e2e.sh

sim-autobaud-sweep: $(SAFEHEX) ## Behavioral: SWEEP auto-baud across host speeds (standard bauds 1200..9600; SWEEP_CYC="..." for literal cyc/bit) (opt-in; skips w/o loader ucsim_51 + adc/rxd)
	@SAFEHEX=$(SAFEHEX) UCSIM_51="$(UCSIM_51)" SIMFLAGS="$(SIMFLAGS)" \
		SWEEP_BAUD="$(SWEEP_BAUD)" SWEEP_CYC="$(SWEEP_CYC)" \
		$(SIMDIR)/tests/sim_autobaud_sweep.sh

sim-issue004-fix: $(SAFEHEX) ## Behavioral: LIVE socket round-trip proves the `uart0_check_often` config var dispatches a frame (opt-in; needs ucsim_51 0.9.9+ + adc/rxd)
	@SAFEHEX=$(SAFEHEX) UCSIM_51="$(UCSIM_51)" \
		python3 $(SIMDIR)/tests/test_issue004_fix.py

sim-ros2-live: $(SAFEHEX) ## Behavioral: the REAL ROS2 driver codec+SerialTransport round-trips over a LIVE pty (proves issue-004 fix end-to-end; needs ucsim_51 0.9.9+ + adc/rxd + driver + socat + pyserial)
	@UCSIM_51="$(UCSIM_51)" DRIVER="$(DRIVER)" \
		python3 $(SIMDIR)/tests/verify_ros2_driver_live.py

sim-teleop-ros2: $(SAFEHEX) ## Behavioral: ROS2 TELEOP (JointJog -> rob3_driver -> firmware in free-running ucSim) inside the rob3-ros2 container (proves live teleop; skips w/o docker image + ucsim_51 0.9.9+ + driver)
	@IMAGE="$(IMAGE)" UCSIM_HOST="$(UCSIM_HOST)" DRIVER_HOST="$(DRIVER_HOST)" \
		TELEOP_TIMEOUT="$(TELEOP_TIMEOUT)" \
		$(SIMDIR)/tests/sim_teleop_ros2.sh

sim-teachbox: $(SAFEHEX) ## Behavioral: run the keypad scanner, assert key decode
	@SAFEHEX=$(SAFEHEX) SIM="$(SIM)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_teachbox.sh

sim-teachbox-module: $(SAFEHEX) ## Behavioral: exercise the compiled teachbox cl_hw module (opt-in; skips w/o ucsim_51)
	@SAFEHEX=$(SAFEHEX) SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_teachbox_module.sh

sim-adc: $(SAFEHEX) ## Behavioral: free-run past the ADC/INT1 gate via the compiled adc cl_hw module (opt-in; skips w/o ucsim_51)
	@SAFEHEX=$(SAFEHEX) SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/sim_adc.sh

sim-teachbox-axis: $(SAFEHEX) ## Black-box: real keypad axis-select -> POSITION mode (needs teachbox+loopback cl_hw; skips w/o them)
	@UCSIM_51="$(UCSIM_51)" ROB3_HEX="$(SAFEHEX)" python3 $(SIMDIR)/tests/test_teachbox_axis_select.py

demo-teachbox: $(SAFEHEX) ## Demo: teachbox key press -> axis-select -> jog -> axis position moves (needs custom ucsim_51)
	@SAFEHEX=$(SAFEHEX) SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/demo_teachbox_axis.sh

demo-hello-program: $(SAFEHEX) ## Demo: hand-assemble a "hello world" program, load into SRAM, run it (move axes 0/1, END)
	@SAFEHEX=$(SAFEHEX) SIM="$(SIM)" UCSIM_51="$(UCSIM_51)" SIMFLAGS="$(SIMFLAGS)" \
		$(SIMDIR)/tests/demo_hello_program.sh

# ---- Aggregate ---------------------------------------------------------------
test: verify sim-init sim-run sim-serial sim-program sim-serial-autobaud sim-serial-e2e sim-teachbox sim-teachbox-module sim-adc sim-teachbox-axis ## Run all tests (golden + behavioral)
	@echo "ALL TESTS PASSED"

clean: ## Remove build artifacts
	rm -rf $(BUILD)
