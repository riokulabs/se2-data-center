"""Rack placement renders: the parts of the rack the block placer depends on (the open slot front, the rear stop brackets, the
slot-1 deck 25 mm under the slot floor, the tray floor's raised underside).

    DC_PREVIEW=rack-placement DC_RACK_PLACEMENT_SET=after blender -b --python Source/Model/build_dc.py -- DC_Rack42_Open DC_Srv_Compute
Writes preview/rack-placement/<set>/render_*.png (set = DC_RACK_PLACEMENT_SET, default "after"); previews stay out of git."""
import os

from mathutils import Vector

from . import config
from . import preview as PV
from . import preview_icons as pv_icons
from . import preview_block_views as VP

SET = os.environ.get("DC_RACK_PLACEMENT_SET", "after")
OUT = os.environ.get("DC_RACK_PLACEMENT_OUT") or os.path.join(config.PREVIEW_DIR, "rack-placement", SET)
RACK = "DC_Rack42_Open"
MIX = (None, "DC_Srv_Compute", None, "DC_Srv_Compute", None, None, "DC_Srv_Compute", None)


def _shot(built, name, cam, tgt, lens=40):
    s = VP._scene(name)
    pv_icons.rack(s, built, RACK, paint="keen", mix=MIX, fan=20, working=True)
    s.camera(tuple(cam), tuple(tgt), lens)
    VP._lights(s, tgt)
    PV.OUT = OUT
    return s.render()


def render_all(built):
    if RACK not in built or "DC_Srv_Compute" not in built:
        print("rack-placement previews need", RACK, "and DC_Srv_Compute")
        return
    out = [
        # the lower slots from the aisle: slot 1 empty (the deck under it), slot 2 a server, slot 3 empty
        _shot(built, "render_front_lower", Vector((0.55, 1.9, 1.0)), Vector((0.0, 0.0, 0.6)), lens=40),
        # into empty slot 1 at its rear: the rear stop brackets on the rear rails and the deck gap
        _shot(built, "render_slot1_rear", Vector((0.12, 0.95, 0.42)), Vector((0.0, -0.36, 0.33)), lens=35),
        # from behind (the open rack's rear): the brackets behind each slot and the servers' backs
        _shot(built, "render_rear", Vector((-0.7, -2.0, 1.3)), Vector((0.0, -0.35, 1.0)), lens=40),
        # the top slot's ceiling: the tray floor's underside 25 mm over the slot
        _shot(built, "render_top_slot", Vector((0.25, 1.1, 1.95)), Vector((0.0, -0.2, 2.2)), lens=35),
    ]
    for p in out:
        print("PFIX", p)
