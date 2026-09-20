"""
SQLite persistence layer. Handles accounts, character stats, inventory,
equipment and quest progress. This is a small prototype: passwords are
hashed with sha256+salt, which is NOT production-grade security, just a
sanity check against trivial account theft in a v0.1 prototype.
"""
import sqlite3
import hashlib
import os
import time

from content import STARTER_INVENTORY, XP_SKILLS
from world_map import SPAWN_POINT
import combat

DB_PATH = os.path.join(os.path.dirname(__file__), "world.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    char_name TEXT NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    hp INTEGER NOT NULL DEFAULT 10,
    attack_xp INTEGER NOT NULL DEFAULT 388,   -- level 5
    strength_xp INTEGER NOT NULL DEFAULT 388,
    defence_xp INTEGER NOT NULL DEFAULT 388,
    hitpoints_xp INTEGER NOT NULL DEFAULT 1154,
    woodcutting_xp INTEGER NOT NULL DEFAULT 0,
    mining_xp INTEGER NOT NULL DEFAULT 0,
    fishing_xp INTEGER NOT NULL DEFAULT 0,
    cooking_xp INTEGER NOT NULL DEFAULT 0,
    firemaking_xp INTEGER NOT NULL DEFAULT 0,
    smithing_xp INTEGER NOT NULL DEFAULT 0,
    karma_xp INTEGER NOT NULL DEFAULT 0,
    coins INTEGER NOT NULL DEFAULT 0,
    equip_weapon TEXT,
    equip_shield TEXT,
    equip_body TEXT,
    equip_legs TEXT,
    equip_helmet TEXT,
    auto_pickup_items INTEGER NOT NULL DEFAULT 0,
    stats_allocated INTEGER NOT NULL DEFAULT 0,
    bank_coins INTEGER NOT NULL DEFAULT 0,
    active_pet TEXT,
    owned_pets TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    slot_index INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    UNIQUE(player_id, slot_index),
    FOREIGN KEY(player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS bank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    slot_index INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    UNIQUE(player_id, slot_index),
    FOREIGN KEY(player_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS quest_progress (
    player_id INTEGER NOT NULL,
    quest_id TEXT NOT NULL,
    status TEXT NOT NULL,      -- 'active' | 'complete'
    progress INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, quest_id),
    FOREIGN KEY(player_id) REFERENCES players(id)
);
"""

INVENTORY_SIZE = 24


def _hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(players)")}
        if "smithing_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN smithing_xp INTEGER NOT NULL DEFAULT 0"
            )
        if "equip_helmet" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN equip_helmet TEXT")
        if "auto_pickup_items" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN auto_pickup_items INTEGER NOT NULL DEFAULT 0"
            )
        if "stats_allocated" not in cols:
            # Existing characters already started — treat them as allocated.
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN stats_allocated INTEGER NOT NULL DEFAULT 1"
            )
        if "bank_coins" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN bank_coins INTEGER NOT NULL DEFAULT 0"
            )
        if "karma_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN karma_xp INTEGER NOT NULL DEFAULT 0"
            )
        if "active_pet" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN active_pet TEXT")
        if "owned_pets" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN owned_pets TEXT NOT NULL DEFAULT '[]'"
            )
        if "cooking_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN cooking_xp INTEGER NOT NULL DEFAULT 0"
            )
        if "firemaking_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN firemaking_xp INTEGER NOT NULL DEFAULT 0"
            )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS bank ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "player_id INTEGER NOT NULL,"
            "slot_index INTEGER NOT NULL,"
            "item_id TEXT NOT NULL,"
            "quantity INTEGER NOT NULL,"
            "UNIQUE(player_id, slot_index),"
            "FOREIGN KEY(player_id) REFERENCES players(id))"
        )

    # --- accounts ---------------------------------------------------------
    def get_player_by_username(self, username):
        cur = self.conn.execute("SELECT * FROM players WHERE username = ?", (username,))
        return cur.fetchone()

    def create_account(self, username, password, char_name):
        salt = os.urandom(8).hex()
        pw_hash = _hash_password(password, salt)
        x, y = SPAWN_POINT
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        # New characters begin at Attack/Strength/Defence 5, Hitpoints 10
        start_combat_xp = combat.xp_for_level(5)
        cur = self.conn.execute(
            "INSERT INTO players (username, password_hash, salt, char_name, x, y, "
            "attack_xp, strength_xp, defence_xp, "
            "created_at, last_login, stats_allocated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (username, pw_hash, salt, char_name, x, y,
             start_combat_xp, start_combat_xp, start_combat_xp, now, now),
        )
        self.conn.commit()
        player_id = cur.lastrowid
        for slot, (item_id, qty) in enumerate(STARTER_INVENTORY):
            self.add_item_to_slot(player_id, slot, item_id, qty)
        return self.get_player_by_id(player_id)

    def verify_login(self, username, password):
        row = self.get_player_by_username(username)
        if row is None:
            return None
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            return None
        self.conn.execute(
            "UPDATE players SET last_login = ? WHERE id = ?",
            (time.strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
        )
        self.conn.commit()
        return row

    def get_player_by_id(self, player_id):
        cur = self.conn.execute("SELECT * FROM players WHERE id = ?", (player_id,))
        return cur.fetchone()

    def save_player_position(self, player_id, x, y):
        self.conn.execute("UPDATE players SET x = ?, y = ? WHERE id = ?", (x, y, player_id))
        self.conn.commit()

    def save_player_stats(self, player_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [player_id]
        self.conn.execute(f"UPDATE players SET {cols} WHERE id = ?", vals)
        self.conn.commit()

    # --- inventory ----------------------------------------------------------
    def get_inventory(self, player_id):
        cur = self.conn.execute(
            "SELECT slot_index, item_id, quantity FROM inventory WHERE player_id = ? ORDER BY slot_index",
            (player_id,),
        )
        return {row["slot_index"]: {"item_id": row["item_id"], "qty": row["quantity"]} for row in cur.fetchall()}

    def add_item_to_slot(self, player_id, slot, item_id, qty):
        self.conn.execute(
            "INSERT OR REPLACE INTO inventory (player_id, slot_index, item_id, quantity) VALUES (?, ?, ?, ?)",
            (player_id, slot, item_id, qty),
        )
        self.conn.commit()

    def clear_slot(self, player_id, slot):
        self.conn.execute("DELETE FROM inventory WHERE player_id = ? AND slot_index = ?", (player_id, slot))
        self.conn.commit()

    def set_equipment(self, player_id, slot_name, item_id):
        col = f"equip_{slot_name}"
        self.conn.execute(f"UPDATE players SET {col} = ? WHERE id = ?", (item_id, player_id))
        self.conn.commit()

    # --- bank -------------------------------------------------------------
    def get_bank(self, player_id):
        cur = self.conn.execute(
            "SELECT slot_index, item_id, quantity FROM bank WHERE player_id = ? ORDER BY slot_index",
            (player_id,),
        )
        return {row["slot_index"]: {"item_id": row["item_id"], "qty": row["quantity"]} for row in cur.fetchall()}

    def set_bank_slot(self, player_id, slot, item_id, qty):
        self.conn.execute(
            "INSERT OR REPLACE INTO bank (player_id, slot_index, item_id, quantity) VALUES (?, ?, ?, ?)",
            (player_id, slot, item_id, qty),
        )
        self.conn.commit()

    def clear_bank_slot(self, player_id, slot):
        self.conn.execute("DELETE FROM bank WHERE player_id = ? AND slot_index = ?", (player_id, slot))
        self.conn.commit()

    # --- quests ---------------------------------------------------------
    def get_quest_progress(self, player_id):
        cur = self.conn.execute("SELECT quest_id, status, progress FROM quest_progress WHERE player_id = ?", (player_id,))
        return {row["quest_id"]: {"status": row["status"], "progress": row["progress"]} for row in cur.fetchall()}

    def set_quest_progress(self, player_id, quest_id, status, progress):
        self.conn.execute(
            "INSERT INTO quest_progress (player_id, quest_id, status, progress) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(player_id, quest_id) DO UPDATE SET status = excluded.status, progress = excluded.progress",
            (player_id, quest_id, status, progress),
        )
        self.conn.commit()

    def get_leaderboards(self, limit=5):
        """Top players per skill by XP, plus overall total level."""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(players)")}
        boards = {}
        for skill in XP_SKILLS:
            col = f"{skill}_xp"
            if col not in cols:
                boards[skill] = []
                continue
            rows = self.conn.execute(
                f"SELECT char_name, {col} AS xp FROM players "
                f"ORDER BY {col} DESC, char_name ASC LIMIT ?",
                (limit,),
            ).fetchall()
            boards[skill] = [
                {
                    "name": row["char_name"],
                    "xp": int(row["xp"] or 0),
                    "level": combat.level_from_xp(int(row["xp"] or 0)),
                }
                for row in rows
            ]

        # Overall total level = sum of all skill levels; XP = sum of skill XP
        xp_cols = [f"{s}_xp" for s in XP_SKILLS if f"{s}_xp" in cols]
        if xp_cols:
            select_cols = ", ".join(["char_name"] + xp_cols)
            rows = self.conn.execute(f"SELECT {select_cols} FROM players").fetchall()
            totals = []
            for row in rows:
                total_xp = 0
                total_level = 0
                for col in xp_cols:
                    xp = int(row[col] or 0)
                    total_xp += xp
                    total_level += combat.level_from_xp(xp)
                totals.append({
                    "name": row["char_name"],
                    "xp": total_xp,
                    "level": total_level,
                })
            totals.sort(key=lambda e: (-e["level"], -e["xp"], e["name"]))
            boards["total"] = totals[:limit]
        else:
            boards["total"] = []
        return boards
