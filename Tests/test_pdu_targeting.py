"""Final review I1 (2026-10-19): the block placer seats a zero-U PDU strip only at its designed place, the rack's rear
PDU column (rack.PDU_CELLS), in every rack (42U / 24U; Open, SplitFront, SplitFrontRear) for both feeds.

The defect: the strip mounted Forward (its brackets on the column's bulkhead) and Down (its inlet plug on the plinth
top). The placer centres the strip on the aimed cell (BlockPlacementSnapping TrySnapPreviewToGrid), so aiming at the
upper half of a 24U column put it one or two cells up, sticking out through the half rack's open top (the cells above
the rack are empty, so TryFindFreePosition never ran), and the bulkhead mounts over the whole column (its render face
lies 0.5 mm inside the bracket plane, so the generator mounts every column cell whatever the pdu_bracket hint says:
measured, build_dc.py with the hint cut to the bottom row) validated it: ANY one mount cell is enough
(BlockPlacementValidation.cs:178-264, BlockPlacementTester.cs:181-193). The fix: a strip mounts Down only (its plug
seat; dc/pdu.strip_directions). A raised strip's bottom then faces an empty column cell, so it never validates; the
designed seat validates on the plinth's pdu_seat.

dc/placer_emu.py runs the decompiled placer on the rack as built (build_report.json: free cells, every mount cell,
the regular collision boxes) and the strip with its STAGED mount directions (whole faces: the report's coverage).
Asserted per rack, feed and neighbourhood (empty rack; the other feed's strip seated; that plus a server in every
slot):
  * the natural aims seat the strip exactly: from the hot aisle (1.4 m behind the rack, eye 1.6 m) at the plinth top
    under the column, and at the bulkhead behind the strip's centre cell (the column's middle);
  * over a fan of aims from behind the rack (eyes 0.8 / 1.6 m out, left / centre / right, low / level / high; looking
    at the bulkhead over the whole column height and at the plinth top) no aim yields a validating ghost that touches
    the rack's cell box other than the exact seat; a validating ghost wholly outside the box stands on the rack's top
    (a strip's Down mount meets any Up face, INGAME-CHECKLIST: a floor tile, a rack top), held by outer mounts only.
The strip is aimed with the rack's orientation (the designed one; a player who turns it gets a turned strip).
"""
import json
import os

import pytest

from dc import catalog, config, integration, pdu, rack
from dc import placer_emu as E

pytestmark = pytest.mark.build

RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_Open",
         "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
FEEDS = ("A", "B")


def _report():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _strip_name(rack_name, feed):
    return f"DC_PDU_Rack{rack_name[7:9]}_{feed}"


def _strip(name, rep):
    """The strip as the placer sees it: its staged directions (integration.pdu_patch -> pdu.strip_directions), each a
    whole face (asserted from the report's coverage)."""
    spec = catalog.BY_NAME[name]
    dirs = [d.strip() for d in pdu.strip_directions(spec).split(",")]
    faces = rep[name]["placement"]["faces"]
    for d, f in faces.items():
        assert f["coverage"] == (1.0 if d in dirs else 0.0), (name, d, f)
    lo, hi = catalog.bounds(spec)
    return E.Prefab(name, lo, hi, dirs)


def _setup(rack_name, feed):
    rep = _report()
    spec = catalog.BY_NAME[rack_name]
    rb = E.rack_block(spec, rep[rack_name])
    pf = _strip(_strip_name(rack_name, feed), rep)
    seat = {tuple(c) for c in rack.PDU_CELLS(spec, feed)}
    assert E.placed(pf, E.ROT_ID, E.mounted_for(pf, E.ROT_ID, seat)).cells == seat
    return spec, rb, pf, seat, rep


def _scenarios(spec, rb, feed, rep):
    """(label, grid): the empty rack; the other feed's strip seated; that plus a compute server in every slot."""
    other = "B" if feed == "A" else "A"
    opf = _strip(_strip_name(spec.name, other), rep)
    ocells = {tuple(c) for c in rack.PDU_CELLS(spec, other)}
    out = [("empty", E.Grid([rb]))]
    g = E.Grid([rb])
    g.add(E.placed(opf, E.ROT_ID, E.mounted_for(opf, E.ROT_ID, ocells), "other strip"))
    out.append(("other strip", g))
    g = E.Grid([rb])
    g.add(E.placed(opf, E.ROT_ID, E.mounted_for(opf, E.ROT_ID, ocells), "other strip"))
    srv = E.server_prefab(catalog.BY_NAME["DC_Srv_Compute"], integration.SERVER_MOUNTS)
    slots = {tuple(c) for c in rack.SLOT_CELLS(spec)}
    for k, y in enumerate(sorted({c[1] for c in slots})):
        cells = {c for c in slots if c[1] == y}
        g.add(E.placed(srv, E.ROT_ID, E.mounted_for(srv, E.ROT_ID, cells), f"server {k + 1}"))
    out.append(("full", g))
    return out


def _geometry(spec, seat):
    (x0, y0, z0), (x1, y1, z1) = catalog.bounds(spec)
    xc = E.CELL * next(iter(seat))[0]
    ys = sorted(c[1] for c in seat)
    zc = E.CELL * next(iter(seat))[2]
    return {"xc": xc, "ybot": E.CELL * ys[0] - E.HALF, "ytop": E.CELL * ys[-1] + E.HALF, "zc": zc,
            "bracket": zc - E.HALF - 0.001,          # just inside the bulkhead (the side column's physics)
            "floor": E.CELL * y0 - E.HALF, "rear": E.CELL * z1 + E.HALF}


def _natural_aims(spec, seat, pf):
    """The plinth top under the column (INGAME-CHECKLIST 13.2: the plug's seat), and the bulkhead behind the strip's
    centre cell (the placer centres the ghost on the aimed cell: TrySnapPreviewToGrid, Min + (Max - Min) / 2)."""
    g = _geometry(spec, seat)
    eye = (g["xc"], g["floor"] + 1.6, g["rear"] + 1.4)
    yc = E.CELL * (min(c[1] for c in seat) + pf.centre[1] - pf.lo[1])
    return [("bulkhead, centre cell", eye, (g["xc"], yc, g["bracket"])),
            ("plinth top", eye, (g["xc"], g["ybot"] - 0.001, g["zc"]))]


def _aim_fan(spec, seat):
    g = _geometry(spec, seat)
    looks = []
    for fy in (0.03, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 0.97):
        for dx in (-0.08, 0.0, 0.08):
            looks.append(((g["xc"] + dx, g["ybot"] + fy * (g["ytop"] - g["ybot"]), g["bracket"]), f"bulkhead {fy}"))
    for dx in (-0.06, 0.06):
        for dz in (-0.08, 0.0, 0.08):
            looks.append(((g["xc"] + dx, g["ybot"] - 0.001, g["zc"] + dz), "plinth top"))
    for dist in (0.8, 1.6):
        for dx in (-0.5, 0.0, 0.5):
            for eh in (0.7, 1.6, 2.3):
                eye = (g["xc"] + dx, g["floor"] + eh, g["rear"] + dist)
                for la, lab in looks:
                    yield eye, la, f"eye d{dist} dx{dx} h{eh} -> {lab}"


@pytest.mark.parametrize("feed", FEEDS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_natural_aims_seat_the_strip(rack_name, feed):
    spec, rb, pf, seat, rep = _setup(rack_name, feed)
    bad = []
    for lab, g in _scenarios(spec, rb, feed, rep):
        for al, eye, look in _natural_aims(spec, seat, pf):
            r = g.aim(pf, E.ROT_ID, eye, look)
            if r is None or not r["valid"] or r["cells"] != seat:
                bad.append((lab, al, r and (r["hit"], r["normal"], sorted(r["cells"]), r["valid"])))
    assert not bad, bad


@pytest.mark.parametrize("feed", FEEDS)
@pytest.mark.parametrize("rack_name", RACKS)
def test_no_aim_mis_seats_the_strip(rack_name, feed):
    spec, rb, pf, seat, rep = _setup(rack_name, feed)
    lo, hi = catalog.bounds(spec)
    box = E.box_cells(lo, hi)
    inner = {d: {tuple(c) for c in cs} for d, cs in rep[rack_name]["placement"]["inner_mounts"].items()}
    wrong, seated = [], 0
    for lab, g in _scenarios(spec, rb, feed, rep):
        for eye, look, al in _aim_fan(spec, seat):
            r = g.aim(pf, E.ROT_ID, eye, look)
            if r is None or not r["valid"]:
                continue
            if r["cells"] == seat:
                seated += 1
                continue
            row = (lab, al, sorted(r["cells"]))
            if r["cells"] & box:
                wrong.append(row)
                continue
            m = E.mounted_for(pf, E.ROT_ID, r["cells"])
            held = [n for d, cs in pf.mount_cells.items() for c in cs
                    for n in [E.add(E.add(c, m), E.DIRS[d])]
                    if g.at.get(n) is rb and n in rb.mounts.get(E.VEC2DIR[E.neg(E.DIRS[d])], ())]
            on_top = all(c[1] > hi[1] for c in r["cells"])
            if not (on_top and held and not any(n in inner.get("Up", ()) for n in held)):
                wrong.append(row + (held,))
    assert not wrong, (len(wrong), wrong[:4])
    assert seated, "no aim of the fan seats the strip"
