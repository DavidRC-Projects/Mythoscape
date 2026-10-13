#!/bin/bash
cd /workspace/fairy_village
while ! grep -q ALLDONE work/ground/render_all.log 2>/dev/null; do sleep 5; done
for d in ${@:-mushroom_ring toadstool_cluster moonpetal_clump rosebell_clump fallen_petals glow_stones fairy_lantern fern_clump pebbles queens_tree_hall_skirt moonstone_fountain_rim lily_fountain_rim}; do
  /home/box/bin/blender -b -P src/ground/bl_decals.py -- $d ${SAMPLES:-64} 2>&1 | grep -E "DECAL|Error|Traceback|line [0-9]"
done
echo DECALSDONE
