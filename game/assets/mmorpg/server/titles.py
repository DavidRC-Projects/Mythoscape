"""Earned name titles the player can choose to display (or hide).

Nameplates used to always append sewer / milestone titles, which made names
long. Players pick one earned title (or none) in Settings; noble prefix and
house suffix can also be toggled off.
"""
from __future__ import annotations

SEWER_TITLE_ID = "sewer_ratcatcher"
SEWER_TITLE_LABEL = "Ratcatcher"

# Endless Depths milestone floors → (id, display label).
ENDLESS_TITLES = {
    10: ("endless_10", "Depthseeker"),
    25: ("endless_25", "Abyss Walker"),
    50: ("endless_50", "Pitforged"),
    75: ("endless_75", "Night Delver"),
    100: ("endless_100", "Endless Adept"),
    150: ("endless_150", "Mythbound"),
    200: ("endless_200", "Lord of Depths"),
}


def ensure_schema(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
    if "active_title" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN active_title TEXT NOT NULL DEFAULT ''")
        # Preserve the old always-on Ratcatcher look for anyone who already earned it.
        try:
            conn.execute(
                "UPDATE players SET active_title = ? WHERE id IN "
                "(SELECT player_id FROM sewer_tutorial WHERE title != '' AND title IS NOT NULL)",
                (SEWER_TITLE_ID,),
            )
        except Exception:
            pass
    if "show_noble_prefix" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN show_noble_prefix INTEGER NOT NULL DEFAULT 1"
        )
    if "show_house_suffix" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN show_house_suffix INTEGER NOT NULL DEFAULT 1"
        )
    conn.commit()


def load(session):
    """Cache title prefs on the session from the players row."""
    srv = _srv()
    try:
        row = srv.WORLD.db.get_player_by_id(session.player_id)
    except Exception:
        row = None
    if row is None:
        session.active_title = ""
        session.show_noble_prefix = True
        session.show_house_suffix = True
        return
    keys = row.keys()
    session.active_title = (row["active_title"] if "active_title" in keys else "") or ""
    session.show_noble_prefix = bool(
        int(row["show_noble_prefix"]) if "show_noble_prefix" in keys else 1
    )
    session.show_house_suffix = bool(
        int(row["show_house_suffix"]) if "show_house_suffix" in keys else 1
    )


def _srv():
    import server
    return server


def earned(session) -> list[dict]:
    """Titles this character has unlocked, oldest-first-ish."""
    out = []
    # Sewer tutorial.
    try:
        import sewer_tutorial
        label = sewer_tutorial.title_for(session)
        if label:
            out.append({
                "id": SEWER_TITLE_ID,
                "label": label or SEWER_TITLE_LABEL,
                "source": "sewer",
            })
    except Exception:
        pass
    # Endless Depths milestones.
    try:
        import endless_depths as ED
        claimed = ED.milestones_claimed(session)
        for floor in ED.MILESTONES:
            if floor not in claimed:
                continue
            tid, label = ENDLESS_TITLES.get(floor, (f"endless_{floor}", f"Floor {floor}"))
            out.append({"id": tid, "label": label, "source": "endless", "floor": floor})
    except Exception:
        pass
    return out


def _valid_ids(session) -> set[str]:
    return {t["id"] for t in earned(session)}


def active_id(session) -> str:
    if not hasattr(session, "active_title"):
        load(session)
    tid = str(getattr(session, "active_title", "") or "")
    if tid and tid not in _valid_ids(session):
        # Earned list changed (or bad save) — clear quietly.
        return ""
    return tid


def active_label(session) -> str:
    tid = active_id(session)
    if not tid:
        return ""
    for t in earned(session):
        if t["id"] == tid:
            return t["label"]
    return ""


def show_noble(session) -> bool:
    if not hasattr(session, "show_noble_prefix"):
        load(session)
    return bool(getattr(session, "show_noble_prefix", True))


def show_house(session) -> bool:
    if not hasattr(session, "show_house_suffix"):
        load(session)
    return bool(getattr(session, "show_house_suffix", True))


def set_active(session, title_id) -> tuple[bool, str]:
    """Equip a title id, or '' / 'none' to clear. Returns (ok, chat)."""
    tid = str(title_id or "").strip()
    if tid.lower() in ("", "none", "off", "clear"):
        tid = ""
    elif tid not in _valid_ids(session):
        return False, "You have not earned that title."
    session.active_title = tid
    _srv().WORLD.db.save_player_stats(session.player_id, active_title=tid)
    if not tid:
        return True, "Name title cleared."
    label = active_label(session)
    return True, f"Displaying title: the {label}."


def set_show_noble(session, on: bool) -> str:
    session.show_noble_prefix = bool(on)
    _srv().WORLD.db.save_player_stats(
        session.player_id, show_noble_prefix=1 if on else 0,
    )
    return f"Noble prefix: {'ON' if on else 'OFF'}."


def set_show_house(session, on: bool) -> str:
    session.show_house_suffix = bool(on)
    _srv().WORLD.db.save_player_stats(
        session.player_id, show_house_suffix=1 if on else 0,
    )
    return f"House suffix: {'ON' if on else 'OFF'}."


def unlock_chat(label: str) -> str:
    return f"New title unlocked: {label}. Choose it in Settings."


def public_payload(session) -> dict:
    return {
        "active_title": active_id(session),
        "title_line": active_label(session),
        "titles": earned(session),
        "show_noble_prefix": show_noble(session),
        "show_house_suffix": show_house(session),
    }
