"""Plan 4 Task 3: the Programmable as a functional blade (data), and the GUID bridge to the scripts.

Rulings (docs/superpowers/sdd/data-center-scripts/progress.md):
  P4-1 = A'  the vanilla InGameScriptingComponent lives PERMANENTLY in the Programmable's server data (its
             InGameScriptingDefinition a full .def, its object builder in the server prefab), so a save is identical
             with and without -loadScripts. Without the switch a Run ends in an ordinary compile error
             (docs/research/dc-scripts-save-safety.md section 2).
  P4-2       the Programmable moves to the KVM's Ruling 15 chain: PowerableBlockComponent (ConsumedResource null,
             Enabled true), ControlPanel25's Terminal use dummy over the management module; same block GUID.
  P4-6       Scripts/Simulation/Shared/DcGuids.g.cs is generated from the staged definitions + asset_guids.json.
  P4-7       data-only the LED stays amber; the swapper exists for the scripts and maps nothing in data; the
             management LCD reads state-neutral ("SCRIPT HOST" / "PRG-06").

Both modes are covered: the "scripts off" tests are what a player without -loadScripts gets (all of it data), the
"scripts on" tests are what the scripts rely on finding in that same data.
"""
import os
import re
import sys

import pytest

from dc import catalog, clone, config, functional, guids, integration, script_guids, scripting
from dc.assetio import own_guid, read_json
from dc.material_guids import MATERIAL_GUIDS

PROG, KVM = "DC_Srv_Programmable", "DC_Srv_KVM"
# The Programmable's block definition GUID since the core shipped (the clone's GUID map of WallInsertPanel's
# 399e592a): placed blocks reference their definition by it, so it must never change.
PRE_PLAN4_BLOCK_DEF = "824c6c77-9b86-4c54-b691-571bc3b6c246"
PRE_PLAN4_SERVER_PREFAB = "23348530-da41-4f57-bc34-32987f0275d3"
STRUCTURAL_KEY = "786ef564-3cbf-4509-a58c-ad19243fffc1"   # Structural_*Composition: CubeBlockComponent
TERMINAL_TYPE = "b15d441f-88d0-4722-a377-7adfd75579e7"    # System/DummyTypes: UseTerminal (ControlPanel25, Timer50)
T_SCRIPTING = "Game2:Keen.Game2.Simulation.Scripting.InGameScriptingComponent"
LOC_TEXTS = os.path.expanduser("~/.steam/debian-installation/steamapps/common/SpaceEngineers2/GameData/Vanilla/"
                               "Content/MainMenuData/Texts/en-US")
BLOCK_CHAIN = os.path.join(config.TOOLS_DIR, "scripts")


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


@pytest.fixture(scope="module")
def sdk():
    """tools/scripts/block_chain.py's index of the Mod SDK sources (read-only), for resolving vanilla templates."""
    sys.path.insert(0, BLOCK_CHAIN)
    try:
        import block_chain
    finally:
        sys.path.remove(BLOCK_CHAIN)
    if not block_chain.SDK.is_dir():
        pytest.skip("Mod SDK not installed")
    return block_chain.Index()


def _spec():
    return catalog.BY_NAME[PROG]


def _info():
    return clone.entry(_spec())["info"]


def _stage(rel):
    p = os.path.join(config.STAGE_ASSETS, rel)
    assert os.path.exists(p), f"not staged: {rel}"
    return read_json(p)


def _body(d):
    v = d["$Value"]
    return v["Manipulator"] if "PartialDefinitionKind" in v else v


def _file(pat):
    return integration._block_files(_spec(), pat)[0]


def _inserts(delta):
    """{key: value} of a delta-encoded keyed list's Inserts."""
    return {delta["Keys"][c["Index"]]: c["Value"] for c in delta["Changed"] if c["Kind"] == "Insert"}


def _staged_guids():
    out = {}
    for dp, _, fs in os.walk(config.STAGE_ASSETS):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                g = own_guid(read_json(os.path.join(dp, f)))
                if g:
                    out[g] = os.path.relpath(os.path.join(dp, f), config.STAGE_ASSETS)
    return out


# ---------------------------------------------------------------------------------------------- P4-6: GUID bridge
@pytest.mark.scripts
def test_script_guids_current(staged):
    """DcGuids.g.cs is exactly what the generator makes of the current staging (a stale file fails here: rerun
    build_integration.py), and every GUID in it is a staged definition or a stable asset_guids.json key."""
    text = script_guids.generate(config.STAGE_ASSETS)
    with open(script_guids.OUT, encoding="utf-8", newline="") as f:
        assert f.read() == text, "Scripts/Simulation/Shared/DcGuids.g.cs is stale: run Source/Model/build_integration.py"
    consts = dict(re.findall(r'public static readonly Guid (\w+) = new Guid\("([0-9a-f-]{36})"\);', text))
    assert set(consts) == {c.name for c in script_guids.CONSTANTS if c.kind not in ("name", "int")} == {
        "ProgrammableServerPrefab", "ProgrammableClientPrefab", "ProgrammableScriptingDefinition",
        "ProgrammableScriptingComponentId", "ProgrammableSwapper", "KvmClientPrefab", "KvmSequencerComponentId",
        "KvmDrawerComposite", "KvmScreenComposite", "KvmDrawerTranslationDef", "KvmScreenRotationDef",
        "EmissiveGreenMaterial"} | {f"Rack{h}{v}Block" for h in (42, 24) for v in ("Open", "SplitFront", "SplitFrontRear")}
    defs = _staged_guids()
    keys = set(guids.Guids(guids.GUIDS_PATH).d.values())
    materials = {v[0] for v in MATERIAL_GUIDS.values()}
    for name, g in consts.items():
        assert g in defs or g in keys or g in materials, (name, g)
    assert consts["EmissiveGreenMaterial"] == MATERIAL_GUIDS["EmissiveGreen"][0]
    names = dict(re.findall(r'public const string (\w+) = "([^"]*)";', text))
    assert names == {"ProgrammableStatusMeshPart": functional.PROG_LED}
    ints = dict(re.findall(r"public const int (\w+) = (\d+);", text))
    assert {k: int(v) for k, v in ints.items()} == {f"Rack{h}{v}DoorSides": {"Open": 0, "SplitFront": 1, "SplitFrontRear": 3}[v]
                                                    for h in (42, 24) for v in ("Open", "SplitFront", "SplitFrontRear")}
    # the ones the brief pins (the KVM subpart chain of core Task 8)
    for name, prefix in (("KvmDrawerComposite", "e3a9e30c"), ("KvmScreenComposite", "8874b2aa"),
                         ("KvmDrawerTranslationDef", "48311d48"), ("KvmScreenRotationDef", "736752c2")):
        assert consts[name].startswith(prefix), (name, consts[name])
    assert consts["ProgrammableServerPrefab"] == _info()["server_prefab"] == PRE_PLAN4_SERVER_PREFAB
    assert consts["KvmClientPrefab"] == clone.entry(catalog.BY_NAME[KVM])["info"]["client_prefab"]
    assert defs[consts["ProgrammableScriptingDefinition"]].endswith("_InGameScriptingDefinition.def")
    assert defs[consts["ProgrammableSwapper"]].endswith("_BlockMaterialSwapperDefinition.def")


def test_script_guids_refuse_unknown_guid(tmp_path):
    """The generator never mints: a constant whose source is missing from the staging fails loudly."""
    with pytest.raises(RuntimeError, match="not staged"):
        script_guids.generate(str(tmp_path))


def test_script_guids_refuse_missing_key(monkeypatch):
    """... and a constant whose asset_guids.json key is missing fails loudly too (no minting)."""
    real = guids.Guids(guids.GUIDS_PATH)
    real.d.pop(scripting.DEFINITION_KEY)
    monkeypatch.setattr(script_guids, "Guids", lambda path: real)
    with pytest.raises(RuntimeError, match="has no key"):
        script_guids.generate(config.STAGE_ASSETS)


@pytest.mark.scripts
def test_script_guids_file_is_a_valid_script():
    """The generated file follows the scripts' own rules (namespace, header) and declares only readonly fields."""
    with open(script_guids.OUT, encoding="utf-8") as f:
        text = f.read()
    assert "namespace DataCenter.Shared;" in text and "public static class DcGuids" in text
    assert text.startswith("// <auto-generated>")
    body = text[text.index("public static class DcGuids"):]
    n_names = sum(c.kind == "name" for c in script_guids.CONSTANTS)
    n_ints = sum(c.kind == "int" for c in script_guids.CONSTANTS)
    assert body.count("public static readonly Guid") == len(script_guids.CONSTANTS) - n_names - n_ints
    assert body.count("public const string") == n_names
    assert body.count("public const int") == n_ints
    assert "static Guid" not in body.replace("static readonly Guid", "")


# ---------------------------------------------------------------------------------------------- P4-2: functional blade
def test_programmable_is_terminal_powerable(staged):
    """Both compositions carry vanilla's On/Off component at the Ruling 15 key (PowerableBlockComponent bound to the
    block's own definition, now a PowerableBlockDefinition with no consumed resource), the structural
    CubeBlockComponent is gone and no tag slot points at it; both prefabs spawn it Enabled (built ON, as vanilla)."""
    spec = _spec()
    assert spec.functional
    bd = _stage(_info()["block_def_file"])["$Value"]
    assert bd["DefinitionType"] == integration.T_POWERABLE_DEF
    assert bd["BaseDefinition"] == integration.POWERABLE_DEF_BASE
    m = bd["Manipulator"]
    assert m["ConsumedResource"] is None
    assert m["Guid"] == PRE_PLAN4_BLOCK_DEF == _info()["block_def"]       # placed blocks keep their definition
    for pat in ("_ServerComposition", "_ClientComposition"):
        c = _body(_stage(_file(pat)))
        keys = c["Components"]["Keys"]
        assert integration.POWERABLE_KEY in keys and STRUCTURAL_KEY not in keys, pat
        assert STRUCTURAL_KEY in c["Components"]["Removed"]
        assert _inserts(c["Components"])[integration.POWERABLE_KEY] == {"Definition": PRE_PLAN4_BLOCK_DEF,
                                                                        "Type": integration.T_POWERABLE}
        slots = {s["$Key"]: s["$Value"] for s in c["TagSlots"]["ModifiedKeys"]}
        assert STRUCTURAL_KEY not in slots.values()
        for slot in integration.BASE_SLOTS_ON_FUNCTIONAL:
            assert slots[slot] == integration.POWERABLE_KEY, (pat, slot)
    for pat in ("_Server.partialdef", "_Client.partialdef"):
        ob = _body(_stage(_file(pat)))["_entity"]["ObjectBuilders"]
        assert STRUCTURAL_KEY in ob["Removed"] and STRUCTURAL_KEY not in ob["Keys"]
        v = _inserts(ob)[integration.POWERABLE_KEY]
        assert v["$Type"] == integration.OB_POWERABLE and v["Enabled"] is True and "PreviewOnly" not in v
    assert _body(_stage(_file("_Server.partialdef")))["Guid"] == PRE_PLAN4_SERVER_PREFAB


def test_programmable_slots_follow_the_structural_template(sdk):
    """The tag slots retargeted onto the Powerable key are exactly those the structural template points at its
    CubeBlockComponent (resolved from the Mod SDK chain), on both sides."""
    for comp in ("0c791273-388f-418a-8c01-a9a4786f404b", "35365f7b-19e2-460b-87cd-a3a9c2a97fb0"):
        r = sdk.resolve(comp)
        on = {s["$Key"] for s in r["TagSlots"] if s["$Value"] == STRUCTURAL_KEY}
        assert on == set(integration.BASE_SLOTS_ON_FUNCTIONAL), (comp, on)
        types = {c["Key"]: c["Value"]["Type"] for c in r["Components"]}
        assert types[STRUCTURAL_KEY].endswith(".CubeBlockComponent")


def test_programmable_block_definition_keeps_its_values(staged, sdk):
    """Rebasing the block definition from StructuralCubeBlockDefinition onto PowerableBlockDefinition changes no
    value the block had: every field the two template chains resolve differently is set by our manipulator, to the
    structural value, except the deliberate ConsumedResource (null: no sink, always supplied) and, since Plan 5 Task 3
    (G8), Fragility: Functional, the Powerable template's own value (Tests/test_damage_look.py)."""
    structural = sdk.resolve(integration.STRUCTURAL_DEF_BASE)
    powerable = sdk.resolve(integration.POWERABLE_DEF_BASE)
    m = _stage(_info()["block_def_file"])["$Value"]["Manipulator"]
    for k in set(structural) | set(powerable):
        if k in ("Guid", "UIData") or structural.get(k) == powerable.get(k):
            continue
        if k == "ConsumedResource":
            assert m[k] is None
            continue
        if k == "Fragility":
            assert m[k] == powerable[k] == integration.FRAGILITY["Functional"]
            continue
        if k not in structural:
            continue                                  # a Powerable-only field (ConsumptionPriority): template value
        assert k in m, f"{k}: structural {structural.get(k)!r} vs powerable {powerable.get(k)!r}, not set"
        if k != "Recipe":                             # Recipe: ours (patch_recipe)
            assert m[k] == structural[k], (k, m[k], structural[k])


def test_programmable_terminal_over_management_module(staged):
    """ControlPanel25's Terminal use dummy (type, highlight section, name) sits on the face over the management
    module only: aiming at a blade sled opens nothing."""
    from dc import server
    from dc.servers import programmable as P
    bmd = _body(_stage(_info()["model_def_file"]))
    dums = {c["Value"]["Name"]: c["Value"] for c in bmd["Dummies"]["Changed"]}
    t = dums["Terminal"]
    assert t["Type"] == TERMINAL_TYPE and t["HighlightSection"] == {"Id": "TerminalFront"}
    # the module is the right-hand strip of the bezel opening, MGMT_W wide, full height (what the face builds)
    (a0, a1), (b0, b1) = functional.PROG_MGMT["a"], functional.PROG_MGMT["b"]
    _, fa1, fb0, fb1 = server.face_frame_area(server.dims(_spec()))
    assert (a1, b0, b1) == pytest.approx((fa1, fb0, fb1), abs=1e-9) and a1 - a0 == pytest.approx(P.MGMT_W)
    pos = t["Transform"]["Transform"]["Position"]
    sx, sy = t["Scale"]["X"], t["Scale"]["Y"]
    # game x = -a + shift (functional.face_to_game): the box's a-span is the module's
    lo_a, hi_a = functional.SHIFT[0] - (pos["X"] + sx / 2), functional.SHIFT[0] - (pos["X"] - sx / 2)
    assert lo_a == pytest.approx(a0, abs=1e-6) and hi_a == pytest.approx(a1, abs=1e-6)
    sled_edge = a0 - P.GAP
    assert lo_a > sled_edge
    assert pos["Y"] - sy / 2 == pytest.approx(b0, abs=1e-6) and pos["Y"] + sy / 2 == pytest.approx(b1, abs=1e-6)
    assert pos["Z"] == pytest.approx(-functional.FRONT_Y, abs=1e-6)
    assert t["Transform"]["Transform"]["Orientation"] == {"X": 0, "Y": 0, "Z": 0, "W": 1}


# ---------------------------------------------------------------------------------------------- P4-1 A': scripting
def test_programmable_scripting_component_matches_route(staged):
    """Route A': the server composition holds vanilla's InGameScriptingComponent bound to our full
    InGameScriptingDefinition, the server prefab its object builder (the starter program, not running). The client
    side carries none: the terminal's script UI is the server's (ProgrammableBlockDetailModelServer, a replicated
    [BlockDetailProvider]), and a client copy would run a saved Running program a second time."""
    assert config.PROGRAMMABLE_ROUTE == "A'"
    G = guids.Guids(guids.GUIDS_PATH)
    key, dguid = G.d["Programmable.ScriptingComponentId"], G.d["Programmable.InGameScriptingDefinition"]
    sc = _body(_stage(_file("_ServerComposition")))
    assert _inserts(sc["Components"])[key] == {"Definition": dguid, "Type": T_SCRIPTING}
    assert {s["$Key"]: s["$Value"] for s in sc["TagSlots"]["ModifiedKeys"]}["InGameScriptingComponent"] == key
    ob = _inserts(_body(_stage(_file("_Server.partialdef")))["_entity"]["ObjectBuilders"])[key]
    assert ob == {"$Type": scripting.OB_TYPE, "Script": scripting.TEMPLATE, "Running": False}
    for pat in ("_ClientComposition", "_Client.partialdef"):
        assert "InGameScripting" not in str(_stage(_file(pat))) and key not in str(_stage(_file(pat))), pat
    d = _stage(scripting.DEFINITION_FILE)
    assert d["$Type"] == scripting.DEFINITION_TYPE and "PartialDefinitionKind" not in d["$Value"]   # a full .def
    v = d["$Value"]
    assert v["Guid"] == dguid
    assert (v["EntryTypeName"], v["UpdateMethodName"]) == ("Program", "Update")
    # the code defaults (InGameScriptingDefinition.cs:427-457), written out: LoadScript reads every one
    assert {k: v[k] for k in scripting.LIMITS} == {
        "MaxInstructions": 50000, "MaxMethodStackSize": 1024, "MaxStackSize": 1048576,
        "MaxAccumulatedMemory": 5242880, "MaxInitMemory": 1048576, "MaxUpdateMemory": 102400}
    assert d["$Bundles"]["Game2"] == "2.4.0.95"


def test_programmable_scripting_lockeys_exist_in_vanilla():
    """The three LocKeys the component shows (no program, no constructor, compiled) are vanilla's own texts."""
    p = os.path.join(LOC_TEXTS, "MainGameTexts.loc-texts")
    if not os.path.exists(p):
        pytest.skip("game localisation not installed")
    texts = read_json(p)
    v = _stage(scripting.DEFINITION_FILE)["$Value"]
    for k in ("NoProgram", "NoConstructor", "ProgramCompileSuccess"):
        assert v[k] in texts, (k, v[k])


def test_starter_program_fits_the_entry_contract():
    """The starter program is the old-signature entry the definition names (OldScriptSignature.cs:41-60: a class
    EntryTypeName with a ctor (Entity) and a public Update()), and uses only the in-game whitelist's assemblies
    (GameApp.cs:496 [2.4: 465]: typeof(Entity) admits VRage.DCS)."""
    t = scripting.TEMPLATE
    assert re.search(r"^public class Program\b", t, re.M)
    assert re.search(r"public Program\(Entity \w+\)", t)
    assert re.search(r"public void Update\(\)", t)
    assert re.findall(r"^using ([\w.]+);", t, re.M) == ["Keen.VRage.DCS.Components"]
    assert "-loadScripts" in t                       # says why Run may fail, in the editor itself


# ---------------------------------------------------------------------------------------------- scripts off (data only)
def test_programmable_led_amber_data_only(staged):
    """P4-7, data-only: the client composition carries a BlockMaterialSwapper over our models that maps nothing, so
    with scripts off every lamp keeps its authored static amber (the status slot and the PSU slot are both amber)."""
    G = guids.Guids(guids.GUIDS_PATH)
    key = G.d[f"key/{PROG}/swapper"]
    cc = _body(_stage(_file("_ClientComposition")))
    sw = _inserts(cc["Components"])[key]
    assert sw["Type"] == integration.T_SWAPPER
    assert {s["$Key"]: s["$Value"] for s in cc["TagSlots"]["ModifiedKeys"]}["BlockMaterialSwapperComponent"] == key
    assert _inserts(_body(_stage(_file("_Client.partialdef")))["_entity"]["ObjectBuilders"])[key] is None
    d = _stage(integration.PROG_SWAPPER_FILE)
    assert d["$Type"] == integration.T_SWAPPER_DEF and d["$Value"]["Guid"] == sw["Definition"]
    assert d["$Value"]["WorkingReplacementsMeshParts"] == []
    models = staged["blocks"][PROG]["models"]
    assert d["$Value"]["WorkingReplacementModels"] == ["{G}" + models["NonFractured"], "{G}" + models["Fractured"]]
    man = read_json(os.path.join(config.MODELS_DIR, PROG, "export.json"))
    for variant in ("nonfractured", "fractured"):
        for lod in man[variant]["lods"][:2]:
            assert functional.PROG_LED in lod["materials"], (variant, lod["materials"])


def test_programmable_status_slot_is_its_own(staged):
    """Plan 4 Task 4: the script-status lamp and the LCD status bar have their own mesh part, so the scripts' green
    swap reaches them and nothing else (the rear PSU lamps keep EmissiveAmber). Data-only both slots map to the same
    vanilla amber, so the scripts-off block renders exactly as before the split."""
    assert functional.PROG_LED != functional.PROG_PSU_LAMP == "EmissiveAmber"
    assert MATERIAL_GUIDS[functional.PROG_LED] == MATERIAL_GUIDS[functional.PROG_PSU_LAMP]
    man = read_json(os.path.join(config.MODELS_DIR, PROG, "export.json"))
    for variant in ("nonfractured", "fractured"):
        lods = man[variant]["lods"]
        for lod in lods[:2]:            # the lamp, the bar and the PSU lamps are modelled at LOD0-1
            assert {functional.PROG_LED, functional.PROG_PSU_LAMP} <= set(lod["materials"]), (variant, lod)
        assert functional.PROG_LED in lods[2]["materials"]          # LOD2: the LCD window quad stands in for the bar
    # the .model files map the status slot to the amber material (what the game renders in data-only mode)
    for variant, rel in (("NonFractured", f"{PROG}.model"), ("Fractured", f"{PROG}_Fractured.model")):
        m = _stage(f"{config.NAME}/{PROG}/Models/{variant}/{rel}")["$Value"]
        assigned = {a["MaterialName"]: a["MaterialReference"] for a in m["MaterialAssignments"]}
        assert assigned[functional.PROG_LED] == MATERIAL_GUIDS["EmissiveAmber"][0], variant
    # the swapper the script fills targets models that really carry that mesh part
    d = _stage(integration.PROG_SWAPPER_FILE)["$Value"]
    models = staged["blocks"][PROG]["models"]
    assert set(d["WorkingReplacementModels"]) == {"{G}" + models["NonFractured"], "{G}" + models["Fractured"]}


def test_programmable_scripts_off_is_safe(staged):
    """With scripts off the scripting component is inert and harmless: nothing auto-runs (Running false, so
    OnAddedToScene compiles nothing), and every definition field LoadScript dereferences is populated."""
    ob = _inserts(_body(_stage(_file("_Server.partialdef")))["_entity"]["ObjectBuilders"])
    assert [v for v in ob.values() if v and v.get("$Type") == scripting.OB_TYPE][0]["Running"] is False
    v = _stage(scripting.DEFINITION_FILE)["$Value"]
    for k in ("EntryTypeName", "UpdateMethodName", "NoProgram", "NoConstructor", "ProgramCompileSuccess") + \
            scripting.LIMITS:
        assert v.get(k), k


def test_programmable_lcd_state_neutral():
    """P4-7: the baked management LCD and lamp legend read the same in both modes (no OFFLINE, no N/A)."""
    face = read_json(config.REPORT_PATH)["blocks"][PROG]["face"]
    assert face["lcd"] == ["SCRIPT HOST", "PRG-06"]
    assert face["lamp_legend"] == ["SCRIPT", "STATUS"]
    assert face["status_lamp"] == functional.PROG_LED


# ---------------------------------------------------------------------------------------------- breakable or not
BREAKABLE_KEY = "bc5652a0-1296-4040-adc3-a2b9c35d5afc"   # BreakableBlockComponent (dc/integration.py BREAKABLE_KEY)


@pytest.fixture(scope="module", params=[False, True], ids=["non_breakable", "breakable"])
def prog_from_clone(request, tmp_path_factory):
    """The Programmable staged from its fresh structural clone (BreakableBlockComponent present) into a scratch dir,
    once kept breakable (as shipped since Plan 2 Task 9b: real fracture and damaged models, ensure_breakable) and
    once forced through make_non_breakable (the exception path): every Programmable patch must hold either way."""
    import shutil
    from test_fresh_clone import _fresh_clone
    breakable = request.param
    tmp = tmp_path_factory.mktemp("prog_breakable" if breakable else "prog_plain")
    mod_assets, stage = str(tmp / "Assets"), str(tmp / "staged")
    shutil.copytree(config.MOD_ASSETS, mod_assets)
    gpath = str(tmp / "asset_guids.json")
    shutil.copy2(guids.GUIDS_PATH, gpath)
    _fresh_clone(PROG, mod_assets)
    for rel in integration.PROG_STAGED_ONLY:
        for f in (rel, rel + ".meta"):
            if os.path.exists(os.path.join(mod_assets, f)):
                os.remove(os.path.join(mod_assets, f))
    keeps = integration.keeps_breakable
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "MOD_ASSETS", mod_assets)
    mp.setattr(config, "STAGE_ASSETS", stage)
    mp.setattr(integration, "Guids", lambda: guids.Guids(gpath))
    # since Plan 2 Task 9b the Programmable really fractures (keeps_breakable is True for it): the non_breakable run
    # forces it through make_non_breakable (the exception path) so both orders stay covered
    mp.setattr(integration, "keeps_breakable", lambda man: breakable if man["name"] == PROG else keeps(man))
    try:
        integration.write_all()
    finally:
        mp.undo()
    files = {pat: _body(read_json(os.path.join(stage, _file(pat))))
             for pat in ("_ServerComposition", "_ClientComposition", "_Server.partialdef", "_Client.partialdef")}
    return breakable, files


def test_programmable_patches_hold_with_or_without_breakable(prog_from_clone):
    """With the BreakableBlockComponent kept or stripped, every Insert lands on its own key (Keys[Index]), the
    indices are in range and unique, no key is both kept and Removed, the prefabs list exactly their composition's
    keys, and every tag slot points at a kept component."""
    breakable, f = prog_from_clone
    G = guids.Guids(guids.GUIDS_PATH)
    script_key, swap_key = G.d["Programmable.ScriptingComponentId"], G.d[f"key/{PROG}/swapper"]
    want = {"Server": {integration.POWERABLE_KEY: integration.T_POWERABLE, script_key: T_SCRIPTING},
            "Client": {integration.POWERABLE_KEY: integration.T_POWERABLE, swap_key: integration.T_SWAPPER}}
    for side in ("Server", "Client"):
        comp, prefab = f[f"_{side}Composition"], f[f"_{side}.partialdef"]["_entity"]["ObjectBuilders"]
        for delta in (comp["Components"], prefab):
            idx = [c["Index"] for c in delta["Changed"]]
            assert len(idx) == len(set(idx)) and all(0 <= i < len(delta["Keys"]) for i in idx), side
            assert not set(delta["Keys"]) & set(delta.get("Removed", [])), side
            assert (BREAKABLE_KEY in delta["Keys"]) == breakable, side
            assert (BREAKABLE_KEY in delta.get("Removed", [])) != breakable, side
            assert STRUCTURAL_KEY in delta["Removed"] and STRUCTURAL_KEY not in delta["Keys"]
        assert {k: v["Type"] for k, v in _inserts(comp["Components"]).items()} == want[side], side
        assert set(_inserts(prefab)) == set(want[side]), side
        assert prefab["Keys"] == comp["Components"]["Keys"], side
        slots = {s["$Key"]: s["$Value"] for s in comp["TagSlots"]["ModifiedKeys"]}
        assert set(slots.values()) <= set(comp["Components"]["Keys"]), side
        assert (set(integration.BREAKABLE_SLOTS) <= set(comp["TagSlots"]["RemovedKeys"])) != breakable, side
    sob = _inserts(f["_Server.partialdef"]["_entity"]["ObjectBuilders"])
    assert sob[script_key]["$Type"] == scripting.OB_TYPE and sob[integration.POWERABLE_KEY]["Enabled"] is True


# ---------------------------------------------------------------------------------------------- Task 4: scripts on
SCRIPTS = os.path.join(config.MOD_DIR, "Scripts")
LED_INJECTOR = os.path.join(SCRIPTS, "Client", "Programmable", "ProgrammableLedInjector.cs")
PROBE = os.path.join(config.MOD_DIR, "Source", "Model", "review", "probe_scripts.csx")


def _text(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


@pytest.mark.scripts
def test_led_injector_names_the_data_through_dcguids():
    """P4-7 with scripts on: the injector targets exactly our swapper, mesh part and green, and only through the
    generated DcGuids (no literal GUID or slot name that could drift from the data)."""
    t = _text(LED_INJECTOR)
    for const in ("DcGuids.ProgrammableSwapper", "DcGuids.ProgrammableStatusMeshPart", "DcGuids.EmissiveGreenMaterial"):
        assert const in t, const
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", t), "no literal GUIDs: use DcGuids"
    assert f'"{functional.PROG_LED}"' not in t
    assert "SimpleDefinitionPostProcessor<BlockMaterialSwapperDefinition>" in t
    assert "REFLECTION: re-check after a game update" in t


def test_no_route_b_injection_under_a_prime():
    """Ruling P4-1 = A': the scripting component is in the data, so no script adds it (no AddComponent of it, no
    ProgrammableInjector) and no script carries a copy of the starter program (the data's scripting.TEMPLATE is the
    one source)."""
    assert config.PROGRAMMABLE_ROUTE == "A'"
    for dp, _, fs in os.walk(SCRIPTS):
        for f in fs:
            if f.endswith(".cs"):
                t = _text(os.path.join(dp, f))
                assert f != "ProgrammableInjector.cs" and "class ProgrammableInjector" not in t, f
                assert not re.search(r"AddComponent\([^;]*InGameScriptingComponent", t), f
                assert not re.search(r"\bclass Program\b", t), f


def test_probe_matches_the_data():
    """The in-game probe (a .csx, it cannot see DcGuids) names the same status mesh part as the data."""
    assert f'const string StatusPart = "{functional.PROG_LED}";' in _text(PROBE)
