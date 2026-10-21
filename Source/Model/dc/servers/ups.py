"""UPS server (12U, 2x2x3 cells): a Battery50 clone with two OPEN Power Cell bays (no grate, cage, window or door:
the cell sits exposed in its frame, exactly like vanilla Battery50).

Layout (functional.UPS_BAYS). Two vanilla cells (0.30 x 0.31 m face, 0.355 m deep) cannot sit side by side or stacked
in a 0.5 x 0.5 m face, so the bays run back to back along the 0.75 m depth:
| where            | part                                   | purpose                                                       |
| front, left      | CELL 1 bay: vanilla Battery50 slot frame | hot-swap Power Cell from the cold aisle (aim + use, or the inventory) |
| front, top band  | UPS-12 ID plate, inset LCD, CELL 1 tag | the LCD shows battery charge and load as lit bar graphs        |
| front, right     | control column: LOAD / BATT LED ladders, LINE / BATT lamps, TEST key + power button, intake | the classic UPS front panel |
| ears             | Brushed carry handles on the rack ears | a 12U unit with two 25 kg cells is carried by its ears         |
| back             | CELL 2 bay (same frame, facing back)   | the second cell, swapped from the hot aisle                    |
| back, top strip  | AC inlet, input breaker, 2 output sockets, ground stud, CELL 2 tag | power in, protected power out |
| back, left       | louvred exhaust                        | hot air out (cells and inverter)                              |
The chassis (body, slides, ears with thumbscrews) is the shared server chassis; the core tub is hollow round both
bays (server._tub_with_bays) and the face draws its own front plate instead of the 6U bezel.

Materials (LOD0/1 = 8, the cap): Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite stencils,
AtlasDecal_Parts02 (the vanilla frame's decals) and EmissiveGreen (lit lamps / ladder segments). Unlit lenses are
Darker (no EmissiveOff slot left; the vanilla frame's small EmissiveOff part is remapped to Darker, cellbay.py).
The ladders and the LCD are a static ON-LINE picture (no vanilla component drives a material by charge here).
"""
from .. import functional as FN
from .. import server
from ..style import DARK, HARDWARE, LAMP_GREEN, PAINT, STEEL, YELLOW, lamp, louvre_panel, oct_pts, stencil
from . import cellbay, deco

try:
    from se2model import geom as G
except ImportError:
    G = None

LIT = LAMP_GREEN
HOLE_HALF = 0.196          # plate opening half size: 4 mm inside the frame's 0.2 outer rim (the rim overlaps it)
HOLE_CH = 0.06             # its corner cut (more than the frame's own, so no gap shows at the corners)
FRONT_D = (-0.015, 0.008)  # front plate depth on the front face (as the 6U bezel: y 0.360 .. 0.383)
COL = (0.178, 0.236)       # control column (face a)
REAR_XA = server.BODY_X - server.REAR_CH - 0.002   # rear plate half width (as the 6U rear panel)
LADDER_LIT = {"LOAD": 2, "BATT": 4}                 # the static picture: load 2/5, battery 4/5


def _bays():
    """(front bay, rear bay) as (x, z, mouth y, facing)."""
    (_, xf, zf, yf, ff), (_, xr, zr, yr, fr) = FN.UPS_BAYS
    return (xf, zf, yf, ff), (xr, zr, yr, fr)


def core_bays():
    """The core tub's through-openings (server._tub_with_bays): the front bay's box from the middle forward, the
    rear bay's from the middle back."""
    (xf, zf, _, _), (xr, zr, _, _) = _bays()
    h = FN.CELL_KIT_HALF + 0.002
    ys = 0.016
    return [(server.Y_BACK_CORE, ys, (xr - h, xr + h, zr - h, zr + h)),
            (ys, server.Y_FRONT_CORE, (xf - h, xf + h, zf - h, zf + h))]


def _ladder(P, F, a, b_top, n_lit, lod, label):
    """5-segment LED ladder (bottom-up fill): Darker lens cells, the lit ones EmissiveGreen; label above."""
    pitch, w, h = 0.016, 0.018, 0.008
    d = FRONT_D[1] + 0.003
    if lod == 1:   # one Darker lens strip, the lit segments as flat lens quads on it
        G.prism(P["dark"], F, G.rect(a - w / 2 - 0.002, a + w / 2 + 0.002, b_top - pitch * 4 - h / 2 - 0.002,
                                     b_top + h / 2 + 0.002), d, d + 0.002, DARK)
        d += 0.002
    for k in range(5):
        b = b_top - pitch * k
        lit = (4 - k) < n_lit
        if lod >= 1:
            if lit:
                p = P["decal"]
                f = p.bm.faces.new([p.bm.verts.new(F(x, y, d + 0.0015)) for x, y in G.rect(a - w / 2, a + w / 2,
                                                                                        b - h / 2, b + h / 2)])
                f.material_index = p.mi(LIT)
            continue
        G.prism(P["dark"], F, oct_pts(a - w / 2 - 0.002, b - h / 2 - 0.002, a + w / 2 + 0.002, b + h / 2 + 0.002,
                                      0.002), d, d + 0.002, DARK)
        G.prism(P["hw" if lit else "dark"], F, oct_pts(a - w / 2, b - h / 2, a + w / 2, b + h / 2,
                                                         0.0015 if lod == 0 else 0.0), d + 0.002, d + 0.0035,
                LIT if lit else DARK)
    if lod <= 1:
        stencil(P["decal"], F, a, b_top + 0.016, 0.0065, label, d=d)


def _lcd(P, F, a0, a1, b0, b1, lod):
    """Inset LCD: a Darker bezel, a dark glass, lit content: a battery outline with its charge bars (left) and a
    load bar graph (right)."""
    d = FRONT_D[1]
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, b1, 0.005 if lod <= 1 else 0.0), d, d + 0.004, DARK)
    if lod >= 2:
        return
    p = P["decal"]

    def quad(x0, x1, y0, y1, dd, mat):
        f = p.bm.faces.new([p.bm.verts.new(F(x, y, dd)) for x, y in G.rect(x0, x1, y0, y1)])
        f.material_index = p.mi(mat)
    g0 = d + 0.0042
    quad(a0 + 0.006, a1 - 0.006, b0 + 0.006, b1 - 0.006, g0, DARK)        # glass (Darker, inset in the bezel)
    g = g0 + 0.0004
    bc = (b0 + b1) / 2
    # battery glyph: outline 1.6 mm strokes, nub on the right, 4 of 5 charge bars
    ba0, ba1, bb0, bb1, t = a0 + 0.016, a0 + 0.072, bc - 0.011, bc + 0.011, 0.0016
    for x0, x1, y0, y1 in ((ba0, ba1, bb0, bb0 + t), (ba0, ba1, bb1 - t, bb1), (ba0, ba0 + t, bb0, bb1),
                           (ba1 - t, ba1, bb0, bb1), (ba1, ba1 + 0.004, bc - 0.004, bc + 0.004)):
        quad(x0, x1, y0, y1, g, LIT)
    bw = (ba1 - ba0 - 2 * t - 0.012) / 5
    for k in range(LADDER_LIT["BATT"]):
        x0 = ba0 + t + 0.002 + k * (bw + 0.002)
        quad(x0, x0 + bw, bb0 + t + 0.002, bb1 - t - 0.002, g, LIT)
    # load: 8 rising bars, 3 lit
    la0 = a0 + 0.095
    for k in range(8):
        x0 = la0 + k * 0.008
        hgt = 0.004 + 0.0022 * k
        if k < 3:
            quad(x0, x0 + 0.005, bb0, bb0 + hgt, g, LIT)
    if lod == 0:   # the unlit load bars, a shade above the glass
        for k in range(3, 8):
            x0 = la0 + k * 0.008
            quad(x0, x0 + 0.005, bb0, bb0 + 0.004 + 0.0022 * k, g, DARK)


def _column(P, F, b0, b1, lod):
    """The control column right of the bay: LED ladders (LOAD, BATT), the LINE / BATT status lamps, the TEST key
    and the power button in an oval escutcheon, a honeycomb intake at the bottom."""
    a0, a1 = COL
    d = FRONT_D[1]
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, b1, 0.006 if lod <= 1 else 0.0), d, d + 0.003, DARK)
    al, ar = a0 + 0.015, a1 - 0.014
    _ladder(P, F, al, b1 - 0.040, LADDER_LIT["LOAD"], lod, "LOAD")
    _ladder(P, F, ar, b1 - 0.040, LADDER_LIT["BATT"], lod, "BATT")
    # status lamps: on line (lit) / on battery (unlit)
    lb = b1 - 0.150
    for a, lit, txt in ((al, True, "LINE"), (ar, False, "BATT")):
        if lod == 0:
            lamp(P["hw"], F, a, lb, d + 0.003, r=0.0045, mat=LIT if lit else DARK)
        elif lod == 1:
            server._led(P, F, a, lb, d + 0.003, LIT if lit else DARK, 1, r=0.0045)
        elif lit:
            server._led(P, F, a, lb, d + 0.003, LIT, 1, r=0.0045)   # flat lens quad
        if lod <= 1:
            stencil(P["decal"], F, a, lb - 0.016, 0.0055, txt, d=d + 0.003)
    # oval escutcheon: TEST key (Yellow) over the power button (lit ring)
    ac = (a0 + a1) / 2
    eb1, eb0 = lb - 0.030, lb - 0.122
    G.prism(P["frame"], F, oct_pts(ac - 0.021, eb0, ac + 0.021, eb1, 0.014 if lod <= 1 else 0.0), d + 0.003,
            d + 0.007, PAINT)
    if lod <= 1:
        tb = eb1 - 0.024
        G.cylinder(P["dark"], F(ac, tb, d + 0.006), F(ac, tb, d + 0.009), 0.0135, 16 if lod == 0 else 8, DARK)
        G.cylinder(P["hw"], F(ac, tb, d + 0.009), F(ac, tb, d + 0.015), 0.011, 16 if lod == 0 else 8, YELLOW)
        stencil(P["decal"], F, ac, tb - 0.021, 0.0065, "TEST", d=d + 0.007)
        deco.power_button(P, F, ac, eb0 + 0.022, d + 0.007, lod, r=0.009, ring=LIT)
    # honeycomb intake under it (cooling air for the inverter)
    hb1 = eb0 - 0.008
    if hb1 - (b0 + 0.006) > 0.03:
        deco.honeycomb(P, F, a0 + 0.004, a1 - 0.004, b0 + 0.006, hb1, d + 0.003, d + 0.008, 0.0065,
                       2 if lod >= 1 else 0)


def _ear_handles(P, d, lod):
    """A Brushed carry handle on each rack ear (posts between the thumbscrews, clear of the slot-number notches)."""
    F = server.front_face()
    dd = server.EAR_Y[1] - server.D2          # the ear flange's front
    ax = 0.279
    for sx in (-1, 1):
        a = -sx * ax
        if lod >= 2:   # too thin to read at LOD2 range
            continue
        for b in (-0.075, 0.075):
            G.prism(P["hw"], F, G.rect(a - 0.0045, a + 0.0045, b - 0.006, b + 0.006), dd, dd + 0.026, STEEL)
        G.prism(P["hw"], F, oct_pts(a - 0.006, -0.090, a + 0.006, 0.090, 0.005 if lod == 0 else 0.0),
                dd + 0.022, dd + 0.033, STEEL)


def _front(spec, P, lod):
    d = server.dims(spec)
    F = server.front_face()
    zb, zt = d["zb"], d["zt"]
    (xf, zf, yf, _), _ = _bays()
    ac, bc = -xf, zf
    top = bc + FN.CELL_KIT_HALF + 0.006          # the top band's bottom
    outer = oct_pts(-server.BODY_X, zb + 0.002, server.BODY_X, zt, 0.014 if lod <= 1 else 0.0)
    hole = oct_pts(ac - HOLE_HALF, bc - HOLE_HALF, ac + HOLE_HALF, bc + HOLE_HALF, HOLE_CH)
    G.plate(P["frame"], F, outer, [hole], FRONT_D[0], FRONT_D[1], PAINT)
    kit = cellbay.bay(lod, xf, zf, yf, 1, "cellbay_front")
    if kit:
        P["cellbay_front"] = kit
    _column(P, F, zb + 0.014, top - 0.004, lod)
    # top band: ID plate, inset LCD, CELL 1 tag (over the bay)
    tb0, tb1 = top, zt - 0.010
    if lod <= 1:
        deco.label(P, F, -0.226, -0.128, tb0 + 0.006, tb1 - 0.004, FRONT_D[1], "UPS-12", 0.016, lod)
        deco.label(P, F, 0.090, 0.170, tb0 + 0.010, tb1 - 0.008, FRONT_D[1], "CELL 1", 0.012, lod)
    _lcd(P, F, -0.118, 0.080, tb0 + 0.004, tb1 - 0.002, lod)
    _ear_handles(P, d, lod)


def _rear(spec, P, lod):
    """Back: the plate round the CELL 2 bay, a louvred exhaust left of it, the power strip on top."""
    d = server.dims(spec)
    Fb = server.back_face()
    zb, zt = d["zb"], d["zt"]
    _, (xr, zr, yr, _) = _bays()
    ac, bc = xr, zr                               # back face: a = +x
    D0 = -0.019                                   # plate y -0.353 .. -0.372 (the bay mouth sits just inside it)
    xa = REAR_XA
    outer = oct_pts(-xa, zb + 0.004, xa, zt - 0.004, 0.008 if lod <= 1 else 0.0)
    hole = oct_pts(ac - HOLE_HALF, bc - HOLE_HALF, ac + HOLE_HALF, bc + HOLE_HALF, HOLE_CH)
    ex = (-xa + 0.008, ac - HOLE_HALF - 0.008, bc - 0.15, bc + 0.15)
    # power strip over the bay: a recess in the plate (everything stays inside the back plane)
    sb0, sb1 = bc + FN.CELL_KIT_HALF + 0.008, zt - 0.012
    sc = (sb0 + sb1) / 2
    strip = oct_pts(-xa + 0.010, sb0, xa - 0.010, sb1, 0.005 if lod <= 1 else 0.0)
    holes = [hole] + ([strip, G.rect(ex[0], ex[1], ex[2], ex[3])] if lod <= 1 else [])
    G.plate(P["frame"], Fb, outer, holes, D0, 0.0, PAINT)
    if lod <= 1:
        louvre_panel(P["fine"], Fb, ex[0], ex[2], ex[1], ex[3], 9, lod)
    kit = cellbay.bay(lod, xr, zr, yr, -1, "cellbay_rear")
    if kit:
        P["cellbay_rear"] = kit
    if lod >= 2:   # LOD2: a plain plate there
        return
    G.prism(P["dark"], Fb, strip, D0 - 0.001, D0 + 0.002, DARK)
    s = D0 + 0.002                                # the strip floor (d < 0: inside the back plane)
    # AC inlet: Darker housing, recessed socket with 3 Brushed pins
    ia = -0.175
    G.prism(P["dark"], Fb, oct_pts(ia - 0.024, sc - 0.020, ia + 0.024, sc + 0.020, 0.006), s, s + 0.008, DARK)
    G.prism(P["hw"], Fb, oct_pts(ia - 0.016, sc - 0.012, ia + 0.016, sc + 0.012, 0.005), s + 0.008, s + 0.009, STEEL)
    if lod == 0:
        for pa, pb in ((ia - 0.007, sc + 0.003), (ia + 0.007, sc + 0.003), (ia, sc - 0.006)):
            G.prism(P["fine"], Fb, G.rect(pa - 0.0018, pa + 0.0018, pb - 0.003, pb + 0.003), s + 0.009, s + 0.014,
                    HARDWARE)
    # input breaker: Darker body, Yellow toggle
    ba = -0.120
    G.prism(P["dark"], Fb, oct_pts(ba - 0.014, sc - 0.020, ba + 0.014, sc + 0.020, 0.004), s, s + 0.010, DARK)
    G.prism(P["hw"], Fb, G.rect(ba - 0.006, ba + 0.006, sc - 0.002, sc + 0.012), s + 0.010, s + 0.015, YELLOW)
    # two output sockets
    for oa in (-0.068, -0.024):
        G.prism(P["dark"], Fb, oct_pts(oa - 0.018, sc - 0.018, oa + 0.018, sc + 0.018, 0.007), s, s + 0.006, DARK)
        if lod == 0:
            for pa in (oa - 0.006, oa + 0.006):
                G.prism(P["fine"], Fb, G.rect(pa - 0.0015, pa + 0.0015, sc - 0.004, sc + 0.004), s + 0.006,
                        s + 0.0062, HARDWARE)
    deco.label(P, Fb, 0.022, 0.090, sb0 + 0.008, sb1 - 0.008, s, "CELL 2", 0.012, lod)
    # visual pass 2: CELL 2's own charge ladder (5 segments, the prefilled cell's 30 % = 2 lit), so the hot-aisle
    # side reads as a battery too; a Darker bezel strip, lenses 1 mm proud, all inside the back plane
    la0, lb = 0.100, sc + 0.004
    G.prism(P["fine"], Fb, oct_pts(la0 - 0.004, lb - 0.010, la0 + 0.052, lb + 0.010, 0.003), s, s + 0.004, DARK)
    for k in range(5):
        a = la0 + 0.004 + k * 0.011
        lit = k < 2
        if lod == 0:
            G.prism(P["hw"] if lit else P["fine"], Fb, G.rect(a - 0.004, a + 0.004, lb - 0.006, lb + 0.006), s + 0.004,
                    s + 0.005, LIT if lit else DARK)
        elif lit:
            p = P["decal"]
            f = p.bm.faces.new([p.bm.verts.new(Fb(x, y, s + 0.0045)) for x, y in G.rect(a - 0.004, a + 0.004,
                                                                                       lb - 0.006, lb + 0.006)])
            f.material_index = p.mi(LIT)
    if lod <= 1:
        stencil(P["decal"], Fb, la0 + 0.024, lb - 0.016, 0.0055, "CHARGE", d=s)
    # ground stud
    ga = 0.175
    G.cylinder(P["hw"], Fb(ga, sc, s), Fb(ga, sc, s + 0.005), 0.010, 6, HARDWARE)
    if lod == 0:
        G.cylinder(P["hw"], Fb(ga, sc, s + 0.005), Fb(ga, sc, s + 0.012), 0.004, 8, STEEL)


def build(spec, lod):
    """Parts for one LOD: the shared chassis with a hollow core round the two bays, no 6U bezel / rear panel; the UPS
    front (plate, CELL 1 bay, control column, top band, ear handles) and back (plate, CELL 2 bay, power strip)."""
    if lod == server.n_lods(spec) - 1:
        return server.last_lod(spec)
    P = server.parts()
    _front(spec, P, lod)
    _rear(spec, P, lod)
    return server.chassis(spec, lod, P, rear="none", bezel=False, bays=core_bays())
