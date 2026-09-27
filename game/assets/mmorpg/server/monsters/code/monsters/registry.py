"""monsters/registry.py - monster type registry + factory."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class MonsterStats:
    level: int
    hp: int
    attack_style: str          # "melee" | "ranged" | "magic" | mixed "melee/magic"
    max_hit: int
    attack_speed: float        # seconds between attacks
    weakness: str
    aggressive: bool = False
    notes: str = ""


@dataclass
class MonsterType:
    key: str                   # "dragon_green"
    name: str                  # "Green Dragon"
    family: str                # "dragon"
    size_class: str            # "small" | "medium" | "large" | "boss"
    anim_profile: str          # "biped" | "giant" | "quadruped" | "wolf" | "dragon" | "spider" | "floater"
    build: Callable            # () -> Rig
    stats: MonsterStats
    palette: dict = field(default_factory=dict)
    height_m: float = 1.0
    image: str = ""


MONSTERS: dict[str, MonsterType] = {}


def register(key, name, family, size_class, anim_profile, stats, palette,
             height_m, image=None):
    """Decorator for a zero-arg build function returning a Rig."""
    def deco(fn):
        MONSTERS[key] = MonsterType(key, name, family, size_class, anim_profile,
                                    fn, stats, palette, height_m,
                                    image or f"images/{key}.png")
        return fn
    return deco


def load_all():
    """Import every defs module so their @register decorators run."""
    import importlib
    for mod in DEF_MODULES:
        importlib.import_module(f"{__package__}.defs.{mod}")
    return MONSTERS


DEF_MODULES = ["dragons", "goblins", "skeletons", "spiders", "void",
               "bog_lurker", "stone_golem", "barrow_wraith", "cave_gnasher",
               "rot_ghoul", "giants", "wolves"]


def create(key, parent=None):
    """Factory: build a fresh MonsterBase for a registered monster key."""
    from .base import MonsterBase
    if not MONSTERS:
        load_all()
    mtype = MONSTERS[key]
    rig = mtype.build()
    return MonsterBase(mtype, rig, parent)
