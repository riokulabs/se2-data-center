"""Plan 5 Task 12a: the offline client/server composition walk (Tests/clientserver_walk.py) gates the racks' Path A.

The 2026-10-18 world-load failure ("Client component ... should not be on server compositions") came from
BindingsBasedClientServerInfo's SERVER walk reaching an unbound client prefab (the fan rotor) through the door's
DoorBlockCollider -> DoorPartsProvider -> ConditionalSubParts chain, and ConveyorGraphPostProcessor.ValidateClientTypes
rejecting its render components. clientserver_walk ports that walk over fully resolved definitions (vanilla SDK
Assets + the mod's Assets + this run's staging) and the validator; here it must:
  (a) pass the DataCenter package as staged today,
  (b) FAIL the 10-18 structure and the other server-side mistakes Path A could make,
  (c) pass the Path A rack structure (task-12-spike.md Q1 (a)-(d)),
  (d) pass vanilla (the whole SDK, and SlidingDoorNarrow250 / Gyroscope50 / Reactor250 walked explicitly), so the
      port is not over-strict.
"""
import copy
import io
import os
import subprocess
import tarfile
import uuid

import pytest

import clientserver_walk as csw
from dc import config, integration



@pytest.fixture(scope="module", autouse=True)
def _gate_inputs():
    """This module is the Path A safety gate: a missing input FAILS it (a skip would be a silent pass in a full-suite
    run). The SDK's vanilla Assets, tools/decompiled-current and its -extra tree must all exist."""
    missing = [f"{what}: {p}" for what, p in (("Mod SDK vanilla Assets (SE2_SDK_ASSETS)", csw.SDK_ASSETS),
                                               ("decompiled game (tools/decompiled-current)", csw.DECOMPILED_ROOTS[0]),
                                               ("extra decompile (tools/decompiled-<version>-extra)",
                                                csw.DECOMPILED_ROOTS[1]))
               if not os.path.isdir(p)]
    if missing:
        pytest.fail("client/server walk gate inputs missing (see tools/README.md 'Decompiling the game'):\n  "
                    + "\n  ".join(missing), pytrace=False)

T_BINDING = "VRage:Keen.VRage.Multiplayer.Data.PrefabBindingDefinitionObjectBuilder"
T_COMPOSITE = "VRage:Keen.VRage.DCS.Definitions.EntityCompositeDefinitionObjectBuilder"
T_PREFAB = "VRage:Keen.VRage.Core.Game.Definitions.PrefabDefinitionObjectBuilder"
T_CSP = "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Effects.ConditionalSubPartsDefinitionObjectBuilder"
T_PARTIAL = "VRage:Keen.VRage.ContentPipeline.Definitions.PartialDefinitionDiff"
C_MODEL = "VRage:Keen.VRage.Game.Components.Models.ModelComponent"
C_TRANSFORM = "VRage:Keen.VRage.Core.Game.Components.ChildTransformComponent"
C_HIERARCHY = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponent"
C_CSP = "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Effects.ConditionalSubPartsComponent"
OB_TRANSFORM = "VRage:Keen.VRage.Core.Game.Components.ChildTransformComponentObjectBuilder"
OB_HIERARCHY = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder"
SUBPART_COMPOSITE_TEMPLATE = "1297bc6b-92aa-430a-b702-195393d7f84e"   # SDK Templates/Blocks/Subparts/Subpart_Composite.def

DOOR_RACKS = ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
FAN_DOOR_RACKS = ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear")
OPEN_RACKS = ("DC_Rack42_Open", "DC_Rack24_Open")
VANILLA_BLOCKS = ("Blocks/Doors/SlideDoorNarrow/250/SlidingDoorNarrow250.partialdef",
                  "Blocks/Gyroscopes/Gyroscopes/50/Gyroscope50.partialdef",
                  "Blocks/Reactor/Reactor/250/Reactor250.partialdef")


# --------------------------------------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def types():
    return csw.TypeIndex()


@pytest.fixture(scope="module")
def vanilla():
    return csw.Universe([csw.SDK_ASSETS])


@pytest.fixture(scope="module")
def package():
    """The load as installed: vanilla, then the mod's Assets, then this run's staging over it (same relative path)."""
    integration.write_all()
    return csw.Universe([csw.SDK_ASSETS, config.MOD_ASSETS, config.STAGE_ASSETS])


@pytest.fixture(scope="module")
def package_walk(package):
    return csw.walk(package)


def res(u, g):
    """A private copy of a resolved definition (the Universe caches and shares its resolved values)."""
    return copy.deepcopy(u.resolve(g))


def run(u, types):
    w = csw.walk(u)
    return w, csw.validate(w, types)


def own(u, name, suffix):
    """GUID of the block's definition file <name>_<suffix> (in the block folder or its Subparts/)."""
    hits = [g for g, e in u.entries.items()
            if e[4].replace(os.sep, "/").endswith((f"/{name}/{name}_{suffix}", f"/{name}/Subparts/{name}_{suffix}"))]
    assert len(hits) == 1, (name, suffix, hits)
    return hits[0]


def has(u, name, suffix):
    return any(e[4].replace(os.sep, "/").endswith(f"/{name}/Subparts/{name}_{suffix}") for e in u.entries.values())


def guid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "dc-t12a/" + "/".join(parts)))


def as_def(type_, value):
    return {"$Type": type_, "$Value": value}


def errors_of(errs, code, composite):
    return [e for e in errs if e[0] == code and e[2] == composite]


def model_definition(u, composite):
    return next(d for _, t, d in csw.components(res(u, composite)) if t == C_MODEL)


def vanilla_binding(u, rel):
    hits = [g for g, e in u.entries.items() if e[4].replace(os.sep, "/").endswith("/" + rel)]
    assert len(hits) == 1, (rel, hits)
    return hits[0]


# ------------------------------------------------------------------------------------------------ type classification
def test_type_classification_follows_the_decompiled_attributes(types):
    """IsClientType = the assembly's [assembly: ClientAssembly] or a name ending in "Client"; [ServerOnly] is inherited
    down the class chain; NameMigration'd names resolve; an unknown type raises instead of passing."""
    k = types.classify("Game2:Keen.Game2.Client.GameSystems.Render.ModelRenderComponent")
    assert (k["assembly"], k["client"], k["server_only"]) == ("Game2.Client", True, False)
    k = types.classify("VRage:Keen.VRage.Audio.Components.SpatialAudioComponent")       # [assembly: ClientAssembly]
    assert (k["assembly"], k["client"]) == ("VRage.Audio", True), k
    k = types.classify("Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.Models.BlockModelComponent")
    assert (k["client"], k["server_only"]) == (False, False)
    assert types.classify("Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.Doors.DoorServerComponent")["server_only"]
    k = types.classify("Game2:Keen.Game2.Simulation.WorldObjects.Weapons.ProjectileWeaponComponent")
    assert k["server_only"] and "inherited from" in k["reason"], k                     # ProjectileWeaponBaseComponent
    k = types.classify("VRage:Keen.VRage.Physics.Components.FixedPhysicsConstraintComponent")   # 4.0.0.1401 rename
    assert k["type"] == "Keen.VRage.Physics.Components.SharedMotionPhysicsConstraintComponent"
    assert types.component_for_definition("Keen.VRage.Game.Components.Models.ModelComponentDefinition") \
        == "Keen.VRage.Game.Components.Models.ModelComponent"
    with pytest.raises(csw.UnknownType):
        types.classify("Game2:Keen.Game2.Client.NoSuchComponent")


def test_missing_decompile_fails_with_a_named_cause(tmp_path):
    """I1: a missing decompile root (decompiled-current or its -extra tree) raises MissingDecompile naming the path and
    the README recipe, instead of silently classifying fewer types."""
    gone = str(tmp_path / "decompiled-9.9-extra")
    with pytest.raises(csw.MissingDecompile, match="decompiled-9.9-extra.*README"):
        csw.TypeIndex([csw.DECOMPILED_ROOTS[0], gone])


def test_unparseable_and_duplicate_definition_files_are_errors(tmp_path, vanilla):
    """I2 / M1: a definition file that is not JSON, and a GUID defined by two files, are load errors (the pipeline
    rejects the first; DefinitionLoader throws "already contained" on the second), never silently dropped or
    last-wins."""
    root = tmp_path / "Assets"
    root.mkdir()
    (root / "Broken.def").write_text('{"$Type": "VRage:Keen.VRage.DCS.Definitions.EntityCompositeDefinitionObjectBuilder"')
    g = guid("dup")
    body = {"$Type": T_COMPOSITE, "$Value": {"Guid": g, "TagSlots": [], "Components": []}}
    for n in ("A.def", "B.def"):
        (root / n).write_text(__import__("json").dumps(body))
    u = csw.Universe([str(root)])
    w = csw.walk(u)
    codes = {(e[0], e[2]) for e in w.errors}
    assert ("unparseable", None) in codes and ("duplicate-guid", g) in codes, w.errors
    assert {e[0] for e in csw.validate(w, csw.TypeIndex(), only=lambda c: False)} >= {"unparseable", "duplicate-guid"}
    assert not [e for e in vanilla.load_errors], vanilla.load_errors[:5]      # the SDK has neither


def test_unresolved_references_are_counted(package_walk):
    """M6: GUIDs the walk meets that resolve to no loaded definition are not followed (an under-approximation); they
    are counted per (side, referring type, field) so a game update that moves definitions out of the SDK shows up."""
    counts = csw.unresolved(package_walk)
    report = csw.unresolved_report(package_walk)
    print(report)
    assert counts and all(n > 0 for n in counts.values())
    # none of them sits where a prefab is named (the walk would have lost a composite there)
    assert not [k for k in counts if any(w in str(k[2]) for w in ("Prefab", "SubPart", "Children", "Definition"))], \
        report
    assert report.startswith(f"{sum(counts.values())} unresolved")


def test_unknown_component_type_fails_loudly(package, types):
    """A component type the decompile does not define is an error, never a pass."""
    rack = "DC_Rack42_SplitFront"
    sc = res(package, own(package, rack, "LeftDoor_ServerComposition.def"))
    sc["Components"].append({"Key": guid("unknown"), "Value": {"Definition": None, "Type": "Game2:Keen.Game2.Nope"}})
    w, errs = run(package.derive(as_def(T_COMPOSITE, sc)), types)
    assert errors_of(errs, "unknown-type", sc["Guid"]), csw.format_errors(errs)


# ---------------------------------------------------------------------------------------------------------- (d) vanilla
def test_vanilla_passes(vanilla, types):
    """The whole vanilla SDK load passes the port (no false positive anywhere), every walked composite's every
    component type is classified, and the three named blocks are really walked."""
    w, errs = run(vanilla, types)
    assert not errs, csw.format_errors(errs, vanilla)
    assert len(w.bindings) > 1000 and len(w.server.composites) > 1000 and len(w.client.composites) > 1000
    for rel in VANILLA_BLOCKS:
        sc, _, cp = w.bindings[vanilla_binding(vanilla, rel)]
        assert sc in w.server.composites, rel
        assert csw.composition_of(res(vanilla, cp)) in w.client.composites, rel


def test_vanilla_door_and_gyro_reach_their_subparts(vanilla):
    """SlidingDoorNarrow250: the server walk follows DoorBlockCollider -> provider -> ConditionalSubParts and stops at
    the bound leaves (their client prefabs are blocked), whose server compositions it walks through the binding.
    Gyroscope50: the client walk reaches the unbound nested subparts (Root -> S2 -> S3) through hierarchy children."""
    w = csw.walk(vanilla)
    door_csp = [g for g, e in vanilla.entries.items()
                if e[4].endswith("SlidingDoorNarrow250_Client_ConditionalSubPartsDefinition.def")]
    assert len(door_csp) == 1 and door_csp[0] in w.server.definitions, door_csp
    for leaf in res(vanilla, door_csp[0])["SubParts"].values():
        comp = csw.composition_of(res(vanilla, leaf))
        assert comp in w.client.composites and comp not in w.server.composites, leaf
    gyro = {g: e for g, e in vanilla.entries.items() if "/Gyroscopes/Gyroscopes/50/Subparts/" in e[4]}
    nested = [g for g, e in gyro.items() if e[4].endswith(("Gyroscope50_S2.def", "Gyroscope50_S3.def"))]
    assert len(nested) == 2 and all(g in w.client.composites and g not in w.server.composites for g in nested)


# ------------------------------------------------------------------------------------------------------- (a) DataCenter
def test_datacenter_package_passes(package, package_walk, types):
    errs = csw.validate(package_walk, types)
    assert not errs, csw.format_errors(errs, package)
    dc = [b for b in package_walk.bindings if f"/{config.NAME}/" in package.origin(b).replace(os.sep, "/")]
    assert len(dc) >= 73, len(dc)          # every block (and the bound door leaves) is walked from its binding
    for b in dc:
        sc, _, cp = package_walk.bindings[b]
        assert sc in package_walk.server.composites
        assert csw.composition_of(res(package, cp)) in package_walk.client.composites


@pytest.mark.parametrize("rack", DOOR_RACKS)
def test_datacenter_door_racks_are_walked_through_the_door_chain(package, package_walk, rack):
    """Non-vacuity: the server walk reaches each door rack's ConditionalSubParts the way the game does (via the
    door collider's SubPartsProvider), so the fixtures below exercise the real path."""
    csp = own(package, rack, "Client_ConditionalSubPartsDefinition.def")
    assert csp in package_walk.server.definitions
    assert own(package, rack, "ConditionalSubPartsDoorPartsProviderDefinition.def") in package_walk.server.definitions


# ----------------------------------------------------------------------------------------------------- (b) must FAIL
FIX_1018 = "028c11723f133d7fabb3d7a664c50d90136e623c"   # DataCenter: rotors out of the door ConditionalSubParts


def committed_assets(tmp_path, rev):
    """The mod's committed Assets/DataCenter at `rev` (git archive into tmp), or skip without the history."""
    if subprocess.run(["git", "-C", config.MOD_DIR, "cat-file", "-e", f"{rev}^{{commit}}"],
                      capture_output=True).returncode != 0:
        pytest.skip(f"{rev} not in this clone's history")
    arc = subprocess.run(["git", "-C", config.MOD_DIR, "archive", rev, "Assets/" + config.NAME],
                         capture_output=True, check=True, timeout=300).stdout
    with tarfile.open(fileobj=io.BytesIO(arc)) as t:
        t.extractall(tmp_path, filter="data")
    return os.path.join(tmp_path, "Assets")


def test_the_real_10_18_package_fails_and_its_fix_passes(tmp_path, types):
    """The package exactly as committed when the world load failed (028c1172^) fails with the in-game message
    ("Client component ... should not be on server compositions") on the rotor composites, reached through
    DoorBlockCollider -> DoorPartsProvider -> ConditionalSubParts; the fix commit itself passes."""
    before = csw.Universe([csw.SDK_ASSETS, committed_assets(tmp_path / "before", FIX_1018 + "^")])
    w, errs = run(before, types)
    assert errs and {e[0] for e in errs} == {"client-type-on-server"}, csw.format_errors(errs, before)
    rotors = {e[2] for e in errs}
    assert len(rotors) == 2 and all(before.origin(r).endswith("_RackFan_Composite.partialdef") for r in rotors)
    assert all(any("ConditionalSubPartsDefinition" in step for step in e[3]) for e in errs)
    after = csw.Universe([csw.SDK_ASSETS, committed_assets(tmp_path / "after", FIX_1018)])
    w, errs = run(after, types)
    assert not errs, csw.format_errors(errs, after)


@pytest.mark.parametrize("rack", FAN_DOOR_RACKS)
def test_10_18_unbound_rotor_in_door_conditional_subparts_fails(package, types, rack):
    """The 2026-10-18 structure (DataCenter 028c1172 removed it): the unbound RackFan client prefab as a door-rack
    ConditionalSubParts entry. The server walk reaches its render composite -> "Client component ... should not be on
    server compositions"."""
    csp = res(package, own(package, rack, "Client_ConditionalSubPartsDefinition.def"))
    fan = own(package, rack, "RackFan.partialdef")
    csp["SubParts"][own(package, rack, "RackFan_DummyTypeDefinition.def")] = fan
    w, errs = run(package.derive(as_def(T_CSP, csp)), types)
    fan_comp = csw.composition_of(res(package, fan))
    bad = errors_of(errs, "client-type-on-server", fan_comp)
    assert bad, csw.format_errors(errs)
    assert any("ModelRenderComponent" in e[3][0] for e in bad), bad
    assert any(csp["Guid"] in step for e in bad for step in e[3]), bad      # reached through the ConditionalSubParts


@pytest.mark.path_a
@pytest.mark.parametrize("rack,server", [(r, f) for r in FAN_DOOR_RACKS for f in
                                          ("LeftDoor_Server.def", "RackFanTray_Server.def", "RackSide_Server.def")]
                         + [("DC_Rack42_Open", f) for f in ("RackFanTray_Server.def", "RackSide_Server.def")])
def test_bound_entry_whose_server_prefab_has_a_child_fails(package, types, rack, server):
    """A BOUND ConditionalSubParts entry is blocked on the server side only at its client prefab: its server prefab is
    walked as server through the binding, so a child there (the rotor) is a server composite. On the door leaves and
    on Task 12's real RackFanTray / RackSide server prefabs (door and open racks)."""
    sp = res(package, own(package, rack, server))
    fan = res(package, own(package, rack, "RackFan.partialdef"))
    for ob in sp["_entity"]["ObjectBuilders"]:
        if (ob.get("Value") or {}).get("$Type") == OB_HIERARCHY:
            ob["Value"]["Children"] = [dict(fan["_entity"], DebugName="Rotor")]
    w, errs = run(package.derive(as_def(T_PREFAB, sp)), types)
    assert errors_of(errs, "client-type-on-server", csw.composition_of(fan)), csw.format_errors(errs)


@pytest.mark.path_a
@pytest.mark.parametrize("rack,comp", [(r, f) for r in DOOR_RACKS for f in
                                        ("LeftDoor_ServerComposition.def", "RackSide_ServerComposition.def")]
                         + [(r, "RackFanTray_ServerComposition.def") for r in FAN_DOOR_RACKS + ("DC_Rack42_Open",)]
                         + [(r, "RackSide_ServerComposition.def") for r in OPEN_RACKS])
def test_server_composition_inheriting_a_client_type_fails(package, types, rack, comp):
    """A bound entry's server composition that INHERITS render components from its Copy base (the subpart template)
    instead of inserting them: the resolver applies the base chain, so the inherited client types are seen. On the
    door leaves and on Task 12's real RackSide / RackFanTray server compositions."""
    sc = own(package, rack, comp)
    delta = as_def(T_PARTIAL, {"BaseDefinition": SUBPART_COMPOSITE_TEMPLATE, "PartialDefinitionKind": "Copy",
                              "Manipulator": {"Guid": sc}, "DefinitionType": T_COMPOSITE, "PriorityOverride": False})
    w, errs = run(package.derive(delta), types)
    assert errors_of(errs, "client-type-on-server", sc), csw.format_errors(errs)


def test_binding_without_server_prefab_fails(package, types):
    """A binding whose ServerComposite no prefab instantiates: the game asserts "Definition that is linked from ... is
    not found" and dereferences null (BindingsBasedClientServerInfo.cs:68-71, :131-136)."""
    rack = "DC_Rack42_SplitFront"
    sc = guid(rack, "orphan", "sc")
    files = [as_def(T_COMPOSITE, {"Guid": sc, "TagSlots": [], "Components": [
                 {"Key": guid(rack, "orphan", "k"), "Value": {"Definition": None, "Type": C_HIERARCHY}}]}),
             as_def(T_BINDING, {"Guid": guid(rack, "orphan", "b"), "ServerComposite": sc,
                                "ClientPrefab": own(package, rack, "RackSide.partialdef")})]
    w, errs = run(package.derive(*files), types)
    assert [e for e in errs if e[0] == "binding" and e[2] == guid(rack, "orphan", "b")], csw.format_errors(errs)


# ------------------------------------------------------------------------------------------------------ (c) Path A
# Task 12 shipped the Path A structure (task-12-spike.md Q1 (a)-(d), Q3): RackSide (one entry, two dummies) and the
# full racks' RackFanTray are bound ConditionalSubParts entries with a server composition (Model + ChildTransform +
# Hierarchy) and a server prefab with Children []; the rotors are children of the tray's CLIENT prefab only; door
# racks list them in the door's ConditionalSubParts (walked by the server), open racks in a client-only
# ConditionalSubPartsComponent. test_datacenter_package_passes is the gate on it; these pin that the real structure
# is really walked on the intended sides, and that the gate would catch it losing the one rule it depends on.
def rack_parts(u, rack):
    """{part: (binding, server composite, client prefab, dummy type)} of the rack's staged bound subparts."""
    out = {}
    for part in ("RackSide", "RackFanTray"):
        if not has(u, rack, f"{part}_Binding.def"):
            continue
        b = own(u, rack, f"{part}_Binding.def")
        v = res(u, b)
        assert v["ClientPrefab"] == own(u, rack, f"{part}.partialdef")
        out[part] = (b, v["ServerComposite"], v["ClientPrefab"], own(u, rack, f"{part}_DummyTypeDefinition.def"))
    return out


def rack_csp(u, rack):
    return own(u, rack, "Client_ConditionalSubPartsDefinition.def" if rack in DOOR_RACKS
               else "ConditionalSubPartsDefinition.def")


@pytest.mark.path_a
@pytest.mark.parametrize("rack", DOOR_RACKS + OPEN_RACKS)
def test_path_a_rack_structure_is_walked(package, package_walk, rack):
    """Non-vacuity on the real package: each bound part's binding is walked, its server composite is on the server
    side, its client prefab's composite on the client side only; the ConditionalSubParts lists every part (door racks:
    reached by the server walk through the door chain; open racks: client only); the rotors are client only."""
    w, u = package_walk, package
    parts = rack_parts(u, rack)
    assert set(parts) == ({"RackSide", "RackFanTray"} if rack in FAN_DOOR_RACKS + ("DC_Rack42_Open",)
                          else {"RackSide"}), parts
    csp = rack_csp(u, rack)
    subparts = res(u, csp)["SubParts"]
    for part, (b, sc, cp, dt) in parts.items():
        assert w.bindings[b][0] == sc and sc in w.server.composites, part
        cc = csw.composition_of(res(u, cp))
        assert cc in w.client.composites and cc not in w.server.composites, part
        assert subparts[dt] == cp, part
        sp = w.bindings[b][1]
        assert not [ch for ob in csw.object_builders(res(u, sp)["_entity"]).values()
                    if isinstance(ob, dict) for ch in csw._children(ob)], part     # server prefab: Children []
    if rack in DOOR_RACKS:
        assert csp in w.server.definitions
    else:
        assert csp in w.client.definitions and csp not in w.server.definitions
    if "RackFanTray" in parts:
        rotor = csw.composition_of(res(u, own(u, rack, "RackFan.partialdef")))
        assert rotor in w.client.composites and rotor not in w.server.composites
        kids = [ch for ob in csw.object_builders(res(u, parts["RackFanTray"][2])["_entity"]).values()
                if isinstance(ob, dict) for ch in csw._children(ob)]
        assert [csw._g(k["Definition"]) for k in kids] == [rotor, rotor]


@pytest.mark.path_a
@pytest.mark.parametrize("rack", FAN_DOOR_RACKS)
def test_path_a_with_unbound_tray_fails(package, types, rack):
    """Control: re-point the tray's binding at another client prefab (the side's), so the tray is no longer bound: the
    server walk now reaches the tray (through the door chain) and, through its children, the rotors: the gate fails
    on exactly the rule Path A depends on."""
    parts = rack_parts(package, rack)
    b = res(package, parts["RackFanTray"][0])
    b["ClientPrefab"] = parts["RackSide"][2]
    w, errs = run(package.derive(as_def(T_BINDING, b)), types)
    rotor = csw.composition_of(res(package, own(package, rack, "RackFan.partialdef")))
    tray = csw.composition_of(res(package, parts["RackFanTray"][2]))
    assert errors_of(errs, "client-type-on-server", rotor), csw.format_errors(errs)
    assert errors_of(errs, "client-type-on-server", tray), csw.format_errors(errs)
