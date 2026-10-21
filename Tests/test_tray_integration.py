"""The tray family in the definitions pipeline (clone, stage, install, first game build).

  * every tray block (38) is cloned under its own key in .clonemap.json: the trays, Drops, Reducers and the Chute
    from WallInsertPipes, the rod hangers from StructuralSupportStraight with its second file prefix
    (TrussFrame_Long, the LastLod material) renamed in the same copy;
  * every tray block's staged definition: PCU 5 (Plan Decision 12), no MountPointGeneratorSettings (all six
    directions: ports on every face), and the cloned PlacementDefinition with AutoRotateFace null;
  * the built ones (export.json): unfractured (Decision 10), the Fractured collider = the physics boxes, at most 8
    mesh parts (the builder's limit).
"""
import json
import os

import pytest

from dc import menu, catalog, clone, config, integration, names
from dc import fracture as FR
from dc.assetio import meta_id, own_guid, read_json

TRAYS = [b for b in catalog.CATALOGUE if b.family in ("tray", "trayrods")]
PIPES = [b for b in TRAYS if b.copy_from == "WallInsertPipes"]
RODS = [b for b in TRAYS if b.copy_from == "StructuralSupportStraight"]


def _body(d):
    v = d["$Value"]
    return v["Manipulator"] if "PartialDefinitionKind" in v else v


def built_trays():
    return sorted(n for n in integration.built_names() if catalog.BY_NAME[n].family in ("tray", "trayrods"))


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


def staged_def(rel):
    p = os.path.join(config.STAGE_ASSETS, rel)
    return read_json(p) if os.path.exists(p) else None


# ---------------------------------------------------------------------------------------------- catalogue / names
def test_trays_in_the_pipeline():
    """The tray families are wired into the definitions pipeline."""
    assert {"tray", "trayrods"} <= set(catalog.PIPELINE_FAMILIES)
    assert [b for b in catalog.BLOCKS if b in TRAYS] == TRAYS
    assert len(TRAYS) == 38 and len(PIPES) == 35 and len(RODS) == 3


def test_tray_names():
    for b in TRAYS:
        title, desc = names.NAMES[b.name]
        assert len(title) <= 40 and desc.endswith("."), b.name
        if b.density:
            assert b.density in title, (b.name, title)
    assert names.NAMES["DC_Tray_StraightS_Full"][0] == "Cable Tray, Straight (Full)"   # no size in names (2026-10-20)
    # titles are unique per kind: only the sizes of one kind (the two straights, the three rods) share a title
    assert len({names.NAMES[b.name][0] for b in TRAYS}) == len({menu.kind_owner(b).name for b in TRAYS}) == 32


# ---------------------------------------------------------------------------------------------- clones
def test_tray_clones():
    cmap = clone.load_map()
    for b in TRAYS:
        e = clone.entry(b, cmap)
        assert e and e.get("info"), f"{b.name} not cloned"
        info = e["info"]
        assert info["binding"].endswith(f"{b.copy_from}.partialdef"), (b.name, info["binding"])
        root = os.path.join(config.MOD_ASSETS, config.NAME, b.name)
        files = [f for _, _, fs in os.walk(root) for f in fs]
        assert not [f for f in files if b.copy_from in f], f"{b.name}: vanilla prefix left in {root}"
        bd = read_json(os.path.join(config.MOD_ASSETS, info["block_def_file"]))
        assert "MountPointGeneratorSettings" not in _body(bd), b.name
    for b in RODS:
        root = os.path.join(config.MOD_ASSETS, config.NAME, b.name)
        files = [f for _, _, fs in os.walk(root) for f in fs]
        assert not [f for f in files if "TrussFrame_Long" in f], (b.name, files)
        assert f"{b.name}_LastLod.def" in files, b.name
        also = [c["also"] for c in clone.entry(b)["copies"] if c["src"] == b.vanilla_source][0]
        assert also == [f"TrussFrame_Long={b.name}"]
        assert clone.ALSO["StructuralSupportStraight"](b.name) == also


# ---------------------------------------------------------------------------------------------- patches
def test_tray_pcu_and_placer(staged):
    for b in TRAYS:
        info = clone.entry(b)["info"]
        bd = staged_def(info["block_def_file"])
        assert bd, f"{b.name}: block definition not staged"
        m = _body(bd)
        assert m["PCU"] == 5, b.name
        assert "MountPointGeneratorSettings" not in m, b.name
        s = staged["blocks"][b.name]["tray"]
        assert s["pcu"] == 5
        if b in PIPES:
            rel = s["placer_file"]
            assert rel and rel.endswith(f"{b.name}_PlacementDefinition.def"), (b.name, rel)
            pl = staged_def(rel)
            assert pl is not None, rel
            assert "AutoRotateFace" in _body(pl) and _body(pl)["AutoRotateFace"] is None, b.name
            assert m["PlacerDefinition"] == own_guid(pl) == s["placer"], b.name
            assert meta_id(os.path.join(config.STAGE_ASSETS, rel)) in (None, own_guid(pl))
            assert meta_id(os.path.join(config.MOD_ASSETS, rel)) == own_guid(pl)
        else:   # the strut clone has no placer of its own (its template's), so the rod hangers get one
            rel = s["placer_file"]
            assert rel == f"{config.NAME}/{b.name}/{b.name}_PlacementDefinition.def", (b.name, rel)
            pl = staged_def(rel)
            assert pl is not None and pl["$Type"].endswith("PlacementDefinitionObjectBuilder"), rel
            assert _body(pl)["AutoRotateFace"] is None and _body(pl)["AlignWithMountPoints"] is True, b.name
            assert m["PlacerDefinition"] == own_guid(pl) == s["placer"], b.name
            assert meta_id(os.path.join(config.STAGE_ASSETS, rel)) in (None, own_guid(pl))


def test_rods_effects_dummy(staged):
    """Every built rod hanger's model definition carries a "ParticleEffects" dummy (the
    damage / destruction effects origin every block has; the cloned strut's had none) at the block centre."""
    rods = [b for b in TRAYS if b.family == "trayrods"]
    assert rods
    for b in rods:
        if b.name not in built_trays():
            continue
        info = clone.entry(b)["info"]
        bmd = staged_def(info["model_def_file"])
        m = _body(bmd)
        assert list(m)[:3] == ["Guid", "Model", "Dummies"], list(m)
        pe = [c["Value"] for c in m["Dummies"]["Changed"] if c["Value"]["Name"] == "ParticleEffects"]
        assert len(pe) == 1 and pe[0]["Type"] == integration.PARTICLE_EFFECTS_TYPE, b.name
        assert list(pe[0]["Transform"]["Transform"]["Position"].values()) == manifest(b.name)["shift"]
        assert len(m["Dummies"]["Keys"]) == len(m["Dummies"]["Changed"]), b.name


def test_tray_patch_is_idempotent():
    """tray_patch on an already patched definition changes nothing (re-staging over an installed copy)."""
    b = PIPES[0]
    bd = read_json(os.path.join(config.MOD_ASSETS, clone.entry(b)["info"]["block_def_file"]))
    integration.tray_patch(b, bd)
    once = json.dumps(bd, sort_keys=True)
    integration.tray_patch(b, bd)
    assert json.dumps(bd, sort_keys=True) == once


def test_built_trays_unlocked(staged):
    assert built_trays(), "no tray block is built and exported yet"
    unlock = set(staged["unlock"])
    for n in built_trays():
        assert staged["blocks"][n]["built"], n
        assert clone.entry(catalog.BY_NAME[n])["info"]["server_prefab"] in unlock, n
    for b in TRAYS:
        if b.name not in built_trays():
            assert not staged["blocks"][b.name]["built"], b.name


# ---------------------------------------------------------------------------------------------- exports
def manifest(n):
    return read_json(os.path.join(config.MODELS_DIR, n, "export.json"))


def _gltf_boxes(path):
    """{node name: (min, max)} of every collider node in a collision glTF (POSITION accessor bounds + translation)."""
    g = read_json(path)
    out = {}
    for n in g["nodes"]:
        if "mesh" not in n:
            continue
        acc = g["accessors"][g["meshes"][n["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
        t = n.get("translation") or [0, 0, 0]
        out[n["name"]] = (tuple(round(a + b, 4) for a, b in zip(acc["min"], t)),
                          tuple(round(a + b, 4) for a, b in zip(acc["max"], t)))
    return out


def test_tray_fractured():
    """Every tray fractures by its plan (dc/fracture.py): 2 .. Keen's maximum zones for
    its size, one box collider per zone named after it (the zone's hull, in the glTF frame), and the hulls cover
    every NonFractured physics box (the breakable collider is the block's physics once a fracture is damaged)."""
    rep = read_json(config.REPORT_PATH)["blocks"]
    assert built_trays()
    from dc import catalog as C
    for n in built_trays():
        m = manifest(n)
        if FR.unfractured_reason(C.BY_NAME[n]):     # the rod hangers and the Chute: no fractures (non-breakable);
            assert m["fractured"]["zones"] == [], n  # their dented debris: test_damaged_geometry
            continue
        assert m["fractured"]["kind"] == "cut", n
        zones = m["fractured"]["zones"]
        assert 2 <= len(zones) <= FR.max_fractures(m["nonfractured"]["size"]), (n, len(zones))
        fr = _gltf_boxes(os.path.join(config.MODELS_DIR, n, "Fractured", m["fractured"]["collision"]["file"]))
        nf = _gltf_boxes(os.path.join(config.MODELS_DIR, n, "NonFractured", m["nonfractured"]["collision"]["file"]))
        assert sorted(fr) == sorted(z["id"] for z in zones), (n, sorted(fr))
        hulls = []
        for z in zones:
            lo, hi = z["lo"], z["hi"]                      # Blender (x, y, z) -> glTF (x, z, -y)
            g = (lo[0], lo[2], -hi[1]), (hi[0], hi[2], -lo[1])
            assert list(fr[z["id"]][0] + fr[z["id"]][1]) == pytest.approx(list(g[0] + g[1]), abs=2e-4), (n, z["id"])
            hulls.append(g)
        regular = [box for k, box in nf.items() if not k.lower().startswith(("occupancy", "mountpoints"))]
        assert len(regular) == rep[n]["colliders"]["regular"], n
        # the colliders follow the zones' solid (test_fracture_refine), not the physics boxes, so they no
        # longer cover a box's empty corners; every one stays inside the block's cells
        half = [0.125 * c for c in C.BY_NAME[n].cells]     # game cells (x, up, depth) = glTF axes (x, y, -z)
        for lo, hi in hulls:
            assert all(-half[i] - 1e-4 <= lo[i] and hi[i] <= half[i] + 1e-4 for i in range(3)), (n, lo, hi)


def test_tray_mesh_parts():
    """Keen's limits (ModelLimitsChecker, decompiled): an unfractured model of 0.5 .. 2 m holds at most 8 materials
    = mesh parts per LOD; a FRACTURED one 32 materials and 256 mesh parts ("<group>-<material>") per LOD. An earlier
    "8 mesh parts" ceiling on a 2-zone server came from a ColliderMeshGroups entry naming a missing group: the
    importer then drops every fracture (ModelProcessorLoader.CollectBreakableCollider) and checks it as unfractured."""
    assert built_trays()
    for n in built_trays():
        m = manifest(n)
        for lod in m["nonfractured"]["lods"]:
            assert len(lod["materials"]) <= 8, (n, "nonfractured", lod["file"])
        assert len(m["fractured"]["parts"]) <= 256, n
        for variant in ("fractured", "damaged"):
            for lod in m.get(variant, {}).get("lods", []):
                assert len(lod["materials"]) <= 32, (n, variant, lod["file"])