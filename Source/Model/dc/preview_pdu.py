"""PDU previews: the PDU cabinet and the zero-U rack PDU strips (Feed A / Feed B; 42U and 24U).

    DC_PREVIEW=pdu blender -b --python Source/Model/build_dc.py -- "DC_PDU_*" "DC_Rack*" "DC_Srv_*" \
        "DC_Floor_*" "DC_Contain_*" "DC_Tray_Drop_Full" "DC_Tray_Drop_Low" "DC_Tray_StraightS_Full" "DC_TrayRods_100"

Writes Source/Model/preview/pdu/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution):
  hero_<block>_{34_front,34_back,front,back}   each PDU block on its own (the strips stand on a plinth-height stub)
  strips_in_<rack>_{rear_34,rear_open,rear_doors_closed,...}
                              both feeds in a populated rack's rear columns, rear doors open / closed, 42U and 24U
  closeup_*                   cabinet: meter, panelboard, isolator + placard, hinge / lock, top brush plates with a
                              Drop landing in them, rear gland plates; strip: outlets + cords, bank head, feed tags,
                              the inlet plug seated in the plinth receptacle, the brackets in the keyholes
  drop_into_cabinet           a tray Drop over the cabinet, its waterfalls in the top-entry brush plates
  lods_<block>                LOD0..n side by side
  fracture_<block>            the fracture zones pulled apart (break faces on the cut ends), damaged_<block>
  paints_<block>_<paint>      keen, black, blue / orange (cold / hot)
  vanilla_compare             beside the clone source (vanilla WallInsertPanel), vanilla Battery50 and a 42U rack
  room_*                      the reference room (dc/preview_room.py): the cabinet at the row end, the strips in every
                              rack, cold and hot aisle
Contact sheet: python3 Source/Model/pdu_sheet.py.
"""
import math

import bmesh
import bpy
from mathutils import Vector

from . import catalog, pdu, rack
from . import dims as DM
from . import preview as PV
from . import preview_mats as PM
from . import preview_room as PR
from . import preview_rack_doors as pv_rack_doors
from .preview import Rz, T, want

CAB = "DC_PDU_Cabinet"
STRIPS = ("DC_PDU_Rack42_A", "DC_PDU_Rack42_B", "DC_PDU_Rack24_A", "DC_PDU_Rack24_B")
MIX42 = ("DC_Srv_Storage", "DC_Srv_Compute", "UPS", None, "DC_Srv_Switch", "DC_Srv_Compute", "DC_Srv_Timer",
         "DC_Srv_Switch")
MIX24 = ("DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch", "DC_Srv_Blank")


def _H(name):
    return 0.25 * catalog.BY_NAME[name].cells[1]


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


def strip_matrix(rack_name, strip_name, M):
    """A strip placed in a rack standing at base matrix M (its floor point): the PDU column's cells' centre."""
    rs = catalog.BY_NAME[rack_name]
    ss = catalog.BY_NAME[strip_name]
    sx = pdu.strip_sx(ss)
    z0 = rack.pdu_band(rs)[0]
    return M @ T(sx * pdu.COL_X, pdu.COL_Y, z0 + _H(strip_name) / 2)


def rack_with_strips(s, built, rk, x=0.0, y=0.0, rot=0.0, f_rear=0.0, paint="keen", mix=None, feeds=("A", "B"),
                     f=0.0):
    """A populated rack with its strips (both feeds by default) in the rear PDU columns. Returns the base matrix."""
    mix = mix if mix is not None else (MIX42 if catalog.BY_NAME[rk].cells[1] == 10 else MIX24)
    M = pv_rack_doors.rack(s, built, rk, x, y, rot, f=f, paint=paint, mix=mix, f_rear=f_rear)
    h = 42 if catalog.BY_NAME[rk].cells[1] == 10 else 24
    for feed in feeds:
        n = f"DC_PDU_Rack{h}_{feed}"
        if n in built:
            s.inst(PV.painted(built, n, 0, paint), strip_matrix(rk, n, M))
    return M


def _stub(s, x, y, w=0.25, d=0.25, h=0.25):
    """A plinth-height Darker stub the strip stands on in the studio (its plinth-top plane at h)."""
    s.link(_box_obj("stub", (x - w / 2, y - d / 2, 0.0), (x + w / 2, y + d / 2, h), "Darker"))


# ---------------------------------------------------------------------------------------------------- hero
def hero(built):
    if CAB in built:
        for v, loc, lens in (("34_front", (-2.6, 4.3, 2.6), 35), ("34_back", (2.6, -4.3, 2.6), 35),
                             ("front", (0.0, 5.6, 1.4), 35), ("back", (0.0, -5.6, 1.4), 35)):
            nm = f"hero_{CAB}_{v}"
            if not want(nm):
                continue
            s = PV.Shot(nm, floor=(-2, 2, -2, 2))
            s.inst(PV.painted(built, CAB, 0, "keen"), T(0, 0, 1.25))
            s.inst(PV.human(), T(-1.0 if loc[0] <= 0 else 1.0, 0.3, 0) @ Rz(180 if loc[1] > 0 else 0))
            s.camera(loc, (0, 0, 1.2), lens)
            s.render()
    for h in (42, 24):
        names = [n for n in (f"DC_PDU_Rack{h}_A", f"DC_PDU_Rack{h}_B") if n in built]
        if not names:
            continue
        H = _H(names[0])
        D = 0.95 * H + 0.9
        for v, loc, tgt_dz, lens in (("34_rear", (-0.45 * D, -0.95 * D, 0.55 * H + 0.5), 0.0, 35),
                                     ("34_front", (0.45 * D, 0.95 * D, 0.55 * H + 0.5), 0.0, 35),
                                     ("rear", (0.0, -1.05 * D, H / 2 + 0.25), 0.0, 35),
                                     ("side", (1.05 * D, -0.15 * D, H / 2 + 0.25), 0.0, 35)):
            nm = f"hero_PDU_Rack{h}_{v}"
            if not want(nm):
                continue
            s = PV.Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
            s.camera(loc, (0, 0, 0.25 + H / 2), lens)
            for i, n in enumerate(names):
                x = 0.22 if n.endswith("_A") else -0.22        # A at +x (its column; on the right seen from the rear)
                _stub(s, x, 0.0, w=0.2, d=0.2)
                s.inst(PV.painted(built, n, 0, "keen"), T(x, 0.0, 0.25 + H / 2))
                s.caption(f"Feed {n[-1]}", (x, 0.0, 0.25 + H + 0.12), 0.06)
            s.render()


# ---------------------------------------------------------------------------------------------------- in the racks
def in_racks(built):
    for rk in ("DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFrontRear", "DC_Rack42_Open", "DC_Rack24_Open"):
        if rk not in built:
            continue
        H = _H(rk)
        tag = rk.replace("DC_", "")
        for v, f_rear, loc, tgt, lens in (
                ("rear_34_open", 1.0, (-1.55, -2.3, 0.75 * H + 0.5), (0.0, -0.4, 0.5 * H), 32),
                ("rear_34_closed", 0.0, (-1.55, -2.3, 0.75 * H + 0.5), (0.0, -0.4, 0.5 * H), 32),
                ("rear_open", 1.0, (0.0, -2.6, 0.55 * H + 0.3), (0.0, -0.4, 0.5 * H), 32)):
            if "Open" in rk and f_rear == 0.0:
                continue
            nm = f"strips_in_{tag}_{v}"
            if not want(nm):
                continue
            s = PV.Shot(nm, floor=(-2, 2, -2.5, 2))
            rack_with_strips(s, built, rk, f_rear=f_rear)
            s.camera(loc, tgt, lens)
            s.render()


# ---------------------------------------------------------------------------------------------------- close-ups
def closeups(built):
    if CAB in built:
        cab = {
            "closeup_cabinet_meter": ((0.15, 1.15, 2.05), (0.0, 0.55, 2.02), 50),
            "closeup_cabinet_panelboard": ((0.35, 1.55, 1.45), (0.0, 0.55, 1.30), 42),
            "closeup_cabinet_breakers": ((-0.25, 0.95, 1.62), (0.10, 0.55, 1.50), 50),
            "closeup_cabinet_isolator": ((-0.45, 1.25, 0.95), (0.0, 0.55, 0.60), 45),
            "closeup_cabinet_lock_hinge": ((0.65, 1.05, 1.45), (0.30, 0.56, 1.30), 50),
            "closeup_cabinet_top": ((0.85, 1.35, 3.35), (0.0, 0.2, 2.45), 32),
            "closeup_cabinet_rear_glands": ((-0.4, -1.35, 2.25), (0.0, -0.55, 2.02), 45),
            "closeup_cabinet_plinth": ((0.85, 1.4, 0.45), (0.25, 0.55, 0.15), 40),
        }
        for nm, (loc, tgt, lens) in cab.items():
            if not want(nm):
                continue
            s = PV.Shot(nm, floor=(-2, 2, -2, 2))
            s.inst(PV.painted(built, CAB, 0, "keen"), T(0, 0, 1.25))
            s.camera(loc, tgt, lens)
            s.render()
    rk = "DC_Rack42_SplitFrontRear"
    if rk in built and "DC_PDU_Rack42_A" in built:
        x = pdu.COL_X
        st = {   # rear: the A strip is at -x seen from the rear... (rack frame: A = +x)
            "closeup_strip_outlets": ((x - 0.25, -1.05, 1.35), (x, -0.5, 1.22), 45),
            "closeup_strip_bank_head": ((x - 0.2, -0.95, 1.56), (x, -0.5, 1.42), 55),
            "closeup_strip_feed_tags": ((0.0, -1.25, 2.2), (0.0, -0.5, 2.15), 32),
            "closeup_strip_inlet_A": ((x - 0.22, -0.95, 0.55), (x - 0.02, -0.49, 0.27), 50),
            "closeup_strip_inlet_B": ((-x + 0.22, -0.95, 0.55), (-x + 0.02, -0.49, 0.27), 50),
            "closeup_strip_cords": ((x - 0.35, -0.85, 1.75), (x - 0.06, -0.5, 1.6), 45),
        }
        for nm, (loc, tgt, lens) in st.items():
            if not want(nm):
                continue
            s = PV.Shot(nm, floor=(-2, 2, -2.5, 2))
            mix = MIX42
            if nm == "closeup_strip_bracket":   # looking from inside the slot space: no servers there
                mix = (None,) * 8
            rack_with_strips(s, built, rk, f_rear=1.0, mix=mix)
            s.camera(loc, tgt, lens)
            s.render()
        nm = "closeup_strip_bracket"
        if want(nm):   # the strip on its own, seen from the bulkhead side: the standoff brackets and button heads
            s = PV.Shot(nm, floor=(-2, 2, -2, 2))
            _stub(s, 0.0, 0.0, w=0.2, d=0.2)
            ss = catalog.BY_NAME["DC_PDU_Rack42_A"]
            s.inst(PV.painted(built, "DC_PDU_Rack42_A", 0, "keen"), T(0, 0, 0.25 + 1.0))
            zb = 0.25 + pdu.slot_z(ss, 2) + pdu.BTN_Z + 1.0
            s.camera((0.35, 0.55, zb + 0.12), (pdu.XC, 0.09, zb), 45)
            s.render()
        nm = "closeup_strip_inlet_unplugged"
        if want(nm):   # the receptacle alone (the strip lifted out of its column by 0.35 m)
            s = PV.Shot(nm, floor=(-2, 2, -2.5, 2))
            M = pv_rack_doors.rack(s, built, rk, 0, 0, 0, f=0.0, mix=MIX42, f_rear=1.0)
            s.inst(PV.painted(built, "DC_PDU_Rack42_A", 0, "keen"),
                   T(0, 0, 0.35) @ strip_matrix(rk, "DC_PDU_Rack42_A", M))
            s.camera((x - 0.25, -1.0, 0.85), (x - 0.02, -0.49, 0.42), 45)
            s.render()


def drop_into_cabinet(built):
    """A tray Drop over the cabinet as room._trays places it over a rack, both waterfalls in the brush plates."""
    drop = next((n for n in ("DC_Tray_Drop_Full", "DC_Tray_Drop_Low") if n in built), None)
    if CAB not in built or not drop:
        return
    from . import room
    for v, loc, tgt, lens in (("drop_into_cabinet", (1.6, 2.6, 3.6), (0.0, 0.2, 2.7), 32),
                              ("drop_into_cabinet_closeup", (0.75, 1.0, 2.95), (0.30, 0.42, 2.52), 40)):
        if not want(v):
            continue
        s = PV.Shot(v, floor=(-2, 2, -2, 2))
        s.inst(PV.painted(built, CAB, 0, "keen"), T(0, 0, 1.25))
        lc = (0.0, DM.TRAY_RACK_Y + room.CELL / 2, room.UNIT_H / 2 + 1.5 * room.CELL)
        s.inst(PV.painted(built, drop, 0, PR.TRAY_PAINT), T(lc[0], lc[1], 1.25 + lc[2]))
        s.camera(loc, tgt, lens)
        s.render()


# ---------------------------------------------------------------------------------------------------- LODs, paints
def lods(built):
    import json
    from . import config
    with open(config.REPORT_PATH) as f:
        rep = json.load(f)["blocks"]
    for name in (CAB,) + STRIPS:
        nm = f"lods_{name}"
        if name not in built or not want(nm):
            continue
        n = len(built[name]["lods"])
        H = _H(name)
        step = 1.3 if name == CAB else 0.45
        s = PV.Shot(nm, res=(2200, 1000), floor=(-step * n, 1, -1.5, 1.5))
        back = name != CAB
        cx = -step * (n - 1) / 2
        D = max(step * n, H) * 1.25 + 1.0
        s.camera((cx - 0.2, D, H * 0.7 + 0.4), (cx, 0, H * 0.5), 40)
        for i in range(n):
            M = T(-step * i, 0, H / 2) @ (Rz(180) if back else Rz(0))
            s.inst(PV.painted(built, name, i), M)
            lr = rep.get(name, {}).get("lods", [{}] * n)[i]
            s.caption(f"LOD{i}\n{lr.get('tris', '?')}/{lr.get('max_tris', '?')}", (-step * i, 0.3, H + 0.2),
                      0.06 if name == CAB else 0.035)
        s.render()


def paints(built):
    for paint in ("keen", "black", "blue", "orange"):
        nm = f"paints_{paint}"
        if not want(nm):
            continue
        s = PV.Shot(nm, res=(2000, 1150), floor=(-2.5, 2.5, -2.5, 2.5))
        if CAB in built:
            s.inst(PV.painted(built, CAB, 0, paint), T(0.75, 0, 1.25))
        rk = "DC_Rack42_SplitFrontRear"
        if rk in built:
            rack_with_strips(s, built, rk, x=-0.55, rot=180, f_rear=1.0, paint=paint)
        s.camera((-0.4, 4.3, 2.0), (0.1, 0, 1.2), 34)
        s.caption(f"paint: {paint}", (0.1, 0.0, 2.85), 0.08)
        s.render()


# ---------------------------------------------------------------------------------------------------- fracture
def _zone_colls(built, name, paint="keen"):
    """{zone id: collection} of the LOD0 faces each fracture zone gets (fracture.plan, faces by centroid)."""
    from . import preview_contain_roof as pv_contain_roof
    from . import fracture as FR
    spec = catalog.BY_NAME[name]
    plan = FR.plan(spec, pdu.collision(spec))
    zones = [(z.id, *z.hull) for z in plan.zones]
    src = PV.painted(built, name, 0, paint)
    out = {}
    for z, _, _ in zones:
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
        out[z] = c
    return plan, zones, out


def fracture(built):
    for name in (CAB, "DC_PDU_Rack42_A", "DC_PDU_Rack24_B"):
        nm = f"fracture_{name}"
        if name not in built or not want(nm):
            continue
        plan, zones, colls = _zone_colls(built, name)
        H = _H(name)
        s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
        k = 1.0 if name == CAB else 0.35
        if name == CAB:
            s.camera((-2.6, 4.4, 3.2), (0, 0, 1.5), 34)
        else:
            s.camera((-0.9, -2.2 * k - 1.4, 0.6 * H + 0.6), (0, 0, H / 2 + 0.3), 34)
        for zn, (z, lo, hi) in zip(plan.zones, zones):
            c = [(a + b) / 2 for a, b in zip(lo, hi)]
            off = (0.35 * k * math.copysign(1, c[0]) if abs(c[0]) > 0.05 else 0.0,
                   0.25 * k * math.copysign(1, c[1]) if abs(c[1]) > 0.05 and name == CAB else 0.0,
                   0.45 * k * c[2] / max(H / 2, 1e-6))
            s.inst(colls[z], T(*off) @ T(0, 0, H / 2 + 0.3))
            s.caption(f"{z[-2:]}", (c[0] + off[0], c[1] + off[1] + 0.2, c[2] + off[2] + H / 2 + 0.3), 0.06 * k + 0.02)
        s.render()
        nm = f"fracture_{name}_closeup"
        if want(nm):
            s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
            for zn, (z, lo, hi) in zip(plan.zones, zones):
                c = [(a + b) / 2 for a, b in zip(lo, hi)]
                off = (0.0, 0.0, (0.25 if name == CAB else 0.08) * math.copysign(1, c[2]))
                s.inst(colls[z], T(*off) @ T(0, 0, H / 2 + 0.3))
            if name == CAB:
                zj = pdu.PANEL_JOINT_Z + 0.3
                s.camera((0.9, 1.6, zj + 0.45), (0.1, 0.45, zj), 30)
            else:
                zs = fracture_seam_z(name) + H / 2 + 0.3
                s.camera((-0.25, -0.55, zs + 0.15), (0.0, 0.0, zs), 40)
            s.render()


def fracture_seam_z(name):
    from . import fracture as FR
    return FR.pdu_strip_seams(catalog.BY_NAME[name])[0]


def damaged(built):
    from .fracture_mesh import dent
    for name in (CAB, "DC_PDU_Rack42_A"):
        nm = f"damaged_{name}"
        if name not in built or not want(nm):
            continue
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
        st = dent(objs, catalog.BY_NAME[name].family, lo, hi)
        PV._exclude(c)
        H = _H(name)
        w = 0.65 if name == CAB else 0.2
        s = PV.Shot(nm, res=(2000, 1100), floor=(-2.5, 2.5, -2.5, 2.5))
        rot = Rz(0) if name == CAB else Rz(180)
        s.inst(PV.painted(built, name, 0, "keen"), T(w, 0, H / 2) @ rot)
        s.inst(c, T(-w, 0, H / 2) @ rot)
        s.camera((0.0, 2.2 * w + 2.4 + H * 0.5, H * 0.6), (0, 0, H * 0.48), 36)
        s.caption("intact", (w, 0.2, H + 0.15), 0.06)
        s.caption(f"Damaged: mean {st.get('mean_mm')} mm", (-w, 0.2, H + 0.15), 0.06)
        s.render()


# ---------------------------------------------------------------------------------------------------- vanilla
def vanilla_compare(built):
    nm = "vanilla_compare"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2600, 1100), floor=(-6, 2, -2.5, 2.5), light=1.2)
    x, labels = 0.6, []
    rk = "DC_Rack42_SplitFrontRear"
    if rk in built:
        rack_with_strips(s, built, rk, x=x, rot=180, f_rear=1.0)
        labels.append(("42U rack, rear open,\nFeed A + B strips", (x, 0.0, 2.75)))
        x -= 1.15
    if CAB in built:
        s.inst(PV.painted(built, CAB, 0, "keen"), T(x, 0, 1.25))
        labels.append(("PDU Cabinet", (x, 0.0, 2.75)))
        x -= 0.9
    for rel, label in (("Walls/Inserts/Panel/Models/NonFractured/WallInsertPanel.fbx", "vanilla WallInsertPanel\n"
                                                                                         "(the clone source)"),
                       ("Batteries/Battery/50/Models/NonFractured/Battery50.fbx", "vanilla Battery50")):
        try:
            c, lo, hi = PV.vanilla(rel)
        except Exception as e:   # noqa: BLE001
            print("vanilla import failed", rel, e)
            continue
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        labels.append((label, (x - w / 2, 0.0, hi.z - lo.z + 0.3)))
        x -= w + 0.5
    s.inst(PV.human(), T(x, 0.5, 0))
    cx = (x + 0.6) / 2
    s.camera((cx, 0.9 * abs(x - 0.6) + 2.6, 2.0), (cx, 0, 1.1), 30)
    for txt, at in labels:
        s.caption(txt, at, 0.09)
    s.render()


# ---------------------------------------------------------------------------------------------------- room
def _cams():
    def cab_aisle(info):        # inside the aisle at the east end, looking at the cabinet in row A
        w, L, *_ = PR._geo(info)
        return PR.Cam((L - 2.2, 0.25 * w, 1.6), (L - 0.5, -w / 2 - 0.3, 1.25), 22)

    def cab_row(info):          # along the walkway in front of row A's backs (hot side on a cold aisle)
        w, L, x0, x1, y0, y1, front = PR._geo(info)
        walk = -(w / 2 + room_band() + 0.55)
        return PR.Cam((L + 1.6, walk, 1.7), (L - 2.2, -(w / 2 + 0.6), 1.25), 20)

    def rear_strips(info):      # in the hot aisle (the racks' backs face it): row A's rear columns and strips
        w, L, x0, x1, y0, y1, front = PR._geo(info)
        return PR.Cam((0.6, w / 2 - 0.2, 1.55), (2.2, -w / 2 - 0.1, 1.15), 20)
    PR.CAMERAS.update(pdu_cabinet_aisle=cab_aisle, pdu_cabinet_row=cab_row, pdu_rear=rear_strips)


def room_band():
    from . import room
    return room.ROW_BAND


def room_shots(built):
    _cams()
    for w, aisle in ((1.5, "cold"), (1.5, "hot"), (1.0, "cold"), (2.0, "hot")):
        PR.shot(built, "pdu_cabinet_aisle", w, aisle, captions=False)
        PR.shot(built, "pdu_cabinet_row", w, aisle, captions=False)
    PR.shot(built, "pdu_rear", 1.5, "hot", captions=False, doors_open=1.0,
            name="room_150_hot_pdu_rear_racks_open")
    PR.shot(built, "end_row", 1.5, "cold", captions=False)
    PR.shot(built, "overhead", 1.5, "cold", captions=False)
    PR.shot(built, "aisle_eye", 1.5, "hot", captions=False, doors_open=1.0, name="room_150_hot_aisle_eye_racks_open")
    PR.shot(built, "pdu_cabinet_aisle", 1.5, "cold", paint="black", name="room_150_cold_pdu_cabinet_aisle_black",
            captions=False)


def render_all(built):
    PR._out("pdu")
    hero(built)
    in_racks(built)
    closeups(built)
    drop_into_cabinet(built)
    lods(built)
    paints(built)
    fracture(built)
    damaged(built)
    vanilla_compare(built)
    room_shots(built)
    print("pdu previews ->", PV.OUT)
