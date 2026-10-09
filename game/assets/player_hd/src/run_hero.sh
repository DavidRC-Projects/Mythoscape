#!/bin/bash
cd /workspace/player_hd
for K in male female; do
  /home/box/bin/blender -b --factory-startup -noaudio --python src/pl_hero.py -- $K 64 > logs/hero_$K.log 2>&1
done
echo done > logs/hero_DONE
