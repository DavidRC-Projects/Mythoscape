"""
SQLite persistence layer. Handles accounts, character stats, inventory,
equipment and quest progress.

Passwords use argon2id (argon2-cffi). Legacy SHA-256+salt hashes are
accepted once, then upgraded on successful login.
"""
import sqlite3
import hashlib
import hmac
import logging
import os
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from content import STARTER_INVENTORY, XP_SKILLS, INVENTORY_SIZE, ITEMS
from world_map import SPAWN_POINT
import combat

log = logging.getLogger("database")

DB_PATH = os.environ.get(
    "CROWNFALL_DB_PATH",
    os.path.join(os.path.dirname(__file__), "world.db"),
)

_HASHER = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)

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
    starter_tips_seen INTEGER NOT NULL DEFAULT 0,   -- first-session chat pointers
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
    fletching_xp INTEGER NOT NULL DEFAULT 0,
    archery_xp INTEGER NOT NULL DEFAULT 0,
    karma_xp INTEGER NOT NULL DEFAULT 0,
    coins INTEGER NOT NULL DEFAULT 0,
    equip_weapon TEXT,
    equip_shield TEXT,
    equip_body TEXT,
    equip_legs TEXT,
    equip_helmet TEXT,
    equip_amulet TEXT,
    equip_ring TEXT,
    equip_ammo TEXT,
    equip_tool TEXT,
    equip_tools TEXT NOT NULL DEFAULT '{}',
    auto_pickup_items INTEGER NOT NULL DEFAULT 0,
    stats_allocated INTEGER NOT NULL DEFAULT 0,
    bank_coins INTEGER NOT NULL DEFAULT 0,
    active_pet TEXT,
    owned_pets TEXT NOT NULL DEFAULT '[]',
    gender TEXT NOT NULL DEFAULT 'male',
    last_wish_date TEXT,
    created_at TEXT NOT NULL,
    last_login TEXT,
    appearance TEXT,
    owned_cosmetics TEXT NOT NULL DEFAULT '[]',
    hd_player INTEGER NOT NULL DEFAULT 1
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


def _hash_password_legacy(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _is_argon2_hash(stored: str) -> bool:
    return isinstance(stored, str) and stored.startswith("$argon2")


def hash_password(password: str) -> tuple[str, str]:
    """Return (password_hash, salt_column). Salt is embedded in argon2 hash."""
    return _HASHER.hash(password), "argon2"


def verify_password(password: str, stored_hash: str, salt: str) -> tuple[bool, bool]:
    """Return (ok, needs_rehash)."""
    if _is_argon2_hash(stored_hash):
        try:
            _HASHER.verify(stored_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False, False
        return True, _HASHER.check_needs_rehash(stored_hash)
    # Legacy SHA-256(salt + password)
    expected = _hash_password_legacy(password, salt or "")
    if not hmac.compare_digest(expected, stored_hash or ""):
        return False, False
    return True, True


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error:
            log.exception("Failed to enable SQLite WAL mode")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()
        self._harden_db_file()

    def _harden_db_file(self):
        """Restrict DB file permissions to owner read/write (Unix)."""
        try:
            if os.path.isfile(self.path):
                os.chmod(self.path, 0o600)
            for suffix in ("-wal", "-shm"):
                side = self.path + suffix
                if os.path.isfile(side):
                    os.chmod(side, 0o600)
        except OSError:
            pass

    def _migrate(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(players)")}
        if "starter_tips_seen" not in cols:
            # Existing characters have already had their first session.
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN starter_tips_seen INTEGER NOT NULL DEFAULT 1"
            )
        if "smithing_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN smithing_xp INTEGER NOT NULL DEFAULT 0"
            )
        if "equip_helmet" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN equip_helmet TEXT")
        if "equip_amulet" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN equip_amulet TEXT")
        if "equip_ring" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN equip_ring TEXT")
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
        if "gender" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN gender TEXT NOT NULL DEFAULT 'male'"
            )
        if "pickup_ignore" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN pickup_ignore TEXT NOT NULL DEFAULT '[]'"
            )
        if "last_wish_date" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN last_wish_date TEXT")
        if "fletching_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN fletching_xp INTEGER NOT NULL DEFAULT 0"
            )
        if "archery_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN archery_xp INTEGER NOT NULL DEFAULT 0"
            )
        if "equip_ammo" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN equip_ammo TEXT")
        if "equip_tool" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN equip_tool TEXT")
        if "equip_tools" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN equip_tools TEXT NOT NULL DEFAULT '{}'"
            )
        if "quiver_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN quiver_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "tip_box_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN tip_box_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "food_bag_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN food_bag_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "raw_bag_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN raw_bag_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "mining_bag_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN mining_bag_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "log_bag_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN log_bag_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "fletch_pouch_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN fletch_pouch_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "potion_pouch_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN potion_pouch_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "gem_bag_contents" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN gem_bag_contents TEXT NOT NULL DEFAULT '{}'"
            )
        if "knows_teleport" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN knows_teleport INTEGER NOT NULL DEFAULT 0"
            )
        if "teleport_marks" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN teleport_marks TEXT NOT NULL DEFAULT '[]'"
            )
        if "player_killer" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN player_killer INTEGER NOT NULL DEFAULT 0"
            )
        if "pk_kills" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN pk_kills INTEGER NOT NULL DEFAULT 0"
            )
        if "pk_locked_until" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN pk_locked_until REAL NOT NULL DEFAULT 0"
            )
        if "dungeon_resume" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN dungeon_resume TEXT NOT NULL DEFAULT ''")
        if "appearance" not in cols:
            self.conn.execute("ALTER TABLE players ADD COLUMN appearance TEXT")
            self._backfill_existing_looks()
        if "owned_cosmetics" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN owned_cosmetics TEXT NOT NULL DEFAULT '[]'"
            )
        if "hd_player" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN hd_player INTEGER NOT NULL DEFAULT 1"
            )
        if "saved_outfits" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN saved_outfits TEXT NOT NULL DEFAULT '[]'"
            )
        if "tax_notice_seen" not in cols:
            self.conn.execute(
                "ALTER TABLE players ADD COLUMN tax_notice_seen INTEGER NOT NULL DEFAULT 0"
            )
        import clans
        clans.ensure_tables(self.conn)
        import royal_treasury
        royal_treasury.ensure_schema(self.conn)
        import reputation
        reputation.ensure_schema(self.conn)
        import apprentice
        apprentice.ensure_schema(self.conn)
        import nobility
        nobility.ensure_schema(self.conn)
        import throne
        throne.ensure_schema(self.conn)
        import ruling
        ruling.ensure_schema(self.conn)
        import politics
        politics.ensure_schema(self.conn)
        import player_houses
        player_houses.ensure_schema(self.conn)
        import property as _property
        _property.ensure_schema(self.conn)
        import mercenaries
        mercenaries.ensure_schema(self.conn)
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

    def _backfill_existing_looks(self):
        """Characters already in the world keep a default look.

        A new account leaves appearance empty until the creator saves it.
        """
        import json
        rows = self.conn.execute(
            "SELECT id, gender FROM players WHERE appearance IS NULL AND stats_allocated = 1"
        ).fetchall()
        for row in rows:
            if row["gender"] == "female":
                look = {
                    "skin": "skin_base", "skin_tone": "tone_3", "hair": "hair_ponytail", "hair_colour": "chestnut",
                    "top": "top_linen_shirt", "bottom": "bottom_long_skirt", "shoes": "shoes_leather",
                    "outfit": None, "accessories": [],
                }
            else:
                look = {
                    "skin": "skin_base", "skin_tone": "tone_3", "hair": "hair_side_part", "hair_colour": "dark_brown",
                    "top": "top_linen_shirt", "bottom": "bottom_work_trousers", "shoes": "shoes_leather",
                    "outfit": None, "accessories": [],
                }
            self.conn.execute(
                "UPDATE players SET appearance = ? WHERE id = ?",
                (json.dumps(look), row["id"]),
            )
        if rows:
            self.conn.commit()

    def create_account(self, username, password, char_name, gender="male"):
        pw_hash, salt = hash_password(password)
        x, y = SPAWN_POINT
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        gender = "female" if str(gender).lower() == "female" else "male"
        # New characters begin at Attack/Strength/Defence 5, Hitpoints 10
        start_combat_xp = combat.xp_for_level(5)
        cur = self.conn.execute(
            "INSERT INTO players (username, password_hash, salt, char_name, x, y, "
            "attack_xp, strength_xp, defence_xp, "
            "created_at, last_login, stats_allocated, auto_pickup_items, gender) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)",
            (username, pw_hash, salt, char_name, x, y,
             start_combat_xp, start_combat_xp, start_combat_xp, now, now, gender),
        )
        self.conn.commit()
        player_id = cur.lastrowid
        # Starter gather tools go straight into per-skill tool slots (axe / pick / net),
        # so new players never have to equip them before chopping, mining or fishing.
        starter_tools = {
            "woodcutting": "bronze_axe",
            "mining": "bronze_pickaxe",
            "fishing": "small_fishing_net",
        }
        bag_i = 0
        for item_id, qty in STARTER_INVENTORY:
            skill = next((s for s, t in starter_tools.items() if t == item_id), None)
            if skill:
                continue
            self.add_item_to_slot(player_id, bag_i, item_id, qty)
            bag_i += 1
        self.set_equip_tools(player_id, starter_tools)
        # Legacy single column mirrors the pickaxe (common gather tool) for older readers.
        self.set_equipment(player_id, "tool", starter_tools["mining"])
        return self.get_player_by_id(player_id)

    def _rehash_password(self, player_id, password):
        pw_hash, salt = hash_password(password)
        self.conn.execute(
            "UPDATE players SET password_hash = ?, salt = ? WHERE id = ?",
            (pw_hash, salt, player_id),
        )

    def verify_login(self, username, password):
        row = self.get_player_by_username(username)
        if row is None:
            # Dummy verify to reduce timing oracle on missing users.
            try:
                _HASHER.hash("dummy-password-timing")
            except Exception:
                pass
            return None
        ok, needs_rehash = verify_password(password, row["password_hash"], row["salt"])
        if not ok:
            return None
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if needs_rehash:
            self._rehash_password(row["id"], password)
        self.conn.execute(
            "UPDATE players SET last_login = ? WHERE id = ?", (now, row["id"]),
        )
        self.conn.commit()
        # Return a row that reflects the write. Returning the pre-update row
        # left callers seeing a stale last_login, which is exactly what the
        # "is this their first session?" check reads.
        fresh = self.get_player_by_id(row["id"])
        return fresh if fresh is not None else row

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

    def get_equip_tools(self, player_id):
        """Per-skill gather tools: woodcutting / mining / fishing → item_id."""
        import json
        row = self.get_player_by_id(player_id)
        if row is None:
            return {}
        raw = row["equip_tools"] if "equip_tools" in row.keys() else "{}"
        try:
            data = json.loads(raw or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        # Migrate legacy single equip_tool into the matching skill once.
        legacy = row["equip_tool"] if "equip_tool" in row.keys() else None
        if legacy and not data:
            skill = (ITEMS.get(legacy) or {}).get("tool_for")
            if skill in ("woodcutting", "mining", "fishing"):
                data[skill] = legacy
                self.set_equip_tools(player_id, data)
        return {k: v for k, v in data.items() if k in ("woodcutting", "mining", "fishing") and v}

    def set_equip_tools(self, player_id, tools):
        import json
        clean = {k: v for k, v in (tools or {}).items()
                 if k in ("woodcutting", "mining", "fishing") and v}
        self.conn.execute(
            "UPDATE players SET equip_tools = ? WHERE id = ?",
            (json.dumps(clean), player_id),
        )
        # Keep equip_tool in sync (prefer mining, then woodcutting, then fishing).
        mirror = clean.get("mining") or clean.get("woodcutting") or clean.get("fishing")
        self.conn.execute(
            "UPDATE players SET equip_tool = ? WHERE id = ?", (mirror, player_id),
        )
        self.conn.commit()

    def set_equip_tool_skill(self, player_id, skill, item_id):
        tools = self.get_equip_tools(player_id)
        if item_id:
            tools[skill] = item_id
        else:
            tools.pop(skill, None)
        self.set_equip_tools(player_id, tools)

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

    def _player_guild_names(self):
        """player id -> guild name, if the clans tables exist."""
        tables = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "clan_members" not in tables or "clans" not in tables:
            return {}
        rows = self.conn.execute(
            "SELECT m.player_id, c.name FROM clan_members m "
            "JOIN clans c ON c.clan_id = m.clan_id"
        ).fetchall()
        return {int(r[0]): r[1] for r in rows}

    def get_leaderboards(self, limit=50):
        """Top players per skill by XP, overall total, and guild ranks."""
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(players)")}
        guild_of = self._player_guild_names()
        # char_name -> guild (for annotating rows)
        name_guild = {}
        if guild_of:
            for row in self.conn.execute("SELECT id, char_name FROM players").fetchall():
                g = guild_of.get(int(row["id"]))
                if g:
                    name_guild[row["char_name"]] = g
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
                    "guild": name_guild.get(row["char_name"]) or "",
                }
                for row in rows
            ]

        # Overall total level = sum of all skill levels; XP = sum of skill XP
        xp_cols = [f"{s}_xp" for s in XP_SKILLS if f"{s}_xp" in cols]
        player_totals = {}  # id -> (total_level, total_xp, char_name)
        if xp_cols:
            select_cols = ", ".join(["id", "char_name"] + xp_cols)
            rows = self.conn.execute(f"SELECT {select_cols} FROM players").fetchall()
            totals = []
            for row in rows:
                total_xp = 0
                total_level = 0
                for col in xp_cols:
                    xp = int(row[col] or 0)
                    total_xp += xp
                    total_level += combat.level_from_xp(xp)
                player_totals[int(row["id"])] = (total_level, total_xp, row["char_name"])
                totals.append({
                    "name": row["char_name"],
                    "xp": total_xp,
                    "level": total_level,
                    "guild": name_guild.get(row["char_name"]) or "",
                })
            totals.sort(key=lambda e: (-e["level"], -e["xp"], e["name"]))
            boards["total"] = totals[:limit]
        else:
            boards["total"] = []

        # Guild hiscores: sum of member total levels / XP
        boards["guild"] = self._guild_leaderboard(limit, player_totals, guild_of)
        return boards

    def _guild_leaderboard(self, limit, player_totals, guild_of):
        """Rank guilds by combined member total level, then total XP."""
        tables = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "clans" not in tables or "clan_members" not in tables:
            return []
        clans = self.conn.execute("SELECT clan_id, name FROM clans").fetchall()
        members = self.conn.execute(
            "SELECT clan_id, player_id FROM clan_members"
        ).fetchall()
        by_clan = {}
        for row in members:
            by_clan.setdefault(int(row[0]), []).append(int(row[1]))
        board = []
        for clan in clans:
            cid = int(clan[0] if not hasattr(clan, "keys") else clan["clan_id"])
            cname = clan[1] if not hasattr(clan, "keys") else clan["name"]
            ids = by_clan.get(cid, [])
            total_level = 0
            total_xp = 0
            for pid in ids:
                stats = player_totals.get(pid)
                if not stats:
                    continue
                total_level += stats[0]
                total_xp += stats[1]
            board.append({
                "name": cname,
                "level": total_level,
                "xp": total_xp,
                "members": len(ids),
                "guild": cname,
            })
        board.sort(key=lambda e: (-e["level"], -e["xp"], e["name"]))
        return board[:limit]
