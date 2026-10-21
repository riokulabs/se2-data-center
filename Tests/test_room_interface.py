"""The room interface (dc/dims.py) and the rack changes it needs.

The room pieces (raised floor, containment roof and doors, PDU strips, rack labels) are built against these numbers
alone, so the build-marked tests check them on the MEASURED rack (build_report.json "geometry" and "placement"):
  * the containment rail band on the full racks' front and back tray band (the roof panels mount on it);
  * the freed rear PDU columns (the zero-U PDU strips' cells and their clear envelope) with the plinth receptacle;
  * the rack-top label pads (front and back) on every rack, the half rack included;
  * every rack's staged mount directions = All (the containment rail mounts Forward / Backward)."""
import json
import os

import pytest

from dc import catalog, config, dims as DM

FULL = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear")
HALF = ("DC_Rack24_Open", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
ALL_RACKS = FULL + HALF
MM = 0.001


def _entry(name):
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        blocks = json.load(f)["blocks"]
    assert name in blocks, f"{name} not in build_report.json"
    e = blocks[name]
    assert e["placement"]["total"] > 0, f"{name} has no placement data (stub builder?)"
    return e


# ---------------------------------------------------------------------------------------------------- constants

def test_room_constants():
    assert DM.RF_H % 0.25 == 0 and DM.RF_H == 0.25
    assert DM.RF_TILE == 0.5 and 0 < DM.RF_DECK_T < 0.05
    assert all(w % 0.5 == 0 for w in DM.AISLE_WIDTHS) and DM.AISLE_WIDTHS == (1.0, 1.5, 2.0)
    # the containment rail band: in front of the door leaves' back face, 1 mm inside the cell plane
    assert DM.CONTAIN_RAIL_Y[0] >= DM.DOOR_Y_BACK
    assert DM.CONTAIN_RAIL_Y[1] <= 0.625 - 0.001
    assert 0 < DM.CONTAIN_RAIL_DZ[0] < DM.CONTAIN_RAIL_DZ[1] < 0.25
    assert DM.ROOF_CLEAR > 0
    # the PDU envelope (A column, +x; B is mirrored): inside its column, big enough for a strip, clear of the rear
    # leaves and the server ears
    (x0, x1), (y0, y1) = DM.PDU_ENVELOPE
    assert DM.PDU_COL_X[0] <= x0 < x1 <= DM.PDU_COL_X[1]
    assert DM.PDU_COL_Y[0] <= y0 < y1 <= DM.PDU_COL_Y[1]
    assert x1 - x0 >= 0.10 and y1 - y0 >= 0.10
    assert max(abs(y0), abs(y1)) <= DM.DOOR_Y_BACK - 0.002
    assert x0 >= DM.RAIL_X[1] + 0.002
    assert DM.PDU_RECEPTACLE == pytest.approx(((x0 + x1) / 2, (y0 + y1) / 2))
    # the rack-top label pad (front cell, centred two cells)
    assert DM.LABEL_X == (-0.25, 0.25) and DM.LABEL_Y == (0.375, 0.625)


def test_rod_plate_single_source():
    """dims.ROD_PLATE is the cable trays' rod-coupler plate (tray_plan derives it from the cell and the rod spacing)."""
    from dc import tray_plan
    assert DM.ROD_PLATE == pytest.approx(tray_plan.ROD_PLATE)


def test_pdu_cells_helpers():
    from dc import rack
    for name in ALL_RACKS:
        spec = catalog.BY_NAME[name]
        (bx0, by0, bz0), (bx1, by1, bz1) = catalog.bounds(spec)
        n = rack.dims(spec)["nslots"]
        a, b = rack.PDU_CELLS(spec, "A"), rack.PDU_CELLS(spec, "B")
        assert len(a) == len(b) == n
        assert {c[0] for c in a} == {bx1} and {c[0] for c in b} == {bx0}    # A = +x, B = -x
        assert {c[2] for c in a} == {c[2] for c in b} == {bz1}              # the rear cell (game +z = Blender -y)
        assert sorted(c[1] for c in a) == list(range(by0 + 1, by0 + 1 + n))
        free = rack.FREE_CELLS(spec)
        # the slots, their front opening row (free for placement) and the two PDU columns, all distinct
        assert len(set(free)) == len(free) == len(rack.SLOT_CELLS(spec)) + len(rack.OPENING_CELLS(spec)) + 2 * n
        assert not set(rack.OPENING_CELLS(spec)) & (set(a) | set(b) | set(rack.SLOT_CELLS(spec)))
        with pytest.raises(ValueError):
            rack.PDU_CELLS(spec, "C")


def test_kvm_clear_of_rail():
    """A KVM popped out of the full rack's top slot: wherever its lid rises above the slot band (into the tray band),
    it stays behind the containment rail (and so behind a roof panel's edge)."""
    from dc import rack, subparts
    spec = catalog.BY_NAME["DC_Rack42_Open"]
    d = rack.dims(spec)
    zc = 0.25 + DM.SLOT_H * (d["nslots"] - 1) + DM.SLOT_H / 2      # the top slot's centre (local z)
    for i in range(21):
        f = i * 0.05
        c = subparts.lid_at(f)
        # the lid is a box: sample the segments between all its corners (edges and diagonals, all inside the box;
        # corners alone would miss an edge crossing z = ZT)
        for p, q in [(p, q) for k, p in enumerate(c) for q in c[k + 1:]]:
            for t in range(11):
                x, y, z = (p[j] + (q[j] - p[j]) * t / 10 for j in range(3))
                if z + zc > d["ZT"]:
                    assert abs(y) < DM.CONTAIN_RAIL_Y[0], (f, (x, y, z + zc))


# ---------------------------------------------------------------------------------------------------- measured

@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_pdu_columns_free(name):
    from dc import rack
    spec = catalog.BY_NAME[name]
    e = _entry(name)
    free = {tuple(c) for c in e["placement"]["free_cells"]}
    for feed in ("A", "B"):
        assert set(rack.PDU_CELLS(spec, feed)) <= free, (feed, sorted(set(rack.PDU_CELLS(spec, feed)) - free))
    assert len(free) == len(rack.FREE_CELLS(spec))
    g = e["geometry"]
    assert g["pdu_envelope_clear"] == 0, g.get("pdu_envelope_hits")


@pytest.mark.build
@pytest.mark.parametrize("name", FULL)
def test_containment_rail_band(name):
    from dc import rack
    e = _entry(name)
    spec = catalog.BY_NAME[name]
    d = rack.dims(spec)
    zt = d["ZT"] - d["H"] / 2                       # ZT in the centred frame
    rails = e["geometry"]["contain_rails"]
    assert set(rails) == {"front", "back"}
    for side, (x0, x1, y0, y1, z0, z1) in rails.items():
        assert DM.CONTAIN_RAIL_Y[0] - 1e-5 <= min(abs(y0), abs(y1)) and max(abs(y0), abs(y1)) <= \
            DM.CONTAIN_RAIL_Y[1] + 1e-5, (side, y0, y1)
        assert (y0 > 0) == (side == "front")
        assert zt + DM.CONTAIN_RAIL_DZ[0] - 1e-5 <= z0 < z1 <= zt + DM.CONTAIN_RAIL_DZ[1] + 1e-5, (side, z0, z1)
        # above the door leaves' tops, as measured on the built leaves (door racks); the designed top otherwise
        leaf_top = max(z[1] for z in e["doors"]["z"].values()) if e.get("doors") else zt - DM.DOOR_Z_GAP
        assert z0 > leaf_top, (side, z0, leaf_top)
        # the full rack width (a continuous rail along the row), but never into the neighbour's cell
        assert x1 - x0 >= 0.95 and x1 - x0 <= 1.0 - 0.002 and max(abs(x0), abs(x1)) <= 0.5 - 0.001, (x0, x1)
    f = e["placement"]["faces"]
    assert f["Forward"]["groups"] == 1, f["Forward"]
    assert f["Backward"]["plane_groups"] == 1, f["Backward"]


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_label_pad_mountable(name):
    e = _entry(name)
    rects = e["geometry"]["up_mount_rects"]
    for sy in (1, -1):
        ly0, ly1 = sorted(sy * v for v in DM.LABEL_Y)
        area = 0.0
        for x0, x1, y0, y1 in rects:
            w = min(x1, DM.LABEL_X[1]) - max(x0, DM.LABEL_X[0])
            h = min(y1, ly1) - max(y0, ly0)
            if w > 0 and h > 0:
                area += w * h
        # the hints cover the rim band over the pad (|y| IY 0.46 .. YK 0.598, the full 0.5 m width): 0.069 m2, which
        # carries 6 of the sampler's 8 rays per pad cell; a lost rim (or a narrowed one) fails
        assert area >= 0.5 * (0.598 - DM.RACK_TRAY_IY) - 1e-6, (name, sy, area, rects)
    assert e["geometry"]["down_mount_rects"], name


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_pdu_seat_and_receptacle(name):
    from dc import rack
    spec = catalog.BY_NAME[name]
    e = _entry(name)
    H = rack.dims(spec)["H"]
    top = 0.25 - H / 2
    rx, ry = DM.PDU_RECEPTACLE
    got = sorted(e["geometry"]["pdu_receptacles"])
    want = sorted([[-rx, ry, top], [rx, ry, top]])
    assert len(got) == 2
    for g, w in zip(got, want):
        assert g == pytest.approx(w, abs=MM), (g, w)
    hints = {n for n, _, _ in rack.collision(spec)["mount"]}
    assert {"pdu_seat_A", "pdu_seat_B", "pdu_bracket_A", "pdu_bracket_B"} <= hints
    # the brackets: the side column's rear face at y = -SLOT_HALF_D, over each column; the seats on the plinth top
    boxes = {n: (lo, hi) for n, lo, hi in rack.collision(spec)["mount"]}
    for feed, sx in (("A", 1), ("B", -1)):
        lo, hi = boxes[f"pdu_bracket_{feed}"]
        assert lo[1] == pytest.approx(-DM.SLOT_HALF_D) and sx * (lo[0] + hi[0]) > 0
        lo, hi = boxes[f"pdu_seat_{feed}"]
        assert hi[2] == pytest.approx(top) and hi[1] <= -DM.SLOT_HALF_D + 1e-9 and sx * (lo[0] + hi[0]) > 0


@pytest.mark.build
@pytest.mark.parametrize("name", ALL_RACKS)
def test_pdu_brackets_are_the_only_inner_back_mounts(name):
    """The PDU brackets mount (inner Backward cells, one column of cells in front of each PDU column); nothing else
    behind the slot band mounts, so the rear opening stays open."""
    from dc import rack
    spec = catalog.BY_NAME[name]
    e = _entry(name)
    inner = {tuple(c) for c in e["placement"]["inner_mounts"]["Backward"]}
    want = {(x, y, z - 1) for f in ("A", "B") for (x, y, z) in rack.PDU_CELLS(spec, f)}
    assert inner == want, (sorted(inner - want), sorted(want - inner))


# ---------------------------------------------------------------------------------------------------- staged
@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_directions_all(name, staged):
    """Every rack's staged block definition mounts in all six directions (the open rack's cloned wall panel had no
    Forward; the door racks' template already says All and the patch states it explicitly)."""
    from dc import clone
    from dc.assetio import read_json
    info = clone.entry(catalog.BY_NAME[name])["info"]
    bd = read_json(os.path.join(config.STAGE_ASSETS, info["block_def_file"]))["$Value"]["Manipulator"]
    assert bd["MountPointGeneratorSettings"]["Directions"] == "All", name
