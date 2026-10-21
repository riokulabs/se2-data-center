"""Programmable server (6U, 2x1x3 cells): a blade chassis that hosts an in-game script (a WallInsertPanel clone
moved onto the KVM's Ruling 15 chain: a terminal-listed On/Off block, Plan 4 Ruling P4-2).
Data-only (no -loadScripts) it is a working chassis with On/Off whose program will not compile, and its lamps show
the amber standby state; with -loadScripts the same data runs the program (Ruling P4-1 = A', dc/scripting.py) and
the scripts swap its script-status lamp and LCD status bar to green while it is Working (Ruling P4-7). So the baked text is state-neutral:
the management LCD reads "SCRIPT HOST" / "PRG-06" and the lamp's legend "SCRIPT" / "STATUS"; nothing says offline.
Reference: docs/ideas/reference/datacenter/servers/blade-chassis/ (HP c7000, Dell M1000e, IBM BladeCenter) and the v2
mockup (6 sleds, ejector levers, management LCD, script status lamp).

Face (viewer's left to right), inside server.face_frame:
| part                                  | purpose                                                              |
| 6 vertical blade sleds                | the compute nodes; each: 2 hot-swap 2.5" drives (top), a honeycomb vent (air through the node), a status lens column (dark), an ejector lever with a Yellow release tab (bottom) |
| sled 4 pulled 20 mm proud, lever open | a node being serviced (depth, as the reference's half-pulled blade)  |
| management module                     | chassis controller, where the terminal opens (functional.PROG_MGMT): unlit mono LCD "SCRIPT HOST" / "PRG-06" over a lit status bar, 5-way pad (Yellow centre), the SCRIPT STATUS lamp, PRG-06 ID |
| rear (shared chassis)                 | hot-swap PSUs (their power lamps: static amber standby, EmissiveAmber), exhaust, I/O |
Materials (LOD0 8 of 8): Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite stencils, and two slots of the same
vanilla static amber ColorIndicatorMaterial (IndicatorWindTurbineEnabledLowEfficiency 4a74bc1c; dc/material_guids.py):
EmissiveScriptStatus (functional.PROG_LED: the SCRIPT STATUS lamp and the LCD status bar, which the scripts swap green
while Working) and EmissiveAmber (functional.PROG_PSU_LAMP: the rear PSU lamps, never swapped). Data-only both render
the same amber, so the scripts-off block is unchanged (Plan 4 Task 4).
"""
import math

from .. import functional as FN
from .. import server
from ..style import DARK, HARDWARE, PAINT, STEEL, YELLOW, lamp, oct_pts, stencil
from . import deco, panel

try:
    from se2model import geom as G
except ImportError:
    G = None

STATUS = FN.PROG_LED         # the script-status slot (lamp + LCD bar) the scripts swap green (Ruling P4-7)
PSU_LAMP = FN.PROG_PSU_LAMP  # the rear PSU lamps: static amber, never swapped
GAP = deco.GAP
N_SLEDS = 6
PROUD = 3                    # sled index pulled out
PROUD_D = 0.020
LEVER_OPEN = 35.0            # deg, the pulled sled's ejector lever
MGMT_W = FN.PROG_MGMT["a"][1] - FN.PROG_MGMT["a"][0]   # management module width (right)
LCD_LINES = ("SCRIPT HOST", "PRG-06")   # the management LCD: state-neutral (Ruling P4-7)
LAMP_LEGEND = ("SCRIPT", "STATUS")      # beside the status lamp
LAST_FACE = {}               # what the last build placed (build_report "face")


def _sled(P, F, a0, a1, b0, b1, d, lod, proud=0.0, lever_open=0.0):
    """One vertical blade sled standing on depth d (+ proud)."""
    d = d + proud
    w = a1 - a0
    c0 = 1.0 if lod == 0 else 0.0     # LOD1 drops the small corner cuts
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, b1, 0.004 * c0), d, d + 0.008, DARK)   # carrier
    if proud and lod <= 1:   # the pulled sled's sides show (its body runs back into the chassis)
        for a in (a0 + 0.001, a1 - 0.003):
            G.prism(P["dark"], F, G.rect(a, a + 0.002, b0 + 0.004, b1 - 0.004), d - proud, d, DARK)
    if lod >= 2:
        return
    dt = d + 0.008
    # two hot-swap 2.5" drives at the top: painted faces with a MetalDull latch strip and a dark lens
    for k in range(2):
        db1 = b1 - 0.005 - k * 0.026
        db0 = db1 - 0.022
        G.prism(P["frame"], F, oct_pts(a0 + 0.004, db0, a1 - 0.004, db1, 0.002 * c0), dt, dt + 0.004, PAINT)
        if lod == 0:
            G.prism(P["fine"], F, G.rect(a0 + 0.008, a1 - 0.016, db0 + 0.004, db0 + 0.007), dt + 0.004, dt + 0.0055,
                    HARDWARE)
            G.prism(P["fine"], F, G.rect(a1 - 0.013, a1 - 0.008, db0 + 0.004, db0 + 0.007), dt + 0.004,
                    dt + 0.0055, DARK)                                  # activity lens (dark)
    # vent through the node
    vb1 = b1 - 0.060
    vb0 = b0 + 0.052
    if lod == 0:
        deco.honeycomb(P, F, a0 + 0.004, a1 - 0.004, vb0, vb1, dt - 0.002, dt + 0.003, 0.0045, lod)
    else:          # LOD1: a painted vent frame round a dark slot (the honeycomb's read at range, a tenth of the tris)
        G.plate(P["frame"], F, G.rect(a0 + 0.004, a1 - 0.004, vb0, vb1),
                [G.rect(a0 + 0.009, a1 - 0.009, vb0 + 0.006, vb1 - 0.006)], dt - 0.002, dt + 0.003, PAINT)
    # status lens column (dark: no node is running)
    if lod == 0:
        for k in range(3):
            bb = b0 + 0.044 - 0.007 * k
            G.prism(P["fine"], F, G.rect(a1 - 0.012, a1 - 0.006, bb - 0.0018, bb + 0.0018), dt, dt + 0.002, DARK)
    # ejector lever: pivot at the left end, Yellow release tab at the free end; opened = swung out about the pivot
    lb0, lb1 = b0 + 0.008, b0 + 0.020
    pa, L = a0 + 0.007, w - 0.014
    th = math.radians(lever_open)
    pe = (pa + L * math.cos(th), dt + 0.004 + L * math.sin(th))
    p0, p1 = F(pa, (lb0 + lb1) / 2, dt + 0.004), F(pe[0], (lb0 + lb1) / 2, pe[1])
    G.beam(P["hw"], p0, p1, lb1 - lb0, 0.006, STEEL)
    ta = pe[0] - 0.006 * math.cos(th)
    G.prism(P["fine"], F, oct_pts(ta - 0.0045, lb0 - 0.004, ta + 0.0045, lb1 + 0.010, 0.002 * c0), pe[1] - 0.001,
            pe[1] + 0.007, YELLOW)
    if lod == 0:
        G.cylinder(P["hw"], F(pa, lb0 - 0.002, dt + 0.004), F(pa, lb1 + 0.002, dt + 0.004), 0.0035, 8, HARDWARE)


def _mgmt(P, F, a0, a1, b0, b1, d, lod):
    """Chassis management module: mono LCD (host name) over a lit status bar, 5-way pad, the SCRIPT STATUS lamp, ID."""
    G.prism(P["dark"], F, oct_pts(a0, b0, a1, b1, 0.006 if lod <= 1 else 0.0), d, d + 0.010, DARK)
    dm = d + 0.010
    ac = (a0 + a1) / 2
    win = (a0 + 0.008, a1 - 0.008, b1 - 0.050, b1 - 0.010)
    if lod >= 2:
        panel._quad(P["decal"], F, win[0], win[1], win[2], win[3], dm + 0.0015, STATUS)
        return
    # LCD: Darker bezel round a dark (unlit) mono glass with the host's name and a lit status bar under it
    G.plate(P["dark"], F, oct_pts(win[0] - 0.004, win[2] - 0.004, win[1] + 0.004, win[3] + 0.004, 0.004),
            [G.rect(win[0], win[1], win[2], win[3])], dm, dm + 0.004, DARK)
    G.prism(P["dark"], F, G.rect(win[0], win[1], win[2], win[3]), dm - 0.002, dm + 0.001, DARK)
    for k, line in enumerate(LCD_LINES):
        stencil(P["decal"], F, ac, win[3] - 0.009 - 0.013 * k, 0.0085, line, d=dm + 0.0012)
    panel._quad(P["decal"], F, win[0] + 0.005, win[1] - 0.005, win[2] + 0.004, win[2] + 0.009, dm + 0.0012, STATUS)
    # 5-way pad (LOD1: the Yellow centre key on its pad)
    pc = (ac, b1 - 0.075)
    if lod == 1:
        G.prism(P["dark"], F, G.rect(pc[0] - 0.024, pc[0] + 0.024, pc[1] - 0.024, pc[1] + 0.024), dm, dm + 0.002, DARK)
    for da, db in ((0, 0.016), (0, -0.016), (0.016, 0), (-0.016, 0), (0, 0)):
        if lod == 0 or (da, db) == (0, 0):
            panel.key(P, F, pc[0] + da, pc[1] + db, dm, 0.011, 0.011, YELLOW if (da, db) == (0, 0) else DARK, lod)
    # the SCRIPT STATUS lamp (amber: standby, the data-only state; the scripts swap it green while Working)
    lc = (a0 + 0.020, b0 + 0.062)
    if lod == 0:
        lamp(P["hw"], F, lc[0], lc[1], dm, r=0.0085, mat=STATUS, lod=0)
    else:
        server._led(P, F, lc[0], lc[1], dm, STATUS, 1, r=0.0085)
    stencil(P["decal"], F, lc[0] + 0.016, lc[1] + 0.006, 0.010, LAMP_LEGEND[0], d=dm, align="left")
    if lod == 0:
        stencil(P["decal"], F, lc[0] + 0.016, lc[1] - 0.008, 0.010, LAMP_LEGEND[1], d=dm, align="left")
    G.prism(P["dark"], F, oct_pts(a0 + 0.006, b0 + 0.010, a1 - 0.006, b0 + 0.034, 0.003), dm, dm + 0.003, DARK)
    stencil(P["decal"], F, ac, b0 + 0.022, 0.013, "PRG-06", d=dm + 0.003)


def face(spec, P, lod):
    F = server.face_frame(spec)
    a0, a1, b0, b1 = F.area
    fl = F.floor
    ma0, ma1 = FN.PROG_MGMT["a"]          # the module's strip (also the Terminal box: integration)
    assert max(abs(p - q) for p, q in zip((ma1, *FN.PROG_MGMT["b"]), (a1, b0, b1))) < 1e-9, (F.area, FN.PROG_MGMT)
    sa1 = ma0 - GAP
    w = (sa1 - a0 - (N_SLEDS - 1) * GAP) / N_SLEDS
    for i in range(N_SLEDS):
        x0 = a0 + i * (w + GAP)
        pr = PROUD_D if i == PROUD else 0.0
        _sled(P, F, x0, x0 + w, b0, b1, fl, lod, proud=pr, lever_open=LEVER_OPEN if i == PROUD else 0.0)
    _mgmt(P, F, ma0, ma1, b0, b1, fl, lod)
    LAST_FACE.update({"sleds": N_SLEDS, "sled_width": round(w, 4), "proud_sled": PROUD + 1, "proud_mm": PROUD_D * 1000,
                      "lever_open_deg": LEVER_OPEN, "status_lamp": STATUS, "lcd": list(LCD_LINES),
                      "lamp_legend": list(LAMP_LEGEND), "mgmt": [round(ma0, 6), round(ma1, 6)]})


def build(spec, lod):
    """Parts for one LOD: the shared chassis (rear PSU lamps amber: standby) + the blade-chassis face."""
    return server.build(spec, lod, face, lamp=PSU_LAMP)
