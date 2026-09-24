# Farmhouse Deep 3D Geometry Rebuild

## Target Building
**Farmhouse** in starting village = `cottage_se.png` (house style 1)

## Problem Identified
David's screenshot showed the Farmhouse still looked like **flat cardboard planes**:
- Flat front facade
- Flat side plane joined at hard line
- Door/windows flush-pasted on front
- No real recessed entrance depth
- No visible 3D volume

The first pass (outline tweaks + door positioning) was **NOT enough**.

## Root Cause
The geometry parameters were too shallow to read as 3D from gameplay camera:
- Side depth: only 22% of footprint width → too thin
- Vertical rise: only 22% of height → too flat
- Entrance recess: 8-18 pixels → barely visible
- Roof peak: modest → didn't emphasize depth

## Solution: Rebuild Geometry Model

### Changed Parameters (building_shell3d.py)

#### 1. Side Wall Depth
```python
# BEFORE:
side_w = max(14, int(fw * 0.22))  # 22% of width

# AFTER:
side_w = max(18, int(fw * 0.35))  # 35% of width - MUCH DEEPER
```
**Impact:** Side walls now extend **60% further** backward, creating visible extruded volume.

#### 2. Vertical Rise (3/4 View)
```python
# BEFORE:
dy = max(12, int(fh * 0.22))  # 22% of height

# AFTER:
dy = max(16, int(fh * 0.32))  # 32% of height - TALLER
```
**Impact:** Side walls rise **45% higher**, making depth dramatically visible from camera angle.

#### 3. Entrance Recess Depth
```python
# BEFORE:
depth = max(8, min(18, dw // 4))   # 8-18px shallow
jamb = max(6, depth - 1)           # 6px jamb

# AFTER:
depth = max(20, min(35, dw // 3))  # 20-35px DEEP recess
jamb = max(12, depth - 2)          # 12px+ wide jamb surfaces
```
**Impact:** Entrance now **2x-3x deeper**, clearly carved INTO wall with visible interior surfaces.

#### 4. Roof Geometry
```python
# BEFORE:
overhang = max(6, fw // 16)         # Small eaves
peak_h = max(22, int(fh * 0.42))    # Modest peak
pb = (... pf[0] + side_w ...)       # Back ridge didn't reach edge

# AFTER:
overhang = max(10, fw // 12)        # Larger eaves
peak_h = max(28, int(fh * 0.48))    # Taller peak (48% vs 42%)
pb = (fx + fw - 2, ...)             # Back ridge EXTENDS TO RIGHT EDGE
```
**Impact:** Roof now **clearly covers the full extruded depth**, not just front face.

## File Changes

### Code
- `game/assets/characters/building_shell3d.py`
  - Lines 377-392: Increased side_w and dy parameters
  - Lines 120-132: Deeper entrance recess (depth and jamb)
  - Lines 137-148: Stone entrance depth increase
  - Lines 247-250: Wood entrance depth increase  
  - Lines 460-469: Roof geometry (peak, ridge, overhang)

### Asset
- `game/assets/mmorpg/client/assets/buildings/cottage_se.png`
  - **Before:** 306 KB (312,711 bytes)
  - **After:** 342 KB (349,270 bytes)
  - **Growth:** +36 KB (~11% increase) = more geometry

## Visual Verification

### Expected Results (from gameplay camera)
✅ **ONE CONTINUOUS VOLUME**
- Front wall and side wall read as single extruded structure
- NO flat planes with hard edge join
- Side wall clearly extends backward (not just a flat side flap)

✅ **VISIBLE DEPTH**
- Side walls extend ~35% of building width (very visible)
- Roof clearly covers front + side depth
- Foundation wraps around both front and side base

✅ **RECESSED ENTRANCE**
- Doorway carved INTO front wall (not pasted object)
- Visible dark interior through opening
- 12px+ wide jamb surfaces show wall thickness
- Door panel sits 20-35px INSIDE opening
- Wooden frame surrounds recess, not flat on surface

✅ **NO PASTED OBJECTS**
- Door is part of the wall opening, not a separate sprite
- Windows integrated into wall, not overlays
- Entrance depth visible from front AND side angles

### In-Game Testing
1. **Location:** Starting village, building labeled **"Farmhouse"**
2. **Coordinates:** Floor tiles 16-22, 21-27 (per content.py line 2149)
3. **What to check:**
   - Stand south of building, look at front face
   - Side wall should extend visibly backward to the right
   - Roof should cover both front and side depth
   - Entrance should look carved IN, not pasted ON
   - Walk around building - depth should be consistent

### Quick Visual Check
```bash
# Display the regenerated sprite
python3 verify_building_fix.py

# Or view directly
open game/assets/mmorpg/client/assets/buildings/cottage_se.png
```

Look for:
- **Thick side wall** extending right from front edge
- **Deep entrance recess** with visible interior edges
- **Roof ridge** extending to cover side depth
- **Foundation** wrapping around both front and side

## Commits
1. `36e1728` - Dramatically increase 3D depth for house shells
2. `3925cdd` - Regenerate cottage_se.png (Farmhouse) with deep 3D geometry

## Before/After Comparison

### Geometry Numbers
| Parameter | Before (Flat) | After (Deep 3D) | Change |
|-----------|---------------|-----------------|--------|
| Side depth % | 22% | 35% | **+59%** |
| Vertical rise % | 22% | 32% | **+45%** |
| Entrance depth (px) | 8-18 | 20-35 | **+122%** |
| Jamb width (px) | 6 | 12+ | **+100%** |
| Roof peak % | 42% | 48% | **+14%** |
| Overhang ratio | fw/16 | fw/12 | **+33%** |

### Visual Impact
**Before:**
- Flat front wall with thin side strip
- Door appeared pasted on surface
- Roof barely extended past front
- Looked like 2D cutout with side flap

**After:**
- Front + side + roof read as ONE volume
- Door carved into wall with visible depth
- Roof clearly covers full extrusion
- Reads as 3D structure from gameplay angle

## Next Steps
1. **David tests** this Farmhouse in-game
2. If this passes: apply same parameters to ALL cottages/houses
3. If still needs adjustment: tweak depth % for this building only
4. Stone buildings (void_sanctum) need same depth treatment

## Critical Success Criteria
From David's screenshot, the Farmhouse must:
- ❌ NOT look like flat planes at hard angle
- ❌ NOT have door pasted flat on wall
- ✅ MUST show visible side wall depth
- ✅ MUST have entrance carved INTO wall
- ✅ MUST read as ONE extruded volume
