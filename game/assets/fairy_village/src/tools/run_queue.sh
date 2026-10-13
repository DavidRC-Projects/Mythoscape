#!/bin/bash
# usage: run_queue.sh <logdir> "<args1>" "<args2>" ...   (one Blender process per asset, sequential)
LOG=$1; shift; mkdir -p $LOG
cd /workspace/fairy_village/src/blender
for a in "$@"; do
  name=q_$(echo "$a" | tr ' /' '__' | tr -cd '[:alnum:]_-' | cut -c1-80)
  timeout 5400 /home/box/bin/blender -b -P ${SCRIPT:-fv_buildings.py} -- $a > $LOG/$name.log 2>&1
  if grep -q "^DONE" $LOG/$name.log; then echo "ok $a"; else echo "FAIL $a"; fi
done
echo QUEUE_DONE
