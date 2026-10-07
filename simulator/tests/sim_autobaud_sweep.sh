#!/usr/bin/env bash
# Behavioral SWEEP: measure the ROB3 RS-232 SOFTWARE AUTO-BAUD across a range of
# host line speeds, using the `rxd` cl_hw module to drive the P3.0 (RXD) pin at
# bit level (ucSim's byte-level core UART does not toggle the pins — see
# issues/003). This is the "measure auto-detect for different host speeds" rig
# referenced by issue 004.
#
# For each standard baud it:
#   1) reaches the auto-detect start-bit spin (0x06BF) on the P3.0=1 path;
#   2) shifts the training byte 0x20 on P3.0 at that baud's bit time
#      (cycles/bit = XTAL_Hz / baud / 12, the 8051 machine-cycle rate);
#   3) runs a bounded burst and reports whether the firmware LOCKED
#      (reached init_finish 0x073C with the UART armed) and, if so, the derived
#      TH1 / TCON(TR1) / IE.
#
# A LOCK is defined as: reaching 0x073C AND TH1=0xFC AND TCON.6(TR1)=1 AND
# IE=0x17 (ES enabled). A NO-LOCK is the firmware never leaving the measure
# loop (never reaching 0x073C) within the burst — the auto-detect loops back to
# re-measure forever when the training edges fail validation.
#
# WHY THE WINDOW IS WHAT IT IS (documented in ucsim-modules/rxd/README.md +
# issues/003):
#   The firmware times the training byte's edges with Timer 0 and validates
#   (run/6 + 8) & 0xF0 == 0x20 (plus two more edge checks). In THIS ucSim model,
#   where we represent the line in machine cycles, the accepted bit time is
#   ~104..152 machine-cycles/bit, centred ~128, always deriving TH1=0xFC. The
#   standard wire bauds map to:
#       baud   cyc/bit (= 11059200/baud/12)   expected
#       1200   768                            NO  (far above window)
#       2400   384                            NO  (above window)
#       4800   192                            NO  (above window)
#       9600    96                            NO  (just below window)
#   i.e. NONE of the nominal wire bauds land in this model's window — the
#   absolute-baud vs cyc/bit offset is a MODELLING ARTIFACT (the firmware times
#   edges with Timer 0; we drive the line in machine cycles). The meaningful,
#   verified result is the SHAPE of the auto-detect response: where it locks,
#   where it refuses, and the single derived TH1. The lock point itself is
#   covered by sim_serial_autobaud.sh (128 cyc/bit).
#
# To ALSO sweep the model's actual lock window (machine-cycle bit times), set
#   SWEEP_CYC="96 104 112 120 128 136 144 152 160"
# and the script treats each value as a literal cycles/bit instead of a baud.
#
# Requires a loader-enabled ucsim_51 plus the adc + rxd cl_hw modules. SKIPS
# cleanly if they are absent, so a stock-s51 `make test` still passes.
set -euo pipefail

SIMFLAGS="${SIMFLAGS:--t 51 -X 11.0592M}"
SAFEHEX="${SAFEHEX:?SAFEHEX not set}"
UCSIM_51="${UCSIM_51:-$HOME/github/eurobtec/ucsim/src/sims/s51.src/ucsim_51}"

# XTAL in Hz for the baud->cycles/bit conversion (must match SIMFLAGS -X).
XTAL_HZ="${XTAL_HZ:-11059200}"
# Machine cycles per bit burst budget (one 10-bit 8N1 frame at the slowest
# swept bit time, plus slack for the measure loop). 1200 baud = 768 cyc/bit *
# 10 bits = 7680; give generous headroom so a locking frame always completes.
BURST="${BURST:-200000}"

# Default sweep: standard wire bauds (requested starting 1200, 2400 ... 9600).
# Override with SWEEP_BAUD="..." or switch to literal cycles/bit via SWEEP_CYC.
SWEEP_BAUD="${SWEEP_BAUD:-1200 2400 4800 9600}"
SWEEP_CYC="${SWEEP_CYC:-}"

here="$(cd "$(dirname "$0")/.." && pwd)"
ADC="$here/ucsim-modules/adc/adc.so"
RXD="$here/ucsim-modules/rxd/rxd.so"

skip() { echo "SKIP  $1"; echo "sim_autobaud_sweep: SKIPPED"; exit 0; }

[ -x "$UCSIM_51" ] || skip "loader-enabled ucsim_51 not found (set UCSIM_51)"
[ -f "$ADC" ] || skip "adc.so not built (make -C ucsim-modules)"
[ -f "$RXD" ] || skip "rxd.so not built (make -C ucsim-modules)"

# Confirm this binary can loadhw (older builds have no loader).
probe="$(printf 'loadhw "%s"\nquit\n' "$RXD" | timeout 10 "$UCSIM_51" $SIMFLAGS "$SAFEHEX" 2>&1 | sed 's/\x1b\[0K//g' || true)"
grep -qi 'id_string=rxd' <<<"$probe" || skip "ucsim_51 cannot loadhw the rxd module"

# Run one auto-detect measurement at <cyc_per_bit>. Echoes the raw sim output.
run_point() {
  local cyc="$1"
  local script
  read -r -d '' script <<EOF || true
loadhw "$ADC"
loadhw "$RXD"
reset
break 0x06bf
run
clear
break 0x073c
set hardware rxd 0x20 $cyc
step $BURST
dump sfr 0x8d 0x8d
dump sfr 0x88 0x88
dump sfr 0xa8 0xa8
quit
EOF
  printf '%s\n' "$script" | timeout 60 "$UCSIM_51" $SIMFLAGS "$SAFEHEX" 2>&1 | sed 's/\x1b\[0K//g'
}

# Classify a sim output: prints "LOCK <th1>" or "NO-LOCK".
classify() {
  local out="$1"
  if ! grep -qi 'stop at 0x00073c' <<<"$out"; then
    echo "NO-LOCK"; return
  fi
  local th1 tcon ie
  # dump line: "0x8d TH1:   0b11111100 0xfc '.' 252 ( -4)". The value we want is
  # the 0xNN that comes right after the 0b-binary token (awk field).
  val_of() { grep -E "$1" <<<"$out" | awk '{for(i=1;i<=NF;i++) if($i ~ /^0b/){print $(i+1); exit}}' | tr A-F a-f; }
  th1="$(val_of '^0x8d TH1')"
  tcon="$(val_of '^0x88 TCON')"
  ie="$(val_of '^0xa8 IE')"
  local tr1=0
  [[ -n "$tcon" ]] && (( (0x${tcon#0x} & 0x40) == 0x40 )) && tr1=1
  if [[ "$th1" == "0xfc" && $tr1 -eq 1 && "$ie" == "0x17" ]]; then
    echo "LOCK $th1"
  else
    echo "ARMED? th1=$th1 tcon=$tcon ie=$ie"
  fi
}

# This ucSim model's measured accept window (machine-cycles/bit). Verified [SIM]
# by this script's SWEEP_CYC mode: locks 104..152, refuses at 96/160. Inside the
# window the firmware ALWAYS derives TH1=0xFC (div 4 -> 7200 baud) — the single
# reachable rung of its power-of-two reload ladder (see the precision note).
WIN_LO="${WIN_LO:-104}"
WIN_HI="${WIN_HI:-152}"

# Expected result for a given cyc/bit: "LOCK 0xfc" if inside the window, else
# "NO-LOCK". (The firmware can only ever derive TH1=0xFC in this window.)
expected_for() {
  local c="$1"
  if (( c >= WIN_LO && c <= WIN_HI )); then echo "LOCK 0xfc"; else echo "NO-LOCK"; fi
}

echo "ROB3 auto-baud sweep  (XTAL=${XTAL_HZ} Hz, burst=${BURST} machine-cycles/point)"
echo "lock = reached 0x073C with TH1=0xFC, TR1 set, IE=0x17"
echo "model accept window: ${WIN_LO}..${WIN_HI} cyc/bit (inside -> always TH1=0xFC)"
echo

fail=0
pass() { echo "PASS  $1"; }
die()  { echo "FAIL  $1"; fail=1; }

# Build the list of (label, cyc_per_bit) points.
declare -a labels cycs
if [[ -n "$SWEEP_CYC" ]]; then
  printf '%-10s %-14s %-14s %-s\n' "cyc/bit" "measured" "expected" "verdict"
  printf '%-10s %-14s %-14s %-s\n' "-------" "--------" "--------" "-------"
  for c in $SWEEP_CYC; do labels+=("$c cyc/bit"); cycs+=("$c"); done
else
  printf '%-8s %-10s %-14s %-14s %-s\n' "baud" "cyc/bit" "measured" "expected" "verdict"
  printf '%-8s %-10s %-14s %-14s %-s\n' "----" "-------" "--------" "--------" "-------"
  for b in $SWEEP_BAUD; do
    c=$(( (XTAL_HZ + (b*12)/2) / (b*12) ))   # round(XTAL/(baud*12))
    labels+=("$b"); cycs+=("$c")
  done
fi

for i in "${!cycs[@]}"; do
  cyc="${cycs[$i]}"
  out="$(run_point "$cyc")"
  res="$(classify "$out")"
  exp="$(expected_for "$cyc")"
  verdict="ok"
  [[ "$res" == "$exp" ]] || { verdict="MISMATCH"; die "cyc/bit=$cyc: measured [$res] != expected [$exp]"; }
  if [[ -n "$SWEEP_CYC" ]]; then
    printf '%-10s %-14s %-14s %-s\n' "$cyc" "$res" "$exp" "$verdict"
  else
    b="${labels[$i]}"
    printf '%-8s %-10s %-14s %-14s %-s\n' "$b" "$cyc" "$res" "$exp" "$verdict"
  fi
done

# --- Precision of standard-baud reproduction (arithmetic, no sim) -------------
# The firmware derives TH1 = ~(R7-1) with R7 a POWER OF TWO (the normalize loop
# only ever does R7 <<= 1). So the Timer-1 reload (256-TH1) is restricted to
# {1,2,4,8,16,...} and the only achievable bauds are XTAL/(384 * 2^n):
#   28800, 14400, 7200, 3600, 1800, ...  (a power-of-two ladder, SMOD=0, mode1).
#
# WHY THE ERROR IS A CONSTANT RATIO (not a shrinking rounding error):
#   Both the standard series (9600*2^k) and the achievable ladder (7200*2^k) are
#   geometric with ratio 2, so the mismatch is a FIXED MULTIPLICATIVE offset that
#   is identical at every rate -- it does NOT get smaller at lower bauds (which
#   is the usual integer-reload-rounding intuition). The offset MAGNITUDE is set
#   by the crystal: at 11.0592 MHz the exact standard reloads are 24/12/6/3 =
#   3*2^k, and the power-of-two ladder is missing the factor 3; the nearest 2^k
#   to 3*2^k is 4*2^k (4/3 too large -> 3/4 the baud -> uniform -25%). A correct
#   fixed-baud setup here would use div=24/12/6/3 (TH1 0xE8/0xF4/0xFA/0xFD) --
#   divisors the auto-detect can never produce. See issues/004 README for the
#   full write-up (incl. the crystal-dependence table).
echo
echo "Standard-baud reproduction precision (firmware TH1 ladder, SMOD=0, mode1):"
printf '  %-7s %-12s %-8s %-10s %-s\n' "std" "nearest" "TH1" "256-TH1" "error"
offset_x10=""
for s in 1200 2400 4800 9600 19200 38400; do
  # nearest achievable = XTAL/384 rounded to a power-of-two divisor
  best_div=0; best_err=0
  for n in 0 1 2 3 4 5 6 7; do
    div=$((1<<n))
    baud=$(( XTAL_HZ / (384*div) ))
    # abs error in baud
    d=$(( baud>s ? baud-s : s-baud ))
    if [[ $best_div -eq 0 ]] || (( d < best_err )); then best_div=$div; best_err=$d; fi
  done
  baud=$(( XTAL_HZ / (384*best_div) ))
  th1=$(( (256-best_div) & 0xFF ))
  # signed error percent *100 for one decimal via integer math
  errx10=$(( (baud - s)*1000 / s ))
  offset_x10="$errx10"   # same at every rate (constant ratio) -> keep last
  printf '  %-7s %-12s 0x%02X     %-10s %+d.%d%%\n' "$s" "$baud" "$th1" "$best_div" $((errx10/10)) $(( (errx10<0?-errx10:errx10)%10 ))
done
printf '  => the auto-detect can only hit the XTAL/(384*2^n) ladder. The error is a\n'
printf '     CONSTANT RATIO at every rate (here %+d.%d%%), NOT a shrinking rounding\n' \
  $((offset_x10/10)) $(( (offset_x10<0?-offset_x10:offset_x10)%10 ))
printf '     error -- both grids scale by 2, so the offset never decays at lower\n'
printf '     bauds. Its magnitude depends on the CRYSTAL (at 11.0592 MHz the exact\n'
printf '     std reloads are 3*2^k, so the nearest 2^k is 4/3 too large -> -25%%).\n'
printf '     In THIS model the lock always yields TH1=0xFC (div 4 = 7200 baud);\n'
printf '     115200 (~8 cyc/bit) is far outside the accept window (see issues/003).\n'

echo
if [[ $fail -eq 0 ]]; then
  echo "sim_autobaud_sweep: OK"
else
  echo "sim_autobaud_sweep: FAILED"
  exit 1
fi
