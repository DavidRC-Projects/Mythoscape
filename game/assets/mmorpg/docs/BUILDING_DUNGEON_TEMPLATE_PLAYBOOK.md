# Building & Dungeon Geometry Playbook

**Purpose:** Apply OSRS-aligned extruded volume geometry to all Mythoscape buildings and dungeons.

**Target audience:** Future Cursor cloud agents converting buildings to match the gold-standard templates.

**Last updated:** Sept 24, 2026 (Farmhouse + Void Sanctum gold standards complete)

---

## Goal

Convert buildings/dungeons from flat facades to **ONE extruded volume** with:

1. ✅ **Extruded volumes** - Clear 3D depth, not flat facades with pasted objects
2. ✅ **Recessed entrances** - Doorways carved INTO wall geometry, showing interior surfaces
3. ✅ **OSRS-inspired structure** - Structural/layout reference from Old School RuneScape (do NOT copy Jagex assets/IP)
4. ✅ **Exterior hiding** - Dungeon/crypt exteriors hide when player enters (classic overworld → interior transition)
5. ✅ **Map expansion OK** - Prioritize correct geometry over fitting old footprint size
6. ✅ **Pixel-art aesthetic** - Maintain Mythoscape's pixel-art style and stone/wood palette

**Design authority:** See `OSRS_DESIGN_REFERENCE.md` for complete OSRS alignment principles.

---

## Gold Standard Templates

### 1. Farmhouse (Village Home Template)

**Asset file:**
```
/workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/cottage_se.png
```
- **Size:** 383 KB (OSRS-aligned additive depth)
- **Building ID:** `cottage_se`
- **Kind:** `house`
- **Material:** Wood

**Code implementation:**
```python
# File: /workspace/Mythoscape/game/assets/characters/building_shell3d.py
# Function: draw_house_shell(dest, footprint, kind="house", ...)
# Lines: ~377-560
```

**Content hooks:**
```python
# File: /workspace/Mythoscape/game/assets/mmorpg/client/content.py
# Search for: "Farmhouse" or style=1 houses
```

**Map location (for testing):**
- Starting village
- Floor tiles: 16-22 (x), 21-27 (y)
- Label: "Farmhouse"

### 2. Void Sanctum (Dungeon Template)

**Asset file:**
```
/workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/void_sanctum.png
```
- **Size:** 543 KB (OSRS-aligned additive depth)
- **Building ID:** `void_sanctum`
- **Kind:** `crypt` (applies to all dungeons)
- **Material:** Stone

**Code implementation:**
```python
# File: /workspace/Mythoscape/game/assets/characters/building_shell3d.py
# Function: draw_crypt_shell(dest, footprint, kind="crypt", ...)
# Lines: ~560-740
```

**Interior features:**
```python
# File: /workspace/Mythoscape/game/assets/characters/dungeon_interior_3d.py
# Functions: draw_stone_pillar_3d(), draw_brazier_3d(), draw_dungeon_props()
```

**Client integration:**
```python
# File: /workspace/Mythoscape/game/assets/mmorpg/client/client.py
# Line 5356: Exterior hiding when inside
# Line 5120-5137: 3D interior props rendering
```

**Map location (for testing):**
- SE of Stonehaven city
- Coords: ~137, 79
- Label: "Void Sanctum"
- Zone: "shadow_crypt"

---

## OSRS-Aligned Additive Depth Model

### Core Principle

**ADDITIVE, not INSET:**
- Front width maintains full facade presence
- Side depth ADDS beyond front (not subtracted from footprint)
- Total width = front_w + side_w (~125% of original footprint)

### Parameters (Apply to ALL buildings/dungeons)

```python
# File: building_shell3d.py
# In both draw_house_shell() and draw_crypt_shell()

# ADDITIVE DEPTH MODEL (David's constraint relaxation: map can expand)
# Front wall: use 75% of footprint width for solid facade
front_w = max(8, int(fw * 0.75))

# Side depth: ADD 50% more depth for strong extrusion (extends beyond footprint)
side_w = max(24, int(fw * 0.50))

# TALL vertical rise for dramatic 3/4 view (40% of height)
dy = max(22, int(fh * 0.40))

# Lower wall start for more visible height
wall_top = fy + int(fh * 0.12)

# Side face - extends BEYOND footprint by side_w for OSRS-like depth
# CRITICAL: Do NOT constrain to fw! Let it extend to front_w + side_w
sr_top = (fx + front_w + side_w, wall_top - dy)
sr_bot = (fx + front_w + side_w, ground)
```

### Entrance Recess Parameters

```python
# File: building_shell3d.py
# Function: _recessed_entrance()

# Wood doors (houses, shops):
depth = max(28, min(45, int(dw * 0.4)))  # 28-45px deep (40% of door width)
jamb = max(16, min(28, depth - 4))       # 16-28px wide interior surfaces
frame = max(7, int(dw * 0.12))           # 12% door width frame

# Stone doors (dungeons, crypts):
depth = max(24, min(40, int(dw * 0.35)))  # 24-40px deep
jamb = max(18, min(32, depth - 2))        # 18-32px wide interior surfaces
```

---

## Step-by-Step Agent Prompt

**Use this prompt when converting a building/dungeon to OSRS-aligned geometry:**

```
I need to convert [BUILDING_NAME] to match the gold-standard OSRS-aligned geometry.

Gold standard reference:
- Farmhouse template: cottage_se.png (house kind)
- Void Sanctum template: void_sanctum.png (crypt/dungeon kind)

Target building:
- Name: [BUILDING_NAME]
- Asset ID: [ASSET_ID]
- Kind: [house/crypt/shop/smithy/etc]
- Material: [wood/stone]
- Current PNG path: /workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/[ASSET_ID].png

Steps:
1. Verify the target building uses the correct function in building_shell3d.py:
   - Houses/shops/smithies → draw_house_shell()
   - Crypts/dungeons → draw_crypt_shell()

2. Confirm the function already has OSRS-aligned additive depth parameters:
   - front_w = 75% of footprint
   - side_w = 50% of footprint (ADDED beyond front)
   - dy = 40% of height
   - wall_top = 12% from top
   - sr_top/sr_bot use (fx + front_w + side_w) WITHOUT constraint to fw

3. If parameters are correct, regenerate the asset:
   ```bash
   cd /workspace/Mythoscape/game/assets/mmorpg/tools
   SDL_VIDEODRIVER=dummy python3 bake_building_sprite.py [ASSET_ID]
   ```

4. Verify the PNG file size INCREASES (more geometry = larger file):
   ```bash
   ls -lh /workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/[ASSET_ID].png
   ```

5. For dungeons/crypts ONLY, verify exterior hiding is working:
   - Check client.py line 5356 has: `if inside and b.get("kind") in ("crypt", "dungeon"): continue`

6. If dungeon needs 3D interior props (optional):
   - Study dungeon_interior_3d.py
   - Add zone-specific prop rendering in client.py (follow shadow_crypt example)

7. Test in-game:
   - Find the building on the map (check content.py or world_map.py for location)
   - Verify side wall is VERY prominent (~40-50% of total width)
   - Verify entrance is deeply recessed with visible interior surfaces
   - Verify reads as ONE solid volume, not flat facade
   - For dungeons: verify exterior hides when entering

8. Commit changes:
   ```bash
   git add game/assets/mmorpg/client/assets/buildings/[ASSET_ID].png
   git commit -m "Convert [BUILDING_NAME] to OSRS-aligned geometry"
   ```

Visual acceptance:
- ✅ Side wall occupies ~40-50% of total building width
- ✅ Front wall maintains full facade (not shrunk)
- ✅ Entrance carved deeply INTO wall (not pasted in front)
- ✅ Roof covers full depth front-to-back
- ✅ Reads as ONE extruded volume (not cardboard planes)
```

---

## DO NOT List (Common Mistakes)

### ❌ DO NOT: Paste door box in front of wall
**Wrong approach:**
- Drawing door as separate 3D object pasted onto flat facade
- Door sits AT surface level, not IN wall

**Correct approach:**
- Use `_recessed_entrance()` function
- Door is carved opening WITH visible interior jamb surfaces
- Door panel sits INSIDE the opening, not at front surface

### ❌ DO NOT: Fix with outline tweaks only
**Wrong approach:**
- Adjusting polygon outlines
- Changing line colors/thickness
- Tweaking edge drawing

**Correct approach:**
- Change actual geometry parameters (front_w, side_w, dy)
- Regenerate entire asset with new geometry
- Outlines are secondary visual polish, not the fix

### ❌ DO NOT: Use inset/subtraction model
**Wrong approach:**
```python
side_w = int(fw * 0.45)
front_w = fw - side_w  # Front shrinks! ❌
```

**Correct approach:**
```python
front_w = int(fw * 0.75)  # Full facade
side_w = int(fw * 0.50)   # ADDED beyond
# Total = front_w + side_w ✅
```

### ❌ DO NOT: Constrain to original footprint
**Wrong approach:**
```python
sr_top = (fx + front_w + side_w, ...)
sr_top = (fx + fw, ...)  # Overridden to fw! ❌
```

**Correct approach:**
```python
sr_top = (fx + front_w + side_w, ...)  # Unconstrained ✅
# David: map can expand for correct geometry
```

### ❌ DO NOT: Apply shallow depth
**Wrong approach:**
- side_w < 30% of footprint
- dy < 25% of height
- depth < 20px entrance recess

**Correct approach:**
- side_w = 50% of footprint (OSRS prominence)
- dy = 40% of height (dramatic 3/4 view)
- depth = 28-45px (very deep recess)

### ❌ DO NOT: Leave dungeon exterior visible when inside
**Wrong approach:**
- Player sees exterior building shell while inside dungeon

**Correct approach:**
```python
# client.py line 5334
if inside and b.get("kind") in ("crypt", "dungeon"):
    continue  # Hide exterior completely
```

### ❌ DO NOT: Copy Jagex assets or IP
**Wrong approach:**
- Using OSRS textures, sprites, or assets directly
- Copying specific OSRS building designs pixel-for-pixel

**Correct approach:**
- Take structural/layout IDEAS only
- Use Mythoscape's own pixel-art palette
- Reference OSRS for proportions and depth principles

---

## Acceptance Checklist

**Before considering a building "complete," verify ALL criteria:**

### Geometry (Exterior)
- [ ] Front wall occupies ~75% of footprint width (full facade)
- [ ] Side wall adds ~50% beyond front (total ~125% of footprint)
- [ ] Side wall visually occupies ~40-50% of total building width
- [ ] Vertical rise (dy) is ~40% of building height
- [ ] Wall starts ~12% from top of footprint
- [ ] Roof peak is ~50% of building height
- [ ] Foundation wraps entire perimeter (front + side)
- [ ] Roof covers full depth front-to-back
- [ ] No gaps between front and side walls

### Entrance
- [ ] Door opening is carved INTO wall geometry
- [ ] Entrance depth is 28-45px (wood) or 24-40px (stone)
- [ ] Interior jamb surfaces are 16-28px wide and visible
- [ ] Door panel sits INSIDE opening, not at surface
- [ ] Dark throat/interior visible through opening
- [ ] Frame/arch surrounds opening (not floating)

### Visual Quality
- [ ] Building reads as ONE solid extruded volume
- [ ] NOT flat facade with pasted objects
- [ ] NOT separate cardboard planes at hard angles
- [ ] Side wall has clear perspective/depth
- [ ] Hard shading (not smooth gradients)
- [ ] Pixel-art aesthetic maintained
- [ ] Color palette matches Mythoscape style

### OSRS Alignment
- [ ] Proportions match OSRS reference (side ~40-50% of width)
- [ ] Depth is immediately obvious from standard camera angle
- [ ] Recessed entrance shows wall thickness (OSRS-style)
- [ ] Structure conveys solidity and volume

### Dungeons/Crypts ONLY
- [ ] Exterior walls hide completely when player enters
- [ ] `client.py` has `if inside and b.get("kind") in ("crypt", "dungeon"): continue`
- [ ] Entry/exit interaction still works
- [ ] Collision boundaries correct
- [ ] Interior space clearly visible when inside

### File Changes
- [ ] PNG asset file size INCREASED (confirms more geometry)
- [ ] Asset regenerated via `bake_building_sprite.py`
- [ ] No manual pixel editing of PNG files
- [ ] Committed with descriptive message

---

## How to Verify In-Game

### Step 1: Identify Building Location

**Method A: Search content.py**
```python
# File: /workspace/Mythoscape/game/assets/mmorpg/client/content.py
# Search for building name, asset ID, or style number
```

**Method B: Search world_map.py**
```python
# File: /workspace/Mythoscape/game/assets/mmorpg/server/world_map.py
# Look for building definitions with x0, y0, x1, y1 coordinates
```

**Method C: Test in starting village**
- Most houses are in starting village (visible immediately)
- Farmhouse example: tiles 16-22 (x), 21-27 (y)

### Step 2: Restart Client

**CRITICAL:** Client caches PNGs. Must restart to see new assets.

```bash
# If client is running, stop it first
# Then start fresh client to load new PNGs
```

### Step 3: Navigate to Building

**In-game:**
1. Move player character to building location
2. Approach from SOUTHEAST angle (best 3/4 view)
3. Stand 2-3 tiles away for full view

### Step 4: Visual Inspection Checklist

**Camera angle:** Southeast view (front + right side visible)

**Look for:**
- ✅ **Side wall prominence** - Should occupy ~40-50% of total building width
- ✅ **Front wall fullness** - Should be wide, not shrunk
- ✅ **Entrance depth** - Should see dark interior throat, wide jambs
- ✅ **Roof coverage** - Should extend fully front-to-back
- ✅ **Volume read** - Should look like ONE solid 3D block, not flat facade

**Red flags (FAILED):**
- ❌ Side wall is thin strip (<30% of width)
- ❌ Building looks like flat front plane + flat side plane
- ❌ Door looks pasted ON wall, not IN wall
- ❌ Roof doesn't cover side depth
- ❌ Visible gaps or seams between front/side
- ❌ Reads as "cardboard cutout" not solid volume

### Step 5: Dungeon-Specific Tests

**Test exterior hiding:**
1. Stand outside dungeon (see exterior building)
2. Walk through door to enter
3. **VERIFY:** Exterior walls vanish completely
4. **VERIFY:** Interior space/floor/entities visible
5. Exit through door
6. **VERIFY:** Exterior walls reappear

**Test interior props (if implemented):**
1. Enter dungeon
2. **VERIFY:** 3D stone pillars in corners (not flat)
3. **VERIFY:** Lit braziers with animated fire
4. **VERIFY:** Props have visible depth (front + side)
5. **VERIFY:** Atmospheric fire glow

### Step 6: Compare to Gold Standards

**Open gold standard PNGs for side-by-side comparison:**

```bash
# View Farmhouse reference
eog /workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/cottage_se.png

# View Void Sanctum reference
eog /workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/void_sanctum.png

# View your converted building
eog /workspace/Mythoscape/game/assets/mmorpg/client/assets/buildings/[YOUR_ASSET_ID].png
```

**Questions to ask:**
1. Does my building have similar side wall prominence as the gold standard?
2. Does my entrance depth match the gold standard recess?
3. Does my building read as ONE volume like the gold standard?
4. Would I accept my building if I were David?

### Step 7: Screenshot for Verification

**Take screenshot showing:**
- Full building from SE angle
- 2-3 tiles away
- Clear view of front + side walls
- Entrance visible

**Save to:**
```
/workspace/Mythoscape/building_verification_screenshots/[ASSET_ID]_[DATE].png
```

**Include in commit message or PR if needed.**

---

## Building Type Coverage

### Houses (use draw_house_shell)
- [ ] Farmhouse (cottage_se) - ✅ GOLD STANDARD
- [ ] Village cottages (other styles)
- [ ] City houses
- [ ] Player housing

### Shops (use draw_house_shell with kind override)
- [ ] General store
- [ ] Fishing shop
- [ ] Blacksmith shop (kind="smithy")
- [ ] Magic shop
- [ ] etc.

### Dungeons (use draw_crypt_shell)
- [ ] Void Sanctum (void_sanctum) - ✅ GOLD STANDARD
- [ ] Crypts
- [ ] Caves
- [ ] Underground dungeons
- [ ] Boss lairs

### Special Buildings (verify function used)
- [ ] Castle/fortress structures
- [ ] Temples/churches
- [ ] Guild halls
- [ ] Banks

---

## Troubleshooting

### Problem: Asset doesn't change after regeneration

**Causes:**
1. Client is caching old PNG
2. Wrong asset ID passed to bake script
3. Function parameters not actually changed

**Solutions:**
1. **Restart client** (most common fix)
2. Verify asset ID: `ls -l game/assets/mmorpg/client/assets/buildings/*.png | grep [ID]`
3. Check building_shell3d.py was saved before baking
4. Verify PNG file modification time: `ls -l --time-style=full-iso [PNG_PATH]`

### Problem: Building looks stretched or wrong aspect ratio

**Causes:**
1. Used wrong function (house vs crypt)
2. Material/kind mismatch
3. Footprint rect incorrect

**Solutions:**
1. Check which function is called for this building type
2. Verify `kind="house"` vs `kind="crypt"` parameter
3. Check content.py building definition for correct x0,y0,x1,y1

### Problem: Side wall not prominent enough

**Causes:**
1. Still using old parameters (side_w < 40%)
2. Constrained to fw instead of front_w + side_w
3. dy (vertical rise) too small

**Solutions:**
1. Verify: `side_w = max(24, int(fw * 0.50))`
2. Verify: `sr_top = (fx + front_w + side_w, wall_top - dy)` with NO override
3. Verify: `dy = max(22, int(fh * 0.40))`
4. Regenerate asset and restart client

### Problem: Entrance not deep enough

**Causes:**
1. Still using old depth parameters
2. Wrong door type (wood vs stone)
3. Door width (dw) calculation incorrect

**Solutions:**
1. Verify wood depth: `max(28, min(45, int(dw * 0.4)))`
2. Verify stone depth: `max(24, min(40, int(dw * 0.35)))`
3. Check _recessed_entrance() is being called
4. Verify door_frac calculation

### Problem: Dungeon exterior doesn't hide on entry

**Causes:**
1. Missing client.py check for inside + crypt/dungeon kind
2. Building kind is not "crypt" or "dungeon"
3. Player inside detection not working

**Solutions:**
1. Add to client.py line ~5334:
   ```python
   if inside and b.get("kind") in ("crypt", "dungeon"):
       continue
   ```
2. Check content.py: verify building has `"kind": "crypt"` or `"kind": "dungeon"`
3. Test `player_inside_building()` function

### Problem: File size didn't increase

**Causes:**
1. Parameters weren't actually changed
2. Asset was already at new geometry
3. Bake script used old code

**Solutions:**
1. Diff building_shell3d.py against last commit
2. Check git status before baking
3. Reload Python modules if bake script is cached

---

## Asset Baking Reference

### Single Asset
```bash
cd /workspace/Mythoscape/game/assets/mmorpg/tools
SDL_VIDEODRIVER=dummy python3 bake_building_sprite.py [ASSET_ID]
```

### Multiple Assets (Sequential)
```bash
cd /workspace/Mythoscape/game/assets/mmorpg/tools
for asset in cottage_se cottage_ne cottage_sw shop_general crypt_basic; do
    SDL_VIDEODRIVER=dummy python3 bake_building_sprite.py $asset
done
```

### Verify Asset Changed
```bash
# Check file size before
ls -lh game/assets/mmorpg/client/assets/buildings/[ASSET_ID].png

# Bake asset
cd game/assets/mmorpg/tools
SDL_VIDEODRIVER=dummy python3 bake_building_sprite.py [ASSET_ID]

# Check file size after (should be LARGER)
ls -lh game/assets/mmorpg/client/assets/buildings/[ASSET_ID].png

# View git diff stats
git diff --stat game/assets/mmorpg/client/assets/buildings/[ASSET_ID].png
```

---

## Commit Message Template

```
Convert [BUILDING_NAME] to OSRS-aligned geometry

Apply gold-standard additive depth model:
- Front: 75% of footprint (full facade)
- Side: +50% beyond front (OSRS prominence)
- Entrance: 28-45px deep recess (carved into wall)

Asset: [ASSET_ID].png
Kind: [house/crypt/shop/smithy]
Size: [OLD_KB] → [NEW_KB] (+[GROWTH]%)

Matches gold standards:
- Farmhouse (cottage_se.png) for houses
- Void Sanctum (void_sanctum.png) for dungeons

Verified:
- Side wall ~40-50% of total building width ✅
- Entrance deeply recessed with visible jambs ✅
- Reads as ONE extruded volume ✅
- OSRS-style structural alignment ✅

Location: [MAP_LOCATION or COORDS]
```

---

## Success Metrics

**Per building:**
- PNG file size increases by 15-25%
- Side wall occupies 40-50% of total width
- Entrance depth 28-45px (wood) or 24-40px (stone)
- Passes David's visual test (ONE volume, not flat)

**Project-wide:**
- All houses use same additive depth parameters
- All dungeons use same additive depth parameters
- All dungeons hide exterior on entry
- Consistent OSRS-inspired structure across all buildings
- No building uses old inset/flat geometry

---

## Related Documentation

**Core reference files:**
1. `OSRS_DESIGN_REFERENCE.md` - Complete OSRS alignment principles
2. `GOLD_STANDARD_TWO_BUILDINGS.md` - Farmhouse + Void Sanctum specs
3. `BUILDING_RENDERING_FIX.md` - Initial fix documentation (historical)
4. `FARMHOUSE_REBUILD.md` - Second pass documentation (historical)

**Code files:**
1. `/workspace/Mythoscape/game/assets/characters/building_shell3d.py` - Core geometry
2. `/workspace/Mythoscape/game/assets/characters/dungeon_interior_3d.py` - Interior props
3. `/workspace/Mythoscape/game/assets/mmorpg/client/client.py` - Rendering integration
4. `/workspace/Mythoscape/game/assets/mmorpg/tools/bake_building_sprite.py` - Asset generation

**Content/map files:**
1. `/workspace/Mythoscape/game/assets/mmorpg/client/content.py` - Building definitions
2. `/workspace/Mythoscape/game/assets/mmorpg/server/world_map.py` - Map data

---

## Contact & Questions

**Created by:** Cursor Cloud Agent (Sept 2026)
**Gold standards approved by:** David
**PR:** https://github.com/DavidRC-Projects/Mythoscape/pull/1
**Branch:** `cursor/fix-building-depth-rendering-694e`

**If uncertain:**
1. Reference gold standard PNGs visually
2. Read OSRS_DESIGN_REFERENCE.md for principles
3. Compare parameters to draw_house_shell() and draw_crypt_shell()
4. When in doubt: more depth, more prominence, deeper recess
5. Test in-game EARLY and OFTEN (restart client!)

**Visual bar:** If it doesn't look like OSRS-style extruded volume to you, it won't pass David's test.

---

**END OF PLAYBOOK**
