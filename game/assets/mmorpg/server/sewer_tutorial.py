"""Below the Village: the optional sewer tutorial (GUIDE_AND_SEWER_PROPOSAL.md v2, section 5).

A private instance under the village. Seraphine teaches a first fight, eating mid-fight,
loot, priority targets and leaving a dungeon. Nothing here can be lost:
death pulls you out to the entrance with full HP, cleared rooms stay cleared.

Progress lives in the quest row ("below_the_village", progress bits) so it survives
leaving and logging out. The reward is granted once, by the server, and only after the
nest is destroyed (rewarded flag + quest complete are both checked).
"""
import time

from world_map import FLOOR, WALL, WATER

SEWER_ID = "sewer"
QUEST_ID = "below_the_village"
TITLE = "Ratcatcher"
CHARM_ID = "ratcatcher_charm"
REWARD_COINS = 75
REWARD_SHRIMP = 10
ROOM1_CHEST_COINS = 25
XP_BOOST = 0.10
XP_BOOST_SECONDS = 15 * 60
DEATH_SHRIMP = 3
ENTRY_SHRIMP = 3
CRATE_TOP_UP = 3
SOFTEN_AFTER_DEATHS = 2
SOFTEN_MULT = 0.75
SPIDER_SLOW = 0.10
SPIDER_SLOW_S = 3.0
EAT_PAUSE_S = 1.0
NEST_HITS = 3
NEST_SWING_S = 0.9
SPEAKER = "Seraphine"

# Overworld: a sewer arch beside The Resting Ox, facing the village square.
GRATE_XY = (25, 30)
GRATE_STAND = (25, 28)  # 2 tiles north of the grate — leave without standing on the mouth
SIGN_XY = (23, 29)
VILLAGE_RATS = (("village_rat", 24, 28), ("village_rat", 26, 27))

# Progress bits (quest row progress).
B_STARTED = 1
B_ROOM1 = 2
B_CHEST1 = 4
B_ROOM2 = 8
B_NEST = 16
B_REWARD = 32
B_ENTERED = 64

W, H = 32, 31
ROOM2 = (2, 2, 29, 9)
GATE = ((15, 10), (16, 10))
ROOM1 = (4, 13, 27, 21)
TUNNEL = (15, 22, 16, 28)
SPAWN = (15, 27)
EXIT = (15, 28)            # entry ladder: step on it to leave
LADDER2 = (27, 5)          # exit ladder in room 2
CHEST1 = (25, 14)
CRATE1 = (6, 14)
CRATE2 = (4, 8)
NEST = ((21, 2), (22, 2), (21, 3), (22, 3))
REWARD_CHEST = (26, 2)
CHANNEL_X = (9, 10)
BRIDGE_Y = (5, 6)
TORCHES = ((5, 1), (13, 1), (25, 1), (7, 12), (24, 12), (14, 24), (17, 26), (14, 22))
BONES = ((3, 2), (12, 8), (5, 20), (26, 20))

ROOM1_MONSTERS = (("sewer_rat", 12, 19), ("sewer_rat", 18, 19), ("sewer_rat", 22, 15))
ROOM2_MONSTERS = (("sewer_rat", 5, 3), ("sewer_rat", 14, 7),
                  ("sewer_spider", 18, 5), ("sewer_spider", 24, 7))
SPIDERLINGS = (("spiderling", 20, 3), ("spiderling", 23, 3))  # hatch beside the nest

LINES = {
    "go": "Two rats out front, a nest below. Pick one. Click it. Hit it until it stops.",
    "rat2": "Watch both bars. Theirs should empty first.",
    "loot": "Grab what they drop. Bit grim, but it's coin.",
    "enter": "Mind your step. The tunnel opens into the first room.",
    "room1": "Two at once. If the red bar drops by half, eat. Here, three shrimp.",
    "eat": "Now! Press R (or click your shrimp) to eat.",
    "room1_clear": "That's the lot. Open the chest, then the web gate's yours.",
    "chest1": "Pretty, isn't it? Keep going.",
    "room2": "Spiders first. They bite harder than they look.",
    "nest_locked": "Clear the room first. The spiders guard that nest.",
    "nest": "Burn the nest and we're done here. Three good hits.",
    "nest_hit": "Again!",
    "nest_done": "Nest's gone. Squash the little ones, then the chest by the nest is yours.",
    "reward": "Out you go. Ratcatcher. It suits you. The ladder's right there.",
    "death": "Seraphine pulls you out. Full health, nothing lost, and three shrimp for the road.",
    "soften": "They're getting tired. Go again.",
    "crate": "Shrimp crate. Take what you need, it never runs dry.",
    "crate_full": "You've got plenty of shrimp already.",
    "later": "No rush. 'Below the Village' is in your quest log. The grate's by the Resting Ox.",
    "left": "Progress saved. The grate's here when you want to finish.",
    "done_again": "You've cleared it already, Ratcatcher. Nothing left down there but damp.",
}


def _srv():
    import server as srv
    return srv


# --------------------------------------------------------------------------- map
def build_tiles():
    t = [[WALL] * W for _ in range(H)]

    def rect(x0, y0, x1, y1, v=FLOOR):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                t[y][x] = v

    rect(*ROOM2)
    for x in CHANNEL_X:
        for y in range(ROOM2[1], ROOM2[3] + 1):
            if y not in BRIDGE_Y:
                t[y][x] = WATER
    rect(15, 11, 16, 12)          # narrow corridor behind the web gate
    for gx, gy in GATE:
        t[gy][gx] = WALL          # web gate, opens when room 1 is clear
    rect(*ROOM1)
    rect(*TUNNEL)
    for x, y in NEST:
        t[y][x] = WALL            # the egg nest is an object you hit, not floor
    for x, y in (CHEST1, CRATE1, CRATE2, REWARD_CHEST):
        t[y][x] = WALL            # props block like furniture
    return t


def dungeon_walkable(tiles, x, y):
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return False
    return tiles[y][x] == FLOOR


DUNGEON_SPAWN = SPAWN
CAVE_RETURN = GRATE_STAND


def in_rect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


# --------------------------------------------------------------------------- db
def ensure_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sewer_tutorial ("
        " player_id INTEGER PRIMARY KEY, deaths INTEGER NOT NULL DEFAULT 0,"
        " rewarded INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL DEFAULT '',"
        " boost_until REAL NOT NULL DEFAULT 0, rewarded_at REAL NOT NULL DEFAULT 0)"
    )


def _row(conn, pid):
    ensure_table(conn)
    r = conn.execute("SELECT deaths, rewarded, title, boost_until FROM sewer_tutorial WHERE player_id=?",
                     (pid,)).fetchone()
    if r is None:
        conn.execute("INSERT OR IGNORE INTO sewer_tutorial (player_id) VALUES (?)", (pid,))
        conn.commit()
        return {"deaths": 0, "rewarded": 0, "title": "", "boost_until": 0.0}
    return {"deaths": int(r[0]), "rewarded": int(r[1]), "title": r[2] or "", "boost_until": float(r[3] or 0)}


def _set(conn, pid, **fields):
    _row(conn, pid)
    cols = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE sewer_tutorial SET {cols} WHERE player_id=?", (*fields.values(), pid))
    conn.commit()


def load(session):
    """Cache title + XP boost on the session (called at login and after the reward)."""
    srv = _srv()
    try:
        row = _row(srv.WORLD.db.conn, session.player_id)
    except Exception:
        return
    session.sewer_title = row["title"]
    session.sewer_boost_until = row["boost_until"]


def title_for(session):
    if not hasattr(session, "sewer_title"):
        load(session)
    return getattr(session, "sewer_title", "") or ""


def xp_mult(session, skill):
    if skill not in ("attack", "strength", "defence", "archery"):
        return 1.0
    if not hasattr(session, "sewer_boost_until"):
        load(session)
    return 1.0 + XP_BOOST if time.time() < float(getattr(session, "sewer_boost_until", 0) or 0) else 1.0


def boost_left(session):
    if not hasattr(session, "sewer_boost_until"):
        load(session)
    return max(0, int(float(getattr(session, "sewer_boost_until", 0) or 0) - time.time()))


# --------------------------------------------------------------------------- quest
def progress(session):
    q = (session.quests or {}).get(QUEST_ID) or {}
    return int(q.get("progress") or 0)


def status(session):
    return ((session.quests or {}).get(QUEST_ID) or {}).get("status", "not_started")


def _save_progress(session, bits, status_=None):
    srv = _srv()
    q = session.quests.setdefault(QUEST_ID, {"status": "active", "progress": 0})
    q["progress"] = int(bits)
    if status_:
        q["status"] = status_
    srv.WORLD.db.set_quest_progress(session.player_id, QUEST_ID, q["status"], q["progress"])
    session.quest_log_dirty = True


def ensure_quest(session):
    """Put 'Below the Village' in the log (active). Returns True if it was added now."""
    if QUEST_ID in (session.quests or {}):
        return False
    _save_progress(session, B_STARTED, "active")
    return True


def objective(session):
    bits = progress(session)
    st = status(session)
    if st == "complete":
        return "Cleared. You are the Ratcatcher."
    if not bits & B_ENTERED:
        return "Optional: enter the sewer grate beside the Resting Ox."
    if not bits & B_ROOM1:
        return "Room 1: clear the rats (eat if your HP drops by half)."
    if not bits & B_ROOM2:
        return "Room 2: spiders first, then the rats."
    if not bits & B_NEST:
        return "Destroy the spider nest (3 hits) and its spiderlings."
    return "Open the reward chest by the nest."


# --------------------------------------------------------------------------- helpers
async def say(session, key, style=None):
    srv = _srv()
    msg = {"from": SPEAKER, "text": LINES[key]}
    if style:
        msg["style"] = style
    await srv.send(session.ws, "CHAT_MSG", **msg)
    await srv.send(session.ws, "SEWER_SAY", key=key, text=LINES[key])


def _count(session, item_id):
    return sum(int(e.get("qty") or 1) for e in (session.inventory or {}).values()
               if (e or {}).get("item_id") == item_id)


def _give(session, item_id, qty):
    srv = _srv()
    return bool(srv.WORLD.add_item_to_inventory(session, item_id, qty))


def _spawn(session, specs, room):
    srv = _srv()
    out = []
    for mtype, x, y in specs:
        mid = srv.next_id()
        m = srv.MonsterInstance(mid, mtype, x, y, no_respawn=True)
        m.home_room = room
        session.dungeon["monsters"][mid] = m
        out.append(m)
    return out


def _alive_in(session, room):
    return [m for m in session.dungeon["monsters"].values() if m.alive and in_rect(m.spawn_x, m.spawn_y, room)]


def state(session):
    return (session.dungeon or {}).get("sewer") or {}


def here(session):
    return bool(session.dungeon) and session.dungeon.get("id") == SEWER_ID


def _open_gate(session):
    d = session.dungeon
    for gx, gy in GATE:
        d["tiles"][gy][gx] = FLOOR
    d["sewer"]["gate_open"] = True


# --------------------------------------------------------------------------- build / enter
def build(session):
    bits = progress(session)
    tiles = build_tiles()
    session.dungeon = {
        "id": SEWER_ID, "explore": True, "floor": 1, "floors": 1,
        "label": "Below the Village", "name": "Village Sewer",
        "tiles": tiles, "width": W, "height": H, "monsters": {},
        "return_x": GRATE_STAND[0], "return_y": GRATE_STAND[1],
        "exit_x": EXIT[0], "exit_y": EXIT[1], "props": [],
        "sewer": {
            "gate_open": False, "nest_hits": 0, "nest_burning": False, "spiderlings": False,
            "eat_prompted": False, "said": set(), "last_nest_hit": 0.0,
            "deaths": 0,
        },
    }
    srv = _srv()
    try:
        session.dungeon["sewer"]["deaths"] = _row(srv.WORLD.db.conn, session.player_id)["deaths"]
    except Exception:
        pass
    if not bits & B_ROOM1:
        _spawn(session, ROOM1_MONSTERS, ROOM1)
    else:
        _open_gate(session)
    if not bits & B_ROOM2:
        _spawn(session, ROOM2_MONSTERS, ROOM2)
    session.x, session.y = SPAWN
    session.in_combat_with = None
    session.gathering_node = None
    if getattr(session, "pet_id", None):
        session.pet_x, session.pet_y = session.x, session.y
        session.pet_target_id = None


def client_extra(session):
    st = state(session)
    bits = progress(session)
    return {
        "gate_open": bool(st.get("gate_open")),
        "chest1_open": bool(bits & B_CHEST1),
        "nest_hits": int(st.get("nest_hits") or 0) if not bits & B_NEST else NEST_HITS,
        "nest_gone": bool(bits & B_NEST),
        "reward_open": bool(bits & B_REWARD),
        "room1": list(ROOM1), "room2": list(ROOM2), "gate": [list(g) for g in GATE],
        "chest1": list(CHEST1), "crates": [list(CRATE1), list(CRATE2)],
        "nest": [list(n) for n in NEST], "reward_chest": list(REWARD_CHEST),
        "ladder": list(EXIT), "ladder2": list(LADDER2), "torches": [list(t) for t in TORCHES],
        "bones": [list(b) for b in BONES], "channel_x": list(CHANNEL_X), "bridge_y": list(BRIDGE_Y),
        "deaths": int(st.get("deaths") or 0),
    }


async def _send_state(session):
    srv = _srv()
    await srv.send(session.ws, "SEWER_STATE", **client_extra(session))


async def enter(session):
    """Called by handle_enter_dungeon when the player is at the grate."""
    srv = _srv()
    if status(session) == "complete":
        await say(session, "done_again")
        return
    try:
        ensure_quest(session)
    except Exception:
        srv.log.warning("sewer enter: quest row not saved", exc_info=True)
    # Leave stand is already 2 tiles off the grate; keep return in sync.
    # A locked database must not abort the entrance — the player is already
    # on the grate, and failing here is what made the sewer unreachable.
    session._dungeon_return = GRATE_STAND
    try:
        srv.WORLD.db.save_player_position(session.player_id, *GRATE_STAND)
    except Exception:
        srv.log.warning("sewer enter: return tile not saved", exc_info=True)
    try:
        srv._clear_dungeon_resume(session)
    except Exception:
        srv.log.warning("sewer enter: could not clear dungeon resume", exc_info=True)
    build(session)
    try:
        _save_progress(session, progress(session) | B_STARTED | B_ENTERED)
    except Exception:
        srv.log.warning("sewer enter: progress not saved", exc_info=True)
    srv._bring_pet(session)
    await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await srv.send(session.ws, "QUEST_LOG", quests={q: srv.quest_status_for(session, q) for q in srv.QUESTS})
    await say(session, "enter")


async def start_from_log(session):
    """'Below the Village' in the quest log: walk you to the grate (no teleport into combat)."""
    srv = _srv()
    if session.dungeon or status(session) == "complete":
        return False
    ensure_quest(session)
    await srv.send(session.ws, "QUEST_LOG", quests={q: srv.quest_status_for(session, q) for q in srv.QUESTS})
    await srv.send(session.ws, "SEWER_TRACK", x=GRATE_XY[0], y=GRATE_XY[1])
    return True


async def offer_choice(session, choice):
    """Seraphine's offer at the end of the tour. go = start now, later = optional quest in the log."""
    srv = _srv()
    added = ensure_quest(session)
    await srv.send(session.ws, "QUEST_LOG", quests={q: srv.quest_status_for(session, q) for q in srv.QUESTS})
    if choice == "go":
        if not session.dungeon and not session.in_combat_with:
            session.x, session.y = GRATE_STAND
            srv.WORLD.db.save_player_position(session.player_id, *GRATE_STAND)
            await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await srv.send(session.ws, "SEWER_TRACK", x=GRATE_XY[0], y=GRATE_XY[1])
        await say(session, "go")
    else:
        await say(session, "later")
    return added


# --------------------------------------------------------------------------- events
async def on_step(session):
    """After a step inside. Returns True if the step left the dungeon."""
    srv = _srv()
    st = state(session)
    bits = progress(session)
    x, y = session.x, session.y
    if (x, y) == LADDER2:
        await leave(session)
        return True
    if in_rect(x, y, ROOM1) and "room1" not in st["said"] and not bits & B_ROOM1:
        st["said"].add("room1")
        _give(session, "cooked_shrimp", ENTRY_SHRIMP)
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await say(session, "room1")
    if in_rect(x, y, ROOM2) and "room2" not in st["said"] and not bits & B_ROOM2:
        st["said"].add("room2")
        await say(session, "room2")
    return False


async def leave(session):
    srv = _srv()
    done = status(session) == "complete"
    await srv.handle_leave_dungeon(session, silent=True)
    if not done:
        await say(session, "left")


async def on_kill(session, monster):
    srv = _srv()
    st = state(session)
    bits = progress(session)
    if not bits & B_ROOM1 and in_rect(monster.spawn_x, monster.spawn_y, ROOM1):
        if not _alive_in(session, ROOM1):
            _save_progress(session, bits | B_ROOM1)
            _open_gate(session)
            await srv.send(session.ws, "DUNGEON_TILES", changes=[[gx, gy, FLOOR] for gx, gy in GATE])
            await say(session, "room1_clear")
    bits = progress(session)
    if not bits & B_ROOM2 and monster.type != "spiderling" and in_rect(monster.spawn_x, monster.spawn_y, ROOM2):
        rest = [m for m in _alive_in(session, ROOM2) if m.type != "spiderling"]
        if not rest:
            _save_progress(session, bits | B_ROOM2)
            await say(session, "nest")
    bits = progress(session)
    if monster.type == "spiderling" and st.get("nest_hits", 0) >= NEST_HITS and not bits & B_NEST:
        if not [m for m in session.dungeon["monsters"].values() if m.alive and m.type == "spiderling"]:
            _save_progress(session, bits | B_NEST)
            await say(session, "nest_done")
    await _send_state(session)


def _adjacent(session, cells):
    return any(max(abs(session.x - cx), abs(session.y - cy)) <= 1 for cx, cy in cells)


async def handle_interact(session, msg):
    srv = _srv()
    if not here(session):
        return
    try:
        tx, ty = int(msg.get("x")), int(msg.get("y"))
    except (TypeError, ValueError):
        return
    st = state(session)
    bits = progress(session)
    if (tx, ty) in (CRATE1, CRATE2) and _adjacent(session, [(tx, ty)]):
        have = _count(session, "cooked_shrimp")
        if have >= CRATE_TOP_UP:
            await say(session, "crate_full")
        else:
            _give(session, "cooked_shrimp", CRATE_TOP_UP - have)
            await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await say(session, "crate")
        return
    if (tx, ty) == CHEST1 and _adjacent(session, [CHEST1]):
        if not bits & B_ROOM1:
            await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": "Rats first, treasure after."})
            return
        if bits & B_CHEST1:
            await srv.send(session.ws, "CHAT_MSG", **{"from": "Chest", "text": "Empty."})
            return
        _save_progress(session, bits | B_CHEST1)
        srv.WORLD.add_coins(session, ROOM1_CHEST_COINS)
        await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await srv.send(session.ws, "SEWER_LOOT", items=[["coins", ROOM1_CHEST_COINS]], preview=CHARM_ID)
        await say(session, "chest1")
        await _send_state(session)
        return
    if (tx, ty) in NEST and _adjacent(session, NEST):
        await _hit_nest(session)
        return
    if (tx, ty) == REWARD_CHEST and _adjacent(session, [REWARD_CHEST]):
        await claim_reward(session)
        return


def _aggro(session, monsters):
    """Wake monsters onto the player (nest disturb / spiderling hatch)."""
    if not monsters:
        return
    pid = session.player_id
    nearest = None
    best = 10**9
    for m in monsters:
        if not m.alive:
            continue
        m.target_player_id = pid
        m.patrol_steps_left = 0
        m.patrol_leg = ""
        dist = max(abs(session.x - m.x), abs(session.y - m.y))
        if dist < best:
            best = dist
            nearest = m
    if nearest is not None and not session.in_combat_with:
        session.in_combat_with = ("monster", nearest.id)


async def _hit_nest(session):
    srv = _srv()
    st = state(session)
    bits = progress(session)
    if bits & B_NEST or st.get("nest_hits", 0) >= NEST_HITS:
        return
    if not bits & B_ROOM2:
        # Seraphine's line: the spiders guard the nest — disturb it and they come.
        guards = [
            m for m in session.dungeon["monsters"].values()
            if m.alive and m.type == "sewer_spider" and in_rect(m.spawn_x, m.spawn_y, ROOM2)
        ]
        _aggro(session, guards)
        await say(session, "nest_locked")
        return
    now = time.time()
    if now - float(st.get("last_nest_hit") or 0) < NEST_SWING_S:
        return
    st["last_nest_hit"] = now
    st["nest_hits"] = int(st.get("nest_hits") or 0) + 1
    if st["nest_hits"] == 1 and not st.get("spiderlings"):
        st["spiderlings"] = True
        hatched = _spawn(session, SPIDERLINGS, ROOM2)
        _aggro(session, hatched)
    if st["nest_hits"] >= NEST_HITS:
        if not [m for m in session.dungeon["monsters"].values() if m.alive and m.type == "spiderling"]:
            _save_progress(session, bits | B_NEST)
            await say(session, "nest_done")
        else:
            await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": "Nest's burning! Now the spiderlings."})
    else:
        await say(session, "nest_hit")
    await _send_state(session)


async def claim_reward(session):
    """Server-validated, once per character: nest destroyed, not rewarded before."""
    srv = _srv()
    bits = progress(session)
    conn = srv.WORLD.db.conn
    row = _row(conn, session.player_id)
    if row["rewarded"] or status(session) == "complete":
        await srv.send(session.ws, "CHAT_MSG", **{"from": "Chest", "text": "Empty. You already took the reward."})
        return False
    if not bits & B_NEST:
        await srv.send(session.ws, "CHAT_MSG", **{"from": SPEAKER, "text": "Locked tight until that nest is gone."})
        return False
    # Mark first so a crash mid-grant cannot pay twice.
    now = time.time()
    _set(conn, session.player_id, rewarded=1, title=TITLE, boost_until=now + XP_BOOST_SECONDS, rewarded_at=now)
    _save_progress(session, bits | B_REWARD, "complete")
    _give(session, CHARM_ID, 1)
    _give(session, "cooked_shrimp", REWARD_SHRIMP)
    srv.WORLD.add_coins(session, REWARD_COINS)
    load(session)
    # Equip Ratcatcher if they have no title chosen yet (can clear/change in Settings).
    try:
        import titles as titles_mod
        if not titles_mod.active_id(session):
            titles_mod.set_active(session, titles_mod.SEWER_TITLE_ID)
    except Exception:
        pass
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await srv.send(session.ws, "QUEST_LOG", quests={q: srv.quest_status_for(session, q) for q in srv.QUESTS})
    await srv.send(session.ws, "SEWER_REWARD", title=TITLE, items=[[CHARM_ID, 1], ["cooked_shrimp", REWARD_SHRIMP],
                   ["coins", REWARD_COINS]], xp_boost=XP_BOOST, boost_seconds=XP_BOOST_SECONDS)
    await say(session, "reward", style="gold")
    await _send_state(session)
    return True


# --------------------------------------------------------------------------- combat hooks
def scale_damage(session, monster, dmg):
    st = state(session)
    if dmg > 0 and int(st.get("deaths") or 0) >= SOFTEN_AFTER_DEATHS:
        dmg = int(dmg * SOFTEN_MULT)   # floor: a 1 becomes 0, a 3 becomes 2
    if dmg > 0 and monster.type == "sewer_spider":
        session.sewer_slow_until = time.time() + SPIDER_SLOW_S
    return dmg


def swing_mult(session):
    return 1.0 + SPIDER_SLOW if time.time() < float(getattr(session, "sewer_slow_until", 0) or 0) else 1.0


async def after_hits(session):
    """First time HP falls under half in room 1: pause the fight 1s and prompt to eat."""
    srv = _srv()
    st = state(session)
    if st.get("eat_prompted") or session.hp <= 0:
        return
    if session.hp * 2 >= session.max_hp():
        return
    st["eat_prompted"] = True
    until = time.time() + EAT_PAUSE_S
    for m in session.dungeon["monsters"].values():
        if m.alive:
            m.frozen_until = max(float(m.frozen_until or 0), until)
    session.next_swing_at = max(float(getattr(session, "next_swing_at", 0) or 0), until)
    await srv.send(session.ws, "SEWER_EAT_PROMPT", seconds=EAT_PAUSE_S, text=LINES["eat"])
    await say(session, "eat")


async def on_death(session, events, dungeon_tag):
    """No hard fail: full HP at the entrance, nothing lost, cleared rooms stay cleared, +3 shrimp."""
    srv = _srv()
    st = state(session)
    st["deaths"] = int(st.get("deaths") or 0) + 1
    try:
        _set(srv.WORLD.db.conn, session.player_id, deaths=st["deaths"])
    except Exception:
        pass
    session.hp = session.max_hp()
    session.in_combat_with = None
    session.pet_target_id = None
    for m in session.dungeon["monsters"].values():
        m.target_player_id = None
        if m.alive:
            m.hp = m.max_hp
            m.x, m.y = m.spawn_x, m.spawn_y
    # An unfinished nest fight starts over; the nest itself regrows.
    if not progress(session) & B_NEST and st.get("nest_hits"):
        st["nest_hits"] = 0
        st["spiderlings"] = False
        for mid in [k for k, m in session.dungeon["monsters"].items() if m.type == "spiderling"]:
            session.dungeon["monsters"].pop(mid, None)
    st["eat_prompted"] = False
    session.x, session.y = SPAWN
    _give(session, "cooked_shrimp", DEATH_SHRIMP)
    srv.WORLD.db.save_player_stats(session.player_id, hp=session.hp)
    data = {"entity_id": session.player_id, "entity_kind": "player", "coins_lost": 0, "where": "sewer"}
    if dungeon_tag:
        data["_dungeon_player"] = dungeon_tag
    events.append({"type": "DEATH", "data": data})
    await srv.send(session.ws, "DUNGEON_ENTER", **srv._dungeon_payload(session))
    await srv.send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await srv.send(session.ws, "SEWER_RESCUE", deaths=st["deaths"])
    await say(session, "death")
    if st["deaths"] == SOFTEN_AFTER_DEATHS:
        await say(session, "soften")
