"""The construction scaffold (dc/scaffold.py, fracture_mesh.scaffold_object,
export_models._plan_scaffold). The cage the welders work from: an ungrouped BrushedMetal lattice in the Fractured model
only (Scaffold / AlwaysVisible / Scaffolding: see-through BrushedMetal_Scaffold until 30 %), never in the Damaged model,
hidden on a finished block that is shot (the stage-1.0 ApplyOnlyWhenDamaged entry), within the block's cells, and never
pushing the Fractured model over its LOD row.

Also the export determinism (the Damaged dents are seeded per block) and its opt-in end-to-end check."""
import glob
import json
import os
import shutil
import subprocess
import tempfile

import pytest

from dc import catalog, config, scaffold as SC, state_view as SV
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import read_json

BM = "BrushedMetal_Scaffold"
SCAFFOLD_MAT = "4050183d-1340-4643-b8b9-124981f2121d"      # BrushedMetal_Scaffold: the Scaffolding preset's sequence 1
# the light empty / low trays whose FR LOD0 already sits at its LOD row: not even the edges-only cage fits their
# triangle budget. Exactly these; every other cut block carries a scaffold.
NO_ROOM = ("DC_Tray_StraightL_Empty", "DC_Tray_StraightS_Low", "DC_Tray_TurnH_Empty", "DC_Tray_TurnUp_Empty")
NAMES = [b.name for b in catalog.BLOCKS]


def _man(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


CUT = [n for n in NAMES if _man(n)["fractured"].get("kind") == "cut"]
UNCUT = [n for n in NAMES if n not in CUT]
CAGED = [n for n in CUT if n not in NO_ROOM]


def _fr_fbx(name, lod=0, kind="Fractured"):
    m = _man(name)
    key = "fractured" if kind == "Fractured" else "damaged"
    return os.path.join(config.MODELS_DIR, name, kind, m[key]["lods"][lod]["file"])


def _scaffold_meshes(path):
    return [m for m in FRR.fbx_meshes(path).values() if m["props"].get("ConstructionMeshType") == "Scaffold"]


def _tris(meshes):
    return sum(len(p) - 2 for m in meshes for p in m["polys"])


def _box(lo, hi):
    return [(tuple(lo), tuple(hi))]


# ---------------------------------------------------------------------------------------------- the cage (pure)
def test_cage_unit_box():
    unit = _box((0, 0, 0), (1, 1, 1))
    assert len(SC.cage(unit, 1.0, 0)) == 12
    assert len(SC.cage(unit, 0.5, 0)) == 24        # + one interior line per direction on each of the 6 faces
    assert len(SC.cage(unit, SC.EDGES_ONLY, 0)) == 12
    two = unit + _box((1, 0, 0), (2, 1, 1))
    m = SC.cage(two, 1.0, 0)
    key = [tuple(sorted((tuple(round(c, 6) for c in a), tuple(round(c, 6) for c in b)))) for a, b in m]
    assert len(key) == len(set(key))
    # the union's 12 edges (the long ones merged across the joint) + the joint's ring on the surface
    assert len(m) == 16


def test_cage_drops_inner_faces_and_stays_inside():
    """Two boxes of an L: no member runs across their shared face's interior, and every member is pulled `inset`
    inside the union (ends too), so a tube of that radius never leaves the block's outline."""
    boxes = _box((0, 0, 0), (1, 1, 0.2)) + _box((0, 1, 0), (0.4, 2, 0.2))
    r = 0.01
    for a, b in SC.cage(boxes, 0.25, r):
        for p in (a, b):
            assert any(all(lo[i] - 1e-9 <= p[i] <= hi[i] + 1e-9 for i in range(3)) for lo, hi in boxes), p
        mid = [(x + y) / 2 for x, y in zip(a, b)]
        assert not (0.0 + r < mid[0] < 0.4 - r and abs(mid[1] - 1.0) < 1e-6 and r < mid[2] < 0.2 - r), (a, b)
    lo = [min(p[i] for m in SC.cage(boxes, 0.25, r) for p in m) for i in range(3)]
    hi = [max(p[i] for m in SC.cage(boxes, 0.25, r) for p in m) for i in range(3)]
    assert lo == pytest.approx([r, r, r]) and hi == pytest.approx([1 - r, 2 - r, 0.2 - r])


def test_snap_merges_near_coincident_faces():
    """Two zone hulls meeting a few mm apart share one row of members, not a doubled bar."""
    boxes = SC._snap_boxes(_box((0, 0, 0), (0.5, 1, 0.2)) + _box((0.503, 0, 0), (1, 1, 0.2)), 0.012)
    assert boxes[0][1][0] == boxes[1][0][0]


def test_reach_cells():
    """A face the block fills (within FILLS of its cell face) moves OUTSET past the cell; others stay."""
    lo, hi = SC.reach_cells((-0.499, -0.3, -0.1245), (0.4995, 0.2, 0.0), (0.5, 0.375, 0.125))
    assert lo == pytest.approx((-0.504, -0.3, -0.129)) and hi == pytest.approx((0.504, 0.2, 0.0))


def test_budget_pdu_cabinet():
    """A measured case: the PDU cabinet (FR 21 464 / budget 28 006) gets at most 3 742 triangles."""
    size = tuple(_man("DC_PDU_Cabinet")["nonfractured"]["size"])
    b = SC.budget(size, 21464, 28006)
    assert int(0.05 * 21464) <= b <= 3742


def test_row_margin_is_the_last_safe_k():
    from se2model import limits
    size = (0.5, 0.498, 0.248)                           # a StraightS tray: its LOD0 sits near a row
    t0 = 1144
    k = SC.row_margin(size, t0, 10_000)
    assert limits.optimal_lods(size, t0 + k) == limits.optimal_lods(size, t0)
    assert limits.optimal_lods(size, t0 + k + 1) != limits.optimal_lods(size, t0)
    assert SC.row_margin(size, t0, 0) == 0


def test_plan_shrinks_by_pitch_and_reserves_room():
    """A tighter budget never changes the boxes, only the pitch (then the tube sides); a stand-in reserve is
    counted as FR triangles already there; no room at all is None."""
    zones = [{"lo": (-0.5, -0.4, -0.12), "hi": (0.5, 0.4, 0.12)}]
    lo, hi = zones[0]["lo"], zones[0]["hi"]
    size = (1.0, 0.8, 0.24)
    big = SC.plan("server", zones, lo, hi, size, [12000, 2000, 12], [20950, 3500, 55])
    tight = SC.plan("server", zones, lo, hi, size, [12000, 2000, 12], [20950, 3500, 55], cap=big.tris[0] - 1)
    assert tight.boxes == big.boxes and tight.tris[0] < big.tris[0]
    assert tight.pitch > big.pitch or tight.sides[0] < big.sides[0]
    res = SC.plan("server", zones, lo, hi, size, [12000, 2000, 12], [20950, 3500, 55], reserve=(2000, 0))
    assert res.tris[0] <= SC.budget(size, 14000, 20950)
    assert SC.plan("server", zones, lo, hi, size, [20000, 2000, 12], [20950, 3500, 55]) is None
    assert big.sides == {0: 8, 1: 4} and big.tris == {0: 16 * len(big.members), 1: 8 * len(big.lod_members[1])}


def test_dent_seed_is_stable_per_block():
    """Export determinism: the Damaged noise seed is a pure function of the block name (CRC-32, not the per-process
    salted hash()), distinct per block."""
    import zlib
    assert FR.dent_seed("DC_Srv_Timer") == zlib.crc32(b"datacenter/DC_Srv_Timer") & 0x7FFFFFFF
    assert len({FR.dent_seed(n) for n in NAMES}) == len(NAMES)
    src = open(os.path.join(config.HERE, "dc", "fracture_mesh.py")).read()
    assert src.count("noise.seed_set(seed)") == 1 and src.count("noise.noise_vector(") == 2


def test_role_tables_cannot_name_skin_or_glass():
    """A part table names only the suffixed roles (a glass or skin entry would give two meshes one
    mesh-part name); role_of never returns skin/glass from a table."""
    FR.check_role_tables(FR.ROLES)
    for bad in ("glass", "skin"):
        with pytest.raises(ValueError, match="may name only"):
            FR.check_role_tables({"rack": {bad: ("rail",)}})
    assert FR.TABLE_ROLES == ("hide", "support", "frame")


# ---------------------------------------------------------------------------------------------- the build
def test_no_room_list_is_exact():
    """Exactly NO_ROOM of the cut blocks export without a scaffold, each because its budget is below one
    edges-only cage (recorded as scaffold: null)."""
    bare = sorted(n for n in CUT if not _man(n)["fractured"].get("scaffold"))
    assert bare == sorted(NO_ROOM)
    for n in NO_ROOM:
        fr = _man(n)["fractured"]
        t0 = fr["lods"][0]["tris"]
        zones = fr["zones"]
        lo = [min(z["lo"][i] for z in zones) for i in range(3)]
        hi = [max(z["hi"][i] for z in zones) for i in range(3)]
        r = SC.radius_for(lo, hi)
        boxes = SC._snap_boxes(SC.boxes_for(catalog.BY_NAME[n].family, zones, lo, hi), 2 * r)
        least = SC.tris_of(SC.cage(boxes, SC.EDGES_ONLY, r), min(SC.SIDES[0]))    # >= 96: one box, square tubes
        assert least >= 96
        assert SC.budget(tuple(_man(n)["nonfractured"]["size"]), t0, fr["budget"][0]) < least, n


@pytest.mark.build
@pytest.mark.parametrize("name", NAMES)
def test_every_cut_block_has_scaffold(name):
    """Each caged block's FR LOD0 has one ungrouped BrushedMetal mesh part with the Scaffold / AlwaysVisible /
    Scaffolding props, its share of the FR LOD0 (without it) in [MIN_SHARE, MAX_SHARE] (the budget allows the floor
    on every caged block); the unfractured blocks and NO_ROOM have none."""
    meshes = _scaffold_meshes(_fr_fbx(name))
    if name not in CAGED:
        assert not meshes, name
        assert "BrushedMetal" not in _man(name)["fractured"]["parts"] or name in UNCUT, name
        return
    assert len(meshes) == 1, name
    m = meshes[0]
    assert "Group" not in m["props"] and m["materials"] == [SC.MATERIAL], (name, m["props"], m["materials"])
    assert tuple(m["props"][k] for k in ("ConstructionMeshType", "ConstructionMeshVisibility",
                                         "ConstructionMeshPreset")) == SC.PROPS
    fr = _man(name)["fractured"]
    assert fr["parts"][SC.PART] == list(SC.PROPS)
    s = _tris(meshes)
    assert s == fr["scaffold"]["tris"]["0"], name
    base = fr["lods"][0]["tris"] - s
    assert SC.MIN_SHARE * base <= s <= SC.MAX_SHARE * base, (name, s, base, s / base)


@pytest.mark.build
@pytest.mark.parametrize("name", CUT)
def test_scaffold_keeps_lod_count(name):
    """With its scaffold, the FR keeps Keen's LOD count for its own LOD0 and stays within budget[0];
    each LOD's cage is within the plan's per-LOD triangles (LOD1 only within 90 % of its budget)."""
    from se2model import limits
    m = _man(name)
    fr = m["fractured"]
    t0 = fr["lods"][0]["tris"]
    assert limits.optimal_lods(tuple(fr["size"]), t0)[0] == len(fr["lods"]), name      # the FR's own size, cage in
    assert t0 <= fr["budget"][0], (name, t0, fr["budget"][0])
    sc = fr.get("scaffold") or {"tris": {}}
    for i, lod in enumerate(fr["lods"][:-1]):
        got = _tris(_scaffold_meshes(_fr_fbx(name, i)))
        assert got == sc["tris"].get(str(i), 0), (name, i, got)
        assert lod["tris"] <= fr["budget"][i], (name, i)
    if "1" in sc["tris"]:
        assert fr["lods"][1]["tris"] <= SC.LOD1_FILL * fr["budget"][1], name


@pytest.mark.build
@pytest.mark.parametrize("name", CUT)
def test_dm_is_fr_minus_scaffold(name):
    """Vanilla: the scaffold is the only FR / DM mesh-part difference. At every LOD the Damaged mesh parts are the
    Fractured ones minus the scaffold's, and the Damaged collision is the Fractured one."""
    m = _man(name)
    for i in range(len(m["fractured"]["lods"])):
        fr = FRR.mesh_parts(FRR.fbx_meshes(_fr_fbx(name, i)))
        dm = FRR.mesh_parts(FRR.fbx_meshes(_fr_fbx(name, i, "Damaged")))
        cage = {SC.PART} if _scaffold_meshes(_fr_fbx(name, i)) else set()
        assert dm == fr - cage, (name, i, sorted(fr ^ dm))
    d = os.path.join(config.MODELS_DIR, name)
    assert FRR.gltf_hulls(os.path.join(d, "Damaged", m["damaged"]["collision"]["file"])) == \
        FRR.gltf_hulls(os.path.join(d, "Fractured", m["fractured"]["collision"]["file"]))


@pytest.mark.build
@pytest.mark.parametrize("name", CAGED)
def test_scaffold_never_visible_from_30_or_damaged_finished(name):
    """Below 30 % the cage shows in BrushedMetal_Scaffold; from 30 % (and on a finished block
    ground back and welded again past 30 %) it is hidden; a finished block that is shot shows FR with only the
    damaged-only hide, which hides the cage."""
    st = SV.installed_stages(name)
    for shot, r in SV.SHOTS.items():
        s = SV.part_state(st, r)
        if r < 0.3:
            assert s.get(SC.PART, (True, None)) == (True, SCAFFOLD_MAT), (name, shot, s.get(SC.PART))
        else:
            assert s.get(SC.PART, (False, None))[0] is False, (name, shot)
    assert SV.part_state(st, 1.0, damaged=True) == {SC.PART: (False, None)}, name
    assert SV.last_stage_changes(st) == [{"MeshPart": SC.PART, "ShowPart": False, "SetMaterial": None,
                                          "ResetToSkinMaterial": False, "ApplyOnlyWhenDamaged": True}], name


@pytest.mark.build
@pytest.mark.parametrize("name", CAGED)
def test_scaffold_inside_cells(name):
    """Every scaffold vertex lies within the block's cell box + OUTSET (+-0.5 mm), at every LOD that carries it; and
    where the block's skin fills its cell (within 2 mm of the cell face) the cage stands proud of it (>= 3.5 mm past
    the cell face: visible, as vanilla's), so it does not hide behind the skin."""
    spec = catalog.BY_NAME[name]
    half = [0.125 * spec.cells[i] for i in (0, 2, 1)]       # game cells (x, up, depth) -> Blender (x, y, z)
    for i in range(len(_man(name)["fractured"]["lods"]) - 1):
        for m in _scaffold_meshes(_fr_fbx(name, i)):
            for v in m["verts"]:
                assert all(abs(v[k]) <= half[k] + SC.OUTSET + 5e-4 for k in range(3)), (name, i, v, half)
    meshes = FRR.fbx_meshes(_fr_fbx(name))
    skin = [v for m in meshes.values() if m["props"].get("ConstructionMeshType") != "Scaffold" for v in m["verts"]]
    cage = [v for m in _scaffold_meshes(_fr_fbx(name)) for v in m["verts"]]
    from se2model import limits
    fr = _man(name)["fractured"]
    proud = set(fr["scaffold"]["proud"])
    for k in range(3):
        filled = [sgn for sgn in (-1, 1) if max(sgn * v[k] for v in skin) >= half[k] - SC.FILLS]
        if k not in proud:
            # only where standing proud on this axis too would move the FR across a row of Keen's LOD table
            if filled:
                lo = min([v[k] for v in skin + cage] + ([-half[k] - SC.OUTSET] if -1 in filled else []))
                hi = max([v[k] for v in skin + cage] + ([half[k] + SC.OUTSET] if 1 in filled else []))
                grown = [hi - lo if i == k else x for i, x in enumerate(fr["size"])]
                assert limits.optimal_lods(grown, fr["lods"][0]["tris"])[0] != len(fr["lods"]), (name, "xyz"[k])
            continue
        for sgn in filled:
            assert max(sgn * v[k] for v in cage) >= half[k] + 0.0035, (name, "xyz"[k], sgn)


# ---------------------------------------------------------------------------------------------- determinism
def _export(blocks, out):
    """A windowed Blender export of `blocks` into out/Models (and out/build_report.json): never the repo's."""
    os.makedirs(os.path.join(out, "Models"), exist_ok=True)
    shutil.copy(config.REPORT_PATH, os.path.join(out, "build_report.json"))
    env = dict(os.environ, DC_MODELS_DIR=os.path.join(out, "Models"),
               DC_REPORT_PATH=os.path.join(out, "build_report.json"))
    r = subprocess.run(["blender", "--python", os.path.join(config.HERE, "build_dc.py"), "--", *blocks,
                        "--no-render", "--export"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, timeout=900)
    assert "DC BUILD DONE" in r.stdout, r.stdout[-3000:]
    return os.path.join(out, "Models")


def test_export_is_deterministic():
    """(Opt-in: DC_BLENDER_EXPORT=1, a windowed Blender with the VRAGE add-on.) Two exports of one block give the
    same mesh data in every model (fracture_rules.fbx_content: objects, geometry arrays, connections) and the same
    export.json; Damaged models once dented differently per run (Blender's noise_vector
    draws a random offset per process). DC_Rack24_Open covers the cut-and-capped stand-ins."""
    if os.environ.get("DC_BLENDER_EXPORT") != "1":
        pytest.skip("opt-in: set DC_BLENDER_EXPORT=1 (windowed Blender) to export a block twice")
    blocks = ["DC_Tray_StraightS_Full", "DC_Srv_Timer", "DC_PDU_Cabinet", "DC_TrayRods_100",   # (+ a debris DM)
              "DC_Rack24_Open"]                                                              # (cut stand-ins)
    with tempfile.TemporaryDirectory(prefix="dc-det-") as t:
        a, b = _export(blocks, os.path.join(t, "a")), _export(blocks, os.path.join(t, "b"))
        for n in blocks:
            files = sorted(os.path.relpath(p, a) for p in glob.glob(os.path.join(a, n, "**", "*.fbx"), recursive=True))
            assert files and any("Damaged" in f for f in files), n
            for f in files:
                assert FRR.fbx_same_content(os.path.join(a, f), os.path.join(b, f)), f
            assert json.load(open(os.path.join(a, n, "export.json"))) == json.load(open(os.path.join(b, n,
                                                                                               "export.json"))), n


DOORS = [n for n in NAMES if catalog.BY_NAME[n].family == "contain_door"]


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_door_cage_leaves_opening_clear(name):
    """A containment door's cage follows its posts and lintel (scaffold.HULL_BOXES, the
    zone hulls' boxes), as vanilla SlidingDoorNarrow250's U-shaped cage: no scaffold vertex (FR LOD0 and LOD1) lies in
    the door opening (between the two post towers' inner faces, below the lintel), and the cage still reaches the
    posts' outer faces and the lintel's top."""
    man = _man(name)
    fr = man["fractured"]
    zones = fr["zones"]
    xl = max(z["hi"][0] for z in zones if z["hi"][0] < 0)          # the -x towers' inner face
    xr = min(z["lo"][0] for z in zones if z["lo"][0] > 0)          # the +x towers'
    lintel = [z for z in zones if z["critical"] and z["lo"][0] < 0 < z["hi"][0]]
    assert len(lintel) == 1, (name, [z["id"] for z in lintel])
    ztop = lintel[0]["lo"][2]
    for lod in (0, 1):
        meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "Fractured", fr["lods"][lod]["file"]))
        cage = [m for m in meshes.values() if m["props"].get("ConstructionMeshType") == "Scaffold"]
        assert cage, (name, lod)
        vs = [v for m in cage for v in m["verts"]]
        inside = [v for v in vs if xl + 0.001 < v[0] < xr - 0.001 and v[2] < ztop - 0.001]
        assert not inside, (name, lod, len(inside), inside[:3])
        assert min(v[0] for v in vs) <= min(z["lo"][0] for z in zones) + 0.002, (name, lod)
        assert max(v[0] for v in vs) >= max(z["hi"][0] for z in zones) - 0.002, (name, lod)
        assert max(v[2] for v in vs) > lintel[0]["hi"][2] - 0.001, (name, lod)
