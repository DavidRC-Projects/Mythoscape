#!/bin/bash
# resumable worker: run_shard.sh <kind> <i/n>
K=$1; SH=$2; TAG=${K}_${SH/\//of}
cd /workspace/player_hd
export PL_THREADS=${PL_THREADS:-2} PL_SHARD=$SH
for S in 2x 4x; do
  echo "=== $TAG $S start $(date)" >> logs/run_$TAG.log
  /home/box/bin/blender -b --factory-startup -noaudio --python src/pl_render.py -- $K $S > logs/render_${TAG}_${S}.log 2>&1
  echo "=== $TAG $S exit $? $(date)" >> logs/run_$TAG.log
done
