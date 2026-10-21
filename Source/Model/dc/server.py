"""Shared server chassis (6U = 2x1x3 cells, 12U = 2x2x3): body, rack ears, slides, handles, rear panel, collision.

Frame (Blender, metres, centred on the origin like the rack: X width, +Y = front = game Forward, Z up):
    cells x +-0.25 (2 cells), y +-0.375 (3 cells), z +-h/2 (h = 0.25 per slot).
In a rack the server's cell box IS one slot (rack.SLOT_CELLS): the front plane y = +0.375 is the 19" rails' ear face,
the side planes x = +-0.25 are the rack's slide-rail planes.

Clearances (render only; the collision fills the cells):
    | what                         | value                  | why                                                   |
    | body sides                   | |x| <= 0.240           | 1 cm inside the slot                                  |
    | server slide (inner member)  | |x| 0.2405 .. 0.247    | 3 mm clear of the rack's slide bolts (1.5 mm proud)   |
    | top                          | z <= h/2 - 0.006       | the half rack's roof sits 5 mm inside its top slot    |
    | back                         | y >= -0.372            | 3 mm inside the back plane                            |
Front zone (y > 0.375, inside the rack's 0.25 m front zone, clear of its doors at y ~0.6):
    - rack ears: L-brackets whose flange lies on the front 19" rail (x 0.240 .. 0.288, y 0.3755 .. 0.3815) with two
      captive thumbscrews per slot over the rail's square holes (x = +-0.262, slot centre +-0.094); the flange is
      notched round the slot centre so the rack's stencilled slot number (left rail) stays readable;
    - the bezel frame (front at y 0.383), pull handles on the bezel stiles (grip at y ~0.41).
"""

import math

try:   # geometry needs Blender; dims / collision are plain Python
    from se2model import geom as G
    from se2model.geom import Face, Part
except ImportError:
    G = Face = Part = None
from . import dims as DM
from .style import DARK, HARDWARE, LAMP_GREEN, PAINT, STEEL, YELLOW, lamp, louvre_panel, oct_pts, stencil

# interface dimensions come from dc/dims.py (shared with rack.py)
W2 = DM.SLOT_HALF_W  # half width of the cells
D2 = DM.SLOT_FRONT_Y  # half depth of the cells (front plane = the rack's 19" rail ear face)
BODY_X = DM.SERVER_BODY_X
SLIDE_X = DM.SERVER_SLIDE_X   # server-side slide member (the rack's outer member web starts at 0.25)
TOP_GAP = DM.SERVER_TOP_GAP   # top clearance (>= 5 mm: the half rack roof)
Y_FRONT_CORE = 0.360  # front of the Darker core = the floor of the bezel recess
Y_BACK = -0.372      # back of the rear plate
Y_BACK_CORE = -0.352  # back of the core (rear plate is 2 cm thick: louvre pockets)
REAR_CH = 0.02       # chamfer of the rear vertical body edges
EAR_X = DM.EAR_X
EAR_Y = (D2 + DM.EAR_GAP, D2 + DM.EAR_GAP + DM.EAR_T)
EAR_NOTCH = DM.EAR_NOTCH  # half height of the slot-number notch
SCREW_X = DM.RAIL_HOLE_X  # the rack's square-hole column
HANDLE_X = 0.226     # pull handles on the bezel stiles
FRAME_IN = 0.212     # bezel opening half width (the per-type faces build inside it)
FRAME_D = (-0.015, 0.008)   # bezel frame depth on the front face (y 0.360 .. 0.383)


def dims(spec):
    n = spec.cells[1]
    assert spec.cells[0] == 2 and spec.cells[2] == 3, spec
    h = DM.SLOT_H * n
    zb, zt = -h / 2, h / 2 - TOP_GAP
    return {"h": h, "zb": zb, "zt": zt, "n": n,
            "slots": [zb + DM.SLOT_H * k for k in range(n)],             # slot floors (local z)
            "centres": [zb + DM.SLOT_H * (k + 0.5) for k in range(n)]}


def size(spec):
    return tuple(0.25 * c for c in spec.cells)


# name -> LOD count fitted to the MEASURED LOD0 bounds (assemble.fit_lods; Keen's checker keys the LOD count on the
# mesh's bounding-box surface, and the full rack sits right at a row threshold: 4 LODs measured, 5 from its cells)
LOD_COUNT = {}


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


def front_face():
    """The server front: a to the viewer's right (-x), b up (z), d forward (+y); origin on the front plane."""
    return Face((0, D2, 0), (-1, 0, 0), (0, 0, 1))


def back_face():
    """The rear panel: a to the viewer's right (+x), b up, d backward (-y); origin on the rear plate's back."""
    return Face((0, Y_BACK, 0), (1, 0, 0), (0, 0, 1))


def face_frame(spec):
    """The front-panel frame the per-type faces build on: front_face() plus
    .area = (a0, a1, b0, b1), the bezel opening; .floor = the d of the Darker recess floor (core front);
    .top = the d of the bezel frame's front; .slots = the slot centres (b) for 12U layouts."""
    d = dims(spec)
    F = front_face()
    F.area = face_frame_area(d)
    F.floor = FRAME_D[0]
    F.top = FRAME_D[1]
    F.slots = d["centres"]
    return F


def parts():
    """The Part set every server LOD writes into (frame = Colorable shells, dark = Darker, hw = metal hardware,
    fine = small unbevelled detail, decal = stencils)."""
    P = {"frame": Part("frame"), "dark": Part("dark"), "fine": Part("fine"), "hw": Part("hw"),
         "decal": Part("decal"),
         # interface parts kept as separate objects so the build can measure them (build_report "geometry")
         "ear": Part("ear"), "slide": Part("slide"), "screw": Part("screw")}
    P["decal"].decal = True
    return P


# ---------------------------------------------------------------------------------------------------- body

def _plan(c, X=BODY_X, Yb=Y_BACK_CORE, Yf=Y_FRONT_CORE, rear=True):
    """Body outline in plan (x, y): rear vertical edges chamfered c (rear=False: a square back)."""
    if not rear:
        return [(-X, Yb), (X, Yb), (X, Yf), (-X, Yf)]
    return [(-X, Yb + c), (-X + c, Yb), (X - c, Yb), (X, Yb + c), (X, Yf), (-X, Yf)]


def _tub_with_bays(p, mat, d, c, X, zt, bays):
    """The core tub built round through-bays (the UPS cell bays): bays = [(y0, y1, (x0, x1, z0, z1))], one hollow
    segment per bay, its y span (y0 < y1) covering the core from Y_BACK_CORE to Y_FRONT_CORE together. Each segment is
    two side columns (plan prisms; the one touching the back keeps the chamfered rear corners) and a floor and a roof
    slab between them, leaving the bay's x / z box open for the kit sleeve. A segment whose box is None is solid."""
    Fz = Face((0, 0, 0), (1, 0, 0), (0, 1, 0))
    zb = d["zb"]
    for y0, y1, box in bays:
        back = abs(y0 - Y_BACK_CORE) < 1e-9
        if box is None:   # a solid segment (the KVM's core behind its drawer bay)
            G.prism(p, Fz, _plan(c, X, y0, y1, rear=back and c > 0), zb, zt, mat)
            continue
        hx0, hx1, hz0, hz1 = box
        for xa, xb, side in ((-X, hx0, -1), (hx1, X, 1)):
            if xb - xa <= 1e-4:
                continue
            if back and c > 0:   # outer rear corner chamfered like _plan
                xo, xi = (xa, xb) if side < 0 else (xb, xa)
                w = abs(xo - xi)
                if w > c:
                    pts = [(xo, y0 + c), (xo - side * c, y0), (xi, y0), (xi, y1), (xo, y1)]
                else:            # a column narrower than the chamfer: its back is the chamfer line
                    pts = [(xo, y0 + c), (xi, y0 + c - w), (xi, y1), (xo, y1)]
                if side > 0:
                    pts.reverse()
                G.prism(p, Fz, pts, zb, zt, mat)
            else:
                G.box(p, (xa, y0, zb), (xb, y1, zt), mat)
        G.box(p, (hx0, y0, zb), (hx1, y1, hz0), mat)
        if hz1 < zt - 1e-4:
            G.box(p, (hx0, y0, hz1), (hx1, y1, zt), mat)


TYPE_ID = {"Compute": "CX-06", "Storage": "ST-09", "Switch": "SW-24", "Blank": "BL-06", "Timer": "TMR-06",
           "EventCtl": "EVC-06", "Status": "STA-06", "Programmable": "PRG-06", "KVM": "KVM-06", "UPS": "UPS-12"}
TUB_X0 = 0.226        # LOD0 core tub half width: 1 cm inside the skins, room for the layered side panels
TUB_DROP0 = 0.012     # LOD0 core tub top below zt: room for the recessed lid field


def _body(P, d, lod, bays=None, variant=None):
    """Darker core (the steel chassis tub) with Colorable skins: side skins, and a top split into a front service
    lid and a rear cover, with a real 8 mm shadow gap. LOD0 layers them like a Keen face:
    - lid: a framed lid over a recessed field with two stamped stiffening beads, a flush lid-release latch (Darker
      pocket, Brushed T-handle, Yellow release tab) and a Darker type plate with the server's ID stencil;
    - rear cover: three transverse stiffening beads and a cut-in exhaust slot field over the PSU bays;
    - sides: a framed skin over a recessed panel (Darker tub behind), a cold-air intake slot row at the front,
      a long stamped swage, rivets along the frame and a Darker rating plate.
    bays: through-openings in the core (see _tub_with_bays; the UPS cell bays), else a solid tub."""
    zb, zt = d["zb"], d["zt"]
    Fz = Face((0, 0, 0), (1, 0, 0), (0, 1, 0))
    c = REAR_CH if lod <= 2 else 0.0
    if lod >= 2:
        if bays:
            _tub_with_bays(P["frame"], PAINT, d, c, BODY_X, zt, bays)
        else:
            G.prism(P["frame"], Fz, _plan(c), zb, zt, PAINT)
        return
    if lod == 1:
        if bays:
            _tub_with_bays(P["dark"], DARK, d, c, BODY_X * 0.988, zt - 0.004, bays)
        else:
            G.prism(P["dark"], Fz, [(x * 0.988, y) for x, y in _plan(c)], zb, zt - 0.004, DARK)        # core tub
        for sx in (-1, 1):   # side skins, stop 8 mm under the top (shadow gap to the lid)
            x0, x1 = sorted((sx * (BODY_X - 0.003), sx * BODY_X))
            G.box(P["frame"], (x0, Y_BACK_CORE + c + 0.004, zb + 0.004), (x1, Y_FRONT_CORE - 0.002, zt - 0.010),
                  PAINT)
        yg0, yg1 = -0.030, -0.022
        rear = [(-BODY_X + 0.001, Y_BACK_CORE + c), (-BODY_X + 0.001 + c, Y_BACK_CORE + 0.001),
                (BODY_X - 0.001 - c, Y_BACK_CORE + 0.001), (BODY_X - 0.001, Y_BACK_CORE + c),
                (BODY_X - 0.001, yg0), (-BODY_X + 0.001, yg0)]
        G.prism(P["frame"], Fz, rear, zt - 0.004, zt, PAINT)
        Ft = Face((0, 0, zt), (1, 0, 0), (0, 1, 0))
        G.prism(P["frame"], Ft, G.rect(-BODY_X + 0.001, BODY_X - 0.001, yg1, Y_FRONT_CORE - 0.001), -0.004, 0.0, PAINT)
        return
    _body_lod0(P, d, c, bays, variant)


def _body_lod0(P, d, c, bays, variant):
    zb, zt = d["zb"], d["zt"]
    Fz = Face((0, 0, 0), (1, 0, 0), (0, 1, 0))
    X = BODY_X
    tz = zt - TUB_DROP0
    if bays:
        _tub_with_bays(P["dark"], DARK, d, c, TUB_X0, tz, bays)
    else:
        G.prism(P["dark"], Fz, _plan(c, X=TUB_X0), zb, tz, DARK)
    _sides0(P, d, c)
    # ---- top: rear cover | 8 mm shadow gap | service lid
    yg0, yg1 = -0.030, -0.022
    Ft = Face((0, 0, zt), (1, 0, 0), (0, 1, 0))
    rear = [(-X + 0.001, Y_BACK_CORE + c), (-X + 0.001 + c, Y_BACK_CORE + 0.001),
            (X - 0.001 - c, Y_BACK_CORE + 0.001), (X - 0.001, Y_BACK_CORE + c), (X - 0.001, yg0), (-X + 0.001, yg0)]
    # exhaust slots over the PSU bays (rear panel PSUs at x +0.10..+0.21)
    vy = (Y_BACK_CORE + 0.05, Y_BACK_CORE + 0.20)
    slots = [G.rect(xc - 0.0055, xc + 0.0055, vy[0], vy[1]) for xc in (0.205, 0.183, 0.161, 0.139, 0.117)]
    G.plate(P["frame"], Ft, rear, slots, -0.005, -0.001, PAINT, bottom=False)
    for k in range(3):   # transverse stiffening beads (stamped)
        yb = Y_BACK_CORE + 0.075 + k * 0.095
        x1 = 0.07 if k < 2 else X - 0.03       # the first two stop short of the vent field
        G.prism(P["fine"], Ft, oct_pts(-X + 0.03, yb - 0.006, x1, yb + 0.006, 0.004), -0.001, 0.0, PAINT)
    # lid: frame ring round a recessed field
    L0, L1 = yg1, Y_FRONT_CORE - 0.001
    fx, fy0, fy1 = X - 0.020, L0 + 0.020, L1 - 0.026
    G.plate(P["frame"], Ft, G.rect(-X + 0.001, X - 0.001, L0, L1), [oct_pts(-fx, fy0, fx, fy1, 0.010)], -0.005, 0.0,
            PAINT, bottom=False)
    lat = (0.0, L1 - 0.075, 0.075, 0.022)      # latch pocket centre / half sizes (front centre of the lid)
    pocket = oct_pts(lat[0] - lat[2], lat[1] - lat[3], lat[0] + lat[2], lat[1] + lat[3], 0.008)
    G.plate(P["fine"], Ft, oct_pts(-fx, fy0, fx, fy1, 0.010), [pocket], -0.010, -0.007, PAINT, bottom=False)
    for xb in (-0.115, 0.115):   # stamped beads along the lid
        G.prism(P["fine"], Ft, oct_pts(xb - 0.008, fy0 + 0.03, xb + 0.008, fy1 - 0.03, 0.006), -0.007, -0.0045,
                PAINT)
    # lid-release latch: Darker pocket floor, Brushed T-handle lying flat, Yellow release tab
    G.prism(P["fine"], Ft, pocket, -0.0115, -0.0095, DARK)
    G.prism(P["hw"], Ft, oct_pts(-0.055, lat[1] - 0.007, 0.040, lat[1] + 0.007, 0.004), -0.0095, -0.006, STEEL)
    G.prism(P["hw"], Ft, oct_pts(-0.062, lat[1] - 0.015, -0.045, lat[1] + 0.015, 0.004), -0.0095, -0.006, STEEL)
    G.prism(P["fine"], Ft, oct_pts(0.046, lat[1] - 0.010, 0.066, lat[1] + 0.010, 0.003), -0.0095, -0.0065, YELLOW)
    # captive screws at the lid's rear edge (release them, then the latch)
    for x in (-0.17, 0.17):
        G.cylinder(P["hw"], Ft(x, L0 + 0.010, -0.005), Ft(x, L0 + 0.010, -0.001), 0.0065, 8, HARDWARE)
    # type plate: Darker, white ID stencil + "SERVICE"
    if variant in TYPE_ID:   # read from the front: a = -x (the viewer's right), b = -y (away from the viewer)
        Fr = Face((0, 0, zt), (-1, 0, 0), (0, -1, 0))
        pa0, pa1, pb0, pb1 = -0.20, -0.04, -(fy0 + 0.080), -(fy0 + 0.014)
        G.prism(P["dark"], Fr, oct_pts(pa0, pb0, pa1, pb1, 0.008), -0.007, -0.004, DARK)
        stencil(P["decal"], Fr, pa0 + 0.012, pb1 - 0.024, 0.020, TYPE_ID[variant], d=-0.004, align="left")
        stencil(P["decal"], Fr, pa0 + 0.012, pb0 + 0.012, 0.009, "SERVICE - SCREWS THEN LATCH", d=-0.004,
                align="left")


def _sides0(P, d, c):
    """LOD0 side skins: frame ring (Colorable) over a recessed panel, intake slot row, swage, rivets, rating plate."""
    zb, zt = d["zb"], d["zt"]
    X = BODY_X
    y0, y1 = Y_BACK_CORE + c + 0.004, Y_FRONT_CORE - 0.002
    z0, z1 = zb + 0.004, zt - 0.010
    h = z1 - z0
    for sx in (-1, 1):
        Fs = Face((sx * X, 0, 0), (0, sx, 0), (0, 0, 1))
        A = lambda y: sx * y                                     # noqa: E731  face a for a block y
        ra = sorted((A(y0), A(y1)))
        ia = sorted((A(y0 + 0.024), A(y1 - 0.030)))
        inner = oct_pts(ia[0], z0 + 0.016, ia[1], z1 - 0.016, 0.010)
        G.plate(P["frame"], Fs, G.rect(ra[0], ra[1], z0, z1), [inner], -0.004, 0.0, PAINT, bottom=False)
        # the recessed panel: cold-air intake slots near the front, a swage along it
        ny = 5
        holes = []
        for k in range(ny):
            yc = y1 - 0.060 - k * 0.020
            r = sorted((A(yc - 0.0055), A(yc + 0.0055)))
            holes.append(G.rect(r[0], r[1], z0 + 0.034, z1 - 0.034))
        G.plate(P["fine"], Fs, inner, holes, -0.0085, -0.0055, PAINT, bottom=False)
        ys = sorted((A(y0 + 0.05), A(y1 - 0.22)))
        zs = z0 + 0.62 * h
        G.prism(P["fine"], Fs, oct_pts(ys[0], zs - 0.007, ys[1], zs + 0.007, 0.005), -0.0055, -0.003, PAINT)
        # rating plate (Darker, white stencil) at the rear of the panel
        rp = sorted((A(y0 + 0.05), A(y0 + 0.17)))
        pb = z0 + 0.20 * h + 0.012
        for zf in d["slots"]:   # keep the plate off the slide member that runs over it (the 12U UPS)
            lo, hi = zf + DM.SERVER_SLIDE_Z[0], zf + DM.SERVER_SLIDE_Z[1]
            if pb - 0.016 < hi + 0.001 and pb + 0.016 > lo - 0.001:
                pb = hi + 0.006 + 0.016
        G.prism(P["dark"], Fs, oct_pts(rp[0], pb - 0.016, rp[1], pb + 0.016, 0.005), -0.0055, -0.0025, DARK)
        stencil(P["decal"], Fs, (rp[0] + rp[1]) / 2, pb + 0.005, 0.009, "MAX 45 KG", d=-0.0025)
        stencil(P["decal"], Fs, (rp[0] + rp[1]) / 2, pb - 0.007, 0.007, "LIFT 2 PERSON", d=-0.0025)
        # rivets along the frame's top and bottom rails
        n = 3   # ends and middle of each rail
        for k in range(n):
            yc = y0 + 0.04 + k * (y1 - y0 - 0.08) / (n - 1)
            for zr in (z0 + 0.008,):   # bottom rail only (the top rail sits under the lid edge)
                G.cylinder(P["hw"], Fs(A(yc), zr, -0.0005), Fs(A(yc), zr, 0.0015), 0.0035, 6, HARDWARE)


def _slides(P, d, lod):
    """Server-side slide (inner) members: Brushed steel, at the rack's slide height in each slot, with a Yellow
    release latch at the front end (press to pull the server off the slides)."""
    if lod >= 2:
        return
    for zf in d["slots"]:
        for sx in (-1, 1):
            x0, x1 = sorted((sx * SLIDE_X[0], sx * SLIDE_X[1]))
            G.box(P["slide"], (x0, -0.335, zf + DM.SERVER_SLIDE_Z[0]), (x1, 0.300, zf + DM.SERVER_SLIDE_Z[1]), STEEL)
            xl0, xl1 = sorted((sx * SLIDE_X[0], sx * (SLIDE_X[1] - 0.0005)))
            G.box(P["fine"], (xl0, 0.318, zf + DM.SERVER_SLIDE_Z[0] + 0.004), (xl1, 0.336, zf + DM.SERVER_SLIDE_Z[1] - 0.004),
                  YELLOW)


# ---------------------------------------------------------------------------------------------------- front

def _ear_outline(d, x0, x1, xi, c=0.008, e=0.004):
    """Ear flange outline in (x, z) for the +x ear: full height, notched round each slot centre."""
    zb, zt = d["zb"] + 0.002, d["zt"]
    pts = [(x0, zb), (x1 - c, zb), (x1, zb + c)]
    for zc in d["centres"]:
        n = EAR_NOTCH
        pts += [(x1, zc - n - e), (x1 - e, zc - n), (xi, zc - n), (xi, zc + n), (x1 - e, zc + n), (x1, zc + n + e)]
    pts += [(x1, zt - c), (x1 - c, zt), (x0, zt)]
    return pts


def _ears(P, d, lod):
    """Rack ears: an L-bracket per side. The flange lies on the 19" rail (2 captive thumbscrews per slot over the
    rail's square holes); the leg is riveted to the body side inside the slot. The notch at each slot centre
    keeps the rack's slot number readable with the server installed."""
    F = front_face()
    for sx in (-1, 1):
        if lod >= 2:
            a0, a1 = sorted((-sx * EAR_X[0], -sx * EAR_X[1]))
            G.prism(P["ear"], F, G.rect(a0, a1, d["zb"] + 0.002, d["zt"]), EAR_Y[0] - D2, EAR_Y[1] - D2, PAINT)
        else:
            pts = [(-sx * x, z) for x, z in _ear_outline(d, EAR_X[0], EAR_X[1], W2 - 0.0005)]
            if sx < 0:
                pts.reverse()
            G.prism(P["ear"], F, pts, EAR_Y[0] - D2, EAR_Y[1] - D2, PAINT)
            # leg on the body side (inside the slot clearance: x <= 0.2435)
            x0, x1 = sorted((sx * BODY_X, sx * 0.2435))
            G.box(P["ear"], (x0, 0.330, d["zb"] + 0.012), (x1, EAR_Y[1] - 0.001, d["zt"] - 0.012), PAINT)
            if lod == 0:   # flush rivets through the leg (heads 2 mm: x <= 0.2455)
                Fs = Face((sx * 0.2435, 0, 0), (0, sx, 0), (0, 0, 1))
                for zc in d["centres"]:
                    for dz in (-0.06, 0.06):
                        G.cylinder(P["fine"], Fs(sx * 0.352, zc + dz, -0.0005), Fs(sx * 0.352, zc + dz, 0.002), 0.0045, 8,
                                   HARDWARE)
        # captive thumbscrews over the rail's square holes
        dd = EAR_Y[1] - D2
        for zf in d["slots"]:
            for zo in DM.screw_offsets():
                a, b = -sx * SCREW_X, zf + zo
                if lod >= 2:
                    G.box(P["screw"], (sx * SCREW_X - 0.007, EAR_Y[1], b - 0.007), (sx * SCREW_X + 0.007,
                          EAR_Y[1] + 0.010, b + 0.007), HARDWARE)
                    continue
                n = 12 if lod == 0 else 8
                if lod == 0:   # captive washer
                    G.cylinder(P["hw"], F(a, b, dd - 0.0005), F(a, b, dd + 0.003), 0.0105, n, DARK)
                G.cylinder(P["screw"], F(a, b, dd + 0.003), F(a, b, dd + 0.013), 0.0085, n, HARDWARE)   # knurled head
                if lod == 0:   # driver slot across the head
                    G.prism(P["fine"], F, G.rect(a - 0.006, a + 0.006, b - 0.0012, b + 0.0012), dd + 0.013,
                            dd + 0.0136, DARK)


def _bezel(P, d, lod):
    """The front bezel: a Colorable frame (chunky clipped corners) round the Darker recess the per-type face
    sits in, with a pull handle on each stile (one per slot band) on Darker standoffs."""
    F = front_face()
    zb, zt = d["zb"], d["zt"]
    outer = oct_pts(-BODY_X, zb + 0.002, BODY_X, zt, 0.014 if lod <= 1 else 0.0)
    a0, a1, b0, b1 = face_frame_area(d)
    hole = oct_pts(a0, b0, a1, b1, 0.006 if lod <= 1 else 0.0)
    G.plate(P["frame"], F, outer, [hole], FRAME_D[0], FRAME_D[1], PAINT)
    for zc in d["centres"]:
        for sx in (-1, 1):
            a = -sx * HANDLE_X
            hz = 0.062
            if lod >= 2:
                G.prism(P["hw"], F, G.rect(a - 0.0065, a + 0.0065, zc - hz - 0.008, zc + hz + 0.008), FRAME_D[1],
                        FRAME_D[1] + 0.028, STEEL)
                continue
            for bz in (zc - hz, zc + hz):   # standoffs
                G.prism(P["dark"], F, oct_pts(a - 0.0075, bz - 0.009, a + 0.0075, bz + 0.009, 0.003), FRAME_D[1],
                        FRAME_D[1] + 0.020, DARK)
            # the grip (Brushed bar, chamfered ends)
            G.prism(P["hw"], F, oct_pts(a - 0.0065, zc - hz - 0.010, a + 0.0065, zc + hz + 0.010, 0.004),
                    FRAME_D[1] + 0.018, FRAME_D[1] + 0.030, STEEL)
            if lod == 0:   # screws holding the standoffs
                for bz in (zc - hz, zc + hz):
                    G.cylinder(P["fine"], F(a, bz + 0.0, FRAME_D[1] + 0.030), F(a, bz, FRAME_D[1] + 0.0315),
                               0.0035, 6, HARDWARE)


def face_frame_area(d):
    return (-FRAME_IN, FRAME_IN, d["zb"] + 0.020, d["zt"] - 0.018)


# ---------------------------------------------------------------------------------------------------- rear

def _rear(P, d, lod, kind="psu", lamp=LAMP_GREEN, variant=None):
    """Rear panel (seen from the hot aisle / an open rack's back):
    - "psu": two hot-swap power supplies (pull handle, inlet, grille, power-OK lamp) on the right, a louvred
      exhaust over the fans on the left, an I/O plate with network ports and the chassis ground stud below it;
      lamp = the power-OK lamp material (one name, or one per PSU: functional servers put their indicator parts here);
    - "baffle": a passive filler (the blank) - one louvred air baffle, no power."""
    Fb = back_face()
    zb, zt = d["zb"], d["zt"]
    xa = BODY_X - REAR_CH - 0.002
    outer = oct_pts(-xa, zb + 0.004, xa, zt - 0.004, 0.008 if lod <= 1 else 0.0)
    D0 = Y_BACK - Y_BACK_CORE      # -0.020: plate from the core back (d = -0.02) to the back face (d = 0)
    if lod >= 2:
        G.prism(P["frame"], Fb, outer, D0, 0.0, PAINT)
        if kind == "psu":
            for a0 in (0.098, 0.158):
                G.prism(P["dark"], Fb, G.rect(a0, a0 + 0.054, zb + 0.016, zt - 0.016), D0, 0.002, DARK)
        return
    if kind == "baffle":
        hx, hb = (-0.17, 0.17), (zb + 0.04, zt - 0.04)
        G.plate(P["frame"], Fb, outer, [G.rect(hx[0], hx[1], hb[0], hb[1])], D0, 0.0, PAINT)
        louvre_panel(P["fine"], Fb, hx[0], hb[0], hx[1], hb[1], max(3, int((hb[1] - hb[0]) / 0.03)), lod)
        if lod <= 1:   # Darker tab with a white stencil: a passive filler, nothing to plug in
            G.prism(P["dark"], Fb, oct_pts(-0.05, zb + 0.012, 0.05, zb + 0.034, 0.004), 0.0, 0.001, DARK)
            stencil(P["decal"], Fb, 0.0, zb + 0.023, 0.012, "NO POWER", d=0.0008)
        return
    ex = (-0.205, 0.085)
    zc = (zb + zt) / 2
    exb = (zc - 0.01, zt - 0.02)
    iob = (zb + 0.018, zc - 0.028)
    psu = list(DM.SERVER_PSU_X)   # (dims: single-sourced with the inlets, for live cabling)
    fans = variant in REAR_FANS and lod == 0
    if fans:   # compute: round exhaust fans instead of the louvre (the front fan wall's hot air out)
        fr = min(0.042, (exb[1] - exb[0]) / 2 - 0.004)
        fb = (exb[0] + exb[1]) / 2
        fcs = [ex[0] + 0.07 + k * 0.15 for k in range(2)]
        holes = [[(c + x, fb + y) for x, y in G.ngon(fr, 12)] for c in fcs]
    else:
        holes = [G.rect(ex[0], ex[1], exb[0], exb[1])]
    holes += [G.rect(ex[0], ex[1], iob[0], iob[1])]
    holes += [G.rect(a0, a1, zb + 0.014, zt - 0.014) for a0, a1 in psu]
    G.plate(P["frame"], Fb, outer, holes, D0, 0.0, PAINT)
    if fans:
        for c in fcs:
            G.ring(P["fine"], Fb, G.ngon(fr, 12), G.ngon(fr - 0.005, 12), D0, -0.002, DARK, ca=c, cb=fb)
            G.cylinder(P["hw"], Fb(c, fb, -0.014), Fb(c, fb, -0.004), fr * 0.32, 8, DARK)
            for ang in (math.pi / 4, 3 * math.pi / 4):
                ca_, sa_ = math.cos(ang), math.sin(ang)
                r1 = fr - 0.007
                G.prism(P["hw"], Fb, [(c - ca_ * r1 - sa_ * 0.0012, fb - sa_ * r1 + ca_ * 0.0012),
                                      (c + ca_ * r1 - sa_ * 0.0012, fb + sa_ * r1 + ca_ * 0.0012),
                                      (c + ca_ * r1 + sa_ * 0.0012, fb + sa_ * r1 - ca_ * 0.0012),
                                      (c - ca_ * r1 + sa_ * 0.0012, fb - sa_ * r1 - ca_ * 0.0012)], -0.005, -0.0025,
                        HARDWARE)
    else:
        louvre_panel(P["fine"], Fb, ex[0], exb[0], ex[1], exb[1], max(4, int((exb[1] - exb[0]) / 0.022)), lod)
    # I/O plate: Darker, network ports (Brushed shells, dark sockets) and a management port, LOD0
    G.prism(P["dark"], Fb, G.rect(ex[0] + 0.002, ex[1] - 0.002, iob[0] + 0.002, iob[1] - 0.002), D0, -0.008, DARK)
    if lod == 0:
        bc = (iob[0] + iob[1]) / 2
        io = REAR_IO.get(variant, "net4")
        if io == "net16":    # switch / event controller: two rows of eight uplink ports
            for r_, bb in enumerate((bc + 0.0085, bc - 0.0085)):
                for i in range(6):
                    a = ex[0] + 0.03 + 0.026 * i
                    G.prism(P["hw"], Fb, G.rect(a - 0.0095, a + 0.0095, bb - 0.0072, bb + 0.0072), -0.008, -0.004,
                            STEEL)
                    G.prism(P["fine"], Fb, G.rect(a - 0.007, a + 0.007, bb - 0.005, bb + 0.0045), -0.004, -0.0036,
                            DARK)
        elif io == "sas":    # storage: two wide expander connectors, each with a pull tab
            for i in range(2):
                a = ex[0] + 0.05 + 0.085 * i
                G.prism(P["hw"], Fb, oct_pts(a - 0.032, bc - 0.011, a + 0.032, bc + 0.011, 0.004), -0.008, -0.003,
                        STEEL)
                G.prism(P["fine"], Fb, G.rect(a - 0.027, a + 0.027, bc - 0.0065, bc + 0.006), -0.003, -0.0026, DARK)
                G.prism(P["fine"], Fb, G.rect(a - 0.010, a + 0.010, bc - 0.016, bc - 0.012), -0.008, -0.002, YELLOW)
        else:
            for i in range(4):
                a = ex[0] + 0.03 + 0.036 * i
                G.prism(P["hw"], Fb, G.rect(a - 0.012, a + 0.012, bc - 0.01, bc + 0.01), -0.008, -0.003, STEEL)
                G.prism(P["fine"], Fb, G.rect(a - 0.009, a + 0.009, bc - 0.007, bc + 0.006), -0.003, -0.0026, DARK)
        # ground stud
        G.cylinder(P["hw"], Fb(ex[1] - 0.03, bc, -0.008), Fb(ex[1] - 0.03, bc, -0.004), 0.011, 6, HARDWARE)
        G.cylinder(P["hw"], Fb(ex[1] - 0.03, bc, -0.004), Fb(ex[1] - 0.03, bc, -0.0005), 0.0045, 8, STEEL)
    md = -0.016   # PSU module faces sit 1.6 cm into their bays, so the pull handles stay inside the back plane
    for i, (a0, a1) in enumerate(psu):
        b0, b1 = zb + 0.016, zt - 0.016
        ac = (a0 + a1) / 2
        G.prism(P["dark"], Fb, oct_pts(a0 + 0.002, b0, a1 - 0.002, b1, 0.004), D0, md, DARK)   # module face
        # PSU fan grille (MetalDull frame, Darker slots at LOD0) and the power inlet
        G.prism(P["fine"], Fb, G.rect(a0 + 0.008, a1 - 0.008, b1 - 0.075, b1 - 0.012), md, md + 0.0005, HARDWARE)
        if lod == 0:
            for k in range(5):
                bb = b1 - 0.020 - 0.012 * k
                G.prism(P["fine"], Fb, G.rect(a0 + 0.010, a1 - 0.010, bb - 0.003, bb + 0.003), md + 0.0005,
                        md + 0.001, DARK)
        ib0, ib1 = DM.SERVER_INLET_B   # the power inlet shell (its face: dims.SERVER_INLET_FACE_Y)
        G.prism(P["hw"], Fb, oct_pts(ac - 0.014, b0 + ib0, ac + 0.014, b0 + ib1, 0.004), md, md + 0.007, STEEL)
        G.prism(P["fine"], Fb, G.rect(ac - 0.009, ac + 0.009, b0 + 0.017, b0 + 0.035), md + 0.007, md + 0.0074, DARK)
        # pull handle: Brushed loop on two posts, mid module
        hb0, hb1 = b0 + 0.06, b1 - 0.09
        if hb1 - hb0 > 0.03:
            for bb in (hb0, hb1):
                G.prism(P["hw"], Fb, G.rect(ac - 0.004, ac + 0.004, bb - 0.004, bb + 0.004), md, -0.006, STEEL)
            G.prism(P["hw"], Fb, oct_pts(ac - 0.005, hb0 - 0.006, ac + 0.005, hb1 + 0.006, 0.003), -0.007, -0.001,
                    STEEL)
        _led(P, Fb, a0 + 0.012, b0 + 0.052, md, lamp if isinstance(lamp, str) else lamp[i], lod, r=0.005)


REAR_FANS = ("Compute",)
REAR_IO = {"Switch": "net16", "EventCtl": "net16", "Storage": "sas"}


def _led(P, F, a, b, d, mat, lod, r=0.006):
    """A status lamp: LOD0 a round lens in a Darker bezel (style.lamp); LOD1 a square lens (cheap)."""
    if lod == 0:
        lamp(P["hw"], F, a, b, d, r=r, mat=mat, lod=0)
    elif lod == 1:   # a single lens quad 1.5 mm proud (decal part: authored winding faces out)
        p = P["decal"]
        f = p.bm.faces.new([p.bm.verts.new(F(x, y, d + 0.0015)) for x, y in G.rect(a - r, a + r, b - r, b + r)])
        f.material_index = p.mi(mat)


# ---------------------------------------------------------------------------------------------------- assembly

def chassis(spec, lod, P=None, rear=None, lamp=LAMP_GREEN, bezel=True, bays=None):
    """The shared chassis Parts for one LOD (not the last-LOD box): body, slides, ears with thumbscrews, bezel
    frame with handles, rear panel (lamp: its PSU power-OK lamp material, see _rear). Pass P to keep writing into
    the same Part set as the face. bezel=False / rear="none": the face builds its own front plate / rear panel;
    bays: through-openings in the core tub (_body)."""
    d = dims(spec)
    P = P or parts()
    if lod == 0:
        P["frame"].bevel = (0.004, 1)
        P["ear"].bevel = (0.004, 1)
        P["dark"].bevel = (0.003, 1)
    _body(P, d, lod, bays, spec.variant)
    _slides(P, d, lod)
    _ears(P, d, lod)
    if bezel:
        _bezel(P, d, lod)
    rear = rear or ("baffle" if spec.variant == "Blank" else "psu")
    if rear != "none":
        _rear(P, d, lod, rear, lamp, spec.variant)
    return [p for p in P.values() if not p.empty()]


def build(spec, lod, face, lamp=LAMP_GREEN):
    """Every server type's LOD builder: the last LOD is the 12-tri LastLOD box; otherwise face(spec, P, lod) writes
    the per-type front into a fresh Part set and the shared chassis is added round it (lamp: the rear PSU lamps)."""
    if lod == n_lods(spec) - 1:
        return last_lod(spec)
    P = parts()
    face(spec, P, lod)
    return chassis(spec, lod, P, lamp=lamp)


def last_lod(spec):
    """The 12-triangle box with the baked LastLOD material, inside the clearances."""
    d = dims(spec)
    p = Part("lastlod")
    G.box(p, (-BODY_X, Y_BACK, d["zb"]), (BODY_X, D2, d["zt"]), f"{spec.name}_LastLOD")
    return [p]


# ---------------------------------------------------------------------------------------------------- collision

def collision(spec):
    """{"regular": [...], "occupancy": [], "mount": [...]}: one physics box filling the cells exactly (so every
    cell is occupied), and 5 mm mount hints lying on the bottom, top, side and back planes (standalone use: floor,
    stacking, neighbours, a wall behind; in a rack the side hints meet the rack's rail hints). The front gets no
    hint: it is the working face; nor does the UPS's back (its second cell bay)."""
    h2 = 0.125 * spec.cells[1]
    t = 0.005
    reg = [("body", (-W2, -D2, -h2), (W2, D2, h2))]
    mnt = [("bottom", (-W2, -D2, -h2), (W2, D2, -h2 + t)),
           ("top", (-W2, -D2, h2 - t), (W2, D2, h2)),
           ("left", (-W2, -D2, -h2), (-W2 + t, D2, h2)),
           ("right", (W2 - t, -D2, -h2), (W2, D2, h2)),
           ("back", (-W2, -D2, -h2), (W2, -D2 + t, h2))]
    if spec.variant == "UPS":
        mnt = [m for m in mnt if m[0] != "back"]
    return {"regular": reg, "occupancy": [], "mount": mnt}
