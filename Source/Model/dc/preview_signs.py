"""Sign previews: the signs and labels (DC_Sign_Aisle, DC_Sign_AisleHang, DC_Sign_Rack).

    DC_PREVIEW=signs blender -b --python Source/Model/build_dc.py -- "DC_Sign_*" "DC_Contain_Door_*" \
        "DC_TrayRods_*" "DC_Tray_Drop_*" "DC_Tray_StraightS_Full" "DC_Rack42_*" "DC_Rack24_*" "DC_Srv_*" "DC_Floor_*" \
        "DC_Contain_Roof_*"

Writes Source/Model/preview/signs/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution). The
screens show sample text ("AISLE 1 COLD", "RACK 1.01": a preview-only text overlay; in game the player types it):
  <sign>_34 / _front / _side / _back / _top   hero views (cold = blue frame, the label hot = red), the hardware close
  <sign>_lods                                 LOD0..n
  aisle_on_door_<w>                           the aisle sign on each containment door's header (1.0 / 1.5 / 2.0 m)
  aisle_on_door_bolts                         the back plate's bolts on the header's threaded inserts (door cut away)
  aisle_on_wall                               on a hall wall
  hang_on_rods / hang_rods_close              the hanging sign under a turned DC_TrayRods_100 over an aisle
  rack_labels_row_<aisle>                     labels along a populated row with Drops (photo 1 framing), cold / hot
  rack_label_close / rack_label_24u           a label between a Drop's waterfalls; on a half rack under a Chute
  legibility_<d>m                             the aisle sign read at 2, 5 and 15 m (eye height)
  fracture_<sign>                             the fracture tiles pulled apart
  paints_*                                    keen, black, blue (cold), red (hot)
  vanilla_compare                             beside vanilla NarrowLCD50 (the clone source) and LCDWide/NarrowLCD250
  room_*                                      the reference room (dc/preview_room.py): door outside, aisle eye, rack
                                              top, photo 1, overhead; cold and hot
Contact sheet: python3 Source/Model/signs_sheet.py.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix

from . import catalog, room, signs
from . import dims as DM
from . import preview as PV
from . import preview_room as PR
from .preview import Rz, T, want

SIGNS = ("DC_Sign_Aisle", "DC_Sign_AisleHang", "DC_Sign_Rack")
TEXT = {"DC_Sign_Aisle": "AISLE 1 COLD", "DC_Sign_AisleHang": "AISLE 1 COLD", "DC_Sign_Rack": "RACK 1.01"}
TEXT_SIZE = {"DC_Sign_Aisle": 0.105, "DC_Sign_AisleHang": 0.084, "DC_Sign_Rack": 0.062}
PAINT = {"DC_Sign_Aisle": "blue", "DC_Sign_AisleHang": "blue", "DC_Sign_Rack": "blue"}
_CUT = {}


def _out():
    PR._out("signs")


def _spec(name):
    return catalog.BY_NAME[name]


def _face_matrix(scr):
    """A matrix at a screen's centre whose +Y is the screen's normal and +Z its up (preview_room.text faces +Y)."""
    from mathutils import Vector
    n, up = Vector(scr.normal), Vector(scr.up)
    x = n.cross(up)
    R = Matrix((x, n, up)).transposed().to_4x4()
    return T(*scr.center) @ R


def screen_text(coll, name, M, text=None, key="text_white", size=None):
    """Sample text on every screen of a sign placed at M (preview only: the LCD shows what the player types)."""
    out = []
    for scr in signs.screens(_spec(name)):
        body = text if text is not None else TEXT[name]
        out.append(PR.text(coll, body, M @ _face_matrix(scr) @ T(0, 0.0012, 0), size or TEXT_SIZE[name], key,
                           f"txt_{name}_{scr.face}"))
    return out


def place(s, built, name, M, paint=None, text=None, key="text_white", lod=0):
    """A built sign at M, painted, with sample text on its screens (in the Shot s)."""
    s.inst(PV.painted(built, name, lod, paint or PAINT[name]), M)
    if lod == 0:
        screen_text(s.sc.collection, name, M, text, key)


def _new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    PV._exclude(c)
    return c


# ---------------------------------------------------------------------------------------------------- hero
ZS = {"DC_Sign_Aisle": 0.55, "DC_Sign_AisleHang": 0.55, "DC_Sign_Rack": 0.35}


def hero(built, name):
    zc = ZS[name]
    sx = 1.0 if name != "DC_Sign_Rack" else 0.5
    D = 1.6 * sx + 0.4
    views = {"34": ((-0.62 * D, 0.82 * D, zc + 0.30 * D), 40), "front": ((0.0, D, zc), 40),
             "side": ((D, 0.0, zc + 0.05), 40), "back": ((0.45 * D, -0.9 * D, zc + 0.2 * D), 40),
             "top": ((0.25 * D, 0.55 * D, zc + D), 40)}
    for v, (loc, lens) in views.items():
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = PV.Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        place(s, built, name, T(0, 0, zc))
        s.camera(loc, (0, 0, zc), lens)
        s.render()


def close(built, name):
    """The hardware close-up: the bezel bolts and tab (aisle), the hangers (hanging), the foot (label)."""
    zc = ZS[name]
    cams = {"DC_Sign_Aisle": ((0.62, 0.42, zc + 0.18), (0.40, -0.03, zc), 38),
            "DC_Sign_AisleHang": ((0.42, 0.34, zc + 0.24), (0.232, 0.0, zc + 0.10), 42),
            "DC_Sign_Rack": ((0.34, 0.42, zc + 0.05), (0.10, 0.02, zc - 0.07), 40)}
    nm = f"{name}_close"
    if not want(nm):
        return
    loc, tgt, lens = cams[name]
    s = PV.Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
    place(s, built, name, T(0, 0, zc))
    s.camera(loc, tgt, lens)
    s.render()


def lods(built, name):
    import json
    from . import config
    nm = f"{name}_lods"
    if not want(nm):
        return
    n = len(built[name]["lods"])
    sx = 1.15 if name != "DC_Sign_Rack" else 0.6
    s = PV.Shot(nm, res=(2200, 900), floor=(-sx * n - 1, 1, -1, 1))
    for i in range(n):
        place(s, built, name, T(-sx * i, 0, ZS[name]), lod=i)
    cx = -sx * (n - 1) / 2
    s.camera((cx, 1.3 * sx * n + 0.8, ZS[name] + 0.35), (cx, 0, ZS[name]), 45)
    with open(config.REPORT_PATH) as f:
        rep = json.load(f)["blocks"].get(name, {})
    for i in range(n):
        lr = rep.get("lods", [{}] * n)[i]
        s.caption(f"LOD{i}\n{lr.get('tris', '?')}/{lr.get('max_tris', '?')} tris", (-sx * i, 0.0, ZS[name] + 0.3),
                  0.04)
    s.render()


# ---------------------------------------------------------------------------------------------------- in place
def _wall(s, x0, x1, y, z1, key="wall"):
    m = PR.Mesh()
    m.box((x0, y - 0.2, 0.0), (x1, y, z1), key)
    for z in (0.32, 1.45):
        m.box((x0, y - 0.004, z - 0.006), (x1, y + 0.002, z + 0.006), "Darker")
    m.obj(s.sc.collection, "wall")


DOOR_W = {"DC_Contain_Door_100": 1.0, "DC_Contain_Door_150": 1.5, "DC_Contain_Door_200": 2.0}


def on_doors(built):
    """The aisle sign on each containment door's header (room side), the door closed; and the bolts: the sign
    pulled 0.3 m off the header, its back plate's four bolts in line with the fascia's threaded inserts."""
    for door, w in DOOR_W.items():
        if door not in built:
            continue
        nm = f"aisle_on_door_{round(w * 100)}"
        if want(nm):
            s = PV.Shot(nm, floor=(-w - 1, w + 1, -1.5, 3.5))
            M = T(0, 0, 1.25)
            PR.contain_door(s, built, door, M, 0.0, "keen")
            place(s, built, "DC_Sign_Aisle", M @ T(0, DM.CELL, 1.125))
            s.inst(PV.human(), T(w * 0.35, 1.2, 0.0))
            s.camera((0.9 + 0.3 * w, 3.4 + 0.6 * w, 1.7), (0.0, 0.2, 1.75), 32)
            s.render()
    door = "DC_Contain_Door_150"
    nm = "aisle_on_door_bolts"
    if door in built and want(nm):
        s = PV.Shot(nm, floor=(-2.5, 2.5, -1.5, 3.5))
        M = T(0, 0, 1.25)
        PR.contain_door(s, built, door, M, 0.0, "keen")
        place(s, built, "DC_Sign_Aisle", M @ T(0, DM.CELL + 0.30, 1.125))
        s.camera((0.98, 0.31, 2.40), (0.10, 0.27, 2.36), 24)   # in the gap: the fascia's inserts and the back plate
        s.render()


def on_wall(built):
    nm = "aisle_on_wall"
    if not want(nm):
        return
    s = PV.Shot(nm, floor=(-3, 3, -0.2, 4))
    _wall(s, -3.0, 3.0, 0.0, 3.6)
    place(s, built, "DC_Sign_Aisle", T(0, DM.CELL / 2, 2.3))
    place(s, built, "DC_Sign_Aisle", T(-1.6, DM.CELL / 2, 2.3), paint="red", text="AISLE 2 HOT")
    s.inst(PV.human(), T(0.7, 1.0, 0.0))
    s.camera((0.8, 3.6, 1.7), (-0.5, 0.0, 1.95), 30)
    s.render()


def legibility(built):
    """The aisle sign on a wall at the door header's height (centre 2.375 m), read from eye height (1.7 m) at 2, 5
    and 15 m, a human-like field of view (35 mm lens)."""
    for d in (2, 5, 15):
        nm = f"legibility_{d}m"
        if not want(nm):
            continue
        s = PV.Shot(nm, res=(1600, 900), floor=(-6, 6, -0.2, 17), light=0.8)
        _wall(s, -6.0, 6.0, 0.0, 4.0)
        place(s, built, "DC_Sign_Aisle", T(0, DM.CELL / 2, 2.375))
        s.camera((0.3, float(d), 1.7), (0.0, 0.0, 2.2), 35)
        s.render()


def hang(built):
    """The hanging sign on a DC_TrayRods_100 turned 90 deg to it (room.reference_room), from the aisle and close on
    a hanger: the rod's coupler nut on the sign's rod plate, the turnbuckle, the lug."""
    rods = "DC_TrayRods_100"
    if rods not in built:
        return
    zs = 2.875
    Ms = T(0, 0, zs) @ Rz(90)
    Mr = T(0, 0, zs + DM.CELL / 2 + 0.5)
    nm = "hang_on_rods"
    if want(nm):
        s = PV.Shot(nm, floor=(-3, 3, -3, 3), light=0.9)
        place(s, built, "DC_Sign_AisleHang", Ms)
        s.inst(PV.painted(built, rods, 0, "keen"), Mr)
        m = PR.Mesh()
        m.box((-1.5, -1.5, zs + 1.125), (1.5, 1.5, zs + 1.2), "ceiling")
        m.obj(s.sc.collection, "ceiling")
        s.camera((2.6, 1.0, 1.7), (0.0, 0.0, zs + 0.15), 30)
        s.render()
    nm = "hang_rods_close"
    if want(nm):
        s = PV.Shot(nm, floor=(-3, 3, -3, 3), light=0.9)
        place(s, built, "DC_Sign_AisleHang", Ms)
        s.inst(PV.painted(built, rods, 0, "keen"), Mr)
        s.camera((0.32, 0.42, zs + 0.06), (0.0, 0.232, zs + 0.12), 40)
        s.render()
    nm = "hang_back_face"
    if want(nm):
        s = PV.Shot(nm, floor=(-3, 3, -3, 3), light=0.9)
        place(s, built, "DC_Sign_AisleHang", Ms, text=None)
        s.inst(PV.painted(built, rods, 0, "keen"), Mr)
        s.camera((-2.6, -1.0, 1.7), (0.0, 0.0, zs + 0.15), 30)
        s.render()


def _no_containment(fn):
    """room.reference_room without the containment (roof, doors, door signs): the photo 1 hall."""
    def f(*a, **k):
        return [p for p in fn(*a, **k) if room.spec(p).family not in ("contain_roof", "contain_door")
                and not p.tag.endswith(("west/sign", "east/sign"))]
    return f


def row_shots(built):
    """Rack labels along a populated row with Drops (photo 1 framing), cold and hot, the containment left out so
    the row reads as in the photo; the hanging sign over the aisle from eye height."""
    def row(info):      # standing in the aisle near the row's west end, looking down row A's tops
        w, L, *_ = PR._geo(info)
        return PR.Cam((-0.4, -0.05 * w, 1.75), (0.55 * L, -(w / 2 + 0.55), 2.45), 18)

    def labels(info):   # level with the rack tops, along row A's front edge
        w, L, *_, front = PR._geo(info)
        yf = -(w / 2 + 0.625) + front * 0.625
        return PR.Cam((-0.55, yf + front * 0.95, room.STACK["rack_top"] + 0.45), (2.6, yf, room.STACK["rack_top"] +
                                                                                     0.1), 24)

    def hangv(info):    # under the hanging sign, looking along the aisle at it
        w, L, *_ = PR._geo(info)
        return PR.Cam((L / 2 - 2.6, 0.25 * w, 1.6), (L / 2, 0.0, room.STACK["tray_bottom"] + 0.1), 22)
    PR.CAMERAS.update(sign_row=row, sign_labels=labels, sign_hang=hangv)
    old = room.reference_room
    room.reference_room = _no_containment(old)
    try:
        for aisle in ("cold", "hot"):
            for cam in ("sign_row", "sign_labels"):
                PR.shot(built, cam, 1.5, aisle, name=f"rack_labels_{cam[5:]}_{aisle}", captions=False,
                        contain_open=-1.0)
        PR.shot(built, "sign_hang", 1.5, "cold", name="hang_over_aisle_cold", captions=False, contain_open=-1.0)
        PR.shot(built, "photo1", 1.5, "cold", paint="black", name="photo1_open_black", captions=False,
                contain_open=-1.0)
    finally:
        room.reference_room = old


def room_shots(built):
    """The reference room with its containment: outside the door (the aisle sign on the header, the hanging sign
    over the roof beyond), a rack top (the label between the Drop's waterfalls), photo 1, overhead; cold and hot."""
    for aisle in ("cold", "hot"):
        for cam in ("door_outside", "rack_top", "overhead"):
            PR.shot(built, cam, 1.5, aisle, captions=False)
    PR.shot(built, "photo1", 1.5, "cold", captions=False)
    for w in (1.0, 2.0):
        PR.shot(built, "door_outside", w, "cold", captions=False)


def _import_zones(name, kind="Fractured"):
    """{zone index: collection} of an exported model's LOD0 objects (read-only import of our own export)."""
    from . import config
    from . import preview_mats as PM
    path = os.path.join(config.MODELS_DIR, name, kind, f"{name}_{kind}.fbx")
    key = ("zones", name, kind)
    if key in _CUT:
        return _CUT[key]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    out = {}
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        if o.type != "MESH":
            continue
        z = next((int(t) for t in o.name.replace("_", " ").split() if t.isdigit() and len(t) == 2), 0)
        if z not in out:
            out[z] = _new_coll(f"z_{name}_{kind}_{z}")
        out[z].objects.link(o)
        for i, sl in enumerate(o.material_slots):
            n = (sl.material.name if sl.material else "").split(".")[0]
            k = "Fractured" if n.startswith("Fractured") else PM.keen_key(n, PAINT[name])
            o.material_slots[i].material = PM.get(k)
    _CUT[key] = out
    return out


def fracture(built, name):
    """The exported Fractured model's tiles pulled apart along x: the break faces (FracturedMaterial01) on the cut
    housing, bezel and back plate; the screen cut with its tiles."""
    nm = f"fracture_{name}"
    if not want(nm):
        return
    zones = _import_zones(name)
    zc = ZS[name]
    s = PV.Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
    n = len(zones)
    for z, c in sorted(zones.items()):
        dx = {1: 0.0, 2: -0.10, 3: 0.10}[z] if n == 3 else (-0.06 if z == 1 else 0.06)
        s.inst(c, T(dx, 0, zc + (0.04 if z == 1 and n == 3 else 0.0)))
    sx = 1.0 if name != "DC_Sign_Rack" else 0.5
    s.camera((-0.55 * sx - 0.3, 0.9 * sx + 0.6, zc + 0.45), (0, 0, zc), 40)
    s.render()


def paints(built):
    for paint in ("keen", "black", "blue", "red"):
        nm = f"paints_{paint}"
        if not want(nm):
            continue
        s = PV.Shot(nm, res=(2000, 1000), floor=(-2, 2, -1.5, 1.5))
        place(s, built, "DC_Sign_Aisle", T(-0.65, 0, 0.75), paint=paint)
        place(s, built, "DC_Sign_AisleHang", T(0.6, -0.4, 0.75), paint=paint)
        place(s, built, "DC_Sign_Rack", T(-0.1, 0.55, 0.35), paint=paint)
        s.camera((0.6, 3.1, 1.6), (0.0, 0.0, 0.55), 34)
        s.render()


def vanilla_compare(built):
    """Our three signs beside the clone source (vanilla NarrowLCD50) and vanilla NarrowLCD250 / LCD50, same light."""
    nm = "vanilla_compare"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2400, 1000), floor=(-7.6, 0.6, -1.5, 1.5))
    x, labels = 0.0, []
    for n in SIGNS:
        sx = 1.0 if n != "DC_Sign_Rack" else 0.5
        place(s, built, n, T(x - sx / 2, 0, 0.125))
        labels.append((n.replace("DC_Sign_", "ours: "), (x - sx / 2, 0.0, 0.45)))
        x -= sx + 0.3
    for rel, label in (("LCDPanels/NarrowLCD/50/Models/Nonfractured/NarrowLCD50.fbx", "vanilla NarrowLCD50"),
                       ("LCDPanels/NarrowLCD/250/Models/NonFractured/NarrowLCD250.fbx", "vanilla NarrowLCD250"),
                       ("LCDPanels/LCD/50/Models/NonFractured/LCD50.fbx", "vanilla LCD50")):
        c, lo, hi = PV.vanilla(rel)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        labels.append((label, (x - w / 2, 0.0, hi.z - lo.z + 0.25)))
        x -= w + 0.4
    cx = x / 2
    s.camera((cx, 0.62 * abs(x) + 0.6, 0.22 * abs(x) + 0.6), (cx, 0, 0.3), 36)
    for txt, at in labels:
        s.caption(txt, at, 0.085)
    s.render()


def render_all(built):
    _out()
    for n in SIGNS:
        if n in built:
            hero(built, n)
            close(built, n)
            lods(built, n)
            fracture(built, n)
    if all(n in built for n in SIGNS):
        paints(built)
        vanilla_compare(built)
        on_wall(built)
        legibility(built)
    on_doors(built)
    hang(built)
    row_shots(built)
    room_shots(built)
    print("signs previews ->", PV.OUT)
