"""Short, consistent quest talk copy — one idea per beat for every quest."""


def _pretty(token):
    return str(token or "").replace("_", " ")


def _monster_label(qdef):
    n = int(qdef.get("count") or 1)
    name = _pretty(qdef.get("target"))
    if n == 1:
        return f"1 {name}"
    # Simple plural: rats, wolves, guards — avoid "skeletonss"
    if name.endswith("s"):
        return f"{n} {name}"
    if name.endswith("y") and name[-2:] not in ("ay", "ey", "oy", "uy"):
        return f"{n} {name[:-1]}ies"
    return f"{n} {name}s"


def offer_lines(qdef, quest_id=None):
    """Two short lines when a quest is offerable. Gift bag-full is handled by the caller."""
    qtype = qdef.get("type")
    if qtype == "gift":
        return [
            "Free kit when your bag has room.",
            "Bank a few items, then talk to me again.",
        ]
    if qtype == "kill":
        return [
            f"I need {_monster_label(qdef)} gone.",
            "Press Accept — follow the gold trail, then return here.",
        ]
    if qtype == "collect":
        n = int(qdef.get("count") or 1)
        item = _pretty(qdef.get("target"))
        need = f"{n} {item}" if n != 1 else item
        return [
            f"Bring me {need}.",
            "Press Accept — follow the gold trail, then come back.",
        ]
    if qtype == "collect_multi":
        bits = ", ".join(f"{qty} {_pretty(iid)}" for iid, qty in (qdef.get("targets") or {}).items())
        return [
            f"Bring me {bits}.",
            "Press Accept — follow the trail, then return.",
        ]
    if qtype == "find_npc":
        return [
            f"Find {_pretty(qdef.get('target')).title()} and speak to them.",
            "Press Accept — the gold trail points the way.",
        ]
    if qtype == "guild":
        return [
            "Create or join a guild, then /guild deposit any coins.",
            "Press Accept — return here when both steps are done.",
        ]
    if qtype == "oath":
        return [
            (qdef.get("description") or "Take the Royal Challenge.").split(":")[-1].strip(),
            "Press Accept if you swear the oath.",
        ]
    return [
        qdef.get("description") or "I have work for you.",
        "Press Accept to take this quest.",
    ]


def active_lines(qdef, objective=None):
    """While the quest is in progress — don't re-dump lore."""
    if objective:
        return [str(objective), "Follow the gold trail. Come back when you're done."]
    return ["Still going — follow the gold trail, then return here."]


def ready_lines(_qdef=None):
    return ["You're done — press Turn in below for your reward."]


def accept_chat(qdef, giver_name="Guide"):
    """One short chat line after Accept. Trail does the rest."""
    qtype = qdef.get("type")
    if qtype == "kill":
        text = f"Follow the gold trail. Defeat {_monster_label(qdef)}, then return."
    elif qtype == "collect":
        n = int(qdef.get("count") or 1)
        item = _pretty(qdef.get("target"))
        need = f"{n} {item}" if n != 1 else item
        text = f"Follow the gold trail. Collect {need}, then return."
    elif qtype == "collect_multi":
        bits = ", ".join(f"{qty} {_pretty(iid)}" for iid, qty in (qdef.get("targets") or {}).items())
        text = f"Follow the gold trail. Gather {bits}, then return."
    elif qtype == "find_npc":
        text = f"Follow the gold trail to {_pretty(qdef.get('target')).title()}, then return."
    elif qtype == "guild":
        text = "Join or create a guild, /guild deposit any coins, then return here."
    elif qtype == "oath":
        text = "The challenge is long — check your quest journal for the steps."
    else:
        text = "Follow the gold trail. Return here when finished."
    return giver_name, text
