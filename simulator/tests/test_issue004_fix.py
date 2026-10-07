#!/usr/bin/env python3
"""Issue 004 FIX verification: a LIVE serial round-trip over a TCP socket.

Reproduces the issue-004 scenario (async host bytes during a free `run`) and
proves the `check_often` fix resolves it:

  WITHOUT check_often: the two command bytes (0x4F 0x03) are read from the
    socket ~1.84M machine-cycles apart (coarse run-loop fd poll), which exceeds
    the firmware's ~1.47M-cycle serial RX timeout. The frame never completes;
    the firmware stages the 0xF1 reset-ACK. -> reply has NO dispatched frame.

  WITH `expr uart0_check_often=1` (set via ucSim configuration memory, NO patch
    or rebuild required): the serial tick() drains the socket fd every tick, so
    the ETX arrives inside the timeout window and the all-axis query DISPATCHES.
    -> reply contains a real position frame (header 0x4F ... terminated by ETX
    0x03).

Flow per run:
  1) start ucsim_51 with -S port=<p> (socket) + a command console on a pty-ish
     pipe; load adc + rxd;
  2) reach the auto-baud spin, drive the training byte (rxd) to lock the UART;
  3) connect a TCP client to <p>;
  4) (fix case) enable check_often via config memory (expr uart0_check_often=1);
  5) free-run; send 0x4F 0x03 back-to-back on the socket;
  6) read the socket reply and classify.

Opt-in: needs a loader-enabled ucsim_51 (any stock 0.9.9+ exposes the
`uart0_check_often` config variable) and the adc/rxd modules. SKIPS cleanly
otherwise so a stock `make test` is unaffected.
"""
import os
import socket
import subprocess
import sys
import time

UCSIM = os.environ.get("UCSIM_51") or os.path.expanduser("~/github/eurobtec/ucsim/src/sims/s51.src/ucsim_51")
HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
ADC = f"{SIM}/ucsim-modules/adc/adc.so"
RXD = f"{SIM}/ucsim-modules/rxd/rxd.so"
HEX = os.environ.get("SAFEHEX") or f"{SIM}/build/rob3.hex"
PORT = int(os.environ.get("I4_PORT", "15104"))


def skip(msg):
    print(f"SKIP  {msg}")
    print("test_issue004_fix: SKIPPED")
    sys.exit(0)


def need(path, what):
    if not os.path.exists(path):
        skip(f"{what} not found ({path})")


def supports_check_often():
    """Probe: does this ucsim_51 expose the `uart0_check_often` config variable?

    This is standard ucSim configuration memory (serconf_check_often registered
    via uc->vars->add in serial_hw.cc) — present on a stock 0.9.9+ build, no
    patch required. We confirm it is writable with `expr`.
    """
    try:
        p = subprocess.run(
            [UCSIM, "-t", "51", "-X", "11.0592M", "-S", "in=/dev/null,out=/dev/null", HEX],
            input='expr uart0_check_often=1\ninfo variable often\nquit\n',
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return False
    # the `info variable often` line reports the cell = 1 once set
    out = p.stdout + p.stderr
    return "uart0_check_often" in out and "0x00000001" in out


def run_roundtrip(enable_fix):
    """Return the raw socket reply bytes for one command frame."""
    # ucSim reads console commands from stdin (a pipe); the serial link is the
    # TCP socket on PORT. We script the bring-up on stdin and talk bytes on the
    # socket.
    proc = subprocess.Popen(
        [UCSIM, "-t", "51", "-X", "11.0592M", "-S", f"port={PORT},raw", HEX],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )

    def cmd(s):
        proc.stdin.write(s + "\n")
        proc.stdin.flush()

    try:
        cmd(f'loadhw "{ADC}"')
        cmd(f'loadhw "{RXD}"')
        cmd("reset")
        cmd("break 0x06bf")
        cmd("run")                      # free-run to the auto-baud spin
        time.sleep(0.6)
        cmd("clear")
        cmd("break 0x073c")
        cmd("set hardware rxd 0x20 128")  # lock the UART (TH1=0xFC)
        cmd("step 40000")
        time.sleep(0.4)
        cmd("clear")
        if enable_fix:
            # Enable via ucSim configuration memory — no patch/rebuild needed.
            cmd("expr uart0_check_often=1")
            time.sleep(0.1)
        # connect the host client to the serial socket
        sk = socket.create_connection(("127.0.0.1", PORT), timeout=3)
        sk.settimeout(2.0)
        time.sleep(0.2)
        # free-run, then send the all-axis query 0x4F 0x03 back-to-back
        cmd("run")
        time.sleep(0.2)
        sk.sendall(bytes([0x4F, 0x03]))
        # let the sim churn long enough to cross the firmware timeout window
        time.sleep(2.5)
        reply = b""
        try:
            while True:
                chunk = sk.recv(256)
                if not chunk:
                    break
                reply += chunk
        except socket.timeout:
            pass
        sk.close()
        return reply
    finally:
        try:
            proc.stdin.write("quit\n"); proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


def classify(reply):
    """A dispatched all-axis frame contains header 0x4F and an ETX 0x03 after
    some payload; a timeout-only reply is just 0x15/0xF1 bytes."""
    if not reply:
        return "NO-REPLY"
    has_dispatch = (0x4F in reply) and (0x03 in reply[reply.index(0x4F)+1:])
    return "DISPATCHED" if has_dispatch else "F1-ONLY"


def main():
    need(UCSIM, "ucsim_51"); need(ADC, "adc.so"); need(RXD, "rxd.so"); need(HEX, "ROM hex")
    if not os.access(UCSIM, os.X_OK):
        skip("ucsim_51 not executable")
    if not supports_check_often():
        skip("this ucsim_51 has no `uart0_check_often` config variable (need 0.9.9+)")

    fail = 0

    print("--- WITHOUT fix (expect F1-ONLY: timeout, no dispatch) ---")
    r_off = run_roundtrip(enable_fix=False)
    c_off = classify(r_off)
    print(f"  reply = {r_off.hex() or '(none)'}  -> {c_off}")

    print("--- WITH check_often=1 (expect DISPATCHED: all-axis frame) ---")
    r_on = run_roundtrip(enable_fix=True)
    c_on = classify(r_on)
    print(f"  reply = {r_on.hex() or '(none)'}  -> {c_on}")

    if c_on == "DISPATCHED":
        print("PASS  check_often makes the live socket round-trip dispatch")
    else:
        print("FAIL  check_often did NOT dispatch the frame")
        fail = 1
    # The 'without' case is informative, not strictly asserted: on a fast host
    # the OS may coalesce the fd poll. We only require that the FIX works.
    if c_off == "F1-ONLY":
        print("INFO  reproduced the bug without the fix (F1-only), as expected")
    else:
        print(f"INFO  'without fix' gave {c_off} (host-timing dependent; not asserted)")

    print("test_issue004_fix: " + ("OK" if fail == 0 else "FAILED"))
    sys.exit(fail)


if __name__ == "__main__":
    main()
