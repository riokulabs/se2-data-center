"""Plan 2 Tasks 2-3: the cable continuity contract (dc/tray_lanes.py), the tray catalogue and the cable plans of
every piece (dc/tray_plan.py, dc/tray_bends.py). No Blender: the plans are proven here, and the builder only sweeps
what they say.

The sweeps run over every piece x density x port (the bends and junctions included); the bend and junction tests
are at the end."""
import itertools
import json
import math
import os

import numpy as np
import pytest

from dc import catalog, config, dims as DM, tray_lanes as TL, tray_plan as P
from dc.tray_lanes import CELL, FLOOR_Z, R_B, R_WF

TRAY_FAMILIES = ("tray", "trayrods")
TRAYS = [b for b in catalog.CATALOGUE if b.family in TRAY_FAMILIES]
IMPLEMENTED = TRAYS
PLANS = {b.name: P.plan(b) for b in IMPLEMENTED}
PORTED = [n for n, p in PLANS.items() if p.ports]           # pieces with ports (all but the Chute and Rods)
EPS = 1e-9
COS_TOL = math.cos(math.radians(TL.ANG_TOL_DEG))


def ids(names):
    return [n.replace("DC_", "") for n in names]


def on_grid(v, pitch=CELL, tol=1e-9):
    q = v / pitch
    return abs(q - round(q)) < tol


def port_ends(plan, port):
    """[(point, outward dir, material, lane ref, bundle)] of the PORT ends at port `port`."""
    out = []
    for b in plan.bundles:
        for i, e in enumerate(b.ends):
            if e.kind == "PORT" and e.ref.split(":")[0] == port:
                out.append((b.end_point(i), b.end_dir(i), b.material, e.ref.split(":")[1], b))
    return out


def joint_errors(A, pa, B, pb, T):
    """Why B (moved by T) does not meet A at the joint pa / pb, lane for lane ([] = it does)."""
    ea = port_ends(A, pa)
    eb = [(T(p), T.dir(d), m, ref) for p, d, m, ref, _ in port_ends(B, pb)]
    errs = []
    if len(ea) != len(eb):
        errs.append(f"{len(ea)} lanes meet {len(eb)}")
    used = set()
    for p, d, m, ref, _ in ea:
        dist = [np.linalg.norm(p - q) for q, *_ in eb]
        if not dist:
            continue
        j = int(np.argmin(dist))
        q, dq, mq, rq = eb[j]
        if dist[j] > TL.POS_TOL:
            errs.append(f"{ref}: nearest lane {rq} is {dist[j] * 1000:.2f} mm away")
        elif mq != m:
            errs.append(f"{ref}: {m} meets {mq}")
        elif d @ dq > -COS_TOL:
            errs.append(f"{ref}: bundles meet at an angle")
        if j in used:
            errs.append(f"{ref}: lane {rq} matched twice")
        used.add(j)
    return errs


def seg_dist(p, a, b):
    """Distances from points p (N,3) to every segment a[i] -> b[i] (M,3): (N, M)."""
    ab = b - a
    L2 = np.maximum((ab * ab).sum(1), 1e-18)
    t = np.clip(((p[:, None, :] - a[None]) * ab[None]).sum(2) / L2[None], 0, 1)
    c = a[None] + t[..., None] * ab[None]
    return np.linalg.norm(p[:, None, :] - c, axis=2)


def resample(pts, step=0.004):
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, math.ceil(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return np.array(out)


def split_points(plan):
    """{(child lane, parent lane): split point}."""
    return {(b.lane, e.ref): b.end_point(i) for b in plan.bundles for i, e in enumerate(b.ends) if e.kind == "SPLIT"}


# ---------------------------------------------------------------------------------------------------- catalogue
def test_catalogue_counts():
    assert len(TRAYS) == 38
    grid = [b for b in TRAYS if b.variant in catalog.TRAY_SHAPES]
    assert len(grid) == 28 == 7 * 4
    assert {(b.variant, b.density) for b in grid} == set(itertools.product(catalog.TRAY_SHAPES, TL.DENSITIES))
    by_variant = {v: sorted(b.density or "" for b in TRAYS if b.variant == v) for v in ("Drop", "Reducer")}
    assert by_variant["Drop"] == by_variant["Reducer"] == sorted(TL.DENSITIES[1:])
    assert "DC_Tray_Drop_Empty" not in catalog.BY_NAME and "DC_Tray_Reducer_Empty" not in catalog.BY_NAME
    assert [b.name for b in TRAYS if b.family == "trayrods"] == ["DC_TrayRods_025", "DC_TrayRods_100",
                                                                  "DC_TrayRods_200"]
    assert all(len(b.name) <= 40 for b in TRAYS)
    for b in TRAYS:
        want = ("Blocks/Walls/Inserts/Pipes", "WallInsertPipes") if b.family == "tray" else \
            ("Blocks/Truss/Struts/Long", "StructuralSupportStraight")
        assert (b.vanilla_source, b.copy_from) == want, b.name
        assert not b.functional
        assert b.name == (f"DC_Tray_{b.variant}" + (f"_{b.density}" if b.density else "") if b.family == "tray"
                          else b.name)
    # copy_from matches the vanilla file prefix for both sources (test_catalog.test_copy_from_matches_vanilla runs
    # over the whole catalogue; this pins that both new sources are in it)
    for src, prefix in {(b.vanilla_source, b.copy_from) for b in TRAYS}:
        files = os.listdir(os.path.join(config.VANILLA_REF, src))
        assert f"{prefix}.partialdef" in files, src


def test_trays_in_the_pipeline():
    """The tray families are catalogued and, since Task 5, in the definitions pipeline (Ruling P2-15)."""
    assert [b for b in catalog.BLOCKS if b.family in TRAY_FAMILIES] == TRAYS
    assert all(catalog.BY_NAME[b.name] is b for b in TRAYS)
    assert catalog.TRAY_DENSITIES == TL.DENSITIES


def test_select_prefix():
    import build_dc
    names = [s.name for s in build_dc.select(["DC_Tray_Straight*"])]
    assert names == [f"DC_Tray_Straight{k}_{d}" for k in "SL" for d in TL.DENSITIES]
    assert [s.name for s in build_dc.select(["DC_Tray_Chute", "DC_Tray_Chute*"])] == ["DC_Tray_Chute"]
    assert build_dc.select(["all"]) == catalog.BLOCKS
    with pytest.raises(SystemExit):
        build_dc.select(["DC_Nope*"])


# ---------------------------------------------------------------------------------------------------- lanes
def test_lane_table():
    assert len(TL.lanes("Full")) == 9
    assert len(TL.lanes("Moderate")) == 5
    assert len(TL.lanes("Low")) == 2
    assert TL.lanes("Empty") == []
    assert (TL.R_B, TL.R_CABLE) == (0.027, 0.009)
    for l in TL.LANES:   # mirror symmetry, same material on mirrored lanes
        m = [k for k in TL.LANES if abs(k.s + l.s) < EPS and abs(k.h - l.h) < EPS and k.material == l.material]
        assert m and m[0].first == l.first and m[0].name == TL.mirror(l.name), l.name
    assert max(abs(l.s) for l in TL.LANES) + R_B < TL.WALL_S - 0.004     # inside the walls
    assert max(l.h for l in TL.LANES) + R_B < TL.WALL_H                   # below the top wire
    assert max(l.h for l in TL.LANES) + R_B == pytest.approx(0.087)       # the plan's bundle top at Full
    assert {l.material for l in TL.LANES} == {"PaintedMetalColorable", "PaintedMetalYellow", "PaintedMetalGrey",
                                              "Rubber"}


def test_lane_packing():
    """Bundles at a port never overlap, and every one rests on something: the floor, or two bundles below."""
    for a, b in itertools.combinations(TL.LANES, 2):
        assert math.hypot(a.s - b.s, a.h - b.h) >= 2 * R_B - TL.TOUCH_TOL, (a.name, b.name)
    for l in TL.LANES:
        if l.h == pytest.approx(R_B):
            continue
        under = [k for k in TL.LANES if k.h < l.h and math.hypot(k.s - l.s, k.h - l.h) <= 2 * R_B + 0.001]
        under.sort(key=lambda k: k.s)
        assert len(under) == 2 and under[0].s < l.s < under[1].s, l.name
        assert all(TL.level(k.first) <= TL.level(l.first) for k in under), f"{l.name} rests on a later lane"


def test_density_nesting():
    for a, b in itertools.combinations_with_replacement(TL.DENSITIES, 2):
        assert set(TL.lanes(a)) <= set(TL.lanes(b)), (a, b)
    for d in TL.DENSITIES[1:]:
        assert set(TL.lanes(TL.step_down(d))) < set(TL.lanes(d))
        assert TL.lane_set(d) == {TL.lane_key(l.s, l.h, l.material) for l in TL.lanes(d)}


# ---------------------------------------------------------------------------------------------------- ports
@pytest.mark.parametrize("name", PORTED, ids=ids(PORTED))
def test_ports_on_grid(name):
    pl = PLANS[name]
    size = pl.size
    assert set(pl.ports) == set("abcd"[:{"Tee": 3, "Cross": 4}.get(pl.shape, 2)])
    for p in pl.ports.values():
        o, t, s, u = p.frame()
        for v in (t, u):
            assert sorted(np.abs(v)) == pytest.approx([0, 0, 1]), "port axes are grid axes"
        assert abs(t @ u) < EPS
        k = int(np.argmax(np.abs(t)))   # o lies on the box face that t points out of
        assert o[k] == pytest.approx(size[k] if t[k] > 0 else 0.0, abs=EPS), p.name
        assert np.all(o > -EPS) and np.all(o < size + EPS), "o inside the face"
        assert on_grid(o @ s), f"{p.name}: across coordinate {o @ s} off the grid"
        assert on_grid(o @ u - FLOOR_Z), f"{p.name}: floor top not FLOOR_Z in front of a grid plane"
        # the whole tray cross-section (walls, basket bottom, top wire) lies inside the box at the port
        for corner in (o + (TL.WALL_S + TL.WIRE_R) * s, o - (TL.WALL_S + TL.WIRE_R) * s,
                       o + (P.BASKET_BOTTOM - FLOOR_Z) * u, o + (TL.WALL_H + TL.EDGE_WIRE_R) * u):
            assert np.all(corner > -EPS) and np.all(corner < size + EPS), p.name


@pytest.mark.parametrize("name", PORTED, ids=ids(PORTED))
def test_port_lanes_match_density(name):
    pl = PLANS[name]
    for p in pl.ports.values():
        got, refs = set(), set()
        for q, _, m, ref, _ in port_ends(pl, p.name):
            _, s, h = p.local(q)
            got.add(TL.lane_key(s, h, m))
            lane = TL.LANE[ref]   # the ref names the lane it ends on, in that port's frame
            assert (s, h, m) == (pytest.approx(lane.s, abs=TL.POS_TOL), pytest.approx(lane.h, abs=TL.POS_TOL),
                                 lane.material), (p.name, ref)
            refs.add(ref)
        assert got == TL.lane_set(p.density), (name, p.name)
        assert refs == {l.name for l in TL.lanes(p.density)}
    spec = catalog.BY_NAME[name]
    if spec.variant == "Reducer":
        assert pl.ports["a"].density == spec.density
        assert pl.ports["b"].density == TL.step_down(spec.density)
    else:
        assert pl.ports["a"].density == pl.ports["b"].density == spec.density


# ---------------------------------------------------------------------------------------------------- bundles
@pytest.mark.parametrize("name", list(PLANS), ids=ids(PLANS))
def test_bundle_ends_typed(name):
    pl = PLANS[name]
    lanes_of = {b.lane: b for b in pl.bundles}
    assert len(lanes_of) == len(pl.bundles), "bundle ids unique"
    for b in pl.bundles:
        for i, e in enumerate(b.ends):
            assert e.kind in TL.END_KINDS, e
            p, d = b.end_point(i), b.end_dir(i)
            if e.kind == "PORT":
                port_name, lane_name = e.ref.split(":")
                port = pl.ports[port_name]
                assert np.linalg.norm(p - TL.lane_point(port, TL.LANE[lane_name])) <= TL.POS_TOL, (b.lane, e)
                assert d @ np.asarray(port.t) >= COS_TOL, f"{b.lane} leaves {port_name} at an angle"
                pts = b.points if i == 1 else b.points[::-1]
                run = np.cumsum(np.r_[0, np.linalg.norm(np.diff(pts[::-1], axis=0), axis=1)])
                tail = pts[::-1][run <= TL.PORT_STRAIGHT + EPS]
                assert run[-1] >= TL.PORT_STRAIGHT and len(tail) >= 2
                off = np.linalg.norm(np.cross(tail - p, d), axis=1)
                assert off.max() < 1e-4, f"{b.lane}: not straight over its last 5 cm at {port_name}"
            elif e.kind == "SPLIT":
                parent = lanes_of[e.ref]
                assert parent is not b
                assert seg_dist(p[None], parent.points[:-1], parent.points[1:]).min() <= TL.SPLIT_TOL
                collars = [f for f in pl.fittings if f.kind == "split_collar" and f.params["bundle"] == e.ref]
                assert collars and min(np.linalg.norm(f.frame.o - p) for f in collars) <= 0.03, b.lane
            elif e.kind == "BOOT":
                boots = [f for f in pl.fittings if f.kind == "boot" and f.params["bundle"] == b.lane]
                clamps = [f for f in pl.fittings if f.kind == "saddle_clamp" and f.params["bundle"] == b.lane]
                assert len(boots) == len(clamps) == 1, b.lane
                bt, cl = boots[0], clamps[0]
                # the boot sleeves the end along its direction; the clamp's band straps the boot's body
                rel = bt.frame.o - p
                assert np.linalg.norm(np.cross(rel, d)) < 1e-6 and 0 < rel @ d < P.BOOT_L
                along = (cl.frame.o - bt.frame.o) @ d
                assert abs(along) + cl.size[0] / 2 <= bt.size[0] / 2, f"{b.lane}: the band is off the boot body"
                band = cl.frame.o + cl.params["band_dz"] * cl.frame.u
                assert np.linalg.norm(np.cross(band - bt.frame.o, d)) < 1e-9, "the band is coaxial with the boot"
                assert cl.params["band_r"] == pytest.approx(bt.params["radius"] + TL.STRAP_T)
                assert cl.frame.o[0] == pytest.approx(P.CLAMP_X) and p[0] == pytest.approx(P.BOOT_X)
                assert cl.params["post_hw"] >= 0.0075, f"{b.lane}: clamp post too thin to be a clamp"
                # the boot rests on something: the floor (its own wall lifts the bundle) or the bundles below
                assert bt.frame.o[2] - bt.params["radius"] >= FLOOR_Z - 1e-9
            else:
                ents = [en for en in pl.entries if en.name == e.ref]
                assert len(ents) == 1, e
                inside, off = ents[0].margin(p)
                assert off < EPS and inside >= R_WF + 0.003, (b.lane, inside)
                assert d @ ents[0].n >= COS_TOL, f"{b.lane} does not leave through its entry plumb"


@pytest.mark.parametrize("name", list(PLANS), ids=ids(PLANS))
def test_bundle_sampling(name):
    """<= 2 cm steps, the contract radii and materials, and no kinks: every bend radius >= 5 cm (the waterfall's
    climb; cable bend limits are ~4 x the cable diameter)."""
    for b in PLANS[name].bundles:
        steps = np.linalg.norm(np.diff(b.points, axis=0), axis=1)
        assert steps.max() <= TL.BUNDLE_STEP + EPS and steps.min() > 1e-6, b.lane
        if b.lane.startswith("WF"):
            assert (b.radius, b.material) == (R_WF, "PaintedMetalColorable")
        else:
            lane = TL.LANE[b.lane_name]
            assert (b.radius, b.material) == (R_B, lane.material), b.lane
        p = b.points
        for i in range(1, len(p) - 1):
            a, c = p[i] - p[i - 1], p[i + 1] - p[i]
            cos = a @ c / np.linalg.norm(a) / np.linalg.norm(c)
            if cos > 1 - 1e-12:
                continue
            chord = np.linalg.norm(p[i + 1] - p[i - 1])
            radius = chord / (2 * math.sin(math.acos(min(1.0, cos))))
            assert radius >= P.WF_RISE_R - 1e-4, f"{b.lane}: bend radius {radius:.3f} m at {p[i]}"


def parent_station(parent, pts):
    """Per point, the arc length along `parent` of its nearest centreline point."""
    a, b = parent.points[:-1], parent.points[1:]
    ab = b - a
    L2 = np.maximum((ab * ab).sum(1), 1e-18)
    t = np.clip(((pts[:, None, :] - a[None]) * ab[None]).sum(2) / L2[None], 0, 1)
    d = np.linalg.norm(pts[:, None, :] - (a[None] + t[..., None] * ab[None]), axis=2)
    j = d.argmin(axis=1)
    cum = np.r_[0, np.cumsum(np.sqrt(L2))]
    return cum[j] + t[np.arange(len(pts)), j] * np.sqrt(L2[j])


def split_run(child, parent):
    """The child's samples (from its SPLIT end) that are exempt from its parent (Ruling P2-16): the run from the split
    point over which it still overlaps its parent, which must end within the split zone (the collar length plus the
    child's peel radius, measured along the parent). -> (child samples, exempt mask)."""
    i = next(k for k, e in enumerate(child.ends) if e.kind == "SPLIT" and e.ref == parent.lane)
    pts = resample(child.points if i == 0 else child.points[::-1])
    gap = seg_dist(pts, parent.points[:-1], parent.points[1:]).min(axis=1) - child.radius - parent.radius
    clear = np.nonzero(gap >= -TL.TOUCH_TOL)[0]
    n = clear[0] if clear.size else len(pts)
    st = parent_station(parent, pts)
    inside = np.abs(st - st[0]) <= TL.split_zone(child.params["peel_r"])
    mask = np.zeros(len(pts), bool)
    mask[:n] = inside[:n]
    return pts, mask


def split_exempt(pl, A, B, pts):
    """Per point of `pts` (sampled on A or B), whether it lies in A and B's parent-child split run: on the child's
    exempt run, or (on the parent) nearest to a point of it."""
    for child, parent in ((A, B), (B, A)):
        if any(e.kind == "SPLIT" and e.ref == parent.lane for e in child.ends):
            cp, mask = split_run(child, parent)
            near = np.linalg.norm(pts[:, None, :] - cp[None], axis=2).argmin(axis=1)
            return mask[near] & (np.linalg.norm(pts - cp[near], axis=1) <= A.radius + B.radius + 0.01)
    return np.zeros(len(pts), bool)


def pair_gaps(pl, A, B):
    """Surface gap (centreline distance - r1 - r2) from A's samples to B and from B's to A, split zone excluded."""
    out = []
    for P_, Q in ((A, B), (B, A)):
        pts = resample(P_.points)
        d = seg_dist(pts, Q.points[:-1], Q.points[1:]).min(axis=1) - A.radius - B.radius
        out.append(d[~split_exempt(pl, A, B, pts)])
    return np.concatenate(out)


@pytest.mark.parametrize("name", list(PLANS), ids=ids(PLANS))
def test_no_bundle_interpenetration(name):
    """Bundles never interpenetrate (centreline distance >= r1 + r2 - 1 mm), except a child and its parent in their
    split zone."""
    pl = PLANS[name]
    for A, B in itertools.combinations(pl.bundles, 2):
        g = pair_gaps(pl, A, B)
        assert g.size == 0 or g.min() >= -TL.TOUCH_TOL, f"{name}: {A.lane} / {B.lane} {g.min() * 1000:.1f} mm"


def test_split_zone_has_teeth():
    """Every child carries its peel radius; outside its zone it really clears its parent (the zone is not the whole
    bundle), and shrinking the zone to the old 5 cm makes the Tee's M0 peel fail."""
    seen = 0
    for pl in PLANS.values():
        for b in pl.bundles:
            if b.ends[0].kind == "SPLIT":
                seen += 1
                assert b.params["peel_r"] >= 0.05
                parent = pl.bundle(b.ends[0].ref)
                pts, mask = split_run(b, parent)
                assert not mask.all() and not mask[np.argmax(~mask):].any(), f"{b.lane} never clears its parent"
                gap = seg_dist(pts[~mask], parent.points[:-1], parent.points[1:]).min(axis=1) - b.radius - parent.radius
                assert gap.min() >= -TL.TOUCH_TOL
    assert seen > 0
    pl = P.plan("Tee", "Moderate")
    child, parent = pl.bundle("M0/c"), pl.bundle("M0")
    pts = resample(child.points)
    near = np.linalg.norm(pts - child.end_point(0), axis=1) <= 0.05
    d = seg_dist(pts[~near], parent.points[:-1], parent.points[1:]).min(axis=1) - 2 * R_B
    assert d.min() < -TL.TOUCH_TOL


def _in_box(pts, size, margin, port_planes=()):
    """Assert points inside [0, size]; `margin` from every face that is not a port / entry plane."""
    lo, hi = np.zeros(3), size
    for k in range(3):
        for face, sign in ((lo[k], 1), (hi[k], -1)):
            m = 0.0 if (k, face) in port_planes else margin
            gap = sign * (pts[:, k] - face)
            assert gap.min() >= m - 1e-9, f"axis {'xyz'[k]} face {face}: {gap.min() * 1000:.2f} mm"


def _port_planes(pl):
    planes = set()
    for p in pl.ports.values():
        k = int(np.argmax(np.abs(p.t)))
        planes.add((k, float(round(p.o[k], 9))))
    for e in pl.entries:
        k = int(np.argmax(np.abs(e.n)))
        planes.add((k, float(round(e.o[k], 9))))
    return planes


@pytest.mark.parametrize("name", list(PLANS), ids=ids(PLANS))
def test_within_cells(name):
    """Every bundle cross-section, fitting and support lies inside the cell box, >= 1 mm from the faces except
    where a bundle crosses a port or entry plane (it ends exactly on it, square to it)."""
    pl = PLANS[name]
    size, planes = pl.size, _port_planes(pl)
    for b in pl.bundles:
        ext = P.cross_section_extent(b.points) * b.radius
        for sign in (-1, 1):
            _in_box(b.points + sign * ext, size, 0.001, planes)
        for i in (0, -1):   # the ends on a plane are square to it: no cross-section pokes through
            for k, face in planes:
                if abs(b.points[i][k] - face) < 1e-9:
                    assert ext[i][k] < 1e-6, f"{b.lane} meets plane {'xyz'[k]}={face} at an angle"
    entry = {(int(np.argmax(np.abs(e.n))), float(round(e.o[int(np.argmax(np.abs(e.n)))], 9))) for e in pl.entries}
    for f in pl.fittings:   # (Task 10) the landing collars sit ON their ENTRY plane (P.ENTRY_SEAT): an interface
        _in_box(P.fitting_points(f), size, 0.001, entry if f.kind == "brush_collar" else ())   # plane, like a port
    for sp in pl.supports:   # every solid, rod plates and couplers included: 1 mm inside every face too
        if sp.kind == "ladder":   # (Task 10) the Chute's foot and top plates sit ON its two ENTRY planes
            _in_box(P.support_points(sp), size, 0.001, entry)
        elif sp.params.get("flush"):   # (Task 6: the vertical turns' struts end ON the across faces, Keen's model size)
            _in_box(P.support_points(sp), size, 0.001, {(1, 0.0), (1, float(size[1]))})   # flush on y only
            assert abs(abs(float(np.asarray(sp.axis) @ [0, 1, 0])) - 1) < 1e-9 and pl.shape in ("TurnUp", "TurnDown")
        else:
            _in_box(P.support_points(sp), size, 0.001)


def test_support_solids_complete():
    """Support.solids lists every hardware part, so the box checks and occupancy see them all."""
    want = {"trapeze": {"strut": 1, "end_cap": 2, "rod_plate": 2},
            "rods": {"washer": 2, "coupler": 2, "anchor_plate": 2, "channel": 1, "end_cap": 2},
            "ladder": {"rail": 2, "rung": 5, "foot_plate": 1, "top_plate": 1},
            "floor_strut": {"strut": 1, "end_cap": 2}}
    seen = set()
    for pl in PLANS.values():
        for sp in pl.supports:
            parts = {}
            for part, *_ in sp.solids():
                parts[part] = parts.get(part, 0) + 1
            assert parts == want[sp.kind], (pl.shape, sp.kind, parts)
            seen.add(sp.kind)
            for part, fr, size, mat in sp.solids():
                assert min(size) > 0 and mat in ("PaintedMetalDarker", "PaintedMetalYellow", "MetalDull",
                                                 "BrushedMetal")
    assert seen == set(want)
    # the rod plates in particular: 1 mm inside the side faces (y), 1 mm under the top plane
    t = next(s for s in PLANS["DC_Tray_StraightS_Full"].supports if s.kind == "trapeze")
    for part, fr, size, _ in t.solids():
        if part == "rod_plate":
            c = fr.corners(size)
            assert c[:, 1].min() >= 0.001 - 1e-9 and c[:, 1].max() <= 0.5 - 0.001 + 1e-9
            assert c[:, 2].max() == pytest.approx(0.25 - P.END_INSET)


def test_waterfall_clearance():
    """The waterfalls keep WF_CLEAR (3 mm) off every bundle but their parent, at every density: mesh tessellation
    (6- and 8-sided cables) can't make them touch."""
    for d in TL.DENSITIES[1:]:
        pl = P.plan("Drop", d)
        for w in (b for b in pl.bundles if b.lane.startswith("WF")):
            pw = resample(w.points)
            for o in pl.bundles:
                if o is w or o.lane == w.ends[0].ref:
                    continue
                gap = seg_dist(pw, o.points[:-1], o.points[1:]).min() - w.radius - o.radius
                assert gap >= P.WF_CLEAR - 1e-9, f"{d}: {w.lane} / {o.lane} {gap * 1000:.2f} mm"


@pytest.mark.parametrize("name", list(PLANS), ids=ids(PLANS))
def test_fittings_clear_bundles(name):
    """Collars, boots, clamps, guides and tags never cut a bundle that is not theirs (straps hug their neighbours by
    design: they are measured round their own bundle only)."""
    pl = PLANS[name]
    splits = split_points(pl)
    for f in pl.fittings:
        if f.kind == "strap":
            continue
        own = {f.params.get("bundle")}
        if f.kind == "split_collar":
            own |= {c for (c, par), q in splits.items() if par == f.params["bundle"]
                    and np.linalg.norm(q - f.frame.o) <= 0.03}
        if f.kind == "waterfall_guide":
            own |= {b.lane for b in pl.bundles if b.lane.startswith("WF") and abs(b.end_point(1)[0] - f.frame.o[0])
                    < 1e-6}
        pts = P.fitting_points(f)
        carried = set(f.params.get("carries", ()))     # a saddle's bundles rest on its deck: touching, not cutting
        for b in pl.bundles:
            if b.lane in own:
                continue
            d = seg_dist(pts, b.points[:-1], b.points[1:]).min()
            need = b.radius - 1e-6 if b.lane in carried else b.radius + 0.001
            assert d >= need, f"{f.kind} ({f.params.get('bundle')}) cuts {b.lane}: {d * 1000:.1f} mm"


# ---------------------------------------------------------------------------------------------------- joints
def _pairs():
    out = []
    for A, B in itertools.product(PORTED, repeat=2):
        for pa, pb in itertools.product(PLANS[A].ports, PLANS[B].ports):
            if PLANS[A].ports[pa].density == PLANS[B].ports[pb].density:
                out.append((A, pa, B, pb))
    return out


PAIRS = _pairs()


def test_pair_sweep_is_complete():
    """Every (piece, port) of every density meets every other one of the same density."""
    by_density = {}
    for n in PORTED:
        for p in PLANS[n].ports.values():
            by_density.setdefault(p.density, []).append((n, p.name))
    assert len(PAIRS) == sum(len(v) ** 2 for v in by_density.values())
    assert set(by_density) == set(TL.DENSITIES)


def _assert_rigid_grid(T):
    assert np.allclose(T.R @ T.R.T, np.eye(3)) and np.linalg.det(T.R) == pytest.approx(1.0)
    assert np.allclose(np.abs(T.R), np.round(np.abs(T.R))), "a grid rotation"
    assert all(on_grid(v, tol=1e-9) for v in T.d), f"box corner off the grid: {T.d}"


@pytest.mark.parametrize("A,pa,B,pb", PAIRS, ids=[f"{ids([a])[0]}.{x}-{ids([b])[0]}.{y}" for a, x, b, y in PAIRS])
def test_every_port_pair_joins(A, pa, B, pb):
    """B joined to A floor to floor, through every port of each (the piece used forwards or backwards: a 180 deg
    turn about u), seen from both sides of the joint: lanes coincide within 0.5 mm, materials match, bundles meet
    head on, and the placed block lands on the grid."""
    a, b = PLANS[A], PLANS[B]
    for (X, px), (Y_, py) in (((a, pa), (b, pb)), ((b, pb), (a, pa))):
        T = P.place(Y_, py, X.ports[px])
        q = Y_.ports[py]
        assert np.allclose(T(q.o), X.ports[px].o) and np.allclose(T.dir(q.t), -np.asarray(X.ports[px].t))
        assert np.allclose(T.dir(q.u), X.ports[px].u)
        _assert_rigid_grid(T)
        assert joint_errors(X, px, Y_, py, T) == []


def test_joint_check_has_teeth():
    """An upside-down join, a shifted one and a wrong material are all caught."""
    a = PLANS["DC_Tray_StraightS_Full"]
    b = P.plan("StraightL", "Full")
    T = P.place(b, "a", a.ports["b"])
    assert joint_errors(a, "b", b, "a", T) == []
    o = np.asarray(a.ports["b"].o)
    flip = P.Transform(np.diag([1.0, -1.0, -1.0]), o - np.diag([1.0, -1.0, -1.0]) @ o)   # 180 deg about t
    assert joint_errors(a, "b", b, "a", flip @ T)
    assert joint_errors(a, "b", b, "a", P.Transform(np.eye(3), np.array([0, 0.001, 0])) @ T)
    b.bundle("F3+").material = "PaintedMetalGrey"
    assert any("meets" in e for e in joint_errors(a, "b", b, "a", T))


@pytest.mark.parametrize("lo,hi", list(itertools.combinations(TL.DENSITIES, 2)))
def test_mixed_density_joint(lo, hi):
    """Two densities joined without a reducer line up on every lane they share; only the extra lanes end there."""
    A, B = P.plan("StraightS", hi), P.plan("StraightL", lo)
    T = P.place(B, "a", A.ports["b"])
    ea = {r: p for p, _, _, r, _ in port_ends(A, "b")}
    eb = {r: T(p) for p, _, _, r, _ in port_ends(B, "a")}
    # port b's lane names are mirrored on the neighbour's port a (opposite across axes)
    assert set(TL.mirror(r) for r in eb) <= set(ea)
    for r, q in eb.items():
        assert np.linalg.norm(ea[TL.mirror(r)] - q) <= TL.POS_TOL
    assert {r for r in ea if TL.mirror(r) not in eb} == {l.name for l in TL.lanes(hi)} - {l.name for l in
                                                                                          TL.lanes(lo)}


def test_reducer_chain():
    """Full -> Moderate -> Low -> Empty end to end: no PORT end left unmatched at any joint, every dropped lane
    ends in a BOOT, and the chain ends empty."""
    chain = [P.plan("Reducer", d) for d in ("Full", "Moderate", "Low")]
    T = P.Transform.identity()
    placed = [chain[0]]
    for nxt in chain[1:]:
        Tn = P.place(nxt, "a", placed[-1].ports["b"])
        _assert_rigid_grid(Tn)
        moved = nxt.transformed(Tn)
        assert joint_errors(placed[-1], "b", moved, "a", P.Transform.identity()) == []
        placed.append(moved)
    for pl in placed:
        a, b = pl.ports["a"].density, pl.ports["b"].density
        dropped = {l.name for l in TL.lanes(a)} - {l.name for l in TL.lanes(b)}
        boots = {bd.lane for bd in pl.bundles if bd.ends[1].kind == "BOOT"}
        assert boots == dropped and len(dropped) > 0
        assert all(bd.ends[0].kind == "PORT" for bd in pl.bundles)
    assert port_ends(placed[-1], "b") == [] and placed[-1].ports["b"].density == "Empty"
    total = sum(len(TL.lanes(d)) - len(TL.lanes(TL.step_down(d))) for d in ("Full", "Moderate", "Low"))
    assert total == sum(1 for pl in placed for bd in pl.bundles if bd.ends[1].kind == "BOOT") == 9


@pytest.mark.parametrize("d", TL.DENSITIES[1:])
def test_reducer_tags_and_boots(d):
    pl = P.plan("Reducer", d)
    tags = [f for f in pl.fittings if f.kind == "tag"]
    assert len(tags) == 2 and {t.params["text"] for t in tags} == {P.TAG_TEXT[d]}
    assert sorted(np.sign(t.frame.o[1] - P.Y_C) for t in tags) == [-1, 1]
    for t in tags:   # clipped to the outside of the wall wires, between the floor and the top wire
        assert abs(t.frame.o[1] - P.Y_C) - t.size[1] / 2 > TL.WALL_S + TL.WIRE_R
        assert FLOOR_Z < t.frame.o[2] - t.size[2] / 2 and t.frame.o[2] + t.size[2] / 2 < FLOOR_Z + TL.WALL_H
    for f in pl.fittings:
        if f.kind == "boot":
            assert f.params["radius"] > R_B and f.params["material"] == "Rubber"


# ---------------------------------------------------------------------------------------------------- racks
def _drop_to_rack(rack_h):
    """Drop box-corner -> the full rack's centred frame: bottom plane on the rack top, tray centreline at
    TRAY_RACK_Y, along-centre on the rack centre."""
    return P.Transform(np.eye(3), np.array([-0.5, DM.TRAY_RACK_Y - P.Y_C, rack_h / 2]))


def _rack_points(z):
    return [np.array([k * DM.WF_X, DM.WF_Y, z]) for k in (-1, 1)]


def _match_sets(got, want, tol=TL.POS_TOL):
    assert len(got) == len(want)
    for g in got:
        assert min(np.linalg.norm(g - w) for w in want) <= tol, g


@pytest.mark.parametrize("d", TL.DENSITIES[1:])
def test_drop_entries_match_rack(d):
    pl = P.plan("Drop", d)
    rack_h = 0.25 * catalog.BY_NAME["DC_Rack42_Open"].cells[1]
    T = _drop_to_rack(rack_h)
    rack_corner = -0.125 * np.array([4, 5, 10])        # the rack's box corner in its centred frame
    _assert_rigid_grid(P.Transform(np.eye(3), T.d - rack_corner))
    ends = [T(b.end_point(1)) for b in pl.bundles if b.ends[1].kind == "ENTRY"]
    assert len(ends) == 2
    _match_sets(ends, _rack_points(rack_h / 2))
    # the tray hangs TRAY_HANG over the rack, and the Drop stays inside the rack's footprint
    assert T(pl.ports["a"].o)[2] - FLOOR_Z - rack_h / 2 == pytest.approx(DM.TRAY_HANG)
    lo, hi = T(np.zeros(3)), T(pl.size)
    assert lo[0] >= -0.5 and hi[0] <= 0.5 and lo[1] >= -0.625 and hi[1] <= 0.625
    # the entry rectangles are the rack's brush-plate openings
    for e in pl.entries:
        c = T(e.o)
        assert abs(abs(c[0]) - DM.WF_X) < 1e-9 and e.ha == pytest.approx((DM.TOP_ENTRY[0][1] - DM.TOP_ENTRY[0][0]) / 2)
        assert c[1] == pytest.approx(sum(DM.TOP_ENTRY[1]) / 2) and e.hb == pytest.approx(
            (DM.TOP_ENTRY[1][1] - DM.TOP_ENTRY[1][0]) / 2)
    # rack and Drop both turned 180 deg about z: the same landing (the pair is symmetric)
    R = P.Transform.rotation_z(180)
    _match_sets([R(p) for p in ends], [R(p) for p in _rack_points(rack_h / 2)])


def test_chute_continues_drop():
    drop, chute = P.plan("Drop", "Low"), P.plan("Chute")
    T = P.Transform(np.eye(3), np.array([0.0, 2 * CELL, -chute.size[2]]))   # under the Drop's waterfall column
    _assert_rigid_grid(T)
    d_ends = [b.end_point(1) for b in drop.bundles if b.ends[1].kind == "ENTRY"]
    c_top = [T(b.end_point(0)) for b in chute.bundles]
    c_bot = [T(b.end_point(1)) for b in chute.bundles]
    _match_sets(c_top, d_ends)
    for b in chute.bundles:   # plumb all the way, entering at the top and leaving at the bottom
        assert np.allclose(b.points[:, :2], b.points[0, :2]) and b.end_dir(0) @ P.Z > COS_TOL
        assert b.end_dir(1) @ -P.Z > COS_TOL
    # the chute's top rectangles are the Drop's bottom ones
    for e in chute.entries:
        if e.name.startswith("top"):
            twin = next(f for f in drop.entries if f.name[-1] == e.name[-1])
            assert np.allclose(T(e.o), twin.o) and (e.ha, e.hb) == pytest.approx((twin.ha, twin.hb))
    # Drop over a full rack, Chute down to a half rack beside it: 1.25 m lower, on the half rack's openings
    full_h = 0.25 * catalog.BY_NAME["DC_Rack42_Open"].cells[1]
    half_h = 0.25 * catalog.BY_NAME["DC_Rack24_Open"].cells[1]
    assert full_h - half_h == pytest.approx(chute.size[2]) == pytest.approx(1.25)
    to_world = P.Transform(np.eye(3), np.array([-0.5, DM.TRAY_RACK_Y - P.Y_C, full_h]))   # racks on z = 0
    _match_sets([to_world(p) for p in c_bot], [np.array([k * DM.WF_X, DM.WF_Y, half_h]) for k in (-1, 1)])
    for b in chute.bundles:
        e = next(en for en in chute.entries if en.name == b.ends[1].ref)
        inside, _ = e.margin(b.end_point(1))
        assert inside >= R_WF + 0.003


@pytest.mark.build
@pytest.mark.parametrize("rack,piece", [("DC_Rack42_Open", "Drop"), ("DC_Rack24_Open", "Chute")])
def test_waterfalls_land_in_measured_entries(rack, piece):
    """Against the BUILT racks: the waterfalls land inside the measured brush-plate openings (build_report.json
    geometry.top_entries, Task 1) with R_WF + 3 mm to spare."""
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        geo = json.load(f)["blocks"][rack]["geometry"]
    pl = P.plan(piece, "Low") if piece == "Drop" else P.plan(piece)
    shift = np.array([-0.5, DM.TRAY_RACK_Y - P.Y_C + (0 if piece == "Drop" else 2 * CELL), 0.0])
    lands = [b.end_point(1) + shift for b in pl.bundles if b.ends[1].kind == "ENTRY"]
    for x0, x1, y0, y1, _ in geo["top_entries"]:
        hit = [p for p in lands if x0 < p[0] < x1]
        assert len(hit) == 1
        p = hit[0]
        assert min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1]) >= R_WF + 0.003


# ---------------------------------------------------------------------------------------------------- the Drop
@pytest.mark.parametrize("d", TL.DENSITIES[1:])
def test_drop_waterfalls(d):
    pl = P.plan("Drop", d)
    wfs = [b for b in pl.bundles if b.lane.startswith("WF")]
    assert sorted(b.lane for b in wfs) == ["WF+", "WF-"]
    zf = pl.ports["a"].o[2]
    for b in wfs:
        assert b.ends[0] == P.End("SPLIT", "L1+")
        p0 = b.end_point(0)
        xw = b.end_point(1)[0]
        assert abs(p0[0] - xw) == pytest.approx(P.WF_SPLIT_DX) and abs(p0[0] - 0.5) < abs(xw - 0.5)
        # the crest: highest point >= 0.13 over the floor, over the guide centre at s = WF_Y - TRAY_RACK_Y - 0.10
        top = b.points[b.points[:, 2] >= b.points[:, 2].max() - 1e-9][-1]   # the crest: where the guide arc begins
        assert top[2] - zf >= 0.13
        assert top[1] - P.Y_C == pytest.approx(DM.WF_Y - DM.TRAY_RACK_Y - 0.10, abs=1e-3)
        g = next(f for f in pl.fittings if f.kind == "waterfall_guide" and abs(f.frame.o[0] - xw) < 1e-9)
        c = g.params["centre"]
        assert c[1] - P.Y_C == pytest.approx(DM.WF_Y - DM.TRAY_RACK_Y - 0.10)
        on_arc = [q for q in b.points if q[1] >= c[1] - 1e-9 and q[2] >= c[2] - 1e-9 and abs(q[0] - xw) < 1e-9]
        r = [np.linalg.norm(q[1:] - c[1:]) for q in on_arc]
        assert len(on_arc) >= 8 and np.allclose(r, P.WF_GUIDE_R, atol=1e-9), "bundle-centre arc radius 0.10"
        # the bundle's underside clears the top (safety-edge) wire where it crosses the wall
        over = [q for q in b.points if abs(q[1] - P.Y_C - TL.WALL_S) < 0.01]
        assert min(q[2] for q in over) - R_WF - zf > TL.WALL_H + TL.EDGE_WIRE_R
        # the guide plate sits on the wall, clear of its top wire, and under the bundle
        r_in = g.params["r_top"] - g.params["thickness"]
        wire = np.array([TL.WALL_S + P.Y_C, zf + TL.WALL_H])
        assert np.linalg.norm(wire - c[1:]) < r_in - TL.EDGE_WIRE_R
        assert g.params["r_top"] == pytest.approx(P.WF_GUIDE_R - R_WF)


def test_drop_dressing_only_at_full():
    """Only at Full, and only over the middle of the Drop, are F1+ / F3+ dressed apart for the climb; every lane is
    on its port lane for the first and last 7 cm."""
    for d in TL.DENSITIES[1:]:
        pl = P.plan("Drop", d)
        for b in pl.bundles:
            if b.lane.startswith("WF"):
                continue
            lane = TL.LANE[b.lane]
            want = np.array([P.Y_C + lane.s, pl.ports["a"].o[2] + lane.h])
            dev = np.linalg.norm(b.points[:, 1:] - want, axis=1)
            x = b.points[:, 0]
            assert dev[(x <= P.DRESS_X[0]) | (x >= 1.0 - P.DRESS_X[0])].max() < 1e-9
            assert (dev.max() > 1e-3) == (b.lane in P.DRESS), (d, b.lane)


# ---------------------------------------------------------------------------------------------------- hardware
STRAIGHTS = [n for n in PORTED if catalog.BY_NAME[n].variant in ("StraightS", "StraightL", "Reducer", "Drop")]


@pytest.mark.parametrize("name", STRAIGHTS, ids=ids(STRAIGHTS))
def test_straps_phase(name):
    """Straps at 0.125 + k 0.25 from port a, and the same set from port b: the rhythm carries across joints."""
    pl = PLANS[name]
    L = pl.size[0]
    want = [0.125 + 0.25 * k for k in range(int(round(L / 0.25)))]
    assert sorted(round(L - x, 9) for x in want) == pytest.approx(want)     # the same set from port b
    run = [f for f in pl.fittings if f.kind == "strap" and not f.params["bundle"].startswith("WF")]
    st = {round(f.frame.o[0], 9) for f in run}
    assert st <= {round(x, 9) for x in want}
    for b in pl.bundles:
        mine = [f for f in pl.fittings if f.kind == "strap" and f.params["bundle"] == b.lane]
        if all(e.kind == "PORT" for e in b.ends):     # through bundles: every station
            assert sorted(f.frame.o[0] for f in mine) == pytest.approx(want), b.lane
        elif b.ends[1].kind == "BOOT":                  # dropped lanes: every station before the boot
            assert sorted(f.frame.o[0] for f in mine) == pytest.approx([x for x in want if x < P.BOOT_X - 0.03])
        else:     # waterfalls (Task 8): tied on the fall at 0.125 + k 0.25 over the bottom plane (the Chute's rung
            #       rhythm carries on up), horizontal bands, never on the run's rhythm
            assert sorted(f.frame.o[2] for f in mine) == pytest.approx(list(P.WF_STRAPS)), b.lane
            assert all(abs(f.frame.t[2]) == 1.0 for f in mine)
            assert P.WF_STRAPS == tuple(TL.STRAP_PHASE + k * TL.STRAP_PITCH for k in range(len(P.WF_STRAPS)))
        for f in mine:
            assert seg_dist(f.frame.o[None], b.points[:-1], b.points[1:]).min() < 1e-9
            assert f.size[1] == pytest.approx(2 * (b.radius + TL.STRAP_T))


def test_strap_rhythm_across_a_run():
    """StraightS, StraightL, Drop, Reducer chained: the straps of one through lane are evenly 0.25 m apart over the
    whole run (joints included)."""
    run = [P.plan("StraightS", "Full"), P.plan("StraightL", "Full"), P.plan("Drop", "Full"), P.plan("Reducer", "Full")]
    placed = [run[0]]
    for nxt in run[1:]:
        placed.append(nxt.transformed(P.place(nxt, "a", placed[-1].ports["b"])))
    xs = sorted(f.frame.o[0] for pl in placed for f in pl.fittings
                if f.kind == "strap" and f.params["bundle"] in ("M0",))
    assert np.allclose(np.diff(xs), 0.25) and xs[0] == pytest.approx(0.125)


@pytest.mark.parametrize("name", STRAIGHTS, ids=ids(STRAIGHTS))
def test_trapeze_on_grid(name):
    pl = PLANS[name]
    traps = [s for s in pl.supports if s.kind == "trapeze"]
    assert len(traps) == 1
    t = traps[0]
    assert t.position[0] == pytest.approx(pl.size[0] / 2) and on_grid(t.position[0])
    assert np.allclose(t.axis, P.Y)
    zc = pl.ports["a"].o[2] - FLOOR_Z
    assert t.position[2] - t.params["strut"][1] / 2 == pytest.approx(zc + P.STRUT_LIFT)
    assert t.position[2] + t.params["strut"][1] / 2 == pytest.approx(zc + P.BASKET_BOTTOM)   # it carries the basket
    ys = sorted(a[1] for a, _ in t.rods)
    assert ys == pytest.approx([P.Y_C - DM.ROD_S, P.Y_C + DM.ROD_S])
    for a, b in t.rods:
        assert a[0] == b[0] == pytest.approx(t.position[0]) and a[1] == b[1]
        assert b[2] == pytest.approx(pl.size[2] - P.END_INSET)        # up to the coupler plate under the top plane
        clear = abs(a[1] - P.Y_C) - TL.ROD_R - (TL.WALL_S + TL.EDGE_WIRE_R)
        assert clear >= TL.ROD_CLEAR, f"rods clear the wall wires by {clear * 1000:.1f} mm"
    lo, hi = (t.position[1] + e for e in t.extent)
    assert lo == pytest.approx(P.END_INSET) and hi == pytest.approx(2 * CELL - P.END_INSET)


@pytest.mark.parametrize("rods", ["DC_TrayRods_025", "DC_TrayRods_100", "DC_TrayRods_200"])
@pytest.mark.parametrize("piece", ["DC_Tray_StraightS_Full", "DC_Tray_StraightL_Empty", "DC_Tray_Drop_Low",
                                   "DC_Tray_Reducer_Moderate"])
def test_rods_continue_trapeze(rods, piece):
    """A rod hanger stood on a tray's top plane over its trapeze continues both rods coaxially."""
    tr, rd = PLANS[piece], PLANS[rods]
    t = next(s for s in tr.supports if s.kind == "trapeze")
    r = rd.supports[0]
    assert r.kind == "rods" and len(rd.supports) == 1 and not rd.bundles and not rd.ports
    shift = np.array([t.position[0] - rd.size[0] / 2, 0.0, tr.size[2]])
    _assert_rigid_grid(P.Transform(np.eye(3), shift))
    for (a, b), (c, d) in zip(sorted(t.rods, key=lambda q: q[0][1]), sorted(r.rods, key=lambda q: q[0][1])):
        assert np.allclose((c + shift)[:2], b[:2]) and np.allclose((d + shift)[:2], b[:2])
        assert (c + shift)[2] - b[2] == pytest.approx(2 * P.END_INSET)
        assert d[2] == pytest.approx(rd.size[2] - P.END_INSET)
    assert rd.size[2] == pytest.approx(0.25 * catalog.BY_NAME[rods].cells[1])


def test_chute_ladders():
    pl = P.plan("Chute")
    lad = [s for s in pl.supports if s.kind == "ladder"]
    assert len(lad) == 2
    for s, b in zip(lad, pl.bundles):
        rails, rungs = s.ladder()
        zs = [r[2] for r in rungs]
        assert zs == pytest.approx([0.125 + 0.25 * k for k in range(5)])
        xw = b.points[0][0]
        assert sorted(a[0] for a, _ in rails) == pytest.approx([xw - P.CHUTE_RAIL_DX, xw + P.CHUTE_RAIL_DX])
        foot, fsize = s.ladder_plate("foot_plate")
        top_fr, tsize = s.ladder_plate("top_plate")
        for a, top in rails:   # rails stand the full height between the foot plate (seated on the half rack) and
            #                    the top clamp plate (under the Drop)
            assert a[2] == pytest.approx(foot.o[2] + fsize[0] / 2) and top[2] == pytest.approx(top_fr.o[2] - tsize[0] / 2)
        # (Task 10) both plates sit ON the Chute's ENTRY planes: the foot on the half rack's roof (its brush frame is
        # ENTRY_DROP under it), the top plate under the Drop's collar, which sits on the same plane (flush contact)
        assert P.ENTRY_SEAT == 0.0
        assert foot.o[2] - fsize[0] / 2 == pytest.approx(P.ENTRY_SEAT)
        assert top_fr.o[2] + tsize[0] / 2 == pytest.approx(pl.size[2] - P.ENTRY_SEAT)
        # the top plate spans both rails; the foot plate covers the half rack's brush-plate frame (opening + flange)
        # with 3 mm to spare, its bore round the bundle
        assert top_fr.o[0] - tsize[1] / 2 <= xw - P.CHUTE_RAIL_DX - s.params["rail"][0] / 2 + 1e-9
        assert top_fr.o[0] + tsize[1] / 2 >= xw + P.CHUTE_RAIL_DX + s.params["rail"][0] / 2 - 1e-9
        (ex0, ex1), (ey0, ey1) = DM.HALF_TOP_ENTRY
        rack_x = abs(np.array([foot.o[0] - fsize[1] / 2, foot.o[0] + fsize[1] / 2]) - 0.5)   # Chute -> rack frame
        assert min(rack_x) <= ex0 - DM.ENTRY_FLANGE - 0.003 + 1e-9 and max(rack_x) >= ex1 + DM.ENTRY_FLANGE + 0.003 - 1e-9
        ry = np.array([foot.o[1] - fsize[2] / 2, foot.o[1] + fsize[2] / 2]) + DM.WF_Y - b.points[0][1]
        assert ry[0] <= ey0 - DM.ENTRY_FLANGE - 0.003 + 1e-9 and ry[1] >= ey1 + DM.ENTRY_FLANGE + 0.003 - 1e-9
        assert R_WF < s.params["foot_hole"] and R_WF < s.params["top_hole"] < R_WF + 0.003
        assert P.CHUTE_RAIL_DX - s.params["rail"][0] / 2 > R_WF + 0.01        # rails clear of the bundle
        assert s.position[1] + s.params["rung"][1] / 2 < b.points[0][1] - R_WF   # rungs behind it
        straps = [f for f in pl.fittings if f.kind == "strap" and f.params["bundle"] == b.lane]
        assert sorted(f.frame.o[2] for f in straps) == pytest.approx(zs)


def test_transformed_moves_everything():
    """PiecePlan.transformed moves every point, direction and frame-bound param (no stale absolute coordinates)."""
    T = P.Transform.rotation_z(90, about=(0.3, 0.2, 0.0)) @ P.Transform(np.eye(3), np.array([1.0, -2.0, 0.5]))
    for name in ("DC_Tray_Drop_Full", "DC_Tray_Chute", "DC_Tray_Reducer_Full"):
        a, b = PLANS[name], PLANS[name].transformed(T)
        for ba, bb in zip(a.bundles, b.bundles):
            assert np.allclose(T(ba.points), bb.points)
        for sa, sb in zip(a.supports, b.supports):
            assert all(np.allclose(T(p), q) for ra, rb in zip(sa.rods, sb.rods) for p, q in zip(ra, rb))
            if sa.kind == "ladder":
                (ra, ga), (rb, gb) = sa.ladder(), sb.ladder()
                assert all(np.allclose(T(p), q) for x, y in zip(ra, rb) for p, q in zip(x, y))
                assert np.allclose(T(np.array(ga)), np.array(gb))
        for ea, eb in zip(a.entries, b.entries):
            assert np.allclose(T(ea.o), eb.o) and np.allclose(T.dir(ea.n), eb.n)
        for fa, fb in zip(a.fittings, b.fittings):
            assert np.allclose(T(P.fitting_points(fa)), P.fitting_points(fb), atol=1e-9)


# ---------------------------------------------------------------------------------------------------- occupancy
def test_occupied_cells():
    def box(nx, ny, nz):
        return {(i, j, k) for i in range(nx) for j in range(ny) for k in range(nz)}
    for n in PLANS:
        spec = catalog.BY_NAME[n]
        occ = P.occupied_cells(PLANS[n])
        if spec.variant in ("StraightS", "StraightL", "Reducer", "Rods", "TurnH", "TurnDown"):
            assert occ == box(spec.cells[0], spec.cells[2], spec.cells[1]), n
        elif spec.variant == "Tee":        # Task 7: the two cells beside the branch stay free
            assert occ == box(4, 3, 1) - {(0, 2, 0), (3, 2, 0)}, n
        elif spec.variant == "Cross":      # ... and the X's four corners
            assert occ == box(4, 4, 1) - {(0, 0, 0), (0, 3, 0), (3, 0, 0), (3, 3, 0)}, n
        elif spec.variant == "TurnUp":     # the two cells inside the concave curve stay empty
            assert occ == box(2, 2, 2) - {(0, 0, 1), (0, 1, 1)}, n
        elif spec.variant == "Drop":
            column = {(i, 2, k) for i in (0, 3) for k in range(3)}
            assert occ == box(4, 2, 3) - box(4, 2, 2) | column, n
        else:
            assert occ == {(i, 0, k) for i in (0, 3) for k in range(5)}, n


def test_to_block_centres():
    pl = PLANS["DC_Tray_Drop_Full"]
    assert np.allclose(pl.to_block(np.zeros(3)), -pl.size / 2) and np.allclose(pl.to_block(pl.size), pl.size / 2)
    assert np.allclose(pl.size, (1.0, 0.75, 0.75))


def test_plan_entry_points():
    assert P.LATER == () and set(P.BENDS) | {"StraightS", "StraightL", "Drop", "Reducer", "Chute", "Rods"} == \
        set(P.SHAPES)
    for s in P.BENDS:     # every shape is planned, from a spec or by name, the same
        a, b = P.plan(s, "Low"), P.plan(catalog.BY_NAME[f"DC_Tray_{s}_Low"])
        assert a.shape == s and [x.points.tolist() for x in a.bundles] == [x.points.tolist() for x in b.bundles]
    with pytest.raises(ValueError):
        P.plan("Drop", "Empty")
    with pytest.raises(ValueError):
        P.plan("Reducer", "Empty")
    with pytest.raises(NotImplementedError):
        P.plan("StraightS", "Full", style="ladder")
    with pytest.raises(ValueError):
        P.plan(catalog.BY_NAME["DC_Rack42_Open"])
    a, b = P.plan("StraightS", "Moderate"), P.plan(catalog.BY_NAME["DC_Tray_StraightS_Moderate"])
    assert [x.points.tolist() for x in a.bundles] == [x.points.tolist() for x in b.bundles]
    assert {f.kind for pl in PLANS.values() for f in pl.fittings} <= set(P.FITTING_KINDS)
    assert {s.kind for pl in PLANS.values() for s in pl.supports} <= set(P.SUPPORT_KINDS)


# ---------------------------------------------------------------------------------------------------- bends (Task 3)
from dc import tray_bends as TB  # noqa: E402

BEND_SHAPES = ("TurnH", "TurnUp", "TurnDown")
JUNCTIONS = ("Tee", "Cross")
# per bend: the plane's two axes, the piece table's port-to-port centre, and the lane radius as R +- s / h
BEND_GEOM = {"TurnH": ((0, 1), (0.0, 0.75), lambda l: TB.TURN_R["TurnH"] - l.s),
             "TurnUp": ((0, 2), (0.0, 0.5), lambda l: TB.TURN_R["TurnUp"] - l.h),
             "TurnDown": ((0, 2), (0.0, 0.0), lambda l: TB.TURN_R["TurnDown"] + l.h)}


def arc_points(pl, b):
    """A bend bundle's points on its arc (between the two 5 cm leads), in the bend plane, and the arc centre."""
    (i, j), _, _ = BEND_GEOM[pl.shape]
    c = TB.bend_centre(pl.shape)
    q = b.points[:, [i, j]] - c[[i, j]]
    sw = TB.bend_sweep(pl.shape)
    a0, a1 = (sw.frame(l)[0][[i, j]] - c[[i, j]] for l in (TB.LEAD, sw.length - TB.LEAD))   # the tangent points
    ang = np.arctan2(q[:, 1], q[:, 0])
    span = sorted((math.atan2(a0[1], a0[0]), math.atan2(a1[1], a1[0])))
    inside = (ang >= span[0] - 1e-9) & (ang <= span[1] + 1e-9)
    return q[inside], q


@pytest.mark.parametrize("d", TL.DENSITIES)
@pytest.mark.parametrize("shape", BEND_SHAPES)
def test_bend_radii(shape, d):
    """Every lane is an offset curve of the centreline: on the arc its radius is R - s (TurnH, left-hand), R - h
    (TurnUp) or R + h (TurnDown), about one centre, and no lane bends tighter than 0.25 m. R is the piece table's
    radius less the 5 cm leads, so the ports stay on the grid: the centre sits 5 cm in from the table's, and each
    lane is straight for exactly its last 5 cm."""
    pl = P.plan(shape, d)
    (i, j), tc, rad = BEND_GEOM[shape]
    c = TB.bend_centre(shape)
    inward = np.sign(np.array([0.25, 0.25]) - np.array(tc))     # the table centre is a box corner: 5 cm inwards
    assert np.allclose(c[[i, j]], np.array(tc) + TB.LEAD * np.where(inward == 0, 1, inward))
    assert TB.TURN_R == {"TurnH": 0.45, "TurnUp": 0.405, "TurnDown": 0.245}
    for b in pl.bundles:
        lane = TL.LANE[b.lane]
        on, q = arc_points(pl, b)
        r = np.linalg.norm(on, axis=1)
        assert len(on) >= 20 and np.allclose(r, rad(lane), atol=1e-9), (b.lane, r.min(), r.max(), rad(lane))
        assert rad(lane) >= TB.MIN_LANE_R
        assert np.all(np.linalg.norm(q, axis=1) >= rad(lane) - 1e-9)     # the leads lie outside the arc's circle
    if d == "Full":
        all_r = [rad(l) for l in TL.lanes("Full")]
        want = {"TurnH": 0.45 - 0.17, "TurnUp": 0.405 - 0.06, "TurnDown": 0.245 + 0.027}[shape]
        assert min(all_r) == pytest.approx(want) and min(all_r) >= 0.25


def test_bend_lane_order_kept():
    """Bundles keep their lane order and spacing through every bend: the across / up offsets of each lane from the
    centreline are constant along it."""
    for shape in BEND_SHAPES:
        sw = TB.bend_sweep(shape)
        pl = P.plan(shape, "Full")
        ls = sw.stations()
        for b in pl.bundles:
            lane = TL.LANE[b.lane]
            for l, p in zip(ls, b.points):
                q, t, s, u = sw.frame(l)
                assert (p - q) @ s == pytest.approx(lane.s, abs=1e-9) and (p - q) @ u == pytest.approx(lane.h, abs=1e-9)
                assert abs((p - q) @ t) < 1e-9


@pytest.mark.parametrize("shape", BEND_SHAPES)
def test_strap_radials(shape):
    """On bends the straps sit on radial lines: at one station the straps of all lanes share a radial line (angle
    within 0.1 deg) through the arc centre, 0.125 m of centreline from each port, evenly spaced at the pitch nearest
    0.25 m; every lane has one strap per station."""
    for d in TL.DENSITIES[1:]:
        pl = P.plan(shape, d)
        (i, j), _, _ = BEND_GEOM[shape]
        c = TB.bend_centre(shape)
        straps = [f for f in pl.fittings if f.kind == "strap"]
        L = TB.bend_sweep(shape).length
        st = sorted({round(f.params["station"], 9) for f in straps})
        assert st == pytest.approx(TB.radial_stations(L))
        assert st[0] == pytest.approx(0.125) and L - st[-1] == pytest.approx(0.125)
        pitch = np.diff(st)
        assert np.allclose(pitch, pitch[0]) and abs(pitch[0] - 0.25) <= 0.25 / 2 / max(1, len(pitch))
        for x in st:
            here = [f for f in straps if abs(f.params["station"] - x) < 1e-9]
            assert sorted(f.params["bundle"] for f in here) == sorted(b.lane for b in pl.bundles)
            ang = [math.degrees(math.atan2(*(f.frame.o[[j, i]] - c[[j, i]]))) for f in here]
            assert max(ang) - min(ang) < 0.1, (shape, d, x, ang)
            for f in here:      # square to its bundle, round it (on the true arc: within the polyline's chord sag)
                b = pl.bundle(f.params["bundle"])
                assert seg_dist(f.frame.o[None], b.points[:-1], b.points[1:]).min() < 1e-4
                k = np.argmin(np.linalg.norm(b.points - f.frame.o, axis=1))
                tb = b.points[min(k + 1, len(b.points) - 1)] - b.points[max(k - 1, 0)]
                assert abs(f.frame.t @ tb / np.linalg.norm(tb)) > math.cos(math.radians(2))


def _place_chain(steps):
    """[(plan, in port, previous index, previous out port)] -> [(placed plan, transform)], every joint checked."""
    out = []
    for pl, pin, k, pout in steps:
        if k is None:
            T = P.Transform.identity()
        else:
            prev = out[k][0]
            T = P.place(pl, pin, prev.ports[pout])
            _assert_rigid_grid(T)
            moved = pl.transformed(T)
            assert joint_errors(prev, pout, moved, pin, P.Transform.identity()) == [], (pl.shape, pin)
        out.append((pl.transformed(T), T))
    return out


@pytest.mark.parametrize("d", TL.DENSITIES)
def test_jog_closes_on_grid(d):
    """TurnUp, two vertical StraightS, TurnDown (placed by its a port: turned 180 deg about z from its table pose),
    StraightS: every block's box corner lands on the grid, every joint passes the lane check, and the run leaves
    level, heading on, 0.25 k higher."""
    s = lambda: P.plan("StraightS", d)
    chain = _place_chain([(P.plan("TurnUp", d), "a", None, None), (s(), "a", 0, "b"), (s(), "a", 1, "b"),
                          (P.plan("TurnDown", d), "a", 2, "b"), (s(), "a", 3, "b")])
    for _, T in chain:
        assert all(abs(v / CELL - round(v / CELL)) < 1e-6 for v in T.d), T.d
    first, last = chain[0][0].ports["a"], chain[-1][0].ports["b"]
    assert np.allclose(last.t, (1, 0, 0)) and np.allclose(last.u, first.u)
    rise = last.o[2] - first.o[2]
    assert rise > 0 and on_grid(rise) and last.o[1] == pytest.approx(first.o[1])
    R = chain[3][1].R          # the TurnDown's pose: its table pose turned about z by 180 deg, then stood up
    assert np.allclose(R @ np.array([0, 0, -1.0]), [1, 0, 0])


def test_loop_closes():
    """TurnH x 4 and StraightL x 4 make a closed horizontal loop: the last port meets the first within 0.5 mm."""
    steps, k = [], None
    for i in range(4):
        steps.append((P.plan("TurnH", "Full"), "a", k, "b"))
        k = len(steps) - 1
        steps.append((P.plan("StraightL", "Full"), "a", k, "b"))
        k = len(steps) - 1
    chain = _place_chain(steps)
    a, b = chain[0][0].ports["a"], chain[-1][0].ports["b"]
    assert np.linalg.norm(np.asarray(a.o) - np.asarray(b.o)) <= TL.POS_TOL
    assert np.allclose(a.t, -np.asarray(b.t)) and np.allclose(a.u, b.u)
    assert joint_errors(chain[0][0], "a", chain[-1][0], "b", P.Transform.identity()) == []


@pytest.mark.parametrize("hand", ["U", "S"])
@pytest.mark.parametrize("W", [1.0, 1.5, 2.0])
def test_aisle_crossing(W, hand):
    """Two parallel runs W + 1.0 apart (an aisle of width W between two rack rows) close with TurnH + W of
    straights + TurnH: as a U (both left turns, the run comes back) or an S (the second TurnH used as a right turn,
    through its b port)."""
    parts = {1.0: ["StraightS", "StraightS"], 1.5: ["StraightL"], 2.0: ["StraightL", "StraightS"]}[W]
    steps = [(P.plan("StraightS", "Moderate"), "a", None, None), (P.plan("TurnH", "Moderate"), "a", 0, "b")]
    for name in parts:
        steps.append((P.plan(name, "Moderate"), "a", len(steps) - 1, "b"))
    last_in, last_out = ("a", "b") if hand == "U" else ("b", "a")
    steps.append((P.plan("TurnH", "Moderate"), last_in, len(steps) - 1, "b"))
    chain = _place_chain(steps)
    start, end = chain[0][0].ports["a"], chain[-1][0].ports[last_out]
    assert (np.asarray(end.o) - np.asarray(start.o))[1] == pytest.approx(W + 1.0)
    assert np.allclose(end.t, (-1, 0, 0) if hand == "U" else (1, 0, 0))
    assert sum(chain[i][0].size[0] for i in range(2, 2 + len(parts))) == pytest.approx(W)


# ---------------------------------------------------------------------------------------------------- junctions (Task 3)
def _plan_crosses(A, B):
    """Whether A's centreline crosses B's in plan (2D segment intersection)."""
    a0, a1 = A.points[:-1, :2], A.points[1:, :2]
    b0, b1 = B.points[:-1, :2], B.points[1:, :2]

    def orient(p, q, r):
        return np.sign((q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) *
                       (r[..., 0] - p[..., 0]))
    P0, P1, Q0, Q1 = a0[:, None], a1[:, None], b0[None], b1[None]
    hit = (orient(P0, P1, Q0) * orient(P0, P1, Q1) <= 0) & (orient(Q0, Q1, P0) * orient(Q0, Q1, P1) <= 0)
    return bool(hit.any())


def over_events(pl):
    """[(A, B, A's sample, its height over the floor top)] where A passes over B: their centrelines cross in plan
    and, at A's sample, A is higher than B and within 2 R_B of B's centreline horizontally (B's footprint). Lanes
    nesting in a stack (side by side, or in the grooves of the layer below) never cross, so they are not events."""
    zf = FLOOR_Z
    out = []
    for A, B in itertools.permutations(pl.bundles, 2):
        if A.ends[0] == P.End("SPLIT", B.lane) or B.ends[0] == P.End("SPLIT", A.lane):
            continue          # a child and its parent share their line at the split (test_no_bundle_interpenetration)
        if not _plan_crosses(A, B):
            continue
        pa = resample(A.points)
        flat = lambda q: q * np.array([1.0, 1.0, 0.0])
        a, b = flat(B.points[:-1]), flat(B.points[1:])
        dist = seg_dist(flat(pa), a, b)
        j = dist.argmin(axis=1)
        ab = b[j] - a[j]
        t = np.clip(((flat(pa) - a[j]) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0, 1)
        zb = B.points[:-1, 2][j] + t * (B.points[1:, 2][j] - B.points[:-1, 2][j])
        for p, dh, z in zip(pa, dist.min(axis=1), zb):
            if dh < 2 * R_B and p[2] > z + 1e-6:
                out.append((A, B, p, p[2] - zf))
    return out


def _saddles(pl):
    return [f for f in pl.fittings if f.kind == "crossover_saddle"]


def _over_saddle(pl, p):
    for f in _saddles(pl):
        d = p - f.frame.o
        if abs(d @ f.frame.t) <= f.size[0] / 2 and abs(d @ f.frame.s) <= f.size[1] / 2:
            return True
    return False


@pytest.mark.parametrize("d", TL.DENSITIES)
@pytest.mark.parametrize("shape", JUNCTIONS)
def test_junction_humps(shape, d):
    """Every bundle that passes over another's footprint is there >= DECK_H + R_B above the floor top (the bottom
    layer resting on the deck) and over a crossover saddle; every bundle stays inside the cell, its surface
    <= 0.25 - 0.045 - 0.0025 above the floor top. The Cross's c-d stack crosses every a-b lane; nothing crosses in
    the Tee (its branch-side lanes turn, they don't cross: see tray_bends)."""
    pl = P.plan(shape, d)
    ev = over_events(pl)
    for A, B, p, h in ev:
        assert h >= TL.DECK_H + R_B - 1e-9, f"{A.lane} over {B.lane} only {h:.4f} up"
        assert _over_saddle(pl, p), f"{A.lane} over {B.lane} at {p} but no saddle under it"
    pairs = {(A.lane, B.lane) for A, B, *_ in ev}
    if shape == "Cross":
        n = len(TL.lanes(d))
        assert pairs == {(f"{x.name}/d", y.name) for x in TL.lanes(d) for y in TL.lanes(d)} and len(pairs) == n * n
        assert all(A.lane.endswith("/d") for A, *_ in ev)
    else:
        assert ev == []
    top = TL.CELL - FLOOR_Z - TL.CELL_TOP_CLEAR
    for b in pl.bundles:
        assert (b.points[:, 2] + b.radius - FLOOR_Z).max() <= top + 1e-9, b.lane


@pytest.mark.parametrize("d", TL.DENSITIES[1:])
def test_cross_ramp_and_saddle(d):
    """The c-d stack climbs and descends at <= 30 deg, level for the last 5 cm at each port, and rides the deck
    exactly (the bottom layer rests on it). The saddle: deck at DECK_H, Brushed legs bolted through the floor, clear
    of every bundle (test_fittings_clear_bundles) and inside the fillets; a floor strut under it."""
    pl = P.plan("Cross", d)
    (sd,) = _saddles(pl)
    assert sd.params["deck_h"] == TL.DECK_H == 0.095 and sd.params["leg_material"] == "BrushedMetal"
    assert set(sd.params["carries"]) == {b.lane for b in pl.bundles if b.lane.endswith("/d")}
    parts = P.saddle_parts(sd)
    deck = parts[0]
    assert deck[0] == "deck" and (deck[1].o + deck[2][2] / 2 * deck[1].u)[2] - FLOOR_Z == pytest.approx(TL.DECK_H)
    legs = [q for q in parts if q[0] == "leg"]
    assert len(legs) == 4
    for _, fr, size in legs:     # standing through the floor (to the basket's underside), up to the deck
        assert fr.o[2] - size[2] / 2 == pytest.approx(P.BASKET_BOTTOM)
        for cx in (TB.FIL_X, 1 - TB.FIL_X):        # inside the floor: outside every fillet's circle
            for cy in (TB.FIL_X, 1 - TB.FIL_X):
                assert np.linalg.norm(fr.o[:2] - (cx, cy)) - size[0] / math.sqrt(2) > TL.FILLET_R + TL.WIRE_R
    for b in pl.bundles:
        if not b.lane.endswith("/d"):
            assert np.allclose(b.points[:, 2], b.points[0, 2])          # a-b: level, straight
            continue
        lane = TL.LANE[b.lane_name]
        dz = np.diff(b.points[:, 2])
        dy = np.diff(b.points[:, 1])
        assert np.degrees(np.arctan2(np.abs(dz), np.abs(dy))).max() <= 30 + 1e-6
        on = np.abs(b.points[:, 1] - 0.5) <= 0.2
        assert np.allclose(b.points[on, 2] - FLOOR_Z, TL.DECK_H + lane.h)   # resting on the deck (bottom layer)
    st = [s for s in pl.supports if s.kind == "floor_strut"]
    assert len(st) == 1 and np.allclose(st[0].position[:2], (0.5, 0.5))


@pytest.mark.parametrize("d", TL.DENSITIES)
def test_tee_turns_into_branch(d):
    """The Tee: the run's far (-y) half and M0 run straight a -> b; its branch-side half turns into the branch from
    both ports, concentric with the wall fillet (left from a onto s' >= 0, right from b onto s' < 0); the branch's
    M0 is split off the straight M0 at a collar and peels on the left group's outer arc. Every lane at c is fed."""
    pl = P.plan("Tee", d)
    c_lanes = {}
    for b in pl.bundles:
        for i, e in enumerate(b.ends):
            if e.kind == "PORT" and e.ref.startswith("c:"):
                c_lanes[e.ref[2:]] = b
    assert set(c_lanes) == {l.name for l in TL.lanes(d)}
    for name, b in c_lanes.items():
        s_c = TL.LANE[name].s
        other = b.ends[0]
        if name == "M0":
            assert other == P.End("SPLIT", "M0") and b.params["peel_r"] == pytest.approx(TB.FIL_Y - TB.J_Y)
        else:
            assert other.kind == "PORT" and other.ref[0] == ("a" if s_c > 0 else "b")
        c0 = b.params["centre"]
        assert c0[0] == pytest.approx(TB.FIL_X if (s_c > 0 or name == "M0") else 1 - TB.FIL_X)
        assert c0[1] == pytest.approx(TB.FIL_Y)
        side = 1.0 if c0[0] < 0.5 else -1.0           # the arc lies past its centre, towards the branch
        on = (b.points[:, 1] < TB.FIL_Y - 1e-6) & (side * (b.points[:, 0] - c0[0]) >= -1e-9)
        r = np.linalg.norm(b.points[on, :2] - c0[:2], axis=1)
        dressed = name == "F1+" and d == "Full"      # parted 3 mm over the M0 collar, just before the arc
        assert on.sum() >= 20 and np.allclose(r, TB.FIL_Y - TB.J_Y - abs(s_c), atol=0.0031 if dressed else 1e-9)
    straight = [b for b in pl.bundles if "/" not in b.lane]
    assert {b.lane for b in straight} == {l.name for l in TL.lanes(d) if l.s <= 0}
    collars = [f for f in pl.fittings if f.kind == "split_collar"]
    assert len(collars) == (1 if "M0" in c_lanes else 0)


@pytest.mark.parametrize("shape", JUNCTIONS)
def test_junction_walls(shape):
    """Wall paths within 0.2 m (along the path) of an opening stand 0.15 high, every opening is closed by r 0.15
    fillets into the branch's walls, and the walls stand only outside the openings."""
    pl = P.plan(shape, "Full")
    baskets = [p for p in pl.structure if p.kind == "basket"]
    fillets = [p for p in pl.structure if p.kind == "wall"]
    assert len(fillets) == {"Tee": 2, "Cross": 4}[shape]
    for p in baskets:
        assert p.openings
        L = p.lengths()
        for w, (l0, l1), r in p.openings:
            assert r == TL.FILLET_R == 0.15
            assert not p.wall_mask(w)[(L > l0 + 1e-6) & (L < l1 - 1e-6)].any()
        near = any((L >= l0 - TL.JUNCTION_REACH).any() and (L <= l1 + TL.JUNCTION_REACH).any()
                   for _, (l0, l1), _ in p.openings)
        assert near and p.wall_h == TL.JUNCTION_WALL_H == 0.15
    for f in fillets:     # a quarter arc of radius 0.15, tangent to the run's wall and the branch's wall
        ends = f.points[[0, -1], :2]
        centre = next(np.array(q) for q in ((ends[0][0], ends[1][1]), (ends[1][0], ends[0][1]))
                      if np.allclose(np.linalg.norm(f.points[:, :2] - q, axis=1), TL.FILLET_R))
        assert f.wall_h == 0.15
        on_wall = [abs(abs(e[k] - (0.5 if shape == "Cross" or k == 0 else TB.J_Y)) - TL.WALL_S) < 1e-9
                   for e in ends for k in (0, 1)]
        assert sum(on_wall) >= 2, (shape, ends, centre)
    for w in (0, 1):      # the plain runs keep both walls at the plain height
        assert P.plan("StraightS", "Full").structure[0].wall_mask(w).all()


@pytest.mark.parametrize("d", TL.DENSITIES)
def test_junction_run(d):
    """straight -> Tee (in at a, out of its branch c) -> TurnH -> Cross (a -> b) -> TurnUp -> riser -> TurnDown ->
    straight: every block on the grid, every joint lane for lane, and every PORT end at an inner joint meets one."""
    s = lambda n: P.plan(n, d)
    chain = _place_chain([(s("StraightS"), "a", None, None), (s("Tee"), "a", 0, "b"), (s("TurnH"), "a", 1, "c"),
                          (s("Cross"), "a", 2, "b"), (s("TurnUp"), "a", 3, "b"), (s("StraightS"), "a", 4, "b"),
                          (s("TurnDown"), "a", 5, "b"), (s("StraightL"), "a", 6, "b")])
    placed = [c[0] for c in chain]
    ends = [(b.end_point(i), k) for k, pl in enumerate(placed) for b in pl.bundles for i, e in enumerate(b.ends)
            if e.kind == "PORT"]
    joints = [(1, "a"), (2, "a"), (3, "a"), (4, "a"), (5, "a"), (6, "a"), (7, "a")]
    for k, pin in joints:
        o = np.asarray(placed[k].ports[pin].o)
        here = [(p, j) for p, j in ends if np.linalg.norm(p - o) < 0.3 and abs((p - o) @ np.asarray(
            placed[k].ports[pin].t)) < 1e-6]
        mine = [p for p, j in here if j == k]
        theirs = [p for p, j in here if j != k]
        assert len(mine) == len(theirs) == len(TL.lanes(d))
        for p in mine:
            assert min(np.linalg.norm(p - q) for q in theirs) <= TL.POS_TOL


def test_mixed_bends_and_linear_densities():
    """A bend or junction joined to a denser or sparser linear piece lines up on the shared lanes; only the extra
    lanes end at the joint (as test_mixed_density_joint, for the new shapes)."""
    for shape in BEND_SHAPES + JUNCTIONS:
        for lo, hi in itertools.combinations(TL.DENSITIES, 2):
            for A, B in ((P.plan(shape, hi), P.plan("StraightS", lo)), (P.plan("StraightS", hi), P.plan(shape, lo))):
                T = P.place(B, "a", A.ports["b"])
                ea = {r: p for p, _, _, r, _ in port_ends(A, "b")}
                eb = {r: T(p) for p, _, _, r, _ in port_ends(B, "a")}
                for r, q in eb.items():
                    assert np.linalg.norm(ea[TL.mirror(r)] - q) <= TL.POS_TOL, (shape, lo, hi, r)


def test_drop_waterfalls_under_widened_split_zone():
    """Ruling P2-16 re-check: the Drop's waterfalls (peel radius 5 cm: zone = 8 cm along L1+) still leave L1+
    vertically and clear it outside their split run at every density; their exempt run ends inside the zone."""
    for d in TL.DENSITIES[1:]:
        pl = P.plan("Drop", d)
        parent = pl.bundle("L1+")
        for w in (b for b in pl.bundles if b.lane.startswith("WF")):
            pts, mask = split_run(w, parent)
            st = parent_station(parent, pts[mask])
            at = parent_station(parent, pts[:1])[0]
            assert np.abs(st - at).max() <= TL.split_zone(P.WF_RISE_R)
            gap = seg_dist(pts[~mask], parent.points[:-1], parent.points[1:]).min(axis=1) - w.radius - parent.radius
            assert gap.min() >= -TL.TOUCH_TOL
            assert np.allclose(pts[mask][:, :2], pts[0, :2])            # the run is the vertical climb


@pytest.mark.parametrize("d", ["Moderate", "Full"])
def test_tee_breakout_tie(d):
    """M-3: the branch M0 stays inside its parent's envelope for ~0.19 m past the collar (it peels on the left
    group's outer arc, r 0.36, and cannot peel tighter). A breakout tie BREAKOUT_DX past the collar binds M0, the
    branch and (Full) the F1- nested on M0 in one band in the plane x = const; LOD0 only, the only strap off the
    0.25 m rhythm."""
    pl = P.plan("Tee", d)
    ties = [f for f in pl.fittings if f.kind == "strap" and f.params.get("breakout")]
    want = {"M0", "M0/c"} | ({"F1-"} if d == "Full" else set())
    assert {f.params["bundle"] for f in ties} == want
    xb = TB.FIL_X + TB.BREAKOUT_DX
    collar = next(f for f in pl.fittings if f.kind == "split_collar")
    assert xb - (collar.frame.o[0] + collar.size[0] / 2) == pytest.approx(TB.BREAKOUT_DX)
    for f in ties:
        assert f.frame.o[0] == pytest.approx(xb) and np.allclose(f.frame.t, P.X) and f.params["lod0_only"]
        b = pl.bundle(f.params["bundle"])
        assert seg_dist(f.frame.o[None], b.points[:-1], b.points[1:]).min() < 2e-3     # on its bundle (chord sag)
    child, parent = pl.bundle("M0/c"), pl.bundle("M0")
    c = next(f for f in ties if f.params["bundle"] == "M0/c").frame.o
    gap = np.linalg.norm(c[1:] - np.array([TB.J_Y, parent.points[0][2]]))
    assert 0 < gap < 2 * R_B          # still fused with its parent there: the tie holds the fan-out
    assert not any(f.params.get("breakout") for f in P.plan("Tee", "Low").fittings)
