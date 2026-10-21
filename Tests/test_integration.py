"""Task 5: clones, exports, the staged integration package and the install dry run (no Blender needed).

Ruling 2: the per-model checks apply to the blocks built so far (a placement entry in build_report.json); the
clones cover the whole catalogue."""
import json
import os
import re
import subprocess

import pytest

from dc import catalog, clone, config, integration, menu, names
from dc.assetio import meta_id, own_guid, read_json
from dc.material_guids import MATERIAL_GUIDS, guid as mat_guid

STAGE = integration.STAGE
INSTALL = os.path.join(config.INTEGRATION_DIR, "install.sh")
SDK_MATERIALS = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/"
                                   "GameData/Vanilla/Assets/BlockMaterials")


def built():
    return sorted(integration.built_names())


def manifest(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


def asset_id(rel):
    """AssetID of a staged asset: its staged .meta, else the installed one (the mod keeps its built .meta)."""
    return integration.asset_id(rel)


@pytest.fixture(scope="module")
def staged():
    integration.write_all()
    return STAGE


# ---------------------------------------------------------------------------------------------- clones
def test_every_catalogue_block_cloned():
    cmap = clone.load_map()
    assert cmap.get("$keyed"), ".clonemap.json must be keyed per block (se2mod.py copy --map-key)"
    for b in catalog.BLOCKS:
        e = clone.entry(b, cmap)
        assert e and e.get("info"), f"{b.name} not cloned"
        srcs = {c["src"] for c in e["copies"]}
        assert b.vanilla_source in srcs, (b.name, srcs)
        info = e["info"]
        bd = read_json(os.path.join(config.MOD_ASSETS, info["block_def_file"]))
        # Task 10: a 24U rack joins its 42U sibling's kind (two sizes of one kind, dc/menu.py)
        owner = clone.entry(menu.kind_owner(b), cmap)["info"]["kind"]
        assert bd["$Value"]["Manipulator"]["BlockKind"] in (info["kind"], owner), f"{b.name}: BlockKind not rewired"
        assert info["kind"] != info["vanilla"]["kind_guid"]


def test_clone_guids_unique_and_metas_match():
    seen = {}
    for dp, _, fs in os.walk(os.path.join(config.MOD_ASSETS, config.NAME)):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                p = os.path.join(dp, f)
                g = own_guid(read_json(p))
                if g is None:
                    continue
                assert g not in seen, f"{p} and {seen[g]} define the same GUID {g}"
                seen[g] = p
                assert meta_id(p) == g, f"{p}: .meta AssetID {meta_id(p)} != definition GUID {g}"
    assert len(seen) > 200


def test_door_subparts_renamed():
    for b in catalog.BLOCKS:
        if b.copy_from != "SlidingDoorNarrow250":
            continue
        root = os.path.join(config.MOD_ASSETS, config.NAME, b.name)
        files = [f for _, _, fs in os.walk(root) for f in fs]
        assert not [f for f in files if "SlideDoorNarrow_250_" in f or "NarrowSlidingDoor" in f], b.name
        subs = os.listdir(os.path.join(root, "Subparts"))
        assert f"{b.name}_LeftDoor.def" in subs and f"{b.name}_RightDoor.def" in subs, subs
        also = [c["also"] for c in clone.entry(b)["copies"] if c["src"] == b.vanilla_source][0]
        assert f"SlideDoorNarrow_250_={b.name}_" in also


def test_names_for_every_block():
    assert set(names.NAMES) == {b.name for b in catalog.CATALOGUE}   # Plan 3: room blocks are named before wiring
    for n, (title, desc) in names.NAMES.items():
        assert title and desc and len(title) <= 40, n


# ---------------------------------------------------------------------------------------------- materials
def test_material_slots_resolve():
    """Every material slot of every exported LOD (NonFractured, Fractured, Damaged) maps to a vanilla GUID; a Damaged
    slot through its broken remap (fracture.DAMAGED_SLOTS) too."""
    from dc.fracture import DAMAGED_SLOTS
    assert built()
    for n in built():
        m = manifest(n)
        for variant in ("nonfractured", "fractured", "damaged"):
            for lod in m.get(variant, {}).get("lods", []):
                for slot in lod["materials"]:
                    assert re.fullmatch(r"[0-9a-f-]{36}", mat_guid(slot)), (n, variant, lod["file"], slot)
                    if variant == "damaged":
                        assert re.fullmatch(r"[0-9a-f-]{36}", mat_guid(DAMAGED_SLOTS.get(slot, slot))), (n, slot)


@pytest.mark.skipif(not os.path.isdir(SDK_MATERIALS), reason="Mod SDK not installed")
def test_material_guids_are_vanilla_definitions():
    """Each GUID is its file's own: a .def's Guid, or a Copy .partialdef's Manipulator Guid (Plan 5 Task 3, ruling
    R7: PaintedMetalDarkerDeformed is a Copy of PaintedMetalColorableDeformed)."""
    for slot, (g, rel) in MATERIAL_GUIDS.items():
        v = read_json(os.path.join(SDK_MATERIALS, rel))["$Value"]
        if rel.endswith(".partialdef"):
            assert v["PartialDefinitionKind"] == "Copy" and v["DefinitionType"].endswith("MaterialDefinition"), rel
            v = v["Manipulator"]
        assert v["Guid"] == g, (slot, rel)


# ---------------------------------------------------------------------------------------------- exports
def test_exports_complete():
    for n in built():
        spec = catalog.BY_NAME[n]
        m = manifest(n)
        rep = read_json(config.REPORT_PATH)["blocks"][n]
        # a light tray's cut LOD0 may need one more LOD (Keen keys the count on each model's LOD0: the kit's mid detail)
        assert len(m["nonfractured"]["lods"]) == len(rep["lods"]) == len(m["fractured"]["lods"]) - \
            int(m["fractured"].get("mid_lod", False))
        assert m["shift"] == [0.125 if c % 2 == 0 else 0.0 for c in spec.cells]
        for variant, sub in (("nonfractured", "NonFractured"), ("fractured", "Fractured"), ("damaged", "Damaged")):
            if variant not in m:
                from dc.fracture import unfractured_reason
                assert unfractured_reason(spec), (n, "no Damaged model")
                continue
            c = m[variant]["collision"]
            assert set(c["extensionsUsed"]) >= {"MSFT_collision_primitives", "MSFT_rigid_bodies"}, (n, variant)
            for f in [l["file"] for l in m[variant]["lods"]] + [c["file"], c["bin"]]:
                assert os.path.exists(os.path.join(config.MODELS_DIR, n, sub, f)), (n, f)
            assert all(l["objects"] >= 1 for l in m[variant]["lods"])
        # merged per LOD: one object per LOD (NonFractured), NonFractured tris equal the build report's
        assert [l["objects"] for l in m["nonfractured"]["lods"]] == [1] * len(rep["lods"])
        assert [l["tris"] for l in m["nonfractured"]["lods"]] == [l["tris"] for l in rep["lods"]]
        zones = [z["id"] for z in m["fractured"]["zones"]]
        nodes = m["fractured"]["collision"]["nodes"]
        if m["fractured"].get("kind") == "cut":
            # Task 9b (dc/fracture.py; Task 9c: the racks too): planned zones, one convex collider each, every zone's
            # skin in every LOD but the LastLOD box, the Damaged model with the same groups
            assert 2 <= len(zones) <= 16 and sorted(nodes) == sorted(zones)
            assert sorted(m["damaged"]["collision"]["nodes"]) == sorted(zones)
            for v in ("fractured", "damaged"):
                for l in m[v]["lods"][:-1]:
                    assert set(zones) <= set(l["groups"]), (n, v, l["file"], l["groups"])
                    assert all(g.startswith("Fracture_") for g in l["groups"])
                assert m[v]["lods"][-1]["groups"] == []
        else:   # the justified exception (fracture.UNFRACTURED): unfractured, its plain physics boxes
            from dc.fracture import unfractured_reason
            assert unfractured_reason(spec), f"{n}: unfractured model without a reason"
            assert zones == [] and len(nodes) == rep["colliders"]["regular"]
            assert not [nd for nd in nodes if nd.lower().startswith("fracture")]
            assert all(l["groups"] == [] for l in m["fractured"]["lods"])
        assert m["nonfractured"]["collision"]["colliders"] == sum(rep["colliders"][k] for k in
                                                                  ("regular", "occupancy_hints", "mount_hints"))


# ---------------------------------------------------------------------------------------------- staging
def test_every_block_staged(staged):
    """Each built block has a staged BlockModelDefinition whose Model / FractureModel / DamagedModel reference a
    staged .model by its .meta AssetID, and the definition's own .meta AssetID equals its GUID."""
    assert built()
    for n in built():
        info = clone.entry(catalog.BY_NAME[n])["info"]
        rel = info["model_def_file"]
        p = os.path.join(config.STAGE_ASSETS, rel)
        assert os.path.exists(p), f"{n}: no staged {rel}"
        bmd = read_json(p)
        m = bmd["$Value"]["Manipulator"]
        assert asset_id(rel) == own_guid(bmd) == info["model_def"]
        dmg = f"Models/Damaged/{n}_Damaged.model" if manifest(n).get("damaged") else f"Models/Fractured/{n}_Fractured.model"
        for key, model in (("Model", f"Models/NonFractured/{n}.model"),
                           ("FractureModel", f"Models/Fractured/{n}_Fractured.model"),
                           ("DamagedModel", dmg)):
            mrel = f"{config.NAME}/{n}/{model}"
            assert os.path.exists(os.path.join(config.STAGE_ASSETS, mrel)), mrel
            assert m[key] == "{G}" + asset_id(mrel), (n, key)
        stages = m["BuildProgressModels"]
        assert stages[0]["Value"]["Model"] == m["FractureModel"] and stages[-1]["Value"]["Model"] == m["Model"]
        assert [s["Value"]["BuildRatioLowerBound"] for s in stages] == [0, 0.1, 0.2, 0.3, 0.5333, 0.7667, 1]
        pe = [c["Value"] for c in m["Dummies"]["Changed"] if c["Value"]["Name"] in ("ParticleEffects", "Particles") or (
            not c["Value"]["Name"] and c["Value"]["Type"] == integration.CONSTRUCTION_PARTICLES)][0]
        assert list(pe["Transform"]["Transform"]["Position"].values()) == manifest(n)["shift"]
        # every .model reference resolves to a staged asset
        for model in {f"Models/NonFractured/{n}.model", f"Models/Fractured/{n}_Fractured.model", dmg}:
            ma = read_json(os.path.join(config.STAGE_ASSETS, config.NAME, n, model))["$Value"]
            folder = os.path.dirname(f"{config.NAME}/{n}/{model}")
            files = {asset_id(f"{folder}/{f}"): f for f in os.listdir(os.path.join(config.STAGE_ASSETS, folder))
                     if not f.endswith(".meta")}
            for ga in ma["GeometryAssets"]:
                assert ga["AssetReference"][3:] in files, (n, model, ga["AssetReference"])
            assert ma["CollisionShapesAsset"]["AssetReference"][3:] in files
            assert ma["GeometryAssets"][0]["Transformations"]["Translation"] == dict(
                zip("XYZ", manifest(n)["shift"]))
            assert {a["MaterialName"] for a in ma["MaterialAssignments"]} == {
                s for ga in ma["GeometryAssets"] for s in ga["UsedMaterials"]}


def test_names_staged(staged):
    for b in catalog.BLOCKS:
        info = clone.entry(b)["info"]
        kind = read_json(os.path.join(config.STAGE_ASSETS, info["kind_file"]))["$Value"]
        bd = read_json(os.path.join(config.STAGE_ASSETS, info["block_def_file"]))["$Value"]["Manipulator"]
        assert bd["UIData"]["Name"] == names.NAMES[b.name][0]
        # the kind tile: a family kind (racks: shared by 42U + 24U) or the server's own name (dc/menu.py)
        want = menu.kind_text(b) if menu.owns_kind(b) else names.NAMES[b.name]
        assert (kind["Name"], kind["Description"]) == want
        assert "Description" not in bd["UIData"]


def test_guids_stable():
    """Two consecutive write_all runs leave asset_guids.json byte-identical (and so every staged reference)."""
    path = os.path.join(config.HERE, "asset_guids.json")
    integration.write_all()
    with open(path) as f:
        first = f.read()
    integration.write_all()
    with open(path) as f:
        assert f.read() == first
    assert len(json.loads(first)) > 100


def test_install_dry_run_clean(staged):
    r = subprocess.run(["bash", INSTALL], capture_output=True, text=True,
                       env=dict(os.environ, DC_STAGE_SRC=STAGE))   # this run's staging (Tests/conftest.py)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "  0 problems" in r.stdout, r.stdout
    assert "Dry run only" in r.stdout


# ---------------------------------------------------------------------------------------------- placement
@pytest.mark.build
def test_exported_placement_matches_report():
    """check_placement.py (blender -b) on the EXPORTED LOD0 FBX + collision glTF reproduces build_report.json."""
    rep = read_json(config.REPORT_PATH)["blocks"]
    for n in built():
        p = os.path.join(config.MODELS_DIR, n, "placement_exported.json")
        assert os.path.exists(p), f"{n}: run blender -b --python Source/Model/check_placement.py -- all"
        fbx = os.path.join(config.MODELS_DIR, n, "NonFractured", f"{n}.fbx")
        import hashlib
        with open(fbx, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        assert read_json(p).get("fbx_sha256") == sha, f"{n}: placement check measured a different FBX than the export"
        got = read_json(p)["nonfractured"]
        want = rep[n]["placement"]
        assert (got["occupied"], got["total"]) == (want["occupied"], want["total"]), n
        assert sorted(map(tuple, got["free_cells"])) == sorted(map(tuple, want["free_cells"])), n
        for d, f in want["faces"].items():
            assert got["faces"][d]["groups"] == f["groups"], (n, d)
            assert got["faces"][d]["coverage"] == pytest.approx(f["coverage"], abs=1e-4), (n, d)


# ---------------------------------------------------------------------------------------------- render bounds
@pytest.mark.build
def test_render_mesh_within_bounds():
    """No LOD0 render vertex lies outside the block's cell box (tolerance 0), so flush neighbours never share a
    coplanar face (z-fighting). The box is catalog.bounds in the game frame: cell i spans 0.25 i +- 0.125 after the
    .model's per-axis shift; the mesh (Blender frame, centred) maps to game as (x, z, -y) + shift.

    Exception (Ruling 8): server rack ears overhang the server's cells in x (to |x| 0.288 against 0.25), because
    real ears land on the rack's 19-inch rails in the rack's front zone. So x is exempt for servers only.
    The same front hardware (ear flanges, thumbscrews, pull handles) also stands proud of the server's FRONT plane,
    into the rack's front zone (Task 4: max 6 cm, test_server_clearance), so the server's front (game -z) is bounded
    by that front-zone limit instead of the cell plane; rear, top, bottom (and every rack axis) are strict."""
    rep = read_json(config.REPORT_PATH)["blocks"]
    every = sorted(n for n, e in rep.items() if e.get("placement", {}).get("total"))   # trays too (Plan 2 T4)
    assert set(built()) <= set(every)
    for n in every:
        spec = catalog.BY_NAME[n]
        e = rep[n]
        assert "render_bounds" in e, f"{n}: rebuild (build_dc.py) to record render_bounds"
        (bx0, by0, bz0), (bx1, by1, bz1) = e["render_bounds"]
        shift = [0.125 if c % 2 == 0 else 0.0 for c in spec.cells]
        game = {0: (bx0 + shift[0], bx1 + shift[0]),          # game x = blender x
                1: (bz0 + shift[1], bz1 + shift[1]),          # game y (up) = blender z
                2: (-by1 + shift[2], -by0 + shift[2])}        # game z = -blender y
        lo, hi = catalog.bounds(spec)
        for ax in range(3):
            if ax == 0 and spec.family == "server":
                continue   # Ruling 8: the rack ears
            box = (0.25 * lo[ax] - 0.125, 0.25 * hi[ax] + 0.125)
            if ax == 2 and spec.family == "server":   # front hardware in the rack's front zone (see docstring)
                box = (box[0] - 0.06, box[1])
            g0, g1 = game[ax]
            assert g0 >= box[0] - 1e-9 and g1 <= box[1] + 1e-9, (n, "xyz"[ax], (g0, g1), box)
        if spec.family == "rack":   # the side planes: a hairline (>= 1 mm) gap to a flush neighbour
            assert max(-bx0, bx1) <= 0.125 * spec.cells[0] - 0.001 + 1e-9, (n, bx0, bx1)
