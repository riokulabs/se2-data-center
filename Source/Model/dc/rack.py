"""Open-frame rack (DC_Rack42_Open 4x10x5 cells, DC_Rack24_Open 4x5x5): frame, slot rails, collision.

Frame (Blender, metres, centred on the origin like vanilla: X width, +Y = front = game Forward, Z up):
    x +-0.5 (4 cells), y +-0.625 (5 cells), z +-H/2.  Built in "local" z (0 = floor) and shifted by -H/2.

Cells: the server slot is the centred 2 x 1 x 3 cells (x +-0.25,
y +-0.375); each side keeps a 0.25 m column for the corner posts, the 19" rails and an integrated vertical
cable manager; a 0.25 m front zone (door leaves, server ears, KVM travel) and a 0.25 m rear zone stay clear.

    | z (local)        | full rack (42)        | half rack (24)                  |
    | 0 .. 0.25        | plinth                | plinth                          |
    | 0.25 .. ZT       | 8 slots               | 4 slots                         |
    | ZT .. H          | 0.25 m top cable tray | -- (thin render-only roof)      |

Placement design (docs/guides/modeling-keen-style.md 7-8, se2model.placement):
- Regular collision (physics) = the frame: plinth, the two side columns, the top tray, and (for
  placement) a thin rear stop plate behind each slot column's back plane (4-5 boxes).
- Free cells: the slot cells (SLOT_CELLS) and, in front of them, the slot columns' front-zone cells, so the block
  placer's ray reaches into the slot (its targeting stops at the first OCCUPIED cell it crosses). The rear zone
  stays occupied (the rear stop's cells): nothing can be built into the cable space.
- Mount points: the outer sides, the plinth bottom and the tray rim are flush (hints on the planes). Inside the
  slot only the REAR row mounts (the rail faces at x = +-0.25, the slot floor / ceiling), so a server seats only at
  its designed depth (rear cells on the rear row). Front and back: every part stays >= 2.7 cm behind the planes
  and no hint touches them, so the openings never mount.
"""
import math

from se2model.config import DECAL_OFFSET

from . import catalog
from . import dims as DM
from . import doors as DR

try:   # geometry needs Blender; SLOT_CELLS / dims / collision are plain Python (pytest imports them outside)
    from mathutils import Matrix
    from se2model import geom as G
    from se2model.geom import Face, Part
    from se2model.config import S2
except ImportError:
    Matrix = G = Face = Part = S2 = None
from .style import (CHAMFER_LARGE, DARK, HARDWARE, KEEP_OUT, LAMP_GREEN, PAINT, PARTS, SHADOW_GAP, STEEL, YELLOW,
                    bolt, corner_cap, lamp, louvre_panel, oct_pts, perf_quad, stencil)

W2 = 0.5            # half width (4 cells)
D2 = 0.625          # half depth (5 cells)
SX = DM.SLOT_HALF_W  # slot half width (2 cells): the rail plane
SD = DM.SLOT_HALF_D  # slot half depth (3 cells)
YK = D2 - KEEP_OUT  # 0.598: nothing on the front / back reaches past this (non-mounting openings)
SLOT_H = DM.SLOT_H
# No render vertex may reach the side planes. XO is the render mesh's outer side plane, 1 mm
# inside the cell bounds, so two racks placed flush leave a 2 mm hairline gap instead of coplanar (z-fighting) faces;
# the side skins sit 6 mm in, so the hardware standing up to 5 mm proud of them (latches, studs) still ends at XO.
XO = W2 - DM.RACK_SIDE_INSET
SKIN = 0.006        # outer skins sit 6 mm inside the side planes (5 mm hardware and 2 mm decals stay inside XO)
CAP = 0.12          # armoured corner-cap footprint
CAP_CH = 0.06       # corner-cap 45 deg chamfer
POST = 0.075        # corner post section
# cable manager channel in each side column (|x|): rails 0.25..0.29, channel 0.297..0.42, posts 0.425..0.5
RAIL_X = DM.RAIL_X
CH_X = DM.MANAGER_CH_X
SPINE_Y = DM.MANAGER_SPINE_Y   # channel back wall (front channel; mirrored at the rear)
IX, IY = DM.RACK_TRAY_IX, DM.RACK_TRAY_IY   # full-rack top trough interior half sizes (the rim's inner edges)
# No baked rack ID: otherwise every rack reads "A1" (front header, side hatch placard "A1 / ROW A POS 1", half-rack
# roof). The ID comes from the editable rack-label LCD
# (DC_Sign_Rack). The racks carry a neutral caption and a blank Brushed write-on tag (id_tag) instead.
LABEL = "RACK"          # the caption stencil on the front header / kick plate and the half rack's roof plate
ID_CAPTION = "RACK ID"  # the side hatch placard's caption (rack_side.py)
ID_TAG_T = 0.0015       # the blank tag's thickness (proud of its Darker plate: clear of the 0.3 mm z-fight epsilon)
# placement: the slot's rear stop and mount key (collision()), and the render clearances they need
REAR_STOP_GAP = 0.003   # rear stop plate (physics) this far behind the slot's back plane (server render ends 3 mm in)
REAR_STOP_T = 0.02      # its thickness
KEY_ROW = 0.25          # the keyed mount row: the slot's rear cell row (Blender y -SD .. -SD + KEY_ROW)
MOUNT_CLEAR = 0.025     # render near a slot plane outside the key row stays this far off it (the sampler's 2 cm)
REAR_BRACKET_X = 0.232  # |x| the rear stop brackets reach into the slot (server body 0.240, KVM drawer 0.205)


# ---------------------------------------------------------------------------------------------------- dimensions

def dims(spec):
    nx, ny, nz = spec.cells
    assert (nx, nz) == (4, 5), spec
    H, ZT, tray, nslots = DM.rack_frame(ny)
    sides = DR.door_sides(spec)
    # door variants are powered blocks: their power-OK lamp is EmissiveOff in the model and the cloned material
    # swapper lights it (EmissiveGreen) while Working; the open (decor) rack's lamp is always lit
    return {"H": H, "ZT": ZT, "tray": tray, "nslots": nslots, "doors": sides, "spec": spec,
            "lamp": "EmissiveOff" if sides else LAMP_GREEN}


def SLOT_CELLS(spec):  # noqa: N802 (interface name from the plan)
    """Game-frame cell indices (x, y, z; inclusive bounds as catalog.bounds) servers occupy inside the rack:
    nslots boxes of 2 x 1 x 3 cells, centred in x and z, stacked from the cell above the plinth."""
    (x0, y0, z0), (x1, y1, z1) = catalog.bounds(spec)
    d = dims(spec)
    xs = (x0 + 1, x0 + 2)
    zs = (z0 + 1, z0 + 2, z0 + 3)
    ys = range(y0 + 1, y0 + 1 + d["nslots"])
    return [(x, y, z) for y in ys for x in xs for z in zs]


def SLOTS(spec):  # noqa: N802
    """Per slot: (index 1..n, local z of the slot floor)."""
    return [(k + 1, 0.25 + SLOT_H * k) for k in range(dims(spec)["nslots"])]


# ---------------------------------------------------------------------------------------------------- faces
def F_front(y=YK):
    return Face((0, y, 0), (-1, 0, 0), (0, 0, 1))        # normal +Y; a runs to the viewer's right


def F_back(y=-YK):
    return Face((0, y, 0), (1, 0, 0), (0, 0, 1))         # normal -Y


def F_side(sx, x=None):
    x = sx * (W2 - SKIN) if x is None else x
    return Face((x, 0, 0), (0, sx, 0), (0, 0, 1))         # normal +-X; a = +y for the right side


def F_top(z):
    return Face((0, 0, z), (1, 0, 0), (0, 1, 0))


def _quad(p, F, a0, a1, b0, b1, d, mat):
    """A single quad on face F at depth d (cheap inset detail such as rail holes)."""
    f = p.bm.faces.new([p.bm.verts.new(F(a, b, d)) for a, b in G.rect(a0, a1, b0, b1)])
    f.material_index = p.mi(mat)
    return f


def _plate(p, F, pts, d0, d1, mat, holes=()):
    if holes:
        G.plate(p, F, pts, [list(h) for h in holes], d0, d1, mat)
    else:
        G.prism(p, F, pts, d0, d1, mat)


# ---------------------------------------------------------------------------------------------------- builders

def _plinth(P, d, lod):
    """Plinth: Darker solid core, flush bottom (mounts), Darker slot-floor deck (flush top = the slot floor),
    louvred kick panels (cooling air intake under the servers) and Colorable side skins with jacking pockets."""
    fr, dk, hw, dec = P["frame"], P["dark"], P["hw"], P["decal"]
    if lod <= 1:   # visual pass 1: the cabinet stands on four Brushed levelling feet; the base frame clears the
        #            floor by 4 mm, so a shadow line runs under the plinth (collision / mounts are separate boxes)
        G.box(dk, (-W2 + SKIN + 0.02, -YK + 0.02, 0.004), (W2 - SKIN - 0.02, YK - 0.02, 0.014), DARK)
        for fx in (-1, 1):
            for fy in (-1, 1):
                c = (fx * (W2 - 0.075), fy * (YK - 0.075))
                G.cylinder(hw, (c[0], c[1], 0.0), (c[0], c[1], 0.006), 0.034, 12 if lod == 0 else 6, STEEL)
                if lod == 0:   # the threaded stem up into the frame
                    G.cylinder(hw, (c[0], c[1], 0.006), (c[0], c[1], 0.014), 0.016, 6, HARDWARE)
    else:
        G.box(dk, (-W2 + SKIN, -YK, 0.0), (W2 - SKIN, YK, 0.014), DARK)          # base frame (flush bottom)
    # placement fix: the deck sits MOUNT_CLEAR under the slot floor plane, so it does not mount; only the slot-floor
    # hint (rear row) does. Slot 1's server rides on its slides like every other slot, over a 25 mm air gap.
    zd = 0.25 - MOUNT_CLEAR
    # the solid core under the deck (broken interiors in the game's own style): a plinth half's break shows the other
    # half's FracturedMaterial01 cap, not the hollow of a load frame
    G.box(dk, (-0.47, -0.57, 0.014), (0.47, 0.57, zd - 0.008), DARK)              # core
    G.box(dk, (-W2 + SKIN, -YK + 0.012, zd - 0.008), (W2 - SKIN, YK - 0.012, zd), DARK)   # thin dark deck
    for F, front in ((F_front(YK - 0.012), True), (F_back(-YK + 0.012), False)):
        a1 = W2 - CAP - 0.006
        if lod >= 2:
            G.prism(fr, F, oct_pts(-a1, 0.03, a1, 0.22, 0.03), -0.014, 0.0, PAINT)
            continue
        if front and not d["tray"]:
            # half rack: label plate in the middle of the kick panel, a louvre each side
            holes = [G.rect(-a1 + 0.05, -0.15, 0.07, 0.18), G.rect(0.15, a1 - 0.05, 0.07, 0.18)]
            _plate(fr, F, oct_pts(-a1, 0.03, a1, 0.22, 0.03), -0.014, 0.0, PAINT, holes)
            for (h0, h1) in ((-a1 + 0.05, -0.15), (0.15, a1 - 0.05)):
                louvre_panel(P["fine"], F, h0, 0.07, h1, 0.18, 5, lod)
            _label(P, F, 0.0, 0.125, 0.0, 0.11, 0.05, lod, d["lamp"])
        else:
            _plate(fr, F, oct_pts(-a1, 0.03, a1, 0.22, 0.03), -0.014, 0.0, PAINT,
                   [G.rect(-a1 + 0.05, a1 - 0.05, 0.07, 0.18)])
            louvre_panel(P["fine"], F, -a1 + 0.05, 0.07, a1 - 0.05, 0.18, 5, lod)
        if lod == 0:
            for a in (-a1 + 0.025, a1 - 0.025):
                bolt(hw, F, a, 0.125, 0.0)
    for sx in (-1, 1):
        F = F_side(sx)
        b0 = -(YK - CAP - 0.006)
        _plate(fr, F, oct_pts(b0, 0.025, -b0, 0.225, 0.03), -0.012, 0.0, PAINT,
               [G.rect(-0.10, 0.10, 0.075, 0.165)] if lod <= 1 else ())
        if lod <= 1:
            # jacking point: Darker pocket behind the opening, yellow trim line above it
            G.box(dk, (sx * 0.468 - 0.004, -0.10, 0.075), (sx * 0.468 + 0.004, 0.10, 0.165), DARK)
            G.prism(fr, F, G.rect(-0.10, 0.10, 0.178, 0.186), 0.0, 0.0015, YELLOW)
            if lod == 0:
                for a in (b0 + 0.03, -b0 - 0.03):
                    for b in (0.06, 0.19):
                        bolt(hw, F, a, b, 0.0)


def id_tag(P, F, a0, a1, b0, b1, d, lod):
    """A blank write-on ID tag: a Brushed plate ID_TAG_T proud of the face at depth d, riveted at both ends (LOD0).
    Neutral by design: the operator stamps or writes the rack ID on it; the game's ID is the
    editable rack-label LCD. Geometry only (no decal), so no stencil can fight it."""
    c = min(0.004, (b1 - b0) * 0.2)
    G.prism(P["hw"], F, oct_pts(a0, b0, a1, b1, c), d, d + ID_TAG_T, STEEL)
    if lod == 0:
        r = min(0.003, (b1 - b0) * 0.12)
        for a in (a0 + 2.2 * r, a1 - 2.2 * r):
            G.cylinder(P["hw"], F(a, (b0 + b1) / 2, d + ID_TAG_T - 0.0002), F(a, (b0 + b1) / 2, d + ID_TAG_T + 0.0008),
                       r, 6, HARDWARE)


def _label(P, F, a, b, d, w, cap, lod, lamp_mat=LAMP_GREEN):
    """Rack label plate: Darker clipped plate with the neutral "RACK" caption and a blank write-on ID tag (id_tag; no
    baked ID), plus the power-OK lamp."""
    G.prism(P["dark"], F, oct_pts(a - w, b - cap * 0.95, a + w, b + cap * 0.95, cap * 0.35), d, d + 0.006, DARK)
    if lod <= 1:
        a0 = a - w + cap * 0.45                       # clear of the plate's clipped corners
        tw = stencil(P["decal"], F, a0, b, cap * 0.42, LABEL, d=d + 0.006, align="left")
        la = a + w - 0.028                            # the lamp (its bezel r 0.015)
        id_tag(P, F, a0 + tw + 0.012, la - 0.025, b - cap * 0.55, b + cap * 0.55, d + 0.006, lod)
        lamp(P["hw"], F, la, b, d + 0.006, r=0.009, lod=lod, mat=lamp_mat)


def _corners(P, d, lod):
    """Armoured caps on all 8 corners (plinth band and top band) and the 4 chunky corner posts between them."""
    H, ZT = d["H"], d["ZT"]
    top0 = ZT if d["tray"] else H - 0.12
    for sx in (-1, 1):
        for sy in (-1, 1):
            xo, yo = sx * (XO - 0.0015), sy * YK   # the caps' Yellow trim stands 1.5 mm proud of xo
            corner_cap(P["dark"], sx, sy, xo, yo, 0.014 if lod <= 1 else 0.0, 0.25, CAP, CAP_CH, lod,
                       trim_at="top")   # LOD0/1: the levelling foot shows under the cap (_plinth)
            corner_cap(P["dark"], sx, sy, xo, yo, top0, H, CAP, CAP_CH, lod, trim_at="bottom")
            # post: Colorable, outer vertical edge chamfered, runs between the caps
            x0, y0 = xo - sx * POST, yo - sy * POST
            c = 0.025 if lod <= 2 else 0.0
            pts = [(x0, y0), (xo, y0), (xo, yo - sy * c), (xo - sx * c, yo), (x0, yo)]
            if sx * sy < 0:
                pts.reverse()
            G.prism(P["frame"], Face((0, 0, 0), (1, 0, 0), (0, 1, 0)), pts, 0.25, top0, PAINT)


def _latch(P, F, a, b, lod):
    """Quarter-turn panel fastener: Darker boss with a MetalDull slotted head (open the panel with a tool)."""
    n = 12 if lod == 0 else 8
    G.cylinder(P["hw"], F(a, b, -0.001), F(a, b, 0.004), 0.017, n, DARK)
    if lod == 0:
        G.prism(P["hw"], F, G.rect(a - 0.0035, a + 0.0035, b - 0.012, b + 0.012), 0.004, 0.0065, HARDWARE)


def _columns(P, d, lod):
    """Per side column, open like a real rack frame:
    - one telescopic slide-rail kit per slot (MetalDull C-section outer member, its web exactly on the slot plane
      x = +-0.25, bolted to the front and rear 19" rails); nothing spans the slot, and no wall fills the side;
    - the front and rear 19" rails (Brushed, square holes as dark engraving), with ONE stencilled slot number per
      slot on a Darker tab on the left front rail;
    - the integrated vertical cable managers: a painted channel back (visible behind the fingers), Darker finger
      roots and chunky fingers at a 1/2-slot pitch with a cable-pass gap at the top and bottom (front = data,
      rear = power, half as dense), and lacing bars per slot."""
    ZT = d["ZT"]
    # the manager channel's back and finger roots end at the slot band's top under the full rack's tray; under the
    # half rack's roof rail they stop 1 mm below the rail (its brush-plate holes open into the channel)
    ZC = ZT if d["tray"] else ZT - ROOF_RAIL_T - 0.001
    z0 = 0.25
    slots = [0.25 + SLOT_H * k for k in range(d["nslots"])]
    FT = 0.018
    for sx in (-1, 1):
        X = lambda a, b: (min(sx * a, sx * b), max(sx * a, sx * b))  # noqa: E731
        if lod <= 1:
            Fw = Face((sx * SX, 0, 0), (0, -sx, 0), (0, 0, 1))   # the slot plane, normal into the slot
            ye = SD - DM.RAIL_DEPTH
            for zf in slots:
                zb, zt = zf + DM.RACK_SLIDE_Z[0], zf + DM.RACK_SLIDE_Z[1]
                web = X(SX, SX + 0.004)
                G.box(P["slide"], (web[0], -ye, zb), (web[1], ye, zt), HARDWARE)
                for zz in ((zb, zb + 0.004), (zt - 0.004, zt)) if lod == 0 else ():
                    fl = X(SX, SX + 0.02)
                    G.box(P["slide"], (fl[0], -ye, zz[0]), (fl[1], ye, zz[1]), HARDWARE)
                if lod == 0:   # countersunk bolts at both rail ends (1.5 mm heads)
                    for a in (-(ye - 0.02), ye - 0.02):
                        G.cylinder(P["slidebolt"], Fw(a, (zb + zt) / 2, -0.001),
                                   Fw(a, (zb + zt) / 2, DM.RACK_SLIDE_BOLT_PROUD), 0.007, 6, STEEL)
        # 19" rails front and rear: Brushed angle, ear face at y = +-0.375 (the slot's front / back plane)
        for sy in (-1, 1):
            xr = X(RAIL_X[0], RAIL_X[1])
            y0, y1 = sorted((sy * (SD - DM.RAIL_DEPTH), sy * SD))
            G.box(P["rail"], (xr[0], y0, z0), (xr[1], y1, ZT), STEEL)
            xf = X(RAIL_X[1] - 0.004, RAIL_X[1])
            y2, y3 = sorted((sy * (SD - DM.RAIL_DEPTH), sy * (SD - 0.09)))
            G.box(P["hw"], (xf[0], y2, z0), (xf[1], y3, ZT), STEEL)          # return flange
            if lod == 0:
                Fr = Face((0, sy * SD, 0), (-sy, 0, 0), (0, 0, 1))
                ah = -sy * sx * DM.RAIL_HOLE_X          # square-hole column (dark engraving), a in Fr's frame
                hs = DM.RAIL_HOLE_SIZE / 2
                for zf in slots:
                    for zo in DM.hole_offsets():
                        zc = zf + zo
                        _quad(P["holes"], Fr, ah - hs, ah + hs, zc - hs, zc + hs, 0.0006, DARK)
            if lod <= 1 and sy < 0:
                # placement fix: the rear stop brackets, one per slot on each rear rail (Brushed tabs on the rail's
                # back face, between its 2nd and 3rd hole, reaching 18 mm into the slot past the server's body side):
                # what a pushed-in server comes up against. The physics stop is the rear_stop plate (collision()).
                xb = X(REAR_BRACKET_X, RAIL_X[1] - 0.002)
                yb = sorted((-(SD + 0.0012), -(SD + 0.0042)))
                for zf in slots:
                    G.box(P["hw"], (xb[0], yb[0], zf + 0.105), (xb[1], yb[1], zf + 0.145), STEEL)
            if lod <= 1 and sy > 0 and sx < 0:   # one slot number per slot, on a Darker tab
                Fr = Face((0, SD, 0), (-1, 0, 0), (0, 0, 1))
                for i, zf in enumerate(slots, 1):
                    G.prism(P["dark"], Fr, G.rect(0.2525, 0.2875, zf + DM.SLOT_TAB_Z[0], zf + DM.SLOT_TAB_Z[1]), 0.0,
                            0.002, DARK)
                    stencil(P["decal"], Fr, 0.27, zf + 0.125, 0.026, str(i), d=0.002)
        # the front (data) cable manager; the rear column is the zero-U PDU column (_pdu_column)
        sy = 1
        xc = X(CH_X[0], CH_X[1])
        ys = sorted((sy * SPINE_Y[0], sy * SPINE_Y[1]))
        G.box(P["frame"] if lod <= 1 else P["dark"], (xc[0], ys[0], z0), (xc[1], ys[1], ZC),
              PAINT if lod <= 1 else DARK)                                         # channel back
        yt0, yt1 = sorted((sy * SPINE_Y[1], sy * (YK - 0.012)))
        if lod >= 2:
            for e in (CH_X[0], CH_X[1] - FT):
                xe = X(e, e + FT)
                G.box(P["dark"], (xe[0], yt0, z0 + 0.06), (xe[1], yt1, ZT - 0.06), DARK)
        else:
            yr = sorted((sy * SPINE_Y[1], sy * (SPINE_Y[1] + 0.03)))
            for e in (CH_X[0], CH_X[1] - FT):
                xe = X(e, e + FT)
                G.box(P["dark"], (xe[0], yr[0], z0), (xe[1], yr[1], ZC), DARK)         # finger root strip
            pitch = 0.125 if lod == 0 else 0.25
            n = int(round((ZT - z0 - 0.125) / pitch))
            for e in (CH_X[0], CH_X[1] - FT):
                xe = X(e, e + FT)
                for k in range(n + 1):
                    zc = z0 + 0.0625 + pitch * k
                    if zc > ZT - 0.06:
                        break
                    G.box(P["fine"], (xe[0], yt0, zc - 0.018), (xe[1], yt1, zc + 0.018), DARK)
                    if lod == 0:   # finger tip: the cover retention nub
                        xt = X(e - 0.005, e + FT + 0.005)
                        yy = sorted((sy * (YK - 0.026), sy * (YK - 0.012)))
                        G.box(P["fine"], (xt[0], yy[0], zc - 0.02), (xt[1], yy[1], zc + 0.02), DARK)
            if lod == 0:   # lacing bars across the channel every slot (tie points for the bundles)
                for zf in slots:
                    ym = sy * (SPINE_Y[1] + 0.045)
                    G.cylinder(P["hw"], (sx * (CH_X[0] + FT), ym, zf + 0.125), (sx * (CH_X[1] - FT), ym, zf + 0.125),
                               0.006, 8, HARDWARE)
        _pdu_column(P, d, sx, slots, z0, ZC, lod)


# ---------------------------------------------------------------------------------------------------- PDU columns
# The rear of each side column is the zero-U PDU column (dims.PDU_COL_X x PDU_COL_Y over the slot
# band; Feed A = +x, the right column seen from the hot aisle; Feed B mirrored). It replaces the earlier rear
# power manager (its built-in strip and cords): the PDU strip is now its own block, so the rack keeps
# the column's clear envelope (dims.PDU_ENVELOPE) and provides the strip's three interfaces:
#   * the PDU bulkhead: the column's back wall on the bracket plane y = -SLOT_HALF_D (Colorable, 6 mm, 0.5 mm inside
#     the plane) with a keyhole slot per slot (the strip's mounting buttons hang in them), the FEED stencil plate;
#     the pdu_bracket hint makes the plane mount;
#   * the plinth receptacle: the strip's power feed, a twist-lock socket in a Darker gland plate, flush in the plinth
#     top at dims.PDU_RECEPTACLE (the strip's inlet plug seats in it); the pdu_seat hint makes the plinth top mount;
#   * the cleared column itself: nothing of the frame inside the envelope over the PDU band (pdu_band).
BULK_Y = (DM.SLOT_HALF_D - 0.0065, DM.SLOT_HALF_D - 0.0005)   # |y| of the bulkhead (its face 0.5 mm inside the plane)
BULK_X = (RAIL_X[1] + 0.0005, 0.431)                           # rail outer face .. 1 mm short of the side casing
GLAND_X = (0.300, 0.3755)            # the gland plate (|x|): its outer edge 2 mm clear of the plinth corner cap
GLAND_Y = (0.440, 0.533)             # (|y|), centred on the receptacle
SOCKET_R = (0.0145, 0.019)           # the socket's coupling ring (inner, outer radius)


def pdu_band(spec):
    """Local z (0 = floor) of the PDU band: the slot band, from the plinth top to the full rack's tray floor; on the
    half rack it stops under the top corner caps (H - CAP), whose armour reaches into the column's outer corner."""
    d = dims(spec)
    return 0.25, (d["ZT"] if d["tray"] else d["H"] - CAP)


PDU_FEED_SIGN = {"A": 1, "B": -1}


def PDU_CELLS(spec, feed):  # noqa: N802 (interface name from the plan)
    """Game-frame cell indices (x, y, z; inclusive bounds as catalog.bounds) of one PDU column: the rear depth cell
    of the side column, over the slot band. "A" = +x (the right column seen from the hot aisle), "B" = -x."""
    if feed not in PDU_FEED_SIGN:
        raise ValueError(f"PDU feed must be 'A' or 'B', not {feed!r}")
    (x0, y0, z0), (x1, y1, z1) = catalog.bounds(spec)
    x = x1 if feed == "A" else x0
    return [(x, y, z1) for y in range(y0 + 1, y0 + 1 + dims(spec)["nslots"])]


def OPENING_CELLS(spec):  # noqa: N802
    """The slot columns' front-zone row: the cells in front of the slots, left free so the
    block placer's ray can enter a slot (Forward = game -z, the box's first z row)."""
    (x0, y0, z0), (x1, y1, z1) = catalog.bounds(spec)
    xs = sorted({c[0] for c in SLOT_CELLS(spec)})
    ys = sorted({c[1] for c in SLOT_CELLS(spec)})
    return [(x, y, z0) for y in ys for x in xs]


def FREE_CELLS(spec):  # noqa: N802
    """Every cell of the rack box a block may occupy: the server slots, their front opening row and both PDU
    columns."""
    return SLOT_CELLS(spec) + OPENING_CELLS(spec) + PDU_CELLS(spec, "A") + PDU_CELLS(spec, "B")


def _pdu_column(P, d, sx, slots, z0, zc, lod):
    """The rear PDU column of one side (sx): the bulkhead with its keyhole slots and the FEED plate, and the plinth
    receptacle under it (_receptacle)."""
    X = lambda a, b: (min(sx * a, sx * b), max(sx * a, sx * b))  # noqa: E731
    xb = X(*BULK_X)
    G.box(P["frame"], (xb[0], -BULK_Y[1], z0), (xb[1], -BULK_Y[0], zc), PAINT)
    _receptacle(P, sx, lod)
    if lod >= 2:
        return
    Fb = F_back(-BULK_Y[1])                     # the bulkhead's face toward the column (normal -y), a = x
    ac = sx * DM.PDU_RECEPTACLE[0]              # the column's centre line (the strip's buttons hang on it)
    feed = "A" if sx > 0 else "B"
    # FEED plate near the top: Darker, the feed letter and the zero-U PDU caption (white stencils)
    zp = zc - 0.075
    # (thin: the plate 0.4 mm, the stencils 0.6 mm over it, clear of the z-fight epsilon (dc/zfight.py GEOM_EPS_D),
    # so everything stays 1 mm proud of the face, outside the PDU envelope 2.5 mm behind it)
    G.prism(P["dark"], Fb, oct_pts(ac - 0.052, zp - 0.033, ac + 0.052, zp + 0.033, 0.012), 0.0, 0.0004, DARK)
    stencil(P["decal"], Fb, ac, zp + 0.008, 0.022, f"FEED {feed}", d=0.0010 - DECAL_OFFSET)
    stencil(P["decal"], Fb, ac, zp - 0.019, 0.0095, "ZERO-U PDU", d=0.0010 - DECAL_OFFSET)
    if lod == 0:
        # keyhole slots, one per slot in the slot's lower quarter (a strip of any length finds two): the round head
        # opening over a narrow slot below it, dark engraving 0.6 mm proud (as the rails' square holes)
        for zf in slots:
            zk = zf + 0.07
            G.prism(P["fine"], Fb, [(ac + x, zk + y) for x, y in G.ngon(0.0075, 8, math.pi / 8)], 0.0, 0.0006, DARK)
            G.prism(P["fine"], Fb, G.rect(ac - 0.0035, ac + 0.0035, zk - 0.019, zk), 0.0, 0.0006, DARK)


def _receptacle(P, sx, lod):
    """The PDU's power feed in the plinth top under the column: a Darker gland plate (4 mm, 1 mm under the
    plinth top plane), a twist-lock socket in it (Yellow coupling ring = live socket, a recessed Darker face with five
    MetalDull contact sleeves: 3 phases, neutral and the larger earth at the key), two fixing screws and the feed
    letter. The socket is its own part ("socket", measured: build_report geometry.pdu_receptacles)."""
    rx, ry = sx * DM.PDU_RECEPTACLE[0], DM.PDU_RECEPTACLE[1]
    ga, gb = sorted((sx * GLAND_X[0], sx * GLAND_X[1]))
    Ft = F_top(0.0)
    zt = 0.2495
    pts = oct_pts(ga, -GLAND_Y[1], gb, -GLAND_Y[0], 0.008)
    if lod >= 2:
        G.prism(P["fine"], Ft, pts, 0.2445, zt, DARK)
        return
    if lod == 1:
        G.prism(P["fine"], Ft, pts, 0.2445, zt - 0.0005, DARK)
        G.prism(P["socket"], Ft, [(rx + x, ry + y) for x, y in G.ngon(SOCKET_R[1], 8)], zt - 0.0005, zt - 0.0002,
                YELLOW)
        return
    hole = [(rx + x, ry + y) for x, y in G.ngon(SOCKET_R[1], 16)]
    G.plate(P["fine"], Ft, pts, [hole], 0.2445, zt - 0.0005, DARK)   # 0.6 mm under the feed letter (z-fight)
    G.ring(P["socket"], Ft, [(rx + x, ry + y) for x, y in G.ngon(SOCKET_R[1], 16)],
           [(rx + x, ry + y) for x, y in G.ngon(SOCKET_R[0], 16)], zt - 0.004, zt - 0.0003, YELLOW)
    G.prism(P["socket"], Ft, [(rx + x, ry + y) for x, y in G.ngon(SOCKET_R[0], 16)], zt - 0.0045, zt - 0.004, DARK)
    for k in range(5):   # contact sleeves on a circle, the earth (k = 0) larger, at the key toward the slot
        a = math.pi * (1.0 if sx > 0 else 0.0) + k * 2 * math.pi / 5
        r = 0.0030 if k == 0 else 0.0022
        c = (rx + 0.0088 * math.cos(a), ry + 0.0088 * math.sin(a))
        G.cylinder(P["socket"], (c[0], c[1], zt - 0.004), (c[0], c[1], zt - 0.0028), r, 6, HARDWARE)
    sa = sx * (GLAND_X[0] + 0.017)
    for yy in (-GLAND_Y[0] - 0.014, -GLAND_Y[1] + 0.014):   # fixing screws (heads 0.3 mm under the slot floor)
        G.cylinder(P["hw"], (sa, yy, zt - 0.0005), (sa, yy, zt + 0.0002), 0.0055, 6, HARDWARE)
    Fr = Face((sa, ry, zt), (1, 0, 0), (0, 1, 0))   # reads from the hot aisle (rear: -y at the bottom)
    stencil(P["decal"], Fr, 0.0, 0.0, 0.020, "A" if sx > 0 else "B", d=0.0001 - DECAL_OFFSET)   # under the plane


# ---------------------------------------------------------------------------------------------------- containment
CONTAIN_LIP_Y = 0.621                 # |y| of the rail lips' front face (the clamp pads stand to CONTAIN_RAIL_Y[1])
CONTAIN_Z = (0.170, DM.CONTAIN_RAIL_DZ[1])   # the rail's z above ZT (its top 12 mm under the rack's top plane)
CONTAIN_PADS = (-0.375, -0.125, 0.125, 0.375)   # clamp pads every 0.25 m: one per mount cell of the band


CONTAIN_TAG_LIFT = 0.0006   # the CONTAINMENT tag's stencil 0.6 mm clear of its Darker plate (z-fight)
# In game 2026-10-20 (a 42U open rack seen from below): the clamp pads were exactly as tall as the rail and sat flush on
# its back plane, so their top, bottom and back faces lay in the rail's planes (the Darker pad and the Colorable rail
# flickered), and the standoff behind each pad read as a loose dark block under it. Now each pad is a clip that wraps
# the rail: the rail body stands CONTAIN_WRAP inside the band (z0..z1 stays the pads' extent, so the measured rail and
# the mount band do not move), the pad's back face is buried CONTAIN_PAD_SINK inside the rail, and the standoff runs
# down to just above the clip's lower jaw, so from below the clip and its standoff read as one bracket.
CONTAIN_WRAP = 0.003        # the clip's jaws over the rail's top and bottom faces
CONTAIN_PAD_SINK = 0.002    # the clip's back face, inside the rail (not in its back plane)
CONTAIN_STANDOFF_HW = 0.019  # the standoff's half width (the 21 mm pad's sides stay clear: no shared side planes)


def contain_rail_boxes(sy, lod):
    """[(kind, lo, hi)] of the containment rail on side sy (+1 front, -1 back), z relative to ZT: the rail body
    ("lip_lo", "lip_hi", "channel" at LOD0; "rail" at LOD1 and as the far box) and per pad x the clamp pad ("pad") and
    its standoff ("standoff", LOD0). Plain numbers: Tests/test_zfight.py checks them for shared face planes."""
    z0, z1 = CONTAIN_Z
    y0, yp = DM.CONTAIN_RAIL_Y
    xa = XO - 0.002
    lip = 0.026
    w = CONTAIN_WRAP

    def Y(a, b):
        return tuple(sorted((sy * a, sy * b)))
    yl = Y(y0, CONTAIN_LIP_Y)
    if lod >= 2:
        return [("rail", (-xa, yl[0], z0), (xa, yl[1], z1))]
    out = []
    if lod == 0:
        out.append(("lip_lo", (-xa, yl[0], z0 + w), (xa, yl[1], z0 + lip)))
        out.append(("lip_hi", (-xa, yl[0], z1 - lip), (xa, yl[1], z1 - w)))
        yg = Y(y0, y0 + 0.011)
        out.append(("channel", (-xa, yg[0], z0 + lip), (xa, yg[1], z1 - lip)))
    else:
        out.append(("rail", (-xa, yl[0], z0 + w), (xa, yl[1], z1 - w)))
    ypd = Y(y0 + CONTAIN_PAD_SINK, yp - 0.0002)
    for xp in CONTAIN_PADS:
        out.append(("pad", (xp - 0.021, ypd[0], z0), (xp + 0.021, ypd[1], z1)))
        if lod == 0:
            ys = Y(YK - 0.016, y0)
            h = CONTAIN_STANDOFF_HW
            out.append(("standoff", (xp - h, ys[0], z0 + 0.001), (xp + h, ys[1], z1 - 0.008)))
    return out


def _contain_rail(P, d, lod, tag_lift=CONTAIN_TAG_LIFT):
    """Full racks: the aisle-containment rail across the front and back tray band (dims.CONTAIN_RAIL_Y x ZT +
    CONTAIN_Z). A Colorable box rail (two lips round a Darker clamp channel) held off the tray header by Darker
    standoffs; the roof panel's edge bears on it and its clamps grip the Darker clamp pads (one per 0.25 m cell, a
    MetalDull clamp screw on top), clips whose jaws wrap the rail's top and bottom (contain_rail_boxes); a Yellow
    "CONTAINMENT" tag clipped into the channel. The contain_front / back hints make the band mount (the only Forward /
    Backward mounts on the box planes). The rail is its own part ("contain", measured: build_report
    geometry.contain_rails); the standoffs, screws and tag are not part of it.
    tag_lift: lifts the tag's stencil off the Darker plate under it (at 0 the glyphs sit 0.2 mm over it: coplanar for
    the z-fight rule, dc/zfight.py GEOM_EPS_D 0.3 mm). Default CONTAIN_TAG_LIFT (0.6 mm) for every user: the racks
    (checked by test_zfight), the CRAC and the PDU cabinet."""
    ZT = d["ZT"]
    z0, z1 = ZT + CONTAIN_Z[0], ZT + CONTAIN_Z[1]
    y0, yp = DM.CONTAIN_RAIL_Y
    mats = {"lip_lo": PAINT, "lip_hi": PAINT, "rail": PAINT, "channel": DARK, "pad": DARK, "standoff": DARK}
    for sy in (1, -1):
        for kind, lo, hi in contain_rail_boxes(sy, lod):
            part = P["dark"] if kind == "standoff" else P["contain"]
            G.box(part, (lo[0], lo[1], ZT + lo[2]), (hi[0], hi[1], ZT + hi[2]), mats[kind])
        if lod >= 2:
            continue
        if lod == 0:
            for xp in CONTAIN_PADS:   # the clamp screw, seated on the clip's upper jaw
                ym = sy * (y0 + yp) / 2
                G.cylinder(P["hw"], (xp, ym, z1 - 0.001), (xp, ym, z1 + 0.005), 0.0075, 6, HARDWARE)     # screw
        # the CONTAINMENT tag, clipped into the channel at the middle (between the two centre pads)
        F = F_front(CONTAIN_LIP_Y) if sy > 0 else F_back(-CONTAIN_LIP_Y)
        zm = (z0 + z1) / 2
        # (thin layers: the stencil's decal offset must stay inside the cell plane)
        G.prism(P["fine"], F, oct_pts(-0.088, zm - 0.021, 0.088, zm + 0.021, 0.008), 0.0, 0.0008, YELLOW)
        G.prism(P["fine"], F, oct_pts(-0.079, zm - 0.0125, 0.079, zm + 0.0125, 0.005), 0.0008, 0.0012, DARK)
        stencil(P["decal"], F, 0.0, zm, 0.0125, "CONTAINMENT", d=0.0014 + tag_lift - DECAL_OFFSET)


def _brush_lips(p, sx, sy, opening, ym, z_root, lod):
    """Two Darker bristle lips filling the opening (|x| x0..x1, |y| y0..y1; sx, sy mirror it): each is rooted under
    one long edge and droops 3.5 mm toward the slot y = ym, where the two tips meet with a hairline left between them
    (the waterfall bundle parts the bristles there).
    LOD0 combs each lip into 4 mm tufts with 0.8 mm gaps (the dark sleeve shows through them as fine strand lines),
    ragged tip lengths and a slightly uneven droop, so it reads as a brush strip and not as a rubber flap. LOD1 is one
    flat tuft per lip. Tufts are open boxes (top, tip, sides); their undersides face the sleeve and are never seen."""
    x0, x1, y0, y1 = opening
    bm = p.bm
    mi = p.mi(DARK)
    n = max(6, int(round((x1 - x0) / 0.004))) if lod == 0 else 1
    gap = 0.0008 if lod == 0 else 0.0
    droop, t = 0.0035, 0.003

    def jit(i, k):   # deterministic 0..1 per tuft (k picks an independent sequence)
        return ((i * (7919 + 104 * k) + 3 + 5 * k) % 13) / 12.0 if lod == 0 else 0.5

    for yr, side in ((y0, 1), (y1, -1)):   # side = +1: the lip grows toward +y from its root
        flip = sx * sy * side < 0             # every mirror reverses the winding

        def V(x, ly, z):                      # ly: distance from the root toward the slot
            return bm.verts.new((sx * x, sy * (yr + side * ly), z))

        def face(vs):
            f = bm.faces.new(list(reversed(vs)) if flip else vs)
            f.material_index = mi

        for i in range(n):
            xa = x0 + (x1 - x0) * i / n + (gap / 2 if i else 0.0)
            xb = x0 + (x1 - x0) * (i + 1) / n - (gap / 2 if i < n - 1 else 0.0)
            L = abs(ym - yr) - (0.0004 + 0.0012 * jit(i, 0))
            zr = z_root - 0.0003 * jit(i, 1)
            zt = z_root - droop - 0.0008 * jit(i, 2)
            rl, rr, tr, tl = V(xa, 0, zr), V(xb, 0, zr), V(xb, L, zt), V(xa, L, zt)
            rlb, rrb, trb, tlb = V(xa, 0, zr - t), V(xb, 0, zr - t), V(xb, L, zt - t), V(xa, L, zt - t)
            face([rl, rr, tr, tl])                      # top
            face([tl, tr, trb, tlb])                    # tip (faces the slot)
            face([rr, rrb, trb, tr])                    # +x side
            face([rl, tl, tlb, rlb])                    # -x side


def _entry_fitting(P, sx, sy, opening, H, z_bottom, lod, sleeve_front=True):
    """A top-entry brush plate (the cable gland where an overhead waterfall drops into a cable manager).
    - a Darker frame plate, its top ENTRY_DROP (1 mm) under the rack's top plane, standing ENTRY_FLANGE round the
      opening;
    - the Yellow edge: the frame's inner ENTRY_EDGE band, 0.3 mm lower (the safety edge the cables slide over);
    - two Darker bristle lips meeting along the slot (dc/rack._brush_lips, the measured "brush" part);
    - a Darker sleeve under the frame down to z_bottom: it carries the plate and ducts the drop (the full rack's
      trough carries the fans' hot exhaust; the half rack's roof-rail hole) to the manager below.
    opening = (x0, x1, y0, y1) in |x|, |y|; sx, sy = the corner it is mirrored to."""
    x0, x1, y0, y1 = opening
    F, E = DM.ENTRY_FLANGE, DM.ENTRY_EDGE
    zt = H - DM.ENTRY_DROP
    Ft = F_top(0.0)

    def R(a0, a1, b0, b1):   # (x0, x1, y0, y1) in |x|, |y| -> sorted world bounds
        xa, xb = sorted((sx * a0, sx * a1))
        ya, yb = sorted((sy * b0, sy * b1))
        return xa, xb, ya, yb

    def rect(a0, a1, b0, b1):
        xa, xb, ya, yb = R(a0, a1, b0, b1)
        return G.rect(xa, xb, ya, yb)

    if lod >= 2:   # a dark patch: the brush field as one plate
        xa, xb, ya, yb = R(x0, x1, y0, y1)
        G.box(P["fine"], (xa, ya, zt - 0.005), (xb, yb, zt - 0.0005), DARK)
        return
    xa, xb, ya, yb = R(x0 - F, x1 + F, y0 - F, y1 + F)
    G.ring(P["fine"], Ft, G.rect(xa, xb, ya, yb), rect(x0 - E, x1 + E, y0 - E, y1 + E), zt - 0.004, zt, DARK)
    G.ring(P["hw"], Ft, rect(x0 - E, x1 + E, y0 - E, y1 + E), rect(x0, x1, y0, y1), zt - 0.0035, zt - 0.0003, YELLOW)
    _brush_lips(P["brush"], sx, sy, opening, (y0 + y1) / 2, zt - 0.0005, lod)
    if lod == 1 and z_bottom > H - 0.05:
        return     # LOD1: a short sleeve (inside a roof-rail hole) is never seen at that range
    # the sleeve: 2 mm Darker walls 1 mm inside the frame outline, from the frame down to z_bottom
    w, i = 0.002, 0.001
    a0, a1, b0, b1 = x0 - F + i, x1 + F - i, y0 - F + i, y1 + F - i
    walls = [(a0, a0 + w, b0, b1), (a1 - w, a1, b0, b1), (a0 + w, a1 - w, b0, b0 + w)]
    if sleeve_front:
        walls.append((a0 + w, a1 - w, b1 - w, b1))
    for wa0, wa1, wb0, wb1 in walls:
        xa, xb, ya, yb = R(wa0, wa1, wb0, wb1)
        G.box(P["fine"], (xa, ya, z_bottom), (xb, yb, zt - 0.004), DARK)


def _tray(P, d, lod):
    """Full rack: the 0.25 m top cable tray. An open-top trough (the overhead drops land here) with Brushed
    lane dividers, brush-grommet drops into the front managers, a Colorable rim flush with the top (mounts), a
    front header carrying the label plate and power lamp, and a louvred rear header (hot-air exhaust)."""
    H, ZT = d["H"], d["ZT"]
    fr, dk, hw = P["frame"], P["dark"], P["hw"]
    # tray floor (= the slot ceiling) and trough bottom. The rear lane is the exhaust-fan lane: two round
    # openings through the floor; the fan module itself (housings, shroud lips, finger guards, leads, lamps) is the
    # static RackFanTray subpart and the rotors are InfiniteRotation subparts (dc/rack_doors.fan_tray / fan);
    # the fans pull the servers' hot air up out of the rear zone and blow it out of the open-top trough
    # placement fix: the floor's underside sits MOUNT_CLEAR over the slot ceiling plane (it would mount there on
    # every row otherwise; only the slot-ceiling hint, rear row, does)
    zc = ZT + MOUNT_CLEAR
    if lod <= 1:
        nh = 16 if lod == 0 else 12
        holes = [[(fx + x, DM.FAN_Y + y) for x, y in G.ngon(DM.FAN_R + 0.006, nh, math.pi / nh)] for fx in DM.FAN_X]
        G.plate(P["ceiling"], F_top(0.0), G.rect(-0.47, 0.47, -0.57, 0.57), holes, zc, ZT + 0.05, DARK)
        # (the fan module itself, housings, guards, leads and lamps, is the static RackFanTray subpart)
    else:
        G.box(P["ceiling"], (-0.47, -0.57, zc), (0.47, 0.57, ZT + 0.05), DARK)
    # rim: front / back strips and side strips, flush with the top plane
    a1 = W2 - CAP - 0.004
    for sy in (-1, 1):
        y0, y1 = sorted((sy * IY, sy * YK))
        G.box(fr, (-a1, y0, H - 0.03), (a1, y1, H - 0.0), PAINT)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * IX, sx * (W2 - SKIN)))
        G.box(fr, (x0, -(YK - CAP), H - 0.03), (x1, YK - CAP, H), PAINT)
        for sy in (-1, 1):   # fillers between the strips and the caps
            xa, xb = sorted((sx * a1, sx * IX))
            ya, yb = sorted((sy * IY, sy * (YK - CAP)))
            G.box(fr, (xa, ya, H - 0.03), (xb, yb, H), PAINT)
    # trough walls (Darker liners)
    for sy in (-1, 1):
        y0, y1 = sorted((sy * IY, sy * (IY + 0.012)))
        G.box(dk, (-IX, y0, zc), (IX, y1, H - 0.03), DARK)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * IX, sx * (IX + 0.012)))
        G.box(dk, (x0, -IY, zc), (x1, IY, H - 0.03), DARK)
    if lod <= 2:   # lane dividers (Brushed) and the cable lanes' perforated floor panels
        for yy in (-0.15, 0.15):
            G.box(hw, (-IX + 0.06, yy - 0.004, ZT + 0.05), (IX - 0.06, yy + 0.004, ZT + 0.11), STEEL)
        if lod <= 1:
            # Each cable lane gets a framed perforated tray floor (cables lie on it, air passes), a
            # Brushed frame with a 3 mm inset seam to the perforated sheet (the leaves' perforation)
            Ft = F_top(0.0)
            for y0, y1 in ((-0.142, 0.142), (0.158, SPINE_Y[1] - 0.012)):
                a0, a1 = -(IX - 0.07), IX - 0.07
                fw = 0.016
                G.ring(hw, Ft, G.rect(a0, a1, y0, y1), G.rect(a0 + fw, a1 - fw, y0 + fw, y1 - fw),
                       ZT + 0.05, ZT + 0.056, STEEL)
                g = 0.003
                xa, xb, ya, yb = a0 + fw + g, a1 - fw - g, y0 + fw + g, y1 - fw - g
                z = ZT + 0.0535
                perf_quad(P["perf"], [(xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z)], (0, 1))
    if lod <= 1:   # brush grommets: the drop openings into the front channels (rubber bristles = Darker)
        for sx in (-1, 1):
            xc = sorted((sx * CH_X[0], sx * CH_X[1]))
            G.box(dk, (xc[0] - 0.008, SPINE_Y[1] - 0.008, ZT + 0.05), (xc[1] + 0.008, IY, ZT + 0.062), YELLOW)
            G.box(dk, (xc[0], SPINE_Y[1], ZT + 0.051), (xc[1], IY - 0.004, ZT + 0.064), DARK)
    # The top-entry brush plates where the overhead tray's waterfalls come in (dims.TOP_ENTRY), each with
    # a sealed sleeve down to the floor grommet above (the trough carries the fans' hot exhaust; the front managers
    # are on the cold side, so the drop path is ducted from the top plane to the manager)
    (ex0, ex1), (ey0, ey1) = DM.TOP_ENTRY
    for sx in (-1, 1):
        _entry_fitting(P, sx, 1, (ex0, ex1, ey0, ey1), H, ZT + 0.062, lod, sleeve_front=False)
    # front header with the label, rear header with the exhaust louvre
    for F, front in ((F_front(YK - 0.016), True), (F_back(-YK + 0.016), False)):
        pts = oct_pts(-a1, ZT + 0.016, a1, H - 0.034, 0.03)
        if front or lod >= 2:
            G.prism(fr, F, pts, -0.013, 0.0, PAINT)
        else:
            _plate(fr, F, pts, -0.013, 0.0, PAINT, [G.rect(-0.26, 0.26, ZT + 0.06, H - 0.08)])
            louvre_panel(P["fine"], F, -0.26, ZT + 0.06, 0.26, H - 0.08, 6, lod)
        if front:
            _label(P, F, 0.0, (ZT + H) / 2 - 0.012, 0.0, 0.17, 0.06, lod, d["lamp"])
    # side skins of the tray band
    for sx in (-1, 1):
        F = F_side(sx)
        b1 = YK - CAP - 0.006
        G.prism(fr, F, oct_pts(-b1, ZT + 0.016, b1, H - 0.034, 0.03), -0.012, 0.0, PAINT)
        if lod == 0:
            for bb in (-b1 + 0.03, b1 - 0.03):
                bolt(hw, F, bb, (ZT + H) / 2 - 0.016, 0.0)


ROOF_RAIL_X = 0.30     # |x| where the thick roof rails over the side columns start (the slot roof stays 5 mm)
ROOF_RAIL_T = 0.028    # roof rail depth (inside the side columns: nothing below them is a slot)
ROOF_HEADER_Y = 0.45   # |y| where the deep front / rear roof headers start (server front hardware ends at 0.435)


def _roof(P, d, lod):
    """Half rack: no tray (the user's call). Visual pass 1: a layered roof instead of one flat sheet.
    - Over the slots (|x| < ROOF_RAIL_X) the roof stays a render-only 5 mm plate inside the top slot cells (no
      collision; the top slot stays free): a raised 5 mm border round a 3 mm field, an exhaust slot field over the
      rear (hot) half, a Darker ID plate at the front ("RACK" caption, a blank write-on tag: no baked ID)
      and an asset barcode.
    - Over each side column a 28 mm Colorable roof rail (the columns hold no slot space): the brush-grommet cable
      entries above the front / rear manager channels (Darker split brush lips in a deep pocket), a recessed
      lifting eye (Brushed ring in a Darker pocket) in the middle, and recessed fixing bolts."""
    H = d["H"]
    a, b = W2 - SKIN, YK
    c = CAP
    T = DM.HALF_ROOF_T
    rx = ROOF_RAIL_X
    if lod >= 2:
        pts = [(-a + c, -b), (a - c, -b), (a - c, -b + c), (a, -b + c), (a, b - c), (a - c, b - c), (a - c, b),
               (-a + c, b), (-a + c, b - c), (-a, b - c), (-a, -b + c), (-a + c, -b + c)]
        G.prism(P["ceiling"], F_top(0.0), pts, H - T, H, PAINT)
        return
    Ft = F_top(H)
    # ---- front / rear headers: 28 mm deep caps over the front / rear zones in front of the servers' hardware
    #      (server front hardware ends at y 0.435; the door leaves start at 0.600)
    hy = ROOF_HEADER_Y
    for sy in (-1, 1):
        y0, y1 = sorted((sy * hy, sy * b))
        if lod == 0:
            G.prism(P["frame"], Ft, oct_pts(-rx, y0, rx, y1, 0.012), -ROOF_RAIL_T, -0.002, PAINT)
            # a Darker inset strip with the cable-route arrows' slots and two bolts
            G.prism(P["dark"], Ft, oct_pts(-0.22, (y0 + y1) / 2 - 0.022, 0.22, (y0 + y1) / 2 + 0.022, 0.012), -0.006,
                    0.0, DARK)
            for xb in (-0.255, 0.255):
                bolt(P["hw"], Ft, xb, (y0 + y1) / 2, -0.006, r=0.008)
        else:
            G.prism(P["frame"], Ft, G.rect(-rx, rx, y0, y1), -ROOF_RAIL_T, 0.0, PAINT)
    b = hy
    # ---- the slot roof: border ring + recessed field (both inside the 5 mm)
    ring_w = 0.022
    G.plate(P["ceiling"], Ft, G.rect(-rx, rx, -b, b), [G.rect(-rx + ring_w, rx - ring_w, -b + ring_w, b - ring_w)],
            -T, 0.0, PAINT)
    holes = []
    if lod == 0:   # exhaust slots over the rear (hot) half: 2 rows of 9
        for row, yc in enumerate((-0.17, -0.33)):
            for k in range(9):
                xc = -0.20 + k * 0.05
                holes.append(G.rect(xc - 0.007, xc + 0.007, yc - 0.06, yc + 0.06))
    G.plate(P["ceiling"], Ft, G.rect(-rx + ring_w, rx - ring_w, -b + ring_w, b - ring_w), holes, -T, -0.003, PAINT)
    if lod == 0:   # the slots' Darker brush edging is the field's own walls; add the ID plate and barcode
        G.prism(P["fine"], Ft, oct_pts(-0.13, 0.20, 0.13, 0.40, 0.03), -0.003, -0.0025, DARK)
    if lod <= 1:
        Fid = Face((0, 0, H - 0.0025), (1, 0, 0), (0, 1, 0)) if lod == 0 else Face((0, 0, H - 0.003), (1, 0, 0),
                                                                                       (0, 1, 0))
        # read from the front aisle: a = -x, b = -y would mirror; the ID reads from the FRONT, so up = -y
        Fr = Face(Fid.o, (-1, 0, 0), (0, -1, 0))
        stencil(P["decal"], Fr, 0.0, -0.365, 0.035, LABEL, d=0.0)
        if lod == 0:
            # the blank write-on tag between the caption and the barcode (Fr: b = -y), on the Darker plate's top
            id_tag(P, Fr, -0.11, 0.11, -0.335, -0.248, 0.0, lod)
            from se2model import decals as DCL
            DCL.element(P["decal"], Fr, 0.0, -0.215, 0.16, S2, "barcode_long")
    # ---- the roof rails over the side columns
    for sx in (-1, 1):
        # (2 mm inside the side skin plane: the spawned RackSide panel's outer face lies in that plane, and the rail's
        # end face fought it, a subpart-vs-block z-fight found by dc/zfight.py subpart_frame_check, 2026-10-20)
        x0, x1 = sorted((sx * rx, sx * (a - 0.002)))
        ys = YK - c         # between the corner caps
        # The cable entries over the manager channels (front = data, rear = power) take the same top-entry
        # brush plate as the full rack (dims.HALF_TOP_ENTRY): the rail's hole is the plate's outline + 0.5 mm, the
        # plate's sleeve lines the hole down to the rail's underside, and the hole opens into the channel below
        (hx0, hx1), (hy0, hy1) = DM.HALF_TOP_ENTRY
        g = DM.ENTRY_FLANGE + 0.0005
        ent = []
        for sy in (-1, 1):
            xa, xb = sorted((sx * (hx0 - g), sx * (hx1 + g)))
            ya, yb = sorted((sy * (hy0 - g), sy * (hy1 + g)))
            ent.append(G.rect(xa, xb, ya, yb))
        eye = sorted((sx * 0.37, sx * 0.43))
        pocket = (eye[0], eye[1], -0.035, 0.035)
        hole_list = ent if lod >= 1 else ent + [oct_pts(pocket[0], pocket[2], pocket[1], pocket[3], 0.008)]
        G.plate(P["frame"], Ft, G.rect(x0, x1, -ys, ys), hole_list, -ROOF_RAIL_T, 0.0, PAINT)
        for sy in (-1, 1):
            _entry_fitting(P, sx, sy, (hx0, hx1, hy0, hy1), H, H - ROOF_RAIL_T, lod)
        if lod >= 1:
            continue
        # lifting eye: Darker pocket floor, a Brushed eye standing up in the pocket (top 4 mm under the roof)
        ex = (eye[0] + eye[1]) / 2
        G.box(P["dark"], (pocket[0], pocket[2], H - ROOF_RAIL_T), (pocket[1], pocket[3], H - ROOF_RAIL_T + 0.003), DARK)
        Fe = Face((ex, 0.0, H - 0.0145), (0, 1, 0), (0, 0, 1))
        G.ring(P["hw"], Fe, G.ngon(0.010, 12), G.ngon(0.0058, 12), -0.003, 0.003, STEEL)
        for yb_ in (-0.25, 0.25):   # recessed fixing bolts (heads 1 mm under the roof)
            bolt(P["hw"], Ft, ex, yb_, -0.006, r=0.008)


def _hinge_brackets(P, d, lod):
    """Door variants: the frame half of each leaf hinge, a Darker bracket plate on the post's front face (the leaf's
    knuckle barrels turn in front of it, 1 mm clear). It stops at |y| 0.5995, inside the 2.5 cm keep-out."""
    if lod >= 2:
        return
    H = d["H"]
    for sy in d["doors"]:
        y0, y1 = sorted((sy * (YK - 0.002), sy * (DM.DOOR_Y_BACK - 0.0005)))
        for sx in (-1, 1):
            x0, x1 = sorted((sx * (DM.DOOR_AXIS_X - 0.034), sx * (XO - 0.004)))
            for zh in DR.hinge_zs(d["spec"]):
                zl = zh + H / 2
                G.box(P["hw"], (x0, y0, zl - 0.05), (x1, y1, zl + 0.05), DARK)


def _lod3_full(P, d):
    """Silhouette for the full rack's LOD3 (budget 157 tris): plinth, two columns, tray, dark combs."""
    H, ZT = d["H"], d["ZT"]
    G.box(P["dark"], (-XO, -YK, 0.0), (XO, YK, 0.25), DARK)
    G.box(P["frame"], (-XO, -YK, ZT), (XO, YK, H), PAINT)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * XO, sx * 0.425))
        G.box(P["frame"], (x0, -YK, 0.25), (x1, YK, ZT), PAINT)
        x0, x1 = sorted((sx * SX, sx * 0.425))
        G.box(P["dark"], (x0, -SD, 0.25), (x1, SD, ZT), DARK)
        G.box(P["dark"], (x0, SD, 0.25), (x1, YK - 0.012, ZT), DARK)              # front manager
        x0, x1 = sorted((sx * BULK_X[0], sx * BULK_X[1]))
        G.box(P["frame"], (x0, -BULK_Y[1], 0.25), (x1, -BULK_Y[0], ZT), PAINT)   # rear: the PDU bulkhead


def last_lod(spec):
    """The 12-triangle box with the baked LastLOD material (earlier prototype's pattern)."""
    d = dims(spec)
    p = Part("lastlod")
    G.box(p, (-XO, -D2, -d["H"] / 2), (XO, D2, d["H"] / 2), f"{spec.name}_LastLOD")
    return [p]


# name -> LOD count fitted to the MEASURED LOD0 bounds (assemble.fit_lods; Keen's checker keys the LOD count on the
# mesh's bounding-box surface, and the full rack sits right at a row threshold: 4 LODs measured, 5 from its cells)
LOD_COUNT = {}


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


def size(spec):
    return tuple(0.25 * c for c in spec.cells)


def build(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the 12-tri box."""
    if lod == n_lods(spec) - 1:
        return last_lod(spec)
    d = dims(spec)
    P = {"frame": Part("frame"), "dark": Part("dark"), "fine": Part("fine"), "hw": Part("hw"), "decal": Part("decal"),
         "brush": Part("brush"),   # the top-entry bristle lips (measured: build_report geometry.top_entries)
         # interface parts kept as separate objects so the build can measure them (build_report "geometry")
         "rail": Part("rail"), "slide": Part("slide"), "slidebolt": Part("slidebolt"), "holes": Part("holes"),
         "ceiling": Part("ceiling"), "perf": Part("perf"),
         # the containment rail and the PDU receptacles' sockets (build_report geometry.contain_rails,
         # pdu_receptacles)
         "contain": Part("contain"), "socket": Part("socket")}
    P["decal"].decal = True
    P["perf"].decal = True
    if lod == 0:
        P["frame"].bevel = (0.005, 1)
        P["dark"].bevel = (0.004, 1)
        P["contain"].bevel = (0.003, 1)
    if lod >= 3:
        _lod3_full(P, d)
    else:
        _plinth(P, d, lod)
        _corners(P, d, lod)   # (the side skins are the static RackSide subpart since visual pass 2: dc/rack_side.py)
        _columns(P, d, lod)
        _hinge_brackets(P, d, lod)
        if d["tray"]:
            _tray(P, d, lod)
            _contain_rail(P, d, lod)
        else:
            _roof(P, d, lod)
    parts = [p for p in P.values() if not p.empty()]
    m = Matrix.Translation((0, 0, -d["H"] / 2))
    for p in parts:
        p.bm.transform(m)
        p.bm.normal_update()
    return parts


# ---------------------------------------------------------------------------------------------------- collision

def collision(spec):
    """{"regular": [(name, lo, hi)], "occupancy": [...], "mount": [...]}: axis-aligned boxes, Blender frame,
    centred like the render model. Regular = physics (frame only); occupancy = extra occupied cells; mount =
    mountpoints hints (boxes whose face lies exactly on the mounting plane).
    The side columns' physics starts at the PDU bracket plane y = -SLOT_HALF_D, so the rear PDU columns are
    free (FREE_CELLS); their strips mount on the pdu_bracket (the column's rear face) and pdu_seat (the plinth top)
    hints. The full racks' containment rail band mounts (contain_front / back: the only Forward / Backward mounts on
    the box planes); the half rack's top cross rails take the label pads (top_front / back)."""
    d = dims(spec)
    H, ZT = d["H"], d["ZT"]
    e = 0.002   # internal faces inset 2 mm so no slot cell is touched (the occupancy query box is 0.248 m)
    reg = [("plinth", (-W2, -D2, 0.0), (W2, D2, 0.25 - e))]
    for sx, nm in ((-1, "column_left"), (1, "column_right")):
        x0, x1 = sorted((sx * W2, sx * (SX + e)))
        reg.append((nm, (x0, -SD, 0.25 - e), (x1, D2, ZT + e if d["tray"] else H)))
    if d["tray"]:
        reg.append(("tray", (-W2, -D2, ZT + e), (W2, D2, H)))
    # Placement: the slot is open
    # to the front (no front-zone occupancy), and a thin physical REAR STOP closes its back: the block placer's ray
    # needs a physics body to hit at the back of an empty slot, and the first occupied cell it then crosses is the
    # stop's (rear-zone) cell, entered from the slot side, so the ghost lands in the slot's rear row and the server
    # (its Backward face on that cell) fills the slot exactly. The plate starts REAR_STOP_GAP behind the slot's back
    # plane (the servers' render ends 3 mm inside it) and still claims the rear-zone cells (the occupancy query box
    # reaches to 1 mm of the cell face), so nothing can be built into the cable space, as before.
    reg.append(("rear_stop", (-SX + e, -(SD + REAR_STOP_GAP + REAR_STOP_T), 0.25 + e),
                (SX - e, -(SD + REAR_STOP_GAP), ZT - e)))
    occ = []
    t = 0.005
    # the slot's mount points are KEYED to its rear row (game z = +1, Blender |y| SD-0.25 .. SD at the back): the rail
    # faces, the slot floor (plinth top) and ceiling (tray floor) mount only there, so a server mounts only with its
    # rear cells on the rear row, i.e. at its designed depth; one cell forward (into the door zone) it touches no
    # mount (its cells are free, so the placer would otherwise accept it). Their render stays >= 2.5 cm off the
    # planes elsewhere (the plinth deck, the tray floor), see _plinth / _tray.
    yr0, yr1 = -SD, -SD + KEY_ROW
    mnt = []
    for sx, nm in ((-1, "left"), (1, "right")):
        x0, x1 = sorted((sx * W2, sx * (W2 - t)))
        mnt.append((f"side_{nm}", (x0, -YK, 0.0), (x1, YK, H)))
        x0, x1 = sorted((sx * SX, sx * (SX + t)))
        mnt.append((f"rail_{nm}", (x0, yr0, 0.25), (x1, yr1, ZT)))
    mnt.append(("bottom", (-W2, -YK, 0.0), (W2, YK, t)))
    mnt.append(("slot_floor", (-SX, yr0, 0.25 - t), (SX, yr1, 0.25)))
    if d["tray"]:
        mnt.append(("slot_ceiling", (-SX, yr0, ZT), (SX, yr1, ZT + t)))
        for sy in (-1, 1):
            y0, y1 = sorted((sy * IY, sy * YK))
            mnt.append((f"rim_{'front' if sy > 0 else 'back'}", (-W2, y0, H - t), (W2, y1, H)))
        for sx in (-1, 1):
            x0, x1 = sorted((sx * IX, sx * W2))
            mnt.append((f"rim_{'right' if sx > 0 else 'left'}", (x0, -YK, H - t), (x1, YK, H)))
        for sy in (-1, 1):   # the containment rail band (dims.CONTAIN_RAIL_Y x ZT + CONTAIN_RAIL_DZ)
            y0, y1 = sorted((sy * D2, sy * (D2 - t)))
            mnt.append((f"contain_{'front' if sy > 0 else 'back'}", (-W2, y0, ZT + DM.CONTAIN_RAIL_DZ[0]),
                        (W2, y1, ZT + DM.CONTAIN_RAIL_DZ[1])))
    else:
        for sx in (-1, 1):
            x0, x1 = sorted((sx * SX, sx * W2))
            mnt.append((f"top_{'right' if sx > 0 else 'left'}", (x0, -YK, H - t), (x1, YK, H)))
        for sy in (-1, 1):   # the label pads over the front / back roof headers (the rim band of the full rack)
            y0, y1 = sorted((sy * IY, sy * YK))
            mnt.append((f"top_{'front' if sy > 0 else 'back'}", (-SX, y0, H - t), (SX, y1, H)))
    for feed, sx in PDU_FEED_SIGN.items():   # the PDU strips' seat (plinth top) and bracket (the column's rear face)
        x0, x1 = sorted((sx * SX, sx * XO))
        mnt.append((f"pdu_seat_{feed}", (x0, -YK, 0.25 - t), (x1, -SD, 0.25)))
        mnt.append((f"pdu_bracket_{feed}", (x0, -SD, 0.25), (x1, -SD + t, ZT)))
    dz = -H / 2

    def sh(boxes):
        return [(n, (lo[0], lo[1], lo[2] + dz), (hi[0], hi[1], hi[2] + dz)) for n, lo, hi in boxes]
    return {"regular": sh(reg), "occupancy": sh(occ), "mount": sh(mnt)}
