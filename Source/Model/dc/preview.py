"""The rack preview set for the open racks (rendered by build_dc.py unless --no-render).

Writes into Source/Model/preview/racks/. Every scene uses the v2 mockup look: EEVEE, AgX Base Contrast, the
SE-ish neutral lighting and the same Keen-slot material stand-ins on our blocks and on vanilla blocks
(dc/preview_mats.py). Vanilla FBX are imported READ ONLY from tools/vanilla-ref (never written).
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import catalog, config, rack
from . import preview_mats as PM

OUT = os.path.join(config.PREVIEW_DIR, "racks")
VREF = os.path.join(config.VANILLA_REF, "Blocks")
FULL, HALF = "DC_Rack42_Open", "DC_Rack24_Open"
FAST = bool(os.environ.get("DC_FAST"))
ONLY = [s for s in os.environ.get("DC_SHOTS", "").split(",") if s]
_PAINTED = {}
_VAN = {}


def T(x, y, z):
    return Matrix.Translation((x, y, z))


def Rz(deg):
    return Matrix.Rotation(math.radians(deg), 4, "Z")


# ---------------------------------------------------------------------------------------------------- sources
def _exclude(coll):
    def walk(lc):
        if lc.collection == coll:
            lc.exclude = True
            return True
        return any(walk(c) for c in lc.children)
    walk(bpy.context.scene.view_layers[0].layer_collection)


def painted(built, name, lod=0, paint="keen"):
    """A copy of one LOD of a built block with preview stand-ins for the given paint (cached collection)."""
    key = (name, lod, paint)
    if key in _PAINTED:
        return _PAINTED[key]
    src_coll, objs = built[name]["lods"][lod]
    c = bpy.data.collections.new(f"pv_{name}_LOD{lod}_{paint}")
    bpy.context.scene.collection.children.link(c)
    for o in objs:
        n = o.copy()
        n.data = o.data.copy()
        c.objects.link(n)
        PM.apply([n], paint)
    _exclude(c)
    _PAINTED[key] = c
    return c


def vanilla(rel, paint="keen"):
    """Import a vanilla FBX read-only into an excluded collection; materials swapped for the stand-ins."""
    key = (rel, paint)
    if key in _VAN:
        return _VAN[key]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(VREF, rel))
    new = [o for o in bpy.data.objects if o not in before]
    c = bpy.data.collections.new("v_" + os.path.basename(rel))
    bpy.context.scene.collection.children.link(c)
    for o in new:
        for uc in list(o.users_collection):
            uc.objects.unlink(o)
        c.objects.link(o)
        if o.type == "MESH":
            PM.apply([o], paint)
    _exclude(c)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(b) for o in new if o.type == "MESH" for b in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    _VAN[key] = (c, lo, hi)
    return _VAN[key]


def human():
    """A 1.80 m human silhouette (mannequin) for scale."""
    if "pv_human" in bpy.data.collections:
        return bpy.data.collections["pv_human"]
    c = bpy.data.collections.new("pv_human")
    bpy.context.scene.collection.children.link(c)
    bm = bmesh.new()

    def capsule(p0, p1, r):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        m = Matrix.Translation((p0 + p1) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r, depth=d.length, matrix=m)
        for q in (p0, p1):
            bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=r, matrix=Matrix.Translation(q))
    for sx in (-1, 1):
        capsule((sx * 0.10, 0, 0.08), (sx * 0.10, 0, 0.50), 0.065)      # shins
        capsule((sx * 0.10, 0, 0.50), (sx * 0.10, 0, 0.90), 0.08)       # thighs
        capsule((sx * 0.23, 0, 1.43), (sx * 0.26, 0, 1.12), 0.05)       # upper arms
        capsule((sx * 0.26, 0, 1.12), (sx * 0.27, 0.02, 0.84), 0.042)   # forearms
        capsule((sx * 0.10, 0.06, 0.03), (sx * 0.10, -0.08, 0.03), 0.035)  # feet
    capsule((0, 0, 0.95), (0, 0, 1.40), 0.17)                            # torso
    capsule((0, 0, 1.47), (0, 0, 1.52), 0.05)                            # neck
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.11, matrix=Matrix.Translation((0, 0, 1.69)))
    me = bpy.data.meshes.new("pv_human")
    bm.to_mesh(me)
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(PM.get("Human"))
    ob = bpy.data.objects.new("pv_human", me)
    c.objects.link(ob)
    _exclude(c)
    return c


# ---------------------------------------------------------------------------------------------------- scenes
class Shot:
    def __init__(self, name, res=(1800, 1150), floor=(-3, 3, -3, 3), world=(0.055, 0.058, 0.063), light=1.0,
                 floor_z=0.0):
        self.name = name
        sc = bpy.data.scenes.new(name)
        self.sc = sc
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 50 if FAST else 100
        sc.render.engine = "BLENDER_EEVEE"
        for k, v in (("taa_render_samples", 16 if FAST else 64), ("use_raytracing", True), ("use_shadows", True),
                     ("use_gtao", True), ("fast_gi_method", "GLOBAL_ILLUMINATION")):
            try:
                setattr(sc.eevee, k, v)
            except Exception:
                pass
        try:
            sc.view_settings.view_transform = "AgX"
            sc.view_settings.look = "AgX - Base Contrast"
        except Exception:
            pass
        w = bpy.data.worlds.new("W_" + name)
        sc.world = w
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (*world, 1)
        # the v2 mockup rig (lighting_se), mirrored for front = +Y: key front-right-high, cool fill front-left,
        # rim from behind, soft top; each area light aims at the scene centre
        for nm, loc, e, sz, col in (("key", (3, 5, 6), 900, 5, (1.0, 0.97, 0.93)),
                                    ("fill", (-6, 3, 3), 380, 7, (0.88, 0.92, 1.0)),
                                    ("rim", (0, -6, 5), 450, 4, (0.95, 0.97, 1.0)),
                                    ("top", (0, 0.01, 8), 250, 10, (1, 1, 1))):
            ld = bpy.data.lights.new(f"{name}_{nm}", "AREA")
            ld.energy, ld.size, ld.color = e * light, sz, col
            o = bpy.data.objects.new(ld.name, ld)
            o.location = loc
            o.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
            sc.collection.objects.link(o)
        if floor:
            self.grid(*floor, z=floor_z)

    def grid(self, x0, x1, y0, y1, step=0.25, z=0.0):
        bm = bmesh.new()
        me = bpy.data.meshes.new("floor")

        def box(lo, hi, mi):
            vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
            bmesh.ops.scale(bm, vec=Vector(hi) - Vector(lo), verts=vs)
            bmesh.ops.translate(bm, vec=(Vector(lo) + Vector(hi)) / 2, verts=vs)
            for f in {f for v in vs for f in v.link_faces}:
                f.material_index = mi
        box((x0, y0, z - 0.01), (x1, y1, z), 0)
        x = x0
        while x <= x1 + 1e-6:
            box((x - 0.003, y0, z), (x + 0.003, y1, z + 0.0006), 1)
            x += step
        y = y0
        while y <= y1 + 1e-6:
            box((x0, y - 0.003, z), (x1, y + 0.003, z + 0.0006), 1)
            y += step
        bm.to_mesh(me)
        me.materials.append(PM.get("Floor"))
        me.materials.append(PM.get("Darker"))
        self.sc.collection.objects.link(bpy.data.objects.new("floor", me))

    def inst(self, coll, m):
        e = bpy.data.objects.new("i_" + coll.name, None)
        e.instance_type = "COLLECTION"
        e.instance_collection = coll
        e.matrix_world = m
        self.sc.collection.objects.link(e)
        return e

    def link(self, ob):
        self.sc.collection.objects.link(ob)
        return ob

    def camera(self, loc, target, lens=50, ortho=None):
        cam = bpy.data.objects.new("cam_" + self.name, bpy.data.cameras.new("cam_" + self.name))
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.clip_start = 0.02
        cam.data.clip_end = 200
        if ortho:
            cam.data.type, cam.data.ortho_scale = "ORTHO", ortho
        self.sc.collection.objects.link(cam)
        self.sc.camera = cam
        self.cam = cam
        return cam

    def caption(self, txt, loc, size=0.07):
        cu = bpy.data.curves.new("cap", "FONT")
        cu.body = txt
        cu.size = size
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        cu.materials.append(PM.get("Caption"))
        o = bpy.data.objects.new("cap", cu)
        o.location = loc
        self.sc.collection.objects.link(o)
        con = o.constraints.new("TRACK_TO")
        con.target = self.cam
        con.track_axis, con.up_axis = "TRACK_Z", "UP_Y"
        return o

    def render(self):
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, self.name + ".png")
        self.sc.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=self.sc.name)
        print("WROTE", path)
        return path


def _H(name):
    return 0.25 * catalog.BY_NAME[name].cells[1]


def want(name):
    return not ONLY or any(name.startswith(o) for o in ONLY)


# ---------------------------------------------------------------------------------------------------- shots
VIEWS = ("front", "back", "left", "right", "3q_front_left", "3q_back_right", "top")


def turntable(built, name, paint="keen"):
    H = _H(name)
    zc = H / 2
    D = 2.5 * H + 0.6 if H > 2 else 4.2
    for v in VIEWS:
        nm = f"{name}_{v}"
        if not want(nm):
            continue
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        s.inst(painted(built, name, 0, paint), T(0, 0, H / 2))
        loc = {"front": (0, D, zc), "back": (0, -D, zc), "left": (-D, 0, zc), "right": (D, 0, zc),
               "3q_front_left": (-0.55 * D, 0.8 * D, zc + 0.38 * D), "3q_back_right": (0.55 * D, -0.8 * D, zc + 0.38 * D),
               "top": (0.0, 0.25, zc + D)}[v]
        s.camera(loc, (0, 0, zc * (0.95 if v != "top" else 1.0)), 50)
        s.render()


def closeups(built, paint="keen"):
    H = _H(FULL)
    shots = {   # name: (camera, target, lens)
        "closeup_slot_rails": ((0.30, 1.25, 1.25), (-0.27, 0.05, 1.0), 30),
        "closeup_top_tray": ((0.85, 1.35, 3.35), (0.0, 0.05, 2.38), 32),
        "closeup_plinth": ((0.75, 1.55, 0.42), (0.0, 0.45, 0.13), 34),
        "closeup_cable_manager": ((0.95, 1.35, 1.55), (0.37, 0.48, 1.25), 38),
        "closeup_corner_cap": ((0.95, 1.05, 2.85), (0.44, 0.55, 2.38), 42),
        "closeup_corner_cap_bottom": ((0.95, 1.05, 0.55), (0.44, 0.55, 0.12), 42),
        "closeup_label_plate": ((0.18, 1.25, 2.42), (0.0, 0.58, 2.365), 55),
        "closeup_rear_power_combs": ((-0.85, -1.35, 1.5), (-0.37, -0.48, 1.25), 38),
    }
    for nm, (loc, tgt, lens) in shots.items():
        nm = f"{FULL}_{nm}"
        if not want(nm):
            continue
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        s.inst(painted(built, FULL, 0, paint), T(0, 0, H / 2))
        s.camera(loc, tgt, lens)
        s.render()
    # the layered side panels and the slide-rail kits, both racks
    for name in (FULL, HALF):
        Hn = _H(name)
        zt = Hn if name == HALF else 2.25
        extra = {
            f"{name}_side_detail_closeup": ((2.0, 1.15, zt * 0.62 + 0.25), (0.5, 0.0, zt * 0.5), 34),
            f"{name}_slot_rails_v2_closeup": ((0.22, 1.35, min(1.35, zt - 0.1)), (-0.25, 0.0, min(1.05, zt * 0.55)), 28),
        }
        for nm, (loc, tgt, lens) in extra.items():
            if not want(nm):
                continue
            s = Shot(nm, floor=(-1.5, 2.5, -1.5, 2.5))
            s.inst(painted(built, name, 0, paint), T(0, 0, Hn / 2))
            s.camera(loc, tgt, lens)
            s.render()
    nm = f"{HALF}_closeup_roof_and_label"
    if want(nm):
        Hh = _H(HALF)
        s = Shot(nm, floor=(-1.5, 1.5, -1.5, 1.5))
        s.inst(painted(built, HALF, 0, paint), T(0, 0, Hh / 2))
        s.camera((0.9, 1.9, 1.95), (0.0, 0.2, 0.55), 30)
        s.render()


def lods(built, name, paint="keen"):
    nm = f"{name}_lods"
    if not want(nm):
        return
    n = len(built[name]["lods"])
    H = _H(name)
    s = Shot(nm, res=(2200, 1000), floor=(-1.3 * n, 1, -1.2, 1.2))
    for i in range(n):
        s.inst(painted(built, name, i, paint), T(-1.3 * i, 0, H / 2))   # cameras look from +Y: +X is image-left
    cx = -1.3 * (n - 1) / 2
    s.camera((cx - 0.9, 2.4 * n + 0.8, H * 0.9 + 1.2), (cx, 0, H * 0.45), 50)
    rep = {}
    import json
    with open(config.REPORT_PATH) as f:
        rep = json.load(f)["blocks"].get(name, {})
    for i in range(n):
        lr = rep.get("lods", [{}] * n)[i] if rep.get("lods") else {}
        s.caption(f"LOD{i}\n{lr.get('tris', '?')}/{lr.get('max_tris', '?')} tris", (-1.3 * i, 0.7, H + 0.25), 0.075)
    s.render()


def scale(built, paint="keen"):
    nm = "racks_human_scale"
    if not want(nm):
        return
    s = Shot(nm, res=(2000, 1150), floor=(-3, 2, -1.5, 2))
    s.camera((-1.0, 7.6, 1.7), (-1.0, 0, 1.3), 35)
    s.inst(painted(built, FULL, 0, paint), T(0, 0, _H(FULL) / 2))
    s.inst(painted(built, HALF, 0, paint), T(-1.25, 0, _H(HALF) / 2))
    s.inst(human(), T(-2.25, 0.4, 0) @ Rz(160))
    s.caption("full rack 42\n1.00 x 2.50 x 1.25 m", (0, 0.7, 2.75), 0.075)
    s.caption("half rack 24\n1.00 x 1.25 x 1.25 m", (-1.25, 0.7, 1.5), 0.075)
    s.caption("human 1.80 m", (-2.25, 0.5, 2.0), 0.075)
    s.render()


def paints(built):
    nm = "racks_paints_black_keen_blue"
    if not want(nm):
        return
    s = Shot(nm, res=(2200, 1250), floor=(-6.5, 2.5, -1.5, 2.5))
    s.camera((1.2, 9.0, 3.8), (-2.3, 0, 0.95), 30)
    for i, p in enumerate(("black", "keen", "blue")):
        s.inst(painted(built, FULL, 0, p), T(1.0 - i * 1.0, 0, _H(FULL) / 2))      # a flush row of three
        s.inst(painted(built, HALF, 0, p), T(-3.0 - i * 1.0, 0, _H(HALF) / 2))
    for i, p in enumerate(("BLACK", "KEEN GREY", "BLUE")):
        s.caption(p, (1.0 - i * 1.0, 0.9, 0.05), 0.09)
        s.caption(p, (-3.0 - i * 1.0, 0.9, 0.05), 0.09)
    s.render()


def ghost_boxes(spec, base, coll_name, mat="GhostSlot"):
    """One box per SLOT_CELLS cell, converted from game cells back to Blender (the real inverse transform), so the
    boxes show exactly where the generator expects the servers; joined per slot into 2x1x3 blocks."""
    from se2model import placement as PL
    shift = PL.shift_for_bounds(catalog.bounds(spec))
    cells = rack.SLOT_CELLS(spec)
    bm = bmesh.new()
    for (cx, cy, cz) in cells:
        g = Vector((cx * 0.25 - shift[0], cy * 0.25 - shift[1], cz * 0.25 - shift[2]))   # glTF centre
        c = Vector((g.x, -g.z, g.y)) + base                                                  # Blender
        vs = bmesh.ops.create_cube(bm, size=0.25 - 0.004)["verts"]
        bmesh.ops.translate(bm, vec=c, verts=vs)
    me = bpy.data.meshes.new(coll_name)
    bm.to_mesh(me)
    me.materials.append(PM.get(mat))
    return bpy.data.objects.new(coll_name, me)


def wire_copy(ob, mat="GhostSlot", t=0.004):
    w = ob.copy()
    w.data = ob.data.copy()
    w.data.materials.clear()
    w.data.materials.append(PM.get(mat.replace("Ghost", "Em") if False else "EmWhite"))
    md = w.modifiers.new("wf", "WIREFRAME")
    md.thickness = t
    return w


def slot_proof(built, paint="black"):
    """Ghost 2x1x3 boxes in every slot. 3q / front: both racks; section_side: an ortho cut at x = 0 (camera near
    plane), section_plan: an ortho plan cut through slot 5 of the full rack at z = 1.375 m."""
    for view in ("3q", "front", "section_side", "section_plan"):
        nm = f"racks_slot_proof_{view}"
        if not want(nm):
            continue
        s = Shot(nm, res=(2000, 1200), floor=(-3.0, 1.5, -2.0, 2.0))
        if view == "3q":
            s.camera((1.1, 4.4, 2.9), (-0.8, 0, 1.0), 38)
            place = ((FULL, 0.0, 0.0), (HALF, -1.6, 0.0))
        elif view == "front":
            s.camera((-0.8, 6.0, 1.3), (-0.8, 0, 1.2), 45)
            place = ((FULL, 0.0, 0.0), (HALF, -1.6, 0.0))
        elif view == "section_side":
            s.camera((6.0, 0.0, 1.3), (0.0, 0.0, 1.3), 50, ortho=4.4)
            s.cam.data.clip_start = 6.0           # near plane = the x = 0 section
            place = ((FULL, 0.0, 0.85), (HALF, 0.0, -0.85))
        else:
            s.camera((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), 50, ortho=1.7)
            s.cam.data.clip_start = 10.0 - 1.375  # near plane = mid-height of slot 5
            place = ((FULL, 0.0, 0.0),)
        for name, x, y in place:
            spec = catalog.BY_NAME[name]
            H = _H(name)
            s.inst(painted(built, name, 0, paint), T(x, y, H / 2))
            g = s.link(ghost_boxes(spec, Vector((x, y, H / 2)), f"ghost_{name}_{view}"))
            s.link(wire_copy(g))
        if view in ("3q", "front"):
            s.caption("cyan = rack.SLOT_CELLS (2x1x3 cells per slot)\nfree cells in the build report: "
                      f"{FULL} 48, {HALF} 24", (-0.8, 0.9, 2.95), 0.06)
        s.render()


def collision_view(built):
    nm = "racks_collision_and_hints"
    if not want(nm):
        return
    s = Shot(nm, res=(2000, 1200), floor=(-3.0, 1.5, -1.5, 2.0))
    s.camera((1.8, 6.4, 3.6), (-0.8, 0, 1.05), 36)
    for name, x in ((FULL, 0.0), (HALF, -1.6)):
        H = _H(name)
        s.inst(painted(built, name, 0, "keen"), T(x, 0, H / 2))
        for kind, ob in built[name]["collision"]:
            g = ob.copy()
            g.data = ob.data.copy()
            g.matrix_world = T(x, 0, H / 2)
            g.display_type = "SOLID"
            g.data.materials.clear()
            g.data.materials.append(PM.get({"regular": "GhostReg", "occupancy": "GhostOcc", "mount": "GhostMount"}[kind]))
            s.link(g)
    s.caption("orange = physics collision (frame)   yellow = occupancy hints (front/rear zones)\n"
              "green = mount-point hints (sides, bottom, rim, slot rails, slot floor / ceiling)", (-0.8, 0.9, 3.0), 0.055)
    s.render()


def vanilla_compare(built, paint="keen"):
    nm = "vanilla_comparison"
    if not want(nm):
        return
    s = Shot(nm, res=(2200, 1150), floor=(-6.5, 1.5, -2.0, 2.0))
    s.camera((-1.9, 7.0, 2.3), (-2.4, 0, 1.05), 32)
    s.inst(painted(built, FULL, 0, paint), T(0, 0, _H(FULL) / 2))
    s.inst(painted(built, HALF, 0, paint), T(-1.15, 0, _H(HALF) / 2))
    x = -2.2
    for rel, label, rot in (("Timer/50/Models/NonFractured/Timer50.fbx", "vanilla Timer50", 0),
                            ("Batteries/Battery/50/Models/NonFractured/Battery50.fbx", "vanilla Battery50", -90),
                            ("CargoContainers/CargoContainers/150/Models/NonFractured/CargoContainer150.fbx",
                             "vanilla CargoContainer150", 0)):
        c, lo, hi = vanilla(rel, paint)
        w = hi.x - lo.x
        ctr = (lo + hi) / 2
        m = T(x - w / 2, 0, 0) @ Rz(rot) @ T(-ctr.x, -ctr.y, -lo.z)
        s.inst(c, m)
        s.caption(label, (x - w / 2, 0.3, hi.z - lo.z + 0.25), 0.065)
        x -= w + 0.45
    s.caption("OURS: full rack 42 + half rack 24\n(Keen grey paint, Keen material roles)", (-0.55, 0.3, 2.85), 0.07)
    s.render()


def render_all(built):
    if FULL not in built or HALF not in built:
        print("previews need both open racks built; skipping")
        return
    PM.get("Caption")
    for name in (FULL, HALF):
        turntable(built, name)
    closeups(built)
    for name in (FULL, HALF):
        lods(built, name)
    scale(built)
    paints(built)
    slot_proof(built)
    collision_view(built)
    vanilla_compare(built)
