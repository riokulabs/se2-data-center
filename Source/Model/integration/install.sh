#!/usr/bin/env bash
# Install the staged Data Center package into the mod.
#
#   integration/install.sh            dry run (default): checks everything, prints what would change, writes nothing
#   integration/install.sh --apply    copy the staged files into mods/DataCenter/Assets/DataCenter/
#                                     (overwritten files are backed up to integration/backup/<timestamp>/)
#
# The staged files (integration/Assets/DataCenter/) are produced by build_integration.py and already contain every
# GUID edit: the patched definitions point at the new .model assets, and every new asset has a .meta whose AssetID
# matches what references it. This script copies them, after checks. Adapted from an earlier prototype's install.sh.
# Close the game, the Mod HUB and the Editor first, and don't run se2mod.py build at the same time.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOD="$(cd "$HERE/../../.." && pwd)"
# DC_STAGE_SRC: another staged package to check (the test suite stages into a per-run temp dir; Tests/conftest.py)
SRC="${DC_STAGE_SRC:-$HERE/Assets/DataCenter}"
DST="$MOD/Assets/DataCenter"
APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

die() { echo "ERROR: $*" >&2; exit 1; }
[[ -d "$SRC" ]] || die "nothing staged at $SRC (run build_integration.py first)"
[[ -d "$DST" ]] || die "mod assets not found at $DST (run dc/clone.py first)"

if (( APPLY )); then
  # match process names, not full command lines (other tools' args can mention the game folder)
  if ps -eo comm= | grep -qiE '^(Modern\.bin|SpaceEngineers2|VRage\.Editor|VRage\.ContentPip|VRAGE3)'; then
    die "the game, Editor, HUB or builder seems to be running; close it first"
  fi
fi

echo "== Data Center install ($( ((APPLY)) && echo APPLY || echo 'DRY RUN' ))"
echo "   from: $SRC"
echo "   to:   $DST"

# ---- consistency checks (read-only) -------------------------------------------------------------
python3 - "$SRC" "$DST" <<'PY'
import json, os, re, sys
src, dst = sys.argv[1:]
G = re.compile(r"\{G\}([0-9a-f-]{36})")
def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)
def own(v):
    if v.get("PartialDefinitionKind") == "Copy":
        return (v.get("Manipulator") or {}).get("Guid")
    if "PartialDefinitionKind" in v:
        return None
    return v.get("Guid")
problems = 0
def bad(msg):
    global problems
    print("  PROBLEM:", msg); problems += 1
ids = {}            # AssetID -> staged rel path
for dp, dirs, files in os.walk(src):
    for d in dirs:
        rel = os.path.relpath(os.path.join(dp, d), src)
        if not os.path.exists(os.path.join(dp, d) + ".meta") and not os.path.exists(os.path.join(dst, rel) + ".meta"):
            bad(f"missing folder meta: {rel}")
    for f in files:
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, src)
        if f.endswith(".meta"):
            continue
        dmeta = os.path.join(dst, rel + ".meta")
        if os.path.exists(p + ".meta"):
            aid = load(p + ".meta")["$Value"]["AssetID"]
            if os.path.exists(dmeta) and load(dmeta)["$Value"]["AssetID"] != aid:
                bad(f"AssetID differs from the installed .meta: {rel}")
        elif os.path.exists(dmeta):
            aid = load(dmeta)["$Value"]["AssetID"]   # already installed: the mod keeps its own (built) .meta
        else:
            bad(f"missing meta: {rel}"); continue
        if aid in ids:
            bad(f"duplicate AssetID {aid}: {rel} and {ids[aid]}")
        ids[aid] = rel
# every asset already in the mod (the clones) also resolves
mod_ids = {}
for dp, _, files in os.walk(dst):
    for f in files:
        if f.endswith(".meta"):
            mod_ids[load(os.path.join(dp, f))["$Value"]["AssetID"]] = os.path.relpath(os.path.join(dp, f[:-5]), dst)
# definition GUID == AssetID
n_defs = 0
for aid, rel in ids.items():
    if rel.endswith((".partialdef", ".def")):
        n_defs += 1
        g = own(load(os.path.join(src, rel))["$Value"])
        if g and g != aid:
            bad(f"GUID mismatch: {rel} defines {g}, .meta AssetID {aid}")
# .model references resolve into the package
n_models = 0
for aid, rel in ids.items():
    if rel.endswith(".model"):
        n_models += 1
        with open(os.path.join(src, rel), encoding="utf-8-sig") as f:
            for g in G.findall(f.read()):
                if g not in ids:
                    bad(f"{rel}: {{G}}{g} is not a staged asset")
        mats = load(os.path.join(src, rel))["$Value"]
        names = {m["MaterialName"] for m in mats["MaterialAssignments"]}
        used = {m for ga in mats["GeometryAssets"] for m in ga["UsedMaterials"]}
        if used - names:
            bad(f"{rel}: used materials without an assignment: {sorted(used - names)}")
# BlockModelDefinitions point at staged .model files; build stages and dummies are present
n_bmd = 0
for aid, rel in sorted(ids.items(), key=lambda kv: kv[1]):
    if rel.endswith("_BlockModelDefinition.partialdef"):
        n_bmd += 1
        m = load(os.path.join(src, rel))["$Value"]["Manipulator"]
        for k in ("Model", "FractureModel", "DamagedModel"):
            g = (m.get(k) or "")[3:]
            tgt = ids.get(g)
            if not tgt or not tgt.endswith(".model"):
                bad(f"{rel}: {k} {m.get(k)} is not a staged .model")
        print(f"  {os.path.dirname(rel)}: Model -> {ids.get(m['Model'][3:])}; "
              f"{len(m.get('BuildProgressModels') or [])} build stages; "
              f"{len((m.get('Dummies') or {}).get('Changed', []))} dummies")
# every {G} reference in staged definitions: ours (package or mod) or external (vanilla/library)
refs = set()
for aid, rel in ids.items():
    if rel.endswith((".partialdef", ".def", ".model")):
        with open(os.path.join(src, rel), encoding="utf-8-sig") as f:
            refs |= set(G.findall(f.read()))
ours = {g for g in refs if g in ids or g in mod_ids}
print(f"  staged assets: {len(ids)} ({n_defs} definitions, {n_models} .model, {n_bmd} block models); "
      f"{{G}} references: {len(refs)} ({len(ours)} into this mod, {len(refs) - len(ours)} to vanilla/library)")
print(f"  {problems} problems")
sys.exit(1 if problems else 0)
PY

# ---- plan ------------------------------------------------------------------------------------------
new=0; over=0; same=0
while IFS= read -r -d '' f; do
  rel="${f#$SRC/}"
  if [[ -e "$DST/$rel" ]]; then
    if cmp -s "$f" "$DST/$rel"; then same=$((same+1)); continue; fi
    over=$((over+1)); echo "   overwrite  $rel"
  else
    new=$((new+1)); echo "   new        $rel"
  fi
done < <(find "$SRC" -type f -print0 | sort -z)
# generated model files installed earlier that the package no longer has (e.g. a dropped LOD): moved to the backup
stale=()
while IFS= read -r -d '' f; do
  rel="${f#$DST/}"
  asset="${rel%.meta}"   # an installed .meta stays when its asset is still in the package (it isn't re-staged)
  [[ -e "$SRC/$rel" || -e "$SRC/$asset" ]] || { stale+=("$rel"); echo "   stale      $rel"; }
done < <(find "$DST" -path '*/Models/*' -type f -print0 | sort -z)
echo "== $new new, $over overwritten, $same unchanged, ${#stale[@]} stale"

if (( ! APPLY )); then
  echo "Dry run only. Re-run with --apply to install."
  exit 0
fi

# ---- apply -------------------------------------------------------------------------------------------
BK="$HERE/backup/$(date +%Y%m%d-%H%M%S)"
while IFS= read -r -d '' f; do
  rel="${f#$SRC/}"
  if [[ -e "$DST/$rel" ]] && ! cmp -s "$f" "$DST/$rel"; then
    mkdir -p "$BK/$(dirname "$rel")"
    cp -a "$DST/$rel" "$BK/$rel"
  fi
  mkdir -p "$DST/$(dirname "$rel")"
  cp -a "$f" "$DST/$rel"
done < <(find "$SRC" -type f -print0)
for rel in "${stale[@]}"; do
  mkdir -p "$BK/$(dirname "$rel")"
  mv "$DST/$rel" "$BK/$rel"
done
echo "== installed. Backups of overwritten and stale files: $BK"
echo "Next: tools/scripts/se2mod.py build DataCenter (SE2 closed), then check the .meta Problems lists (INTEGRATION.md)."
echo "Rollback: copy $BK back over Assets/DataCenter (or git checkout -- Assets/) and delete the new files listed above."
