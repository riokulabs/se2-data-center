"""The room pieces' build menu (dc/menu.py), names (dc/names.py), costs (dc/recipes.py), initial unlock,
icons, and the mod's en-US texts (dc/texts.py) behind every display string.

Menu: four "Data Center" subcategory tiles after the cable trays, "Raised Floor" (Solid, Perforated:
0.5 / 1.0 m), "Room Cooling & Power" (CRAC, PDU Cabinet, Rack PDU Feed A / Feed B: 24U / 42U), "Aisle Containment"
(Door, Roof: 1.0 / 1.5 / 2.0 m aisles) and "Signs & Labels" (Aisle Sign, Hanging Aisle Sign, Rack Label). There are
no cable looms, so there is no loom tile."""
import json
import os

import pytest

try:
    from PIL import Image
except ImportError:   # the icon pixel checks need Pillow: they FAIL without it, never skip silently
    Image = None

from dc import catalog, clone, config, integration, menu, names, recipes, texts
from dc.assetio import read_json
from test_icons_menu import SDK, UI, alpha_bbox, png_info, report

ROOM = [b for b in catalog.BLOCKS if b.family in catalog.ROOM_FAMILIES]
ROOM_GROUPS = ("floor", "roompower", "contain", "signs")
WANT = {   # group -> [(kind key, [the kind's blocks in size order])]
    "floor": [("Solid", ["DC_Floor_Solid_050", "DC_Floor_Solid_100"]),
              ("Perf", ["DC_Floor_Perf_050", "DC_Floor_Perf_100"])],
    "roompower": [("CRAC", ["DC_CRAC"]), ("Cabinet", ["DC_PDU_Cabinet"]),
                  ("A", ["DC_PDU_Rack24_A", "DC_PDU_Rack42_A"]), ("B", ["DC_PDU_Rack24_B", "DC_PDU_Rack42_B"])],
    "contain": [("Door", ["DC_Contain_Door_100", "DC_Contain_Door_150", "DC_Contain_Door_200"]),
                ("Roof", ["DC_Contain_Roof_100", "DC_Contain_Roof_150", "DC_Contain_Roof_200"])],
    "signs": [("Aisle", ["DC_Sign_Aisle"]), ("AisleHang", ["DC_Sign_AisleHang"]), ("Rack", ["DC_Sign_Rack"])],
}


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
def test_room_families_in_pipeline():
    """Every room family is wired into the pipeline (menu, recipe, icon, unlock): BLOCKS == the whole catalogue,
    nothing is staged outside it, and no loom family exists."""
    assert set(catalog.ROOM_FAMILIES) <= set(catalog.PIPELINE_FAMILIES)
    assert catalog.BLOCKS == catalog.CATALOGUE == catalog.STAGED
    assert len(ROOM) == 19 and "loom" not in menu.GROUPS and not hasattr(menu, "LOOM_ORDER")
    assert all(menu.group(b) in ROOM_GROUPS for b in ROOM)


def test_room_groups(staged):
    """Each new group is staged in the Data Center subcategory under its name, after the cable-tray tiles, and holds
    exactly its kinds in menu order (OrderingPriority 1..n), each kind's blocks in size order; every room kind is in
    exactly one group (none left in a cloned vanilla tile); the initial unlock lists every room block and kind."""
    sub = stage(menu.SUBCATEGORY["file"])["$Value"]
    groups = {g: stage(menu.GROUPS[g]["file"])["$Value"] for g in ROOM_GROUPS}
    assert [groups[g]["Name"] for g in ROOM_GROUPS] == ["Raised Floor", "Room Cooling & Power", "Aisle Containment",
                                                        "Signs & Labels"]
    for v in groups.values():
        assert [s["Value"] for s in v["Subcategories"]] == [sub["Guid"]]
    orders = [menu.GROUPS[g]["order"] for g in menu.GROUPS]
    assert orders == sorted(orders) and len(set(orders)) == len(orders)
    assert min(menu.GROUPS[g]["order"] for g in ROOM_GROUPS) > menu.GROUPS["traysupport"]["order"]
    guid_to_group = {v["Guid"]: g for g, v in groups.items()}
    listed = {g: [] for g in ROOM_GROUPS}
    for b in ROOM:
        k = kind_def(b)
        owner = menu.kind_owner(b)
        assert block_def(b)["BlockKind"] == clone.entry(owner)["info"]["kind"], b.name
        if owner is not b:
            assert k["BlockGroups"] == [] and k["OrderingPriority"] == 0, f"{b.name}: its own clone kind is inert"
            continue
        gs = [guid_to_group.get(e["Value"]) for e in k["BlockGroups"]]
        assert gs == [menu.group(b)], f"{b.name}: in {k['BlockGroups']}"
        assert (k["Name"], k["Description"]) == menu.kind_text(b)
        listed[gs[0]].append((k["OrderingPriority"], menu.kind_key(b), [x.name for x in menu.kind_blocks(b)]))
    got = {g: [(key, blocks) for _, key, blocks in sorted(v)] for g, v in listed.items()}
    assert got == WANT
    for g, v in listed.items():
        assert [p for p, _, _ in sorted(v)] == list(range(1, len(v) + 1)), g
    unlock = stage(integration.UNLOCK_FILE)["$Value"]["Manipulator"]
    for b in ROOM:
        info = clone.entry(b)["info"]
        assert info["server_prefab"] in unlock["Blocks"]["Added"], b.name
        assert clone.entry(menu.kind_owner(b))["info"]["kind"] in unlock["BlockKinds"]["Added"], b.name


def test_room_kind_sizes():
    """The sizes of each multi-size kind (DisplaySize = the largest cell extent x 0.25 m) are distinct, in order."""
    want = {"DC_Floor_Solid_100": (0.5, 1.0), "DC_Floor_Perf_100": (0.5, 1.0),
            "DC_Contain_Door_200": (2.5, 3.0, 4.0), "DC_Contain_Roof_200": (1.0, 1.5, 2.0),
            "DC_PDU_Rack42_A": (1.0, 2.0), "DC_PDU_Rack42_B": (1.0, 2.0)}
    for owner, sizes in want.items():
        o = catalog.BY_NAME[owner]
        got = tuple(menu.display_size(b) for b in menu.kind_blocks(o))
        assert got == sizes, owner
        assert len(set(got)) == len(got)
    for b in ROOM:
        if menu.owns_kind(b) and b.name not in want:
            assert menu.kind_blocks(b) == [b], b.name


def test_room_names():
    """Every room block has a block name and description; each multi-size kind its own tile text (no size in it)."""
    for b in ROOM:
        title, desc = names.NAMES[b.name]
        assert title and len(desc) > 30, b.name
    for o in {menu.kind_owner(b) for b in ROOM}:
        if len(menu.kind_blocks(o)) > 1:
            title = names.KIND_NAMES[o.name][0]
            assert not any(t in title for t in (" 0.5 m", " 1.0 m", "42U", "24U", "2.0 m")), title


def test_no_size_in_block_names():
    """User request 2026-10-20: a block's display name carries no rack units or size; the build menu's size selector
    tells a kind's sizes apart, and the descriptions keep the size. Two blocks share a name only inside one kind."""
    import re
    size = re.compile(r"\b\d+U\b|\b\d+(\.\d+)? m\b|\b(Short|Long) \(")
    owners = {}
    for b in catalog.BLOCKS:
        title, desc = names.NAMES[b.name]
        assert not size.search(title), (b.name, title)
        owners.setdefault(title, set()).add(menu.kind_owner(b).name)
    assert {t: o for t, o in owners.items() if len(o) > 1} == {}, "two kinds share a display name"
    assert names.NAMES["DC_Rack24_Open"][0] == names.NAMES["DC_Rack42_Open"][0] == "Server Rack (Open Frame)"
    assert names.NAMES["DC_Srv_UPS"][0] == "UPS" and names.NAMES["DC_Srv_KVM"][0] == "KVM Console"
    assert names.NAMES["DC_PDU_Rack24_B"][0] == "Rack PDU (Feed B)"
    assert "42U" in names.NAMES["DC_Rack42_Open"][1] and "6U" in names.NAMES["DC_Srv_KVM"][1]


# ---------------------------------------------------------------------------------------------- costs
def test_room_costs(staged):
    """Every room block is costed by our rule, the game would not multiply our recipe (scale 1), a wider door costs at
    least a narrower one, the CRAC keeps the gyroscope's motors (its fans), Solid and Perforated tiles of one size cost
    the same, and the staged block definition points at the staged recipe."""
    t = recipes.table(report())
    for b in ROOM:
        assert recipes.costed(b), b.name
        c = recipes.cost(b, report())
        assert c["game_scale"] == 1, f"{b.name}: the game would multiply our recipe by {c['game_scale']}"
        assert all(a >= 1 for _, a in c["critical"] + c["optional"]), b.name
        r = staged["blocks"][b.name]["recipe"]
        assert r and block_def(b)["Recipe"] == r["guid"], b.name

    def total(n):
        return sum(a * recipes.ITEMS[i][1] for i, a in t[n]["critical"] + t[n]["optional"])
    assert total("DC_Contain_Door_200") >= total("DC_Contain_Door_150") >= total("DC_Contain_Door_100")
    assert total("DC_Contain_Roof_200") >= total("DC_Contain_Roof_100")
    assert any(i == "Motor" for i, _ in t["DC_CRAC"]["critical"])
    for k in ("050", "100"):
        assert t[f"DC_Floor_Solid_{k}"]["critical"] == t[f"DC_Floor_Perf_{k}"]["critical"]
        assert t[f"DC_Floor_Solid_{k}"]["optional"] == t[f"DC_Floor_Perf_{k}"]["optional"]
    # a containment door is the wall-panel frame plus one sliding-door mechanism (its two leaves share one slide)
    door = dict(t["DC_Contain_Door_100"]["critical"])
    assert recipes.door_sides(catalog.BY_NAME["DC_Contain_Door_100"]) == 1
    assert (door["Motor"], door["ElectronicParts"]) == (2, 1)


def test_room_cost_balance():
    """Room balance (recipes module doc): signs pay one vanilla LCD50 recipe per screen face (vanilla prices
    LCDs per screen: the hanging sign's two faces = vanilla's LCD500, never the 3.4x the volume rule gave); the CRAC
    and the PDU cabinet pay the 42U open rack's frame plus their own kit, so the decorative cabinet never needs more
    steel than (or costs as much as) the powered CRAC; and no rack costs less than any server it holds."""
    t = recipes.table(report())

    def total(n):
        return sum(a * recipes.ITEMS[i][1] for i, a in t[n]["critical"] + t[n]["optional"])

    def steel(n):
        return sum(a for i, a in t[n]["critical"] + t[n]["optional"] if i == "SteelPlate")

    lcd = recipes.SOURCES["LCDNarrow50"]
    for v, f in (("Aisle", 1), ("AisleHang", 2), ("Rack", 1)):
        c = t[f"DC_Sign_{v}"]
        assert c["critical"] == [(i, a * f) for i, a in lcd["critical"]], v
        assert c["optional"] == [(i, a * f) for i, a in lcd["optional"]], v
    lcd50 = recipes.set_mass(lcd["critical"]) + recipes.set_mass(lcd["optional"])
    assert total("DC_Sign_AisleHang") == 2 * lcd50 and total("DC_Sign_Rack") == lcd50
    # the in-row units: the frame's steel, and the powered CRAC dearer than the decorative cabinet
    frame = t[recipes.INROW_FRAME]
    for n in ("DC_CRAC", "DC_PDU_Cabinet"):
        assert steel(n) == steel(recipes.INROW_FRAME), n
        assert total(n) > total(recipes.INROW_FRAME), n
        assert t[n]["optional"] == frame["optional"], n
    assert steel("DC_PDU_Cabinet") <= steel("DC_CRAC") and total("DC_PDU_Cabinet") < total("DC_CRAC")
    assert dict(t["DC_CRAC"]["critical"])["Motor"] == 3
    # the frame floor: every rack >= the dearest server; the half open rack is the one it lifts (+1 plate)
    servers = [b.name for b in catalog.BLOCKS if b.family == "server"]
    racks = [b.name for b in catalog.BLOCKS if b.family == "rack"]
    assert min(total(r) for r in racks) >= max(total(s) for s in servers)
    assert t["DC_Rack24_Open"]["critical"] == [("SteelPlate", 6), ("Construction", 4)]
    assert t["DC_Rack24_Open"]["optional"] == [("SteelPlate", 5)]
    for n, c in t.items():
        assert c["game_scale"] == 1, n


def test_every_staged_block_has_a_recipe_decision(staged):
    """No staged block ships with its clone's vanilla recipe by accident: every staged block is
    costed (patched recipe) and has a staged recipe file."""
    for b in catalog.STAGED:
        r = staged["blocks"][b.name]["recipe"]
        assert r, f"{b.name}: no recipe patched (it would keep {b.copy_from}'s)"
        assert os.path.exists(os.path.join(config.STAGE_ASSETS, r["file"])), b.name


# ---------------------------------------------------------------------------------------------- icons
@pytest.mark.parametrize("b", ROOM, ids=lambda b: b.name)
def test_room_icons(staged, b):
    """Source/Model/UI/<name>_Icon.png: 200 x 200 8-bit RGBA, no ICC profile, a subject that fills the tile without
    touching its edge; staged as the block's UIData.Icon."""
    icon = os.path.join(UI, f"{b.name}_Icon.png")
    assert os.path.exists(icon), icon
    w, h, ctype, depth, chunks, _ = png_info(icon)
    assert (w, h) == (200, 200) and (ctype, depth) == (6, 8)
    assert "iCCP" not in chunks
    box = alpha_bbox(icon)
    assert box, "icon is empty"
    x0, y0, x1, y1 = box
    assert x0 > 0 and y0 > 0 and x1 < 199 and y1 < 199, f"icon touches the frame edge: {box}"
    assert max(x1 - x0, y1 - y0) >= 80, f"icon subject too small: {box}"
    ui = block_def(b)["UIData"]
    assert ui["Icon"] == staged["blocks"][b.name]["icon"]
    assert ui["Icon"] == "{G}" + integration.asset_id(f"{config.NAME}/{b.name}/UI/{b.name}_Icon.png")


def test_room_icons_distinct():
    """No two room icons are the same picture (the variants must read apart)."""
    if Image is None:
        pytest.fail("Pillow is needed for the icon pixel check")
    seen = {}
    for b in ROOM:
        data = Image.open(os.path.join(UI, f"{b.name}_Icon.png")).convert("RGBA").tobytes()
        assert data not in seen, f"{b.name} looks exactly like {seen.get(data)}"
        seen[data] = b.name


# ---------------------------------------------------------------------------------------------- localisation
def _vanilla_texts():
    base = os.path.join(SDK, "MainMenuData", "Texts", "en-US")
    out = {}
    for f in os.listdir(base):
        if f.endswith(".loc-texts"):
            with open(os.path.join(base, f), encoding="utf-8-sig") as fh:
                out.update(json.load(fh))
    return out


def test_every_display_string_has_a_text(staged):
    """Every Name / Description / Tooltip / UIData.Name the package stages (a LocKey TextId in game) has an entry in
    the mod's en-US texts (or is a vanilla key), so neither the definition validation ("Unrecognized value") nor the
    UI ("LOCALIZATION WARNING: Could not find key") reports it; the keys are the English texts themselves, so a lookup
    that misses still shows the right words; no key of ours shadows a vanilla one."""
    loc = stage(texts.LOC_FILE)
    assert staged["texts"]["keys"] == len(loc)
    assert all(k == v for k, v in loc.items())
    vanilla = _vanilla_texts() if os.path.isdir(SDK) else {}
    found = texts.staged_strings()
    missing = {t: p[:2] for t, p in found.items() if t not in loc and t not in vanilla}
    assert not missing, missing


def test_no_text_shadows_vanilla(staged):
    """A mod key equal to a vanilla key overwrites vanilla's text (LocalizationPackage.cs:228-235, last writer wins),
    so none of ours may match one. Needs the SDK's vanilla texts: skipped loudly without them, never passed silently."""
    if not os.path.isdir(SDK):
        pytest.skip(f"SDK texts not found at {SDK}: cannot check our keys against vanilla's")
    loc, vanilla = stage(texts.LOC_FILE), _vanilla_texts()
    assert not set(loc) & set(vanilla), sorted(set(loc) & set(vanilla))
    # the strings the log flagged, and every room name, group and kind tile
    for t in ("Data Center", "Programmable Server", menu.SUBCATEGORY["tooltip"]):
        assert t in loc, t
    for g in menu.GROUPS.values():
        assert g["name"] in loc
    for b in catalog.BLOCKS:
        assert names.NAMES[b.name][0] in loc, b.name
        if menu.owns_kind(b):
            assert all(x in loc for x in menu.kind_text(b)), b.name


def test_display_strings_cover_the_lockey_members():
    """display_strings reads the members the game validates as LocKeys (the warnings' $Root.Name.TextId,
    $Root.Description.TextId, $Root.Tooltip.TextId, $Root.UIData.Name.TextId) and skips Override partials."""
    kind = {"$Type": "Game2:Keen.Game2.Simulation.StreamedUI.Categories.BlockKindDefinitionObjectBuilder",
            "$Value": {"Guid": "g", "Name": "N", "Description": "D"}}
    sub = {"$Type": "Game2:Keen.Game2.Simulation.StreamedUI.Categories.SubcategoryDefinitionObjectBuilder",
           "$Value": {"Guid": "g", "Name": "S", "Tooltip": "T"}}
    blk = {"$Type": "VRage:Keen.VRage.ContentPipeline.Definitions.PartialDefinitionDiff",
           "$Value": {"BaseDefinition": "b", "PartialDefinitionKind": "Copy", "Manipulator": {"Guid": "g", "UIData":
                      {"Name": "B"}}, "DefinitionType": "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks."
                                                        "PowerableBlockDefinition"}}
    ov = {"$Type": "VRage:Keen.VRage.ContentPipeline.Definitions.PartialDefinitionDiff",
          "$Value": {"BaseDefinition": "b", "PartialDefinitionKind": "Override", "Manipulator": {"UIData": {"Name": "X"}}}}
    assert texts.display_strings(kind) == [("Name", "N"), ("Description", "D")]
    assert texts.display_strings(sub) == [("Name", "S"), ("Tooltip", "T")]
    assert texts.display_strings(blk) == [("UIData.Name", "B")]
    assert texts.display_strings(ov) == []


def test_culture_definition(staged):
    """The en-US culture definition: the vanilla en-US CultureId, one resource (our content ID, unique in the culture)
    pointing at the staged .loc-texts asset; both staged with .meta files."""
    d = stage(texts.DEF_FILE)
    assert d["$Type"] == texts.T_CULTURE
    v = d["$Value"]
    assert v["CultureId"] == texts.EN_US
    [r] = v["Resources"]
    assert r["Value"]["ContentId"] == texts.CONTENT_ID
    assert r["Value"]["Asset"] == "{G}" + integration.asset_id(texts.LOC_FILE)
    assert integration.asset_id(texts.DEF_FILE) == v["Guid"]
    if os.path.isdir(SDK):
        en = read_json(os.path.join(SDK, "MainMenuData", "Texts", "en-US.def"))["$Value"]
        assert en["CultureId"] == texts.EN_US
        assert texts.CONTENT_ID not in {x["Value"]["ContentId"] for x in en["Resources"]}
        cid = read_json(os.path.join(SDK, "MainMenuData", "Texts", "CultureIdentifiers", "ID_en-US.def"))["$Value"]
        assert (cid["Guid"], cid["CultureId"]) == (texts.EN_US, "en-US")
