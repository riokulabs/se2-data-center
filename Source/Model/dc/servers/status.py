"""Status-display server (6U, 2x1x3 cells): behaves exactly as vanilla LCDFlat50 (cloned definitions). The screen is
the LCD surface: its material slot is named "LCDScreen_Off", LCDFlat50's LcdMultiPanel surface MeshPartName, and the
interaction dummy keeps the name "LcdPanel", so players set text and images as on any vanilla LCD. The screen is 2:1
(integration.py sets the surface to 1024 x 512, AspectRatio 2, and the slot maps to vanilla LCDScreen_Off_2.0, as on
LCDWide300/500). Detail vocabulary: the HP c7000 Insight display / Dell LCD bezel (a recessed, angled screen and a
5-way nav pad; grille strips above and below).

Face (viewer's left to right), inside server.face_frame:
| part                          | purpose                                                                    |
| LCD bezel (painted)           | the screen recessed 1 cm behind a 45 deg angled bezel; slotted grille strips above and below (screen cooling) |
| control column (Darker)       | 5-way nav pad (4 keys round a Yellow OK), PWR / NET / TMP lamps, STA-06 ID |
Materials (LOD0 = 8, the cap): Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite, LCDScreen_Off, EmissiveGreen.
Unlit lamps are Darker lenses (no EmissiveOff slot).
"""
from .. import functional as FN
from .. import server
from ..style import DARK, LAMP_GREEN, PAINT, YELLOW, oct_pts, stencil
from . import deco, panel

try:
    from se2model import geom as G
except ImportError:
    G = None

GAP = deco.GAP
BEZEL = 0.010          # angled bezel width (= its depth: 45 deg)


def face(spec, P, lod):
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    sa, sb, sd = FN.STATUS_SCREEN["a"], FN.STATUS_SCREEN["b"], FN.STATUS_SCREEN["d"]
    top = sd + BEZEL                    # bezel plate front
    c0 = 0.124                          # control column left edge
    hole = (sa[0] - BEZEL, sa[1] + BEZEL, sb[0] - BEZEL, sb[1] + BEZEL)
    outer = oct_pts(a0, b0, c0 - GAP, b1, 0.010 if lod <= 1 else 0.0)

    # ---- the LCD bezel: painted plate, angled bezel down to the recessed screen, grille strips
    if lod >= 2:
        G.plate(P["frame"], F, outer, [G.rect(*hole)], fl, top, PAINT)
        G.prism(P["dark"], F, G.rect(*hole), fl, sd - 0.001, DARK)
    else:
        grille = []
        for gb0, gb1 in ((hole[3] + 0.006, b1 - 0.008), (b0 + 0.008, hole[2] - 0.006)):
            n = 11
            pitch = (hole[1] - hole[0]) / n
            for i in range(n):
                ga = hole[0] + pitch * (i + 0.5)
                grille.append(oct_pts(ga - pitch * 0.32, gb0, ga + pitch * 0.32, gb1, 0.0015 if lod == 0 else 0.0))
        G.plate(P["frame"], F, outer, [G.rect(*hole)] + grille, fl, top, PAINT)
        lip = 0.003   # the ring's outer edge laps over the plate's bevelled hole edge
        panel.bezel_ring(P["decal"], F, (hole[0] - lip, hole[1] + lip, hole[2] - lip, hole[3] + lip),
                         (sa[0], sa[1], sb[0], sb[1]), top + 0.0004, sd, PAINT)
        G.prism(P["dark"], F, G.rect(*hole), fl, sd - 0.001, DARK)      # the display module behind the glass
    panel.screen(P, F, sa[0], sa[1], sb[0], sb[1], sd, FN.LCD_SURFACE)

    # ---- control column: 5-way pad, lamps, ID
    G.prism(P["dark"], F, oct_pts(c0, b0, a1, b1, 0.006 if lod <= 1 else 0.0), fl, fl + 0.008, DARK)
    if lod >= 2:
        return
    d = fl + 0.008
    pc = ((c0 + a1) / 2, 0.052)
    n = 16 if lod == 0 else 8
    G.cylinder(P["frame"], F(pc[0], pc[1], d), F(pc[0], pc[1], d + 0.004), 0.030, n, PAINT)   # pad base
    for da, db in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        panel.key(P, F, pc[0] + da * 0.0175, pc[1] + db * 0.0175, d + 0.004, 0.012, 0.012, DARK, lod)
    G.cylinder(P["hw"], F(pc[0], pc[1], d + 0.004), F(pc[0], pc[1], d + 0.009), 0.0075, n, YELLOW)   # OK
    la = c0 + 0.016
    for i, (lbl, lit) in enumerate((("PWR", True), ("NET", True), ("TMP", False))):
        lb = -0.004 - 0.026 * i
        deco.led(P, F, la, lb, d, lit, lod, r=0.0055, mat=LAMP_GREEN if lit else DARK)
        stencil(P["decal"], F, la + 0.013, lb, 0.011, lbl, d=d, align="left")
    deco.label(P, F, c0 + 0.006, a1 - 0.006, b0 + 0.006, b0 + 0.026, d, "STA-06", 0.012, lod)


def build(spec, lod):
    """Parts for one LOD: the shared chassis (rear PSU lamps green, as the deco servers) + the status face."""
    return server.build(spec, lod, face)
