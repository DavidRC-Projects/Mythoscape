"""
Combat resolution using the classic RuneScape (2001-era) combat formulas.
Strength and strength gear set the highest hit. Attack versus defence
decides how often the roll reaches those higher numbers. A weak attack
mostly lands on 0 instead of missing.

These are standard, publicly documented tabletop-style combat mechanics
(comparable to a dice-game's rules) -- just arithmetic, reimplemented here
from scratch.
"""
import math
import random


def effective_level(level, style_bonus=8):
    """Adds a flat style/prayer-slot bonus the way RS's formula does (no prayers/styles in v0.1, so a fixed +8)."""
    return level + style_bonus


def max_hit(strength_level, strength_bonus=0):
    eff_str = effective_level(strength_level)
    hit = math.floor(0.5 + eff_str * (strength_bonus + 64) / 640)
    return max(1, hit)


def hit_chance(attack_level, attack_bonus, defence_level, defence_bonus):
    eff_att = effective_level(attack_level)
    eff_def = effective_level(defence_level)
    attack_roll = eff_att * (attack_bonus + 64)
    defence_roll = eff_def * (defence_bonus + 64)
    if attack_roll > defence_roll:
        chance = 1 - (defence_roll + 2) / (2 * (attack_roll + 1))
    else:
        chance = attack_roll / (2 * (defence_roll + 1))
    return max(0.02, min(0.98, chance))


def resolve_hit(attacker_stats, defender_stats):
    """
    attacker_stats / defender_stats: dict with keys
        attack, strength, defence, attack_bonus, strength_bonus, defence_bonus
    Returns (damage:int, did_hit:bool)

    Every swing connects. Strength and strength gear set the highest number.
    Attack versus defence decides where the roll lands inside that range:
    a low attack mostly rolls 0, a high attack reaches the higher numbers.
    """
    top = max_hit(attacker_stats["strength"], attacker_stats.get("strength_bonus", 0))
    chance = hit_chance(
        attacker_stats["attack"], attacker_stats.get("attack_bonus", 0),
        defender_stats["defence"], defender_stats.get("defence_bonus", 0),
    )
    # Above 1 crowds the roll near 0. Below 1 crowds it near the strength max.
    exponent = (1.0 - chance) / max(0.08, chance)
    roll = random.random() ** exponent
    dmg = int(math.floor(roll * (top + 1)))
    if dmg > top:
        dmg = top
    return max(0, dmg), True


# --- Skill XP / leveling -----------------------------------------------------
# Simplified RS-style XP curve: level N requires roughly N^3-ish growth.
def xp_for_level(level):
    total = 0
    for lvl in range(1, level):
        total += math.floor(lvl + 300 * (2 ** (lvl / 7.0)))
    return math.floor(total / 4)


LEVEL_XP_TABLE = [xp_for_level(l) for l in range(1, 201)]


def level_from_xp(xp):
    lvl = 1
    for i, threshold in enumerate(LEVEL_XP_TABLE, start=1):
        if xp >= threshold:
            lvl = i
        else:
            break
    return lvl


def xp_to_next_level(xp):
    """XP still needed to reach the next level (0 at max table level)."""
    lvl = level_from_xp(xp)
    if lvl >= len(LEVEL_XP_TABLE):
        return 0
    # LEVEL_XP_TABLE[lvl] == xp required to reach level (lvl + 1)
    return max(0, LEVEL_XP_TABLE[lvl] - int(xp))


def combat_level(attack, strength, defence, hitpoints=1, archery=1):
    """Sum of the three highest among attack, strength, defence, and ranged.

    Hitpoints is not one of the four. The same total is the player's max HP.
    """
    scores = sorted(
        (int(attack), int(strength), int(defence), int(archery)),
        reverse=True,
    )
    return max(1, scores[0] + scores[1] + scores[2])


# Monsters with a dragonfire breath or boss mechanics: stands in for the player's karma term.
ABILITY_MONSTERS = frozenset(("dragon", "nyxarath"))
ABILITY_MULT = 1.10


def monster_combat_level(mdef, monster_type=None):
    """A monster's combat level on the same scale as players (gear never counts).

    base = attack + strength + defence (players: top three of att/str/def/archery; monsters have no archery)
    + round((hp - base) / 10)   tankier or squishier than a player of that level
    + round(def_bonus / 4)      natural hide or armour is the monster's own stat
    x 1 / attack_cooldown       when the cooldown is 1.0 s or more (slower swings = weaker)
    x 1.10                      dragonfire / boss mechanics (ABILITY_MONSTERS, "boss" or "ability_mult")
    A "level_override" wins outright.
    """
    mdef = mdef or {}
    if mdef.get("level_override") is not None:
        return int(mdef["level_override"])
    base = int(mdef.get("attack") or 0) + int(mdef.get("strength") or 0) + int(mdef.get("defence") or 0)
    hp = int(mdef.get("hp") or base)
    raw = base + round((hp - base) / 10) + round(int(mdef.get("def_bonus") or 0) / 4)
    cd = mdef.get("attack_cooldown")
    speed = 1.0 / float(cd) if cd is not None and float(cd) >= 1.0 else 1.0
    ability = float(mdef.get("ability_mult") or 0) or (
        ABILITY_MULT if (mdef.get("boss") or monster_type in ABILITY_MONSTERS) else 1.0)
    return max(1, int(round(raw * speed * ability)))
