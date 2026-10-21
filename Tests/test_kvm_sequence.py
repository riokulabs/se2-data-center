"""The scripted KVM sequence, checked in geometry (dc/kvm_motion.py).

The trajectories are the motion core's own (Tests/CoreTests --dump: Source/Model/preview/plan4/traj/*.csv, 240 Hz).
Every clearance below is a LOWER bound over the swept motion (convex hulls of each part over each sample interval,
inflated by the rotation sagitta and the interpolation slack), so a pass cannot hide a collision between samples.
"""
import glob
import math
import os
import random

import pytest

from dc import catalog, doors, kvm_motion as K, subparts as S
from dc import dims as DM

# The trajectories are CoreTests output outside git: the conftest fixture regenerates them when stale or absent.
pytestmark = [pytest.mark.scripts, pytest.mark.usefixtures("trajectories")]

LEAF_MARGIN = 0.005       # the fast stow beats the closing leaves by 5 mm, with 0.1 s replication latency
LATENCY = 0.1
STATIC_MARGIN = 0.002     # frame and neighbours: no latency, built-mesh AABBs; 2 mm keeps a visible gap
DOOR_RACKS = K.DOOR_RACKS
STANDARD = ("open", "close", "fast_stow", "reverse_mid_slide", "reverse_mid_fold", "door_close_while_out")


def _slots(spec):
    return range(1, K.nslots(spec) + 1)


@pytest.fixture(scope="module")
def sweep():
    return K.load_sweep()


def _runs(path, sweep):
    return K.path_runs(path, sweep)


def _decimate(traj, k):
    d = traj[::k]
    return d if d[-1] == traj[-1] else d + [traj[-1]]


# ------------------------------------------------------------------------------------------------ subparts change

def _lid_at_before(f):
    """subparts.lid_at before the scripted sequence (frozen copy): the data-only simultaneous slide and fold."""
    f = min(1.0, max(0.0, f))
    dy, ang = S.TRAVEL * f, S.FOLD_DEG * f
    a = math.radians(ang)
    hx, hy, hz = S.HINGE
    out = []
    for x, y, z in S.lid_corners():
        y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
        out.append((x + hx, y + hy + dy, z + hz))
    return out


def test_lid_at_unchanged():
    for i in range(21):
        f = i / 20
        assert S.lid_at(f) == pytest.approx(_lid_at_before(f), abs=1e-12), f
        assert S.lid_at(f) == S.lid_at_pose(*S.pose(f))


# ------------------------------------------------------------------------------------------------ the inputs

def test_trajectories_fresh():
    """The dumped trajectories come from the motion-core sources on disk: the dump's stamp (written by a passing
    CoreTests --dump) is the digest of today's Scripts/Client/Core/*.cs. By content, so a fresh checkout or a copy,
    which reorders modification times, cannot fail it, and a source edit cannot slip past it."""
    csvs = glob.glob(os.path.join(K.TRAJ_DIR, "*.csv"))
    assert {os.path.splitext(os.path.basename(p))[0] for p in csvs} >= set(STANDARD) | {K.SWEEP}
    assert glob.glob(os.path.join(K.CORE_DIR, "*.cs"))
    assert K.dump_stamp() == K.core_sources_digest(), \
        "the trajectories are stale (or unstamped): cd Tests/CoreTests && dotnet run -c Release -- --dump " \
        "../../Source/Model/preview/plan4/traj"


def test_core_digest_is_by_content(tmp_path):
    """The digest follows the text and the file names, not line endings or modification times."""
    (tmp_path / "A.cs").write_bytes(b"class A {}\n")
    (tmp_path / "B.cs").write_bytes(b"class B {}\n")
    first = K.core_sources_digest(str(tmp_path))
    os.utime(tmp_path / "A.cs", (1, 1))
    (tmp_path / "B.cs").write_bytes(b"class B {}\r\n")
    assert K.core_sources_digest(str(tmp_path)) == first
    (tmp_path / "B.cs").write_bytes(b"class B { }\n")
    assert K.core_sources_digest(str(tmp_path)) != first
    (tmp_path / "B.cs").write_bytes(b"class B {}\n")
    (tmp_path / "B.cs").rename(tmp_path / "C.cs")
    assert K.core_sources_digest(str(tmp_path)) != first


def test_core_digest_covers_shared_core(tmp_path):
    """Scripts/Simulation/Shared/Core is compiled by CoreTests too, so editing it makes a dump stale."""
    (tmp_path / "A.cs").write_bytes(b"class A {}\n")
    assert K.core_sources_digest(str(tmp_path)) != K.core_sources_digest(str(tmp_path), K.SHARED_CORE_DIR)
    assert K.core_sources_digest() == K.core_sources_digest(K.CORE_DIR, K.SHARED_CORE_DIR)
    assert K.core_sources_digest() != K.core_sources_digest(K.CORE_DIR)
    scratch = tmp_path / "shared"
    scratch.mkdir()
    for f in os.listdir(K.SHARED_CORE_DIR):
        if f.endswith(".cs"):
            (scratch / f).write_bytes(open(os.path.join(K.SHARED_CORE_DIR, f), "rb").read())
    base = K.core_sources_digest(K.CORE_DIR, str(scratch))
    assert base == K.core_sources_digest()
    victim = scratch / sorted(os.listdir(scratch))[0]
    victim.write_bytes(victim.read_bytes() + b"// edit\n")
    assert K.core_sources_digest(K.CORE_DIR, str(scratch)) != base


def test_trajectories_shape(sweep):
    for name in STANDARD:
        tr = K.load(name)
        assert len(tr) > 100 and all(b[0] > a[0] for a, b in zip(tr, tr[1:])), name
        assert all(0.0 <= s <= 1.0 and 0.0 <= f <= 1.03 for _, s, f in tr), name
    assert len(sweep) == 16 + 16 + 18 + 18                                 # CoreTests kvm.reversal_sweep
    assert {rid.split("@")[0] for rid in sweep} == {"open_stow", "open_fast", "close_out", "close_fast"}
    for rid, (tr, at, target) in sweep.items():
        end = (1.0, 1.0) if target == "Out" else (0.0, 0.0)
        assert tr[-1][1:] == end, rid
        assert tr[0][0] == 0.0 < at < tr[-1][0], rid


def test_read_tuning():
    t = K.read_tuning()
    assert t["FoldGate"] == pytest.approx(0.91)
    assert t["MaxSubstep"] == pytest.approx(1 / 120)
    assert t["SlideOmegaFast"] <= 20 and t["FoldOmegaFast"] <= 20          # the spring ceiling
    assert t["RetractGateFast"] >= 0.04


# ------------------------------------------------------------------------------------------------ the measuring tools

def _box_dist(p, lo, hi):
    return math.sqrt(sum(max(lo[j] - p[j], 0.0, p[j] - hi[j]) ** 2 for j in range(3)))


def test_convex_distance_exact():
    """GJK against closed forms: point to box, box to box (separated on 1, 2 and 3 axes), and overlap = 0."""
    rng = random.Random(6)
    for _ in range(300):
        lo = tuple(rng.uniform(-1, 0) for _ in range(3))
        hi = tuple(lo[j] + rng.uniform(0.01, 1) for j in range(3))
        p = tuple(rng.uniform(-2, 2) for _ in range(3))
        assert K.convex_distance([p], K._corners(lo, hi)) == pytest.approx(_box_dist(p, lo, hi), abs=1e-9)
        q0 = tuple(rng.uniform(-2, 2) for _ in range(3))
        q1 = tuple(q0[j] + rng.uniform(0.01, 1) for j in range(3))
        gap = math.sqrt(sum(max(0.0, lo[j] - q1[j], q0[j] - hi[j]) ** 2 for j in range(3)))
        assert K.convex_distance(K._corners(lo, hi), K._corners(q0, q1)) == pytest.approx(gap, abs=1e-9)
    # a rotated box: distance from a point straight above its top face
    c = S.rot_x
    box = [c(p, 30.0) for p in K._corners((-1, -1, -1), (1, 1, 1))]
    top = c((0, 0, 1), 30.0)
    n = c((0, 0, 1.0), 30.0)
    assert K.convex_distance([tuple(top[j] + 0.5 * n[j] for j in range(3))], box) == pytest.approx(0.5, abs=1e-9)


def test_grid_agrees_with_hulls():
    """A uniform leaf sampling (a 41 x 9 grid over the leaf's mid-plane, less its half thickness) agrees with the
    exact box-to-box distance at the race's closest instant, to within the grid's resolution."""
    spec = catalog.BY_NAME["DC_Rack42_SplitFront"]
    tr = K.load("door_close_while_out")
    rep = K.leaf_clearance_report(tr, spec, 4, DM.DOOR_SECONDS, LATENCY)
    t = rep["at"][0]
    _, s, f = min(tr, key=lambda r: abs(r[0] - t))
    fr = K.door_fraction(t, -LATENCY, DM.DOOR_SECONDS)
    lf = next(x for x in doors.leaves(spec) if x["name"] == rep["at"][1])
    part = K.to_rack(K.kvm_parts(s, f)[rep["at"][2]], spec, 4)
    exact = K.convex_distance(part, K.leaf_box(spec, lf, fr))
    grid = min(K.convex_distance([p], part) for p in K.leaf_grid(spec, lf, fr)) - DM.DOOR_HALF_T
    step = (DM.DOOR_W + DM.DOOR_KNUCKLE_R) / 40
    assert exact - 1e-9 <= grid <= exact + step, (exact, grid)


def test_swept_bound_brackets_samples():
    """The swept lower bound sits under the instant-sampled distance, and close to it (240 Hz samples)."""
    spec = catalog.BY_NAME["DC_Rack24_SplitFrontRear"]
    rep = K.leaf_clearance_report(K.load("door_close_while_out"), spec, 2, DM.DOOR_SECONDS, LATENCY, facing=-1)
    assert rep["min"] <= rep["sampled"] <= rep["min"] + 0.005, rep


def test_self_intrusion_reproduces_the_data_only_rule():
    """The data-only motion (slide and fold together, linear) run through self_intrusion gives the data's 0.1325 m
    (the swept bound may only add to it), so the rule is the same one the scripted motion now passes."""
    data_only = [(i / 240, i / 240, i / 240) for i in range(241)]
    v = K.self_intrusion(data_only)
    assert S.transient_intrusion()["max_above_bay_roof"] == 0.1325
    assert 0.1325 - 0.0005 <= v <= 0.1325 + 0.003, v


# ------------------------------------------------------------------------------------------------ the pads bite

@pytest.mark.parametrize("k", [6, 12, 24])
def test_swept_bounds_hold_when_decimated(k):
    """The pads (interpolation slack, rotation sagitta) are what keep a swept bound on the safe side of the truth. At
    240 Hz they are tiny, so test them where they matter: decimate a trajectory to 40, 20 and 10 Hz and the swept
    bound must still sit on the safe side of the fine (240 Hz) instant samples, which approximate the truth from the
    other side. Zeroing the pads, the slack or the sagitta fails this."""
    spec = catalog.BY_NAME["DC_Rack24_SplitFront"]
    race = K.load("door_close_while_out")
    fine = K.leaf_clearance_report(race, spec, 2, DM.DOOR_SECONDS, LATENCY)["sampled"]
    assert K.leaf_clearance(_decimate(race, k), spec, 2, DM.DOOR_SECONDS, LATENCY) <= fine
    for name in ("open", "fast_stow", "reverse_mid_fold"):
        tr, coarse = K.load(name), _decimate(K.load(name), k)
        true = K.obstacle_clearance(tr, spec, 2, swept=False)
        for ob, d in K.obstacle_clearance(coarse, spec, 2).items():
            assert d <= true[ob], (name, k, ob, d, true[ob])
        assert K.self_intrusion(coarse) >= K.self_intrusion(tr, swept=False), (name, k)
        assert K.max_height(coarse) >= K.max_height(tr, swept=False), (name, k)


def test_sagitta_covers_a_coarse_arc():
    """A lid swept 0 -> 100 degrees in two 50 degree steps (linear: no interpolation slack): the hull of the end poses
    alone misses the arc's apex at 90 degrees; the sagitta pad covers it."""
    coarse = [(0.0, 1.0, 0.0), (0.5, 1.0, 0.5), (1.0, 1.0, 1.0)]
    fine = [(i / 240, 1.0, i / 240) for i in range(241)]
    assert K.max_height(coarse) >= K.max_height(fine, swept=False) == pytest.approx(S.HINGE[2] + K.LID_RADIUS, abs=1e-4)
    assert K.max_y_above(coarse, 0.20) >= K.max_y_above(fine, 0.20, swept=False)


# ------------------------------------------------------------------------------------------------ per-slot paths

def test_motion_path_for_slot():
    """A full rack's top slot (the containment rail and roof above) runs the data-only path; every other slot, and
    every slot of a half rack (half racks get top-rim label pads, no containment), runs the sequence."""
    for name, spec in catalog.BY_NAME.items():
        if spec.family != "rack":
            continue
        n = K.nslots(spec)
        paths = [K.motion_path_for_slot(name, slot) for slot in range(1, n + 1)]
        full = name.startswith("DC_Rack42_")
        assert paths == [K.SEQUENCED] * (n - 1) + [K.DATA_ONLY if full else K.SEQUENCED], name
        assert K.motion_path_for_slot(spec, n) == paths[-1]
        for bad in (0, n + 1):
            with pytest.raises(ValueError):
                K.motion_path_for_slot(spec, bad)


def test_data_only_path_is_the_vanilla_motion():
    tr = K.data_only_trajectory([(0.0, 0.0, 1.0)])
    assert tr[0] == (0.0, 0.0, 0.0) and tr[-1] == pytest.approx((S.POP_TIME, 1.0, 1.0))
    assert all(s == f and s == pytest.approx(min(1.0, t / S.POP_TIME)) for t, s, f in tr)
    names = [n for n, _, _ in K.path_runs(K.DATA_ONLY)]
    assert {"data_only_open", "data_only_close", "data_only_door_close_while_out"} <= set(names) and len(names) == 21


def _path_slots(spec):
    """[(slot, path)] for the representative slots: 1, 2 and the top (test_middle_slots_are_alike)."""
    return [(slot, K.motion_path_for_slot(spec, slot)) for slot in _representative_slots(spec)]


# ------------------------------------------------------------------------------------------------ the KVM's own panel

@pytest.mark.parametrize("name", ["open", "close", "reverse_mid_slide", "reverse_mid_fold"])
def test_sequence_never_enters_upper_panel(name):
    assert K.self_intrusion(K.load(name)) <= 0.0


def test_no_trajectory_enters_upper_panel(sweep):
    """The sequence never enters the KVM's own upper panel. The data-only path (a full rack's top slot) does, by the
    accepted transient (0.1325 m, the lid cutting through its own port bank mid-motion), and
    never by more: at the instants it is that transient (0.1328 exact; 41 samples gave 0.1325); the swept bound adds
    its pads, most at a reversal's kink, where the second-difference slack over-estimates (on the safe side)."""
    worst = max((K.self_intrusion(tr), rid) for rid, tr, _ in _runs(K.SEQUENCED, sweep))
    assert worst[0] <= 0.0, worst
    for rid, tr, _ in _runs(K.DATA_ONLY, sweep):
        at = K.self_intrusion(tr, swept=False)
        assert at <= 0.1325 + 0.0005, (rid, at)
        assert K.self_intrusion(tr) <= 0.1325 + 0.005, rid


def test_fold_gate_margin():
    gate = K.min_safe_fold_gate()
    assert 0.5 < gate < 1.0
    assert K.read_tuning()["FoldGate"] * S.TRAVEL >= gate * S.TRAVEL + 0.010


# ------------------------------------------------------------------------------------------------ the door race

def _door_run(path, sweep):
    return next((tr, t0) for rid, tr, t0 in _runs(path, sweep) if rid.endswith("door_close_while_out"))


@pytest.mark.parametrize("name", DOOR_RACKS)
def test_fast_stow_clears_closing_leaves(name, sweep):
    """The rack doors close (OpenRatio 1 -> 0 linear over DOOR_SECONDS) while the KVM is out; the
    leaves start LATENCY before the trajectory's t = 0 (so 0.2 s before the sequencer reacts at t = 0.1: strict).
    Every slot, on the path that slot runs, the front-facing KVM and (FrontRear) the rear-facing one."""
    spec = catalog.BY_NAME[name]
    for facing in [s for s in (1, -1) if s in doors.door_sides(spec)]:
        for slot in _slots(spec):
            tr, t0 = _door_run(K.motion_path_for_slot(spec, slot), sweep)
            d = K.leaf_clearance(tr, spec, slot, DM.DOOR_SECONDS, LATENCY, facing=facing, t0=t0)
            assert d >= LEAF_MARGIN, (name, slot, facing, d)


def test_fast_stow_from_any_moment_clears_leaves(sweep):
    """The doors may start closing at any moment of an open or a close: the leaves start LATENCY before the sequencer
    hears of it. The sequence: the sweep's FastStow runs in the bottom slot (the leaves' whole height overlaps the KVM
    there; other slots and the rear facing differ only by translation and symmetry). The data-only path: its door
    runs in the full rack's top slot, both facings; on this path the script still stows on a closing door, along the
    same simultaneous path at the vanilla speed, and that already wins (the drawer starts home at once)."""
    spec = catalog.BY_NAME["DC_Rack42_SplitFrontRear"]
    top = K.nslots(spec)
    for slot, facings in ((1, (1,)), (top, (1, -1))):
        for rid, tr, t0 in _runs(K.motion_path_for_slot(spec, slot), sweep):
            if t0 is None:
                continue
            for facing in facings:
                d = K.leaf_clearance(tr, spec, slot, DM.DOOR_SECONDS, LATENCY, facing=facing, t0=t0)
                assert d >= LEAF_MARGIN, (rid, slot, facing, d)


# ------------------------------------------------------------------------------------------------ frame and neighbours

def _representative_slots(spec):
    n = K.nslots(spec)
    return sorted({1, 2, n})


def test_middle_slots_are_alike():
    """Relative to the KVM, every middle slot sees the same obstacles as slot 2, so slots 1, 2 and the top cover all."""
    for name in ("DC_Rack42_Open", "DC_Rack24_Open"):
        spec = catalog.BY_NAME[name]
        ref = K.obstacles(spec, 2)
        dz = K.slot_centre_z(spec, 2)
        for slot in range(3, K.nslots(spec)):
            assert K.motion_path_for_slot(spec, slot) == K.motion_path_for_slot(spec, 2)
            ob, z = K.obstacles(spec, slot), K.slot_centre_z(spec, slot)
            assert ob.keys() == ref.keys()
            for k in ("column_left", "column_right"):
                assert ob[k] == ref[k]                                   # full height
            for k in ("server_above", "server_below"):
                for a, b in zip(ob[k], ref[k]):
                    assert (a[0], a[1]) == (b[0], b[1]) and a[2] - z == pytest.approx(b[2] - dz)


@pytest.mark.parametrize("name", ["DC_Rack42_SplitFront", "DC_Rack24_SplitFront"])
def test_sequence_clears_frame_and_neighbours(name, sweep):
    """No run of the path a slot uses brings the drawer or the lid within STATIC_MARGIN of the rack's side columns, its
    plinth, its top or a server in the slot above or below (the sequence's six trajectories; the data-only path's
    runs). The top slot's lid already reaches into the tray / roof at rest (accepted): there
    the motion may rise no higher than the lid's own fold arc (its apex, passing vertical, is 2.5 mm above its 100
    degree rest; both paths pass it): exactly at the instants, and within the swept bound's pad (at most 1.5 mm, at a
    reversal's kink) over the intervals."""
    spec = catalog.BY_NAME[name]
    apex = S.HINGE[2] + K.LID_RADIUS
    for slot, path in _path_slots(spec):
        runs = [(n, K.load(n)) for n in STANDARD] if path == K.SEQUENCED else \
            [(rid, tr) for rid, tr, _ in _runs(path, sweep)]
        for rid, tr in runs:
            for k, d in K.obstacle_clearance(tr, spec, slot).items():
                if k == "top" and slot == K.nslots(spec):
                    assert K.rest_clearance(spec, slot)["top"] == 0.0        # the accepted static overlap
                    assert K.max_height(tr, swept=False) <= apex + 1e-9, (rid, K.max_height(tr, swept=False), apex)
                    assert K.max_height(tr) <= apex + 0.0015, (rid, K.max_height(tr), apex)
                    continue
                assert d >= STATIC_MARGIN, (name, slot, path, rid, k, d)


def test_sweep_clears_frame_and_neighbours(sweep):
    """Every reversal of the sweep, in a middle slot (both neighbours present)."""
    spec = catalog.BY_NAME["DC_Rack24_SplitFront"]
    for rid, (tr, _, _) in sweep.items():
        for k, d in K.obstacle_clearance(tr, spec, 2).items():
            assert d >= STATIC_MARGIN, (rid, k, d)


# ------------------------------------------------------------------------------------------------ the room

def _z_cut(spec, slot):
    """ZT (the slot band's top) in slot `slot`'s KVM frame; the same as the room's local-z rule (d["ZT"] vs its zc)."""
    H, ZT, _ = doors.rack_dims(spec)
    n = K.nslots(spec)
    assert K.slot_centre_z(spec, n) + H / 2 == pytest.approx(0.25 + DM.SLOT_H * (n - 1) + DM.SLOT_H / 2)
    return ZT - H / 2 - K.slot_centre_z(spec, slot)


def test_sequence_clears_plan3_roof_and_rail(sweep):
    """The room's rules over the motion each slot actually runs, in every full rack's two highest slots (no
    lower slot reaches the tray band) and for both facings (the rail and the roof run along front and back):
    - test_kvm_clear_of_rail: wherever any part rises above the slot band, it stays behind the containment rail;
    - test_roof_clears_kvm_and_rack_doors: over the aisle (beyond the cell plane), every part stays under the roof
      (ZT + ROOF_CLEAR).
    The values come from dims when it defines them, else kvm_motion's fallbacks (kvm_motion.PLAN3_*)."""
    rail, clear = K.PLAN3_RAIL_Y[0], K.PLAN3_ROOF_CLEAR
    cases = {}                                      # the three 42U variants share the frame: measure each case once
    for name in ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear"):
        spec = catalog.BY_NAME[name]
        n = K.nslots(spec)
        for slot in (n - 1, n):
            cases.setdefault((round(_z_cut(spec, slot), 9), K.motion_path_for_slot(spec, slot)), []).append((name, slot))
    assert len(cases) == 2
    for (z_cut, path), where in cases.items():
        for rid, tr, _ in _runs(path, sweep):
            assert K.max_y_above(tr, z_cut) < rail, (where, rid, K.max_y_above(tr, z_cut))
            assert K.max_z_beyond(tr, K.AISLE_Y) < z_cut + clear, (where, rid)


def test_sequence_would_hit_the_rail_in_the_top_slot():
    """Why the full rack's top slot is routed to the data-only path: the sequence's lid folds with the drawer fully
    out and would rise above the slot band in front of the rail. If the sequence ever clears it, drop the routing."""
    spec = catalog.BY_NAME["DC_Rack42_Open"]
    assert K.max_y_above(K.load("open"), _z_cut(spec, K.nslots(spec))) >= K.PLAN3_RAIL_Y[0]
