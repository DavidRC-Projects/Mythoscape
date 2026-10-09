#!/bin/bash
# Resumable: hero/portrait skipped if present; sprite frames already on disk are skipped by kn_hd.py.
# Two Blender processes at a time. Usage: nohup bash run_all.sh [keys...] > logs/run_all.log 2>&1 &
BL=/home/box/bin/blender; P=/workspace/knights_hd/src/kn_hd.py; R=/workspace/knights_hd/renders; LOG=/workspace/knights_hd/logs
KEYS=("$@"); [ ${#KEYS[@]} -eq 0 ] && KEYS=(knight shadow_knight knight_captain_vorn barrow_knight sir_aldric magma_knight)
run_one() { local key=$1 mode=$2 S=40
  [ "$mode" = hero ] && [ -f $R/$key/hero.png ] && return 0
  [ "$mode" = portrait ] && [ -f $R/$key/portrait_bust.png ] && return 0
  [ "$mode" != sprites ] && S=96
  echo "=== $key $mode $(date +%T)"
  timeout 14400 $BL -b -P $P -- --key $key --mode $mode --samples $S > $LOG/${key}_${mode}.log 2>&1
  grep -q "^DONE" $LOG/${key}_${mode}.log && echo "ok $key $mode $(date +%T)" || { echo "FAIL $key $mode"; tail -20 $LOG/${key}_${mode}.log; }
}
run_char() { for m in hero portrait sprites; do run_one $1 $m; done; echo "CHAR_DONE $1 $(date +%T)"; }
lane() { for k in "$@"; do run_char $k; done; }
A=(); B=(); j=0
for k in "${KEYS[@]}"; do if [ $((j % 2)) -eq 0 ]; then A+=($k); else B+=($k); fi; j=$((j+1)); done
lane "${A[@]}" & pa=$!
[ ${#B[@]} -gt 0 ] && { lane "${B[@]}" & pb=$!; wait $pb; }
wait $pa
echo ALL_DONE $(date +%T)
