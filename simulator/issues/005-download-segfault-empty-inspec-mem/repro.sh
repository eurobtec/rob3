#!/usr/bin/env bash
# Reproduce the `download` segfault (ucSim 0.9.9) — issue 005.
#
# Before the fix: feeding Intel-HEX records to the interactive `download`
# command SIGSEGVs the simulator (empty cl_inspec -> uninitialized `mem` ->
# wild-pointer deref in cl_uc::set_rom).
# After the fix (download-crash.patch): the records load into the ROM/code
# space and the process exits cleanly.
#
# Usage:  UCSIM_51=/path/to/ucsim_51 ./repro.sh
set -u

UC="${UCSIM_51:-$HOME/github/eurobtec/ucsim/src/sims/s51.src/ucsim_51}"
HEX="${ROB3_HEX:-$HOME/github/eurobtec/rob3/firmware/legacy/hex/M2764A@DIP28.HEX}"

if [ ! -x "$UC" ]; then echo "SKIP: ucsim_51 not found at $UC (set UCSIM_51)"; exit 0; fi
# @-free copy (unrelated issue 002)
SAFE=/tmp/rob3_issue005.hex
cp "$HEX" "$SAFE" 2>/dev/null || { echo "SKIP: ROM not found at $HEX"; exit 0; }

out="$(printf 'download\n:1080000000810000000000000000000000000000EF\n:108100001F00000000000000070000000000000049\n:00000001FF\ndump rom 0x8100 0x8101\nquit\n' \
  | "$UC" -t 8031 -X 11.0592M "$SAFE" 2>&1)"
rc=$?

echo "$out" | tail -4
echo "exit code: $rc"
if [ $rc -eq 139 ] || echo "$out" | grep -qi "segmentation"; then
  echo "RESULT: CRASH (bug present — apply download-crash.patch)"
  exit 1
fi
if echo "$out" | grep -qi "words loaded\|0x8100"; then
  echo "RESULT: OK (download loaded without crashing — fix present)"
  exit 0
fi
echo "RESULT: inconclusive"; exit 2
