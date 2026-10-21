"""Visual fix pass (in-game z-fighting report): close-ups of the rack side panel labels and the door leaf edges.

    DC_PREVIEW=zfix DC_ZFIX_SET=before blender -b --python Source/Model/build_dc.py -- DC_Rack42_SplitFrontRear
Writes preview/visual-fixes/<set>/ (set = DC_ZFIX_SET, default "after"); previews stay out of git."""
import os

from mathutils import Vector

from . import catalog, config, rack_side
from . import preview as PV
from . import preview_task10 as P10
from . import preview_vp1 as VP

SET = os.environ.get("DC_ZFIX_SET", "after")
OUT = os.environ.get("DC_ZFIX_OUT") or os.path.join(config.PREVIEW_DIR, "visual-fixes", SET)
RACK = "DC_Rack42_SplitFrontRear"


def _shot(built, name, cam, tgt, lens=50, f=0.0):
    s = VP._scene(name)
    spec = catalog.BY_NAME[RACK]
    P10.rack(s, built, RACK, f=f, f_rear=0.0, paint="keen", mix=(), fan=20, working=True)
    s.camera(tuple(cam), tuple(tgt), lens)
    VP._lights(s, tgt)
    PV.OUT = OUT
    return s.render()


def render_all(built):
    if RACK not in built:
        print("zfix previews need", RACK)
        return
    L = rack_side.layout(catalog.BY_NAME[RACK])
    m0, m1 = L["m"]
    mid = (m0 + m1) / 2
    h0, h1 = L["hatch"]
    b0, b1 = L["band"]
    x = 0.5
    out = []
    # the side panel: the whole PDU hatch, then the service band, then the full side at 2 m
    out.append(_shot(built, "side_hatch_labels", Vector((x + 1.7, mid + 0.35, (h0 + h1) / 2 + 0.1)),
                     Vector((x, mid, (h0 + h1) / 2)), lens=40))
    out.append(_shot(built, "side_hatch_upper", Vector((x + 0.6, mid + 0.12, h1 - 0.12)),
                     Vector((x, mid, h1 - 0.16)), lens=40))
    out.append(_shot(built, "side_hatch_lower", Vector((x + 0.55, mid + 0.12, h0 + 0.22)),
                     Vector((x, mid - 0.02, h0 + 0.18)), lens=40))
    out.append(_shot(built, "side_band", Vector((x + 0.6, mid + 0.15, (b0 + b1) / 2 + 0.08)),
                     Vector((x, mid, (b0 + b1) / 2)), lens=40))
    out.append(_shot(built, "side_full_2m", Vector((x + 3.6, 1.5, 1.6)), Vector((x, 0.0, 1.25)), lens=30))
    # the door leaves' meeting edge (closed, then the front pair half open: the edge side faces the camera)
    out.append(_shot(built, "door_meeting_edge", Vector((0.22, 0.95, 1.35)), Vector((0.0, 0.612, 1.2)), lens=60))
    # front-left leaf half open (yaw 42.5 deg about its hinge at (-0.474, 0.6115)): look straight at its free edge
    out.append(_shot(built, "door_edge_open", Vector((0.30, 1.30, 1.45)), Vector((-0.126, 0.93, 1.25)), lens=55,
                     f=0.5))
    out.append(_shot(built, "door_edge_open_close", Vector((0.05, 1.10, 1.30)), Vector((-0.126, 0.93, 1.22)),
                     lens=55, f=0.5))
    out.append(_shot(built, "door_hinge_edge", Vector((0.85, 0.95, 1.05)), Vector((0.47, 0.612, 1.0)), lens=60))
    for p in out:
        print("ZFIX", p)
