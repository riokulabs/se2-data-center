"""Cross-section and layout helpers of the tray kit (Plan 2 Task 4). Pure Python (numpy), no Blender.

dc/tray_kit.py turns the plans (dc/tray_plan.py) into meshes; every decision it makes that can be checked without
Blender lives here, so Tests/test_tray_build.py checks it offline:

- the 7-cable lay of a bundle and which cable faces are ever visible (the hidden centre cable and the faces pressed
  against a neighbour are not built);
- the strap groups: bundles that nest share one band per station (Ruling P2-17), and that band's outline;
- the basket's wire stations (U-wires) and the per-point wall height of a path, with the step from a junction's
  0.15 m walls down to the 0.10 m straight walls at a port (Ruling P2-20);
- the LOD simplification of bundle centrelines.

Frames: a cross-section point is (s, h) in a path frame (s across, h along the floor normal), as in tray_lanes.
"""
import math

import numpy as np

from . import tray_lanes as TL

# ---------------------------------------------------------------------------------------------------- the basket
FLOOR_PITCH = 0.05            # longitudinal floor wires every 5 cm across ...
FLOOR_S = tuple(round(-0.20 + FLOOR_PITCH * k, 4) for k in range(9))   # ... s = -0.20 .. +0.20 (9 wires)
LOWER_WALL_H = 0.05           # the lower wall wire, above the floor top
U_PITCH = (0.10, 0.20)        # U-wire pitch per LOD (LOD2 and later: none, the card carries the mesh)
U_PHASE = 0.05                # the first U-wire this far from each port: the 0.1 m rhythm continues across a joint
U_LEG_DS = 2 * TL.WIRE_R      # U-wire legs stand on the outside of the longitudinal wall wires (welded crossings)
U_FLOOR_DH = -3 * TL.WIRE_R   # U-wire centre under the floor top: below the longitudinal floor wires
FLOOR_WIRE_DH = -TL.WIRE_R    # longitudinal floor wire centre under the floor top (their tops = the floor top)
EDGE_TURN = TL.EDGE_WIRE_R + TL.WIRE_R   # the U-wire's turned-over end rides on top of the safety-edge wire


def u_stations(length, lod=0, phase=U_PHASE):
    """Arc lengths of the U-wires along a basket path of `length`: every U_PITCH[lod] from `phase`, symmetric (the
    same set measured from either port) when the length allows. LOD1 keeps every other LOD0 wire."""
    if lod >= len(U_PITCH):
        return []
    n = int(math.floor((length - 2 * phase) / U_PITCH[0] + 1e-9)) + 1
    base = [round(phase + k * U_PITCH[0], 6) for k in range(n)]
    step = int(round(U_PITCH[lod] / U_PITCH[0]))
    return base[::step]


def branch_u_stations(length, lod=0, phase=U_PHASE, clear=0.02):
    """A junction branch's U-wires (its port at the path's END, its start free inside the junction): every U_PITCH
    from `phase` off the port, as far as `clear` short of the free end, as arc lengths from the path's start."""
    if lod >= len(U_PITCH):
        return []
    out, d = [], phase
    while d <= length - clear + 1e-9:
        out.append(round(length - d, 6))
        d += U_PITCH[lod]
    return out


# ---------------------------------------------------------------------------------------------------- bends
BEND_FACET = math.radians(15)  # LOD0: a bend's arc is faceted on radial lines at most 15 deg apart ...
#                                (the U-wires stand on exactly these radials, so every wire crossing is a vertex)


def bend_facet_count(angle, lod=0):
    """How many equal facets a bend's arc of `angle` gets at a LOD: LOD0 every <= 15 deg, LOD1 every other one,
    LOD2 and later two (the mid radial)."""
    n0 = max(2, int(math.ceil(angle / BEND_FACET - 1e-9)))
    return (n0, max(2, n0 // 2), 2)[min(lod, 2)]


def bend_facets(length, arc, lod=0):
    """Centreline arc lengths at which the kit samples every longitudinal part of a bend (floor and wall wires,
    bundles): the radial lines of its facets. arc = (l0, l1, angle), the path's Path.arc. LOD0: both ports, both
    lead ends and the arc's facet radials, so every wire and bundle bends on the same radials, and the 5 cm leads
    stay straight (the PORT rule). LOD1 and later: the ports and the interior radials only (the leads fold into the
    first and last chords; the kit squares the end rings to the ports)."""
    l0, l1, angle = arc
    n = bend_facet_count(angle, lod)
    inner = [l0 + (l1 - l0) * k / n for k in range(1, n)]
    if lod == 0:
        return [0.0, l0] + inner + [l1, length]
    return [0.0] + inner + [length]


def bend_u_stations(arc, lod=0):
    """A bend's U-wires: on its LOD0 facet radials, from the arc's start to its end (both lead ends, 5 cm from each
    port, where a straight has its first U-wire too); LOD1 on every other one (the LOD1 facets); LOD2 none."""
    if lod >= len(U_PITCH):
        return []
    l0, l1, angle = arc
    n = bend_facet_count(angle, lod)
    return [l0 + (l1 - l0) * k / n for k in range(n + 1)]


def path_facets(path, lod=0):
    """A basket path's facet stations at a LOD (bend_facets), or None (a straight path: the kit uses its points)."""
    if not getattr(path, "arc", ()):
        return None
    return bend_facets(float(path.lengths()[-1]), path.arc, lod)


def _unique(stations, eps=1e-9):
    out = []
    for v in sorted(stations):
        if not out or v - out[-1] > eps:
            out.append(float(v))
    return out


def sweep_facets(segs, lod=0, extra=()):
    """The facet stations (arc lengths along a junction bundle's own sweep, Task 7) at a LOD, the bends' rule
    generalised to a sweep of several straights and arcs: segs = [(kind, length, angle)].
    LOD0: every segment end, and each turn every <= 15 deg (BEND_FACET; a ramp arc of <= 45 deg is one chord, which
    kinks 15 deg at each end, as a bend's facets do), plus `extra` (a dressed bundle's ramp points);
    LOD1: the arcs at every other facet, the end leads folded into the first and last chords (as a bend's; a ramp's
    foot arc too: the Cross's c-d stack runs port -> incline top -> deck -> ... at LOD1);
    LOD2: one arc -> its mid radial (a bend's LOD2), several -> the ends of the longest straight (the Cross's deck)."""
    ends, arcs, l0 = [0.0], [], 0.0
    for kind, L, ang in segs:
        if kind == "arc":
            arcs.append((l0, l0 + L, ang))
        l0 += L
        ends.append(l0)
    total = ends[-1]
    if lod >= 2:
        if len(arcs) == 1:
            a, b, _ = arcs[0]
            return _unique([0.0, (a + b) / 2, total])
        k = max((i for i, sg in enumerate(segs) if sg[0] == "line"), key=lambda i: segs[i][1])
        return _unique([0.0, ends[k], ends[k + 1], total])
    out = list(ends)
    if lod == 1:     # fold the end leads (and on a ramp, its foot's arc) into the first and last chords
        fold = 2 if len(arcs) > 1 else 1
        for i in range(fold):
            if segs[i][0] == "line" or i > 0:
                out.remove(ends[1 + i])
            if (segs[-1 - i][0] == "line" or i > 0) and len(segs) > 1:
                out.remove(ends[-2 - i])
    for a, b, ang in arcs:      # a turn (90 deg) as a bend's; a short ramp arc (the Cross's 30 deg) as one chord,
        n = bend_facet_count(ang, lod) if ang > math.radians(45) else 1     # a kink of 15 deg at each end (a bend's)
        out += [a + (b - a) * k / n for k in range(1, n)]
    return _unique(out + list(extra))


def lay_locked(b):
    """Whether a bundle's lay is phase-locked (whole cable pitches): it ends on a PORT or an ENTRY. A bundle that
    starts on its port (a Reducer's dropped lane, from port a) starts in phase 0 anyway; one that ends on its port (a
    junction's split child, from its collar to port c) must arrive in phase 0, so its lay turns whole pitches. A
    waterfall (Task 8) arrives at its entry in phase 0 too, its frame turned to the entry's a axis (frame_drift): a
    Drop's waterfall and the Chute under it meet strand to strand."""
    return b.ends[-1].kind in ("PORT", "ENTRY")


def bundle_facets(plan, b, lod=0):
    """The facet stations a bend's bundle is built at (its plan points carry their centreline arc lengths in
    params["along"]; the piece's basket path carries the arc), a junction bundle's own (params["facets"] per LOD,
    Task 7), or None."""
    if "facets" in b.params:
        return list(b.params["facets"][min(lod, 2)])
    if "along" not in b.params:
        return None
    path = next((p for p in plan.structure if p.kind == "basket" and getattr(p, "arc", ())), None)
    return None if path is None else path_facets(path, lod)


def built_centreline(plan, b, lod=0, tol=0.001):
    """The centreline the kit sweeps a bundle along at a LOD: a bend's bundle re-sampled on the facet radials,
    any other simplified to `tol` (tray_kit.TOL[lod])."""
    fac = bundle_facets(plan, b, lod)
    return simplify_bundle(b, tol) if fac is None else resample(b.points, b.params["along"], fac)


def resample(points, along, stations):
    """A polyline sampled at `along` (each point's centreline arc length) re-sampled at `stations` (on the same
    scale; the last station is the far end), its two end points kept exactly (they lie on the port planes)."""
    p = np.asarray(points, float)
    a = np.asarray(along, float)
    st = np.asarray(stations, float) * (a[-1] / stations[-1])
    out = np.column_stack([np.interp(st, a, p[:, k]) for k in range(p.shape[1])])
    out[0], out[-1] = p[0], p[-1]
    return out


STEP_AT = U_PHASE + 0.01      # a junction wall's step-down ramp starts just past the first U-wire ...
STEP_RAMP = 0.05              # ... and rises over 5 cm (Ruling P2-20), ending before the second U-wire


def step_stations(length, port_start=True, port_end=True):
    """The arc lengths where a junction wall's step-down ramps start and end (the LOD2 card breaks there)."""
    out = []
    if port_start:
        out += [STEP_AT, STEP_AT + STEP_RAMP]
    if port_end:
        out += [length - STEP_AT - STEP_RAMP, length - STEP_AT]
    return [v for v in out if 0.0 < v < length]


def wall_height_profile(lengths, wall_h, port_start=True, port_end=True, ramp=STEP_RAMP, low=TL.WALL_H):
    """Per point (arc lengths `lengths`) the wall top-wire height of a basket path. A straight's wall is `low`
    everywhere. A junction's taller walls (`wall_h` > `low`) step down to `low` at every PORT end so the neighbouring
    straight meets them flush (Ruling P2-20): flat `low` up to just past the first U-wire (STEP_AT, so that U-wire and
    the splice plate stand exactly as a straight's), then a straight 45 deg slope over `ramp` m (the wire bent twice,
    as a real stepped wall wire is), done before the second U-wire."""
    L = np.asarray(lengths, dtype=float)
    h = np.full(len(L), float(wall_h))
    if wall_h <= low + 1e-9:
        return h
    total = L[-1]

    def ease(d):
        return np.clip((d - STEP_AT) / ramp, 0.0, 1.0)
    w = np.ones(len(L))
    if port_start:
        w = np.minimum(w, ease(L))
    if port_end:
        w = np.minimum(w, ease(total - L))
    return low + (wall_h - low) * w


# ---------------------------------------------------------------------------------------------------- junctions
# A T or X junction's run walls are cut open where a branch leaves and closed by r 0.15 fillet walls ("wall" paths,
# dc/tray_bends). Between a fillet and the two outer floor wires it joins, the floor is filled as a cut-and-welded
# basket is: an edge wire 1 cm in from the fillet wall (as a straight's outer floor wire is 1 cm in from its wall),
# and stubs on the 5 cm floor pitch from it to the outer floor wires. The fillet's own wall stands on two posts, the
# U-wires of a curved wall, a quarter and three quarters round it.
FLOOR_EDGE_IN = TL.WALL_S - FLOOR_S[-1]      # 0.01: a floor's outer wire lies this far inside its wall
STUB_MIN = 0.02                              # corner floor stubs shorter than this are left out
POST_AT = (0.25, 0.75)                       # fillet posts at these fractions of the arc (none at its 45 deg mid,
#                                              where the fillet passes closest to the free corner cell)


def fillet_geometry(path):
    """A fillet "wall" path's (centre, A, B, R) in its plane: A its start (on the run's wall line), B its end (on the
    branch's), R its radius. The centre is recovered from the points (it survives any rigid placement)."""
    from .tray_plan import fillet_centre
    p = np.asarray(path.points, float)
    A, B = p[0], p[-1]
    c = fillet_centre(path)
    return c, A, B, float(np.linalg.norm(A - c))


def fillet_frame(path):
    """(c, e1, e2, R): the fillet's centre, the unit directions from it towards B and towards A (floor points are
    c + a e1 + b e2 with a, b >= 0 outside the circle of radius R), and the radius."""
    c, A, B, R = fillet_geometry(path)
    return c, (B - c) / R, (A - c) / R, R


def corner_floor(path):
    """The floor wires that fill one fillet corner, as point pairs on the floor top (the kit lowers them to the
    floor-wire layer): the edge arc (radius R + FLOOR_EDGE_IN about the fillet's centre, from the run's outer floor
    wire to the branch's) as a polyline, and the stubs on the 5 cm floor pitch from it out to the outer floor wires.
    -> (edge points (N, 3), [(p0, p1)] stubs)."""
    c, e1, e2, R = fillet_frame(path)
    re = R + FLOOR_EDGE_IN
    edge = np.array([c + re * (math.sin(f) * e1 + math.cos(f) * e2) for f in np.linspace(0, math.pi / 2, 13)])
    stubs = []
    k = 1
    while re - k * FLOOR_PITCH > 0:
        a = re - k * FLOOR_PITCH
        b0 = math.sqrt(re * re - a * a)
        if re - b0 >= STUB_MIN:
            stubs.append((c + a * e1 + b0 * e2, c + a * e1 + re * e2))      # towards the run's outer floor wire
            stubs.append((c + b0 * e1 + a * e2, c + re * e1 + a * e2))      # towards the branch's
        k += 1
    return edge, stubs


def fillet_posts(path):
    """Arc lengths of a fillet wall's posts (POST_AT of its length)."""
    L = float(path.lengths()[-1])
    return [f * L for f in POST_AT]


def corner_card(path, off=TL.U_LEG_S, n=4):
    """LOD2: the floor card's fill of one fillet corner, a fan of n triangles from the corner of the two cards'
    edges (each `off` from its path, U_LEG_S like every card) to the fillet arc pushed out to the same line."""
    c, e1, e2, R = fillet_frame(path)
    r = R - (off - TL.WALL_S)
    K = c + r * e1 + r * e2
    arc = [c + r * (math.sin(f) * e1 + math.cos(f) * e2) for f in np.linspace(0, math.pi / 2, n + 1)]
    return [(K, arc[i], arc[i + 1]) for i in range(n)]


# ---------------------------------------------------------------------------------------------------- bundles
CABLES = 6                   # the six outer cables of a 7-cable bundle (the centre one is never visible)
CABLE_RING = 2 * TL.R_CABLE   # their centres lie on this radius round the bundle centre
CABLE_PHASE = -math.pi / 2    # one cable at the bottom: a floor bundle rests on it


def cable_centres(phase=CABLE_PHASE):
    """(s, h) offsets of the six outer cables from the bundle centre."""
    return [(CABLE_RING * math.cos(phase + k * math.pi / 3), CABLE_RING * math.sin(phase + k * math.pi / 3))
            for k in range(CABLES)]


def cable_arc(phase=CABLE_PHASE):
    """Per cable, its visible cross-section polyline (offsets from the BUNDLE centre): three faces over the cable's
    exposed 240 deg, between its two contact points with its neighbours (+-120 deg from its outward direction). The
    part that faces the hidden centre cable is not built; neighbouring arcs share their contact points, so the
    bundle's outer skin is closed, with a crevice between each pair of cables."""
    out = []
    r = TL.R_CABLE
    for k, (cs, ch) in enumerate(cable_centres(phase)):
        phi = phase + k * math.pi / 3
        out.append([(cs + r * math.cos(phi + a), ch + r * math.sin(phi + a))
                    for a in (math.radians(d) for d in (-120, -40, 40, 120))])
    return out


LAY_TURN = math.radians(60)   # the cables' lay: the six outer cables turn 60 deg (one cable pitch) ...
LAY_LEN = 0.5                  # ... per 0.5 m of bundle,
LAY_SEG = 0.25                 # in straight segments of at most 0.25 m (30 deg each: a chord sags 0.6 mm)
STRAP_BITE = 0.0015            # LOD0: a strap's band lies this far inside the bundle radius (it cinches the cables)


def lay_pitches(length):
    """The per-piece lay rule (Ruling P2-22): a bundle that runs port to port turns a WHOLE number of cable pitches
    (60 deg), the number nearest its own length at the nominal rate, and at least one. Each lane of a bend is its own
    length (inner lanes are shorter than outer ones), so each lane's rate differs slightly from the nominal 60 deg per
    0.5 m, but every lane leaves both ports in phase 0: the strand pattern is the same on every port face, and the
    lay continues across every joint. At least one pitch: no lane runs untwisted (a lane must be >= 0.25 m for its
    rate to stay within 2x nominal; tray_build tests every catalogue piece)."""
    return max(1, int(round(length / LAY_LEN)))


def lay_total(length, lock=True):
    """The lay rotation over a bundle of `length`. lock (a bundle that runs port to port): lay_pitches whole cable
    pitches, so it leaves its far end in the phase it entered (the six outer cables are interchangeable); otherwise
    (it ends in a boot, a collar or an entry) the plain rate. The helix keeps its hand when a piece is turned (a
    rotation), so neighbours always twist the same way."""
    if not lock:
        return LAY_TURN * length / LAY_LEN
    return LAY_TURN * lay_pitches(length)


def lay_points(points, lock=True):
    """The bundle centreline with points added so no segment is longer than LAY_SEG, and each point's lay angle."""
    p = np.asarray(points, dtype=float)
    out = [p[0]]
    for a, b in zip(p, p[1:]):
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / LAY_SEG - 1e-9)))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    q = np.array(out)
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
    total = lay_total(L[-1], lock)
    return q, (total * L / L[-1] if L[-1] > 0 else np.zeros(len(q)))


def port_leads(points, ends, lead=TL.PORT_STRAIGHT):
    """Indices of a bundle's points that close its straight PORT leads: the last point within `lead` along from each
    PORT end (the PORT rule: straight for the last 5 cm, so that point is still on the straight). Kept by any
    simplification, so a dressed bundle whose dressing starts right after its lead still meets its port square."""
    p = np.asarray(points, float)
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    out = []
    if ends[0].kind == "PORT":
        out.append(int(np.searchsorted(L, lead + 1e-9, side="right")) - 1)
    if ends[-1].kind == "PORT":
        out.append(int(np.searchsorted(L, L[-1] - lead - 1e-9)))
    return sorted({i for i in out if 0 < i < len(p) - 1})


def simplify_keep(points, tol, keep=()):
    """simplify() that keeps the points at indices `keep` (it simplifies between them)."""
    p = np.asarray(points, dtype=float)
    cuts = [0] + sorted(set(keep)) + [len(p) - 1]
    parts = [simplify(p[a:b + 1], tol) for a, b in zip(cuts, cuts[1:]) if b > a]
    return np.vstack([parts[0]] + [q[1:] for q in parts[1:]])


# ---------------------------------------------------------------------------------------------------- built skin
# The kit's sweep frames and a bundle's LOD0 skin, in numpy (Task 7 fix round 1): dc/tray_kit.frames wraps
# frames_np, and tray_kit.bundle builds exactly the rings skin_rings returns, so the built-mesh clearance of every
# bundle pair is tested offline (Tests/test_tray_build.py::test_built_bundles_clear).
def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _rotate(v, axis, ang):
    """v rotated by ang about the unit axis (Rodrigues)."""
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * (axis @ v) * (1 - math.cos(ang))


def frames_np(points, up=None, ends=None):
    """Rotation-minimising frames (t, s, u) along a polyline: t the tangent (the mean of the two segment directions
    at a corner), u parallel-transported from `up` (default +z, or +x when the path starts vertical), s = u x t, so
    (t, s, u) is right-handed like a port frame. Also each point's mitre (scale 1 / cos(half the turn), and the bend
    direction it applies along). ends = (t0, t1): the end tangents instead of the end segments' directions (a bend's
    coarse LOD folds the lead into its first chord; its end rings stay square to the port, so they lie on it)."""
    pts = np.asarray(points, float)
    n = len(pts)
    segs = [_unit(pts[i + 1] - pts[i]) for i in range(n - 1)]
    ts, mit = [], []
    for i in range(n):
        if i == 0:
            t = segs[0] if ends is None else _unit(np.asarray(ends[0], float))
        elif i == n - 1:
            t = segs[-1] if ends is None else _unit(np.asarray(ends[1], float))
        else:
            t = segs[i - 1] + segs[i]
            t = _unit(t) if np.linalg.norm(t) > 1e-9 else segs[i]
        ts.append(t)
        if 0 < i < n - 1:
            c = max(0.2, float(t @ segs[i]))
            m = segs[i] - segs[i - 1]
            mit.append((1.0 / c, _unit(m) if np.linalg.norm(m) > 1e-9 else None))
        else:
            mit.append((1.0, None))
    u = np.asarray(up, float) if up is not None else np.array([0.0, 0.0, 1.0])
    if abs(_unit(u) @ ts[0]) > 0.95:
        u = np.array([1.0, 0.0, 0.0]) if abs(ts[0][0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = _unit(u - ts[0] * (u @ ts[0]))
    out = []
    for i in range(n):
        if i > 0:
            a, b = ts[i - 1], ts[i]
            ax = np.cross(a, b)
            if np.linalg.norm(ax) > 1e-9:
                u = _rotate(u, _unit(ax), math.acos(max(-1.0, min(1.0, float(a @ b)))))
            u = _unit(u - b * (u @ b))
        out.append((ts[i], np.cross(u, ts[i]), u))
    return out, mit


def floor_up(plan, q):
    """The floor normal of the basket path point nearest to q (a bundle's sweep starts from it)."""
    best, up = 9.0, np.array([0.0, 0.0, 1.0])
    for path in plan.structure:
        d = np.linalg.norm(np.asarray(path.points, float) - np.asarray(q, float), axis=1)
        i = int(np.argmin(d))
        if d[i] < best:
            best, up = d[i], np.asarray(path.normals[i], float)
    return up


def frame_drift(plan, b, pts, up, ends):
    """Per point, the twist that cancels the rotation-minimising frame's drift along a non-planar bundle (the Tee's
    F1+ lane rises over the M0 collar while it turns in plan: its transported frame arrives ~1.4 deg rolled), spread
    evenly along it, so a bundle that ends on a PORT arrives with the port's floor normal (its strands in phase 0).
    Zero for every planar bundle (straights, bends, the Cross's ramps)."""
    pts = np.asarray(pts, float)
    if b.ends[-1].kind not in ("PORT", "ENTRY") or len(pts) < (3 if b.ends[-1].kind == "PORT" else 2):
        return np.zeros(len(pts))
    fr, _ = frames_np(pts, up, ends)
    t, _, u = fr[-1]
    if b.ends[-1].kind == "PORT":
        want = np.asarray(plan.ports[b.ends[-1].ref.split(":")[0]].u, float)
    else:      # an entry: its in-plane a axis (the frame a straight Chute bundle starts in)
        want = np.asarray(next(e for e in plan.entries if e.name == b.ends[-1].ref).a, float)
        want = _unit(want - t * (want @ t))
    ang = math.atan2(float(np.cross(u, want) @ t), float(u @ want))
    if abs(ang) < 1e-6:
        return np.zeros(len(pts))
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    return ang * L / L[-1]


def bundle_path(plan, b, lod, tol):
    """The polyline the kit sweeps a bundle along at a LOD and its end tangents: a faceted bundle (a bend's, a
    junction's) re-sampled on its facets with its end rings square to its ports, any other simplified (tol)."""
    fac = bundle_facets(plan, b, lod)
    if fac is not None:
        p = np.asarray(b.points, float)
        return resample(b.points, b.params["along"], fac), (p[1] - p[0], p[-1] - p[-2])
    if lod >= 1 and b.params.get("dress"):      # the Drop's dressing is a LOD0 detail: the lane lies straight
        p = np.asarray(b.points, float)
        return p[[0, -1]], None
    if lod >= 1 and "stretches" in b.params:     # a waterfall: its stretch ends, its arcs in a few chords
        from .tray_plan import waterfall_stations
        st = waterfall_stations(b, lod)
        return resample(b.points, b.params["along"], st), None
    return simplify_bundle(b, tol), None


def skin_profile(scale=1.0):
    """The closed LOD0 skin of a bundle's section: the six visible cables' arcs end to end (they share their
    contact points), counter-clockwise, as (s, h) offsets from the bundle centre."""
    out = []
    for arc in cable_arc():
        out += [(a * scale, c * scale) for a, c in arc[:-1]]
    return out


def skin_rings(plan, b, tol=0.001):
    """A bundle's LOD0 skin exactly as dc/tray_kit.bundle sweeps it (path, lay, frame drift, mitres): (centreline
    points (N, 3), rings (N, M, 3)), each ring the section's skin_profile at that point."""
    pts, ends = bundle_path(plan, b, 0, tol)
    up = floor_up(plan, pts[0])
    pts, lay = lay_points(pts, lock=lay_locked(b))
    lay = lay + frame_drift(plan, b, pts, up, ends)
    fr, mit = frames_np(pts, up, ends)
    prof = np.array(skin_profile(b.radius / TL.R_B))
    rings = []
    for q, (t, s, u), (k, m), a in zip(pts, fr, mit, lay):
        c, sn = math.cos(a), math.sin(a)
        rot = np.column_stack([prof[:, 0] * c - prof[:, 1] * sn, prof[:, 0] * sn + prof[:, 1] * c])
        o = rot[:, :1] * s + rot[:, 1:] * u
        if m is not None and k != 1.0:
            o = o + np.outer(o @ m, m) * (k - 1.0)
        rings.append(q + o)
    return np.asarray(pts), np.array(rings)


def simplify_bundle(b, tol):
    """A bundle's centreline simplified to `tol`, its straight PORT leads kept straight: when the plain simplification
    tilts a lead (a dressing ramp starting right after it), the lead's end point is kept (port_leads)."""
    q = simplify(b.points, tol)
    p = np.asarray(b.points, float)
    for (i, j), (a, c) in (((0, 1), (0, 1)), ((-1, -2), (-1, -2))):
        if b.ends[i].kind != "PORT":
            continue
        d0, d1 = p[j] - p[i], q[c] - q[a]
        if np.linalg.norm(np.cross(d0 / np.linalg.norm(d0), d1 / np.linalg.norm(d1))) > 1e-6:
            return simplify_keep(p, tol, port_leads(p, b.ends))
    return q


def simplify(points, tol):
    """Douglas-Peucker on a 3D polyline (keeps the ends). A bundle at a lower LOD follows its plan within `tol`."""
    p = np.asarray(points, dtype=float)
    if len(p) < 3:
        return p
    keep = np.zeros(len(p), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(p) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = p[i], p[j]
        d = b - a
        L = np.linalg.norm(d)
        seg = p[i + 1:j] - a
        if L < 1e-12:
            dist = np.linalg.norm(seg, axis=1)
        else:
            dist = np.linalg.norm(np.cross(seg, d / L), axis=1)
        k = int(np.argmax(dist))
        if dist[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return p[keep]


# ---------------------------------------------------------------------------------------------------- straps
def strap_groups(discs, gap=TL.TOUCH_TOL):
    """Connected groups of discs [(s, h, r)] that touch or nest (centre distance <= r1 + r2 + gap): one shared strap
    band per group and station (Ruling P2-17). Returns lists of indices, each sorted, groups ordered by first index."""
    n = len(discs)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            (a, b, r1), (c, d, r2) = discs[i], discs[j]
            if math.hypot(a - c, b - d) <= r1 + r2 + gap:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def convex_hull(points):
    """Andrew's monotone chain: the hull of 2D points, counter-clockwise, no repeated end point."""
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def band_outline(discs, pad=TL.STRAP_T, sides=10, floor_h=None):
    """A strap band round a group of discs [(s, h, r)]: the convex hull of the discs grown by `pad` (a tight band),
    as a counter-clockwise polygon. A single disc gives a regular `sides`-gon (its flats tangent to the padded circle
    are pushed out so the band never cuts the bundle). Several discs: each sampled at `sides` points, hull, then
    near-collinear points merged. floor_h: the band's underside is flattened to this height (it threads under the
    floor top, through the mesh) instead of following the round bottom."""
    pts = []
    for s, h, r in discs:
        R = (r + pad) / math.cos(math.pi / sides)          # the polygon circumscribes the padded circle
        pts += [(s + R * math.cos(math.pi / sides + 2 * math.pi * k / sides),
                 h + R * math.sin(math.pi / sides + 2 * math.pi * k / sides)) for k in range(sides)]
    if floor_h is not None:
        pts = [(s, max(h, floor_h)) for s, h in pts]
    hull = convex_hull(pts)
    return _merge_collinear(hull, 0.0015)


def _merge_collinear(poly, tol):
    """Drop hull points that lie within tol of the line through their neighbours (closed polygon)."""
    p = list(poly)
    changed = True
    while changed and len(p) > 3:
        changed = False
        for i in range(len(p)):
            a, b, c = p[i - 1], p[i], p[(i + 1) % len(p)]
            ab = math.hypot(c[0] - a[0], c[1] - a[1])
            if ab < 1e-12:
                continue
            d = abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / ab
            if d < tol:
                p.pop(i)
                changed = True
                break
    return p


def polygon_area(poly):
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))


def min_clearance(poly, discs):
    """The least distance from the polygon's edges to any disc's surface (negative = the band cuts a disc)."""
    best = 9.0
    for s, h, r in discs:
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            dx, dy = x1 - x0, y1 - y0
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((s - x0) * dx + (h - y0) * dy) / L2))
            d = math.hypot(x0 + t * dx - s, y0 + t * dy - h) - r
            best = min(best, d)
    return best


# ---------------------------------------------------------------------------------------------------- end caps
CAP_INSET = 0.0015      # the cap's plane: this far inside the port plane (never on it: no coplanar faces at a joint)
# The caps cost 16 triangles per bundle end (16 is the least that closes the section: a hexagon and six quads), so
# 288 on a 2-port Full piece and 576 on the Full Cross. Ruling P2-28 (Task 10 round 2): every piece is capped, the
# four Full pieces they lift over the plan's LOD0 budgets included (StraightS, StraightL, Cross, TurnDown): the cap
# triangles sit outside the per-metre and share-of-Keen LOD0 budgets (Keen's own limits still hold; LOD1+ has none).
CAP_TRIS = 16
CAP_SKIP = set()
