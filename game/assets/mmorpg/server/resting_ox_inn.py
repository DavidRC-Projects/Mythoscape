"""The Resting Ox tavern (server side). Entered from the inn's arched door (resting_ox_arch).

Rules and data live in server/tavern.py; this module checks the door and routes the BAR_* messages.
Client -> server:
  BAR_ENTER, BAR_INTRO_SEEN, BAR_LEAVE
  BAR_TALK {patron: barman|wenna|tobin|sable}, BAR_CHOICE {patron, choice}, BAR_SABLE_DRINK
  BAR_ORDER {item}, BAR_RUMOUR {tip}, BAR_ABOUT {topic}
  BAR_SIT {seat: bar|table, table}, BAR_STAND, BAR_QUEUE {table}, BAR_TABLE_LOCK {locked},
  BAR_TABLE_CHAT {text}, BAR_TOAST, BAR_TOAST_JOIN, BAR_ROUND
  BAR_BOARD, BAR_JOB {action: accept|drop|turn_in, id}, BAR_POST {kind, fields, note, escrow},
  BAR_POST_ACT {action: cancel|renew|report, id}, BAR_PROCLAIM {template, value, note}
  BAR_TROPHIES, BAR_BARD, BAR_BARD_REQ {song, jump}
Server -> client: BAR_STATE, BAR_LINE, BAR_SERVED, BAR_BOARD_STATE, BAR_TROPHY_STATE, BAR_BARD_STATE,
  BAR_TABLE, BAR_TABLES, BAR_BUFFS, BAR_LEFT, ERROR.
"""
import time

import tavern

DOOR = (9, 47)          # fallback only; the live door comes from content.INTERACTABLES
EXIT = (9, 48)
INN_FLOOR = (5, 37, 14, 46)
ALE_PRICE = tavern.DRINKS["village_ale"]["price"]
BARMAN = tavern.BRAM
PATRONS = tavern.PATRONS


def _door():
    """(door, exit, enter, floor) from the live content pins, so moving the inn never breaks the bar."""
    try:
        import content
        ents = list(content.INTERACTABLES)
        ents.sort(key=lambda e: 0 if e.get("id") == "resting_ox_arch" else 1)
        for ent in ents:
            if ent.get("id") in ("resting_ox_arch", "cottage_sw_door"):
                d = (int(ent["x"]), int(ent["y"]))
                ex = (int(ent.get("exit_x", d[0])), int(ent.get("exit_y", d[1] + 1)))
                en = (int(ent.get("enter_x", d[0])), int(ent.get("enter_y", d[1] - 1)))
                floor = INN_FLOOR
                try:
                    import buildings_v2
                    fl = getattr(buildings_v2, "FLOORS", None) or {}
                    if "cottage_sw" in fl:
                        floor = tuple(fl["cottage_sw"])
                except Exception:
                    pass
                return d, ex, en, floor
    except Exception:
        pass
    return DOOR, EXIT, (DOOR[0], DOOR[1] - 2), INN_FLOOR


def _near_door(session):
    x, y = int(getattr(session, "x", -99)), int(getattr(session, "y", -99))
    door, _exit, enter, (x0, y0, x1, y1) = _door()
    near = lambda p: max(abs(x - p[0]), abs(y - p[1])) <= 3
    return near(door) or near(enter) or (x0 <= x <= x1 and y0 <= y <= y1)


def _conn():
    import server
    return server.WORLD.db.conn


def _coins(session):
    return int(getattr(session, "coins", 0) or 0)


def state(session, info=None):
    bar = getattr(session, "bar", None) or {}
    out = {"seat": bar.get("seat", "bar"), "table": bar.get("table"), "ale_price": ALE_PRICE,
           "coins": _coins(session), "barman": BARMAN["name"],
           "patrons": [{"id": k, "name": v["name"], "seat": v["view"]} for k, v in PATRONS.items()],
           "buffs": tavern.buffs_payload(session), "tables": tavern.tables_state()}
    if info:
        out.update(info)
        out["free_ale"] = info.get("free_left", 0) > 0
    return out


async def _line(send, session, line, speaker=None, **extra):
    await send(session.ws, "BAR_LINE", speaker=speaker or BARMAN["name"], line=line, coins=_coins(session),
               buffs=tavern.buffs_payload(session), **extra)


async def _table_push(send, t):
    if t is None:
        return
    payload = tavern.table_payload(t)
    for s in t["seats"]:
        if s is not None and getattr(s, "ws", None) is not None:
            try:
                await send(s.ws, "BAR_TABLE", table=payload)
            except Exception:
                pass


async def tick(send):
    """Called from the server's regen loop: resolve finished toasts."""
    for t in tavern.pending_toasts():
        joined = tavern.toast_resolve(t)
        if joined is None:
            continue
        if joined:
            t["chat"].append({"from": "Bram", "text": f"{len(joined)} tankards clink. +1% XP for 5 minutes."})
        else:
            t["chat"].append({"from": "Bram", "text": "Nobody joined the toast. Drink alone, then."})
        await _table_push(send, t)
        for s in joined:
            try:
                await send(s.ws, "BAR_BUFFS", buffs=tavern.buffs_payload(s))
            except Exception:
                pass


def left_game(session):
    tavern.drop_session(session)


async def handle(session, mtype, msg, send):
    """Returns True when the message was a bar message. Persists coin / HP changes afterwards."""
    if not mtype.startswith("BAR_"):
        return False
    before = (_coins(session), int(getattr(session, "bank_coins", 0) or 0), getattr(session, "hp", None))
    await _handle(session, mtype, msg, send)
    after = (_coins(session), int(getattr(session, "bank_coins", 0) or 0), getattr(session, "hp", None))
    if after != before:
        try:
            import server
            server.WORLD.db.save_player_stats(session.player_id, coins=after[0], bank_coins=after[1], hp=after[2])
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        except Exception:
            pass
    return True


async def _handle(session, mtype, msg, send):
    conn = _conn()
    bar = getattr(session, "bar", None)
    ws = session.ws
    if mtype == "BAR_ENTER":
        if getattr(session, "dungeon", None) or not _near_door(session):
            await send(ws, "ERROR", message="You need to be at the Resting Ox door.")
            return True
        session.bar = {"seat": "bar", "table": None}
        info = tavern.enter(session, conn)
        await send(ws, "BAR_STATE", bar=state(session, info), line=info["line"], speaker=BARMAN["name"],
                   intro=info["intro"])
        return True
    if bar is None:
        await send(ws, "ERROR", message="You're not in the Resting Ox.")
        return True
    if mtype == "BAR_INTRO_SEEN":
        tavern.mark_intro_seen(conn, session.player_id)
    elif mtype == "BAR_TALK":
        pid = str(msg.get("patron") or "")
        if pid == "barman":
            sp = tavern.special_today()
            name = (tavern.DRINKS.get(sp) or tavern.FOOD.get(sp))["name"]
            await _line(send, session, tavern.DRINKS_LINE.format(special=name), patron="barman",
                        choices=["Drinks", "Food", "Any rumours?", "Tell me about...", "Leave"])
        else:
            ok, line, info = tavern.patron_talk(session, conn, pid)
            if not ok:
                await send(ws, "ERROR", message=line)
            else:
                await _line(send, session, line, info["speaker"], patron=pid, choices=info["choices"])
    elif mtype == "BAR_CHOICE":
        pid = str(msg.get("patron") or "")
        ok, line, info = tavern.patron_talk(session, conn, pid, int(msg.get("choice") or 0))
        if ok:
            await _line(send, session, line, info.get("speaker"), patron=pid, offer=info.get("offer"),
                        quest=info.get("quest"), close=True)
    elif mtype == "BAR_SABLE_DRINK":
        ok, line, _price = tavern.buy_sable_drink(session, conn)
        await _line(send, session, line, "Sable", patron="sable", close=True)
    elif mtype == "BAR_ORDER":
        item = str(msg.get("item") or "village_ale")
        ok, line, info = tavern.buy(session, conn, item)
        if not ok:
            await _line(send, session, line, patron="barman")
            return True
        await send(ws, "BAR_SERVED", price=info["price"], free=info["free"], item=item, name=info["name"],
                   drink=info["drink"], tipsy=info["tipsy"], free_left=info["free_left"], coins=_coins(session),
                   hp=int(getattr(session, "hp", 0) or 0), speaker=BARMAN["name"], line=line,
                   buffs=tavern.buffs_payload(session))
    elif mtype == "BAR_RUMOUR":
        ok, text, hook, paid = tavern.rumour(session, conn, tip=bool(msg.get("tip")))
        await _line(send, session, text, patron="barman", rumour=ok, hook=hook, paid=paid)
    elif mtype == "BAR_ABOUT":
        topic = str(msg.get("topic") or "")
        await _line(send, session, tavern.ABOUT.get(topic, "Can't say I know much about that."), patron="barman")
    elif mtype == "BAR_SIT":
        seat = msg.get("seat")
        if seat == "table":
            tid = int(msg.get("table") or 1)
            ok, line, t = tavern.sit(session, tid)
            if ok:
                bar.update(seat="table", table=t["id"])
                await _table_push(send, t)
            else:
                await _line(send, session, line, "")
        elif seat == "bar":
            t = tavern.stand(session)
            bar.update(seat="bar", table=None)
            await _table_push(send, t)
        await send(ws, "BAR_STATE", bar=state(session))
    elif mtype == "BAR_STAND":
        t = tavern.stand(session)
        bar.update(seat="bar", table=None)
        await _table_push(send, t)
        await send(ws, "BAR_STATE", bar=state(session))
    elif mtype == "BAR_TABLES":
        await send(ws, "BAR_TABLES", tables=tavern.tables_state())
    elif mtype == "BAR_QUEUE":
        tavern.join_queue(session, int(msg.get("table") or 1))
        await _line(send, session, "You'll get a nod when a seat frees up.", "")
    elif mtype == "BAR_TABLE_LOCK":
        ok, line, t = tavern.set_lock(session, bool(msg.get("locked")))
        await _line(send, session, line, "")
        await _table_push(send, t)
    elif mtype == "BAR_TABLE_CHAT":
        ok, line, t = tavern.table_chat(session, msg.get("text"))
        if ok:
            await _table_push(send, t)
        else:
            await _line(send, session, line, "")
    elif mtype in ("BAR_TOAST", "BAR_TOAST_JOIN"):
        fn = tavern.toast_start if mtype == "BAR_TOAST" else tavern.toast_join
        ok, line, t = fn(session)
        if not ok:
            await _line(send, session, line, "")
        await _table_push(send, t)
    elif mtype == "BAR_ROUND":
        ok, line, t = tavern.order_round(session, conn)
        await _line(send, session, line, BARMAN["name"] if ok else "")
        if ok:
            await _table_push(send, t)
            for s in t["seats"]:
                if s is not None and s is not session:
                    await send(s.ws, "BAR_BUFFS", buffs=tavern.buffs_payload(s))
    elif mtype == "BAR_BOARD":
        await send(ws, "BAR_BOARD_STATE", board=tavern.board_state(session, conn))
    elif mtype == "BAR_JOB":
        act, jid = msg.get("action"), str(msg.get("id") or "")
        if act == "accept":
            ok, line = tavern.accept_job(session, conn, jid)
        elif act == "drop":
            ok, line = tavern.drop_job(session, conn, jid)
        else:
            ok, line, _r = tavern.turn_in_job(session, conn, jid)
        await _line(send, session, line, "", board_result=ok)
        await send(ws, "BAR_BOARD_STATE", board=tavern.board_state(session, conn))
    elif mtype == "BAR_POST":
        ok, line, _pid = tavern.create_post(session, conn, str(msg.get("kind") or ""), msg.get("fields") or {},
                                            msg.get("note") or "", int(msg.get("escrow") or 0))
        await _line(send, session, line, "", board_result=ok)
        await send(ws, "BAR_BOARD_STATE", board=tavern.board_state(session, conn))
    elif mtype == "BAR_POST_ACT":
        act, post = msg.get("action"), int(msg.get("id") or 0)
        fn = {"cancel": tavern.cancel_post, "renew": tavern.renew_post, "report": tavern.report_post}.get(act)
        ok, line = fn(session, conn, post) if fn else (False, "Unknown action.")
        await _line(send, session, line, "", board_result=ok)
        await send(ws, "BAR_BOARD_STATE", board=tavern.board_state(session, conn))
    elif mtype == "BAR_PROCLAIM":
        ok, line = tavern.proclaim(session, conn, str(msg.get("template") or ""), msg.get("value") or "",
                                   msg.get("note") or "")
        await _line(send, session, line, "", board_result=ok)
        await send(ws, "BAR_BOARD_STATE", board=tavern.board_state(session, conn))
    elif mtype == "BAR_TROPHIES":
        await send(ws, "BAR_TROPHY_STATE", trophies=tavern.trophies(conn))
    elif mtype == "BAR_BARD":
        await send(ws, "BAR_BARD_STATE", bard=tavern.bard_state())
    elif mtype == "BAR_BARD_REQ":
        ok, line = tavern.bard_request(session, conn, str(msg.get("song") or ""), bool(msg.get("jump")))
        await _line(send, session, line, "Elric", bard_result=ok)
        await send(ws, "BAR_BARD_STATE", bard=tavern.bard_state())
    elif mtype == "BAR_LEAVE":
        t = tavern.stand(session)
        await _table_push(send, t)
        line = tavern.leave(session, conn)
        session.bar = None
        session.x, session.y = _door()[1]
        await send(ws, "BAR_LEFT", x=session.x, y=session.y, line=line)
    return True
