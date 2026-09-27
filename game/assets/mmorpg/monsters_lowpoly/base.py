"""monsters/base.py - MonsterBase: one live monster instance in the world."""
from __future__ import annotations

from panda3d.core import NodePath

from .animations import LOOPING, PROFILES


class MonsterBase:
    """Owns the rig, the current animation and simple combat state.

    Scene layout:
        self.node        <- game code moves/turns this (world position, heading)
          rig.root       <- animations may roll/sink this (death) - never move it yourself
            joints...    <- procedural limb animation

    Adapt to David's existing entity/NPC classes: this can be a component
    owned by an existing Monster/NPC object rather than a replacement.
    """

    def __init__(self, mtype, rig, parent: NodePath | None = None):
        self.type = mtype
        self.rig = rig
        self.node = NodePath(f"monster_{mtype.key}")
        rig.root.reparent_to(self.node)
        self.rest = rig.rest_pose()
        self.rest_pos = {n: j.get_pos() for n, j in rig.joints.items()}
        self.hp = mtype.stats.hp
        self.state = None
        self._ival = None
        self.node.set_python_tag("monster", self)   # for mouse picking -> monster
        if parent is not None:
            self.node.reparent_to(parent)
        self.play("idle")

    # --- scene helpers -------------------------------------------------------
    def joint(self, name: str):
        return self.rig.joints.get(name)

    def set_pos(self, *xyz):
        self.node.set_pos(*xyz)

    def face(self, target_np_or_point):
        self.node.look_at(target_np_or_point)
        self.node.set_p(0)
        self.node.set_r(0)

    # --- animation -----------------------------------------------------------
    def play(self, name: str, **kw):
        if self.state == name and name in LOOPING:
            return
        if self._ival is not None:
            self._ival.finish() if name == "death" else self._ival.pause()
        self._restore_rest()
        builder = PROFILES[self.type.anim_profile][name]
        self._ival = builder(self, **kw) if kw else builder(self)
        self.state = name
        if name in LOOPING:
            self._ival.loop()
        else:
            from direct.interval.IntervalGlobal import Func, Sequence
            if name != "death":
                self._ival = Sequence(self._ival, Func(self._back_to_idle))
            self._ival.start()

    def _back_to_idle(self):
        self.state = None
        self.play("idle")

    def _restore_rest(self):
        for n, j in self.rig.joints.items():
            if n != "root":
                j.set_hpr(*self.rest[n])
                j.set_pos(self.rest_pos[n])

    def respawn(self):
        """Undo a death animation and refill HP (reuse instead of rebuilding)."""
        root = self.rig.root
        root.set_pos_hpr_scale(0, 0, 0, 0, 0, 0, 1, 1, 1)
        root.show()
        self.hp = self.type.stats.hp
        self.state = None
        self.play("idle")

    # --- combat hooks (wire into your own combat system) -------------------
    def take_damage(self, amount: int) -> bool:
        """Returns True if this hit killed the monster."""
        if self.hp <= 0:
            return False
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.play("death")
            return True
        return False

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def destroy(self):
        if self._ival is not None:
            self._ival.pause()
        self.node.remove_node()
