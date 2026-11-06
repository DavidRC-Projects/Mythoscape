"""War for the Crown — verbose in-game guide (Royal Herald + Seraphine walk).

The Royal Herald stands outside the King's Castle approach (King's Realm portal)
and teaches the monthly war. Seraphine starts in the village and walks the player
to him once the first-5-minutes tour is finished.
"""
from __future__ import annotations

# Progress on players.crown_guide:
#   0   = available (offer not accepted)
#   1   = intro accepted — walk to the Herald
#   2   = arrived — talk to the Herald
#   100 = finished
#   101 = skipped
CROWN_GUIDE_WALK = 1
CROWN_GUIDE_TALK = 2
CROWN_GUIDE_DONE = 100
CROWN_GUIDE_SKIPPED = 101
CROWN_GUIDE_FINISHED = (CROWN_GUIDE_DONE, CROWN_GUIDE_SKIPPED)

# Must match content.NPCS royal_herald overworld stand (outside King's Realm portal).
HERALD_ID = "royal_herald"
HERALD_OUTSIDE = (12, 21)

GUIDE_OPTION = {"id": "siege_guide", "label": "How the War for the Crown works"}


def ensure_schema(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
    if "crown_guide" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN crown_guide INTEGER NOT NULL DEFAULT 0"
        )
        # Veterans who already finished Seraphine's first tour may take this next;
        # leave at 0 so the village offer can appear.
        conn.commit()


def guide_pages():
    """Verbose Herald pages — short enough for dialogue, full enough to play."""
    return [
        [
            "I am the Royal Herald. I stand here outside the King's Castle approach "
            "so every traveller may learn how the throne is won.",
            "The old solo Crown Challenge is retired. The crown now falls through the "
            "War for the Crown — a monthly guild war for Crownfall Castle.",
        ],
        [
            "Where to begin: join or create a guild. Only a guild Leader can register "
            "a side. Talk to me, use /siege status, or open the War Council on the world map (M).",
            "A gold war chip appears in the King's Realm while a war is open — click it for the board.",
        ],
        [
            "The month builds toward Day 30 — The Siege of Crownfall.",
            "Days 1–7: recruitment and diplomacy. 8–14: gather wood, stone, ore. "
            "15–21: craft engines and fortifications. 22–27: alliances and scouting. "
            "28–29: registration. Day 30: the assault.",
            "Contribute all month — deposits into the war storehouse earn recognition even if you never swing a blade.",
        ],
        [
            "Registration: Leaders /siege register attack or defend. Ally smaller guilds "
            "with /siege ally <guild>. Confirm within 48 hours with 20+ humans, or the next guild may take your slot.",
            "Attack Leaders set a published start time with /siege when <1–72>h "
            "(shown in UTC for every time zone) or open early with /siege begin.",
        ],
        [
            "The war storehouse: /siege deposit <item> <qty> turns logs, ore, coal, and bars "
            "into timber, ore, stone, and bars. Deposits cannot be withdrawn for personal use.",
            "The lead Leader allocates budgets: /siege alloc rams=40 ladders=25 barricades=20 reserve=15. "
            "Craft engines with /siege craft ram|ladder|tower|catapult|barricade.",
        ],
        [
            "Assault — three hours. Attackers fire engines at the Outer Gate, walls, Watchtower, "
            "Armoury, Supply Depot, and Royal Keep. Destroyed gates and walls open walkable breaches.",
            "Capture in order: Outer Yard → Gatehouse (needs a breach) → Courtyard → Throne Room. "
            "Hold the Throne Room to claim Crownfall. Defenders win if the clock runs out.",
        ],
        [
            "Last Stand: when the keep falls, the Royal Guard fortifies the Throne Room. "
            "The Monarch or Marshal may appoint up to four players as Royal Guard "
            "(/siege royalguard <name>). While they stand in the chamber, they protect the King.",
            "If the King falls in battle the castle still stands — attackers must take the throne.",
        ],
        [
            "Roster: 20–100 fighters a side, mercenaries at most 40%. Contracts lock when the assault begins. "
            "Death eliminates you from this siege only — respawn outside, watch, then /siege report after Crownfall.",
            "Victor's heraldry flies over the King's Castle; Regal robes unlock at Mae's. "
            "Ask me any time for War for the Crown, storehouse, scout, or the battle report. Fare you well.",
        ],
    ]


def guide_dialogue_lines(page=0):
    pages = guide_pages()
    page = max(0, min(int(page), len(pages) - 1))
    lines = list(pages[page])
    lines.append(f"— Guide {page + 1}/{len(pages)} —")
    return lines, page


def guide_options(page=0):
    pages = guide_pages()
    page = max(0, min(int(page), len(pages) - 1))
    opts = []
    if page + 1 < len(pages):
        opts.append({"id": f"siege_guide_{page + 1}", "label": "Next"})
    else:
        opts.append({"id": "siege_guide_done", "label": "I understand"})
    if page > 0:
        opts.append({"id": f"siege_guide_{page - 1}", "label": "Back"})
    opts.append(GUIDE_OPTION)
    return opts


def mark_talked(conn, player_id, session=None):
    """Advance Seraphine's walk tour when the player finishes speaking to the Herald."""
    ensure_schema(conn)
    cur = 0
    if session is not None:
        cur = int(getattr(session, "crown_guide", 0) or 0)
    else:
        row = conn.execute(
            "SELECT crown_guide FROM players WHERE id = ?", (int(player_id),)
        ).fetchone()
        cur = int(row[0] or 0) if row else 0
    if cur == CROWN_GUIDE_TALK or cur == CROWN_GUIDE_WALK:
        conn.execute(
            "UPDATE players SET crown_guide = ? WHERE id = ?",
            (CROWN_GUIDE_DONE, int(player_id)),
        )
        conn.commit()
        if session is not None:
            session.crown_guide = CROWN_GUIDE_DONE
        return True
    return False


def seraphine_offer_lines():
    return [
        "Hello again, darling. The throne isn't won by a quiet stroll anymore.",
        "Walk with me to the Royal Herald — he waits outside the King's Castle approach, "
        "by the gold portal west of the wishing well.",
        "He'll teach you the War for the Crown: guilds, the storehouse, the siege, and Crownfall.",
    ]


def seraphine_walk_lines():
    return [
        "Follow the gold trail. The Herald stands outside the King's Realm portal — "
        "not inside the keep, right there on the road so travellers can't miss him.",
        "When you reach him, talk. I'll stay out of the way while he explains.",
    ]


def seraphine_talk_lines():
    return [
        "There he is — the Royal Herald, outside the castle approach.",
        "Click him and choose How the War for the Crown works. Listen to every page.",
    ]
