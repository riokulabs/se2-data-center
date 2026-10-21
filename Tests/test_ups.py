"""Task 7: the UPS (12U, two OPEN Power Cell bays) behaves as Battery50 with two cells.

Vanilla values are read with json from tools/vanilla-ref (read-only hard links) and the SDK, never copied.

Capacity semantics (Ruling 3, verified in the decompiled game, tools/decompiled/Game2.Simulation/
Keen.Game2.Simulation.WorldObjects.CubeBlocks.ResourceDistribution.Resources/ResourceContainerInventoryComponent.cs):
the definition's MaxCapacity only seeds the resource entity (ResourceContainerComponent: MaxCapacity =
_definition.MaxCapacity); on add-to-scene and on every inventory change RecalculateCapacity overwrites it with
sum(cell MaxStored x Amount) over the slot inventories (ResourceContainerItemsConfiguration: Power Cell -> MaxStored
180000). So the capacity lives on the CELLS; the charge / discharge rates (MaxChargingRate / MaxDischargeRate) are
read from the block definition and cap the flow. Battery50's block value (180000) equals one cell's MaxStored, so the
consistent block value for two slots is 2 x 180000 = 360000, and the rates double so two cells charge and discharge as
fast as two Battery50s.

Slot mass (deviation from the brief's "MaxMass == 50", see the report): a slot is one InventoryComponent and every
slot uses the SAME InventoryDefinition (InventorySlotsServerDefinition.SlotDefinition; vanilla Battery250: four
InventoryComponents of one definition). MaxMass is per InventoryComponent and MaxStacks = 1, so MaxMass 50 would let
each slot take a stack of 2 cells (4 cells, 4 x capacity). One cell per slot = 25 kg per slot; 2 slots = 50 kg total.
"""
import json
import os

import pytest

from dc import catalog, clone, config, functional, integration
from dc.assetio import own_guid, read_json

UPS = "DC_Srv_UPS"
B50 = os.path.join(config.VANILLA_REF, "Blocks", "Batteries", "Battery", "50")
SDK_CONTENT = os.path.expanduser("~/.steam/debian-installation/steamapps/common/SpaceEngineers2/GameData/Vanilla/"
                                 "Content")


def _v(rel):
    p = os.path.join(B50, rel)
    if not os.path.exists(p):
        pytest.skip(f"tools/vanilla-ref missing {rel}")
    return read_json(p)["$Value"]["Manipulator"]


def _sdk(rel):
    p = os.path.join(SDK_CONTENT, rel)
    if not os.path.exists(p):
        pytest.skip(f"SDK content missing {rel}")
    return read_json(p)["$Value"]


@pytest.fixture(scope="module")
def staged(stage_package):
    rep = read_json(config.REPORT_PATH)["blocks"]
    if not rep.get(UPS, {}).get("placement", {}).get("total"):
        pytest.fail("DC_Srv_UPS not built (build_dc.py)")
    return stage_package()


def _staged(pattern):
    files = integration._block_files(catalog.BY_NAME[UPS], pattern)
    assert len(files) == 1, files
    return read_json(os.path.join(config.STAGE_ASSETS, files[0]))


def _dummies():
    bmd = read_json(os.path.join(config.STAGE_ASSETS, clone.entry(catalog.BY_NAME[UPS])["info"]["model_def_file"]))
    return [c["Value"] for c in bmd["$Value"]["Manipulator"]["Dummies"]["Changed"]]


# ---------------------------------------------------------------------------------------------- slots
def test_ups_two_cell_slots(staged):
    dums = _dummies()
    slots = sorted(d["Name"] for d in dums if d["Type"] == functional.CELL_SLOT_TYPE)
    acts = sorted(d["Name"] for d in dums if d["Type"] == functional.CELL_ACTION_TYPE)
    assert slots == ["CellSlot 0", "CellSlot 1"] and acts == ["CellAction 0", "CellAction 1"], (slots, acts)
    # the dummy types are vanilla Battery50's
    van = {d["Value"]["Name"]: d["Value"]["Type"] for d in _v("Battery50_BlockModelDefinition.partialdef")["Dummies"]
           ["Changed"]}
    assert van["CellSlot 0"] == functional.CELL_SLOT_TYPE and van["CellAction 0"] == functional.CELL_ACTION_TYPE
    # the slot inventory: Power Cell only, one cell (25 kg) per slot
    inv = _staged("_InventoryDefinition")
    m = inv["$Value"]["Manipulator"]
    base = _sdk("Templates/Blocks/BaseDefinitions/Battery_InventoryDefinition.def")
    assert inv["$Value"]["BaseDefinition"] == base["Guid"]
    items = (set(base["WhitelistedItems"]["Added"]) - set(m["WhitelistedItems"]["Removed"])) | set(
        m["WhitelistedItems"]["Added"])
    assert items == {functional.POWER_CELL}, items
    cell = _sdk("Components/Simple/PowerCell/ItemPowerCell.def")
    assert cell["Guid"] == functional.POWER_CELL and cell["MassPerUnit"] == functional.POWER_CELL_MASS
    assert base["MaxStacks"] == 1 and m["MaxMass"] == functional.POWER_CELL_MASS     # one cell per slot
    # two slot inventories of that definition, tagged CellSlot 0 / 1 -> 50 kg of cells in all
    comp = _staged("_ServerComposition")["$Value"]["Manipulator"]
    tags = {t["$Key"]: t["$Value"] for t in comp["TagSlots"]["ModifiedKeys"]}
    assert sorted(t for t in tags if t.startswith("CellSlot")) == ["CellSlot 0", "CellSlot 1"]
    keys = comp["Components"]["Keys"]
    defs = {keys[c["Index"]]: c["Value"].get("Definition") for c in comp["Components"]["Changed"]}
    own = own_guid(inv)
    assert [defs[tags[f"CellSlot {i}"]] for i in (0, 1)] == [own, own]
    assert sum(m["MaxMass"] for _ in (0, 1)) == 50
    # InventorySlotsServer / InventorySlotSync both use that definition
    assert _staged("InventorySlotsServerDefinition")["$Value"]["Manipulator"]["SlotDefinition"] == own
    assert _staged("InventorySlotSyncDefinition")["$Value"]["Manipulator"]["SlotDefinition"] == own
    # the prefab starts both slots like vanilla slot 0 (one cell at FillRatio 0.3)
    ob = _staged("_Server.partialdef")["$Value"]["Manipulator"]["_entity"]["ObjectBuilders"]
    val = {ob["Keys"][c["Index"]]: c["Value"] for c in ob["Changed"]}
    for i in (0, 1):
        it = val[tags[f"CellSlot {i}"]]["Items"]
        assert len(it) == 1 and it[0]["Definition"] == functional.POWER_CELL and it[0]["Amount"] == 1


def test_ups_capacity_doubled(staged):
    """Capacity lives on the cells (module docstring); the block is kept consistent: 2 slots x MaxStored, rates x2."""
    cell = _sdk("Components/Simple/PowerCell/PowerCellResourceContainerItemDefinition.def")
    cfg = _sdk("System/Configurations/ResourceContainerItemsConfiguration.def")
    assert cfg["Containers"][functional.POWER_CELL] == cell["Guid"]
    assert cell["MaxStored"] == functional.POWER_CELL_MAX_STORED
    van = _v("Battery50_Battery_ResourceContainerInventoryDefinition.partialdef")
    assert van["MaxCapacity"] == cell["MaxStored"]            # vanilla: block value = its one cell
    ours = _staged("ResourceContainerInventoryDefinition")["$Value"]["Manipulator"]
    assert ours["MaxCapacity"] == 360000 == 2 * van["MaxCapacity"] == 2 * cell["MaxStored"]
    assert ours["MaxChargingRate"] == pytest.approx(2 * van["MaxChargingRate"])
    assert ours["MaxDischargeRate"] == pytest.approx(2 * van["MaxDischargeRate"])
    assert ours["MaxChargingRate"] < ours["MaxDischargeRate"]  # the definition's range rule (charge < discharge)


# ---------------------------------------------------------------------------------------------- the bays
@pytest.mark.build
def test_ups_open_slots():
    """The bays are OPEN like Battery50's: no grate, cage, window or door anywhere in the model; the vanilla slot
    frame is there (kit provenance), with no material slot that would read as glass."""
    e = read_json(config.REPORT_PATH)["blocks"][UPS]
    names = [n.lower() for n in e["lod0_objects"]] + [m.lower() for m in e["mesh_parts"]]
    for bad in ("grate", "grille_door", "cage", "window", "door", "glass"):
        assert not [n for n in names if bad in n], (bad, names)
    assert any("cellbay_front" in n for n in names) and any("cellbay_rear" in n for n in names), names
    assert any("Battery50.fbx:UpgradePort_SpeedModule" in p for p in e["provenance"]), e["provenance"]


def test_ups_dummies_on_bays(staged):
    """Each bay's CellSlot / CellAction sit on that bay's axis, offset from its frame mouth exactly as Battery50's
    sit from its frame (the cell's face 22.6 mm out, the use box 4.6 mm in); the rear pair is turned 180 deg about
    the up axis so the cell faces out of the back; each pair is supported by its bay's fracture (vanilla Battery50:
    CellSlot 0 / CellAction 0 on Fracture_01): the front bay by Fracture_01, the rear one by Fracture_02."""
    v = {d["Value"]["Name"]: d["Value"] for d in _v("Battery50_BlockModelDefinition.partialdef")["Dummies"]["Changed"]}
    assert v["CellSlot 0"]["SupportingFracture"] == v["CellAction 0"]["SupportingFracture"] == {"Id": "Fracture_01"}
    # Battery50 (2x2x2, shift 0.125): Blender y of a dummy = -(game z - 0.125); its frame mouth is CELL_KIT_MOUTH
    for name, off in (("CellSlot 0", functional.CELL_SLOT_AHEAD), ("CellAction 0", -functional.CELL_ACTION_BEHIND)):
        yb = -(v[name]["Transform"]["Transform"]["Position"]["Z"] - 0.125)
        assert yb - functional.CELL_KIT_MOUTH == pytest.approx(off, abs=2e-4), name
    assert tuple(v["CellSlot 0"]["Scale"].values()) == functional.CELL_SLOT_SCALE
    assert tuple(v["CellAction 0"]["Scale"].values()) == functional.CELL_ACTION_SCALE
    ours = {d["Name"]: d for d in _dummies() if d["Name"]}
    sx, sy, sz = functional.UPS_SHIFT
    for i, x, z, ym, f in functional.UPS_BAYS:
        for name, off in ((f"CellSlot {i}", functional.CELL_SLOT_AHEAD),
                          (f"CellAction {i}", -functional.CELL_ACTION_BEHIND)):
            d = ours[name]
            p = d["Transform"]["Transform"]["Position"]
            assert (p["X"], p["Y"]) == pytest.approx((x + sx, z + sy)), name
            assert -(p["Z"] - sz) == pytest.approx(ym + f * off), name
            q = d["Transform"]["Transform"]["Orientation"]
            assert (q["X"], q["Y"], q["Z"], q["W"]) == ((0, 0, 0, 1) if f > 0 else (0, 1, 0, 0)), name
            assert d["SupportingFracture"] == {"Id": "Fracture_01" if f > 0 else "Fracture_02"}, name
        # inside the block's x / up extent (the bay sits inside the face)
        assert 0.125 - 0.25 <= x + sx - 0.15 and x + sx + 0.15 <= 0.125 + 0.25
        assert -0.125 <= z + sy - 0.15 and z + sy + 0.15 <= 0.375
    # the front pair is on the front face, the rear pair on the back face (game z: front = -0.375)
    assert -0.42 <= ours["CellSlot 0"]["Transform"]["Transform"]["Position"]["Z"] <= -0.375
    assert 0.35 <= ours["CellSlot 1"]["Transform"]["Transform"]["Position"]["Z"] <= 0.375


@pytest.mark.build
def test_ups_bays_match_model():
    """The model's bays (build_report "bays", measured on the built kit meshes) are where functional.UPS_BAYS says:
    the kit frame's mouth and centre per bay."""
    bays = read_json(config.REPORT_PATH)["blocks"][UPS]["bays"]
    for (i, x, z, ym, f), b in zip(functional.UPS_BAYS, bays):
        assert b["mouth_y"] == pytest.approx(ym, abs=1e-3), b
        assert b["centre"] == pytest.approx([x, z], abs=1e-3), b
        assert b["half"] == pytest.approx(functional.CELL_KIT_HALF, abs=2e-3), b


def test_ups_mounts(staged):
    info = clone.entry(catalog.BY_NAME[UPS])["info"]
    bd = read_json(os.path.join(config.STAGE_ASSETS, info["block_def_file"]))["$Value"]["Manipulator"]
    assert bd["MountPointGeneratorSettings"]["Directions"] == integration.UPS_MOUNTS
    assert "Backward" not in integration.UPS_MOUNTS and "Forward" not in integration.UPS_MOUNTS


def test_ups_size():
    spec = catalog.BY_NAME[UPS]
    assert spec.cells == (2, 2, 3) and spec.copy_from == "Battery50"
    assert json.dumps(catalog.bounds(spec)) == json.dumps(((0, 0, -1), (1, 1, 1)))


# ------------------------------------------------------------------ SE2 4.0.0.3151: damage effects on particle sets
SETS = {"SmokeSmall": ("d8cb4c53-5d1b-4aaa-9b56-71bb67ad1dd7", "Smoke/SmokeSmall_ParticleSet.def"),
        "FireSmall": ("9056509a-00d5-4abd-a2ea-3a9707e2ef45", "Fire/FireSmall_ParticleSet.def"),
        "GridExplosions": ("b41e3b65-0919-4ff9-95b0-72c0ddad7409", "Explosion/Regular/GridExplosions_ParticleSet.def")}
# Plan 5 Task 4: the KVM's band is now 4.0 ControlPanel25's own update (ElectricalDamageSmall sparks, no SmokeSmall;
# Tests/test_effects.py::test_kvm_sparks_like_cp25), so it names no set and pins CP25's threshold
EFFECT_SETS = {UPS: ("SmokeSmall", "FireSmall", "GridExplosions"), "DC_Srv_KVM": ()}


def _effects_files(name):
    """The block's BlockEffects definitions as they will be installed (staged copy over the mod's)."""
    out = {}
    for f in integration._block_files(catalog.BY_NAME[name], "BlockEffectsComponentDefinition"):
        out[f] = json.dumps(integration.read_current(f))
    return out


def test_damage_effects_use_vanilla_particle_sets(staged):
    """4.0.0.3151 moved SmokeSmall / FireSmall / ExplosionGrid to V1 variants of new particle SETS and vanilla
    BlockEffects point at the sets; our UPS and KVM overrides do too (user decision 2026-10-19: accept the new
    vanilla damage bands, so our deltas set no HealthIntegrity thresholds)."""
    for name, want in EFFECT_SETS.items():
        files = _effects_files(name)
        assert files, name
        text = "".join(files.values())
        for v1 in integration.PARTICLE_SETS:
            assert v1 not in text, (name, "still names V1 effect", v1)
        for s in want:
            assert SETS[s][0] in text, (name, s)
        if want:   # (the KVM carries ControlPanel25's 4.0 band update verbatim, threshold included)
            assert "HealthIntegrity" not in text, (name, "the 4.0 vanilla damage bands are inherited, not pinned")
    ups = json.loads(_effects_files(UPS)[next(iter(_effects_files(UPS)))])
    assert ups["$Value"]["Manipulator"]["OnBlockDeathParticleEffect"] == {"ParticleEffect": SETS["GridExplosions"][0],
                                                                          "Scale": 0.15}


def test_particle_sets_exist_in_vanilla():
    """Each set we point at is a ParticleEffectSetDefinition in 4.0 vanilla whose variants include the V1 effect
    we used before (so the look is the same family, with V2/V3 variety)."""
    v1_of = {s: v1 for v1, s in integration.PARTICLE_SETS.items()}
    for name, (guid, rel) in SETS.items():
        d = _sdk(os.path.join("System", "Particles", "Generic", rel))
        assert d["Guid"] == guid, name
        assert v1_of[guid] in [e["Value"]["Effect"] for e in d["Effects"]], name
