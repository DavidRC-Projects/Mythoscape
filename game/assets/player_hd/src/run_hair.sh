#!/bin/bash
# re-render the long hair layers (front-strand fix) for one sex, 2x then 4x; then clear HOLD when both sexes are done
K=$1; cd /workspace/player_hd
export PL_THREADS=${PL_THREADS:-2}
for S in 2x 4x; do
  rm -rf renders/$K/$S/hair_long_straight renders/$K/$S/hair_shoulder_wavy
  /home/box/bin/blender -b --factory-startup -noaudio --python src/pl_render.py -- $K $S hair_long_straight,hair_shoulder_wavy > logs/render_hair_${K}_$S.log 2>&1
  echo "$(date +%T) hair $K $S exit $?" >> logs/orchestrate.log
done
touch work/HAIR_$K
[ -f work/HAIR_male ] && [ -f work/HAIR_female ] && rm -f work/HOLD && echo "$(date +%T) HOLD cleared" >> logs/orchestrate.log
