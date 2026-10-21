"""Animated subparts (adapted from an earlier prototype): the KVM console's drawer and screen.

Vanilla pattern: every subpart is its own model (FBX per LOD,
no collision, the FBX origin = the pivot), spawned by the block's ConditionalSubPartsComponent at every block-model
dummy of a dedicated DummyType, its prefab a copy of Templates/Blocks/Subparts/Subpart (composite = a copy of
Subpart_Composite + one rigid animation component). Nested motion = a child entity inside the prefab (the
RocketTurret250 S1 -> S2 / Gyroscope50 S2 -> S3 pattern). Subparts are client-only and visual: they never move
collision, and the material swapper does not reach them.

KVM (DC_Srv_KVM, a ControlPanel25 clone):
  KvmDrawer  dummy "KvmDrawer" (block model, its own DummyType) -> prefab DC_Srv_KVM_KvmDrawer.
             TranslationAnimation (0, 0, -TRAVEL) in block space (game -Z = the block's front), Speed TRAVEL/POP_TIME.
             The drawer: front fascia (pull bar, release latches, power lamp), keyboard tray on telescopic slides,
             keyboard + trackpad, rear electronics cover, the hinge brackets.
  KvmScreen  a child of the drawer prefab at the drawer model's dummy "KvmScreen" (the hinge axis; the drawer pivot
             IS the hinge, so the child sits at the drawer's local origin). RotationAnimation about local +X (= game
             +X: the hinge axis) by FOLD_DEG, AngularSpeed FOLD_DEG/POP_TIME: the lid lying on the keyboard folds up
             and 10 deg past vertical, screen to the user. Lid = shell, bezel, screen (vanilla Terminal art), hinge
             barrels, latch hooks.
  Trigger    FunctionalBlockAnimationControllerComponent (client): both animations toggle with Working (= built and
             not broken, and the grid switched on: ControlPanel25 has no power or on/off of its own). One channel per
             block, so the slide and the fold run SIMULTANEOUSLY; equal durations make the close the exact reverse
             of the open (unequal ones leave the lid standing while the drawer slides back into the rack).
  Load bug   Translation/RotationAnimation do not toggle on spawn (_autoToggleOnSpawn = false), and ConditionalSubParts
             respawns subparts on every Functional change: after a world load, a repair or streaming in, a Working
             KVM shows STOWED until the next Working change (vanilla-animations.md section 9 Q1).

Frames: the KVM model's Blender frame (centred, +Y front, Z up; game = (x, z, -y) + shift (0.125, 0, 0)).
Everything here is plain Python (no bpy): the Blender builders live in dc/servers/kvm.py.
"""
import math

KVM = "DC_Srv_KVM"
DRAWER, SCREEN = "KvmDrawer", "KvmScreen"
SHIFT = (0.125, 0.0, 0.0)            # export_models.shift for cells (2, 1, 3)

TRAVEL = 0.45                        # m, the drawer slides out this far (about 0.45 m)
FOLD_DEG = 100.0                     # the screen folds up 100 deg (10 deg past vertical)
POP_TIME = 1.0                       # s, both animations (equal: the close retraces the open)
DRAWER_SPEED = TRAVEL / POP_TIME     # m/s (TranslationAnimation.Speed)
SCREEN_SPEED = FOLD_DEG / POP_TIME   # deg/s (RotationAnimation.AngularSpeed)

# ---- geometry (KVM Blender frame, stowed). Face: server.face_frame (bezel opening a +-0.212, b -0.105 .. 0.101).
HINGE = (0.0, 0.046, -0.041)         # the hinge axis (along x) = the drawer pivot = the screen pivot
BAY = {"x": 0.209, "y0": -0.170, "z0": -0.105, "z1": -0.026}       # the drawer bay cut into the core (y to the core front)
DRAWER_BOX = {"x": 0.205, "y0": -0.160, "y_fascia": 0.352, "y_front": 0.381, "z0": -0.101, "z1": -0.029}
LID = {"half_w": 0.184, "len": 0.300, "half_t": 0.009}            # lid local frame: hinge axis = x, lies along +y
SCREEN_AREA = {"half_w": 0.170, "y0": 0.022, "y1": 0.285}         # the Terminal screen on the lid's underside
NEIGHBOUR_FRONT_Y = 0.4145           # the deepest front hardware of a server (handles, the clearance max_y)
FACE_Y = 0.383                       # the bezel front: the KVM's face plane (its upper panel lies behind it)


def to_game(p):
    """A KVM Blender-frame point in the game frame of the .model (LOD0 shift applied)."""
    x, y, z = p
    return (round(x + SHIFT[0], 6), round(z + SHIFT[1], 6), round(-y + SHIFT[2], 6))


def drawer_dummy_game():
    """Position of the "KvmDrawer" block-model dummy (= the drawer pivot = the stowed hinge), game frame."""
    return list(to_game(HINGE))


SCREEN_LOCAL = (0.0, 0.0, 0.0)       # "KvmScreen" dummy on the drawer model (game frame, relative to the pivot)


def pose(f):
    """(drawer offset along +Y, screen angle deg) at animation fraction f in [0, 1] (both linear, equal times)."""
    f = min(1.0, max(0.0, f))
    return TRAVEL * f, FOLD_DEG * f


def rot_x(p, deg):
    """Rotate (x, y, z) about the x axis by deg (right-handed: +deg lifts +y toward +z)."""
    a = math.radians(deg)
    x, y, z = p
    return (x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


def lid_corners():
    """The lid's 8 box corners in its local frame (hinge axis = x through the origin)."""
    w, L, t = LID["half_w"], LID["len"], LID["half_t"]
    return [(x, y, z) for x in (-w, w) for y in (-t, L) for z in (-t, t)]


def lid_at_pose(dy, deg):
    """The lid corners in the KVM Blender frame with the drawer out by dy (m) and the lid folded up by deg."""
    hx, hy, hz = HINGE
    return [(x + hx, y + hy + dy, z + hz) for x, y, z in (rot_x(c, deg) for c in lid_corners())]


def lid_at(f):
    """The lid corners in the KVM Blender frame at the data-only animation fraction f (slide and fold together)."""
    return lid_at_pose(*pose(f))


def transient_intrusion(steps=200):
    """Simultaneous slide-and-fold: the largest height the lid reaches above the bay roof (BAY z1) while any of it is
    still behind the face plane (y < the bezel front 0.383), i.e. how far it passes through the KVM's own upper
    panel mid-motion; and where. Same value on the close (it retraces the open). Lid sampled on its box edges."""
    worst = (0.0, 0.0)
    y_face = FACE_Y
    for i in range(steps + 1):
        f = i / steps
        dy, ang = pose(f)
        hx, hy, hz = HINGE
        w, L, t = LID["half_w"], LID["len"], LID["half_t"]
        for k in range(41):
            s = -t + (L + t) * k / 40
            for zz in (-t, t):
                _, y, z = rot_x((0.0, s, zz), ang)
                y, z = y + hy + dy, z + hz
                if y < y_face:
                    worst = max(worst, (z - BAY["z1"], f))
    return {"max_above_bay_roof": round(worst[0], 4), "at_fraction": round(worst[1], 3),
            "panel_top_above_bay_roof": round(0.101 - BAY["z1"], 4)}
