"""Small JSON / .meta helpers shared by the clone step and the integration writer (no Blender)."""
import json
import os

B_VRAGE = {"System.Runtime": "1.0.0.0", "VRage": "2.4.0.95"}
B_GAME = {"Game2": "2.4.0.95", "System.Runtime": "1.0.0.0", "VRage": "2.4.0.95"}
META_TYPE = "VRage:Keen.VRage.ContentPipeline.Metafiles.MetaData"
PARTIAL = "VRage:Keen.VRage.ContentPipeline.Definitions.PartialDefinitionDiff"


def envelope(type_, value, bundles=B_VRAGE):
    return {"$Bundles": bundles, "$Type": type_, "$Value": value}


def read_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def write_meta(path, asset_id):
    """<path>.meta with only the AssetID (the builder fills in hashes and processor info)."""
    write_json(path + ".meta", envelope(META_TYPE, {"AssetID": asset_id, "InternalItems": []}))


def meta_id(path):
    m = path + ".meta"
    return read_json(m)["$Value"]["AssetID"] if os.path.exists(m) else None


def own_guid(data):
    """GUID a definition file defines: Manipulator.Guid for a Copy partialdef, $Value.Guid for a .def, None for an
    Override partialdef (same rule as tools/scripts/se2mod.py)."""
    v = data.get("$Value") or {}
    if v.get("PartialDefinitionKind") == "Copy":
        return (v.get("Manipulator") or {}).get("Guid")
    if "PartialDefinitionKind" in v:
        return None
    return v.get("Guid")


def body(data):
    """The editable value of a definition (the Manipulator of a partialdef)."""
    v = data["$Value"]
    return v["Manipulator"] if "PartialDefinitionKind" in v else v
