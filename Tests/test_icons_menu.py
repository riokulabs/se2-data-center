"""Icons, previews, build-menu grouping (dc/menu.py) and cost balancing (dc/recipes.py)."""
import math
import os
import struct
import zlib

import pytest

from dc import catalog, clone, config, integration, menu, recipes
from dc.assetio import read_json

UI = os.path.join(config.HERE, "UI")
PREVIEW_BLOCKS = os.path.join(config.PREVIEW_DIR, "blocks")
HERO = os.path.join(config.PREVIEW_DIR, "hero")
SDK = os.path.expanduser("~/.steam/debian-installation/steamapps/common/Space Engineers 2 - Mod SDK/GameData/"
                         "Vanilla/Assets")


def png_info(path):
    """(width, height, colour type, bit depth, chunk names, decoded RGBA rows) from a PNG, stdlib only."""
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    pos, chunks, idat, hdr = 8, [], b"", None
    while pos < len(data):
        n, t = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        chunks.append(t.decode())
        if t == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif t == b"IDAT":
            idat += body
        pos += 12 + n
    w, h, depth, ctype = hdr[0], hdr[1], hdr[2], hdr[3]
    return w, h, ctype, depth, chunks, idat


def alpha_bbox(path):
    """Bounding box (x0, y0, x1, y1) of pixels with alpha > 8, for an 8-bit RGBA PNG (stdlib decoder)."""
    w, h, ctype, depth, _, idat = png_info(path)
    assert (ctype, depth) == (6, 8)
    raw = zlib.decompress(idat)
    bpp, stride = 4, w * 4
    prev = bytearray(stride)
    xs, ys = [], []
    i = 0
    for y in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        for x in range(w):
            if line[4 * x + 3] > 8:
                xs.append(x)
                ys.append(y)
        prev = line
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


# ---------------------------------------------------------------------------------------------- icons + previews
# every block has a menu entry, an icon and a cost (the cable trays included)
MENU_BLOCKS = list(catalog.BLOCKS)


def test_menu_covers_every_block():
    assert len(MENU_BLOCKS) == 73 and {b.family for b in MENU_BLOCKS} == {"rack", "server", "tray", "trayrods",
                                                                         *catalog.ROOM_FAMILIES}   # room families too
    assert all(menu.group(b) in menu.GROUPS for b in MENU_BLOCKS)
    assert all(recipes.costed(b) for b in MENU_BLOCKS)


@pytest.mark.parametrize("b", MENU_BLOCKS, ids=lambda b: b.name)
def test_every_block_has_icon_and_preview(b):
    icon = os.path.join(UI, f"{b.name}_Icon.png")
    assert os.path.exists(icon), icon
    w, h, ctype, depth, chunks, _ = png_info(icon)
    assert (w, h) == (200, 200)
    assert (ctype, depth) == (6, 8), "8-bit RGBA"
    assert "iCCP" not in chunks, "no ICC profile (the project validator rejects some)"
    box = alpha_bbox(icon)
    assert box, "icon is empty"
    x0, y0, x1, y1 = box
    assert x0 > 0 and y0 > 0 and x1 < 199 and y1 < 199, f"icon touches the frame edge: {box}"
    assert max(x1 - x0, y1 - y0) >= 90, f"icon subject too small: {box}"
    if b.family in catalog.ROOM_FAMILIES:
        return   # the room pieces' store shots are their own preview sets, not preview/blocks/
    if not os.path.isdir(PREVIEW_BLOCKS):
        pytest.skip("preview renders are not tracked in git (generated on disk); none present")
    assert os.path.exists(os.path.join(PREVIEW_BLOCKS, f"{b.name}.png")), f"no preview for {b.name}"


def test_hero_shots():
    if not os.path.isdir(HERO):
        pytest.skip("preview renders are not tracked in git (generated on disk); none present")
    want = ("hero_aisle", "hero_server_lineup", "hero_door_variants_3_paints", "hero_layout_top", "hero_detail")
    for n in want:
        assert os.path.exists(os.path.join(HERO, n + ".png")), n


# ---------------------------------------------------------------------------------------------- staged package
@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


def stage(rel):
    return read_json(os.path.join(config.STAGE_ASSETS, rel))


def test_icons_staged(staged):
    for b in MENU_BLOCKS:
        icon = staged["blocks"][b.name].get("icon")
        assert icon and icon.startswith("{G}"), b.name
        rel = f"{config.NAME}/{b.name}/UI/{b.name}_Icon.png"
        assert integration.asset_id(rel) == icon[3:]


def test_menu_one_entry_per_family(staged):
    sub = stage(menu.SUBCATEGORY["file"])["$Value"]
    assert sub["Name"] == "Data Center"
    assert [c["Value"] for c in sub["Categories"]] == [menu.AUTOMATION_CATEGORY]
    groups = {g: stage(v["file"])["$Value"] for g, v in menu.GROUPS.items()}
    for g in groups.values():
        assert [s["Value"] for s in g["Subcategories"]] == [sub["Guid"]]
    kinds = {}   # kind guid -> (kind value, [blocks])
    for b in MENU_BLOCKS:
        info = clone.entry(b)["info"]
        bd = stage(info["block_def_file"])["$Value"]["Manipulator"]
        owner_info = clone.entry(menu.kind_owner(b))["info"]
        assert bd["BlockKind"] == owner_info["kind"], b.name
        kinds.setdefault(bd["BlockKind"], [stage(owner_info["kind_file"])["$Value"], []])[1].append(b)
    for kv, blocks in kinds.values():
        grp = menu.group(blocks[0])
        assert {menu.group(b) for b in blocks} == {grp}
        assert [g["Value"] for g in kv["BlockGroups"]] == [groups[grp]["Guid"]], kv["Name"]
        sizes = [menu.display_size(b) for b in blocks]
        assert len(set(sizes)) == len(sizes), f"{kv['Name']}: blocks of one kind must differ in size"
        assert kv["OrderingPriority"] >= 1
    per_group = {g: len([k for k in kinds.values() if menu.group(k[1][0]) == g]) for g in menu.GROUPS}
    assert per_group == {"rack": 3, "server": 10, "tray_Empty": 6, "tray_Low": 8, "tray_Moderate": 8,
                         "tray_Full": 8, "traysupport": 2, "floor": 2, "roompower": 4, "contain": 2, "signs": 3}
    # every group is staged, in the subcategory, ordered racks, servers, Empty .. Full, supports
    orders = [groups[g]["Order"] for g in menu.GROUPS]
    assert orders == sorted(orders) and len(set(orders)) == len(orders) and 0 not in orders
    # the further sizes' own clone kinds (24U racks, short straights, 0.25 / 2.0 m rods) are inert: no group, no unlock
    unlock = stage(integration.UNLOCK_FILE)["$Value"]["Manipulator"]["BlockKinds"]["Added"]
    assert sorted(unlock) == sorted(kinds)
    for b in MENU_BLOCKS:
        if not menu.owns_kind(b):
            assert stage(clone.entry(b)["info"]["kind_file"])["$Value"]["BlockGroups"] == []


def test_menu_order():
    racks = sorted((b for b in catalog.BLOCKS if b.family == "rack" and menu.owns_kind(b)), key=menu.priority)
    assert [b.variant for b in racks] == ["Open", "SplitFront", "SplitFrontRear"]
    assert sorted({menu.priority(b) for b in catalog.BLOCKS if b.family == "server"}) == list(range(1, 11))


# ---------------------------------------------------------------------------------------------- costs
def report():
    return read_json(config.REPORT_PATH) if os.path.exists(config.REPORT_PATH) else None


def test_cost_formula_matches_vanilla_source_cost():
    """A vanilla block's in-game cost = its recipe x the game's scale. The heavy mixes have scale 1 (the source cost is
    the recipe itself); the long strut's lone Steel Plate (35 kg) is about half the strut (69 kg), so the game charges
    it twice, and our ratio is computed against that in-game cost."""
    want = {"StructuralSupportStraight": 2,
            # the room sources' light recipes (one plate for a 2.5 m catwalk or deck, 225 kg) and the
            # gyroscope's and sliding door's solid 2.5 m boxes are charged several times their recipe in game
            "CatwalkSquareBase250": 6, "DeckPanel250": 6, "Gyroscope250": 3, "SlidingDoorNarrow250": 2}
    for k, s in recipes.SOURCES.items():
        if s["cells"]:
            m = recipes.mass(recipes.cells(s["cells"]), s["density"])
            assert recipes.game_scale(m, s["critical"], s["optional"]) == want.get(k, 1), k
            assert recipes.source_scale(k) == want.get(k, 1), k


def test_costs_scale_with_volume_and_game_scale_is_one():
    t = recipes.table(report())
    for name, c in t.items():
        assert c["game_scale"] == 1, f"{name}: the game would multiply our recipe by {c['game_scale']}"
        assert all(a >= 1 for _, a in c["critical"] + c["optional"])

    def total(n):
        return sum(a * recipes.ITEMS[i][1] for i, a in t[n]["critical"] + t[n]["optional"])
    for h in (42, 24):
        assert total(f"DC_Rack{h}_Open") < total(f"DC_Rack{h}_SplitFront") < total(f"DC_Rack{h}_SplitFrontRear")
    for v in ("Open", "SplitFront", "SplitFrontRear"):
        assert total(f"DC_Rack24_{v}") < total(f"DC_Rack42_{v}")
    racks = [b.name for b in catalog.BLOCKS if b.family == "rack"]
    servers = [b.name for b in catalog.BLOCKS if b.family == "server"]
    # the game's mass follows the OCCUPIED cells, and the half rack frees its slots'
    # front row (the placement fix) and its PDU columns: 60 cells, 370 kg-equivalent, just under the
    # Timer server's 375 (4 Hard Drives). Every rack's cost is floored at the dearest server (recipes.FRAME_FLOOR):
    # no rack costs less than a server it holds.
    assert max(total(n) for n in servers) < min(total(n) for n in racks if "Rack42" in n)
    assert max(total(n) for n in servers) <= min(total(n) for n in racks)
    deco = [b.name for b in catalog.BLOCKS if b.family == "server" and b.variant in ("Compute", "Storage", "Switch",
                                                                                        "Blank")]
    assert len(deco) == 4 and max(total(n) for n in deco) < min(total(n) for n in racks)


# three costs worth checking in game
GOLDEN_COSTS = {
    # the freed PDU columns (16 cells) + the placement fix (the slots' front-zone row, 16 cells):
    # 120 occupied cells, not 152: 11 -> 9 plates, 8 -> 7 construction, 8 -> 7 optional
    "DC_Rack42_Open": ([("SteelPlate", 9), ("Construction", 7)], [("SteelPlate", 7)]),
    "DC_Srv_Compute": ([("SteelPlate", 1), ("Construction", 1)], [("SteelPlate", 1)]),
    "DC_Srv_UPS": ([("Construction", 9), ("ElectronicParts", 1)], [("Construction", 4)]),
}


@pytest.mark.parametrize("name", sorted(GOLDEN_COSTS))
def test_cost_golden_numbers(name):
    c = recipes.table(report())[name]
    assert (c["critical"], c["optional"]) == GOLDEN_COSTS[name]


def test_recipes_staged(staged):
    t = recipes.table(report())
    assert sorted(t) == sorted(b.name for b in catalog.BLOCKS)
    for b in catalog.BLOCKS:
        r = staged["blocks"][b.name]["recipe"]
        info = clone.entry(b)["info"]
        bd = stage(info["block_def_file"])["$Value"]["Manipulator"]
        assert bd["Recipe"] == r["guid"]
        rec = stage(r["file"])["$Value"]
        rec = rec.get("Manipulator", rec)
        got = [(e["Value"]["Item"], e["Value"]["Amount"]) for e in rec["CriticalItems"]]
        assert got == [(recipes.ITEMS[i][0], a) for i, a in t[b.name]["critical"]], b.name
        got = [(e["Value"]["Item"], e["Value"]["Amount"]) for e in rec.get("OptionalItems") or []]
        assert got == [(recipes.ITEMS[i][0], a) for i, a in t[b.name]["optional"]], b.name
        if recipes.door_sides(b):
            assert bd["Density"] == recipes.DENSITY["MostlyHollow"][0]
        if recipes.density_patch(b):
            assert bd["Density"] == recipes.DENSITY[recipes.density_patch(b)][0], b.name
        else:   # as cloned: absent (the template's) or the source's own
            assert bd.get("Density", recipes.DENSITY[recipes.SOURCES[b.copy_from]["density"]][0]) == \
                recipes.DENSITY[recipes.SOURCES[b.copy_from]["density"]][0], f"{b.name}: keeps its source's density"


def _qrot(q, v):
    """v rotated by the unit quaternion q = (x, y, z, w) (glTF order)."""
    x, y, z, w = q
    c = (y * v[2] - z * v[1], z * v[0] - x * v[2], x * v[1] - y * v[0])
    cc = (y * c[2] - z * c[1], z * c[0] - x * c[2], x * c[1] - y * c[0])
    return tuple(v[i] + 2 * w * c[i] + 2 * cc[i] for i in range(3))


def collider_extent(g):
    """Size of the union of a collision glTF's colliders (box primitives, or convex meshes' bounds), each placed by the
    rotation and translation of the node that carries it (the catwalk's and gyroscope's fracture pieces)."""
    cols = g["extensions"]["MSFT_collision_primitives"]["colliders"]
    node = {n["extensions"]["MSFT_rigid_bodies"]["collider"]: n for n in g.get("nodes", [])
            if "collider" in n.get("extensions", {}).get("MSFT_rigid_bodies", {})}
    lo, hi = [1e9] * 3, [-1e9] * 3
    for i, col in enumerate(cols):
        if "box" in col:
            b = [v / 2 for v in col["box"]["size"]]
            a = [-v for v in b]
        else:
            acc = g["accessors"][g["meshes"][col["convex"]["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
            a, b = acc["min"], acc["max"]
        n = node.get(i, {})
        q, t = n.get("rotation", (0, 0, 0, 1)), n.get("translation", (0, 0, 0))
        for c in [(x, y, z) for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])]:
            p = [v + t[k] for k, v in enumerate(_qrot(q, c))]
            lo, hi = [min(lo[k], p[k]) for k in range(3)], [max(hi[k], p[k]) for k in range(3)]
    return [h - lo_ for lo_, h in zip(lo, hi)]


def collider_cells(size):
    """The 0.25 m cells a collider extent occupies (a 0.125 m deep LCD still takes one cell; 2.46 m of catwalk ten)."""
    return tuple(max(1, math.ceil(v / 0.25 - 0.1)) for v in size)


@pytest.mark.skipif(not os.path.isdir(SDK), reason="Mod SDK not installed")
def test_sources_match_sdk():
    """The vanilla source recipes and item masses written in dc/recipes.py equal the SDK files."""
    def load(rel):
        return read_json(os.path.join(SDK, rel))["$Value"]

    def items(v, k):
        v = v.get("Manipulator", v).get(k) or []
        return [(e["Value"]["Item"], e["Value"]["Amount"]) for e in v]
    for k, s in recipes.SOURCES.items():
        if "recipe_chain" in s:   # inherited through a Copy chain: checked below
            continue
        v = load(s["file"])
        assert items(v, "CriticalItems") == [(recipes.ITEMS[i][0], a) for i, a in s["critical"]], k
        assert items(v, "OptionalItems") == [(recipes.ITEMS[i][0], a) for i, a in s["optional"]], k
        assert v.get("Manipulator", v).get("BuildTimePerItem") == s["time"], k

    def chain(head, rest, key):
        """The value of `key` along a partial-definition Copy chain: each file's BaseDefinition must be the next file's
        Guid; the first file whose body sets the key wins."""
        files = [load(f) for f in (head,) + tuple(rest)]
        for a, b in zip(files, files[1:]):
            assert a["BaseDefinition"] == b.get("Manipulator", b)["Guid"], (head, "chain broken")
        for v in files:
            v = v.get("Manipulator", v)
            if key in v:
                return v[key]
        return None
    for k, s in recipes.SOURCES.items():
        def norm(v):
            return [(e["Value"]["Item"], e["Value"]["Amount"]) for e in v or []]
        if "recipe_chain" in s:
            assert norm(chain(s["file"], s["recipe_chain"], "CriticalItems")) == \
                [(recipes.ITEMS[i][0], a) for i, a in s["critical"]], k
            assert norm(chain(s["file"], s["recipe_chain"], "OptionalItems")) == \
                [(recipes.ITEMS[i][0], a) for i, a in s["optional"]], k
            assert chain(s["file"], s["recipe_chain"], "BuildTimePerItem") == s["time"], k
        if "block_chain" in s:
            assert chain(s["block_chain"][0], s["block_chain"][1:], "Density") == recipes.DENSITY[s["density"]][0], k
        if "collision" in s:
            size = collider_extent(read_json(os.path.join(SDK, s["collision"])))
            assert collider_cells(size) == s["cells"], (k, size)
    for name, (g, m) in recipes.DENSITY.items():
        hits = [f for f in os.listdir(os.path.join(SDK, "Blocks/Shared/Density"))
                if f.endswith(".def") and read_json(os.path.join(SDK, "Blocks/Shared/Density", f))["$Value"]["Guid"] == g]
        assert hits and read_json(os.path.join(SDK, "Blocks/Shared/Density", hits[0]))["$Value"]["MassCurveModifier"] == m
