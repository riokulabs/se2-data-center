"""The integration package (no Blender): everything needed to install the models into the cloned blocks, staged
under integration/Assets/DataCenter/ exactly as it must land in mods/DataCenter/Assets/DataCenter/.

Nothing here writes to the mod's Assets/ or Content/. integration/install.sh copies the staged files (dry run by
default). Asset GUIDs are created once and kept in asset_guids.json, so rebuilding never changes a reference.
Adapted from an earlier prototype's integration module.

Inputs: the clones (dc/clone.py: Assets/DataCenter/<name>/ and the keyed .clonemap.json), build_report.json and
the exports (Models/<name>/export.json + files, written by build_dc.py --export). Per catalogue block:
  * every block: the BlockKind's Name and Description and the block definition's UIData.Name (dc/names.py);
  * built blocks (a placement entry in build_report.json AND an export) also get:
      Models/NonFractured/  LOD FBX + collision glTF/bin + <name>.model
      Models/Fractured/     LOD FBX + collision glTF/bin + <name>_Fractured.model
      Models/Damaged/       (servers and trays) LOD FBX + collision + <name>_Damaged.model, whose lamp and
                            screen slots map to vanilla's broken materials (fracture.DAMAGED_SLOTS)
      the patched <name>_BlockModelDefinition.partialdef: Model, FractureModel, DamagedModel (the Damaged model; the
      racks' Fractured one), Dummies (ParticleEffects at the block centre) and generated BuildProgressModels;
      UIData.Icon when Source/Model/UI/<name>_Icon.png exists;
      an entry in DataCenter_InitialUnlock.partialdef (Override of ProgressionInitialUnlockConfiguration).
      fractured blocks (>= 2 zones: every rack, server and tray) are breakable (ensure_breakable: the component
      the hotfix removed is restored, bound to the block's BreakableBlockDefinition with its CriticalFractures; the
      KVM gets a new one); an unfractured block (the 4 exceptions of fracture.UNFRACTURED) is made non-breakable (make_non_breakable:
      the BreakableBlockComponent Removed from the cloned compositions and prefabs, as vanilla Non-Breakable).
  * built functional servers (dc/functional.py) also get, keeping every composition and component as cloned:
      the interaction dummy (Terminal / LcdPanel, vanilla name, type and highlight section kept) moved onto our face;
      the cloned indicator definition's ReplacementModels pointed at our models (its states, materials and
      IndicatorMeshParts unchanged: our lamp slots carry those mesh-part names);
      the status display's LCD surface (MeshPartName kept) set to our 2:1 screen (1024 x 512, AspectRatio 2);
      mount directions without Forward (the working face never takes a block) and without
      Up (SERVER_MOUNTS; the deco servers get the same);
  * the built UPS (dc/functional.py UPS_*) also gets, keeping Battery50's components:
      two Power Cell slots: the cloned server composition gets a second InventoryComponent (the cloned Battery50
      InventoryDefinition, so the same Power Cell whitelist and 25 kg per slot) tagged "CellSlot 1", and the server
      prefab a second slot pre-filled like slot 0 (vanilla Battery250 pattern);
      per-slot dummies "CellSlot N" (slot render) + "CellAction N" (UseBatterySlotCells: aim + use) on each bay;
      the ResourceContainerInventory with MaxCapacity = slots x the Power Cell's MaxStored and doubled rates;
      mount directions Left, Right, Down (front and back are working faces: the two cell bays; no Up: SERVER_MOUNTS).
  * the built KVM (dc/subparts.py) also gets, keeping every ControlPanel25 component (terminal access):
      the subpart models (Models/Subparts/<sub>/: FBX per LOD + a .model without collision) and, under Subparts/,
      a DummyType per subpart, a ModelComponentDefinition per subpart (the drawer's carries the "KvmScreen" hinge
      dummy), a TranslationAnimation (drawer) and a RotationAnimation (screen) definition, a composite per subpart
      (Copy of vanilla Subpart_Composite + its rigid animation component), the drawer prefab (Copy of vanilla Subpart,
      the screen nested as a child entity at the hinge) and the block's ConditionalSubPartsDefinition
      (KvmDrawer dummy type -> drawer prefab; MeshPartsToHideWhenActive = the closed drawer and lid baked into the
      Fractured / Damaged models, standin_parts);
      the "KvmDrawer" dummy in the BlockModelDefinition, the Terminal dummy onto our face;
      ConditionalSubPartsComponent + FunctionalBlockAnimationControllerComponent (definition null) in the cloned client
      composition, with a null object builder for each in the client prefab (the earlier prototype's pattern).
  * the built Programmable becomes a functional blade in data:
      the KVM's On/Off chain (onto_powerable), ControlPanel25's Terminal dummy over its management module, vanilla
      InGameScriptingComponent + our InGameScriptingDefinition on the server side (dc/scripting.py) and an
      empty BlockMaterialSwapper on the client side (filled by the scripts). build_integration.py then generates the
      scripts' DcGuids.g.cs from this staging (dc/script_guids.py).
"""
import json
import os
import shutil

from . import catalog, clone, config, construction, doors, fracture, functional, menu, names, recipes, script_guids
from . import rack_side, scripting, subparts, texts
from . import dims as DM
from . import effects
from .effects import PARTICLE_EFFECTS_TYPE   # the one ParticleEffects dummy type constant (dc/effects.py)
from .assetio import B_GAME, B_VRAGE, PARTIAL, body, envelope, meta_id, own_guid, read_json, write_json, write_meta
from .guids import Guids
from .material_guids import guid as mat_guid

STAGE = os.path.join(config.STAGE_ASSETS, config.NAME)
UI_DIR = os.path.join(config.HERE, "UI")
INITIAL_UNLOCK = "c7b8e669-e76b-4edb-aa18-8067d0340b96"
UNLOCK_FILE = f"{config.NAME}/{config.NAME}_InitialUnlock.partialdef"
MODEL_TYPE = "VRage:Keen.VRage.ContentPipeline.Models.ModelAssetData"


_STAGED = set()   # rel paths stage_def wrote in this write_all run


def read_mod(rel):
    """The installed (mod) copy. A definition already staged in this run must be read with read_current, or the
    later stage_def would silently drop this run's earlier patch."""
    if rel in _STAGED:
        raise RuntimeError(f"{rel}: already staged in this run; read it with read_current, not read_mod")
    return read_json(os.path.join(config.MOD_ASSETS, rel))


def stage_path(rel):
    return os.path.join(config.STAGE_ASSETS, rel)


def stage_meta(rel, asset_id):
    """Stage <rel>.meta unless the mod already has one with this AssetID (the installed .meta keeps the builder's
    hashes and processor info, so a reinstall doesn't rewrite it); a different installed AssetID is an error."""
    have = meta_id(os.path.join(config.MOD_ASSETS, rel))
    if have == asset_id:
        return
    if have:
        raise RuntimeError(f"{rel}: installed .meta AssetID {have} != {asset_id}")
    write_meta(stage_path(rel), asset_id)


def asset_id(rel):
    """AssetID of a staged-or-installed asset (staged .meta first)."""
    return meta_id(stage_path(rel)) or meta_id(os.path.join(config.MOD_ASSETS, rel))


# "Bundle:Type" names resolve through the file's own $Bundles (MigrationsHelper.TryGetType throws "There is no bundle
# named X" otherwise: VRage.Library/Keen.VRage.Library.Serialization.Migrations.Internal/MigrationsHelper.cs:126-147).
# A patch that brings a bundle's first type into a file (a Game2 object builder in a structural prefab) declares it at
# the version our values are written against: the current one, so no migration rewrites them.
TYPE_FIELDS = ("$Type", "Type", "UseActionType")
BUNDLE_VERSIONS = {"Game2": B_GAME["Game2"], "VRage": B_GAME["VRage"]}


def type_bundles(x, out=None):
    """The bundle prefixes of every "Bundle:Type" name in x ($Type / Type / UseActionType values, nested)."""
    out = set() if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            if k in TYPE_FIELDS and isinstance(v, str) and ":" in v:
                out.add(v.split(":", 1)[0])
            type_bundles(v, out)
    elif isinstance(x, list):
        for v in x:
            type_bundles(v, out)
    return out


def declare_bundles(data):
    """Add every bundle data's type names use to its $Bundles (the ones already declared keep their version)."""
    bundles = data.setdefault("$Bundles", {})
    for b in sorted(type_bundles(data) - set(bundles)):
        if b not in BUNDLE_VERSIONS:
            raise RuntimeError(f"type bundle {b!r} has no known version")
        bundles[b] = BUNDLE_VERSIONS[b]
    data["$Bundles"] = dict(sorted(bundles.items()))


def stage_def(rel, data):
    """A patched definition, staged with a .meta whose AssetID is its own GUID (and must equal the mod's), its
    $Bundles declaring every bundle its type names use."""
    declare_bundles(data)
    g = own_guid(data)
    have = meta_id(os.path.join(config.MOD_ASSETS, rel))
    if g and have and have != g:
        raise RuntimeError(f"{rel}: mod .meta AssetID {have} != definition GUID {g}")
    write_json(stage_path(rel), data)
    _STAGED.add(rel)
    stage_meta(rel, g or have)


def stage_file(src, rel, G):
    dst = stage_path(rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    stage_meta(rel, G[rel])
    return G[rel]


def model_asset(geom, collision_guid, shift, remap=None):
    """geom: [(fbx asset guid, used materials)] in LOD order. LOD0 carries the per-axis grid-align translation
    (vanilla: SnapToGrid false, the shift written explicitly). remap: slot -> material slot for the Damaged model
    (fracture.damaged_slot: the slot keeps its name, it maps to the broken / Deformed material, as vanilla's Deformed;
    a stand-in's `<Mat>_Subpart` slot to its base's), or None."""
    remap = remap or (lambda m: m)
    names_ = sorted({m for _, mats in geom for m in mats})
    ga = []
    for i, (g, mats) in enumerate(geom):
        t = shift if i == 0 else [0, 0, 0]
        ga.append({"AssetReference": "{G}" + g, "UsedMaterials": mats,
                   "Transformations": {"Translation": {"X": t[0], "Y": t[1], "Z": t[2]},
                                       "Rotation": {"X": 0, "Y": 0, "Z": 0}, "Scale": 1}})
    return envelope(MODEL_TYPE, {
        "MaterialAssignments": [{"MaterialName": m, "MaterialReference": mat_guid(remap(m))} for m in names_],
        "MaterialStateOverrides": [], "GeometryAssets": ga, "SnapToGrid": False, "SuggestedModelSize": None,
        "CollisionShapesAsset": {"AssetReference": "{G}" + collision_guid, "GroupsByFracture": [],
                                 "GeneratePreciseCollider": True}})


def manifest(spec):
    p = os.path.join(config.MODELS_DIR, spec.name, "export.json")
    return read_json(p) if os.path.exists(p) else None


def built_names(report=None):
    if report is None:
        report = read_json(config.REPORT_PATH) if os.path.exists(config.REPORT_PATH) else {"blocks": {}}
    pipeline = {b.name for b in catalog.STAGED}   # built catalogue blocks outside the staged families (room blocks
    #                                               not yet wired) are in the report but not staged
    return {n for n, e in report["blocks"].items() if e.get("placement", {}).get("total") and n in pipeline}


def stage_models(spec, man, G):
    """Copy the exported files, write the .model assets. Returns {variant: .model guid}."""
    out = {}
    variants = [("NonFractured", "nonfractured", spec.name), ("Fractured", "fractured", f"{spec.name}_Fractured")]
    if man.get("damaged"):          # the dented Damaged model (vanilla "Deformed")
        variants.append(("Damaged", "damaged", f"{spec.name}_Damaged"))
    for variant, key, stem in variants:
        src = os.path.join(config.MODELS_DIR, spec.name, variant)
        rel = f"{config.NAME}/{spec.name}/Models/{variant}"
        geom = [(stage_file(os.path.join(src, l["file"]), f"{rel}/{l['file']}", G), l["materials"])
                for l in man[key]["lods"]]
        c = man[key]["collision"]
        col = stage_file(os.path.join(src, c["file"]), f"{rel}/{c['file']}", G)
        stage_file(os.path.join(src, c["bin"]), f"{rel}/{c['bin']}", G)
        mrel = f"{rel}/{stem}.model"
        write_json(stage_path(mrel), model_asset(geom, col, man["shift"],
                                                      fracture.damaged_slot if key == "damaged" else None))
        stage_meta(mrel, G[mrel])
        out[variant] = G[mrel]
    return out


def patch_model_def(spec, info, man, models, G=None):
    """The cloned BlockModelDefinition with our models, the centred effects dummy and generated build stages."""
    bmd = read_mod(info["model_def_file"])
    m = body(bmd)
    model_ref, frac_ref = "{G}" + models["NonFractured"], "{G}" + models["Fractured"]
    dmg_ref = "{G}" + models["Damaged"] if "Damaged" in models else frac_ref   # racks: no dents yet
    m["Model"], m["FractureModel"], m["DamagedModel"] = model_ref, frac_ref, dmg_ref
    sx, sy, sz = man["shift"]
    dummies = m.get("Dummies") or {}
    ours = functional.DUMMIES.get(spec.name, {})
    sign_d = sign_dummies(spec) if spec.family == "sign" else {}     # the LcdPanel over the screen
    found = set()
    if spec.variant == "UPS":
        patch_ups_dummies(spec, dummies, G, man["fractured"].get("supporting", {}))
    if spec.variant == "KVM":
        patch_kvm_dummies(spec, dummies, G, man["fractured"])
    if spec.variant == "Programmable":
        patch_programmable_dummies(spec, dummies, G)
    if spec.family == "rack" and doors.has_doors(spec):
        patch_door_dummies(spec, dummies, G)
    if spec.family == "rack" and spec.name in _DOOR_CTX and config.RACK_PATH == "A":
        patch_rack_subpart_dummies(spec, dummies, G)
    if spec.family == "contain_door":
        patch_contain_door_dummies(spec, dummies, G, man["fractured"].get("supporting", {}))
    if spec.family == "crac":
        patch_crac_dummies(spec, dummies, G, man["fractured"].get("supporting", {}))
    if spec.family in ("trayrods", "floor", "contain_roof"):   # clones without a ParticleEffects dummy
        dummies = patch_effects_dummy(spec, dummies, G)
        items = [(k, v) for k, v in m.items() if k != "Dummies"]
        m.clear()
        for k, v in items:                   # (keep vanilla's member order: the Dummies follow the Model)
            m[k] = v
            if k == "Model":
                m["Dummies"] = dummies
    for ch in dummies.get("Changed", []):
        v = ch.get("Value") or {}
        if v.get("Name") == "ParticleEffects" or (not v.get("Name") and v.get("Type") == CONSTRUCTION_PARTICLES):
            # damage / destruction (ParticleEffects) and construction-stage (Battery50's unnamed
            # ConstructionStagesParticles) effects origin: the block centre
            v["Transform"]["Transform"]["Position"] = {"X": sx, "Y": sy, "Z": sz}
        elif v.get("Name") in ours:              # interaction dummy (functional servers): onto our face, facing out
            (a, b, d), scale = ours[v["Name"]]
            x, y, z = functional.face_to_game(a, b, d)
            v["Transform"]["Transform"]["Position"] = {"X": x, "Y": y, "Z": z}
            v["Transform"]["Transform"]["Orientation"] = {"X": 0, "Y": 0, "Z": 0, "W": 1}
            v["Transform"]["EulerHint"] = {"X": 0, "Y": 0, "Z": 0}
            v["Scale"] = {"X": scale[0], "Y": scale[1], "Z": scale[2]}
            # the face's terminal / LCD dies with the zone holding it (the front service
            # module), as vanilla binds its terminals to their plates (Battery150 TerminalRight -> Fracture_02)
            zid = man["fractured"].get("supporting", {}).get(v["Name"])
            v["SupportingFracture"] = {"Id": zid} if zid else None
            found.add(v["Name"])
        elif v.get("Name") in sign_d:
            pos, scale = sign_d[v["Name"]]
            v["Transform"]["Transform"]["Position"] = {"X": pos[0], "Y": pos[1], "Z": pos[2]}
            v["Transform"]["Transform"]["Orientation"] = {"X": 0, "Y": 0, "Z": 0, "W": 1}
            v["Transform"]["EulerHint"] = {"X": 0, "Y": 0, "Z": 0}
            v["Scale"] = {"X": scale[0], "Y": scale[1], "Z": scale[2]}
            zid = man["fractured"].get("supporting", {}).get(v["Name"])    # the zone holding the screen's centre
            v["SupportingFracture"] = {"Id": zid} if zid else None
            found.add(v["Name"])
    patch_spark_dummies(spec, dummies, man, G)   # after the center dummy is placed
    if set(ours) - found or set(sign_d) - found:
        raise RuntimeError(f"{spec.name}: cloned model definition lacks dummies "
                           f"{sorted((set(ours) | set(sign_d)) - found)}")
    parts = {k: tuple(v) for k, v in man["fractured"]["parts"].items()}
    stages = construction.generate_stages(parts, model_ref, frac_ref, seed=f"datacenter/{spec.name}",
                                          damaged_hide=construction.scaffold_parts(parts))
    m["BuildProgressModels"] = stages
    stage_def(info["model_def_file"], bmd)
    return stages


def _block_files(spec, pattern):
    """Cloned definition files of a block whose name contains pattern (mod-relative paths, no .meta)."""
    root = os.path.join(config.MOD_ASSETS, config.NAME, spec.name)
    return sorted(os.path.relpath(os.path.join(dp, f), config.MOD_ASSETS) for dp, _, fs in os.walk(root) for f in fs
                  if pattern in f and f.endswith((".def", ".partialdef")))


def patch_indicator(spec, models, man=None):
    """Point the cloned indicator definition's ReplacementModels at our models (the indicator recolours only the
    models it lists; the clone still lists the vanilla block's). States and materials stay vanilla; the mesh parts
    keep vanilla's and gain our Fractured model's lamp parts the vanilla list lacks (a 6U server's third
    zone: Fracture_03_Hide-<lamp slot>, which vanilla Timer50's two zones never name)."""
    files = _block_files(spec, "IndicatorDefinition")
    if len(files) != 1:
        raise RuntimeError(f"{spec.name}: expected one cloned indicator definition, found {files}")
    d = read_mod(files[0])
    v = body(d)
    # vanilla lists all three (Timer50: NonFractured, Fractured, Deformed): the lamps keep their state when damaged
    refs = ["{G}" + models[k] for k in ("NonFractured", "Fractured", "Damaged") if k in models]
    if isinstance(v.get("ReplacementModels"), dict):     # a Copy partialdef: delta list on an empty template list
        v["ReplacementModels"] = {"$DeltaEncoded": True, "Removed": [], "Added": refs}
    else:
        v["ReplacementModels"] = refs
    stage_def(files[0], d)
    parts = v["IndicatorMeshParts"]
    parts = parts["Added"] if isinstance(parts, dict) else parts
    if man:
        plain = {p for p in parts if "-" not in p}
        extra = sorted(p for p in man["fractured"]["parts"] if "-" in p and p.split("-", 1)[1] in plain
                       and p not in parts)
        parts.extend(extra)
        stage_def(files[0], d)
    return {"file": files[0], "replacement_models": refs, "mesh_parts": parts}


def patch_lcd(spec, surfaces, G=None):
    """The cloned LcdMultiPanel definition's surfaces (vanilla LCDFlat50 / LCDNarrow50 clone: one inserted surface).
    surfaces: [dict] of the fields to set per surface (MeshPartName, Resolution, AspectRatio, and optionally
    DefaultDisplayName), in order; every surface keeps the cloned one's DefaultScreenMaterial and UseOnlineTexture.
    The first keeps the cloned delta key; each further one (the hanging sign's back face) is a new
    Insert with its own stable key (G "lcdsurface/<name>/<i>"). The status server keeps its call with one
    surface: the same MeshPartName (LCDScreen_Off), our 2:1 screen's resolution / aspect."""
    import copy
    files = _block_files(spec, "LcdMultiPanelDefinition")
    if len(files) != 1:
        raise RuntimeError(f"{spec.name}: expected one LcdMultiPanelDefinition, found {files}")
    d = read_current(files[0])
    sv = body(d)["Surfaces"]
    tmpl = copy.deepcopy(sv["Changed"][0]["Value"])
    if len(surfaces) > 1 and G is None:
        raise RuntimeError(f"{spec.name}: a second LCD surface needs the asset GUIDs (G)")
    keys, changed = [sv["Keys"][0]], []
    for i, f in enumerate(surfaces):
        v = copy.deepcopy(tmpl)
        v.update(copy.deepcopy(f))
        changed.append({"Kind": "Insert", "Index": i, "Value": v})
        if i:
            keys.append(G[f"lcdsurface/{spec.name}/{i}"])
    sv["Keys"], sv["Changed"] = keys, changed
    stage_def(files[0], d)
    return {"file": files[0], "surfaces": [c["Value"] for c in changed], "keys": keys,
            "mesh_part": changed[0]["Value"]["MeshPartName"],
            **{k: changed[0]["Value"][k] for k in ("Resolution", "AspectRatio")}}


# No server mounts on its TOP (Up). A rack slot's mounts are keyed to its rear
# row (dc/rack.py collision()), so a server one cell too far forward touches none of the rack's; its only other way
# in was its bottom (Down) on the top (Up) of a correctly seated server below, which overlaps on two of three rows.
# With Up gone the wrong depth fails placement everywhere. Cost: nothing builds onto a server's lid (no stacking
# servers outside a rack); a server still sits on a floor (Down), backs onto a wall and takes side neighbours.
SERVER_MOUNTS = "Backward, Left, Right, Down"   # every server (deco: was the cloned wall panel's, with Up)
UPS_MOUNTS = "Left, Right, Down"                # the UPS: cell bays on the front AND the back
# the racks mount in all six directions. The open rack's cloned wall panel says "Backward, Left, Right,
# Up, Down" (no Forward: the front containment rail could not mount); the door racks' template
# (DoorsPowerableBlockDefinition) already resolves to All, and the patch states it explicitly for both. The model's
# mount hints decide WHERE (the front / back planes mount only on the containment rail band).
RACK_MOUNTS = "All"
CONSTRUCTION_PARTICLES = "82c73d56-c77f-4ba7-a0a5-7f1438dd576b"   # System/DummyTypes/ConstructionStagesParticles
INVENTORY_COMPONENT = "Game2:Keen.Game2.Simulation.WorldObjects.Items.InventoryComponent"
BATTERY50 = os.path.join(config.VANILLA_REF, "Blocks", "Batteries", "Battery", "50")


def patch_effects_dummy(spec, dummies, G):
    """The rod hangers' cloned model definition (StructuralSupportStraight's) changes no dummies, so it has no
    "ParticleEffects" dummy (damage / destruction effects origin) as every other block does: add one (the vanilla
    Pipes insert's), the effects-origin loop then puts it at the block centre. Idempotent (a stable delta key)."""
    dummies = dict(dummies or {})
    dummies.setdefault("$DeltaEncoded", True)
    keys, changed = dummies.setdefault("Keys", []), dummies.setdefault("Changed", [])
    dummies.setdefault("Removed", [])
    if any((c.get("Value") or {}).get("Name") == "ParticleEffects" for c in changed):
        return dummies
    v = _dummy("ParticleEffects", PARTICLE_EFFECTS_TYPE, (0, 0, 0), (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))
    v["HighlightSection"] = None
    keys.append(G[f"dummy/{spec.name}/ParticleEffects"])
    changed.append({"Kind": "Insert", "Index": len(keys) - 1, "Value": v})
    return dummies


def _dummy(name, typ, pos, q, e, scale):
    return {"Name": name,
            "Transform": {"Transform": {"Position": dict(zip("XYZ", pos)), "Orientation": dict(zip("XYZW", q))},
                          "EulerHint": dict(zip("XYZ", e))},
            "Scale": dict(zip("XYZ", scale)), "Type": typ, "SupportingFracture": None}


def patch_ups_dummies(spec, dummies, G, supporting=None):
    """The UPS's dummies: one CellSlot + CellAction pair per bay (functional.ups_dummies), each supported by its
    bay's fracture (export.json "supporting": Fracture_01 the front bay, Fracture_02 the rear one), as vanilla
    Battery50 supports its CellSlot / CellAction by Fracture_01; one "ParticleEffects <i>" per
    bay, supported like that bay's "CellSlot <i>" (the damage bands' sparks / smoke / fire stop with the bay's zone);
    every other cloned dummy kept (the unnamed ConstructionStagesParticles). Idempotent: existing entries keep their
    delta keys, new ones get stable keys from asset_guids.json."""
    supporting = supporting or {}
    keys, changed = dummies.get("Keys", []), dummies.get("Changed", [])
    assert all(c["Kind"] == "Insert" for c in changed) and len(keys) == len(changed), dummies
    by_name = {c["Value"].get("Name"): (k, c["Value"]) for k, c in zip(keys, sorted(changed, key=lambda c: c["Index"]))}
    out = []
    for name, typ, pos, q, e, sc in functional.ups_dummies():
        k = by_name.pop(name, (None, None))[0] or G[f"dummy/{spec.name}/{name}"]
        v = _dummy(name, typ, pos, q, e, sc)
        zid = supporting.get(name.replace("ParticleEffects ", "CellSlot ")) if name.startswith("ParticleEffects ") \
            else supporting.get(name)
        if zid:
            v["SupportingFracture"] = {"Id": zid}
        out.append((k, v))
    for name, (k, v) in by_name.items():
        if name and (name.startswith("CellSlot") or name.startswith("CellAction")):
            continue   # a vanilla slot dummy we did not re-place (none expected)
        out.append((k, v))
    dummies["Keys"] = [k for k, _ in out]
    dummies["Changed"] = [{"Kind": "Insert", "Index": i, "Value": v} for i, (_, v) in enumerate(out)]
    dummies["Removed"] = []


# ------------------------------------------------------------------------------------------------ KVM subparts
SUBPART_COMPOSITE_BASE = "1297bc6b-92aa-430a-b702-195393d7f84e"   # Templates/Blocks/Subparts/Subpart_Composite
SUBPART_PREFAB_BASE = "107bcdfc-f977-4486-b14a-6acb61fe0f03"      # Templates/Blocks/Subparts/Subpart
# the template's component keys, in order: Hierarchy, ChildTransform, Model, ModelRender, ParentRenderAdapter
SUBPART_TEMPLATE_KEYS = ["27f10314-65ac-44ab-89ca-e8f300bf1130", "abdad87f-d02b-4a66-9c71-7fa16e764efb",
                         "970c6c3c-a8e1-4e0a-be76-5acc73782323", "270d533d-96ee-476e-af5e-510ecf1568c9",
                         "5f721af6-ecb8-4aaf-a1fc-6b89e2a99bb1"]
T_CONDSUB = "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Effects.ConditionalSubPartsComponent"
T_ANIMCTL = "Game2:Keen.Game2.Simulation.GameSystems.RigidAnimations.FunctionalBlockAnimationControllerComponent"
RIGID = "VRage:Keen.VRage.Core.Game.GameSystems.RigidAnimations."
IDENTITY = {"X": 0, "Y": 0, "Z": 0, "W": 1}


def _xyz(v):
    return dict(zip("XYZ", v))


def _put_dummy(spec, dummies, G, v):
    """Insert dummy v (or replace the one of its name, keeping its delta key and list position). Idempotent: a new
    entry's delta key is stable (asset_guids.json)."""
    keys, changed = dummies.setdefault("Keys", []), dummies.setdefault("Changed", [])
    dummies.setdefault("Removed", [])
    for c in changed:
        if c["Value"].get("Name") == v["Name"]:
            c["Value"] = v
            return
    keys.append(G[f"dummy/{spec.name}/{v['Name']}"])
    changed.append({"Kind": "Insert", "Index": len(keys) - 1, "Value": v})


def patch_kvm_dummies(spec, dummies, G, fractured=None):
    """The KVM's own dummies, after the cloned ControlPanel25 ones (Terminal, ParticleEffects; patch_model_def places
    the Terminal and the toggle on the face from functional.DUMMIES):
      KvmDrawer  the drawer pivot (= the stowed hinge), identity orientation, of the drawer's own DummyType;
      KvmToggle  the vanilla UsePowerable use box over the drawer band (functional.KVM_TOGGLE),
                 LAST, so it wins a tie with the Terminal (InteractorEntityComponent.cs:83). Its SupportingFracture is
                 the fracture zone that holds the box (fracture.Plan.zone_at over the manifest's zones: the FRONT
                 service module, Fracture_02 on the 3-zone servers; not the critical core), as vanilla
                 supports its ButtonTop01 boxes (GravityGenerator500 / Reactor250) and as the face's Terminal is
                 supported (patch_model_def, the manifest's "supporting"): the use box dies with the face it sits on.
    fractured: the export manifest's "fractured" (its zones); None or no zones (a non-breakable build): no support,
    as the validator requires (BreakableBlockModelValidator.cs:90-98)."""
    v = _dummy(subparts.DRAWER, G[f"dummytype/{spec.name}/{subparts.DRAWER}"], subparts.drawer_dummy_game(),
               (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))
    v["HighlightSection"] = None
    _put_dummy(spec, dummies, G, v)
    (a, b, d), scale = functional.DUMMIES[spec.name][functional.KVM_TOGGLE]
    t = _dummy(functional.KVM_TOGGLE, functional.USE_POWERABLE_TYPE, functional.face_to_game(a, b, d), (0, 0, 0, 1),
               (0, 0, 0), scale)
    zones = (fractured or {}).get("zones") or []
    if len(zones) > 1:
        zone = fracture.Plan.zone_at(zones, (-a, functional.FRONT_Y + d, b))
        t["SupportingFracture"] = {"Id": zone}
    t["HighlightSection"] = None                 # vanilla's UsePowerable boxes name none: the whole block highlights
    _put_dummy(spec, dummies, G, t)


def subpart_model_asset(geom, collision_guid=None):
    """A subpart .model: LODs with no translation (the FBX origin is the pivot) and NO collision (vanilla subparts:
    visual only; ConditionalSubParts would otherwise add the collider to the block's static collision), except a door
    leaf's (collision_guid: its own collision glTF, as vanilla NarrowSlidingDoor_LeftDoor.model's .hkt:
    the DoorBlockCollider compounds it while the door is closed)."""
    names_ = sorted({m for _, mats in geom for m in mats})
    ga = [{"AssetReference": "{G}" + g, "UsedMaterials": mats,
           "Transformations": {"Translation": {"X": 0, "Y": 0, "Z": 0}, "Rotation": {"X": 0, "Y": 0, "Z": 0},
                               "Scale": 1}} for g, mats in geom]
    return envelope(MODEL_TYPE, {
        "MaterialAssignments": [{"MaterialName": m, "MaterialReference": mat_guid(m)} for m in names_],
        "MaterialStateOverrides": [], "GeometryAssets": ga, "SnapToGrid": False, "SuggestedModelSize": None,
        "CollisionShapesAsset": ({"AssetReference": None, "GroupsByFracture": []} if not collision_guid else
                                 {"AssetReference": "{G}" + collision_guid, "GroupsByFracture": [],
                                  "GeneratePreciseCollider": True})})


def _partial(base, manip, dtype, bundles=B_VRAGE):
    return envelope(PARTIAL, {"BaseDefinition": base, "PartialDefinitionKind": "Copy", "Manipulator": manip,
                              "DefinitionType": dtype, "PriorityOverride": False}, bundles)


def _child_transform(pos, yaw=0.0):
    """A child's transform: position (game frame) and an optional turn about game +Y (degrees; vanilla writes the
    quaternion plus the Euler hint in degrees, e.g. Y = 180)."""
    q = dict(IDENTITY) if not yaw else dict(zip("XYZW", doors.quat_yaw(yaw)))
    return {"$Type": "VRage:Keen.VRage.Core.Game.Components.ChildTransformComponentObjectBuilder",
            "TransformWithEulerHint": {"Transform": {"Position": _xyz(pos), "Orientation": q},
                                       "EulerHint": {"X": 0, "Y": yaw, "Z": 0}}}


def standin_parts(man):
    """The Fractured LOD0's baked stand-in mesh parts (`<Group>-<Mat>_Subpart`), sorted: the block's
    ConditionalSubParts MeshPartsToHideWhenActive (hidden while the real subparts are spawned, i.e. Functional)."""
    return sorted(p for p in man["fractured"].get("parts", {}) if p.endswith(fracture.SUBPART_SUFFIX))


def hide_when_active(spec, man, G):
    """ConditionalSubParts MeshPartsToHideWhenActive in vanilla's form (Reactor250: [{"Key": guid, "Value": mesh
    part}], a keyed list; a bare string list fails the SDK's project load): the block's stand-ins, each keyed by a
    stable GUID (asset_guids.json "hide/<block>/<part>")."""
    return [{"Key": G[f"hide/{spec.name}/{p}"], "Value": p} for p in standin_parts(man)]


def stage_kvm_subparts(spec, man, G):
    """Stage the KVM's drawer and screen (see the module docstring). Returns a summary with every GUID."""
    out = {"models": {}, "animations": {}, "composites": {}}
    base = f"{config.NAME}/{spec.name}"
    sub_rel = f"{base}/Subparts"
    anim = {subparts.DRAWER: ("Translation", {"Speed": round(subparts.DRAWER_SPEED, 6),
                                              "Translation": {"X": 0, "Y": 0, "Z": -subparts.TRAVEL}}),
            subparts.SCREEN: ("Rotation", {"RotationAxis": {"X": 1, "Y": 0, "Z": 0},
                                           "AngularSpeed": round(subparts.SCREEN_SPEED, 6),
                                           "RotationAngle": subparts.FOLD_DEG})}
    for sub in (subparts.DRAWER, subparts.SCREEN):
        info = man["subparts"][sub]
        src = os.path.join(config.MODELS_DIR, spec.name, info["dir"])
        rel = f"{base}/Models/Subparts/{sub}"
        geom = [(stage_file(os.path.join(src, l["file"]), f"{rel}/{l['file']}", G), l["materials"])
                for l in info["lods"]]
        mrel = f"{rel}/{spec.name}_{sub}.model"
        write_json(stage_path(mrel), subpart_model_asset(geom))
        stage_meta(mrel, G[mrel])
        # dummy type (the drawer's spawns the prefab; the screen's marks the hinge on the drawer model)
        dt = G[f"dummytype/{spec.name}/{sub}"]
        stage_def(f"{sub_rel}/{spec.name}_{sub}_DummyTypeDefinition.def",
                  envelope("VRage:Keen.VRage.Core.Model.DummyTypeDefinitionObjectBuilder", {"Guid": dt}))
        # model component (the drawer's carries the hinge dummy "KvmScreen")
        dums = []
        if sub == subparts.DRAWER:
            hv = _dummy(subparts.SCREEN, G[f"dummytype/{spec.name}/{subparts.SCREEN}"], subparts.SCREEN_LOCAL,
                        (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))
            hv["HighlightSection"] = None
            dums = {"$DeltaEncoded": True, "Keys": [G[f"dummy/{spec.name}/{sub}/{subparts.SCREEN}"]],
                    "Changed": [{"Kind": "Insert", "Index": 0, "Value": hv}], "Removed": []}
        mc = G[f"def/{spec.name}/{sub}/ModelComponent"]
        stage_def(f"{sub_rel}/{spec.name}_{sub}_ModelComponentDefinition.def",
                  envelope("VRage:Keen.VRage.Game.Components.Models.ModelComponentDefinitionObjectBuilder",
                           {"Guid": mc, "Model": "{G}" + G[mrel], "Dummies": dums,
                            "SubpartColliderOffset": {"X": 0, "Y": 0, "Z": 0}}))
        # rigid animation definition
        kind, val = anim[sub]
        an = G[f"def/{spec.name}/{sub}/Animation"]
        stage_def(f"{sub_rel}/{spec.name}_{sub}_{kind}AnimationDefinition.def",
                  envelope(f"{RIGID}{kind}AnimationDefinitionObjectBuilder", dict({"Guid": an}, **val)))
        # composite: vanilla Subpart_Composite + the model + one rigid animation component (tag RigidAnimationComponent)
        rk = G[f"key/{spec.name}/{sub}/RigidAnimation"]
        comp = G[f"def/{spec.name}/{sub}/Composite"]
        stage_def(f"{sub_rel}/{spec.name}_{sub}_Composite.partialdef", _partial(SUBPART_COMPOSITE_BASE, {
            "Guid": comp,
            "TagSlots": {"$DeltaEncoded": True, "RemovedKeys": [],
                         "ModifiedKeys": [{"$Key": "RigidAnimationComponent", "$Value": rk}]},
            "Components": {"$DeltaEncoded": True, "Keys": SUBPART_TEMPLATE_KEYS + [rk],
                           "Changed": [{"Kind": "Update", "Index": 2, "Value": {"Definition": mc}},
                                       {"Kind": "Insert", "Index": 5,
                                        "Value": {"Definition": an, "Type": f"{RIGID}{kind}AnimationComponent"}}],
                           "Removed": []}}, "VRage:Keen.VRage.DCS.Definitions.EntityCompositeDefinition"))
        out["models"][sub] = {"model_rel": mrel, "model": G[mrel], "model_component": mc, "dummy_type": dt,
                              "lods": len(geom)}
        out["animations"][sub] = an
        out["composites"][sub] = comp
    # the drawer prefab, the screen nested as a child entity at the hinge (RocketTurret250Subpart / Gyroscope50 pattern)
    child = {"$ObjectId": 0, "Definition": out["composites"][subparts.SCREEN],
             "ObjectBuilders": [{"Key": SUBPART_TEMPLATE_KEYS[0], "Value": {
                                    "$Type": "VRage:Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder",
                                    "Children": []}},
                                {"Key": SUBPART_TEMPLATE_KEYS[1], "Value": _child_transform(subparts.SCREEN_LOCAL)}]
             + [{"Key": k, "Value": None} for k in SUBPART_TEMPLATE_KEYS[2:]]
             + [{"Key": G[f"key/{spec.name}/{subparts.SCREEN}/RigidAnimation"], "Value": None}],
             "DebugName": subparts.SCREEN}
    pf = G[f"def/{spec.name}/{subparts.DRAWER}/Prefab"]
    dk = G[f"key/{spec.name}/{subparts.DRAWER}/RigidAnimation"]
    stage_def(f"{sub_rel}/{spec.name}_{subparts.DRAWER}.partialdef", _partial(SUBPART_PREFAB_BASE, {
        "Guid": pf, "_entity": {"Definition": out["composites"][subparts.DRAWER], "ObjectBuilders": {
            "$DeltaEncoded": True, "Keys": SUBPART_TEMPLATE_KEYS + [dk],
            "Changed": [{"Kind": "Update", "Index": 0, "Value": {
                            "$Type": "VRage:Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder",
                            "Children": {"$DeltaEncoded": True,
                                         "Keys": [G[f"child/{spec.name}/{subparts.SCREEN}"]],
                                         "Changed": [{"Kind": "Insert", "Index": 0, "Value": child}],
                                         "Removed": []}}},
                        {"Kind": "Insert", "Index": 5, "Value": None}],
            "Removed": []}}}, "VRage:Keen.VRage.Core.Game.Definitions.PrefabDefinition"))
    out["prefab"] = pf
    # the block's conditional subparts: KvmDrawer dummy type -> the drawer prefab; MeshPartsToHideWhenActive: the
    # closed drawer and lid baked into the Fractured / Damaged models, so the bay shows them while
    # the KVM is not Functional (under construction, broken) and the spawned subparts replace them when it is
    cs = G[f"def/{spec.name}/ConditionalSubParts"]
    stage_def(f"{sub_rel}/{spec.name}_ConditionalSubPartsDefinition.def", envelope(
        "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Effects.ConditionalSubPartsDefinitionObjectBuilder",
        {"Guid": cs, "SubParts": {out["models"][subparts.DRAWER]["dummy_type"]: pf},
         "MeshPartsToHideWhenActive": hide_when_active(spec, man, G)}, B_GAME))
    out["conditional_subparts"] = cs
    # client composition + client prefab: ConditionalSubParts + the Working animation controller
    new = [(G[f"key/{spec.name}/condsub"], cs, T_CONDSUB, "ConditionalSubPartsComponent"),
           (G[f"key/{spec.name}/animctl"], None, T_ANIMCTL, "FunctionalBlockAnimationControllerComponent")]
    cc_file = _block_files(spec, "_ClientComposition")[0]
    cc = read_mod(cc_file)
    cm = body(cc)
    keys = cm["Components"]["Keys"]
    for k, d, t, slot in new:
        if k not in keys:
            keys.append(k)
            cm["Components"]["Changed"].append({"Kind": "Insert", "Index": len(keys) - 1,
                                                "Value": {"Definition": d, "Type": t}})
        else:   # re-staging over an installed copy: keep the definition current
            for c in cm["Components"]["Changed"]:
                if c["Kind"] == "Insert" and c["Index"] == keys.index(k):
                    c["Value"] = {"Definition": d, "Type": t}
        mk = cm["TagSlots"]["ModifiedKeys"]
        if not any(m["$Key"] == slot for m in mk):
            mk.append({"$Key": slot, "$Value": k})
    stage_def(cc_file, cc)
    cl_file = _block_files(spec, "_Client.partialdef")[0]
    cl = read_mod(cl_file)
    ob = body(cl)["_entity"]["ObjectBuilders"]
    for k, *_ in new:
        if k not in ob["Keys"]:
            ob["Keys"].append(k)
            ob["Changed"].append({"Kind": "Insert", "Index": len(ob["Keys"]) - 1, "Value": None})
    stage_def(cl_file, cl)
    out["client_composition"] = cc_file
    out["client_prefab"] = cl_file
    return out


# ------------------------------------------------------------------------------------------------ KVM On/Off
# ControlPanel25 has a plain FunctionalBlockComponent (Working = Functional && grid on). The vanilla On/Off ("Enabled")
# state lives in PowerableBlockComponent (a FunctionalBlockComponent subclass: RecomputeWorking = base && Enabled &&
# Supplied; terminal toggle = PowerableBlockDetailModelServer, a [BlockDetailProvider] bound to any
# PowerableBlockComponent). Timer50 / EventController get it from Templates/BasePowerableBlockBreakable_*: component key
# 4f2bc5f9 (PowerableBlockComponent <- PowerableBlockDefinition), prefab object builder PowerableBlockObjectBuilder with
# "Enabled": true (vanilla blocks are built ON). With ConsumedResource null (vanilla ContractBlock250, Battery250,
# reactors) the block has no power sink and is always Supplied, so Working = Functional && grid on && Enabled.
FUNCTIONAL_KEY = "91e12dcf-837b-4bec-8269-cf48c52a1e1f"     # BaseFunctionalBlockBreakable: FunctionalBlockComponent
POWERABLE_KEY = "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727"      # BasePowerableBlockBreakable: PowerableBlockComponent
POWERABLE_DEF_BASE = "794c5233-6a1c-4932-b37c-03a0e539d069"  # Templates/Blocks/BaseDefinitions/PowerableBlockDefinition
T_POWERABLE = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.PowerableBlockComponent"
T_POWERABLE_DEF = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.PowerableBlockDefinition"
OB_POWERABLE = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.PowerableBlockObjectBuilder"
BASE_SLOTS_ON_FUNCTIONAL = ("GridBlockComponent", "MaxHealthComponent", "IBoundsProvider")


def _swap_component(delta, value, old=FUNCTIONAL_KEY):
    """In a delta-encoded key list: replace the old key by POWERABLE_KEY at the same position (old key Removed, new
    key Inserted with value). Idempotent on an already-swapped list (the Insert's value is refreshed)."""
    keys, changed, removed = delta["Keys"], delta["Changed"], delta.setdefault("Removed", [])
    if old in keys:
        i = keys.index(old)
        keys[i] = POWERABLE_KEY
        changed[:] = [c for c in changed if c["Index"] != i]
    i = keys.index(POWERABLE_KEY)
    changed[:] = [c for c in changed if c["Index"] != i] + [{"Kind": "Insert", "Index": i, "Value": value}]
    changed.sort(key=lambda c: c["Index"])
    if old not in removed:
        removed.append(old)
    removed.sort()   # set semantics; a fixed order keeps re-staging over any install history byte-identical


def _retarget_slots(comp, old=FUNCTIONAL_KEY):
    """Every tag slot on the old key points at POWERABLE_KEY, including the base template's slots the copy does not
    list (BASE_SLOTS_ON_FUNCTIONAL: the same three in the ControlPanel25 and the structural chains), except a
    NO_TERMINAL* slot, which is dropped."""
    ts = comp.setdefault("TagSlots", {"$DeltaEncoded": True, "RemovedKeys": [], "ModifiedKeys": []})
    mk = ts["ModifiedKeys"]
    for m in mk:
        if m["$Value"] == old:
            m["$Value"] = POWERABLE_KEY
    # The chain makes the block terminal-listed: drop ControlPanel25's NO_TERMINAL_FUNCTIONAL slot (any NO_TERMINAL*
    # tag on the FunctionalBlockComponent hides the block from the grid console, StreamedControlPanelSessionComponent
    # .IsBlockEligible, Game2.Simulation .../StreamedUI.Terminal.ControlPanel/StreamedControlPanelSessionComponent.cs:
    # 651-656). The base template (BaseFunctionalBlockBreakable _*Composition) has no such slot, so not listing it is
    # enough.
    mk[:] = [m for m in mk if not (m["$Key"].startswith("NO_TERMINAL") and m["$Value"] == POWERABLE_KEY)]
    have = {m["$Key"] for m in mk}
    for slot in BASE_SLOTS_ON_FUNCTIONAL:   # base-template slots that still point at the removed key
        if slot not in have:
            mk.append({"$Key": slot, "$Value": POWERABLE_KEY})


# ---------------------------------------------------------------------------------------------- non-breakable blocks
# BreakableBlockModelValidator (Game2.Simulation RuntimeSystems.Validators, a load-time error) needs every model of a
# composite with a BreakableBlockComponent to be a fractured collider (IBreakableCollider, ColliderCount > 1) or to
# have a FractureReplacementModels entry. A block with an unfractured model (no Fracture_NN colliders: the servers and
# trays before they got fracture plans; today only the justified exception: the three rod hangers
# and the Chute, fracture.UNFRACTURED) becomes non-breakable the way vanilla does it:
# Templates/Blocks/Non-Breakable/Structural_{Server,Client}Composition.def and ControlPanel25 / Sensor25 / Button25
# remove the component key and the five tag slots that point at it, and their prefabs list ObjectBuilders without it.
# ensure_breakable is the inverse, for a block whose model fractures again.
BREAKABLE_KEY = "bc5652a0-1296-4040-adc3-a2b9c35d5afc"   # BreakableBlockComponent in every Base*Breakable template
BREAKABLE_SLOTS = ("BreakableBlockComponent", "IIntegrityModifier", "IMountPointModifier", "PhysicsColliderProvider",
                   "IBlockPhysicsColliderProvider")
# The vanilla Breakable template prefabs our functional servers derive from carry ObjectBuilders that list the
# component (GameData/Vanilla/Content/Templates/Blocks/Breakable/<name>.def, 2.4.0.95). A clone prefab without its
# own ObjectBuilders inherits these keys; the strip writes them back without the component (Sensor25_Server pattern).
TEMPLATE_PREFAB_OB_KEYS = {
    "fbb99548-fbd3-447c-9821-238bc9d2316b": (   # Battery_Client
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "a1687822-b4c2-4bcb-961e-3e44fae3221d", "d358358e-30b3-484a-b8b8-2e5568c7298b",
        "bc5652a0-1296-4040-adc3-a2b9c35d5afc", "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727",
        "72e2ef60-d699-48a2-9959-4e246eecdacc", "24f8dfe2-6b3f-4764-a9db-6e4383dcae5d",
        "5c7bd857-3dd9-4f2c-86d0-7678709c8a8a", "480546a7-c048-4a07-b376-c0e2ab9b07ab",
        "f2f285a3-bcec-4093-ae3f-e22b40980aa5", "2fb312ca-49a7-443d-9d5a-6d8c9dea82f9",
        "273ebbf5-4c24-4e39-89b3-5e9791b47813",
    ),
    "f41b5ee5-b489-4a42-a81a-1bbb4ce9dd0e": (   # Battery_Server
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "d358358e-30b3-484a-b8b8-2e5568c7298b", "bc5652a0-1296-4040-adc3-a2b9c35d5afc",
        "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727", "340c1f18-066e-459a-8003-03e6311c867e",
        "d89d1e44-110f-45e7-a5b6-c2fec95861d9", "5fecc529-30f6-497c-8985-89391fdd4c45",
        "2e666e70-2382-4a56-a2d1-0842f41e220f", "a936783d-7a41-4244-8b1a-28698e215b96",
    ),
    "e1f824e7-892b-4598-8ba4-3ae65af9ae27": (   # EventController_Client
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "a1687822-b4c2-4bcb-961e-3e44fae3221d", "d358358e-30b3-484a-b8b8-2e5568c7298b",
        "bc5652a0-1296-4040-adc3-a2b9c35d5afc", "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727",
        "72e2ef60-d699-48a2-9959-4e246eecdacc", "24f8dfe2-6b3f-4764-a9db-6e4383dcae5d",
        "30a7eb7b-1873-479a-b7d8-fe5db6a0567e", "235a9ab4-3959-4d8b-aa28-a95a59b0e5ec",
        "6ec2c005-8ea0-4a2c-a376-10364eba2378", "7c315231-c610-4268-a0e7-35f8cc71c574",
    ),
    "967c1f01-a818-4c2c-b5ad-d353d0278c85": (   # EventController_Server
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "d358358e-30b3-484a-b8b8-2e5568c7298b", "bc5652a0-1296-4040-adc3-a2b9c35d5afc",
        "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727", "516f421a-5dab-4f8f-9f05-eecbd79240e7",
        "fc446c26-c18b-4105-b7a0-f1408f88b91e", "d2106c5b-fd13-4daf-ab86-79d7b313cdb0",
        "235a9ab4-3959-4d8b-aa28-a95a59b0e5ec", "7c315231-c610-4268-a0e7-35f8cc71c574",
    ),
    "66ed053f-e12d-4bfd-8a03-8552550f61a3": (   # LCDPowerableBlockBreakable_Client
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "a1687822-b4c2-4bcb-961e-3e44fae3221d", "d358358e-30b3-484a-b8b8-2e5568c7298b",
        "bc5652a0-1296-4040-adc3-a2b9c35d5afc", "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727",
        "72e2ef60-d699-48a2-9959-4e246eecdacc", "24f8dfe2-6b3f-4764-a9db-6e4383dcae5d",
        "e4622cd6-89cd-4258-bfcf-e760638697b1", "dbcee27f-284a-4388-9606-5ae12fe34cf4",
    ),
    "a79c3716-f81b-4240-9ecb-bcd6aa99247d": (   # LCDPowerableBlockBreakable_Server
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "d358358e-30b3-484a-b8b8-2e5568c7298b", "bc5652a0-1296-4040-adc3-a2b9c35d5afc",
        "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727", "e4622cd6-89cd-4258-bfcf-e760638697b1",
    ),
    "667eb18b-240f-4db0-a8ae-fb5809e1009c": (   # Timers_Client
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "a1687822-b4c2-4bcb-961e-3e44fae3221d", "d358358e-30b3-484a-b8b8-2e5568c7298b",
        "bc5652a0-1296-4040-adc3-a2b9c35d5afc", "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727",
        "72e2ef60-d699-48a2-9959-4e246eecdacc", "24f8dfe2-6b3f-4764-a9db-6e4383dcae5d",
        "e4a8653e-5c9d-4318-acd2-50feb81bbf29", "30a7eb7b-1873-479a-b7d8-fe5db6a0567e",
        "f4c12576-79d5-4f98-9f19-a341598d64c8", "6c101dae-ce4e-46cb-8fac-be66b4f6fb7e",
        "eeddee24-7023-4f71-87e7-12ea06489246",
    ),
    "2d22caf0-6740-40cd-8ef8-d9e32e7f2e86": (   # Timers_Server
        "b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
        "d358358e-30b3-484a-b8b8-2e5568c7298b", "bc5652a0-1296-4040-adc3-a2b9c35d5afc",
        "4f2bc5f9-6a6d-4347-a1eb-5937cbce6727", "dcc08559-19fa-46d2-95de-35615cb61da4",
        "de9daf84-7f7c-41e4-8df0-1ec090197a56", "eeddee24-7023-4f71-87e7-12ea06489246",
    ),
}
STRUCTURAL_PREFABS = ("b706bfc1-a8b6-4dc9-945c-8394d94478f0",   # Breakable/Structural_Server: no ObjectBuilders, so
                      "8b1eca27-c1b8-4441-83b7-c6ba97109703")   # the strip lists the composition's (Non-Breakable)


def keeps_breakable(man):
    """A block is breakable exactly when its FractureModel really fractures (>= 2 fracture zones: the racks, and
    every server and cable tray). The others (fracture.UNFRACTURED: the rod hangers and the
    Chute) go through make_non_breakable."""
    return len(man["fractured"]["zones"]) >= 2


BLOCK_MODEL_KEY = "d358358e-30b3-484a-b8b8-2e5568c7298b"     # BlockModelComponent: the breakable key follows it
BBD_BASE = "a74c6fd1-fa39-4f24-89cb-17a46e65cfd7"            # Templates/Blocks/BaseDefinitions/BreakableBlockDefinition
T_BBD = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.BreakableBlockDefinition"
# the key the breakable one follows in a template's own key order, where it is not the BlockModelComponent:
# Templates/Blocks/Breakable/Structural_ClientComposition lists it last, after its BlockDecalReceiver key
BREAKABLE_AFTER = {"35365f7b-19e2-460b-87cd-a3a9c2a97fb0": "1b938f02-30d8-4cc7-8fa7-df3ad5686048"}


def _insert_key(delta, key, pos):
    """Insert key at pos of a delta-encoded key list (later Changed indices shift up; no longer Removed)."""
    delta["Keys"].insert(pos, key)
    for ch in delta.setdefault("Changed", []):
        if ch["Index"] >= pos:
            ch["Index"] += 1
    if key in delta.get("Removed", []):
        delta["Removed"].remove(key)


def breakable_definition(spec, man, G):
    """The block's BreakableBlockDefinition with its CriticalFractures (export.json "critical": Fracture_01, the key
    zone, for servers and hung trays; none for the Chute and the rod hangers). The cloned one when the clone has it
    (every Breakable-template clone); the KVM (a ControlPanel25 clone, never breakable in vanilla) gets a new Copy of
    the base definition. Returns (rel, guid)."""
    crit = {"$DeltaEncoded": True, "Removed": [], "Added": [{"Id": f} for f in man["fractured"].get("critical", [])]}
    files = _block_files(spec, "_BreakableBlockDefinition")
    if files:
        rel = _patch_body(spec, "_BreakableBlockDefinition", lambda v: v.update(CriticalFractures=crit))
        return rel, own_guid(read_current(rel))
    rel = f"{config.NAME}/{spec.name}/{spec.name}_BreakableBlockDefinition.partialdef"
    guid = G[f"def/{spec.name}/BreakableBlockDefinition"]
    stage_def(rel, envelope(PARTIAL, {"BaseDefinition": BBD_BASE, "PartialDefinitionKind": "Copy",
                                      "Manipulator": {"Guid": guid, "CriticalFractures": crit},
                                      "DefinitionType": T_BBD, "PriorityOverride": False}, B_GAME))
    return rel, guid


def body_base(d):
    return d["$Value"].get("BaseDefinition")


def ensure_breakable(spec, man, G):
    """The inverse of make_non_breakable, for a block whose model now fractures: in both compositions the
    BreakableBlockComponent key goes back where its vanilla Breakable template has it (after the BlockModelComponent;
    BREAKABLE_AFTER: the Structural client template lists it last), bound to the block's BreakableBlockDefinition, leaves Removed, and its five tag slots leave RemovedKeys
    (they fall back to the template's, which point at it); in both prefabs an ObjectBuilders list make_non_breakable
    wrote is dropped again (the template's applies), an explicit one gets the key back the same way. On the hotfix's
    blocks this restores the pre-hotfix clone exactly. Only a planned (cut) model gets its CriticalFractures written
    here (the door racks write theirs with the doors). Returns the files changed."""
    out = []
    if man["fractured"].get("kind") == "cut":
        rel, bbd = breakable_definition(spec, man, G)
        out.append(rel)
    else:
        files = _block_files(spec, "_BreakableBlockDefinition")
        bbd = own_guid(read_current(files[0])) if files else None
    for side in ("Server", "Client"):
        crel = f"{config.NAME}/{spec.name}/{spec.name}_{side}Composition.partialdef"
        comp = read_current(crel)
        c = body(comp)
        keys = c["Components"]
        if BREAKABLE_KEY in keys["Keys"]:
            continue                                 # breakable already (the racks)
        if bbd is None:
            raise RuntimeError(f"{spec.name}: no BreakableBlockDefinition to bind")
        after = BREAKABLE_AFTER.get(body_base(comp), BLOCK_MODEL_KEY)
        pos = keys["Keys"].index(after if after in keys["Keys"] else BLOCK_MODEL_KEY) + 1
        _insert_key(keys, BREAKABLE_KEY, pos)
        keys["Changed"].append({"Kind": "Update", "Index": pos, "Value": {"Definition": bbd}})
        keys["Changed"].sort(key=lambda ch: ch["Index"])
        ts = c.get("TagSlots")
        if ts is not None:
            ts["RemovedKeys"] = [k for k in ts.get("RemovedKeys", []) if k not in BREAKABLE_SLOTS]
            if not ts["RemovedKeys"] and not ts.get("ModifiedKeys"):
                del c["TagSlots"]
        stage_def(crel, comp)
        out.append(crel)
        prel = f"{config.NAME}/{spec.name}/{spec.name}_{side}.partialdef"
        pf = read_current(prel)
        v = pf["$Value"]
        ent = v["Manipulator"].setdefault("_entity", {})
        ob = ent.get("ObjectBuilders")
        if ob is None or BREAKABLE_KEY in ob["Keys"]:
            continue
        base = v["BaseDefinition"]
        written = (TEMPLATE_PREFAB_OB_KEYS.get(base) and
                   ob["Keys"] == [k for k in TEMPLATE_PREFAB_OB_KEYS[base] if k != BREAKABLE_KEY]) or \
                  (base in STRUCTURAL_PREFABS and ob["Keys"] == [k for k in keys["Keys"] if k != BREAKABLE_KEY])
        if written and not ob.get("Changed") and ob.get("Removed") == [BREAKABLE_KEY]:
            del ent["ObjectBuilders"]
        else:
            _insert_key(ob, BREAKABLE_KEY, ob["Keys"].index(BLOCK_MODEL_KEY) + 1)
        stage_def(prel, pf)
        out.append(prel)
    return out


def _drop_key(delta, key):
    """Remove key from a delta-encoded key list (Changed indices shifted, key Removed). False when absent."""
    keys, changed = delta["Keys"], delta.setdefault("Changed", [])
    if key not in keys:
        return False
    i = keys.index(key)
    inserted = any(c["Index"] == i and c["Kind"] == "Insert" for c in changed)
    del keys[i]
    changed[:] = [c for c in changed if c["Index"] != i]
    for c in changed:
        if c["Index"] > i:
            c["Index"] -= 1
    removed = delta.setdefault("Removed", [])
    if not inserted and key not in removed:   # (a key the clone itself Inserted is not in the base: nothing to remove)
        removed.append(key)
    return True


def make_non_breakable(spec):
    """Strip the BreakableBlockComponent from a built block's server and client compositions and prefabs (see
    BREAKABLE_KEY). Builds on this run's staged copies (UPS, KVM patch their compositions / prefabs first).
    Integrity, damage, grinding and deformation stay with CubeBlockComponent (its BreakableBlockComponent and
    IMountPointModifier dependencies are WeakDependency) and the grid collider falls back to the BlockModel's
    (BlockPhysicsUtils.TryGetBlockCurrentCollider). Returns the files changed."""
    out = []
    for side in ("Server", "Client"):
        crel = f"{config.NAME}/{spec.name}/{spec.name}_{side}Composition.partialdef"
        comp = read_current(crel)
        c = body(comp)
        if not _drop_key(c["Components"], BREAKABLE_KEY):
            continue                                   # already non-breakable (the KVM: a ControlPanel25 clone)
        ts = c.setdefault("TagSlots", {"$DeltaEncoded": True, "RemovedKeys": [], "ModifiedKeys": []})
        ts["ModifiedKeys"] = [m for m in ts.get("ModifiedKeys", []) if m["$Value"] != BREAKABLE_KEY]
        have = {m["$Key"] for m in ts["ModifiedKeys"]}
        removed_slots = ts.setdefault("RemovedKeys", [])
        for slot in BREAKABLE_SLOTS:
            if slot not in have and slot not in removed_slots:
                removed_slots.append(slot)
        stage_def(crel, comp)
        out.append(crel)
        prel = f"{config.NAME}/{spec.name}/{spec.name}_{side}.partialdef"
        pf = read_current(prel)
        v = pf["$Value"]
        ent = v["Manipulator"].setdefault("_entity", {})
        ob = ent.get("ObjectBuilders")
        if ob is None:
            if v["BaseDefinition"] in TEMPLATE_PREFAB_OB_KEYS:
                keys = list(TEMPLATE_PREFAB_OB_KEYS[v["BaseDefinition"]])
            elif v["BaseDefinition"] in STRUCTURAL_PREFABS:
                keys = list(c["Components"]["Keys"]) + [BREAKABLE_KEY]
            else:
                raise RuntimeError(f"{prel}: unknown base prefab {v['BaseDefinition']}: add its ObjectBuilders keys")
            ob = ent["ObjectBuilders"] = {"$DeltaEncoded": True, "Keys": keys, "Changed": [], "Removed": []}
        _drop_key(ob, BREAKABLE_KEY)
        stage_def(prel, pf)
        out.append(prel)
    return out


# the PowerableBlockObjectBuilder: the clones' own (2.4) CubeBlock / FunctionalBlock object builder fields + the two
# Powerable fields with BasePowerableBlockBreakable's defaults (Enabled true: vanilla blocks are built ON). Not the
# SDK template's compiled fields: its PreviewOnly is rejected by the 2.4 serializer.
POWERABLE_OB = {"$Type": OB_POWERABLE, "Color": None, "BuildProgress": 1, "HealthIntegrity": 1, "Generated": False,
                "EphemeralFirstItem": False, "DisplayName": {"RawText": ""}, "Enabled": True, "WasSupplied": False}


def onto_powerable(spec, bd, old, keep=None, enabled=True):
    """The powerable chain: the block definition bd (being staged, patched in place) becomes a PowerableBlockDefinition
    with no consumed resource (keep: base-template values to carry over), and the component at key old in both
    compositions (with every tag slot on it) and its object builder in both prefabs become vanilla's
    PowerableBlockComponent at POWERABLE_KEY. A prefab that inherits all its object builders gets a delta listing its
    composition's keys. enabled: the object builders' initial On/Off (PowerableBlockComponent.Init reads ob.Enabled,
    PowerableBlockComponent.cs:303-307; saved blocks serialize their own, :340-345, so it only affects new blocks).
    Idempotent: re-staging over an installed (already patched) copy changes nothing."""
    v = bd["$Value"]
    v["BaseDefinition"] = POWERABLE_DEF_BASE
    v["DefinitionType"] = T_POWERABLE_DEF
    m = v["Manipulator"]
    for k, val in (keep or {}).items():
        m.setdefault(k, val)
    m["ConsumedResource"] = None
    block_def = m["Guid"]
    out = {"block_def": block_def}
    comp_keys = {}
    for side in ("Server", "Client"):
        f = _block_files(spec, f"_{side}Composition")[0]
        d = read_current(f)   # earlier patches of this run (the KVM's subparts) are already staged: build on them
        c = body(d)
        comp_keys[side] = list(c["Components"]["Keys"])
        _swap_component(c["Components"], {"Definition": block_def, "Type": T_POWERABLE}, old)
        _retarget_slots(c, old)
        stage_def(f, d)
        out[f"{side}Composition"] = f
    for side in ("Server", "Client"):
        f = _block_files(spec, f"_{side}.partialdef")[0]
        d = read_current(f)
        ob = body(d)["_entity"].setdefault("ObjectBuilders", {"$DeltaEncoded": True, "Keys": comp_keys[side],
                                                              "Changed": [], "Removed": []})
        _swap_component(ob, dict(POWERABLE_OB, Enabled=enabled), old)
        stage_def(f, d)
        out[side] = f
    return out


# A new KVM spawns Off (in-game feedback), so stowed (drawer in, screen folded) in both
# script modes; the player opens it from the terminal's On/Off or by Use on it (functional.py, UsePowerableAction).
KVM_SPAWN_ENABLED = False


def patch_kvm_onoff(spec, bd):
    """The KVM (ControlPanel25: a FunctionalBlockComponent) gets the vanilla On/Off state, terminal-listed
    (no NO_TERMINAL_FUNCTIONAL), spawning Off (KVM_SPAWN_ENABLED)."""
    return onto_powerable(spec, bd, FUNCTIONAL_KEY, enabled=KVM_SPAWN_ENABLED)


# ------------------------------------------------------------------------------------------------ Programmable
# The core shell was a structural WallInsertPanel clone (CubeBlockComponent at STRUCTURAL_KEY, no terminal). Here
# it becomes a functional blade in DATA, the same in both script modes:
#   * the powerable chain (onto_powerable): terminal-listed, On/Off, no power sink; ControlPanel25's Terminal use
#     dummy over the management module (dc/functional.py PROG_MGMT); the block definition GUID is unchanged;
#   * vanilla InGameScriptingComponent + our full InGameScriptingDefinition in the SERVER composition,
#     its object builder (the starter program, not running) in the server prefab (dc/scripting.py);
#   * an empty BlockMaterialSwapper on our models in the client composition (the door racks' pattern), which
#     the client script fills with the status LED -> green while Working; data-only the lamps stay amber.
STRUCTURAL_KEY = "786ef564-3cbf-4509-a58c-ad19243fffc1"      # Structural_*Composition: CubeBlockComponent
STRUCTURAL_DEF_BASE = "8a27c509-f7ca-4c08-9a00-66fa6893e3d0"  # Templates/.../StructuralCubeBlockDefinition
# The values the structural template chain gives the block where the Powerable template's differ (block_chain.py
# resolve of both; Tests/test_programmable_data.py re-derives them): carried over, so rebasing changes nothing else.
# (Fragility is not carried over: the Programmable is Functional, FRAGILITY.)
STRUCTURAL_DEF_VALUES = {"Density": "d8adcfdc-f8e2-467e-9d27-78deae4057da",
                         "RecipeEfficiency": "30e09afc-4437-49fe-aff5-54553d05d3c4", "PCU": 5}
CONTROL_PANEL25_BMD = os.path.join(config.VANILLA_REF, "Blocks", "ControlPanel", "25",
                                   "ControlPanel25_BlockModelDefinition.partialdef")
T_SWAPPER = "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Render.BlockMaterialSwapperComponent"
T_SWAPPER_DEF = "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Render.BlockMaterialSwapperDefinitionObjectBuilder"
PROG_SWAPPER_FILE = f"{config.NAME}/DC_Srv_Programmable/DC_Srv_Programmable_BlockMaterialSwapperDefinition.def"
# files the core clone does not have: write_all creates them (Tests/test_fresh_clone.py removes them again)
PROG_STAGED_ONLY = (scripting.DEFINITION_FILE, PROG_SWAPPER_FILE)


def patch_programmable_dummies(spec, dummies, G):
    """Add ControlPanel25's "Terminal" use dummy (vanilla type, scale, highlight section; read from tools/vanilla-ref)
    if the model definition has none yet; patch_model_def then places it like every functional server's
    (functional.DUMMIES: over the management module). Idempotent (stable delta key)."""
    keys, changed = dummies.setdefault("Keys", []), dummies.setdefault("Changed", [])
    dummies.setdefault("Removed", [])
    if any(c["Value"].get("Name") == "Terminal" for c in changed):
        return
    van = body(read_json(CONTROL_PANEL25_BMD))["Dummies"]["Changed"]
    term = [c["Value"] for c in van if c["Value"]["Name"] == "Terminal"][0]
    keys.append(G[f"dummy/{spec.name}/Terminal"])
    changed.append({"Kind": "Insert", "Index": len(keys) - 1, "Value": json.loads(json.dumps(term))})


def patch_programmable_functional(spec, bd):
    """The powerable chain from the structural CubeBlockComponent (bd: the block definition being staged).
    Fragility Functional, the PowerableBlockDefinition template's own value (every vanilla
    powerable block, e.g. Timer50, resolves to it): MaxHPMassMultiplier 0.8, rifle damage x0.5 past 2.4 flat
    reduction, instead of the structural panel's 1.0 / x1 past 4. Set explicitly: the installed copy names Structural."""
    out = onto_powerable(spec, bd, STRUCTURAL_KEY, keep=STRUCTURAL_DEF_VALUES)
    body(bd)["Fragility"] = FRAGILITY["Functional"]
    return out


def stage_programmable_scripting(spec, G):
    """The InGameScriptingDefinition (a full .def: vanilla ships none to copy) and the component plus
    its object builder on the server side only. The terminal's script editor is server-side
    (ProgrammableBlockDetailModelServer, a replicated [BlockDetailProvider] bound to the component), and a client
    copy would compile and run a saved Running program a second time (InGameScriptingComponent.OnAddedToScene)."""
    dguid = G[scripting.DEFINITION_KEY]
    stage_def(scripting.DEFINITION_FILE, envelope(scripting.DEFINITION_TYPE, scripting.definition(dguid), B_GAME))
    key = G[scripting.COMPONENT_KEY]
    comp, prefab = _add_components(spec, "Server", [(key, dguid, scripting.COMPONENT_TYPE, "InGameScriptingComponent",
                                                     scripting.object_builder())])
    return {"definition": dguid, "definition_file": scripting.DEFINITION_FILE, "component_id": key,
            "composition": comp, "prefab": prefab}


def patch_programmable_swapper(spec, models, G):
    """A BlockMaterialSwapper over our models (NonFractured; Fractured = Damaged) mapping no mesh part: inert in
    data. The client script adds functional.PROG_LED -> EmissiveGreen to its Working replacements."""
    g = G[f"def/{spec.name}/BlockMaterialSwapper"]
    stage_def(PROG_SWAPPER_FILE, envelope(T_SWAPPER_DEF, {
        "Guid": g, "WorkingReplacementModels": ["{G}" + models["NonFractured"], "{G}" + models["Fractured"]],
        "WorkingReplacementsMeshParts": []}, B_GAME))
    key = G[f"key/{spec.name}/swapper"]
    comp, prefab = _add_client_components(spec, [(key, g, T_SWAPPER, "BlockMaterialSwapperComponent")])
    return {"definition": g, "file": PROG_SWAPPER_FILE, "component_id": key, "composition": comp, "prefab": prefab}


def _vanilla_b50(name):
    return read_json(os.path.join(BATTERY50, name))


def patch_ups(spec, G):
    """Two Power Cell slots and the capacity / rates for two cells (see the module docstring). Returns a summary."""
    out = {}
    # the slot inventory definition: unchanged clone of Battery50's (Power Cell only, 25 kg = one cell per slot)
    inv_file = _block_files(spec, "_InventoryDefinition")
    assert len(inv_file) == 1, inv_file
    inv = read_mod(inv_file[0])
    inv_guid = own_guid(inv)
    out["slot_inventory"] = {"file": inv_file[0], "guid": inv_guid, "MaxMass": body(inv)["MaxMass"],
                             "WhitelistedItems": body(inv)["WhitelistedItems"]}
    # staged unchanged (as cloned), so the package carries every definition the two slots rely on
    stage_def(inv_file[0], inv)
    for pat in ("InventorySlotsServerDefinition", "InventorySlotSyncDefinition"):
        f = _block_files(spec, pat)
        assert len(f) == 1 and body(read_mod(f[0]))["SlotDefinition"] == inv_guid, (pat, f)
        stage_def(f[0], read_mod(f[0]))
    # server composition: a second InventoryComponent, same definition, tagged "CellSlot 1"
    comp_file = _block_files(spec, "_ServerComposition")[0]
    comp = read_mod(comp_file)
    cb = body(comp)
    base_keys = _vanilla_b50("Battery50_ServerComposition.partialdef")["$Value"]["Manipulator"]["Components"]["Keys"]
    slots = []
    for i, *_ in functional.UPS_BAYS:
        tag = f"CellSlot {i}"
        mk = {m["$Key"]: m["$Value"] for m in cb["TagSlots"]["ModifiedKeys"]}
        if tag in mk:
            key = mk[tag]
        else:
            key = G[f"component/{spec.name}/{tag}"]
            cb["TagSlots"]["ModifiedKeys"].append({"$Key": tag, "$Value": key})
        comps = cb["Components"]
        if key not in comps["Keys"]:
            comps["Keys"].append(key)
            comps["Changed"].append({"Kind": "Insert", "Index": comps["Keys"].index(key),
                                     "Value": {"Definition": inv_guid, "Type": INVENTORY_COMPONENT}})
        slots.append((tag, key))
    stage_def(comp_file, comp)
    out["composition"] = {"file": comp_file, "slots": slots, "vanilla_components": len(base_keys),
                          "components": len(cb["Components"]["Keys"])}
    # server prefab: every slot starts with one Power Cell at vanilla's fill (Battery50 slot 0's object builder)
    pre_file = _block_files(spec, "_Server.partialdef")[0]
    pre = read_mod(pre_file)
    ob = body(pre)["_entity"]["ObjectBuilders"]
    first = next(c["Value"] for c in ob["Changed"] if ob["Keys"][c["Index"]] == slots[0][1])
    for tag, key in slots[1:]:
        if key not in ob["Keys"]:
            ob["Keys"].append(key)
            ob["Changed"].append({"Kind": "Insert", "Index": ob["Keys"].index(key), "Value": json.loads(json.dumps(first))})
    stage_def(pre_file, pre)
    out["prefab"] = {"file": pre_file, "keys": len(ob["Keys"])}
    # resource container: capacity = cells x MaxStored (the runtime recomputes it from the cells anyway), rates x2
    rc_file = _block_files(spec, "ResourceContainerInventoryDefinition")[0]
    rc = read_mod(rc_file)
    van = _vanilla_b50("Battery50_Battery_ResourceContainerInventoryDefinition.partialdef")["$Value"]["Manipulator"]
    n = len(functional.UPS_BAYS)
    r = body(rc)
    r["MaxCapacity"] = n * functional.POWER_CELL_MAX_STORED
    r["MaxChargingRate"] = round(n * van["MaxChargingRate"], 6)
    r["MaxDischargeRate"] = round(n * van["MaxDischargeRate"], 6)
    stage_def(rc_file, rc)
    out["resource_container"] = {"file": rc_file, **{k: r[k] for k in ("MaxCapacity", "MaxChargingRate",
                                                                       "MaxDischargeRate")}}
    return out


# ------------------------------------------------------------------------------------------------ cable trays
TRAY_FAMILIES = ("tray", "trayrods")
TRAY_PCU = 5   # the vanilla decorative standard (Truss, Handrail, Catwalk, StructuralSupport)


T_PLACER = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.PlacementDefinitionObjectBuilder"


def rods_placer(spec, G):
    """The rod hangers' own PlacementDefinition (the cloned strut has none: it used its template's): the
    Pipes trays' placer values, AutoRotateFace off (null) as the trays': aimed at a ceiling the hanger
    keeps its authored up (the anchor plates to the ceiling), aimed at a tray's top its couplers seat on the rod
    plates; AlignWithMountPoints puts them on their mount hints. Staged as <name>_PlacementDefinition.def, its GUID
    stable (asset_guids.json). -> (GUID, rel)."""
    rel = f"{config.NAME}/{spec.name}/{spec.name}_PlacementDefinition.def"
    g = meta_id(os.path.join(config.MOD_ASSETS, rel)) or G[f"def/{spec.name}/Placement"]
    stage_def(rel, envelope(T_PLACER, {"Guid": g, "BestSnapSize": None, "AlignWithMountPoints": True,
                                       "AllowSquareSnapping": True, "AutoRotateFace": None, "SizeGroup": None,
                                       "MaxInVoxelRatio": 0.5, "SnapAlignment": 0, "OverrideSymmetries": None},
                            B_GAME))
    return g, rel


def tray_patch(spec, bd, G=None):
    """A tray block: bd = its block definition being staged (patched in place).
      * PCU 5 (WallInsertPipes inherits its PCU from the template; StructuralSupportStraight already says 5);
      * no MountPointGeneratorSettings: all six directions mount (ports on every face; the model's mount hints
        decide where). Neither source sets one, so this only guards against a re-clone from another source;
      * the cloned PlacementDefinition (WallInsertPipes) with AutoRotateFace null: vanilla's "Down" would turn a tray
        upside down when it is aimed at a ceiling; the rod hangers (the strut has no placer of its own) get
        their own (rods_placer, when G is given).
    Idempotent. Returns {pcu, placer, placer_file}."""
    m = body(bd)
    m["PCU"] = TRAY_PCU
    m.pop("MountPointGeneratorSettings", None)
    out = {"pcu": TRAY_PCU, "placer": None, "placer_file": None}
    if spec.family == "trayrods" and G is not None:
        g, rel = rods_placer(spec, G)
        m["PlacerDefinition"] = g
        out.update(placer=g, placer_file=rel)
        return out
    files = _block_files(spec, "_PlacementDefinition")
    if len(files) > 1:
        raise RuntimeError(f"{spec.name}: several cloned placement definitions {files}")
    if files:
        pl = read_current(files[0])
        if m.get("PlacerDefinition") != own_guid(pl):
            raise RuntimeError(f"{spec.name}: PlacerDefinition {m.get('PlacerDefinition')} is not the cloned "
                               f"placer {own_guid(pl)} ({files[0]})")
        body(pl)["AutoRotateFace"] = None
        stage_def(files[0], pl)
        out.update(placer=own_guid(pl), placer_file=files[0])
    return out


# ------------------------------------------------------------------------------------------------ raised floor
FLOOR_PCU = 5          # as the clone source (CatwalkSquareBase250), the vanilla decorative standard
FLOOR_MOUNTS = "All"   # the tile mounts on every face (deck Up, base plates Down, stringer band on the sides)


def floor_patch(spec, bd):
    """A raised-floor block: bd = its block definition being staged (patched in place). PCU 5 and
    mount directions All (the model's mount hints decide where). The clone keeps the catwalk's breakable chain: the
    floor's Fractured model has two fracture zones (deck, understructure), so make_non_breakable never runs on it.
    Idempotent. Returns {pcu, mounts}."""
    m = body(bd)
    m["PCU"] = FLOOR_PCU
    m["MountPointGeneratorSettings"] = {"Directions": FLOOR_MOUNTS}
    return {"pcu": FLOOR_PCU, "mounts": FLOOR_MOUNTS}


# ------------------------------------------------------------------------------------- fragility
# Vanilla 4.0's CubeBlockFragilityDefinitions (SDK Blocks/Shared/Fragility/: Structural.def, Functional.def, Windows
# .partialdef, a Copy of Structural with ProjectileDamage 2.5 / x1.25 and ExplosionDamage x0).
FRAGILITY = {"Structural": "c748fae2-a8fe-4012-9936-cf2a570fa685",
             "Functional": "eaaa3a8d-d04c-461f-a7f5-00e8cabd27bd",
             "Windows": "060b61a3-51ed-4a47-8d4e-e3c2f8712216"}
# vanilla Blocks/Windows/Windows_BlockEffectsComponentDefinition.partialdef: the glass-shatter fracture / death effect
# (99e7ae3b) and DamageGlassBlock / DestroyGlassBlock audio; every vanilla window's BlockEffects Copy is based on it
# (WindowFlat250 / 125, WindowSlopeLong500, ...)
WINDOWS_EFFECTS = "30c64f59-209d-40b7-97d2-b7aaaf9a1add"
# the overrides of those effects our clone inherited from DeckPanel250 (DestroyBlockTiny): dropped, so the glass ones
# apply (vanilla WindowFlat250's Copy sets only the construction-state dummy)
WINDOWS_EFFECT_KEYS = ("OnFractureBlockParticleEffect", "OnBlockDeathParticleEffect", "OnDamagedAudio",
                       "OnDestroyedAudio")


def patch_roof_effects(spec):
    """The roof's cloned BlockEffects Copy re-based onto the vanilla Windows BlockEffects (it is glazing),
    keeping its GUID (still bound in the client composition) and its construction-state effect. Idempotent. Returns
    the base."""
    f, d = _effects_copy(spec)
    v = d["$Value"]
    v["BaseDefinition"] = WINDOWS_EFFECTS
    for k in WINDOWS_EFFECT_KEYS:
        v["Manipulator"].pop(k, None)
    stage_def(f, d)
    return v["BaseDefinition"]


def _effects_copy(spec):
    """(file, current data) of the block's one cloned BlockEffects definition, a Copy partialdef (the one its client
    composition binds: Tests/test_effects.py checks the binding)."""
    files = _block_files(spec, "BlockEffectsComponentDefinition")
    if len(files) != 1:
        raise RuntimeError(f"{spec.name}: expected one cloned BlockEffects definition, found {files}")
    d = read_current(files[0])
    if d["$Value"].get("PartialDefinitionKind") != "Copy":
        raise RuntimeError(f"{spec.name}: {files[0]} is not a Copy partialdef")
    return files[0], d


# ------------------------------------------------------------------------------------- containment roof
ROOF_PCU = 5           # as the clone source (DeckPanel250)
ROOF_MOUNTS = "All"    # the model's mount hints decide where (the four edges over the rail band; not Up / Down)


def roof_patch(spec, bd):
    """A containment roof panel: bd = its block definition being staged (patched in place). PCU 5,
    Fragility Windows, mount directions All, and the cloned DeckPanel250 placer with AutoRotateFace null (as the
    trays' patch): the deck's "Down" would flip a panel aimed at a rack's rail face. The clone keeps the deck's
    breakable chain: the roof's
    Fractured model has two fracture zones (glazing, frame), so make_non_breakable never runs on it. Idempotent.
    Returns {pcu, mounts, placer, placer_file}."""
    m = body(bd)
    m["PCU"] = ROOF_PCU
    m["MountPointGeneratorSettings"] = {"Directions": ROOF_MOUNTS}
    m["Fragility"] = FRAGILITY["Windows"]   # glazing, as vanilla WallInsertWindowFlat150
    files = _block_files(spec, "_PlacementDefinition")
    if len(files) != 1:
        raise RuntimeError(f"{spec.name}: expected one cloned placement definition, found {files}")
    pl = read_current(files[0])
    if m.get("PlacerDefinition") != own_guid(pl):
        raise RuntimeError(f"{spec.name}: PlacerDefinition {m.get('PlacerDefinition')} is not the cloned placer "
                           f"{own_guid(pl)} ({files[0]})")
    body(pl)["AutoRotateFace"] = None
    stage_def(files[0], pl)
    return {"pcu": ROOF_PCU, "mounts": ROOF_MOUNTS, "placer": own_guid(pl), "placer_file": files[0]}


# ------------------------------------------------------------------------------------------------ PDUs
PDU_PCU = 5             # as the clone source (WallInsertPanel, the decorative standard)
PDU_CABINET_MOUNTS = "All"   # the rack's flush mounts (sides, bottom, top rim, containment rail band): the hints decide


def pdu_patch(spec, bd):
    """The PDU cabinet / a rack PDU strip: bd = its block definition being staged (patched in place).
    PCU 5. Mount directions: the cabinet All (as the racks: its hints decide); a strip only the directions its hints
    lie on (dc/pdu.strip_directions: Down = the plug seat on the plinth; not Forward, the bracket on the bulkhead,
    which let a raised strip validate), so it seats only on its plinth seat (or any Up face). A strip's cloned
    WallInsertPanel placer gets AutoRotateFace null (as the trays' patch): the panel's "Down" would turn a strip
    aimed at the bulkhead onto its back. Both keep the
    panel's breakable chain (their Fractured models have 8 / 2-3 zones: ensure_breakable). Idempotent.
    Returns {pcu, mounts, placer, placer_file}."""
    from . import pdu
    m = body(bd)
    m["PCU"] = PDU_PCU
    mounts = PDU_CABINET_MOUNTS if spec.family == "pdu_cabinet" else pdu.strip_directions(spec)
    m["MountPointGeneratorSettings"] = {"Directions": mounts}
    out = {"pcu": PDU_PCU, "mounts": mounts, "placer": None, "placer_file": None}
    if spec.family == "pdu_strip":
        files = _block_files(spec, "_PlacementDefinition")
        if len(files) != 1:
            raise RuntimeError(f"{spec.name}: expected one cloned placement definition, found {files}")
        pl = read_current(files[0])
        if m.get("PlacerDefinition") != own_guid(pl):
            raise RuntimeError(f"{spec.name}: PlacerDefinition {m.get('PlacerDefinition')} is not the cloned placer "
                               f"{own_guid(pl)} ({files[0]})")
        body(pl)["AutoRotateFace"] = None
        stage_def(files[0], pl)
        out.update(placer=own_guid(pl), placer_file=files[0])
    return out
# ------------------------------------------------------------------------------------- signs and labels
def sign_patch(spec, bd):
    """A sign / label: bd = its block definition being staged (patched in place). PCU 35 (as
    LCDNarrow50) and mount directions restricted to the sign's one mounting face (dc/signs.mount_direction: the aisle
    sign Backward, the hanging sign Up, the rack label Down), so it never mounts by its screen or bezel. The clone
    keeps LCDNarrow50's LcdMultiPanel and breakable chains: its Fractured model has 2-3 in-plane zones
    (dc/fracture.py _sign), so make_non_breakable never runs on it. Idempotent. Returns {pcu, mounts}."""
    from . import signs
    m = body(bd)
    m["PCU"] = functional.SIGN_PCU
    m["MountPointGeneratorSettings"] = {"Directions": signs.mount_direction(spec)}
    return {"pcu": functional.SIGN_PCU, "mounts": signs.mount_direction(spec)}


def sign_dummies(spec):
    """{"LcdPanel": ((x, y, z) game, (sx, sy, sz))}: the cloned UseTerminal dummy (vanilla name and type kept) over the
    sign's front screen; on the hanging sign deep enough to reach both faces (aim at either face: the terminal lists
    both surfaces)."""
    from . import signs
    sc = signs.screens(spec)
    c = sc[0].center
    sh = [0.125 if n % 2 == 0 else 0.0 for n in spec.cells]           # export_models.shift (the .model LOD0 shift)
    pos = (round(c[0] + sh[0], 6), round(c[2] + sh[1], 6), round((0.0 if len(sc) > 1 else -c[1]) + sh[2], 6))
    w, h = sc[0].size
    depth = 2 * abs(c[1]) + 0.04 if len(sc) > 1 else 0.05
    return {"LcdPanel": (pos, (round(w, 4), round(h, 4), round(depth, 4)))}


def write_folder_metas(G):
    for dp, ds, _ in os.walk(config.STAGE_ASSETS):
        for d in ds:
            full = os.path.join(dp, d)
            rel = os.path.relpath(full, config.STAGE_ASSETS)
            stage_meta(rel, meta_id(os.path.join(config.MOD_ASSETS, rel)) or G["dir/" + rel])


def write_all(specs=None, report=None):
    specs = list(specs or catalog.STAGED)
    G = Guids()
    cmap = clone.load_map()
    if os.path.isdir(config.STAGE_ASSETS):
        shutil.rmtree(config.STAGE_ASSETS)
    os.makedirs(os.path.join(config.STAGE_ASSETS, config.NAME))   # config read at call time (tests redirect it)
    _STAGED.clear()
    if report is None:
        report = read_json(config.REPORT_PATH) if os.path.exists(config.REPORT_PATH) else {"blocks": {}}
    built = built_names(report)
    summary = {"blocks": {}, "unlock": [], "menu": {}}
    unlock_blocks, unlock_kinds = [], []
    menu_ids = menu_guids(G)
    for spec in specs:
        e = clone.entry(spec, cmap)
        if not e or not e.get("info"):
            raise RuntimeError(f"{spec.name} is not cloned yet: run python3 Source/Model/dc/clone.py")
        info = e["info"]
        title, desc = names.NAMES[spec.name]
        s = {"name": title, "built": False}
        owner = menu.kind_owner(spec)
        owner_kind = clone.entry(owner, cmap)["info"]["kind"]
        s["kind"] = patch_kind(spec, info, menu_ids, G)
        bd = read_mod(info["block_def_file"])
        body(bd)["BlockKind"] = owner_kind            # 42U and 24U racks of a door variant share one kind (sizes)
        # every pipeline block is costed (the room pieces included; a STAGED block outside the pipeline
        # would keep its clone's vanilla recipe: Tests/test_room_menu.py proves there is none)
        s["recipe"] = patch_recipe(spec, bd, G, report) if recipes.costed(spec) and spec in catalog.BLOCKS else None
        if spec.family in TRAY_FAMILIES:
            s["tray"] = tray_patch(spec, bd, G)
        if spec.family == "rack":
            body(bd)["MountPointGeneratorSettings"] = {"Directions": RACK_MOUNTS}
        if spec.family == "floor":
            s["floor"] = floor_patch(spec, bd)
        if spec.family == "contain_roof":
            s["roof"] = roof_patch(spec, bd)
            s["roof"]["effects"] = patch_roof_effects(spec)
        if spec.family == "contain_door":
            s["door"] = door_patch(spec, bd)
        if spec.family == "crac":
            s["crac"] = crac_patch(spec, bd)
        if spec.family in ("pdu_cabinet", "pdu_strip"):   # the PDUs
            s["pdu"] = pdu_patch(spec, bd)
        if spec.family == "sign":
            s["sign"] = sign_patch(spec, bd)
        ui = body(bd).setdefault("UIData", {})
        ui["Name"] = title
        man = manifest(spec) if spec.name in built else None
        if man:
            icon = os.path.join(UI_DIR, f"{spec.name}_Icon.png")
            if os.path.exists(icon):
                ui["Icon"] = "{G}" + stage_file(icon, f"{config.NAME}/{spec.name}/UI/{spec.name}_Icon.png", G)
            models = stage_models(spec, man, G)
            if spec.family == "rack" and man.get("subparts"):
                s["rack_subparts"] = stage_rack_subparts(spec, man, models, G, bd)
            if spec.family == "contain_door":
                s["contain_door"] = stage_contain_door(spec, man, models, G)
            if spec.family == "crac":
                s["crac_subparts"] = stage_crac(spec, man, models, G)
            stages = patch_model_def(spec, info, man, models, G)
            if spec.name in functional.INDICATOR_PARTS:
                s["indicator"] = patch_indicator(spec, models, man)
            if spec.variant == "Status":
                s["lcd"] = patch_lcd(spec, [dict(MeshPartName=functional.LCD_SURFACE, **functional.STATUS_LCD)])
            if spec.family == "sign":
                s["lcd"] = patch_lcd(spec, functional.SIGN_LCD[spec.name], G)
            if spec.variant == "UPS":
                s["ups"] = patch_ups(spec, G)
            if spec.variant == "KVM":
                s["subparts"] = stage_kvm_subparts(spec, man, G)
                s["onoff"] = patch_kvm_onoff(spec, bd)
                s["hum"] = patch_hum(spec, HUM_SERVER)   # ControlPanel25 has no OnUseAudio (the others keep vanilla's)
            if spec.variant == "UPS":
                s["particle_sets"] = patch_particle_sets(spec)
            if spec.variant == "KVM":            # after patch_hum (both edit the one cloned BlockEffects)
                s["effects"] = patch_kvm_effects(spec)
            if spec.variant == "Programmable":
                s["onoff"] = patch_programmable_functional(spec, bd)
                s["scripting"] = stage_programmable_scripting(spec, G)
                s["swapper"] = patch_programmable_swapper(spec, models, G)
                s["effects"] = patch_programmable_effects(spec)
            s["sparks"] = patch_spark_effects(spec, G)   # None for a block that does not spark
            if keeps_breakable(man):
                s["breakable"] = ensure_breakable(spec, man, G)
                s["critical"] = man["fractured"].get("critical")
            else:
                s["non_breakable"] = make_non_breakable(spec)
            if spec.family == "server":   # deco ones too (no Up mount)
                body(bd)["MountPointGeneratorSettings"] = {"Directions": UPS_MOUNTS if spec.variant == "UPS"
                                                           else SERVER_MOUNTS}
            s.update(built=True, models=models, model_def=info["model_def"],
                     stages=[(st["Value"]["BuildRatioLowerBound"], len(st["Value"]["PartChanges"]["_data"]))
                             for st in stages],
                     fractures=[z["id"] for z in man["fractured"]["zones"]],
                     icon=ui.get("Icon"))
            if spec in catalog.BLOCKS:   # the room pieces joined the initial unlock with their menu
                unlock_blocks.append(info["server_prefab"])
                if owner_kind not in unlock_kinds:
                    unlock_kinds.append(owner_kind)
        stage_def(info["block_def_file"], bd)
        summary["blocks"][spec.name] = s
    summary["menu"] = stage_menu(menu_ids, G)
    summary["texts"] = texts.stage(G)   # every Name / Description / Tooltip staged above, as en-US texts
    if unlock_blocks:
        ov = envelope(PARTIAL, {
            "BaseDefinition": INITIAL_UNLOCK, "PartialDefinitionKind": "Override",
            "Manipulator": {"Blocks": {"$DeltaEncoded": True, "Removed": [], "Added": unlock_blocks},
                            "BlockKinds": {"$DeltaEncoded": True, "Removed": [], "Added": unlock_kinds}},
            "DefinitionType": "Game2:Keen.Game2.Simulation.GameSystems.Progression.ProgressionInitialUnlockConfiguration",
            "PriorityOverride": False}, B_GAME)
        write_json(stage_path(UNLOCK_FILE), ov)
        stage_meta(UNLOCK_FILE, meta_id(os.path.join(config.MOD_ASSETS, UNLOCK_FILE)) or G["def/InitialUnlock"])
        summary["unlock"] = unlock_blocks
    summary["script_ids"] = script_guids.reserve(G)   # ids only the scripts use
    write_folder_metas(G)
    G.save()
    files = [os.path.relpath(os.path.join(dp, f), config.INTEGRATION_DIR)
             for dp, _, fs in os.walk(config.STAGE_ASSETS) for f in fs]
    summary["staged_files"] = len(files)
    return summary



# ------------------------------------------------------------------------------------------------ rack doors
# The door racks are SlidingDoorNarrow250 clones (DoorServer / DoorClient / DoorBlockCollider / DoorAudio /
# ConditionalSubParts kept as cloned). The leaves become HINGED: each leaf subpart's DoorSegmentTransformSLERP reads
# "<leaf>Closed" / "<leaf>Open" dummies of the block model, both ON the hinge axis, the open one turned 85 deg about
# the vertical (dc/doors.py). FrontRear gets two more leaves (copies of the front leaf set with new GUIDs and their
# own dummy types). The side panels (RackSide, twice) and the full racks' fan tray
# are ConditionalSubParts entries, spawned while the rack is Functional, each a bound client prefab (bind_subpart);
# the tray's two rotors (InfiniteRotation) are children of the tray's CLIENT prefab (_rotor_children), toggled with
# Working by the rack's FunctionalBlockAnimationController (the closest parent controller). The open racks get the
# powerable functional chain and a client-only ConditionalSubPartsComponent (stage_rack_subparts). Below Functional the
# Fractured / Damaged models show the baked stand-ins (fracture.STANDINS), hidden while the subparts are spawned.

USE_DOOR = "4511a2ef-912d-4980-adf2-47b1e8898190"            # System/DummyTypes/UseDoor (aim + use toggles the door)
BLOCK_EFFECTS_KEY = "72e2ef60-d699-48a2-9959-4e246eecdacc"   # BlockEffectsComponent's key in the vanilla templates
HUM_RACK = "event:/SFX/Block/GyroscopeSM"                     # vanilla loop while Working: the tray fans' whir
HUM_SERVER = "event:/SFX/Block/LCD"                           # vanilla loop while Working: the KVM's screen / PSU hum
# the CRAC's hum is set explicitly, as the racks' and servers' are. Vanilla 2.4 has
# no fan / air-handler loop (its OnUseAudio set: tools/vanilla-ref, 40 events); the gyroscope family's whir is the
# closest to an EC fan bank, and MID (not the racks' SM) is the deeper one, for three 0.4 m fans against a rack's
# small tray fans. Listen in game; the alternative is event:/SFX/Block/O2H2Generator (a pump / compressor hum).
HUM_CRAC = "event:/SFX/Block/GyroscopeMID"
CRAC_PORT_TYPE = "ServicePort"                                # the CRAC service ports' own (inert) dummy type
CRAC_PORT_TYPE_ON = "29d45e5b-2ddf-4ba5-9031-885260550947"     # vanilla UseConveyor (O2H2Generator250's ports): later
T_INFROT = f"{RIGID}InfiniteRotationAnimationComponent"
FAN_ANIM = {"RotationAxis": {"X": 0, "Y": 1, "Z": 0}, "AngularSpeed": 720, "AngularSpeedup": 360,
            "AngularSlowdown": 180}
LEAF_FILES = ("{leaf}.def", "{leaf}_Client.def", "{leaf}_ClientComposition.def",
              "{leaf}_Client_DoorSegmentTransformSLERPDefinition.def", "{leaf}_Client_ModelComponentDefinition.def",
              "{leaf}_Server.def", "{leaf}_ServerComposition.def")
REAR_TEMPLATE = {"RearLeftDoor": "RightDoor", "RearRightDoor": "LeftDoor"}   # same leaf model, turned 180 deg
DETECTOR = "DoorwayObstructionDetector"
def critical_fractures(man):
    """The fracture zones that carry the hinges: the side columns. The fracture plan names them (export.json
    "critical"); for an older export, the zones lying wholly outside the slot (min |x| >= the slot plane), derived from
    the exported zone boxes, not from their order."""
    if "critical" in man["fractured"]:
        return sorted(man["fractured"]["critical"])
    out = []
    for z in man["fractured"]["zones"]:
        (x0, _, _), (x1, _, _) = z["lo"], z["hi"]
        if min(abs(x0), abs(x1)) >= DM.SLOT_HALF_W - 0.005 and x0 * x1 >= 0:
            out.append(z["id"])
    return sorted(out)
_DOOR_CTX = {}


def read_current(rel):
    """A definition as it will be installed: the staged copy when this run already patched it, else the mod's."""
    return read_json(stage_path(rel)) if os.path.exists(stage_path(rel)) else read_mod(rel)


def _leaf_rel(spec, leaf, pat):
    return f"{config.NAME}/{spec.name}/Subparts/{spec.name}_{pat.format(leaf=leaf)}"


def _stage_subpart_model(spec, man, G, sub):
    info = man["subparts"][sub]
    src = os.path.join(config.MODELS_DIR, spec.name, info["dir"])
    rel = f"{config.NAME}/{spec.name}/Models/Subparts/{sub}"
    geom = [(stage_file(os.path.join(src, l["file"]), f"{rel}/{l['file']}", G), l["materials"])
            for l in info["lods"]]
    col = None
    if info.get("collision"):
        c = info["collision"]
        col = stage_file(os.path.join(src, c["file"]), f"{rel}/{c['file']}", G)
        stage_file(os.path.join(src, c["bin"]), f"{rel}/{c['bin']}", G)
    mrel = f"{rel}/{spec.name}_{sub}.model"
    write_json(stage_path(mrel), subpart_model_asset(geom, col))
    stage_meta(mrel, G[mrel])
    return G[mrel]


def _door_dummy_types(spec, G):
    """{leaf: (closed type, open type)}: the clone's own types for the front leaves, new ones for the rear."""
    out = {}
    for lf in doors.leaves(spec):
        pair = []
        for kind in ("Closed", "Open"):
            rel = f"{config.NAME}/{spec.name}/{lf['name']}{kind}Dummy.def"
            if lf["name"] in REAR_TEMPLATE:
                g = G[f"dummytype/{spec.name}/{lf['name']}{kind}"]
                stage_def(rel, envelope("VRage:Keen.VRage.Core.Model.DummyTypeDefinitionObjectBuilder", {"Guid": g}))
            else:
                g = own_guid(read_mod(rel))
            pair.append(g)
        out[lf["name"]] = tuple(pair)
    return out


def _stage_leaf(spec, lf, model_guid, types, G):
    """The leaf's seven subpart definitions (prefab binding, client / server prefab + composition, SLERP, model
    component): the front ones as cloned, the rear ones copied from the front leaf with the same model under new GUIDs
    and the rear dummy types; then the model component gets our leaf model and its UseDoor box."""
    leaf = lf["name"]
    if leaf in REAR_TEMPLATE:
        tmpl = REAR_TEMPLATE[leaf]
        src = {pat: read_current(_leaf_rel(spec, tmpl, pat)) for pat in LEAF_FILES}
        remap = {own_guid(d): G[f"door/{spec.name}/{leaf}/{pat.format(leaf='')}"] for pat, d in src.items()}
        sl = body(src[LEAF_FILES[3]])
        remap[sl["ClosedPositionDummy"]], remap[sl["OpenPositionDummy"]] = types[leaf]
        files = {}
        for pat, d in src.items():
            t = json.dumps(d)
            for a, b in remap.items():
                t = t.replace(a, b)
            files[pat] = json.loads(t)
    else:
        files = {pat: read_mod(_leaf_rel(spec, leaf, pat)) for pat in LEAF_FILES}
    mc = body(files[LEAF_FILES[4]])
    mc["Model"] = "{G}" + model_guid
    (cx, cy, cz), (sx, sy, sz) = doors.use_box(spec, lf["model"])
    use = _dummy("DoorUse", USE_DOOR, (cx, cy, cz), (0, 0, 0, 1), (0, 0, 0), (sx, sy, sz))
    mc["Dummies"] = [{"Key": G[f"dummy/{spec.name}/{leaf}/DoorUse"], "Value": use}]
    sl = body(files[LEAF_FILES[3]])
    assert (sl["ClosedPositionDummy"], sl["OpenPositionDummy"]) == types[leaf], (spec.name, leaf)
    for pat, d in files.items():
        stage_def(_leaf_rel(spec, leaf, pat), d)
    return {"client_prefab": own_guid(files[LEAF_FILES[1]]), "slerp": own_guid(files[LEAF_FILES[3]]),
            "model_component": own_guid(files[LEAF_FILES[4]]), "model": model_guid, "types": types[leaf]}


def _stage_fan(spec, man, G):
    """The tray-fan rotor subpart (see _stage_rotor)."""
    return _stage_rotor(spec, man, G, doors.FAN, FAN_ANIM)


def _stage_rotor(spec, man, G, sub, anim):
    """A rotor subpart: model, dummy type, model component, InfiniteRotation (anim: its definition's fields), composite
    and prefab (the vanilla Subpart template pattern, as the KVM's). The racks' tray fans and the CRAC's fans."""
    sub_rel = f"{config.NAME}/{spec.name}/Subparts"
    model = _stage_subpart_model(spec, man, G, sub)
    dt = G[f"dummytype/{spec.name}/{sub}"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_DummyTypeDefinition.def",
              envelope("VRage:Keen.VRage.Core.Model.DummyTypeDefinitionObjectBuilder", {"Guid": dt}))
    mc = G[f"def/{spec.name}/{sub}/ModelComponent"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_ModelComponentDefinition.def",
              envelope("VRage:Keen.VRage.Game.Components.Models.ModelComponentDefinitionObjectBuilder",
                       {"Guid": mc, "Model": "{G}" + model, "Dummies": [],
                        "SubpartColliderOffset": {"X": 0, "Y": 0, "Z": 0}}))
    an = G[f"def/{spec.name}/{sub}/Animation"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_InfiniteRotationAnimationDefinition.def",
              envelope(f"{RIGID}InfiniteRotationAnimationDefinitionObjectBuilder", dict({"Guid": an}, **anim)))
    rk = G[f"key/{spec.name}/{sub}/RigidAnimation"]
    comp = G[f"def/{spec.name}/{sub}/Composite"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_Composite.partialdef", _partial(SUBPART_COMPOSITE_BASE, {
        "Guid": comp,
        "TagSlots": {"$DeltaEncoded": True, "RemovedKeys": [],
                     "ModifiedKeys": [{"$Key": "RigidAnimationComponent", "$Value": rk}]},
        "Components": {"$DeltaEncoded": True, "Keys": SUBPART_TEMPLATE_KEYS + [rk],
                       "Changed": [{"Kind": "Update", "Index": 2, "Value": {"Definition": mc}},
                                   {"Kind": "Insert", "Index": 5, "Value": {"Definition": an, "Type": T_INFROT}}],
                       "Removed": []}}, "VRage:Keen.VRage.DCS.Definitions.EntityCompositeDefinition"))
    pf = G[f"def/{spec.name}/{sub}/Prefab"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}.partialdef", _partial(SUBPART_PREFAB_BASE, {
        "Guid": pf, "_entity": {"Definition": comp, "ObjectBuilders": {
            "$DeltaEncoded": True, "Keys": SUBPART_TEMPLATE_KEYS + [rk],
            "Changed": [{"Kind": "Insert", "Index": 5, "Value": None}], "Removed": []}}},
        "VRage:Keen.VRage.Core.Game.Definitions.PrefabDefinition"))
    return {"model": model, "dummy_type": dt, "model_component": mc, "animation": an, "composite": comp,
            "prefab": pf, "rigid_key": rk}


def _stage_tray(spec, man, G, sub=None, children=None):
    """A static subpart (no animation; the fan tray, or the side panel RackSide): model, dummy type, model component,
    composite (a plain Copy of Subpart_Composite with our ModelComponent) and prefab. children: [(name, child entity)]
    nested under the prefab's HierarchyComponent (the tray's rotors, the Gyroscope50_Subparts pattern)."""
    sub = sub or doors.FAN_TRAY_SUB
    sub_rel = f"{config.NAME}/{spec.name}/Subparts"
    model = _stage_subpart_model(spec, man, G, sub)
    dt = G[f"dummytype/{spec.name}/{sub}"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_DummyTypeDefinition.def",
              envelope("VRage:Keen.VRage.Core.Model.DummyTypeDefinitionObjectBuilder", {"Guid": dt}))
    mc = G[f"def/{spec.name}/{sub}/ModelComponent"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_ModelComponentDefinition.def",
              envelope("VRage:Keen.VRage.Game.Components.Models.ModelComponentDefinitionObjectBuilder",
                       {"Guid": mc, "Model": "{G}" + model, "Dummies": [],
                        "SubpartColliderOffset": {"X": 0, "Y": 0, "Z": 0}}))
    comp = G[f"def/{spec.name}/{sub}/Composite"]
    stage_def(f"{sub_rel}/{spec.name}_{sub}_Composite.partialdef", _partial(SUBPART_COMPOSITE_BASE, {
        "Guid": comp,
        "Components": {"$DeltaEncoded": True, "Keys": list(SUBPART_TEMPLATE_KEYS),
                       "Changed": [{"Kind": "Update", "Index": 2, "Value": {"Definition": mc}}], "Removed": []}},
        "VRage:Keen.VRage.DCS.Definitions.EntityCompositeDefinition"))
    pf = G[f"def/{spec.name}/{sub}/Prefab"]
    ent = {"Definition": comp}
    if children:
        ent["ObjectBuilders"] = {"$DeltaEncoded": True, "Keys": list(SUBPART_TEMPLATE_KEYS), "Changed": [
            {"Kind": "Update", "Index": 0, "Value": {"$Type": HIERARCHY_OB, "Children": {
                "$DeltaEncoded": True, "Keys": [G[f"child/{spec.name}/{sub}/{n}"] for n, _ in children],
                "Changed": [{"Kind": "Insert", "Index": i, "Value": c} for i, (_, c) in enumerate(children)],
                "Removed": []}}}], "Removed": []}
    stage_def(f"{sub_rel}/{spec.name}_{sub}.partialdef", _partial(SUBPART_PREFAB_BASE, {
        "Guid": pf, "_entity": ent}, "VRage:Keen.VRage.Core.Game.Definitions.PrefabDefinition"))
    return {"model": model, "dummy_type": dt, "model_component": mc, "composite": comp, "prefab": pf}


# Rack subparts, Path A: a rack subpart spawned by ConditionalSubParts is a
# BOUND client prefab. The door's DoorPartsProvider (a SERVER definition) references the door racks' ConditionalSubParts,
# so BindingsBasedClientServerInfo's server walk follows its prefabs, stopping only at a binding's ClientPrefab
# (BindingsBasedClientServerInfo.cs:134-135, 222-230); an unbound one put render components on a "server" composite
# and fails the world load. The binding's server side is vanilla SlideDoorNarrow_250_LeftDoor's minus
# the door-segment components: a server composition of ModelComponent (the subpart's own model component),
# ChildTransform and Hierarchy (no client type: ConveyorGraphPostProcessor.ValidateClientTypes), and ONE server prefab
# on it (the prefab-by-composition map throws on two) whose Hierarchy Children is [] (its children would be walked as
# server). The open racks' entries are bound too (one pattern; nothing on their server side reaches them).
T_MODEL_COMPONENT = "VRage:Keen.VRage.Game.Components.Models.ModelComponent"
T_CHILD_TRANSFORM = "VRage:Keen.VRage.Core.Game.Components.ChildTransformComponent"
T_HIERARCHY = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponent"
HIERARCHY_OB = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder"
OB_CHILD_TRANSFORM = "VRage:Keen.VRage.Core.Game.Components.ChildTransformComponentObjectBuilder"
T_PREFAB = "VRage:Keen.VRage.Core.Game.Definitions.PrefabDefinitionObjectBuilder"
T_COMPOSITE = "VRage:Keen.VRage.DCS.Definitions.EntityCompositeDefinitionObjectBuilder"
T_BINDING = "VRage:Keen.VRage.Multiplayer.Data.PrefabBindingDefinitionObjectBuilder"


def bind_subpart(spec, sub, info, G):
    """The PrefabBinding of subpart sub's client prefab (info: _stage_tray's), with its server composition and server
    prefab (see above), staged as Subparts/<name>_<sub>_{ServerComposition,Server,Binding}.def. Returns the GUIDs."""
    sub_rel = f"{config.NAME}/{spec.name}/Subparts/{spec.name}_{sub}"
    k = {c: G[f"key/{spec.name}/{sub}/server/{c}"] for c in ("model", "transform", "hierarchy")}
    sc, sp, b = (G[f"def/{spec.name}/{sub}/{n}"] for n in ("ServerComposite", "ServerPrefab", "Binding"))
    stage_def(f"{sub_rel}_ServerComposition.def", envelope(T_COMPOSITE, {
        "Guid": sc,
        "TagSlots": [{"$Key": "ModelComponent", "$Value": k["model"]},
                     {"$Key": "ChildTransformComponent", "$Value": k["transform"]},
                     {"$Key": "HierarchyComponent", "$Value": k["hierarchy"]}],
        "Components": [{"Key": k["model"], "Value": {"Definition": info["model_component"], "Type": T_MODEL_COMPONENT}},
                       {"Key": k["transform"], "Value": {"Definition": None, "Type": T_CHILD_TRANSFORM}},
                       {"Key": k["hierarchy"], "Value": {"Definition": None, "Type": T_HIERARCHY}}]}))
    stage_def(f"{sub_rel}_Server.def", envelope(T_PREFAB, {"Guid": sp, "_entity": {
        "Definition": sc,
        "ObjectBuilders": [{"Key": k["model"], "Value": None},
                           {"Key": k["transform"], "Value": _child_transform((0.0, 0.0, 0.0))},
                           {"Key": k["hierarchy"], "Value": {"$Type": HIERARCHY_OB, "Children": []}}],
        "DebugName": "_Server"}}))
    stage_def(f"{sub_rel}_Binding.def", envelope(T_BINDING, {"Guid": b, "ServerComposite": sc,
                                                             "ClientPrefab": info["prefab"], "ReplicatedData": None}))
    return {"binding": b, "server_composite": sc, "server_prefab": sp, "client_prefab": info["prefab"],
            "dummy_type": info["dummy_type"]}


def _add_components(spec, side, new):
    """Add components (key, definition, type, tag slot, object builder) to the cloned side ("Server" / "Client")
    composition, each with its tag slot, and their object builders to that side's prefab (appended in the same
    order). Idempotent: re-staging over an installed copy refreshes the definition and the object builder."""
    cc_file = _block_files(spec, f"_{side}Composition")[0]
    cc = read_current(cc_file)
    cm = body(cc)
    keys = cm["Components"]["Keys"]
    for k, d, t, slot, _ in new:
        value = {"Definition": d, "Type": t}
        if k not in keys:
            keys.append(k)
        i = keys.index(k)
        cm["Components"]["Changed"] = sorted([c for c in cm["Components"]["Changed"] if c["Index"] != i] + [
            {"Kind": "Insert", "Index": i, "Value": value}], key=lambda c: c["Index"])
        mk = cm.setdefault("TagSlots", {"$DeltaEncoded": True, "RemovedKeys": [], "ModifiedKeys": []})["ModifiedKeys"]
        if not any(m["$Key"] == slot for m in mk):
            mk.append({"$Key": slot, "$Value": k})
    stage_def(cc_file, cc)
    cl_file = _block_files(spec, f"_{side}.partialdef")[0]
    cl = read_current(cl_file)
    ob = body(cl)["_entity"]["ObjectBuilders"]
    for k, *_, value in new:
        if k not in ob["Keys"]:
            ob["Keys"].append(k)
        i = ob["Keys"].index(k)
        ob["Changed"] = sorted([c for c in ob["Changed"] if c["Index"] != i] +
                               [{"Kind": "Insert", "Index": i, "Value": value}], key=lambda c: c["Index"])
    stage_def(cl_file, cl)
    return cc_file, cl_file


def _remove_client_components(spec, keys):
    """Undo _add_client_components for these component keys (Path B over an installed Path A package: the
    open racks' ConditionalSubPartsComponent): each key leaves the client composition (with its tag slot) and the
    client prefab's object builders, the later delta indices shifted down. Stages both files only when one changed."""
    out = []
    for side_file, path in ((_block_files(spec, "_ClientComposition")[0], ("Components",)),
                            (_block_files(spec, "_Client.partialdef")[0], ("_entity", "ObjectBuilders"))):
        d = read_current(side_file)
        node = body(d)
        for k in path:
            node = node[k]
        hit = False
        for key in keys:
            if key not in node["Keys"]:
                continue
            hit = True
            i = node["Keys"].index(key)
            node["Keys"].pop(i)
            node["Changed"] = [dict(c, Index=c["Index"] - (c["Index"] > i)) for c in node["Changed"] if c["Index"] != i]
            ts = body(d).get("TagSlots")
            if isinstance(ts, dict):
                ts["ModifiedKeys"] = [m for m in ts.get("ModifiedKeys", []) if m.get("$Value") != key]
        if hit:
            stage_def(side_file, d)
            out.append(side_file)
    return out


def _add_client_components(spec, new):
    """Add components (key, definition, type, tag slot) to the cloned client composition and a null object builder
    for each to the client prefab (the KVM's pattern). Idempotent."""
    return _add_components(spec, "Client", [(k, d, t, slot, None) for k, d, t, slot in new])


def _patch_body(spec, pattern, fn):
    files = _block_files(spec, pattern)
    if len(files) != 1:
        raise RuntimeError(f"{spec.name}: expected one {pattern}, found {files}")
    d = read_current(files[0])
    fn(body(d))
    stage_def(files[0], d)
    return files[0]


def patch_hum(spec, sound):
    """OnUseAudio (a vanilla loop while Working) on the BlockEffects definition the client composition uses: the
    clone's own copy when it has one, else a new Copy of the inherited definition bound in the composition."""
    cc_file = _block_files(spec, "_ClientComposition")[0]
    cc = read_current(cc_file)
    cm = body(cc)
    keys = cm["Components"]["Keys"]
    cloned = {own_guid(read_mod(f)): f for f in _block_files(spec, "BlockEffectsComponentDefinition")}
    for i, k in enumerate(keys):
        ch = [c for c in cm["Components"]["Changed"] if c["Index"] == i and isinstance(c.get("Value"), dict)]
        d = ch[0]["Value"].get("Definition") if ch else None
        if d in cloned:
            f = cloned[d]
            data = read_current(f)
            body(data)["OnUseAudio"] = sound
            stage_def(f, data)
            if not os.path.exists(stage_path(cc_file)):   # stage the binding composition too (unchanged)
                stage_def(cc_file, cc)
            return {"file": f, "definition": d, "key": k, "sound": sound}
    raise RuntimeError(f"{spec.name}: no cloned BlockEffects definition bound in the client composition")


# SE2 4.0.0.3151 turned the generic damage / destruction particle effects into ParticleEffectSetDefinitions (V1/V2/V3,
# weight 0.33 each; the 2.4 effect is now variant V1 under .../V1/) and vanilla BlockEffects point at the sets. Our
# cloned BlockEffects (cloned from 2.3/2.4 vanilla) still named the V1 effects; the user accepted the 4.0 vanilla
# damage bands, so we only swap the effect for its set, as the small vanilla blocks (Timer, Sensor,
# Buttons, EventController BlockEffects templates) do. Verified in the 4.0 SDK: each set's Effects list holds the V1
# GUID (System/Particles/Generic/{Smoke/SmokeSmall,Fire/FireSmall,Explosion/Regular/GridExplosions}_ParticleSet.def).
PARTICLE_SETS = {
    "068f3203-ac68-489a-b111-4021029eda2d": "d8cb4c53-5d1b-4aaa-9b56-71bb67ad1dd7",   # SmokeSmall -> SmokeSmall_ParticleSet
    "16b93a55-0a9d-453b-ad77-287d7ddd7e5c": "9056509a-00d5-4abd-a2ea-3a9707e2ef45",   # FireSmall -> FireSmall_ParticleSet
    "21e2b44f-a116-4a47-84eb-7450f2ad989c": "b41e3b65-0919-4ff9-95b0-72c0ddad7409",   # ExplosionGrid -> GridExplosions_ParticleSet
}


def _swap_particle_sets(node, swapped):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "ParticleEffect" and v in PARTICLE_SETS:
                node[k] = PARTICLE_SETS[v]
                swapped.append((v, node[k]))
            else:
                _swap_particle_sets(v, swapped)
    elif isinstance(node, list):
        for v in node:
            _swap_particle_sets(v, swapped)


def patch_particle_sets(spec):
    """Every cloned BlockEffects definition of the block: a V1 damage / death effect -> its 4.0 vanilla particle set
    (PARTICLE_SETS). Scales, keys and thresholds are kept (the 4.0 vanilla bands apply). Returns {file: swaps}; empty
    when there is nothing to swap: once installed (the mod's files already name the sets), or on a fresh clone from
    4.0 vanilla, which names no V1 effect. Run on the UPS only: the KVM's band is now 4.0
    ControlPanel25's own (patch_kvm_effects: ElectricalDamageSmall 617b0925 x0.3 below 0.99 instead of SmokeSmall),
    which names no set. Tests/test_ups.py pins the installed state."""
    out = {}
    for f in _block_files(spec, "BlockEffectsComponentDefinition"):
        data = read_current(f)
        swapped = []
        _swap_particle_sets(body(data), swapped)
        if swapped:
            stage_def(f, data)
            out[f] = swapped
    return out


# ------------------------------------------------------------------------------- damage effects
def patch_spark_effects(spec, G):
    """A spark block's (effects.spark_kind) cloned Structural BlockEffects Copy inserts the vanilla 4.0 spark band
    verbatim (effects.vanilla_band: CableStraight250's for the trays, CircuitBreaker's for the PDUs and the deco
    servers: 0 - 0.99, one Electrical effect on the ParticleEffects dummy), with stable delta keys
    (G "band/<name>/spark" and "band/<name>/spark/fx"). The Structural base (9be983e4) has no band to collide with.
    Idempotent (the delta is rebuilt whole). Returns {file, kind, band} or None for a block that does not spark."""
    import copy
    kind = effects.spark_kind(spec)
    if not kind:
        return None
    f, d = _effects_copy(spec)
    band = copy.deepcopy(effects.vanilla_band(kind))
    assert len(band["ParticleEffects"]) == 1, band
    band["ParticleEffects"][0]["Key"] = G[f"band/{spec.name}/spark/fx"]
    d["$Value"]["Manipulator"]["OnDamagedBlockParticleEffect"] = {
        "$DeltaEncoded": True, "Keys": [G[f"band/{spec.name}/spark"]],
        "Changed": [{"Kind": "Insert", "Index": 0, "Value": band}], "Removed": []}
    stage_def(f, d)
    return {"file": f, "kind": kind, "band": band}


def patch_spark_dummies(spec, dummies, man, G):
    """A spark block's ParticleEffects-type dummies follow its fracture zones (effects.zone_dummies).
    The cloned centre "ParticleEffects" keeps its delta key, name and the block-centre position (the one-shot death
    effect's origin: the first dummy of the type) and gains SupportingFracture = the zone holding the centre;
    a long block (effects.per_zone) gets one "ParticleEffects_<zone>" per other zone after it, at that zone's AABB
    centre (a tray's: its cables' box) and supported by it, so each section's sparks stop when it falls off.
    Idempotent (stable keys from asset_guids.json; stale ParticleEffects_<zone> entries dropped). No-op for a block
    that does not spark."""
    if not effects.spark_kind(spec):
        return
    keys, changed = dummies.get("Keys", []), dummies.get("Changed", [])
    assert all(c["Kind"] == "Insert" for c in changed) and len(keys) == len(changed), dummies
    rows = [(k, c["Value"]) for k, c in zip(keys, sorted(changed, key=lambda c: c["Index"]))
            if not (c["Value"].get("Name") or "").startswith("ParticleEffects_")]
    want = effects.zone_dummies(man["fractured"], man["shift"], effects.per_zone(spec),
                                prefer_role="hide" if spec.family == "tray" else None)   # on the cables
    (cname, cpos, czone), rest = want[0], want[1:]
    centre = [v for _, v in rows if v.get("Name") == cname and v.get("Type") == PARTICLE_EFFECTS_TYPE]
    if len(centre) != 1:
        raise RuntimeError(f"{spec.name}: expected one cloned centre {cname} dummy, found {len(centre)}")
    centre[0]["Transform"]["Transform"]["Position"] = dict(zip("XYZ", cpos))
    centre[0]["SupportingFracture"] = {"Id": czone}
    for name, pos, zid in rest:
        v = _dummy(name, PARTICLE_EFFECTS_TYPE, pos, (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))
        v["SupportingFracture"] = {"Id": zid}
        v["HighlightSection"] = None
        rows.append((G[f"dummy/{spec.name}/{name}"], v))
    dummies["Keys"] = [k for k, _ in rows]
    dummies["Changed"] = [{"Kind": "Insert", "Index": i, "Value": v} for i, (_, v) in enumerate(rows)]
    dummies["Removed"] = []


def patch_kvm_effects(spec):
    """The KVM's damage band is vanilla 4.0 ControlPanel25's (its clone source): the cloned
    BlockEffects' OnDamagedBlockParticleEffect delta = ControlPanel25's 4.0 one verbatim (band 0: upper 0.99,
    ElectricalDamageSmall x0.3 on the ParticleEffects dummy, the 2.4 key 92d61473 removed). It replaces the KVM's
    SmokeSmall set swap (patch_particle_sets). Every other key of the clone is kept. Idempotent."""
    import copy
    f, d = _effects_copy(spec)
    d["$Value"]["Manipulator"]["OnDamagedBlockParticleEffect"] = copy.deepcopy(effects.vanilla_effects("cp25"))
    stage_def(f, d)
    return f


def patch_programmable_effects(spec):
    """The Programmable (a functional blade, Functional fragility) gets the vanilla Timer BlockEffects
    template's three bands (sparks below 95 %, smoke 90 - 65 %, fire below 65 %; its death explosion and audio too),
    as DC_Srv_Timer has: its cloned Structural BlockEffects Copy is re-based onto effects.TIMER_EFFECTS, keeping its
    GUID (bound in the client composition) and every key. Idempotent. Returns the base."""
    f, d = _effects_copy(spec)
    d["$Value"]["BaseDefinition"] = effects.TIMER_EFFECTS
    stage_def(f, d)
    return effects.TIMER_EFFECTS


def patch_door_dummies(spec, dummies, G):
    """The door block model's dummies: effects at the block centre, the leaves' closed / open pairs on the hinge axes,
    the doorway detector over the door plane, the fan pivots; the vanilla frame UseDoor boxes (TerminalFront01 /
    TerminalBack01) are dropped: open, they would sit in front of the servers' own terminals."""
    ctx = _DOOR_CTX[spec.name]
    keys, changed = dummies.get("Keys", []), dummies.get("Changed", [])
    by_name = {c["Value"].get("Name"): (k, c["Value"]) for k, c in zip(keys, sorted(changed, key=lambda c: c["Index"]))}
    sh = doors.shift(spec)
    out = []
    for name in ("Particles", "ParticleDirection"):
        k, v = by_name[name]
        v["Transform"]["Transform"]["Position"] = {"X": sh[0], "Y": sh[1], "Z": sh[2]}
        v["SupportingFracture"] = None
        out.append((k, v))
    for name, lf, kind, pos, q, e in doors.dummies(spec):
        k = by_name.get(name, (None,))[0] or G[f"dummy/{spec.name}/{name}"]
        typ = ctx["types"][lf["name"]][0 if kind == "Closed" else 1]
        out.append((k, _dummy(name, typ, pos, q, e, (1, 1, 1))))
    k, v = by_name[DETECTOR]
    c, half = doors.detector_box(spec)
    out.append((k, _dummy(DETECTOR, v["Type"], c, (0, 0, 0, 1), (0, 0, 0), tuple(2 * h for h in half))))
    # (the side panels' and fan tray's spawn dummies follow: patch_rack_subpart_dummies; the rotors have none, they
    # are children of the tray's client prefab)
    dummies["Keys"] = [k for k, _ in out]
    dummies["Changed"] = [{"Kind": "Insert", "Index": i, "Value": v} for i, (_, v) in enumerate(out)]
    dummies["Removed"] = []


STRUCTURAL_CLIENT_KEYS = ["b7bf405c-71aa-46a1-a5ec-4c690f2ab7e3", "e58b8f69-45da-40d4-82b0-f1a82564a53a",
                          "786ef564-3cbf-4509-a58c-ad19243fffc1", "a1687822-b4c2-4bcb-961e-3e44fae3221d",
                          "d358358e-30b3-484a-b8b8-2e5568c7298b", "bc5652a0-1296-4040-adc3-a2b9c35d5afc",
                          "7a7762eb-c3ed-466b-b09c-336b5073251c", "1b938f02-30d8-4cc7-8fa7-df3ad5686048",
                          "8ebd0b91-0f3b-40e2-8f8f-251fed4012c0"]   # Templates/Blocks/Breakable/Structural_Client


def _rotor_children(spec, fan):
    """The fan rotors as Hierarchy children of the fan tray's client prefab: [(name, child entity)], each at its pivot
    relative to the tray's (game frame; the tray is not turned), with the Subpart template's object builders and its
    rigid animation key. ConditionalSubParts' spawn overwrites only the ROOT ChildTransform (OBsOfType is not
    recursive), so these offsets survive. Their InfiniteRotation takes its state from the
    closest parent IRigidAnimationController (ToggleRigidAnimationComponent.OnAddedToScene): the rack's
    FunctionalBlockAnimationController, i.e. they spin while the rack is Working."""
    t = doors.to_game(doors.fan_tray_point(spec), spec)
    out = []
    for i, p in enumerate(doors.fan_points(spec)):
        pos = tuple(round(a - b, 6) for a, b in zip(doors.to_game(p, spec), t))
        name = f"{doors.FAN}{i + 1}"
        out.append((name, {"$ObjectId": i, "Definition": fan["composite"],
                           "ObjectBuilders": [{"Key": SUBPART_TEMPLATE_KEYS[0],
                                               "Value": {"$Type": HIERARCHY_OB, "Children": []}},
                                              {"Key": SUBPART_TEMPLATE_KEYS[1], "Value": _child_transform(pos)}]
                           + [{"Key": k, "Value": None} for k in SUBPART_TEMPLATE_KEYS[2:]]
                           + [{"Key": fan["rigid_key"], "Value": None}],
                           "DebugName": name}))
    return out


HIERARCHY_KEY = STRUCTURAL_CLIENT_KEYS[1]   # the HierarchyComponent's key in the block client prefabs (door too)
SIDE_CHILDREN = rack_side.SIDES   # the one side model: RackSideR at the block origin, RackSideL turned 180 deg


def rack_subpart_dummies(spec, ctx):
    """[(dummy name, dummy type, game position, yaw)] of a rack's ConditionalSubParts spawn points: the side panel
    twice (one dummy type, two dummies: CollectSubparts spawns one deep clone per dummy) and, on a full rack, the
    fan tray at its pivot."""
    out = [(name, ctx["side"]["dummy_type"], doors.to_game((0.0, 0.0, 0.0), spec), yaw) for name, yaw in SIDE_CHILDREN]
    if ctx.get("tray"):
        out.append((doors.FAN_TRAY_SUB, ctx["tray"]["dummy_type"], doors.to_game(doors.fan_tray_point(spec), spec), 0.0))
    return out


def patch_rack_subpart_dummies(spec, dummies, G):
    """The rack's subpart spawn dummies (rack_subpart_dummies) in its BlockModelDefinition, unsupported (the spawn
    needs Functional, which a dead critical zone already ends). Idempotent (stable keys, replaced by name)."""
    for name, typ, pos, yaw in rack_subpart_dummies(spec, _DOOR_CTX[spec.name]):
        v = _dummy(name, typ, pos, doors.quat_yaw(yaw) if yaw else (0, 0, 0, 1), (0, yaw, 0), (1, 1, 1))
        v["HighlightSection"] = None
        _put_dummy(spec, dummies, G, v)


def clear_rack_static_children(spec):
    """Remove the static client-prefab children (fan tray, side panels, rotors) an older build put on the
    rack's client prefab: they are ConditionalSubParts entries now. The door racks drop the HierarchyComponent update
    (the cloned door template's own, empty, applies); the open racks keep the structural template's key list with no
    change."""
    f = _block_files(spec, "_Client.partialdef")[0]
    d = read_current(f)
    ent = body(d)["_entity"]
    if doors.has_doors(spec):
        ob = ent["ObjectBuilders"]
        if ob["Keys"][1] != HIERARCHY_KEY:
            raise RuntimeError(f"{spec.name}: client prefab key 1 is not the HierarchyComponent: {ob['Keys'][1]}")
        ob["Changed"] = [c for c in ob["Changed"] if not (c["Kind"] == "Update" and c["Index"] == 1)]
    else:
        ent["ObjectBuilders"] = {"$DeltaEncoded": True, "Keys": list(STRUCTURAL_CLIENT_KEYS), "Changed": [],
                                 "Removed": []}
    stage_def(f, d)
    return f


# Path B (config.RACK_PATH "B", the fallback if Path A fails the world load): the side panels, the fan
# tray and its rotors are static children of the rack's CLIENT prefab (the earlier structure):
# always present whatever the build state, no stand-ins (fracture.rack_standins("B") is empty),
# no bindings, nothing the server walk can reach. On/Off stays on every rack: the rotors follow
# Working through the rack's FunctionalBlockAnimationController, the closest parent controller.
def _client_child(info, oid, name, pos, yaw=0.0, rigid_key=None):
    """A subpart as a client-prefab child at pos (game frame), turned yaw deg about game +Y: the Subpart template's
    object builders (plus the rotor's rigid animation key)."""
    return {"$ObjectId": oid, "Definition": info["composite"],
            "ObjectBuilders": [{"Key": SUBPART_TEMPLATE_KEYS[0], "Value": {"$Type": HIERARCHY_OB, "Children": []}},
                               {"Key": SUBPART_TEMPLATE_KEYS[1], "Value": _child_transform(pos, yaw)}]
            + [{"Key": k, "Value": None} for k in SUBPART_TEMPLATE_KEYS[2:]]
            + ([{"Key": rigid_key, "Value": None}] if rigid_key else []),
            "DebugName": name}


def static_children(spec, ctx):
    """[(child name, child entity)] of a Path B rack's client prefab: the fan rotors at their pivots and the fan tray
    (full racks), and the side panel model twice (rack_side.SIDES)."""
    out = []
    if ctx.get("fan"):
        for i, p in enumerate(doors.fan_points(spec)):
            name = f"{doors.FAN}{i + 1}"
            out.append((name, _client_child(ctx["fan"], len(out), name, doors.to_game(p, spec),
                                            rigid_key=ctx["fan"]["rigid_key"])))
    if ctx.get("tray"):
        out.append((doors.FAN_TRAY_SUB, _client_child(ctx["tray"], len(out), doors.FAN_TRAY_SUB,
                                                      doors.to_game(doors.fan_tray_point(spec), spec))))
    for name, yaw in SIDE_CHILDREN:
        out.append((name, _client_child(ctx["side"], len(out), name, doors.to_game((0.0, 0.0, 0.0), spec), yaw)))
    return out


def set_rack_static_children(spec, ctx, G):
    """Path B: the client prefab's HierarchyComponent (key index 1 on both the door and the structural template)
    lists static_children; the door racks keep their other object-builder updates, the open racks get the structural
    template's key list."""
    f = _block_files(spec, "_Client.partialdef")[0]
    d = read_current(f)
    ent = body(d)["_entity"]
    kids = static_children(spec, ctx)
    upd = {"Kind": "Update", "Index": 1, "Value": {"$Type": HIERARCHY_OB, "Children": {
        "$DeltaEncoded": True, "Keys": [G[f"child/{spec.name}/{n}"] for n, _ in kids],
        "Changed": [{"Kind": "Insert", "Index": i, "Value": c} for i, (_, c) in enumerate(kids)], "Removed": []}}}
    if doors.has_doors(spec):
        ob = ent["ObjectBuilders"]
        if ob["Keys"][1] != HIERARCHY_KEY:
            raise RuntimeError(f"{spec.name}: client prefab key 1 is not the HierarchyComponent: {ob['Keys'][1]}")
        ob["Changed"] = [upd] + [c for c in ob["Changed"] if not (c["Kind"] == "Update" and c["Index"] == 1)]
    else:
        ent["ObjectBuilders"] = {"$DeltaEncoded": True, "Keys": list(STRUCTURAL_CLIENT_KEYS), "Changed": [upd],
                                 "Removed": []}
    stage_def(f, d)
    return f


def stage_rack_subparts(spec, man, models, G, bd=None):
    """Everything a built rack gets (see the section comment; config.RACK_PATH picks the subpart
    path, Path B above). bd: the block definition being staged (the open racks' powerable chain patches it). Returns a
    summary; the subparts' dummy types are kept for patch_rack_subpart_dummies (called from patch_model_def)."""
    path = config.RACK_PATH
    if path not in ("A", "B"):
        raise ValueError(f"config.RACK_PATH must be 'A' or 'B', not {path!r}")
    out = {"path": path}
    ctx = _DOOR_CTX.setdefault(spec.name, {})
    ctx.pop("tray", None)
    if doors.fan_points(spec):
        ctx["fan"] = out["fan"] = _stage_fan(spec, man, G)
        ctx["tray"] = out["tray"] = _stage_tray(spec, man, G, children=(
            _rotor_children(spec, ctx["fan"]) if path == "A" else None))
    ctx["side"] = out["side"] = _stage_tray(spec, man, G, rack_side.SIDE_SUB)
    subs, hide = {}, []
    if path == "A":
        parts = [rack_side.SIDE_SUB] + ([doors.FAN_TRAY_SUB] if ctx.get("tray") else [])
        infos = {rack_side.SIDE_SUB: ctx["side"], doors.FAN_TRAY_SUB: ctx.get("tray")}
        out["bound"] = {p: bind_subpart(spec, p, infos[p], G) for p in parts}
        subs = {b["dummy_type"]: b["client_prefab"] for b in out["bound"].values()}
        hide = hide_when_active(spec, man, G)
        out["client_prefab"] = clear_rack_static_children(spec)
    else:
        out["client_prefab"] = set_rack_static_children(spec, ctx, G)
    if not doors.has_doors(spec):
        # ConditionalSubPartsComponent spawns on Functional, which needs a FunctionalBlockComponent: the
        # powerable chain from the structural CubeBlockComponent (as the Programmable), Fragility kept Structural; the
        # component and its definition on the client side only (vanilla Gyroscope50_ClientComposition), plus the
        # animation controller on a full rack, so its rotors follow Working (On/Off) as the door racks' do. Path B
        # keeps the chain and the controller (On/Off on every rack) and has no ConditionalSubParts.
        if bd is None:
            raise RuntimeError(f"{spec.name}: the open rack's functional chain needs its block definition")
        out["onoff"] = onto_powerable(spec, bd, STRUCTURAL_KEY, keep=STRUCTURAL_DEF_VALUES)
        body(bd)["Fragility"] = FRAGILITY["Structural"]
        new = []
        if path == "A":
            cs = G[f"def/{spec.name}/ConditionalSubParts"]
            rel = f"{config.NAME}/{spec.name}/Subparts/{spec.name}_ConditionalSubPartsDefinition.def"
            stage_def(rel, envelope(
                "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Effects.ConditionalSubPartsDefinitionObjectBuilder",
                {"Guid": cs, "SubParts": subs, "MeshPartsToHideWhenActive": hide}, B_GAME))
            out["conditional_subparts"] = rel
            new.append((G[f"key/{spec.name}/condsub"], cs, T_CONDSUB, "ConditionalSubPartsComponent"))
        else:   # (an installed Path A package's ConditionalSubPartsComponent goes)
            out["removed_components"] = _remove_client_components(spec, [G[f"key/{spec.name}/condsub"]])
        if ctx.get("fan"):
            new.append((G[f"key/{spec.name}/animctl"], None, T_ANIMCTL, "FunctionalBlockAnimationControllerComponent"))
        if new:
            out["client_components"] = _add_client_components(spec, new)
        return out
    types = ctx["types"] = _door_dummy_types(spec, G)
    leaf_models = {m: _stage_subpart_model(spec, man, G, m) for m in doors.leaf_models(spec)}
    out["leaves"] = {lf["name"]: _stage_leaf(spec, lf, leaf_models[lf["model"]], types, G) for lf in doors.leaves(spec)}
    # ConditionalSubParts: each leaf's closed dummy type -> its client prefab, and (Path A) the bound side / tray
    # entries; the rotors are children of the tray's client prefab (_rotor_children), or (Path B) of the
    # rack's (static_children)
    subs.update({v["types"][0]: v["client_prefab"] for v in out["leaves"].values()})
    if ctx.get("fan"):
        out["fan_controller"] = _add_client_components(
            spec, [(G[f"key/{spec.name}/animctl"], None, T_ANIMCTL, "FunctionalBlockAnimationControllerComponent")])
    out["conditional_subparts"] = _patch_body(spec, "_Client_ConditionalSubPartsDefinition",
                                              lambda v: v.update(SubParts=subs, MeshPartsToHideWhenActive=hide))
    green = mat_guid("EmissiveGreen")
    lamp_parts = ["EmissiveOff"] + sorted(p for p in man["fractured"]["parts"] if p.endswith("-EmissiveOff"))

    def swapper(v):
        v["WorkingReplacementModels"] = ["{G}" + models["NonFractured"], "{G}" + models["Fractured"]]
        v["WorkingReplacementsMeshParts"] = [{"$Key": p, "$Value": green} for p in lamp_parts]
    out["swapper"] = _patch_body(spec, "_BlockMaterialSwapperDefinition", swapper)
    out["breakable"] = _patch_body(spec, "_BreakableBlockDefinition", lambda v: v.update(CriticalFractures={
        "$DeltaEncoded": True, "Removed": [], "Added": [{"Id": f} for f in critical_fractures(man)]}))
    c, half = doors.detector_box(spec)
    out["detector"] = _patch_body(spec, "_DoorwayObstacleEntityDetectorDefinition", lambda v: v.update(
        QueryHalfExtents=dict(zip("XYZ", half))))
    out["door_server"] = _patch_body(spec, "_DoorServerDefinition",
                                     lambda v: v.update(OpeningDuration=int(round(DM.DOOR_SECONDS * 1e7))))
    out["hum"] = patch_hum(spec, HUM_RACK)
    return out


# ------------------------------------------------------------------------- containment doors
# The containment doors are SlidingDoorNarrow250 clones like the door racks (DoorServer / DoorClient /
# DoorBlockCollider / DoorAudio / ConditionalSubParts kept as cloned), generalised from stage_rack_subparts: the two
# cloned leaves (LeftDoor / RightDoor, the clone's own spawn = Closed and Open dummy types) get our leaf models WITH
# a collision model (the vanilla DoorBlockColliderDefinition.CollectDoorLeavesColliders takes each door subpart prefab
# that has a DoorSegmentTransformSLERP and a ModelComponent whose model has a collider, and places that collider at
# the block model's ClosedPositionDummy; DoorBlockColliderComponent compounds them with the frame while the door is
# Closed and Functional), Closed / Open dummies that differ by a pure translation (the vanilla slide), a DoorUse box
# on each leaf, the doorway detector resized to the opening, OpeningDuration 1.0 s, PCU 150 and mounts All.
def door_patch(spec, bd):
    """A containment door: bd = its block definition being staged (patched in place). PCU 150 (the
    clone's template value, stated explicitly), mount directions All (the model's hints decide where). The clone keeps
    the door's breakable chain (four fracture zones). Idempotent. Returns {pcu, mounts}."""
    from . import contain
    m = body(bd)
    m["PCU"] = contain.DOOR_PCU
    m["MountPointGeneratorSettings"] = {"Directions": contain.DOOR_MOUNTS}
    return {"pcu": contain.DOOR_PCU, "mounts": contain.DOOR_MOUNTS}


def _contain_types(spec):
    """{leaf: (closed type, open type)}: the clone's own dummy types (vanilla LeftDoor* / RightDoor*)."""
    from . import contain
    out = {}
    for lf in contain.door_leaves(spec):
        out[lf.name] = tuple(own_guid(read_mod(f"{config.NAME}/{spec.name}/{lf.name}{k}Dummy.def"))
                             for k in ("Closed", "Open"))
    return out


def patch_contain_door_dummies(spec, dummies, G, supporting=None):
    """The containment door's block-model dummies: effects at the block centre, each leaf's Closed / Open pair (a pure
    x translation, identity orientation), the doorway detector over the opening; the vanilla frame UseDoor boxes
    (TerminalFront01 / TerminalBack01) dropped (the leaves carry DoorUse boxes). supporting: export.json's
    {dummy: zone} (fracture._door: each Closed dummy -> the lintel)."""
    supporting = supporting or {}
    from . import contain
    ctx = _DOOR_CTX[spec.name]
    keys, changed = dummies.get("Keys", []), dummies.get("Changed", [])
    by_name = {c["Value"].get("Name"): (k, c["Value"]) for k, c in zip(keys, sorted(changed, key=lambda c: c["Index"]))}
    sh = doors.shift(spec)
    out = []
    for name in ("Particles", "ParticleDirection"):
        k, v = by_name[name]
        v["Transform"]["Transform"]["Position"] = {"X": sh[0], "Y": sh[1], "Z": sh[2]}
        v["SupportingFracture"] = None
        out.append((k, v))
    for lf in contain.door_leaves(spec):
        for i, (kind, tr) in enumerate((("Closed", lf.closed), ("Open", lf.open))):
            name = lf.name + kind
            k = by_name.get(name, (None,))[0] or G[f"dummy/{spec.name}/{name}"]
            v = _dummy(name, ctx["types"][lf.name][i], tr.position, tr.orientation, (0, 0, 0), (1, 1, 1))
            if kind == "Closed":   # the closed leaf hangs from the lintel's track: it goes when the lintel goes
                if name not in supporting:
                    raise RuntimeError(f"{spec.name}: {name} has no SupportingFracture in the fracture plan")
                v["SupportingFracture"] = {"Id": supporting[name]}
            out.append((k, v))
    k, v = by_name[DETECTOR]
    c, half = contain.detector_box(spec)
    out.append((k, _dummy(DETECTOR, v["Type"], c, (0, 0, 0, 1), (0, 0, 0), tuple(2 * h for h in half))))
    dummies["Keys"] = [k for k, _ in out]
    dummies["Changed"] = [{"Kind": "Insert", "Index": i, "Value": v} for i, (_, v) in enumerate(out)]
    dummies["Removed"] = []


def _stage_contain_leaf(spec, lf, model_guid, types, G):
    """The leaf's seven cloned subpart definitions; the model component gets our leaf model (with its collision) and
    a DoorUse box over the leaf."""
    from . import contain
    files = {pat: read_mod(_leaf_rel(spec, lf.name, pat)) for pat in LEAF_FILES}
    mc = body(files[LEAF_FILES[4]])
    mc["Model"] = "{G}" + model_guid
    (cx, cy, cz), (sx, sy, sz) = contain.use_box(spec)
    use = _dummy("DoorUse", USE_DOOR, (cx, cy, cz), (0, 0, 0, 1), (0, 0, 0), (sx, sy, sz))
    mc["Dummies"] = [{"Key": G[f"dummy/{spec.name}/{lf.name}/DoorUse"], "Value": use}]
    sl = body(files[LEAF_FILES[3]])
    if (sl["ClosedPositionDummy"], sl["OpenPositionDummy"]) != types[lf.name]:
        raise RuntimeError(f"{spec.name} {lf.name}: SLERP dummies {sl} are not the clone's {types[lf.name]}")
    for pat, d in files.items():
        stage_def(_leaf_rel(spec, lf.name, pat), d)
    return {"client_prefab": own_guid(files[LEAF_FILES[1]]), "slerp": own_guid(files[LEAF_FILES[3]]),
            "model_component": own_guid(files[LEAF_FILES[4]]), "model": model_guid, "types": types[lf.name]}


def stage_contain_door(spec, man, models, G):
    """Everything a built containment door gets (see the section comment). Returns a summary; the dummy
    types are kept for patch_contain_door_dummies (called from patch_model_def)."""
    from . import contain
    out = {}
    ctx = _DOOR_CTX.setdefault(spec.name, {})
    types = ctx["types"] = _contain_types(spec)
    leaf_models = {m: _stage_subpart_model(spec, man, G, m) for m in contain.LEAF_MODELS}
    out["leaves"] = {lf.name: _stage_contain_leaf(spec, lf, leaf_models[lf.model], types, G)
                     for lf in contain.door_leaves(spec)}
    subs = {v["types"][0]: v["client_prefab"] for v in out["leaves"].values()}
    out["conditional_subparts"] = _patch_body(spec, "_Client_ConditionalSubPartsDefinition",
                                              lambda v: v.update(SubParts=subs, MeshPartsToHideWhenActive=[]))

    def swapper(v):   # no status lamp on the door: the swapper acts on our models with nothing to swap
        v["WorkingReplacementModels"] = ["{G}" + models[k] for k in ("NonFractured", "Fractured", "Damaged")
                                         if k in models]
        v["WorkingReplacementsMeshParts"] = []
    out["swapper"] = _patch_body(spec, "_BlockMaterialSwapperDefinition", swapper)
    crit = man["fractured"].get("critical", [])   # fracture._door: the frame round the opening; not the threshold
    zones = {z["id"] for z in man["fractured"]["zones"]}
    if not set(crit) <= zones:
        raise RuntimeError(f"{spec.name}: critical fractures {crit} not all exported zones {sorted(zones)}")
    out["critical_fractures"] = crit
    out["breakable"] = _patch_body(spec, "_BreakableBlockDefinition", lambda v: v.update(CriticalFractures={
        "$DeltaEncoded": True, "Removed": [], "Added": [{"Id": f} for f in crit]}))
    c, half = contain.detector_box(spec)
    out["detector"] = _patch_body(spec, "_DoorwayObstacleEntityDetectorDefinition", lambda v: v.update(
        QueryHalfExtents=dict(zip("XYZ", half))))
    out["door_server"] = _patch_body(spec, "_DoorServerDefinition",
                                     lambda v: v.update(OpeningDuration=int(round(contain.DOOR_SECONDS * 1e7))))
    return out


# ------------------------------------------------------------------------- build-menu grouping and costs
# dc/menu.py has the G-screen evidence: one "Data Center" subcategory (Automation category) with one BlockGroup per
# family (racks, servers), one per cable density plus the tray supports, and the room groups; multi-size kinds
# (42U + 24U racks, the two straights, the three rod lengths) are one kind each. dc/recipes.py has the cost rule and
# the game's mass formula.
# ------------------------------------------------------------------------------------- the CRAC
# The in-row cooler is a Gyroscope250 clone with the gyroscope stripped (a cooler must not apply 44 MN m of torque):
# the template-inserted GyroscopeComponent (key GYRO_KEY) is Removed from the cloned server composition and
# server prefab, with its tag slot (the KVM On/Off's delta form), and the clone's GyroscopeDefinition file is dropped
# (clone.DROP); nothing else references either. Everything else of the powered chain stays as cloned: the
# PowerableBlockDefinition (ConsumedResource Amount 25, priority 6: a real load) and its component (terminal On/Off,
# Working), the FunctionalBlockAnimationController (server and client), ConditionalSubParts (now spawning the CracFan
# rotor at the three CracFan dummies; the vanilla gimbal prefab and its static-copy hide list are unbound), the
# BlockMaterialSwapper (our RUN lamp's EmissiveOff slot lit EmissiveGreen while Working) and the BlockEffects hum
# (vanilla GyroscopeMID loop while Working).
GYRO_KEY = "c232d09e-aa3a-490a-85e2-caa6094b4fa6"     # Templates/Blocks/Breakable/Gyroscopes_ServerComposition, index 5
GYRO_SLOT = "GyroscopeComponent"
T_GYRO_DEF = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.Movement.GyroscopeDefinition"


def crac_fan_anim():
    """The CracFan InfiniteRotation: about game +Z (the block's forward axis; Blender -y), 600 deg/s, a 2 s linear soft
    start and a 4 s coast (dc/crac.py FAN_*)."""
    from . import crac
    return {"RotationAxis": dict(zip("XYZ", crac.FAN_AXIS)), "AngularSpeed": crac.FAN_DEG_S,
            "AngularSpeedup": crac.FAN_SPEEDUP, "AngularSlowdown": crac.FAN_SLOWDOWN}


def crac_patch(spec, bd):
    """The CRAC's definitions: bd = its block definition being staged (patched in place): PCU 30 (the
    template's, stated), mount directions All (the model's hints decide, as the racks); the PowerableBlockDefinition's
    ConsumedResource is the clone's (Amount 25) and is checked, not changed. Strips the GyroscopeComponent from the
    cloned server composition (key Removed, its Update dropped, the later Changed indices shifted; tag slot
    GyroscopeComponent RemovedKeys) and from the server prefab's ObjectBuilders (key Removed). Idempotent.
    Returns {pcu, mounts, consumed, composition, prefab}."""
    from . import crac
    m = body(bd)
    if (m.get("ConsumedResource") or {}).get("Amount") != 25:
        raise RuntimeError(f"{spec.name}: the cloned PowerableBlockDefinition does not draw 25: {m.get('ConsumedResource')}")
    m["PCU"] = crac.PCU
    m["MountPointGeneratorSettings"] = {"Directions": crac.MOUNTS}
    out = {"pcu": crac.PCU, "mounts": crac.MOUNTS, "consumed": m["ConsumedResource"]}
    f = _block_files(spec, "_ServerComposition")
    if len(f) != 1:
        raise RuntimeError(f"{spec.name}: expected one server composition, found {f}")
    d = read_current(f[0])
    c = body(d)
    _drop_key(c["Components"], GYRO_KEY)
    ts = c.setdefault("TagSlots", {"$DeltaEncoded": True, "RemovedKeys": [], "ModifiedKeys": []})
    ts["ModifiedKeys"] = [k for k in ts.get("ModifiedKeys", []) if k["$Value"] != GYRO_KEY]
    if GYRO_SLOT not in ts.setdefault("RemovedKeys", []):
        ts["RemovedKeys"].append(GYRO_SLOT)
    stage_def(f[0], d)
    out["composition"] = f[0]
    f = _block_files(spec, "_Server.partialdef")
    if len(f) != 1:
        raise RuntimeError(f"{spec.name}: expected one server prefab, found {f}")
    d = read_current(f[0])
    _drop_key(body(d)["_entity"]["ObjectBuilders"], GYRO_KEY)
    stage_def(f[0], d)
    out["prefab"] = f[0]
    return out


def stage_crac(spec, man, models, G):
    """The CRAC's subpart and client definitions: the CracFan rotor (model, dummy type, model component, its
    InfiniteRotation, composite, prefab), the cloned ConditionalSubParts definition pointed at it (the CracFan dummy
    type -> the rotor prefab; MeshPartsToHideWhenActive: the three parked fans baked into our Fractured / Damaged
    models (the clone's list named vanilla Fracture15 parts), shown while the CRAC is not
    Functional (under construction, a dead fan section) and hidden while the rotors spin) and the cloned
    BlockMaterialSwapper pointed at our models' RUN lamp (EmissiveOff and every Fracture_NN_Hide-EmissiveOff part ->
    EmissiveGreen while Working; the Damaged model maps its lamps to EmissiveOffBroken and is not swapped).
    The dummy type is kept for patch_crac_dummies (called from patch_model_def). Returns a summary."""
    from . import crac
    ctx = _DOOR_CTX.setdefault(spec.name, {})
    fan = ctx["fan"] = _stage_rotor(spec, man, G, crac.FAN, crac_fan_anim())
    out = {"fan": fan}
    out["conditional_subparts"] = _patch_body(spec, "SubParts.def", lambda v: v.update(
        SubParts={fan["dummy_type"]: fan["prefab"]}, MeshPartsToHideWhenActive=hide_when_active(spec, man, G)))
    green = mat_guid("EmissiveGreen")
    lamp_parts = [crac.LAMP] + sorted(p for p in man["fractured"]["parts"] if p.endswith("-" + crac.LAMP))

    def swapper(v):
        v["WorkingReplacementModels"] = ["{G}" + models["NonFractured"], "{G}" + models["Fractured"]]
        v["WorkingReplacementsMeshParts"] = [{"$Key": p, "$Value": green} for p in lamp_parts]
    out["swapper"] = _patch_body(spec, "_BlockMaterialSwapperDefinition", swapper)
    out["lamp_parts"] = lamp_parts
    # the service ports' dummy type, our own and inert (no component reads it: nothing snaps, no mount);
    # to turn the ports on later, their dummies take vanilla's UseConveyor type instead (CRAC_PORT_TYPE_ON)
    pt = ctx["port_type"] = G[f"dummytype/{spec.name}/{CRAC_PORT_TYPE}"]
    stage_def(f"{config.NAME}/{spec.name}/{spec.name}_{CRAC_PORT_TYPE}_DummyTypeDefinition.def",
              envelope("VRage:Keen.VRage.Core.Model.DummyTypeDefinitionObjectBuilder", {"Guid": pt}))
    out["port_dummy_type"] = pt
    out["hum"] = patch_hum(spec, HUM_CRAC)
    return out


def patch_crac_dummies(spec, dummies, G, supporting=None):
    """The CRAC model's dummies, rebuilt: the clone's terminal (TerminalFront01: its key, type and name kept) on our
    controller display, supported by the controller zone; the effects origin (Particles) at the block centre; the
    vanilla RotatingSubpart (the gimbal spawn point) replaced by CracFan1..3 at the rotor pivots (our CracFan dummy
    type), each supported by its fan section."""
    from . import crac
    sup = supporting or {}
    ctx = _DOOR_CTX[spec.name]
    keys, changed = dummies.get("Keys", []), dummies.get("Changed", [])
    by_name = {c["Value"].get("Name"): (k, c["Value"]) for k, c in zip(keys, sorted(changed, key=lambda c: c["Index"]))}
    out = []
    k, v = by_name[crac.TERMINAL_DUMMY]
    x, y, z = crac.TERMINAL
    sx, sz, sy = crac.TERMINAL_SCALE
    t = _dummy(crac.TERMINAL_DUMMY, v["Type"], doors.to_game((x, y, z - crac.H / 2), spec), (0, 0, 0, 1), (0, 0, 0),
               (sx, sz, sy))
    t["SupportingFracture"] = {"Id": sup[crac.TERMINAL_DUMMY]} if sup.get(crac.TERMINAL_DUMMY) else None
    out.append((k, t))
    k, v = by_name["Particles"]
    out.append((k, _dummy("Particles", v["Type"], doors.shift(spec), (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))))
    for i, p in enumerate(crac.fan_points(spec), 1):
        name = f"{crac.FAN}{i}"
        d = _dummy(name, ctx["fan"]["dummy_type"], doors.to_game(p, spec), (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))
        d["SupportingFracture"] = {"Id": sup[name]} if sup.get(name) else None
        out.append((by_name.get(name, (None,))[0] or G[f"dummy/{spec.name}/{name}"], d))
    # the O2 / coolant service ports: on the rear cell face (game +Z = Backward), turned like vanilla's
    # ConveyorBack (180 deg about Y: the dummy's +Z points into the block), vanilla's small-port scale
    for name, p in crac.port_points(spec).items():
        d = _dummy(name, ctx["port_type"], doors.to_game(p, spec), (0, 1, 0, 0), (0, 180, 0), crac.PORT_DUMMY_SCALE)
        d["SupportingFracture"] = {"Id": sup[name]} if sup.get(name) else None
        out.append((by_name.get(name, (None,))[0] or G[f"dummy/{spec.name}/{name}"], d))
    dummies["Keys"] = [k for k, _ in out]
    dummies["Changed"] = [{"Kind": "Insert", "Index": i, "Value": v} for i, (_, v) in enumerate(out)]
    dummies["Removed"] = []


T_SUBCATEGORY = "Game2:Keen.Game2.Simulation.StreamedUI.Categories.SubcategoryDefinitionObjectBuilder"
T_BLOCKGROUP = "Game2:Keen.Game2.Simulation.StreamedUI.Categories.BlockGroupDefinitionObjectBuilder"
T_RECIPE = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.CubeBlockRecipeDefinitionObjectBuilder"


def menu_guids(G):
    return {"subcategory": G["def/menu/subcategory"],
            "groups": {g: G[f"def/menu/group/{g}"] for g in menu.GROUPS}}


def patch_kind(spec, info, ids, G):
    """The block's cloned BlockKind: a kind owner joins its menu group (menu.group; OrderingPriority = menu order) and
    leaves the cloned vanilla ones (the trays' Structural > Walls and Trusses tiles); a block that is a further size
    of another block's kind (24U racks, 0.5 m straights, 0.25 / 2.0 m rods) leaves its own clone kind inert: no
    groups, priority 0, no blocks (the group insertion skips a kind without blocks). The room
    pieces too: their cloned vanilla tiles (Catwalks, Gyroscopes, Doors, Deck Panels, LCDs, wall inserts) are left."""
    kind = read_mod(info["kind_file"])
    k = body(kind)
    if menu.owns_kind(spec):
        k["Name"], k["Description"] = menu.kind_text(spec)
        k["OrderingPriority"] = menu.priority(spec)
        k["BlockGroups"] = [{"Key": G[f"key/{spec.name}/kind_group"], "Value": ids["groups"][menu.group(spec)]}]
    else:
        k["Name"], k["Description"] = names.NAMES[spec.name]
        k["OrderingPriority"] = 0
        k["BlockGroups"] = []
    stage_def(info["kind_file"], kind)
    return {"guid": k["Guid"], "name": k["Name"], "owner": menu.owns_kind(spec), "groups": len(k["BlockGroups"])}


def stage_menu(ids, G):
    """The subcategory and its groups (vanilla formats: UI/Screens/GScreen/*), tile order = menu.GROUPS Order."""
    sub = envelope(T_SUBCATEGORY, {"Guid": ids["subcategory"], "Name": menu.SUBCATEGORY["name"],
                                   "Tooltip": menu.SUBCATEGORY["tooltip"], "Order": 0,
                                   "Categories": [{"Key": G["key/menu/subcategory_category"],
                                                   "Value": menu.AUTOMATION_CATEGORY}]}, B_GAME)
    stage_def(menu.SUBCATEGORY["file"], sub)
    out = {"subcategory": ids["subcategory"], "groups": {}}
    for fam, g in menu.GROUPS.items():
        grp = envelope(T_BLOCKGROUP, {"Guid": ids["groups"][fam], "Name": g["name"], "Order": g["order"],
                                      "Subcategories": [{"Key": G[f"key/menu/group_{fam}_subcategory"],
                                                         "Value": ids["subcategory"]}],
                                      "BlockKinds": []}, B_GAME)
        stage_def(g["file"], grp)
        out["groups"][fam] = ids["groups"][fam]
    return out


def _recipe_file(spec):
    """The block's cloned recipe definition (mod-relative), if the clone has one."""
    files = [f for f in _block_files(spec, "Recipe") if "Recipe" in os.path.basename(f)]
    if len(files) > 1:
        raise RuntimeError(f"{spec.name}: several recipe files {files}")
    return files[0] if files else None


def _items(spec, kind, items, G):
    return [{"Key": G[f"key/{spec.name}/recipe/{kind}/{i}"], "Value": {"Item": recipes.ITEMS[i][0], "Amount": a}}
            for i, a in items]


def patch_recipe(spec, bd, G, report):
    """Our cost (dc/recipes.py) into the block's own recipe: the cloned recipe file when the clone has one (patched,
    GUID kept), else a new full definition; the block definition's Recipe points at it. A block whose density differs
    from its source's (recipes.density_patch: the door racks, the cable trays) gets it on the block definition."""
    c = recipes.cost(spec, report)
    crit, opt = _items(spec, "critical", c["critical"], G), _items(spec, "optional", c["optional"], G)
    rel = _recipe_file(spec)
    if rel:
        data = read_mod(rel)
        b = body(data)
        b["CriticalItems"], b["OptionalItems"] = crit, opt
        if c["time"] is not None:
            b["BuildTimePerItem"] = c["time"]
        guid = own_guid(data)
    else:
        rel = f"{config.NAME}/{spec.name}/{spec.name}_RecipeDefinition.def"
        guid = G[f"def/{spec.name}/recipe"]
        val = {"Guid": guid, "CriticalItems": crit, "OptionalItems": opt}
        if c["time"] is not None:
            val["BuildTimePerItem"] = c["time"]
        data = envelope(T_RECIPE, val, B_GAME)
    stage_def(rel, data)
    b = body(bd)
    b["Recipe"] = guid
    if recipes.density_patch(spec):
        b["Density"] = recipes.DENSITY[c["density"]][0]
    return {"file": rel, "guid": guid, "critical": c["critical"], "optional": c["optional"],
            "game_scale": c["game_scale"]}
