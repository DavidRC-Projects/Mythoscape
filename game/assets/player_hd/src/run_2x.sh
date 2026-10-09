#!/bin/bash
K=$1; SH=$2; TAG=${K}_${SH/\//of}
cd /workspace/player_hd
export PL_THREADS=${PL_THREADS:-2} PL_SHARD=$SH
echo "=== $TAG 2x-only start $(date)" >> logs/run_$TAG.log
/home/box/bin/blender -b --factory-startup -noaudio --python src/pl_render.py -- $K 2x > logs/render_${TAG}_2x.log 2>&1
echo "=== $TAG 2x-only exit $? $(date)" >> logs/run_$TAG.log
