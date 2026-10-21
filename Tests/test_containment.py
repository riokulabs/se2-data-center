"""The containment roof panels (dc/contain.py), DC_Contain_Roof_{100,150,200}.

Pure tests check the builder's numbers (collision, hints, the bay layout, the up-face rule, the clamps on the rack's
rail pads). The build-marked tests check the MEASURED blocks (build_report.json geometry / placement / lods, the
export manifests) against the measured racks, placed as dc/room.reference_room places them:
  * the roof spans the aisle on the racks' containment rails: its +-y edge mounts overlap the facing racks' rail
    band, its clamps face the rail pads, its x extent is one rack's (every in-row unit built so far);
  * it sits flush with the rack tops and tiles along the row at the 1.0 m pitch (no gap, no overlap);
  * nothing that moves into the aisle reaches it: a KVM popped out of the top slot, rack doors open;
  * faces: nothing mounts Up or Down, the edges mount; Keen's limits; breakable, a fracture zone per bay
    (dc/fracture.py _roof; the files are checked with every breakable block in test_fracture_refine.py).
"""
import json
import math
import os

import pytest

from dc import catalog, config, contain, crac, integration, menu, names, pdu, rack, room
from dc import dims as DM

ROOFS = ("DC_Contain_Roof_100", "DC_Contain_Roof_150", "DC_Contain_Roof_200")
FULL = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear")
INROW = FULL + ("DC_CRAC", "DC_PDU_Cabinet")   # every in-row unit so far (full racks, the CRAC, the PDU cabinet)
DOOR_RACKS = ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear")
MM = 0.001
LOD_MATERIALS = (8, 6, 4, 1)     # per-LOD material caps (the last LOD: 1), as the floor
GLAZING_MATS = {"FrostedGlass", "PaintedMetalColorable"}


def _blocks():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _entry(name):
    blocks = _blocks()
    assert name in blocks, f"{name} not in build_report.json"
    e = blocks[name]
    assert e["placement"]["total"] > 0, f"{name} has no placement data (stub builder?)"
    return e


def _manifest(name):
    p = os.path.join(config.MODELS_DIR, name, "export.json")
    if not os.path.exists(p):
        pytest.skip(f"{name} not exported yet")
    with open(p) as f:
        return json.load(f)


# ---------------------------------------------------------------------------------------------------- pure
def test_roof_catalogue_and_staging():
    specs = [catalog.BY_NAME[n] for n in ROOFS]
    assert all(s.family == "contain_roof" for s in specs)
    assert [contain.width(s) for s in specs] == list(DM.AISLE_WIDTHS)
    assert [room.aisle_width(s) for s in specs] == list(DM.AISLE_WIDTHS)
    assert "contain_roof" in catalog.STAGED_ROOM_FAMILIES
    assert all(s in catalog.STAGED and s in catalog.BLOCKS for s in specs)   # wired into the menu
    import build_dc
    assert build_dc.BUILDERS["contain_roof"] is build_dc.build_contain_roof


@pytest.mark.parametrize("name", ROOFS)
def test_roof_collision_and_hints(name):
    """Two physics slabs, glazing over frame, split at the panes' bed (the intact model's physics; the fracture zones
    are the plan's bays). Mount hints only on the four edge planes, each over the rack's containment-rail band; none
    on Up or Down."""
    spec = catalog.BY_NAME[name]
    w = contain.width(spec)
    b = contain.collision(spec)
    (n0, lo0, hi0), (n1, lo1, hi1) = b["regular"]
    assert (n0, n1) == ("glazing", "frame")
    assert lo0[2] == hi1[2] == contain.ZS and hi0[2] == contain.H2
    for lo, hi in ((lo0, hi0), (lo1, hi1)):
        assert (lo[0], hi[0], lo[1], hi[1]) == (-0.5, 0.5, -w / 2, w / 2)
    assert lo1[2] > -contain.H2 + 0.1                 # the slab is in the cell's top part
    assert b["occupancy"] == []
    rects = contain.edge_mount_rects(spec)
    assert {k: len(v) for k, v in rects.items()} == {"+y": 1, "-y": 1, "+x": 1, "-x": 1}
    band = (-contain.H2 + DM.CONTAIN_RAIL_DZ[0], -contain.H2 + DM.CONTAIN_RAIL_DZ[1])
    for k, ((a0, a1, z0, z1),) in rects.items():
        assert (z0, z1) == pytest.approx(band)
        assert (a0, a1) == ((-0.5, 0.5) if k[1] == "y" else (-w / 2, w / 2))
    for _, lo, hi in b["mount"]:
        assert hi[2] < contain.H2 and lo[2] > -contain.H2      # nothing on the top / bottom planes


@pytest.mark.parametrize("name", ROOFS)
def test_roof_layout(name):
    """0.5 m bays (a pane each, its fire release), mullions on cell boundaries, the clamps at the rail pads."""
    spec = catalog.BY_NAME[name]
    w = contain.width(spec)
    bays = contain.bays(spec)
    assert len(bays) == 2 * round(w / 0.5)
    for y in contain.mullion_ys(spec):
        assert ((y + w / 2) / DM.CELL) == pytest.approx(round((y + w / 2) / DM.CELL))
    assert contain.clamp_xs() == rack.CONTAIN_PADS
    for s, k, (x0, x1, y0, y1) in bays:
        px0, px1, py0, py1 = contain.pane(spec, s, k)
        assert x0 <= px0 < px1 <= x1 and y0 < py0 < py1 < y1
        assert px1 - px0 > 0.4 and py1 - py0 > 0.4


def test_roof_up_face_rule():
    """The flush top never mounts: every top member stays within RAY_FREE of the cell plane it sits on, and the
    panes' top is more than the sampler's 20 mm band under the top plane (se2model.placement.TOL)."""
    from se2model import placement as PL
    assert contain.RAY_FREE == pytest.approx(0.125 - max(abs(a) for a, _ in PL.SAMPLES))
    assert max(contain.CAP_EDGE) < contain.RAY_FREE and max(contain.CAP_END) < contain.RAY_FREE
    assert contain.CAP_LIP < contain.RAY_FREE
    assert contain.H2 - (contain.ZS + contain.PANE_T) > PL.TOL
    assert contain.H2 - 0.001 <= contain.TOP < contain.H2
    assert contain.CLAMP_FACE <= MM and contain.GASKET[0] <= MM


# ---------------------------------------------------------------------------------------------------- coupling
def _world_box(p, lo, hi):
    """A placed block's local box (Blender frame) in world: (lo, hi)."""
    pts = [room.rot((x, y, z), p.yaw) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    pts = [tuple(a + b for a, b in zip(q, p.origin)) for q in pts]
    return tuple(min(q[i] for q in pts) for i in range(3)), tuple(max(q[i] for q in pts) for i in range(3))


def _world_pt(p, v):
    return tuple(a + b for a, b in zip(room.rot(v, p.yaw), p.origin))


def _room_with(unit, w, aisle):
    """The reference room with every in-row unit replaced by `unit` (same 4 x 10 x 5 cell box)."""
    out = []
    for p in room.reference_room(w, aisle, trays=False, labels=False):
        if room.spec(p).family in ("rack", "crac", "pdu_cabinet"):
            p = room.Placed(unit, p.origin, p.yaw, p.tag)
        out.append(p)
    return out


def _pairs(placed, unit):
    """(roof, unit) for every roof and each of the two units under its edges (same x, either row)."""
    roofs = [p for p in placed if room.spec(p).family == "contain_roof"]
    units = [p for p in placed if p.name == unit]
    out = []
    for r in roofs:
        mine = [u for u in units if abs(u.origin[0] - r.origin[0]) < 1e-9]
        assert len(mine) == 2 and {math.copysign(1, u.origin[1]) for u in mine} == {-1.0, 1.0}, r
        out += [(r, u) for u in mine]
    return out


def _unit_rail_hint(u):
    """The unit's containment-rail mount hint on its face toward the aisle (y = 0), in world."""
    s = room.spec(u)
    best = None
    coll = {"crac": crac.collision, "pdu_cabinet": pdu.cabinet_collision}.get(s.family, rack.collision)
    for nm, lo, hi in coll(s)["mount"]:
        if nm.startswith("contain_"):
            b = _world_box(u, lo, hi)
            if best is None or abs(b[0][1] + b[1][1]) < abs(best[0][1] + best[1][1]):
                best = b
    assert best is not None, f"{u.name} has no containment rail"
    return best


def _unit_rail(u, e):
    """The unit's measured containment rail (geometry.contain_rails) on its face toward the aisle, in world."""
    best = None
    for x0, x1, y0, y1, z0, z1 in e["geometry"]["contain_rails"].values():
        b = _world_box(u, (x0, y0, z0), (x1, y1, z1))
        if best is None or min(abs(b[0][1]), abs(b[1][1])) < min(abs(best[0][1]), abs(best[1][1])):
            best = b
    return best


def _roof_edge(r, side_y):
    """The roof's edge mount rect on the side facing the unit at world y sign side_y: (y plane, x0, x1, z0, z1)."""
    spec = room.spec(r)
    w = contain.width(spec)
    e = _entry(r.name)
    (x0, x1, z0, z1), = e["geometry"]["edge_mount_rects"]["+y" if side_y > 0 else "-y"]
    return (r.origin[1] + side_y * w / 2, r.origin[0] + x0, r.origin[0] + x1, r.origin[2] + z0, r.origin[2] + z1)


def _overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def _check_on_rails(unit, w, aisle):
    placed = _room_with(unit, w, aisle)
    ue = _entry(unit)
    for r, u in _pairs(placed, unit):
        sy = 1 if u.origin[1] > 0 else -1
        yp, rx0, rx1, rz0, rz1 = _roof_edge(r, sy)
        (hx0, hy0, hz0), (hx1, hy1, hz1) = _unit_rail_hint(u)
        plane = hy0 if sy > 0 else hy1                      # the unit's face plane toward the aisle
        assert plane == pytest.approx(yp, abs=1e-6), (r.tag, u.tag, plane, yp)
        assert _overlap(rx0, rx1, hx0, hx1) >= 0.6, (r.tag, u.tag)
        assert _overlap(rz0, rz1, hz0, hz1) >= 0.1, (r.tag, u.tag)
        # the measured rail: in front of the roof's edge (2..4 mm gap to the clamps' faces), under its clamps
        (ax0, ay0, az0), (ax1, ay1, az1) = _unit_rail(u, ue)
        rail_face = ay0 if sy > 0 else ay1
        re = _entry(r.name)
        for xc, yf, cz0, cz1 in re["geometry"]["clamps"]["+y" if sy > 0 else "-y"]:
            gap = sy * (rail_face - (r.origin[1] + yf))
            assert 0.001 <= gap <= 0.004, (r.tag, u.tag, gap)
            assert _overlap(r.origin[2] + cz0, r.origin[2] + cz1, az0, az1) >= 0.04, (r.tag, u.tag)
            assert ax0 < r.origin[0] + xc < ax1
        # every clamp lands on one of the unit's rail pads
        pads = sorted(_world_pt(u, (x, 0, 0))[0] for x in rack.CONTAIN_PADS)
        got = sorted(r.origin[0] + c[0] for c in re["geometry"]["clamps"]["+y" if sy > 0 else "-y"])
        assert got == pytest.approx(pads, abs=MM), (r.tag, u.tag)


@pytest.mark.build
@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_roof_spans_aisle_on_rack_rails(w, aisle):
    """Rows of DC_Rack42_Open at the 1.0 m pitch (room.reference_room): each roof's +-y edge mounts overlap the facing
    racks' containment-rail band (>= 0.6 m along x, >= 0.1 m in z), its x extent is one rack's (1 mm)."""
    _check_on_rails("DC_Rack42_Open", w, aisle)
    re, ue = _entry(room.roof_name(w)), _entry("DC_Rack42_Open")
    (rx0, _, _), (rx1, _, _) = re["render_bounds"]
    (ux0, _, _), (ux1, _, _) = ue["render_bounds"]
    assert (rx1 - rx0) == pytest.approx(ux1 - ux0, abs=MM)


@pytest.mark.build
@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
@pytest.mark.parametrize("unit", INROW)
def test_roof_mounts_on_every_inrow_unit(unit, w, aisle):
    """Every 1.0 m roof panel mounts on whatever unit is under it, on both rows."""
    _check_on_rails(unit, w, aisle)


@pytest.mark.build
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_roof_flush_and_tiles_along_row(w):
    """The roof's top is flush with the rack tops (1 mm), and a run at the 1.0 m pitch leaves a 0..2 mm hairline
    between neighbours (never an overlap), its +-y edges 0..1 mm inside the aisle's planes."""
    name = room.roof_name(w)
    re, ue = _entry(name), _entry("DC_Rack42_Open")
    placed = _room_with("DC_Rack42_Open", w, "cold")
    r = next(p for p in placed if p.name == name)
    u = next(p for p in placed if p.name == "DC_Rack42_Open")
    top = r.origin[2] + re["render_bounds"][1][2]
    rack_top = u.origin[2] + ue["render_bounds"][1][2]
    assert 0 <= rack_top - top <= MM, (top, rack_top)
    (x0, y0, _), (x1, y1, _) = re["render_bounds"]
    eps = 1e-9
    assert 0 < 0.5 - x1 <= MM + eps and 0 < x0 + 0.5 <= MM + eps
    assert 0 < w / 2 - y1 <= MM + eps and 0 < y0 + w / 2 <= MM + eps
    roofs = sorted((p for p in placed if p.name == name), key=lambda p: p.origin[0])
    for a, b in zip(roofs, roofs[1:]):
        gap = (b.origin[0] + x0) - (a.origin[0] + x1)
        assert 0 < gap <= 2 * MM + eps, gap
    assert re["geometry"]["top_z"] == pytest.approx(re["render_bounds"][1][2])


@pytest.mark.build
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_roof_clears_kvm_and_rack_doors(w):
    """The roof's underside is >= ZT + ROOF_CLEAR everywhere; over the aisle a KVM popped out of the
    top slot (lid and drawer, every animation fraction) and the rack doors (open at any angle) stay under it.
    Every in-row unit, not only the full racks: the CRAC and the PDU cabinet
    take the rack's top plane, and nothing of theirs reaches into the aisle (their render mesh stays in the box)."""
    from dc import subparts
    name = room.roof_name(w)
    g = _entry(name)["geometry"]
    for unit in INROW:
        s = catalog.BY_NAME[unit]
        d = rack.dims(s)
        placed = _room_with(unit, w, "cold")
        r = next(p for p in placed if p.name == name)
        u = next(p for p in placed if p.name == unit)
        base = u.origin[2] - d["H"] / 2                      # the rack's floor point (local z 0)
        under = r.origin[2] + g["underside_z"]
        assert under >= base + d["ZT"] + DM.ROOF_CLEAR - 1e-9, (unit, under, base + d["ZT"])
        if unit not in FULL:     # in-row units without a slot band: no KVM, no leaves; nothing past the cell planes
            (lo, hi) = _entry(unit)["render_bounds"]
            half_d = DM.CELL * catalog.BY_NAME[unit].cells[2] / 2          # the cell planes (5 cells deep: 0.625)
            assert -half_d <= lo[1] and hi[1] <= half_d, (unit, lo, hi)
            continue
        zc = 0.25 + DM.SLOT_H * (d["nslots"] - 1) + DM.SLOT_H / 2      # the top slot's centre (local z)
        zmax = -9.0
        for i in range(41):
            f = i / 40
            c = subparts.lid_at(f)
            for p, q in [(p, q) for k, p in enumerate(c) for q in c[k + 1:]]:
                for t in range(11):
                    x, y, z = (p[j] + (q[j] - p[j]) * t / 10 for j in range(3))
                    if abs(y) > 0.625:
                        zmax = max(zmax, z + zc)
            dy, _ = subparts.pose(f)
            if subparts.DRAWER_BOX["y_front"] + dy > 0.625:
                zmax = max(zmax, subparts.DRAWER_BOX["z1"] + zc)
        assert base + zmax < under, (unit, base + zmax, under)
        e = _entry(unit)
        if unit in DOOR_RACKS:     # the leaves swing about vertical axes: their z span bounds the whole sweep
            top = max(z1 for _, z1 in e["doors"]["z"].values()) + d["H"] / 2
            assert base + top < under, (unit, base + top, under)


# ---------------------------------------------------------------------------------------------------- measured
@pytest.mark.build
@pytest.mark.parametrize("name", ROOFS)
def test_roof_faces(name):
    """Nothing mounts on Up or Down; the long (Forward / Backward) and short (Left / Right) edges do. Keen's limits."""
    e = _entry(name)
    f = e["placement"]["faces"]
    assert f["Up"]["groups"] == 0 and f["Down"]["groups"] == 0, (f["Up"], f["Down"])
    assert f["Left"]["groups"] >= 1 and f["Right"]["groups"] >= 1
    assert f["Forward"]["groups"] >= 1 and f["Backward"]["groups"] >= 1
    assert f["Forward"]["coverage"] == 1.0 and f["Backward"]["coverage"] == 1.0
    assert e["placement"]["occupied"] == e["placement"]["total"]
    rows = e["lods"]
    for i, l in enumerate(rows):
        assert l["tris"] <= l["max_tris"], (name, i)
        assert l["materials"] <= l["max_materials"], (name, i)
        assert l["materials"] <= (LOD_MATERIALS[i] if i < len(rows) - 1 else 1), (name, i, l["material_names"])
    assert rows[0]["tris"] <= 0.7 * rows[0]["max_tris"]
    assert rows[-1]["tris"] <= 32
    assert e["colliders"]["regular"] == 2
    assert not e["bevel_guard"]


@pytest.mark.build
@pytest.mark.parametrize("name", ROOFS)
def test_roof_measured_parts(name):
    """The measured parts: the top band keeps the up-face rule, the panes' top under the 20 mm band, a clamp at
    every rail pad on both edges, the LED batten across the aisle facing down, under the frame."""
    spec = catalog.BY_NAME[name]
    w = contain.width(spec)
    g = _entry(name)["geometry"]
    assert g["top_band_max_inset"] < contain.RAY_FREE
    assert g["pane_top_z"] < contain.H2 - 0.02
    for side in ("+y", "-y"):
        cl = g["clamps"][side]
        assert sorted(round(c[0], 4) for c in cl) == sorted(rack.CONTAIN_PADS)
        for xc, yf, z0, z1 in cl:
            assert (yf > 0) == (side == "+y") and w / 2 - abs(yf) == pytest.approx(contain.CLAMP_FACE, abs=1e-5)
    x0, x1, y0, y1, zl = g["led"]
    assert y1 - y0 >= w - 0.2 and abs(x0 + x1) < 1e-6
    assert zl < contain.LED_Z[0] and abs(zl - g["frame_underside_z"]) <= 0.001   # hangs to the frame's underside
    assert g["bays"] == len(contain.bays(spec))


@pytest.mark.build
@pytest.mark.parametrize("name", ROOFS)
def test_roof_breakable_export(name):
    """docs/guides/vanilla-fracture-models.md 10.4: split IN PLANE by 0.5 m bays within Keen's table
    for the measured panel (1.0 m aisle: 3, the -y row one zone; 1.5 m: 4; 2.0 m: a zone per bay), each with its pane, caps and frame segment (glazing AND frame materials), break faces
    where the seams cut the beams and caps, no critical zone; its own Damaged model, whose panes map to vanilla's
    WindowGlassBroken (fracture.DAMAGED_SLOTS)."""
    from dc import fracture as FR
    m = _manifest(name)
    zones = [z["id"] for z in m["fractured"]["zones"]]
    assert len(zones) == {"DC_Contain_Roof_100": 3, "DC_Contain_Roof_150": 4, "DC_Contain_Roof_200": 8}[name]
    assert integration.keeps_breakable(m) and m["fractured"]["kind"] == "cut" and m["fractured"]["critical"] == []
    by_zone = {}
    for p in m["fractured"]["parts"]:
        g, _, mat = p.partition("-")
        by_zone.setdefault(g.replace("_Hide", ""), set()).add(mat)
    for z in zones:
        assert GLAZING_MATS <= by_zone[z] and "PaintedMetalDarker" in by_zone[z], (z, by_zone[z])
    assert any("FracturedMaterial01" in v for v in by_zone.values())
    assert FR.DAMAGED_SLOTS["FrostedGlass"] == "WindowGlassBroken" and m["damaged"]["lods"]
    for i, lod in enumerate(m["nonfractured"]["lods"]):
        assert len(lod["materials"]) <= (LOD_MATERIALS[i] if i < len(m["nonfractured"]["lods"]) - 1 else 1)


@pytest.fixture(scope="module")
def staged(stage_package):
    stage_package()
    return integration.STAGE


def _staged(rel):
    from dc.assetio import read_json
    p = os.path.join(config.STAGE_ASSETS, rel)
    return read_json(p if os.path.exists(p) else os.path.join(config.MOD_ASSETS, rel))


@pytest.mark.build
def test_roof_staged(staged):
    """Staged as a breakable block: PCU 5, mount directions All, the placer's AutoRotateFace off, our names, the
    BreakableBlockComponent kept, the effects dummy at the centre, our FrostedGlass / EmissiveWhite slots mapped."""
    from dc import clone
    from dc.assetio import body
    from dc.material_guids import MATERIAL_GUIDS
    built = integration.built_names()
    for n in ROOFS:
        if n not in built or not os.path.exists(os.path.join(config.MODELS_DIR, n, "export.json")):
            pytest.skip(f"{n} not built and exported")
        info = clone.entry(catalog.BY_NAME[n])["info"]
        bd = body(_staged(info["block_def_file"]))
        assert bd["PCU"] == 5 and bd["MountPointGeneratorSettings"] == {"Directions": "All"}
        assert bd["UIData"]["Name"] == names.NAMES[n][0]
        pl = [f for f in integration._block_files(catalog.BY_NAME[n], "_PlacementDefinition")]
        assert len(pl) == 1 and bd["PlacerDefinition"] == integration.own_guid(_staged(pl[0]))
        assert body(_staged(pl[0]))["AutoRotateFace"] is None
        kind = body(_staged(info["kind_file"]))   # a size of a multi-size kind (its own clone kind inert)
        assert (kind["Name"], kind["Description"]) == (menu.kind_text(catalog.BY_NAME[n]) if menu.owns_kind(
            catalog.BY_NAME[n]) else names.NAMES[n])
        comp = body(_staged(f"{config.NAME}/{n}/{n}_ServerComposition.partialdef"))
        assert integration.BREAKABLE_KEY in comp["Components"]["Keys"]
        bmd = body(_staged(info["model_def_file"]))
        assert any((c.get("Value") or {}).get("Name") == "ParticleEffects" for c in bmd["Dummies"]["Changed"])
        assert n in [b.name for b in catalog.BLOCKS]       # in the menu / unlock
    assert {"FrostedGlass", "EmissiveWhite", "FracturedMaterial01"} <= set(MATERIAL_GUIDS)


# =================================================================================================================
# The containment end-of-aisle sliding doors DC_Contain_Door_{100,150,200}
# =================================================================================================================
DOORS = ("DC_Contain_Door_100", "DC_Contain_Door_150", "DC_Contain_Door_200")
H2C = DM.CELL / 2


def _dspec(name):
    return catalog.BY_NAME[name]


def test_door_catalogue_and_staging():
    specs = [_dspec(n) for n in DOORS]
    assert all(s.family == "contain_door" and s.copy_from == "SlidingDoorNarrow250" for s in specs)
    assert [contain.door_w(s) for s in specs] == list(DM.AISLE_WIDTHS) == [room.aisle_width(s) for s in specs]
    assert "contain_door" in catalog.STAGED_ROOM_FAMILIES
    assert all(s in catalog.STAGED and s in catalog.BLOCKS for s in specs)   # wired into the menu
    import build_dc
    assert build_dc.BUILDERS["contain_door"] is build_dc.build_contain_door
    assert contain.ZH + contain.DH == pytest.approx(rack.dims(catalog.BY_NAME["DC_Rack42_Open"])["ZT"])


@pytest.mark.parametrize("name", DOORS)
def test_door_leaves_slide(name):
    """Two leaves, each W/2 + 2 x 15 mm wide, meeting at x = 0 (15 mm past the centre line each); open =
    the closed transform translated by W/2 - 15 mm along x (identity orientation: the vanilla slide), which parks a
    leaf inside its pocket and inside the block (|x| <= W)."""
    spec = _dspec(name)
    W = contain.door_w(spec)
    lv = contain.door_leaves(spec)
    assert [(l.name, l.model, l.side) for l in lv] == [("LeftDoor", "ContainLeafL", -1), ("RightDoor", "ContainLeafR", 1)]
    assert contain.leaf_width(spec) == pytest.approx(W / 2 + 0.03)
    for l in lv:
        d = [b - a for a, b in zip(l.closed.position, l.open.position)]
        assert d == pytest.approx([l.side * (W / 2 - 0.015), 0, 0], abs=1e-9)
        assert l.closed.orientation == l.open.orientation == (0.0, 0.0, 0.0, 1.0)
    closed, opened = contain.leaf_boxes(spec, 0.0), contain.leaf_boxes(spec, 1.0)
    (l0, l1), (r0, r1) = closed["ContainLeafL"], closed["ContainLeafR"]
    assert l1[0] == pytest.approx(0.015) and r0[0] == pytest.approx(-0.015)        # the 30 mm meeting overlap
    for m, (lo, hi) in opened.items():
        assert max(abs(lo[0]), abs(hi[0])) == pytest.approx(W, abs=1e-9)          # nominal box to the block's end
        assert min(abs(lo[0]), abs(hi[0])) == pytest.approx(W / 2 - 0.03)          # leading edge behind the post


@pytest.mark.parametrize("name", DOORS)
def test_door_closed_blocks_opening(name):
    """The closed leaves' collision boxes cover the opening (|x| <= W/2 - 0.01, 0.02 m over the floor .. ZT - 0.02);
    the open leaves' boxes lie inside the pocket frames' physics boxes (nothing of a parked leaf in the aisle)."""
    spec = _dspec(name)
    W = contain.door_w(spec)
    closed = list(contain.leaf_boxes(spec, 0.0).values())
    xs = sorted((lo[0], hi[0]) for lo, hi in closed)
    assert xs[0][0] <= -(W / 2 - 0.01) and xs[-1][1] >= W / 2 - 0.01 and xs[0][1] >= xs[1][0]   # no gap between
    for lo, hi in closed:
        assert lo[2] <= -contain.DH + 0.02 and hi[2] >= contain.ZH - 0.02
        assert hi[1] - lo[1] >= 0.04
    pockets = {nm: (lo, hi) for nm, lo, hi in contain.door_collision(spec)["regular"] if nm.startswith("pocket")}
    for m, (lo, hi) in contain.leaf_boxes(spec, 1.0).items():
        plo, phi = pockets["pocket_l" if m.endswith("L") else "pocket_r"]
        assert all(plo[i] - 1e-9 <= lo[i] and hi[i] <= phi[i] + 1e-9 for i in range(3)), (m, lo, hi, plo, phi)


@pytest.mark.parametrize("name", DOORS)
def test_door_collision_and_hints(name):
    """<= 4 physics boxes (header, pocket frames, sill) that together reach every face and touch each other (Havok
    connects fracture colliders within 0.1 m); mount hints exactly: -Y back plates over the pockets, the header band
    on -Y and +Y, Up, Down. The detector covers the opening (W/2, ZT/2, 0.125)."""
    spec = _dspec(name)
    W = contain.door_w(spec)
    b = contain.door_collision(spec)
    reg = b["regular"]
    assert [n for n, *_ in reg] == ["header", "pocket_l", "pocket_r", "sill"]

    def gap(a, c):
        return max(max(a[1][i], c[1][i]) - min(a[2][i], c[2][i]) - (a[2][i] - a[1][i]) - (c[2][i] - c[1][i])
                   for i in range(3))
    seen, todo = {0}, [0]
    while todo:
        i = todo.pop()
        for j in range(len(reg)):
            if j not in seen and gap(reg[i], reg[j]) <= 1e-9:
                seen.add(j)
                todo.append(j)
    assert seen == set(range(len(reg)))
    for _, lo, hi in reg:
        assert all(-c - 1e-9 <= v for v, c in zip(lo, (W, H2C, contain.DH)))
        assert all(v <= c + 1e-9 for v, c in zip(hi, (W, H2C, contain.DH)))
    names = [n for n, *_ in b["mount"]]
    assert set(names) == {"back_l", "back_r", "header_back", "header_front", "top", "sill_down", "pocket_down_l",
                          "pocket_down_r"}
    backs = contain.back_mount_rects(spec)
    assert sorted(tuple(r[:2]) for r in backs) == [(-W, -W / 2), (W / 2, W)]
    hr = contain.header_rects(spec)
    for k in ("-y", "+y"):
        (x0, x1, z0, z1), = hr[k]
        assert (x0, x1, z0, z1) == pytest.approx((-W, W, contain.ZH, contain.DH))
    c, half = contain.detector_box(spec)
    assert half == pytest.approx((W / 2, (contain.ZH + contain.DH) / 2, 0.125), abs=MM)
    assert c[0] == pytest.approx(0.125) and c[2] == pytest.approx(0.0)


def _door_world_rect_x(p, x0, x1, z0, z1, y):
    """A door-local rect on the plane y (x0..x1, z0..z1) in world: (plane world x, (wy0, wy1), (wz0, wz1))."""
    a = _world_pt(p, (x0, y, z0))
    b = _world_pt(p, (x1, y, z1))
    assert abs(a[0] - b[0]) < 1e-9
    return a[0], tuple(sorted((a[1], b[1]))), tuple(sorted((a[2], b[2])))


def _doors_and_ends(placed):
    """(door, end unit) for both doors of the room: the in-row unit whose side face the door's -Y plane meets."""
    doors_ = [p for p in placed if room.spec(p).family == "contain_door"]
    units = [p for p in placed if room.spec(p).family in ("rack", "crac", "pdu_cabinet")]
    out = []
    for d in doors_:
        xs = sorted({u.origin[0] for u in units})
        xe = xs[0] if d.origin[0] < xs[0] else xs[-1]
        ends = [u for u in units if u.origin[0] == xe]
        assert len(ends) == 2
        out += [(d, u) for u in ends]
    return out


@pytest.mark.build
@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_door_on_both_ends_and_aisles(w, aisle):
    """A door at either end of the aisle, cold (rack fronts) or hot (rack backs): its -Y back-plate
    mount rects over each pocket lie on the end unit's side plane and overlap that side face by >= 0.25 m^2; the
    measured frame stays >= 1 mm off the side plane (frame_min_y), and the end racks' sides mount (100 %)."""
    name = room.door_name(w)
    g = _entry(name)["geometry"]
    assert g["frame_min_y"] >= -H2C + 0.001 - 1e-9
    assert g["frame_max_y"] <= H2C - 0.001 + 1e-9
    for unit in ("DC_Rack42_SplitFront", "DC_Rack42_Open"):
        ue = _entry(unit)
        assert ue["placement"]["faces"]["Left"]["groups"] >= 1 and ue["placement"]["faces"]["Right"]["groups"] >= 1
        placed = _room_with(unit, w, aisle)
        pairs = _doors_and_ends(placed)
        assert len(pairs) == 4
        for d, u in pairs:
            (ulo, uhi) = room.box(u)
            face_x = uhi[0] if d.origin[0] > u.origin[0] else ulo[0]
            # the rack's own side mount hint on that face (side_left / side_right, the full side panel band)
            sides = [_world_box(u, lo, hi) for nm, lo, hi in rack.collision(room.spec(u))["mount"]
                     if nm.startswith("side_")]
            (slo, shi), = [b_ for b_ in sides if min(abs(b_[0][0] - face_x), abs(b_[1][0] - face_x)) < 1e-6]
            best = 0.0
            for x0, x1, z0, z1 in g["back_mount_rects"]:
                px, (y0, y1), (wz0, wz1) = _door_world_rect_x(d, x0, x1, z0, z1, -H2C)
                assert px == pytest.approx(face_x, abs=1e-9), (d.tag, u.tag)
                a = max(0.0, _overlap(y0, y1, slo[1], shi[1])) * max(0.0, _overlap(wz0, wz1, slo[2], shi[2]))
                best = max(best, a)
            assert best >= 0.25, (d.tag, u.tag, best)
            # the measured frame does not reach the side plane
            near = d.origin[0] + (-g["frame_min_y"] if d.yaw == 1 else g["frame_min_y"])
            assert abs(near - face_x) >= 0.001 - 1e-9, (d.tag, near, face_x)


@pytest.mark.build
@pytest.mark.parametrize("rk", DOOR_RACKS)
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_door_pockets_clear_rack_leaves(w, rk):
    """Cold aisles (the racks' front leaves swing into the aisle): every point of the end racks' leaves over their
    0..85 deg sweep (the measured plan hulls, dc/doors.py) stays > 5 mm from the door frame and its leaves (open or
    closed): the whole door lies beyond the row-end plane, its nearest point frame_min_y / the leaves' -LEAF_HT."""
    from dc import doors as RD
    name = room.door_name(w)
    g = _entry(name)["geometry"]
    near_local = min(g["frame_min_y"], *(l["bounds"][0][1] for l in g["leaves"].values()))
    e = _entry(rk)
    hulls = {m: [tuple(p) for p in h] for m, h in e["doors"]["hulls"].items()}
    spec = catalog.BY_NAME[rk]
    placed = _room_with(rk, w, "cold")
    worst = 9.0
    for d, u in _doors_and_ends(placed):
        sgn = 1 if d.origin[0] > u.origin[0] else -1                    # +1: the east door (beyond the row's +x end)
        door_edge = d.origin[0] + (near_local if d.yaw == 3 else -near_local)
        for lf in RD.leaves(spec):
            for k in range(35):
                P = RD.placed_hull(lf, hulls[lf["model"]], RD.swing_yaw(lf, k / 34))
                for x, y in P:
                    wx = _world_pt(u, (x, y, 0.0))[0]
                    worst = min(worst, sgn * (door_edge - wx))
    assert worst > 0.005, worst


@pytest.mark.build
@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_roof_meets_door_header(w, aisle):
    """The roof run's end panels mount on the door headers: the header's -Y rect over the opening lies on the roof's
    +-x edge plane and overlaps the roof's edge mount rect by >= 0.7 W x 0.2 m^2 (the roof's end gasket band)."""
    dname, rname = room.door_name(w), room.roof_name(w)
    g = _entry(dname)["geometry"]
    re = _entry(rname)
    placed = _room_with("DC_Rack42_Open", w, aisle)
    roofs = sorted((p for p in placed if p.name == rname), key=lambda p: p.origin[0])
    for d in (p for p in placed if p.name == dname):
        r = roofs[0] if d.origin[0] < roofs[0].origin[0] else roofs[-1]
        side = "-x" if d.origin[0] < r.origin[0] else "+x"
        (y0, y1, z0, z1), = re["geometry"]["edge_mount_rects"][side]
        plane = r.origin[0] + (-0.5 if side == "-x" else 0.5)
        ry, rz = (r.origin[1] + y0, r.origin[1] + y1), (r.origin[2] + z0, r.origin[2] + z1)
        (x0, x1, hz0, hz1), = g["header_rects"]["-y"]
        x0, x1 = max(x0, -w / 2), min(x1, w / 2)                         # the part over the opening
        px, (dy0, dy1), (dz0, dz1) = _door_world_rect_x(d, x0, x1, hz0, hz1, -H2C)
        assert px == pytest.approx(plane, abs=1e-9)
        a = _overlap(dy0, dy1, *ry) * _overlap(dz0, dz1, *rz)
        assert a >= 0.7 * w * 0.2, (d.tag, a)


@pytest.mark.build
@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_door_on_floor_under_roof(w, aisle):
    """Over the floor: the door stands on the raised floor's top plane (its render bottom 0..1 mm above it) with
    tiles under its whole footprint; under the roof: its header is the roof band (ZT .. rack top) and its top is
    flush with the roof panels' top (1 mm)."""
    dname, rname = room.door_name(w), room.roof_name(w)
    de = _entry(dname)
    placed = room.reference_room(w, aisle, trays=False, labels=False)
    tiles = [p for p in placed if room.spec(p).family == "floor"]
    for d in (p for p in placed if p.name == dname):
        lo, hi = room.box(d)
        assert lo[2] == pytest.approx(room.STACK["floor_top"])
        assert 0 <= d.origin[2] + de["render_bounds"][0][2] - room.STACK["floor_top"] <= MM
        area = 0.0
        for t in tiles:
            tlo, thi = room.box(t)
            assert thi[2] == pytest.approx(room.STACK["floor_top"])
            a = _overlap(lo[0], hi[0], tlo[0], thi[0])
            b = _overlap(lo[1], hi[1], tlo[1], thi[1])
            if a > 0 and b > 0:
                area += a * b
        assert area == pytest.approx((hi[0] - lo[0]) * (hi[1] - lo[1]))
        assert d.origin[2] + contain.ZH == pytest.approx(room.STACK["roof"][0])
        assert hi[2] == pytest.approx(room.STACK["roof"][1])
        if os.path.exists(config.REPORT_PATH) and _blocks().get(rname, {}).get("placement", {}).get("total"):
            re = _entry(rname)
            r = next(p for p in placed if p.name == rname)
            assert abs((d.origin[2] + de["render_bounds"][1][2]) - (r.origin[2] + re["render_bounds"][1][2])) <= MM


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_door_faces_and_limits(name):
    """Faces: +Y mounts only on the header band (one group: the aisle sign), -Y on the back plates and the header,
    Up and Down fully; Keen's limits on every LOD of the frame and both leaves, <= 8 materials per model."""
    e = _entry(name)
    f = e["placement"]["faces"]
    assert f["Forward"]["groups"] == 1 and f["Forward"]["coverage"] == pytest.approx(0.1)       # the header row
    assert f["Backward"]["coverage"] >= 0.5 and f["Up"]["coverage"] == 1.0 and f["Down"]["coverage"] == 1.0
    for i, l in enumerate(e["lods"]):
        assert l["tris"] <= l["max_tris"] and l["materials"] <= l["max_materials"], (name, i)
        assert l["materials"] <= 8
    assert e["lods"][0]["tris"] <= 0.7 * e["lods"][0]["max_tris"]
    assert e["lods"][-1]["tris"] <= 32
    assert e["colliders"]["regular"] == 4 and not e["bevel_guard"]
    for m in contain.LEAF_MODELS:
        rows = e["subparts"]["models"][m]["lods"]
        for i, l in enumerate(rows):
            assert l["tris"] <= l["max_tris"] and l["materials"] <= min(8, l["max_materials"]), (name, m, i)
        assert "WindowGlassThin" in rows[0]["material_names"]


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_door_measured_leaves(name):
    """The measured leaves: inside their collision box across (x) and through the door (within the jamb slot), the
    carriages up into the header track; open, inside the block; the closed pair overlaps at the centre line."""
    spec = _dspec(name)
    W = contain.door_w(spec)
    g = _entry(name)["geometry"]
    for m, l in g["leaves"].items():
        (lo, hi), (clo, chi) = l["bounds"], l["collision"]
        assert clo[0] - 1e-6 <= lo[0] and hi[0] <= chi[0] + 1e-6
        assert max(abs(lo[1]), abs(hi[1])) < contain.SLOT + 0.001          # rollers / axles: inside the track walls
        (clo2, chi2) = l["closed"]                                         # the block frame (origin on the track)
        assert clo2[2] >= -contain.DH + 0.0025 and chi2[2] > contain.ZH     # guide shoes in the sill, carriages up
        (olo, ohi) = l["open"]
        assert max(abs(olo[0]), abs(ohi[0])) <= W - 0.001
    assert g["opening_clear"][1] - g["opening_clear"][0] >= W - 2 * (contain.POST_IN + 0.006)   # caps: 5.5 mm proud


@pytest.mark.build
@pytest.mark.parametrize("name", DOORS)
def test_door_breakable_export(name):
    """docs/guides/vanilla-fracture-models.md applied through the shared pipeline (dc/fracture.py _door;
    recognition, connectivity, cap UVs, hull fill and the Damaged model's parity are test_fracture_refine.py's,
    on the files): the 8 zones of the plan, the door's frame members cut and capped at every seam (each pocket piece,
    the lintel and the sill carry FracturedMaterial01 break faces), the 7 frame zones critical, the closed leaves
    supported by the lintel, its own dented Damaged model, and each leaf model its own box collider."""
    from dc import fracture as FR
    spec = _dspec(name)
    m = _manifest(name)
    p = FR.plan(spec, contain.door_collision(spec))
    zones = [z["id"] for z in m["fractured"]["zones"]]
    assert zones == p.ids() and m["fractured"]["kind"] == "cut"
    assert m["fractured"]["critical"] == p.critical() == zones[:7]
    assert m["fractured"]["supporting"] == {"LeftDoorClosed": "Fracture_01", "RightDoorClosed": "Fracture_01"}
    assert integration.keeps_breakable(m)
    parts = m["fractured"]["parts"]
    for z in zones:                                                                # every zone has break faces
        assert f"{z}-FracturedMaterial01" in parts, z
    assert m["fractured"]["caps"][0][0] > 0
    dm = m["damaged"]
    assert sorted(dm["collision"]["nodes"]) == sorted(zones)
    assert 4.0 <= dm["dent"]["mean_mm"] <= 15.0 and dm["dent"]["max_mm"] <= 50.0
    for sub in contain.LEAF_MODELS:
        c = m["subparts"][sub]["collision"]
        assert c["colliders"] == 1 and c["file"].endswith("_collision.gltf")
        lo, hi = contain.leaf_box(spec)
        assert c["boxes"][0][1:] == [[round(v, 5) for v in lo], [round(v, 5) for v in hi]]


@pytest.mark.parametrize("name", DOORS)
def test_door_fracture_plan(name):
    """The zone plan (pure, dc/fracture.py _door): 8 zones (the lintel, three pieces per pocket tower, the sill), like
    the vanilla door frame's 8; the plan boxes lie inside the block and connect within 0.1 m; health (volume,
    criticals x 2) is balanced: every frame zone 5..70 % (the 8 mm threshold is the one cheap piece); the criticals
    stay in the largest island whatever single other zone dies; the closed leaves' dummies sit in their supporting
    zone (the lintel); the -Y back-plate mounts are owned by the pocket zones (the boxes reach that face)."""
    from dc import fracture as FR
    spec = _dspec(name)
    W = contain.door_w(spec)
    p = FR.plan(spec, contain.door_collision(spec))
    zones = [(z.label, *z.hull) for z in p.zones]
    assert len(zones) == 8 and zones[0][0].startswith("lintel") and zones[-1][0].startswith("threshold")
    for _, lo, hi in zones:
        assert all(-c - 1e-9 <= v for v, c in zip(lo, (W, H2C, contain.DH)))
        assert all(v <= c + 1e-9 for v, c in zip(hi, (W, H2C, contain.DH)))

    def gap(a, b):
        return max(max(a[1][i], b[1][i]) - min(a[2][i], b[2][i]) - (a[2][i] - a[1][i]) - (b[2][i] - b[1][i])
                   for i in range(3))

    def islands(alive):
        left, out = set(alive), []
        while left:
            todo, comp = [left.pop()], set()
            while todo:
                i = todo.pop()
                comp.add(i)
                for j in list(left):
                    if gap(zones[i], zones[j]) <= 0.1:
                        left.discard(j)
                        todo.append(j)
            out.append(comp)
        return out
    assert len(islands(range(len(zones)))) == 1
    ci = {i for i, z in enumerate(p.zones) if z.critical}
    assert len(ci) == 7 and len(zones) - 1 not in ci
    vol = [(hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]) * (2 if i in ci else 1)
           for i, (_, lo, hi) in enumerate(zones)]
    shares = [v / sum(vol) for v in vol]
    for i, sh in enumerate(shares[:-1]):
        assert 0.05 <= sh <= 0.70, (zones[i][0], sh)
    for dead in range(len(zones)):
        rest = [i for i in range(len(zones)) if i != dead]
        big = max(islands(rest), key=lambda c: sum(vol[i] for i in c))
        assert (ci - {dead}) <= big, (zones[dead][0], big)
    # the closed leaves' dummies (block frame, back from game) inside the lintel's box (Fracture_01), its supporter
    from dc import doors as RD
    sh_ = RD.shift(spec)
    (_, llo, lhi) = zones[0]
    for lf in contain.door_leaves(spec):
        assert p.manifest()["supporting"][lf.name + "Closed"] == "Fracture_01"
        gx, gy, gz = lf.closed.position
        x, y, z = gx - sh_[0], -(gz - sh_[2]), gy - sh_[1]
        assert all(llo[i] - 1e-6 <= v <= lhi[i] + 1e-6 for i, v in enumerate((x, y, z))), (lf.name, (x, y, z))
    for x0, x1, z0, z1 in contain.back_mount_rects(spec):
        for _, lo, hi in zones[1:-1]:
            if lo[0] <= (x0 + x1) / 2 <= hi[0] and lo[1] <= -H2C + 0.001:
                break
        else:
            raise AssertionError(("back mounts not owned", x0, x1))


@pytest.mark.build
def test_door_definitions(staged):
    """Staged: the leaf subparts' models carry a collision model; each leaf's Closed / Open dummies (the clone's own
    types) differ by a pure x translation of W/2 - 15 mm (identity orientation); ConditionalSubParts spawns each leaf
    at its Closed type; OpeningDuration 1.0 s; the detector box = (W/2, ZT/2, 0.125); a DoorUse box on each leaf;
    PCU 150, mounts All, breakable kept with our critical fractures, the vanilla frame UseDoor boxes gone."""
    from dc import clone
    from dc.assetio import body, read_json
    built = integration.built_names()
    for n in DOORS:
        if n not in built or not os.path.exists(os.path.join(config.MODELS_DIR, n, "export.json")):
            pytest.skip(f"{n} not built and exported")
        spec = _dspec(n)
        W = contain.door_w(spec)
        info = clone.entry(spec)["info"]
        bd = body(_staged(info["block_def_file"]))
        assert bd["PCU"] == 150 and bd["MountPointGeneratorSettings"] == {"Directions": "All"}
        assert bd["UIData"]["Name"] == names.NAMES[n][0]
        bmd = body(_staged(info["model_def_file"]))
        dm = {c["Value"]["Name"]: c["Value"] for c in bmd["Dummies"]["Changed"]}
        assert "TerminalFront01" not in dm and "TerminalBack01" not in dm
        cs = body(_staged(integration._block_files(spec, "_Client_ConditionalSubPartsDefinition")[0]))["SubParts"]
        assert len(cs) == 2
        for lf in contain.door_leaves(spec):
            c, o = dm[lf.name + "Closed"], dm[lf.name + "Open"]
            pc, po = c["Transform"]["Transform"], o["Transform"]["Transform"]
            d = [po["Position"][k] - pc["Position"][k] for k in "XYZ"]
            assert d == pytest.approx([lf.side * (W / 2 - 0.015), 0, 0], abs=1e-6)
            assert pc["Orientation"] == po["Orientation"] == {"X": 0, "Y": 0, "Z": 0, "W": 1}
            sl = body(_staged(integration._leaf_rel(spec, lf.name, integration.LEAF_FILES[3])))
            assert (sl["ClosedPositionDummy"], sl["OpenPositionDummy"]) == (c["Type"], o["Type"])
            assert cs[c["Type"]] == integration.own_guid(_staged(integration._leaf_rel(spec, lf.name,
                                                                                       integration.LEAF_FILES[1])))
            mc = body(_staged(integration._leaf_rel(spec, lf.name, integration.LEAF_FILES[4])))
            assert [x["Value"]["Name"] for x in mc["Dummies"]] == ["DoorUse"]
            assert mc["Dummies"][0]["Value"]["Type"] == integration.USE_DOOR
            mrel = f"{config.NAME}/{n}/Models/Subparts/{lf.model}/{n}_{lf.model}.model"
            assert integration.asset_id(mrel) == mc["Model"][3:]
            ma = body(read_json(os.path.join(config.STAGE_ASSETS, mrel)))
            col = ma["CollisionShapesAsset"]["AssetReference"]
            assert col and col.startswith("{G}")
            folder = os.path.join(config.STAGE_ASSETS, os.path.dirname(mrel))
            ids = {integration.asset_id(f"{os.path.dirname(mrel)}/{f}"): f for f in os.listdir(folder)
                   if not f.endswith(".meta")}
            assert ids[col[3:]].endswith("_collision.gltf")
        det = dm[integration.DETECTOR]
        half = body(_staged(integration._block_files(spec, "_DoorwayObstacleEntityDetectorDefinition")[0]))[
            "QueryHalfExtents"]
        assert [half[k] for k in "XYZ"] == pytest.approx([W / 2, 1.125, 0.125], abs=MM)
        assert [det["Scale"][k] for k in "XYZ"] == pytest.approx([W, 2.25, 0.25], abs=MM)
        ds = body(_staged(integration._block_files(spec, "_DoorServerDefinition")[0]))
        assert ds["OpeningDuration"] == 10000000
        br = body(_staged(integration._block_files(spec, "_BreakableBlockDefinition")[0]))
        assert [a["Id"] for a in br["CriticalFractures"]["Added"]] == integration.manifest(spec)["fractured"]["critical"]
        for lf in contain.door_leaves(spec):
            assert dm[lf.name + "Closed"]["SupportingFracture"] == {"Id": "Fracture_01"}   # the lintel
            assert dm[lf.name + "Open"]["SupportingFracture"] is None
        assert bmd["DamagedModel"] not in (bmd["FractureModel"], bmd["Model"])
        drel = f"{config.NAME}/{n}/Models/Damaged/{n}_Damaged.model"
        assert bmd["DamagedModel"][3:] == integration.asset_id(drel)
        comp = body(_staged(f"{config.NAME}/{n}/{n}_ServerComposition.partialdef"))
        assert integration.BREAKABLE_KEY in comp["Components"]["Keys"]
        sw = body(_staged(integration._block_files(spec, "_BlockMaterialSwapperDefinition")[0]))
        m = integration.manifest(spec)
        assert sw["WorkingReplacementsMeshParts"] == [] and len(sw["WorkingReplacementModels"]) == 3
        assert n in [b.name for b in catalog.BLOCKS]          # in the menu / unlock / recipe
        assert m["subparts"]
    assert "WindowGlassThin" in __import__("dc.material_guids", fromlist=["x"]).MATERIAL_GUIDS
