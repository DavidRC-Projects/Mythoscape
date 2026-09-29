#!/bin/bash
# build every house (4 parallel Blender jobs). usage: tools/build_all.sh [--fast] [keys...]
cd "$(dirname "$0")/.."
FAST=""; [ "$1" == "--fast" ] && { FAST="--fast"; shift; }
KEYS=${@:-elders_hall general_store resting_ox farmhouse village_bank pet_emporium stonehaven_cottage stonehaven_house city_barracks kais_catch harbour_tackle}
mkdir -p notes/logs
printf "%s\n" $KEYS | xargs -P 4 -I{} sh -c "${BLENDER:-$HOME/bin/blender} -b -P blender_scripts/house.py -- --key {} $FAST > notes/logs/{}.log 2>&1; grep -q done notes/logs/{}.log && echo ok {} || echo FAIL {}"
