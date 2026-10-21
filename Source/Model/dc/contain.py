"""Aisle containment: the roof panels DC_Contain_Roof_{100,150,200}, DeckPanel250 clones.

A roof panel spans the contained aisle (W = 1.0 / 1.5 / 2.0 m across, block y) over one rack pitch (1.0 m along the
row, block x) and fills the aisle's top cell, flush with the rack tops: its long (+-y) edges bear on the racks'
containment rails (dims.CONTAIN_RAIL_Y / CONTAIN_RAIL_DZ), its short (+-x) edges seal against the
next panel of the run or the containment door's header. Frame (Blender, metres, centred like every builder here):
x +-0.5, y +-W/2, z +-0.125 (z = -0.125 is the rack's ZT, z = +0.125 the rack top).

Part -> purpose (SE-ified: a chunky Colorable frame, Darker hardware, few big parts):
  frame      Colorable box beams (chamfered underside) round the     carries the panes from rail to rail; the
             perimeter, a cross mullion at x = 0, a long mullion     mullions split the glazing into 0.5 m bays
             every 0.5 m across the aisle                            (a pane a crew member can lift out alone)
  caps       Colorable snap-on glazing caps over every member        retain the panes from above (the top you see
                                                                     from the tray deck)
  panes      FrostedGlass, one per 0.5 x 0.5 m bay                   close the aisle (the hot / cold air stays in)
                                                                     but let the hall light through
  clamps     Darker L-brackets on both long edges at the rack's      grip the rack's containment-rail pads (one per
             rail-pad pitch, two MetalDull bolts up into the beam    0.25 m, the rail's CONTAIN_PADS), so the panel
                                                                     cannot lift off or slide along the row
  gaskets    Darker bulb seals on both short edges                   seal the joint to the next panel / door header
  gussets    Darker corner plates under the frame, two bolts each   keep the welded frame square
  release    per bay: two MetalDull drop ledges under the pane's    FIRE RELEASE: the pane rests on hinged ledges
             end, their latch bar, a fusible link to a lug on the    held up by a fusible link; when the link melts
             end beam, and a Darker tag with a white "FIRE           (a fire under the roof) the ledges drop and the
             RELEASE" stencil under the beam                         pane swings down, so the sprinklers reach the
                                                                     racks (real containment roofs drop away)
  LED        a Darker batten under the cross mullion with an         lights the contained aisle (a roof shades the
             EmissiveWhite diffuser                                  hall luminaires): one batten per rack pitch

Up-face rule (test_roof_faces: nothing mounts on Up or Down): the game's mount generator samples 8 rays per face cell
on a ring of radius 0.66 x 0.125 m and counts hits within 20 mm of the plane (se2model.placement.sample). Every member
of the flush top therefore stays within RAY_FREE (48.8 mm) of the cell planes it sits on (the caps are 36..46 mm
wide; the mullions lie on cell boundaries), and the panes' top stays more than 20 mm under the top plane: no top cell
gets 4 hits. The underside is 18 mm and more above the bottom plane, so Down gets none either.

Fracture (breakable, real fracture zones, as vanilla's panels do): split IN PLANE per 0.5 m bay
(dc/fracture.py _roof): each zone is a bay's pane with its caps, frame segment, clamps and fire release, parting along
the mullions (the beams and caps across a seam are cut and capped in FracturedMaterial01; the 1.5 m aisle's middle panes
crack across its centre line). The two physics slabs (glazing over frame, split at ZS, the panes' bed) stay the intact
model's collision. The Damaged model maps the panes to vanilla's WindowGlassBroken. Under every pane the members carry a
Darker glazing tape (the bed the pane is set on).
"""
import math

from . import dims as DM

try:   # geometry needs Blender; the constants and collision() are plain Python (pytest imports them outside)
    import bmesh
    from se2model import decals as DC
    from se2model import geom as G
    from se2model.geom import Face, Part
except ImportError:
    bmesh = DC = G = Face = Part = None
from .style import DARK, HARDWARE, PAINT, STEEL, STENCIL_WHITE, stencil  # noqa: F401 (STENCIL_WHITE: the decal slot)

GLASS = "FrostedGlass"             # vanilla glazing (our material slot; DeckPanel250 has none)
LED = "EmissiveWhite"              # vanilla static white emissive (as HangarDoor_Base's light strips)

H2 = DM.CELL / 2                   # 0.125: the cell planes (block frame); -H2 = the rack's ZT, +H2 = the rack top
TOP = H2 - 0.0005                  # the caps' top: 0.5 mm under the rack-top plane (flush, never coplanar)
ZS = 0.096                         # the panes' bed (the glazing slab over it, the frame slab under it)
PANE_T = 0.0055                    # pane thickness; its top 23.5 mm under the top plane (> the 20 mm ray band)
ZP = ZS + PANE_T + 0.0005          # the caps' lips start here (0.5 mm over the pane)
BED = 0.0005                       # the Darker glazing tape on every member, under the panes
ZB1 = ZS - 0.0005 - BED            # the frame members' top (the bed on it reaches ZS - 0.5 mm)
BEAM_Z0 = 0.030                    # the perimeter beams' underside
EDGE_IN = 0.010                    # the long beams' outer face: this far inside the +-y planes (the clamps stand there)
EDGE_W = 0.052                     # long beam width (y_in 0.010 .. 0.062)
END_IN = 0.008                     # the end beams' outer face inside the +-x planes (the gaskets stand there)
END_W = 0.046                      # end beam width (x_in 0.008 .. 0.054)
BEAM_CH = 0.016                    # the beams' underside chamfer (the aisle side)
CROSS_HW, CROSS_Z0, CROSS_CH = 0.028, 0.046, 0.010   # the cross mullion (x = 0): half width, underside, chamfers
LONG_HW, LONG_Z0, LONG_CH = 0.026, 0.052, 0.008      # the long mullions (y = bay lines)
CAP_EDGE = (EDGE_IN, 0.038, 0.046)  # long caps' y_in: outer face, stem (pane side), lip edge
CAP_END = (END_IN, 0.046)          # end caps' x_in: outer face, inner edge (no lip: the pane drops on this side)
CAP_STEM, CAP_LIP = 0.016, 0.024   # mullion caps: half widths of the stem (between panes) and the lip (over them)
CAP_CH = 0.004                     # the caps' top-edge chamfer
PANE_EDGE = 0.039                  # pane edge y_in at a long beam (7 mm under the lip, 23 mm on the beam's bed)
PANE_MULL = 0.017                  # pane edge from a mullion's centre line (7 mm under the lip, 9..11 mm on its bed)
PANE_END = 0.003                   # gap between a pane's end and the end beam's inner face (it drops on that side)
# flush-top members stay within this of a cell plane (module docstring): 0.125 minus the sampler ring's largest
# offset along an axis (0.66 x 0.125 x cos 22.5 deg = 0.0762), = 0.0488
RAY_FREE = 0.125 - 0.66 * 0.125 * math.cos(math.radians(22.5))
# clamps: Darker L-brackets (jaw on the beam's outer face, flange under the beam), one per rail pad
CLAMP_HW = 0.024                   # half length along x
CLAMP_FACE = 0.001                 # the jaw's face: 1 mm inside the +-y plane (it mounts there), facing the rail pad
CLAMP_JAW = (0.034, ZS - 0.0005)   # jaw z (covers the rail's 0.045 .. 0.113 band up to the fracture split)
CLAMP_FLANGE = (0.022, BEAM_Z0, 0.036)   # flange z0, z1 and its inner y_in (under the beam)
GASKET = (0.001, END_IN, 0.044, 0.084)   # x_in face .. root, z band
GUSSET = (0.095, 0.004)            # corner gusset: leg length from the corner, thickness (under the beams)
HINT_T = 0.005                     # mount hint slab thickness
HINT_Z = (-H2 + DM.CONTAIN_RAIL_DZ[0], -H2 + DM.CONTAIN_RAIL_DZ[1])   # the rack's rail band (block frame)
LED_HW, LED_Z = 0.020, (0.032, CROSS_Z0)   # the batten housing: half width, z (under the cross mullion)
LED_LENS_HW, LED_LENS_Z = 0.013, 0.0305    # the diffuser: half width, its underside
LED_END = 0.075                    # the batten stops this far inside the +-y planes
TAG_TEXT = "FIRE RELEASE"

LOD_COUNT = {}                     # name -> LOD count fitted to the MEASURED LOD0 (assemble.fit_lods)


def _pads():
    from .rack import CONTAIN_PADS
    return CONTAIN_PADS


def width(spec):
    """The aisle width W (m): the panel's depth across the aisle (block y)."""
    return DM.CELL * spec.cells[2]


def size(spec):
    return (DM.CELL * spec.cells[0], width(spec), DM.CELL * spec.cells[1])


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


def mullion_ys(spec):
    """y of the long mullions: every 0.5 m across the aisle (on cell boundaries)."""
    w = width(spec)
    n = int(round(w / 0.5))
    return [round(-w / 2 + 0.5 * k, 6) for k in range(1, n)]


def bays(spec):
    """[(side, k, (x0, x1, y0, y1))]: every 0.5 m bay's opening between the members' centre lines / outer faces, side
    = -1 / +1 (the half of the panel along x), k = its index across the aisle."""
    w = width(spec)
    ys = [-w / 2] + mullion_ys(spec) + [w / 2]
    return [(s, k, (min(0.0, s * 0.5), max(0.0, s * 0.5), ys[k], ys[k + 1]))
            for s in (-1, 1) for k in range(len(ys) - 1)]


def pane(spec, s, k):
    """(x0, x1, y0, y1) of the pane of bay (s, k)."""
    w = width(spec)
    ys = [-w / 2] + mullion_ys(spec) + [w / 2]
    y0 = ys[k] + (PANE_EDGE if k == 0 else PANE_MULL)
    y1 = ys[k + 1] - (PANE_EDGE if k == len(ys) - 2 else PANE_MULL)
    xe = 0.5 - END_IN - END_W - PANE_END
    return (min(s * PANE_MULL, s * xe), max(s * PANE_MULL, s * xe), y0, y1)


def clamp_xs():
    return tuple(_pads())


# ---------------------------------------------------------------------------------------------------- collision
def collision(spec):
    """{"regular", "occupancy", "mount"} (the rack.collision format; Blender frame, centred).

    Regular = two slabs that together are the panel: the glazing (z ZS .. +H2) and the frame under it (down to the
    clamp bolts): the intact model's physics (the fracture zones are dc/fracture.py _roof's bays). Mount hints: the +-y long edges and the +-x short edges, each over the
    rack's containment-rail band (HINT_Z); nothing on Up or Down."""
    w = width(spec)
    h, t = 0.5, HINT_T
    z0, z1 = HINT_Z
    reg = [("glazing", (-h, -w / 2, ZS), (h, w / 2, H2)),
           ("frame", (-h, -w / 2, CLAMP_FLANGE[0] - 0.004), (h, w / 2, ZS))]
    mnt = [("edge_front", (-h, w / 2 - t, z0), (h, w / 2, z1)), ("edge_back", (-h, -w / 2, z0), (h, -w / 2 + t, z1)),
           ("end_right", (h - t, -w / 2, z0), (h, w / 2, z1)), ("end_left", (-h, -w / 2, z0), (-h + t, w / 2, z1))]
    return {"regular": reg, "occupancy": [], "mount": mnt}


def edge_mount_rects(spec):
    """{"+y" / "-y": [[x0, x1, z0, z1]], "+x" / "-x": [[y0, y1, z0, z1]]}: the mount hints on each edge plane."""
    out = {"+y": [], "-y": [], "+x": [], "-x": []}
    for _, lo, hi in collision(spec)["mount"]:
        thin = min(range(3), key=lambda i: hi[i] - lo[i])           # the slab's normal axis
        if thin == 1:
            out["+y" if hi[1] > 0 else "-y"].append([lo[0], hi[0], lo[2], hi[2]])
        elif thin == 0:
            out["+x" if hi[0] > 0 else "-x"].append([lo[1], hi[1], lo[2], hi[2]])
        else:
            raise ValueError("a roof mount hint on Up / Down")
    return out


# ---------------------------------------------------------------------------------------------------- geometry
def _area(pts):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def bar(p, axis, a0, a1, pts, mat):
    """Extrude a section polygon along x or y from a0 to a1. pts: [(s, z)], s = the other horizontal coordinate."""
    if axis == "x":
        F, q = Face((a0, 0, 0), (0, 1, 0), (0, 0, 1)), list(pts)               # normal +x, (u, v) = (y, z)
    else:
        F, q = Face((0, a0, 0), (0, 0, 1), (1, 0, 0)), [(z, s) for s, z in pts]   # normal +y, (u, v) = (z, x)
    if _area(q) < 0:
        q.reverse()
    G.prism(p, F, q, 0.0, a1 - a0, mat)


def _dedupe(pts):
    out = []
    for q in pts:
        if not out or abs(q[0] - out[-1][0]) > 1e-9 or abs(q[1] - out[-1][1]) > 1e-9:
            out.append(q)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-9 and abs(out[0][1] - out[-1][1]) < 1e-9:
        out.pop()
    return out


def _beam_section(i0, i1, z0, z1, ch, sg, base):
    """A perimeter beam's section [(s, z)]: from i0 (outer, toward the plane) to i1 (the aisle side) inward of the
    plane at `base` (s = sg * (base - i)), its aisle-side bottom edge chamfered, a 3 mm break on the outer one."""
    S = lambda i: sg * (base - i)  # noqa: E731
    return _dedupe([(S(i0), z0 + 0.003), (S(i0 + 0.003), z0), (S(i1 - ch), z0), (S(i1), z0 + ch), (S(i1), z1),
                    (S(i0), z1)])


def _mullion_section(c, hw, z0, z1, ch):
    return [(c - hw + ch, z0), (c + hw - ch, z0), (c + hw, z0 + ch), (c + hw, z1), (c - hw, z1), (c - hw, z0 + ch)]


def _cap_section(c, stem, lip, z0, z1):
    return [(c - stem, z0), (c + stem, z0), (c + stem, ZP), (c + lip, ZP), (c + lip, z1 - CAP_CH),
            (c + lip - CAP_CH, z1), (c - lip + CAP_CH, z1), (c - lip, z1 - CAP_CH), (c - lip, ZP), (c - stem, ZP)]


def _frame(P, spec, lod):
    """The Colorable frame and its Darker glazing tape under the panes (LOD0)."""
    w = width(spec)
    W2 = w / 2
    fr = P["frame"]
    xb = 0.5 - END_IN                                 # the long beams run the full length; the end beams between
    yb = W2 - EDGE_IN - EDGE_W                        # the end beams', cross and long mullions' y reach
    xm = 0.5 - END_IN - END_W                         # the long mullions' x reach (to the end beams)
    for sg in (-1, 1):                                # the long (edge) beams, +-y
        bar(fr, "x", -xb, xb, _beam_section(EDGE_IN, EDGE_IN + EDGE_W, BEAM_Z0, ZB1, BEAM_CH, sg, W2), PAINT)
        bar(fr, "y", -yb, yb, _beam_section(END_IN, END_IN + END_W, BEAM_Z0, ZB1, BEAM_CH, sg, 0.5), PAINT)
    bar(fr, "y", -yb, yb, _mullion_section(0.0, CROSS_HW, CROSS_Z0, ZB1, CROSS_CH), PAINT)
    for y in mullion_ys(spec):
        for sx in (-1, 1):
            a0, a1 = sorted((sx * CROSS_HW, sx * xm))
            bar(fr, "x", a0, a1, _mullion_section(y, LONG_HW, LONG_Z0, ZB1, LONG_CH), PAINT)
    if lod == 0:   # the glazing tape (the panes are set on it)
        b = P["tape"]
        z0, z1 = ZB1, ZB1 + BED
        for sg in (-1, 1):
            ya, yb_ = sorted((sg * (W2 - EDGE_IN), sg * (W2 - EDGE_IN - EDGE_W)))
            G.box(b, (-xb, ya, z0), (xb, yb_, z1), DARK)
            xa, xc = sorted((sg * (0.5 - CAP_END[0]), sg * (0.5 - CAP_END[1])))   # (only under the end cap)
            G.box(b, (xa, -yb, z0), (xc, yb, z1), DARK)
        G.box(b, (-CROSS_HW, -yb, z0), (CROSS_HW, yb, z1), DARK)
        for y in mullion_ys(spec):
            for sx in (-1, 1):
                a0, a1 = sorted((sx * CROSS_HW, sx * xm))
                G.box(b, (a0, y - LONG_HW, z0), (a1, y + LONG_HW, z1), DARK)


def _caps(P, spec, lod):
    """The Colorable glazing caps: on the long beams (a lip over the panes), the end beams (none: the
    panes drop on that side), the cross mullion (full width) and the long mullions (between the cross cap and the
    end caps)."""
    w = width(spec)
    W2 = w / 2
    cp = P["cap"]
    o, st, lp = CAP_EDGE
    xb = 0.5 - END_IN
    for sg in (-1, 1):
        S = lambda i: sg * (W2 - i)  # noqa: E731
        sec = [(S(o), ZS), (S(st), ZS), (S(st), ZP), (S(lp), ZP), (S(lp), TOP - CAP_CH), (S(lp - CAP_CH), TOP),
               (S(o), TOP)]
        bar(cp, "x", -xb, xb, sec, PAINT)
        e0, e1 = CAP_END
        X = lambda i: sg * (0.5 - i)  # noqa: E731
        bar(cp, "y", -(W2 - lp), W2 - lp, [(X(e0), ZS), (X(e1), ZS), (X(e1), TOP - CAP_CH), (X(e1 - CAP_CH), TOP),
                                           (X(e0), TOP)], PAINT)
    bar(cp, "y", -(W2 - lp), W2 - lp, _cap_section(0.0, CAP_STEM, CAP_LIP, ZS, TOP), PAINT)
    for y in mullion_ys(spec):
        for sx in (-1, 1):
            a0, a1 = sorted((sx * CAP_LIP, sx * (0.5 - CAP_END[1])))
            bar(cp, "x", a0, a1, _cap_section(y, CAP_STEM, CAP_LIP, ZS, TOP), PAINT)


def _panes(P, spec, lod):
    for s, k, _ in bays(spec):
        x0, x1, y0, y1 = pane(spec, s, k)
        G.box(P["glass"], (x0, y0, ZS), (x1, y1, ZS + PANE_T), GLASS)


def _clamps(P, spec, lod):
    """Darker L-brackets on both long edges at the rail pads' x: the jaw on the beam's outer face (its face 1 mm
    inside the plane, facing the rack's rail pad), the flange under the beam with two MetalDull bolts up into it."""
    W2 = width(spec) / 2
    f0, f1, fi = CLAMP_FLANGE
    j0, j1 = CLAMP_JAW
    for sg in (-1, 1):
        S = lambda i: sg * (W2 - i)  # noqa: E731
        sec = [(S(CLAMP_FACE), f0), (S(fi), f0), (S(fi), f1), (S(EDGE_IN), f1), (S(EDGE_IN), j1),
               (S(CLAMP_FACE), j1)]
        if lod >= 2:
            sec = [(S(CLAMP_FACE), j0), (S(EDGE_IN), j0), (S(EDGE_IN), j1), (S(CLAMP_FACE), j1)]
        for xc in clamp_xs():
            bar(P["clamp"], "x", xc - CLAMP_HW, xc + CLAMP_HW, sec, DARK)
            if lod == 0:
                for dx in (-0.012, 0.012):
                    G.cylinder(P["hw"], (xc + dx, S(0.024), f0 + 0.0005), (xc + dx, S(0.024), f0 - 0.004), 0.0065, 6,
                               HARDWARE)


def _gaskets(P, spec, lod):
    """Darker bulb seals along both short edges (their face 1 mm inside the +-x planes)."""
    W2 = width(spec) / 2
    a, r, z0, z1 = GASKET
    ys = W2 - EDGE_IN - 0.004
    for sg in (-1, 1):
        X = lambda i: sg * (0.5 - i)  # noqa: E731
        if lod == 0:
            zm = (z0 + z1) / 2
            sec = [(X(r), z0), (X(r), z1), (X(0.004), z1 - 0.0015), (X(0.0018), z1 - 0.007), (X(a), zm + 0.008),
                   (X(a), zm - 0.008), (X(0.0018), z0 + 0.007), (X(0.004), z0 + 0.0015)]
        else:
            sec = [(X(r), z0), (X(r), z1), (X(a), z1), (X(a), z0)]
        bar(P["gasket"], "y", -ys, ys, sec, DARK)


def _gussets(P, spec, lod):
    """Darker corner plates under the beams (each leg along a beam's underside), two MetalDull bolts."""
    W2 = width(spec) / 2
    L, t = GUSSET
    F = Face((0, 0, 0), (1, 0, 0), (0, 1, 0))
    z1 = BEAM_Z0
    for sx in (-1, 1):
        for sy in (-1, 1):
            X = lambda i: sx * (0.5 - i)  # noqa: E731
            Y = lambda i: sy * (W2 - i)  # noqa: E731
            pts = [(X(END_IN), Y(EDGE_IN)), (X(L), Y(EDGE_IN)), (X(L), Y(EDGE_IN + EDGE_W - 0.008)),
                   (X(END_IN + END_W + 0.012), Y(EDGE_IN + EDGE_W - 0.008)),
                   (X(END_IN + END_W - 0.008), Y(EDGE_IN + EDGE_W + 0.012)), (X(END_IN + END_W - 0.008), Y(L)),
                   (X(END_IN), Y(L))]
            if _area(pts) < 0:
                pts.reverse()
            G.prism(P["dark"], F, pts, z1 - t, z1, DARK)
            if lod == 0:
                for a, b in ((X(L - 0.030), Y(EDGE_IN + 0.024)), (X(END_IN + 0.022), Y(L - 0.030))):
                    G.cylinder(P["hw"], (a, b, z1 - t + 0.0005), (a, b, z1 - t - 0.0035), 0.0065, 6, HARDWARE)


def _release(P, spec, lod):
    """Per bay, at its end beam: the two drop ledges under the pane's end, their latch bar, the fusible link to the
    lug on the beam, and the FIRE RELEASE tag under the beam."""
    xi = 0.5 - END_IN - END_W                       # the end beam's inner face
    hw = P["hw"]
    for s, k, (bx0, bx1, by0, by1) in bays(spec):
        yc = (by0 + by1) / 2
        X = lambda i: s * (xi - i)  # noqa: E731   i > 0: into the bay
        zl1, zl0 = ZS - 0.0006, ZS - 0.0036          # the ledges' top (0.6 mm under the pane), bottom
        for dy in (-0.11, 0.11):
            a0, a1 = sorted((X(0.0), X(0.022)))
            G.box(hw, (a0, yc + dy - 0.015, zl0), (a1, yc + dy + 0.015, zl1), HARDWARE)          # drop ledge
            if lod == 0:   # its hinge knuckle on the beam face
                G.cylinder(hw, (X(0.003), yc + dy - 0.015, zl0 - 0.003), (X(0.003), yc + dy + 0.015, zl0 - 0.003),
                           0.004, 6, HARDWARE)
        a0, a1 = sorted((X(0.012), X(0.021)))
        G.box(hw, (a0, yc - 0.13, zl0 - 0.006), (a1, yc + 0.13, zl0), HARDWARE)                  # latch bar
        lug_z = 0.058
        a0, a1 = sorted((X(0.0), X(0.008)))
        G.box(hw, (a0, yc - 0.009, lug_z - 0.008), (a1, yc + 0.009, lug_z + 0.006), HARDWARE)    # lug on the beam
        # the fusible link: from the lug (x_in 0.006) up to the latch bar's middle (x_in 0.0165), two soldered plates
        p0 = (X(0.006), lug_z)
        p1 = (X(0.0165), zl0 - 0.006)
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dz)
        u = (dx / L, 0.0, dz / L)
        F = Face((p0[0], yc, p0[1]), u, (0, 1, 0))
        if lod == 0:
            r, wst = 0.0055, 0.0032
            bone = [(0.0, -r), (r, -r), (r + 0.004, -wst), (L - r - 0.004, -wst), (L - r, -r), (L, -r),
                    (L + 0.003, 0.0), (L, r), (L - r, r), (L - r - 0.004, wst), (r + 0.004, wst), (r, r), (0.0, r),
                    (-0.003, 0.0)]
            G.prism(hw, F, bone, -0.0008, 0.0008, HARDWARE)
            G.prism(hw, F, [(L * 0.35, -wst - 0.0006), (L * 0.65, -wst - 0.0006), (L * 0.65, wst + 0.0006),
                            (L * 0.35, wst + 0.0006)], 0.0008, 0.0016, HARDWARE)                  # the solder joint
        else:
            G.prism(hw, F, [(0.0, -0.004), (L, -0.004), (L, 0.004), (0.0, 0.004)], -0.001, 0.001, HARDWARE)
        # the tag under the end beam (its face down), the stencil reading from the bay toward the end beam
        a0, a1 = sorted((s * (0.5 - END_IN - 0.006), s * (xi + 0.008)))
        G.box(P["dark"], (a0, yc - 0.052, BEAM_Z0 - 0.003), (a1, yc + 0.052, BEAM_Z0), DARK)
        if lod == 0:
            from se2model.config import DECAL_OFFSET
            Ft = Face((s * (0.5 - END_IN - END_W / 2 + 0.001), yc, BEAM_Z0 - 0.003), (0, s, 0), (s, 0, 0))
            stencil(P["decal"], Ft, 0.0, 0.0, 0.0105, TAG_TEXT, d=0.0004 - DECAL_OFFSET)


def _led(P, spec, lod):
    """The LED batten under the cross mullion: a Darker housing with end caps, the EmissiveWhite diffuser under it,
    two MetalDull screws per end cap and the feed gland into the +y long beam."""
    W2 = width(spec) / 2
    y1 = W2 - LED_END
    z0, z1 = LED_Z
    G.box(P["dark"], (-LED_HW, -y1, z0), (LED_HW, y1, z1), DARK)
    G.box(P["led"], (-LED_LENS_HW, -y1 + 0.012, LED_LENS_Z), (LED_LENS_HW, y1 - 0.012, z0), LED)
    if lod >= 2:
        return
    for sg in (-1, 1):
        ya, yb = sorted((sg * (y1 - 0.012), sg * y1))
        G.box(P["dark"], (-LED_HW - 0.003, ya, z0 - 0.003), (LED_HW + 0.003, yb, z1), DARK)        # end cap
        if lod == 0:
            for dx in (-0.011, 0.011):
                G.cylinder(P["hw"], (dx, sg * (y1 - 0.006), z0 - 0.0025), (dx, sg * (y1 - 0.006), z0 - 0.0055),
                           0.004, 6, HARDWARE)
    if lod == 0:   # the feed: a gland from the +y end cap into the long beam's inner face
        yb = W2 - EDGE_IN - EDGE_W
        G.cylinder(P["hw"], (0.0, y1, (z0 + z1) / 2), (0.0, yb + 0.0005, (z0 + z1) / 2), 0.006, 8, HARDWARE)


def _lod2(P, spec):
    """Far: every member one Colorable box (frame + cap), one pane per bay, the clamps, gaskets and the LED."""
    w = width(spec)
    W2 = w / 2
    fr = P["frame"]
    xb = 0.5 - END_IN
    yb = W2 - EDGE_IN - EDGE_W
    xm = 0.5 - END_IN - END_W
    for sg in (-1, 1):
        ya, yc = sorted((sg * (W2 - EDGE_IN), sg * yb))
        G.box(fr, (-xb, ya, BEAM_Z0), (xb, yc, TOP), PAINT)
        xa, xc = sorted((sg * xb, sg * xm))
        G.box(fr, (xa, -yb, BEAM_Z0), (xc, yb, TOP), PAINT)
    G.box(fr, (-CROSS_HW, -yb, CROSS_Z0), (CROSS_HW, yb, TOP), PAINT)
    for y in mullion_ys(spec):
        for sx in (-1, 1):
            a0, a1 = sorted((sx * CROSS_HW, sx * xm))
            G.box(fr, (a0, y - LONG_HW, LONG_Z0), (a1, y + LONG_HW, TOP), PAINT)
    _panes(P, spec, 2)
    _clamps(P, spec, 2)
    _gaskets(P, spec, 2)
    _led(P, spec, 2)


def last_lod(spec):
    p = Part("lastlod")
    W2 = width(spec) / 2
    G.box(p, (-0.5 + END_IN, -W2 + EDGE_IN, BEAM_Z0), (0.5 - END_IN, W2 - EDGE_IN, TOP), f"{spec.name}_LastLOD")
    return [p]


PART_NAMES = ("frame", "cap", "glass", "clamp", "gasket", "dark", "hw", "tape", "decal", "led")


def build(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the 12-tri box."""
    if lod == n_lods(spec) - 1:
        return last_lod(spec)
    P = {k: Part(k) for k in PART_NAMES}
    P["decal"].decal = True
    if lod >= 2:
        _lod2(P, spec)
        return [p for p in P.values() if not p.empty()]
    if lod == 0:
        P["frame"].bevel = (0.0025, 1)
        P["cap"].bevel = (0.0015, 1)
        P["clamp"].bevel = (0.0015, 1)
    _frame(P, spec, lod)
    _caps(P, spec, lod)
    _panes(P, spec, lod)
    _clamps(P, spec, lod)
    _gaskets(P, spec, lod)
    _gussets(P, spec, lod)
    _release(P, spec, lod)
    _led(P, spec, lod)
    return [p for p in P.values() if not p.empty()]


# =================================================================================================================
# The containment end-of-aisle sliding doors DC_Contain_Door_{100,150,200}, SlidingDoorNarrow250 clones
# =================================================================================================================
# Frame (Blender, centred block frame): x across the aisle end (|x| <= W, the block is 2W wide), y through the door
# (-Y faces the racks: the door's -Y plane is the row-end plane, so its -Y face is the aisle side over the opening and
# lies on the end racks' side panels over the pockets; +Y faces the room), z up (z = -DH is the raised floor's top,
# z = ZH the racks' ZT, z = +DH the rack tops). Opening |x| <= W/2, pockets W/2 <= |x| <= W in front of the rack sides.
#
# Part -> purpose:
#   header (lintel)       Colorable box beam ZT..H (the roof band): fascia (+Y, the aisle sign mounts on it), back
#                         board with a Darker seal-seat lip (-Y, the roof run's end gasket bears on it), soffit with
#                         the leaf slot, top plate (Up), end caps; inside: the Brushed top-hung C-track (the leaves'
#                         carriages roll on its flanges) and Darker end stops (they set the open travel); under the
#                         room side of the soffit one Darker spring closer per leaf (keeps the aisle sealed: the
#                         leaves run back shut on their own; stencil "SELF-CLOSING")
#   posts                 Colorable split jambs at |x| = W/2 round the leaf slot, Darker brush seals in the slot
#                         (air separation where the leaf passes into its pocket), Darker armoured corner caps at foot
#                         and head on the aisle- and room-side corners (carts and trolleys knock them)
#   pockets               Colorable cover (+Y) with a panel line, a Darker kick plate and a "KEEP CLOSED" plate; a
#                         Darker back plate on the rack side (-Y) bolted through 4 slotted Brushed angle brackets
#                         (slots: the rack-to-rack tolerance); a slotted end stile with seals: the leaf parks here
#                         without intruding on the aisle
#   sill                  the MetalDull floor guide: a low ramped threshold whose centre slot takes the leaves' guide
#                         shoes (the leaves cannot swing out at the bottom); runs on through both pockets
#   leaves (subparts)     ContainLeafL / ContainLeafR: Colorable aluminium frames (stiles, kick rail, push rail, top
#                         rail) glazed with WindowGlassThin in Darker gaskets; a shiplap (rebated) meeting stile, so
#                         the closed leaves overlap 15 mm past the centre line with a Darker seal; a flush vertical
#                         Brushed pull with a Darker grip on both faces (a pocket door needs a flush pull), yellow
#                         chevrons round the pull zone only (the pinch point); two carriages (MetalDull rollers on
#                         Darker hangers) into the header track; a Darker floor brush and guide shoes.
# Motion: closed, the leaves meet at x = 0 (each runs LEAF_OVER past the centre line and LEAF_OVER behind its post);
# open, each is translated by W/2 - LEAF_OVER into its pocket, its leading edge in the post's shadow.
# Collision: header, two pocket frames (posts included) and the sill (the intact model's physics). Fracture: dc/fracture.py
# _door (8 zones: the lintel, three pieces per pocket tower, the sill), cut and capped by dc/fracture_mesh.py at the
# real joints; every member is built whole across them. Each leaf model has its own collision box (export_models.export_subparts), which the
# vanilla DoorBlockColliderDefinition compounds into the block's collider while the door is Closed and Functional.
from dataclasses import dataclass as _dataclass   # noqa: E402

DOOR_PCU = 150                     # as the clone source (SlidingDoorNarrow250's template)
DOOR_SECONDS = 1.0                 # DoorServerDefinition.OpeningDuration
DOOR_MOUNTS = "All"                # the model's mount hints decide where
LEAF_MODELS = ("ContainLeafL", "ContainLeafR")
DH = 1.25                          # half the block height (10 cells)
ZH = DM.rack_frame(10)[1] - DH     # 1.0: the header's underside = the racks' ZT
YF = DM.CELL / 2 - 0.001           # 0.124: the mounting faces, 1 mm inside the +-y planes
LEAF_HT = 0.022                    # half the leaf thickness (a 44 mm aluminium leaf)
LEAF_Z = (-DH + 0.01, ZH - 0.01)   # the leaf: 10 mm over the floor .. 10 mm under the header
LEAF_ORIGIN_Z = ZH                 # the leaf model's origin: on the track (the header's underside), so its Closed dummy
#                                    lies in the lintel's zone (SupportingFracture)
LEAF_OVER = 0.015                  # each leaf runs this far past the centre line and behind its post
TONGUE, TONGUE_GAP = 0.030, 0.0015  # the shiplap tongue: u range at the meeting edge (half the thickness)
LEAD = 0.110                       # the leading (meeting) stile's u reach (it carries the flush pull)
TRAIL = 0.065                      # the trailing stile's width
RAIL = {"top": 0.075, "bottom": 0.13, "mid": 0.05}
MID_Z = -DH + 0.875                # the push rail's centre (0.875 m over the floor)
PULL_Z = -DH + 1.05                # the flush pull's centre (1.05 m over the floor)
PULL_U, PULL_HH = (0.045, 0.095), 0.17   # its recess (u) and half height
PULL_PLATE = 0.0006                # LOD1+: the flush Darker pull plate's face over the stile (z-fight: > 0.3 mm)
STRIPE_D = 0.0006                  # the pinch-zone chevrons over the stile face (z-fight: not 0.3 mm)
PULL_CORE = 0.004                  # the recess floor (|y|): the stile's web behind the pulls
POST_IN, POST_OUT = 0.050, 0.035   # a post spans W/2 - POST_IN .. W/2 + POST_OUT
SLOT = 0.026                       # the jambs' leaf slot (|y|), seals SEAL_T deep in it
SEAL_T = 0.0035
JAMB_Y = (-0.114, 0.104)           # the jambs' back / front faces
JAMB_CH = 0.018                    # the jambs' opening-side corner chamfer
COVER_Y = (0.080, 0.096)           # the pocket cover (+Y): its kit stays > 20 mm off the plane (no +Y mount)
BACK_Y = (-YF, -0.114)             # the pocket back plate (-Y, on the rack side panel)
END_W = 0.032                      # the pocket end stile's width
KICK_H = 0.15                      # the kick plate's height
POCKET_SPLITS = (-DH + 0.80, -DH + 1.55)   # the pocket towers' joints (the covers' panel lines): 3 fracture pieces
POCKET_FRONT = JAMB_Y[1] + 0.0045  # the pocket hulls' front: the corner caps' face (the solid's +Y extent)
SILL_HW, SILL_TOP, SILL_SLOT = 0.06, -DH + 0.008, 0.007   # the threshold: half width, top, guide-slot half width
SOFFIT_T, HEAD_SLOT = 0.012, 0.034  # the header soffit's thickness and its leaf slot (|y|)
TRACK_Z = ZH + 0.030               # the track flanges' underside (6 mm thick, gap +-0.008, walls at |y| 0.030..0.034)
ROLLER_R = 0.0145
ROLLER_Z = TRACK_Z + 0.006 + ROLLER_R + 0.0005
CARRIAGE_U = 0.16                  # the carriages' u from either leaf end
LIP_Z = (ZH + 0.150, ZH + 0.230)   # the -Y seal-seat lip: the roof's end gasket bears at ZH + 0.169 .. 0.209
LIP_Y = -YF + 0.0005               # its face (the flush bolts reach -YF + 0.1 mm: the frame never passes -YF)
CLOSER = {"x_in": 0.08, "len": 0.32, "y": (0.040, 0.094), "z": (ZH - 0.050, ZH - 0.004)}
KEEP_TEXT, CLOSER_TEXT = "KEEP CLOSED", "SELF-CLOSING"


@_dataclass(frozen=True)
class Transform:
    position: tuple                # game frame (the block model's; doors.to_game)
    orientation: tuple = (0.0, 0.0, 0.0, 1.0)


@_dataclass(frozen=True)
class Leaf:
    name: str                      # the cloned subpart / dummy prefix (LeftDoor / RightDoor)
    model: str                     # ContainLeafL / ContainLeafR
    side: int                      # -1: the -x leaf, +1: the +x leaf
    closed: Transform
    open: Transform


def door_w(spec):
    """The aisle width W the door closes (the block is 2W wide)."""
    return DM.CELL * spec.cells[0] / 2


def leaf_width(spec):
    return door_w(spec) / 2 + 2 * LEAF_OVER


def leaf_travel(spec):
    return door_w(spec) / 2 - LEAF_OVER


def leaf_centre_x(spec, side, f=0.0):
    """The leaf's model origin (its nominal centre across, on the header's underside: the track) in the block frame at
    open fraction f; the origin's z is LEAF_ORIGIN_Z."""
    return side * (door_w(spec) / 4 + f * leaf_travel(spec))


def door_leaves(spec):
    """[Leaf]: LeftDoor (-x, ContainLeafL) and RightDoor (+x, ContainLeafR); open = closed + a pure translation of
    leaf_travel along x (the vanilla slide), orientation identity. The origin hangs from the track (z = ZH), inside
    the lintel's fracture zone, which supports the closed leaves (SupportingFracture: fracture._door)."""
    from .doors import to_game
    out = []
    for name, model, s in (("LeftDoor", LEAF_MODELS[0], -1), ("RightDoor", LEAF_MODELS[1], 1)):
        out.append(Leaf(name, model, s, Transform(to_game((leaf_centre_x(spec, s, 0.0), 0.0, LEAF_ORIGIN_Z), spec)),
                        Transform(to_game((leaf_centre_x(spec, s, 1.0), 0.0, LEAF_ORIGIN_Z), spec))))
    return out


def leaf_box(spec):
    """The leaf's collision box in its own model frame (Blender axes, origin = the nominal leaf centre on the track)."""
    hw = leaf_width(spec) / 2
    return (-hw, -LEAF_HT, LEAF_Z[0] - LEAF_ORIGIN_Z), (hw, LEAF_HT, LEAF_Z[1] - LEAF_ORIGIN_Z)


def leaf_boxes(spec, f=0.0):
    """{model: (lo, hi)} of the leaves' collision boxes in the block frame at open fraction f."""
    lo, hi = leaf_box(spec)
    out = {}
    for lf in door_leaves(spec):
        x = leaf_centre_x(spec, lf.side, f)
        out[lf.model] = ((lo[0] + x, lo[1], lo[2] + LEAF_ORIGIN_Z), (hi[0] + x, hi[1], hi[2] + LEAF_ORIGIN_Z))
    return out


def use_box(spec):
    """The leaf's DoorUse box (leaf model frame, game axes): (centre, scale)."""
    z0, z1 = LEAF_Z
    return ((0.0, round((z0 + z1) / 2 - LEAF_ORIGIN_Z, 6), 0.0),
            (round(leaf_width(spec), 6), round(z1 - z0, 6), 2 * LEAF_HT + 0.03))


def detector_box(spec):
    """The doorway obstacle detector over the opening (|x| <= W/2, floor .. ZT, the block's depth):
    (centre game, half extents game) = ((x, y up, z), (W/2, ZT/2, 0.125))."""
    from .doors import to_game
    zt = ZH + DH
    c = to_game((0.0, 0.0, -DH + zt / 2), spec)
    return c, (round(door_w(spec) / 2, 6), round(zt / 2, 6), DM.CELL / 2)


def pocket_segments(spec):
    """[(z0, z1)] of the pocket towers' fracture pieces (bottom .. top): split at the cover's panel lines, real joints
    (the jambs and back plate are cut there; the covers part at their own joints)."""
    zs = [-DH] + list(POCKET_SPLITS) + [ZH]
    return list(zip(zs, zs[1:]))


def door_collision(spec):
    """{"regular", "occupancy", "mount"} (Blender frame, centred). Regular (the intact model's physics): header,
    pocket -x, pocket +x (each with its post), sill; the fracture zones are dc/fracture.py _door's. Mount
    hints: the -Y back plates over the pockets (on the rack sides), the -Y header band (the roof run's ends), the +Y
    header band (signs), Up (the header top), Down (sill and pocket frames)."""
    W = door_w(spec)
    h, t = DM.CELL / 2, HINT_T
    xi = W / 2 - POST_IN
    reg = [("header", (-W, -h, ZH), (W, h, DH))]
    for nm, s in (("pocket_l", -1), ("pocket_r", 1)):
        a, b = sorted((s * xi, s * W))
        reg.append((nm, (a, -h, -DH), (b, POCKET_FRONT, ZH)))
    reg.append(("sill", (-xi, -SILL_HW, -DH), (xi, SILL_HW, SILL_TOP)))
    mnt = []
    for nm, s in (("back_l", -1), ("back_r", 1)):
        a, b = sorted((s * W / 2, s * W))
        mnt.append((nm, (a, -h, -DH), (b, -h + t, ZH)))
    mnt += [("header_back", (-W, -h, ZH), (W, -h + t, DH)), ("header_front", (-W, h - t, ZH), (W, h, DH)),
            ("top", (-W, -h, DH - t), (W, h, DH)), ("sill_down", (-xi, -0.1, -DH), (xi, 0.1, -DH + t))]
    for nm, s in (("pocket_down_l", -1), ("pocket_down_r", 1)):
        a, b = sorted((s * xi, s * W))
        mnt.append((nm, (a, -h, -DH), (b, h, -DH + t)))
    return {"regular": reg, "occupancy": [], "mount": mnt}


def back_mount_rects(spec):
    """[[x0, x1, z0, z1]] of the -Y mount hints over the pockets (the faces that bolt to the end racks' sides)."""
    return [[lo[0], hi[0], lo[2], hi[2]] for nm, lo, hi in door_collision(spec)["mount"] if nm.startswith("back_")]


def header_rects(spec):
    """{"-y" / "+y": [[x0, x1, z0, z1]]}: the header band's mount hints (-Y: the roof run, +Y: the aisle sign)."""
    out = {"-y": [], "+y": []}
    for nm, lo, hi in door_collision(spec)["mount"]:
        if nm in ("header_back", "header_front"):
            out["-y" if nm == "header_back" else "+y"].append([lo[0], hi[0], lo[2], hi[2]])
    return out


def pocket_x(spec):
    W = door_w(spec)
    return [W / 2, W]


# ---------------------------------------------------------------------------------------------------- door geometry
def _zprism(p, pts, z0, z1, mat):
    pts = list(pts)
    if _area(pts) < 0:
        pts.reverse()
    G.prism(p, Face((0, 0, 0), (1, 0, 0), (0, 1, 0)), pts, z0, z1, mat)


def _sb(p, s, a0, a1, y0, y1, z0, z1, mat):
    """A box from |x| = a0 .. a1 on side s."""
    xa, xb = sorted((s * a0, s * a1))
    G.box(p, (xa, y0, z0), (xb, y1, z1), mat)


def _jamb(P, s, a_open, a_back, z0, z1, lod, chamfer_open=True):
    """A split jamb (front and back halves round the leaf slot) from |x| = a_open (the chamfered side) to a_back,
    with the Darker brush seals in the slot; whole (the fracture cutter parts it at the pocket pieces' seams)."""
    sg = 1 if a_back > a_open else -1          # direction from the open side to the back side, in |x|
    c = JAMB_CH if (chamfer_open and lod < 2) else 0.0
    for za, zb in ((z0, z1),):
        for yi, yo in ((SLOT, JAMB_Y[1]), (-SLOT, JAMB_Y[0])):
            if c:
                pts = [(a_open, yi), (a_back, yi), (a_back, yo), (a_open + sg * c, yo),
                       (a_open, yo - (c if yo > 0 else -c))]
            else:
                pts = [(a_open, yi), (a_back, yi), (a_back, yo), (a_open, yo)]
            _zprism(P["frame"], [(s * a, y) for a, y in _dedupe(pts)], za, zb, PAINT)
        if lod < 2:
            a0, a1 = sorted((a_open + sg * 0.004, a_back - sg * 0.002))
            for y0, y1 in ((SLOT - SEAL_T, SLOT), (-SLOT, -SLOT + SEAL_T)):
                _sb(P["dark"], s, a0, a1, y0, y1, max(za, z0 + 0.008), min(zb, z1 - 0.002), DARK)


def _post_caps(P, s, xi, lod):
    """Armoured Darker caps on the posts' opening-side corners, both faces, at the foot and the head."""
    from .style import corner_cap
    for yo, sy in ((JAMB_Y[1] + 0.004, 1), (JAMB_Y[0] - 0.004, -1)):
        for z0, z1, trim in ((-DH + 0.0008, -DH + 0.20, "top"), (ZH - 0.16, ZH - 0.0008, None)):
            corner_cap(P["dark"], -s, sy, s * (xi - 0.004), yo, z0, z1, size=0.05, chamfer=0.022, lod=lod,
                       trim_at=trim)


def _near_seam(z, d=0.02):
    return any(abs(z - c) < d for c in POCKET_SPLITS)


def _pocket(P, spec, s, lod):
    W = door_w(spec)
    xi, xo, xe = W / 2 - POST_IN, W / 2 + POST_OUT, W - END_W
    z0, z1 = -DH + 0.0008, ZH - 0.0008
    _jamb(P, s, xi, xo, z0, z1, lod)                               # the post at the opening
    _jamb(P, s, W - 0.001, xe, z0, z1, lod)                        # the pocket's end stile (chamfered outer corners)
    # the cover (+Y): one panel per pocket piece (the panel lines are the pieces' joints), a Darker backer in each line
    g = 0.003
    edges = [z0] + list(POCKET_SPLITS) + [z1]
    for k in range(len(edges) - 1):
        a = edges[k] + (g if k > 0 else 0.0)
        b = edges[k + 1] - (g if k < len(edges) - 2 else 0.0)
        _sb(P["frame"], s, xo, xe, COVER_Y[0], COVER_Y[1], a, b, PAINT)
    if lod < 2:
        for zc in POCKET_SPLITS:
            _sb(P["dark"], s, xo, xe, COVER_Y[0], COVER_Y[1] - 0.003, zc - g, zc + g, DARK)
    _sb(P["dark"], s, xo + 0.004, xe - 0.004, COVER_Y[1], COVER_Y[1] + 0.004, z0, -DH + KICK_H, DARK)   # kick plate
    # the back plate on the rack side (-Y), whole (the cutter parts it with the towers)
    _sb(P["dark"], s, W / 2, W - 0.001, BACK_Y[0], BACK_Y[1], z0, z1, DARK)
    if lod >= 2:
        return
    xc = (xo + xe) / 2
    if lod == 0:
        for a in (xo + 0.012, xe - 0.012):                          # the cover screws (into the pocket frame)
            z = -DH + 0.30
            while z < ZH - 0.08:
                if not _near_seam(z, 0.03):
                    G.cylinder(P["hw"], (s * a, COVER_Y[1] - 0.0005, z), (s * a, COVER_Y[1] + 0.0025, z), 0.0055, 8,
                               HARDWARE)
                z += 0.25
        for y in (0.066, -0.070):                                   # the jambs' seal-retainer screws (opening face)
            z = -DH + 0.35
            while z < ZH - 0.2:
                if not _near_seam(z):
                    G.cylinder(P["hw"], (s * (xi + 0.0005), y, z), (s * (xi - 0.0025), y, z), 0.0055, 6, HARDWARE)
                z += 0.30
        for a in (xo + 0.03, xe - 0.03):                            # kick plate bolts
            for zb in (-DH + 0.04, -DH + KICK_H - 0.04):
                G.cylinder(P["hw"], (s * a, COVER_Y[1] + 0.0035, zb), (s * a, COVER_Y[1] + 0.0075, zb), 0.0065, 6,
                           HARDWARE)
    # "KEEP CLOSED" plate at eye height on the cover
    zk, hw_, hh = -DH + 1.62, min(0.12, (xe - xo) / 2 - 0.03), 0.034
    _sb(P["dark"], s, xc - hw_, xc + hw_, COVER_Y[1], COVER_Y[1] + 0.003, zk - hh, zk + hh, DARK)
    from se2model.config import DECAL_OFFSET
    Fk = Face((s * xc, COVER_Y[1] + 0.003, zk), (-1, 0, 0), (0, 0, 1))
    stencil(P["decal"], Fk, 0.0, 0.0, 0.026, KEEP_TEXT, d=0.0004 - DECAL_OFFSET)
    if lod == 0:
        # the 4 slotted angle brackets: the back plate to the post's and the end stile's pocket-side faces
        for a, d in ((xo, 1), (xe, -1)):
            for zb in (-DH + 0.30, ZH - 0.25):
                _sb(P["steel"], s, a, a + d * 0.07, BACK_Y[1], BACK_Y[1] + 0.004, zb - 0.04, zb + 0.04, STEEL)
                _sb(P["steel"], s, a, a + d * 0.004, BACK_Y[1], -0.050, zb - 0.04, zb + 0.04, STEEL)
                ac = a + d * 0.042
                _sb(P["dark"], s, ac - 0.007, ac + 0.007, BACK_Y[1] + 0.004, BACK_Y[1] + 0.0045, zb - 0.026,
                    zb + 0.026, DARK)                               # the slot
                G.cylinder(P["hw"], (s * ac, BACK_Y[1] + 0.004, zb), (s * ac, BACK_Y[1] + 0.009, zb), 0.0075, 6,
                           HARDWARE)
                for dz in (-0.022, 0.022):
                    a2 = a + d * 0.004
                    G.cylinder(P["hw"], (s * a2, -0.085, zb + dz), (s * (a2 + d * 0.004), -0.085, zb + dz), 0.0065,
                               6, HARDWARE)


def _sill(P, spec, lod):
    """The MetalDull threshold, one piece through both pockets (the cutter parts it at the posts' faces: the opening =
    the sill zone, the pockets = their towers): ramped lips either side of the guide slot, countersunk floor
    anchors."""
    W = door_w(spec)
    xe = W - END_W
    b0, b1 = -DH + 0.0005, -DH + 0.0025
    for a0, a1 in ((-xe, xe),):
        if lod >= 2:
            G.box(P["hw"], (a0, -SILL_HW, b0), (a1, SILL_HW, SILL_TOP), HARDWARE)
            continue
        # one solid section (the base plate with both ramped lips and the guide slot between them): the welded
        # parts would otherwise share edges, and the cutter caps only a closed cross-section
        sec = [(-SILL_HW, b0), (SILL_HW, b0), (SILL_HW, b1 + 0.001), (0.024, SILL_TOP), (SILL_SLOT, SILL_TOP),
               (SILL_SLOT, b1), (-SILL_SLOT, b1), (-SILL_SLOT, SILL_TOP), (-0.024, SILL_TOP), (-SILL_HW, b1 + 0.001)]
        bar(P["hw"], "x", a0, a1, sec, HARDWARE)
        for sg in (-1, 1):
            if lod == 0:   # countersunk anchors into the floor deck, every 0.25 m on both lips
                n = max(1, int((a1 - a0) / 0.25))
                for k in range(n):
                    x = a0 + (a1 - a0) * (k + 0.5) / n
                    G.cylinder(P["hw"], (x, sg * 0.040, b1 + 0.0015), (x, sg * 0.040, b1 + 0.0035), 0.006, 8,
                               HARDWARE)


def _header(P, spec, lod):
    """The header beam, whole (the cutter parts it at the lintel's ends, x = +-(W/2 + POST_OUT): the joints over the
    posts, into the lintel and the two pocket heads)."""
    W = door_w(spec)
    xh = W - 0.012                                                 # the boards run between the end caps
    top0 = DH - 0.013
    fr = P["frame"]
    if lod >= 2:
        G.box(fr, (-W + 0.001, -0.1225, ZH), (W - 0.001, YF, DH - 0.001), PAINT)
        G.box(P["dark"], (-W / 2 - 0.03, LIP_Y, LIP_Z[0]), (W / 2 + 0.03, -0.1225, LIP_Z[1]), DARK)
        G.box(P["steel"], (-xh, -HEAD_SLOT, ZH - 0.0005), (xh, HEAD_SLOT, ZH + 0.001), STEEL)
        return
    yf = YF - 0.0005                                               # the fascia face (its inserts reach YF)
    for a, b in ((-xh, xh),):
        bar(fr, "x", a, b, [(0.104, ZH), (yf - 0.012, ZH), (yf, ZH + 0.012), (yf, DH - 0.001), (0.104, DH - 0.001)],
            PAINT)                                                 # the fascia (+Y)
        bar(fr, "x", a, b, [(-0.104, ZH), (-0.104, DH - 0.001), (-0.1225, DH - 0.001), (-0.1225, ZH + 0.012),
                            (-0.1105, ZH)], PAINT)                 # the back board (-Y)
        G.box(fr, (a, -0.104, top0), (b, 0.104, DH - 0.001), PAINT)                      # the top plate (Up)
        for sg in (-1, 1):
            ya, yb = sorted((sg * HEAD_SLOT, sg * 0.104))
            G.box(fr, (a, ya, ZH), (b, yb, ZH + SOFFIT_T), PAINT)                         # the soffit
            # the track: Brushed walls and flanges (a C-channel open downward)
            ya, yb = sorted((sg * 0.030, sg * HEAD_SLOT))
            G.box(P["steel"], (a, ya, ZH + 0.004), (b, yb, top0), STEEL)
            ya, yb = sorted((sg * 0.008, sg * 0.030))
            G.box(P["steel"], (a, ya, TRACK_Z), (b, yb, TRACK_Z + 0.006), STEEL)
    for sg in (-1, 1):
        xa, xb = sorted((sg * xh, sg * (W - 0.001)))
        G.box(fr, (xa, -0.1225, ZH), (xb, YF, DH - 0.001), PAINT)                        # end caps
        _sb(P["dark"], sg, W - 0.115, W - 0.06, -0.028, 0.028, TRACK_Z + 0.006, TRACK_Z + 0.045, DARK)   # end stops
    # the -Y seal-seat lip over the opening (the roof run's end gasket bears on it), flush bolts
    G.box(P["dark"], (-W / 2 - 0.03, LIP_Y, LIP_Z[0]), (W / 2 + 0.03, -0.1225, LIP_Z[1]), DARK)
    if lod == 0:
        n = int(round((W + 0.06) / 0.25))
        for k in range(n + 1):
            x = -W / 2 - 0.03 + 0.02 + k * (W + 0.02) / n
            G.cylinder(P["hw"], (x, LIP_Y + 0.0003, sum(LIP_Z) / 2), (x, -YF + 0.0001, sum(LIP_Z) / 2), 0.0055, 6,
                       HARDWARE)
        for x in (-0.42, 0.42):                                    # the sign's threaded inserts on the fascia
            if abs(x) < W - 0.05:
                for z in (ZH + 0.05, DH - 0.05):
                    G.cylinder(P["hw"], (x, YF - 0.0015, z), (x, YF - 0.0001, z), 0.006, 8, HARDWARE)


def _closers(P, spec, lod):
    """One spring closer per leaf under the room-side soffit, just inside each post: a Darker body on a mounting
    plate, a Brushed tension cap and drive rod, the arm into the track slot (to the leaf's carriage)."""
    W = door_w(spec)
    xi = W / 2 - POST_IN
    y0, y1 = CLOSER["y"]
    z0, z1 = CLOSER["z"]
    for s in (-1, 1):
        a1 = xi - CLOSER["x_in"]
        a0 = a1 - CLOSER["len"]
        if lod >= 2:
            _sb(P["dark"], s, a0, a1, y0, y1, z0, ZH, DARK)
            continue
        _sb(P["dark"], s, a0 - 0.02, a1 + 0.02, y0 - 0.006, y1 + 0.006, z1, ZH, DARK)          # mounting plate
        xa, xb = sorted((s * a0, s * a1))
        c = 0.010
        bar(P["dark"], "x", xa, xb, [(y0, z0 + c), (y0 + c, z0), (y1 - c, z0), (y1, z0 + c), (y1, z1), (y0, z1)],
            DARK)                                                                              # the body
        yc, zc = (y0 + y1) / 2, (z0 + z1) / 2
        G.cylinder(P["steel"], (s * a1, yc, zc), (s * (a1 + 0.012), yc, zc), 0.016, 12 if lod == 0 else 8, STEEL)
        G.cylinder(P["steel"], (s * a0, yc, zc), (s * (a0 - 0.07), yc, zc), 0.005, 8, STEEL)   # drive rod
        _sb(P["dark"], s, a0 - 0.085, a0 - 0.065, 0.026, yc + 0.008, zc - 0.012, ZH, DARK)     # arm to the slot
        if lod == 0:
            for a in (a0 + 0.03, a1 - 0.03):
                for yb in (y0 - 0.002, y1 + 0.002):
                    G.cylinder(P["hw"], (s * a, yb, z1 - 0.0005), (s * a, yb, z1 - 0.004), 0.0055, 6, HARDWARE)
            from se2model.config import DECAL_OFFSET
            Fc = Face((s * (a0 + a1) / 2, y1, zc), (-1, 0, 0), (0, 0, 1))
            stencil(P["decal"], Fc, 0.0, 0.0, 0.011, CLOSER_TEXT, d=0.0004 - DECAL_OFFSET)


def _door_lod3(P, spec):
    W = door_w(spec)
    xi = W / 2 - POST_IN
    G.box(P["frame"], (-W + 0.001, -0.1225, ZH), (W - 0.001, YF, DH - 0.001), PAINT)
    for s in (-1, 1):
        _sb(P["frame"], s, xi, W - 0.001, SLOT, JAMB_Y[1], -DH + 0.0008, ZH - 0.0008, PAINT)
        _sb(P["dark"], s, xi, W - 0.001, BACK_Y[0], -SLOT, -DH + 0.0008, ZH - 0.0008, DARK)
    G.box(P["hw"], (-xi, -SILL_HW, -DH + 0.0005), (xi, SILL_HW, SILL_TOP), HARDWARE)


def door_last_lod(spec):
    W = door_w(spec)
    p = Part("lastlod")
    G.box(p, (-W + 0.001, -YF, -DH + 0.0005), (W - 0.001, YF, DH - 0.001), f"{spec.name}_LastLOD")
    return [p]


DOOR_PARTS = ("frame", "dark", "steel", "hw", "decal")


def build_door(spec, lod):
    """The door frame's parts for one LOD (centred block frame); the last LOD is the 12-tri box. The members run whole
    across the fracture seams: dc/fracture_mesh.py cuts and caps them for the Fractured model."""
    n = n_lods(spec)
    if lod == n - 1:
        return door_last_lod(spec)
    P = {k: Part(k) for k in DOOR_PARTS}
    P["decal"].decal = True
    if lod >= 3:
        _door_lod3(P, spec)
        return [p for p in P.values() if not p.empty()]
    if lod == 0:
        P["frame"].bevel = (0.0025, 1)
    _header(P, spec, lod)
    W = door_w(spec)
    for s in (-1, 1):
        _pocket(P, spec, s, lod)
        if lod < 2:
            _post_caps(P, s, W / 2 - POST_IN, lod)
    _sill(P, spec, lod)
    _closers(P, spec, lod)
    return [p for p in P.values() if not p.empty()]


# ---------------------------------------------------------------------------------------------------- leaf geometry
def build_leaf(spec, model, lod):
    """One leaf model's parts (not its last LOD: leaf_last). Leaf frame: origin = the nominal leaf centre at the
    block's mid-height, x across (u = the distance from the meeting edge: x = s (u - hw)), +Y the room side."""
    s = -1 if model == LEAF_MODELS[0] else 1
    t = -s                                     # the shiplap tongue's side (y sign): L in front, R behind
    Lw = leaf_width(spec)
    hw = Lw / 2
    z0, z1 = LEAF_Z
    T_ = LEAF_HT
    P = {k: Part(k) for k in ("frame", "glass", "dark", "steel", "hw", "decal")}
    P["decal"].decal = True
    if lod == 0:
        P["frame"].bevel = (0.002, 1)
    fr, dk = P["frame"], P["dark"]

    def X(u):
        return s * (u - hw)

    def ub(part, u0, u1, y0, y1, za, zb, mat):
        xa, xb = sorted((X(u0), X(u1)))
        G.box(part, (xa, y0, za), (xb, y1, zb), mat)

    ue = Lw - 0.0015                           # the trailing edge (1.5 mm short: open, it stays inside the block)
    rt, rb, rm = z1 - RAIL["top"], z0 + RAIL["bottom"], (MID_Z - RAIL["mid"] / 2, MID_Z + RAIL["mid"] / 2)
    # the tongue (half thickness, on side t) and the trailing stile
    ya, yb = sorted((t * 0.0005, t * T_))
    ub(fr, TONGUE_GAP, TONGUE, ya, yb, z0, z1, PAINT)
    ub(fr, Lw - TRAIL, ue, -T_, T_, z0, z1, PAINT)
    # the leading stile, broken round the two flush pulls (LOD0 / 1)
    pz0, pz1 = PULL_Z - PULL_HH, PULL_Z + PULL_HH
    if lod >= 1:
        ub(fr, TONGUE, LEAD, -T_, T_, z0, z1, PAINT)
    else:
        ub(fr, TONGUE, LEAD, -T_, T_, z0, pz0, PAINT)
        ub(fr, TONGUE, LEAD, -T_, T_, pz1, z1, PAINT)
        ub(fr, TONGUE, PULL_U[0], -T_, T_, pz0, pz1, PAINT)
        ub(fr, PULL_U[1], LEAD, -T_, T_, pz0, pz1, PAINT)
        ub(fr, PULL_U[0], PULL_U[1], -PULL_CORE, PULL_CORE, pz0, pz1, PAINT)
    # rails: top, bottom (kick), mid (push)
    for za, zb in ((rt, z1), (z0, rb), rm):
        ub(fr, LEAD, Lw - TRAIL, -T_, T_, za, zb, PAINT)
    # the glazing: two WindowGlassThin panes in the members' grooves, Darker gaskets round them on both faces
    for za, zb in ((rb, rm[0]), (rm[1], rt)):
        ub(P["glass"], LEAD - 0.008, Lw - TRAIL + 0.008, -0.003, 0.003, za - 0.008, zb + 0.008, "WindowGlassThin")
        if lod == 0:
            u0, u1, g = LEAD, Lw - TRAIL, 0.004
            for sg in (-1, 1):
                ya, yb = sorted((sg * 0.003, sg * 0.007))
                ub(dk, u0, u1, ya, yb, za, za + g, DARK)
                ub(dk, u0, u1, ya, yb, zb - g, zb, DARK)
                ub(dk, u0, u0 + g, ya, yb, za + g, zb - g, DARK)
                ub(dk, u1 - g, u1, ya, yb, za + g, zb - g, DARK)
    # the meeting seal (Darker) on the body's rebate face, where the other leaf's tongue tip lands
    if lod < 1:
        ya, yb = sorted((-t * 0.001, -t * (T_ - 0.003)))
        ub(dk, TONGUE - 0.0012, TONGUE, ya, yb, z0 + 0.01, z1 - 0.01, DARK)
    # the flush pulls (both faces): Darker recess liner, a Brushed bar on two posts, the Darker grip
    uc = sum(PULL_U) / 2
    for sg in (-1, 1):
        if lod >= 1:   # far: the recess as a flush Darker plate, the bar as a Brushed strip on it
            # (z-fight: the plate's face 0.6 mm over the stile's, not 0.2 mm; the bar on it)
            ya, yb = sorted((sg * (T_ - 0.0005), sg * (T_ + PULL_PLATE)))
            ub(dk, PULL_U[0], PULL_U[1], ya, yb, pz0, pz1, DARK)
            ya, yb = sorted((sg * (T_ + PULL_PLATE), sg * (T_ + PULL_PLATE + 0.0004)))
            ub(P["steel"], sum(PULL_U) / 2 - 0.0055, sum(PULL_U) / 2 + 0.0055, ya, yb, PULL_Z - 0.15, PULL_Z + 0.15,
               STEEL)
            if lod == 1:
                from se2model.config import DECAL_OFFSET
                F = Face((0, sg * T_, 0), (-sg, 0, 0), (0, 0, 1))
                for u in (0.0375, 0.1025):
                    DC.stripes(P["decal"], F, -sg * X(u), PULL_Z, 2 * PULL_HH + 0.04, 0.010, "yellow",
                               d=STRIPE_D - DECAL_OFFSET, vertical=True)
            continue
        ya, yb = sorted((sg * PULL_CORE, sg * (PULL_CORE + 0.0015)))
        ub(dk, PULL_U[0], PULL_U[1], ya, yb, pz0, pz1, DARK)                      # recess floor
        if lod == 0:
            ya, yb = sorted((sg * (PULL_CORE + 0.0015), sg * (T_ - 0.0005)))
            for u0, u1 in ((PULL_U[0], PULL_U[0] + 0.0015), (PULL_U[1] - 0.0015, PULL_U[1])):
                ub(dk, u0, u1, ya, yb, pz0, pz1, DARK)                            # recess side walls
            for za, zb in ((pz0, pz0 + 0.0015), (pz1 - 0.0015, pz1)):   # end walls BETWEEN the side walls (z-fight:
                ub(dk, PULL_U[0] + 0.0015, PULL_U[1] - 0.0015, ya, yb, za, zb, DARK)   # no coplanar corner overlaps)
        yc = sg * 0.0135
        n = 10 if lod == 0 else 6
        G.cylinder(P["steel"], (X(uc), yc, PULL_Z - 0.15), (X(uc), yc, PULL_Z + 0.15), 0.0055, n, STEEL)
        for zp in (PULL_Z - 0.15, PULL_Z + 0.15):
            G.cylinder(P["steel"], (X(uc), sg * (PULL_CORE + 0.0015), zp), (X(uc), yc, zp), 0.006, n, STEEL)
        G.cylinder(dk, (X(uc), yc, PULL_Z - 0.065), (X(uc), yc, PULL_Z + 0.065), 0.0075, n + 2, DARK)
        # yellow chevrons round the pull zone only (the pinch point where the leaves meet)
        if lod == 0:
            from se2model.config import DECAL_OFFSET
            F = Face((0, sg * T_, 0), (-sg, 0, 0), (0, 0, 1))                     # a = -sg x on the sg face
            A = lambda u: -sg * X(u)  # noqa: E731
            d = STRIPE_D - DECAL_OFFSET
            for u in (0.0375, 0.1025):
                DC.stripes(P["decal"], F, A(u), PULL_Z, 2 * PULL_HH + 0.04, 0.010, "yellow", d=d, vertical=True)
            for zz in (pz0 - 0.012, pz1 + 0.012):
                DC.stripes(P["decal"], F, A(uc), zz, 0.055, 0.010, "yellow", d=d)
    # the floor brush and the guide shoes (Darker), the carriages (Darker hangers, MetalDull rollers, Brushed axles)
    ub(dk, 0.04, Lw - 0.01, -0.010, 0.010, z0 - 0.0015, z0, DARK)
    for u in (0.14, Lw - 0.14):
        ub(dk, u - 0.03, u + 0.03, -0.005, 0.005, -DH + 0.003, z0 - 0.0015, DARK)
    for u in (CARRIAGE_U, Lw - CARRIAGE_U):
        ub(P["hw"], u - 0.05, u + 0.05, -0.014, 0.014, z1, z1 + 0.006, HARDWARE)
        ub(dk, u - 0.035, u + 0.035, -0.0055, 0.0055, z1 + 0.006, ROLLER_Z + 0.012, DARK)
        for du in (-0.022, 0.022):
            if lod >= 1:
                ub(P["hw"], u + du - ROLLER_R, u + du + ROLLER_R, -0.0235, 0.0235, ROLLER_Z - ROLLER_R,
                   ROLLER_Z + ROLLER_R, HARDWARE)
                continue
            n = 14 if lod == 0 else 8
            for sg in (-1, 1):
                G.cylinder(P["hw"], (X(u + du), sg * 0.0115, ROLLER_Z), (X(u + du), sg * 0.0235, ROLLER_Z), ROLLER_R,
                           n, HARDWARE)
            if lod == 0:
                G.cylinder(P["steel"], (X(u + du), -0.026, ROLLER_Z), (X(u + du), 0.026, ROLLER_Z), 0.0045, 8, STEEL)
    out = [p for p in P.values() if not p.empty()]
    for p in out:   # built in block z; the model's origin hangs on the track
        bmesh.ops.translate(p.bm, vec=(0.0, 0.0, -LEAF_ORIGIN_Z), verts=list(p.bm.verts))
    return out


def leaf_last(lo, hi):
    p = Part("leaf_last")
    G.box(p, lo, hi, PAINT)
    return [p]


def leaf_subparts(spec):
    """{model: (builder(spec, lod), last(lo, hi))} for build_dc.build_generic_subparts."""
    return {m: ((lambda sp, lod, m=m: build_leaf(sp, m, lod)), leaf_last) for m in LEAF_MODELS}
