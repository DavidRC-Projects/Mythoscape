#!/bin/bash
# waits for v2 renders, starts the missing shard when memory allows, then hero -> post -> meta -> fx -> previews
cd /workspace/player_hd
L=logs/orchestrate.log
started=0; pgrep -f "run_shard.sh female 2/3" >/dev/null && started=1
while true; do
  n=$(pgrep -fc "pl_render.py")
  avail=$(free -m | awk '/Mem:/{print $7}')
  if [ $started -eq 0 ] && { { [ "$n" -le 4 ] && [ "$avail" -ge 1800 ]; } || { [ "$n" -le 5 ] && [ "$avail" -ge 2300 ]; }; }; then
    nohup src/run_shard.sh female 2/3 >/dev/null 2>&1 &
    started=1; echo "$(date +%T) started female 2/3 (n=$n avail=$avail)" >> $L
  fi
  d2=$(ls renders/*/2x/*/DONE 2>/dev/null | wc -l); d4=$(ls renders/*/4x/*/DONE 2>/dev/null | wc -l)
  echo "$(date +%T) procs=$n avail=$avail done2x=$d2 done4x=$d4" >> $L
  if [ $started -eq 1 ] && [ "$n" -eq 0 ] && ! pgrep -f run_shard.sh >/dev/null && [ ! -f work/HOLD ]; then break; fi
  sleep 120
done
echo "$(date +%T) renders finished d2=$d2 d4=$d4" >> $L
for K in male female; do
  PL_HW=760 PL_HH=1140 nice -n 5 /home/box/bin/blender -b --factory-startup -noaudio --python src/pl_hero.py -- $K 64 > logs/hero_$K.log 2>&1
  echo "$(date +%T) hero $K exit $?" >> $L
done
python3 src/pl_post.py > logs/post.log 2>&1; echo "$(date +%T) post $?" >> $L
python3 src/pl_meta.py > logs/meta.log 2>&1; echo "$(date +%T) meta $?" >> $L
python3 src/pl_fx.py > logs/fx.log 2>&1; echo "$(date +%T) fx $?" >> $L
python3 src/pl_previews.py > logs/previews.log 2>&1; echo "$(date +%T) previews $?" >> $L
python3 src/pl_combat_sheet.py > logs/combat_sheet.log 2>&1; echo "$(date +%T) combat $?" >> $L
echo "$(date +%T) ALL DONE" >> $L
