"""The Resting Ox bar scene (server side). Self-contained: entered from the inn's arched door.

Messages (client -> server): BAR_ENTER, BAR_TALK {patron}, BAR_ORDER, BAR_SIT {seat}, BAR_LEAVE.
Replies: BAR_STATE, BAR_LINE, BAR_SERVED, BAR_LEFT, ERROR. The scene itself is drawn client side
(client/resting_ox_bar.py); this server module only validates the door, charges for ale and moves the player out.
"""
DOOR = (9, 47)          # fallback only; the live door comes from content.INTERACTABLES (cottage_sw_door)
EXIT = (9, 48)
INN_FLOOR = (5, 37, 14, 46)


def _door():
    """(door, exit, floor) from the live content pins, so moving the inn never breaks the bar."""
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
ALE_PRICE = 2
PATRONS = {
    "old_tam": {"name": "Old Tam", "seat": "left", "lines": [
        "Sit, sit. The Ox pours the best ale this side of the mountains.",
        "Rats in the sewer again, they say. The grate's just outside, if you've the stomach.",
        "Saw lights up on the passes last night. Wouldn't wander the vale after dark unarmed.",
    ]},
    "wren": {"name": "Wren the Minstrel", "seat": "right", "lines": [
        "A new face! Raise a stein with me, traveller.",
        "They say the arena champion fights one-on-one now. Brutus hates arrows, I hear.",
        "Mae's shop has the finest gowns and coats. Earn your rank and she'll dress you like a lord.",
    ]},
}
BARMAN = {"name": "Barnaby", "lines": [
    "Welcome to the Resting Ox. Ale's two coins, first one's on the house.",
    "Another? Mind the foam.",
]}


def _near_door(session):
    x, y = int(getattr(session, "x", -99)), int(getattr(session, "y", -99))
    door, _exit, enter, (x0, y0, x1, y1) = _door()
    near = lambda p: max(abs(x - p[0]), abs(y - p[1])) <= 3
    return near(door) or near(enter) or (x0 <= x <= x1 and y0 <= y <= y1)


def state(session):
    bar = getattr(session, "bar", None) or {}
    return {
        "seat": bar.get("seat", "bar"), "ale_price": ALE_PRICE, "free_ale": not bar.get("served"),
        "coins": int(getattr(session, "coins", 0) or 0),
        "barman": BARMAN["name"],
        "patrons": [{"id": k, "name": v["name"], "seat": v["seat"]} for k, v in PATRONS.items()],
    }


async def handle(session, mtype, msg, send):
    """Returns True when the message was a bar message."""
    if not mtype.startswith("BAR_"):
        return False
    bar = getattr(session, "bar", None)
    if mtype == "BAR_ENTER":
        if getattr(session, "dungeon", None) or not _near_door(session):
            await send(session.ws, "ERROR", message="You need to be at the Resting Ox door.")
            return True
        session.bar = {"seat": "bar", "served": 0, "talk": {}}
        await send(session.ws, "BAR_STATE", bar=state(session), line=BARMAN["lines"][0], speaker=BARMAN["name"])
        return True
    if bar is None:
        await send(session.ws, "ERROR", message="You're not in the Resting Ox.")
        return True
    if mtype == "BAR_TALK":
        pid = str(msg.get("patron") or "")
        if pid == "barman":
            p = BARMAN
        else:
            p = PATRONS.get(pid)
        if not p:
            await send(session.ws, "ERROR", message="Nobody there.")
            return True
        n = bar["talk"].get(pid, 0)
        bar["talk"][pid] = n + 1
        await send(session.ws, "BAR_LINE", patron=pid, speaker=p["name"], line=p["lines"][n % len(p["lines"])])
    elif mtype == "BAR_SIT":
        seat = msg.get("seat")
        if seat in ("bar", "table"):
            bar["seat"] = seat
        await send(session.ws, "BAR_STATE", bar=state(session))
    elif mtype == "BAR_ORDER":
        price = 0 if not bar["served"] else ALE_PRICE
        if price:
            import mercenaries
            ok, err, _p, _b = mercenaries.spend_coins(session, price)
            if not ok:
                await send(session.ws, "BAR_LINE", patron="barman", speaker=BARMAN["name"],
                           line="Two coins for an ale, friend. Come back when your purse is heavier.")
                return True
        bar["served"] += 1
        await send(session.ws, "BAR_SERVED", price=price, coins=int(getattr(session, "coins", 0) or 0),
                   speaker=BARMAN["name"], line="On the house!" if not price else BARMAN["lines"][1])
    elif mtype == "BAR_LEAVE":
        session.bar = None
        session.x, session.y = _door()[1]
        await send(session.ws, "BAR_LEFT", x=session.x, y=session.y)
    return True
