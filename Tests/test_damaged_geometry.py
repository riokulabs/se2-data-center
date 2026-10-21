"""The Damaged ("Deformed") model geometry.

Tris a Damaged LOD holds at most fracture.damaged_tris_x(family) x its Fractured LOD's triangles without the
     construction scaffold (vanilla Deformed / Fractured: median 1.0; ours x 1.2, the floor decks and roof tops x 1.5),
     densified to at least MIN_RATIO except the named light-tray LODs; the dents still read (mean
     displacement >= MIN_DENT_MM);
New  the 4 unfractured, non-breakable blocks (fracture.UNFRACTURED: the 3 rod hangers and the Chute) gain a dented
     Damaged model too (vanilla's non-breakable ControlPanel25 / Sensor25 have their Deformed model), with the
     Fractured model's mesh parts, and their BlockModelDefinition's DamagedModel points at it.
Also the <Block>_LastLOD slot keeps its Fractured material in the Damaged .model, as 194 of
the 196 vanilla Deformed models with a LastLOD slot do.
"""
import os

import pytest

from dc import catalog, clone, config
from dc import fracture as FR
from dc.assetio import read_json

NAMES = [b.name for b in catalog.BLOCKS]
UNFRACTURED = ("DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200", "DC_Tray_Chute")


def _man(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


CUT = [n for n in NAMES if _man(n)["fractured"].get("kind") == "cut"]


# ---------------------------------------------------------------------------------------------------- pure
def test_damaged_tris_x_table():
    """x 1.2 by default, x 1.5 for the floor decks and the roof tops (big flat panels need vertices a
    dent can move), never above vanilla's flat-panel range used here (1.5)."""
    assert FR.DAMAGED_TRIS_X == {"default": 1.2, "floor": 1.5, "contain_roof": 1.5}
    assert FR.damaged_tris_x("floor") == FR.damaged_tris_x("contain_roof") == 1.5
    for fam in ("rack", "server", "tray", "trayrods", "pdu_cabinet", "pdu_strip", "crac", "sign", "contain_door"):
        assert FR.damaged_tris_x(fam) == 1.2, fam
    assert FR.MIN_DENT_MM == 1.5


# ---------------------------------------------------------------------------------------------------- build
# the least Damaged / (Fractured - scaffold) ratio densify must reach (a silent densify regression fails here)
MIN_RATIO = 1.15
# (block, LOD) that cannot reach MIN_RATIO: light trays whose LOD has no edge left longer than DENT max_edge (the
# densify step stops there). Exactly these, measured: ratios 1.005-1.147.
LIGHT_LODS = {("DC_Tray_TurnH_Empty", 0), ("DC_Tray_TurnUp_Empty", 0), ("DC_Tray_TurnUp_Empty", 1),
              ("DC_Tray_StraightL_Empty", 0), ("DC_Tray_StraightL_Empty", 1), ("DC_Tray_StraightL_Low", 2),
              ("DC_Tray_StraightS_Empty", 1), ("DC_Tray_TurnDown_Empty", 2)}


@pytest.mark.build
@pytest.mark.parametrize("name", CUT)
def test_dm_ratio(name):
    """Every cut block, every LOD but the LastLOD box: DM <= damaged_tris_x x (FR - scaffold) (+2: the densify step's
    last n-gon triangulation) and within the fractured budget of that LOD; and densified to at least MIN_RATIO x base
    (or to within 4 triangles of the LOD's budget: the PDU cabinet's LOD1, the 42U racks' LOD3), except LIGHT_LODS."""
    m = _man(name)
    fam = catalog.BY_NAME[name].family
    sc = (m["fractured"].get("scaffold") or {}).get("tris") or {}
    fr, dm, budget = m["fractured"]["lods"], m["damaged"]["lods"], m["fractured"]["budget"]
    assert len(fr) == len(dm) == len(budget), name
    for i in range(len(fr) - 1):
        base = fr[i]["tris"] - sc.get(str(i), 0)
        t = dm[i]["tris"]
        assert t <= FR.damaged_tris_x(fam) * base + 2, (name, i, base, t)
        assert t <= budget[i], (name, i, t, budget[i])
        if (name, i) not in LIGHT_LODS:
            assert t >= min(MIN_RATIO * base, budget[i] - 4), (name, i, base, t, budget[i])


def test_light_lods_exist():
    """The LIGHT_LODS exemption names real blocks (no stale entry)."""
    assert {n for n, _ in LIGHT_LODS} <= set(CUT)


@pytest.mark.build
def test_two_trays_back_under_ratio():
    """The two light trays the old x 2.0 ratio densified most (DM LOD0 3 574 / 5 174): their LOD0 is now at the x 1.2
    cap derived from their own manifest (FR LOD0 - scaffold). (There were never over-limit tray warnings:
    Keen's fractured limit, ~15.4k / ~22.5k here, was never exceeded.)"""
    for name in ("DC_Tray_Reducer_Low", "DC_Tray_Tee_Empty"):
        m = _man(name)
        sc0 = ((m["fractured"].get("scaffold") or {}).get("tris") or {}).get("0", 0)
        cap = int(FR.damaged_tris_x(catalog.BY_NAME[name].family) * (m["fractured"]["lods"][0]["tris"] - sc0))
        t0 = m["damaged"]["lods"][0]["tris"]
        assert t0 <= cap, (name, t0, cap)


@pytest.mark.build
@pytest.mark.parametrize("name", [n for n in NAMES if n not in UNFRACTURED])
def test_dents_still_read(name):
    """With fewer densify vertices the dent must still read: mean vertex displacement >= MIN_DENT_MM on every block
    with zones (the unfractured blocks' gentler rods: test_unfractured_have_dented_debris)."""
    m = _man(name)
    assert "damaged" in m, name
    assert m["damaged"]["dent"]["mean_mm"] >= FR.MIN_DENT_MM, (name, m["damaged"]["dent"])


@pytest.mark.build
@pytest.mark.parametrize("name", UNFRACTURED)
def test_unfractured_have_dented_debris(name, stage_package):
    """The rod hangers and the Chute (non-breakable, no zones) leave dented debris: a Damaged model with the
    Fractured model's mesh parts and LOD count, dented >= 1 mm mean, its colliders the Fractured's plain boxes, and
    the staged DamagedModel points at it."""
    from dc import fracture_rules as FRR
    from dc import integration
    spec = catalog.BY_NAME[name]
    assert FR.unfractured_reason(spec), name
    m = _man(name)
    dm = m.get("damaged")
    assert dm, name
    assert dm["dent"]["mean_mm"] >= 1.0, (name, dm["dent"])
    assert len(dm["lods"]) == len(m["fractured"]["lods"]), name
    d = os.path.join(config.MODELS_DIR, name)
    fr_fbx = os.path.join(d, "Fractured", m["fractured"]["lods"][0]["file"])
    dm_fbx = os.path.join(d, "Damaged", dm["lods"][0]["file"])
    assert FRR.mesh_parts(FRR.fbx_meshes(dm_fbx)) == FRR.mesh_parts(FRR.fbx_meshes(fr_fbx)), name
    fr_col = FRR.gltf_hulls(os.path.join(d, "Fractured", m["fractured"]["collision"]["file"]))
    dm_col = FRR.gltf_hulls(os.path.join(d, "Damaged", dm["collision"]["file"]))
    assert sorted(map(sorted, dm_col.values())) == sorted(map(sorted, fr_col.values())), name
    for a, b in zip(m["fractured"]["lods"][:-1], dm["lods"][:-1]):
        assert b["tris"] <= FR.damaged_tris_x(spec.family) * a["tris"] + 2, (name, a["tris"], b["tris"])
    stage_package()
    rel = clone.entry(spec)["info"]["model_def_file"]
    bmd = read_json(os.path.join(config.STAGE_ASSETS, rel))["$Value"]["Manipulator"]
    want = "{G}" + integration.asset_id(f"{config.NAME}/{name}/Models/Damaged/{name}_Damaged.model")
    assert bmd["DamagedModel"] == want, name


@pytest.mark.build
def test_lastlod_slot_keeps_its_material(stage_package):
    """The LastLOD box's <Block>_LastLOD slot is NOT Deformed-remapped: vanilla's Deformed models
    keep the Fractured / NonFractured LastLOD material (194 of 196 measured), and so do ours."""
    from dc import integration
    stage_package()
    n = 0
    for spec in catalog.STAGED:
        p = os.path.join(config.STAGE_ASSETS, config.NAME, spec.name, "Models", "Damaged", f"{spec.name}_Damaged.model")
        if not os.path.exists(p):
            continue
        dm = {a["MaterialName"]: a["MaterialReference"] for a in read_json(p)["$Value"]["MaterialAssignments"]}
        fr = {a["MaterialName"]: a["MaterialReference"]
              for a in read_json(p.replace("Damaged", "Fractured"))["$Value"]["MaterialAssignments"]}
        for slot in (s for s in dm if s.endswith("_LastLOD")):
            assert dm[slot] == fr[slot], (spec.name, slot)
            n += 1
    assert n >= 60, n
