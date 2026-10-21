"""Rack door previews: the rack door variants (split front; front + rear) for both heights, the tray fans
(Source/Model/preview/rack-doors/).

Same rig and stand-ins as the rack and server sets. The leaves are the built leaf subpart models placed exactly as the game places
them: at the leaf's "<name>Closed" dummy (the hinge axis) turned by the SLERP of the closed and open dummies' yaw,
i.e. yaw = closed + (open - closed) * f for the door's OpenRatio f (dc/doors.py). The perforated insert uses the
vanilla MetalPerforationSteel textures (colour + alpha mask, converted into the preview cache). A rack shown with its
doors open is a Working rack, so its power lamp is lit (the material swapper's EmissiveOff -> EmissiveGreen).
Vanilla SlidingDoorNarrow250 is imported READ ONLY from tools/vanilla-ref.

    DC_PREVIEW=rack-doors blender -b --python Source/Model/build_dc.py -- all
(DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution).
"""
import math
import os

import bpy
from mathutils import Vector

from . import catalog, config, doors
from . import dims as DM
from . import preview as PV
from . import preview_mats as PM
from . import preview_indicator_servers as pv_indicator_servers
from . import preview_ups as pv_ups
from . import preview_kvm as pv_kvm
from .preview import Rz, Shot, T, human, want

OUT = os.path.join(config.PREVIEW_DIR, "rack-doors", os.environ.get("DC_PREVIEW_SUB", ""))
DOOR_RACKS = ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
SHORT = {"DC_Rack42_SplitFront": "42U SPLIT FRONT", "DC_Rack42_SplitFrontRear": "42U FRONT + REAR",
         "DC_Rack24_SplitFront": "24U SPLIT FRONT", "DC_Rack24_SplitFrontRear": "24U FRONT + REAR",
         "DC_Rack42_Open": "42U OPEN", "DC_Rack24_Open": "24U OPEN"}
MIX42 = ("UPS", None, "DC_Srv_Storage", "DC_Srv_Timer", "KVM", "DC_Srv_Compute", "DC_Srv_Status", "PROG")
MIX24 = ("UPS", None, "DC_Srv_Switch", "DC_Srv_Compute")


def _H(name):
    return 0.25 * catalog.BY_NAME[name].cells[1]


def _copy(objs, cname, paint, working=False):
    """A painted (cached) collection of the given objects; working=True lights the EmissiveOff power lamp."""
    if cname in bpy.data.collections:
        return bpy.data.collections[cname]
    c = bpy.data.collections.new(cname)
    bpy.context.scene.collection.children.link(c)
    for o in objs:
        if o.type != "MESH":
            continue
        n = o.copy()
        n.data = o.data.copy()
        c.objects.link(n)
        for i, sl in enumerate(n.material_slots):
            if not sl.material:
                continue
            slot = sl.material.name.split(".")[0]
            key = "EmGreen" if (working and slot == "EmissiveOff") else PM.keen_key(slot, paint)
            n.material_slots[i].material = PM.get(key)
    PV._exclude(c)
    return c


def body(built, name, paint, working, lod=0):
    return _copy(built[name]["lods"][lod][1], f"pv9_{name}_L{lod}_{paint}_{int(working)}", paint, working)


def sub(built, name, model, paint, lod=0):
    lods = built[name]["subparts"][model]
    lod = min(lod, len(lods) - 1)
    return _copy(lods[lod][1], f"pv9_{name}_{model}_L{lod}_{paint}", paint)


def rack(s, built, name, x=0.0, y=0.0, rot=0.0, f=0.0, paint="keen", mix=(), fan=0.0, working=None, lod=0,
         f_rear=None):
    """A rack standing on the floor at (x, y) turned rot deg, its doors at open fraction f (rear: f_rear, default
    f), its servers from slot 1 up, its fans turned fan deg. Returns the rack's base matrix."""
    spec = catalog.BY_NAME[name]
    H = _H(name)
    M = T(x, y, 0) @ Rz(rot)
    C = M @ T(0, 0, H / 2)
    working = (f > 0 or bool(f_rear)) if working is None else working
    s.inst(body(built, name, paint, working, lod), C)
    side = (built[name].get("subparts") or {}).get("RackSide")
    if side:   # the static side panels: one model, right side and turned to the left
        for yaw in (0, 180):
            s.inst(sub(built, name, "RackSide", paint, lod), C @ Rz(yaw))
    if lod < len(built[name]["lods"]) - 1:
        for lf in doors.leaves(spec):
            fr = f if lf["sy"] > 0 else (f if f_rear is None else f_rear)
            s.inst(sub(built, name, lf["model"], paint, lod),
                   C @ T(lf["axis"][0], lf["axis"][1], 0) @ Rz(doors.swing_yaw(lf, fr)))
        tp = doors.fan_tray_point(spec)
        if tp:
            s.inst(sub(built, name, doors.FAN_TRAY_SUB, paint, lod), C @ T(*tp))
        for i, p in enumerate(doors.fan_points(spec)):
            s.inst(sub(built, name, doors.FAN, paint, lod), C @ T(*p) @ Rz(fan + 37 * i))
    for k, n in enumerate(mix, 1):
        # a KVM behind closed front doors is shown stowed (switched Off): Working, it would pop through the leaves
        if n == "KVM" and doors.door_sides(spec) and f < 1.0:
            n = "KVM0"
        srv(s, built, n, M, 0.25 * k, paint)
    return M


def srv(s, built, n, M, z, paint):
    if not n:
        return
    loc = M @ Vector((0, 0, 0))
    rot = math.degrees(M.to_euler().z)
    x, y = loc.x, loc.y
    if n == "KVM":
        pv_kvm.kvm(s, built, x, y, z, paint, f=1.0, rot=rot)
    elif n == "KVM0":
        pv_kvm.kvm(s, built, x, y, z, paint, f=0.0, rot=rot)
    elif n == "UPS":
        pv_ups.ups(s, built, x, y, z, paint, rot=rot)
    elif n == "PROG":
        pv_kvm.prog(s, built, x, y, z, paint, rot=rot)
    else:
        pv_indicator_servers.srv(s, built, n, x, y, z, paint, rot=rot)


def flat(s, txt, loc, size):
    """A caption lying flat (readable from straight above, +Y up): for the plan views."""
    o = s.caption(txt, loc, size)
    o.constraints.clear()
    o.rotation_euler = (0, 0, 0)
    return o


def floor_for(H, w=2.0):
    return (-w, w, -w, w + 1.0)


# ---------------------------------------------------------------------------------------------------- per variant
def per_variant(built):
    for name in DOOR_RACKS:
        H = _H(name)
        zc = H / 2
        rear = len(doors.door_sides(catalog.BY_NAME[name])) == 2
        d = 4.6 if H > 2 else 3.0
        views = {
            "closed_front": (0.0, ((0.0, d, zc), (0, 0, zc), 40)),
            "closed_3q": (0.0, ((-0.62 * d, 0.78 * d, zc + 0.9), (0, 0.1, zc * 0.95), 38)),
            "closed_back": (0.0, ((0.0, -d, zc), (0, 0, zc), 40)),
            "open_front": (1.0, ((0.0, d + 0.6, zc), (0, 0.4, zc), 40)),
            "open_3q": (1.0, ((-0.62 * d, 0.78 * d + 0.4, zc + 0.9), (0, 0.35, zc * 0.95), 38)),
            "open_top_plan": (1.0, ((0.0, 0.0, H + 4.0), (0, 0.0, 0.0), 40, 3.4)),
        }
        if rear:
            views["open_back_3q"] = (1.0, ((0.62 * d, -0.78 * d - 0.4, zc + 0.9), (0, -0.35, zc * 0.95), 38))
        for v, (f, cam) in views.items():
            nm = f"{name}_{v}"
            if not want(nm):
                continue
            s = Shot(nm, res=(1600, 1400) if v != "open_top_plan" else (1500, 1500), floor=floor_for(H))
            rack(s, built, name, f=f, mix=MIX42 if H > 2 else MIX24, fan=10)
            if len(cam) == 4:
                s.camera(cam[0], cam[1], cam[2], ortho=cam[3])
                s.cam.rotation_euler = (0, 0, 0)
            else:
                s.camera(*cam)
            if v == "open_top_plan":
                flat(s, f"{SHORT[name]}: doors at the {DM.DOOR_OPEN_DEG:.0f} deg cap", (0, -1.4, H + 0.1), 0.09)
            s.render()
        for f in (0.25, 0.5, 0.75):
            nm = f"{name}_anim_f{int(f * 100):03d}"
            if not want(nm):
                continue
            s = Shot(nm, res=(1600, 1400), floor=floor_for(H))
            rack(s, built, name, f=f, mix=MIX42 if H > 2 else MIX24, fan=40 * f)
            s.camera((-0.62 * d, 0.78 * d + 0.4, zc + 0.9), (0, 0.35, zc * 0.95), 38)
            s.caption(f"OpenRatio {f:.2f}: leaves at {DM.DOOR_OPEN_DEG * f:.1f} deg", (0, 0.4, H + 0.25), 0.07)
            s.render()


# ---------------------------------------------------------------------------------------------------- neighbours
def neighbours(built):
    name = "DC_Rack42_SplitFrontRear"
    spec = catalog.BY_NAME[name]
    rep = pv_kvm._rep(name).get("doors", {})
    H = _H(name)
    hulls = {m: [tuple(p) for p in h] for m, h in rep["hulls"].items()}
    lv = {lf["name"]: lf for lf in doors.leaves(spec)}
    gaps = []
    for sy, a, b in ((1, "RightDoor", "LeftDoor"), (-1, "RearRightDoor", "RearLeftDoor")):
        P = doors.placed_hull(lv[a], hulls[lv[a]["model"]], lv[a]["yaw_open"])
        Q = doors.placed_hull(lv[b], hulls[lv[b]["model"]], lv[b]["yaw_open"], dx=1.0)
        gaps.append(doors.closest_points(P, Q))
    for nm, cam in (("pair_all_open_front", ((0.5, 4.8, 1.25), (0.5, 0.4, 1.2), 40, None)),
                    ("pair_all_open_3q", ((-2.6, 3.9, 2.5), (0.5, 0.3, 1.1), 36, None)),
                    ("pair_all_open_top_plan", ((0.5, 0.0, H + 4), (0.5, 0.0, 0), 40, 3.6)),
                    ("pair_all_open_top_plan_gap_closeup", ((0.5, 0.75, H + 3), (0.5, 0.75, 0), 40, 0.42))):
        if not want(nm):
            continue
        s = Shot(nm, res=(1800, 1500), floor=(-1.5, 2.5, -2.2, 2.2))
        for x in (0.0, 1.0):
            rack(s, built, name, x=x, f=1.0, mix=MIX42, fan=20 * x)
        loc, tgt, lens, ortho = cam
        s.camera(loc, tgt, lens, ortho=ortho)
        if ortho:
            s.cam.rotation_euler = (0, 0, 0)
            for d, p, q in gaps:
                mk = marker((p[0], p[1], H + 0.02), (q[0], q[1], H + 0.02))
                s.link(mk)
                sz = 0.09 if ortho > 1 else 0.012
                yoff = (0.25 if p[1] > 0 else -0.25) if ortho > 1 else (0.04 if p[1] > 0 else -0.04)
                flat(s, f"{d * 1000:.0f} mm clear at {DM.DOOR_OPEN_DEG:.0f} deg", ((p[0] + q[0]) / 2,
                                                                                    p[1] + yoff, H + 0.05), sz)
            if ortho > 1:
                flat(s, f"two {SHORT[name]} racks flush (1.0 m pitch), all 8 leaves at the cap;\n"
                        f"max clear angle {rep['max_clear_deg']:.1f} deg", (0.5, -1.25, H + 0.05), 0.07)
        s.render()


def marker(p, q):
    """A thin red bar from p to q (the measured gap), plus end ticks."""
    import bmesh
    bm = bmesh.new()
    p, q = Vector(p), Vector(q)
    d = (q - p)
    L = max(d.length, 1e-4)
    n = Vector((-d.y, d.x, 0)).normalized() if L > 1e-4 else Vector((0, 1, 0))
    for a, b, w in ((p, q, 0.0012), (p - n * 0.006, p + n * 0.006, 0.0008), (q - n * 0.006, q + n * 0.006, 0.0008)):
        e = (b - a)
        m = e.normalized().cross(Vector((0, 0, 1))).normalized() * w
        vs = [bm.verts.new(v) for v in (a - m, b - m, b + m, a + m)]
        bm.faces.new(vs)
    me = bpy.data.meshes.new("gap_marker")
    bm.to_mesh(me)
    me.materials.append(PM.get("EmRed"))
    return bpy.data.objects.new("gap_marker", me)


# ---------------------------------------------------------------------------------------------------- populated
def populated(built):
    nm = "rack42_split_front_open_populated_kvm_popped"
    if want(nm):
        s = Shot(nm, res=(1800, 1500), floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, "DC_Rack42_SplitFront", f=1.0, mix=MIX42, fan=15)
        s.camera((-1.9, 3.6, 2.0), (0, 0.4, 1.3), 34)
        s.render()
    nm = "rack42_split_front_open_kvm_first_person"
    if want(nm):
        s = Shot(nm, res=(1800, 1300), floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, "DC_Rack42_SplitFront", f=1.0, mix=MIX42, fan=15)
        s.camera((0.35, 2.05, 1.72), (0.0, 0.4, 1.25), 28)
        s.render()
    nm = "rack42_front_rear_back_open_ups_rear_bay"
    if want(nm):
        s = Shot(nm, res=(1800, 1500), floor=(-2.5, 2.5, -4.0, 2.5))
        rack(s, built, "DC_Rack42_SplitFrontRear", f=1.0, mix=MIX42, fan=15)
        s.inst(human(), T(1.45, -1.2, 0) @ Rz(40))
        s.camera((0.9, -3.9, 1.5), (0.2, -0.4, 0.9), 34)
        s.render()
    nm = "rack42_front_rear_back_open_ups_rear_bay_closeup"
    if want(nm):
        s = Shot(nm, res=(1800, 1300), floor=(-2.5, 2.5, -4.0, 2.5))
        rack(s, built, "DC_Rack42_SplitFrontRear", f=1.0, mix=MIX42, fan=15)
        s.camera((0.55, -1.75, 0.95), (0.0, -0.4, 0.5), 32)
        s.render()


# ---------------------------------------------------------------------------------------------------- close-ups
def closeups(built):
    name = "DC_Rack42_SplitFront"
    spec = catalog.BY_NAME[name]
    H = _H(name)
    zh = doors.hinge_zs(spec)[0] + H / 2
    zc = doors.handle_z(spec) + H / 2
    ax, ay = DM.DOOR_AXIS_X, DM.DOOR_AXIS_Y
    shots = {
        "closeup_hinge_closed": (0.0, ((0.75, 0.95, zh + 0.12), (ax, ay, zh), 40)),
        "closeup_hinge_open": (1.0, ((0.80, 1.05, zh + 0.15), (ax, ay + 0.05, zh), 40)),
        "closeup_handle_hazard": (0.0, ((-0.12, 0.95, zc + 0.08), (0.02, ay, zc), 38)),
        "closeup_perforation": (0.0, ((0.15, 1.05, 1.35), (0.18, ay, 1.30), 40)),
        "closeup_perforation_open_servers_behind": (0.0, ((-0.3, 1.25, 1.55), (-0.15, 0.45, 1.35), 32)),
        "closeup_meeting_edge": (0.0, ((0.0, 0.80, zc + 0.35), (0.0, ay, zc + 0.2), 40)),
    }
    for v, (f, cam) in shots.items():
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, name, f=f, mix=MIX42, fan=0)
        s.camera(*cam)
        s.render()
    # fan tray from above (the open-top trough), and a section look from below the tray
    for nm, cam in (("DC_Rack42_SplitFront_closeup_fan_tray", ((0.3, 0.35, 3.25), (0.0, -0.3, 2.28), 34)),
                    ("DC_Rack42_SplitFront_closeup_fan_tray_rear", ((0.75, -1.25, 3.55), (0.0, -0.15, 2.3), 34))):
        if not want(nm):
            continue
        s = Shot(nm, res=(1600, 1200), floor=(-2.5, 2.5, -2.5, 4.0))
        rack(s, built, "DC_Rack42_SplitFront", f=0.0, mix=MIX42, fan=25, working=True)
        s.camera(*cam)
        s.render()


# ---------------------------------------------------------------------------------------------------- set pieces
def paints(built):
    nm = "door_variants_3_paints"
    if not want(nm):
        return
    s = Shot(nm, res=(3000, 1500), floor=(-1.0, 12.5, -2.0, 3.0))
    x = 0.0
    for p in ("black", "keen", "blue"):
        for name in DOOR_RACKS:
            rack(s, built, name, x=x, f=0.0 if "Rear" not in name else 1.0, paint=p,
                 mix=MIX42 if "42" in name else MIX24)
            x += 1.0
        x += 0.3
    s.camera((5.7, 9.2, 2.4), (5.7, 0, 1.0), 36)
    for i, p in enumerate(("BLACK", "KEEN GREY", "BLUE")):
        s.caption(p, (1.5 + 4.3 * i, 0.4, 2.85), 0.12)
    s.render()


def row_and_aisle(built):
    row = (("DC_Rack42_SplitFront", 0.0), ("DC_Rack42_SplitFrontRear", 1.0), ("DC_Rack42_Open", 0.0),
           ("DC_Rack24_SplitFront", 1.0), ("DC_Rack24_SplitFrontRear", 0.0), ("DC_Rack42_SplitFront", 1.0),
           ("DC_Rack24_Open", 0.0))
    nm = "row_mixed_door_variants"
    if want(nm):
        s = Shot(nm, res=(3000, 1400), floor=(-1.0, 7.5, -2.0, 4.0))
        for i, (n, f) in enumerate(row):
            rack(s, built, n, x=1.0 * i, f=f, mix=MIX42 if "42" in n else MIX24, fan=13 * i)
        s.inst(human(), T(3.0, 1.9, 0) @ Rz(200))
        s.camera((3.0, 8.3, 2.0), (3.0, 0, 1.05), 33)
        for i, (n, f) in enumerate(row):
            s.caption(SHORT[n] + ("\nopen" if f else "\nclosed"), (1.0 * i, 0.6, _H(n) + 0.22), 0.06)
        s.render()
    nm = "aisle_first_person"
    if want(nm):
        s = Shot(nm, res=(2000, 1300), floor=(-1.0, 7.5, -2.5, 4.5))
        for i, (n, f) in enumerate(row):          # row A faces +y (the aisle), row B across a 1.5 m aisle faces -y
            rack(s, built, n, x=1.0 * i, f=f, mix=MIX42 if "42" in n else MIX24, fan=13 * i)
            m = row[(i + 3) % len(row)]
            rack(s, built, m[0], x=1.0 * i, y=2.75, rot=180, f=1.0 - m[1], mix=MIX42 if "42" in m[0] else MIX24,
                 fan=7 * i)
        s.camera((-2.3, 1.375, 1.68), (4.0, 1.3, 1.0), 24)
        s.render()


def vanilla_compare(built):
    nm = "door_vanilla_comparison_SlidingDoorNarrow250"
    if not want(nm):
        return
    base = "Doors/SlideDoorNarrow/250/Models/NonFractured/"
    fr, lo, hi = PV.vanilla(base + "NarrowSlidingDoor.fbx")
    left, _, _ = PV.vanilla(base + "LeftDoor/NarrowSlidingDoor_LeftDoor.fbx")
    right, _, _ = PV.vanilla(base + "RightDoor/NarrowSlidingDoor_RightDoor.fbx")
    s = Shot(nm, res=(2600, 1400), floor=(-6.0, 1.5, -2.0, 3.0))
    rack(s, built, "DC_Rack42_SplitFront", x=0.0, f=0.0, mix=MIX42)
    rack(s, built, "DC_Rack42_SplitFront", x=-1.3, f=1.0, mix=MIX42)
    ctr = (lo + hi) / 2
    mv = T(-3.6, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z)
    s.inst(fr, mv)
    # vanilla leaves at their closed dummies (game x 0.625 / -0.59 -> Blender x; the leaf FBX share the block frame)
    s.inst(left, mv @ T(0.625, 0, 0))
    s.inst(right, mv @ T(-0.59, 0, 0))
    s.inst(human(), T(-5.3, 0.3, 0) @ Rz(180))
    s.camera((-2.4, 9.0, 1.7), (-2.4, 0, 1.3), 33)
    for txt, x in (("OURS: 42U split front\nclosed", 0.0), ("OURS: open (85 deg)", -1.3),
                   ("vanilla SlidingDoorNarrow250\n(same door mechanism)", -3.6)):
        s.caption(txt, (x, 0.7, 2.75), 0.075)
    s.render()


def lods(built):
    for name in ("DC_Rack42_SplitFront", "DC_Rack24_SplitFront"):
        nm = f"{name}_leaf_lods"
        if not want(nm):
            continue
        rep = pv_kvm._rep(name).get("subparts", {}).get("models", {})
        lodsL = built[name]["subparts"][doors.LEAF_R]
        s = Shot(nm, res=(2200, 1300), floor=(-2.5, 1.0, -1.0, 2.0))
        s.camera((-0.95, 4.5, _H(name) / 2 + 0.3), (-0.95, 0, _H(name) / 2), 35)
        for i in range(len(lodsL)):
            s.inst(sub(built, name, doors.LEAF_R, "keen", i), T(-0.7 * i, 0, _H(name) / 2))
            r = rep.get(doors.LEAF_R, {}).get("lods", [{}] * 9)[i]
            s.caption(f"leaf LOD{i}\n{r.get('tris', '?')}/{r.get('max_tris', '?')} tris, "
                      f"{r.get('materials', '?')}/{r.get('max_materials', '?')} mats", (-0.7 * i - 0.25, 0.3,
                                                                                           _H(name) + 0.2), 0.05)
        s.render()


def render_all(built):
    PV.OUT = OUT
    PM.get("Caption")
    need = DOOR_RACKS + ("DC_Srv_KVM", "DC_Srv_UPS", "DC_Srv_Programmable") + pv_indicator_servers.FUNC + pv_indicator_servers.DECO
    missing = [n for n in need if n not in built]
    if missing:
        print("rack-doors previews need", missing)
        return
    per_variant(built)
    neighbours(built)
    populated(built)
    closeups(built)
    paints(built)
    if all(n in built for n in ("DC_Rack42_Open", "DC_Rack24_Open")):
        row_and_aisle(built)
    vanilla_compare(built)
    lods(built)
