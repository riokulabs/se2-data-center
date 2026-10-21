"""Room comparison previews: the same room cameras before and after a visual change.

    DC_PREVIEW=room-compare DC_COMPARE_PHASE=before|after blender -b --python Source/Model/build_dc.py -- \
        "DC_Floor_*" DC_CRAC "DC_PDU_*" "DC_Contain_*" "DC_Sign_*" DC_Rack42_SplitFront "DC_Srv_*" \
        DC_Tray_Drop_Full DC_Tray_StraightS_Full DC_TrayRods_100

Writes Source/Model/preview/room-compare/<phase>/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution):
  room_photo1 / room_photo1_black   the photo 1 camera (docs/ideas/reference/datacenter/01), keen and black racks
  room_photo4 / room_photo4_black   the photo 4 camera (04: high at the row end, along the rack tops and trays)
  room_hero06                       the v1 / v2 mockup "06-room-hero" camera (inside the aisle, lens 17)
  room_eye_west / room_eye_east     the contained cold aisle at 1.7 m eye height from both ends
  room_hot_eye_west / _east         the same in the hot-aisle room
  room_door_outside / room_overhead / room_end_row   the room's standard cameras
  room_inside_up                    standing in the contained aisle looking up at the rack tops (labels, roof)
  room_labels_open_side             the rack tops seen from the open (hot) side of a contained cold aisle
  joint_rack_top / joint_door_pocket / joint_roof_clamp / joint_pdu_inlet / joint_floor_seam
                                    every coupling joint at ~0.5 m
  vs_<block>_front / _back          each room block beside its vanilla source at the same scale and light
  vanilla_sources                   every room source in one line beside a 42U rack
  crac_rear / crac_rear_close       the CRAC's hot-aisle face (the service bay)
  crac_controller                   the controller panel (stencil contrast)
  crac_lods                         LOD0..n with their budgets
  door_pull_closed / door_pull_open the containment door's meeting stiles and pulls (the z-fight fixes)
  pdu_bank_head                     a rack PDU strip's bank head labels
  rail_tag                          the CRAC's CONTAINMENT tag in the rail channel
"""
import math
import os

from mathutils import Vector

from . import catalog, config, room
from . import preview as PV
from . import preview_room as PR
from .preview import Rz, T, want

PHASE = os.environ.get("DC_COMPARE_PHASE", "before")
VAN = {"floor": "Catwalks/CatwalkSquareBase/250/Models/NonFractured/CatwalkSquareBase_250.fbx",
       "crac": "Gyroscopes/Gyroscopes/250/Models/NonFractured/Base/Gyroscope250_Base.fbx",
       "pdu_cabinet": "Batteries/Battery/50/Models/NonFractured/Battery50.fbx",
       "pdu_strip": "Walls/Inserts/Vent/Models/NonFractured/WallInsertVent.fbx",
       "contain_door": "Doors/SlideDoorNarrow/250/Models/NonFractured/NarrowSlidingDoor.fbx",
       "contain_roof": "DeckPanel/250/Models/NonFractured/DeckPanel250.fbx",
       "sign": "LCDPanels/NarrowLCD/50/Models/Nonfractured/NarrowLCD50.fbx"}
OPEN_LABEL_SHOTS = ("room_labels_open_side", "room_inside_up", "room_eye_west")   # after: the label guidance
PAIRS = ("DC_Floor_Perf_100", "DC_Floor_Solid_100", "DC_CRAC", "DC_PDU_Cabinet", "DC_PDU_Rack42_A",
         "DC_Contain_Door_150", "DC_Contain_Roof_150", "DC_Sign_Aisle", "DC_Sign_AisleHang", "DC_Sign_Rack")


def _out():
    out = os.path.join(config.PREVIEW_DIR, "room-compare", PHASE)
    os.makedirs(out, exist_ok=True)
    PR.OUT = PV.OUT = out


# ---------------------------------------------------------------------------------------------------- room
def _cam(nm, loc, target, lens, hide=()):
    PR.CAMERAS[nm] = lambda info, c=PR.Cam(loc, target, lens, hide): c


def _room_cams():
    """The comparison cameras in the 1.5 m reference room (rows A at y < 0, B at y > 0, aisle centred on y = 0)."""
    w = 1.5
    L = room.PITCH * len(room.row_units(4))
    # photo 4 (docs/ideas/reference/datacenter/04): high at a row's end, looking down along its rack tops, the RACK
    # labels on the front edges, the trays on rods above, the walkway (the racks' fronts) to the right: the HOT room,
    # whose row B faces its outer walkway (+y), seen from the east end looking -x
    _cam("photo4", (L + 0.9, 2.45, 3.45), (0.25 * L, 1.55, 2.2), 20, ("luminaires",))
    _cam("hero06", (0.3, 0.12, 1.87), (L - 0.4, -0.1, 2.15), 17)
    _cam("eye_west", (0.45, -0.18 * w, 1.95), (L - 0.4, 0.06 * w, 1.67), 17)
    _cam("eye_east", (L - 0.45, 0.18 * w, 1.95), (0.4, -0.06 * w, 1.67), 17)
    _cam("inside_up", (1.0, 0.25, 1.95), (1.6, -0.9, 2.95), 18)
    _cam("labels_open_side", (2.6, -2.85, 1.95), (1.6, -1.45, 2.8), 16)
    _cam("joint_rack_top", (1.15, -0.45, 3.1), (1.5, -0.8, 2.78), 24)
    _cam("joint_door_pocket", (-0.75, -0.35, 1.7), (-0.125, -0.8, 1.5), 24)
    _cam("joint_roof_clamp", (1.0, -0.25, 2.2), (1.0, -0.74, 2.55), 24)
    _cam("joint_pdu_inlet", (0.75, -2.55, 0.75), (0.65, -1.95, 0.45), 26)
    _cam("joint_floor_seam", (2.35, -0.25, 0.75), (2.0, -0.72, 0.3), 24)


def room_shots(built):
    _room_cams()
    for nm, cam, aisle, paint in (("room_photo1", "photo1", "cold", "keen"), ("room_photo1_black", "photo1", "cold",
                                                                              "black"),
                                  ("room_photo4", "photo4", "hot", "keen"), ("room_photo4_black", "photo4", "hot",
                                                                              "black"),
                                  ("room_hero06", "hero06", "cold", "keen"), ("room_eye_west", "eye_west", "cold", "keen"),
                                  ("room_eye_east", "eye_east", "cold", "keen"),
                                  ("room_hot_eye_west", "eye_west", "hot", "keen"),
                                  ("room_hot_eye_east", "eye_east", "hot", "keen"),
                                  ("room_door_outside", "door_outside", "cold", "keen"),
                                  ("room_overhead", "overhead", "cold", "keen"), ("room_end_row", "end_row", "cold", "keen"),
                                  ("room_inside_up", "inside_up", "cold", "keen"),
                                  ("room_labels_open_side", "labels_open_side", "cold", "keen"),
                                  ("joint_rack_top", "joint_rack_top", "cold", "keen"),
                                  ("joint_door_pocket", "joint_door_pocket", "cold", "keen"),
                                  ("joint_roof_clamp", "joint_roof_clamp", "cold", "keen"),
                                  ("joint_pdu_inlet", "joint_pdu_inlet", "cold", "keen"),
                                  ("joint_floor_seam", "joint_floor_seam", "cold", "keen")):
        kw = {"label_side": "open"} if PHASE == "after" and nm in OPEN_LABEL_SHOTS else {}   # (before: HEAD's API)
        PR.shot(built, cam, 1.5, aisle, paint=paint, name=nm, captions=False, **kw)


# ---------------------------------------------------------------------------------------------------- blocks
def _place(s, built, name, M, paint="keen", lod=0):
    fam = catalog.BY_NAME[name].family
    if fam == "crac":
        PR.crac_unit(s, built, name, M, 17.0, True, paint, lod)
    elif fam == "contain_door":
        PR.contain_door(s, built, name, M, 0.0, paint, lod)
    elif fam == "sign":
        from . import preview_signs as P8
        P8.place(s, built, name, M, paint="blue", lod=lod)
    else:
        s.inst(PV.painted(built, name, lod, paint), M)


def pairs(built):
    """Each room block beside its vanilla clone source, same scale, same light, front and back 3/4."""
    for name in PAIRS:
        if name not in built:
            continue
        spec = catalog.BY_NAME[name]
        sx, sz, sy = (0.25 * c for c in spec.cells)
        c, lo, hi = PV.vanilla(VAN[spec.family])
        vw = hi.x - lo.x
        span = max(sx + vw + 0.6, 1.6, sz * 1.4)
        for view, sgn in (("front", 1), ("back", -1)):
            nm = f"vs_{name}_{view}"
            if not want(nm):
                continue
            s = PV.Shot(nm, res=(1800, 1100), floor=(-span, span, -span, span))
            _place(s, built, name, T(sx / 2 + 0.3, 0, sz / 2))
            ctr = (lo + hi) / 2
            s.inst(c, T(-vw / 2 - 0.3, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
            zc = max(sz, hi.z - lo.z) / 2
            D = 1.6 * span + 0.6
            s.camera((sgn * 0.45 * D, sgn * 0.85 * D, zc + 0.35 * D), (0, 0, zc), 40)
            s.caption(f"ours: {name}", (sx / 2 + 0.3, 0, max(sz, 0.25) + 0.18), 0.05 + 0.02 * span)
            s.caption(f"vanilla {os.path.basename(VAN[spec.family])[:-4]}", (-vw / 2 - 0.3, 0, hi.z - lo.z + 0.18),
                      0.05 + 0.02 * span)
            s.render()


def _studio(nm, built, name, cam, target, lens, paint="keen", res=(1800, 1150), f=0.0):
    if not want(nm) or name not in built:
        return
    spec = catalog.BY_NAME[name]
    H = 0.25 * spec.cells[1]
    s = PV.Shot(nm, res=res, floor=(-2, 2, -2, 2))
    if spec.family == "contain_door":
        PR.contain_door(s, built, name, T(0, 0, H / 2), f, paint)
    else:
        _place(s, built, name, T(0, 0, H / 2), paint)
    s.camera(cam, target, lens)
    s.render()


def closeups(built):
    _studio("crac_rear", built, "DC_CRAC", (1.6, -5.2, 1.6), (0, 0, 1.2), 40)
    _studio("crac_rear_close", built, "DC_CRAC", (0.9, -2.4, 1.05), (0.0, -0.6, 0.72), 35)
    _studio("crac_controller", built, "DC_CRAC", (-0.25, 1.35, 2.15), (0.0, 0.58, 2.05), 40)
    _studio("rail_tag", built, "DC_CRAC", (0.15, 1.05, 2.45), (0.0, 0.62, 2.33), 50)
    _studio("door_pull_closed", built, "DC_Contain_Door_150", (0.35, 0.75, 1.2), (0.0, 0.0, 1.05), 30)
    _studio("door_pull_open", built, "DC_Contain_Door_150", (-0.35, 0.75, 1.2), (-0.72, 0.0, 1.05), 30, f=1.0)
    _studio("pdu_bank_head", built, "DC_PDU_Rack42_A", (0.35, -0.55, 0.9), (0.0, 0.0, 0.75), 30)
    if "DC_CRAC" in built:
        PV.lods(built, "DC_CRAC")
        src = os.path.join(PV.OUT, "DC_CRAC_lods.png")
        if os.path.exists(src):
            os.replace(src, os.path.join(PV.OUT, "crac_lods.png"))


def render_all(built):
    _out()
    closeups(built)
    pairs(built)
    if want("vanilla_sources"):
        PR.vanilla_sources(built)
    room_shots(built)
