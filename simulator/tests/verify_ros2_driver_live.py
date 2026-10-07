#!/usr/bin/env python3
"""Confirm the issue-004 `check_often` fix with the ACTUAL ROS2 driver code.

Unlike the driver's pre-staged-file integration test, this exercises the LIVE
pty path that issue 004 used to break:

  * ucSim attaches its UART to a real PTY (-S in=<pty>,out=<pty>,raw) and
    free-runs (exactly scripts/sim_bringup.py);
  * `expr uart0_check_often=1` (ucSim config memory) enables the fix;
  * the driver's OWN SerialTransport opens the other end of the pty and its OWN
    protocol codec sends query_all_positions() and parses the reply.

No staged file, no `step` pacing — the driver talks to the firmware over a live
serial device the same way it would talk to the real robot. PASS means the
all-axis position frame round-trips and the codec parses 6 positions.

Env: UCSIM_51, ROB3_ROM, ROB3_MODS, DRIVER (path to rob3_driver package dir).
Skips cleanly if the fixed ucsim_51 / modules / driver are unavailable.
"""
import os
import pty
import re
import select
import shutil
import sys
import time

UCSIM = os.environ.get("UCSIM_51") or os.path.expanduser("~/github/eurobtec/ucsim/src/sims/s51.src/ucsim_51")
ROM_SRC = os.environ.get("ROB3_ROM") or os.path.expanduser("~/github/eurobtec/rob3/firmware/legacy/hex/M2764A@DIP28.HEX")
MODS = os.environ.get("ROB3_MODS") or os.path.expanduser("~/github/eurobtec/rob3/simulator/ucsim-modules")
DRIVER = os.environ.get("DRIVER") or os.path.expanduser("~/github/eurobtec/rob3_ros2_driver/rob3_driver")

PROMPT = "ROB3SIM>"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def skip(msg):
    print(f"SKIP  {msg}")
    print("verify_ros2_driver_live: SKIPPED")
    sys.exit(0)


def _read(fd, token, timeout):
    buf = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if not r:
            continue
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        buf += data.decode("latin-1", "replace")
        if token in buf:
            break
    return ANSI.sub("", buf)


def _cmd(fd, line, timeout=5.0):
    os.write(fd, (line + "\n").encode())
    return _read(fd, PROMPT, timeout)


def main():
    for path, what in ((UCSIM, "ucsim_51"), (ROM_SRC, "ROM"),
                       (f"{MODS}/rxd/rxd.so", "rxd.so"),
                       (f"{MODS}/adc/adc.so", "adc.so"),
                       (DRIVER, "driver package")):
        if not os.path.exists(path):
            skip(f"{what} not found ({path})")
    if not os.access(UCSIM, os.X_OK):
        skip("ucsim_51 not executable")

    # ucSim mis-parses '@' in a filename (file@memspace) -> copy to a safe name
    # BEFORE anything touches the ROM (incl. the probe below).
    rom = "/tmp/rob3_ros2live.hex"
    shutil.copyfile(ROM_SRC, rom)

    # Probe the config variable is present in this binary (stock 0.9.9+).
    import subprocess
    probe = subprocess.run(
        [UCSIM, "-t", "51", "-X", "11.0592M", "-S", "in=/dev/null,out=/dev/null", rom],
        input="expr uart0_check_often=1\ninfo variable often\nquit\n",
        capture_output=True, text=True, timeout=10)
    if "uart0_check_often" not in (probe.stdout + probe.stderr) \
            or "0x00000001" not in (probe.stdout + probe.stderr):
        skip("this ucsim_51 lacks the uart0_check_often config variable (need 0.9.9+)")

    # Import the driver's real codec + transport.
    sys.path.insert(0, DRIVER)
    try:
        import serial  # noqa: F401  (pyserial, used by SerialTransport)
    except Exception:
        skip("pyserial not installed (needed by the driver SerialTransport)")
    try:
        import rob3_driver.protocol as P
        from rob3_driver.transport import SerialTransport
    except Exception:
        skip(f"rob3_driver package not importable from DRIVER={DRIVER}")

    # Bridge two PTYs with socat so ucSim and the driver each get a real tty
    # device path: ucSim attaches to one end, the driver opens the other.
    # (A single pty slave opened by both parties does not bridge RX<->TX.)
    import subprocess as _sp
    if not shutil.which("socat"):
        skip("socat not available (needed to bridge the ucSim<->driver ptys)")
    link_a, link_b = "/tmp/rob3_tty_sim", "/tmp/rob3_tty_drv"
    for lk in (link_a, link_b):
        if os.path.islink(lk) or os.path.exists(lk):
            try:
                os.remove(lk)
            except OSError:
                pass
    socat = _sp.Popen(
        ["socat", "-d", "-d",
         f"pty,raw,echo=0,link={link_a}", f"pty,raw,echo=0,link={link_b}"],
        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    # wait for both link nodes to appear
    for _ in range(50):
        if os.path.exists(link_a) and os.path.exists(link_b):
            break
        time.sleep(0.05)
    if not (os.path.exists(link_a) and os.path.exists(link_b)):
        socat.kill()
        skip("socat did not create the pty bridge")
    dev = link_a           # ucSim end
    drv_dev = link_b       # driver end

    pid, cfd = pty.fork()
    if pid == 0:
        os.execv(UCSIM, [UCSIM, "-t", "51", "-X", "11.0592M", "-p", PROMPT,
                         "-S", f"in={dev},out={dev},raw", rom])
        os._exit(127)

    fail = 0
    try:
        _read(cfd, PROMPT, 5.0)
        _cmd(cfd, f'loadhw "{MODS}/adc/adc.so"')
        _cmd(cfd, f'loadhw "{MODS}/rxd/rxd.so"')
        _cmd(cfd, "reset")
        _cmd(cfd, "break 0x06bf")
        _cmd(cfd, "run", timeout=5.0)
        _cmd(cfd, "clear")
        _cmd(cfd, "break 0x073c")
        _cmd(cfd, "set hardware rxd 0x20 128")
        out = _cmd(cfd, "step 60000", timeout=15.0)
        if "0x00073c" not in out:
            print("FAIL  auto-baud did not lock")
            fail = 1
        else:
            print("PASS  auto-baud locked (UART up over the live pty)")
        _cmd(cfd, "clear")
        _cmd(cfd, "set hardware adc 3 0x3b")        # recognizable feedback value
        _cmd(cfd, "expr uart0_check_often=1")        # THE FIX (config memory)
        os.write(cfd, b"run\n")                      # free-run; UART live
        time.sleep(0.3)

        # ---- now use the DRIVER'S OWN code over the live pty ----
        tp = SerialTransport(device=drv_dev, baud=9600)
        tp.open()
        try:
            tp.write(P.query_all_positions())        # 0x4F 0x03
            # read up to the ETX terminator; allow a leading 0x15 init-ack
            raw = tp.read_until(0x03, timeout=4.0, limit=64)
        finally:
            tp.close()
        print(f"      driver received: {raw.hex() or '(none)'}")
        start = raw.find(0x4F)
        if start < 0:
            print(f"FAIL  no 0x4F reply keyword (got {raw.hex()!r})")
            fail = 1
        else:
            reply = P.parse_reply(raw[start:])
            if not reply.ok:
                print(f"FAIL  reply not ETX-terminated: {raw.hex()}")
                fail = 1
            else:
                positions = P.parse_positions(reply)
                if len(positions) == P.NUM_AXES and all(0 <= v <= 255 for v in positions):
                    print(f"PASS  driver codec parsed {P.NUM_AXES} positions: {positions}")
                else:
                    print(f"FAIL  bad positions: {positions}")
                    fail = 1
    finally:
        try:
            os.write(cfd, b"quit\n"); time.sleep(0.1); os.close(cfd)
        except OSError:
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except OSError:
            pass
        try:
            socat.kill()
        except Exception:
            pass
        os.remove(rom) if os.path.exists(rom) else None

    print("verify_ros2_driver_live: " + ("OK" if fail == 0 else "FAILED"))
    sys.exit(fail)


if __name__ == "__main__":
    main()
