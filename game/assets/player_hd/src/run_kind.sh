#!/bin/bash
# resumable: re-run any time; finished frames/layers are skipped
K=$1
cd /workspace/player_hd
export PL_THREADS=${PL_THREADS:-4}
for S in 2x 4x; do
  echo "=== $K $S start $(date)" >> logs/run_$K.log
  /home/box/bin/blender -b --factory-startup -noaudio --python src/pl_render.py -- $K $S > logs/render_${K}_${S}.log 2>&1
  echo "=== $K $S exit $? $(date)" >> logs/run_$K.log
done
