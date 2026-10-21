"""Containment door previews: the containment end-of-aisle sliding doors.

    DC_PREVIEW=contain-doors blender -b --python Source/Model/build_dc.py -- "DC_Contain_Door_*" "DC_Contain_Roof_*" \
        "DC_Rack42_*" "DC_Srv_*" "DC_Floor_*" "DC_Tray_Drop_Full" "DC_Tray_StraightS_Full" "DC_TrayRods_100"

Writes Source/Model/preview/contain-doors/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution):
  <door>_closed_34 / _open_34 / _anim_f025 / _anim_f050 / _anim_f075
                                each width from the room side (3/4), leaves at OpenRatio 0, 1, 0.25, 0.5, 0.75
  <door>_aisle_closed / _aisle_open   the same door from the aisle side (-Y), a 1.8 m figure for scale
  <door>_lods                   LOD0..n of the frame with the leaves at the same LOD
  <door>_collision              the four physics boxes (orange), the mount hints (green), the leaves' collision
                                boxes closed (red, they block the opening) and open (blue ghosts, in the pockets)
  plan_sweep_<w>                ortho plan cut at 2.0 m: the pockets on the end racks' sides, the racks' leaves at
                                0 .. 85 deg (five steps), the door's leaves closed and open (ghost)
  closeup_*                     the flush pull and chevrons, the header from below (track, carriages, end stop,
                                closer), the threshold with the guide shoes, a post foot (cap, seals), the meeting
                                stile's shiplap (plan cut), the pocket with its cover cut away (brackets, parked leaf)
  fracture_<door>               the four fracture pieces pulled apart
  paints_*                      keen, black and the cold / hot pair (blue, orange)
  vanilla_compare               the doors beside the clone source (vanilla NarrowSlidingDoor with its leaves)
  room_*                        the reference room (dc/preview_room.py): from inside the aisle and from outside it
                                (with the aisle-sign stand-in), closed / half / open, every width, cold and hot
Contact sheet: python3 Source/Model/contain_doors_sheet.py.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import catalog, contain, room
from . import preview as PV
from . import preview_mats as PM
from . import preview_room as PR
from .preview import Rz, T, want

DOORS = ("DC_Contain_Door_100", "DC_Contain_Door_150", "DC_Contain_Door_200")
ZC = contain.DH                     # the block centre over the ground in the studio shots (the door on the floor)


def _w(name):
    return contain.door_w(catalog.BY_NAME[name])


def door(s, built, name, M, f=0.0, paint="keen", lod=0):
    PR.contain_door(s, built, name, M, f, paint, lod)


def _box_obj(name, lo, hi, mat, M=None):
    bm = bmesh.new()
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=Vector(hi) - Vector(lo), verts=vs)
    bmesh.ops.translate(bm, vec=(Vector(lo) + Vector(hi)) / 2, verts=vs)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(PM.get(mat))
    ob = bpy.data.objects.new(name, me)
    if M is not None:
        ob.matrix_world = M
    return ob


def _studio(nm, w, light=1.0, res=(1800, 1150)):
    return PV.Shot(nm, res=res, floor=(-w - 1.5, w + 1.5, -2.5, 2.5), light=light)


# ---------------------------------------------------------------------------------------------------- per width
def hero(built, name):
    w = _w(name)
    D = 1.15 * w + 3.2
    M = T(0, 0, ZC)
    shots = [("closed_34", 0.0, (0.55 * D, 0.85 * D, 1.9), 40), ("open_34", 1.0, (0.55 * D, 0.85 * D, 1.9), 40),
             ("anim_f025", 0.25, (0.55 * D, 0.85 * D, 1.9), 40), ("anim_f050", 0.5, (0.55 * D, 0.85 * D, 1.9), 40),
             ("anim_f075", 0.75, (0.55 * D, 0.85 * D, 1.9), 40),
             ("aisle_closed", 0.0, (-0.45 * D, -0.9 * D, 1.6), 40), ("aisle_open", 1.0, (-0.45 * D, -0.9 * D, 1.6), 40)]
    for v, f, loc, lens in shots:
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = _studio(nm, w)
        door(s, built, name, M, f)
        s.inst(PV.human(), T(-w - 0.45, 0.45 if loc[1] > 0 else -0.45, 0) @ Rz(180 if loc[1] > 0 else 0))
        s.camera(loc, (0, 0, 1.15), lens)
        s.caption(f"OpenRatio {f:.2f}", (-w, 0.2, 2.75), 0.09)
        s.render()


def lods(built, name):
    import json
    from . import config
    nm = f"{name}_lods"
    if not want(nm):
        return
    n = len(built[name]["lods"])
    w = _w(name)
    step = 2 * w + 0.6
    s = PV.Shot(nm, res=(2400, 1000), floor=(-step * n, step, -2, 2))
    with open(config.REPORT_PATH) as f:
        rep = json.load(f)["blocks"].get(name, {})
    cx = -step * (n - 1) / 2
    s.camera((cx + 0.3, 1.2 * step * n / 2 + 4.0, 2.4), (cx, 0, 1.2), 32)
    for i in range(n):
        x = -step * i
        s.inst(PV.painted(built, name, i), T(x, 0, ZC))
        for lf in contain.door_leaves(catalog.BY_NAME[name]):
            lods_ = built[name]["subparts"][lf.model]
            from . import preview_rack_doors as pv_rack_doors
            s.inst(pv_rack_doors.sub(built, name, lf.model, "keen", min(i, len(lods_) - 1)),
                   T(x + contain.leaf_centre_x(catalog.BY_NAME[name], lf.side, 0.3), 0, ZC + contain.LEAF_ORIGIN_Z))
        lr = rep.get("lods", [{}] * n)[i]
        s.caption(f"LOD{i}\n{lr.get('tris', '?')}/{lr.get('max_tris', '?')} tris", (x, 0.3, 2.85), 0.11)
    s.render()


def collision(built, name):
    nm = f"{name}_collision"
    if not want(nm):
        return
    spec = catalog.BY_NAME[name]
    w = _w(name)
    s = _studio(nm, w, light=0.9)
    M = T(0, 0, ZC)
    door(s, built, name, M, 0.0)
    b = contain.door_collision(spec)
    for nm_, lo, hi in b["regular"]:
        wf = PV.wire_copy(_box_obj(f"col_{nm_}", lo, hi, "GhostReg", M), t=0.012)
        wf.data.materials[0] = PM.get("EmAmber")
        s.link(wf)
    for nm_, lo, hi in b["mount"]:
        s.link(_box_obj(f"mnt_{nm_}", lo, hi, "GhostMount", M))
    for f, mat in ((0.0, "GhostRed"), (1.0, "GhostSlot")):
        for m, (lo, hi) in contain.leaf_boxes(spec, f).items():
            s.link(_box_obj(f"leaf_{m}_{f}", lo, (hi[0], hi[1], hi[2]), mat, M))
    s.camera((0.5 * w + 1.4, 1.15 * w + 3.4, 2.6), (0, 0, 1.1), 40)
    s.caption("amber wire = the intact physics boxes (header, pockets, sill)   green = mount hints\n"
              "red = the leaves' own collision boxes, closed (blocking the opening)   cyan = the same boxes open "
              "(inside the pocket boxes)", (-w, 0.3, 2.9), 0.065)
    s.render()
    nm = f"{name}_collision_open"
    if not want(nm):
        return
    from . import preview_rack_doors as pv_rack_doors
    s = _studio(nm, w, light=0.9)
    for nm_, lo, hi in b["regular"]:
        wf = PV.wire_copy(_box_obj(f"col_{nm_}", lo, hi, "GhostReg", M), t=0.012)
        wf.data.materials[0] = PM.get("EmAmber")
        s.link(wf)
    for lf in contain.door_leaves(spec):
        s.inst(pv_rack_doors.sub(built, name, lf.model, "keen"), M @ T(contain.leaf_centre_x(spec, lf.side, 1.0), 0, contain.LEAF_ORIGIN_Z))
    for m, (lo, hi) in contain.leaf_boxes(spec, 1.0).items():
        s.link(_box_obj(f"leafo_{m}", lo, hi, "GhostSlot", M))
    for m, (lo, hi) in contain.leaf_boxes(spec, 0.0).items():
        wf = PV.wire_copy(_box_obj(f"leafc_{m}", lo, hi, "GhostRed", M), t=0.006)
        wf.data.materials[0] = PM.get("EmRed")
        s.link(wf)
    s.camera((0.5 * w + 1.4, 1.15 * w + 3.4, 2.6), (0, 0, 1.1), 40)
    s.caption("frame model hidden: leaves open (cyan = their collision boxes, inside the amber pocket boxes); "
              "red wire = the closed boxes", (-w, 0.3, 2.9), 0.065)
    s.render()


def plan_sweep(built, name, rk="DC_Rack42_SplitFront"):
    """Ortho plan, cut at 2.0 m over the floor (under the header): the west door at the row end on the two end racks
    (cold aisle, fronts facing the aisle), the racks' leaves at five steps from 0 to 85 deg, the door's leaves closed
    and (ghost copies) open; red line = the row-end plane (the racks' side faces)."""
    w = _w(name)
    nm = f"plan_sweep_{round(w * 100):03d}"
    if not want(nm) or rk not in built:
        return
    from . import doors as RD
    from . import preview_rack_doors as pv_rack_doors
    s = PV.Shot(nm, res=(1800, 1600), floor=(-2.0, 2.5, -w - 2, w + 2), light=1.1)
    zc = contain.DH
    Md = T(-0.125, 0, zc) @ Rz(90)                       # room.reference_room: the west door at yaw 1
    door(s, built, name, Md, 0.0)
    for lf in contain.door_leaves(catalog.BY_NAME[name]):
        s.inst(pv_rack_doors.sub(built, name, lf.model, "blue"), Md @ T(contain.leaf_centre_x(catalog.BY_NAME[name], lf.side, 1.0), 0, contain.LEAF_ORIGIN_Z))
    spec = catalog.BY_NAME[rk]
    for sg in (-1, 1):
        yaw = 0 if sg < 0 else 180
        C = T(0.5, sg * (w / 2 + 0.625), 1.25) @ Rz(yaw)
        s.inst(pv_rack_doors.body(built, rk, "keen", False), C)
        for k, f in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
            for lf in RD.leaves(spec):
                s.inst(pv_rack_doors.sub(built, rk, lf["model"], "keen" if f in (0.0, 1.0) else "orange"),
                       C @ T(lf["axis"][0], lf["axis"][1], 0) @ Rz(RD.swing_yaw(lf, f)))
    s.link(_box_obj("row_end", (-0.0015, -w / 2 - 1.3, 0.0), (0.0015, w / 2 + 1.3, 2.0), "EmRed"))
    s.camera((0.2, 0.002, 12.0), (0.2, 0.0, 0.0), 50, ortho=2 * w + 2.8)
    s.cam.data.clip_start = 12.0 - 2.0
    s.cam.data.clip_end = 30.0
    s.caption("door leaves closed (keen) + open (blue)  |  rack leaves 0 / 85 deg (keen), 21 / 43 / 64 deg (orange)\n"
              "red = the row-end plane: the door's back plates sit 1 mm off it, the racks' leaves stay >= 15 mm inside",
              (0.2, -w / 2 - 1.15, 1.9), 0.07)
    s.render()


# ---------------------------------------------------------------------------------------------------- close-ups
def closeups(built, name="DC_Contain_Door_150"):
    if name not in built:
        return
    from . import preview_contain_roof as pv_contain_roof
    spec = catalog.BY_NAME[name]
    w = _w(name)
    M = T(0, 0, ZC)
    pz = contain.PULL_Z + ZC
    xl = contain.leaf_centre_x(spec, 1, 0.0) - contain.leaf_width(spec) / 2 + 0.07   # the +x leaf's pull, closed
    cams = {
        "closeup_pull": (0.0, (xl + 0.42, 0.55, pz + 0.12), (xl - 0.02, 0.0, pz), 50),
        "closeup_pull_aisle": (0.0, (xl + 0.40, -0.55, pz + 0.10), (xl - 0.02, 0.0, pz), 50),
        "closeup_header_under": (0.0, (w / 2 - 0.10, 0.62, 1.35), (w / 2 - 0.45, 0.0, contain.ZH + ZC + 0.02), 32),
        "closeup_header_open": (1.0, (w - 0.35, 0.42, 1.65), (w - 0.10, 0.0, contain.ZH + ZC + 0.03), 34),
        "closeup_threshold": (0.5, (0.25, 0.42, 0.28), (0.0, 0.0, 0.0), 40),
        "closeup_post_foot": (0.0, (w / 2 - 0.55, 0.55, 0.45), (w / 2 - 0.04, 0.05, 0.12), 40),
        "closeup_post_head": (0.0, (w / 2 - 0.55, -0.55, 2.0), (w / 2 - 0.04, -0.05, 2.18), 40),
        "closeup_lip_fascia": (0.0, (-w / 2 - 0.4, -0.75, 2.05), (-0.2, -0.12, 2.38), 34),
    }
    for nm, (f, loc, tgt, lens) in cams.items():
        if not want(nm):
            continue
        s = _studio(nm, w, light=1.0)
        door(s, built, name, M, f)
        s.camera(loc, tgt, lens)
        s.render()
    nm = "closeup_meeting_plan"
    if want(nm):   # ortho plan cut at the pull's height: the shiplap tongues, the seals, the two flush pulls
        s = PV.Shot(nm, res=(1600, 1000), floor=(-2, 2, -2, 2), light=1.2)
        door(s, built, name, M, 0.0)
        s.camera((0.0, 0.0, pz + 6.0), (0.0, 0.0, pz), 50, ortho=0.34)
        s.cam.data.clip_start = 6.0 - 0.0001
        s.caption("plan cut at the pulls (1.05 m): the leaves' shiplap tongues overlap 2 x 15 mm at the centre line",
                  (0.0, 0.09, pz - 0.01), 0.008)
        s.render()
    nm = "closeup_pocket_cutaway"
    if want(nm):   # the pocket with its cover cut away (y < 0.075 kept): back plate, slotted brackets, parked leaf
        s = _studio(nm, w, light=1.0)
        s.inst(pv_contain_roof.section(built, name, "y", 0.075), M)
        from . import preview_rack_doors as pv_rack_doors
        for lf in contain.door_leaves(spec):
            s.inst(pv_rack_doors.sub(built, name, lf.model, "keen"), M @ T(contain.leaf_centre_x(spec, lf.side, 1.0), 0, contain.LEAF_ORIGIN_Z))
        s.camera((0.75 * w + 0.4, 1.9, 1.5), (0.75 * w, 0.0, 1.1), 36)
        s.caption("pocket, cover cut away: back plate on the rack side, 4 slotted brackets, the parked leaf",
                  (0.5 * w, 0.1, 2.75), 0.05)
        s.render()


def _zone_colls(built, name, paint="keen"):
    """{zone id: collection} of the LOD0 faces each fracture zone gets (fracture.plan, as the export)."""
    from . import preview_contain_roof as pv_contain_roof
    from . import fracture as FR
    spec = catalog.BY_NAME[name]
    plan = FR.plan(spec, contain.door_collision(spec))   # the export's zones (fracture.plan; faces by centroid)
    zones = [(z.id, *z.hull) for z in plan.zones]
    src = PV.painted(built, name, 0, paint)
    out = {}
    for z, _, _ in zones:
        key = ("frac", name, z, paint)
        c = PV._PAINTED.get(key)
        if c is None:
            c = bpy.data.collections.new(f"frac_{name}_{z}_{paint}")
            bpy.context.scene.collection.children.link(c)
            for o in src.objects:
                if o.type != "MESH":
                    continue
                me = pv_contain_roof._copy_world(o)
                bm = bmesh.new()
                bm.from_mesh(me)
                drop = [f for f in bm.faces if plan.zones[plan.zone_index(tuple(f.calc_center_median()))].id != z]
                bmesh.ops.delete(bm, geom=drop, context="FACES")
                bm.to_mesh(me)
                bm.free()
                if len(me.polygons):
                    c.objects.link(bpy.data.objects.new(f"fr_{o.name}_{z}", me))
            PV._exclude(c)
            PV._PAINTED[key] = c
        out[z] = c
    return zones, out


def fracture(built, name):
    """The 8 fracture pieces pulled apart (each along its hull centre's direction), the break faces
    (FracturedMaterial01) showing on the cut ends of the jambs, back plates, header and threshold."""
    nm = f"fracture_{name}"
    if not want(nm):
        return
    w = _w(name)
    zones, colls = _zone_colls(built, name)
    names = ["lintel"] + [f"pocket_{t}{k}" for t in "lr" for k in (1, 2, 3)] + ["sill"]   # (fracture._door order)
    s = _studio(nm, w)
    s.camera((0.45 * w + 1.4, 1.4 * w + 5.2, 2.2), (0, 0, 1.45), 38)
    for (z, lo, hi), label in zip(zones, names):
        c = [(a + b) / 2 for a, b in zip(lo, hi)]
        off = (0.25 * c[0] / max(w, 1e-6), 0.6 if label == "sill" else 0.0,
               0.16 * c[2] + (0.18 if label == "lintel" else 0.0) + (0.10 if label == "sill" else 0.0))
        s.inst(colls[z], T(*off) @ T(0, 0, ZC))
        s.caption(f"{z[-2:]} {label}", (c[0] + off[0], 0.25, c[2] + off[2] + ZC + 0.1), 0.06)
    s.render()
    nm = f"fracture_{name}_cut_closeup"
    if want(nm):   # one pocket tower's joint pulled apart: the jamb and back plate cut ends, FracturedMaterial01
        s = _studio(nm, w)
        zl = [z for (z, *_), n in zip(zones, names) if n.startswith("pocket_r")]
        for k, z in enumerate(zl):
            s.inst(colls[z], T(0, 0, 0.25 * k) @ T(0, 0, ZC))
        zc = contain.POCKET_SPLITS[0] + ZC + 0.12
        s.camera((w / 2 - 0.30, -0.65, zc + 0.30), (w / 2 + 0.05, -0.04, zc), 36)
        s.render()


def damaged(built, name):
    """The Damaged model's look: a copy of LOD0 dented with the exporter's own field (export_models.dent), beside
    the intact frame."""
    nm = f"damaged_{name}"
    if not want(nm):
        return
    from .export_models import dent
    w = _w(name)
    src = PV.painted(built, name, 0, "keen")
    c = bpy.data.collections.new(f"dm_{name}")
    bpy.context.scene.collection.children.link(c)
    objs = []
    for o in src.objects:
        if o.type != "MESH":
            continue
        n = o.copy()
        n.data = o.data.copy()
        c.objects.link(n)
        objs.append(n)
    vs = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    st = dent(objs, lo, hi)
    PV._exclude(c)
    s = PV.Shot(nm, res=(2200, 1100), floor=(-2 * w - 2, 2 * w + 2, -2.5, 2.5))
    door(s, built, name, T(w + 0.3, 0, ZC), 0.0)                  # the camera looks along -y: +x is on the left
    s.inst(c, T(-w - 0.3, 0, ZC))
    s.camera((0.0, 2.2 * w + 4.2, 1.9), (0, 0, 1.35), 36)
    s.caption("intact", (w + 0.3, 0.2, 2.62), 0.09)
    s.caption(f"Damaged model: dented, mean {st.get('mean_mm')} mm", (-w - 0.3, 0.2, 2.62), 0.09)
    s.render()


def paints(built, name="DC_Contain_Door_150"):
    for paint in ("keen", "black", "blue", "orange"):
        nm = f"paints_{paint}"
        if not want(nm) or name not in built:
            continue
        w = _w(name)
        s = _studio(nm, w)
        door(s, built, name, T(0, 0, ZC), 0.5, paint)
        s.camera((0.9 * w + 1.2, 1.1 * w + 3.2, 2.0), (0, 0, 1.15), 40)
        s.caption(f"paint: {paint}", (-w, 0.2, 2.75), 0.09)
        s.render()


def vanilla_compare(built):
    """Our three doors (half open) beside the clone source, vanilla NarrowSlidingDoor with its two leaves (read-only
    FBX), same light and stand-in materials."""
    nm = "vanilla_compare"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2600, 1100), floor=(-15, 2, -2.5, 2.5))
    x, labels = 0.0, []
    for n in DOORS:
        if n not in built:
            continue
        w = _w(n)
        door(s, built, n, T(x - w, 0, ZC), 0.5)
        labels.append((n.replace("DC_Contain_", "") + "\n(half open)", (x - w, 0.2, 2.8)))
        x -= 2 * w + 0.6
    base = "Doors/SlideDoorNarrow/250/Models/NonFractured/"
    parts = [base + "NarrowSlidingDoor.fbx", base + "LeftDoor/NarrowSlidingDoor_LeftDoor.fbx",
             base + "RightDoor/NarrowSlidingDoor_RightDoor.fbx"]
    frame = PV.vanilla(parts[0])
    _, lo, hi = frame
    wv = hi.x - lo.x
    ctr = (lo + hi) / 2
    Mv = T(x - wv / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z)
    for rel in parts:
        c, _, _ = PV.vanilla(rel)
        s.inst(c, Mv)
    labels.append(("vanilla NarrowSlidingDoor\n(SlidingDoorNarrow250, closed)", (x - wv / 2, 0.2, hi.z - lo.z + 0.35)))
    x -= wv + 0.5
    s.inst(PV.human(), T(x + 0.2, 0.6, 0))
    cx = x / 2
    s.camera((cx, 0.8 * abs(x) + 3.0, 2.6), (cx, 0, 1.2), 30)
    for txt, at in labels:
        s.caption(txt, at, 0.12)
    s.render()


# ---------------------------------------------------------------------------------------------------- room
def _cams():
    def inside(info):     # in the aisle, looking back at the west door: the leaves, posts, header lip, roof run
        w, L, *_ = PR._geo(info)
        return PR.Cam((2.7, 0.18 * w, 1.62), (-0.1, -0.05 * w, 1.35), 22)

    def outside(info):    # in front of the west door, outside the aisle: the leaves, pockets, closers, sign
        w, L, x0, *_ = PR._geo(info)
        return PR.Cam((-2.6, -0.22 * w - 0.35, 1.68), (0.0, 0.0, 1.45), 24)

    def outside_far(info):   # further out: the door on the end racks, the roof run behind it, the sign on the header
        w, L, x0, *_ = PR._geo(info)
        return PR.Cam((x0 + 0.35, -0.55 * w - 0.9, 1.75), (0.3, 0.1, 1.55), 20)

    def east_inside(info):   # inside the aisle looking at the east door (its end unit is the PDU cabinet ghost)
        w, L, *_ = PR._geo(info)
        return PR.Cam((L - 2.6, -0.18 * w, 1.62), (L + 0.1, 0.05 * w, 1.35), 22)
    PR.CAMERAS.update(door_inside=inside, door_outside_near=outside, door_outside_far=outside_far,
                      door_east_inside=east_inside)


def room_shots(built):
    _cams()
    for w in DM_WIDTHS:
        for aisle in ("cold", "hot"):
            PR.shot(built, "door_inside", w, aisle, captions=False)
            PR.shot(built, "door_outside_near", w, aisle, captions=False)
    for f, tag in ((0.5, "half"), (1.0, "open")):
        for cam in ("door_inside", "door_outside_near"):
            PR.shot(built, cam, 1.5, "cold", name=f"room_150_cold_{cam}_{tag}", captions=False, contain_open=f)
    PR.shot(built, "door_outside_far", 1.5, "cold", captions=False)
    PR.shot(built, "door_outside_far", 1.5, "hot", captions=False)
    PR.shot(built, "door_east_inside", 1.5, "cold", captions=False)
    PR.shot(built, "door_inside", 1.5, "cold", paint="black", name="room_150_cold_door_inside_black", captions=False)
    PR.shot(built, "overhead", 1.5, "cold", captions=False)
    PR.shot(built, "photo1", 1.5, "cold", captions=False)
    PR.shot(built, "door_inside", 1.5, "cold", name="room_150_cold_door_inside_racks85", captions=False,
            doors_open=1.0)


DM_WIDTHS = (1.0, 1.5, 2.0)


def render_all(built):
    PR._out("contain-doors")
    for n in DOORS:
        if n in built:
            hero(built, n)
            lods(built, n)
            collision(built, n)
            plan_sweep(built, n)
    closeups(built)
    for n in ("DC_Contain_Door_100", "DC_Contain_Door_200"):
        if n in built:
            fracture(built, n)
            damaged(built, n)
    paints(built)
    vanilla_compare(built)
    room_shots(built)
    print("contain-doors previews ->", PV.OUT)
