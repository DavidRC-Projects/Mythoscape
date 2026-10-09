#!/bin/bash
# re-render garment layers after push_out (2x then 4x). usage: run_fix.sh <kind> <layers,comma>
K=$1; LS=$2; cd /workspace/player_hd; export PL_THREADS=2
for S in 2x 4x; do
  for l in ${LS//,/ }; do rm -rf renders/$K/$S/$l; done
  /home/box/bin/blender -b --factory-startup -noaudio --python src/pl_render.py -- $K $S $LS > logs/render_fix_${K}_${LS%%,*}_$S.log 2>&1
  echo "$(date +%T) fix $K ${LS%%,*} $S exit $?" >> logs/fix.log
done
