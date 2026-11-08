"""Deliver one siege result into the game database.

This is the destination side of the siege outbox. It writes the throne row
and the King's Castle ownership row in a single transaction, then a receipt.
A retry of the same revision does nothing. It does not call ``throne._crown``
(that commits on its own and can roll the shared connection back). Gold,
noble rank, skills, and every castle other than ``king`` are not written.
"""
from __future__ import annotations

import json
import sqlite3
import time


ROYAL_CASTLE = "king"
RECEIPT = "kcs_throne_receipt"


class DestinationError(RuntimeError):
    pass


def deliver(conn, payload: dict) -> str:
    """Apply ``payload`` once. Returns 'applied' or 'already'.

    ``payload`` is the siege outbox body: rev, war_id, winner_side,
    monarch_player_id, owner_guild_id. The caller marks the outbox delivered
    only after this returns.
    """
    if conn is None:
        raise DestinationError("no game database")
    rev = int(payload["rev"])
    war_id = int(payload["war_id"])
    winner = str(payload.get("winner_side") or "")
    if winner not in ("attack", "defend"):
        raise DestinationError("result has no side")
    monarch = payload.get("monarch_player_id")
    monarch = int(monarch) if monarch not in (None, "") else None
    guild = payload.get("owner_guild_id")
    try:
        guild = int(guild) if guild not in (None, "") else None
    except (TypeError, ValueError):
        guild = None
    import castle_owners
    import throne
    throne.ensure_schema(conn)
    castle_owners.ensure_schema(conn)
    _ensure_receipt(conn)
    _ensure_title_column(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        seen = conn.execute(f"SELECT war_id, winner_side, monarch_player_id FROM {RECEIPT} WHERE rev=?",
                            (rev,)).fetchone()
        if seen is not None:
            if int(seen[0]) != war_id or seen[1] != winner or (
                    None if seen[2] is None else int(seen[2])) != monarch:
                raise DestinationError("this revision was already delivered for a different result")
            conn.commit()
            return "already"
        if winner == "attack" and monarch:
            _crown_and_castle(conn, monarch, guild, war_id)
        # A defence, or an attack with nobody to name, leaves the throne and
        # every castle as they are. The receipt still stops a later retry
        # from crowning someone else for this same result.
        conn.execute(
            f"INSERT INTO {RECEIPT}(rev, war_id, winner_side, monarch_player_id, payload_json, applied_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rev, war_id, winner, monarch, json.dumps(payload, sort_keys=True), time.time()))
        conn.commit()
        return "applied"
    except DestinationError:
        conn.rollback()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        raise DestinationError(str(exc)) from exc
    except Exception:
        conn.rollback()
        raise


def _ensure_receipt(conn) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {RECEIPT} ("
        "rev INTEGER PRIMARY KEY, war_id INTEGER NOT NULL, winner_side TEXT NOT NULL, "
        "monarch_player_id INTEGER, payload_json TEXT NOT NULL, applied_at REAL NOT NULL)")
    conn.commit()


def _ensure_title_column(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "royal_title" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN royal_title TEXT NULL")
        conn.commit()


def _crown_and_castle(conn, monarch: int, guild, war_id: int) -> None:
    """Same throne and castle rows the game already reads. One transaction."""
    row = conn.execute(
        "SELECT char_name FROM players WHERE id=?", (monarch,)).fetchone()
    if row is None:
        raise DestinationError("the claimant is not a character")
    name = row[0] or "Monarch"
    title = _title_for(conn, monarch)
    previous = conn.execute(
        "SELECT monarch_kind, monarch_player_id FROM throne WHERE id=1").fetchone()
    previous_text = "none"
    if previous is not None:
        previous_text = f"{previous[0]}:{previous[1]}"
    now = time.time()
    conn.execute(
        "UPDATE throne SET monarch_kind='player', monarch_player_id=?, since=?, path=?, "
        "old_king_state=CASE WHEN monarch_kind='npc' THEN 'reigning' ELSE old_king_state END "
        "WHERE id=1",
        (monarch, now, "siege"))
    conn.execute(
        "INSERT INTO throne_log(ts, event, player_id, detail) VALUES (?, 'crowned', ?, ?)",
        (now, monarch, f"siege war {war_id}; previous {previous_text}"))
    # One crown. This is the existing rule: royal_title, not noble_rank.
    conn.execute("UPDATE players SET royal_title=NULL WHERE royal_title IS NOT NULL")
    conn.execute("UPDATE players SET royal_title=? WHERE id=?", (title, monarch))
    conn.execute(
        "INSERT INTO castle_ownership"
        "(castle_id, owner_account_id, owner_display_name, purchased_at, last_tax_paid_at, tax_weeks_owed, guild_id) "
        "VALUES (?, ?, ?, ?, ?, 0, ?) "
        "ON CONFLICT(castle_id) DO UPDATE SET owner_account_id=excluded.owner_account_id, "
        "owner_display_name=excluded.owner_display_name, purchased_at=excluded.purchased_at, "
        "guild_id=excluded.guild_id",
        (ROYAL_CASTLE, monarch, name, now, now, guild))


def _title_for(conn, monarch: int) -> str:
    try:
        row = conn.execute("SELECT gender FROM players WHERE id=?", (monarch,)).fetchone()
    except sqlite3.Error:
        return "King"
    if row and str(row[0] or "").lower().startswith("f"):
        return "Queen"
    return "King"
