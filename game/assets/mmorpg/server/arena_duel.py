"""Crownfall boss duels: the player alone vs a gladiator champion.

Soldier battles (practice / ranked / roster) stay in mercenaries.tick_live_match; only
foe ids "boss:<tier>" become duels. All numbers live in duel_tuning.json.

Model: one lane, distance `gap` in tiles between player and boss. Time runs in steps
(200 ms, 3 per server tick). The boss telegraphs every attack (wind-up steps); the player
answers with light / heavy / parry / dodge / back / forward / finish. Bows kite: shots
need distance, focus builds while standing still, charged shots use it.
Momentum (the crowd) fills from clean play; at boss HP <= finisher frac and full momentum
the player may FINISH -> finishing-move cinematic (blade or arrow).
"""
from __future__ import annotations

import json
import os
import random

_TUNING_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duel_tuning.json")
_T = None

ACTIONS = ("light", "heavy", "parry", "dodge", "back", "forward", "finish")


def tuning(reload=False):
    global _T
    if _T is None or reload:
        with open(_TUNING_PATH, encoding="utf-8") as f:
            _T = json.load(f)
    return _T


def set_tuning(t):
    """Tests / sim may inject a modified table."""
    global _T
    _T = t


def style_for_weapon(item: dict | None) -> str:
    item = item or {}
    if item.get("ranged_att") or item.get("ranged_str") or "bow" in str(item.get("id", "")):
        return "bow"
    name = (str(item.get("id", "")) + " " + str(item.get("name", ""))).lower()
    if "axe" in name or "maul" in name or "hammer" in name:
        return "axe"
    return "sword"


# --- State -------------------------------------------------------------------------------
def new_duel(boss_id: str, style: str = "sword", level_ratio: float = 1.0, gear: str = "steel",
             defence_ratio: float = 1.0, seed: int | None = None) -> dict:
    T = tuning()
    lv = T["level"]
    mult = max(lv["min_mult"], min(lv["max_mult"], level_ratio)) * T["gear_mult"].get(gear, 1.0)
    cut = max(0.0, min(lv["defence_cut_max"], (defence_ratio - 1.0) * 0.5 + 0.1))
    return {
        "boss_id": boss_id, "style": style, "step": 0, "gap": float(T["start_gap"]),
        "rng": random.Random(seed),
        "p": {"hp": 1.0, "sta": float(T["stamina"]["max"]), "busy": 0, "parry": 0, "parry_age": 0,
              "iframes": 0, "wind": None, "focus": 0.0, "counter": 0, "root": 0, "stun": 0,
              "since_spend": 99, "wall": float(T["arena_len"]) - float(T["start_gap"]), "dmg_mult": mult, "def_cut": cut, "queued": None},
        "b": {"hp": 1.0, "state": "think", "t": 3, "atk": None, "guard": 0, "second_wind_used": False,
              "face": "w"},
        "momentum": 0.0, "finisher_ready": False, "done": False, "won": None, "finisher": None,
        "stats": {"parries": 0, "perfect_parries": 0, "dodges": 0, "perfect_dodges": 0, "hits": 0, "taken": 0},
        "events": [],
    }


def _style(d):
    return tuning()["styles"][d["style"]]


def _boss(d):
    return tuning()["bosses"][d["boss_id"]]


def _ev(d, kind, **kw):
    kw["kind"] = kind
    kw["step"] = d["step"]
    d["events"].append(kw)


def _mom(d, key, scale=1.0):
    M = tuning()["momentum"]
    mult = float(_boss(d).get("momentum_mult_" + d["style"], _boss(d).get("momentum_mult", 1.0))) * float(_style(d).get("momentum_mult", 1.0)) * scale
    gain = M[key] * (mult if M[key] > 0 else 1.0)
    d["momentum"] = max(0.0, min(float(M["max"]), d["momentum"] + gain))


def act(d, action: str) -> bool:
    """Queue a player action; applied on the next step the player is free."""
    if action not in ACTIONS or d["done"]:
        return False
    d["p"]["queued"] = action
    return True


def telegraph(d) -> dict | None:
    b = d["b"]
    if b["state"] != "windup":
        return None
    a = b["atk"]
    return {"id": a["id"], "left": b["t"], "parry": bool(a.get("parry")), "reach": a["reach"]}


# --- Player ------------------------------------------------------------------------------
def _spend(d, cost):
    p = d["p"]
    if p["sta"] < cost:
        return False
    p["sta"] -= cost
    p["since_spend"] = 0
    return True


def _move(d, sign):
    S = _style(d)
    T = tuning()
    if d["p"]["root"] > 0 or not _spend(d, S["move"]["sta"]):
        return
    p = d["p"]
    dx = S["move"]["speed"] * sign
    if sign > 0:
        dx = min(dx, p["wall"])
        if dx <= 0:
            _ev(d, "cornered")
            return
    elif d["gap"] - S["move"]["speed"] < 0.6:
        return
    p["wall"] = max(0.0, min(T["arena_len"], p["wall"] - dx))
    d["gap"] = max(0.6, d["gap"] + dx)
    if S.get("focus"):
        d["p"]["focus"] *= (1 - S["focus"]["lost_on_move"])


def _damage_boss(d, frac, tag):
    b = d["b"]
    B = _boss(d)
    p = d["p"]
    S = _style(d)
    frac *= p["dmg_mult"]
    if S["ranged"]:
        frac *= B.get("shot_taken", 1.0)  # armour vs arrows at any range
        if d["gap"] >= S["focus"]["far_gap"]:
            frac *= S["focus"]["far_mult"] * B.get("far_shot_taken", 1.0)
    if p["counter"] > 0:
        frac *= S["counter"]["mult"]
        p["counter"] = 0
        _mom(d, "counter_hit")
        tag += "_counter"
    if b["guard"] > 0 and not S["ranged"] or (b["guard"] > 0 and S["ranged"] and d["gap"] < S["focus"]["far_gap"]):
        cut = B.get("guard_cut_heavy", 0.0) if tag.startswith("heavy") else B.get("guard_cut", 0.0)
        if cut:
            frac *= (1 - cut)
            tag += "_guarded"
    if b["state"] == "stagger":
        frac *= 1.25
    b["hp"] = max(0.0, b["hp"] - frac)
    d["stats"]["hits"] += 1
    ref = float(tuning()["momentum"].get("hit_ref_dmg", 0) or 0)
    _mom(d, "hit", max(0.8, min(2.5, frac / ref)) if ref else 1.0)  # bigger blows, louder crowd
    _ev(d, "boss_hit", dmg=round(frac, 4), tag=tag)
    if b["hp"] <= 0:
        if B.get("second_wind") and not b["second_wind_used"]:
            b["second_wind_used"] = True
            b["hp"] = float(B["second_wind"])
            d["momentum"] *= float(B.get("second_wind_momentum", 1.0))  # the crowd gasps: earn the finish again
            b["state"], b["t"] = "stagger", 4
            _ev(d, "second_wind")
        else:
            _end(d, True, None)


def _resolve_player_wind(d):
    p = d["p"]
    S = _style(d)
    kind = p["wind"]
    p["wind"] = None
    H = S["heavy"]
    if S["ranged"]:
        if d["gap"] < S["light"]["min_gap"]:
            mult = S["light"]["close_mult"]
        else:
            mult = 1.0
        f = p["focus"]
        if f >= 0.99:
            _mom(d, "focus_shot")
        _damage_boss(d, H["dmg"] * (1 + H.get("focus_bonus", 0) * f) * mult, "heavy_shot")
        p["focus"] = 0.0
    else:
        if d["gap"] > S["reach"] + 0.01:
            _ev(d, "whiff")
            return
        if d["b"]["guard"] > 0 and H.get("breaks_guard"):
            d["b"]["guard"] = 0
            d["b"]["state"], d["b"]["t"] = "stagger", 3
            _ev(d, "guard_break")
        _damage_boss(d, H["dmg"], "heavy")


def _player_step(d):
    p = d["p"]
    S = _style(d)
    T = tuning()
    for k in ("iframes", "counter", "root", "stun"):
        if p[k] > 0:
            p[k] -= 1
    if p["parry"] > 0:
        p["parry"] -= 1
        p["parry_age"] += 1
    p["since_spend"] += 1
    if p["since_spend"] > T["stamina"]["regen_delay_steps"]:
        p["sta"] = min(T["stamina"]["max"], p["sta"] + T["stamina"]["regen_per_step"])
    if S.get("focus") and p["wind"] is None and p["busy"] == 0:
        p["focus"] = min(S["focus"]["max"], p["focus"] + S["focus"]["per_step"])
    if p["busy"] > 0:
        p["busy"] -= 1
        if p["busy"] == 0 and p["wind"]:
            _resolve_player_wind(d)
            p["busy"] = S["heavy"]["recover"]
        return
    if p["stun"] > 0:
        return
    a = p["queued"]
    p["queued"] = None
    if not a:
        return
    if a == "finish":
        ranged_ok = S["ranged"] and d["p"]["focus"] >= float(_boss(d).get("bow_focus", T["finisher"].get("bow_focus", 0.0))) - 1e-6
        if d["finisher_ready"] and (ranged_ok or (not S["ranged"] and d["gap"] <= T["finisher"]["melee_reach"] + 0.01)):
            _end(d, True, "arrow" if S["ranged"] else "blade")
        return
    if a in ("back", "forward"):
        _move(d, 1 if a == "back" else -1)
        return
    if a == "light":
        L = S["light"]
        if not S["ranged"] and d["gap"] > S["reach"] + 0.01:
            _move(d, -1)  # close in instead of whiffing
            return
        if not _spend(d, L["sta"]):
            return
        mult = 1.0
        if S["ranged"]:
            if d["gap"] < L["min_gap"]:
                mult = L["close_mult"]
            mult *= 1 + 0.5 * p["focus"]
            p["focus"] = 0.0
        _damage_boss(d, L["dmg"] * mult, "shot" if S["ranged"] else "light")
        p["busy"] = L["recover"]
    elif a == "heavy":
        H = S["heavy"]
        if _spend(d, H["sta"]):
            p["wind"] = "heavy"
            p["busy"] = H["windup"]
            _ev(d, "player_windup", heavy=True)
    elif a == "parry" and S.get("parry"):
        P = S["parry"]
        if _spend(d, P["sta"]):
            p["parry"] = P["active"]
            p["parry_age"] = 0
            p["busy"] = P["recover"]
    elif a == "dodge":
        D = S["dodge"]
        if p["root"] == 0 and _spend(d, D["sta"]):
            p["iframes"] = D["iframes"]
            p["busy"] = D["recover"]
            p["wind"] = None
            sh = min(D["shift"], p["wall"])
            p["wall"] -= sh
            d["gap"] += sh
            _ev(d, "dodge")


# --- Boss --------------------------------------------------------------------------------
def _pick_attack(d):
    B = _boss(d)
    rng = d["rng"]
    opts = [a for a in B["attacks"]
            if d["gap"] <= a["reach"] + 0.5 and d["gap"] >= a.get("min_gap", 0)]
    if not opts:
        return None
    return rng.choices(opts, weights=[a.get("w", 1) for a in opts])[0]


def _land(d, a):
    p = d["p"]
    S = _style(d)
    if d["gap"] > a["reach"] + 0.01:
        _ev(d, "boss_miss", atk=a["id"])
        return "miss"
    if p["iframes"] > 0:
        d["stats"]["dodges"] += 1
        perfect = p["iframes"] >= S["dodge"]["iframes"]
        if perfect:
            d["stats"]["perfect_dodges"] += 1
            _mom(d, "perfect_dodge")
            p["counter"] = S["counter"]["window"]
        else:
            _mom(d, "dodge")
        _ev(d, "dodged", atk=a["id"], perfect=perfect)
        return "dodged"
    if p["parry"] > 0 and a.get("parry"):
        d["stats"]["parries"] += 1
        perfect = p["parry_age"] < S["parry"]["perfect"] + 1
        if perfect:
            d["stats"]["perfect_parries"] += 1
            _mom(d, "perfect_parry")
        else:
            _mom(d, "parry")
        p["counter"] = S["counter"]["window"]
        p["busy"] = 0
        d["b"]["state"], d["b"]["t"] = "stagger", 4 if perfect else 2
        _ev(d, "parried", atk=a["id"], perfect=perfect)
        return "parried"
    dmg = a["dmg"] * (1 - p["def_cut"])
    if p["wind"]:
        dmg *= 1.3
        p["wind"] = None
        p["busy"] = 0
    p["hp"] = max(0.0, p["hp"] - dmg)
    d["stats"]["taken"] += 1
    _mom(d, "taken_hit")
    if a.get("root"):
        p["root"] = a["root"]
    if a.get("stun"):
        p["stun"] = a["stun"]
    _ev(d, "player_hit", atk=a["id"], dmg=round(dmg, 4))
    if a.get("double") and d["rng"].random() < a["double"] and p["hp"] > 0:
        p["hp"] = max(0.0, p["hp"] - dmg * 0.6)
        _ev(d, "player_hit", atk=a["id"] + "_2", dmg=round(dmg * 0.6, 4))
    if p["hp"] <= 0:
        _end(d, False, None)
    return "hit"


def _boss_step(d):
    b = d["b"]
    B = _boss(d)
    rng = d["rng"]
    if b["guard"] > 0:
        b["guard"] -= 1
    frenzy = B.get("frenzy_below") and b["hp"] < B["frenzy_below"]
    if b["state"] in ("think", "recover", "stagger"):
        b["t"] -= 1
        if b["t"] > 0:
            if b["state"] != "stagger" and d["gap"] > 2.0:
                walk = 1.0 if b["state"] == "think" else tuning().get("recover_walk", 0.0)
                d["gap"] = max(1.6, d["gap"] - B["speed"] * walk)
            return
        a = _pick_attack(d)
        if a is None:
            b["state"], b["t"] = "think", 1
            d["gap"] = max(1.6, d["gap"] - B["speed"])
            return
        if B.get("guard_chance") and b["state"] != "stagger" and rng.random() < B["guard_chance"] and d["gap"] <= 3:
            b["guard"] = B.get("guard_steps", 4)
        b["state"], b["atk"] = "windup", a
        b["t"] = max(2, a["windup"] - (B.get("frenzy_windup_cut", 0) if frenzy else 0))
        _ev(d, "boss_windup", atk=a["id"], steps=b["t"], parry=bool(a.get("parry")))
        return
    if b["state"] == "windup":
        b["t"] -= 1
        if b["t"] > 0:
            return
        a = b["atk"]
        if a.get("lunge_to") is not None:
            if d["p"]["iframes"] == 0:
                d["gap"] = max(a["lunge_to"], 0.6)
        res = _land(d, a)
        if res == "parried":
            return
        lo, hi = B["think_steps"]
        if res == "dodged" and (a.get("lunge_to") is not None or (_style(d)["ranged"] and d["p"]["wall"] < 1.0)):
            # rolled under the charge: the boss thunders past, the player has room again
            T = tuning()
            d["gap"] = max(d["gap"], 2.5)
            d["p"]["wall"] = max(0.0, T["arena_len"] - d["gap"] - d["p"]["wall"])
            _ev(d, "rolled_past")
        rec = a.get("recover", 3) + (6 if res == "dodged" and a.get("lunge_to") is not None else 0)
        b["state"], b["t"] = "recover", rec + rng.randint(0, max(0, hi - lo))


# --- Loop --------------------------------------------------------------------------------
def _end(d, won, finisher):
    if d["done"]:
        return
    d["done"], d["won"], d["finisher"] = True, bool(won), finisher
    _ev(d, "end", won=bool(won), finisher=finisher)


def step(d):
    if d["done"]:
        return
    T = tuning()
    d["step"] += 1
    _player_step(d)
    if not d["done"]:
        _boss_step(d)
    F = T["finisher"]
    Bd = _boss(d)
    sw_open = not Bd.get("second_wind") or d["b"]["second_wind_used"]  # rise again first, then the finish
    if not d["done"] and sw_open and d["b"]["hp"] <= Bd.get("finisher_hp", F["boss_hp_frac"]) \
            and d["momentum"] >= F["momentum"] - 1e-6:
        d["ready_until"] = d["step"] + F["window_steps"]
    d["finisher_ready"] = not d["done"] and d["step"] <= d.get("ready_until", -1)
    d["momentum"] = max(0.0, d["momentum"] - T["momentum"]["decay_per_step"])
    if d["step"] >= T["timeout_steps"] and not d["done"]:
        _end(d, d["b"]["hp"] < d["p"]["hp"], None)


def tick(d):
    """One server tick (0.6 s)."""
    d["events"] = []
    for _ in range(tuning()["steps_per_tick"]):
        step(d)
    return list(d["events"])


def public(d) -> dict:
    p, b = d["p"], d["b"]
    return {
        "style": d["style"], "boss_id": d["boss_id"], "gap": round(d["gap"], 2),
        "hp": round(p["hp"], 4), "sta": round(p["sta"], 1), "focus": round(p["focus"], 2),
        "counter": p["counter"] > 0, "rooted": p["root"] > 0, "stunned": p["stun"] > 0,
        "player_wind": bool(p["wind"]), "boss_hp": round(b["hp"], 4), "boss_state": b["state"],
        "boss_guard": b["guard"] > 0, "wall": round(p["wall"], 2), "telegraph": telegraph(d), "momentum": round(d["momentum"], 1),
        "finisher_ready": d["finisher_ready"], "done": d["done"], "won": d["won"], "finisher": d["finisher"],
        "second_wind_used": b["second_wind_used"],
    }


# --- Match glue (mercenaries / server) -----------------------------------------------------
def stage(match, session, entry, player_unit, boss_unit):
    """Turn a staged boss match into a duel: only the player and the champion on the sand."""
    import mercenaries as merc
    w = (getattr(session, "equipment", None) or {}).get("weapon")
    try:
        from content import ITEMS
        item = dict(ITEMS.get(w) or {}, id=w)
    except Exception:
        item = {"id": w}
    style = style_for_weapon(item)
    cl = 3
    try:
        cl = int(session.combat_level())
    except Exception:
        pass
    ratio = cl / max(1, int(entry.get("recommend_cl") or cl))
    d = new_duel(entry["boss"]["id"], style, level_ratio=ratio, gear=_player_gear(session))
    match.update(mode="duel", duel=d, units=[player_unit, boss_unit])
    _place(match)
    return d


def _player_gear(session):
    w = str((getattr(session, "equipment", None) or {}).get("weapon") or "")
    for g in ("mythos", "rune", "adamant", "mithril", "steel", "iron", "bronze"):
        if g in w:
            return g
    return "steel"


def _place(match):
    d = match["duel"]
    cx, cy = match.get("center") or [0, 0]
    you, boss = match["units"][0], match["units"][1]
    half = d["gap"] / 2.0
    you["x"], you["y"] = int(round(cx - half)), int(cy)
    boss["x"], boss["y"] = int(round(cx + half)), int(cy)
    you["facing"], boss["facing"] = "e", "w"
    you["hp"] = max(0, int(round(you["max_hp"] * d["p"]["hp"])))
    boss["hp"] = max(0, int(round(boss["max_hp"] * d["b"]["hp"])))
    you["alive"], boss["alive"] = you["hp"] > 0, boss["hp"] > 0 or not d["done"]


def exchange_line(e: dict, foe: str = "The champion", you: str = "You") -> str | None:
    """Short commentary for one duel event (log strip + chat). None = not worth a line."""
    k = e.get("kind")
    pct = lambda: f"{max(1, int(round(float(e.get('dmg') or 0) * 100)))}%"
    if k == "boss_hit":
        tag = str(e.get("tag") or "")
        if "finish" in tag:
            return f"{you} land the finishing blow!"
        if "counter" in tag:
            return f"Counter! {you} punish {foe} for {pct()}."
        return f"{you} hit {foe} for {pct()}."
    if k == "player_hit":
        return f"{foe} hits you for {pct()}." if not str(e.get("atk", "")).endswith("_2") else None
    return {"parried": f"{'Perfect parry' if e.get('perfect') else 'Parried'} — {foe} is open!",
            "dodged": f"{'Perfect dodge' if e.get('perfect') else 'Dodged'} {foe}'s attack.",
            "boss_miss": f"{foe} swings wide.",
            "guard_break": f"{foe}'s guard breaks!",
            "second_wind": f"{foe} rises with a second wind!",
            "rolled_past": f"{you} roll past {foe}.",
            "cornered": "Your back is to the wall!",
            "whiff": f"{you} swing at empty air.",
            "end": (f"{foe} falls — victory!" if e.get("won") else f"{foe} wins the duel."),
            }.get(k)


def tick_match(match) -> list[dict]:
    """Called by mercenaries.tick_live_match for mode == 'duel'."""
    if match.get("phase") != "fight":
        return []
    d = match["duel"]
    match["tick"] = int(match.get("tick") or 0) + 1
    evs = tick(d)
    _place(match)
    you, boss = match["units"][0], match["units"][1]
    out = []
    for e in evs:
        if e["kind"] == "boss_hit":
            boss["attacking"] = 0
            you["attacking"] = 1.0
            out.append({"type": "COMBAT_EVENT", "attacker_id": you["id"], "defender_id": boss["id"],
                        "damage": max(1, int(round(e["dmg"] * boss["max_hp"]))), "hit": True,
                        "defender_hp": boss["hp"], "defender_max_hp": boss["max_hp"], "kind": "arena",
                        "ranged": d["style"] == "bow"})
        elif e["kind"] == "player_hit":
            boss["attacking"] = 1.0
            out.append({"type": "COMBAT_EVENT", "attacker_id": boss["id"], "defender_id": you["id"],
                        "damage": max(1, int(round(e["dmg"] * you["max_hp"]))), "hit": True,
                        "defender_hp": you["hp"], "defender_max_hp": you["max_hp"], "kind": "arena",
                        "ranged": False})
    foe = str(match.get("foe_name") or "The champion")
    log = match.setdefault("log", [])
    for e in evs:
        line = exchange_line(e, foe)
        if line:
            log.append(line)
    del log[:-24]
    out.append({"type": "ARENA_DUEL", "duel": public(d), "events": evs})
    match["crowd"] = int(d["momentum"])
    if d["done"]:
        match["phase"] = "done"
        match["won"] = bool(d["won"])
        match["finisher"] = d["finisher"]
        match["your_alive"] = 1 if d["p"]["hp"] > 0 else 0
        match["foe_alive"] = 0 if d["won"] else 1
        match["your_hp_left"], match["foe_hp_left"] = you["hp"], boss["hp"]
        match["rounds"] = match["tick"]
    return out
