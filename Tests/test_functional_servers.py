"""Task 6: the timer, event-controller and status-display servers behave as their vanilla blocks.

The vanilla values are read from tools/vanilla-ref (read-only hard links of the SDK) with json, never copied.

Mesh-part naming (dc/functional.py): the NonFractured model's mesh parts are its material slots; since Plan 2 Task 9b
the Fractured and Damaged models are fractured like vanilla's, so their parts are "<group>-<material>" with the lamps
in the zones' "Fracture_NN_Hide" groups. Vanilla's IndicatorMeshParts list both forms ("EmissiveOff",
"Fracture_01_Hide-EmissiveOff", ...). So "our indicator parts == vanilla's" is checked on vanilla's unfractured names,
and every fractured lamp part of ours must be one vanilla lists (else the lamp would stay dark once damaged).
"""
import json
import os

import pytest

from dc import catalog, clone, config, functional, integration
from dc.assetio import read_json

VREF = os.path.join(config.VANILLA_REF, "Blocks")
INDICATOR_SRC = {
    "DC_Srv_Timer": "Timer/50/Timer50_TimerBlockIndicatorDefinition.partialdef",
    "DC_Srv_EventCtl": "EventController/100/EventController_Client_EventControllerIndicatorDefinition.def",
}
LCD_SRC = "LCDPanels/LCD/50/LCDFlat50LcdMultiPanelDefinition.partialdef"
LCD_BMD_SRC = "LCDPanels/LCD/50/LCDFlat50_BlockModelDefinition.partialdef"
FUNCTIONAL = ("DC_Srv_Timer", "DC_Srv_EventCtl", "DC_Srv_Status")


def _vanilla(rel):
    p = os.path.join(VREF, rel)
    if not os.path.exists(p):
        pytest.skip(f"tools/vanilla-ref missing {rel}")
    with open(p) as f:
        return json.load(f)["$Value"]


def _body(v):
    return v.get("Manipulator", v)


def _list(x):
    """A plain list, or a delta-encoded list on an empty template ("Added")."""
    return x["Added"] if isinstance(x, dict) else x


def _report(name):
    rep = read_json(config.REPORT_PATH)["blocks"]
    e = rep.get(name, {})
    assert e.get("placement", {}).get("total"), f"{name} not built (build_dc.py)"
    return e


def _manifest(name):
    return read_json(os.path.join(config.MODELS_DIR, name, "export.json"))


def _lod0_parts(name):
    """LOD0 material slots of every model the indicator recolours: the build's LOD0 slots, the exported
    NonFractured, Fractured and Damaged LOD0."""
    m = _manifest(name)
    return {"build": set(_report(name)["mesh_parts"]),
            "nonfractured": set(m["nonfractured"]["lods"][0]["materials"]),
            "fractured": set(m["fractured"]["lods"][0]["materials"]),
            "damaged": set(m["damaged"]["lods"][0]["materials"])}


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


# ---------------------------------------------------------------------------------------------- indicators
@pytest.mark.parametrize("name", sorted(INDICATOR_SRC))
def test_indicator_parts_match_vanilla(staged, name):
    vanilla = _list(_body(_vanilla(INDICATOR_SRC[name]))["IndicatorMeshParts"])
    plain = {p for p in vanilla if "-" not in p}                    # unfractured mesh-part names
    by_group = {p.split("-", 1)[1] for p in vanilla if "-" in p}    # "<Fracture_NN_x>-<material>"
    assert plain == set(functional.INDICATOR_PARTS[name]), (plain, functional.INDICATOR_PARTS[name])
    assert by_group <= plain, by_group - plain
    for where, parts in _lod0_parts(name).items():
        ours = {p for p in parts if p in plain or p.startswith("Emissive")}
        assert ours == plain, (name, where, sorted(parts))
    fractured = {p for p in _manifest(name)["fractured"]["parts"] if "-" in p and p.split("-", 1)[1] in plain}
    assert fractured and all(p.split("-", 1)[0].endswith("_Hide") for p in fractured), sorted(fractured)
    # the staged indicator lists every one of them: vanilla's names, plus (Task 9c) the lamp parts of a zone vanilla
    # does not have (a 6U server's third zone, Fracture_03_Hide-<slot>)
    rel = integration._block_files(catalog.BY_NAME[name], "IndicatorDefinition")[0]
    listed = set(_list(_body(read_json(os.path.join(config.STAGE_ASSETS, rel))["$Value"])["IndicatorMeshParts"]))
    assert set(vanilla) <= listed and fractured <= listed, sorted(fractured - listed)


@pytest.mark.parametrize("name", sorted(INDICATOR_SRC))
def test_indicator_lamps_at_range(name):
    """The state stays visible at range: indicator parts in every LOD but the LastLOD box."""
    m = _manifest(name)
    for variant in ("nonfractured", "fractured", "damaged"):
        for i, lod in enumerate(m[variant]["lods"][:-1]):
            assert set(functional.INDICATOR_PARTS[name]) <= set(lod["materials"]), (variant, i, lod["materials"])


@pytest.mark.parametrize("name", sorted(INDICATOR_SRC))
def test_indicator_definition_targets_our_models(name, staged):
    """The staged indicator keeps vanilla's states, materials, overrides and mesh parts; ReplacementModels changes, to
    our NonFractured, Fractured and Damaged models (vanilla Timer50 lists its three), and (Task 9c) the mesh parts
    gain only our Fractured model's lamp parts that vanilla's list lacks (a 6U server's third zone)."""
    spec = catalog.BY_NAME[name]
    files = integration._block_files(spec, "IndicatorDefinition")
    ours = _body(read_json(os.path.join(config.STAGE_ASSETS, files[0]))["$Value"])
    van = _body(_vanilla(INDICATOR_SRC[name]))
    for k in ("DefaultMaterials", "MeshPartMaterialOverrides"):
        assert ours.get(k) == van.get(k), k
    extra = set(_list(ours["IndicatorMeshParts"])) - set(_list(van["IndicatorMeshParts"]))
    assert _list(ours["IndicatorMeshParts"])[:len(_list(van["IndicatorMeshParts"]))] == _list(van["IndicatorMeshParts"])
    assert extra <= set(_manifest(name)["fractured"]["parts"]), sorted(extra)
    bmd = read_json(os.path.join(config.STAGE_ASSETS, clone.entry(spec)["info"]["model_def_file"]))
    m = bmd["$Value"]["Manipulator"]
    assert _list(ours["ReplacementModels"]) == [m["Model"], m["FractureModel"], m["DamagedModel"]]
    assert m["DamagedModel"] != m["FractureModel"]


def test_indicator_slots_default_to_vanilla_material():
    """The indicator slots' default material (the .model assignment) is vanilla's EmissiveOff, as in Timer50.model
    and EventController100.model; the screen slot maps as in Timer50.model."""
    for name, rel in (("DC_Srv_Timer", "Timer/50/Models/NonFractured/Timer50.model"),
                      ("DC_Srv_EventCtl", "EventController/100/Models/NonFractured/EventController100.model")):
        van = {a["MaterialName"]: a["MaterialReference"] for a in _vanilla(rel)["MaterialAssignments"]}
        ma = read_json(os.path.join(config.STAGE_ASSETS, config.NAME, name, "Models", "NonFractured",
                                    f"{name}.model"))["$Value"]
        ours = {a["MaterialName"]: a["MaterialReference"] for a in ma["MaterialAssignments"]}
        for slot in functional.INDICATOR_PARTS[name] + ((functional.TERMINAL_SCREEN,) if name == "DC_Srv_Timer"
                                                       else ()):
            assert ours[slot] == van[slot], (name, slot)


# ---------------------------------------------------------------------------------------------- status LCD
def test_status_has_lcd_surface(staged):
    """The status model has the LCD surface mesh part named as LCDFlat50's surface, in every model and LOD but the
    last; the staged surface keeps that name; the interaction dummy keeps LCDFlat50's name and type."""
    name = "DC_Srv_Status"
    van_part = _list(_body(_vanilla(LCD_SRC))["Surfaces"]["Changed"])[0]["Value"]["MeshPartName"]
    assert van_part == functional.LCD_SURFACE
    for where, parts in _lod0_parts(name).items():
        assert van_part in parts, (where, parts)
    m = _manifest(name)
    for variant in ("nonfractured", "fractured", "damaged"):
        for lod in m[variant]["lods"][:-1]:
            assert van_part in lod["materials"], (variant, lod)
    spec = catalog.BY_NAME[name]
    lcd = read_json(os.path.join(config.STAGE_ASSETS, integration._block_files(spec, "LcdMultiPanelDefinition")[0]))
    surf = lcd["$Value"]["Manipulator"]["Surfaces"]["Changed"][0]["Value"]
    assert surf["MeshPartName"] == van_part
    a, b = functional.STATUS_SCREEN["a"], functional.STATUS_SCREEN["b"]
    assert surf["AspectRatio"] == pytest.approx((a[1] - a[0]) / (b[1] - b[0]), rel=1e-6)
    assert surf["Resolution"]["X"] / surf["Resolution"]["Y"] == surf["AspectRatio"]
    van_dummies = {c["Value"]["Name"]: c["Value"]["Type"] for c in _body(_vanilla(LCD_BMD_SRC))["Dummies"]["Changed"]}
    bmd = read_json(os.path.join(config.STAGE_ASSETS, clone.entry(spec)["info"]["model_def_file"]))
    ours = {c["Value"]["Name"]: c["Value"]["Type"] for c in bmd["$Value"]["Manipulator"]["Dummies"]["Changed"]}
    assert ours == van_dummies


# ---------------------------------------------------------------------------------------------- interaction
@pytest.mark.parametrize("name", FUNCTIONAL + ("DC_Srv_KVM", "DC_Srv_Programmable"))
def test_interaction_dummy_on_face(name, staged):
    """The terminal / LCD dummy sits on our front face (game -z), inside the face's width and height."""
    spec = catalog.BY_NAME[name]
    bmd = read_json(os.path.join(config.STAGE_ASSETS, clone.entry(spec)["info"]["model_def_file"]))
    dums = {c["Value"]["Name"]: c["Value"] for c in bmd["$Value"]["Manipulator"]["Dummies"]["Changed"]}
    for dn in functional.DUMMIES[name]:
        t = dums[dn]["Transform"]["Transform"]
        x, y, z = (t["Position"][k] for k in "XYZ")
        sx, sy, _ = (dums[dn]["Scale"][k] for k in "XYZ")
        assert t["Orientation"] == {"X": 0, "Y": 0, "Z": 0, "W": 1}
        assert -0.39 <= z <= -0.35, z                                   # the front plane: game z = -0.375
        assert 0.125 - 0.25 <= x - sx / 2 and x + sx / 2 <= 0.125 + 0.25, (x, sx)
        assert -0.125 <= y - sy / 2 and y + sy / 2 <= 0.125, (y, sy)


@pytest.mark.parametrize("name", FUNCTIONAL + ("DC_Srv_KVM", "DC_Srv_Programmable"))
def test_functional_server_mounts_like_deco(name, staged):
    info = clone.entry(catalog.BY_NAME[name])["info"]
    bd = read_json(os.path.join(config.STAGE_ASSETS, info["block_def_file"]))["$Value"]["Manipulator"]
    assert bd["MountPointGeneratorSettings"]["Directions"] == integration.SERVER_MOUNTS
