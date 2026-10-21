"""Plan 3 Task 12: the final hero set, the whole reference hall (dc/room.two_aisle_room).

    DC_PREVIEW=plan3-t12 blender -b --python Source/Model/build_dc.py -- "DC_Rack42_SplitFront" "DC_Srv_*" \
        "DC_Tray_Drop_Full" "DC_Tray_StraightS_Full" "DC_TrayRods_100" "DC_Floor_*" DC_CRAC "DC_PDU_*" \
        DC_Contain_Door_150 DC_Contain_Roof_150 DC_Contain_Door_100 DC_Contain_Roof_100 "DC_Sign_*"

Three rows, a contained 1.5 m COLD aisle (rows A and B face it) and a contained 1.0 m HOT aisle (rows B and C turn
their backs to it), trays on rods with a Drop into every rack, a hanging sign over each aisle, the aisle signs on the
door headers, rack labels, three CRACs and three PDU cabinets. Writes Source/Model/preview/plan3-task-12/ (DC_SHOTS
filters, DC_FAST halves the resolution):
  hall_photo1           the photo 1 camera (docs/ideas/reference/datacenter/01) in the cold aisle
  hall_photo1_black     the same with black racks (the paint most real halls use)
  hall_cold_eye         the cold aisle at 1.7 m eye height
  hall_hot_eye          the hot aisle at eye height (rack backs, PDU strips)
  hall_doors_outside    outside both west doors: the cold and the hot aisle side by side, signs on their headers
  hall_overhead         overhead, the ceiling cut away: both aisles' roofs, trays, CRACs, cabinets
  hall_crac_header      close: a CRAC's front header, the neutral "CRAC" caption and its blank riveted ID tag
"""
import os

from . import config, room
from . import preview as PV
from . import preview_room as PR

COLD_W, HOT_W = 1.5, 1.0


def _geo():
    L = room.PITCH * len(room.row_units(4))
    x0, x1, y0, y1 = room.hall_extent(COLD_W, HOT_W)
    return L, x0, x1, y0, y1, room.hot_offset(COLD_W, HOT_W)


def cam_hot_eye(info):
    L, *_, dy = _geo()
    return PR.Cam((0.45, dy - 0.18 * HOT_W, 1.7), (L - 0.4, dy + 0.06 * HOT_W, 1.42), 16)


def cam_doors_outside(info):
    L, x0, x1, y0, y1, dy = _geo()
    yc = (0.0 + dy) / 2
    return PR.Cam((x0 + 0.35, yc - 0.15, 1.65), (0.0, yc, 1.75), 15)


def cam_overhead(info):
    L, x0, x1, y0, y1, dy = _geo()
    return PR.Cam((L / 2 - 2.4, y0 - 3.4, 10.2), (L / 2 + 0.2, dy / 2, 1.0), 19, ("ceiling", "luminaires", "wall_south"))


def cam_crac_header(info):
    """Row A's CRAC front header from inside the cold aisle: the neutral "CRAC" caption and its blank ID tag (T12)."""
    x = room.PITCH * (room.row_units(4).index("crac") + 0.5)
    yf = -COLD_W / 2
    z = room.STACK["rack_top"] - 0.17
    return PR.Cam((x - 0.25, yf + 0.9, z - 0.25), (x, yf, z), 50)


SHOTS = (("hall_photo1", "photo1", None, "keen"), ("hall_photo1_black", "photo1", None, "black"),
         ("hall_cold_eye", "aisle_eye", None, "keen"), ("hall_hot_eye", "hot_eye", cam_hot_eye, "keen"),
         ("hall_doors_outside", "doors_outside", cam_doors_outside, "keen"),
         ("hall_overhead", "overhead", cam_overhead, "keen"),
         ("hall_crac_header", "crac_header", cam_crac_header, "keen"))


def render_all(built):
    out = os.path.join(config.PREVIEW_DIR, "plan3-task-12", os.environ.get("DC_PREVIEW_SUB", ""))
    os.makedirs(out, exist_ok=True)
    PR.OUT = PV.OUT = out
    for name, cam, fn, paint in SHOTS:
        PR.shot(built, cam, COLD_W, "cold", paint=paint, name=name, captions=False, hall=HOT_W, cam_fn=fn)
