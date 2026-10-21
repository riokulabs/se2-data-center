"""Plan 3 Task 7: the PDU cabinet (DC_PDU_Cabinet) and the zero-U rack PDU strips (DC_PDU_Rack{42,24}_{A,B}),
dc/pdu.py.

Pure tests check the builder's numbers (catalogue, collision and hints, mount directions, the single-sourced outlet /
inlet positions, the fracture plans). The build-marked tests check the MEASURED blocks (build_report.json geometry /
placement / lods, the export manifests) against the measured racks:
  * each strip fits its rack's freed rear PDU column (dims.PDU_ENVELOPE x rack.pdu_band, both feeds, both heights),
    occupies exactly rack.PDU_CELLS, conflicts with nothing in a fully populated rack, mounts on the rack's pdu_seat
    hint (Down only since final review I1) with its back on the pdu_bracket plane, and its inlet plug seats in the rack's plinth receptacle (1 mm);
  * a strip stays clear of the rear door leaves and of the UPS's rear bay;
  * the cabinet shares the full rack's interface (footprint, plinth, side and top mounts, the containment rail, the
    top-entry brush plates: a Plan 2 Drop lands in it, Tests/test_tray_build.py LANDINGS; the roof panels mount on it,
    Tests/test_containment.py INROW);
  * limits, materials, breakable exports (dc/fracture.py _pdu_cabinet / _pdu_strip) and the staged definitions.
"""
import json
import os

import pytest

from dc import catalog, config, integration, pdu, rack, room
from dc import dims as DM
from dc import fracture as FR

CAB = "DC_PDU_Cabinet"
STRIPS = ("DC_PDU_Rack42_A", "DC_PDU_Rack42_B", "DC_PDU_Rack24_A", "DC_PDU_Rack24_B")
ALL = (CAB,) + STRIPS
RACKS = {42: ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear"),
         24: ("DC_Rack24_Open", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")}
FIT = [(s, r) for s in STRIPS for r in RACKS[42 if "42" in s else 24]]
MM = 0.001


def _blocks():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _entry(name):
    blocks = _blocks()
    if name not in blocks or not blocks[name].get("placement", {}).get("total"):
        pytest.skip(f"{name} not built yet")
    return blocks[name]


def _manifest(name):
    p = os.path.join(config.MODELS_DIR, name, "export.json")
    if not os.path.exists(p):
        pytest.skip(f"{name} not exported yet")
    with open(p) as f:
        return json.load(f)


def _spec(n):
    return catalog.BY_NAME[n]


def _feed(n):
    return pdu.strip_feed(_spec(n))


def _sx(n):
    return 1 if _feed(n) == "A" else -1


def _strip_origin(strip, rk):
    """The strip's model origin in the rack's centred frame (placed at its PDU column's cells)."""
    rs, ss = _spec(rk), _spec(strip)
    b0 = rack.pdu_band(rs)[0]
    H = rack.dims(rs)["H"]
    return (_sx(strip) * pdu.COL_X, pdu.COL_Y, -H / 2 + b0 + pdu.h2(ss))


def _shift(box, o):
    lo, hi = box
    return tuple(a + b for a, b in zip(lo, o)), tuple(a + b for a, b in zip(hi, o))


# ---------------------------------------------------------------------------------------------------- pure
def test_pdu_catalogue_and_staging():
    assert _spec(CAB).family == "pdu_cabinet" and _spec(CAB).cells == (4, 10, 5)
    for n in STRIPS:
        s = _spec(n)
        assert s.family == "pdu_strip" and s.cells == (1, 8 if "42" in n else 4, 1)
        assert pdu.strip_feed(s) == n[-1]
        assert pdu.strip_rack(s).cells[1] == (10 if "42" in n else 5)
    assert {"pdu_cabinet", "pdu_strip"} <= set(catalog.STAGED_ROOM_FAMILIES)
    assert all(_spec(n) in catalog.STAGED and _spec(n) in catalog.BLOCKS for n in ALL)   # T10
    import build_dc
    assert build_dc.BUILDERS["pdu_cabinet"] is build_dc.build_pdu and build_dc.BUILDERS["pdu_strip"] is build_dc.build_pdu
    with pytest.raises(ValueError):
        pdu.strip_feed(_spec(CAB))


@pytest.mark.parametrize("name", STRIPS)
def test_strip_collision_and_hints(name):
    """One physics box inside the envelope (mirrored for B), one occupancy box over the whole column, one mount hint:
    the plug seat (Down, the whole bottom face). No bracket (Forward) hint since final review I1."""
    s = _spec(name)
    b = pdu.strip_collision(s)
    (nm, lo, hi), = b["regular"]
    x0, x1 = sorted((_sx(name) * pdu.ENV_X[0], _sx(name) * pdu.ENV_X[1]))
    assert (lo[0], hi[0]) == pytest.approx((x0, x1)) and (lo[1], hi[1]) == pytest.approx(pdu.ENV_Y)
    assert lo[2] == pytest.approx(-pdu.h2(s)) and hi[2] == pytest.approx(pdu.strip_top(s))
    assert len(b["occupancy"]) == 1
    hints = {n: (lo, hi) for n, lo, hi in b["mount"]}
    assert set(hints) == {"plug_seat"}      # final review I1: no bracket (Forward) mount, Tests/test_pdu_targeting.py
    lo, hi = hints["plug_seat"]
    assert lo[2] == pytest.approx(-pdu.h2(s)) and hi[2] - lo[2] < 0.01
    assert pdu.strip_directions(s) == "Down"


def test_strip_layout_numbers():
    """The strip's parts in the envelope: the body on the column's centre line round the receptacle, the cord channel
    on the servers' side, the brackets' buttons in the keyholes' column, the outlet pair inside the body face."""
    (ex0, ex1), (ey0, ey1) = pdu.ENV_X, pdu.ENV_Y
    assert ex0 <= pdu.CH_X[0] < pdu.CH_X[1] < pdu.BX[0] < pdu.XC < pdu.BX[1] <= ex1
    assert pdu.BY[0] <= pdu.YR <= pdu.BY[1] and pdu.BY[1] < pdu.BTN_Y <= ey1
    assert pdu.XC == pytest.approx(DM.PDU_RECEPTACLE[0] - pdu.COL_X)
    w = DM.PDU_OUTLET_SIZE[0]
    assert pdu.BX[0] < pdu.OX[0] - w / 2 and pdu.OX[1] + w / 2 < pdu.BX[1] and pdu.OX[1] - pdu.OX[0] > w
    for lane in pdu.LANES:
        assert pdu.CH_X[0] + pdu.CH_W + pdu.LIP < lane - pdu.CORD_R and lane + pdu.CORD_R < pdu.CH_X[1] - pdu.CH_W - pdu.LIP
    assert abs(pdu.LANES[0] - pdu.LANES[1]) > 2 * pdu.CORD_R


@pytest.mark.parametrize("name", STRIPS)
def test_strip_slots_layout(name):
    """Per slot: the outlet pair at dims.PDU_OUTLET_Z (inside the body: the 24U body stops under the half rack's PDU
    band); a bank head per 4 slots over its first slot's outlets; the feed tag in a free slot; the brackets at the
    keyholes; each slot's cords parked under its own strap, inside the strip's box."""
    s = _spec(name)
    zb, zt = -pdu.h2(s), pdu.strip_top(s)
    oz = DM.PDU_OUTLET_SIZE[1] / 2
    for k in range(1, pdu.nslots(s) + 1):
        z = pdu.slot_z(s, k) + DM.PDU_OUTLET_Z
        assert zb + pdu.BODY_Z0 + pdu.CAP_T < z - oz and z + oz < zt - pdu.CAP_T, (name, k)
        for pts in pdu._cord_paths(s, k):
            assert all(zb < p[2] < zt for p in pts), (name, k)
            assert pts[-1][2] == pytest.approx(pdu.strap_z(s, k) - 0.004)
    heads = [k for _, k in pdu.banks(s)]
    assert heads == ([1, 5] if pdu.nslots(s) == 8 else [1])
    t = pdu.tag_slot(s)
    assert t not in heads and pdu.slot_z(s, t) + pdu.HEAD_Z[1] <= zt - pdu.CAP_T
    assert pdu.bracket_slots(s) == (2, pdu.nslots(s))


def test_outlets_and_inlets_single_sourced():
    """The live-cabling hook (WS/docs/ideas/README.md): the strip's outlets and the server's power inlets come from
    dims only. dims.pdu_outlets moved into the strip's frame is pdu.outlets_local; the server builder's PSU bays and
    inlet shells read dims (dc/server.py _rear)."""
    import inspect
    from dc import server
    for n in STRIPS:
        s = _spec(n)
        loc = pdu.outlets_local(s)
        assert len(loc) == 2 * pdu.nslots(s)
        for k, i, (x, y, z) in loc:
            assert x == pytest.approx(_sx(n) * pdu.OX[i]) and y == pytest.approx(pdu.FACE_Y - 0.006)
            assert z == pytest.approx(pdu.slot_z(s, k) + DM.PDU_OUTLET_Z)
    src = inspect.getsource(server._rear)
    assert "DM.SERVER_PSU_X" in src and "DM.SERVER_INLET_B" in src
    inl = DM.server_inlets()
    assert [p[0] for _, p in inl] == [0.125, 0.185] and all(p[1] == DM.SERVER_INLET_FACE_Y for _, p in inl)
    assert server.Y_BACK + 0.016 - 0.007 == pytest.approx(DM.SERVER_INLET_FACE_Y)


def test_cabinet_collision_is_the_racks():
    """The cabinet's physics boxes split where the full rack's do; its mount hints are the rack's flush ones (sides,
    bottom, rim, containment band) and nothing else: no slot, PDU or front / back hints."""
    c = pdu.cabinet_collision(_spec(CAB))
    r = rack.collision(_spec("DC_Rack42_Open"))
    assert len(c["regular"]) == 3 and c["occupancy"] == []
    rk = {n: (lo, hi) for n, lo, hi in r["mount"]}
    ck = {n: (lo, hi) for n, lo, hi in c["mount"]}
    want = {n for n in rk if n.startswith(("side_", "rim_", "contain_")) or n == "bottom"}
    assert set(ck) == want
    for n in want:
        assert ck[n][0] == pytest.approx(rk[n][0]) and ck[n][1] == pytest.approx(rk[n][1]), n


def test_pdu_fracture_plans():
    """The cabinet: the rack pattern, 8 zones (plinth halves, the body's lower / upper sections at the isolator panel
    joint, each halved at x = 0, the top band's halves), no critical zone. The strips: 3 sections (42U) / 2 (24U)
    along the run, Fracture_01 the bottom one with the plug; no seam crosses a cord, an outlet, the plug or a
    bracket."""
    p = FR.plan(_spec(CAB), pdu.cabinet_collision(_spec(CAB)))
    assert len(p.zones) == 8 and p.critical() == [] and p.family == "pdu_cabinet"
    zm = pdu.PANEL_JOINT_Z - pdu.H / 2
    assert any(abs(s.o[2] - zm) < 1e-9 and s.axis() == 2 for s in p.seams)
    assert FR.max_fractures((1.0, 1.25, 2.5)) >= 8
    for n in STRIPS:
        s = _spec(n)
        p = FR.plan(s, pdu.strip_collision(s))
        want = 3 if pdu.nslots(s) == 8 else 2
        assert len(p.zones) == want and p.critical() == [] and all(sm.axis() == 2 for sm in p.seams)
        assert FR.max_fractures((0.13, 0.22, pdu.strip_top(s) + pdu.h2(s))) >= want
        assert p.zone_index((pdu.XC * _sx(n), pdu.YR, -pdu.h2(s) + 0.01)) == 0       # the plug: Fracture_01
        for z in FR.pdu_strip_seams(s):
            for k in range(1, pdu.nslots(s) + 1):
                zo = pdu.slot_z(s, k) + DM.PDU_OUTLET_Z
                assert abs(z - zo) > DM.PDU_OUTLET_SIZE[1] / 2 + 0.004, (n, k)
                for pts in pdu._cord_paths(s, k):
                    zs = [q[2] for q in pts]
                    assert not (min(zs) - pdu.CORD_R - 0.002 < z < max(zs) + pdu.CORD_R + 0.002), (n, k, z)
                if k in pdu.bracket_slots(s):
                    assert abs(z - (pdu.slot_z(s, k) + pdu.BTN_Z)) > 0.03
            for _, k in pdu.banks(s):
                assert not (pdu.slot_z(s, k) + pdu.HEAD_Z[0] - 0.002 < z < pdu.slot_z(s, k) + pdu.HEAD_Z[1])
            assert z > -pdu.h2(s) + pdu.BODY_Z0 + 0.03


def test_reference_room_places_strips_in_columns():
    """dc/room.reference_room puts both feeds' strips in every rack, at the rack's PDU cells (pure)."""
    placed = room.reference_room(1.5, "hot", trays=False, labels=False)
    racks = {p.tag: p for p in placed if room.spec(p).family == "rack"}
    strips = [p for p in placed if room.spec(p).family == "pdu_strip"]
    assert len(strips) == 2 * len(racks)
    for st in strips:
        host = racks[st.tag.split("/")[0]]
        feed = st.name[-1]
        assert room.world_cells(st) == room.world_cells(host, rack.PDU_CELLS(room.spec(host), feed))


# ---------------------------------------------------------------------------------------------------- measured
@pytest.mark.build
@pytest.mark.parametrize("strip,rk", FIT)
def test_pdu_column_fit(strip, rk):
    """Placed at rack.PDU_CELLS(rack, feed) (every yaw), the strip's world cells are exactly those cells; its render
    bounds lie inside dims.PDU_ENVELOPE (mirrored for B) x the rack's PDU band; with the rack and a fully populated
    server stack (and the other feed's strip) nothing conflicts (the measured free / occupied cells)."""
    rs = _spec(rk)
    e = _entry(strip)
    _entry(rk)
    feed = _feed(strip)
    o = _strip_origin(strip, rk)
    for yaw in range(4):
        xy = (2.0, -2.875) if yaw % 2 == 0 else (2.125, -3.0)               # (its box on the grid)
        R = room.Placed(rk, (*xy, 0.25 + rack.dims(rs)["H"] / 2), yaw)
        cs = rack.PDU_CELLS(rs, feed)
        lc = tuple(sum(room.local_centre(rs, c)[a] for c in cs) / len(cs) for a in range(3))
        assert lc == pytest.approx(o)
        S = room.Placed(strip, tuple(a + b for a, b in zip(R.origin, room.rot(lc, yaw))), yaw)
        assert room.world_cells(S) == room.world_cells(R, cs), yaw
    (bx0, by0, bz0), (bx1, by1, bz1) = _shift(e["render_bounds"], o)
    (ex0, ex1), (ey0, ey1) = DM.PDU_ENVELOPE
    ex0, ex1 = sorted((_sx(strip) * ex0, _sx(strip) * ex1))
    b0, b1 = rack.pdu_band(rs)
    H = rack.dims(rs)["H"]
    assert ex0 - 1e-6 <= bx0 and bx1 <= ex1 + 1e-6, (bx0, bx1, ex0, ex1)
    assert ey0 - 1e-6 <= by0 and by1 <= ey1 + 1e-6, (by0, by1)
    assert b0 - H / 2 - 1e-6 <= bz0 and bz1 <= b1 - H / 2 + 1e-6, (bz0, bz1, b0, b1)
    # a fully populated rack: a 6U server in every slot, both strips
    R = room.Placed(rk, (0.5, 0.625, rack.dims(rs)["H"] / 2), 0)
    placed = [R]
    by_slot = {}
    for c in rack.SLOT_CELLS(rs):
        by_slot.setdefault(c[1], []).append(c)
    for y, cs in sorted(by_slot.items()):
        lc = tuple(sum(room.local_centre(rs, c)[a] for c in cs) / len(cs) for a in range(3))
        placed.append(room.Placed("DC_Srv_Compute", tuple(a + b for a, b in zip(R.origin, lc)), 0))
    other = strip[:-1] + ("B" if feed == "A" else "A")
    for n in (strip, other):
        oo = _strip_origin(n, rk)
        placed.append(room.Placed(n, tuple(a + b for a, b in zip(R.origin, oo)), 0))
    rep = _blocks()
    for p in placed:
        assert p.name in rep, p.name
    assert room.conflicts(placed, rep) == []


@pytest.mark.build
@pytest.mark.parametrize("strip,rk", FIT)
def test_pdu_mounts_on_rack_hints(strip, rk):
    """The strip's Down (plug seat) mount rect lies on the rack's pdu_seat plane and overlaps that hint by >= 50 % of
    the strip's face; its back face (the brackets) lies on the pdu_bracket plane but does not mount (final review I1:
    a Forward mount let a raised strip validate on the bulkhead, Tests/test_pdu_targeting.py)."""
    rs, ss = _spec(rk), _spec(strip)
    feed = _feed(strip)
    o = _strip_origin(strip, rk)
    sh = {n: _shift((lo, hi), o) for n, lo, hi in pdu.strip_collision(ss)["mount"]}
    rh = {n: (lo, hi) for n, lo, hi in rack.collision(rs)["mount"]}
    (slo, shi), (rlo, rhi) = sh["plug_seat"], rh[f"pdu_seat_{feed}"]
    assert slo[2] == pytest.approx(rhi[2], abs=1e-9)                     # the strip's bottom on the plinth top
    ov = max(0.0, min(shi[0], rhi[0]) - max(slo[0], rlo[0])) * max(0.0, min(shi[1], rhi[1]) - max(slo[1], rlo[1]))
    assert ov >= 0.5 * DM.CELL * DM.CELL, ov
    (rlo, rhi) = rh[f"pdu_bracket_{feed}"]
    assert o[1] + DM.CELL / 2 == pytest.approx(rlo[1], abs=1e-9)           # the strip's +y face on the bracket plane
    f = _entry(strip)["placement"]["faces"]
    assert f["Down"]["groups"] == 1
    assert all(f[d]["groups"] == 0 for d in ("Forward", "Backward", "Left", "Right", "Up")), f


@pytest.mark.build
@pytest.mark.parametrize("strip,rk", FIT)
def test_pdu_inlet_meets_receptacle(strip, rk):
    """The measured twist-lock plug (its centre, its bottom) is the rack's measured plinth receptacle on that side
    (its socket's centre and top), within 1 mm."""
    g = _entry(strip)["geometry"]
    o = _strip_origin(strip, rk)
    plug = [a + b for a, b in zip(g["inlet_plug"], o)]
    recs = _entry(rk)["geometry"]["pdu_receptacles"]
    rec = next(r for r in recs if r[0] * _sx(strip) > 0)
    assert plug == pytest.approx(rec, abs=MM), (plug, rec)


@pytest.mark.build
@pytest.mark.parametrize("strip", STRIPS)
def test_pdu_clear_of_rear_doors_and_ups(strip):
    """Nothing of the strip reaches the rear door leaves' plane (DOOR_Y_BACK - 2 mm) or the slot side: its closest
    vertex to the servers stays 5 mm outside the UPS's (measured) widest part inside the slot, its rear bays."""
    g = _entry(strip)["render_bounds"]
    o = _strip_origin(strip, RACKS[42 if "42" in strip else 24][0])
    (x0, y0, _), (x1, y1, _) = _shift(g, o)
    assert max(abs(y0), abs(y1)) <= DM.DOOR_Y_BACK - 0.002
    u = _entry("DC_Srv_UPS")
    bay = max(abs(b["centre"][0]) + b["half"] for b in u["bays"])
    ups = max(u["clearance"]["max_abs_x_in_slot"], bay)
    assert min(abs(x0), abs(x1)) >= ups + 0.005, (x0, x1, ups)


@pytest.mark.build
@pytest.mark.parametrize("strip", STRIPS)
def test_strip_measured_outlets(strip):
    """The built outlet housings' socket faces are where dims says the outlets are (1 mm)."""
    g = _entry(strip)["geometry"]
    want = sorted((round(x, 4), round(z, 4)) for _, _, x, _, z in g["outlets"])
    got = sorted((round(c[0], 4), round(c[2], 4)) for c in g["outlet_housings"])
    assert len(got) == len(want)
    for (a, b), (c, d) in zip(got, want):
        assert a == pytest.approx(c, abs=MM) and b == pytest.approx(d, abs=MM)
    assert all(c[1] == pytest.approx(DM.PDU_OUTLET_FACE_Y - pdu.COL_Y, abs=1e-5) for c in g["outlet_housings"])


@pytest.mark.build
def test_cabinet_shares_rack_interface():
    """As the full rack: the same render footprint (x, the plinth), the same containment rails (roof panels: Tests/
    test_containment.py INROW), the same top-entry brush plates (a Drop lands: Tests/test_tray_build.py LANDINGS), the
    same top-rim and bottom mount rects; the front and back keep the 2.7 cm KEEP_OUT outside the rail band; mounts:
    Forward / Backward only the rail band (one group each), the sides and the bottom fully."""
    c, r = _entry(CAB), _entry("DC_Rack42_Open")
    cg, rg = c["geometry"], r["geometry"]
    for i in (0, 2):
        assert c["render_bounds"][0][i] == pytest.approx(r["render_bounds"][0][i], abs=MM)
        assert c["render_bounds"][1][i] == pytest.approx(r["render_bounds"][1][i], abs=MM)
    assert set(cg["contain_rails"]) == {"front", "back"}
    for side in ("front", "back"):
        assert cg["contain_rails"][side] == pytest.approx(rg["contain_rails"][side], abs=MM), side
    assert len(cg["top_entries"]) == 2
    for a, b in zip(cg["top_entries"], rg["top_entries"]):
        assert a == pytest.approx(b, abs=MM)
    for key in ("down_mount_rects", "up_mount_rects"):        # the plinth bottom; the top rim (Drop collars, labels)
        a, b = sorted(cg[key]), sorted(rg[key])
        assert len(a) == len(b) and all(x == pytest.approx(y) for x, y in zip(a, b)), key
    from dc.style import KEEP_OUT
    yk = 0.625 - KEEP_OUT + 0.0015      # (the rack's corner caps: their Yellow trim stands 1.5 mm proud, dc/style.py)
    assert cg["front_max_y"] <= yk + 1e-6 and cg["back_min_y"] >= -yk - 1e-6
    f = c["placement"]["faces"]
    assert f["Forward"]["groups"] == 1 and f["Backward"]["groups"] == 1
    assert f["Forward"]["coverage"] == pytest.approx(r["placement"]["faces"]["Forward"]["coverage"])
    assert f["Left"]["coverage"] == 1.0 and f["Right"]["coverage"] == 1.0 and f["Down"]["coverage"] == 1.0
    assert c["placement"]["occupied"] == c["placement"]["total"] == 200


@pytest.mark.build
@pytest.mark.parametrize("name", ALL)
def test_pdu_limits_and_materials(name):
    """Keen's limits on every LOD (the cabinet <= 90 %, the project cap, the strips <= 75 % on LOD0), <= 8 materials
    on LOD0, the last LOD the 1-material box; the physics boxes (cabinet 3: the rack pattern; strip 1); no bevel
    hazards."""
    e = _entry(name)
    rows = e["lods"]
    for i, l in enumerate(rows):
        assert l["tris"] <= l["max_tris"], (name, i, l["tris"], l["max_tris"])
        assert l["materials"] <= min(8, l["max_materials"]), (name, i)
    assert rows[-1]["materials"] == 1 and rows[-1]["tris"] <= 32
    assert rows[0]["tris"] <= (0.9 if name == CAB else 0.75) * rows[0]["max_tris"]
    assert e["colliders"]["regular"] == (3 if name == CAB else 1)
    assert not e["bevel_guard"]
    lamps = {m for m in rows[0]["material_names"] if m.startswith("Emissive")}
    assert lamps == {"EmissiveGreen"}                         # static lamps, one lamp material (<= 2)


@pytest.mark.build
@pytest.mark.parametrize("name", ALL)
def test_pdu_breakable_export(name):
    """Breakable through the planned pipeline (guide docs/guides/vanilla-fracture-models.md): the plan's zones, cut
    and capped (FracturedMaterial01), no critical zone, its own Damaged model (the lamps -> EmissiveOffBroken)."""
    m = _manifest(name)
    zones = [z["id"] for z in m["fractured"]["zones"]]
    want = 8 if name == CAB else (3 if "42" in name else 2)
    assert len(zones) == want
    assert integration.keeps_breakable(m) and m["fractured"]["kind"] == "cut" and m["fractured"]["critical"] == []
    parts = m["fractured"]["parts"]
    assert any("FracturedMaterial01" in p for p in parts)
    assert m["damaged"]["lods"] and FR.DAMAGED_SLOTS["EmissiveGreen"] == "EmissiveOffBroken"


@pytest.fixture(scope="module")
def staged():
    integration.write_all()
    return integration.STAGE


def _staged(rel):
    from dc.assetio import read_json
    p = os.path.join(config.STAGE_ASSETS, rel)
    return read_json(p if os.path.exists(p) else os.path.join(config.MOD_ASSETS, rel))


@pytest.mark.build
def test_pdu_staged(staged):
    """Staged as breakable decorative blocks: PCU 5; mount directions All (cabinet) / Down (strips; final review I1); a
    strip's placer AutoRotateFace off; our names; the BreakableBlockComponent kept; the effects dummy at the centre."""
    from dc import clone, names
    from dc.assetio import body
    built = integration.built_names()
    for n in ALL:
        if n not in built or not os.path.exists(os.path.join(config.MODELS_DIR, n, "export.json")):
            pytest.skip(f"{n} not built and exported")
        spec = _spec(n)
        info = clone.entry(spec)["info"]
        bd = body(_staged(info["block_def_file"]))
        want = "All" if n == CAB else "Down"
        assert bd["PCU"] == 5 and bd["MountPointGeneratorSettings"] == {"Directions": want}, n
        assert bd["UIData"]["Name"] == names.NAMES[n][0]
        pl = integration._block_files(spec, "_PlacementDefinition")
        assert len(pl) == 1 and bd["PlacerDefinition"] == integration.own_guid(_staged(pl[0]))
        if n != CAB:
            assert body(_staged(pl[0]))["AutoRotateFace"] is None
        for side in ("Server", "Client"):
            comp = body(_staged(f"{config.NAME}/{n}/{n}_{side}Composition.partialdef"))
            assert integration.BREAKABLE_KEY in comp["Components"]["Keys"], (n, side)
        bmd = body(_staged(info["model_def_file"]))
        assert any((c.get("Value") or {}).get("Name") == "ParticleEffects" for c in bmd["Dummies"]["Changed"])
        assert bmd["DamagedModel"] != bmd["FractureModel"]
