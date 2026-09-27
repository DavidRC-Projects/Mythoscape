"""monsters/animations.py - procedural OSRS-style animation profiles.

Every animation is built from LerpHprInterval / LerpPosInterval /
LerpScaleInterval on rig joints, relative to the rig's rest pose, so the
same code drives every monster that shares a joint-naming convention.
Missing joints are skipped, so a profile degrades gracefully.

Profiles: biped, giant, quadruped, wolf, dragon, spider, floater.
Each profile maps "idle" | "walk" | "attack" | "death" -> fn(monster) -> Interval.
idle/walk are looped by MonsterBase; attack/death play once.
"""
from direct.interval.IntervalGlobal import (Func, LerpHprInterval, LerpPosInterval,
                                            LerpScaleInterval, Parallel, Sequence, Wait)
from panda3d.core import Vec3


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _rest(m, name):
    return Vec3(*m.rest[name])


def swing(m, name, delta, dur, blend="easeInOut"):
    """rest -> rest+delta -> rest (one there-and-back cycle)."""
    j = m.joint(name)
    if j is None:
        return None
    r = _rest(m, name)
    tgt = r + Vec3(*delta)
    return Sequence(LerpHprInterval(j, dur / 2, tgt, startHpr=r, blendType=blend),
                    LerpHprInterval(j, dur / 2, r, startHpr=tgt, blendType=blend))


def pendulum(m, name, delta, dur, phase=0.0):
    """rest+delta -> rest-delta -> rest+delta; phase 0.5 starts on the other side."""
    j = m.joint(name)
    if j is None:
        return None
    r = _rest(m, name)
    d = Vec3(*delta) * (1 if phase < 0.5 else -1)
    a, b = r + d, r - d
    return Sequence(LerpHprInterval(j, dur / 2, b, startHpr=a, blendType="easeInOut"),
                    LerpHprInterval(j, dur / 2, a, startHpr=b, blendType="easeInOut"))


def pose(m, name, delta, dur, blend="easeOut"):
    """Lerp from the current hpr to rest+delta (one way)."""
    j = m.joint(name)
    if j is None:
        return None
    return LerpHprInterval(j, dur, _rest(m, name) + Vec3(*delta), blendType=blend)


def bob(m, name, dz, dur):
    j = m.joint(name)
    if j is None:
        return None
    p0 = m.rest_pos[name]
    return Sequence(LerpPosInterval(j, dur / 2, p0 + Vec3(0, 0, dz), startPos=p0, blendType="easeInOut"),
                    LerpPosInterval(j, dur / 2, p0, startPos=p0 + Vec3(0, 0, dz), blendType="easeInOut"))


def par(*ivals):
    return Parallel(*[i for i in ivals if i is not None])


def seq(*ivals):
    return Sequence(*[i for i in ivals if i is not None])


def reset_pose(m, dur=0.12):
    return par(*[LerpHprInterval(j, dur, _rest(m, n)) for n, j in m.rig.joints.items()
                 if n != "root"])


def fall_over(m, dur=0.6, roll=85):
    """Generic OSRS death: tip over sideways, sink a little, then hide."""
    root = m.rig.root
    return Sequence(
        Parallel(LerpHprInterval(root, dur, Vec3(0, 0, roll), blendType="easeIn"),
                 LerpPosInterval(root, dur, Vec3(0, 0, -0.05 * m.type.height_m), blendType="easeIn")),
        Wait(1.2),
        Func(root.hide),
    )


# --------------------------------------------------------------------------
# biped (goblins, skeletons, golem, ghoul, bog lurker, void brute)
# --------------------------------------------------------------------------
def biped_idle(m):
    return par(swing(m, "torso", (0, 3, 0), 2.0), swing(m, "head", (6, -3, 0), 2.0),
               swing(m, "l_arm", (0, 4, 0), 2.0), swing(m, "r_arm", (0, 4, 0), 2.0),
               swing(m, "jaw", (0, -6, 0), 2.0))


def biped_walk(m, speed=1.0):
    t = 0.9 / speed
    return par(pendulum(m, "l_leg", (0, 25, 0), t), pendulum(m, "r_leg", (0, 25, 0), t, 0.5),
               pendulum(m, "l_shin", (0, -12, 0), t, 0.5), pendulum(m, "r_shin", (0, -12, 0), t),
               pendulum(m, "l_arm", (0, 18, 0), t, 0.5), pendulum(m, "r_arm", (0, 18, 0), t),
               pendulum(m, "torso", (4, 0, 2), t))


def biped_attack(m):
    """Wind-up then overhead/side swing with the right arm (weapon arm)."""
    return seq(
        par(pose(m, "r_arm", (0, 70, -20), 0.25), pose(m, "r_forearm", (0, 40, 0), 0.25),
            pose(m, "torso", (15, 6, 0), 0.25)),
        par(pose(m, "r_arm", (0, -40, 10), 0.15, "easeIn"), pose(m, "r_forearm", (0, -10, 0), 0.15, "easeIn"),
            pose(m, "torso", (-15, -8, 0), 0.15, "easeIn"), pose(m, "jaw", (0, -20, 0), 0.15)),
        Wait(0.15),
        reset_pose(m, 0.3),
    )


# --------------------------------------------------------------------------
# quadruped (cave gnasher) and dragon
# --------------------------------------------------------------------------
LEGS4 = ("l_front_leg", "r_hind_leg", "r_front_leg", "l_hind_leg")


def quad_idle(m):
    return par(swing(m, "body", (0, 2, 0), 2.4), swing(m, "head", (8, -4, 0), 2.4),
               swing(m, "jaw", (0, -8, 0), 2.4), swing(m, "tail", (15, 0, 0), 2.4),
               swing(m, "neck_0", (4, -3, 0), 2.4), swing(m, "tail_1", (10, 0, 0), 2.4))


def quad_walk(m, speed=1.0):
    t = 1.0 / speed
    legs = [pendulum(m, n, (0, 22, 0), t, 0.5 * (i // 2)) for i, n in enumerate(LEGS4)]
    shins = [pendulum(m, n.replace("leg", "shin"), (0, -15, 0), t, 0.5 * (1 - i // 2))
             for i, n in enumerate(LEGS4)]
    return par(*legs, *shins, pendulum(m, "head", (0, 5, 0), t / 2),
               pendulum(m, "tail_0", (12, 0, 0), t), pendulum(m, "tail", (15, 0, 0), t))


def quad_attack(m):
    """Head lunge + jaw snap (bite)."""
    return seq(
        par(pose(m, "head", (0, 20, 0), 0.25), pose(m, "neck_0", (0, 15, 0), 0.25),
            pose(m, "jaw", (0, -30, 0), 0.25), pose(m, "body", (0, 6, 0), 0.25)),
        par(pose(m, "head", (0, -20, 0), 0.12, "easeIn"), pose(m, "neck_0", (0, -15, 0), 0.12, "easeIn"),
            pose(m, "jaw", (0, 5, 0), 0.12, "easeIn"), pose(m, "body", (0, -4, 0), 0.12)),
        Wait(0.1),
        reset_pose(m, 0.3),
    )


def dragon_idle(m):
    return par(quad_idle(m), pendulum(m, "l_wing", (0, 0, 8), 2.4), pendulum(m, "r_wing", (0, 0, -8), 2.4))


def dragon_walk(m, speed=1.0):
    return par(quad_walk(m, speed * 0.8), pendulum(m, "l_wing", (0, 0, 5), 1.2),
               pendulum(m, "r_wing", (0, 0, -5), 1.2), pendulum(m, "tail_1", (10, 0, 0), 1.25))


def dragon_attack(m):
    """Rear back, wings flare, jaw opens wide (breath or bite)."""
    return seq(
        par(pose(m, "neck_0", (0, 25, 0), 0.35), pose(m, "neck_1", (0, 15, 0), 0.35),
            pose(m, "head", (0, 10, 0), 0.35), pose(m, "l_wing", (0, 0, 25), 0.35),
            pose(m, "r_wing", (0, 0, -25), 0.35)),
        par(pose(m, "neck_0", (0, -15, 0), 0.18, "easeIn"), pose(m, "neck_1", (0, -10, 0), 0.18, "easeIn"),
            pose(m, "head", (0, -15, 0), 0.18, "easeIn"), pose(m, "jaw", (0, -35, 0), 0.18)),
        Wait(0.5),   # <- spawn the breath particle / projectile here
        reset_pose(m, 0.4),
    )


# --------------------------------------------------------------------------
# spider
# --------------------------------------------------------------------------
def _spider_groups():
    a = [f"leg_{s}{i}" for s, i in (("l", 0), ("r", 1), ("l", 2), ("r", 3))]
    b = [f"leg_{s}{i}" for s, i in (("r", 0), ("l", 1), ("r", 2), ("l", 3))]
    return a, b


def spider_idle(m):
    return par(bob(m, "body", -0.02 * m.type.height_m, 1.6), swing(m, "head", (4, 3, 0), 1.6))


def spider_walk(m, speed=1.0):
    t = 0.6 / speed
    a, b = _spider_groups()
    ivals = []
    for i, names in enumerate((a, b)):
        for n in names:
            ivals.append(pendulum(m, n, (14, 0, 0), t, 0.5 * i))
            ivals.append(pendulum(m, n.replace("leg_", "knee_"), (0, 0, 10), t, 0.5 * i))
    return par(*ivals, bob(m, "body", 0.02, t / 2))


def spider_attack(m):
    return seq(
        par(pose(m, "body", (0, 15, 0), 0.2), pose(m, "head", (0, 10, 0), 0.2)),
        par(pose(m, "body", (0, -10, 0), 0.1, "easeIn"), pose(m, "head", (0, -20, 0), 0.1, "easeIn")),
        Wait(0.1),
        reset_pose(m, 0.25),
    )


def spider_death(m):
    """Flip onto its back and curl the legs in."""
    root = m.rig.root
    curls = []
    for s in "lr":
        for i in range(4):
            curls.append(pose(m, f"knee_{s}{i}", (0, 0, -45), 0.5))
            curls.append(pose(m, f"leg_{s}{i}", (0, 0, 30), 0.5))
    return Sequence(
        Parallel(LerpHprInterval(root, 0.5, Vec3(0, 0, 180)),
                 LerpPosInterval(root, 0.5, Vec3(0, 0, 0.35 * m.type.height_m)), *[c for c in curls if c]),
        Wait(1.2), Func(root.hide))


# --------------------------------------------------------------------------
# floater (void spawn, barrow wraith)
# --------------------------------------------------------------------------
def floater_idle(m):
    ivals = [bob(m, "body", 0.08, 2.0), swing(m, "head", (8, 0, 0), 3.0),
             pendulum(m, "tail_0", (12, 0, 0), 2.0), pendulum(m, "tail_1", (18, 0, 0), 2.0, 0.5),
             pendulum(m, "l_arm", (0, 6, 0), 2.0), pendulum(m, "r_arm", (0, 6, 0), 2.0, 0.5)]
    for i in range(4):
        ivals.append(pendulum(m, f"tentacle_{i}", (0, 10, 6), 1.6, 0.5 * (i % 2)))
        ivals.append(pendulum(m, f"tentacle_{i}_tip", (0, 18, 0), 1.6, 0.5 * ((i + 1) % 2)))
    j = m.joint("shards")
    if j is not None:
        ivals.append(j.hprInterval(4.0, Vec3(360, 0, 0), startHpr=Vec3(0, 0, 0)))
    return par(*ivals)


def floater_walk(m, speed=1.0):
    return par(floater_idle(m), pose(m, "body", (0, -12, 0), 0.3))


def floater_attack(m):
    return seq(
        par(pose(m, "body", (0, 10, 0), 0.25), pose(m, "l_arm", (0, 60, -20), 0.25),
            pose(m, "r_arm", (0, 60, 20), 0.25), pose(m, "eye", (0, 0, 0), 0.25)),
        par(pose(m, "body", (0, -20, 0), 0.12, "easeIn"), pose(m, "l_arm", (0, 20, 0), 0.12, "easeIn"),
            pose(m, "r_arm", (0, 20, 0), 0.12, "easeIn")),
        Wait(0.2),
        reset_pose(m, 0.3),
    )


def floater_death(m):
    """Dissolve: rise slightly, spin and shrink away (no body left behind)."""
    root = m.rig.root
    return Sequence(
        Parallel(LerpPosInterval(root, 0.9, Vec3(0, 0, 0.4)),
                 LerpHprInterval(root, 0.9, Vec3(180, 0, 0)),
                 LerpScaleInterval(root, 0.9, 0.01, blendType="easeIn")),
        Func(root.hide))


# --------------------------------------------------------------------------
# giant (hill / ice giant): heavy biped - slow stride, two-handed club smash,
# topples forward on death
# --------------------------------------------------------------------------
def giant_idle(m):
    return par(swing(m, "torso", (0, 4, 0), 3.0), swing(m, "head", (10, -4, 0), 3.0),
               swing(m, "l_arm", (0, 5, 0), 3.0), swing(m, "r_arm", (0, 3, 0), 3.0),
               swing(m, "jaw", (0, -8, 0), 3.0))


def giant_walk(m, speed=1.0):
    t = 1.6 / speed
    return par(pendulum(m, "l_leg", (0, 20, 0), t), pendulum(m, "r_leg", (0, 20, 0), t, 0.5),
               pendulum(m, "l_shin", (0, -10, 0), t, 0.5), pendulum(m, "r_shin", (0, -10, 0), t),
               pendulum(m, "l_arm", (0, 12, 0), t, 0.5), pendulum(m, "r_arm", (0, 6, 0), t),
               pendulum(m, "torso", (6, 0, 4), t), bob(m, "hips", -0.05, t / 2))


def giant_attack(m):
    """Slow overhead wind-up, heavy smash (sync the damage/screen-shake to the
    end of the smash pose, ~0.65 s in)."""
    return seq(
        par(pose(m, "r_arm", (0, 110, 15), 0.45), pose(m, "l_arm", (0, 60, -15), 0.45),
            pose(m, "torso", (0, 14, 0), 0.45), pose(m, "head", (0, -10, 0), 0.45)),
        par(pose(m, "r_arm", (0, -30, 0), 0.2, "easeIn"), pose(m, "l_arm", (0, 10, 0), 0.2, "easeIn"),
            pose(m, "torso", (0, -18, 0), 0.2, "easeIn"), pose(m, "jaw", (0, -18, 0), 0.2)),
        Wait(0.35),
        reset_pose(m, 0.45),
    )


def giant_death(m, dur=0.9):
    """Topple forward onto the face (negative pitch tips the top toward +Y)."""
    root = m.rig.root
    return Sequence(
        par(pose(m, "l_leg", (0, -15, 0), dur), pose(m, "r_leg", (0, -10, 0), dur),
            LerpHprInterval(root, dur, Vec3(0, -84, 0), blendType="easeIn")),
        Wait(1.5), Func(root.hide))


# --------------------------------------------------------------------------
# wolf: fast trot, tail wag, lunge bite, collapse on its side
# --------------------------------------------------------------------------
def wolf_idle(m):
    j = m.joint("tail")
    ivals = [swing(m, "body", (0, 2, 0), 1.6), swing(m, "head", (12, -4, 0), 2.4),
             swing(m, "neck_0", (0, 4, 0), 1.6), swing(m, "jaw", (0, -6, 0), 1.2)]
    if j is not None:
        ivals.append(pendulum(m, "tail", (18, 0, 0), 0.8))
    return par(*ivals)


def wolf_walk(m, speed=1.0):
    return par(quad_walk(m, speed * 1.6), pendulum(m, "neck_0", (0, 4, 0), 0.31 / speed),
               bob(m, "body", 0.03 * m.type.height_m, 0.31 / speed))


def wolf_attack(m):
    """Crouch, lunge forward with the whole body, snap the jaw."""
    body = m.joint("body")
    p0 = m.rest_pos["body"]
    lunge = Vec3(0, 0.35 * m.type.height_m, 0.05)
    return seq(
        par(pose(m, "body", (0, -6, 0), 0.18), pose(m, "head", (0, -10, 0), 0.18),
            pose(m, "jaw", (0, -30, 0), 0.18), pose(m, "l_hind_leg", (0, 15, 0), 0.18),
            pose(m, "r_hind_leg", (0, 15, 0), 0.18)),
        par(LerpPosInterval(body, 0.12, p0 + lunge, blendType="easeIn"),
            pose(m, "body", (0, 8, 0), 0.12, "easeIn"), pose(m, "jaw", (0, 4, 0), 0.12, "easeIn"),
            pose(m, "l_front_leg", (0, 35, 0), 0.12), pose(m, "r_front_leg", (0, 35, 0), 0.12)),
        Wait(0.08),
        par(LerpPosInterval(body, 0.25, p0), reset_pose(m, 0.25)),
    )


def wolf_death(m):
    return fall_over(m, dur=0.45, roll=88)


PROFILES = {
    "biped": {"idle": biped_idle, "walk": biped_walk, "attack": biped_attack, "death": fall_over},
    "giant": {"idle": giant_idle, "walk": giant_walk, "attack": giant_attack, "death": giant_death},
    "wolf": {"idle": wolf_idle, "walk": wolf_walk, "attack": wolf_attack, "death": wolf_death},
    "quadruped": {"idle": quad_idle, "walk": quad_walk, "attack": quad_attack, "death": fall_over},
    "dragon": {"idle": dragon_idle, "walk": dragon_walk, "attack": dragon_attack, "death": fall_over},
    "spider": {"idle": spider_idle, "walk": spider_walk, "attack": spider_attack, "death": spider_death},
    "floater": {"idle": floater_idle, "walk": floater_walk, "attack": floater_attack, "death": floater_death},
}
LOOPING = {"idle", "walk"}
