"""Castle Realm sellers, deeds, and gate plaques.

Hire, placement, and vault options stay as the pack's placeholder lines.
Flag off: no sellers, no plaques, no deeds.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import feature_flags

WEEK = 7 * 24 * 3600
_ROOT = Path(__file__).resolve().parent.parent / "client" / "assets" / "castle_realm" / "owners"
_DATA = None
_WORLD = None


def enabled():
    return bool(feature_flags.USE_CASTLE_OWNERS)


def bind(world):
    global _WORLD
    _WORLD = world
    if enabled():
        ensure_schema(world.db.conn)
        install_items()
        claim_kings_castle(world.db.conn)


def load():
    global _DATA
    if _DATA is None:
        sellers = json.loads((_ROOT / "json" / "sellers.json").read_text(encoding="utf-8"))
        schema = json.loads((_ROOT / "json" / "ownership_schema.json").read_text(encoding="utf-8"))
        by_npc = {}
        by_castle = {}
        for seller in sellers["sellers"]:
            by_npc[seller["npc_id"]] = seller
            by_castle[seller["castle_id"]] = seller
        castles = {row["castle_id"]: row for row in schema["castles"]}
        _DATA = {"sellers": sellers, "schema": schema, "by_npc": by_npc, "by_castle": by_castle, "castles": castles}
    return _DATA


def sellers():
    if not enabled():
        return []
    return list(load()["by_npc"].values())


def seller_by_npc(npc_id):
    if not enabled():
        return None
    return load()["by_npc"].get(npc_id)


def seller_at(x, y):
    for seller in sellers():
        tile = seller["spawn"]["tile"]
        if int(tile[0]) == int(x) and int(tile[1]) == int(y):
            return seller
    return None


def is_seller(npc_id):
    return seller_by_npc(npc_id) is not None


def castle_row(castle_id):
    return load()["castles"].get(castle_id)


def claim_kings_castle(conn):
    """David already holds King's Castle. That keep charges no lease."""
    player = conn.execute(
        "SELECT id, char_name FROM players WHERE lower(username) = ?",
        ("david",),
    ).fetchone()
    if player is None:
        return
    player_id = int(player["id"])
    name = player["char_name"] or "David"
    existing = conn.execute(
        "SELECT owner_account_id FROM castle_ownership WHERE castle_id = 'king'"
    ).fetchone()
    if existing is not None and int(existing["owner_account_id"]) == player_id:
        return
    now = time.time()
    conn.execute(
        """INSERT INTO castle_ownership
           (castle_id, owner_account_id, owner_display_name, purchased_at, last_tax_paid_at, tax_weeks_owed)
           VALUES ('king', ?, ?, ?, ?, 0)
           ON CONFLICT(castle_id) DO UPDATE SET
             owner_account_id = excluded.owner_account_id,
             owner_display_name = excluded.owner_display_name,
             purchased_at = excluded.purchased_at,
             last_tax_paid_at = excluded.last_tax_paid_at,
             tax_weeks_owed = 0""",
        (player_id, name, now, now),
    )
    conn.commit()


def ensure_schema(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS castle_ownership (
            castle_id TEXT PRIMARY KEY,
            owner_account_id INTEGER,
            owner_display_name TEXT,
            purchased_at REAL,
            last_tax_paid_at REAL,
            tax_weeks_owed INTEGER DEFAULT 0
        )"""
    )
    conn.commit()


def install_items():
    if not enabled():
        return
    from content import ITEMS
    for row in load()["schema"]["deed_items"]:
        ITEMS.setdefault(row["item_id"], {
            "name": row["name"],
            "examine": row["examine"],
            "tradeable": False,
            "sellable": False,
            "bankable": True,
            "stackable": False,
        })


def owners(conn):
    rows = conn.execute(
        "SELECT castle_id, owner_account_id, owner_display_name, purchased_at, last_tax_paid_at, tax_weeks_owed FROM castle_ownership"
    ).fetchall()
    return {
        row[0]: {
            "owner_id": row[1],
            "owner_name": row[2],
            "purchased_at": row[3],
            "last_tax_paid_at": row[4],
            "tax_weeks_owed": int(row[5] or 0),
        }
        for row in rows
    }


def plaque_states(conn):
    """Vacant plaques say For Sale. Owned plaques show the owner's name."""
    if not enabled():
        return []
    owned = owners(conn) if conn is not None else {}
    out = []
    for castle_id, row in load()["castles"].items():
        plaque = row["plaque"]
        owner = owned.get(castle_id)
        vacant = owner is None
        out.append({
            "castle_id": castle_id,
            "x": int(plaque["tile"][0]),
            "y": int(plaque["tile"][1]),
            "vacant": vacant,
            "title": plaque["vacant_text"] if vacant else (owner["owner_name"] or "Owner"),
            "subtitle": plaque["subtitle_vacant"] if vacant else plaque["subtitle_owned"],
            "sprite": plaque["sprite_vacant"] if vacant else plaque["sprite_owned_example"],
        })
    return out


def _on_realm(session):
    dungeon = getattr(session, "dungeon", None) or {}
    return dungeon.get("id") == "castle_realm" and dungeon.get("plane") == "realm"


def _near(session, seller):
    tile = seller["spawn"]["tile"]
    return max(abs(session.x - int(tile[0])), abs(session.y - int(tile[1]))) <= 1


def _node_payload(seller, node_id):
    node = seller["dialogue"][node_id]
    options = [{"id": opt["id"], "label": opt["label"]} for opt in node.get("options") or []]
    text = node.get("npc_text") or ""
    if seller.get("castle_id") == "king" and node_id == "hire_placeholder":
        text = (
            "The knights of King's Castle already serve their lord. "
            "There is no hire cost and no weekly wage."
        )
    elif seller.get("castle_id") == "king" and node_id == "info":
        text = "King's Castle asks no weekly lease. Its knights serve without a wage."
    return {
        "node": node_id,
        "npc_text": text,
        "options": options,
        "end": bool(node.get("end")),
    }


async def _send(ws, *args, **kwargs):
    import sys
    fn = getattr(sys.modules.get("__main__"), "send", None)
    if fn is None:
        import server
        fn = server.send
    await fn(ws, *args, **kwargs)


async def send_state(session):
    if not enabled() or _WORLD is None or not _on_realm(session):
        return
    await _send(session.ws, "CASTLE_OWNERS", plaques=plaque_states(_WORLD.db.conn))


async def broadcast():
    if not enabled() or _WORLD is None:
        return
    for session in list(_WORLD.sessions.values()):
        try:
            await send_state(session)
        except Exception:
            pass


async def open_talk(session, npc_id):
    seller = seller_by_npc(npc_id)
    if seller is None or not _on_realm(session) or not _near(session, seller):
        await _send(session.ws, "ERROR", message="You're too far away to talk to them.")
        return
    await _ensure_deed(session, seller)
    castle = _node_payload(seller, "root")
    await _send(
        session.ws, "DIALOGUE",
        npc_id=npc_id, npc_name=seller["display_name"], lines=[castle["npc_text"]],
        castle=castle,
    )


async def _ensure_deed(session, seller):
    """If the pack was full at purchase, hand over the recorded deed once there is room."""
    if _WORLD is None:
        return
    castle_id = seller["castle_id"]
    owned = owners(_WORLD.db.conn).get(castle_id)
    if not owned or owned["owner_id"] != session.player_id:
        return
    deed = castle_row(castle_id)["deed_item_id"]
    if _WORLD.count_item(session, deed) > 0:
        return
    if _WORLD.add_item_to_inventory(session, deed, 1):
        await _send(session.ws, "PLAYER_UPDATE", player=session.full_state())
        await _send(session.ws, "CHAT_MSG", **{
            "from": seller["display_name"],
            "text": "Here is the deed that was waiting for a free space in your pack.",
        })


async def choose(session, npc_id, node_id, option_id):
    seller = seller_by_npc(npc_id)
    if seller is None or not _on_realm(session) or not _near(session, seller):
        await _send(session.ws, "ERROR", message="You're too far away to talk to them.")
        return
    node = (seller.get("dialogue") or {}).get(node_id) or {}
    option = next((opt for opt in node.get("options") or [] if opt.get("id") == option_id), None)
    if option is None:
        return
    if option.get("action") == "BUY_CASTLE":
        node_id = await buy(session, seller)
    else:
        node_id = option.get("goto") or "root"
    if node_id not in seller["dialogue"]:
        node_id = "root"
    castle = _node_payload(seller, node_id)
    await _send(
        session.ws, "DIALOGUE",
        npc_id=npc_id, npc_name=seller["display_name"], lines=[castle["npc_text"]],
        castle=castle,
    )


def can_buy(session, castle_id):
    row = castle_row(castle_id)
    if row is None or _WORLD is None:
        return "missing"
    owned = owners(_WORLD.db.conn).get(castle_id)
    if owned and owned["owner_id"] == session.player_id:
        return "already_yours"
    if owned:
        return "owned"
    if int(session.bank_coins) < int(row["deed_price"]):
        return "funds"
    return "ok"


async def buy(session, seller):
    castle_id = seller["castle_id"]
    reason = can_buy(session, castle_id)
    if reason == "already_yours":
        return "buy_fail_already_yours"
    if reason == "owned":
        return "buy_fail_owned"
    if reason != "ok":
        return "buy_fail_funds"
    row = castle_row(castle_id)
    price = int(row["deed_price"])
    session.bank_coins -= price
    _WORLD.db.save_player_stats(session.player_id, bank_coins=session.bank_coins)
    now = time.time()
    name = getattr(session, "char_name", None) or "Owner"
    conn = _WORLD.db.conn
    conn.execute(
        """INSERT INTO castle_ownership
           (castle_id, owner_account_id, owner_display_name, purchased_at, last_tax_paid_at, tax_weeks_owed)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (castle_id, session.player_id, name, now, now),
    )
    conn.commit()
    install_items()
    deed = row["deed_item_id"]
    if not _WORLD.add_item_to_inventory(session, deed, 1):
        await _send(session.ws, "CHAT_MSG", **{
            "from": seller["display_name"],
            "text": "Your pack is full. The deed is recorded on the gate plaque; make a space and speak to me again.",
        })
    await _send(session.ws, "PLAYER_UPDATE", player=session.full_state())
    await _send(session.ws, "CHAT_MSG", **{
        "from": seller["display_name"],
        "text": f"You are now the lord of {row['display_name']}.",
    })
    await broadcast()
    return "buy_success"


async def settle_taxes(session, quiet=False):
    """Debit one due week from the bank. Unpaid weeks are recorded, never evict."""
    if not enabled() or _WORLD is None:
        return
    conn = _WORLD.db.conn
    now = time.time()
    changed = False
    for castle_id, owner in list(owners(conn).items()):
        if owner["owner_id"] != session.player_id:
            continue
        row = castle_row(castle_id)
        if row is None or castle_id == "king":
            continue
        last = float(owner["last_tax_paid_at"] or owner["purchased_at"] or now)
        if now < last + WEEK:
            continue
        tax = int(row["weekly_tax"])
        if int(session.bank_coins) >= tax:
            session.bank_coins -= tax
            _WORLD.db.save_player_stats(session.player_id, bank_coins=session.bank_coins)
            conn.execute(
                "UPDATE castle_ownership SET last_tax_paid_at = ?, tax_weeks_owed = 0 WHERE castle_id = ?",
                (last + WEEK, castle_id),
            )
            if not quiet:
                await _send(session.ws, "CHAT_MSG", **{
                    "from": "Castle Realm",
                    "text": f"Weekly upkeep of {tax:,} coins leaves your bank for {row['display_name']}.",
                })
        else:
            conn.execute(
                """UPDATE castle_ownership
                   SET tax_weeks_owed = tax_weeks_owed + 1, last_tax_paid_at = ?
                   WHERE castle_id = ?""",
                (last + WEEK, castle_id),
            )
            if not quiet:
                await _send(session.ws, "CHAT_MSG", **{
                    "from": "Castle Realm",
                    "text": f"{row['display_name']} is a week behind on its tax. The vault stays locked.",
                })
        changed = True
    if changed:
        conn.commit()


async def on_login(session):
    if not enabled() or _WORLD is None:
        return
    claim_kings_castle(_WORLD.db.conn)
    if (getattr(session, "username", "") or "").strip().lower() == "david":
        seller = load()["by_castle"].get("king")
        if seller:
            await _ensure_deed(session, seller)
    await settle_taxes(session, quiet=False)


async def tick_taxes():
    if not enabled() or _WORLD is None:
        return
    for session in list(_WORLD.sessions.values()):
        try:
            await settle_taxes(session, quiet=True)
        except Exception:
            pass
