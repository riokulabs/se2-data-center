"""Placement fix (2026-10-18): the block placer can put a server into every rack slot, and only at its designed depth.

dc/placer_emu.py emulates the decompiled placer (targeting, snapping, mount-point substitution, free-position search,
validation; file:line references there) on the rack as built (build_report.json free cells and every mount cell,
the outer faces included; the collision boxes of dc/rack.py) and the servers' staged mount directions (dc/integration.SERVER_MOUNTS / UPS_MOUNTS).

Asserted per rack (42U and 24U; Open, SplitFront, SplitFrontRear), per server height (6U: 1 cell, the 12U UPS: 2), per
slot, with the slot's neighbours empty and filled, and for the server facing the rack's front and turned round
(Ruling P4-13 allows a rear-facing KVM):
  * the obvious aim, straight at the middle of the slot's rear stop from the aisle, seats it exactly;
  * over a fan of aims (eyes 0.8-2.2 m out, left / centre / right, low / level / high; looking at the rear stop, at
    the rails and at the floor on every depth row) no aim yields a placement inside the rack that validates and is
    not exactly a slot seat (the old front zone let a server sit one cell forward on the rails, Ruling 7);
  * placed directly one cell forward or back of its seat, a server never validates (empty cells and a mount point).
"""
import json
import os

import pytest

from dc import catalog, config, integration, rack
from dc import placer_emu as E

pytestmark = pytest.mark.build

RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_Open",
         "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
SERVERS = (("DC_Srv_Compute", 1, integration.SERVER_MOUNTS), ("DC_Srv_UPS", 2, integration.UPS_MOUNTS))
ROTS = (("front", E.ROT_ID), ("turned", E.ROT_YAW180))


def _report():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _setup(rack_name, srv_name, dirs):
    blocks = _report()
    spec = catalog.BY_NAME[rack_name]
    rb = E.rack_block(spec, blocks[rack_name])
    slots = {tuple(c) for c in rack.SLOT_CELLS(spec)}
    srv = E.server_prefab(catalog.BY_NAME[srv_name], dirs)
    return spec, rb, slots, srv


def _seats(slots, srv, n_u):
    n = len({c[1] for c in slots})
    return {k: E.slot_seat(slots, srv, k, n_u) for k in range(1, n - n_u + 2)}


def _scenarios(rb, slots, srv, n_u, k):
    """(label, grid): the slot's neighbours empty; the seat below filled; the seat above filled."""
    seats = _seats(slots, srv, n_u)
    out = [("empty", E.Grid([rb]))]
    for lab, j in (("below", k - n_u), ("above", k + n_u)):
        if j in seats:
            g = E.Grid([rb])
            g.add(E.placed(srv, E.ROT_ID, E.mounted_for(srv, E.ROT_ID, seats[j]), lab))
            out.append((lab, g))
    return out


def _top_of_half_rack(spec, seat):
    """The seat touches the top face of a half rack (no tray: the block's top is the slot's ceiling)."""
    _, hi = catalog.bounds(spec)
    return not rack.dims(spec)["tray"] and max(c[1] for c in seat) == hi[1]


@pytest.mark.parametrize("srv_name,n_u,dirs", SERVERS, ids=[s[0] for s in SERVERS])
@pytest.mark.parametrize("rack_name", RACKS)
def test_obvious_aim_seats(rack_name, srv_name, n_u, dirs):
    """Aim from 1.5 m in front of the rack, level with the slot, at the slot's rear stop, 6 cm left or right of the
    slot's middle (the middle itself is the boundary of the slot's two cell columns) and in the middle of its bottom
    row: the ghost fills the slot exactly and validates, in every slot, with or without neighbours, facing either way.

    One residual, asserted so it stays known: on the TOP slot of a half rack, the right-of-middle aim does not seat.
    The placer puts a 2-wide block's left cell on the aimed cell (the snap centres Min + (Max - Min) / 2), so the
    ghost first overlaps the right column; TryFindFreePosition then takes the nearest empty offset in its scan order
    (BlockPlacementSnapping.cs:257-266 in 4.0.0.3151, same tie order as 2.4's :240-253), which is one cell UP (out through the half rack's open top) before one cell
    left. Everywhere else the cell above is occupied (the next slot's column cells, the full rack's tray) and the
    ghost steps left into the slot."""
    spec, rb, slots, srv = _setup(rack_name, srv_name, dirs)
    lo, _ = catalog.bounds(spec)
    bad, residual = [], []
    for k, seat in _seats(slots, srv, n_u).items():
        xs = [E.CELL * c[0] for c in seat]
        y0 = E.CELL * min(c[1] for c in seat)
        zb = E.CELL * max(c[2] for c in seat) + E.HALF
        for side, dx in (("left", -0.06), ("right", 0.06)):
            look = ((min(xs) + max(xs)) / 2 + dx, y0, zb + 0.001)
            eye = (look[0], look[1] + 0.05, E.CELL * lo[2] - E.HALF - 1.5)
            for lab, g in _scenarios(rb, slots, srv, n_u, k):
                for rl, R in ROTS:
                    r = g.aim(srv, R, eye, look)
                    ok = r is not None and r["valid"] and r["cells"] == seat
                    if ok:
                        continue
                    row = (k, side, lab, rl, r and (r["hit_block"], r["normal"], sorted(r["cells"])[:3], r["valid"]))
                    (residual if side == "right" and _top_of_half_rack(spec, seat) else bad).append(row)
    assert not bad, bad[:6]
    if not rack.dims(spec)["tray"] and n_u == 1:   # (the UPS's bottom row is below the top: the cell above is taken)
        assert residual, "the half rack's top-slot residual is gone: update the report and this test"


def _holds(g, prefab, R, cells, rb):
    """[(rack mount direction, rack cell)] of the rack's mount points this placement's mount cells meet."""
    m = E.mounted_for(prefab, R, cells)
    out = []
    for d, cs in prefab.mount_cells.items():
        gd = E.mul(R, E.DIRS[d])
        opp = E.VEC2DIR[E.neg(gd)]
        for c in cs:
            n = E.add(E.add(E.mul(R, c), m), gd)
            if g.at.get(n) is rb and n in rb.mounts.get(opp, ()):
                out.append((opp, n))
    return out


@pytest.mark.slow   # ~82 s over the 12 cases (the aim fan through the placer emulation)
@pytest.mark.parametrize("srv_name,n_u,dirs", SERVERS, ids=[s[0] for s in SERVERS])
@pytest.mark.parametrize("rack_name", RACKS)
def test_no_aim_mis_seats(rack_name, srv_name, n_u, dirs):
    """Over the aim fan, every validating ghost that touches the rack's cell box sits at a slot's designed depth and
    across its two cell columns, and every slot is seated by some aim. The only validating ghost in the box that is
    not exactly a slot seat is the 12U UPS in a half rack's top slot sticking out through the open top (its bottom
    slot's rails hold it, as before the fix: the half rack's roof is render-only), asserted to be that and nothing
    else.

    The rack carries its outer-face mounts too (placer_emu.rack_block, final review M1). A high, close eye aiming at
    the top slot's back can meet the rack's outside first (the 42U tray band's front, the top rim), and the ghost then
    stands wholly outside the box on that face: on the top (Down on the rim / roof) or, on a full (42U) rack, hung
    on the containment rail band (Backward on its Forward mounts). That is a placement on the rack's outside,
    visibly not in a slot; it is asserted to be held only by outer-face mount cells and never to reach into the
    box."""
    spec, rb, slots, srv = _setup(rack_name, srv_name, dirs)
    lo, hi = catalog.bounds(spec)
    box = E.box_cells(lo, hi)
    seats = _seats(slots, srv, n_u)
    seat_set = [frozenset(s) for s in seats.values()]
    foot = {(c[0], c[2]) for c in slots}
    outer = {d: cs - {tuple(c) for c in _report()[rack_name]["placement"]["inner_mounts"][d]}
             for d, cs in rb.mounts.items()}
    wrong, overhang, outside, seated = [], [], [], set()
    for k, seat in seats.items():
        for lab, g in _scenarios(rb, slots, srv, n_u, k):
            for rl, R in ROTS:
                for eye, look, al in E.aim_fan(seat, lo[2], sorted({c[2] for c in seat}), eye_dists=(0.8, 1.6),
                                               eye_dx=(-0.3, 0.3), eye_dy=(-0.35, 0.45)):
                    r = g.aim(srv, R, eye, look)
                    if r is None or not r["valid"]:
                        continue
                    if frozenset(r["cells"]) in seat_set:
                        if r["cells"] == seat:
                            seated.add(k)
                    elif not r["cells"] & box:
                        # wholly outside the rack (the ray met its outside: the 42U tray band's front, a top), held
                        # only by the rack's OUTER mounts (final review M1: rack_block now carries them)
                        held = _holds(g, srv, R, r["cells"], rb)
                        row = (k, lab, rl, al, sorted(r["cells"])[:3], sorted(held))
                        (outside if held and all(c in outer[d] for d, c in held) else wrong).append(row)
                    elif r["cells"] & box:
                        row = (k, lab, rl, al, sorted(r["cells"])[:3])
                        out = r["cells"] - box
                        if ({(c[0], c[2]) for c in r["cells"]} == foot and out and n_u > 1
                                and not rack.dims(spec)["tray"] and all(c[1] == hi[1] + 1 for c in out)):
                            overhang.append(row)
                        else:
                            wrong.append(row)
    assert not wrong, (len(wrong), wrong[:4])
    assert seated == set(seats), sorted(set(seats) - seated)
    for row in outside:   # a ghost on the outside sits beside the box face it mounts on, never across a slot
        assert all(c[1] > hi[1] or c[2] < lo[2] or c[2] > hi[2] or c[0] < lo[0] or c[0] > hi[0] for c in row[4]), row
    if overhang:
        assert n_u == 2 and not rack.dims(spec)["tray"], overhang[:3]


@pytest.mark.parametrize("srv_name,n_u,dirs", SERVERS, ids=[s[0] for s in SERVERS])
@pytest.mark.parametrize("rack_name", RACKS)
def test_off_depth_never_validates(rack_name, srv_name, n_u, dirs):
    """One cell forward of its seat (into the door zone) a server's cells are free but it touches no mount point,
    with or without seated servers above and below; one cell back it collides with the rear stop."""
    spec, rb, slots, srv = _setup(rack_name, srv_name, dirs)
    bad = []
    for k, seat in _seats(slots, srv, n_u).items():
        for dz in (-1, 1):
            cells = {(c[0], c[1], c[2] + dz) for c in seat}
            for lab, g in _scenarios(rb, slots, srv, n_u, k):
                for rl, R in ROTS:
                    m = E.mounted_for(srv, R, cells)
                    ok = g.empty(cells) and g.mount_ok(srv, R, m)
                    if ok:
                        bad.append((k, dz, lab, rl))
                    if dz == 1:
                        assert not g.empty(cells), "one cell back should hit the rear stop"
                    else:
                        assert g.empty(cells), "one cell forward is free (the opening): mount points must refuse it"
    assert not bad, bad[:6]


def test_off_depth_needs_no_server_top_mount():
    """Why servers lost their Up mount (dc/integration.SERVER_MOUNTS): with it, a server one cell forward sits on the
    top of a correctly seated server below (two of its three rows overlap) and validates."""
    spec, rb, slots, _ = _setup("DC_Rack42_Open", "DC_Srv_Compute", integration.SERVER_MOUNTS)
    old = E.server_prefab(catalog.BY_NAME["DC_Srv_Compute"], "Backward, Left, Right, Up, Down")
    seats = _seats(slots, old, 1)
    g = E.Grid([rb])
    g.add(E.placed(old, E.ROT_ID, E.mounted_for(old, E.ROT_ID, seats[1]), "below"))
    fwd = {(c[0], c[1], c[2] - 1) for c in seats[2]}
    assert g.empty(fwd) and g.mount_ok(old, E.ROT_ID, E.mounted_for(old, E.ROT_ID, fwd))
    assert "Up" not in integration.SERVER_MOUNTS and "Up" not in integration.UPS_MOUNTS
