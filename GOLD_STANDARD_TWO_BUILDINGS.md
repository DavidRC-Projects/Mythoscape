# TWO GOLD STANDARD BUILDINGS - Final Geometry

## David's Bar: TWO Buildings That Read as 3D Volumes

### 1. Farmhouse (Village Home)
**Asset:** `cottage_se.png` (house style 1)
**Location:** Starting village, floor tiles 16-22, 21-27
**Label:** "Farmhouse"

### 2. Void Sanctum (Dungeon)
**Asset:** `void_sanctum.png` (crypt)
**Location:** SE of Stonehaven city, coords ~137,79
**Label:** "Void Sanctum"

---

## Final Geometry Parameters

### Target Reference Analysis
Looking at the **Fishing Shop** target image:
- Side wall appears to occupy **~45-50%** of total building width
- Very prominent backward extrusion
- Deep recessed entrance with visible interior walls
- Roof clearly covers full depth

### Applied Parameters (BOTH Buildings)

| Parameter | Was (Failed) | Now (Gold) | Visual Impact |
|-----------|--------------|------------|---------------|
| **Side depth %** | 22% → 35% | **45%** | Side wall nearly HALF the width |
| **Vertical rise %** | 22% → 32% | **38%** | Very tall 3/4 view projection |
| **Entrance recess** | 8-18px → 20-35px | **28-45px** | Deep carved opening (40% of door width) |
| **Jamb width** | 6px → 12px | **16-28px** | Wide visible interior walls |
| **Wall start** | 16% → 16% | **14%** | Lower walls for more visible height |
| **Roof peak %** | 42% → 48% | **48%** | Tall peak maintained |

---

## Code Changes (building_shell3d.py)

### Houses (draw_house_shell - Line 377)
```python
# BEFORE (failed review):
side_w = max(18, int(fw * 0.35))  # 35% depth
dy = max(16, int(fh * 0.32))      # 32% rise

# AFTER (gold standard):
side_w = max(22, int(fw * 0.45))  # 45% depth - NEARLY HALF WIDTH
dy = max(20, int(fh * 0.38))      # 38% rise - VERY TALL
wall_top = fy + int(fh * 0.14)    # Start walls lower
```

### Dungeons (draw_crypt_shell - Line 560)
```python
# BEFORE (old shallow):
side_w = max(14, int(fw * 0.22))  # Only 22%
dy = max(12, int(fh * 0.22))      # Only 22%

# AFTER (gold standard - matches house):
side_w = max(22, int(fw * 0.45))  # 45% depth
dy = max(20, int(fh * 0.38))      # 38% rise
wall_top = fy + int(fh * 0.14)    # Lower wall start
```

### Entrance Recess (_recessed_entrance - Line 120)
```python
# BEFORE (shallow):
depth = max(20, min(35, dw // 3))  # 20-35px
jamb = max(12, depth - 2)          # 12px jamb

# AFTER (very deep):
depth = max(28, min(45, int(dw * 0.4)))  # 28-45px (40% of door width)
jamb = max(16, min(28, depth - 4))       # 16-28px WIDE interior surfaces
```

### Stone Entrance (Line 137)
```python
# BEFORE:
depth = max(18, min(28, dw // 4))
jamb = max(12, min(20, depth))

# AFTER:
depth = max(24, min(40, int(dw * 0.35)))  # Very deep
jamb = max(18, min(32, depth - 2))        # Very wide
```

### Wood Entrance (Line 247)
```python
# BEFORE:
depth = max(20, min(35, dw // 3))
jamb = max(12, depth - 2)
frame = max(6, dw // 9)

# AFTER:
depth = max(28, min(45, int(dw * 0.4)))  # Match stone depth
jamb = max(16, min(28, depth - 4))       # Wide interior
frame = max(7, int(dw * 0.12))           # Prominent frame (12%)
```

---

## Asset Changes

### Farmhouse (cottage_se.png)
**Evolution:**
1. Original: 306 KB (312,711 bytes) - flat facade
2. Second pass (35% depth): 342 KB (349,270 bytes) - still rejected
3. **Gold standard (45% depth): 352 KB (359,692 bytes)** ✅

**Growth:** +46 KB from original (+15%)

### Void Sanctum (void_sanctum.png)
**Evolution:**
1. Original: 441 KB (441,242 bytes) - flat + gap
2. Second pass (35% depth): 441 KB (441,489 bytes) - minimal change
3. **Gold standard (45% depth): 531 KB (530,891 bytes)** ✅

**Growth:** +90 KB from original (+20%!) - MASSIVE geometry increase

---

## Visual Verification

### Expected Results (Both Buildings)

✅ **SIDE WALL PROMINENCE**
- Side wall occupies nearly **HALF** the building width (45%)
- Very visible from front angle - not a thin strip
- Extends far backward with clear perspective

✅ **STRONG VERTICAL RISE**
- Side walls rise 38% of height upward
- Creates dramatic 3/4 view depth
- Much more than subtle tilt

✅ **DEEP CARVED ENTRANCE**
- Opening goes 28-45px INTO the wall
- 16-28px wide interior jamb surfaces clearly visible
- Dark throat/interior visible through opening
- Door panel sits WAY inside, not at surface

✅ **SEAMLESS VOLUME**
- Front, side, roof, foundation all share same footprint
- No gaps, no separate planes at hard angles
- Reads as ONE extruded stone/wood block

✅ **NO PASTED OBJECTS**
- Door is carved opening in wall geometry
- Windows integrated into walls
- Entrance depth visible from any angle
- If you hide door, building volume remains prominent

### In-Game Testing

#### 1. Farmhouse (Village Home)
**Location:** Starting village
**Finding:** Building labeled "Farmhouse" when moused over
**Coordinates:** Floor tiles 16-22, 21-27

**Check from south:**
- Side wall (right side) extends nearly half the visible width
- Wooden door deeply recessed with visible interior frame
- Roof clearly covers both front and side depth
- Foundation wraps around front + side base
- NO flat cardboard appearance

#### 2. Void Sanctum (Dungeon)
**Location:** SE of Stonehaven city
**Finding:** Portal at coords ~137,79, building labeled "Void Sanctum"
**Coordinates:** Building footprint 132-142, 74-80

**Check from south:**
- Stone side wall extends nearly half the visible width
- Arched entrance deeply carved with visible stone thickness
- Purple glow comes from deep interior, not pasted sprite
- Flat stone parapet roof covers full depth
- Foundation wraps around entire perimeter

---

## Commits

### 1. Geometry Code
**e88f783** - `building_shell3d.py`
- Side depth: 35% → **45%**
- Vertical rise: 32% → **38%**
- Entrance: 20-35px → **28-45px**
- Applied to both draw_house_shell AND draw_crypt_shell

### 2. Asset Regeneration
**5a084b8** - Both PNGs
- cottage_se.png: 342KB → 352KB (+10KB)
- void_sanctum.png: 441KB → 531KB (+90KB, +20%!)

---

## Why 45% Depth Works

### Geometry Math
For an 11-tile wide building (like Farmhouse):
- Total footprint: 11 tiles × 64 PPT = 704 pixels
- **Side depth (45%):** 317 pixels - VERY visible from front
- **Front wall (55%):** 387 pixels - still dominant

For comparison:
- 22% (old): 155px side - barely visible thin strip
- 35% (rejected): 246px side - better but still flat
- **45% (gold): 317px side - NEARLY HALF, clearly prominent**

### Why Previous Attempts Failed
- **22% depth:** Too thin, read as "side flap" not extruded volume
- **35% depth:** Better but still not enough to overcome flat appearance
- **45% depth:** Matches target reference - side wall is VERY visible

### Target Reference Match
Looking at Fishing Shop target:
- Measuring pixels: side wall ≈ 45-50% of total width
- Our 45% matches this proportion
- Creates same visual impression: ONE solid extruded volume

---

## Critical Success Criteria

From David's screenshot and target reference, these TWO buildings MUST:

❌ **NOT look like:**
- Flat front facade with thin side strip
- Flat planes joined at hard angle
- Door/entrance pasted flush on wall
- Separate 3D box floating in front
- Cardboard cutout with side flap

✅ **MUST look like:**
- ONE continuous extruded volume
- Side wall nearly HALF the visible width
- Deep entrance carved INTO wall (not on it)
- Interior surfaces visible through opening
- Roof covering full front + side depth
- Foundation wrapping entire perimeter
- Solid 3D structure from gameplay camera

---

## Copy/Paste for Rest of Game

Once David confirms these TWO buildings pass:

### Copy Farmhouse parameters to:
- cottage_nw, cottage_ne, cottage_sw (other village homes)
- city_house_nw, city_house_sw (city residences)
- All wooden buildings with peaked roofs

### Copy Void Sanctum parameters to:
- Other dungeon entrances (if any)
- Stone buildings with flat parapets
- Castle/fortress structures

### Parameters to Copy:
```python
side_w = max(22, int(fw * 0.45))  # 45% side depth
dy = max(20, int(fh * 0.38))      # 38% vertical rise
wall_top = fy + int(fh * 0.14)    # Lower wall start

# Entrance:
depth = max(28, min(45, int(dw * 0.4)))  # 40% of door width
jamb = max(16, min(28, depth - 4))       # Wide interior
```

---

## Failure Modes Eliminated

### First Pass Issues (FIXED)
- ❌ Only tweaked outlines (1px seams) → ✅ Rebuilt full geometry
- ❌ Only fixed door X position → ✅ Deepened entire entrance
- ❌ Kept shallow 22% depth → ✅ Increased to 45% depth

### Second Pass Issues (FIXED)
- ❌ 35% depth still looked flat → ✅ Increased to 45% (target match)
- ❌ Side wall still thin strip → ✅ Now nearly half the width
- ❌ Entrance only 20-35px → ✅ Now 28-45px (much deeper)

### Current Gold Standard
- ✅ 45% side depth - matches target reference proportion
- ✅ 38% vertical rise - dramatic 3/4 view projection
- ✅ 28-45px recess - entrance clearly carved in
- ✅ 16-28px jambs - wide visible interior surfaces
- ✅ Applied to BOTH house and dungeon shells

---

## File Summary

### Changed Code
- `game/assets/characters/building_shell3d.py`
  - draw_house_shell: 45% depth + 38% rise
  - draw_crypt_shell: 45% depth + 38% rise
  - _recessed_entrance: 28-45px depth + 16-28px jambs
  - All entrance paths: wood + stone

### Changed Assets
- `game/assets/mmorpg/client/assets/buildings/cottage_se.png`
  - Farmhouse: +46KB from original (+15%)
- `game/assets/mmorpg/client/assets/buildings/void_sanctum.png`
  - Void Sanctum: +90KB from original (+20%!)

### Client Usage
- Client already loads these PNGs via building_sprites.py
- No client code changes needed
- Buildings automatically use new geometry

---

## Next Steps

1. **David tests** these TWO buildings in-game
2. **Farmhouse:** Navigate to starting village, check labeled "Farmhouse"
3. **Void Sanctum:** Navigate to SE of Stonehaven (~137,79)
4. **Verify:** Both read as ONE extruded 3D volume, not flat cardboard
5. **If pass:** Copy parameters to all other buildings
6. **If fail:** Further adjustments to these TWO only

**Do NOT merge to main until David confirms both pass visual test.**
