"""Screen-space attack facing for the HD player.

1 and -1 are the side views. "front" is toward the camera and "back" is away
from it. The 2D player keeps its own side-only facing.
"""
from __future__ import annotations


def target_point(client, target, glide=None):
    """Tile centre to face. A wyrm uses the body tile nearest the player."""
    if not target:
        return None
    if target.get("type") == "emberdeep_wyrm":
        import time

        import emberdeep_creatures

        if glide is not None:
            gx, gy, _sliding = glide(client, target, time.time())
            ax, ay = gx - 0.5, gy - 0.5
        else:
            ax, ay = float(target.get("x", 0)), float(target.get("y", 0))
        p = getattr(client, "player", None) or {}
        px = float(p.get("x", 0)) + 0.5
        py = float(p.get("y", 0)) + 0.5
        best = None
        best_d = None
        for x, y in emberdeep_creatures.footprint(round(ax), round(ay)):
            cx, cy = x + 0.5, y + 0.5
            dist = (cx - px) ** 2 + (cy - py) ** 2
            if best_d is None or dist < best_d:
                best_d = dist
                best = (cx, cy)
        if best is not None:
            return best
    return (float(target["x"]) + 0.5, float(target["y"]) + 0.5)


def sheet_tag(face):
    """HD strip letter for a game facing."""
    if face in ("back", "n"):
        return "n"
    if face in (-1, "-1", "w"):
        return "w"
    if face in (1, 1.0, "1", "e"):
        return "e"
    return "s"


def choose(client, feet, target, screen_of, tile_px, fallback=1, glide=None):
    """Dominant screen axis toward the target, with a little hysteresis.

    Returns 1, -1, "front", or "back". A gap under 0.12 of a tile keeps the
    previous facing. A new axis replaces it when it leads by more than 25%,
    or when the target point itself moved.
    """
    point = target_point(client, target, glide=glide)
    last = getattr(client, "_ember_fight_face", None)
    last_point = getattr(client, "_ember_fight_point", None)
    if point is None or screen_of is None:
        return last if last is not None else fallback
    hit = screen_of(point[0], point[1])
    feet_s = screen_of(feet[0], feet[1])
    if hit is None or feet_s is None:
        return last if last is not None else fallback
    dxs = hit[0] - feet_s[0]
    dys = hit[1] - feet_s[1]
    gap = 0.12 * float(tile_px or 0)
    if max(abs(dxs), abs(dys)) < gap:
        face = last if last is not None else fallback
        client._ember_fight_face = face
        client._ember_fight_point = point
        return face
    if abs(dxs) > abs(dys):
        fresh = 1 if dxs > 0 else -1
        major, minor = abs(dxs), abs(dys)
    else:
        fresh = "front" if dys > 0 else "back"
        major, minor = abs(dys), abs(dxs)
    moved = (
        last_point is None
        or abs(point[0] - last_point[0]) > 0.05
        or abs(point[1] - last_point[1]) > 0.05
    )
    if last is None or moved or major > 1.25 * minor:
        face = fresh
    else:
        face = last
    client._ember_fight_face = face
    client._ember_fight_point = point
    return face
