"""Plan 5 Task 12: the racks' construction roles, and their side panels and fan tray as build-gated subparts (G2,
Ruling DB-10 Path A).

Supports  fracture.ROLES["rack"]: the posts and corner frame (`frame`), the 19" mounting rails (`rail`), the server
          slides (`slide`) and the containment rail (`contain`) are the structure the rack is built on, welded first
          (Fracture_NN_Support, the Support preset), as vanilla Smelter250 (24 % support).
Subparts  the two side panels (one RackSide model, right side and turned 180 deg) and the full racks' fan tray were
          static client-prefab children: painted and complete at 0 % build, never dented, floating when their zone
          died. They are now ConditionalSubParts entries (spawned only while the block is Functional: built to its
          MinFunctionalBuildProgress, no dead critical zone), each a BOUND client prefab with a server composition
          (ModelComponent + ChildTransform + Hierarchy, no client type) and a server prefab whose Hierarchy Children
          is [] (the vanilla SlideDoorNarrow_250_LeftDoor pattern), the tray's two rotors nested under the tray's
          CLIENT prefab only (Gyroscope50_Subparts nesting): task-12-spike.md Q1 (a)-(d). Below Functional the FR / DM
          show their stand-ins (fracture.STANDINS: the side LOD1 twice, the tray LOD1), hidden while the real ones
          are spawned (MeshPartsToHideWhenActive).
Open racks get the Ruling 15 functional chain (PowerableBlockComponent, ConsumedResource null, Fragility kept
          Structural) and a client-only ConditionalSubPartsComponent (spike Q3); the door racks' entries join the
          door's own ConditionalSubParts, which the server walk reaches (the walk gate: test_clientserver_walk)."""
import math
import os

import pytest

from dc import catalog, clone, config, doors, integration, rack, rack_side
from dc import fracture as FR
from dc import fracture_rules as FRR
from dc.assetio import read_json

from test_standins import _hide_list_matches, _man, _standin_faces_in_zone

RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear",
         "DC_Rack24_Open", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
DOOR_RACKS = tuple(r for r in RACKS if "Split" in r)
OPEN_RACKS = tuple(r for r in RACKS if r.endswith("_Open"))
FULL_RACKS = tuple(r for r in RACKS if r.startswith("DC_Rack42"))
SIDE, TRAY = rack_side.SIDE_SUB, doors.FAN_TRAY_SUB
T_MODEL = "VRage:Keen.VRage.Game.Components.Models.ModelComponent"
T_TRANSFORM = "VRage:Keen.VRage.Core.Game.Components.ChildTransformComponent"
T_HIERARCHY = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponent"
OB_HIERARCHY = "VRage:Keen.VRage.Core.Game.Components.HierarchyComponentObjectBuilder"


@pytest.fixture(scope="module")
def staged(stage_package):
    return stage_package()


def _files(name, pattern):
    out = set()
    for base in (config.STAGE_ASSETS, config.MOD_ASSETS):
        root = os.path.join(base, config.NAME, name)
        out |= {os.path.relpath(os.path.join(dp, f), base) for dp, _, fs in os.walk(root)
                for f in fs if f.endswith((".def", ".partialdef")) and pattern in f}
    return sorted(out)


def _one(name, pattern):
    f = _files(name, pattern)
    assert len(f) == 1, (name, pattern, f)
    return integration.read_current(f[0])


def _v(d):
    v = d["$Value"]
    return v.get("Manipulator", v) if "PartialDefinitionKind" in v else v


def _guid(d):
    return _v(d)["Guid"]


def _parts(name):
    return (SIDE, TRAY) if name in FULL_RACKS else (SIDE,)


def _hier_children(entity):
    """The HierarchyComponentObjectBuilder children a (delta-encoded or plain) ObjectBuilders list sets."""
    ob = entity.get("ObjectBuilders") or []
    rows = [c["Value"] for c in ob.get("Changed", [])] if isinstance(ob, dict) else [c["Value"] for c in ob]
    out = []
    for v in rows:
        if isinstance(v, dict) and v.get("$Type") == OB_HIERARCHY:
            ch = v.get("Children") or []
            out += [c["Value"] for c in ch["Changed"]] if isinstance(ch, dict) else [c.get("Value", c) for c in ch]
    return out


def _dummies(name):
    info = clone.entry(catalog.BY_NAME[name])["info"]
    m = _v(integration.read_current(info["model_def_file"]))
    return {c["Value"]["Name"]: c["Value"] for c in m["Dummies"]["Changed"]}


def _csp(staged, name):
    rel = staged["blocks"][name]["rack_subparts"]["conditional_subparts"]
    return rel, _v(integration.read_current(rel))


# ---------------------------------------------------------------------------------------------------- tables
def test_rack_role_table():
    """The posts, corner frame and roof rails (rack.py `frame`), the 19" rails (`rail`), the server slides (`slide`)
    and the containment rail (`contain`) are the rack's supports; panels, trim and hardware stay skin."""
    assert FR.ROLES["rack"] == {"support": ("frame", "rail", "slide", "contain")}
    FR.check_role_tables(FR.ROLES)


@pytest.mark.path_a
@pytest.mark.parametrize("name", RACKS)
def test_rack_standin_table(name):
    """Each rack parks its side panel twice (the right side at the block origin, the left turned 180 deg about the
    vertical: integration.SIDE_CHILDREN) and, on a full rack, its fan tray at the tray pivot; every one split over
    the zones it sits in (zone None), FR LOD0 <- the subpart's LOD1, FR LOD1 <- its LOD2."""
    st = FR.STANDINS[name]
    sides = [s for s in st if s.subpart == SIDE]
    assert [(s.at, s.yaw) for s in sides] == [((0.0, 0.0, 0.0), y) for _, y in integration.SIDE_CHILDREN]
    trays = [s for s in st if s.subpart == TRAY]
    assert len(trays) == (1 if name in FULL_RACKS else 0)
    if trays:
        assert trays[0].at == doors.fan_tray_point(catalog.BY_NAME[name]) and trays[0].yaw == 0.0
    assert all(s.zone is None and s.src_lods == (1, 2) for s in st)
    assert len(st) == len(sides) + len(trays)


# ---------------------------------------------------------------------------------------------------- build
@pytest.mark.build
@pytest.mark.parametrize("name", RACKS)
def test_rack_support_roles(name):
    """Every rack's FR LOD0 has its supports (Fracture_NN_Support), 5 % - 35 % of its triangles (vanilla Smelter250
    24 %)."""
    fr = _man(name)["fractured"]
    groups = fr["lods"][0]["groups"]
    assert any(g.startswith(FR.PREFIX) and g.endswith("_Support") for g in groups), (name, groups)
    share = fr["role_tris"]["support"] / fr["lods"][0]["tris"]
    assert 0.05 <= share <= 0.35, (name, round(share, 4))


def _placed(p, at, yaw):
    """A subpart-local point (Blender frame) placed at its pivot, turned yaw deg about +z."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (at[0] + c * p[0] - s * p[1], at[1] + s * p[0] + c * p[1], at[2] + p[2])


@pytest.mark.path_a
@pytest.mark.build
@pytest.mark.parametrize("name", RACKS)
def test_rack_standins(staged, name):
    """The FR and DM LOD0 carry the stand-ins, the NF none; every stand-in face sits in the zone holding its centroid
    (<= 2 cm past it) and the count equals the manifest's; every stand-in vertex lies inside one of its subparts'
    placed LOD0 boxes (parked where the real one spawns); the staged ConditionalSubParts hides exactly them; the FR
    stays within its budget (<= 28 006 at LOD0) with the LOD count unchanged (Keen's for its size and LOD0, = NF's)."""
    from se2model import limits
    man = _man(name)
    fr = man["fractured"]
    for key in ("fractured", "damaged"):
        m = man[key]
        parts = FRR.mesh_parts(FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, key.capitalize(),
                                                           m["lods"][0]["file"])))
        assert [p for p in parts if p.endswith(FR.SUBPART_SUFFIX)], (name, key)
    nf = FRR.mesh_parts(FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "NonFractured",
                                                    man["nonfractured"]["lods"][0]["file"])))
    assert not [p for p in nf if p.endswith(FR.SUBPART_SUFFIX)]
    assert _standin_faces_in_zone(name) == fr["standins"]["tris"]["0"]
    rep = read_json(config.REPORT_PATH)["blocks"][name]["subparts"]["models"]
    boxes = []
    for s in FR.STANDINS[name]:
        (x0, y0, z0), (x1, y1, z1) = rep[s.subpart]["bounds_local"]
        corners = [_placed((x, y, z), s.at, s.yaw) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        boxes.append([min(c[a] for c in corners) for a in range(3)] + [max(c[a] for c in corners) for a in range(3)])
    # FR LOD0 (the subparts' LOD1) and FR LOD1 (their LOD2): every stand-in vertex inside a placed LOD0 box, and
    # nothing past the side panel's render inset rack.XO (fix round 1, M2: the LOD1 vent slats once stood 17 mm proud)
    for lod in (0, 1):
        meshes = FRR.fbx_meshes(os.path.join(config.MODELS_DIR, name, "Fractured", fr["lods"][lod]["file"]))
        n = 0
        for m in meshes.values():
            for poly, k in zip(m["polys"], m["poly_mat"]):
                if m["materials"][k].endswith(FR.SUBPART_SUFFIX):
                    for i in poly:
                        p = m["verts"][i]
                        assert any(all(b[a] - 0.002 <= p[a] <= b[a + 3] + 0.002 for a in range(3)) for b in boxes), \
                            (name, lod, m["materials"][k], p)
                        assert abs(p[0]) <= rack.XO + 0.001, (name, lod, m["materials"][k], p)
                    n += 1
        assert n, (name, lod)
    rel, _ = _csp(staged, name)
    _hide_list_matches(staged, name, rel)
    st = fr["standins"]["tris"]
    assert st["0"] > 0 and st["1"] > 0
    assert fr["lods"][0]["tris"] <= 28006 and fr["lods"][0]["tris"] <= fr["budget"][0]
    for i, row in enumerate(fr["lods"][:-1]):
        assert row["tris"] <= fr["budget"][i], (i, row["tris"], fr["budget"][i])
    assert len(fr["lods"]) == len(man["nonfractured"]["lods"])
    assert limits.optimal_lods(tuple(fr["size"]), fr["lods"][0]["tris"])[0] == len(fr["lods"])


@pytest.mark.path_a
# ---------------------------------------------------------------------------------------------------- staged
@pytest.mark.parametrize("name", RACKS)
def test_rack_children_follow_build(staged, name):
    """No static children on the block's client prefab any more (no side, tray or rotor whatever the state); the
    ConditionalSubParts map each subpart's dummy type to its client prefab (door racks: beside the leaves) and hides
    the stand-ins while they are spawned (MeshPartsToHideWhenActive == the FR LOD0 stand-in parts, keyed form)."""
    cl = _v(_one(name, f"{name}_Client.partialdef"))
    assert _hier_children(cl["_entity"]) == [], name
    rel, csp = _csp(staged, name)
    want = {_guid(_one(name, f"_{p}_DummyTypeDefinition")): _guid(_one(name, f"_{p}.partialdef"))
            for p in _parts(name)}
    assert want.items() <= csp["SubParts"].items(), (name, csp["SubParts"])
    if name in DOOR_RACKS:
        assert len(csp["SubParts"]) == len(doors.leaves(catalog.BY_NAME[name])) + len(want)
        assert rel.endswith("_Client_ConditionalSubPartsDefinition.def")
    else:
        assert csp["SubParts"] == want
    man = _man(name)
    assert [x["Value"] for x in csp["MeshPartsToHideWhenActive"]] == integration.standin_parts(man)
    assert integration.standin_parts(man)


@pytest.mark.path_a
@pytest.mark.parametrize("name", RACKS)
def test_rack_subparts_are_bound(staged, name):
    """task-12-spike.md Q1 (a)+(b): each entry is a PrefabBinding's ClientPrefab; the binding's ServerComposite is
    instantiated by exactly one server prefab, whose Hierarchy Children is []; the server composition holds exactly
    ModelComponent (the subpart's own model component), ChildTransform and Hierarchy (no client type)."""
    for p in _parts(name):
        cp = _guid(_one(name, f"_{p}.partialdef"))
        b = [_v(integration.read_current(f)) for f in _files(name, f"_{p}_Binding.def")]
        assert len(b) == 1 and b[0]["ClientPrefab"] == cp, (name, p, b)
        sc = b[0]["ServerComposite"]
        comp = _v(_one(name, f"_{p}_ServerComposition.def"))
        assert comp["Guid"] == sc
        types = sorted(c["Value"]["Type"] for c in comp["Components"])
        assert types == sorted([T_MODEL, T_TRANSFORM, T_HIERARCHY]), types
        mc = [c["Value"]["Definition"] for c in comp["Components"] if c["Value"]["Type"] == T_MODEL]
        assert mc == [_guid(_one(name, f"_{p}_ModelComponentDefinition"))]
        prefabs = [f for f in _files(name, "") if f.endswith(".def")
                   and (_v(integration.read_current(f)).get("_entity") or {}).get("Definition") == sc]
        assert len(prefabs) == 1 and prefabs[0].endswith(f"_{p}_Server.def"), prefabs
        sp = _v(integration.read_current(prefabs[0]))
        assert _hier_children(sp["_entity"]) == []
        assert any(isinstance(o["Value"], dict) and o["Value"].get("$Type") == OB_HIERARCHY
                   and o["Value"]["Children"] == [] for o in sp["_entity"]["ObjectBuilders"])


@pytest.mark.path_a
@pytest.mark.parametrize("name", FULL_RACKS)
def test_tray_rotors_under_the_tray_client_prefab(staged, name):
    """Q1 (c): the two rotors are Hierarchy children of the fan tray's CLIENT prefab (Gyroscope50_Subparts nesting),
    each at its pivot relative to the tray's (the spawn overwrites only the root ChildTransform: the offsets survive);
    their InfiniteRotation follows the block's animation controller (closest parent: Working)."""
    spec = catalog.BY_NAME[name]
    tray = _v(_one(name, f"_{TRAY}.partialdef"))
    kids = _hier_children(tray["_entity"])
    fan = _guid(_one(name, f"_{doors.FAN}_Composite"))
    assert [k["Definition"] for k in kids] == [fan, fan]
    t = doors.to_game(doors.fan_tray_point(spec), spec)
    for k, p in zip(kids, doors.fan_points(spec)):
        want = [round(a - b, 6) for a, b in zip(doors.to_game(p, spec), t)]
        tf = [o["Value"] for o in k["ObjectBuilders"] if isinstance(o["Value"], dict)
              and "TransformWithEulerHint" in o["Value"]][0]
        got = [tf["TransformWithEulerHint"]["Transform"]["Position"][a] for a in "XYZ"]
        assert got == pytest.approx(want, abs=1e-6), (k["DebugName"], got, want)
    cc = _v(_one(name, f"{name}_ClientComposition"))
    assert integration.T_ANIMCTL in [c["Value"].get("Type") for c in cc["Components"]["Changed"]
                                     if isinstance(c.get("Value"), dict)]


@pytest.mark.path_a
@pytest.mark.parametrize("name", RACKS)
def test_rack_subpart_dummies(staged, name):
    """The block model's spawn points: RackSideR at the block origin and RackSideL turned 180 deg about game +Y (the
    side dummy type), RackFanTray at the tray pivot (the tray's); the rotors have no block dummy any more."""
    spec = catalog.BY_NAME[name]
    dm = _dummies(name)
    side_t = _guid(_one(name, f"_{SIDE}_DummyTypeDefinition"))
    for child, yaw in integration.SIDE_CHILDREN:
        d = dm[child]
        assert d["Type"] == side_t
        assert [d["Transform"]["Transform"]["Position"][a] for a in "XYZ"] == pytest.approx(
            list(doors.to_game((0.0, 0.0, 0.0), spec)))
        assert d["Transform"]["EulerHint"]["Y"] == yaw
        assert abs(d["Transform"]["Transform"]["Orientation"]["Y"]) == pytest.approx(1.0 if yaw else 0.0, abs=1e-6)
    if name in FULL_RACKS:
        d = dm[TRAY]
        assert d["Type"] == _guid(_one(name, f"_{TRAY}_DummyTypeDefinition"))
        assert [d["Transform"]["Transform"]["Position"][a] for a in "XYZ"] == pytest.approx(
            list(doors.to_game(doors.fan_tray_point(spec), spec)))
    assert not [n for n in dm if n.startswith(doors.FAN) and n != TRAY]


@pytest.mark.path_a
@pytest.mark.parametrize("name", OPEN_RACKS)
def test_open_rack_functional_chain(staged, name):
    """Spike Q3: the open rack spawns its ConditionalSubParts only with a FunctionalBlockComponent: the Ruling 15
    chain (onto_powerable from the structural CubeBlockComponent: PowerableBlockDefinition, ConsumedResource null,
    built ON), Fragility kept Structural; a ConditionalSubPartsComponent (and the animation controller, so the rotors
    follow Working) on the CLIENT composition only."""
    info = clone.entry(catalog.BY_NAME[name])["info"]
    bd = integration.read_current(info["block_def_file"])["$Value"]
    assert bd["BaseDefinition"] == integration.POWERABLE_DEF_BASE
    m = bd["Manipulator"]
    assert m["ConsumedResource"] is None and m["Fragility"] == integration.FRAGILITY["Structural"]
    for k, v in integration.STRUCTURAL_DEF_VALUES.items():
        assert m[k] == v, k
    for side in ("Server", "Client"):
        c = _v(_one(name, f"{name}_{side}Composition"))
        types = [x["Value"].get("Type") for x in c["Components"]["Changed"] if isinstance(x.get("Value"), dict)]
        assert integration.T_POWERABLE in types, side
        assert (integration.T_CONDSUB in types) == (side == "Client"), side
        assert (integration.T_ANIMCTL in types) == (side == "Client" and name in FULL_RACKS), side
        assert integration.STRUCTURAL_KEY not in c["Components"]["Keys"]


def test_every_rack_is_terminal_listed_with_on_off(staged):
    """User ruling (Task 12 fix round 1, M6): all six racks are in the grid terminal with On/Off, draw no power and
    are built On. Terminal-listed = the server composition holds a FunctionalBlockComponent (PowerableBlockComponent
    is one) with no NO_TERMINAL* tag on it (StreamedControlPanelSessionComponent.IsBlockEligible,
    decompiled-current Game2.Simulation, :819-825); On/Off = the PowerableBlockComponent (its terminal toggle,
    PowerableBlockDetailModelServer); no power = ConsumedResource null (open racks) or an amount of 0 (the door racks'
    vanilla SlidingDoorNarrow250 value); built On = the server prefab's PowerableBlockObjectBuilder Enabled true.
    Checked on the fully resolved definitions (SDK < mod Assets < this run's staging, Copy chains applied)."""
    import clientserver_walk as csw
    u = csw.Universe([csw.SDK_ASSETS, config.MOD_ASSETS, config.STAGE_ASSETS])
    for name in RACKS:
        rel = f"{config.NAME}/{name}/{name}.partialdef"
        b = u.resolve(_guid(integration.read_current(rel)))
        sc = b["ServerComposite"]
        comp = u.resolve(sc)
        keys = [k for k, t, _ in csw.components(comp) if (t or "").endswith(".PowerableBlockComponent")]
        assert len(keys) == 1, (name, keys)
        tags = comp.get("TagSlots") or []
        assert not [t for t in tags if str(t.get("$Key", "")).startswith("NO_TERMINAL")
                    and str(t.get("$Value", "")).lower() == keys[0]], (name, tags)
        info = clone.entry(catalog.BY_NAME[name])["info"]
        bd = u.resolve(info["block_def"])
        assert u.full_type_of(info["block_def"]).endswith(".PowerableBlockDefinition"), name
        cr = bd.get("ConsumedResource")
        assert cr is None or cr.get("Amount") == 0, (name, cr)
        sp = [p for p in u.guids_of_type("PrefabDefinition") if csw.composition_of(u.resolve(p)) == sc]
        assert len(sp) == 1, (name, sp)
        ob = csw.object_builders(u.resolve(sp[0])["_entity"]).get(keys[0])
        assert isinstance(ob, dict) and ob.get("$Type", "").endswith("PowerableBlockObjectBuilder"), (name, ob)
        assert ob.get("Enabled") is True, (name, ob)


@pytest.mark.path_a
@pytest.mark.build
@pytest.mark.parametrize("name", RACKS)
def test_rack_standins_capped(name):
    """Plan 5 Task 13 fix round 1 (StandIn.cut): the side (and tray) stand-ins are cut along the rack's seams with
    break caps, so the piece a live zone keeps is closed where a dead neighbour's piece was. On the 42U racks the
    sides cross the columns' mid-height seam: both column zones of each side get a `<zone>-FracturedMaterial01_Subpart`
    part, hidden with the other stand-ins (MeshPartsToHideWhenActive = the manifest's parts) and within 2 cm of their
    zone (_standin_faces_in_zone). On the 24U racks no seam crosses a side (it stands on the plinth seam, inside one
    column zone's height), so a dead column takes its side whole and there is nothing to cap."""
    assert all(s.cut for s in FR.STANDINS[name])
    man = _man(name)
    parts = man["fractured"]["standins"]["parts"]
    caps = sorted({p.split("-")[0] for p in parts if p.endswith(f"-{FR.CUT_MATERIAL}{FR.SUBPART_SUFFIX}")})
    if name in FULL_RACKS:
        assert caps == ["Fracture_03", "Fracture_04", "Fracture_05", "Fracture_06"], (name, caps)
        assert {f"{c}-{FR.CUT_MATERIAL}{FR.SUBPART_SUFFIX}" for c in caps} <= set(integration.standin_parts(man))
    else:
        rep = read_json(config.REPORT_PATH)["blocks"][name]["subparts"]["models"][SIDE]["bounds_local"]
        cols = [z for z in man["fractured"]["zones"] if z["id"] in ("Fracture_03", "Fracture_04")]
        assert all(z["lo"][2] <= rep[0][2] + 1e-3 and rep[1][2] <= z["hi"][2] + 1e-3 for z in cols), (name, rep)
        assert caps == [], (name, caps)
