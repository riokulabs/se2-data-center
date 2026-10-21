"""Plan 3 Task 8: the signs and labels (dc/signs.py), DC_Sign_Aisle, DC_Sign_AisleHang, DC_Sign_Rack (LCDNarrow50
clones: editable LCDs).

Pure tests check the builder's numbers (screens and their aspect, collision and mount hints, the rod plates, the
back plate's bolts on the door header's inserts) and the room couplings on dc/room.reference_room:
  * the rack label on a rack's top front edge between the Drop's waterfall columns: no cell conflict with the Drop,
    the roof or (on a half rack) the Chute, and its foot's mount hint on the rack's label pad (Review Focus 4);
  * the hanging sign under a rod hanger turned 90 deg to it: the hanger's rods and coupler hints land on the sign's
    rod plates and Up hints (the T2 carry).
The build-marked tests check the MEASURED blocks (build_report.json, the export manifests, the staged definitions):
the LCD surfaces (P3-18: 4:1 at 1024 x 256 on the aisle signs, native 2:1 on the label, on the matching vanilla
off-screen material), the faces that mount, Keen's limits, breakable in-plane zones, the aisle sign on every door
header and the label clear of every built Drop's render mesh.
"""
import json
import math
import os

import numpy as np
import pytest

from dc import catalog, config, contain, functional, integration, rack, room, signs, tray, tray_plan
from dc import dims as DM
from dc import fracture as FR
from dc.material_guids import MATERIAL_GUIDS

SIGNS = ("DC_Sign_Aisle", "DC_Sign_AisleHang", "DC_Sign_Rack")
MM = 0.001
DROPS = [f"DC_Tray_Drop_{d}" for d in ("Low", "Moderate", "Full")]
FACES = ("Forward", "Backward", "Left", "Right", "Up", "Down")
LOD_MATERIALS = {"DC_Sign_Aisle": 8, "DC_Sign_AisleHang": 8, "DC_Sign_Rack": 4}   # Keen's LOD0 cap per model size


def _spec(n):
    return catalog.BY_NAME[n]


def _blocks():
    if not os.path.exists(config.REPORT_PATH):
        pytest.skip("no build_report.json yet")
    with open(config.REPORT_PATH) as f:
        return json.load(f)["blocks"]


def _entry(name):
    blocks = _blocks()
    if name not in blocks or not blocks[name].get("placement", {}).get("total"):
        pytest.skip(f"{name} not built yet")
    return blocks[name]


def _manifest(name):
    p = os.path.join(config.MODELS_DIR, name, "export.json")
    if not os.path.exists(p):
        pytest.skip(f"{name} not exported yet")
    with open(p) as f:
        return json.load(f)


def _world(p, v):
    """A point of placed block p's centred frame in world (room) coordinates."""
    return np.array(p.origin) + np.array(room.rot(tuple(v), p.yaw))


def _local(p, w):
    """A world point in placed block p's centred frame."""
    return np.array(room.rot(tuple(np.array(w) - np.array(p.origin)), -p.yaw % 4))


def _rect_world(p, rect, axes, plane):
    """A mount rect [a0, a1, b0, b1] on a block's plane (axes = the two in-plane axes, plane = (axis, value)) -> the
    world AABB (lo, hi) of its corners."""
    pts = []
    for a in rect[:2]:
        for b in rect[2:]:
            v = [0.0, 0.0, 0.0]
            v[axes[0]], v[axes[1]], v[plane[0]] = a, b, plane[1]
            pts.append(_world(p, v))
    pts = np.array(pts)
    return pts.min(axis=0), pts.max(axis=0)


# ---------------------------------------------------------------------------------------------------- pure
def test_sign_catalogue_and_staging():
    specs = [_spec(n) for n in SIGNS]
    assert all(s.family == "sign" and s.copy_from == "LCDNarrow50" and s.functional for s in specs)
    assert [s.cells for s in specs] == [(4, 1, 1), (4, 1, 2), (2, 1, 1)]
    assert [round(v, 6) for v in signs.size(specs[1])] == [1.0, 0.5, 0.25]
    staged = {b.name for b in catalog.STAGED}
    assert set(SIGNS) <= staged and set(SIGNS) <= {b.name for b in catalog.BLOCKS}   # menu / unlock since T10
    assert [signs.mount_direction(s) for s in specs] == ["Backward", "Up", "Down"]


@pytest.mark.parametrize("name", SIGNS)
def test_screens_and_surfaces(name):
    """P3-18: the aisle signs' screens are 4:1 (1024 x 256, AspectRatio 4) on vanilla LCDScreen_Off_4.0, the rack
    label's 2:1 (LCDNarrow50's native 512 x 256) on LCDScreen_Off_2.0; the screens' slots are the surfaces'
    MeshPartNames, in order; each screen's measured-to-be size has its surface's aspect (1 %)."""
    scr = signs.screens(_spec(name))
    surf = functional.SIGN_LCD[name]
    assert [s.slot for s in scr] == [f["MeshPartName"] for f in surf]
    for s, f in zip(scr, surf):
        w, h = s.size
        assert w / h == pytest.approx(f["AspectRatio"], rel=0.01)
        assert f["Resolution"]["X"] / f["Resolution"]["Y"] == pytest.approx(f["AspectRatio"])
        want = {4: ("fa0a1f34-75c1-4899-bc3c-761ec9f70877", "LCDScreen_Off_4.0.def"),
                2: ("bd7f946b-3867-4aaf-8aaf-2a8eed16e832", "LCDScreen_Off_2.0.def")}[f["AspectRatio"]]
        assert MATERIAL_GUIDS[s.slot] == want, s.slot
        assert FR.DAMAGED_SLOTS[s.slot] == "LCDScreen_Off_Damaged"
        assert abs(np.linalg.norm(s.normal) - 1) < 1e-9 and abs(np.dot(s.normal, s.up)) < 1e-9
    if name == "DC_Sign_Aisle":
        assert scr[0].size == (0.80, 0.20)
    if name == "DC_Sign_AisleHang":   # double-faced: back to back on the y = 0 plane
        assert [s.normal for s in scr] == [(0.0, 1.0, 0.0), (0.0, -1.0, 0.0)]
        assert scr[0].center[1] == -scr[1].center[1] and scr[0].center[2] == scr[1].center[2]
    if name == "DC_Sign_Rack":        # the face looks down at the aisle
        assert scr[0].normal[1] > 0.9 and scr[0].normal[2] < -0.2


@pytest.mark.parametrize("name", SIGNS)
def test_sign_collision_and_hints(name):
    """One physics box inside the cell box; mount hints only on the sign's one mounting face."""
    s = _spec(name)
    c = signs.collision(s)
    sx, sy, sz = signs.size(s)
    assert len(c["regular"]) == 1 and c["occupancy"] == []
    for _, lo, hi in c["regular"] + c["mount"]:
        assert -sx / 2 <= lo[0] < hi[0] <= sx / 2 and -sy / 2 <= lo[1] < hi[1] <= sy / 2
        assert -sz / 2 <= lo[2] < hi[2] <= sz / 2
    plane = {"Backward": (1, -sy / 2), "Up": (2, sz / 2), "Down": (2, -sz / 2)}[signs.mount_direction(s)]
    for _, lo, hi in c["mount"]:
        k, v = plane
        assert hi[k] - lo[k] <= signs.HINT_T + 1e-9 and (lo[k] if v < 0 else hi[k]) == pytest.approx(v)
    rects = {"DC_Sign_Aisle": signs.back_mount_rects, "DC_Sign_AisleHang": signs.up_mount_rects,
             "DC_Sign_Rack": signs.down_mount_rects}[name](s)
    assert len(rects) == len(c["mount"]) == (2 if name == "DC_Sign_AisleHang" else 1)


def test_aisle_back_bolts_on_door_inserts():
    """The aisle sign's four back-plate bolts are the door header fascia's threaded inserts (dc/contain.py: x +-0.42,
    z ZH + 0.05 and DH - 0.05), the sign centred on the header band."""
    zc = (contain.ZH + contain.DH) / 2
    inserts = sorted((x, round(z - zc, 6)) for x in (-0.42, 0.42) for z in (contain.ZH + 0.05, contain.DH - 0.05))
    assert sorted((x, round(z, 6)) for x, z in signs.A_BOLTS_BACK) == inserts
    assert contain.DH - contain.ZH == pytest.approx(DM.CELL)        # the header band is exactly the sign's cell


def test_hang_rod_plates_pure():
    """The hanging sign's two rod plates: x = +-ROD_S on its centre line, ROD_PLATE square, top 1 mm under the top
    plane (Plan 2's rod-plate convention)."""
    s = _spec("DC_Sign_AisleHang")
    got = signs.rod_plates(s)
    assert [(x, y) for x, y, _, _ in got] == [(-DM.ROD_S, 0.0), (DM.ROD_S, 0.0)]
    assert all(z == pytest.approx(DM.CELL / 2 - tray_plan.END_INSET) and side == pytest.approx(tray_plan.ROD_PLATE)
               for _, _, z, side in got)
    assert tray_plan.ROD_PLATE == pytest.approx(DM.ROD_PLATE) == pytest.approx(0.034)


def _hang_and_rods(placed):
    hang = next(p for p in placed if p.name == "DC_Sign_AisleHang")
    rods = next(p for p in placed if p.tag == "aisle/hang/rods")
    return hang, rods


@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_hang_sign_rods_land_on_plates(w):
    """reference_room: the hanger (DC_TrayRods_100) turned 90 deg to the sign stands on the sign's top plane, its two
    rods (tray_plan: the piece's centre +- ROD_S across) over the sign's rod plates (1 mm), and its coupler hints
    (Down) are the sign's Up hints (1 mm): the same two cells mount."""
    hang, rods = _hang_and_rods(room.reference_room(w, "cold"))
    assert (rods.yaw - hang.yaw) % 2 == 1                     # turned 90 deg to each other
    rs, ss = _spec(rods.name), _spec(hang.name)
    assert rods.origin[2] - 0.25 * rs.cells[1] / 2 == pytest.approx(hang.origin[2] + 0.25 * ss.cells[1] / 2)
    pl = tray_plan.plan(rs)
    sup = next(sp for sp in pl.supports if sp.kind == "rods")
    centre = pl.size / 2
    rod_xy = sorted(tuple(np.round(_world(rods, np.asarray(a, float) - centre)[:2], 6)) for a, _ in sup.rods)
    plates = sorted(tuple(np.round(_world(hang, (x, y, z))[:2], 6)) for x, y, z, _ in signs.rod_plates(ss))
    assert np.allclose(rod_xy, plates, atol=MM), (rod_xy, plates)
    down = [(lo, hi) for n, lo, hi in tray.collision(rs)["mount"] if n.startswith("coupler")]
    up = [(lo, hi) for n, lo, hi in signs.collision(ss)["mount"]]
    to_w = lambda p, lo, hi: np.sort(np.array([_world(p, (x, y, 0.0))[:2] for x in (lo[0], hi[0])  # noqa: E731
                                               for y in (lo[1], hi[1])]), axis=0)[[0, -1]]
    a = sorted(tuple(np.round(to_w(rods, lo, hi).ravel(), 4)) for lo, hi in down)
    b = sorted(tuple(np.round(to_w(hang, lo, hi).ravel(), 4)) for lo, hi in up)
    assert np.allclose(a, b, atol=MM), (a, b)


def _label_for(placed, tag):
    return next(p for p in placed if p.tag == f"{tag}/label")


def _occ(p):
    return room.occupied(p, room.pure_report([p.name]))


@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_rack_top_stack_no_conflicts(w, aisle):
    """Review Focus 4: on every full rack of the reference room (trays on) the label's cells miss the Drop's occupied
    cells (tray_plan.occupied_cells: the waterfall columns either side of it) and the roof's; the label stands
    between the waterfalls (|x| of its cells < WF_X - R_WF) on the rack's top plane."""
    placed = room.reference_room(w, aisle)
    roofs = set().union(*(_occ(p) for p in placed if room.spec(p).family == "contain_roof"))
    racks = [p for p in placed if room.spec(p).family == "rack"]
    assert len(racks) == 8
    for r in racks:
        lab = _label_for(placed, r.tag)
        drop = next(p for p in placed if p.tag == f"{r.tag}/tray")
        assert drop.name.startswith("DC_Tray_Drop_")
        assert not _occ(lab) & _occ(drop), (r.tag, _occ(lab) & _occ(drop))
        assert not _occ(lab) & roofs, r.tag
        lo, hi = (np.array(v) for v in room.box(lab))
        loc = [_local(r, c) for c in (lo, hi)]
        assert max(abs(v[0]) for v in loc) <= DM.WF_X - DM.R_WF
        assert min(v[2] for v in loc) == pytest.approx(0.25 * room.spec(r).cells[1] / 2)


def _half_rack_with_chute(yaw):
    """A half rack under a Chute (the Drop's waterfall column continued down, Plan 2 test_chute_continues_drop), its
    label on the front (yaw 0) or, the rack turned, the other face: floor z = 0, the rack's 5-cell depth on the grid
    (its centre half a cell off a grid line)."""
    hr = room.Placed("DC_Rack24_Open", (0.0, DM.CELL / 2, 0.625), yaw, "H1")
    full_h = 0.25 * _spec("DC_Rack42_Open").cells[1]
    ch = tray_plan.plan("Chute")
    c_local = (0.0, DM.TRAY_RACK_Y - tray_plan.Y_C + 2 * DM.CELL + DM.CELL / 2, full_h - ch.size[2] / 2 - 0.625)
    chute = room.Placed("DC_Tray_Chute", tuple(_world(hr, c_local)), yaw, "H1/chute")
    lc = (sum(DM.LABEL_X) / 2, sum(DM.LABEL_Y) / 2, 0.625 + DM.CELL / 2)
    lab = room.Placed("DC_Sign_Rack", tuple(_world(hr, lc)), yaw, "H1/label")
    return hr, chute, lab


@pytest.mark.parametrize("yaw", (0, 2))
def test_half_rack_label_between_chute_ladders(yaw):
    """A half rack with a Chute: the label's cells miss the Chute's occupied cells (its two ladders) and sit inside
    the Chute's box between them, on the half rack's top plane."""
    hr, chute, lab = _half_rack_with_chute(yaw)
    assert _occ(lab) <= room.world_cells(chute)               # in the Chute's bottom row, between the ladders
    assert not _occ(lab) & _occ(chute), _occ(lab) & _occ(chute)
    assert room.box(lab)[0][2] == pytest.approx(1.25)


@pytest.mark.parametrize("rk", ("DC_Rack42_Open", "DC_Rack24_Open"))
@pytest.mark.parametrize("side", (1, -1))
def test_label_foot_on_rack_pad(rk, side):
    """The label's Down mount hint (its foot) lies on the rack's Up mount hints (the full rack's rim band, the half
    rack's label pads), front and back (the label turned with the face), >= 95 % of its area."""
    s = _spec("DC_Sign_Rack")
    (fx0, fx1, fy0, fy1), = signs.down_mount_rects(s)
    H = 0.25 * _spec(rk).cells[1]
    ups = [(lo, hi) for n, lo, hi in rack.collision(_spec(rk))["mount"] if abs(hi[2] - H / 2) < 1e-9
           and hi[2] - lo[2] < 0.01]
    yc = side * sum(DM.LABEL_Y) / 2
    pts = [(side * x, yc + side * y) for x in (fx0, fx1) for y in (fy0, fy1)]   # label yaw 0 (front) / 2 (back)
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    area = (x1 - x0) * (y1 - y0)
    cover = sum(max(0.0, min(x1, hi[0]) - max(x0, lo[0])) * max(0.0, min(y1, hi[1]) - max(y0, lo[1]))
                for lo, hi in ups)
    assert cover >= 0.95 * area, (rk, side, cover / area)


# ---------------------------------------------------------------------------------------------------- measured
@pytest.mark.build
@pytest.mark.parametrize("name", SIGNS)
def test_sign_faces_and_limits(name):
    """Only the mounting face mounts (the hanging sign: Up in its two rod-plate groups); every face else none; the
    whole box occupied; Keen's limits (LOD0 <= 70 %, its material cap, the last LOD 1 material and <= 32 tris); one
    physics box; no bevel hazard."""
    e = _entry(name)
    f = e["placement"]["faces"]
    want = signs.mount_direction(_spec(name))
    for d in FACES:
        if d == want:
            assert f[d]["groups"] == (2 if name == "DC_Sign_AisleHang" else 1), (name, d, f[d])
        else:
            assert f[d]["groups"] == 0, (name, d, f[d])
    assert e["placement"]["occupied"] == e["placement"]["total"] and not e["placement"]["outside"]
    rows = e["lods"]
    for i, l in enumerate(rows):
        assert l["tris"] <= l["max_tris"] and l["materials"] <= l["max_materials"], (name, i, l)
    assert rows[0]["tris"] <= 0.7 * rows[0]["max_tris"] and rows[0]["materials"] <= LOD_MATERIALS[name]
    assert rows[-1]["tris"] <= 32 and rows[-1]["materials"] == 1
    assert e["colliders"]["regular"] == 1 and not e["bevel_guard"]
    assert e["geometry"]["mount_direction"] == want


@pytest.mark.build
@pytest.mark.parametrize("name", SIGNS)
def test_measured_screens(name):
    """The built screens: one quad per surface slot, at the planned centre, size (its aspect within 1 %) and normal."""
    for s in _entry(name)["geometry"]["screens"]:
        assert s["faces"] == 1, s
        assert np.allclose(s["center"], s["planned"]["center"], atol=MM), s
        assert np.allclose(s["size"], s["planned"]["size"], atol=MM), s
        assert np.allclose(s["normal"], s["planned"]["normal"], atol=1e-3), s
        assert s["size"][0] / s["size"][1] == pytest.approx(s["planned"]["size"][0] / s["planned"]["size"][1],
                                                            rel=0.01)


@pytest.fixture(scope="module")
def staged():
    integration.write_all()
    return integration.STAGE


def _staged(rel):
    from dc.assetio import read_json
    p = os.path.join(config.STAGE_ASSETS, rel)
    return read_json(p if os.path.exists(p) else os.path.join(config.MOD_ASSETS, rel))


@pytest.mark.build
@pytest.mark.parametrize("name", SIGNS)
def test_sign_lcd_surfaces(staged, name):
    """The staged LcdMultiPanel: one surface per screen, in order, each MeshPartName a material of our NonFractured
    LOD0 (the mesh part the LCD draws into), 1024 x 256 / AspectRatio 4 on the aisle signs and 512 x 256 / 2 on the
    label (P3-18), vanilla's DefaultScreenMaterial and UseOnlineTexture kept, one delta key per surface; the
    NonFractured .model maps each screen slot to the matching vanilla off-screen material; the model's LcdPanel
    dummy over the front screen, SupportingFracture of the zone holding it."""
    from dc import clone
    from dc.assetio import body
    if name not in integration.built_names():
        pytest.skip(f"{name} not built")
    spec = _spec(name)
    m = _manifest(name)
    lod0 = set(m["nonfractured"]["lods"][0]["materials"])
    files = integration._block_files(spec, "LcdMultiPanelDefinition")
    assert len(files) == 1
    sv = body(_staged(files[0]))["Surfaces"]
    vals = [c["Value"] for c in sv["Changed"]]
    assert [c["Index"] for c in sv["Changed"]] == list(range(len(vals))) and len(set(sv["Keys"])) == len(vals)
    assert len(vals) == len(signs.screens(spec)) == len(functional.SIGN_LCD[name])
    for v, want in zip(vals, functional.SIGN_LCD[name]):
        assert v["MeshPartName"] in lod0, (v["MeshPartName"], lod0)
        for k, x in want.items():
            assert v[k] == x, (k, v[k], x)
        assert v["DefaultScreenMaterial"] == "8a35c12c-0fb9-45fa-be7b-6d97cb624c75" and v["UseOnlineTexture"]
        ar = 4 if name != "DC_Sign_Rack" else 2
        assert v["AspectRatio"] == ar and v["Resolution"] == ({"X": 1024, "Y": 256} if ar == 4 else
                                                               {"X": 512, "Y": 256})
    model = _staged(f"{config.NAME}/{name}/Models/NonFractured/{name}.model")["$Value"]
    mats = {a["MaterialName"]: a["MaterialReference"] for a in model["MaterialAssignments"]}
    for v in vals:
        assert mats[v["MeshPartName"]] == MATERIAL_GUIDS[v["MeshPartName"]][0]
    info = clone.entry(spec)["info"]
    bmd = body(_staged(info["model_def_file"]))
    dm = {c["Value"]["Name"]: c["Value"] for c in bmd["Dummies"]["Changed"]}
    lp = dm["LcdPanel"]
    (x, y, z), sc = integration.sign_dummies(spec)["LcdPanel"]
    assert lp["Transform"]["Transform"]["Position"] == {"X": x, "Y": y, "Z": z}
    assert lp["SupportingFracture"] == {"Id": "Fracture_01"}
    s0 = signs.screens(spec)[0]
    assert (lp["Scale"]["X"], lp["Scale"]["Y"]) == pytest.approx(s0.size)


@pytest.mark.build
def test_signs_staged(staged):
    """Staged as breakable editable LCDs: PCU 35, mount directions restricted to the sign's one face, our names,
    the BreakableBlockComponent kept, the menu / unlock left to Task 10."""
    from dc import clone, names
    from dc.assetio import body
    built = integration.built_names()
    for n in SIGNS:
        if n not in built:
            pytest.skip(f"{n} not built")
        spec = _spec(n)
        info = clone.entry(spec)["info"]
        bd = body(_staged(info["block_def_file"]))
        assert bd["PCU"] == 35 and bd["MountPointGeneratorSettings"] == {"Directions": signs.mount_direction(spec)}
        assert bd["UIData"]["Name"] == names.NAMES[n][0]
        kind = body(_staged(info["kind_file"]))
        assert (kind["Name"], kind["Description"]) == names.NAMES[n]
        comp = body(_staged(f"{config.NAME}/{n}/{n}_ServerComposition.partialdef"))
        assert integration.BREAKABLE_KEY in comp["Components"]["Keys"]
        bmd = body(_staged(info["model_def_file"]))
        assert bmd["DamagedModel"] != bmd["FractureModel"]


@pytest.mark.build
@pytest.mark.parametrize("name", SIGNS)
def test_sign_files_declare_their_bundles(staged, name):
    """Every "Bundle:Type" name ($Type, Type, UseActionType) in a staged / installed sign file has its bundle in the
    file's own $Bundles (the archive serializer resolves types only through them: Plan 4 test_bundles.py)."""
    from dc.assetio import read_json

    def types(x, out):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("$Type", "Type", "UseActionType") and isinstance(v, str) and ":" in v:
                    out.add(v.split(":", 1)[0])
                types(v, out)
        elif isinstance(x, list):
            for v in x:
                types(v, out)
        return out
    n = 0
    for root in (os.path.join(integration.STAGE, name), os.path.join(config.MOD_ASSETS, config.NAME, name)):
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.endswith((".def", ".partialdef", ".model", ".meta")):
                    d = read_json(os.path.join(dp, f))
                    n += 1
                    assert not types(d, set()) - set(d.get("$Bundles") or {}), os.path.join(dp, f)
    assert n > 20


@pytest.mark.build
@pytest.mark.parametrize("name", SIGNS)
def test_sign_breakable_export(name):
    """Breakable, split IN PLANE (dc/fracture.py _sign; vanilla LCDNarrow50: 2 zones, none critical): 3 tiles along x
    on the 1.0 m signs, 2 halves on the label, within Keen's table for the measured model; the screen is cut with its
    tiles (its slot in more than one zone), the housing / bezel / caps in every zone; its own Damaged model maps the
    screens to vanilla's broken LCD; the LcdPanel dummy supported by Fracture_01."""
    m = _manifest(name)
    zones = [z["id"] for z in m["fractured"]["zones"]]
    assert len(zones) == (2 if name == "DC_Sign_Rack" else 3)
    assert len(zones) <= FR.max_fractures(m["fractured"]["size"])
    assert integration.keeps_breakable(m) and m["fractured"]["kind"] == "cut" and m["fractured"]["critical"] == []
    assert m["fractured"]["supporting"] == {"LcdPanel": "Fracture_01"}
    by_zone = {}
    for p in m["fractured"]["parts"]:
        g, _, mat = p.partition("-")
        by_zone.setdefault(g.replace("_Hide", ""), set()).add(mat)
    for z in zones:
        assert {"PaintedMetalColorable", "PaintedMetalDarker"} <= by_zone[z], (z, by_zone[z])
    slot = signs.screens(_spec(name))[0].slot
    assert sum(slot in v for v in by_zone.values()) >= 2
    assert any("FracturedMaterial01" in v for v in by_zone.values())
    assert m["damaged"]["lods"]


@pytest.mark.build
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_aisle_sign_on_door_header(w):
    """reference_room, every door width: the aisle sign at each end stands on its door's room-side header face (its
    -Y plane on the door's +Y plane), its back mount rect inside the door's +Y header_rects and centred on x = 0."""
    se = _entry("DC_Sign_Aisle")
    de = _entry(room.door_name(w))
    (sx0, sx1, sz0, sz1), = se["geometry"]["back_mount_rects"]
    placed = room.reference_room(w, "cold")
    for end in ("west", "east"):
        door = next(p for p in placed if p.tag == f"{end}/door")
        sign = next(p for p in placed if p.tag == f"{end}/sign")
        assert door.yaw == sign.yaw
        back = _local(door, _world(sign, (0.0, -DM.CELL / 2, 0.0)))
        assert back[1] == pytest.approx(DM.CELL / 2) and abs(back[0]) < 1e-9, back    # on the door's +Y plane
        (hx0, hx1, hz0, hz1), = de["geometry"]["header_rects"]["+y"]
        lo = _local(door, _world(sign, (sx0, -DM.CELL / 2, sz0)))
        hi = _local(door, _world(sign, (sx1, -DM.CELL / 2, sz1)))
        x0, x1, z0, z1 = min(lo[0], hi[0]), max(lo[0], hi[0]), min(lo[2], hi[2]), max(lo[2], hi[2])
        assert hx0 - 1e-6 <= x0 and x1 <= hx1 + 1e-6 and hz0 - 1e-6 <= z0 and z1 <= hz1 + 1e-6, (end, w)
        assert abs(x0 + x1) < 1e-6, (x0, x1)


@pytest.mark.build
def test_hang_sign_rod_plates_match_trays():
    """The built hanging sign: rod_plates == (+-ROD_S, 0) at the top plane's 1 mm inset, ROD_PLATE square (1 mm);
    with DC_TrayRods_100 placed per room.reference_room (turned 90 deg to the sign) the hanger's measured Down
    groups (2) pair with the sign's Up groups (2), and its rod centres coincide with the plates (1 mm)."""
    e = _entry("DC_Sign_AisleHang")
    g = e["geometry"]["rod_plates"]
    assert len(g) == 2
    for (x, y, zt, side), sx in zip(sorted(g), (-1, 1)):
        assert x == pytest.approx(sx * DM.ROD_S, abs=MM) and y == pytest.approx(0.0, abs=MM)
        assert zt == pytest.approx(DM.CELL / 2 - 0.001, abs=MM) and side == pytest.approx(DM.ROD_PLATE, abs=MM)
    assert e["placement"]["faces"]["Up"]["groups"] == 2
    re = _entry("DC_TrayRods_100")
    assert re["placement"]["faces"]["Down"]["groups"] == 2
    hang, rods = _hang_and_rods(room.reference_room(1.5, "cold"))
    pl = tray_plan.plan(_spec(rods.name))
    sup = next(sp for sp in pl.supports if sp.kind == "rods")
    rod_xy = sorted(tuple(_world(rods, np.asarray(a, float) - pl.size / 2)[:2]) for a, _ in sup.rods)
    pw = sorted(tuple(_world(hang, (x, y, zt))[:2]) for x, y, zt, _ in g)
    assert np.allclose(rod_xy, pw, atol=MM), (rod_xy, pw)


def _drop_verts(name):
    from dc import fracture_rules as FRR
    m = _manifest(name)
    f = os.path.join(config.MODELS_DIR, name, "NonFractured", m["nonfractured"]["lods"][0]["file"])
    return np.array([v for mesh in FRR.fbx_meshes(f).values() for v in mesh["verts"]])


@pytest.mark.build
@pytest.mark.parametrize("drop", DROPS)
def test_rack_label_clear_of_drop_render(drop):
    """No vertex of the built Drop's LOD0 (every density), placed over a rack as reference_room places it, lies inside
    the label's cell box (the label stands between the waterfalls, under the tray)."""
    placed = room.reference_room(1.5, "cold")
    r = next(p for p in placed if p.tag == "A1")
    lab = _label_for(placed, "A1")
    d = next(p for p in placed if p.tag == "A1/tray")
    d = room.Placed(drop, d.origin, d.yaw, d.tag)
    vs = _drop_verts(drop)
    lo, hi = (np.array(v) for v in room.box(lab))
    w = np.array([_world(d, v) for v in vs])
    inside = np.all((w > lo + 1e-6) & (w < hi - 1e-6), axis=1)
    assert not inside.any(), (drop, w[inside][:5])
    assert r.yaw == lab.yaw == d.yaw


@pytest.mark.build
def test_sign_previews_skip_when_absent():
    """Previews are generated on disk, never tracked (user direction): nothing here depends on them."""
    p = os.path.join(config.PREVIEW_DIR, "p3-task-8")
    if not os.path.isdir(p):
        pytest.skip("no previews rendered")
    assert any(f.endswith(".png") for f in os.listdir(p))


# ---------------------------------------------------------------------------------------------------- Plan 3 T11
def _label_faces_out(lab):
    """The label's screen (its +Y, tilted down) points away from the contained aisle (y = 0)."""
    face = room.rot((0.0, 1.0, 0.0), lab.yaw)
    return face[1] * lab.origin[1] > 0


@pytest.mark.parametrize("aisle", ("cold", "hot"))
@pytest.mark.parametrize("w", DM.AISLE_WIDTHS)
def test_contained_aisle_labels_go_on_the_open_side(w, aisle):
    """The T8 carry: in a contained aisle the roof covers the rack tops' aisle edge, so a label there stands above the
    roof (unreadable from inside). The guidance, as the room builds it (reference_room(label_side="open")): every
    label on its rack's OTHER top edge, facing the open aisle: the back pad of a rack facing a contained cold aisle,
    the front pad of one whose back faces a contained hot aisle. No cell of the roof, the Drop or anything else in
    the room is taken; each label sits on its rack's top plane over that pad (its foot mounts there:
    test_label_foot_on_rack_pad, both sides)."""
    placed = room.reference_room(w, aisle, label_side="open")
    assert not room.conflicts(placed, room.pure_report([p.name for p in placed]))
    want = -1 if aisle == "cold" else 1
    assert room.label_pad(aisle, "open") == want and room.label_pad(aisle, "aisle") == -want
    racks = {p.tag: p for p in placed if room.spec(p).family == "rack"}
    labels = [p for p in placed if p.name == "DC_Sign_Rack"]
    assert len(labels) == len(racks) == 8
    for lab in labels:
        r = racks[lab.tag.split("/")[0]]
        assert room.box(lab)[0][2] == room.STACK["rack_top"]
        c = _local(r, lab.origin)
        assert c[1] == pytest.approx(want * sum(DM.LABEL_Y) / 2) and abs(c[0]) < 1e-9, (aisle, r.tag, c)
        assert _label_faces_out(lab), (aisle, r.tag)


@pytest.mark.parametrize("aisle", ("cold", "hot"))
def test_reference_room_label_sides(aisle):
    """label_side as the room builds it: "front" (the default, Review Focus 4) puts every label on its rack's front
    pad whatever the aisle; "aisle" faces the contained aisle; "open" and "aisle" are mirror images."""
    def pads(side):
        placed = room.reference_room(1.5, aisle, label_side=side)
        racks = {p.tag: p for p in placed if room.spec(p).family == "rack"}
        return {lab.tag: (np.sign(_local(racks[lab.tag.split("/")[0]], lab.origin)[1]), _label_faces_out(lab))
                for lab in placed if lab.name == "DC_Sign_Rack"}
    front, toward, away = pads("front"), pads("aisle"), pads("open")
    assert {s for s, _ in front.values()} == {1.0}
    assert {lab.tag: lab for lab in room.reference_room(1.5, aisle) if lab.name == "DC_Sign_Rack"} == \
        {lab.tag: lab for lab in room.reference_room(1.5, aisle, label_side="front") if lab.name == "DC_Sign_Rack"}
    assert all(not out for _, out in toward.values()) and all(out for _, out in away.values())
    assert all(toward[t][0] == -away[t][0] for t in toward)
    assert {s for s, _ in toward.values()} == ({1.0} if aisle == "cold" else {-1.0})
    with pytest.raises(ValueError):
        room.reference_room(1.5, aisle, label_side="both")
