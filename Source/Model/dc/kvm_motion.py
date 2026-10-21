"""The scripted KVM motion, checked in geometry. Plain Python, no bpy.

Tests/CoreTests (`dotnet run -c Release -- --dump ...`) writes the game-free sequencer's trajectories
(Scripts/Client/Core/KvmMotion.cs, 240 Hz) to Source/Model/preview/plan4/traj/<name>.csv as `t,slide,fold,target`
(slide and fold normalised 0..1). This module places the KVM's two moving parts at those poses and measures them
against everything they could hit:

  - the KVM's own upper panel (`self_intrusion`, the `subparts.transient_intrusion` rule; `min_safe_fold_gate`);
  - the rack's closing door leaves (`leaf_clearance`: the fast stow must beat them);
  - the rack frame and the servers in the neighbouring slots (`obstacle_clearance`).

Frames. The KVM model's Blender frame (centred, +Y = front, Z up; dc/subparts.py). A KVM in rack slot k (1-based)
sits at rack-centred (0, 0, slot centre) and faces the rack's front (facing +1) or, turned 180 degrees about Z, its
rear (facing -1). The rack frame is dc/doors.py's: centred, +Y = front, z block-centred.

The moving parts. Each is a box in its own frame, sized from the BUILT subpart models (build_report.json
`subparts.models.<name>.bounds_local`, the pivot = the hinge), falling back to the design numbers (subparts.DRAWER_BOX,
subparts.LID) when no build report exists. The drawer translates by slide * TRAVEL along +Y; the lid rotates about the
hinge axis (x) by fold * FOLD_DEG and rides on the drawer. A leaf is a box too: the leaf layer (DOOR_HALF_T either side
of its mid-plane), from the hinge barrel's back (u = -DOOR_KNUCKLE_R) to its free edge (u = DOOR_W), over its z band.

Swept, not sampled. Every check runs over the trajectory's intervals [t_i, t_i+1], not just its instants. Within an
interval the CSV is interpolated linearly in (slide, fold) and the door's open ratio is linear in time, so:

  - a translating vertex sweeps the segment between its endpoints;
  - a translating AND rotating vertex (the lid) stays inside the parallelogram spanned by its translation and its
    rotation chord: the four "cross" vertices (both drawer ends x both lid angles) bound it;
  - a rotation's arc leaves its chord by at most its sagitta, r (1 - cos(dtheta / 2));
  - the true motion leaves the linear interpolation by at most |second difference| / 8 (`_interp_slack`).

So the convex hull of each part's interval vertices, inflated by those two slacks, contains every pose the part takes
in the interval. Hull-to-hull distances (GJK, exact for convex polytopes) minus the slacks are therefore LOWER bounds
on the true clearance (exact for the sagitta; the slack is a second-difference estimate, exact for smooth motion and
over-estimating at kinks, so on the safe side). `swept=False` measures at the instants only (the other side of the
bracket); test_swept_bounds_hold_when_decimated checks that the pads keep a 10 Hz bound on the safe side.

Per-slot paths: `motion_path_for_slot(rack, slot)` says which motion a slot runs ("data_only" in a
full rack's top slot, under the containment rail; "sequenced" elsewhere) and `path_runs(path)` lists every run
of that path the checks cover; the runtime sequencer (KvmRackSlot.cs) routes on the same rule.
"""
import csv
import glob
import hashlib
import math
import os
import re

from . import dims as DM
from . import doors
from . import subparts as S

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.dirname(HERE)                                  # Source/Model
MOD_DIR = os.path.normpath(os.path.join(MODEL_DIR, "..", ".."))
TRAJ_DIR = os.path.join(MODEL_DIR, "preview", "plan4", "traj")
CORE_DIR = os.path.join(MOD_DIR, "Scripts", "Client", "Core")
# The game-free shared rules CoreTests also compiles (the surgery and scripting rules): part of the same digest.
SHARED_CORE_DIR = os.path.join(MOD_DIR, "Scripts", "Simulation", "Shared", "Core")
TUNING_CS = os.path.join(CORE_DIR, "KvmMotionTuning.cs")
BUILD_REPORT = os.path.join(MODEL_DIR, "build_report.json")
# Written by CoreTests --dump after a passing run: the digest of the core sources the dump was made from.
SOURCES_STAMP = os.path.join(TRAJ_DIR, "core_sources.sha256")

TRAJECTORIES = ("open", "close", "fast_stow", "reverse_mid_slide", "reverse_mid_fold", "door_close_while_out")
DOOR_RACKS = ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")

FACE_Y = S.FACE_Y                   # the KVM's face plane (bezel front): the upper panel lies behind it
BAY_ROOF_Z = S.BAY["z1"]            # ... and above the bay roof


# ================================================================================================ trajectories

def core_sources_digest(*core_dirs):
    """SHA-256 of the game-free core sources CoreTests compiles: for each directory in turn (default Scripts/Client/Core,
    then Scripts/Simulation/Shared/Core), each *.cs in ordinal file-name order: the file name, a newline, the text with
    CRLF read as LF, a newline. Tests/CoreTests/Program.cs (CoreSourcesDigest) computes the same digest and stamps it
    into SOURCES_STAMP when it dumps, so a dump is fresh exactly when the sources it came from are the ones on disk:
    content, not modification times, which a checkout or a copy reorders."""
    h = hashlib.sha256()
    for core_dir in core_dirs or (CORE_DIR, SHARED_CORE_DIR):
        for path in sorted(glob.glob(os.path.join(core_dir, "*.cs")), key=lambda p: os.path.basename(p).encode()):
            with open(path, "rb") as fh:
                text = fh.read().replace(b"\r\n", b"\n")
            h.update(os.path.basename(path).encode() + b"\n" + text + b"\n")
    return h.hexdigest()


def dump_stamp(path=SOURCES_STAMP):
    """The core digest the dump in TRAJ_DIR was made from, or None when it carries no stamp."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip() or None


def _rows(name):
    path = name if os.path.isabs(name) else os.path.join(TRAJ_DIR, name + ".csv")
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def load(name):
    """[(t, slide, fold)] of the trajectory `name` (a TRAJECTORIES entry, or a CSV path)."""
    return [(float(r["t"]), float(r["slide"]), float(r["fold"])) for r in _rows(name)]


def first_command(name, target):
    """The time of the first frame whose target is `target` (e.g. "FastStow"), or None."""
    return next((float(r["t"]) for r in _rows(name) if r["target"] == target), None)


def pose(slide, fold):
    """(drawer offset m, lid angle deg) of a normalised pose."""
    return S.TRAVEL * slide, S.FOLD_DEG * fold


def _lerp_pose(a, b, t):
    """The pose at time t inside the sample interval a..b ((t, slide, fold) each)."""
    if b[0] <= a[0]:
        return (t, a[1], a[2])
    k = (t - a[0]) / (b[0] - a[0])
    return (t, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k)


def _interp_slack(traj):
    """Per interval: (slide, fold) bounds on how far the true motion leaves the linear interpolation of the samples.
    For a C2 curve the chord error is at most h^2 max|x''| / 8; the second differences around the interval estimate
    h^2 x'' (a hard-stop kink only inflates it, which stays conservative)."""
    n = len(traj)
    d2 = [0.0] * n
    for i in range(1, n - 1):
        d2[i] = (abs(traj[i + 1][1] - 2 * traj[i][1] + traj[i - 1][1]),
                 abs(traj[i + 1][2] - 2 * traj[i][2] + traj[i - 1][2]))
    d2[0] = d2[1] if n > 2 else (0.0, 0.0)
    d2[-1] = d2[-2] if n > 2 else (0.0, 0.0)
    return [(max(d2[i][0], d2[i + 1][0]) / 8.0, max(d2[i][1], d2[i + 1][1]) / 8.0) for i in range(n - 1)]


def intervals(traj, swept=True):
    """[(a, b, slack)] the checks run over. swept: every sample interval with its interpolation slack (the bounds are
    lower bounds on clearances, upper bounds on intrusions); not swept: every sample as a zero-length interval with no
    slack (the poses at the instants only: the other side of the bracket)."""
    if not swept:
        return [(p, p, (0.0, 0.0)) for p in traj]
    return [(a, b, sl) for (a, b), sl in zip(zip(traj, traj[1:]), _interp_slack(traj))]


# ================================================================================================ the moving parts

def _built_bounds(model):
    try:
        import json
        with open(BUILD_REPORT) as fh:
            rep = json.load(fh)
        return rep["blocks"][S.KVM]["subparts"]["models"][model]["bounds_local"]
    except (OSError, KeyError, ValueError):
        return None


def _drawer_local():
    """The drawer's box relative to its pivot (the stowed hinge), KVM axes: ((x0, y0, z0), (x1, y1, z1))."""
    b = _built_bounds(S.DRAWER)
    if b:
        return tuple(b[0]), tuple(b[1])
    d, (_, hy, hz) = S.DRAWER_BOX, S.HINGE
    return (-d["x"], d["y0"] - hy, d["z0"] - hz), (d["x"], d["y_front"] - hy, d["z1"] - hz)


def _lid_local():
    """The lid's box in its own frame (hinge axis = x, lying along +y): ((x0, y0, z0), (x1, y1, z1))."""
    b = _built_bounds(S.SCREEN)
    if b:
        return tuple(b[0]), tuple(b[1])
    w, L, t = S.LID["half_w"], S.LID["len"], S.LID["half_t"]
    return (-w, -t, -t), (w, L, t)


DRAWER_LOCAL = _drawer_local()
LID_LOCAL = _lid_local()


def _corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


_DRAWER_C = _corners(*DRAWER_LOCAL)
_LID_C = _corners(*LID_LOCAL)
LID_RADIUS = max(math.hypot(y, z) for _, y, z in _LID_C)          # the lid's farthest point from the hinge axis


def drawer_at(dy):
    """The drawer's 8 corners in the KVM frame, out by dy."""
    hx, hy, hz = S.HINGE
    return [(x + hx, y + hy + dy, z + hz) for x, y, z in _DRAWER_C]


def lid_box_at(dy, deg):
    """The (built) lid box's 8 corners in the KVM frame, the drawer out by dy and the lid folded by deg."""
    hx, hy, hz = S.HINGE
    return [(x + hx, y + hy + dy, z + hz) for x, y, z in (S.rot_x(c, deg) for c in _LID_C)]


def kvm_parts(slide, fold):
    """{"drawer": corners, "lid": corners} in the KVM frame at a normalised pose."""
    dy, deg = pose(slide, fold)
    return {"drawer": drawer_at(dy), "lid": lid_box_at(dy, deg)}


def _swept_parts(a, b, slack):
    """Per part, (vertices whose hull holds every pose in the interval a..b, inflation radius): see the docstring."""
    (dya, dega), (dyb, degb) = pose(a[1], a[2]), pose(b[1], b[2])
    s_slide, s_fold = slack
    lin = s_slide * S.TRAVEL                                         # interpolation slack, metres of drawer
    dtheta = math.radians(abs(degb - dega) + s_fold * S.FOLD_DEG)    # the lid's sweep incl. slack
    sag = LID_RADIUS * (1.0 - math.cos(dtheta / 2.0))
    ang = LID_RADIUS * math.radians(s_fold * S.FOLD_DEG)
    drawer = drawer_at(dya) + drawer_at(dyb)
    lid = lid_box_at(dya, dega) + lid_box_at(dyb, degb) + lid_box_at(dya, degb) + lid_box_at(dyb, dega)
    return {"drawer": (drawer, lin), "lid": (lid, lin + sag + ang)}


# ================================================================================================ rack placement

def slot_centre_z(spec, slot):
    """Block-centred z of slot `slot`'s centre (1-based, from the bottom)."""
    H, _, _ = doors.rack_dims(spec)
    return 0.25 + DM.SLOT_H * (slot - 1) + DM.SLOT_H / 2 - H / 2


def nslots(spec):
    return DM.rack_frame(spec.cells[1])[3]


def to_rack(points, spec, slot, facing=1):
    """KVM-frame points into the rack frame: slot `slot`, facing the front (+1) or the rear (-1)."""
    zc = slot_centre_z(spec, slot)
    return [(facing * x, facing * y, z + zc) for x, y, z in points]


# ================================================================================================ door leaves

def leaf_box(spec, leaf, open_fraction):
    """A leaf's 8 corners in the rack frame at open fraction f (1 = open, 0 = closed)."""
    s = 1 if leaf["model"] == doors.LEAF_R else -1                  # DoorLeafR extends toward -x
    z0, z1 = doors.z_range(spec)
    yaw = doors.swing_yaw(leaf, open_fraction)
    out = []
    for u in (-DM.DOOR_KNUCKLE_R, DM.DOOR_W):
        for v in (-DM.DOOR_HALF_T, DM.DOOR_HALF_T):
            x, y = doors.place(leaf, (-s * u, v), yaw)
            out += [(x, y, z0), (x, y, z1)]
    return out


def leaf_grid(spec, leaf, open_fraction, nu=41, nz=9):
    """The leaf's mid-plane sampled as an nu x nz grid (a uniform sampling; see test_grid_agrees_with_hulls)."""
    s = 1 if leaf["model"] == doors.LEAF_R else -1
    z0, z1 = doors.z_range(spec)
    yaw = doors.swing_yaw(leaf, open_fraction)
    pts = []
    for i in range(nu):
        u = -DM.DOOR_KNUCKLE_R + (DM.DOOR_W + DM.DOOR_KNUCKLE_R) * i / (nu - 1)
        x, y = doors.place(leaf, (-s * u, 0.0), yaw)
        pts += [(x, y, z0 + (z1 - z0) * k / (nz - 1)) for k in range(nz)]
    return pts


LEAF_RADIUS = math.hypot(DM.DOOR_W, DM.DOOR_HALF_T)


def door_fraction(t, t_start, opening_s):
    """The closing door's OpenRatio at time t: 1 until t_start, then linear to 0 over opening_s (DoorServerComponent
    advances it linearly; no easing)."""
    return min(1.0, max(0.0, 1.0 - (t - t_start) / opening_s))


# ================================================================================================ convex distance

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _support(P, d):
    return max(P, key=lambda p: p[0] * d[0] + p[1] * d[1] + p[2] * d[2])


def _solve(G, r):
    """Gaussian elimination with partial pivoting for a k x k system (k <= 3); None if singular."""
    k = len(r)
    M = [list(G[i]) + [r[i]] for i in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda i: abs(M[i][c]))
        if abs(M[p][c]) < 1e-14:
            return None
        M[c], M[p] = M[p], M[c]
        for i in range(k):
            if i != c:
                f = M[i][c] / M[c][c]
                for j in range(c, k + 1):
                    M[i][j] -= f * M[c][j]
    return [M[i][k] / M[i][i] for i in range(k)]


def _closest_on_simplex(W):
    """The point of hull(W) (|W| <= 4) nearest the origin and the smallest subset of W it lies on. The nearest point
    lies in the relative interior of one face, where it is that face's affine projection of the origin; so the answer
    is the shortest projection whose barycentric weights are all non-negative (brute force over the <= 15 faces)."""
    best = None
    n = len(W)
    for mask in range(1, 1 << n):
        Y = [W[i] for i in range(n) if mask >> i & 1]
        y0 = Y[0]
        E = [_sub(y, y0) for y in Y[1:]]
        if E:
            mu = _solve([[_dot(a, b) for b in E] for a in E], [-_dot(a, y0) for a in E])
            if mu is None:
                continue
            lam = [1.0 - sum(mu)] + mu
            if min(lam) < -1e-12:
                continue
            v = tuple(y0[j] + sum(m * e[j] for m, e in zip(mu, E)) for j in range(3))
        else:
            v = y0
        d = _dot(v, v)
        if best is None or d < best[0] - 1e-18 or (abs(d - best[0]) <= 1e-18 and len(Y) < len(best[2])):
            best = (d, v, Y)
    return best[1], best[2]


def convex_distance(P, Q):
    """Euclidean distance between hull(P) and hull(Q) (3D point lists); 0.0 when they touch or overlap. GJK on the
    Minkowski difference P - Q with the exhaustive sub-simplex solver above (exact up to float round-off)."""
    v = _sub(P[0], Q[0])
    W = []
    for _ in range(64):
        vv = _dot(v, v)
        if vv < 1e-24:
            return 0.0
        w = _sub(_support(P, (-v[0], -v[1], -v[2])), _support(Q, v))
        if vv - _dot(v, w) <= 1e-12 * max(vv, 1e-12) or w in W:
            break
        v, W = _closest_on_simplex(W + [w])
        if len(W) == 4:
            return 0.0
    return math.sqrt(_dot(v, v))


def _aabb(P):
    return (tuple(min(p[j] for p in P) for j in range(3)), tuple(max(p[j] for p in P) for j in range(3)))


def aabb_gap(A, B):
    """Distance between two AABBs ((lo, hi) each): a cheap lower bound on the hull distance."""
    return math.sqrt(sum(max(0.0, A[0][j] - B[1][j], B[0][j] - A[1][j]) ** 2 for j in range(3)))


def min_distance(candidates):
    """Best-first branch and bound over [(lower bound, pad, P, Q, tag)]: the smallest hull(P)-to-hull(Q) distance less
    its pad, and its tag. A cheap lower bound (an AABB gap less the pad) orders the search and ends it as soon as no
    remaining candidate can beat the best found, so only the few near pairs ever run GJK."""
    best, tag = math.inf, None
    for bound, pad, P, Q, t in sorted(candidates, key=lambda c: c[0]):
        if bound >= best:
            break
        d = convex_distance(P, Q) - pad
        if d < best:
            best, tag = d, t
    return best, tag


def _candidate(P, Q, pad, tag, boxes=None):
    """A min_distance candidate; `boxes` = the AABBs of P and Q when the caller already has them."""
    bp, bq = boxes or (_aabb(P), _aabb(Q))
    return (aabb_gap(bp, bq) - pad, pad, P, Q, tag)


# ================================================================================================ the KVM's own panel

def _section(points):
    """The convex (y, z) outline of 3D points (the lid section: x plays no part in a rotation about x)."""
    return doors.convex_hull([(y, z) for _, y, z in points])


def _clip(poly, keep):
    """Sutherland-Hodgman: the part of a convex polygon where keep(p) <= 0 (keep is affine)."""
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        fa, fb = keep(a), keep(b)
        if fa <= 0:
            out.append(a)
        if (fa < 0 < fb) or (fb < 0 < fa):
            k = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
    return out


def _height_behind_face(section, pad=0.0):
    """The highest z above the bay roof of a lid section's part behind the face plane (grown by pad), or -inf."""
    part = _clip(section, lambda p: p[0] - (FACE_Y + pad))
    return max((z for _, z in part), default=-math.inf) - BAY_ROOF_Z + (pad if part else 0.0)


def self_intrusion(traj, swept=True):
    """The transient_intrusion rule over a trajectory: the largest height (m) the lid (subparts.LID, the rule's box)
    reaches above the bay roof while any of it is behind the face plane, i.e. how far it passes up into the KVM's own
    upper panel. <= 0 means it never does (negative = the margin under the roof). Swept over every interval."""
    worst = -math.inf
    for a, b, (ss, sf) in intervals(traj, swept):
        (dya, dega), (dyb, degb) = pose(a[1], a[2]), pose(b[1], b[2])
        pts = S.lid_at_pose(dya, dega) + S.lid_at_pose(dyb, degb) + S.lid_at_pose(dya, degb) + S.lid_at_pose(dyb, dega)
        r = max(math.hypot(y, z) for _, y, z in S.lid_corners())
        pad = (ss * S.TRAVEL + r * (1 - math.cos(math.radians(abs(degb - dega)) / 2))
               + r * math.radians(sf * S.FOLD_DEG))
        worst = max(worst, _height_behind_face(_section(pts), pad))
    return worst


def _sweep_height(slide, step_deg=0.05):
    """With the drawer held at `slide`, the worst self-intrusion of a full lid sweep 0 .. FOLD_DEG."""
    dy = S.TRAVEL * slide
    n = int(math.ceil(S.FOLD_DEG / step_deg))
    r = max(math.hypot(y, z) for _, y, z in S.lid_corners())
    pad = r * (1 - math.cos(math.radians(S.FOLD_DEG / n) / 2))
    worst = -math.inf
    for i in range(n):
        a, b = S.FOLD_DEG * i / n, S.FOLD_DEG * (i + 1) / n
        worst = max(worst, _height_behind_face(_section(S.lid_at_pose(dy, a) + S.lid_at_pose(dy, b)), pad))
    return worst


def min_safe_fold_gate(tol=1e-6):
    """The smallest normalised slide at which a full lid sweep (the drawer held there) never enters the upper panel.
    Moving the drawer out only moves the lid away from the panel, so the safe set is an interval [gate, 1]: bisect."""
    lo, hi = 0.0, 1.0
    if _sweep_height(hi) > 0:
        return math.inf
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if _sweep_height(mid) > 0:
            lo = mid
        else:
            hi = mid
    return hi


# ================================================================================================ door leaves vs KVM

def _with_breaks(traj, times):
    """The trajectory with samples inserted at `times` (interpolated, or held before / after its ends)."""
    out = list(traj)
    for t in times:
        if t < out[0][0]:
            out.insert(0, (t, out[0][1], out[0][2]))
        elif t > out[-1][0]:
            out.append((t, out[-1][1], out[-1][2]))
        else:
            i = next(k for k in range(len(out) - 1) if out[k][0] <= t <= out[k + 1][0])
            if t not in (out[i][0], out[i + 1][0]):
                out.insert(i + 1, _lerp_pose(out[i], out[i + 1], t))
    return out


def leaf_clearance_report(traj, spec, slot, opening_s, latency_s, facing=1, t0=0.0):
    """The closing-door race: the leaves run OpenRatio 1 -> 0 over opening_s, starting latency_s before t0 (the
    instant the KVM's sequencer is told to stow; default the trajectory's t = 0, so a trajectory that commands the stow
    later only gets more conservative). Returns {"min": lower bound m, "sampled": at the instants (upper bound),
    "at": (t, leaf, part)} over every leaf of the rack against the drawer and the lid, in slot `slot`, facing ±1."""
    t_start = t0 - latency_s
    tr = _with_breaks(traj, (t_start, t_start + opening_s))
    lvs = doors.leaves(spec)
    swept, sampled = [], []
    for (a, b), slack in zip(zip(tr, tr[1:]), _interp_slack(tr)):
        fa, fb = door_fraction(a[0], t_start, opening_s), door_fraction(b[0], t_start, opening_s)
        leaf_sag = LEAF_RADIUS * (1 - math.cos(math.radians(abs(fb - fa) * DM.DOOR_OPEN_DEG) / 2))
        parts = {k: (to_rack(V, spec, slot, facing), pad) for k, (V, pad) in _swept_parts(a, b, slack).items()}
        now = {k: to_rack(V, spec, slot, facing) for k, V in kvm_parts(b[1], b[2]).items()}
        pbox = {k: _aabb(V) for k, (V, _) in parts.items()}
        nbox = {k: _aabb(V) for k, V in now.items()}
        for lf in lvs:
            La, Lb = leaf_box(spec, lf, fa), leaf_box(spec, lf, fb)
            L = La + Lb
            lbox, lbbox = _aabb(L), _aabb(Lb)
            for name, (V, pad) in parts.items():
                tag = (round(a[0], 6), lf["name"], name)
                swept.append(_candidate(V, L, pad + leaf_sag, tag, (pbox[name], lbox)))
                sampled.append(_candidate(now[name], Lb, 0.0, tag, (nbox[name], lbbox)))
    d, at = min_distance(swept)
    return {"min": d, "sampled": min_distance(sampled)[0], "at": at}


def leaf_clearance(traj, spec, slot, opening_s, latency_s, facing=1, t0=0.0):
    """The minimum distance (m, a lower bound over the swept motion) between the closing leaves and the KVM's drawer
    and lid in rack space; see leaf_clearance_report."""
    return leaf_clearance_report(traj, spec, slot, opening_s, latency_s, facing, t0)["min"]


# ================================================================================================ frame and neighbours

def obstacles(spec, slot, facing=1):
    """What a KVM in `slot` could touch besides the leaves, as rack-frame boxes {name: (lo, hi)}:
    - the side columns (19" rails, slide bolts, cable managers, posts): |x| >= SIDE_LIMIT_X, |y| <= the frame front;
    - the plinth (below the slot band) and the top tray / half-rack roof (above it);
    - the servers in the slots above and below: the slot's width, back to the deepest front hardware any server has
      (NEIGHBOUR_Y), filling their cells' height.
    `facing` picks the side the KVM opens to; the boxes are symmetric front / rear except the servers' fronts."""
    H, ZT, tray = doors.rack_dims(spec)
    yk = 0.625 - 0.027                                              # rack.YK: the frame stops 2.7 cm behind the plane
    zb, zt = 0.25 - H / 2, ZT - H / 2 - (0.0 if tray else DM.HALF_ROOF_T)
    big = 9.0
    zc = slot_centre_z(spec, slot)
    out = {
        "column_left": ((-big, -yk, -big), (-DM.SIDE_LIMIT_X, yk, big)),
        "column_right": ((DM.SIDE_LIMIT_X, -yk, -big), (big, yk, big)),
        "plinth": ((-big, -yk, -big), (big, yk, zb)),
        "top": ((-big, -yk, zt), (big, yk, big)),
    }
    ny = NEIGHBOUR_Y
    front = ((-DM.SIDE_LIMIT_X, -0.375, None), (DM.SIDE_LIMIT_X, ny, None)) if facing > 0 else \
        ((-DM.SIDE_LIMIT_X, -ny, None), (DM.SIDE_LIMIT_X, 0.375, None))
    if slot < nslots(spec):
        out["server_above"] = ((front[0][0], front[0][1], zc + DM.SLOT_H / 2), (front[1][0], front[1][1], zc + 1.5 * DM.SLOT_H))
    if slot > 1:
        out["server_below"] = ((front[0][0], front[0][1], zc - 1.5 * DM.SLOT_H), (front[1][0], front[1][1], zc - DM.SLOT_H / 2))
    return out


def _neighbour_y():
    """The deepest front hardware of any server (build_report clearance.max_y; subparts.NEIGHBOUR_FRONT_Y without)."""
    try:
        import json
        with open(BUILD_REPORT) as fh:
            rep = json.load(fh)["blocks"]
        ys = [b["clearance"]["max_y"] for n, b in rep.items() if n.startswith("DC_Srv_") and "clearance" in b]
        return max(ys) if ys else S.NEIGHBOUR_FRONT_Y
    except (OSError, KeyError, ValueError):
        return S.NEIGHBOUR_FRONT_Y


NEIGHBOUR_Y = _neighbour_y()


def obstacle_clearance(traj, spec, slot, facing=1, swept=True):
    """{obstacle: lower-bound clearance m over the swept trajectory} for every box of `obstacles` (0.0 = touching or
    overlapping)."""
    obs = {k: _corners(*v) for k, v in obstacles(spec, slot, facing).items()}
    obox = {k: _aabb(O) for k, O in obs.items()}
    cands = {k: [] for k in obs}
    for a, b, sl in intervals(traj, swept):
        for name, (V, pad) in _swept_parts(a, b, sl).items():
            V = to_rack(V, spec, slot, facing)
            vbox = _aabb(V)
            for k, O in obs.items():
                cands[k].append(_candidate(V, O, pad, (round(a[0], 6), name), (vbox, obox[k])))
    return {k: max(0.0, min_distance(c)[0]) for k, c in cands.items()}


def rest_clearance(spec, slot, facing=1, slide=1.0, fold=1.0):
    """obstacle clearances of a single resting pose (the data-only open pose by default): the reference the sequence
    is compared with where the rest pose itself already touches (the top slot's lid in the tray)."""
    obs = {k: _corners(*v) for k, v in obstacles(spec, slot, facing).items()}
    parts = [to_rack(v, spec, slot, facing) for v in kvm_parts(slide, fold).values()]
    return {k: min(convex_distance(K, O) for K in parts) for k, O in obs.items()}


def max_height(traj, swept=True):
    """The highest point (KVM-frame z) any part reaches over the swept trajectory (conservative)."""
    top = -math.inf
    for a, b, sl in intervals(traj, swept):
        for _, (K, pad) in _swept_parts(a, b, sl).items():
            top = max(top, max(z for _, _, z in K) + pad)
    return top


def _swept_sections(traj, parts=("drawer", "lid"), swept=True):
    """Per interval and part: (the swept hull's (y, z) section, its pad). x plays no part in the room rules below."""
    for a, b, sl in intervals(traj, swept):
        swept = _swept_parts(a, b, sl)
        for name in parts:
            V, pad = swept[name]
            yield _section(V), pad


def max_y_above(traj, z_cut, swept=True):
    """Over the swept trajectory: the largest KVM-frame y of any drawer or lid point above z_cut (KVM frame), or -inf
    (the containment-rail rule, test_kvm_clear_of_rail). Exact per (y, z) section, padded by the slacks."""
    worst = -math.inf
    for sec, pad in _swept_sections(traj, swept=swept):
        part = _clip(sec, lambda p: (z_cut - pad) - p[1])
        if part:
            worst = max(worst, max(y for y, _ in part) + pad)
    return worst


def max_z_beyond(traj, y_cut, swept=True):
    """Over the swept trajectory: the highest KVM-frame z of any drawer or lid point in front of y_cut (KVM frame), or
    -inf (the roof rule, test_roof_clears_kvm_and_rack_doors: over the aisle, under the roof)."""
    worst = -math.inf
    for sec, pad in _swept_sections(traj, swept=swept):
        part = _clip(sec, lambda p: (y_cut - pad) - p[0])
        if part:
            worst = max(worst, max(z for _, z in part) + pad)
    return worst


# ================================================================================================ per-slot paths

SEQUENCED, DATA_ONLY = "sequenced", "data_only"

# The room's containment values: dims' own when it defines them, else these fallbacks.
PLAN3_RAIL_Y = getattr(DM, "CONTAIN_RAIL_Y", (0.600, 0.624))
PLAN3_ROOF_CLEAR = getattr(DM, "ROOF_CLEAR", 0.004)
AISLE_Y = 0.625                     # the rack's cell plane: beyond it, the aisle (under a containment roof)


def has_containment_above(spec):
    """The room puts the aisle-containment rail and roof on the FULL racks' tray band only (front and back); a half
    rack gets top-rim label pads, no containment. So only a full rack has anything above its top slot's
    front for the lid to hit."""
    return spec.family == "rack" and doors.rack_dims(spec)[2]


def motion_path_for_slot(rack, slot):
    """Which motion the scripted KVM runs in rack slot `slot` (1-based, from the bottom) of `rack` (a
    BlockSpec or its name): "data_only" in a full rack's top slot (the slide-then-fold arc would rise into the
    containment rail there; the simultaneous data-only path stays behind it), "sequenced" everywhere else. Facing
    plays no part: the rail runs along both the front and the back."""
    from . import catalog
    spec = catalog.BY_NAME[rack] if isinstance(rack, str) else rack
    n = nslots(spec)
    if not 1 <= slot <= n:
        raise ValueError(f"{spec.name} has slots 1..{n}, not {slot}")
    return DATA_ONLY if has_containment_above(spec) and slot == n else SEQUENCED


def data_only_trajectory(steps, hz=240):
    """The data-only motion (slide and fold together, linear, POP_TIME per full stroke: the vanilla Translation /
    RotationAnimation pair) through `steps` = [(hold s, from f, to f)], as [(t, f, f)] at `hz`."""
    out, t = [], 0.0
    for hold, f0, f1 in steps:
        n_hold = int(round(hold * hz))
        n_move = int(round(abs(f1 - f0) * S.POP_TIME * hz))
        out += [(t + i / hz, f0, f0) for i in range(n_hold)]
        t += n_hold / hz
        out += [(t + i / hz, f0 + (f1 - f0) * i / n_move, f0 + (f1 - f0) * i / n_move) for i in range(n_move)]
        t += n_move / hz
        last = f1
    out.append((t, last, last))
    return out


def path_runs(path, sweep=None):
    """[(name, trajectory, door t0 or None)] of everything the KVM can do on `path`; door t0 = when its sequencer is
    told the door is closing (the leaf race starts LATENCY before it), None for runs without a door race.
    sequenced: the six tuned trajectories plus the reversal sweep; the door runs are door_close_while_out (t0 = 0,
    the strictest reading) and every FastStow sweep run (t0 = its reversal).
    data_only: open, close, the door race (out for 0.1 s, then home: on this path the script still stows on a closing
    door, along the same simultaneous path at the vanilla speed) and reversals every 0.1 of a stroke."""
    if path == SEQUENCED:
        runs = [(n, load(n), 0.0 if n == "door_close_while_out" else None) for n in TRAJECTORIES]
        sweep = load_sweep() if sweep is None else sweep
        runs += [(rid, tr, at if target == "FastStow" else None) for rid, (tr, at, target) in sweep.items()]
        return runs
    if path != DATA_ONLY:
        raise ValueError(path)
    runs = [("data_only_open", data_only_trajectory([(0.0, 0.0, 1.0)]), None),
            ("data_only_close", data_only_trajectory([(0.0, 1.0, 0.0)]), None),
            ("data_only_door_close_while_out", data_only_trajectory([(0.1, 1.0, 0.0)]), 0.0)]
    for k in range(1, 10):
        f = k / 10
        tr = data_only_trajectory([(0.0, 0.0, f), (0.0, f, 0.0)])
        runs.append((f"data_only_open_door@{f:.1f}", tr, f * S.POP_TIME))
        runs.append((f"data_only_close_out@{f:.1f}", data_only_trajectory([(0.0, 1.0, 1 - f), (0.0, 1 - f, 1.0)]), None))
    return runs


# ================================================================================================ the C# tuning

_PARAM = re.compile(r"\b(?:float|int|double)\s+(\w+)\s*=\s*([^,)]+)")


def _number(expr):
    """A C# numeric literal or a quotient of two (`1f / 120f`)."""
    parts = [p.strip().rstrip("fFdDmM") for p in expr.split("/")]
    v = float(parts[0])
    for p in parts[1:]:
        v /= float(p)
    return v


def read_tuning(path=TUNING_CS):
    """The shipped KvmMotionTuning: the constructor's parameter defaults, overridden by any named arguments in the
    `Default = new KvmMotionTuning(...)` initialiser. {PascalCase field: value}."""
    with open(path) as fh:
        src = fh.read()
    ctor = re.search(r"public\s+KvmMotionTuning\s*\((.*?)\)\s*\{", src, re.S)
    vals = {m.group(1): _number(m.group(2)) for m in _PARAM.finditer(ctor.group(1))}
    init = re.search(r"Default\s*=\s*new\s+KvmMotionTuning\s*\((.*?)\)\s*;", src, re.S)
    if init and init.group(1).strip():
        for m in re.finditer(r"(\w+)\s*:\s*([^,]+)", init.group(1)):
            vals[m.group(1)] = _number(m.group(2))
    return {k[0].upper() + k[1:]: v for k, v in vals.items()}


# ================================================================================================ the reversal sweep

SWEEP = "reversal_sweep"


def load_sweep(name=SWEEP):
    """{run id: (trajectory [(t, slide, fold)], reversal time, the target it reverses to)} of the reversal sweep
    (Tests/CoreTests kvm.reversal_sweep: run ids `<family>@<t>`, e.g. `open_fast@0.6`)."""
    runs = {}
    for r in _rows(name):
        runs.setdefault(r["run"], []).append(r)
    out = {}
    for rid, rows in runs.items():
        traj = [(float(r["t"]), float(r["slide"]), float(r["fold"])) for r in rows]
        out[rid] = (traj, float(rid.split("@")[1]), rows[-1]["target"])
    return out
