#!/bin/bash
# usage: run_tex_queue.sh kind:seed:name ...   (skips outputs that exist)
cd /workspace/emberdeep_hd
for job in "$@"; do
  IFS=: read kind seed name <<< "$job"
  out=work/st2_$name.png
  [ -f "$out" ] && continue
  /home/box/bin/blender -b -P tools/bake_stones2.py -- $kind $seed $out 768 > logs/st2_$name.log 2>&1
done
