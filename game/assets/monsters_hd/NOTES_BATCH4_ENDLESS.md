# Mythoscape HD monsters batch 4 — Endless Depths coverage

Fills the remaining Endless Depths roster types that lacked `monsters_hd` packs.

## Derived (clone + tint from existing Blender packs)

| id | source | notes |
|---|---|---|
| village_rat | giant_rat | warm dust tint |
| sewer_rat | giant_rat | green-grey sewer tint |
| skeleton | big_skeleton | cooler bone tint |

Tool: `mmorpg/tools/clone_monsters_hd.py`

## Painted stills packs

Built from AI-painted stills (idle/attack facings), cut out with rembg `u2netp`, fitted to the batch-1 256×288 / 128×144 canvas, then expanded into idle/walk/attack/hit/death × s/e/n/w frame trees.

| id | notes |
|---|---|
| goblin | early-floor staple |
| spider | base arachnid |
| spiderling | smaller/lighter tint of spider stills |
| sewer_spider | green-black tint of spider stills |
| dragon | adamant dragon |
| petal_thrall | base corrupted fairy |
| petal_thrall_thorn / _mirror / _night | thrall recolours |
| petal_elite_mirror / petal_elite_night | elite recolours |
| petaldeep_queen | queen recolour |

Tool: `mmorpg/tools/pack_monsters_hd_from_stills.py`

Wired in `mmorpg/client/knights_hd_client.py` (`MONSTERS_HD`).

These stills packs are a painted stand-in for full Blender Cycles sheets. Replacing them with proper batch-1-quality Blender exports later is welcome; the folder layout already matches.
