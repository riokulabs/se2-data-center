"""Cable plans of the tray pieces. Pure Python (numpy), no Blender.

A plan says, for one piece at one density, where everything goes: the ports, every bundle's centreline, the basket's
centreline paths, the supports and the fittings. The Blender kit (dc/tray_kit.py) only sweeps and dresses what the
plan says, so the cable continuity contract (dc/tray_lanes.py) is proven here, offline, by Tests/test_tray_contract.py.

Frame: the **box-corner frame**. x runs along from the -X face, y across from the -Y face, z up from the bottom
face; the cell box is [0, size]. The builder centres it (``PiecePlan.to_block``). In every straight-type piece the
tray centreline runs along x at y = 0.25, and the piece's own lane names are those of port b (s = +y); port a's
across axis is -y, so a bundle that leaves port b on lane L1+ leaves port a on lane L1- (``tray_lanes.mirror``).

The linear shapes (StraightS, StraightL, Reducer, Drop, Chute, Rods) are planned here; the bends and junctions
(TurnH, TurnUp, TurnDown, Tee, Cross) in dc/tray_bends.py, which builds on these data types and helpers.
"""
import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import catalog, dims as DM, tray_lanes as TL
from .tray_lanes import CELL, FLOOR_Z, LANE, R_B, R_WF, Port, lanes, mirror, vec

X, Y, Z = np.eye(3)
SHAPES = ("StraightS", "StraightL", "TurnH", "TurnUp", "TurnDown", "Tee", "Cross", "Drop", "Reducer", "Chute", "Rods")
BENDS = ("TurnH", "TurnUp", "TurnDown", "Tee", "Cross")            # planned in dc/tray_bends.py
LATER = ()                                                          # every shape is planned
STYLES = ("basket",)                                                # "ladder" may follow (Decision 1)
FITTING_KINDS = ("split_collar", "boot", "saddle_clamp", "tag", "waterfall_guide", "crossover_saddle", "strap",
                 "brush_collar", "bundle_clamp")
CYLINDER_FITTINGS = ("strap", "split_collar", "boot", "brush_collar", "bundle_clamp")   # sampled as cylinders along t
SUPPORT_KINDS = ("trapeze", "floor_strut", "rods", "ladder")
POINT_PARAMS = ("centre",)      # params that are points / directions (moved by PiecePlan.transformed); every
DIR_PARAMS = ("across", "toward", "up", "axis")   # other param is a size or an offset in the object's own frame


def _move_params(T, params):
    return {k: T(v) if k in POINT_PARAMS else T.dir(v) if k in DIR_PARAMS else v for k, v in params.items()}

Y_C = CELL                      # 0.25: the tray centreline across its 2 cells (a grid line)

# ---------------------------------------------------------------------------------------------------- hardware
STRUT_W = 0.040                 # strut channel 40 x 28 mm ...
STRUT_H = 0.028
STRUT_LIFT = 0.001              # ... its bottom 1 mm above the cell plane: its top (0.029) carries the basket
BASKET_BOTTOM = STRUT_LIFT + STRUT_H    # the U-wires' underside (floor top 0.045 = 2 wire layers of r 4 mm above it)
END_INSET = 0.001               # strut end plates and rod ends stay 1 mm inside the box
ROD_PLATE = 2 * (CELL - TL.ROD_S - END_INSET)   # 0.034: rod-coupler plate (square), 1 mm inside the side faces
ROD_PLATE_T = 0.006             # ... thick; its top 1 mm under the top plane (it bolts to the plane above)
COUPLER_AF = 0.022              # rod hanger: the coupling nut on each rod's bottom end, hex 22 mm across flats ...
COUPLER_R = COUPLER_AF / 2 / math.cos(math.pi / 6)   # ... (across corners / 2)
COUPLER_L = 0.030
WASHER_T = 0.003                # ... seated in a square washer the size of the tray's rod plate (ROD_PLATE)
ANCHOR = (0.060, ROD_PLATE, 0.006)   # rod hanger: a Darker ceiling anchor plate over each rod (x, y, thick), 1 mm under
#                                      the top plane, 4 anchor bolts; the ceiling strut channel hangs under the pair
CEIL_STRUT = (0.040, 0.028)     # the ceiling channel (Darker, lipped, opening down) across both rods: width, depth
STRUT_CAP = 0.004               # yellow end caps on the strut's end plates
COLLAR_L = TL.SPLIT_COLLAR_L   # split collar along the parent
COLLAR_T = 0.004                # ... wall thickness over the parent
BOOT_X = 0.30                   # Reducer: dropped lanes end here (from port a) ...
BOOT_L = 0.040                  # ... in a rubber boot from 5 mm behind the end to 35 mm past it
BOOT_BACK = 0.005
BOOT_T = 0.003                  # ... standing 3 mm proud of the bundle
CLAMP_X = BOOT_X + 0.02         # the saddle clamp straps the boot's body (0.295 .. 0.335) ...
CLAMP_L = 0.012                 # ... with a band this wide, on a post standing from the floor
CLAMP_MAX_HW = 0.030            # clamp half width across, at most ...
CLAMP_CLEAR = 0.004             # ... keeping 4 mm from every through bundle and the wall wires
BOOT_CLEAR = TL.STRAP_T + 0.0015   # a boot keeps this much off the through bundles: its clamp band, plus 1.5 mm
TAG = (0.14, 0.002, 0.05)       # density tag on each wall's outside: along, thickness, height
TAG_H = 0.025                   # tag bottom above the floor top (between the floor and the top wire)
TAG_X = 0.125                   # tag centre from port a (on the dropped side, clear of the trapeze rods at L / 2)
TAG_S = TL.U_LEG_S + TL.WIRE_R + 0.0015 + TAG[1] / 2   # clipped on the outside of the U-wire legs
TAG_TEXT = {"Full": "F>M", "Moderate": "M>L", "Low": "L>0"}

# ---------------------------------------------------------------------------------------------------- the Drop
# The waterfalls leave over the tray's front wall (+y) and fall into the rack's front cable managers through the
# top-entry brush plates. Each one peels off lane L1+ (piece frame) at a split collar, climbs straight up out
# of the bundle, bends over towards its rack-side end, swings across the tray in plan at crest height, rolls over a
# radius guide on the wall and falls plumb to the Drop's bottom plane.
WF_SPLIT_DX = 0.18              # split collar this far from the waterfall's x, towards the Drop's centre
WF_GUIDE_R = 0.10               # bundle-centre radius over the guide (the fibre and copper bend limit)
WF_CREST = 0.147                # bundle-centre height over the crest (>= 0.13): the guide plate under it clears the
#                                 safety-edge wire AND the basket's U-wire turned over it (one U-wire stands
#                                 under each guide), by the gap its two spring clamps bridge
WF_RISE_R = 0.05                # the climb's bend (vertical -> along x)
WF_GUIDE_T = 0.006              # guide plate thickness (under the bundle), ribs included
WF_GUIDE_W = 0.090              # guide width along x, cheeks included
WF_GUIDE_LEAD = math.radians(20)    # the guide plate starts 20 deg before the crest (inside the tray)
WF_GUIDE_CHEEK = (0.004, 0.016)     # the moulded trough's side cheeks: thickness, height over the plate top
WF_GUIDE_RIB = (0.002, 0.005, math.radians(10))   # its ribbed top: rib height (the bundle rides the rib crests at
#                                                   r_top), width along the arc, angular pitch
WF_CLAMP_DX = 0.030             # two Brushed spring clamps, this far either side of the waterfall, clip the guide over
WF_CLAMP = (0.008, 0.0015)      # the safety-edge wire: strip width (along x), thickness
WF_STRAPS = (0.125, 0.375)      # bundle ties on the fall, at these heights over the bottom plane (the Chute's rung
#                                 rhythm 0.125 + k 0.25 carries on up through a Drop over a Chute)
ENTRY_SEAT = 0.0                # the landing collar and the Chute's plates sit ON their ENTRY plane (an
#                                 interface plane like a port: the rack's brush frame is ENTRY_DROP under it, the
#                                 Chute's top plate meets the Drop's collar there), not 1 mm over it: the old 2 mm float
#                                 over the brush frame closes to the rack's own 1 mm (dims.ENTRY_DROP)
ENTRY_COLLAR = dict(h=0.006, wall=0.006, gap=0.005)   # the landing brush collar on the rack's brush plate: height, ring
#                                 wall, and the bristle gap between its bore and the bundle
WF_S_C = DM.WF_Y - DM.TRAY_RACK_Y - WF_GUIDE_R      # 0.2075: guide centre across (tray-centreline relative)
WF_FALL_S = WF_S_C + WF_GUIDE_R                      # 0.3075: the plumb line (= WF_Y in rack terms)
DROP_Y_OFF = Y_C - DM.TRAY_RACK_Y                    # Drop y = rack-local y + 0.125
# At Full the waterfall climbs between F1+ and F3+, which are 85 mm apart: too narrow for it. Over the middle of the
# Drop the two are dressed 10.5 mm apart and 12 mm up, onto the bottom layer's shoulders: the waterfall passes with
# WF_CLEAR to spare, and they stay clear of M0, L1+ and M2+. Front side only: only the front has waterfalls (a "make
# way for the drop" dressing, as cable installers do at a drop-out).
WF_CLEAR = 0.003                # the waterfall's surface clearance from every bundle but its parent
DRESS = {"F1+": (0.032, 0.072), "F3+": (0.138, 0.072)}
DRESS_X = (0.07, 0.22)          # dressing ramps (from each port): straight lanes for the first 7 cm, flat from 22 cm


# ---------------------------------------------------------------------------------------------------- data
@dataclass(frozen=True)
class End:
    kind: str                   # tray_lanes.END_KINDS
    ref: str                    # PORT "a:L1+"; SPLIT the parent bundle's lane; BOOT "boot:<lane>"; ENTRY the rect


@dataclass
class Bundle:
    points: np.ndarray          # (N, 3) centreline, <= BUNDLE_STEP apart
    material: str
    radius: float
    ends: Tuple[End, End]
    lane: str                   # its id in the piece: a lane name, "<lane>/<port>" (a junction's branch or crossing
    #                             bundle, by its lane at that port), or "WF-" / "WF+"
    params: dict = field(default_factory=dict)   # "peel_r": a SPLIT child's first bend radius (tray_lanes.split_zone)

    @property
    def lane_name(self):
        """The contract lane this bundle carries (None for a waterfall)."""
        return None if self.lane.startswith("WF") else self.lane.split("/")[0]

    def length(self):
        return float(np.linalg.norm(np.diff(self.points, axis=0), axis=1).sum())

    def end_point(self, i):
        return self.points[0 if i == 0 else -1]

    def end_dir(self, i):
        """Outward direction at end i (0 = start, 1 = finish)."""
        p = self.points
        d = p[0] - p[1] if i == 0 else p[-1] - p[-2]
        return d / np.linalg.norm(d)


@dataclass
class Frame:
    o: np.ndarray
    t: np.ndarray
    s: np.ndarray
    u: np.ndarray

    def corners(self, size):
        a, b, c = (0.5 * float(v) for v in size)
        return np.array([self.o + i * a * self.t + j * b * self.s + k * c * self.u
                         for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])


@dataclass
class Fitting:
    kind: str                   # FITTING_KINDS
    frame: Frame                # its centre and axes
    size: Tuple[float, float, float]   # full extents along (t, s, u)
    params: dict = field(default_factory=dict)


@dataclass
class Support:
    kind: str                   # SUPPORT_KINDS
    position: np.ndarray        # its centre
    axis: np.ndarray            # trapeze / floor strut: the strut's axis; rods / ladder: up
    extent: Tuple[float, float]  # along axis, relative to position
    rods: List[Tuple[np.ndarray, np.ndarray]] = field(default_factory=list)   # rod centrelines (bottom, top)
    params: dict = field(default_factory=dict)

    def solids(self):
        """Every hardware solid of this support (rods aside) as a box: [(part, Frame, size (t, s, u), material)]."""
        out, a = [], self.axis
        if self.kind in ("trapeze", "floor_strut"):
            w, h = self.params["strut"]
            up = vec(self.params.get("up", Z))      # the strut's depth axis: +z, or a vertical floor's normal
            along = np.cross(a, up)
            mid = self.position + 0.5 * (self.extent[0] + self.extent[1]) * a
            out.append(("strut", Frame(mid, a, along, up), (self.extent[1] - self.extent[0], w, h),
                        "PaintedMetalDarker"))
            for e in self.extent:
                c = self.position + (e - math.copysign(STRUT_CAP / 2, e)) * a
                out.append(("end_cap", Frame(c, a, along, up), (STRUT_CAP, w, h), "PaintedMetalYellow"))
        if self.kind == "rods":
            return out + self._rod_hanger_solids()
        for lo, hi in self.rods:
            d = (hi - lo) / np.linalg.norm(hi - lo)
            t = vec(self.params["across"])
            s = np.cross(d, t)
            pl = self.params["plate"]
            out.append(("rod_plate", Frame(hi - d * ROD_PLATE_T / 2, t, s, d), (pl, pl, ROD_PLATE_T), "MetalDull"))
        if self.kind == "ladder":
            rails, rungs = self.ladder()
            c, w = vec(self.params["across"]), vec(self.params["toward"])
            (rw, rd), (ll, lt, lh) = self.params["rail"], self.params["rung"]
            for lo, hi in rails:
                out.append(("rail", Frame((lo + hi) / 2, a, c, w), (np.linalg.norm(hi - lo), rw, rd), "BrushedMetal"))
            for r in rungs:
                out.append(("rung", Frame(r, c, w, a), (ll, lt, lh), "BrushedMetal"))
            for part, end, mat in (("foot_plate", 0, "PaintedMetalDarker"), ("top_plate", 1, "BrushedMetal")):
                fr, size = self.ladder_plate(part)
                out.append((part, fr, size, mat))
        return out

    def ladder_plate(self, part):
        """A Chute ladder's foot plate (seated over the half rack's roof brush, the rails standing on it) or its top
        clamp plate (across the rail heads, under the Drop): (Frame (t = the ladder's axis), size (t, across,
        toward)). params[part] = (across lo, across hi, toward lo, toward hi, thickness) about the bundle's axis."""
        a, c, w = self.axis, vec(self.params["across"]), vec(self.params["toward"])
        x0, x1, y0, y1, th = self.params[part]
        lo, hi = (self.position + e * a for e in self.full_extent())
        end = lo + a * (th / 2) if part == "foot_plate" else hi - a * (th / 2)
        o = end + w * self.params["bundle_at"] + c * ((x0 + x1) / 2) + w * ((y0 + y1) / 2)
        return Frame(o, a, c, w), (th, x1 - x0, y1 - y0)

    def full_extent(self):
        """A ladder's whole height, plates included (its rails stand between the foot and top plates)."""
        return self.params.get("full", self.extent)

    def _rod_hanger_solids(self):
        """A rod hanger's hardware as boxes: per rod a square washer (the tray's rod-plate footprint) and the hex
        coupler nut on it at the bottom, a Darker ceiling anchor plate at the top; the Darker ceiling strut channel
        across both rods under the anchor plates, with its Yellow end caps."""
        out = []
        t = vec(self.params["across"])
        aw, al, at = self.params["anchor"]
        cw, ch = self.params["channel"]
        for lo, hi in self.rods:
            d = (hi - lo) / np.linalg.norm(hi - lo)
            s = np.cross(d, t)
            pl = self.params["plate"]
            out.append(("washer", Frame(lo + d * WASHER_T / 2, t, s, d), (pl, pl, WASHER_T), "BrushedMetal"))
            out.append(("coupler", Frame(lo + d * (WASHER_T + COUPLER_L / 2), t, s, d),
                        (2 * COUPLER_R, 2 * COUPLER_R, COUPLER_L), "BrushedMetal"))
            out.append(("anchor_plate", Frame(hi - d * at / 2, t, s, d), (aw, al, at), "PaintedMetalDarker"))
        (lo0, hi0), (lo1, hi1) = self.rods
        d = (hi0 - lo0) / np.linalg.norm(hi0 - lo0)
        along = (hi1 - hi0) / np.linalg.norm(hi1 - hi0)
        mid = (hi0 + hi1) / 2 - d * (at + ch / 2)
        y0, y1 = self.params["channel_span"]
        c0 = mid + along * ((y0 + y1) / 2)
        out.append(("channel", Frame(c0, along, t, d), (y1 - y0 - 2 * STRUT_CAP, cw, ch), "PaintedMetalDarker"))
        for e, sg in ((y0, 1), (y1, -1)):
            out.append(("end_cap", Frame(mid + along * (e + sg * STRUT_CAP / 2), along, t, d), (STRUT_CAP, cw, ch),
                        "PaintedMetalYellow"))
        return out

    def ladder(self):
        """A ladder's rails [(bottom, top)] (centrelines) and rung centres, from its frame-relative params."""
        a, c, w = self.axis, vec(self.params["across"]), vec(self.params["toward"])
        lo, hi = (self.position + e * a for e in self.extent)
        back = (self.params["rail"][1] / 2 - self.params["rung"][1] / 2) * w     # rails flush with the rungs' back
        rails = [(lo + k * self.params["rail_dx"] * c + back, hi + k * self.params["rail_dx"] * c + back)
                 for k in (-1, 1)]
        return rails, [self.position + z * a for z in self.params["rungs"]]


@dataclass
class Path:
    """A basket centreline on the floor top, with its floor normals and wall flags (-s wall, +s wall)."""
    points: np.ndarray
    normals: np.ndarray
    walls: Tuple[bool, bool] = (True, True)
    wall_h: float = TL.WALL_H
    openings: Tuple = ()        # junction cuts: (wall index (0 = -s, 1 = +s), (l0, l1) arc length along the path,
    #                             fillet radius); the fillets themselves are "wall" paths
    kind: str = "basket"        # "basket" (floor + walls); "wall" (one wall wire run: a fillet; points on the floor
    #                             top along the wall's foot, normals up the wall)
    arc: Tuple = ()             # a bend's (l0, l1, angle): where its circular arc starts and ends (arc length along
    #                             the path) and the angle it turns; the kit facets it on radials (tray_xsec.bend_facets)

    def lengths(self):
        return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(self.points, axis=0), axis=1))]

    def wall_mask(self, k):
        """Per point, whether wall k (0 = -s, 1 = +s) stands there (on, and not cut by an opening)."""
        on = np.full(len(self.points), bool(self.walls[k]))
        l = self.lengths()
        for w, (l0, l1), _ in self.openings:
            if w == k:
                on &= ~((l > l0 + 1e-9) & (l < l1 - 1e-9))
        return on


@dataclass
class Entry:
    """An ENTRY rectangle: centre o on the plane, outward normal n, half sizes ha / hb along the in-plane axes a / b."""
    name: str
    o: np.ndarray
    n: np.ndarray
    a: np.ndarray
    b: np.ndarray
    ha: float
    hb: float

    def margin(self, p):
        """How far p lies inside the rectangle's edges (negative = outside) and off its plane."""
        d = vec(p) - self.o
        return min(self.ha - abs(d @ self.a), self.hb - abs(d @ self.b)), abs(d @ self.n)


@dataclass
class Transform:
    R: np.ndarray
    d: np.ndarray

    def __call__(self, p):
        return vec(p) @ self.R.T + self.d

    def dir(self, v):
        return vec(v) @ self.R.T

    def __matmul__(self, other):
        return Transform(self.R @ other.R, self.R @ other.d + self.d)

    @staticmethod
    def identity():
        return Transform(np.eye(3), np.zeros(3))

    @staticmethod
    def rotation_z(deg, about=(0.0, 0.0, 0.0)):
        c, s = round(math.cos(math.radians(deg)), 12), round(math.sin(math.radians(deg)), 12)
        R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        a = vec(about)
        return Transform(R, a - R @ a)


@dataclass
class PiecePlan:
    shape: str
    density: Optional[str]
    style: str
    cells: Tuple[int, int, int]           # catalogue cells: (along X, up Z, across Y)
    ports: Dict[str, Port]
    bundles: List[Bundle]
    structure: List[Path]
    supports: List[Support]
    fittings: List[Fitting]
    entries: List[Entry]

    @property
    def size(self):
        """The cell box (x, y, z) in metres."""
        return CELL * np.array([self.cells[0], self.cells[2], self.cells[1]], dtype=float)

    def to_block(self, p):
        """Box-corner frame -> the centred model frame."""
        return vec(p) - self.size / 2

    def bundle(self, lane):
        return next(b for b in self.bundles if b.lane == lane)

    def transformed(self, T):
        """The plan moved rigidly by T (cells unchanged: the box itself is not re-derived)."""
        fr = lambda f: Frame(T(f.o), T.dir(f.t), T.dir(f.s), T.dir(f.u))
        return replace(
            self,
            ports={k: Port(p.name, tuple(T(p.o)), tuple(T.dir(p.t)), tuple(T.dir(p.u)), p.density)
                   for k, p in self.ports.items()},
            bundles=[replace(b, points=T(b.points)) for b in self.bundles],
            structure=[replace(s, points=T(s.points), normals=T.dir(s.normals)) for s in self.structure],
            supports=[replace(s, position=T(s.position), axis=T.dir(s.axis), rods=[(T(a), T(b)) for a, b in s.rods],
                              params=_move_params(T, s.params)) for s in self.supports],
            fittings=[replace(f, frame=fr(f.frame), params=_move_params(T, f.params)) for f in self.fittings],
            entries=[replace(e, o=T(e.o), n=T.dir(e.n), a=T.dir(e.a), b=T.dir(e.b)) for e in self.entries])


# ---------------------------------------------------------------------------------------------------- joining
def _basis(t, u):
    t, u = vec(t), vec(u)
    return np.column_stack([t, np.cross(u, t), u])


def place(plan, at_port_name, onto):
    """The rigid transform that joins `plan`'s port `at_port_name` to the port `onto` floor to floor: the origins
    coincide, the outward normals are opposite and the floor normals equal."""
    p = plan.ports[at_port_name]
    R = _basis(-vec(onto.t), onto.u) @ _basis(p.t, p.u).T
    return Transform(R, vec(onto.o) - R @ vec(p.o))


# ---------------------------------------------------------------------------------------------------- paths
class _Polyline:
    """Builds a centreline from lines and circular arcs, sampled <= TL.BUNDLE_STEP (arcs <= 10 mm chords)."""

    def __init__(self, p0):
        self.pts = [vec(p0)]
        self.heading = None

    @property
    def p(self):
        return self.pts[-1]

    def line(self, p1):
        p0, p1 = self.p, vec(p1)
        n = max(1, math.ceil(np.linalg.norm(p1 - p0) / TL.BUNDLE_STEP - 1e-9))
        self.pts += [p0 + (p1 - p0) * k / n for k in range(1, n + 1)]
        self.heading = (p1 - p0) / np.linalg.norm(p1 - p0)
        return self

    def go(self, d):
        return self.line(self.p + vec(d))

    def turn(self, toward, r, angle):
        """Arc from the current point and heading, turning towards the unit direction `toward` (perpendicular to the
        heading) about a centre r away, through `angle` radians."""
        b, toward = self.heading, vec(toward)
        c, a = self.p + r * toward, -toward
        n = max(2, math.ceil(r * angle / 0.01))
        self.pts += [c + r * (math.cos(th) * a + math.sin(th) * b) for th in (angle * k / n for k in range(1, n + 1))]
        self.heading = -math.sin(angle) * a + math.cos(angle) * b
        return self

    def array(self):
        return np.array(self.pts)


def _smooth(x, x0, x1):
    """0 before x0, 1 after x1, C1 smoothstep between."""
    if x1 <= x0:
        return float(x >= x1)
    t = min(1.0, max(0.0, (x - x0) / (x1 - x0)))
    return t * t * (3 - 2 * t)


def _xs(x0, x1, step=TL.BUNDLE_STEP):
    n = max(1, math.ceil(abs(x1 - x0) / step - 1e-9))
    return [x0 + (x1 - x0) * k / n for k in range(n + 1)]


# ---------------------------------------------------------------------------------------------------- pieces
def _linear_ports(L, z_cell, da, db):
    zf = z_cell + FLOOR_Z
    return {"a": Port("a", (0.0, Y_C, zf), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), da),
            "b": Port("b", (L, Y_C, zf), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), db)}


def _lane_bundle(lane, x0, x1, zf, ends, offset=None):
    """A bundle along x on `lane` (piece frame), optionally displaced by offset(x) -> (ds, dh)."""
    pts = []
    for x in _xs(x0, x1, TL.BUNDLE_STEP / 2 if offset else TL.BUNDLE_STEP):   # dressed bundles curve: finer
        ds, dh = offset(x) if offset else (0.0, 0.0)
        pts.append((x, Y_C + lane.s + ds, zf + lane.h + dh))
    return Bundle(np.array(pts), lane.material, R_B, ends, lane.name)


def _through(lane, L, zf, offset=None):
    return _lane_bundle(lane, 0.0, L, zf, (End("PORT", "a:" + mirror(lane.name)), End("PORT", "b:" + lane.name)),
                        offset)


def _basket(L, zf):
    pts = np.array([(x, Y_C, zf) for x in _xs(0.0, L)])
    return [Path(pts, np.tile(Z, (len(pts), 1)))]


def _trapeze(x, z_cell, z_top):
    """A strut under the floor at x, rods at the centreline +- ROD_S up to rod-coupler plates under the top plane."""
    zc = z_cell + STRUT_LIFT + STRUT_H / 2
    half = CELL * 2 / 2 - END_INSET
    rods = [(vec((x, Y_C + k * TL.ROD_S, z_cell + STRUT_LIFT)), vec((x, Y_C + k * TL.ROD_S, z_top - END_INSET)))
            for k in (-1, 1)]
    return Support("trapeze", vec((x, Y_C, zc)), Y.copy(), (-half, half), rods,
                   {"strut": (STRUT_W, STRUT_H), "rod_r": TL.ROD_R, "plate": ROD_PLATE, "across": X.copy()})


def _strap(b, x):
    """A strap round bundle b where it crosses the station plane at x (None if it does not)."""
    p = b.points
    for i in range(len(p) - 1):
        x0, x1 = p[i][0], p[i + 1][0]
        if min(x0, x1) - 1e-9 <= x <= max(x0, x1) + 1e-9 and abs(x1 - x0) > 1e-12:
            f = (x - x0) / (x1 - x0)
            o = p[i] + f * (p[i + 1] - p[i])
            t = (p[i + 1] - p[i]) / np.linalg.norm(p[i + 1] - p[i])
            s = np.cross(Z, t)
            s /= np.linalg.norm(s)
            d = 2 * (b.radius + TL.STRAP_T)
            return Fitting("strap", Frame(o, t, s, np.cross(t, s)), (TL.STRAP_W, d, d), {"bundle": b.lane})
    return None


def strap_stations(L):
    """Distances from port a of the straight-run strap stations (0.125 + k 0.25)."""
    return [TL.STRAP_PHASE + k * TL.STRAP_PITCH for k in range(int(math.floor((L - TL.STRAP_PHASE) / TL.STRAP_PITCH
                                                                               + 1e-9)) + 1)]


def _straps(bundles, L, until=None):
    out = []
    for x in strap_stations(L):
        for b in bundles:
            if until and x > until.get(b.lane, L):
                continue
            f = _strap(b, x)
            if f:
                f.params["station"] = x
                out.append(f)
    return out


def _plan(shape, density, cells, ports, bundles, structure, supports, fittings, entries=()):
    return PiecePlan(shape, density, "basket", tuple(cells), ports, bundles, structure, supports, fittings,
                     list(entries))


def _straight(shape, density):
    cells = catalog.TRAY_CELLS[shape]
    L = cells[0] * CELL
    ports = _linear_ports(L, 0.0, density, density)
    bundles = [_through(l, L, FLOOR_Z) for l in lanes(density)]
    supports = [_trapeze(L / 2, 0.0, cells[1] * CELL)]
    return _plan(shape, density, cells, ports, bundles, _basket(L, FLOOR_Z), supports, _straps(bundles, L))


def _clamp_half_width(s, through):
    """The saddle clamp's half width across at lane position s: the most that keeps CLAMP_CLEAR from every through
    bundle (the post stands from the floor, so it passes between the bottom layer) and from the wall wires."""
    w = min(CLAMP_MAX_HW, TL.WALL_S - TL.WIRE_R - CLAMP_CLEAR - abs(s))
    for t in through:
        w = min(w, abs(s - t.s) - R_B - CLAMP_CLEAR)
    return w


def _boot_height(lane, through, r_boot):
    """The centre height at which lane's boot (radius r_boot) clears every through bundle: bottom-layer lanes stay
    on the floor (lifted by the boot's own wall); a top-layer lane rides up onto its neighbours' shoulders."""
    h = max(lane.h, r_boot)
    for t in through:
        ds, need = abs(lane.s - t.s), r_boot + R_B + BOOT_CLEAR
        if ds < need:
            h = max(h, t.h + math.sqrt(need * need - ds * ds))
    return h


def _reducer(density):
    if density not in catalog.TRAY_DENSITIES[1:]:
        raise ValueError(f"no Reducer from {density}")
    lower = TL.step_down(density)
    cells = catalog.TRAY_CELLS["Reducer"]
    L = cells[0] * CELL
    ports = _linear_ports(L, 0.0, density, lower)
    through = lanes(lower)
    dropped = [l for l in lanes(density) if l not in through]
    bundles = [_through(l, L, FLOOR_Z) for l in through]
    fittings, r_boot = [], R_B + BOOT_T
    for l in dropped:
        hb = _boot_height(l, through, r_boot)
        ride = (lambda x, l=l, hb=hb: (0.0, (hb - l.h) * _smooth(x, BOOT_X - 0.10, BOOT_X - 0.03)))
        b = _lane_bundle(l, 0.0, BOOT_X, FLOOR_Z, (End("PORT", "a:" + mirror(l.name)), End("BOOT", "boot:" + l.name)),
                         ride)
        bundles.append(b)
        y, zc = Y_C + l.s, FLOOR_Z + hb
        fittings.append(Fitting("boot", Frame(vec((BOOT_X - BOOT_BACK + BOOT_L / 2, y, zc)), X.copy(), Y.copy(),
                                              Z.copy()), (BOOT_L, 2 * r_boot, 2 * r_boot),
                                {"bundle": l.name, "radius": r_boot, "material": "Rubber"}))
        # the clamp: a band round the boot's body on a post from the floor (the post passes between the bottom-layer
        # bundles under a top-layer boot; under a floor boot the band threads under a floor wire)
        w, rb = _clamp_half_width(l.s, through), r_boot + TL.STRAP_T
        z0, z1 = FLOOR_Z + min(0.0, hb - rb), FLOOR_Z + hb + rb
        fittings.append(Fitting("saddle_clamp", Frame(vec((CLAMP_X, y, (z0 + z1) / 2)), X.copy(), Y.copy(), Z.copy()),
                                (CLAMP_L, 2 * max(w, rb), z1 - z0),
                                {"bundle": l.name, "band_r": rb, "band_dz": FLOOR_Z + hb - (z0 + z1) / 2,
                                 "post_hw": w, "post_h": max(0.0, hb - r_boot), "material": "PaintedMetalDarker"}))
    for k in (-1, 1):     # the density tag, clipped to the outside of each wall
        s = k * TAG_S
        fittings.append(Fitting("tag", Frame(vec((TAG_X, Y_C + s, FLOOR_Z + TAG_H + TAG[2] / 2)), X.copy(),
                                             k * Y, Z.copy()), TAG,
                                {"text": TAG_TEXT[density], "material": "PaintedMetalYellow"}))
    until = {l.name: BOOT_X - BOOT_BACK - TL.STRAP_W for l in dropped}
    fittings += _straps(bundles, L, until)
    supports = [_trapeze(L / 2, 0.0, cells[1] * CELL)]
    return _plan("Reducer", density, cells, ports, bundles, _basket(L, FLOOR_Z), supports, fittings)


def _rect(name, x, y, z, up):
    """An ENTRY rectangle on the horizontal plane z over x / y ranges; `up` = whether its outward normal is +z."""
    return Entry(name, vec(((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, z)), (Z if up else -Z).copy(), X.copy(), Y.copy(),
                 (x[1] - x[0]) / 2, (y[1] - y[0]) / 2)


def _rack_rects(name, entry, x_mid, y_off, z, up):
    """The two ENTRY rectangles of a rack's front top entries (|x| range, y range in rack-local terms)."""
    (xa, xb), (ya, yb) = entry
    return [_rect(f"{name}{'-' if k < 0 else '+'}", sorted((x_mid + k * xa, x_mid + k * xb)), (ya + y_off, yb + y_off),
                  z, up) for k in (-1, 1)]


def waterfall_x(L=1.0):
    """The two waterfalls' x in a Drop or Chute (box-corner): the rack's manager channel centres."""
    return [L / 2 - DM.WF_X, L / 2 + DM.WF_X]


def _waterfall(xw, xs, zf, z_bottom, name, entry):
    """Peel off L1+ at xs, climb, bend outward, swing across to the crest, roll over the guide, fall to z_bottom."""
    parent = LANE["L1+"]
    e = np.sign(xw - xs) * X                          # outward along x
    p = _Polyline((xs, Y_C + parent.s, zf + parent.h))
    keys = []                                         # the point index where each stretch ends
    p.go((0, 0, WF_CREST - WF_RISE_R - parent.h))     # straight up out of the bundle, between F1+ and F3+
    keys.append(("climb", len(p.pts) - 1))
    p.heading = Z.copy()
    p.turn(e, WF_RISE_R, math.pi / 2)                 # over to outward, at crest height
    keys.append(("rise", len(p.pts) - 1))
    r_plan = WF_S_C - parent.s                        # the plan swing across the tray to the crest
    straight = WF_SPLIT_DX - WF_RISE_R - r_plan
    assert straight >= -1e-9, "the split is too close to the waterfall for the climb and the swing"
    if straight > 1e-9:
        p.go(e * straight)
    keys.append(("straight", len(p.pts) - 1))
    p.turn(Y, r_plan, math.pi / 2)                    # now heading +y at the crest, over the wall
    keys.append(("swing", len(p.pts) - 1))
    p.turn(-Z, WF_GUIDE_R, math.pi / 2)               # over the guide: heading straight down at the plumb line
    keys.append(("guide", len(p.pts) - 1))
    p.line((p.p[0], p.p[1], z_bottom))
    keys.append(("fall", len(p.pts) - 1))
    pts = p.array()
    along = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    return Bundle(pts, "PaintedMetalColorable", R_WF, (End("SPLIT", parent.name), End("ENTRY", entry)), name,
                  {"peel_r": WF_RISE_R, "along": along, "stretches": {k: float(along[i]) for k, i in keys}})


# a waterfall's coarse LODs: its centreline at the ends of its stretches and, per arc, this many chords (LOD1, LOD2)
WF_LOD_CHORDS = {"rise": (1, 1), "swing": (1, 1), "guide": (2, 2)}
WF_LOD_MIN = 0.01               # ... a stretch shorter than this (the 7.5 mm straight) folds into the next one


def waterfall_stations(b, lod):
    """The arc lengths a waterfall is built at for LOD1 and later (LOD0 follows its plan within the kit's tolerance):
    every stretch end (the climb, the rise bend, the straight, the plan swing, the guide arc, the fall), each arc in
    WF_LOD_CHORDS chords. The climb and the fall stay straight and plumb, so the split and the entry stay square."""
    st, prev = [0.0], 0.0
    for k, l in b.params["stretches"].items():
        if l - prev < WF_LOD_MIN and k != "fall":
            continue
        n = WF_LOD_CHORDS.get(k, (1, 1))[min(lod, 2) - 1]
        st += [prev + (l - prev) * i / n for i in range(1, n + 1)]
        prev = l
    out = []
    for v in st:
        if not out or v - out[-1] > 1e-6:
            out.append(v)
    return out


def _guide(xw, zf):
    """The waterfall's moulded radius guide (Darker): a trough under the bundle's arc, from 20 deg before the crest
    to plumb, its ribbed plate (the bundle rides the rib crests on the 0.10 m bend radius) between two side cheeks,
    clipped over the tray's front wall by two Brushed spring clamps round the safety-edge wire."""
    c = vec((xw, Y_C + WF_S_C, zf + WF_CREST - WF_GUIDE_R))
    r1 = WF_GUIDE_R - R_WF                            # the plate's top surface radius (the rib crests)
    r0 = r1 - WF_GUIDE_T
    ch = WF_GUIDE_CHEEK[1]
    psi = np.linspace(-WF_GUIDE_LEAD, math.pi / 2, 12)
    ys = np.concatenate([r0 * np.sin(psi), (r1 + ch) * np.sin(psi)])
    zs = np.concatenate([r0 * np.cos(psi), (r1 + ch) * np.cos(psi)])
    lo, hi = vec((xw - WF_GUIDE_W / 2, c[1] + ys.min(), c[2] + zs.min())), \
        vec((xw + WF_GUIDE_W / 2, c[1] + ys.max(), c[2] + zs.max()))
    # the clamps grip the safety-edge wire (its centre relative to the guide centre, in the frame's s / u)
    wire = (TL.WALL_S - WF_S_C, TL.WALL_H - (WF_CREST - WF_GUIDE_R), TL.EDGE_WIRE_R)
    return Fitting("waterfall_guide", Frame((lo + hi) / 2, X.copy(), Y.copy(), Z.copy()), tuple(hi - lo),
                   {"centre": c, "r_top": r1, "thickness": WF_GUIDE_T, "angles": (-WF_GUIDE_LEAD, math.pi / 2),
                    "width": WF_GUIDE_W, "cheek": WF_GUIDE_CHEEK, "rib": WF_GUIDE_RIB, "wire": wire,
                    "clamps": (-WF_CLAMP_DX, WF_CLAMP_DX), "clamp": WF_CLAMP, "material": "PaintedMetalDarker"})


def guide_clamp_path(f, n=8):
    """A guide clamp's strip centreline in the guide's frame, as (s, h) about the guide centre: a stem down from the
    plate's underside onto the safety-edge wire, then wrapped over the wire's top and round its outside to under it
    (a spring clip hooked on the wire). Every guide clamp shares it (they differ only along t)."""
    ws, wh, wr = f.params["wire"]
    rc = wr + f.params["clamp"][1] / 2                 # the strip's centreline radius round the wire
    r_in = f.params["r_top"] - f.params["thickness"]
    top = math.sqrt(r_in * r_in - ws * ws)             # the plate's underside over the wire
    pts = [(ws, top), (ws, wh + rc)]
    pts += [(ws + rc * math.cos(a), wh + rc * math.sin(a)) for a in np.linspace(math.pi / 2, -math.radians(115),
                                                                                    n + 1)[1:]]
    return pts


def _waterfall_strap(xw, y, z, lane):
    """A tie round the falling bundle (horizontal band, its station = the height over the bottom plane)."""
    d = 2 * (R_WF + TL.STRAP_T)
    return Fitting("strap", Frame(vec((xw, y, z)), -Z, X.copy(), -Y), (TL.STRAP_W, d, d),
                   {"bundle": lane, "station": z, "lod0_only": True})


def _entry_collar(xw, y, z0, lane, up=True):
    """The landing brush collar: a Darker ring seated on the plane at z0 (the rack's brush plate, or the Chute's top
    plate) round the bundle, its bore lined with a ring of bristle tufts that part round the bundle."""
    c = ENTRY_COLLAR
    r_out = R_WF + c["gap"] + c["wall"]
    zc = z0 + (1 if up else -1) * (ENTRY_SEAT + c["h"] / 2)
    return Fitting("brush_collar", Frame(vec((xw, y, zc)), Z.copy(), X.copy(), Y.copy()), (c["h"], 2 * r_out, 2 * r_out),
                   {"bundle": lane, "r_bore": R_WF + c["gap"], "r_bundle": R_WF, "material": "PaintedMetalDarker"})


def _collar(b, at):
    """A split collar round bundle b (along x) centred at x = at."""
    o = vec((at, b.points[0][1], b.points[0][2]))
    d = 2 * (b.radius + COLLAR_T)
    return Fitting("split_collar", Frame(o, X.copy(), Y.copy(), Z.copy()), (COLLAR_L, d, d),
                   {"bundle": b.lane, "material": "PaintedMetalDarker"})


def _drop(density):
    if density not in catalog.TRAY_DENSITIES[1:]:
        raise ValueError(f"no Drop at {density}: there is no lane to feed it (use a straight)")
    cells = catalog.TRAY_CELLS["Drop"]
    L, z_cell, z_top = cells[0] * CELL, (cells[1] - 1) * CELL, cells[1] * CELL
    zf = z_cell + FLOOR_Z
    ports = _linear_ports(L, z_cell, density, density)

    def dress(lane):
        if lane.name not in DRESS:
            return None
        s1, h1 = DRESS[lane.name]

        def off(x):
            w = min(_smooth(x, *DRESS_X), _smooth(L - x, *DRESS_X))
            return (s1 - lane.s) * w, (h1 - lane.h) * w
        return off

    bundles = [_through(l, L, zf, dress(l)) for l in lanes(density)]
    for b in bundles:
        if b.lane in DRESS:
            b.params["dress"] = True       # a LOD0 detail: from LOD1 on the kit lays the lane straight
    fittings = _straps(bundles, L)
    entries = _rack_rects("bottom", DM.TOP_ENTRY, L / 2, DROP_Y_OFF, 0.0, False)
    parent = next(b for b in bundles if b.lane == "L1+")
    for xw, ent in zip(waterfall_x(L), entries):
        xs = xw + np.sign(L / 2 - xw) * WF_SPLIT_DX
        lane = "WF" + ent.name[-1]
        bundles.append(_waterfall(xw, xs, zf, 0.0, lane, ent.name))
        collar = _collar(parent, xs)
        if any(b.params.get("dress") for b in bundles):     # at Full the dressed top layer closes
            collar.params["hidden"] = True                  # over the collar: the plan keeps it, the kit skips it
        fittings += [collar, _guide(xw, zf)]
        y = Y_C + WF_FALL_S
        fittings += [_waterfall_strap(xw, y, z, lane) for z in WF_STRAPS]
        fittings.append(_entry_collar(xw, y, 0.0, lane))
    supports = [_trapeze(L / 2, z_cell, z_top)]
    return _plan("Drop", density, cells, ports, bundles, _basket(L, zf), supports, fittings, entries)


CHUTE_RAIL = (0.012, 0.040)     # ladder rail section (a lipped C, open outward): x, y
CHUTE_RAIL_DX = 0.050           # rail centres either side of the bundle
CHUTE_RUNG = 0.020              # rung height; rungs behind the bundle (towards the tray), the cables strapped on
CHUTE_RUNG_T = 0.012
CHUTE_PLATE_T = 0.006           # the foot plate (Darker, seated over the half rack's roof brush) and the top clamp
#                                 plate (Brushed, across the rail heads, under the Drop's landing collar)
CHUTE_CLAMP_L = 0.012           # the Darker bundle clamp bolted under the top plate
CHUTE_FOOT_MARGIN = DM.ENTRY_FLANGE + 0.003   # the foot plate covers the brush plate's frame and 3 mm more
CHUTE_TOP_HOLE = R_WF + 0.0015  # the top plate's bore (the clamp under it grips the bundle)


def _chute():
    cells = catalog.TRAY_CELLS["Chute"]
    L, H = cells[0] * CELL, cells[1] * CELL
    y_off = DROP_Y_OFF - 2 * CELL                 # the Chute stands in the Drop's waterfall column (2 cells across)
    top = _rack_rects("top", DM.TOP_ENTRY, L / 2, y_off, H, True)
    bottom = _rack_rects("bottom", DM.HALF_TOP_ENTRY, L / 2, y_off, 0.0, False)
    y = Y_C + WF_FALL_S - 2 * CELL                # 0.0575
    bundles, supports, fittings = [], [], []
    rungs = [TL.STRAP_PHASE + k * TL.STRAP_PITCH for k in range(cells[1])]
    y_rung = y - R_WF - TL.STRAP_T - CHUTE_RUNG_T / 2
    t, rw = CHUTE_PLATE_T, CHUTE_RAIL[0]
    rail_back = y_rung - CHUTE_RUNG_T / 2 - y    # the rails' (and rungs') back face, from the bundle's axis
    (ex0, ex1), (ey0, ey1) = DM.HALF_TOP_ENTRY
    m = CHUTE_FOOT_MARGIN
    for xw, tp, bt in zip(waterfall_x(L), top, bottom):
        pts = np.array([(xw, y, z) for z in _xs(H, 0.0)])
        wf = Bundle(pts, "PaintedMetalColorable", R_WF, (End("ENTRY", tp.name), End("ENTRY", bt.name)),
                    "WF" + tp.name[-1])
        bundles.append(wf)
        sx = 1.0 if xw > L / 2 else -1.0              # the - side's brush plate is the + side's mirror image in x
        fx = sorted((sx * (ex0 - m - DM.WF_X), sx * (ex1 + m - DM.WF_X)))
        foot = (fx[0], fx[1], ey0 - m - DM.WF_Y, ey1 + m - DM.WF_Y, t)
        top_plate = (-CHUTE_RAIL_DX - rw / 2, CHUTE_RAIL_DX + rw / 2, rail_back,
                     R_WF + ENTRY_COLLAR["gap"] + ENTRY_COLLAR["wall"] + 0.002, t)   # (the Drop's collar sits on it)
        supports.append(Support("ladder", vec((xw, y_rung, H / 2)), Z.copy(),
                                (-H / 2 + ENTRY_SEAT + t, H / 2 - ENTRY_SEAT - t), [],
                                {"across": X.copy(), "toward": Y.copy(), "rail_dx": CHUTE_RAIL_DX,
                                 "rail": CHUTE_RAIL, "rungs": [z - H / 2 for z in rungs],
                                 "rung": (2 * CHUTE_RAIL_DX, CHUTE_RUNG_T, CHUTE_RUNG),
                                 "full": (-H / 2 + ENTRY_SEAT, H / 2 - ENTRY_SEAT), "bundle_at": y - y_rung,
                                 "foot_plate": foot, "top_plate": top_plate,
                                 "foot_hole": R_WF + ENTRY_COLLAR["gap"], "top_hole": CHUTE_TOP_HOLE,
                                 "material": "BrushedMetal"}))
        for z in rungs:       # a strap at every rung, round the bundle and the rung behind it (the cables tied on)
            d = 2 * (R_WF + TL.STRAP_T)
            fittings.append(Fitting("strap", Frame(vec((xw, y, z)), -Z, X.copy(), -Y), (TL.STRAP_W, d, d),
                                    {"bundle": wf.lane, "station": H - z,
                                     "tie_to": (y - y_rung, 0.007, CHUTE_RUNG_T)}))
        d = 2 * (R_WF + COLLAR_T)
        fittings.append(Fitting("bundle_clamp", Frame(vec((xw, y, H - ENTRY_SEAT - t - CHUTE_CLAMP_L / 2)), Z.copy(),
                                                      X.copy(), Y.copy()), (CHUTE_CLAMP_L, d, d),
                                {"bundle": wf.lane, "material": "PaintedMetalDarker"}))
    return _plan("Chute", None, cells, {}, bundles, [], supports, fittings, top + bottom)


def _rods(cells):
    """A rod hanger: two threaded rods continuing a trapeze's (x = the piece's centre, y_c +- ROD_S), each on a hex
    coupler nut in a square washer at the bottom (it takes the tray's, or a lower hanger's, rod plate) and up through
    a Darker ceiling strut channel to a Darker anchor plate under the top plane."""
    H = cells[1] * CELL
    x = cells[0] * CELL / 2
    rods = [(vec((x, Y_C + k * TL.ROD_S, END_INSET)), vec((x, Y_C + k * TL.ROD_S, H - END_INSET))) for k in (-1, 1)]
    return _plan("Rods", None, cells, {}, [], [], [Support("rods", vec((x, Y_C, H / 2)), Z.copy(),
                                                            (-H / 2, H / 2), rods,
                                                            {"rod_r": TL.ROD_R, "plate": ROD_PLATE,
                                                             "across": X.copy(), "anchor": ANCHOR,
                                                             "channel": CEIL_STRUT,
                                                             "channel_span": (-(CELL - END_INSET), CELL - END_INSET)})],
                 [])


def plan(spec_or_shape, density=None, style="basket"):
    """The cable plan of a catalogue block (a BlockSpec) or of a shape at a density."""
    if isinstance(spec_or_shape, catalog.BlockSpec):
        spec = spec_or_shape
        if spec.family not in ("tray", "trayrods"):
            raise ValueError(f"{spec.name} is not a tray block")
        shape, density = spec.variant, density or spec.density
        cells = spec.cells
    else:
        shape = spec_or_shape
        cells = catalog.TRAY_CELLS.get(shape, (2, 1, 2))
    if style not in STYLES:
        raise NotImplementedError(f"tray style {style!r}")
    if shape not in SHAPES:
        raise ValueError(f"unknown tray shape {shape!r}")
    if shape == "Rods":
        return _rods(cells)
    if shape == "Chute":
        return _chute()
    if density not in TL.DENSITIES:
        raise ValueError(f"{shape}: density {density!r} not in {TL.DENSITIES}")
    if shape in BENDS:
        from . import tray_bends
        return tray_bends.plan_bend(shape, density)
    if shape == "Reducer":
        return _reducer(density)
    if shape == "Drop":
        return _drop(density)
    return _straight(shape, density)


# ---------------------------------------------------------------------------------------------------- occupancy
def cross_section_extent(points):
    """Per point, the half extent along x / y / z of a unit disc perpendicular to the polyline there."""
    p = np.asarray(points)
    t = np.gradient(p, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    return np.sqrt(np.clip(1.0 - t * t, 0.0, 1.0))


def fitting_points(f, n=6):
    """Sample points of a fitting's solid: strap / collar / boot are cylinders along t; the guide is its arc plate;
    the rest are boxes."""
    fr, (a, b, c) = f.frame, f.size
    if f.kind in CYLINDER_FITTINGS:
        r = b / 2
        out = []
        for i in np.linspace(-a / 2, a / 2, 3):
            for k in range(16):
                th = 2 * math.pi * k / 16
                out.append(fr.o + i * fr.t + r * (math.cos(th) * fr.s + math.sin(th) * fr.u))
        return np.array(out)
    if f.kind == "saddle_clamp":   # the band round the boot, and the post under it
        c0 = fr.o + f.params["band_dz"] * fr.u
        out = [c0 + i * fr.t + f.params["band_r"] * (math.cos(th) * fr.s + math.sin(th) * fr.u)
               for i in np.linspace(-a / 2, a / 2, 3) for th in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        ph, w = f.params["post_h"], f.params["post_hw"]
        if ph > 0:
            base = c0 - (f.params["band_r"] - TL.STRAP_T + ph) * fr.u
            g = np.linspace(-0.5, 0.5, n)
            out += [base + i * a * fr.t + j * 2 * w * fr.s + (k + 0.5) * ph * fr.u for i in g for j in g for k in g]
        return np.array(out)
    if f.kind == "crossover_saddle":
        return np.vstack([box_points(q, size, 0.01) for _, q, size in saddle_parts(f)] + [saddle_shell_points(f)])
    if f.kind == "waterfall_guide":   # the ribbed plate, its two cheeks and its two clamps round the edge wire
        c0, (lo, hi) = vec(f.params["centre"]), f.params["angles"]
        W, (ct, ch) = f.params["width"], f.params["cheek"]
        r1 = f.params["r_top"]
        out = []
        for x in np.linspace(-W / 2, W / 2, 3):
            for psi in np.linspace(lo, hi, 24):
                for r in (r1 - f.params["thickness"], r1):
                    out.append(c0 + x * fr.t + r * (math.sin(psi) * fr.s + math.cos(psi) * fr.u))
        for x in (-W / 2, -W / 2 + ct, W / 2 - ct, W / 2):
            for psi in np.linspace(lo, hi, 24):
                for r in (r1, r1 + ch / 2, r1 + ch):
                    out.append(c0 + x * fr.t + r * (math.sin(psi) * fr.s + math.cos(psi) * fr.u))
        cw, cth = f.params["clamp"]
        for dx in f.params["clamps"]:
            for s_, h in guide_clamp_path(f):
                for x in (dx - cw / 2, dx + cw / 2):
                    for k in (-1, 1):
                        out.append(c0 + x * fr.t + (s_ + k * cth / 2) * fr.s + h * fr.u)
        return np.array(out)
    g = np.linspace(-0.5, 0.5, n)
    return np.array([fr.o + i * a * fr.t + j * b * fr.s + k * c * fr.u for i in g for j in g for k in g])


def _segment_samples(p0, p1, step=0.02):
    n = max(1, math.ceil(np.linalg.norm(vec(p1) - vec(p0)) / step))
    return [vec(p0) + (vec(p1) - vec(p0)) * k / n for k in range(n + 1)]


def box_points(frame, size, step=0.02):
    """Sample points of a box (faces and interior on a grid at most `step` apart, corners included)."""
    axes = [np.linspace(-v / 2, v / 2, max(2, math.ceil(v / step) + 1)) for v in size]
    return np.array([frame.o + i * frame.t + j * frame.s + k * frame.u for i in axes[0] for j in axes[1]
                     for k in axes[2]])


def support_points(sp):
    """Sample points of every solid of a support: its boxes (Support.solids) and its rods' surfaces."""
    pts = [box_points(fr, size) for _, fr, size, _ in sp.solids()]
    for a, b in sp.rods:
        d = (b - a) / np.linalg.norm(b - a)
        e1 = np.cross(d, vec(sp.params["across"]))
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(d, e1)
        r = sp.params["rod_r"]
        ring = [r * (math.cos(t) * e1 + math.sin(t) * e2) for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
        pts.append(np.array([q + o for q in _segment_samples(a, b) for o in ring]))
    return np.vstack(pts) if pts else np.zeros((0, 3))


def structure_points(path):
    """Envelope sample points of a basket path (its floor edges and wall tops, a wall standing only where
    Path.wall_mask says) or of a "wall" path (one wire run, floor to top wire)."""
    p, n = path.points, path.normals
    lo, hi = BASKET_BOTTOM - FLOOR_Z, path.wall_h + TL.EDGE_WIRE_R
    if path.kind == "wall":
        return [p + h * n for h in (lo, hi)]
    t = np.gradient(p, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    s = np.cross(n, t)
    out = []
    for i, k in ((0, -1), (1, 1)):
        on = path.wall_mask(i)
        out.append(p + k * TL.WALL_S * s + lo * n)                  # the floor's edge wire
        if on.any():
            q = p[on] + k * (TL.WALL_S + TL.WIRE_R) * s[on]
            out += [q + lo * n[on], q + hi * n[on]]
    return out


def saddle_parts(f):
    """A crossover saddle's solids as boxes [(part, Frame, size)]: the deck plate (its top at the deck height) and
    the legs standing on the strut line under the floor, bolted through it."""
    fr = f.frame
    out = [("deck", Frame(fr.o + (f.params["deck_top"] - f.params["deck_t"] / 2) * fr.u, fr.t, fr.s, fr.u),
            (f.size[0], f.size[1], f.params["deck_t"]))]
    lw, z0 = f.params["leg_w"], f.params["leg_bottom"]
    h = f.params["deck_top"] - f.params["deck_t"] - z0
    for i, j in f.params["legs"]:
        c = fr.o + i * fr.t + j * fr.s + (z0 + h / 2) * fr.u
        out.append(("leg", Frame(c, fr.t, fr.s, fr.u), (lw, lw, h)))
    return out


def saddle_profiles(f):
    """The formed deck's sections in the saddle's frame, as top / bottom surface polylines:
    "roll": [(s, h)] down one rolled end (sign +1; the other mirrors in s), h above the floor top, on the stack's own
    convex radius from the deck edge; "lip": [(t, h)] up one side lip (sign +1), from the flat deck round its bend
    and up its inner face. Each as (top, bottom) = the surface the cables meet and the one a deck_t below / outside."""
    P = f.params
    H, top, dt = f.size[1] / 2, P["deck_top"], P["deck_t"]
    r, ang = P["roll_r"], P["roll_angle"]
    phis = np.linspace(0.0, ang, 6)
    roll = [[(H + q * math.sin(a), top - r + q * math.cos(a)) for a in phis] for q in (r, r - dt)]
    lr, lh, W = P["lip_r"], P["lip_h"], f.size[0] / 2
    t0 = W - dt - lr                                        # the bend starts here (inner surface)
    ths = np.linspace(-math.pi / 2, 0.0, 5)
    inner = [(t0 + lr * math.cos(a), top + lr + lr * math.sin(a)) for a in ths] + [(t0 + lr, top + lh)]
    outer = [(t0 + (lr + dt) * math.cos(a), top + lr + (lr + dt) * math.sin(a)) for a in ths] + [(W, top + lh)]
    return {"roll": roll, "lip": [inner, outer]}


def saddle_tie_boxes(f):
    """The tie mounts on the deck top, one each side of the stack at every deck strap: [(Frame, size)]."""
    fr, P = f.frame, f.params
    sx, sy, sh = P["tie_size"]
    return [(Frame(fr.o + i * P["tie_t"] * fr.t + y * fr.s + (P["deck_top"] + sh / 2) * fr.u, fr.t, fr.s, fr.u),
             (sx, sy, sh)) for y in P["ties"] for i in (-1, 1)]


def saddle_feet(f):
    """Each leg's foot: a clamp plate on the floor wires and a backing plate under the basket (bolted through):
    [(Frame, size)]."""
    fr, P = f.frame, f.params
    a, t = P["foot"]
    out = []
    for i, j in P["legs"]:
        c = fr.o + i * fr.t + j * fr.s
        out.append((Frame(c + (t / 2) * fr.u, fr.t, fr.s, fr.u), (a, a, t)))
        out.append((Frame(c + (P["leg_bottom"] - t / 2) * fr.u, fr.t, fr.s, fr.u), (a, a, t)))
    return out


def saddle_shell_points(f):
    """Sample points of the formed deck's rolled ends and side lips, its tie mounts and its leg feet."""
    fr, P = f.frame, f.params
    prof = saddle_profiles(f)
    out = []
    for sg in (-1, 1):
        for surf in prof["roll"]:
            for s_, h in surf:
                for t_ in np.linspace(-P["roll_half"], P["roll_half"], 9):
                    out.append(fr.o + t_ * fr.t + sg * s_ * fr.s + h * fr.u)
        for surf in prof["lip"]:
            for t_, h in surf:
                for s_ in np.linspace(-f.size[1] / 2, f.size[1] / 2, 9):
                    out.append(fr.o + sg * t_ * fr.t + s_ * fr.s + h * fr.u)
    for q, size in saddle_tie_boxes(f) + saddle_feet(f):
        out += list(box_points(q, size, 0.01))
    return np.array(out)


def solid_points(plan):
    """Sample points of everything a plan puts in its box (bundle surfaces, basket envelope, fittings, supports)."""
    pts = []
    for b in plan.bundles:
        p, ext = b.points, cross_section_extent(b.points) * b.radius
        for sx in (-1, 0, 1):
            for sy in (-1, 0, 1):
                for sz in (-1, 0, 1):
                    pts.append(p + ext * np.array([sx, sy, sz]))
    for path in plan.structure:
        pts += structure_points(path)
    for f in plan.fittings:
        pts.append(fitting_points(f))
    for sp in plan.supports:
        pts.append(support_points(sp))
    return np.vstack([np.atleast_2d(np.asarray(q, dtype=float)) for q in pts])


JUNCTION_GRAZE = 0.006          # a fillet wall may graze a free corner cell this deep (its 45 deg point: 4 mm)


def fillet_centre(path):
    """A fillet "wall" path's arc centre: the circumcentre of its two ends and a middle point (it survives any rigid
    placement of the plan)."""
    p = np.asarray(path.points, float)
    A, B, M = p[0], p[-1], p[len(p) // 2]
    a, b = A - M, B - M
    w = np.cross(a, b)
    return M + np.cross((a @ a) * b - (b @ b) * a, w) / (2 * (w @ w))


def corner_cells(plan):
    """A junction's corner cells outside the tray: each holds a fillet's centre (the T's two beside the branch, the
    X's four corners). Only a fillet's sliver reaches into them (corner_graze), so they stay free."""
    n = np.round(plan.size / CELL).astype(int)
    return {tuple(int(v) for v in np.clip(np.floor(fillet_centre(path) / CELL), 0, n - 1))
            for path in plan.structure if path.kind == "wall"}


def corner_graze(plan, cell, pts=None):
    """How deep any solid point reaches into `cell`, measured from its faces inside the box (a face on the box's
    own boundary is not a neighbour's)."""
    pts = solid_points(plan) if pts is None else pts
    lo, hi = np.array(cell) * CELL, (np.array(cell) + 1) * CELL
    inside = np.all((pts > lo + 1e-9) & (pts < hi - 1e-9), axis=1)
    deep = 0.0
    for q in pts[inside]:
        d = [q[k] - lo[k] for k in range(3) if lo[k] > 1e-9] + \
            [hi[k] - q[k] for k in range(3) if hi[k] < plan.size[k] - 1e-9]
        deep = max(deep, min(d) if d else 9.0)
    return deep


def occupied_cells(plan):
    """The box-corner cell indices (ix, iy, iz), Blender axes, that any structure, bundle, fitting or support point
    falls in. A point on a cell plane belongs to the cell below it (geometry that only touches a plane does not
    occupy the far cell); the box faces clamp. A junction's corner cells (corner_cells) stay free while nothing but a
    fillet's sliver grazes them (<= JUNCTION_GRAZE)."""
    n = np.round(plan.size / CELL).astype(int)
    pts = solid_points(plan)
    idx = np.floor(pts / CELL - 1e-7).astype(int)
    idx = np.clip(idx, 0, n - 1)
    occ = {tuple(int(v) for v in r) for r in np.unique(idx, axis=0)}
    for cell in corner_cells(plan):
        if corner_graze(plan, cell, pts) <= JUNCTION_GRAZE:
            occ.discard(cell)
    return occ
