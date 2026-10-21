"""The cable continuity contract of the cable trays. Pure Python (numpy).

Every tray piece meets its neighbours at **ports**. A port is a frame on a face of the piece's cell box:

- ``o``: the tray centreline point on the port face, at floor-top height;
- ``t``: the outward port normal;
- ``u``: the floor normal (into the tray);
- ``s = u x t``: the across axis.

Two ports join when their ``o`` coincide, their ``t`` are opposite and their ``u`` are equal ("floor to floor"). The
across axes are then opposite too, which is why the lane table is mirror-symmetric in ``s``: a piece used backwards,
or as the other hand, still meets its neighbour lane for lane.

A **lane** is a bundle slot at ``(s, h)`` in a port frame (``h`` above the floor top). Densities nest: each density
adds lanes to the one below, so two densities joined without a reducer still line up on the lanes they share.

The geometry constants of the basket and its hardware live here too, because the contract tests check clearances
against them (the Blender kit, dc/tray_kit.py, builds to these numbers).
"""
from dataclasses import dataclass

import numpy as np

from . import dims as DM

CELL = DM.CELL
FLOOR_Z = DM.FLOOR_Z          # the floor top lies this far in front of the grid plane behind the floor

# ---------------------------------------------------------------------------------------------------- bundles
R_CABLE = 0.009               # one cable
R_B = 0.027                   # a bundle of 7 (one in the centre, six round it) = 3 R_CABLE
R_WF = DM.R_WF                # a waterfall bundle (7 cables of r 7.5 mm): 0.0225
BUNDLE_STEP = 0.02            # bundle polylines are sampled at most this far apart

# ---------------------------------------------------------------------------------------------------- the basket
WALL_S = 0.21                 # wall wire centres at s = +-WALL_S
WALL_H = 0.10                 # the top (safety-edge) wire centre above the floor top
JUNCTION_WALL_H = 0.15        # T / X walls round the junction
WIRE_R = 0.004                # basket wires (floor, U-wires, lower wall wire)
EDGE_WIRE_R = 0.005           # the top safety-edge wire
U_LEG_S = WALL_S + 2 * WIRE_R # the transverse U-wires' legs stand on the outside of the longitudinal wall wires
#                               (welded crossings, centres one wire diameter apart): 0.218, their outside 0.222

# ---------------------------------------------------------------------------------------------------- hardware
STRAP_PITCH = 0.25            # straps every grid cell ...
STRAP_PHASE = 0.125           # ... at cell centres, counted from each port: the rhythm continues across joints
STRAP_W = 0.018               # strap band width (along the bundle)
STRAP_T = 0.0025              # strap band thickness over the bundle
ROD_S = DM.ROD_S              # trapeze rods at the tray centreline +- ROD_S: 0.232
ROD_R = 0.005                 # threaded rod radius
ROD_CLEAR = 0.005             # rods clear the wall wires by at least this much

END_KINDS = ("PORT", "SPLIT", "BOOT", "ENTRY")
DENSITIES = ("Empty", "Low", "Moderate", "Full")

# the joint and end tolerances (the contract's numbers; the tests read them from here)
POS_TOL = 0.0005              # a PORT end lies within 0.5 mm of its lane point
ANG_TOL_DEG = 0.5             # ... and leaves along t within 0.5 deg
PORT_STRAIGHT = 0.05          # ... straight for its last 5 cm
SPLIT_TOL = 0.001             # a SPLIT end lies within 1 mm of its parent's centreline
SPLIT_COLLAR_L = 0.030       # a split collar's length along its parent
TOUCH_TOL = 0.001             # bundles keep centreline distance >= r1 + r2 - 1 mm, except a child and its parent ...


def split_zone(peel_r):
    """... within this distance, measured along the parent, of their SPLIT point: the collar plus one
    bend radius of the child's peel. A child that leaves its parent on an arc of radius `peel_r` (in plan, or rising)
    is still partly inside the parent's envelope until about that far along, as real cables are where they fan out of
    a collar."""
    return SPLIT_COLLAR_L + peel_r


# ---------------------------------------------------------------------------------------------------- junctions
DECK_H = 0.095                # crossover saddle: deck top above the floor top (bundles ride it at DECK_H + R_B)
JUNCTION_REACH = 0.20         # walls within this far (along the path) of a junction opening rise to JUNCTION_WALL_H
FILLET_R = 0.15               # a junction opening's wall fillet radius
CELL_TOP_CLEAR = 0.0025       # every junction bundle's surface stays this far under the cell's top plane


@dataclass(frozen=True)
class Lane:
    name: str
    s: float                  # across, in the port frame
    h: float                  # centre height above the floor top
    material: str             # vanilla material of the bundle's cables
    first: str                # the lowest density that carries it


_LOW_H = R_B                  # the bottom layer rests on the floor
_PITCH = 0.085                # bottom-layer lane pitch (3.15 R_B: a finger's gap for the straps)
# the top layer nests in the bottom layer's grooves: its centre is 2 R_B (minus 0.2 mm of cable give) from the two
# bundles below, which puts it at R_B + sqrt((2 R_B)^2 - (pitch / 2)^2) = 0.060 (the plan's value)
_HIGH_H = 0.060

LANES = (
    Lane("L1+", +_PITCH, _LOW_H, "PaintedMetalColorable", "Low"),          # data
    Lane("L1-", -_PITCH, _LOW_H, "PaintedMetalColorable", "Low"),
    Lane("M0", 0.0, _LOW_H, "PaintedMetalYellow", "Moderate"),             # fibre
    Lane("M2+", +2 * _PITCH, _LOW_H, "PaintedMetalGrey", "Moderate"),      # power
    Lane("M2-", -2 * _PITCH, _LOW_H, "PaintedMetalGrey", "Moderate"),
    Lane("F1+", +_PITCH / 2, _HIGH_H, "PaintedMetalColorable", "Full"),    # data, top layer
    Lane("F1-", -_PITCH / 2, _HIGH_H, "PaintedMetalColorable", "Full"),
    Lane("F3+", +3 * _PITCH / 2, _HIGH_H, "Rubber", "Full"),               # black power, top layer
    Lane("F3-", -3 * _PITCH / 2, _HIGH_H, "Rubber", "Full"),
)
LANE = {l.name: l for l in LANES}


def level(density):
    """0 (Empty) .. 3 (Full)."""
    return DENSITIES.index(density)


def lanes(density):
    """The lanes a density carries, in table order. Empty -> []."""
    n = level(density)
    return [l for l in LANES if level(l.first) <= n]


def lane_key(s, h, material):
    """The comparison key of a lane slot: (s, h) rounded to 0.1 mm, plus the material."""
    return (round(s + 0.0, 4) + 0.0, round(h, 4) + 0.0, material)


def lane_set(density):
    return {lane_key(l.s, l.h, l.material) for l in lanes(density)}


def mirror(name):
    """'L1+' <-> 'L1-'; centre lanes map to themselves."""
    return name[:-1] + {"+": "-", "-": "+"}[name[-1]] if name[-1] in "+-" else name


def step_down(density):
    """The density a reducer steps down to (Full -> Moderate -> Low -> Empty)."""
    return DENSITIES[level(density) - 1]


# ---------------------------------------------------------------------------------------------------- ports
def vec(v):
    return np.asarray(v, dtype=float)


@dataclass(frozen=True)
class Port:
    name: str
    o: tuple
    t: tuple
    u: tuple
    density: str

    @property
    def s(self):
        return np.cross(vec(self.u), vec(self.t))

    def frame(self):
        """(o, t, s, u) as numpy vectors."""
        return vec(self.o), vec(self.t), self.s, vec(self.u)

    def local(self, p):
        """A point in this port's frame: (along t, s, h)."""
        o, t, s, u = self.frame()
        d = vec(p) - o
        return float(d @ t), float(d @ s), float(d @ u)


def lane_point(port, lane):
    """The centre of `lane` on `port`'s face."""
    o, _, s, u = port.frame()
    return o + lane.s * s + lane.h * u
