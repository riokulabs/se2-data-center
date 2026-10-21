"""Rack doors and tray fans: the bpy-free numbers, frames and clearance geometry.

Mechanism (vanilla SlidingDoorNarrow250, decompiled 2.4.0.95; docs/guides/vanilla-animations.md section 6.1):
  DoorServerComponent advances DoorData.OpenRatio (0..1, linear, saved and replicated); every leaf subpart carries a
  DoorSegmentComponent (copies the ratio) and a DoorSegmentTransformSLERPComponent, which sets the leaf's
  RelativeTransform = RelativeTransform.Slerp(Closed, Open, ratio) = position LERP + orientation quaternion SLERP
  (RelativeTransform.cs:749-755) between two dummies of the closest parent model (the BLOCK model). So a HINGED leaf
  is data-only: the leaf model's origin is ON the hinge axis, both dummies sit at the same point (the lerp is then
  constant) and the open dummy is the closed one turned DOOR_OPEN_DEG about the vertical axis (the slerp sweeps the
  arc). Hinged, not sliding: the fallback was not needed. [code; unverified in game]

Leaf models (Blender frame of the subpart, origin = the hinge axis at the block's mid-height, +Y = the leaf's
outside face, Z up). Two models: DoorLeafR is hinged on its +x edge and extends toward -x; DoorLeafL is its mirror.
The rear leaves reuse them turned 180 deg (a rear leaf hinged at -x is DoorLeafR seen from behind).

Block frame: centred, +Y = front = game Forward; game = (x, z, -y) + the .model shift; Blender Rz(a) = game Ry(a).
"""
import math

from . import dims as DM

LEAF_L, LEAF_R = "DoorLeafL", "DoorLeafR"
FAN = "RackFan"
OPEN = DM.DOOR_OPEN_DEG

# per leaf: subpart / dummy name, model, hinge side (sign of x), door side (sign of y), closed yaw, open yaw (deg,
# Blender Rz). Front leaves swing out toward +y, rear leaves toward -y.
_FRONT = [("LeftDoor", LEAF_L, -1, 1, 0.0, OPEN), ("RightDoor", LEAF_R, 1, 1, 0.0, -OPEN)]
_REAR = [("RearLeftDoor", LEAF_R, -1, -1, 180.0, 180.0 - OPEN), ("RearRightDoor", LEAF_L, 1, -1, 180.0, 180.0 + OPEN)]


def has_doors(spec):
    return spec.family == "rack" and spec.variant in ("SplitFront", "SplitFrontRear")


def door_sides(spec):
    """(+1 front, -1 rear) sides that carry leaves."""
    return {"SplitFront": (1,), "SplitFrontRear": (1, -1)}.get(spec.variant, ()) if spec.family == "rack" else ()


def leaves(spec):
    """[{name, model, sx, sy, yaw_closed, yaw_open, axis}] for the block (empty for an open rack)."""
    out = []
    for side in door_sides(spec):
        for name, model, sx, sy, y0, y1 in (_FRONT if side > 0 else _REAR):
            out.append({"name": name, "model": model, "sx": sx, "sy": sy, "yaw_closed": y0, "yaw_open": y1,
                        "axis": (sx * DM.DOOR_AXIS_X, sy * DM.DOOR_AXIS_Y)})
    return out


def leaf_models(spec):
    return sorted({lf["model"] for lf in leaves(spec)})


def rack_dims(spec):
    """(H, ZT, tray) as dc/rack.dims without importing it (rack.py needs Blender for geometry)."""
    H, ZT, tray, _ = DM.rack_frame(spec.cells[1])
    return H, ZT, tray


def z_range(spec):
    """Leaf z span in the centred block frame: the slot band less DOOR_Z_GAP at each end."""
    H, ZT, _ = rack_dims(spec)
    return 0.25 + DM.DOOR_Z_GAP - H / 2, ZT - DM.DOOR_Z_GAP - H / 2


def handle_z(spec):
    """Leaf handle centre (block-centred z): about 1.1 m above the rack's floor, kept inside the leaf."""
    z0, z1 = z_range(spec)
    H = 0.25 * spec.cells[1]
    return min(max(-H / 2 + 1.1, z0 + 0.22), z1 - 0.22)


def hinge_zs(spec):
    """Hinge centres (block-centred z): near both ends, plus one mid-height on the tall leaves."""
    z0, z1 = z_range(spec)
    zs = [z0 + 0.16, z1 - 0.16]
    if z1 - z0 > 1.2:
        zs.insert(1, (z0 + z1) / 2)
    return zs


def shift(spec):
    return tuple(0.125 if n % 2 == 0 else 0.0 for n in spec.cells)


def to_game(p, spec):
    x, y, z = p
    s = shift(spec)
    return (round(x + s[0], 6), round(z + s[1], 6), round(-y + s[2], 6))


def quat_yaw(deg):
    """Game quaternion (X, Y, Z, W) of a Blender Rz(deg) = a game rotation about +Y."""
    a = math.radians(deg) / 2
    return (0.0, round(math.sin(a), 8), 0.0, round(math.cos(a), 8))


def quat_angle(q0, q1):
    """Angle (deg) between two unit quaternions (the slerp's sweep)."""
    d = abs(sum(a * b for a, b in zip(q0, q1)))
    return math.degrees(2 * math.acos(min(1.0, d)))


def rot2(p, deg):
    a = math.radians(deg)
    x, y = p
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def place(leaf, p, deg):
    """A leaf-local plan point (x, y) placed in the block frame at yaw `deg` (the closed yaw + the swing)."""
    x, y = rot2(p, deg)
    return (leaf["axis"][0] + x, leaf["axis"][1] + y)


def swing_yaw(leaf, f):
    """Yaw at open fraction f in [0, 1] (the slerp of a pure yaw is linear in angle)."""
    return leaf["yaw_closed"] + (leaf["yaw_open"] - leaf["yaw_closed"]) * f


def dummies(spec):
    """Block-model dummies for the doors: per leaf "<name>Closed" and "<name>Open" (game frame, the hinge axis at
    the block's mid-height). Returns [(name, leaf, kind, position, quaternion, euler)]."""
    out = []
    for lf in leaves(spec):
        pos = to_game((lf["axis"][0], lf["axis"][1], 0.0), spec)
        for kind, yaw in (("Closed", lf["yaw_closed"]), ("Open", lf["yaw_open"])):
            out.append((lf["name"] + kind, lf, kind, pos, quat_yaw(yaw), (0.0, yaw, 0.0)))
    return out


def use_box(spec, model):
    """The leaf's UseDoor interaction box (leaf model frame, game axes): (centre, scale)."""
    z0, z1 = z_range(spec)
    s = 1 if model == LEAF_R else -1
    u0, u1 = DM.DOOR_U0, DM.DOOR_W
    cx = -s * (u0 + u1) / 2
    return (round(cx, 6), round((z0 + z1) / 2, 6), 0.0), (round(u1 - u0, 6), round(z1 - z0, 6), 0.05)


def detector_box(spec):
    """The doorway obstacle detector (vanilla: re-opens a closing door when something stands in its box): the
    leaves' plane plus 13 cm in front of it (front doors only), or the whole depth for front + rear doors (the
    block's own grid is ignored, so the servers inside never trigger it). (centre game, half extents game)."""
    z0, z1 = z_range(spec)
    zc, hz = (z0 + z1) / 2, (z1 - z0) / 2
    hx = DM.DOOR_AXIS_X
    if len(door_sides(spec)) == 2:
        c, hy = (0.0, 0.0, zc), DM.DOOR_Y_FRONT + 0.13
    else:
        c, hy = (0.0, DM.DOOR_Y_BACK + 0.075, zc), 0.075
    return to_game(c, spec), (round(hx, 6), round(hz, 6), round(hy, 6))


FAN_TRAY_SUB = "RackFanTray"
TRAY_FLOOR = 0.05            # the trough floor's top above ZT (dc/rack.py _tray)
FAN_TRAY = {"half_x": 0.42, "half_y": 0.147, "plate_t": 0.008, "housing_h": 0.05, "housing_half": 0.125,
            "open_r": DM.FAN_R + 0.008, "guard_r": (0.098, 0.07, 0.042)}
FAN_HUB_Z = FAN_TRAY["plate_t"] + 0.028      # rotor hub above the tray origin (inside the housing)
FAN_CAN_TOP = FAN_TRAY["plate_t"] + FAN_TRAY["housing_h"] + 0.0025 - FAN_HUB_Z   # motor can reaches the guard disc


def fan_tray_point(spec):
    """The static fan tray's origin (Blender block frame): the rear (fan) lane's centre on the trough floor."""
    H, ZT, tray = rack_dims(spec)
    return (0.0, DM.FAN_Y, ZT - H / 2 + TRAY_FLOOR) if tray else None


def fan_points(spec):
    """Fan rotor pivots (Blender block frame): in their housings on the fan tray in the tray's rear lane."""
    t = fan_tray_point(spec)
    if t is None:
        return []
    return [(x, t[1], t[2] + FAN_HUB_Z) for x in DM.FAN_X]


# ------------------------------------------------------------------------------------------------ plan geometry
def convex_hull(points):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L = ax * ax + ay * ay
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def _overlap(P, Q):
    """Separating-axis test for two convex polygons (True = they intersect)."""
    for poly in (P, Q):
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            n = (a[1] - b[1], b[0] - a[0])
            pa = [n[0] * x + n[1] * y for x, y in P]
            pb = [n[0] * x + n[1] * y for x, y in Q]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def poly_distance(P, Q):
    """Minimum distance between two convex polygons; negative (-1e-9) when they overlap."""
    if _overlap(P, Q):
        return -1e-9
    d = min(_seg_dist(p, Q[i], Q[(i + 1) % len(Q)]) for p in P for i in range(len(Q)))
    return min(d, min(_seg_dist(q, P[i], P[(i + 1) % len(P)]) for q in Q for i in range(len(P))))


def closest_points(P, Q):
    """(distance, point on P, point on Q) by vertex-to-edge search (for the preview's clearance marker)."""
    best = (9.0, None, None)

    def proj(p, a, b):
        ax, ay = b[0] - a[0], b[1] - a[1]
        L = ax * ax + ay * ay
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L))
        return (a[0] + t * ax, a[1] + t * ay)
    for A, B, flip in ((P, Q, False), (Q, P, True)):
        for p in A:
            for i in range(len(B)):
                q = proj(p, B[i], B[(i + 1) % len(B)])
                d = math.hypot(p[0] - q[0], p[1] - q[1])
                if d < best[0]:
                    best = (d, q, p) if flip else (d, p, q)
    return best


def placed_hull(leaf, hull, deg, dx=0.0):
    return [(x + dx, y) for x, y in (place(leaf, p, deg) for p in hull)]


def neighbour_clearance(spec, hulls, f=1.0, pitch=None):
    """Two identical racks flush side by side (centres `pitch` apart, default the rack width) with every leaf at
    open fraction f: the minimum plan distance between a leaf of one rack and a leaf of the other (the leaves span
    the same z band, so plan distance is the 3D distance). hulls: {model: [(x, y)] leaf-local plan hull}."""
    pitch = pitch if pitch is not None else 0.25 * spec.cells[0]
    lv = leaves(spec)
    best = (9.0, None)
    for a in lv:
        for b in lv:
            if a["sy"] != b["sy"]:
                continue
            P = placed_hull(a, hulls[a["model"]], swing_yaw(a, f))
            Q = placed_hull(b, hulls[b["model"]], swing_yaw(b, f), dx=pitch)
            d = poly_distance(P, Q)
            if d < best[0]:
                best = (d, (a["name"], b["name"]))
    return best


def max_clear_angle(spec, hulls, step=0.25):
    """The largest swing (deg) at which flush neighbours' leaves still clear (search in `step` deg)."""
    lf = leaves(spec)[0]
    span = abs(lf["yaw_open"] - lf["yaw_closed"])
    a = 0.0
    while a < 180.0:
        if neighbour_clearance(spec, hulls, (a + step) / span)[0] <= 0:
            return a
        a += step
    return a


def sweep_report(spec, hulls, steps=34):
    """Over the whole swing (0..1) per leaf: the minimum |y| any leaf point reaches (must stay in front of the frame,
    |y| >= 0.598), the max |x| (inside the side plane) and the open leaf's inner edge |x| (the opening it leaves)."""
    out = {}
    for lf in leaves(spec):
        h = hulls[lf["model"]]
        miny, maxx = 9.0, 0.0
        for k in range(steps + 1):
            P = placed_hull(lf, h, swing_yaw(lf, k / steps))
            miny = min(miny, min(abs(y) for _, y in P))
            maxx = max(maxx, max(abs(x) for x, _ in P))
        P1 = placed_hull(lf, h, lf["yaw_open"])
        out[lf["name"]] = {"min_abs_y": round(miny, 5), "max_abs_x": round(maxx, 5),
                           "open_inner_abs_x": round(min(abs(x) for x, y in P1 if abs(y) > 0.625), 5)}
    return out


def closed_boxes(spec, hulls, zs):
    """Closed leaves' AABBs in the block frame: {name: (lo, hi)} (zs: {model: (z0, z1)} measured)."""
    out = {}
    for lf in leaves(spec):
        P = placed_hull(lf, hulls[lf["model"]], lf["yaw_closed"])
        z0, z1 = zs[lf["model"]]
        out[lf["name"]] = ((min(x for x, _ in P), min(y for _, y in P), z0),
                           (max(x for x, _ in P), max(y for _, y in P), z1))
    return out
