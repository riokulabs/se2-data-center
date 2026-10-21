"""Plan 2 Task 9c: the fracture refinement pass against docs/guides/vanilla-fracture-models.md, checked offline on the
EXPORTED files of every breakable block (6 racks, 10 servers, 34 trays; since the Plan 3 merge also the room's staged
4 raised floors, 3 containment roofs and 3 containment doors), Fractured AND Damaged (dc/fracture_rules.py).

T1   recognition (guide 1 / 9.1 B4-B9): every collider is a fracture because its name equals a LOD0 Group, fractures
     and plain colliders never mix, 2 .. 16 of them and no more than Keen's table allows for the model's size, every
     ColliderMeshGroups entry names a LOD0 group; on the colliders' real convex shapes, one connected graph at 0.1 m.
T5   the Damaged model (guide 2): every breakable block has its OWN Deformed model (a separate .model, never the
     FractureModel), whose LOD0 carries exactly the Fractured LOD0's Fracture_NN-Material mesh parts (the renderer
     shows the damaged zones' parts BY NAME, BlockModelRenderer.cs:277-297), at most ~2 x its triangles.
T8   break faces at vanilla's texel density (guide 3): FracturedMaterial01 at 0.40 +- 0.04 UV/m.
Hull every zone collider is shaped to its solid (guide 4 / 10.3 (5)): health is the collider's volume share, so no
     zone may buy it with empty space: >= HULL_FILL of each collider lies within its zone geometry's extent.
"""
import os
from collections import Counter

import pytest

from dc import catalog, clone, config
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import body, read_json

HULL_FILL = 0.85       # (T9b's boxes: a Drop waterfall 0.22, a TurnH half 0.68, a Cross arm 0.80)
UV_DENSITY = (0.36, 0.44)


def _manifest(n):
    p = os.path.join(config.MODELS_DIR, n, "export.json")
    return read_json(p) if os.path.exists(p) else None


BREAKABLE = [b.name for b in catalog.STAGED if len((_manifest(b.name) or {}).get("fractured", {}).get("zones", [])) >= 2]
# the breakable blocks per family, pinned (one line per family: a task adding a family adds its own line, so parallel
# branches merge without re-summing literals); the pipeline count is derived from the catalogue
PIPELINE_EXPECT = {"rack": 6, "server": 10, "tray": 34}   # of 54 pipeline blocks, 4 stay whole (FR.UNFRACTURED)
ROOM_EXPECT = {
    "floor": 4,
    "contain_roof": 3,
    "contain_door": 3,
    "crac": 1,            # Plan 3 Task 6
    "pdu_cabinet": 1,     # Plan 3 Task 7
    "pdu_strip": 4,       # Plan 3 Task 7
    "sign": 3,            # Plan 3 Task 8
}
N_PIPELINE = sum(1 for b in catalog.BLOCKS if b.family not in catalog.ROOM_FAMILIES and not FR.unfractured_reason(b))
N_BLOCKS = 69             # after Plan 3 T6 + T7 + T8


def _files(name, key):
    m = _manifest(name)
    sub = {"fractured": "Fractured", "damaged": "Damaged"}[key]
    d = os.path.join(config.MODELS_DIR, name, sub)
    return os.path.join(d, m[key]["lods"][0]["file"]), os.path.join(d, m[key]["collision"]["file"])


MODELS = [(n, k) for n in BREAKABLE for k in ("fractured", "damaged")]


def _id(v):
    return v if isinstance(v, str) else None


def test_every_breakable_block_is_covered():
    """Every breakable pipeline block (the non-breakable exceptions aside) and every staged room block, each with a
    Fractured and a Damaged model, counted per family."""
    fam = Counter(catalog.BY_NAME[n].family for n in BREAKABLE)
    room = Counter({f: c for f, c in fam.items() if f in catalog.STAGED_ROOM_FAMILIES})
    assert dict(room) == ROOM_EXPECT, dict(room)
    assert dict(fam - room) == PIPELINE_EXPECT, dict(fam - room)
    # every staged room block of the catalogue is breakable
    assert ROOM_EXPECT == dict(Counter(b.family for b in catalog.STAGED if b.family in catalog.STAGED_ROOM_FAMILIES))
    assert sum(PIPELINE_EXPECT.values()) == N_PIPELINE
    assert len(BREAKABLE) == N_PIPELINE + sum(ROOM_EXPECT.values()) == N_BLOCKS, len(BREAKABLE)


# ---------------------------------------------------------------------------------------------------- T1
@pytest.mark.parametrize("name,kind", MODELS, ids=lambda v: _id(v))
def test_fractures_recognised(name, kind):
    """T1: the importer recognises every zone (collider name = Group, no mixing, 2 .. 16 and within Keen's size
    table, ColliderMeshGroups consistent), and the zone colliders' convex shapes connect at Havok's 0.1 m."""
    fbx, gltf = _files(name, kind)
    props = FRR.fbx_model_props(fbx)
    hulls = FRR.gltf_hulls(gltf)
    m = _manifest(name)
    assert FRR.recognition_problems(props, list(hulls), m[kind]["size"]) == [], (name, kind)
    assert sorted(hulls) == sorted(z["id"] for z in m["fractured"]["zones"]), (name, kind)
    assert FRR.hull_connectivity_problems(hulls) == [], (name, kind)


def test_recognition_rule_bites():
    ok = {"a": {"Group": "Fracture_01", "ColliderMeshGroups": "Fracture_01"},
          "b": {"Group": "Fracture_02", "ColliderMeshGroups": "Fracture_02"}}
    assert FRR.recognition_problems(ok, ["Fracture_01", "Fracture_02", "mountpoints_x"]) == []
    assert FRR.recognition_problems(ok, ["Fracture_01", "Fracture_02", "frame"])               # B9: mixed
    assert FRR.recognition_problems(ok, ["Fracture_01", "Fracture_2"])                         # B4: name != Group
    assert FRR.recognition_problems({"a": ok["a"]}, ["Fracture_01"])                            # B7: one zone
    many = {f"m{i}": {"Group": f"F{i}", "ColliderMeshGroups": f"F{i}"} for i in range(17)}
    assert FRR.recognition_problems(many, [f"F{i}" for i in range(17)])                       # B8: > 16
    assert FRR.recognition_problems(ok, ["Fracture_01", "Fracture_02"], (0.25, 0.1, 0.1))      # B13: 2 > 1 at 25 cm


def test_hull_gap_is_convex_distance():
    box = lambda lo, hi: [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]  # noqa
    assert FRR.hull_gap(box((0, 0, 0), (1, 1, 1)), box((1.05, 0, 0), (2, 1, 1))) == pytest.approx(0.05)
    assert FRR.hull_gap(box((0, 0, 0), (1, 1, 1)), box((0.5, 0.5, 0.5), (2, 2, 2))) == 0.0
    tet = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    assert FRR.hull_gap(tet, [(x + 1, y + 1, z + 1) for x, y, z in tet]) == pytest.approx(3 ** 0.5 - 3 ** -0.5)
    # two wedges whose BOXES overlap but whose shapes lie 0.14 m apart: the box test would join them
    a = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1)]
    b = [(1, 1, 0), (0.2, 1, 0), (1, 0.2, 0), (1, 1, 1), (0.2, 1, 1), (1, 0.2, 1)]
    bb = lambda P: (tuple(min(p[i] for p in P) for i in range(3)), tuple(max(p[i] for p in P) for i in range(3)))  # noqa
    assert FRR.box_gap(bb(a), bb(b)) == 0.0
    assert FRR.hull_gap(a, b) == pytest.approx(0.2 / 2 ** 0.5)
    assert FRR.hull_connectivity_problems({"a": a, "b": b})


# ---------------------------------------------------------------------------------------------------- T5
@pytest.mark.parametrize("name", BREAKABLE)
def test_own_damaged_model(name):
    """T5: a separate Damaged model with the Fractured LOD0's exact Fracture_NN-Material mesh-part set, its zone
    colliders, and at most damaged_tris_x(family) (+ 2 % for the densify step's granularity) x the Fractured
    triangles without the scaffold (Plan 5 Task 7, R7: the per-family ratio; exact bound in test_damaged_geometry).
    Plan 5 Task 6 (R7): the Fractured model also carries the ungrouped construction scaffold (BrushedMetal), which
    vanilla leaves out of the Deformed model (the one FR / DM mesh-part difference, guide §2.4): the parts compare
    without it."""
    from dc import scaffold as SC
    m = _manifest(name)
    assert "damaged" in m, name
    fr = FRR.mesh_parts(FRR.fbx_meshes(_files(name, "fractured")[0]))
    dm = FRR.mesh_parts(FRR.fbx_meshes(_files(name, "damaged")[0]))
    assert fr - dm <= {SC.PART} and (SC.PART in fr - dm) == bool(m["fractured"].get("scaffold")), (name, sorted(fr ^ dm))
    assert dm <= fr, (name, sorted(dm - fr))
    assert {p.split("-")[0] for p in fr if p.startswith("Fracture_")} >= {z["id"] for z in m["fractured"]["zones"]}
    assert sorted(FRR.gltf_hulls(_files(name, "damaged")[1])) == sorted(FRR.gltf_hulls(_files(name, "fractured")[1]))
    sc = (m["fractured"].get("scaffold") or {}).get("tris") or {}
    for i, (a, b) in enumerate(zip(m["fractured"]["lods"], m["damaged"]["lods"])):
        base = a["tris"] - sc.get(str(i), 0)
        assert b["tris"] <= FR.damaged_tris_x(catalog.BY_NAME[name].family) * base * 1.02 + 16, (name, base, b["tris"])


@pytest.fixture(scope="module")
def staged():
    from dc import integration
    integration.write_all()
    return config.STAGE_ASSETS


def test_damaged_model_is_its_own_asset(staged):
    """T5: every breakable block's BlockModelDefinition points DamagedModel at its own Damaged .model, never at
    the FractureModel (the racks did until Task 9c: damage was invisible until a zone died)."""
    from dc import integration
    for n in BREAKABLE:
        rel = clone.entry(catalog.BY_NAME[n])["info"]["model_def_file"]
        p = os.path.join(staged, rel)
        bmd = body(read_json(p if os.path.exists(p) else os.path.join(config.MOD_ASSETS, rel)))
        dmg = "{G}" + integration.asset_id(f"{config.NAME}/{n}/Models/Damaged/{n}_Damaged.model")
        assert bmd["DamagedModel"] == dmg and bmd["DamagedModel"] != bmd["FractureModel"], n


# ---------------------------------------------------------------------------------------------------- T8
@pytest.mark.parametrize("name", BREAKABLE)
def test_cut_uv_density(name):
    """T8: the break faces tile at vanilla's 0.40 UV/m (FracturedMaterial01, the painted metals' density)."""
    d = FRR.cut_uv_density(FRR.fbx_meshes(_files(name, "fractured")[0]))
    if d is None:      # a light empty basket whose cut 6 mm wire ends stay open (test_fracture_plan)
        assert "no wire-end caps" in _manifest(name)["fractured"]["cut_mode"], name
        return
    assert UV_DENSITY[0] <= d <= UV_DENSITY[1], (name, d)


# ---------------------------------------------------------------------------------------------------- hulls
@pytest.mark.parametrize("name", BREAKABLE)
def test_hulls_follow_the_solid(name):
    """Guide 10.3 (5): each zone's collider lies (>= HULL_FILL of its volume) within its zone's own geometry
    extent: no box over mostly empty space buying health; and the export's health shares are Keen's (volume, x 2
    for a critical zone) and sum to 1."""
    meshes = FRR.fbx_meshes(_files(name, "fractured")[0])
    hulls = FRR.gltf_hulls(_files(name, "fractured")[1])
    m = _manifest(name)
    for z in m["fractured"]["zones"]:
        fill = FRR.hull_fill(hulls[z["id"]], FRR.zone_geometry(meshes, z["id"]))
        assert fill >= HULL_FILL, (name, z["id"], round(fill, 3))
    share = FR.health_shares({z["id"]: z["volume"] for z in m["fractured"]["zones"]}, set(m["fractured"]["critical"]))
    assert share == pytest.approx({z["id"]: z["health_share"] for z in m["fractured"]["zones"]}, abs=2e-4)
    assert sum(share.values()) == pytest.approx(1.0, abs=1e-3)


def test_hull_fill_bites():
    """A box collider over an L of geometry (a bend's inner corner left empty) fills far less than the L's own hull."""
    L = [(x, y, z) for x in (0, 1) for y in (0, 0.2) for z in (0, 0.1)] + \
        [(x, y, z) for x in (0, 0.2) for y in (0, 1) for z in (0, 0.1)]
    box = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 0.1)]
    tri = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0.2, 0), (0.2, 1, 0)]
    tri += [(x, y, 0.1) for x, y, _ in tri]
    assert FRR.hull_fill(box, L) < 0.8 < 0.95 < FRR.hull_fill(tri, L)      # (the L's own hull: 68 % of the box)


def test_shaped_hull_cuts_empty_corners():
    """fracture.shaped_hull: a box for a box; for a quarter ring, 45 degree planes cut the empty inner corner within
    the vertex budget; the polytope volume is exact."""
    import math
    b = [(x, y, z) for x in (0, 1) for y in (0, 2) for z in (0, 3)]
    h = FR.shaped_hull(b, (-5, -5, -5), (5, 5, 5), 30)
    assert len(h["verts"]) == 8 and h["volume"] == pytest.approx(6.0)
    ring = [(r * math.cos(t), r * math.sin(t), z) for r in (0.3, 0.5) for t in [i * math.pi / 40 for i in range(21)]
            for z in (0, 0.1)]
    h = FR.shaped_hull(ring, (-1, -1, -1), (1, 1, 1), 16)
    assert len(h["verts"]) <= 16 and h["volume"] < 0.8 * h["box_volume"]
    assert all(max(FR._dot(n, p) - d for n, d in h["planes"]) <= 1e-9 for p in ring)      # every point inside
    h = FR.shaped_hull(b, (-5, -5, -5), (0.5, 5, 5), 30)                                   # clipped to the cells
    assert h["volume"] == pytest.approx(3.0)
    h = FR.shaped_hull(b, (-5, -5, -5), (5, 5, 5), 30, halfspaces=[((0.5, 0, 0), FR._unit((-1, -1, 0)))])
    assert h["volume"] == pytest.approx(0.375)                                             # stops at its seam plane
