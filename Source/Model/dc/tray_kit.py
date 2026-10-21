"""The cable-tray kit: Blender geometry for everything a tray plan (dc/tray_plan.py) describes.

The plan says where things go; the kit only sweeps and dresses it. Every function takes plan objects (a PiecePlan, a
Bundle, a Support, a Fitting) and writes into the piece's Parts, in the plan's box-corner frame (dc/tray.py moves
the finished Parts to the centred block frame).

SE-styled wire basket, not photoreal (Keen style: chunky, readable at first-person range, few large fasteners):

| part | look | purpose |
|---|---|---|
| floor wires | 9 longitudinal wires, r 4 mm, every 5 cm across, on top of the U-wires | carry the cables |
| U-wires | every 0.1 m from 5 cm off each port, under the floor wires, legs outside the wall wires | the basket's load-bearing frame |
| safety edge | a 5 mm top wire, each U-wire leg turned over it (the rolled T-weld) | no sharp wire end at the cable jackets |
| splice plates | half a bolted plate at each port and wall; two halves + two bolts per joint | join the sections |
| bundles | 7 cables of r 9 mm (the six visible ones swept, the hidden centre left out), crevices between cables, laid with a slow twist (60 deg per 0.5 m, phase-locked at ports) | the cabling itself |
| straps | Darker bands round each bundle, or ONE band round bundles that nest, with a buckle | bundle retention |
| trapeze | lipped strut channel, bolted chamfered Yellow end caps, threaded rods, square washers and hex nuts | hanging support |
| rod plates | 34 mm plates under the top plane, the rod threaded into the plate's boss, two square anchor bolt heads | ceiling anchor / rod extension |
| boots, clamps, tags | Rubber end boots, Darker saddle clamps, Yellow density tags with a white stencil | sealed spare ends, strain relief, density marking |

LODs (budgets: plan §Global Constraints): LOD0 as above; LOD1 4-sided wires, every other U-wire, 4-sided bundles,
1 strap per 0.5 m, the trapeze without nuts; LOD2 an alpha-tested vanilla card set for the basket (style.TRAY_CARD),
3-sided bundles, the strut only, in 4 materials; the last LOD (dc/tray.py) a
U channel and a bundle-bed quad.
"""
import math

import bmesh
import numpy as np
from mathutils import Matrix, Vector

from se2model import decals as DC
from se2model import geom as G
from se2model.geom import Part

from . import tray_lanes as TL
from . import tray_plan as TP
from . import tray_xsec as XS
from .style import DARK, HARDWARE, STENCIL_WHITE, TIE, TRAY_CARD, TRAY_HW, TRAY_STEEL, YELLOW

RUBBER = "Rubber"
Z = Vector((0.0, 0.0, 1.0))

# ---------------------------------------------------------------------------------------------------- materials
# LOD2 keeps 4 materials (plan budget): the card, the paint (data cables), Yellow (fibre),
# Rubber (every dark part: power bundles, the strut). Moderate's grey power reads as dark at that range.
# Applied only to pieces that carry the basket card (Parts.card): a piece without one (rod hangers, the Chute) has
# material headroom, so its Brushed rails and Darker parts keep their own materials at range.
LOD2_MAP = {DARK: RUBBER, HARDWARE: RUBBER, "PaintedMetalGrey": RUBBER, "BrushedMetal": RUBBER}   # (no wires at LOD2)


def mat(name, lod, card=True):
    """The material a role takes at a LOD (Parts.done applies it to every Part)."""
    return LOD2_MAP.get(name, name) if (lod >= 2 and card) else name


# ---------------------------------------------------------------------------------------------------- parts
class Parts:
    """The Parts of one piece at one LOD. Swept geometry is authored with outward winding, so those Parts are
    decal-style (no normal recalculation, open ends stay open); closed library solids go to `solid`."""

    def __init__(self, lod, card=True):
        self.lod = lod
        self.card = card          # the piece carries the LOD2 basket card (its 4-material LOD2 set applies)
        self.bundle_pts = {}      # lane -> a bend bundle's faceted centreline (its straps hug it: straps())
        self.P = {}
        # The Parts are what the pieces ARE (fracture.ROLES["tray"] follows them): wire = the basket;
        # cable = the bundles and their end boots; tie = the cable dressing (straps, split collars, saddle clamps)
        # with tiehw its metal (strap buckles, collar bolts); hw = the hangers' and the basket's hardware (rods, nuts,
        # rod / splice plates, guide clamps); strut = the Darker strut channels that carry the basket (trapeze, floor
        # strut, the rod hanger's ceiling channel and anchor plate); guide = the Darker tray furniture the cables
        # later ride on (waterfall guide, landing brush collar, the ladder's brush foot plate, the Cross's saddle deck)
        for name, decal in (("wire", True), ("cable", True), ("tie", True), ("hw", True), ("solid", False),
                            ("trim", True), ("stencil", True), ("card", True), ("tiehw", True), ("strut", True),
                            ("guide", True)):
            p = Part(name)
            p.decal = decal
            self.P[name] = p

    def __getitem__(self, k):
        return self.P[k]

    def done(self, shift):
        """The non-empty Parts, moved by `shift` (box-corner frame -> centred block frame), their materials mapped
        to the LOD's set (mat())."""
        m = Matrix.Translation(Vector(shift))
        out = []
        for p in self.P.values():
            if p.empty():
                continue
            _remap(p, self.lod, self.card)
            p.bm.transform(m)
            p.bm.normal_update()
            out.append(p)
        return out


def _remap(p, lod, card=True):
    """Rename a Part's material slots by mat(name, lod, card), merging slots that map to the same material."""
    new = []
    idx = []
    for name in p.mats:
        n = mat(name, lod, card)
        if n not in new:
            new.append(n)
        idx.append(new.index(n))
    if new == p.mats:
        return
    for f in p.bm.faces:
        f.material_index = idx[f.material_index]
    p.mats = new


# ---------------------------------------------------------------------------------------------------- sweeps
def _v(p):
    return Vector((float(p[0]), float(p[1]), float(p[2])))


def frames(points, up=None, ends=None):
    """tray_xsec.frames_np (rotation-minimising frames and mitres) as mathutils Vectors for sweep()."""
    fr, mit = XS.frames_np([tuple(_v(p)) for p in points], None if up is None else tuple(up),
                           None if ends is None else tuple(tuple(e) for e in ends))
    return ([tuple(Vector(tuple(float(x) for x in v)) for v in f) for f in fr],
            [(k, None if m is None else Vector(tuple(float(x) for x in m))) for k, m in mit])


def sweep(p, points, profile, material, closed=True, cap0=False, cap1=False, up=None, smooth=True, fr=None,
          twist=None, ends=None, normals=None):
    """Sweep a 2D profile [(a, b)] (a along the frame's s, b along u) along a polyline. Closed profiles are
    counter-clockwise (outward faces); an open profile's outward side is on the right of its direction (a
    counter-clockwise arc). Corners are mitred (the ring is stretched along the bend so the section keeps its
    thickness). smooth: the side faces form one round band (shaded smooth, never bevelled). normals: per profile
    point its exact 2D shading normal (a, b), turned with the twist and written to the per-loop normal hook
    (se2model.normals: the strands' radial normals). Returns the rings."""
    bm = p.bm
    pts = [_v(q) for q in points]
    if fr is None:
        fr, mit = frames(pts, up, ends)
    else:
        mit = [(1.0, None)] * len(pts)
    rings = []
    vn = {}
    for i, (q, (t, s, u), (k, m)) in enumerate(zip(pts, fr, mit)):
        ring = []
        prof, nprof = profile, normals
        if twist is not None and twist[i]:
            c, sn = math.cos(twist[i]), math.sin(twist[i])
            prof = [(a * c - b * sn, a * sn + b * c) for a, b in profile]
            if normals is not None:
                nprof = [(a * c - b * sn, a * sn + b * c) for a, b in normals]
        for j, (a, b) in enumerate(prof):
            o = s * a + u * b
            if m is not None and k != 1.0:
                o = o + m * (o.dot(m) * (k - 1.0))
            v = bm.verts.new(q + o)
            ring.append(v)
            if nprof is not None:
                vn[v] = (s * nprof[j][0] + u * nprof[j][1]).normalized()
        rings.append(ring)
    nlay = G.loop_normal_layer(bm) if normals is not None else None
    idx = p.mi(material)
    lay, rid = G.round_id(bm) if smooth else (None, 0)
    nprof = len(profile)
    nedge = nprof if closed else nprof - 1
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(nedge):
            j = (k + 1) % nprof
            f = bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
            f.material_index = idx
            if lay:
                f[lay] = rid
            if nlay is not None:
                for lp in f.loops:
                    lp[nlay] = vn[lp.vert]
    if closed and cap0:
        bm.faces.new(list(reversed(rings[0]))).material_index = idx
    if closed and cap1:
        bm.faces.new(rings[-1]).material_index = idx
    return rings


ngon = G.ngon        # a counter-clockwise regular n-gon of circumradius r (se2model.geom)


def wire_profile(r, lod, sides=None):
    """A wire's section per LOD: 6-sided at LOD0 (a flat on top), 4-sided at LOD1 (a diamond), 3 at LOD2. sides=5:
    the LOD0 U-wires (the cross wires bend 5 times; 5 sides keep the StraightS within its 1500-tri budget)."""
    n = sides or (6, 4, 3)[min(lod, 2)]
    R, phase = {6: (r / math.cos(math.pi / 6), 0.0), 5: (r / math.cos(math.pi / 5), math.pi / 2),
                4: (r * 1.15, 0.0), 3: (r * 1.3, -math.pi / 2)}[n]
    return ngon(R, n, phase)


def box_open(p, lo, hi, material, skip=()):
    """An axis-aligned box from its faces, outward wound, leaving out the faces in `skip` (e.g. "-x": a face that
    lies on a port plane, or "-z": one that is never seen)."""
    bm = p.bm
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    V = {}

    def v(i, j, k):
        if (i, j, k) not in V:
            V[(i, j, k)] = bm.verts.new(((x0, x1)[i], (y0, y1)[j], (z0, z1)[k]))
        return V[(i, j, k)]
    idx = p.mi(material)
    faces = {"-x": ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)), "+x": ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
             "-y": ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)), "+y": ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
             "-z": ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)), "+z": ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))}
    for k, c in faces.items():
        if k not in skip:
            bm.faces.new([v(*q) for q in c]).material_index = idx


def hexnut(p, centre, axis, r, h, material, cap=True, sides=6, phase=0.0):
    """A hex nut / bolt head: a `sides`-gon prism from centre along axis (unit) for h, capped at the far end."""
    a = _v(axis).normalized()
    ref = Vector((1.0, 0.0, 0.0)) if abs(a.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    e1 = (ref - a * ref.dot(a)).normalized()
    e2 = a.cross(e1)
    c0 = _v(centre)
    pts = [c0, c0 + a * h]
    fr = [(a, e1, e2)] * 2
    sweep(p, pts, ngon(r, sides, phase), material, closed=True, cap0=False, cap1=cap, smooth=False, fr=fr)


# ---------------------------------------------------------------------------------------------------- the basket
from .tray_kit_tol import TOL      # per LOD: how far a simplified wire or bundle may leave its plan path
CARD_UV_M = 2.0                       # LOD2 card: metres per UV unit. GratingMetallic has 60 x 20 slots per tile, so
#                                       3.3 cm across the floor (and up the walls), 10 cm along the run (the U pitch)
SPLICE = dict(l=0.032, t=0.0025, h=0.022, chamfer=0.004, bolt_r=0.0055, bolt_h=0.003)


def _path_frames(path):
    """Per point of a plan Path: (t, s, u) as numpy (u = the floor normal; s = u x t) and the arc lengths."""
    p = np.asarray(path.points, float)
    t = np.gradient(p, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    u = np.asarray(path.normals, float)
    u = u - t * np.sum(u * t, axis=1)[:, None]
    u /= np.linalg.norm(u, axis=1)[:, None]
    s = np.cross(u, t)
    return t, s, u, path.lengths()


def _offset(path, fr, s_off, h_off):
    """The path offset by (s, h) in its own frame: per point, h_off may be an array."""
    t, s, u, _ = fr
    h = np.broadcast_to(np.asarray(h_off, float), (len(t),))
    return np.asarray(path.points, float) + s_off * s + h[:, None] * u


def _port_ends(plan, path):
    """Whether each end of a basket path lies on a port (open, flush-joined) or is free (capped)."""
    ends = []
    for q in (path.points[0], path.points[-1]):
        ends.append(any(np.linalg.norm(np.asarray(q) - np.asarray(pt.o)) < 1e-3 for pt in plan.ports.values()))
    return ends


def _runs(mask):
    """[(i0, i1)] index runs where mask is True (inclusive)."""
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def _wire(p, pts, r, lod, material, up, cap0, cap1, ends=None):
    """A wire along pts: simplified to the LOD's tolerance, or (ends given: a bend's facet points) as it is."""
    q = XS.simplify(pts, TOL[lod]) if ends is None else pts
    if len(q) < 2:
        return
    sweep(p, q, wire_profile(r, lod), material, closed=True, cap0=cap0, cap1=cap1, up=up, ends=ends)


def facets(path, lod):
    """A bend path's facet stations at this LOD (tray_xsec.bend_facets), or None for a straight path."""
    return XS.path_facets(path, lod)


def _interp(path, fr, l):
    """Point and frame of a path at arc length l."""
    t, s, u, L = fr
    i = int(np.clip(np.searchsorted(L, l) - 1, 0, len(L) - 2))
    f = 0.0 if L[i + 1] - L[i] < 1e-12 else (l - L[i]) / (L[i + 1] - L[i])
    p = np.asarray(path.points[i], float) * (1 - f) + np.asarray(path.points[i + 1], float) * f
    tt = t[i] * (1 - f) + t[i + 1] * f
    tt /= np.linalg.norm(tt)
    uu = u[i] * (1 - f) + u[i + 1] * f
    uu = uu - tt * (uu @ tt)
    uu /= np.linalg.norm(uu)
    return p, tt, np.cross(uu, tt), uu


def basket(P, plan, lod):
    """The wire basket of every basket path of the plan (fillet "wall" paths are junction pieces)."""
    for path in plan.structure:
        if path.kind == "basket":
            _basket_path(P, plan, path, lod)
        else:
            _wall_path(P, path, lod)


def _others(plan, path):
    return [q for q in plan.structure if q.kind == "basket" and q is not path]


def _in_floor_of(others, p, half=XS.FLOOR_S[-1] + 1e-6):
    """Whether point p lies over another basket path's floor (within `half` of its centreline, between its ends):
    a Cross's two floors overlap in the crossing, where one path's U-wires are left out (the other's floor wires
    are there) and one card gives way to the other at LOD2."""
    for q in others:
        a, b = np.asarray(q.points[0], float), np.asarray(q.points[-1], float)
        d = b - a
        f = float((p - a) @ d / (d @ d))
        if -1e-9 <= f <= 1 + 1e-9 and np.linalg.norm(p - (a + f * d)) < half:
            return True
    return False


def _basket_path(P, plan, path, lod):
    fr = _path_frames(path)
    t, s, u, L = fr
    port0, port1 = _port_ends(plan, path)
    he = XS.wall_height_profile(L, path.wall_h, port0, port1)
    floor_up = Vector(u[0])         # the longitudinal wires' sweeps start from the floor normal (frames())
    w = P["wire"]
    fac = facets(path, lod)         # a bend: every longitudinal wire on the same radial facets, ends square to the ports
    ends = None if fac is None else (Vector(t[0]), Vector(t[-1]))
    others = _others(plan, path)
    if lod >= 2:
        _cards(P, path, fr, he, lod, fac, others, (port0, port1))
        return

    def run(pts, sub):
        whole = sub.start == 0 and sub.stop == len(L)
        return (XS.resample(pts, L, fac), ends) if (fac is not None and whole) else (pts[sub], None)
    floor = XS.FLOOR_S if lod == 0 else XS.FLOOR_S[::2]
    for so in floor:
        q, e = run(_offset(path, fr, so, XS.FLOOR_WIRE_DH), slice(0, len(L)))
        q = np.array(q, float)
        for end, is_port in ((0, port0), (1, port1)):     # a branch's free end inside a junction: its floor wires
            if not is_port and others:                    # reach on to the run's outer floor wire (welded there)
                i, k = (0, 1) if end == 0 else (-1, -2)
                q[i] = q[i] + XS.FLOOR_EDGE_IN * (q[i] - q[k]) / np.linalg.norm(q[i] - q[k])
        _wire(w, q, TL.WIRE_R, lod, TRAY_STEEL, floor_up, not port0, not port1, e)
    for k, sg in ((0, -1), (1, 1)):
        for i0, i1 in _runs(path.wall_mask(k)):
            c0, c1 = (i0 > 0 or not port0), (i1 < len(L) - 1 or not port1)
            sub = slice(i0, i1 + 1)
            if path.openings:     # an end at an opening runs on into the fillet's wire: left open
                Ls = path.lengths()
                cuts = [rng for w_, rng, _ in path.openings if w_ == k]
                c0 = c0 and not any(abs(Ls[i0] - b) < 1e-6 for _, b in cuts)
                c1 = c1 and not any(abs(Ls[i1] - a) < 1e-6 for a, _ in cuts)
            low, e = run(_offset(path, fr, sg * TL.WALL_S, XS.LOWER_WALL_H), sub)
            top, _ = run(_offset(path, fr, sg * TL.WALL_S, he), sub)
            _wire(w, low, TL.WIRE_R, lod, TRAY_STEEL, floor_up, c0, c1, e)
            _wire(w, top, TL.EDGE_WIRE_R, lod, TRAY_STEEL, floor_up, c0, c1, e)
    if fac is not None:
        ust = XS.bend_u_stations(path.arc, lod)
    elif port0 or not port1:
        ust = XS.u_stations(L[-1], lod)
    else:                           # a branch (one port, at its far end): the 0.1 m rhythm counts from that port,
        ust = XS.branch_u_stations(L[-1], lod)      # on to its free end in the junction
    for l in ust:
        if others and _in_floor_of(others, _interp(path, fr, l)[0]):
            continue                # the crossing: the other run's floor wires lie here
        _u_wire(P, path, fr, he, l, lod)
    if lod == 0:
        for end, is_port in ((0, port0), (1, port1)):
            if is_port:
                _splice(P, path, fr, end)


def _u_wire(P, path, fr, he, l, lod):
    """A transverse U-wire at arc length l: under the floor wires, up the outside of each standing wall, and (LOD0)
    turned over the safety-edge wire."""
    p, t, s, u = _interp(path, fr, l)
    _, _, _, L = fr
    h_e = float(np.interp(l, L, he))
    k = int(np.clip(np.searchsorted(L, l), 0, len(L) - 1))
    walls = [bool(path.wall_mask(0)[k]), bool(path.wall_mask(1)[k])]
    us, hf, ht = TL.U_LEG_S, XS.U_FLOOR_DH, h_e + (XS.EDGE_TURN if lod == 0 else 0.0)
    pts = []
    if walls[0]:
        if lod == 0:
            pts.append((-(TL.WALL_S - 0.007), ht))
        pts += [(-us, ht), (-us, hf)]
    else:
        pts.append((-TL.WALL_S, hf))
    if walls[1]:
        pts += [(us, hf), (us, ht)]
        if lod == 0:
            pts.append((TL.WALL_S - 0.007, ht))
    else:
        pts.append((TL.WALL_S, hf))
    q = [p + a * s + b * u for a, b in pts]
    sweep(P["wire"], q, wire_profile(TL.WIRE_R, lod, 5 if lod == 0 else None), TRAY_STEEL, closed=True,
          cap0=lod == 0 or not walls[0],
          cap1=lod == 0 or not walls[1], up=Vector(t))


def _splice(P, path, fr, end):
    """Half a bolted splice plate on the outside of each wall at a port: the neighbour piece brings the other half
    (the halves meet open on the port plane), so a joint shows one 64 mm plate with two bolts."""
    t, s, u, L = fr
    i = 0 if end == 0 else -1
    o = np.asarray(path.points[i], float)
    inward = t[i] if end == 0 else -t[i]
    S = SPLICE
    for k in (0, 1):
        if not path.wall_mask(k)[i]:
            continue
        sg = -1 if k == 0 else 1
        s0 = TL.WALL_S + TL.WIRE_R + 0.0005
        pts = [o, o + inward * S["l"]]
        Tn, Sn, Un = Vector(inward), Vector(np.cross(u[i], inward)), Vector(u[i])
        frs = [(Tn, Sn, Un)] * 2
        # the sweep's s axis is u x inward (= -s at the far end): the plate centre on that axis
        a_c = sg * (s0 + S["t"] / 2) * float(Sn.dot(Vector(s[i])))
        rect = [(a_c - S["t"] / 2, XS.LOWER_WALL_H - S["h"]), (a_c + S["t"] / 2, XS.LOWER_WALL_H - S["h"]),
                (a_c + S["t"] / 2, XS.LOWER_WALL_H + S["h"]), (a_c - S["t"] / 2, XS.LOWER_WALL_H + S["h"])]
        sweep(P["hw"], pts, rect, TRAY_HW, closed=True, cap0=False, cap1=True, smooth=False, fr=frs)
        c = o + inward * (S["l"] / 2) + sg * (s0 + S["t"]) * s[i] + XS.LOWER_WALL_H * u[i]
        hexnut(P["hw"], c, sg * s[i], S["bolt_r"], S["bolt_h"], TRAY_HW, sides=4, phase=math.pi / 4)   # square head


def _wall_on(path, k, l):
    """Whether wall k (0 = -s, 1 = +s) of a basket path stands at arc length l (not in an opening)."""
    return bool(path.walls[k]) and not any(w == k and l0 + 1e-9 < l < l1 - 1e-9 for w, (l0, l1), _ in path.openings)


def _band_crossings(path, fr, others, half):
    """Arc lengths where a path enters or leaves another basket path's card band (|lateral| = half)."""
    L = fr[3]
    out = []
    for q in others:
        a, b = np.asarray(q.points[0], float), np.asarray(q.points[-1], float)
        d = (b - a) / np.linalg.norm(b - a)

        def lat(p):
            r = p - a
            return np.linalg.norm(r - (r @ d) * d) - half
        v = [lat(np.asarray(p, float)) for p in path.points]
        for i in range(len(v) - 1):
            if v[i] * v[i + 1] < 0:
                out.append(L[i] + (L[i + 1] - L[i]) * v[i] / (v[i] - v[i + 1]))
    return out


def _cards(P, path, fr, he, lod, fac=None, others=(), ports=(True, True)):
    """LOD2: the basket as an alpha-tested card set (floor + two walls; the card material is two-sided). The grey
    grating matches the bright-steel basket at range. A bend: one quad per facet (fac). A junction's
    path: its floor breaks only where it runs into another path's floor, which it leaves to that path's card
    (no overlapping cards); its walls break at its openings and stand at the plain WALL_H (at this range the junction
    reads as a plain tray, and every joint meets its neighbour's LOD2 wall exactly)."""
    t, s, u, L = fr
    junction = bool(path.openings or others)
    if fac is not None:
        lf = lw = list(fac)
    else:
        pts = np.asarray(path.points, float)
        lf = [float(L[int(np.argmin(np.linalg.norm(pts - q, axis=1)))]) for q in XS.simplify(pts, TOL[lod])]
        lw = list(lf)
        if junction:
            lf += _band_crossings(path, fr, others, TL.U_LEG_S)
            lw += [v for _, rng, _ in path.openings for v in rng]
            he = np.full(len(L), TL.WALL_H)
    card = P["card"]
    bm = card.bm
    uvl = bm.loops.layers.uv.verify()
    mi = card.mi(TRAY_CARD)
    us, hf = TL.U_LEG_S, (XS.U_FLOOR_DH + XS.FLOOR_WIRE_DH) / 2

    def quad(corners, uvs):
        f = bm.faces.new([bm.verts.new(Vector(c)) for c in corners])
        f.material_index = mi
        for loop, uv in zip(f.loops, uvs):
            loop[uvl].uv = uv

    def stations(ls):
        ls = XS._unique([min(max(v, 0.0), L[-1]) for v in ls])
        return ls, [_interp(path, fr, l) for l in ls]
    ls, smp = stations(lf)
    for i in range(len(ls) - 1):
        (pi, _, si, ui), (pj, _, sj, uj) = smp[i], smp[i + 1]
        if others and _in_floor_of(others, _interp(path, fr, (ls[i] + ls[i + 1]) / 2)[0], us):
            continue
        li, lj = ls[i] / CARD_UV_M, ls[i + 1] / CARD_UV_M
        # floor (faces up; the card material is two-sided, as vanilla's one-face catwalk grating): u across, v along
        quad([pi - us * si + hf * ui, pi + us * si + hf * ui, pj + us * sj + hf * uj, pj - us * sj + hf * uj][::-1],
             [(-us / CARD_UV_M, li), (us / CARD_UV_M, li), (us / CARD_UV_M, lj), (-us / CARD_UV_M, lj)][::-1])
    ls, smp = stations(lw)
    hs = np.interp(ls, L, he)
    for i in range(len(ls) - 1):
        j = i + 1
        (pi, _, si, ui), (pj, _, sj, uj) = smp[i], smp[j]
        li, lj = ls[i] / CARD_UV_M, ls[j] / CARD_UV_M
        for k, sg in ((0, -1), (1, 1)):
            if not _wall_on(path, k, (ls[i] + ls[j]) / 2):
                continue
            a = [pi + sg * us * si + XS.U_FLOOR_DH * ui, pj + sg * us * sj + XS.U_FLOOR_DH * uj,
                 pj + sg * us * sj + hs[j] * uj, pi + sg * us * si + hs[i] * ui]
            uv = [(XS.U_FLOOR_DH / CARD_UV_M, li), (XS.U_FLOOR_DH / CARD_UV_M, lj), (hs[j] / CARD_UV_M, lj),
                  (hs[i] / CARD_UV_M, li)]
            if sg < 0:
                a, uv = a[::-1], uv[::-1]
            quad(a, uv)


def _wall_path(P, path, lod):
    """A junction's fillet wall (a "wall" path: points on the floor top along the wall foot, normals up the wall) and
    the floor it closes:
    - LOD0: the lower wall wire and the safety-edge wire (as a straight's; LOD1 the safety edge only), the floor's
      edge arc 1 cm in from the wall and the stubs on the 5 cm floor pitch out to the two outer floor wires it joins
      (tray_xsec.corner_floor);
    - LOD0: two posts, the U-wires of a curved wall (tray_xsec.fillet_posts): up the outside of the wall wires
      from under the floor, turned over the safety edge;
    - LOD2: the wall as card quads at the cards' line (U_LEG_S, 8 mm outside the wall) and the corner's floor fan
      (tray_xsec.corner_card), so the junction's card set has no hole and no overlap."""
    p = np.asarray(path.points, float)
    n = np.asarray(path.normals, float)
    c, e1, e2, R = XS.fillet_frame(path)
    up = Vector(n[0])
    if lod >= 2:
        _fillet_cards(P, path, c, e1, e2, R, n[0])
        return
    # every wire here ends ON another (the run's and branch's wall wires, the outer floor wires, the edge arc), so
    # their ends are left open: the wire they meet covers them
    k = 4 if lod == 0 else 2                          # the arc's chords: 22.5 deg / 45 deg
    arc = [c + R * (math.sin(f) * e1 + math.cos(f) * e2) for f in np.linspace(0, math.pi / 2, k + 1)]
    for h, r in ((XS.LOWER_WALL_H, TL.WIRE_R), (path.wall_h, TL.EDGE_WIRE_R))[lod:]:     # LOD1: the edge only
        sweep(P["wire"], [q + h * n[0] for q in arc], wire_profile(r, lod), TRAY_STEEL, closed=True, up=up)
    if lod > 0:
        return
    edge, stubs = XS.corner_floor(path)
    edge = edge[::(len(edge) - 1) // k]               # (corner_floor samples it in 12 chords)
    dz = XS.FLOOR_WIRE_DH * n[0]
    sweep(P["wire"], [q + dz for q in edge], wire_profile(TL.WIRE_R, lod), TRAY_STEEL, closed=True, up=up)
    for a, b in stubs:
        sweep(P["wire"], [a + dz, b + dz], wire_profile(TL.WIRE_R, lod), TRAY_STEEL, closed=True, up=up)
    L = path.lengths()
    for l in XS.fillet_posts(path):     # posts: radial line at this arc length
        f = (math.pi / 2) * l / L[-1]
        rad = math.sin(f) * e1 + math.cos(f) * e2     # outwards from the centre = into the tray
        ht = path.wall_h + XS.EDGE_TURN       # turned over the safety edge, 7 mm into the tray (as a U-wire's)
        pts = [(R + 0.007, ht), (R - XS.U_LEG_DS, ht), (R - XS.U_LEG_DS, XS.U_FLOOR_DH)]
        q = [c + a * rad + b * n[0] for a, b in pts]
        tan = np.cross(n[0], rad)
        sweep(P["wire"], q, wire_profile(TL.WIRE_R, lod, 5), TRAY_STEEL, closed=True, cap0=True, cap1=True,
              up=Vector(tan))


def _fillet_cards(P, path, c, e1, e2, R, nrm, segs=2):
    """LOD2 of a fillet: its wall as card quads on the cards' line, and its corner's floor fan."""
    card = P["card"]
    bm = card.bm
    uvl = bm.loops.layers.uv.verify()
    mi = card.mi(TRAY_CARD)
    r = R - (TL.U_LEG_S - TL.WALL_S)
    hf = (XS.U_FLOOR_DH + XS.FLOOR_WIRE_DH) / 2

    def face(corners, uvs):
        f = bm.faces.new([bm.verts.new(Vector(tuple(v))) for v in corners])
        f.material_index = mi
        for loop, uv in zip(f.loops, uvs):
            loop[uvl].uv = uv
    fs = np.linspace(0, math.pi / 2, segs + 1)
    for a, b in zip(fs, fs[1:]):
        pa, pb = (c + r * (math.sin(f) * e1 + math.cos(f) * e2) for f in (a, b))
        la, lb = r * a / CARD_UV_M, r * b / CARD_UV_M
        h = TL.WALL_H                    # (a junction's LOD2 walls stand at the plain height: _cards)
        face([pa + XS.U_FLOOR_DH * nrm, pb + XS.U_FLOOR_DH * nrm, pb + h * nrm, pa + h * nrm],
             [(XS.U_FLOOR_DH / CARD_UV_M, la), (XS.U_FLOOR_DH / CARD_UV_M, lb), (h / CARD_UV_M, lb),
              (h / CARD_UV_M, la)])
    for tri in XS.corner_card(path):
        q = [v + hf * nrm for v in tri]
        f = bm.faces.new([bm.verts.new(Vector(tuple(v))) for v in q])
        if f.normal.dot(Vector(tuple(nrm))) < 0:
            f.normal_flip()
        f.material_index = mi
        for loop in f.loops:
            loop[uvl].uv = (loop.vert.co.x / CARD_UV_M, loop.vert.co.y / CARD_UV_M)


# ---------------------------------------------------------------------------------------------------- bundles
def bundle(P, plan, b, lod):
    """One cable bundle along its plan centreline. LOD0: the six visible cables of the 7 (each a 6-sided cable's
    three outward faces between its contacts with its neighbours: a closed skin with a crevice between cables, laid
    with a slow twist phase-locked at the ports);
    LOD1 a 4-sided tube; LOD2 a 3-sided one. PORT ends are open (the neighbour continues them); a bundle that ends
    anywhere else is capped unless its end hides in a fitting (boot, collar, entry brush)."""
    # a bend's / junction's bundle bends on its facet radials, its end rings square to the ports (tray_xsec.bundle_path)
    pts, ends = XS.bundle_path(plan, b, lod, TOL[lod])
    if ends is not None:
        P.bundle_pts[b.lane] = pts
        ends = tuple(Vector(tuple(float(x) for x in e)) for e in ends)
    if len(pts) < 2:
        return
    up = Vector(tuple(float(x) for x in XS.floor_up(plan, pts[0])))
    m = b.material
    scale = b.radius / TL.R_B
    if lod == 0:   # the lay: the strands turn round the bundle, whole cable pitches per piece (tray_xsec.lay_total)
        pts, lay = XS.lay_points(pts, lock=XS.lay_locked(b))
        lay = lay + XS.frame_drift(plan, b, pts, up, ends)
        rings = [sweep(P["cable"], pts, [(a * scale, c * scale) for a, c in arc], m, closed=False, up=up, twist=lay,
                       ends=ends, normals=[(a - cs, c - ch) for a, c in arc] if RADIAL_NORMALS else None)
                 for arc, (cs, ch) in zip(XS.cable_arc(), XS.cable_centres(XS.CABLE_PHASE))]
        if CAP_PORTS and (plan.shape, plan.density) not in CAP_SKIP:
            for i, e in enumerate(b.ends):
                if e.kind == "PORT":
                    _cable_cap(P["cable"], [r[0 if i == 0 else -1] for r in rings], pts, i, m)
        return
    caps = [e.kind not in ("PORT", "SPLIT", "ENTRY", "BOOT") or (e.kind == "BOOT" and lod >= 2) for e in b.ends]
    sweep(P["cable"], pts, wire_profile(b.radius, lod), m, closed=True, cap0=caps[0], cap1=caps[1], up=up, ends=ends,
          twist=XS.frame_drift(plan, b, pts, up, ends))


RADIAL_NORMALS = True   # LOD0 strands shade by their own radial normal (no lay bands)
CAP_PORTS = True        # LOD0 cable-end caps at every PORT end (tray_xsec.CAP_SKIP aside)
CAP_INSET, CAP_SKIP = XS.CAP_INSET, XS.CAP_SKIP


def _cable_cap(p, end_rings, pts, i, material):
    """Close a LOD0 bundle's PORT end: at a free run end the open strand sweeps showed hollow 3-faced
    profiles. The cap is the bundle's own section (the hexagon of the six contact points, for the hidden centre
    cable, plus each outer cable's 3-faced lobe: 16 triangles), flat-shaded, CAP_INSET inside the port plane. At a
    joint the two pieces' caps face away from each other 2 x CAP_INSET apart, wholly inside the continuous closed
    strand skin, so they never show and never z-fight; at a free end the run reads as cut, solid cables.
    end_rings: per cable, its arc's ring at that end (ordered by cable, counter-clockwise in the profile)."""
    a, b = (pts[0], pts[1]) if i == 0 else (pts[-1], pts[-2])
    out = (_v(a) - _v(b)).normalized()         # outward along the port normal (the PORT rule: straight for 5 cm)
    bm = p.bm
    mi = p.mi(material)
    shift = -out * CAP_INSET
    polys = [[r[0] for r in end_rings]] + [list(r) for r in end_rings]     # centre hexagon, then the six lobes
    for poly in polys:
        vs = [bm.verts.new(v.co + shift) for v in poly]
        n = (vs[1].co - vs[0].co).cross(vs[2].co - vs[0].co)
        if n.dot(out) < 0:
            vs.reverse()
        f = bm.faces.new(vs)
        f.material_index = mi


def _bundle_facets(plan, b, lod):
    return XS.bundle_facets(plan, b, lod)


def bundles(P, plan, lod):
    for b in plan.bundles:
        bundle(P, plan, b, lod)


# ---------------------------------------------------------------------------------------------------- straps
BUCKLE = (0.022, 0.016, 0.004)     # along the bundle, across, thick


def _station_straps(plan):
    """{station plane: [strap fittings]}: the straps that share one station plane (its unit normal, sign-fixed, and
    offset), whichever bundle or lane station they were planned from. A junction's turning group shares its radial
    lines (its lanes are concentric), and a turning lane's lead strap 0.125 m from a port lies in the plane of the
    straight lanes' strap there, so each such plane gets one band per nest of bundles."""
    out = {}
    for f in plan.fittings:
        if f.kind != "strap":
            continue
        t = np.asarray(f.frame.t, float)
        k = int(np.argmax(np.abs(t) > 1e-6))      # the first non-zero component positive: +t and -t are one plane
        sg = 1.0 if t[k] > 0 else -1.0
        key = (tuple(np.round(sg * t, 3) + 0.0), round(float(sg * np.dot(f.frame.o, t)), 3))
        out.setdefault(key, []).append(f)
    return out


def straps(P, plan, lod):
    """The straps per station: bundles that nest share one band, the rest get their own. LOD0 every
    station, with a buckle; LOD1 one station per 0.5 m (0.125 + k 0.5 from port a), no buckle; LOD2 none."""
    if lod >= 2:
        return
    ties = _deck_ties(plan)
    for _, fs in sorted(_station_straps(plan).items()):
        station = min(float(f.params.get("station", 0.0)) for f in fs)
        if lod == 1 and abs(((station - TL.STRAP_PHASE) / 0.5) - round((station - TL.STRAP_PHASE) / 0.5)) > 1e-6:
            continue
        if lod >= 1 and all(f.params.get("lod0_only") for f in fs):     # (the Drop's ties on its falls)
            continue
        o0, t, s, u = fs[0].frame.o, fs[0].frame.t, fs[0].frame.s, fs[0].frame.u
        discs, tied = [], []
        for f in fs:
            c = _on_facets(P.bundle_pts.get(f.params.get("bundle")), f.frame.o, t)
            d = c - o0
            discs.append((float(d @ s), float(d @ u), f.size[1] / 2 - TL.STRAP_T))
            if "tie_to" in f.params:     # the Chute's straps tie the bundle to the rung behind it: the band
                off, half, thick = f.params["tie_to"]    # also wraps the rung's back corners
                ds, du = discs[-1][:2]
                tied.append((len(discs) - 1, [(ds + k * half, du + off + thick / 2, TL.STRAP_T + XS.STRAP_BITE)
                                              for k in (-1, 1)]))
        anchors = _tie_anchors(ties, o0, t, s, u)       # a deck strap: tied down to the saddle at both sides
        groups = XS.strap_groups(discs)
        for g in groups:
            extra = [q for i, ex in tied if i in g for q in ex]
            if anchors:     # the outermost band on each side runs down to that side's tie mount
                lo_i = min(range(len(discs)), key=lambda i: discs[i][0])
                hi_i = max(range(len(discs)), key=lambda i: discs[i][0])
                extra = [a for a, i in zip(anchors, (lo_i, hi_i)) if i in g]
            strap(P, (o0, t, s, u), [discs[i] for i in g] + extra, lod,
                  buckle=not _under_deck(plan, o0) and not tied)


TIE_DISC = 0.003      # a tie mount as the strap band sees it: a small disc on the deck at the mount's centre


def _deck_ties(plan):
    """The crossover saddles' tie mounts [(saddle fitting, centre (world), across unit)]."""
    out = []
    for f in plan.fittings:
        if f.kind == "crossover_saddle":
            for q, size in TP.saddle_tie_boxes(f):
                out.append((f, np.asarray(q.o, float), np.asarray(f.frame.t, float)))
    return out


def _tie_anchors(ties, o, t, s, u):
    """The two tie-mount discs [(s, h, r)] (the -s one first) a strap station's band must reach when its plane runs
    through a pair of tie mounts on a saddle's deck, else []."""
    o, t, s, u = (np.asarray(v, float) for v in (o, t, s, u))
    hits = []
    for f, c, _ in ties:
        if abs((c - o) @ t) < 0.004:
            d = c + (TIE_DISC + 0.001 - f.params["tie_size"][2] / 2) * np.asarray(f.frame.u, float) - o
            hits.append((float(d @ s), float(d @ u), TIE_DISC))
    return sorted(hits)[:1] + sorted(hits)[-1:] if len(hits) >= 2 else []


def _on_facets(pts, o, t):
    """Where a faceted bundle centreline crosses the strap's station plane (through o, normal t): between two facet
    radials the chord lies up to a few mm inside the plan's arc, and the band must hug the built bundle. None ->
    the plan's point o."""
    o, t = np.asarray(o, float), np.asarray(t, float)
    if pts is None:
        return o
    d = (np.asarray(pts, float) - o) @ t
    best = None
    for i in range(len(d) - 1):
        if d[i] * d[i + 1] <= 0 and d[i] != d[i + 1]:
            q = pts[i] + (pts[i + 1] - pts[i]) * (d[i] / (d[i] - d[i + 1]))
            if best is None or np.linalg.norm(q - o) < np.linalg.norm(best - o):
                best = q
    return o if best is None or np.linalg.norm(best - o) > 0.02 else best


def _under_deck(plan, o):
    """Whether a strap station lies under a crossover saddle's deck (the a-b straps in the Cross: the deck clears
    their bands by 1.5 mm, so they carry no buckle there)."""
    for f in plan.fittings:
        if f.kind == "crossover_saddle":
            d = np.asarray(o, float) - np.asarray(f.frame.o, float)
            if abs(d @ f.frame.t) <= f.size[0] / 2 and abs(d @ f.frame.s) <= f.size[1] / 2 and \
                    d @ f.frame.u < f.params["deck_top"]:
                return True
    return False


def strap(P, at, discs, lod, buckle=True):
    """One strap band at station frame `at` = (o, t, s, u) round the discs [(s, h, r)] (one bundle, or a nested
    group), with a cinch buckle on top at LOD0 (none under a saddle's deck)."""
    o, t, s, u = (np.asarray(v, float) for v in at)
    # the band bites into the cables (the strap cinches the bundle): its outline lies STRAP_BITE inside the bundle
    poly = XS.band_outline(discs, -XS.STRAP_BITE if lod == 0 else TL.STRAP_T,
                           sides=8 if lod == 0 else 6)
    T, S, U = Vector(t), Vector(s), Vector(u)
    # the sweep's s axis must be u x t: the station's s is, by the plan's construction (Frame(o, t, s, t x s))
    Sx = U.cross(T)
    flip = Sx.dot(S) < 0
    prof = [((-a if flip else a), b) for a, b in poly]
    if flip:
        prof = prof[::-1]
    pts = [Vector(o) - T * (TL.STRAP_W / 2), Vector(o) + T * (TL.STRAP_W / 2)]
    sweep(P["tie"], pts, prof, TIE, closed=True, smooth=False, fr=[(T, Sx, U)] * 2)
    if lod == 0 and buckle:
        top = max(prof, key=lambda q: q[1])
        bl, bw, bt = BUCKLE
        rect = [(top[0] - bw / 2, top[1]), (top[0] + bw / 2, top[1]), (top[0] + bw / 2, top[1] + bt),
                (top[0] - bw / 2, top[1] + bt)]
        sweep(P["tiehw"], [Vector(o) - T * (bl / 2), Vector(o) + T * (bl / 2)], rect, TRAY_HW, closed=True, cap0=True,
              cap1=True, smooth=False, fr=[(T, Sx, U)] * 2)


# ---------------------------------------------------------------------------------------------------- supports
CHANNEL = dict(wall=0.0025, lip_in=0.007, lip_down=0.005, chamfer=0.002)
CAP_BOLT = dict(r=0.006, h=0.002, dx=0.0)            # one bolt head on each Yellow end cap
WASHER = (0.018, 0.003)                               # square strut washer: side, thick
NUT = dict(r=0.0085, h=0.008)                         # hex nut on the washer (across corners 17 mm)
PLATE_BOLT = dict(r=0.0055, h=0.0025, d=0.010)        # 2 square bolt heads under each rod plate (ceiling anchors)


def _channel_profile(w, h):
    """The lipped strut channel's section (counter-clockwise, centred): opening up, lips turned in and down."""
    c, t, li, ld = CHANNEL["chamfer"], CHANNEL["wall"], CHANNEL["lip_in"], CHANNEL["lip_down"]
    a, b = w / 2, h / 2
    right = [(a - c, -b), (a, -b + c), (a, b), (a - li, b), (a - li, b - ld), (a - t, b - ld), (a - t, -b + t)]
    left = [(-x, y) for x, y in reversed(right)]
    return right + left


def _solid_frame(fr):
    """A plan Frame -> sweep frame vectors (T, S, U) with S = U x T."""
    T, U = Vector(fr.t), Vector(fr.u)
    return T, U.cross(T), U


def support(P, sp, lod):
    if sp.kind in ("trapeze", "floor_strut"):
        trapeze(P, sp, lod)
    elif sp.kind == "rods":
        rods(P, sp, lod)
    elif sp.kind == "ladder":
        ladder(P, sp, lod)


def trapeze(P, sp, lod):
    """A strut-channel trapeze (or a floor strut, without rods): the channel under the basket, Yellow end caps on
    1 mm-inset end plates, and (trapeze) two threaded rods up to rod-coupler plates under the top plane."""
    sol = {}
    for name, fr, size, m in sp.solids():
        sol.setdefault(name, []).append((fr, size, m))
    fr, size, _ = sol["strut"][0]
    T, S, U = _solid_frame(fr)
    o = Vector(fr.o)
    half = size[0] / 2
    w, h = size[1], size[2]
    cap_in = TP.STRUT_CAP + 0.002 if lod == 0 else TP.STRUT_CAP     # LOD0: the cap's face 2 mm in, bolt heads proud
    a0, a1 = o - T * (half - cap_in), o + T * (half - cap_in)
    if lod == 0:
        sweep(P["strut"], [a0, a1], _channel_profile(w, h), TIE, closed=True, smooth=False, fr=[(T, S, U)] * 2)
    elif lod == 1:
        sweep(P["strut"], [a0, a1], G.clipped_rect(w / 2, h / 2, 0.0), TIE, closed=True, smooth=False,
              fr=[(T, S, U)] * 2)
    else:
        prof = [(-w / 2, h / 2), (-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2)]
        sweep(P["strut"], [o - T * half, o + T * half], prof, TIE, closed=False, smooth=False,
              fr=[(T, S, U)] * 2)
        return
    for sg in (-1, 1):            # the end caps, outward along the strut axis
        Te = T * sg
        Se = U.cross(Te)
        e = o + T * (sg * half)
        c0 = e - Te * cap_in
        c1 = e - Te * (cap_in - TP.STRUT_CAP)
        if lod == 0:
            sweep(P["trim"], [c0, c1], G.clipped_rect(w / 2, h / 2, 0.004), YELLOW, closed=True, cap1=True, smooth=False,
                  fr=[(Te, Se, U)] * 2)
            for dx in (0.0,):     # one large bolt per cap (fewer, larger fasteners)
                hexnut(P["hw"], c1 + Se * dx, Te, CAP_BOLT["r"], CAP_BOLT["h"], TRAY_HW)
        else:   # LOD1: the cap's end face only (the channel's walls carry on to it)
            bm = P["trim"].bm
            q = [c1 + Se * a + U * b for a, b in G.clipped_rect(w / 2, h / 2, 0.0)]
            bm.faces.new([bm.verts.new(v) for v in q]).material_index = P["trim"].mi(YELLOW)
    if not sp.rods:
        return
    top_strut = o + U * (h / 2)
    for (lo, hi), (pfr, psize, _) in zip(sp.rods, sol.get("rod_plate", [])):
        lo, hi = Vector(lo), Vector(hi)
        d = (hi - lo).normalized()
        base = lo + d * CHANNEL["wall"]
        plate_bot = hi - d * TP.ROD_PLATE_T
        sweep(P["hw"], [base, plate_bot], wire_profile(TL.ROD_R, lod), TRAY_HW, closed=True, up=T)
        pc = Vector(pfr.o)
        pl, _, pt = psize
        box_open(P["hw"], tuple(pc - Vector((pl / 2, pl / 2, pt / 2))), tuple(pc + Vector((pl / 2, pl / 2, pt / 2))),
                 TRAY_HW, skip=("+z",) if lod > 0 else ())
        if lod > 0:
            continue
        # the square strut washer and the hex nut on the channel's lips
        z0 = float(top_strut.dot(d))
        c = lo + d * (z0 - lo.dot(d))
        ws, wt = WASHER
        box_open(P["hw"], (c.x - ws / 2, c.y - ws / 2, c.z), (c.x + ws / 2, c.y + ws / 2, c.z + wt), TRAY_HW,
                 skip=("-z",))
        hexnut(P["hw"], c + d * wt, d, NUT["r"], NUT["h"], TRAY_HW)
        # the plate's two anchor bolt heads (it bolts to the structure above; the rod threads into the plate's boss)
        for i, j in ((-1, -1), (1, 1)):          # two diagonal anchor bolts (fewer, larger fasteners)
            q = plate_bot + Vector((i * PLATE_BOLT["d"], j * PLATE_BOLT["d"], 0.0))
            hexnut(P["hw"], q, -d, PLATE_BOLT["r"], PLATE_BOLT["h"], TRAY_HW, sides=4, phase=math.pi / 4)


# --------------------------------------------------------------------------------------- Chute, Drop and hanger helpers
def _v3(q):
    return Vector((float(q[0]), float(q[1]), float(q[2])))


def _oface(p, material, pts, outward):
    """One face on pts, wound so that its normal points along `outward` (the decal Parts keep the authored winding,
    so every such face states which way it faces)."""
    bm = p.bm
    f = bm.faces.new([bm.verts.new(_v3(q)) for q in pts])
    f.material_index = p.mi(material)
    f.normal_update()
    if f.normal.dot(_v3(outward)) < 0:
        f.normal_flip()
    return f


def _cap(p, material, pts, outward):
    """An end cap (any simple polygon, concave too), triangulated."""
    f = _oface(p, material, pts, outward)
    bmesh.ops.triangulate(p.bm, faces=[f])


def _outward_2d(prof):
    """Per edge i -> i+1 of a closed 2D polygon, its outward normal (any winding)."""
    area = sum(a0 * b1 - a1 * b0 for (a0, b0), (a1, b1) in zip(prof, prof[1:] + prof[:1]))
    out = []
    for (a0, b0), (a1, b1) in zip(prof, prof[1:] + prof[:1]):
        da, db = a1 - a0, b1 - b0
        out.append((db, -da) if area > 0 else (-db, da))
    return out


def _extrude(p, material, prof, o, ea, eb, el, length, caps=(True, True)):
    """A prism: the closed 2D polygon prof [(a, b)] in the plane (ea, eb) through o, extruded along el for `length`;
    side quads facing out of the polygon, end caps (concave-safe) facing -el / +el (caps: which to build)."""
    o, ea, eb, el = (np.asarray(v, float) for v in (o, ea, eb, el))
    r0 = [o + a * ea + b * eb for a, b in prof]
    r1 = [q + length * el for q in r0]
    n = len(prof)
    for i, (na, nb) in enumerate(_outward_2d(list(prof))):
        j = (i + 1) % n
        _oface(p, material, [r0[i], r0[j], r1[j], r1[i]], na * ea + nb * eb)
    if caps[0]:
        _cap(p, material, r0, -el)
    if caps[1]:
        _cap(p, material, r1, el)


def _box(p, material, o, axes, size, skip=()):
    """A box centred at o on the unit axes (e0, e1, e2) with full sizes; skip: faces left out, as "-0", "+2", ..."""
    o = np.asarray(o, float)
    E = [np.asarray(e, float) for e in axes]
    h = [s / 2 for s in size]
    for k in range(3):
        i, j = [m for m in range(3) if m != k]
        for sg in (-1, 1):
            if f"{'-' if sg < 0 else '+'}{k}" in skip:
                continue
            c = o + sg * h[k] * E[k]
            q = [c + a * h[i] * E[i] + b * h[j] * E[j] for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            _oface(p, material, q, sg * E[k])


def _holed_plate(p, material, o, n, e1, rect, hole, r_hole, t, segs, bottom=True):
    """A plate t thick whose bottom face lies on the plane through o (unit normal n), its outer rectangle rect =
    (a0, a1, b0, b1) in (e1, e2 = n x e1) and a round bore of radius r_hole at hole = (a, b): the top annulus
    (rectangle <-> circle, rays from the bore's centre, the four corners included), the bore wall, the outer walls
    and (optionally) the bottom."""
    o, n, e1 = (np.asarray(v, float) for v in (o, n, e1))
    e2 = np.cross(n, e1)
    a0, a1, b0, b1 = rect
    ca, cb = hole
    corners = [(a1, b1), (a0, b1), (a0, b0), (a1, b0)]
    angs = sorted({round(2 * math.pi * k / segs + math.pi / segs, 9) for k in range(segs)} |
                  {round(math.atan2(y - cb, x - ca) % (2 * math.pi), 9) for x, y in corners})

    def edge(th):
        d = (math.cos(th), math.sin(th))
        ts = [v for v in ((a1 - ca) / d[0] if d[0] > 1e-12 else None, (a0 - ca) / d[0] if d[0] < -1e-12 else None,
                          (b1 - cb) / d[1] if d[1] > 1e-12 else None, (b0 - cb) / d[1] if d[1] < -1e-12 else None)
              if v is not None]
        k = min(ts)
        return ca + k * d[0], cb + k * d[1]
    P2 = lambda a, b, z: o + a * e1 + b * e2 + z * n     # noqa: E731
    for k in range(len(angs)):
        th0, th1 = angs[k], angs[(k + 1) % len(angs)]
        if th1 <= th0:
            th1 += 2 * math.pi
        i0 = (ca + r_hole * math.cos(th0), cb + r_hole * math.sin(th0))
        i1 = (ca + r_hole * math.cos(th1), cb + r_hole * math.sin(th1))
        o0, o1 = edge(th0), edge(th1)
        for z, sg in ((t, 1), (0.0, -1)) if bottom else ((t, 1),):
            _oface(p, material, [P2(*i0, z), P2(*o0, z), P2(*o1, z), P2(*i1, z)], sg * n)
        mid = (th0 + th1) / 2
        _oface(p, material, [P2(*i0, 0.0), P2(*i1, 0.0), P2(*i1, t), P2(*i0, t)],
               -(math.cos(mid) * e1 + math.sin(mid) * e2))
    for (xa, ya), (xb, yb), out in (((a0, b0), (a1, b0), -e2), ((a1, b0), (a1, b1), e1), ((a1, b1), (a0, b1), e2),
                                    ((a0, b1), (a0, b0), -e1)):
        _oface(p, material, [P2(xa, ya, 0.0), P2(xb, yb, 0.0), P2(xb, yb, t), P2(xa, ya, t)], out)


def _bristles(p, material, c, axis, e1, r_root, z_root, r_tip, z_tip, n, fill=0.78):
    """A ring of n bristle tufts parting round a bundle: each one quad from the bore (r_root, z_root along axis from
    c) in and down to the bundle (r_tip, z_tip), facing up and in (the side seen from above); ragged tips, a gap
    between tufts (the dark bore shows through as strand lines, as the racks' brush plates do)."""
    c, axis, e1 = (np.asarray(v, float) for v in (c, axis, e1))
    e2 = np.cross(axis, e1)
    dr, dz = r_root - r_tip, z_root - z_tip
    for k in range(n):
        th0 = 2 * math.pi * k / n
        th1 = th0 + 2 * math.pi * fill / n
        rag = 0.0007 * ((k * 5) % 3 - 1)
        d0, d1 = (math.cos(th0) * e1 + math.sin(th0) * e2), (math.cos(th1) * e1 + math.sin(th1) * e2)
        q = [c + axis * z_root + r_root * d0, c + axis * z_root + r_root * d1,
             c + axis * (z_tip + rag) + r_tip * d1, c + axis * (z_tip + rag) + r_tip * d0]
        dm = (d0 + d1) / np.linalg.norm(d0 + d1)
        _oface(p, material, q, -dz * dm + dr * axis)


# ---------------------------------------------------------------------------------------------------- rod hangers
ANCHOR_BOLT = dict(r=0.004, h=0.0025, dx=0.025, dy=0.010)   # 4 anchor bolts under each ceiling plate (outside the
#                                                             channel: x +-25 mm, y +-10 mm about the rod)


def rods(P, sp, lod):
    """A rod hanger (DC_TrayRods): per rod a square washer the tray's rod-plate size and the 22 mm hex coupler
    nut on it (it takes the tray's rod at the plate), the threaded rod up through the Darker ceiling strut channel (a
    square washer and a hex channel nut under its lips hold it) to a Darker ceiling anchor plate with four anchor
    bolts; the channel's Yellow end caps as the trapeze's. LOD1: plain prisms, no nuts or bolts."""
    sol = sp.solids()
    across = np.asarray(sp.params["across"], float)
    cfr, csize = next((fr, size) for name, fr, size, _ in sol if name == "channel")
    for name, fr, size, _ in sol:
        o, t, s, u = (np.asarray(v, float) for v in (fr.o, fr.t, fr.s, fr.u))
        a, b, c = size
        if name == "washer":                       # its underside lies on the rod plate below
            _box(P["hw"], TRAY_HW, o, (t, s, u), size, skip=("-2",))
        elif name == "coupler":
            hexnut(P["hw"], o - u * (c / 2), u, TP.COUPLER_R, c, TRAY_HW, sides=6 if lod == 0 else 4,
                   phase=math.pi / 6 if lod == 0 else math.pi / 4)
        elif name == "anchor_plate":               # its top lies against the ceiling
            _box(P["strut"], TIE, o, (t, s, u), size, skip=("+2",))
            if lod == 0:
                B = ANCHOR_BOLT
                for i in (-1, 1):
                    for j in (-1, 1):
                        q = o - u * (c / 2) + t * (i * B["dx"]) + s * (j * B["dy"])
                        hexnut(P["hw"], q, -u, B["r"], B["h"], TRAY_HW, sides=6)
        elif name == "channel":                    # the lipped channel, opening down (rods through its slot)
            prof = _channel_profile(b, c) if lod == 0 else G.clipped_rect(b / 2, c / 2, 0.0)
            prof = [(x, -y) for x, y in prof]
            _extrude(P["strut"], TIE, prof, o - t * (a / 2), s, u, t, a, caps=(False, False))
        elif name == "end_cap":     # (LOD0: the cap set in by its bolt head, which ends on the 1 mm-inset plane)
            out = t if (o - np.asarray(cfr.o, float)) @ t > 0 else -t
            back = CAP_BOLT["h"] if lod == 0 else 0.0
            c0 = o - out * (a / 2 + back)
            prof = G.clipped_rect(b / 2, c / 2, 0.004 if lod == 0 else 0.0)
            _extrude(P["trim"], YELLOW, prof, c0, s, u, out, a, caps=(False, True))
            if lod == 0:
                hexnut(P["hw"], c0 + out * a, out, CAP_BOLT["r"], CAP_BOLT["h"], TRAY_HW)
    if lod >= 2:
        return
    cbot = np.asarray(cfr.o, float) - np.asarray(cfr.u, float) * (csize[2] / 2)     # the channel lips' underside
    aw, al, at = sp.params["anchor"]
    for lo, hi in sp.rods:
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        d = (hi - lo) / np.linalg.norm(hi - lo)
        base = lo + d * (TP.WASHER_T + TP.COUPLER_L)
        top = hi - d * at
        sweep(P["hw"], [_v3(base), _v3(top)], wire_profile(TL.ROD_R, lod), TRAY_HW, closed=True, up=_v3(across))
        if lod == 0:   # the channel nut: a square washer and a hex nut under the lips
            z = float((cbot - lo) @ d)
            q = lo + d * z
            ws, wt = WASHER
            s_ = np.cross(d, across)
            _box(P["hw"], TRAY_HW, q - d * (wt / 2), (across, s_, d), (ws, ws, wt), skip=("+2",))
            hexnut(P["hw"], q - d * wt, -d, NUT["r"], NUT["h"], TRAY_HW)


# ---------------------------------------------------------------------------------------------------- the Chute ladder
LADDER_C = dict(t=0.0025, lip=0.004)       # the rails' lipped C section: wall, lip depth


def _rail_profile(w, d, lod):
    """A Chute ladder rail's section (p = across, outward from the bundle; q = toward), a lipped C: its web towards
    the bundle (the cables lie against a smooth face), the flanges and lips turned outward. LOD1: a plain bar."""
    if lod > 0:
        return [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    t, lip = LADDER_C["t"], LADDER_C["lip"]
    a, b = w / 2, d / 2
    return [(-a, -b), (a, -b), (a, -b + lip), (a - t, -b + lip), (a - t, -b + t), (-a + t, -b + t),
            (-a + t, b - t), (a - t, b - t), (a - t, b - lip), (a, b - lip), (a, b), (-a, b)]


def ladder(P, sp, lod):
    """The Chute's cable ladder: two Brushed lipped-C rails standing on a Darker foot plate (seated over the
    half rack's roof brush, its bore lined with bristles that part round the bundle), Brushed rungs every 0.25 m
    between the rails' webs (the bundle strapped to each: dc/tray_kit.straps), and a Brushed top clamp plate across
    the rail heads (welded to them, flush under the top plane: its bore takes the bundle, the clamp under it grips
    it, the Drop's landing collar sits on it)."""
    a, c, w = (np.asarray(v, float) for v in (sp.axis, sp.params["across"], sp.params["toward"]))
    rails, rungs = sp.ladder()
    (rw, rd), (ll, lt, lh) = sp.params["rail"], sp.params["rung"]
    bpos = np.asarray(sp.position, float) + w * sp.params["bundle_at"]
    for lo, hi in rails:
        lo, hi = np.asarray(lo, float), np.asarray(hi, float)
        side = 1.0 if (lo - bpos) @ c > 0 else -1.0
        L = float(np.linalg.norm(hi - lo))
        _extrude(P["hw"], TRAY_HW, _rail_profile(rw, rd, lod), lo, side * c, w, a, L, caps=(False, False))
    inner = sp.params["rail_dx"] - rw / 2            # the rungs run between the rails' webs
    for r in rungs:
        r = np.asarray(r, float)
        if lod == 0:
            _extrude(P["hw"], TRAY_HW, G.clipped_rect(lt / 2, lh / 2, 0.002), r - c * inner, w, a, c, 2 * inner,
                     caps=(False, False))
        else:          # LOD1: the rung's front and back faces
            for sg in (-1, 1):
                q = [r + sg * w * (lt / 2) + c * (i * inner) + a * (j * lh / 2) for i, j in ((-1, -1), (1, -1),
                                                                                             (1, 1), (-1, 1))]
                _oface(P["hw"], TRAY_HW, q, sg * w)
    if lod >= 2:
        return
    if lod == 1:       # the plates as plain slabs (top and sides)
        for part, mat in (("foot_plate", TIE), ("top_plate", TRAY_HW)):
            fr, size = sp.ladder_plate(part)
            _box(P["guide" if mat == TIE else "hw"], mat, fr.o, (fr.t, fr.s, fr.u), size, skip=("-0",))
        return
    for part, mat, hole, bottom in (("foot_plate", TIE, sp.params["foot_hole"], False),
                                    ("top_plate", TRAY_HW, sp.params["top_hole"], True)):
        fr, (th, sa, sw) = sp.ladder_plate(part)
        o = np.asarray(fr.o, float) - a * (th / 2)
        hc = ((bpos - o) @ c, (bpos - o) @ w)
        _holed_plate(P["guide" if mat == TIE else "hw"], mat, o, a, c, (-sa / 2, sa / 2, -sw / 2, sw / 2), hc, hole, th,
                     16 if lod == 0 else 8, bottom=bottom)
        if lod > 0:
            continue
        if part == "foot_plate":     # the bore's brush: tufts from the bore's rim down onto the bundle
            ctr = o + c * hc[0] + w * hc[1]
            _bristles(P["guide"], TIE, ctr, a, c, hole, th - 0.001, TL.R_WF + 0.0003, 0.0015, 16)


# ---------------------------------------------------------------------------------------------------- fittings
def _sleeve(p, fr, r, length, material, lod, ends=True, sides=10):
    """A sleeve (collar, band) of outer radius r round the t axis of `fr` (o, t, s, u as numpy), `length` long,
    with annular end faces 1 wall in (they read as a thick part)."""
    T, U = Vector(fr[1]), Vector(fr[3])
    S = U.cross(T)
    o = Vector(fr[0])
    n = sides if lod == 0 else max(4, sides // 2)
    prof = ngon(r / math.cos(math.pi / n), n, math.pi / n)
    rings = sweep(p, [o - T * (length / 2), o + T * (length / 2)], prof, material, closed=True, smooth=True,
                  fr=[(T, S, U)] * 2)
    if ends and lod == 0:
        bm = p.bm
        mi = p.mi(material)
        for ring, sgn in ((rings[0], -1), (rings[1], 1)):
            c = o + T * (sgn * length / 2)
            inner = [bm.verts.new(c + (v.co - c) * (1 - TL.STRAP_T / r)) for v in ring]
            for k in range(n):
                j = (k + 1) % n
                q = (ring[k], ring[j], inner[j], inner[k]) if sgn > 0 else (ring[j], ring[k], inner[k], inner[j])
                bm.faces.new(q).material_index = mi


def _prism(p, a, b, frame, profile, material, smooth=False, caps=(True, True)):
    """A closed (possibly concave) profile [(s, u)] in `frame` = (T, S, U) swept straight from a to b, its end caps
    triangulated (polyfill: concave caps stay inside their outline)."""
    rings = sweep(p, [a, b], profile, material, closed=True, smooth=smooth, fr=[frame] * 2)
    bm = p.bm
    mi = p.mi(material)
    for ring, want in ((rings[0], caps[0]), (rings[1], caps[1])):
        if not want:
            continue
        f = bm.faces.new(list(reversed(ring)) if ring is rings[0] else ring)
        f.material_index = mi
        bmesh.ops.triangulate(bm, faces=[f])
    return rings


COLLAR = dict(gap=0.0015, ear=0.010, ear_t=0.003, bolt_r=0.0042, bolt_h=0.003)


def _collar_half(ri, ro, g, n=6):
    """One half shell of a split collar (the top half; the bottom one mirrors in u): an arch from the split plane
    (u = g) over the bundle, inner radius ri, outer ro, with a flat ear each side (out to ro + ear, ear_t thick) that
    the clamp bolts pass through. Counter-clockwise."""
    e, et = COLLAR["ear"], COLLAR["ear_t"]
    a0 = math.asin((g + et) / ro)
    outer = [(ro * math.cos(a), ro * math.sin(a)) for a in np.linspace(a0, math.pi - a0, n + 1)]
    b0 = math.asin(g / ri)
    inner = [(ri * math.cos(a), ri * math.sin(a)) for a in np.linspace(math.pi - b0, b0, n + 1)]
    return ([(ro + e, g), (ro + e, g + et)] + outer + [(-(ro + e), g + et), (-(ro + e), g)] + inner)


def split_collar(P, f, lod):
    """A Darker split collar where a branch bundle leaves its parent (it holds the split): two half shells clamped
    round the bundle, their flat ears bolted together each side (a bolt head on the top ear, its nut under the
    bottom one). LOD0 only (a 3 cm part; the bundles dressed over it are dressed at LOD0 only too). Not drawn when
    the plan marks it hidden (the Full Drop's split collars lie wholly inside its dressed top layer and
    the nest of bundles round L1+; 400 triangles nobody sees)."""
    if lod >= 1 or f.params.get("hidden"):
        return
    fr = (f.frame.o, f.frame.t, f.frame.s, f.frame.u)
    T, U = Vector(fr[1]), Vector(fr[3])
    S = U.cross(T)
    o = Vector(fr[0])
    ro = f.size[1] / 2
    ri = ro - TP.COLLAR_T
    g = COLLAR["gap"]
    a, b = o - T * (f.size[0] / 2), o + T * (f.size[0] / 2)
    half = _collar_half(ri, ro, g)
    for sg in (1, -1):         # the top half, then the bottom one (mirrored in u: reversed to stay counter-clockwise)
        prof = half if sg > 0 else [(x, -y) for x, y in reversed(half)]
        _prism(P["tie"], a, b, (T, S, U), prof, TIE)
    x = ro + COLLAR["ear"] / 2
    top = g + COLLAR["ear_t"]
    for k in (-1, 1):          # the clamp bolts: head on the top ear, nut under the bottom ear
        c = o + S * (k * x)
        hexnut(P["tiehw"], c + U * top, U, COLLAR["bolt_r"], COLLAR["bolt_h"], TRAY_HW)
        hexnut(P["tiehw"], c - U * top, -U, COLLAR["bolt_r"], COLLAR["bolt_h"], TRAY_HW)


def boot(P, f, lod):
    """A Rubber end boot over a dropped bundle's end (a sealed spare): a sleeve with a rounded, closed tip."""
    if lod >= 2:
        return
    o, T, U = Vector(f.frame.o), Vector(f.frame.t), Vector(f.frame.u)
    S = U.cross(T)
    r, L = f.params["radius"], f.size[0]
    n = 10 if lod == 0 else 6
    a = o - T * (L / 2)
    pts = [a, a + T * (L - 0.010), a + T * (L - 0.003), a + T * L]
    fr = [(T, S, U)] * 4
    rings = []
    bm = P["cable"].bm
    mi = P["cable"].mi(RUBBER)
    lay, rid = G.round_id(bm)
    for q, k in zip(pts, (1.0, 1.0, 0.82, 0.45) if lod == 0 else (1.0, 1.0, 0.75, 0.3)):
        R = r * k / math.cos(math.pi / n)
        rings.append([bm.verts.new(q + S * (R * math.cos(math.pi / n + 2 * math.pi * j / n)) +
                                   U * (R * math.sin(math.pi / n + 2 * math.pi * j / n))) for j in range(n)])
    if lod > 0:
        rings = [rings[0], rings[1], rings[3]]
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(n):
            jj = (j + 1) % n
            fc = bm.faces.new((r0[j], r0[jj], r1[jj], r1[j]))
            fc.material_index = mi
            fc[lay] = rid
    bm.faces.new(rings[-1]).material_index = mi


def saddle_clamp(P, f, lod):
    """A Darker saddle clamp: a band round the boot's body on a post standing from the floor (strain relief)."""
    if lod >= 1:
        return
    fr = f.frame
    o, T, U = np.asarray(fr.o, float), np.asarray(fr.t, float), np.asarray(fr.u, float)
    c0 = o + f.params["band_dz"] * U
    _sleeve(P["tie"], (c0, T, fr.s, U), f.params["band_r"], f.size[0], TIE, lod, sides=10)
    ph, w = f.params["post_h"], f.params["post_hw"]
    if ph > 0:
        top = c0 - (f.params["band_r"] - TL.STRAP_T) * U
        base = top - ph * U
        Tv, Uv = Vector(T), Vector(U)
        Sv = Uv.cross(Tv)
        l2 = f.size[0] / 2
        # sweep up the post: t = the post axis (U), u = the bundle axis (T), s = u x t = -S
        sweep(P["tie"], [Vector(base), Vector(top)], [(-w, -l2), (w, -l2), (w, l2), (-w, l2)], TIE, closed=True,
              cap0=True, smooth=False, fr=[(Uv, -Sv, Tv)] * 2)


def tag(P, f, lod):
    """A Yellow density tag clipped to the outside of a wall, with its white stencil ("F>M": from the a side's
    density to the b side's). On the +y wall it reads "M<F" (its reading direction runs from b to a there)."""
    if lod >= 2:
        return
    o, T, S, U = (Vector(v) for v in (f.frame.o, f.frame.t, f.frame.s, f.frame.u))
    L, th, H = f.size
    out = S.normalized()            # the tag's frame s points away from the tray (plan: k * Y)
    Ue = U.normalized()
    # a prism through the tag's thickness: sweep t = outward, u = up, s = u x t (along the tray)
    prof = G.clipped_rect(L / 2, H / 2, 0.006 if lod == 0 else 0.0)
    sweep(P["trim"], [o - out * (th / 2), o + out * (th / 2)], prof, YELLOW, closed=True, cap1=True,
          cap0=lod == 0, smooth=False, fr=[(out, Ue.cross(out), Ue)] * 2)
    if lod > 0:
        return
    # the stencil on the outer face: its reading axis a with a x up = outward, i.e. a = up x outward
    F = G.Face(o + out * (th / 2), Ue.cross(out), Ue)
    text = f.params["text"]
    plus_y = out.y > 0
    if plus_y:
        text = text[::-1].replace(">", "<")
    _stencil(P["stencil"], F, text, 0.024)


def _stencil(p, F, text, cap):
    """White stencil text centred on face F; '>' and '<' are drawn as chevrons of two dash strokes."""
    s = cap / DC.CAP_PX
    x0d, y0d, x1d, y1d = DC.GLYPHS["-"]
    widths = []
    for ch in text:
        if ch in "<>":
            widths.append(0.55 * cap)
        else:
            gx0, _, gx1, _ = DC.GLYPHS[ch]
            widths.append((gx1 - gx0) * s)
    track = 0.18 * cap
    total = sum(widths) + track * (len(text) - 1)
    x = -total / 2
    for ch, w in zip(text, widths):
        if ch in "<>":
            sg = 1 if ch == ">" else -1
            lw = 0.13 * cap                        # stroke thickness
            ln = math.hypot(w, cap / 2)
            for k in (1, -1):                      # the two strokes of the chevron
                ang = math.atan2(-k * cap / 2, sg * w)
                cx, cy = x + w / 2, k * cap / 4
                ca, sa = math.cos(ang), math.sin(ang)
                hl, hw = ln / 2, lw / 2
                corners = [(cx - ca * hl + sa * hw, cy - sa * hl - ca * hw), (cx + ca * hl + sa * hw, cy + sa * hl - ca * hw),
                           (cx + ca * hl - sa * hw, cy + sa * hl + ca * hw), (cx - ca * hl - sa * hw, cy - sa * hl + ca * hw)]
                u0, u1, v0, v1 = x0d / 1024, x1d / 1024, 1 - y1d / 1024, 1 - y0d / 1024
                DC._quad(p, F, corners, 0.0, STENCIL_WHITE, ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))
        else:
            gx0, gy0, gx1, gy1 = DC.GLYPHS[ch]
            gh = (gy1 - gy0) * s
            u0, u1, v0, v1 = gx0 / 1024, gx1 / 1024, 1 - gy1 / 1024, 1 - gy0 / 1024
            DC._quad(p, F, [(x, -gh / 2), (x + w, -gh / 2), (x + w, gh / 2), (x, gh / 2)], 0.0, STENCIL_WHITE,
                     ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))
        x += w + track


def _guide_profile(f, lod):
    """The guide's section across the arc (a = along the frame's t, the waterfall's x; b = radially out from the rib
    crests at r_top): LOD0 the moulded trough, its plate (top between the ribs rib_h under the crests) between two
    cheeks standing cheek_h over the crests; LOD1 the plate alone."""
    W, th = f.params["width"], f.params["thickness"]
    (ct, ch), (rh, _, _) = f.params["cheek"], f.params["rib"]
    a = W / 2
    if lod > 0:
        return [(-a, -th), (a, -th), (a, -rh), (-a, -rh)]
    return [(-a, -th), (a, -th), (a, ch), (a - ct, ch), (a - ct, -rh), (-a + ct, -rh), (-a + ct, ch), (-a, ch)]


def waterfall_guide(P, f, lod):
    """The waterfall's moulded radius guide: a Darker trough on the 0.10 m bend radius from 20 deg inside
    the tray round to plumb, its plate ribbed across (the bundle rides the rib crests) between two side cheeks that
    keep the bundle on the radius; two Brushed spring clamps hook it over the front wall's safety-edge wire.
    LOD1: the plate on 3 chords; LOD2: the plate's top as a strip on 2 chords."""
    Pp = f.params
    c = np.asarray(Pp["centre"], float)
    T, S, U = (np.asarray(v, float) for v in (f.frame.t, f.frame.s, f.frame.u))
    lo, hi = Pp["angles"]
    r1, th, W = Pp["r_top"], Pp["thickness"], Pp["width"]
    rad = lambda psi: math.sin(psi) * S + math.cos(psi) * U          # noqa: E731
    tan = lambda psi: math.cos(psi) * S - math.sin(psi) * U          # noqa: E731
    n = (8, 3, 2)[min(lod, 2)]
    psis = np.linspace(lo, hi, n + 1)
    p = P["guide"]
    if lod >= 2:          # the plate's top as a strip (the trough's silhouette over the wall at range)
        rh = Pp["rib"][0]
        for k in range(n):
            a_, b_ = psis[k], psis[k + 1]
            q = [c + x * T + (r1 - rh) * rad(ps) for ps, x in ((a_, -W / 2), (a_, W / 2), (b_, W / 2), (b_, -W / 2))]
            _oface(p, TIE, q, rad((a_ + b_) / 2))
        return
    prof = _guide_profile(f, lod)
    rings = [[c + a * T + (r1 + b) * rad(ps) for a, b in prof] for ps in psis]
    outs = _outward_2d(prof)
    m = len(prof)
    for k in range(n):
        mid = (psis[k] + psis[k + 1]) / 2
        for i, (na, nb) in enumerate(outs):
            j = (i + 1) % m
            _oface(p, TIE, [rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]], na * T + nb * rad(mid))
    if lod > 0:           # (LOD1: the plate's open ends are not seen at range)
        return
    _cap(p, TIE, rings[0], -tan(lo))
    _cap(p, TIE, rings[-1], tan(hi))
    (ct, _), (rh, rw, rp) = Pp["cheek"], Pp["rib"]
    da = (rw / 2) / r1
    x0, x1 = -W / 2 + ct, W / 2 - ct
    for ps in np.arange(lo + rp / 2, hi - rp / 4, rp):            # the ribs across the plate, crests at r_top
        a_, b_ = ps - da, ps + da
        q = lambda psi, r, x: c + x * T + r * rad(psi)             # noqa: E731
        _oface(p, TIE, [q(a_, r1, x0), q(a_, r1, x1), q(b_, r1, x1), q(b_, r1, x0)], rad(ps))
        _oface(p, TIE, [q(a_, r1 - rh, x0), q(a_, r1 - rh, x1), q(a_, r1, x1), q(a_, r1, x0)], -tan(a_))
        _oface(p, TIE, [q(b_, r1 - rh, x0), q(b_, r1 - rh, x1), q(b_, r1, x1), q(b_, r1, x0)], tan(b_))
    cw, cth = Pp["clamp"]
    path = TP.guide_clamp_path(f, n=5)
    rect = [(-cth / 2, -cw / 2), (cth / 2, -cw / 2), (cth / 2, cw / 2), (-cth / 2, cw / 2)]
    for dx in Pp["clamps"]:                                         # the spring clips hooked on the edge wire
        pts = [_v3(c + dx * T + s_ * S + h * U) for s_, h in path]
        sweep(P["hw"], pts, rect, TRAY_HW, closed=True, cap0=True, cap1=True, up=_v3(T), smooth=False)


def brush_collar(P, f, lod):
    """The landing brush collar: a Darker ring seated on the rack's brush plate (or the Chute's top plate)
    round the waterfall, chamfered on top, two screws into the plate's frame; its bore lined with bristle tufts that
    part round the bundle. LOD0 only (a 7 cm part on the rack top: the bundle's end reads at range)."""
    if lod >= 1:
        return
    A, E1, E2 = (np.asarray(v, float) for v in (f.frame.t, f.frame.s, f.frame.u))
    o = np.asarray(f.frame.o, float)
    h, r_out = f.size[0], f.size[1] / 2
    rb, rbun = f.params["r_bore"], f.params["r_bundle"]
    z0, z1 = -h / 2, h / 2
    ch = 0.0015 if lod == 0 else 0.0
    n = 12 if lod == 0 else 8
    p = P["guide"]

    def pt(r, z, th):
        return o + A * z + r * (math.cos(th) * E1 + math.sin(th) * E2)
    for k in range(n):
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        tm = (t0 + t1) / 2
        rd = math.cos(tm) * E1 + math.sin(tm) * E2
        _oface(p, TIE, [pt(r_out, z0, t0), pt(r_out, z0, t1), pt(r_out, z1 - ch, t1), pt(r_out, z1 - ch, t0)], rd)
        if ch:
            _oface(p, TIE, [pt(r_out, z1 - ch, t0), pt(r_out, z1 - ch, t1), pt(r_out - ch, z1, t1),
                            pt(r_out - ch, z1, t0)], rd + A)
        _oface(p, TIE, [pt(rb, z1, t0), pt(r_out - ch, z1, t0), pt(r_out - ch, z1, t1), pt(rb, z1, t1)], A)
        if lod == 0:
            _oface(p, TIE, [pt(rb, z0, t0), pt(rb, z0, t1), pt(rb, z1, t1), pt(rb, z1, t0)], -rd)
    if lod > 0:
        return
    _bristles(p, TIE, o, A, E1, rb, z1 - 0.001, rbun + 0.0003, z0 + 0.0012, 16)   # (ragged tips stay over z0:
    #                                                                     the collar sits ON the Drop's ENTRY plane)
    for sg in (-1, 1):            # two screws into the plate's frame (across the slot, where the collar bears on it)
        hexnut(P["hw"], pt((rb + r_out) / 2, z1, sg * math.pi / 2), A, 0.0026, 0.0014, TRAY_HW, sides=6)


def _deck_section(f, lod):
    """The formed deck's section across the c-d stack (t, u): the flat plate with a lip rolled up each side (inner
    bend radius lip_r, up to lip_h over the deck top, a round hem on top), counter-clockwise (tray_plan.saddle_profiles
    gives its surfaces; the contract tests check them against every bundle)."""
    inner, outer = TP.saddle_profiles(f)["lip"]
    if lod > 0:                        # LOD1: the bends as single chords
        inner, outer = [inner[0], inner[-2], inner[-1]], [outer[0], outer[-2], outer[-1]]
    dt = f.params["deck_t"]
    hem = [(0.5 * (inner[-1][0] + outer[-1][0]) + 0.5 * dt * math.cos(a), inner[-1][1] + 0.5 * dt * math.sin(a))
           for a in np.linspace(0.0, math.pi, 4 if lod == 0 else 2)]
    # counter-clockwise: from the right bend's underside up the lip's outer face, over the hem, down its inner face
    # and across the deck top; the left lip mirrors it; the bottom closes back to the start
    right = list(outer) + hem[1:-1] + list(reversed(inner))
    return right + [(-x, h) for x, h in reversed(right)]


def _roll_section(f, lod):
    """A rolled end's section along the stack (s, u), the +s one: the band between its top and bottom surfaces,
    counter-clockwise; it starts on the deck's edge plane (open there: the deck continues it)."""
    top, bot = TP.saddle_profiles(f)["roll"]
    if lod > 0:
        top, bot = top[::len(top) - 1], bot[::len(bot) - 1]
    return list(reversed(top)) + list(bot)


def crossover_saddle(P, f, lod):
    """The Cross's crossover saddle: a Darker formed-steel bridge over the a-b stack.
    - The deck: a 4 mm plate whose sides roll up into lips along the c-d stack (they keep it on the deck and stiffen
      the plate) and whose two ends roll down on the stack's own convex radius (no cable-cutting edge: the stack
      leaves the deck along them), as tongues over the stack's width.
    - Four Brushed square legs in the crossing's corners, each bolted through the floor wires between a clamp plate on
      the floor and a backing plate under the basket.
    - Brushed tie mounts beside the stack at each deck strap: the straps are tied down to the deck.
    - A CleanWhite "X-OVER" stencil on each lip's outer face (it faces the a and b ports).
    LOD1: the same plate with single-chord bends; LOD2: the plate and its ends as quads."""
    fr = f.frame
    o, T, S, U = (Vector(tuple(v)) for v in (fr.o, fr.t, fr.s, fr.u))
    Sx = U.cross(T)                               # the sweep's s axis for a sweep along T
    H = f.size[1] / 2
    P_ = f.params
    if lod >= 2:
        _saddle_card(P, f)
        return
    # the deck with its lips: swept along the stack (S), its section in (T, U)
    Tn = S                                        # sweep direction
    Sn = U.cross(Tn)                              # = the section's first axis
    sec = _deck_section(f, lod)
    if Sn.dot(T) < 0:                             # keep the section's first axis along +T
        sec = [(-a, b) for a, b in reversed(sec)]
    _prism(P["guide"], o - S * H, o + S * H, (Tn, Sn, U), sec, TIE)
    # the rolled ends: swept across the stack (T), their section in (S, U)
    roll = _roll_section(f, lod)
    w = P_["roll_half"]
    for sg in (-1, 1):
        prof = [(sg * a, b) for a, b in roll]
        if sg < 0:
            prof = prof[::-1]
        if Sx.dot(S) < 0:
            prof = [(-a, b) for a, b in reversed(prof)]
        _prism(P["guide"], o - T * w, o + T * w, (T, Sx, U), prof, TIE)
    if lod > 0:
        return
    # the legs (12 mm square tubes), up into the deck plate (LOD0: from LOD1 on, the deck and its ends only)
    lw, z0 = P_["leg_w"], P_["leg_bottom"]
    for i, j in P_["legs"]:
        c = o + T * i + S * j
        box_open(P["solid"], tuple(c - T * (lw / 2) - S * (lw / 2) + U * z0),
                 tuple(c + T * (lw / 2) + S * (lw / 2) + U * (P_["deck_top"] - 0.001)), "BrushedMetal", skip=("-z",))
    feet = TP.saddle_feet(f)
    for k, (q, size) in enumerate(feet + TP.saddle_tie_boxes(f)):
        c = Vector(tuple(q.o))
        h = Vector((size[0] / 2, size[1] / 2, size[2] / 2))
        # a tie mount sits on the deck, a backing plate against the basket's underside: their hidden face left out
        skip = ("-z",) if k >= len(feet) else (("+z",) if k % 2 else ())
        box_open(P["hw"], tuple(c - h), tuple(c + h), TRAY_HW, skip=skip)
    a_, t_ = P_["foot"]
    for i, j in P_["legs"]:                       # a square bolt head on each foot clamp, through the floor wires
        c = o + T * i + S * j + U * t_
        hexnut(P["hw"], c + (T + S) * (math.copysign(a_ * 0.3, i * j)), U, 0.0035, 0.002, TRAY_HW, sides=4,
               phase=math.pi / 4)
    # X-OVER on each lip's outer face
    lr, lh = P_["lip_r"], P_["lip_h"]
    hc = P_["deck_top"] + (lr + lh) / 2
    for sg in (-1, 1):
        out = T * sg
        F = G.Face(o + out * (f.size[0] / 2 + 0.0002) + U * hc, U.cross(out), U)
        _stencil(P["stencil"], F, P_["stencil"], 0.012)


def _saddle_card(P, f):
    """LOD2: the deck as one plate quad and each rolled end as one sloped quad (the lips and legs left out)."""
    fr = f.frame
    o, T, S, U = (Vector(tuple(v)) for v in (fr.o, fr.t, fr.s, fr.u))
    bm = P["guide"].bm
    mi = P["guide"].mi(TIE)
    W, H, top = f.size[0] / 2, f.size[1] / 2, f.params["deck_top"]
    r, ang, w = f.params["roll_r"], f.params["roll_angle"], f.params["roll_half"]

    def quad(c):
        bm.faces.new([bm.verts.new(v) for v in c]).material_index = mi
    quad([o + T * -W + S * -H + U * top, o + T * W + S * -H + U * top, o + T * W + S * H + U * top,
          o + T * -W + S * H + U * top])
    ds, dh = r * math.sin(ang), r * (1 - math.cos(ang))
    for sg in (-1, 1):
        a = [o + T * -w + S * (sg * H) + U * top, o + T * w + S * (sg * H) + U * top,
             o + T * w + S * (sg * (H + ds)) + U * (top - dh), o + T * -w + S * (sg * (H + ds)) + U * (top - dh)]
        quad(a if sg > 0 else a[::-1])


FITTINGS = {"split_collar": split_collar, "boot": boot, "saddle_clamp": saddle_clamp, "tag": tag,
            "waterfall_guide": waterfall_guide, "crossover_saddle": crossover_saddle, "brush_collar": brush_collar,
            "bundle_clamp": split_collar}     # (the Chute's bundle clamp: a split collar round the vertical bundle)


def fittings(P, plan, lod):
    for f in plan.fittings:
        if f.kind in FITTINGS:
            FITTINGS[f.kind](P, f, lod)
