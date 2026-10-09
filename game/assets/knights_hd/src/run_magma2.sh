#!/bin/bash
BL=/home/box/bin/blender; P=/workspace/knights_hd/src/kn_hd.py; L=/workspace/knights_hd/logs
echo "=== magma sprites v2 $(date +%T)"
timeout 14400 nice -n 5 $BL -b -P $P -- --key magma_knight --mode sprites --samples 32 --sprdir sprite_4x_fix2 > $L/magma2_sprites.log 2>&1 && grep -q "^DONE" $L/magma2_sprites.log && echo "ok sprites $(date +%T)"
for m in hero portrait; do
  [ -f /workspace/knights_hd/renders/magma_v2/$m.ok ] && continue
  timeout 7200 nice -n 5 $BL -b -P $P -- --key magma_knight --mode $m --samples 96 > $L/magma2_$m.log 2>&1 && grep -q "^DONE" $L/magma2_$m.log && touch /workspace/knights_hd/renders/magma_v2/$m.ok && echo "ok $m $(date +%T)"
done
echo CHAR_DONE magma_knight_v2 $(date +%T)
