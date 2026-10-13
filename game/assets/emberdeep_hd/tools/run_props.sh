#!/bin/bash
cd /workspace/emberdeep_hd
for job in "$@"; do m=${job%%:*}; s=${job##*:}
  [ -e work/p_$m.done ] && continue
  /home/box/bin/blender -b -P tools/bake_props.py -- $m $s work/p_$m.png > logs/p_$m.log 2>&1 && touch work/p_$m.done
done
