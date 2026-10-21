"""The functional servers' interface to their cloned vanilla definitions (plain Python, no bpy).

The faces (dc/servers/timer.py, eventctl.py, status.py) build their indicator lamps, screens and interaction areas
from these numbers, and dc/integration.py patches the cloned definitions with the same numbers, so the model and
the definitions cannot drift apart.

Mesh-part names. Our 6U servers are unfractured, so every mesh part of the NonFractured and the
Fractured model is named after its material slot (vanilla: "<material>" unfractured, "<Fracture_NN[_Hide]>-<material>"
per fracture group). An indicator component swaps the material of the mesh parts listed in its definition's
IndicatorMeshParts, so a lamp is an indicator lamp exactly when its material SLOT is named like a listed part:

| block           | vanilla indicator (cloned, kept)  | IndicatorMeshParts (vanilla)                 | ours (LOD0)             |
| DC_Srv_Timer    | Timer50 TimerBlockIndicator       | EmissiveOff + Fracture_0N_(Hide|Support)-... | EmissiveOff             |
| DC_Srv_EventCtl | EventControllerIndicator          | Emissive01, Emissive02 + Fracture_0N_Hide-.. | Emissive01, Emissive02  |

The vanilla lists also name per-fracture parts our unfractured models don't have; the component skips parts a
model lacks (vanilla's own lists name parts that only its Fractured model has), so they stay unchanged.
Default material of each slot (its .model MaterialAssignment) = vanilla's: EmissiveOff (d2648963).

Only ReplacementModels changes: it lists the models the indicator may recolour, and the clone still lists Timer50's /
EventController100's own models; integration.py points it at ours (NonFractured, Fractured = Damaged).

States -> material (vanilla, unchanged; colours = ColorIndicatorMaterial Color as R,G,B; blink = rate s / on ratio):
  Timer:  NotFunctional EmissiveOffBroken (off) | NotPowered IndicatorMaterial-POW (153,0,0 dim, 2 s / 0.1)
          Idle +ACT (0,127,0) | Paused +RDY (214,186,0, 2 s / 0.4) | Running +Counting (0,87,127, 1 s / 0.1)
  EventController: NotFunctional off | NotPowered -POW | NullState -RDY (255,255,255) on both parts
          True: Emissive01 +ACT green, Emissive02 off | False: Emissive01 off, Emissive02 +ACT green
"""

from . import dims as DM
from . import subparts as _subparts
from .effects import PARTICLE_EFFECTS_TYPE

# Blender frame of a 6U server (dc/server.py): +Y front, front cell plane y = 0.375; game = (x, z, -y) + shift.
SHIFT = (0.125, 0.0, 0.0)          # dc/export_models.shift for cells (2, 1, 3)

TIMER_IND = "EmissiveOff"           # Timer50's indicator part (every lamp of this slot shows the timer state)
EVC_TRUE = "Emissive01"             # EventControllerIndicator: lit (+ACT) in True, off in False
EVC_FALSE = "Emissive02"            # lit in False, off in True
LCD_SURFACE = "LCDScreen_Off"       # LCDFlat50's LcdMultiPanel surface MeshPartName (kept)
TERMINAL_SCREEN = "Terminal"        # vanilla Terminal material (the lit "SERVER TERMINAL" UI art; Timer50 uses it)

INDICATOR_PARTS = {"DC_Srv_Timer": (TIMER_IND,), "DC_Srv_EventCtl": (EVC_TRUE, EVC_FALSE)}

# Status screen: 2:1, like vanilla's wide LCDs (LCDWide300/500: Resolution 1024 x 512, AspectRatio 2, material
# LCDScreen_Off_2.0 bd7f946b). Face coordinates (server.front_face: a = viewer's right = -x, b = up, d = out).
STATUS_SCREEN = {"a": (-0.186, 0.074), "b": (-0.068, 0.062), "d": -0.011}
STATUS_LCD = {"Resolution": {"X": 1024, "Y": 512}, "AspectRatio": 2}

# Programmable: the chassis management module, the right-hand strip of the bezel opening
# (dc/servers/programmable.py builds it here; the opening is server.face_frame_area: a +-0.212, b -0.105 .. 0.101).
# The Terminal use box covers it and nothing else, so aiming at a blade sled opens no terminal.
PROG_MGMT = {"a": (0.122, 0.212), "b": (-0.105, 0.101)}
# The script-status slot: the SCRIPT STATUS lamp and the LCD's status bar, nothing else. Data-only it
# is vanilla's static amber indicator, the same material as PROG_PSU_LAMP, so the scripts-off block looks unchanged;
# the client script (Scripts/Client/Programmable/ProgrammableLedInjector.cs) maps this mesh part to
# EmissiveGreen while the block is Working. A mesh part is a material slot name, so it needs its own slot.
PROG_LED = "EmissiveScriptStatus"
# The rear PSU power lamps: always the static amber standby lamp (they report power, not the script host).
PROG_PSU_LAMP = "EmissiveAmber"

# KVM use-to-toggle (data-only, so it works with and without scripts). The face is split
# in two use boxes that never overlap, one per job:
#   KvmToggle  vanilla DummyType UsePowerable (System/DummyTypes/UsePowerable.def 504d93cd), which the player's
#              UseActionBindings (System/UseActions/UseActionBindings.def:14) map to UsePowerableAction
#              (UsePowerableAction.def a514581d): Use flips PowerableBlockComponent.Enabled
#              (UsePowerableAction.cs:42-47), the block's On/Off state, so Working and with it the pop-out follow:
#              the FBAC's data-only motion with scripts off, the KVM sequencer (and its door interlock) with scripts
#              on. The hint is vanilla's: the block's name over "Press F to enable / disable"
#              (UsePowerableAction.cs:63-69, en-US UseFunctionalEnable/Disable).
#              Vanilla precedent: GravityGenerator500 / Reactor250 "ButtonTop01" (0.25 x 0.25 x ~0.07).
#              The box is the drawer's band: the bay mouth with the stowed fascia, its pull bar and latch tabs in it.
#              Stowed, Use on the handle pops the console out. Out, the drawer and the screen hang in front of the face
#              with no collision (subparts), so the use ray passes through them to the face: aiming at the drawer's
#              rear, the hinge or the screen's lower edge reaches the band and stows it (the drawer still fills the
#              mouth: it stays 7 cm engaged).
#   Terminal   ControlPanel25's UseTerminal (b15d441f), shrunk from the whole face to the modules above the bay header
#              lip (port-select bank, intake, OSD). Out, the screen stands in front of exactly this band, so aiming at
#              the console's screen opens the terminal: a console behaves like a console.
# A use ray reaches a dummy only through its own block's collider (RaycastEntityDetectorComponent.cs:108-280: the
# dummies of the hit block's model and its descendants that the eye-to-hit line crosses), and the later dummy in the
# list wins a tie (InteractorEntityComponent.cs:83: OrderByDescending(Priority = index)); the toggle is added last.
KVM_TOGGLE = "KvmToggle"
USE_POWERABLE_TYPE = "504d93cd-9f8f-47b5-9be6-6fb633b93ee1"      # System/DummyTypes/UsePowerable.def
USE_TERMINAL_TYPE = "b15d441f-88d0-4722-a377-7adfd75579e7"       # System/DummyTypes (ControlPanel25's "Terminal")
_KVM_LIP_TOP = -0.026 + 0.006 + 0.005    # bay header lip top + the module gap = the modules' floor (servers/kvm.face)
# Both span the bezel opening's width (a +-0.212). The toggle: the bezel's bottom rail and the bay mouth (subparts.BAY
# b -0.105 .. -0.026), from the face's bottom edge (server.layout zb -0.125); d from the fascia's back (y_fascia 0.352)
# to past the pull bar's front (y 0.403). The terminal: the modules and the bezel's top rail, to the face's top edge
# (zt = 0.125 - TOP_GAP), vanilla depth. The rails matter once the console is out: the use rays through the screen's
# lower edge (from above) and its upper half (from below) land on them.
_KVM_FACE_BOTTOM, _KVM_FACE_TOP = -0.125, round(0.125 - DM.SERVER_TOP_GAP, 6)
KVM_TOGGLE_BOX = {"a": (-0.212, 0.212), "b": (_KVM_FACE_BOTTOM, -0.026), "d": (-0.0275, 0.0325)}
KVM_TERMINAL_BOX = {"a": (-0.212, 0.212), "b": (_KVM_LIP_TOP, _KVM_FACE_TOP), "d": (-0.025, 0.025)}


def _box_dummy(box):
    """A face box {a, b, d: (lo, hi)} as DUMMIES' ((a, b, d) centre, game scale (x, y, z))."""
    c = tuple(round((lo + hi) / 2, 6) for lo, hi in (box["a"], box["b"], box["d"]))
    return c, tuple(round(hi - lo, 6) for lo, hi in (box["a"], box["b"], box["d"]))


# Interaction dummies (vanilla type b15d441f; names kept): (face a, face b, face d) centre, game scale (x, y, z).
# Timer / event controller: the whole working face opens the terminal; status: the screen (LCD50 pattern).
DUMMIES = {
    "DC_Srv_Timer": {"Terminal": ((0.0, -0.002, 0.0), (0.42, 0.21, 0.05))},
    "DC_Srv_EventCtl": {"Terminal": ((0.0, -0.002, 0.0), (0.42, 0.21, 0.05))},
    # KVM: the terminal over the upper modules, the On/Off toggle over the drawer band (see KVM_TOGGLE above)
    "DC_Srv_KVM": {"Terminal": _box_dummy(KVM_TERMINAL_BOX), KVM_TOGGLE: _box_dummy(KVM_TOGGLE_BOX)},
    "DC_Srv_Status": {"LcdPanel": ((sum(STATUS_SCREEN["a"]) / 2, sum(STATUS_SCREEN["b"]) / 2, STATUS_SCREEN["d"]),
                                   (STATUS_SCREEN["a"][1] - STATUS_SCREEN["a"][0],
                                    STATUS_SCREEN["b"][1] - STATUS_SCREEN["b"][0], 0.05))},
    # Programmable: ControlPanel25's "Terminal" (added by integration.patch_programmable_dummies) over the module
    "DC_Srv_Programmable": {"Terminal": ((sum(PROG_MGMT["a"]) / 2, sum(PROG_MGMT["b"]) / 2, 0.0),
                                         (PROG_MGMT["a"][1] - PROG_MGMT["a"][0],
                                          PROG_MGMT["b"][1] - PROG_MGMT["b"][0], 0.05))},
}
FRONT_Y = 0.375


def face_to_game(a, b, d):
    """A front-face point (server.front_face: origin on the front cell plane) in the game frame of the .model."""
    x, y, z = -a, FRONT_Y + d, b                    # Blender
    return (round(x + SHIFT[0], 6), round(z + SHIFT[1], 6), round(-y + SHIFT[2], 6))


KVM_FACE_PLANE_Y = _subparts.FACE_Y   # the KVM's bezel front: where a use ray meets its face (one source)


def kvm_use_target(eye, through):
    """Which KVM use box a player aiming from eye through the point `through` (both in the KVM's Blender frame) gets:
    "KvmToggle", "Terminal" or None (the ray meets the face outside both boxes: the ear strips, the header lip, or
    above / below this server, i.e. the neighbour's face). The subparts have no collision, so the ray runs on through
    the drawer and the screen to the face (taken as the bezel plane: every face hit lies within 2 cm of it, inside
    both boxes' depth). Returns (name, (x, z) where the ray meets the face). The game tests the line from the eye to
    the hit against each box (RaycastEntityDetectorComponent.cs:246-280), so the face crossing decides."""
    ex, ey, ez = eye
    px, py, pz = through
    if py >= ey:
        raise ValueError("the eye must be in front of the point it aims through")
    t = (KVM_FACE_PLANE_Y - ey) / (py - ey)
    x, z = ex + t * (px - ex), ez + t * (pz - ez)
    for name, box in ((KVM_TOGGLE, KVM_TOGGLE_BOX), ("Terminal", KVM_TERMINAL_BOX)):   # the toggle wins a tie
        (a0, a1), (b0, b1) = box["a"], box["b"]
        if a0 <= -x <= a1 and b0 <= z <= b1:
            return name, (x, z)
    return None, (x, z)


# ------------------------------------------------------------------------------------------------------- UPS
# DC_Srv_UPS (12U, cells 2x2x3): a Battery50 clone with TWO open Power Cell bays, each the vanilla Battery50 slot frame
# (kit part, dc/servers/cellbay.py) with its own CellSlot / CellAction dummy pair (vanilla names "CellSlot N" /
# "CellAction N": the use action and the slot render read the slot index from the name's trailing number).
# Two vanilla cells (0.30 x 0.31 face, 0.355 deep) cannot sit side by side or stacked in a 0.5 x 0.5 m face, so
# bay 1 opens on the front (cold aisle) and bay 2 on the back (hot aisle), back to back along the 0.75 m depth.
UPS_SHIFT = (0.125, 0.125, 0.0)        # dc/export_models.shift for cells (2, 2, 3)
CELL_KIT_MOUTH = 0.2319                # Battery50 slot frame: its mouth (front-most y) in the vanilla FBX frame
CELL_KIT_HALF = 0.2                    # the frame's half width / height (0.4 m frame; 0.3 m opening)
# Battery50's dummies relative to that mouth (vanilla: CellSlot z -0.12951645, CellAction z -0.10230097 in a
# 2x2x2 block shifted 0.125): the cell's face sits 22.6 mm in front of the mouth, the use box 4.6 mm behind it.
CELL_SLOT_AHEAD = 0.0226
CELL_ACTION_BEHIND = 0.0046
CELL_SLOT_SCALE = (0.3, 0.3, 0.05)     # vanilla CellSlot 0 scale
CELL_ACTION_SCALE = (0.4, 0.4, 0.05)   # vanilla CellAction 0 scale
CELL_SLOT_TYPE = "0dd8466e-8e44-4ebf-93de-218954b34f43"     # System/DummyTypes/CellSlot.def
CELL_ACTION_TYPE = "a7594bb4-e821-4c38-bbb5-0d5c8926854b"   # System/DummyTypes/UseBatterySlotCells.def
# (slot index, bay centre x, bay centre z, mouth y, facing): Blender frame of the UPS, facing +1 = +Y (front)
UPS_BAYS = ((0, 0.030, -0.030, 0.385, 1), (1, 0.018, -0.030, -0.352, -1))
CELL_DEPTH = 0.355                     # an inserted Power Cell's depth behind the mouth (dc/servers/cellbay.py)
POWER_CELL = "089240e7-2ad9-4ec9-adef-cceeda83666e"          # Components/Simple/PowerCell/ItemPowerCell.def
POWER_CELL_MASS = 25                                         # kg (ItemPowerCell MassPerUnit)


def ups_dummies():
    """[(name, type, game position, game orientation quaternion (x, y, z, w), euler hint deg, scale)] of the two bays:
    each bay's CellSlot (the cell model's face, where the game draws the inserted cell) and CellAction (the use box
    you aim at), as Battery50 places them relative to its slot frame; then one "ParticleEffects
    <i>" per bay at the centre of its cell volume (half a cell deep behind the mouth), identity, where the damage
    bands' sparks / smoke / fire play (vanilla 4.0 Battery50 has one ParticleEffects dummy, at its centre; ours has
    two bays in two zones, so each bay's effects stop with its own zone). Also an
    unsupported centre "ParticleEffects" FIRST, as Battery50's, so the one-shot death explosion and the fracture
    effect's orientation (the first dummy of the type) come from the block centre."""
    sx, sy, sz = UPS_SHIFT
    out = [("ParticleEffects", PARTICLE_EFFECTS_TYPE, UPS_SHIFT, (0, 0, 0, 1), (0, 0, 0), (1, 1, 1))]
    for i, x, z, ym, f in UPS_BAYS:
        q, e = ((0, 0, 0, 1), (0, 0, 0)) if f > 0 else ((0, 1, 0, 0), (0, 180, 0))
        for name, typ, yb, sc in ((f"CellSlot {i}", CELL_SLOT_TYPE, ym + f * CELL_SLOT_AHEAD, CELL_SLOT_SCALE),
                                  (f"CellAction {i}", CELL_ACTION_TYPE, ym - f * CELL_ACTION_BEHIND,
                                   CELL_ACTION_SCALE)):
            out.append((name, typ, (round(x + sx, 6), round(z + sy, 6), round(-yb + sz, 6)), q, e, sc))
    for i, x, z, ym, f in UPS_BAYS:
        yb = ym - f * CELL_DEPTH / 2
        out.append((f"ParticleEffects {i}", PARTICLE_EFFECTS_TYPE, (round(x + sx, 6), round(z + sy, 6),
                                                                    round(-yb + sz, 6)), (0, 0, 0, 1), (0, 0, 0),
                    (1, 1, 1)))
    return out
POWER_CELL_MAX_STORED = 180000   # Components/Simple/PowerCell/PowerCellResourceContainerItemDefinition.def MaxStored


# ----------------------------------------------------------------------------------------------------- signs
# The signs' LcdMultiPanel surfaces (dc/signs.py builds the screens with these slot names; dc/integration.py patch_lcd
# writes them, keeping the cloned LCDNarrow50 surface's DefaultScreenMaterial and UseOnlineTexture).
# LCDNarrow50 is natively 2:1 at 512 x 256, which the rack label keeps (its slot on vanilla LCDScreen_Off_2.0);
# the 1.0 m aisle signs are patched to 1024 x 256 with AspectRatio 4, as vanilla ControlSeat250's CustomDisplay04, and
# their slots map to vanilla's 4:1 off-screen material LCDScreen_Off_4.0 (material_guids.py), the one ControlSeat250
# maps that 4:1 surface to. The hanging sign is double-faced: two surfaces (the definition's Surfaces is a list:
# ControlSeat250 has 8; LcdMultiPanelComponent.Init fills a state per surface). No default text: LcdPanelSurface
# has only MeshPartName, Resolution, DefaultScreenMaterial, AspectRatio, UseOnlineTexture and DefaultDisplayName (the
# surface's name in the terminal), so the player types the text; the DefaultDisplayName names each face.
SIGN_LCD_4 = {"Resolution": {"X": 1024, "Y": 256}, "AspectRatio": 4}
SIGN_LCD_2 = {"Resolution": {"X": 512, "Y": 256}, "AspectRatio": 2}
SIGN_LCD = {
    "DC_Sign_Aisle": [dict(MeshPartName="LCDScreen_Off_4", DefaultDisplayName="Aisle Sign", **SIGN_LCD_4)],
    "DC_Sign_AisleHang": [dict(MeshPartName="LCDScreen_Off_4", DefaultDisplayName="Front Face", **SIGN_LCD_4),
                          dict(MeshPartName="LCDScreen_Off_4_Back", DefaultDisplayName="Back Face", **SIGN_LCD_4)],
    "DC_Sign_Rack": [dict(MeshPartName="LCDScreen_Off", DefaultDisplayName="Rack Label", **SIGN_LCD_2)],
}
SIGN_PCU = 35                       # as the clone source (LCDNarrow50)
