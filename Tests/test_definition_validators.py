"""Offline ports of the SE2 definition validators that can reject our blocks when a world loads.

A definition error at load is fatal ("DefinitionValidationException: Could not push definition set to
DefinitionManager because validation failed"), so every rule the game checks on our staged blocks and that we can
evaluate from files is ported here and run on the package as it will be installed (staged copy first, else the
mod's). Sources: decompiled 4.0.0.3151 (WS/tools/decompiled-current); first ported from 2.4.0.95 (WS/tools/decompiled),
the rules below are unchanged unless noted:

  * Game2.Simulation/.../RuntimeSystems.Validators/BreakableBlockModelValidator.cs (EntityCompositeDefinition):
    a composite with a BreakableBlockComponent needs a BlockModelComponent, a breakable collider (a fatal Error
    since 4.0, :66; in 2.4 Info/Warning by BreakableBlockCoreConfiguration.AllowMissingBreakableColliders) and,
    for the Model, the FractureModel and every BuildProgressModels[].Model that is not a fractured collider
    (IBreakableCollider with ColliderCount > 1): a damaged version and a fracture version
    ((model == Model && FractureModel set) || FractureReplacementModels.ContainsKey(model)). Without the
    component, no dummy may carry a SupportingFracture.
  * NEW in 4.0: VRage.Game/Keen.VRage.Game.Components.Fractures/BreakableModelColliderValidator.cs:15-24
    (PrefabDefinition): a prefab whose composition has a BreakableComponentDefinition and whose
    BreakableModelComponentDefinition has BreakableCollider == null is a fatal Error. BreakableCollider is only set
    from a valid FractureModel whose collider is an IRootBreakableCollider (BreakableModelComponentDefinition.cs
    Init :264-271), so no FractureModel, or one without fracture colliders, fails.
  * BreakableBlockCompositionValidator.cs: with the component, the tags IBlockPhysicsColliderProvider and
    IMountPointModifier must exist (warning).
  * BlockModelValidator.cs: no ambiguous PartChange (ResetToSkinMaterial with SetMaterial), every
    Damaged/FractureReplacementModels key is the Model or a build-stage model, every model has a collider.
  * BlockCompositionValidator.cs: a block composite needs a model with a baked collider.
  * PlacementDefinitionValidator.cs: SnapAlignment never holds two opposite directions.

A model's fracture collider count is read from its staged collision glTF (the Fracture_NN collider nodes, which
is what the importer turns into the IBreakableCollider's sub-colliders) and cross-checked against export.json.
Not ported (need the game runtime): CubeBlockValidator's MountPointsGroupsPerDirection (generated at load, none
in our files), BlockModelValidator's optimized-collider search, mass and bounds checks, MechanicalBlock /
Conveyor / GridControl / Seat / Drill validators (none of our blocks has those components).
"""
import os

import pytest

from dc import catalog, clone, config, integration
from dc.assetio import body, read_json

BREAKABLE_KEY = "bc5652a0-1296-4040-adc3-a2b9c35d5afc"   # BreakableBlockComponent in every Base*Breakable template
BREAKABLE_TYPE = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.BreakableBlockComponent"
BLOCK_MODEL_KEY = "d358358e-30b3-484a-b8b8-2e5568c7298b"
REQUIRED_BREAKABLE_TAGS = ("IBlockPhysicsColliderProvider", "IMountPointModifier")
OPPOSITE = {"Forward": "Backward", "Backward": "Forward", "Left": "Right", "Right": "Left", "Up": "Down",
            "Down": "Up"}


@pytest.fixture(scope="module")
def staged():
    integration.write_all()
    return integration.STAGE


def built():
    return sorted(integration.built_names())


def current(rel):
    p = os.path.join(config.STAGE_ASSETS, rel)
    return read_json(p if os.path.exists(p) else os.path.join(config.MOD_ASSETS, rel))


def block_file(name, suffix):
    return f"{config.NAME}/{name}/{name}{suffix}.partialdef"


def model_colliders(name):
    """{model guid: fracture collider count} for the block's staged .model assets (0: not breakable)."""
    out = {}
    for variant, stem in (("NonFractured", name), ("Fractured", f"{name}_Fractured"), ("Damaged", f"{name}_Damaged")):
        folder = f"{config.NAME}/{name}/Models/{variant}"
        if variant == "Damaged" and not os.path.isdir(os.path.join(config.STAGE_ASSETS, folder)):
            continue
        mrel = f"{folder}/{stem}.model"
        if not os.path.exists(os.path.join(config.STAGE_ASSETS, mrel)):
            continue                   # an unfractured block (the non-breakable exception) has no Damaged model
        ma = body(read_json(os.path.join(config.STAGE_ASSETS, mrel)))
        col_id = ma["CollisionShapesAsset"]["AssetReference"][3:]
        files = {integration.asset_id(f"{folder}/{f}"): f
                 for f in os.listdir(os.path.join(config.STAGE_ASSETS, folder)) if not f.endswith(".meta")}
        gltf = read_json(os.path.join(config.STAGE_ASSETS, folder, files[col_id]))
        out[integration.asset_id(mrel)] = sum(1 for n in gltf.get("nodes", [])
                                              if (n.get("name") or "").startswith("Fracture"))
    return out


def has_breakable(comp):
    c = body(comp)["Components"]
    if BREAKABLE_KEY in c["Keys"]:
        return True
    return any((ch.get("Value") or {}).get("Type") == BREAKABLE_TYPE for ch in c.get("Changed", []))


def ref(handle):
    return handle[3:] if isinstance(handle, str) and handle.startswith("{G}") else handle


def replacement_keys(m, member):
    v = m.get(member)
    if not v:
        return set()
    if isinstance(v, dict):
        return {ref(e["$Key"]) for e in v.get("ModifiedKeys", [])}
    return {ref(e["Key"] if "Key" in e else e["$Key"]) for e in v}


def breakable_model_errors(m, colliders):
    """BreakableBlockModelValidator.ValidateNeedsReplacements on Model, FractureModel and the build stages."""
    model, frac, dmg = ref(m.get("Model")), ref(m.get("FractureModel")), ref(m.get("DamagedModel"))
    dmg_rep, frac_rep = replacement_keys(m, "DamagedReplacementModels"), replacement_keys(m, "FractureReplacementModels")
    todo = [("Model", model)] + ([("FractureModel", frac)] if frac else [])
    todo += [(f"BuildProgressModels[{i}]", ref(s["Value"]["Model"])) for i, s in enumerate(m["BuildProgressModels"])
             if s["Value"].get("Model")]
    errs = []
    for where, mdl in todo:
        if colliders.get(mdl, 0) > 1:
            continue
        damaged_ok = ((mdl == model and dmg) or (frac and mdl == frac and dmg)) or mdl in dmg_rep
        fracture_ok = (mdl == model and bool(frac)) or mdl in frac_rep
        if not damaged_ok:
            errs.append(f"{where}: The model does not have a damaged replacement model")
        if not fracture_ok:
            errs.append(f"{where}: The model does not have a fracture replacement model")
    if colliders.get(frac, 0) == 0:
        errs.append(MISSING_BREAKABLE_COLLIDER)
    return errs


MISSING_BREAKABLE_COLLIDER = "Breakable blocks must have a breakable collider. (fatal Error since 4.0.0.3151)"


def breakable_model_collider_error(m, colliders):
    """BreakableModelColliderValidator (new in 4.0.0.3151, fatal): a breakable prefab's model needs a
    BreakableCollider, which only a FractureModel with fracture colliders provides (Init :264-271)."""
    frac = ref(m.get("FractureModel"))
    if not frac or colliders.get(frac, 0) == 0:
        return "Breakable prefab's model does not have a valid breakable collider. (fatal Error)"
    return None


def kept_and_removed(delta):
    """Keys both kept and Removed without being re-Inserted (vanilla re-inserts a Removed key with a new Type, e.g.
    LCDPowerableBlockBreakable's PowerableBlockComponent)."""
    inserted = {delta["Keys"][ch["Index"]] for ch in delta["Changed"] if ch["Kind"] == "Insert"}
    return (set(delta["Keys"]) & set(delta.get("Removed", []))) - inserted


def tags(comp):
    ts = body(comp).get("TagSlots") or {}
    return {e["$Key"]: e["$Value"] for e in ts.get("ModifiedKeys", [])}, set(ts.get("RemovedKeys", []))


# ---------------------------------------------------------------------------------------------- the load blocker
def test_breakable_block_model_validator(staged):
    """No staged block fails BreakableBlockModelValidator (the 2.4 load blocker: every one-collider server and
    tray kept the vanilla template's BreakableBlockComponent; 564 errors + 282 warnings)."""
    assert built()
    problems = []
    for n in built():
        bmd = body(current(clone.entry(catalog.BY_NAME[n])["info"]["model_def_file"]))
        colliders = model_colliders(n)
        for side in ("_ServerComposition", "_ClientComposition"):
            comp = current(block_file(n, side))
            if has_breakable(comp):
                if BLOCK_MODEL_KEY not in body(comp)["Components"]["Keys"]:
                    problems.append(f"{n}{side}: Breakable blocks need a BlockModelComponent component.")
                problems += [f"{n}{side}: {e}" for e in breakable_model_errors(bmd, colliders)]
            else:
                dummies = (bmd.get("Dummies") or {}).get("Changed", [])
                problems += [f"{n}{side}: dummy {d['Value'].get('Name')} has a SupportingFracture but the block "
                             f"is not breakable" for d in dummies
                             if (d.get("Value") or {}).get("SupportingFracture")]
    assert not problems, f"{len(problems)} validation problems:\n" + "\n".join(problems[:40])


def test_missing_breakable_collider_is_fatal():
    """4.0.0.3151 made a missing breakable collider fatal twice over: BreakableBlockModelValidator reports an Error
    (2.4: Info/Warning) and the new BreakableModelColliderValidator rejects the prefab. Both ports must report it
    as fatal, for a block without a FractureModel and for one whose FractureModel has no fracture colliders."""
    no_frac = {"Model": "{G}m", "DamagedModel": "{G}d", "FractureModel": None, "BuildProgressModels": []}
    no_cols = dict(no_frac, FractureModel="{G}f")
    for m, cols in ((no_frac, {}), (no_cols, {"f": 0})):
        errs = breakable_model_errors(m, cols)
        assert MISSING_BREAKABLE_COLLIDER in errs, errs
        assert not any("warning" in e.lower() for e in errs), errs
        assert "fatal" in (breakable_model_collider_error(m, cols) or ""), m
    ok = dict(no_frac, FractureModel="{G}f")
    assert MISSING_BREAKABLE_COLLIDER not in breakable_model_errors(ok, {"f": 3})
    assert breakable_model_collider_error(ok, {"f": 3}) is None


def test_breakable_model_collider_validator(staged):
    """BreakableModelColliderValidator (new in 4.0.0.3151): every built prefab with a BreakableBlockComponent has a
    model whose FractureModel resolves a breakable collider."""
    assert built()
    problems, checked = [], 0
    for n in built():
        bmd = body(current(clone.entry(catalog.BY_NAME[n])["info"]["model_def_file"]))
        colliders = model_colliders(n)
        for side in ("_ServerComposition", "_ClientComposition"):
            if has_breakable(current(block_file(n, side))):
                checked += 1
                e = breakable_model_collider_error(bmd, colliders)
                if e:
                    problems.append(f"{n}{side}: {e}")
    assert checked, "no breakable prefab found: the scan reads nothing"
    assert not problems, f"{len(problems)} validation problems:\n" + "\n".join(problems[:40])


SERVER_AND_TRAY = ("server", "tray", "trayrods")


def test_servers_and_trays_breakable(staged):
    """Plan 2 Task 9b (Ruling P2-27): every built DC_Srv_* and DC_Tray* block but the justified exception (the three
    rod hangers and the Chute: fracture.UNFRACTURED) is BREAKABLE again: a
    fractured Fractured model (>= 2 fracture colliders) and a fractured Damaged model, both compositions carry the
    BreakableBlockComponent bound to the block's own BreakableBlockDefinition, whose CriticalFractures are the
    export's critical zone (Fracture_01, the key zone), the five tag slots
    are not removed, and both prefabs build its object builder (no Removed entry for it)."""
    from dc import fracture as FR
    names = [n for n in built() if catalog.BY_NAME[n].family in SERVER_AND_TRAY]
    assert len(names) == len([b for b in catalog.BLOCKS if b.family in SERVER_AND_TRAY]) == 48, len(names)
    exception = sorted(n for n in names if FR.unfractured_reason(catalog.BY_NAME[n]))
    assert exception == ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200", "DC_Tray_Chute"], exception
    for n in names:
        spec = catalog.BY_NAME[n]
        if n in exception:     # the justified exception: unfractured, non-breakable (test_breakable_only_...)
            assert model_colliders(n)[integration.asset_id(
                f"{config.NAME}/{n}/Models/Fractured/{n}_Fractured.model")] == 0, n
            assert not has_breakable(current(block_file(n, "_ServerComposition"))), n
            continue
        man = read_json(os.path.join(config.MODELS_DIR, n, "export.json"))
        bmd = body(current(clone.entry(spec)["info"]["model_def_file"]))
        cols = model_colliders(n)
        assert cols[ref(bmd["FractureModel"])] >= 2 and cols[ref(bmd["DamagedModel"])] >= 2, (n, cols)
        assert ref(bmd["DamagedModel"]) != ref(bmd["FractureModel"]), n
        crit = man["fractured"]["critical"]
        want = [] if spec.family == "tray" else ["Fracture_01"]    # Ruling P2-30: trays are structural
        assert crit == want, (n, crit)
        bbd_files = integration._block_files(spec, "_BreakableBlockDefinition")
        assert len(bbd_files) == 1 or (n == "DC_Srv_KVM" and not bbd_files), (n, bbd_files)
        rel = bbd_files[0] if bbd_files else f"{config.NAME}/{n}/{n}_BreakableBlockDefinition.partialdef"
        bbd = current(rel)
        assert [c["Id"] for c in body(bbd)["CriticalFractures"].get("Added", [])] == crit, n
        guid = bbd["$Value"]["Manipulator"]["Guid"]
        for side in ("Server", "Client"):
            comp = current(block_file(n, f"_{side}Composition"))
            c = body(comp)["Components"]
            assert BREAKABLE_KEY in c["Keys"] and BREAKABLE_KEY not in c.get("Removed", []), (n, side)
            i = c["Keys"].index(BREAKABLE_KEY)
            assert c["Keys"][i - 1] == integration.BREAKABLE_AFTER.get(comp["$Value"]["BaseDefinition"],
                                                                       BLOCK_MODEL_KEY), (n, side, "not where the template has it")
            assert [ch["Value"].get("Definition") for ch in c["Changed"] if ch["Index"] == i] == [guid], (n, side)
            _, removed = tags(comp)
            assert not removed & set(integration.BREAKABLE_SLOTS), (n, side)
            ob = body(current(block_file(n, f"_{side}")))["_entity"].get("ObjectBuilders")
            assert ob is None or (BREAKABLE_KEY in ob["Keys"] and BREAKABLE_KEY not in ob.get("Removed", [])), (n, side)


def test_supporting_fractures_exist(staged):
    """A dummy's SupportingFracture (the UPS cell slots, vanilla Battery50's pattern) names a fracture its block's
    FractureModel has."""
    for n in built():
        man = read_json(os.path.join(config.MODELS_DIR, n, "export.json"))
        zones = {z["id"] for z in man["fractured"]["zones"]}
        bmd = body(current(clone.entry(catalog.BY_NAME[n])["info"]["model_def_file"]))
        for d in (bmd.get("Dummies") or {}).get("Changed", []):
            sf = (d.get("Value") or {}).get("SupportingFracture")
            if sf:
                assert sf["Id"] in zones, (n, d["Value"].get("Name"), sf)


def test_fracture_colliders_match_export(staged):
    """The collider counts the validator test relies on agree with the export (one per zone, Damaged too)."""
    for n in built():
        zones = read_json(os.path.join(config.MODELS_DIR, n, "export.json"))["fractured"]["zones"]
        frac = integration.asset_id(f"{config.NAME}/{n}/Models/Fractured/{n}_Fractured.model")
        assert model_colliders(n)[frac] == len(zones), n
        if read_json(os.path.join(config.MODELS_DIR, n, "export.json")).get("damaged"):
            dmg = integration.asset_id(f"{config.NAME}/{n}/Models/Damaged/{n}_Damaged.model")
            assert model_colliders(n)[dmg] == len(zones), n


def test_breakable_only_on_fractured_models(staged):
    """A block keeps the BreakableBlockComponent exactly when its FractureModel really fractures (>= 2 fracture
    colliders: the racks, servers and trays); the others are non-breakable like vanilla Templates/Blocks/Non-Breakable/Structural
    and ControlPanel25 (component Removed, its five tag slots RemovedKeys, prefab ObjectBuilders without it)."""
    for n in built():
        frac = integration.asset_id(f"{config.NAME}/{n}/Models/Fractured/{n}_Fractured.model")
        fractures = model_colliders(n)[frac] > 1
        for side in ("Server", "Client"):
            comp = current(block_file(n, f"_{side}Composition"))
            assert has_breakable(comp) == fractures, (n, side)
            mk, removed = tags(comp)
            if fractures:
                assert not removed & set(REQUIRED_BREAKABLE_TAGS), (n, side)   # BreakableBlockCompositionValidator
                continue
            c = body(comp)["Components"]
            assert BREAKABLE_KEY in c["Removed"], (n, side)
            assert BREAKABLE_KEY not in mk.values(), (n, side, "a tag slot still points at the removed component")
            assert set(integration.BREAKABLE_SLOTS) <= removed | set(mk), (n, side)
            ob = body(current(block_file(n, f"_{side}")))["_entity"].get("ObjectBuilders")
            assert ob and BREAKABLE_KEY not in ob["Keys"] and BREAKABLE_KEY in ob["Removed"], (n, side)


# ---------------------------------------------------------------------------------------------- delta sanity
def test_composition_and_prefab_deltas_consistent(staged):
    """Every staged composition / prefab key-list delta is well formed: Changed indices inside Keys and unique,
    no key both kept and Removed (unless re-Inserted), every tag slot pointing at a kept component; the same index / Removed rules for
    a prefab's explicit ObjectBuilders."""
    for n in built():
        for side in ("Server", "Client"):
            comp = body(current(block_file(n, f"_{side}Composition")))
            c = comp["Components"]
            idx = [ch["Index"] for ch in c["Changed"]]
            assert len(idx) == len(set(idx)) and all(0 <= i < len(c["Keys"]) for i in idx), (n, side)
            assert not kept_and_removed(c), (n, side)
            mk, _ = tags(current(block_file(n, f"_{side}Composition")))
            assert set(mk.values()) <= set(c["Keys"]), (n, side, set(mk.values()) - set(c["Keys"]))
            ob = body(current(block_file(n, f"_{side}")))["_entity"].get("ObjectBuilders")
            if ob:
                oidx = [ch["Index"] for ch in ob["Changed"]]
                assert len(oidx) == len(set(oidx)) and all(0 <= i < len(ob["Keys"]) for i in oidx), (n, side)
                assert not kept_and_removed(ob), (n, side)


# ---------------------------------------------------------------------------------------------- other validators
def test_block_model_validator(staged):
    """BlockModelValidator's file-checkable rules on every staged BlockModelDefinition."""
    for n in built():
        m = body(current(clone.entry(catalog.BY_NAME[n])["info"]["model_def_file"]))
        stages = [ref(s["Value"].get("Model")) for s in m["BuildProgressModels"]]
        for i, s in enumerate(m["BuildProgressModels"]):
            for pc in s["Value"]["PartChanges"]["_data"]:
                v = pc["Value"]
                assert not (v.get("ResetToSkinMaterial") and v.get("SetMaterial")), (n, i, v["MeshPart"])
        for member in ("DamagedReplacementModels", "FractureReplacementModels"):
            for k in replacement_keys(m, member):
                assert k == ref(m["Model"]) or k in stages, (n, member, "has an unused pair")
        colliders = model_colliders(n)
        for mdl in {ref(m["Model"]), ref(m["FractureModel"]), ref(m["DamagedModel"])} | set(filter(None, stages)):
            assert mdl in colliders, (n, mdl, "model is not one of the block's staged models (no collider known)")


def test_placement_snap_alignment(staged):
    """PlacementDefinitionValidator: no SnapAlignment with two opposite directions (none of ours sets one)."""
    for n in built():
        rel = f"{config.NAME}/{n}/{n}_PlacementDefinition.def"
        if not os.path.exists(os.path.join(config.MOD_ASSETS, rel)):
            continue
        snap = body(current(rel)).get("SnapAlignment")
        if snap:
            dirs = {d.strip() for d in snap.split(",")}
            assert not any(OPPOSITE[d] in dirs for d in dirs if d in OPPOSITE), (n, snap)


# ---------------------------------------------------------------------------- ConveyorGraphPostProcessor client types
# Final review M2 (2026-10-19). ConveyorGraphPostProcessor.ValidateClientTypes (Game2.Simulation/.../
# ConveyorGraphPostProcessor.cs:162-205) runs on every EntityCompositeDefinition that BindingsBasedClientServerInfo
# reaches from a PrefabBinding: a SERVER composition may hold no type from a client assembly
# (ComponentTypeUtility.IsClientType, VRage.Core.Game/.../ComponentTypeUtility.cs:14-22: the assembly carries
# [assembly: ClientAssembly] or its name ends in "Client"), and a CLIENT composition no [ServerOnly] type. A failure
# is a definition validation error, fatal at world load. Our compositions are vanilla clones (valid as cloned), so the
# risk is what we insert: every type a delta inserts is resolved to its assembly in WS/tools/decompiled-current
# (<Assembly>/<Namespace>/<Class>.cs; a symlink to the decompile of the installed game version, 4.0.0.3151).
# This is the inserted-types shortcut; the full walk (base chains, reference following, hierarchy children, every
# reached composite, vanilla included) is Tests/clientserver_walk.py, tested in Tests/test_clientserver_walk.py (T12a).
DECOMPILED = os.path.join(config.TOOLS_DIR, "decompiled-current")
NOT_ASSEMBLIES = {"sdk-pipeline"}       # the SDK Editor pipeline decompile lives inside the 4.0 tree


def _type_index():
    """{full type name: (assembly, server_only)} for the decompiled assemblies; client assemblies by attribute."""
    idx, client = {}, set()
    for asm in os.listdir(DECOMPILED):
        if asm in NOT_ASSEMBLIES:
            continue
        info = os.path.join(DECOMPILED, asm, "Properties", "AssemblyInfo.cs")
        if asm.endswith("Client") or (os.path.exists(info) and "[assembly: ClientAssembly]" in open(info).read()):
            client.add(asm)
        root = os.path.join(DECOMPILED, asm)
        if not os.path.isdir(root):
            continue
        for ns in os.listdir(root):
            d = os.path.join(root, ns)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".cs"):
                        idx[f"{ns}.{f[:-3]}"] = (asm, os.path.join(d, f))
    return idx, client


def _package_defs():
    """{definition GUID: manipulator} over the package as it will be installed (the staged file over the mod's)."""
    files = {}
    for base in (config.MOD_ASSETS, config.STAGE_ASSETS):
        for dp, _, fs in os.walk(os.path.join(base, config.NAME)):
            for f in fs:
                if f.endswith(("def", ".partialdef")) and not f.endswith(".meta"):
                    files[os.path.relpath(os.path.join(dp, f), base)] = os.path.join(dp, f)
    out = {}
    for p in files.values():
        try:
            m = body(read_json(p))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if isinstance(m, dict) and m.get("Guid"):
            out[m["Guid"]] = m
    return out


def _inserted_types(comp):
    c = comp.get("Components")
    if isinstance(c, dict):
        rows = [ch.get("Value") or {} for ch in c.get("Changed", [])]
    elif isinstance(c, list):
        rows = c
    else:
        rows = []
    return [r["Type"] for r in rows if isinstance(r, dict) and ":" in str(r.get("Type", ""))]


def test_no_client_types_on_server_compositions(staged):
    if not os.path.isdir(DECOMPILED):
        pytest.skip("no WS/tools/decompiled-current (the decompiled game assemblies)")
    idx, client_asms = _type_index()
    defs = _package_defs()
    bindings = [m for m in defs.values() if "ServerComposite" in m and "ClientPrefab" in m]
    assert len(bindings) >= 73, len(bindings)      # every block (and its subpart prefabs) binds
    bad, unresolved, checked = [], set(), 0

    def resolve(t):
        name = t.split(":", 1)[1]
        if name not in idx:
            unresolved.add(t)
            return None
        return idx[name]

    for b in bindings:
        srv = defs.get(b["ServerComposite"])
        for t in _inserted_types(srv) if srv else ():
            checked += 1
            r = resolve(t)
            if r and r[0] in client_asms:
                bad.append(("client type on server composition", b["Guid"], t))
        cp = defs.get(b["ClientPrefab"])
        comp = defs.get(((cp or {}).get("_entity") or {}).get("Definition"))
        for t in _inserted_types(comp) if comp else ():
            checked += 1
            r = resolve(t)
            if r and "[ServerOnly]" in open(r[1]).read():
                bad.append(("server-only type on client composition", b["Guid"], t))
    assert not unresolved, sorted(unresolved)
    assert not bad, bad
    assert checked, "no inserted component type found: the scan reads nothing"


# ------------------------------------------------------------------------------- 4.0 schema gate: non-null + component types
# Fix 2026-10-20 (fix-open-rack-load.md): the open racks failed world load with NullableValidator errors (Density,
# RecipeEfficiency, ConsumedResource.Type) and EntityBuilder "Definition PowerableBlockDefinition type doesn't match
# expected CubeBlockDefinition" on both compositions. The assets were right; the SDK build had not rewritten the racks'
# Content .def files after Task 12 rebased them onto PowerableBlockDefinition, while it regenerated the definition index.
# Two checks of Tests/definition_schema.py (shared core, ports and sources there), each run on the package as installed
# (staged over the mod's Assets) AND on the built Content as the game loads it; plus a Content freshness check.
import clientserver_walk as csw            # noqa: E402
import definition_schema as ds             # noqa: E402

CONTENT = os.path.join(config.MOD_DIR, "Content")


def _need_sdk():
    if not os.path.isdir(csw.SDK_ASSETS):
        pytest.skip("no Mod SDK vanilla Assets (SE2_SDK_ASSETS): the definition bases cannot be resolved")
    try:
        return ds.Schema(csw.TypeIndex())
    except csw.MissingDecompile as ex:
        pytest.skip(str(ex))


@pytest.fixture(scope="module")
def schema():
    return _need_sdk()


@pytest.fixture(scope="module")
def installed(staged):
    return csw.Universe([csw.SDK_ASSETS, config.MOD_ASSETS, config.STAGE_ASSETS])


def _ours(u, *roots):
    roots = tuple(os.path.abspath(r) + os.sep for r in roots)
    return [g for g in u.entries if os.path.abspath(str(u.origin(g))).startswith(roots)]


def test_every_definition_nonnull_members(staged, installed, schema):
    """NullableValidator over every DataCenter definition, fully resolved (base chain + partialdef deltas)."""
    mine = _ours(installed, config.MOD_ASSETS, config.STAGE_ASSETS)
    assert len(mine) >= 1200, len(mine)
    errs = ds.nonnull_errors(installed, schema, mine)
    assert not errs, "\n" + ds.format_errors(errs)
    assert not schema.unknown, schema.unknown            # every member type classified: nothing silently skipped


def test_every_composition_component_definition_type(staged, installed, schema):
    """EntityBuilder.AssertMatch: each composite component's Definition is exactly the class the component expects."""
    mine = _ours(installed, config.MOD_ASSETS, config.STAGE_ASSETS)
    comps = [g for g in mine if installed.type_of(g) == csw.COMPOSITE]
    assert len(comps) >= 150, len(comps)
    errs = ds.composition_type_errors(installed, schema, comps)
    assert not errs, "\n" + ds.format_errors(errs)


def test_checks_catch_the_2026_10_20_open_rack_failure(staged, installed, schema):
    """The two checks reject the exact state that failed in game: DC_Rack24_Open's structural definition rebased onto
    PowerableBlockDefinition (794c5233) with the CubeBlock-shaped members it had before Task 12 (no Density,
    RecipeEfficiency, ConsumedResource), and the server composition still on the structural CubeBlockComponent key."""
    def_rel = "DataCenter/DC_Rack24_Open/DC_Rack24_Open_StructuralCubeBlockDefinition.partialdef"
    comp_rel = "DataCenter/DC_Rack24_Open/DC_Rack24_Open_ServerComposition.partialdef"
    d, c = current(def_rel), current(comp_rel)
    man = {k: v for k, v in d["$Value"]["Manipulator"].items()
           if k not in ("Density", "RecipeEfficiency", "PCU", "ConsumedResource", "Fragility")}
    bad_def = {"$Type": d["$Type"], "$Value": dict(d["$Value"], Manipulator=man)}
    comp_man = {"Guid": c["$Value"]["Manipulator"]["Guid"], "Components": {
        "$DeltaEncoded": True, "Keys": ["786ef564-3cbf-4509-a58c-ad19243fffc1"],
        "Changed": [{"Kind": "Update", "Index": 0, "Value": {"Definition": man["Guid"]}}], "Removed": []}}
    bad_comp = {"$Type": c["$Type"], "$Value": dict(c["$Value"], Manipulator=comp_man)}
    u = installed.derive(bad_def, bad_comp)
    got = {p for _, _, p, _ in ds.nonnull_errors(u, schema, [man["Guid"]])}
    assert got == {"$Root.Density", "$Root.RecipeEfficiency", "$Root.ConsumedResource.Type"}, got
    cerr = ds.composition_type_errors(u, schema, [comp_man["Guid"]])
    assert [e[2] for e in cerr] == ["$Root.Components[2].Definition"], cerr
    assert "PowerableBlockDefinition type doesn't match expected Keen.Game2.Simulation.WorldObjects.CubeBlocks." \
           "CubeBlockDefinition" in cerr[0][3]


def _content_or_skip():
    if not os.path.isfile(os.path.join(CONTENT, "definitionsets.vrb")):
        pytest.skip("no built Content/ (run `python3 tools/scripts/se2mod.py build DataCenter`)")


def test_built_content_current():
    """Every installed asset has its Content .def, of the asset's class, holding the asset's own members: a stale
    output loads against the regenerated index as a different definition (see definition_schema.content_view)."""
    _content_or_skip()
    stale = ds.stale_outputs(config.MOD_ASSETS, CONTENT)
    assert not stale, f"{len(stale)} stale Content outputs (rebuild):\n" + "\n".join(f"{r}: {w}" for r, w in stale[:30])


def test_built_content_loads(schema):
    """The two schema checks on the BUILT package as the game loads it (Content members on the index's bases)."""
    _content_or_skip()
    u = csw.Universe([csw.SDK_ASSETS, config.MOD_ASSETS])
    cu, missing = ds.content_view(u, config.MOD_ASSETS, CONTENT)
    mine = _ours(u, config.MOD_ASSETS)
    errs = ds.nonnull_errors(cu, schema, mine) + ds.composition_type_errors(cu, schema, mine)
    assert not missing, missing[:20]
    assert not errs, "\n" + ds.format_errors(errs)
