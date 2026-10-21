"""The room catalogue, names and clones, and the pure-Python room layout (dc/room.py).

dc/room.py places every block of the reference room in world cells (Blender axes, metres: x along the rows, y across
the aisle with the aisle centred on y = 0, z up from the deck under the raised floor). These tests need no Blender:
the occupancy of a block is its full cell box, except
  * racks: the box minus rack.FREE_CELLS (the server slots and the rear PDU columns), and
  * tray pieces: the box minus the cells their cable plan leaves empty (tray_plan.occupied_cells), which is
    what lets a rack label stand between a Drop's two waterfalls.
Other tests re-run the same layout on the measured geometry (build_report.json free_cells)."""
import os

import pytest

from dc import catalog, clone, config, dims as DM, names, rack, room

ROOM_TABLE = {   # name: (family, cells, vanilla source, copy_from, variant)
    "DC_Floor_Solid_050": ("floor", (2, 1, 2), "Blocks/Catwalks/CatwalkSquareBase/250", "CatwalkSquareBase250", "Solid"),
    "DC_Floor_Perf_050": ("floor", (2, 1, 2), "Blocks/Catwalks/CatwalkSquareBase/250", "CatwalkSquareBase250", "Perf"),
    "DC_Floor_Solid_100": ("floor", (4, 1, 4), "Blocks/Catwalks/CatwalkSquareBase/250", "CatwalkSquareBase250", "Solid"),
    "DC_Floor_Perf_100": ("floor", (4, 1, 4), "Blocks/Catwalks/CatwalkSquareBase/250", "CatwalkSquareBase250", "Perf"),
    "DC_CRAC": ("crac", (4, 10, 5), "Blocks/Gyroscopes/Gyroscopes/250", "Gyroscope250", "CRAC"),
    "DC_PDU_Cabinet": ("pdu_cabinet", (4, 10, 5), "Blocks/Walls/Inserts/Panel", "WallInsertPanel", "Cabinet"),
    "DC_PDU_Rack42_A": ("pdu_strip", (1, 8, 1), "Blocks/Walls/Inserts/Panel", "WallInsertPanel", "A"),
    "DC_PDU_Rack42_B": ("pdu_strip", (1, 8, 1), "Blocks/Walls/Inserts/Panel", "WallInsertPanel", "B"),
    "DC_PDU_Rack24_A": ("pdu_strip", (1, 4, 1), "Blocks/Walls/Inserts/Panel", "WallInsertPanel", "A"),
    "DC_PDU_Rack24_B": ("pdu_strip", (1, 4, 1), "Blocks/Walls/Inserts/Panel", "WallInsertPanel", "B"),
    "DC_Contain_Door_100": ("contain_door", (8, 10, 1), "Blocks/Doors/SlideDoorNarrow/250", "SlidingDoorNarrow250", "Door"),
    "DC_Contain_Door_150": ("contain_door", (12, 10, 1), "Blocks/Doors/SlideDoorNarrow/250", "SlidingDoorNarrow250",
                            "Door"),
    "DC_Contain_Door_200": ("contain_door", (16, 10, 1), "Blocks/Doors/SlideDoorNarrow/250", "SlidingDoorNarrow250",
                            "Door"),
    "DC_Contain_Roof_100": ("contain_roof", (4, 1, 4), "Blocks/DeckPanel/250", "DeckPanel250", "Roof"),
    "DC_Contain_Roof_150": ("contain_roof", (4, 1, 6), "Blocks/DeckPanel/250", "DeckPanel250", "Roof"),
    "DC_Contain_Roof_200": ("contain_roof", (4, 1, 8), "Blocks/DeckPanel/250", "DeckPanel250", "Roof"),
    "DC_Sign_Aisle": ("sign", (4, 1, 1), "Blocks/LCDPanels/NarrowLCD/50", "LCDNarrow50", "Aisle"),
    "DC_Sign_AisleHang": ("sign", (4, 1, 2), "Blocks/LCDPanels/NarrowLCD/50", "LCDNarrow50", "AisleHang"),
    "DC_Sign_Rack": ("sign", (2, 1, 1), "Blocks/LCDPanels/NarrowLCD/50", "LCDNarrow50", "Rack"),
}
NEW_SOURCES = {"CatwalkSquareBase250", "Gyroscope250", "DeckPanel250", "LCDNarrow50"}   # + two the core already clones
ROOM_SOURCES = NEW_SOURCES | {"WallInsertPanel", "SlidingDoorNarrow250"}
CASES = [(w, a) for w in DM.AISLE_WIDTHS for a in ("cold", "hot")]
EPS = 1e-9


def _on_grid(v):
    return abs(v / DM.CELL - round(v / DM.CELL)) < 1e-9


# ---------------------------------------------------------------------------------------------------- catalogue
def test_room_catalogue():
    rooms = [b for b in catalog.CATALOGUE if b.family in catalog.ROOM_FAMILIES]
    assert [b.name for b in rooms] == list(ROOM_TABLE), "the 19 room blocks, in the table's order"
    assert catalog.ROOM == rooms
    for b in rooms:
        fam, cells, src, cf, variant = ROOM_TABLE[b.name]
        assert (b.family, b.cells, b.vanilla_source, b.copy_from, b.variant) == (fam, cells, src, cf, variant), b.name
        assert len(b.name) <= 40 and b.density is None
        title, desc = names.NAMES[b.name]
        assert title and desc and len(title) <= 40, b.name
    assert {b.copy_from for b in rooms} == ROOM_SOURCES
    # copy_from is the exact vanilla prefix (test_catalog.test_copy_from_matches_vanilla, for the 5 sources here)
    for b in rooms:
        files = os.listdir(os.path.join(config.VANILLA_REF, b.vanilla_source))
        assert f"{b.copy_from}.partialdef" in files, b.name


def test_room_blocks_in_the_pipeline():
    """Catalogue gating: a room family joins PIPELINE_FAMILIES once it has definitions; all of them are
    wired (menu, icons, recipes, unlock), so the whole-catalogue loops see every room block."""
    assert set(catalog.ROOM_FAMILIES) <= set(catalog.PIPELINE_FAMILIES)
    assert [b for b in catalog.BLOCKS if b.family in catalog.ROOM_FAMILIES] == catalog.ROOM


def test_room_clone_prefixes():
    """Every second file prefix in a room source folder has a clone.ALSO rename, so no cloned file
    keeps a vanilla name."""
    assert clone.ALSO["CatwalkSquareBase250"]("X") == ["CatwalkSquareBase_250=X"]
    assert clone.ALSO["LCDNarrow50"]("X") == ["NarrowLCD50=X"]
    sdk = clone._sdk_assets()
    for cf in ROOM_SOURCES:
        b = next(b for b in catalog.ROOM if b.copy_from == cf)
        renames = [(cf, b.name)] + [tuple(a.split("=", 1)) for a in clone.ALSO.get(cf, lambda n: [])(b.name)]
        root = os.path.join(sdk, b.vanilla_source)
        for dp, _, fs in os.walk(root):
            for f in fs:
                if not f.endswith((".def", ".partialdef")):
                    continue
                new = f
                for a, z in renames:
                    new = new.replace(a, z)
                assert not [a for a, _ in renames if a in new] and " " not in new, (cf, f, new)


# ---------------------------------------------------------------------------------------------------- interfaces
def test_aisle_widths():
    for w in DM.AISLE_WIDTHS:
        assert room.door_name(w) == f"DC_Contain_Door_{round(w * 100):03d}"
        assert room.roof_name(w) == f"DC_Contain_Roof_{round(w * 100):03d}"
        assert room.aisle_width(catalog.BY_NAME[room.door_name(w)]) == w
        assert room.aisle_width(catalog.BY_NAME[room.roof_name(w)]) == w
    with pytest.raises(ValueError):
        room.aisle_width(catalog.BY_NAME["DC_Rack42_Open"])


def test_stack_heights():
    S = room.STACK
    assert S["floor_top"] == DM.RF_H
    assert S["rack_top"] == DM.RF_H + 2.5
    assert S["roof"] == (S["rack_top"] - DM.CELL, S["rack_top"])
    assert S["roof"][1] == S["rack_top"] == S["door_top"]
    assert abs(S["tray_bottom"] - S["rack_top"] - DM.TRAY_HANG) < EPS


def test_world_cells_frame():
    """A rack at yaw 0 has its front (+y) toward +y; the game-frame local cells map to the right world cells."""
    spec = catalog.BY_NAME["DC_Rack42_Open"]
    p = room.Placed(spec.name, (0.5, 0.625, 1.5), 0)            # box x 0..1, y 0..1.25, z 0.25..2.75
    cells = room.world_cells(p)
    assert len(cells) == 4 * 10 * 5
    assert {c[0] for c in cells} == set(range(0, 4)) and {c[1] for c in cells} == set(range(0, 5))
    assert {c[2] for c in cells} == set(range(1, 11))
    # Feed A: the rear (-y) depth cell of the right (+x) column over the slot band
    a = room.world_cells(p, rack.PDU_CELLS(spec, "A"))
    assert a == {(3, 0, k) for k in range(2, 10)}
    # turned 180 deg about z: the rack's right / rear go to world -x / +y
    q = room.Placed(spec.name, (0.5, 0.625, 1.5), 2)
    assert room.world_cells(q, rack.PDU_CELLS(spec, "A")) == {(0, 4, k) for k in range(2, 10)}
    assert room.world_cells(q) == cells
    # a quarter turn swaps the footprint
    r = room.Placed(spec.name, (0.625, 0.5, 1.5), 1)
    assert {c[0] for c in room.world_cells(r)} == set(range(0, 5))


# ---------------------------------------------------------------------------------------------------- the room
def _by_tag(placed):
    return {p.tag: p for p in placed if p.tag}


@pytest.mark.parametrize("w,aisle", CASES)
def test_reference_room_on_grid(w, aisle):
    placed = room.reference_room(w, aisle)
    for p in placed:
        lo, hi = room.box(p)
        assert all(_on_grid(v) for v in (*lo, *hi)), (p, lo, hi)
    racks = [p for p in placed if room.spec(p).family == "rack"]
    assert len(racks) == 8
    for p in racks:
        # the rack's front (cold) or back (hot) face lies on the aisle plane y = +-w/2
        face_y = p.origin[1] + room.rot((0.0, 0.625 * (1 if aisle == "cold" else -1), 0.0), p.yaw)[1]
        assert abs(abs(face_y) - w / 2) < EPS and face_y * p.origin[1] > 0, (p, face_y)
        assert abs(room.box(p)[0][2] - room.STACK["floor_top"]) < EPS
        assert abs(room.box(p)[1][2] - room.STACK["rack_top"]) < EPS


@pytest.mark.parametrize("w,aisle", CASES)
def test_reference_room_contents(w, aisle):
    placed = room.reference_room(w, aisle)
    count = {}
    for p in placed:
        count[p.name] = count.get(p.name, 0) + 1
    assert count["DC_Rack42_SplitFront"] == 8 and count["DC_CRAC"] == 2 and count["DC_PDU_Cabinet"] == 2
    assert count["DC_PDU_Rack42_A"] == count["DC_PDU_Rack42_B"] == 8
    assert count["DC_Sign_Rack"] == 8 and count["DC_Sign_Aisle"] == 2 and count["DC_Sign_AisleHang"] == 1
    assert count[room.door_name(w)] == 2 and count[room.roof_name(w)] == 6        # every 1.0 m of a 6-unit row
    assert sum(v for k, v in count.items() if k.startswith("DC_Tray_Drop_")) == 8
    assert sum(v for k, v in count.items() if k.startswith("DC_Floor_")) > 0
    # every rack stands on tiles, perforated ones on the cold side of the rows
    floor = [p for p in placed if room.spec(p).family == "floor"]
    under = set().union(*(room.world_cells(p) for p in floor))
    for p in placed:
        if room.spec(p).family in ("rack", "crac", "pdu_cabinet", "contain_door"):
            foot = {(i, j) for i, j, k in room.world_cells(p)}
            assert {(i, j, 0) for i, j in foot} <= under, p
    perf = [p for p in floor if room.spec(p).variant == "Perf"]
    L = max(room.box(p)[1][0] for p in placed if room.spec(p).family == "rack")
    assert perf and all((abs(p.origin[1]) < w / 2) == (aisle == "cold") for p in perf)
    assert all(0.0 < p.origin[0] < L + room.PITCH for p in perf)          # along the rows (incl. the PDU cabinet)
    # the doors close the aisle at both ends, their signs on the outer face of the header band
    doors = [p for p in placed if room.spec(p).family == "contain_door"]
    xs = sorted(room.box(d)[0][0] for d in doors)
    rx = [room.box(p)[0][0] for p in placed if room.spec(p).family in ("rack", "crac", "pdu_cabinet")]
    rX = [room.box(p)[1][0] for p in placed if room.spec(p).family in ("rack", "crac", "pdu_cabinet")]
    assert xs == [min(rx) - DM.CELL, max(rX)]
    for d in doors:
        lo, hi = room.box(d)
        assert (lo[1], hi[1]) == (-w, w) and hi[2] == room.STACK["door_top"]
    for s in (p for p in placed if p.name == "DC_Sign_Aisle"):
        lo, hi = room.box(s)
        assert (lo[2], hi[2]) == (room.STACK["door_top"] - DM.CELL, room.STACK["door_top"])
        assert hi[0] == min(rx) - DM.CELL or lo[0] == max(rX) + DM.CELL


@pytest.mark.parametrize("w,aisle", CASES)
def test_reference_room_no_conflicts(w, aisle):
    placed = room.reference_room(w, aisle)
    report = room.pure_report(p.name for p in placed)
    assert room.conflicts(placed, report) == []
    # PDU strips sit exactly in their rack's PDU columns
    tags = _by_tag(placed)
    strips = [p for p in placed if room.spec(p).family == "pdu_strip"]
    assert len(strips) == 16
    for s in strips:
        host = tags[s.tag.split("/")[0]]
        feed = room.spec(s).variant
        assert room.world_cells(s) == room.world_cells(host, rack.PDU_CELLS(room.spec(host), feed)), s
        assert room.world_cells(s) <= room.world_cells(host) - room.occupied(host, report)
    # a rack label stands in the front label pad cells, between its Drop's waterfalls
    for lab in (p for p in placed if p.name == "DC_Sign_Rack"):
        host = tags[lab.tag.split("/")[0]]
        lo, hi = room.box(lab)
        assert lo[2] == room.STACK["rack_top"]
        c = room.rot((0.0, sum(DM.LABEL_Y) / 2, 0.0), host.yaw)
        assert abs(lab.origin[0] - host.origin[0] - c[0]) < EPS and abs(lab.origin[1] - host.origin[1] - c[1]) < EPS


def test_conflicts_detects_overlap():
    a = room.Placed("DC_CRAC", (0.5, 0.625, 1.5), 0)
    b = room.Placed("DC_PDU_Cabinet", (1.0, 0.625, 1.5), 0)
    out = room.conflicts([a, b], {})
    assert len(out) == 1 and out[0][:2] == ("DC_CRAC", "DC_PDU_Cabinet") and out[0][2]


@pytest.mark.parametrize("w,aisle", CASES)
def test_reference_room_trays(w, aisle):
    placed = room.reference_room(w, aisle)
    S = room.STACK
    drops = [p for p in placed if p.name.startswith("DC_Tray_Drop_")]
    straights = [p for p in placed if p.name.startswith("DC_Tray_Straight")]
    rods = [p for p in placed if p.name.startswith("DC_TrayRods_")]
    assert len(straights) == 2 * 2 * 2       # two 0.5 m Straights over each CRAC and PDU cabinet, both rows
    for p in drops:
        assert abs(room.box(p)[0][2] - S["rack_top"]) < EPS
    for p in straights:
        assert abs(room.box(p)[0][2] - S["tray_bottom"]) < EPS
    # a rod hanger over every tray piece, all up to one ceiling plane; the hanging sign's one mid-aisle
    tops = {round(room.box(p)[1][2], 6) for p in rods}
    assert len(tops) == 1 and len(rods) == len(drops) + len(straights) + 1
    hang = next(p for p in placed if p.name == "DC_Sign_AisleHang")
    assert abs(hang.origin[1]) < EPS and hang.yaw % 2 == 1
    overhead = ("DC_Tray", "DC_Sign_AisleHang")
    assert room.reference_room(w, aisle, trays=False) == [p for p in placed if not p.name.startswith(overhead)]


def test_reference_room_options():
    full = room.reference_room()
    bare = room.reference_room(trays=False, labels=False)
    assert not [p for p in bare if p.name.startswith(("DC_Tray", "DC_Sign"))]
    assert len(bare) < len(full)
    six = room.reference_room(racks=6)
    assert sum(1 for p in six if p.name == "DC_Rack42_SplitFront") == 12
    assert sum(1 for p in six if p.name == room.roof_name(1.5)) == 8
    with pytest.raises(ValueError):
        room.reference_room(aisle="warm")
    with pytest.raises(ValueError):
        room.reference_room(aisle_w=1.25)


# ---------------------------------------------------------------------------------------------------- clones
def test_room_clones():
    cmap = clone.load_map()
    for b in catalog.ROOM:
        e = clone.entry(b, cmap)
        assert e and e.get("info"), f"{b.name} not cloned"
        assert b.vanilla_source in {c["src"] for c in e["copies"]}
        root = os.path.join(config.MOD_ASSETS, config.NAME, b.name)
        files = [f for _, _, fs in os.walk(root) for f in fs]
        assert not [f for f in files if b.copy_from in f or "NarrowLCD50" in f or "CatwalkSquareBase_250" in f], b.name
        assert not [f for f in files if " " in f], b.name
    crac = os.path.join(config.MOD_ASSETS, config.NAME, "DC_CRAC")
    subs = os.listdir(os.path.join(crac, "Subparts"))
    # the vanilla gimbal's dead subpart chain is dropped (clone.DROP), only the
    # CracFan rotor's files and the ConditionalSubParts definition stay
    every = [f for _, _, fs in os.walk(crac) for f in fs if not f.endswith(".meta")]
    assert not [f for f in every if f.endswith(clone.GIMBAL)], every
    assert "DC_CRAC_CracFan.partialdef" in subs and "SubParts.def" in os.listdir(crac), subs
    assert not [f for f in every if "Gyroscope250" in f]


# ---------------------------------------------------------------------------------------------------- hero hall
def test_shared_row_doors_fit():
    """A row between a contained cold and a contained hot aisle carries both aisles' end doors
    on its end racks; each door's leaves park W/2 beyond its aisle, so the two pockets share row B's 1.25 m depth.
    1.5 + 1.0 (and 1.0 + 1.0, 1.0 + 1.5) fit; two 1.5 m aisles or any 2.0 m aisle do not."""
    fits = {(c, h) for c in DM.AISLE_WIDTHS for h in DM.AISLE_WIDTHS if room.shared_row_doors_fit(c, h)}
    assert fits == {(1.0, 1.0), (1.0, 1.5), (1.5, 1.0)}
    with pytest.raises(ValueError):
        room.two_aisle_room(1.5, 1.5)


@pytest.mark.parametrize("cold,hot", [(1.5, 1.0), (1.0, 1.0), (1.0, 1.5)])
def test_two_aisle_hall(cold, hot):
    """The hero hall: three rows (A and B face the cold aisle, B and C turn their backs to the hot one), both
    aisles contained (a roof over every unit, a door at each end), no cell conflicts anywhere (doors included), and
    one gap-free raised floor."""
    placed = room.two_aisle_room(cold, hot)
    assert room.conflicts(placed, room.pure_report(p.name for p in placed)) == []
    units = [p for p in placed if room.spec(p).family in ("rack", "crac", "pdu_cabinet")]
    rows = sorted({round(p.origin[1], 4) for p in units})
    dy = room.hot_offset(cold, hot)
    assert rows == [-(cold / 2 + 0.625), cold / 2 + 0.625, dy + hot / 2 + 0.625]
    assert len(units) == 3 * len(room.row_units())
    n = len(room.row_units())
    for w, y in ((cold, 0.0), (hot, dy)):
        assert len([p for p in placed if p.name == room.roof_name(w) and abs(p.origin[1] - y) < 1e-9]) == n
        assert len([p for p in placed if p.name == room.door_name(w) and abs(p.origin[1] - y) < 1e-9]) == 2
    # row B is shared: its backs face the hot aisle (yaw 2 faces -y, the cold aisle)
    assert {p.yaw for p in units if abs(p.origin[1] - rows[1]) < 1e-9} == {2}
    # the floor covers the hall exactly once
    x0, x1, y0, y1 = room.hall_extent(cold, hot)
    area = sum(room.size(room.spec(p))[0] * room.size(room.spec(p))[1] for p in placed if room.spec(p).family == "floor")
    assert abs(area - (x1 - x0) * (y1 - y0)) < 1e-6
    cells = [room.world_cells(p) for p in placed if room.spec(p).family == "floor"]
    assert sum(len(c) for c in cells) == len(set().union(*cells))
