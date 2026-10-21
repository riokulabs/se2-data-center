"""Task 8: the KVM console (animated pop-out drawer + fold-up screen) and the programmable server shell.

KVM (DC_Srv_KVM, a ControlPanel25 clone: terminal access kept). Two subparts (dc/subparts.py):
  KvmDrawer  spawned by ConditionalSubParts at the block-model dummy "KvmDrawer"; TranslationAnimation 0.45 m forward;
  KvmScreen  a child entity nested in the drawer's prefab, its hinge = the drawer model's dummy "KvmScreen";
             RotationAnimation folding up 100 deg about the hinge (game +X).
Trigger: FunctionalBlockAnimationControllerComponent (Working) on the client composition, data-only. Both animations
take the same time, so the open and the close follow the same (simultaneous) path.

Programmable (DC_Srv_Programmable, a WallInsertPanel clone): a blade chassis; its status LED is the static amber
vanilla ColorIndicatorMaterial (no blink). Plan 4 Task 3 made it a functional On/Off blade with the vanilla scripting
component in data (Tests/test_programmable_data.py).

No definition anywhere under DataCenter/ may reference a type outside the Game2: / VRage: bundles (no mod-assembly,
i.e. script-only, types: a save must load without -loadScripts)."""
import json
import os

import pytest

from dc import catalog, clone, config, integration, subparts
from dc.assetio import own_guid, read_json
from dc.material_guids import MATERIAL_GUIDS

KVM, PROG = "DC_Srv_KVM", "DC_Srv_Programmable"
SDK_MATERIALS = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/"
                                   "GameData/Vanilla/Assets/BlockMaterials")


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


def _stage(rel):
    p = os.path.join(config.STAGE_ASSETS, rel)
    assert os.path.exists(p), f"not staged: {rel}"
    return read_json(p)


def _body(d):
    v = d["$Value"]
    return v["Manipulator"] if "PartialDefinitionKind" in v else v


def _dummies(block_like):
    """{name: dummy} from a Dummies field (plain list or delta-encoded Insert list)."""
    d = block_like["Dummies"]
    items = d["Changed"] if isinstance(d, dict) else [{"Value": x} for x in d]
    return {c["Value"]["Name"]: c["Value"] for c in items}


def _by_guid(guid):
    """The staged definition file whose own GUID is guid."""
    for dp, _, fs in os.walk(integration.STAGE):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                d = read_json(os.path.join(dp, f))
                if own_guid(d) == guid:
                    return d
    raise AssertionError(f"no staged definition {guid}")


def _report(name):
    e = read_json(config.REPORT_PATH)["blocks"][name]
    assert e.get("placement", {}).get("total"), f"{name} not built"
    return e


# ---------------------------------------------------------------------------------------------- KVM subparts
def test_kvm_subparts(staged):
    """Dummies: the block model has KvmDrawer (its type spawns the drawer prefab), the drawer model has KvmScreen (the
    hinge; the prefab's nested screen child sits exactly there). Both subpart models are staged (FBX per LOD, no
    collision, vanilla material GUIDs) and referenced by their ModelComponentDefinitions."""
    info = clone.entry(catalog.BY_NAME[KVM])["info"]
    bmd = _body(_stage(info["model_def_file"]))
    dums = _dummies(bmd)
    assert subparts.DRAWER in dums, sorted(dums)
    drawer_dummy = dums[subparts.DRAWER]
    pos = drawer_dummy["Transform"]["Transform"]["Position"]
    assert [pos[k] for k in "XYZ"] == pytest.approx(subparts.drawer_dummy_game(), abs=1e-6)
    assert drawer_dummy["Transform"]["Transform"]["Orientation"] == {"X": 0, "Y": 0, "Z": 0, "W": 1}

    s = staged["blocks"][KVM]["subparts"]
    cs = _by_guid(s["conditional_subparts"])
    assert cs["$Type"].endswith("ConditionalSubPartsDefinitionObjectBuilder")
    assert _body(cs)["SubParts"] == {drawer_dummy["Type"]: s["prefab"]}

    prefab = _body(_by_guid(s["prefab"]))
    ob = prefab["_entity"]["ObjectBuilders"]
    hier = [c["Value"] for c in ob["Changed"] if c["Kind"] == "Update" and c["Index"] == 0][0]
    kids = hier["Children"]["Changed"]
    assert len(kids) == 1 and kids[0]["Value"]["DebugName"] == subparts.SCREEN
    child = kids[0]["Value"]
    ct = [b["Value"] for b in child["ObjectBuilders"] if b["Value"] and "ChildTransform" in b["Value"]["$Type"]][0]
    child_pos = ct["TransformWithEulerHint"]["Transform"]["Position"]

    for name in (subparts.DRAWER, subparts.SCREEN):
        sp = s["models"][name]
        mc = _body(_by_guid(sp["model_component"]))
        mrel = sp["model_rel"]
        assert mc["Model"] == "{G}" + integration.asset_id(mrel)
        ma = _stage(mrel)["$Value"]
        assert ma["CollisionShapesAsset"]["AssetReference"] is None      # visual only (vanilla subparts)
        folder = os.path.dirname(mrel)
        files = {integration.asset_id(f"{folder}/{f}") for f in os.listdir(os.path.join(config.STAGE_ASSETS, folder))
                 if f.endswith(".fbx")}
        assert len(ma["GeometryAssets"]) == len(files) >= 2
        for ga in ma["GeometryAssets"]:
            assert ga["AssetReference"][3:] in files
            assert ga["Transformations"]["Translation"] == {"X": 0, "Y": 0, "Z": 0}   # the FBX origin is the pivot
        for a in ma["MaterialAssignments"]:
            assert a["MaterialReference"] in {g for g, _ in MATERIAL_GUIDS.values()}, a
        if name == subparts.DRAWER:
            hinge = _dummies(mc)[subparts.SCREEN]
            hp = hinge["Transform"]["Transform"]["Position"]
            assert [hp[k] for k in "XYZ"] == [child_pos[k] for k in "XYZ"]
            assert child["Definition"] == s["composites"][subparts.SCREEN]


def test_kvm_animations(staged):
    """Drawer: TranslationAnimation 0.45 m along game -Z (block forward). Screen: RotationAnimation about game +X by
    about 100 deg (folds UP). Equal durations: the close is the open played backwards (no lid standing in the rack
    while the drawer is already in)."""
    s = staged["blocks"][KVM]["subparts"]
    tr = _body(_by_guid(s["animations"][subparts.DRAWER]))
    rot = _body(_by_guid(s["animations"][subparts.SCREEN]))
    assert _by_guid(s["animations"][subparts.DRAWER])["$Type"].endswith("TranslationAnimationDefinitionObjectBuilder")
    assert _by_guid(s["animations"][subparts.SCREEN])["$Type"].endswith("RotationAnimationDefinitionObjectBuilder")
    t = tr["Translation"]
    assert (t["X"], t["Y"]) == (0, 0) and t["Z"] == pytest.approx(-0.45, abs=0.02)
    assert rot["RotationAxis"] == {"X": 1, "Y": 0, "Z": 0}
    assert 95 <= rot["RotationAngle"] <= 105
    assert abs(t["Z"]) / tr["Speed"] == pytest.approx(rot["RotationAngle"] / rot["AngularSpeed"], rel=1e-6)
    # composites: a copy of vanilla Subpart_Composite plus exactly one rigid animation each
    for name, comp in (("Translation", s["composites"][subparts.DRAWER]), ("Rotation", s["composites"][subparts.SCREEN])):
        c = _body(_by_guid(comp))
        ins = [x["Value"]["Type"] for x in c["Components"]["Changed"] if x["Kind"] == "Insert"]
        assert ins == [f"VRage:Keen.VRage.Core.Game.GameSystems.RigidAnimations.{name}AnimationComponent"]
        assert {m["$Key"] for m in c["TagSlots"]["ModifiedKeys"]} == {"RigidAnimationComponent"}


def test_kvm_trigger_is_working_toggle(staged):
    """Client composition: ConditionalSubPartsComponent (our definition) + FunctionalBlockAnimationControllerComponent
    (definition null), with tag slots; the client prefab carries a null object builder for each new component."""
    info = clone.entry(catalog.BY_NAME[KVM])["info"]
    cc_file = integration._block_files(catalog.BY_NAME[KVM], "_ClientComposition")[0]
    cc = _body(_stage(cc_file))
    comps = {x["Value"].get("Type"): x["Value"].get("Definition") for x in cc["Components"]["Changed"]
             if x["Kind"] == "Insert"}
    s = staged["blocks"][KVM]["subparts"]
    assert comps[integration.T_CONDSUB] == s["conditional_subparts"]
    assert comps[integration.T_ANIMCTL] is None
    slots = {m["$Key"] for m in cc["TagSlots"]["ModifiedKeys"]}
    assert {"ConditionalSubPartsComponent", "FunctionalBlockAnimationControllerComponent"} <= slots
    keys = cc["Components"]["Keys"]
    cl_file = integration._block_files(catalog.BY_NAME[KVM], "_Client.partialdef")[0]
    ob = _body(_stage(cl_file))["_entity"]["ObjectBuilders"]
    assert ob["Keys"] == keys
    assert info["model_def"]


def test_kvm_popped_envelope():
    """Built geometry (build_report "subparts"): the popped-out screen rises into the slot above (the user's decision)
    and its rearmost point above this slot stays in front of the neighbour's front hardware (ears, handles: max y
    0.4145); stowed, both subparts stay inside the slot box and the front zone like any server."""
    e = _report(KVM)["subparts"]
    env = e["envelope"]
    assert env["stowed"]["max_y"] <= 0.375 + 0.06
    assert env["stowed"]["min_z"] >= -0.125 and env["stowed"]["max_z"] <= 0.125 - 0.006
    assert env["popped"]["max_z"] > 0.125 + 0.08                     # covers the slot above (taller than v2)
    assert env["popped_rear_y_above_slot"] >= 0.4145 + 0.01            # clears the neighbour's handles
    assert env["popped"]["max_y"] <= 0.375 + 0.25 + 0.45               # out of the rack front zone: doors open
    assert e["screen_height"] > 0.17 * 1.5                             # v2 lid was 0.17 m


@pytest.mark.parametrize("sub", [subparts.DRAWER, subparts.SCREEN])
def test_kvm_subpart_limits(sub):
    """Each subpart model against its own Keen limits (size-keyed): LOD count, tris, materials, last LOD a box."""
    from se2model import limits
    e = _report(KVM)["subparts"]["models"][sub]
    lods = e["lods"]
    n = limits.model_limits(tuple(e["model_size"]), lods[0]["tris"])["optimal_lods"]
    assert len(lods) == n >= 2, (len(lods), n)
    for i, l in enumerate(lods):
        assert l["tris"] <= l["max_tris"], (i, l)
        assert l["materials"] <= l["max_materials"], (i, l)
    assert lods[-1]["tris"] <= 32 and lods[-1]["materials"] == 1


# ---------------------------------------------------------------------------------------------- programmable
def test_programmable_status_led_static_amber():
    """The 'scripting unavailable' LED slot maps to a vanilla static amber indicator material (no blink)."""
    g, rel = MATERIAL_GUIDS["EmissiveAmber"]
    if not os.path.isdir(SDK_MATERIALS):
        pytest.skip("Mod SDK not installed")
    v = read_json(os.path.join(SDK_MATERIALS, rel))["$Value"]
    assert v["Guid"] == g
    assert not v.get("AnimationParameters")
    p = v["Color"]["PackedValue"]
    r, gg, b = p & 255, (p >> 8) & 255, (p >> 16) & 255
    assert r > gg > b == 0, (r, gg, b)                                 # amber
    man = read_json(os.path.join(config.MODELS_DIR, PROG, "export.json"))
    for variant in ("nonfractured", "fractured"):
        for lod in man[variant]["lods"][:2]:
            assert "EmissiveAmber" in lod["materials"], (variant, lod["materials"])


def test_programmable_blade_face():
    """The blade chassis: six sleds (one pulled for service). Since Plan 4 Task 3 the block is functional (an On/Off
    Powerable with the vanilla scripting component in data): Tests/test_programmable_data.py."""
    assert catalog.BY_NAME[PROG].functional
    e = _report(PROG)
    assert e["face"]["sleds"] == 6 and e["face"]["proud_sled"] is not None


# ---------------------------------------------------------------------------------------------- save safety
def _types(x, out):
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("$Type", "Type", "UseActionType") and isinstance(v, str) and ":" in v:
                out.add(v)
            _types(v, out)
    elif isinstance(x, list):
        for v in x:
            _types(v, out)
    return out


def test_no_script_types_in_definitions(staged):
    """Every type named by a DataCenter definition (staged package and installed mod) lives in the game's own
    Game2: / VRage: bundles, never in a mod assembly."""
    roots = [integration.STAGE, os.path.join(config.MOD_ASSETS, config.NAME)]
    seen = 0
    for root in roots:
        for dp, _, fs in os.walk(root):
            for f in fs:
                if not f.endswith((".def", ".partialdef", ".model")):
                    continue
                d = read_json(os.path.join(dp, f))
                for t in _types(d, set()):
                    seen += 1
                    assert t.split(":", 1)[0] in ("Game2", "VRage"), (os.path.join(dp, f), t)
                for b in d.get("$Bundles", {}):
                    assert b in ("Game2", "VRage", "System.Runtime"), (os.path.join(dp, f), b)
    assert seen > 500


# ---------------------------------------------------------------------------------------------- Ruling 15: On/Off
TIMER50 = os.path.join(config.VANILLA_REF, "Blocks", "Timer", "50")
SDK_TEMPLATES = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/"
                                   "GameData/Vanilla/Assets/Templates")


def _vanilla_template(rel):
    p = os.path.join(SDK_TEMPLATES, rel)
    if not os.path.exists(p):
        pytest.skip(f"Mod SDK missing {rel}")
    return read_json(p)


def test_kvm_has_vanilla_onoff(staged):
    """The KVM's server and client compositions carry vanilla's On/Off component exactly as Timer50's chain does
    (Templates/BasePowerableBlockBreakable_*: key 4f2bc5f9 = PowerableBlockComponent), bound to the KVM's own block
    definition, now a PowerableBlockDefinition with no consumed resource (always supplied); the prefabs spawn it Off
    (Enabled = false: Ruling 15 amended 2026-10-18, a new KVM is stowed); the old FunctionalBlockComponent key is gone
    and no tag slot points at it."""
    spec = catalog.BY_NAME[KVM]
    van = _body(_vanilla_template("BasePowerableBlockBreakable_ServerComposition.partialdef"))
    vc = van["Components"]
    ins = {vc["Keys"][c["Index"]]: c["Value"] for c in vc["Changed"] if c["Kind"] == "Insert"}
    assert ins[integration.POWERABLE_KEY]["Type"] == integration.T_POWERABLE
    bd_file = clone.entry(spec)["info"]["block_def_file"]
    bd = _stage(bd_file)["$Value"]
    assert bd["DefinitionType"] == integration.T_POWERABLE_DEF
    assert bd["BaseDefinition"] == integration.POWERABLE_DEF_BASE
    assert bd["Manipulator"]["ConsumedResource"] is None
    for pat in ("_ServerComposition", "_ClientComposition"):
        c = _body(_stage(integration._block_files(spec, pat)[0]))
        keys = c["Components"]["Keys"]
        assert integration.POWERABLE_KEY in keys and integration.FUNCTIONAL_KEY not in keys
        assert integration.FUNCTIONAL_KEY in c["Components"]["Removed"]
        v = [x["Value"] for x in c["Components"]["Changed"] if x["Index"] == keys.index(integration.POWERABLE_KEY)][0]
        assert v == {"Definition": bd["Manipulator"]["Guid"], "Type": integration.T_POWERABLE}
        assert all(m["$Value"] != integration.FUNCTIONAL_KEY for m in c["TagSlots"]["ModifiedKeys"])
    for pat in ("_Server.partialdef", "_Client.partialdef"):
        ob = _body(_stage(integration._block_files(spec, pat)[0]))["_entity"]["ObjectBuilders"]
        v = [x["Value"] for x in ob["Changed"] if x["Index"] == ob["Keys"].index(integration.POWERABLE_KEY)][0]
        assert v["$Type"] == integration.OB_POWERABLE and v["Enabled"] is False
    # Timer50 (a vanilla block with On/Off) gets the same component from the same template chain:
    # Timer50_ServerComposition -> Templates/Blocks/Breakable/Timers_ServerComposition -> BasePowerable...Composition
    t = read_json(os.path.join(TIMER50, "Timer50_ServerComposition.partialdef"))["$Value"]
    timers = _body(_vanilla_template("Blocks/Breakable/Timers_ServerComposition.partialdef"))
    tv = _vanilla_template("Blocks/Breakable/Timers_ServerComposition.partialdef")["$Value"]
    assert t["BaseDefinition"] == timers["Guid"] and tv["BaseDefinition"] == van["Guid"]
    assert integration.POWERABLE_KEY in timers["Components"]["Keys"] or integration.POWERABLE_KEY in vc["Keys"]


def test_kvm_spawns_off_stowed(staged):
    """Ruling 15 amended 2026-10-18 (in-game: "when placed it's open"): a newly placed KVM spawns Off, so not Working,
    so stowed in both script modes (the FBAC follows Working; the sequencer starts stowed and targets Working). The
    initial state is the prefab's PowerableBlockObjectBuilder.Enabled (PowerableBlockComponent.Init reads ob.Enabled,
    PowerableBlockComponent.cs:303-307); a saved KVM keeps its own serialized Enabled (:340-345), so existing worlds do
    not change. The Programmable keeps vanilla's built-ON default."""
    assert integration.KVM_SPAWN_ENABLED is False
    for name, want in ((KVM, False), (PROG, True)):
        spec = catalog.BY_NAME[name]
        for pat in ("_Server.partialdef", "_Client.partialdef"):
            ob = _body(_stage(integration._block_files(spec, pat)[0]))["_entity"]["ObjectBuilders"]
            v = [x["Value"] for x in ob["Changed"] if x["Index"] == ob["Keys"].index(integration.POWERABLE_KEY)][0]
            assert v["Enabled"] is want, (name, pat)


def test_functional_servers_are_terminal_listed(staged):
    """In-game: "the KVM doesn't show up in the block list in the grid console". The grid console lists a block only
    when its composition has a FunctionalBlockComponent whose tags carry no NO_TERMINAL* tag
    (StreamedControlPanelSessionComponent.IsBlockEligible, Game2.Simulation
    Keen.Game2.Simulation.StreamedUI.Terminal.ControlPanel/StreamedControlPanelSessionComponent.cs:651-656).
    ControlPanel25 tags its FunctionalBlockComponent NO_TERMINAL_FUNCTIONAL; the Ruling 15 chain drops it. No
    staged DataCenter composition may carry a NO_TERMINAL* tag slot at all (none of our blocks is meant to hide), and
    the two servers we rebase onto vanilla's PowerableBlockComponent carry it in both compositions (Timer, EventCtl,
    UPS and Status inherit theirs from vanilla templates without NO_TERMINAL slots)."""
    for dp, _, fs in os.walk(config.STAGE_ASSETS):
        for f in fs:
            if f.endswith("Composition.partialdef"):
                c = _body(read_json(os.path.join(dp, f)))
                tags = [m["$Key"] for m in c.get("TagSlots", {}).get("ModifiedKeys", [])]
                assert not any(t.startswith("NO_TERMINAL") for t in tags), (f, tags)
    for name in (KVM, PROG):   # ours: rebased onto the PowerableBlockComponent in data
        spec = catalog.BY_NAME[name]
        for pat in ("_ServerComposition", "_ClientComposition"):
            c = _body(_stage(integration._block_files(spec, pat)[0]))
            assert integration.POWERABLE_KEY in c["Components"]["Keys"], (name, pat)


def test_retarget_slots_drops_no_terminal():
    """_retarget_slots: ControlPanel25's slot on the FunctionalBlockComponent is dropped, not moved; idempotent."""
    comp = {"TagSlots": {"$DeltaEncoded": True, "RemovedKeys": [], "ModifiedKeys": [
        {"$Key": "GridBlockComponent", "$Value": integration.FUNCTIONAL_KEY},
        {"$Key": "NO_TERMINAL_FUNCTIONAL", "$Value": integration.FUNCTIONAL_KEY},
        {"$Key": "Other", "$Value": "x"}]}}
    for _ in range(2):
        integration._retarget_slots(comp)
        mk = {m["$Key"]: m["$Value"] for m in comp["TagSlots"]["ModifiedKeys"]}
        assert "NO_TERMINAL_FUNCTIONAL" not in mk
        assert mk["GridBlockComponent"] == integration.POWERABLE_KEY and mk["Other"] == "x"


def test_kvm_animation_controller_drives_both_subparts(staged):
    """The client composition's FunctionalBlockAnimationController toggles every rigid animation under the block:
    the conditional-subparts definition it sits beside spawns the drawer prefab, whose composite carries the
    Translation and whose nested child (the screen composite) carries the Rotation."""
    spec = catalog.BY_NAME[KVM]
    s = staged["blocks"][KVM]["subparts"]
    cc = _body(_stage(integration._block_files(spec, "_ClientComposition")[0]))
    types = {x["Value"].get("Type"): x["Value"].get("Definition") for x in cc["Components"]["Changed"]
             if x["Kind"] == "Insert"}
    assert integration.T_ANIMCTL in types and types[integration.T_CONDSUB] == s["conditional_subparts"]
    cs = _body(_by_guid(s["conditional_subparts"]))
    prefab = _body(_by_guid(list(cs["SubParts"].values())[0]))
    assert prefab["_entity"]["Definition"] == s["composites"][subparts.DRAWER]
    child = [c["Value"] for c in prefab["_entity"]["ObjectBuilders"]["Changed"] if c["Index"] == 0][0]
    assert child["Children"]["Changed"][0]["Value"]["Definition"] == s["composites"][subparts.SCREEN]
    for sub, kind in ((subparts.DRAWER, "Translation"), (subparts.SCREEN, "Rotation")):
        comp = _body(_by_guid(s["composites"][sub]))
        assert [x["Value"]["Type"] for x in comp["Components"]["Changed"] if x["Kind"] == "Insert"] == [
            f"VRage:Keen.VRage.Core.Game.GameSystems.RigidAnimations.{kind}AnimationComponent"]


# ---------------------------------------------------------------------------------------------- KVM use-to-toggle
# Plan 4 Task 9 (Ruling P4-8a): Use on the drawer pops the console out or stows it, data-only (dc/functional.py
# KVM_TOGGLE has the design and the vanilla citations).
SDK_ASSETS = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/"
                                "GameData/Vanilla/Assets")


def _game_box(d):
    """(lo, hi) of a staged dummy's box in the .model's game frame (identity orientation)."""
    p, s = d["Transform"]["Transform"]["Position"], d["Scale"]
    return tuple(tuple(p[k] + sg * s[k] / 2 for k in "XYZ") for sg in (-1, 1))


def _inside(pt, box):
    return all(lo - 1e-9 <= c <= hi + 1e-9 for c, lo, hi in zip(pt, *box))


def test_kvm_use_toggle_dummy(staged):
    """The KVM's model carries a vanilla UsePowerable use box (the type the player's UseActionBindings map to
    UsePowerableAction: Use flips PowerableBlockComponent.Enabled, the Ruling 15 On/Off) over the drawer band, and
    the Terminal box shrinks to the upper modules. The two never overlap, both sit inside the 6U face, the toggle is
    the last dummy (it wins a tie) and is supported by the front fracture zone it sits in; no subpart model carries
    one (UsePowerableAction gets PowerableBlockComponent from the dummy's own entity: a subpart has none)."""
    from dc import functional as FN
    bind = os.path.join(SDK_ASSETS, "System", "UseActions", "UseActionBindings.def")
    act = os.path.join(SDK_ASSETS, "System", "UseActions", "UsePowerableAction.def")
    if not (os.path.exists(bind) and os.path.exists(act)):
        pytest.skip("Mod SDK use actions missing")
    action = read_json(act)["$Value"]
    assert read_json(bind)["$Value"]["DummyTypesMap"][FN.USE_POWERABLE_TYPE] == action["Guid"]
    assert action["UseActionType"].endswith(".UsePowerableAction")

    spec = catalog.BY_NAME[KVM]
    bmd = _body(_stage(clone.entry(spec)["info"]["model_def_file"]))["Dummies"]
    order = {c["Value"]["Name"]: c["Index"] for c in bmd["Changed"]}
    dums = _dummies({"Dummies": bmd})
    tog, term = dums[FN.KVM_TOGGLE], dums["Terminal"]
    assert tog["Type"] == FN.USE_POWERABLE_TYPE and term["Type"] == FN.USE_TERMINAL_TYPE
    assert [d["Name"] for d in dums.values() if d["Type"] == FN.USE_POWERABLE_TYPE] == [FN.KVM_TOGGLE]
    assert order[FN.KVM_TOGGLE] == max(order.values())
    tb, mb = _game_box(tog), _game_box(term)

    # the stowed drawer fascia (face, pull bar, latch tabs) lies inside the toggle box
    D = subparts.DRAWER_BOX
    for x in (-D["x"], D["x"]):
        for z in (D["z0"], D["z1"]):
            for y in (D["y_fascia"], D["y_front"] + 0.022):          # the fascia's back .. the pull bar's front
                assert _inside(subparts.to_game((x, y, z)), tb), (x, y, z)
    # the Terminal box: above the bay header lip, over the OSD window and the port bank (dc/servers/kvm.face)
    assert mb[0][1] >= subparts.BAY["z1"] + 0.006 - 1e-9
    for a, b in ((0.083, 0.050), (0.200, 0.089), (-0.212, 0.024), (-0.05, 0.101)):
        assert _inside(FN.face_to_game(a, b, 0.0), mb), (a, b)
    # disjoint (the vertical band split), inside the face (|x| <= 0.25 about the shift, the 6U band +-0.125)
    assert tb[1][1] < mb[0][1]
    for lo, hi in (tb, mb):
        assert lo[0] >= FN.SHIFT[0] - 0.25 - 1e-9 and hi[0] <= FN.SHIFT[0] + 0.25 + 1e-9
        assert lo[1] >= -0.125 - 1e-9 and hi[1] <= 0.125 + 1e-9
        assert -0.41 <= lo[2] and hi[2] <= -0.34                         # on the face: game z = -0.375 +- a slab

    # supported by the FRONT service module (Task 9c's 3-zone servers: Fracture_01 the critical core, Fracture_02
    # the front module, Fracture_03 the rear), the zone its centre lies in, as the face's Terminal is
    from dc import fracture
    man = read_json(os.path.join(config.MODELS_DIR, KVM, "export.json"))["fractured"]
    plan_front = [z for z in fracture._server(spec).zones if z.label.startswith("front service module")]
    assert len(plan_front) == 1 and not plan_front[0].critical
    fid = plan_front[0].id
    front = [z for z in man["zones"] if z["id"] == fid]
    assert len(front) == 1 and not front[0]["critical"]
    (a, b, d), _ = FN.DUMMIES[KVM][FN.KVM_TOGGLE]
    centre = (-a, FN.FRONT_Y + d, b)
    assert fracture.Plan.zone_at(man["zones"], centre) == fid
    assert tog["SupportingFracture"] == {"Id": fid}
    assert term["SupportingFracture"] == {"Id": fid}
    assert man["supporting"].get(FN.KVM_TOGGLE, fid) == fid and man["supporting"]["Terminal"] == fid
    lo, hi = front[0]["lo"], front[0]["hi"]
    assert all(l <= c <= h for c, l, h in zip((-a, FN.FRONT_Y + d - 0.01, b), lo, hi))

    # no subpart model carries a use box
    for sub in (subparts.DRAWER, subparts.SCREEN):
        mc = _body(_by_guid(staged["blocks"][KVM]["subparts"]["models"][sub]["model_component"]))
        ds = mc.get("Dummies") or []
        ds = ds.get("Changed", []) if isinstance(ds, dict) else [{"Value": x} for x in ds]
        assert all(c["Value"]["Type"] not in (FN.USE_POWERABLE_TYPE, FN.USE_TERMINAL_TYPE) for c in ds), sub


def _lid_point(s, f=1.0):
    """A point s metres up the lid from its hinge (Blender frame, x = 0) at the data-only pose f (f = 1: out, the
    same end pose as the scripted motion's)."""
    import math
    dy, ang = subparts.pose(f)
    a = math.radians(ang)
    return (0.0, subparts.HINGE[1] + dy + s * math.cos(a), subparts.HINGE[2] + s * math.sin(a))


def test_kvm_use_targets_feel_natural():
    """Where a standing player aims, they get the use they expect (dc/functional.kvm_use_target: the ray runs through
    the collision-less subparts to the face). Stowed, from any height: the pull bar pops it out, the OSD and the port
    bank open the terminal. Out, for eyes level with the KVM up to 0.6 m above it (a console you stand at): the
    screen's lower half (in front of this server's own face) opens the terminal, and the lid's bottom edge, the hinge
    over the drawer, stows it."""
    from dc import functional as FN
    eyes = [(0.0, FN.KVM_FACE_PLANE_Y + d, h) for d in (0.7, 1.2) for h in (-0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.9, 1.2)]
    bc = (subparts.DRAWER_BOX["z0"] + subparts.DRAWER_BOX["z1"]) / 2
    for e in eyes:
        assert FN.kvm_use_target(e, (0.0, subparts.DRAWER_BOX["y_front"] + 0.022, bc))[0] == FN.KVM_TOGGLE, e
        for a, b in ((0.14, 0.07), (-0.13, 0.05)):                  # the OSD window, the port-select keys
            assert FN.kvm_use_target(e, (-a, 0.40, b))[0] == "Terminal", (e, a, b)
    for e in [e for e in eyes if 0.0 <= e[2] <= 0.6]:
        assert FN.kvm_use_target(e, _lid_point(0.12))[0] == "Terminal", e
        assert any(FN.kvm_use_target(e, _lid_point(s))[0] == FN.KVM_TOGGLE for s in (0.0, 0.03, 0.06)), e
