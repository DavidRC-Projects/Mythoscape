"""Mythos Outfitters: the shop screen (Mae) and the new-character creator.

Shop mode follows SELECTION_SCREEN_UX.md / OUTFITTER_BUILD_CHECKLIST.md: left icon rail, pedestal preview,
Sets story path, 220 px detail panel, bottom bar with live totals. Creator mode keeps the simple starter
layout (plus the 10 skin tones). Prices mirror the server (reputation.buy_price + royal_treasury.buy_tax).
"""
import math
import os
import time

import pygame

NAVY = (12, 18, 34)
NAVY_CARD = (20, 28, 48)
NAVY_HI = (32, 42, 68)
GOLD = (212, 175, 90)
GOLD_HI = (240, 206, 120)
GOLD_DIM = (120, 96, 52)
INK = (232, 226, 210)
MUTED = (150, 160, 180)
SAFE_GREEN = (72, 180, 110)
SHORT_RED = (196, 104, 96)
LOCK_GREY = (110, 116, 132)

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "player_hd", "assets")
_CATALOGUE = None
_CAT_MTIME = None
_FACINGS = (("s", "Front"), ("e", "Side"), ("n", "Back"))
# Everyone starts in the free Villager / Village Lady outfit (worn over the base clothes), so the
# creator only picks what shows: skin tone, hair and hair colour. Mae sells the rest.
_CREATOR_TABS = (("body", "Body"), ("hair", "Hair"), ("hair_colour", "Hair colour"))
_CROPS = {
    "hair": (0.15, 0.0, 0.7, 0.38), "top": (0.18, 0.22, 0.64, 0.38), "bottom": (0.22, 0.48, 0.56, 0.32),
    "shoes": (0.25, 0.72, 0.5, 0.26), "outfit": (0.08, 0.04, 0.84, 0.94), "skin": (0.2, 0.12, 0.6, 0.7),
    "accessory": (0.15, 0.18, 0.7, 0.5), "cloak": (0.05, 0.08, 0.9, 0.9), "head": (0.2, 0.0, 0.6, 0.3),
    "jewellery": (0.2, 0.1, 0.6, 0.35), "held": (0.1, 0.3, 0.8, 0.5),
}
FRAME = pygame.Rect(12, 12, 1176, 776)
RAIL = pygame.Rect(28, 112, 84, 560)
STAGE = pygame.Rect(120, 112, 270, 560)
CENTRE = pygame.Rect(398, 112, 548, 560)
DETAIL = pygame.Rect(954, 112, 220, 560)
BAR_Y = 684


def _catalogue():
    """Catalogue, re-read when the file changes (new sets or art land while the game runs)."""
    global _CATALOGUE, _CAT_MTIME
    path = os.path.join(_BASE, "catalogue.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    if _CATALOGUE is None or mtime != _CAT_MTIME:
        import json
        if mtime is not None:
            with open(path, encoding="utf-8") as handle:
                _CATALOGUE = json.load(handle)
        else:
            _CATALOGUE = {}
        _CAT_MTIME = mtime
    return _CATALOGUE


def _items(slot):
    return [item for item in _catalogue().get("items", []) if item.get("slot") == slot]


def _visible_items(sex, slot=None):
    """Shop list for one sex: own + unisex items; legacy baked skins hidden."""
    out = []
    for item in _catalogue().get("items", []):
        if item.get("legacy"):
            continue
        if item.get("sex") not in (None, sex):
            continue
        if slot is not None and item.get("slot") != slot:
            continue
        out.append(item)
    return out


def _by_id(item_id):
    for item in _catalogue().get("items", []):
        if item.get("id") == item_id:
            return item
    return None


def _hex(value):
    text = str(value or "#808080").lstrip("#")
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (128, 128, 128)


def buy_price(base, score_mult, discount, cap=0.10):
    """Mirror of reputation.buy_price, given the server's price_mult for this player."""
    base = int(base)
    if base <= 0:
        return 0
    mult = max(1.0 - cap, float(score_mult) * (1.0 - float(discount or 0)))
    return max(1, int(round(base * mult)))


def buy_tax(cost, rate):
    cost = int(cost)
    if cost <= 0:
        return 0
    return max(1, int(math.ceil(cost * float(rate) - 1e-9)))


class Outfitters:
    """Creator mode for a new account, shop mode when talking to Mae."""

    # SIDEBAR_DESIGN.md §1: painted figures, so 11 tabs became 6. No colour options, no Plain/Fine/Regal.
    SHOP_TABS = ("sets", "head", "accessories", "hair", "body", "wardrobe")

    def __init__(self, client):
        self.client = client
        self.active = False
        self.mode = "shop"
        self.tab = "sets"
        self.sex = "male"
        self.facing_i = 0
        self.look = {}
        self.saved = {}
        self.scroll = 0
        self.dragging = False
        self.drag_x = 0
        self.hit = []
        self._thumbs = {}
        self.focus_set = None
        self.focus_item = None
        self.try_set = None
        self.compare = False
        self.apply_to_set = True
        self.modal = None
        self.greeting = ""
        self.hover = None
        self.hover_since = 0.0
        self.focus_coll = None
        self.toast = None
        self._pending_wear = None
        self._sil = {}

    # ---- open / close ------------------------------------------------------------------------
    def open(self, mode="shop", greeting=None):
        player = self.client.player or {}
        self.mode = "creator" if mode == "creator" else "shop"
        self.active = True
        self.sex = "female" if player.get("gender") == "female" else "male"
        self.tab = "hair" if self.mode == "creator" else "sets"
        self.facing_i = 0
        self.scroll = 0
        self.modal = None
        self.compare = False
        self._pending_wear = None
        self.greeting = greeting or ""
        import player_hd_client
        base = player.get("appearance") or player_hd_client.get_default_appearance(self.sex)
        self.look = self._full_look(base)
        self.saved = self._copy(self.look)
        self.try_set = None
        self.focus_item = None
        worn = _by_id(self.look.get("outfit")) or {}
        order = self._set_order()
        self.focus_set = worn.get("set") if worn.get("set") in order else (order[0] if order else None)

    def _full_look(self, base):
        import player_hd_client
        return {
            "skin": "skin_base" if _by_id("skin_base") else (base.get("skin") or "skin_light"),
            "skin_tone": player_hd_client.skin_tone_id(base),
            "hair": base.get("hair"), "hair_colour": base.get("hair_colour") or "dark_brown",
            "top": base.get("top"), "bottom": base.get("bottom"), "shoes": base.get("shoes"),
            "outfit": base.get("outfit"), "accessories": list(base.get("accessories") or []),
            "cloak": base.get("cloak"), "head": base.get("head"), "held": base.get("held"),
            "jewellery": list(base.get("jewellery") or []), "set": base.get("set") or self._set_of(base),
        }

    @staticmethod
    def _set_of(look):
        if look.get("set"):
            return look["set"]
        return (_by_id(look.get("outfit")) or {}).get("set")

    @staticmethod
    def _painted(set_id):
        cat = _catalogue()
        entry = (cat.get("sets") or {}).get(set_id) or next(
            (c for c in cat.get("collection") or [] if c.get("id") == set_id), {})
        return entry.get("painted") or {}

    def _overlay_block(self, item, set_id=None):
        """Why a headwear/cloak/jewellery overlay is off on this set (None when allowed)."""
        flags = self._painted(set_id or self.look.get("set"))
        slot = item.get("slot")
        if item.get("hd_jewellery") and not item.get("bundle"):
            try:
                import jewellery as J, player_hd_client as P
                eq = (self._player().get("equipment") or {})
                why = J.hidden_reason(item.get("id"), flags, {
                    "head": P._helm.helmet_tier(eq) if eq else None, "body": None, "hands": None})
                if why:
                    return why
            except Exception as e:
                print("jw block:", e)
        if slot == "head" and flags.get("head"):
            return "This set wears its own crown"
        if slot == "cloak" and flags.get("cloak"):
            return "This set has its own cloak"
        if slot == "jewellery" and flags.get("neck") and item.get("anchor") == "neck":
            return "This set has its own necklace"
        return None

    def _say(self, text):
        self.toast = (str(text), time.time())

    def on_server_error(self, text):
        """Surface Mae / wear errors in the shop toast (not only chat)."""
        if self.active:
            self._pending_wear = None
            self._say(text)

    def on_player_update(self):
        """Sync from server after Wear/Buy. Do not stomp an in-progress try-on on every tick."""
        if not self.active or self.mode == "creator":
            return
        base = self._player().get("appearance")
        if not isinstance(base, dict):
            return
        worn_name = self._pending_wear
        if worn_name:
            self.look = self._full_look(base)
            self.saved = self._copy(self.look)
            self.try_set = None
            self._thumbs.clear()
            self._say(f"Now wearing {worn_name}")
            self._pending_wear = None
            return
        # Background PLAYER_UPDATE (coins, unlocks…): keep try-on; refresh saved only if clean.
        if not self.dirty():
            self.look = self._full_look(base)
            self.saved = self._copy(self.look)

    @staticmethod
    def _copy(look):
        out = dict(look)
        out["accessories"] = list(look.get("accessories") or [])
        out["jewellery"] = list(look.get("jewellery") or [])
        return out

    def dirty(self):
        return self._payload_of(self.look) != self._payload_of(self.saved)

    def close(self, force=False):
        if self.mode == "creator":
            return
        if self.dirty() and not force:
            self.modal = "discard"
            return
        self.active = False
        self.dragging = False
        self.modal = None

    # ---- events ------------------------------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.modal:
                self.modal = None
            else:
                self.close()
            return
        if event.type in (pygame.KEYDOWN, pygame.KEYUP) and event.key == pygame.K_TAB and self.mode == "shop":
            self.compare = event.type == pygame.KEYDOWN
            return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - int(event.y) * 40)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                dx = event.pos[0] - self.drag_x
                if abs(dx) > 36:
                    self.facing_i = (self.facing_i + (1 if dx > 0 else -1)) % 3
                    self.drag_x = event.pos[0]
            self._track_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

    def _track_hover(self, pos):
        found = None
        for kind, rect, payload in self.hit:
            if kind in ("set_card", "item", "coll_card") and rect.collidepoint(pos):
                found = (kind, payload.get("id") if isinstance(payload, dict) else payload)
                break
        if found != self.hover:
            self.hover = found
            self.hover_since = time.time()

    def _stage_rect(self):
        return STAGE if self.mode == "shop" else pygame.Rect(60, 136, 400, 554)

    def _click(self, pos):
        if self.modal:
            for kind, rect, payload in self.hit:
                if kind.startswith("modal_") and rect.collidepoint(pos):
                    self._activate(kind, payload)
            return
        for kind, rect, payload in self.hit:
            if rect.collidepoint(pos):
                self._activate(kind, payload)
                return
        if self._stage_rect().collidepoint(pos):
            self.dragging = True
            self.drag_x = pos[0]

    def _toggle_sex(self):
        """Creator only. In the shop the pill is display-only and shows the character's own sex."""
        if self.mode != "creator":
            return
        self.sex = "female" if self.sex == "male" else "male"
        import player_hd_client
        fresh = player_hd_client.get_default_appearance(self.sex)
        for key in ("hair", "top", "bottom", "shoes"):
            item = _by_id(self.look.get(key))
            if item and item.get("sex") not in (None, self.sex):
                self.look[key] = fresh.get(key)
        self.client.net.send("SET_GENDER", gender=self.sex)
        self._thumbs.clear()

    def _activate(self, kind, payload):
        net = self.client.net
        if kind == "close":
            self.close()
        elif kind == "modal_keep":
            self.modal = None
        elif kind == "modal_discard":
            self.look = self._copy(self.saved)
            self.close(force=True)
        elif kind == "sex":
            self._toggle_sex()
        elif kind == "tab":
            self.tab = payload
            self.scroll = 0
        elif kind == "turn":
            self.facing_i = (self.facing_i + payload) % 3
        elif kind == "facing":
            self.facing_i = int(payload)
        elif kind == "item":
            self._pick_item(payload)
        elif kind == "colour":
            self.look["hair_colour"] = payload
        elif kind == "tone":
            self.look["skin_tone"] = payload
        elif kind in ("set_card", "wear_set"):
            self._try_set(payload)
        elif kind == "coll_card":
            self._focus_collection(payload)
        elif kind == "compare":
            self.compare = not self.compare
        elif kind == "random":
            self._randomise()
        elif kind == "reset":
            self.look = self._copy(self.saved)
            self.try_set = None
        elif kind == "skip":
            import player_hd_client
            look = player_hd_client.get_default_appearance(self.sex)
            look["skin_tone"] = self.look.get("skin_tone") or look.get("skin_tone")
            self.client.needs_appearance = False
            net.send("UPDATE_APPEARANCE", appearance=look)
            self.active = False
        elif kind == "confirm":
            self.client.needs_appearance = False
            net.send("UPDATE_APPEARANCE", appearance=self._payload())
            self.active = False
        elif kind == "buy":
            self._buy_and_wear()
        elif kind == "save_slot":
            name = (self._wardrobe()[int(payload)] or {}).get("name") or f"Outfit {int(payload) + 1}"
            net.send("SAVE_OUTFIT", slot=int(payload), appearance=self._payload(), name=name)
        elif kind == "wear_slot":
            worn = self._wardrobe()[int(payload)]
            if worn:
                self.look = self._full_look(worn)
                self.try_set = None
                self._pending_wear = worn.get("name") or self._wear_label()
                self.client.net.send("UPDATE_APPEARANCE", appearance=self._payload())
                self._say(f"Wearing {self._pending_wear}…")
        elif kind == "save_current":
            outfits = self._wardrobe()
            slot = next((i for i, o in enumerate(outfits) if not o), 0)
            net.send("SAVE_OUTFIT", slot=slot, appearance=self._payload(), name=f"Outfit {slot + 1}")
            self.tab = "wardrobe"

    # ---- data helpers ------------------------------------------------------------------------
    def _player(self):
        return self.client.player or {}

    def _owned(self):
        return set(self._player().get("owned_cosmetics") or [])

    def _wardrobe(self):
        raw = list(self._player().get("saved_outfits") or [])
        slots = int(_catalogue().get("saved_outfit_slots") or 6)
        return (raw + [None] * slots)[:slots]

    def _set_order(self):
        return list((_catalogue().get("set_order") or {}).get(self.sex) or [])

    def _sets(self):
        return _catalogue().get("sets") or {}

    def _unlock(self, set_id):
        """Server-sent state for one set (outfit_unlocks); sets with no rule are always open."""
        info = (self._player().get("outfit_unlocks") or {}).get(set_id)
        if info:
            return info
        entry = self._sets().get(set_id) or {}
        return {"state": "unlocked" if not entry.get("unlock") else "locked", "hint": "", "progress": None}

    def _item_locked(self, item):
        if not item or item.get("starter") or item["id"] in self._owned():
            return False
        if item.get("set"):
            return self._unlock(item["set"]).get("state") != "unlocked"
        return False

    def _regalia_held(self, item):
        if not item or not item.get("regalia"):
            return True
        title = self._player().get("royal_title")
        allowed = {6: {"female": ("Queen Consort", "Queen"), "male": ("Prince Consort", "King")},
                   7: {"female": ("Queen",), "male": ("King",)}}
        return title in (allowed.get(int(item.get("tier") or 0)) or {}).get(self.sex, ())

    def _pricing(self):
        p = self._player().get("outfit_pricing") or {}
        return (float(p.get("price_mult", 1.0)), float(p.get("discount", 0.0)), float(p.get("cap", 0.10)),
                float(p.get("tax_rate", 0.05)))

    def _price(self, base):
        mult, disc, cap, _rate = self._pricing()
        return buy_price(base, mult, disc, cap)

    def _spendable(self):
        """Purse + bank. Mae takes purse first, then the vault (purse caps at 65k)."""
        p = self._player()
        return int(p.get("coins") or 0) + int(p.get("bank_coins") or 0)

    def _owned_level(self, set_id):
        owned = self._owned()
        return 3 if f"{set_id}@3" in owned else (2 if f"{set_id}@2" in owned else 1)

    def _selected_ids(self, look=None):
        look = look or self.look
        ids = []
        for key in ("hair", "top", "bottom", "shoes", "outfit", "cloak", "head", "held"):
            item_id = look.get(key)
            item = _by_id(item_id) if item_id else None
            if item_id and item and not (item.get("regalia") and not self._regalia_held(item)):
                ids.append(item_id)
        for item_id in look.get("accessories") or []:
            ids.append(item_id)
        for item_id in look.get("jewellery") or []:
            item = _by_id(item_id) or {}
            if not (item.get("regalia") and not self._regalia_held(item)):
                ids.append(item_id)
        return ids

    def _free_regalia(self, item):
        return bool(item and item.get("regalia") and int(item.get("tier") or 0) == 7 and self._regalia_held(item))

    def _quote(self):
        """Footer total. Same maths as the server: set bundle, free coronation crown, Collection design, tax."""
        owned = self._owned()
        cat = _catalogue()
        new_ids = []
        for item_id in self._selected_ids():
            item = _by_id(item_id)
            if item and not item.get("starter") and item_id not in owned and item_id not in new_ids:
                new_ids.append(item_id)
        for b in cat.get("items") or []:       # Crown Jewels bundles: both pieces new -> one bundle line
            pcs = b.get("bundle") or []
            if pcs and b.get("id") not in owned and all(p in new_ids for p in pcs):
                new_ids = [i for i in new_ids if i not in pcs] + [b["id"]]
        locked = [i for i in new_ids if self._item_locked(_by_id(i))]
        lines, total = [], 0
        want = list(new_ids)
        entry = self._sets().get(self.try_set) if self.try_set else None
        if entry:
            unowned = [p for p in entry.get("pieces") or [] if p not in owned]
            if unowned and all(p in want for p in unowned):
                pieces = [p for p in unowned if not self._free_regalia(_by_id(p))]
                if len(unowned) == len(entry.get("pieces") or []) and len(pieces) == len(unowned):
                    base = int(entry.get("price") or 0)
                else:
                    share = 1.0 - float(cat.get("set_bundle_discount") or 0.15)
                    base = int(round(sum(int((_by_id(p) or {}).get("price") or 0) for p in pieces) * share))
                cost = self._price(base) if base else 0
                lines.append((entry["name"] + " set", cost))
                total += cost
                want = [i for i in want if i not in unowned]
        for item_id in want:
            item = _by_id(item_id)
            base = 0 if self._free_regalia(item) else int(item.get("price") or 0)
            cost = self._price(base) if base else 0
            lines.append((item.get("name") or item_id, cost))
            total += cost
        extras = []
        coll = self._coll(self.focus_coll) if self.try_set == self.focus_coll else None
        if coll and self._coll_live(coll) and coll["id"] not in owned:
            cost = self._price(int(coll.get("price") or 0))
            extras.append(("collection", coll["id"], None, cost))
            lines.append((coll.get("name") or coll["id"], cost))
            total += cost
        rate = self._pricing()[3]
        return {"new": new_ids, "locked": locked, "lines": lines, "extras": extras, "total": total,
                "tax": buy_tax(total, rate), "rate": rate}

    # ---- actions -----------------------------------------------------------------------------
    @staticmethod
    def _payload_of(look):
        # SIDEBAR_DESIGN §4 canonical block (+ skin/hair/outfit so older servers still render it).
        return {
            "set": look.get("set") or Outfitters._set_of(look), "skin": look.get("skin"),
            "skin_tone": look.get("skin_tone"), "hair": look.get("hair"), "hair_colour": look.get("hair_colour"),
            "outfit": look.get("outfit"), "head": look.get("head"), "cloak": look.get("cloak"),
            "jewellery": list(look.get("jewellery") or []),
        }

    def _payload(self):
        """Canonical wear block; drop title-gated regalia so Wear never fails for the rest of a set."""
        wear = self._payload_of(self.look)
        for slot in ("head", "cloak", "held"):
            item = _by_id(wear.get(slot))
            if item and item.get("regalia") and not self._regalia_held(item):
                wear[slot] = None
        wear["jewellery"] = [
            j for j in wear.get("jewellery") or []
            if self._regalia_held(_by_id(j) or {})
        ]
        return wear

    def _wear_label(self):
        entry = self._sets().get(self.look.get("set") or self.try_set or "") or {}
        if entry.get("name"):
            return entry["name"]
        item = _by_id(self.look.get("outfit") or self.focus_item)
        return (item or {}).get("name") or "that look"

    def _buy_and_wear(self):
        """Pieces (story set) or the Collection design, then the full look. No colours or upgrades."""
        q = self._quote()
        if q["locked"]:
            self._say("Locked — preview only")
            return
        label = self._wear_label()
        net = self.client.net
        wear = self._payload()
        coll = [e for e in q["extras"] if e[0] == "collection"]
        self._pending_wear = label
        if coll:
            net.send("BUY_COLLECTION_SET", set=coll[0][1])
            self._say(f"Buying {label}…")
        elif q["new"]:
            net.send("BUY_COSMETICS", items=q["new"], appearance=wear, set=self.try_set)
            self._say(f"Buying & wearing {label}…")
        else:
            net.send("UPDATE_APPEARANCE", appearance=wear)
            self._say(f"Wearing {label}…")

    # ---- Collection row (SIDEBAR_DESIGN §6.1 / §6.3) -------------------------------------------
    def _collection(self):
        return [c for c in _catalogue().get("collection") or [] if c.get("sex") == self.sex]

    def _coll(self, set_id):
        return next((c for c in _catalogue().get("collection") or [] if c.get("id") == set_id), None)

    @staticmethod
    def _coll_live(entry):
        try:
            return entry.get("release") == "live" and float(entry.get("review_score") or 0) >= 8
        except (TypeError, ValueError):
            return False

    def _focus_collection(self, set_id):
        entry = self._coll(set_id)
        if not entry:
            return
        self.focus_coll = set_id
        self.focus_set = None
        if self._coll_live(entry):          # released: previewable, Buy & Wear
            self.try_set = set_id
            self.look["set"] = set_id
        else:
            self._say("Coming soon: no preview yet")

    def _try_set(self, set_id):
        """Try on a whole set: outfit + head + cloak + jewellery + held + suggested hair."""
        entry = self._sets().get(set_id)
        if not entry:
            return
        self.focus_set = set_id
        self.focus_coll = None
        self.try_set = set_id
        look = self.look
        keep = {"head": look.get("head"), "cloak": look.get("cloak"), "jewellery": [
            j for j in look.get("jewellery") or [] if (_by_id(j) or {}).get("overlay")]}
        if not (_by_id(keep["head"]) or {}).get("overlay"):
            keep["head"] = self.__dict__.get("_held_head")
        if not (_by_id(keep["cloak"]) or {}).get("overlay"):
            keep["cloak"] = None
        look["set"] = set_id
        look["outfit"] = look["cloak"] = look["head"] = look["held"] = None
        look["jewellery"] = []
        skipped = []
        for pid in entry.get("pieces") or []:
            item = _by_id(pid) or {}
            slot = item.get("slot")
            # Title regalia only while the title is held (preview + Wear).
            if item.get("regalia") and not self._regalia_held(item):
                skipped.append(item.get("name") or pid)
                continue
            if slot == "jewellery":
                look["jewellery"].append(pid)
            elif slot in ("outfit", "cloak", "head", "held"):
                look[slot] = pid
        if entry.get("hair") and _by_id(entry["hair"]):
            look["hair"] = entry["hair"]
        if skipped:
            self._say(f"{skipped[0]} needs the title — trying the rest")
        # Overlays carry over unless the painting already has that piece (§5: cleared with a toast,
        # headwear restored if you go back to an uncrowned set this session).
        cleared = []
        for slot in ("head", "cloak"):
            item = _by_id(keep[slot])
            if item:
                if self._overlay_block(item, set_id):
                    cleared.append(item["name"])
                    if slot == "head":
                        self._held_head = keep[slot]
                else:
                    look[slot] = keep[slot]
                    if slot == "head":
                        self._held_head = None
        for jid in keep["jewellery"]:
            if self._overlay_block(_by_id(jid), set_id):
                cleared.append(_by_id(jid)["name"])
            else:
                look["jewellery"].append(jid)
        if cleared:
            self._say(f"{', '.join(cleared)} off: {self._overlay_block(_by_id(keep['head']) or {'slot': 'cloak'}, set_id) or 'painted in'}")

    def _pick_item(self, item):
        if self.mode == "creator" and not item.get("starter"):
            return
        slot = item.get("slot")
        self.focus_item = item.get("id")
        if item.get("id") and self.mode == "shop":
            why = self._overlay_block(item)
            if why:
                self._say(why)
                return
        if item.get("bundle"):
            for pid in item["bundle"]:
                piece = _by_id(pid)
                if piece and pid not in (self.look.get("jewellery") or []):
                    self._pick_item(piece)
            self.focus_item = item.get("id")
            return
        if slot == "jewellery" and item.get("hd_jewellery"):
            def _an(it):
                return set(str((it or {}).get("anchor") or "").split("+")) - {""}
            mine = _an(item)
            self.look["jewellery"] = [j for j in self.look.get("jewellery") or [] if j == item["id"] or not (
                mine & _an(_by_id(j)))]
        if slot in ("accessory", "jewellery"):
            key = "accessories" if slot == "accessory" else "jewellery"
            limit = 2       # v1: max 2 jewellery pieces (SIDEBAR_DESIGN §3.3)
            chosen = list(self.look.get(key) or [])
            if item["id"] in chosen:
                chosen.remove(item["id"])
            else:
                if len(chosen) >= limit:
                    chosen = chosen[1:]
                chosen.append(item["id"])
            self.look[key] = chosen
        elif item.get("id") is None or (slot in ("outfit", "cloak", "head", "held") and self.look.get(slot) == item["id"]):
            self.look[slot] = None
        else:
            self.look[slot] = item["id"]
            if item.get("set"):
                self.focus_set = item["set"]
        if self.try_set and item.get("set") != self.try_set:
            self.try_set = None

    def _randomise(self):
        """Painted sets: shuffle the free choices only (hair colour, skin tone stays the player's)."""
        import random
        sw = self._swatches()
        if sw:
            self.look["hair_colour"] = random.choice(sw)["id"]
        if self.mode == "creator":
            pool = [i for i in _visible_items(self.sex, "hair") if i.get("starter")]
            if pool:
                self.look["hair"] = random.choice(pool)["id"]

    def _swatches(self):
        cat = _catalogue()
        pal = {h.get("id"): h for h in cat.get("hair_palette") or []}
        ids = cat.get("hair_swatches") or [h for h in pal if not pal[h].get("legacy")]
        return [pal[i] for i in ids if i in pal]

    # ---- drawing helpers ---------------------------------------------------------------------
    def _font(self, size, bold=False):
        cache = self.__dict__.setdefault("_fonts", {})
        if (size, bold) not in cache:
            cache[(size, bold)] = pygame.font.SysFont("arial", size, bold=bold)
        return cache[(size, bold)]

    def _text(self, surf, text, pos, colour=INK, size=14, bold=False, centre=False, right=False):
        img = self._font(size, bold).render(str(text), True, colour)
        x, y = pos
        if centre:
            x -= img.get_width() // 2
        elif right:
            x -= img.get_width()
        surf.blit(img, (x, y))
        return img.get_width()

    def _wrap(self, text, width, size=14):
        lines, cur = [], ""
        for word in str(text).split():
            trial = (cur + " " + word).strip()
            if self._font(size).size(trial)[0] <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def _button(self, surf, rect, label, kind, payload=None, primary=False, disabled=False, size=16):
        fill = GOLD if primary and not disabled else (NAVY_HI if not disabled else NAVY_CARD)
        pygame.draw.rect(surf, fill, rect, border_radius=8)
        pygame.draw.rect(surf, GOLD if not disabled else LOCK_GREY, rect, 1, border_radius=8)
        colour = NAVY if primary and not disabled else (INK if not disabled else LOCK_GREY)
        img = self._font(size, bold=primary).render(label, True, colour)
        surf.blit(img, (rect.centerx - img.get_width() // 2, rect.centery - img.get_height() // 2))
        if not disabled:
            self.hit.append((kind, rect, payload))

    def _toggle(self, surf, x, y, label, on, kind):
        track = pygame.Rect(x, y + 5, 40, 22)
        pygame.draw.rect(surf, GOLD if on else NAVY_HI, track, border_radius=11)
        pygame.draw.rect(surf, GOLD_DIM, track, 1, border_radius=11)
        pygame.draw.circle(surf, INK, (track.right - 11, track.centery) if on else (track.x + 11, track.centery), 8)
        w = self._text(surf, label, (x + 48, y + 7), INK, 15)
        self.hit.append((kind, pygame.Rect(x, y, 56 + w, 32), None))

    def _padlock(self, surf, centre, scale=1.0, colour=GOLD):
        cx, cy = int(centre[0]), int(centre[1])
        w, h = int(18 * scale), int(14 * scale)
        body = pygame.Rect(cx - w // 2, cy - h // 4, w, h)
        pygame.draw.arc(surf, colour, (cx - w // 3, cy - h, w * 2 // 3, h * 3 // 2), 0, math.pi, max(2, int(3 * scale)))
        pygame.draw.rect(surf, colour, body, border_radius=3)
        pygame.draw.circle(surf, NAVY, (cx, body.centery), max(1, int(2 * scale)))

    def _crown_glyph(self, surf, centre, scale=1.0, colour=GOLD):
        cx, cy, s = centre[0], centre[1], scale
        pygame.draw.polygon(surf, colour, [(cx - 9 * s, cy + 5 * s), (cx - 9 * s, cy - 4 * s), (cx - 4 * s, cy + s),
                                           (cx, cy - 6 * s), (cx + 4 * s, cy + s), (cx + 9 * s, cy - 4 * s),
                                           (cx + 9 * s, cy + 5 * s)])

    def _coin(self, surf, centre, r=9):
        pygame.draw.circle(surf, GOLD, centre, r)
        pygame.draw.circle(surf, GOLD_DIM, centre, r, 2)

    def _tick(self, surf, pos, colour=SAFE_GREEN):
        x, y = pos
        pygame.draw.lines(surf, colour, False, [(x, y + 5), (x + 4, y + 9), (x + 11, y)], 3)

    def _fit_image(self, canvas, size):
        box = canvas.get_bounding_rect()
        if box.w < 4 or box.h < 4:
            return None
        img = canvas.subsurface(box).copy()
        k = min(size[0] / img.get_width(), size[1] / img.get_height())
        return pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))

    # ---- render ------------------------------------------------------------------------------
    def render(self, surf):
        self.hit = []
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((4, 6, 14, 200))
        surf.blit(shade, (0, 0))
        if self.mode == "creator":
            self._render_creator(surf)
        else:
            self._render_shop(surf)

    def _render_shop(self, surf):
        pygame.draw.rect(surf, NAVY, FRAME, border_radius=14)
        pygame.draw.rect(surf, GOLD, FRAME, 2, border_radius=14)
        pygame.draw.rect(surf, GOLD_DIM, FRAME.inflate(-8, -8), 1, border_radius=12)
        self._text(surf, "Mythos Outfitters", (36, 24), GOLD, 34, bold=True)
        self._text(surf, "Hair, clothing and outfits. Try anything on before you buy.", (38, 70), MUTED, 15)
        if self.greeting:
            for i, row in enumerate(self._wrap(f"Mae: \u201c{self.greeting}\u201d", 560, 14)[:2]):
                self._text(surf, row, (520, 34 + i * 18), INK, 14)
        close = pygame.Rect(1132, 26, 36, 34)
        pygame.draw.rect(surf, NAVY_CARD, close, border_radius=6)
        pygame.draw.rect(surf, GOLD_DIM, close, 1, border_radius=6)
        self._text(surf, "X", (close.centerx, close.y + 7), INK, 18, bold=True, centre=True)
        self.hit.append(("close", close, None))
        pygame.draw.line(surf, GOLD_DIM, (28, 100), (1172, 100), 1)
        self._draw_rail(surf)
        self._draw_stage_shop(surf)
        pygame.draw.rect(surf, NAVY_CARD, CENTRE, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, CENTRE, 1, border_radius=12)
        if self.tab == "sets":
            self._draw_sets_path(surf)
        elif self.tab == "body":
            self._draw_body_tab(surf, CENTRE)
        elif self.tab == "wardrobe":
            self._draw_wardrobe(surf)
        else:
            self._draw_item_grid(surf)
        self._draw_detail(surf)
        pygame.draw.line(surf, GOLD_DIM, (28, BAR_Y - 4), (1172, BAR_Y - 4), 1)
        self._draw_bar(surf)
        if self.toast and time.time() - self.toast[1] < 3.5:
            text = self.toast[0]
            ok = text.startswith("Now wearing")
            tw = self._font(15, True).size(text)[0] + 36
            box = pygame.Rect(STAGE.centerx - tw // 2, STAGE.y + 48, tw, 34)
            pygame.draw.rect(surf, NAVY, box, border_radius=16)
            pygame.draw.rect(surf, SAFE_GREEN if ok else GOLD, box, 2, border_radius=16)
            self._text(surf, text, (box.centerx, box.y + 8), SAFE_GREEN if ok else GOLD_HI, 15, bold=True, centre=True)
        if self.modal == "discard":
            self._draw_modal(surf)

    def _tab_label(self, key):
        female = self.sex == "female"
        return {"sets": "Sets", "outfit": "Gowns" if female else "Coats", "top": "Tops",
                "bottom": "Skirts" if female else "Bottoms", "cloak": "Cloaks", "accessories": "Accessories",
                "head": "Headwear", "jewellery": "Jewellery", "hair": "Hair colour", "shoes": "Shoes",
                "body": "Body", "wardrobe": "Wardrobe"}[key]

    def _draw_rail(self, surf):
        pygame.draw.rect(surf, NAVY_CARD, RAIL, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, RAIL, 1, border_radius=12)
        h = (RAIL.h - 8) // len(self.SHOP_TABS)
        for i, key in enumerate(self.SHOP_TABS):
            rect = pygame.Rect(RAIL.x + 4, RAIL.y + 4 + i * h, RAIL.w - 8, h - 2)
            active = key == self.tab
            if active:
                pygame.draw.rect(surf, NAVY_HI, rect, border_radius=8)
                pygame.draw.rect(surf, GOLD, rect, 1, border_radius=8)
            colour = GOLD_HI if active else MUTED
            self._rail_icon(surf, key, (rect.centerx, rect.y + 14), colour)
            self._text(surf, self._tab_label(key), (rect.centerx, rect.y + 26), INK if active else MUTED, 13, centre=True)
            self.hit.append(("tab", rect, key))

    def _rail_icon(self, surf, key, c, col):
        x, y = c
        if key == "sets":
            for k in range(8):
                a = k * math.pi / 4
                r = 9 if k % 2 == 0 else 5
                pygame.draw.line(surf, col, (x, y), (x + r * math.cos(a), y + r * math.sin(a)), 2)
        elif key == "outfit":
            pygame.draw.polygon(surf, col, [(x - 4, y - 9), (x + 4, y - 9), (x + 9, y + 9), (x - 9, y + 9)])
        elif key == "top":
            pygame.draw.polygon(surf, col, [(x - 10, y - 5), (x - 5, y - 9), (x + 5, y - 9), (x + 10, y - 5),
                                            (x + 6, y - 1), (x + 5, y + 9), (x - 5, y + 9), (x - 6, y - 1)])
        elif key == "bottom":
            if self.sex == "female":
                pygame.draw.polygon(surf, col, [(x - 4, y - 9), (x + 4, y - 9), (x + 10, y + 9), (x - 10, y + 9)])
            else:
                pygame.draw.polygon(surf, col, [(x - 6, y - 9), (x + 6, y - 9), (x + 8, y + 9), (x + 2, y + 9),
                                                (x, y - 2), (x - 2, y + 9), (x - 8, y + 9)])
        elif key == "cloak":
            pygame.draw.polygon(surf, col, [(x - 3, y - 9), (x + 3, y - 9), (x + 10, y + 9), (x - 10, y + 9)], 2)
            pygame.draw.circle(surf, col, (x, y - 8), 3)
        elif key == "head":
            self._crown_glyph(surf, (x, y), 0.95, col)
        elif key in ("jewellery", "accessories"):
            pygame.draw.circle(surf, col, (x, y + 3), 6, 2)
            pygame.draw.polygon(surf, col, [(x - 3, y - 7), (x + 3, y - 7), (x, y - 2)])
        elif key == "hair":
            pygame.draw.arc(surf, col, (x - 9, y - 9, 18, 20), 0, math.pi, 4)
            pygame.draw.line(surf, col, (x - 8, y), (x - 9, y + 9), 3)
            pygame.draw.line(surf, col, (x + 8, y), (x + 9, y + 9), 3)
        elif key == "shoes":
            pygame.draw.polygon(surf, col, [(x - 8, y - 8), (x - 3, y - 8), (x - 2, y + 2), (x + 9, y + 5),
                                            (x + 9, y + 8), (x - 8, y + 8)])
        elif key == "body":
            pygame.draw.circle(surf, col, (x, y - 6), 4)
            pygame.draw.line(surf, col, (x, y - 2), (x, y + 5), 3)
            pygame.draw.line(surf, col, (x - 7, y), (x + 7, y), 2)
            pygame.draw.line(surf, col, (x, y + 5), (x - 5, y + 10), 2)
            pygame.draw.line(surf, col, (x, y + 5), (x + 5, y + 10), 2)
        elif key == "wardrobe":
            pygame.draw.rect(surf, col, (x - 9, y - 9, 18, 18), 2, border_radius=2)
            pygame.draw.line(surf, col, (x, y - 9), (x, y + 9), 2)

    def _preview_look(self):
        return self.saved if self.compare else self.look

    def _blit_stage_player(self, surf, cx, feet, facing):
        """Draw the shop/creator preview at native 4x with a light unsharp pass."""
        import player_hd_client
        pad = 300
        canvas = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
        player_hd_client.draw_player(
            canvas, self.sex, self._preview_look() if self.mode != "creator" else self.look,
            pad, pad + 80, 160, pygame.time.get_ticks() / 1000.0, anim="idle", facing=facing, equipment=None,
            fx_ctx={"preview": True},
        )
        box = canvas.get_bounding_rect()
        if box.w < 4 or box.h < 4:
            return
        fig = canvas.subsurface(box).copy()
        fig = self._unsharp(fig)
        surf.blit(fig, (cx - (pad - box.x), feet - (pad + 80 - box.y)))

    @staticmethod
    def _unsharp(surf, amount=0.4):
        """Mild unsharp-mask so soft HD edges read cleaner in the Outfitters stage."""
        try:
            import numpy as np
        except ImportError:
            return surf
        w, h = surf.get_size()
        if w < 8 or h < 8:
            return surf
        small = pygame.transform.smoothscale(surf, (max(1, w // 2), max(1, h // 2)))
        blur = pygame.transform.smoothscale(small, (w, h))
        rgb = pygame.surfarray.array3d(surf).astype(np.float32)
        brgb = pygame.surfarray.array3d(blur).astype(np.float32)
        alpha = pygame.surfarray.array_alpha(surf)
        out = np.clip(rgb + amount * (rgb - brgb), 0, 255).astype(np.uint8)
        sharp = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.surfarray.blit_array(sharp, out)
        alpha_px = pygame.surfarray.pixels_alpha(sharp)
        alpha_px[:] = alpha
        del alpha_px
        return sharp

    def _draw_stage_shop(self, surf):
        stage = STAGE
        pygame.draw.rect(surf, NAVY_CARD, stage, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, stage, 1, border_radius=12)
        # sex pill: display only, the character's own sex is highlighted (no hit area)
        pill = pygame.Rect(stage.centerx - 70, stage.y + 12, 140, 30)
        pygame.draw.rect(surf, NAVY, pill, border_radius=15)
        pygame.draw.rect(surf, GOLD_DIM, pill, 1, border_radius=15)
        for k, (label, sex) in enumerate((("Male", "male"), ("Female", "female"))):
            seg = pygame.Rect(pill.x + 3 + k * 67, pill.y + 3, 67, 24)
            on = sex == self.sex
            if on:
                pygame.draw.rect(surf, GOLD, seg, border_radius=12)
            self._text(surf, label, (seg.centerx, seg.y + 4), NAVY if on else LOCK_GREY, 14, bold=on, centre=True)
        # Native 4x (tile=160): 1:1 pixels — no smoothscale soft blur from up/downscaling.
        cx, feet = stage.centerx, stage.bottom - 112
        ped = pygame.Rect(cx - 70, feet + 2, 140, 30)
        pygame.draw.ellipse(surf, (32, 26, 22), ped)
        clip = surf.get_clip()
        surf.set_clip(stage.inflate(-4, -4))
        self._blit_stage_player(surf, cx, feet, _FACINGS[self.facing_i][0])
        pygame.draw.ellipse(surf, GOLD, ped, 2)
        surf.set_clip(clip)
        if self.compare:
            self._text(surf, "Comparing: saved look", (cx, stage.y + 50), GOLD, 14, centre=True)
        y = stage.bottom - 46
        for rect, step, glyph in ((pygame.Rect(stage.x + 10, y, 34, 34), -1, "<"),
                                  (pygame.Rect(stage.right - 44, y, 34, 34), 1, ">")):
            pygame.draw.circle(surf, NAVY, rect.center, 16)
            pygame.draw.circle(surf, GOLD, rect.center, 16, 1)
            self._text(surf, glyph, (rect.centerx, rect.y + 7), GOLD, 16, bold=True, centre=True)
            self.hit.append(("turn", rect, step))
        back_hint = self._back_hint()
        for k, (_f, label) in enumerate(_FACINGS):
            rect = pygame.Rect(stage.x + 50 + k * 58, y + 2, 54, 32)
            on = k == self.facing_i
            if on:
                pygame.draw.rect(surf, NAVY_HI, rect, border_radius=16)
                pygame.draw.rect(surf, GOLD, rect, 1, border_radius=16)
            self._text(surf, label, (rect.centerx, rect.y + 8), GOLD_HI if on else MUTED, 14, centre=True)
            if label == "Back" and back_hint:
                pygame.draw.polygon(surf, GOLD, [(rect.right - 12, rect.y + 3), (rect.right - 3, rect.y + 3),
                                                 (rect.right - 3, rect.y + 14)])
            self.hit.append(("facing", rect, k))

    def _back_hint(self):
        """Cloak/veil sets show mostly from behind: flag the Back pill."""
        outfit = _by_id(self.look.get("outfit")) or {}
        entry = self._sets().get(outfit.get("set")) or {}
        return bool(entry.get("back_hint"))

    # ---- sets path ----------------------------------------------------------------------------
    def _set_look(self, set_id, palette=None):
        entry = self._sets().get(set_id) or {}
        look = self._copy(self.look)
        look.update(outfit=None, cloak=None, head=None, held=None, jewellery=[], set=set_id)
        for pid in entry.get("pieces") or []:
            item = _by_id(pid) or {}
            if item.get("slot") == "jewellery":
                look["jewellery"].append(pid)
            elif item.get("slot") in ("outfit", "cloak", "head", "held"):
                look[item["slot"]] = pid
        if entry.get("hair") and _by_id(entry["hair"]):
            look["hair"] = entry["hair"]
        return look

    def _set_thumb(self, set_id, facing="s", size=(66, 144)):
        """Each card shows its own set in palette 1 (front, or back after a 0.6 s hover)."""
        key = ("set", self.sex, set_id, facing, self.look.get("skin_tone"), self.look.get("hair_colour"), size)
        if key in self._thumbs:
            return self._thumbs[key]
        import player_hd_client
        canvas = pygame.Surface((220, 340), pygame.SRCALPHA)     # tall enough for crowns and HD sets
        player_hd_client.draw_player(canvas, self.sex, self._set_look(set_id), 110, 320, 160, 0.0,
                                     anim="idle", facing=facing, fx_ctx={"preview": True})
        self._thumbs[key] = self._fit_image(canvas, size)
        return self._thumbs[key]

    def _set_state(self, set_id):
        entry = self._sets().get(set_id) or {}
        owned = self._owned()
        pieces = entry.get("pieces") or []
        own_all = bool(pieces) and all(p in owned for p in pieces)
        regalia_lost = any((_by_id(p) or {}).get("regalia") and p in owned and not self._regalia_held(_by_id(p))
                           for p in pieces)
        return self._unlock(set_id), own_all, regalia_lost

    def _draw_sets_path(self, surf):
        area = CENTRE
        self._text(surf, "The royal path", (area.x + 18, area.y + 14), GOLD, 18, bold=True)
        self._text(surf, "Each set is shown as painted. Click to try on; locked sets can still be previewed.",
                   (area.x + 18, area.y + 40), MUTED, 13)
        self._draw_collection_row(surf, area)
        order = [s for s in self._set_order() if self._unlock(s).get("state") != "hidden"]
        if not order:
            return
        card_w, card_h, gap = 72, 222, 4
        total = len(order) * card_w + (len(order) - 1) * gap
        x0 = area.centerx - total // 2
        y0 = area.y + 64
        coins = self._spendable()
        rects = [pygame.Rect(x0 + i * (card_w + gap), y0, card_w, card_h) for i in range(len(order))]
        base_y = y0 + card_h + 16
        for a, b in zip(rects, rects[1:]):
            y = a.y + 96
            pygame.draw.line(surf, GOLD_DIM, (a.right - 2, y), (b.x + 2, y), 3)
        if len(rects) > 1:
            pygame.draw.line(surf, GOLD_DIM, (rects[0].centerx, base_y), (rects[-1].centerx, base_y), 2)
        tip = None
        for sid, rect in zip(order, rects):
            entry = self._sets()[sid]
            info, own_all, regalia_lost = self._set_state(sid)
            locked = info.get("state") != "unlocked" and not own_all
            worn_set = (_by_id(self.look.get("outfit")) or {}).get("set")
            selected = self.try_set == sid or (self.try_set is None and worn_set == sid)
            pygame.draw.line(surf, GOLD if selected else GOLD_DIM, (rect.centerx, rect.bottom), (rect.centerx, base_y), 2)
            pygame.draw.circle(surf, GOLD if selected else GOLD_DIM, (rect.centerx, base_y), 5 if selected else 3)
            if selected:
                halo = pygame.Surface((rect.w + 28, rect.h + 28), pygame.SRCALPHA)
                for r in range(12, 0, -2):
                    pygame.draw.rect(halo, (240, 206, 120, 8 + (12 - r) * 5), halo.get_rect().inflate(-r * 2, -r * 2),
                                     border_radius=14)
                surf.blit(halo, (rect.x - 14, rect.y - 14))
            pygame.draw.rect(surf, NAVY, rect, border_radius=8)
            tier_col = tuple((_catalogue().get("tier_colours") or {}).get(str(entry["tier"]), GOLD))
            pygame.draw.rect(surf, tier_col, (rect.x + 6, rect.y + 5, rect.w - 12, 5), border_radius=2)
            self._text(surf, f"T{entry['tier']}", (rect.right - 6, rect.y + 12), tier_col, 12, bold=True, right=True)
            hovering = self.hover == ("set_card", sid) and time.time() - self.hover_since > 0.6
            thumb = self._set_thumb(sid, "n" if hovering else "s", (66, 136))
            if thumb:
                if locked:
                    thumb = thumb.copy()
                    thumb.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
                surf.blit(thumb, (rect.centerx - thumb.get_width() // 2, rect.y + 152 - thumb.get_height()))
            if locked:
                self._padlock(surf, (rect.centerx, rect.y + 96), 1.3)
            for k, row in enumerate(self._wrap(entry["name"], rect.w - 4, 14)[:2]):
                self._text(surf, row, (rect.centerx, rect.y + 154 + k * 16), INK if not locked else MUTED, 14,
                           centre=True)
            sy = rect.y + 190
            if regalia_lost:
                self._text(surf, "Regalia", (rect.centerx, sy), LOCK_GREY, 13, centre=True)
            elif own_all:
                self._tick(surf, (rect.centerx - 24, sy + 2))
                self._text(surf, "owned", (rect.centerx + 6, sy), SAFE_GREEN, 13, centre=True)
            elif locked:
                for k, row in enumerate(self._wrap(self._short_hint(sid, info), rect.w - 4, 12)[:2]):
                    self._text(surf, row, (rect.centerx, sy - 4 + k * 13), GOLD_DIM, 12, centre=True)
            else:
                price = self._price(int(entry.get("price") or 0))
                self._text(surf, f"{price:,}", (rect.centerx, sy), GOLD if coins >= price else SHORT_RED, 13,
                           centre=True)
            if selected:
                self._text(surf, "selected", (rect.centerx, rect.bottom - 16), GOLD_HI, 12, centre=True)
            if any((_by_id(p) or {}).get("regalia") for p in entry.get("pieces") or []):
                self._crown_glyph(surf, (rect.x + 13, rect.y + 20), 0.6, GOLD)
            pygame.draw.rect(surf, GOLD_HI if selected else (GOLD_DIM if not locked else LOCK_GREY), rect,
                             3 if selected else 1, border_radius=8)
            self.hit.append(("set_card", rect, sid))
            if locked and self.hover == ("set_card", sid):
                tip = (rect, info)
        if tip:
            rect, info = tip
            text = info.get("hint") or "Locked"
            if info.get("progress"):
                text = f"{text} ({info['progress']})"
            rows = self._wrap(text, 200, 13)[:4]
            box = pygame.Rect(0, 0, 216, 12 + 16 * len(rows))
            box.midtop = (rect.centerx, base_y + 12)
            box.clamp_ip(CENTRE.inflate(-8, -8))
            pygame.draw.line(surf, GOLD, (rect.centerx, rect.bottom), (rect.centerx, box.top), 1)
            pygame.draw.rect(surf, NAVY, box, border_radius=8)
            pygame.draw.rect(surf, GOLD, box, 1, border_radius=8)
            for k, row in enumerate(rows):
                self._text(surf, row, (box.x + 8, box.y + 6 + k * 16), INK, 13)

    def _silhouette(self, entry, size):
        """Greyed silhouette of a not-yet-released design (§6.1): shape only, no colour, no preview."""
        key = (entry["id"], size)
        if key in self._sil:
            return self._sil[key]
        img = None
        path = os.path.join(_BASE, "collection", entry["id"] + ".png")
        try:
            raw = pygame.image.load(path)
            raw = raw.convert_alpha() if pygame.display.get_surface() else raw
            img = self._fit_image(raw, size)
            if img:
                img = img.copy()
                img.fill((70, 76, 92, 0), special_flags=pygame.BLEND_RGB_MIN)
                img.fill((0, 0, 0, 150), special_flags=pygame.BLEND_RGBA_MIN)
        except (pygame.error, FileNotFoundError, OSError):
            img = None
        self._sil[key] = img
        return img

    def _draw_collection_row(self, surf, area):
        rows = self._collection()
        if not rows:
            return
        y = area.y + 330
        self._text(surf, "Collection", (area.x + 18, y), GOLD, 16, bold=True)
        self._text(surf, "New painted designs, sold separately. Elemental line: coming soon.",
                   (area.x + 118, y + 3), MUTED, 12)
        card_w, card_h, gap = 72, 186, 4
        total = len(rows) * card_w + (len(rows) - 1) * gap
        x0 = area.centerx - total // 2
        coins = self._spendable()
        owned = self._owned()
        for i, entry in enumerate(rows):
            rect = pygame.Rect(x0 + i * (card_w + gap), y + 24, card_w, card_h)
            live = self._coll_live(entry)
            focus = self.focus_coll == entry["id"]
            pygame.draw.rect(surf, NAVY, rect, border_radius=8)
            sil = self._silhouette(entry, (60, 118))
            if sil:
                surf.blit(sil, (rect.centerx - sil.get_width() // 2, rect.y + 124 - sil.get_height()))
            el = (entry.get("element") or "").title()
            self._padlock(surf, (rect.centerx, rect.y + 66), 1.0, INK if live else LOCK_GREY)
            for k, row in enumerate(self._wrap(entry.get("name") or "", rect.w - 6, 12)[:2]):
                self._text(surf, row, (rect.centerx, rect.y + 126 + k * 13), INK if live else MUTED, 12, centre=True)
            if entry["id"] in owned:
                self._text(surf, "owned", (rect.centerx, rect.bottom - 22), SAFE_GREEN, 12, centre=True)
            elif live:
                price = self._price(int(entry.get("price") or 0))
                self._text(surf, f"{price:,}", (rect.centerx, rect.bottom - 22), GOLD if coins >= price else SHORT_RED,
                           12, centre=True)
            else:
                self._text(surf, "Coming soon", (rect.centerx, rect.bottom - 22), GOLD_DIM, 12, centre=True)
            if el:
                self._text(surf, el, (rect.right - 5, rect.y + 6), GOLD_DIM, 11, right=True)
            pygame.draw.rect(surf, GOLD_HI if focus else (GOLD_DIM if live else LOCK_GREY), rect,
                             3 if focus else 1, border_radius=8)
            self.hit.append(("coll_card", rect, entry["id"]))

    def _short_hint(self, set_id, info):
        """Card line under a locked set; gender-correct, never Courtier wording for men."""
        tier = int((self._sets().get(set_id) or {}).get("tier") or 0)
        female = self.sex == "female"
        return {
            2: "Requires Respected",
            3: "Requires " + ("Dame" if female else "Knight") + " rank",
            4: "Requires " + ("Countess" if female else "Count") + " rank",
            5: "Courtier's Path · 500 favour" if female else "Count, Revered, guild",
            6: "Queen Consort or 1,000 favour" if female else "Prince Consort",
            7: "Reigning Queen" if female else "Reigning King",
        }.get(tier, info.get("hint") or "Locked")

    # ---- item grid ----------------------------------------------------------------------------
    def _grid_items(self):
        """Headwear: None + head overlays. Accessories: cloak section + jewellery section (overlays only)."""
        tab = self.tab
        def live(i):
            return i.get("release", "live") == "live"
        def overlays(slot):
            return [i for i in _visible_items(self.sex, slot) if i.get("overlay") and live(i)]
        if tab == "head":
            return [{"id": None, "slot": "head", "name": "None", "price": 0, "starter": True}] + overlays("head")
        if tab == "accessories":
            free = [{"id": None, "slot": "cloak", "name": "No cloak", "price": 0, "starter": True}] + overlays("cloak") + [
                i for i in overlays("jewellery") if i.get("row") != "Crown Jewels"]
            crown = [i for i in _catalogue().get("items", []) if (i.get("row") == "Crown Jewels" or i.get("slot") == "bundle") and live(i)
                     and i.get("sex") in (None, self.sex)]
            if crown:
                free += [{"spacer": True, "id": None}] * ((-len(free)) % 4)
                crown = [dict(c, _crown_first=(k == 0)) for k, c in enumerate(crown)]
            return free + crown
        return []

    def _draw_item_grid(self, surf):
        area = CENTRE
        label = self._tab_label(self.tab)
        self._text(surf, label, (area.x + 18, area.y + 14), GOLD, 18, bold=True)
        if self.tab == "hair":
            self._draw_hair_tab(surf, area)
            return
        if self.tab == "accessories":
            worn = [j for j in self.look.get("jewellery") or [] if (_by_id(j) or {}).get("overlay")]
            self._text(surf, f"1 cloak · Jewellery {len(worn)}/2", (area.right - 18, area.y + 18), MUTED, 13, right=True)
        if self.tab == "head":
            eq = (self.client.player or {}).get("equipment") or {}
            helm = eq.get("helmet") if isinstance(eq, dict) else None
            note = "Helmets come from Equipment (unequip there). " + ("Hidden by helmet." if helm else "")
            self._text(surf, note, (area.right - 18, area.y + 18), MUTED, 12, right=True)
        items = self._grid_items()
        top = area.y + 48
        bottom_pad = 10
        if not items:
            self._text(surf, f"No {label.lower()} yet. Mae expects them with the new outfit art.",
                       (area.centerx, area.y + 220), MUTED, 15, centre=True)
            return
        cols, card_w, card_h, gap = 4, 124, 158, 8
        clip_rect = pygame.Rect(area.x + 6, top, area.w - 12, area.bottom - top - bottom_pad)
        max_scroll = max(0, ((len(items) + cols - 1) // cols) * (card_h + gap) - clip_rect.h)
        self.scroll = min(self.scroll, max_scroll)
        old_clip = surf.get_clip()
        surf.set_clip(clip_rect)
        coins = self._spendable()
        crown_row = next((i // cols for i, it in enumerate(items) if it.get("_crown_first")), None)
        if crown_row is not None:
            max_scroll += 30
            self.scroll = min(self.scroll, max_scroll)
        for i, item in enumerate(items):
            col, row = i % cols, i // cols
            dy = 30 if crown_row is not None and row >= crown_row else 0
            rect = pygame.Rect(area.x + 14 + col * (card_w + gap), top + row * (card_h + gap) + dy - self.scroll, card_w, card_h)
            if item.get("_crown_first"):
                hy = rect.y - 26
                self._text(surf, "Crown Jewels", (area.x + 18, hy), GOLD_HI, 16, bold=True)
                self._text(surf, "gem sparkle \u00b7 hover to see it", (area.right - 18, hy + 2), MUTED, 12, right=True)
                pygame.draw.line(surf, GOLD_DIM, (area.x + 130, hy + 10), (area.right - 200, hy + 10), 1)
            if item.get("spacer"):
                continue
            if rect.bottom < clip_rect.y or rect.top > clip_rect.bottom:
                continue
            selected = self._is_selected(item)
            locked = self._item_locked(item)
            blocked = self._overlay_block(item) if item.get("id") else None
            crown = item.get("row") == "Crown Jewels"
            pygame.draw.rect(surf, (34, 22, 52) if crown else NAVY, rect, border_radius=8)
            if item.get("tier"):
                tier_col = tuple((_catalogue().get("tier_colours") or {}).get(str(item["tier"]), GOLD))
                pygame.draw.rect(surf, tier_col, (rect.x + 6, rect.y + 5, rect.w - 12, 4), border_radius=2)
            if item.get("id"):
                thumb = self._thumb(item)
                if thumb:
                    if locked:
                        thumb = thumb.copy()
                        thumb.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    surf.blit(thumb, (rect.centerx - thumb.get_width() // 2, rect.y + 12))
                else:
                    self._placeholder_icon(surf, item, pygame.Rect(rect.centerx - 40, rect.y + 14, 80, 80))
                if locked:
                    self._padlock(surf, (rect.centerx, rect.y + 54), 1.1)
                if crown and thumb and not locked and self.hover == ("item", item.get("id")):
                    self._card_sparkle(surf, item, pygame.Rect(rect.centerx - thumb.get_width() // 2, rect.y + 12,
                                                               thumb.get_width(), thumb.get_height()))
                if item.get("regalia"):
                    self._crown_glyph(surf, (rect.x + 14, rect.y + 18), 0.6)
            for k, row_t in enumerate(self._wrap(item.get("name") or "", card_w - 8, 14)[:2]):
                self._text(surf, row_t, (rect.centerx, rect.bottom - 54 + k * 16), INK, 14, centre=True)
            price, colour = self._price_label(item, coins)
            if blocked:
                grey = pygame.Surface(rect.size, pygame.SRCALPHA)
                grey.fill((12, 18, 34, 170))
                surf.blit(grey, rect.topleft)
                price, colour = blocked, LOCK_GREY
                rows_b = self._wrap(price, card_w - 8, 11)[:2]
                for k, r in enumerate(rows_b):
                    self._text(surf, r, (rect.centerx, rect.bottom - 26 + k * 12), colour, 11, centre=True)
            else:
                self._text(surf, price, (rect.centerx, rect.bottom - 20), colour, 13, centre=True)
            pygame.draw.rect(surf, GOLD_HI if selected or crown else GOLD_DIM, rect, 3 if selected else 1, border_radius=8)
            self.hit.append(("item", rect.clip(clip_rect), item))
        surf.set_clip(old_clip)

    def _draw_hair_tab(self, surf, area):
        """§3.4: 10 free colour swatches; style is fixed to the painting."""
        self._text(surf, "Hair colour", (area.x + 18, area.y + 14), GOLD, 18, bold=True)
        self._text(surf, "10 colours, all free. Tints the painted hair (and beard) in every set.",
                   (area.x + 18, area.y + 40), MUTED, 13)
        sw = self._swatches()
        size, gap, per_row = 50, 46, 5
        x0 = area.x + (area.w - (per_row * size + (per_row - 1) * gap)) // 2
        for i, colour in enumerate(sw):
            cell = pygame.Rect(x0 + (i % per_row) * (size + gap), area.y + 90 + (i // per_row) * 116, size, size)
            pygame.draw.circle(surf, tuple(colour.get("mul") or (80, 80, 80)), cell.center, size // 2)
            pygame.draw.circle(surf, (0, 0, 0), cell.center, size // 2, 1)
            if self.look.get("hair_colour") == colour.get("id"):
                pygame.draw.circle(surf, GOLD, cell.center, size // 2 + 5, 3)
            self._text(surf, colour.get("name") or colour.get("id"), (cell.centerx, cell.bottom + 10), INK, 13, centre=True)
            self.hit.append(("colour", cell.inflate(10, 10), colour.get("id")))
        row = pygame.Rect(area.x + 18, area.y + 340, area.w - 36, 40)
        pygame.draw.rect(surf, NAVY, row, border_radius=8)
        pygame.draw.rect(surf, LOCK_GREY, row, 1, border_radius=8)
        self._padlock(surf, (row.x + 18, row.centery + 1), 0.6, LOCK_GREY)
        self._text(surf, "Style: as painted on this set", (row.x + 36, row.y + 11), MUTED, 15)

    def _placeholder_icon(self, surf, item, rect):
        """Head, jewellery and held pieces have no strip yet: a clean drawn icon in the set colours."""
        import player_hd_client
        base, trim = player_hd_client.garment_rgb(item) or ((150, 150, 150), (201, 160, 62))
        pygame.draw.circle(surf, (28, 36, 58), rect.center, rect.w // 2)
        slot = item.get("slot")
        if slot == "head":
            self._crown_glyph(surf, rect.center, 2.2, trim)
            pygame.draw.circle(surf, base, (rect.centerx, rect.centery + 4), 4)
        elif slot == "jewellery":
            pygame.draw.circle(surf, trim, (rect.centerx, rect.centery + 2), 16, 4)
            pygame.draw.circle(surf, base if base != (21, 20, 24) else (176, 18, 42), (rect.centerx, rect.centery + 18), 7)
        elif slot == "held":
            pygame.draw.rect(surf, base, (rect.centerx - 14, rect.centery - 6, 28, 22), border_radius=6)
            pygame.draw.arc(surf, trim, (rect.centerx - 10, rect.centery - 18, 20, 24), 0, math.pi, 3)
        else:
            pygame.draw.circle(surf, base, rect.center, 18)
            pygame.draw.circle(surf, trim, rect.center, 18, 3)

    def _price_label(self, item, coins):
        if not item.get("id") or item.get("starter"):
            return "Free", SAFE_GREEN
        if item["id"] in self._owned():
            return ("Regalia", LOCK_GREY) if not self._regalia_held(item) else ("Owned", SAFE_GREEN)
        if self._item_locked(item):
            return "Locked", LOCK_GREY
        price = 0 if self._free_regalia(item) else self._price(int(item.get("price") or 0))
        return f"{price:,} coins", GOLD if coins >= price else SHORT_RED

    def _draw_hair_swatches(self, surf, rect):
        self._text(surf, "Hair colour", (rect.x, rect.y + 14), INK, 14)
        x = rect.x + 96
        for colour in _catalogue().get("hair_palette") or []:
            cell = pygame.Rect(x, rect.y + 6, 34, 34)
            pygame.draw.circle(surf, tuple(colour.get("mul") or (80, 80, 80)), cell.center, 13)
            if self.look.get("hair_colour") == colour.get("id"):
                pygame.draw.circle(surf, GOLD, cell.center, 16, 2)
            self.hit.append(("colour", cell, colour.get("id")))
            x += 36

    def _draw_body_tab(self, surf, area):
        self._text(surf, "Body", (area.x + 18, area.y + 14), GOLD, 18, bold=True)
        self._text(surf, "Skin tone · free · face, neck and hands, in every outfit", (area.x + 18, area.y + 40),
                   MUTED, 13)
        self._text(surf, "Gender: change at the barber or in the creator", (area.x + 18, area.bottom - 34), MUTED, 13)
        tones = _catalogue().get("skin_palette") or []
        size, gap, per_row = 44, 44, 5
        x0 = area.x + (area.w - (per_row * size + (per_row - 1) * gap)) // 2
        for i, tone in enumerate(tones):
            cell = pygame.Rect(x0 + (i % per_row) * (size + gap), area.y + 96 + (i // per_row) * 112, size, size)
            pygame.draw.circle(surf, _hex(tone.get("hex")), cell.center, size // 2)
            pygame.draw.circle(surf, (0, 0, 0), cell.center, size // 2, 1)
            if self.look.get("skin_tone") == tone.get("id"):
                pygame.draw.circle(surf, GOLD, cell.center, size // 2 + 5, 3)
            self._text(surf, tone.get("name") or "", (cell.centerx, cell.bottom + 10), INK, 13, centre=True)
            self.hit.append(("tone", cell.inflate(10, 10), tone.get("id")))

    def _draw_wardrobe(self, surf):
        area = CENTRE
        self._text(surf, "Wardrobe", (area.x + 18, area.y + 14), GOLD, 18, bold=True)
        for i, entry in enumerate(self._wardrobe()):
            rect = pygame.Rect(area.x + 14 + (i % 2) * 264, area.y + 44 + (i // 2) * 102, 256, 94)
            pygame.draw.rect(surf, NAVY, rect, border_radius=8)
            pygame.draw.rect(surf, GOLD_DIM, rect, 1, border_radius=8)
            name = (entry or {}).get("name") or f"Outfit {i + 1}"
            self._text(surf, f"{i + 1}. {name}", (rect.x + 76, rect.y + 8), INK, 14, bold=True)
            if entry:
                thumb = self._look_thumb(entry, (58, 82))
                if thumb:
                    surf.blit(thumb, (rect.x + 10 + (58 - thumb.get_width()) // 2, rect.y + 6))
                held_ok = all(self._regalia_held(_by_id(entry.get(k))) for k in ("head", "held", "cloak"))
                note = "Regalia not held" if not held_ok else self._outfit_name(entry)
                self._text(surf, self._wrap(note, 170, 13)[0], (rect.x + 76, rect.y + 28), LOCK_GREY if not held_ok else MUTED, 13)
            else:
                self._text(surf, "Empty", (rect.x + 76, rect.y + 28), MUTED, 13)
            self._button(surf, pygame.Rect(rect.x + 76, rect.bottom - 40, 80, 32), "Save", "save_slot", i, size=14)
            self._button(surf, pygame.Rect(rect.x + 166, rect.bottom - 40, 80, 32), "Wear", "wear_slot", i,
                         disabled=not entry, size=14)
        y = area.y + 44 + 3 * 102 + 4
        self._text(surf, "Owned sets", (area.x + 18, y), GOLD, 15, bold=True)
        owned_sets = [s for s in self._set_order() if self._set_state(s)[1]]
        if not owned_sets:
            self._text(surf, "Buy a set and it appears here, ready to wear in one click.", (area.x + 18, y + 26), MUTED, 13)
        for k, sid in enumerate(owned_sets):
            rect = pygame.Rect(area.x + 14 + k * 76, y + 22, 70, 120)
            pygame.draw.rect(surf, NAVY, rect, border_radius=8)
            regalia_lost = self._set_state(sid)[2]
            pygame.draw.rect(surf, LOCK_GREY if regalia_lost else GOLD_DIM, rect, 1, border_radius=8)
            thumb = self._set_thumb(sid, "s", (44, 84))
            if thumb:
                surf.blit(thumb, (rect.centerx - thumb.get_width() // 2, rect.y + 6))
            self._text(surf, self._wrap(self._sets()[sid]["name"], 66, 12)[0], (rect.centerx, rect.bottom - 26), INK, 12,
                       centre=True)
            if regalia_lost:
                self._text(surf, "Regalia", (rect.centerx, rect.bottom - 13), LOCK_GREY, 11, centre=True)
            self.hit.append(("wear_set", rect, sid))

    def _outfit_name(self, look):
        return (_by_id(look.get("outfit")) or {}).get("name") or "Everyday clothes"

    def _look_thumb(self, look, size):
        key = ("look", self.sex, tuple(sorted((k, str(v)) for k, v in look.items())), size)
        if key not in self._thumbs:
            import player_hd_client
            canvas = pygame.Surface((200, 260), pygame.SRCALPHA)
            player_hd_client.draw_player(canvas, self.sex, self._full_look(look), 100, 240, 160, 0.0, anim="idle", facing="s")
            self._thumbs[key] = self._fit_image(canvas, size)
        return self._thumbs[key]

    # ---- detail panel -------------------------------------------------------------------------
    def _draw_detail(self, surf):
        rect = DETAIL
        pygame.draw.rect(surf, NAVY_CARD, rect, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, rect, 1, border_radius=12)
        item = _by_id(self.focus_item) if self.tab in ("head", "accessories") else None
        if item and not ((self.tab == "head" and item.get("slot") == "head")
                         or (self.tab == "accessories" and item.get("slot") in ("cloak", "jewellery", "bundle"))):
            item = None
        coll = self._coll(self.focus_coll) if self.tab == "sets" and self.focus_coll else None
        if coll:
            self._draw_coll_detail(surf, DETAIL, coll)
            return
        set_id = (item or {}).get("set") if item else (self.focus_set if self.tab in ("sets", "wardrobe") else None)
        entry = self._sets().get(set_id) if set_id else None
        x, y, w = rect.x + 12, rect.y + 12, rect.w - 24
        coins = self._spendable()
        if entry:
            info, own_all, _regalia_lost = self._set_state(set_id)
            name = item.get("name") if item else entry["name"]
            rows = self._wrap(name, w, 21)[:2]
            for k, row in enumerate(rows):
                self._text(surf, row, (rect.centerx, y + k * 25), GOLD_HI, 21, bold=True, centre=True)
            y += 26 * len(rows) + 4
            base = int((item or entry).get("price") or 0)
            price = 0 if (item and self._free_regalia(item)) else self._price(base)
            owned_here = (item["id"] in self._owned()) if item else own_all
            label = "Owned" if owned_here else f"{price:,} coins"
            lw = self._font(17, True).size(label)[0]
            self._coin(surf, (rect.centerx - lw // 2 - 14, y + 10))
            self._text(surf, label, (rect.centerx + 4, y), GOLD if owned_here or coins >= price else SHORT_RED, 17,
                       bold=True, centre=True)
            y += 28
            ok = info.get("state") == "unlocked"
            line = self._unlock_line(set_id, info)
            if ok:
                self._tick(surf, (x, y + 2))
            else:
                self._padlock(surf, (x + 6, y + 9), 0.65)
            rows = self._wrap(line, w - 20, 13)[:3]
            for k, row in enumerate(rows):
                self._text(surf, row, (x + 20, y + k * 15), INK if ok else MUTED, 13)
            y += 15 * len(rows) + 6
            if not ok and info.get("progress"):
                self._text(surf, f"Progress {info['progress']}", (x + 20, y - 2), GOLD, 13)
                y += 16
            if ok and not owned_here and coins < price:
                self._text(surf, f"You need {price - coins:,} more (purse + bank).", (x, y - 2), SHORT_RED, 13)
                y += 16
            flags = self._painted(set_id)
            painted = [n for k, n in (("head", "crown"), ("neck", "necklace"), ("cloak", "cloak")) if flags.get(k)]
            if painted:
                for k, row in enumerate(self._wrap("Painted in: " + ", ".join(painted), w, 13)[:2]):
                    self._text(surf, row, (x, y + k * 15), MUTED, 13)
                y += 34
            self._text(surf, "Shown as painted · no colour options", (x, y), MUTED, 12)
            y += 20
            jmax = 2
            self._text(surf, f"Jewellery {len(self.look.get('jewellery') or [])}/{jmax}", (x, y + 2), INK, 13)
        elif item:
            rows = self._wrap(item.get("name") or "", w, 19)[:2]
            for k, row in enumerate(rows):
                self._text(surf, row, (rect.centerx, y + k * 23), GOLD_HI, 19, bold=True, centre=True)
            y += 24 * len(rows) + 6
            label, colour = self._price_label(item, coins)
            self._text(surf, label, (rect.centerx, y), colour, 16, centre=True)
            y += 28
            why = self._overlay_block(item)
            if why:
                for k, row in enumerate(self._wrap(why, w, 13)[:2]):
                    self._text(surf, row, (x, y + k * 15), LOCK_GREY, 13)
            elif item.get("overlay") and not item.get("layer") and not item.get("hd_jewellery") and not item.get("bundle"):
                for k, row in enumerate(self._wrap("Overlay art arriving soon; saved with your look.", w, 12)[:2]):
                    self._text(surf, row, (x, y + k * 14), MUTED, 12)
        elif self.tab == "body":
            tone = next((t for t in _catalogue().get("skin_palette") or [] if t["id"] == self.look.get("skin_tone")), {})
            self._text(surf, "Skin tone", (rect.centerx, y), GOLD_HI, 21, bold=True, centre=True)
            pygame.draw.circle(surf, _hex(tone.get("hex")), (rect.centerx, y + 56), 22)
            pygame.draw.circle(surf, GOLD, (rect.centerx, y + 56), 25, 2)
            self._text(surf, tone.get("name", ""), (rect.centerx, y + 86), INK, 16, centre=True)
            self._text(surf, "Free. Carries across every", (rect.centerx, y + 112), MUTED, 13, centre=True)
            self._text(surf, "outfit and the wardrobe.", (rect.centerx, y + 128), MUTED, 13, centre=True)
        else:
            self._text(surf, self._tab_label(self.tab), (rect.centerx, y), GOLD_HI, 21, bold=True, centre=True)
            self._text(surf, "Pick a piece to see it here.", (rect.centerx, y + 34), MUTED, 13, centre=True)
        if entry and not item:
            self._detail_picture(surf, rect, self._set_thumb(set_id, "s", (rect.w - 40, 160)))
        elif item:
            self._detail_picture(surf, rect, self._item_picture(item, (rect.w - 40, 160)))
        back = pygame.Rect(rect.x + 10, rect.bottom - 132, rect.w - 20, 122)
        pygame.draw.rect(surf, NAVY, back, border_radius=8)
        pygame.draw.rect(surf, GOLD_DIM, back, 1, border_radius=8)
        import player_hd_client
        canvas = pygame.Surface((200, 260), pygame.SRCALPHA)
        player_hd_client.draw_player(canvas, self.sex, self._preview_look(), 100, 240, 160, 0.0, anim="idle", facing="n")
        img = self._fit_image(canvas, (back.w - 16, back.h - 12))
        if img:
            surf.blit(img, (back.centerx - img.get_width() // 2, back.bottom - 6 - img.get_height()))
        self._text(surf, "Back", (back.x + 8, back.y + 6), MUTED, 12)

    def _draw_coll_detail(self, surf, rect, entry):
        x, y, w = rect.x + 12, rect.y + 12, rect.w - 24
        for k, row in enumerate(self._wrap(entry.get("name") or "", w, 21)[:2]):
            self._text(surf, row, (rect.centerx, y + k * 25), GOLD_HI, 21, bold=True, centre=True)
        y += 58
        live = self._coll_live(entry)
        self._text(surf, ((entry.get("element") or "").title() + " · elemental line").strip(" ·"),
                   (rect.centerx, y), MUTED, 13, centre=True)
        y += 24
        if live:
            price = self._price(int(entry.get("price") or 0))
            owned = entry["id"] in self._owned()
            self._text(surf, "Owned" if owned else f"{price:,} coins", (rect.centerx, y), GOLD, 17, bold=True, centre=True)
            y += 26
            need = "Needs its story tier" if entry.get("tier") else "Buy only, no story gate"
            self._text(surf, need, (x, y), INK, 13)
        else:
            self._padlock(surf, (rect.centerx, y + 16), 1.2, LOCK_GREY)
            y += 44
            self._text(surf, "Coming soon", (rect.centerx, y), GOLD, 18, bold=True, centre=True)
            y += 28
            for k, row in enumerate(self._wrap("Not released yet: no preview and no Buy. A paid painted design with "
                                               "its own animated effect.", w, 13)[:5]):
                self._text(surf, row, (x, y + k * 16), MUTED, 13)
        y += 16 * 5 if not live else 40
        box = pygame.Rect(rect.x + 12, y + 6, rect.w - 24, rect.bottom - 14 - (y + 6))
        pic = self._coll_picture(entry, (box.w - 8, box.h - 8))
        if pic is None:
            pic = self._silhouette(entry, (box.w - 8, box.h - 8))
        if pic:
            frame = pygame.Rect(0, 0, pic.get_width() + 6, pic.get_height() + 6)
            frame.midbottom = (box.centerx, box.bottom)
            pygame.draw.rect(surf, NAVY, frame, border_radius=6)
            surf.blit(pic, (frame.x + 3, frame.y + 3))
            pygame.draw.rect(surf, GOLD if live else LOCK_GREY, frame, 1, border_radius=6)
            if not live:     # still locked: badge over the picture, Buy stays disabled
                tag = pygame.Rect(0, 0, frame.w - 20, 26)
                tag.midbottom = (frame.centerx, frame.bottom - 8)
                shade = pygame.Surface(tag.size, pygame.SRCALPHA)
                shade.fill((6, 8, 16, 205))
                surf.blit(shade, tag)
                self._padlock(surf, (tag.x + 14, tag.centery), 0.6, GOLD)
                self._text(surf, "Coming soon", (tag.centerx + 8, tag.y + 5), GOLD, 14, bold=True, centre=True)

    def _coll_picture(self, entry, size):
        """The design's painted card (OUTFITS/sidebar/elemental) for the detail panel, live or coming soon."""
        key = ("collpic", entry["id"], size)
        if key not in self._sil:
            img = None
            for path in (os.path.join(_BASE, "collection", "elemental", entry["id"] + ".jpg"),
                         os.path.join(_BASE, "collection", entry["id"] + ".png")):
                try:
                    raw = pygame.image.load(path)
                    raw = raw.convert() if pygame.display.get_surface() else raw
                    k = min(size[0] / raw.get_width(), size[1] / raw.get_height())
                    img = pygame.transform.smoothscale(raw, (max(1, int(raw.get_width() * k)),
                                                             max(1, int(raw.get_height() * k))))
                    break
                except (pygame.error, FileNotFoundError, OSError):
                    continue
            self._sil[key] = img
        return self._sil[key]

    def _item_picture(self, item, size):
        """Picture for a selected head/accessory/jewellery piece: painted card, else the worn render."""
        key = ("itempic", self.sex, item.get("id"), size)
        if key in self._thumbs:
            return self._thumbs[key]
        img = None
        ids = list(item.get("bundle") or [item.get("id")])
        try:
            import jewellery as _jw
            cards = []
            for pid in ids:
                jit = _jw.item(pid)
                if jit and "bundle" not in jit and os.path.exists(_jw.card_path(pid)):
                    cards.append(pygame.image.load(_jw.card_path(pid)))
            if cards:
                cw = size[0] // len(cards)
                out = pygame.Surface((cw * len(cards), min(size[1], cw)), pygame.SRCALPHA)
                for k, c in enumerate(cards):
                    c = pygame.transform.smoothscale(c, (min(cw, out.get_height()),) * 2)
                    out.blit(c, (k * cw + (cw - c.get_width()) // 2, 0))
                img = out
        except Exception as e:
            print("item picture:", e)
        if img is None:
            th = self._thumb(item)
            if th is not None:
                k = min(size[0] / th.get_width(), size[1] / th.get_height())
                img = pygame.transform.smoothscale(th, (int(th.get_width() * k), int(th.get_height() * k)))
        if img is None:      # no strip yet: the same drawn icon the grid card shows, larger
            img = pygame.Surface((min(size), min(size)), pygame.SRCALPHA)
            try:
                self._placeholder_icon(img, item, img.get_rect().inflate(-16, -16))
            except Exception as e:
                print("placeholder picture:", e)
                img = None
        self._thumbs[key] = img
        return img

    def _detail_picture(self, surf, rect, img):
        if img is None:
            return
        area = pygame.Rect(rect.x + 12, rect.bottom - 312, rect.w - 24, 172)
        frame = pygame.Rect(0, 0, min(area.w, img.get_width() + 8), min(area.h, img.get_height() + 8))
        frame.center = area.center
        pygame.draw.rect(surf, NAVY, frame, border_radius=6)
        pygame.draw.rect(surf, GOLD_DIM, frame, 1, border_radius=6)
        surf.blit(img, (frame.centerx - img.get_width() // 2, frame.centery - img.get_height() // 2))

    def _unlock_line(self, set_id, info):
        tier = int((self._sets().get(set_id) or {}).get("tier") or 1)
        if info.get("state") == "unlocked":
            female = self.sex == "female"
            return {1: "Open to everyone", 2: "Respected standing", 3: ("Dame" if female else "Knight") + " rank",
                    4: ("Countess" if female else "Count") + " rank",
                    5: "Court Favour 500" if female else "Count, Revered, guild officer",
                    6: "Consort or Acclaim-ready" if female else "Prince Consort",
                    7: "Reigning Queen" if female else "Reigning King"}.get(tier, "Unlocked")
        return info.get("hint") or self._short_hint(set_id, info)

    # ---- bottom bar ---------------------------------------------------------------------------
    def _draw_bar(self, surf):
        purse = int(self._player().get("coins") or 0)
        bank = int(self._player().get("bank_coins") or 0)
        coins = purse + bank
        self._coin(surf, (44, BAR_Y + 48), 11)
        self._text(surf, f"{coins:,} coins", (62, BAR_Y + 30), INK, 18, bold=True)
        self._text(surf, f"purse {purse:,} · bank {bank:,}", (62, BAR_Y + 52), MUTED, 12)
        self._toggle(surf, 200, BAR_Y + 32, "Compare (Tab)", self.compare, "compare")
        q = self._quote()
        n = len(q["new"]) + len(q["extras"])
        mult, disc, cap, rate = self._pricing()
        pct = int(round((1.0 - max(1.0 - cap, mult * (1.0 - disc))) * 100))
        who = self._player().get("royal_title") or self._player().get("noble_title") or "standing"
        disc_txt = f"\u2212{pct}% {who}, " if pct > 0 else (f"+{-pct}% standing, " if pct < 0 else "")
        if n:
            trying = (f"Trying on: {n} piece{'s' if n != 1 else ''} \u00b7 Total {q['total'] + q['tax']:,} "
                      f"({disc_txt}tax {int(round(rate * 100))}%)")
        else:
            trying = "Trying on: nothing new \u00b7 owned items are free to wear"
        self._text(surf, trying, (200, BAR_Y + 6), INK, 14)
        if q["locked"]:
            chip = pygame.Rect(200 + self._font(14).size(trying)[0] + 14, BAR_Y + 4, 176, 22)
            pygame.draw.rect(surf, (60, 40, 30), chip, border_radius=11)
            pygame.draw.rect(surf, SHORT_RED, chip, 1, border_radius=11)
            self._padlock(surf, (chip.x + 14, chip.centery + 1), 0.55, INK)
            self._text(surf, "Locked \u2014 preview only", (chip.x + 26, chip.y + 3), INK, 13)
        x = 556
        for kind, label, width in (("random", "Randomise", 110), ("reset", "Reset", 90), ("save_current", "Save outfit", 120)):
            self._button(surf, pygame.Rect(x, BAR_Y + 32, width, 40), label, kind, size=16)
            x += width + 10
        soon = bool(self.focus_coll) and not self._coll_live(self._coll(self.focus_coll) or {}) and self.tab == "sets"
        disabled = soon or bool(q["locked"]) or (n > 0 and q["total"] + q["tax"] > coins)
        self._button(surf, pygame.Rect(x, BAR_Y + 28, 1172 - x - 4, 48), "Buy & Wear" if n else "Wear", "buy",
                     primary=True, disabled=disabled, size=20)

    def _draw_modal(self, surf):
        self.hit = [h for h in self.hit if h[0].startswith("modal_")]
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surf.blit(shade, (0, 0))
        box = pygame.Rect(0, 0, 380, 160)
        box.center = (600, 400)
        pygame.draw.rect(surf, NAVY, box, border_radius=12)
        pygame.draw.rect(surf, GOLD, box, 2, border_radius=12)
        self._text(surf, "Discard changes?", (box.centerx, box.y + 22), GOLD_HI, 22, bold=True, centre=True)
        self._text(surf, "You have try-ons you haven't bought or saved.", (box.centerx, box.y + 58), MUTED, 14, centre=True)
        self._button(surf, pygame.Rect(box.x + 30, box.bottom - 56, 150, 40), "Keep shopping", "modal_keep")
        self._button(surf, pygame.Rect(box.right - 180, box.bottom - 56, 150, 40), "Discard", "modal_discard", primary=True)

    # ---- creator (starters only, plus the 10 skin tones) ----------------------------------------
    def _render_creator(self, surf):
        panel = pygame.Rect(40, 30, 1120, 740)
        pygame.draw.rect(surf, NAVY, panel, border_radius=14)
        pygame.draw.rect(surf, GOLD, panel, 2, border_radius=14)
        pygame.draw.rect(surf, GOLD_DIM, panel.inflate(-8, -8), 1, border_radius=12)
        self._text(surf, "Create your adventurer", (72, 46), GOLD, 30, bold=True)
        self._text(surf, "Choose how you look. You can change it later at Mythos Outfitters.", (72, 86), MUTED, 15)
        pygame.draw.line(surf, GOLD_DIM, (60, 120), (1140, 120), 1)
        self._draw_creator_stage(surf)
        y = 136
        for key, label in _CREATOR_TABS:
            rect = pygame.Rect(480, y, 150, 44)
            active = key == self.tab
            pygame.draw.rect(surf, NAVY_HI if active else NAVY_CARD, rect, border_radius=8)
            pygame.draw.rect(surf, GOLD if active else GOLD_DIM, rect, 1, border_radius=8)
            if active:
                pygame.draw.rect(surf, GOLD, (rect.x, rect.y + 8, 4, rect.h - 16))
            self._text(surf, label, (rect.x + 16, rect.y + 12), INK if active else MUTED, 17)
            self.hit.append(("tab", rect, key))
            y += 50
        grid = pygame.Rect(650, 136, 490, 554)
        pygame.draw.rect(surf, NAVY_CARD, grid, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, grid, 1, border_radius=12)
        if self.tab == "body":
            self._draw_body_tab(surf, grid)
        elif self.tab == "hair_colour":
            self._text(surf, "Hair colour", (grid.x + 16, grid.y + 12), GOLD, 18, bold=True)
            for i, colour in enumerate(_catalogue().get("hair_palette") or []):
                cell = pygame.Rect(grid.x + 30 + (i % 5) * 88, grid.y + 60 + (i // 5) * 88, 72, 72)
                pygame.draw.circle(surf, tuple(colour.get("mul") or (80, 80, 80)), cell.center, 24)
                if self.look.get("hair_colour") == colour.get("id"):
                    pygame.draw.circle(surf, GOLD, cell.center, 28, 3)
                self.hit.append(("colour", cell, colour.get("id")))
        else:
            self._text(surf, dict(_CREATOR_TABS)[self.tab], (grid.x + 16, grid.y + 12), GOLD, 18, bold=True)
            for i, item in enumerate(_visible_items(self.sex, self.tab)):
                rect = pygame.Rect(grid.x + 14 + (i % 4) * 120, grid.y + 44 + (i // 4) * 150, 108, 140)
                selected = self._is_selected(item)
                pygame.draw.rect(surf, NAVY, rect, border_radius=8)
                pygame.draw.rect(surf, GOLD if selected else GOLD_DIM, rect, 3 if selected else 1, border_radius=8)
                thumb = self._thumb(item)
                if thumb:
                    surf.blit(thumb, (rect.centerx - thumb.get_width() // 2, rect.y + 8))
                self._text(surf, self._wrap(item.get("name") or "", 100, 14)[0], (rect.centerx, rect.bottom - 40), INK, 14,
                           centre=True)
                starter = item.get("starter")
                self._text(surf, "Free" if starter else "In shop", (rect.centerx, rect.bottom - 20),
                           SAFE_GREEN if starter else MUTED, 13, centre=True)
                self.hit.append(("item", rect, item))
        pygame.draw.line(surf, GOLD_DIM, (60, 702), (1140, 702), 1)
        self._text(surf, "Everything here is free. More styles at Mythos Outfitters in the village.", (60, 716), MUTED, 14)
        self._text(surf, "Skip uses the basic look for your body type.", (60, 736), MUTED, 14)
        x = 616
        for kind, label, primary in (("random", "Randomise", False), ("reset", "Reset", False), ("skip", "Skip", False),
                                     ("confirm", "Confirm look", True)):
            width = 150 if primary else 110
            self._button(surf, pygame.Rect(x, 718, width, 36), label, kind, primary=primary)
            x += width + 10

    def _draw_creator_stage(self, surf):
        stage = pygame.Rect(60, 136, 400, 554)
        pygame.draw.rect(surf, NAVY_CARD, stage, border_radius=12)
        pygame.draw.rect(surf, GOLD_DIM, stage, 1, border_radius=12)
        feet = stage.bottom - 150
        ped = pygame.Rect(stage.centerx - 70, feet + 2, 140, 30)
        pygame.draw.ellipse(surf, (32, 26, 22), ped)
        self._blit_stage_player(surf, stage.centerx, feet, _FACINGS[self.facing_i][0])
        pygame.draw.ellipse(surf, GOLD, ped, 2)
        pill = pygame.Rect(stage.centerx - 78, stage.y + 16, 156, 32)
        pygame.draw.rect(surf, NAVY, pill, border_radius=16)
        pygame.draw.rect(surf, GOLD_DIM, pill, 1, border_radius=16)
        for k, (label, sex) in enumerate((("Male", "male"), ("Female", "female"))):
            seg = pygame.Rect(pill.x + 4 + k * 76, pill.y + 4, 72, 24)
            if sex == self.sex:
                pygame.draw.rect(surf, GOLD, seg, border_radius=12)
            self._text(surf, label, (seg.centerx, seg.y + 4), NAVY if sex == self.sex else INK, 14, centre=True)
        self.hit.append(("sex", pill, None))
        for rect, step, glyph in ((pygame.Rect(stage.x + 24, stage.bottom - 58, 36, 36), -1, "<"),
                                  (pygame.Rect(stage.right - 60, stage.bottom - 58, 36, 36), 1, ">")):
            pygame.draw.circle(surf, NAVY, rect.center, 16)
            pygame.draw.circle(surf, GOLD, rect.center, 16, 1)
            self._text(surf, glyph, (rect.centerx, rect.y + 8), GOLD, 16, centre=True)
            self.hit.append(("turn", rect, step))
        self._text(surf, "Drag or use arrows to turn", (stage.centerx, stage.bottom - 72), MUTED, 13, centre=True)
        self._text(surf, _FACINGS[self.facing_i][1], (stage.centerx, stage.bottom - 48), GOLD, 15, centre=True)

    # ---- shared ------------------------------------------------------------------------------
    def _is_selected(self, item):
        slot = item.get("slot")
        if slot == "accessory":
            return item.get("id") in (self.look.get("accessories") or [])
        if slot == "jewellery":
            return item.get("id") in (self.look.get("jewellery") or [])
        if not item.get("id"):
            return not self.look.get(slot)
        if slot == "skin":
            return True
        return self.look.get(slot) == item.get("id")

    def _card_sparkle(self, surf, item, rect):
        """Hover preview: the piece's gem glints (Full sparkle, max 2 lit) over the card art."""
        try:
            import jewellery as J
            src = J.item(item.get("id")) or {}
            pts = (src.get("sparkle_points") or {}).get("s") or []
            fx = item.get("fx") or src.get("fx") or {}
            if not pts:
                return
            w60, h60 = src.get("size60") or (1, 1)
            box = rect.inflate(-16, -16)
            sc = min(box.w / float(w60), box.h / float(h60))
            rect = pygame.Rect(0, 0, int(w60 * sc), int(h60 * sc))
            rect.center = box.center
            loop = float(fx.get("loop_s") or 1.8)
            phase = (time.time() % loop) / loop
            for k, p in enumerate(pts):
                ph = (phase + k / max(1, len(pts))) % 1.0
                if ph > 0.34 or k >= 6:
                    continue
                a = math.sin(ph / 0.34 * math.pi)
                x = rect.x + p[0] * rect.w
                y = rect.y + p[1] * rect.h
                r = 2 + 5 * a
                col = (255, 255, 255)
                pygame.draw.line(surf, col, (x - r, y), (x + r, y), 1)
                pygame.draw.line(surf, col, (x, y - r), (x, y + r), 1)
                pygame.draw.circle(surf, col, (int(x), int(y)), max(1, int(1.6 * a)))
        except Exception as e:
            print("card sparkle:", e)

    def _thumb(self, item):
        if item.get("hd_jewellery") and item.get("card"):
            k = ("card", item["id"])
            if k not in self._thumbs:
                try:
                    import player_hd_client
                    img = pygame.image.load(os.path.join(player_hd_client._BASE, item["card"])).convert_alpha()
                    self._thumbs[k] = pygame.transform.smoothscale(img, (96, 96))
                except Exception as e:
                    print("card load:", e)
                    self._thumbs[k] = None
            return self._thumbs[k]
        key = ("item", self.sex, item.get("id"), self.look.get("hair_colour"), self.look.get("skin_tone"),
               self.look.get("palette"))
        if key in self._thumbs:
            return self._thumbs[key]
        import player_hd_client
        slot = item.get("slot")
        if slot in ("head", "jewellery", "held") and not player_hd_client.resolve_layer(item, self.sex)[0]:
            self._thumbs[key] = None          # drawn icon until the strip lands
            return None
        look = self._copy(self.look)
        if slot == "accessory":
            look["accessories"] = [item["id"]]
        elif slot == "jewellery":
            look["jewellery"] = [item["id"]]
        elif slot:
            look[slot] = item["id"]
            if slot in ("top", "bottom"):
                look["outfit"] = None
        if item.get("palettes") and look.get("palette") not in item["palettes"]:
            look["palette"] = item["palettes"][0]
        canvas = pygame.Surface((160, 200), pygame.SRCALPHA)
        player_hd_client.draw_player(canvas, self.sex, look, 80, 186, 120, 0.0, anim="idle", facing="s",
                                     starter=False)
        box = canvas.get_bounding_rect()
        if box.w < 4 or box.h < 4:
            self._thumbs[key] = None
            return None
        crop = _CROPS.get(slot, (0.2, 0.1, 0.6, 0.7))
        rect = pygame.Rect(box.x + int(box.w * crop[0]), box.y + int(box.h * crop[1]),
                           max(8, int(box.w * crop[2])), max(8, int(box.h * crop[3]))).clamp(canvas.get_rect())
        self._thumbs[key] = self._fit_image(canvas.subsurface(rect).copy(), (96, 86))
        return self._thumbs[key]
