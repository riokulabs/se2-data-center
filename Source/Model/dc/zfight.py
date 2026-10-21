"""Z-fight check (in-game report: rack side labels flickering, door edges "fighting").

Two faults make two surfaces fight for the same pixels:
  (a) two DECAL ELEMENTS (a stencil line, an atlas sticker, a stripe band) overlap in-plane at (nearly) the same depth;
  (b) a decal quad, or a mesh face, lies in the plane of another same-facing face it overlaps (coplanar geometry).

The build tags every decal quad with the element it belongs to (install(): a face int layer written by
se2model.decals._quad, the element = one outermost call of a decal API: decals.element / text / trim / stripes,
style.stencil / hazard_triangle, tray_kit._stencil), measures the built models (check_built), strips the tag again
before export, and records the result in build_report.json ("zfight"). Tests/test_zfight.py re-checks the recorded
element boxes with the bpy-free rules below.

Rules (metres):
  DECAL_EPS_D  decal elements whose depths differ by less than this must not overlap in-plane (a sticker layered on
               a plate sits >= 0.5 mm proud of it: the depth buffer separates them at any view distance);
  DECAL_GAP    in-plane clearance between two such elements (tidy composition, no crowding labels); elements
               meeting exactly edge to edge (ABUT: a continuous stripe border built from bands) are allowed;
  GEOM_EPS_D   a decal / face this close to the plane of a same-facing face it overlaps is coplanar;
  BURY_D       a same-facing mesh face up to this far IN FRONT of a decal that it overlaps hides (buries) it.
"""
import math
import os
import sys

DECAL_EPS_D = 0.0005
DECAL_GAP = 0.001
GEOM_EPS_D = 0.0003
BURY_D = 0.015
ABUT = 1e-5            # boxes meeting exactly edge to edge (shared edge, no overlap)
MIN_AREA = 2e-7          # 0.2 mm^2: smaller overlaps are edge contacts / float noise
TAG = "dc_decal_el"

# ------------------------------------------------------------------------------------------------ bpy-free core


def nkey(n):
    """Normal key: the unit normal rounded (same key = same facing)."""
    return tuple(round(c, 3) + 0.0 for c in n)


def basis(n):
    """(u, v) in-plane axes for a unit normal, deterministic per normal key."""
    ax = min(range(3), key=lambda i: abs(n[i]))
    h = [0.0, 0.0, 0.0]
    h[ax] = 1.0
    u = _norm(_cross(h, n))
    return u, _cross(n, u)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    m = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / m, a[1] / m, a[2] / m)


def project(pts, n):
    u, v = basis(n)
    return [(_dot(p, u), _dot(p, v)) for p in pts]


def box_of(pts2):
    return (min(p[0] for p in pts2), min(p[1] for p in pts2), max(p[0] for p in pts2), max(p[1] for p in pts2))


def box_gap(a, b):
    """Signed in-plane separation of two boxes: < 0 overlap depth, >= 0 clear distance (Chebyshev)."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def decal_conflicts(elements, eps_d=DECAL_EPS_D, gap=DECAL_GAP):
    """Pairs of decal elements of one model that fight or crowd: same facing, depth within eps_d, in-plane boxes
    closer than `gap`. elements: [{"label", "model", "n", "d", "box"}]; returns [(label_a, label_b, dd, box_gap)]."""
    out = []
    groups = {}
    for e in elements:
        groups.setdefault((e["model"], tuple(e["n"])), []).append(e)
    for es in groups.values():
        es = sorted(es, key=lambda e: e["d"])
        for i, a in enumerate(es):
            for b in es[i + 1:]:
                if b["d"] - a["d"] >= eps_d:
                    break
                g = box_gap(a["box"], b["box"])
                if g < gap and not abs(g) <= ABUT:     # edge-to-edge joints (a continuous stripe border) are fine
                    out.append((a["label"], b["label"], round(b["d"] - a["d"], 6), round(g, 5)))
    return out


def clip(subject, clipper):
    """Sutherland-Hodgman: subject polygon clipped by a CONVEX clipper (both 2D, any winding)."""
    def area2(poly):
        return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))
    if area2(clipper) < 0:
        clipper = clipper[::-1]
    out = list(subject)
    for i in range(len(clipper)):
        if not out:
            break
        a, b = clipper[i - 1], clipper[i]
        inp, out = out, []

        def inside(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12

        def cut(p, q):
            x1, y1, x2, y2 = p[0], p[1], q[0], q[1]
            dx, dy = x2 - x1, y2 - y1
            den = (b[0] - a[0]) * dy - (b[1] - a[1]) * dx
            if abs(den) < 1e-18:
                return q
            t = ((b[1] - a[1]) * (x1 - a[0]) - (b[0] - a[0]) * (y1 - a[1])) / den
            return (x1 + t * dx, y1 + t * dy)
        for j in range(len(inp)):
            p, q = inp[j - 1], inp[j]
            if inside(q):
                if not inside(p):
                    out.append(cut(p, q))
                out.append(q)
            elif inside(p):
                out.append(cut(p, q))
    return out


def poly_area(poly):
    return abs(sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1] for i in range(len(poly)))) / 2


def overlap_area(p, q):
    return poly_area(clip(p, q)) if len(p) >= 3 and len(q) >= 3 else 0.0


class PlaneIndex:
    """Triangles bucketed by facing and plane depth: [(nkey, d, tri2d, box, tag)]."""

    def __init__(self, bin_m=0.001):
        self.bin, self.b = bin_m, {}

    def add(self, n, d, pts3, tag):
        k = nkey(n)
        p2 = project(pts3, k)
        self.b.setdefault((k, math.floor(d / self.bin)), []).append((d, p2, box_of(p2), tag))

    def near(self, n, d0, d1):
        """Entries of facing n with depth in [d0, d1]."""
        k = nkey(n)
        for i in range(math.floor(d0 / self.bin), math.floor(d1 / self.bin) + 1):
            for e in self.b.get((k, i), ()):
                if d0 <= e[0] <= d1:
                    yield e


def coplanar_pairs(tris_a, index, eps=GEOM_EPS_D, min_area=MIN_AREA, same=False):
    """Same-facing coplanar overlapping triangle pairs between tris_a [(n, d, pts3, tag)] and a PlaneIndex.
    Returns {(tag_a, tag_b): area}. With same=True (tris_a are the index's own triangles) each pair counts once and
    a triangle never pairs with itself or a triangle of the same tag."""
    out = {}
    for n, d, pts3, ta in tris_a:
        k = nkey(n)
        p2 = project(pts3, k)
        bx = box_of(p2)
        for d2, q2, qb, tb in index.near(n, d - eps, d + eps):
            if same and ta >= tb:
                continue
            if box_gap(bx, qb) >= 0:
                continue
            a = overlap_area(p2, q2)
            if a > min_area:
                key = (ta, tb)
                out[key] = out.get(key, 0.0) + a
    return out


def box_tris(lo, hi, tag):
    """The 12 outward triangles of an axis-aligned box as (n, d, pts3, tag) (plain numbers, for the generators'
    box layouts: Tests/test_zfight.py runs coplanar_pairs on them without Blender)."""
    out = []
    for ax in range(3):
        for side, v in ((-1.0, lo[ax]), (1.0, hi[ax])):
            u, w = [i for i in range(3) if i != ax]

            def P(a, b):
                p = [0.0, 0.0, 0.0]
                p[ax], p[u], p[w] = v, a, b
                return tuple(p)
            q = [P(lo[u], lo[w]), P(hi[u], lo[w]), P(hi[u], hi[w]), P(lo[u], hi[w])]
            n = [0.0, 0.0, 0.0]
            n[ax] = side
            d = side * v
            out.append((tuple(n), d, [q[0], q[1], q[2]], tag))
            out.append((tuple(n), d, [q[0], q[2], q[3]], tag))
    return out


def boxes_coplanar(boxes):
    """{(tag_a, tag_b): area} of same-facing coplanar overlapping faces between different boxes [(tag, lo, hi)]."""
    tris = [t for i, (tag, lo, hi) in enumerate(boxes) for t in box_tris(lo, hi, (i, tag))]
    idx = PlaneIndex()
    for n, d, pts, tag in tris:
        idx.add(n, d, pts, tag)
    out = {}
    for (a, b), v in coplanar_pairs(tris, idx, same=True).items():
        if a[0] != b[0]:
            k = (a[1], b[1])
            out[k] = out.get(k, 0.0) + v
    return out


# ------------------------------------------------------------------------------------------------ Blender side
_STATE = {"next": 1, "frame": None, "labels": {}}
_API = {("decals.py", "element"), ("decals.py", "text"), ("decals.py", "trim"), ("decals.py", "stripes"),
        ("style.py", "stencil"), ("style.py", "hazard_triangle"), ("tray_kit.py", "_stencil")}


def _element():
    """The id of the decal element being drawn: the outermost decal-API frame on the stack (new frame = new id)."""
    f, api = sys._getframe(2), None
    while f is not None:
        if (os.path.basename(f.f_code.co_filename), f.f_code.co_name) in _API:
            api = f
        f = f.f_back
    if api is None:            # a direct _quad call from a builder: an element of its own
        api = sys._getframe(2)
        _STATE["frame"] = None
    if api is _STATE["frame"]:
        return _STATE["eid"]
    eid = _STATE["next"]
    _STATE["next"] += 1
    _STATE["frame"], _STATE["eid"] = api, eid
    loc = api.f_locals
    what = loc.get("key") or loc.get("text") or loc.get("string") or loc.get("kind") or loc.get("colour") or ""
    caller = api.f_back if api.f_back is not None else api
    _STATE["labels"][eid] = f"{os.path.basename(caller.f_code.co_filename)}:{caller.f_lineno} {what}".strip()
    return eid


def install():
    """Tag every decal quad with its element id (idempotent)."""
    from se2model import decals as DC
    if getattr(DC._quad, "_dc_zfight", False):
        return
    orig = DC._quad

    def tagged(p, F, corners, d, mat, uvs):
        lay = p.bm.faces.layers.int.get(TAG) or p.bm.faces.layers.int.new(TAG)
        f = orig(p, F, corners, d, mat, uvs)
        f[lay] = _element()
        return f
    tagged._dc_zfight = True
    DC._quad = tagged


def _mesh_tris(objs, matrix=None):
    """(decal faces {eid: [(n, d, pts3)]}, geometry tris [(n, d, pts3, tag)]) of mesh objects (evaluated)."""
    from mathutils import Matrix
    decal, geom = {}, []
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.data
        m = (matrix or Matrix.Identity(4)) @ o.matrix_world
        rot = m.to_3x3()
        att = me.attributes.get(TAG)
        tags = [0] * len(me.polygons)
        if att is not None and att.domain == "FACE":
            tags = [a.value for a in att.data]
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            pts = [m @ me.vertices[i].co for i in t.vertices]
            n = (rot @ t.normal).normalized()
            if n.length < 0.5:
                continue
            d = n.dot(pts[0])
            rec = (tuple(n), d, [tuple(p) for p in pts])
            eid = tags[t.polygon_index]
            if eid:
                decal.setdefault(eid, []).append(rec)
            else:
                geom.append(rec + ((o.name.split(".")[0], t.polygon_index),))
    return decal, geom


def strip(objs):
    for o in objs:
        if o.type == "MESH" and o.data.attributes.get(TAG) is not None:
            o.data.attributes.remove(o.data.attributes[TAG])


def _elements(model, decal):
    out = []
    for eid, faces in sorted(decal.items()):
        n = nkey(faces[0][0])
        pts = [p for _, _, ps in faces for p in ps]
        out.append({"label": _STATE["labels"].get(eid, f"el{eid}"), "model": model, "n": list(n),
                    "d": round(sum(f[1] for f in faces) / len(faces), 6), "box": [round(c, 5) for c in
                                                                              box_of(project(pts, n))]})
    return out


def _decal_vs_geom(model, decal, geom):
    """Decal faces coplanar with (or buried under) an overlapping same-facing mesh face."""
    idx = PlaneIndex()
    for n, d, pts, tag in geom:
        idx.add(n, d, pts, tag[0])
    hits = {}
    for eid, faces in decal.items():
        for n, d, pts in faces:
            k = nkey(n)
            p2 = project(pts, k)
            bx = box_of(p2)
            for d2, q2, qb, tag in idx.near(n, d - GEOM_EPS_D, d + BURY_D):
                if box_gap(bx, qb) >= 0:
                    continue
                a = overlap_area(p2, q2)
                if a > MIN_AREA:
                    kind = "coplanar" if abs(d2 - d) < GEOM_EPS_D else "buried"
                    key = (_STATE["labels"].get(eid, f"el{eid}"), tag, kind)
                    hits[key] = max(hits.get(key, 0.0), round(d2 - d, 5))
    return [{"model": model, "decal": k[0], "part": k[1], "kind": k[2], "dd": v} for k, v in sorted(hits.items())]


def _coplanar_geom(model, geom):
    """Same-facing coplanar overlapping mesh triangles of DIFFERENT objects (parts) in one model."""
    idx = PlaneIndex()
    for n, d, pts, tag in geom:
        idx.add(n, d, pts, tag)
    agg = {}
    for (a, b), v in coplanar_pairs(geom, idx, same=True).items():
        k = tuple(sorted((a[0], b[0])))
        agg[k] = agg.get(k, 0.0) + v
    return [{"model": model, "a": a, "b": b, "area_mm2": round(v * 1e6, 3)} for (a, b), v in sorted(agg.items())]


def _models(built):
    """[(model name, lod, objs)] of a built block: the block LODs and every subpart LOD (rendered LODs only)."""
    out = [("block", i, objs) for i, (_, objs) in enumerate(built["lods"])]
    for name, lods in (built.get("subparts") or {}).items():
        out += [(name, i, objs) for i, (_, objs) in enumerate(lods)]
    return out


def leaf_frame_check(spec, built):
    """Closed and open leaves (LOD0) placed in the block frame against the rack LOD0 and both side panels:
    same-facing coplanar overlapping faces between a leaf and the frame. [{leaf, pose, part, area_mm2}]"""
    from mathutils import Matrix
    from . import doors, rack_side
    sub = built.get("subparts") or {}
    if not doors.has_doors(spec):
        return []
    _, frame = _mesh_tris(built["lods"][0][1])
    if rack_side.SIDE_SUB in sub:
        for m in (Matrix.Identity(4), Matrix.Rotation(math.pi, 4, "Z")):
            frame += _mesh_tris(sub[rack_side.SIDE_SUB][0][1], m)[1]
    idx = PlaneIndex()
    for n, d, pts, tag in frame:
        idx.add(n, d, pts, tag[0])
    out = []
    for lf in doors.leaves(spec):
        for pose, yaw in (("closed", lf["yaw_closed"]), ("open", lf["yaw_open"])):
            m = Matrix.Translation((lf["axis"][0], lf["axis"][1], 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
            _, tris = _mesh_tris(sub[lf["model"]][0][1], m)
            tris = [(n, d, pts, tag[0]) for n, d, pts, tag in tris]
            for (a, b), v in sorted(coplanar_pairs(tris, idx).items()):
                out.append({"leaf": lf["name"], "pose": pose, "leaf_part": a, "frame_part": b,
                            "area_mm2": round(v * 1e6, 3)})
    return out


# ------------------------------------------------------------------------------------------------ model faces
# In game (DC_Rack42_Open seen from below) the containment rail's clamp pads were exactly as tall as the
# rail (their top / bottom faces in the rail's top / bottom planes) and the Feed A tag band stood exactly as proud as
# the PDU face plate: same-facing coplanar faces of different boxes, the Darker / Yellow and the Colorable flicker.
# The decal rules never saw them (neither is a decal); this checks every mesh face of the close LODs.
COPLANAR_LODS = (0, 1)


def _mat_tris(objs, matrix=None):
    """Non-decal mesh triangles as (n, d, pts3, (part, material, polygon index)) (world frame or matrix @ world)."""
    from mathutils import Matrix
    out = []
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.data
        m = (matrix or Matrix.Identity(4)) @ o.matrix_world
        rot = m.to_3x3()
        att = me.attributes.get(TAG)
        tags = [a.value for a in att.data] if att is not None and att.domain == "FACE" else None
        mats = [s.material.name.split(".")[0] if s.material else "-" for s in o.material_slots]
        part = o.name.split(".")[0]
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            if tags and tags[t.polygon_index]:
                continue
            n = (rot @ t.normal).normalized()
            if n.length < 0.5:
                continue
            pts = [tuple(m @ me.vertices[i].co) for i in t.vertices]
            mi = me.polygons[t.polygon_index].material_index
            out.append((tuple(n), n.dot(pts[0]), pts, (part, mats[mi] if mi < len(mats) else "-", t.polygon_index)))
    return out


VIS_OFF = 0.0006   # a coplanar overlap is probed this far in front of its plane (> GEOM_EPS_D)


def _occluder(tris):
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for _, _, pts, _ in tris:
        polys.append((len(verts), len(verts) + 1, len(verts) + 2))
        verts += pts
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None


def _visible(bvh, n, d, poly2):
    """Is any of the overlap's sample points (its centroid and its corners pulled 25 % toward it) open to view: the
    first face the probe ray (from VIS_OFF in front of the plane, along n) meets is not the back of a solid (a face
    turned along the ray, i.e. the probe point is inside a closed body: the overlap is buried)."""
    if bvh is None:
        return True
    from mathutils import Vector
    u, v = basis(nkey(n))
    nv = Vector(n)
    c = (sum(p[0] for p in poly2) / len(poly2), sum(p[1] for p in poly2) / len(poly2))
    for a, b in [c] + [(c[0] + 0.75 * (p[0] - c[0]), c[1] + 0.75 * (p[1] - c[1])) for p in poly2]:
        q = Vector(u) * a + Vector(v) * b + nv * (d + VIS_OFF)
        hit, hn, _, _ = bvh.ray_cast(q, nv, 10.0)
        if hit is None or hn.dot(nv) < 0:
            return True
    return False


def coplanar_rows(model, tris_a, tris_b=None, key_a="a", key_b="b"):
    """VISIBLE same-facing coplanar overlapping faces: within tris_a (any two polygons, also of one part) or, with
    tris_b, between the two sets. Overlaps buried inside a closed body (a plate's back face on the body it is glued to)
    never render and are skipped (_visible). One row per (part/material, part/material) with the visible overlap area
    and one overlap's centroid."""
    other = tris_b if tris_b is not None else tris_a
    idx = PlaneIndex()
    for n, d, pts, tag in other:
        idx.add(n, d, pts, tag)
    bvh = _occluder(tris_a + (tris_b or []))
    agg, where = {}, {}
    for n, d, pts3, ta in tris_a:
        k = nkey(n)
        p2 = project(pts3, k)
        bx = box_of(p2)
        for d2, q2, qb, tb in idx.near(n, d - GEOM_EPS_D, d + GEOM_EPS_D):
            if tris_b is None and ta >= tb:
                continue
            if box_gap(bx, qb) >= 0:
                continue
            poly = clip(p2, q2)
            a = poly_area(poly) if len(poly) >= 3 else 0.0
            if a <= MIN_AREA or not _visible(bvh, n, d, poly):
                continue
            key = (f"{ta[0]}/{ta[1]}", f"{tb[0]}/{tb[1]}")
            if tris_b is None:
                key = tuple(sorted(key))
            agg[key] = agg.get(key, 0.0) + a
            if key not in where:
                u, v = basis(k)
                cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
                where[key] = ([round(u[i] * cx + v[i] * cy + n[i] * d, 4) for i in range(3)], list(k))
    return [{"model": model, key_a: a, key_b: b, "area_mm2": round(v * 1e6, 3), "at": where[(a, b)][0],
             "n": where[(a, b)][1]}
            for (a, b), v in sorted(agg.items())]


def model_coplanar(built):
    """Every rendered close model (block and subpart LODs in COPLANAR_LODS): same-facing coplanar overlapping faces."""
    out = []
    for model, lod, objs in _models(built):
        if lod in COPLANAR_LODS:
            out += coplanar_rows(f"{model}_LOD{lod}", _mat_tris(objs))
    return out


def spawned_subparts(spec):
    """[(subpart model, pose name, Matrix)] of the subparts a Functional block spawns, at their spawned pose in the
    block frame (Path A: the rack sides at the block origin and turned 180 deg, the 42U racks' fan tray)."""
    from mathutils import Matrix
    from . import config, doors, rack_side
    if spec.family != "rack" or getattr(config, "RACK_PATH", "A") != "A":
        return []
    out = [(rack_side.SIDE_SUB, "R", Matrix.Identity(4)), (rack_side.SIDE_SUB, "L", Matrix.Rotation(math.pi, 4, "Z"))]
    t = doors.fan_tray_point(spec)
    if t is not None:
        out.append((doors.FAN_TRAY_SUB, "tray", Matrix.Translation(t)))
    return out


def subpart_frame_check(spec, built):
    """Each spawned subpart (LOD0 and LOD1, at its spawned pose) against the block model of the same LOD: same-facing
    coplanar overlapping faces between the subpart and the block's own geometry."""
    sub = built.get("subparts") or {}
    out = []
    for name, pose, m in spawned_subparts(spec):
        for lod in COPLANAR_LODS:
            if name not in sub or lod >= len(sub[name]) or lod >= len(built["lods"]):
                continue
            rows = coplanar_rows(f"{name}_{pose}_LOD{lod}", _mat_tris(sub[name][lod][1], m),
                                 _mat_tris(built["lods"][lod][1]), "subpart", "block")
            out += rows
    return out


def check_built(spec, built):
    """build_report "zfight" entry for one built block; strips the element tags from every mesh afterwards."""
    from . import doors
    rep = {"elements": [], "decal_geometry": [], "leaf_coplanar": [], "leaf_frame": []}
    if not built:
        return rep
    for model, lod, objs in _models(built):
        name = f"{model}_LOD{lod}"
        decal, geom = _mesh_tris(objs)
        rep["elements"] += _elements(name, decal)
        rep["decal_geometry"] += _decal_vs_geom(name, decal, geom)
        if model in (doors.LEAF_L, doors.LEAF_R):
            rep["leaf_coplanar"] += _coplanar_geom(name, geom)
    rep["leaf_frame"] = leaf_frame_check(spec, built)
    rep["coplanar"] = model_coplanar(built)
    rep["subpart_frame"] = subpart_frame_check(spec, built)
    for _, _, objs in _models(built):
        strip(objs)
    return rep
