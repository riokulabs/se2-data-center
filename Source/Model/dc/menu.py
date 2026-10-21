"""Build-menu (G-screen) grouping, the vanilla way (no Blender). Evidence: decompiled 2.4.0.95 Game2.Simulation
Keen.Game2.Simulation.StreamedUI.Categories and Game2.Client ...UI.TerminalScreen.GScreen.

The G-screen tree is Category -> Subcategory -> BlockGroup (one tile) -> BlockKind (a tile inside the group) -> the
kind's blocks (the size selector):
  * BlockKindDefinition = "blocks of the same type but different sizes". A block joins a kind through its own
    CubeBlockDefinition.BlockKind; BlockKindDefinitionPostProcessor orders a kind's blocks by DisplaySize
    (= the block's largest cell extent x 0.25 m), assigns BlockSize1..4 in that order, and the tile lists them all
    (vanilla Battery50 / Battery150 / Battery250 all point at the one PowerBattery kind).
  * BlockGroupDefinition = the tile in a subcategory. A kind lists its groups in BlockKindDefinition.BlockGroups;
    BlockGroupDefinitionPostProcessor inserts each kind into its groups ordered by OrderingPriority (0 = last), then
    name, then GUID. SubcategoryDefinitionPostProcessor sorts multi-kind groups before single-kind groups.
  * Vanilla family entries are multi-kind groups: Decor/LCDs "LCD" (LCDFlat, LCDNarrow, LCDWide, LCDCorner),
    Automation/Inputs "ButtonsAll" (Button, ButtonPanel), the armour "BasicShapes" groups.

So the Data Center gets ONE subcategory ("Data Center", in the vanilla Automation category) with ONE group per
family: "Server Racks" and "Rack Servers". Racks: three kinds (Open Frame, Split Front Doors, Front + Rear Doors),
each holding its 42U and 24U block as the two sizes (24U = size 1, 42U = size 2). Servers: one kind per server type
(all servers share DisplaySize 0.75 m, so a kind per type, as vanilla does for same-size blocks).
Unlike vanilla LCDs we do NOT also add a single-kind group per kind: the menu keeps one entry per family.

The 24U racks' own cloned kinds then hold no block; a kind with no blocks is skipped by the group insertion
(`GetOrderedBlockKindsToInsert`: Blocks.Length > 0) and is left out of the initial unlock, so it is inert. Its file
stays (BlockGroups emptied) because the clone map records it.

Cable trays, in the same subcategory: one group per cable density, "Cable Trays: Empty /
Low / Moderate / Full", each holding one kind per shape in TRAY_ORDER (Empty has no Drop and no Reducer: nothing to
drop, nothing to step down), and "Cable Tray Supports" with the Rods and the Chute. The 0.5 m and 1.5 m straights are
the two sizes of one "Straight" kind (owned by the 1.5 m block, as the 42U rack owns its rack kind); the three rod
hangers (0.25 / 1.0 / 2.0 m) are the three sizes of one "Rods" kind (owned by the 1.0 m). Every other tray block owns
its kind. The trays' cloned vanilla groups (WallInsertPipes: Structural > Walls; the strut: Trusses) are replaced, so
nothing of ours shows under the vanilla tiles.

Room pieces, after the supports: "Raised Floor" (Solid, Perforated: each 0.5 / 1.0 m),
"Room Cooling & Power" (CRAC, PDU Cabinet, Rack PDU Feed A and Feed B: each 24U / 42U), "Aisle Containment" (Door,
Roof: each 1.0 / 1.5 / 2.0 m aisles) and "Signs & Labels" (Aisle Sign, Hanging Aisle Sign, Rack Label). The cloned
vanilla tiles (Catwalks, Gyroscopes, Doors, Deck Panels, LCDs, wall inserts) are left, as the trays' are.

Group tiles in a subcategory are ordered by the group's Order (multi-kind groups first, then Order with 0 = last, then
name; SubcategoryDefinitionPostProcessor): racks, servers, the four densities, supports, then the four room groups.

Every Name / Description / Tooltip here and in dc/names.py is a localisation key (LocKey TextId) that the mod's own
en-US texts resolve (dc/texts.py)."""
from . import catalog

AUTOMATION_CATEGORY = "300a06f0-7d80-469c-bd3e-b19152cb6b7b"   # UI/Screens/GScreen/AutomationCategory.def

SUBCATEGORY = {"name": "Data Center",
               "tooltip": "Server racks, rack-mount servers, overhead cable trays and the room around them: raised floor, cooling, power, aisle containment and signs",
               "file": "DataCenter/UI/DataCenter_SubcategoryDefinition.def"}
_UI = "DataCenter/UI/DataCenter_{}_BlockGroupDefinition.def"
# group key -> the group (tile) name, its file and its Order. Subcategory tiles sort multi-kind groups first, then by
# Order (0 = last), then name (SubcategoryDefinitionPostProcessor.SortBlockGroupsByRules): every group here holds
# several kinds, so Order alone sets the tile order (with Order 0 everywhere the names would put "Rack Servers"
# before "Server Racks" and every cable-tray tile before both).
GROUPS = {
    "rack": {"name": "Server Racks", "file": _UI.format("Racks"), "order": 100},
    "server": {"name": "Rack Servers", "file": _UI.format("Servers"), "order": 200},
}
for _k, _d in enumerate(catalog.TRAY_DENSITIES):   # one tile per cable density
    GROUPS[f"tray_{_d}"] = {"name": f"Cable Trays: {_d}", "file": _UI.format(f"Trays{_d}"), "order": 300 + 100 * _k}
GROUPS["traysupport"] = {"name": "Cable Tray Supports", "file": _UI.format("TraySupports"), "order": 700}
# the room pieces, after the trays (there are no cable loom blocks, so no loom tile)
GROUPS["floor"] = {"name": "Raised Floor", "file": _UI.format("RaisedFloor"), "order": 800}
GROUPS["roompower"] = {"name": "Room Cooling & Power", "file": _UI.format("RoomCoolingPower"), "order": 900}
GROUPS["contain"] = {"name": "Aisle Containment", "file": _UI.format("AisleContainment"), "order": 1000}
GROUPS["signs"] = {"name": "Signs & Labels", "file": _UI.format("SignsLabels"), "order": 1100}
ROOM_GROUP = {"floor": "floor", "crac": "roompower", "pdu_cabinet": "roompower", "pdu_strip": "roompower",
              "contain_door": "contain", "contain_roof": "contain", "sign": "signs"}   # room family -> group key

RACK_KIND_NAMES = {"Open": "Server Rack (Open Frame)", "SplitFront": "Server Rack (Split Front Doors)",
                   "SplitFrontRear": "Server Rack (Front + Rear Doors)"}
RACK_KIND_DESC = {
    "Open": "Open-frame 19-inch server rack: server slots on slide rails, cable managers in both side columns. "
            "42U: 8 slots and an overhead cable tray with fans; 24U: 4 slots.",
    "SplitFront": "19-inch server rack with split perforated front doors (hinged, 85 degree swing). "
                  "42U: 8 slots and an overhead cable tray with fans; 24U: 4 slots.",
    "SplitFrontRear": "19-inch server rack with split perforated front and rear doors (hinged, 85 degree swing). "
                      "42U: 8 slots and an overhead cable tray with fans; 24U: 4 slots.",
}
# menu order inside each group (OrderingPriority 1..n; vanilla treats 0 as "last"), by kind key (kind_key)
RACK_ORDER = ("Open", "SplitFront", "SplitFrontRear")
SERVER_ORDER = ("Timer", "EventCtl", "KVM", "Status", "UPS", "Programmable", "Compute", "Storage", "Switch", "Blank")
TRAY_ORDER = ("Straight", "TurnH", "TurnUp", "TurnDown", "Tee", "Cross", "Drop", "Reducer")
SUPPORT_ORDER = ("Rods", "Chute")
FLOOR_ORDER = ("Solid", "Perf")
ROOMPOWER_ORDER = ("CRAC", "Cabinet", "A", "B")    # the cooler, the floor PDU cabinet, the rack PDUs Feed A / Feed B
CONTAIN_ORDER = ("Door", "Roof")
SIGN_ORDER = ("Aisle", "AisleHang", "Rack")
ORDERS = {"rack": RACK_ORDER, "server": SERVER_ORDER, "tray": TRAY_ORDER, "traysupport": SUPPORT_ORDER,
          "floor": FLOOR_ORDER, "roompower": ROOMPOWER_ORDER, "contain": CONTAIN_ORDER, "signs": SIGN_ORDER}
# a multi-size room kind is owned by this size of it (name suffix): the 1.0 m floor tile of a variant, the 42U strip of
# a feed, the 2.0 m door and roof; every other room block (CRAC, PDU cabinet, the three signs) owns its kind
_ROOM_OWNER = {"floor": "DC_Floor_{v}_100", "pdu_strip": "DC_PDU_Rack42_{v}", "contain_door": "DC_Contain_Door_200",
               "contain_roof": "DC_Contain_Roof_200"}


def group(spec):
    """The group key (GROUPS) whose tile shows this block's kind: the family for racks and servers; a tray piece's
    cable density (a Reducer's is its a side: Full to Moderate sits with Full); the supports' tile for the rod
    hangers and the Chute (no cables of its own, no density)."""
    if spec.family in ("rack", "server"):
        return spec.family
    if spec.family in ROOM_GROUP:
        return ROOM_GROUP[spec.family]
    if spec.family == "trayrods" or spec.variant == "Chute":
        return "traysupport"
    return f"tray_{spec.density}"


def kind_key(spec):
    """The kind a block belongs to, as the ORDERS entry: the rack door variant, the server type, the tray shape with
    both straights as one "Straight" kind, "Rods" for every hanger length."""
    if spec.family == "tray" and spec.variant in ("StraightS", "StraightL"):
        return "Straight"
    return spec.variant


def kind_owner(spec):
    """The catalogue block whose cloned BlockKind holds this block (a kind's blocks are its sizes): the 42U rack of
    the same door variant for both rack heights; the 1.5 m straight of the same density for both straights (0.5 m =
    size 1, 1.5 m = size 2); the 1.0 m rods for the three hanger lengths (0.25 / 1.0 / 2.0 m = sizes 1-3); room pieces
    the 1.0 m tile of a floor variant (0.5 / 1.0 m), the 42U strip of a PDU feed (24U / 42U), the 2.0 m
    door and roof (1.0 / 1.5 / 2.0 m aisles); the block itself otherwise (servers all share one size, so a kind each;
    every other tray shape, the CRAC, the PDU cabinet and each sign has one size)."""
    if spec.family == "rack":
        return catalog.BY_NAME[f"DC_Rack42_{spec.variant}"]
    if kind_key(spec) == "Straight":
        return catalog.BY_NAME[f"DC_Tray_StraightL_{spec.density}"]
    if spec.family == "trayrods":
        return catalog.BY_NAME["DC_TrayRods_100"]
    if spec.family in _ROOM_OWNER:
        return catalog.BY_NAME[_ROOM_OWNER[spec.family].format(v=spec.variant)]
    return spec


def owns_kind(spec):
    return kind_owner(spec) is spec


def priority(spec):
    """OrderingPriority of the block's kind inside its group (1..n)."""
    g = group(spec)
    order = ORDERS["tray" if g.startswith("tray_") else g]
    return order.index(kind_key(spec)) + 1


def kind_blocks(owner):
    """The catalogue blocks that share owner's kind, in DisplaySize order (the game's size order)."""
    return sorted((b for b in catalog.BLOCKS if kind_owner(b) is owner), key=lambda b: max(b.cells))


def display_size(spec):
    """CubeBlockDefinition.DisplaySize: largest bounding-box extent in cells x 0.25 m."""
    return max(spec.cells) * 0.25


def kind_text(spec):
    """(name, description) of a kind owner's tile: rack kinds get the family names, the multi-size tray and room kinds
    (the straights, the rods; floor variants, rack PDU feeds, doors, roofs) theirs (dc/names.py KIND_NAMES); every
    other kind keeps its block's (dc/names.py)."""
    from . import names
    if spec.family == "rack":
        return RACK_KIND_NAMES[spec.variant], RACK_KIND_DESC[spec.variant]
    return names.KIND_NAMES.get(spec.name) or names.NAMES[spec.name]
