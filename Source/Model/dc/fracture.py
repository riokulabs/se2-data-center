"""Real fracture models for the racks, servers and cable trays and the room's raised floor, containment roof and
containment doors, vanilla-style.

Every DC_Rack*, DC_Srv_*, DC_Tray* / DC_TrayRods*, DC_Floor_*, DC_Contain_Roof_* and DC_Contain_Door_* block gets a
FRACTURE PLAN (this module, plain Python) that the exporter turns into a cut Fractured model and a dented Damaged model (fracture_mesh.py, Blender),
the way vanilla ships them (measured on Timer50 / Battery50 / EventController100, tools/vanilla-ref, read-only):

  Fractured  per zone "Fracture_NN": the skin (Group Fracture_NN), the decals / stencils / lamps (Group
             Fracture_NN_Hide, AlwaysHidden while under construction) and the BREAK FACES: closed caps over every
             cross-section the seam cuts, vanilla FracturedMaterial01 (0f2772fd), Group Fracture_NN,
             ConstructionMeshType Split / HiddenUntilSecondSequenceStart / preset Fracture (vanilla "Fracture_NN_Cut").
             The cut line is jagged (cut edges subdivided where long, cut vertices jittered along the seam normal by
             a smooth noise of their position): both zones share those vertices, so the intact model stays closed.
             One convex collider per zone (glTF node "Fracture_NN"), shaped to the zone's geometry.
  Damaged    (vanilla "Deformed") the same meshes, mesh parts and groups, dented by a smooth position-based field
             (no tears: coincident vertices move together; mostly inward; pinned on the model's bounding box so the
             render bounds, ports and mount faces never move), large flat faces densified so a dent can show. Its
             .model maps the lamp slots to EmissiveOffBroken and the screens to Display01Broken / LCDScreen_Off,
             exactly the swaps vanilla's Deformed models make (DAMAGED_SLOTS).

Zones are convex regions of the block frame (Blender: X width, +Y front / tray plan y, Z up), each an intersection of
half spaces; a seam is the plane between two zones (Seam: one or several zones on each side). Every rack, server and
tray has a plan. Fracture_01 is the key zone on functional and hung blocks; only functional blocks (servers) have it
critical.
A critical zone does NOT destroy the block: a dead critical zone makes BreakableBlockComponent.IsBroken true, which
switches a functional block off (FunctionalBlockComponent.RecomputeFunctional) and shows "Broken"; the block is
destroyed only when its volume-weighted integrity falls below its DestructionThreshold (0.3 by default,
CubeBlockComponent.cs:4388-4400). Racks and cable trays are structural (CriticalFractures = []): no
critical zone, except a door rack's columns (the hinges).
The rod hangers and the Chute stay unfractured and non-breakable (UNFRACTURED).

    | family / shape        | zones (critical first)                                          | seams          |
    | full rack (42U)       | 01 / 02 plinth front / rear, 03-06 columns lower / upper, 07 / 08 top tray front /
    |                       | rear (door racks: 03-06 critical, open rack: none)              | y, z, z, z, y  |
    | half rack (24U)       | 01 plinth, 02 roof, 03 / 04 columns (door racks: 03 / 04 critical) | z, x, x     |
    | 6U servers            | 01 core, 02 front service module, 03 rear chassis               | y, y = lid gap |
    | UPS (12U)             | 01 front bay module, 02 rear bay module                         | y = core split |
    | StraightS / Reducer   | 01 hanger half (trapeze), 02 free half                          | x              |
    | StraightL             | 01 hanger third (trapeze), 02 / 03 the two end thirds          | x, x           |
    | Drop                  | 01 tray section (trapeze), 02 / 03 the waterfalls under it     | z, z, x        |
    | TurnH / TurnUp / Down | 01 strut half, 02 other half (the bend's 45 deg radial)         | diagonal       |
    | Tee                   | 01 hub (strut), 02 / 03 run arms, 04 branch                     | x, x, y        |
    | Cross                 | 01 hub + one through arm (saddle, strut), 02-04 the other arms  | x, x, y        |
    | raised floor 0.5 m    | 01 / 02 the tile's back / front half (deck, pedestals, stringers) | y (panel line) |
    | raised floor 1.0 m    | 01-04 the four 0.5 m tiles, each with its quarter of the understructure | x, y (joints)|
    | containment roof      | 0.5 m bays (2.0 m aisle: 8 zones, one per bay); 1.0 m: 3 (Keen: 3 at 0.998 m), the   |
    |                       | -y row one zone; 1.5 m: 4 (Keen: 5), the middle panes cracked at y = 0 | mullions  |
    | containment door      | 01 lintel (track), 02-04 / 05-07 the -x / +x pocket towers bottom .. top, 08 sill;    |
    |                       | 01-07 critical (the frame round the opening, vanilla's door: 7 of 8)  | x, z joints |
    | Chute / TrayRods      | none: NON-BREAKABLE (UNFRACTURED: independent members, no fracture connection)   |

The exported colliders are shaped to each zone's geometry (shaped_hull, below); zone health = collider volume share,
x 2 for a critical zone.

Keen's limits (ModelLimitsChecker, VRage.ContentPipeline.ModelsValidation, decompiled): a fractured model may hold
round(interp(max edge: 0.25 m -> 1, 0.5 -> 2, 1.5 -> 5, 2.5 -> 15)) fractures, 32 materials and 256 mesh parts per
LOD, and 1.83425 x the triangles; its LOD count is still keyed on its own LOD0 triangles (fracture_budget).
"""
import math
import zlib
from dataclasses import dataclass

from . import dims as DM
from . import catalog as _CAT
from . import config as _CONFIG
from . import crac as _CRAC
from . import doors as _DOORS
from . import rack_side as _SIDE
from . import subparts as _SUB

PREFIX = "Fracture_"
CUT_MATERIAL = "FracturedMaterial01"          # vanilla break-face material (Timer50, Battery50, EventController100)
CUT_UV_PER_M = 0.4                            # vanilla cut faces: ~0.4 UV units per metre (Timer50 / Battery50)
CUT_PROPS = dict(ConstructionMeshType="Split", ConstructionMeshVisibility="HiddenUntilSecondSequenceStart",
                 ConstructionMeshPreset="Fracture")
CUT_MIN = 0.012     # an island is cut by a seam only when it reaches this far past the plane on BOTH sides
THIN_CAP = 0.04     # a cut loop shorter than this is a thin wire's end (6 mm wire: 0.02 m)

SERVER_SEAM_Y = -0.026      # dc/server.py: the middle of the 8 mm shadow gap between the rear cover and the lid
SERVER_FRONT_Y = 0.19       # the front service module's back edge: behind the lid latch (y 0.26-0.31) and
#                             the side intake slots (y 0.21-0.31), in front of the side swages (y < 0.14)
LONG_CUT = 0.04             # servers / racks: a hardware island reaching this far past a seam on both sides is cut
UPS_SEAM_Y = 0.016          # dc/servers/ups.py core_bays: where the front bay's core ends and the rear bay's begins
KEEP_WHOLE = {              # Part names never cut: hardware assigned whole by its centre (a strut is not sawn in two)
    "server": ("screw", "hw", "ear"),
    "tray": ("hw", "solid", "tiehw"),   # (tiehw = the strap buckles and collar bolts, whole as before)
    "trayrods": ("hw", "solid"),
    "rack": ("hw", "slidebolt", "decal", "holes"),
    # the room: round hardware, screws, stencils go whole; with ROOM_LONG_CUT the long ones are still cut
    "floor": ("ped", "fine", "decal", "arrow"),
    "contain_roof": ("frame", "cap", "glass", "clamp", "gasket", "dark", "hw", "tape", "decal", "led"),
    "contain_door": ("hw", "steel", "decal"),
    # the CRAC: hardware, the fan guards, the water stubs, stencils and the brush lips go whole
    "crac": ("hw", "guard", "pipe", "decal", "brush", "lip"),   # (the venturi lips, out of hw, still whole)
    # the PDUs (the cabinet's lit segments and placard go whole with their panel; the strip's cords,
    # plug and brackets go whole: no seam crosses them, dc/pdu.py)
    "pdu_cabinet": ("hw", "decal", "sticker", "lamp"),
    "pdu_strip": ("hw", "decal", "lamp", "cord", "plug", "steel"),
    "sign": ("hw", "decal"),           # bolts, hangers, stencils whole; the screen is cut
}
# Broken interiors follow the game's own style: a zone's inside is
# a solid core whose exposed faces are vanilla FracturedMaterial01. CORE_PARTS {family: part names}: in the cut
# (Fractured, Damaged) LODs every face of these parts takes CUT_MATERIAL with box UVs at CUT_UV_PER_M and goes into its
# zone's break-face object (Group Fracture_NN, CUT_PROPS: hidden until the second sequence, as a cut face), so a
# broken neighbour shows the core as vanilla's torn wiring; the NonFractured model keeps the part's own material
# (Darker: at most 8 materials there, and nothing sees it). The parts are cut like any solid (not in KEEP_WHOLE).
CORE_PARTS = {"crac": ("core",), "pdu_cabinet": ("core",)}
# Construction roles per face. A face's role decides its object and Group in
# the Fractured model (export_models._group) and so its construction mesh-part props:
#   skin     the zone's own group Fracture_NN: the panels that build up through both sequences;
#   hide     Fracture_NN_Hide, AlwaysHidden while under construction: decals, stencils, lamps, screens (HIDE_PREFIXES);
#   support  Fracture_NN_Support, the Support preset: the mounts that carry the block, built first;
#   frame    Fracture_NN_Frame, Split / HiddenUntilSecondSequenceStart: parts that appear in the second sequence;
#   glass    the zone's own group, a separate object with the WindowGlass preset: glass stays glass while it builds.
# Zone names never change, so a save's DamagedFractures stay valid. ROLES is per family {role: part names}, matched
# by exact part name like KEEP_WHOLE; each family's module fills it (empty here: the mechanism only).
HIDE_PREFIXES = ("AtlasDecal", "AtlasFont", "Emissive", "Terminal", "LCDScreen")   # vanilla LCDs keep their screen in
#                                                            a _Hide group too: Fracture_16_Hide-LCDScreen_Off
ROLE_IDS = ("skin", "hide", "support", "frame", "glass")
ROLE_SUFFIX = {"skin": "", "hide": "_Hide", "support": "_Support", "frame": "_Frame", "glass": ""}
ROLE_PROPS = {"skin": ("Default", "AlwaysVisible", "Default"), "hide": ("Default", "AlwaysHidden", "Default"),
              "support": ("Default", "AlwaysVisible", "Support"),
              "frame": ("Split", "HiddenUntilSecondSequenceStart", "Default"),
              "glass": ("Default", "AlwaysVisible", "WindowGlass")}
GLASS_MATERIALS = ("FrostedGlass", "WindowGlass", "WindowGlassThin", "ClearGlass")
ROLES = {fam: {} for fam in KEEP_WHOLE}
# The servers' rack ears (dc/server.py _ears: the L-bracket flange on the 19" rail and its leg riveted
# to the body) and slide inner members (_slides: the server-side rails riding the rack's slides) are the mounting
# hardware that carries the server, welded first (vanilla Timer50 11 %, Battery50 8 % support); with them the captive
# thumbscrews (`screw`: they fasten the ear flange to the rail's square holes)
ROLES["server"] = {"support": ("ear", "slide", "screw")}
# The cable trays, by what the kit's Parts are (dc/tray_kit.py Parts): the bundles with their boots
# (`cable`) and their dressing (`tie`: straps, split collars, saddle clamps; `tiehw`: the strap buckles and collar
# bolts) are pulled into the finished tray, so they arrive on completion (hide), as vanilla CableStraight250 (65 % of
# its FR LOD0 in _Hide groups); the hangers' and the basket's hardware (`hw`: rods, nuts, rod / splice plates, guide
# clamps) and the strut channels that carry the basket (`strut`: trapeze, floor strut) are the supports. The basket
# wire, the trim and the tray furniture the cables ride on (`guide`: waterfall guide, brush collar, crossover saddle)
# stay skin. (The rod hangers and the Chute are unfractured: their roles come from the material only.)
ROLES["tray"] = {"hide": ("cable", "tie", "tiehw"), "support": ("hw", "strut")}
# The room (vanilla CatwalkSquareBase250 / DeckPanel250 / WindowFlat250 / CircuitBreaker / LCDFlat50):
# the floor's pedestals (dc/floor.py _pedestal: `ped` the tube, jack, nut and anchor bolts, `pedplate` its base and
# head plates) stand on the slab and carry the deck; the roof's frame (contain.py _frame: the beams and mullions the
# panes sit on) and its rail clamps (_clamps: the brackets onto the racks' rail pads) carry the glazing, which stays
# glass by material; the signs' bolts and hangers (signs.py `hw`); the PDU cabinet's fixings (`hw`: the four levelling
# feet and the bolts) and the strips' standoff brackets with their keyhole button heads (pdu.py _brackets: `steel`,
# `hw`). The PDUs' detail arrives on completion (CircuitBreaker: 48 % _Hide): the cabinet's lamps (the meter's unlit
# bar segments too), DANGER sticker and the 24 branch breakers (pdu.py _breakers `breaker`: bodies, toggles, trip
# tabs; the busbar stays); the strips' lamps, jumper cords and inlet plug (plugged in last). Vanilla doors: no support.
ROLES["floor"] = {"support": ("ped", "pedplate")}
ROLES["contain_roof"] = {"support": ("frame", "clamp")}
ROLES["contain_door"] = {}
ROLES["sign"] = {"support": ("hw",)}
ROLES["pdu_cabinet"] = {"hide": ("lamp", "sticker", "breaker"), "support": ("hw",)}
ROLES["pdu_strip"] = {"hide": ("lamp", "cord", "plug"), "support": ("hw", "steel")}
# The CRAC's mounting hardware (dc/crac.py `hw`: the levelling feet, the fixing bolts of the fan
# modules and panels, the hinges and latches the doors hang on) and its coolant stubs (`pipe`: the CHW supply / return
# valves and stubs, the condensate stub, where the facility's pipework lands) are its supports, welded first
ROLES["crac"] = {"support": ("hw", "pipe")}
# The rack's structure (dc/rack.py): `frame` the posts (_columns' corner posts), the plinth frame, the
# corner caps' posts, the roof rails and the rear PDU bulkhead the frame is built from; `rail` the 19" mounting rails
# the servers hang on; `slide` the slide members the servers ride on; `contain` the containment rail along the top
# front / rear edge the roof clamps onto. Posts and rails first (vanilla Smelter250 24 % support); the side skins,
# ceiling, perforated panels and trim stay skin
ROLES["rack"] = {"support": ("frame", "rail", "slide", "contain")}
TABLE_ROLES = tuple(r for r in ROLE_IDS if ROLE_SUFFIX[r])   # the roles a part table may name (own suffixed group)


def check_role_tables(roles):
    """A part table names only suffixed roles. A "skin" entry is the default anyway, and a "glass"
    one would put a glass object and a skin object of the same material in one Group, i.e. one mesh-part name for two
    meshes (the exporter keeps the last object's props, the importer sees two meshes for one part). Glass is decided
    by material (GLASS_MATERIALS) only."""
    bad = {(fam, r) for fam, t in roles.items() for r in t if r not in TABLE_ROLES}
    if bad:
        raise ValueError(f"role tables may name only {TABLE_ROLES}: {sorted(bad)}")


check_role_tables(ROLES)


def is_hide(material):
    """The one hide test (preflight D3): a decal / stencil / lamp / screen material, AlwaysHidden while building."""
    return material.startswith(HIDE_PREFIXES)


def role_of(family, part, material):
    """The construction role of a face: hide by material, then glass by material, then the first role whose
    ROLES[family] entry names the face's part (exact name, as KEEP_WHOLE), else skin."""
    if is_hide(material):
        return "hide"
    if material in GLASS_MATERIALS:
        return "glass"
    table = ROLES.get(family, {})
    return next((r for r in TABLE_ROLES if part in table.get(r, ())), "skin")


def role_props(role):
    """{ConstructionMeshType, ConstructionMeshVisibility, ConstructionMeshPreset} of a role's objects."""
    return dict(zip(("ConstructionMeshType", "ConstructionMeshVisibility", "ConstructionMeshPreset"),
                    ROLE_PROPS[role]))


def skin_carrier(present, lod, block, zone):
    """The role whose piece carries a zone's Group and ColliderMeshGroups at this LOD: the skin when there
    is one; on a lower LOD the first present role in ROLE_IDS order (a decal-only or glass-only corner of a coarse
    LOD); None when the zone has nothing at that lower LOD. A zone with no LOD0 skin face fails here, by name: its
    group would carry no ColliderMeshGroups (the importer then drops every fracture) and the generator reads LOD0."""
    if "skin" in present:
        return "skin"
    if lod == 0:
        if present:
            raise RuntimeError(f"{block}: fracture zone {zone} has no LOD0 skin face (only {', '.join(sorted(present))}"
                               f"): give it a skin part or move its role parts to a neighbouring zone")
        raise RuntimeError(f"{block}: fracture zone {zone} has no LOD0 geometry")
    return next((r for r in ROLE_IDS if r in present), None)


ROOM_LONG_CUT = 0.04        # room blocks: a keep-whole island is cut only where it reaches this far past a seam on
#                             both sides (a roof member CENTRED on its mullion seam stays whole, a beam across is cut)

# Damaged (vanilla "Deformed") material swaps: the slot keeps its name (mesh parts are unchanged), the Damaged .model
# maps it to the broken material. Measured on 242 vanilla Deformed models (tools/vanilla-ref): every emissive slot
# -> EmissiveOffBroken (21 models), Terminal / Display01 -> Display01Broken, LCDScreen_Off_* -> LCDScreen_Off;
# 4.0: the painted / brushed / chrome metals -> their parallax Deformed materials.
DAMAGED_SLOTS = {"EmissiveOff": "EmissiveOffBroken", "EmissiveGreen": "EmissiveOffBroken",
                 "EmissiveRed": "EmissiveOffBroken", "EmissiveAmber": "EmissiveOffBroken",
                 "Emissive01": "EmissiveOffBroken", "Emissive02": "EmissiveOffBroken",
                 "EmissiveScriptStatus": "EmissiveOffBroken",   # the Programmable's script-status slot
                 "Terminal": "Display01Broken", "LCDScreen_Off": "LCDScreen_Off_Damaged",
                 "FrostedGlass": "WindowGlassBroken",   # the roof panes (vanilla Deformed: WindowGlass -> broken)
                 # the signs' 4:1 LCD slots (vanilla LCDScreen_Off_4.0; Deformed: LCDScreen_Off_*)
                 "LCDScreen_Off_4": "LCDScreen_Off_Damaged", "LCDScreen_Off_4_Back": "LCDScreen_Off_Damaged",
                 # the scratched 4.0 parallax Deformed metals, as vanilla's Deformed models map
                 # them (material_guids: Timer50_Deformed and ~90 % of 269 vanilla Deformed models); the player
                 # colour stays on the Colorable one (its colour mask)
                 "PaintedMetalColorable": "PaintedMetalColorableDeformed",
                 "PaintedMetalDarker": "PaintedMetalDarkerDeformed",
                 "BrushedMetal": "BrushedMetalDeformed", "Chrome": "ChromeDeformed"}

# deformation of the Damaged model (vanilla Timer50 / Battery50 Deformed: mean 5-8 mm, p90 9-14 mm, max 15-25 mm)
DENT = {"server": dict(amp=0.026, freq=5.5, fine=0.008, fine_freq=19.0, max_edge=0.045),
        "tray": dict(amp=0.014, freq=4.5, fine=0.004, fine_freq=14.0, max_edge=0.05),
        "trayrods": dict(amp=0.010, freq=3.0, fine=0.003, fine_freq=11.0, max_edge=0.05),
        "rack": dict(amp=0.024, freq=3.2, fine=0.007, fine_freq=12.0, max_edge=0.08),
        # the walking deck and the roof's top caps lie on the model's top face: there the dent may go INWARD
        # (unpin: the bounding-box faces where only the outward component stays pinned), or nothing would show
        "floor": dict(amp=0.016, freq=4.0, fine=0.004, fine_freq=14.0, max_edge=0.06, unpin=("+z",)),
        "contain_roof": dict(amp=0.016, freq=4.0, fine=0.004, fine_freq=14.0, max_edge=0.08, unpin=("+z",)),
        # the door's dent (mean ~7 mm on the 2.5 m frame)
        "contain_door": dict(amp=0.022, freq=4.0, fine=0.004, fine_freq=15.0, max_edge=0.16),
        # the CRAC: the rack's dent (a 2.5 m cabinet of 1-2 mm sheet over a frame)
        "crac": dict(amp=0.022, freq=3.4, fine=0.006, fine_freq=12.0, max_edge=0.08),
        # the PDU cabinet dents like a rack; the strip's 9 cm body like a server's shell, gentler
        "pdu_cabinet": dict(amp=0.024, freq=3.2, fine=0.007, fine_freq=12.0, max_edge=0.08),
        "pdu_strip": dict(amp=0.008, freq=9.0, fine=0.002, fine_freq=24.0, max_edge=0.03),
        # the signs (small, a knock dents the housing a few mm; vanilla LCD50 Deformed)
        "sign": dict(amp=0.010, freq=7.0, fine=0.003, fine_freq=18.0, max_edge=0.05)}


def damaged_slot(slot):
    """The material a Damaged .model maps a slot to: its DAMAGED_SLOTS target, or that of its base slot when it is a
    stand-in slot (`<Mat>_Subpart`: the base's Deformed material), else the slot itself (the .model maps by
    slot name, so a stand-in slot needs no re-suffixed Deformed name; material_guids.guid resolves `_Subpart`)."""
    if slot in DAMAGED_SLOTS:
        return DAMAGED_SLOTS[slot]
    if slot.endswith(SUBPART_SUFFIX):
        return DAMAGED_SLOTS.get(slot[:-len(SUBPART_SUFFIX)], slot)
    return slot


# Subpart stand-ins: a parked moving part baked into the Fractured (and, dented
# with its zone, the Damaged) model, never the NonFractured, as vanilla Gyroscope250 (17 `_Subpart` parts in FR, 16 in
# DM, 0 in NF). The subpart's exported LOD src_lods[i] goes into FR LOD i at `at` (its pivot in the block's Blender
# frame, in the closed / parked pose: no rotation), every slot renamed `<Mat>_Subpart`, Group = the zone holding each
# face's centroid (zone None, uncut: one subpart spans the zones it sits in, as vanilla Gyroscope50 / O2H2Generator250)
# or the explicit zone (zone_Hide for a HIDE_PREFIXES material), props Default / AlwaysVisible / SubpartConstruct.
# The ConditionalSubParts lists them in MeshPartsToHideWhenActive (integration.standin_parts): shown while the block
# is not Functional (under construction, broken), hidden when the real subparts spawn.
SUBPART_SUFFIX = "_Subpart"
STANDIN_PROPS = ("Default", "AlwaysVisible", "SubpartConstruct")


@dataclass(frozen=True)
class StandIn:
    subpart: str                    # the subpart's name (export.json "subparts" key)
    zone: str                       # None: its faces split by centroid over the zones (uncut); else all in this zone
    src_lods: tuple                 # (subpart LOD for FR LOD0, for FR LOD1)
    at: tuple = (0.0, 0.0, 0.0)     # the pivot in the block's Blender frame, closed pose
    yaw: float = 0.0                # turned about Blender +z (game +Y) at the pivot, degrees (the rack's left side)
    cut: bool = False               # zone None: cut along the plan's seams (fracture_mesh.cut_object), each zone's
    #                                 cross-sections closed by FracturedMaterial01_Subpart caps (build_caps)

    def __post_init__(self):
        # every auto-zoned stand-in is cut (the racks' and the KVM's), so a dead zone never leaves a raw edge on its
        # live neighbour's piece; an explicit zone is whole
        if (self.zone is None) != self.cut:
            raise ValueError(f"StandIn {self.subpart}: cut must be set exactly when zone is None")


# the KVM's drawer, closed (the KVM is placed with its drawer shut), and its lid folded down on the
# keyboard: both pivot at the stowed hinge (dc/subparts.py HINGE; the screen's pivot is the drawer's, SCREEN_LOCAL 0);
# both split over the zones they sit in (the drawer runs from the front module's fascia through the core
# into the rear chassis, the lid over the front module and the core), cut along the seams with break caps as the
# racks' (closed edges when one of its zones dies)
STANDINS = {"DC_Srv_KVM": (StandIn("KvmDrawer", None, (1, 2), _SUB.HINGE, cut=True),
                           StandIn("KvmScreen", None, (1, 1), _SUB.HINGE, cut=True))}
# The CRAC's three CracFan rotors, parked (no power: still), each in its own fan section (Fracture_02..04, the
# zones supporting CracFan1..3), at its own rotor pivot (crac.fan_points: the CracFan1..3 dummies, identity
# orientation, centred Blender frame). One subpart, three stand-ins: their mesh parts are distinct by zone.
STANDINS["DC_CRAC"] = tuple(StandIn(_CRAC.FAN, f"Fracture_{k + 2:02d}", (1, 2),
                                    (0.0, _CRAC.ROTOR_Y, zc - _CRAC.H / 2)) for k, zc in enumerate(_CRAC.FAN_ZC))
# Rack path "A": the racks' side panels (one RackSide model: the right side at the block origin,
# the left turned 180 deg, rack_side.SIDES) and the full racks' fan tray (at doors.fan_tray_point) spawn as
# ConditionalSubParts only on a Functional rack; until then their LOD1 stands in, split over the zones it sits in
# (the side columns, the tray's top zones). The rotors are not parked separately: the tray's LOD1 shows the housings.


def _rack_standins(spec):
    # (cut along the seams with break caps, so a broken side shows no raw edge where its zone
    # parts from a dead one; the tray likewise)
    out = [StandIn(_SIDE.SIDE_SUB, None, (1, 2), (0.0, 0.0, 0.0), yaw, cut=True) for _, yaw in _SIDE.SIDES]
    t = _DOORS.fan_tray_point(spec)
    if t is not None:
        out.append(StandIn(_DOORS.FAN_TRAY_SUB, None, (1, 2), t, 0.0, cut=True))
    return tuple(out)


def rack_standins(path):
    """{rack: stand-ins} for RACK_PATH "A" (the side panels and fan tray are ConditionalSubParts: stand-ins
    while not Functional); {} for path "B" (they are static client-prefab children, always present: no stand-ins)."""
    if path not in ("A", "B"):
        raise ValueError(f"RACK_PATH must be 'A' or 'B', not {path!r}")
    return {b.name: _rack_standins(b) for b in _CAT.BLOCKS if b.family == "rack"} if path == "A" else {}


STANDINS.update(rack_standins(_CONFIG.RACK_PATH))


def dent_seed(name):
    """The Damaged model's noise seed for block `name` (export determinism). Blender's
    mathutils.noise.noise_vector draws a random offset per process unless noise.seed_set is called (two exports of
    one block dented differently, up to ~15 mm apart), so fracture_mesh.dent seeds it with this stable per-block
    value (CRC-32: Python's hash() of a str is salted per process)."""
    return (zlib.crc32(f"datacenter/{name}".encode()) & 0x7FFFFFFF) or 1   # (seed_set(0) seeds from the clock)


# A Damaged LOD holds at most damaged_tris_x(family) x its Fractured LOD's triangles WITHOUT the construction scaffold
# (vanilla never has it in the Deformed model). Vanilla Deformed / Fractured: median 1.00, flat panels up to x 4.
# x 1.2, the floor decks and the roof tops x 1.5 (big flat panels need
# vertices a dent can move); the parallax Deformed materials (DAMAGED_SLOTS) carry the small-scale damage.
DAMAGED_TRIS_X = {"default": 1.2, "floor": 1.5, "contain_roof": 1.5}
# the least mean dent (vertex displacement, fracture_mesh.dent) a Damaged model must keep to read as dented
MIN_DENT_MM = 1.5


def damaged_tris_x(family):
    """The Damaged / Fractured (scaffold excluded) triangle ratio cap of a family (DAMAGED_TRIS_X)."""
    return DAMAGED_TRIS_X.get(family, DAMAGED_TRIS_X["default"])
# the ragged break (vanilla: chunks ~5-10 cm, +-2-4 cm along the cut normal): long cut edges split every `step`, the
# cut islands' vertices within reach x amp of the plane displaced along its normal by +-amp (fracture_mesh.jag_offset)
JAG = {"server": dict(step=0.018, amp=0.022, freq=11.0, reach=2.6),
       "tray": dict(step=None, amp=0.006, freq=21.0, reach=2.6),   # thin strands / wires: a slanted snap
       "trayrods": dict(step=None, amp=0.0, freq=0.0, reach=2.6),
       "rack": dict(step=0.02, amp=0.02, freq=7.0, reach=2.6),
       # (a gentle break: the caps' UVs are projected on the seam plane, so a steep jag on a thin plate or pane would
       #  stretch them below vanilla's 0.40 UV/m)
       "floor": dict(step=0.02, amp=0.008, freq=4.0, reach=2.6),
       "contain_roof": dict(step=0.02, amp=0.008, freq=4.0, reach=2.6),
       "contain_door": dict(step=None, amp=0.0, freq=0.0, reach=2.6),   # straight: the frame parts at its joints
       "crac": dict(step=None, amp=0.0, freq=0.0, reach=2.6),   # straight: the seams run on door rails / panel joints
       "pdu_cabinet": dict(step=0.02, amp=0.02, freq=7.0, reach=2.6),    # as the rack
       "pdu_strip": dict(step=0.008, amp=0.004, freq=30.0, reach=2.6),   # the extrusion snaps across, a little ragged
       "sign": dict(step=0.015, amp=0.006, freq=9.0, reach=2.6)}       # a gentle crack across the housing


class Zone:
    def __init__(self, zid, halfspaces, label, critical=False, hull_from="regular"):
        self.id = zid
        self.halfspaces = [(tuple(map(float, o)), _unit(n)) for o, n in halfspaces]
        self.label = label
        self.critical = critical
        self.hull_from = hull_from   # the collision boxes its plan box is fitted to: "regular" (physics),
        #                              "occupancy" (the Drop's waterfalls) or "geometry" (none: the half rack's roof);
        #                              the exported collider is shaped to the zone's geometry (shaped_hull)
        self.shape = None         # the exported collider: shaped_hull's dict (export_models)
        self.hull = None          # (lo, hi): its collider, set by Plan.fit_hulls

    def violation(self, p):
        return max([0.0] + [-_dot(_sub(p, o), n) for o, n in self.halfspaces])

    def __repr__(self):
        return f"Zone({self.id}, {self.label!r}, critical={self.critical})"


class Seam:
    """The plane between zones a and b (indices into Plan.zones): (p - o) . n >= 0 on a's side. a / b may also be
    tuples of zones sharing that plane on each side (a rack's plinth top meets both columns): self.A / self.B; self.a /
    self.b are their first zones."""

    def __init__(self, o, n, a, b, snap=0.0):
        self.o, self.n = tuple(map(float, o)), _unit(n)
        self.A = tuple(a) if isinstance(a, (tuple, list)) else (a,)
        self.B = tuple(b) if isinstance(b, (tuple, list)) else (b,)
        self.a, self.b = self.A[0], self.B[0]
        self.snap = snap          # +- window (m) in which build snaps the plane into the widest vertex-free gap
        self.jag = 0.0            # the break's amplitude along n (fracture_mesh.snap_seams)
        self.reach = 0.0          # how far from the plane the break field fades out (< the model's bounding faces)

    def axis(self):
        """The axis index when the plane is axis-aligned, else None."""
        for i in range(3):
            if abs(abs(self.n[i]) - 1.0) < 1e-9:
                return i
        return None

    def moved(self, d):
        """Shift the plane by d along its normal (the zones that use it follow: Plan.move_seam)."""
        return tuple(self.o[i] + d * self.n[i] for i in range(3))


class Plan:
    def __init__(self, spec, family, zones, seams, keep_whole=(), supporting=None):
        self.spec, self.family = spec, family
        self.zones, self.seams = zones, seams
        self.keep_whole = tuple(keep_whole)
        self.supporting = supporting or {}     # dummy name -> point (Blender frame): its zone supports it

    def ids(self):
        return [z.id for z in self.zones]

    # the cheaper LOD0 cuts a light block may take to stay clearly on one side of Keen's LOD-count row (see
    # export_models._export_planned), in turn: no caps on thin wire ends (< THIN_CAP perimeter), then a split along
    # the existing edges instead of a bisect (a bend's arcs are faceted: its wires and strands part at a segment ring)
    edge_split = False
    thin_caps = True
    long_cut = None      # keep_whole islands reaching this far past a seam on both sides are cut (None: never)

    def cut_mode(self):
        return ("edges" if self.edge_split else "bisect") + ("" if self.thin_caps else ", no wire-end caps")

    def critical(self):
        return [z.id for z in self.zones if z.critical]

    def zone_index(self, p):
        """Index of the zone containing p (the least violated; ties to the lower index = the key zone)."""
        best, bi = None, 0
        for i, z in enumerate(self.zones):
            v = z.violation(p)
            if best is None or v < best - 1e-12:
                best, bi = v, i
        return bi

    @staticmethod
    def zone_at(zones, p):
        """The id of the zone holding p (Blender frame) among an export manifest's zones ("fractured" "zones": their
        half spaces), by Plan.zone_index's rule: the least violated, ties to the earlier (the key) zone. For dummies
        placed after the export (integration: the KVM's use toggle) that a zone must support."""
        best, bid = None, None
        for z in zones:
            v = max([0.0] + [-_dot(_sub(p, o), n) for o, n in z["halfspaces"]])
            if best is None or v < best - 1e-12:
                best, bid = v, z["id"]
        return bid

    def move_seam(self, k, d):
        """Move seam k by d along its normal, and the matching half spaces of its two zones."""
        s = self.seams[k]
        old = s.o
        s.o = s.moved(d)
        for z in [self.zones[i] for i in s.A + s.B]:     # (the half spaces lying on the seam's plane move with it)
            z.halfspaces = [(tuple(c + d * m for c, m in zip(o, s.n))
                             if ((n == s.n or n == _neg(s.n)) and abs(_dot(_sub(o, old), s.n)) < 1e-9) else o, n)
                            for o, n in z.halfspaces]

    def fit_hulls(self, boxes):
        """Each zone's collider: the bounding box of the regular physics boxes (or, for a zone flagged so, the
        occupancy boxes) clipped to the zone: a box where the zone holds a box piece; the zones of an L bend overlap
        a little at the bend, as vanilla's hulls do. boxes: the collision dict."""
        for z in self.zones:
            if z.hull_from == "geometry":     # no physics box under it (the half rack's render-only roof): its
                continue                      # collider comes from its geometry only (shaped_hull, at export)
            pts = []
            for _, lo, hi in boxes[z.hull_from]:
                pts += clip_box(lo, hi, z.halfspaces)
            if not pts:
                raise RuntimeError(f"{self.spec.name}: zone {z.id} holds no physics box")
            lo = tuple(round(min(p[i] for p in pts), 5) for i in range(3))
            hi = tuple(round(max(p[i] for p in pts), 5) for i in range(3))
            if min(h - l for l, h in zip(lo, hi)) < 0.004:
                raise RuntimeError(f"{self.spec.name}: zone {z.id} collider is degenerate {lo} {hi}")
            z.hull = (lo, hi)
        return [(z.id, z.hull[0], z.hull[1]) for z in self.zones if z.hull]

    def manifest(self):
        return {"zones": [{"id": z.id, "label": z.label, "critical": z.critical,
                           "lo": list(z.hull[0]) if z.hull else None, "hi": list(z.hull[1]) if z.hull else None,
                           "halfspaces": [[list(o), list(n)] for o, n in z.halfspaces]} for z in self.zones],
                "seams": [{"o": [round(v, 6) for v in s.o], "n": [round(v, 6) for v in s.n],
                           "zones": [self.zones[s.a].id, self.zones[s.b].id],
                           "sides": [[self.zones[i].id for i in s.A], [self.zones[i].id for i in s.B]],
                           "jag": round(s.jag, 6),
                           "reach": round(s.reach, 6)}
                          for s in self.seams],
                "supporting": {d: self.zones[self.zone_index(p)].id for d, p in sorted(self.supporting.items())}}


# ---------------------------------------------------------------------------------------------------- geometry
def _unit(n):
    n = tuple(map(float, n))
    m = math.sqrt(sum(c * c for c in n))
    return tuple(c / m for c in n)


def _neg(n):
    return tuple(-c for c in n)


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def clip_box(lo, hi, halfspaces):
    """Vertices of the AABB [lo, hi] clipped by the half spaces (every face polygon clipped Sutherland-Hodgman);
    [] when nothing is left."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [[c[i] for i in f] for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6),
                                         (3, 0, 4, 7))]
    for o, n in halfspaces:
        out = []
        for poly in faces:
            res = []
            for i, p in enumerate(poly):
                q = poly[(i + 1) % len(poly)]
                dp, dq = _dot(_sub(p, o), n), _dot(_sub(q, o), n)
                if dp >= -1e-9:
                    res.append(p)
                if (dp >= -1e-9) != (dq >= -1e-9):
                    t = dp / (dp - dq)
                    res.append(tuple(p[k] + t * (q[k] - p[k]) for k in range(3)))
            if len(res) >= 3:
                out.append(res)
        faces = out
    return [p for f in faces for p in f]


# ---------------------------------------------------------------------------------------------------- shaped hulls
# A zone's collider follows its solid (vanilla's breakable blocks do the same). Health is the
# block's MaxHealth x the collider's VOLUME share (BreakableComponentDefinition.PostProcessPrefabs), and the colliders
# become the block's physics once anything breaks, so a box over mostly empty space (a bend's inner corner, a
# waterfall's occupancy column) buys health and phantom collision. Each collider is a k-DOP of the zone's own LOD0
# geometry (its skin, decals and break faces): the axis box clipped to the block's cells and the zone's seams, then
# greedily the planes (45 degree face / body diagonals, and DOP_FREE) that cut the most volume, while each cuts
# >= HULL_GAIN of it and the block's total
# hull vertices stay within Keen's fractured collider budget (ModelAssetProcessorValidator.ValidateColliders: the SUM
# of all pieces' vertices <= 1.5 x interp(max edge: 0.25 -> 32, 0.5 -> 40, 1.5 -> 48, 2.5 -> 80, 4 -> 120)).
_R2, _R3 = 1 / math.sqrt(2), 1 / math.sqrt(3)
DOP_AXES = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
DOP_DIAGONALS = ([tuple(c * _R2 for c in v) for v in
                  [(a, b, 0) for a in (1, -1) for b in (1, -1)] + [(a, 0, b) for a in (1, -1) for b in (1, -1)] +
                  [(0, a, b) for a in (1, -1) for b in (1, -1)]] +
                 [tuple(c * _R3 for c in (a, b, e)) for a in (1, -1) for b in (1, -1) for e in (1, -1)])
HULL_GAIN = 0.03


def _spiral(n, turn=2.39996323):
    """n directions spread evenly over the sphere (a golden-angle spiral)."""
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1 - z * z))
        out.append((r * math.cos(turn * i + 0.3), r * math.sin(turn * i + 0.3), z))
    return out


# a waterfall's slanted bundle or a bend's arc has faces in no 45 degree direction: 48 more directions to choose from
DOP_FREE = _spiral(48)


def _solve3(planes):
    """The point on three planes (n . p = d), or None when they do not meet in one point (Cramer)."""
    (a, da), (b, db), (c, dc) = planes
    bc = _cross(b, c)
    det = _dot(a, bc)
    if abs(det) < 1e-12:
        return None
    ca, ab = _cross(c, a), _cross(a, b)
    return tuple((da * bc[i] + db * ca[i] + dc * ab[i]) / det for i in range(3))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dedupe(pts, q=1e-6):
    seen, out = set(), []
    for p in pts:
        k = tuple(round(c / q) for c in p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def polytope_vertices(planes, eps=1e-7):
    """Vertices of the bounded polytope {p: n . p <= d for every (n, d)} (every feasible triple intersection)."""
    out = []
    k = len(planes)
    for i in range(k):
        for j in range(i + 1, k):
            for m in range(j + 1, k):
                p = _solve3((planes[i], planes[j], planes[m]))
                if p is not None and all(_dot(n, p) <= d + eps for n, d in planes):
                    out.append(p)
    return _dedupe(out)


def _clip_vertices(verts, planes, new, eps=1e-7):
    """polytope_vertices(planes + [new]) from the polytope's verts: the kept ones and the new plane's corners."""
    n0, d0 = new
    out = [v for v in verts if _dot(n0, v) <= d0 + eps]
    k = len(planes)
    for i in range(k):
        for j in range(i + 1, k):
            p = _solve3((new, planes[i], planes[j]))
            if p is not None and all(_dot(n, p) <= d + eps for n, d in planes):
                out.append(p)
    return _dedupe(out)


def polytope_volume(planes, verts, eps=1e-6):
    """Volume of the convex polytope (planes, its vertices): a pyramid from the vertex centroid over each face."""
    if len(verts) < 4:
        return 0.0
    c = tuple(sum(v[i] for v in verts) / len(verts) for i in range(3))
    vol = 0.0
    for n, d in planes:
        f = [v for v in verts if abs(_dot(n, v) - d) < eps]
        if len(f) < 3:
            continue
        fc = tuple(sum(v[i] for v in f) / len(f) for i in range(3))
        t1 = _unit(_sub(f[0], fc)) if any(abs(x) > 1e-12 for x in _sub(f[0], fc)) else _unit(_cross(n, (1, 0, 0)))
        t2 = _cross(n, t1)
        f.sort(key=lambda v: math.atan2(_dot(_sub(v, fc), t2), _dot(_sub(v, fc), t1)))
        area = 0.0
        for a, b in zip(f, f[1:] + f[:1]):
            area += _dot(_cross(_sub(a, fc), _sub(b, fc)), n) / 2
        vol += abs(area) * (d - _dot(n, c)) / 3
    return vol


def shaped_hull(points, lo, hi, max_verts, gain=HULL_GAIN, halfspaces=()):
    """The zone collider fitted to points (its LOD0 geometry): {"verts", "planes", "volume", "box_volume"}; see the
    section comment. lo / hi: the block's cell box (the collider stays inside it). halfspaces: the zone's own
    [(o, n)] ((p - o) . n >= 0): the collider stops at its seams' planes, so the ragged break's few cm of spill do not
    carry it into the next zone's cells (a mount cell belongs to the FIRST collider overlapping it, and the seams
    lie on cell boundaries), while two neighbours still touch along the plane (Havok's 0.1 m)."""
    sup = lambda n: max(_dot(n, p) for p in points)   # noqa: E731
    planes = []
    for n in DOP_AXES:
        i = [k for k in range(3) if n[k]][0]
        d = sup(n)
        lim = hi[i] if n[i] > 0 else -lo[i]
        planes.append((n, min(d, lim)))
    for o, n in halfspaces:
        m = _neg(n)
        d = _dot(m, o)
        same = [k for k, (q, _) in enumerate(planes) if all(abs(a - b) < 1e-12 for a, b in zip(q, m))]
        if same:
            planes[same[0]] = (m, min(planes[same[0]][1], d))
        else:
            planes.append((m, d))
    verts = polytope_vertices(planes)
    vol = box = polytope_volume(planes, verts)
    cands = [(n, sup(n)) for n in DOP_DIAGONALS + DOP_FREE]
    while True:
        best = None
        for n, d in cands:
            if (n, d) in planes or max(_dot(n, v) for v in verts) <= d + 1e-6:
                continue
            v2 = _clip_vertices(verts, planes, (n, d))
            if len(v2) > max_verts:
                continue
            vol2 = polytope_volume(planes + [(n, d)], v2)
            if vol - vol2 >= gain * vol and (best is None or vol2 < best[2]):
                best = ((n, d), v2, vol2)
        if best is None:
            break
        planes.append(best[0])
        verts, vol = best[1], best[2]
    planes = [(n, d) for n, d in planes if sum(1 for v in verts if abs(_dot(n, v) - d) < 1e-6) >= 3]
    return {"verts": verts, "planes": planes, "volume": vol, "box_volume": box}


def health_shares(volumes, critical):
    """Keen's per-zone health share (BreakableComponentDefinition.PostProcessPrefabs): collider volume, x 2 for a
    critical zone (BreakableBlocksConfiguration CriticalFractureHealthShareMultiplier), over the sum. {id: share}."""
    w = {z: v * (2.0 if z in critical else 1.0) for z, v in volumes.items()}
    t = sum(w.values())
    return {z: round(x / t, 4) for z, x in w.items()}


# A zone's health is its collider's volume share, so a thin zone's shaped hull dies at the first hit. A
# zone under MIN_ZONE_SHARE gets an axis box instead (min_share_box): its LOD0 geometry's box thickened on its thinnest
# axis, to at least MIN_HULL_T and to the share, but never more than MIN_HULL_T beyond its own geometry (the hull is a
# live collider: after any zone dies the Fractured collision is the block's physics, its debris piece and its re-weld
# overlap check). A zone that would need more raises, by name; it is re-zoned or listed in
# MIN_SHARE_EXEMPT. Zone ids and critical lists are unchanged; the manifest flags a lifted zone min_share.
MIN_ZONE_SHARE = 0.01
MIN_HULL_T = 0.02
_SHARE_MARGIN = 1.02          # aim 2 % over the floor: the manifest's shares are rounded to 4 places
# (family, zone) kept on their shaped hull under the floor. The containment
# doors' sill (8 mm threshold, 0.06 %): the one non-critical door zone; its death changes no function (the door stays
# Functional, only the doorway's sill_down mount drops); an 8 mm strip dying early is plausible and
# low-impact; the only volume cure (a 6-7 cm box) puts an invisible step in the walkway of a broken door. Accepted
# cost: the sill can die early.
MIN_SHARE_EXEMPT = {("contain_door", "Fracture_08")}


def box_hull(lo, hi):
    """An axis box as a shaped_hull dict."""
    verts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    planes = [(n, (hi[i] if n[i] > 0 else -lo[i])) for n in DOP_AXES for i in range(3) if n[i]]
    vol = (hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2])
    return {"verts": verts, "planes": planes, "volume": vol, "box_volume": vol}


def min_share_box(glo, ghi, lo, hi, need, zone="zone"):
    """The box hull of a zone below MIN_ZONE_SHARE (see above): its geometry box (glo, ghi) within the cells (lo,
    hi), thickened on its thinnest axis to max(MIN_HULL_T, the thickness giving volume `need`), shifted back inside
    the cells. Raises when that is more than MIN_HULL_T beyond the geometry or does not fit the cells."""
    blo = [max(a, c) for a, c in zip(glo, lo)]
    bhi = [min(b, c) for b, c in zip(ghi, hi)]
    a = min(range(3), key=lambda i: bhi[i] - blo[i])
    o1, o2 = [i for i in range(3) if i != a]
    ext = bhi[a] - blo[a]
    t = max(ext, MIN_HULL_T, need / ((bhi[o1] - blo[o1]) * (bhi[o2] - blo[o2])))
    if t - ext > MIN_HULL_T + 1e-9 or t > hi[a] - lo[a] + 1e-9:
        raise RuntimeError(f"{zone}: under MIN_ZONE_SHARE; reaching it needs {t * 1000:.1f} mm on its thinnest axis "
                           f"(geometry {ext * 1000:.1f} mm, at most +{MIN_HULL_T * 1000:.0f} mm): re-zone it or list "
                           f"it in fracture.MIN_SHARE_EXEMPT")
    c = (blo[a] + bhi[a]) / 2
    z0 = min(max(c - t / 2, lo[a]), hi[a] - t)
    blo[a], bhi[a] = z0, z0 + t
    return box_hull(blo, bhi)


def lift_small_zones(shapes, critical, geo, lo, hi, exempt=()):
    """{zone: min_share_box shape} for the zones whose health share (shapes' volumes, Keen's rule) is under
    MIN_ZONE_SHARE, except the `exempt` ones (they keep their hulls); shapes {zone: shaped_hull dict}, geo {zone:
    (glo, ghi)} its LOD0 geometry box. Each is sized against the others' current weight, repeated until every share
    holds."""
    vols = {z: s["volume"] for z, s in shapes.items()}
    out = {}
    for _ in range(8):
        share = health_shares(vols, critical)
        small = [z for z in vols if share[z] < MIN_ZONE_SHARE and z not in exempt]
        if not small:
            return out
        w = {z: 2.0 if z in critical else 1.0 for z in vols}
        for z in small:
            rest = sum(vols[k] * w[k] for k in vols if k != z)
            s = MIN_ZONE_SHARE * _SHARE_MARGIN
            need = s * rest / (1.0 - s) / w[z]
            out[z] = min_share_box(*geo[z], lo, hi, need, z)
            vols[z] = out[z]["volume"]
    raise RuntimeError(f"zones {sorted(out)} stay under MIN_ZONE_SHARE")


def max_fractures(size):
    """Keen's GetMaximumNumberOfFractures: interpolated on the model's largest edge, rounded (MathF.Round, to even)."""
    m = max(size)
    tab = [(0.25, 1.0), (0.5, 2.0), (1.5, 5.0), (2.5, 15.0)]
    if m <= tab[0][0]:
        v = tab[0][1]
    elif m >= tab[-1][0]:
        v = tab[-1][1]
    else:
        for (a, va), (b, vb) in zip(tab, tab[1:]):
            if a <= m <= b:
                v = va + (vb - va) * (m - a) / (b - a)
                break
    return int(round(v))       # Python's round is round-half-to-even, as MathF.Round


def fracture_budget(size, lod0_tris, n_lods):
    """Per LOD, the most triangles a fractured / damaged model of this block may have: Keen's fractured limit
    (x 1.83425) with 5 % headroom, and on LOD0 the row value that keeps Keen's LOD count (the count is keyed on the
    model's own LOD0 triangles: crossing row[bias] would ask for one more LOD)."""
    from se2model import limits
    lim = limits.model_limits(size, lod0_tris)
    frac = limits.model_limits(size, lod0_tris, fractured=True)
    out = [int(frac["lods"][i]["max_tris"] * 0.95) for i in range(n_lods)]
    r = lod_row(size, lod0_tris)
    if r is not None:
        out[0] = min(out[0], int(LOD_ROW_BAND[0] * r))
    return out


# Keen's importer counts a few % fewer LOD0 triangles than the FBX holds (TurnH_Empty: 2100 exported, 1960
# counted), so a cut LOD0 must sit clearly on one side of the row its LOD count is keyed on: at most 0.97 x the row
# (same LOD count) or at least 1.15 x (one more LOD, the tray kit's mid detail).
LOD_ROW_BAND = (0.97, 1.15)


def lod_row(size, lod0_tris):
    """The row value Keen's LOD count for this LOD0 is keyed on (crossing it changes the count), or None when the
    LOD0 already has lod bias 0 (more triangles cannot ask for more LODs)."""
    from se2model import limits
    b = limits.model_limits(size, lod0_tris)["lod_bias"]
    if b == 0:
        return None
    return limits._interp(limits._tri_table(), limits.surface(*size))[0][b]


def lod_side(size, nf_lod0_tris, t0):
    """Where a cut LOD0 of t0 triangles lands against the NonFractured LOD0's row: below | above | ambiguous."""
    r = lod_row(size, nf_lod0_tris)
    if r is None or t0 <= LOD_ROW_BAND[0] * r:
        return "below"
    return "above" if t0 >= LOD_ROW_BAND[1] * r else "ambiguous"


# ---------------------------------------------------------------------------------------------------- plans
# Blocks kept NON-BREAKABLE (the justified exception, integration.make_non_breakable): their parts are independent
# members with nothing between them, and Havok's breakable compound connects two fractures only when their colliders
# lie within BreakableColliderArgs.MaxEdgeDistance (0.1 m) of each other; with no connection at all the builder fails
# ("Connectivity graph should have at least one connection", seen on the first 9b build). A connected split would
# need a convex collider spanning the empty gap (a phantom wall once a zone is damaged), and a split into separate
# graph components (two zones per rod) has no vanilla precedent and an untested runtime.
UNFRACTURED = {
    "Rods": "two independent hanger rods 0.44 m apart: no fracture connection (Havok: <= 0.1 m)",
    "Chute": "two independent ladders 0.6 m apart: no fracture connection (Havok: <= 0.1 m)",
}


def unfractured_reason(spec):
    """Why a block keeps no fractures (non-breakable), or None."""
    if spec.family not in ("tray", "trayrods"):
        return None
    from . import tray_plan as TP
    return UNFRACTURED.get(TP.plan(spec).shape)


def plan(spec, boxes):
    """The block's fracture plan (every rack, server and cable tray), or None for the non-breakable
    exception (UNFRACTURED). boxes: the collision dict (regular physics boxes in the centred Blender frame)."""
    if spec.family == "server":
        p = _server(spec)
    elif spec.family == "rack":
        p = _rack(spec)
    elif unfractured_reason(spec):
        return None
    elif spec.family in ("tray", "trayrods"):
        p = _tray(spec, boxes)
    elif spec.family == "floor":
        p = _floor(spec)
    elif spec.family == "contain_roof":
        p = _roof(spec)
    elif spec.family == "contain_door":
        p = _door(spec)
    elif spec.family == "crac":
        p = _crac(spec)
    elif spec.family == "pdu_cabinet":
        p = _pdu_cabinet(spec)
    elif spec.family == "pdu_strip":
        p = _pdu_strip(spec)
    elif spec.family == "sign":
        p = _sign(spec)
    else:
        return None
    p.fit_hulls(boxes)
    return p


def _server(spec):
    """6U servers: a critical central core (the mainboard / drive cage between the lid
    and the rear cover: two neighbours, so it always stays in the largest island) with two shell modules: the
    front service module (bezel, face, controls, rack ears, the lid's latch end), which supports the face's
    interaction dummies (functional.DUMMIES: Terminal / LcdPanel die with it), and the rear chassis (rear cover,
    PSU). The UPS keeps vanilla Battery50's pattern: its two cell bays meet back to back in the middle, so there
    is no core to cut free; the front bay module is critical and each bay supports its CellSlot / CellAction."""
    from . import functional as FN
    if spec.variant == "UPS":
        y = UPS_SEAM_Y
        front = Zone("Fracture_01", [((0, y, 0), (0, 1, 0))], "front bay module (front cell bay, terminal, rack ears)",
                     critical=True)
        rear = Zone("Fracture_02", [((0, y, 0), (0, -1, 0))], "rear bay module (rear cell bay, rear cover)")
        sup = {}
        for i, x, z, ym, f in FN.UPS_BAYS:     # vanilla Battery50: CellSlot / CellAction supported by the bay's fracture
            sup[f"CellSlot {i}"] = sup[f"CellAction {i}"] = (x, ym - f * 0.05, z)
        p = Plan(spec, "server", [front, rear], [Seam((0, y, 0), (0, 1, 0), 0, 1, snap=0.0)], KEEP_WHOLE["server"],
                 supporting=sup)
        p.long_cut = LONG_CUT
        return p
    yr, yf = SERVER_SEAM_Y, SERVER_FRONT_Y
    core = Zone("Fracture_01", [((0, yr, 0), (0, 1, 0)), ((0, yf, 0), (0, -1, 0))],
                "core (mainboard, drive cage, under the service lid)", critical=True)
    front = Zone("Fracture_02", [((0, yf, 0), (0, 1, 0))],
                 "front service module (bezel, face, controls, rack ears, lid latch)")
    rear = Zone("Fracture_03", [((0, yr, 0), (0, -1, 0))], "rear chassis (rear cover, rear panel, PSU)")
    sup = {name: (-a, FN.FRONT_Y + d, b) for name, ((a, b, d), _) in FN.DUMMIES.get(spec.name, {}).items()}
    p = Plan(spec, "server", [core, front, rear],
             [Seam((0, yf, 0), (0, -1, 0), 0, 1, snap=0.02), Seam((0, yr, 0), (0, 1, 0), 0, 2, snap=0.0)],
             KEEP_WHOLE["server"], supporting=sup)
    p.long_cut = LONG_CUT
    return p


# Regular (physics) boxes no fracture zone owns. The racks' rear stop (dc/rack.py
# collision()) is a 2 cm plate across the slot band's back, between the two side columns: no convex zone of the
# column / plinth / tray plan holds it without its box hull swallowing the slot volume, and the half rack already
# has Keen's maximum of 4 zones. It stays in the intact model's physics (the block's optimised collider, which the
# grid's physics and the placer's ray use: BlockPhysicsProvider.cs:80) and carries no mount point (its render, the
# rear stop brackets, sits outside the sampled slot face), so no fracture has to support anything on it.
UNFRACTURED_BOXES = ("rear_stop",)


def _rack(spec):
    """The racks: a frame cut where it would really part
    (as vanilla's breakables do), every zone a full-section chunk. Full rack (8 zones, within vanilla's 8-12 at 2.5 m): the plinth's
    front and rear halves, each side column (corner posts, 19" rails, cable manager) in a lower and an upper
    half, the top cable tray's front and rear halves. Half rack (Keen allows 4 at 1.25 m): plinth, the two side
    columns, the roof over the slots (it owns the slot roof's mount cells, which no zone covered before). The
    middle of the slot holds only the columns' slides: it goes to the nearer column. Structural: no critical zone,
    except on the door racks, whose side columns carry the hinges (integration.critical_fractures)."""
    from . import doors, rack
    d = rack.dims(spec)
    H, ZT = d["H"], d["ZT"]
    zp, zt = 0.25 - H / 2, ZT - H / 2
    SX = rack.SX
    door = bool(doors.has_doors(spec))
    down, up = (0, 0, -1), (0, 0, 1)
    L = ((-SX, 0, 0), (-1, 0, 0))
    R = ((SX, 0, 0), (1, 0, 0))
    if d["tray"]:
        zm = (zp + zt) / 2
        yp, yt = (0, 0, zp - 0.125), (0, 0, (zt + H / 2) / 2)    # the y = 0 planes, through the plinth / the tray
        Z = [Zone("Fracture_01", [((0, 0, zp), down), (yp, (0, 1, 0))], "plinth, front half"),
             Zone("Fracture_02", [((0, 0, zp), down), (yp, (0, -1, 0))], "plinth, rear half"),
             Zone("Fracture_03", [((0, 0, zp), up), ((0, 0, zm), down), L],
                  "left column, lower half (corner posts, rail, cable manager)", critical=door),
             Zone("Fracture_04", [((0, 0, zp), up), ((0, 0, zm), down), R],
                  "right column, lower half (corner posts, rail, cable manager)", critical=door),
             Zone("Fracture_05", [((0, 0, zm), up), ((0, 0, zt), down), L],
                  "left column, upper half", critical=door),
             Zone("Fracture_06", [((0, 0, zm), up), ((0, 0, zt), down), R],
                  "right column, upper half", critical=door),
             Zone("Fracture_07", [((0, 0, zt), up), (yt, (0, 1, 0))], "top cable tray, front half"),
             Zone("Fracture_08", [((0, 0, zt), up), (yt, (0, -1, 0))], "top cable tray, rear half")]
        c = (-(SX + 0.125), 0.3)                                  # (a point in the left column's plan)
        S = [Seam(yp, (0, 1, 0), 0, 1, snap=0.03),
             Seam((*c, zp), down, (0, 1), (2, 3)),
             Seam((*c, zm), down, (2, 3), (4, 5), snap=0.06),
             Seam((*c, zt), up, (6, 7), (4, 5)),
             Seam(yt, (0, 1, 0), 6, 7, snap=0.03)]
    else:
        zr = H / 2 - 0.04
        zs = H / 2 - 0.02                                         # the roof / column planes, through the roof
        Z = [Zone("Fracture_01", [((0, 0, zp), down)], "plinth"),
             Zone("Fracture_02", [((0, 0, zr), up), ((-SX, 0, zs), (1, 0, 0)), ((SX, 0, zs), (-1, 0, 0))],
                  "roof over the slots (headers, slot roof)", hull_from="geometry"),
             Zone("Fracture_03", [((0, 0, zp), up), ((-SX, 0, zs), (-1, 0, 0))],
                  "left column (corner posts, rail, cable manager, roof rail)", critical=door),
             Zone("Fracture_04", [((0, 0, zp), up), ((SX, 0, zs), (1, 0, 0))],
                  "right column (corner posts, rail, cable manager, roof rail)", critical=door)]
        S = [Seam((-(SX + 0.125), 0, zp), down, 0, (2, 3)),
             Seam((-SX, 0, zs), (1, 0, 0), 1, 2),
             Seam((SX, 0, zs), (-1, 0, 0), 1, 3)]
    p = Plan(spec, "rack", Z, S, KEEP_WHOLE["rack"])
    p.long_cut = LONG_CUT
    return p


def _tray(spec, boxes):
    from . import tray_plan as TP
    pl = TP.plan(spec)
    sh = [v / 2 for v in pl.size]
    reg = boxes["regular"]
    sup = [tuple(float(c) - s for c, s in zip(sp.position, sh)) for sp in pl.supports]
    fam = spec.family
    kw = KEEP_WHOLE[fam]
    shape = pl.shape
    if shape in ("StraightS", "Reducer"):
        s = 0.0625                                 # a quarter cell off the trapeze (x = 0): the hanger stays whole
        hang = Zone("Fracture_01", [((s, 0, 0), (-1, 0, 0))], "hanger half (trapeze, rod plates)")
        free = Zone("Fracture_02", [((s, 0, 0), (1, 0, 0))], "free half")
        return Plan(spec, fam, [hang, free], [Seam((s, 0, 0), (-1, 0, 0), 0, 1, snap=0.03)], kw)
    if shape == "StraightL":
        a = 0.25
        mid = Zone("Fracture_01", [((-a, 0, 0), (1, 0, 0)), ((a, 0, 0), (-1, 0, 0))],
                   "hanger section (trapeze, rod plates)")
        lft = Zone("Fracture_02", [((-a, 0, 0), (-1, 0, 0))], "left section")
        rgt = Zone("Fracture_03", [((a, 0, 0), (1, 0, 0))], "right section")
        return Plan(spec, fam, [mid, lft, rgt], [Seam((-a, 0, 0), (1, 0, 0), 0, 1, snap=0.03),
                                                 Seam((a, 0, 0), (-1, 0, 0), 0, 2, snap=0.03)], kw)
    if shape == "Drop":
        # the tray section (its trough: the only physics box) and the two waterfalls under it, torn off where they
        # leave the trough's floor; a waterfall's collider is its occupancy column, so its landing collar (the
        # Down mount on the rack's brush plate) is supported by the waterfall that rests on it
        zs = reg[0][1][2]
        top = Zone("Fracture_01", [((0, 0, zs), (0, 0, 1))],
                   "tray section (trapeze, split collars, waterfall guides)")
        lft = Zone("Fracture_02", [((0, 0, zs), (0, 0, -1)), ((0, 0, 0), (-1, 0, 0))],
                   "left waterfall (bundle drop, landing collar)", hull_from="occupancy")
        rgt = Zone("Fracture_03", [((0, 0, zs), (0, 0, -1)), ((0, 0, 0), (1, 0, 0))],
                   "right waterfall (bundle drop, landing collar)", hull_from="occupancy")
        return Plan(spec, fam, [top, lft, rgt], [Seam((-0.36, 0, zs), (0, 0, 1), 0, 1),
                                                 Seam((0.36, 0, zs), (0, 0, 1), 0, 2),
                                                 Seam((0, 0, zs - 0.2), (-1, 0, 0), 1, 2)], kw)
    if shape in ("TurnH", "TurnUp", "TurnDown"):
        (_, lo0, hi0), (_, lo1, hi1) = reg[:2]
        olo = [max(a, b) for a, b in zip(lo0, lo1)]
        ohi = [min(a, b) for a, b in zip(hi0, hi1)]
        o = [(a + b) / 2 for a, b in zip(olo, ohi)]
        c0 = [(a + b) / 2 for a, b in zip(lo0, hi0)]
        c1 = [(a + b) / 2 for a, b in zip(lo1, hi1)]
        d = [round(b - a, 1) for a, b in zip(c0, c1)]       # the two halves lie 45 deg apart: snap to +-1 / 0
        n = tuple(0.0 if abs(v) < 1e-9 else math.copysign(1.0, v) for v in d)
        z0 = Zone("x", [(o, _neg(n))], "first half of the bend")
        z1 = Zone("x", [(o, n)], "second half of the bend")
        first = 0 if sup and z0.violation(sup[0]) <= z1.violation(sup[0]) else 1
        hang, free = (z0, z1) if first == 0 else (z1, z0)
        hang.id, hang.label, hang.critical = "Fracture_01", hang.label + " (floor strut)", False
        free.id = "Fracture_02"
        nn = hang.halfspaces[0][1]
        return Plan(spec, fam, [hang, free], [Seam(o, nn, 0, 1)], kw)
    if shape == "Tee":
        a, yb = DM_HALF, 0.125
        hub = Zone("Fracture_01", [((-a, 0, 0), (1, 0, 0)), ((a, 0, 0), (-1, 0, 0)), ((0, yb, 0), (0, -1, 0))],
                   "hub (junction, floor strut)")
        lft = Zone("Fracture_02", [((-a, 0, 0), (-1, 0, 0))], "left run arm")
        rgt = Zone("Fracture_03", [((a, 0, 0), (1, 0, 0))], "right run arm")
        br = Zone("Fracture_04", [((-a, 0, 0), (1, 0, 0)), ((a, 0, 0), (-1, 0, 0)), ((0, yb, 0), (0, 1, 0))],
                  "branch arm")
        return Plan(spec, fam, [hub, lft, rgt, br],
                    [Seam((-a, 0, 0), (1, 0, 0), 0, 1, snap=0.02), Seam((a, 0, 0), (-1, 0, 0), 0, 2, snap=0.02),
                     Seam((0, yb, 0), (0, -1, 0), 0, 3, snap=0.02)], kw)
    if shape == "Cross":
        a = DM_HALF
        hub = Zone("Fracture_01", [((-a, 0, 0), (1, 0, 0)), ((a, 0, 0), (-1, 0, 0)), ((0, -a, 0), (0, 1, 0))],
                   "hub and north arm (crossover saddle, floor strut)")
        sth = Zone("Fracture_02", [((-a, 0, 0), (1, 0, 0)), ((a, 0, 0), (-1, 0, 0)), ((0, -a, 0), (0, -1, 0))],
                   "south arm")
        wst = Zone("Fracture_03", [((-a, 0, 0), (-1, 0, 0))], "west arm")
        est = Zone("Fracture_04", [((a, 0, 0), (1, 0, 0))], "east arm")
        return Plan(spec, fam, [hub, sth, wst, est],
                    [Seam((0, -a, 0), (0, 1, 0), 0, 1, snap=0.02), Seam((-a, 0, 0), (1, 0, 0), 0, 2, snap=0.02),
                     Seam((a, 0, 0), (-1, 0, 0), 0, 3, snap=0.02)], kw)
    raise RuntimeError(f"{spec.name}: no fracture plan for tray shape {shape}")


DM_HALF = DM.SLOT_HALF_W     # 0.25: a junction's hub is its middle two cells


# ---------------------------------------------------------------------------------------------------- the room
def _quadrants(xs, ys, label):
    """Zones over a grid of cells split at the planes x = xs[i], y = ys[j] (row-major: y rows, then x): every cell's
    half spaces, and the seams (one per plane, the zones each side as tuples). label(i, j) names a zone."""
    nx, ny = len(xs) + 1, len(ys) + 1
    zones = []
    for j in range(ny):
        for i in range(nx):
            hs = []
            if i > 0:
                hs.append(((xs[i - 1], 0, 0), (1, 0, 0)))
            if i < nx - 1:
                hs.append(((xs[i], 0, 0), (-1, 0, 0)))
            if j > 0:
                hs.append(((0, ys[j - 1], 0), (0, 1, 0)))
            if j < ny - 1:
                hs.append(((0, ys[j], 0), (0, -1, 0)))
            zones.append(Zone(f"Fracture_{len(zones) + 1:02d}", hs, label(i, j)))
    seams = []
    for i, x in enumerate(xs):
        seams.append(Seam((x, 0, 0), (-1, 0, 0), tuple(j * nx + i for j in range(ny)),
                          tuple(j * nx + i + 1 for j in range(ny))))
    for j, y in enumerate(ys):
        seams.append(Seam((0, y, 0), (0, -1, 0), tuple(j * nx + i for i in range(nx)),
                          tuple((j + 1) * nx + i for i in range(nx))))
    return zones, seams


def _floor(spec):
    """The raised floor (panels split IN PLANE, every zone the full thickness): a 1.0 m block parts at
    its real tile joints, each 0.5 m tile with the pedestals, stringers and pads under it (the shared pedestals on the
    joints: their round column goes whole to one tile, their head and base plates part with the tiles); the 0.5 m
    block is one tile, cracked in two along its panel line (the solid tile's skin plates part there). Structural: no
    critical zone (vanilla DeckPanel250 / CatwalkSquareBase250)."""
    from . import floor as FL
    n = int(round(2 * FL.half(spec) / DM.RF_TILE))
    if n == 1:
        zones, seams = _quadrants([], [0.0], lambda i, j: ("back", "front")[j] + " half of the tile (deck, its "
                                                                                 "pedestals, stringers and pads)")
    else:
        zones, seams = _quadrants([0.0], [0.0], lambda i, j: f"{('back', 'front')[j]} {('left', 'right')[i]} tile "
                                                             "(deck, its quarter of the pedestals and stringers)")
    p = Plan(spec, "floor", zones, seams, KEEP_WHOLE["floor"])
    p.long_cut = ROOM_LONG_CUT
    return p


def _roof(spec):
    """The containment roof (split in plane per bay): every 0.5 m bay its own zone with its pane, caps,
    frame segment, clamps and fire release, parting along the mullions (a member centred on its mullion goes whole
    to one side; the beams and caps across it are cut). Keen's table is keyed on the model's largest edge: the
    panel's gaskets and clamps stop 1 mm inside the cell planes, so the 1.0 m panel measures 0.998 m and is allowed 3
    zones (the -y row's two bays stay one zone), the 1.5 m one 5 (its 6 bays become 4 zones, the middle bays' panes
    cracked across the aisle's centre line), the 2.0 m one 10 (8 bays). Structural: no critical zone."""
    from . import contain as C
    w = C.width(spec)
    side = ("-x", "+x")
    lab = "(pane, caps, frame segment, clamps, fire release)"
    if round(w / 0.5) == 2:
        zones = [Zone("Fracture_01", [((0, 0, 0), (0, -1, 0))], f"bay row 1 across the aisle, both bays {lab}"),
                 Zone("Fracture_02", [((0, 0, 0), (0, 1, 0)), ((0, 0, 0), (-1, 0, 0))],
                      f"bay row 2 across the aisle, -x bay {lab}"),
                 Zone("Fracture_03", [((0, 0, 0), (0, 1, 0)), ((0, 0, 0), (1, 0, 0))],
                      f"bay row 2 across the aisle, +x bay {lab}")]
        seams = [Seam((0, 0, 0), (0, -1, 0), 0, (1, 2)), Seam((0, w / 4, 0), (-1, 0, 0), 1, 2)]
    else:
        ys = [0.0] if round(w / 0.5) == 3 else C.mullion_ys(spec)
        zones, seams = _quadrants([0.0], ys, lambda i, j: f"bay row {j + 1} across the aisle, {side[i]} half {lab}")
    p = Plan(spec, "contain_roof", zones, seams, KEEP_WHOLE["contain_roof"])
    p.long_cut = ROOM_LONG_CUT
    return p


def _door(spec):
    """The containment door's frame ("frame segments around an opening", vanilla SlidingDoorNarrow250: 8
    zones, 7 critical): the lintel over the opening and the posts (it carries the track the closed leaves hang from:
    their Closed dummies are SupportingFracture of it), each pocket tower in three pieces at the cover's panel lines
    (real joints), the top piece with the header over its pocket, and the threshold. The seams are straight, at the
    joints: the header parts over the posts (x = +-(W/2 + POST_OUT)), the towers at contain.POCKET_SPLITS, the sill
    at the posts' faces. Every zone but the 8 mm sill is critical: a dead frame piece stops the door."""
    from . import contain as C
    W = C.door_w(spec)
    xi, xo = W / 2 - C.POST_IN, W / 2 + C.POST_OUT
    s0, s1 = C.POCKET_SPLITS
    zb = C.SILL_TOP + 0.01
    X = lambda x, sg: ((x, 0, 0), (sg, 0, 0))   # noqa: E731   (x - x0) * sg >= 0
    Z = lambda z, sg: ((0, 0, z), (0, 0, sg))   # noqa: E731
    zones = [Zone("Fracture_01", [X(-xo, 1), X(xo, -1), Z(C.ZH, 1)], "lintel (header over the opening and the posts, "
                  "the track, the closers)", critical=True)]
    for tag, sg in (("-x", -1), ("+x", 1)):
        out = X(sg * xi, sg)
        zones += [Zone(f"Fracture_{len(zones) + 1:02d}", [out, Z(s0, -1)], f"{tag} pocket tower, bottom (post foot, "
                       "kick plate)", critical=True),
                  Zone(f"Fracture_{len(zones) + 2:02d}", [out, Z(s0, 1), Z(s1, -1)], f"{tag} pocket tower, middle",
                       critical=True),
                  Zone(f"Fracture_{len(zones) + 3:02d}", [out, Z(s1, 1)], f"{tag} pocket tower, top (with the header "
                       "over the pocket)", critical=True)]
    zones.append(Zone("Fracture_08", [X(-xi, 1), X(xi, -1), Z(zb, -1)], "threshold (sill)"))
    zh, xp, zs = (C.ZH + C.DH) / 2, -(xi + W) / 2, -C.DH + 0.004   # (points on each seam's own stretch)
    seams = [Seam((-xo, 0, zh), (1, 0, 0), 0, 3), Seam((xo, 0, zh), (-1, 0, 0), 0, 6),
             Seam((xp, 0, s0), (0, 0, -1), (1, 4), (2, 5)), Seam((xp, 0, s1), (0, 0, -1), (2, 5), (3, 6)),
             Seam((-xi, 0, zs), (1, 0, 0), 7, 1), Seam((xi, 0, zs), (-1, 0, 0), 7, 4)]
    sup = {lf.name + "Closed": (C.leaf_centre_x(spec, lf.side, 0.0), 0.0, C.LEAF_ORIGIN_Z) for lf in C.door_leaves(spec)}
    p = Plan(spec, "contain_door", zones, seams, KEEP_WHOLE["contain_door"], supporting=sup)
    p.long_cut = ROOM_LONG_CUT
    return p


def _crac(spec):
    """The in-row cooler ("functional core + shell plates"; 9 zones, within vanilla's 8-12 at 2.5 m).
    The machine is the coil core between the filter section and the fan plenums: it holds the function, is critical
    and is the volume-dominant zone, with every other zone its neighbour (it always stays in the largest island). In
    front of it the three fan sections (each a fan module with its plenum, split on the door rails between the
    modules) are critical too: their rotors are ConditionalSubParts, which only despawn when the block stops being
    Functional, so a dead fan section must stop the block (vanilla Gyroscope250 makes the zones under its rotating
    rings critical the same way); each supports its CracFan dummy. The controller (display, lamps, the terminal it
    supports) is a shell plate, as vanilla's terminal plates; so are the two filter-door halves (split on the grille's
    middle rail), the plinth and the top band (headers, rail, brush plates, the CHW well). Seams follow real joints:
    the door rails, the controller's shadow gap, the grille rail, the plinth top and the slot band's top. The
    rear's lower half is the bolted service bay (its two O2 / coolant ports supported by it), the upper half the
    filter door: the old grille rail is their joint."""
    from . import crac as C
    hz = C.H / 2
    zp, zt = 0.25 - hz, C.ZT - hz
    z1, z2, zc, zr = (z - hz for z in C.SEAM_Z)
    yf, yr = C.SEAM_Y
    up, down = (0, 0, 1), (0, 0, -1)
    Z = lambda z, n: ((0, 0, z), n)   # noqa: E731
    F_ = ((0, yf, 0), (0, 1, 0))       # in front of the core
    R_ = ((0, yr, 0), (0, -1, 0))      # behind it
    zones = [Zone("Fracture_01", [Z(zp, up), Z(zt, down), ((0, yf, 0), (0, -1, 0)), ((0, yr, 0), (0, 1, 0))],
                  "coil core (cooling coil, plenum walls, side panels' middle)", critical=True),
             Zone("Fracture_02", [Z(zp, up), Z(z1, down), F_], "fan section F1 (module, plenum, door below the rail)",
                  critical=True),
             Zone("Fracture_03", [Z(z1, up), Z(z2, down), F_], "fan section F2 (module, plenum, the door's latch)",
                  critical=True),
             Zone("Fracture_04", [Z(z2, up), Z(zc, down), F_], "fan section F3 (module, plenum)", critical=True),
             Zone("Fracture_05", [Z(zc, up), Z(zt, down), F_], "controller (display, RUN / ALARM lamps, keys, vent)"),
             Zone("Fracture_06", [Z(zp, up), Z(zr, down), R_],
                  "service bay (the bolted panel, the two O2 / coolant service ports)"),
             Zone("Fracture_07", [Z(zr, up), Z(zt, down), R_], "filter door (grilles 1-2, filters)"),
             Zone("Fracture_08", [Z(zp, down)], "plinth (feet, nameplate, condensate pan, float switch)"),
             Zone("Fracture_09", [Z(zt, up)], "top band (headers, containment rail, brush plates, CHW well)")]
    seams = [Seam((0, 0, zp), down, 7, (0, 1, 5)),
             Seam((0, 0, zt), up, 8, (0, 4, 6)),
             Seam((0, yf, -0.2), (0, 1, 0), (1, 2, 3, 4), 0),
             Seam((0, yr, -0.5), (0, -1, 0), (5, 6), 0),
             Seam((0, 0.4, z1), down, 1, 2),
             Seam((0, 0.4, z2), down, 2, 3),
             Seam((0, 0.4, zc), down, 3, 4),
             Seam((0, -0.5, zr), down, 5, 6)]
    sup = {f"{C.FAN}{i + 1}": p for i, p in enumerate(C.fan_points(spec))}
    tx, ty, tz = C.TERMINAL
    sup[C.TERMINAL_DUMMY] = (tx, ty, tz - hz)
    for name, (x, y, z) in C.port_points(spec).items():   # the service ports: their bay supports them (a dead bay
        sup[name] = (x, y + 0.05, z)                        # panel disables the port once it is a real one)
    p = Plan(spec, "crac", zones, seams, KEEP_WHOLE["crac"], supporting=sup)
    p.long_cut = ROOM_LONG_CUT
    return p


# ----------------------------------------------------------------------------------------------------------------- PDUs
def _pdu_cabinet(spec):
    """The PDU cabinet (the rack pattern: parts at real joints, every zone a full-section chunk): the
    plinth's front and rear halves; the cabinet body in a lower and an upper section, parting at the shadow gap
    between the isolator panel and the hinged breaker cover (dc/pdu.py PANEL_JOINT_Z), each split left / right at
    x = 0 (between the two breaker columns); the top band's front and rear halves. Decorative (no function to
    stop): no critical zone."""
    from . import pdu
    H = pdu.H
    zp, zt = 0.25 - H / 2, pdu.ZT - H / 2
    zm = pdu.PANEL_JOINT_Z - H / 2                           # the cover / isolator panel joint (local 0.79 m)
    down, up = (0, 0, -1), (0, 0, 1)
    L, R = ((0, 0, 0), (-1, 0, 0)), ((0, 0, 0), (1, 0, 0))
    yp, yt = (0, 0, zp - 0.125), (0, 0, (zt + H / 2) / 2)
    Z = [Zone("Fracture_01", [((0, 0, zp), down), (yp, (0, 1, 0))], "plinth, front half"),
         Zone("Fracture_02", [((0, 0, zp), down), (yp, (0, -1, 0))], "plinth, rear half"),
         Zone("Fracture_03", [((0, 0, zp), up), ((0, 0, zm), down), L],
              "body, lower -x half (DANGER placard, side panel, rear cover)"),
         Zone("Fracture_04", [((0, 0, zp), up), ((0, 0, zm), down), R],
              "body, lower +x half (rotary isolator, side panel, rear cover)"),
         Zone("Fracture_05", [((0, 0, zm), up), ((0, 0, zt), down), L],
              "body, upper -x half (even breaker column, meter half, gland plate)"),
         Zone("Fracture_06", [((0, 0, zm), up), ((0, 0, zt), down), R],
              "body, upper +x half (odd breaker column, meter half, gland plate)"),
         Zone("Fracture_07", [((0, 0, zt), up), (yt, (0, 1, 0))], "top band, front half (brush plates, label)"),
         Zone("Fracture_08", [((0, 0, zt), up), (yt, (0, -1, 0))], "top band, rear half (exhaust louvre)")]
    c = (-0.25, 0.3)                                          # (a point in the left half's plan)
    S = [Seam(yp, (0, 1, 0), 0, 1, snap=0.03),
         Seam((*c, zp), down, (0, 1), (2, 3)),
         Seam((*c, zm), down, (2, 3), (4, 5), snap=0.015),
         Seam((*c, zt), up, (6, 7), (4, 5)),
         Seam(yt, (0, 1, 0), 6, 7, snap=0.03),
         Seam((0, 0.3, (zp + zm) / 2), (-1, 0, 0), 2, 3, snap=0.002),
         Seam((0, 0.3, (zm + zt) / 2), (-1, 0, 0), 4, 5, snap=0.002)]
    p = Plan(spec, "pdu_cabinet", Z, S, KEEP_WHOLE["pdu_cabinet"])
    p.long_cut = LONG_CUT
    return p


def pdu_strip_seams(spec):
    """Strip-local z of the strip's fracture seams: between a slot's outlet housings (their top: slot z 0.116) and
    the bank head / the next cords over them (slot z 0.130), where only the body and the cord channel run (no cord,
    outlet, plug or bracket is cut): after slot 3 and slot 6 on the 42U strip, after slot 2 on the 24U."""
    from . import pdu
    ks = (3, 6) if pdu.nslots(spec) == 8 else (2,)
    return [round(pdu.slot_z(spec, k) + 0.122, 6) for k in ks]


def _pdu_strip(spec):
    """The zero-U strip (a linear block: sections along the run): the extruded body and its cord
    channel snap across between two slots' outlets, 3 sections on the 42U strip (Keen allows 10 at 2.0 m), 2 on the
    24U (3 at 0.88 m); Fracture_01 is the bottom section with the inlet cord and plug. Decorative: no critical zone."""
    zs = pdu_strip_seams(spec)
    up, down = (0, 0, 1), (0, 0, -1)
    labels = ["bottom section (inlet cord and twist-lock plug, bank 1 head)"]
    if len(zs) == 2:
        labels += ["middle section (bank 2 head)", "top section (feed tag)"]
    else:
        labels += ["top section (feed tag)"]
    Z = []
    for i, lab in enumerate(labels):
        hs = []
        if i > 0:
            hs.append(((0, 0, zs[i - 1]), up))
        if i < len(zs):
            hs.append(((0, 0, zs[i]), down))
        Z.append(Zone(f"Fracture_{i + 1:02d}", hs, lab))
    S = [Seam((0, 0, z), down, i, i + 1, snap=0.004) for i, z in enumerate(zs)]
    p = Plan(spec, "pdu_strip", Z, S, KEEP_WHOLE["pdu_strip"])
    p.long_cut = ROOM_LONG_CUT
    return p


# ---------------------------------------------------------------------------------------------------------------- signs
SIGN_SEAM_X = 0.16          # the 1.0 m signs' seams (|x|): between the screen's thirds, clear of the end tabs and
#                             the hanging sign's hangers (x +-ROD_S)


def _sign(spec):
    """The signs ("panels split IN PLANE", vanilla LCDNarrow50: 2 zones, none critical):
    the 1.0 m aisle signs part in three tiles along x (Keen's table: 3 at the measured ~0.95-0.97 m edge), the middle
    one holding the screen's centre (Fracture_01: its LcdPanel dummy is SupportingFracture of it, so the display dies
    with its core) and each end tile its tab / hanger; the 0.5 m rack label in two halves (Keen: 2 at 0.43 m), the
    screen's centre on the seam going to Fracture_01. The screen, housing, bezel, liner and back plate are cut (break
    faces in FracturedMaterial01; the open screen quad gets none); bolts, hangers and stencils go whole. Not critical
    (vanilla LCDs have no critical fracture)."""
    from . import signs as SG
    sc = SG.screens(spec)[0].center
    X = lambda x, sg: ((x, 0, 0), (sg, 0, 0))   # noqa: E731   (x - x0) * sg >= 0
    if spec.variant == "Rack":
        zones = [Zone("Fracture_01", [X(0.0, -1)], "-x half (foot, body, bezel, half the screen)"),
                 Zone("Fracture_02", [X(0.0, 1)], "+x half (foot, body, bezel, half the screen)")]
        seams = [Seam((0.0, 0.0, 0.0), (-1, 0, 0), 0, 1)]
    else:
        a = SIGN_SEAM_X
        what = "back plate, housing, bezel" if spec.variant == "Aisle" else "housing, both bezels"
        zones = [Zone("Fracture_01", [X(-a, 1), X(a, -1)], f"middle tile ({what}, the screen's centre)"),
                 Zone("Fracture_02", [X(-a, -1)], f"-x end tile ({what}" + (", gland)" if spec.variant == "Aisle"
                                                                         else ", a hanger)")),
                 Zone("Fracture_03", [X(a, 1)], f"+x end tile ({what}, the AISLE tab" +
                      (")" if spec.variant == "Aisle" else ", a hanger)"))]
        seams = [Seam((-a, 0.0, 0.0), (1, 0, 0), 0, 1), Seam((a, 0.0, 0.0), (-1, 0, 0), 0, 2)]
    p = Plan(spec, "sign", zones, seams, KEEP_WHOLE["sign"], supporting={"LcdPanel": tuple(sc)})
    p.long_cut = ROOM_LONG_CUT
    return p
