"""The mod's own en-US texts (no Blender): every display string the integration stages resolves as a localisation key.

Why. Every Name / Description / Tooltip in SE2 2.4 is a LocKey (one member, TextId), looked up in the culture texts
(decompiled VRage.Library Keen.VRage.Library.Localization). A value that is no key logs, at world load,
"Unrecognized value '<text>'" (the LocalizationSuggester's definition validation, member $Root.Name.TextId /
$Root.Description.TextId / $Root.Tooltip.TextId / $Root.UIData.Name.TextId) and, each time the UI shows it,
"LOCALIZATION WARNING: Could not find key <text> in the culture set en-US. Evaluating to string id."

How vanilla does it (SDK Assets/MainMenuData/Texts/): a CultureInfoAssetDefinition per culture (en-US.def: CultureId
f59b9226 = the en-US CultureIdDefinition, Resources = [{ContentId, Asset}]) points at .loc-texts files, each a flat
JSON object key -> text. CultureInfoDefinitionPostProcessor merges every definition with the same CultureId (content
IDs must be unique per culture), so a mod adds its own: DataCenter/Texts/DataCenter_en-US.def with ContentId
"DataCenterTexts" -> DataCenter/Texts/en-US/DataCenter.loc-texts.

Keys ARE the English texts (key == value). Vanilla uses identifier keys ("ArmorCubeHeavy"), but the base culture's
strings are read once, at game start (TextManager.InitializeBaseCulture -> LocalizationPackage.LoadBaseCultureAssets),
while a mod's World-set definitions arrive with the world (GameDataLoaderComponent pushes the world's projects later),
so the in-game lookup of a mod key can still miss in 2.4; a miss evaluates to the key itself, so the menu shows the
right English text either way. The definition validation, which rebuilds the base texts from the loaded culture
definitions (CultureInfoDefinitionPostProcessor.TryGetBaseCultureTexts, an early post-processor of the World set),
finds them. (A Core-set definition would be read at start-up, but a mod pushed with a world after the Core set is
mounted throws: ProjectBasedDefinitionSetManagerComponent.ProjectsPushed.)

stage(G) runs at the end of integration.write_all: it reads back every staged definition, collects its display strings
(display_strings) and stages the two files. Tests/test_room_menu.py checks that every display string has an entry.
"""
import json
import os

from . import config
from .assetio import B_VRAGE, body, envelope, read_json

EN_US = "f59b9226-51d4-4fe7-9479-dfd24c60a387"   # MainMenuData/Texts/CultureIdentifiers/ID_en-US.def
CONTENT_ID = f"{config.NAME}Texts"
LOC_FILE = f"{config.NAME}/Texts/en-US/{config.NAME}.loc-texts"
DEF_FILE = f"{config.NAME}/Texts/{config.NAME}_en-US.def"
T_CULTURE = "VRage:Keen.VRage.Library.Localization.CultureInfoAssetDefinitionObjectBuilder"
# definition type (last segment of $Type / DefinitionType) -> its LocKey members at the root
ROOT_KEYS = {"BlockKindDefinition": ("Name", "Description"), "BlockGroupDefinition": ("Name",),
             "SubcategoryDefinition": ("Name", "Tooltip")}


def def_type(data):
    """'BlockKindDefinition' for a .def ($Type ...ObjectBuilder) or a partialdef (its DefinitionType)."""
    v = data.get("$Value") or {}
    t = v.get("DefinitionType") if "PartialDefinitionKind" in v else data.get("$Type", "")
    t = (t or "").rsplit(".", 1)[-1]
    return t[:-len("ObjectBuilder")] if t.endswith("ObjectBuilder") else t


def display_strings(data):
    """[(member, text)] of one definition's LocKey members: UIData.Name of a block definition, Name / Description /
    Tooltip of the menu definitions (ROOT_KEYS)."""
    v = data.get("$Value") or {}
    if v.get("PartialDefinitionKind") == "Override":
        return []
    b = body(data)
    out = []
    for k in ROOT_KEYS.get(def_type(data), ()):
        if isinstance(b.get(k), str) and b[k]:
            out.append((k, b[k]))
    ui = b.get("UIData")
    if isinstance(ui, dict) and isinstance(ui.get("Name"), str) and ui["Name"]:
        out.append(("UIData.Name", ui["Name"]))
    return out


def staged_strings(root=None):
    """{text: [rel path, ...]} over every staged definition under root (default: the integration package)."""
    root = root or config.STAGE_ASSETS
    found = {}
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if not f.endswith((".def", ".partialdef")):
                continue
            p = os.path.join(dp, f)
            for _, text in display_strings(read_json(p)):
                found.setdefault(text, []).append(os.path.relpath(p, root))
    return found


def loc_texts(strings):
    """The .loc-texts body: key == the English text, sorted (stable output)."""
    return {k: k for k in sorted(strings)}


def stage(G):
    """Stage the en-US texts of every display string staged so far, and the culture definition that loads them.
    Returns {"file", "definition", "keys"}."""
    from . import integration as I
    strings = staged_strings()
    path = I.stage_path(LOC_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(loc_texts(strings), f, indent=4, ensure_ascii=False)
        f.write("\n")
    I.stage_meta(LOC_FILE, G[LOC_FILE])
    guid = G["def/texts/en-US"]
    I.stage_def(DEF_FILE, envelope(T_CULTURE, {
        "Guid": guid, "CultureId": EN_US,
        "Resources": [{"Key": G["key/texts/en-US/resource"],
                       "Value": {"ContentId": CONTENT_ID, "Asset": "{G}" + G[LOC_FILE]}}]}, B_VRAGE))
    return {"file": LOC_FILE, "definition": DEF_FILE, "guid": guid, "keys": len(strings)}
