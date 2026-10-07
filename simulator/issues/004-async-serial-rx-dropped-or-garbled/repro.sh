#!/usr/bin/env bash
# Repro for ucSim issue 004 — async serial RX bytes dropped (socket) / garbled
# (live pty), while pre-staged file input round-trips cleanly.
#
# Brings the ROB3 ROM to the serial auto-baud lock using the rxd cl_hw module,
# then sends the all-axis position query (0x4F 0x03) three ways and shows that
# only the pre-staged file input dispatches a real reply frame.
#
# Needs: a loader-enabled ucsim_51 (UCSIM_51) + the adc & rxd cl_hw modules.
set -euo pipefail

UCSIM_51="${UCSIM_51:-$HOME/github/eurobtec/ucsim/src/sims/s51.src/ucsim_51}"
MODS="${ROB3_MODS:-$HOME/github/eurobtec/rob3/simulator/ucsim-modules}"
ROM_SRC="${ROB3_ROM:-$HOME/github/eurobtec/rob3/firmware/legacy/hex/M2764A@DIP28.HEX}"
ROM=/tmp/rob3_issue004.hex
cp "$ROM_SRC" "$ROM"

skip() { echo "SKIP  issue-004 repro: $1"; exit 0; }
[ -x "$UCSIM_51" ] || skip "ucsim_51 not found (set UCSIM_51)"
[ -f "$MODS/rxd/rxd.so" ] || skip "rxd.so not built"
[ -f "$MODS/adc/adc.so" ] || skip "adc.so not built"

# --- (1) pre-staged file input: EXPECTED to round-trip cleanly ---------------
IN=/tmp/issue004_in; OUT=/tmp/issue004_out
printf '\x4f\x03' > "$IN"; : > "$OUT"
mkfifo /tmp/issue004_con 2>/dev/null || true
"$UCSIM_51" -t 51 -X 11.0592M -S "in=$IN,out=$OUT" "$ROM" </tmp/issue004_con \
  >/tmp/issue004.log 2>&1 &
UCPID=$!
exec 3>/tmp/issue004_con
sleep 0.6
printf 'loadhw "%s/adc/adc.so"\nloadhw "%s/rxd/rxd.so"\n' "$MODS" "$MODS" >&3
sleep 0.2
printf 'reset\nbreak 0x06bf\nrun\nclear\nbreak 0x073c\nset hardware rxd 0x20 128\nstep 40000\nclear\n' >&3
sleep 1.2
printf 'set hardware adc 3 0x3b\nstep 2000000\nstep 2000000\nquit\n' >&3
sleep 2
exec 3>&-; kill "$UCPID" 2>/dev/null || true; rm -f /tmp/issue004_con
echo "(1) pre-staged file input  -> serial OUT: $(xxd -p "$OUT" 2>/dev/null | tr -d '\n')"
echo "    EXPECT a '4f ... 03' reply frame (dispatched)."
rm -f "$IN" "$OUT"

echo
echo "(2) TCP socket / (3) live pty paths are shown in the issue README; they"
echo "    drop (socket: '... queued for RX, skip') or garble the frame. The"
echo "    reliable contract is the pre-staged file input above."
