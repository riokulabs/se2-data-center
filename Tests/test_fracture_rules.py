"""Plan 2 Task 9b fix round 1: Keen's two silent fracture rules on every EXPORTED fractured model (dc/fracture_rules.py).

I-1  ColliderMeshGroups / fracture groups (ModelProcessorLoader.CollectBreakableCollider): one ColliderMeshGroups entry
     naming no LOD0 group drops EVERY fracture of the model; a Fracture* collider needs a LOD0 group of its name.
I-2  Havok connectivity (RootConnectivityGraph): a breakable block's fracture colliders form ONE graph, joining
     colliders within BreakableColliderArgs.MaxEdgeDistance (0.1 m), or the build fails.
Both on the Fractured and the Damaged model of every block (racks, servers, trays; since the Plan 3 merge the room's
staged floors, roofs and doors), LOD0 FBX + collision glTF.
(Task 9c: test_fracture_refine.py checks the colliders' real convex shapes, the box gap here is their bounding boxes.)
"""
import os
from collections import Counter

import pytest

from dc import catalog, config
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import read_json


def _models():
    out = []
    for b in catalog.STAGED:
        p = os.path.join(config.MODELS_DIR, b.name, "export.json")
        if not os.path.exists(p):
            continue
        m = read_json(p)
        for key, sub in (("fractured", "Fractured"), ("damaged", "Damaged")):
            if key in m:
                d = os.path.join(config.MODELS_DIR, b.name, sub)
                out.append((b.name, key, os.path.join(d, m[key]["lods"][0]["file"]),
                            os.path.join(d, m[key]["collision"]["file"]), len(m["fractured"]["zones"])))
    return out


N_BLOCKS = 69   # after Plan 3 T6 + T7 + T8 (the per-family split is test_fracture_refine's ROOM_EXPECT)
MODELS = _models()
FRACTURED = [m for m in MODELS if m[4] >= 2]


def test_every_breakable_block_covered():
    """Every breakable pipeline block (racks / servers / trays) and every staged room block, each a Fractured and
    (Task 9c: the racks too; the Plan 3 merge: the floors and roofs) a Damaged model: 2 x N_BLOCKS models."""
    blocks = {m[0] for m in FRACTURED}
    fam = Counter(catalog.BY_NAME[n].family for n in blocks)
    room = Counter({f: c for f, c in fam.items() if f in catalog.STAGED_ROOM_FAMILIES})
    # per family, derived from the catalogue: every staged room block, every pipeline block but the non-breakable ones
    assert room == Counter(b.family for b in catalog.STAGED if b.family in catalog.STAGED_ROOM_FAMILIES), dict(room)
    assert sum((fam - room).values()) == sum(1 for b in catalog.BLOCKS if b.family not in catalog.ROOM_FAMILIES
                                              and not FR.unfractured_reason(b)), dict(fam)
    assert len(FRACTURED) == 2 * len(blocks), (len(blocks), len(FRACTURED))
    assert (len(blocks), len(FRACTURED)) == (N_BLOCKS, 2 * N_BLOCKS)


@pytest.mark.parametrize("name,kind,fbx,gltf,zones", FRACTURED, ids=lambda v: v if isinstance(v, str) and
                         not v.endswith((".fbx", ".gltf")) else "")
def test_collider_mesh_groups_name_existing_groups(name, kind, fbx, gltf, zones):
    """I-1: every ColliderMeshGroups entry names a LOD0 group, every Fracture* collider has its group (carrying
    ColliderMeshGroups) and every fracture group its collider; the colliders are the export's zones."""
    props = FRR.fbx_model_props(fbx)
    cols = FRR.fracture_colliders(gltf)
    assert len(cols) == zones, (name, kind, sorted(cols))
    assert any(p.get("ColliderMeshGroups") for p in props.values()), (name, kind)
    assert FRR.collider_mesh_group_problems(props, set(cols)) == [], (name, kind)


@pytest.mark.parametrize("name,kind,fbx,gltf,zones", FRACTURED, ids=lambda v: v if isinstance(v, str) and
                         not v.endswith((".fbx", ".gltf")) else "")
def test_fracture_colliders_connected(name, kind, fbx, gltf, zones):
    """I-2: the fracture colliders form one connected graph at Havok's 0.1 m."""
    assert FRR.connectivity_problems(FRR.fracture_colliders(gltf)) == [], (name, kind)


def test_exceptions_have_no_fracture_colliders():
    """The 4 non-breakable blocks (fracture.UNFRACTURED) export plain colliders only: nothing for either rule, in
    their Fractured model and (Plan 5 Task 7) their dented Damaged debris."""
    from dc import fracture as FR
    ex = [m for m in MODELS if FR.unfractured_reason(catalog.BY_NAME[m[0]])]
    names = ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200", "DC_Tray_Chute"]
    assert sorted((m[0], m[1]) for m in ex) == [(n, k) for n in names for k in ("damaged", "fractured")]
    for name, kind, fbx, gltf, zones in ex:
        assert zones == 0 and FRR.fracture_colliders(gltf) == {}, (name, kind)


# ---------------------------------------------------------------------------------------------- the rules themselves
def test_rule_collider_mesh_groups():
    ok = {"a": {"Group": "Fracture_01", "ColliderMeshGroups": "Fracture_01|Fracture_01_Hide"},
          "b": {"Group": "Fracture_01_Hide"}, "c": {"Group": "Fracture_02", "ColliderMeshGroups": "Fracture_02"}}
    assert FRR.collider_mesh_group_problems(ok, {"Fracture_01", "Fracture_02"}) == []
    bad = dict(ok, b={"Group": "Fracture_01_Hidden"})                       # a listed group that is missing
    assert any("Fracture_01_Hide" in p for p in FRR.collider_mesh_group_problems(bad, {"Fracture_01", "Fracture_02"}))
    assert FRR.collider_mesh_group_problems(ok, {"Fracture_01", "Fracture_02", "Fracture_03"})   # collider, no group
    assert FRR.collider_mesh_group_problems(ok, {"Fracture_01"})                               # group, no collider


def test_rule_connectivity():
    a, b = ((0, 0, 0), (1, 1, 1)), ((1.05, 0, 0), (2, 1, 1))
    far = ((1.2, 0, 0), (2, 1, 1))
    assert FRR.box_gap(a, b) == pytest.approx(0.05) and FRR.box_gap(a, a) == 0
    assert FRR.connectivity_problems({"F1": a, "F2": b}) == []
    assert FRR.connectivity_problems({"F1": a, "F2": far})                    # no connection at all
    assert FRR.connectivity_problems({"F1": a, "F2": b, "F3": ((5, 5, 5), (6, 6, 6))})   # an isolated node
    assert len(FRR.connectivity_components({"F1": a, "F2": b, "F3": ((5, 5, 5), (6, 6, 6)),
                                            "F4": ((6.05, 5, 5), (7, 6, 6))})) == 2      # two components
