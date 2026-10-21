"""Task 4: server chassis + deco blades, asserted on build_report.json (run the Blender build first).

Sizes (controller ruling 2026-10-17, NOTES.md): 6U servers are 2x1x3 cells, the 12U UPS 2x2x3. A server's cell box
must equal one rack slot's cell box (rack.SLOT_CELLS) and sit on the slot origin, its collision fills its cells, and
the render model keeps the slot clearances (sides >= 2 mm inside the slot, top >= 5 mm below the cell top)."""
import json
import os

import pytest

from dc import catalog, config, dims as DM

pytestmark = pytest.mark.build

DECO = ("DC_Srv_Blank", "DC_Srv_Compute", "DC_Srv_Storage", "DC_Srv_Switch")
FUNCTIONAL = ("DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_Status")   # Task 6: same chassis, same checks
TASK8 = ("DC_Srv_KVM", "DC_Srv_Programmable")                         # Task 8: base models (KVM subparts: own tests)
SIX_U = DECO + FUNCTIONAL + TASK8
TWELVE_U = ("DC_Srv_UPS",)                                            # Task 7: same chassis, two slots tall
SERVERS = SIX_U + TWELVE_U
RACKS = ("DC_Rack42_Open", "DC_Rack24_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear",
         "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")   # Task 9: the door racks share the frame


def _entry(name):
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        blocks = json.load(f)["blocks"]
    assert name in blocks, f"{name} not in build_report.json"
    e = blocks[name]
    assert e["placement"]["total"] > 0, f"{name} has no placement data (stub builder?)"
    return e


@pytest.mark.parametrize("name", SERVERS)
def test_server_fills_cells(name):
    p = _entry(name)["placement"]
    nx, ny, nz = catalog.BY_NAME[name].cells
    assert p["total"] == nx * ny * nz
    assert p["occupied"] == p["total"], p["summary"]
    assert p["outside"] == 0, p["summary"]
    assert p["free_cells"] == []


@pytest.mark.parametrize("name", SERVERS)
def test_server_standalone_mountable(name):
    """Usable outside a rack: it sits on a floor, backs onto a wall, and takes neighbours left and right. (The UPS's
    back is its second cell bay, a working face: no wall behind it.)"""
    f = _entry(name)["placement"]["faces"]
    for d in ("Down", "Left", "Right") + (() if name in TWELVE_U else ("Backward",)):
        assert f[d]["groups"] >= 1, (d, f[d])
        assert f[d]["coverage"] >= 0.99, (d, f[d])


def _cell_box(cells, shift):
    """Metric box (collision-glTF frame, the frame placement uses) covered by inclusive game cells."""
    lo = [min(c[i] for c in cells) * 0.25 - shift[i] - 0.125 for i in range(3)]
    hi = [max(c[i] for c in cells) * 0.25 - shift[i] + 0.125 for i in range(3)]
    return lo, hi


@pytest.mark.parametrize("name", SERVERS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_server_cells_match_slot_cells(name, rack_name):
    """Bookkeeping: the server's cell box (catalog.bounds) shifted by whole cells in height is exactly each slot's
    rack.SLOT_CELLS, and with each model's own grid shift the metric x / depth boxes coincide. (The built geometry
    couplings are the test_rack_coupling_* tests below.)"""
    from se2model import placement as PL
    from dc import rack
    srv, rk = catalog.BY_NAME[name], catalog.BY_NAME[rack_name]
    (sx0, sy0, sz0), (sx1, sy1, sz1) = catalog.bounds(srv)
    own = {(x, y, z) for x in range(sx0, sx1 + 1) for y in range(sy0, sy1 + 1) for z in range(sz0, sz1 + 1)}
    slots = rack.SLOT_CELLS(rk)
    ys = sorted({c[1] for c in slots})
    n_u = srv.cells[1]
    for k in range(len(ys) - n_u + 1):
        want = {c for c in slots if ys[k] <= c[1] < ys[k] + n_u}
        moved = {(x, y + ys[k] - sy0, z) for x, y, z in own}
        assert moved == want, (k, sorted(moved ^ want)[:6])
    s_lo, s_hi = _cell_box(sorted(own), PL.shift_for_bounds(catalog.bounds(srv)))
    r_lo, r_hi = _cell_box([c for c in slots if c[1] < ys[0] + n_u], PL.shift_for_bounds(catalog.bounds(rk)))
    for i in (0, 2):
        assert s_lo[i] == pytest.approx(r_lo[i]) and s_hi[i] == pytest.approx(r_hi[i]), (i, s_lo, s_hi, r_lo, r_hi)
    assert s_hi[1] - s_lo[1] == pytest.approx(r_hi[1] - r_lo[1])


# ------------------------------------------------------------------- built-geometry couplings (measured meshes)
# build_report "geometry" is measured by build_dc.py on the built LOD0 meshes of both blocks (named interface
# parts: the rack's rail / holes / slide / slidebolt / ceiling, the server's ear / screw / slide), in each block's
# own frame; slot-relative z is measured from a slot floor. The server sits in a slot with its cell front on the
# slot front plane and its cell bottom on the slot floor (test_server_cells_match_slot_cells).
MM = 0.001


def _geo(name):
    g = _entry(name).get("geometry")
    assert g, f"{name}: no geometry in build_report.json (rebuild)"
    return g


@pytest.mark.parametrize("name", SERVERS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_rack_coupling_front_plane(name, rack_name):
    s, r = _geo(name), _geo(rack_name)
    assert s["cell_front_y"] == pytest.approx(r["slot_front_y"], abs=1e-6), (s, r)
    gap = s["ear_back_y"] - r["slot_front_y"]
    assert 0.0 <= gap <= MM, f"ear flange {gap * 1000:.2f} mm off the rail ear face"
    assert s["ear_max_x"] <= r["rail_outer_x"] + 1e-6, "ear overhangs the rail"


@pytest.mark.parametrize("name", SERVERS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_rack_coupling_slides(name, rack_name):
    s, r = _geo(name), _geo(rack_name)
    (s0, s1), (r0, r1) = s["slide_z"], r["slide_z"]
    assert abs((s0 + s1) / 2 - (r0 + r1) / 2) <= MM, (s["slide_z"], r["slide_z"])
    assert r0 - 1e-6 <= s0 and s1 <= r1 + 1e-6, "server slide outside the rack slide's height"
    assert s["slide_max_x"] < r["slide_plane_x"], "server slide touches the rack slide web"


@pytest.mark.parametrize("name", SERVERS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_rack_coupling_thumbscrews(name, rack_name):
    s, r = _geo(name), _geo(rack_name)
    assert abs(s["screw_x"] - r["hole_x"]) <= MM, (s["screw_x"], r["hole_x"])
    assert len(s["screw_offsets"]) >= 2
    for z in s["screw_offsets"]:
        assert min(abs(z - h) for h in r["hole_offsets"]) <= MM, (z, r["hole_offsets"])


@pytest.mark.parametrize("name", SERVERS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_rack_coupling_clearances(name, rack_name):
    """Side: inside the slot depth nothing comes within 1 mm of the rack's slide-bolt heads. Top: the server's top
    stays below whatever sits over the rack's top slot (the half rack's roof, the full rack's tray floor)."""
    s, r = _geo(name), _geo(rack_name)
    assert s["side_max_x"] <= r["slide_bolt_reach_x"] - MM, (s["side_max_x"], r["slide_bolt_reach_x"])
    assert -s["top_gap"] <= r["top_obstruction_z"] - MM, (s["top_gap"], r["top_obstruction_z"])


@pytest.mark.parametrize("name", SERVERS)
def test_server_clearance(name):
    """Render-only limits from dc/dims.py (the collision still fills the cells); the rack-measured versions are the
    test_rack_coupling_* tests."""
    c = _entry(name)["clearance"]
    h2 = DM.SLOT_H * catalog.BY_NAME[name].cells[1] / 2
    assert c["max_abs_x_in_slot"] <= DM.SIDE_LIMIT_X + 1e-6, c
    assert c["max_z"] <= h2 - DM.HALF_ROOF_T + 1e-6, c
    assert c["min_z"] >= -h2 - 1e-6, c
    assert c["min_y"] >= -DM.SLOT_HALF_D - 1e-6, c
    # the front-zone parts (ears, thumbscrews, handles) stay well inside the rack's 0.25 m front zone
    assert c["max_y"] <= DM.SLOT_FRONT_Y + 0.06, c
    assert c["max_abs_x"] <= DM.RAIL_X[1] + 1e-6, c   # the ears end on the 19" rail


@pytest.mark.parametrize("name", SERVERS)
def test_server_limits(name):
    from se2model import limits
    spec = catalog.BY_NAME[name]
    e = _entry(name)
    lods = e["lods"]
    n = limits.model_limits(tuple(e["model_size"]), lods[0]["tris"])["optimal_lods"]
    assert len(lods) == n, (len(lods), n)
    assert lods[-1]["tris"] == 12
    for i, l in enumerate(lods):
        assert l["tris"] <= l["max_tris"], (i, l)
        assert l["materials"] <= l["max_materials"], (i, l)
    assert e["colliders"]["regular"] <= e["colliders"]["max"]


@pytest.mark.parametrize("rack_name", RACKS)
def test_ups_spans_two_consecutive_slots(rack_name):
    """The 12U UPS fills two consecutive slots in both racks: its measured thumbscrews land on the rack's holes in
    BOTH slot bands (4 screws per side, one slot pitch apart), its slides sit at the rack slide height in both, and it
    fits every pair of consecutive slots (the top pair included: top clearance)."""
    from dc import rack
    s, r = _geo("DC_Srv_UPS"), _geo(rack_name)
    zs = s["screw_z_all"]
    assert len(zs) == 4, zs
    for z in zs:
        band, rel = divmod(z + 1e-9, DM.SLOT_H)
        assert band in (0, 1), z
        assert min(abs(rel - h) for h in r["hole_offsets"]) <= MM, (z, r["hole_offsets"])
    assert sorted({int((z + 1e-9) // DM.SLOT_H) for z in zs}) == [0, 1]
    n = rack.dims(catalog.BY_NAME[rack_name])["nslots"]
    assert n - 1 >= 1   # at least one pair of consecutive slots
    assert -s["top_gap"] <= r["top_obstruction_z"] - MM
