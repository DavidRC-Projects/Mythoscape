"""War for the Crown: structure damage, founding reign, and siege registration."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "server"))

import database  # noqa: E402
database.Database.__init__.__defaults__ = (":memory:",)

import apprentice as ap  # noqa: E402
import clans  # noqa: E402
import crown_siege  # noqa: E402
import royal_treasury as rt  # noqa: E402
import ruling  # noqa: E402
import throne  # noqa: E402

T0 = 1_800_000_000.0


def check(ok, msg):
    if not ok:
        raise AssertionError(msg)
    print("ok ", msg)


def make_db():
    db = database.Database(":memory:")
    crown_siege.ensure_schema(db.conn)
    throne.ensure_schema(db.conn)
    ruling.ensure_schema(db.conn)
    clans.ensure_tables(db.conn)
    rt.ensure_schema(db.conn)
    clans._CONN = db.conn
    crown_siege._CONN = db.conn
    crown_siege.invalidate_breaches()
    return db


def _pad_guild(db, leader_username, leader_name, guild_name, humans):
    """Create a guild with ``humans`` members (leader + fillers). Returns (leader_id, clan_id)."""
    db.create_account(leader_username, "pw", leader_name, gender="male")
    lid = db.conn.execute(
        "SELECT id FROM players WHERE username = ?", (leader_username,)
    ).fetchone()[0]
    ap.bank_set(db.conn, lid, clans.CHARTER_COST)
    ok, _m, cid = clans.create_core(lid, guild_name, now=T0)
    check(ok, f"create guild {guild_name}")
    for i in range(1, humans):
        uname = f"{leader_username}_m{i}"
        cname = f"{leader_name}M{i}"
        db.create_account(uname, "pw", cname, gender="male")
        mid = db.conn.execute("SELECT id FROM players WHERE username = ?", (uname,)).fetchone()[0]
        clans.join_core(mid, cid, now=T0 + i)
    return lid, cid


def test_hp_bands():
    check(crown_siege.state_for(10000, 10000) == "intact", "full hp is intact")
    check(crown_siege.state_for(7000, 10000) == "intact", "above two thirds is intact")
    check(crown_siege.state_for(6666, 10000) == "damaged", "under two thirds is damaged")
    check(crown_siege.state_for(4000, 10000) == "damaged", "mid band is damaged")
    check(crown_siege.state_for(3332, 10000) == "heavily_damaged", "under one third is heavily damaged")
    check(crown_siege.state_for(1, 10000) == "heavily_damaged", "one hp is heavily damaged")
    check(crown_siege.state_for(0, 10000) == "destroyed", "zero is destroyed")
    check(crown_siege.state_for(-5, 10000) == "destroyed", "negative clamps to destroyed")


def test_damage_persists():
    db = make_db()
    conn = db.conn
    gate = crown_siege.get_structure(conn, "outer_gate")
    check(gate["state"] == "intact" and gate["hp"] == gate["max_hp"], "gate starts intact")
    updated = crown_siege.apply_damage(conn, "outer_gate", 4000)
    check(updated["hp"] == gate["max_hp"] - 4000, "damage subtracts hp")
    check(updated["state"] == "damaged", "gate enters damaged band")
    again = crown_siege.get_structure(conn, "outer_gate")
    check(again["hp"] == updated["hp"], "damage persists across reads")
    dead = crown_siege.apply_damage(conn, "outer_gate", 999999)
    check(dead["hp"] == 0 and dead["state"] == "destroyed", "hp cannot go below zero")
    # Nothing in the live castle calls apply_damage yet — paths stay closed.
    check(dead["effect"].startswith("Opens"), "destroyed effect is recorded for later")
    check(crown_siege.apply_damage(conn, "no_such", 1) is None, "unknown structure ignored")
    listed = crown_siege.list_structures(conn)
    check(len(listed) == 7, "all seven structures exist")
    pub = crown_siege.public_state(conn)
    check(pub["outer_gate"]["state"] == "destroyed", "public payload carries state")
    check(pub["royal_keep"]["state"] == "intact", "untouched keep stays intact")


def test_founder_once():
    db = make_db()
    conn = db.conn
    # No founder account yet — nothing changes.
    check(crown_siege.ensure_founder(conn) is False, "no founder account leaves NPC king")
    st = throne.state(conn)
    check(st["monarch_kind"] == "npc", "throne still npc")

    db.create_account("david", "pw", "The Creator", gender="male")
    pid = conn.execute("SELECT id FROM players WHERE username = 'david'").fetchone()[0]

    check(crown_siege.ensure_founder(conn) is True, "founder crowning runs while npc")
    st = throne.state(conn)
    check(st["monarch_kind"] == "player" and int(st["monarch_player_id"]) == int(pid), "Creator is king")
    check(st["path"] == "founder", "path is founder")
    title = conn.execute("SELECT royal_title FROM players WHERE id = ?", (pid,)).fetchone()[0]
    check(title == "King", f"royal title set ({title})")
    reign = ruling.current_reign(conn)
    check(reign and reign["path"] == "founder" and reign["name"] == "The Creator", "reign recorded")

    # Second start must not replace the player king.
    db.create_account("other", "pw", "Other", gender="male")
    check(crown_siege.ensure_founder(conn) is False, "second start does not re-crown")
    st2 = throne.state(conn)
    check(int(st2["monarch_player_id"]) == int(pid), "same monarch remains")

    lines = crown_siege.hall_lines(conn)
    blob = " ".join(lines).lower()
    check("founded" in blob and "no siege" in blob, "Great Hall mentions founding, no siege")
    check("the creator" in blob, "Great Hall names The Creator")


def test_client_overlay_helpers():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((8, 8))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import castle_realm_renderer as cr

    class Stub:
        dungeon = {
            "id": "castle_realm",
            "plane": "realm",
            "crown_siege": {
                "outer_gate": {"state": "heavily_damaged", "hp": 100, "max_hp": 10000},
                "royal_keep": {"state": "intact", "hp": 12000, "max_hp": 12000},
            },
        }

    check(cr._siege_state(Stub(), "outer_gate") == "heavily_damaged", "client reads gate state")
    check(cr._siege_state(Stub(), "royal_keep") == "intact", "client reads keep state")
    check(cr._siege_state(Stub(), "missing") == "intact", "missing structure defaults intact")
    surf = pygame.Surface((40, 40), pygame.SRCALPHA)
    surf.fill((200, 180, 140, 255))
    before = pygame.surfarray.array3d(surf).copy()
    cr._siege_overlay(surf, surf.get_rect(), "destroyed", cracks=True)
    after = pygame.surfarray.array3d(surf)
    check((before != after).any(), "destroyed overlay changes pixels")


def test_register_confirm_and_schedule():
    db = make_db()
    conn = db.conn
    atk_leader, atk = _pad_guild(db, "atk", "Attacker", "Storm Guild", crown_siege.HUMAN_MIN)
    dfn_leader, dfn = _pad_guild(db, "dfn", "Defender", "Shield Guild", crown_siege.HUMAN_MIN)

    ok, msg, slot = crown_siege.register(conn, atk_leader, "attack", now=T0)
    check(ok and slot["status"] == "reserved", f"first attacker reserves ({msg})")
    check(slot["confirm_deadline"] == T0 + crown_siege.CONFIRM_SECONDS, "48h confirm deadline set")

    # Second attacker queues behind the first.
    a2, _ = _pad_guild(db, "atk2", "AttackerTwo", "River Guild", 5)
    ok, msg, slot2 = crown_siege.register(conn, a2, "attack", now=T0 + 10)
    check(ok and slot2["status"] == "queued", f"second attacker queues ({msg})")

    ok, msg = crown_siege.confirm(conn, atk_leader, now=T0 + 60)
    check(ok, f"attacker confirms with {crown_siege.HUMAN_MIN} humans ({msg})")
    ok, msg, dslot = crown_siege.register(conn, dfn_leader, "defend", now=T0 + 120)
    check(ok and dslot["status"] == "reserved", f"defender reserves ({msg})")
    ok, msg = crown_siege.confirm(conn, dfn_leader, now=T0 + 180)
    check(ok, f"defender confirms ({msg})")
    war = crown_siege.current_war(conn)
    check(war and war["status"] == "scheduled", f"both sides confirmed → scheduled ({war})")
    lines = " ".join(crown_siege.war_lines(conn, now=T0 + 200)).lower()
    check("storm guild" in lines and "shield guild" in lines, "war board names both leads")


def test_confirm_timeout_promotes_queue():
    db = make_db()
    conn = db.conn
    first, _ = _pad_guild(db, "first", "FirstLead", "Early Birds", 3)
    second, _ = _pad_guild(db, "second", "SecondLead", "Next In Line", crown_siege.HUMAN_MIN)
    ok, _msg, slot = crown_siege.register(conn, first, "attack", now=T0)
    check(ok and slot["status"] == "reserved", "first reserves with too few humans")
    ok, _msg, q = crown_siege.register(conn, second, "attack", now=T0 + 1)
    check(ok and q["status"] == "queued", "second queues")
    # Before deadline: still reserved.
    notices = crown_siege.tick_wars(conn, now=T0 + crown_siege.CONFIRM_SECONDS - 10)
    check(not notices, "no promote before deadline")
    slot = crown_siege.get_slot(conn, slot["id"])
    check(slot["status"] == "reserved", "still reserved inside window")
    # After deadline: first forfeits, second promoted.
    notices = crown_siege.tick_wars(conn, now=T0 + crown_siege.CONFIRM_SECONDS + 1)
    check(any("failed to confirm" in n.lower() for n in notices), "timeout notice")
    slot = crown_siege.get_slot(conn, slot["id"])
    check(slot["status"] == "forfeited", "first forfeited after timeout")
    promoted = crown_siege._lead_slot(conn, crown_siege.current_war(conn)["id"], "attack")
    check(promoted and promoted["name"] == "Next In Line" and promoted["status"] == "reserved",
          "next guild takes the slot")
    ok, msg = crown_siege.confirm(conn, second, now=T0 + crown_siege.CONFIRM_SECONDS + 30)
    check(ok, f"promoted guild confirms ({msg})")


def test_alliances_count_toward_human_min():
    db = make_db()
    conn = db.conn
    # Lead has 12 humans; ally brings enough to reach HUMAN_MIN.
    need_ally = 8
    lead_n = crown_siege.HUMAN_MIN - need_ally
    lead, lead_cid = _pad_guild(db, "lead", "LeadName", "Vanguard", lead_n)
    ally, ally_cid = _pad_guild(db, "ally", "AllyName", "Free Company", need_ally)
    ok, _msg, slot = crown_siege.register(conn, lead, "attack", now=T0)
    check(ok and slot["status"] == "reserved", "vanguard reserves")
    ok, msg = crown_siege.confirm(conn, lead, now=T0 + 10)
    check(not ok and "humans" in msg.lower(), f"cannot confirm under-strength ({msg})")
    ok, msg = crown_siege.invite_ally(conn, lead, "Free Company", now=T0 + 20)
    check(ok, f"invite ally ({msg})")
    ok, msg = crown_siege.respond_ally(conn, ally, True, now=T0 + 30)
    check(ok, f"ally accepts ({msg})")
    humans = crown_siege._alliance_humans(conn, slot["war_id"], lead_cid, "attack")
    check(humans >= crown_siege.HUMAN_MIN, f"alliance humans {humans}")
    ok, msg = crown_siege.confirm(conn, lead, now=T0 + 40)
    check(ok, f"confirm with allies ({msg})")
    pub = crown_siege.public_state(conn)
    check(pub["war"]["sides"]["attack"]["allies"][0]["name"] == "Free Company", "public lists ally")


def test_king_guild_cannot_attack():
    db = make_db()
    conn = db.conn
    king, _ = _pad_guild(db, "david", "The Creator", "First Guild", 5)
    crown_siege.ensure_founder(conn, now=T0)
    ok, msg, *_ = crown_siege.register(conn, king, "attack", now=T0 + 1)
    # register returns 2-tuple on failure
    if isinstance(ok, bool) and not ok:
        check("king" in msg.lower() or "cannot" in msg.lower(), f"king blocked from attack ({msg})")
    else:
        raise AssertionError(f"expected king attack to fail, got {ok!r} {msg!r}")
    ok, msg, slot = crown_siege.register(conn, king, "defend", now=T0 + 2)
    check(ok and slot["side"] == "defend", f"king guild may defend ({msg})")


def test_siege_command_parser():
    db = make_db()
    conn = db.conn
    lead, _ = _pad_guild(db, "cmd", "CmdLead", "Command Guild", crown_siege.HUMAN_MIN)
    ok, lines = crown_siege.handle_command(conn, lead, "/siege status")
    check(ok and lines, "status lines")
    ok, lines = crown_siege.handle_command(conn, lead, "/siege register attack")
    check(ok and "reserved" in lines[0].lower(), f"command register ({lines})")
    ok, lines = crown_siege.handle_command(conn, lead, "/siege confirm")
    check(ok and "confirmed" in lines[0].lower(), f"command confirm ({lines})")


def test_storehouse_deposit_alloc_contrib():
    db = make_db()
    conn = db.conn
    lead, lead_cid = _pad_guild(db, "sup", "Supplier", "Supply Guild", crown_siege.HUMAN_MIN)
    helper_name = "sup_m1"
    helper = conn.execute(
        "SELECT id FROM players WHERE username = ?", (helper_name,)
    ).fetchone()[0]
    crown_siege.register(conn, lead, "attack", now=T0)
    crown_siege.confirm(conn, lead, now=T0 + 1)

    # Outsiders cannot deposit.
    outsider, _ = _pad_guild(db, "out", "Outsider", "Bystanders", 3)
    ok, msg = crown_siege.deposit(conn, outsider, "logs", 10, now=T0 + 2)
    check(not ok and "registered" in msg.lower(), f"outsider blocked ({msg})")

    bag = {"logs": 50, "iron_ore": 20, "coal": 15, "iron_bar": 5}

    def take(item_id, qty, bag=bag):
        if bag.get(item_id, 0) < qty:
            return False
        bag[item_id] -= qty
        return True

    ok, msg = crown_siege.deposit(conn, lead, "logs", 40, now=T0 + 3, take_fn=take)
    check(ok and bag["logs"] == 10, f"leader deposit ({msg})")
    ok, msg = crown_siege.deposit(conn, helper, "iron_ore", 10, now=T0 + 4, take_fn=take)
    check(ok, f"member deposit ({msg})")
    ok, msg = crown_siege.deposit(conn, helper, "coal", 15, now=T0 + 5, take_fn=take)
    check(ok, f"coal as stone ({msg})")
    ok, msg = crown_siege.deposit(conn, lead, "iron_bar", 5, now=T0 + 6, take_fn=take)
    check(ok, f"bars deposited ({msg})")

    war = crown_siege.current_war(conn)
    stock = crown_siege.store_stock(conn, war["id"], lead_cid)
    check(stock["timber"] == 40 and stock["ore"] == 10 and stock["stone"] == 15 and stock["bars"] == 5,
          f"stock totals {stock}")

    # Default allocation present; leader may rebalance.
    alloc = crown_siege.store_alloc(conn, war["id"], lead_cid)
    check(sum(alloc.values()) == 100, f"default alloc sums to 100 ({alloc})")
    ok, msg = crown_siege.set_allocation(
        conn, lead, {"rams": 50, "ladders": 20, "barricades": 20, "reserve": 10}, now=T0 + 7,
    )
    check(ok, f"set alloc ({msg})")
    alloc = crown_siege.store_alloc(conn, war["id"], lead_cid)
    check(alloc["rams"] == 50 and alloc["reserve"] == 10, "alloc updated")
    ok, msg = crown_siege.set_allocation(
        conn, lead, {"rams": 50, "ladders": 50, "barricades": 50, "reserve": 50}, now=T0 + 8,
    )
    check(not ok and "100" in msg, f"alloc must sum to 100 ({msg})")

    board = crown_siege.contrib_board(conn)
    check(len(board) >= 2, "contribution board has suppliers")
    check(board[0]["points"] >= board[1]["points"], "board sorted by points")
    # Leader deposited 40 logs (40pts) + 5 bars (15pts) = 55; helper 10 ore (20) + 15 coal (15) = 35.
    lead_entry = next(e for e in board if e["player_id"] == lead)
    helper_entry = next(e for e in board if e["player_id"] == helper)
    check(lead_entry["points"] == 55, f"leader points {lead_entry['points']}")
    check(helper_entry["points"] == 35, f"helper points {helper_entry['points']}")

    lines = " ".join(crown_siege.store_lines(conn, lead)).lower()
    check("timber 40" in lines and "top suppliers" in lines, "store lines show stock and board")
    # No personal withdraw path — only allocation.
    check(not hasattr(crown_siege, "withdraw_store"), "store cannot be withdrawn personally")


def test_weapons_damage_and_breaches():
    db = make_db()
    conn = db.conn
    lead, lead_cid = _pad_guild(db, "siege", "SiegeLead", "Engineers", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, lead, "attack", now=T0)
    crown_siege.confirm(conn, lead, now=T0 + 1)
    war = crown_siege.current_war(conn)

    # Seed storehouse with enough timber/bars/ore to ram the gate down and breach a wall.
    # Bias allocation toward rams/ladders so craft stays inside the leader's budget.
    _fund_side(
        conn, lead,
        {"timber": 2000, "bars": 400, "ore": 400},
        alloc={"rams": 50, "ladders": 35, "barricades": 5, "reserve": 10},
        now=T0 + 2,
    )

    ok, msg = crown_siege.craft_weapon(conn, lead, "ram", 1, now=T0 + 3)
    check(ok, f"craft ram ({msg})")
    ok, msg = crown_siege.craft_weapon(conn, lead, "ladder", 2, now=T0 + 4)
    check(ok, f"craft ladders ({msg})")
    stock = crown_siege.weapon_stock(conn, war["id"], lead_cid)
    check(stock["ram"] == 1 and stock["ladder"] == 2, f"weapon stock {stock}")

    gate = crown_siege.get_structure(conn, "outer_gate")
    import castle_realm
    sample_breach = crown_siege.structure_breach_tiles("west_wall")[0]
    check(not castle_realm.walkable("realm", sample_breach[0], sample_breach[1]),
          "wall tile blocked before destruction")

    # Ram the gate until destroyed.
    # fire_weapon public contract: (ok, message, sync_meta_or_None) — same as server.py /siege fire.
    hits = 0
    last_meta = None
    while crown_siege.get_structure(conn, "outer_gate")["state"] != "destroyed":
        if crown_siege.weapon_stock(conn, war["id"], lead_cid)["ram"] < 1:
            ok, _ = crown_siege.craft_weapon(conn, lead, "ram", 1, now=T0 + 10 + hits)
            check(ok, "craft more rams")
        ok, msg, meta = crown_siege.fire_weapon(conn, lead, "ram", "outer_gate", now=T0 + 20 + hits)
        check(ok, f"fire ram ({msg})")
        check(meta and meta.get("sync") is True and meta.get("structure"), f"fire ram meta ({meta})")
        last_meta = meta
        hits += 1
        check(hits < 30, "ram should destroy gate eventually")
    check(crown_siege.get_structure(conn, "outer_gate")["state"] == "destroyed", "gate destroyed")
    check(last_meta and last_meta.get("breached") is True, "destroying hit reports breached")
    check(last_meta["structure"]["state"] == "destroyed", "meta structure matches destroyed gate")
    gate_breach = crown_siege.structure_breach_tiles("outer_gate")
    check(len(gate_breach) > 0, "gate breach tiles defined")
    check(any(crown_siege.is_breach_tile(x, y, conn) for x, y in gate_breach),
          "destroyed gate opens breach tiles")

    ok, msg, meta = crown_siege.fire_weapon(conn, lead, "ladder", "west_wall", now=T0 + 100)
    check(ok, f"ladder hits west wall ({msg})")
    check(meta and meta.get("structure") and meta["structure"]["id"] == "west_wall",
          f"ladder meta targets west_wall ({meta})")
    # Burn the west wall down.
    ladder_hits = 0
    while crown_siege.get_structure(conn, "west_wall")["state"] != "destroyed":
        if crown_siege.weapon_stock(conn, war["id"], lead_cid)["ladder"] < 1:
            check(crown_siege.craft_weapon(conn, lead, "ladder", 1)[0], "craft ladder")
        check(crown_siege.fire_weapon(conn, lead, "ladder", "west_wall")[0], "fire ladder")
        ladder_hits += 1
        check(ladder_hits < 40, "ladder should destroy wall eventually")
    check(castle_realm.walkable("realm", sample_breach[0], sample_breach[1]),
          "destroyed wall opens walk path")
    # Wrong target rejected.
    ok, msg, meta = crown_siege.fire_weapon(conn, lead, "ram", "west_wall")
    check(not ok and "can hit" in msg.lower(), f"ram cannot hit walls ({msg})")
    check(meta is None, f"rejected fire has no sync meta ({meta})")


def _confirm_both_sides(db):
    atk, _ = _pad_guild(db, "cap_a", "CapAtk", "Assault Guild", crown_siege.HUMAN_MIN)
    dfn, _ = _pad_guild(db, "cap_d", "CapDfn", "Hold Guild", crown_siege.HUMAN_MIN)
    crown_siege.register(db.conn, atk, "attack", now=T0)
    crown_siege.confirm(db.conn, atk, now=T0 + 1)
    crown_siege.register(db.conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(db.conn, dfn, now=T0 + 3)
    return atk, dfn


def _fund_side(conn, player_id, amounts, alloc=None, now=None):
    """Deposit war materials (and optionally set allocation) for a lead guild."""
    now = T0 if now is None else float(now)
    war = crown_siege.current_war(conn)
    clan_id = crown_siege._clan_of(conn, player_id)
    for res, qty in amounts.items():
        crown_siege.credit_deposit(
            conn, war["id"], clan_id, player_id, res, int(qty), int(qty), now=now,
        )
    if alloc:
        ok, msg = crown_siege.set_allocation(conn, player_id, alloc, now=now)
        check(ok, f"set alloc for funding ({msg})")
    return clan_id


def _push_point(conn, player_id, point_id, now_start):
    """Drive one capture point to attack ownership with solo presence."""
    spec = crown_siege.CAPTURE_POINTS[point_id]
    x0, y0, x1, y1 = spec["rect"]
    xy = ((x0 + x1) // 2, (y0 + y1) // 2)
    presence = [(player_id, spec["plane"], xy[0], xy[1])]
    # Watchtower can double realm need — read live need from capture_state.
    need = int(crown_siege._capture_need(conn, spec))
    notices = []
    for i in range(need + 5):
        batch = crown_siege.tick_captures(conn, presence, now=now_start + i)
        notices.extend(batch)
        points = {p["id"]: p for p in crown_siege.capture_state(conn)}
        if points[point_id]["owner"] == "attack":
            return notices, now_start + i + 1
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points[point_id]["owner"] == "attack", f"{point_id} flips to attack ({points[point_id]})")
    return notices, now_start + need + 5


def test_capture_throne_and_last_stand():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    ok, msg = crown_siege.begin_assault(conn, atk, now=T0 + 10)
    check(ok and crown_siege.current_war(conn)["status"] == "active", f"assault begins ({msg})")
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["throne"]["owner"] == "defend", "defenders start with throne")
    check(points["outer_yard"]["unlocked_for_attack"], "outer yard unlocked first")
    check(not points["throne"]["unlocked_for_attack"], "throne locked until prior stages fall")

    # Attackers must take stages in order; gatehouse needs a breach, throne needs the keep down.
    t = T0 + 20
    notices, t = _push_point(conn, atk, "outer_yard", t)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(not points["gatehouse"]["unlocked_for_attack"], "gatehouse locked until walls breach")
    crown_siege.apply_damage(conn, "outer_gate", 99999)
    check(crown_siege.walls_breached(conn), "gate rubble counts as breach")
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["gatehouse"]["unlocked_for_attack"], "gatehouse unlocks after breach")
    notices, t = _push_point(conn, atk, "gatehouse", t)
    notices, t = _push_point(conn, atk, "courtyard", t)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(not points["throne"]["unlocked_for_attack"], "throne locked until keep falls")
    crown_siege.apply_damage(conn, "royal_keep", 99999)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["throne"]["unlocked_for_attack"], "throne unlocks after keep destroyed")

    notices, t = _push_point(conn, atk, "throne", t)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["throne"]["owner"] == "attack", f"throne flips to attack ({points['throne']})")
    check(any("throne" in n.lower() for n in notices), f"flip notice ({notices})")

    # Hold for THRONE_HOLD_SECONDS → war resolves and crowns attacker.
    hold_start = points["throne"]["hold_started_at"]
    check(hold_start is not None, "hold timer started")
    throne_xy = (26, 17)
    presence = [(atk, "king_f1", throne_xy[0], throne_xy[1])]
    notices = crown_siege.tick_captures(
        conn, presence, now=hold_start + crown_siege.THRONE_HOLD_SECONDS + 1,
    )
    war = crown_siege.current_war(conn)
    check(war is None, "war completed and no longer current")
    done = conn.execute(
        "SELECT status, note FROM crown_wars ORDER BY id DESC LIMIT 1"
    ).fetchone()
    check(done[0] == "completed" and "crowned" in done[1].lower(), f"war resolved ({done})")
    st = throne.state(conn)
    check(st["monarch_kind"] == "player" and int(st["monarch_player_id"]) == int(atk),
          "attacker leader crowned")
    check(st["path"] == "siege", "crown path is siege")
    heraldry = crown_siege.castle_heraldry(conn)
    check(heraldry and int(heraldry["player_id"]) == int(atk), "siege heraldry recorded")
    check(crown_siege.siege_regal_unlocked(conn, atk), "siege unlocks Regal outfit")
    council = " ".join(crown_siege.council_lines(conn, atk)).lower()
    check("council" in council and "public works" in council, f"council lines ({council})")

    # Fresh war for Last Stand.
    db2 = make_db()
    conn = db2.conn
    atk, dfn = _confirm_both_sides(db2)
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    ok, msg, herald = crown_siege.on_siege_death(
        conn, atk, {"id": "castle_realm", "plane": "realm"}, now=T0 + 11,
    )
    check(ok and "out of this siege" in msg.lower(), f"last stand eliminates ({msg})")
    check(herald and "fallen" in herald.lower() and "capatk" in herald.lower(),
          f"herald names the fallen ({herald})")
    check(crown_siege.is_eliminated(conn, atk), "attacker marked eliminated")
    ok_enter, block = crown_siege.can_enter_siege(conn, atk)
    check(not ok_enter and "eliminated" in block.lower(), f"cannot re-enter ({block})")
    # Eliminated fighters do not contest captures.
    presence = [(atk, "king_f1", 26, 17), (dfn, "king_f1", 26, 17)]
    crown_siege.tick_captures(conn, presence, now=T0 + 12)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    # Only defender counts → throne stays defend with progress toward defend (already owner).
    check(points["throne"]["owner"] == "defend", "elim player ignored for capture")
    # Non-fighter death in realm is a no-op for Last Stand.
    outsider, _ = _pad_guild(db2, "watch", "Watcher", "Spectators", 3)
    ok, msg, herald = crown_siege.on_siege_death(conn, outsider, {"id": "castle_realm"}, now=T0 + 13)
    check(not ok and herald is None, "spectators are not eliminated")


def test_heraldry_and_council_commands():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    crown_siege.begin_assault(conn, atk, now=T0 + 5)
    # Force resolve as attack win.
    ok, msg = crown_siege.resolve_war(conn, winner="attack", now=T0 + 6)
    check(ok and "heraldry" in msg.lower(), f"resolve grants heraldry ({msg})")
    ok, lines = crown_siege.handle_command(conn, atk, "/siege heraldry")
    check(ok and "heraldry" in lines[0].lower(), f"heraldry command ({lines})")
    ok, lines = crown_siege.handle_command(conn, atk, "/siege council")
    check(ok and any("council" in ln.lower() for ln in lines), f"council command ({lines})")
    # Appoint via existing ruling tables (no coin mint from siege module).
    other = conn.execute("SELECT id FROM players WHERE username = 'cap_d'").fetchone()[0]
    conn.execute("UPDATE players SET noble_rank = 2 WHERE id = ?", (other,))
    conn.commit()
    ok, msg = ruling.appoint(conn, atk, "Chancellor", other)
    check(ok, f"monarch appoints chancellor ({msg})")
    lines = crown_siege.council_lines(conn, atk)
    check(any("Chancellor" in ln for ln in lines), f"council lists chancellor ({lines})")


def test_roster_caps():
    check(crown_siege.roster_caps_ok(20, 0)[0], "20 humans ok")
    check(not crown_siege.roster_caps_ok(19, 0)[0], "under human min fails")
    check(not crown_siege.roster_caps_ok(20, 14)[0], "over 40% mercs fails")
    # 20 humans → max mercs = 13 (13/33 ≈ 39.4%)
    check(crown_siege.roster_caps_ok(20, 13)[0], "40% merc ceiling ok")
    check(not crown_siege.roster_caps_ok(90, 20)[0], "side cap 100 enforced")
    check(crown_siege.roster_caps_ok(60, 40)[0], "100 with 40% mercs ok")


def test_live_interest_and_presence():
    me = {"id": 1, "x": 150, "y": 60}
    near = {"id": 2, "x": 155, "y": 62}
    far = {"id": 3, "x": 200, "y": 100}
    kept = crown_siege.filter_by_interest(me, [me, near, far], radius=24)
    ids = {p["id"] for p in kept}
    check(ids == {1, 2}, f"interest keeps nearby only ({ids})")
    check(crown_siege.in_interest(0, 0, 24, 0), "edge of radius included")
    check(not crown_siege.in_interest(0, 0, 25, 0), "beyond radius excluded")

    class Fake:
        def __init__(self, pid, plane, x, y):
            self.player_id = pid
            self.dungeon = {"id": "castle_realm", "plane": plane}
            self.x, self.y = x, y

    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    crown_siege.begin_assault(conn, atk, now=T0 + 1)
    sessions = [
        Fake(atk, "king_f1", 26, 17),
        Fake(dfn, "king_f1", 26, 17),
        Fake(999, "realm", 150, 70),  # non-fighter still listed in presence; capture ignores
    ]
    presence = crown_siege.live_presence(sessions, conn)
    check(len(presence) == 3, f"presence collects realm sessions ({presence})")
    notices = crown_siege.tick_live(conn, sessions, now=T0 + 2)
    # Take prior stages; breach walls and keep so the throne unlocks.
    t = T0 + 10
    _notices, t = _push_point(conn, atk, "outer_yard", t)
    crown_siege.apply_damage(conn, "outer_gate", 99999)
    _notices, t = _push_point(conn, atk, "gatehouse", t)
    _notices, t = _push_point(conn, atk, "courtyard", t)
    crown_siege.apply_damage(conn, "royal_keep", 99999)
    sessions = [Fake(atk, "king_f1", 26, 17)]
    for i in range(30):
        crown_siege.tick_live(conn, sessions, now=t + 10 + i)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["throne"]["progress"] > 0 or points["throne"]["owner"] == "attack",
          f"live tick advances throne ({points['throne']})")
    snap = crown_siege.hud_snapshot(conn, atk)
    check(snap["war"] and snap["war"]["status"] == "active", "hud snapshot has active war")
    check(snap["side"] == "attack", "hud knows attacker side")

    # Client war prompt helpers
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((8, 8))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import castle_realm_renderer as cr

    class Stub:
        dungeon = {
            "id": "castle_realm",
            "plane": "realm",
            "crown_siege_hud": snap,
        }
        font_small = pygame.font.Font(None, 16)
        screen = pygame.display.get_surface()

    check(cr._war_hud(Stub()).get("war"), "client reads war hud")


def test_repair_and_structure_sync():
    db = make_db()
    conn = db.conn
    atk, atk_cid = _pad_guild(db, "rep_a", "RepAtk", "Breachers", crown_siege.HUMAN_MIN)
    dfn, dfn_cid = _pad_guild(db, "rep_d", "RepDfn", "Masons", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, atk, "attack", now=T0)
    crown_siege.confirm(conn, atk, now=T0 + 1)
    crown_siege.register(conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(conn, dfn, now=T0 + 3)
    war = crown_siege.current_war(conn)
    _fund_side(
        conn, dfn,
        {"timber": 800, "stone": 800, "bars": 200},
        alloc={"rams": 10, "ladders": 10, "barricades": 20, "reserve": 60},
        now=T0 + 4,
    )
    _fund_side(
        conn, atk,
        {"timber": 1200, "bars": 200},
        alloc={"rams": 10, "ladders": 70, "barricades": 10, "reserve": 10},
        now=T0 + 5,
    )

    # Attacker smashes the west wall to rubble.
    ok, msg = crown_siege.craft_weapon(conn, atk, "ladder", 20, now=T0 + 6)
    check(ok, f"craft ladder stock ({msg})")
    smash = 0
    while crown_siege.get_structure(conn, "west_wall")["state"] != "destroyed":
        ok, _msg, _m = crown_siege.fire_weapon(conn, atk, "ladder", "west_wall", now=T0 + 7)
        if not ok:
            ok2, msg2 = crown_siege.craft_weapon(conn, atk, "ladder", 5, now=T0 + 7)
            check(ok2, f"craft more ladders ({msg2})")
        smash += 1
        check(smash < 40, "wall smash should finish")
    check(crown_siege.get_structure(conn, "west_wall")["state"] == "destroyed", "wall destroyed")
    sync = crown_siege.structure_sync(conn)
    check(sync["structures"]["west_wall"]["state"] == "destroyed", "sync reports destroyed")
    check(len(sync["breaches"]) > 0, "sync lists breach tiles")

    # Attacker cannot repair.
    ok, msg, _ = crown_siege.repair_structure(conn, atk, "west_wall", 1, now=T0 + 8)
    check(not ok and "defend" in msg.lower(), f"attacker cannot repair ({msg})")
    # (message: "Only defenders can repair castle structures.")

    # Defender repairs enough batches to leave destroyed.
    batches = 0
    while crown_siege.get_structure(conn, "west_wall")["state"] == "destroyed":
        ok, msg, meta = crown_siege.repair_structure(conn, dfn, "west_wall", 2, now=T0 + 9 + batches)
        check(ok, f"defender repair ({msg})")
        batches += 1
        check(batches < 30, "repair should leave destroyed eventually")
    wall = crown_siege.get_structure(conn, "west_wall")
    check(wall["state"] != "destroyed" and wall["hp"] > 0, f"wall restored ({wall})")
    sync2 = crown_siege.structure_sync(conn)
    # West-wall-only breaches should be gone (gate may still be intact → fewer/no breaches).
    west_tiles = set(crown_siege.structure_breach_tiles("west_wall"))
    open_breaches = {tuple(t) for t in sync2["breaches"]}
    check(not (west_tiles & open_breaches), "repaired wall no longer opens its breach tiles")


def test_challenge_gated_during_war():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    war = crown_siege.current_war(conn)
    check(war and war["status"] == "scheduled", "war open for gate test")

    class Sess:
        player_id = atk
        char_name = "CapAtk"
        bank_coins = 0

    # Solo Crown Challenge is retired in favour of the War for the Crown.
    ok, msg = throne.schedule_crown(Sess(), conn, 12, now=T0 + 10)
    check(not ok and "retired" in str(msg).lower(), f"crown challenge retired ({msg})")
    check("war for the crown" in str(msg).lower(), f"points to war ({msg})")

    crown_siege.begin_assault(conn, atk, now=T0 + 11)
    crown_siege.resolve_war(conn, winner="defend", now=T0 + 12)
    check(crown_siege.current_war(conn) is None, "war closed")
    ok2, msg2 = throne.schedule_crown(Sess(), conn, 12, now=T0 + 13)
    check(not ok2 and "retired" in str(msg2).lower(), f"still retired after war ({msg2})")


def test_auto_assault_after_confirm_delay():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    war = crown_siege.current_war(conn)
    check(war["status"] == "scheduled", "both confirmed → scheduled")
    scheduled_at = float(war["scheduled_at"])
    # Before the delay: still scheduled.
    notices = crown_siege.tick_wars(conn, now=scheduled_at + crown_siege.ASSAULT_DELAY - 10)
    check(crown_siege.current_war(conn)["status"] == "scheduled", "no auto-start early")
    check(not any("begun" in n.lower() for n in notices), f"no begun notice early ({notices})")
    # After the delay: assault begins automatically.
    notices = crown_siege.tick_wars(conn, now=scheduled_at + crown_siege.ASSAULT_DELAY + 1)
    war = crown_siege.current_war(conn)
    check(war and war["status"] == "active", f"auto-assault after delay ({war})")
    check(any("begun" in n.lower() for n in notices), f"begun notice ({notices})")
    # Leader may still begin early on a fresh war.
    db2 = make_db()
    atk2, _dfn2 = _confirm_both_sides(db2)
    ok, msg = crown_siege.begin_assault(db2.conn, atk2, now=T0 + 30)
    check(ok and "begun" in msg.lower(), f"leader can begin before delay ({msg})")
    check(crown_siege.current_war(db2.conn)["status"] == "active", "early begin activates")


def test_siege_kill_tally_and_board():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    ok, msg = crown_siege.eliminate(conn, atk, now=T0 + 11, killer_id=dfn)
    check(ok and "out of this siege" in msg.lower(), f"elim with killer ({msg})")
    board = crown_siege.contrib_board(conn)
    by_id = {e["player_id"]: e for e in board}
    check(dfn in by_id and by_id[dfn]["kills"] == 1, f"defender credited one kill ({board})")
    # Friendly fire / same side does not credit.
    outsider, _ = _pad_guild(db, "cap_a2", "CapAtk2", "Assault Two", crown_siege.HUMAN_MIN)
    # Ally of attack dying to attack leader — no credit.
    # Register outsider on attack as queued member of new guild; use a pad member as victim.
    atk_member = conn.execute(
        "SELECT id FROM players WHERE username LIKE 'cap_a_m%' LIMIT 1"
    ).fetchone()
    check(atk_member, "attacker has a member")
    victim = int(atk_member[0])
    # Member must be on the war side via their guild (already joined attack lead guild).
    ok, msg = crown_siege.eliminate(conn, victim, now=T0 + 12, killer_id=atk)
    check(ok, f"same-side elim still removes ({msg})")
    board2 = {e["player_id"]: e for e in crown_siege.contrib_board(conn)}
    check(board2.get(atk, {}).get("kills", 0) == 0, f"friendly fire not credited ({board2})")
    lines = " ".join(crown_siege.board_lines(conn, dfn, now=T0 + 13)).lower()
    check("eliminated this siege" in lines, f"board mentions elims ({lines})")
    check("1k" in lines or "kills" in lines or "fighters" in lines, f"board shows kills ({lines})")
    snap = crown_siege.hud_snapshot(conn, dfn)
    check(snap.get("board"), "hud snapshot carries board lines")

    # Client war chip opens a board panel.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((640, 480))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import castle_realm_renderer as cr

    class Stub:
        dungeon = {
            "id": "castle_realm",
            "plane": "realm",
            "crown_siege_hud": snap,
        }
        font_small = pygame.font.Font(None, 18)
        font_tiny = pygame.font.Font(None, 14)
        screen = pygame.display.get_surface()
        show_war_board = False
        war_chip_rect = None
        war_board_rect = None
        war_board_close_rect = None

    stub = Stub()
    cr.draw_war_prompt(stub)
    check(stub.war_chip_rect is not None, "war chip has a hit rect")
    mx, my = stub.war_chip_rect.center
    check(cr.war_board_click(stub, mx, my), "chip click opens board")
    check(stub.show_war_board, "show_war_board set")
    cr.draw_war_prompt(stub)
    check(stub.war_board_rect is not None, "board panel drawn")
    check(cr.war_board_click(stub, stub.war_board_close_rect.centerx,
                             stub.war_board_close_rect.centery), "close consumes click")
    check(not stub.show_war_board, "board closed")


def test_barricades_stages_depot_reset_monthly():
    db = make_db()
    conn = db.conn
    atk, atk_cid = _pad_guild(db, "bar_a", "BarAtk", "Ram Guild", crown_siege.HUMAN_MIN)
    dfn, dfn_cid = _pad_guild(db, "bar_d", "BarDfn", "Wall Guild", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, atk, "attack", now=T0)
    crown_siege.confirm(conn, atk, now=T0 + 1)
    crown_siege.register(conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(conn, dfn, now=T0 + 3)
    war = crown_siege.current_war(conn)
    _fund_side(
        conn, dfn,
        {"timber": 500, "stone": 500, "bars": 100, "ore": 50},
        alloc={"rams": 10, "ladders": 10, "barricades": 40, "reserve": 40},
        now=T0 + 4,
    )
    _fund_side(
        conn, atk,
        {"timber": 500, "stone": 500, "bars": 100, "ore": 50},
        now=T0 + 5,
    )

    # Damage the gate before the assault — assault must reset it.
    crown_siege.apply_damage(conn, "outer_gate", 5000)
    check(crown_siege.get_structure(conn, "outer_gate")["state"] == "damaged", "pre-assault damage")
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    gate = crown_siege.get_structure(conn, "outer_gate")
    check(gate["hp"] == gate["max_hp"] and gate["state"] == "intact", "assault resets structures")

    # Defenders craft and deploy a barricade on the outer yard.
    ok, msg = crown_siege.craft_weapon(conn, dfn, "barricade", 2, now=T0 + 11)
    check(ok, f"craft barricade ({msg})")
    ok, msg = crown_siege.deploy_barricade(conn, dfn, "outer_yard", now=T0 + 12)
    check(ok and "barricade" in msg.lower(), f"deploy barricade ({msg})")
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["outer_yard"]["barricades"] == crown_siege.BARRICADE_DEPLOY_HP,
          f"barricade HP on outer yard ({points['outer_yard']})")

    # Attackers chip barricades before capture progress moves.
    spec = crown_siege.CAPTURE_POINTS["outer_yard"]
    x0, y0, x1, y1 = spec["rect"]
    presence = [(atk, spec["plane"], (x0 + x1) // 2, (y0 + y1) // 2)]
    for i in range(crown_siege.BARRICADE_DEPLOY_HP):
        crown_siege.tick_captures(conn, presence, now=T0 + 20 + i)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["outer_yard"]["barricades"] == 0, "barricades cleared by attackers")
    check(points["outer_yard"]["progress"] == 0, "no capture progress until barricades fall")
    need = int(points["outer_yard"]["need"])  # watchtower may double this
    for i in range(need):
        crown_siege.tick_captures(conn, presence, now=T0 + 100 + i)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["outer_yard"]["owner"] == "attack", "outer yard falls after barricades")

    # Gatehouse still needs a wall/gate breach after the outer yard falls.
    check(not points["gatehouse"]["unlocked_for_attack"], "gatehouse locked without breach")
    crown_siege.apply_damage(conn, "west_wall", 99999)
    points = {p["id"]: p for p in crown_siege.capture_state(conn)}
    check(points["gatehouse"]["unlocked_for_attack"], "gatehouse unlocks after wall breach")

    # Destroyed supply depot doubles repair cost.
    dead = crown_siege.apply_damage(conn, "supply_depot", 99999)
    check(dead and dead["state"] == "destroyed", "depot destroyed")
    crown_siege.apply_damage(conn, "west_wall", 1000)
    # One batch normally costs 8 timber / 12 stone / 2 bars; double = 16/24/4.
    stock_before = crown_siege.store_stock(conn, war["id"], dfn_cid)
    ok, msg, _ = crown_siege.repair_structure(conn, dfn, "west_wall", 1, now=T0 + 210)
    check(ok, f"repair with double cost ({msg})")
    stock_after = crown_siege.store_stock(conn, war["id"], dfn_cid)
    check(stock_before["timber"] - stock_after["timber"] == 16, "depot doubles timber cost")
    check(stock_before["stone"] - stock_after["stone"] == 24, "depot doubles stone cost")

    # Monthly auto-open after cooldown.
    crown_siege.resolve_war(conn, winner="defend", now=T0 + 300)
    check(crown_siege.current_war(conn) is None, "war resolved")
    notices = crown_siege.tick_wars(conn, now=T0 + 300 + crown_siege.SIEGE_COOLDOWN - 10)
    check(crown_siege.current_war(conn) is None, "still closed inside cooldown")
    notices = crown_siege.tick_wars(conn, now=T0 + 300 + crown_siege.SIEGE_COOLDOWN + 1)
    war2 = crown_siege.current_war(conn)
    check(war2 and war2["status"] == "registration", f"monthly auto-open ({war2})")
    check(any("registration is open" in n.lower() for n in notices), f"open notice ({notices})")


def test_structure_effects_and_capture_markers():
    db = make_db()
    conn = db.conn
    atk, atk_cid = _pad_guild(db, "fx_a", "FxAtk", "Tower Breakers", crown_siege.HUMAN_MIN)
    dfn, dfn_cid = _pad_guild(db, "fx_d", "FxDfn", "Tower Hold", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, atk, "attack", now=T0)
    crown_siege.confirm(conn, atk, now=T0 + 1)
    crown_siege.register(conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(conn, dfn, now=T0 + 3)
    war = crown_siege.current_war(conn)
    _fund_side(
        conn, dfn,
        {"timber": 400, "stone": 200, "bars": 80, "ore": 40},
        alloc={"rams": 10, "ladders": 10, "barricades": 60, "reserve": 20},
        now=T0 + 4,
    )
    crown_siege.begin_assault(conn, atk, now=T0 + 5)

    check(crown_siege.effective_interest_radius(conn) == crown_siege.INTEREST_RADIUS,
          "intact watchtower keeps tight interest")
    crown_siege.apply_damage(conn, "watchtower", 99999)
    check(crown_siege.effective_interest_radius(conn) == crown_siege.INTEREST_RADIUS_BREACHED,
          "destroyed watchtower opens interest")

    # Armoury doubles defender craft cost.
    crown_siege.apply_damage(conn, "armoury", 99999)
    stock_before = crown_siege.store_stock(conn, war["id"], dfn_cid)
    ok, msg = crown_siege.craft_weapon(conn, dfn, "barricade", 1, now=T0 + 6)
    check(ok and "double" in msg.lower(), f"defender craft pays double ({msg})")
    stock_after = crown_siege.store_stock(conn, war["id"], dfn_cid)
    # Barricade base cost 20 timber + 10 stone; double = 40 / 20.
    check(stock_before["timber"] - stock_after["timber"] == 40, "double timber craft cost")
    check(stock_before["stone"] - stock_after["stone"] == 20, "double stone craft cost")

    pub = crown_siege.war_public(conn)
    check("mercs" in (pub["sides"]["attack"]["lead"] or {}), "public lead exposes mercs")
    snap = crown_siege.hud_snapshot(conn, atk)
    check(snap["watchtower_down"] and snap["armoury_down"], "hud flags structure losses")
    check(snap["interest_radius"] == crown_siege.INTEREST_RADIUS_BREACHED, "hud radius matches")

    # Client capture markers helper runs without error.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((320, 240))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import castle_realm_renderer as cr

    class Stub:
        dungeon = {
            "id": "castle_realm",
            "plane": "realm",
            "crown_siege_hud": snap,
        }
        font_small = pygame.font.Font(None, 16)
        font_tiny = pygame.font.Font(None, 14)
        screen = pygame.display.get_surface()
        show_war_board = False

        def camera_origin(self):
            return (130, 50)

        def player_xy(self):
            return (150, 70)

    stub = Stub()
    cr.draw_capture_markers(stub)
    cr.draw_war_prompt(stub)
    check(stub.war_chip_rect is not None, "war chip still draws with structure flags")


def test_engine_contrib_tower_need_and_scars():
    db = make_db()
    conn = db.conn
    atk, atk_cid = _pad_guild(db, "ec_a", "EcAtk", "Engine Guild", crown_siege.HUMAN_MIN)
    dfn, dfn_cid = _pad_guild(db, "ec_d", "EcDfn", "Repair Guild", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, atk, "attack", now=T0)
    crown_siege.confirm(conn, atk, now=T0 + 1)
    crown_siege.register(conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(conn, dfn, now=T0 + 3)
    war = crown_siege.current_war(conn)
    _fund_side(
        conn, atk,
        {"timber": 200, "stone": 100, "bars": 40, "ore": 20},
        alloc={"rams": 50, "ladders": 20, "barricades": 10, "reserve": 20},
        now=T0 + 4,
    )
    _fund_side(
        conn, dfn,
        {"timber": 200, "stone": 100, "bars": 40, "ore": 20},
        alloc={"rams": 10, "ladders": 10, "barricades": 20, "reserve": 60},
        now=T0 + 5,
    )
    crown_siege.begin_assault(conn, atk, now=T0 + 6)

    # Realm capture need doubles while the watchtower stands.
    base = crown_siege.CAPTURE_POINTS["outer_yard"]["capture_need"]
    check(crown_siege._capture_need(conn, crown_siege.CAPTURE_POINTS["outer_yard"]) == base * 2,
          "watchtower doubles outer yard need")
    crown_siege.apply_damage(conn, "watchtower", 99999)
    check(crown_siege._capture_need(conn, crown_siege.CAPTURE_POINTS["outer_yard"]) == base,
          "need returns to base after tower falls")

    # Firing a ram awards contribution.
    crown_siege.craft_weapon(conn, atk, "ram", 1, now=T0 + 7)
    before = {e["player_id"]: e for e in crown_siege.contrib_board(conn)}
    pts0 = before.get(atk, {}).get("points", 0)
    ok, msg, _ = crown_siege.fire_weapon(conn, atk, "ram", "outer_gate", now=T0 + 8)
    check(ok and "contrib" in msg.lower(), f"fire awards contrib ({msg})")
    after = {e["player_id"]: e for e in crown_siege.contrib_board(conn)}
    check(after[atk]["points"] > pts0, f"attacker points rose ({after[atk]})")

    # Defender repair awards contribution.
    crown_siege.apply_damage(conn, "west_wall", 600)
    ok, msg, _ = crown_siege.repair_structure(conn, dfn, "west_wall", 1, now=T0 + 9)
    check(ok and "contrib" in msg.lower(), f"repair awards contrib ({msg})")
    dboard = {e["player_id"]: e for e in crown_siege.contrib_board(conn)}
    check(dboard[dfn]["points"] > 0, "defender has repair points")

    ok, msg = crown_siege.resolve_war(conn, winner="attack", now=T0 + 10)
    check(ok and "crownfall" in msg.lower() and "hail" in msg.lower(), f"coronation line ({msg})")

    # Client structure scar helper queues overlays when damaged.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((64, 64))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import castle_realm_renderer as cr

    class Stub:
        dungeon = {
            "id": "castle_realm",
            "plane": "realm",
            "crown_siege": {
                "watchtower": {"state": "destroyed", "hp": 0, "max_hp": 6000, "anchor": [120, 20]},
                "armoury": {"state": "damaged", "hp": 2000, "max_hp": 5000, "anchor": [160, 40]},
                "supply_depot": {"state": "intact", "hp": 5000, "max_hp": 5000, "anchor": [140, 55]},
            },
        }
        screen = pygame.display.get_surface()

    draw_list = []
    cr._queue_structure_scars(Stub(), draw_list, 100, 0, 40)
    check(len(draw_list) == 2, f"scars for destroyed tower + damaged armoury ({len(draw_list)})")


def test_assault_clock_scout_and_capture_contrib():
    db = make_db()
    conn = db.conn
    atk, _ = _pad_guild(db, "cl_a", "ClAtk", "Clock Attack", crown_siege.HUMAN_MIN)
    dfn, _ = _pad_guild(db, "cl_d", "ClDfn", "Clock Defend", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, atk, "attack", now=T0)
    crown_siege.confirm(conn, atk, now=T0 + 1)
    crown_siege.register(conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(conn, dfn, now=T0 + 3)
    ok, msg = crown_siege.begin_assault(conn, atk, now=T0 + 10)
    check(ok and "hour" in msg.lower(), f"assault names the clock ({msg})")
    war = crown_siege.current_war(conn)
    check(war["started_at"] == T0 + 10, f"started_at recorded ({war})")
    left = crown_siege.assault_time_left(war, now=T0 + 10)
    check(left == crown_siege.ASSAULT_SECONDS, f"full assault window ({left})")

    # Scout report lists every structure.
    ok, lines = crown_siege.handle_command(conn, atk, "/siege scout")
    check(ok and any("outer gate" in ln.lower() for ln in lines), f"scout lists gate ({lines})")
    check(any("no wall/gate breach" in ln.lower() for ln in lines), f"scout notes no breach ({lines})")

    # Capture flip awards contribution to fighters on the point.
    crown_siege.apply_damage(conn, "watchtower", 99999)  # avoid doubled need
    notices, t = _push_point(conn, atk, "outer_yard", T0 + 20)
    board = {e["player_id"]: e for e in crown_siege.contrib_board(conn)}
    check(atk in board and board[atk]["points"] >= crown_siege.CAPTURE_CONTRIB,
          f"capture flip credits attacker ({board})")
    check(any("outer yard" in n.lower() for n in notices), f"flip notice ({notices})")

    # Assault clock expires → defenders win.
    db2 = make_db()
    atk2, dfn2 = _confirm_both_sides(db2)
    crown_siege.begin_assault(db2.conn, atk2, now=T0 + 50)
    war2 = crown_siege.current_war(db2.conn)
    notices = crown_siege.tick_wars(
        db2.conn, now=float(war2["started_at"]) + crown_siege.ASSAULT_SECONDS + 1,
    )
    check(crown_siege.current_war(db2.conn) is None, "war ends on assault timeout")
    check(any("expired" in n.lower() and "hold" in n.lower() for n in notices),
          f"timeout notice ({notices})")
    st = throne.state(db2.conn)
    # Defenders held — monarch should still be NPC (or prior) unless attack won.
    check(st["monarch_kind"] == "npc" or st.get("path") != "siege",
          f"timeout does not crown attacker ({st})")


def test_chronicle_roster_lock_postpone_and_scar_click():
    # War chronicle appears in the Great Hall after a completed assault.
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    ok, note = crown_siege.resolve_war(conn, winner="defend", now=T0 + 20)
    check(ok and "held the walls" in note.lower(), f"defend resolve ({note})")
    lines = crown_siege.hall_lines(conn)
    blob = " ".join(lines).lower()
    check("chronicles of the war" in blob, f"hall names war chronicle ({lines})")
    check("held the walls" in blob, f"hall records defend win ({lines})")
    notes = crown_siege.recent_war_notes(conn)
    check(len(notes) == 1 and "held" in notes[0]["note"].lower(), f"recent notes ({notes})")

    # Roster lock: no ally invites / recruit hires while assault is active.
    db2 = make_db()
    atk2, dfn2 = _confirm_both_sides(db2)
    crown_siege.begin_assault(db2.conn, atk2, now=T0 + 30)
    check(crown_siege.roster_locked(db2.conn), "roster locked during active assault")
    ally_lead, _ = _pad_guild(db2, "lock_ally", "LockAlly", "Late Allies", 3)
    ok, msg = crown_siege.invite_ally(db2.conn, atk2, "Late Allies", now=T0 + 31)
    check(not ok and "locked" in msg.lower(), f"ally invite blocked ({msg})")
    ap.bank_set(db2.conn, atk2, clans.RECRUIT_HIRE_COST + 1000)
    clans.deposit_core(atk2, clans.RECRUIT_HIRE_COST + 500, now=T0 + 32)
    ok, msg = clans.hire_core(atk2, "Guard", now=T0 + 33)
    check(not ok and "locked" in msg.lower(), f"hire blocked during assault ({msg})")

    # Under-strength at assault time → postpone (stay scheduled, bump delay).
    db3 = make_db()
    atk3, dfn3 = _confirm_both_sides(db3)
    war = crown_siege.current_war(db3.conn)
    check(war["status"] == "scheduled", "war scheduled after confirm")
    # Drop attackers below HUMAN_MIN after they already confirmed.
    members = db3.conn.execute(
        "SELECT player_id FROM clan_members WHERE clan_id = ("
        "SELECT clan_id FROM clan_members WHERE player_id = ?) "
        "AND player_id != ?",
        (atk3, atk3),
    ).fetchall()
    drop = max(1, len(members) - (crown_siege.HUMAN_MIN - 5))
    for (pid,) in members[:drop]:
        db3.conn.execute("DELETE FROM clan_members WHERE player_id = ?", (pid,))
    db3.conn.commit()
    humans = crown_siege._alliance_humans(
        db3.conn, war["id"],
        crown_siege._clan_of(db3.conn, atk3), "attack",
    )
    check(humans < crown_siege.HUMAN_MIN, f"attackers under strength ({humans})")
    scheduled_at = float(war["scheduled_at"])
    notices = crown_siege.tick_wars(
        db3.conn, now=scheduled_at + crown_siege.ASSAULT_DELAY + 1,
    )
    war2 = crown_siege.current_war(db3.conn)
    check(war2 and war2["status"] == "scheduled", f"stays scheduled when under strength ({war2})")
    check(any("postponed" in n.lower() for n in notices), f"postpone notice ({notices})")
    check(float(war2["scheduled_at"]) >= scheduled_at + crown_siege.ASSAULT_DELAY,
          "scheduled_at bumped forward on postpone")
    ok, msg = crown_siege.begin_assault(db3.conn, atk3, now=T0 + 100)
    check(not ok and "under strength" in msg.lower(), f"manual begin blocked ({msg})")

    # Scar click examines structure HP from stored rects.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((8, 8))
    sys.path.insert(0, os.path.join(ROOT, "client"))
    sys.path.insert(0, os.path.join(ROOT, "..", "characters"))
    import castle_realm_renderer as cr

    class Stub:
        font_small = pygame.font.Font(None, 16)
        screen = pygame.display.get_surface()
        dungeon = {
            "id": "castle_realm",
            "plane": "realm",
            "crown_siege": {
                "watchtower": {
                    "name": "Watchtower", "state": "destroyed",
                    "hp": 0, "max_hp": 6000, "anchor": [120, 20],
                },
                "armoury": {
                    "name": "Armoury", "state": "damaged",
                    "hp": 2000, "max_hp": 5000, "anchor": [160, 40],
                },
            },
        }

    stub = Stub()
    draw_list = []
    cr._queue_structure_scars(stub, draw_list, 100, 0, 40)
    rects = stub.siege_scar_rects
    check("watchtower" in rects and "armoury" in rects, f"scar rects stored ({rects})")
    tower = rects["watchtower"]
    check(cr.structure_scar_click(stub, tower.centerx, tower.centery), "click scar consumed")
    ex = stub.siege_examine
    check(ex and ex["id"] == "watchtower" and ex["hp"] == 0, f"examine payload ({ex})")
    check("destroyed" in str(ex.get("state")), f"examine state ({ex})")
    cr.draw_siege_examine(stub)  # smoke: no crash


def test_elim_blocks_actions_and_requirements_board():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    # Prep stores visible before assault (and fund defender craft budget).
    _fund_side(
        conn, atk,
        {"timber": 80, "ore": 20, "bars": 10, "stone": 20},
        now=T0 + 4,
    )
    _fund_side(
        conn, dfn,
        {"timber": 100, "stone": 50},
        alloc={"rams": 10, "ladders": 10, "barricades": 60, "reserve": 20},
        now=T0 + 5,
    )
    board = " ".join(crown_siege.board_lines(conn, atk, now=T0 + 6)).lower()
    check("war storehouse" in board, f"board shows store before assault ({board})")
    check("costs:" in board or "battering" in board, f"board shows resource costs ({board})")
    check("roster" in board and "20h" in board, f"board shows roster counts ({board})")
    ok, lines = crown_siege.handle_command(conn, atk, "/siege costs")
    check(ok and any("battering ram" in ln.lower() for ln in lines), f"costs command ({lines})")
    check(any("repair" in ln.lower() for ln in lines), f"costs list repair ({lines})")

    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    ok, msg = crown_siege.eliminate(conn, atk, now=T0 + 11, killer_id=dfn)
    check(ok, f"attacker eliminated ({msg})")
    check(crown_siege.action_blocked(conn, atk), "action_blocked for elim")
    ok, msg = crown_siege.deposit(conn, atk, "logs", 5, now=T0 + 12)
    check(not ok and "eliminated" in msg.lower(), f"elim cannot deposit ({msg})")
    ok, msg = crown_siege.craft_weapon(conn, atk, "ram", 1, now=T0 + 13)
    check(not ok and "eliminated" in msg.lower(), f"elim cannot craft ({msg})")
    ok, msg, _m = crown_siege.fire_weapon(conn, atk, "ram", "outer_gate", now=T0 + 14)
    check(not ok and "eliminated" in msg.lower(), f"elim cannot fire ({msg})")
    ok, msg = crown_siege.set_allocation(
        conn, atk, {"rams": 40, "ladders": 25, "barricades": 20, "reserve": 15}, now=T0 + 15,
    )
    check(not ok and ("eliminated" in msg.lower() or "lock" in msg.lower()),
          f"elim/assault cannot alloc ({msg})")
    # Living defender can still craft from the pre-assault store budget.
    ok, msg = crown_siege.craft_weapon(conn, dfn, "barricade", 1, now=T0 + 17)
    check(ok, f"living defender can craft ({msg})")


def test_war_hire_caps_elim_names_and_herald_costs():
    # 40% merc ceiling applies to hires while registered for war.
    check(crown_siege.war_merc_caps_ok(20, 13)[0], "13/33 ≈ 39% ok")
    check(not crown_siege.war_merc_caps_ok(20, 14)[0], "14 mercs over 40%")
    check(crown_siege.war_merc_caps_ok(15, 5)[0], "under human-min still may hire mercs")
    check(not crown_siege.war_merc_caps_ok(0, 1)[0], "no humans → no war mercs")

    db = make_db()
    conn = db.conn
    atk, atk_cid = _pad_guild(db, "cap_a", "CapAtk", "Assault Guild", crown_siege.HUMAN_MIN)
    dfn, _ = _pad_guild(db, "cap_d", "CapDfn", "Hold Guild", crown_siege.HUMAN_MIN)
    crown_siege.register(conn, atk, "attack", now=T0)
    crown_siege.confirm(conn, atk, now=T0 + 1)
    crown_siege.register(conn, dfn, "defend", now=T0 + 2)
    crown_siege.confirm(conn, dfn, now=T0 + 3)
    # Seed guild bank and fill mercs to the war ceiling (13 of 20 humans).
    ap.bank_set(conn, atk, clans.RECRUIT_HIRE_COST * 20)
    clans.deposit_core(atk, clans.RECRUIT_HIRE_COST * 20, now=T0 + 4)
    # Guild recruit cap may be lower than war merc ceiling — insert rows directly
    # so the alliance merc count hits the war 40% line, then hire_core must refuse.
    for i in range(13):
        conn.execute(
            "INSERT INTO clan_recruits (clan_id, name, role, hired_at, upkeep_paid_through, active) "
            "VALUES (?, ?, 'Guard', ?, ?, 1)",
            (atk_cid, f"WarMerc{i}", T0 + 5, T0 + 5),
        )
    conn.commit()
    mercs = crown_siege._alliance_mercs(conn, crown_siege.current_war(conn)["id"], atk_cid, "attack")
    check(mercs == 13, f"seeded 13 war mercs ({mercs})")
    ok, msg = crown_siege.hire_allowed(conn, atk_cid)
    check(not ok and "40%" in msg, f"hire_allowed blocks past 40% ({msg})")
    ok, msg = clans.hire_core(atk, "Guard", now=T0 + 6)
    check(not ok and ("40%" in msg or "mercenar" in msg.lower()), f"hire_core blocked ({msg})")

    # Eliminated names appear on the board; Herald costs option wired.
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    crown_siege.eliminate(conn, atk, now=T0 + 11, killer_id=dfn)
    board = " ".join(crown_siege.board_lines(conn, dfn, now=T0 + 12)).lower()
    check("fallen:" in board and "capatk" in board, f"board names fallen ({board})")
    check("siege_costs" in {o["id"] for o in crown_siege.HERALD_SIEGE_OPTIONS}, "herald costs option")
    ok, lines = crown_siege.handle_command(conn, dfn, "/siege costs")
    check(ok and any("battering ram" in ln.lower() for ln in lines), f"costs still work ({lines})")


def test_side_fighters_and_skill_boost():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    # Pad a non-leader attacker member and seed high smithing/woodcutting.
    member = conn.execute(
        "SELECT id FROM players WHERE username LIKE 'cap_a_m%' LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "UPDATE players SET smithing_xp = ?, woodcutting_xp = ? WHERE id = ?",
        (2_000_000, 2_000_000, member),  # high levels → near +50% mult
    )
    conn.commit()
    mult = crown_siege.siege_skill_mult(conn, member)
    check(mult > 1.2, f"high skills raise siege mult ({mult})")
    _fund_side(
        conn, atk,
        {"timber": 400, "bars": 80, "ore": 40},
        alloc={"rams": 70, "ladders": 10, "barricades": 10, "reserve": 10},
        now=T0 + 4,
    )
    _fund_side(
        conn, dfn,
        {"timber": 200, "stone": 200, "bars": 40},
        alloc={"rams": 10, "ladders": 10, "barricades": 20, "reserve": 60},
        now=T0 + 5,
    )
    # Non-leader on the attack side can craft and fire.
    ok, msg = crown_siege.craft_weapon(conn, member, "ram", 1, now=T0 + 6)
    check(ok and "contrib" in msg.lower(), f"member crafts ram ({msg})")
    ok, msg, meta = crown_siege.fire_weapon(conn, member, "ram", "outer_gate", now=T0 + 7)
    check(ok, f"member fires ram ({msg})")
    base = crown_siege.WEAPONS["ram"]["damage"]
    # Message reports boosted damage.
    check(str(int(round(base * mult))) in msg or "skill" in msg.lower(),
          f"fire reflects skill boost ({msg}, mult={mult})")
    gate = crown_siege.get_structure(conn, "outer_gate")
    expected_hp = gate["max_hp"] - int(round(base * mult))
    # Fresh assault not begun — structure may already be damaged from fire above.
    check(gate["hp"] == expected_hp or gate["hp"] < gate["max_hp"] - base,
          f"skill-boosted damage applied ({gate}, expected ~{expected_hp})")
    # Defender non-leader repairs with skill boost.
    dfn_member = conn.execute(
        "SELECT id FROM players WHERE username LIKE 'cap_d_m%' LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "UPDATE players SET smithing_xp = ?, woodcutting_xp = ? WHERE id = ?",
        (2_000_000, 2_000_000, dfn_member),
    )
    conn.commit()
    crown_siege.apply_damage(conn, "west_wall", 2000)
    before = crown_siege.get_structure(conn, "west_wall")["hp"]
    ok, msg, _ = crown_siege.repair_structure(conn, dfn_member, "west_wall", 1, now=T0 + 8)
    check(ok and "skill" in msg.lower(), f"defender member repairs ({msg})")
    after = crown_siege.get_structure(conn, "west_wall")["hp"]
    check(after - before > crown_siege.REPAIR_BATCH_HP,
          f"skill boosts repair HP ({before}→{after})")
    # Outsider still blocked.
    out, _ = _pad_guild(db, "sk_out", "SkOut", "No War Guild", crown_siege.HUMAN_MIN)
    ok, msg = crown_siege.craft_weapon(conn, out, "ram", 1, now=T0 + 9)
    check(not ok and "not fighting" in msg.lower(), f"outsider craft blocked ({msg})")


def test_war_council_notice_and_guild_panel():
    db = make_db()
    conn = db.conn
    # No open war → council quiet (or founding-only).
    quiet = crown_siege.war_council_lines(conn)
    check(quiet == [] or "no War for the Crown is open" in " ".join(quiet),
          f"quiet council when no war ({quiet})")
    atk, dfn = _confirm_both_sides(db)
    lines = crown_siege.war_council_lines(conn, atk, now=T0 + 5)
    blob = " ".join(lines).lower()
    check("royal war council" in blob, f"notice board names war council ({lines})")
    check("war for the crown" in blob, f"council names the war ({lines})")
    check("assault guild" in blob and "hold guild" in blob, f"council names both sides ({lines})")
    check(any("herald" in ln.lower() or "/siege" in ln.lower() for ln in lines),
          f"council points to herald/commands ({lines})")
    atk_cid = crown_siege._clan_of(conn, atk)
    dfn_cid = crown_siege._clan_of(conn, dfn)
    summary = crown_siege.guild_war_summary(conn, atk_cid, now=T0 + 5)
    check(summary and summary["side"] == "attack" and summary["role"] == "lead",
          f"attacker guild summary ({summary})")
    check("scheduled" in summary["line"].lower() or "assault" in summary["line"].lower(),
          f"guild line mentions schedule ({summary})")
    # clans.public exposes the war blurb for the guild panel.
    pub = clans.public(atk_cid)
    check(isinstance(pub.get("war"), dict) and pub["war"]["side"] == "attack",
          f"clan public carries war ({pub.get('war')})")
    outsider, out_cid = _pad_guild(db, "out_w", "OutLead", "Spectators", crown_siege.HUMAN_MIN)
    check(crown_siege.guild_war_summary(conn, out_cid) is None, "outsider guild has no war blurb")
    check(clans.public(out_cid).get("war") is None, "outsider public has no war")
    # After resolve, notice board keeps the last Crownfall note.
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    crown_siege.resolve_war(conn, winner="defend", now=T0 + 20)
    after = crown_siege.war_council_lines(conn, dfn, now=T0 + 21)
    check(any("last crownfall" in ln.lower() for ln in after), f"board keeps last crownfall ({after})")


def test_alloc_budget_enforced_and_locked():
    db = make_db()
    conn = db.conn
    atk, _dfn = _confirm_both_sides(db)
    # 100 timber deposited; rams only get 20% → budget 20. One ram costs 40.
    _fund_side(
        conn, atk,
        {"timber": 100, "bars": 20},
        alloc={"rams": 20, "ladders": 20, "barricades": 20, "reserve": 40},
        now=T0 + 4,
    )
    ok, msg = crown_siege.craft_weapon(conn, atk, "ram", 1, now=T0 + 5)
    check(not ok and "allocation" in msg.lower(), f"ram blocked by rams budget ({msg})")
    # Board / alloc status show empty spent against timber budgets.
    lines = " ".join(crown_siege.store_lines(conn, atk, now=T0 + 5)).lower()
    check("spent (timber)" in lines and "rams 0/20t" in lines,
          f"board shows timber spent/budget ({lines})")
    pub = crown_siege.war_public(conn)
    spend = pub["sides"]["attack"]["alloc_spend"]
    check(spend["rams"]["resources"]["timber"]["budget"] == 20, f"public rams budget ({spend})")
    check(spend["rams"]["resources"]["timber"]["spent"] == 0, f"public rams spent ({spend})")
    ok, view = crown_siege.handle_command(conn, atk, "/siege alloc")
    check(ok and any("0/20t" in ln for ln in view), f"/siege alloc view ({view})")
    # Rebalance before the assault so rams can spend.
    ok, msg = crown_siege.set_allocation(
        conn, atk,
        {"rams": 60, "ladders": 10, "barricades": 10, "reserve": 20},
        now=T0 + 6,
    )
    check(ok, f"rebalance before assault ({msg})")
    ok, msg = crown_siege.craft_weapon(conn, atk, "ram", 1, now=T0 + 7)
    check(ok, f"ram crafts inside new budget ({msg})")
    spend2 = crown_siege.alloc_status(conn, crown_siege.current_war(conn)["id"],
                                      crown_siege._clan_of(conn, atk))
    check(spend2["rams"]["resources"]["timber"]["spent"] == 40,
          f"rams spent timber after craft ({spend2})")
    lines2 = " ".join(crown_siege.store_lines(conn, atk, now=T0 + 8)).lower()
    check("rams 40/60t" in lines2, f"board updates spent after craft ({lines2})")
    crown_siege.begin_assault(conn, atk, now=T0 + 10)
    ok, msg = crown_siege.set_allocation(
        conn, atk,
        {"rams": 40, "ladders": 25, "barricades": 20, "reserve": 15},
        now=T0 + 11,
    )
    check(not ok and "lock" in msg.lower(), f"alloc locked mid-assault ({msg})")
    ok, view2 = crown_siege.handle_command(conn, atk, "/siege alloc")
    check(ok and any("locked" in ln.lower() for ln in view2), f"alloc view notes lock ({view2})")


def test_forfeit_and_dismiss_locked_during_assault():
    db = make_db()
    conn = db.conn
    atk, dfn = _confirm_both_sides(db)
    # Before assault, forfeit still works.
    ok, msg = crown_siege.forfeit(conn, atk, now=T0 + 5)
    check(ok and "forfeited" in msg.lower(), f"forfeit before assault ({msg})")
    # Rebuild a fresh confirmed war.
    db2 = make_db()
    atk2, dfn2 = _confirm_both_sides(db2)
    crown_siege.begin_assault(db2.conn, atk2, now=T0 + 10)
    ok, msg = crown_siege.forfeit(db2.conn, atk2, now=T0 + 11)
    check(not ok and "assault" in msg.lower(), f"forfeit blocked mid-assault ({msg})")
    # Seed a recruit, then dismiss must lock during assault.
    atk_cid = crown_siege._clan_of(db2.conn, atk2)
    db2.conn.execute(
        "INSERT INTO clan_recruits (clan_id, name, role, hired_at, upkeep_paid_through, active) "
        "VALUES (?, 'LockedMerc', 'Guard', ?, ?, 1)",
        (atk_cid, T0 + 10, T0 + 10),
    )
    db2.conn.commit()
    rid = db2.conn.execute(
        "SELECT id FROM clan_recruits WHERE clan_id = ? AND name = 'LockedMerc'",
        (atk_cid,),
    ).fetchone()[0]
    ok, msg = clans.dismiss_core(atk2, rid)
    check(not ok and "locked" in msg.lower(), f"dismiss locked mid-assault ({msg})")
    check(db2.conn.execute(
        "SELECT COUNT(*) FROM clan_recruits WHERE id = ?", (rid,)
    ).fetchone()[0] == 1, "recruit still present")


if __name__ == "__main__":
    test_hp_bands()
    test_damage_persists()
    test_founder_once()
    test_client_overlay_helpers()
    test_register_confirm_and_schedule()
    test_confirm_timeout_promotes_queue()
    test_alliances_count_toward_human_min()
    test_king_guild_cannot_attack()
    test_siege_command_parser()
    test_storehouse_deposit_alloc_contrib()
    test_weapons_damage_and_breaches()
    test_capture_throne_and_last_stand()
    test_heraldry_and_council_commands()
    test_roster_caps()
    test_live_interest_and_presence()
    test_repair_and_structure_sync()
    test_challenge_gated_during_war()
    test_auto_assault_after_confirm_delay()
    test_siege_kill_tally_and_board()
    test_barricades_stages_depot_reset_monthly()
    test_structure_effects_and_capture_markers()
    test_engine_contrib_tower_need_and_scars()
    test_assault_clock_scout_and_capture_contrib()
    test_chronicle_roster_lock_postpone_and_scar_click()
    test_elim_blocks_actions_and_requirements_board()
    test_war_hire_caps_elim_names_and_herald_costs()
    test_side_fighters_and_skill_boost()
    test_war_council_notice_and_guild_panel()
    test_alloc_budget_enforced_and_locked()
    test_forfeit_and_dismiss_locked_during_assault()
    print("crown siege next pass ok")
