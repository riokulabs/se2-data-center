"""Event-controller server (6U, 2x1x3 cells): behaves exactly as vanilla EventController (cloned definitions, its
EventControllerIndicator kept). Detail vocabulary: a network / IO module front (rows of ports with a link lamp each,
docs/ideas/reference/datacenter/servers/README.md), plus a key-lock switch and a recessed reset.

Face (viewer's left to right), inside server.face_frame:
| part                          | purpose                                                                    |
| ID plate                      | EVC-06 / LOGIC stencils                                                    |
| key-lock switch               | arms the controller (Brushed escutcheon, key with a Yellow tag at ARM)     |
| power + reset strip           | power button, recessed reset pinhole (RST)                                 |
| IO module (painted)           | two rows of 8 action ports with a lamp over each: row T fires on True,     |
|                               | row F on False (the event controller's two action groups)                  |
| honeycomb intake (IO module)  | cooling air                                                                |
Indicator: row T's lamps (and rear PSU A) are the slot "Emissive01", row F's (and PSU B) "Emissive02": the vanilla
IndicatorMeshParts. True lights row T green and darkens row F; False the reverse; NullState lights both white; not
powered blinks both red; not functional leaves both off.
Materials (LOD0 = 8, the cap): Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite, Emissive01, Emissive02.
"""
from .. import functional as FN
from .. import server
from ..style import DARK, PAINT, STEEL, YELLOW, oct_pts, stencil
from . import deco, panel

try:
    from se2model import geom as G
except ImportError:
    G = None

T, F_ = FN.EVC_TRUE, FN.EVC_FALSE
GAP = deco.GAP
PITCH = 0.030
PORT_W, PORT_H = 0.020, 0.015


def _io(P, F, a0, a1, b0, b1, fl, lod):
    """The IO module: a painted plate with 2 x 8 port openings (Brushed contacts inside), a lamp over each port, a T
    and an F row plate, and a honeycomb intake below."""
    rows = ((T, "T", 0.054), (F_, "F", 0.006))      # (indicator slot, row label, port centre b)
    pa0 = a0 + 0.040                                  # first port column edge (row plates to its left)
    ports = [(pa0 + PITCH * (i + 0.5), bc, mat) for mat, _, bc in rows for i in range(8)]
    hb0, hb1 = b0 + 0.012, -0.024                     # intake opening
    if lod >= 2:
        G.prism(P["frame"], F, G.rect(a0, a1, b0, b1), fl, fl + 0.012, PAINT)
        G.prism(P["dark"], F, G.rect(a0 + 0.012, a1 - 0.012, hb0, hb1), fl + 0.012, fl + 0.013, DARK)
        for mat, _, bc in rows:   # one lamp bar per row: the state stays readable at range
            panel.screen(P, F, pa0 + 0.004, pa0 + 8 * PITCH - 0.004, bc + 0.014, bc + 0.021, fl + 0.0135, mat)
        return
    holes = [G.rect(ac - PORT_W / 2, ac + PORT_W / 2, bc - PORT_H / 2, bc + PORT_H / 2) for ac, bc, _ in ports]
    holes.append(G.rect(a0 + 0.012, a1 - 0.012, hb0, hb1))
    G.plate(P["frame"], F, oct_pts(a0, b0, a1, b1, 0.008), holes, fl, fl + 0.012, PAINT, bottom=(lod == 0))
    deco.honeycomb(P, F, a0 + 0.012, a1 - 0.012, hb0, hb1, fl, fl + 0.008, 0.0095, lod)
    for ac, bc, mat in ports:
        if lod == 0:   # the port's contact strip and latch tab inside the socket
            G.prism(P["fine"], F, G.rect(ac - PORT_W / 2 + 0.003, ac + PORT_W / 2 - 0.003, bc + PORT_H / 2 - 0.004,
                    bc + PORT_H / 2 - 0.001), fl, fl + 0.0015, STEEL)
            G.prism(P["fine"], F, G.rect(ac - 0.003, ac + 0.003, bc - PORT_H / 2, bc - PORT_H / 2 + 0.003), fl,
                    fl + 0.002, DARK)
        panel.ind_lamp(P, F, ac, bc + PORT_H / 2 + 0.0095, fl + 0.012, mat, lod, r=0.0045)
    for mat, lbl, bc in rows:   # row plates: T / F
        G.prism(P["dark"], F, oct_pts(a0 + 0.008, bc - 0.012, pa0 - 0.004, bc + 0.024, 0.004), fl + 0.012, fl + 0.015,
                DARK)
        stencil(P["decal"], F, (a0 + 0.008 + pa0 - 0.004) / 2, bc + 0.006, 0.018, lbl, d=fl + 0.015)


def _key_switch(P, F, a, b, d, lod):
    """Key-lock switch: Brushed escutcheon, Darker keyway, the key turned to ARM with a Yellow tag."""
    n = 16 if lod == 0 else 8
    G.cylinder(P["hw"], F(a, b, d - 0.001), F(a, b, d + 0.006), 0.016, n, STEEL)
    G.cylinder(P["hw"], F(a, b, d + 0.006), F(a, b, d + 0.008), 0.011, n, DARK)
    G.prism(P["hw"], F, oct_pts(a - 0.004, b - 0.0035, a + 0.016, b + 0.0035, 0.0015), d + 0.008, d + 0.016, STEEL)
    G.prism(P["fine"], F, oct_pts(a + 0.014, b - 0.008, a + 0.030, b + 0.008, 0.003), d + 0.009, d + 0.015, YELLOW)


def face(spec, P, lod):
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    c1 = -0.090                       # left column right edge
    ca = (a0 + c1) / 2
    idb0 = 0.050
    pb1 = -0.064                      # power / reset strip top
    io0 = c1 + GAP + 0.001

    # ---- left column: ID plate, key switch on the floor, power + reset strip
    G.prism(P["dark"], F, oct_pts(a0, idb0, c1, b1, 0.006 if lod <= 1 else 0.0), fl, fl + 0.010, DARK)
    if lod <= 1:
        stencil(P["decal"], F, ca, 0.084, 0.017, "EVC-06", d=fl + 0.010)
        stencil(P["decal"], F, ca, 0.062, 0.010, "LOGIC", d=fl + 0.010)
    # key switch on a painted mounting plate
    kb0, kb1 = pb1 + GAP, idb0 - GAP
    G.prism(P["frame"], F, oct_pts(a0, kb0, c1, kb1, 0.006 if lod <= 1 else 0.0), fl, fl + 0.008, PAINT)
    kc = (a0 + 0.040, (kb0 + kb1) / 2)
    if lod <= 1:
        _key_switch(P, F, kc[0], kc[1], fl + 0.008, lod)
        G.prism(P["dark"], F, oct_pts(kc[0] + 0.036, kc[1] - 0.009, c1 - 0.006, kc[1] + 0.009, 0.003), fl + 0.008,
                fl + 0.010, DARK)
        stencil(P["decal"], F, (kc[0] + 0.036 + c1 - 0.006) / 2, kc[1], 0.011, "ARM", d=fl + 0.010)
        G.prism(P["dark"], F, oct_pts(kc[0] - 0.016, kb1 - 0.016, kc[0] + 0.016, kb1 - 0.004, 0.002), fl + 0.008,
                fl + 0.010, DARK)
        stencil(P["decal"], F, kc[0], kb1 - 0.010, 0.008, "SAFE", d=fl + 0.010)
    else:
        G.cylinder(P["hw"], F(kc[0], kc[1], fl + 0.008), F(kc[0], kc[1], fl + 0.014), 0.016, 6, STEEL)
    # power + reset strip
    G.prism(P["dark"], F, oct_pts(a0, b0, c1, pb1, 0.005 if lod <= 1 else 0.0), fl, fl + 0.008, DARK)
    sb = (b0 + pb1) / 2
    if lod <= 1:
        G.cylinder(P["hw"], F(a0 + 0.018, sb, fl + 0.007), F(a0 + 0.018, sb, fl + 0.012), 0.0115, 16 if lod == 0 else 8,
                   DARK)
        G.cylinder(P["frame"], F(a0 + 0.018, sb, fl + 0.012), F(a0 + 0.018, sb, fl + 0.016), 0.0085,
                   16 if lod == 0 else 8, PAINT)
        ra = a0 + 0.056   # reset: a Brushed ring round a pinhole (the pin sits recessed, needs a tool)
        n = 12 if lod == 0 else 6
        ring = [[(ra + x, sb + y) for x, y in G.ngon(r, n)] for r in (0.0065, 0.0022)]
        G.plate(P["hw"], F, ring[0], [ring[1]], fl + 0.008, fl + 0.011, STEEL)
        stencil(P["decal"], F, ra + 0.014, sb, 0.010, "RST", d=fl + 0.008, align="left")

    # ---- IO module
    _io(P, F, io0, a1, b0, b1, fl, lod)


def build(spec, lod):
    """Parts for one LOD: the shared chassis (PSU A lamp = Emissive01, PSU B = Emissive02) + the face."""
    return server.build(spec, lod, face, lamp=(T, F_))
