"""KVM console (6U, 2x1x3 cells): a ControlPanel25 clone (terminal access) with a pop-out console drawer.
Reference: docs/ideas/reference/datacenter/servers/kvm/ (a 1U pull-out drawer: fold-down LCD lid with two latch hooks,
keyboard + trackpad, side slide rails visible when open, a handle lip) and the v2 mockup (drawer + port-select bank).

Three models (dc/subparts.py has the numbers, the animation and the definitions):
| model            | part                                     | purpose                                                  |
| base (the block) | drawer bay (Darker core cut-out)          | the drawer's housing; fixed slide members on its walls   |
|                  | bay header lip with a Yellow line         | marks the moving drawer's edge (pinch point)             |
|                  | port-select bank: 8 keys, port lamps, 1-8 | choose which server the console talks to (port 3 = Yellow, selected) |
|                  | OSD module: screen, power ring, KVM-06    | on-screen display of the selected port; power            |
|                  | honeycomb intake                          | front-to-back cooling air                                |
| KvmDrawer        | painted fascia: pull bar, 2 Yellow latch tabs, power lamp, KVM plate | pull the drawer; press the tabs to release it |
|                  | tray on telescopic slides (Brushed)       | carries the console; stays 7 cm engaged when fully out   |
|                  | keyboard bed + 70 keys, palm rest, trackpad + buttons | input                                        |
|                  | rear electronics cover with vent bars, hinge towers + knuckles | the console electronics; the lid pivots |
| KvmScreen        | lid: painted back shell, Darker bezel, screen (vanilla Terminal art), hinge barrels, latch hooks | the monitor |

The drawer sits in the LOWER band of the face (v2 layout; the reference README suggests the top): the fold-up screen
then rises over this server's own upper panel and covers the lower half of the slot above when fully out (the user's
decision: real KVMs do), and the simultaneous slide-and-fold's mid-motion overlap stays inside this server's own face
(subparts.transient_intrusion) instead of cutting through the neighbour above.

Materials. Base LOD0/1 (8, the cap): Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite stencils,
EmissiveGreen (lit lamps; unlit ones are Darker lenses), Terminal (the OSD). Drawer (a 0.56 m model, cap 8): Colorable,
Darker, Yellow, Brushed, MetalDull, CleanWhite, EmissiveGreen. Screen (a 0.37 m model: Keen's small-model cap 4 / 3):
Colorable, Darker, Terminal, Brushed (LOD1 drops Brushed). Subpart lamps are always lit: the material swapper does not
reach subparts (vanilla-animations.md Q11), and the drawer only exists while the block is Functional.
"""
from .. import server
from .. import subparts as S
from ..style import DARK, HARDWARE, LAMP_GREEN, PAINT, STEEL, STENCIL_WHITE, YELLOW, oct_pts, stencil
from . import deco, panel

try:
    from se2model import geom as G
    from se2model.geom import Face, Part
except ImportError:
    G = Face = Part = None

TERMINAL = "Terminal"
GAP = deco.GAP
FZ = None          # the horizontal face (a = x, b = y, d = z), made on first use


def _fz():
    return Face((0, 0, 0), (1, 0, 0), (0, 1, 0))


# ---------------------------------------------------------------------------------------------------- base model
def core_bays():
    """The core tub (server._tub_with_bays): solid behind the bay, the drawer bay box from there to the core front."""
    b = S.BAY
    return [(server.Y_BACK_CORE, b["y0"], None),
            (b["y0"], server.Y_FRONT_CORE, (-b["x"], b["x"], b["z0"], b["z1"]))]


def face(spec, P, lod):
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    hb0, hb1 = S.BAY["z1"], S.BAY["z1"] + 0.006          # bay header lip
    pb0 = hb1 + GAP                                       # modules above the bay
    ba1 = 0.066                                           # port bank / intake right edge (face a)
    ra0 = ba1 + GAP                                       # OSD module
    kb0 = 0.024                                           # port bank bottom
    G.prism(P["dark"], F, G.rect(a0, a1, hb0, hb1), fl, fl + 0.012, DARK)
    if lod <= 1:   # hazard line on the lip: the moving drawer runs right under it
        G.prism(P["fine"], F, G.rect(a0 + 0.004, a1 - 0.004, hb0 + 0.0015, hb0 + 0.0035), fl + 0.012, fl + 0.0134,
                YELLOW)
    # fixed (outer) slide members on the bay walls: the drawer's telescopic rails run in them
    if lod <= 1:
        for sx in (-1, 1):
            x0, x1 = sorted((sx * 0.2048, sx * (S.BAY["x"] - 0.0002)))
            G.box(P["hw"], (x0, S.BAY["y0"] + 0.005, -0.091), (x1, server.Y_FRONT_CORE - 0.004, -0.073), STEEL)
    if lod >= 2:
        G.prism(P["dark"], F, G.rect(a0, ba1, pb0, b1), fl, fl + 0.010, DARK)
        G.prism(P["dark"], F, G.rect(ra0, a1, pb0, b1), fl, fl + 0.010, DARK)
        panel.screen(P, F, 0.083, 0.200, 0.050, 0.089, fl + 0.0115, TERMINAL, panel.TERMINAL_UV)
        return

    # ---- port-select bank: 8 keys (port 3 selected: Yellow), a lamp over each (lit: ports with a live server)
    G.prism(P["dark"], F, oct_pts(a0, kb0, ba1, b1, 0.006), fl, fl + 0.010, DARK)
    d = fl + 0.010
    pitch = (ba1 - a0 - 0.016) / 8
    for i in range(8):
        ka = a0 + 0.008 + pitch * (i + 0.5)
        panel.key(P, F, ka, 0.046, d, pitch - 0.009, 0.020, YELLOW if i == 2 else PAINT, lod)
        lit = i in (0, 2, 5)
        deco.led(P, F, ka, 0.071, d, lit, lod, r=0.0042, mat=LAMP_GREEN if lit else DARK)
        if lod == 0:
            stencil(P["decal"], F, ka, 0.089, 0.009, str(i + 1), d=d)
    # ---- intake under the bank
    deco.honeycomb(P, F, a0, ba1, pb0, kb0 - GAP, fl, fl + 0.010, 0.0072, lod, chamfer=0.004)
    # ---- OSD module: the on-screen display (vanilla Terminal art), power with lit ring, ID
    G.prism(P["dark"], F, oct_pts(ra0, pb0, a1, b1, 0.006), fl, fl + 0.010, DARK)
    win = (0.083, 0.200, 0.050, 0.089)
    G.plate(P["dark"], F, oct_pts(win[0] - 0.006, win[2] - 0.006, win[1] + 0.006, win[3] + 0.006, 0.004),
            [oct_pts(win[0], win[2], win[1], win[3], 0.003)], fl + 0.010, fl + 0.016, DARK)
    panel.screen(P, F, win[0], win[1], win[2], win[3], fl + 0.012, TERMINAL, panel.TERMINAL_UV)
    deco.power_button(P, F, ra0 + 0.020, pb0 + 0.024, fl + 0.010, lod, r=0.0085)
    stencil(P["decal"], F, 0.155, 0.031, 0.014, "KVM-06", d=fl + 0.010)
    if lod == 0:
        stencil(P["decal"], F, 0.155, 0.009, 0.0085, "CONSOLE", d=fl + 0.010)


def build(spec, lod):
    """Parts for one LOD: the shared chassis (6U bezel, PSU rear) round a core with the drawer bay, and the face."""
    if lod == server.n_lods(spec) - 1:
        return server.last_lod(spec)
    P = server.parts()
    face(spec, P, lod)
    return server.chassis(spec, lod, P, bays=core_bays())


# ---------------------------------------------------------------------------------------------------- subparts
def _parts():
    P = {k: Part(k) for k in ("frame", "dark", "hw", "fine", "keys", "decal")}
    P["decal"].decal = True
    return P


def _translate(parts, v):
    import bmesh
    for p in parts:
        bmesh.ops.translate(p.bm, vec=v, verts=p.bm.verts)


def drawer(lod):
    """The KvmDrawer subpart, built in the KVM frame (stowed) and moved so the hinge (the pivot) is the origin."""
    P = _parts()
    if lod == 0:
        P["frame"].bevel = (0.003, 1)
    F = server.front_face()
    Fz = _fz()
    D = S.DRAWER_BOX
    x, z0, z1 = D["x"], D["z0"], D["z1"]
    df0, df1 = D["y_fascia"] - server.D2, D["y_front"] - server.D2
    bc = (z0 + z1) / 2
    # ---- fascia
    G.prism(P["frame"], F, oct_pts(-x, z0, x, z1, 0.008 if lod <= 1 else 0.0), df0, df1, PAINT)
    for sa in (-1, 1):   # release latch tabs
        G.prism(P["fine"], F, oct_pts(sa * 0.172 - 0.008, bc - 0.020, sa * 0.172 + 0.008, bc + 0.020, 0.003),
                df1, df1 + 0.008, YELLOW)
    for sa in (-1, 1):   # pull-bar standoffs
        G.prism(P["dark"], F, oct_pts(sa * 0.072 - 0.007, bc - 0.007, sa * 0.072 + 0.007, bc + 0.007, 0.002),
                df1, df1 + 0.014, DARK)
    G.prism(P["hw"], F, oct_pts(-0.085, bc - 0.0065, 0.085, bc + 0.0065, 0.003), df1 + 0.012, df1 + 0.022, STEEL)
    if lod <= 1:
        deco.led(P, F, -0.125, bc, df1, True, lod, r=0.005)
        G.prism(P["dark"], F, oct_pts(0.100, bc - 0.010, 0.150, bc + 0.010, 0.003), df1, df1 + 0.003, DARK)
        stencil(P["decal"], F, 0.125, bc, 0.011, "KVM", d=df1 + 0.003)
    # ---- tray, side walls, telescopic rails, hinge towers
    yb, yf = D["y0"], D["y_fascia"]
    G.box(P["dark"], (-0.196, yb, z0), (0.196, yf, z0 + 0.007), DARK)
    for sx in (-1, 1):
        xa, xb = sorted((sx * 0.189, sx * 0.196))
        G.box(P["dark"], (xa, yb, z0 + 0.007), (xb, yf, -0.062), DARK)
        xa, xb = sorted((sx * 0.186, sx * 0.196))
        G.box(P["dark"], (xa, 0.031, -0.062), (xb, 0.061, -0.033), DARK)                       # hinge tower
        if lod <= 1:
            xa, xb = sorted((sx * 0.196, sx * 0.2045))
            G.box(P["hw"], (xa, yb, -0.088), (xb, 0.345, -0.076), STEEL)                          # inner rail
        G.cylinder(P["hw"], (sx * 0.185, S.HINGE[1], S.HINGE[2]), (sx * 0.1965, S.HINGE[1], S.HINGE[2]), 0.0095,
                   12 if lod == 0 else 6, STEEL)                                                 # knuckle
    # ---- keyboard: bed, keys, palm rest, trackpad
    kz0 = z0 + 0.007
    G.box(P["hw"], (-0.182, 0.078, kz0), (0.182, 0.262, -0.070), HARDWARE)
    G.box(P["dark"], (-0.182, 0.262, kz0), (0.182, 0.345, -0.066), DARK)
    for r in range(5):
        yc = 0.096 + 0.035 * r
        if lod >= 1:
            G.box(P["keys"], (-0.173, yc - 0.014, -0.070), (0.173, yc + 0.014, -0.061), DARK)
            continue
        cols = [(c, c) for c in range(14)] if r < 4 else [(0, 0), (1, 1), (2, 2), (3, 3), (4, 9), (10, 10),
                                                            (11, 11), (12, 12), (13, 13)]
        for c0, c1 in cols:
            xa, xb = -0.1625 + 0.025 * c0 - 0.0105, -0.1625 + 0.025 * c1 + 0.0105
            G.prism(P["keys"], Fz, oct_pts(xa, yc - 0.014, xb, yc + 0.014, 0.002), -0.070, -0.060, DARK)
    G.prism(P["hw"], Fz, oct_pts(-0.032, 0.272, 0.032, 0.316, 0.004 if lod == 0 else 0.0), -0.066, -0.0645, STEEL)
    if lod == 0:
        for xa in (-0.030, 0.002):
            G.box(P["dark"], (xa, 0.321, -0.066), (xa + 0.028, 0.335, -0.0635), DARK)
    # ---- underside (seen when the drawer is out): two Brushed stiffening channels along the tray, three
    #      Darker cross ribs, a Darker data plate (the 4 mm under the tray is still inside the bay, z0 >= bay z0)
    if lod == 0:
        for sx in (-1, 1):
            xa, xb = sorted((sx * 0.150, sx * 0.170))
            G.box(P["hw"], (xa, yb + 0.010, z0 - 0.003), (xb, yf - 0.010, z0), STEEL)
        for yy in (yb + 0.06, (yb + yf) / 2, yf - 0.06):
            G.box(P["fine"], (-0.150, yy - 0.006, z0 - 0.0025), (0.150, yy + 0.006, z0), DARK)
        Fu = Face((0, 0, z0 - 0.0025), (1, 0, 0), (0, -1, 0))   # facing down; reads from in front of the drawer
        G.prism(P["fine"], Fu, oct_pts(-0.07, -0.25, 0.07, -0.20, 0.006), 0.0, 0.0005, DARK)
        stencil(P["decal"], Fu, 0.0, -0.225, 0.014, "KVM-06 TRAY", d=0.0005)
    # ---- rear electronics cover with vent bars
    G.box(P["dark"], (-0.182, yb + 0.005, kz0), (0.182, 0.026, -0.062), DARK)
    if lod == 0:
        for k in range(7):
            yy = yb + 0.025 + 0.022 * k
            G.box(P["hw"], (-0.150, yy, -0.062), (0.150, yy + 0.008, -0.0605), HARDWARE)
    parts = [p for p in P.values() if not p.empty()]
    _translate(parts, (-S.HINGE[0], -S.HINGE[1], -S.HINGE[2]))
    return parts


def screen(lod):
    """The KvmScreen subpart in its own frame: hinge axis = x through the origin; the closed lid lies along +y with its
    screen facing down (-z) onto the keyboard. Rotating +FOLD_DEG about +x stands it up, screen to the front."""
    P = _parts()
    if lod == 0:
        P["frame"].bevel = (0.002, 1)
    Fz = _fz()
    w, L, t = S.LID["half_w"], S.LID["len"], S.LID["half_t"]
    sa = S.SCREEN_AREA
    outer = oct_pts(-w, 0.008, w, L, 0.012 if lod <= 1 else 0.0)
    G.prism(P["frame"], Fz, outer, 0.001, t, PAINT)                                   # back shell (paint)
    if lod == 0:   # back: a raised stiffening panel and a Darker finger recess by the free edge (lift the lid here)
        G.prism(P["frame"], Fz, oct_pts(-w + 0.022, 0.040, w - 0.022, L - 0.040, 0.016), t, t + 0.0015, PAINT)
        G.prism(P["dark"], Fz, oct_pts(-0.060, L - 0.030, 0.060, L - 0.014, 0.006), t, t + 0.0008, DARK)
    if lod == 0:
        G.plate(P["dark"], Fz, outer, [oct_pts(-sa["half_w"], sa["y0"], sa["half_w"], sa["y1"], 0.004)], -t, 0.001,
                DARK)                                                                  # bezel round the screen
        G.box(P["dark"], (-sa["half_w"], sa["y0"], -0.0015), (sa["half_w"], sa["y1"], 0.001), DARK)   # panel back
        sd = 0.0045                                                                    # screen 4.5 mm inside
    else:
        G.prism(P["dark"], Fz, outer, -t, 0.001, DARK)
        sd = t + 0.0004
    # the screen faces -z (u = -x: the viewer's right when the lid stands up; v = +y: up)
    Fs = Face((0, 0, 0), (-1, 0, 0), (0, 1, 0))
    asp = (sa["y1"] - sa["y0"]) / (2 * sa["half_w"])
    panel._quad(P["decal"], Fs, -sa["half_w"], sa["half_w"], sa["y0"], sa["y1"], sd, TERMINAL,
                (0.0, 1.0, 0.5 - asp / 2, 0.5 + asp / 2))
    G.box(P["dark"], (-0.108, -t + 0.002, -t + 0.001), (0.108, 0.008, t - 0.001), DARK)      # hinge spine
    if lod == 0:
        for sx in (-1, 1):
            G.cylinder(P["hw"], (sx * 0.110, 0, 0), (sx * 0.183, 0, 0), t + 0.001, 12, STEEL)   # hinge barrels
            G.box(P["hw"], (sx * 0.150 - 0.010, L - 0.006, -t - 0.006), (sx * 0.150 + 0.010, L - 0.001, -t + 0.002),
                  STEEL)                                                               # latch hooks
    return [p for p in P.values() if not p.empty()]


def last_box(name, lo, hi):
    """A subpart's last LOD: its LOD0 bounding box, one material (the paint), 12 triangles."""
    p = Part(f"{name}_last")
    G.box(p, lo, hi, PAINT)
    return [p]


SUBPARTS = {S.DRAWER: drawer, S.SCREEN: screen}
