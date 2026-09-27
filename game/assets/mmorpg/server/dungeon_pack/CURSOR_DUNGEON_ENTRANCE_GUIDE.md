# Cursor Dungeon Entrance Guide (Blender-built, OSRS style)

Seven 3D dungeon-entrance exteriors, one per monster family, in the **same art style as the
monster pack** (`CURSOR_MONSTER_GUIDE.md`). Every model is built by a **Blender Python script**
(`blender --background --python ...`), so Cursor can change a number, re-run one command and get
the `.blend`, `.glb`, `.bam`, concept image, in-engine check render and 2D sprites again.

> **Integration rule (read first).** These assets replace **only the exterior visuals** of the
> existing dungeon entrances. The existing enter-dungeon triggers, entrance positions, interiors,
> server logic and save data stay exactly as they are. The new visuals go behind a
> `USE_NEW_ENTRANCES` flag. The old drawing code is **kept, not deleted**. Start with **one**
> entrance type. The paste-ready prompt is `CURSOR_PROMPT.md`.

---

## 0. What's in the pack

```
dungeons/
  CURSOR_DUNGEON_ENTRANCE_GUIDE.md   this file
  CURSOR_PROMPT.md                   paste-ready prompt for Cursor (investigate first, then one entrance)
  blender_scripts/
    osrs_kit.py                      shared low-poly kit (primitives, archway, mound, materials, export, render)
    dragon_lair.py goblin_cave.py skeleton_crypt.py spider_nest.py
    void_rift.py giants_cavern.py wolf_den.py        one reusable script per entrance
  blend/<key>.blend                  Blender source (scene "Scene" = entrance + COLLISION; scene
                                     "CONCEPT_RENDER" = camera, sun, ground, 1.8 m figure)
  glb/<key>.glb                      glTF binary, per-face colour materials, no textures, no UVs
  bam/<key>.bam                      Panda3D BAM via blend2bam (legacy materials + invisible CollisionBoxes)
  json/<key>.json                    metadata: triangles, bounds, colliders, trigger, palette, emissive, camera
  ref/<key>_ref_player.glb           the 1.8 m reference figure in place (for scale checks only)
  images/<key>_concept.png           Blender EEVEE concept render (3/4 game camera, 1.8 m figure)
  images/contact_sheet.png           labelled sheet: concept | Panda3D render, tris, opening, score
  panda_renders/<key>_panda.png      the same camera in Panda3D with the monster-pack lighting
  sprites/<view>/<key>_<size>.png    2D route: transparent PNGs (views front34 / iso / osrs; 128/256/512 px)
  sprites/<view>/<key>.json          pixel anchors (origin, door, trigger polygon) per size
  tools/
    entrance_loader.py               drop-in Panda3D loader + collision/trigger helper (copy into the game)
    build_all.py                     rebuild everything (Blender -> blend2bam -> Panda renders -> sprites -> sheet)
    panda_render.py                  in-engine check renders
    render_sprites.py                2D sprite renderer
    verify_pack.py                   automated checks (loads, budgets, trigger fires, walls block, bam collisions)
    make_contact_sheet.py
  review/scores.json                 OSRS-look scores and review history
  review/verify_report.txt           last verify_pack.py result
```

---

## 1. Art spec (the OSRS look, same as the monster pack)

| Rule | Value |
|---|---|
| Scale | **1 unit = 1 m**. Player = **1.8 m**. Doorways at least **2.2 m wide x 2.3 m tall** (giant: 6 x 7.3 m) |
| Axes | Z up, ground at z = 0. The entrance **front faces -Y**. Origin (0,0,0) = centre of the doorway's front edge at ground level. The interior goes into **+Y** |
| Geometry | Low poly, **chunky readable shapes**, faceted (every face flat-shaded, no smoothing, no bevel modifiers) |
| Colour | **One material per palette colour**, Principled BSDF base colour only, roughness 1, specular 0. Each face randomly picks the base colour or a `.d` (x0.86) / `.l` (x1.10) variant, which gives OSRS-style facet noise |
| Textures | **None.** No image textures, no UVs, no normal maps |
| Palette | Muted, earthy, slightly desaturated (moss/olive, bark/leather browns, bone creams, slate greys, scorched browns, bruised violets). Hex values are sRGB, the same convention as the monster guide |
| Glow | Only small accents are emissive: flames, embers, necro urns, spider eyes, and the void portal. They're listed in json `emissive` |
| Inside | Every entrance has a **walkable opening** lined with progressively darker `interior` -> `interior_deep` colours, a dark floor, and a **black back plane**. That's what makes it read as "going inside". The void rift instead has a portal whose bands darken to a near-black core |
| Silhouette | One big readable idea per family: horns + fangs (dragon), timber frame + totem (goblin), pillars + pediment + steps down (crypt), webs + eggs (spider), crystal crown + purple ring (void), giant door + boulders (giant), tree + roots (wolf) |
| Avoid (David's past rejections) | Flat facade with a door pasted on it, residential brown doors with knobs, gaps between front and side, debug/construction lines, grids, and floating planes |
| Lighting | The monster pack's `setup_osrs_lighting()`: ambient 0.42 + one warm directional sun, `set_shader_off()`, flat shade model. The sun heading is mirrored to `(20, -45, 0)` because entrances face -Y while monsters face +Y |

### Triangle budgets

The budget range is roughly 1.5k to 4k triangles. Actual counts are measured after triangulation (`json/<key>.json` -> `triangles`).

| Entrance | Triangles | Budget (max) | Opening (w x h) | OSRS score |
|---|---|---|---|---|
| Dragon Lair | 1495 | 3000 | 4.0 x 4.2 m | 8.5/10 |
| Goblin Cave | 1579 | 2500 | 2.2 x 2.6 m | 8.5/10 |
| Skeleton Crypt | 1863 | 3000 | 2.2 x 3.4 m | 8.0/10 |
| Spider Nest | 1693 | 2500 | 2.8 x 2.6 m | 8.0/10 |
| Void Rift | 1555 | 3000 | 2.7 x 3.7 m | 8.5/10 |
| Giant's Cavern | 1685 | 4000 | 6.0 x 7.3 m | 8.0/10 |
| Wolf Den | 1585 | 2500 | 2.4 x 2.3 m | 8.0/10 |

Keep the whole pack under about 15k triangles on screen at once. Each entrance is **one GeomNode**
(about 30 materials, so about 30 geoms). If draw calls matter, call `model.flatten_strong()` after
loading, or merge materials by colour.

---

## 2. Per-entrance specs

### Dragon Lair (`dragon_lair`)

- **Family:** dragon family (green/red/black dragons)
- **Look:** Scorched cliff (hill height-field + craggy boulders) with a 4 m pointed **maw** lined with 6 hanging fangs and 2 tusks, two huge curved horns on the cliff top, a dragon skull and ribcage in a scorched, ember-strewn clearing, dull ember glow deep in the throat.
- **Triangles:** 1495 (budget 3000) | **OSRS review:** 8.5/10 - Strong silhouette (horns + fangs), deep dark maw, scorched ground, bones read at a glance.
- **Footprint (bounds):** x -7.3 .. 7.6, y -4.7 .. 10.5, height 9.4 m (~15 x 15 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 4.0 m wide x 4.2 m tall, passage 3.4 m deep, floor at z = 0.0
- **Trigger `TRIGGER_door`:** centre (0, 1.2, 1.3), size (3.6, 1.4, 2.6)
- **Collision boxes:** `COL_cliff_left`, `COL_cliff_right`, `COL_cliff_back`, `COL_skull`, `COL_ribcage`
- **Palette:** rock `#4d433c`, ash `#6b625a`, char `#2b2623`, scorch `#332c28`, bone `#cfc3a0`, horn `#bfb49a`, horn_dark `#8f8570`, socket `#221e19`, ember `#d0662e`, ember_deep `#8c3b2a`, interior `#221a16`, interior_deep `#120d0b`, void_black `#070606`
- **Glowing (emissive) colours:** ember, ember_deep
- **Files:** `blender_scripts/dragon_lair.py`, `blend/dragon_lair.blend`, `glb/dragon_lair.glb`, `bam/dragon_lair.bam`, `json/dragon_lair.json`, `images/dragon_lair_concept.png`, `panda_renders/dragon_lair_panda.png`, `sprites/<view>/dragon_lair_<size>.png` + `dragon_lair.json`
- **Review history:** v1 7/10: maw too narrow, horn growth-rings read as plates, box skull -> v2 8.5/10: 4 m maw with 6 fangs, clean horns, proper dragon skull, darker throat + ember glow

### Goblin Cave (`goblin_cave`)

- **Family:** goblin family (grunt, shaman)
- **Look:** Earth bank merged into a grassy hill; crude **timber frame** (two leaning posts, lashed lintel, crooked second beam, plank cladding) round a 2.2 x 2.6 m hole; horned skull on the lintel, two torches, painted horned **totem** on the left, **skulls on stakes**, broken plank door and crate.
- **Triangles:** 1579 (budget 2500) | **OSRS review:** 8.5/10 - Crude, chunky, readable; dark passage clearly goes in.
- **Footprint (bounds):** x -6.3 .. 6.6, y -2.9 .. 8.9, height 5.0 m (~13 x 12 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 2.2 m wide x 2.6 m tall, passage 2.6 m deep, floor at z = 0.0
- **Trigger `TRIGGER_door`:** centre (0, 0.9, 1.2), size (2.0, 1.2, 2.4)
- **Collision boxes:** `COL_bank_left`, `COL_bank_right`, `COL_mound`, `COL_totem`
- **Palette:** earth `#6b5440`, grass `#5f6d3a`, rock `#7b776c`, wood `#6b4c30`, wood_dark `#47331f`, rope `#a08a5c`, bone `#d6cdb2`, socket `#221e19`, paint_red `#8c3b2a`, paint_ochre `#a3823f`, goblin `#6e7b3c`, interior `#2e2620`, interior_deep `#17120f`, flame `#e0a542`, void_black `#070606`
- **Glowing (emissive) colours:** flame
- **Files:** `blender_scripts/goblin_cave.py`, `blend/goblin_cave.blend`, `glb/goblin_cave.glb`, `bam/goblin_cave.bam`, `json/goblin_cave.json`, `images/goblin_cave_concept.png`, `panda_renders/goblin_cave_panda.png`, `sprites/<view>/goblin_cave_<size>.png` + `goblin_cave.json`
- **Review history:** v1 6/10: flat box facade + tiled grass slabs (David's 'pasted-on box' failure) -> v2 8.5/10: faceted earth bank merged into a hill, timber frame, torches, totem, skulls on stakes

### Skeleton Crypt (`skeleton_crypt`)

- **Family:** undead family (skeleton warrior/mage, wraith, ghoul)
- **Look:** Stone **mausoleum** with gabled roof, skull pediment and 4-pillar portico; **steps go down** (7 steps, to z = -1.5) between iron-railed walls to a round-arched doorway with a **cracked, half-open stone door** (one leaf ajar, one broken with fallen chunks), facade cracks, moss, necrotic-teal urn flames, gravestones, sarcophagus lid.
- **Triangles:** 1863 (budget 3000) | **OSRS review:** 8.0/10 - Reads as a mausoleum with steps going down to a cracked, half-open door. Could take more weathering/moss later.
- **Footprint (bounds):** x -4.8 .. 4.9, y -6.7 .. 7.4, height 6.3 m (~10 x 14 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 2.2 m wide x 3.4 m tall, passage 3.0 m deep, floor at z = -1.5
- **Trigger `TRIGGER_door`:** centre (0, 0.9, -0.3), size (1.8, 1.2, 2.4)
- **Collision boxes:** `COL_stair_wall_left`, `COL_stair_wall_right`, `COL_mausoleum`, `COL_front_wall_left`, `COL_front_wall_right`, `COL_pillar_-3.3`, `COL_pillar_-1.9`, `COL_pillar_+1.9`, `COL_pillar_+3.3`
- **Palette:** stone `#8a8578`, stone_dark `#6c685e`, roof `#5d5a55`, slab `#9d978a`, moss `#5f6d3a`, door `#77736a`, crack `#1d1a18`, bone `#d6cdb2`, socket `#221e19`, iron `#505254`, necro `#86d1b8`, interior `#27241f`, interior_deep `#121110`, void_black `#070606`
- **Glowing (emissive) colours:** necro
- **Ground cut-out:** centre [0, -1.5], size [2.6, 9.0] m - stairwell + passage: lower/hide terrain here in 3D
- **Files:** `blender_scripts/skeleton_crypt.py`, `blend/skeleton_crypt.blend`, `glb/skeleton_crypt.glb`, `bam/skeleton_crypt.bam`, `json/skeleton_crypt.json`, `images/skeleton_crypt_concept.png`, `panda_renders/skeleton_crypt_panda.png`, `sprites/<view>/skeleton_crypt_<size>.png` + `skeleton_crypt.json`
- **Review history:** v1 7/10: stairwell hidden by ground, plain -> v2 8/10: ground cut-out, iron railings, roof contrast, pilasters, sarcophagus lid, skulls

### Spider Nest (`spider_nest`)

- **Family:** spider family (giant spider, broodmother)
- **Look:** Rocky **burrow** in a dark rock mound with a ring of rim boulders round a low round 2.8 m mouth; **funnel web** radiating from the mouth plus corner webs, pale **egg-sac** clusters either side, a wrapped cocoon, red eyes glinting inside, husks and bones on trampled dirt.
- **Triangles:** 1693 (budget 2500) | **OSRS review:** 8.0/10 - Mouth, funnel web and egg sacs read; web strands are chunky 'sticks' by design so they survive at sprite sizes.
- **Footprint (bounds):** x -6.1 .. 6.1, y -3.4 .. 8.9, height 4.8 m (~12 x 12 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 2.8 m wide x 2.6 m tall, passage 2.8 m deep, floor at z = 0.0
- **Trigger `TRIGGER_door`:** centre (0, 1.0, 1.1), size (2.3, 1.2, 2.2)
- **Collision boxes:** `COL_rim_left`, `COL_rim_right`, `COL_mound`
- **Palette:** rock `#57504a`, dirt `#5a4a3a`, moss `#4f5a36`, web `#cfcabc`, egg `#d8d0b8`, egg_spot `#9a8458`, cocoon `#b8ae96`, bone `#bdb59c`, socket `#221e19`, eye `#c23a26`, interior `#221d19`, interior_deep `#100d0b`, void_black `#070606`
- **Glowing (emissive) colours:** eye
- **Files:** `blender_scripts/spider_nest.py`, `blend/spider_nest.blend`, `glb/spider_nest.glb`, `bam/spider_nest.bam`, `json/spider_nest.json`, `images/spider_nest_concept.png`, `panda_renders/spider_nest_panda.png`, `sprites/<view>/spider_nest_<size>.png` + `spider_nest.json`
- **Review history:** v1 5/10: rim boulders + mound skirt blocked the mouth -> v2 6/10: mouth still hidden, web sheets looked like paper -> v3 8/10: skirt fix, rim boulders pushed out, funnel web + corner webs, big egg clusters

### Void Rift (`void_rift`)

- **Family:** void family (void spawn, void brute)
- **Look:** Cracked octagonal dark-stone platform; a 2.7 x 3.7 m elliptical **portal** with a glowing rim and bands that darken to a near-black core (the 'interior'), framed by jagged stone blocks and a crown of **dark crystal shards** leaning outward, glowing runes and small shards, floating rocks/shards, two ruined pillars.
- **Triangles:** 1555 (budget 3000) | **OSRS review:** 8.5/10 - Glowing purple portal with a dark core (the 'interior'), dark crystal crown - strongest silhouette in the set.
- **Footprint (bounds):** x -4.9 .. 4.7, y -4.2 .. 4.7, height 7.2 m (~10 x 9 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 2.7 m wide x 3.7 m tall (portal plane - no passage; the dark core is the 'interior')
- **Trigger `TRIGGER_door`:** centre (0, -0.2, 1.55), size (2.2, 0.8, 2.4)
- **Collision boxes:** `COL_platform_left`, `COL_platform_right`, `COL_crystals_back`
- **Palette:** stone `#3f3b46`, stone_edge `#57525e`, crystal `#3a3150`, crystal_lt `#5b4b7a`, crystal_dk `#241f33`, rim `#8a52b8`, glow `#b56ad9`, glow_mid `#6c3b99`, core `#2a1543`, rune `#b56ad9`, rock `#34303a`, interior `#2a231e`, interior_deep `#15110f`, void_black `#070606`
- **Glowing (emissive) colours:** rim, glow, glow_mid, core, rune
- **Files:** `blender_scripts/void_rift.py`, `blend/void_rift.blend`, `glb/void_rift.glb`, `bam/void_rift.bam`, `json/void_rift.json`, `images/void_rift_concept.png`, `panda_renders/void_rift_panda.png`, `sprites/<view>/void_rift_<size>.png` + `void_rift.json`
- **Review history:** v1 8/10 (1.1k tris) -> v2 8.5/10: outer shard ring, ruin pillars, floating shards, smoother portal; Panda emission restored in loader

### Giant's Cavern (`giants_cavern`)

- **Family:** giant family (hill/ice giant, golem)
- **Look:** Huge stacked-**boulder archway** (6 x 7.3 m opening) in a mossy rock hill; **giant-sized double door** of planks, iron bands and rivets with a huge ring knocker - right leaf shut, left leaf swung open so the dark cavern shows; doorstep slab, stepping stones, giant club, huge bone, hide banner with skull.
- **Triangles:** 1685 (budget 4000) | **OSRS review:** 8.0/10 - Scale reads (1.8 m figure is tiny next to the 7.3 m arch and iron-banded door). Right-hand arch boulders still overlap the shut leaf a little from this angle.
- **Footprint (bounds):** x -10.1 .. 10.1, y -5.0 .. 14.6, height 13.6 m (~20 x 20 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 6.0 m wide x 7.3 m tall, passage 4.0 m deep, floor at z = 0.0
- **Trigger `TRIGGER_door`:** centre (-1.5, 1.8, 1.5), size (2.8, 1.2, 3.0)
- **Collision boxes:** `COL_arch_left`, `COL_arch_right`, `COL_door_right_leaf`, `COL_hill`
- **Palette:** boulder `#7b776c`, boulder_dk `#5b584f`, moss `#5f6d3a`, grass `#63703d`, wood `#6b4c30`, wood_dk `#47331f`, iron `#505254`, rivet `#35373a`, bone `#bdb59c`, hide `#7d5b43`, rope `#a08a5c`, socket `#221e19`, interior `#27231f`, interior_deep `#12100e`, void_black `#070606`
- **Files:** `blender_scripts/giants_cavern.py`, `blend/giants_cavern.blend`, `glb/giants_cavern.glb`, `bam/giants_cavern.bam`, `json/giants_cavern.json`, `images/giants_cavern_concept.png`, `panda_renders/giants_cavern_panda.png`, `sprites/<view>/giants_cavern_<size>.png` + `giants_cavern.json`
- **Review history:** v1 5/10: mound skirt plate covered the door, arch boulders blocked the opening -> v2 7/10: open leaf hidden from the 3/4 camera -> v3 8/10: open leaf moved to the camera side, boulders kept outside the opening, stepping stones

### Wolf Den (`wolf_den`)

- **Family:** wolf family (grey/dire wolf)
- **Look:** Grassy **hillside** with a gnarled tree on top whose **roots** spill down over a 2.4 m round den mouth; **claw scratch marks** on a boulder and the earth bank, gnawed bones, deer skull, fur tufts, trampled dirt, fallen log, grass tufts.
- **Triangles:** 1585 (budget 2500) | **OSRS review:** 8.0/10 - Gnarled tree + roots over a dark den mouth, claw marks visible on the rock and bank.
- **Footprint (bounds):** x -6.5 .. 6.5, y -3.3 .. 8.9, height 8.4 m (~13 x 12 m; the back of the hill/cliff is the deep +Y part)
- **Walkable opening:** 2.4 m wide x 2.3 m tall, passage 2.6 m deep, floor at z = 0.0
- **Trigger `TRIGGER_door`:** centre (0, 1.0, 1.0), size (1.9, 1.2, 2.0)
- **Collision boxes:** `COL_bank_left`, `COL_bank_right`, `COL_hill`, `COL_scratched_rock`
- **Palette:** earth `#6b5440`, grass `#5f6d3a`, grass_dk `#4d5a30`, root `#5a4632`, bark `#4f3d2c`, leaf `#4f5f33`, rock `#7c776e`, bone `#c1b8a5`, scratch `#231f1c`, fur `#57524b`, socket `#221e19`, interior `#2a221c`, interior_deep `#140f0c`, void_black `#070606`
- **Files:** `blender_scripts/wolf_den.py`, `blend/wolf_den.blend`, `glb/wolf_den.glb`, `bam/wolf_den.bam`, `json/wolf_den.json`, `images/wolf_den_concept.png`, `panda_renders/wolf_den_panda.png`, `sprites/<view>/wolf_den_<size>.png` + `wolf_den.json`
- **Review history:** v1 7.5/10 (1.3k tris, sparse) -> v2 8/10: fallen log, flank roots, extra rocks/skull


---

## 3. Blender scripting workflow (how Cursor edits and re-runs)

### 3.1 Install Blender headlessly (Linux, once)

```bash
# official portable LTS tarball (apt's Blender is usually too old)
mkdir -p ~/apps && cd ~/apps
curl -LO https://download.blender.org/release/Blender4.2/blender-4.2.23-linux-x64.tar.xz
python3 -c "import tarfile; tarfile.open('blender-4.2.23-linux-x64.tar.xz').extractall('.')"   # or: tar xf (needs xz)
ln -sfn blender-4.2.23-linux-x64 blender && ln -sfn ~/apps/blender/blender ~/bin/blender
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libxi6 libsm6 libxrender1 libxxf86vm1 libxfixes3   # EEVEE renders
blender --background --version        # -> Blender 4.2.23 LTS
```

Windows/macOS: install Blender 4.2 LTS normally, then use the full path to `blender(.exe)` in the commands below.

### 3.2 Build one entrance

```bash
cd dungeons
blender --background --python blender_scripts/wolf_den.py                 # full: blend + glb + json + concept render
blender --background --python blender_scripts/wolf_den.py -- --no-render  # fast: skip the EEVEE render
python3 tools/build_all.py --only wolf_den    # the same, plus blend2bam, Panda render, sprites, contact sheet
python3 tools/build_all.py                    # all seven
/workspace/monsters_venv/bin/python tools/verify_pack.py   # automated checks (must say PASS for every row)
```

Each script is deterministic because of its seed, so reruns produce identical geometry. Change `seed=` for a new rock layout.

### 3.3 How a script is structured

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osrs_kit import Kit

PALETTE = {"earth": "#6b5440", "grass": "#5f6d3a", "root": "#5a4632", ...}   # sRGB hex
k = Kit("wolf_den", PALETTE, seed=79, title="Wolf Den", emissive={})          # emissive: {key: strength}

W, SPRING, DEPTH = 2.4, 1.1, 2.6          # opening width, wall height before the arch, passage depth
k.archway(W, SPRING, DEPTH, outer_w=6.4, outer_h=3.1, front="earth", shape="round")   # solid wall + dark passage
k.mound(0, 3.0, 6.4, 5.8, 4.4, "earth", mat_top="grass", crop_y=0.35)                 # hill BEHIND the wall
k.rock((3.3, -0.3, 0.4), (0.9, 0.8, 0.7), "rock")                                     # props...
k.collider("bank_left", (-2.4, 1.4, 1.6), (2.4, 3.0, 3.2))   # invisible solid box: centre, size (m)
k.trigger((0, 1.0, 1.0), (W - 0.5, 1.2, 2.0))                # ONE doorway trigger, inside the opening
k.figure((1.3, -2.3, 0))                                      # 1.8 m reference figure (concept render only)
k.finish()                                                    # build, save .blend, export .glb/.json, render
```

### 3.4 Kit API (`blender_scripts/osrs_kit.py`)

| Call | What it makes |
|---|---|
| `Kit(key, palette, seed, title, emissive)` | Starts an empty scene. Palette keys become materials plus `.d`/`.l` variants |
| `box(loc, size, mat, rot=(0,0,0), taper=1, skew=(0,0))` | Box centred on `loc`. `taper` scales the top face |
| `cyl(base, r0, r1, h, mat, segs=6, rot=...)` / `cone(base, r, h, mat, segs=5)` | Tapered prism or cone standing on `base`. Hanging spikes use `rot=(180,0,0)` |
| `rock(loc, size, mat, subdiv=1, rough=0.22)` | Jittered icosphere boulder (80 tris at subdiv 1) |
| `tube(points, radii, mat, segs=5)` + `arc_pts(a, ctrl, b, n)` | Tapered tube along a curve: horns, roots, ribs, bones, webs |
| `archway(width, spring, depth, outer_w, outer_h, front, shape='round'/'pointed'/'flat', z0, y0, jag, bulge)` | **The key piece.** A solid faceted wall with a walk-through opening, a passage lined dark to black, a floor, and a black back plane. Registers the opening in json |
| `mound(cx, cy, rx, ry, h, mat, mat_top, crop_y)` | Faceted hill height-field. `crop_y` cuts it at the wall and drops a skirt, but never inside the wall's width |
| `disc(loc, r, mat)` | Flat ground decal (scorch, dirt path) |
| `skull(loc, s)`, `torch(loc)`, `scratches(x, y, z, n)`, `web(cx, cy, cz, r, a0, a1)` | Small props |
| `collider(name, centre, size)` / `trigger(centre, size)` | Gameplay boxes -> json + `COLLISION` collection (passive rigid-body boxes -> CollisionBoxes in the .bam) |
| `k.meta[...]` | Extra json fields (e.g. `ground_cutout`) |
| `k.cam_target`, `k.cam_scale`, `k.cam_margin` | Optional concept-camera tweaks (default: auto-fit) |
| `blender ... -- --no-render / --no-export / --out DIR` | Script arguments |

### 3.5 Editing rules for Cursor

1. **The scripts are the source of truth.** Don't hand-edit `.blend`/`.glb` files. Change the script and re-run it.
2. Change **one entrance at a time**. Re-run it, then look at `images/<key>_concept.png` **and** `panda_renders/<key>_panda.png` before touching the next one.
3. Keep the doorway clear: no prop, web, rock or door leaf inside `openings[0]` (width x height) apart from things lying flat on the floor. The trigger box must stay inside the opening.
4. Keep the trigger count at exactly one (`TRIGGER_door`). Colliders must never cover the doorway.
5. Stay within the triangle budget (section 1). `verify_pack.py` fails outside 1.4k to 4k.
6. Only add colours through the palette dict (muted, sRGB hex). No textures. Glow only via `emissive`.
7. Keep front = -Y and origin = doorway threshold. The game positions and rotates the model, not the script.
8. After changes: `python3 tools/build_all.py --only <key>`, then `verify_pack.py`, then update `review/scores.json` and re-run `make_contact_sheet.py`.

---

## 4. Export and load

### 4.1 glTF (`.glb`) via panda3d-gltf

```bash
pip install panda3d-gltf        # auto-registers a .gltf/.glb loader for Panda3D >= 1.10.4
```

PRC (config) line, **required** for this style:
```
gltf-legacy-materials true      # plain fixed-function Materials, works with set_shader_off()
```

Load through the helper, which is identical for `.glb` and `.bam`:
```python
from entrance_loader import load_entrance, add_entrance_collision, setup_osrs_lighting, ENTRANCE_SUN_HPR
model, meta = load_entrance(base.loader, "assets/dungeons/glb/goblin_cave.glb")
model.reparent_to(render)
model.set_pos(x, y, z)       # the OLD entrance's position
model.set_h(heading)         # 0 = front faces -Y
```

Three things `load_entrance()` fixes for you. They were found while verifying this pack in Panda3D:
1. **Too dark:** glTF colours are linear, and the fixed-function pipeline does not convert them. The loader converts material colours back to sRGB so they match the hex palette.
2. **Washed out / grey:** glTF has no ambient colour, so Panda treats the surface as white under ambient light. The loader sets ambient = diffuse. (Loaded materials are attrib-locked, so it builds fresh ones.)
3. **No glow:** panda3d-gltf's legacy mode drops emission. The loader restores full-bright emission for the palette keys listed in json `emissive`.

If you do not use the helper, you must do those three steps yourself. `model.set_material_off(1)` is only for vertex-colour workflows. It is not needed here, because colour lives in materials.

Offline conversion without Blender: `gltf2bam glb/goblin_cave.glb goblin_cave.bam` (ships with panda3d-gltf). The collision boxes then come from json via `add_entrance_collision()`.

### 4.2 `.bam` via blend2bam

```bash
pip install panda3d-blend2bam
blend2bam -m legacy --blender-dir ~/apps/blender --invisible-collisions-collection COLLISION \
          blend/goblin_cave.blend bam/goblin_cave.bam
```

* `-m legacy` gives fixed-function materials. Still load through `load_entrance()` for the sRGB, ambient and emission fixes.
* The `COLLISION` collection's passive rigid-body boxes become **invisible `CollisionNode`s** (`COL_*` solids and `TRIGGER_door`) inside the .bam. `add_entrance_collision()` reuses them rather than adding duplicates.
* The concept camera, sun, ground and figure live in the separate `CONCEPT_RENDER` scene, so they never end up in the .bam.

### 4.3 Which one to ship

A 3D Panda3D world should ship `.bam` (fastest load, includes collisions). You can also ship `.glb` + json if you'd rather not depend on blend2bam. A 2D pygame world should ship the sprites (section 6) and never needs Panda3D at runtime.

---

## 5. Collision approach

The shapes are simple on purpose. Visual meshes are **never** used for collision.

* **Solid boxes** (`COL_*`): invisible axis-aligned boxes covering the walls, hill and big props. The player can't walk through them, and **none of them cover the doorway**.
* **Doorway trigger** (`TRIGGER_door`): one box just inside the opening (floor to about head height). When the player enters it, call the game's **existing** enter-dungeon function with the entrance's existing id. Do not write a new one.
* All boxes are in model space (metres, front -Y) and live in `json/<key>.json`, the `.blend` `COLLISION` collection and the `.bam`.

### 5.1 Panda3D (3D route)

```python
from panda3d.core import CollisionTraverser, CollisionHandlerEvent, CollisionNode, CollisionSphere, BitMask32
SOLID, TRIG = BitMask32.bit(1), BitMask32.bit(2)

solids, trig_np = add_entrance_collision(model, meta, solid_mask=SOLID, trigger_mask=TRIG)
trig_np.set_python_tag("entrance_id", existing_entrance_id)   # the id the OLD code already uses

handler = CollisionHandlerEvent()
handler.add_in_pattern("%fn-into-%in")
base.accept("player-into-TRIGGER_door", lambda entry: existing_enter_dungeon(   # EXISTING function
    entry.get_into_node_path().get_python_tag("entrance_id")))
# the player's existing collider: from-mask includes TRIG (and SOLID if it uses a pusher)
```

If the game already has its own trigger (a distance check, tile check or server message), **keep it** and use only the solid boxes, or skip collisions entirely. Positions and triggers stay as they are.

### 5.2 2D / pygame route

Use the world-space footprint of the trigger box (x/y from json, rotated by the entrance heading), or the sprite's `trigger_px` polygon, only if the old code has no trigger of its own. In most cases the old tile/rect trigger stays exactly as it is, and only the drawing changes.

`entrance_loader.point_in_box(p, box)` is a tiny helper for axis-aligned checks.

### 5.3 Crypt note

The Skeleton Crypt stairwell goes down to z = -1.5. In a 3D terrain, hide or lower the ground inside json `ground_cutout`. A 2D game needs nothing.

---

## 6. 2D sprite route (if the game draws the world with pygame)

```bash
/workspace/monsters_venv/bin/python tools/render_sprites.py                              # all views and sizes
/workspace/monsters_venv/bin/python tools/render_sprites.py --only goblin_cave --views front34 --sizes 96 192
```

* **Views:** orthographic, so a sprite looks the same anywhere on the map.
  * `front34`: straight on, 35 deg down (top-down 3/4 RPG)
  * `iso`: front-right 45 deg, 30 deg down
  * `osrs`: front-right 35 deg, 30 deg down, the same angle as the concepts
  
  Pick the one matching the game's existing building sprites.
* **Sizes:** `--sizes` sets the sprite width in px (default 128/256/512). Height follows the shape. Transparent RGBA PNG, supersampled 3x then downscaled with LANCZOS.
* **Anchors** in `sprites/<view>/<key>.json`, per size:
  * `origin_px`: the model origin (doorway threshold at ground level)
  * `door_px`: trigger centre at ground level
  * `trigger_px`: trigger footprint polygon
  * `metres_per_px`

```python
# pygame: draw the new sprite where the OLD entrance was drawn, keep the old trigger logic
spr = pygame.image.load("assets/dungeons/sprites/front34/goblin_cave_256.png").convert_alpha()
ax, ay = anchors["sizes"]["256"]["origin_px"]
if USE_NEW_ENTRANCES:
    screen.blit(spr, (screen_x - ax, screen_y - ay))     # screen_x/y = old entrance anchor on screen
else:
    old_draw_entrance(...)                              # unchanged old code
```

* **Size choice:** match the old sprite's on-screen size. The metre scale is in `metres_per_px`, and at 256 px wide a 13 m entrance is about 20 px per metre. Keep the player sprite about 1.8 m tall at that scale.
* **Depth sorting:** sort by the entrance's ground y (the `origin_px` row) the same way the old code sorts buildings.
* **Lighting:** baked into the sprite (the monster-pack OSRS light). Don't recolour it at runtime.
* To re-bake after editing a script, run `python3 tools/build_all.py --only <key>` (includes sprites).

---

## 7. Verification (done for this pack)

* `tools/verify_pack.py` checks every entrance, all **PASS** (see `review/verify_report.txt`):
  * `.glb` loads via panda3d-gltf with `gltf-legacy-materials`
  * `.bam` loads and carries all `COL_*` + `TRIGGER_door` CollisionNodes
  * no textures, triangles within budget
  * a 0.35 m player sphere walking straight in **fires the trigger without hitting a solid**
  * walking into the wall beside the door **is blocked**
* `tools/panda_render.py` renders each `.glb` in Panda3D with the monster pack's `setup_osrs_lighting()` from the **same camera** as the Blender concept (camera stored in json `concept_camera`). The side-by-side contact sheet shows the in-engine look matches the concept: colours, facets, dark interiors and glow.
* **OSRS-look review:** each entrance was scored out of 10, and anything under 8 was rebuilt. Scores and history are in `review/scores.json` and on the contact sheet.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `Couldn't open libEGL.so.1` when rendering | `sudo apt-get install libegl1 libgl1` (EEVEE needs EGL even in background mode) |
| `tar: xz: Cannot exec` | Extract with Python: `python3 -c "import tarfile; tarfile.open('x.tar.xz').extractall('.')"` |
| Model too dark in Panda | Load via `load_entrance()` (sRGB fix) |
| Model grey or washed out | ambient = diffuse (done by `load_entrance()`) |
| Portal or embers not glowing | Emission restore (done by `load_entrance()` using json `emissive`) |
| Faces look smooth | `render.set_shader_off()` + flat `ShadeModelAttrib`. Never `set_shader_auto()` |
| Lit from behind | Entrances face -Y. Use `ENTRANCE_SUN_HPR = (20, -45, 0)`, or rotate the model with `set_h` |
| Something blocks the doorway | A prop is inside `openings[0]`. Move it out, re-run, then check `verify_pack.py` |
| blend2bam can't find Blender | `--blender-dir <folder containing the blender binary>` |
