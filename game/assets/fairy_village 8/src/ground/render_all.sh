#!/bin/bash
# one Blender process per tile (keeps each run short).  moss/path: v1..v5; paving: 16 cuts of the 4x4 macro.
# usage: render_all.sh [names...]   (default: everything)
cd /workspace/fairy_village
NAMES="$@"
if [ -z "$NAMES" ]; then
  for s in fairy_moss petal_path; do for v in 1 2 3 4 5; do NAMES="$NAMES ${s}_v${v}"; done; done
  for v in $(seq 1 16); do NAMES="$NAMES moonstone_paving_v${v}"; done
fi
for n in $NAMES; do
  /home/box/bin/blender -b -P src/ground/bl_ground.py -- $n ${SAMPLES:-64} 2>&1 | grep -E "RENDERED|Error|Traceback"
done
echo ALLDONE
