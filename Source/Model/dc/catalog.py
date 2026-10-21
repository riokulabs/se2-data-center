"""The Data Center block catalogue (names, sizes, vanilla sources).

CATALOGUE holds every block the mod defines. BLOCKS is the part of it that the definitions pipeline already carries
(clones, staging, names, menu, icons, recipes): the families in PIPELINE_FAMILIES. A family joins the pipeline when
its definitions are wired (today every family is, so BLOCKS == CATALOGUE); until then
its blocks are catalogued (cells, sources, plans, builds by name) but invisible to the pipeline's whole-catalogue loops
and tests. Within the pipeline, the menu (dc/menu.py GROUPS) and the cost rule (dc/recipes.py costed) cover every
family, the trays and the room pieces included."""
from dataclasses import dataclass
from typing import Optional, Tuple

from .tray_lanes import DENSITIES as TRAY_DENSITIES   # the cable densities (dc/tray_lanes.py is plain Python)

PANEL = "Blocks/Walls/Inserts/Panel"
DOOR = "Blocks/Doors/SlideDoorNarrow/250"
PIPES = "Blocks/Walls/Inserts/Pipes"          # WallInsertPipes: the trays' clone source
STRUT = "Blocks/Truss/Struts/Long"            # StructuralSupportStraight: the rod hangers' clone source


@dataclass(frozen=True)
class BlockSpec:
    name: str
    family: str  # "rack" | "server" | "tray" | "trayrods" | one of ROOM_FAMILIES
    cells: Tuple[int, int, int]  # (x, y, z)
    vanilla_source: Optional[str]  # path under Vanilla/Assets, e.g. "Blocks/Timer/50"
    copy_from: Optional[str]  # vanilla name prefix, e.g. "Timer50"
    variant: str
    functional: bool
    density: Optional[str] = None  # trays: the cable density (dc/tray_lanes.DENSITIES); the Reducer's is its a side


def _rack(height, variant, source, copy_from, functional):
    return BlockSpec(f"DC_Rack{height}_{variant}", "rack", (4, 10 if height == 42 else 5, 5),
                     source, copy_from, variant, functional)


# Sizes: racks 4 cells (1.0 m) wide so the 2-cell server slot is centered;
# servers 3 cells (0.75 m) deep so they sit centered in the 5-cell rack depth.
CORE_BLOCKS = []   # racks and servers
for _h in (42, 24):
    CORE_BLOCKS.append(_rack(_h, "Open", PANEL, "WallInsertPanel", False))
    CORE_BLOCKS.append(_rack(_h, "SplitFront", DOOR, "SlidingDoorNarrow250", True))
    CORE_BLOCKS.append(_rack(_h, "SplitFrontRear", DOOR, "SlidingDoorNarrow250", True))


def _srv(name, source, copy_from, variant, functional, cells=(2, 1, 3)):
    return BlockSpec(name, "server", cells, source, copy_from, variant, functional)


CORE_BLOCKS += [
    _srv("DC_Srv_Timer", "Blocks/Timer/50", "Timer50", "Timer", True),
    _srv("DC_Srv_EventCtl", "Blocks/EventController/100", "EventController", "EventCtl", True),
    _srv("DC_Srv_KVM", "Blocks/ControlPanel/25", "ControlPanel25", "KVM", True),
    _srv("DC_Srv_UPS", "Blocks/Batteries/Battery/50", "Battery50", "UPS", True, cells=(2, 2, 3)),
    _srv("DC_Srv_Status", "Blocks/LCDPanels/LCD/50", "LCDFlat50", "Status", True),
    _srv("DC_Srv_Programmable", PANEL, "WallInsertPanel", "Programmable", True),   # a Powerable blade
    _srv("DC_Srv_Compute", PANEL, "WallInsertPanel", "Compute", False),
    _srv("DC_Srv_Storage", PANEL, "WallInsertPanel", "Storage", False),
    _srv("DC_Srv_Switch", PANEL, "WallInsertPanel", "Switch", False),
    _srv("DC_Srv_Blank", PANEL, "WallInsertPanel", "Blank", False),
]

# ---------------------------------------------------------------------------------------------------- cable trays
# Cells are (along X, up Z, across Y) like every block here; the cable plans (dc/tray_plan.py)
# lay their geometry out in exactly these boxes.
TRAY_SHAPES = ("StraightS", "StraightL", "TurnH", "TurnUp", "TurnDown", "Tee", "Cross")   # x 4 densities
TRAY_CELLS = {
    "StraightS": (2, 1, 2),
    "StraightL": (6, 1, 2),
    "TurnH": (3, 1, 3),
    "TurnUp": (2, 2, 2),
    "TurnDown": (2, 2, 2),
    "Tee": (4, 1, 3),
    "Cross": (4, 1, 4),
    "Reducer": (2, 1, 2),
    "Drop": (4, 3, 3),
    "Chute": (4, 5, 1),
}
ROD_LENGTHS = {"025": 1, "100": 4, "200": 8}                 # rod hanger name suffix -> height in cells


def _tray(shape, density=None):
    name = f"DC_Tray_{shape}" + (f"_{density}" if density else "")
    return BlockSpec(name, "tray", TRAY_CELLS[shape], PIPES, "WallInsertPipes", shape, False, density)


TRAYS = [_tray(_s, _d) for _s in TRAY_SHAPES for _d in TRAY_DENSITIES]
TRAYS += [_tray("Drop", _d) for _d in TRAY_DENSITIES[1:]]       # no empty Drop: no lane to feed it (v1 Q5)
TRAYS += [_tray("Reducer", _d) for _d in TRAY_DENSITIES[1:]]    # steps its a side's density down one level
TRAYS.append(_tray("Chute"))
TRAYS += [BlockSpec(f"DC_TrayRods_{_k}", "trayrods", (2, _n, 2), STRUT, "StructuralSupportStraight", "Rods", False)
          for _k, _n in ROD_LENGTHS.items()]

# ---------------------------------------------------------------------------------------------------- room pieces
# Each family joins PIPELINE_FAMILIES once its definitions are wired; until
# then its blocks are catalogued (cells, sources, names, clones, the room layout in dc/room.py) but stay out of the
# pipeline's whole-catalogue loops. The PDU strips and the PDU cabinet are decorative (the wall-panel chain); the CRAC
# keeps the gyroscope's powered chain; doors and signs keep their vanilla door / LCD behavior.
CATWALK = "Blocks/Catwalks/CatwalkSquareBase/250"   # CatwalkSquareBase250: the raised floor
GYRO = "Blocks/Gyroscopes/Gyroscopes/250"           # Gyroscope250: the CRAC
DECK = "Blocks/DeckPanel/250"                       # DeckPanel250: the containment roof
NARROW_LCD = "Blocks/LCDPanels/NarrowLCD/50"        # LCDNarrow50: the signs
ROOM_FAMILIES = ("floor", "crac", "pdu_cabinet", "pdu_strip", "contain_door", "contain_roof", "sign")
AISLE_CELLS = {"100": 4, "150": 6, "200": 8}          # aisle width (name suffix) -> cells (dims.AISLE_WIDTHS)


def _room(name, family, cells, source, copy_from, variant, functional):
    return BlockSpec(name, family, cells, source, copy_from, variant, functional)


ROOM = []
for _k, _n in (("050", 2), ("100", 4)):
    ROOM += [_room(f"DC_Floor_{_v}_{_k}", "floor", (_n, 1, _n), CATWALK, "CatwalkSquareBase250", _v, False)
             for _v in ("Solid", "Perf")]
ROOM += [
    _room("DC_CRAC", "crac", (4, 10, 5), GYRO, "Gyroscope250", "CRAC", True),
    _room("DC_PDU_Cabinet", "pdu_cabinet", (4, 10, 5), PANEL, "WallInsertPanel", "Cabinet", False),
]
for _h, _n in ((42, 8), (24, 4)):   # zero-U strips in the racks' rear PDU columns (rack.PDU_CELLS)
    ROOM += [_room(f"DC_PDU_Rack{_h}_{_f}", "pdu_strip", (1, _n, 1), PANEL, "WallInsertPanel", _f, False)
             for _f in ("A", "B")]
ROOM += [_room(f"DC_Contain_Door_{_k}", "contain_door", (2 * _n, 10, 1), DOOR, "SlidingDoorNarrow250", "Door", True)
         for _k, _n in AISLE_CELLS.items()]    # 2W wide: the two W/2 leaves slide into pockets beside the opening
ROOM += [_room(f"DC_Contain_Roof_{_k}", "contain_roof", (4, 1, _n), DECK, "DeckPanel250", "Roof", False)
         for _k, _n in AISLE_CELLS.items()]    # one rack pitch (1.0 m) along the row x the aisle width
ROOM += [_room(f"DC_Sign_{_v}", "sign", _c, NARROW_LCD, "LCDNarrow50", _v, True)
         for _v, _c in (("Aisle", (4, 1, 1)), ("AisleHang", (4, 1, 2)), ("Rack", (2, 1, 1)))]

# the trays and the room families (menu, recipes, icons, unlock) are all wired, so today BLOCKS == CATALOGUE
PIPELINE_FAMILIES = ("rack", "server", "tray", "trayrods") + ROOM_FAMILIES
CATALOGUE = CORE_BLOCKS + TRAYS + ROOM
BLOCKS = [b for b in CATALOGUE if b.family in PIPELINE_FAMILIES]   # the definitions pipeline's view
BY_NAME = {b.name: b for b in CATALOGUE}
# A room family's models and definitions can be staged before it joins PIPELINE_FAMILIES (which brings its
# build-menu group, recipe, icon and unlock). STAGED = what dc/integration.py stages: BLOCKS plus any staged room
# family not yet in the pipeline (none today).
STAGED_ROOM_FAMILIES = ("floor", "contain_roof", "contain_door", "crac")
STAGED_ROOM_FAMILIES += ("pdu_cabinet", "pdu_strip")
STAGED_ROOM_FAMILIES += ("sign",)
STAGED = BLOCKS + [b for b in ROOM if b.family in STAGED_ROOM_FAMILIES and b not in BLOCKS]


def bounds(spec: BlockSpec) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Inclusive cell-index bounds ((x0,y0,z0),(x1,y1,z1)) for placement.analyse, centred like the game."""
    lo, hi = [], []
    for n in spec.cells:
        a = -((n - 1) // 2)
        lo.append(a)
        hi.append(a + n - 1)
    return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


def expand(patterns):
    """Block names for command-line patterns (R12): each argument is ONE name or shell-style glob over the catalogue
    ("DC_*", "DC_Tray_Turn?_Full"), quoted so the shell leaves it alone; catalogue order, no duplicates. A pattern
    matching nothing raises (a typo must not check zero blocks silently)."""
    from fnmatch import fnmatchcase
    picked = set()
    for p in patterns:
        hits = {b.name for b in CATALOGUE if fnmatchcase(b.name, p)}
        if not hits:
            raise ValueError(f"no block matches {p!r}")
        picked |= hits
    return [b.name for b in CATALOGUE if b.name in picked]
