"""Final review I1: staging must not depend on what an earlier install left in Assets/.

The KVM's client composition and client prefab are patched twice in one write_all run: stage_kvm_subparts adds the
ConditionalSubParts + Working animation controller, then patch_kvm_onoff swaps FunctionalBlockComponent for the
vanilla PowerableBlockComponent. If the second patch re-reads the installed copy, the first patch is lost, and that
only shows on a fresh clone (the installed copy of a long-lived checkout already carries the subpart inserts).

So: a scratch copy of Assets/ whose KVM is put back to its fresh-clone state (every cloned ControlPanel25 definition
re-derived from the vanilla file with the KVM's GUID map, as `se2mod.py copy` writes it, and no Subparts/ folder),
staged into a scratch dir with a scratch asset_guids.json. The staged KVM must carry both patches.

The same scratch copy puts a built cable tray (Plan 2 Task 5) back to its fresh-clone state too: its staged block
definition must carry PCU 5 and its staged placement definition AutoRotateFace null, equal to the tracked staging.

And the Programmable (Plan 4 Task 3): back to the structural WallInsertPanel clone (CubeBlockComponent, no terminal
dummy, none of the files write_all adds), it must stage as the functional blade: the Powerable swap, the scripting
component (server side) and the swapper (client side) on top of it in the same run, equal to the tracked staging."""
import json
import os
import re
import shutil

import pytest

from dc import catalog, clone, config, guids, integration, scripting
from dc.assetio import read_json

KVM = "DC_Srv_KVM"
PROG = "DC_Srv_Programmable"   # Plan 4 Task 3: structural clone -> functional blade, three patches in one run
TRAY = "DC_Tray_StraightS_Full"   # Plan 2 Task 5: a built tray block (PCU, placer, models) from a fresh clone
OPEN = "DC_Rack42_Open"   # Plan 5 Task 12: structural clone -> Ruling 15 chain + client-only ConditionalSubParts
GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _body(d):
    v = d["$Value"]
    return v["Manipulator"] if "PartialDefinitionKind" in v else v


def _fresh_clone_kvm(mod_assets):
    """Rewrite the KVM's cloned definitions in mod_assets as the clone step produced them; returns the files."""
    written = _fresh_clone(KVM, mod_assets)
    sub = os.path.join(mod_assets, config.NAME, KVM, "Subparts")
    shutil.rmtree(sub)
    os.remove(sub + ".meta")
    return written


def _fresh_clone(name, mod_assets):
    """Rewrite a block's cloned definitions in mod_assets as the clone step produced them (the vanilla file with the
    block's GUID map and the copy's renames, se2mod.py copy's rule); returns the files."""
    e = clone.entry(catalog.BY_NAME[name])
    gmap = e["guids"]
    cp = [c for c in e["copies"] if c["recursive"]][0]
    src = os.path.join(config.VANILLA_REF, cp["src"])   # vanilla-ref mirrors the SDK Assets/ layout
    if not os.path.isdir(src):
        pytest.skip(f"vanilla reference missing: {src}")
    written = []
    for dp, _, fs in os.walk(src):
        for f in fs:
            if not f.endswith((".def", ".partialdef")):
                continue
            rel = os.path.relpath(os.path.join(dp, f), src)
            head, base = os.path.split(rel)
            for a, b in [(cp["from"], cp["to"])] + [tuple(x.split("=", 1)) for x in cp.get("also") or []]:
                base = base.replace(a, b)
            rel = os.path.join(head, base)
            dst = os.path.join(mod_assets, cp["dest"], rel)
            assert os.path.exists(dst), f"clone target missing: {dst}"
            with open(os.path.join(dp, f)) as fh:
                text = GUID_RE.sub(lambda m: gmap.get(m.group(0), m.group(0)), fh.read())
            with open(dst, "w") as fh:
                fh.write(text)
            written.append(rel)
    return written


@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    integration.write_all()   # the long-lived checkout's staging, this run's (Tests/conftest.py), to compare with
    tmp = tmp_path_factory.mktemp("fresh_clone")
    mod_assets, stage_assets = str(tmp / "Assets"), str(tmp / "staged")
    shutil.copytree(config.MOD_ASSETS, mod_assets)
    gpath = str(tmp / "asset_guids.json")
    shutil.copy2(guids.GUIDS_PATH, gpath)
    written = _fresh_clone_kvm(mod_assets)
    written_tray = _fresh_clone(TRAY, mod_assets)
    written_prog = _fresh_clone(PROG, mod_assets)
    written_open = _fresh_clone(OPEN, mod_assets)       # (its Subparts/ are all write_all's: none on a fresh clone)
    osub = os.path.join(mod_assets, config.NAME, OPEN, "Subparts")
    shutil.rmtree(osub)
    os.remove(osub + ".meta")
    for rel in integration.PROG_STAGED_ONLY:      # what write_all adds: a fresh clone has none of it
        for f in (rel, rel + ".meta"):
            p = os.path.join(mod_assets, f)
            if os.path.exists(p):
                os.remove(p)
    pspec = catalog.BY_NAME[PROG]
    psc = _body(read_json(os.path.join(mod_assets, integration._block_files(pspec, "_ServerComposition")[0])))
    assert integration.STRUCTURAL_KEY in psc["Components"]["Keys"], "the scratch Programmable is not a fresh clone"
    assert integration.POWERABLE_KEY not in psc["Components"]["Keys"]
    tray_bd = _body(read_json(os.path.join(mod_assets, clone.entry(catalog.BY_NAME[TRAY])["info"]["block_def_file"])))
    assert "PCU" not in tray_bd, "the scratch tray is not a fresh clone"
    spec = catalog.BY_NAME[KVM]
    cc = _body(read_json(os.path.join(mod_assets, integration._block_files(spec, "_ClientComposition")[0])))
    assert integration.FUNCTIONAL_KEY in cc["Components"]["Keys"], "the scratch KVM is not a fresh clone"
    assert integration.POWERABLE_KEY not in cc["Components"]["Keys"]
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "MOD_ASSETS", mod_assets)
    mp.setattr(config, "STAGE_ASSETS", stage_assets)
    mp.setattr(integration, "Guids", lambda: guids.Guids(gpath))
    try:
        summary = integration.write_all()
    finally:
        mp.undo()
    with open(gpath) as a, open(guids.GUIDS_PATH) as b:
        same_guids = json.load(a) == json.load(b)
    return {"stage": stage_assets, "summary": summary, "written": written, "written_tray": written_tray,
            "written_prog": written_prog, "written_open": written_open, "same_guids": same_guids}


def _staged(fresh, pat):
    rel = integration._block_files(catalog.BY_NAME[KVM], pat)[0]
    return _body(read_json(os.path.join(fresh["stage"], rel)))


def test_fresh_clone_restored_every_cloned_definition(fresh):
    assert len(fresh["written"]) == clone.entry(catalog.BY_NAME[KVM])["copies"][1]["definitions"] == 10


def test_fresh_clone_kvm_client_composition_has_subparts_and_onoff(fresh):
    cond = guids.Guids(guids.GUIDS_PATH)
    keys = _staged(fresh, "_ClientComposition")["Components"]["Keys"]
    assert cond[f"key/{KVM}/condsub"] in keys and cond[f"key/{KVM}/animctl"] in keys
    assert integration.POWERABLE_KEY in keys and integration.FUNCTIONAL_KEY not in keys
    types = {c["Value"]["Type"] for c in _staged(fresh, "_ClientComposition")["Components"]["Changed"]
             if c["Kind"] == "Insert"}
    assert {integration.T_CONDSUB, integration.T_ANIMCTL, integration.T_POWERABLE} <= types


def test_fresh_clone_kvm_client_prefab_has_subparts_and_onoff(fresh):
    cond = guids.Guids(guids.GUIDS_PATH)
    keys = _staged(fresh, "_Client.partialdef")["_entity"]["ObjectBuilders"]["Keys"]
    assert cond[f"key/{KVM}/condsub"] in keys and cond[f"key/{KVM}/animctl"] in keys
    assert integration.POWERABLE_KEY in keys and integration.FUNCTIONAL_KEY not in keys


def test_fresh_clone_kvm_server_side_has_onoff(fresh):
    for pat, path in (("_ServerComposition", ("Components",)), ("_Server.partialdef", ("_entity", "ObjectBuilders"))):
        d = _staged(fresh, pat)
        for k in path:
            d = d[k]
        assert integration.POWERABLE_KEY in d["Keys"] and integration.FUNCTIONAL_KEY not in d["Keys"]


def test_fresh_clone_kvm_matches_installed(fresh):
    """The fresh-clone staging of the KVM's patched chain equals the tracked staging (the long-lived checkout)."""
    spec = catalog.BY_NAME[KVM]
    for pat in ("_ClientComposition", "_ServerComposition", "_Client.partialdef", "_Server.partialdef"):
        rel = integration._block_files(spec, pat)[0]
        assert read_json(os.path.join(fresh["stage"], rel)) == read_json(os.path.join(config.STAGE_ASSETS, rel)), rel
    assert fresh["same_guids"], "the fresh-clone run minted new asset GUIDs"


# ---------------------------------------------------------------------------------------------- Plan 2: a tray block
def test_fresh_clone_restored_the_tray(fresh):
    assert len(fresh["written_tray"]) == clone.entry(catalog.BY_NAME[TRAY])["copies"][1]["definitions"] == 12
    assert f"{TRAY}_PlacementDefinition.def" in fresh["written_tray"]


def test_fresh_clone_tray_patched(fresh):
    spec = catalog.BY_NAME[TRAY]
    info = clone.entry(spec)["info"]
    bd = _body(read_json(os.path.join(fresh["stage"], info["block_def_file"])))
    assert bd["PCU"] == 5 and "MountPointGeneratorSettings" not in bd
    pl_rel = integration._block_files(spec, "_PlacementDefinition")[0]
    pl = _body(read_json(os.path.join(fresh["stage"], pl_rel)))
    assert pl["AutoRotateFace"] is None and bd["PlacerDefinition"] == pl["Guid"]
    bmd = _body(read_json(os.path.join(fresh["stage"], info["model_def_file"])))
    assert bmd["Model"].startswith("{G}") and bmd["FractureModel"] != bmd["DamagedModel"]   # Task 9b: dented
    assert fresh["summary"]["blocks"][TRAY]["built"]


def test_fresh_clone_tray_matches_installed(fresh):
    spec = catalog.BY_NAME[TRAY]
    info = clone.entry(spec)["info"]
    for rel in (info["block_def_file"], info["model_def_file"], info["kind_file"],
                integration._block_files(spec, "_PlacementDefinition")[0]):
        assert read_json(os.path.join(fresh["stage"], rel)) == read_json(os.path.join(config.STAGE_ASSETS, rel)), rel


# ---------------------------------------------------------------------------------------------- Plan 4: the Programmable
def _staged_prog(fresh, pat):
    rel = integration._block_files(catalog.BY_NAME[PROG], pat)[0]
    return _body(read_json(os.path.join(fresh["stage"], rel)))


def _inserted_types(delta):
    return {c["Value"].get("Type") for c in delta["Changed"] if c["Kind"] == "Insert" and c["Value"]}


def test_fresh_clone_restored_the_programmable(fresh):
    assert len(fresh["written_prog"]) == clone.entry(catalog.BY_NAME[PROG])["copies"][1]["definitions"] == 12


def test_fresh_clone_programmable_is_a_functional_blade(fresh):
    """All three patches of one run on a structural clone: Powerable on both sides, the scripting component on the
    server only, the swapper on the client only; prefabs to match; the Terminal dummy; the block GUID kept."""
    cond = guids.Guids(guids.GUIDS_PATH)
    sc, cc = _staged_prog(fresh, "_ServerComposition"), _staged_prog(fresh, "_ClientComposition")
    assert _inserted_types(sc["Components"]) == {integration.T_POWERABLE, scripting.COMPONENT_TYPE}
    assert _inserted_types(cc["Components"]) == {integration.T_POWERABLE, integration.T_SWAPPER}
    for c in (sc, cc):
        assert integration.STRUCTURAL_KEY not in c["Components"]["Keys"]
    sp = _staged_prog(fresh, "_Server.partialdef")["_entity"]["ObjectBuilders"]
    cp = _staged_prog(fresh, "_Client.partialdef")["_entity"]["ObjectBuilders"]
    assert cond[scripting.COMPONENT_KEY] in sp["Keys"] and integration.POWERABLE_KEY in sp["Keys"]
    assert cond[f"key/{PROG}/swapper"] in cp["Keys"] and integration.POWERABLE_KEY in cp["Keys"]
    info = clone.entry(catalog.BY_NAME[PROG])["info"]
    bd = read_json(os.path.join(fresh["stage"], info["block_def_file"]))["$Value"]
    assert bd["DefinitionType"] == integration.T_POWERABLE_DEF and bd["Manipulator"]["Guid"] == info["block_def"]
    bmd = _body(read_json(os.path.join(fresh["stage"], info["model_def_file"])))
    assert "Terminal" in {c["Value"]["Name"] for c in bmd["Dummies"]["Changed"]}
    for rel in integration.PROG_STAGED_ONLY:
        assert os.path.exists(os.path.join(fresh["stage"], rel)), rel


def test_fresh_clone_programmable_matches_installed(fresh):
    spec = catalog.BY_NAME[PROG]
    info = clone.entry(spec)["info"]
    rels = [integration._block_files(spec, pat)[0] for pat in ("_ClientComposition", "_ServerComposition",
                                                               "_Client.partialdef", "_Server.partialdef")]
    for rel in rels + [info["block_def_file"], info["model_def_file"], *integration.PROG_STAGED_ONLY]:
        assert read_json(os.path.join(fresh["stage"], rel)) == read_json(os.path.join(config.STAGE_ASSETS, rel)), rel


# ---------------------------------------------------------------------------------------------- Plan 5 Task 12: open rack
def test_fresh_clone_open_rack_matches_installed(fresh):
    """The open rack from its fresh WallInsertPanel clone (CubeBlockComponent, no Subparts/) stages, in one run, with
    the static children cleared, the Ruling 15 swap and the client-only ConditionalSubParts + animation controller on
    top of it, equal to the tracked staging."""
    spec = catalog.BY_NAME[OPEN]
    assert len(fresh["written_open"]) == 12
    cc = _body(read_json(os.path.join(fresh["stage"], integration._block_files(spec, "_ClientComposition")[0])))
    assert integration.POWERABLE_KEY in cc["Components"]["Keys"]
    assert integration.STRUCTURAL_KEY not in cc["Components"]["Keys"]
    assert {integration.T_CONDSUB, integration.T_ANIMCTL, integration.T_POWERABLE} <= _inserted_types(cc["Components"])
    info = clone.entry(spec)["info"]
    for rel in [info["block_def_file"], info["model_def_file"]] + [
            integration._block_files(spec, p)[0] for p in ("_ClientComposition", "_ServerComposition",
                                                           "_Client.partialdef", "_Server.partialdef")]:
        assert read_json(os.path.join(fresh["stage"], rel)) == read_json(os.path.join(config.STAGE_ASSETS, rel)), rel
    sub = os.path.join(config.NAME, OPEN, "Subparts")
    mine = sorted(f for f in os.listdir(os.path.join(config.STAGE_ASSETS, sub)) if f.endswith((".def", ".partialdef")))
    assert mine == sorted(f for f in os.listdir(os.path.join(fresh["stage"], sub)) if f.endswith((".def", ".partialdef")))
    for f in mine:
        assert read_json(os.path.join(fresh["stage"], sub, f)) == read_json(os.path.join(config.STAGE_ASSETS, sub, f)), f
