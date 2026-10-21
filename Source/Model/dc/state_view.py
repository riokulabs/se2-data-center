"""Build-stage and damage-state evaluation for the states preview harness (states_preview.py / states_sheet.py), the
vanilla analogues rendered beside our blocks, and the pre-4.0-damage baseline (Tests/golden/states_baseline.json).

Pure Python (no Blender): it reads the installed definitions (Assets/DataCenter/<name>/), the build outputs
(Source/Model/Models/<name>/export.json and FBX) and, read-only, tools/vanilla-ref.

What a shot shows (guide docs/guides/vanilla-damage-and-build-states.md §1, §2.1, §3.5):
  c00 .. c77    the Fractured model (FR) with the cumulative stage changes up to that ratio (part_state);
  done          the NonFractured model (NF), no changes;
  done_damaged  a finished block that took damage: FR with only the last stage's ApplyOnlyWhenDamaged changes, every
                zone intact (what Keen's hand-added scaffold hide is for);
  one_hit, battered, broken
                the same FR plus the per-zone states of damage_scenario: a damaged zone shows its Damaged-model (DM)
                parts in place of its FR parts, a dead zone is hidden.
"""
import hashlib
import json
import os
import re

from . import config
from .assetio import meta_id, own_guid, read_json

SHOTS = {"c00": 0.0, "c10": 0.1, "c20": 0.2, "c30": 0.3, "c53": 0.5333, "c77": 0.7667, "done": 1.0}
DAMAGE_SHOTS = ("done_damaged", "one_hit", "battered", "broken")
ALL_SHOTS = tuple(SHOTS) + DAMAGE_SHOTS
# A block without fracture zones (the unfractured rod hangers and Chute) has no damage scenario; its
# Damaged model (the dented debris) is shown whole in this extra panel
DEBRIS_SHOT = "debris"
VIEWS = ("front", "rear")
ZONE_STATES = ("intact", "damaged", "dead")

# family -> vanilla analogue block names (guide §4). Names, not paths: analogue_dir resolves each to its nested
# vanilla-ref folder.
ANALOGUE = {
    "rack": ("SlidingDoorNarrow250", "WallInsertPanel"),
    "server": ("Timer50", "Battery50"),
    "tray": ("CableStraight250",),
    "trayrods": ("CableStraight250",),
    "floor": ("CatwalkSquareBase250", "DeckPanel250"),
    "contain_roof": ("DeckPanel250", "WindowFlat250"),
    "contain_door": ("SlidingDoorNarrow250",),
    "crac": ("Gyroscope250",),
    "pdu_cabinet": ("CircuitBreaker",),
    "pdu_strip": ("CircuitBreaker",),
    "sign": ("LCDFlat50",),
}
BASELINE_KEYS = ("zones", "critical", "nf_parts", "fr_parts", "stages_sha1", "def_guids")
BASELINE_PATH = os.path.join(config.MOD_DIR, "Tests", "golden", "states_baseline.json")
VANILLA_BLOCKS = os.path.join(config.VANILLA_REF, "Blocks")

_ZONE = re.compile(r"^(Fracture_?\d+)")


# ---------------------------------------------------------------------------------------------------- stages
def part_state(stages, ratio, damaged=False):
    """{mesh part: (shown, material GUID | None = its skin)} for a block at build ratio `ratio`.

    ratio < 1: the cumulative changes of every stage with BuildRatioLowerBound <= ratio (QueryChanges accumulates from
    the last model swap, which is stage 0's FractureModel). ratio >= 1: the finished block has no changes ({}); when
    `damaged`, it renders FR with the last stage's ApplyOnlyWhenDamaged changes only (guide §2.1 / §3.5). A part a
    change never touched is shown in its skin and is absent from the result: read it as state.get(p, (True, None))."""
    st = {}
    if ratio >= 1:
        if not damaged or not stages:
            return st
        todo = [c["Value"] for c in stages[-1]["Value"]["PartChanges"]["_data"] if c["Value"]["ApplyOnlyWhenDamaged"]]
    else:
        todo = [c["Value"] for s in stages if s["Value"]["BuildRatioLowerBound"] <= ratio
                for c in s["Value"]["PartChanges"]["_data"] if damaged or not c["Value"]["ApplyOnlyWhenDamaged"]]
    for c in todo:
        shown, mat = st.get(c["MeshPart"], (True, None))
        if c["ShowPart"] is not None:
            shown = c["ShowPart"]
        if c["SetMaterial"]:
            mat = c["SetMaterial"]
        if c["ResetToSkinMaterial"]:
            mat = None
        st[c["MeshPart"]] = (shown, mat)
    return st


def stages_sha1(stages):
    """SHA-1 of the stage list (JSON, sorted keys) with the LAST stage's PartChanges emptied: the fracture pass replaces
    the stage-1.0 damaged-only hide (today the no-op "Chrome"), so that one list is recorded apart
    (last_stage_changes) and everything else (keys, ratios, models, every earlier change) stays under the hash."""
    s = json.loads(json.dumps(stages))
    if s:
        s[-1]["Value"]["PartChanges"] = {"_data": []}
    return hashlib.sha1(json.dumps(s, sort_keys=True).encode()).hexdigest()


def last_stage_changes(stages):
    return [c["Value"] for c in stages[-1]["Value"]["PartChanges"]["_data"]] if stages else []


def zone_of(group):
    """Zone id of an FR / DM object's Group: Fracture_01, Fracture_01_Hide, Fracture_01_Support -> Fracture_01
    (vanilla also spells Fracture14_Support); None for an ungrouped object (the scaffold) or another group."""
    m = _ZONE.match(group or "")
    return m.group(1) if m else None


def mesh_part(group, material):
    """The importer's mesh-part name: <Group>-<material>, or the bare material without a Group."""
    return f"{group}-{material}" if group else material


# ---------------------------------------------------------------------------------------------------- damage
def _size(z):
    return z.get("volume", z.get("health_share", 0.0))


def damage_scenario(fractured, kind):
    """{zone id: "intact" | "damaged" | "dead"} for a damage shot, from export.json's "fractured" (zones with id,
    volume, critical; or analogue_fractured's equivalent). Zones are ranked by volume (ties by id).
      done_damaged  every zone intact (the block is damaged, no zone yet: FR with the damaged-only changes);
      one_hit       the largest non-critical zone damaged (the largest zone when every zone is critical);
      battered      every zone damaged and the smallest non-critical zone dead (none dead when all are critical);
      broken        the largest critical zone dead, the rest intact; {} when the block has no critical zone.
    A block without zones (the unfractured rods and chute) gives {}."""
    zones = sorted(fractured.get("zones") or [], key=lambda z: (-_size(z), z["id"]))
    if kind not in DAMAGE_SHOTS:
        raise ValueError(f"not a damage shot: {kind}")
    if not zones:
        return {}
    crit = set(fractured.get("critical") or [])
    out = {z["id"]: "intact" for z in zones}
    soft = [z["id"] for z in zones if z["id"] not in crit]
    if kind == "one_hit":
        out[(soft or [zones[0]["id"]])[0]] = "damaged"
    elif kind == "battered":
        out = {k: "damaged" for k in out}
        if soft:
            out[soft[-1]] = "dead"
    elif kind == "broken":
        hard = [z["id"] for z in zones if z["id"] in crit]
        if not hard:
            return {}
        out[hard[0]] = "dead"
    return out


# ---------------------------------------------------------------------------------------------------- installed (ours)
def bmd_path(name, assets=None):
    d = os.path.join(assets or config.MOD_ASSETS, config.NAME, name)
    hits = sorted(f for f in os.listdir(d) if f.endswith("_BlockModelDefinition.partialdef"))
    if len(hits) != 1:
        raise FileNotFoundError(f"{name}: expected one *_BlockModelDefinition.partialdef in {d}, found {hits}")
    return os.path.join(d, hits[0])


def installed_bmd(name):
    """The installed BlockModelDefinition's Manipulator (Model, FractureModel, DamagedModel, Dummies, stages)."""
    return read_json(bmd_path(name))["$Value"]["Manipulator"]


def installed_stages(name):
    """BuildProgressModels of Assets/DataCenter/<name>/*_BlockModelDefinition.partialdef."""
    return installed_bmd(name)["BuildProgressModels"]


def dummies_of(manip):
    """The dummy values a (delta-encoded) Dummies list inserts or updates."""
    d = manip.get("Dummies") or {}
    if isinstance(d, list):
        return [x.get("Value", x) for x in d]
    return [c["Value"] for c in d.get("Changed", []) if c.get("Kind") in ("Insert", "Update") and c.get("Value")]


def installed_dummies(name):
    return dummies_of(installed_bmd(name))


def effect_dummies(dummies):
    """The dummies damage bands bind to: type ParticleEffects (e9f28118; dc.effects.PARTICLE_EFFECTS_TYPE)."""
    from .effects import PARTICLE_EFFECTS_TYPE
    return [d for d in dummies if d.get("Type") == PARTICLE_EFFECTS_TYPE]


def manifest(name, models_dir=None):
    return read_json(os.path.join(models_dir or config.MODELS_DIR, name, "export.json"))


def model_fbx(name, kind, models_dir=None):
    """LOD0 FBX of our block: kind nf | fr | dm (dm absent on the unfractured blocks: None)."""
    sub, suf = {"nf": ("NonFractured", ""), "fr": ("Fractured", "_Fractured"), "dm": ("Damaged", "_Damaged")}[kind]
    p = os.path.join(models_dir or config.MODELS_DIR, name, sub, f"{name}{suf}.fbx")
    return p if os.path.exists(p) else None


def fbx_parts(path):
    from .fracture_rules import fbx_meshes, mesh_parts
    return sorted(mesh_parts(fbx_meshes(path)))


SHARED_KEY = "shared_def_guids"   # the baseline's one non-block entry: GUIDs defined outside the block folders


def def_guids(name=None, assets=None, skip=()):
    """Sorted own GUIDs of every .def / .partialdef under Assets/DataCenter/<name>/ (Override partials define none);
    name None walks all of Assets/DataCenter, minus the top-level folders in `skip`."""
    root = os.path.join(assets or config.MOD_ASSETS, config.NAME, *([name] if name else []))
    out = set()
    for dp, ds, fs in os.walk(root):
        if dp == root:
            ds[:] = [d for d in ds if d not in skip]
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                g = own_guid(read_json(os.path.join(dp, f)))
                if g:
                    out.add(g)
    return sorted(out)


def shared_def_guids(assets=None):
    """The definitions outside every block folder (DataCenter_InitialUnlock, UI/*_BlockGroupDefinition, texts...)."""
    from . import catalog
    return def_guids(None, assets, skip={b.name for b in catalog.BLOCKS})


def baseline_record(name):
    """The identity a save binds to (zones, critical, NF mesh parts), the FR mesh parts, the stage hash (the last
    stage's PartChanges excluded, the last stage recorded apart) and every definition GUID."""
    fr = manifest(name)["fractured"]
    stages = installed_stages(name)
    last = stages[-1]["Value"]
    return {"zones": [z["id"] for z in fr.get("zones") or []], "critical": list(fr.get("critical") or []),
            "nf_parts": fbx_parts(model_fbx(name, "nf")), "fr_parts": fbx_parts(model_fbx(name, "fr")),
            "stages_sha1": stages_sha1(stages), "def_guids": def_guids(name),
            "last_stage": {"BuildRatioLowerBound": last["BuildRatioLowerBound"], "Model": last["Model"],
                           "PartChanges": last_stage_changes(stages)}}


def capture_src(dst):
    """Snapshot for a later "before" render: Source/Model/Models/ -> <dst>/<name>/..., and per block the installed
    stage list (<dst>/stages/<name>.json), BMD (<dst>/stages/<name>.bmd.json: dummies) and Damaged .model (beside
    its FBX, for the DM slot materials)."""
    import shutil
    from . import catalog
    os.makedirs(os.path.join(dst, "stages"), exist_ok=True)
    for b in catalog.BLOCKS:
        n = b.name
        out = os.path.join(dst, n)
        if os.path.isdir(out):
            shutil.rmtree(out)
        shutil.copytree(os.path.join(config.MODELS_DIR, n), out)
        manip = installed_bmd(n)
        for suffix, obj in ((".json", manip["BuildProgressModels"]), (".bmd.json", manip)):
            with open(os.path.join(dst, "stages", n + suffix), "w") as f:
                json.dump(obj, f, indent=1)
        dm = os.path.join(config.MOD_ASSETS, config.NAME, n, "Models", "Damaged", f"{n}_Damaged.model")
        if os.path.exists(dm) and os.path.isdir(os.path.join(out, "Damaged")):
            shutil.copy2(dm, os.path.join(out, "Damaged"))


def dm_slot_map(name, models_dir=None):
    """{DM slot name: material GUID} of our Damaged .model (the --src copy's when it has one, else the installed)."""
    for p in (os.path.join(models_dir or config.MODELS_DIR, name, "Damaged", f"{name}_Damaged.model"),
              os.path.join(config.MOD_ASSETS, config.NAME, name, "Models", "Damaged", f"{name}_Damaged.model")):
        if os.path.exists(p):
            return {a["MaterialName"]: a["MaterialReference"] for a in read_json(p)["$Value"]["MaterialAssignments"]}
    return {}


# ---------------------------------------------------------------------------------------------------- vanilla analogues
_DIRS = {}


def analogue_dir(name):
    """The vanilla-ref folder holding <name>_BlockModelDefinition.partialdef (e.g. Timer50 -> Blocks/Timer/50)."""
    if name not in _DIRS:
        want = f"{name}_BlockModelDefinition.partialdef"
        hits = [dp for dp, _, fs in os.walk(VANILLA_BLOCKS) if want in fs]
        if len(hits) != 1:
            raise FileNotFoundError(f"vanilla analogue {name}: {len(hits)} folders hold {want}")
        _DIRS[name] = hits[0]
    return _DIRS[name]


def analogue_bmd(name):
    return read_json(os.path.join(analogue_dir(name), f"{name}_BlockModelDefinition.partialdef"))["$Value"]["Manipulator"]


def analogue_stages(name):
    return analogue_bmd(name).get("BuildProgressModels") or []


def _by_meta(root, guid, ext):
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(ext) and meta_id(os.path.join(dp, f)) == guid:
                return os.path.join(dp, f)
    return None


def _model_lod0(model_path):
    """(LOD0 FBX path, Keen-frame translation) of a .model: its GeometryAsset whose FBX name has no _LOD."""
    v = read_json(model_path)["$Value"]
    d = os.path.dirname(model_path)
    ids = {meta_id(os.path.join(d, f)): os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".fbx")}
    for ga in v["GeometryAssets"]:
        p = ids.get(ga["AssetReference"][3:])
        if p and "_LOD" not in os.path.basename(p):
            t = ga["Transformations"]["Translation"]
            return p, (t["X"], t["Y"], t["Z"])
    return None


def analogue_models(name):
    """{"nf" | "fr" | "dm": (LOD0 FBX, translation) | None} of the models the analogue's BMD references."""
    bmd, d = analogue_bmd(name), analogue_dir(name)
    out = {}
    for k, key in (("nf", "Model"), ("fr", "FractureModel"), ("dm", "DamagedModel")):
        g = (bmd.get(key) or "")[3:]
        mp = _by_meta(d, g, ".model") if g else None
        out[k] = _model_lod0(mp) if mp else None
    return out


def analogue_collision(name):
    """The FR model's collision asset (a glTF, or None when it is missing or a Havok .hkt)."""
    g = (analogue_bmd(name).get("FractureModel") or "")[3:]
    mp = _by_meta(analogue_dir(name), g, ".model") if g else None
    ref = ((read_json(mp)["$Value"].get("CollisionShapesAsset") or {}).get("AssetReference") or "")[3:] if mp else ""
    d = os.path.dirname(mp) if mp else None
    hit = next((os.path.join(d, f) for f in os.listdir(d) if not f.endswith(".meta")
                and meta_id(os.path.join(d, f)) == ref), None) if ref else None
    return hit if hit and hit.endswith(".gltf") else None


def analogue_dm_slots(name):
    g = (analogue_bmd(name).get("DamagedModel") or "")[3:]
    mp = _by_meta(analogue_dir(name), g, ".model") if g else None
    return {a["MaterialName"]: a["MaterialReference"]
            for a in read_json(mp)["$Value"]["MaterialAssignments"]} if mp else {}


def analogue_fractured(name):
    """export.json-like {"zones": [{id, volume, critical}], "critical": [...]} of a vanilla block: zones from the FR
    LOD0 groups that have a fracture collider (Timer50's FR carries a stray Fracture_16 group with none), volume =
    the zone geometry's AABB; criticals from <name>_BreakableBlockDefinition.partialdef."""
    from .fracture_rules import fbx_meshes, fracture_colliders
    crit = []
    bbd = os.path.join(analogue_dir(name), f"{name}_BreakableBlockDefinition.partialdef")
    if os.path.exists(bbd):
        cf = read_json(bbd)["$Value"].get("Manipulator", {}).get("CriticalFractures") or {}
        crit = [x["Id"] for x in (cf.get("Added", []) if isinstance(cf, dict) else cf)]
    fr = analogue_models(name)["fr"]
    gl = analogue_collision(name)
    cols = set(fracture_colliders(gl)) if gl else None
    boxes = {}
    if fr:
        for m in fbx_meshes(fr[0]).values():
            z = zone_of(m["props"].get("Group"))
            if z and m["verts"] and (cols is None or z in cols):
                lo, hi = boxes.get(z, ([1e9] * 3, [-1e9] * 3))
                for v in m["verts"]:
                    lo = [min(a, b) for a, b in zip(lo, v)]
                    hi = [max(a, b) for a, b in zip(hi, v)]
                boxes[z] = (lo, hi)
    zones = [{"id": z, "critical": z in crit,
              "volume": round((hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]), 6)}
             for z, (lo, hi) in sorted(boxes.items())]
    return {"zones": zones, "critical": [c for c in crit if c in boxes]}
