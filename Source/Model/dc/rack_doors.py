"""Rack door leaves and tray fan rotors (Task 9): the subpart models (Blender; numbers in dc/dims.py, dc/doors.py).

Leaf (APC-style split door, one of two per side; model frame: origin ON the hinge axis at the block's mid-height,
+Y = the leaf's outside face, Z up). DoorLeafR is hinged on its +x edge and extends toward -x (s = +1), DoorLeafL is
its mirror (s = -1); u = distance from the axis toward the free (meeting) edge, x = -s * u.
Part -> purpose:
  - Colorable frame (hinge stile, meeting stile, top / bottom / mid rails): the leaf's structure, carries the paint;
  - perforated steel insert (vanilla MetalPerforationSteel: an alpha-masked perforation, ~44 % open): cold-aisle
    air in, see the servers' lamps through the door; two back-to-back quads so it reads from both sides;
  - hinge barrels (MetalDull, three knuckles per hinge, Brushed pin caps) on the axis, the hinge leaf plates
    bolted to the hinge stile: they are round about the axis, so they look still while the leaf swings;
  - one recessed swing-handle latch on the ACTIVE leaf (DoorLeafL; Rittal / APC style): a Darker clipped escutcheon
    (bezel + pocket), a Brushed fold-flat L-handle on a MetalDull pivot boss, a Brushed key cylinder, a Stickers01
    lock pictogram and an 8 mm chevron border (Stickers02 yellow band over a Darker backing) round the escutcheon
    ONLY: the pinch point where the leaves meet. Everything stays inside the 2.3 cm leaf layer;
  - the meeting stile's rubber seal strip (Darker) on the free edge (the passive leaf has only this).
Fan rotor (model frame: origin on the rotation axis, Z = the axis): hub, Brushed cap, seven pitched blades, the motor
can. Fan tray (static subpart, origin on the fan lane's centre on the trough floor): see fan_tray().
"""
import math

from mathutils import Matrix
from se2model import decals as DC
from se2model import geom as G
from se2model.geom import Face, Part

from . import dims as DM
from . import doors
from se2model.config import S1

from .style import DARK, HARDWARE, PAINT, STEEL, oct_pts, perf_quad

FW = 0.045                       # frame member width
T = DM.DOOR_HALF_T               # half the leaf thickness (0.0115)
VF = T - 0.004                   # frame front face (4 mm behind the layer: room for the recessed latch)
VB = -T                          # frame back face
SEAL_T = 0.003                   # meeting edge seal strip: how far it stands past the (shortened) meeting stile


def _perf_quad(p, x0, x1, z0, z1, v, facing):
    """One vertical perforated quad at y = v (facing +1 = +y)."""
    pts = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    if facing < 0:
        pts.reverse()
    return perf_quad(p, [(x, v, z) for x, z in pts], (0, 2))


def leaf(spec, model, lod):
    """Parts of one leaf LOD (not the last: see last_box)."""
    s = 1 if model == doors.LEAF_R else -1
    z0, z1 = doors.z_range(spec)
    u0, W = DM.DOOR_U0, DM.DOOR_W

    def X(ua, ub):   # sorted x range for a u range
        return sorted((-s * ua, -s * ub))

    def box(part, ua, ub, va, vb, za, zb, mat):
        xa, xb = X(ua, ub)
        G.box(part, (xa, va, za), (xb, vb, zb), mat)

    P = {k: Part(k) for k in ("frame", "dark", "hw", "perf", "decal")}
    P["perf"].decal = True        # open quads: keep the authored winding and the UVs
    P["decal"].decal = True
    if lod == 0:
        P["frame"].bevel = (0.003, 1)
    fr, dk, hw = P["frame"], P["dark"], P["hw"]
    zm = (z0 + z1) / 2
    mid = (z1 - z0) > 0.8                              # a mid rail on the tall leaves (two panes)
    rails = [(z0, z0 + FW), (z1 - FW, z1)] + ([(zm - FW / 2, zm + FW / 2)] if mid else [])
    # frame: hinge stile, meeting stile, rails
    box(fr, u0, u0 + FW, VB, VF, z0, z1, PAINT)
    # the meeting stile stops SEAL_T short of the free edge at LOD0: the seal strip, not the stile, is the edge
    # (one face per plane; the old full-width stile shared its end face with the seal: in-game edge z-fighting)
    box(fr, W - FW, W - (SEAL_T if lod == 0 else 0.0), VB, VF, z0, z1, PAINT)
    for za, zb in rails:
        box(fr, u0 + FW, W - FW, VB, VF, za, zb, PAINT)
    # perforated panes (overlap 4 mm under the frame so no light leaks at the joints)
    edges = sorted({z for r in rails for z in r})
    panes = [(edges[i], edges[i + 1]) for i in range(1, len(edges) - 1, 2)]
    for za, zb in panes:
        xa, xb = X(u0 + FW - 0.004, W - FW + 0.004)
        _perf_quad(P["perf"], xa, xb, za - 0.004, zb + 0.004, 0.002, +1)
        _perf_quad(P["perf"], xa, xb, za - 0.004, zb + 0.004, 0.000, -1)
    # hinges: three knuckles on the axis (the middle one reads as the frame's), pin caps, the leaf plate
    sides = 12 if lod == 0 else 6
    for zh in doors.hinge_zs(spec):
        if lod <= 1:
            knuckles = ((-0.06, -0.021), (-0.019, 0.019), (0.021, 0.06)) if lod == 0 else ((-0.06, 0.06),)
            for ka, kb in knuckles:
                G.cylinder(hw, (0, 0, zh + ka), (0, 0, zh + kb), DM.DOOR_KNUCKLE_R, sides, HARDWARE)
            if lod == 0:
                for e, d in ((-0.06, -0.066), (0.06, 0.066)):
                    G.cylinder(hw, (0, 0, zh + e), (0, 0, zh + d), 0.0055, 8, STEEL)
            box(dk, 0.004, u0 + FW - 0.006, VF - 0.001, VF + 0.0015, zh - 0.05, zh + 0.05, DARK)
            if lod == 0:   # two hex bolts through the plate into the stile (inside the leaf layer)
                xb = -s * (u0 + FW / 2)
                for zb in (zh - 0.03, zh + 0.03):
                    G.cylinder(hw, (xb, VF + 0.0015, zb), (xb, VF + 0.0037, zb), 0.0065, 6, HARDWARE)
        else:
            box(hw, -DM.DOOR_KNUCKLE_R, DM.DOOR_KNUCKLE_R, -DM.DOOR_KNUCKLE_R, DM.DOOR_KNUCKLE_R,
                zh - 0.06, zh + 0.06, HARDWARE)
    # meeting edge seal strip (Darker rubber) on the free edge
    if lod == 0:   # 2 mm under the stile's end, 3 mm proud of it: the free edge
        box(dk, W - SEAL_T - 0.002, W, VB + 0.003, VF - 0.003, z0 + 0.01, z1 - 0.01, DARK)
    # recessed swing-handle latch (Rittal / APC style) on the meeting stile: a Darker escutcheon with a clipped bezel
    # round a pocket, a fold-flat MetalDull L-handle on its pivot boss, a Brushed key cylinder, a lock pictogram, and
    # a THIN (8 mm) chevron border round the escutcheon only. All of it stays inside the leaf layer (|v| <= T).
    # One active leaf carries the latch (DoorLeafL: the front's right-hand leaf as you face it; on the rear the
    # mirrored model puts it on the other side); the passive leaf meets it with its seal only, as on real racks.
    if model == doors.LEAF_L:
        _handle(P, s, spec, lod)
    return [p for p in P.values() if not p.empty()]


ESC_U = (DM.DOOR_W - 0.060, DM.DOOR_W - 0.010)   # escutcheon u range: the stile plus 15 mm over the pane
ESC_HH = 0.10                                  # escutcheon half height
HAZ_W = 0.008                                  # hazard chevron border width
LEVER_DROP = 0.0008                            # the lever's top under the bezel / boss top (boss at -0.2 mm)


def _handle(P, s, spec, lod):
    dk, hw = P["dark"], P["hw"]
    zc = doors.handle_z(spec)
    Fd = Face((0, 0, 0), (-1, 0, 0), (0, 0, 1))        # the leaf's outside face frame: a = -x = s * u, b = z, d = y
    a0, a1 = sorted((s * ESC_U[0], s * ESC_U[1]))
    ac = (a0 + a1) / 2
    hw2, hh = (a1 - a0) / 2, ESC_HH
    d_back, d_plate, d_bezel = VF + 0.0008, VF + 0.0012, VF + 0.0036
    # Darker backing plate under the chevron border (bolted over the stile, reaching back onto the pane)
    G.prism(dk, Fd, G.rect(a0 - HAZ_W, a1 + HAZ_W, zc - hh - HAZ_W, zc + hh + HAZ_W), 0.0005, d_back, DARK)
    if lod >= 1:   # far: the escutcheon as one clipped block, the flat lever (and the border at LOD1)
        G.prism(dk, Fd, oct_pts(a0, zc - hh, a1, zc + hh, 0.012), d_back, d_plate, DARK)
        G.prism(hw, Fd, G.rect(ac - 0.0065, ac + 0.0065, zc - hh + 0.05, zc + hh - 0.017), d_plate,
                d_bezel - 0.0004, HARDWARE)
        if lod == 1:
            for (a, b, L, hgt, vert) in ((a0 - HAZ_W / 2, zc, 2 * hh + 2 * HAZ_W, HAZ_W, True),
                                         (a1 + HAZ_W / 2, zc, 2 * hh + 2 * HAZ_W, HAZ_W, True),
                                         (ac, zc + hh + HAZ_W / 2, 2 * hw2, HAZ_W, False),
                                         (ac, zc - hh - HAZ_W / 2, 2 * hw2, HAZ_W, False)):
                DC.stripes(P["decal"], Fd, a, b, L, hgt, "yellow", d=d_back - 0.0012, vertical=vert)
        return
    c = 0.012
    outer = oct_pts(-hw2, -hh, hw2, hh, c)
    inner = oct_pts(-hw2 + 0.006, -hh + 0.006, hw2 - 0.006, hh - 0.006, c * 0.6)
    G.ring(dk, Fd, outer, inner, d_back, d_bezel, DARK, ca=ac, cb=zc)        # bezel (4 mm proud of the stile)
    G.prism(dk, Fd, inner, d_back, d_plate, DARK, ca=ac, cb=zc)               # the pocket floor, 2.4 mm down
    # the chevron border: four thin bands just outside the bezel, on the backing plate
    for (a, b, L, hgt, vert) in ((a0 - HAZ_W / 2, zc, 2 * hh + 2 * HAZ_W, HAZ_W, True),
                                 (a1 + HAZ_W / 2, zc, 2 * hh + 2 * HAZ_W, HAZ_W, True),
                                 (ac, zc + hh + HAZ_W / 2, 2 * hw2, HAZ_W, False),
                                 (ac, zc - hh - HAZ_W / 2, 2 * hw2, HAZ_W, False)):
        DC.stripes(P["decal"], Fd, a, b, L, hgt, "yellow", d=d_back - 0.0012, vertical=vert)
    # fold-flat L-handle: pivot boss at the top, the grip bar down the pocket, a finger foot turned toward the edge
    zp, zf = zc + hh - 0.026, zc - hh + 0.05
    n = 16 if lod == 0 else 8
    G.cylinder(hw, Fd(ac, zp, d_plate), Fd(ac, zp, d_bezel - 0.0002), 0.0095, n, HARDWARE)
    # the bar runs under the boss: its top LEVER_DROP below the boss top, its underside 0.6 mm off the pocket floor
    # (the boss stands on the floor): no coplanar face pair
    G.prism(hw, Fd, G.rect(ac - 0.0065, ac + 0.0065, zf + 0.012, zp), d_plate + 0.0006, d_bezel - LEVER_DROP, STEEL)
    foot = sorted((ac - s * 0.0065, ac + s * 0.018))           # the L's foot: one piece with the bar's end
    G.prism(hw, Fd, G.rect(foot[0], foot[1], zf, zf + 0.012), d_plate + 0.0006, d_bezel - LEVER_DROP, STEEL)
    if lod == 0:
        G.cylinder(hw, Fd(ac, zp, d_bezel - 0.0002), Fd(ac, zp, d_bezel + 0.0003), 0.004, 8, STEEL)   # rivet
        zk = zc - hh + 0.022                                                                   # key cylinder
        G.cylinder(hw, Fd(ac, zk, d_plate), Fd(ac, zk, d_bezel - 0.0002), 0.0068, 16, STEEL)
        G.prism(dk, Fd, G.rect(ac - 0.0009, ac + 0.0009, zk - 0.004, zk + 0.004), d_bezel - 0.0006,
                d_bezel + 0.0003, DARK)                                       # key slot, 0.5 mm over the cylinder
        DC.element(P["decal"], Fd, ac - s * 0.0135, zk, 0.011, S1, "lock",
                   "white", d=d_plate - 0.0012)                                                 # lock pictogram


def leaf_last(lo, hi):
    p = Part("leaf_last")
    G.box(p, lo, hi, PAINT)
    return [p]


# ------------------------------------------------------------------------------------------------ fan tray
# Fan rotor: model origin on the rotation axis (Z), hub mid-height. It turns inside its housing in the static tray.
def fan(spec, lod):
    """Exhaust fan rotor: hub with a Brushed cap, seven pitched blades, the motor can up to the guard's centre disc
    (round about the axis, so it reads as the fixed motor while the rotor spins)."""
    hub, bl = Part("hub"), Part("blades")
    n = 20 if lod == 0 else 10
    G.cylinder(hub, (0, 0, -0.011), (0, 0, 0.011), 0.032, n, DARK)
    G.cylinder(hub, (0, 0, 0.011), (0, 0, doors.FAN_CAN_TOP), 0.021, n, HARDWARE)
    if lod == 0:
        G.cylinder(hub, (0, 0, -0.0125), (0, 0, -0.011), 0.022, n, STEEL)
    nb = 7 if lod == 0 else 5
    for k in range(nb):
        m = (Matrix.Rotation(2 * math.pi * k / nb, 4, "Z") @ Matrix.Translation((0.0, 0.0625, 0.0))
             @ Matrix.Rotation(math.radians(30), 4, "Y"))
        G.box(bl, (-0.021, -0.031, -0.0016), (0.021, 0.031, 0.0016), DARK, matrix=m)
    return [hub, bl]


def fan_last(lo, hi):
    p = Part("fan_last")
    G.box(p, lo, hi, DARK)
    return [p]


def fan_tray(spec, lod):
    """The static fan tray (model origin: the fan lane's centre on the trough floor; Z up, +Y toward the rack front).
    Part -> purpose: a two-panel Colorable tray plate (seam + screws) = the removable fan module; per fan a square
    Darker housing with the round opening and a MetalDull shroud lip; a finger guard (three rings, four spokes and a
    centre disc carrying the motor and the fan's stencil ID); a power lead to a connector on the plate; a status lamp
    on the housing; the CAUTION MOVING PARTS label on the housing's aisle-side face."""
    from se2model import decals as DCL
    from .style import LAMP_GREEN, STENCIL_WHITE, lamp, stencil
    P = {k: Part(k) for k in ("plate", "dark", "hw", "cable", "decal")}
    P["decal"].decal = True
    if lod == 0:
        P["plate"].bevel = (0.002, 1)
    L = doors.FAN_TRAY
    Ft = Face((0, 0, 0), (1, 0, 0), (0, 1, 0))
    hx, hy, tp, hz = L["half_x"], L["half_y"], L["plate_t"], L["housing_h"]
    seam = 0.002
    nh = 24 if lod == 0 else (10 if lod == 1 else 0)
    r_open = L["open_r"]
    for sx in (-1, 1):                    # two plate panels (one per fan), a 4 mm seam; the fan's air opening
        x0, x1 = sorted((sx * seam, sx * hx))
        fx = DM.FAN_X[0] if sx < 0 else DM.FAN_X[1]
        if nh:
            G.plate(P["plate"], Ft, G.rect(x0, x1, -hy, hy),
                    [[(fx + x, y) for x, y in G.ngon(r_open, nh, math.pi / nh)]], 0.0, tp, PAINT)
        else:
            G.box(P["plate"], (x0, -hy, 0.0), (x1, hy, tp), PAINT)
        if lod == 0:
            for xs in (x0 + 0.014, x1 - 0.014):
                for ys in (-hy + 0.014, hy - 0.014):
                    G.cylinder(P["hw"], (xs, ys, tp - 0.0005), (xs, ys, tp + 0.0025), 0.0045, 6, HARDWARE)
    hs = L["housing_half"]
    for i, fx in enumerate(DM.FAN_X):
        z0, z1 = tp, tp + hz
        if nh:
            hole = [(fx + x, y) for x, y in G.ngon(r_open, nh, math.pi / nh)]
            G.plate(P["dark"], Ft, oct_pts(fx - hs, -hs, fx + hs, hs, 0.02), [hole], z0, z1, DARK)
            G.ring(P["hw"], Ft, G.ngon(r_open + 0.012, nh, math.pi / nh), G.ngon(r_open, nh, math.pi / nh),
                   z1, z1 + 0.004, HARDWARE, ca=fx)                                      # shroud lip
        else:
            G.prism(P["dark"], Ft, oct_pts(fx - hs, -hs, fx + hs, hs, 0.02), z0, z1, DARK)
        if lod <= 1:                                                                     # finger guard
            zg = z1 + 0.006
            ng = 20 if lod == 0 else 10
            for r in (L["guard_r"][:3] if lod == 0 else L["guard_r"][:1]):
                G.ring(P["hw"], Ft, G.ngon(r + 0.0016, ng), G.ngon(r - 0.0016, ng), zg - 0.002, zg, HARDWARE, ca=fx)
            for k in range(4):
                m = Matrix.Translation((fx, 0, 0)) @ Matrix.Rotation(math.pi / 4 + k * math.pi / 2, 4, "Z")
                G.box(P["hw"], (0.02, -0.0016, zg - 0.0024), (r_open + 0.008, 0.0016, zg + 0.0004), HARDWARE,
                      matrix=m)
            for k in range(4 if lod == 0 else 0):                                         # spoke feet on the lip
                ang = math.pi / 4 + k * math.pi / 2
                px, py = fx + (r_open + 0.006) * math.cos(ang), (r_open + 0.006) * math.sin(ang)
                G.box(P["hw"], (px - 0.004, py - 0.004, z1), (px + 0.004, py + 0.004, zg), HARDWARE)
            G.cylinder(P["dark"], (fx, 0, zg - 0.0035), (fx, 0, zg + 0.0015), 0.026, 20 if lod == 0 else 10, DARK)
            if lod == 0:
                # reads from the front aisle (text up = -y as seen from above)
                stencil(P["decal"], Face((fx, 0, zg + 0.0015), (-1, 0, 0), (0, -1, 0)), 0.0, 0.0, 0.016, f"F{i + 1}")
        if lod == 0:
            # status lamp on the housing's aisle-side corner, CAUTION MOVING PARTS on its aisle-side face
            lamp(P["hw"], Face((fx + 0.0, 0, z1), (1, 0, 0), (0, 1, 0)), -0.085 if fx < 0 else 0.085, hs - 0.024,
                 0.0, r=0.006, lod=0, mat=LAMP_GREEN)
            Ff = Face((fx, hs, z0), (-1, 0, 0), (0, 0, 1))     # normal +y (toward the rack front / the cable lanes)
            DCL.element(P["decal"], Ff, 0.0, hz / 2, 0.05, DCL.S2, "moving_parts")
            # power lead: housing wall -> a latching connector on the plate (inboard side, toward the seam)
            sgn = 1 if fx < 0 else -1
            xw = fx + sgn * hs
            cx = xw + sgn * 0.05
            G.box(P["hw"], (min(cx - 0.012, cx + 0.012), 0.035, tp), (max(cx - 0.012, cx + 0.012), 0.065, tp + 0.016),
                  HARDWARE)                                                              # connector body
            G.box(P["dark"], (cx - 0.006, 0.065, tp + 0.004), (cx + 0.006, 0.071, tp + 0.012), DARK)  # latch
            G.pipe_path(P["cable"], [(xw, 0.02, tp + 0.03), (xw + sgn * 0.025, 0.02, tp + 0.03),
                                     (cx, 0.03, tp + 0.008), (cx, 0.05, tp + 0.008)], 0.0045, 8, "Rubber",
                        bend=0.012)
    return [p for p in P.values() if not p.empty()]


def fan_tray_last(lo, hi):
    p = Part("tray_last")
    G.box(p, lo, hi, DARK)
    return [p]


SUBPARTS = {doors.LEAF_L: (lambda spec, lod: leaf(spec, doors.LEAF_L, lod), leaf_last),
            doors.LEAF_R: (lambda spec, lod: leaf(spec, doors.LEAF_R, lod), leaf_last),
            doors.FAN: (fan, fan_last), doors.FAN_TRAY_SUB: (fan_tray, fan_tray_last)}


def subparts_for(spec):
    """Every rack's subpart models: door leaves, tray fan + static tray (full racks), the static side panel."""
    from . import rack_side
    names = doors.leaf_models(spec) + ([doors.FAN, doors.FAN_TRAY_SUB] if doors.fan_points(spec) else [])
    out = {n: SUBPARTS[n] for n in names}
    out[rack_side.SIDE_SUB] = (rack_side.build, rack_side.last)
    return out
