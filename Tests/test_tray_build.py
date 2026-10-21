"""The tray kit and the Blender build of the straight pieces (StraightS, StraightL, Reducer),
of the turns (TurnH, TurnUp, TurnDown), of the junctions (Tee, Cross) and of the rack interface (Drop, Chute, the rod
hangers).

Offline tests (tray_xsec, tray.collision) run everywhere; the build-marked ones read build_report.json after
    blender -b --python Source/Model/build_dc.py -- "DC_Tray_StraightS_*" "DC_Tray_StraightL_*" "DC_Tray_Reducer_*"
    blender -b --python Source/Model/build_dc.py -- "DC_Tray_Turn*" --no-render
    blender -b --python Source/Model/build_dc.py -- "DC_Tray_Tee_*" "DC_Tray_Cross_*" --no-render
    blender -b --python Source/Model/build_dc.py -- "DC_Tray_Drop_*" DC_Tray_Chute "DC_TrayRods_*" --no-render
"""
import math
import os

import numpy as np
import pytest

from dc import catalog, config, dims as DM, tray, tray_lanes as TL, tray_plan as TP, tray_xsec as XS
from dc.assetio import read_json


def _export_models_pure():
    """fracture_zones from dc/export_models.py (a bpy module: read, not imported)."""
    import ast
    src = open(os.path.join(config.HERE, "dc", "export_models.py")).read()
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fracture_zones"]
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "export_models", "exec"), ns)
    return ns["fracture_zones"]


fracture_zones = _export_models_pure()

T4 = [b.name for b in catalog.CATALOGUE if b.family == "tray" and b.variant in ("StraightS", "StraightL", "Reducer")]
TURNS = ("TurnH", "TurnUp", "TurnDown")
T6 = [b.name for b in catalog.CATALOGUE if b.family == "tray" and b.variant in TURNS]
JUNCTIONS = ("Tee", "Cross")
T7 = [b.name for b in catalog.CATALOGUE if b.family == "tray" and b.variant in JUNCTIONS]
DROPS = ("Drop", "Chute", "Rods")
T8 = [b.name for b in catalog.CATALOGUE if b.family in ("tray", "trayrods") and b.variant in DROPS]
BUILT = T4 + T6 + T7 + T8
FULL = ["DC_Tray_StraightS_Full", "DC_Tray_StraightL_Full"]
PER_METRE = (3000, 600, 150)        # LOD0..2 tris per metre of run at Full (plan §Global Constraints)
FITTING_RUN = 1.0                   # a fitting (the Reducer, the turns) is budgeted as 1 m of run (LOD1, LOD2)
BEND_LOD0 = 0.5                     # a turn's LOD0: <= half of Keen's LOD0 limit (its per-metre share is proven over
#                                     a 20 m run with turns: test_run20_with_turns)
JUNCTION_LOD0 = 0.6                 # a junction's LOD0 budget: <= 0.6 x Keen's LOD0 limit; the Full Cross is
#                                     the heaviest block (test_run20_with_junctions proves the per-metre share)
MATS = (8, 6, 4, 1)                 # materials per LOD (the last LOD: 1)


def cap_tris(name):
    """LOD0 triangles of a piece's cable-end caps (outside the plan's LOD0 budgets, inside Keen's)."""
    spec = catalog.BY_NAME[name]
    if spec.family != "tray":
        return 0
    return XS.CAP_TRIS * sum(1 for b in TP.plan(spec).bundles for x in b.ends if x.kind == "PORT")


def report():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    rep = read_json(config.REPORT_PATH)["blocks"]
    missing = [n for n in BUILT if not rep.get(n, {}).get("placement", {}).get("total")]
    if missing:
        pytest.skip(f"trays not built yet: {missing[:3]}")
    return rep


# ---------------------------------------------------------------------------------------------------- offline
def test_t4_blocks():
    assert len(T4) == 11      # 4 + 4 + 3


def test_u_stations_rhythm():
    """U-wires every 0.1 m from 5 cm off each port (the same set from either end, so the rhythm continues across
    joints); LOD1 keeps every other one; LOD2 none."""
    for L in (0.5, 1.5):
        st = XS.u_stations(L, 0)
        assert st[0] == pytest.approx(0.05) and st[-1] == pytest.approx(L - 0.05)
        assert np.allclose(np.diff(st), 0.1)
        assert set(XS.u_stations(L, 1)) <= set(st)
        assert XS.u_stations(L, 2) == []


def test_floor_wires():
    assert len(XS.FLOOR_S) == 9 and XS.FLOOR_S[0] == -0.2 and XS.FLOOR_S[-1] == 0.2
    # the floor wires' tops are the floor top; the U-wires lie under them and their undersides on the strut
    assert XS.FLOOR_WIRE_DH + TL.WIRE_R == 0.0
    assert TL.FLOOR_Z + XS.U_FLOOR_DH - TL.WIRE_R == pytest.approx(TP.BASKET_BOTTOM)


def test_basket_clears_bundles_and_rods():
    """Every wire clears every lane at Full; the U-wire legs (outside the wall wires) clear the trapeze rods."""
    for l in TL.lanes("Full"):
        assert TL.U_LEG_S - TL.WIRE_R - (abs(l.s) + TL.R_B) > 0.01
        for so in XS.FLOOR_S:   # floor wires lie below the floor top: never inside a bundle
            assert math.hypot(l.s - so, l.h - XS.FLOOR_WIRE_DH) >= TL.R_B + TL.WIRE_R - 1e-9
        assert math.hypot(abs(l.s) - TL.WALL_S, l.h - XS.LOWER_WALL_H) > TL.R_B + TL.WIRE_R
    assert TL.ROD_S - TL.ROD_R - (TL.U_LEG_S + TL.WIRE_R) >= TL.ROD_CLEAR - 1e-9


def test_wall_height_steps_down_at_ports():
    """A junction's 0.15 m walls ramp down to the straights' 0.10 m at each port end."""
    L = np.linspace(0, 1.0, 101)
    h = XS.wall_height_profile(L, TL.JUNCTION_WALL_H, True, True)
    assert h[0] == pytest.approx(TL.WALL_H) and h[-1] == pytest.approx(TL.WALL_H)
    assert h[50] == pytest.approx(TL.JUNCTION_WALL_H)
    assert np.all(np.abs(np.diff(h)) < 0.05 * 0.01 / 0.05 * 1.6)    # a smooth ramp, no step
    assert np.allclose(XS.wall_height_profile(L, TL.WALL_H), TL.WALL_H)
    assert XS.wall_height_profile(L, TL.JUNCTION_WALL_H, False, True)[0] == pytest.approx(TL.JUNCTION_WALL_H)


def test_cable_skin_closed():
    """The six visible cables' arcs meet at their contact points, so the bundle's skin is closed (no gap into the
    left-out centre cable), and the skin lies within the bundle radius."""
    arcs = XS.cable_arc()
    for a, b in zip(arcs, arcs[1:] + arcs[:1]):
        assert math.dist(a[-1], b[0]) < 1e-9
    r = max(math.hypot(*p) for a in arcs for p in a)
    assert r <= TL.R_B + 1e-9
    assert min(c[1] for c in XS.cable_centres()) == pytest.approx(-2 * TL.R_CABLE)   # one cable rests on the floor


@pytest.mark.parametrize("name", BUILT)
def test_lay_phase_locked_at_ports(name):
    """The per-piece lay rule: every bundle that runs port to port turns a WHOLE number of
    cable pitches (60 deg), the number nearest its own length at the nominal rate and at least one
    (tray_xsec.lay_pitches), so every port face shows the same strand pattern and the lay continues across joints.
    In a straight that is exactly the nominal rate; in a bend each lane is its own length (inner lanes shorter), so
    its rate differs slightly, but never by more than the rounding allows (half a pitch over the lane). The twist is
    uniform along each bundle's built centreline (the facets of a bend), and segments stay short enough that a chord
    sags < 1 mm."""
    pl = TP.plan(catalog.BY_NAME[name])
    nominal = XS.LAY_TURN / XS.LAY_LEN
    for b in pl.bundles:
        lock = XS.lay_locked(b)                     # ends on a PORT (a junction's split child too)
        q, lay = XS.lay_points(XS.built_centreline(pl, b, 0), lock=lock)
        assert lay[0] == 0.0
        assert np.all(np.diff(lay) >= 0)
        seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
        assert seg.max() <= XS.LAY_SEG + 1e-9
        turn = np.diff(lay)
        assert XS.CABLE_RING * (1 - np.cos(turn.max() / 2)) < 0.001
        L = float(seg.sum())
        cum = np.cumsum(seg)
        assert np.allclose(lay[1:], lay[-1] * cum / L)                  # one rate along the bundle
        if lock:
            k = lay[-1] / XS.LAY_TURN
            assert abs(k - round(k)) < 1e-9 and round(k) == XS.lay_pitches(L) >= 1, (b.lane, lay[-1])
            if pl.shape in TURNS + JUNCTIONS or b.ends[-1].kind == "ENTRY" or b.params.get("dress"):
                # (a waterfall arrives at its entry in phase 0, so a Chute continues it strand to strand)
                assert L >= XS.LAY_LEN / 2, b.lane                      # so one pitch stays within 2 x the rate
                assert abs(round(k) - L / XS.LAY_LEN) <= 0.5 + 1e-9
            else:
                assert lay[-1] / L == pytest.approx(nominal)             # one rate across a straight run
    # the six outer cables are interchangeable: a 60 deg turn maps the strand pattern onto itself
    arcs = XS.cable_arc()
    rot = [[(a * math.cos(XS.LAY_TURN) - c * math.sin(XS.LAY_TURN), a * math.sin(XS.LAY_TURN) + c * math.cos(
        XS.LAY_TURN)) for a, c in arc] for arc in arcs]
    pts = sorted((round(a, 9), round(c, 9)) for arc in arcs for a, c in arc)
    assert pts == sorted((round(a, 9), round(c, 9)) for arc in rot for a, c in arc)


def test_lay_rule_covers_every_piece():
    """No port-to-port bundle in the catalogue is shorter than half a lay length, so the 'at least one pitch'
    rule never twists a lane faster than twice the nominal rate; the bends' lanes differ in pitch count (inner vs
    outer) but every one turns at least once."""
    for spec in catalog.CATALOGUE:
        if spec.family != "tray" or spec.variant in ("Chute",):
            continue
        pl = TP.plan(spec)
        for b in pl.bundles:
            if all(e.kind == "PORT" for e in b.ends):
                assert b.length() >= XS.LAY_LEN / 2, (spec.name, b.lane, b.length())
    pl = TP.plan("TurnH", "Full")
    n = {b.lane: XS.lay_pitches(b.length()) for b in pl.bundles}
    assert n["M2+"] == 1 and n["M2-"] == 2          # the inner lane (r 0.28) and the outer one (r 0.62)


def test_strap_bites_the_bundle():
    """At LOD0 the band lies slightly inside the bundle radius (it cinches the cables), never deeper than
    the strands' crests."""
    for d in ("Low", "Full"):
        ds = [(l.s, l.h, TL.R_B) for l in TL.lanes(d)]
        for g in XS.strap_groups(ds):
            poly = XS.band_outline([ds[i] for i in g], -XS.STRAP_BITE, 8)
            c = XS.min_clearance(poly, [ds[i] for i in g])
            assert -XS.STRAP_BITE - 1e-6 <= c < 0


def test_strap_groups_share_a_band():
    """Nesting bundles share one band per station; separate bundles get their own."""
    def discs(d):
        return [(l.s, l.h, TL.R_B) for l in TL.lanes(d)]
    assert len(XS.strap_groups(discs("Full"))) == 1
    assert len(XS.strap_groups(discs("Moderate"))) == 5
    assert len(XS.strap_groups(discs("Low"))) == 2
    for d in ("Low", "Moderate", "Full"):
        for g in XS.strap_groups(discs(d)):
            ds = [discs(d)[i] for i in g]
            poly = XS.band_outline(ds, TL.STRAP_T, 10)
            assert XS.polygon_area(poly) > 0                       # counter-clockwise
            assert XS.min_clearance(poly, ds) >= TL.STRAP_T - 1e-6   # tight but never cutting a bundle
            assert max(h for _, h in poly) < TL.WALL_H + TL.EDGE_WIRE_R   # under the safety edge


def test_reducer_clamp_and_straps_at_full():
    """The Reducer's straps stay clear of its boots and clamps, and the Full clamp
    band stays inside the cell (it tops out about level with the safety edge)."""
    pl = TP.plan("Reducer", "Full")
    straps = [f for f in pl.fittings if f.kind == "strap"]
    for f in pl.fittings:
        if f.kind == "saddle_clamp":
            for s_ in straps:
                assert abs(s_.frame.o[0] - f.frame.o[0]) > (TL.STRAP_W + f.size[0]) / 2
            top = f.frame.o[2] + f.size[2] / 2
            assert top < TL.CELL - TL.FLOOR_Z + TL.FLOOR_Z and top - TL.FLOOR_Z < TL.WALL_H + 0.01
        if f.kind == "boot":
            x0, x1 = f.frame.o[0] - f.size[0] / 2, f.frame.o[0] + f.size[0] / 2
            for s_ in straps:
                assert s_.frame.o[0] + TL.STRAP_W / 2 < x0 or s_.frame.o[0] - TL.STRAP_W / 2 > x1


def test_simplify_keeps_ends_and_tolerance():
    p = np.array([(x, 0.0, 0.01 * math.sin(10 * x)) for x in np.linspace(0, 1, 101)])
    q = XS.simplify(p, 0.001)
    assert np.allclose(q[0], p[0]) and np.allclose(q[-1], p[-1]) and len(q) < len(p)
    for pt in p:   # every original point within tol of the simplified polyline
        d = min(np.linalg.norm(np.cross(b - a, pt - a)) / np.linalg.norm(b - a) if np.dot(pt - a, b - a) >= 0
                and np.dot(pt - b, a - b) >= 0 else min(np.linalg.norm(pt - a), np.linalg.norm(pt - b))
                for a, b in zip(q, q[1:]))
        assert d <= 0.001 + 1e-9


@pytest.mark.parametrize("name", T4)
def test_collision_layout(name):
    """One physics box (the trough, never the open top), occupancy covering the box, mount hints at the ports,
    under the strut, at each strut end plate and rod plate; every box inside the block."""
    spec = catalog.BY_NAME[name]
    c = tray.collision(spec)
    half = np.array(tray.size(spec))[[0, 2, 1]] / 2
    assert len(c["regular"]) == 1
    _, lo, hi = c["regular"][0]
    assert hi[2] == pytest.approx(-half[2] + TL.FLOOR_Z + TL.WALL_H)
    assert lo[2] == pytest.approx(-half[2] + TP.STRUT_LIFT)
    names = sorted(n for n, _, _ in c["mount"])
    assert names == sorted(["port_a", "port_b", "strut_bottom_0", "strut_end_m_0", "strut_end_p_0", "rod_plate_0_0",
                            "rod_plate_0_1"])
    for kind in ("regular", "occupancy", "mount"):
        for n, lo, hi in c[kind]:
            assert np.all(np.array(lo) >= -half - 1e-9) and np.all(np.array(hi) <= half + 1e-9), (kind, n)


def test_trays_planned_not_simple():
    """The trays fracture by plan (dc/fracture.py), as do the racks, and the simple
    per-box zones are left to describe an unfractured block's plain colliders (none for one box)."""
    from dc import fracture as FR
    from dc import rack
    assert fracture_zones({"regular": [("a", (0, 0, 0), (1, 1, 1))]}) == []
    spec = catalog.BY_NAME["DC_Rack42_Open"]
    assert len(FR.plan(spec, rack.collision(spec)).zones) == 8
    spec = catalog.BY_NAME["DC_Tray_StraightL_Full"]
    assert [z.id for z in FR.plan(spec, tray.collision(spec)).zones] == ["Fracture_01", "Fracture_02", "Fracture_03"]


# ---------------------------------------------------------------------------------------------------- build
def _expected_section(density):
    """The lane contract at a port face, as the built strands must show it: every lane's centre (tray_lanes) plus the
    phase-0 strand pattern of a bundle (tray_xsec.cable_arc), with the lane's material."""
    return [(l.s + a, l.h + c, l.material) for l in TL.lanes(density) for arc in XS.cable_arc() for a, c in arc]


def _match(got, want, tol=5e-4):
    """Every point of each set lies within tol of a point of the other with the same material."""
    for A, B in ((got, want), (want, got)):
        for a, h, m in A:
            d = min((math.hypot(a - b, h - k) for b, k, n in B if n == m), default=9.0)
            assert d <= tol, (a, h, m, d)


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_tray_built_matches_plan(name):
    """Measured on the BUILT LOD0 mesh (build_dc.port_sections: the cable vertices on each port plane, in the port's
    frame): the strands sit on the contract's lanes (tray_lanes) in the phase-0 strand pattern, with the lane's
    material, at both ports. So the kit's frames, lay and offsets cannot slip a bundle off the contract, and any two
    pieces of the same density join strand to strand in both directions."""
    rep = report()
    spec = catalog.BY_NAME[name]
    pl = TP.plan(spec)
    secs = rep[name]["tray"]["port_sections"]
    assert set(secs) == set(pl.ports)
    for k, port in pl.ports.items():
        got = [tuple(v) for v in secs[k]]
        want = _expected_section(port.density)
        assert len(got) == len({(round(a, 4), round(c, 4), m) for a, c, m in want}), (k, len(got), len(want))
        _match(got, want)
    # the port origins in the report are where the plan puts them (the model frame)
    for k, p in pl.ports.items():
        assert np.allclose(rep[name]["tray"]["ports"][k]["o"], pl.to_block(p.o), atol=5e-4)


@pytest.mark.build
@pytest.mark.parametrize("name", T4)
def test_tray_mount_faces(name):
    """Mount only where hardware exists (game faces: ports Left/Right, across Forward/Backward). A mount is a whole
    cell face, so the target area coverages (< 5 %, < 10 %) are not reachable on a 2 x 2 face; instead the mounting
    cells are pinned: Up exactly two (one per rod plate, diagonal, so they never merge), Forward/Backward exactly one
    each (the strut end plates), Down the cells under the strut, the ports every cell."""
    rep = report()
    e = rep[name]["placement"]
    f, cells = e["faces"], e["mount_cells"]
    nx = catalog.BY_NAME[name].cells[0]
    assert f["Up"]["groups"] == 2 and len(cells["Up"]) == 2
    assert f["Down"]["groups"] >= 1 and len(cells["Down"]) == 4
    for d in ("Forward", "Backward"):
        assert f[d]["groups"] >= 1 and len(cells[d]) == 1
    for d in ("Left", "Right"):
        assert f[d]["groups"] >= 1 and f[d]["coverage"] == 1.0
    assert f["Up"]["coverage"] == pytest.approx(2 / (2 * nx), abs=1e-3)
    # the plates and end plates sit at the centre: their cells are the two middle columns
    mid = {nx // 2 - 1 + catalog.bounds(catalog.BY_NAME[name])[0][0], nx // 2 + catalog.bounds(catalog.BY_NAME[name])[0][0]}
    for d in ("Up", "Down", "Forward", "Backward"):
        assert {c[0] for c in cells[d]} <= mid, (d, cells[d])


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_tray_occupancy(name):
    """The block claims exactly the cells its plan occupies (all of them but the TurnUp's two inside its curve)."""
    e = report()[name]["placement"]
    assert e["occupied"] == len(TP.occupied_cells(TP.plan(catalog.BY_NAME[name]))) and e["outside"] == 0


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_tray_materials(name):
    e = report()[name]
    for i, l in enumerate(e["lods"]):
        lim = MATS[-1] if i == len(e["lods"]) - 1 else MATS[min(i, 2)]
        assert l["materials"] <= lim, (i, l["material_names"])
    assert len({m for l in e["lods"][:-1] for m in l["material_names"]}) <= 8
    assert len(set(e["tray"]["materials_per_lod"][0])) <= 8      # hidden (stencil) and main parts together


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_run_budget_per_metre(name):
    """At Full: LOD0..2 per metre of run within (3000, 600, 150) (the Reducer, a fitting, counts as 1 m); every
    density: each LOD after LOD0 within 60 % of Keen's limit (LOD0 always fits its own limit: Keen's LOD count is
    chosen from it), the last LOD <= 19 triangles."""
    e = report()[name]
    spec = catalog.BY_NAME[name]
    lods = e["lods"]
    if spec.density == "Full":
        fitting = spec.variant in ("Reducer", "Drop") or spec.variant in TURNS + JUNCTIONS
        run = max(FITTING_RUN, e["tray"]["run_length"]) if fitting else e["tray"]["run_length"]
        for i in range(0 if spec.variant not in TURNS + JUNCTIONS + ("Drop",) else 1, min(3, len(lods) - 1)):
            caps = cap_tris(name) if i == 0 else 0
            assert (lods[i]["tris"] - caps) / run <= PER_METRE[i], (i, lods[i]["tris"], caps, run)
    if spec.variant in TURNS + JUNCTIONS + ("Drop",):   # LOD0: a share of Keen's (unbiased) limit; a run: run20
        from se2model import limits
        cap = limits.model_limits(e["model_size"])["lods"][0]["max_tris"]
        share = BEND_LOD0 if spec.variant in TURNS else JUNCTION_LOD0
        assert lods[0]["tris"] - cap_tris(name) <= share * cap, (lods[0]["tris"], cap)
    for i, l in enumerate(lods):
        assert l["tris"] <= l["max_tris"], (i, l)
        if i > 0:
            assert l["tris"] <= 0.6 * l["max_tris"], (i, l)
    assert lods[-1]["tris"] <= tray.LAST_LOD_MAX


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_tray_colliders(name):
    e = report()[name]
    assert e["colliders"]["regular"] <= 3


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_render_inset_from_side_planes(name):
    """The render mesh keeps >= 1 mm inside every non-port face (the across sides, top and bottom); along the run
    it ends exactly on the port planes."""
    e = report()[name]
    spec = catalog.BY_NAME[name]
    lo, hi = e["render_bounds"]
    half = (0.125 * c for c in (spec.cells[0], spec.cells[2], spec.cells[1]))
    pl = TP.plan(spec)
    faces = {(i, int(round(v))) for p in pl.ports.values() for i, v in enumerate(p.t) if abs(v) > 0.5}
    # an ENTRY plane is a port plane for the waterfalls: they end exactly on it, open
    faces |= {(i, int(round(v))) for en in pl.entries for i, v in enumerate(en.n) if abs(v) > 0.5}
    for i, h in enumerate(half):
        for sg, v in ((-1, -lo[i]), (1, hi[i])):
            if (i, sg) in faces:                     # a port face: the open ends lie exactly on it
                assert v == pytest.approx(h, abs=1e-6), (i, sg)
            elif i == 1 and any(sp.params.get("flush") for sp in TP.plan(spec).supports):
                # the vertical turns' strut-cap bolts end ON the across faces (Keen's 0.5 m model size)
                assert v == pytest.approx(h, abs=1e-6), (i, sg)
            else:                                    # any other face: >= 1 mm inside
                assert v <= h - 0.001 + 1e-9, (i, sg, v)


@pytest.mark.build
def test_bevel_guard_clean():
    rep = report()
    for n in BUILT:
        assert not rep[n].get("bevel_guard"), n


# the LOD chain each piece gets from Keen's table (it follows the measured LOD0, so a small LOD0 edit near a threshold
# changes it: StraightS Moderate 1400/1414, Reducer Low 1360/1414, StraightL Low 2088/2136). Pinned so such a flip is
# a deliberate change; "detail" = the kit level each LOD uses (a 3-LOD chain's LOD1 is the card version).
# (the cable-end caps lift StraightS Moderate to 1560 and StraightL Low to 2152, over their thresholds: both
# now get Keen's 4-LOD chain, a mid LOD between the full model and the card, the lay-rule LOD1 pop gone for them)
CHAINS = {"DC_Tray_StraightS_Empty": 3, "DC_Tray_StraightS_Low": 3, "DC_Tray_StraightS_Moderate": 4,
          "DC_Tray_StraightS_Full": 4, "DC_Tray_StraightL_Empty": 3, "DC_Tray_StraightL_Low": 4,
          "DC_Tray_StraightL_Moderate": 4, "DC_Tray_StraightL_Full": 4, "DC_Tray_Reducer_Low": 3,
          "DC_Tray_Reducer_Moderate": 4, "DC_Tray_Reducer_Full": 4,
          # the turns: Empty TurnH / TurnUp sit under Keen's next LOD0 row (1824 tris), so they get 3 LODs as well
          **{f"DC_Tray_{t}_{d}": 3 if (d == "Empty" and t != "TurnDown") else 4 for t in TURNS
             for d in ("Empty", "Low", "Moderate", "Full")},
          # the junctions: the Empty Tee (1816 tris) sits under Keen's next LOD0 row (2100): 3 LODs
          **{f"DC_Tray_{t}_{d}": 3 if (t, d) == ("Tee", "Empty") else 4 for t in JUNCTIONS
             for d in ("Empty", "Low", "Moderate", "Full")},
          # the Drops; the Chute (thin: 3 LODs); the rod hangers (a few hundred tris: Keen gives the 0.25 and
          # 2.0 m ones 2 LODs, LOD0 + the last, and the 1.0 m one 3)
          **{f"DC_Tray_Drop_{d}": 4 for d in ("Low", "Moderate", "Full")}, "DC_Tray_Chute": 3,
          "DC_TrayRods_025": 2, "DC_TrayRods_100": 3, "DC_TrayRods_200": 2}
DETAILS = {"DC_Tray_Chute": [0, 1], "DC_TrayRods_025": [0], "DC_TrayRods_100": [0, 1], "DC_TrayRods_200": [0]}


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_lod_chain_pinned(name):
    e = report()[name]
    assert len(e["lods"]) == CHAINS[name], [l["tris"] for l in e["lods"]]
    assert e["tray"]["detail"] == DETAILS.get(name, [0, 1, 2] if CHAINS[name] == 4 else [0, 2])


# ------------------------------------------------------------------------------------------------------------- turns
def test_bend_facets():
    """A bend's longitudinal parts (floor and wall wires, bundles) bend on shared radial lines at most 15 deg apart;
    the LOD0 set keeps both 5 cm port leads straight (the PORT rule); the U-wires stand on exactly the facet radials
    (every wire crossing is a vertex), from 5 cm off each port like a straight's; coarser LODs halve the facets."""
    for shape in TURNS:
        pl = TP.plan(shape, "Full")
        path = pl.structure[0]
        l0, l1, ang = path.arc
        L = float(path.lengths()[-1])
        f0 = XS.bend_facets(L, path.arc, 0)
        assert f0[0] == 0.0 and f0[-1] == L and f0[1] == pytest.approx(0.05)
        assert f0[-2] == pytest.approx(L - 0.05, abs=1e-4)          # (L: the sampled path's chord length)
        step = np.diff(f0[1:-1]) / ((l1 - l0) / ang)                   # radians per facet
        assert np.allclose(step, step[0]) and step[0] <= math.radians(15) + 1e-9
        assert XS.bend_u_stations(path.arc, 0) == pytest.approx(f0[1:-1])
        assert set(np.round(XS.bend_u_stations(path.arc, 1), 9)) <= set(np.round(f0, 9))
        assert XS.bend_u_stations(path.arc, 2) == []
        assert len(XS.bend_facets(L, path.arc, 1)) - 1 == XS.bend_facet_count(ang, 1)
        assert XS.bend_facets(L, path.arc, 2) == pytest.approx([0.0, L / 2, L], abs=1e-4)
        # every bundle re-samples onto the same radials: its facet points lie on the plan's lane, ends exact
        for b in pl.bundles:
            q = XS.built_centreline(pl, b, 0)
            assert len(q) == len(f0) and np.allclose(q[[0, -1]], b.points[[0, -1]])
            A, B = b.points[:-1], b.points[1:]

            def seg_dist(p):           # to the plan polyline (its segments)
                t = np.clip(np.einsum("ij,ij->i", p - A, B - A) / np.einsum("ij,ij->i", B - A, B - A), 0, 1)
                return np.min(np.linalg.norm(A + t[:, None] * (B - A) - p, axis=1))
            assert max(seg_dist(p) for p in q) < 1e-5


def test_turn_struts_on_u_wires():
    """Each turn's floor strut sits under a U-wire radial (it carries the basket where a cross wire is): TurnH on the
    45 deg one, as wide as the basket (its ends at the U-wire legs, nothing past the inner wall);
    TurnUp and TurnDown at the lead-end U-wire 5 cm from their port."""
    for shape in TURNS:
        pl = TP.plan(shape, "Full")
        path = pl.structure[0]
        sp = pl.supports[0]
        st = XS.bend_u_stations(path.arc, 0)
        pts = np.asarray(path.points)
        L = path.lengths()
        foot = np.array([[np.interp(l, L, pts[:, k]) for k in range(3)] for l in st])     # floor top at each U-wire
        up = np.asarray(sp.params.get("up", TP.Z))
        under = foot - up * (TL.FLOOR_Z - TP.STRUT_LIFT - TP.STRUT_H / 2)                 # strut centre under it
        r = np.asarray(sp.position) - under
        d = np.min(np.linalg.norm(r - np.outer(r @ np.asarray(sp.axis), sp.axis), axis=1))
        assert d < 1e-4, (shape, d)
    sp = TP.plan("TurnH", "Full").supports[0]
    assert sp.extent == pytest.approx((-(TL.U_LEG_S + TL.WIRE_R), TL.U_LEG_S + TL.WIRE_R))


@pytest.mark.parametrize("name", T6)
def test_turn_collision(name):
    """Two physics boxes (an L round the arc trough: each half of the path, never the open top), occupancy = the
    plan's cells, mount hints on both port faces and under the floor strut only (TurnH: the centre cell its 45 deg
    strut crosses; TurnUp: the two cells under its lead's strut; TurnDown: none, its strut is on an inner plane).
    The physics boxes never enter a cell the plan leaves free (the TurnUp's two inside its curve)."""
    spec = catalog.BY_NAME[name]
    pl = TP.plan(spec)
    c = tray.collision(spec)
    half = pl.size / 2
    assert len(c["regular"]) == 2
    names = sorted(n for n, _, _ in c["mount"])
    struts = {"TurnH": ["strut_bottom_0_0"], "TurnUp": ["strut_bottom_0_0", "strut_bottom_0_1"],
              "TurnDown": []}[spec.variant]
    assert names == sorted(["port_a", "port_b"] + struts)
    for kind in ("regular", "occupancy", "mount"):
        for n, lo, hi in c[kind]:
            assert np.all(np.array(lo) >= -half - 1e-9) and np.all(np.array(hi) <= half + 1e-9), (kind, n)
    occ = TP.occupied_cells(pl)
    n = np.round(pl.size / TL.CELL).astype(int)
    free = {(i, j, k) for i in range(n[0]) for j in range(n[1]) for k in range(n[2])} - occ
    for _, lo, hi in c["regular"]:
        a, b = np.array(lo) + half, np.array(hi) + half
        for cell in free:
            clo, chi = np.array(cell) * TL.CELL, (np.array(cell) + 1) * TL.CELL
            assert np.any(b <= clo + 1e-6) or np.any(a >= chi - 1e-6), (cell, a, b)


def _game_cells(spec, cells, shift):
    """Plan cells (box-corner, Blender axes) -> the game's cell indices (placement: glTF = (x, z, -y))."""
    size = TP.plan(spec).size
    out = set()
    for c in cells:
        p = (np.array(c) + 0.5) * TL.CELL - size / 2
        g = np.array([p[0], p[2], -p[1]])
        out.add(tuple(int(v) for v in np.round((g + np.array(shift)) / TL.CELL)))
    return out


@pytest.mark.build
@pytest.mark.parametrize("name", T6)
def test_turn_free_cells(name):
    """The built block claims exactly the plan's cells (tray_plan.occupied_cells), in game cell indices: the TurnUp
    leaves the two cells inside its curve free. (The TurnH's inner corner cell is NOT free: with the bend radii
    its inner wall cuts that cell's corner, so the plan claims it.)"""
    rep = report()
    spec = catalog.BY_NAME[name]
    e = rep[name]["placement"]
    lo, hi = catalog.bounds(spec)
    box = {(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}
    occ = _game_cells(spec, TP.occupied_cells(TP.plan(spec)), e["shift"])
    assert occ <= box
    assert {tuple(c) for c in e["free_cells"]} == box - occ
    assert len(e["free_cells"]) == (2 if spec.variant == "TurnUp" else 0)


GAME_DIR = {(-1, 0, 0): "Left", (1, 0, 0): "Right", (0, 1, 0): "Up", (0, -1, 0): "Down", (0, 0, -1): "Forward",
            (0, 0, 1): "Backward"}


@pytest.mark.build
@pytest.mark.parametrize("name", T6)
def test_turn_ports_mount(name):
    """Each port face mounts (>= 1 group); no other face does, except Down under the floor strut (TurnH, TurnUp;
    the TurnDown's Down face is its port b). A fitting is carried by its neighbours (Decision 8)."""
    e = report()[name]["placement"]
    pl = TP.plan(catalog.BY_NAME[name])
    port_faces = set()
    for p in pl.ports.values():
        t = np.round(p.t).astype(int)
        port_faces.add(GAME_DIR[(int(t[0]), int(t[2]), int(-t[1]))])
    strut = "Down" if any(n.startswith("strut_bottom") for n, _, _ in tray.collision(catalog.BY_NAME[name])["mount"]) \
        else None
    for d, f in e["faces"].items():
        if d in port_faces:
            assert f["groups"] >= 1, (d, f)
        elif d == strut:
            assert f["groups"] == 1, (d, f)
        else:
            assert f["groups"] == 0, (d, f)


# a 20 m Full run with turns: an offset (TurnUp, a 0.5 m riser, TurnDown) and a U (two TurnH), filled with StraightL
RUN20 = {"DC_Tray_TurnH_Full": 2, "DC_Tray_TurnUp_Full": 1, "DC_Tray_TurnDown_Full": 1, "DC_Tray_StraightS_Full": 1}


@pytest.mark.build
def test_run20_with_turns():
    """Plan Review Focus 5: a 20 m full-density run stays inside the per-metre budgets at LOD0..2, here with four
    turns in it (the turns spend more than a straight per metre at LOD0: a bend needs its facets)."""
    rep = report()
    length = sum(k * rep[n]["tray"]["run_length"] for n, k in RUN20.items())
    n_long = int(math.ceil((20.0 - length) / 1.5))
    parts = dict(RUN20, DC_Tray_StraightL_Full=n_long)
    length = sum(k * rep[n]["tray"]["run_length"] for n, k in parts.items())
    assert length >= 20.0
    for i in range(3):
        tris = sum(k * (rep[n]["lods"][i]["tris"] - (cap_tris(n) if i == 0 else 0)) for n, k in parts.items())
        assert tris / length <= PER_METRE[i], (i, tris, length)


@pytest.mark.build
@pytest.mark.parametrize("name", BUILT)
def test_keen_material_limits(name):
    """Keen's checker sizes a model by its LOD0 bounds: below 0.5 m it allows 4 / 3 / 1 materials, which no tray can
    meet (the lane colours) and which FAIL the game build. Every tray spans >= 0.5 m (the vertical turns by their
    full-width strut) and stays within Keen's material limit at every LOD."""
    e = report()[name]
    if catalog.BY_NAME[name].family != "trayrods":    # (a rod hanger carries no lanes: 3 materials fit Keen's small
        assert max(e["model_size"]) >= 0.5, e["model_size"]      # model limits, 4 / 1, so it keeps its 1 mm insets)
    for i, l in enumerate(e["lods"]):
        assert l["materials"] <= l["max_materials"], (i, l)


# --------------------------------------------------------------------------------------------------------- junctions
FREE = {"Tee": {(0, 2, 0), (3, 2, 0)}, "Cross": {(0, 0, 0), (0, 3, 0), (3, 0, 0), (3, 3, 0)}}


def test_t7_blocks():
    assert len(T7) == 8


def test_wall_step_between_u_wires():
    """As built, a junction wall stands at the plain 0.10 m up to just past the first U-wire
    (5 cm from the port: that U-wire and the splice plate stand exactly as a straight's), steps up on a straight 45 deg
    slope over 5 cm, and is at 0.15 m before the second U-wire (15 cm)."""
    L = np.linspace(0, 1.0, 1001)
    h = XS.wall_height_profile(L, TL.JUNCTION_WALL_H, True, True)
    at = lambda d: float(np.interp(d, L, h))        # noqa: E731
    assert at(XS.U_PHASE) == pytest.approx(TL.WALL_H) and at(1.0 - XS.U_PHASE) == pytest.approx(TL.WALL_H)
    assert at(XS.U_PHASE + XS.U_PITCH[0]) == pytest.approx(TL.JUNCTION_WALL_H)
    slope = np.diff(h) / np.diff(L)
    assert np.abs(slope).max() == pytest.approx(1.0, abs=1e-6)                 # 45 deg
    up = L[1:][(slope > 0.5)]           # the slope from the port at 0 starts at STEP_AT and runs STEP_RAMP
    assert up.min() == pytest.approx(XS.STEP_AT, abs=0.002)
    assert up.max() - up.min() == pytest.approx(XS.STEP_RAMP, abs=0.002)
    down = L[1:][(slope < -0.5)]        # ... and mirrored at the far port
    assert 1.0 - down.max() == pytest.approx(XS.STEP_AT, abs=0.002)
    assert XS.step_stations(1.0) == pytest.approx([0.06, 0.11, 0.89, 0.94])


def test_branch_u_wire_rhythm():
    """A branch's U-wires count from its port (0.05 + k 0.1, as a straight's), so the rhythm continues across the
    joint at port c; LOD1 keeps every other one."""
    pl = TP.plan("Tee", "Full")
    br = pl.structure[1]
    L = float(br.lengths()[-1])
    st = XS.branch_u_stations(L, 0)
    from_port = sorted(round(L - v, 6) for v in st)
    assert from_port[0] == pytest.approx(XS.U_PHASE) and np.allclose(np.diff(from_port), XS.U_PITCH[0])
    assert set(XS.branch_u_stations(L, 1)) <= set(st) and XS.branch_u_stations(L, 2) == []
    assert min(st) >= 0.02                                  # clear of the free end on the run's wall line


def test_junction_facets():
    """The junction bundles are built on facets as a bend's: a turning group (90 deg) every 15 deg on radials through
    its centre, both 5 cm port leads straight; the Cross's 30 deg ramp arcs as one chord each (a 15 deg kink at each
    end, as a bend's facets); every facet point lies on the plan's lane; LOD1 folds the leads (and the ramps' feet);
    LOD2: the turning groups' mid radial, the c-d stack's deck ends."""
    for shape in JUNCTIONS:
        pl = TP.plan(shape, "Full")
        for b in pl.bundles:
            if "facets" not in b.params:     # a straight a-b lane: level, or (Tee Full F1-) dressed over the collar
                q = XS.built_centreline(pl, b, 0)
                if not all(abs(p[2] - b.points[0][2]) < 1e-9 for p in b.points):
                    assert (shape, b.lane) == ("Tee", "F1-"), b.lane
                    d = np.diff(q, axis=0)
                    cosk = np.einsum("ij,ij->i", d[:-1], d[1:]) / (np.linalg.norm(d[:-1], axis=1) *
                                                                    np.linalg.norm(d[1:], axis=1))
                    assert np.degrees(np.arccos(np.clip(cosk, -1, 1))).max() <= 15.0      # a gentle dressing
                    m0 = pl.bundle("M0").points          # and it never comes nearer M0 than nesting allows
                    gap = min(np.min(np.linalg.norm(m0 - p, axis=1)) for p in b.points) - 2 * TL.R_B
                    assert gap >= -TL.TOUCH_TOL, gap
                continue
            f0, f1, f2 = b.params["facets"]
            along = np.asarray(b.params["along"])
            assert f0[0] == 0.0 and f0[-1] == pytest.approx(along[-1]) and len(f1) < len(f0) and len(f2) <= 4
            q = XS.built_centreline(pl, b, 0)
            A, B = b.points[:-1], b.points[1:]
            for p in q:
                t = np.clip(np.einsum("ij,ij->i", p - A, B - A) / np.einsum("ij,ij->i", B - A, B - A), 0, 1)
                assert np.min(np.linalg.norm(A + t[:, None] * (B - A) - p, axis=1)) < 1e-5, b.lane
            if "centre" in b.params and b.lane != "M0/c":     # a turning lane: the 5 cm leads stay straight
                assert f0[1] >= TL.PORT_STRAIGHT - 1e-9 and along[-1] - f0[-2] >= TL.PORT_STRAIGHT - 1e-9
            if shape == "Cross":
                d = np.diff(q, axis=0)
                ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", d[:-1], d[1:]) / (
                    np.linalg.norm(d[:-1], axis=1) * np.linalg.norm(d[1:], axis=1)), -1, 1)))
                assert ang.max() <= 15.1, (b.lane, ang.max())       # (facet points interpolate the plan's samples)
            else:
                d = np.diff(q, axis=0)
                ang = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", d[:-1], d[1:]) / (
                    np.linalg.norm(d[:-1], axis=1) * np.linalg.norm(d[1:], axis=1)), -1, 1)))
                assert ang.max() <= 15.1, (b.lane, ang.max())


def test_split_child_lay_locked():
    """The Tee's split child (M0 from its collar to port c) turns whole pitches, so it arrives at port c in phase 0
    (the measured port c section: test_tray_built_matches_plan)."""
    pl = TP.plan("Tee", "Moderate")
    child = pl.bundle("M0/c")
    assert child.ends[0].kind == "SPLIT" and XS.lay_locked(child)
    q, lay = XS.lay_points(XS.built_centreline(pl, child, 0), lock=True)
    assert (lay[-1] / XS.LAY_TURN) == pytest.approx(round(lay[-1] / XS.LAY_TURN))


def test_junction_strap_planes():
    """Straps in rhythm with the neighbours: every turning group's mid-arc straps share ONE
    radial plane through the group's centre (one band per nest), its lead straps lie in the straight lanes' plane
    0.125 m from port a or b, and its branch straps in the plane 0.125 m from port c."""
    pl = TP.plan("Tee", "Full")
    straps = [f for f in pl.fittings if f.kind == "strap"]

    def plane(f):
        t = np.asarray(f.frame.t)
        k = int(np.argmax(np.abs(t) > 1e-6))
        sg = 1 if t[k] > 0 else -1
        return tuple(np.round(sg * t, 4)), round(float(sg * f.frame.o @ t), 4)
    planes = {}
    for f in straps:
        planes.setdefault(plane(f), set()).add(f.params["bundle"])
    turning = [b.lane for b in pl.bundles if "/c" in b.lane]
    for lane in turning:
        mine = [plane(f) for f in straps if f.params["bundle"] == lane]
        assert len(mine) >= 2
    # one radial plane per turning group, holding every lane of the group
    diag = [p for p in planes if abs(abs(p[0][0]) - abs(p[0][1])) < 1e-3 and abs(p[0][0]) > 0.5]
    assert len(diag) == 2 and all(len(planes[p]) >= 4 for p in diag)
    for x in (0.125, 0.875):          # the lead straps in the straights' planes at a and b
        assert ((1.0, 0.0, 0.0), x) in planes and len(planes[((1.0, 0.0, 0.0), x)]) >= 5
    assert planes[((0.0, 1.0, 0.0), 0.625)] >= set(turning)      # the branch's strap 0.125 m from port c


def test_corner_floor_and_posts_avoid_free_cells():
    """A fillet corner's floor (edge arc + stubs on the 5 cm pitch) lies on the floor side of the fillet (outside its
    circle) and ends on the two outer floor wires; the fillet's posts (a quarter and three quarters round) stay out
    of the free corner cell; the plan's own solids graze the free cells by <= JUNCTION_GRAZE."""
    for shape in JUNCTIONS:
        pl = TP.plan(shape, "Full")
        for path in (p for p in pl.structure if p.kind == "wall"):
            c, e1, e2, R = XS.fillet_frame(path)
            edge, stubs = XS.corner_floor(path)
            assert np.allclose(np.linalg.norm(edge - c, axis=1), R + XS.FLOOR_EDGE_IN)
            assert len(stubs) == 2
            for a, b in stubs:
                for p in (a, b):
                    assert np.linalg.norm(p - c) >= R + XS.FLOOR_EDGE_IN - 1e-9
                    assert (p - c) @ e1 <= R + XS.FLOOR_EDGE_IN + 1e-9 and (p - c) @ e2 <= R + XS.FLOOR_EDGE_IN + 1e-9
                assert max((b - c) @ e1, (b - c) @ e2) == pytest.approx(R + XS.FLOOR_EDGE_IN)   # on an outer wire
            cell = next(cl for cl in TP.corner_cells(pl) if np.all(np.floor(c / TL.CELL).astype(int) == cl))
            lo, hi = np.array(cell) * TL.CELL, (np.array(cell) + 1) * TL.CELL
            L = path.lengths()
            for l in XS.fillet_posts(path):
                f = (math.pi / 2) * l / L[-1]
                rad = math.sin(f) * e1 + math.cos(f) * e2
                for r in (R - XS.U_LEG_DS - TL.WIRE_R, R + 0.007):
                    p = c + r * rad
                    assert not np.all((p[:2] > lo[:2] - 1e-9) & (p[:2] < hi[:2] + 1e-9)), (shape, p)
        for cell in TP.corner_cells(pl):
            assert TP.corner_graze(pl, cell) <= TP.JUNCTION_GRAZE


@pytest.mark.parametrize("name", T7)
def test_junction_collision(name):
    """Physics: each path's trough at the plain 0.10 m wall height over its whole length (it steps down at the ports:
    a neighbour's trough meets it flush) plus one raised box (the Tee: the run between its step-downs at
    0.15 m; the Cross: the crossing up to the stack's top over the saddle), <= 3 boxes, none in a free corner cell.
    Mounts: every port face, and Down under the floor strut only."""
    spec = catalog.BY_NAME[name]
    pl = TP.plan(spec)
    c = tray.collision(spec)
    half = pl.size / 2
    assert len(c["regular"]) == 3
    tops = sorted(hi[2] + half[2] for _, lo, hi in c["regular"])
    assert tops[0] == pytest.approx(TL.FLOOR_Z + TL.WALL_H) and tops[1] == pytest.approx(TL.FLOOR_Z + TL.WALL_H)
    raised = max(c["regular"], key=lambda b: b[2][2])
    assert raised[2][2] + half[2] >= TL.FLOOR_Z + TL.JUNCTION_WALL_H - 1e-9
    n, lo, hi = raised                   # only the raised box rises over 0.10, and it stops short of every port plane
    for p in pl.ports.values():          # by the step's flat 6 cm (where the wall is still at 0.10)
        k = int(np.argmax(np.abs(p.t)))
        plane = p.o[k] - half[k]
        gap = plane - hi[k] if p.t[k] > 0 else lo[k] - plane
        assert gap >= XS.STEP_AT - 1e-6, (n, p.name, gap)
    names = sorted(n for n, _, _ in c["mount"])
    assert names == sorted([f"port_{k}" for k in pl.ports] + ["strut_bottom_0"])
    for kind in ("regular", "occupancy", "mount"):
        for n, lo, hi in c[kind]:
            a, b = np.array(lo) + half, np.array(hi) + half
            assert np.all(a >= -1e-9) and np.all(b <= pl.size + 1e-9), (kind, n)
            for cell in FREE[spec.variant]:
                clo, chi = np.array(cell) * TL.CELL, (np.array(cell) + 1) * TL.CELL
                assert np.any(b <= clo + 1e-6) or np.any(a >= chi - 1e-6), (kind, n, cell)


@pytest.mark.build
@pytest.mark.parametrize("name", T7)
def test_tee_free_cells(name):
    """The built block leaves exactly its corner cells free (the Tee's two beside the branch, the Cross's four), in
    game cell indices, and no render vertex reaches more than 12 mm into them (a fillet's sliver: its 45 deg point
    lies 4 mm inside, plus the safety-edge wire)."""
    rep = report()
    spec = catalog.BY_NAME[name]
    e = rep[name]["placement"]
    lo, hi = catalog.bounds(spec)
    box = {(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}
    occ = _game_cells(spec, TP.occupied_cells(TP.plan(spec)), e["shift"])
    assert {tuple(c) for c in e["free_cells"]} == box - occ == _game_cells(spec, FREE[spec.variant], e["shift"])
    assert rep[name]["tray"]["geometry"]["corner_graze"] <= 0.012


@pytest.mark.build
@pytest.mark.parametrize("name", T7)
def test_junction_built_heights(name):
    """The render mesh stays >= 1 mm under the cell top; the Cross's saddle deck top, measured on the built mesh, is
    0.045 + 0.095 above the cell plane (+-1 mm)."""
    e = report()[name]
    spec = catalog.BY_NAME[name]
    top = 0.125 * spec.cells[1]
    assert e["render_bounds"][1][2] <= top - 0.001
    g = e["tray"]["geometry"]
    if spec.variant == "Cross":
        assert g["saddle_top"] == pytest.approx(TL.FLOOR_Z + TL.DECK_H, abs=0.001)
    else:
        assert "saddle_top" not in g


@pytest.mark.build
@pytest.mark.parametrize("name", T7)
def test_junction_ports_mount(name):
    """Every port face mounts; no other face does but Down (the floor strut)."""
    e = report()[name]["placement"]
    pl = TP.plan(catalog.BY_NAME[name])
    port_faces = {GAME_DIR[(int(t[0]), int(t[2]), int(-t[1]))] for t in (np.round(p.t).astype(int)
                                                                           for p in pl.ports.values())}
    for d, f in e["faces"].items():
        if d in port_faces:
            assert f["groups"] >= 1 and f["coverage"] > 0.3, (d, f)
        elif d == "Down":
            assert f["groups"] == 1, (d, f)
        else:
            assert f["groups"] == 0, (d, f)


# a 20 m Full run through junctions: a Tee and a Cross on the run (their branch arms count: 1.5 + 2.0 m), two TurnH
RUN20_J = {"DC_Tray_Tee_Full": 1, "DC_Tray_Cross_Full": 1, "DC_Tray_TurnH_Full": 2, "DC_Tray_StraightS_Full": 1}


@pytest.mark.build
def test_run20_with_junctions():
    """Plan Review Focus 5 with junctions: a 20 m Full network (StraightL fill) with a Tee and a Cross stays inside
    the per-metre budgets at LOD0..2."""
    rep = report()
    length = sum(k * rep[n]["tray"]["run_length"] for n, k in RUN20_J.items())
    n_long = int(math.ceil((20.0 - length) / 1.5))
    parts = dict(RUN20_J, DC_Tray_StraightL_Full=n_long)
    length = sum(k * rep[n]["tray"]["run_length"] for n, k in parts.items())
    assert length >= 20.0
    for i in range(3):
        tris = sum(k * (rep[n]["lods"][i]["tris"] - (cap_tris(n) if i == 0 else 0)) for n, k in parts.items())
        assert tris / length <= PER_METRE[i], (i, tris, length)


def test_junction_run_length():
    """A junction adds its arms to a run: each port to its centre (Tee 1.5 m, Cross 2.0 m)."""
    assert tray.run_length(catalog.BY_NAME["DC_Tray_Tee_Full"]) == pytest.approx(1.5)
    assert tray.run_length(catalog.BY_NAME["DC_Tray_Cross_Low"]) == pytest.approx(2.0)


def test_saddle_ties_on_deck_straps():
    """The deck straps are tied to the saddle: at each c-d strap station over the deck there is a tie
    mount each side of the stack, on the deck top, in the strap's plane, clear of the stack and inside the lips."""
    pl = TP.plan("Cross", "Full")
    (sd,) = [f for f in pl.fittings if f.kind == "crossover_saddle"]
    ties = TP.saddle_tie_boxes(sd)
    deck = [f for f in pl.fittings if f.kind == "strap" and f.params["bundle"].endswith("/d")
            and abs(f.frame.o[1] - 0.5) < sd.size[1] / 2]
    ys = sorted({round(float(f.frame.o[1]), 4) for f in deck})
    assert ys == [0.375, 0.625] and len(ties) == 4
    for q, size in ties:
        assert any(abs(q.o[1] - y) < 1e-9 for y in ys)
        assert q.o[2] - size[2] / 2 == pytest.approx(TL.FLOOR_Z + TL.DECK_H)
        across = abs(q.o[0] - 0.5)
        assert across - size[0] / 2 > 0.17 + TL.R_B + 0.005                    # clear of M2 (the outermost)
        inner, _ = TP.saddle_profiles(sd)["lip"]
        assert across + size[0] / 2 < inner[0][0]                             # inside the lips' bend


# ---------------------------------------------------------------------------------------------------------- port leads
def _straight_lane(lane="L1+", L=0.5):
    from dc.tray_plan import Bundle, End
    pts = np.array([(x, 0.25 + 0.085, TL.FLOOR_Z + TL.R_B) for x in np.linspace(0.0, L, 26)])
    return Bundle(pts, "PaintedMetalColorable", TL.R_B, (End("PORT", "a:" + lane), End("PORT", "b:" + lane)), lane)


def test_port_leads_and_simplify_bundle():
    """The PORT rule as built: a bundle whose plain simplification keeps its 5 cm leads straight is unchanged; one
    whose dressing (or ramp) starts right after a lead tilts that lead when simplified plainly, and then keeps the
    lead's end point, so its port ring stays square (e.g. the Tee's dressed F1-)."""
    from dc.tray_plan import Bundle, End
    b = _straight_lane()
    assert np.array_equal(XS.simplify_bundle(b, 0.008), XS.simplify(b.points, 0.008))       # straight: 2 points
    assert len(XS.simplify_bundle(b, 0.008)) == 2
    p = b.points.copy()
    p[:, 2] += 0.007 * np.clip((p[:, 0] - 0.05) / 0.1, 0, 1)        # rises 7 mm from 5 cm on, then level
    tilted = Bundle(p, b.material, b.radius, b.ends, b.lane)
    plain = XS.simplify(p, 0.008)
    assert abs(plain[1][2] - plain[0][2]) > 1e-6 and plain[1][0] > 0.05                    # the plain lead tilts
    kept = XS.simplify_bundle(tilted, 0.008)
    assert kept[1][0] == pytest.approx(0.04) and kept[1][2] == pytest.approx(kept[0][2])    # a point on the lead
    idx = XS.port_leads(p, tilted.ends)
    L = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    assert L[idx[0]] <= TL.PORT_STRAIGHT + 1e-9 < L[idx[0] + 1]
    assert L[-1] - L[idx[1]] <= TL.PORT_STRAIGHT + 1e-9 < L[-1] - L[idx[1] - 1]
    nonport = Bundle(p, b.material, b.radius, (End("SPLIT", "x"), End("BOOT", "boot:x")), b.lane)
    assert XS.port_leads(p, nonport.ends) == [] and np.array_equal(XS.simplify_bundle(nonport, 0.008), plain)


# the Reducers' dropped lanes (PORT -> BOOT ramp up onto the boot): points per LOD (TOL 1 / 3 / 8 mm); the kept
# 5 cm lead adds one point where a plain line would tilt the port ring
REDUCER_POINTS = {("Low", "L1+"): (4, 3, 3), ("Moderate", "M0"): (4, 3, 3), ("Moderate", "M2+"): (4, 3, 3),
                  ("Full", "F1+"): (5, 4, 3), ("Full", "F3+"): (5, 4, 3)}      # (plain: 4/2/2 and 5/4/2)


def test_reducer_points_pinned():
    from dc import tray_kit_tol
    for (d, lane), want in REDUCER_POINTS.items():
        pl = TP.plan("Reducer", d)
        b = pl.bundle(lane)
        got = tuple(len(XS.simplify_bundle(b, t)) for t in tray_kit_tol.TOL[:3])
        assert got == want, (d, lane, got)
        for t in tray_kit_tol.TOL[:3]:
            q = XS.simplify_bundle(b, t)
            assert np.linalg.norm(np.cross(q[1] - q[0], b.points[1] - b.points[0])) < 1e-9     # square at port a


def _poly_signed(p2, poly):
    """Signed distance of a 2D point to a closed polygon's boundary (negative inside)."""
    a, b = poly, np.roll(poly, -1, axis=0)
    ab = b - a
    t = np.clip(np.einsum("ij,ij->i", p2 - a, ab) / np.einsum("ij,ij->i", ab, ab), 0, 1)
    d = np.min(np.linalg.norm(a + t[:, None] * ab - p2, axis=1))
    inside = False
    for (x0, y0), (x1, y1) in zip(a, b):
        if (y0 > p2[1]) != (y1 > p2[1]) and p2[0] < x0 + (p2[1] - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return -d if inside else d


def _poly_signed_many(p2, poly):
    """_poly_signed for n points against n polygons (n, M, 2), vectorised (crossing count + nearest edge)."""
    a, b = poly, np.roll(poly, -1, axis=1)
    ab = b - a
    ap = p2[:, None, :] - a
    t = np.clip((ap * ab).sum(-1) / (ab * ab).sum(-1), 0, 1)
    d = np.linalg.norm(a + t[..., None] * ab - p2[:, None, :], axis=-1).min(axis=1)
    y, x = p2[:, 1:2], p2[:, 0:1]
    cross = (a[..., 1] > y) != (b[..., 1] > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xi = a[..., 0] + (y - a[..., 1]) * ab[..., 0] / ab[..., 1]
    inside = (np.sum(cross & (x < xi), axis=1) % 2) == 1
    return np.where(inside, -d, d)


def _skin_samples(rings, step=0.004):
    """A skin's vertices, face midpoints and edges sampled every <= step along the bundle."""
    out = [rings.reshape(-1, 3)]
    for r0, r1 in zip(rings[:-1], rings[1:]):
        n = max(1, int(math.ceil(np.max(np.linalg.norm(r1 - r0, axis=1)) / step)))
        for k in range(1, n):
            out.append(r0 + (r1 - r0) * k / n)
        mid = (r0 + r1) / 2
        out.append((mid + np.roll(mid, -1, axis=0)) / 2)
    return np.vstack(out)


def built_clearance(pl, skins=None):
    """Per ordered bundle pair (A, B): the least signed gap (m) from A's built skin to B's built skin section, and
    A's furthest sample inside B measured along B from the split (a child in its parent), from tray_xsec.skin_rings
    (the rings tray_kit.bundle sweeps)."""
    skins = skins or {b.lane: XS.skin_rings(pl, b) for b in pl.bundles}
    out = {}
    for A in pl.bundles:
        samp = _skin_samples(skins[A.lane][1])
        ca = skins[A.lane][0]
        for B in pl.bundles:
            if A is B:
                continue
            c, rings = skins[B.lane]
            far = np.min(np.linalg.norm(ca[:, None, :] - c[None], axis=-1))   # (vertex-to-vertex: >= the true min)
            if far > A.radius + B.radius + 0.26:          # (points <= 0.25 apart along each: lay segments)
                out[(A.lane, B.lane)] = (9.0, 0.0)
                continue
            seg0, seg1 = c[:-1], c[1:]
            d = seg1 - seg0
            dd = np.einsum("ij,ij->i", d, d)
            f = np.clip(((samp[:, None, :] - seg0[None]) * d[None]).sum(-1) / dd[None], 0, 1)
            dist = np.linalg.norm(seg0[None] + f[..., None] * d[None] - samp[:, None, :], axis=-1)
            j = dist.argmin(axis=1)
            near = dist[np.arange(len(samp)), j] < 2 * B.radius + 0.004
            fj = f[np.arange(len(samp)), j]
            ok = near & (fj > 1e-6) & (fj < 1 - 1e-6) | near & (j > 0) & (j < len(seg0) - 1)
            Lb = np.r_[0.0, np.cumsum(np.sqrt(dd))]
            idx = np.nonzero(ok)[0]
            if len(idx) == 0:
                out[(A.lane, B.lane)] = (9.0, 0.0)
                continue
            k, fk = j[idx], fj[idx]
            ring = rings[k] * (1 - fk)[:, None, None] + rings[k + 1] * fk[:, None, None]       # (n, M, 3)
            ctr = c[k] * (1 - fk)[:, None] + c[k + 1] * fk[:, None]
            t = d[k] / np.sqrt(dd[k])[:, None]
            ref = np.where(np.abs(t[:, 2:3]) < 0.9, [[0.0, 0.0, 1.0]], [[1.0, 0.0, 0.0]])
            e1 = np.cross(t, ref)
            e1 /= np.linalg.norm(e1, axis=1)[:, None]
            e2 = np.cross(t, e1)
            rel = ring - ctr[:, None, :]
            poly = np.stack([np.einsum("nmk,nk->nm", rel, e1), np.einsum("nmk,nk->nm", rel, e2)], -1)   # (n, M, 2)
            q = samp[idx] - ctr
            p2 = np.stack([np.einsum("nk,nk->n", q, e1), np.einsum("nk,nk->n", q, e2)], -1)          # (n, 2)
            g = _poly_signed_many(p2, poly)
            best = float(g.min())
            pen = g < 0
            deep = float((Lb[k] + fk * np.sqrt(dd[k]))[pen].max()) if pen.any() else 0.0
            out[(A.lane, B.lane)] = (best, deep)
    return out


CLEAR_MIN = 0.001          # built skins of neighbouring bundles keep >= 1 mm (measured minimum: 2.0 mm, Cross Full)


@pytest.mark.parametrize("name", [n for n in BUILT if catalog.BY_NAME[n].density != "Empty"])
def test_built_bundles_clear(name):
    """The contract's "bundles never interpenetrate", on the BUILT LOD0 skins (tray_xsec.skin_rings: the kit's path,
    facets, lay, frame drift and mitres): every sample of each bundle's skin keeps >= 1 mm outside every other
    bundle's skin section, except a split child inside its parent, whose overlap must end within the split zone
    (collar + peel radius) measured along the parent from the split."""
    pl = TP.plan(catalog.BY_NAME[name])
    res = built_clearance(pl)
    for (a, b), (gap, deep) in res.items():
        A, B = pl.bundle(a), pl.bundle(b)
        family = A.ends[0].kind == "SPLIT" and A.ends[0].ref == b or B.ends[0].kind == "SPLIT" and B.ends[0].ref == a
        if family:
            child = A if A.ends[0].kind == "SPLIT" else B
            parent = B if child is A else A
            split = child.points[0]
            s0 = np.argmin(np.linalg.norm(parent.points - split, axis=1))
            Ls = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(parent.points, axis=0), axis=1))][s0]
            if gap < 0 and child is A:
                assert deep - Ls <= TL.split_zone(child.params["peel_r"]) + 1e-6, (a, b, deep - Ls)
            continue
        assert gap >= CLEAR_MIN, (a, b, round(gap * 1000, 2))


# ------------------------------------------------------------------------------------------------ the rack interface
DROP_NAMES = [n for n in T8 if catalog.BY_NAME[n].variant == "Drop"]
RODS_NAMES = [n for n in T8 if catalog.BY_NAME[n].variant == "Rods"]


def test_t8_blocks():
    assert len(T8) == 7 and len(DROP_NAMES) == 3 and len(RODS_NAMES) == 3


def _cells_of(points, size):
    n = np.round(size / TL.CELL).astype(int)
    idx = np.clip(np.floor(np.asarray(points) / TL.CELL - 1e-7).astype(int), 0, n - 1)
    return {tuple(int(v) for v in r) for r in idx}


def _box_cells(size):
    n = np.round(size / TL.CELL).astype(int)
    return {(i, j, k) for i in range(n[0]) for j in range(n[1]) for k in range(n[2])}


def _hint_cells(boxes, size):
    """The cells an axis-aligned list of (name, lo, hi) boxes (centred frame) cover: the cell's centre inside the box
    on every axis the box spans, and on a thin slab's axis (a mount hint on a face) the slab within the cell."""
    out = set()
    for _, lo, hi in boxes:
        a, b = np.array(lo) + size / 2, np.array(hi) + size / 2
        for c in _box_cells(size):
            m = (np.array(c) + 0.5) * TL.CELL
            ok = True
            for k in range(3):
                if b[k] - a[k] < 0.02:
                    ok &= c[k] * TL.CELL - 1e-9 <= a[k] and b[k] <= (c[k] + 1) * TL.CELL + 1e-9
                else:
                    ok &= a[k] - 1e-9 < m[k] < b[k] + 1e-9
            if ok:
                out.add(c)
    return out


@pytest.mark.parametrize("name", DROP_NAMES)
def test_drop_free_cells(name):
    """The Drop claims its tray row and the two waterfall columns (the cells the falling bundles pass through, from
    the plan); every other cell of the drop zone under the tray is free. Its one physics box is the tray's trough."""
    spec = catalog.BY_NAME[name]
    pl = TP.plan(spec)
    size = pl.size
    tray_row = {c for c in _box_cells(size) if c[2] == 2 and c[1] < 2}
    columns = set()
    for b in pl.bundles:
        if b.lane.startswith("WF"):
            fall = b.points[b.points[:, 1] > 2 * TL.CELL]           # the waterfall beyond the tray: its column
            columns |= _cells_of(fall, size)
    assert columns == {(i, 2, k) for i in (0, 3) for k in range(3)}
    zone = _box_cells(size) - tray_row
    assert TP.occupied_cells(pl) == tray_row | columns
    assert _box_cells(size) - TP.occupied_cells(pl) == zone - columns and len(zone - columns) == 22
    c = tray.collision(spec)
    assert _hint_cells(c["occupancy"], size) == tray_row | columns
    assert len(c["regular"]) == 1
    _, lo, hi = c["regular"][0]
    assert hi[2] + size[2] / 2 <= 0.75 and lo[2] + size[2] / 2 >= 0.5            # the trough, in the tray row only
    # mounts: the ports, the rod plates (Up), the strut's -y end plate (the +y end is inside the block), the two
    # landing collars (Down); the strut stands on an inner plane over the drop zone: no Down hint there
    names = sorted(n for n, _, _ in c["mount"])
    assert names == sorted(["port_a", "port_b", "rod_plate_0_0", "rod_plate_0_1", "strut_end_m_0", "landing_0",
                            "landing_1"])
    landing = [b for b in c["mount"] if b[0].startswith("landing")]
    assert _hint_cells(landing, size) == {(0, 2, 0), (3, 2, 0)}


@pytest.mark.build
@pytest.mark.parametrize("name", DROP_NAMES + ["DC_Tray_Chute"])
def test_drop_free_cells_built(name):
    """The built Drop / Chute leaves exactly the plan's free cells free (game cell indices)."""
    rep = report()
    spec = catalog.BY_NAME[name]
    e = rep[name]["placement"]
    lo, hi = catalog.bounds(spec)
    box = {(x, y, z) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1)}
    occ = _game_cells(spec, TP.occupied_cells(TP.plan(spec)), e["shift"])
    assert {tuple(c) for c in e["free_cells"]} == box - occ
    assert len(e["free_cells"]) == (22 if spec.variant == "Drop" else 10)


@pytest.mark.parametrize("name", DROP_NAMES)
def test_waterfall_vertical(name):
    """The last 0.2 m above each ENTRY deviates < 1 mm from vertical: in the plan and on the built LOD0 centreline
    (tray_xsec.skin_rings: the kit's path, lay and frames)."""
    pl = TP.plan(catalog.BY_NAME[name])
    for b in pl.bundles:
        if b.ends[1].kind != "ENTRY":
            continue
        end = b.points[-1]
        for pts in (b.points, XS.skin_rings(pl, b)[0]):
            low = pts[pts[:, 2] <= end[2] + 0.2]
            assert len(low) >= 2 and np.linalg.norm(low[:, :2] - end[:2], axis=1).max() < 0.001, b.lane
        rings = XS.skin_rings(pl, b)[1]
        assert np.allclose(rings[-1][:, 2], end[2], atol=1e-9)       # the end ring lies flat on the entry plane


@pytest.mark.parametrize("name", ["DC_Tray_Drop_Full", "DC_Tray_Chute"])
def test_waterfall_entry_phase(name):
    """A waterfall arrives at its entry in phase 0 with its frame on the entry's a axis (tray_xsec.lay_locked,
    frame_drift), and a Chute's bundle leaves its top entry the same way: the two meet strand to strand (the built
    pattern: test_drop_chute_joint_strands)."""
    drop, chute = TP.plan("Drop", "Full"), TP.plan("Chute")
    for w in (b for b in drop.bundles if b.lane.startswith("WF")):
        c = chute.bundle(w.lane)
        a = XS.skin_rings(drop, w)[1][-1] - w.points[-1]
        b = XS.skin_rings(chute, c)[1][0] - c.points[0]
        d = np.linalg.norm(a[:, None] - b[None], axis=2)          # (the same strand pattern: a whole-pitch turn
        assert d.min(axis=1).max() < 5e-4 and d.min(axis=0).max() < 5e-4, w.lane    # permutes the strands)


def _station_band(pl, x, lod=0):
    """The run's strap bands at the station plane x of a straight piece: [(polygon (s, h) about the tray
    centreline at floor top)], as tray_kit.straps builds them (nesting bundles share a band)."""
    discs = []
    zf = pl.ports["a"].o[2]
    for f in pl.fittings:
        if f.kind == "strap" and abs(f.frame.o[0] - x) < 1e-9 and not f.params["bundle"].startswith("WF"):
            discs.append((float(f.frame.o[1] - TP.Y_C), float(f.frame.o[2] - zf), f.size[1] / 2 - TL.STRAP_T))
    return [XS.band_outline([discs[i] for i in g], -XS.STRAP_BITE if lod == 0 else TL.STRAP_T,
                            sides=8 if lod == 0 else 6) for g in XS.strap_groups(discs)]


@pytest.mark.parametrize("name", DROP_NAMES)
def test_waterfall_strap_clearance(name):
    """The run's strap bands (as built: one band per nest, cinched at LOD0) keep
    >= 2 mm off the waterfalls' built skins wherever a waterfall passes a station plane, and the waterfalls' own ties
    sit on the fall (plumb), round their bundle only."""
    pl = TP.plan(catalog.BY_NAME[name])
    zf = pl.ports["a"].o[2]
    for w in (b for b in pl.bundles if b.lane.startswith("WF")):
        _, rings = XS.skin_rings(pl, w)
        skin = _skin_samples(rings)
        for x in TP.strap_stations(pl.size[0]):
            near = skin[np.abs(skin[:, 0] - x) <= TL.STRAP_W / 2 + 1e-9]
            for poly in _station_band(pl, x):
                if len(near) == 0:
                    continue
                q = np.column_stack([near[:, 1] - TP.Y_C, near[:, 2] - zf])
                g = _poly_signed_many(q, np.repeat(np.array(poly)[None], len(q), axis=0))
                assert g.min() >= 0.002, (w.lane, x, g.min())
        ties = [f for f in pl.fittings if f.kind == "strap" and f.params["bundle"] == w.lane]
        assert len(ties) == len(TP.WF_STRAPS)
        for f in ties:
            assert np.allclose(f.frame.o[:2], w.points[-1][:2]) and f.size[1] == pytest.approx(2 * (TL.R_WF + TL.STRAP_T))


def test_guide_over_the_wall():
    """The guide: its plate's underside clears the basket's U-wire turned over the safety edge under it
    (one stands under each guide) by >= 1 mm and the safety edge by >= 2 mm; its two clamps hook the safety-edge wire
    (the strip's inside on the wire), standing from the plate's underside, between the U-wires; the bundle rides the
    rib crests at the 0.10 m bend radius; the cheeks keep it on the radius."""
    pl = TP.plan("Drop", "Full")
    zf = pl.ports["a"].o[2]
    us = XS.u_stations(pl.size[0], 0)
    for g in (f for f in pl.fittings if f.kind == "waterfall_guide"):
        c = np.asarray(g.params["centre"])
        r_in = g.params["r_top"] - g.params["thickness"]
        x0, x1 = g.frame.o[0] - g.params["width"] / 2, g.frame.o[0] + g.params["width"] / 2
        under = [u for u in us if x0 - TL.WIRE_R < u < x1 + TL.WIRE_R]
        assert len(under) == 1
        # the U-wire's turned-over end: from inside the wall wire over the safety edge to the leg (tray_kit._u_wire)
        h_turn = TL.WALL_H + XS.EDGE_TURN
        for s_ in np.linspace(TL.WALL_S - 0.007, TL.U_LEG_S, 12):
            d = np.hypot(TP.Y_C + s_ - c[1], zf + h_turn - c[2]) + TL.WIRE_R / math.cos(math.pi / 5)
            assert r_in - d >= 0.001, (s_, r_in - d)
        for s_, h in ((TL.U_LEG_S, h_turn - 0.03), (TL.U_LEG_S, h_turn)):        # the leg under the turn
            assert r_in - (np.hypot(TP.Y_C + s_ - c[1], zf + h - c[2]) + TL.WIRE_R) >= 0.001
        ws, wh, wr = g.params["wire"]
        assert (ws, wh) == pytest.approx((TL.WALL_S - TP.WF_S_C, TL.WALL_H - (TP.WF_CREST - TP.WF_GUIDE_R)))
        assert r_in - np.hypot(ws, wh) - wr >= 0.002
        path = TP.guide_clamp_path(g)
        cth = g.params["clamp"][1]
        assert path[0][1] == pytest.approx(math.sqrt(r_in ** 2 - ws ** 2))       # the stem starts at the plate
        for s_, h in path[1:]:
            assert np.hypot(s_ - ws, h - wh) - cth / 2 == pytest.approx(wr)        # the strip lies on the wire
        for dx in g.params["clamps"]:
            x = g.frame.o[0] + dx
            assert min(abs(x - u) for u in us) > g.params["clamp"][0] / 2 + TL.WIRE_R + 0.005
        w = next(b for b in pl.bundles if b.lane.startswith("WF") and abs(b.points[-1][0] - g.frame.o[0]) < 1e-9)
        arc = w.points[(w.points[:, 1] >= c[1] - 1e-9) & (w.points[:, 2] >= c[2] - 1e-9)]
        assert np.allclose(np.hypot(arc[:, 1] - c[1], arc[:, 2] - c[2]) - TL.R_WF, g.params["r_top"])
        assert g.params["width"] / 2 - g.params["cheek"][0] >= TL.R_WF + 0.015          # the cheeks clear the bundle
        assert g.params["cheek"][1] >= 0.5 * TL.R_WF                                    # ... and stand up its side


def test_landing_collars_seat():
    """Each waterfall lands through a brush collar seated 1 mm over the plane it lands on: across the slot it bears on
    the 42U brush plate's frame (wider than the opening, inside the frame's flange); over a half rack the Chute's top
    plate carries it (the plate reaches past it on every side)."""
    pl, chute = TP.plan("Drop", "Low"), TP.plan("Chute")
    (_, _), (ey0, ey1) = DM.TOP_ENTRY
    half = (ey1 - ey0) / 2
    for f in (f for f in pl.fittings if f.kind == "brush_collar"):
        r_out = f.size[1] / 2
        # seated ON the Drop's ENTRY plane: over a 42U it then floats only the rack's own ENTRY_DROP (1 mm)
        # over the brush frame (formerly 2 mm), and on a Chute it meets the top plate's face on that plane
        assert f.frame.o[2] - f.size[0] / 2 == pytest.approx(TP.ENTRY_SEAT) and TP.ENTRY_SEAT == 0.0
        assert DM.ENTRY_DROP == 0.001
        assert half < r_out <= half + DM.ENTRY_FLANGE
        assert f.params["r_bore"] > f.params["r_bundle"] == TL.R_WF
        sp = next(s for s in chute.supports if abs(s.position[0] - f.frame.o[0]) < 1e-9)
        fr, (th, sa, sw) = sp.ladder_plate("top_plate")
        bx = f.frame.o[0]
        by = f.frame.o[1] - 2 * TL.CELL                      # the Chute stands in the Drop's waterfall column
        assert fr.o[0] - sa / 2 <= bx - r_out and fr.o[0] + sa / 2 >= bx + r_out
        assert fr.o[1] - sw / 2 <= by - r_out and fr.o[1] + sw / 2 >= by + r_out


def test_chute_collision():
    """The Chute: one thin physics box per ladder (rails, rungs, plates, bundle) in its column, occupancy = the two
    columns, mounts only at the foot plates (Down, on the half rack's roof) and the top plates (Up, under the Drop's
    landing collars)."""
    spec = catalog.BY_NAME["DC_Tray_Chute"]
    pl = TP.plan(spec)
    size = pl.size
    c = tray.collision(spec)
    cols = {(i, 0, k) for i in (0, 3) for k in range(5)}
    assert TP.occupied_cells(pl) == cols and _hint_cells(c["occupancy"], size) == cols
    assert len(c["regular"]) == 2
    for _, lo, hi in c["regular"]:
        a, b = np.array(lo) + size / 2, np.array(hi) + size / 2
        assert b[0] - a[0] < 0.13 and b[1] - a[1] < 0.1           # thin: round the ladder only
        assert _cells_of([a + 1e-6, b - 1e-6], size) <= cols
    assert sorted(n for n, _, _ in c["mount"]) == ["foot_0", "foot_1", "top_0", "top_1"]
    assert _hint_cells([m for m in c["mount"] if m[0].startswith("foot")], size) == {(0, 0, 0), (3, 0, 0)}
    assert _hint_cells([m for m in c["mount"] if m[0].startswith("top")], size) == {(0, 0, 4), (3, 0, 4)}


@pytest.mark.parametrize("name", RODS_NAMES)
def test_rods_collision(name):
    """A rod hanger: one thin physics box per rod, occupancy = every cell its rods pass through (the whole box), mount
    hints only at the coupler footprints (Down) and the anchor plates (Up): the tray's rod-plate pattern, one cell per
    rod, diagonal (so the two never merge into one group)."""
    spec = catalog.BY_NAME[name]
    pl = TP.plan(spec)
    c = tray.collision(spec)
    assert TP.occupied_cells(pl) == _box_cells(pl.size)
    assert len(c["regular"]) == 2
    for _, lo, hi in c["regular"]:
        assert hi[0] - lo[0] < 0.03 and hi[1] - lo[1] < 0.03
    names = sorted(n for n, _, _ in c["mount"])
    assert names == ["anchor_0", "anchor_1", "coupler_0", "coupler_1"]


def _game_boxes(boxes):
    return [(n, np.array(lo), np.array(hi)) for n, lo, hi in boxes]


@pytest.mark.parametrize("name", RODS_NAMES)
def test_rods_hints_meet_rod_plates(name):
    """A rod hanger stood on a StraightS's top plane over its trapeze (the contract tests' placement): its Down hints
    are the tray's Up rod-plate hints (within 1 mm), and its Up hints are the same rectangles on its top plane (a
    hanger stacks on a hanger)."""
    rods, tr = catalog.BY_NAME[name], catalog.BY_NAME["DC_Tray_StraightS_Full"]
    rp, tp_ = TP.plan(rods), TP.plan(tr)
    shift = np.array([tp_.supports[0].position[0] - rp.size[0] / 2, 0.0, tp_.size[2]])   # rods box corner on the tray's
    up = [(n, lo + tp_.size / 2, hi + tp_.size / 2) for n, lo, hi in _game_boxes(tray.collision(tr)["mount"])
          if n.startswith("rod_plate")]
    rc = _game_boxes(tray.collision(rods)["mount"])
    down = [(n, lo + rp.size / 2 + shift, hi + rp.size / 2 + shift) for n, lo, hi in rc if n.startswith("coupler")]
    top = [(n, lo + rp.size / 2, hi + rp.size / 2) for n, lo, hi in rc if n.startswith("anchor")]
    assert len(up) == len(down) == len(top) == 2
    for (_, a0, a1), (_, b0, b1) in zip(sorted(up, key=lambda q: q[1][1]), sorted(down, key=lambda q: q[1][1])):
        assert np.allclose(a0[:2], b0[:2], atol=0.001) and np.allclose(a1[:2], b1[:2], atol=0.001)
        assert a1[2] == pytest.approx(b0[2])                     # the tray's top plane = the hanger's bottom plane
    for (_, a0, a1), (_, b0, b1) in zip(sorted(down, key=lambda q: q[1][1]), sorted(top, key=lambda q: q[1][1])):
        assert np.allclose(a0[:2], b0[:2]) and np.allclose(a1[:2], b1[:2])


@pytest.mark.build
@pytest.mark.parametrize("name", RODS_NAMES)
def test_rods_mount_only_on_plates(name):
    """Plan Review Focus 4 on the built hanger: Down and Up each mount exactly two cells in two groups (one per rod,
    diagonal: the tray's Up rod-plate cells); Left, Right, Forward and Backward never mount. (A game mount is a whole
    cell face, so the plates' area share is pinned as cells, as for the trays.) The Down cells, placed on a
    StraightS's trapeze, are the StraightS's Up cells."""
    rep = report()
    e = rep[name]["placement"]
    f, cells = e["faces"], e["mount_cells"]
    for d in ("Down", "Up"):
        assert f[d]["groups"] == 2 and len(cells[d]) == 2, (d, cells[d])
        assert f[d]["coverage"] == pytest.approx(2 / 4)
    for d in ("Left", "Right", "Forward", "Backward"):
        assert f[d]["groups"] == 0, (d, f[d])
    s = rep["DC_Tray_StraightS_Full"]["placement"]
    # game cells: x the same, the hanger one layer of cells over the tray: its Down cells' (x, z) = the tray's Up cells'
    assert {(c[0], c[2]) for c in cells["Down"]} == {(c[0], c[2]) for c in s["mount_cells"]["Up"]}
    assert {(c[0], c[2]) for c in cells["Up"]} == {(c[0], c[2]) for c in cells["Down"]}


def _rack_shift(rack, piece):
    """The block-centre -> rack-centre translation of a Drop (over a 42U) or a Chute (on a 24U): the plan's placement
    (Tests/test_tray_contract.py::test_drop_entries_match_rack): the box corner at (-0.5, TRAY_RACK_Y - 0.25 [+ 0.5 in
    the Drop's waterfall column], the rack's top plane)."""
    spec = catalog.BY_NAME[piece]
    pl = TP.plan(spec)
    top = 0.125 * catalog.BY_NAME[rack].cells[1]
    corner = np.array([-0.5, DM.TRAY_RACK_Y - 0.25 + (0.5 if spec.variant == "Chute" else 0.0), top])
    return corner + pl.size / 2


LANDINGS = [(r, "DC_Tray_Drop_Low" if r.startswith("DC_Rack42") else "DC_Tray_Chute")
            for r in ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_Open",
                      "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")]
LANDINGS.append(("DC_PDU_Cabinet", "DC_Tray_Drop_Low"))   # the PDU cabinet's top-entry brush plates


@pytest.mark.build
@pytest.mark.parametrize("rack,piece", LANDINGS)
def test_drop_lands_in_built_rack(rack, piece):
    """Against the BUILT pieces on both sides: each waterfall's built end on the entry plane (build_dc.entry_sections:
    the LOD0 cable vertices there), placed as test_drop_entries_match_rack places it, lies inside the built rack's
    brush-plate opening (geometry.top_entries) with >= 3 mm between the bundle's skin and every edge; the Drop over
    the 42U racks, the Chute's bottom on the 24U racks (open and door variants), every Drop density."""
    rep = report()
    ents = rep[rack]["geometry"]["top_entries"]
    pieces = [piece] if piece == "DC_Tray_Chute" else DROP_NAMES
    for p in pieces:
        got = {k: v for k, v in rep[p]["tray"]["entries"].items() if k.startswith("bottom")}
        assert len(got) == 2, (p, sorted(rep[p]["tray"]["entries"]))
        sh = _rack_shift(rack, p)
        for k, v in got.items():
            c = np.array(v["centre"]) + sh
            r = v["r"]
            assert r == pytest.approx(TL.R_WF, abs=0.0015)
            assert c[2] == pytest.approx(0.125 * catalog.BY_NAME[rack].cells[1])        # on the rack's top plane
            hit = [e for e in ents if e[0] < c[0] < e[1]]
            assert len(hit) == 1, (p, k, c, ents)
            x0, x1, y0, y1, z_top = hit[0]
            m = min(c[0] - x0, x1 - c[0], c[1] - y0, y1 - c[1]) - r
            assert m >= 0.003, (p, k, round(m * 1000, 2))
            assert c[2] - z_top < 0.002                              # the plate's top just under the landing


@pytest.mark.build
def test_drop_chute_joint_strands():
    """A Drop over a half rack meets the Chute under it strand to strand: the built Drop's bottom-entry cable
    vertices and the built Chute's top-entry ones coincide (within 0.5 mm) once the Chute stands in the Drop's
    waterfall column (every density)."""
    rep = report()
    ch = rep["DC_Tray_Chute"]["tray"]["entries"]
    chute = TP.plan("Chute")
    for p in DROP_NAMES:
        dr = rep[p]["tray"]["entries"]
        drop = TP.plan(catalog.BY_NAME[p])
        # centred frames -> the Drop's box-corner frame: the Chute's corner at (0, 0.5, -H_chute)
        for side in ("-", "+"):
            a = np.array(dr["bottom" + side]["points"]) + drop.size[:2] / 2
            b = np.array(ch["top" + side]["points"]) + chute.size[:2] / 2 + [0.0, 2 * TL.CELL]
            assert len(a) == len(b), (p, side, len(a), len(b))
            d = np.linalg.norm(a[:, None] - b[None], axis=2)
            assert d.min(axis=1).max() < 5e-4 and d.min(axis=0).max() < 5e-4, (p, side)


# --------------------------------------------------------------------------------------------- cable-end caps
@pytest.mark.build
@pytest.mark.parametrize("name", [n for n in BUILT if catalog.BY_NAME[n].family == "tray"])
def test_port_caps(name):
    """At every port, each bundle that ends there is closed at LOD0 by a cap CAP_INSET inside the port plane
    (7 faces: the hidden centre cable's hexagon and the six strand lobes), so a free run end shows solid cut cables,
    not hollow strand sweeps. Nothing lies on the port plane itself (the open strands do, for the flush join). The
    caps cover every piece, every density (tray_xsec.CAP_SKIP is empty)."""
    e = report()[name]
    spec = catalog.BY_NAME[name]
    pl = TP.plan(spec)
    caps = e["tray"]["port_caps"]
    assert set(caps) == set(pl.ports)
    skip = (pl.shape, pl.density) in XS.CAP_SKIP
    for k in pl.ports:
        n_end = sum(1 for b in pl.bundles for x in b.ends if x.kind == "PORT" and x.ref.split(":")[0] == k)
        assert caps[k] == (0 if skip else 7 * n_end), (k, caps[k], n_end)
    assert XS.CAP_INSET >= 0.001 and not XS.CAP_SKIP and not skip
    if any(x.kind == "PORT" for b in pl.bundles for x in b.ends):
        assert sum(caps.values()) * 16 / 7 == cap_tris(name)        # 7 faces = 16 triangles per bundle end


@pytest.mark.build
def test_caps_within_keen():
    """The caps are outside the plan's LOD0 budgets but inside Keen's: every capped Full piece keeps
    its LOD0 under Keen's limit (and the 60 % rule on the later LODs, which carry no caps)."""
    from se2model import limits
    rep = report()
    assert not XS.CAP_SKIP and XS.CAP_TRIS == 16
    for n in BUILT:
        e = rep[n]
        lods = e["lods"]
        assert lods[0]["tris"] <= limits.model_limits(e["model_size"])["lods"][0]["max_tris"], n
        if cap_tris(n):
            assert lods[0]["tris"] >= cap_tris(n)


@pytest.mark.build
def test_drop_full_hidden_collars():
    """The Full Drop's two split collars lie inside its dressed top layer (no one sees them): the plan keeps
    them (the SPLIT rule), the kit leaves them out, about 400 LOD0 triangles; the Low and Moderate Drops draw theirs."""
    for d in ("Low", "Moderate", "Full"):
        cs = [f for f in TP.plan("Drop", d).fittings if f.kind == "split_collar"]
        assert len(cs) == 2 and all(bool(f.params.get("hidden")) == (d == "Full") for f in cs)
    rep = report()
    assert rep["DC_Tray_Drop_Full"]["lods"][0]["tris"] < 6452     # (was 6452 with the collars; now 288 caps)
