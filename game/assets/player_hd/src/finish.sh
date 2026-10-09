#!/bin/bash
# waits for the 12 fix lines, then post -> meta -> fx -> previews -> combat sheet -> zips
cd /workspace/player_hd; L=logs/finish.log
while [ "$(wc -l < logs/fix.log 2>/dev/null || echo 0)" -lt 12 ] || pgrep -f run_fix.sh >/dev/null; do sleep 30; done
echo "$(date +%T) fixes done" >> $L
python3 src/pl_post.py > logs/post.log 2>&1; echo "$(date +%T) post $?" >> $L
python3 src/pl_meta.py > logs/meta.log 2>&1; echo "$(date +%T) meta $?" >> $L
python3 src/pl_fx.py > logs/fx.log 2>&1; echo "$(date +%T) fx $?" >> $L
python3 src/pl_previews.py > logs/previews.log 2>&1; echo "$(date +%T) previews $?" >> $L
python3 src/pl_combat_sheet.py > logs/combat_sheet.log 2>&1; echo "$(date +%T) combat $?" >> $L
python3 src/make_zips.py > logs/zips.log 2>&1; echo "$(date +%T) zips $?" >> $L
echo "$(date +%T) FINISHED" >> $L
