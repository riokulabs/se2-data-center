"""Cable plans of the bends and junctions (Plan 2 Task 3): TurnH, TurnUp, TurnDown, Tee and Cross. Pure Python.

Same frame and data types as dc/tray_plan.py (the box-corner frame; ports, bundles, structure, supports, fittings).

**Bends.** A bend's centreline is a 5 cm straight lead from each port with one circular arc between (the PORT rule:
bundles are straight for their last 5 cm). Every lane is the offset curve of the centreline at its (s, h) in the
moving frame (t along, s = u x t across, u the floor normal), so the bundles keep their lane order and spacing
through the bend and all share the arc's centre: lane radius = R - s (TurnH, left-hand), R - h (TurnUp, concave)
or R + h (TurnDown, convex). The leads take 5 cm off the piece table's floor-line radii, which are measured port to
port: R = 0.45 / 0.405 / 0.245, centred 5 cm in from the table's centres, so both ports stay exactly on the grid.
Straps sit on radial lines (Decision 13): 0.125 m of centreline from each port, evenly spaced at the pitch nearest
0.25 m between.

**Tee.** A real tray tee: the cables on the branch side of the run turn into the branch, from both directions, and
the far side runs straight through. The run's -y half (piece frame; M0 included) is straight a -> b. Its +y half
turns: from port a left into the branch (they land on the branch's s' >= 0 lanes), from port b right (s' < 0).
Every turning group is concentric with the junction's wall fillet, so lane order and spacing hold exactly (as in a
TurnH). The branch's M0 is a SPLIT child of the straight M0: it leaves a Darker split collar and peels off on the
outermost arc of the left group, at floor level, as cables fan out of a collar (the widened split zone, P2-16).
Nothing crosses anything, so the Tee needs no saddle. (A tap in which every through lane continues and the branch
is split off them cannot be built at Full: M0 and L1 lie under the top layer and could only leave it through a
bundle; see the Task 3 report.)

**Cross.** The a-b lanes run straight. The c-d lanes ramp up as one stack at <= 30 deg, ride a Darker crossover
saddle over the a-b bundles (the bottom layer resting on its deck, DECK_H above the floor top) and ramp down again,
level for the last 5 cm at each port. The saddle stands on four Brushed legs in the corners of the crossing, where
no bundle runs, bolted through the floor.

**Walls.** Junction walls stand JUNCTION_WALL_H (0.15) high within JUNCTION_REACH (0.2 m, along the path) of an
opening, which on these 1 m pieces is all of them. Openings are cut out of the run's walls and closed by r 0.15
fillets (one "wall" path each) into the branch's walls.
"""
import math

import numpy as np

from . import catalog, tray_lanes as TL, tray_xsec as XS
from .tray_lanes import CELL, FLOOR_Z, R_B, Port, lanes, mirror, vec
from .tray_plan import (BASKET_BOTTOM, END_INSET, STRUT_H, STRUT_LIFT, STRUT_W, X, Y, Z, Bundle, End, Fitting,
                        Frame, Path, Support, _plan, _straps, _xs)

LEAD = TL.PORT_STRAIGHT         # 5 cm straight lead at every port
ARC_STEP = 0.008                # centreline step on arcs (outer lanes: <= 0.02 even at 1.4 x the radius)
TURN_R = {"TurnH": 0.50 - LEAD, "TurnUp": 0.455 - LEAD, "TurnDown": 0.295 - LEAD}   # centreline / floor-line radius
MIN_LANE_R = 0.25               # no lane bends tighter than this (data-cable bend limits, ~10 x the bundle diameter)


def _rot(v, k, a):
    """v rotated by angle a about the unit axis k (Rodrigues)."""
    v, k = vec(v), vec(k)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * (k @ v) * (1 - math.cos(a))


class Sweep:
    """A centreline with a moving frame (point, t, u): straight leads and circular arcs. lane(s, h) gives the offset
    curve of one lane; frames(l) the frame at arc length l."""

    def __init__(self, p0, t0, u0):
        self.segs = []          # (kind, start point, t, u, length, centre, axis, radius)
        self.p, self.t, self.u = vec(p0), vec(t0), vec(u0)
        self.length = 0.0

    def line(self, L):
        self.segs.append(("line", self.p, self.t, self.u, L, None, None, None))
        self.p = self.p + L * self.t
        self.length += L
        return self

    def arc(self, toward, r, angle):
        """Turn towards the unit direction `toward` (perpendicular to t) about a centre r away, through `angle`."""
        toward = vec(toward)
        c, k = self.p + r * toward, np.cross(self.t, toward)
        self.segs.append(("arc", self.p, self.t, self.u, r * angle, c, k, r))
        self.p, self.t, self.u = c + _rot(self.p - c, k, angle), _rot(self.t, k, angle), _rot(self.u, k, angle)
        self.length += r * angle
        return self

    def frame(self, l):
        """(point, t, s, u) at centreline arc length l."""
        for i, (kind, p, t, u, L, c, k, r) in enumerate(self.segs):
            if l <= L + 1e-12 or i == len(self.segs) - 1:
                l = min(l, L)
                if kind == "line":
                    q = p + l * t
                else:
                    a = l / r
                    q, t, u = c + _rot(p - c, k, a), _rot(t, k, a), _rot(u, k, a)
                return q, t, np.cross(u, t), u
            l -= L
        raise AssertionError

    def stations(self):
        """Centreline arc lengths sampled <= ARC_STEP on arcs, <= 2 cm on leads; every segment end included."""
        out, l0 = [0.0], 0.0
        for kind, *_, L, _c, _k, _r in self.segs:
            n = max(1, math.ceil(L / (ARC_STEP if kind == "arc" else TL.BUNDLE_STEP) - 1e-9))
            out += [l0 + L * i / n for i in range(1, n + 1)]
            l0 += L
        return out

    def arc_seg(self):
        return next(sg for sg in self.segs if sg[0] == "arc")

    def lane(self, s, h, ls=None):
        return np.array([q + s * ss + h * u for q, _, ss, u in (self.frame(l) for l in (ls or self.stations()))])

    def path(self, **kw):
        ls = self.stations()
        fr = [self.frame(l) for l in ls]
        return Path(np.array([f[0] for f in fr]), np.array([f[3] for f in fr]), **kw)


def _port(name, p, t, u, density):
    return Port(name, tuple(float(round(v, 12)) + 0.0 for v in p), tuple(float(v) + 0.0 for v in np.round(t, 12)),
                tuple(float(v) + 0.0 for v in np.round(u, 12)), density)


# ---------------------------------------------------------------------------------------------------- bends
def bend_sweep(shape):
    """The centreline of a bend, from port a: lead, arc, lead."""
    r = TURN_R[shape]
    if shape == "TurnH":     # a (0, 0.25) heading +x, turning left about (0.05, 0.70) to b (0.5, 0.75) heading +y
        sw = Sweep((0.0, CELL, FLOOR_Z), X, Z).line(LEAD).arc(Y, r, math.pi / 2).line(LEAD)
    elif shape == "TurnUp":  # a (0, z 0.045) heading +x, up about (0.05, z 0.45) to b (0.455, z 0.5) heading +z
        sw = Sweep((0.0, CELL, FLOOR_Z), X, Z).line(LEAD).arc(Z, r, math.pi / 2).line(LEAD)
    else:                    # TurnDown: a (0, z 0.295) heading +x, over about (0.05, z 0.05) to b (0.295, z 0) down
        sw = Sweep((0.0, CELL, CELL + FLOOR_Z), X, Z).line(LEAD).arc(-Z, r, math.pi / 2).line(LEAD)
    return sw


def bend_centre(shape):
    return bend_sweep(shape).arc_seg()[5]


def radial_stations(L):
    """Strap stations along a bend's centreline: 0.125 from each port, evenly between at the pitch nearest 0.25."""
    span = L - 2 * TL.STRAP_PHASE
    n = max(1, round(span / TL.STRAP_PITCH))
    return [TL.STRAP_PHASE + span * k / n for k in range(n + 1)]


def _floor_strut(position, axis, up=Z, half=CELL - END_INSET):
    p = {"strut": (STRUT_W, STRUT_H), "up": vec(up)}
    if half >= CELL - 1e-12:
        p["flush"] = True          # its end caps lie ON the across faces (the vertical turns: see _bend)
    return Support("floor_strut", vec(position), vec(axis), (-half, half), [], p)


def _bend(shape, density):
    cells = catalog.TRAY_CELLS[shape]
    sw = bend_sweep(shape)
    q0, t0, _, u0 = sw.frame(0.0)
    q1, t1, _, u1 = sw.frame(sw.length)
    ports = {"a": _port("a", q0, -t0, u0, density), "b": _port("b", q1, t1, u1, density)}
    ls = sw.stations()
    bundles = []
    for l in lanes(density):
        b = Bundle(sw.lane(l.s, l.h, ls), l.material, R_B, (End("PORT", "a:" + mirror(l.name)),
                                                         End("PORT", "b:" + l.name)), l.name,
                   {"along": [float(v) for v in ls]})     # each point's centreline arc length (the kit's facets)
        bundles.append(b)
    c = sw.arc_seg()[5]
    fittings = []
    for st in radial_stations(sw.length):
        q, t, s, u = sw.frame(st)
        for l, b in zip(lanes(density), bundles):
            d = 2 * (R_B + TL.STRAP_T)
            fittings.append(Fitting("strap", Frame(q + l.s * s + l.h * u, t, s, u), (TL.STRAP_W, d, d),
                                    {"bundle": b.lane, "station": st, "centre": c.copy()}))
    zs = STRUT_LIFT + STRUT_H / 2           # a strut's centre over the grid plane under the floor
    if shape == "TurnH":                    # on the 45 deg radial, under that radial's U-wire, as wide as the basket
        q, t, s, u = sw.frame(LEAD + TURN_R[shape] * math.pi / 4)        # (its ends at the U-wire legs: Ruling P2-20)
        supports = [_floor_strut((q[0], q[1], zs), -s, half=TL.U_LEG_S + TL.WIRE_R)]
    elif shape == "TurnUp":                 # under port a's lead, at the U-wire where the arc starts
        supports = [_floor_strut((LEAD, CELL, zs), Y, half=CELL)]
    else:                                   # TurnDown: behind port b's (vertical) floor, on the grid plane x = 0.25,
        supports = [_floor_strut((CELL + zs, CELL, LEAD), Y, X, half=CELL)]    # at the U-wire where the arc ends
    # (the vertical turns' struts run the full 0.5 m across, their end-cap bolts ON the across faces: the model then
    # spans 0.5 m, so Keen's checker sizes it as the 2 x 2 x 2 block it is. Every other part of these turns stops
    # short of 0.5 m, and at 0.498 m the checker applies its small-model limits of 4 / 3 / 1 materials, which the
    # lane colours cannot meet and which fail the build. Back to back with whatever is beside it, never seen.)
    structure = [sw.path(arc=(LEAD, LEAD + TURN_R[shape] * math.pi / 2, math.pi / 2))]
    return _plan(shape, density, cells, ports, bundles, structure, supports, fittings)


def plan_bend(shape, density):
    if shape in TURN_R:
        return _bend(shape, density)
    if shape == "Tee":
        return _tee(density)
    return _cross(density)


# ---------------------------------------------------------------------------------------------------- junctions
J_Y = CELL                                   # the Tee's run centreline (y)
FIL_X = 0.5 - TL.WALL_S - TL.FILLET_R        # 0.14: the left fillet's centre x (the turning groups' centre too)
FIL_Y = J_Y + TL.WALL_S + TL.FILLET_R        # 0.61: ... and y; the branch walls start here
FIL_STEP = 24                                # fillet wall samples


def _strap_at(sw, l, lane, bundle, centre):
    q, t, s, u = sw.frame(l)
    d = 2 * (R_B + TL.STRAP_T)
    return Fitting("strap", Frame(q + lane.s * s + lane.h * u, t, s, u), (TL.STRAP_W, d, d),
                   {"bundle": bundle, "station": l, "centre": vec(centre)})


def _fillet(centre, start, end, zf):
    """A junction wall fillet: a quarter arc of radius FILLET_R about `centre` (x, y) from `start` to `end`."""
    c = vec((centre[0], centre[1], zf))
    a, b = vec((start[0], start[1], zf)) - c, vec((end[0], end[1], zf)) - c
    pts = np.array([c + math.cos(f) * a + math.sin(f) * b for f in np.linspace(0, math.pi / 2, FIL_STEP)])
    return Path(pts, np.tile(Z, (len(pts), 1)), (True, True), TL.JUNCTION_WALL_H, (), "wall")


# At Full, M0 lies under F1+ and F1-: they touch it, leaving no room for its split collar. Over the collar the two
# are dressed 3 mm outward and 7 mm up (cable installers part a bundle to fit a collar), with C1 ramps that keep the
# first 5 cm from each port straight and every bend radius over 5 cm.
COLLAR_DRESS = (0.003, 0.007)
COLLAR_DRESS_X = (0.05, 0.105, 0.16, 0.215)     # ramp up, hold (the collar spans 0.11 .. 0.14), ramp down


def _smooth(x, x0, x1):
    t = min(1.0, max(0.0, (x - x0) / (x1 - x0)))
    return t * t * (3 - 2 * t)


def collar_dress(x):
    """The dressing weight at x (0 .. 1)."""
    a, b, c, d = COLLAR_DRESS_X
    return min(_smooth(x, a, b), 1.0 - _smooth(x, c, d))


def _dressed(sw, lane, sign):
    """Lane `lane` along sweep `sw`, displaced by the collar dressing (sign: the across direction away from M0)."""
    out = []
    for l in _fine(sw):
        q, t, s, u = sw.frame(l)
        w = collar_dress(q[0])
        out.append(q + (lane.s + sign * COLLAR_DRESS[0] * w) * s + (lane.h + COLLAR_DRESS[1] * w) * u)
    return np.array(out)


def _fine(sw):
    """Stations at most 1 cm apart (a dressed lane curves)."""
    out = []
    for a, b in zip(sw.stations()[:-1], sw.stations()[1:]):
        n = max(1, math.ceil((b - a) / 0.01 - 1e-9))
        out += [a + (b - a) * k / n for k in range(n)]
    return out + [sw.length]


def _turning(lane, side, zf):
    """A Tee lane on the run's +y half that turns into the branch: from port a (side -1, a left turn) or b (+1, a
    right turn), concentric with that side's wall fillet. -> (sweep, bundle)."""
    sig = lane.s                                         # > 0: the piece-frame lane's offset towards the branch
    x_port, heading = (0.0, X) if side < 0 else (1.0, -X)
    x_c = 0.5 + side * (0.5 - FIL_X)                     # the group centre's x (0.14 or 0.86)
    rho = FIL_Y - (J_Y + sig)
    sw = (Sweep((x_port, J_Y + sig, zf + lane.h), heading, Z).line(abs(x_c - x_port)).arc(Y, rho, math.pi / 2)
          .line(0.75 - FIL_Y))
    c_lane = lane.name if side < 0 else mirror(lane.name)   # left lands on s' = +sig, right on s' = -sig
    port = "a:" + mirror(lane.name) if side < 0 else "b:" + lane.name
    dress = side < 0 and lane.name == "F1+"           # over the M0 collar (left of the left group's start)
    pts = _dressed(sw, TL.Lane(lane.name, 0.0, 0.0, "", ""), 1.0) if dress else sw.lane(0, 0)
    along = _fine(sw) if dress else sw.stations()
    return sw, Bundle(pts, lane.material, R_B, (End("PORT", port), End("PORT", "c:" + c_lane)),
                      c_lane + "/c", {"centre": vec((x_c, FIL_Y, zf)), **_facet_params(sw, along, dress)})


BREAKOUT_DX = 0.12      # (Task 10, carry M-3) the breakout tie: this far past the collar's far end along M0


def _breakout_tie(m0, child, rho, zf, straight):
    """The Tee's breakout tie (Task 10, M-3): the branch M0 peels on a 0.36 m arc concentric with the left turning
    group (it cannot peel tighter: it is that group's outermost lane), so it stays inside its parent's envelope for
    about 0.19 m past the collar and read as one fused yellow mass. A cable installer ties a fan-out where the
    branch leaves its run: one Darker band, BREAKOUT_DX past the collar, round M0, the peeling branch and (at Full)
    the F1- bundle nested on M0, all in the plane x = const (one shared band, Ruling P2-17). LOD0 only (fine
    dressing, like the Drop's fall ties); off the 0.25 m strap rhythm by purpose (it marks the breakout)."""
    xb = FIL_X + BREAKOUT_DX
    h = TL.LANE["M0"].h
    d = 2 * (R_B + TL.STRAP_T)
    th = math.asin(BREAKOUT_DX / rho)
    out = [Fitting("strap", Frame(vec((xb, J_Y, zf + h)), X.copy(), Y.copy(), Z.copy()), (TL.STRAP_W, d, d),
                   {"bundle": "M0", "station": xb, "breakout": True, "lod0_only": True}),
           Fitting("strap", Frame(vec((xb, FIL_Y - rho * math.cos(th), zf + h)), X.copy(), Y.copy(), Z.copy()),
                   (TL.STRAP_W, d, d), {"bundle": child.lane, "station": rho * th, "breakout": True,
                                        "lod0_only": True})]
    for b in straight:          # the straight bundles nested on M0 at the tie (F1- at Full)
        if b.lane == "F1-":
            lane = TL.LANE["F1-"]
            out.append(Fitting("strap", Frame(vec((xb, J_Y + lane.s, zf + lane.h)), X.copy(), Y.copy(), Z.copy()),
                               (TL.STRAP_W, d, d), {"bundle": b.lane, "station": xb, "breakout": True,
                                                    "lod0_only": True}))
    return out


def _segs(sw):
    return [(kind, L, (L / r if kind == "arc" else 0.0)) for kind, _p, _t, _u, L, _c, _k, r in sw.segs]


def _facet_params(sw, along, dressed=False):
    """A junction bundle's own facet stations per LOD (tray_xsec.sweep_facets: its arcs faceted on radials every
    <= 15 deg, like a bend's) and its points' arc lengths along its sweep, so the kit re-samples it there. A bundle
    dressed over the M0 collar also keeps its ramps at LOD0 (every 1 cm), the only LOD that draws the collar."""
    extra0 = ()
    if dressed:
        a, _, _, d = COLLAR_DRESS_X
        xs = [sw.frame(l)[0][0] for l in along]
        extra0 = [l for l, x in zip(along, xs) if a - 1e-9 <= x <= d + 1e-9]
    segs = _segs(sw)
    return {"along": [float(v) for v in along],
            "facets": [XS.sweep_facets(segs, 0, extra0), XS.sweep_facets(segs, 1), XS.sweep_facets(segs, 2)]}


def _tee(density):
    cells = catalog.TRAY_CELLS["Tee"]
    L, zf = cells[0] * CELL, FLOOR_Z
    ports = {"a": _port("a", (0.0, J_Y, zf), -X, Z, density), "b": _port("b", (L, J_Y, zf), X, Z, density),
             "c": _port("c", (0.5, 0.75, zf), Y, Z, density)}
    from .tray_plan import _collar, _through
    straight = [_through(l, L, zf) for l in lanes(density) if l.s <= 1e-12]
    if "M0" in {l.name for l in lanes(density)}:
        for i, b in enumerate(straight):
            if b.lane == "F1-":                       # parted from M0 over its collar
                sw = Sweep((0.0, J_Y, zf), X, Z).line(L)
                straight[i] = Bundle(_dressed(sw, TL.LANE["F1-"], -1.0), b.material, R_B, b.ends, b.lane)
    bundles, fittings = list(straight), []
    for side in (-1, 1):
        for l in (l for l in lanes(density) if l.s > 1e-12):
            sw, b = _turning(l, side, zf)
            bundles.append(b)
            lane0 = TL.Lane(l.name, 0.0, 0.0, l.material, l.first)
            for st in (TL.STRAP_PHASE, sw.segs[0][4] + sw.segs[1][4] / 2, sw.length - TL.STRAP_PHASE):
                fittings.append(_strap_at(sw, st, lane0, b.lane, b.params["centre"]))
    m0 = next((b for b in straight if b.lane == "M0"), None)
    if m0 is not None:      # the branch's M0: a split off the straight M0, peeling on the left group's outer arc
        rho = FIL_Y - J_Y
        sw = Sweep((FIL_X, J_Y, zf + TL.LANE["M0"].h), X, Z).arc(Y, rho, math.pi / 2).line(0.75 - FIL_Y)
        child = Bundle(sw.lane(0, 0), m0.material, R_B, (End("SPLIT", "M0"), End("PORT", "c:M0")), "M0/c",
                       {"peel_r": rho, "centre": vec((FIL_X, FIL_Y, zf)), **_facet_params(sw, sw.stations())})
        bundles.append(child)
        fittings.append(_collar(m0, FIL_X - TL.SPLIT_COLLAR_L / 2))     # the collar takes the strap's place there
        lane0 = TL.Lane("M0", 0.0, 0.0, m0.material, "Moderate")
        for st in (sw.segs[0][4] / 2, sw.length - TL.STRAP_PHASE):
            fittings.append(_strap_at(sw, st, lane0, child.lane, child.params["centre"]))
        fittings += _breakout_tie(m0, child, rho, zf, straight)
    for f in _straps(straight, L):
        if not (m0 is not None and f.params["bundle"] == "M0" and abs(f.params["station"] - TL.STRAP_PHASE) < 1e-9):
            fittings.append(f)
    cut = (FIL_X, L - FIL_X)
    main = Path(np.array([(x, J_Y, zf) for x in _xs(0.0, L)]), np.tile(Z, (len(_xs(0.0, L)), 1)), (True, True),
                TL.JUNCTION_WALL_H, ((1, cut, TL.FILLET_R),))
    ys = _xs(J_Y + TL.WALL_S, 0.75)
    branch = Path(np.array([(0.5, y, zf) for y in ys]), np.tile(Z, (len(ys), 1)), (True, True), TL.JUNCTION_WALL_H,
                  tuple((k, (0.0, TL.FILLET_R), TL.FILLET_R) for k in (0, 1)))
    w = J_Y + TL.WALL_S
    fillets = [_fillet((FIL_X, FIL_Y), (FIL_X, w), (0.5 - TL.WALL_S, FIL_Y), zf),
               _fillet((L - FIL_X, FIL_Y), (L - FIL_X, w), (0.5 + TL.WALL_S, FIL_Y), zf)]
    zs = STRUT_LIFT + STRUT_H / 2
    supports = [_floor_strut((0.5, J_Y, zs), Y)]
    return _plan("Tee", density, cells, ports, bundles, [main, branch] + fillets, supports, fittings)


X_C = 0.5                       # the Cross's centre (x and y)
RAMP = math.radians(30)         # the c-d stack climbs at 30 deg ...
RAMP_R_IN = 0.12                # ... on a concave arc (centre above: lanes R - h, the top layer 0.06) ...
RAMP_R_OUT = 0.06               # ... and a convex one (centre below: lanes R + h)
DECK_T = 0.004                  # saddle deck plate
SADDLE_LEG = 0.012              # square Brushed legs ...
SADDLE_HALF = 0.235             # the deck's half size: it starts just after the c-d stack levels out (y 0.263)
SADDLE_LEG_AT = SADDLE_HALF - SADDLE_LEG / 2    # legs under the deck's corners, clear of both stacks and the fillets
SADDLE_LEG_T = 0.213            # ... their across-a-b position (x), under the flat deck, just inside the side lips
# The deck is formed steel (Task 7): both ends where the c-d stack climbs on roll down on the stack's own convex radius
# (no cable-cutting edge: the cables leave the deck along it), as tongues narrower than the deck (clear of the
# fillets); both sides along the stack are rolled up into lips (they keep the stack on the deck, and stiffen the
# plate); the deck straps are tied to it at tie mounts beside the stack.
ROLL_R = RAMP_R_OUT             # the rolled ends' top radius = the stack's convex arc (they part as it straightens)
ROLL_ANG = math.radians(75)     # ... rolled through 75 deg
ROLL_HALF = 0.21                # ... over the stack's width (+-0.197) and a little more
LIP_R, LIP_H = 0.010, 0.030     # side lips: inner bend radius, height over the deck top
TIE_T = 0.209                   # tie mounts: across position (x), 12 mm outside the stack ...
TIE_SIZE = (0.008, 0.024, 0.005)    # ... x, y, height (on the deck top)
FOOT = (0.026, 0.003)           # leg foot clamp plates (on the floor wires, and a backing plate under the basket)


def cross_sweep(zf=FLOOR_Z):
    """The c-d floor line: level lead, up over the saddle (deck DECK_H over the floor top), level, down, lead."""
    rise = TL.DECK_H - (RAMP_R_IN + RAMP_R_OUT) * (1 - math.cos(RAMP))
    incline = rise / math.sin(RAMP)
    sw = Sweep((X_C, 0.0, zf), Y, Z).line(LEAD)
    sw.arc(Z, RAMP_R_IN, RAMP).line(incline)
    sw.arc(-sw.u, RAMP_R_OUT, RAMP)
    ramp_y = sw.p[1]
    sw.line(1.0 - 2 * ramp_y)
    sw.arc(-sw.u, RAMP_R_OUT, RAMP).line(incline)
    sw.arc(sw.u, RAMP_R_IN, RAMP).line(LEAD)
    assert abs(sw.p[1] - 1.0) < 1e-9 and abs(sw.p[2] - zf) < 1e-9
    return sw


def _cross(density):
    cells = catalog.TRAY_CELLS["Cross"]
    zf = FLOOR_Z
    ports = {"a": _port("a", (0.0, X_C, zf), -X, Z, density), "b": _port("b", (1.0, X_C, zf), X, Z, density),
             "c": _port("c", (X_C, 0.0, zf), -Y, Z, density), "d": _port("d", (X_C, 1.0, zf), Y, Z, density)}
    ab, cd, fittings = [], [], []
    for l in lanes(density):
        pts = np.array([(x, X_C + l.s, zf + l.h) for x in _xs(0.0, 1.0)])
        ab.append(Bundle(pts, l.material, R_B, (End("PORT", "a:" + mirror(l.name)), End("PORT", "b:" + l.name)),
                         l.name))
    sw = cross_sweep(zf)
    ls = sw.stations()
    fp = _facet_params(sw, ls)          # the stack's ramps faceted on shared lines (every lane an offset of one sweep)
    for l in lanes(density):
        cd.append(Bundle(sw.lane(l.s, l.h, ls), l.material, R_B,
                         (End("PORT", "c:" + mirror(l.name)), End("PORT", "d:" + l.name)), l.name + "/d", dict(fp)))
    fittings += _straps_along_x(ab, zf)
    for y in (TL.STRAP_PHASE + k * TL.STRAP_PITCH for k in range(4)):     # the run's rhythm, measured along y
        st = _station_at_y(sw, y)
        for l, b in zip(lanes(density), cd):
            fittings.append(_strap_at(sw, st, l, b.lane, (X_C, y, zf)))
    fittings.append(Fitting(
        "crossover_saddle", Frame(vec((X_C, X_C, zf)), X.copy(), Y.copy(), Z.copy()),
        (2 * SADDLE_HALF, 2 * SADDLE_HALF, TL.DECK_H - (BASKET_BOTTOM - FLOOR_Z)),
        {"deck_h": TL.DECK_H, "deck_top": TL.DECK_H, "deck_t": DECK_T, "leg_w": SADDLE_LEG,
         "leg_bottom": BASKET_BOTTOM - FLOOR_Z, "legs": [(i * SADDLE_LEG_T, j * SADDLE_LEG_AT) for i in (-1, 1)
                                                          for j in (-1, 1)],
         "roll_r": ROLL_R, "roll_angle": ROLL_ANG, "roll_half": ROLL_HALF, "lip_r": LIP_R, "lip_h": LIP_H,
         "ties": [y - X_C for y in (TL.STRAP_PHASE + k * TL.STRAP_PITCH for k in range(4))
                  if abs(y - X_C) < SADDLE_HALF],
         "tie_t": TIE_T, "tie_size": TIE_SIZE, "foot": FOOT, "stencil": "X-OVER",
         "carries": [b.lane for b in cd], "material": "PaintedMetalDarker", "leg_material": "BrushedMetal"}))
    cut = (FIL_X, 1.0 - FIL_X)
    xs = _xs(0.0, 1.0)
    run_ab = Path(np.array([(x, X_C, zf) for x in xs]), np.tile(Z, (len(xs), 1)), (True, True), TL.JUNCTION_WALL_H,
                  tuple((k, cut, TL.FILLET_R) for k in (0, 1)))
    run_cd = Path(np.array([(X_C, y, zf) for y in xs]), np.tile(Z, (len(xs), 1)), (True, True), TL.JUNCTION_WALL_H,
                  tuple((k, cut, TL.FILLET_R) for k in (0, 1)))
    lo, hi = X_C - TL.WALL_S, X_C + TL.WALL_S          # the arms' wall lines (0.29, 0.71)
    fillets = [_fillet((cx, cy), (cx, lo if cy < X_C else hi), (lo if cx < X_C else hi, cy), zf)
               for cx in (FIL_X, 1.0 - FIL_X) for cy in (FIL_X, 1.0 - FIL_X)]
    zs = STRUT_LIFT + STRUT_H / 2
    supports = [_floor_strut((X_C, X_C, zs), Y)]        # under the saddle
    return _plan("Cross", density, cells, ports, ab + cd, [run_ab, run_cd] + fillets, supports, fittings)


def _station_at_y(sw, y):
    """The centreline arc length at which the c-d floor line reaches y."""
    lo, hi = 0.0, sw.length
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if sw.frame(mid)[0][1] < y else (lo, mid)
    return (lo + hi) / 2


def _straps_along_x(bundles, zf):
    out = []
    for x in (TL.STRAP_PHASE + k * TL.STRAP_PITCH for k in range(4)):
        for b in bundles:
            l = TL.LANE[b.lane]
            d = 2 * (R_B + TL.STRAP_T)
            out.append(Fitting("strap", Frame(vec((x, X_C + l.s, zf + l.h)), X.copy(), Y.copy(), Z.copy()),
                               (TL.STRAP_W, d, d), {"bundle": b.lane, "station": x}))
    return out
