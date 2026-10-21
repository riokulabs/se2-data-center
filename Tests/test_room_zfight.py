"""Nothing in a ROOM block fights for the same pixels, and its stencils read on any paint.

The in-game lessons (2026-10-18, commit 4f7288a5): decal elements overlapping in-plane at the same depth,
decals coplanar with or buried under mesh faces, and a sliding / hinged leaf coplanar with its frame all flicker in
game; white stencils straight on a light paint read poorly. dc/zfight.py (Tests/test_zfight.py covers the racks
and servers) audits every built block; dc/zfight_room.py adds the
containment door's sliding leaves (closed and open) and the stencil backing check. build_dc.py records both in
build_report.json "zfight"; these tests re-check the room blocks from it.
"""
import json
import os
import re

import pytest

from dc import catalog, config, contain
from dc import zfight as Z

HERE = os.path.dirname(os.path.abspath(__file__))
DC_SRC = os.path.join(HERE, "..", "Source", "Model", "dc")
ROOM = [b.name for b in catalog.ROOM]
DOORS = [b.name for b in catalog.ROOM if b.family == "contain_door"]
ROOM_MODULES = ("floor.py", "contain.py", "crac.py", "crac_ports.py", "pdu.py", "signs.py")


def _zf(name):
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        e = json.load(f)["blocks"].get(name, {})
    if not e.get("placement", {}).get("total"):
        pytest.skip(f"{name} not built")
    assert "zfight" in e, f"{name}: no zfight audit in build_report.json (rebuild with build_dc.py)"
    return e["zfight"]


def test_no_rectangle_hazard_triangles_in_room_modules():
    """Stickers02's warning triangles drawn as atlas rectangles catch their neighbours' corners: the room builders use
    style.hazard_triangle (an exact triangle) if they draw one at all."""
    hits = []
    for f in ROOM_MODULES:
        src = open(os.path.join(DC_SRC, f)).read()
        hits += [f"{f}: {m}" for m in re.findall(r"element\([^)]*\"tri_(?:electric|hot)\"", src)]
    assert not hits, hits


def test_stencil_backing_rule():
    """The contrast rule's materials: paint is the player's colour (light by default), so it never backs a stencil."""
    from dc import zfight_room as ZR
    assert ZR.PAINT_MATS == ("PaintedMetalColorable",) and ZR.BACK_D <= 0.02


@pytest.mark.build
@pytest.mark.parametrize("name", ROOM)
def test_room_decal_elements_do_not_fight(name):
    """No two decal elements of a model (every LOD, subparts included) overlap or crowd within 1 mm in-plane at depths
    closer than 0.5 mm."""
    assert Z.decal_conflicts(_zf(name)["elements"]) == []


@pytest.mark.build
@pytest.mark.parametrize("name", ROOM)
def test_room_decals_clear_of_coplanar_geometry(name):
    """No decal quad lies in the plane of (within 0.3 mm), or up to 15 mm under, a same-facing mesh face it overlaps."""
    assert _zf(name)["decal_geometry"] == []


@pytest.mark.build
@pytest.mark.parametrize("name", ROOM)
def test_room_stencils_on_dark_backing(name):
    """Every white stencil glyph stands on a non-paint plate (Darker, Yellow, ...): the face right behind it."""
    assert _zf(name)["stencil_backing"] == []


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_contain_door_leaves_have_no_coplanar_faces(name):
    """The sliding leaves: no two parts of a leaf model share a face plane where they overlap (every LOD), and neither
    leaf, closed or open, shares one with the door frame; the closed leaves' meeting stiles neither."""
    zf = _zf(name)
    assert zf["contain_leaf_coplanar"] == []
    assert zf["contain_leaf_frame"] == []
    assert zf["contain_leaf_leaf"] == []


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_contain_door_leaf_audit_poses(name):
    """The audit placed the leaves where the game does (contain.leaf_boxes, closed and open): their mesh bounds hug the
    collision boxes along the slide (x) and up (z), so the frame check above ran on the real poses."""
    zf = _zf(name)
    spec = catalog.BY_NAME[name]
    for pose, f in (("closed", 0.0), ("open", 1.0)):
        for model, (lo, hi) in contain.leaf_boxes(spec, f).items():
            blo, bhi = zf["contain_leaf_bounds"][f"{model}_{pose}"]
            assert blo[0] == pytest.approx(lo[0], abs=0.005) and bhi[0] == pytest.approx(hi[0], abs=0.005)
            assert blo[2] == pytest.approx(lo[2], abs=0.01) and bhi[2] >= hi[2] - 0.01


def test_contain_tag_lift_is_the_default():
    """The CONTAINMENT tag's 0.6 mm lift is _contain_rail's DEFAULT, so the
    racks get it too (test_zfight audits them); the CRAC and the PDU cabinet use the same value."""
    import inspect

    from dc import crac, pdu, rack
    assert rack.CONTAIN_TAG_LIFT == pytest.approx(0.0006)
    assert inspect.signature(rack._contain_rail).parameters["tag_lift"].default == rack.CONTAIN_TAG_LIFT
    assert crac.TAG_LIFT == pdu.TAG_LIFT == rack.CONTAIN_TAG_LIFT
    assert rack.CONTAIN_TAG_LIFT > Z.GEOM_EPS_D


@pytest.mark.build
@pytest.mark.parametrize("name", [b.name for b in catalog.BLOCKS if b.family == "rack"])
def test_rack_contain_tag_clear(name):
    """The racks' CONTAINMENT tag stencil is not coplanar with its plate (decal_geometry has no CONTAINMENT row)."""
    zf = _zf(name)
    assert not [r for r in zf["decal_geometry"] if "CONTAINMENT" in str(r)], name
