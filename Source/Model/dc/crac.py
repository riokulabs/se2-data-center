"""In-row cooling unit DC_CRAC: 4 x 10 x 5 cells, the full rack's footprint (1.0 x 2.5 x 1.25 m), so a
row keeps its 1.0 m pitch and the containment roof clamps onto it like onto a rack.

Frame as dc/rack.py (Blender, metres, centred: X width, +Y = front = game Forward = the cold aisle, Z up), built in
local z (0 = floor) and shifted by -H/2. The vertical layout is the full rack's (dims.rack_frame(10)): the plinth
0 .. 0.25, the "slot band" 0.25 .. ZT (here the cooling section), the top band ZT .. H. The plinth, the corner posts
and caps, the containment rail and the top-entry brush plates are the rack's own builders, so every interface a rack
offers the room (floor, roof rail, Drop, neighbours) the CRAC offers with the same numbers.

What it does in game: a stripped Gyroscope250 clone. It draws 25 power units (priority 6), has the
terminal On/Off, and while Working its three fan rotors spin (the CracFan rotor subpart, InfiniteRotation about the
block's forward axis, ramping up and coasting down) and its RUN lamp lights; the gyroscope's torque is gone.

Purpose of every part (a real in-row chilled-water cooler, SE-styled; the user's functional-design rule):
| part                                         | purpose                                                         |
| plinth: base frame, levelling feet           | stands the unit on the raised floor (same as a rack: same plane)|
| plinth front: nameplate                      | model / duty / medium of the unit                               |
| plinth rear: condensate pan lip, float switch| the coil's drip pan; the float switch stops the unit if it fills|
|   CONDENSATE PAN label on a Darker plate     |   (every white stencil on a Darker plate: it reads on any paint)|
| corner posts + armoured caps                 | the cabinet frame; impact armour where units get knocked        |
| front service door (hinges, recessed latch)  | access to the fan bank; latched so it cannot swing into the aisle|
| three fan modules F1-F3 (housing, venturi,   | the supply fans: hot-swappable EC fan modules blowing the       |
|   finger guard, motor, stencil)              | chilled air into the cold aisle; the guard keeps fingers out    |
| side supply grilles (perforated)             | the door's discharge strips beside the fan bank: air across the |
|                                              | full rack width, not just three jets                            |
| CAUTION ROTATING FANS label                  | the hazard where it is: on the fan door                         |
| controller panel: display, RUN / ALARM lamps,| setpoint and status: supply / return temperature, fan count;    |
|   MODE / SET keys, perforated vent           | RUN lit while Working; the vent cools the controller / drives   |
| rear filter door (upper half): two louvred   | the hot aisle's air enters here; the louvres hide the filters   |
|   return grilles with pleated filters, FILTER|   the filters are changed through it (quarter-turn latches)    |
|   tabs, latches                              |                                                                 |
| rear service bay (lower half, bolted panel): | two blanked O2 / coolant service ports (Keen's small conveyor   |
|   two small conveyor ports (vanilla kit),    |   port frame, 0.4 m; our bolted blind plate in place of its     |
|   blind plates, O2 / COOLANT SERVICE label   |   hatch) for the station's life-support loop: capped today,     |
|                                              |   where a conveyor / vent would connect once SE2 has airtightness|
|                                              |   (dummies conveyor_port_o2_1 / _2; dc/crac_ports.py)           |
| rear header: RETURN AIR, filter DP gauge     | the filter's differential pressure: change them when it rises  |
| top: CHW S / CHW R stubs with insulation,    | chilled-water supply and return from the facility: insulated    |
|   ball valves, blind flanges (1 mm under the |   against condensation, isolation valves for service, blind      |
|   top plane), COND stub                      |   flanges where the facility pipework connects; condensate out  |
| top: two brush plates (the rack's)           | power and controls in from an overhead tray Drop                |
| containment rail (the rack's)                | the containment roof's edge bears and clamps here               |
| side panels: hand pockets, rating plate      | removable service panels; the electrical rating                 |
"""
import math

from se2model.config import DECAL_OFFSET

from . import dims as DM
from . import rack as R

try:   # geometry needs Blender; dims / collision / fan_points are plain Python (pytest imports them outside)
    from mathutils import Matrix
    from se2model import geom as G
    from se2model.geom import Face, Part
except ImportError:
    Matrix = G = Face = Part = None
from .style import DARK, HARDWARE, PAINT, STEEL, YELLOW, bolt, lamp, oct_pts, perf_quad, stencil

W2, D2, YK, XO, SKIN, CAP, POST = R.W2, R.D2, R.YK, R.XO, R.SKIN, R.CAP, R.POST
H, ZT, _TRAY, _NSLOTS = DM.rack_frame(10)        # 2.5, 2.25: the full rack's vertical layout
LAMP = "EmissiveOff"     # the RUN lamp's slot: the cloned BlockMaterialSwapper lights it EmissiveGreen while Working
FAN = "CracFan"          # the rotor subpart (and its dummy type / dummies CracFan1..3)
FAN_DEG_S = 600.0        # InfiniteRotation AngularSpeed (deg/s): 100 rpm, a big EC fan's idle-to-run feel in game
FAN_SPEEDUP = 300.0      # deg/s^2: 2 s soft start (linear ramp, InfiniteRotationAnimationComponent)
FAN_SLOWDOWN = 150.0     # deg/s^2: a 4 s coast-down when switched off or unpowered
FAN_AXIS = (0, 0, 1)     # game +Z = Blender -Y: the blades' leading edges sit upstream (-y), the air goes to +y
PCU = 30                 # the clone source's (Gyroscope250's template)
MOUNTS = "All"           # the model's mount hints decide (as the racks)

# ---------------------------------------------------------------------------------------------------- layout (local z)
DOOR_A = 0.42                          # |x| of the front / rear doors (4.5 mm inside the posts' inner faces)
DOOR_Z = (0.262, 1.840)                # the front fan door
CTRL_Z = (1.856, ZT - 0.012)           # the controller panel over it (a 16 mm shadow gap)
DOOR_Y = (0.556, 0.578)                # front door / controller plate (outer face 20 mm behind the keep-out plane)
FAN_ZC = (0.531, 1.051, 1.571)         # the three fan modules' centres (pitch 0.52, a 30 mm door rail between)
MOD_HALF = 0.243                       # fan module housing half size (square, chamfered)
MOD_Y = (0.470, 0.570)                 # module housing (its orifice wall is the fan's shroud)
ORIFICE_R = 0.207
VENTURI = (0.226, 0.570, 0.576)        # the MetalDull venturi lip: outer radius, y0, y1
GUARD_Y = (0.580, 0.585)               # finger-guard wire layer
GUARD_R = (0.214, 0.172, 0.130, 0.088)
MOTOR = (0.058, 0.536, 0.587)          # the static motor stator / guard centre: radius, y0, y1
ROTOR_Y = 0.512                        # the rotor pivot (blades 0.49 .. 0.54, behind the motor)
ROTOR_R = (0.072, 0.196)               # hub bell, blade tip
WIN_X = (0.27, 0.36)                   # |x| of the perforated side grilles
LABEL_Z = (1.07, 1.27)                 # the caution label on the latch-side grille strip (the middle module's band)
LATCH_X, LATCH_Z = (0.372, 0.408), (0.995, 1.125)
HINGE_Z = (0.45, 1.05, 1.65)                          # the front fan door's hinges
CORE_Y = (-0.530, 0.440)               # the Darker body shell (coil, plenum walls), seen through every opening
REAR_Y = (-0.578, -0.556)              # the rear filter door
FILTER_Y = (-0.552, -0.534)
REAR_Z = tuple((DOOR_Z[0] + 0.494 * k + 0.008, DOOR_Z[0] + 0.494 * (k + 1) - 0.008) for k in range(4))
# The filter door is the upper half (grilles 3-4 of the old four), the lower half a bolted service bay with
# the two O2 / coolant service ports. The joint is the old grille rail z 1.25 (SEAM_Z[3]).
GRILLES = REAR_Z[2:]                    # the filter door's two return grilles (FILTER 1 lower, FILTER 2 upper)
FILTER_DOOR_Z = (REAR_Z[2][0] - 0.004, ZT - 0.012)       # 1.254 .. 2.238 (a 12 mm gap over the bay)
BAY_Z = (DOOR_Z[0], REAR_Z[1][1])                       # 0.262 .. 1.242: the service bay panel
REAR_HINGE_Z = (1.42, 2.06)                             # the filter door's two hinges
# the ports: (dummy name, x, local z of the centre): centred on 2 x 2 cell patches of the rear cell face (x = 0 and
# z = 0.5 / 1.0 are cell lines, like a vanilla small conveyor port), the frame's face at the keep-out plane -YK
PORTS = (("conveyor_port_o2_1", 0.0, 0.50), ("conveyor_port_o2_2", 0.0, 1.00))
PORT_FACE_Y = -(YK - 0.0005)                            # the kit frame's outer face (0.5 mm inside the keep-out)
PORT_LABEL = "O2 / COOLANT SERVICE"
UNIT_CAPTION = "CRAC"   # the front header caption: neutral, no unit number (the ID tag beside it is blank)
PORT_DUMMY_SCALE = (0.5, 0.5, 0.05)                     # vanilla's small-port dummy scale (O2H2Generator250)
WELL = (-0.30, 0.30, -0.44, -0.06)     # the top's water service well (x0, x1, y0, y1)
WELL_FLOOR = ZT + 0.06
CHW = ((-0.15, -0.25, "CHW S"), (0.15, -0.25, "CHW R"))
COND = (0.0, -0.12)
FLANGE = (0.062, H - 0.022, H - 0.006)          # blind flange: radius, z0, z1; bolt heads to H - 0.001
# fracture seams (local z): between the fan modules (on the door rails), under the controller, the rear grille's
# middle rail; across y: the coil core's faces (dc/fracture.py _crac)
SEAM_Z = ((FAN_ZC[0] + FAN_ZC[1]) / 2, (FAN_ZC[1] + FAN_ZC[2]) / 2, (DOOR_Z[1] + CTRL_Z[0]) / 2, 1.25)
SEAM_Y = (0.10, -0.35)                          # core front (the fan plenums start), core back (the filter section)
TERMINAL = (0.205, 0.580, 2.045)                # the terminal dummy: the display's centre, on its glass (local z)
TERMINAL_SCALE = (0.40, 0.31, 0.06)             # (x, z, y) extent of the aim box
TERMINAL_DUMMY = "TerminalFront01"              # the clone's terminal dummy (aim + use: the On/Off terminal)
TAG_LIFT = R.CONTAIN_TAG_LIFT   # the CONTAINMENT rail tag 0.6 mm clear of its plate (z-fight)
LEGEND = (0.02, 1.888, 0.235, 2.185)   # the controller's Darker lamp / key legend plate (a0, b0, a1, b1)
LEGEND_T = 0.002                       # its (and the title strip's) thickness
LOD_COUNT = {}


def dims(spec):
    nx, ny, nz = spec.cells
    assert (nx, ny, nz) == (4, 10, 5), spec
    return {"H": H, "ZT": ZT, "tray": True, "nslots": _NSLOTS, "doors": (), "spec": spec, "lamp": LAMP}


def fan_points(spec):
    """The three rotor pivots (Blender block frame, centred): F1 bottom .. F3 top."""
    dims(spec)
    return [(0.0, ROTOR_Y, zc - H / 2) for zc in FAN_ZC]


def size(spec):
    return tuple(0.25 * c for c in spec.cells)


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


# ---------------------------------------------------------------------------------------------------- faces
def F_front(y):
    return Face((0, y, 0), (-1, 0, 0), (0, 0, 1))      # normal +y; a = -x (the viewer's right), b = z


def F_back(y):
    return Face((0, y, 0), (1, 0, 0), (0, 0, 1))       # normal -y; a = +x


def F_side(sx, x=None):
    return Face((sx * (W2 - SKIN) if x is None else x, 0, 0), (0, sx, 0), (0, 0, 1))


def F_top(z):
    return Face((0, 0, z), (1, 0, 0), (0, 1, 0))


def _circle(r, n, a=0.0, b=0.0, rot=None):
    rot = math.pi / n if rot is None else rot
    return [(a + x, b + y) for x, y in G.ngon(r, n, rot)]


def _seg(lod, n0):
    return max(8, n0 >> lod)


# ---------------------------------------------------------------------------------------------------- plinth
def _plinth(P, lod):
    """The rack's plinth (feet, base frame, core, side skins with jacking pockets), its kick panels made the CRAC's:
    the nameplate at the front, the condensate pan lip and its float switch at the rear (the hot aisle)."""
    fr, dk, hw = P["frame"], P["dark"], P["hw"]
    if lod == 0:   # (LOD1 budget: the 6 mm feet are the LOD2 base box from LOD1 on)
        G.box(dk, (-W2 + SKIN + 0.02, -YK + 0.02, 0.004), (W2 - SKIN - 0.02, YK - 0.02, 0.014), DARK)
        for fx in (-1, 1):
            for fy in (-1, 1):
                c = (fx * (W2 - 0.075), fy * (YK - 0.075))
                G.cylinder(hw, (c[0], c[1], 0.0), (c[0], c[1], 0.006), 0.034, 12, STEEL)
                G.cylinder(hw, (c[0], c[1], 0.006), (c[0], c[1], 0.014), 0.016, 6, HARDWARE)
    else:
        G.box(dk, (-W2 + SKIN, -YK, 0.0), (W2 - SKIN, YK, 0.014), DARK)
    # core (the body sits on it), its top 2 mm under the plinth seam so it stays the plinth's (a face in the seam plane
    # went to the body zones: a dead fan section took the plinth's lid with it)
    G.box(dk, (-0.47, -0.57, 0.014), (0.47, 0.57, 0.248), DARK)
    a1 = W2 - CAP - 0.006
    # front kick panel + nameplate
    F = F_front(YK - 0.012)
    G.prism(fr, F, oct_pts(-a1, 0.03, a1, 0.22, 0.03), -0.014, 0.0, PAINT)
    if lod <= 1:
        G.prism(P["fine"], F, oct_pts(-0.22, 0.075, 0.22, 0.175, 0.012), 0.0, 0.003, DARK)
        stencil(P["decal"], F, 0.0, 0.145, 0.030, "IN-ROW COOLER", d=0.003)
        if lod == 0:
            stencil(P["decal"], F, 0.0, 0.100, 0.018, "CRAC  25 KW  CHW", d=0.003)
        if lod == 0:
            for a in (-a1 + 0.025, a1 - 0.025):
                bolt(hw, F, a, 0.125, 0.0)
    # rear kick panel: a slot showing the condensate pan's lip, the float switch housing under it
    F = F_back(-YK + 0.012)
    if lod >= 2:
        G.prism(fr, F, oct_pts(-a1, 0.03, a1, 0.22, 0.03), -0.014, 0.0, PAINT)
        G.prism(P["fine"], F, G.rect(-0.38, 0.38, 0.17, 0.215), 0.0, 0.002, DARK)
        return
    slot = G.rect(-0.38, 0.38, 0.168, 0.214)
    G.plate(fr, F, oct_pts(-a1, 0.03, a1, 0.22, 0.03), [slot], -0.014, 0.0, PAINT)
    ys = sorted((-(YK - 0.026), -(YK - 0.020)))
    G.box(P["fine"], (-0.385, ys[0], 0.164), (0.385, ys[1], 0.218), DARK)                 # the pan's lip (rolled edge)
    if lod == 0:   # its drain spigot down into the float switch housing
        G.cylinder(hw, (0.31, -(YK - 0.008), 0.17), (0.31, -(YK - 0.008), 0.133), 0.006, 8, STEEL)
    G.prism(P["fine"], F, oct_pts(0.255, 0.05, 0.365, 0.135, 0.01), 0.0, 0.008, DARK)     # float switch housing
    G.cylinder(hw, F(0.31, 0.098, 0.008), F(0.31, 0.098, 0.0105), 0.011, 12 if lod == 0 else 8, YELLOW)  # test cap
    if lod == 0:
        stencil(P["decal"], F, 0.31, 0.068, 0.011, "FLOAT", d=0.008)
    if lod == 0:   # (on its own Darker plate; LOD1 drops the 24 mm label, unreadable that far)
        G.prism(P["fine"], F, oct_pts(-0.285, 0.097, -0.015, 0.133, 0.008), 0.0, 0.0015, DARK)
        stencil(P["decal"], F, -0.15, 0.115, 0.024, "CONDENSATE PAN", d=0.0015)
    if lod == 0:
        for a in (-a1 + 0.025, a1 - 0.025):
            bolt(hw, F, a, 0.125, 0.0)
    # side skins with jacking pockets (the rack's)
    for sx in (-1, 1):
        F = F_side(sx)
        b0 = -(YK - CAP - 0.006)
        if lod == 1:
            G.prism(fr, F, oct_pts(b0, 0.025, -b0, 0.225, 0.03), -0.012, 0.0, PAINT)
            continue
        R._plate(fr, F, oct_pts(b0, 0.025, -b0, 0.225, 0.03), -0.012, 0.0, PAINT, [G.rect(-0.10, 0.10, 0.075, 0.165)])
        G.box(P["fine"], (sx * 0.468 - 0.004, -0.10, 0.075), (sx * 0.468 + 0.004, 0.10, 0.165), DARK)
        G.prism(fr, F, G.rect(-0.10, 0.10, 0.178, 0.186), 0.0, 0.0015, YELLOW)


# ---------------------------------------------------------------------------------------------------- body shell
def _body(P, lod):
    """The body shell between the posts: Darker plenum side walls (liners), the fan wall behind the fan modules and the
    roof under the top band, with the cores and the coil inside (_inside); and the side panels."""
    dk, fr, hw = P["fine"], P["frame"], P["hw"]   # (the shell walls unbevelled)
    if lod <= 1:
        for sx in (-1, 1):   # the plenum side walls, in the old solid shell's side planes (|x| 0.47)
            x0, x1 = sorted((sx * LINER_X[0], sx * LINER_X[1]))
            G.box(dk, (x0, CORE_Y[0], 0.25), (x1, CORE_Y[1], ZT), DARK)
        G.box(dk, (-LINER_X[0], CORE_Y[0], ZT - 0.006), (LINER_X[0], CORE_Y[1], ZT), DARK)   # the roof (drip-proof)
    _inside(P, lod)
    yb = YK - POST - 0.004                       # side field between the posts (|y|)
    for sx in (-1, 1):
        F = F_side(sx)
        for k, (z0, z1) in enumerate(((0.262, 1.242), (1.258, ZT - 0.012))):
            pts = oct_pts(-yb, z0, yb, z1, 0.03)
            G.prism(fr, F, pts, -0.012, 0.0, PAINT)
            if lod == 0:   # the panel's lift-off grip (Darker, 4 mm proud)
                G.prism(P["fine"], F, oct_pts(-0.07, z1 - 0.10, 0.07, z1 - 0.075, 0.008), 0.0, 0.004, DARK)
        if sx > 0 and lod == 0:   # the rating plate (right side, lower panel)
            G.prism(P["fine"], F, oct_pts(-0.33, 0.92, 0.01, 1.12, 0.015), 0.0, 0.002, DARK)   # (behind the y 0.10 seam)
            for i, t in enumerate(("IN-ROW COOLER", "CRAC  CHW  25 KW", "400 V  3 PH  50 HZ", "CHW 7 / 12 C")):
                stencil(P["decal"], F, -0.16, 1.09 - 0.045 * i, 0.022 if i == 0 else 0.016, t, d=0.002)


# ---------------------------------------------------------------------------------------------------- inside
# Broken interiors follow the game's own style (this replaces an earlier modelled machine: pipes, valve, pump, drip
# tray, drives, board, filter rack, and its separate fan wall).
# Behind the shell each zone is a SOLID CORE whose faces are vanilla FracturedMaterial01 in the Fractured / Damaged
# models (the `core` part, fracture.CORE_PARTS; Darker in the NonFractured model, where nothing sees it), cut and
# capped along the seams like any solid; the only modelled parts are the two a hole shows and a player recognises:
#   | part                                   | purpose / what a break shows                                      |
#   | the fan wall: the three fan modules    | the fans blow through their orifices into the cold aisle (_fan_   |
#   |   (housing with its orifice, rotor)    |   module: the housings' orifice walls are the fan wall)           |
#   | cooling coil: the fin pack filling the | the CHW coil the hot aisle's air passes; its perforated fin faces |
#   |   core zone, perforated fin faces      |   are what a dead fan section or filter door shows (2 mm behind  |
#   |   front (fan plenum) and back (filters)|   the seam)                                                       |
#   | plenum baffles (Darker, 4 mm)          | close the cores where the fan orifices, the door grilles and the  |
#   |                                        |   filter louvres look in: the intact Fractured model shows no     |
#   |                                        |   break face                                                      |
# Every exposing zone's death leaves its seams covered (dc/interior.py cover, Tests/test_interior.py): the fan
# sections and the controller share one front core (cut at the door-rail seams), the service bay and the filter door
# one rear core (cut at the grille rail); the core zone is the coil. LOD2 (no openings left) is one core box.
LINER_X = (0.458, 0.470)              # |x| of the plenum side walls
INNER_Z = (0.252, ZT - 0.006)         # the cores and the coil: on the plinth (2 mm clear) up to the roof plate
COIL_Y = (SEAM_Y[1] + 0.002, SEAM_Y[0] - 0.002)    # the fin pack fills the core zone, 2 mm inside its seams
PERF_LIFT = 0.0015                    # the perforated fin faces stand this proud of the fin pack
BAFFLE_T = 0.004
FRONT_CORE_Y = (SEAM_Y[0] + 0.002, MOD_Y[0] - 0.07 - BAFFLE_T)   # a 7 cm plenum behind the fan modules
REAR_CORE_Y = (-0.505, SEAM_Y[1] - 0.002)          # behind the filters and the bay's port frames (3 cm clear)


def _inside(P, lod):
    """The cores, the coil and the baffles (table above) at LOD0 / LOD1; LOD2 one core box (LOD3 is the silhouette)."""
    core, dk = P["core"], P["fine"]
    x0, x1 = -LINER_X[0], LINER_X[0]
    z0, z1 = INNER_Z
    if lod >= 2:
        G.box(core, (-LINER_X[1], CORE_Y[0], z0), (LINER_X[1], CORE_Y[1], ZT - 0.002), DARK)
        return
    # the coil: the Darker fin pack with its perforated faces toward the fan plenum (+y) and the filters (-y)
    ya, yb = COIL_Y
    G.box(dk, (x0, ya, z0), (x1, yb, z1), DARK)
    _perf(P, x0, x1, z0, z1, yb + PERF_LIFT)
    y = ya - PERF_LIFT
    perf_quad(P["perf"], [(x1, y, z0), (x1, y, z1), (x0, y, z1), (x0, y, z0)], (0, 2))
    # the front core (fan sections, controller) behind its baffle; the rear core (bay, filter door) behind its own
    fa, fb = FRONT_CORE_Y
    G.box(core, (x0, fa, z0), (x1, fb, z1), DARK)
    G.box(dk, (x0, fb, z0), (x1, fb + BAFFLE_T, z1), DARK)
    ra, rb = REAR_CORE_Y
    G.box(core, (x0, ra, z0), (x1, rb, z1), DARK)
    G.box(dk, (x0, ra - BAFFLE_T, z0), (x1, ra, z1), DARK)


# ---------------------------------------------------------------------------------------------------- front
def _fan_module(P, k, lod):
    """One hot-swap fan module: the Darker housing (its orifice wall is the fan's shroud), the MetalDull venturi lip,
    the finger guard (rings, spokes) round the static motor, the stencilled module number."""
    F = F_front(0.0)
    zc = FAN_ZC[k]
    sq = oct_pts(-MOD_HALF, zc - MOD_HALF, MOD_HALF, zc + MOD_HALF, 0.03)
    if lod >= 2:
        G.prism(P["fine"], F, sq, MOD_Y[0], MOD_Y[1], DARK)
        G.prism(P["lip"], F, _circle(VENTURI[0], 10, 0, zc), MOD_Y[1], VENTURI[2], HARDWARE)   # the fan disc
        return
    n = 16 if lod == 0 else 8
    G.plate(P["fine"], F, sq, [_circle(ORIFICE_R, n, 0, zc)], MOD_Y[0], MOD_Y[1], DARK)
    G.ring(P["lip"], F, _circle(VENTURI[0], n, 0, zc), _circle(ORIFICE_R, n, 0, zc), VENTURI[1], VENTURI[2], HARDWARE)
    g = P["guard"]
    # (12-sided wires: a 3.6 mm ring reads round at 12; within the project's 90 % triangle cap)
    rings, ng = (GUARD_R[:3], 12) if lod == 0 else ((), 0)      # LOD1: the wires are sub-pixel, the spokes stay
    for r in rings:
        G.ring(g, F, _circle(r + 0.0018, ng, 0, zc), _circle(r - 0.0018, ng, 0, zc), GUARD_Y[0], GUARD_Y[1], HARDWARE)
    ns = 8 if lod == 0 else 0                                      # (LOD1: no guard at all)
    for i in range(ns):
        ang = math.pi / ns * (2 * i + 1) / 2 + math.pi / 8
        m = Matrix.Translation(F(0.0, zc, 0.0)) @ Matrix.Rotation(ang, 4, "Y")
        G.box(g, (MOTOR[0] - 0.004, GUARD_Y[0] - 0.001, -0.0018), (VENTURI[0] - 0.002, GUARD_Y[1], 0.0018), HARDWARE,
              matrix=m)
    # the static motor (external-rotor EC motor: its stator and the guard's centre carry it), a MetalDull face ring
    G.cylinder(P["fine"], F(0.0, zc, MOTOR[1]), F(0.0, zc, MOTOR[2]), MOTOR[0], 12 if lod == 0 else 8, DARK)
    stencil(P["decal"], F, 0.0, zc, 0.040, f"F{k + 1}", d=MOTOR[2])
    if lod == 0:   # the module's two captive screws (hot-swap) on the housing corners
        for a, b in ((-MOD_HALF + 0.03, zc + MOD_HALF - 0.03), (MOD_HALF - 0.03, zc - MOD_HALF + 0.03)):
            G.cylinder(P["hw"], F(a, b, MOD_Y[1] - 0.001), F(a, b, MOD_Y[1] + 0.004), 0.009, 6, STEEL)


def _perf(P, a0, a1, b0, b1, y):
    """A perforated grille quad facing +y over the window a0..a1 (a = -x), b0..b1 at depth y."""
    x0, x1 = -a1, -a0
    perf_quad(P["perf"], [(x0, y, b0), (x0, y, b1), (x1, y, b1), (x1, y, b0)], (0, 2))


def door_windows():
    """The perforated supply-grille windows of the fan door, (a0, a1, b0, b1) with a = -x: one per fan module on each
    side (the door rails between the modules stay solid, so a fracture seam runs along a rail, not through a grille);
    the latch side's middle one stops under the caution label."""
    out = []
    for k, zc in enumerate(FAN_ZC):
        b0, b1 = zc - MOD_HALF + 0.012, zc + MOD_HALF - 0.012
        out.append((-WIN_X[1], -WIN_X[0], b0, b1))                                   # hinge side (viewer's left)
        out.append((WIN_X[0], WIN_X[1], b0, LABEL_Z[0] - 0.018 if k == 1 else b1))    # latch side
    return out


def _front_door(P, lod):
    """The hinged fan door: a Colorable plate round the three module openings and the perforated supply grilles,
    three hinges on the left edge (the viewer's left: +x), a recessed latch on the right, the caution label."""
    F = F_front(0.0)
    z0, z1 = DOOR_Z
    out = oct_pts(-DOOR_A, z0, DOOR_A, z1, 0.02)
    y0, y1 = DOOR_Y
    holes = [G.rect(-MOD_HALF - 0.004, MOD_HALF + 0.004, zc - MOD_HALF - 0.004, zc + MOD_HALF + 0.004)
             for zc in FAN_ZC]
    wins = door_windows()
    if lod >= 2:
        G.plate(P["frame"], F, out, holes, y0, y1, PAINT)
        for k in range(3):
            _fan_module(P, k, lod)
        for a0, a1, b0, b1 in wins:
            G.prism(P["fine"], F, G.rect(a0, a1, b0, b1), y1, y1 + 0.001, DARK)
        return
    holes += [G.rect(*w) for w in wins]
    holes.append(oct_pts(LATCH_X[0], LATCH_Z[0], LATCH_X[1], LATCH_Z[1], 0.006))   # the latch pocket (viewer's right)
    G.plate(P["panel"], F, out, holes, y0, y1, PAINT)
    for a0, a1, b0, b1 in wins:   # the perforated supply grille, 16 mm in (the dark plenum behind shows through)
        _perf(P, a0, a1, b0, b1, y0 + 0.006)
    for k in range(3):
        _fan_module(P, k, lod)
    # hinges (+x edge): a Darker barrel on the door's edge, its leaf on the door face, MetalDull pin caps
    for zh in HINGE_Z:
        xh = DOOR_A - 0.003
        G.cylinder(P["fine"], (xh, y1 + 0.002, zh - 0.045), (xh, y1 + 0.002, zh + 0.045), 0.010,
                   10 if lod == 0 else 4, DARK)
        G.prism(P["fine"], F, G.rect(-DOOR_A + 0.004, -DOOR_A + 0.05, zh - 0.04, zh + 0.04), y1, y1 + 0.003, DARK)
        if lod == 0:
            for zz in (zh - 0.049, zh + 0.045):
                G.cylinder(P["hw"], (xh, y1 + 0.002, zz), (xh, y1 + 0.002, zz + 0.004), 0.007, 6, HARDWARE)
    # the recessed latch (-x edge): a Darker pocket floor, a flush MetalDull T-handle, its key cylinder
    xa, xb = -LATCH_X[1], -LATCH_X[0]
    G.box(P["fine"], (xa, y0 - 0.004, LATCH_Z[0]), (xb, y0 + 0.004, LATCH_Z[1]), DARK)
    G.box(P["hw"], (xa + 0.009, y0 + 0.004, LATCH_Z[0] + 0.018), (xb - 0.009, y0 + 0.013, LATCH_Z[1] - 0.034), HARDWARE)
    if lod == 0:
        xm = (xa + xb) / 2
        G.cylinder(P["hw"], (xm, y0 + 0.004, LATCH_Z[1] - 0.017), (xm, y0 + 0.012, LATCH_Z[1] - 0.017), 0.007, 12, STEEL)
    # CAUTION ROTATING FANS on the latch-side strip: Yellow border, Darker field, white stencils
    a0, a1 = WIN_X[0] + 0.002, WIN_X[1] - 0.002
    b0, b1 = LABEL_Z
    G.prism(P["hw"], F, oct_pts(a0, b0, a1, b1, 0.008), y1, y1 + 0.001, YELLOW)
    G.prism(P["fine"], F, oct_pts(a0 + 0.006, b0 + 0.006, a1 - 0.006, b1 - 0.006, 0.006), y1 + 0.001, y1 + 0.0016,
            DARK)
    am = (a0 + a1) / 2
    stencil(P["decal"], F, am, b1 - 0.035, 0.016, "CAUTION", d=y1 + 0.0016)
    if lod == 0:
        stencil(P["decal"], F, am, b1 - 0.085, 0.0125, "ROTATING", d=y1 + 0.0016)
        stencil(P["decal"], F, am, b1 - 0.115, 0.0125, "FANS", d=y1 + 0.0016)
        stencil(P["decal"], F, am, b0 + 0.030, 0.0095, "ISOLATE FIRST", d=y1 + 0.0016)


def _controller(P, lod):
    """The controller panel: the static status display (white text on a Darker screen), the RUN lamp (the swapper's
    slot), the unlit amber ALARM lamp, MODE / SET keys, the perforated vent of the electronics bay."""
    F = F_front(0.0)
    z0, z1 = CTRL_Z
    y0, y1 = DOOR_Y
    out = oct_pts(-DOOR_A, z0, DOOR_A, z1, 0.02)
    disp = (-0.39, -0.02, 1.895, 2.195)          # (a0, a1, b0, b1): the viewer's left
    vent = (0.25, 0.39, 1.895, 2.195)
    if lod >= 2:
        G.prism(P["frame"], F, out, y0, y1, PAINT)
        G.prism(P["fine"], F, G.rect(disp[0], disp[1], disp[2], disp[3]), y1, y1 + 0.001, DARK)
        return
    G.plate(P["panel"], F, out, [G.rect(disp[0], disp[1], disp[2], disp[3]), G.rect(*vent)], y0, y1, PAINT)
    # display: a Darker bezel round the opening, the screen 12 mm in, the readout
    e = 0.012
    G.ring(P["fine"], F, oct_pts(disp[0] - e, disp[2] - e, disp[1] + e, disp[3] + e, 0.008),
           oct_pts(disp[0], disp[2], disp[1], disp[3], 0.004), y1, y1 + 0.004, DARK)
    ys = y0 + 0.010
    G.box(P["fine"], (-disp[1], ys - 0.004, disp[2]), (-disp[0], ys, disp[3]), DARK)
    lines = (("SUPPLY  18 C", 0.026), ("RETURN  32 C", 0.026), ("FANS  3/3", 0.020), ("SET  18 C   AUTO", 0.016))
    for i, (t, h) in enumerate(lines):
        stencil(P["decal"], F, disp[0] + 0.022, disp[3] - 0.045 - 0.072 * i, h, t, d=ys, align="left")
    # the lamp / key legend: a Darker plate (white stencils never straight on the paint) carrying the RUN
    # (swapped to green while Working) and ALARM (unlit amber lens) lamps, the MODE / SET keys and their legends
    yl = y1 + LEGEND_T
    G.prism(P["fine"], F, oct_pts(*LEGEND, 0.012), y1, yl, DARK)
    lamp(P["hw"], F, 0.05, 2.15, yl, r=0.014, mat=LAMP, lod=lod)
    lamp(P["hw"], F, 0.05, 2.07, yl, r=0.014, mat=YELLOW, lod=lod)
    if lod == 0:   # (LOD1: the lamps only)
        stencil(P["decal"], F, 0.08, 2.15, 0.018, "RUN", d=yl, align="left")
        stencil(P["decal"], F, 0.08, 2.07, 0.018, "ALARM", d=yl, align="left")
    for a, t in ((0.06, "MODE"), (0.16, "SET")) if lod == 0 else ():   # keys: MetalDull caps in Darker bezels
        G.prism(P["fine"], F, oct_pts(a - 0.026, 1.905, a + 0.026, 1.955, 0.006), yl, yl + 0.003, DARK)
        G.prism(P["hw"], F, oct_pts(a - 0.019, 1.912, a + 0.019, 1.948, 0.004), yl + 0.003, yl + 0.007, HARDWARE)
        stencil(P["decal"], F, a, 1.977, 0.011, t, d=yl)
    _perf(P, *vent, y0 + 0.006)
    if lod == 0:   # the panel's title on its own Darker strip
        G.prism(P["fine"], F, oct_pts(-0.33, 2.212, -0.08, 2.234, 0.006), y1, y1 + LEGEND_T, DARK)
        stencil(P["decal"], F, -0.205, 2.223, 0.012, "CRAC CONTROLLER", d=y1 + LEGEND_T)
        for a in (-DOOR_A + 0.016, DOOR_A - 0.016):
            for b in (z0 + 0.016, z1 - 0.016):
                bolt(P["hw"], F, a, b, y1, r=0.006)


# ---------------------------------------------------------------------------------------------------- rear
def _rear_door(P, lod):
    """The filter door on the hot aisle (the upper half): two louvred return grilles over pleated
    filters, a FILTER tab and two quarter-turn latches each, hinged on the +x edge (the viewer's right from the rear:
    a = +x)."""
    F = F_back(0.0)
    z0, z1 = FILTER_DOOR_Z
    y0, y1 = -REAR_Y[1], -REAR_Y[0]               # depths along -y (F_back's normal)
    out = oct_pts(-DOOR_A, z0, DOOR_A, z1, 0.02)
    gx = 0.36
    wins = [(-gx, gx, b0 + 0.05, b1 - 0.012) for b0, b1 in GRILLES]    # each grille over its FILTER tab
    if lod >= 2:
        G.prism(P["frame"], F, out, y0, y1, PAINT)
        for a0, a1, b0, b1 in wins:
            G.prism(P["fine"], F, G.rect(a0, a1, b0, b1), y1, y1 + 0.001, DARK)
        return
    G.plate(P["panel"], F, out, [G.rect(*w) for w in wins], y0, y1, PAINT)
    for i, (a0, a1, b0, b1) in enumerate(wins):
        Fw = F_back(-y1)
        G.louvre(P["fine"], Fw, a0, a1, b0, b1, -0.011, 7 if lod == 0 else 3, DARK, angle=40, t=0.004)
        # the filter behind: a MetalDull frame and (LOD0) the pleats, Darker media
        fy0, fy1 = -FILTER_Y[1], -FILTER_Y[0]
        if lod == 0:
            G.ring(P["hw"], F, G.rect(a0 - 0.004, a1 + 0.004, b0 - 0.004, b1 + 0.004),
                   G.rect(a0 + 0.008, a1 - 0.008, b0 + 0.008, b1 - 0.008), fy0, fy1, HARDWARE)
            n = int((a1 - a0 - 0.016) / 0.06)
            pitch = (a1 - a0 - 0.016) / n
            for k in range(n):
                a = a0 + 0.008 + pitch * (k + 0.5)
                tri = [(a - pitch * 0.45, fy0), (a + pitch * 0.45, fy0), (a, fy1 - 0.001)]
                pts = [(x, y) for x, y in tri]
                Fp = Face((0, 0, b1 - 0.008), (1, 0, 0), (0, -1, 0))    # plan section (a = x, b = -y), normal -z
                G.prism(P["fine"], Fp, pts, 0.0, (b1 - 0.008) - (b0 + 0.008), DARK)
        # FILTER tab + latches
        bt = (GRILLES[i][0] + 0.012, GRILLES[i][0] + 0.042)
        G.prism(P["fine"], F, oct_pts(-0.10, bt[0], 0.10, bt[1], 0.006), y1, y1 + 0.003, DARK)
        if lod == 0:
            stencil(P["decal"], F, 0.0, (bt[0] + bt[1]) / 2, 0.018, f"FILTER {i + 1}", d=y1 + 0.003)
        for a in (-0.30, 0.30) if lod == 0 else ():   # quarter-turn fasteners: Darker boss, MetalDull slot
            bm = (bt[0] + bt[1]) / 2
            G.cylinder(P["fine"], F(a, bm, y1 - 0.001), F(a, bm, y1 + 0.004), 0.017, 8, DARK)
            G.prism(P["hw"], F, G.rect(a - 0.0035, a + 0.0035, bm - 0.012, bm + 0.012), y1 + 0.004, y1 + 0.0065,
                    HARDWARE)
    for zh in REAR_HINGE_Z:   # hinges on the +x edge
        xh = DOOR_A - 0.003
        G.cylinder(P["fine"], (xh, -(y1 + 0.002), zh - 0.045), (xh, -(y1 + 0.002), zh + 0.045), 0.010,
                   10 if lod == 0 else 4, DARK)
        G.prism(P["fine"], F, G.rect(DOOR_A - 0.05, DOOR_A - 0.004, zh - 0.04, zh + 0.04), y1, y1 + 0.003, DARK)


def port_points(spec):
    """{dummy name: (x, y, z)} of the service ports in the centred Blender block frame: on the rear CELL FACE (y = -D2,
    where a conveyor would butt the block), centred on a 2 x 2 cell patch (x, z on cell lines)."""
    dims(spec)
    return {n: (x, -D2, z - H / 2) for n, x, z in PORTS}


def _service_bay(P, lod):
    """The bolted service bay under the filter door: a Colorable panel with two 0.4 m port openings, Keen's small
    conveyor port frame (kit part) in each, a bolted Darker blind plate in each hatch recess (the hatch is gone), the
    "O2 / COOLANT SERVICE" label between them and a PORT tag beside each (white stencils on Darker plates)."""
    from . import crac_ports as KP
    F = F_back(0.0)
    z0, z1 = BAY_Z
    y0, y1 = -REAR_Y[1], -REAR_Y[0]
    out = oct_pts(-DOOR_A, z0, DOOR_A, z1, 0.02)
    hy = -KP.hatch_y(PORT_FACE_Y)                  # the blind plates' face depth (F_back: +depth = -y)
    hb = 0.171                                     # the hatch recess half size (the vanilla hatch face's)
    # the openings follow the kit frame's chamfered outline (1 mm clear all round: no void at the corners)
    holes = [oct_pts(x - KP.HALF - 0.001, z - KP.HALF - 0.001, x + KP.HALF + 0.001, z + KP.HALF + 0.001, KP.CLIP)
             for _, x, z in PORTS]
    if lod >= 2:   # far: the panel, each port a Yellow block (its frame) with the Darker blind plate standing on it
        G.prism(P["frame"], F, out, y0, y1, PAINT)
        for _, x, z in PORTS:
            G.prism(P["hw"], F, G.rect(x - KP.HALF, x + KP.HALF, z - KP.HALF, z + KP.HALF), y1, -PORT_FACE_Y - 0.004,
                    YELLOW)
            G.prism(P["fine"], F, G.rect(x - hb, x + hb, z - hb, z + hb), y1, -PORT_FACE_Y, DARK)
        return
    G.plate(P["panel"], F, out, holes, y0, y1, PAINT)
    for i, (name, x, z) in enumerate(PORTS):
        P[f"port{i + 1}"] = KP.port(lod, x, z - H / 2, PORT_FACE_Y, f"port{i + 1}")   # (built centred: no shift)
        # the blind plate in the hatch recess (Darker, bolted), its BLANKED tag
        G.prism(P["fine"], F, oct_pts(x - hb, z - hb, x + hb, z + hb, 0.04) if lod == 0 else
                G.rect(x - hb, x + hb, z - hb, z + hb), y0 - 0.01, hy, DARK)
        if lod == 0:
            for k in range(4):   # four bolts at the corners hold the blind plate in the hatch's seat
                t = 2 * math.pi * k / 4 + math.pi / 4
                bolt(P["hw"], F, x + 0.17 * math.cos(t), z + 0.17 * math.sin(t), hy, r=0.008)
            stencil(P["decal"], F, x, z + 0.03, 0.026, "BLANKED", d=hy)
            stencil(P["decal"], F, x, z - 0.03, 0.016, "DO NOT REMOVE", d=hy)
        if lod > 0:   # (LOD1 budget: the tags and the label are LOD0 detail)
            continue
        # the PORT tag beside the frame (latch side)
        ta = x + KP.HALF + 0.11
        G.prism(P["fine"], F, oct_pts(ta - 0.075, z - 0.022, ta + 0.075, z + 0.022, 0.008), y1, y1 + 0.002, DARK)
        stencil(P["decal"], F, ta, z, 0.020, f"PORT {i + 1}", d=y1 + 0.002)
    if lod > 0:
        return
    # the label between the ports, on a Darker plate
    zm = (PORTS[0][2] + PORTS[1][2]) / 2
    G.prism(P["fine"], F, oct_pts(-0.19, zm - 0.03, 0.19, zm + 0.03, 0.01), y1, y1 + 0.002, DARK)
    stencil(P["decal"], F, 0.0, zm, 0.024, PORT_LABEL, d=y1 + 0.002)
    if lod == 0:   # the panel's four corner bolts
        for a in (-DOOR_A + 0.03, DOOR_A - 0.03):
            for b in (z0 + 0.03, z1 - 0.03):
                bolt(P["hw"], F, a, b, y1, r=0.007)


# ---------------------------------------------------------------------------------------------------- top band
def _top_band(P, lod):
    """Headers (front: the unit ID; rear: RETURN AIR and the filter DP gauge), side skins, the containment rail (the
    rack's), the top deck with the two brush plates (the rack's) and the chilled-water service well."""
    fr, dk, hw = P["frame"], P["dark"], P["hw"]
    a1 = W2 - CAP - 0.006
    for F, front in ((R.F_front(YK - 0.016), True), (R.F_back(-YK + 0.016), False)):
        G.prism(fr, F, oct_pts(-a1, ZT + 0.016, a1, H - 0.034, 0.03), -0.013, 0.0, PAINT)
        if lod >= 2:
            continue
        zc = ZT + 0.075            # (under the containment rail: it stands 4 cm proud over the header's top half)
        if front:
            # (the unnamed Yellow "cold-side tag" square beside the ID is gone: Yellow only at hazards)
            # As on the racks (neutral ID): the neutral "CRAC" caption and a blank riveted write-on tag
            # (rack.id_tag), no baked unit number (every CRAC read alike); the ID comes from a sign or rack label
            G.prism(P["fine"], F, oct_pts(-0.17, zc - 0.05, 0.17, zc + 0.05, 0.018), 0.0, 0.006, DARK)
            a0 = -0.17 + 0.03                          # clear of the plate's clipped corners
            tw = stencil(P["decal"], F, a0, zc, 0.045, UNIT_CAPTION, d=0.006, align="left")
            if lod == 0:   # (LOD1 budget: the tag is LOD0 detail, as the rack roof's)
                R.id_tag(P, F, a0 + tw + 0.018, 0.17 - 0.03, zc - 0.028, zc + 0.028, 0.006, lod)
        else:
            G.prism(P["fine"], F, oct_pts(-0.21, zc - 0.04, 0.12, zc + 0.04, 0.012), 0.0, 0.004, DARK)
            stencil(P["decal"], F, -0.045, zc + 0.012, 0.026, "RETURN AIR", d=0.004)
            stencil(P["decal"], F, -0.045, zc - 0.022, 0.013, "FILTER DP", d=0.004)
            # the filter differential-pressure gauge: Darker bezel, MetalDull dial, Yellow needle
            G.cylinder(P["fine"], F(0.22, zc, 0.0), F(0.22, zc, 0.012), 0.036, 16 if lod == 0 else 8, DARK)
            G.cylinder(hw, F(0.22, zc, 0.012), F(0.22, zc, 0.0135), 0.029, 16 if lod == 0 else 8, HARDWARE)
            if lod == 0:
                m = Matrix.Translation(F(0.22, zc, 0.0145)) @ Matrix.Rotation(math.radians(35), 4, "Y")
                G.box(hw, (-0.002, -0.0006, -0.002), (0.024, 0.0006, 0.002), YELLOW, matrix=m)
        if lod == 0:
            for a in (-a1 + 0.025, a1 - 0.025):
                bolt(hw, F, a, zc, 0.0)
    for sx in (-1, 1):
        F = R.F_side(sx)
        b1 = YK - CAP - 0.006
        G.prism(fr, F, oct_pts(-b1, ZT + 0.016, b1, H - 0.034, 0.03), -0.012, 0.0, PAINT)
        if lod == 0:
            for bb in (-b1 + 0.03, b1 - 0.03):
                bolt(hw, F, bb, (ZT + H) / 2 - 0.016, 0.0)
    if lod <= 1:   # the band's floor pan over the body's roof: a dead body zone shows it, not the band's hollow
        G.box(P["fine"], (-LINER_X[1], CORE_Y[0], ZT + 0.002), (LINER_X[1], CORE_Y[1], ZT + 0.006), DARK)
    R._contain_rail(P, dims_stub(), lod, tag_lift=TAG_LIFT)
    _deck(P, lod)


def dims_stub():
    return {"H": H, "ZT": ZT, "tray": True}


def _deck(P, lod):
    """The closed top: a Colorable deck flush with the top plane (the rims mount there, as on the rack), the rack's
    two front brush plates (dims.TOP_ENTRY) and the water service well at the rear."""
    fr, dk, hw = P["frame"], P["dark"], P["hw"]
    a, b, c = W2 - SKIN, YK, CAP
    pts = [(-a + c, -b), (a - c, -b), (a - c, -b + c), (a, -b + c), (a, b - c), (a - c, b - c), (a - c, b),
           (-a + c, b), (-a + c, b - c), (-a, b - c), (-a, -b + c), (-a + c, -b + c)]
    (ex0, ex1), (ey0, ey1) = DM.TOP_ENTRY
    g = DM.ENTRY_FLANGE + 0.0005
    w0, w1, v0, v1 = WELL
    Ft = F_top(0.0)
    if lod >= 2:
        G.plate(fr, Ft, pts, [G.rect(w0, w1, v0, v1)], H - 0.03, H, PAINT)
        G.box(P["fine"], (w0, v0, WELL_FLOOR), (w1, v1, H - 0.03), DARK)
        for x, y, _ in CHW:      # the two flanged stubs
            G.cylinder(P["pipe"], (x, y, H - 0.03), (x, y, FLANGE[2]), FLANGE[0], 8, STEEL)
        for sx in (-1, 1):
            R._entry_fitting(P, sx, 1, (ex0, ex1, ey0, ey1), H, ZT + 0.03, lod, sleeve_front=True)
        return
    m = 0.006                       # the well's Yellow edge trim (the step down), round its opening
    holes = [G.rect(w0 - m, w1 + m, v0 - m, v1 + m)]
    for sx in (-1, 1):
        xa, xb = sorted((sx * (ex0 - g), sx * (ex1 + g)))
        holes.append(G.rect(xa, xb, ey0 - g, ey1 + g))
    G.plate(fr, Ft, pts, holes, H - 0.03, H, PAINT)
    for sx in (-1, 1):   # (the combed LOD0 tufts are the rack's 2 x 500 tris: here its one-tuft lips)
        R._entry_fitting(P, sx, 1, (ex0, ex1, ey0, ey1), H, ZT + 0.03 if lod == 0 else H - 0.03, max(lod, 1),
                         sleeve_front=True)
    G.ring(hw, Ft, G.rect(w0 - m, w1 + m, v0 - m, v1 + m), G.rect(w0, w1, v0, v1), H - 0.03, H - 0.0015, YELLOW)
    G.ring(P["fine"], Ft, G.rect(w0 - m, w1 + m, v0 - m, v1 + m), G.rect(w0, w1, v0, v1), WELL_FLOOR, H - 0.03, DARK)
    G.box(P["fine"], (w0, v0, WELL_FLOOR - 0.006), (w1, v1, WELL_FLOOR), DARK)
    _water(P, lod)


def _water(P, lod):
    """The chilled-water stubs: Darker insulation from the well floor, a Brushed ball valve with a Yellow lever (its
    stem toward the aisle side of the well), the pipe up to a Brushed blind flange whose MetalDull bolt heads stop
    1 mm under the top plane; the condensate stub; the stencils on the well floor (read from the hot aisle)."""
    dk, hw, pp = P["fine"], P["hw"], P["pipe"]
    n = 16 if lod == 0 else 10
    Ft = F_top(0.0)
    zf = WELL_FLOOR
    for x, y, label in CHW:
        if lod >= 1:   # LOD1: insulation, valve body, pipe and flange as four plain cylinders
            G.cylinder(dk, (x, y, zf), (x, y, zf + 0.092), 0.040, 8, DARK)
            G.cylinder(pp, (x, y, zf + 0.092), (x, y, zf + 0.140), 0.042, 8, STEEL)
            G.box(hw, (x - 0.008, y + 0.035, zf + 0.115), (x + 0.008, y + 0.170, zf + 0.125), YELLOW)
            G.cylinder(pp, (x, y, zf + 0.140), (x, y, FLANGE[1]), 0.030, 6, STEEL)   # (LOD1 budget: 6 / 8)
            G.cylinder(pp, (x, y, FLANGE[1]), (x, y, FLANGE[2]), FLANGE[0], 8, STEEL)
            stencil(P["decal"], Ft, x, -0.355, 0.022, label, d=zf)
            continue
        G.cylinder(dk, (x, y, zf), (x, y, zf + 0.085), 0.040, n, DARK)                    # insulation
        G.cylinder(dk, (x, y, zf + 0.085), (x, y, zf + 0.092), 0.044, n, DARK)            # its end collar
        G.cylinder(pp, (x, y, zf + 0.092), (x, y, zf + 0.100), 0.031, n, STEEL)           # union
        G.cylinder(pp, (x, y, zf + 0.100), (x, y, zf + 0.140), 0.042, n, STEEL)           # valve body
        G.cylinder(pp, (x, y + 0.035, zf + 0.120), (x, y + 0.062, zf + 0.120), 0.009, 8, STEEL)   # stem
        G.box(hw, (x - 0.008, y + 0.058, zf + 0.115), (x + 0.008, y + 0.170, zf + 0.125), YELLOW)  # lever
        G.box(dk, (x - 0.010, y + 0.130, zf + 0.113), (x + 0.010, y + 0.172, zf + 0.127), DARK)    # grip
        G.cylinder(pp, (x, y, zf + 0.140), (x, y, FLANGE[1]), 0.030, n, STEEL)            # pipe to the flange
        G.cylinder(pp, (x, y, FLANGE[1]), (x, y, FLANGE[2]), FLANGE[0], 20, STEEL)        # blind flange
        for k in range(6):
            t = 2 * math.pi * k / 6 + math.pi / 6
            bx, by = x + 0.047 * math.cos(t), y + 0.047 * math.sin(t)
            G.cylinder(hw, (bx, by, FLANGE[2] - 0.001), (bx, by, H - 0.001), 0.0085, 6, HARDWARE)
        stencil(P["decal"], Ft, x, -0.355, 0.022, label, d=zf)
    x, y = COND
    G.cylinder(pp, (x, y, zf), (x, y, zf + 0.08), 0.016, 10 if lod == 0 else 6, STEEL)
    G.cylinder(dk, (x, y, zf + 0.08), (x, y, zf + 0.095), 0.021, 10 if lod == 0 else 6, DARK)    # its cap
    if lod == 0:
        stencil(P["decal"], Ft, x, y - 0.050, 0.014, "COND", d=zf)


# ---------------------------------------------------------------------------------------------------- LOD3 / last
def _lod3(P):
    """Silhouette (budget ~150 tris): plinth, body, top, the fan door's three dark discs, the rear grille field."""
    y = YK - 0.003
    G.box(P["dark"], (-XO, -y, 0.0), (XO, y, 0.25), DARK)
    G.box(P["frame"], (-XO, -y, 0.25), (XO, y, H), PAINT)
    F = F_front(0.0)
    for zc in FAN_ZC:
        G.prism(P["fine"], F, oct_pts(-MOD_HALF, zc - MOD_HALF, MOD_HALF, zc + MOD_HALF, 0.06), y, YK - 0.001, DARK)
    G.box(P["fine"], (-0.36, -YK + 0.001, FILTER_DOOR_Z[0] + 0.05), (0.36, -y, ZT - 0.06), DARK)
    for _, x, z in PORTS:   # the service ports: Yellow frames (a 12-tri box each)
        G.box(P["hw"], (x - 0.2, -YK + 0.001, z - 0.2), (x + 0.2, -y, z + 0.2), YELLOW)


def last_lod(spec):
    p = Part("lastlod")
    G.box(p, (-XO, -D2, -H / 2), (XO, D2, H / 2), f"{spec.name}_LastLOD")
    return [p]


# frame / dark / contain take the LOD0 bevel; panel (the three door plates, full of openings) and fine (small Darker
# kit, round parts) do not: a bevel there would cost ~4k triangles for edges nobody sees break
# (`lip` = the fan modules' venturi lip rings, the orifice trim: skin, built with the housing it trims,
# not mounting hardware; split out of `hw` so fracture.ROLES["crac"]'s supports are only the mounts)
PART_NAMES = ("frame", "panel", "dark", "fine", "hw", "guard", "pipe", "decal", "perf", "brush", "contain", "lip",
              "core")   # (core: the solid inside, FracturedMaterial01 when broken: fracture.CORE_PARTS)


def build(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the 12-tri box."""
    if lod == n_lods(spec) - 1:
        return last_lod(spec)
    dims(spec)
    P = {k: Part(k) for k in PART_NAMES}
    P["decal"].decal = True
    P["perf"].decal = True
    if lod == 0:
        P["frame"].bevel = (0.005, 1)
        P["dark"].bevel = (0.004, 1)
        P["contain"].bevel = (0.003, 1)
    if lod >= 3:
        _lod3(P)
    else:
        _plinth(P, lod)
        R._corners(P, dims_stub(), 2 if lod == 1 else lod)   # (LOD1: the caps without their trim: -290 tris)
        _body(P, lod)
        _front_door(P, lod)
        _controller(P, lod)
        _rear_door(P, lod)
        _service_bay(P, lod)
        _top_band(P, lod)
    parts = [p for p in P.values() if p is not None and not p.empty()]
    m = Matrix.Translation((0, 0, -H / 2))
    for p in parts:
        if getattr(p, "kit_meshes", None):   # the vanilla port kit parts are placed in the centred frame already
            continue
        p.bm.transform(m)
        p.bm.normal_update()
    return parts


# ---------------------------------------------------------------------------------------------------- the rotor
def _blade(p, phi0, lod):
    """One swept, twisted blade (a closed thin shell) in the rotor frame (axis = Blender y). Chord stations s in
    -0.5 (trailing) .. +0.5 (leading); the rotor turns about -y, so at angle phi the blade moves toward +phi, and the
    leading edge sits upstream (-y): the air leaves toward +y (the cold aisle)."""
    nr, ns = (6, 4) if lod == 0 else (3, 2)
    r0, r1 = ROTOR_R[0] - 0.004, ROTOR_R[1]
    t = 0.0018
    bm = p.bm
    mi = p.mi(DARK)

    def pt(i, j, side):
        f = i / (nr - 1)
        r = r0 + (r1 - r0) * f
        c = 0.090 + 0.030 * f                     # chord
        beta = math.radians(40.0 - 18.0 * f)      # pitch: steep at the root, flat at the tip
        sweep = -0.32 * f * f                     # sickle: the tip trails (rad)
        s = j / (ns - 1) - 0.5
        camber = 0.010 * (1.0 - (2 * s) ** 2) * (1 - 0.4 * f)
        u = s * c * math.cos(beta)                # along the circle
        y = -s * c * math.sin(beta) + camber + side * t
        phi = phi0 + sweep + u / r
        return bm.verts.new((r * math.cos(phi), y, r * math.sin(phi)))

    top = [[pt(i, j, 1) for j in range(ns)] for i in range(nr)]
    bot = [[pt(i, j, -1) for j in range(ns)] for i in range(nr)]
    for i in range(nr - 1):
        for j in range(ns - 1):
            bm.faces.new((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1])).material_index = mi
            bm.faces.new((bot[i][j], bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j])).material_index = mi
    for i in range(nr - 1):          # leading / trailing edges
        for j in (0, ns - 1):
            q = (top[i][j], bot[i][j], bot[i + 1][j], top[i + 1][j])
            bm.faces.new(q if j == 0 else q[::-1]).material_index = mi
    for i in (0, nr - 1):            # root / tip
        for j in range(ns - 1):
            q = (top[i][j], top[i][j + 1], bot[i][j + 1], bot[i][j])
            bm.faces.new(q if i == 0 else q[::-1]).material_index = mi


def rotor(spec, lod):
    """The CracFan rotor (origin = the pivot, axis = Blender y): the external rotor's Darker bell with a MetalDull
    balancing ring and three Brushed balance clips (so the spin reads even on a dark bell), seven swept blades."""
    hub, bl = Part("hub"), Part("blades")
    n = 24 if lod == 0 else 12
    G.cylinder(hub, (0, -0.026, 0), (0, 0.022, 0), ROTOR_R[0], n, DARK)
    G.cylinder(hub, (0, 0.022, 0), (0, 0.026, 0), ROTOR_R[0] - 0.010, n, HARDWARE)
    if lod == 0:
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.4
            m = Matrix.Rotation(-a, 4, "Y")
            G.box(hub, (ROTOR_R[0] - 0.004, 0.006, -0.008), (ROTOR_R[0] + 0.003, 0.020, 0.008), STEEL, matrix=m)
    for k in range(7):
        _blade(bl, 2 * math.pi * k / 7, lod)
    return [hub, bl]


def rotor_last(lo, hi):
    p = Part("fan_last")
    G.box(p, lo, hi, DARK)
    return [p]


def subparts_for(spec):
    return {FAN: (rotor, rotor_last)}


# ---------------------------------------------------------------------------------------------------- collision
def collision(spec):
    """{"regular", "occupancy", "mount"} boxes, centred Blender frame. Physics: plinth, body, top band (every cell
    occupied). Mount hints as the full rack's (dc/rack.collision) without the slot's: both side planes, the bottom,
    the top rims round the deck, the containment rail band front and back (contain_front / back)."""
    dims(spec)
    reg = [("plinth", (-W2, -D2, 0.0), (W2, D2, 0.25)), ("body", (-W2, -D2, 0.25), (W2, D2, ZT)),
           ("top", (-W2, -D2, ZT), (W2, D2, H))]
    t = 0.005
    IX, IY = DM.RACK_TRAY_IX, DM.RACK_TRAY_IY
    mnt = []
    for sx, nm in ((-1, "left"), (1, "right")):
        x0, x1 = sorted((sx * W2, sx * (W2 - t)))
        mnt.append((f"side_{nm}", (x0, -YK, 0.0), (x1, YK, H)))
    mnt.append(("bottom", (-W2, -YK, 0.0), (W2, YK, t)))
    for sy in (-1, 1):
        y0, y1 = sorted((sy * IY, sy * YK))
        mnt.append((f"rim_{'front' if sy > 0 else 'back'}", (-W2, y0, H - t), (W2, y1, H)))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * IX, sx * W2))
        mnt.append((f"rim_{'right' if sx > 0 else 'left'}", (x0, -YK, H - t), (x1, YK, H)))
    for sy in (-1, 1):
        y0, y1 = sorted((sy * D2, sy * (D2 - t)))
        mnt.append((f"contain_{'front' if sy > 0 else 'back'}", (-W2, y0, ZT + DM.CONTAIN_RAIL_DZ[0]),
                    (W2, y1, ZT + DM.CONTAIN_RAIL_DZ[1])))
    dz = -H / 2

    def sh(boxes):
        return [(n, (lo[0], lo[1], lo[2] + dz), (hi[0], hi[1], hi[2] + dz)) for n, lo, hi in boxes]
    return {"regular": sh(reg), "occupancy": [], "mount": sh(mnt)}
