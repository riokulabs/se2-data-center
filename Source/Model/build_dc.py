"""Data Center build.

    blender -b --python Source/Model/build_dc.py -- [BLOCK ...|all] [--no-render]
    blender --python Source/Model/build_dc.py -- [BLOCK ...|all] --no-render --export     (WINDOWED: VRAGE Tools)

--export writes Source/Model/Models/<name>/ (FBX LODs, collision glTF, Fractured variant, export.json) for every
built block of this run; the VRAGE Tools add-on needs a GPU context, so run Blender windowed (it quits itself).
Then `python3 Source/Model/build_integration.py` stages the package (no Blender needed)."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tools")))

from dc import catalog, config, dims as DM, report  # noqa: E402

BUILT = {}   # name -> {"lods": [(coll, objs)], "collision": [(kind, ob)], "root": coll} for previews
BEVEL_HAZARDS = {}   # object name -> zero-length edges in a bevelled Part (visual pass 2 guard)


def _install_bevel_guard():
    """se2model bevels use clamp-overlap, which clamps the WHOLE part: one zero-length edge (e.g. oct_pts(..., 0.0))
    silently kills every bevel of that Part. Wrap part_to_object once and record such edges per object."""
    from se2model import objects as OB
    if getattr(OB.part_to_object, "_dc_guard", False):
        return
    orig = OB.part_to_object

    def guarded(p, coll, name, *a, **k):
        if p.bevel[0] > 0 and p.bevel[1] > 0:
            n = sum(1 for e in p.bm.edges if e.calc_length() < 1e-6)
            if n:
                BEVEL_HAZARDS[name] = n
        return orig(p, coll, name, *a, **k)
    guarded._dc_guard = True
    OB.part_to_object = guarded


def bevel_guard(spec):
    return {k: v for k, v in BEVEL_HAZARDS.items() if k.startswith(spec.name + "_")}


def build_rack(spec, render):
    import bpy
    from dc import assemble, rack
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, rack.build, rack, root)
    boxes = rack.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], raw = assemble.placement(spec, lods[0][1], boxes)
    # every mount cell, the box faces too (the Open racks mount Forward / Backward on the containment rail band, all
    # racks on the sides and top): dc/placer_emu.rack_block models the rack's outside with them (final review M1)
    entry["placement"]["mount_cells"] = {d: [list(c) for c in f.get("mount_cell_list", [])]
                                         for d, f in raw["faces"].items()}
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["frame: generated (dc/rack.py, ported from tools/mockups/datacenter/dclib2.py build_rack2)",
                           "stencil glyphs: AtlasFont_BarlowCondensed boxes from se2model/decals.py"]
    entry["geometry"] = rack_geometry(spec, lods[0][1])
    sub = None
    from dc import doors, rack_doors
    table = rack_doors.subparts_for(spec)
    if table:
        sub = build_generic_subparts(spec, root, table)
        entry["subparts"] = {"models": subpart_rows(sub)}
        entry["provenance"].append("door leaves + tray fan rotors: generated (dc/rack_doors.py, dc/doors.py); "
                                   "perforation: vanilla MetalPerforationSteel material")
    entry["geometry"].update(pdu_clearance(spec, lods[0][1], sub))
    if doors.has_doors(spec):
        entry["doors"] = door_report(spec, sub)
        print("  doors", {k: v for k, v in entry["doors"].items() if k not in ("hulls", "sweep")})
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", entry["geometry"])
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials")
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": sub}
    return entry


def build_generic_subparts(spec, root, table):
    """{subpart: [(coll, objs)] per LOD} from {name: (builder(spec, lod), last(lo, hi))}: Keen's optimal LOD count
    for each subpart's own measured LOD0 (at least 2); the last LOD is its LOD0 bounding box (12 tris)."""
    from dc import assemble
    from se2model import limits
    from se2model import objects as OB
    out = {}
    for name, (builder, last) in table.items():
        coll = OB.new_collection(f"{spec.name}_{name}_LOD0", root)
        objs = [OB.part_to_object(p, coll, f"{spec.name}_{name}_LOD0_{p.name}") for p in builder(spec, 0)]
        n = max(2, limits.model_limits(assemble.measured_size(objs), OB.stats(objs)["tris"])["optimal_lods"])
        lo, hi = OB.bounds(objs)
        lods = [(coll, objs)]
        for L in range(1, n):
            coll = OB.new_collection(f"{spec.name}_{name}_LOD{L}", root)
            parts = builder(spec, L) if L < n - 1 else last(lo, hi)
            lods.append((coll, [OB.part_to_object(p, coll, f"{spec.name}_{name}_LOD{L}_{p.name}") for p in parts]))
        out[name] = lods
    return out


def subpart_rows(sub):
    from dc import assemble
    from se2model import limits
    from se2model import objects as OB
    rep = {}
    for name, lods in sub.items():
        size = assemble.measured_size(lods[0][1])
        st = [OB.stats(objs) for _, objs in lods]
        lim = limits.model_limits(size, st[0]["tris"])
        rows = []
        for i, s_ in enumerate(st):
            li = lim["lods"][i] if i < len(lim["lods"]) else {"max_tris": 0, "max_materials": 0}
            rows.append({"tris": s_["tris"], "max_tris": li["max_tris"], "materials": len(s_["materials"]),
                         "max_materials": li["max_materials"], "material_names": s_["materials"]})
        rep[name] = {"model_size": list(size), "lods": rows, "bounds_local": OB.bounds(lods[0][1])}
        print(f"  subpart {name}: " + " | ".join(f"{r['tris']}/{r['max_tris']} {r['materials']}/{r['max_materials']}"
                                                for r in rows))
    return rep


def door_report(spec, sub):
    """Measured on the built LOD0 leaf models: each model's plan hull (leaf frame) and z span, then the closed boxes,
    the neighbour clearance at the cap, the largest clear angle and the swing envelope (dc/doors.py)."""
    from dc import doors
    hulls, zs = {}, {}
    for m in doors.leaf_models(spec):
        pts = [(o.matrix_world @ v.co) for o in sub[m][0][1] if o.type == "MESH" for v in o.data.vertices]
        hulls[m] = [list(p) for p in doors.convex_hull([(p.x, p.y) for p in pts])]
        zs[m] = [round(min(p.z for p in pts), 5), round(max(p.z for p in pts), 5)]
    H = {m: [tuple(p) for p in h] for m, h in hulls.items()}
    d, pair = doors.neighbour_clearance(spec, H, 1.0)
    closed = doors.closed_boxes(spec, H, {m: tuple(z) for m, z in zs.items()})
    return {"hulls": hulls, "z": zs, "open_deg": doors.OPEN, "clearance_m": round(d, 5), "clearance_pair": pair,
            "max_clear_deg": doors.max_clear_angle(spec, H), "sweep": doors.sweep_report(spec, H),
            "closed": {k: [[round(c, 5) for c in lo], [round(c, 5) for c in hi]] for k, (lo, hi) in closed.items()},
            "leaf_width_m": round(DM.DOOR_W - DM.DOOR_U0, 5), "axis": [DM.DOOR_AXIS_X, DM.DOOR_AXIS_Y]}


def clearance(objs):
    """Render-geometry extents of LOD0 (evaluated, world = block frame): proves the slot clearances."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    c = {"max_abs_x_in_slot": 0.0, "max_abs_x": 0.0, "max_z": -9.0, "min_z": 9.0, "min_y": 9.0, "max_y": -9.0}
    for o in objs:
        if o.type != "MESH":
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        for v in me.vertices:
            x, y, z = o.matrix_world @ v.co
            c["max_abs_x"] = max(c["max_abs_x"], abs(x))
            if abs(y) < DM.SLOT_HALF_D - 1e-6:
                c["max_abs_x_in_slot"] = max(c["max_abs_x_in_slot"], abs(x))
            c["max_z"], c["min_z"] = max(c["max_z"], z), min(c["min_z"], z)
            c["max_y"], c["min_y"] = max(c["max_y"], y), min(c["min_y"], y)
        oe.to_mesh_clear()
    return {k: round(v, 5) for k, v in c.items()}


# ---------------------------------------------------------------------------------------------------- measurements
def _part_objs(objs, part):
    return [o for o in objs if o.type == "MESH" and o.name.split(".")[0].endswith("_" + part)]


def _verts(objs, part):
    return [tuple(o.matrix_world @ v.co) for o in _part_objs(objs, part) for v in o.data.vertices]


def _clusters(vals, gap=0.004):
    """Centres ((min + max) / 2) of runs of sorted values separated by more than gap."""
    vals = sorted(vals)
    out, run = [], [vals[0]] if vals else []
    for v in vals[1:]:
        if v - run[-1] > gap:
            out.append((run[0] + run[-1]) / 2)
            run = []
        run.append(v)
    if run:
        out.append((run[0] + run[-1]) / 2)
    return out


def _rel(z, floor):
    """Slot-relative z (0 .. SLOT_H) of an absolute z, slots stacked from floor."""
    return (z - floor) % DM.SLOT_H


def server_geometry(spec, objs, clear):
    """Measured on the built LOD0 meshes (block frame): the interface parts the rack couples to."""
    h2 = DM.SLOT_H * spec.cells[1] / 2
    ear = [v for v in _verts(objs, "ear") if abs(v[0]) > DM.SLOT_HALF_W]
    scr = _verts(objs, "screw")
    sld = _verts(objs, "slide")
    r5 = lambda v: round(v, 5)   # noqa: E731
    return {"cell_front_y": DM.SLOT_FRONT_Y,
            "ear_back_y": r5(min(v[1] for v in ear)), "ear_front_y": r5(max(v[1] for v in ear)),
            "ear_max_x": r5(max(abs(v[0]) for v in ear)),
            "screw_x": r5(sum(abs(v[0]) for v in scr) / len(scr)),
            "screw_offsets": sorted({r5(_rel(z, -h2)) for z in _clusters([v[2] for v in scr], gap=0.02)}),
            "screw_z_all": [r5(z + h2) for z in _clusters([v[2] for v in scr], gap=0.02)],
            "slide_z": [r5(min(_rel(v[2], -h2) for v in sld)), r5(max(_rel(v[2], -h2) for v in sld))],
            "slide_max_x": r5(max(abs(v[0]) for v in sld)),
            "side_max_x": clear["max_abs_x_in_slot"],
            "top_gap": r5(h2 - clear["max_z"])}


SX_IN = DM.SLOT_HALF_W - 1e-4   # strictly inside the slot's side planes (the rack's slide webs lie on them)


def rack_geometry(spec, objs):
    """Measured on the built LOD0 rack meshes: the slot front plane (front rail ear face), the square-hole column,
    the slide rails, the slide bolts' reach into the slot, the obstruction over the top slot and (Plan 2) the
    top-entry brush plates."""
    from dc import rack
    d = rack.dims(spec)
    floor0 = -d["H"] / 2 + 0.25                       # slot 1 floor in the centred frame
    top = floor0 + DM.SLOT_H * d["nslots"]             # top slot's top
    rail = [v for v in _verts(objs, "rail") if v[1] > 0]
    holes = [o.matrix_world @ p.center for o in _part_objs(objs, "holes") for p in o.data.polygons]
    holes = [c for c in holes if c.y > 0]
    sld = _verts(objs, "slide")
    bolt = _verts(objs, "slidebolt")
    ceil = _verts(objs, "ceiling")
    r5 = lambda v: round(v, 5)   # noqa: E731
    # visual pass 1: anything of the rack inside the slot footprint near the top slot's top (roof, headers, tray)
    near = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    near = [v for v in near if abs(v[0]) < SX_IN and abs(v[1]) < DM.SLOT_HALF_D - 1e-4 and v[2] > top - 0.05]
    return {"top_slot_intrusion": r5(max(0.0, top - min(v[2] for v in near))) if near else 0.0,
            "slot_front_y": r5(max(v[1] for v in rail)), "rail_inner_x": r5(min(abs(v[0]) for v in rail)),
            "rail_outer_x": r5(max(abs(v[0]) for v in rail)),
            "hole_x": r5(sum(abs(c.x) for c in holes) / len(holes)),
            "hole_offsets": sorted({r5(_rel(c.z, floor0)) for c in holes}),
            "slide_z": [r5(min(_rel(v[2], floor0) for v in sld)), r5(max(_rel(v[2], floor0) for v in sld))],
            "slide_bolt_reach_x": r5(min(abs(v[0]) for v in bolt)),
            "slide_plane_x": r5(min(abs(v[0]) for v in sld)),
            "top_obstruction_z": r5(min(v[2] for v in ceil) - top),
            "top_entries": top_entries(objs), **room_interface(spec, objs)}


def room_interface(spec, objs):
    """Plan 3: the rack's room interface, measured on the built LOD0 parts (and, for the mount rects, read from the
    mount hints the placement analysis uses), centred block frame:
      * contain_rails: {front, back} -> [x0, x1, y0, y1, z0, z1] of the containment rail ("contain" part; full racks);
      * pdu_receptacles: [[x, y, z_top]] per PDU socket ("socket" part: its ring's centre and top);
      * up_mount_rects / down_mount_rects: [x0, x1, y0, y1] of the mount hints on the top / bottom plane."""
    from dc import rack
    r5 = lambda v: round(v, 5)   # noqa: E731
    rails = {}
    vs = _verts(objs, "contain")
    for side, sy in (("front", 1), ("back", -1)):
        g = [v for v in vs if v[1] * sy > 0]
        if g:
            rails[side] = [r5(min(v[i] for v in g)) if k == 0 else r5(max(v[i] for v in g))
                           for i in range(3) for k in (0, 1)]
    recs = []
    vs = _verts(objs, "socket")
    for sx in (-1, 1):
        g = [v for v in vs if v[0] * sx > 0]
        if g:
            recs.append([r5((min(v[0] for v in g) + max(v[0] for v in g)) / 2),
                         r5((min(v[1] for v in g) + max(v[1] for v in g)) / 2), r5(max(v[2] for v in g))])
    H = rack.dims(spec)["H"]
    up, down = [], []
    for _, lo, hi in rack.collision(spec)["mount"]:
        if hi[2] - lo[2] > 0.01:
            continue
        rect = [r5(lo[0]), r5(hi[0]), r5(lo[1]), r5(hi[1])]
        if abs(hi[2] - H / 2) < 1e-6:
            up.append(rect)
        elif abs(lo[2] + H / 2) < 1e-6:
            down.append(rect)
    return {"contain_rails": rails, "pdu_receptacles": recs, "up_mount_rects": up, "down_mount_rects": down}


def pdu_clearance(spec, objs, sub):
    """Plan 3: the rack's LOD0 vertices inside the PDU envelope (dims.PDU_ENVELOPE, mirrored for Feed B) over the PDU
    band (rack.pdu_band), counting the rack model and its static side panels (the RackSide subpart, placed at the
    origin and turned 180 deg as the integration places it). 0 = the zero-U PDU strip's space is clear."""
    from dc import rack
    (x0, x1), (y0, y1) = DM.PDU_ENVELOPE
    b0, b1 = rack.pdu_band(spec)
    dz = -rack.dims(spec)["H"] / 2
    z0, z1 = b0 + dz, b1 + dz
    pts = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    side = (sub or {}).get("RackSide")
    if side:
        sp = [tuple(o.matrix_world @ v.co) for o in side[0][1] if o.type == "MESH" for v in o.data.vertices]
        pts += sp + [(-x, -y, z) for x, y, z in sp]
    eps = 1e-5
    hits = [p for p in pts if x0 + eps < abs(p[0]) < x1 - eps and y0 + eps < p[1] < y1 - eps and z0 + eps < p[2] < z1 - eps]
    return {"pdu_envelope_clear": len(hits), "pdu_envelope_hits": [[round(c, 4) for c in p] for p in hits[:8]],
            "pdu_band": [round(z0, 5), round(z1, 5)]}


def top_entries(objs):
    """Plan 2: the FRONT top-entry brush plates, measured on the bristle lips (the "brush" part spans exactly the
    plate's opening): per entry [x0, x1, y0, y1, z_top] in the centred block frame, sorted by x. The tray plan
    (dims.WF_X / WF_Y / R_WF) must land its waterfalls inside these; the rear (power) entries are not tray ports."""
    vs = [v for v in _verts(objs, "brush") if v[1] > 0]
    out = []
    for sx in (-1, 1):
        g = [v for v in vs if v[0] * sx > 0]
        if g:
            out.append([round(min(v[0] for v in g), 5), round(max(v[0] for v in g), 5), round(min(v[1] for v in g), 5),
                        round(max(v[1] for v in g), 5), round(max(v[2] for v in g), 5)])
    return out


def build_server(spec, render):
    from dc import assemble, server
    from dc.servers import deco, eventctl, kvm, programmable, status, timer, ups
    from se2model import objects as OB
    builders = {**{v: deco.build for v in deco.FACES}, "Timer": timer.build, "EventCtl": eventctl.build,
                "Status": status.build, "UPS": ups.build, "KVM": kvm.build, "Programmable": programmable.build}
    if spec.variant not in builders:
        return report.empty_entry(spec)
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, builders[spec.variant], server, root)
    boxes = server.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["clearance"] = clearance(lods[0][1])
    entry["geometry"] = server_geometry(spec, lods[0][1], entry["clearance"])
    entry["provenance"] = ["chassis + face: generated (dc/server.py, dc/servers/*.py); v2 SE language from "
                           "tools/mockups/datacenter/dclib2.py", "stencil glyphs: se2model/decals.py boxes"]
    if spec.variant == "UPS":
        from dc.servers import cellbay
        entry["lod0_objects"] = sorted(o.name for o in lods[0][1])
        entry["bays"] = []
        for part, front in (("cellbay_front", True), ("cellbay_rear", False)):
            vs = _verts(lods[0][1], part)
            lo = [min(v[i] for v in vs) for i in range(3)]
            hi = [max(v[i] for v in vs) for i in range(3)]
            entry["bays"].append({"part": part, "mouth_y": round(hi[1] if front else lo[1], 5),
                                  "centre": [round((lo[0] + hi[0]) / 2, 5), round((lo[2] + hi[2]) / 2, 5)],
                                  "half": round((hi[0] - lo[0]) / 2, 5)})
        entry["provenance"].append("cell bays: vanilla Battery50 slot frame (kit part, read-only import) "
                                   + ", ".join(f"LOD{k}={v}" for k, v in sorted(cellbay.PROVENANCE.items())))
    if spec.variant in ("Timer", "EventCtl", "Status"):
        entry["provenance"].append("screen art: vanilla Terminal material UVs (Terminal_albedo 'SERVER TERMINAL' "
                                   "panel) / the vanilla LCD surface")
    if spec.variant == "Programmable":
        entry["face"] = dict(programmable.LAST_FACE)
    sub = None
    if spec.variant == "KVM":
        sub = build_subparts(spec, root)
        entry["subparts"] = subpart_report(sub)
        entry["provenance"].append("KVM subparts (drawer, screen): generated (dc/servers/kvm.py, dc/subparts.py); "
                                   "screen art: vanilla Terminal material UVs")
    if spec.variant in ("Timer", "EventCtl", "Status", "UPS", "KVM", "Programmable"):
        entry["mesh_parts"] = sorted({m for o in lods[0][1] if o.type == "MESH" for m in
                                      (s.material.name.split(".")[0] for s in o.material_slots if s.material)})
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  clearance", entry["clearance"])
    print("  geometry", entry["geometry"])
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": sub}
    return entry


# ---------------------------------------------------------------------------------------------------- subparts
def build_subparts(spec, root):
    """{subpart: [(coll, objs)] per LOD}: each subpart gets Keen's optimal LOD count for its own measured LOD0 size and
    triangles (at least 2); the last LOD is its LOD0 bounding box in one material (12 tris), as vanilla subparts."""
    from dc import assemble
    from dc.servers import kvm
    from se2model import limits
    from se2model import objects as OB
    out = {}
    for name, builder in kvm.SUBPARTS.items():
        coll = OB.new_collection(f"{spec.name}_{name}_LOD0", root)
        objs = [OB.part_to_object(p, coll, f"{spec.name}_{name}_LOD0_{p.name}") for p in builder(0)]
        n = max(2, limits.model_limits(assemble.measured_size(objs), OB.stats(objs)["tris"])["optimal_lods"])
        lo, hi = OB.bounds(objs)
        lods = [(coll, objs)]
        for L in range(1, n):
            coll = OB.new_collection(f"{spec.name}_{name}_LOD{L}", root)
            parts = builder(L) if L < n - 1 else kvm.last_box(name, lo, hi)
            lods.append((coll, [OB.part_to_object(p, coll, f"{spec.name}_{name}_LOD{L}_{p.name}") for p in parts]))
        out[name] = lods
    return out


def subpart_report(sub):
    """Per subpart: LOD rows against its own limits; the stowed and popped-out envelopes in the KVM frame (the
    animation is applied to the built LOD0 vertices: drawer + TRAVEL along +Y, screen rotated FOLD_DEG about the
    hinge then carried by the drawer) and the transient overlap of the simultaneous motion."""
    from mathutils import Matrix, Vector
    from dc import assemble
    from dc import subparts as S
    from se2model import limits
    from se2model import objects as OB
    rep = {"models": {}}
    for name, lods in sub.items():
        size = assemble.measured_size(lods[0][1])
        st = [OB.stats(objs) for _, objs in lods]
        lim = limits.model_limits(size, st[0]["tris"])
        rows = []
        for i, s_ in enumerate(st):
            li = lim["lods"][i] if i < len(lim["lods"]) else {"max_tris": 0, "max_materials": 0}
            rows.append({"tris": s_["tris"], "max_tris": li["max_tris"], "materials": len(s_["materials"]),
                         "max_materials": li["max_materials"], "material_names": s_["materials"]})
        rep["models"][name] = {"model_size": list(size), "lods": rows, "bounds_local": OB.bounds(lods[0][1])}
    hinge = Vector(S.HINGE)

    def verts(name, m):
        return [m @ (o.matrix_world @ v.co) for o in sub[name][0][1] if o.type == "MESH" for v in o.data.vertices]

    def env(pts):
        return {k: round(f(p[i] for p in pts), 5) for k, f, i in (("min_x", min, 0), ("max_x", max, 0),
                                                                  ("min_y", min, 1), ("max_y", max, 1),
                                                                  ("min_z", min, 2), ("max_z", max, 2))}
    stow = Matrix.Translation(hinge)
    pop = Matrix.Translation(hinge + Vector((0, S.TRAVEL, 0)))
    rot = Matrix.Rotation(__import__("math").radians(S.FOLD_DEG), 4, "X")
    st_pts = verts(S.DRAWER, stow) + verts(S.SCREEN, stow)
    lid_pop = verts(S.SCREEN, pop @ rot)
    pop_pts = verts(S.DRAWER, pop) + lid_pop
    above = [p for p in lid_pop if p.z > 0.125]
    rep["envelope"] = {"stowed": env(st_pts), "popped": env(pop_pts),
                       "popped_rear_y_above_slot": round(min(p.y for p in above), 5) if above else None,
                       "slot_above_covered_m": round(max(p.z for p in lid_pop) - 0.125, 5)}
    rep["screen_height"] = S.LID["len"]
    rep["animation"] = {"travel_m": S.TRAVEL, "fold_deg": S.FOLD_DEG, "seconds": S.POP_TIME,
                        "drawer_speed": S.DRAWER_SPEED, "screen_deg_per_s": S.SCREEN_SPEED}
    rep["transient"] = S.transient_intrusion()
    rep["pivot_game"] = S.drawer_dummy_game()
    print("  subparts", {n: [(r["tris"], r["max_tris"], r["materials"], r["max_materials"]) for r in m["lods"]]
                         for n, m in rep["models"].items()})
    print("  envelope", rep["envelope"], "transient", rep["transient"])
    return rep


def build_tray(spec, render):
    """Plan 2: a cable-tray block (dc/tray.py from its cable plan dc/tray_plan.py, dressed by dc/tray_kit.py)."""
    import bpy
    from dc import assemble, tray
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, tray.build, tray, root)
    boxes = tray.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], raw = assemble.placement(spec, lods[0][1], boxes)
    entry["placement"]["mount_cells"] = {d: [list(c) for c in f.get("mount_cell_list", [])]
                                         for d, f in raw["faces"].items()}
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["tray: generated from its cable plan (dc/tray_plan.py, dc/tray_bends.py) by dc/tray_kit.py; "
                           "wire, strap, trapeze and boot shapes ported from tools/mockups/datacenter/dclib.py and "
                           "dclib2.py, SE-ified",
                           "LOD2 basket card: vanilla GratingMetallic material (alpha-tested, read-only reference)",
                           "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py"]
    entry["tray"] = {"run_length": round(tray.run_length(spec), 6), "ports": tray.ports_block(spec),
                     "materials_per_lod": [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                                   for m in o.data.materials if m}) for _, objs in lods]}
    entry["tray"]["port_sections"] = port_sections(lods[0][1], entry["tray"]["ports"])
    entry["tray"]["port_caps"] = port_caps(lods[0][1], entry["tray"]["ports"])
    entry["tray"]["detail"] = [tray.DETAIL.get((spec.name, i), i) for i in range(len(lods) - 1)]
    entry["tray"]["geometry"] = junction_geometry(spec, lods[0][1])
    entry["tray"]["entries"] = entry_sections(spec, lods[0][1])
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    mid = None
    if spec.family == "tray":   # Task 9b: the kit's mid detail, for a light piece's cut Fractured / Damaged models
        mcoll = OB.new_collection(f"{spec.name}_MID")
        mid = [OB.part_to_object(p, mcoll, f"{spec.name}_MID_{p.name}") for p in tray.mid_parts(spec)]
        bpy.context.scene.view_layers[0].layer_collection.children[mcoll.name].exclude = True
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": None, "mid": mid}
    return entry


def junction_geometry(spec, objs):
    """Measured on the BUILT LOD0 mesh of a junction (Task 7): "saddle_top", the crossover saddle's deck top above the
    cell plane (the largest upward face of the Darker guide part inside the deck's footprint); "corner_graze", how deep
    any render vertex reaches into the plan's free corner cells (tray_plan.corner_cells), from their inner faces."""
    import numpy as np
    from dc import tray_plan as TP
    pl = TP.plan(spec)
    out = {}
    half = pl.size / 2
    sd = [f for f in pl.fittings if f.kind == "crossover_saddle"]
    if sd:
        c = pl.to_block(sd[0].frame.o)
        best = None
        for ob in objs:
            if ob.type != "MESH" or not ob.name.split(".")[0].endswith("_guide"):
                continue
            me, mw = ob.data, ob.matrix_world
            for poly in me.polygons:
                n = mw.to_3x3() @ poly.normal
                q = np.array(mw @ poly.center)
                if n.z > 0.99 and np.all(np.abs(q[:2] - c[:2]) < 0.2) and (best is None or poly.area > best[0]):
                    best = (poly.area, float(q[2] + half[2]))
        out["saddle_top"] = None if best is None else round(best[1], 6)
    cells = TP.corner_cells(pl)
    if cells:
        vs = np.array([tuple(ob.matrix_world @ v.co) for ob in objs if ob.type == "MESH" for v in ob.data.vertices])
        out["corner_graze"] = round(max(TP.corner_graze(pl, cell, vs + half) for cell in cells), 6)
    return out


def entry_sections(spec, objs):
    """Measured on the BUILT LOD0 cable mesh (Task 8): per ENTRY rectangle of the plan (a Drop's bottom, a Chute's
    top and bottom), the cable vertices lying on its plane (within 1 um) inside it, in the centred block frame:
    "centre" (the middle of their extent, on the plane), "r" (their largest distance from it) and "points" ([x, y],
    deduplicated to 0.01 mm: the strand pattern a Chute under a Drop must continue)."""
    import numpy as np
    from dc import tray_plan as TP
    pl = TP.plan(spec)
    out = {}
    for e in pl.entries:
        o = pl.to_block(e.o)
        pts = set()
        for ob in objs:
            if ob.type != "MESH" or not ob.name.split(".")[0].endswith("_cable"):
                continue
            mw = ob.matrix_world
            for v in ob.data.vertices:
                w = np.array(mw @ v.co)
                d = w - o
                if abs(d @ e.n) < 1e-6 and abs(d @ e.a) <= e.ha and abs(d @ e.b) <= e.hb:
                    pts.add((round(float(w[0]), 5), round(float(w[1]), 5)))
        if not pts:
            continue
        a = np.array(sorted(pts))
        c = (a.min(axis=0) + a.max(axis=0)) / 2
        out[e.name] = {"centre": [round(float(c[0]), 6), round(float(c[1]), 6), round(float(o[2]), 6)],
                       "r": round(float(np.linalg.norm(a - c, axis=1).max()), 6), "points": a.tolist()}
    return out


def port_sections(objs, ports):
    """Measured on the BUILT LOD0 cable mesh: per port, every cable vertex lying on the port plane (within 1 um), as
    [s, h, material] in that port's frame (s = u x t, h along u from the port origin), deduplicated to 0.01 mm. The
    build-marked tests compare these with the lane contract (tray_lanes) and the strand pattern (tray_xsec)."""
    import numpy as np
    out = {}
    for name, p in ports.items():
        o, t, u = (np.array(p[k], float) for k in ("o", "t", "u"))
        s = np.cross(u, t)
        pts = set()
        for ob in objs:
            if ob.type != "MESH" or not ob.name.split(".")[0].endswith("_cable"):
                continue
            me, mw = ob.data, ob.matrix_world
            for poly in me.polygons:
                m = me.materials[poly.material_index].name.split(".")[0]
                for vi in poly.vertices:
                    w = np.array(mw @ me.vertices[vi].co) - o
                    if abs(w @ t) < 1e-6:
                        pts.add((round(float(w @ s), 5), round(float(w @ u), 5), m))
        out[name] = sorted([a, b, m] for a, b, m in pts)
    return out


def build_floor(spec, render):
    """Plan 3 Task 3: a raised-floor block (dc/floor.py), breakable: in-plane tile zones (dc/fracture.py _floor)."""
    from dc import assemble, floor
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, floor.build, floor, root)
    boxes = floor.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["tiles, pedestals, stringers: generated (dc/floor.py; the raised-floor look of the "
                           "docs/design/mockups/data-center 06 room shots, SE-ified)",
                           "perforated insert: vanilla MetalPerforationSteel material; break faces (Fractured model): vanilla "
                           "FracturedMaterial01 (dc/fracture_mesh.py caps)",
                           "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py"]
    entry["geometry"] = floor_geometry(spec, lods[0][1])
    entry["materials_per_lod"] = [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                          for m in o.data.materials if m}) for _, objs in lods]
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", {k: v for k, v in entry["geometry"].items() if "rects" not in k})
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": None}
    return entry


def floor_geometry(spec, objs):
    """Measured on the built LOD0 floor meshes (centred block frame):
      * deck_top_z: the highest render vertex (the deck trim's top; the cell-top plane is +RF_H / 2);
      * seam_inset: how far the deck's top edges (every vertex above the seal lip) stand inside the side planes;
      * internal_seam: the same, from each internal tile edge of a 1.0 m block (None for one tile): equal to
        seam_inset, so the 0.5 m grid's hairline is the same inside a block and between blocks;
      * lip_reach: the side planes' distance to the outermost render vertex (the seal lip: 0);
      * under_clear: how far everything under the deck (z < the deck's underside) stays inside the side planes;
      * up_mount_rects / down_mount_rects: [x0, x1, y0, y1] of the mount hints on the top / bottom plane."""
    from dc import floor
    r5 = lambda v: round(v, 5)   # noqa: E731
    h = floor.half(spec)
    vs = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    above = [v for v in vs if v[2] > floor.ZB + floor.LIP + 1e-4]
    below = [v for v in vs if v[2] < floor.ZB - 1e-5]
    seam = h - max(max(abs(v[0]), abs(v[1])) for v in above)
    internal = None
    if len(floor.tiles(spec)) > 1:
        internal = min(min(abs(v[0]) for v in above if abs(v[0]) < 0.1), min(abs(v[1]) for v in above
                                                                              if abs(v[1]) < 0.1))
    down = [[lo[0], hi[0], lo[1], hi[1]] for _, lo, hi in floor.collision(spec)["mount"]
            if abs(lo[2] + floor.H2) < 1e-9 and hi[2] - lo[2] < 0.01]
    return {"deck_top_z": r5(max(v[2] for v in vs)), "cell_top_z": floor.H2, "seam_inset": r5(seam),
            "internal_seam": None if internal is None else r5(internal),
            "lip_reach": r5(h - max(max(abs(v[0]), abs(v[1])) for v in vs)),
            "under_clear": r5(h - max(max(abs(v[0]), abs(v[1])) for v in below)),
            "up_mount_rects": [[r5(c) for c in r] for r in floor.up_mount_rects(spec)],
            "down_mount_rects": [[r5(c) for c in r] for r in down],
            "tiles": len(floor.tiles(spec)), "pedestals": len(floor.pedestals(spec))}


def build_contain_roof(spec, render):
    """Plan 3 Task 4: a containment roof panel (dc/contain.py), breakable: a zone per bay (dc/fracture.py _roof)."""
    from dc import assemble, contain
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, contain.build, contain, root)
    boxes = contain.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["frame, caps, clamps, release links, LED batten: generated (dc/contain.py; the containment "
                           "roof of the docs/design/mockups/data-center 06c shot, SE-ified)",
                           "panes: vanilla FrostedGlass material; LED diffuser: vanilla EmissiveWhite; break faces "
                           "(Fractured model): vanilla FracturedMaterial01 (dc/fracture_mesh.py caps)",
                           "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py"]
    entry["geometry"] = roof_geometry(spec, lods[0][1])
    entry["materials_per_lod"] = [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                          for m in o.data.materials if m}) for _, objs in lods]
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", {k: v for k, v in entry["geometry"].items() if k not in ("edge_mount_rects", "clamps")})
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": None}
    return entry


def roof_geometry(spec, objs):
    """Measured on the built LOD0 roof meshes (centred block frame; z = -0.125 is the racks' ZT):
      * underside_z / top_z: the lowest / highest render vertex; frame_underside_z: the frame beams' underside;
      * edge_mount_rects: {"+y" / "-y": [[x0, x1, z0, z1]], "+x" / "-x": [[y0, y1, z0, z1]]} (the mount hints);
      * clamps: {"+y" / "-y": [[x_centre, y_face, z0, z1]]}: each rail clamp's centre, its face toward the rack (the
        vertex nearest the plane) and z span ("clamp" part);
      * led: [x0, x1, y0, y1, z_under] of the EmissiveWhite diffuser ("led" part);
      * pane_top_z: the panes' top; top_band_max_inset: over every vertex within 20 mm of the top plane, the largest
        distance to the nearest cell plane across x or y (the up-face rule: < contain.RAY_FREE);
      * bays: the number of 0.5 m bays (a pane and a fire release each)."""
    from dc import contain
    r5 = lambda v: round(v, 5)   # noqa: E731
    w = contain.width(spec)
    vs = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    clamps = {"+y": [], "-y": []}
    cv = _verts(objs, "clamp")
    for side, sg in (("+y", 1), ("-y", -1)):
        g = [v for v in cv if v[1] * sg > 0]
        for xc in _clusters([v[0] for v in g], gap=0.06):   # a clamp spans 48 mm, the pads 0.25 m apart
            c = [v for v in g if abs(v[0] - xc) < 0.04]
            clamps[side].append([r5(xc), r5(max(v[1] for v in c) if sg > 0 else min(v[1] for v in c)),
                                 r5(min(v[2] for v in c)), r5(max(v[2] for v in c))])
    lv = _verts(objs, "led")
    gv = _verts(objs, "glass")
    fv = _verts(objs, "frame")
    xs = [-0.5 + DM.CELL * k for k in range(5)]
    ys = [-w / 2 + DM.CELL * k for k in range(spec.cells[2] + 1)]
    top = [v for v in vs if v[2] > contain.H2 - 0.02]
    inset = max(min(min(abs(v[0] - x) for x in xs), min(abs(v[1] - y) for y in ys)) for v in top) if top else 0.0
    return {"underside_z": r5(min(v[2] for v in vs)), "top_z": r5(max(v[2] for v in vs)),
            "frame_underside_z": r5(min(v[2] for v in fv)),
            "x_extent": [r5(min(v[0] for v in vs)), r5(max(v[0] for v in vs))],
            "y_extent": [r5(min(v[1] for v in vs)), r5(max(v[1] for v in vs))],
            "edge_mount_rects": {k: [[r5(c) for c in r] for r in v] for k, v in contain.edge_mount_rects(spec).items()},
            "up_mount_rects": [], "down_mount_rects": [],
            "clamps": clamps,
            "led": [r5(min(v[0] for v in lv)), r5(max(v[0] for v in lv)), r5(min(v[1] for v in lv)),
                    r5(max(v[1] for v in lv)), r5(min(v[2] for v in lv))],
            "pane_top_z": r5(max(v[2] for v in gv)), "top_band_max_inset": r5(inset),
            "bays": len(contain.bays(spec)), "zone_split_z": contain.ZS}


def build_contain_door(spec, render):
    """Plan 3 Task 5: a containment end-of-aisle sliding door (dc/contain.py): the frame, breakable in eight fracture
    zones (dc/fracture.py _door: the lintel, three pieces per pocket tower, the sill), and its two leaf subparts, each with its own collision box (the vanilla
    DoorBlockCollider compounds them into the block's collider while the door is closed)."""
    from dc import assemble, contain
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, contain.build_door, contain, root)
    boxes = contain.door_collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["frame, header track, closers, pockets, threshold, leaves: generated (dc/contain.py; the "
                           "end-of-aisle doors of the docs/design/mockups/data-center 06c shot, SE-ified)",
                           "leaf glazing: vanilla WindowGlassThin material; chevrons: vanilla AtlasDecal_Stickers02; "
                           "break faces (Fractured model): vanilla FracturedMaterial01 (dc/fracture_mesh.py caps)",
                           "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py",
                           "mechanism: vanilla SlidingDoorNarrow250 (DoorServer / DoorSegmentTransformSLERP / "
                           "DoorBlockCollider), cloned"]
    sub = build_generic_subparts(spec, root, contain.leaf_subparts(spec))
    entry["subparts"] = {"models": subpart_rows(sub)}
    lo, hi = contain.leaf_box(spec)
    subcol = {m: [("leaf", lo, hi)] for m in contain.LEAF_MODELS}
    entry["geometry"] = door_geometry(spec, lods[0][1], sub)
    entry["materials_per_lod"] = [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                          for m in o.data.materials if m}) for _, objs in lods]
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", {k: v for k, v in entry["geometry"].items() if k not in ("leaves",)})
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": sub,
                        "subpart_collision": subcol}
    return entry


def door_geometry(spec, objs, sub):
    """Measured on the built LOD0 door (centred block frame; -Y = the racks' side planes at y = -0.125):
      * frame_min_y / frame_max_y: the frame's render extent through the door (the -Y faces stay >= 1 mm inside);
      * back_mount_rects: [[x0, x1, z0, z1]] of the -Y mount hints over the pockets (on the end racks' sides);
      * header_rects: {"-y" / "+y": [[x0, x1, z0, z1]]}: the header band's mount hints (roof run / aisle sign);
      * frame_min_z, header_underside_z, pocket_x ([W/2, W]), opening_clear ([x0, x1] between the posts' faces);
      * leaves: per leaf model its measured LOD0 bounds (leaf frame), its collision box, and the block-frame AABB of
        the closed and the open leaf (the model's bounds moved by the closed / open dummy)."""
    from dc import contain
    r5 = lambda v: round(v, 5)   # noqa: E731
    W = contain.door_w(spec)
    vs = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    inner = [v for v in vs if abs(v[0]) < W / 2 - 1e-4 and v[2] < contain.ZH - 0.06 and v[2] > -contain.DH + 0.02]
    leaves = {}
    for lf in contain.door_leaves(spec):
        pts = [tuple(o.matrix_world @ v.co) for o in sub[lf.model][0][1] if o.type == "MESH" for v in o.data.vertices]
        lo = [r5(min(p[i] for p in pts)) for i in range(3)]
        hi = [r5(max(p[i] for p in pts)) for i in range(3)]
        cb = contain.leaf_box(spec)
        e = {"bounds": [lo, hi], "collision": [[r5(c) for c in cb[0]], [r5(c) for c in cb[1]]]}
        zo = contain.LEAF_ORIGIN_Z
        for k, f in (("closed", 0.0), ("open", 1.0)):
            x = contain.leaf_centre_x(spec, lf.side, f)
            e[k] = [[r5(lo[0] + x), lo[1], r5(lo[2] + zo)], [r5(hi[0] + x), hi[1], r5(hi[2] + zo)]]
        leaves[lf.model] = e
    return {"frame_min_y": r5(min(v[1] for v in vs)), "frame_max_y": r5(max(v[1] for v in vs)),
            "frame_min_z": r5(min(v[2] for v in vs)), "header_underside_z": contain.ZH,
            "opening_clear": [r5(max(v[0] for v in inner if v[0] < 0)), r5(min(v[0] for v in inner if v[0] > 0))]
            if inner else None,
            "back_mount_rects": [[r5(c) for c in r] for r in contain.back_mount_rects(spec)],
            "header_rects": {k: [[r5(c) for c in r] for r in v] for k, v in contain.header_rects(spec).items()},
            "pocket_x": contain.pocket_x(spec), "travel": r5(contain.leaf_travel(spec)),
            "up_mount_rects": [], "down_mount_rects": [], "leaves": leaves}


def build_crac(spec, render):
    """Plan 3 Task 6: the in-row cooler (dc/crac.py): the cabinet, breakable as a functional block (dc/fracture.py
    _crac: a critical coil core and fan sections, shell plates round them), and its CracFan rotor subpart (spawned
    three times by the cloned ConditionalSubParts, spinning while Working)."""
    from dc import assemble, crac
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, crac.build, crac, root)
    boxes = crac.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["cabinet, fan door and modules, controller, filter door, water stubs: generated (dc/crac.py; "
                           "the in-row cooler of the docs/design/mockups/data-center 06c shot, SE-ified)",
                           "plinth, corner posts and caps, containment rail, top-entry brush plates: the rack's own "
                           "builders (dc/rack.py), so every room interface matches the rack's",
                           "perforated grilles: vanilla MetalPerforationSteel; break faces (Fractured model): vanilla "
                           "FracturedMaterial01 (dc/fracture_mesh.py caps)",
                           "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py",
                           "mechanism: vanilla Gyroscope250 (PowerableBlock, FunctionalBlockAnimationController, "
                           "ConditionalSubParts, BlockMaterialSwapper, BlockEffects hum), cloned, GyroscopeComponent "
                           "stripped (P3-15)"]
    from dc import crac_ports
    entry["provenance"].append(
        "O2 / coolant service ports (Plan 3 T11): Keen's small conveyor port frame as a kit part (read-only import; "
        "geometry, normals and first UV unchanged), tools/vanilla-ref/Blocks/O2H2Generator/250/Models/NonFractured/ "
        + "; ".join(f"LOD{lod}: " + ", ".join(v) for lod, v in sorted(crac_ports.PROVENANCE.items()))
        + "; LOD2+ and the bolted blind plates: generated (dc/crac.py _service_bay)")
    sub = build_generic_subparts(spec, root, crac.subparts_for(spec))
    entry["subparts"] = {"models": subpart_rows(sub)}
    entry["geometry"] = crac_geometry(spec, lods[0][1], sub)
    entry["materials_per_lod"] = [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                          for m in o.data.materials if m}) for _, objs in lods]
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", {k: v for k, v in entry["geometry"].items() if k not in ("fans",)})
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": sub}
    return entry


def crac_geometry(spec, objs, sub):
    """Measured on the built LOD0 CRAC (centred block frame), the rack's room interface plus the CRAC's own:
      * contain_rails / up_mount_rects / down_mount_rects (as rack room_interface; the hints from crac.collision);
      * top_entries: the front brush plates (as the rack's geometry.top_entries);
      * front_max_y / back_min_y: the render mesh's reach through the front / back planes outside the rail band (the
        non-mounting openings: <= rack.YK, the keep-out); top_z: the highest vertex (the blind flanges' bolts);
      * flange_top_z: the highest vertex over the CHW stubs (1 mm under the top plane);
      * fans: per rotor pivot (Blender frame) the rotor model's measured radius and y span in the block frame, and the
        clearance to the module's orifice (radial) and to the guard (along y)."""
    from dc import crac
    r5 = lambda v: round(v, 5)   # noqa: E731
    H = crac.H
    rails = {}
    vs = _verts(objs, "contain")
    for side, sy in (("front", 1), ("back", -1)):
        g = [v for v in vs if v[1] * sy > 0]
        if g:
            rails[side] = [r5(min(v[i] for v in g)) if k == 0 else r5(max(v[i] for v in g))
                           for i in range(3) for k in (0, 1)]
    up, down = [], []
    for _, lo, hi in crac.collision(spec)["mount"]:
        if hi[2] - lo[2] > 0.01:
            continue
        rect = [r5(lo[0]), r5(hi[0]), r5(lo[1]), r5(hi[1])]
        if abs(hi[2] - H / 2) < 1e-6:
            up.append(rect)
        elif abs(lo[2] + H / 2) < 1e-6:
            down.append(rect)
    allv = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    zr0, zr1 = crac.ZT - H / 2 + DM.CONTAIN_RAIL_DZ[0], crac.ZT - H / 2 + DM.CONTAIN_RAIL_DZ[1]
    # (the rack's own parts reach past it: the rail's clamp screws stand 5 mm over the band, the corner caps' Yellow
    #  trim 1.5 mm proud of the caps; the CRAC's own front / back stays behind the keep-out)
    out_band = [v for v in allv if not (zr0 - 1e-4 <= v[2] <= zr1 + 0.006) and abs(v[0]) < 0.38]
    pipes = _verts(objs, "pipe") + [v for v in _verts(objs, "hw") if v[1] < -0.1 and v[2] > H / 2 - 0.03]
    fans = []
    rot = [tuple(o.matrix_world @ v.co) for o in sub[crac.FAN][0][1] if o.type == "MESH" for v in o.data.vertices]
    rmax = max(math.hypot(v[0], v[2]) for v in rot)
    for p in crac.fan_points(spec):
        fans.append({"pivot": [r5(c) for c in p], "rotor_r": r5(rmax),
                     "rotor_y": [r5(p[1] + min(v[1] for v in rot)), r5(p[1] + max(v[1] for v in rot))],
                     "tip_clear": r5(crac.ORIFICE_R - rmax),
                     "guard_clear": r5(crac.GUARD_Y[0] - (p[1] + max(v[1] for v in rot)))})
    return {"contain_rails": rails, "up_mount_rects": up, "down_mount_rects": down, "top_entries": top_entries(objs),
            "front_max_y": r5(max(v[1] for v in out_band)), "back_min_y": r5(min(v[1] for v in out_band)),
            "side_max_x": r5(max(abs(v[0]) for v in allv)), "top_z": r5(max(v[2] for v in allv)),
            "bottom_z": r5(min(v[2] for v in allv)), "flange_top_z": r5(max(v[2] for v in pipes)), "fans": fans}


def build_pdu(spec, render):
    """Plan 3 Task 7: the PDU cabinet and the zero-U rack PDU strips (dc/pdu.py), breakable (dc/fracture.py
    _pdu_cabinet / _pdu_strip)."""
    from dc import assemble, pdu
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, pdu.build, pdu, root)
    boxes = pdu.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    if spec.family == "pdu_cabinet":
        entry["provenance"] = ["cabinet, meter, isolator, breakers, gland plates: generated (dc/pdu.py; the floor PDU of "
                               "the docs/design/mockups/data-center 06d shot, SE-ified); plinth, corner posts, "
                               "containment rail and top-entry brush plates: the rack's (dc/rack.py)",
                               "DANGER HIGH VOLTAGE placard: vanilla AtlasDecal_Stickers02 (se2model/decals.py "
                               "danger_hv); break faces (Fractured model): vanilla FracturedMaterial01",
                               "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py"]
        entry["geometry"] = pdu_cabinet_geometry(spec, lods[0][1])
    else:
        entry["provenance"] = ["strip body, outlets, jumper cords, cord channel, bank heads, inlet plug: generated "
                               "(dc/pdu.py; the zero-U PDUs of the docs/design/mockups/data-center 06d shot, SE-ified)",
                               "cords: vanilla Rubber material; break faces (Fractured model): vanilla "
                               "FracturedMaterial01 (dc/fracture_mesh.py caps)",
                               "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py"]
        entry["geometry"] = pdu_strip_geometry(spec, lods[0][1])
    entry["materials_per_lod"] = [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                          for m in o.data.materials if m}) for _, objs in lods]
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", {k: v for k, v in entry["geometry"].items() if "rects" not in k and k != "outlets"})
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": None}
    return entry


def pdu_cabinet_geometry(spec, objs):
    """Measured on the built LOD0 cabinet (centred block frame), the rack's interface names:
      * top_entries: the front top-entry brush plates (as rack_geometry: a Drop lands in them);
      * contain_rails: {front, back} -> [x0, x1, y0, y1, z0, z1] of the containment rail ("contain" part);
      * up_mount_rects / down_mount_rects: [x0, x1, y0, y1] of the mount hints on the top / bottom plane;
      * front_max_y / back_min_y: the render mesh's reach toward the front / back planes (KEEP_OUT)."""
    from dc import pdu
    r5 = lambda v: round(v, 5)   # noqa: E731
    rails = {}
    vs = _verts(objs, "contain")
    for side, sy in (("front", 1), ("back", -1)):
        g = [v for v in vs if v[1] * sy > 0]
        if g:
            rails[side] = [r5(min(v[i] for v in g)) if k == 0 else r5(max(v[i] for v in g))
                           for i in range(3) for k in (0, 1)]
    up, down = [], []
    for _, lo, hi in pdu.cabinet_collision(spec)["mount"]:
        if hi[2] - lo[2] > 0.01:
            continue
        rect = [r5(lo[0]), r5(hi[0]), r5(lo[1]), r5(hi[1])]
        if abs(hi[2] - pdu.H / 2) < 1e-6:
            up.append(rect)
        elif abs(lo[2] + pdu.H / 2) < 1e-6:
            down.append(rect)
    allv = [tuple(o.matrix_world @ v.co) for o in objs if o.type == "MESH" for v in o.data.vertices]
    # the front / back reach outside the containment rail band (the rail's pads stand to 1 mm inside the plane, its
    # clamp screws 5 mm over its top: the rack's rail, dc/rack._contain_rail)
    zt = pdu.ZT - pdu.H / 2
    body = [v for v in allv if not (zt + DM.CONTAIN_RAIL_DZ[0] - 1e-4 < v[2] < zt + DM.CONTAIN_RAIL_DZ[1] + 0.0061)]
    return {"top_entries": top_entries(objs), "contain_rails": rails, "up_mount_rects": up, "down_mount_rects": down,
            "front_max_y": r5(max(v[1] for v in body)), "back_min_y": r5(min(v[1] for v in body))}


def pdu_strip_geometry(spec, objs):
    """Measured on the built LOD0 strip (centred block frame):
      * inlet_plug: [x, y, z] of the twist-lock plug ("plug" part): its centre in plan, its bottom (the face that seats
        in the rack's plinth receptacle);
      * envelope_bounds: [[x0, y0, z0], [x1, y1, z1]] of the whole render mesh (= render_bounds);
      * outlets: [[slot, outlet, x, y, z]] the outlet sockets (dims.pdu_outlets in the strip's frame);
      * outlet_housings: the measured centres of the outlet housings' faces (the "dark" part's socket-face
        polygons), to check the model against dims;
      * up_mount_rects / down_mount_rects: [x0, x1, y0, y1] of the mount hints on the top / bottom plane."""
    from dc import assemble, pdu
    r5 = lambda v: round(v, 5)   # noqa: E731
    pv = _verts(objs, "plug")
    H2 = pdu.h2(spec)
    down = [[r5(lo[0]), r5(hi[0]), r5(lo[1]), r5(hi[1])] for _, lo, hi in pdu.strip_collision(spec)["mount"]
            if abs(lo[2] + H2) < 1e-9 and hi[2] - lo[2] < 0.01]
    sf = pdu.FACE_Y - 0.006
    faces = []
    for o in _part_objs(objs, "dark"):
        for poly in o.data.polygons:
            c = o.matrix_world @ poly.center
            n = o.matrix_world.to_3x3() @ poly.normal
            if abs(c.y - sf) < 1e-5 and n.y < -0.99 and poly.area > 0.0008:
                faces.append([r5(c.x), r5(c.y), r5(c.z)])
    return {"inlet_plug": [r5((min(v[0] for v in pv) + max(v[0] for v in pv)) / 2),
                           r5((min(v[1] for v in pv) + max(v[1] for v in pv)) / 2), r5(min(v[2] for v in pv))],
            "envelope_bounds": assemble.render_bounds(objs),
            "outlets": [[k, i, *p] for k, i, p in pdu.outlets_local(spec)],
            "outlet_housings": sorted(faces, key=lambda c: (c[2], c[0])),
            "feed": pdu.strip_feed(spec), "top_z": r5(pdu.strip_top(spec)),
            "up_mount_rects": [], "down_mount_rects": down}


def build_sign(spec, render):
    """Plan 3 Task 8: a sign / label (dc/signs.py), an editable LCD (LCDNarrow50 clone), breakable: in-plane tiles
    along x (dc/fracture.py _sign)."""
    from dc import assemble, signs
    from se2model import objects as OB
    root = OB.new_collection(spec.name)
    lods = assemble.fit_lods(spec, signs.build, signs, root)
    boxes = signs.collision(spec)
    ccoll = OB.new_collection(f"{spec.name}_collision", root)
    cobjs = assemble.collision_objects(spec, boxes, ccoll)
    entry = report.empty_entry(spec)
    entry["lods"], lim = assemble.lod_report(spec, lods)
    entry["model_size"] = lim["size"]
    entry["render_bounds"] = assemble.render_bounds(lods[0][1])
    entry["placement"], _ = assemble.placement(spec, lods[0][1], boxes)
    entry["colliders"] = {"regular": len(boxes["regular"]), "max": lim["colliders"]["max"],
                          "occupancy_hints": len(boxes["occupancy"]), "mount_hints": len(boxes["mount"])}
    entry["provenance"] = ["housing, bezel, liner, tabs, hangers, foot: generated (dc/signs.py; the photo 1 "
                           "\"AISLE 3 COLD\" / \"RACK 3.01\" signs, SE-ified)",
                           "screens: the cloned LCDNarrow50 LcdMultiPanel surfaces on vanilla LCDScreen_Off_4.0 (4:1) "
                           "/ LCDScreen_Off_2.0 (2:1); break faces (Fractured model): vanilla FracturedMaterial01 "
                           "(dc/fracture_mesh.py caps)",
                           "stencil glyphs: AtlasFont_BarlowCondensed_CleanWhite boxes from se2model/decals.py",
                           "mechanism: vanilla LCDNarrow50 (LcdMultiPanel, terminal), cloned"]
    entry["geometry"] = sign_geometry(spec, lods[0][1])
    entry["materials_per_lod"] = [sorted({m.name.split(".")[0] for o in objs if o.type == "MESH"
                                          for m in o.data.materials if m}) for _, objs in lods]
    entry["bevel_guard"] = bevel_guard(spec)
    print(entry["placement"]["summary"])
    print("  geometry", {k: v for k, v in entry["geometry"].items() if k != "screens"})
    for i, l in enumerate(entry["lods"]):
        print(f"  LOD{i}: {l['tris']}/{l['max_tris']} tris, {l['materials']}/{l['max_materials']} materials "
              f"{l['material_names']}")
    if os.environ.get("DC_DEBUG"):
        for _, objs in lods:
            for ob in objs:
                print("   ", ob.name, OB.stats([ob])["tris"])
    BUILT[spec.name] = {"lods": lods, "collision": cobjs, "root": root, "boxes": boxes, "subparts": None}
    return entry


def sign_geometry(spec, objs):
    """Measured on the built LOD0 sign (centred block frame):
      * screens: per LCD slot, the measured screen quad: centre, size along the face (width along x, height along
        the face's up), its normal (the quad's), and the planned dc/signs.screens entry it must match;
      * rod_plates: [[x, y, z_top, side]] of the hanging sign's rod plates, measured on the "hw" verts at the top;
      * back_mount_rects ([[x0, x1, z0, z1]], -Y), up_mount_rects / down_mount_rects ([[x0, x1, y0, y1]]): the
        mount hints; mount_direction: the one face the definition lets mount."""
    import numpy as np
    from dc import signs
    r5 = lambda v: round(float(v), 5)   # noqa: E731
    by_slot = {}
    for o in objs:
        if o.type != "MESH":
            continue
        mw = o.matrix_world
        names = [m.name.split(".")[0] if m else "" for m in o.data.materials]
        for poly in o.data.polygons:
            n = names[poly.material_index]
            if n.startswith("LCDScreen"):
                by_slot.setdefault(n, []).append((poly, mw, o))
    scr = []
    for s in signs.screens(spec):
        polys = by_slot.get(s.slot, [])
        pts = np.array([tuple(mw @ ob.data.vertices[i].co) for poly, mw, ob in polys for i in poly.vertices])
        nrm = np.array(sum((np.array(tuple(mw.to_3x3() @ poly.normal)) for poly, mw, _ in polys), np.zeros(3)))
        nrm = nrm / (np.linalg.norm(nrm) or 1.0)
        up = np.array(s.up)
        x = np.array((1.0, 0.0, 0.0))
        c = (pts.min(axis=0) + pts.max(axis=0)) / 2 if len(pts) else np.zeros(3)
        w = float(np.ptp(pts @ x)) if len(pts) else 0.0
        h = float(np.ptp(pts @ up)) if len(pts) else 0.0
        scr.append({"face": s.face, "slot": s.slot, "faces": len(polys), "center": [r5(v) for v in c],
                    "size": [r5(w), r5(h)], "normal": [r5(v) for v in nrm],
                    "planned": {"center": list(s.center), "size": list(s.size), "normal": list(s.normal)}})
    plates = []
    for x, y, zt, side in signs.rod_plates(spec):
        hv = [v for v in _verts(objs, "hw") if abs(v[0] - x) < side and abs(v[1] - y) < side and v[2] > zt - 0.0065]
        if hv:
            plates.append([r5((min(v[0] for v in hv) + max(v[0] for v in hv)) / 2),
                           r5((min(v[1] for v in hv) + max(v[1] for v in hv)) / 2), r5(max(v[2] for v in hv)),
                           r5(max(v[0] for v in hv) - min(v[0] for v in hv))])
    return {"screens": scr, "rod_plates": plates,
            "back_mount_rects": [[r5(c) for c in r] for r in signs.back_mount_rects(spec)],
            "up_mount_rects": [[r5(c) for c in r] for r in signs.up_mount_rects(spec)],
            "down_mount_rects": [[r5(c) for c in r] for r in signs.down_mount_rects(spec)],
            "mount_direction": signs.mount_direction(spec)}


def _not_yet(spec, render):
    """Plan 3 room families: catalogued (Task 2) but not built until their task (floor T3, roof T4, door T5, CRAC T6,
    PDUs T7, signs T8). Each task replaces its family's entry with the real builder."""
    raise NotImplementedError(spec.family)


def port_caps(objs, ports):
    """Measured on the BUILT LOD0 cable mesh (Task 10, V-T7b): per port, the cable faces that close a bundle's end
    there: every vertex tray_xsec.CAP_INSET inside the port plane (within 1 um), facing out along t. -> {port: count}
    (7 per capped bundle: the hexagon of the hidden centre cable and the six strand lobes)."""
    import numpy as np
    from dc import tray_xsec as XS
    out = {}
    for name, p in ports.items():
        o, t = (np.array(p[k], float) for k in ("o", "t"))
        n = 0
        for ob in objs:
            if ob.type != "MESH" or not ob.name.split(".")[0].endswith("_cable"):
                continue
            me, mw = ob.data, ob.matrix_world
            for poly in me.polygons:
                d = [float((np.array(mw @ me.vertices[vi].co) - o) @ t) for vi in poly.vertices]
                if all(abs(x + XS.CAP_INSET) < 1e-6 for x in d) and float(np.array(mw.to_3x3() @ poly.normal) @ t) > 0.99:
                    n += 1
        out[name] = n
    return out


BUILDERS = {"rack": build_rack, "server": build_server, "tray": build_tray, "trayrods": build_tray}
BUILDERS.update({f: _not_yet for f in catalog.ROOM_FAMILIES})
BUILDERS["floor"] = build_floor          # Plan 3 Task 3
BUILDERS["contain_roof"] = build_contain_roof   # Plan 3 Task 4
BUILDERS["contain_door"] = build_contain_door   # Plan 3 Task 5
BUILDERS["crac"] = build_crac                   # Plan 3 Task 6
BUILDERS["pdu_cabinet"] = build_pdu        # Plan 3 Task 7
BUILDERS["pdu_strip"] = build_pdu
BUILDERS["sign"] = build_sign                   # Plan 3 Task 8


def select(names):
    """The specs to build: "all" (or nothing) = the pipeline's blocks; otherwise each name, where a name ending in
    "*" is a prefix over the whole catalogue (quote it in the shell: "DC_Tray_Straight*"). Catalogue order, no
    duplicates."""
    if not names or names == ["all"]:
        return list(catalog.BLOCKS)
    picked, missing = set(), []
    for n in names:
        hits = ({b.name for b in catalog.CATALOGUE if b.name.startswith(n[:-1])} if n.endswith("*") else
                {n} & set(catalog.BY_NAME))
        if not hits:
            missing.append(n)
        picked |= hits
    if missing:
        raise SystemExit(f"unknown block(s): {', '.join(missing)}")
    return [b for b in catalog.CATALOGUE if b.name in picked]


def main(argv):
    _install_bevel_guard()
    from dc import zfight, zfight_room
    zfight.install()       # tag decal quads per element (measured below, stripped before export)
    render = "--no-render" not in argv
    do_export = "--export" in argv
    names = [a for a in argv if not a.startswith("--")]
    specs = select(names)
    nobuilder = sorted({s.family for s in specs} - set(BUILDERS))
    if nobuilder:
        raise SystemExit(f"no builder yet for famil{'ies' if len(nobuilder) > 1 else 'y'} {', '.join(nobuilder)}")
    pending = sorted({s.family for s in specs if BUILDERS[s.family] is _not_yet})
    if pending:   # fail before building anything (a room block would otherwise stop the run half way)
        raise NotImplementedError(", ".join(pending))
    data = {"blocks": {}}
    if os.path.exists(config.REPORT_PATH):   # merge: blocks not rebuilt keep their last entry
        import json
        with open(config.REPORT_PATH) as f:
            data = json.load(f)
    for spec in specs:
        data["blocks"][spec.name] = BUILDERS[spec.family](spec, render)
        if spec.family in catalog.ROOM_FAMILIES:   # Plan 3 T11: stencil contrast (before audit_built strips the tags)
            backing = zfight_room.stencil_backing(spec, BUILT.get(spec.name))
        zf = zfight.audit_built(spec, BUILT.get(spec.name))
        zf.update(zfight_room.contain_door_check(spec, BUILT.get(spec.name)))   # Plan 3 T11: the sliding leaves
        if spec.family in catalog.ROOM_FAMILIES:
            zf["stencil_backing"] = backing
        data["blocks"][spec.name]["zfight"] = zf
        bad = (zfight.decal_conflicts(zf["elements"]), zf["decal_geometry"], zf["leaf_coplanar"], zf["leaf_frame"],
               zf["coplanar"], zf["subpart_frame"])
        bad += tuple(zf.get(k, []) for k in ("contain_leaf_coplanar", "contain_leaf_frame", "contain_leaf_leaf",
                                             "stencil_backing"))
        print(f"  zfight: {len(zf['elements'])} decal elements; conflicts {[len(b) for b in bad]}")
        for b in bad:
            for row in b[:40]:
                print("   ", row)
        print(f"built {spec.name}")
    old = data["blocks"]
    # the pipeline's blocks always have an entry; other catalogue blocks (Plan 2 trays until Task 5 wires them into
    # the pipeline: Ruling P2-15) keep theirs once built
    data["blocks"] = {b.name: old[b.name] if old.get(b.name, {}).get("placement", {}).get("total") else
                      report.empty_entry(b) for b in catalog.CATALOGUE
                      if b in catalog.BLOCKS or old.get(b.name, {}).get("placement", {}).get("total")}
    report.write(config.REPORT_PATH, data)
    if do_export:
        from dc import export_models
        from se2model import export as EX
        ops = EX.vrt_ops()
        for name, b in BUILT.items():
            m = export_models.export_block(catalog.BY_NAME[name], b["lods"], b["collision"], b["boxes"], ops,
                                           subparts=b.get("subparts"), subpart_collision=b.get("subpart_collision"),
                                           mid=b.get("mid"))
            print(f"exported {name}: NF {[l['tris'] for l in m['nonfractured']['lods']]} tris, "
                  f"{m['nonfractured']['collision']['colliders']} colliders; Fractured "
                  f"{[l['tris'] for l in m['fractured']['lods']]} tris, zones "
                  f"{[z['id'] for z in m['fractured']['zones']]}"
                  + (f"; Damaged {[l['tris'] for l in m['damaged']['lods']]} tris, dents {m['damaged']['dent']}"
                     if m.get("damaged") else ""))
    if render and BUILT:
        # task-4 previews when servers were built (they need both open racks too), else the task-3 rack set;
        # DC_PREVIEW=task3|task4 forces one
        which = os.environ.get("DC_PREVIEW") or ("task4" if any(catalog.BY_NAME[n].family == "server" for n in BUILT)
                                                 else "task3")
        if which.startswith("plan2-t") and which != "plan2-t1":
            from dc import preview_trays
            preview_trays.render_all(BUILT, task=int(which[len("plan2-t"):]))
        elif which in ("plan3-t1", "p3t1"):
            from dc import preview_p3t1
            preview_p3t1.render_all(BUILT)
        elif which in ("plan3-t3", "p3t3"):   # the raised floor (its own set + room shots)
            from dc import preview_p3t3
            preview_p3t3.render_all(BUILT)
        elif which in ("plan3-t4", "p3t4"):   # the containment roof (its own set + room shots)
            from dc import preview_p3t4
            preview_p3t4.render_all(BUILT)
        elif which in ("plan3-t5", "p3t5"):   # the containment doors (their own set + room shots)
            from dc import preview_p3t5
            preview_p3t5.render_all(BUILT)
        elif which in ("plan3-t6", "p3t6"):   # the in-row cooler (its own set, fans, room shots)
            from dc import preview_p3t6
            preview_p3t6.render_all(BUILT)
        elif which in ("plan3-t7", "p3t7"):   # the PDU cabinet and strips (their own set + room shots)
            from dc import preview_p3t7
            preview_p3t7.render_all(BUILT)
        elif which in ("plan3-t8", "p3t8"):   # the signs and labels (their own set + room shots)
            from dc import preview_p3t8
            preview_p3t8.render_all(BUILT)
        elif which in ("plan3-t11", "p3t11"):   # the visual pass's audit set (DC_T11_PHASE=before|after)
            from dc import preview_p3t11
            preview_p3t11.render_all(BUILT)
        elif which == "showcase":   # the clean presentation stills and clips (dc/preview_showcase.py)
            from dc import preview_showcase
            preview_showcase.render_all(BUILT)
        elif which in ("plan3-t12", "p3t12"):   # the final hero set: the two-aisle hall (dc/preview_p3t12.py)
            from dc import preview_p3t12
            preview_p3t12.render_all(BUILT)
        elif which.startswith("plan3-t"):   # Plan 3 Task 2 on: the shots in the reference room (dc/preview_room.py)
            from dc import preview_room
            preview_room.render_task(BUILT, task=int(which[len("plan3-t"):]))
        elif which in ("plan2-t1", "p2t1"):
            from dc import preview_p2t1
            preview_p2t1.render_all(BUILT)
        elif which == "zfix":
            from dc import preview_zfix
            preview_zfix.render_all(BUILT)
        elif which == "merge":   # merge main -> plan3-room: racks (rails, strips, placard) and the CRAC
            from dc import preview_merge
            preview_merge.render_all(BUILT)
        elif which == "pfix":
            from dc import preview_pfix
            preview_pfix.render_all(BUILT)
        elif which == "vp1":
            from dc import preview_vp1
            preview_vp1.render_all(BUILT)
        elif which == "plan4":
            from dc import preview_plan4
            preview_plan4.render_all(BUILT)
        elif which == "task10":
            from dc import preview_task10
            preview_task10.render_all(BUILT)
        elif which == "task9":
            from dc import preview_task9
            preview_task9.render_all(BUILT)
        elif which == "task8":
            from dc import preview_task8
            preview_task8.render_all(BUILT)
        elif which == "task7":
            from dc import preview_task7
            preview_task7.render_all(BUILT)
        elif which == "task6":
            from dc import preview_task6
            preview_task6.render_all(BUILT)
        elif which == "task5":
            from dc import preview_task5
            preview_task5.render_all(BUILT)
        elif which == "task4":
            from dc import preview_servers
            preview_servers.render_all(BUILT)
        else:
            from dc import preview
            preview.render_all(BUILT)
    print(f"wrote {config.REPORT_PATH} ({len(specs)} blocks)")


def _argv():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def _run_windowed():
    import bpy
    import traceback
    try:
        main(_argv())
        print("=== DC BUILD DONE ===")
    except BaseException:  # noqa: BLE001 (SystemExit too: the window must still close)
        traceback.print_exc()
        print("=== DC BUILD FAILED ===")
    finally:
        if not os.environ.get("DC_NO_QUIT"):
            bpy.ops.wm.quit_blender()
    return None


if __name__ == "__main__":
    import bpy
    if bpy.app.background:
        main(_argv())
    else:   # windowed: wait for the GPU context the VRAGE add-on needs, then quit
        bpy.app.timers.register(_run_windowed, first_interval=2.0)
