"""Personal noble houses (player-owned), separate from kingdom pledge factions.

David's account is seeded with House of the Creator and a random heraldic banner.
"""
from __future__ import annotations

import json
import random
import time

CREATOR_USERNAME = "david"
CREATOR_HOUSE_NAME = "House of the Creator"

# Heraldic building blocks — deterministic from banner_seed.
_FIELD_COLORS = (
    (28, 52, 98),    # deep azure
    (92, 22, 28),    # gules
    (18, 72, 42),    # vert
    (48, 36, 72),    # purpure
    (22, 24, 30),    # sable
    (180, 150, 70),  # or (muted)
    (200, 200, 210), # argent
    (110, 58, 28),   # tenne
)
_CHARGE_COLORS = (
    (230, 210, 120),
    (240, 240, 245),
    (30, 30, 36),
    (210, 70, 70),
    (90, 170, 230),
    (120, 200, 130),
)
_CHARGES = (
    "lion", "wolf", "stag", "eagle", "dragon",
    "sword", "tower", "tree", "crown", "star",
    "sun", "moon", "rose", "anchor", "hammer",
)
_PARTITIONS = ("plain", "per_pale", "per_fess", "quarterly", "bend")


def ensure_schema(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS player_houses ("
        "player_id INTEGER PRIMARY KEY,"
        "name TEXT NOT NULL,"
        "banner_seed INTEGER NOT NULL,"
        "banner_json TEXT,"
        "created_at REAL"
        ")"
    )
    conn.commit()


def banner_from_seed(seed: int) -> dict:
    """Procedural coat of arms from a stable integer seed."""
    rng = random.Random(int(seed) & 0xFFFFFFFF)
    primary = rng.choice(_FIELD_COLORS)
    secondary = rng.choice(_FIELD_COLORS)
    # Avoid identical field halves.
    if secondary == primary:
        secondary = rng.choice(_FIELD_COLORS)
    charge_col = rng.choice(_CHARGE_COLORS)
    return {
        "seed": int(seed),
        "partition": rng.choice(_PARTITIONS),
        "primary": list(primary),
        "secondary": list(secondary),
        "charge": rng.choice(_CHARGES),
        "charge_color": list(charge_col),
        "rim": [210, 180, 90],
    }


def _row(conn, player_id: int):
    return conn.execute(
        "SELECT player_id, name, banner_seed, banner_json FROM player_houses WHERE player_id = ?",
        (int(player_id),),
    ).fetchone()


def get_house(conn, player_id: int) -> dict | None:
    row = _row(conn, player_id)
    if not row:
        return None
    banner = None
    raw = row["banner_json"] if "banner_json" in row.keys() else None
    if raw:
        try:
            banner = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            banner = None
    if not isinstance(banner, dict):
        banner = banner_from_seed(int(row["banner_seed"]))
    return {
        "name": str(row["name"]),
        "banner_seed": int(row["banner_seed"]),
        "banner": banner,
    }


def public(conn, player_id: int) -> dict | None:
    h = get_house(conn, player_id)
    if not h:
        return None
    return {"name": h["name"], "banner": h["banner"], "banner_seed": h["banner_seed"]}


def suffix_for(conn, player_id: int) -> str:
    """Text nameplate suffix for a personal house.

    Personal houses are shown as a crest beside the nameplate, not as a long
    'of House …' string — so this always returns empty when a house exists.
    Callers use get_house / public for the crest payload instead.
    """
    return ""


def has_house(conn, player_id: int) -> bool:
    return _row(conn, player_id) is not None


def create_house(conn, player_id: int, name: str, seed: int | None = None) -> dict:
    seed = int(seed if seed is not None else random.randint(1, 2_000_000_000))
    banner = banner_from_seed(seed)
    conn.execute(
        "INSERT OR REPLACE INTO player_houses (player_id, name, banner_seed, banner_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (int(player_id), str(name)[:64], seed, json.dumps(banner), time.time()),
    )
    conn.commit()
    return get_house(conn, player_id)


def ensure_creator_house(conn, player_id: int, username: str) -> dict | None:
    """Grant House of the Creator to account david if missing."""
    if str(username or "").lower() != CREATOR_USERNAME:
        return get_house(conn, player_id)
    existing = get_house(conn, player_id)
    if existing:
        # Keep the name locked to the Creator house for this account.
        if existing["name"] != CREATOR_HOUSE_NAME:
            conn.execute(
                "UPDATE player_houses SET name = ? WHERE player_id = ?",
                (CREATOR_HOUSE_NAME, int(player_id)),
            )
            conn.commit()
            return get_house(conn, player_id)
        return existing
    return create_house(conn, player_id, CREATOR_HOUSE_NAME)


def reroll_banner(conn, player_id: int) -> tuple[bool, str, dict | None]:
    """Customise: roll a new random banner for the player's personal house."""
    h = get_house(conn, player_id)
    if not h:
        return False, "You have no personal house yet.", None
    seed = random.randint(1, 2_000_000_000)
    banner = banner_from_seed(seed)
    conn.execute(
        "UPDATE player_houses SET banner_seed = ?, banner_json = ? WHERE player_id = ?",
        (seed, json.dumps(banner), int(player_id)),
    )
    conn.commit()
    h = get_house(conn, player_id)
    return True, f"{h['name']}'s banner is remade.", h
