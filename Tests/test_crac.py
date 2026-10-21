"""The in-row cooler DC_CRAC (dc/crac.py): a powered load.

Pure tests check the builder's numbers (footprint, collision and hints against the full rack's, the fan pivots and the
InfiniteRotation ramp, the fracture plan). Build-marked tests read the MEASURED block (build_report.json: geometry,
placement, LODs) and its export (Models/DC_CRAC/export.json); the staged tests read the integration package
(integration.write_all): a powered load with On/Off and no gyroscope, three CracFan rotors spun while Working, the RUN
lamp swapped on our model's slot, breakable with its own Damaged model.
"""
import json
import math
import os

import pytest

from dc import catalog, clone, config, crac, integration, names, rack
from dc import dims as DM
from dc import fracture as FR
from dc.assetio import body, read_json

NAME = "DC_CRAC"
SPEC = catalog.BY_NAME[NAME]
FULL = "DC_Rack42_SplitFront"
MM = 0.001
T_POWERABLE_DEF = "Game2:Keen.Game2.Simulation.WorldObjects.CubeBlocks.PowerableBlockDefinition"


def _report():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _entry(name=NAME):
    e = _report().get(name, {})
    if not e.get("placement", {}).get("total"):
        pytest.skip(f"{name} not built")
    return e


def _manifest():
    p = os.path.join(config.MODELS_DIR, NAME, "export.json")
    if not os.path.exists(p):
        pytest.skip(f"{NAME} not exported yet")
    return read_json(p)


@pytest.fixture(scope="module")
def staged(stage_package):
    stage_package()
    return integration.STAGE


def _staged(rel):
    return integration.read_current(rel)


def _files(pattern):
    out = set()
    for base in (config.STAGE_ASSETS, config.MOD_ASSETS):
        root = os.path.join(base, config.NAME, NAME)
        out |= {os.path.relpath(os.path.join(dp, f), base) for dp, _, fs in os.walk(root)
                for f in fs if pattern in f and f.endswith((".def", ".partialdef"))}
    return sorted(out)


def _built_and_exported():
    if NAME not in integration.built_names() or not os.path.exists(os.path.join(config.MODELS_DIR, NAME, "export.json")):
        pytest.skip(f"{NAME} not built and exported")


# ---------------------------------------------------------------------------------------------------- pure
def test_crac_catalogue_and_staging():
    assert SPEC.family == "crac" and SPEC.cells == (4, 10, 5) and SPEC.copy_from == "Gyroscope250"
    assert "crac" in catalog.STAGED_ROOM_FAMILIES and SPEC in catalog.STAGED and SPEC in catalog.BLOCKS   # in menu
    assert (crac.H, crac.ZT) == DM.rack_frame(10)[:2]
    assert names.NAMES[NAME][0] == "In-Row Cooler (CRAC)"


def test_crac_collision_and_hints():
    """Physics: plinth, body, top band (<= 4 boxes, every cell). The hints are the full rack's without the slot's:
    the same sides, bottom, top rims and containment-rail band (contain_front / back), box for box."""
    c = crac.collision(SPEC)
    assert len(c["regular"]) <= 4 and not c["occupancy"]
    vol = sum((hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]) for _, lo, hi in c["regular"])
    assert vol == pytest.approx(1.0 * 1.25 * 2.5)
    rk = {n: (lo, hi) for n, lo, hi in rack.collision(catalog.BY_NAME[FULL])["mount"]}
    mine = {n: (lo, hi) for n, lo, hi in c["mount"]}
    want = ("side_left", "side_right", "bottom", "rim_front", "rim_back", "rim_left", "rim_right", "contain_front",
            "contain_back")
    assert sorted(mine) == sorted(want)
    for n in want:
        assert [*mine[n][0], *mine[n][1]] == pytest.approx([*rk[n][0], *rk[n][1]]), n


def test_crac_fan_points_and_ramp():
    """Three rotor pivots stacked on the door's centre line, inside their module's orifice; the InfiniteRotation
    turns them about the forward axis (game +Z) at 600 deg/s with a 2 s soft start and a 4 s coast."""
    pts = crac.fan_points(SPEC)
    assert len(pts) == 3 and all(p[0] == 0.0 and p[1] == crac.ROTOR_Y for p in pts)
    zs = [p[2] + crac.H / 2 for p in pts]
    assert zs == pytest.approx(list(crac.FAN_ZC)) and all(b - a == pytest.approx(0.52) for a, b in zip(zs, zs[1:]))
    assert crac.ROTOR_R[1] + 0.008 <= crac.ORIFICE_R and crac.MOD_Y[0] < crac.ROTOR_Y < crac.GUARD_Y[0]
    a = integration.crac_fan_anim()
    assert a["RotationAxis"] == {"X": 0, "Y": 0, "Z": 1}
    assert (a["AngularSpeed"], a["AngularSpeedup"], a["AngularSlowdown"]) == (600.0, 300.0, 150.0)
    assert a["AngularSpeed"] / a["AngularSpeedup"] == 2.0 and a["AngularSpeed"] / a["AngularSlowdown"] == 4.0
    # (7 blades: at 60 fps a frame turns 10 deg, at 30 fps 20 deg, both under half the 51 deg blade pitch: no strobing)
    assert 600.0 / 30 < 0.5 * 360 / 7


def test_crac_fracture_plan():
    """Guide 10.3 (3): a critical coil core with every other zone its neighbour, three critical fan sections (their
    rotors only despawn when the block stops being Functional), shell plates for the controller, the filter door
    halves, the plinth and the top band: 9 zones (the guide's 8-12 at 2.5 m, Keen allows 15). The fans' and the
    terminal's dummies are supported by their zones; health (box volume, criticals x 2) keeps every zone >= 4 % and the
    core under 70 %; the criticals stay in the largest island whatever single zone dies."""
    p = FR.plan(SPEC, crac.collision(SPEC))
    ids = p.ids()
    assert ids == [f"Fracture_{i:02d}" for i in range(1, 10)] and len(ids) <= FR.max_fractures((1.0, 1.25, 2.5))
    assert p.critical() == ids[:4] and p.zones[0].label.startswith("coil core")
    sup = p.manifest()["supporting"]
    assert sup == {"CracFan1": "Fracture_02", "CracFan2": "Fracture_03", "CracFan3": "Fracture_04",
                   crac.TERMINAL_DUMMY: "Fracture_05",
                   "conveyor_port_o2_1": "Fracture_06", "conveyor_port_o2_2": "Fracture_06"}   # the service bay
    hulls = [z.hull for z in p.zones]

    def touch(a, b):
        return max(max(a[0][i], b[0][i]) - min(a[1][i], b[1][i]) for i in range(3)) <= 0.1

    assert all(touch(hulls[0], h) for h in hulls[1:])          # the core touches every zone
    crit = set(range(4))
    vol = [(h[1][0] - h[0][0]) * (h[1][1] - h[0][1]) * (h[1][2] - h[0][2]) * (2 if i in crit else 1)
           for i, h in enumerate(hulls)]
    sh = [v / sum(vol) for v in vol]
    assert min(sh) >= 0.04 and max(sh) == sh[0] < 0.70, sh

    def islands(alive):
        left, out = set(alive), []
        while left:
            todo, comp = [left.pop()], set()
            while todo:
                i = todo.pop()
                comp.add(i)
                for j in [j for j in left if touch(hulls[i], hulls[j])]:
                    left.discard(j)
                    todo.append(j)
            out.append(comp)
        return out
    for dead in range(len(hulls)):
        big = max(islands([i for i in range(len(hulls)) if i != dead]), key=lambda c: sum(vol[i] for i in c))
        assert crit - {dead} <= big, dead
    # every seam on a joint: the door rails between the fan modules, the controller's shadow gap, the grille's rail
    for z in crac.SEAM_Z[:2]:
        assert all(abs(z - zc) >= crac.MOD_HALF + 0.004 for zc in crac.FAN_ZC)
    assert crac.DOOR_Z[1] < crac.SEAM_Z[2] < crac.CTRL_Z[0]
    assert any(b0 < crac.SEAM_Z[3] < a1 for (_, b0), (a1, _) in zip(crac.REAR_Z, crac.REAR_Z[1:]))


# ---------------------------------------------------------------------------------------------------- measured
@pytest.mark.build
def test_crac_shares_rack_interface():
    """The rack's room interface, measured: the same cells; both sides mount (>= 50 %); the containment rails equal
    the full rack's within 1 mm (the roof clamps onto either); the bottom and top-rim mount rects and the front
    brush plates (a Drop feeds either) equal the rack's."""
    e, r = _entry(), _entry(FULL)
    g, rg = e["geometry"], r["geometry"]
    assert tuple(SPEC.cells) == (4, 10, 5) and e["placement"]["occupied"] == e["placement"]["total"] == 200
    f = e["placement"]["faces"]
    assert f["Left"]["coverage"] >= 0.5 and f["Right"]["coverage"] >= 0.5
    for side in ("front", "back"):
        assert g["contain_rails"][side] == pytest.approx(rg["contain_rails"][side], abs=MM), side
    flat = lambda rs: [c for r in sorted(rs) for c in r]   # noqa: E731
    assert flat(g["down_mount_rects"]) == pytest.approx(flat(rg["down_mount_rects"]))
    assert flat(g["up_mount_rects"]) == pytest.approx(flat(rg["up_mount_rects"]))
    assert flat(g["top_entries"]) == pytest.approx(flat(rg["top_entries"]), abs=MM)


@pytest.mark.build
def test_crac_faces_and_limits():
    """Front and back mount only on the rail band (one group, 10 %), the sides fully, Up on the rims; Keen's limits on
    every LOD of the cabinet and the rotor, <= 8 materials (the RUN lamp's EmissiveOff among them), LOD0 <= 90 % of
    Keen's (the project cap; the 597f7c6e machine interior took it to 98 %, the solid core brought it back), the last
    LOD a 12-tri box; 3 physics boxes; no bevel hazard."""
    e = _entry()
    f = e["placement"]["faces"]
    for d in ("Forward", "Backward"):
        assert f[d]["groups"] == 1 and f[d]["coverage"] == pytest.approx(0.1), d
    assert f["Left"]["coverage"] == f["Right"]["coverage"] == 1.0 and f["Down"]["coverage"] == 1.0
    for i, l in enumerate(e["lods"]):
        assert l["tris"] <= l["max_tris"] and l["materials"] <= min(8, l["max_materials"]), i
    assert e["lods"][0]["tris"] <= 0.90 * e["lods"][0]["max_tris"]
    assert crac.LAMP in e["lods"][0]["material_names"] and "MetalPerforationSteel" in e["lods"][0]["material_names"]
    assert e["lods"][-1]["tris"] == 12 and e["colliders"]["regular"] == 3 and not e["bevel_guard"]
    rows = e["subparts"]["models"][crac.FAN]["lods"]
    for i, l in enumerate(rows):
        assert l["tris"] <= l["max_tris"] and l["materials"] <= min(8, l["max_materials"]), i


@pytest.mark.build
def test_crac_render_mesh_and_fans():
    """The render mesh stays in its cell box; outside the rail band nothing reaches the front / back planes past the
    rack's keep-out (rack.YK); the blind flanges' bolt heads end 1 mm under the top plane; each rotor turns inside its
    orifice (>= 8 mm tip clearance) and >= 20 mm behind the guard."""
    e = _entry()
    g = e["geometry"]
    (x0, y0, z0), (x1, y1, z1) = e["render_bounds"]
    assert -0.5 <= x0 and x1 <= 0.5 and -0.625 <= y0 and y1 <= 0.625 and -1.25 <= z0 and z1 <= 1.25
    assert g["side_max_x"] <= rack.XO + 1e-6 and g["bottom_z"] >= -crac.H / 2 - 1e-6 and g["top_z"] <= crac.H / 2
    assert g["front_max_y"] <= rack.YK + 1e-6 and g["back_min_y"] >= -rack.YK - 1e-6
    assert g["flange_top_z"] == pytest.approx(crac.H / 2 - 0.001, abs=2e-4)
    assert len(g["fans"]) == 3
    for fan in g["fans"]:
        assert fan["tip_clear"] >= 0.008 and fan["guard_clear"] >= 0.020, fan
        assert fan["rotor_y"][0] > crac.MOD_Y[0]


@pytest.mark.build
def test_crac_breakable_export():
    """Through the shared pipeline (dc/fracture.py _crac; recognition, connectivity, cap UVs, hull fill and the
    Damaged parity are test_fracture_refine.py's, on the files): the plan's 9 zones cut and capped (every zone has
    FracturedMaterial01 break faces but the jointed plinth / top band), 01-04 critical, the fans and the terminal supported, its own dented Damaged
    model; the RUN lamp is in the controller zone's _Hide group; the CracFan rotor exported as a subpart. The plinth
    and the top band have no break faces: the cabinet stands on the one and carries the other at bolted joints (closed
    both sides, as the rack's plinth and tray), so no member crosses their seams."""
    m = _manifest()
    p = FR.plan(SPEC, crac.collision(SPEC))
    zones = [z["id"] for z in m["fractured"]["zones"]]
    assert zones == p.ids() and m["fractured"]["kind"] == "cut" and m["fractured"]["critical"] == p.critical()
    assert m["fractured"]["supporting"] == p.manifest()["supporting"]
    parts = m["fractured"]["parts"]
    for z in zones:   # (the plinth and the top band meet the body at bolted joints: nothing crosses those seams)
        assert (f"{z}-FracturedMaterial01" in parts) == (z not in ("Fracture_08", "Fracture_09")), z
    assert "Fracture_05_Hide-EmissiveOff" in parts
    assert integration.keeps_breakable(m)
    dm = m["damaged"]
    assert sorted(dm["collision"]["nodes"]) == sorted(zones)
    assert 4.0 <= dm["dent"]["mean_mm"] <= 15.0 and dm["dent"]["max_mm"] <= 50.0
    assert m["subparts"][crac.FAN]["lods"]


# ---------------------------------------------------------------------------------------------------- staged
@pytest.mark.build
def test_crac_is_powered_load(staged):
    """The resolved block definition is the clone's PowerableBlockDefinition drawing 25 (PCU 30, mounts
    All); the server composition keeps the PowerableBlockComponent and has no GyroscopeComponent (its key Removed,
    its tag slot RemovedKeys), nor does the server prefab; no CRAC file (installed or staged) is a GyroscopeDefinition
    or references one, and the dropped file is gone."""
    _built_and_exported()
    info = clone.entry(SPEC)["info"]
    bd = _staged(info["block_def_file"])
    assert bd["$Value"]["DefinitionType"] == T_POWERABLE_DEF
    m = body(bd)
    assert m["ConsumedResource"]["Amount"] == 25 and m["PCU"] == 30
    assert m["MountPointGeneratorSettings"] == {"Directions": "All"}
    assert m["UIData"]["Name"] == names.NAMES[NAME][0]
    comp = body(_staged(f"{config.NAME}/{NAME}/{NAME}_ServerComposition.partialdef"))
    keys = comp["Components"]["Keys"]
    assert integration.POWERABLE_KEY in keys
    assert integration.GYRO_KEY not in keys and integration.GYRO_KEY in comp["Components"]["Removed"]
    assert integration.GYRO_SLOT in comp["TagSlots"]["RemovedKeys"]
    assert all(i < len(keys) for i in (c["Index"] for c in comp["Components"]["Changed"]))
    pf = body(_staged(f"{config.NAME}/{NAME}/{NAME}_Server.partialdef"))["_entity"]["ObjectBuilders"]
    assert integration.GYRO_KEY not in pf["Keys"] and integration.GYRO_KEY in pf["Removed"]
    for base in (config.STAGE_ASSETS, config.MOD_ASSETS):
        root = os.path.join(base, config.NAME, NAME)
        for dp, _, fs in os.walk(root):
            for f in fs:
                assert not f.endswith("_GyroscopeDefinition.partialdef"), f
                if f.endswith((".def", ".partialdef")):
                    with open(os.path.join(dp, f), encoding="utf-8-sig") as fh:
                        assert integration.T_GYRO_DEF not in fh.read(), f


@pytest.mark.build
def test_crac_fans_spin_on_working(staged):
    """Three CracFan dummies (our dummy type, each supported by its fan section); ConditionalSubParts spawns one rotor
    subpart there (no vanilla gimbal; its hide list: the parked fans baked into the FR / DM); the rotor's
    composite carries an InfiniteRotation about game +Z (0, 0, 1) at 600 deg/s; the FunctionalBlockAnimationController
    (Working) is in both compositions."""
    _built_and_exported()
    info = clone.entry(SPEC)["info"]
    dm = {c["Value"]["Name"]: c["Value"] for c in body(_staged(info["model_def_file"]))["Dummies"]["Changed"]}
    fans = sorted(n for n in dm if n.startswith(crac.FAN))
    assert fans == ["CracFan1", "CracFan2", "CracFan3"] and "RotatingSubpart" not in dm
    types = {dm[n]["Type"] for n in fans}
    assert len(types) == 1
    for i, n in enumerate(fans):
        assert dm[n]["SupportingFracture"] == {"Id": f"Fracture_{i + 2:02d}"}
    cs = body(_staged(_files("SubParts.def")[0]))
    (dt, prefab), = cs["SubParts"].items()
    assert dt in types   # it hides the three parked fans baked into the FR / DM while the rotors run
    assert [x["Value"] for x in cs["MeshPartsToHideWhenActive"]] == integration.standin_parts(_manifest())
    assert len([x for x in cs["MeshPartsToHideWhenActive"] if x["Value"].endswith(FR.SUBPART_SUFFIX)]) >= 3
    dtype = _files(f"{crac.FAN}_DummyTypeDefinition")
    assert len(dtype) == 1 and body(_staged(dtype[0]))["Guid"] == dt
    pf = _staged(_files(f"{NAME}_{crac.FAN}.partialdef")[0])
    assert body(pf)["Guid"] == prefab
    comp = body(_staged(_files(f"{crac.FAN}_Composite")[0]))
    inf = [c["Value"] for c in comp["Components"]["Changed"] if c["Kind"] == "Insert"
           and c["Value"].get("Type", "").endswith("InfiniteRotationAnimationComponent")]
    assert len(inf) == 1
    rot = body(_staged(_files(f"{crac.FAN}_InfiniteRotationAnimationDefinition")[0]))
    assert rot["Guid"] == inf[0]["Definition"]
    assert rot["RotationAxis"] == {"X": 0, "Y": 0, "Z": 1} and rot["AngularSpeed"] == 600
    for side in ("Server", "Client"):
        c = body(_staged(f"{config.NAME}/{NAME}/{NAME}_{side}Composition.partialdef"))
        assert any(isinstance(ch.get("Value"), dict) and ch["Value"].get("Type") == integration.T_ANIMCTL
                   for ch in c["Components"]["Changed"]), side
    mc = body(_staged(_files(f"{crac.FAN}_ModelComponentDefinition")[0]))
    mrel = f"{config.NAME}/{NAME}/Models/Subparts/{crac.FAN}/{NAME}_{crac.FAN}.model"
    assert mc["Model"][3:] == integration.asset_id(mrel)


@pytest.mark.build
def test_crac_status_lamp_swapped(staged):
    """The swapper lights our RUN lamp: its target slot (EmissiveOff) is in our LOD0 materials and every swapped part
    names it (the NonFractured slot and the Fractured model's Fracture_NN_Hide-EmissiveOff parts), on our two models;
    the ALARM lamp (a Yellow lens) is not swapped."""
    _built_and_exported()
    from dc.material_guids import guid
    m = _manifest()
    sw = body(_staged(_files("_BlockMaterialSwapperDefinition")[0]))
    models = {integration.asset_id(f"{config.NAME}/{NAME}/Models/NonFractured/{NAME}.model"),
              integration.asset_id(f"{config.NAME}/{NAME}/Models/Fractured/{NAME}_Fractured.model")}
    assert {r[3:] for r in sw["WorkingReplacementModels"]} == models
    parts = {p["$Key"]: p["$Value"] for p in sw["WorkingReplacementsMeshParts"]}
    assert crac.LAMP in m["nonfractured"]["lods"][0]["materials"]
    assert crac.LAMP in parts and set(parts.values()) == {guid("EmissiveGreen")}
    assert all(k == crac.LAMP or k in m["fractured"]["parts"] for k in parts)
    assert all(k.endswith(crac.LAMP) for k in parts)


@pytest.mark.build
def test_crac_terminal_on_controller(staged):
    """The clone's terminal dummy (On/Off) sits on our controller display, its aim box the display's size, supported
    by the controller zone; the effects origin is the block centre."""
    _built_and_exported()
    from dc import doors
    info = clone.entry(SPEC)["info"]
    dm = {c["Value"]["Name"]: c["Value"] for c in body(_staged(info["model_def_file"]))["Dummies"]["Changed"]}
    t = dm[crac.TERMINAL_DUMMY]
    x, y, z = crac.TERMINAL
    want = doors.to_game((x, y, z - crac.H / 2), SPEC)
    assert [t["Transform"]["Transform"]["Position"][k] for k in "XYZ"] == pytest.approx(want)
    assert t["SupportingFracture"] == {"Id": "Fracture_05"}
    assert [t["Scale"][k] for k in "XYZ"] == pytest.approx([0.40, 0.31, 0.06])
    p = dm["Particles"]["Transform"]["Transform"]["Position"]
    assert [p[k] for k in "XYZ"] == pytest.approx(list(doors.shift(SPEC)))
    assert len(dm) == 7          # + the two service-port dummies


# ---------------------------------------------------------------------------------------------------- service ports
# The O2 / coolant service ports: decorative today, placed for a data-only "turn on".
PORT_NAMES = ("conveyor_port_o2_1", "conveyor_port_o2_2")


def test_crac_service_ports_on_cell_faces():
    """The reserved port names, each port on the rear CELL FACE (where a conveyor butts the block), centred on a 2 x 2
    cell patch of it (x and z on cell lines from the block's corner, at least one cell in from every edge), like a
    vanilla small conveyor port; the two 0.4 m frames do not overlap, the bay holds both, and the filter door keeps the
    upper half (its two grilles above the bay's joint, the old grille rail z 1.25)."""
    pts = crac.port_points(SPEC)
    assert tuple(sorted(pts)) == PORT_NAMES
    for name, (x, y, z) in pts.items():
        assert y == pytest.approx(-crac.D2)                              # the -Y (Backward, hot aisle) cell face
        for v, half in ((x, crac.W2), (z, crac.H / 2)):
            k = (v + half) / DM.CELL
            assert k == pytest.approx(round(k)) and 1 <= round(k) <= round(2 * half / DM.CELL) - 1, (name, v)
    (_, x1, z1), (_, x2, z2) = crac.PORTS
    assert abs(z2 - z1) >= 0.4 + 0.05 or abs(x2 - x1) >= 0.4 + 0.05
    for _, x, z in crac.PORTS:
        assert crac.BAY_Z[0] <= z - 0.2 and z + 0.2 <= crac.BAY_Z[1] and abs(x) + 0.2 <= crac.DOOR_A
    assert crac.BAY_Z[1] < crac.SEAM_Z[3] < crac.FILTER_DOOR_Z[0] and len(crac.GRILLES) == 2
    assert crac.YK - 0.001 <= -crac.PORT_FACE_Y <= crac.YK          # the kit frame stays in the keep-out plane


def test_crac_service_ports_add_no_mount_points():
    """Today the ports must not snap conveyors or change placement: no mount hint on the rear face (the CRAC's hints
    are the rack's sides, bottom, rims and rail band only) and no conveyor component in the definitions."""
    for n, lo, hi in crac.collision(SPEC)["mount"]:
        if n.startswith("contain_"):
            continue                                                       # the rail band, z 2.29..2.36 (top band)
        assert not (lo[1] <= -crac.D2 + 0.006 and hi[1] - lo[1] < 0.01), n   # no slab on the rear plane
    for name, (x, y, z) in crac.port_points(SPEC).items():
        for n, lo, hi in crac.collision(SPEC)["mount"]:
            inside = lo[0] <= x <= hi[0] and lo[2] <= z <= hi[2] and lo[1] <= y + 0.01 and hi[1] >= y - 0.01
            assert not inside, (name, n)


@pytest.mark.build
def test_crac_service_port_dummies(staged):
    """The two reserved dummies exist on the rear cell face, turned like vanilla's ConveyorBack (180 deg about Y),
    vanilla's small-port scale, supported by the service bay; their type is our own inert ServicePort type (staged),
    not vanilla UseConveyor, and no definition of the block carries a conveyor component."""
    _built_and_exported()
    from dc import doors
    info = clone.entry(SPEC)["info"]
    dm = {c["Value"]["Name"]: c["Value"] for c in body(_staged(info["model_def_file"]))["Dummies"]["Changed"]}
    dt = _files(f"{integration.CRAC_PORT_TYPE}_DummyTypeDefinition")
    assert len(dt) == 1
    port_type = body(_staged(dt[0]))["Guid"]
    for name, p in crac.port_points(SPEC).items():
        d = dm[name]
        assert [d["Transform"]["Transform"]["Position"][k] for k in "XYZ"] == pytest.approx(doors.to_game(p, SPEC))
        assert d["Transform"]["Transform"]["Orientation"] == {"X": 0, "Y": 1, "Z": 0, "W": 0}
        assert [d["Scale"][k] for k in "XYZ"] == pytest.approx(list(crac.PORT_DUMMY_SCALE))
        assert d["Type"] == port_type != integration.CRAC_PORT_TYPE_ON
        assert d["SupportingFracture"] == {"Id": "Fracture_06"}
    for f in _files(""):
        txt = json.dumps(_staged(f))
        assert "Conveyor" not in txt or f.endswith("_BlockModelDefinition.partialdef"), f   # (the dummy names only)
        assert integration.CRAC_PORT_TYPE_ON not in txt, f


@pytest.mark.build
def test_crac_service_ports_kit_provenance():
    """The ports are Keen's small conveyor port FRAME (O2H2Generator250's ConveyorRight border) at LOD0 / LOD1,
    recorded in the build report; its hatch (the ConveyorsAtlas face Fracture_01.017) and latch handle are
    deliberately left out (blanked ports: our blind plate takes the hatch's place). The CRAC stays within Keen's
    limits at every LOD and at 8 materials."""
    e = _entry()
    prov = [p for p in e["provenance"] if "O2Generator250.fbx" in p]
    assert len(prov) == 1 and "ConveyorPortSmall_Border_low" in prov[0]
    assert "ConveyorPortSmall_Handle" not in prov[0] and "Fracture_01" not in prov[0]
    for row in e["lods"]:
        assert row["tris"] <= row["max_tris"] and row["materials"] <= 8, row


@pytest.mark.build
def test_crac_hum_explicit(staged):
    """The hum is set like the racks' (integration.patch_hum): a vanilla loop while Working."""
    _built_and_exported()
    fx = body(_staged(_files("BlockEffectsComponentDefinition")[0]))
    assert fx["OnUseAudio"] == integration.HUM_CRAC


@pytest.mark.build
def test_crac_exported_mount_hints_unchanged():
    """The EXPORTED model (Models/DC_CRAC/placement_exported.json, check_placement) still carries the rack pattern's 9
    mount hints, and its Backward (rear, the ports' face) mounts are only the containment rail band: one group
    covering 10 % of the face, the same as Forward. The ports add no mount point."""
    p = os.path.join(config.MODELS_DIR, NAME, "placement_exported.json")
    if not os.path.exists(p):
        pytest.skip(f"{NAME} not exported / placement not checked")
    m = read_json(p)
    assert m["colliders"]["mount_hints"] == 9
    faces = m["nonfractured"]["faces"]
    assert faces["Backward"] == faces["Forward"] == {"groups": 1, "coverage": 0.1}


def test_crac_caption_is_neutral():
    """Like the racks' neutral IDs: the front header says "CRAC" beside a blank write-on tag (rack.id_tag); no
    unit number is baked in (every CRAC read "CRAC 01")."""
    src = open(crac.__file__).read()
    assert crac.UNIT_CAPTION == "CRAC"
    assert "CRAC 01" not in src and "R.id_tag(" in src


@pytest.mark.build
def test_crac_carries_no_baked_id():
    """The built CRAC's decal labels (build_report zfight elements, every LOD): "CRAC" is there, no numbered ID."""
    zf = _entry().get("zfight")
    assert zf, "no zfight check in build_report.json (rebuild with build_dc.py)"
    labels = {e["label"].split(" ", 1)[1] for e in zf["elements"]}
    import re
    assert "CRAC" in labels and not [lb for lb in labels if re.fullmatch(r"CRAC\s*\d+", lb)], sorted(labels)
