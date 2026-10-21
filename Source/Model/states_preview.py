"""Build-state and damage-state renders of our blocks AS EXPORTED, each beside its vanilla analogue (dc/state_view.py).

    blender -b --python Source/Model/states_preview.py -- --set=<tag> [--src=<dir>] [--stages=<dir>] [--markers]
                                                           [--no-analogues | --analogues-only] [--manifest-only]
                                                           [BLOCK ...]
    python3 Source/Model/states_sheet.py --set=<tag> [--before=<tag>] [--by-family]

Output: preview/dmg-build/<tag>/<block>/<shot>_<view>.png (views front / rear: 3/4 from the block's front and from
behind), <block>/shots.json, and manifest.json = {block: [shot, ...]} of our blocks; the analogues (vanilla, read
only from tools/vanilla-ref) go to V_<name>/ and analogues.json. Default blocks: the whole catalogue.

  --src=<dir>     our models from a copy of Source/Model/Models (state_view.capture_src) instead of the live one;
  --stages=<dir>  stage lists from <dir>/<name>.json (and dummies from <dir>/<name>.bmd.json) instead of the
                  installed BlockModelDefinition;
  --markers       in the damage shots, an orange octahedron at every staged ParticleEffects-type (e9f28118) dummy,
                  with a pin up through the block's top so a dummy inside the block still reads (none for a dummy
                  whose SupportingFracture zone is dead).

Shots (state_view.ALL_SHOTS): c00 .. c77 render the Fractured LOD0 with the cumulative stage changes (hidden parts
removed, SetMaterial in the construction material by GUID, dc/preview_mats.BY_GUID); done the NonFractured LOD0;
done_damaged / one_hit / battered / broken the Fractured LOD0 with the damaged-only changes and the zone states of
state_view.damage_scenario (damaged zone: its Damaged-model parts in the DM's slot materials; dead zone: hidden, so
the neighbours' FracturedMaterial01 caps show). Nothing is exploded. Stand-ins (`_Subpart` slots) show in c* and in
every damage shot (done_damaged / one_hit / battered / broken) in their live zones: any health loss ends Functional
(EffectiveBuildProgress = BuildProgress x integrity < MinFunctionalBuildProgress 1.0: FunctionalBlockComponent.cs:728,
CubeBlockComponent.cs:4048-4054), so the game despawns the real subparts and shows the stand-ins (Plan 5 Task 12 fix
round 1; Task 8 assumed a damaged block stays Functional). Only `done` (the intact NF) has none. The camera is fitted to
the NonFractured model, so every shot of a block (and the same block in another set) is framed alike. A block
without fracture zones but with a Damaged model (the unfractured rod hangers and Chute, Plan 5 Task 7) also gets
the `debris` shot: its whole Damaged model (state_view.DEBRIS_SHOT).
"""
import glob
import json
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))

_src = open(os.path.join(HERE, "p2t9c_preview.py")).read()
_src = _src[:_src.rindex("\nmain(")]                    # the renderer without its own entry point
R = {"__file__": os.path.join(HERE, "p2t9c_preview.py"), "__name__": "p2t9c_preview"}
exec(compile(_src, R["__file__"], "exec"), R)            # noqa: S102 (our own module, read from the checkout)
R["RES"] = (640, 480)

from dc import catalog, config, fracture as FR, state_view as SV  # noqa: E402
from dc import preview_mats as PM  # noqa: E402

OUT_ROOT = os.path.join(config.PREVIEW_DIR, "dmg-build")
SAMPLES = 24
FRONT, REAR = (-0.72, 0.62, 0.42), (0.72, -0.62, 0.42)
HIGH = {"floor", "contain_roof"}            # flat blocks: seen from higher up
MARK_COL = (1.0, 0.42, 0.02)


# ---------------------------------------------------------------------------------------------------- parts
class Part:
    """One single-material piece of an imported model: its mesh part name, zone, slot material name."""

    def __init__(self, ob, group, slot, name=""):
        self.ob, self.group, self.slot = ob, group, slot
        # (some vanilla Deformed objects carry no Group property: Battery50's skins; their name still says the zone)
        self.zone = SV.zone_of(group) or SV.zone_of(name)
        self.part = SV.mesh_part(group, slot)
        self.standin = slot.lower().endswith("_subpart")


def split(objs):
    """Every imported mesh object split per material slot (a mesh part is <Group>-<material>: one slot each)."""
    out = []
    for o in objs:
        group = o.get("Group") or o.get("group") or None
        used = sorted({p.material_index for p in o.data.polygons})
        for i in used:
            if i >= len(o.material_slots) or not o.material_slots[i].material:
                continue
            slot = R["slot"](o.material_slots[i].material)
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != i], context="FACES")
            for f in bm.faces:
                f.material_index = 0
            me = bpy.data.meshes.new(f"{o.name}_{slot}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(o.material_slots[i].material)
            ob = bpy.data.objects.new(me.name, me)
            ob.matrix_world = o.matrix_world.copy()
            out.append(Part(ob, group, slot, o.name))
        me = o.data
        bpy.data.objects.remove(o)
        if not me.users:
            bpy.data.meshes.remove(me)
    return out


def put(sc, part, mat):
    c = part.ob.copy()
    c.material_slots[0].link = "OBJECT"
    c.material_slots[0].material = mat
    sc.collection.objects.link(c)
    return c


def real(part, damaged=False, dm_slots=None):
    """The game material stand-in of a part (damaged: the Damaged model's slot material by GUID, else the slot swap
    vanilla Deformed models make, fracture.DAMAGED_SLOTS)."""
    n = part.slot
    if n.startswith("FracturedMaterial"):
        return R["frac_mat"]()
    if damaged:
        g = (dm_slots or {}).get(n)
        if g and g in PM.BY_GUID:
            return PM.get(g)
        if n in FR.DAMAGED_SLOTS:
            t = FR.DAMAGED_SLOTS[n]
            return PM.get(PM.keen_key(t)) if t.startswith("WindowGlassBroken") else R["broken_mat"](t)
    return PM.get(PM.keen_key(n))


# ---------------------------------------------------------------------------------------------------- subjects
class Subject:
    """Everything a block's shots need: parts of NF / FR / DM LOD0, stages, zones, dummies, model translation."""

    def __init__(self, key, family, nf, fr, dm, stages, fractured, dummies, shift, dm_slots, info=None):
        self.key, self.family = key, family
        self.nf, self.fr, self.dm = split(R["load"](nf)), split(R["load"](fr)) if fr else [], \
            split(R["load"](dm)) if dm else []
        self.stages, self.fractured, self.dummies, self.shift, self.dm_slots = \
            stages, fractured, dummies, shift, dm_slots
        self.info = info or {}


def ours(name, src, stages_dir):
    models = src or config.MODELS_DIR
    man = SV.manifest(name, models)
    stages, bmd = None, None
    if stages_dir:
        stages = json.load(open(os.path.join(stages_dir, name + ".json")))
        p = os.path.join(stages_dir, name + ".bmd.json")
        bmd = json.load(open(p)) if os.path.exists(p) else None
    stages = stages if stages is not None else SV.installed_stages(name)
    dummies = SV.dummies_of(bmd) if bmd else SV.installed_dummies(name)
    return Subject(name, catalog.BY_NAME[name].family, SV.model_fbx(name, "nf", models),
                   SV.model_fbx(name, "fr", models), SV.model_fbx(name, "dm", models), stages, man["fractured"],
                   dummies, tuple(man["shift"]), SV.dm_slot_map(name, models),
                   {"fr_lod0_tris": (man["fractured"].get("lods") or [{}])[0].get("tris"),
                    "role_tris": dict(man["fractured"].get("role_tris") or {},
                                      scaffold=((man["fractured"].get("scaffold") or {}).get("tris") or {}).get("0", 0))})


def vanilla(name, family):
    m = SV.analogue_models(name)
    fr = m["fr"] or m["nf"]
    return Subject("V_" + name, family, m["nf"][0], fr[0], (m["dm"] or (None,))[0], SV.analogue_stages(name),
                   SV.analogue_fractured(name), SV.dummies_of(SV.analogue_bmd(name)), fr[1],
                   SV.analogue_dm_slots(name))


# ---------------------------------------------------------------------------------------------------- shots
def to_blender(subj, pos):
    """Keen model frame (Y up, translation = the .model's) -> the imported FBX's Blender frame (Z up)."""
    x, y, z = (pos["X"] - subj.shift[0], pos["Y"] - subj.shift[1], pos["Z"] - subj.shift[2])
    return Vector((x, -z, y))


def marker_mat():
    m = bpy.data.materials.get("pvs_marker")
    return m or PM.simple("pvs_marker", MARK_COL, 0.4, 0.0, emit=MARK_COL, estr=4.0)


def markers(sc, subj, zst, lo, hi):
    size = max(0.012, 0.035 * max(hi - lo))
    for d in SV.effect_dummies(subj.dummies):
        z = (d.get("SupportingFracture") or {}).get("Id")
        if z and zst.get(z) == "dead":
            continue
        p = to_blender(subj, d["Transform"]["Transform"]["Position"])
        top = Vector((p.x, p.y, hi.z + 2.5 * size))
        bm = bmesh.new()
        for c, s in ((p, size), (top, size * 0.8)):
            vs = [bm.verts.new(c + Vector(v) * s) for v in
                  ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
            for a in (0, 1):
                for b in (2, 3):
                    for e in (4, 5):
                        bm.faces.new((vs[a], vs[b], vs[e]))
        r = size * 0.12
        q = [bm.verts.new(c + Vector((dx, dy, 0))) for c in (p, top) for dx, dy in ((r, 0), (0, r), (-r, 0), (0, -r))]
        for i in range(4):
            bm.faces.new((q[i], q[(i + 1) % 4], q[4 + (i + 1) % 4], q[4 + i]))
        me = bpy.data.meshes.new("marker")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(marker_mat())
        sc.collection.objects.link(bpy.data.objects.new("marker", me))


def has_debris(subj):
    """An unfractured block with a Damaged model: its dented debris gets the extra DEBRIS_SHOT panel."""
    return bool(subj.dm) and not (subj.fractured or {}).get("zones") and not subj.key.startswith("V_")


def compose(sc, subj, shot, with_markers):
    """Link the parts a shot shows into scene sc."""
    if shot == SV.DEBRIS_SHOT:        # the whole Damaged model in its Deformed materials
        for p in subj.dm:
            put(sc, p, real(p, damaged=True, dm_slots=subj.dm_slots))
        return
    if shot == "done":
        for p in subj.nf:
            put(sc, p, real(p))
        return
    if shot in SV.SHOTS:
        st = SV.part_state(subj.stages, SV.SHOTS[shot])
        for p in subj.fr:
            shown, mat = st.get(p.part, (True, None))
            if shown:
                put(sc, p, PM.get(PM.key_for_guid(mat)) if mat else real(p))
        return
    zst = SV.damage_scenario(subj.fractured, shot) if shot != "done_damaged" else {}
    st = SV.part_state(subj.stages, 1.0, damaged=True)
    for p in subj.fr:       # (stand-ins included: a damaged block is never Functional, see the docstring)
        if zst.get(p.zone, "intact") != "intact":
            continue
        shown, mat = st.get(p.part, (True, None))
        if shown:
            put(sc, p, PM.get(PM.key_for_guid(mat)) if mat else real(p))
    for p in subj.dm:
        if zst.get(p.zone) != "damaged":
            continue
        if st.get(p.part, (True, None))[0]:
            put(sc, p, real(p, damaged=True, dm_slots=subj.dm_slots))
    if with_markers:
        lo, hi = R["bounds"]([p.ob for p in subj.nf])
        markers(sc, subj, zst, lo, hi)


def render(subj, out, with_markers):
    frame = [p.ob for p in subj.nf]
    views = {"front": FRONT, "rear": REAR}
    if subj.family in HIGH:
        views = {"front": (-0.55, 0.50, 0.80), "rear": (0.55, -0.50, 0.80)}
    done = []
    for shot in SV.ALL_SHOTS + ((SV.DEBRIS_SHOT,) if has_debris(subj) else ()):
        for view, direction in views.items():
            sc = R["new_scene"](f"{subj.key}_{shot}_{view}")
            sc.eevee.taa_render_samples = SAMPLES
            compose(sc, subj, shot, with_markers)
            R["shoot"](sc, frame, direction, os.path.join(out, subj.key, f"{shot}_{view}.png"))
            for o in list(sc.collection.objects):
                bpy.data.objects.remove(o)
            bpy.data.scenes.remove(sc)
        done.append(shot)
    with open(os.path.join(out, subj.key, "shots.json"), "w") as f:
        json.dump(done, f)
    with open(os.path.join(out, subj.key, "info.json"), "w") as f:   # the sheet's share column (export.json)
        json.dump(subj.info, f)
    for p in subj.nf + subj.fr + subj.dm:      # (materials and images stay: preview_mats caches them)
        me = p.ob.data
        bpy.data.objects.remove(p.ob)
        bpy.data.meshes.remove(me)
    for kind in (bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for d in [d for d in kind if not d.users]:
            kind.remove(d)


def write_manifests(out):
    """manifest.json (our blocks) and analogues.json (V_*) from every <block>/shots.json in the set."""
    man, ana = {}, {}
    for p in sorted(glob.glob(os.path.join(out, "*", "shots.json"))):
        k = os.path.basename(os.path.dirname(p))
        (ana if k.startswith("V_") else man)[k] = json.load(open(p))
    for fn, d in (("manifest.json", man), ("analogues.json", ana)):
        with open(os.path.join(out, fn), "w") as f:
            json.dump(d, f, indent=1, sort_keys=True)


def main(argv):
    opt = {a.split("=", 1)[0]: (a.split("=", 1) + [True])[1] for a in argv if a.startswith("--")}
    tag = opt.get("--set")
    if not tag or tag is True:
        sys.exit("states_preview: --set=<tag> is required")
    out = os.path.join(OUT_ROOT, tag)
    os.makedirs(out, exist_ok=True)
    if "--analogues-only" in opt:      # re-render only the analogues of the named (default: every) block's family
        names = [a for a in argv if not a.startswith("--")] or [b.name for b in catalog.BLOCKS]
        seen = {}
        for n in names:
            f = catalog.BY_NAME[n].family
            for a in SV.ANALOGUE[f]:
                seen.setdefault(a, f)
        for a, f in seen.items():
            render(vanilla(a, f), out, "--markers" in opt)
    elif "--manifest-only" not in opt:
        names = [a for a in argv if not a.startswith("--")] or [b.name for b in catalog.BLOCKS]
        src, stages = opt.get("--src"), opt.get("--stages")
        for n in names:
            render(ours(n, src, stages), out, "--markers" in opt)
        if "--no-analogues" not in opt:
            fams = []
            for n in names:
                f = catalog.BY_NAME[n].family
                for a in SV.ANALOGUE[f]:
                    if a not in [x for x, _ in fams]:
                        fams.append((a, f))
            for a, f in fams:
                render(vanilla(a, f), out, "--markers" in opt)
    write_manifests(out)


main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
