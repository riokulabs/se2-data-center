"""Construction roles per face (dc/fracture.py ROLE_IDS / role_of, written by fracture_mesh.cut_object,
split per zone by export_models.keep_zone / _group). The mechanism came first with empty role tables (the one change
then: the containment roof's glass builds as glass: its own object in the zone's group with the WindowGlass
preset 83c075f5); each block family then filled its entry in fracture.ROLES.

Save compatibility is checked against Tests/golden/states_baseline.json."""
import json
import os

import pytest

from dc import catalog, config, construction as C, state_view as SV
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import read_json

WINDOWGLASS = "83c075f5-f177-460d-94a7-8aca19fd4d6f"
ROOFS = ("DC_Contain_Roof_100", "DC_Contain_Roof_150", "DC_Contain_Roof_200")
GOLDEN = json.load(open(SV.BASELINE_PATH))
SHARED = GOLDEN.pop(SV.SHARED_KEY)
NAMES = [b.name for b in catalog.BLOCKS]


def _man(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


def _parts(name):
    return {k: tuple(v) for k, v in _man(name)["fractured"]["parts"].items()}


# ---------------------------------------------------------------------------------------------- the rules
def test_role_of_rules(monkeypatch):
    assert FR.role_of("tray", "cable", "AtlasDecal_Stickers02") == "hide"
    assert FR.role_of("contain_roof", "glass", "FrostedGlass") == "glass"
    assert FR.role_of("rack", "perf", "MetalPerforationSteel") == "skin"
    monkeypatch.setattr(FR, "ROLES", {"rack": {"support": ("rail",)}})
    assert FR.role_of("rack", "rail", "PaintedMetalDarker") == "support"
    assert FR.role_of("rack", "rails", "PaintedMetalDarker") == "skin"         # exact name, as KEEP_WHOLE
    assert FR.role_of("rack", "rail", "EmissiveGreen") == "hide"               # the material rules come first
    assert FR.role_of("server", "rail", "PaintedMetalDarker") == "skin"        # another family's table


def test_hide_is_one_predicate():
    """One hide test (preflight D3): role_of's hide is fracture.is_hide, and the exporter imports the same table."""
    from unittest import mock
    with mock.patch.object(FR, "is_hide", return_value=True) as h:
        assert FR.role_of("rack", "perf", "PaintedMetalDarker") == "hide"
        h.assert_called_once_with("PaintedMetalDarker")
    for m in FR.HIDE_PREFIXES:
        assert FR.is_hide(m + "_X") and FR.role_of("rack", "x", m + "_X") == "hide"


def test_role_tables_filled_by_family_tasks():
    """Every family has a role table, filled per family (the servers' ears and slides; the
    trays' cables, hangers and hardware; the room's pedestals, frames, hangers and the PDUs' detail;
    the CRAC's hardware and pipes; the racks' posts, rails, slides and containment rail); only the
    containment doors' stays empty (vanilla doors have no support)."""
    assert set(FR.ROLES) == set(FR.KEEP_WHOLE)
    assert {f for f, v in FR.ROLES.items() if v} == {"server", "tray", "crac", "floor", "contain_roof", "sign",
                                                     "pdu_cabinet", "pdu_strip", "rack"}
    assert FR.ROLES["contain_door"] == {}          # vanilla doors have no support


def test_role_props_match_guide():
    """Per role: (ConstructionMeshType, ConstructionMeshVisibility, ConstructionMeshPreset) per role, each preset a
    preset of the generator."""
    assert FR.ROLE_IDS == ("skin", "hide", "support", "frame", "glass")
    assert FR.ROLE_SUFFIX == {"skin": "", "hide": "_Hide", "support": "_Support", "frame": "_Frame", "glass": ""}
    assert FR.ROLE_PROPS == {"skin": ("Default", "AlwaysVisible", "Default"),
                             "hide": ("Default", "AlwaysHidden", "Default"),
                             "support": ("Default", "AlwaysVisible", "Support"),
                             "frame": ("Split", "HiddenUntilSecondSequenceStart", "Default"),
                             "glass": ("Default", "AlwaysVisible", "WindowGlass")}
    assert all(p.lower() in C.PRESETS for _t, _v, p in FR.ROLE_PROPS.values())
    assert set(FR.GLASS_MATERIALS) == {"FrostedGlass", "WindowGlass", "WindowGlassThin", "ClearGlass"}


def test_skin_carrier():
    """A zone keeps a skin. LOD0 without a skin fails with a message naming the zone and the roles it has (the
    exporter would otherwise raise later, or ship a group without ColliderMeshGroups); a lower LOD promotes the first
    present role in ROLE_IDS order."""
    assert FR.skin_carrier({"skin", "glass"}, 0, "B", "Fracture_01") == "skin"
    assert FR.skin_carrier({"glass", "hide", "frame"}, 1, "B", "Fracture_01") == "hide"
    assert FR.skin_carrier({"glass", "frame"}, 2, "B", "Fracture_01") == "frame"
    assert FR.skin_carrier(set(), 1, "B", "Fracture_01") is None
    with pytest.raises(RuntimeError, match=r"B: fracture zone Fracture_03 has no LOD0 skin face .*glass, support"):
        FR.skin_carrier({"support", "glass"}, 0, "B", "Fracture_03")
    with pytest.raises(RuntimeError, match="no LOD0 geometry"):
        FR.skin_carrier(set(), 0, "B", "Fracture_03")


# ---------------------------------------------------------------------------------------------- the build
@pytest.mark.build
@pytest.mark.parametrize("name", NAMES)
def test_zone_names_match_baseline(name):
    """Save compatibility: a save's DamagedFractures bind to the zone ids, critical list and NF mesh parts."""
    rec = SV.baseline_record(name)
    for k in ("zones", "critical", "nf_parts"):
        assert rec[k] == GOLDEN[name][k], (name, k)


@pytest.mark.build
def test_no_definition_guid_removed():
    """Every definition GUID of the baseline (per block and outside the block folders) still exists."""
    for name in NAMES:
        gone = set(GOLDEN[name]["def_guids"]) - set(SV.def_guids(name))
        assert not gone, (name, sorted(gone))
    assert not set(SHARED) - set(SV.shared_def_guids()), sorted(set(SHARED) - set(SV.shared_def_guids()))


@pytest.mark.build
@pytest.mark.parametrize("name", ROOFS)
def test_roof_glass_builds_as_glass(name):
    """(The stage identity test is gone: the scaffold changes every block's stages.) The
    roofs' glass parts are the baseline's FrostedGlass parts, with the WindowGlass preset (SetMaterial 83c075f5 from
    stage 0)."""
    parts = _parts(name)
    glass = sorted(p for p, v in parts.items() if tuple(v) == FR.ROLE_PROPS["glass"])
    assert glass and glass == sorted(p for p in GOLDEN[name]["fr_parts"] if p.endswith("-FrostedGlass")), name
    s0 = {c["Value"]["MeshPart"]: c["Value"] for c in SV.installed_stages(name)[0]["Value"]["PartChanges"]["_data"]}
    assert all(s0[p]["SetMaterial"] == WINDOWGLASS for p in glass), name


@pytest.mark.build
@pytest.mark.parametrize("name", NAMES)
def test_lower_lod_groups_exist_at_lod0(name):
    """Guide §2.4: the generator reads LOD0, so every Group of FR LOD1..n-2 is a LOD0 group (the LastLOD has none)."""
    lods = _man(name)["fractured"]["lods"]
    lod0 = set(lods[0].get("groups") or [])
    for i, lod in enumerate(lods[1:-1], 1):
        assert set(lod.get("groups") or []) <= lod0, (name, i, sorted(set(lod["groups"]) - lod0))


@pytest.mark.build
@pytest.mark.parametrize("name", [n for n in NAMES if not FR.unfractured_reason(catalog.BY_NAME[n])])
def test_every_zone_keeps_a_lod0_skin(name):
    """On the exported data: every zone's LOD0 has a skin object (Group = the zone, skin props) carrying
    ColliderMeshGroups = the zone and its present suffixed groups, in role order."""
    man = _man(name)
    fbx = os.path.join(config.MODELS_DIR, name, "Fractured", man["fractured"]["lods"][0]["file"])
    props = FRR.fbx_model_props(fbx)
    groups = {p.get("Group") for p in props.values()}
    skin = dict(zip(("ConstructionMeshType", "ConstructionMeshVisibility", "ConstructionMeshPreset"),
                    FR.ROLE_PROPS["skin"]))
    for z in man["fractured"]["zones"]:
        zid = z["id"]
        carriers = [p for p in props.values() if p.get("Group") == zid and p.get("ColliderMeshGroups")]
        assert len(carriers) == 1, (name, zid, len(carriers))
        c = carriers[0]
        assert all(c.get(k) == v for k, v in skin.items()), (name, zid, c)
        want = [zid] + [zid + FR.ROLE_SUFFIX[r] for r in FR.ROLE_IDS if FR.ROLE_SUFFIX[r]
                        and zid + FR.ROLE_SUFFIX[r] in groups]
        assert c["ColliderMeshGroups"].split("|") == want, (name, zid)


@pytest.mark.build
@pytest.mark.parametrize("name", NAMES)
def test_role_manifest(name):
    """export.json: LOD0 triangles per role and per zone per role bounds; skin, hide, (the roofs') glass, and support
    exactly on the families whose role table names it (the servers). Every LOD0 face has a role:
    the role triangles are exactly the FR LOD0 minus its break faces (FracturedMaterial01), its scaffold
    (no role: it has no zone) and its baked stand-ins (the parked subparts, not the block's own faces)."""
    fr = _man(name)["fractured"]
    rt = fr["role_tris"]
    assert set(rt) == set(FR.ROLE_IDS), name
    fam = catalog.BY_NAME[name].family
    is_cut = FR.unfractured_reason(catalog.BY_NAME[name]) is None     # (unfractured: no part names, roles by material)
    for role in ("support", "frame"):
        assert (rt[role] > 0) == (is_cut and bool(FR.ROLES[fam].get(role))), (name, role)
    assert (rt["glass"] > 0) == (name in ROOFS), name
    zones = [z["id"] for z in fr.get("zones") or []]
    assert sorted(fr["role_bounds"]) == sorted(zones), name
    for z, roles in fr["role_bounds"].items():
        assert "skin" in roles and set(roles) <= set(FR.ROLE_IDS), (name, z)
        for b in roles.values():
            assert len(b) == 6 and all(b[i] <= b[i + 3] for i in range(3)), (name, z, b)
    meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "Fractured", fr["lods"][0]["file"]))
    cut = sum(len(p) - 2 for m in meshes.values() for p, k in zip(m["polys"], m["poly_mat"])
              if m["materials"][k] == FR.CUT_MATERIAL)
    scaffold = ((fr.get("scaffold") or {}).get("tris") or {}).get("0", 0)
    standins = ((fr.get("standins") or {}).get("tris") or {}).get("0", 0)
    assert sum(rt.values()) == fr["lods"][0]["tris"] - cut - scaffold - standins, name
