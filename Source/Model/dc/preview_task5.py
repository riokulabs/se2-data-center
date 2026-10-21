"""Task-5 fix-round previews (Source/Model/preview/task-5/): the black populated row, and close-ups of the shared
side plane of two flush full racks (the render mesh now stops 1 mm inside each side plane: a 2 mm hairline gap,
no coplanar faces). Needs the same blocks as the Task-4 set:
    blender -b --python Source/Model/build_dc.py -- DC_Rack42_Open DC_Rack24_Open DC_Srv_Blank DC_Srv_Compute \
        DC_Srv_Storage DC_Srv_Switch       with DC_PREVIEW=task5
"""
import os

from . import config
from . import preview as PV
from . import preview_mats as PM
from .preview import Shot, want
from .preview_servers import FULL, FULL_MIX, HALF, HALF_MIX, _rack

OUT = os.path.join(config.PREVIEW_DIR, "task-5")


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    nm = "racks_row_black_populated"
    if want(nm):
        s = Shot(nm, res=(2200, 1250), floor=(-3, 2, -2, 4))
        _rack(s, built, FULL, FULL_MIX, x=0.0, paint="black")
        _rack(s, built, FULL, tuple(reversed(FULL_MIX)), x=-1.0, paint="black")
        _rack(s, built, HALF, HALF_MIX, x=-2.0, paint="black")
        s.camera((1.4, 4.2, 1.9), (-1.0, 0, 1.15), 32)
        s.render()
    # two flush full racks (centres 1.0 m apart): the shared plane is x = -0.5
    shots = {
        "flush_racks_shared_side_front_closeup": ((-0.38, 0.95, 2.35), (-0.5, 0.55, 2.2), 55, None),
        "flush_racks_shared_side_top_closeup": ((-0.5, 0.40, 3.4), (-0.5, 0.40, 2.5), 60, None),
        "flush_racks_shared_side_plinth_closeup": ((-0.30, 1.05, 0.30), (-0.5, 0.58, 0.14), 50, None),
    }
    for nm, (loc, tgt, lens, ortho) in shots.items():
        if not want(nm):
            continue
        s = Shot(nm, floor=(-3, 2, -2, 4))
        _rack(s, built, FULL, FULL_MIX, x=0.0, paint="black")
        _rack(s, built, FULL, tuple(reversed(FULL_MIX)), x=-1.0, paint="keen")
        s.camera(loc, tgt, lens, ortho)
        s.render()
