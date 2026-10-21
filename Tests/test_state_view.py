"""dc.state_view: the build-stage / damage-state evaluation behind the states preview harness, the vanilla analogues it
renders beside our blocks, and the pre-4.0-damage baseline (Tests/golden/states_baseline.json) later tasks test
against (zone ids, criticals, NF mesh parts, stage hash, definition GUIDs)."""
import copy
import json
import os
import re

import pytest

from dc import catalog, config, state_view as SV
from dc.assetio import meta_id, read_json

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden", "states_baseline.json")
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
M = "2a8225c1-df6c-41a7-ad6f-b58a77bdd88d"   # ConstructionMetal01


def _chg(part, show=None, mat=None, reset=False, damaged=False):
    return {"Key": f"k-{part}-{show}-{mat}", "Value": {"MeshPart": part, "ShowPart": show, "SetMaterial": mat,
                                                     "ResetToSkinMaterial": reset, "ApplyOnlyWhenDamaged": damaged}}


def _stages(last=()):
    return [{"Key": "s0", "Value": {"BuildRatioLowerBound": 0, "Model": "{G}fr", "PartChanges": {"_data": [
                _chg("A", show=False), _chg("B", mat=M)]}}},
            {"Key": "s1", "Value": {"BuildRatioLowerBound": 0.3, "Model": None, "PartChanges": {"_data": [
                _chg("A", show=True, mat=M), _chg("B", reset=True)]}}},
            {"Key": "s2", "Value": {"BuildRatioLowerBound": 1, "Model": "{G}nf", "PartChanges": {"_data": list(last)}}}]


def manifest(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


# ---------------------------------------------------------------------------------------------------- pure
def test_part_state_cumulative():
    s = _stages()
    assert SV.part_state(s, 0.0) == {"A": (False, None), "B": (True, M)}
    assert SV.part_state(s, 0.1)["A"] == (False, None)
    assert SV.part_state(s, 0.3)["A"] == (True, M)
    assert SV.part_state(s, 0.3)["B"] == (True, None)          # ResetToSkinMaterial
    assert SV.part_state(s, 1.0) == {}
    s = _stages([_chg("BrushedMetal", show=False, damaged=True)])
    assert SV.part_state(s, 1.0) == {}                          # ApplyOnlyWhenDamaged: not on a sound block
    assert SV.part_state(s, 1.0, damaged=True) == {"BrushedMetal": (False, None)}


def test_shots():
    assert list(SV.SHOTS) == ["c00", "c10", "c20", "c30", "c53", "c77", "done"]
    assert list(SV.SHOTS.values()) == [0.0, 0.1, 0.2, 0.3, 0.5333, 0.7667, 1.0]
    assert SV.DAMAGE_SHOTS == ("done_damaged", "one_hit", "battered", "broken")
    assert SV.ALL_SHOTS == tuple(SV.SHOTS) + SV.DAMAGE_SHOTS


def test_stages_sha1_ignores_only_the_last_stage_changes():
    """R3: the baseline hash survives Task 2 replacing the stage-1.0 damaged-only hide, and nothing else."""
    a = _stages([_chg("Chrome", show=False, damaged=True)])
    assert SV.stages_sha1(a) == SV.stages_sha1(_stages()) == SV.stages_sha1(_stages([_chg("BrushedMetal", False)]))
    b = copy.deepcopy(a)
    b[1]["Value"]["PartChanges"]["_data"][0]["Value"]["SetMaterial"] = "other"
    assert SV.stages_sha1(b) != SV.stages_sha1(a)
    c = copy.deepcopy(a)
    c[-1]["Value"]["Model"] = "{G}other"
    assert SV.stages_sha1(c) != SV.stages_sha1(a)
    assert SV.last_stage_changes(a) == [a[-1]["Value"]["PartChanges"]["_data"][0]["Value"]]


def test_zone_of():
    assert SV.zone_of("Fracture_01") == "Fracture_01"
    assert SV.zone_of("Fracture_03_Hide") == "Fracture_03"
    assert SV.zone_of("Fracture_12_Support") == "Fracture_12"
    assert SV.zone_of("Fracture14_Support") == "Fracture14"      # vanilla Reactor250 spelling
    assert SV.zone_of(None) is None and SV.zone_of("") is None and SV.zone_of("Scaffold") is None


def test_damage_scenario_edges():
    z = lambda i, v, c: {"id": i, "volume": v, "critical": c}  # noqa: E731
    allcrit = {"zones": [z("Fracture_01", 2, True), z("Fracture_02", 1, True)],
               "critical": ["Fracture_01", "Fracture_02"]}
    assert SV.damage_scenario(allcrit, "battered") == {"Fracture_01": "damaged", "Fracture_02": "damaged"}
    assert SV.damage_scenario(allcrit, "broken") == {"Fracture_01": "dead", "Fracture_02": "intact"}
    nocrit = {"zones": [z("Fracture_01", 1, False), z("Fracture_02", 3, False)], "critical": []}
    assert SV.damage_scenario(nocrit, "one_hit") == {"Fracture_01": "intact", "Fracture_02": "damaged"}
    assert SV.damage_scenario(nocrit, "battered") == {"Fracture_01": "dead", "Fracture_02": "damaged"}
    assert SV.damage_scenario(nocrit, "broken") == {}
    assert SV.damage_scenario(nocrit, "done_damaged") == {"Fracture_01": "intact", "Fracture_02": "intact"}
    assert SV.damage_scenario({"zones": [], "critical": []}, "one_hit") == {}
    with pytest.raises(ValueError):
        SV.damage_scenario(nocrit, "c30")


# ---------------------------------------------------------------------------------------------------- built data
@pytest.mark.build
@pytest.mark.parametrize("name", ["DC_Srv_UPS", "DC_Contain_Door_100"])
def test_damage_scenarios(name):
    fr = manifest(name)["fractured"]
    crit = set(fr["critical"])
    ids = {z["id"] for z in fr["zones"]}
    one = SV.damage_scenario(fr, "one_hit")
    assert set(one) == ids
    hit = [k for k, v in one.items() if v == "damaged"]
    assert len(hit) == 1 and hit[0] not in crit and set(one.values()) <= {"intact", "damaged"}
    bat = SV.damage_scenario(fr, "battered")
    dead = [k for k, v in bat.items() if v == "dead"]
    assert len(dead) == 1 and dead[0] not in crit
    assert all(v == "damaged" for k, v in bat.items() if k != dead[0])
    brk = SV.damage_scenario(fr, "broken")
    dead = [k for k, v in brk.items() if v == "dead"]
    assert len(dead) == 1 and dead[0] in crit
    if name == "DC_Srv_UPS":
        assert dead[0] in {"Fracture_01", "Fracture_02"} & crit


@pytest.mark.build
def test_installed_stages_every_block():
    names = [b.name for b in catalog.BLOCKS]
    assert len(names) == 73
    for n in names:
        s = SV.installed_stages(n)
        assert len(s) == 7, n
        fr_model = os.path.join(config.MOD_ASSETS, config.NAME, n, "Models", "Fractured", f"{n}_Fractured.model")
        assert s[0]["Value"]["Model"] == "{G}" + meta_id(fr_model) == SV.installed_bmd(n)["FractureModel"], n


@pytest.mark.build
def test_installed_dummies_resolve():
    """The marker source: the UPS has its centre ParticleEffects dummy, then one per bay (Plan 5 Task 4, audit G3); a
    tray has its centre one first, then one per other zone (ParticleEffects_<zone>)."""
    ups = SV.installed_dummies("DC_Srv_UPS")
    assert {d.get("Name") for d in ups} >= {"CellSlot 0", "CellSlot 1"}
    assert [d["Name"] for d in SV.effect_dummies(ups)] == ["ParticleEffects", "ParticleEffects 0",
                                                       "ParticleEffects 1"]
    tray = SV.effect_dummies(SV.installed_dummies("DC_Tray_StraightL_Full"))
    assert [d["Name"] for d in tray] == ["ParticleEffects", "ParticleEffects_Fracture_02", "ParticleEffects_Fracture_03"]


def test_analogues_exist():
    """R14: ANALOGUE holds vanilla block names; analogue_dir resolves each to its nested vanilla-ref folder (the one
    holding <name>_BlockModelDefinition.partialdef) with the NF / FR / DM LOD0 FBX the BMD references beside it."""
    fams = {b.family for b in catalog.BLOCKS}
    assert set(SV.ANALOGUE) == fams
    blocks = os.path.join(config.VANILLA_REF, "Blocks")
    for fam, names in SV.ANALOGUE.items():
        assert names, fam
        for a in names:
            d = SV.analogue_dir(a)
            assert os.path.isdir(d) and os.path.commonpath([d, blocks]) == blocks, a
            assert os.path.exists(os.path.join(d, f"{a}_BlockModelDefinition.partialdef")), a
            fbx = SV.analogue_models(a)
            assert fbx["nf"] and os.path.exists(fbx["nf"][0]), a
            for k in ("fr", "dm"):
                assert fbx[k] is None or os.path.exists(fbx[k][0]), (a, k)
            assert len(SV.analogue_stages(a)) >= 3, a


def test_analogue_fractured_timer50():
    fr = SV.analogue_fractured("Timer50")
    assert sorted(z["id"] for z in fr["zones"]) == ["Fracture_01", "Fracture_02"]
    assert sorted(fr["critical"]) == ["Fracture_01", "Fracture_02"]
    assert all(z["volume"] > 0 for z in fr["zones"])


def test_baseline_golden_complete():
    """The committed baseline holds every block with the six keys (plus the last stage, R3) and real values: the
    zone list matches the critical list's ids, every definition GUID is a GUID (R16), every block has NF parts."""
    g = json.load(open(GOLDEN))
    shared = g.pop(SV.SHARED_KEY)
    assert sorted(g) == sorted(b.name for b in catalog.BLOCKS) and len(g) == 73
    assert shared and all(GUID.match(x) for x in shared) and shared == sorted(set(shared))
    for n, r in g.items():
        assert set(r) == set(SV.BASELINE_KEYS) | {"last_stage"}, n
        assert set(r["critical"]) <= set(r["zones"]), n
        assert r["nf_parts"] and r["fr_parts"], n
        assert re.fullmatch(r"[0-9a-f]{40}", r["stages_sha1"]), n
        assert r["def_guids"] and all(GUID.match(x) for x in r["def_guids"]), n
        assert r["def_guids"] == sorted(set(r["def_guids"])), n
        assert r["last_stage"]["BuildRatioLowerBound"] == 1 and isinstance(r["last_stage"]["PartChanges"], list), n


def test_baseline_holds_every_definition_guid():
    """R16 groundwork: the baseline's GUIDs (every block's def_guids plus the shared ones: InitialUnlock, the UI block
    groups, the texts) are exactly the GUIDs every .def / .partialdef under Assets/DataCenter defines at this commit,
    counted from the files directly (no state_view walker)."""
    from dc.assetio import own_guid
    root = os.path.join(config.MOD_ASSETS, config.NAME)
    live, files, origin = set(), 0, {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                files += 1
                g = own_guid(read_json(os.path.join(dp, f)))
                if g:
                    live.add(g)
                    origin[g] = os.path.relpath(os.path.join(dp, f), root)
    gold = json.load(open(GOLDEN))
    base = set(gold.pop(SV.SHARED_KEY)) | {x for r in gold.values() for x in r["def_guids"]}
    assert files >= 1253
    assert base <= live, sorted(base - live)[:5]          # no definition GUID removed since the baseline
    # Added since the baseline, and only these, each pinned by GUID (the stable asset_guids.json key) AND file: Plan 5
    # Task 12's rack subpart bindings (binding, server composition, server prefab per bound subpart) and the open
    # racks' own ConditionalSubParts definition
    from dc.guids import Guids
    reg = Guids().d                                             # (read, never allocate)
    want = {}
    for b in catalog.BLOCKS:
        if b.family != "rack":
            continue
        subs = ("RackSide", "RackFanTray") if b.name.startswith("DC_Rack42") else ("RackSide",)
        for sub in subs:
            for key, f in (("Binding", "Binding"), ("ServerComposite", "ServerComposition"), ("ServerPrefab", "Server")):
                want[reg[f"def/{b.name}/{sub}/{key}"]] = f"{b.name}/Subparts/{b.name}_{sub}_{f}.def"
        if b.name.endswith("_Open"):
            want[reg[f"def/{b.name}/ConditionalSubParts"]] = f"{b.name}/Subparts/{b.name}_ConditionalSubPartsDefinition.def"
    assert len(want) == 29
    assert {g: origin[g].replace(os.sep, "/") for g in live - base} == want
