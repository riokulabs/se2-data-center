"""Rack door variants (split front; split front + rear), the tray fans and the hum.

Geometry tests read build_report.json (the Blender build measures the built leaf models: plan hull + z span per
leaf model); definition tests read the staged integration package (integration.write_all)."""
import json
import os

import pytest

from dc import catalog, clone, config, doors, fracture, integration
from dc import dims as DM
from dc.assetio import read_json

DOOR_RACKS = ("DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear", "DC_Rack24_SplitFront", "DC_Rack24_SplitFrontRear")
FULL_RACKS = ("DC_Rack42_Open", "DC_Rack42_SplitFront", "DC_Rack42_SplitFrontRear")
SERVER_FRONT_HARDWARE = DM.SLOT_FRONT_Y + 0.06     # server ears / handles reach <= 6 cm past the slot


def _entry(name):
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        e = json.load(f)["blocks"][name]
    assert e["placement"]["total"] > 0, f"{name}: not built"
    assert "doors" in e, f"{name}: no door data in build_report.json (rebuild)"
    return e


def _hulls(e):
    return {m: [tuple(p) for p in h] for m, h in e["doors"]["hulls"].items()}


@pytest.fixture(scope="module")
def staged(stage_package):
    stage_package()
    return integration.STAGE


def _staged(rel):
    """A definition as the install will leave it: the staged copy, else the mod's (unchanged by this package)."""
    return integration.read_current(rel)


def _files(name, pattern):
    out = set()
    for base in (config.STAGE_ASSETS, config.MOD_ASSETS):
        root = os.path.join(base, config.NAME, name)
        out |= {os.path.relpath(os.path.join(dp, f), base) for dp, _, fs in os.walk(root)
                for f in fs if pattern in f and f.endswith((".def", ".partialdef"))}
    return sorted(out)


def _dummies(name):
    info = clone.entry(catalog.BY_NAME[name])["info"]
    m = _staged(info["model_def_file"])["$Value"]["Manipulator"]
    return {c["Value"]["Name"]: c["Value"] for c in m["Dummies"]["Changed"]}


# ------------------------------------------------------------------------------------------------ geometry
def test_leaf_layout_numbers():
    """The layout is re-derived for this rack: 1.0 m wide, the frame's front plane at 0.598 (keep-out), the leaves
    in the 2.3 cm layer in front of it; the two leaves meet at the centre; each is half the opening."""
    assert DM.DOOR_Y_BACK > 0.598 and DM.DOOR_Y_FRONT < 0.625
    assert DM.DOOR_KNUCKLE_R <= DM.DOOR_HALF_T + 1e-9
    # the two leaves (axis to free edge, plus the meeting gap each) span exactly the opening between the hinge axes
    assert 2 * (DM.DOOR_W + DM.DOOR_MEET_GAP) == pytest.approx(2 * DM.DOOR_AXIS_X)
    assert 0.45 < DM.DOOR_W < 0.5
    assert DM.DOOR_OPEN_DEG <= 85.0


@pytest.mark.build
@pytest.mark.parametrize("name", DOOR_RACKS)
def test_doors_closed_inside_footprint(name):
    spec = catalog.BY_NAME[name]
    e = _entry(name)
    boxes = doors.closed_boxes(spec, _hulls(e), {m: tuple(z) for m, z in e["doors"]["z"].items()})
    assert len(boxes) == 2 * len(doors.door_sides(spec))
    nx, ny, nz = spec.cells
    hx, hy, hz = 0.125 * nx - DM.RACK_SIDE_INSET, 0.125 * nz, 0.125 * ny
    for leaf, (lo, hi) in boxes.items():
        assert -hx <= lo[0] and hi[0] <= hx, (leaf, lo, hi)
        assert -hy < lo[1] and hi[1] < hy, (leaf, lo, hi)
        assert -hz <= lo[2] and hi[2] <= hz, (leaf, lo, hi)
        # in the front / rear zone, in front of the frame (0.598) and of every server's front hardware
        near = min(abs(lo[1]), abs(hi[1]))
        assert near >= 0.598 and near > SERVER_FRONT_HARDWARE, (leaf, lo, hi)


@pytest.mark.build
@pytest.mark.parametrize("name", DOOR_RACKS)
def test_neighbour_clearance(name):
    """Two of these racks flush side by side (centres 1.0 m apart: the racks are 4 cells wide, not v2's 0.75 m), every
    leaf at the 85 deg cap: the leaves of one rack never reach the other's. Also checked through the whole swing."""
    spec = catalog.BY_NAME[name]
    e = _entry(name)
    hulls = _hulls(e)
    d, pair = doors.neighbour_clearance(spec, hulls, 1.0)
    assert d > 0.005, (d, pair)
    assert e["doors"]["clearance_m"] == pytest.approx(round(d, 5), abs=1e-5)
    for k in range(11):
        assert doors.neighbour_clearance(spec, hulls, k / 10)[0] > 0, k
    assert e["doors"]["max_clear_deg"] >= DM.DOOR_OPEN_DEG


@pytest.mark.build
@pytest.mark.parametrize("name", DOOR_RACKS)
def test_door_sweep_clear_of_frame_and_opening(name):
    """Through the swing no leaf point enters the frame (|y| < 0.598) or crosses the side plane; open, the leaves
    leave the 2-cell slot face clear (KVM pop-out, the UPS's rear cell bay)."""
    spec = catalog.BY_NAME[name]
    for leaf, s in doors.sweep_report(spec, _hulls(_entry(name))).items():
        assert s["min_abs_y"] >= 0.5985, (leaf, s)
        assert s["max_abs_x"] <= 0.5 - DM.RACK_SIDE_INSET, (leaf, s)
        assert s["open_inner_abs_x"] >= DM.SLOT_HALF_W + 0.1, (leaf, s)


@pytest.mark.build
@pytest.mark.parametrize("name", DOOR_RACKS)
def test_leaf_models_within_limits(name):
    e = _entry(name)
    models = e["subparts"]["models"]
    assert set(doors.leaf_models(catalog.BY_NAME[name])) <= set(models)
    for m, r in models.items():
        for i, row in enumerate(r["lods"]):
            assert row["tris"] <= row["max_tris"], (m, i, row)
            assert row["materials"] <= row["max_materials"], (m, i, row)


@pytest.mark.build
@pytest.mark.parametrize("name", FULL_RACKS)
def test_full_racks_have_fans(name):
    e = _entry(name) if name != "DC_Rack42_Open" else json.load(open(config.REPORT_PATH))["blocks"][name]
    assert {doors.FAN, doors.FAN_TRAY_SUB} <= set(e["subparts"]["models"])
    assert len(doors.fan_points(catalog.BY_NAME[name])) == 2


# ------------------------------------------------------------------------------------------------ definitions
@pytest.mark.parametrize("name", DOOR_RACKS)
def test_door_open_angle(staged, name):
    """Every leaf's closed and open dummies share the hinge point and differ by a yaw of exactly the 85 deg cap."""
    spec = catalog.BY_NAME[name]
    dm = _dummies(name)
    lv = doors.leaves(spec)
    assert len(lv) == 2 * len(doors.door_sides(spec))
    for lf in lv:
        c, o = dm[lf["name"] + "Closed"], dm[lf["name"] + "Open"]
        tc, to = c["Transform"]["Transform"], o["Transform"]["Transform"]
        assert tc["Position"] == to["Position"], lf["name"]
        q0 = tuple(tc["Orientation"][k] for k in "XYZW")
        q1 = tuple(to["Orientation"][k] for k in "XYZW")
        ang = doors.quat_angle(q0, q1)
        assert ang <= DM.DOOR_OPEN_DEG + 1e-4 and ang >= DM.DOOR_OPEN_DEG - 1e-4, (lf["name"], ang)
        assert sum(a * b for a, b in zip(q0, q1)) > 0, "slerp must take the short way"
    # the vanilla frame UseDoor boxes are gone (they would sit in front of the servers' terminals when open)
    assert not {"TerminalFront01", "TerminalBack01"} & set(dm)


@pytest.mark.parametrize("name", DOOR_RACKS)
def test_door_leaf_definitions_wired(staged, name):
    """ConditionalSubParts: each leaf's closed dummy type -> its own client prefab; the prefab's SLERP definition
    reads that leaf's closed / open dummy types; its ModelComponent points at our leaf model with a UseDoor box."""
    spec = catalog.BY_NAME[name]
    dm = _dummies(name)
    cs = _staged(_files(name, "_Client_ConditionalSubPartsDefinition")[0])["$Value"]["SubParts"]
    lv = doors.leaves(spec)
    # the leaves plus the bound side panel and (full racks) fan tray entries (test_rack_states)
    assert len(cs) == len(lv) + (2 if name in FULL_RACKS else 1), cs
    for lf in lv:
        closed_t = dm[lf["name"] + "Closed"]["Type"]
        open_t = dm[lf["name"] + "Open"]["Type"]
        prefab = cs[closed_t]
        cl = [f for f in _files(name, f"_{lf['name']}_Client.def")]
        assert len(cl) == 1, (lf["name"], cl)
        pf = _staged(cl[0])["$Value"]
        assert pf["Guid"] == prefab
        slerp = _staged(_files(name, f"_{lf['name']}_Client_DoorSegmentTransformSLERPDefinition")[0])["$Value"]
        assert (slerp["ClosedPositionDummy"], slerp["OpenPositionDummy"]) == (closed_t, open_t)
        mc = _staged(_files(name, f"_{lf['name']}_Client_ModelComponentDefinition")[0])["$Value"]
        mrel = f"{config.NAME}/{name}/Models/Subparts/{lf['model']}/{name}_{lf['model']}.model"
        assert mc["Model"] == "{G}" + integration.asset_id(mrel), lf["name"]
        assert [d["Value"]["Type"] for d in mc["Dummies"]] == [integration.USE_DOOR]
    # the cloned frame panels' fracture names are replaced by ours: the critical zones are the two side columns
    # (they carry the hinges), checked on the exported zone boxes, not on the names' order
    br = _staged(_files(name, "_BreakableBlockDefinition")[0])["$Value"]["Manipulator"]
    crit = [f["Id"] for f in br["CriticalFractures"]["Added"]]
    zones = {z["id"]: z for z in read_json(os.path.join(config.MODELS_DIR, name, "export.json"))["fractured"]["zones"]}
    # the columns are shaped to their members (fracture.shaped_hull) and, on the full rack, cut in a lower
    # and an upper half: every critical zone lies beside the slot out to the side plane over the full depth, and on
    # each side they stack up to the slot band's height
    assert len(crit) == (4 if catalog.BY_NAME[name].cells[1] == 10 else 2)
    span = {-1: 0.0, 1: 0.0}
    for zid in crit:
        (x0, y0, z0), (x1, y1, z1) = zones[zid]["lo"], zones[zid]["hi"]
        assert x0 * x1 >= 0 and min(abs(x0), abs(x1)) >= DM.SLOT_HALF_W - 0.02, (zid, x0, x1)   # beside the slot
        assert max(abs(x0), abs(x1)) >= 0.5 - 0.005                    # out to the side skins (the render's 2.5 mm)
        # depth: from the PDU bracket plane (the rear PDU column is free) to the front plane
        assert y1 - y0 >= 0.625 + DM.SLOT_HALF_D - 0.005, (zid, y0, y1)
        span[1 if x0 > 0 else -1] += z1 - z0
    for sx, h in span.items():
        assert h >= 0.25 * catalog.BY_NAME[name].cells[1] - 0.5, (sx, h)


@pytest.mark.parametrize("name", DOOR_RACKS)
def test_door_timing_and_detector(staged, name):
    srv = _staged(_files(name, "_DoorServerDefinition")[0])["$Value"]["Manipulator"]
    assert srv["OpeningDuration"] == int(DM.DOOR_SECONDS * 1e7)
    det = _staged(_files(name, "_DoorwayObstacleEntityDetectorDefinition")[0])["$Value"]["Manipulator"]
    c, half = doors.detector_box(catalog.BY_NAME[name])
    assert [det["QueryHalfExtents"][k] for k in "XYZ"] == list(half)
    assert list(_dummies(name)["DoorwayObstructionDetector"]["Transform"]["Transform"]["Position"].values()) == list(c)


@pytest.mark.parametrize("name", FULL_RACKS)
def test_fan_subparts(staged, name):
    """Every full rack: the rotors are InfiniteRotation subparts, children of the fan tray's CLIENT prefab
    (never an unbound ConditionalSubParts entry, which the door's server walk would reach: see
    test_conditional_subparts_are_bound and Tests/test_clientserver_walk.py), spun while Working by the rack's
    FunctionalBlockAnimationController: the door racks', and the open rack's (the powerable functional chain gives
    it Working); none on the block's own client prefab."""
    rot = _staged(_files(name, "RackFan_InfiniteRotationAnimationDefinition")[0])["$Value"]
    assert rot["RotationAxis"] == {"X": 0, "Y": 1, "Z": 0} and rot["AngularSpeed"] > 0
    comp = _staged(_files(name, "RackFan_Composite")[0])["$Value"]["Manipulator"]
    assert any(c["Value"].get("Type", "").endswith("InfiniteRotationAnimationComponent")
               for c in comp["Components"]["Changed"] if c["Kind"] == "Insert")
    cc = _staged(_files(name, "_ClientComposition")[0])["$Value"]["Manipulator"]
    types = [c["Value"].get("Type") for c in cc["Components"]["Changed"] if c["Kind"] == "Insert"]
    assert integration.T_ANIMCTL in types
    tray = _staged(_files(name, f"_{doors.FAN_TRAY_SUB}.partialdef")[0])["$Value"]["Manipulator"]["_entity"]
    hier = [c for c in tray["ObjectBuilders"]["Changed"] if c["Kind"] == "Update"
            and c["Value"].get("$Type", "").endswith("HierarchyComponentObjectBuilder")]
    kids = [c["Value"] for c in hier[0]["Value"]["Children"]["Changed"]]
    fan_comp = _staged(_files(name, "RackFan_Composite")[0])["$Value"]["Manipulator"]["Guid"]
    assert len(hier) == 1 and [k["Definition"] for k in kids] == [fan_comp, fan_comp]
    assert all(len(k["ObjectBuilders"]) == len(integration.SUBPART_TEMPLATE_KEYS) + 1 for k in kids)
    cl = _staged(_files(name, "_Client.partialdef")[0])["$Value"]["Manipulator"]["_entity"]["ObjectBuilders"]
    assert not [c for c in cl["Changed"] if isinstance(c["Value"], dict)
                and c["Value"].get("$Type", "").endswith("HierarchyComponentObjectBuilder")]


@pytest.mark.parametrize("name", DOOR_RACKS + ("DC_Srv_KVM",))
def test_hum_while_working(staged, name):
    """A vanilla loop plays while Working (BlockEffectsComponent.OnUseAudio): the racks' fans, the KVM's hum. The
    other functional servers keep the loop their vanilla templates already have (Timer / Battery50:
    BatteriesInsertRemove, EventController: UI/OreDetector, LCD50: Block/LCD); ControlPanel25 had none."""
    want = integration.HUM_RACK if name.startswith("DC_Rack") else integration.HUM_SERVER
    files = _files(name, "BlockEffectsComponentDefinition")
    assert files, name
    vals = [_staged(f)["$Value"].get("Manipulator", {}).get("OnUseAudio") for f in files]
    assert want in vals, (name, vals)
    cc = _staged(_files(name, "_ClientComposition")[0])["$Value"]["Manipulator"]
    keys = cc["Components"]["Keys"]
    hum = [_staged(f)["$Value"]["Manipulator"]["Guid"] for f, v in zip(files, vals) if v == want][0]
    assert any(isinstance(c["Value"], dict) and c["Value"].get("Definition") == hum
               for c in cc["Components"]["Changed"]), name


@pytest.mark.parametrize("name", DOOR_RACKS)
def test_power_lamp_swapped_while_working(staged, name):
    """The rack's label lamp is EmissiveOff in the model and the cloned material swapper lights it (EmissiveGreen)
    while Working, on our models (the vanilla door's models and mesh parts are gone)."""
    from dc.material_guids import guid
    sw = _staged(_files(name, "_BlockMaterialSwapperDefinition")[0])["$Value"]
    models = {integration.asset_id(f"{config.NAME}/{name}/Models/NonFractured/{name}.model"),
              integration.asset_id(f"{config.NAME}/{name}/Models/Fractured/{name}_Fractured.model")}
    assert {r[3:] for r in sw["WorkingReplacementModels"]} == models
    parts = {p["$Key"]: p["$Value"] for p in sw["WorkingReplacementsMeshParts"]}
    assert parts and all(k.endswith("EmissiveOff") for k in parts) and set(parts.values()) == {guid("EmissiveGreen")}


@pytest.mark.path_a
@pytest.mark.parametrize("name", FULL_RACKS)
def test_fan_tray_follows_build(staged, name):
    """No always-present static tray: the fan tray (plate, housings, guards)
    is a bound ConditionalSubParts entry spawned with the rack Functional; below that its LOD1 stand-in, baked into the
    Fractured / Damaged models, fills the fan lane (the lane never shows bare floor openings). The rotors are never an
    entry of their own (they ride on the tray)."""
    cs = [_staged(f)["$Value"] for f in _files(name, "ConditionalSubPartsDefinition")]
    assert len(cs) == 1, name
    tray_pf = _staged(_files(name, f"_{doors.FAN_TRAY_SUB}.partialdef")[0])["$Value"]["Manipulator"]["Guid"]
    fan_pf = _staged(_files(name, f"_{doors.FAN}.partialdef")[0])["$Value"]["Manipulator"]["Guid"]
    assert tray_pf in cs[0]["SubParts"].values() and fan_pf not in cs[0]["SubParts"].values()
    assert any(s.subpart == doors.FAN_TRAY_SUB for s in fracture.STANDINS[name])


CS_TYPE = "ConditionalSubPartsDefinitionObjectBuilder"
PROVIDER_TYPE = "DoorPartsProviderDefinitionObjectBuilder"


def _door_conditional_defs(name):
    """The block's ConditionalSubParts definitions that a DoorPartsProvider references (the door's server walk follows
    those: in-game fix 028c1172), as package-relative paths. A ConditionalSubParts referenced only by a client
    composition (the KVM's drawer, the CRAC's fan rotor) is not walked by the server and is not subject to the rule."""
    defs = {}
    for rel in _files(name, ".def"):
        try:
            d = integration.read_current(rel)
        except Exception:   # noqa: BLE001 (a non-JSON file is not a definition)
            continue
        defs[rel] = d
    cs = {rel: d["$Value"]["Guid"] for rel, d in defs.items() if d.get("$Type", "").endswith(CS_TYPE)}
    prov = [json.dumps(d) for d in defs.values() if d.get("$Type", "").endswith(PROVIDER_TYPE)]
    return sorted(rel for rel, g in cs.items() if any(g in p for p in prov))


def _conditional_blocks():
    """Every catalogue block with a door-walked ConditionalSubParts definition: the door racks, the room's
    containment doors (vanilla SlidingDoor clones) and any later door-like block."""
    return [b.name for b in catalog.CATALOGUE if _door_conditional_defs(b.name)]


CONDITIONAL_BLOCKS = _conditional_blocks()


def test_conditional_subparts_cover_door_like_blocks():
    """The rule below runs on every door-like block, not only the racks: the four door
    racks and the three containment doors at least."""
    want = set(DOOR_RACKS) | {b.name for b in catalog.CATALOGUE if b.name.startswith("DC_Contain_Door_")}
    assert len(want) >= 7
    assert want <= set(CONDITIONAL_BLOCKS), sorted(want - set(CONDITIONAL_BLOCKS))


@pytest.mark.parametrize("name", CONDITIONAL_BLOCKS)
def test_conditional_subparts_are_bound(staged, name):
    """The door's DoorPartsProvider (server) references the ConditionalSubParts definition, so the game's server walk
    (BindingsBasedClientServerInfo) follows every prefab in it unless it is a bound client prefab. An unbound one (the
    rotors, 2026-10-18) puts client render components on a "server" composition and ConveyorGraphPostProcessor fails
    the world load. Every entry of every door-walked ConditionalSubParts definition must be some PrefabBinding's
    ClientPrefab (door racks, containment doors, any door-like block)."""
    bound = set()
    for rel in _files(name, ".def"):
        v = _staged(rel)["$Value"]
        v = v.get("Manipulator", v) if isinstance(v, dict) else v
        if isinstance(v, dict) and "ServerComposite" in v and "ClientPrefab" in v:
            bound.add(v["ClientPrefab"])
    for rel in _door_conditional_defs(name):
        cs = _staged(rel)["$Value"]["SubParts"]
        assert cs and set(cs.values()) <= bound, (name, rel, set(cs.values()) - bound)


@pytest.mark.parametrize("name", FULL_RACKS)
def test_fan_tray_static_and_rotors_spin(staged, name):
    """The fan tray (housings, guards, leads, lamps) is a STATIC subpart (the plain Subpart composite, no rigid
    animation); the rotors stay InfiniteRotation about game +Y, and each rotor sits inside its housing below the guard."""
    comp = _staged(_files(name, f"{doors.FAN_TRAY_SUB}_Composite")[0])["$Value"]["Manipulator"]
    assert all(c["Kind"] == "Update" for c in comp["Components"]["Changed"])
    assert "TagSlots" not in comp
    rot = _staged(_files(name, f"{doors.FAN}_InfiniteRotationAnimationDefinition")[0])["$Value"]
    assert rot["RotationAxis"] == {"X": 0, "Y": 1, "Z": 0}
    spec = catalog.BY_NAME[name]
    t = doors.fan_tray_point(spec)
    L = doors.FAN_TRAY
    for p in doors.fan_points(spec):
        hub = p[2] - t[2]
        assert L["plate_t"] < hub < L["plate_t"] + L["housing_h"]
        assert hub + doors.FAN_CAN_TOP <= L["plate_t"] + L["housing_h"] + 0.006 + 1e-9


@pytest.mark.build
@pytest.mark.parametrize("name", DOOR_RACKS)
def test_leaf_and_handle_inside_layer(name):
    """The recessed handle (escutcheon, L-handle, key, stripes) adds nothing outside the 23 mm leaf layer and
    stays short of the meeting edge."""
    e = _entry(name)
    for m, h in e["doors"]["hulls"].items():
        ys = [p[1] for p in h]
        assert -DM.DOOR_HALF_T - 1e-6 <= min(ys) and max(ys) <= DM.DOOR_HALF_T + 1e-6, (m, min(ys), max(ys))
        xs = [abs(p[0]) for p in h]
        assert max(xs) <= DM.DOOR_W + 1e-6, (m, max(xs))


def _qrot(q, v):
    """VRage Vector3.Transform(v, q) for a unit quaternion (x, y, z, w)."""
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


@pytest.mark.parametrize("name", DOOR_RACKS)
def test_staged_swing_direction(staged, name):
    """Pins the swing direction on the STAGED dummies: the leaf model's free-edge point (game axes: the leaf extends
    -s * DOOR_W in x from its hinge, s = +1 for DoorLeafR) turned by the staged open quaternion and placed at the
    staged hinge ends outside the rack: front leaves at game z < -0.625 (game -Z = Forward), rear leaves at z > 0.625.
    Closed, the same point lies on the rack's centre line inside the door layer."""
    dm = _dummies(name)
    for lf in doors.leaves(catalog.BY_NAME[name]):
        s = 1 if lf["model"] == doors.LEAF_R else -1
        edge = (-s * DM.DOOR_W, 0.0, 0.0)
        for kind in ("Closed", "Open"):
            t = dm[lf["name"] + kind]["Transform"]["Transform"]
            q = tuple(t["Orientation"][k] for k in "XYZW")
            p = [t["Position"][k] for k in "XYZ"]
            r = _qrot(q, edge)
            gx, gz = p[0] + r[0], p[2] + r[2]
            if kind == "Closed":
                assert abs(gx - doors.shift(catalog.BY_NAME[name])[0]) < 0.003, (lf["name"], gx)
                assert 0.598 < abs(gz) < 0.625, (lf["name"], gz)
            elif lf["sy"] > 0:
                assert gz < -0.625, (lf["name"], gz)
            else:
                assert gz > 0.625, (lf["name"], gz)
