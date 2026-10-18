"""Fishing spots deplete and move (COMBAT_SKILLING_SPEC part 3, with David's 10-20 catches).

Every spot has a shared stock of catches and a lifetime that starts on the first catch. When either runs out,
everyone fishing it is stopped, the spot disappears, and after a short wait it comes back on another shoreline
water tile 3-6 tiles from its home. All of this lives on the server; the client only sees the spot vanish and
reappear in the world state. A moved spot sits on a new tile, so the tile is its key: requests aimed at the old
tile find nothing.
"""
import random

STOCK = (10, 20)            # shared catches per spot, random per spawn (David: 10-20, not 3-6)
LIFE_TICKS = (34, 67)       # ~20-40 s from the first catch (0.6 s ticks)
MOVE_RADIUS = (3, 6)        # tiles from home (Chebyshev)
MOVE_TICKS = (15, 25)       # ~9-15 s hidden before it reappears
MIN_GAP = 2                 # same spacing as the world generator uses between spots
MOVED_MSG = "The fishing spot moves away."


def _cfg(ydef, key, default):
    val = (ydef or {}).get(key)
    return tuple(val) if isinstance(val, (list, tuple)) and len(val) == 2 else default


def is_spot(node, ydef=None):
    if (ydef or {}).get("skill") == "fishing":
        return True
    return bool(node.get("is_fish_spot")) or str(node.get("type", "")).startswith("fishing_spot")


def restock(node, ydef=None, rng=None):
    rng = rng or random
    lo, hi = _cfg(ydef, "stock", STOCK)
    node["stock_left"] = rng.randint(lo, hi)
    node["expires_at"] = None


def init_spot(node, pos, ydef=None, rng=None):
    node.setdefault("home", tuple(pos))
    node["is_fish_spot"] = True
    restock(node, ydef, rng)


def take_catch(node, tick, ydef=None, rng=None):
    """One catch from the shared stock. True when the spot is used up."""
    rng = rng or random
    if node.get("stock_left") is None:
        restock(node, ydef, rng)
    if node.get("expires_at") is None:
        lo, hi = _cfg(ydef, "life_ticks", LIFE_TICKS)
        node["expires_at"] = int(tick) + rng.randint(lo, hi)
    node["stock_left"] = int(node["stock_left"]) - 1
    return node["stock_left"] <= 0


def expired(node, tick):
    return node.get("expires_at") is not None and int(tick) >= int(node["expires_at"])


def depart(nodes, pos, tick, ydef=None, rng=None):
    """Take the spot off the map. Returns the node for the moving list."""
    rng = rng or random
    node = nodes.pop(tuple(pos))
    node.setdefault("home", tuple(pos))
    lo, hi = _cfg(ydef, "move_ticks", MOVE_TICKS)
    node["depleted"] = True
    node["left_from"] = tuple(pos)
    node["respawn_at"] = int(tick) + rng.randint(lo, hi)
    return node


def shoreline(grid, x, y, water, walkable):
    """A water tile with walkable ground beside it (8-neighbours), like the world generator places spots."""
    h, w = len(grid), len(grid[0]) if grid else 0
    if not (0 <= x < w and 0 <= y < h) or grid[y][x] != water:
        return None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] in walkable:
                return (nx, ny)
    return None


def _reachable(grid, start, goal, walkable, limit):
    """BFS over walkable tiles from start to goal, within a box around both."""
    if start == goal:
        return True
    x0 = min(start[0], goal[0]) - limit
    x1 = max(start[0], goal[0]) + limit
    y0 = min(start[1], goal[1]) - limit
    y1 = max(start[1], goal[1]) + limit
    seen = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for x, y in frontier:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (x + dx, y + dy)
                if p in seen or not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
                    continue
                if not (0 <= p[1] < len(grid) and 0 <= p[0] < len(grid[0])) or grid[p[1]][p[0]] not in walkable:
                    continue
                if p == goal:
                    return True
                seen.add(p)
                nxt.append(p)
        frontier = nxt
    return False


def pick_tile(grid, nodes, home, avoid, water, walkable, ydef=None, rng=None):
    """A shoreline tile 3-6 tiles from home, not `avoid`, clear of other spots, reachable from home's shore."""
    rng = rng or random
    lo, hi = _cfg(ydef, "move_radius", MOVE_RADIUS)
    hx, hy = home
    home_shore = shoreline(grid, hx, hy, water, walkable)
    spots = [p for p, n in nodes.items() if is_spot(n)]
    cands = []
    for y in range(hy - hi, hy + hi + 1):
        for x in range(hx - hi, hx + hi + 1):
            if not lo <= max(abs(x - hx), abs(y - hy)) <= hi or (x, y) == tuple(avoid):
                continue
            if (x, y) in nodes or any(max(abs(x - px), abs(y - py)) < MIN_GAP for px, py in spots):
                continue
            shore = shoreline(grid, x, y, water, walkable)
            if shore:
                cands.append(((x, y), shore))
    rng.shuffle(cands)
    for pos, shore in cands:
        if home_shore is None or _reachable(grid, home_shore, shore, walkable, hi + 4):
            return pos
    return None


def return_due(moving, nodes, grid, tick, water, walkable, ydefs, rng=None):
    """Bring back every spot whose wait is over. Returns [(old_pos, new_pos)]; keeps the rest waiting."""
    rng = rng or random
    moved = []
    for node in list(moving):
        if int(tick) < int(node["respawn_at"]):
            continue
        ydef = ydefs.get(node.get("type")) or {}
        pos = pick_tile(grid, nodes, node["home"], node.get("left_from") or node["home"], water, walkable, ydef, rng)
        if pos is None:
            node["respawn_at"] = int(tick) + 5          # nothing free right now: try again shortly
            continue
        moving.remove(node)
        node["depleted"] = False
        node["respawn_at"] = 0
        restock(node, ydef, rng)
        moved.append((node.pop("left_from", None), pos))
        nodes[pos] = node
    return moved
