"""PDUs: the floor PDU cabinet and the zero-U rack PDU strips (Feed A / Feed B).

Both are decorative (vanilla 2.4 has no power-junction block): WallInsertPanel clones, PCU 5, breakable through the
planned fracture pipeline (dc/fracture.py _pdu_cabinet / _pdu_strip).

Frame (Blender, metres, centred on the cell box like every builder here): X width, +Y = front = game Forward, Z up.

---------------------------------------------------------------------------------------------- the zero-U strips
DC_PDU_Rack{42,24}_{A,B}: one cell wide and deep (the rack's freed rear PDU column, rack.PDU_CELLS), 8 / 4 cells tall
(the slot band). Placed at the column's cells, with the rack's yaw, the strip's +Y face is the column's bracket plane
(rack y = -SLOT_HALF_D: the PDU bulkhead with its keyhole slots) and its bottom is the plinth top, where the rack's
twist-lock receptacle sits (dims.PDU_RECEPTACLE). Everything stays inside dims.PDU_ENVELOPE (the column's measured
clear box; Feed B mirrored in x) over the PDU band (rack.pdu_band: the half rack's stops at local z 1.13, under its
top corner caps). Feed A is the +x column (the right one seen from the hot aisle), Feed B is built mirrored, so its
inlet is never upside down.

    | part             | what it is                                              | purpose                                |
    | body             | Darker extruded profile (T-slot grooves, end caps)      | the PDU: busbar and outlets housing    |
    | outlets          | per slot a pair of locking outlets (dims.PDU_OUTLET_*)  | feed the slot's server PSUs (2 per 6U) |
    | jumper cords     | a plug in every outlet, its cord looping into the cord  | pre-dressed cords, ready for the next  |
    |                  | channel and parked under a strap (no free end)          | server: plug them into its PSUs        |
    | cord channel     | Colorable U-channel on the servers' side, strapped      | dresses and holds the parked cords     |
    | bank head        | per 4 slots: breaker (Darker, Yellow trip tab) and a    | bank overcurrent protection and the    |
    |                  | 3-digit ammeter (lit green segments), "BANK n"          | bank's load at a glance                |
    | feed tag         | Feed A: Yellow band + "A"; Feed B: paint band + "B"     | A / B redundancy: which feed this is   |
    | inlet cord, plug | heavy cord from the bottom gland to a twist-lock plug   | the strip's supply: the plinth socket  |
    |                  | seated in the rack's plinth receptacle                  | (dims.PDU_RECEPTACLE)                  |
    | brackets         | Brushed standoffs with buttons in the bulkhead keyholes | hang the strip on the column           |

---------------------------------------------------------------------------------------------- the cabinet
DC_PDU_Cabinet: the rack footprint (4 x 10 x 5 cells): the rack's plinth, corner posts and caps, side mounts,
top rim and containment rail, and the rack's top-entry brush plates at the same place (dims.TOP_ENTRY), so a cable
tray Drop lands in it. Its body is a closed cabinet (the front and back keep the rack's 2.7 cm KEEP_OUT).

    | part                | what it is                                            | purpose                             |
    | meter               | Darker window: L1 / L2 / L3 rows, lit 3-digit readings | the incomer's load per phase        |
    |                     | and bar graphs                                         |                                     |
    | rotary isolator     | Yellow escutcheon, Darker handle, ON / OFF, padlock    | isolates the whole cabinet for safe |
    |                     | hasp                                                   | maintenance (lock-off)              |
    | DANGER 400 V        | vanilla Stickers02 "DANGER HIGH VOLTAGE" + 400 V plate | the incomer voltage                 |
    | branch breakers     | 2 x 12 Darker breakers on DIN rails, Yellow trip tabs, | per-rack-feed branch protection     |
    |                     | circuit numbers 1-24, behind a hinged lockable cover    | (each rack PDU strip is one branch) |
    | hinged cover        | shadow-gap outline, Brushed hinge knuckles, key lock   | keeps the dead-front closed         |
    | top brush plates    | the rack's top-entry plates (dims.TOP_ENTRY)           | cables in from / out to the tray    |
    | rear gland plates   | Darker plates, cable glands with blanking plugs        | alternative (bottom-rear) entries   |
    | rear louvre         | exhaust louvre in the rear header                      | breaker / busbar heat to the hot    |
    |                     |                                                        | aisle                               |
    | label, lamp         | "PDU 1" plate and the always-lit power lamp            | which cabinet; supply present       |
"""
import math

from . import catalog
from . import dims as DM

try:   # geometry needs Blender; the numbers, collision() and hints are plain Python (pytest imports them outside)
    from mathutils import Matrix
    from se2model import geom as G
    from se2model.geom import Face, Part
    from se2model.config import S2
except ImportError:
    Matrix = G = Face = Part = S2 = None
from .style import DARK, HARDWARE, LAMP_GREEN, PAINT, STEEL, YELLOW, bolt, oct_pts, stencil

RUBBER = "Rubber"          # the cords and plug bodies (vanilla Rubber, as the trays' black power cable)
CELL = DM.CELL
TAG_LIFT = 0.0006          # the CONTAINMENT rail tag 0.6 mm clear of its plate (z-fight); = rack.CONTAIN_TAG_LIFT

# ============================================================================================== the strips
COL_X = sum(DM.PDU_COL_X) / 2            # 0.375: the strip's origin in the rack (|x|)
COL_Y = sum(DM.PDU_COL_Y) / 2            # -0.5
(_EX0, _EX1), (_EY0, _EY1) = DM.PDU_ENVELOPE
ENV_X = (_EX0 - COL_X, _EX1 - COL_X)     # (-0.083, 0.045): the envelope, strip-local (Feed A)
ENV_Y = (_EY0 - COL_Y, _EY1 - COL_Y)     # (-0.096, 0.123)
XC = DM.PDU_RECEPTACLE[0] - COL_X        # -0.019: the column centre line (keyholes, receptacle)
YR = DM.PDU_RECEPTACLE[1] - COL_Y        # 0.0135: the receptacle's y
BX = (DM.PDU_STRIP_CX - COL_X - 0.045, DM.PDU_STRIP_CX - COL_X + 0.045)   # body x (-0.047, 0.043)
FACE_Y = DM.PDU_OUTLET_FACE_Y + 0.006 - COL_Y   # 0.0: the body's front face (outlets 6 mm proud)
BY = (FACE_Y, FACE_Y + 0.066)            # body y (front .. back)
OX = tuple(x - COL_X for x in DM.PDU_OUTLET_X)   # (-0.024, 0.020): the outlet pair (inner, outer)
CH_X = (ENV_X[0] + 0.0015, BX[0] - 0.004)        # the cord channel (-0.0815, -0.051), on the servers' side
CH_Y = (FACE_Y, FACE_Y + 0.060)
CH_W = 0.003                             # channel wall
LIP = 0.0025                             # the channel mouth's lips
LANES = (-0.0615, -0.0705)               # the parked cords' x in the channel (inner outlet, outer outlet)
CORD_R = 0.0040                          # jumper cord radius
INLET_R = 0.0085                         # the inlet cord
PLUG_R = 0.0175                          # twist-lock plug body (the socket's Yellow ring: r 0.019)
PLUG_H = 0.030
BOOT = (0.030, 0.048)                    # the plug's strain-relief boot (z above the strip bottom)
BODY_Z0 = 0.062                          # the body's bottom above the strip bottom (the inlet gland)
CAP_T = 0.008                            # end-cap thickness
TOP_GAP = 0.004                          # under the full rack's tray floor (= the strip cell top)
BAND_GAP = 0.004                         # under the half rack's PDU band top (rack.pdu_band)
HEAD_Z = (0.130, 0.235)                  # slot-relative z of a bank head / the feed tag
BANK = 4                                 # slots per bank (one breaker + ammeter each)
BTN_Z = 0.058                            # slot-relative z of a bracket's button (the bulkhead keyhole's slot)
BTN_Y = ENV_Y[1] - 0.0001                # the button heads' face (inside the envelope)
AMPS = {1: "124", 2: "118"}              # the static ammeter readings per bank (12.4 A, 11.8 A)

LOD_COUNT = {}


def strip_feed(spec):
    """"A" | "B" (the catalogue variant)."""
    if spec.family != "pdu_strip" or spec.variant not in ("A", "B"):
        raise ValueError(f"{spec.name} is not a rack PDU strip")
    return spec.variant


def strip_sx(spec):
    return 1 if strip_feed(spec) == "A" else -1


def strip_rack(spec):
    """The rack this strip fits (its height: 8 cells = 42U, 4 cells = 24U); the open variant is the reference."""
    return catalog.BY_NAME[f"DC_Rack{42 if spec.cells[1] == 8 else 24}_Open"]


def nslots(spec):
    return spec.cells[1]


def h2(spec):
    return CELL * spec.cells[1] / 2


def strip_top(spec):
    """Strip-local z of the body's top: under the full rack's tray floor, or under the half rack's PDU band top."""
    from . import rack
    b0, b1 = rack.pdu_band(strip_rack(spec))
    zb = -h2(spec)
    return min(h2(spec) - TOP_GAP, zb + (b1 - b0) - BAND_GAP)


def slot_z(spec, k):
    """Strip-local z of slot k's floor (k = 1..n; slot 1's floor is the strip's bottom = the plinth top)."""
    return -h2(spec) + DM.SLOT_H * (k - 1)


def banks(spec):
    """[(bank 1.., the slot its head sits in)]: one bank per BANK slots, the head over its first slot's outlets."""
    return [(i + 1, 1 + BANK * i) for i in range((nslots(spec) + BANK - 1) // BANK)]


def tag_slot(spec):
    """The slot carrying the feed tag: the highest one without a bank head whose head region fits under the top."""
    heads = {s for _, s in banks(spec)}
    for k in range(nslots(spec), 0, -1):
        if k not in heads and slot_z(spec, k) + HEAD_Z[1] <= strip_top(spec) - CAP_T:
            return k
    raise RuntimeError(f"{spec.name}: no room for the feed tag")


def bracket_slots(spec):
    """The two slots whose bulkhead keyholes take the strip's mounting buttons (the second and the top slot)."""
    return (2, nslots(spec))


def outlets_local(spec):
    """[(slot, outlet 0 / 1, (x, y, z))] of the strip's outlet sockets, strip-local (dims.pdu_outlets, moved into the
    strip's frame; Feed B mirrored)."""
    from . import rack
    sx = strip_sx(spec)
    zc = rack.pdu_band(strip_rack(spec))[0] + h2(spec)      # the strip's centre, rack-local z (0 = floor)
    return [(k, i, (round(x - sx * COL_X, 6), round(y - COL_Y, 6), round(z - zc, 6)))
            for k, i, (x, y, z) in DM.pdu_outlets(nslots(spec), strip_feed(spec))]


# ---------------------------------------------------------------------------------------------------- collision
HINT_T = 0.005


def strip_collision(spec):
    """{"regular", "occupancy", "mount"} (the rack.collision format; Blender frame, centred).
    Regular: one box, the envelope (mirrored for B) from the bottom to the body's top. Occupancy: the column cells
    (the whole 1 x n x 1 box, so nothing else is built into the column). Mount hint: Down only (the plug's seat on
    the plinth top: the rack's pdu_seat).
    The strip does not mount Forward (its brackets on the bulkhead). The bulkhead's
    render face lies 0.5 mm inside the bracket plane, so the rack mounts Backward over the WHOLE column (the generator
    samples the render; the pdu_bracket hint cannot narrow it), and the placer centres a strip on the aimed cell: aimed
    at the upper half of a 24U column it rose one or two cells, out through the half rack's open top, and one bracket
    cell on the bulkhead validated it (any one mount cell does). With Down only, a raised strip's bottom faces an empty
    column cell and never validates; only the seat on the plinth does (Tests/test_pdu_targeting.py)."""
    sx = strip_sx(spec)
    H2 = h2(spec)
    x0, x1 = sorted((sx * ENV_X[0], sx * ENV_X[1]))
    reg = [("strip", (x0, ENV_Y[0], -H2), (x1, ENV_Y[1], strip_top(spec)))]
    e = 0.002
    occ = [("column", (-CELL / 2 + e, -CELL / 2 + e, -H2 + e), (CELL / 2 - e, CELL / 2 - e, H2 - e))]
    t = HINT_T
    c = CELL / 2
    mnt = [("plug_seat", (-c, -c, -H2), (c, c, -H2 + t))]
    return {"regular": reg, "occupancy": occ, "mount": mnt}


def strip_directions(spec):
    """The strip's MountPointGeneratorSettings.Directions, read off its hints (the game's names: Blender +Y = game
    Forward, -Z = Down): "Down" only (strip_collision)."""
    out = []
    H2 = h2(spec)
    c = CELL / 2
    for _, lo, hi in strip_collision(spec)["mount"]:
        if abs(lo[2] + H2) < 1e-9 and hi[2] - lo[2] < 0.01:
            out.append("Down")
        elif abs(hi[1] - c) < 1e-9 and hi[1] - lo[1] < 0.01:
            out.append("Forward")
    order = ("Forward", "Backward", "Left", "Right", "Up", "Down")
    return ", ".join(d for d in order if d in out)


# ---------------------------------------------------------------------------------------------------- geometry
def F_rear(y):  # noqa: N802
    """The strip's working face (normal -y, toward the rear opening): a = +x (the viewer's right), b = z."""
    return Face((0, y, 0), (1, 0, 0), (0, 0, 1))


def F_up():  # noqa: N802
    return Face((0, 0, 0), (1, 0, 0), (0, 1, 0))


def _profile(lod):
    """The body's extruded section in plan (x, y): chamfered front corners, a T-slot groove on each side."""
    x0, x1 = BX
    y0, y1 = BY
    if lod >= 2:
        return G.rect(x0, x1, y0, y1)
    c, g, gd = 0.006, (y0 + 0.030, y0 + 0.040), 0.002
    pts = [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c)]
    if lod == 0:
        pts += [(x1, g[0]), (x1 - gd, g[0]), (x1 - gd, g[1]), (x1, g[1])]
    pts += [(x1, y1 - 0.003), (x1 - 0.003, y1), (x0 + 0.003, y1), (x0, y1 - 0.003)]
    if lod == 0:
        pts += [(x0, g[1]), (x0 + gd, g[1]), (x0 + gd, g[0]), (x0, g[0])]
    pts += [(x0, y0 + c)]
    return pts


def _body(P, spec, lod):
    zb, zt = -h2(spec) + BODY_Z0, strip_top(spec)
    G.prism(P["body"], F_up(), _profile(lod), zb + CAP_T, zt - CAP_T, DARK)
    for z0, z1 in ((zb, zb + CAP_T), (zt - CAP_T, zt)):           # end caps, 1.5 mm proud all round
        e = 0.0015
        G.prism(P["dark"], F_up(), oct_pts(BX[0] - e, BY[0] - e, BX[1] + e, BY[1] + e, 0.007 if lod <= 1 else 0.0),
                z0, z1, DARK)
        if lod == 0:   # two cap screws on the front
            for x in (BX[0] + 0.012, BX[1] - 0.012):
                G.cylinder(P["hw"], (x, BY[0] - e, (z0 + z1) / 2), (x, BY[0] - e - 0.0012, (z0 + z1) / 2), 0.0028, 6,
                           HARDWARE)


FACEPLATE_T = 0.0015       # the Colorable face plate's thickness on the body's front (_faceplate)


def feed_band_outline(lod):
    """The feed tag band's plan outline (strip-local x, y): 1.5 mm proud of the body on the sides and the back, and
    1.5 mm proud of the face plate on the front. In game 2026-10-20 the band stood only 1.5 mm off the body's front,
    exactly as proud as the face plate: its front face lay in the plate's plane and the Yellow band flickered
    through the Colorable plate (only its side wraps showed, as loose yellow tabs by the cords)."""
    e = 0.0015
    return oct_pts(BX[0] - e, BY[0] - FACEPLATE_T - e, BX[1] + e, BY[1] + e, 0.007 if lod <= 1 else 0.0)


def _faceplate(P, spec, lod):
    """The Colorable face plate on the body's front (the player's paint; the Darker outlets, bank heads and tags
    stand on it), one plate per bank of BANK slots with a shadow gap between banks."""
    if lod >= 2:
        return
    F = F_rear(FACE_Y)
    z0 = -h2(spec) + BODY_Z0 + CAP_T + 0.004
    z1 = strip_top(spec) - CAP_T - 0.004
    cuts = [slot_z(spec, k) - 0.03 for _, k in banks(spec)[1:]] if lod == 0 else []
    edges = [z0] + [c for c in cuts for _ in (0, 1)] + [z1]
    for a, b in zip(edges[0::2], edges[1::2]):
        g0 = 0.0015 if a != z0 else 0.0
        g1 = 0.0015 if b != z1 else 0.0
        G.prism(P["chan"], F, oct_pts(BX[0] + 0.005, a + g0, BX[1] - 0.005, b - g1, 0.004 if lod == 0 else 0.0), 0.0,
                FACEPLATE_T, PAINT)


def _outlet(P, spec, x, z, lod):
    """A locking outlet (Darker housing 5 mm proud of the face, socket face at dims.PDU_OUTLET_FACE_Y) with its
    plugged jumper: a Rubber plug body, the MetalDull lock-release latch on top, the strain-relief boot."""
    w, h = DM.PDU_OUTLET_SIZE
    F = F_rear(FACE_Y)
    sf = FACE_Y - 0.006                                            # the socket face (where the plug seats)
    if lod >= 2:   # (far: the outlets are one Darker column, _cords)
        return
    if lod == 1:
        G.box(P["dark"], (x - w / 2, sf, z - h / 2), (x + w / 2, FACE_Y, z + h / 2), DARK)
        G.box(P["cord"], (x - 0.012, sf - 0.022, z - 0.010), (x + 0.012, sf, z + 0.010), RUBBER)
        return
    G.prism(P["dark"], F, oct_pts(x - w / 2, z - h / 2, x + w / 2, z + h / 2, 0.005), 0.0, 0.006, DARK)
    # the plug: body, latch, boot
    G.box(P["cord"], (x - 0.012, sf - 0.022, z - 0.010), (x + 0.012, sf, z + 0.010), RUBBER)
    if lod == 0:
        G.box(P["hw"], (x - 0.006, sf - 0.016, z + 0.010), (x + 0.006, sf - 0.004, z + 0.0125), HARDWARE)
    G.cylinder(P["cord"], (x, sf - 0.022, z), (x, sf - 0.031, z), 0.0068, 8 if lod == 0 else 6, RUBBER)


def _cord_paths(spec, k):
    """The two jumper cords of slot k: from the plug's boot down and across into the cord channel, then down the
    channel to their parked end under the slot's strap. [(path points, radius)]."""
    zr = slot_z(spec, k)
    zo = zr + DM.PDU_OUTLET_Z
    zs = strap_z(spec, k)
    sf = FACE_Y - 0.006 - 0.031                                    # the boot's end
    out = []
    for xo, yy, dz, lane in ((OX[0], -0.044, 0.0, LANES[0]), (OX[1], -0.056, 0.008, LANES[1])):
        ye = 0.024
        out.append([(xo, sf, zo), (xo, yy, zo - 0.004 - dz), (BX[0] - 0.002 + (xo - OX[0]) * 0.0, yy, zo - 0.030 - dz),
                    (lane, -0.020 - dz, zo - 0.050 - dz), (lane, ye, zo - 0.066 - dz), (lane, ye, zs - 0.004)])
    return out


def strap_z(spec, k):
    """The centre z of slot k's cord strap (just over the slot's floor; slot 1's clear of the strip's bottom)."""
    return max(slot_z(spec, k) - 0.008, -h2(spec) + 0.026)


def _cords(P, spec, lod):
    if lod >= 2:   # far: the parked cords as one Rubber bundle in the channel, the outlets one Darker column
        zt = strip_top(spec)
        G.box(P["cord"], (LANES[1] - CORD_R, CH_Y[0] + 0.012, -h2(spec) + 0.02), (LANES[0] + CORD_R, CH_Y[0] + 0.03,
                                                                                zt - 0.06), RUBBER)
        z0 = slot_z(spec, 1) + DM.PDU_OUTLET_Z - DM.PDU_OUTLET_SIZE[1] / 2
        z1 = slot_z(spec, nslots(spec)) + DM.PDU_OUTLET_Z + DM.PDU_OUTLET_SIZE[1] / 2
        G.box(P["dark"], (OX[0] - 0.018, FACE_Y - 0.02, z0), (OX[1] + 0.018, FACE_Y, z1), DARK)
        return
    for k in range(1, nslots(spec) + 1):
        for pts in _cord_paths(spec, k):
            if lod == 0:
                G.pipe_path(P["cord"], pts, CORD_R, 6, RUBBER, bend=0.012, bend_steps=3)
            else:   # LOD1: the drape from the plug into the channel as one straight run
                G.beam(P["cord"], pts[0], pts[4], 2 * CORD_R, 2 * CORD_R, RUBBER)


def _channel(P, spec, lod):
    """The Colorable cord channel (open toward the rear), its straps (Darker hook-and-loop bands with a MetalDull
    buckle) and the Brushed clips that hold it on the body."""
    x0, x1 = CH_X
    y0, y1 = CH_Y
    z0, z1 = -h2(spec) + 0.004, strip_top(spec) - 0.002
    ch = P["chan"]
    if lod >= 2:
        G.box(ch, (x0, y1 - CH_W, z0), (x1, y1, z1), PAINT)
        for xa, xb in ((x0, x0 + CH_W), (x1 - CH_W, x1)):
            G.box(ch, (xa, y0, z0), (xb, y1, z1), PAINT)
        return
    G.box(ch, (x0, y1 - CH_W, z0), (x1, y1, z1), PAINT)                         # back
    for xa, xb in ((x0, x0 + CH_W), (x1 - CH_W, x1)):
        G.box(ch, (xa, y0, z0), (xb, y1 - CH_W, z1), PAINT)                     # walls
    if lod == 0:
        for xa, xb in ((x0 + CH_W, x0 + CH_W + LIP), (x1 - CH_W - LIP, x1 - CH_W)):
            G.box(ch, (xa, y0, z0), (xb, y0 + 0.003, z1), PAINT)               # the mouth's lips
    for k in range(1, nslots(spec) + 1):
        zs = strap_z(spec, k)
        G.box(P["dark"], (x0 - 0.001, y0 - 0.003, zs - 0.012), (x1 + 0.001, y0, zs + 0.012), DARK)     # the strap
        for xa, xb in ((x0 - 0.001, x0), (x1, x1 + 0.001)) if lod == 0 else ():
            G.box(P["dark"], (xa, y0, zs - 0.012), (xb, y1, zs + 0.012), DARK)
        if lod == 0:
            xm = (x0 + x1) / 2
            G.box(P["hw"], (xm - 0.006, y0 - 0.0045, zs - 0.009), (xm + 0.006, y0 - 0.003, zs + 0.009), HARDWARE)
            G.box(P["steel"], (x1, y1 - 0.016, zs - 0.010), (BX[0], y1 - 0.006, zs + 0.010), STEEL)   # clip


def _inlet(P, spec, lod):
    """The supply: a gland in the bottom cap, the heavy inlet cord, the strain-relief boot and the twist-lock plug
    seated in the plinth receptacle (its bottom on the plinth-top plane: the "plug" part, build_report
    geometry.inlet_plug)."""
    zb = -h2(spec)
    n = 16 if lod == 0 else (10 if lod == 1 else 8)
    c = (XC, YR)
    G.cylinder(P["plug"], (c[0], c[1], zb), (c[0], c[1], zb + PLUG_H), PLUG_R, n, DARK)        # plug body
    if lod <= 1:
        G.cylinder(P["hw"], (c[0], c[1], zb + 0.005), (c[0], c[1], zb + 0.018), PLUG_R + 0.0018, n, HARDWARE)   # collar
        G.cylinder(P["cord"], (c[0], c[1], zb + BOOT[0]), (c[0], c[1], zb + BOOT[1]), 0.0115, n // 2 + 2, RUBBER)
    G.cylinder(P["cord"], (c[0], c[1], zb + BOOT[1] - 0.002), (c[0], c[1], zb + BODY_Z0 - 0.004), INLET_R, 8, RUBBER)
    if lod <= 1:
        G.cylinder(P["hw"], (c[0], c[1], zb + BODY_Z0 - 0.007), (c[0], c[1], zb + BODY_Z0), 0.0125, 6, HARDWARE)  # gland
    if lod == 0:   # the coupling ring's grip flats
        for k in range(6):
            a = 2 * math.pi * k / 6
            x, y = c[0] + (PLUG_R + 0.0018) * math.cos(a), c[1] + (PLUG_R + 0.0018) * math.sin(a)
            G.box(P["hw"], (x - 0.002, y - 0.002, zb + 0.007), (x + 0.002, y + 0.002, zb + 0.016), HARDWARE)


def _brackets(P, spec, lod):
    """The Brushed standoff brackets on the body's back, each with a button head in a bulkhead keyhole."""
    if lod >= 1:
        return
    for k in bracket_slots(spec):
        zc = slot_z(spec, k) + BTN_Z
        st = P["steel"]
        for xa in (XC - 0.019, XC + 0.0165):
            G.box(st, (xa, BY[1], zc - 0.024), (xa + 0.0025, BTN_Y - 0.0035, zc + 0.024), STEEL)          # webs
        G.box(st, (XC - 0.019, BTN_Y - 0.0065, zc - 0.024), (XC + 0.019, BTN_Y - 0.0035, zc + 0.024), STEEL)  # plate
        if lod == 0:
            G.cylinder(P["hw"], (XC, BTN_Y - 0.0035, zc), (XC, BTN_Y - 0.0012, zc), 0.004, 8, HARDWARE)     # stem
            G.cylinder(P["hw"], (XC, BTN_Y - 0.0012, zc), (XC, BTN_Y, zc), 0.0068, 8, HARDWARE)             # head
            for zz in (zc - 0.016, zc + 0.016):                                                              # rivets
                G.cylinder(P["hw"], (XC, BTN_Y - 0.0065, zz), (XC, BTN_Y - 0.0075, zz), 0.003, 6, HARDWARE)


def _bank_head(P, spec, k, lod):
    """A bank head over slot k's outlets: a Colorable bezel with the bank breaker (Darker body, MetalDull toggle, Yellow
    trip tab) and the ammeter window (its lit segments: _decor)."""
    z0, z1 = slot_z(spec, k) + HEAD_Z[0], slot_z(spec, k) + HEAD_Z[1]
    F = F_rear(FACE_Y)
    a0, a1 = BX[0] + 0.004, BX[1] - 0.004
    if lod >= 2:
        G.prism(P["chan"], F, G.rect(a0, a1, z0, z1), 0.0, 0.003, PAINT)
        return
    G.prism(P["chan"], F, oct_pts(a0, z0, a1, z1, 0.006), 0.0, 0.003, PAINT)                        # bezel
    bz = (z0 + 0.018, z0 + 0.074)
    G.prism(P["dark"], F, oct_pts(a0 + 0.005, bz[0], a0 + 0.031, bz[1], 0.003), 0.003, 0.011, DARK)  # breaker body
    zt = (bz[0] + bz[1]) / 2
    G.prism(P["hw"], F, G.rect(a0 + 0.013, a0 + 0.023, zt, zt + 0.019), 0.011, 0.019, HARDWARE)     # toggle (ON: up)
    G.prism(P["arrow"], F, G.rect(a0 + 0.010, a0 + 0.026, bz[0] + 0.003, bz[0] + 0.009), 0.011, 0.0135, YELLOW)  # trip
    G.prism(P["dark"], F, G.rect(a0 + 0.036, a1 - 0.004, bz[0] + 0.012, bz[1] - 0.010), 0.003, 0.004, DARK)  # window
    if lod == 0:   # the label strip (white stencils: _decor)
        G.prism(P["dark"], F, G.rect(a0 + 0.004, a1 - 0.004, z0 + 0.081, z0 + 0.095), 0.003, 0.0042, DARK)


def _feed_tag(P, spec, lod):
    """The feed tag: a band round the body (Feed A Yellow, Feed B the player's paint) and a Darker tag plate (its
    letter: _decor)."""
    k = tag_slot(spec)
    z0, z1 = slot_z(spec, k) + HEAD_Z[0], slot_z(spec, k) + HEAD_Z[1]
    mat, part = (YELLOW, "arrow") if strip_feed(spec) == "A" else (PAINT, "chan")
    zb = (z0 + 0.004, z0 + 0.030)
    G.prism(P[part], F_up(), feed_band_outline(lod), zb[0], zb[1], mat)
    if lod >= 2:
        return
    G.prism(P["dark"], F_rear(FACE_Y), oct_pts(BX[0] + 0.006, z0 + 0.038, BX[1] - 0.006, z1 - 0.004, 0.008), 0.0,
            0.004, DARK)


SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
       "8": "abcdefg", "9": "abcdfg", "-": "g"}


def lit_quad(p, F, a0, a1, b0, b1, d, mat=LAMP_GREEN):
    """One lit quad on face F at depth d, wound to face out along F's normal (p is a decal-style Part)."""
    f = p.bm.faces.new([p.bm.verts.new(F(a, b, d)) for a, b in G.rect(a0, a1, b0, b1)])
    f.material_index = p.mi(mat)
    return f


def seven_seg(p, F, a, b, h, text, d, mat=LAMP_GREEN, dp=None):
    """Lit seven-segment digits (one quad per segment, mat; p is a decal-style Part) on face F: left edge a, centre b,
    digit height h; dp = the index of the digit after which a decimal point is lit. Returns the width."""
    w, t = 0.52 * h, 0.13 * h
    pitch = w + 0.22 * h
    for i, ch in enumerate(text):
        x = a + i * pitch
        e = 0.06 * t                     # the hairline between two segments
        R = {"a": (x + t + e, x + w - t - e, b + h / 2 - t, b + h / 2),
             "d": (x + t + e, x + w - t - e, b - h / 2, b - h / 2 + t),
             "g": (x + t + e, x + w - t - e, b - t / 2, b + t / 2),
             "f": (x, x + t, b + e, b + h / 2 - e), "b": (x + w - t, x + w, b + e, b + h / 2 - e),
             "e": (x, x + t, b - h / 2 + e, b - e), "c": (x + w - t, x + w, b - h / 2 + e, b - e)}
        for sg in SEG.get(ch, ""):
            lit_quad(p, F, *R[sg], d, mat)
        if dp is not None and i == dp:
            lit_quad(p, F, x + w + 0.06 * h, x + w + 0.06 * h + t, b - h / 2, b - h / 2 + t, d, mat)
    return pitch * len(text)


def _decor(P, spec, lod):
    """What must read correctly from the hot aisle, built AFTER Feed B's mirror (text and digits are never mirrored):
    the slot numbers, the bank labels and ammeter digits, the feed letter."""
    if lod >= 2:
        return
    sx = strip_sx(spec)
    F = F_rear(FACE_Y)
    bx0, bx1 = sorted((sx * BX[0], sx * BX[1]))
    outer = bx1 - 0.0145 if sx > 0 else bx0 + 0.0145      # near the body's outer edge (clear of the cords)
    for k in range(1, nslots(spec) + 1):
        zn = slot_z(spec, k) + (0.074 if k == 1 else 0.045)
        if lod == 0:   # the slot number on a Darker tab (it reads on any paint), the rack's slot numbering
            G.prism(P["dark"], F, oct_pts(outer - 0.009, zn - 0.010, outer + 0.009, zn + 0.010, 0.003), 0.0015, 0.0025,
                    DARK)
            stencil(P["decal"], F, outer, zn, 0.012, str(k), d=0.001)
        for x in OX:   # the outlets' lit "on" LEDs (a metered PDU's per-outlet status)
            xl = sx * x
            zl = slot_z(spec, k) + DM.PDU_OUTLET_Z + DM.PDU_OUTLET_SIZE[1] / 2 + 0.006
            # 0.6 mm proud of the face plate (at 0.1 mm the LED and the plate fought: dc/zfight.py coplanar rule)
            lit_quad(P["lamp"], F, xl - 0.0035, xl + 0.0035, zl - 0.002, zl + 0.002, FACEPLATE_T + 0.0006)
    for b, k in banks(spec):
        z0 = slot_z(spec, k) + HEAD_Z[0]
        a0, a1 = sorted((sx * (BX[0] + 0.004), sx * (BX[1] - 0.004)))
        # the ammeter window spans a0 + 0.036 .. a1 - 0.004 in Feed A's x: mirrored for B
        wa0, wa1 = sorted((sx * (BX[0] + 0.040), sx * (BX[1] - 0.008)))
        h = 0.016
        wd = (0.52 * h + 0.22 * h) * 3
        seven_seg(P["lamp"], F, (wa0 + wa1) / 2 - wd / 2 + 0.002, z0 + 0.046, h, AMPS.get(b, "120"), 0.0045,
                  dp=1 if lod == 0 else None)
        if lod == 0:   # on the bank head's label strip (its face 4.2 mm proud; the glyphs 0.6 mm over it, z-fight)
            stencil(P["decal"], F, (wa0 + wa1) / 2, z0 + 0.088, 0.009, f"BANK {b}", d=0.0028)
            stencil(P["decal"], F, sx * (BX[0] + 0.022), z0 + 0.088, 0.008, "16A", d=0.0028)
    k = tag_slot(spec)
    z0, z1 = slot_z(spec, k) + HEAD_Z[0], slot_z(spec, k) + HEAD_Z[1]
    cx = sx * (BX[0] + BX[1]) / 2
    stencil(P["decal"], F, cx, (z0 + 0.038 + z1 - 0.004) / 2 + 0.008, 0.036, strip_feed(spec), d=0.004)
    if lod == 0:
        stencil(P["decal"], F, cx, z0 + 0.046, 0.0085, "FEED", d=0.004)


def strip_last_lod(spec):
    sx = strip_sx(spec)
    p = Part("lastlod")
    x0, x1 = sorted((sx * ENV_X[0], sx * BX[1]))
    G.box(p, (x0, BY[0] - 0.006, -h2(spec)), (x1, BY[1], strip_top(spec)), f"{spec.name}_LastLOD")
    return [p]


def build_strip(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the 12-tri box."""
    if lod == n_lods(spec) - 1:
        return strip_last_lod(spec)
    P = {k: Part(k) for k in ("body", "dark", "chan", "cord", "plug", "hw", "steel", "arrow", "lamp", "decal")}
    P["decal"].decal = True
    P["lamp"].decal = True
    if lod == 0:
        P["body"].bevel = (0.0015, 1)
        P["chan"].bevel = (0.0008, 1)
    _body(P, spec, lod)
    _faceplate(P, spec, lod)
    _inlet(P, spec, lod)
    _channel(P, spec, lod)
    _brackets(P, spec, lod)
    for k in range(1, nslots(spec) + 1):
        for x in OX:
            _outlet(P, spec, x, slot_z(spec, k) + DM.PDU_OUTLET_Z, lod)
    _cords(P, spec, lod)
    for _, k in banks(spec):
        _bank_head(P, spec, k, lod)
    _feed_tag(P, spec, lod)
    if strip_sx(spec) < 0:   # Feed B: the mirror image (normals are recomputed at export; decals come after)
        m = Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
        for p in P.values():
            if not p.empty():
                p.bm.transform(m)
                _reverse(p)
    _decor(P, spec, lod)
    return [p for p in P.values() if not p.empty()]


def _reverse(p):
    import bmesh
    bmesh.ops.reverse_faces(p.bm, faces=p.bm.faces[:])


# ============================================================================================== the cabinet
W2, D2 = 0.5, 0.625
H, ZT = 2.5, 2.25          # the rack's frame (dims.rack_frame(10)): ZT = the top band's floor
COVER_Y = (0.548, 0.562)   # the front cover plates (|y|): 36 mm behind the posts' faces (room for handle, breakers)
BACK_Y = (0.530, 0.548)    # the Darker chassis face behind them
A_IN = 0.418               # |a| the front / rear plates span between the corner posts (inner faces at 0.4225)
# the front, local z (0 = floor; the panelboard layout of the v1 06d mockup): the meter on top, the hinged breaker
# cover with two columns of 12 (odd circuits left, even right, as a real panelboard), the isolator and the DANGER
# placard at working height, a foot strip over the plinth
METER_Z = (1.84, 2.21)
BRK_Z = (0.80, 1.80)       # the hinged breaker cover
ISO_Z = (0.36, 0.78)       # the isolator + placard panel
PANEL_JOINT_Z = (ISO_Z[1] + BRK_Z[0]) / 2   # 0.79: the shadow gap between them (the body's fracture joint)
N_BRK = 12                 # per column
BRK_PITCH = 0.072          # breaker pitch (z)
BRK_Z0 = 0.863             # the bottom breaker's foot
COLS = (-0.125, 0.125)     # the columns' centres (a: + = the viewer's right); odd circuits in the left one
BRK_HW, BRK_HH = 0.075, 0.027   # a breaker body's half width / height
WIN_A, WIN_Z = 0.085, (BRK_Z0 - 0.008, BRK_Z0 + N_BRK * BRK_PITCH + 0.008)   # the cover's windows
LOAD = (("L1", "212", 8), ("L2", "198", 7), ("L3", "205", 8))   # the meter rows: label, amps, lit bar segments
ISO_C = (-0.20, 0.57)      # the isolator's centre (a, z) on the front face
PLACARD_C = (0.19, 0.60)   # the DANGER placard's centre


def breaker_zs():
    """Local z of the 12 breaker centres in a column, bottom up."""
    return [BRK_Z0 + BRK_PITCH * (k + 0.5) for k in range(N_BRK)]


def cabinet_dims(spec):
    """The rack.dims-shaped dict the reused rack builders read (plinth, corners, containment rail)."""
    return {"H": H, "ZT": ZT, "tray": True, "nslots": 8, "doors": (), "spec": spec, "lamp": LAMP_GREEN}


def cabinet_collision(spec):
    """As the full rack, closed: physics = plinth, body, top band (3 boxes, the rack's split planes); no occupancy
    hints (the boxes fill every cell). Mount hints: the rack's flush ones only, so it couples like a rack: the outer
    sides, the plinth bottom, the top rim (a Drop's landing and a rack label), the containment rail band (the roof
    panels); the front and back openings never mount (KEEP_OUT)."""
    e = 0.002
    reg = [("plinth", (-W2, -D2, 0.0), (W2, D2, 0.25 - e)), ("body", (-W2, -D2, 0.25 - e), (W2, D2, ZT + e)),
           ("top", (-W2, -D2, ZT + e), (W2, D2, H))]
    from . import rack
    YK, IX, IY = rack.YK, rack.IX, rack.IY
    t = 0.005
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


def _sides(P, lod):
    """The side skins between the corner posts: two Colorable panels split by a shadow gap at mid height, bolted,
    over a Darker liner (the gap reads dark)."""
    from . import rack
    for sx in (-1, 1):
        F = rack.F_side(sx)
        b1 = rack.YK - rack.POST - 0.004
        xl = sorted((sx * (W2 - rack.SKIN - 0.012), sx * (W2 - rack.SKIN - 0.024)))
        G.box(P["dark"], (xl[0], -b1, 0.26), (xl[1], b1, ZT - 0.01), DARK)
        zs = (0.26 + ZT - 0.01) / 2
        g = 0.008 if lod <= 1 else 0.0
        for z0, z1 in ((0.27, zs - g), (zs + g, ZT - 0.02)):
            G.prism(P["frame"], F, oct_pts(-b1, z0, b1, z1, 0.03 if lod <= 1 else 0.0), -0.012, 0.0, PAINT)
            if lod == 0:
                for bb in (-b1 + 0.03, b1 - 0.03):
                    for zz in (z0 + 0.04, z1 - 0.04):
                        bolt(P["hw"], F, bb, zz, 0.0)


def _front(P, lod):
    """The front: the Darker chassis face and the Colorable cover plates (the meter panel, the hinged breaker cover
    with its two column windows, the isolator panel, the foot strip), split by shadow gaps; the hinged cover's Brushed
    hinge knuckles and its key lock. The items in the openings: _meter, _breakers, _isolator."""
    from . import rack
    y0, y1 = COVER_Y
    Fc = rack.F_front(y1)                                    # the cover's face (a = -x: the viewer's right)
    G.box(P["dark"], (-A_IN, BACK_Y[0], 0.27), (A_IN, BACK_Y[1], ZT - 0.01), DARK)
    if lod >= 2:
        G.prism(P["frame"], Fc, G.rect(-A_IN, A_IN, 0.27, ZT - 0.02), -(y1 - y0), 0.0, PAINT)
        return
    gap = rack.SHADOW_GAP / 2
    mw = G.rect(-0.31, 0.31, METER_Z[0] + 0.035, METER_Z[1] - 0.035)
    G.plate(P["frame"], Fc, oct_pts(-A_IN, METER_Z[0] + gap, A_IN, METER_Z[1], 0.02), [mw], -(y1 - y0), 0.0, PAINT)
    holes = [G.rect(c - WIN_A, c + WIN_A, WIN_Z[0], WIN_Z[1]) for c in COLS]
    G.plate(P["cover"], Fc, oct_pts(-A_IN + 0.012, BRK_Z[0] + gap, A_IN - 0.012, BRK_Z[1] - gap, 0.02), holes,
            -(y1 - y0), 0.0, PAINT)
    G.prism(P["frame"], Fc, oct_pts(-A_IN, ISO_Z[0] + gap, A_IN, ISO_Z[1] - gap, 0.02), -(y1 - y0), 0.0, PAINT)
    G.prism(P["frame"], Fc, oct_pts(-A_IN, 0.27, A_IN, ISO_Z[0] - gap, 0.015), -(y1 - y0), 0.0, PAINT)
    if lod == 0:   # the cover's hinge knuckles on its left edge, the key lock and pull on its right
        for z in (BRK_Z[0] + 0.12, (BRK_Z[0] + BRK_Z[1]) / 2, BRK_Z[1] - 0.12):
            G.cylinder(P["steel"], Fc(-A_IN + 0.006, z - 0.045, 0.004), Fc(-A_IN + 0.006, z + 0.045, 0.004), 0.008, 8,
                       STEEL)
        a = A_IN - 0.045
        zc = (BRK_Z[0] + BRK_Z[1]) / 2
        G.cylinder(P["hw"], Fc(a, zc, 0.0), Fc(a, zc, 0.007), 0.016, 12, HARDWARE)                 # lock barrel
        G.prism(P["dark"], Fc, G.rect(a - 0.0025, a + 0.0025, zc - 0.010, zc + 0.010), 0.007, 0.0075, DARK)  # keyway
        G.prism(P["hw"], Fc, oct_pts(a - 0.010, zc - 0.095, a + 0.010, zc - 0.035, 0.004), 0.0, 0.010, HARDWARE)  # pull


def _meter(P, lod):
    """The meter window: a Darker bezel and screen, a row per phase (white L1 / L2 / L3, lit 3-digit amps, a lit bar
    graph of ten segments), the window's caption."""
    from . import rack
    Fc = rack.F_front(COVER_Y[1])
    z0, z1 = METER_Z[0] + 0.035, METER_Z[1] - 0.035
    G.ring(P["dark"], Fc, G.rect(-0.315, 0.315, z0 - 0.005, z1 + 0.005), G.rect(-0.30, 0.30, z0 + 0.008, z1 - 0.008),
           -0.010, 0.004, DARK)                                                                    # bezel
    G.prism(P["dark"], Fc, G.rect(-0.30, 0.30, z0 + 0.008, z1 - 0.008), -0.012, -0.008, DARK)    # the screen
    if lod >= 2:
        return
    rows = [(z0 + z1) / 2 + 0.072 * (1 - i) for i in range(3)]
    for (lab, amps, bars), zr in zip(LOAD, rows):
        stencil(P["decal"], Fc, -0.255, zr, 0.024, lab, d=-0.0094)
        seven_seg(P["lamp"], Fc, -0.205, zr, 0.036, amps, -0.0076)
        if lod == 0:
            stencil(P["decal"], Fc, -0.105, zr - 0.010, 0.014, "A", d=-0.0094)
        if lod == 0:   # the bar graph: ten segments, the lit ones green, the rest dark grey
            for k in range(10):
                a = 0.026 * k
                lit_quad(P["lamp"], Fc, a, a + 0.020, zr - 0.013, zr + 0.013, -0.0076,
                         LAMP_GREEN if k < bars else HARDWARE)
        else:
            lit_quad(P["lamp"], Fc, 0.0, 0.026 * bars - 0.006, zr - 0.013, zr + 0.013, -0.0076)
    if lod == 0:   # captions on a Darker strip over the window
        zc = METER_Z[1] - 0.018
        G.prism(P["dark"], Fc, oct_pts(-0.32, zc - 0.012, 0.32, zc + 0.012, 0.006), 0.0, 0.0015, DARK)
        stencil(P["decal"], Fc, -0.20, zc, 0.013, "INCOMER LOAD", d=0.0)
        stencil(P["decal"], Fc, 0.20, zc, 0.013, "400 V 3 PH  50 HZ", d=0.0)


def _isolator(P, lod):
    """The rotary isolator: a Yellow escutcheon on the cover, a Darker hub and bar handle (at ON: vertical), ON / OFF
    tabs, a padlock hasp (lock-off for maintenance); and the DANGER 400 V placard beside it."""
    from . import rack
    Fc = rack.F_front(COVER_Y[1])
    a, z = ISO_C
    G.prism(P["arrow"], Fc, oct_pts(a - 0.13, z - 0.13, a + 0.13, z + 0.13, 0.025), 0.0, 0.004, YELLOW)   # escutcheon
    n = 16 if lod == 0 else 8
    G.cylinder(P["dark"], Fc(a, z, 0.004), Fc(a, z, 0.016), 0.042, n, DARK)                              # hub
    G.prism(P["dark"], Fc, oct_pts(a - 0.018, z - 0.105, a + 0.018, z + 0.105, 0.012), 0.016, 0.032, DARK)  # handle
    if lod >= 2:
        return
    G.cylinder(P["hw"], Fc(a, z, 0.032), Fc(a, z, 0.034), 0.011, 8, HARDWARE)                             # centre cap
    G.prism(P["hw"], Fc, G.rect(a - 0.004, a + 0.004, z + 0.06, z + 0.095), 0.032, 0.0335, HARDWARE)   # pointer
    # ON / OFF tabs (Darker, white text) at 12 and 9 o'clock (a = -x on this face: the viewer's right is +a)
    for ta, tz, txt in ((a, z + 0.118, "ON"), (a - 0.118, z, "OFF")):
        G.prism(P["dark"], Fc, oct_pts(ta - 0.024, tz - 0.011, ta + 0.024, tz + 0.011, 0.004), 0.004, 0.0055, DARK)
        if lod == 0:
            stencil(P["decal"], Fc, ta, tz, 0.012, txt, d=0.004)
    if lod == 0:   # the padlock hasp at 4 o'clock: a MetalDull tongue through the escutcheon
        G.prism(P["hw"], Fc, oct_pts(a + 0.070, z - 0.095, a + 0.098, z - 0.050, 0.006), 0.004, 0.012, HARDWARE)
        G.prism(P["dark"], Fc, G.rect(a + 0.078, a + 0.090, z - 0.086, z - 0.074), 0.012, 0.0125, DARK)
    # the placard: Darker plate, the vanilla DANGER HIGH VOLTAGE sticker, the 400 V caption
    pa, pz = PLACARD_C
    G.prism(P["dark"], Fc, oct_pts(pa - 0.125, pz - 0.16, pa + 0.125, pz + 0.10, 0.012), 0.0, 0.002, DARK)
    from se2model import decals as DCL
    DCL.element(P["sticker"], Fc, pa, pz + 0.01, 0.22, S2, "danger_hv", d=0.002 - 0.0015)
    stencil(P["decal"], Fc, pa, pz - 0.105, 0.030, "400 V", d=0.0005)
    if lod == 0:
        stencil(P["decal"], Fc, pa, pz - 0.140, 0.0115, "ISOLATE BEFORE OPENING", d=0.0005)


def _breakers(P, lod):
    """The panelboard: two columns of 12 branch breakers behind the cover's windows, on a Brushed busbar: Darker
    bodies standing 12 mm proud of the cover, a Brushed toggle thrown toward the column's middle (ON), a Yellow trip
    tab at the outer end; the circuit numbers on a Darker strip outside each column (odd left, even right), the
    cover's captions."""
    from . import rack
    Fb = rack.F_front(COVER_Y[1])
    zs = breaker_zs()
    bk = P["breaker"]     # the breakers themselves (installed last: fracture.ROLES hide); the busbar and strips stay
    for ci, c in enumerate(COLS):
        out = -1 if c < 0 else 1                                  # toward the column's outer side (a)
        if lod >= 2:
            G.prism(bk, Fb, G.rect(c - WIN_A + 0.01, c + WIN_A - 0.01, WIN_Z[0] + 0.01, WIN_Z[1] - 0.01),
                    -0.014, 0.010, DARK)
            continue
        G.prism(P["steel"], Fb, G.rect(c - 0.022, c + 0.022, WIN_Z[0], WIN_Z[1]), -0.014, -0.011, STEEL)   # busbar
        ta = sorted((c - out * 0.004, c - out * 0.036))           # the toggle, thrown inward
        tt = sorted((c + out * 0.044, c + out * 0.062))           # the trip tab
        if lod == 1:   # the column as one block: bodies, a toggle strip, a trip-tab strip
            G.prism(bk, Fb, G.rect(c - BRK_HW, c + BRK_HW, zs[0] - BRK_HH, zs[-1] + BRK_HH), -0.011, 0.012,
                    DARK)
            G.prism(bk, Fb, G.rect(ta[0], ta[1], zs[0] - 0.009, zs[-1] + 0.009), 0.012, 0.026, STEEL)
            G.prism(bk, Fb, G.rect(tt[0], tt[1], zs[0] - 0.012, zs[-1] + 0.012), 0.012, 0.016, YELLOW)
        else:
            for z in zs:
                G.prism(bk, Fb, oct_pts(c - BRK_HW, z - BRK_HH, c + BRK_HW, z + BRK_HH, 0.006), -0.011, 0.012,
                        DARK)
                G.prism(bk, Fb, G.rect(c - 0.044, c + 0.012, z - 0.013, z + 0.013) if out < 0 else
                        G.rect(c - 0.012, c + 0.044, z - 0.013, z + 0.013), 0.012, 0.0125, HARDWARE)   # toggle slot
                G.prism(bk, Fb, G.rect(ta[0], ta[1], z - 0.009, z + 0.009), 0.012, 0.026, STEEL)      # toggle
                G.prism(bk, Fb, G.rect(tt[0], tt[1], z - 0.012, z + 0.012), 0.012, 0.016, YELLOW)    # trip
        # the circuit-number strip outside the column
        la = sorted((c + out * (WIN_A + 0.008), c + out * (WIN_A + 0.050)))
        G.prism(P["dark"], Fb, G.rect(la[0], la[1], WIN_Z[0], WIN_Z[1]), 0.0, 0.002, DARK)
        if lod == 0:
            for k, z in enumerate(zs):
                n = 2 * (N_BRK - 1 - k) + 1 + ci                 # top down: 1 / 2 at the top, 23 / 24 at the foot
                stencil(P["decal"], Fb, (la[0] + la[1]) / 2, z, 0.018, str(n), d=0.0005)
    if lod <= 1:   # captions on Darker strips (white stencils read on any paint)
        for zc, h, txt, w in ((BRK_Z[1] - 0.026, 0.017, "BRANCH CIRCUITS 1-24", 0.15),
                              (BRK_Z[0] + 0.030, 0.012, "EACH 32 A - ONE PER RACK FEED", 0.15),
                              (0.315, 0.016, "PDU 1  FEED A / B", 0.12)):
            if lod == 1 and h < 0.015:
                continue
            G.prism(P["dark"], Fb, oct_pts(-w, zc - h * 0.85, w, zc + h * 0.85, 0.005), 0.0, 0.0015, DARK)
            stencil(P["decal"], Fb, 0.0, zc, h, txt, d=0.0)


REAR_SPLIT = 1.25          # the rear cover's two bolted panels part here (local z)
REAR_VENT = ((-0.30, 0.30), (0.42, 0.98))   # the lower panel's louvred vent (a, z)
GLAND_Z = (1.88, 2.16)     # the gland plates (local z) in the upper panel
GLAND_A = ((-0.36, -0.04), (0.04, 0.36))


def _rear(P, lod):
    """The rear (the hot aisle): the Darker chassis face, two bolted Colorable cover panels (lift-off, Brushed grab
    handles), the lower one with a louvred vent (the busbar and breaker heat out to the hot aisle), the upper one with
    two gland plates (cable glands with blanking plugs: the alternative bottom-rear entries, the incomer's larger),
    an ID plate."""
    from . import rack
    y0, y1 = COVER_Y
    Fr = rack.F_back(-y1)
    G.box(P["dark"], (-A_IN, -BACK_Y[1], 0.27), (A_IN, -BACK_Y[0], ZT - 0.01), DARK)
    if lod >= 2:
        G.prism(P["frame"], Fr, G.rect(-A_IN, A_IN, 0.27, ZT - 0.02), -(y1 - y0), 0.0, PAINT)
        return
    gap = rack.SHADOW_GAP / 2
    (va0, va1), (vz0, vz1) = REAR_VENT
    G.plate(P["frame"], Fr, oct_pts(-A_IN, 0.27, A_IN, REAR_SPLIT - gap, 0.02), [G.rect(va0, va1, vz0, vz1)],
            -(y1 - y0), 0.0, PAINT)
    rack.louvre_panel(P["fine"], Fr, va0, vz0, va1, vz1, 12, lod)
    holes = [G.rect(a0, a1, GLAND_Z[0], GLAND_Z[1]) for a0, a1 in GLAND_A]
    G.plate(P["frame"], Fr, oct_pts(-A_IN, REAR_SPLIT + gap, A_IN, ZT - 0.02, 0.02), holes, -(y1 - y0), 0.0, PAINT)
    for z0, z1 in ((0.27, REAR_SPLIT - gap), (REAR_SPLIT + gap, ZT - 0.02)):
        zc = (z0 + z1) / 2
        for a in (-0.33, 0.33) if lod == 0 else ():   # grab handles: two posts and a bar, 26 mm proud (keep-out)
            for zz in (zc - 0.07, zc + 0.07):
                G.prism(P["steel"], Fr, G.rect(a - 0.008, a + 0.008, zz - 0.008, zz + 0.008), 0.0, 0.016, STEEL)
            G.prism(P["steel"], Fr, oct_pts(a - 0.009, zc - 0.085, a + 0.009, zc + 0.085, 0.004), 0.016, 0.026, STEEL)
        if lod == 0:                     # the panel's fixing bolts
            for a in (-A_IN + 0.03, A_IN - 0.03):
                for zz in (z0 + 0.035, z1 - 0.035):
                    bolt(P["hw"], Fr, a, zz, 0.0)
    for gi, (a0, a1) in enumerate(GLAND_A):
        gz = GLAND_Z
        G.prism(P["dark"], Fr, oct_pts(a0 + 0.004, gz[0] + 0.004, a1 - 0.004, gz[1] - 0.004, 0.012), -0.012, 0.002, DARK)
        n = 2 if gi == 0 else 3
        for i in range(n):
            for j in range(2):
                ga = a0 + (a1 - a0) * (i + 0.5) / n
                gzc = gz[0] + (gz[1] - gz[0]) * (j + 0.5) / 2 - 0.012
                r = 0.034 if gi == 0 else 0.024
                G.cylinder(P["hw"], Fr(ga, gzc, 0.002), Fr(ga, gzc, 0.012), r, 6, HARDWARE)            # gland nut
                if lod == 0:
                    G.cylinder(P["dark"], Fr(ga, gzc, 0.012), Fr(ga, gzc, 0.020), r * 0.72, 12, DARK)  # blank plug
        if lod == 0:
            for aa in (a0 + 0.016, a1 - 0.016):
                for zz in (gz[0] + 0.016, gz[1] - 0.016):
                    bolt(P["hw"], Fr, aa, zz, 0.002, r=0.006)
            stencil(P["decal"], Fr, (a0 + a1) / 2, gz[1] - 0.026, 0.012, "ALT ENTRY" if gi else "INCOMER ALT",
                    d=0.002)
    if lod == 0:
        zl = REAR_SPLIT + 0.30
        G.prism(P["dark"], Fr, oct_pts(-0.25, zl - 0.04, 0.25, zl + 0.035, 0.01), 0.0, 0.0015, DARK)
        stencil(P["decal"], Fr, 0.0, zl + 0.010, 0.026, "PDU 1  REAR", d=0.0)
        stencil(P["decal"], Fr, 0.0, zl - 0.023, 0.012, "NO USER SERVICEABLE PARTS - ISOLATE AT FRONT", d=0.0)


def _top(P, lod):
    """The top band (ZT .. H): the rack's rim (flush, mounts), a Darker cable-entry trough with the rack's top-entry
    brush plates at dims.TOP_ENTRY (their sleeves into the trough floor: a Drop's waterfalls come in here), Brushed
    cable cleats, a front header with the label plate and power lamp, a louvred rear header, side skins."""
    from . import rack
    fr, dk, hw = P["frame"], P["dark"], P["hw"]
    IX, IY, YK, CAP = rack.IX, rack.IY, rack.YK, rack.CAP
    if lod >= 2:   # far: the band as a Colorable box round a Darker top, the brush fields as dark patches
        G.box(fr, (-rack.XO + 0.004, -YK, ZT), (rack.XO - 0.004, YK, H - 0.03), PAINT)
        G.ring(fr, F_up(), G.rect(-rack.XO + 0.004, rack.XO - 0.004, -YK, YK), G.rect(-IX, IX, -IY, IY), H - 0.03, H,
               PAINT)
        G.box(dk, (-IX, -IY, H - 0.03), (IX, IY, H - 0.026), DARK)
        (ex0, ex1), (ey0, ey1) = DM.TOP_ENTRY
        for sx in (-1, 1):
            rack._entry_fitting(P, sx, 1, (ex0, ex1, ey0, ey1), H, ZT + 0.05, lod, sleeve_front=False)
        return
    G.box(dk, (-0.47, -0.57, ZT), (0.47, 0.57, ZT + 0.05), DARK)                                 # trough floor
    a1 = W2 - CAP - 0.004
    for sy in (-1, 1):
        y0, y1 = sorted((sy * IY, sy * YK))
        G.box(fr, (-a1, y0, H - 0.03), (a1, y1, H), PAINT)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * IX, sx * (W2 - rack.SKIN)))
        G.box(fr, (x0, -(YK - CAP), H - 0.03), (x1, YK - CAP, H), PAINT)
        for sy in (-1, 1):
            xa, xb = sorted((sx * a1, sx * IX))
            ya, yb = sorted((sy * IY, sy * (YK - CAP)))
            G.box(fr, (xa, ya, H - 0.03), (xb, yb, H), PAINT)
    for sy in (-1, 1):
        y0, y1 = sorted((sy * IY, sy * (IY + 0.012)))
        G.box(dk, (-IX, y0, ZT + 0.014), (IX, y1, H - 0.03), DARK)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * IX, sx * (IX + 0.012)))
        G.box(dk, (x0, -IY, ZT + 0.014), (x1, IY, H - 0.03), DARK)
    (ex0, ex1), (ey0, ey1) = DM.TOP_ENTRY
    for sx in (-1, 1):
        rack._entry_fitting(P, sx, 1, (ex0, ex1, ey0, ey1), H, ZT + 0.05, lod, sleeve_front=False)
    if lod == 0:   # cable cleats across the trough floor (they clamp the incomer and branch cables)
        for yy in (-0.25, 0.0, 0.25):
            G.box(hw, (-IX + 0.05, yy - 0.012, ZT + 0.05), (IX - 0.05, yy + 0.012, ZT + 0.062), STEEL)
            if lod == 0:
                for xx in (-IX + 0.07, IX - 0.07):
                    bolt(hw, F_up().sub(0, 0, ZT + 0.062), xx, yy, 0.0, r=0.007)
    for F, front in ((rack.F_front(YK - 0.016), True), (rack.F_back(-YK + 0.016), False)):
        pts = oct_pts(-a1, ZT + 0.016, a1, H - 0.034, 0.03)
        if front or lod >= 2:
            G.prism(fr, F, pts, -0.013, 0.0, PAINT)
        else:
            G.plate(fr, F, pts, [G.rect(-0.26, 0.26, ZT + 0.06, H - 0.08)], -0.013, 0.0, PAINT)
            rack.louvre_panel(P["fine"], F, -0.26, ZT + 0.06, 0.26, H - 0.08, 6, lod)
        if front:
            zc = (ZT + H) / 2 - 0.012
            G.prism(P["dark"], F, oct_pts(-0.17, zc - 0.057, 0.17, zc + 0.057, 0.021), 0.0, 0.006, DARK)
            if lod <= 1:
                stencil(P["decal"], F, -0.012, zc, 0.06, "PDU 1", d=0.006)
                from .style import lamp
                lamp(P["hw"], F, 0.142, zc, 0.006, r=0.009, lod=lod, mat=LAMP_GREEN)
    for sx in (-1, 1):
        F = rack.F_side(sx)
        b1 = YK - CAP - 0.006
        G.prism(fr, F, oct_pts(-b1, ZT + 0.016, b1, H - 0.034, 0.03), -0.012, 0.0, PAINT)
        if lod == 0:
            for bb in (-b1 + 0.03, b1 - 0.03):
                bolt(hw, F, bb, (ZT + H) / 2 - 0.016, 0.0)


# ---------------------------------------------------------------------------------------------- the inside
# Broken interiors follow the game's own style (this replaces an earlier modelled panelboard: gear plate, uprights,
# isolator body and links, CTs, meter body, incomer, looms, PE bar). Behind
# the dead-front the body is a SOLID CORE whose faces are vanilla FracturedMaterial01 in the Fractured / Damaged
# models (the `core` part, fracture.CORE_PARTS; Darker in the NonFractured model, where the chassis faces and liners
# hide it): one block per body section, each standing clear of the body seams (x = 0, PANEL_JOINT_Z), so a dead
# section shows its neighbours' core faces (two seams crossing one solid leave its cut loops open at the crossing: no
# cap). In front of it, in the pocket behind the breaker cover, only the two parts a hole shows and a player
# recognises (local z, |x| inside the liners 0.470, |y| inside the chassis faces 0.530):
#   | part                           | purpose                                                                       |
#   | busbar riser (L1 / L2 / L3 / N | the incomer's three phases and neutral, up from the isolator gear (the lower  |
#   |   tinned bars on three Darker  |   core) to every breaker; the insulators hold them off the core's face        |
#   |   insulator blocks)            |                                                                               |
#   | breaker rows (per column a     | the 24 branch breakers' backs behind the cover's windows (their fronts are    |
#   |   Darker chassis pan and the   |   _breakers)                                                                  |
#   |   breakers' rear bodies)       |                                                                               |
# The core also fills the pocket under the bars (the isolator gear) and over them (the meter's gear), so no section's
# break opens onto a hollow (dc/interior.py cover, Tests/test_interior.py).
CORE_X = 0.468                              # |x|: 2 mm inside the side liners
CORE_Y = (-0.528, 0.378)                    # the core behind the pocket (2 mm inside the rear chassis face)
POCKET_Y = (0.378, 0.528)                   # the pocket behind the cover (2 mm inside the front chassis face)
POCKET_FILL_Y = (POCKET_Y[0] + 0.001, POCKET_Y[1])   # (1 mm off the core: touching boxes weld into one island)
CORE_SEAM_X = 0.004                         # |x| of the core blocks' faces at the x = 0 seam
CORE_SEAM_Z = (0.765, 0.81)                 # their faces under / over PANEL_JOINT_Z (the seam snaps within 15 mm)
CORE_Z = (0.262, ZT - 0.012)
POCKET_FILL_Z = (0.74, 1.98)                # the core fills the pocket below and above these
BUS_X = (-0.09, -0.03, 0.03, 0.09)          # L1, L2, L3, N (clear of the x = 0 seam)
BUS_Y = (0.394, 0.434)
BUS_Z = (POCKET_FILL_Z[0], 1.96)
INSUL_Z = (0.90, 1.38, 1.86)
PAN_Y = (0.452, 0.458)
REAR_BODY_Y = (0.458, 0.5295)               # the breakers' backs, up to the chassis face's back (0.530)


def _interior(P, lod):
    """The core and the pocket's parts (table above): LOD0 in full, LOD1 a body block per column, LOD2 the core."""
    if lod >= 3:
        return
    core = P["core"]
    for sx in (-1, 1):
        x0, x1 = sorted((sx * CORE_SEAM_X, sx * CORE_X))
        for z0, z1 in ((CORE_Z[0], CORE_SEAM_Z[0]), (CORE_SEAM_Z[1], CORE_Z[1])):
            G.box(core, (x0, CORE_Y[0], z0), (x1, CORE_Y[1], z1), DARK)
        G.box(core, (x0, POCKET_FILL_Y[0], CORE_Z[0]), (x1, POCKET_FILL_Y[1], POCKET_FILL_Z[0]), DARK)
        G.box(core, (x0, POCKET_FILL_Y[0], POCKET_FILL_Z[1]), (x1, POCKET_FILL_Y[1], CORE_Z[1]), DARK)
    if lod >= 2:
        return
    p = P["fine"]
    for z in INSUL_Z:      # busbar insulators on the core's face, the riser bars on them
        G.box(p, (-0.12, POCKET_Y[0], z - 0.028), (0.12, BUS_Y[0], z + 0.028), DARK)
    for x in BUS_X:
        G.box(P["steel"], (x - 0.005, BUS_Y[0], BUS_Z[0]), (x + 0.005, BUS_Y[1], BUS_Z[1]), STEEL)
    zs = breaker_zs()
    for c in COLS:
        x = -c                                                   # (COLS are in the front face's a = -x)
        G.box(p, (x - 0.10, PAN_Y[0], zs[0] - 0.05), (x + 0.10, PAN_Y[1], zs[-1] + 0.05), DARK)
        if lod == 0:
            for z in zs:
                G.box(p, (x - 0.046, REAR_BODY_Y[0], z - 0.026), (x + 0.046, REAR_BODY_Y[1], z + 0.026), DARK)
        else:
            G.box(p, (x - 0.046, REAR_BODY_Y[0], zs[0] - 0.026), (x + 0.046, REAR_BODY_Y[1], zs[-1] + 0.026), DARK)


def _cabinet_lod3(P):
    from . import rack
    XO, YK = rack.XO, rack.YK
    G.box(P["dark"], (-XO, -YK, 0.0), (XO, YK, 0.25), DARK)
    G.box(P["frame"], (-XO, -YK, ZT), (XO, YK, H), PAINT)
    G.box(P["frame"], (-XO, -COVER_Y[1], 0.25), (XO, COVER_Y[1], ZT), PAINT)
    G.box(P["arrow"], (ISO_C[0] - 0.13, COVER_Y[1], ISO_C[1] - 0.13), (ISO_C[0] + 0.13, COVER_Y[1] + 0.004,
                                                                         ISO_C[1] + 0.13), YELLOW)


def cabinet_last_lod(spec):
    from . import rack
    p = Part("lastlod")
    G.box(p, (-rack.XO, -D2, -H / 2), (rack.XO, D2, H / 2), f"{spec.name}_LastLOD")
    return [p]


def build_cabinet(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the 12-tri box."""
    if lod == n_lods(spec) - 1:
        return cabinet_last_lod(spec)
    from . import rack
    d = cabinet_dims(spec)
    P = {k: Part(k) for k in ("frame", "caps", "dark", "fine", "hw", "steel", "cover", "arrow", "lamp", "decal",
                              "sticker", "brush", "contain", "breaker", "core")}
    for k in ("decal", "sticker", "lamp"):
        P[k].decal = True
    if lod == 0:   # (the chunky Darker caps and plinth frame are bevelled; the small Darker detail is not: budget)
        P["frame"].bevel = (0.005, 1)
        P["cover"].bevel = (0.004, 1)
        P["caps"].bevel = (0.004, 1)
        P["contain"].bevel = (0.003, 1)
    if lod >= 3:
        _cabinet_lod3(P)
    else:
        rack._plinth({**P, "dark": P["caps"]}, d, lod)
        rack._corners({**P, "dark": P["caps"]}, d, lod)
        _sides(P, lod)
        _front(P, lod)
        _meter(P, lod)
        _isolator(P, lod)
        _breakers(P, lod)
        _rear(P, lod)
        _top(P, lod)
        _interior(P, lod)
        rack._contain_rail(P, d, lod, tag_lift=TAG_LIFT)   # the tag clear of its plate (z-fight)
    parts = [p for p in P.values() if not p.empty()]
    m = Matrix.Translation((0, 0, -H / 2))
    for p in parts:
        p.bm.transform(m)
        p.bm.normal_update()
    return parts


# ============================================================================================== shared
def size(spec):
    return tuple(CELL * c for c in spec.cells)


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


def build(spec, lod):
    return build_cabinet(spec, lod) if spec.family == "pdu_cabinet" else build_strip(spec, lod)


def collision(spec):
    return cabinet_collision(spec) if spec.family == "pdu_cabinet" else strip_collision(spec)
