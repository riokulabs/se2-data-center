"""Survival cost balancing, no Blender.

How SE2 2.4 turns a recipe into a cost (decompiled Game2.Simulation, CubeBlockDefinition.ComputeMassAndHP and
ComputeRecipeAmounts, called from GeneratedBlockDataLoader with the block's own mass):
    mass  = Density.MassCurveModifier * sqrt(n) * log10(n) + MinBlockMass(5)     n = occupied grid cells
    scale = RoundToIntStrictlyPositive(mass / sum(recipe amount * item MassPerUnit))
    cost  = every recipe amount * scale
A recipe is therefore a MIX that the game multiplies by a whole number. Vanilla mixes are heavy (the wall panel's
4 plates + 3 construction + 3 plates is 260 kg against its own 108 kg), so a clone keeping its source mix pays
scale 1 = exactly the source block's cost, whatever its size: Rack42 Open (301 kg) paid one wall panel.

Our rule: cost = the vanilla SOURCE block's cost x (our mass / the source's mass), both masses from the game's own
formula (so the ratio follows the occupied VOLUME through the game's density curve), each item rounded half up,
at least 1. The recipe is written with those final amounts and the test proves the game's scale stays 1: the game's
scale is RoundToIntStrictlyPositive(block mass / recipe mass), so any recipe of at least 0.67 x the block mass gives 1
(a recipe much heavier than the block, as the minimum-1 items and the trays' length floor make it, rounds to 0 and is
lifted to 1, never more). Door racks: the open frame of the same height (wall-panel source) plus the
vanilla door's mechanism (2 Motor + 1 Electronic Parts) per door side; their Density is set to the open frame's
Mostly Hollow (they are the same hollow frame; the door's Mostly Solid made them 1.8x heavier and tougher).

Cable trays: the same rule against their clone sources. Tray pieces, Drops, Reducers and the Chute
cost from WallInsertPipes (whose recipe is the wall panel's), at Hollow density (an open wire basket); the rod
hangers from StructuralSupportStraight (Mostly Hollow as cloned), whose in-game cost is 2 Steel Plate (its 1-plate
recipe x the game's scale 2). The cables are decoration, so the cable density never changes a cost: occupancy is the
same for the four densities of a shape.

Run-length floor: the volume rule alone puts every tray piece at the minimum-1 floor (13-35 kg blocks),
so a 1.5 m straight cost the same as a 0.5 m one. Tray pieces therefore pay at least one BASE UNIT (one of each item
of the Pipes mix: 1 Steel Plate + 1 Construction, 1 Steel Plate optional) per 0.5 m of tray run, RUN_LENGTH below:
each item = max(the volume rule's amount, units x 1). The rod hangers are not floored: they already scale (1 / 2 / 3).

Balance (three outliers of the volume rule, each replaced by a rule that names what is being paid for):
- SIGNS pay per SCREEN FACE, not per cell: one vanilla LCD50 recipe (3 Electronic Parts, 2 Wire, 2 Glass, plus 3 Steel
  Plate) per face (SIGN_FACES). Vanilla prices its LCDs per screen, not per area (the narrow LCD, the 0.5 m LCD and
  the 2.5 m LCD all use that one recipe; the 5 m LCD doubles it). The volume rule made the hanging sign 3.4x a vanilla
  LCD (10 / 7 / 7 + 10); now the aisle sign and the rack label cost one vanilla LCD and the double-faced hanging sign
  two (= vanilla's LCD500).
- IN-ROW UNITS (CRAC, PDU cabinet: they share the full rack's footprint and are built on its frame:
  plinth, corners, containment rail) pay the 42U open rack's frame (INROW_FRAME, by the rule above) plus their own
  machinery (INROW_KIT): the CRAC the gyroscope's 3 Motor + 2 Wire (its fans), the cabinet 1 Electronic Parts + 2 Wire
  (meter, breakers, busbars). The volume rule priced the decorative cabinet from the wall panel's heavy mix at 200
  cells (23 Steel Plate) above the powered CRAC from the gyroscope's light one (14). Now both carry the frame's steel
  and the CRAC costs more than the cabinet.
- RACK FLOOR (FRAME_FLOOR): a rack never costs less (item mass) than the dearest server it can hold. The half rack's
  60 occupied cells priced it at 370 kg, under the Timer server's 375 (4 Hard Drives); missing mass is paid in the
  frame's optional Steel Plate, one plate at a time (the 24U Open rack: 4 -> 5 optional plates). The bigger racks are
  above the floor already.
"""
import math

from . import catalog

MIN_BLOCK_MASS = 5        # System/Configurations/CubeBlockMassConfiguration.def
DENSITY = {               # Blocks/Shared/Density/*.def: guid -> MassCurveModifier
    "Hollow": ("3dca2cf9-e9b5-4df4-99ed-f7d12f2fce7b", 7),
    "MostlyHollow": ("d8adcfdc-f8e2-467e-9d27-78deae4057da", 11),
    "MostlySolid": ("0dc50007-32a5-4b11-97e5-22a34d7c3d3c", 20),
    "Solid": ("0177a842-4cd2-4318-963a-900824601d83", 35),
}
ITEMS = {                 # Components/*: item guid, MassPerUnit (kg)
    "SteelPlate": ("292eba9e-e5f8-4951-8038-e476a677b584", 35),
    "Construction": ("824e331b-a798-479e-9276-5d35dc02df35", 5),
    "ElectronicParts": ("3df97616-e714-4ddc-baa6-d8fa2df800ce", 5),
    "Motor": ("13fe6b89-4d27-4291-88c0-d0ba06065fa0", 25),
    "Wire": ("e1f56096-b043-4f8e-aca0-40423c54b603", 20),
    "Glass": ("f882a509-434f-4d05-ad2d-41491f6591b5", 20),
    "Motherboard": ("828c2c1e-25e0-44c7-870a-a20810725726", 40),
    "HardDrive": ("616013e6-bbe2-44df-b762-9bcb79771238", 80),
}
# vanilla source blocks: grid cell box (from the LOD0 / collision bounds on the 0.25 m grid), density, recipe
# (critical, optional, BuildTimePerItem in 100 ns ticks; None = the recipe template's), recipe file
SOURCES = {
    "WallInsertPanel": {"cells": (6, 6, 1), "density": "MostlyHollow",
                        "critical": (("SteelPlate", 4), ("Construction", 3)), "optional": (("SteelPlate", 3),),
                        "time": 3300000, "file": "Blocks/Walls/Inserts/Panel/WallInsertPanelRecipeDefinition.def"},
    # cells: the LOD0 model's bounds (NarrowSlidingDoor.fbx, imported read-only in Blender: 2.51 x 2.51 x 0.51 m without
    # two overhanging decal strips); the door has no glTF collider (a Havok .hkt), so the SDK test checks only the
    # density chain. Our door racks and containment doors cost from the wall panel plus DOOR_KIT, not from this.
    "SlidingDoorNarrow250": {"cells": (10, 10, 2), "density": "MostlySolid",
                             "critical": (("SteelPlate", 4), ("Motor", 2), ("ElectronicParts", 1)),
                             "optional": (("SteelPlate", 3),), "time": 1625000,
                             "file": "Blocks/Doors/Recipes/SlidingDoor_CubeBlockRecipeDefinition.partialdef",
                             "block_chain": (
                                 "Blocks/Doors/SlideDoorNarrow/250/SlidingDoorNarrow250_DoorsPowerableBlockDefinition.partialdef",
                                 "Templates/Blocks/BaseDefinitions/DoorsPowerableBlockDefinition.partialdef",
                                 "Templates/Blocks/BaseDefinitions/PowerableBlockDefinition.def")},
    "Timer50": {"cells": (2, 2, 2), "density": "MostlySolid",
                "critical": (("Construction", 1), ("Motherboard", 1), ("HardDrive", 5)),
                "optional": (("Construction", 3),), "time": 3250000, "file": "Blocks/Timer/50/Timer50RecipeDefinition.def"},
    "EventController": {"cells": (4, 2, 2), "density": "MostlySolid",
                        "critical": (("Construction", 4), ("ElectronicParts", 3)), "optional": (("SteelPlate", 3),),
                        "time": 3300000, "file": "Blocks/EventController/100/EventControllerRecipeDefinition.def"},
    "ControlPanel25": {"cells": (1, 1, 1), "density": "Hollow", "critical": (("Construction", 1),), "optional": (),
                       "time": None,
                       "file": "Blocks/ControlPanel/25/ControlPanel25_CubeBlockRecipeDefinition.partialdef"},
    "Battery50": {"cells": (2, 2, 2), "density": "MostlySolid",
                  "critical": (("Construction", 6), ("ElectronicParts", 1)), "optional": (("Construction", 3),),
                  "time": 3250000, "file": "Blocks/Batteries/Battery/Recipes/Battery_50_BlockRecipeDefinition.partialdef"},
    "LCDFlat50": {"cells": (2, 2, 1), "density": "MostlyHollow",
                  "critical": (("ElectronicParts", 3), ("Wire", 2), ("Glass", 2)), "optional": (("SteelPlate", 3),),
                  "time": 3300000, "file": "Blocks/LCDPanels/Recipes/LCDPanel50_CubeBlockRecipeDefinition.def"},
    # the cable trays' clone sources. Both inherit through partial-definition Copy chains, so the
    # SDK check (test_sources_match_sdk) follows "recipe_chain" / "block_chain" (each file's BaseDefinition is the
    # next file's Guid) and reads the cell box from the "collision" glTF (the collider's extent on the 0.25 m grid).
    # The pipes' recipe IS the wall panel's (an unchanged Copy); both blocks take Mostly Hollow from the
    # StructuralCubeBlockDefinition template.
    "WallInsertPipes": {"cells": (6, 6, 1), "density": "MostlyHollow",
                        "critical": (("SteelPlate", 4), ("Construction", 3)), "optional": (("SteelPlate", 3),),
                        "time": 3300000, "file": "Blocks/Walls/Inserts/Pipes/WallInsertPipesRecipeDefinition.partialdef",
                        "recipe_chain": ("Blocks/Walls/Inserts/Panel/WallInsertPanelRecipeDefinition.def",),
                        "block_chain": ("Blocks/Walls/Inserts/Pipes/WallInsertPipes_StructuralCubeBlockDefinition.partialdef",
                                        "Templates/Blocks/BaseDefinitions/StructuralCubeBlockDefinition.partialdef"),
                        "collision": "Blocks/Walls/Inserts/Pipes/Models/NonFractured/WallInsertPipes_collision.gltf"},
    "StructuralSupportStraight": {
        "cells": (2, 10, 1), "density": "MostlyHollow", "critical": (("SteelPlate", 1),), "optional": (),
        "time": 16250000, "file": "Blocks/Truss/Struts/Long/StructuralSupportStraight_CubeBlockRecipeDefinition.partialdef",
        "recipe_chain": ("Templates/Blocks/BaseDefinitions/CubeBlockRecipeDefinition.def",),
        "block_chain": ("Blocks/Truss/Struts/Long/StructuralSupportStraight_StructuralCubeBlockDefinition.partialdef",
                        "Templates/Blocks/BaseDefinitions/StructuralCubeBlockDefinition.partialdef"),
        "collision": "Blocks/Truss/Struts/Long/Models/NonFractured/TrussFrame_Long_collision.gltf"},
    # the room pieces' clone sources. The cell box is the union of the glTF
    # colliders (the catwalk and gyroscope have several convex pieces) on the 0.25 m grid.
    "CatwalkSquareBase250": {
        "cells": (10, 1, 10), "density": "MostlyHollow", "critical": (("SteelPlate", 1),), "optional": (),
        "time": 5420000, "file": "Blocks/Catwalks/Recipes/Catwalk250BlockRecipeDefinition.partialdef",
        "recipe_chain": ("Templates/Blocks/BaseDefinitions/CubeBlockRecipeDefinition.def",),
        "block_chain": ("Blocks/Catwalks/CatwalkSquareBase/250/CatwalkSquareBase250_StructuralCubeBlockDefinition.partialdef",
                        "Templates/Blocks/BaseDefinitions/StructuralCubeBlockDefinition.partialdef"),
        "collision": "Blocks/Catwalks/CatwalkSquareBase/250/Models/Fractured/CatwalkSquareBase250_Fractured.gltf"},
    "Gyroscope250": {
        "cells": (10, 10, 10), "density": "MostlySolid",
        "critical": (("SteelPlate", 8), ("Construction", 1), ("Motor", 3), ("Wire", 2)), "optional": (("SteelPlate", 6),),
        "time": 1250000, "file": "Blocks/Gyroscopes/Recipes/Gyroscope250_RecipeDefinition.partialdef",
        "recipe_chain": ("Templates/Blocks/BaseDefinitions/CubeBlockRecipeDefinition.def",),
        "block_chain": ("Blocks/Gyroscopes/Gyroscopes/250/Gyroscope250_GyroscopePowerableBlockDefinition .partialdef",
                        "Templates/Blocks/BaseDefinitions/GyroscopePowerableBlockDefinition .partialdef",
                        "Templates/Blocks/BaseDefinitions/PowerableBlockDefinition.def"),
        "collision": "Blocks/Gyroscopes/Gyroscopes/250/Models/Fractured/Gyroscope250_Fractured_collision.gltf"},
    "DeckPanel250": {
        "cells": (10, 1, 10), "density": "MostlyHollow", "critical": (("SteelPlate", 1),), "optional": (),
        "time": 5417000, "file": "Blocks/DeckPanel/250/DeckPanel250_RecipeDefinition.partialdef",
        "recipe_chain": ("Blocks/Walls/Recipes/InteriorWalls_RecipeDefinition.partialdef",
                         "Templates/Blocks/BaseDefinitions/CubeBlockRecipeDefinition.def"),
        "block_chain": ("Blocks/DeckPanel/250/DeckPanel250_StructuralCubeBlockDefinition.partialdef",
                        "Templates/Blocks/BaseDefinitions/StructuralCubeBlockDefinition.partialdef"),
        "collision": "Blocks/DeckPanel/250/Models/NonFractured/DeckPanel250.gltf"},
    # the narrow LCD uses the 0.5 m LCD's recipe (LCDPanel50, the same file as LCDFlat50's)
    "LCDNarrow50": {
        "cells": (2, 1, 1), "density": "MostlyHollow",
        "critical": (("ElectronicParts", 3), ("Wire", 2), ("Glass", 2)), "optional": (("SteelPlate", 3),),
        "time": 3300000, "file": "Blocks/LCDPanels/Recipes/LCDPanel50_CubeBlockRecipeDefinition.def",
        "block_chain": ("Blocks/LCDPanels/NarrowLCD/50/LCDNarrow50_LCDPanelPowerableBlockDefinition.partialdef",
                        "Templates/Blocks/BaseDefinitions/LCDPanelPowerableBlockDefinition.partialdef",
                        "Templates/Blocks/BaseDefinitions/PowerableBlockDefinition.def"),
        "collision": "Blocks/LCDPanels/NarrowLCD/50/Models/Nonfractured/NarrowLCD50.gltf"},
}
# our block -> the cost source (door racks: the frame from the wall panel + the door mechanism, see DOOR_KIT)
COST_SOURCE = {"WallInsertPanel": "WallInsertPanel", "SlidingDoorNarrow250": "WallInsertPanel",
               "Timer50": "Timer50", "EventController": "EventController", "ControlPanel25": "ControlPanel25",
               "Battery50": "Battery50", "LCDFlat50": "LCDFlat50",
               "WallInsertPipes": "WallInsertPipes", "StructuralSupportStraight": "StructuralSupportStraight",
               "CatwalkSquareBase250": "CatwalkSquareBase250", "Gyroscope250": "Gyroscope250",
               "DeckPanel250": "DeckPanel250", "LCDNarrow50": "LCDNarrow50"}
DOOR_KIT = (("Motor", 2), ("ElectronicParts", 1))   # per door side: the vanilla sliding door's mechanism parts
# our blocks' densities: as cloned, except the door racks (Mostly Hollow like the open frame) and the cable trays
# (Hollow: an open wire basket is as much air as vanilla's Truss250 lattice, which uses Hollow 3dca2cf9). The rod
# hangers keep the strut's Mostly Hollow. A density that differs from the source's is written to the block
# definition (density_patch).
OUR_DENSITY = {"WallInsertPanel": "MostlyHollow", "SlidingDoorNarrow250": "MostlyHollow", "Timer50": "MostlySolid",
               "EventController": "MostlySolid", "ControlPanel25": "Hollow", "Battery50": "MostlySolid",
               "LCDFlat50": "MostlyHollow", "WallInsertPipes": "Hollow", "StructuralSupportStraight": "MostlyHollow",
               "CatwalkSquareBase250": "MostlyHollow", "Gyroscope250": "MostlySolid", "DeckPanel250": "MostlyHollow",
               "LCDNarrow50": "MostlyHollow"}


# metres of tray run per piece (the run-length floor). Turns, Tee and Cross count the
# centreline from each port to the junction point (their "arms"); the Drop is its 1.0 m through run; the Reducer counts
# as a 1 m run (it carries two loads' worth of fittings: boots, saddle clamp); the Chute is its 1.25 m ladder.
RUN_LENGTH = {"StraightS": 0.5, "StraightL": 1.5, "TurnH": 1.0, "TurnUp": 0.91, "TurnDown": 0.59, "Tee": 1.5,
              "Cross": 2.0, "Drop": 1.0, "Reducer": 1.0, "Chute": 1.25}
RUN_UNIT = 0.5   # metres of run per base unit

# balance outliers (see the module doc)
SIGN_FACES = {"Aisle": 1, "AisleHang": 2, "Rack": 1}       # screen faces per sign (DC_Sign_<variant>)
INROW_FRAME = "DC_Rack42_Open"                             # the frame an in-row unit is built on (same footprint)
INROW_KIT = {"crac": (("Motor", 3), ("Wire", 2)),            # Gyroscope250's fan motors and wiring, unscaled
             "pdu_cabinet": (("ElectronicParts", 1), ("Wire", 2))}   # the meter and breakers; the busbars
FRAME_FLOOR = ("rack",)                                    # families floored at the dearest server's item mass


def run_units(spec):
    """Base units of the run-length floor (0 = no floor: the rod hangers and every non-tray block)."""
    if spec.family != "tray":
        return 0
    return _round(RUN_LENGTH[spec.variant] / RUN_UNIT)


def costed(spec):
    """Whether our cost rule covers the block (every catalogue block)."""
    return spec.copy_from in COST_SOURCE


def density_patch(spec):
    """The Density our block definition must set (a key of DENSITY), or None to keep the cloned source's."""
    d = OUR_DENSITY[spec.copy_from]
    return d if d != SOURCES[spec.copy_from]["density"] else None


def mass(n, density):
    """The game's block mass for n occupied cells (CubeBlockDefinition.ComputeMassAndHP)."""
    return DENSITY[density][1] * math.sqrt(n) * math.log10(n) + MIN_BLOCK_MASS


def cells(box):
    return box[0] * box[1] * box[2]


def _round(x):
    return max(1, int(math.floor(x + 0.5)))


def set_mass(items):
    return sum(a * ITEMS[i][1] for i, a in items)


def game_scale(m, critical, optional):
    """RoundToIntStrictlyPositive(mass / recipe mass): what the game multiplies our recipe by."""
    return max(1, int(math.floor(m / set_mass(tuple(critical) + tuple(optional)) + 0.5)))


def occupied(spec, report=None):
    """Occupied cells: the measured placement occupancy (build_report.json) when built, else the cell box."""
    e = (report or {}).get("blocks", {}).get(spec.name, {}).get("placement", {})
    return e.get("occupied") or cells(spec.cells)


def door_sides(spec):
    """Door mechanisms (DOOR_KIT) on top of the frame: one per door side of a door rack, one for a containment door
    (its two leaves run on one slide, as the vanilla sliding door's two leaves do)."""
    if spec.family == "contain_door":
        return 1
    return {"SplitFront": 1, "SplitFrontRear": 2}.get(spec.variant, 0) if spec.family == "rack" else 0


def source_scale(key):
    """The game's multiplier on a vanilla source's own recipe (1 for the heavy mixes; the long strut's single Steel
    Plate is lighter than the strut, so the game charges it twice)."""
    s = SOURCES[key]
    return game_scale(mass(cells(s["cells"]), s["density"]), s["critical"], s["optional"])


def cost(spec, report=None):
    """{"source", "n", "n_src", "mass", "mass_src", "ratio", "density", "critical", "optional", "time",
    "game_scale"} for one catalogue block. The source's in-game cost is its recipe x source_scale."""
    src_key = COST_SOURCE[spec.copy_from]
    src = SOURCES[src_key]
    n, n_src = occupied(spec, report), cells(src["cells"])
    dens = OUR_DENSITY[spec.copy_from]
    m, m_src = mass(n, dens), mass(n_src, src["density"])
    r = m / m_src
    k = source_scale(src_key)
    u = run_units(spec)
    rule = "volume"
    if spec.family == "sign":
        f = SIGN_FACES[spec.variant]
        crit = [(i, a * k * f) for i, a in src["critical"]]
        opt = [(i, a * k * f) for i, a in src["optional"]]
        rule = f"per screen face x{f}"
    elif spec.family in INROW_KIT:
        frame = cost(catalog.BY_NAME[INROW_FRAME], report)
        crit = _add(frame["critical"], INROW_KIT[spec.family])
        opt = list(frame["optional"])
        rule = f"in-row: {INROW_FRAME} frame + kit"
    else:
        crit = [(i, max(_round(a * k * r), u)) for i, a in src["critical"]]
        opt = [(i, max(_round(a * k * r), u)) for i, a in src["optional"]]
    for i, a in DOOR_KIT:
        if door_sides(spec):
            crit.append((i, a * door_sides(spec)))
    if spec.family in FRAME_FLOOR:
        floor = max(set_mass(c["critical"]) + set_mass(c["optional"]) for c in
                    (cost(b, report) for b in catalog.BLOCKS if b.family == "server"))
        added = 0
        while set_mass(crit) + set_mass(opt) < floor:
            opt = _add(opt, (("SteelPlate", 1),))
            added += 1
        if added:
            rule = f"volume + frame floor ({added} Steel Plate)"
    time = SOURCES[spec.copy_from]["time"] if door_sides(spec) else src["time"]
    return {"source": spec.copy_from, "cost_source": src_key, "n": n, "n_src": n_src, "density": dens,
            "mass": round(m, 1), "mass_src": round(m_src, 1), "ratio": round(r, 3), "critical": crit,
            "optional": opt, "time": time, "game_scale": game_scale(m, crit, opt), "run_units": u, "rule": rule}


def _add(items, extra):
    """items + extra, summing an item already present (order kept, new items appended)."""
    out = [list(x) for x in items]
    for i, a in extra:
        for x in out:
            if x[0] == i:
                x[1] += a
                break
        else:
            out.append([i, a])
    return [tuple(x) for x in out]


def table(report=None):
    return {b.name: cost(b, report) for b in catalog.BLOCKS if costed(b)}


def fmt(items):
    return ", ".join(f"{a} {i}" for i, a in items) or "-"


def markdown(report=None):
    rows = ["| Block | Source (cost from) | Cells ours / source | Mass ours / source (kg) | Ratio | Critical | "
            "Optional |", "|---|---|---|---|---|---|---|"]
    for name, c in table(report).items():
        src = c["source"] + ("" if c["cost_source"] == c["source"] else f" (frame: {c['cost_source']})")
        rows.append(f"| {name} | {src} | {c['n']} / {c['n_src']} | {c['mass']} / {c['mass_src']} | "
                    f"{c['ratio']:.2f} | {fmt(c['critical'])} | {fmt(c['optional'])} |")
    return "\n".join(rows)
