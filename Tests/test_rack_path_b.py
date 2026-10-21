"""Plan 5 final review I1: Ruling DB-10's Path B fallback is a switch (config.RACK_PATH = "B"), not a revert.

If Path A (the racks' side panels and fan tray as bound ConditionalSubParts, task-12-spike.md) fails the world load in
game, setting config.RACK_PATH = "B" and re-running the rack pipeline must give back the structure the racks shipped
with before Task 12 (commit 10455382's parent): the rotors, the fan tray and both side panels as static children of
the rack's client prefab, with no bindings, no rack ConditionalSubParts entries and no stand-ins, while every rack
keeps On/Off (user 2026-10-20). Here the B package is staged into a temp dir (the committed A package is untouched)
and must:
  (a) stage exactly the pre-Task-12 client-prefab children (compared with the commit's own files),
  (b) stage no Path A definition (bindings, server compositions, the open racks' ConditionalSubParts),
  (c) keep On/Off and the rotor controller on every full rack, the door's CSP listing only its leaves,
  (d) pass the client/server walk gate (Tests/clientserver_walk.py) over vanilla + the mod without its Path A files,
  (e) need no new GUID (asset_guids.json unchanged: every child key is the pre-Task-12 one).
"""
import json
import os
import re
import shutil
import subprocess

import pytest

import clientserver_walk as csw
from dc import config, fracture, integration
from dc.guids import GUIDS_PATH

RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear",
         "DC_Rack24_Open", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
PRE_TASK12 = "10455382^"
C_CSP = "Game2:Keen.Game2.Client.WorldObjects.CubeBlocks.Effects.ConditionalSubPartsComponent"
OB_HIERARCHY = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder"
# the Path A-only rack definitions (the B recipe removes them from Assets/: INGAME-CHECKLIST "Next session")
PATH_A_ONLY = re.compile(r"^DC_Rack\w+/Subparts/DC_Rack\w+_(Rack(Side|FanTray)_(Binding|Server|ServerComposition)"
                         r"|Open_ConditionalSubPartsDefinition)\.def$")


def _git(*args):
    return subprocess.run(["git", "-C", config.MOD_DIR, *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True)


def _hierarchy(client_partialdef):
    v = client_partialdef["$Value"]
    ent = v.get("Manipulator", v)["_entity"]
    ups = [c["Value"] for c in ent["ObjectBuilders"]["Changed"]
           if c["Kind"] == "Update" and c["Index"] == 1 and c["Value"].get("$Type") == OB_HIERARCHY]
    assert len(ups) == 1, ups
    return ups[0]["Children"]


@pytest.fixture(scope="module")
def path_b(tmp_path_factory):
    """The whole package staged with RACK_PATH "B" into a temp dir; config restored after, and the GUID registry
    too should B have allocated a key (test_b_needs_no_new_guid then fails)."""
    guids_before = open(GUIDS_PATH, encoding="utf-8").read()
    stage = str(tmp_path_factory.mktemp("rack-path-b") / "Assets")
    saved = config.STAGE_ASSETS, config.RACK_PATH
    config.STAGE_ASSETS, config.RACK_PATH = stage, "B"
    try:
        summary = integration.write_all()
    finally:
        config.STAGE_ASSETS, config.RACK_PATH = saved
    guids_after = open(GUIDS_PATH, encoding="utf-8").read()
    if guids_after != guids_before:
        with open(GUIDS_PATH, "w", encoding="utf-8") as f:
            f.write(guids_before)
    return {"stage": stage, "summary": summary, "guids_changed": guids_before != guids_after}


def test_standins_follow_the_path():
    """Path A bakes the rack stand-ins, Path B none (the real parts are always there); the shipped default is A."""
    racks = set(RACKS)
    assert set(fracture.rack_standins("A")) == racks
    assert fracture.rack_standins("B") == {}
    with pytest.raises(ValueError):
        fracture.rack_standins("C")
    assert config.RACK_PATH == "A"
    assert racks <= set(fracture.STANDINS)


def test_b_needs_no_new_guid(path_b):
    assert not path_b["guids_changed"], "Path B allocated new asset_guids.json keys (it must reuse pre-Task-12 ones)"


@pytest.mark.parametrize("name", RACKS)
def test_b_restores_pre_task12_children(path_b, name):
    """The B client prefab's Hierarchy children equal the ones committed before Task 12 (rotors, tray, both sides:
    same keys, composites, transforms and rotor animation keys)."""
    rel = f"Assets/{config.NAME}/{name}/{name}_Client.partialdef"
    old = _git("show", f"{PRE_TASK12}:{rel}")
    if old.returncode != 0:
        pytest.skip(f"commit {PRE_TASK12} is not in this clone's history")
    with open(os.path.join(path_b["stage"], config.NAME, name, f"{name}_Client.partialdef"), encoding="utf-8-sig") as f:
        new = json.load(f)
    assert _hierarchy(new) == _hierarchy(json.loads(old.stdout)), name


@pytest.mark.parametrize("name", RACKS)
def test_b_stages_no_path_a_definition(path_b, name):
    sub = os.path.join(path_b["stage"], config.NAME, name, "Subparts")
    got = sorted(f for f in os.listdir(sub) if PATH_A_ONLY.match(f"{name}/Subparts/{f}"))
    assert got == [], got
    s = path_b["summary"]["blocks"][name]["rack_subparts"]
    assert s["path"] == "B" and "bound" not in s


@pytest.mark.parametrize("name", RACKS)
def test_b_keeps_on_off_and_the_door(path_b, name):
    s = path_b["summary"]["blocks"][name]["rack_subparts"]
    full = name.startswith("DC_Rack42")
    if name.endswith("_Open"):
        assert s["onoff"], name
        assert "conditional_subparts" not in s
        assert bool(s.get("client_components")) == full     # the rotors' FunctionalBlockAnimationController
        f = os.path.join(path_b["stage"], config.NAME, name, f"{name}_ClientComposition.partialdef")
        if os.path.exists(f):                               # (an installed Path A one loses its CSP component)
            with open(f, encoding="utf-8-sig") as fh:
                assert C_CSP not in fh.read(), name
    else:
        rel = s["conditional_subparts"]
        with open(os.path.join(path_b["stage"], rel), encoding="utf-8-sig") as f:
            v = json.load(f)["$Value"]
        v = v.get("Manipulator", v)
        assert set(v["SubParts"]) == {x["types"][0] for x in s["leaves"].values()}   # the leaves only
        assert v["MeshPartsToHideWhenActive"] == []
        assert bool(s.get("fan_controller")) == full


def test_b_passes_the_walk_gate(path_b, tmp_path):
    """The client/server walk (the 2026-10-18 world-load failure's offline gate) passes the B package: vanilla, then
    the mod's Assets without its Path A rack files (as the B recipe leaves them), then the B staging."""
    if not os.path.isdir(csw.SDK_ASSETS):
        pytest.fail(f"walk gate input missing: {csw.SDK_ASSETS}", pytrace=False)
    mod = tmp_path / "mod"
    base = os.path.join(config.MOD_ASSETS, config.NAME)
    for dp, _, fs in os.walk(base):
        for f in fs:
            if f.endswith((".def", ".partialdef")):
                rel = os.path.relpath(os.path.join(dp, f), base)
                if PATH_A_ONLY.match(rel.replace(os.sep, "/")):
                    continue
                dst = mod / config.NAME / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(os.path.join(dp, f), dst)
    u = csw.Universe([csw.SDK_ASSETS, str(mod), path_b["stage"]])
    errs = csw.validate(csw.walk(u), csw.TypeIndex())
    assert errs == [], errs[:20]


def test_path_b_passes_the_schema_gate(path_b):
    """The 4.0 schema gate (non-null members, component definition types: Tests/definition_schema.py) holds under Path B
    too: the 2026-10-20 open-rack load failure was a stale build, not a Path A structure."""
    import clientserver_walk as csw
    import definition_schema as ds
    if not os.path.isdir(csw.SDK_ASSETS):
        pytest.skip("no Mod SDK vanilla Assets")
    u = csw.Universe([csw.SDK_ASSETS, config.MOD_ASSETS, path_b["stage"]])
    s = ds.Schema(csw.TypeIndex())
    roots = tuple(os.path.abspath(r) + os.sep for r in (config.MOD_ASSETS, path_b["stage"]))
    mine = [g for g in u.entries if os.path.abspath(str(u.origin(g))).startswith(roots)]
    errs = ds.nonnull_errors(u, s, mine) + ds.composition_type_errors(u, s, mine)
    assert not errs, "\n" + ds.format_errors(errs)
