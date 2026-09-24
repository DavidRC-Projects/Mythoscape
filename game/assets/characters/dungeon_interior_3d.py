"""
3D dungeon interior props for Void Sanctum and similar dungeons.

RuneScape-style extruded volumes: stone pillars, walls with depth, 
braziers, furniture. Pixel-art aesthetic with procedural geometry.
"""
import pygame


def _shade(rgb, delta):
    """Adjust RGB by delta."""
    return tuple(max(0, min(255, c + delta)) for c in rgb[:3])


def draw_stone_pillar_3d(surf, cx, cy, tile, yaw=0):
    """
    Extruded stone pillar with depth - 3/4 view matching building style.
    
    cx, cy: center screen position
    tile: tile size in pixels
    yaw: camera rotation (0-3)
    """
    s = tile * 0.9  # Pillar size relative to tile
    
    # Pillar dimensions for 3/4 view
    base_w = int(s * 0.4)  # Front face width
    base_h = int(s * 0.3)  # Base height
    pillar_h = int(s * 1.2)  # Total pillar height
    depth = int(base_w * 0.35)  # Side depth
    dy = int(base_h * 0.30)  # Vertical rise for 3/4 view
    
    # Colors - dark stone with lighting
    base_stone = (45, 42, 58)
    lit_stone = (75, 70, 92)
    dark_stone = (28, 26, 36)
    edge_light = (110, 105, 135)
    
    # Base coordinates
    bottom = int(cy + pillar_h * 0.4)
    top = int(bottom - pillar_h)
    
    # Front face
    fl = (cx - base_w // 2, top)
    fr = (cx + base_w // 2, top)
    br = (cx + base_w // 2, bottom)
    bl = (cx - base_w // 2, bottom)
    
    # Side face (right side, 3/4 view)
    sr_top = (fr[0] + depth, fr[1] - dy)
    sr_bot = (br[0] + depth, br[1] - dy)
    
    # Top cap (visible from 3/4 view)
    tl = fl
    tr = fr
    tr_back = sr_top
    tl_back = (tl[0] + depth // 2, tl[1] - dy // 2)
    
    # Draw bottom shadow
    shadow_pts = [
        (bl[0] - 3, bottom + 2),
        (sr_bot[0] + 3, bottom + 2),
        (sr_bot[0] + 2, bottom + 5),
        (bl[0] - 2, bottom + 5),
    ]
    pygame.draw.polygon(surf, (10, 8, 14, 80), shadow_pts)
    
    # Draw side wall first (behind front)
    side_pts = [fr, sr_top, sr_bot, br]
    pygame.draw.polygon(surf, dark_stone, side_pts)
    # Side detail lines (mortar/stone blocks)
    for i in range(3):
        y_offset = top + (bottom - top) * (i + 1) // 4
        pygame.draw.line(surf, _shade(dark_stone, -8), 
                        (fr[0], y_offset), (sr_top[0], y_offset - dy), 1)
    pygame.draw.line(surf, _shade(dark_stone, 15), fr, sr_top, 1)
    
    # Draw front face
    pygame.draw.polygon(surf, base_stone, [fl, fr, br, bl])
    # Front vertical mortar lines
    for i in range(1, 3):
        x_offset = fl[0] + (fr[0] - fl[0]) * i // 3
        pygame.draw.line(surf, dark_stone, (x_offset, top), (x_offset, bottom), 1)
    # Horizontal mortar lines
    for i in range(1, 4):
        y_offset = top + (bottom - top) * i // 4
        pygame.draw.line(surf, dark_stone, (fl[0], y_offset), (fr[0], y_offset), 1)
    # Lighting - left edge lit, right edge dark
    pygame.draw.line(surf, edge_light, fl, bl, 2)
    pygame.draw.line(surf, _shade(base_stone, -15), (fr[0] - 1, top), (br[0] - 1, bottom), 1)
    
    # Draw top cap
    top_pts = [tl, tr, tr_back, tl_back]
    pygame.draw.polygon(surf, lit_stone, top_pts)
    pygame.draw.line(surf, edge_light, tl, tr, 1)
    pygame.draw.line(surf, _shade(lit_stone, -10), tr, tr_back, 1)


def draw_wall_segment_3d(surf, x, y, tile, horizontal=True, yaw=0):
    """
    Stone wall segment with depth - 3/4 view.
    
    x, y: top-left tile position on screen
    tile: tile size
    horizontal: True for horizontal wall, False for vertical
    """
    s = tile
    
    # Wall dimensions
    wall_thickness = int(s * 0.3)
    wall_height = int(s * 0.5)
    depth = int(s * 0.25)  # Depth for 3/4 view
    dy = int(s * 0.20)  # Vertical rise
    
    # Colors
    wall_stone = (52, 48, 64)
    dark_stone = (32, 30, 42)
    lit_edge = (90, 85, 110)
    
    if horizontal:
        # Horizontal wall going right
        length = int(s * 1.0)
        
        # Wall base
        bottom = y + s
        top = bottom - wall_height
        
        # Front face
        fl = (x, top)
        fr = (x + length, top)
        br = (x + length, bottom)
        bl = (x, bottom)
        
        # Top surface (3/4 view)
        tl = fl
        tr = fr
        tr_back = (tr[0] + depth, tr[1] - dy)
        tl_back = (tl[0] + depth, tl[1] - dy)
        
        # Draw shadow
        pygame.draw.rect(surf, (8, 6, 12, 60), (x - 1, bottom, length + depth + 2, 3))
        
        # Draw top surface
        pygame.draw.polygon(surf, _shade(wall_stone, 15), [tl, tr, tr_back, tl_back])
        pygame.draw.line(surf, lit_edge, tl, tr, 1)
        
        # Draw front face
        pygame.draw.polygon(surf, wall_stone, [fl, fr, br, bl])
        # Mortar lines
        for i in range(1, length // 20 + 1):
            x_line = x + i * 20
            pygame.draw.line(surf, dark_stone, (x_line, top), (x_line, bottom), 1)
        # Lighting
        pygame.draw.line(surf, lit_edge, fl, bl, 1)
    
    else:
        # Vertical wall going down (depth extends right)
        length = int(s * 1.0)
        
        # Wall positioned
        left = x
        right = x + wall_thickness
        top = y
        bottom = y + length
        
        # Front face
        fl = (left, top)
        fr = (right, top)
        br = (right, bottom)
        bl = (left, bottom)
        
        # Side depth
        sr_top = (fr[0] + depth, fr[1] - dy)
        sr_bot = (br[0] + depth, br[1] - dy)
        
        # Draw shadow
        pygame.draw.ellipse(surf, (8, 6, 12, 60), (left - 2, bottom - 2, wall_thickness + depth + 4, 8))
        
        # Draw side surface
        pygame.draw.polygon(surf, dark_stone, [fr, sr_top, sr_bot, br])
        
        # Draw front face
        pygame.draw.polygon(surf, wall_stone, [fl, fr, br, bl])
        # Horizontal mortar lines
        for i in range(1, length // 15 + 1):
            y_line = top + i * 15
            pygame.draw.line(surf, dark_stone, (left, y_line), (right, y_line), 1)
        # Lighting
        pygame.draw.line(surf, lit_edge, fl, fr, 1)
        pygame.draw.line(surf, _shade(wall_stone, -12), fr, br, 1)


def draw_brazier_3d(surf, cx, cy, tile, lit=True, t=0.0):
    """
    Stone brazier with fire - 3/4 view with depth.
    
    cx, cy: center position
    tile: tile size
    lit: whether fire is burning
    t: time for animation
    """
    import math
    
    s = tile * 0.7
    
    # Bowl dimensions
    bowl_w = int(s * 0.45)
    bowl_h = int(s * 0.25)
    depth = int(bowl_w * 0.3)
    dy = int(bowl_h * 0.25)
    
    # Pedestal
    ped_w = int(bowl_w * 0.5)
    ped_h = int(s * 0.4)
    
    # Colors
    stone = (45, 42, 58)
    dark = (28, 26, 36)
    lit_edge = (85, 80, 105)
    
    # Pedestal bottom
    ped_bottom = int(cy + s * 0.3)
    ped_top = ped_bottom - ped_h
    
    # Pedestal front face
    p_fl = (cx - ped_w // 2, ped_top)
    p_fr = (cx + ped_w // 2, ped_top)
    p_br = (cx + ped_w // 2, ped_bottom)
    p_bl = (cx - ped_w // 2, ped_bottom)
    
    # Pedestal side
    p_sr_top = (p_fr[0] + depth // 2, p_fr[1] - dy // 2)
    p_sr_bot = (p_br[0] + depth // 2, p_br[1] - dy // 2)
    
    # Draw shadow
    pygame.draw.ellipse(surf, (8, 6, 12, 90), (cx - ped_w, ped_bottom - 2, ped_w * 2 + depth, 8))
    
    # Draw pedestal side
    pygame.draw.polygon(surf, dark, [p_fr, p_sr_top, p_sr_bot, p_br])
    
    # Draw pedestal front
    pygame.draw.polygon(surf, stone, [p_fl, p_fr, p_br, p_bl])
    pygame.draw.line(surf, lit_edge, p_fl, p_bl, 1)
    pygame.draw.line(surf, _shade(stone, -10), p_fr, p_br, 1)
    
    # Bowl
    bowl_bottom = ped_top
    bowl_top = bowl_bottom - bowl_h
    
    # Bowl front
    b_fl = (cx - bowl_w // 2, bowl_top)
    b_fr = (cx + bowl_w // 2, bowl_top)
    b_br = (cx + bowl_w // 2, bowl_bottom)
    b_bl = (cx - bowl_w // 2, bowl_bottom)
    
    # Bowl side
    b_sr_top = (b_fr[0] + depth, b_fr[1] - dy)
    b_sr_bot = (b_br[0] + depth, b_br[1] - dy)
    
    # Draw bowl side
    pygame.draw.polygon(surf, dark, [b_fr, b_sr_top, b_sr_bot, b_br])
    
    # Draw bowl front
    pygame.draw.polygon(surf, stone, [b_fl, b_fr, b_br, b_bl])
    pygame.draw.line(surf, lit_edge, b_fl, b_fr, 1)
    
    # Bowl interior rim
    rim_d = 3
    pygame.draw.polygon(surf, _shade(stone, -18), [
        (b_fl[0] + rim_d, b_fl[1] + rim_d),
        (b_fr[0] - rim_d, b_fr[1] + rim_d),
        (b_br[0] - rim_d, b_br[1] - rim_d),
        (b_bl[0] + rim_d, b_bl[1] - rim_d),
    ])
    
    # Fire (if lit)
    if lit:
        fire_h = int(bowl_h * 1.5)
        fire_w = int(bowl_w * 0.7)
        fire_cy = bowl_top - fire_h // 2
        
        # Animated flicker
        pulse = abs(math.sin(t * 3.5)) * 0.3
        glow = int(30 + pulse * 40)
        
        # Fire glow base
        glow_surf = pygame.Surface((fire_w + 20, fire_h + 20), pygame.SRCALPHA)
        pygame.draw.ellipse(glow_surf, (255, 140, 30, 60), glow_surf.get_rect())
        surf.blit(glow_surf, (cx - fire_w // 2 - 10, fire_cy - fire_h // 2 - 10))
        
        # Fire shapes (3 overlapping ellipses)
        for i, (h_offset, color, size_mult) in enumerate([
            (0, (255, 180 + glow, 60), 1.0),
            (-fire_h * 0.2, (255, 140 + glow, 40), 0.7),
            (-fire_h * 0.4, (255, 100, 30), 0.4),
        ]):
            fw = int(fire_w * size_mult)
            fh = int(fire_h * size_mult)
            fy = fire_cy + h_offset + int(math.sin(t * 4 + i) * 3)
            pygame.draw.ellipse(surf, color, (cx - fw // 2, int(fy - fh // 2), fw, fh))


def draw_dungeon_props(surf, room_rect, tile, zone="shadow_crypt", t=0.0):
    """
    Draw 3D dungeon interior props for a room.
    
    room_rect: pygame.Rect of the room in screen space
    tile: tile size
    zone: dungeon type (shadow_crypt, volcano, etc.)
    t: animation time
    """
    x, y, w, h = room_rect.x, room_rect.y, room_rect.w, room_rect.h
    
    # Void Sanctum / shadow crypt props
    if zone == "shadow_crypt":
        # Corner pillars (4 corners inset from edges)
        inset = tile * 0.8
        corners = [
            (x + inset, y + inset),  # Top-left
            (x + w - inset, y + inset),  # Top-right
            (x + inset, y + h - inset),  # Bottom-left
            (x + w - inset, y + h - inset),  # Bottom-right
        ]
        for cx, cy in corners:
            draw_stone_pillar_3d(surf, int(cx), int(cy), tile)
        
        # Central braziers (if room is large enough)
        if w > tile * 5 and h > tile * 4:
            # Two braziers flanking center
            center_y = y + h // 2
            for offset in [-tile * 1.5, tile * 1.5]:
                draw_brazier_3d(surf, int(x + w // 2 + offset), int(center_y), tile, lit=True, t=t)
