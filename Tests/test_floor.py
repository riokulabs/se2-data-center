"""The raised-floor tiles (dc/floor.py), DC_Floor_{Solid,Perf}_{050,100}.

Pure tests check the builder's numbers (collision, hints, pedestal layout, the deck against dims). The build-marked
tests check the MEASURED blocks (build_report.json geometry / placement / lods, the export manifests):
  * every cell occupied, every face mounts (Up over the whole deck, Down on the base plates, the four sides);
  * the deck flush under the cell-top plane, so a rack placed on the floor sits on it (0..2 mm render gap) and its
    bottom mount lands on the tiles' Up mounts, at every offset from the tile seams;
  * the seams: the same 1 mm inset at every tile edge, inside a 1.0 m block as between blocks, nothing under the
    deck on a shared side plane, only the seal lip reaching it;
  * Keen's limits, and the breakable export: in-plane tile zones (dc/fracture.py _floor; the files
    themselves are checked with every breakable block in test_fracture_refine.py / test_fracture_plan.py).
"""
import json
import os

import pytest

from dc import catalog, config, floor, integration, menu, names, room
from dc import dims as DM

FLOORS = ("DC_Floor_Solid_050", "DC_Floor_Perf_050", "DC_Floor_Solid_100", "DC_Floor_Perf_100")
RACKS = ("DC_Rack42_Open", "DC_Rack24_Open")
MM = 0.001
LOD_MATERIALS = (8, 6, 4, 1)   # our per-LOD material caps (the last LOD: 1)
DECK_MATS = {"PaintedMetalColorable", "PaintedMetalDarker", "MetalPerforationSteel", "PaintedMetalYellow"}
UNDER_MATS = {"BrushedMetal", "MetalDull", "PaintedMetalDarker"}   # stringers, pedestals, rubber pads


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
def test_floor_catalogue_and_staging():
    """The four floor blocks are staged (models, definitions) and wired into the menu / recipe / icon loops
    (BLOCKS)."""
    specs = [catalog.BY_NAME[n] for n in FLOORS]
    assert all(s.family == "floor" for s in specs)
    assert [s.cells for s in specs] == [(2, 1, 2), (2, 1, 2), (4, 1, 4), (4, 1, 4)]
    assert "floor" in catalog.STAGED_ROOM_FAMILIES
    assert all(s in catalog.STAGED and s in catalog.BLOCKS for s in specs)   # wired into the menu
    assert catalog.STAGED[:len(catalog.BLOCKS)] == catalog.BLOCKS
    import build_dc
    assert build_dc.BUILDERS["floor"] is build_dc.build_floor


def test_floor_deck_against_dims():
    """The deck: top 0..1 mm under the cell-top plane (RF_H: one cell), RF_DECK_T thick; the physics boxes meet at
    its underside; the rubber pads and stringers stay under it."""
    assert DM.RF_H == 0.25 and floor.H2 == DM.RF_H / 2
    assert floor.H2 - 0.001 <= floor.DECK_TOP < floor.H2
    assert floor.ZB == pytest.approx(floor.DECK_TOP - DM.RF_DECK_T)
    assert floor.HEAD_TOP + floor.PAD < floor.ZB and floor.STR_TOP < floor.ZB
    assert floor.SKIN_BOT > floor.ZB + floor.LIP and floor.SKIN_TOP < floor.DECK_TOP


@pytest.mark.parametrize("name", FLOORS)
def test_floor_collision_and_hints(name):
    """Two physics boxes (deck, pedestal envelope) that together are the cell box (the intact model's physics; the
    fracture zones are the plan's in-plane tiles, test_floor_breakable_export). Mount hints
    lie on their planes: Up = the whole deck, Down = every base plate, a band on each side."""
    spec = catalog.BY_NAME[name]
    h = floor.half(spec)
    c = floor.collision(spec)
    assert [n for n, _, _ in c["regular"]] == ["deck", "pedestals"]
    (_, dlo, dhi), (_, plo, phi) = c["regular"]
    assert dlo == (-h, -h, floor.ZB) and dhi == (h, h, floor.H2)
    assert plo == (-h, -h, -floor.H2) and phi == (h, h, floor.ZB)
    assert c["occupancy"] == []
    m = {n: (lo, hi) for n, lo, hi in c["mount"]}
    assert m["deck_top"] == ((-h, -h, floor.H2 - floor.HINT_T), (h, h, floor.H2))
    bases = [v for k, v in m.items() if k.startswith("base_")]
    assert len(bases) == len(floor.pedestals(spec))
    for lo, hi in bases:
        assert lo[2] == -floor.H2 and hi[2] - lo[2] == pytest.approx(floor.HINT_T)
        assert min(lo[0], lo[1]) >= -h + 0.03 - 1e-9 and max(hi[0], hi[1]) <= h - 0.03 + 1e-9
    for side, ax, sg in (("left", 0, -1), ("right", 0, 1), ("back", 1, -1), ("front", 1, 1)):
        lo, hi = m[f"side_{side}"]
        assert (hi[ax] if sg > 0 else lo[ax]) == sg * h and hi[ax] - lo[ax] == pytest.approx(floor.HINT_T)
        assert (lo[2], hi[2]) == floor.SIDE_HINT_Z
    assert floor.up_mount_rects(spec) == [[-h, h, -h, h]]


def test_floor_pedestal_layout():
    """A pedestal near every tile corner: PED_INSET inside the block edges (nothing on a shared side plane), shared on
    every internal tile seam (4 in the 0.5 m block, 9 in the 1.0 m); each tile's four screws over a pedestal head."""
    for name, n in (("DC_Floor_Solid_050", 4), ("DC_Floor_Solid_100", 9)):
        spec = catalog.BY_NAME[name]
        h = floor.half(spec)
        peds = floor.pedestals(spec)
        assert len(peds) == len(set(peds)) == n
        assert floor.lines(spec)[0] == pytest.approx(-h + floor.PED_INSET)
        assert h - floor.PED_INSET - floor.BASE >= 0.03     # the base plates' 30 mm (at least) from the side planes
        for t in floor.tiles(spec):
            for x, y in floor.screws(spec, t):
                assert t[0] < x < t[2] and t[1] < y < t[3]
                assert min(max(abs(x - px), abs(y - py)) for px, py in peds) <= floor.HEAD - floor.SCREW_R
    spec = catalog.BY_NAME["DC_Floor_Solid_100"]
    assert (0.0, 0.0) in floor.pedestals(spec)            # the shared head at the four tiles' corner


# ---------------------------------------------------------------------------------------------------- measured
@pytest.mark.build
@pytest.mark.parametrize("name", FLOORS)
def test_floor_fills_and_mounts(name):
    e = _entry(name)
    p = e["placement"]
    assert p["occupied"] == p["total"] == len(floor.tiles(catalog.BY_NAME[name])) * 4
    f = p["faces"]
    assert f["Up"]["groups"] >= 1 and f["Up"]["coverage"] >= 0.9
    assert f["Down"]["groups"] >= 1
    for d in ("Left", "Right", "Forward", "Backward"):
        assert f[d]["groups"] >= 1, (name, d)


@pytest.mark.build
@pytest.mark.parametrize("name", FLOORS)
def test_floor_deck_flush(name):
    e = _entry(name)
    g = e["geometry"]
    top = DM.RF_H / 2
    assert top - 0.001 <= g["deck_top_z"] <= top
    assert e["render_bounds"][1][2] <= top
    assert e["render_bounds"][0][2] == pytest.approx(-top, abs=1e-6)      # the base plates stand on the bottom


@pytest.mark.build
@pytest.mark.parametrize("name", FLOORS)
def test_floor_seams(name):
    """The grid's edges: every tile's top edges 1 mm in (a 2 mm hairline to any neighbour, inside a 1.0 m block the
    same as between blocks), the seal lip reaching the side planes exactly (so neighbours close the seam under the
    hairline, and the LOD0 bounds are the full block), nothing under the deck within 30 mm of a side plane."""
    e = _entry(name)
    g = e["geometry"]
    h = floor.half(catalog.BY_NAME[name])
    assert g["seam_inset"] == pytest.approx(floor.SEAM, abs=1e-4)
    if g["tiles"] > 1:
        assert g["internal_seam"] == pytest.approx(g["seam_inset"], abs=1e-4)
    assert g["lip_reach"] == pytest.approx(0.0, abs=1e-6)
    assert g["under_clear"] >= 0.03
    (x0, y0, _), (x1, y1, _) = e["render_bounds"]
    assert (x0, y0, x1, y1) == pytest.approx((-h, -h, h, h), abs=1e-6)
    assert e["model_size"][:2] == pytest.approx([2 * h, 2 * h], abs=1e-3)


def _area(rects, inside):
    """Fraction of the area of rects (world [x0, x1, y0, y1]) covered by the union inside (5 mm sampling)."""
    step = 0.005
    hit = tot = 0
    for x0, x1, y0, y1 in rects:
        nx, ny = int(round((x1 - x0) / step)), int(round((y1 - y0) / step))
        for i in range(nx):
            x = x0 + (i + 0.5) * step
            for j in range(ny):
                y = y0 + (j + 0.5) * step
                tot += 1
                hit += any(a0 <= x <= a1 and b0 <= y <= b1 for a0, a1, b0, b1 in inside)
    return hit / tot


@pytest.mark.build
@pytest.mark.parametrize("tile", ("050", "100"))
@pytest.mark.parametrize("dy", (0.0, 0.25, 0.5))
@pytest.mark.parametrize("dx", (0.0, 0.25, 0.5))
@pytest.mark.parametrize("rack", RACKS)
def test_floor_under_rack_plinth(rack, dx, dy, tile):
    """A rack placed on a tiled area (solid and perforated tiles in a checkerboard), its box corner (dx, dy) from a
    tile seam: it stands on the floor's top layer, its lowest render vertex 0..2 mm over the deck, and the tiles' Up
    mount hints cover >= 80 % of its bottom mount."""
    t = 0.5 if tile == "050" else 1.0
    tiles = [room.Placed(f"DC_Floor_{'Solid' if (i + j) % 2 else 'Perf'}_{tile}",
                         (t * (i + 0.5), t * (j + 0.5), DM.RF_H / 2))
             for i in range(-2, int(3 / t) + 2) for j in range(-2, int(3 / t) + 2)]
    rs = catalog.BY_NAME[rack]
    H = DM.CELL * rs.cells[1]
    r = room.Placed(rack, (dx + 0.5, dy + 0.625, DM.RF_H + H / 2))
    re = _entry(rack)
    # the rack's bottom layer sits on the floor's top (only) layer, every cell of its footprint on a tile
    cells = room.world_cells(r)
    k0 = min(c[2] for c in cells)
    floor_cells = set().union(*(room.world_cells(p) for p in tiles))
    assert k0 == 1 and {c[2] for c in floor_cells} == {0}
    assert {(i, j, 0) for i, j, k in cells if k == k0} <= floor_cells
    assert not room.conflicts(tiles + [r], {})
    # render gap: the rack's lowest vertex over the deck top of the tiles
    low = r.origin[2] + re["render_bounds"][0][2]
    for p in tiles:
        lo, hi = room.box(p)
        if lo[0] < r.origin[0] + 0.5 and hi[0] > r.origin[0] - 0.5 and lo[1] < r.origin[1] + 0.625 and \
                hi[1] > r.origin[1] - 0.625:
            deck = p.origin[2] + _entry(p.name)["geometry"]["deck_top_z"]
            assert 0.0 <= low - deck <= 2 * MM, (p.name, low - deck)
    # mount coverage: the tiles' Up rects against the rack's Down rects (world plan)
    up = [[a0 + p.origin[0], a1 + p.origin[0], b0 + p.origin[1], b1 + p.origin[1]]
          for p in tiles for a0, a1, b0, b1 in _entry(p.name)["geometry"]["up_mount_rects"]]
    down = [[a0 + r.origin[0], a1 + r.origin[0], b0 + r.origin[1], b1 + r.origin[1]]
            for a0, a1, b0, b1 in re["geometry"]["down_mount_rects"]]
    assert down
    assert _area(down, up) >= 0.8


@pytest.mark.build
@pytest.mark.parametrize("name", FLOORS)
def test_floor_limits(name):
    """Keen's per-LOD triangle and material limits, our material caps (8, 6, 4, 1) and the 70 % triangle
    aim on LOD0."""
    e = _entry(name)
    rows = e["lods"]
    assert len(rows) == 4
    for i, l in enumerate(rows):
        assert l["tris"] <= l["max_tris"], (name, i)
        assert l["materials"] <= l["max_materials"], (name, i)
        assert l["materials"] <= (LOD_MATERIALS[i] if i < len(rows) - 1 else 1), (name, i, l["material_names"])
    assert rows[0]["tris"] <= 0.7 * rows[0]["max_tris"]
    assert rows[-1]["tris"] <= 32


@pytest.mark.build
@pytest.mark.parametrize("name", FLOORS)
def test_floor_breakable_export(name):
    """docs/guides/vanilla-fracture-models.md 10.3 (2) / 10.4: the floor is cut IN PLANE, every zone the
    full thickness (deck AND understructure): 2 halves of the 0.5 m tile, the 1.0 m block's 4 tiles; every zone has
    deck and understructure materials, break faces (FracturedMaterial01, the pedestal plates and stringers the seams
    cut), its own dented Damaged model; no critical zone (structural)."""
    m = _manifest(name)
    spec = catalog.BY_NAME[name]
    zones = [z["id"] for z in m["fractured"]["zones"]]
    assert zones == [f"Fracture_{i:02d}" for i in range(1, len(floor.tiles(spec)) * (2 if spec.cells[0] == 2 else 1)
                                                        + 1)]
    assert integration.keeps_breakable(m) and m["fractured"]["kind"] == "cut" and m["fractured"]["critical"] == []
    by_zone = {}
    for p in m["fractured"]["parts"]:
        g, _, mat = p.partition("-")
        by_zone.setdefault(g.replace("_Hide", ""), set()).add(mat)
    for z in m["fractured"]["zones"]:
        mats = by_zone[z["id"]]
        assert mats & DECK_MATS and mats & UNDER_MATS, (z["id"], mats)          # full thickness
        assert z["lo"][2] <= -floor.H2 + 0.01 and z["hi"][2] >= floor.DECK_TOP - 0.001, z
    assert any("FracturedMaterial01" in v for v in by_zone.values())
    assert m["damaged"]["lods"] and m["damaged"]["dent"]["mean_mm"] > 2.0
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
def test_floor_staged(staged):
    """Staged as a breakable block: PCU 5, mount directions All, our names, the BreakableBlockComponent kept (its
    FractureModel has two fracture colliders)."""
    from dc import clone
    from dc.assetio import body
    built = integration.built_names()
    for n in FLOORS:
        if n not in built:
            pytest.skip(f"{n} not built and exported")
        info = clone.entry(catalog.BY_NAME[n])["info"]
        bd = body(_staged(info["block_def_file"]))
        assert bd["PCU"] == 5 and bd["MountPointGeneratorSettings"] == {"Directions": "All"}
        assert bd["UIData"]["Name"] == names.NAMES[n][0]
        kind = body(_staged(info["kind_file"]))   # a size of a multi-size kind (its own clone kind inert)
        assert (kind["Name"], kind["Description"]) == (menu.kind_text(catalog.BY_NAME[n]) if menu.owns_kind(
            catalog.BY_NAME[n]) else names.NAMES[n])
        comp = body(_staged(f"{config.NAME}/{n}/{n}_ServerComposition.partialdef"))
        assert integration.BREAKABLE_KEY in comp["Components"]["Keys"]
