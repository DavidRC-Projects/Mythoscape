# Building Rendering Fix - Extruded Volumes with Recessed Entrances

## Problem
Buildings and dungeons were rendering as flat facades with separate 3D entrance objects "pasted" in front, rather than as unified extruded volumes with recessed entrances.

### Symptoms
- Visible gaps between front wall and side wall
- Door/entrance appeared as a separate object floating in front
- No depth read - looked like a facade with a box in front
- Void Sanctum had particularly visible issues

## Root Causes

### 1. Door Positioning Bug
**File:** `game/assets/characters/building_shell3d.py`
**Lines:** 526 (draw_house_shell), 681 (draw_crypt_shell)

Door X position was calculated using full footprint width (`fw`) instead of just the front wall width (`front_w`):
```python
# BEFORE (wrong):
ddx = int(fx + fw * frac - door_w * 0.5)

# AFTER (correct):
ddx = int(fx + front_w * frac - door_w * 0.5)
```

The side wall occupies `side_w = max(14, int(fw * 0.22))` of the footprint width, so the front wall is only `front_w = fw - side_w`. Using `fw` could position the door beyond the front wall edge.

### 2. Visible Gaps Between Walls
**File:** `game/assets/characters/building_shell3d.py`
**Function:** `_fill_poly`

Every polygon was drawn with a 1-pixel dark outline, including on shared edges between front and side walls. This created visible black seams that made walls appear disconnected.

**Fix:** Added `outline` parameter (default True) to skip outlines on internal edges:
```python
def _fill_poly(surf, pts, tex_name, shade=0, flat=None, alpha=255, uv=(0, 0), outline=True):
    # ... polygon fill ...
    if outline:
        pygame.draw.polygon(surf, (18, 12, 10), pts, 1)
```

### 3. Heavy Black Edge Lines
**File:** `game/assets/characters/building_shell3d.py`
**Function:** `_fill_side_wall`

Heavy black outlines were drawn on ALL edges, including the shared front/side edge:
```python
# BEFORE (wrong):
pygame.draw.polygon(surf, (14, 10, 8), pts, 1)  # All edges
pygame.draw.line(surf, (22, 14, 10), fr, br, 2)  # Thick black line

# AFTER (correct):
# External edges only
pygame.draw.line(surf, (14, 10, 8), sr_top, sr_bot, 1)
pygame.draw.line(surf, (14, 10, 8), sr_bot, br, 1)
pygame.draw.line(surf, (14, 10, 8), sr_top, fr, 1)
# Subtle crease on shared edge
pygame.draw.line(surf, (40, 32, 24) if wood else (36, 38, 44), fr, br, 1)
```

## Changes Made

### 1. building_shell3d.py
- Fixed door positioning to use `front_w` instead of `fw` in both `draw_house_shell` and `draw_crypt_shell`
- Added `outline` parameter to `_fill_poly` function
- Updated `_fill_side_wall` to skip outline on shared edge with front wall
- Replaced heavy black seams with subtle 1-pixel creases at wall joins
- Added external edge outlines only where needed
- Updated both `draw_house_shell` and `draw_crypt_shell` to use `outline=False` for internal faces

### 2. Regenerated Building Sprites
All PNG files in `game/assets/mmorpg/client/assets/buildings/` were regenerated with the fixed code:
- cottage_nw.png, cottage_ne.png, cottage_sw.png, cottage_se.png
- bank.png, smithy.png, pet_emporium.png
- harbour_tackle.png, harbour_fishmonger.png
- city_house_nw.png, city_house_sw.png, city_barracks.png
- stonehaven_castle.png
- **void_sanctum.png** (primary issue)
- emberdeep_volcano.png

## Verification Checklist

### Visual Requirements (All YES)
- [x] Visible building depth — side walls extend backward
- [x] Roof covers full depth of building
- [x] Foundation follows full footprint perimeter
- [x] Entrance recessed INTO main building (not separate box)
- [x] Door frame connects seamlessly to wall
- [x] Inside edges show entrance depth
- [x] Stone/wood texture continues around corners
- [x] Reads as ONE unified structure from gameplay camera
- [x] No pasted front object or floating door
- [x] No visible gaps between front and side walls

### Gameplay Preserved
- [ ] Dungeon/door interaction works
- [ ] Collision detection unchanged
- [ ] Movement and entry work
- [ ] NPC pathing unaffected
- [ ] Map placement correct
- [ ] Camera and scale match
- [ ] Pixel-art stone/wood aesthetic maintained

## Technical Details

### Rendering Architecture
Buildings are rendered in two modes:
1. **Pre-baked PNGs** (default, yaw=0): `building_sprites.draw_building_sprite()` → uses cached PNG
2. **Runtime procedural** (yaw≠0 or fallback): `building_shell3d.draw_building_shell()` → generates on-the-fly

The fix ensures both paths produce identical geometry:
- Front wall: vertical plane from `fx` to `fx + front_w`
- Side wall: parallelogram from `fx + front_w` to `fx + fw`, rising up by `dy`
- Roof: covers full extruded volume
- Foundation: wraps front + side base
- Entrance: carved into front wall using `_recessed_entrance()`

### Geometry Parameters
```python
fw = footprint.w                    # Full footprint width (11 tiles for void_sanctum)
fh = footprint.h                    # Full footprint height (7 tiles)
side_w = max(14, int(fw * 0.22))   # Side depth (~22% of width, INSIDE footprint)
front_w = fw - side_w               # Front wall width (~78% of footprint)
dy = max(12, int(fh * 0.22))       # Vertical rise for 3/4 view depth
```

### Entrance Rendering
`_recessed_entrance()` (line 119-315) creates depth through:
1. **Hole mask** - Defines opening shape (arch or rectangular)
2. **Throat** - Dark interior visible through hole
3. **Left/Right reveals** - Wall thickness surfaces (jambs) with lighting gradient
4. **Top soffit** - Ceiling inside the recess
5. **Door panel** - Actual door leaf INSIDE the recess, not at opening

## Files Changed
- `game/assets/characters/building_shell3d.py` - Core rendering logic
- `game/assets/mmorpg/client/assets/buildings/*.png` - All building sprites (15 files)
- `game/assets/mmorpg/client/assets/buildings/*.json` - Metadata (15 files)

## Testing Instructions
1. Pull this branch: `git checkout cursor/fix-building-depth-rendering-694e`
2. Start the game server and client
3. Navigate to Void Sanctum (SE of Stonehaven city, coords ~137,79)
4. Verify:
   - Building appears as ONE solid stone volume
   - Side walls extend backward (not flat)
   - Entrance is carved INTO the front wall
   - No separate entrance object visible
   - No gaps between walls
   - Door is centered properly in front wall
5. Test entering the dungeon still works (click door)
6. Rotate camera (if multi-yaw support exists) - geometry should stay consistent
7. Check other buildings (cottages, bank, smithy) also look correct

## Before/After Comparison
**BEFORE:**
- Void Sanctum: Flat stone wall + separate purple arch floating in front
- Cottages: Flat wooden facade + door as separate overlay
- Visible gap between front and side planes

**AFTER:**
- Void Sanctum: Unified stone structure with recessed arched entrance
- Cottages: Solid wooden building with door carved into front
- Seamless connection between all surfaces
- Clear depth from side walls, roof overhang, foundation wrap

## Known Limitations
- Camera yaw support: Pre-baked PNGs only exist for yaw=0 (south-facing camera). Runtime procedural shells handle other yaws but aren't cached.
- Texture alignment: UV mapping at wall corners may show minor misalignment under close inspection (acceptable for gameplay camera distance).
- Door alignment: Door position is calculated from footprint fraction, which works for most layouts but may need manual tweaking for asymmetric buildings.
