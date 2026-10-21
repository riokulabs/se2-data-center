"""Fracture comparison previews: the refined fracture and damaged models AS EXPORTED, against earlier exports (the
"before" files,
extracted read-only from git HEAD into a scratch folder) and vanilla's (tools/vanilla-ref, imported read-only).

    blender -b --python Source/Model/fracture_compare_preview.py -- --before=<dir> [SHOT ...]   (default: every shot)
    python3 Source/Model/fracture_compare_sheet.py                                               family sheets + contact sheet

<dir>/<name>/{Fractured,Damaged}/<name>_{Fractured,Damaged}[_collision.gltf/.bin].fbx: HEAD's LOD0 files.
Per subject, panels (preview/fracture-compare/panels/<subject>_<panel>.png), same camera direction:
  intact         the NonFractured LOD0, as built;
  before_zones   the earlier Fractured LOD0 exploded along its zones, each zone's skin in its colour, break faces in
                 vanilla FracturedMaterial01, and each zone's COLLIDER as a wire cage in the zone's colour;
  zones          the same for the refined model (shaped colliders, the racks cut and capped, 3-zone servers);
  broken         the refined explosion in the game materials (what a player sees once zones have broken off);
  damaged        the refined Damaged LOD0 whole (vanilla "Deformed"), lamp / screen slots in
                 the broken materials the Damaged .model maps them to.
Vanilla subjects get intact / zones / broken / damaged from their NonFractured / Fractured / Deformed FBX (no cage:
several ship Havok .hkt colliders); their construction scaffold is hidden.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))

from dc import config, fracture as FR  # noqa: E402
from dc import preview_mats as PM  # noqa: E402

OUT = os.path.join(config.PREVIEW_DIR, "fracture-compare", "panels")
BEFORE = None   # --before=<dir>
VREF = os.path.join(config.VANILLA_REF, "Blocks")
SDK_MATS = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/GameData/"
                              "Vanilla/Assets/BlockMaterials")
ZONE_COL = [(0.08, 0.30, 0.95), (0.10, 0.62, 0.22), (0.55, 0.18, 0.80), (0.95, 0.62, 0.06), (0.9, 0.2, 0.2),
            (0.08, 0.72, 0.78), (0.88, 0.38, 0.62), (0.62, 0.62, 0.12), (0.5, 0.5, 0.5)]
RES = (1000, 760)

# subject -> (FBX: nonfractured, fractured, damaged | None = ours), camera direction (Blender frame), explode factor
SERVER_DIR, TRAY_DIR, RACK_DIR = (-0.88, 0.55, 0.42), (-0.62, -0.62, 0.62), (-0.75, 0.62, 0.38)
SUBJECTS = {
    "DC_Rack42_Open": (None, RACK_DIR, 0.16), "DC_Rack24_SplitFront": (None, RACK_DIR, 0.18),
    "DC_Srv_Compute": (None, SERVER_DIR, 0.22), "DC_Srv_Timer": (None, SERVER_DIR, 0.22),
    "DC_Srv_KVM": (None, SERVER_DIR, 0.22), "DC_Srv_UPS": (None, SERVER_DIR, 0.22),
    "DC_Tray_StraightL_Moderate": (None, TRAY_DIR, 0.22), "DC_Tray_TurnH_Full": (None, TRAY_DIR, 0.25),
    "DC_Tray_TurnUp_Low": (None, (-0.2, -0.95, 0.35), 0.25), "DC_Tray_Cross_Full": (None, TRAY_DIR, 0.22),
    "DC_Tray_Drop_Full": (None, (-0.5, -0.8, 0.40), 0.22),
    "Vanilla_SlideDoorNarrow250": (("Doors/SlideDoorNarrow/250/Models/NonFractured/NarrowSlidingDoor.fbx",
                                    "Doors/SlideDoorNarrow/250/Models/Fractured/NarrowSlidingDoor_Fractured.fbx",
                                    "Doors/SlideDoorNarrow/250/Models/Deformed/NarrowSlidingDoor_Deformed.fbx"),
                                   (-0.75, -0.62, 0.38), 0.14),
    "Vanilla_Battery150": (("Batteries/Battery/150/Models/NonFractured/Battery150.fbx",
                            "Batteries/Battery/150/Models/Fractured/Battery150_Fractured.fbx",
                            "Batteries/Battery/150/Models/Deformed/Battery150_Deformed.fbx"), (-0.85, 0.55, 0.42), 0.22),
    "Vanilla_WallInsertPipes": (("Walls/Inserts/Pipes/Models/NonFractured/WallInsertPipes.fbx",
                                 "Walls/Inserts/Pipes/Models/Fractured/WallInsertPipes_Fractured.fbx",
                                 "Walls/Inserts/Pipes/Models/Deformed/WallInsertPipes_Deformed.fbx"),
                                (-0.62, -0.62, 0.55), 0.20),
}


# ---------------------------------------------------------------------------------------------------- materials
def _tex_mat(name, png, rough=0.8, metal=0.1, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if os.path.exists(png):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(png, check_existing=True)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (2.5, 2.5, 2.5)   # vanilla's cut density is ~0.4 UV/m: show the grain
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    else:
        print("NO TEXTURE", png)
        b.inputs["Base Color"].default_value = (0.2, 0.15, 0.12, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def frac_mat():
    return _tex_mat("pv9c_frac", os.path.join(SDK_MATS, "FracturedMaterial01", "FracturedMaterial01_albedo.png"))


BROKEN_TEX = {"EmissiveOffBroken": ("EmissiveOffBroken", "EmissiveOffBroken_albedo.png"),
              "Display01Broken": ("Display01Broken", "Display01Broken_albedo.png")}


def broken_mat(target):
    if target in BROKEN_TEX:
        d, f = BROKEN_TEX[target]
        return _tex_mat("pv9c_" + target, os.path.join(SDK_MATS, d, f), 0.6, 0.2)
    return PM.get("EmOff")


def zone_mat(k):
    c = ZONE_COL[k % len(ZONE_COL)]
    return PM.simple(f"pv9c_zone{k}", c, 0.45, 0.15)


def slot(m):
    return (m.name if m else "").split(".")[0]


def apply_real(o, damaged=False):
    for i, s in enumerate(o.material_slots):
        n = slot(s.material)
        if n.startswith("FracturedMaterial"):
            o.material_slots[i].material = frac_mat()
        elif damaged and n in FR.DAMAGED_SLOTS:
            o.material_slots[i].material = broken_mat(FR.DAMAGED_SLOTS[n])
        elif s.material:
            o.material_slots[i].material = PM.get(PM.keen_key(n))


# ---------------------------------------------------------------------------------------------------- sources
def load(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
    return [o for o in new if o.type == "MESH"]


def info(o):
    """(zone index or None, kind) of an exported object: kind skin | hide | cut | support | scaffold."""
    g = o.get("Group") or o.get("group") or ""
    t, p = o.get("ConstructionMeshType", ""), o.get("ConstructionMeshPreset", "")
    z = None
    if g.startswith("Fracture"):
        digits = "".join(ch for ch in g[len("Fracture"):].lstrip("_").split("_")[0] if ch.isdigit())
        z = int(digits) - 1 if digits else None
    if t == "Scaffold" or p == "Scaffolding":
        return z, "scaffold"
    if p == "Fracture" or all(slot(m).startswith("Fractured") for m in o.data.materials if m):
        return z, "cut"
    if g.endswith("_Hide") or o.get("ConstructionMeshVisibility") == "AlwaysHidden":
        return z, "hide"
    if g.endswith("_Support"):
        return z, "support"
    return z, "skin"


def sources(name, before=False):
    spec = SUBJECTS[name][0]
    if spec is None:
        d = os.path.join(BEFORE if before else config.MODELS_DIR, name)
        dm = os.path.join(d, "Damaged", f"{name}_Damaged.fbx")
        return (os.path.join(config.MODELS_DIR, name, "NonFractured", f"{name}.fbx"),
                os.path.join(d, "Fractured", f"{name}_Fractured.fbx"), dm if os.path.exists(dm) else None,
                os.path.join(d, "Fractured", f"{name}_Fractured_collision.gltf"))
    return tuple(os.path.join(VREF, p) for p in spec) + (None,)


def cages(gltf):
    """{zone index: wire-cage object} of a collision glTF's Fracture_NN colliders (dc/fracture_rules.gltf_hulls)."""
    import bmesh
    from dc import fracture_rules as FRR
    out = {}
    for nm, vs in FRR.gltf_hulls(gltf).items():
        if not nm.startswith("Fracture"):
            continue
        z = int("".join(ch for ch in nm if ch.isdigit())) - 1
        bm = bmesh.new()
        for v in vs:
            bm.verts.new(v)
        bmesh.ops.convex_hull(bm, input=list(bm.verts))
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=5e-4)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=5e-4)
        me = bpy.data.meshes.new("cage_" + nm)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new("cage_" + nm, me)
        w = o.modifiers.new("w", "WIREFRAME")
        w.thickness = 0.004
        w.use_replace = True
        w.use_even_offset = False      # (even offset spikes out at a hull's sharp, thin corners)
        o.data.materials.append(cage_mat(z))
        out[z] = o
    return out


def cage_mat(k):
    m = bpy.data.materials.get(f"pv9c_cage{k}")
    if m:
        return m
    c = ZONE_COL[k % len(ZONE_COL)]
    m = PM.simple(f"pv9c_cage{k}", tuple(min(1.0, 0.35 + v) for v in c), 0.3, 0.0)
    try:
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (*c, 1)
        b.inputs["Emission Strength"].default_value = 2.5
    except Exception:
        pass
    return m


# ---------------------------------------------------------------------------------------------------- scene
def bounds(objs, m=None):
    pts = [(m or Matrix()) @ o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def new_scene(tag):
    sc = bpy.data.scenes.new("s9c_" + tag)
    r = sc.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y = RES
    r.film_transparent = False
    for k, v in (("taa_render_samples", 64), ("use_raytracing", True), ("use_shadows", True)):
        try:
            setattr(sc.eevee, k, v)
        except Exception:
            pass
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Base Contrast"
    except Exception:
        pass
    w = bpy.data.worlds.new("w9c_" + tag)
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.36, 0.37, 0.39, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc.world = w
    return sc


def shoot(sc, objs, direction, path, lens=60):
    lo, hi = bounds(objs)
    tgt = (lo + hi) / 2
    size = (hi - lo).length
    d = Vector(direction).normalized()
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = lens
    cam.data.clip_start, cam.data.clip_end = 0.01, 100
    sc.collection.objects.link(cam)
    sc.camera = cam
    dist = size * 1.5
    from bpy_extras.object_utils import world_to_camera_view
    for _ in range(6):    # fit: the bounds fill ~80 % of the frame
        cam.location = tgt + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        sc.view_layers[0].update()
        cs = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        p = [world_to_camera_view(sc, cam, c) for c in cs]
        span = max(max(q.x for q in p) - min(q.x for q in p), max(q.y for q in p) - min(q.y for q in p))
        dist *= span / 0.80
    right = d.cross(Vector((0, 0, 1))).normalized()
    for nm, off, e, col in (("key", -1.0 * right + 0.5 * d + Vector((0, 0, 1.0)), 260, (1.0, 0.97, 0.93)),
                            ("fill", 1.2 * right + 0.9 * d + Vector((0, 0, 0.2)), 70, (0.9, 0.94, 1.0)),
                            ("rim", -1.2 * d + 0.3 * right + Vector((0, 0, 0.8)), 200, (0.85, 0.9, 1.0))):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.energy, ld.size, ld.color = e * size * size, 1.6 * size, col
        lo_ = bpy.data.objects.new(nm, ld)
        lo_.location = tgt + off * 1.8 * size
        lo_.rotation_euler = (tgt - lo_.location).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(lo_)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    print("WROTE", path)


def place(sc, objs, m=Matrix()):
    out = []
    for o in objs:
        c = o.copy()
        c.data = o.data.copy()
        c.matrix_world = m @ o.matrix_world
        sc.collection.objects.link(c)
        out.append(c)
    return out


def explode_offsets(objs, k):
    """{zone: offset}: each zone moves away from the model centre along (its skin centre - model centre)."""
    lo, hi = bounds(objs)
    c = (lo + hi) / 2
    size = max(hi - lo)
    zc = {}
    for o in objs:
        z, kind = info(o)
        if z is not None and kind in ("skin", "support"):
            zc.setdefault(z, []).append(o)
    out = {}
    for z, os_ in zc.items():
        a, b = bounds(os_)
        d = (a + b) / 2 - c
        out[z] = d.normalized() * k * size if d.length > 0.08 * size else Vector((0, 0, 0))   # a middle zone stays
    return out


def exploded(name, fr, gl, k, direction, panel, cage=True):
    off = explode_offsets(fr, k)
    sc = new_scene(f"{name}_{panel}")
    objs = []
    for o in fr:
        z, kind = info(o)
        if panel != "broken" and kind == "hide":
            continue
        c = place(sc, [o], Matrix.Translation(off.get(z, Vector())))[0]
        if panel != "broken" and kind != "cut":
            for i in range(len(c.material_slots)):
                c.material_slots[i].material = zone_mat(z if z is not None else 8)
        else:
            apply_real(c)
        objs.append(c)
    if cage and gl and os.path.exists(gl):
        for z, o in cages(gl).items():
            o.matrix_world = Matrix.Translation(off.get(z, Vector()))
            sc.collection.objects.link(o)
    shoot(sc, objs, direction, os.path.join(OUT, f"{name}_{panel}.png"))


def subject(name):
    nf_p, fr_p, dm_p, gl = sources(name)
    _, direction, k = SUBJECTS[name]
    nf, fr = load(nf_p), [o for o in load(fr_p) if info(o)[1] != "scaffold"]
    sc = new_scene(name + "_intact")
    objs = place(sc, nf)
    for o in objs:
        apply_real(o)
    shoot(sc, objs, direction, os.path.join(OUT, f"{name}_intact.png"))
    exploded(name, fr, gl, k, direction, "zones")
    exploded(name, fr, gl, k, direction, "broken", cage=False)
    if SUBJECTS[name][0] is None and BEFORE:
        _, bfr_p, _, bgl = sources(name, before=True)
        bfr = [o for o in load(bfr_p) if info(o)[1] != "scaffold"]
        exploded(name, bfr, bgl, k, direction, "before_zones")
    if dm_p:
        dm = [o for o in load(dm_p) if info(o)[1] != "scaffold"]
        sc = new_scene(name + "_damaged")
        objs = place(sc, dm)
        for o in objs:
            apply_real(o, damaged=True)
        shoot(sc, objs, direction, os.path.join(OUT, f"{name}_damaged.png"))


def main(argv):
    global BEFORE
    for a in argv:
        if a.startswith("--before="):
            BEFORE = a.split("=", 1)[1]
    names = [a for a in argv if not a.startswith("--")]
    if not names:                     # the whole set: start clean (no panel of a subject no longer rendered)
        names = list(SUBJECTS)
        if os.path.isdir(OUT):
            for f in os.listdir(OUT):
                if f.endswith(".png"):
                    os.remove(os.path.join(OUT, f))
    for n in names:
        subject(n)


main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
