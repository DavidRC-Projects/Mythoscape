"""Moonpetal Inn — quest talk bridge + fairy friendship / house secret.

Client owns film / room POV. Quest offer/progress and friendship social talk
go through MOONPETAL_* messages.
"""
from __future__ import annotations

import fairy_friendship as FF
import quest_steps
from content import QUESTS

DOOR_ID = "moonpetal_inn_door"
FAIRY_NAMES = FF.FAIRY_NAMES
NAME_TO_ID = FF.NAME_TO_ID

# Short quest lines when a step targets this fairy.
STEP_LINES = {
    ("moonpetal_hospitality", "ivria"): (
        "A spare candle note? Take it — and tell Selune the archives still stand.",
    ),
    ("moonpetal_hospitality", "maelis"): (
        "The blooms are thirsty. Three dews from the glade, then come back to me.",
        "You brought the dew. The blooms will open cleaner tonight.",
    ),
    ("moonpetal_hospitality", "aerin"): (
        "A traveler named Nell wanders the south edge of the glade. Calm her — she keeps missing the door.",
    ),
    ("moonpetal_hospitality", "rhosyn"): (
        "Tell Tamsin I want the old moon-road air — the quiet one. She'll know.",
    ),
    ("moonpetal_hospitality", "tamsin_moon"): (
        "Rhosyn's song? Done. Tell Selune the house is settled.",
    ),
    ("moonpetal_hospitality", "selune"): (
        "You came back. The house is quieter for it. Thank you.",
    ),
    ("misplaced_folio", "kaede"): (
        "Someone left with a folio under their cloak — headed toward the wishing well. Ask Bryony; her crystals saw it.",
    ),
    ("misplaced_folio", "bryony"): (
        "North of the wishing well. Three rats. The page is humming.",
    ),
    ("misplaced_folio", "ivria"): (
        "You found it — but the seal is cracked. Lady Elowen can verify. Then bring it home.",
        "The seal holds. The shelves remember you kindly.",
    ),
}


def _conn():
    import server
    return server.WORLD.db.conn


def _near_door(session):
    try:
        from content import INTERACTABLES
        for ent in INTERACTABLES:
            if ent.get("id") != DOOR_ID:
                continue
            dx, dy = int(ent["x"]), int(ent["y"])
            sx = int((ent.get("stand") or [dx, dy + 1])[0])
            sy = int((ent.get("stand") or [dx, dy + 1])[1])
            x, y = int(session.x), int(session.y)
            return max(abs(x - dx), abs(y - dy)) <= 3 or max(abs(x - sx), abs(y - sy)) <= 2
    except Exception:
        pass
    x, y = int(getattr(session, "x", -1)), int(getattr(session, "y", -1))
    return max(abs(x - 21), abs(y - 82)) <= 3


def resolve_fairy(msg):
    raw = msg.get("fairy") or msg.get("npc_id") or msg.get("name") or ""
    fid = FF.resolve_id(raw)
    if not fid:
        return None, str(raw)
    return fid, FF.FAIRY_NAMES.get(fid, str(raw))


def _active_step_for(session, fairy_id):
    for qid, qdef in QUESTS.items():
        if qdef.get("type") != "steps":
            continue
        prog = session.quests.get(qid)
        if not prog or prog.get("status") not in ("active", "ready"):
            continue
        if prog.get("status") == "ready" and qdef.get("giver") == fairy_id:
            return qid, qdef, prog, {"kind": "deliver", "target": fairy_id}
        cur = quest_steps.current_step(qdef, prog)
        if not cur:
            continue
        _idx, step = cur
        target = step.get("target")
        if step.get("kind") == "deliver":
            target = target or qdef.get("giver")
        if target == fairy_id:
            return qid, qdef, prog, step
    return None


def _offer_for(session, fairy_id):
    offers = quest_steps.try_interior_offer_lines(session, fairy_id)
    return offers[0] if offers else None


def _friend_payload(d, fairy_id):
    return FF.public_state(d, fairy_id)


async def _send_line(send, session, fairy_name, fairy_id, line, choices=None, quest=None,
                     friend=None, close=False, page=None, gained=0):
    import petaldeep
    if petaldeep.try_grant_key(session):
        line = ((line or "").rstrip() + "\n\n" + petaldeep.KEY_GIFT.format(name=fairy_name)).strip()
        await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await send(session.ws, "CHAT_MSG", **{
            "from": fairy_name, "text": "You receive the Petaldeep Key.",
        })
    await send(
        session.ws, "MOONPETAL_LINE",
        fairy=fairy_name, npc_id=fairy_id, line=line or "",
        choices=list(choices or []), quest=quest,
        friendship=friend, close=bool(close), page=page,
        gained=int(gained or 0),
    )


def _social_menu_choices(d, fairy_id):
    """Build greeting-menu labels once friendship state is known."""
    pub = FF.public_state(d, fairy_id)
    choices = []
    # Topics
    for tid, lab in (
        ("moon", "Ask about the Moon"),
        ("fae", "Ask about the Fae"),
        ("throne", "Ask about Throne & Realm"),
        ("rumours", "Ask about Rumours"),
    ):
        mark = " ✓" if tid in (pub.get("topics_done") or []) else ""
        choices.append(f"{lab}{mark}")
    choices.append("Offer a compliment…")
    if pub.get("secret_unlocked"):
        choices.append("Ask about the house secret")
    elif int(pub.get("value") or 0) >= 40:
        choices.append("Ask what the house still hides")
    choices.append("Leave")
    return choices, pub


async def handle(session, mtype, msg, send):
    import server as srv

    if mtype == "MOONPETAL_ENTER":
        if not _near_door(session):
            await send(session.ws, "ERROR", message="Stand at the Moonpetal Inn door.")
            return True
        session.moonpetal = {"in": True}
        import petaldeep
        petaldeep.prepare_account(session)
        if petaldeep.try_grant_key(session):
            await send(session.ws, "PLAYER_UPDATE", player=session.full_state())
            await send(session.ws, "CHAT_MSG", **{
                "from": "Selune",
                "text": petaldeep.KEY_GIFT.format(name="Selune"),
            })
        d = FF.load(_conn(), session.player_id)
        await send(
            session.ws, "MOONPETAL_STATE",
            inside=True, friendship=FF.public_state(d),
        )
        return True

    if mtype == "MOONPETAL_LEAVE":
        session.moonpetal = None
        await send(session.ws, "MOONPETAL_STATE", inside=False)
        return True

    if mtype not in ("MOONPETAL_TALK", "MOONPETAL_CHOICE", "MOONPETAL_SOCIAL"):
        return False

    fairy_id, fairy_name = resolve_fairy(msg)
    if not fairy_id:
        await send(session.ws, "ERROR", message="No one answers.")
        return True

    conn = _conn()
    offer = _offer_for(session, fairy_id)
    step_hit = _active_step_for(session, fairy_id)

    # --- Social: topic / compliment / secret ---------------------------------
    if mtype == "MOONPETAL_SOCIAL":
        kind = str(msg.get("kind") or "")
        sid = str(msg.get("id") or "")
        d = FF.load(conn, session.player_id)
        gained = 0
        line = ""
        page = "social"
        if kind == "topic":
            d, gained, line = FF.apply_topic(conn, session.player_id, fairy_id, sid)
        elif kind == "compliment":
            d, gained, line = FF.apply_compliment(conn, session.player_id, fairy_id, sid)
        elif kind == "secret":
            line = FF.secret_line(d)
            if d.get("secret_unlocked") or FF.all_maxed(d):
                d = FF.mark_secret_told(conn, session.player_id)
            page = "secret"
        else:
            line = "She waits."
        friend = _friend_payload(d, fairy_id)
        choices = ["Offer another compliment…", "Ask something else", "Leave"] if kind != "secret" else [
            "I will remember.", "Leave",
        ]
        if kind == "secret" and not friend.get("secret_unlocked"):
            choices = ["I will earn their trust.", "Leave"]
        await _send_line(
            send, session, fairy_name, fairy_id, line,
            choices=choices, friend=friend, page=page, gained=gained,
        )
        return True

    if mtype == "MOONPETAL_TALK":
        d, greet_gain = FF.greet(conn, session.player_id, fairy_id)
        choices = []
        line = None
        quest_payload = None
        page = "greeting"
        if offer and offer.get("state") == "offerable":
            line = f"{fairy_name}: I have a task, if you'll take it."
            choices = [f"Accept: {offer['name']}", "Not now — just talk"]
            quest_payload = offer
            page = "quest_offer"
        elif step_hit:
            qid, qdef, prog, step = step_hit
            lines = STEP_LINES.get((qid, fairy_id)) or ()
            if len(lines) > 1 and step.get("id") in ("maelis_deliver", "return_ivria"):
                line = lines[-1]
            elif lines:
                line = lines[0]
            else:
                line = quest_steps.objective_text(qdef, prog, session)
            if prog.get("status") == "ready" or step.get("kind") == "deliver":
                choices = ["[Turn in / report]", "Just talk", "Leave"]
            else:
                choices = ["[Continue]", "Just talk", "Leave"]
            quest_payload = {
                "quest_id": qid, "state": prog.get("status"),
                "name": qdef.get("name"),
                "objective": quest_steps.objective_text(qdef, prog, session),
            }
            page = "quest"
        else:
            friend = int((d.get("friendship") or {}).get(fairy_id) or 0)
            if friend >= 100:
                line = (
                    f"{fairy_name} lights up when she sees you.\n\n"
                    f"\"There you are. The house already knows your step.\""
                )
            elif friend >= 50:
                line = (
                    f"{fairy_name} smiles — warmer than a first greeting.\n\n"
                    f"\"Sit. You've been kind to us. What shall we speak of?\""
                )
            else:
                # Use the classic short greet as opener; menu carries the rest.
                greets = {
                    "selune": "You came in with the rain on your boots and the realm on your shoulders. Set both down a while.",
                    "ivria": "Mind the candle. These pages are older than your grandmother's grandmother.",
                    "maelis": "Don't touch the blue ones. They bite. Only a little.",
                    "aerin": "I saw you three streets away. You walk like someone being followed.",
                    "rhosyn": "You stopped on the stairs to listen. Everyone does. Come, sit.",
                    "tamsin_moon": "Moonwine, dewmead or something honest? I'd suggest honest, for your first night.",
                    "nyx": "Sit by the fire. You've been cold for longer than tonight.",
                    "kaede": "Don't read over my shoulder. Unless you're offering to deliver this.",
                    "bryony": "Oh, you're the one from the crystals! Well, someone like you. Sit, sit.",
                }
                line = greets.get(fairy_id, f"{fairy_name} nods.")
                if greet_gain:
                    line += f"\n\n(Friendship with {fairy_name} begins — +{greet_gain}.)"
            social_choices, pub = _social_menu_choices(d, fairy_id)
            choices = social_choices
            await _send_line(
                send, session, fairy_name, fairy_id, line,
                choices=choices, friend=pub, page=page, gained=greet_gain,
            )
            return True

        friend = _friend_payload(d, fairy_id)
        await _send_line(
            send, session, fairy_name, fairy_id, line or "",
            choices=choices, quest=quest_payload, friend=friend, page=page,
            gained=greet_gain,
        )
        return True

    # MOONPETAL_CHOICE
    choice = int(msg.get("choice") or 0)
    d = FF.load(conn, session.player_id)
    menu = str(msg.get("menu") or "")

    # Compliment submenu
    if menu == "compliments":
        comps = FF.COMPLIMENTS.get(fairy_id) or []
        if choice < 0 or choice >= len(comps):
            social_choices, pub = _social_menu_choices(d, fairy_id)
            await _send_line(
                send, session, fairy_name, fairy_id,
                "Another time, then.", choices=social_choices, friend=pub, page="greeting",
            )
            return True
        cid = comps[choice][0]
        d, gained, line = FF.apply_compliment(conn, session.player_id, fairy_id, cid)
        friend = _friend_payload(d, fairy_id)
        await _send_line(
            send, session, fairy_name, fairy_id, line,
            choices=["Offer another compliment…", "Ask something else", "Leave"],
            friend=friend, page="social", gained=gained,
        )
        return True

    # After a topic / compliment / secret beat
    if menu == "social":
        # 0 compliment submenu · 1 ask something else · 2 leave
        if choice == 0:
            comps = FF.COMPLIMENTS.get(fairy_id) or []
            done = set((d.get("compliments_done") or {}).get(fairy_id) or [])
            labels = [f"{FF._compliment_label(cid)}{' ✓' if cid in done else ''}" for cid, _ in comps]
            labels.append("Back")
            await _send_line(
                send, session, fairy_name, fairy_id,
                "Choose your words carefully. Fairies remember the first time you mean them.",
                choices=labels, friend=_friend_payload(d, fairy_id), page="compliments",
            )
            return True
        if choice == 1:
            social_choices, pub = _social_menu_choices(d, fairy_id)
            await _send_line(
                send, session, fairy_name, fairy_id,
                f"{fairy_name} waits, patient as moonlight.",
                choices=social_choices, friend=pub, page="greeting",
            )
            return True
        await _send_line(
            send, session, fairy_name, fairy_id, "Safe paths.",
            choices=[], close=True, friend=_friend_payload(d, fairy_id),
        )
        return True

    if menu == "secret":
        await _send_line(
            send, session, fairy_name, fairy_id,
            "The roots will know you when the time comes.",
            choices=[], close=True, friend=_friend_payload(d, fairy_id),
        )
        return True

    if offer and offer.get("state") == "offerable":
        if choice == 0:
            await srv.handle_quest_accept(session, {"quest_id": offer["quest_id"]})
            await _send_line(
                send, session, fairy_name, fairy_id,
                f"Accepted: {offer['name']}. {offer.get('description') or ''}",
                choices=[], close=True, friend=_friend_payload(d, fairy_id),
            )
            return True
        # "Not now — just talk"
        social_choices, pub = _social_menu_choices(d, fairy_id)
        await _send_line(
            send, session, fairy_name, fairy_id,
            f"{fairy_name} nods. \"Talk, then. The task will wait.\"",
            choices=social_choices, friend=pub, page="greeting",
        )
        return True

    if step_hit:
        qid, qdef, prog, step = step_hit
        if choice == 0:
            before = prog.get("status")
            quest_steps.on_talk(session, fairy_id)
            prog = session.quests.get(qid) or prog
            if prog.get("status") == "ready" and (
                step.get("kind") == "deliver" or before == "ready" or qdef.get("giver") == fairy_id
            ):
                await srv.handle_quest_turnin(session, {"quest_id": qid})
                await _send_line(
                    send, session, fairy_name, fairy_id,
                    "The house remembers your help.",
                    choices=[], close=True, friend=_friend_payload(d, fairy_id),
                )
            else:
                await srv.send_quest_log(session)
                await _send_line(
                    send, session, fairy_name, fairy_id,
                    quest_steps.objective_text(qdef, prog, session),
                    choices=[], close=True, friend=_friend_payload(d, fairy_id),
                )
            return True
        if choice == 1:
            social_choices, pub = _social_menu_choices(d, fairy_id)
            await _send_line(
                send, session, fairy_name, fairy_id,
                f"{fairy_name} sets the task aside for a moment.",
                choices=social_choices, friend=pub, page="greeting",
            )
            return True
        await _send_line(
            send, session, fairy_name, fairy_id, "Safe paths.",
            choices=[], close=True, friend=_friend_payload(d, fairy_id),
        )
        return True

    # Greeting social menu choices
    # 0-3 topics, 4 compliment menu, maybe secret, leave last
    pub = FF.public_state(d, fairy_id)
    topic_ids = list(FF.TOPICS)
    n_topics = len(topic_ids)
    idx_comp = n_topics
    has_secret = bool(pub.get("secret_unlocked")) or int(pub.get("value") or 0) >= 40
    idx_secret = n_topics + 1 if has_secret else None
    idx_leave = n_topics + (2 if has_secret else 1)

    if choice == idx_leave or choice < 0:
        await _send_line(
            send, session, fairy_name, fairy_id, "Safe paths.",
            choices=[], close=True, friend=pub,
        )
        return True

    if choice == idx_comp:
        comps = FF.COMPLIMENTS.get(fairy_id) or []
        done = set(pub.get("compliments_done") or [])
        labels = []
        for cid, _line in comps:
            mark = " ✓" if cid in done else ""
            labels.append(f"{FF._compliment_label(cid)}{mark}")
        labels.append("Back")
        await _send_line(
            send, session, fairy_name, fairy_id,
            "Choose your words carefully. Fairies remember the first time you mean them.",
            choices=labels, friend=pub, page="compliments",
        )
        return True

    if idx_secret is not None and choice == idx_secret:
        line = FF.secret_line(d)
        if d.get("secret_unlocked") or FF.all_maxed(d):
            d = FF.mark_secret_told(conn, session.player_id)
            pub = FF.public_state(d, fairy_id)
        await _send_line(
            send, session, fairy_name, fairy_id, line,
            choices=["I will remember.", "Leave"],
            friend=pub, page="secret",
        )
        return True

    if 0 <= choice < n_topics:
        tid = topic_ids[choice]
        d, gained, line = FF.apply_topic(conn, session.player_id, fairy_id, tid)
        pub = FF.public_state(d, fairy_id)
        await _send_line(
            send, session, fairy_name, fairy_id, line,
            choices=["Offer a compliment…", "Ask something else", "Leave"],
            friend=pub, page="social", gained=gained,
        )
        return True

    await _send_line(
        send, session, fairy_name, fairy_id, "Safe paths.",
        choices=[], close=True, friend=pub,
    )
    return True
