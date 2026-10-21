"""Merge main -> plan3-room: after-previews of what the merge touched on the racks (containment rails + rear PDU
strips + seated servers on main's placement-fixed rack, the neutral rack placard of the controller ruling) and the
CRAC beside them.

    DC_PREVIEW=merge blender -b --python Source/Model/build_dc.py -- "DC_Rack*" "DC_PDU_Rack*" "DC_Srv_*" DC_CRAC

Writes Source/Model/preview/merge-main/ (previews stay out of git)."""
import os

from . import catalog, config, rack_side
from . import preview as PV
from . import preview_p3t6 as P6
from . import preview_p3t7 as P7
from . import preview_task9 as P9
from .preview import T, want

OUT = os.path.join(config.PREVIEW_DIR, "merge-main")
R42 = "DC_Rack42_SplitFrontRear"
R24 = "DC_Rack24_Open"


def _shot(nm, cam, tgt, lens, floor=(-2.5, 2.5, -2.5, 2.5)):
    PV.OUT = OUT
    s = PV.Shot(nm, floor=floor)
    s.camera(cam, tgt, lens)
    return s


def render_all(built):
    out = []
    if R42 in built:
        H = 0.25 * catalog.BY_NAME[R42].cells[1]
        # rear 3/4, rear doors open: both feeds' strips in the PDU columns, the servers seated against the rear stop,
        # the back containment rail on the tray band
        nm = "rack42_rear34_strips_rails"
        if want(nm):
            s = _shot(nm, (-1.7, -3.1, 2.3), (0.0, 0.0, 1.2), 35)
            P7.rack_with_strips(s, built, R42, f=0.0, f_rear=1.0)
            out.append(s.render())
        # front 3/4, front doors open: the seated servers, the front containment rail and the header placard
        nm = "rack42_front34_rails_servers"
        if want(nm):
            s = _shot(nm, (1.6, 3.2, 2.2), (0.0, 0.0, 1.25), 35)
            P7.rack_with_strips(s, built, R42, f=1.0, f_rear=0.0)
            out.append(s.render())
        # the front header: "RACK" caption + blank write-on tag + power-OK lamp, the containment rail and tag under it
        nm = "rack42_header_placard"
        if want(nm):
            s = _shot(nm, (0.25, 1.55, H - 0.05), (0.0, 0.6, H - 0.17), 45)
            P9.rack(s, built, R42, mix=P7.MIX42, working=True)
            out.append(s.render())
        # the side hatch placard: "RACK ID" over the blank tag (no baked A1 / ROW A POS 1)
        nm = "rack42_side_placard"
        if want(nm):
            L = rack_side.layout(catalog.BY_NAME[R42])
            mid = sum(L["m"]) / 2
            h1 = L["hatch"][1]
            s = _shot(nm, (0.5 + 0.75, mid + 0.15, h1 - 0.10), (0.5, mid, h1 - 0.16), 40)
            P9.rack(s, built, R42, mix=P7.MIX42, working=True)
            out.append(s.render())
    if R24 in built:
        H = 0.25 * catalog.BY_NAME[R24].cells[1]
        # the half rack's roof ID plate (read from the front) and its kick-plate label
        nm = "rack24_roof_and_kick_placards"
        if want(nm):
            s = _shot(nm, (0.35, 1.9, H + 0.9), (0.0, 0.15, H * 0.55), 35)
            P7.rack_with_strips(s, built, R24, f=0.0)
            out.append(s.render())
    if "DC_CRAC" in built:
        nm = "crac_3q_front_right"
        if want(nm):
            s = _shot(nm, (3.6, 4.9, 2.2), (0.0, 0.0, P6.ZC * 0.95), 50, floor=(-2.0, 2.0, -2.0, 2.0))
            P6.unit(s, built, T(0, 0, P6.ZC), 17.0)
            out.append(s.render())
        nm = "crac_beside_rack"
        if want(nm) and R42 in built:
            s = _shot(nm, (2.4, 5.2, 2.3), (-0.5, 0.0, 1.2), 35, floor=(-3.0, 3.0, -2.5, 2.5))
            P6.unit(s, built, T(0.5, 0, P6.ZC), 17.0)
            P7.rack_with_strips(s, built, R42, x=-0.5, f=0.0)
            out.append(s.render())
    for p in out:
        print("MERGE", p)
