"""The room layout: every block of a reference data-centre room placed in world cells (plain Python, no bpy).

World frame: Blender axes, metres. x runs along the rack rows, y across the aisle (the aisle is centred on y = 0),
z up from the deck under the raised floor (z = 0). World cell (i, j, k) is the 0.25 m cube [0.25 i, 0.25 (i + 1)) x
... ; a block's box corners always lie on that grid.

A placed block (Placed) is its catalogue name, the world position of its cell-box centre (= its model origin) and a
yaw in quarter turns about world +Z (counter-clockwise seen from above). Its local frame is the model frame of every
builder here (+Y = front = game Forward, Z up), so a rack at yaw 0 faces +y and one at yaw 2 faces -y.

Cell sets come in two frames:
  * local cells: the game-frame indices of catalog.bounds (x, y up, z across; z grows toward the BACK, the frame of
    rack.SLOT_CELLS / PDU_CELLS / FREE_CELLS and of build_report.json "free_cells");
  * world cells: (i, j, k) as above.
world_cells() maps one to the other; occupied() is a block's box minus its report's free cells; conflicts() lists the
placed pairs whose occupied cells overlap. The coupling tests run on pure_report() (racks: rack.FREE_CELLS; Plan 2
tray pieces: the cells their cable plan leaves empty) and, once built, on the measured build_report.json.

reference_room() is the room every Plan 3 task's in-context previews (dc/preview_room.py) and coupling tests use:
two facing rows (racks, an in-row CRAC, racks, the PDU cabinet) on a raised floor, a contained hot or cold aisle (roof
panels over every 1.0 m, a sliding door at each end with its aisle sign), PDU strips and a label on every rack, and
Plan 2's tray run overhead (a Drop into every rack, Straights over the in-row units, rod hangers to one ceiling).
"""
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple

from . import catalog
from . import dims as DM

CELL = DM.CELL
PITCH = 1.0                      # rack pitch along a row (every in-row unit is 4 cells wide)
UNIT_H = 2.5                     # full-rack / in-row unit height (10 cells)
DOOR_T = CELL                    # the containment door's slice just beyond the row end
TRAY_DENSITY = "Full"            # the reference room's tray load (Drops and Straights must match across joints)
SERVICE = 1.0                    # the walkway beyond the rows' outer faces (floor band)
ROW_BAND = 1.5                   # the floor band under a row (the 1.25 m deep units sit in it, aisle edge flush)
END_MARGIN = 3.0                 # floor beyond each row end (the door, its sign, room to stand and look)

STACK = {
    "floor_top": DM.RF_H,          # the raised floor's top plane: racks, CRAC and doors stand on it
    "rack_top": DM.RF_H + UNIT_H,                          # full racks and in-row units
}
STACK["roof"] = (STACK["rack_top"] - CELL, STACK["rack_top"])   # the roof panels fill the aisle's top cell
STACK["door_top"] = STACK["rack_top"]                           # the door header is flush with the rack tops
STACK["tray_bottom"] = STACK["rack_top"] + DM.TRAY_HANG         # Plan 2: the tray's lowest cell plane
STACK["tray_top"] = STACK["tray_bottom"] + CELL
STACK["ceiling"] = STACK["tray_top"] + CELL * catalog.ROD_LENGTHS["100"]   # the rod hangers' anchor plane


@dataclass(frozen=True)
class Placed:
    name: str
    origin: Tuple[float, float, float]   # world position of the block's cell-box centre (metres)
    yaw: int = 0                         # quarter turns about world +Z
    tag: str = ""                        # what it is in the room ("A1" = row A rack 1, "A1/PDU-A", "west/sign", ...)


# ---------------------------------------------------------------------------------------------------- names
def door_name(w: float) -> str:
    return f"DC_Contain_Door_{round(w * 100):03d}"


def roof_name(w: float) -> str:
    return f"DC_Contain_Roof_{round(w * 100):03d}"


def aisle_width(spec) -> float:
    """The aisle a containment block closes: a door is 2W wide (its leaves park beside the opening), a roof W deep."""
    if spec.family == "contain_door":
        return spec.cells[0] / 8
    if spec.family == "contain_roof":
        return spec.cells[2] / 4
    raise ValueError(f"{spec.name} is not a containment block")


def spec(p: Placed):
    return catalog.BY_NAME[p.name]


# ---------------------------------------------------------------------------------------------------- geometry
def rot(v, yaw: int):
    """v turned yaw quarter turns about +Z (exact: no trigonometry)."""
    x, y, z = v
    for _ in range(yaw % 4):
        x, y = -y, x
    return (x, y, z)


def _add(a, b):
    return tuple(p + q for p, q in zip(a, b))


def size(s) -> Tuple[float, float, float]:
    """A spec's box in metres along its local Blender axes (x, y across = front/back, z up)."""
    return (CELL * s.cells[0], CELL * s.cells[2], CELL * s.cells[1])


def box(p: Placed):
    """World (lo, hi) corners of a placed block's cell box."""
    sx, sy, sz = size(spec(p))
    if p.yaw % 2:
        sx, sy = sy, sx
    lo = tuple(round(o - h / 2, 9) for o, h in zip(p.origin, (sx, sy, sz)))
    hi = tuple(round(o + h / 2, 9) for o, h in zip(p.origin, (sx, sy, sz)))
    return lo, hi


def _shift(n):
    return CELL / 2 if n % 2 == 0 else 0.0   # the game's grid-align step (se2model.placement.shift_for_bounds)


def local_centre(s, cell) -> Tuple[float, float, float]:
    """Centre of a game-frame local cell (catalog.bounds indices) in the block's centred Blender frame."""
    gx, gy, gz = cell
    nx, ny, nz = s.cells
    return (CELL * gx - _shift(nx), -(CELL * gz - _shift(nz)), CELL * gy - _shift(ny))


def plan_cell_to_local(s, cell) -> Tuple[int, int, int]:
    """A box-corner cell (ix, iy, iz; Blender axes, the frame of tray_plan.occupied_cells) -> game-frame local."""
    (x0, y0, _), (_, _, z1) = catalog.bounds(s)
    ix, iy, iz = cell
    return (x0 + ix, y0 + iz, z1 - iy)


def _index(c):
    return int(math.floor(c / CELL + 1e-6))


def world_cells(p: Placed, local_cells: Optional[Iterable] = None) -> Set[Tuple[int, int, int]]:
    """World cell indices of a placed block's whole box, or of the given game-frame local cells."""
    if local_cells is None:
        lo, hi = box(p)
        r = [range(_index(a), _index(b - CELL) + 1) for a, b in zip(lo, hi)]
        return {(i, j, k) for i in r[0] for j in r[1] for k in r[2]}
    s = spec(p)
    out = set()
    for c in local_cells:
        w = _add(p.origin, rot(local_centre(s, c), p.yaw))
        out.add(tuple(_index(v) for v in w))
    return out


def _blocks(report):
    return (report or {}).get("blocks", report or {})


def free_cells(name: str, report: dict) -> list:
    e = _blocks(report).get(name) or {}
    return (e.get("placement") or {}).get("free_cells") or []


def occupied(p: Placed, report: dict) -> Set[Tuple[int, int, int]]:
    """The block's box minus the free cells its report lists (none listed: the full box)."""
    return world_cells(p) - world_cells(p, free_cells(p.name, report))


def conflicts(placed: List[Placed], report: dict) -> List[Tuple[str, str, tuple]]:
    """(name a, name b, overlapping world cells) for every pair of placed blocks whose occupied cells overlap."""
    owner = {}
    for i, p in enumerate(placed):
        for c in occupied(p, report):
            owner.setdefault(c, []).append(i)
    pairs = {}
    for c, ids in owner.items():
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                pairs.setdefault((ids[a], ids[b]), []).append(c)
    return [(placed[a].name, placed[b].name, tuple(sorted(cs))) for (a, b), cs in sorted(pairs.items())]


def pure_report(names: Iterable[str]) -> dict:
    """A report-shaped occupancy without Blender: racks free rack.FREE_CELLS, Plan 2 tray pieces the cells their
    cable plan leaves empty; every other block occupies its whole box."""
    from . import rack, tray_plan
    out = {}
    for n in sorted(set(names)):
        s = catalog.BY_NAME[n]
        if s.family == "rack":
            free = rack.FREE_CELLS(s)
        elif s.family in ("tray", "trayrods"):
            occ = {plan_cell_to_local(s, c) for c in tray_plan.occupied_cells(tray_plan.plan(s))}
            (x0, y0, z0), (x1, y1, z1) = catalog.bounds(s)
            free = [(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)
                    if (x, y, z) not in occ]
        else:
            continue
        out[n] = {"placement": {"free_cells": [list(c) for c in free]}}
    return {"blocks": out}


# ---------------------------------------------------------------------------------------------------- the room
def row_units(racks: int = 4) -> List[str]:
    """One row along +x: the racks with the in-row CRAC between their halves (an in-row cooler serves the racks
    either side of it), and the PDU cabinet at the far (east) end, where the power comes in."""
    a = (racks + 1) // 2
    return ["rack"] * a + ["crac"] + ["rack"] * (racks - a) + ["pdu"]


def floor_extent(aisle_w: float = 1.5, racks: int = 4):
    """(x0, x1, y0, y1) of the raised floor: the rows plus END_MARGIN at each end; across, the aisle, a ROW_BAND
    under each row and a SERVICE walkway beyond it. Every edge is on the 0.5 m tile grid."""
    L = PITCH * len(row_units(racks))
    Y = aisle_w / 2 + ROW_BAND + SERVICE
    return (-END_MARGIN, L + END_MARGIN, -Y, Y)


def _floor(aisle_w, aisle, racks):
    """Tiles: 1.0 m blocks, and a row of 0.5 m blocks where a band's width leaves 0.5 m. Perforated tiles where the
    chilled air comes up, along the rows only: the contained cold aisle, or for a hot aisle the walkways in front of
    the rows."""
    x0, x1, _, Y = floor_extent(aisle_w, racks)
    h = aisle_w / 2
    bands = [(-h, h, "aisle")]
    for sg in (-1, 1):
        for a, b, kind in ((h, h + ROW_BAND, "row"), (h + ROW_BAND, Y, "service")):
            bands.append((min(sg * a, sg * b), max(sg * a, sg * b), kind))
    perf = "aisle" if aisle == "cold" else "service"
    out = []
    zc = STACK["floor_top"] / 2
    L = PITCH * len(row_units(racks))
    for y0, y1, kind in sorted(bands):
        n_full = int(math.floor((y1 - y0) / 1.0 + 1e-9))
        rows = [(y0 + k, 1.0) for k in range(n_full)]
        if y1 - y0 - n_full > 1e-9:
            rows.append((y0 + n_full, 0.5))
        for ry, t in rows:
            for i in range(int(round((x1 - x0) / t))):
                x = x0 + t * (i + 0.5)
                v = "Perf" if kind == perf and 0.0 < x < L else "Solid"    # along the rows only
                out.append(Placed(f"DC_Floor_{v}_{'100' if t == 1.0 else '050'}", (x, ry + t / 2, zc), 0,
                                  f"floor/{kind}"))
    return out


def _unit_name(kind):
    return {"pdu": "DC_PDU_Cabinet", "crac": "DC_CRAC", "rack": "DC_Rack42_SplitFront"}[kind]


def _strip_name(rack_spec, feed):
    return f"DC_PDU_Rack{42 if rack_spec.cells[1] == 10 else 24}_{feed}"


def reference_room(aisle_w: float = 1.5, aisle: str = "cold", racks: int = 4, trays: bool = True,
                   labels: bool = True, label_side: str = "front") -> List[Placed]:
    """The reference room (see the module docstring). Row A stands at y < 0, row B at y > 0; on a cold aisle the
    rows face each other across it (fronts on y = -+w/2), on a hot aisle they are turned so their backs face it.
    labels: the rack labels and the aisle signs; trays: Plan 2's overhead run (and the hanging aisle sign).
    label_side: "front" (default) puts every rack label on its rack's front pad, between the Drop's waterfalls
    (Review Focus 4, photo 1); "aisle" on the edge facing the contained aisle, "open" on the edge facing the open
    aisle (Plan 3 T11 guidance, rack_label). "aisle" / "open" follow the aisle type (label_pad): the racks face a
    contained cold aisle and turn their backs to a contained hot one."""
    if aisle not in ("cold", "hot"):
        raise ValueError(f"aisle must be 'cold' or 'hot', not {aisle!r}")
    if not any(abs(aisle_w - w) < 1e-9 for w in DM.AISLE_WIDTHS):
        raise ValueError(f"aisle width {aisle_w} not in {DM.AISLE_WIDTHS}")
    if racks < 1:
        raise ValueError("a row needs at least one rack")
    h = aisle_w / 2
    units = row_units(racks)
    L = PITCH * len(units)
    zc = STACK["floor_top"] + UNIT_H / 2
    out = _floor(aisle_w, aisle, racks)
    tray_rows = []
    for row, sg in (("A", -1), ("B", 1)):
        faces_aisle = aisle == "cold"
        yaw = (0 if sg < 0 else 2) if faces_aisle else (2 if sg < 0 else 0)
        yc = sg * (h + 0.625)
        k = 0
        for i, kind in enumerate(units):
            x = PITCH * (i + 0.5)
            if kind == "rack":
                k += 1
                tag = f"{row}{k}"
            else:
                tag = f"{row}/{kind}"
            u = Placed(_unit_name(kind), (x, yc, zc), yaw, tag)
            out.append(u)
            us = spec(u)
            if kind == "rack":
                from . import rack as R
                for feed in ("A", "B"):
                    cs = R.PDU_CELLS(us, feed)
                    lc = tuple(sum(local_centre(us, c)[a] for c in cs) / len(cs) for a in range(3))
                    out.append(Placed(_strip_name(us, feed), _add(u.origin, rot(lc, yaw)), yaw, f"{tag}/PDU-{feed}"))
                if labels:
                    out.append(rack_label(u, label_pad(aisle, label_side)))
            tray_rows.append((u, kind))
    # the containment: a roof panel over every 1.0 m of the aisle, a door at each end with its sign on the header
    w_door, w_roof = door_name(aisle_w), roof_name(aisle_w)
    zr = sum(STACK["roof"]) / 2
    out += [Placed(w_roof, (PITCH * (i + 0.5), 0.0, zr), 0, f"roof/{i + 1}") for i in range(len(units))]
    for end, x, yaw in (("west", -DOOR_T / 2, 1), ("east", L + DOOR_T / 2, 3)):   # door fronts face out of the aisle
        out.append(Placed(w_door, (x, 0.0, STACK["floor_top"] + UNIT_H / 2), yaw, f"{end}/door"))
        if labels:
            xs = x + (-DOOR_T if end == "west" else DOOR_T)
            out.append(Placed("DC_Sign_Aisle", (xs, 0.0, STACK["door_top"] - CELL / 2), yaw, f"{end}/sign"))
    if trays:
        out += _trays(tray_rows, L, labels)
    return out


def label_pad(aisle: str, label_side: str = "front") -> int:
    """The rack-top pad (+1 front, -1 back) a label takes in the reference room: the racks FACE a contained cold aisle
    and turn their BACKS to a contained hot one, so the contained ("aisle") edge is the front pad on a cold aisle and
    the back pad on a hot one, and the open edge the other."""
    if label_side == "front":
        return 1
    if label_side not in ("aisle", "open"):
        raise ValueError(f"label_side must be 'front', 'aisle' or 'open', not {label_side!r}")
    toward_aisle = 1 if aisle == "cold" else -1
    return toward_aisle if label_side == "aisle" else -toward_aisle


def rack_label(u: Placed, side: int = 1) -> Placed:
    """The rack label on a full rack's top: on its front label pad (side +1, between the Drop's waterfalls, the
    reference room's) or its back pad (side -1, the label turned to face the rack's back).
    Plan 3 T11 guidance: in a CONTAINED aisle the roof covers the rack tops' aisle edge (the labels there are above the
    roof, unreadable from inside), so the labels go on the edge facing the OPEN aisle: side -1 on the racks of a
    contained cold aisle, +1 on those of a contained hot aisle (whose fronts face the open cold aisle)."""
    lc = (sum(DM.LABEL_X) / 2, side * sum(DM.LABEL_Y) / 2, UNIT_H / 2 + CELL / 2)
    return Placed("DC_Sign_Rack", _add(u.origin, rot(lc, u.yaw)), (u.yaw + (0 if side > 0 else 2)) % 4,
                  f"{u.tag}/label")


def _trays(units, L, labels):
    """Plan 2's run over each row: a Drop into every rack (its waterfalls land in the rack's top-entry brushes), two
    0.5 m Straights over each in-row unit, a 1.0 m rod hanger over every piece up to the ceiling plane; and the
    hanging aisle sign mid-aisle on its own (turned) rod hanger, at tray height."""
    out = []
    drop, straight, rods = f"DC_Tray_Drop_{TRAY_DENSITY}", f"DC_Tray_StraightS_{TRAY_DENSITY}", "DC_TrayRods_100"
    yt = DM.TRAY_RACK_Y                          # the tray centreline, rack-local (in front of the rack centre)
    zb = STACK["tray_bottom"] - STACK["rack_top"] + UNIT_H / 2   # the tray floor cell's bottom, unit-local
    zr = zb + CELL + CELL * catalog.ROD_LENGTHS["100"] / 2       # the rods' centre, unit-local
    for u, kind in units:
        if kind == "rack":
            pieces = [(drop, (0.0, yt + CELL / 2, UNIT_H / 2 + 1.5 * CELL))]   # 3x3 cells: rack top .. tray top
        else:
            pieces = [(straight, (sx * CELL, yt, zb + CELL / 2)) for sx in (-1, 1)]
        for name, lc in pieces:
            out.append(Placed(name, _add(u.origin, rot(lc, u.yaw)), u.yaw, f"{u.tag}/tray"))
            out.append(Placed(rods, _add(u.origin, rot((lc[0], yt, zr), u.yaw)), u.yaw, f"{u.tag}/rods"))
    if labels:
        # the sign reads along the aisle (its face across it, yaw 1); its hanger is turned 90 deg TO THE SIGN (yaw 0,
        # like the trays' own hangers), so the hanger's two rods (its local y = +-ROD_S) land on the sign's two rod
        # plates at x = +-ROD_S along its face (Plan 3 Task 8, the T2 carry; dc/signs.py rod_plates)
        zs = STACK["tray_bottom"] + CELL / 2
        out.append(Placed("DC_Sign_AisleHang", (L / 2, 0.0, zs), 1, "aisle/hang"))
        out.append(Placed(rods, (L / 2, 0.0, STACK["tray_top"] + CELL * catalog.ROD_LENGTHS["100"] / 2), 0,
                          "aisle/hang/rods"))
    return out


# ---------------------------------------------------------------------------------------------------- the hall
UNIT_D = 1.25                    # the in-row units' depth (rack, CRAC, PDU cabinet): row B's back-to-front


def hot_offset(cold_w: float = 1.5, hot_w: float = 1.0) -> float:
    """How far (+y) the hall's hot aisle centre lies from its cold aisle centre: row B stands with its front on the
    cold aisle and its back on the hot one, so the hot reference room's row A lands exactly on the cold room's row B."""
    return cold_w / 2 + UNIT_D + hot_w / 2


def shared_row_doors_fit(cold_w: float, hot_w: float) -> bool:
    """Whether both aisles of a shared row can take their end doors at the same row end: each door's leaves park in
    pockets W/2 beyond its aisle (Decision 2: the door is 2W wide), so on row B's end face the cold door's pocket
    (cold_w / 2) and the hot door's (hot_w / 2) must fit in the unit's 1.25 m depth. 1.5 + 1.0 fits exactly; two
    1.5 m (or any 2.0 m) aisles do not: their pockets overlap (Plan 3 Task 12 finding)."""
    return cold_w / 2 + hot_w / 2 <= UNIT_D + 1e-9


def hall_extent(cold_w: float = 1.5, hot_w: float = 1.0, racks: int = 4):
    """(x0, x1, y0, y1) of two_aisle_room's raised floor: the cold room's floor up to its row B band, then whole 1.0 m
    tiles (a 0.5 m one at the end) past row C's walkway."""
    x0, x1, y0, _ = floor_extent(cold_w, racks)
    start = cold_w / 2 + ROW_BAND
    end = hot_offset(cold_w, hot_w) + floor_extent(hot_w, racks)[3]
    return (x0, x1, y0, start + math.ceil((end - start) / 0.5 - 1e-9) * 0.5)


def two_aisle_room(cold_w: float = 1.5, hot_w: float = 1.0, racks: int = 4) -> List[Placed]:
    """The Plan 3 Task 12 hero hall: three rows and two contained aisles, the way real halls alternate them. Rows A
    and B face the contained COLD aisle (y = 0; the reference room, labels on the front pads between the waterfalls);
    row B's back and row C's back close the contained HOT aisle (y = hot_offset). Built from the two reference rooms:
    the hot one shifted +y so its row A IS the cold room's row B (dropped, with its strips, labels and trays), its row B
    renamed C, its other tags prefixed "hot/" ("hot/west/door", "hot/roof/1", ...), its rack labels on the open edge
    (row C's fronts face the outer walkway, label_side="open"). One raised floor: the cold room's tiles up to its row B
    band (perforated in the cold aisle), then 1.0 m tiles, perforated in front of row C (the hot room's walkway).
    The aisles must pass shared_row_doors_fit (both doors bolt to row B's end racks)."""
    if not shared_row_doors_fit(cold_w, hot_w):
        raise ValueError(f"a {cold_w} m cold and a {hot_w} m hot aisle: their doors' pockets overlap on row B's ends")
    dy = hot_offset(cold_w, hot_w)
    start = cold_w / 2 + ROW_BAND
    out = [p for p in reference_room(cold_w, "cold", racks)
           if not (p.tag.startswith("floor/") and p.origin[1] > start)]
    for p in reference_room(hot_w, "hot", racks, label_side="open"):
        if p.tag.startswith("floor/") or p.tag.startswith("A"):
            continue
        tag = "C" + p.tag[1:] if p.tag.startswith("B") else f"hot/{p.tag}"
        out.append(Placed(p.name, (p.origin[0], p.origin[1] + dy, p.origin[2]), p.yaw, tag))
    x0, x1, _, y1 = hall_extent(cold_w, hot_w, racks)
    L = PITCH * len(row_units(racks))
    walk = dy + hot_w / 2 + ROW_BAND              # row C's walkway starts here (the hot room's service band)
    zc = STACK["floor_top"] / 2
    y = start
    while y < y1 - 1e-9:
        t = 1.0 if y1 - y >= 1.0 - 1e-9 else 0.5
        for i in range(int(round((x1 - x0) / t))):
            x = x0 + t * (i + 0.5)
            v = "Perf" if y + t / 2 > walk and 0.0 < x < L else "Solid"
            out.append(Placed(f"DC_Floor_{v}_{'100' if t == 1.0 else '050'}", (x, y + t / 2, zc), 0, "floor/hall"))
        y += t
    return out
