"""The scripted KVM's runtime held to the data and to the geometry checks (Tests/test_kvm_sequence.py).

The runtime's decisions live in the game-free C# core (Scripts/Client/Core, unit-tested by Tests/CoreTests); the game
glue is Scripts/Client/Kvm. CoreTests dumps two files next to the trajectories, so these tests need no dotnet:
  routing.json        KvmRackSlot's rule per rack kind and slot, against dc/kvm_motion.motion_path_for_slot;
  data_only_open.csv  KvmLinearMotion, against dc/kvm_motion.data_only_trajectory: the very motion the top-slot
                      clearances were measured on (so the runtime's data-only path cannot drift from what was checked).
Regenerate both with: cd Tests/CoreTests && dotnet run -c Release -- --dump ../../Source/Model/preview/scripts/traj
(the conftest `trajectories` fixture does it when the dump's content stamp does not match the core sources).
"""
import glob
import json
import os
import re

import pytest

from dc import catalog, doors, kvm_motion as K, subparts as S

MOD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CLIENT = os.path.join(MOD, "Scripts", "Client")
ROUTING = os.path.join(K.TRAJ_DIR, "routing.json")
DATA_ONLY_CSV = os.path.join(K.TRAJ_DIR, "data_only_open.csv")
RACKS = [b for b in catalog.CORE_BLOCKS if b.family == "rack"]
# The dumps are CoreTests output outside git: the conftest fixture regenerates them when stale or absent.
pytestmark = [pytest.mark.scripts, pytest.mark.usefixtures("trajectories")]


def _need(path):
    """The dumps are CoreTests output under Source/Model/preview/, outside git: skip, never fail, without them (the
    trajectories fixture has already regenerated them when dotnet is there)."""
    if not os.path.exists(path):
        pytest.skip(f"{os.path.relpath(path, MOD)} absent: run cd Tests/CoreTests && dotnet run -c Release -- --dump "
                    "../../Source/Model/preview/scripts/traj")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_routing_matches_python():
    """Runtime vs geometry: the C# rule routes exactly the slots the Python rule routes, for every rack."""
    _need(ROUTING)
    with open(ROUTING, encoding="utf-8") as fh:
        table = json.load(fh)
    assert len(RACKS) == 6
    for spec in RACKS:
        kind = "Full" if K.has_containment_above(spec) else "Half"
        row = table[kind]
        assert row["cells"] == spec.cells[1], (spec.name, "rack height in cells")
        assert len(row["slots"]) == K.nslots(spec), spec.name
        for slot in range(1, K.nslots(spec) + 1):
            assert row["slots"][str(slot)] == K.motion_path_for_slot(spec, slot), (spec.name, slot)
    # the rule is not vacuous: one data-only slot per full rack, none in a half rack
    assert [p for p in table["Full"]["slots"].values()].count(K.DATA_ONLY) == 1
    assert K.DATA_ONLY not in table["Half"]["slots"].values()


def test_rack_kind_guids_cover_every_rack():
    """The runtime tells a full rack from a half one by block definition (DcGuids.Rack*Block, generated from the
    data): every rack variant has its constant, and KvmRackTable maps the 42U ones to Full and the 24U ones to Half."""
    guids = _read(os.path.join(MOD, "Scripts", "Simulation", "Shared", "DcGuids.g.cs"))
    link = _read(os.path.join(CLIENT, "Kvm", "KvmRackTable.cs"))
    full = re.search(r"if \((g == DcGuids\.\w+(?: \|\| g == DcGuids\.\w+)*)\)\s*return KvmRackKind\.Full;", link)
    half = re.search(r"bool half = (g == DcGuids\.\w+(?: \|\| g == DcGuids\.\w+)*);", link)
    assert full and half, "KvmRackTable.KindOf changed shape: update this test"
    names = lambda m: set(re.findall(r"DcGuids\.(\w+)", m.group(1)))
    for spec in RACKS:
        const = spec.name.replace("DC_", "").replace("_", "") + "Block"
        assert f"public static readonly Guid {const} =" in guids, const
        assert const in (names(full) if K.has_containment_above(spec) else names(half)), (spec.name, const)


def test_data_only_path_matches_the_checked_trajectory():
    """KvmLinearMotion (the data-only path) is exactly dc/kvm_motion.data_only_trajectory at 240 Hz: the top-slot
    clearances hold for the motion the game runs. Adding easing breaks this on purpose: re-dump and re-check."""
    _need(DATA_ONLY_CSV)
    runtime = K.load("data_only_open")
    python = K.data_only_trajectory([(0.0, 0.0, 1.0)])
    assert len(runtime) == len(python)
    for (t, s, f), (pt, ps, pf) in zip(runtime, python):
        assert abs(t - pt) < 1e-5 and abs(s - ps) < 1e-5 and abs(f - pf) < 1e-5, (t, s, f, pt, ps, pf)


def test_data_only_stroke_is_the_data():
    """KvmMotionTuning.DataOnlyStroke is the data's POP_TIME: travel / Speed and angle / AngularSpeed."""
    stroke = K.read_tuning()["DataOnlyStroke"]
    assert stroke == S.POP_TIME
    assert abs(S.TRAVEL / S.DRAWER_SPEED - stroke) < 1e-9
    assert abs(S.FOLD_DEG / S.SCREEN_SPEED - stroke) < 1e-9


def test_runtime_dumps_fresh():
    """routing.json and data_only_open.csv come from the core sources on disk: the dump's content stamp (the
    trajectories' freshness test, test_kvm_sequence.test_trajectories_fresh, explains it) matches today's digest."""
    _need(ROUTING)
    _need(DATA_ONLY_CSV)
    assert K.dump_stamp() == K.core_sources_digest(), "stale or unstamped dump: re-run CoreTests --dump"


def test_drivers_own_their_definition_types():
    """No script component declares a vanilla definition type in its [Definition] field. Two components
    declaring the same definition type make the game's definition-to-component lookup throw "Ambiguous match" for any
    untyped composite entry (ComponentInfoIndexer.cs:75-90), vanilla's or another mod's."""
    declared = set()
    fields = []
    for path in glob.glob(os.path.join(CLIENT, "**", "*.cs"), recursive=True) + \
            glob.glob(os.path.join(MOD, "Scripts", "Simulation", "**", "*.cs"), recursive=True):
        text = _read(path)
        declared |= set(re.findall(r"\b(?:class|struct|record)\s+(\w+)", text))
        fields += [(os.path.relpath(path, MOD), t) for t in re.findall(r"\[Definition\]\s*(?:public|private|protected|internal)?\s*readonly\s+([\w.]+)\??\s+\w+", text)]
    assert fields, "no [Definition] field found: the drivers moved?"
    foreign = [(p, t) for p, t in fields if t.split(".")[-1] not in declared]
    assert not foreign, f"script components must declare their own definition types: {foreign}"


def test_door_sides_follow_the_data():
    """KvmRackTable maps every rack's block GUID to that rack's own DoorSides constant, and the
    constants are dc/doors.py door_sides (bit 1 = front, the block's Forward; bit 2 = rear)."""
    guids = _read(os.path.join(MOD, "Scripts", "Simulation", "Shared", "DcGuids.g.cs"))
    link = _read(os.path.join(CLIENT, "Kvm", "KvmRackTable.cs"))
    pairs = re.findall(r"g == DcGuids\.(\w+)Block \? \(KvmDoorSides\)DcGuids\.(\w+)DoorSides", link)
    assert len(pairs) == len(RACKS) and all(a == b for a, b in pairs), pairs
    for spec in RACKS:
        name = spec.name.replace("DC_", "").replace("_", "")
        m = re.search(rf"public const int {name}DoorSides = (\d+);", guids)
        sides = doors.door_sides(spec)
        assert m and int(m.group(1)) == (1 if 1 in sides else 0) | (2 if -1 in sides else 0), (spec.name, sides)
        assert name in {a for a, _ in pairs}, spec.name
    core = _read(os.path.join(K.CORE_DIR, "KvmRackSlot.cs"))
    assert re.search(r"Front = 1 << 0,", core) and re.search(r"Rear = 1 << 1,", core), "KvmDoorSides bits changed"
