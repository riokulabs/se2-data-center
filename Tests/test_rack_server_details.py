"""The geometry contracts of the rack and server detail work.

- Half-rack roof: only the 5 mm render-only plate may reach into the top slot's cells; the deep roof parts (28 mm
  rails over the side columns, front / rear headers) stay outside the slot footprint and in front of / behind the
  servers' hardware zone (<= 6 cm past the slot planes) and behind the door leaves.
- Every server type carries its own lid ID (unique, stencillable glyphs); the switch's patch cables and the compute
  fan wall stay in the 6 cm front zone (max_y) and inside the slot sides; LOD0/LOD1 keep the material cap.
"""
import json
import os

import pytest

from dc import catalog, config, dims as DM, rack, server

SERVERS = [b.name for b in catalog.BLOCKS if b.family == "server"]
RACKS = [b.name for b in catalog.BLOCKS if b.family == "rack"]
GLYPHS = set("0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ/ ")


def _entry(name):
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"][name]


def test_roof_layout_constants():
    assert rack.ROOF_RAIL_X > DM.SLOT_HALF_W + 0.04          # clear of the 19" rails (0.25 .. 0.29)
    assert DM.SLOT_FRONT_Y + 0.06 < rack.ROOF_HEADER_Y < DM.DOOR_Y_BACK   # past the server hardware, before the leaves
    assert rack.ROOF_RAIL_T <= 0.25 - DM.HALF_ROOF_T                      # inside the column's top cell


@pytest.mark.build
@pytest.mark.parametrize("name", RACKS)
def test_top_slot_stays_free(name):
    """Measured on LOD0: nothing of the rack reaches more than the 5 mm roof plate into the top slot."""
    g = _entry(name)["geometry"]
    assert g["top_slot_intrusion"] <= DM.HALF_ROOF_T + 1e-6, g["top_slot_intrusion"]


def test_server_type_ids():
    variants = {b.variant for b in catalog.BLOCKS if b.family == "server"}
    assert variants <= set(server.TYPE_ID)
    ids = [server.TYPE_ID[v] for v in variants]
    assert len(set(ids)) == len(ids)
    assert all(set(i) <= GLYPHS for i in ids)


@pytest.mark.build
@pytest.mark.parametrize("name", SERVERS)
def test_server_front_zone_and_caps(name):
    e = _entry(name)
    c = e["clearance"]
    assert c["max_y"] <= DM.SLOT_FRONT_Y + 0.06 + 1e-6          # cables / fan wall / lid: the 6 cm front zone
    assert c["max_abs_x_in_slot"] <= DM.SIDE_LIMIT_X + 1e-6
    for lod in e["lods"]:
        assert lod["materials"] <= lod["max_materials"] and lod["tris"] <= lod["max_tris"]
    assert "AtlasFont_BarlowCondensed_CleanWhite" in e["lods"][0]["material_names"]   # the lid ID stencil


# ---------------------------------------------------------------------------------------------- rack side panels
from dc import clone, integration, rack_side  # noqa: E402
from test_rack_doors import _files, _staged, staged  # noqa: E402,F401  (the staged-package fixture)


@pytest.mark.build
@pytest.mark.parametrize("name", SERVERS + RACKS)
def test_no_bevel_hazards(name):
    """Bevel guard: no zero-length edge in any bevelled Part (clamp-overlap would flatten the whole part's bevels)."""
    e = _entry(name)
    assert "bevel_guard" in e, "rebuild (build_dc.py) to record the bevel guard"
    assert e["bevel_guard"] == {}, e["bevel_guard"]


@pytest.mark.build
@pytest.mark.parametrize("name", RACKS)
def test_side_model_within_limits_and_bounds(name):
    """The side panels are their own static subpart model: inside its own LOD caps, on the +x side, never past the
    render inset (XO) nor the front / back keep-out, between the plinth top and the block top."""
    m = _entry(name)["subparts"]["models"][rack_side.SIDE_SUB]
    for row in m["lods"]:
        assert row["tris"] <= row["max_tris"] and row["materials"] <= row["max_materials"], row
    (x0, y0, z0), (x1, y1, z1) = m["bounds_local"]
    H = 0.25 * catalog.BY_NAME[name].cells[1]
    assert x0 >= rack.SX + 0.15 and x1 <= rack.XO + 1e-6
    assert -rack.YK - 1e-6 <= y0 and y1 <= rack.YK + 1e-6
    assert z0 >= -H / 2 + 0.25 - 1e-6 and z1 <= H / 2 + 1e-6


@pytest.mark.parametrize("name", RACKS)
def test_side_panels_spawn_on_both_sides(staged, name):  # noqa: F811 (pytest fixture)
    """Every rack's side model spawns twice from one ConditionalSubParts entry (it was a static
    child pair): RackSideR at the block origin, RackSideL turned 180 deg about game +Y (quaternion and Euler hint
    agree), both of the side's own dummy type, which maps to the side's client prefab."""
    info = clone.entry(catalog.BY_NAME[name])["info"]
    dm = {c["Value"]["Name"]: c["Value"]
          for c in _staged(info["model_def_file"])["$Value"]["Manipulator"]["Dummies"]["Changed"]}
    dt = _staged(_files(name, f"{rack_side.SIDE_SUB}_DummyTypeDefinition")[0])["$Value"]["Guid"]
    pf = _staged(_files(name, f"_{rack_side.SIDE_SUB}.partialdef")[0])["$Value"]["Manipulator"]["Guid"]
    cs = [_staged(f)["$Value"]["SubParts"] for f in _files(name, "ConditionalSubPartsDefinition")]
    assert len(cs) == 1 and cs[0][dt] == pf
    for child, yaw in integration.SIDE_CHILDREN:
        t = dm[child]["Transform"]
        assert dm[child]["Type"] == dt
        assert t["EulerHint"]["Y"] == yaw
        assert abs(t["Transform"]["Orientation"]["Y"]) == pytest.approx(1.0 if yaw == 180 else 0.0, abs=1e-6)

