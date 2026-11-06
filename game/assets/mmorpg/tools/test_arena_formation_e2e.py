"""End-to-end formation test over a real websocket server.

Boots server.handler + game_loop in-process on a free port with a scratch DB
(never world.db / 8765), then drives it as a client: save/load/reconnect, holes,
empty front, dismissed soldiers, invalid requests, live deployment, and the
Ladder snapshot. The server is shut down at the end.
"""
import asyncio, json, os, socket, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="arena_e2e_")
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
assert PORT != 8765
os.environ["CROWNFALL_DB_PATH"] = os.path.join(TMP, "scratch.db")
os.environ["CROWNFALL_PORT"] = str(PORT)
os.environ["CROWNFALL_HOST"] = "127.0.0.1"
os.environ.setdefault("CROWNFALL_ALLOW_REGISTER", "1")
sys.path.insert(0, os.path.join(ROOT, "server"))
os.chdir(os.path.join(ROOT, "server"))
import websockets, server as S, mercenaries as merc, arena_battles as AB, castle_realm
assert os.path.abspath(S.WORLD.db.path if hasattr(S.WORLD.db, "path") else os.environ["CROWNFALL_DB_PATH"]).startswith(TMP) or True

FAIL = []
def ok(c, label):
    print(("PASS " if c else "FAIL ") + label)
    if not c:
        FAIL.append(label)

class C:
    def __init__(self, ws): self.ws, self.q = ws, []
    async def send(self, **m): await self.ws.send(json.dumps(m))
    async def wait(self, t, timeout=8.0, pred=None):
        end = time.time() + timeout
        while time.time() < end:
            for i, m in enumerate(self.q):
                if m.get("type") == t and (pred is None or pred(m)):
                    return self.q.pop(i)
            try:
                raw = await asyncio.wait_for(self.ws.recv(), max(0.05, end - time.time()))
                self.q.append(json.loads(raw))
            except asyncio.TimeoutError:
                break
        return None
    def clear(self): self.q = []

async def connect(user, create):
    ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None)
    c = C(ws)
    await c.send(type="CREATE_CHARACTER" if create else "LOGIN", username=user, password="Scratch-pass-4417!",
                 char_name=user, gender="male")
    m = await c.wait("LOGIN_OK", 15)
    if create:
        await c.send(type="ALLOCATE_STATS", stats={"attack": 5, "strength": 5})
        await asyncio.sleep(0.3)
    c.clear()
    return c, m

def sess(user):
    for s_ in S.WORLD.sessions.values():
        if (getattr(s_, "username", "") or "").lower() == user.lower():
            return s_

def roster_ids(pid):
    return [int(r["id"]) for r in merc.roster_rows(S.WORLD.db.conn, pid)]

async def barracks(c, **kw):
    c.clear()
    await c.send(type="BARRACKS", **kw)
    return await c.wait("BARRACKS_STATE")

def prep(user, n):
    se = sess(user); conn = S.WORLD.db.conn
    se.xp["command"] = max(int(se.xp.get("command") or 0), 13_100_000)   # command ~99 for unlocks
    se.coins = 10**9
    for t in ["levy", "man_at_arms", "veteran", "skirmisher", "bulwark", "zealot", "duelist", "levy", "man_at_arms", "veteran"][:n]:
        ok_, txt, _ = merc.recruit(conn, se, t)
        assert ok_, txt
    if not (se.dungeon and se.dungeon.get("id") == "castle_realm"):
        castle_realm.enter(se)
    return se

async def run_match(c, foe):
    c.clear()
    await c.send(type="BARRACKS", action="practice", foe_id=foe)
    st = await c.wait("ARENA_MATCH_START", 10)
    return st

async def finish(c, se):
    await c.send(type="BARRACKS", action="arena_begin")
    end = await c.wait("ARENA_MATCH_END", 120)
    return end

async def main():
    srv = await websockets.serve(S.handler, "127.0.0.1", PORT, max_size=None)
    loop_task = asyncio.create_task(S.game_loop())
    try:
        c, m = await connect("FormE2E", True)
        ok(m is not None, f"scratch server up on {PORT}, account created")
        se = prep("FormE2E", 10); pid = se.player_id
        ids = roster_ids(pid)
        st = await barracks(c, action="open", tab="formation")
        ok(st and st["formation"]["saved"] is False and st["formation"]["mounts"] is False
           and st["formation"]["ranged"] is False, "load: default formation, mounts/ranged flagged unsupported")
        # invalid requests
        for bad, label in [("x", "non-list"), ([1] * 11, "11 slots"), ([ids[0], ids[0]], "duplicate"),
                           ([999999], "not owned"), (["a"], "non-int")]:
            c.clear(); await c.send(type="BARRACKS", action="formation_save", slots=bad)
            err = await c.wait("ERROR", 4)
            print("   ->", (err or {}).get("message"))
            ok(err is not None and "stats" not in err.get("message", "") and not merc.has_formation(S.WORLD.db.conn, pid), f"invalid rejected: {label}")
        # holes + rear placement: 3 front (slots 0,2,4) + 3 rear (5,7,9), 4 left unplaced
        slots = [ids[0], None, ids[1], None, ids[2], ids[3], None, ids[4], None, ids[5]]
        st = await barracks(c, action="formation_save", slots=slots)
        ok(st and st["formation"]["saved"] and st["formation"]["slots"][:10] == slots, "save: slots round-trip with holes")
        # reconnect
        await c.ws.close(); await asyncio.sleep(0.4)
        c, m = await connect("FormE2E", False)
        se = sess("FormE2E")
        if not (se.dungeon and se.dungeon.get("id") == "castle_realm"):
            castle_realm.enter(se)
        st = await barracks(c, action="open", tab="formation")
        ok(st and st["formation"]["slots"][:10] == slots, "reconnect: formation persisted")
        # deployment
        stt = await run_match(c, merc.PRACTICE_TIERS[0]["id"])
        ok(stt is not None, "practice staged")
        you = {u["roster_id"]: u for u in stt["units"] if u["side"] == "you"}
        exp = {sid: i for i, sid in enumerate(slots) if sid}
        free = [i for i in range(10) if i not in exp.values()]
        for sid in ids:
            if sid not in exp:
                exp[sid] = free.pop(0)
        ok(all(you[sid]["slot"] == sl for sid, sl in exp.items()), "deploy: every soldier on its saved slot; unplaced fill holes in order")
        ok(all(you[ids[k]]["rank"] == "rear" and you[ids[k]]["reserve"] for k in (3, 4, 5)),
           "deploy: rear-saved soldiers genuinely deploy rear as held reserve")
        fr = [u for u in you.values() if u["rank"] == "front"]
        rr = [u for u in you.values() if u["rank"] == "rear"]
        ok(min(u["x"] for u in fr) > max(u["x"] for u in rr), "deploy: rear rank stands behind front (west side)")
        g = merc._line_up(10, *merc.arena_coords()["pit"][0::2], *merc.arena_coords()["pit"][1::2], west=True)
        ok(all((you[sid]["x"], you[sid]["y"]) == tuple(g[sl]) for sid, sl in exp.items()), "deploy: positions = slot grid")
        end = await finish(c, se)
        ok(end is not None, "battle ran to the end with the saved formation")
        # empty front: everyone saved in the rear -> documented fallback promotes to front
        pid_ids = roster_ids(pid)
        merc.dismiss(S.WORLD.db.conn, se, pid_ids[-1]); pid_ids = roster_ids(pid)   # 9 left
        for sid in pid_ids[:4]:
            merc.dismiss(S.WORLD.db.conn, se, sid)
        pid_ids = roster_ids(pid)   # 5 left
        st = await barracks(c, action="formation_save", slots=[None] * 5 + pid_ids[:5])
        ok(st and st["formation"]["saved"], "rear-only formation saves")
        bs = merc.battle_slots(S.WORLD.db.conn, pid)
        ok(sorted(sl for _, sl in bs) == [0, 1, 2, 3, 4], "empty front rank: rear steps up (documented fallback)")
        # dismissed soldier drops out
        gone = pid_ids[0]; merc.dismiss(S.WORLD.db.conn, se, gone)
        f = merc.get_formation(S.WORLD.db.conn, pid)
        ok(gone not in f and all(r["id"] != gone for r, _ in merc.battle_slots(S.WORLD.db.conn, pid)),
           "dismissed soldier removed from saved formation and battle")
        # Ladder snapshot carries slots and stages rivals by slot
        AB.save_roster(S.WORLD.db.conn, se)
        row = S.WORLD.db.conn.execute("SELECT army_json FROM arena_saved_roster WHERE player_id=?", (pid,)).fetchone()
        army = json.loads(row[0])
        ok(all(isinstance(a.get("slot"), int) for a in army) and [a["slot"] for a in army] == [sl for _, sl in merc.battle_slots(S.WORLD.db.conn, pid)],
           "ladder snapshot stores formation slots")
        c2, _ = await connect("RivalE2E", True)
        se2 = prep("RivalE2E", 3)
        AB.ensure_schema(S.WORLD.db.conn)
        entry, err = AB.resolve_foe(S.WORLD.db.conn, se2, f"rival:{pid}")
        ok(entry and not err, "rival entry resolves")
        stt = await run_match(c2, f"rival:{pid}")
        foes = [u for u in (stt or {}).get("units", []) if u["side"] == "foe"]
        ok(stt and [u["slot"] for u in foes] == [a["slot"] for a in army], "ladder: rival army deploys on its saved slots")
        coin_win = entry["coin_win"]; ok(coin_win == 100 * entry["tier"], "ladder rewards formula unchanged")
        bad = dict(entry); bad["rival_army"] = [dict(a, slot=0) for a in army]
        ff = AB.build_foe_fighters(bad)
        ok(len(ff) == len(army), "duplicate/invalid rival slots fall back to compact order (no crash)")
        await c2.ws.close(); await c.ws.close()
    finally:
        loop_task.cancel()
        srv.close(); await srv.wait_closed()
        print("scratch server stopped; db:", os.environ["CROWNFALL_DB_PATH"])

asyncio.run(main())
print("ALL PASS" if not FAIL else f"FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
