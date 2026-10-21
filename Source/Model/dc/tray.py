"""Cable-tray blocks: the Blender build of every tray shape from its cable plan, and its collision.

    build(spec, lod) -> [Part]      the LOD's Parts in the centred block frame (dc/tray_kit.py dresses the plan)
    collision(spec) -> dict         {"regular": [(name, lo, hi)], "occupancy": [...], "mount": [...]} (rack format)

The geometry comes from dc/tray_plan.py (box-corner frame; the plan proves the cable continuity contract offline) and
is moved to the centred frame at the end. Collision (plan §Review Focus 4, mount only where hardware exists):

- regular: one physics box per straight-type piece, the trough (s +-0.25, from 1 mm over the bottom plane to the
  wall top); nothing on the open top;
- occupancy: every cell the plan occupies (dc/tray_plan.occupied_cells), merged into boxes;
- mount hints: both port faces (s +-0.24, the bottom plane to the wall top); Up at each rod plate; Down under the
  strut; the two across faces at the strut's end plates. A mount is a whole cell face in the game (8 rays per cell,
  se2model.placement), so each hardware hint is sized to catch ONE cell's rays: the rod plates and end plates sit on
  the grid line at the piece's centre, so the -y one mounts the cell on its -x side and the +y one the cell on its
  +x side (the pattern is the same after a 180 deg turn, as the piece is).
"""
import numpy as np

from . import catalog
from . import tray_lanes as TL
from . import tray_plan as TP

try:   # geometry needs Blender; collision is plain Python (pytest imports it outside)
    from se2model import geom as G
    from se2model.geom import Part
    from . import tray_kit as K
except ImportError:
    G = Part = K = None

CELL = TL.CELL
HINT_T = 0.005           # mount hint slab thickness
LAST_LOD_MAX = 19        # the last LOD stays <= 0.6 x Keen's 32 triangles

# name -> LOD count fitted to the MEASURED LOD0 (assemble.fit_lods)
LOD_COUNT = {}


def size(spec):
    return tuple(CELL * c for c in spec.cells)


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


def plan_of(spec):
    return TP.plan(spec)


# ---------------------------------------------------------------------------------------------------- build
def build(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the U channel + bed quad."""
    pl = plan_of(spec)
    shift = tuple(-v for v in pl.size / 2)
    if lod == n_lods(spec) - 1:
        return last_lod(spec, pl, shift)
    if lod == 0:
        parts = dress(pl, 0)
        _LOD0[spec.name] = (_tris(parts), _extent(parts))
        return [p for p in parts if _move(p, shift)]
    # LOD1 .. n-2: the kit's detail level for this LOD, one step simpler while it would exceed 60 % of Keen's limit
    # for this LOD (the limits follow the measured LOD0: a light LOD0 gets fewer LODs with tighter caps)
    from se2model import limits
    tris0, ext = _LOD0.get(spec.name) or (_tris(dress(pl, 0)), size(spec))
    lims = limits.model_limits(ext, tris0)["lods"]
    cap = lims[min(lod, len(lims) - 1)]["max_tris"]      # (a first pass from the cell box may count more LODs)
    detail = lod
    parts = dress(pl, detail)
    while detail < 2 and _tris(parts) > BUDGET * cap:
        detail += 1
        parts = dress(pl, detail)
    DETAIL[(spec.name, lod)] = detail
    return [p for p in parts if _move(p, shift)]


def mid_parts(spec):
    """The kit's mid detail (1) in the centred block frame: an extra LOD the Fractured / Damaged models of a light
    piece take when their cut LOD0 needs one more LOD than the NonFractured (dc/fracture.py)."""
    pl = plan_of(spec)
    shift = tuple(-v for v in pl.size / 2)
    return [p for p in dress(pl, 1) if _move(p, shift)]


BUDGET = 0.6             # every LOD stays under 60 % of Keen's limit (plan §Global Constraints)
_LOD0 = {}               # name -> (LOD0 tris, LOD0 extent): the limits of the later LODs follow it
DETAIL = {}              # (name, lod) -> the kit detail level used (report)


def dress(pl, detail):
    """The kit's Parts of a plan at a detail level (0 full, 1 mid, 2 card), in the box-corner frame."""
    P = K.Parts(detail, card=any(p.kind == "basket" for p in pl.structure))
    K.basket(P, pl, detail)
    K.bundles(P, pl, detail)
    K.straps(P, pl, detail)
    for sp in pl.supports:
        K.support(P, sp, detail)
    K.fittings(P, pl, detail)
    return P.done((0.0, 0.0, 0.0))


def _tris(parts):
    return sum(len(f.verts) - 2 for p in parts for f in p.bm.faces)


def _extent(parts):
    vs = np.array([tuple(v.co) for p in parts for v in p.bm.verts])
    return tuple(float(v) for v in (vs.max(axis=0) - vs.min(axis=0)))


def _move(p, shift):
    from mathutils import Matrix, Vector
    p.bm.transform(Matrix.Translation(Vector(shift)))
    p.bm.normal_update()
    return True


def last_lod(spec, pl, shift):
    """An open U channel along each basket path (floor and walls, both faces) and, when the piece carries cables,
    one quad at the bundle-bed top: <= 19 triangles in the interim LastLOD material (material_guids.LASTLOD_FALLBACK,
    the paint: by design the silver basket pops to the cable paint at this last switch; a baked
    <name>_LastLOD material is the follow-up)."""
    from mathutils import Matrix, Vector
    p = Part("lastlod")
    p.decal = True
    m = f"{spec.name}_LastLOD"
    bm = p.bm
    mi = p.mi(m)
    bed = max((l.h + TL.R_B for l in TL.lanes(pl.density)), default=None) if pl.density else None
    if pl.shape in ("Chute", "Rods"):
        _last_lod_columns(p, mi, pl)
        p.bm.transform(Matrix.Translation(Vector(shift)))
        p.bm.normal_update()
        return [p]
    if _junction(pl):
        _last_lod_junction(p, mi, pl, bed)
        p.bm.transform(Matrix.Translation(Vector(shift)))
        p.bm.normal_update()
        return [p]
    for path in pl.structure:
        if path.kind != "basket":
            continue
        if path.arc:
            _last_lod_bend(p, mi, path, bed)
            continue
        pts = np.asarray(path.points, float)
        nrm = np.asarray(path.normals, float)
        keep = K.XS.simplify(pts, K.TOL[3])
        idx = [int(np.argmin(np.linalg.norm(pts - q, axis=1))) for q in keep]
        t = np.gradient(pts, axis=0)
        t /= np.linalg.norm(t, axis=1)[:, None]
        s = np.cross(nrm, t)
        us, hf = TL.U_LEG_S, -0.016

        def P_(i, a, b):
            return Vector(pts[i] + a * s[i] + b * nrm[i])

        def quad(c):
            bm.faces.new([bm.verts.new(v) for v in c]).material_index = mi
        e = 0.001                     # the two faces of each sheet 2 mm apart (coincident ones would be merged)
        for i, j in zip(idx, idx[1:]):
            quad([P_(i, -us, hf + e), P_(i, us, hf + e), P_(j, us, hf + e), P_(j, -us, hf + e)][::-1])   # floor top
            quad([P_(i, -us, hf - e), P_(i, us, hf - e), P_(j, us, hf - e), P_(j, -us, hf - e)])         # underside
            for sg in (-1, 1):
                for k, so in ((1, sg * (us + e)), (-1, sg * (us - e))):     # outside, inside
                    w = [P_(i, so, hf), P_(j, so, hf), P_(j, so, path.wall_h), P_(i, so, path.wall_h)]
                    quad(w if sg * k > 0 else w[::-1])
            if bed:
                b = bed * 0.75
                quad([P_(i, -0.19, b), P_(i, 0.19, b), P_(j, 0.19, b), P_(j, -0.19, b)][::-1])
    p.bm.transform(Matrix.Translation(Vector(shift)))
    p.bm.normal_update()
    return [p]


def _last_lod_bend(p, mi, path, bed):
    """A bend's last LOD: two chords (port, mid radial, port), each the floor's underside, the two walls' outsides
    and one top quad (the bundle bed, or the floor top when empty): 16 triangles. Trays hang overhead, so at this
    range they are seen from below and the side; the inside faces are left out to stay under 19."""
    from mathutils import Vector
    bm = p.bm
    fr = K._path_frames(path)
    L = fr[3]
    us, hf = TL.U_LEG_S, -0.016
    smp = [K._interp(path, fr, l) for l in (0.0, L[-1] / 2, L[-1])]

    def P_(k, a, b):
        q, _, s, u = smp[k]
        return Vector(q + a * s + b * u)

    def quad(c):
        bm.faces.new([bm.verts.new(v) for v in c]).material_index = mi
    top = bed * 0.75 if bed else 0.0
    w = 0.19 if bed else us
    for i, j in ((0, 1), (1, 2)):
        quad([P_(i, -us, hf), P_(i, us, hf), P_(j, us, hf), P_(j, -us, hf)])                    # underside (down)
        quad([P_(i, -w, top), P_(i, w, top), P_(j, w, top), P_(j, -w, top)][::-1])               # bed / floor top
        for sg in (-1, 1):                                                                       # wall outsides
            q = [P_(i, sg * us, hf), P_(j, sg * us, hf), P_(j, sg * us, path.wall_h), P_(i, sg * us, path.wall_h)]
            quad(q[::-1] if sg > 0 else q)                                                         # (outward)


def _last_lod_columns(p, mi, pl):
    """The Chute's and the rod hangers' last LOD: per ladder (bundle and rails) or per rod, an open
    four-sided column round its solids (8 triangles each, 16 in all; seen from every side at range)."""
    from mathutils import Vector
    cols = []
    for sp in pl.supports:
        if sp.kind == "ladder":
            pts = np.vstack([np.asarray(fr.corners(size)) for _, fr, size, _ in sp.solids()])
            cols.append((pts.min(axis=0), pts.max(axis=0)))
        elif sp.kind == "rods":
            for lo, hi in sp.rods:
                r = TP.COUPLER_R * 0.8
                lo, hi = np.asarray(lo, float), np.asarray(hi, float)
                cols.append((np.minimum(lo, hi) - [r, r, 0.0], np.maximum(lo, hi) + [r, r, 0.0]))
    bm = p.bm
    for lo, hi in cols:
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        for a, b, out in (((x0, y0), (x1, y0), (0, -1)), ((x1, y0), (x1, y1), (1, 0)), ((x1, y1), (x0, y1), (0, 1)),
                          ((x0, y1), (x0, y0), (-1, 0))):
            f = bm.faces.new([bm.verts.new(Vector(v)) for v in ((*a, z0), (*b, z0), (*b, z1), (*a, z1))])
            f.material_index = mi
            f.normal_update()
            if f.normal.dot(Vector((out[0], out[1], 0.0))) < 0:
                f.normal_flip()


def _junction(pl):
    return any(path.kind == "wall" for path in pl.structure)


def _free_intervals(path, others, half=TL.U_LEG_S):
    """[(l0, l1)] stretches of a basket path NOT inside another path's card band (a junction's branch starts inside
    the run's; the Cross's c-d path crosses the a-b one)."""
    pts = np.asarray(path.points, float)
    L = path.lengths()
    fine = np.linspace(0.0, L[-1], 401)
    q = np.column_stack([np.interp(fine, L, pts[:, k]) for k in range(3)])
    inside = np.zeros(len(fine), bool)
    for o in others:
        a, b = np.asarray(o.points[0], float), np.asarray(o.points[-1], float)
        d = (b - a) / np.linalg.norm(b - a)
        r = q - a
        f = r @ d
        lat = np.linalg.norm(r - np.outer(f, d), axis=1)
        inside |= (lat < half - 1e-9) & (f > -1e-9) & (f < np.linalg.norm(b - a) + 1e-9)
    out, start = [], None
    for i, m in enumerate(list(~inside) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((float(fine[start]), float(fine[i - 1])))
            start = None
    return out


def _last_lod_junction(p, mi, pl, bed):
    """A junction's last LOD: per basket path, its underside and top (the bundle bed, or the floor top when empty)
    over the stretches outside the other path's (no overlapping quads), and the walls' outsides where they stand when
    the whole set fits in LAST_LOD_MAX triangles (the Tee: 18; the Cross keeps its plus-shaped floor only: 12)."""
    from mathutils import Vector
    bm = p.bm
    paths = [q for q in pl.structure if q.kind == "basket"]
    us, hf = TL.U_LEG_S, -0.016
    top = bed * 0.75 if bed else 0.0
    floors, walls = [], []
    for path in paths:
        fr = K._path_frames(path)
        others = [q for q in paths if q is not path]

        def P_(l, a, b):
            q, _, s, u = K._interp(path, fr, l)
            return Vector(q + a * s + b * u)
        for l0, l1 in _free_intervals(path, others):
            floors.append([P_(l0, -us, hf), P_(l0, us, hf), P_(l1, us, hf), P_(l1, -us, hf)])            # underside
            floors.append([P_(l0, -us, top), P_(l0, us, top), P_(l1, us, top), P_(l1, -us, top)][::-1])    # top
            for k, sg in ((0, -1), (1, 1)):
                cuts = sorted({l0, l1} | {v for w, rng, _ in path.openings if w == k for v in rng if l0 < v < l1})
                for a, b in zip(cuts, cuts[1:]):
                    if K._wall_on(path, k, (a + b) / 2):
                        q = [P_(a, sg * us, hf), P_(b, sg * us, hf), P_(b, sg * us, path.wall_h),
                             P_(a, sg * us, path.wall_h)]
                        walls.append(q[::-1] if sg > 0 else q)
    quads = floors + (walls if 2 * (len(floors) + len(walls)) <= LAST_LOD_MAX else [])
    for c in quads:
        bm.faces.new([bm.verts.new(v) for v in c]).material_index = mi


# ---------------------------------------------------------------------------------------------------- collision
def _aabb(points):
    a = np.asarray(points, float)
    return a.min(axis=0), a.max(axis=0)


def _clip(lo, hi, size, inset=0.0):
    lo = np.maximum(lo, inset)
    hi = np.minimum(hi, np.asarray(size, float) - inset)
    return lo, hi


def _cell_boxes(cells, size, inset=0.001):
    """Merge occupied cells into boxes (greedy, se2model.placement.build_groups), box-corner metres."""
    from se2model.placement import build_groups
    out = []
    for lo, hi in build_groups(sorted(cells)):
        a = np.array(lo, float) * CELL + inset
        b = (np.array(hi, float) + 1) * CELL - inset
        out.append((a, b))
    return out


def _trough(pl):
    """The regular physics boxes: the trough of each basket path (s +-0.25 = the full two cells across, from 1 mm
    over the cell plane under the floor to the wall top), one box for a straight path; a bend's two halves (an L
    round the arc trough: each half's box up to its 45 deg radial)."""
    boxes = []
    for path in pl.structure:
        if path.kind != "basket":
            continue
        pts = np.asarray(path.points, float)
        nrm = np.asarray(path.normals, float)
        t = np.gradient(pts, axis=0)
        t /= np.linalg.norm(t, axis=1)[:, None]
        s = np.cross(nrm, t)
        chunks = np.array_split(np.arange(len(pts)), 1 if len(pts) < 3 or _straight(pts) else 2)
        for ch in chunks:
            if len(ch) == 0:
                continue
            q = []
            for i in ch:
                for a in (-CELL, CELL):
                    for b in (-TL.FLOOR_Z + TP.STRUT_LIFT, path.wall_h):
                        q.append(pts[i] + a * s[i] + b * nrm[i])
            lo, hi = _aabb(q)
            boxes.append(_clip(lo, hi, pl.size))
    return boxes[:3]


def _straight(pts):
    d = pts[-1] - pts[0]
    d /= np.linalg.norm(d)
    off = (pts - pts[0]) - np.outer((pts - pts[0]) @ d, d)
    return float(np.abs(off).max()) < 1e-6


def _junction_boxes(pl):
    """A junction's physics boxes, each path's trough at the plain 0.10 m wall height (the step-down at its
    ports: a neighbour's trough meets it flush) plus one raised box: the Tee's run between its two
    step-downs at the junction walls' 0.15 m, the Cross's crossing up to the walls' 0.15 m or the c-d stack's top over
    the saddle, whichever is higher. Each
    trough s +-0.25 (its two cells), from 1 mm over the cell plane; a branch's from the run's trough on (the Tee's
    "branch stub"). Never in a free corner cell."""
    paths = [q for q in pl.structure if q.kind == "basket"]
    z0, z_low = TP.STRUT_LIFT, TL.FLOOR_Z + TL.WALL_H
    boxes = []
    for path in paths:
        a, b = np.asarray(path.points[0], float), np.asarray(path.points[-1], float)
        d = (b - a) / np.linalg.norm(b - a)
        s = np.cross(TP.Z, d)
        lo = np.minimum(a, b) - CELL * np.abs(s)
        hi = np.maximum(a, b) + CELL * np.abs(s)
        lo[2], hi[2] = z0, z_low
        boxes.append([lo, hi])
    main, branch = boxes[0], boxes[1]
    if pl.shape == "Tee":                 # the branch stub starts where the run's trough ends
        branch[0][1] = main[1][1]
        x0, x1 = XS_STEP_FULL, pl.size[0] - XS_STEP_FULL
        boxes.append([np.array([x0, main[0][1], z0]), np.array([x1, main[1][1], TL.FLOOR_Z + TL.JUNCTION_WALL_H])])
    else:                                 # the Cross: the c-d stack over the saddle
        top = max([TL.FLOOR_Z + TL.JUNCTION_WALL_H] + [float(np.max(b.points[:, 2])) + b.radius for b in pl.bundles])
        sd = [f for f in pl.fittings if f.kind == "crossover_saddle"]
        if sd:
            top = max(top, float(sd[0].frame.o[2]) + sd[0].params["deck_top"] + sd[0].params["lip_h"])
        boxes.append([np.array([branch[0][0], XS_STEP_FULL, z0]),
                      np.array([branch[1][0], pl.size[1] - XS_STEP_FULL, max(top, z_low)])])
    return [_clip(np.asarray(lo, float), np.asarray(hi, float), pl.size) for lo, hi in boxes]


XS_STEP_FULL = 0.06              # the raised box ends where the walls start stepping down (tray_xsec.STEP_AT)


def _junction_strut_hints(sp, size, k):
    """A junction's floor strut (across y on the grid line x = 0.5, under the junction): Down only, the cells on both
    sides of its line along its length (a hint reaching one cell's 4 nearest rays each side, _hint_reach)."""
    if sp.kind != "floor_strut":
        return []
    reach, _ = _hint_reach()
    x = float(sp.position[0])
    y0, y1 = (float(sp.position[1]) + e for e in sp.extent)
    return [(f"strut_bottom_{k}", np.array([x - reach, max(y0, 0.001), 0.0]),
             np.array([x + reach, min(y1, size[1] - 0.001), HINT_T]))]


def collision(spec):
    pl = plan_of(spec)
    size = pl.size
    sh = size / 2
    if pl.shape in ("Chute", "Rods"):
        return _column_collision(pl)
    boxes = _junction_boxes(pl) if _junction(pl) else _trough(pl)
    reg = [("trough" if k == 0 else f"trough_{k}", lo, hi) for k, (lo, hi) in enumerate(boxes)]
    occ = [(f"cells_{k}", lo, hi) for k, (lo, hi) in enumerate(_cell_boxes(TP.occupied_cells(pl), size))]
    mnt = []
    for name, port in sorted(pl.ports.items()):
        o, t, s, u = port.frame()
        q = [o + a * s + b * u + c * t for a in (-0.24, 0.24) for b in (-TL.FLOOR_Z, TL.WALL_H)
             for c in (-HINT_T, 0.0)]
        lo, hi = _aabb(q)
        mnt.append((f"port_{name}", *_clip(lo, hi, size)))
    bend = any(path.arc for path in pl.structure)
    for k, sp in enumerate(pl.supports):
        if _junction(pl):
            mnt += _junction_strut_hints(sp, size, k)
        else:
            mnt += _bend_strut_hints(sp, size, k) if bend else _support_hints(sp, size, k)
    mnt += _landing_hints(pl)
    return _centred(sh, reg, occ, mnt)


def _centred(sh, reg, occ, mnt):
    f = lambda boxes: [(n, tuple(float(v) for v in lo - sh), tuple(float(v) for v in hi - sh))  # noqa: E731
                       for n, lo, hi in boxes]
    return {"regular": f(reg), "occupancy": f(occ), "mount": f(mnt)}


def _cell_face_hint(name, xy, z0, z1):
    """A hint filling the face of the cell column at xy (box-corner metres) between z0 and z1: it catches all of that
    cell's rays (se2model.placement), so the cell mounts."""
    ix, iy = (int(np.floor(v / CELL)) for v in xy)
    return (name, np.array([ix * CELL + 0.001, iy * CELL + 0.001, z0]),
            np.array([(ix + 1) * CELL - 0.001, (iy + 1) * CELL - 0.001, z1]))


def _landing_hints(pl):
    """The Drop's landing collars: each seats on a rack's brush plate (or a Chute's top plate), so the
    waterfall column's bottom cell under it mounts (Down)."""
    return [_cell_face_hint(f"landing_{k}", f.frame.o[:2], 0.0, HINT_T)
            for k, f in enumerate(f for f in pl.fittings if f.kind == "brush_collar")]


def _column_collision(pl):
    """The Chute and the rod hangers. Physics: one thin box per ladder (its rails, rungs, plates and the
    bundle) or per rod (round the rod and its coupler): players walk round them, nothing else is solid. Occupancy:
    the cells they pass through. Mounts: the Chute's foot plates (Down, on the half rack's roof) and top plates (Up,
    under the Drop's landing collars); a rod hanger's coupler footprints (Down, on a tray's rod plates: the same
    rectangles as the tray's Up hints) and its ceiling anchor plates (Up)."""
    size = pl.size
    H = float(size[2])
    reg, mnt = [], []
    for k, sp in enumerate(pl.supports):
        if sp.kind == "ladder":
            pts = np.vstack([np.asarray(fr.corners(sz)) for _, fr, sz, _ in sp.solids()])
            b = pl.bundles[k]
            pts = np.vstack([pts, b.points + [0.0, TL.R_WF, 0.0], b.points - [0.0, TL.R_WF, 0.0]])
            lo, hi = _clip(pts.min(axis=0), pts.max(axis=0), size, 0.001)
            reg.append((f"ladder_{k}", lo, hi))
            mnt.append(_cell_face_hint(f"foot_{k}", b.points[0][:2], 0.0, HINT_T))
            mnt.append(_cell_face_hint(f"top_{k}", b.points[0][:2], H - HINT_T, H))
        elif sp.kind == "rods":
            reach, keep = _hint_reach()
            yc = float(sp.position[1])
            for j, (a, b) in enumerate(sp.rods):
                a, b = np.asarray(a, float), np.asarray(b, float)
                r = TP.COUPLER_R
                lo, hi = _clip(np.minimum(a, b) - [r, r, 0.0], np.maximum(a, b) + [r, r, 0.0], size, 0.001)
                reg.append((f"rod_{j}", lo, hi))
                x = float(a[0])
                if a[1] < yc:      # the tray's rod-plate hint pattern (_support_hints): one cell each, diagonal
                    xs, ys = (x - reach, x + keep), (0.001, yc - 0.04)
                else:
                    xs, ys = (x - keep, x + reach), (yc + 0.04, float(size[1]) - 0.001)
                mnt.append((f"coupler_{j}", np.array([xs[0], ys[0], 0.0]), np.array([xs[1], ys[1], HINT_T])))
                mnt.append((f"anchor_{j}", np.array([xs[0], ys[0], H - HINT_T]), np.array([xs[1], ys[1], H])))
    occ = [(f"cells_{k}", lo, hi) for k, (lo, hi) in enumerate(_cell_boxes(TP.occupied_cells(pl), size))]
    return _centred(size / 2, reg, occ, mnt)


def _support_hints(sp, size, k):
    """Mount hints of a trapeze / floor strut: Down under the strut, the two strut end plates (one cell each), and
    (trapeze) Up at each rod plate (one cell each). Only axis-aligned struts across y at an x grid line."""
    out = []
    if sp.kind not in ("trapeze", "floor_strut"):
        return out
    a = np.asarray(sp.axis, float)
    if abs(abs(a[1]) - 1.0) > 1e-6:
        return out                              # a turned strut (bends): its piece task adds its hints
    x = float(sp.position[0])
    zb = float(sp.position[2]) - TP.STRUT_H / 2 - TP.STRUT_LIFT       # the cell plane under the strut
    reach, keep = _hint_reach()
    lo_x, hi_x = (x - reach, x + keep), (x - keep, x + reach)
    y0, y1 = (float(sp.position[1]) + e for e in sp.extent)
    # only hardware ON a block face mounts (the Drop's strut sits on an inner plane, over its waterfall
    # column's open bottom, and its +y end plate is inside the block)
    if abs(zb) < 1e-6:
        out.append((f"strut_bottom_{k}", np.array([x - reach, 0.001, zb]), np.array([x + reach, size[1] - 0.001,
                                                                                     zb + HINT_T])))
    zt = min(zb + 0.21, size[2])
    if y0 <= 0.002:
        out.append((f"strut_end_m_{k}", np.array([lo_x[0], 0.0, zb + 0.001]), np.array([lo_x[1], HINT_T, zt])))
    if y1 >= size[1] - 0.002:
        out.append((f"strut_end_p_{k}", np.array([hi_x[0], size[1] - HINT_T, zb + 0.001]),
                    np.array([hi_x[1], size[1], zt])))
    for j, (lo, hi) in enumerate(sp.rods):
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        yc = float(sp.position[1])
        top = float(hi[2]) + TP.END_INSET
        if hi[1] < yc:
            box = (np.array([lo_x[0], 0.001, top - HINT_T]), np.array([lo_x[1], yc - 0.04, top]))
        else:
            box = (np.array([hi_x[0], yc + 0.04, top - HINT_T]), np.array([hi_x[1], size[1] - 0.001, top]))
        out.append((f"rod_plate_{k}_{j}", *box))
    return out


STRUT_CELL_MIN = 0.10    # a bend's floor strut mounts (Down) the bottom cells it runs >= 10 cm through


def _bend_strut_hints(sp, size, k):
    """A bend's floor strut: Down only, and only when the strut stands on the block's bottom plane (TurnH, TurnUp;
    the TurnDown's strut is behind its vertical lead, on an inner grid plane, where nothing can be bolted). One
    hint per bottom cell the strut runs at least STRUT_CELL_MIN through, filling that cell's face (a hardware hint
    must catch 4 of the cell's 8 rays, se2model.placement): TurnH the centre cell under its 45 deg strut, TurnUp the
    two cells under its lead's strut. No end-plate hints: a fitting is carried by its neighbours (Decision 8), so
    its across faces never mount."""
    if sp.kind != "floor_strut":
        return []
    up = np.asarray(sp.params.get("up", TP.Z), float)
    zb = float(sp.position[2]) - TP.STRUT_H / 2 - TP.STRUT_LIFT
    if abs(up[2] - 1.0) > 1e-6 or abs(zb) > 1e-6:
        return []
    a = np.asarray(sp.axis, float)
    ls = np.linspace(sp.extent[0], sp.extent[1], 401)
    pts = np.asarray(sp.position, float) + ls[:, None] * a
    step = (sp.extent[1] - sp.extent[0]) / (len(ls) - 1)
    run = {}
    for q in pts:
        c = (int(np.floor(q[0] / CELL)), int(np.floor(q[1] / CELL)))
        run[c] = run.get(c, 0.0) + step
    out = []
    for j, (ix, iy) in enumerate(sorted(c for c, l in run.items() if l >= STRUT_CELL_MIN)):
        out.append((f"strut_bottom_{k}_{j}", np.array([ix * CELL + 0.001, iy * CELL + 0.001, 0.0]),
                    np.array([(ix + 1) * CELL - 0.001, (iy + 1) * CELL - 0.001, HINT_T])))
    return out


def _hint_reach():
    """From se2model.placement's ray pattern: a hint reaching `reach` to one side of a grid line catches the 4 rays
    of the cell on that side that lie nearest the line (they sit CELL/2 - min|offset| from it), and one reaching
    `keep` past the line stays clear of the far cell's rays (CELL/2 - max|offset| away)."""
    from se2model import placement as PL
    offs = sorted({round(abs(a), 6) for a, _ in PL.SAMPLES})
    return PL.CELL / 2 - offs[0] + 0.005, PL.CELL / 2 - offs[-1] - 0.025


# ---------------------------------------------------------------------------------------------------- report
def ports_block(spec):
    """The plan's ports in the centred model frame: {name: {"o", "t", "u", "density"}}."""
    pl = plan_of(spec)
    return {n: {"o": [round(float(v), 6) for v in pl.to_block(p.o)], "t": [float(v) for v in p.t],
                "u": [float(v) for v in p.u], "density": p.density} for n, p in pl.ports.items()}


def run_length(spec):
    """The centreline length a piece adds to a run (the basket paths' length; 0 for rods and the Chute). A junction
    has its arms, each port to the junction's centre (the Tee 3 x 0.5 = 1.5 m, the Cross 4 x 0.5 = 2.0 m; its
    branch path itself starts at the run's wall line)."""
    pl = plan_of(spec)
    if _junction(pl):
        paths = [p for p in pl.structure if p.kind == "basket"]
        a, b = (np.asarray(paths[0].points[k], float) for k in (0, -1))
        c = (a + b) / 2
        return float(sum(np.linalg.norm((np.asarray(p.o) - c)[:2]) for p in pl.ports.values()))
    return float(sum(p.lengths()[-1] for p in pl.structure if p.kind == "basket"))

