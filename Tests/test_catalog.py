import os

from dc import catalog, config


def test_names_unique_and_prefixed():
    names = [b.name for b in catalog.CATALOGUE]
    assert all(n.startswith("DC_") for n in names)
    assert len(set(names)) == len(names)


def test_sizes():
    # cable tray piece table: (along X, up Z, across Y)
    tray_cells = {"StraightS": (2, 1, 2), "StraightL": (6, 1, 2), "TurnH": (3, 1, 3), "TurnUp": (2, 2, 2),
                  "TurnDown": (2, 2, 2), "Tee": (4, 1, 3), "Cross": (4, 1, 4), "Reducer": (2, 1, 2),
                  "Drop": (4, 3, 3), "Chute": (4, 5, 1)}
    rods = {"DC_TrayRods_025": 1, "DC_TrayRods_100": 4, "DC_TrayRods_200": 8}
    room_cells = {
        "floor": lambda b: {"050": (2, 1, 2), "100": (4, 1, 4)}[b.name[-3:]],
        "crac": lambda b: (4, 10, 5),
        "pdu_cabinet": lambda b: (4, 10, 5),
        "pdu_strip": lambda b: (1, 8 if "Rack42" in b.name else 4, 1),
        "contain_door": lambda b: ({"100": 8, "150": 12, "200": 16}[b.name[-3:]], 10, 1),
        "contain_roof": lambda b: (4, 1, {"100": 4, "150": 6, "200": 8}[b.name[-3:]]),
        "sign": lambda b: {"Aisle": (4, 1, 1), "AisleHang": (4, 1, 2), "Rack": (2, 1, 1)}[b.variant],
    }
    for b in catalog.CATALOGUE:
        if b.family == "rack":
            assert b.cells[1] in (10, 5) and b.cells[0] == 4 and b.cells[2] == 5
        elif b.family == "server":
            assert b.cells[0] == 2 and b.cells[2] == 3
        elif b.family == "tray":
            assert b.cells == tray_cells[b.variant], b.name
        elif b.family == "trayrods":
            assert b.cells == (2, rods[b.name], 2), b.name
        else:   # room pieces (Tests/test_room_layout.py checks the whole row)
            assert b.cells == room_cells[b.family](b), b.name
    assert catalog.BY_NAME["DC_Srv_UPS"].cells[1] == 2


def test_pipeline_view():
    """BLOCKS is the pipeline's view of the catalogue: exactly the wired families, in catalogue order."""
    assert catalog.BLOCKS == [b for b in catalog.CATALOGUE if b.family in catalog.PIPELINE_FAMILIES]
    assert set(catalog.BY_NAME) == {b.name for b in catalog.CATALOGUE}


def test_sources_exist():
    for b in catalog.CATALOGUE:
        assert b.vanilla_source.startswith("Blocks/")
        assert os.path.isdir(os.path.join(config.VANILLA_REF, b.vanilla_source)), b.vanilla_source


def test_bounds():
    """placement.analyse takes INCLUSIVE cell indices where cell i has centre 0.25*i (game frame). Welder400 is
    10x10x16 cells at -4..5, -4..5, -7..8: the even extra cell goes on the + side. So lo = -((n-1)//2) and
    hi = lo + n - 1; odd n is symmetric (3 -> -1..1, 5 -> -2..2)."""
    from dc.catalog import BlockSpec, bounds
    assert bounds(BlockSpec("x", "rack", (10, 10, 16), None, None, "", False)) == ((-4, -4, -7), (5, 5, 8))
    assert bounds(BlockSpec("x", "rack", (3, 10, 5), None, None, "", False)) == ((-1, -4, -2), (1, 5, 2))
    assert bounds(catalog.BY_NAME["DC_Srv_UPS"]) == ((0, 0, -1), (1, 1, 1))
    assert bounds(catalog.BY_NAME["DC_Rack42_Open"]) == ((-1, -4, -2), (2, 5, 2))


def test_copy_from_matches_vanilla():
    for b in catalog.CATALOGUE:
        d = os.path.join(config.VANILLA_REF, b.vanilla_source)
        files = [f for f in os.listdir(d) if f.endswith(".partialdef")]
        assert any(f.startswith(b.copy_from) for f in files), b.name
        assert f"{b.copy_from}.partialdef" in files, b.name


def test_expand_globs():
    """check_placement.py takes one name or glob per argument."""
    import pytest
    from dc import catalog
    assert catalog.expand(["DC_*"]) == [b.name for b in catalog.CATALOGUE]
    assert catalog.expand(["DC_Tray_Turn?_Full", "DC_Srv_UPS", "DC_Srv_UPS"]) == \
        ["DC_Srv_UPS"] + [n for n in (b.name for b in catalog.CATALOGUE) if n.startswith("DC_Tray_Turn")
                          and n.endswith("_Full") and len(n) == len("DC_Tray_TurnH_Full")]
    with pytest.raises(ValueError, match="no block matches"):
        catalog.expand(["DC_Nope*"])
