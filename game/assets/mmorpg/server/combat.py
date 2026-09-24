"""
Combat resolution using the classic RuneScape (2001-era) combat formulas:
attack roll vs defence roll decides whether a hit lands, and a max-hit
based on the effective strength level decides how big it can be.

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
    """
    chance = hit_chance(
        attacker_stats["attack"], attacker_stats.get("attack_bonus", 0),
        defender_stats["defence"], defender_stats.get("defence_bonus", 0),
    )
    if random.random() > chance:
        return 0, False
    top = max_hit(attacker_stats["strength"], attacker_stats.get("strength_bonus", 0))
    dmg = random.randint(0, top)
    return dmg, True


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


def combat_level(attack, strength, defence, hitpoints, archery=1):
    """Classic RS combat level with melee vs ranged (no Prayer/Summoning)."""
    base = 0.25 * (defence + hitpoints)
    melee = 0.325 * (attack + strength)
    ranged = 0.325 * (archery * 2)
    return max(1, int(math.floor(base + max(melee, ranged))))
