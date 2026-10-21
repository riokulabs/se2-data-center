"""Plan 3 Task 4 previews: the containment roof panels.

    DC_PREVIEW=plan3-t4 blender -b --python Source/Model/build_dc.py -- "DC_Contain_Roof_*" "DC_Rack42_*" \
        "DC_Srv_*" "DC_Floor_*" "DC_Tray_Drop_Full" "DC_Tray_StraightS_Full" "DC_TrayRods_100"

Writes Source/Model/preview/p3-task-4/ (DC_SHOTS=prefix,... renders a subset; DC_FAST=1 half resolution):
  <roof>_34 / _top / _under / _section_clamp / _section_release / _lods
                                each width: 3/4 from above, top (ortho), from under (the LED, links, tags), a section
                                through a rail clamp (across the aisle) and one through a bay's fire release and the
                                LED batten (along the row), cut faces red; LOD0..n
  fracture_<roof>               the two fracture pieces (glazing lifted off the frame)
  paints_*                      keen, black and the cold / hot pair (blue, orange)
  room_*                        the reference room (dc/preview_room.py), lit in the aisle by the roofs' own LEDs:
                                looking up from the aisle at 1.7 m, aisle eye, a rail-clamp close-up on a rack, a run
                                over the racks with a KVM popped and the doors open at 85 deg, the trays above the
                                roof, overhead, outside the door, photo 1; every width, cold and hot
  vanilla_compare               the roofs beside vanilla DeckPanel250 (the clone source) and a window block
Contact sheet: python3 Source/Model/p3t4_sheet.py.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import catalog, contain, room
from . import preview as PV
from . import preview_mats as PM
from . import preview_room as PR
from .preview import Rz, T, want

ROOFS = ("DC_Contain_Roof_100", "DC_Contain_Roof_150", "DC_Contain_Roof_200")
ZC = contain.H2                       # block centre above the ground for the studio shots (the roof on the grid)
_CUT = {}


def _out():
    PR._out(4)


def _w(name):
    return contain.width(catalog.BY_NAME[name])


def _new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    PV._exclude(c)
    return c


def _copy_world(o):
    me = o.data.copy()
    me.transform(o.matrix_world)
    return me


def section(built, name, axis, at, paint="keen"):
    """A copy of LOD0 cut by the plane axis = at (the part below it kept), closed parts' cut faces red."""
    key = ("section", name, axis, at, paint)
    if key in _CUT:
        return _CUT[key]
    src = PV.painted(built, name, 0, paint)
    c = _new_coll(f"sec_{name}_{axis}_{paint}")
    red = PM.get("Section")
    no = Vector((1, 0, 0)) if axis == "x" else Vector((0, 1, 0))
    i = 0 if axis == "x" else 1
    for o in src.objects:
        if o.type != "MESH":
            continue
        me = _copy_world(o)
        bm = bmesh.new()
        bm.from_mesh(me)
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=no * at, plane_no=no, clear_outer=True)
        cut = [e for e in bm.edges if e.is_boundary and all(abs(v.co[i] - at) < 1e-5 for v in e.verts)]
        if cut and len(bm.faces) > 8:
            new = bmesh.ops.holes_fill(bm, edges=cut, sides=0)["faces"]
            if new:
                me.materials.append(red)
                for f in new:
                    f.material_index = len(me.materials) - 1
        bm.to_mesh(me)
        bm.free()
        if len(me.polygons):
            c.objects.link(bpy.data.objects.new(f"sec_{o.name}", me))
    _CUT[key] = c
    return c


def pieces(built, name, paint="keen"):
    """The two fracture pieces of LOD0 as the export assigns them (fracture.plan, per face centroid)."""
    key = ("pieces", name, paint)
    if key in _CUT:
        return _CUT[key]
    from . import fracture as FR
    spec = catalog.BY_NAME[name]
    plan = FR.plan(spec, contain.collision(spec))   # the export's zones (fracture.plan; faces by centroid)
    zones = [(z.id, *z.hull) for z in plan.zones]
    src = PV.painted(built, name, 0, paint)
    out = {}
    for z, _, _ in zones:
        c = _new_coll(f"piece_{name}_{z}_{paint}")
        for o in src.objects:
            if o.type != "MESH":
                continue
            me = _copy_world(o)
            bm = bmesh.new()
            bm.from_mesh(me)
            drop = [f for f in bm.faces if plan.zones[plan.zone_index(tuple(f.calc_center_median()))].id != z]
            bmesh.ops.delete(bm, geom=drop, context="FACES")
            bm.to_mesh(me)
            bm.free()
            if len(me.polygons):
                c.objects.link(bpy.data.objects.new(f"pc_{o.name}_{z}", me))
        out[z] = c
    _CUT[key] = out
    return out


def _under_light(s, z=0.0, energy=60.0, size=3.0):
    """A soft area light on the ground pointing up (the studio rig lights from above only)."""
    ld = bpy.data.lights.new(f"{s.name}_under", "AREA")
    ld.energy, ld.size, ld.color = energy, size, (0.95, 0.97, 1.0)
    o = bpy.data.objects.new(ld.name, ld)
    o.location = (0.4, 0.6, z)
    o.rotation_euler = (math.pi, 0, 0)
    s.sc.collection.objects.link(o)


def _led_light(s, name, M, energy_per_m=PR.ROOF_LED_W):
    spec = catalog.BY_NAME[name]
    L = contain.width(spec) - 2 * (contain.LED_END + 0.012)
    ld = bpy.data.lights.new(f"{s.name}_led", "AREA")
    ld.shape, ld.size, ld.size_y = "RECTANGLE", 2 * contain.LED_LENS_HW, L
    ld.energy, ld.color = energy_per_m * L, (0.92, 0.96, 1.0)
    o = bpy.data.objects.new(ld.name, ld)
    o.matrix_world = M @ T(0, 0, contain.LED_LENS_Z - 0.0015)
    s.sc.collection.objects.link(o)


# ---------------------------------------------------------------------------------------------------- per width
def roof_views(built, name):
    w = _w(name)
    D = 1.25 * w + 1.3
    views = {"34": dict(loc=(-0.75 * D, 0.95 * D, 0.75 * D), tgt=(0, 0, 0.12), lens=50),
             "top": dict(loc=(0, 0, 4.0), tgt=(0, 0, 0), lens=50, ortho=max(1.0, w) * 1.25 * 1800 / 1150)}
    for v, c in views.items():
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
        s.inst(PV.painted(built, name, 0), T(0, 0, ZC))
        s.camera(c["loc"], c["tgt"], c["lens"], ortho=c.get("ortho"))
        s.render()
    nm = f"{name}_under"
    if want(nm):   # lifted to the room height, seen from below: the frame's underside, clamps, links, tags, LED
        s = PV.Shot(nm, floor=None, world=(0.03, 0.032, 0.036), light=0.35)
        zr = 2.625
        M = T(0, 0, zr)
        s.inst(PV.painted(built, name, 0), M)
        _led_light(s, name, M)
        _under_light(s, 0.0, 25.0, 4.0)
        s.camera((-0.95, -0.25 * w - 0.55, 1.2), (0.05, 0.05 * w, zr), 30)
        s.render()
    W2 = w / 2
    nm = f"{name}_section_clamp"
    if want(nm):   # across the aisle through the +x end rail clamp (x = 0.375): edge beam, clamp, caps, panes
        s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
        s.inst(section(built, name, "x", 0.375), T(0, 0, ZC))
        s.camera((0.375 + 0.42, W2 - 0.16, ZC + 0.18), (0.375, W2 - 0.07, ZC + 0.06), 40)
        s.render()
    nm = f"{name}_section_release"
    if want(nm):   # along the row through a +y bay's fire release (its link, ledges, tag) and the LED batten
        spec = catalog.BY_NAME[name]
        _, _, (bx0, bx1, by0, by1) = next(b for b in contain.bays(spec) if b[0] > 0 and b[1] == len(
            contain.mullion_ys(spec)))
        yc = (by0 + by1) / 2
        s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
        s.inst(section(built, name, "y", yc + 0.0001), T(0, 0, ZC))
        _under_light(s, -0.02, 20.0, 2.0)
        s.camera((0.30, yc + 0.34, ZC + 0.02), (0.44, yc, ZC + 0.06), 42)
        s.render()
    nm = f"{name}_lods"
    if want(nm):
        lods(built, name)


def lods(built, name):
    import json
    from . import config
    nm = f"{name}_lods"
    n = len(built[name]["lods"])
    w = _w(name)
    s = PV.Shot(nm, res=(2200, 1000), floor=(-1.4 * n, 1, -w, w))
    for i in range(n):
        s.inst(PV.painted(built, name, i), T(-1.25 * i, 0, ZC))
    cx = -1.25 * (n - 1) / 2
    s.camera((cx - 0.5, 1.6 * n + 0.6 * w, 2.4 + 0.4 * w), (cx, 0, 0.0), 45)
    with open(config.REPORT_PATH) as f:
        rep = json.load(f)["blocks"].get(name, {})
    for i in range(n):
        lr = rep.get("lods", [{}] * n)[i]
        s.caption(f"LOD{i}\n{lr.get('tris', '?')}/{lr.get('max_tris', '?')} tris", (-1.25 * i, w / 2 + 0.25, 0.5), 0.07)
    s.render()


def coupling(built, name, rk="DC_Rack42_Open"):
    """The roof on a rack's containment rail, both cut at x = 0.375 (a rail pad and its clamp): the rail's lips and
    pad, the 2 mm joint, the roof's clamp jaw, flange and bolts, the edge beam, the cap over the pane. Seen along
    the row; plus the same joint uncut from the aisle below."""
    w = _w(name)
    zr = 2.25 + ZC                                     # the roof in the rack's top cell (ZT .. H)
    yr = 0.625 + w / 2                                 # the rack's front plane at y = 0.625: the roof beyond it
    nm = f"coupling_{name}_section"
    if want(nm):
        s = PV.Shot(nm, floor=(-2, 2, -1, 3))
        s.inst(section(built, rk, "x", 0.375), T(0, 0, 1.25))
        s.inst(section(built, name, "x", 0.375), T(0, yr, zr))
        s.camera((0.375 + 0.62, 0.64, 2.43), (0.375, 0.64, 2.41), 50)
        s.render()
    nm = f"coupling_{name}_aisle"
    if want(nm):
        s = PV.Shot(nm, floor=(-2, 2, -1, 3), light=0.6)
        s.inst(PV.painted(built, rk, 0), T(0, 0, 1.25))
        M = T(0, yr, zr)
        s.inst(PV.painted(built, name, 0), M)
        _led_light(s, name, M)
        _under_light(s, 0.0, 30.0, 3.0)
        s.camera((-0.42, 0.98, 2.12), (0.05, 0.62, 2.43), 32)
        s.render()


def fracture(built, name):
    nm = f"fracture_{name}"
    if not want(nm):
        return
    w = _w(name)
    pc = pieces(built, name)
    s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
    s.inst(pc["Fracture_02"], T(0, 0, ZC))
    s.inst(pc["Fracture_01"], T(0.08, -0.05 * w, ZC + 0.32 + 0.1 * w) @ Matrix.Rotation(math.radians(-14), 4, "X")
           @ Matrix.Rotation(math.radians(6), 4, "Y"))
    D = 1.25 * w + 1.3
    s.camera((-0.7 * D, 0.95 * D, 0.7 * D + 0.2), (0, 0, 0.25), 45)
    s.caption("Fracture_01: glazing (panes + caps)", (0.1, -0.1 * w, 0.85 + 0.15 * w), 0.05)
    s.caption("Fracture_02: frame, clamps, release, LED", (-0.1, 0.62 * w + 0.15, 0.05), 0.05)
    s.render()


def paints(built):
    name = "DC_Contain_Roof_150"
    for paint in ("keen", "black", "blue", "orange"):
        nm = f"paints_{paint}"
        if not want(nm):
            continue
        s = PV.Shot(nm, floor=(-2.5, 2.5, -2.5, 2.5))
        s.inst(PV.painted(built, name, 0, paint), T(0, 0, ZC))
        s.camera((-1.6, 2.6, 1.9), (0, 0, 0.1), 42)
        s.render()


def vanilla_compare(built):
    """Our three roofs beside the clone source (vanilla DeckPanel250) and a vanilla window (WindowFlat250), same
    light and stand-in materials, on one ground plane."""
    nm = "vanilla_compare"
    if not want(nm):
        return
    s = PV.Shot(nm, res=(2400, 1100), floor=(-11, 2, -2.5, 2.5))
    x, labels = 0.0, []
    for n in ROOFS:
        s.inst(PV.painted(built, n, 0), T(x - 0.5, 0, ZC))
        labels.append((n.replace("DC_Contain_", ""), (x - 0.5, 0.0, 0.9)))
        x -= 1.35
    for rel, label in (("DeckPanel/250/Models/NonFractured/DeckPanel250.fbx", "vanilla DeckPanel250"),
                       ("Windows/Flat/250/Models/NonFractured/WindowFlat250.fbx", "vanilla WindowFlat250")):
        c, lo, hi = PV.vanilla(rel)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        s.inst(c, T(x - w / 2, 0, 0) @ T(-ctr.x, -ctr.y, -lo.z))
        labels.append((label, (x - w / 2, 0.0, hi.z - lo.z + 0.3)))
        x -= w + 0.5
    cx = x / 2
    s.camera((cx, 0.85 * abs(x) + 2.5, 0.5 * abs(x) + 2.0), (cx, 0, 0.6), 30)
    for txt, at in labels:
        s.caption(txt, at, 0.08)
    s.render()


# ---------------------------------------------------------------------------------------------------- room
def _cams():
    def lookup(info):   # in the aisle at eye height, looking up along the roof run (glass, mullions, links, LEDs)
        w, L, *_ = PR._geo(info)
        return PR.Cam((0.35, -0.16 * w, 1.7), (2.8, 0.12 * w, 2.85), 16)

    def clamp(info):    # a rail clamp on rack A2's containment rail, from the aisle just under it
        w, L, *_ = PR._geo(info)
        return PR.Cam((0.92, -w / 2 + 0.30, 2.50), (1.40, -w / 2 - 0.01, 2.69), 32)

    def run(info):      # down the aisle's centre from the west door: popped KVMs and open doors under the roof
        w, L, *_ = PR._geo(info)
        return PR.Cam((-0.05, 0.0, 1.45), (3.2, 0.0, 2.3), 17)

    def kvm(info):      # from row B's rack B2, between its open leaves: A2's popped KVM, its doors, the roof
        w, L, *_ = PR._geo(info)
        return PR.Cam((1.5, w / 2 - 0.12, 1.72), (1.5, -w / 2, 2.25), 19)

    def trays(info):    # from over row B's trays toward the roof: the trays and Drops above the roof plane
        w, L, *_ = PR._geo(info)
        return PR.Cam((0.2, w / 2 + 1.6, 3.85), (2.4, 0.0, 2.7), 22, ("ceiling", "luminaires"))
    PR.CAMERAS.update(roof_lookup=lookup, roof_clamp=clamp, roof_run=run, roof_kvm=kvm, roof_trays=trays)


def _kvm_mix():
    """Every rack's top slot a KVM popped out (the room's slot mixes, the top slot replaced)."""
    return tuple(m[:-1] + ("KVM",) for m in PR.MIXES)


def room_shots(built):
    _cams()
    for w in (1.0, 1.5, 2.0):
        for aisle in ("cold", "hot"):
            PR.shot(built, "roof_lookup", w, aisle, captions=False)
    for cam in ("aisle_eye", "roof_clamp", "roof_trays", "overhead", "door_outside", "photo1"):
        PR.shot(built, cam, 1.5, "cold", captions=False)
    for cam in ("aisle_eye", "roof_trays", "overhead"):
        PR.shot(built, cam, 1.5, "hot", captions=False)
    for w in (1.0, 2.0):
        PR.shot(built, "aisle_eye", w, "cold", captions=False)
    PR.shot(built, "roof_lookup", 1.5, "cold", paint="black", name="room_150_cold_roof_lookup_black", captions=False)
    old = PR.MIXES
    PR.MIXES = _kvm_mix()
    try:
        for w in (1.5, 2.0):
            for cam in ("roof_run", "roof_kvm"):
                PR.shot(built, cam, w, "cold", name=f"room_{round(w * 100)}_cold_{cam}_kvm_doors85",
                        captions=False, doors_open=1.0)
    finally:
        PR.MIXES = old


def render_all(built):
    _out()
    for n in ROOFS:
        if n in built:
            roof_views(built, n)
    for n in ("DC_Contain_Roof_100", "DC_Contain_Roof_150"):
        if n in built:
            fracture(built, n)
    if "DC_Rack42_Open" in built and "DC_Contain_Roof_150" in built:
        coupling(built, "DC_Contain_Roof_150")
    if all(n in built for n in ROOFS):
        paints(built)
        vanilla_compare(built)
    room_shots(built)
    print("p3t4 previews ->", PV.OUT)
