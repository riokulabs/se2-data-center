"""Material slot name -> vanilla material definition GUID, for the .model MaterialAssignments (no Blender).

Every GUID is the `Guid` of a vanilla BlockMaterials .def or Copy .partialdef (SDK GameData/Vanilla/Assets/BlockMaterials/...), checked
by Tests/test_integration.py when the SDK is installed. Slot names are free (the .model maps any name), so ours
keep readable names: `AtlasFont_BarlowCondensed_CleanWhite` is vanilla's own clean-white glyph atlas material.
"""

MATERIAL_GUIDS = {
    # name: (guid, vanilla .def under BlockMaterials/)
    "PaintedMetalColorable": ("be89c5c3-25ce-42e9-93f9-72ba32c3d8a7", "PaintedMetalColorable.def"),
    "PaintedMetalDarker": ("cb933a73-bce4-4224-a7d8-c5083935dac8", "PaintedMetalDarker.def"),
    "PaintedMetalYellow": ("d74fe97a-dbf1-4b0f-8e1b-90f6fa3b1b27", "PaintedMetalYellow.def"),
    "BrushedMetal": ("0c3be477-8bff-4e2c-8a0e-d7d842905ae9", "BrushedMetal.def"),
    "MetalDull": ("0e9e7d42-9533-47ed-b814-cf4be55b6aa8", "MetalDull.def"),
    "Chrome": ("3312f76c-b118-4616-bd95-adfb9b59a996", "Chrome.def"),
    "Rubber": ("ea603341-6e46-42f7-afae-ce60b8848ec5", "Rubber.def"),
    "EmissiveGreen": ("78f2cbaa-112e-4068-99e7-c146d4da58f2", "EmissiveGreen.def"),
    "EmissiveOff": ("d2648963-ef2b-442d-af7b-ee3d79dad677", "EmissiveOff.def"),
    "EmissiveRed": ("a68b9acc-bcaa-4023-9a26-10df67be55ca", "EmissiveRed.def"),
    "AtlasDecal_Stickers02": ("c3e749ff-35ff-469c-b7ae-84a5a5d829b3",
                              "Decals/Atlases/AtlasDecal_Stickers02/AtlasDecal_Stickers02.def"),
    # Task 7, UPS: the vanilla Battery50 slot frame's decal atlas (kit part), mapped as Battery50.model maps it
    "AtlasDecal_Parts02": ("8affab53-a343-4c9d-b513-2f82180c0326",
                           "Decals/Atlases/AtlasDecal_Parts02/AtlasDecal_Parts02.def"),
    "AtlasFont_BarlowCondensed": ("481b2a1f-b394-4d99-b58a-1c370e013315",
                                  "Decals/Fonts/BarlowCondensed/AtlasFont_BarlowCondensed.def"),
    "AtlasFont_BarlowCondensed_CleanWhite": ("d9b7cea3-19fa-4aee-843a-a6838dda5990",
                                             "Decals/Fonts/BarlowCondensed/AtlasFont_BarlowCondensed_CleanWhite.def"),
    # Task 6, functional servers (dc/functional.py): slots named as vanilla's mesh parts, mapped as vanilla maps them
    "Terminal": ("60363146-c219-42d4-ba67-eceb934647ce", "Terminal.def"),          # Timer50 / EventController screen
    "Emissive01": ("d2648963-ef2b-442d-af7b-ee3d79dad677", "EmissiveOff.def"),     # EventController100.model
    "Emissive02": ("d2648963-ef2b-442d-af7b-ee3d79dad677", "EmissiveOff.def"),     # EventController100.model
    # the LCD surface slot: vanilla's 2:1 screen material (LCDWide300/500, NarrowLCD50 map LCDScreen_Off to it)
    "LCDScreen_Off": ("bd7f946b-3867-4aaf-8aaf-2a8eed16e832", "LCDScreen_Off_2.0.def"),
    # Task 8, programmable shell: the static amber "scripting unavailable" lamp. Vanilla has no amber PBR emissive;
    # its only steady amber is this ColorIndicatorMaterial (115, 86, 0), Emissivity 20, AnimationParameters null (the
    # wind turbine's low-efficiency state). Used here as a model's own material assignment (vanilla swaps indicator
    # materials in at runtime instead): unverified in game, see the Task 8 report.
    "EmissiveAmber": ("4a74bc1c-0530-4c06-a5c5-5d91f11353f4",
                      "Indicators_Placeholder/WindTurbineIndicators/IndicatorWindTurbineEnabledLowEfficiency.def"),
    # Plan 4 Task 4: the Programmable's script-status slot (functional.PROG_LED: its status lamp and LCD status bar),
    # the same static amber as EmissiveAmber, but its own mesh part, so the scripts can swap it green while Working
    # without touching the rear PSU lamps (which keep EmissiveAmber).
    "EmissiveScriptStatus": ("4a74bc1c-0530-4c06-a5c5-5d91f11353f4",
                             "Indicators_Placeholder/WindTurbineIndicators/IndicatorWindTurbineEnabledLowEfficiency.def"),
    # Task 9 fix 1: the door handle's lock pictogram (Stickers01 white icon quadrant)
    "AtlasDecal_Stickers01": ("2a953884-e538-4bec-a334-1fef9d3712ce",
                              "Decals/Atlases/AtlasDecal_Stickers01/AtlasDecal_Stickers01.def"),
    # Task 9, rack door leaves: vanilla perforated steel (a construction-stage material; DefaultState f97448f5, the
    # alpha-tested two-sided state the hair / *_TwoSided materials use; its source has an _alphamask.png: ~44 % open)
    "MetalPerforationSteel": ("6b6c351e-f5cf-4bf0-bd9d-09b06e7bce7c",
                              "Constructions/MetalPerforationSteel/MetalPerforationSteel.def"),
    # Plan 2 Task 4, cable trays: the power bundles (moderate density) and the LOD2 basket card (alpha-tested grating,
    # vanilla's catwalk floor; the choice among the brief's candidates is in NOTES "Plan 2 Task 4")
    "PaintedMetalGrey": ("9db1117a-b2a1-4fa1-a536-19a35139c3fc", "PaintedMetalGrey.def"),
    "GratingMetallic": ("2cc33fe2-00c5-4a64-a648-d1ea7aa8e3ee", "GratingMetallic.def"),
    # Plan 3 (P3-13, P3-19): vanilla glazing, both PBRTransparentMaterialDefinition. The containment roof's panes
    # (DeckPanel250 has no glass of its own; vanilla user: Projector300) and the containment door leaves (vanilla
    # user: InteriorLight50). Fallback if either renders badly: MetalPerforationSteel.
    "FrostedGlass": ("c41f2732-51b4-4634-8fc4-b740f52a4ff5", "FrostedGlass.def"),
    "WindowGlassThin": ("646cbd24-5fd8-4b80-9c45-4e3ddee5a79d", "WindowGlassThin.def"),
    # Plan 3 Task 4, containment roof: the LED batten's diffuser. Vanilla's static white emissive (a PBR material,
    # EmissivityMultiplier 80), mapped as HangarDoor_Base.model maps its light strips (no swapper: always lit)
    "EmissiveWhite": ("8ffced10-c911-4a5a-921f-075ee31ca2cc", "EmissiveWhite.def"),
    # Plan 2 Task 9b, fracture models (dc/fracture.py): vanilla's break-face material (every Fracture_NN_Cut of
    # Timer50, Battery50, EventController100) and the broken states vanilla's Deformed models map their lamp and screen
    # slots to (DAMAGED_SLOTS; never a slot of ours by itself, only a Damaged .model's MaterialReference)
    "FracturedMaterial01": ("0f2772fd-72d6-4ee9-9211-38d1781ba8b9", "FracturedMaterial01.def"),
    "EmissiveOffBroken": ("bcefad69-a79d-498b-97c8-5f2c024cfc52", "EmissiveOffBroken.def"),
    "Display01Broken": ("0f138e31-e25c-415e-94a8-137b9c3f5f7f", "Display01Broken.def"),
    "LCDScreen_Off_Damaged": ("73b146d6-2a17-405c-ac00-dd7ddb4454d6", "LCDScreen_Off.def"),   # LCDFlat50_Deformed
    # Plan 3 (main merge): the broken glazing vanilla's Deformed models map their WindowGlass slot to (Piston500,
    # Reactor250): the containment roof's FrostedGlass panes in its Damaged .model (fracture.DAMAGED_SLOTS)
    "WindowGlassBroken": ("b9db8238-9373-4690-b743-17e37759179e", "WindowGlassBroken.def"),
    # Plan 5 Task 3 (G4): vanilla 4.0's scratched parallax Deformed materials (PBRParallaxMaterialDefinition), what
    # vanilla's Deformed models map the four metal slots to (tools/vanilla-ref, 269 Deformed models: Colorable
    # 249/264, Darker 239/251, BrushedMetal 87/97, Chrome 131/134; e.g. Timer50_Deformed). The Darker one is a Copy
    # .partialdef of the Colorable one (its own textures). Only a Damaged .model's MaterialReference (DAMAGED_SLOTS).
    "PaintedMetalColorableDeformed": ("d8847d2a-cbb3-4982-9036-ee7785cce3c1",
                                      "PaintedMetalColorable_Deformed/PaintedMetalColorableDeformed.def"),
    "PaintedMetalDarkerDeformed": ("ea15e749-58ce-4ca8-95e2-307af0bd273d",
                                   "PaintedMetalColorable_Deformed/PaintedMetalDarkerDeformed.partialdef"),
    "BrushedMetalDeformed": ("d2d76bf2-2c7c-4798-8eec-c515c07b84cc", "BrushedMetalDeformed/BrushedMetalDeformed.def"),
    "ChromeDeformed": ("4418666d-ba5b-481c-b9a3-e7233fc001a8", "Chrome_Deformed/ChromeDeformed.def"),
    # Plan 3 Task 8, signs (dc/signs.py, functional.SIGN_LCD): the 4:1 LCD surfaces (aisle sign; the hanging sign's
    # front and back) on vanilla's 4:1 off-screen material, as ControlSeat250 maps its 4:1 CustomDisplay04
    "LCDScreen_Off_4": ("fa0a1f34-75c1-4899-bc3c-761ec9f70877", "LCDScreen_Off_4.0.def"),
    "LCDScreen_Off_4_Back": ("fa0a1f34-75c1-4899-bc3c-761ec9f70877", "LCDScreen_Off_4.0.def"),
}

# Interim LastLOD material (no bake yet): the last-LOD box takes the block's paint, like the Colorable body that
# covers about half of every model's surface. Replace with a baked <name>_LastLOD .def later (guide section 11).
LASTLOD_FALLBACK = "PaintedMetalColorable"


def guid(slot):
    """GUID for a material slot used in an exported model; KeyError if it has none."""
    if slot.startswith("DC_") and slot.endswith("_LastLOD"):
        slot = LASTLOD_FALLBACK
    if slot.endswith("_Subpart"):     # a baked stand-in's slot (fracture.SUBPART_SUFFIX) wears its base slot's material
        slot = slot[:-len("_Subpart")]
    return MATERIAL_GUIDS[slot][0]
