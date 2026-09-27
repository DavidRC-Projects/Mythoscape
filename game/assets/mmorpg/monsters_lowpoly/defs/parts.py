"""Shared body-part helpers used by the monster definitions."""
from ..mesh_builder import Rig


def seg(rig: Rig, name, parent, pos, end, r0, r1, color, hpr=(0, 0, 0),
        segments=6, squash=1.0):
    """Create joint `name` at pos (in parent space) and a tapered tube from
    the joint origin to `end` (joint space). Returns the joint's MeshBuilder
    so more detail can be added."""
    rig.joint(name, parent, pos, hpr)
    mb = rig.mesh(name)
    mb.tube((0, 0, 0), end, r0, r1, color, segments, squash=squash)
    return mb


def biped_legs(rig, parent, hip_w, hip_z, thigh, shin, r_thigh, r_shin,
               color, foot_color, foot=(0.10, 0.20, 0.06), knee_bend=8,
               segments=6, joint_color=None):
    """Two-segment legs: l_leg/r_leg (hip pivot) -> l_shin/r_shin (knee).
    hip_z is relative to parent; legs hang along -Z. Returns total leg length."""
    for side, sx in (("l", -1), ("r", 1)):
        rig.joint(f"{side}_leg", parent, (sx * hip_w, 0, hip_z), (0, knee_bend, 0))
        rig.mesh(f"{side}_leg").tube((0, 0, 0), (0, 0, -thigh), r_thigh, r_shin * 1.05,
                                     color, segments)
        if joint_color:
            rig.mesh(f"{side}_leg").sphere(r_shin * 1.3, joint_color, pos=(0, 0, -thigh),
                                           rings=3, segments=5)
        rig.joint(f"{side}_shin", f"{side}_leg", (0, 0, -thigh), (0, -2 * knee_bend, 0))
        m = rig.mesh(f"{side}_shin")
        m.tube((0, 0, 0), (0, 0, -shin), r_shin, r_shin * 0.8, color, segments)
        m.box(foot, foot_color, pos=(0, foot[1] * 0.28, -shin - foot[2] * 0.3),
              hpr=(0, knee_bend, 0), taper=(0.85, 0.7))
    return thigh + shin


def aim(rig: Rig, joint, direction, up=(0, 0, 1)):
    """Rotate `joint` so its local +Z axis points along `direction`, given in
    the rig's root space (e.g. (0, 1, 0.6) = forward and up). Handy for
    weapons, staffs and tails without hand-tuning hpr values."""
    from panda3d.core import Point3, Vec3
    np = rig[joint]
    target = np.get_pos(rig.root) + Vec3(*direction)
    np.look_at(rig.root, Point3(target), Vec3(*up))   # +Y -> direction
    np.set_hpr(np, 0, -90, 0)                           # swap so +Z -> direction
