"""Signs and labels: DC_Sign_Aisle, DC_Sign_AisleHang, DC_Sign_Rack, LCDNarrow50 clones.

Every sign is a real, editable vanilla LCD (the cloned LcdMultiPanel chain): the player types "AISLE 1 COLD" or
"RACK 1.01" in the terminal. Hot or cold is shown by the frame's PAINT (vanilla has no blue
material), so the frame is Colorable and the screen's surround is Darker. Surfaces: the
aisle signs' screens are 4:1, patched to 1024 x 256 with AspectRatio 4 (vanilla ControlSeat250 CustomDisplay04) and
their slot maps to vanilla's 4:1 off-screen material LCDScreen_Off_4.0; the rack label keeps LCDNarrow50's native
2:1 512 x 256 surface on vanilla LCDScreen_Off_2.0 (dc/functional.py SIGN_LCD).

Frame (Blender, metres, centred like every builder here): x along the sign, +Y = front = game Forward, z up.

  DC_Sign_Aisle      1.0 x 0.25 x 0.25 (cells 4, 1, 1). Mounts Backward only: on a wall, or on a containment door's
                     header fascia (dc/contain.py: the header band is exactly this cell, its threaded inserts at
                     x +-0.42, z +-0.075 take the back plate's four bolts).
  DC_Sign_AisleHang  1.0 x 0.25 x 0.5 (cells 4, 1, 2), double-faced, centred on y = 0. Mounts Up only: under a
                     cable-tray rod hanger (DC_TrayRods_*) turned 90 deg to the sign, so the hanger's two rods (its
                     y = +-ROD_S) land on the sign's two rod plates at x = +-ROD_S along the face (room.reference_room).
  DC_Sign_Rack       0.5 x 0.25 x 0.25 (cells 2, 1, 1). Mounts Down only: on a rack's top front (or back) edge,
                     between the Drop's two waterfall columns (dims.LABEL_X / LABEL_Y: the rack's label pads).

Part -> purpose (SE-ified: chunky Colorable frames, Darker surrounds, few big MetalDull fasteners):
  housing    Colorable box, 45 deg clipped corners       the display's enclosure (panel, backlight, driver board)
  bezel      Colorable frame proud of the housing,        protects the screen's edge; the corner bolts hold it
             4 MetalDull corner bolts                     (the screen is serviced from the front)
  liner      Darker sloped surround inside the bezel      shades the screen (contrast under hall lighting) and
                                                          seals the panel's edge against dust
  screen     the LCD surface (the cloned LcdMultiPanel's   what the player writes on
             MeshPartName), UV 0..1
  tab        Darker plate, white "AISLE" stencil          names the sign's kind when the screen is off / unpowered
  back plate Darker mounting plate, 4 flush bolts         (aisle sign) hangs the sign on the wall / door header: its
             at x +-0.42, z +-0.075                       bolts take the header's threaded inserts
  gland      Darker cable gland + MetalDull nut on the    (aisle sign) the display's power / data feed
             right end
  top rail   Darker capping channel along the top         (hanging sign) the "T-bar" header that carries the two
                                                          lifting lugs and closes the double-faced housing
  hangers    per rod: MetalDull rod plate (ROD_PLATE      (hanging sign) the rod hanger's coupler seats on the
             square), coupler nut, turnbuckle, Darker     plate; the turnbuckles level the sign across the aisle;
             lifting lug with a MetalDull pin             the lug and pin carry it
  body       Colorable wedge, face tilted 15 deg down     (rack label) a lectern: the face looks down to the aisle
                                                          (the label sits ~2.8 m up)
  foot       Darker plate, 2 MetalDull bolts              (rack label) bolts to the rack's top rim (label pad)
  service    Darker rear cover, 2 MetalDull screws        (rack label) the driver board's service hatch
  (rack label LOD0 is held to Keen's 4-material budget for a 0.43 m model: no stencil)

Mount faces: only the mounting face of each sign mounts (hints; every other face's parts stay > 20 mm off its
plane where the game's mount rays can reach them); the definitions also restrict MountPointGeneratorSettings to that
one direction (dc/integration.py sign_patch).

Fracture (panels split IN PLANE; vanilla LCDNarrow50: 2 zones, no critical):
the 1.0 m signs in 3 tiles along x (Keen's table: 3 at the measured ~0.95 m edge), the rack label in 2 halves
(dc/fracture.py _sign). The middle zone holds the screen's centre, so the LcdPanel dummy is SupportingFracture of it.
"""
import math
from dataclasses import dataclass
from typing import Tuple

from . import dims as DM

try:   # geometry needs Blender; the constants, collision() and screens() are plain Python (pytest imports them)
    from se2model import geom as G
    from se2model.geom import Face, Part
except ImportError:
    G = Face = Part = None
from .style import DARK, HARDWARE, PAINT, stencil

H2 = DM.CELL / 2                    # 0.125: the cell planes
HINT_T = 0.005                      # mount hint slab thickness
SCREEN_4 = "LCDScreen_Off_4"        # the 4:1 surface slot (vanilla LCDScreen_Off_4.0, fa0a1f34)
SCREEN_4_BACK = "LCDScreen_Off_4_Back"   # the hanging sign's back face (a second surface, same material)
SCREEN_2 = "LCDScreen_Off"          # the rack label's 2:1 slot (vanilla LCDScreen_Off_2.0, bd7f946b)
TAB_TEXT = "AISLE"
BOLT_R = 0.0065                     # the bezel's corner bolts (hex)

# ---- DC_Sign_Aisle
A_HW, A_HH, A_CLIP = 0.485, 0.122, 0.026     # housing / bezel outline: half width, half height, corner clip
A_BACK = (-H2 + 0.0005, -0.113)              # back plate y (its back face 0.5 mm inside the -Y plane)
A_BACK_HW, A_BACK_HH = 0.470, 0.112
A_HOUSE = (-0.113, -0.050)                   # housing y
A_BEZEL = (-0.050, -0.036)                   # bezel y (its face at -0.036)
A_SCREEN = (0.80, 0.20)                      # the 4:1 screen
A_WIN = (0.410, 0.110)                       # bezel window half sizes (10 mm Darker liner round the screen)
A_SCREEN_Y = -0.0495                         # the screen surface (13.5 mm behind the bezel face)
A_CAP = (0.451, 0.489, 0.124, 0.028)         # Darker end caps: |x| from .. to, half height, corner clip
A_CAP_Y = (-0.1125, -0.0335)                 # ... their y (2.5 mm proud of the bezel face)
A_TAB = (0.4135, 0.4475, 0.078)              # the AISLE tab: |x| from .. to (viewer's left, +x), half height
A_BOLTS_BACK = [(sx * 0.42, sz * 0.075) for sx in (-1, 1) for sz in (-1, 1)]   # = contain.py's header inserts
A_CORNER = (0.470, 0.088)                    # the end caps' bolts |x|, |z| (on the caps' faces)
A_VENTS = [(-0.30 + 0.12 * k) for k in range(6)]   # backlight vent slots on the top and bottom (x centres)

# ---- DC_Sign_AisleHang
H_HW = 0.470                                 # housing half width
H_Z = (-0.123, 0.073)                        # housing z (bottom 2 mm over the bottom plane, top under the hangers)
H_ZC = sum(H_Z) / 2                          # -0.025: the body's and the screens' centre height
H_HH = (H_Z[1] - H_Z[0]) / 2                 # 0.098
H_CLIP = 0.020
H_T = 0.022                                  # housing half thickness (|y|)
H_BEZEL = 0.034                              # the bezels' faces (|y|)
H_SCREEN = (0.64, 0.16)                      # the 4:1 screens
H_WIN = (0.328, 0.088)
H_SCREEN_Y = 0.0225                          # the screens' surface (|y|, 11.5 mm behind the bezel faces)
H_CAP = (0.449, 0.474, 0.0995, 0.022)        # Darker end caps: |x| from .. to, half height (about H_ZC), clip
H_TAB = (0.346, 0.438, 0.060)                # the AISLE tab: |x| from .. to (viewer's left on each face), half height
H_CORNER = (0.4615, 0.072)                   # the end caps' bolts |x|, |z - H_ZC|
H_RAIL = (H_Z[1], H_Z[1] + 0.007, 0.036)     # the top rail: z0, z1, half width across (|y|)
LUG = (0.012, 0.005, H_RAIL[1], H_RAIL[1] + 0.016)   # lifting lug: half x, half y, z0, z1
PIN_Z = H_RAIL[1] + 0.009
PLATE_T = 0.006                              # rod plate thickness (tray_plan.ROD_PLATE_T)
PLATE_TOP = H2 - 0.001                       # rod plate top: 1 mm under the top plane (as the tray's rod plates)
COUPLER_R = 0.0085                           # the coupler nut (hex), under the plate
TB = (PIN_Z + 0.008, PLATE_TOP - PLATE_T - 0.007)   # the turnbuckle body's z span

# ---- DC_Sign_Rack
R_TILT = 15.0                                # the face leans forward, looking 15 deg down
R_HW = 0.205                                 # body half width (between the end caps)
R_CAP = 0.219                                # the end caps' outer |x|
R_Z = (-0.116, 0.100)                        # body z (on the foot; top 25 mm under the top plane: no Up mount)
R_BACK_Y = -0.025                            # body back face
R_FACE_TOP_Y = 0.110                         # the face line's top (y at R_Z[1])
R_SCREEN = (0.34, 0.17)                      # the 2:1 screen (along the face)
R_WIN = (0.178, 0.093)
R_BEZEL_HW = 0.200                           # the bezel ring's half width (between the caps)
R_BEZEL_T = 0.010                            # the bezel ring, proud of the face
R_SCREEN_D = 0.0005                          # the screen, just off the face plane (9.5 mm behind the bezel)
R_FOOT = (0.210, -0.035, 0.090, -H2 + 0.0005, -0.116)   # half x, y0, y1, z0, z1: on the rack's top rim
R_FOOT_BOLTS = [(sx * 0.150, 0.073) for sx in (-1, 1)]

LOD_COUNT = {}                               # name -> LOD count fitted to the MEASURED LOD0 (assemble.fit_lods)


@dataclass(frozen=True)
class Screen:
    """An LCD surface: its mesh part (material slot), centre (Blender, block frame), size (w, h along the face) and
    the face's outward normal and up direction."""
    face: str
    center: Tuple[float, float, float]
    size: Tuple[float, float]
    slot: str = SCREEN_4
    normal: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    up: Tuple[float, float, float] = (0.0, 0.0, 1.0)


def size(spec):
    return (DM.CELL * spec.cells[0], DM.CELL * spec.cells[2], DM.CELL * spec.cells[1])


def n_lods(spec):
    if spec.name in LOD_COUNT:
        return LOD_COUNT[spec.name]
    from se2model import limits
    return limits.model_limits(size(spec))["optimal_lods"]


def _tilt():
    t = math.radians(R_TILT)
    return math.sin(t), math.cos(t)


def rack_face_y(z):
    """The rack label's face plane: y at height z (the top leans forward)."""
    s, c = _tilt()
    return R_FACE_TOP_Y - (R_Z[1] - z) * s / c


def screens(spec):
    """[Screen] of a sign: the 4:1 front of the aisle sign, both 4:1 faces of the hanging sign (front +Y, back -Y), the
    rack label's tilted 2:1 face."""
    v = spec.variant
    if v == "Aisle":
        return [Screen("front", (0.0, A_SCREEN_Y, 0.0), A_SCREEN, SCREEN_4)]
    if v == "AisleHang":
        return [Screen("front", (0.0, H_SCREEN_Y, H_ZC), H_SCREEN, SCREEN_4),
                Screen("back", (0.0, -H_SCREEN_Y, H_ZC), H_SCREEN, SCREEN_4_BACK, (0.0, -1.0, 0.0))]
    if v == "Rack":
        s, c = _tilt()
        zc = sum(R_Z) / 2
        y = rack_face_y(zc)
        n = (0.0, c, -s)
        p = (0.0, y + R_SCREEN_D * n[1], zc + R_SCREEN_D * n[2])
        return [Screen("front", tuple(round(q, 6) for q in p), R_SCREEN, SCREEN_2, n, (0.0, s, c))]
    raise ValueError(spec.name)


def mount_direction(spec):
    """The one face a sign mounts on (the definition's MountPointGeneratorSettings.Directions)."""
    return {"Aisle": "Backward", "AisleHang": "Up", "Rack": "Down"}[spec.variant]


def rod_plates(spec):
    """[(x, y, z_top, side)] of the hanging sign's rod plates (square, ROD_PLATE): on the top plane's 1 mm inset, at
    x = +-ROD_S on the sign's centre line (where a rod hanger turned 90 deg puts its two rods)."""
    if spec.variant != "AisleHang":
        return []
    return [(sx * DM.ROD_S, 0.0, PLATE_TOP, DM.ROD_PLATE) for sx in (-1, 1)]


def _hint_reach():
    """se2model.placement's ray ring (the rod hanger's own hint pattern, dc/tray.py _hint_reach): a hint reaching
    `reach` past a grid line catches the 4 nearest rays of the cell on that side; `keep` stays clear of the far one."""
    from se2model import placement as PL
    offs = sorted({round(abs(a), 6) for a, _ in PL.SAMPLES})
    return PL.CELL / 2 - offs[0] + 0.005, PL.CELL / 2 - offs[-1] - 0.025


def collision(spec):
    """{"regular", "occupancy", "mount"} (the rack.collision format; Blender frame, centred): one physics box round
    the sign, and the mount hints on its one mounting face only."""
    v = spec.variant
    t = HINT_T
    if v == "Aisle":
        reg = [("sign", (-A_HW, -H2 + 0.0005, -A_HH), (A_HW, A_BEZEL[1] + 0.003, A_HH))]
        mnt = [("back", (-A_BACK_HW, -H2, -A_BACK_HH), (A_BACK_HW, -H2 + t, A_BACK_HH))]
    elif v == "AisleHang":
        reg = [("sign", (-H_HW, -H_BEZEL - 0.002, H_Z[0]), (H_HW, H_BEZEL + 0.002, PLATE_TOP))]
        # the rod hanger's coupler hints (dc/tray.py _column_collision) turned into the sign's frame: each plate
        # mounts one cell (the diagonal pattern), so the hanger's Down cells and the sign's Up cells are the same
        reach, keep = _hint_reach()
        mnt = [("rod_m", (-(H2 * 2) + 0.001, -keep, H2 - t), (-0.04, reach, H2)),
               ("rod_p", (0.04, -reach, H2 - t), (H2 * 2 - 0.001, keep, H2))]
    elif v == "Rack":
        fx, fy0, fy1, fz0, _ = R_FOOT
        reg = [("sign", (-R_CAP, fy0, fz0), (R_CAP, R_FACE_TOP_Y + R_BEZEL_T + 0.003, R_Z[1] + 0.002))]
        mnt = [("foot", (-fx, fy0, -H2), (fx, fy1, -H2 + t))]
    else:
        raise ValueError(spec.name)
    return {"regular": reg, "occupancy": [], "mount": mnt}


def _rects(spec, plane_axis, plane_val):
    out = []
    for _, lo, hi in collision(spec)["mount"]:
        if abs((lo[plane_axis] if plane_val < 0 else hi[plane_axis]) - plane_val) < 1e-9 and \
                hi[plane_axis] - lo[plane_axis] <= HINT_T + 1e-9:
            a, b = [i for i in range(3) if i != plane_axis]
            out.append([lo[a], hi[a], lo[b], hi[b]])
    return out


def back_mount_rects(spec):
    """[[x0, x1, z0, z1]] of the mount hints on the -Y plane (the aisle sign's back plate)."""
    return _rects(spec, 1, -H2)


def up_mount_rects(spec):
    """[[x0, x1, y0, y1]] on the top plane (the hanging sign's rod plates)."""
    return _rects(spec, 2, H2)


def down_mount_rects(spec):
    """[[x0, x1, y0, y1]] on the bottom plane (the rack label's foot)."""
    return _rects(spec, 2, -H2)


# ---------------------------------------------------------------------------------------------------- geometry
def _front(y):
    """The face frame looking out +Y: a = viewer's right (-x), b = up, d = +y."""
    return Face((0.0, y, 0.0), (-1, 0, 0), (0, 0, 1))


def _back(y):
    """The face frame looking out -Y: a = viewer's right (+x), b = up, d = -y."""
    return Face((0.0, y, 0.0), (1, 0, 0), (0, 0, 1))


def _clip(hw, hh, c, bc=0.0):
    return [(a, b + bc) for a, b in G.clipped_rect(hw, hh, c)]


def frustum_ring(p, F, outer, inner0, inner1, d0, d1, mat):
    """A closed frame: the outer loop straight from d0 to d1, the inner loop going from inner0 (at d0) to inner1 (at
    d1): a sloped liner round a recessed screen. Loops have the same vertex count, counter-clockwise."""
    bm = p.bm
    O0 = [bm.verts.new(F(a, b, d0)) for a, b in outer]
    O1 = [bm.verts.new(F(a, b, d1)) for a, b in outer]
    I0 = [bm.verts.new(F(a, b, d0)) for a, b in inner0]
    I1 = [bm.verts.new(F(a, b, d1)) for a, b in inner1]
    mi = p.mi(mat)
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        for q in ((O1[i], O1[j], I1[j], I1[i]), (O0[j], O0[i], I0[i], I0[j]), (O0[i], O0[j], O1[j], O1[i]),
                  (I0[j], I0[i], I1[i], I1[j])):
            bm.faces.new(q).material_index = mi


def _screen(P, F, hw, hh, d, slot, bc=0.0):
    """The LCD surface: one open quad (UV 0..1, u to the viewer's right, v up) in the screen Part."""
    bm = P["screen"].bm
    uvl = bm.loops.layers.uv.verify()
    pts = [(-hw, -hh + bc), (hw, -hh + bc), (hw, hh + bc), (-hw, hh + bc)]
    f = bm.faces.new([bm.verts.new(F(a, b, d)) for a, b in pts])
    f.material_index = P["screen"].mi(slot)
    for loop, uv in zip(f.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        loop[uvl].uv = uv


def _hex(p, F, a, b, d0, d1, r=BOLT_R, mat=HARDWARE):
    G.cylinder(p, F(a, b, d0), F(a, b, d1), r, 6, mat)


def _cap_poly(sa, a0, hw, hh, c, bc=0.0):
    """The end of a clipped outline beyond |a| = a0 on side sa (counter-clockwise)."""
    pts = [(sa * a0, -hh), (sa * (hw - c), -hh), (sa * hw, -hh + c), (sa * hw, hh - c), (sa * (hw - c), hh),
           (sa * a0, hh)]
    pts = [(a, b + bc) for a, b in pts]
    return pts if sa > 0 else list(reversed(pts))


def _end_caps(P, F, cap, d0, d1, lod, bc=0.0):
    """Darker armoured end caps over both ends of a housing (Keen corner armour: the ends get knocked)."""
    a0, hw, hh, c = cap
    for sa in (-1, 1):
        G.prism(P["dark"], F, _cap_poly(sa, a0, hw, hh, c if lod < 2 else 0.0, bc), d0, d1, DARK)


def _bezel(P, F, outline, win, screen, d_house, d_face, slot, lod, bc=0.0, liner_back=None):
    """Bezel (Colorable ring proud of the housing), the Darker sloped liner inside its window, the screen quad."""
    wl = _clip(win[0], win[1], 0.004 if lod < 2 else 0.0, bc)
    sw, sh = screen[0] / 2, screen[1] / 2
    dl = liner_back if liner_back is not None else d_house
    if lod >= 2:
        G.ring(P["bezel"], F, outline, _clip(sw, sh, 0.0, bc), d_house, d_face, PAINT)
        _screen(P, F, sw, sh, dl + 0.0005, slot, bc)
        return
    G.ring(P["bezel"], F, outline, wl, d_house, d_face, PAINT)
    if lod == 0:   # sloped: from the screen's edge up to the window's (a 0.5 mm flat at the bezel face)
        frustum_ring(P["dark"], F, wl, _clip(sw, sh, 0.0015, bc), _clip(win[0] - 0.0005, win[1] - 0.0005, 0.0036, bc),
                     dl, d_face - 0.0005, DARK)
    else:
        G.ring(P["dark"], F, wl, _clip(sw, sh, 0.0015, bc), dl, d_face - 0.003, DARK)
    _screen(P, F, sw, sh, dl + 0.0005, slot, bc)


def _tab_stencil(P, F, a0, a1, hh, d, height, vertical, lod, bc=0.0):
    """The Darker AISLE tab (2 mm proud) and its white stencil."""
    G.prism(P["dark"], F, _clip((a1 - a0) / 2, hh, 0.006 if lod < 2 else 0.0, bc), d, d + 0.002, DARK,
            ca=(a0 + a1) / 2)
    if lod >= 2:
        return
    from se2model.config import DECAL_OFFSET
    ac = (a0 + a1) / 2
    if vertical:   # reading bottom to top (the glyphs' tops toward the viewer's left)
        Fv = Face(F(ac, bc, 0.0), F.v, -F.u)
        stencil(P["decal"], Fv, 0.0, 0.0, height, TAB_TEXT, d=d + 0.002 + 0.0004 - DECAL_OFFSET)
    else:
        stencil(P["decal"], F, ac, bc, height, TAB_TEXT, d=d + 0.002 + 0.0004 - DECAL_OFFSET)


# ---- DC_Sign_Aisle
def _aisle(P, spec, lod):
    Fb = _front(0.0)
    out = _clip(A_HW, A_HH, A_CLIP if lod < 2 else 0.0)
    if lod < 2:   # back plate (Darker) with its four flush bolts (the studs into the header's inserts)
        G.prism(P["dark"], Fb, _clip(A_BACK_HW, A_BACK_HH, 0.02), A_BACK[0], A_BACK[1], DARK)
    if lod == 0:
        Fk = _back(0.0)
        for x, z in A_BOLTS_BACK:
            _hex(P["hw"], Fk, x, z, -A_BACK[0] - 0.0011, -A_BACK[0] + 0.0002, r=0.008)
    # housing and bezel, the armoured end caps
    G.prism(P["body"], Fb, out, A_BACK[0] if lod >= 2 else A_HOUSE[0], A_HOUSE[1], PAINT)
    _bezel(P, Fb, out, A_WIN, A_SCREEN, A_BEZEL[0], A_BEZEL[1], SCREEN_4, lod, liner_back=A_SCREEN_Y - 0.0005)
    _end_caps(P, Fb, A_CAP, A_CAP_Y[0], A_CAP_Y[1], lod)
    # the AISLE tab on the viewer's left end (a < 0 = +x), vertical stencil
    _tab_stencil(P, Fb, -A_TAB[1], -A_TAB[0], A_TAB[2], A_BEZEL[1], 0.024, True, lod)
    if lod >= 2:
        return
    if lod == 0:
        for sa in (-1, 1):   # the caps' bolts (they clamp the bezel to the housing), on washers
            for sb in (-1, 1):
                _hex(P["hw"], Fb, sa * A_CORNER[0], sb * A_CORNER[1], A_CAP_Y[1] - 0.001, A_CAP_Y[1] + 0.004)
                G.cylinder(P["hw"], Fb(sa * A_CORNER[0], sb * A_CORNER[1], A_CAP_Y[1] - 0.001),
                           Fb(sa * A_CORNER[0], sb * A_CORNER[1], A_CAP_Y[1] + 0.0012), 0.0095, 12, HARDWARE)
        # the bezel gasket: a Darker seal between the housing and the bezel (a dark line round the frame)
        G.ring(P["dark"], Fb, _clip(A_HW + 0.0012, A_HH + 0.0012, A_CLIP + 0.0005), _clip(A_WIN[0] + 0.03,
               A_WIN[1] + 0.004, A_CLIP), A_BEZEL[0] - 0.0008, A_BEZEL[0] + 0.0008, DARK)
        # backlight vents: Darker louvre slots on the housing's top and bottom (hot air out, cool air in)
        for x in A_VENTS:
            for sz in (-1, 1):
                z0, z1 = sorted((sz * (A_HH - 0.0035), sz * (A_HH + 0.0015)))
                G.box(P["dark"], (x - 0.045, -0.100, z0), (x + 0.045, -0.088, z1), DARK)
                G.box(P["dark"], (x - 0.045, -0.078, z0), (x + 0.045, -0.066, z1), DARK)
    # the power / data gland through the right end cap (-x)
    Fe = Face((-A_CAP[1], (A_HOUSE[0] + A_HOUSE[1]) / 2, -0.060), (0, -1, 0), (0, 0, 1))   # normal -x
    G.cylinder(P["dark"], Fe(0, 0, -0.001), Fe(0, 0, 0.0045), 0.011, 8 if lod == 0 else 6, DARK)
    if lod == 0:
        G.cylinder(P["hw"], Fe(0, 0, 0.0045), Fe(0, 0, 0.0095), 0.0085, 6, HARDWARE)


# ---- DC_Sign_AisleHang
def _hang_face(P, F, lod):
    out = _clip(H_HW, H_HH, H_CLIP if lod < 2 else 0.0, H_ZC)
    _bezel(P, F, out, H_WIN, H_SCREEN, H_T, H_BEZEL, F.slot, lod, H_ZC, liner_back=H_SCREEN_Y - 0.0005)
    _tab_stencil(P, F, -H_TAB[1], -H_TAB[0], H_TAB[2], H_BEZEL, 0.026, False, lod, H_ZC)
    if lod == 0:
        for sa in (-1, 1):   # the end caps' bolts
            for sb in (-1, 1):
                _hex(P["hw"], F, sa * H_CORNER[0], H_ZC + sb * H_CORNER[1], H_BEZEL + 0.0005, H_BEZEL + 0.0055,
                     r=0.0055)
                G.cylinder(P["hw"], F(sa * H_CORNER[0], H_ZC + sb * H_CORNER[1], H_BEZEL + 0.0005),
                           F(sa * H_CORNER[0], H_ZC + sb * H_CORNER[1], H_BEZEL + 0.0025), 0.0085, 12, HARDWARE)


def _hanger(P, x, lod):
    """One rod's hanger: the rod plate under the top plane, the coupler nut, the turnbuckle (two threaded stubs, an
    open body with hex end bosses), the clevis on the lug's pin, the Darker lug on the top rail."""
    hw = P["hw"]
    s = DM.ROD_PLATE / 2
    G.box(hw, (x - s, -s, PLATE_TOP - PLATE_T), (x + s, s, PLATE_TOP), HARDWARE)                   # rod plate
    l0, l1 = LUG[2], LUG[3]
    G.box(P["dark"], (x - LUG[0], -LUG[1], l0 - 0.001), (x + LUG[0], LUG[1], l1), DARK)            # lifting lug
    if lod >= 1:
        G.box(hw, (x - 0.004, -0.004, l1), (x + 0.004, 0.004, PLATE_TOP - PLATE_T), HARDWARE)     # one rod
        return
    z_c = PLATE_TOP - PLATE_T
    G.cylinder(hw, (x, 0, z_c + 0.0005), (x, 0, z_c - 0.006), COUPLER_R, 6, HARDWARE)               # coupler nut
    G.cylinder(hw, (x, 0, z_c - 0.006), (x, 0, TB[1]), 0.0035, 8, HARDWARE)                          # upper stub
    for z0, z1 in ((TB[1] - 0.004, TB[1]), (TB[0], TB[0] + 0.004)):                                  # end bosses
        G.cylinder(hw, (x, 0, z0), (x, 0, z1), 0.0058, 6, HARDWARE)
    for sx in (-1, 1):                                                                                # open body
        G.box(hw, (x + sx * 0.0060 - 0.0016, -0.0024, TB[0] + 0.002), (x + sx * 0.0060 + 0.0016, 0.0024,
                                                                         TB[1] - 0.002), HARDWARE)
    G.cylinder(hw, (x, 0, TB[0]), (x, 0, PIN_Z + 0.004), 0.0035, 8, HARDWARE)                       # lower stub
    for sy in (-1, 1):                                                                                # clevis cheeks
        G.box(hw, (x - 0.006, sy * 0.0055 - 0.0012, PIN_Z - 0.006), (x + 0.006, sy * 0.0055 + 0.0012, PIN_Z + 0.005),
              HARDWARE)
    G.cylinder(hw, (x, -0.0085, PIN_Z), (x, 0.0085, PIN_Z), 0.0032, 8, HARDWARE)                    # pin


def _hang(P, spec, lod):
    Fb = _front(0.0)
    out = _clip(H_HW, H_HH, H_CLIP if lod < 2 else 0.0, H_ZC)
    G.prism(P["body"], Fb, out, -H_T, H_T, PAINT)                                   # the double-faced housing
    Ff, Fk = _front(0.0), _back(0.0)
    Ff.slot, Fk.slot = SCREEN_4, SCREEN_4_BACK
    _hang_face(P, Ff, lod)
    _hang_face(P, Fk, lod)
    _end_caps(P, Fb, H_CAP, -(H_BEZEL + 0.0015), H_BEZEL + 0.0015, lod, H_ZC)
    z0, z1, w = H_RAIL
    G.box(P["dark"], (-H_CAP[0], -w, z0 - 0.002), (H_CAP[0], w, z1), DARK)          # top rail (the T-bar header)
    for x, _, _, _ in rod_plates(spec):
        _hanger(P, x, lod)


# ---- DC_Sign_Rack
def _rack_face():
    s, c = _tilt()
    zc = sum(R_Z) / 2
    return Face((0.0, rack_face_y(zc), zc), (-1, 0, 0), (0, s, c))


def _offset(poly, d, keep=()):
    """A convex polygon [(y, z)] (counter-clockwise) grown outward by d, the edges in keep (index i = edge i..i+1)
    left in place."""
    n = len(poly)
    lines = []
    for i in range(n):
        (y0, z0), (y1, z1) = poly[i], poly[(i + 1) % n]
        ly = math.hypot(y1 - y0, z1 - z0)
        ny, nz = (z1 - z0) / ly, -(y1 - y0) / ly            # outward normal of a CCW polygon
        o = 0.0 if i in keep else d
        lines.append(((y0 + ny * o, z0 + nz * o), (y1 - y0, z1 - z0)))
    out = []
    for i in range(n):
        (p, u), (q, v) = lines[i - 1], lines[i]
        den = u[0] * v[1] - u[1] * v[0]
        t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
        out.append((p[0] + t * u[0], p[1] + t * u[1]))
    return out


def _rack_profile():
    yb, yt = rack_face_y(R_Z[0]), R_FACE_TOP_Y
    ch = 0.018
    return [(R_BACK_Y, R_Z[0]), (yb, R_Z[0]), (rack_face_y(R_Z[1] - 0.004), R_Z[1] - 0.004), (yt - 0.005, R_Z[1]),
            (R_BACK_Y + ch, R_Z[1]), (R_BACK_Y, R_Z[1] - ch)]


def _rack(P, spec, lod):
    s, c = _tilt()
    fx, fy0, fy1, fz0, fz1 = R_FOOT
    # the foot on the rack's rim, its two bolts in front of the body
    Fz = Face((0.0, 0.0, 0.0), (1, 0, 0), (0, 1, 0))
    k = 0.012 if lod < 2 else 0.0
    G.prism(P["dark"], Fz, [(-fx + k, fy0), (fx - k, fy0), (fx, fy0 + k), (fx, fy1 - k), (fx - k, fy1),
                            (-fx + k, fy1), (-fx, fy1 - k), (-fx, fy0 + k)], fz0, fz1, DARK)
    if lod == 0:
        for x, y in R_FOOT_BOLTS:
            G.cylinder(P["hw"], (x, y, fz1 - 0.001), (x, y, fz1 + 0.0055), 0.0075, 6, HARDWARE)
            G.cylinder(P["hw"], (x, y, fz1 - 0.001), (x, y, fz1 + 0.0012), 0.0105, 12, HARDWARE)   # washer
    # the wedge body (the side profile extruded along x) and the armoured end caps round its two ends
    prof = _rack_profile()
    Fx = Face((-R_HW, 0.0, 0.0), (0, 1, 0), (0, 0, 1))                                   # normal +x
    G.prism(P["body"], Fx, prof, 0.0, 2 * R_HW, PAINT)
    cap = _offset(prof, 0.002, keep=(0,))          # 2 mm proud all round but on the foot
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (R_HW - 0.002), sx * R_CAP))
        G.prism(P["dark"], Face((x0, 0.0, 0.0), (0, 1, 0), (0, 0, 1)), cap, 0.0, x1 - x0, DARK)
    # the bezel ring on the tilted face, the liner, the screen
    F = _rack_face()
    sl = (R_Z[1] - R_Z[0]) / c / 2                                                       # half the face's slant
    out = _clip(R_BEZEL_HW, sl - 0.004, 0.012 if lod < 2 else 0.0)
    _bezel(P, F, out, R_WIN, R_SCREEN, -0.0005, R_BEZEL_T, SCREEN_2, lod, liner_back=R_SCREEN_D - 0.0005)
    if lod == 0:
        for sa in (-1, 1):
            for sb in (-1, 1):
                _hex(P["hw"], F, sa * (R_WIN[0] + 0.011), sb * (sl - 0.016), R_BEZEL_T - 0.001,
                     R_BEZEL_T + 0.004, r=0.0055)
    if lod >= 2:
        return
    # the rear service cover (two screws) and the power / data gland under it
    Fr = _back(R_BACK_Y)
    G.prism(P["dark"], Fr, _clip(R_HW - 0.03, 0.05, 0.01, 0.0), -0.0005, 0.003, DARK)
    G.cylinder(P["dark"], Fr(0.10, -0.085, -0.001), Fr(0.10, -0.085, 0.009), 0.010, 8 if lod == 0 else 6, DARK)
    if lod == 0:
        for sa in (-1, 1):
            _hex(P["hw"], Fr, sa * 0.15, 0.0, 0.002, 0.0055, r=0.005)
        G.cylinder(P["hw"], Fr(0.10, -0.085, 0.009), Fr(0.10, -0.085, 0.014), 0.0078, 6, HARDWARE)
        # backlight vents on the top: Darker louvre slots
        for x in (-0.12, -0.06, 0.0, 0.06, 0.12):
            G.box(P["dark"], (x - 0.022, 0.012, R_Z[1] - 0.0035), (x + 0.022, 0.024, R_Z[1] + 0.0015), DARK)
            G.box(P["dark"], (x - 0.022, 0.036, R_Z[1] - 0.0035), (x + 0.022, 0.048, R_Z[1] + 0.0015), DARK)


def last_lod(spec):
    p = Part("lastlod")
    v = spec.variant
    m = f"{spec.name}_LastLOD"
    if v == "Aisle":
        G.box(p, (-A_HW, A_BACK[0], -A_HH), (A_HW, A_BEZEL[1], A_HH), m)
    elif v == "AisleHang":
        G.box(p, (-H_HW, -H_BEZEL, H_Z[0]), (H_HW, H_BEZEL, H_RAIL[1]), m)
    else:
        G.box(p, (-R_HW, R_BACK_Y, R_FOOT[3]), (R_HW, R_FACE_TOP_Y, R_Z[1]), m)
    return [p]


PART_NAMES = ("body", "bezel", "dark", "hw", "decal", "screen")


def build(spec, lod):
    """Parts for one LOD, in the centred block frame. The last LOD (n_lods - 1) is the 12-tri box."""
    if lod == n_lods(spec) - 1:
        return last_lod(spec)
    P = {k: Part(k) for k in PART_NAMES}
    P["decal"].decal = True
    P["screen"].decal = True
    if lod == 0:
        P["body"].bevel = (0.002, 1)
        P["bezel"].bevel = (0.0015, 1)
    {"Aisle": _aisle, "AisleHang": _hang, "Rack": _rack}[spec.variant](P, spec, lod)
    return [p for p in P.values() if not p.empty()]
