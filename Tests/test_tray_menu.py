"""The cable trays' build menu (dc/menu.py), names (dc/names.py), costs (dc/recipes.py) and icons.

Menu (plan Decision 11): one "Data Center" subcategory tile per cable density, "Cable Trays: Empty / Low / Moderate /
Full", each with one kind per shape in menu.TRAY_ORDER, and "Cable Tray Supports" with the Rods and the Chute. The two
straights are the two sizes of one kind, the three rod hangers the three sizes of another."""
import itertools
import os

import pytest

try:
    from PIL import Image
except ImportError:   # the icon pixel checks need Pillow: they FAIL without it (see _need_pillow), never skip silently
    Image = None

from dc import catalog, clone, config, integration, menu, names, recipes, tray_plan
from dc.assetio import read_json
from test_task10 import UI, alpha_bbox, png_info, report

TRAYS = [b for b in catalog.BLOCKS if b.family in ("tray", "trayrods")]
DENSITY_GROUPS = [f"tray_{d}" for d in catalog.TRAY_DENSITIES]


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


def stage(rel):
    return read_json(os.path.join(config.STAGE_ASSETS, rel))


def block_def(b):
    return stage(clone.entry(b)["info"]["block_def_file"])["$Value"]["Manipulator"]


def kind_def(b):
    return stage(clone.entry(b)["info"]["kind_file"])["$Value"]


# ---------------------------------------------------------------------------------------------- menu
def test_tray_groups(staged):
    """The five tray groups are staged in the Data Center subcategory; each density group lists exactly its shapes in
    TRAY_ORDER (Empty has no Drop and no Reducer), the supports group Rods then Chute; every tray kind is in exactly
    one group; no tray kind stays in a vanilla group (Structural > Walls, Trusses)."""
    sub = stage(menu.SUBCATEGORY["file"])["$Value"]
    groups = {g: stage(menu.GROUPS[g]["file"])["$Value"] for g in DENSITY_GROUPS + ["traysupport"]}
    for g, v in groups.items():
        assert v["Name"] == menu.GROUPS[g]["name"]
        assert [s["Value"] for s in v["Subcategories"]] == [sub["Guid"]]
    assert [groups[g]["Name"] for g in DENSITY_GROUPS] == [f"Cable Trays: {d}" for d in catalog.TRAY_DENSITIES]
    assert groups["traysupport"]["Name"] == "Cable Tray Supports"
    guid_to_group = {v["Guid"]: g for g, v in groups.items()}
    listed = {g: [] for g in groups}   # group -> [(priority, kind key)]
    for b in TRAYS:
        k = kind_def(b)
        if not menu.owns_kind(b):
            assert k["BlockGroups"] == [] and k["OrderingPriority"] == 0, b.name
            continue
        gs = [guid_to_group.get(e["Value"]) for e in k["BlockGroups"]]
        assert len(gs) == 1 and gs[0] in groups, f"{b.name}: kind in {gs}, want exactly one tray group"
        listed[gs[0]].append((k["OrderingPriority"], "Straight" if b.variant.startswith("Straight") else b.variant))
    want_low = list(menu.TRAY_ORDER)
    want = {"tray_Empty": [s for s in want_low if s not in ("Drop", "Reducer")], "tray_Low": want_low,
            "tray_Moderate": want_low, "tray_Full": want_low, "traysupport": list(menu.SUPPORT_ORDER)}
    for g, kinds in listed.items():
        prios = [p for p, _ in kinds]
        assert len(set(prios)) == len(prios) and 0 not in prios, (g, kinds)
        assert [s for _, s in sorted(kinds)] == want[g], g
    # every tray block's kind (via its owner) sits in the tile its catalogue data says, derived here independently of
    # menu.group: the rods and the Chute in the supports, every other piece in its own density's tile
    for b in TRAYS:
        want_group = "traysupport" if (b.family == "trayrods" or b.variant == "Chute") else f"tray_{b.density}"
        gs = [guid_to_group.get(e["Value"]) for e in kind_def(catalog.BY_NAME[_owner_name(b)])["BlockGroups"]]
        assert gs == [want_group], (b.name, gs)


def _owner_name(b):
    """The expected kind owner, written out from the design (not menu.kind_owner)."""
    if b.variant == "StraightS":
        return f"DC_Tray_StraightL_{b.density}"
    if b.family == "trayrods":
        return "DC_TrayRods_100"
    return b.name


def test_vanilla_tile_sort_on_staged_groups(staged):
    """Replay SubcategoryDefinitionPostProcessor.SortBlockGroupsByRules on the STAGED groups (single-kind groups last,
    then Order with 0 = last, then name, then Guid). A group's kinds come from the staged kinds' BlockGroups (the
    post-processor inserts them: BlockGroupDefinitionPostProcessor), counting kinds that hold blocks."""
    sub = stage(menu.SUBCATEGORY["file"])["$Value"]
    groups = [stage(v["file"])["$Value"] for v in menu.GROUPS.values()]
    groups = [g for g in groups if sub["Guid"] in [s["Value"] for s in g["Subcategories"]]]
    n_kinds = {g["Guid"]: 0 for g in groups}
    holding = {clone.entry(b)["info"]["kind_file"] for b in catalog.BLOCKS
               if block_def(b)["BlockKind"] == clone.entry(b)["info"]["kind"]}
    for rel in holding:
        for e in stage(rel)["$Value"]["BlockGroups"]:
            if e["Value"] in n_kinds:
                n_kinds[e["Value"]] += 1
    tiles = sorted(groups, key=lambda g: (n_kinds[g["Guid"]] == 1, g["Order"] if g["Order"] != 0 else 2 ** 31 - 1,
                                          g["Name"], g["Guid"]))
    assert [g["Name"] for g in tiles] == ["Server Racks", "Rack Servers", "Cable Trays: Empty", "Cable Trays: Low",
                                          "Cable Trays: Moderate", "Cable Trays: Full", "Cable Tray Supports",
                                          "Raised Floor", "Room Cooling & Power", "Aisle Containment",
                                          "Signs & Labels"]
    assert all(n_kinds[g["Guid"]] > 1 for g in groups)


def test_tray_group_tiles_ordered(staged):
    """Tiles: racks, servers, Empty, Low, Moderate, Full, supports (the subcategory sorts groups by Order, 0 = last,
    then by name, which alone would put every cable-tray tile first)."""
    orders = [stage(v["file"])["$Value"]["Order"] for v in menu.GROUPS.values()]
    assert list(menu.GROUPS) == ["rack", "server"] + DENSITY_GROUPS + ["traysupport", "floor", "roompower", "contain",
                                                                        "signs"]
    assert 0 not in orders and orders == sorted(orders) and len(set(orders)) == len(orders)


def staged_display_size(b):
    """The game's DisplaySize for a block as staged (CubeBlockDefinition.cs:2069 [2.4: 2045]): DisplaySizeOverride, else the
    largest extent of the occupancy bounds (occupancyData.Bounds, :2399) x 0.25, the occupancy being the measured cell
    box minus its free cells (build_report.json placement)."""
    bd = block_def(b)
    if bd.get("DisplaySizeOverride") is not None:
        return bd["DisplaySizeOverride"]
    lo, hi = catalog.bounds(b)
    free = {tuple(c) for c in report()["blocks"][b.name]["placement"]["free_cells"]}
    cells = [c for c in itertools.product(*(range(lo[i], hi[i] + 1) for i in range(3))) if c not in free]
    return max(max(c[i] for c in cells) - min(c[i] for c in cells) + 1 for i in range(3)) * 0.25


def test_straight_kind_sizes(staged):
    """The Straight kind holds Short and Long (DisplaySize 0.5, 1.5 m); the Rods kind 0.25, 1.0 and 2.0 m
    (DisplaySize 0.5, 1.0, 2.0), read from the staged blocks; every block of a kind points its BlockKind at the
    owner's kind."""
    for d in catalog.TRAY_DENSITIES:
        owner = catalog.BY_NAME[f"DC_Tray_StraightL_{d}"]
        blocks = menu.kind_blocks(owner)
        assert [b.name for b in blocks] == [f"DC_Tray_StraightS_{d}", f"DC_Tray_StraightL_{d}"]
        assert [staged_display_size(b) for b in blocks] == [0.5, 1.5]
    rods = menu.kind_blocks(catalog.BY_NAME["DC_TrayRods_100"])
    assert [b.name for b in rods] == ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200"]
    assert [staged_display_size(b) for b in rods] == [0.5, 1.0, 2.0]
    for b in TRAYS:   # sizes of one kind must differ, or the game would not offer them as sizes
        owner = catalog.BY_NAME[_owner_name(b)]
        sizes = [staged_display_size(x) for x in TRAYS if _owner_name(x) == owner.name]
        assert len(set(sizes)) == len(sizes), owner.name
    for b in TRAYS:
        assert block_def(b)["BlockKind"] == clone.entry(menu.kind_owner(b))["info"]["kind"], b.name
    multi = [b for b in TRAYS if menu.owns_kind(b) and len(menu.kind_blocks(b)) > 1]
    assert sorted(b.name for b in multi) == sorted([f"DC_Tray_StraightL_{d}" for d in catalog.TRAY_DENSITIES] +
                                                   ["DC_TrayRods_100"])
    assert len([b for b in TRAYS if menu.owns_kind(b)]) == 6 + 3 * 8 + 2


# ---------------------------------------------------------------------------------------------- names
def test_tray_names_consistent(staged):
    """"Cable Tray, <shape> (<load>)" on every block; the multi-size kinds' tiles drop the size; the in-game block name
    (UIData.Name) and the kind tile are staged."""
    for b in TRAYS:
        title = names.NAMES[b.name][0]
        assert title.startswith("Cable Tray, ") and len(title) <= 40, title
        if b.variant == "Reducer":
            assert title.endswith(f"({b.density} to {names._DOWN[b.density]})"), title
        elif b.density:
            assert title.endswith(f"({b.density})"), title
        assert block_def(b)["UIData"]["Name"] == title
    assert names.NAMES["DC_Tray_StraightL_Full"][0] == "Cable Tray, Straight (Full)"
    assert names.NAMES["DC_Tray_StraightS_Low"][0] == "Cable Tray, Straight (Low)"
    assert names.NAMES["DC_TrayRods_025"][0] == "Cable Tray, Hanger Rods"
    assert kind_def(catalog.BY_NAME["DC_Tray_StraightL_Moderate"])["Name"] == "Cable Tray, Straight (Moderate)"
    assert kind_def(catalog.BY_NAME["DC_TrayRods_100"])["Name"] == "Cable Tray, Hanger Rods"
    assert kind_def(catalog.BY_NAME["DC_Tray_Tee_Full"])["Name"] == "Cable Tray, Tee (Full)"


# ---------------------------------------------------------------------------------------------- costs
def test_tray_costs(staged):
    """Every tray block costs by the core rule with game scale 1; the long straight costs at least the short one;
    density never changes a cost (cables are decoration): the four densities of a shape share one recipe."""
    t = recipes.table(report())

    def total(n):
        return sum(a * recipes.ITEMS[i][1] for i, a in t[n]["critical"] + t[n]["optional"])
    for b in TRAYS:
        c = t[b.name]
        assert c["game_scale"] == 1, b.name
        assert c["cost_source"] == ("StructuralSupportStraight" if b.family == "trayrods" else "WallInsertPipes")
        assert staged["blocks"][b.name]["recipe"]["game_scale"] == 1
    for d in catalog.TRAY_DENSITIES:   # cost follows run length
        S, L = total(f"DC_Tray_StraightS_{d}"), total(f"DC_Tray_StraightL_{d}")
        assert L == 3 * S, (S, L)
        assert total(f"DC_Tray_TurnDown_{d}") == S < total(f"DC_Tray_TurnH_{d}") == total(f"DC_Tray_TurnUp_{d}")
        assert total(f"DC_Tray_TurnH_{d}") < total(f"DC_Tray_Tee_{d}") == L < total(f"DC_Tray_Cross_{d}")
        if d != "Empty":
            assert total(f"DC_Tray_Drop_{d}") == total(f"DC_Tray_Reducer_{d}") == 2 * S   # 1 m runs
    shapes = {}
    for b in TRAYS:
        if b.density:
            shapes.setdefault(b.variant, set()).add((tuple(t[b.name]["critical"]), tuple(t[b.name]["optional"])))
    assert all(len(v) == 1 for v in shapes.values()), shapes   # incl. the three Reducers (all 1 m runs)
    assert total("DC_TrayRods_025") < total("DC_TrayRods_100") < total("DC_TrayRods_200")


def test_run_length_floor():
    """RUN_LENGTH is the tray centreline from each port to the junction: for these axis-aligned pieces the sum of the
    ports' extents along x, y and z (straights: the length; turns: both arms; Tee: through + branch; Cross: both
    throughs), from the cable plans. Two ruled exceptions: the Reducer is a 1 m run, the Chute its 1.25 m ladder.
    The rods are not floored (they already scale with length) and keep the strut's in-game scale."""
    for shape, L in recipes.RUN_LENGTH.items():
        if shape == "Reducer":
            assert L == 1.0
            continue
        if shape == "Chute":
            assert L == 0.25 * catalog.TRAY_CELLS["Chute"][1]
            continue
        o = [p.o for p in tray_plan.plan(shape, "Full").ports.values()]
        ext = sum(max(q[i] for q in o) - min(q[i] for q in o) for i in range(3))
        assert abs(ext - L) < 1e-6, (shape, ext, L)
    for b in TRAYS:
        u = recipes.run_units(b)
        if b.family == "trayrods":
            assert u == 0
            continue
        assert u == max(1, int(recipes.RUN_LENGTH[b.variant] / 0.5 + 0.5))
        c = recipes.cost(b, report())
        assert all(a >= u for _, a in c["critical"] + c["optional"]), b.name
        assert c["game_scale"] == 1


def test_tray_density_is_hollow(staged):
    """Tray pieces are an open wire basket: Hollow density (vanilla Truss250's) on the block definition; the rod
    hangers keep the strut's Mostly Hollow (no Density override)."""
    for b in TRAYS:
        bd = block_def(b)
        if b.family == "trayrods":
            assert "Density" not in bd, b.name
        else:
            assert bd["Density"] == recipes.DENSITY["Hollow"][0], b.name


# name -> (critical, optional, block mass kg): Pipes-sourced pieces pay one base unit (1 SP + 1 C, 1 SP optional) per
# 0.5 m of run; the rods scale the strut's in-game 2 Steel Plate by volume (1 / 2 / 3)
def _u(n):
    return [("SteelPlate", n), ("Construction", n)], [("SteelPlate", n)]


GOLDEN = {
    "DC_Tray_StraightS_Full": (*_u(1), 13.4),
    "DC_Tray_StraightL_Empty": (*_u(3), 31.2),
    "DC_Tray_TurnH_Low": (*_u(2), 25.0),
    "DC_Tray_TurnDown_Moderate": (*_u(1), 22.9),
    "DC_Tray_Cross_Full": (*_u(4), 31.2),
    "DC_Tray_Drop_Full": (*_u(2), 35.0),
    "DC_Tray_Reducer_Low": (*_u(2), 13.4),
    "DC_Tray_Chute": (*_u(3), 27.1),
    "DC_TrayRods_025": ([("SteelPlate", 1)], [], 18.2),
    "DC_TrayRods_100": ([("SteelPlate", 2)], [], 58.0),
    "DC_TrayRods_200": ([("SteelPlate", 3)], [], 98.7),
}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_tray_cost_golden_numbers(name):
    c = recipes.table(report())[name]
    assert (c["critical"], c["optional"], c["mass"]) == GOLDEN[name]


def test_tray_recipe_files(staged):
    """Each tray patches its own cloned recipe file (GUID kept), so no new recipe definitions are written for them."""
    for b in TRAYS:
        r = staged["blocks"][b.name]["recipe"]
        assert r["file"].startswith(f"{config.NAME}/{b.name}/") and "Recipe" in r["file"], r["file"]
        assert r["file"].endswith(".partialdef"), f"{b.name}: the cloned recipe Copy, not a new definition"


# ---------------------------------------------------------------------------------------------- icons
@pytest.mark.parametrize("b", TRAYS, ids=lambda b: b.name)
def test_tray_icons(staged, b):
    icon = os.path.join(UI, f"{b.name}_Icon.png")
    assert os.path.exists(icon), icon
    w, h, ctype, depth, chunks, _ = png_info(icon)
    assert (w, h, ctype, depth) == (200, 200, 6, 8) and "iCCP" not in chunks
    x0, y0, x1, y1 = alpha_bbox(icon)
    assert x0 > 0 and y0 > 0 and x1 < 199 and y1 < 199
    g = staged["blocks"][b.name].get("icon")
    assert g and g == "{G}" + integration.asset_id(f"{config.NAME}/{b.name}/UI/{b.name}_Icon.png")
    assert block_def(b)["UIData"]["Icon"] == g


def _need_pillow():
    if Image is None:
        pytest.fail("Pillow is required for the icon pixel checks (python3 -m pip install pillow)")


def _blue_pixels(path):
    """Opaque pixels of the blue preview paint on the data cables (clearly bluer than the grey basket)."""
    _need_pillow()
    im = Image.open(path).convert("RGBA")
    px = im.tobytes()
    return sum(1 for k in range(0, len(px), 4)
               if px[k + 3] > 200 and px[k + 2] > px[k] + 45 and px[k + 2] > px[k + 1] + 25)


# every tray shape kind that comes in densities; Drop and Reducer have no Empty (no lane to feed / nothing to step
# down). Excluded: the Chute and the rods, which carry no cable load (a single block each, no density to read).
DENSITY_SHAPES = sorted({b.variant for b in TRAYS if b.density})


def test_density_shapes_cover_every_shape():
    assert DENSITY_SHAPES == sorted(set(catalog.TRAY_SHAPES) | {"Drop", "Reducer"})
    assert {b.variant for b in TRAYS if not b.density} == {"Chute", "Rods"}


@pytest.mark.parametrize("shape", DENSITY_SHAPES)
def test_tray_icon_density_reads(shape):
    """The density reads on the icon: no blue cable on Empty, blue data bundles on Low, Moderate and Full (a Reducer's
    high side is at least Low), and the icons of a shape all differ."""
    dens = [b.density for b in TRAYS if b.variant == shape]
    paths = [os.path.join(UI, f"DC_Tray_{shape}_{d}_Icon.png") for d in dens]
    blue = dict(zip(dens, (_blue_pixels(p) for p in paths)))
    if "Empty" in blue:
        assert blue["Empty"] < 20, blue
    assert min(v for d, v in blue.items() if d != "Empty") > 150, blue
    data = [open(p, "rb").read() for p in paths]
    assert len(set(data)) == len(paths)


def test_support_icons_differ():
    """The supports (no density): the three rod lengths and the Chute are four distinct icons, the longer rods drawn
    taller (their alpha box)."""
    _need_pillow()
    names_ = ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200", "DC_Tray_Chute"]
    data = [open(os.path.join(UI, f"{n}_Icon.png"), "rb").read() for n in names_]
    assert len(set(data)) == 4
    h = [alpha_bbox(os.path.join(UI, f"{n}_Icon.png")) for n in names_[:3]]
    assert h[0][3] - h[0][1] < h[1][3] - h[1][1] < h[2][3] - h[2][1], h
