"""Rack frame and slot mechanics, asserted on build_report.json (run the Blender build first).

Slot sizes: racks 4 cells wide, servers 2x1x3 cells, so the
free slot cells are 8 x 2 x 1 x 3 = 48 (full rack) and 24 (half rack)."""
import json
import os

import pytest

from dc import catalog, config

pytestmark = pytest.mark.build

OPEN_RACKS = ("DC_Rack42_Open", "DC_Rack24_Open")
# the door variants share the frame (dc/rack.py), so every frame / slot test runs on them too
ALL_RACKS = OPEN_RACKS + ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFront",
                          "DC_Rack24_SplitFrontRear")


def _report():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _entry(name):
    blocks = _report()
    assert name in blocks, f"{name} not in build_report.json"
    e = blocks[name]
    assert e["placement"]["total"] > 0, f"{name} has no placement data (stub builder?)"
    return e


@pytest.mark.parametrize("name,n_slot_cells", [(n, (8 if "42" in n else 4) * 2 * 1 * 3) for n in ALL_RACKS])
def test_rack_slots_free_and_mountable(name, n_slot_cells):
    """Placement fix (2026-10-18): the free cells are the slots AND, in front of each, the slot columns' front-zone
    row (the opening the placer's ray enters by; the old front-zone occupancy sealed every slot, the bug); the rear
    zone stays occupied (the rear stop). The slot mounts only on its REAR row: the rails (inner faces of the side
    columns), the slot floor (plinth top) and, on the full rack, the slot ceiling (tray floor)."""
    from dc import rack
    spec = catalog.BY_NAME[name]
    slots = {tuple(c) for c in rack.SLOT_CELLS(spec)}
    assert len(slots) == n_slot_cells
    p = _entry(name)["placement"]
    free = {tuple(c) for c in p["free_cells"]}
    lo, hi = catalog.bounds(spec)
    xs = sorted({c[0] for c in slots})
    ys = sorted({c[1] for c in slots})
    zs = sorted({c[2] for c in slots})
    zf, zr = lo[2], zs[-1]                       # the front-zone row (game -z = Forward) and the slot's rear row
    opening = {(x, y, zf) for x in xs for y in ys}
    assert zf == zs[0] - 1 and hi[2] == zr + 1
    assert opening == set(rack.OPENING_CELLS(spec))
    # plus the two rear PDU columns; the rest of the front zone and the rear zone stay occupied
    pdu = set(rack.PDU_CELLS(spec, "A")) | set(rack.PDU_CELLS(spec, "B"))
    want = slots | opening | pdu
    assert free == want, (sorted(free - want)[:8], sorted(want - free)[:8])
    assert free == set(rack.FREE_CELLS(spec))
    assert p["occupied"] == p["total"] - len(free)
    nx, ny, nz = spec.cells
    assert p["total"] == nx * ny * nz
    inner = {d: {tuple(c) for c in cells} for d, cells in p["inner_mounts"].items()}
    assert inner["Right"] == {(xs[0] - 1, y, zr) for y in ys}, sorted(inner["Right"])       # left rail
    assert inner["Left"] == {(xs[-1] + 1, y, zr) for y in ys}, sorted(inner["Left"])        # right rail
    # the PDU columns: the strip's seat on the plinth top (Up, under the column's bottom cell) and its
    # bracket, the side column's rear face (Backward, the occupied cell in front of each PDU cell)
    seats = {(c[0], ys[0] - 1, c[2]) for c in pdu}
    brackets = {(c[0], c[1], c[2] - 1) for c in pdu}
    assert inner["Up"] == {(x, ys[0] - 1, zr) for x in xs} | seats, sorted(inner["Up"])     # slot floor + seats
    ceiling = {c for c in inner["Down"] if c[2] in zs and c[0] in xs}
    assert ceiling == ({(x, ys[-1] + 1, zr) for x in xs} if name.startswith("DC_Rack42") else set()), sorted(ceiling)
    assert not inner["Forward"]
    assert set(inner["Backward"]) == brackets, sorted(inner["Backward"])


@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_slot_cavities_reachable(name):
    """Every slot cell connects through free cells to the rack's FRONT face (the placer's ray can reach it; the
    targeting stops at the first occupied cell, BlockPlacementAlignment.cs:558, 2.4: 530), and none to the rear face: the
    rear stop closes the slot's back (servers load from the front, the rear zone is cable space)."""
    from collections import deque
    from dc import rack
    spec = catalog.BY_NAME[name]
    lo, hi = catalog.bounds(spec)
    p = _entry(name)["placement"]
    free = {tuple(c) for c in p["free_cells"]}

    def flood(seed):
        seen, q = set(seed), deque(seed)
        while q:
            c = q.popleft()
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                n = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
                if n in free and n not in seen:
                    seen.add(n)
                    q.append(n)
        return seen

    front = flood([c for c in free if c[2] == lo[2]])
    slots = {tuple(c) for c in rack.SLOT_CELLS(spec)}
    assert slots <= front, sorted(slots - front)[:8]
    # the only free rear-face cells are the PDU columns, and they do not lead into a slot
    rear_free = {c for c in free if c[2] == hi[2]}
    assert rear_free == set(rack.PDU_CELLS(spec, "A")) | set(rack.PDU_CELLS(spec, "B")), sorted(rear_free)[:8]
    assert not flood(sorted(rear_free)) & slots, "the rear stop does not close the slot"


@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_rear_stop(name):
    """The rear stop is a regular (physics) box right behind the slot's back plane, across both slot columns and
    the whole slot band: the placer's physics ray has something to hit in an empty open rack (no physics behind
    it, BlockPlacementAlignment.cs:519-535, 2.4: 491-507), and its cell is the first occupied one the ray then crosses."""
    from dc import dims as DM, rack
    spec = catalog.BY_NAME[name]
    d = rack.dims(spec)
    reg = {n: (lo, hi) for n, lo, hi in rack.collision(spec)["regular"]}
    lo, hi = reg["rear_stop"]
    zb = -d["H"] / 2
    assert hi[1] == pytest.approx(-(DM.SLOT_HALF_D + rack.REAR_STOP_GAP))
    assert 0.0 < rack.REAR_STOP_GAP <= 0.0045 and hi[1] - lo[1] >= 0.01
    assert lo[0] <= -DM.SLOT_HALF_W + 0.003 and hi[0] >= DM.SLOT_HALF_W - 0.003
    assert lo[2] <= zb + 0.25 + 0.003 and hi[2] >= zb + d["ZT"] - 0.003
    assert not rack.collision(spec)["occupancy"], "no occupancy hint is needed any more"


@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_side_faces_mountable(name):
    f = _entry(name)["placement"]["faces"]
    for d in ("Left", "Right"):
        assert f[d]["coverage"] >= 0.5 and f[d]["groups"] >= 1, (d, f[d])
    assert f["Down"]["groups"] >= 1, f["Down"]
    if name.startswith("DC_Rack42"):   # the tray rim mounts (the trough in the middle is open by design)
        assert f["Up"]["groups"] >= 1, f["Up"]


@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_front_back_open(name):
    """The front and back openings never mount, except the full racks' containment rail band: one row of
    cells on the box plane (coverage 4 / 40). The PDU brackets are inner Backward mounts (one cell in front of each
    PDU column), so the Backward check counts the box plane only (Tests/test_room_interface.py pins the brackets)."""
    f = _entry(name)["placement"]["faces"]
    if name.startswith("DC_Rack42"):
        assert f["Forward"]["groups"] == 1 and f["Forward"]["coverage"] <= 0.11, f["Forward"]
        assert f["Backward"]["plane_groups"] == 1 and f["Backward"]["coverage"] <= 0.11, f["Backward"]
    else:
        assert f["Forward"]["groups"] == 0, f["Forward"]
        assert f["Backward"]["plane_groups"] == 0 and f["Backward"]["coverage"] == 0, f["Backward"]


@pytest.mark.parametrize("name", ALL_RACKS)
def test_rack_limits(name):
    from se2model import limits
    spec = catalog.BY_NAME[name]
    lods = _entry(name)["lods"]
    # Keen's size table decides the LOD count from the LOD0 MESH bounds (the checker's "Surface area"): the full
    # rack (13.4 m2, just under the 25/74 row threshold) gets LOD0-2 + a LOD3 box, as does the half rack.
    e = _entry(name)
    n = limits.model_limits(tuple(e["model_size"]), lods[0]["tris"])["optimal_lods"]
    x, y, z = spec.cells   # model_size is in the Blender frame (x, depth, height)
    assert e["model_size"] == [pytest.approx(0.25 * c, abs=0.08) for c in (x, z, y)]
    assert len(lods) == n, (len(lods), n)
    assert lods[-1]["tris"] == 12
    for i, l in enumerate(lods):
        assert l["tris"] <= l["max_tris"], (i, l)
        assert l["materials"] <= l["max_materials"], (i, l)
