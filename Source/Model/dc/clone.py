"""Clone the vanilla definition chains of every catalogue block into mods/DataCenter/Assets/DataCenter/<name>/.

    python3 Source/Model/dc/clone.py [BLOCK ...]      (default: the whole catalogue; already cloned blocks are skipped)

Per block, two `se2mod.py copy` runs share one GUID map, kept under the block's name in the mod's keyed
`.clonemap.json` (`--map-key`), so the same vanilla folder (the wall panel, the sliding door) can be cloned once per
block with its own GUIDs:
  1. the vanilla BlockKind (the build-menu tile) -> <name>/UI/<name>_BlockKindDefinition.def, so the clone gets its
     own tile instead of becoming an extra size of the vanilla one;
  2. the block's SDK folder, recursively (-r), into <name>/. The kind was mapped first, so the block definition's
     BlockKind reference is rewired by the copy itself. Files with a second prefix in the same folder (the door's
     `SlideDoorNarrow_250_` subparts and `NarrowSlidingDoor` LOD materials, the LCD's `LCD50` LOD material) are
     renamed with `--also` in the SAME copy: the door's main definitions and its subparts reference each other
     (ConditionalSubParts -> subpart prefabs, subpart SLERP -> door dummies), so a separate copy could not rewire both.
Every cloned file gets a .meta whose AssetID is its own definition GUID; every folder gets a .meta with a stable
AssetID from asset_guids.json. The server and client compositions are cloned untouched, so functional behaviour is
vanilla. The block's key GUIDs and files are recorded in .clonemap.json as maps[<name>].info for the integration step.

The wall-panel shells (open racks, deco servers, programmable shell) are already a non-functional decorative
breakable block (Breakable/Structural template: model, breakable, effects; no power, terminal or inventory), so
"stripping" them is renaming only.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from dc import catalog, config  # noqa: E402
from dc.assetio import own_guid, read_json, write_meta  # noqa: E402
from dc.guids import Guids  # noqa: E402

# extra file-name prefixes inside a vanilla folder, per copy_from (see the module docstring)
ALSO = {
    "SlidingDoorNarrow250": lambda n: [f"SlideDoorNarrow_250_={n}_", f"NarrowSlidingDoor={n}"],
    "LCDFlat50": lambda n: [f"LCD50={n}"],
    "EventController": lambda n: [f"{n}100={n}"],   # LODMaterial/EventController100_LastLOD
    "StructuralSupportStraight": lambda n: [f"TrussFrame_Long={n}"],   # LODMaterials/TrussFrame_Long_LastLod (rods)
    # Plan 3 room pieces (risk spike, docs/research/dc-room-risk-spike.md section 3)
    "CatwalkSquareBase250": lambda n: [f"CatwalkSquareBase_250={n}"],   # its LODMaterial (P3-17)
    "LCDNarrow50": lambda n: [f"NarrowLCD50={n}"],                       # its LODMaterial (P3-18)
    # Gyroscope250's prefixed files (Subparts/Gyroscope250_S2/S3/Subparts*, the Gyroscope250_Base LOD materials, the
    # Gyroscope250Particles dummy type) take the main rename; its other files (S1..S3 model components and rotation
    # animations, SubParts.def, SubpartMarker.def) have generic names and keep them. This only drops the space in
    # "Gyroscope250_GyroscopePowerableBlockDefinition .partialdef" (P3-15 hygiene: <name>_PowerableBlockDefinition).
    # DeckPanel250 has no second prefix.
    "Gyroscope250": lambda n: ["GyroscopePowerableBlockDefinition =PowerableBlockDefinition"],
}
# cloned files a block must not keep, per copy_from (file-name suffixes; their .meta goes too). Gyroscope250's
# GyroscopeDefinition (44 MN m of torque): the CRAC strips the GyroscopeComponent that is its only reader (P3-15,
# integration.crac_patch), so the definition is dropped with it. Plan 3 T11 (the T6 review's minor 1): the vanilla
# gimbal's subpart chain too, dead since the CRAC's ConditionalSubParts (SubParts.def) maps only its CracFan rotor:
# the S2 / S3 ring composites, the gimbal prefab and its composite, the S1-S3 rotations and model components (they
# reference only each other and vanilla's gimbal models) and the unbound SubpartMarker.
GIMBAL = ("_S2.def", "_S3.def", "_Subparts.def", "_Subparts_Composite.def", "SubpartMarker.def") + tuple(
    f"S{i}{t}.def" for i in (1, 2, 3) for t in ("RotationAnimation", "_ModelComponentDefinition"))
DROP = {"Gyroscope250": ("_GyroscopeDefinition.partialdef",) + GIMBAL}


def drop_files(spec):
    """Delete the block's DROP files (and their .meta) from its clone; returns the mod-relative paths removed."""
    root = os.path.join(config.MOD_ASSETS, dest_rel(spec))
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(DROP.get(spec.copy_from, ())):
                p = os.path.join(dp, f)
                os.remove(p)
                if os.path.exists(p + ".meta"):
                    os.remove(p + ".meta")
                out.append(os.path.relpath(p, config.MOD_ASSETS))
    return out


def dest_rel(spec):
    return f"{config.NAME}/{spec.name}"


def load_map():
    return read_json(config.CLONE_MAP) if os.path.exists(config.CLONE_MAP) else {}


def entry(spec, cmap=None):
    cmap = load_map() if cmap is None else cmap
    return (cmap.get("maps") or {}).get(spec.name)


def is_cloned(spec, cmap=None):
    e = entry(spec, cmap)
    return bool(e and e.get("info"))


def _se2mod():
    sys.path.insert(0, os.path.join(config.TOOLS_DIR, "scripts"))
    import se2mod  # noqa: E402
    return se2mod


def _sdk_assets():
    return _se2mod().SDK_ASSETS


def _block_info(spec):
    """(kind dir rel, kind file stem, server prefab, client prefab, block def, kind guid) from block_chain."""
    sys.path.insert(0, os.path.join(config.TOOLS_DIR, "scripts"))
    import block_chain as bc  # noqa: E402
    idx = bc.Index()
    blocks = bc.Blocks(idx)
    want = f"{spec.vanilla_source}/{spec.copy_from}.partialdef"
    hits = [(g, e) for g, e in blocks.bindings() if idx.rel(e.path) == want]
    if len(hits) != 1:
        raise SystemExit(f"{spec.name}: binding {want} not found in the SDK ({len(hits)} hits)")
    info = blocks.describe(hits[0][0])
    return info


def _copy(src, from_, to, dest, key, recursive, also=()):
    """`se2mod.py copy` into THIS source tree's mod (config.MOD_DIR). The command line resolves the mod by its name
    under the workspace's mods/ (mods/DataCenter), which in a git worktree (mods/DataCenter-<topic>) is the wrong
    checkout; so se2mod's own cmd_copy runs in-process with its mod lookup pinned to config.MOD_DIR. se2mod.py itself
    is unchanged and is the only copy implementation."""
    import argparse
    from pathlib import Path
    se2mod = _se2mod()
    args = argparse.Namespace(mod=config.NAME, src=src, from_=from_, to=to, dest=dest, map_key=key,
                              recursive=recursive, also=list(also) or None, force=False)
    cmd = ["copy", config.NAME, src, "--from", from_, "--to", to, "--dest", dest, "--map-key", key]
    cmd += ["-r"] if recursive else []
    for a in also:
        cmd += ["--also", a]
    print(f"$ se2mod.py {' '.join(cmd)}   (mod: {config.MOD_DIR})", flush=True)
    real = se2mod.mod_dir
    se2mod.mod_dir = lambda name: Path(config.MOD_DIR)
    try:
        se2mod.cmd_copy(args)
    finally:
        se2mod.mod_dir = real


def _find_def(root, guid):
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.endswith((".def", ".partialdef")):
                p = os.path.join(dp, f)
                if own_guid(read_json(p)) == guid:
                    return p
    return None


def write_metas(root, G):
    """.meta for every cloned definition (AssetID = own GUID) and every folder (stable AssetID), never overwriting."""
    n = 0
    folders = [root] + [os.path.join(dp, d) for dp, ds, _ in os.walk(root) for d in ds]
    parent = os.path.dirname(root)          # Assets/DataCenter itself
    if parent != config.MOD_ASSETS:
        folders.append(parent)
    for d in folders:
        rel = os.path.relpath(d, config.MOD_ASSETS)
        if not os.path.exists(d + ".meta"):
            write_meta(d, G["dir/" + rel])
            n += 1
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            if f.endswith((".def", ".partialdef")) and not os.path.exists(p + ".meta"):
                g = own_guid(read_json(p))
                if not g:
                    raise SystemExit(f"{p}: no own GUID (an Override?)")
                write_meta(p, g)
                n += 1
    return n


def clone(spec, G):
    info = _block_info(spec)
    kind_path = info.get("kind_path")
    if not kind_path:
        raise SystemExit(f"{spec.name}: the vanilla block has no BlockKind")
    sdk = _sdk_assets()
    kind_dir = os.path.dirname(kind_path)
    others = [f for f in os.listdir(os.path.join(sdk, kind_dir))
              if f.endswith((".def", ".partialdef")) and f != os.path.basename(kind_path)]
    if others:
        raise SystemExit(f"{kind_dir} holds more than the kind ({others}); copy the kind by hand")
    kind_stem = os.path.splitext(os.path.basename(kind_path))[0]
    dest = dest_rel(spec)
    done = {c["src"] for c in (entry(spec) or {}).get("copies", [])}
    if kind_dir not in done:   # 1. the kind first, so step 2 rewires the block definition's BlockKind reference
        _copy(kind_dir, kind_stem, f"{spec.name}_BlockKindDefinition", f"{dest}/UI", spec.name, False)
    if spec.vanilla_source not in done:
        also = ALSO.get(spec.copy_from, lambda n: [])(spec.name)
        _copy(spec.vanilla_source, spec.copy_from, spec.name, dest, spec.name, True, also)
        for rel in drop_files(spec):
            print(f"dropped {rel}")
    cmap = load_map()
    e = cmap["maps"][spec.name]
    m = e["guids"]
    root = os.path.join(config.MOD_ASSETS, dest)
    rel = lambda p: os.path.relpath(p, config.MOD_ASSETS) if p else None   # noqa: E731
    new = {k: m.get(info.get(k) or "") for k in ("block_def", "server_prefab", "client_prefab", "kind_guid")}
    bmd = [f for f in os.listdir(root) if f.endswith("_BlockModelDefinition.partialdef")]
    if len(bmd) != 1:
        raise SystemExit(f"{spec.name}: expected one *_BlockModelDefinition.partialdef, found {bmd}")
    bmd_path = os.path.join(root, bmd[0])
    e["info"] = {
        "binding": info["binding_path"], "archetype": info.get("archetype"),
        "block_def": new["block_def"], "block_def_file": rel(_find_def(root, new["block_def"])),
        "kind": new["kind_guid"], "kind_file": rel(_find_def(os.path.join(root, "UI"), new["kind_guid"])),
        "server_prefab": new["server_prefab"], "client_prefab": new["client_prefab"],
        "model_def": own_guid(read_json(bmd_path)), "model_def_file": rel(bmd_path),
        "vanilla": {k: info.get(k) for k in ("block_def", "server_prefab", "client_prefab", "kind_guid")},
    }
    missing = [k for k, v in e["info"].items() if v is None]
    if missing:
        raise SystemExit(f"{spec.name}: could not resolve {missing}")
    with open(config.CLONE_MAP, "w") as f:
        json.dump(cmap, f, indent=2)
        f.write("\n")
    n = write_metas(root, G)
    print(f"cloned {spec.name}: {sum(c['definitions'] for c in e['copies'])} definitions, {n} metas")
    return e["info"]


def ensure_kind(info):
    """Point the cloned block definition at the cloned kind. The copy rewires an explicit BlockKind; a definition
    that inherits its kind from its Copy base (doors, timer, event controller, LCD) gets it written here, otherwise
    the clone would show up as an extra size of the vanilla tile (as tools/scripts/clone_block.py does)."""
    p = os.path.join(config.MOD_ASSETS, info["block_def_file"])
    d = read_json(p)
    m = d["$Value"]["Manipulator"]
    if m.get("BlockKind") != info["kind"]:
        m["BlockKind"] = info["kind"]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
            f.write("\n")
        print(f"  {info['block_def_file']}: BlockKind = {info['kind']}")


def clone_all(specs=None):
    G = Guids()
    out = {}
    for spec in specs or catalog.BLOCKS:
        if is_cloned(spec):
            print(f"skip {spec.name}: already cloned (.clonemap.json)")
            out[spec.name] = entry(spec)["info"]
        else:
            out[spec.name] = clone(spec, G)
            G.save()
        ensure_kind(out[spec.name])
    G.save()
    return out


if __name__ == "__main__":
    names = sys.argv[1:]
    clone_all([catalog.BY_NAME[n] for n in names] if names else None)
