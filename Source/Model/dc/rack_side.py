"""Rack side panels as a STATIC subpart (visual pass 2): its own model and LOD budget, so the 42U frame's cap stops
blocking the most-seen face (the end of a row). One model, built for the block's +x side in the centred block frame;
the integration places it twice as static client-prefab children: at the block origin (right side) and turned
180 deg about the vertical (left side; the hatch then sits toward the rear on that side, as on real paired racks).

Purpose of every part (the side column holds the rack's PDU and the coolant manifold for the tray fans / rear heat
exchanger):
| part                                   | purpose                                                              |
| frame plate (Colorable, flush)         | the side skin: carries the openings, stiff border, corner bolts      |
| Darker casing                          | the column's inner wall, seen through every opening                   |
| PDU service hatch (inset 8 mm)         | access to the power distribution unit: hinges at the rear edge,       |
|                                        | two quarter-turn latches + a grip pocket at the front, a stiffening   |
|                                        | rib, "PDU ACCESS" stencil and the high-voltage warning                |
| rack placard (Yellow frame, Darker)    | "RACK ID" over a blank Brushed write-on tag (no baked ID: the ID is   |
|                                        | the rack-label LCD's), readable from the end of the aisle             |
| coolant conduit (2 Brushed pipes)      | supply / return in a recessed channel at the rear edge; Brushed       |
|                                        | brackets with bolts; Yellow collars + black union nuts where they     |
|                                        | turn into the column                                                  |
| flow meter with sight glass            | coolant flow check: Darker housing on the pipes, a lit level bar      |
| framed vent recess (two louvred bays)  | side intake for the PDU's cooling, Brushed bay frames, Yellow filter  |
|                                        | release tabs                                                          |
| service band                           | grounding stud + maintenance caution, asset barcode                   |
Nothing stands past x = rack.XO (the render inset); decals stay <= 2 mm under it."""
import math

from . import rack as R
from .style import DARK, HARDWARE, LAMP_GREEN, PAINT, STEEL, YELLOW, hazard_triangle, louvre_panel, oct_pts, stencil

try:
    from mathutils import Matrix
    from se2model import geom as G
    from se2model.geom import Part
    from se2model.config import S2
except ImportError:
    Matrix = G = Part = S2 = None

SIDE_SUB = "RackSide"
SIDES = (("RackSideR", 0.0), ("RackSideL", 180.0))   # the one side model: right side, and turned 180 deg to the left
CASING_X = (0.432, 0.44)
CH_FLOOR = -0.030       # conduit channel / vent recess floor (d below the skin face)
HATCH_D = (-0.016, -0.008)
PLACARD_HH = 0.09       # rack placard half height (fits the 24U hatch above the PDU warning row)
LABEL_MARGIN = 0.018    # labels keep this clear of the hatch rib's inner edge


def extent(spec):
    """(z0, z1, yb): the side field between the plinth and the tray (top on a half rack), between the posts."""
    d = R.dims(spec)
    z1 = d["ZT"] if d["tray"] else d["H"] - 0.006
    return 0.25, z1, R.YK - R.POST - 0.004


def layout(spec):
    z0, z1, yb = extent(spec)
    h = z1 - z0
    cond = (-yb + 0.035, -yb + 0.150)              # conduit channel (a = block y on the +x side; rear = negative)
    m0, m1 = cond[1] + 0.035, yb - 0.035           # the main field
    vent = (z0 + 0.05, z0 + 0.05 + 0.27 * h)
    band = (vent[1] + 0.03, vent[1] + 0.03 + max(0.11, 0.07 * h))
    hatch = (band[1] + 0.03, z1 - 0.05)
    return {"z0": z0, "z1": z1, "yb": yb, "h": h, "cond": cond, "m": (m0, m1), "vent": vent, "band": band,
            "hatch": hatch}


def parts(lod):
    P = {k: Part(k) for k in ("frame", "dark", "fine", "hw", "decal")}
    P["decal"].decal = True
    if lod == 0:
        P["frame"].bevel = (0.005, 1)
        P["dark"].bevel = (0.004, 1)
    return P


def build(spec, lod):
    """Parts for one LOD of the +x side, centred block frame (the rack model's z shift applied)."""
    L = layout(spec)
    P = parts(lod)
    Fs = R.F_side(1)
    z0, z1, yb = L["z0"], L["z1"], L["yb"]
    c0, c1 = L["cond"]
    m0, m1 = L["m"]
    v0, v1 = L["vent"]
    h0, h1 = L["hatch"]
    G.box(P["dark"], (CASING_X[0], -yb, z0), (CASING_X[1], yb, z1), DARK)      # the column wall behind
    if lod >= 2:
        G.prism(P["frame"], Fs, oct_pts(-yb, z0 + 0.01, yb, z1 - 0.01, 0.03), -0.012, 0.0, PAINT)
        G.prism(P["dark"], Fs, G.rect(c0, c1, z0 + 0.04, z1 - 0.04), 0.0, 0.002, DARK)
        G.prism(P["dark"], Fs, G.rect(m0, m1, v0, v1), 0.0, 0.002, DARK)
        _finish(P, spec)
        return [p for p in P.values() if not p.empty()]
    # ---- the skin: frame plate with the conduit channel, the vent recess and the hatch opening
    holes = [G.rect(c0, c1, z0 + 0.04, z1 - 0.04), oct_pts(m0, v0, m1, v1, 0.02), oct_pts(m0, h0, m1, h1, 0.03)]
    G.plate(P["frame"], Fs, G.rect(-yb, yb, z0, z1), holes, -0.012, 0.0, PAINT)
    # recess floors (Darker): the conduit channel and the vent recess
    G.prism(P["dark"], Fs, G.rect(c0, c1, z0 + 0.04, z1 - 0.04), CH_FLOOR - 0.004, CH_FLOOR, DARK)
    G.prism(P["dark"], Fs, oct_pts(m0, v0, m1, v1, 0.02), CH_FLOOR - 0.004, CH_FLOOR, DARK)
    _hatch(P, Fs, L, lod)
    _vents(P, Fs, L, lod)
    _conduit(P, Fs, L, lod)
    _band(P, Fs, L, lod)
    if lod == 0:   # corner bolts on the skin
        for a in (-yb + 0.018, yb - 0.018):
            for b in (z0 + 0.018, z1 - 0.018):
                G.cylinder(P["hw"], Fs(a, b, -0.001), Fs(a, b, 0.003), 0.007, 6, HARDWARE)
    _finish(P, spec)
    return [p for p in P.values() if not p.empty()]


def _finish(P, spec):
    m = Matrix.Translation((0, 0, -R.dims(spec)["H"] / 2))
    for p in P.values():
        if not p.empty():
            p.bm.transform(m)
            p.bm.normal_update()


def _hatch(P, Fs, L, lod):
    """The PDU service hatch, inset 8 mm in its opening (6 mm shadow gap), hinged at the rear edge."""
    m0, m1 = L["m"]
    h0, h1 = L["hatch"]
    g = 0.006
    a0, a1, b0, b1 = m0 + g, m1 - g, h0 + g, h1 - g
    grip = (a1 - 0.045, (b0 + b1) / 2, 0.022, 0.11)          # grip pocket (centre a, b; half w, half h)
    pocket = oct_pts(grip[0] - grip[2], grip[1] - grip[3], grip[0] + grip[2], grip[1] + grip[3], 0.01)
    if lod == 0:
        G.plate(P["frame"], Fs, oct_pts(a0, b0, a1, b1, 0.025), [pocket], HATCH_D[0], HATCH_D[1], PAINT)
        G.prism(P["fine"], Fs, pocket, HATCH_D[0] - 0.012, HATCH_D[0] - 0.008, DARK)   # pocket floor
        G.prism(P["hw"], Fs, oct_pts(grip[0] - 0.006, grip[1] - grip[3] + 0.02, grip[0] + 0.006,
                                     grip[1] + grip[3] - 0.02, 0.003), HATCH_D[0] - 0.008, HATCH_D[1] - 0.004,
                STEEL)                                                                    # grip bar
        # stiffening rib round the hatch field (stamped, 2 mm)
        G.plate(P["fine"], Fs, oct_pts(a0 + 0.03, b0 + 0.03, a1 - 0.075, b1 - 0.03, 0.02),
                [oct_pts(a0 + 0.045, b0 + 0.045, a1 - 0.09, b1 - 0.045, 0.014)], HATCH_D[1], HATCH_D[1] + 0.002,
                PAINT, bottom=False)
        for k in range(3):   # hinge knuckles on the rear edge
            bb = b0 + 0.06 + k * (b1 - b0 - 0.12) / 2
            G.cylinder(P["hw"], Fs(a0 - 0.001, bb - 0.03, HATCH_D[1] - 0.004),
                       Fs(a0 - 0.001, bb + 0.03, HATCH_D[1] - 0.004), 0.007, 8, STEEL)
        for bb in (b0 + 0.06, b1 - 0.06):   # quarter-turn latches at the front edge (top 2 mm under the skin)
            R._latch(P, Fs.sub(0, 0, HATCH_D[1]), grip[0], bb, lod)
    else:
        G.prism(P["frame"], Fs, oct_pts(a0, b0, a1, b1, 0.025), HATCH_D[0], HATCH_D[1], PAINT)
    # The hatch's labels sit inside the stiffening rib's inner field (never across the rib: its top face is the
    # decal plane) in two rows that never share an inch (Tests/test_zfight.py): the rack placard at the top, the
    # high-voltage warning and the PDU stencils side by side at the bottom (sticker left, text block right).
    fa0, fa1, fb0, fb1 = a0 + 0.045, a1 - 0.09, b0 + 0.045, b1 - 0.045      # the rib's inner field
    ac = (fa0 + fa1) / 2
    # rack placard: Yellow frame round a Darker plate, the "RACK ID" caption (white stencil) over a blank Brushed
    # write-on tag (rack.id_tag). No baked ID or row (controller ruling: every rack read "A1 / ROW A POS 1"); the ID
    # comes from the editable rack-label LCD (DC_Sign_Rack).
    pw, ph = 0.17, PLACARD_HH
    pc = (ac, fb1 - LABEL_MARGIN - ph)
    G.prism(P["fine"], Fs, oct_pts(pc[0] - pw, pc[1] - ph, pc[0] + pw, pc[1] + ph, 0.025), HATCH_D[1],
            HATCH_D[1] + 0.003, YELLOW)
    G.prism(P["fine"], Fs, oct_pts(pc[0] - pw + 0.012, pc[1] - ph + 0.012, pc[0] + pw - 0.012, pc[1] + ph - 0.012,
                                   0.018), HATCH_D[1] + 0.003, HATCH_D[1] + 0.004, DARK)
    stencil(P["decal"], Fs, pc[0], pc[1] + 0.050, 0.022, R.ID_CAPTION, d=HATCH_D[1] + 0.004)
    R.id_tag(P, Fs, pc[0] - 0.135, pc[0] + 0.135, pc[1] - 0.062, pc[1] + 0.030, HATCH_D[1] + 0.004, lod)
    if lod == 0:
        from se2model import decals as DCL
        sw = 0.15                                                   # DANGER HIGH VOLTAGE sticker width
        sh = sw / DCL.element_aspect(S2, "danger_hv")
        tw = 0.18                                                   # the text block ("PDU ACCESS" at 30 mm cap)
        x0 = ac - (sw + 0.025 + tw) / 2
        rb = fb0 + LABEL_MARGIN + sh / 2                            # the bottom row's centre line
        DCL.element(P["decal"], Fs, x0 + sw / 2, rb, sw, S2, "danger_hv", d=HATCH_D[1])
        stencil(P["decal"], Fs, x0 + sw + 0.025, rb + 0.022, 0.03, "PDU ACCESS", d=HATCH_D[1], align="left")
        stencil(P["decal"], Fs, x0 + sw + 0.025, rb - 0.016, 0.014, "ISOLATE BEFORE OPENING", d=HATCH_D[1],
                align="left")


def _vents(P, Fs, L, lod):
    """Two louvred intake bays in the framed vent recess, Brushed bay frames, Yellow filter release tabs."""
    m0, m1 = L["m"]
    v0, v1 = L["vent"]
    mid = (m0 + m1) / 2
    bays = [(m0 + 0.02, mid - 0.012), (mid + 0.012, m1 - 0.02)]
    G.prism(P["frame"], Fs, G.rect(mid - 0.012, mid + 0.012, v0, v1), CH_FLOOR, -0.006, PAINT)   # mullion
    n = max(4, int((v1 - v0 - 0.04) / 0.045))
    for a0, a1 in bays:
        b0, b1 = v0 + 0.02, v1 - 0.02
        if lod == 0:
            G.plate(P["hw"], Fs, G.rect(a0, a1, b0, b1), [G.rect(a0 + 0.008, a1 - 0.008, b0 + 0.008, b1 - 0.008)],
                    -0.012, -0.006, STEEL, bottom=False)
            G.prism(P["fine"], Fs, oct_pts((a0 + a1) / 2 - 0.02, b1 - 0.004, (a0 + a1) / 2 + 0.02, b1 + 0.006,
                                           0.003), -0.012, -0.004, YELLOW)
        # (LOD1 keeps LOD0's slat count: louvre_panel halves it there, which doubles the slats' width, and the tilted
        # slats then stood 17 mm proud of the render inset XO; Plan 5 Task 12 found it baking the stand-ins. LOD2 and
        # below have no slats at all: louvre_panel returns there, so the FR LOD1 stand-in, the side's LOD2, has none)
        louvre_panel(P["fine"], Fs.sub(0, 0, -0.004), a0 + 0.008, b0 + 0.008, a1 - 0.008, b1 - 0.008, n,
                     0 if lod == 1 else lod)


def _conduit(P, Fs, L, lod):
    """Coolant supply / return in the rear-edge channel: Brushed pipes turning into the column at both ends
    (Yellow collars, black union nuts), Brushed brackets, the flow meter with its lit sight glass."""
    z0, z1 = L["z0"], L["z1"]
    c0, c1 = L["cond"]
    ac = (c0 + c1) / 2
    r = 0.013
    dp = -0.013                                   # pipe axis depth (front of the pipe 1 mm under the skin)
    bot, top = z0 + 0.06, z1 - 0.06
    for a in (ac - 0.028, ac + 0.028):
        if lod == 0:
            pts = [Fs(a, bot, CH_FLOOR), Fs(a, bot + 0.05, dp), Fs(a, top - 0.05, dp), Fs(a, top, CH_FLOOR)]
            G.pipe_path(P["hw"], pts, r, 10, STEEL, bend=0.035, bend_steps=3)
            for b in (bot + 0.07, top - 0.07):    # Yellow collar + black union nut where the pipe leaves the run
                s = 1 if b < (bot + top) / 2 else -1
                G.cylinder(P["fine"], Fs(a, b, dp), Fs(a, b + s * 0.022, dp), r + 0.004, 10, YELLOW)
                G.cylinder(P["hw"], Fs(a, b + s * 0.022, dp), Fs(a, b + s * 0.034, dp), r + 0.0055, 6, DARK)
        else:
            G.cylinder(P["hw"], Fs(a, bot, dp), Fs(a, top, dp), r, 6, STEEL)
    # brackets: a Brushed strap over both pipes on two Darker posts, bolted
    n = max(3, int((top - bot) / 0.38))
    for k in range(n):
        b = bot + 0.16 + k * (top - bot - 0.32) / max(1, n - 1)
        if abs(b - (z0 + z1) / 2) < 0.12:
            continue                                # the flow meter sits there
        if lod == 0:
            for a in (c0 + 0.008, c1 - 0.008):
                G.box(P["dark"], *_ab(Fs, a - 0.006, a + 0.006, b - 0.012, b + 0.012, CH_FLOOR, 0.001))
                G.cylinder(P["hw"], Fs(a, b, 0.001), Fs(a, b, 0.0035), 0.0045, 6, HARDWARE)
        G.prism(P["hw"], Fs, G.rect(c0 + 0.004, c1 - 0.004, b - 0.009, b + 0.009), -0.0005, 0.001 if lod else 0.0015,
                STEEL)
    # flow meter: a Darker housing on the pipes, a Brushed-framed sight glass with the lit level bar
    mb = (z0 + z1) / 2
    G.prism(P["dark"], Fs, oct_pts(c0 + 0.004, mb - 0.09, c1 - 0.004, mb + 0.09, 0.012), CH_FLOOR, 0.0, DARK)
    gl = (ac - 0.011, ac + 0.011, mb - 0.055, mb + 0.045)
    G.prism(P["hw"], Fs, G.rect(gl[0] - 0.005, gl[1] + 0.005, gl[2] - 0.005, gl[3] + 0.005), 0.0, 0.0015, STEEL)
    lvl = gl[2] + 0.66 * (gl[3] - gl[2])
    G.prism(P["fine"], Fs, G.rect(gl[0], gl[1], gl[2], lvl), 0.0015, 0.002, LAMP_GREEN)
    G.prism(P["fine"], Fs, G.rect(gl[0], gl[1], lvl, gl[3]), 0.0015, 0.002, DARK)
    if lod <= 1:
        stencil(P["decal"], Fs, ac, mb + 0.068, 0.016, "FLOW", d=0.0)
        stencil(P["decal"], Fs, ac, mb - 0.074, 0.011, "COOLANT", d=0.0)


def _ab(F, a0, a1, b0, b1, d0, d1):
    """World-space (lo, hi) of an a/b/d box on a side face (axis-aligned faces only)."""
    p0, p1 = F(a0, b0, d0), F(a1, b1, d1)
    return (tuple(min(u, v) for u, v in zip(p0, p1)), tuple(max(u, v) for u, v in zip(p0, p1)), DARK)


def _band(P, Fs, L, lod):
    """The service band between the vents and the hatch: grounding stud, maintenance caution, asset barcode."""
    if lod > 0:
        return
    from se2model import decals as DCL
    m0, m1 = L["m"]
    b = (L["band"][0] + L["band"][1]) / 2
    ga = m0 + 0.05
    G.cylinder(P["hw"], Fs(ga, b, -0.001), Fs(ga, b, 0.002), 0.016, 6, HARDWARE)            # nut (flat)
    G.cylinder(P["hw"], Fs(ga, b, 0.002), Fs(ga, b, 0.0035), 0.0065, 8, STEEL)              # stud end
    # one row, left to right, clear of each other: the earth stud's electric-hazard triangle, the maintenance
    # caution, and the asset barcode at the front end (Tests/test_zfight.py)
    hazard_triangle(P["decal"], Fs, ga + 0.07, b, 0.06, d=0.0)
    DCL.element(P["decal"], Fs, ga + 0.25, b, 0.22, S2, "caution_maint", d=0.0)
    DCL.element(P["decal"], Fs, m1 - 0.14, b, 0.18, S2, "barcode_long", d=0.0)


def last(lo, hi):
    p = Part("side_last")
    G.box(p, lo, hi, PAINT)
    return [p]
