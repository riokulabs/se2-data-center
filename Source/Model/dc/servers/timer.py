"""Timer server (6U, 2x1x3 cells): behaves exactly as vanilla Timer50 (cloned definitions, its TimerBlockIndicator
kept). Detail vocabulary: the Dell R610 front LCD strip (docs/ideas/reference/datacenter/servers/README.md).

Face (viewer's left to right), inside server.face_frame:
| part                          | purpose                                                                    |
| LCD module (Darker)           | backlit strip (vanilla Terminal UI art) + 3 nav keys (< > and a Yellow SET) |
| 3 drive sleds                 | the timer's own storage (hex vent, lever + Yellow release, ACTIVITY lamp)  |
| control strip                 | power button (indicator ring), 2 USB service ports, TMR-06 stencil         |
| COUNT plate                   | the big COUNT lamp: the timer's state lamp                                 |
| honeycomb intake (right)      | front-to-back cooling air                                                  |
Indicator: every lamp of the slot "EmissiveOff" (COUNT, the power ring, the 3 sled lamps, the 2 rear PSU lamps) is
a mesh part of Timer50's IndicatorMeshParts, so the vanilla states apply unchanged: off (not functional), red slow
blink (not powered), green (idle), amber blink (paused), teal fast blink (counting).
Materials (LOD0 = 8, the cap): Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite stencils, Terminal,
EmissiveOff (the indicator). No EmissiveGreen: an unlit or always-green lamp would look like a state.
"""
from .. import functional as FN
from .. import server
from ..style import DARK, PAINT, STEEL, YELLOW, oct_pts, stencil
from . import deco, panel

try:
    from se2model import geom as G
except ImportError:
    G = None

IND = FN.TIMER_IND
GAP = deco.GAP


def face(spec, P, lod):
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    lm1 = 0.046                       # left block right edge (LCD module, sleds, control strip)
    ra0 = lm1 + 0.006                 # right block (COUNT plate over the intake)
    mb0 = 0.004                       # LCD module bottom
    sb0, sb1 = -0.072, mb0 - GAP      # sled row
    cs1 = sb0 - GAP                   # control strip top
    cp0 = 0.052                       # COUNT plate bottom
    win = (-0.200, -0.038, 0.032, 0.086)   # LCD window (3:1, the Terminal art region)
    keys_a = (-0.016, 0.006, 0.028)
    kb = 0.066
    count = (ra0 + 0.024, (cp0 + b1) / 2)

    # ---- LCD module: Darker plate with the window cut in, the lit strip recessed 8 mm
    md = fl + 0.012
    outer = oct_pts(a0, mb0, lm1, b1, 0.006 if lod <= 1 else 0.0)
    if lod >= 2:
        G.prism(P["dark"], F, outer, fl, md, DARK)
        panel.screen(P, F, win[0], win[1], win[2], win[3], md + 0.0015, FN.TERMINAL_SCREEN, panel.TERMINAL_UV)
    else:
        G.plate(P["dark"], F, outer, [oct_pts(win[0], win[2], win[1], win[3], 0.004)], fl, md, DARK)
        panel.screen(P, F, win[0] + 0.002, win[1] - 0.002, win[2] + 0.002, win[3] - 0.002, fl + 0.004,
                     FN.TERMINAL_SCREEN, panel.TERMINAL_UV)
        for i, ka in enumerate(keys_a):            # nav keys: < >  and SET
            panel.key(P, F, ka, kb, md, 0.016, 0.016, YELLOW if i == 2 else PAINT, lod)
        if lod == 0:                               # arrow notches on the < > caps (cut-in look: Darker chevrons)
            for ka, s in ((keys_a[0], -1), (keys_a[1], 1)):
                G.prism(P["fine"], F, [(ka - s * 0.003, kb - 0.004), (ka + s * 0.004, kb), (ka - s * 0.003, kb + 0.004)]
                        if s > 0 else [(ka - s * 0.003, kb - 0.004), (ka - s * 0.003, kb + 0.004), (ka + s * 0.004, kb)],
                        md + 0.006, md + 0.0065, DARK)
        stencil(P["decal"], F, (keys_a[0] + keys_a[2]) / 2, 0.036, 0.013, "TMR-06", d=md)

    # ---- drive sleds (the timer's storage); their activity lamps are indicator parts
    n = 3
    w = (lm1 - a0 - (n - 1) * GAP) / n
    if lod >= 2:
        G.prism(P["dark"], F, G.rect(a0, lm1, sb0, sb1), fl, fl + 0.010, DARK)
    for i in range(n):
        x0 = a0 + i * (w + GAP)
        deco.caddy(P, F, x0, x0 + w, sb0, sb1, fl, lod, True, lamp=IND)

    # ---- control strip: power button with the indicator ring, two USB service ports, TIMER stencil
    G.prism(P["dark"], F, oct_pts(a0, b0, lm1, cs1, 0.005 if lod <= 1 else 0.0), fl, fl + 0.008, DARK)
    cb = (b0 + cs1) / 2
    deco.power_button(P, F, a0 + 0.018, cb, fl + 0.008, lod, r=0.0085, ring=IND)
    if lod <= 1:
        for ua in (a0 + 0.050, a0 + 0.074):
            G.prism(P["hw"], F, G.rect(ua - 0.008, ua + 0.008, cb - 0.0045, cb + 0.0045), fl + 0.008, fl + 0.013, STEEL)
            if lod == 0:
                G.prism(P["fine"], F, G.rect(ua - 0.006, ua + 0.006, cb - 0.0022, cb + 0.0022), fl + 0.013,
                        fl + 0.0134, DARK)
        stencil(P["decal"], F, lm1 - 0.008, cb, 0.012, "TIMER", d=fl + 0.008, align="right")

    # ---- COUNT plate: the big state lamp
    G.prism(P["dark"], F, oct_pts(ra0, cp0, a1, b1, 0.006 if lod <= 1 else 0.0), fl, fl + 0.010, DARK)
    panel.ind_lamp(P, F, count[0], count[1], fl + 0.010, IND, lod, r=0.011)
    if lod <= 1:
        stencil(P["decal"], F, count[0] + 0.022, count[1], 0.016, "COUNT", d=fl + 0.010, align="left")

    # ---- honeycomb intake in a painted frame
    hb1 = cp0 - GAP
    G.plate(P["frame"], F, oct_pts(ra0, b0, a1, hb1, 0.008 if lod <= 1 else 0.0),
            [G.rect(ra0 + 0.012, a1 - 0.012, b0 + 0.012, hb1 - 0.012)], fl, fl + 0.012, PAINT)
    deco.honeycomb(P, F, ra0 + 0.012, a1 - 0.012, b0 + 0.012, hb1 - 0.012, fl, fl + 0.008, 0.0095, lod)


def build(spec, lod):
    """Parts for one LOD: the shared chassis (its rear PSU lamps are indicator parts too) + the timer face."""
    return server.build(spec, lod, face, lamp=IND)
