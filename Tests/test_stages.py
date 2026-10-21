"""dc.construction: the BlockModelDefinition.BuildProgressModels generator, in the mod (Ruling DB-1). The stage-1.0
ApplyOnlyWhenDamaged hide names exactly the block's Scaffold-type mesh parts (Decision 2, audit G9: no scaffold -> an
empty last stage, as vanilla writes it), and the 4.0 presets the later tasks use (WindowGlass, SubpartConstruct)."""
import json
import os

import pytest

from dc import fracture as FR
from dc import catalog, config, construction as C, state_view as SV
from dc.assetio import read_json

PAINT = "Fracture_01-PaintedMetalColorable"
DEFAULT = (PAINT, ("Default", "AlwaysVisible", "Default"))
WINDOWGLASS = "83c075f5-f177-460d-94a7-8aca19fd4d6f"
SUBPART = "851d4d6e-9ec8-467f-87a5-06ef06e97336"
RATIOS = [0, 0.1, 0.2, 0.3, 0.5333, 0.7667, 1]


def _gen(parts, **kw):
    return C.generate_stages(dict(parts), "{G}m", "{G}f", "s", **kw)


def _changes(stages):
    """{(ratio, part): change value} over every stage."""
    return {(s["Value"]["BuildRatioLowerBound"], c["Value"]["MeshPart"]): c["Value"]
            for s in stages for c in s["Value"]["PartChanges"]["_data"]}


def test_no_scaffold_no_damaged_hide():
    parts = dict([DEFAULT])
    assert C.scaffold_parts(parts) == []
    assert _gen(parts)[-1]["Value"]["PartChanges"]["_data"] == []
    assert _gen(parts, damaged_hide=C.scaffold_parts(parts))[-1]["Value"]["PartChanges"]["_data"] == []


def test_damaged_hide_names_scaffold():
    parts = dict([DEFAULT, ("BrushedMetal", ("Scaffold", "AlwaysVisible", "Scaffolding"))])
    assert C.scaffold_parts(parts) == ["BrushedMetal"]
    last = _gen(parts, damaged_hide=C.scaffold_parts(parts))[-1]["Value"]
    assert last["BuildRatioLowerBound"] == 1 and last["Model"] == "{G}m"
    got = [{k: v for k, v in c["Value"].items() if k in ("MeshPart", "ShowPart", "ApplyOnlyWhenDamaged")}
           for c in last["PartChanges"]["_data"]]
    assert got == [{"MeshPart": "BrushedMetal", "ShowPart": False, "ApplyOnlyWhenDamaged": True}]
    c = last["PartChanges"]["_data"][0]["Value"]
    assert c["SetMaterial"] is None and c["ResetToSkinMaterial"] is False


def test_scaffold_parts_sorted_and_typed():
    parts = {"Z": ("Scaffold", "AlwaysVisible", "Scaffolding"), "A": ("Scaffold", "AlwaysVisible", "Scaffolding"),
             "M": ("Default", "AlwaysVisible", "Default"), "S": ("Split", "HiddenUntilSecondSequenceStart", "Fracture")}
    assert C.scaffold_parts(parts) == ["A", "Z"]


@pytest.mark.parametrize("preset,mat", [("WindowGlass", WINDOWGLASS), ("SubpartConstruct", SUBPART)])
def test_new_presets_timing(preset, mat):
    parts = dict([DEFAULT, ("Fracture_01-X", ("Default", "AlwaysVisible", preset))])
    st = _gen(parts)
    ch = _changes(st)
    assert ch[(0, "Fracture_01-X")]["SetMaterial"] == mat
    assert ch[(0.3, "Fracture_01-X")]["SetMaterial"] == mat
    assert [s["Value"]["BuildRatioLowerBound"] for s in st] == RATIOS
    assert [s["Value"]["BuildRatioLowerBound"] for s in _gen(dict([DEFAULT]))] == RATIOS


def test_presets_match_sdk_names():
    """The preset table: today's five plus the two 4.0 presets with a user (GratingMetallic has none: left out)."""
    assert set(C.PRESETS) == {"default", "fracture", "support", "scaffolding", "conveyor_port",
                              "windowglass", "subpartconstruct"}
    assert C.PRESETS["windowglass"] == {"T": [WINDOWGLASS], "S": [WINDOWGLASS]}
    assert C.PRESETS["subpartconstruct"] == {"T": [SUBPART], "S": [SUBPART]}


def test_unknown_preset_raises():
    """Task 2 review M3: a mistyped preset ("WindowGlas") raises instead of silently building with no materials; no
    preset (None / "") stays the plain no-material form."""
    with pytest.raises(KeyError, match="WindowGlas"):
        _gen(dict([DEFAULT, ("Fracture_01-X", ("Default", "AlwaysVisible", "WindowGlas"))]))
    for none in (None, ""):
        st = _gen(dict([DEFAULT, ("Fracture_01-X", ("Default", "AlwaysVisible", none))]))
        assert (0, "Fracture_01-X") not in _changes(st)


def _vanilla_last_stage_lists():
    root = os.path.join(config.VANILLA_REF, "Blocks")
    if not os.path.isdir(root):
        pytest.skip("tools/vanilla-ref/Blocks missing (the SDK's read-only vanilla definitions)")
    out = []

    def walk(o, f):
        if isinstance(o, dict):
            bpm = o.get("BuildProgressModels")
            if isinstance(bpm, list) and bpm:
                out.append((f, bpm[-1]["Value"]["PartChanges"]["_data"]))
            for v in o.values():
                walk(v, f)
        elif isinstance(o, list):
            for v in o:
                walk(v, f)

    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                with open(os.path.join(dp, f)) as fh:
                    try:
                        walk(json.load(fh), f)
                    except ValueError:
                        continue
    return out


def test_empty_last_stage_form_is_vanilla():
    """G9: an empty last-stage PartChanges is a form vanilla 4.0 itself ships (so a block without a scaffold writes [],
    not a hide naming a part it lacks)."""
    lists = _vanilla_last_stage_lists()
    assert lists, "no vanilla BuildProgressModels found under tools/vanilla-ref/Blocks"
    empty = [f for f, d in lists if d == []]
    assert empty, ("no vanilla 4.0 BuildProgressModels ends with an empty PartChanges: emit the hide-less form "
                   "vanilla uses")


@pytest.mark.build
def test_installed_stages_regenerate():
    """B5: the installed stages are exactly what dc.construction generates from export.json's FR LOD0 parts with the
    block's seed and its installed Model / FractureModel refs."""
    for b in catalog.BLOCKS:
        man = read_json(os.path.join(config.MODELS_DIR, b.name, "export.json"))
        parts = {k: tuple(v) for k, v in man["fractured"]["parts"].items()}
        bmd = SV.installed_bmd(b.name)
        want = C.generate_stages(parts, bmd["Model"], bmd["FractureModel"], seed=f"datacenter/{b.name}",
                                 damaged_hide=C.scaffold_parts(parts))
        assert SV.installed_stages(b.name) == want, b.name


@pytest.mark.build
def test_installed_stages_match_baseline_except_last():
    """R3: moving the generator changed only the stage-1.0 hide (the stray "Chrome" is gone); every other stage is
    the baseline's, byte for byte under the hash, and the last stage keeps its ratio and model. Task 5 (G11): the
    roofs' glass builds as glass, so their hash moved (test_construction_roles.test_roof_glass_builds_as_glass).
    Task 6: the scaffold's own changes (BrushedMetal_Scaffold at 0, hidden at 0.3) are new; with them taken out the
    installed stages are the baseline's, and the last stage hides exactly the scaffold on a damaged finished block
    (vanilla's hand-added entry), or nothing on a block without one (the unfractured blocks and
    test_scaffold.NO_ROOM). The generator now writes every time as a float; INT_ZERO blocks had stage 0 keyed and
    ratioed from an int 0 in the baseline, so their stage 0 is compared in that form. Task 8: the support and stand-in
    parts (_role_and_standin_parts) are new and taken out likewise."""
    golden = read_json(SV.BASELINE_PATH)
    for b in catalog.BLOCKS:
        st = SV.installed_stages(b.name)
        man = read_json(os.path.join(config.MODELS_DIR, b.name, "export.json"))
        scaf = C.scaffold_parts({k: tuple(v) for k, v in man["fractured"]["parts"].items()})
        assert all(type(s["Value"]["BuildRatioLowerBound"]) is float for s in st[:-1]), b.name
        if b.name in INTERIOR_PARTS:   # (the parts as they were before the interior: regenerate without them)
            assert set(INTERIOR_PARTS[b.name]) <= set(man["fractured"]["parts"]), b.name
            man = {**man, "fractured": {**man["fractured"], "parts": {
                k: v for k, v in man["fractured"]["parts"].items() if k not in INTERIOR_PARTS[b.name]}}}
            if not _role_and_standin_parts(man):
                bmd = SV.installed_bmd(b.name)
                st = C.generate_stages({k: tuple(v) for k, v in man["fractured"]["parts"].items()}, bmd["Model"],
                                       bmd["FractureModel"], seed=f"datacenter/{b.name}", damaged_hide=scaf)
        if b.family != "contain_roof":
            if _role_and_standin_parts(man):      # (the parts as they were before the roles and stand-ins)
                bmd = SV.installed_bmd(b.name)
                st = C.generate_stages(_without_roles_and_standins(man), bmd["Model"], bmd["FractureModel"],
                                       seed=f"datacenter/{b.name}", damaged_hide=scaf)
            rest = _without_parts(st, scaf)
            if b.name in INT_ZERO:
                rest = _int_zero(rest, f"datacenter/{b.name}")
            assert SV.stages_sha1(rest) == golden[b.name]["stages_sha1"], b.name
        last = st[-1]["Value"]
        assert last["BuildRatioLowerBound"] == golden[b.name]["last_stage"]["BuildRatioLowerBound"], b.name
        assert last["Model"] == golden[b.name]["last_stage"]["Model"], b.name
        assert [c["MeshPart"] for c in SV.last_stage_changes(st)] == scaf, b.name
        assert all(c["ApplyOnlyWhenDamaged"] and c["ShowPart"] is False for c in SV.last_stage_changes(st)), b.name


# Broken interiors, Keen's way (2026-10-20, NOTES.md): the CRAC's coil face (dc/crac.py _inside: the perforated fin
# faces in the core zone) is a material that zone had none of: a new mesh part whose stage changes are new; taken
# out like the roles. (Its solid cores' faces join the zones' existing break-face parts.)
INTERIOR_PARTS = {"DC_CRAC": ("Fracture_01-MetalPerforationSteel",)}


def _role_and_standin_parts(man):
    """The mesh parts the role tables and stand-ins add, whose changes are new too: every role group's parts
    (`Fracture_NN_Support` / `_Frame`: Task 8's server ears, slides and thumbscrews first; a `Fracture_NN_Hide` part of a
    material that is not a HIDE_PREFIXES one: Task 9's tray cables, Task 10's PDU breakers / cords) and every baked
    stand-in (`_Subpart`: the KVM's drawer and lid first, Task 11's CRAC fans). The standing mechanism the later role / stand-in tasks (PDUs, CRAC,
    racks) rely on to keep the baseline hash check: with _without_roles_and_standins it covers every family."""
    return [p for p in man["fractured"]["parts"]
            if p.split("-", 1)[0].endswith(("_Support", "_Frame")) or p.endswith("_Subpart")
            or (p.split("-", 1)[0].endswith("_Hide") and not FR.is_hide(p.split("-", 1)[1]))]


def _without_roles_and_standins(man):
    """The FR LOD0 parts as they were before the roles and stand-ins: without their parts, and with each role part's faces back in
    the zone's skin part of that material (where the ears / slides were a zone's only faces of a material, e.g. the
    Timer's Fracture_01-BrushedMetal, that skin part vanished when they moved to Fracture_01_Support).
    test_installed_stages_regenerate holds the installed stages to generate_stages(parts), so regenerating from these
    parts is the pre-Task-8 stage list."""
    parts = {k: tuple(v) for k, v in man["fractured"]["parts"].items()}
    new = set(_role_and_standin_parts(man))
    out = {k: v for k, v in parts.items() if k not in new}
    cut = tuple(FR.CUT_PROPS.values())
    for k in new:
        g, mat = k.split("-", 1)
        if not k.endswith("_Subpart"):     # (Task 13 fix round 1: a hidden part's caps were the zone's break faces)
            out.setdefault(f"{g.rsplit('_', 1)[0]}-{mat}",
                           cut if mat == FR.CUT_MATERIAL else tuple(FR.ROLE_PROPS["skin"]))
    return out


# the blocks whose baseline stage 0 came from an int 0 (their first part by name started hidden; the roofs too, but
# their hash is exempt): Task 6 made the generator's times floats
INT_ZERO = ("DC_CRAC", "DC_Sign_Aisle", "DC_Sign_AisleHang", "DC_Sign_Rack")


def _without_parts(stages, parts):
    """The stage list with every change of `parts` removed (no stage is left empty: the scaffold changes at 0 and
    0.3, where every block's skin changes too)."""
    s = json.loads(json.dumps(stages))
    for st in s:
        d = st["Value"]["PartChanges"]["_data"]
        d[:] = [c for c in d if c["Value"]["MeshPart"] not in parts]
    return s


def _int_zero(stages, seed):
    """Stage 0 in the old int-0 form: ratio 0, Key and change Keys derived from "0" (construction.generate_stages)."""
    import uuid
    rng = uuid.uuid5(uuid.NAMESPACE_URL, seed)
    s = json.loads(json.dumps(stages))
    s0 = s[0]
    s0["Key"] = str(uuid.uuid5(rng, "stage/0"))
    s0["Value"]["BuildRatioLowerBound"] = 0
    for c in s0["Value"]["PartChanges"]["_data"]:
        c["Key"] = str(uuid.uuid5(rng, f"chg/0/{c['Value']['MeshPart']}"))
    return s
