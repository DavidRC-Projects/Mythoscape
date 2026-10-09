#!/bin/bash
# Corrected-camera sprite pass (sensor_fit HORIZONTAL: true 175.6 px/m, feet at 256,528) into renders/<k>/sprite_4x_fix.
# Resumable (existing frames skipped). Unfinished characters first. Old sprite_4x renders are left untouched.
BL=/home/box/bin/blender; P=/workspace/knights_hd/src/kn_hd.py; R=/workspace/knights_hd/renders; LOG=/workspace/knights_hd/logs
run_one() { local key=$1 mode=$2 S=32 extra=""
  [ "$mode" = hero ] && [ -f $R/$key/hero.png ] && return 0
  [ "$mode" = portrait ] && [ -f $R/$key/portrait_bust.png ] && return 0
  [ "$mode" != sprites ] && S=96
  [ "$mode" = sprites ] && extra="--sprdir sprite_4x_fix"
  echo "=== $key $mode $(date +%T)"
  timeout 14400 $BL -b -P $P -- --key $key --mode $mode --samples $S $extra > $LOG/fix_${key}_${mode}.log 2>&1
  grep -q "^DONE" $LOG/fix_${key}_${mode}.log && echo "ok $key $mode $(date +%T)" || { echo "FAIL $key $mode"; tail -5 $LOG/fix_${key}_${mode}.log; }
}
lane() { for k in "$@"; do for m in hero portrait sprites; do run_one $k $m; done; echo "CHAR_DONE $k $(date +%T)"; done; }
lane magma_knight knight_captain_vorn shadow_knight & pa=$!
lane sir_aldric knight barrow_knight & pb=$!
wait $pa $pb
echo ALL_DONE $(date +%T)
