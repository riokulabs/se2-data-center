"""Build-menu names and descriptions (plain text, the kind verified in an earlier prototype). Names go on both the BlockKind
(the menu tile) and the block definition's UIData.Name; descriptions only on the BlockKind (UIData has no
Description field: the builder rejects unknown members)."""
from . import catalog

_RACK_DESC = ("Open-frame 19-inch server rack, {u}U: {n} server slots on slide rails, cable managers in both "
              "side columns{tray}. Place servers into the slots.")
_DOOR = {"SplitFront": " with split perforated front doors", "SplitFrontRear": " with split perforated front and rear doors"}

NAMES = {}
for _u, _n in ((42, 8), (24, 4)):
    for _v, _label in (("Open", "Open Frame"), ("SplitFront", "Split Front Doors"),
                       ("SplitFrontRear", "Front + Rear Doors")):
        desc = _RACK_DESC.format(u=_u, n=_n, tray=", overhead cable tray" if _u == 42 else "")
        if _v != "Open":
            desc = desc.replace("Open-frame 19-inch server rack", "19-inch server rack" + _DOOR[_v])
        NAMES[f"DC_Rack{_u}_{_v}"] = (f"Server Rack ({_label})", desc)   # the size is the kind's size selector

NAMES.update({
    "DC_Srv_Timer": ("Timer Server", "Rack-mount timer: a vanilla Timer block in a 6U server chassis."),
    "DC_Srv_EventCtl": ("Event Controller Server",
                        "Rack-mount event controller: a vanilla Event Controller in a 6U server chassis."),
    "DC_Srv_KVM": ("KVM Console", "Rack-mount KVM drawer, 6U: a control panel with a pull-out screen and keyboard."),
    "DC_Srv_UPS": ("UPS", "Rack-mount uninterruptible power supply: a battery with two Power Cell slots, 12U."),
    "DC_Srv_Status": ("Status Display Server", "Rack-mount status panel: an LCD screen in a 6U server chassis."),
    "DC_Srv_Programmable": ("Programmable Server",
                            "Rack-mount script host: a programmable block in a 6U blade chassis (its program runs "
                            "when the game has scripts enabled)."),
    "DC_Srv_Compute": ("Compute Server", "Decorative 6U compute server: drive bays and a honeycomb intake door."),
    "DC_Srv_Storage": ("Storage Server", "Decorative 6U storage server: twelve hot-swap drive caddies."),
    "DC_Srv_Switch": ("Network Switch", "Decorative 6U network switch: 24 ports, SFP uplinks and a fan tray."),
    "DC_Srv_Blank": ("Blanking Panel", "Perforated 6U blanking panel that closes an empty rack slot."),
})

# ---------------------------------------------------------------------------------------------------- cable trays
# "Full", "Moderate", ... is the cable load; every piece lines its cables up across every joint
# with any other piece of the same load (and a Reducer steps one load down). Titles read "Cable Tray, <shape>
# (<load>)", so a list sorted by name keeps a shape's four loads together and the load is always last. Names carry no
# size: the two straights (one kind, two sizes) and the three rod lengths (one kind, three sizes) share
# their kind's name and the game's size selector tells them apart; the descriptions keep the lengths.
_LOAD = {"Empty": "no cables", "Low": "low cable load (two data bundles)",
         "Moderate": "moderate cable load (data, fibre and power)", "Full": "full cable load (two layers)"}
_JOINT = " Cables line up across every joint."
_TRAY = {   # shape -> (title stem, description stem)
    "StraightS": ("Straight Short", "Overhead wire-basket cable tray, 0.5 m straight"),
    "StraightL": ("Straight Long", "Overhead wire-basket cable tray, 1.5 m straight"),
    "TurnH": ("Horizontal Turn", "Overhead wire-basket cable tray, 90 degree horizontal turn (0.5 m radius)"),
    "TurnUp": ("Turn Up", "Overhead wire-basket cable tray, 90 degree turn up into a vertical riser"),
    "TurnDown": ("Turn Down", "Overhead wire-basket cable tray, 90 degree turn down from a vertical riser"),
    "Tee": ("Tee", "Overhead wire-basket cable tray, T junction with a side branch"),
    "Cross": ("Cross", "Overhead wire-basket cable tray, X crossing with a crossover saddle"),
    "Drop": ("Rack Drop", "Overhead wire-basket cable tray, 1.0 m straight over a rack with two cable waterfalls "
                          "down into the rack's top-entry brushes"),
}
_DOWN = {"Full": "Moderate", "Moderate": "Low", "Low": "Empty"}
_RODS = {"025": "0.25", "100": "1.0", "200": "2.0"}
_RODS_DESC = ("Threaded hanger rods with coupler nuts and ceiling anchor plates. Extends the hang of a cable tray "
              "below a higher ceiling; snaps onto the tray's rod plates.")
KIND_NAMES = {}   # kind owner -> the tile text of a multi-size kind (dc/menu.py kind_text)
for _b in catalog.TRAYS:
    if _b.family == "trayrods":
        _m = _RODS[_b.name.rsplit("_", 1)[1]]
        NAMES[_b.name] = ("Cable Tray, Hanger Rods", _RODS_DESC.replace("rods with", f"rods, {_m} m, with"))
    elif _b.variant == "Chute":
        NAMES[_b.name] = ("Cable Tray, Long Drop Chute",
                          "Ladder chute that carries a Rack Drop's two cable waterfalls 1.25 m further down, onto a "
                          "half-height rack's roof brushes.")
    elif _b.variant == "Reducer":
        _lo = _DOWN[_b.density]
        NAMES[_b.name] = (f"Cable Tray, Reducer ({_b.density} to {_lo})",
                          f"Overhead wire-basket cable tray, 0.5 m, stepping the cable load down from {_b.density} "
                          f"to {_lo}: the extra bundles end in strapped rubber boots.{_JOINT}")
    else:
        _t, _d = _TRAY[_b.variant]
        if _b.variant in ("StraightS", "StraightL"):   # one Straight kind, two sizes (dc/menu.py): no size in the name
            _t = "Straight"
        NAMES[_b.name] = (f"Cable Tray, {_t} ({_b.density})", f"{_d}, {_LOAD[_b.density]}.{_JOINT}")
for _d in catalog.TRAY_DENSITIES:
    KIND_NAMES[f"DC_Tray_StraightL_{_d}"] = (
        f"Cable Tray, Straight ({_d})",
        f"Overhead wire-basket cable tray, straight: 0.5 m (Short) or 1.5 m (Long), {_LOAD[_d]}.{_JOINT}")
KIND_NAMES["DC_TrayRods_100"] = ("Cable Tray, Hanger Rods", "Threaded hanger rods, 0.25 m, 1.0 m or 2.0 m, with "
                                 "coupler nuts and ceiling anchor plates. Extends the hang of a cable tray below a "
                                 "higher ceiling; snaps onto the tray's rod plates.")

# ---------------------------------------------------------------------------------------------------- room pieces
# Honest about what each block does in game: the CRAC draws power and runs its fans (vanilla 2.4 has
# no cooling or room atmosphere); the PDUs are decorative (vanilla has no power-junction block).
_SIZE = {"050": "0.5", "100": "1.0", "150": "1.5", "200": "2.0"}
for _b in catalog.ROOM:
    _k = _b.name.rsplit("_", 1)[1]
    if _b.family == "floor":
        _m = _SIZE[_k]
        _n = "one 0.5 m tile" if _k == "050" else "four 0.5 m tiles"
        if _b.variant == "Solid":
            NAMES[_b.name] = ("Raised Floor (Solid)",
                              f"Raised-floor access panel, {_m} x {_m} m ({_n}) on adjustable pedestals, 0.25 m "
                              f"high. Racks, coolers and containment doors stand on its top plane.")
        else:
            NAMES[_b.name] = ("Raised Floor (Perforated)",
                              f"Perforated raised-floor panel, {_m} x {_m} m ({_n}), 25 % open over a volume damper: "
                              f"the cold-aisle tile that lets chilled air up in front of the racks. 0.25 m high.")
    elif _b.family == "contain_door":
        NAMES[_b.name] = ("Containment Door",
                          f"Sliding end-of-aisle door for a {_SIZE[_k]} m hot or cold aisle; mounts on the end racks' "
                          f"sides.")
    elif _b.family == "contain_roof":
        NAMES[_b.name] = ("Containment Roof",
                          f"Frosted roof panel over one rack pitch (1.0 m) of a {_SIZE[_k]} m contained aisle. Rests "
                          f"on the racks' containment rails, flush with the rack tops; its fire-release links let it "
                          f"drop away so sprinklers reach the racks.")
NAMES.update({
    "DC_CRAC": ("In-Row Cooler (CRAC)",
                "In-row computer-room air conditioner the size of a 42U rack: takes the hot aisle's air through its "
                "rear filters and blows it out chilled at the front. Draws power and runs its fans while switched on."),
    "DC_PDU_Cabinet": ("PDU Cabinet",
                       "Floor-standing power distribution cabinet the size of a 42U rack: 400 V incomer, rotary "
                       "isolator, meter and 2 x 12 branch breakers feeding the rack PDUs overhead. Decorative."),
    "DC_Sign_Aisle": ("Aisle Sign",
                      "Editable 1.0 x 0.25 m LCD sign for an aisle (\"AISLE 1 COLD\"): on a wall or on a containment "
                      "door's header."),
    "DC_Sign_AisleHang": ("Hanging Aisle Sign",
                          "Double-faced editable LCD aisle sign, 1.0 x 0.25 m, hung across the aisle from cable-tray "
                          "rods."),
    "DC_Sign_Rack": ("Rack Label",
                     "Editable 0.5 x 0.25 m LCD label (\"RACK 3.01\") for a rack's top front edge, between the cable "
                     "tray's two drops."),
})
for _h in (42, 24):
    for _f, _side in (("A", "right"), ("B", "left")):
        NAMES[f"DC_PDU_Rack{_h}_{_f}"] = (
            f"Rack PDU (Feed {_f})",
            f"Zero-U power strip for a {_h}U rack's {_side} rear column (feed {_f}): one outlet pair per slot, its "
            f"inlet plugged into the plinth socket. Decorative.")
# the tile text of the multi-size room kinds (dc/menu.py kind_owner); the game lists the sizes under it
KIND_NAMES.update({
    "DC_Floor_Solid_100": ("Raised Floor (Solid)",
                           "Raised-floor access panel on adjustable pedestals, 0.25 m high: 0.5 m (one tile) or 1.0 m "
                           "(four 0.5 m tiles). Racks, coolers and containment doors stand on its top plane."),
    "DC_Floor_Perf_100": ("Raised Floor (Perforated)",
                          "Perforated raised-floor panel, 25 % open over a volume damper: the cold-aisle tile that lets "
                          "chilled air up in front of the racks. 0.5 m (one tile) or 1.0 m (four tiles), 0.25 m high."),
    "DC_Contain_Door_200": ("Containment Door",
                            "Sliding end-of-aisle door for a 1.0 m, 1.5 m or 2.0 m hot or cold aisle; mounts on the end "
                            "racks' sides."),
    "DC_Contain_Roof_200": ("Containment Roof",
                            "Frosted roof panel over one rack pitch (1.0 m) of a contained aisle, 1.0 m, 1.5 m or 2.0 m "
                            "wide. Rests on the racks' containment rails, flush with the rack tops; its fire-release "
                            "links let it drop away so sprinklers reach the racks."),
})
for _f, _side in (("A", "right"), ("B", "left")):
    KIND_NAMES[f"DC_PDU_Rack42_{_f}"] = (
        f"Rack PDU (Feed {_f})",
        f"Zero-U power strip for a rack's {_side} rear column (feed {_f}), 24U or 42U: one outlet pair per slot, its "
        f"inlet plugged into the plinth socket. Decorative.")
