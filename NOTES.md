# Data Center mod notes

Design: ../../docs/design/2026-10-17-data-center-design.md. Shared modelling library: ../../tools/se2model.
Build: `blender -b --python Source/Model/build_dc.py -- all --no-render` (writes Source/Model/build_report.json).
Tests: `python3 -m pytest -q Tests -m "not build"`.
`dc.catalog.bounds(spec)` gives inclusive cell bounds for `placement.analyse`.

Door subparts use a different prefix: `SlideDoorNarrow_250_` (e.g. `SlideDoorNarrow_250_LeftDoor`) in `Doors/SlideDoorNarrow/250/Subparts`. Cloning with `--from SlidingDoorNarrow250` does not rename those, so Tasks 5/9 must handle the subparts separately.

## Task 3: rack frame and slot mechanics (2026-10-17)

**Size ruling (controller, 2026-10-17), quoted:** "Rack width = 4 cells (1.0 m) for all racks: DC_Rack42_* (4,10,5) and DC_Rack24_* (4,5,5). The server stays 2 cells wide, centred, with rails at x = ±0.25. Each side gets a 0.25 m column for the posts and the integrated vertical cable manager." and "Servers become 3 cells deep (0.75 m): cells=(2,1,3), and the UPS (2,2,3). They sit centred in the 5-cell rack depth." Why: on the 0.25 m grid a 2-cell server cannot be centred in a 3-cell rack (an even block in an odd one always lands 0.125 m off-centre); the Task 3 probe showed the flush side could then mount at most 36 %. Deviations from the approved spec (0.75 m wide racks, 1.0 m deep servers) are the user's to confirm.

- Free slot cells: 8 x 2x1x3 = 48 (full), 24 (half); `rack.SLOT_CELLS` (game-frame inclusive cell indices).
- Placement uses the game's per-axis grid shift (`placement.analyse(..., shift="bounds")`: 0.125 m on even-sized axes, 0 on odd ones).
- Collision: physics = plinth + 2 side columns (+ top tray) boxes; occupancy hints fill the front/rear 0.25 m zones; mount hints on the sides, bottom, tray rim, the slot rails (x = +-0.25) and slot floor/ceiling. Front/back geometry stays >= 2.7 cm behind the planes.
- Fix round 1 (visual audit V1-V4): layered side panels (frame + inset panels + casing, seam over the manager channel, louvred vents, lifting recess, cable grommet, quarter-turn latches, grounding stud + Stickers02 electrical label), slide-rail kits instead of the rail wall, one stencilled number per slot, chunkier fingers (1/2-slot pitch) on a painted channel back. Adds AtlasDecal_Stickers02 (half rack LOD0 now 8/8 materials).
- Half rack: no tray; a 5 mm render-only roof inside the top slot cells (servers must leave >= 5 mm top clearance in the top slot of a half rack, or accept a visual overlap). Its label plate sits on the plinth.
- LODs follow Keen's size table: full rack LOD0-3 + LOD4 box; half rack (max dim 1.25 m) LOD0-2 + LOD3 box.
- Stencils for IDs use `AtlasFont_BarlowCondensed_CleanWhite` (white on Darker plates, readable on any paint); the status lamp slot is `EmissiveGreen`. Task 5 must map both names to their vanilla GUIDs.

Placement summaries (`placement.summary_line`):
```
Task 3 (before the placement fix): DC_Rack42_Open 152/200 occupied, 48 empty (groups U/D 3/2); DC_Rack24_Open 76/100, 24 empty (U 5, 70%).
DC_Rack42_Open: groups F/B/L/R/U/D = 0 / 0 / 2 / 2 / 3 / 2; plane coverage = 0% / 0% / 100% / 100% / 40% / 100%; occupied 136/200 box cells, 64 empty, 0 outside
DC_Rack24_Open: groups F/B/L/R/U/D = 0 / 0 / 2 / 2 / 4 / 1; plane coverage = 0% / 0% / 100% / 100% / 60% / 100%; occupied 68/100 box cells, 32 empty, 0 outside
```
(Re-recorded by the placement fix of 2026-10-18, below: the slots' front-zone row is free, the rear zone is the rear
stop. Tests/test_tray_rack_interface.py compares the build to these two lines.)

Design rationale (rack, part -> purpose): plinth = load frame + louvred cold-air intake + jacking pockets; corner caps = impact armour on knockable corners; posts = structure; 19" rails (Brushed, square holes, slot-number tabs) = server ear seats; slide rails = server support; rail wall pass-through slots = cables to the side channel; front finger combs = data cable manager (waterfall channel), rear combs = power; lacing bars = tie points; top tray = landing trough for overhead drops, Brushed lane dividers, brush grommets down into the front channels; header = rack ID + power-OK lamp; rear header louvre = hot-air exhaust; side ID plates = rack ID from the aisle.
Provenance: geometry generated (no vanilla meshes reused); stencil glyph boxes from se2model/decals.py; preview stand-ins ported from tools/mockups/datacenter/dclib2.py.

## Task 4: server chassis + deco blades (2026-10-17)

- `dc/server.py`: shared chassis for 6U (2x1x3) and 12U (2x2x3): body (Darker tub, Colorable skins, split top with service lid), server-side slides, rack ears, bezel frame + pull handles, rear panel (PSUs / exhaust / I/O, or a passive baffle for the blank), `face_frame(spec)`, `collision(spec)` (one box = the cells; mount hints bottom/top/left/right/back, none on the front), `last_lod`.
- `dc/servers/deco.py`: `build_compute/storage/switch/blank(spec, lod)`, v2 SE language (paint on bezels and caddies, shadow gaps, white stencils on Darker plates, fewer/larger lenses).
- Clearances (render only): body |x| <= 0.240, slides 0.2405..0.247 (rack slide bolts reach 0.2485), top <= h/2 - 0.006 (half-rack roof 5 mm), back >= -0.372. Proven per build in `build_report.json` `clearance` and `test_server_clearance`.
- Ears: L-brackets, flange x 0.240..0.288 on the 19" rail face (y 0.3755..0.3815), thumbscrews over the rail's square holes (x 0.262, slot centre +-0.094), notched at the slot centre so the rack's slot number stays readable. Ears reach outside the cell box (front zone, x up to 0.288): flush standalone neighbours clip ears by ~7.6 cm.
- New material slot: `EmissiveOff` (unlit lens, vanilla library). Deco LOD0/LOD1 are at the 8-material cap.
- Rationale (part -> purpose): caddies = hot-swap disks (vent, lever + release button, activity lamp); honeycomb = cooling intake; compute door = memory/fan access (latch, hinges); control module = power ring button, locator, health lamp, ID; switch ports + link lamps, SFP uplinks, console/mgmt, fan tray; blank label = slot size + locator; ears/thumbscrews = rack mounting; handles = pull-out; slides + yellow latch = rail support and release; lid + grip slot = service access; rear PSUs/exhaust/I-O = power in, hot air out, network.

## Task 5: definitions pipeline (2026-10-17)

How to regenerate, install, build and roll back: `Source/Model/integration/INTEGRATION.md`.

- **Clones:** all 16 catalogue blocks cloned (`dc/clone.py`; `se2mod.py copy --map-key <name>`, keyed
  `.clonemap.json`), each with its own BlockKind. Seven wall-panel clones and four door clones need per-block GUID
  maps: se2mod's flat map would hand every clone of one folder the same GUIDs. Door subparts (`SlideDoorNarrow_250_`)
  are renamed in the same copy with `--also` (cyclic references with the door's dummies). The wall-panel chain is
  already a decorative breakable block (no power/terminal/inventory), so its clones are only renamed.
- **Mount directions:** the wall-panel block definition limits mount points to `Backward, Left, Right, Up, Down`
  (kept). The servers' front therefore does NOT mount in game, which resolves Ruling 9's standalone-face concern; the
  offline generator still reports the raw Forward group.
- **Fractured:** (Task 5) racks got one fracture per physics box, no cut geometry, DamagedModel = the Fractured model;
  the servers were unfractured on the belief in an 8-mesh-part limit. **Superseded** by Plan 2 Task 9b (servers and
  trays cut, capped and dented) and Task 9c (racks cut and capped with their own Damaged model, 6U servers a critical
  core between two shells, every collider shaped to its zone's solid; docs/guides/vanilla-fracture-models.md).
- **LastLOD:** no bake yet; the `DC_<name>_LastLOD` slot maps to PaintedMetalColorable (takes the block paint).
- **LOD count from the measured mesh:** Keen's checker keys the LOD count on the LOD0 bounding-box surface. The full
  rack measures 13.42 m2 (cell box 13.75), just under the 25/74 row threshold, so it now has LOD0-2 + a LOD3 box (the
  112-tri LOD3 silhouette is gone); `assemble.fit_lods` measures and rebuilds. Budgets: 15532/15974, 3284/3655,
  992/1261, 12/32.
- **Material GUIDs:** `dc/material_guids.py` (checked against the SDK BlockMaterials defs by the tests).
  `AtlasFont_BarlowCondensed_CleanWhite` is vanilla's own material `d9b7cea3…`.
- **Build:** `se2mod.py build DataCenter` exits 0 with no DataCenter warnings: 12 `.model` -> `.vrm` (P_MODEL,
  `Problems: []`), 168 partialdefs, 146 defs.

## Task 6: functional servers (timer, event controller, status display) (2026-10-17)

- **Behaviour = vanilla.** The clones of Timer50 / EventController / LCDFlat50 keep their server and client
  compositions and components; only the model, the interaction dummy position, the indicator's ReplacementModels,
  the LCD surface aspect and the mount directions (no Forward, as the deco servers) are patched (`dc/integration.py`).
- **Indicator lamps by slot name** (`dc/functional.py`): the servers are unfractured, so every mesh part is named
  after its material slot. Timer lamps use the slot `EmissiveOff` (Timer50's IndicatorMeshParts): COUNT, the power
  ring, the 3 sled lamps, both rear PSU lamps. Event controller: row T lamps + PSU A = `Emissive01` (lit on True),
  row F + PSU B = `Emissive02` (lit on False). Both slots map to EmissiveOff by default, as vanilla. The vanilla
  per-fracture entries in IndicatorMeshParts are kept (unused by our unfractured models).
- **Indicator ReplacementModels** must list our models: the clone still listed the vanilla block's models, so without
  the patch the states would never show on our blocks.
- **Screens:** the timer strip is the vanilla `Terminal` material (lit UI art), UV-mapped to its "SERVER TERMINAL"
  panel. The status screen is the LCD surface `LCDScreen_Off` (2:1; slot -> vanilla `LCDScreen_Off_2.0`; surface
  1024 x 512, AspectRatio 2 as LCDWide300/500); its `LcdPanel` dummy covers the screen. Screens sit in the Fractured
  model's hidden (construction) object, as vanilla LCDs.
- **Material cap:** every functional LOD0/LOD1 is at 8/8. Timer has no EmissiveGreen (any lamp would read as a
  state); the event controller has no Terminal screen (ID plate with stencils instead); the status display has no
  EmissiveOff (unlit lamps are Darker lenses).

## Task 7: UPS (12U, two open Power Cell bays) (2026-10-17)

- **Capacity lives on the cells (Ruling 3, verified).** Decompiled `ResourceContainerInventoryComponent`
  (tools/decompiled/Game2.Simulation/...ResourceDistribution.Resources/): the block's `MaxCapacity` only seeds the
  resource entity (`ResourceContainerComponent`: `MaxCapacity = _definition.MaxCapacity`); on add-to-scene and on every
  slot-inventory change `RecalculateCapacity` overwrites it with sum(cell `MaxStored` x Amount) over the slot
  inventories (`ResourceContainerItemsConfiguration`: Power Cell -> `PowerCellResourceContainerItemDefinition`,
  MaxStored 180000). The charge / discharge RATES are read from the block definition. Battery50's block value 180000 =
  one cell. So the UPS block is kept consistent: `MaxCapacity` 360000 (2 cells) and rates doubled (399.8 / 400);
  two cells hold exactly 2 x Battery50's charge whatever the block value says.
- **Two slots = two InventoryComponents** (vanilla Battery250 pattern: one InventoryComponent per slot, all of the
  `InventorySlotsServerDefinition.SlotDefinition`, each tagged "CellSlot N"; `InventorySlotsServerComponent` orders them
  by the tag's trailing number). The UPS's server composition gets a second InventoryComponent (the cloned Battery50
  InventoryDefinition) tagged "CellSlot 1", and its server prefab pre-fills slot 1 like slot 0 (one cell, FillRatio
  0.3). **MaxMass stays 25 kg per slot** (50 kg in all): MaxMass is per InventoryComponent and MaxStacks = 1, so 50
  per slot would accept a stack of 2 cells per slot (4 cells). Whitelist: Power Cell only (unchanged from Battery50).
- **Dummies:** "CellSlot 0/1" (type CellSlot 0dd8466e: where InventorySlotRender draws the cell) and "CellAction 0/1"
  (type UseBatterySlotCells a7594bb4: aim + use; `UseResourceContainerSlotAction` reads the slot index from the name's
  trailing " N"), placed relative to each bay's frame mouth exactly as Battery50 places its pair (cell face 22.6 mm
  out, use box 4.6 mm in, scales 0.3x0.3x0.05 / 0.4x0.4x0.05); the rear pair turned 180 deg about Y.
  `SupportingFracture` None (unfractured model). The unnamed ConstructionStagesParticles dummy moves to the centre.
- **Layout:** two vanilla cells (0.30 x 0.31 face, 0.355 deep) do not fit side by side or stacked in a 0.5 x 0.5 m
  face, so CELL 1 opens on the front and CELL 2 on the back, back to back along the 0.75 m depth (front mouth y 0.385,
  rear mouth y -0.352; the core tub is hollow round both bays, `server._tub_with_bays`). Front and back are working
  faces: mount directions `Left, Right, Up, Down`, no back mount hint.
- **Kit part provenance:** the Battery50 slot frame, `tools/vanilla-ref/Blocks/Batteries/Battery/50/Models/NonFractured/`
  `Battery50.fbx` / `_LOD1.fbx` / `_LOD2.fbx`, object `UpgradePort_SpeedModule*` (367 / 181 / 28 tris), imported
  read-only, used unchanged except its EmissiveOff slot -> PaintedMetalDarker (material cap). `dc/servers/cellbay.py`.
- **Materials (LOD0/1 8/8):** Colorable, Darker, Yellow, Brushed, MetalDull, CleanWhite stencils, AtlasDecal_Parts02
  (the frame's decals, vanilla 8affab53 as in Battery50.model), EmissiveGreen. The LED ladders / LCD are a static
  ON-LINE picture (no component drives them).
- **Unfractured** (ControlPanel25 pattern, as the 6U servers): the 12U model is still one physics box, the builder
  rejects one fracture, and 2 zones x 8 materials exceed the 8 mesh-part limit.

## Task 8: KVM console and programmable shell (2026-10-17)

- **KVM = ControlPanel25 clone** (terminal access kept; the "Terminal" use dummy covers the face). Two animated
  subparts, separate models without collision (`dc/subparts.py` numbers + definitions, `dc/servers/kvm.py` models):
  `KvmDrawer` (dummy "KvmDrawer" = the stowed hinge, TranslationAnimation (0, 0, -0.45) game = 0.45 m forward,
  0.45 m/s) and `KvmScreen` (a child entity nested in the drawer prefab at the drawer model's "KvmScreen" dummy, the
  hinge; RotationAnimation axis game +X, 100 deg at 100 deg/s). Screen lid 0.30 m (v2: 0.17 m); popped out it covers
  0.13 m of the slot above, its rearmost point above the slot at y 0.435 (neighbour hardware ends at 0.4145).
- **Trigger: FunctionalBlockAnimationControllerComponent (Working), not the door.** The door mechanism could drive
  these leaves data-only in principle (DoorSegmentTransformSLERP reads Closed/Open dummies from the closest parent
  model, so a nested screen leaf could read the drawer model's dummies; the door state is saved and replicated), but it
  means grafting the whole SlidingDoorNarrow250 server+client set (DoorServer/DoorClient, PowerableBlock, door-parts
  provider with server-side leaf entities, DoorBlockCollider, the doorway obstacle detector, DoorAudio, UseToggleDoor
  on the leaves) onto the ControlPanel25 clone, with two use actions on one block and nested door segments that
  vanilla never uses. Kept as the Plan 4 upgrade (prototype in game first).
- **Working on a ControlPanel25 = built, not broken, and the GRID switched on** (FunctionalBlockComponent
  .RecomputeWorking = Functional && Grid.GridIsTurnedOn; ControlPanel25 has no power or on/off of its own). So the
  console would be OUT whenever the grid is on. **Fixed (Ruling 15, fix round 1):** the KVM now carries vanilla's
  On/Off: its FunctionalBlockComponent (key 91e12dcf) is swapped for PowerableBlockComponent (key 4f2bc5f9, as
  Templates/BasePowerableBlockBreakable_*, Timer50's chain), its block definition is a PowerableBlockDefinition with
  ConsumedResource null (no power sink, always Supplied; vanilla ContractBlock250 / Battery250 pattern), prefab
  object builders PowerableBlockObjectBuilder Enabled = true (vanilla default: built ON). Working = Functional && grid
  on && Enabled: On = popped out, Off = stowed. Terminal stays usable when Off (UseTerminalAction has no Working gate).
- **Simultaneous slide and fold; equal durations (1 s each).** The close retraces the open exactly. Mid-motion the lid
  passes up through the KVM's own upper panel (max 0.1325 m above the bay roof at f = 0.475, i.e. 5 mm above the
  panel top, still inside this server's 6U band: `subparts.transient_intrusion()`); never through the neighbour.
  Unequal times would leave the lid standing while the drawer slides back in (or flip it up inside the bay).
- **Load bug (vanilla-animations.md Q1):** Translation/RotationAnimation do not toggle on spawn and ConditionalSubParts
  respawns subparts on every Functional change, so after a world load, a repair or streaming in a Working KVM shows
  STOWED until Working next changes (grid off/on). RotationAnimation's reverse-while-returning overshoot (Q4) applies
  to fast grid on/off flicker.
- **Not Functional (under construction, broken): no subparts**, so the bay shows empty (no static copies: the models
  are unfractured and part names = material slots, so MeshPartsToHideWhenActive cannot single out a copy).
- **Programmable = WallInsertPanel clone, inert blade shell**: 6 sleds (sled 4 pulled 20 mm, lever open 35 deg),
  ejector levers, management module (unlit mono LCD "SCRIPTS OFFLINE" over an amber fault bar, 5-way pad, SCRIPT N/A
  lamp, PRG-06). Status lamp slot `EmissiveAmber` -> vanilla `IndicatorWindTurbineEnabledLowEfficiency` (4a74bc1c,
  ColorIndicatorMaterial (115, 86, 0), Emissivity 20, no AnimationParameters): vanilla's only static amber emissive.
  Used as a model's own material (vanilla only swaps indicator materials in at runtime); the build accepts it
  (P_MODEL, Problems []), the in-game look is unverified.
- No script-only types: `test_no_script_types_in_definitions` checks every $Type/Type/UseActionType of every staged
  and installed DataCenter definition and .model is Game2:/VRage:.

## Task 9: rack doors (split front; front + rear), tray fans, hum (2026-10-17)

- **Hinged leaves, data-only (the sliding fallback was NOT needed).** Decompiled 2.4.0.95:
  `DoorSegmentTransformSLERPComponent.Init` reads the `ClosedPositionDummy` / `OpenPositionDummy` transforms from the
  closest parent ModelComponent (= the BLOCK model) and sets `RelativeTransform = RelativeTransform.Slerp(Closed, Open,
  OpenRatio)`; `RelativeTransform.Slerp` = `Vector3.Lerp(position)` + `Quaternion.Slerp(orientation)`
  (VRage.Core RelativeTransform.cs:749-755). Each leaf model's origin is ON its hinge axis and both of its dummies
  sit on that axis, so the lerp is constant and the slerp swings the leaf about the axis. Open dummy = closed yaw
  +-85 deg about game +Y (all quaternion pairs have a positive dot: the slerp takes the 85 deg way). Unverified in
  game: the swing direction (front leaves open toward the aisle) and the vanilla DoorSliding sound on a swing door.
- **Layout re-derived for this rack** (`dc/dims.py` DOOR_*, `dc/doors.py`): the frame already stops 2.7 cm behind its
  front / back planes (the keep-out: no mount points on the openings) and the posts' faces sit on |y| = 0.598, so the
  leaves live in the 2.3 cm layer |y| 0.600..0.623, in front of the posts, corner caps and every server's hardware
  (<= 0.435). No post setback (v2's 40 mm fixed a rack whose posts reached the front plane). Hinge axis 26 mm in from
  the side plane (x +-0.474, y +-0.6115), knuckle barrels r 11 mm (flush with both leaf faces), leaf from 13 mm off
  the axis to 1.5 mm short of the centre line: 0.4595 m of leaf, 0.4725 m axis-to-edge (half the opening). Flush
  racks keep 30 mm between neighbouring knuckles at 85 deg (any angle up to 91.75 deg clears); handles are recessed.
- **Leaves = subparts** (own models, own budgets; no collision, like every Task 8 subpart): `DoorLeafL` / `DoorLeafR`
  (rear leaves reuse them turned 180 deg). Colorable frame + mid rail, vanilla **MetalPerforationSteel** insert (its
  source has an `_alphamask.png`, DefaultState f97448f5 = the state of the hair and *_TwoSided materials; ~44 % open,
  ~17 mm pitch at 3 m per UV), three-knuckle hinges, Darker hinge plates with bolts, Darker seal strip on the meeting
  edge; on the active leaf (DoorLeafL) one recessed swing-handle latch (Darker escutcheon, Brushed fold-flat
  L-handle, key cylinder, lock pictogram) with an 8 mm chevron border **only around the handle** (fix round 1).
- **Frame changes** (`dc/rack.py`): door variants get Darker hinge brackets on the post faces (to |y| 0.5995, inside
  the keep-out) and an `EmissiveOff` power lamp that the cloned material swapper lights (EmissiveGreen) while Working;
  every full rack (open too) gets the tray fan lane: two round openings through the tray floor in the rear lane with
  the static RackFanTray subpart on top (housings, shroud lips, finger guards, leads, lamps; fix round 1) and the
  cable lanes' framed perforated tray floors.
- **Definitions** (`integration.stage_rack_subparts`): leaf model components -> our models + a `DoorUse` box; rear
  leaves = copies of the front leaf set (7 files each) under new GUIDs and new dummy types; ConditionalSubParts maps
  every leaf's closed dummy type -> its client prefab (+ the fan); block dummies rebuilt (effects at the centre, the
  leaf Closed/Open pairs, the doorway detector over the door plane (whole depth for front + rear; the block's own grid
  is ignored, so servers never block it), fan pivots; the vanilla frame UseDoor boxes TerminalFront01/Back01 dropped:
  open they would sit in front of the servers' terminals); CriticalFractures = the two side columns (they carry the
  hinges); OpeningDuration 1 s; swapper on our models.
- **Fans:** `RackFan` rotor subpart (InfiniteRotation about game +Y, 720 deg/s, speed-up 360, slow-down 180 deg/s2).
  Door racks: spawned by the door's ConditionalSubParts, toggled with Working by a
  FunctionalBlockAnimationController added to the client composition. **Open rack (decor, a CubeBlockComponent, no
  FunctionalBlockComponent, so no ConditionalSubParts): always-on spin IS feasible data-only** and is implemented: the
  rotors are static children of the client prefab (Piston500 pattern: client-only children in HierarchyComponent) and,
  with no IRigidAnimationControllerComponent on the block, `ToggleRigidAnimationComponent.OnAddedToScene` turns them
  on (`IsAnimationOn ?? true`). They spin always, also while the rack is still being built. Unverified in game.
- **Hum (OnUseAudio, a vanilla loop while Working):** door racks `event:/SFX/Block/GyroscopeSM` (the fan whir), KVM
  `event:/SFX/Block/LCD` (ControlPanel25 had none). The other functional servers keep their templates' loop (Timer50 /
  Battery50 `BatteriesInsertRemove`, EventController `UI/OreDetector`, LCD50 `Block/LCD`). Loudness unverified.
- Not changed: DoorBlockCollider (our leaves have no collider, so a closed door is a closed-door LOOK; players are kept
  out of the 0.25 m door zone only by the servers' faces), DoorAudio (vanilla sliding-door sound), the door's
  "Permeability false" and PCU 150.
- **Fix round 1 (visual audit V1–V3):**
  - **Fan tray** = a STATIC subpart `RackFanTray`: a two-panel Colorable tray plate with a seam, screws and an air
    opening per fan; per fan a square Darker housing with a MetalDull shroud lip and a finger guard (3 rings,
    4 spokes, a centre disc carrying the motor and an "F1"/"F2" stencil), a status lamp, a CAUTION MOVING PARTS label
    and a power lead to a latching connector. The rotors (`RackFan`, InfiniteRotation) now turn inside the housings.
    Door racks spawn the tray via ConditionalSubParts (so it is absent while the rack is not Functional); the open
    rack carries it as a third static client-prefab child.
  - The cable lanes' loose straps became framed perforated tray floors in the rack model (Brushed frame, a 3 mm
    seam, the doors' MetalPerforationSteel).
  - **Handle:** one recessed swing-handle latch on the active leaf (`DoorLeafL`): a Darker clipped escutcheon with
    a bezel and pocket, a Brushed fold-flat L-handle on a pivot boss, a key cylinder, a Stickers01 lock pictogram,
    and an 8 mm chevron border round the escutcheon only. The passive leaf has its seal only.
- **KVM behind closed doors (in-game checklist):** a Working KVM pops its drawer and screen out THROUGH closed
  front doors. Nothing data-only couples the KVM to the rack's door state. Switch the KVM Off (its On/Off, Ruling 15)
  or open the doors first; the previews show it stowed behind closed doors. Also check in game: the leaves have no
  collider (visual only), the swing direction, the perforation's transparency, the fan spin and the hum mix.
- **"Powered" is loose wording (cleanup round, review #9):** the door racks' PowerableBlockDefinition consumes
  `Amount 0`, so Working is about Functional + grid on + Enabled; an actual power supply is probably NOT needed
  (vanilla doors behave the same). A rack whose UPS is flat should still open, spin its fans and hum.
  **In-game checklist:** fans, hum and the doors' toggle on a grid with NO power source.


## Task 10: build menu, icons, previews, costs (2026-10-18)

### Build-menu grouping (`dc/menu.py`; evidence from the decompiled 2.4.0.95 G-screen code)
- **The tree:** Category > Subcategory > BlockGroup (one tile) > BlockKind (a tile inside the group) > the kind's blocks (the size selector).
- **BlockKind** (`BlockKindDefinition`: "blocks of the same type but different sizes"):
  - a block joins a kind through its own `BlockKind`;
  - `BlockKindDefinitionPostProcessor` orders the kind's blocks by `DisplaySize` (the largest cell extent × 0.25 m) and assigns BlockSize1..4;
  - vanilla Battery50, 150 and 250 share the one PowerBattery kind.
- **BlockGroup:**
  - kinds list their groups in `BlockGroups`;
  - `BlockGroupDefinitionPostProcessor` inserts the kinds by `OrderingPriority` (0 = last), then name, then GUID;
  - `SubcategoryDefinitionPostProcessor` puts multi-kind groups first.
- **Vanilla family tiles are multi-kind groups:** Decor/LCDs "LCD" (4 kinds), Automation/Inputs "ButtonsAll", and the armour "BasicShapes" groups.
- **Ours:**
  - one subcategory, **Data Center**, in the vanilla Automation category (`300a06f0`);
  - one group per family: **Server Racks** and **Rack Servers**;
  - three rack kinds (Open Frame, Split Front Doors, Front + Rear Doors), each holding its 24U (size 1) and 42U (size 2) block. The 24U block definitions point at the 42U clone's kind;
  - one kind per server type (every server has DisplaySize 0.75, so they cannot be sizes of one kind);
  - menu order through OrderingPriority 1..n;
  - unlike vanilla LCDs, we add no extra single-kind groups, so there is one entry per family.
- **The 24U racks' own cloned kinds:**
  - their `BlockGroups` are emptied and they are left out of the unlock;
  - they hold no blocks, so the group insertion skips them (`Blocks.Length > 0`).
- **Files:** `DataCenter/UI/DataCenter_SubcategoryDefinition.def`, `DataCenter_Racks_BlockGroupDefinition.def`, `DataCenter_Servers_BlockGroupDefinition.def` (vanilla formats). The tile names are plain text, as the kind names already were.

### Costs (Ruling 10, `dc/recipes.py`)
The ledger's premise ("Rack42 costs one wall panel") was half right. SE2 does scale a recipe by block size, but by whole multiples of the recipe.
- **The game's formula** (decompiled `CubeBlockDefinition.ComputeMassAndHP` and `ComputeRecipeAmounts`, called by `GeneratedBlockDataLoader`):
  - `mass = Density.MassCurveModifier × sqrt(n) × log10(n) + 5`, where n = occupied cells;
  - `scale = RoundToIntStrictlyPositive(mass / recipe mass)`;
  - `cost = recipe × scale`.
- **Why the clones were wrong:** vanilla mixes are heavy. The wall panel mix weighs 260 kg against the panel's 108 kg, so the scale is 1 and a clone keeping its source mix paid exactly the source block's cost at any size. Rack42 Open (301 kg) paid one wall panel.
- **Our rule:** cost = the source block's in-game cost × (our mass ÷ the source's mass).
  - Both masses come from the game's formula, so the ratio follows the occupied volume through the game's own density curve.
  - Each item is rounded half up, with a minimum of 1.
  - The recipe carries those final amounts. The tests prove the game's scale stays 1.
- **Door racks:** the open frame of the same height plus the vanilla sliding door's mechanism (2 Motor + 1 Electronic Parts) per door side. Their `Density` changes from Mostly Solid (door) to **Mostly Hollow** (the frame), so their mass and HP match the open frame instead of being 1.8× heavier.
- **Source cell boxes** (measured on the vanilla LOD0 FBX on the 0.25 m grid):
  - WallInsertPanel 6×6×1;
  - Timer50 2×2×2;
  - EventController 4×2×2;
  - ControlPanel25 1×1×1;
  - Battery50 2×2×2;
  - LCDFlat50 2×2×1.
- **Recipe files:**
  - the block's own cloned recipe file is patched where the clone has one (GUID kept; the Timer and Event Controller clones had an unreferenced one);
  - otherwise a new `<name>_RecipeDefinition.def` is written (door racks, UPS, Status);
  - the block definition's `Recipe` points at it. BuildTimePerItem stays the source's value.

| Block | Source (cost from) | Cells ours / source | Mass ours / source (kg) | Ratio | Critical | Optional |
|---|---|---|---|---|---|---|
| DC_Rack42_Open | WallInsertPanel | 152 / 36 | 300.9 / 107.7 | 2.79 | 11 SteelPlate, 8 Construction | 8 SteelPlate |
| DC_Rack42_SplitFront | SlidingDoorNarrow250 (frame: WallInsertPanel) | 152 / 36 | 300.9 / 107.7 | 2.79 | 11 SteelPlate, 8 Construction, 2 Motor, 1 ElectronicParts | 8 SteelPlate |
| DC_Rack42_SplitFrontRear | SlidingDoorNarrow250 (frame: WallInsertPanel) | 152 / 36 | 300.9 / 107.7 | 2.79 | 11 SteelPlate, 8 Construction, 4 Motor, 2 ElectronicParts | 8 SteelPlate |
| DC_Rack24_Open | WallInsertPanel | 76 / 36 | 185.4 / 107.7 | 1.72 | 7 SteelPlate, 5 Construction | 5 SteelPlate |
| DC_Rack24_SplitFront | SlidingDoorNarrow250 (frame: WallInsertPanel) | 76 / 36 | 185.4 / 107.7 | 1.72 | 7 SteelPlate, 5 Construction, 2 Motor, 1 ElectronicParts | 5 SteelPlate |
| DC_Rack24_SplitFrontRear | SlidingDoorNarrow250 (frame: WallInsertPanel) | 76 / 36 | 185.4 / 107.7 | 1.72 | 7 SteelPlate, 5 Construction, 4 Motor, 2 ElectronicParts | 5 SteelPlate |
| DC_Srv_Timer | Timer50 | 6 / 8 | 43.1 / 56.1 | 0.77 | 1 Construction, 1 Motherboard, 4 HardDrive | 2 Construction |
| DC_Srv_EventCtl | EventController | 6 / 16 | 43.1 / 101.3 | 0.43 | 2 Construction, 1 ElectronicParts | 1 SteelPlate |
| DC_Srv_KVM | ControlPanel25 | 6 / 1 | 18.3 / 5.0 | 3.67 | 4 Construction | - |
| DC_Srv_UPS | Battery50 | 12 / 8 | 79.8 / 56.1 | 1.42 | 9 Construction, 1 ElectronicParts | 4 Construction |
| DC_Srv_Status | LCDFlat50 | 6 / 4 | 26.0 / 18.2 | 1.42 | 4 ElectronicParts, 3 Wire, 3 Glass | 4 SteelPlate |
| DC_Srv_Programmable | WallInsertPanel | 6 / 36 | 26.0 / 107.7 | 0.24 | 1 SteelPlate, 1 Construction | 1 SteelPlate |
| DC_Srv_Compute | WallInsertPanel | 6 / 36 | 26.0 / 107.7 | 0.24 | 1 SteelPlate, 1 Construction | 1 SteelPlate |
| DC_Srv_Storage | WallInsertPanel | 6 / 36 | 26.0 / 107.7 | 0.24 | 1 SteelPlate, 1 Construction | 1 SteelPlate |
| DC_Srv_Switch | WallInsertPanel | 6 / 36 | 26.0 / 107.7 | 0.24 | 1 SteelPlate, 1 Construction | 1 SteelPlate |
| DC_Srv_Blank | WallInsertPanel | 6 / 36 | 26.0 / 107.7 | 0.24 | 1 SteelPlate, 1 Construction | 1 SteelPlate |

The game multiplies each recipe by 1 (`test_costs_scale_with_volume_and_game_scale_is_one`). The 6U decorative servers cost 1 + 1 + 1 because the minimum is one of each item.

### Icons (`dc/preview_task10.py`, `Source/Model/UI/<name>_Icon.png`)
- **Format:** 200 × 200, 8-bit RGBA, transparent, no ICC profile (tested with a stdlib PNG reader).
- **Match to vanilla:**
  - a 3/4 view from front-left-above (the face on the left), a 70 mm lens, ~28° elevation for racks;
  - servers more frontal (~15°), so the face is large;
  - the default (Keen grey) paint, emissives lit;
  - studio light: key upper-left, low fill, a small top light, a cool rim; AgX Medium High Contrast at −0.55 EV for vanilla's mid-grey metal and dark recesses;
  - each block fitted to its own bounds: 42U 86 %, 24U 70 % (so it reads smaller, like Battery50 vs Battery250), 6U servers 80 %, UPS 84 %.
- **Telling variants apart:**
  - Open: no doors, so the empty slots show through;
  - Split Front: closed perforated doors;
  - Front + Rear: front doors swung open and the closed rear door seen through the empty slots;
  - KVM: popped out;
  - UPS: its cells shown.
- **Contact sheet** against 8 vanilla icons, on dark and light backgrounds and at 64 px: `preview/task-10/icons_contact_sheet.png` (`python3 Source/Model/icon_sheet.py`, Pillow).

### Previews
- `preview/blocks/<name>.png`: one store-style shot per block.
- `preview/hero/`:
  - `hero_aisle` and `hero_aisle_wide`: a cold aisle with 4 full and 2 half racks; doors open and closed, a popped KVM, UPS units;
  - `hero_server_lineup`;
  - `hero_door_variants_3_paints`;
  - `hero_layout_top`;
  - `hero_detail`.
- **The `Mood` rig:**
  - dark 0.5 m raised-floor tiles, and perforated cold-aisle tiles over a blue plenum glow;
  - visible ceiling light strips with rectangular area lights, dark walls and a low front fill;
  - black racks with default-grey servers.
- **Render:** `DC_PREVIEW=task10 blender -b --python Source/Model/build_dc.py -- all` (`DC_T10_PART=icons|blocks|hero`).

### In-game checklist
`INGAME-CHECKLIST.md`. The probe is `Source/Model/review/probe_mountpoints.csx` (it also prints the menu sizes, mass and the in-game cost).

## Visual pass 1 (2026-10-18)

Audit, changes and before/after: `docs/superpowers/sdd/data-center-core/visual-pass-1-{audit,report}.md`; renders
`DC_PREVIEW=vp1 DC_VP1_SET=before|after` (`dc/preview_vp1.py`), sheets `python3 Source/Model/vp1_sheet.py audit|compare`
(audit sheets embed the private reference photos and stay in the workspace docs, never in this repo).

- **Server chassis LOD0** (`server._body_lod0`, `_sides0`): framed lid over a recessed field (stamped beads, flush
  latch with Brushed T-handle + Yellow tab, Darker type plate with the per-type ID `server.TYPE_ID`), rear cover with
  beads and a PSU exhaust slot field, layered side skins (frame ring, recessed panel, front intake slots, swage,
  rating plate, rivets). The LOD0 tub shrinks to |x| 0.226 and drops 12 mm under the lid (hidden).
- **Distinct faces:** Compute = drive row over a three-fan wall (`deco.fan_module`); Switch = patch cables in ~60 % of
  its ports into a clipped bundle (`deco.patch_cables`, <= 4.5 cm past the slot front). Rears vary: Compute 2 round
  exhaust fans, Switch / Event Controller 12 uplinks, Storage 2 SAS connectors (`server.REAR_FANS`, `REAR_IO`).
- **Half-rack roof** (`rack._roof`): 5 mm slot roof (border, field, rear exhaust slots, big A1 + barcode) between
  28 mm roof rails over the side columns (brush cable entries, recessed lifting eye, bolts) and front / rear headers
  at |y| >= 0.45 (`ROOF_HEADER_Y`). `build_report` `geometry.top_slot_intrusion` proves <= 5 mm into the top slot.
- **All racks:** four Brushed levelling feet under the corner caps (base frame 4 mm off the floor, caps start at
  14 mm on LOD0/1); Stickers02 service / maintenance / barcode decals on the side panels; slide bolts 8 -> 6 sides.
- **Bevel gotcha:** se2model bevels use clamp-overlap, which clamps the WHOLE part: one zero-length edge
  (`oct_pts(..., 0.0)`) or sub-2 mm slab in a bevelled Part (frame / dark / ear) silently kills every bevel of that
  part. Thin plates go into `fine` (unbevelled).
- **Fan tray always present (coordinator item):** door racks now carry the static `RackFanTray` as a client-prefab
  child (`integration.patch_door_rack_tray`, HierarchyComponent at key index 1 as on the open rack); only the
  rotors stay ConditionalSubParts. The tray's spawn dummy is gone from the door racks. `test_fan_tray_always_present`.

## Visual pass 2 (2026-10-18)

Report: `docs/superpowers/sdd/data-center-core/visual-pass-1-report.md` ("Pass 2"); pairs `preview/visual-pass-2/after/pairs/`.

- **Side panels = static subpart `RackSide`** (`dc/rack_side.py`, built for +x in the centred block frame), placed
  twice per rack as client-prefab children (`integration.static_children`, `SIDE_CHILDREN`: `RackSideR` yaw 0,
  `RackSideL` yaw 180 about game +Y; `_child_transform(pos, yaw)`). The frame model no longer has `_sides`. Own LOD
  budget (42U ~13k LOD0 cap): PDU hatch, row placard, coolant conduit + flow meter, framed vents, service band.
- **Rear power manager:** zero-U PDU strip + tied cord bundle per rear channel (`rack._rear_pdu`). *Superseded by Plan 3 Task 1: the rear column is now the free PDU column; the strip is the separate Plan 3 Task 7 block.*
- **UPS rear** charge ladder; **Storage** controller column + 3x3 drive wall (ID ST-09); **KVM drawer underside**.
- **Bevel guard:** `build_dc._install_bevel_guard` records zero-length edges in bevelled Parts
  (`build_report` `bevel_guard`; `test_no_bevel_hazards`).
- Audit renders: `DC_VP_DIR=visual-pass-2` selects the pass folder for `dc/preview_vp1.py` and `vp1_sheet.py`.

## Plan 2 Task 1: rack <-> tray interface and top-entry brush plates (2026-10-18)

Report: `docs/superpowers/sdd/data-center-cable-trays/task-1-report.md`; previews `preview/p2-task-1/{before,after}/`,
pairs `preview/p2-task-1/pairs/`, sheet `contact_after.jpg` (`dc/preview_p2t1.py`, `p2t1_sheet.py`).

- **Interface in `dc/dims.py`** (rack-local, centred, +Y front): `RACK_TRAY_IX/IY` 0.44/0.46, `MANAGER_CH_X`
  (0.297, 0.42), `MANAGER_SPINE_Y` (0.393, 0.405) moved from `rack.py` (no geometry change); `TRAY_RACK_Y` 0.125,
  `TRAY_HANG` 0.5, `FLOOR_Z` 0.045, `WF_X` 0.3585, `WF_Y` 0.4325, `R_WF` 0.0225, `ROD_S` 0.232,
  `TOP_ENTRY` ((0.297, 0.42), (0.405, 0.46)); plate constants `ENTRY_FLANGE` 8 mm, `ENTRY_DROP` 1 mm,
  `ENTRY_EDGE` 4 mm; `HALF_TOP_ENTRY` ((0.313, 0.416), (0.405, 0.466)).
- **Top-entry brush plate** (`rack._entry_fitting` / `_brush_lips`), purpose = the cable gland where the overhead
  tray's waterfall drops into a front (data) cable manager, keeping dust and air out (reference photo 4):
  - Darker frame plate 1 mm under the top plane, 8 mm round the opening (on the full rack its front flange tucks
    under the rim strip, which clamps it);
  - Yellow edge = the frame's inner 4 mm, 0.3 mm lower: the safety edge the cables slide over;
  - two Darker bristle lips rooted under the long edges, drooping 3.5 mm to meet along the slot (y = opening
    centre = WF_Y on the full rack); LOD0 combs them into 4 mm tufts with 0.8 mm gaps and ragged tips so they read
    as brush strips; LOD1 = one flat tuft per lip; LOD2 = a dark patch (full rack);
  - a Darker sleeve under the frame: on the full rack it ducts the drop through the trough (which carries the fans'
    hot exhaust) down to the existing floor brush grommet over the manager, so hot air never reaches the cold-side
    manager; on the half rack it lines the roof-rail hole.
- **Full rack:** two plates over the front managers (`TOP_ENTRY`), front corners of the trough. The rear (fan)
  lane is untouched (fan tray subpart y -0.452..-0.158).
- **Half rack:** the 4 roof-rail entries (front data + rear power) get the same plate. The rail holes are now the
  plate outline + 0.5 mm; the opening's inner edge moved 4 mm out (0.309 -> 0.313) so 4.5 mm of rail remains toward
  the slot roof. The pocket floor is gone (the entry opens into the channel), and the manager channel back + finger
  roots now stop 1 mm under the rail (they used to reach the top plane and poked up into the old hole).
  LOD1 of the rail now carries the holes and plates too (it was a plain slab).
- **Measured:** `build_report` `geometry.top_entries` = the FRONT entries [x0, x1, y0, y1, z_top] from the "brush"
  part (= the opening); `Tests/test_tray_rack_interface.py` couples dims to it (waterfall inside with 3 mm margin,
  z_top within 2 mm under the top plane, mirrors, dims match, placement unchanged vs Task 3, materials unchanged).
- **Budgets:** 42U Open LOD0 13424 -> 14616 (cap 15959), LOD1 2724 -> 2956 (3649); 24U Open LOD0 11034 -> 12746
  (14128), LOD1 1856 -> 2256 (2886); materials unchanged (24U 8/8).

## Plan 2 Task 4: tray kit and the straight pieces (StraightS, StraightL, Reducer) (2026-10-18)

Code: `dc/tray_kit.py` (bpy kit: everything takes plan objects), `dc/tray.py` (`build`, `collision`, last LOD,
report helpers), `dc/tray_xsec.py` (pure-Python cross-sections, strap groups, wall-height profile, U stations,
simplify), `dc/preview_trays.py` (the shot catalogue, all later tray tasks), `p2t4_sheet.py` (sheets).
`build_dc.BUILDERS["tray"] = BUILDERS["trayrods"] = build_tray`; `DC_PREVIEW=plan2-tN` -> `preview_trays`.

- **Paintable tray steel (ledger CHECK): YES, but NOT used (Ruling P2-21, fix round 1: the basket is fixed BrushedMetal;
  this bullet is the check's finding only).** Vanilla's paint mask is the `_colormask` texture: PaintedMetalColorable's
  is white (mean 254.9/255); PaintedMetalScratched 222 and PaintedMetalColorable_Damaged 238 are partly paintable;
  every other block material has none or an all-black one, including every alpha-tested candidate (ConstructionMesh01-05:
  all 0; GratingMetallic, MetalPerforationSteel: no mask). [Superseded by fix round 1: the basket and the tray
  hardware are fixed BrushedMetal, only the data cables take the paint, the LOD2 card matches the basket, and there are
  no LOD2 paint ribbons; flipping back is `style.TRAY_STEEL = PAINT`.] The last LOD is the interim paint material, so the
  silver basket pops to the cable paint at that final switch (a baked LastLOD is the follow-up).
- **LOD2 card: GratingMetallic** (2cc33fe2), chosen over MetalPerforationSteel and ConstructionMesh01/05 by
  `card_compare_*`: its rectangular slots are the only pattern that reads as a welded-wire grid; it is vanilla's
  catwalk floor (CatwalkNarrowBase uses ONE upward face for it, so its state renders two-sided); 43 % open.
  UV: 2 m per unit (60 x 20 slots per tile: 3.3 cm across, 10 cm along = the U-wire pitch).
- **Part rationale (functional design):**
  - floor wires (9, r 4 mm, every 5 cm, tops = the floor top) and U-wires (every 0.1 m from 5 cm off each port, under
    the floor wires, legs outside the wall wires at s 0.218): the load-bearing basket; the rhythm continues across
    joints (5 + 5 cm);
  - safety edge: the 5 mm top wire, each U-wire leg turned over it (the rolled T-weld): no cut wire end at the cable
    jackets;
  - splice plates: half a bolted (BrushedMetal since fix 1) plate per port and wall, open on the port plane; two halves and two bolts
    per joint join the sections (a free end shows a half plate);
  - bundles: 7 cables of r 9 mm; only the 6 outer cables are built, each as the 4 faces of a 6-sided cable between its
    contacts with its neighbours (the skin is closed: `test_cable_skin_closed`), smooth per cable, sharp crevices (fix 1: 3 faces per cable, with the lay);
  - straps: Darker bands = bundle retention. Ruling P2-17: bundles that touch or nest share ONE band per station (Full:
    one hull band round all 9; Low/Moderate: one per bundle); a cinch buckle on top at LOD0 (BrushedMetal since fix 1);
  - trapeze = hanging support: Darker lipped strut channel (opening up), Yellow chamfered end caps whose face is 2 mm
    in with a bolt head (two before fix 1) proud to the 1 mm-inset end plane, r 5 mm rods (BrushedMetal since fix 1) ending on the channel's base (a
    channel nut), a square strut washer + hex nut on the lips;
  - rod plates = ceiling anchor / rod extension: 34 mm (plan ROD_PLATE, 1 mm inside the sides; the brief's 40 mm would
    poke out), the rod threaded into its boss, two square anchor bolt heads (fix 1; it bolts to the structure above);
  - Reducer: Rubber boots = sealed spare ends; Darker saddle clamps (band + post) = strain relief; Yellow tags with a
    CleanWhite stencil = density-change marking ("F>M"; it reads "M<F" on the +y wall, so the arrow always points to
    port b). The tag moved to x 0.125, outside the U-wire legs (plan `TAG_X`, `TAG_S`), clear of the trapeze rods.
- **LODs:** detail 0 (full), 1 (4-sided wires, every other U-wire, 4-sided bundles, one strap per 0.5 m, trapeze
  without nuts), 2 (card set, 3-sided bundles, the strut only; 4 materials: card, paint, Yellow,
  Rubber, with Darker/MetalDull/BrushedMetal/Grey mapped to Rubber, on card pieces only), last (U channel + bed quad, <= 19 tris, interim LastLOD = paint).
  Keen's LOD count follows the measured LOD0 (`assemble.fit_lods`): Empty/Low StraightS/L have a light LOD0, so they get
  3 LODs with tight caps (since fix 1 also StraightS Moderate and Reducer Low; pinned in `test_lod_chain_pinned`); `tray.build` then uses the next simpler detail whenever a LOD would pass 60 % of its cap
  (Empty/Low LOD1 = the card version). Bundles at LOD1 are 4-sided, not the brief's 8-sided fluted tubes: at LOD1
  range a bundle is ~4 px tall and the 8-sided tubes alone would break 600 tris/m on a StraightS.
- **Mount hints:** a game mount is a whole cell face (8 rays per cell, `se2model.placement`), so a 34 mm rod plate
  cannot mount by itself. Each hardware hint is sized to catch exactly one cell's rays: rod plate y- -> the cell on its
  -x side, y+ -> +x side (diagonal, so Up = 2 groups that never merge, and the pattern survives a 180 deg turn); the
  strut end plates likewise one cell each on Forward/Backward; Down = the cells under the strut; ports = whole faces.
  The brief's area coverages (< 5 % / < 10 %) are not reachable on a 2-cell-wide face; the tests pin the cells instead.
- **Report:** tray entries carry `tray` = {run_length, ports (model frame), materials_per_lod} and
  `placement.mount_cells` (new `mount_cells` per face in `se2model.placement.analyse`). Ruling P2-15: build_dc keeps
  built CATALOGUE entries; `integration.built_names` stays the pipeline's (trays are not exported until Task 5);
  `test_render_mesh_within_bounds` covers every built report entry. `export_models.UNFRACTURED_FAMILIES`.
- **Fix round 1 (Ruling P2-21, V1/V2):**
  - **Basket steel reverted to plan Decision 6:** the basket wires are fixed **BrushedMetal** (bright/galvanised steel,
    chosen over Chrome and MetalDull by `preview/p2-task-4/fix1/basket_compare_*`); only the data cables take the paint,
    so a painted tray always shows silver basket + coloured cables. The hardware (rods, nuts, washers, plates, splice
    plates, buckles) is BrushedMetal too (zinc-plated), which keeps a Reducer at <= 8 materials across all its LODs
    with the card. The LOD2 GratingMetallic card now matches the basket at range (no colour pop); the LOD2 paint
    ribbons are gone. The CHECK result above stands as a finding (the basket COULD be paintable: one-line flip,
    `style.TRAY_STEEL = PAINT`).
  - **Cable lay:** at LOD0 each bundle's six strands turn round its axis, 60 deg (one cable pitch) per 0.5 m, in
    straight 0.25 m segments (30 deg each, a chord sags 0.6 mm). Port-to-port bundles turn whole pitches only
    (`tray_xsec.lay_total`), so every port face shows the same strand pattern and the lay continues across joints;
    a turned piece keeps the helix's hand. Strands are 3 faces each over their exposed 240 deg (was 4) to pay for it.
    Varied strand diameters were rejected: with interchangeable strands at the ports they would break the phase match.
  - **Cinch:** at LOD0 a strap's band lies 1.5 mm inside the bundle radius (`STRAP_BITE`), so it bites into the cables.
  - **Budget trims (StraightS Full LOD0 1472 <= 1500):** the LOD0 U-wires are 5-sided, the splice and rod-plate bolts
    have square heads, two diagonal anchor bolts per rod plate (was four), one bolt per end cap, no nut under the rod
    plate (the rod threads into the plate's boss), the LOD0 band outlines are 8-sided.

## Plan 2 Task 5: the tray family in the definitions pipeline (2026-10-18)

- `catalog.PIPELINE_FAMILIES` now has `tray` and `trayrods` (Ruling P2-15), so `catalog.BLOCKS == CATALOGUE` (54).
- Clones: 35 WallInsertPipes clones (kind + 12 definitions each, including the block's own PlacementDefinition) and 3
  StructuralSupportStraight clones for the rod hangers (kind + 11), whose LastLod material
  (`LODMaterials/TrussFrame_Long_LastLod.def`) is renamed by `clone.ALSO` (`--also TrussFrame_Long=<name>`, an existing
  `se2mod.py copy` option; no shared-tool change).
- `integration.tray_patch` (all 38): PCU 5; no MountPointGeneratorSettings (neither source has one); the cloned
  PlacementDefinition with `AutoRotateFace: null` (Pipes clones only: the strut uses its template's placer).
- The 11 built trays (StraightS/L x 4, Reducer x 3) are staged with models, 7 build stages, the ParticleEffects dummy at
  the block centre, and are in the initial unlock (27 blocks now).
- Menu and costs wait for Task 9: a tray kind gets its name and description only and keeps the cloned vanilla group;
  the block keeps the cloned recipe (`recipes.costed`). The core menu/icon/recipe tests cover `menu.GROUPS` families.
- First game build with the trays: exit 0 twice, no DataCenter warnings, 0 `.meta` problems. **No builder rejection**:
  unfractured trays (Decision 10), at most 7 mesh parts per model, one physics box each.

## Plan 2 Task 6: the turns (TurnH, TurnUp, TurnDown) x 4 densities (2026-10-18)

- **Facets on radials** (`tray_xsec.bend_facets`): every longitudinal part of a bend (9 floor wires, the lower wall
  and safety-edge wires, every bundle) is sampled on the same radial lines: both ports, both 5 cm lead ends (the PORT
  rule keeps the leads straight) and the arc every 15 deg (6 facets per 90 deg). The U-wires stand on exactly those
  radials (`bend_u_stations`), so every wire crossing is a vertex and the wire mesh fans round the bend as a cut-and-
  bent basket does (TurnH: 0.118 m pitch on the centreline, 0.17 m at the outer wall). LOD1 halves the facets and
  folds the leads into the end chords; LOD2 and the last LOD use the mid radial only. The sweep's end rings stay square
  to the ports (`tray_kit.frames(ends=...)`), so even the coarse LODs end flat on the port planes.
- **Straps** stay on the plan's radial stations (Decision 13); between two facets a bundle's chord lies a few mm inside
  the plan's arc, so the band is centred where the BUILT bundle crosses the station plane (`tray_kit._on_facets`).
- **Lay rule for bends (Ruling P2-22):** a port-to-port bundle turns the whole number of 60 deg pitches nearest its own
  length at the nominal rate, and at least one (`tray_xsec.lay_pitches`). Inner lanes are shorter than outer ones,
  so each lane's rate differs slightly (TurnH Full: 81..149 deg/m against 120), but every lane leaves both ports in
  phase 0, so the strand pattern matches every neighbour. No catalogue lane is under 0.25 m (tested), so no lane
  twists faster than twice the nominal rate and none runs untwisted.
- **Supports:** TurnH's floor strut on the 45 deg radial is now as wide as the basket (its Yellow caps at the U-wire
  legs: Ruling P2-20, nothing past the inner wall); TurnUp's and TurnDown's struts moved to the lead-end U-wire
  (5 cm from the port) so they carry a cross wire instead of floating under the floor wires.
- **Collision:** two physics boxes per turn (the two halves of the trough), occupancy = the plan's cells, mounts on
  both port faces and Down under the TurnH / TurnUp strut only (a fitting is carried by its neighbours).
- **Last LOD:** two chords (port, mid radial, port), each the underside, both wall outsides and the bed: 16 tris.
- **Budget:** LOD1 and LOD2 meet the plan's per-metre budget as 1 m fittings (Full: 580/560/560 and 126). LOD0 does
  not (TurnH Full 4512; 6 facets x 9 bundles of 6 strands is most of it): it is held to half Keen's LOD0 limit and
  proven over a 20 m Full run with four turns (`test_run20_with_turns`).
- **Rationale:** every part is the Task 4 kit's (wire basket, safety edge, splice plates, straps, strut); nothing new.
- **Keen's model size (build failure found and fixed):** Keen's checker sizes a model by its LOD0 bounds. TurnUp
  (0.499 m) and TurnDown (0.498 m) first came out "small" (< 0.5 m: 4 / 3 / 1 materials), and the game build FAILED
  (exit 301) on the material and mesh-part warnings. Their floor struts now run the full 0.5 m across, the end-cap
  bolts ON the across faces (`Support.params["flush"]`, the only exception to the 1 mm inset; back to back with any
  neighbour, never seen), so both are 0.5 m models (8 / 8 / 6 / 4 / 1). Pinned by `test_keen_material_limits`.

## Plan 2 Task 7: the junctions (Tee, Cross) x 4 densities (2026-10-18)

- **Real tray tee (P2-18):** the branch-side lanes turn into the branch from both ports, concentric with the r 0.15
  fillets; M0 splits at one collar. Turning groups are faceted on radials every 15 deg (`tray_xsec.sweep_facets`,
  a bend's rule), 5 cm port leads straight.
- **Split collar** (`tray_kit.split_collar`, LOD0): two Darker half shells clamped round M0 with a 1.5 mm split line,
  a flat ear each side, one Brushed bolt through both ears (head on top, nut below). Purpose: it holds the split.
- **Crossover saddle** (`tray_kit.crossover_saddle`, P2-19): a formed 4 mm Darker deck; its ends roll down on the
  c-d stack's own convex radius (no cable-cutting edge), as tongues over the stack's width (clear of the fillets);
  its sides roll up into 30 mm lips (keep the stack on the deck, stiffen the plate) carrying a CleanWhite "X-OVER"
  stencil that faces the a and b ports; four Brushed square legs, each bolted through the floor wires between a
  clamp plate and a backing plate; Brushed tie mounts beside the stack at each deck strap, the outermost band of
  each deck strap running down into them (P2-20: straps tied to the saddle). Deck top 0.140 above the cell plane,
  measured on the built mesh (`tray.geometry.saddle_top`). The a-b straps under the deck carry no buckle (the deck
  clears their bands by 1.5 mm).
- **Walls (P2-20):** junction walls stand 0.15 and step to the plain 0.10 at every port: flat to just past the first
  U-wire (6 cm), a straight 45 deg slope over 5 cm, at 0.15 before the second U-wire. The fillets have two posts
  (U-wires of a curved wall, none at the 45 deg point next to the free cell) and, at LOD0, a corner floor: an edge
  arc 1 cm in from the wall and stubs on the 5 cm pitch to the outer floor wires. A branch's floor wires reach the
  run's outer floor wire; its U-wires count from its port; the Cross skips the U-wires under the crossing (the other
  run's floor wires are there).
- **Straps:** one band per nest per station plane (P2-17), grouped by plane: each turning group shares its 45 deg
  radial; the turning leads share the straights' planes 0.125 m from a / b; the branch has one band 0.125 m from c.
- **Lay:** a split child is phase-locked at its port (`tray_xsec.lay_locked`). A non-planar bundle (the dressed F1+
  turning lane) gets its rotation-minimising frame drift cancelled by a spread twist (`tray_kit._frame_drift`), so
  it arrives in phase 0; zero on every planar bundle. Bundle simplification keeps the 5 cm PORT lead straight
  (`tray_xsec.simplify_bundle`).
- **LODs:** LOD1 drops the collar (and the dressing over it), the saddle legs and the fillets' lower wire; the c-d
  stack runs port -> incline top -> deck. LOD2: one card floor per path, corner fans (no overlaps), walls at the
  plain 0.10 (they match neighbours at range), fillet walls drawn (T4 carry). Last LOD: Tee 18 tris (floors +
  walls), Cross 12 (plus-shaped floor).
- **Collision:** 3 boxes: each path's trough at 0.10 (meets neighbours flush: the step) + one raised box (Tee: the
  run at 0.15 between the steps; Cross: the crossing to the stack top). Mounts: every port face + Down under the
  floor strut. Free cells: the Tee's two beside the branch, the Cross's four corners (`tray_plan.corner_cells`;
  only a fillet's sliver grazes them, <= 12 mm measured).
- **Run length:** a junction adds its arms (port to centre): Tee 1.5 m, Cross 2.0 m.
- **Rationale:** every part has a purpose: collar (holds the split), saddle deck (keeps crossing bundles off the
  through bundles), rolled ends (bend former, no cutting edge), lips (retention + stiffness), legs and foot clamps
  (carry the deck through the floor wires), tie mounts (strap anchors), stencil (marks the crossover for installers),
  fillet posts and corner floor (the basket's frame and floor round the opening).

## Plan 2 Task 8: the rack interface (Drop x 3, Chute, rod hangers x 3) (2026-10-18)

- **Waterfalls (Drop):** each peels off L1+ at a split collar, climbs plumb between the (Full: dressed) top-layer
  lanes, bends over (r 0.05), swings across the tray in plan (r 0.1225) and rolls over the guide on the 0.10 m bend
  radius (fibre and copper limit) to fall plumb onto the rack's top plane at (+-WF_X, WF_Y). The crest is now 0.147
  over the floor (was 0.135): one basket U-wire stands under each guide (x 0.15 / 0.85) and its turned-over end
  needs the plate 3.6 mm higher; the clamps bridge the gap. A waterfall is phase-locked at its entry (whole cable
  pitches, its frame turned to the entry's a axis: `tray_xsec.lay_locked` / `frame_drift`), so a Chute under it
  continues it strand to strand (built-mesh test).
- **Waterfall guide** (`tray_kit.waterfall_guide`): a Darker moulded trough from 20 deg inside the tray to plumb, its
  plate ribbed across every 10 deg (the bundle rides the rib crests at r_top = 0.0775), two 16 mm cheeks keeping the
  bundle on the radius, two Brushed spring clamps (8 x 1.5 mm strip) hooked over the safety-edge wire 30 mm either
  side of the waterfall, between the U-wires. LOD1: the plate on 3 chords; LOD2: its top as a 2-chord strip.
- **Straps on the fall:** two bundle ties at 0.125 and 0.375 m over the bottom plane (the Chute's rung rhythm
  0.125 + k 0.25 carries on up through a Drop over a Chute); LOD0 only. The run's bands keep >= 2 mm off the
  waterfall skins (tested on the built skins: the T2 strap-clearance carry).
- **Landing brush collar** (`tray_kit.brush_collar`, LOD0): a Darker ring (bore R_WF + 5 mm, 6 mm wall, chamfered)
  seated 1 mm over the plane the waterfall lands on: across the slot it bears on the 42U brush plate's frame (its
  radius 0.0335 lies between the opening's half width 0.0275 and the frame's 0.0355), over a half rack on the
  Chute's top plate; 16 bristle tufts from its bore down onto the bundle (the brushes part round it); two screws into
  the plate's frame. Mount: the waterfall column's bottom cell (Down) under each collar.
- **Chute** (`tray_kit.ladder`): per waterfall a Darker foot plate (6 mm) seated over the half rack's brush plate
  (opening + flange + 3 mm), its bore lined with bristles; two Brushed lipped-C rails (12 x 40, web towards the
  bundle) standing on it; Brushed rungs (12 x 20, chamfered) every 0.25 m between the webs, the bundle tied to each
  (the band wraps the rung's back corners: `tray_kit.straps` tie_to); a Brushed top clamp plate across the rail heads,
  1 mm under the top plane (the Drop's collar sits on it), a Darker split clamp (the collar part) under it gripping
  the bundle. No bolts on the top plate (they would stand proud of the top plane): the rails are welded to it.
  LOD1: plain rails, rungs as their two faces, the plates as slabs. Physics: one thin box per ladder (players walk
  round it). Mounts: foot plates (Down, the 24U roof's top_left / top_right) and top plates (Up, the Drop's landing
  cells).
- **Rod hangers** (`tray_kit.rods`): per rod a 34 mm square washer (the tray's rod-plate footprint) and a 22 mm hex
  coupler nut at the bottom, the r 5 mm rod up through a Darker lipped ceiling channel (opening down, Yellow end
  caps as the trapeze's) held by a square washer and hex nut under its lips, to a Darker 60 x 34 mm anchor plate
  with four anchor bolts under the top plane. The rods are BrushedMetal like the trapeze rods they extend (P2-21's
  zinc-plated hardware), not the brief's MetalDull. Mounts: the tray's rod-plate hint rectangles at the bottom
  (Down) and the top (Up): one cell per rod, diagonal. The 0.25 m hanger is a Keen small model (0.498 m: 4 / 1
  materials, it uses 3) and keeps its 1 mm insets (no flush exception). Own PlacementDefinition (the strut clone
  had none): AutoRotateFace null; a ParticleEffects dummy added to the cloned model definition.
- **Shared code, unchanged outputs:** `_support_hints` emits a hint only for hardware on a block face (the Drop's
  strut stands on an inner plane over its waterfall column; its +y end plate is inside the block); every earlier
  tray rebuilt byte-identical in build_report.json.
- **Budgets (tris LOD0 / 1 / 2 / last):** Drop Low 4588 / 448 / 104 / 14, Moderate 5356 / 544 / 122 / 14, Full
  6452 / 592 / 146 / 14 (LOD0 0.51 x Keen's; LOD1 / LOD2 within 600 / 150 per metre as a 1 m fitting); Chute 1672 /
  236 / 16; Rods 380 / 16 (0.25, 2.0 m), 380 / 104 / 16 (1.0 m). The waterfalls' coarse LODs follow their
  stretches (`tray_plan.waterfall_stations`); the Full dressing is a LOD0 detail (straight lanes from LOD1).
- **Rationale:** guide (keeps the bend radius, protects the jackets at the wall), ribs (grip and air under the
  bundle), cheeks (keep it on the radius), clamps (hold the guide on the wall), ties (bundle the waterfall),
  collar + bristles (seal the entry, part round the cables), foot plate (seats the chute on the roof brush),
  ladder rails / rungs / ties (carry the long drop), top clamp plate and clamp (take the drop's weight), coupler and
  washer (join the hanger's rod to the tray's), ceiling channel + anchor plates (hang the pair from the slab).

## Plan 2 Task 9: build menu, names, costs and icons for the 38 tray blocks (2026-10-18)

- **Menu** (`dc/menu.py`, Decision 11): five new group tiles in the "Data Center" subcategory: "Cable Trays: Empty /
  Low / Moderate / Full" and "Cable Tray Supports". Kinds per density tile in `TRAY_ORDER` (Empty: 6 kinds, no Drop or
  Reducer; the others 8); the supports tile holds Rods then Chute. Multi-size kinds: Straight (owner `StraightL`,
  Short = size 1 at DisplaySize 0.5, Long = size 2 at 1.5) and Rods (owner `DC_TrayRods_100`; 0.5 / 1.0 / 2.0).
  The tray kinds' cloned vanilla groups (WallInsertPipes: Structural > Walls; the strut: Trusses) are replaced.
  `menu.group(spec)` / `menu.kind_key(spec)` generalise the core's family-keyed lookups.
- **Group order (fixes a core latent issue):** `SubcategoryDefinitionPostProcessor` sorts tiles by multi-kind first,
  then `Order` (0 = last), then name. The core staged both groups at Order 0, so "Rack Servers" sorted before
  "Server Racks", and every "Cable Tray..." tile would have sorted before both. Groups now carry Order 100..700.
- **Names:** "Cable Tray, <shape> (<load>)" ("Cable Tray, Straight Long (Full)", "Cable Tray, Reducer (Full to
  Moderate)", "Cable Tray, Hanger Rods 0.25 m"); multi-size kind tiles drop the size ("Cable Tray, Straight (Full)",
  "Cable Tray, Hanger Rods"; `names.KIND_NAMES`).
- **Costs** (`dc/recipes.py`): the core rule (source in-game cost x our mass / its mass, half up, min 1).
  - Sources read from the SDK through their Copy chains (`test_sources_match_sdk` follows `recipe_chain` and
    `block_chain` and measures the cell box from the collision glTF): WallInsertPipes = the wall panel's recipe
    (4 SP + 3 C, 3 SP optional, 3300000), 6x6x1, Mostly Hollow (template); StructuralSupportStraight = 1 SP
    (16250000), 2x10x1 (box collider 0.5 x 2.5 x 0.25), Mostly Hollow (template).
  - The strut's own in-game scale is **2** (69 kg block vs a 35 kg recipe), so its in-game cost is 2 SP;
    `recipes.source_scale` multiplies it in (every core source is 1, so no core number moved).
  - Trays at **Hollow** (Truss250's 3dca2cf9), written to the block definition (`recipes.density_patch`, which also
    covers the door racks' Mostly Hollow); rods keep Mostly Hollow.
  - Cables are decoration: occupancy (and so cost) is equal across a shape's densities.

| Block (any density) | Run (m) | Units | Mass ours / source (kg) | Volume ratio | Critical | Optional |
|---|---|---|---|---|---|---|
| DC_Tray_StraightS_* | 0.5 | 1 | 13.4 / 107.7 | 0.12 | 1 SteelPlate, 1 Construction | 1 SteelPlate |
| DC_Tray_StraightL_* | 1.5 | 3 | 31.2 / 107.7 | 0.29 | 3 SteelPlate, 3 Construction | 3 SteelPlate |
| DC_Tray_TurnH_* | 1.0 | 2 | 25.0 / 107.7 | 0.23 | 2 SteelPlate, 2 Construction | 2 SteelPlate |
| DC_Tray_TurnUp_* | 0.91 | 2 | 18.3 / 107.7 | 0.17 | 2 SteelPlate, 2 Construction | 2 SteelPlate |
| DC_Tray_TurnDown_* | 0.59 | 1 | 22.9 / 107.7 | 0.21 | 1 SteelPlate, 1 Construction | 1 SteelPlate |
| DC_Tray_Tee_* | 1.5 | 3 | 27.1 / 107.7 | 0.25 | 3 SteelPlate, 3 Construction | 3 SteelPlate |
| DC_Tray_Cross_* | 2.0 | 4 | 31.2 / 107.7 | 0.29 | 4 SteelPlate, 4 Construction | 4 SteelPlate |
| DC_Tray_Drop_* | 1.0 | 2 | 35.0 / 107.7 | 0.33 | 2 SteelPlate, 2 Construction | 2 SteelPlate |
| DC_Tray_Reducer_* | 1.0 | 2 | 13.4 / 107.7 | 0.12 | 2 SteelPlate, 2 Construction | 2 SteelPlate |
| DC_Tray_Chute | 1.25 | 3 | 27.1 / 107.7 | 0.25 | 3 SteelPlate, 3 Construction | 3 SteelPlate |
| DC_TrayRods_025 | - | - | 18.2 / 69.0 | 0.26 | 1 SteelPlate | - |
| DC_TrayRods_100 | - | - | 58.0 / 69.0 | 0.84 | 2 SteelPlate | - |
| DC_TrayRods_200 | - | - | 98.7 / 69.0 | 1.43 | 3 SteelPlate | - |

  **Fix round 1, Ruling P2-26 (run-length floor):** the volume rule alone put every Pipes-sourced piece at the
  minimum 1 + 1 + 1 (Short == Long). Each item is now max(volume amount, units), units = round(RUN_LENGTH / 0.5 m)
  (`recipes.RUN_LENGTH`: the port-to-junction centreline, i.e. the sum of the ports' x/y/z extents in the cable plan;
  the Reducer counts as a 1 m run, the Chute as its 1.25 m ladder). The rods are not floored (they already scale) and
  keep the strut's in-game scale 2. Game scale stays 1 everywhere (a recipe heavier than the block rounds to 0 and is
  lifted to 1). The volume ratio column is the mass ratio; the rods' cost is 2 SP x that ratio.
- **Icons** (`dc/preview_task10.py`, the core renderer, same `Icon` rig: lens, studio lights, AgX -0.55 EV, transparent
  200 px): trays instanced at LOD0 with the data cables in the blue preview paint (Ruling P2-21: the paint goes to the
  cables, the basket stays galvanised). Routing pieces from higher up (~50 deg) so the load reads inside the basket;
  straight-type pieces (Straight S/L, Reducer, Drop) more along their run, as vanilla's conveyor straights; rods from
  the side so the two rods separate; the Chute with the rack view. Fills per shape (`TRAY_FILLS`): 0.5 m pieces
  smaller (0.70) than the long ones (0.92), the rods by length (0.50 / 0.76 / 0.90).
  `render_all` now renders icons and store shots for whatever is built (heroes still need the core blocks).
- **Store shots** (`preview/blocks/DC_Tray*.png`): each tray on the dark hall floor, same direction as its icon.
- **Sheets:** `icon_sheet.py trays` (`preview/p2-task-9/icons_contact_sheet_trays.png`: vanilla structural icons,
  our core icons, one row per group dark and light, 64 px rows) and `icon_sheet.py menu`
  (`preview/p2-task-9/menu_structure.png`: the G-screen tree).
- **Tests:** `Tests/test_tray_menu.py` (groups, order, sizes, names, costs with goldens, Hollow density, icons, the
  density read on icons). `Tests/test_task10.py` widened back to all 54 blocks (menu, icons and store shots, recipes,
  unlock); `test_tray_integration` names updated.
## Plan 4 Task 1: script toolchain, shared helpers, API probe (2026-10-18)

- **How the game compiles the scripts** (decompiled 2.4.0.95). Only with `-loadScripts` (`GameApp.cs:330-333`).
  `GameScriptCodeProvider.LoadProjectAssembliesAsync` (`GameScriptCodeProvider.cs:29-57`) compiles `Scripts/Simulation`
  then `Scripts/Client`, each with a fresh `ModCompilationDescriptor` (`GameApp.cs:445`), into `<vrgproj Name>.<Sub>`
  (`ScriptCodeProvider.cs:77`), so `DataCenter.Simulation` and `DataCenter.Client`. Client also references
  Simulation's emitted image (`GameScriptCodeProvider.cs:46-50`), so shared helpers live in Simulation (P4-5). Any
  error diagnostic throws `ScriptLoadingException` (`ScriptCodeProvider.cs:80-83`) and fails the mod's load.
- **`Tests/CompileCheck`** (copied from an earlier prototype) replicates that offline, under wine with the game's own DLLs,
  whitelist lists (`GameApp.cs:452-489`, verbatim, including the in-game whitelist), generators, analyzers and the
  post-processor step. `run.sh [Simulation|Client|all] [--mod <dir>] [dump-dir]`; Client/all compile Simulation first
  and hand its image to Client. It catches VRS1001 (checked: a Client file using `System.Text.Json` fails, exit 1)
  and resolves a Client reference to a public Simulation type (checked).
- **Plan 4: API probe.** `run.sh all --mod Tests/CompileCheck/ApiProbe`: every row compiled as written, first try
  (`DataCenterProbe.Simulation` and `.Client`: OK: 0 errors). No row needed an alternative. The generated sources show
  DCS invocation stubs for both probe jobs: `[OnUpdateRigidAnimation] static void (ref RelativeTransform, KvmProbePart)`
  and a job in a nested `JobGroup` with `[Before(typeof(OnPrepareRigidAnimation))]`; without a context parameter the
  stub's `__jobContext` is `object`. The post-processor reaches the manager through the protected
  `DefinitionPostProcessor.Manager` (`DefinitionPostProcessor.cs:25`).
- **`CompositionSurgery`** (Simulation/Shared) validates before it changes anything: the new part goes through the
  builder's own `EntityBuilder.ResolveComponent` checks (definition and OB types, `EntityBuilder.cs:464-511`), the tag
  table is compiled (`Builder.TagIndex` throws on a conflicting tag, `EntityCompositeDefinition.cs:178-192`) before
  `Assign`, and `AddComponent` also requires the prefab's OB keys to equal the composition ids in order (the OBs are
  matched by index, `EntityBuilder.cs:231-255`). `AddComponent` rolls the composition back if the OB slot cannot be
  added. Failures log once (`DcLog.Once`) and return false.
- **Tags in a type swap (for Task 8).** Default tags come from the base-class chain (`ComponentInfoIndexer.cs:97-118`):
  every rigid animation's is `RigidAnimationComponent`, and the KVM composites name that tag in `TagSlots`.
  `Entity.Get<T>()` hard-casts whatever sits under T's default tag (`Entity.cs:119-130`). `SwapComponentType`
  therefore replaces the old type's default tag with the new type's, and refuses a slot carrying any other tag
  (fix round 1: vanilla code could `Get<T>(thatTag)` and hard-cast). A driver deriving from
  `Component` is then found by `Get<KvmDrawerPart>()`, and FBAC's `TryGet<ToggleRigidAnimationComponent>` finds
  nothing, which is what the script wants. Only OB-free parts can be swapped (the data's KVM animation slots are null).
- **Risk for Task 8: two components declaring the same `[Definition]` type.** A composite entry without a `Type` is
  resolved from its definition type (`EntityCompositeDefinitionObjectBuilder.cs:1249-1253` → `RuntimeComponentInfo.ForDefinition`),
  which throws "Ambiguous match" when two component types declare that definition type (`ComponentInfoIndexer.cs:75-90`).
  A script part with `[Definition] TranslationAnimationDefinition` creates exactly that pair. All 354 component entries
  in tools/vanilla-ref name their `Type`, so vanilla is not affected, but other mods might omit it. Prove it in game
  (Task 8) or give the drivers their own definition type.
- **In-game probe:** `Source/Model/review/probe_scripts.csx` (the switch, the two script assemblies, the reflection
  targets from the game and from inside the mod). Not run yet: the game was not available.
- `Scripts/Client/Core/.gitkeep` keeps the (still empty) core folder in git until Task 5; the game reads only `*.cs`.

## Plan 4: save safety and the Programmable route (2026-10-18)

**Programmable route: A'**

The Programmable's server composite and prefab carry the `InGameScriptingComponent` (with its definition and default
object builder) permanently, in both script modes. No runtime injection code exists. Ruling P4-1 was resolved as A' by
the controller. Route B (inject at runtime only with `-loadScripts`) also passes the engine's save gate, but A' wins
on its trade-offs. Full trace: `docs/research/dc-scripts-save-safety.md` (paths below relative to `tools/decompiled/`).
`config.PROGRAMMABLE_ROUTE` records the choice; `Tests/test_scripts_layout.py::test_route_recorded` checks it.

| Question | Answer | Evidence |
|---|---|---|
| (a) Saved shape of a block | A full keyed OB list (`Definition` by GUID, `ObjectBuilders`), not a delta against the prefab; plus a `snapshots` side-file with the component IDs as saved | `VRage.DCS/Keen.VRage.DCS.ObjectBuilders/EntityObjectBuilder.cs:206-218`; `EntityObjectBuilderObjectBuilder.cs:452-465, 762-765`; `EOBUpdateContext.cs:701-723`; `EntityContainerSerializer.cs:88-94`; `KeyedListSerializer.cs:28,56` (reads deltas only) |
| (b) Extra OB on load | Dropped by the EOB migration (`Remove`) before the count check; a missing one is re-inserted from the prefab | `EntityContainerDeserializer.cs:92-127`; `EOBUpdateContext.cs:752-811` (removes `:760-771`, inserts `:772-783`), `:821-880` |
| (c) A throw on load | Caught per entity, then rethrown as `EntityBundleInitException`: the whole bundle fails. The "Mismatch in Entity parts" throw (`EntityBuilder.cs:231-256`) is not on the world-load path | `GameEntitySerializer.cs:375-378, 418-425`; `EntityBuilder.cs:459-462`; callers `PrefabDefinition.cs:292`, `CompositionProcessorComponent.cs:17` |
| Client entities are not saved | 0 `*_ClientComposition` GUIDs against 136 `*_ServerComposition` in a real save, so P4-3's client-only injection is save-safe | research doc section 3 |
| Run without `-loadScripts` | `ProgrammableBlockDetailModelServer.OnPropertyChanged` (`:206-231`) -> `Run` (`InGameScriptingComponent.cs:108-119`) -> `LoadScript` (`:173-191`) -> `InGameScript.Load` (`InGameScript.cs:101-113`) -> `ScriptCompiler.CompileAsync` (`ScriptCompiler.cs:30-50`) returns `CompilationResult` error -> `InGameScriptLoadResult.Fail` -> `CompilationResult = Error; return false` (`:183-187`). No throw in the `async void` | `GameCompilationDescriptor.cs:13`, `GameWhitelistProvider.cs:30` (empty by default), `GameApp.cs:330-333, 437-490` (only `AddScripting` fills them), `ScriptingAssemblyInjectorPreProcessor.cs:17-23` |

**Why A' over B.** B strips the saved PB script text the first time a world is re-saved with scripts off, needs a fixed
component GUID plus a matching entry in the prefab's `_entity` list (else a silent reset or a null OB), and needs
matching `-loadScripts` on both multiplayer peers. A' keeps saves identical in both modes.

**Cost of A'.** Players without scripts see the Programmable's terminal UI, and Run reports a compile error (matches
"just won't run til keen enables it"). Vanilla 2.4 ships no block with `InGameScripting`, so no Keen content has
exercised this path with scripts off; the trace is by reading only.

**Data requirement (Task 4).** Keep every `InGameScriptingDefinition` field populated (`EntryTypeName`, the LocKeys and
the limits): `LoadScript` dereferences `_definition` unconditionally (`InGameScriptingComponent.cs:175-188`).
`InGameScriptingComponent.IInSceneListener.OnAddedToScene` (`:69-75`) auto-runs on load when the saved `Running` flag is
true, so a world saved with a running script reaches the same failure path at load with scripts off.

**Still needs the game (Task 13 section C, INGAME-CHECKLIST section 12):** one Run click with scripts off; save and
load both ways. REFLECTION/ENGINE: re-check `EOBUpdateContext.cs:725-880` and `EntityContainerDeserializer.cs:92-127`
after a game update.
- **Fix round 1 (review I1-I3, M1-M6).**
  - Every surgery now runs the composite's own dependency checks before `Assign`: the game's
    `EntityCompositeDependencyOrderBuildStrategy.IterateDependencies` for every component (it throws "Unsatisfied" /
    "Malformed dependency", `EntityCompositeDependencyOrderBuildStrategy.cs:13-40`), and every dependency must sit at a
    lower index (the order `IBuildStrategy.Build` sorts into, `EntityCompositeDefinition.cs:38-69`). Surgery never
    reorders, because prefab OBs are matched by index, so a change that would need a reorder is logged and refused.
  - `AddComponent` takes a required 6th argument, `allPrefabs` (a post-processor passes
    `Manager.GetDefinitionsOfTypeAndDescendants<PrefabDefinition>()`), and refuses when another prefab uses the same
    composition object. When the type is already present it checks this prefab's OBs: in line → no-op; exactly the
    trailing slot missing → adds it; anything else → logged refusal. A failed rollback is logged as such.
  - The decisions live in the game-free `Scripts/Simulation/Shared/Core/{SurgeryRules,OnceGate}.cs`, unit-tested by
    `Tests/CoreTests` (`surgery.*`, `log.once_gate`); pytest runs CoreTests (`test_core_tests_pass`).
  - **Compile gotcha:** a generic `where T : IEquatable<T>` instantiated with `StringId` is CS0012 (StringId also
    implements `IXmlSerializable`, System.Xml.ReaderWriter, not referenced). Likewise `SingletonManager.TryGet<DefinitionManager>`.
    The core generics use `EqualityComparer<T>.Default` instead.
  - **KVM TagSlots (for Task 8):** `DC_Srv_KVM_KvmDrawer_Composite` and `DC_Srv_KVM_KvmScreen_Composite` each tag only
    their animation slot, with `RigidAnimationComponent` (the default tag), so both swaps pass the tag rule.
  - `DcLog.Once` logs one "budget exhausted" line when its 256-key budget fills. The defensive lint is per method:
    every static method with a job-group attribute (a declared `JobGroup` or vanilla's `On<Something>`) and every
    `PostProcess`/`ReProcess`/`Unload` override must have its own `catch (Exception`.
  - `test_build_hides_scripts` has its own marker, `sdkbuild`, and is opt-in (`DC_SDK_BUILD=1`), so a plain pytest
    no longer runs the SDK build. CompileCheck reads the `.vrgproj` Version too, and uses the game's hint names
    (`Simulation/<rel>`).

## Plan 4 Task 3: the Programmable as a functional blade, and the GUID bridge (2026-10-18)

Data only; the same in both script modes. `dc/integration.py` section "Plan 4: Programmable", `dc/scripting.py`,
`dc/script_guids.py`; tests `Tests/test_programmable_data.py` and the Programmable part of `Tests/test_fresh_clone.py`.

| Change | What | Evidence |
|---|---|---|
| P4-2 On/Off (`patch_programmable_functional`) | The structural `CubeBlockComponent` (key `786ef564`) becomes vanilla `PowerableBlockComponent` at the Ruling 15 key `4f2bc5f9`, in both compositions and both prefabs, by the KVM's mechanics (now `onto_powerable`, shared). Tag slots GridBlockComponent / MaxHealthComponent / IBoundsProvider follow it (the same three the structural template points at its CubeBlockComponent, re-derived from the SDK chain by a test). Block definition: rebased from StructuralCubeBlockDefinition (`8a27c509`) onto PowerableBlockDefinition (`794c5233`), `ConsumedResource` null, **GUID `824c6c77` kept**; Density, Fragility, RecipeEfficiency and PCU carried over (the only fields the two template chains resolve differently; a test re-derives them). Prefabs: `PowerableBlockObjectBuilder`, `Enabled: true` (built ON, as vanilla). | `PowerableBlockComponent.cs:236-257, 378-385`; `CubeBlockComponent.cs:3960-3964` (its only dependencies: ChildTransform, Hierarchy); `tools/scripts/block_chain.py resolve` |
| P4-2 Terminal | ControlPanel25's `Terminal` dummy (type `b15d441f`, highlight `TerminalFront`, read from `tools/vanilla-ref`) over the management module only (`functional.PROG_MGMT`: a 0.122..0.212, the full height); aiming at a sled opens nothing. | `UseTerminalAction.cs:37-40` (no Working gate) |
| P4-1 A' scripting (`stage_programmable_scripting`) | `InGameScriptingComponent` in the **server** composition (key `Programmable.ScriptingComponentId`, tag slot `InGameScriptingComponent`) bound to a full `InGameScriptingDefinition` `.def` (vanilla ships none to copy): `EntryTypeName "Program"`, `UpdateMethodName "Update"`, vanilla LocKeys `ProgramableBlockNoProgram` / `ProgramableBlockNoConstructor` / `ProgramableBlockSuccess`, the code-default limits written out. The server prefab holds `InGameScriptingObjectBuilder {Script: the starter program, Running: false}`. | `InGameScriptingComponent.cs:55-75, 173-191`; `InGameScriptingDefinition.cs:401-457`; `MainGameTexts.loc-texts` |
| Server side only (deviation from the brief's "both compositions") | The script editor is the server's (`ProgrammableBlockDetailModelServer`, a replicated `[BlockDetailProvider]` with `[Component] InGameScriptingComponent`), and a client copy would compile and run a saved Running program a second time (`OnAddedToScene`). Vanilla has server-only components too (Timer50's `TimerBlockServerComponent`). | `ProgrammableBlockDetailModelServer.cs:15-16, 197-230`; `ProgrammableBlockDetailModel.cs:20-22` |
| Starter program (`scripting.TEMPLATE`) | `class Program` with a ctor `(Entity)` and `Update()` (the old-signature entry), `using Keen.VRage.DCS.Components` only (the in-game whitelist admits VRage.DCS through `typeof(Entity)`). Its first lines tell the player that Run needs `-loadScripts`. Its in-game compile is a checklist item (CompileCheck compiles mod scripts, not in-game ones). | `OldScriptSignature.cs:41-60`; `InGameScriptInstance.cs:78-106`; `GameApp.cs:465` |
| P4-7 swapper (`patch_programmable_swapper`) | A `BlockMaterialSwapperComponent` in the client composition with our full `BlockMaterialSwapperDefinition`: `WorkingReplacementModels` = our NonFractured and Fractured models, `WorkingReplacementsMeshParts` = `[]`. It maps nothing, so data-only every lamp keeps its authored `EmissiveAmber`. Task 4's client script adds `EmissiveAmber -> EmissiveGreen`. Every amber lamp of the block (LED, LCD status bar, rear PSU lamps) shares that one slot, so they turn green together. | `BlockMaterialSwapperComponent.cs:47-94` (needs `BlockRenderComponent`, no object builder); `BlockMaterialSwapperDefinition.cs:239-279` |
| P4-7 lettering | The management LCD reads `SCRIPT HOST` / `PRG-06` (was `SCRIPTS` / `OFFLINE`), the lamp legend `SCRIPT` / `STATUS` (was `SCRIPT` / `N/A`). Same Keen stencil atlas; the font has no middle dot, so the brief's "SCRIPT HOST · PRG-06" is two lines. Previews: `Source/Model/preview/plan4/programmable_{front,3q,closeup_lcd}.png` (`DC_PREVIEW=plan4`), against `preview/task-8/DC_Srv_Programmable_*`. | `build_report.json` `face.lcd` / `face.lamp_legend` |
| P4-6 GUIDs | `Scripts/Simulation/Shared/DcGuids.g.cs`, written by `build_integration.py` through `script_guids.write()` from the staging and `asset_guids.json` (never minted by the generator; `Kvm.SequencerComponentId` is reserved by `write_all`). `test_script_guids_current` fails when it is stale. | |

**Fix round 1 (review C1, I1, M1, M3, M6).**
- C1: `stage_def` now declares in `$Bundles` every bundle a file's type names use (`declare_bundles`; a new bundle
  gets the current 2.4.0.95, so no migration rewrites our 2.4 object builders). The structural Programmable prefabs
  were the only files whose `Game2:` object builders had no `Game2` bundle ("There is no bundle named Game2",
  `MigrationsHelper.cs:126-147`). `Tests/test_bundles.py` checks every staged and installed asset of every block.
- I1 (merge with the breakable hotfix): `write_all` runs the Programmable patches first, then `make_non_breakable`,
  whose `_drop_key` re-indexes every later `Changed` entry of the compositions and the explicit prefab lists.
  `test_programmable_patches_hold_with_or_without_breakable` stages the Programmable from its fresh clone both ways
  (stripped as today, and kept, for the planned fractured servers) and checks every Insert lands on its key.
  `_swap_component` sorts `Removed` (set semantics) so a re-stage is byte-identical whatever the install history.
- M3: the tag slots `InGameScriptingComponent` and `BlockMaterialSwapperComponent` are ours; vanilla adds the swapper
  with no slot (ButtonPanel250, our door racks). Harmless (free-form slot names on kept ids); kept.
- M6: the empty swapper logs one non-fatal Info line per load, "Model is set, but no meshparts. No swapping will be
  performed" (`BlockMaterialSwapperValidator.cs:11-20`). Expected; not a fault.

**Catalogue:** `DC_Srv_Programmable` is now `functional=True` (its mounts were already the functional servers').
**New asset_guids keys:** `Programmable.ScriptingComponentId`, `Programmable.InGameScriptingDefinition`,
`Kvm.SequencerComponentId`, `def/DC_Srv_Programmable/BlockMaterialSwapper`, `key/DC_Srv_Programmable/swapper`,
`dummy/DC_Srv_Programmable/Terminal`.

**Existing placed Programmables (save migration).** A world saved before this change holds the old
`CubeBlockObjectBuilder` under key `786ef564`. On load the EOB migration removes it and inserts the prefab's default
`PowerableBlockObjectBuilder` under `4f2bc5f9` (and the scripting component's default), so the block loads, but its
per-block CubeBlock state (Color, BuildProgress, HealthIntegrity) resets to the prefab's (painted -> default, damaged
or half built -> whole). Keeping the old key with the new type would take the migration's Replace path instead, which
copies same-named members across assignable OB types and keeps that state (`VRage.DCS/Keen.VRage.DCS.Serialization/EOBUpdateContext.cs:796-806, 857-878`),
but leaves the Ruling 15 key and is unproven for a type change through a Copy delta. The mod is unpublished, so only
test worlds are affected; revisit before publishing if that changes.

**Not verified here (no SDK build in the worktree; the controller builds after the merge):** that the SDK builder
accepts the base-less `InGameScriptingDefinition` `.def` (if it rejects it, construct the definition at runtime in
Task 4 and record that) and the `BlockMaterialSwapperDefinition` `.def`; and everything in game (INGAME-CHECKLIST §12c).

## Plan 4 Task 4: the scripted status lamp, and the read-only scripting check (2026-10-18)

Re-scoped by Ruling P4-1 = A' (the scripting component is permanently in the Programmable's data since Task 3):
**no runtime injection exists.** The brief's `ProgrammableInjector` (Route B) and `ProgrammableTemplate.cs` (the
starter program as C#) are not written: the component and its object builder, with the starter program
(`dc/scripting.py` `TEMPLATE`), are data, and a second C# copy of the program would be a second source of truth.
`Tests/test_programmable_data.py::test_no_route_b_injection_under_a_prime` keeps it that way.

| Part | What | Evidence |
|---|---|---|
| Status slot split (data, both modes) | The SCRIPT STATUS lamp and the LCD status bar (and its LOD2 stand-in, the LCD window quad) move from `EmissiveAmber` to their own slot `EmissiveScriptStatus` (`functional.PROG_LED`), mapped to **the same** vanilla amber `4a74bc1c`. The rear PSU lamps keep `EmissiveAmber` (`functional.PROG_PSU_LAMP`). Data-only the block renders exactly as before; LOD0/1 now use 8 of 8 materials, LOD2 5 of 6; triangle counts unchanged. Model rebuilt headless, exported windowed, placement re-checked (unchanged), re-staged, installed. | A swapper replaces by **mesh part = material slot name** (the door racks map `EmissiveOff`), so only a slot of its own can turn the lamp green without the PSUs (Task 3 concern 4). `test_programmable_status_slot_is_its_own` |
| Why the PSU lamps stay amber | They report the chassis' power, not the script host; a swap that also lit them would claim something the script switch says nothing about. Kept amber (not changed to the fleet's static green) so that the scripts-off block is pixel-identical to Task 3. Changing them to `LAMP_GREEN` like every other server is a one-line data change if the user prefers. | |
| P4-7 lamp (`Scripts/Client/Programmable/ProgrammableLedInjector.cs`) | A client `SimpleDefinitionPostProcessor<BlockMaterialSwapperDefinition>`: for `DcGuids.ProgrammableSwapper` only, it adds `DcGuids.ProgrammableStatusMeshPart -> EmissiveGreen` (`DcGuids.EmissiveGreenMaterial`, looked up through the post-processor's `Manager` as a plain `Definition`, since `TryGetDefinition<T>` hard-casts) to `WorkingReplacementsMeshParts`, recomputes `ProcessedWorkingMaterialReplacements` with the definition's own private `ProcessReplacements`, and sets both through their private setters (REFLECTION). Computed first, assigned last, rolled back if the second setter throws. The vanilla component then applies it on WhenStartWorking and drops it while disabled. Additive only: an existing mapping of the part to another material is left alone (logged). | `BlockMaterialSwapperDefinition.cs:239-299`; `BlockMaterialSwapperComponent.cs:57-94`; `WorkingAttributes.cs:13-37`; `DefinitionManager.cs:992-1003` |
| Game-free rules | `Scripts/Client/Core/StatusLampRules.cs` (Add / AlreadyMapped / Conflict / NoModels / Missing, and a copying `With`) and `Scripts/Simulation/Shared/Core/ScriptingPresence.cs`; `Tests/CoreTests/ProgrammableRulesTests.cs`. | CoreTests `OK: 54 checks` |
| Read-only scripting check (`Scripts/Simulation/Programmable/ProgrammableCheck.cs`) | A `SimpleDefinitionPostProcessor<PrefabDefinition>` that changes nothing: for the server prefab it checks that `DcGuids.ProgrammableScriptingComponentId` holds an `InGameScriptingComponent` bound to `DcGuids.ProgrammableScriptingDefinition` and logs one line (`programmable: scripting available on ...`, or what is wrong). It replaces the brief's "scripting enabled" injection log line. | `PrefabDefinition.cs:224`; `EntityCompositeDefinition.cs:509-516` |
| GUID bridge | `dc/script_guids.py` gains two kinds: `material` (from `dc/material_guids.py`) and `name` (a `const string` from the Python constant that builds the model). New: `DcGuids.ProgrammableStatusMeshPart`, `DcGuids.EmissiveGreenMaterial`. | `test_script_guids_current` |
| Probe | `Source/Model/review/probe_scripts.csx` section 5 (the Programmable on server and client: components, Working, the swapper's mesh parts and processed replacements, the injector's reflection targets) and section 6 (this session's `[DataCenter]` log lines through `Log.Default.FileName`). The KVM part (sequencer, subparts, front-cell door) belongs to Task 8, where the sequencer exists. Not compiled yet (the game was not running). | INGAME-CHECKLIST §12d |
| Previews | `Source/Model/preview/plan4/programmable_scripts_on_{front,closeup_lcd,back}.png` (the status slot lit with Task 6's green indicator stand-in) and `programmable_back.png` (data-only rear). `DC_PREVIEW=plan4 blender -b --python Source/Model/build_dc.py -- DC_Srv_Programmable` | |

CompileCheck gotcha (new): `nameof(BlockMaterialSwapperDefinition.ProcessedWorkingMaterialReplacements)` is CS0012
(its type names `MeshPartMaterialPair` from VRage.Render, which mods do not reference): look such members up by string.

## Plan 4 Task 5: the KVM motion core (game-free) (2026-10-18)

`Scripts/Client/Core/{KvmMotion, KvmMotionTuning, KvmFrontCell, KvmSpawnPolicy}.cs`, namespace `DataCenter.Kvm.Core`;
tests in `Tests/CoreTests/KvmMotionTests.cs` (24 tests); trajectories in `Source/Model/preview/plan4/traj/*.csv`
(`cd Tests/CoreTests && dotnet run -c Release -- --dump ../../Source/Model/preview/plan4/traj`; `--verbose` prints
every check with its measured margin).

| Part | What |
|---|---|
| Model | Per axis, a second-order spring chasing a **lead goal** that eases toward the target at `LeadRatio` (4) x omega. The lead makes acceleration continuous: the drawer spins up over ~25 ms instead of being kicked, and a reversal bends the motion instead of jolting it. |
| Integration | **Closed form** (under-, critically and over-damped, driven by the exponentially moving goal): exact for any step, so 30 / 60 / 144 Hz and jittery frames match 240 Hz within 0.0008. Substeps (`MaxSubstep` 1/120 s) exist only to resolve gates, and gate crossings are split inside the substep (the beat's end exactly; the slide-gate and retract-gate crossings by linear interpolation). No allocation per `Step`. |
| Hard stops | The drawer's rails (0, 1) and the deck under the lid (fold 0) are inelastic stops. The spring aims `StopPreload` (0.02) beyond a stop, so the part lands at a few cm/s and the stop takes it. This removes the critically damped spring's long, invisible creep, which is what makes the budgets reachable. The open lid has no stop: it overshoots ~1.9 % (its detent bounce) and settles. |
| Sequencing | Out: slide; the lid stays flat until `Slide >= FoldGate`, then for `OpenBeat`; then it lifts. Stow: the lid closes; the drawer holds out until `Fold <= RetractGate` (FastStow: `RetractGateFast`), then retracts, latched until the target is Out again. The lift clock keeps running during a stow, so reversing to Out while the drawer is still out lifts at once (no repeated beat). A target change keeps position, velocity and goal. |
| Settle | Within `SnapEpsilon` of the end pose with speed under `SnapEpsilon` x omega (and the goal there): snap exactly and stop updating (`Settled`; a `Step` with the same target is then free). |
| Measured (60 Hz) | Gate at 0.355 s, lift at 0.417 s; open settled at 1.333 s (budget 1.40); close at 1.100 s (1.20); fast stow at 0.567 s (0.60), the same at 30 and 144 Hz within a frame. Peak speeds: drawer 3.97/s = 1.79 m/s; lid 4.15/s open, 3.61/s close; fast stow 6.49/s (2.9 m/s) and 7.21/s. Landings: drawer 0.19/s (8.5 cm/s), lid 0.17/s (17 degrees/s). |
| Tuning vs the brief | `FoldOmegaOpen` 8.5 -> 10, `SlideOmegaFast` 16 -> 18, `FoldOmegaFast` 18 -> 20 (P4-4's ceiling), plus `LeadRatio` 4 and `StopPreload` 0.02. With the brief's values and a 0.001 settle, the open / close / fast stow settle at 1.45 / 1.42 / 0.81 s. |
| Front cell | `KvmFrontCell.Of(min, max, forward)`: inclusive AABB, either order; across the face the centre rounds toward min (floor, also for negative cells); a non-axis forward uses its dominant axis, a zero forward gives the block's own centre cell (never a door). |
| Spawn | `KvmSpawnPolicy.ShouldSnap(age) = age < 1 s` (NaN animates). |

Not yet consumed: `DoorOpenDelay` and `LidAxisSign` are carried in the tuning for the Task 8 sequencer.

## Plan 4 Task 6: the KVM sequence in geometry (2026-10-18)

`Source/Model/dc/kvm_motion.py` (bpy-free) places the motion core's dumped trajectories on the KVM's moving parts and
measures them; `Tests/test_kvm_sequence.py` holds the checks. `subparts.lid_at_pose(dy, deg)` is new and `lid_at(f)`
is now `lid_at_pose(*pose(f))` (output unchanged, tested against a frozen copy).

- **Swept, not sampled.** Each check runs over every 240 Hz interval: the convex hull of a part's poses at both ends
  (for the lid, all four drawer-end x lid-angle combinations), inflated by the rotation sagitta and the
  interpolation slack (|second difference| / 8). GJK hull distances less those pads are lower bounds on the true
  clearance; the instant-sampled distances are upper bounds, and the two agree within 2-3 mm.
- **Part envelopes** are the built subpart boxes (`build_report.json` `subparts.models`), not the design numbers:
  the drawer's pull bar reaches 22 mm past `DRAWER_BOX`, the lid's hooks 6 mm past `LID`. The neighbour servers'
  front is the deepest `clearance.max_y` of any server (the Programmable's lever, 0.420).
- **FoldGate 0.89 -> 0.91.** The smallest slide at which a full lid sweep misses the KVM's own upper panel is 0.8844
  (`min_safe_fold_gate`); 0.89 left 2.6 mm, the rule is 10 mm, 0.91 leaves 11.5 mm. The open now settles in 1.350 s
  (budget 1.40); close and fast stow are unchanged, so nothing was re-pinned.
- **The door race needs no retune (P4-4 holds at 1.0 s).** With the leaves starting 0.1 s before the trajectory's
  t = 0 (0.2 s before the sequencer reacts at t = 0.1), the closest approach is 32.7 mm (rack-frame lower bound;
  drawer vs a leaf at t = 0.325 s). Aligned to the command it is 84.7 mm, and the worst of the reversal sweep's
  FastStow runs is 84.1 mm. The race breaks at about 0.3 s of total lead, or at a 0.6 s door; a normal (non-fast)
  stow loses it.
- **The reversal sweep** (`kvm.reversal_sweep`, `traj/reversal_sweep.csv`): 50 runs, every 0.1 s of an open or a
  close, reversed to Stowed, FastStow or Out. Every run passes the panel, the leaf and the frame / neighbour checks.
- **Known, not the sequence's:** in a top slot the lid's fold arc reaches into the tray / roof band (core Task 8
  concern 7); the motion never rises above the arc's apex (2.5 mm over the 100 degree rest, as data-only). The
  1.9 degree detent bounce brings the lid within 3.8 mm of the Programmable's lever above (13.5 mm at rest).
- **Plan 3 (not in this branch):** the scripted lid sweeps its whole arc with the drawer fully out, so in a full
  rack's top slot it rises above ZT in front of y = 0.600 (to y 0.746, 104 mm above the containment rail's bottom).
  `test_sequence_clears_plan3_roof_and_rail` skips here and will fail after the merge until that is resolved.
- **Fix round 1 (P4-12):** `kvm_motion.motion_path_for_slot(rack, slot)` puts a full rack's top slot on the data-only
  path (under Plan 3's containment rail). Every other slot, and every half-rack slot (no containment there), runs the
  sequence. The checks run per slot on each slot's own path. On the data-only path the top slot clears the rail by
  116 mm and the closing leaves by 86 mm (the script stows along the simultaneous path at the vanilla speed). Its
  panel transient is the accepted 0.1325 m. A decimated (10-40 Hz) test now proves the swept pads keep the bounds on
  the safe side; zeroing the pads, the slack or the sagitta fails it.

## Plan 4: KVM motion (Task 7, the feel review) (2026-10-18)

Ruling P4-11 (feel beats the settle budgets). The Task 5 tuning moved the 0.45 m drawer at 1.79 m/s and swung the lid at
415 deg/s: it read as a snap, not a server-rack drawer. The retune below gives a weighted drawer, a lid with mass and
a felt (not seen) detent, and a deliberate close; the fast stow stays urgent and still beats the closing door at
1.0 s. Renders, videos and charts: `Source/Model/preview/plan4/` (`dc/preview_scripts.py`, `dc/kvm_charts.py`;
frames under `frames/` are not tracked).

| Constant (`KvmMotionTuning.cs`) | Before | After | Why |
|---|---|---|---|
| SlideOmega | 11 | **5.2** | drawer peak 1.79 -> 0.85 m/s: quick start, long soft stop |
| FoldOmegaOpen / FoldZetaOpen | 10 / 0.78 | **6.5 / 0.82** | lid 415 -> 261 deg/s; bounce 1.9 -> 1.06 deg (felt, no wobble) |
| FoldOmegaClose | 10 | **8** | lid down 361 -> 290 deg/s, lands at 17 deg/s |
| SlideOmegaFast / FoldOmegaFast | 18 / 20 | **16 / 18** | fast stow 2.92 -> 2.61 m/s; off the P4-4 ceiling |
| StopPreload | 0.02 | **0.025** | keeps the slower drawer's landing definite (5 cm/s) |
| OpenBeat | 0.06 s | **0.15 s** | a readable beat: the lid starts as the drawer reaches 98 % |
| FoldGate, RetractGate(Fast), LeadRatio | 0.91, 0.02 (0.08), 4 | unchanged | |

Measured (240 Hz dumps; CoreTests `--verbose`):

| | Before | After | Budget (CoreTests) |
|---|---|---|---|
| Open: drawer lands / lid lifts / settled | 0.56 / 0.43 / 1.35 s | 1.13 / 0.93 / 2.35 s | 2.50 s (was 1.40) |
| Close: lid lands / drawer home (settled) | 0.62 / 1.09 s | 0.74 / 1.78 s | 1.90 s (was 1.20) |
| Fast stow settled | 0.554 s | 0.600 s | 0.65 s (was 0.60) |
| Landings: drawer / lid | 8.6 cm/s / 17 deg/s | 5.0 cm/s / 17 deg/s | |
| Door race (leaves 0.2 s ahead, strict) | 32.7 mm | 20.9 mm | >= 5 mm, door 1.0 s |
| Lid bounce vs the server above (slot 2) | 3.8 mm | 8.1 mm | >= 2 mm |

Sequencer changes (`KvmMotion.cs`), both found by the retune:
- **The retract gate also needs the lid on its way down.** `open_fast@1.0` (a door closing just after the lid began to
  lift) started the drawer home with the lid under 8 degrees but still rising by momentum: the swept check measured
  12.5 mm through the KVM's own upper panel. The drawer now waits until the lid's position, rate and lead goal are all
  under the gate and not rising (`LidClear`). A dense 0.01 s reversal scan (740 runs) then gives a worst
  self-intrusion of -2.8 mm (never enters) and a worst door race of 71 mm among the reversals.
- **A part resting on a stop leaves from the stop** (`Axis.LeaveStop`): the preloaded goal is pulled back onto the
  stop when the part is sent away, so the drawer no longer sits pressed into its rail for a few ms (the delay was
  step-size dependent; `kvm.integrator_is_exact` caught it at the slower omega).

Carries settled here:
- **M2** (reverse to Out with the lid half up and the drawer under the gate): unreachable in practice. The drawer only
  leaves its out stop once the lid is under 2 degrees (8 on a fast stow) and falling, and a fast stow is only
  reversed by the door reopening, which takes longer than the stow. No sequencer change.
- **The lid bounce vs the neighbour above:** 1.06 degrees now, 8.1 mm clear (was 3.8 mm).
- `reverse_mid_fold` now reverses at 1.2 s (the lid at 60 %); 0.85 s fell before the lift with the slower drawer.
  The reversal sweep covers 0.1..1.6 s of an open and 0.1..1.8 s of a close (68 runs).

Previews (`Source/Model/preview/plan4/`, KVM in slot 5 of a populated `DC_Rack42_SplitFront`, doors open):
- `kvm_open_{side,3q,first_person,orbit}.mp4`, `kvm_close_{side,3q,first_person}.mp4`,
  `kvm_door_close_while_out_{side,3q,first_person,top}.mp4` (the fast stow against the closing leaves; `top` is a
  plan section), `kvm_reverse_mid_fold_{side,3q,first_person}.mp4`, `kvm_reverse_mid_slide_3q.mp4`,
  `kvm_data_only_top_{3q,side}.mp4` (P4-12, slot 8), `kvm_dataonly_vs_scripted_3q.mp4`;
- `kvm_<run>_3q.gif` and `kvm_<run>_sheet.png` (24 frames over the whole run, time burned in) per run;
- stills `kvm_scripted_{f_gate,f_lift,f_bounce,out}_3q.png`; charts `kvm_timing.svg`, `kvm_motion_graphs.svg`
  (before | after; the pre-retune dumps are kept in `traj_before/`).
- Regenerate: `DC_PREVIEW=plan4 blender -b --python Source/Model/build_dc.py -- DC_Rack42_SplitFront DC_Srv_KVM
  DC_Srv_Compute DC_Srv_Timer DC_Srv_UPS DC_Srv_Storage DC_Srv_Status DC_Srv_Programmable` (about 25 min, 2.9 GB of
  frames, not tracked). `Tests/test_plan4_previews.py` checks every file and each MP4's frame count.

## Plan 4 Task 8: the KVM client runtime (2026-10-18)

`Scripts/Client/Kvm/{KvmSequencerComponent, KvmRackLink, KvmPartComponents, KvmInjector}.cs` (namespace
`DataCenter.Kvm`; split by responsibility in Task 11, see "Plan 4 Task 11"), plus the game-free decisions in
`Scripts/Client/Core/{KvmSequencerCore, KvmMotionPaths, KvmRackSlot}.cs` (CoreTests `runtime.*`). Scripts off: none of it loads and the KVM is exactly the data-only one.

- **Injection, all or nothing (`KvmInjector`).** Three client-side edits: append `KvmSequencerComponent` to
  `DcGuids.KvmClientPrefab` (id `KvmSequencerComponentId`, no definition, null OB); swap the drawer's
  `TranslationAnimationComponent` for `KvmDrawerPart` and the screen's `RotationAnimationComponent` for `KvmScreenPart`
  (same index, same id, null OB). A partial application CAN freeze the KVM (drivers with no sequencer rest at their
  spawn pose), so `CompositionSurgery` now prepares every edit first (`PrepareAdd` / `PrepareSwap`: validated, nothing
  changed; verdict Ready / AlreadyDone / Refused) and `Apply`s a set together, rolling back the applied ones if a
  later one throws. Any refusal applies nothing: the KVM keeps the whole vanilla motion. Two post-processors (prefabs,
  composites) run the same idempotent routine, because a definition reload re-runs only the reloaded type's
  post-processors; `PrepareAdd` also repairs the "one long" reload case (the prefab kept the sequencer's OB slot, the
  composition lost the component). The remaining partial state (vanilla parts beside a sequencer) animates data-only.
- **P4-10, own definition types.** `KvmDrawerPartDefinition` / `KvmScreenPartDefinition` are built in code from the
  data's Translation/RotationAnimationDefinition (GUIDs checked against `DcGuids.KvmDrawerTranslationDef` /
  `KvmScreenRotationDef`) and put in the swapped slot. The game's Library generator makes every `Definition` subclass
  a serializable named type, so they are `[Serialize] partial` with a parameterless constructor (VRG1006 / VRG2006
  otherwise); the generated object builder is never used. `Tests/test_kvm_runtime.py` fails if any script component
  declares a vanilla definition type.
- **The target rule (`KvmSequencerCore`):** faulted → snap to the wanted end pose every frame; door Closing/Closed and
  not home → FastStow; Working and (no door, or Open for `DoorOpenDelay`) → Out; else Stowed. Scene entry (the first
  `KvmSpawnPolicy.SceneEntryWindow` = 1 s in the scene, paused time not counted) shows the end pose at once, including
  late answers (a rack that streams in a few frames later) and a door already open (no delay): **the load bug is
  fixed**. Subparts spawned later (a weld finished during play) restart stowed and animate.
- **P4-12 at runtime (`KvmRackSlot`, `KvmRackLink`).** The block in the cell in front of the face is the rack (its
  front/rear layers are occupied cells). Its block definition GUID (`DcGuids.Rack{42,24}{Open,SplitFront,SplitFrontRear}Block`,
  generated) gives Full or Half; its AABB and Up give the KVM's slot. Data-only exactly in a Full rack's slot 8;
  sequenced everywhere else (Rack24's top slot included). CoreTests dumps the rule (`preview/plan4/traj/routing.json`),
  and `test_kvm_runtime.py` holds it to `kvm_motion.motion_path_for_slot` for all 6 racks. The data-only path
  (`KvmLinearMotion`) is the data's own linear simultaneous motion, un-eased; its dump (`data_only_open.csv`) equals
  `kvm_motion.data_only_trajectory`, so Task 6's top-slot clearances hold for what runs. A path change waits until the
  motion is settled (no jump).
- **Rack link caching.** Full lookup every 0.5 s; every frame a cheap identity check (the KVM's grid, the block in the
  cached cell, that block's CubeBlockComponent) re-resolves at once when the cached block left. Entities are pooled
  stubs, so a held reference alone proves nothing.
- **Defensive.** Every job, scene listener and post-processor catches; faults log once per site. At 3 faults the
  sequencer stops sequencing (snaps; once faulted, a world read that throws is not retried) and a part rests at its
  spawn pose. A part with no sequencer above it writes its rest pose once. Part drivers write only when the pose
  changed. Jobs: `KvmSequenceUpdate` (after OnStartRigidAnimation, before OnPrepareRigidAnimation), the parts in
  OnUpdateRigidAnimation.
- **Multiplayer, mixed script settings.** Client-only: the server never has these types and nothing is replicated.
  Each client animates its own copy from replicated state (Working, DoorState). A client with scripts sees the
  sequenced, door-aware KVM; one without sees the vanilla motion of the same block (it may poke through closing doors
  for a moment). Cosmetic only: the subparts have no collision. A dedicated server is unaffected.
- **Fix round 1 (review 2026-10-18):**
  - **`Entity.Has(out T)` needs a conditional for a Component type.** Without one it asserts "Use of Entity.Has is
    reserved for interfaces or with conditional!" (`Entity.cs:158`; VRage.DCS is built with FEATURE_ASSERTIONS, so it
    fires in shipping builds: an exception every lookup, or an assertion report at exit). Pass an always-true one,
    the vanilla idiom (`ThirdPersonCameraComponent.cs:295`). `Tests/test_scripts_layout.py::test_no_bare_entity_has`
    fails on any `.Has(out x)` without a second argument.
  - **Ruling P4-13, the face side.** A rack's door guards only the sides its leaves are on: `door_sides` from
    dc/doors.py, generated as `DcGuids.Rack*DoorSides` (bit 1 = front = the block's Forward, bit 2 = rear). A KVM
    facing a side without leaves ignores the door (a rear-facing KVM in a SplitFront rack deploys, as with scripts
    off); a sideways face (unknown) still waits. Rule: `KvmRackSlot.FaceSide` / `DoorGuardsFace` (CoreTests
    `runtime.door_face_side`); the mapping is tied to the data by `test_door_sides_follow_the_data`.
  - **A refused reload can leave earlier edits in place** (review M3): on a reload, verdicts such as {AlreadyDone,
    Refused, AlreadyDone} apply nothing new and roll nothing back, and `KvmInjector.State` then reads DataOnly although
    the sequencer and one driver stay. Not frozen (the vanilla part animates through FBAC, the driver through the
    sequencer); reloads happen only in development. Accepted and recorded.
  - A part that finds no sequencer keeps looking every 30 frames (it used to rest for good).
- **Analyzer warnings kept:** KN041 ("must have suffix Component") on `KvmDrawerPart` / `KvmScreenPart`, the names the
  plan's interface fixes; KN026 as elsewhere (Task 11 removed every KN023).
- **In-game:** `probe_scripts.csx` section 7 (state per KVM, the parts against their rest poses, save safety, the
  surgery refusal paths prepared-only, and the opt-in fault pass 7d); INGAME-CHECKLIST §12e.

## Merge main (cable trays T9b-T11) into plan4-scripts (2026-10-18)

- The Programmable is now breakable (main, Task 9b: real Fractured and Damaged models, `ensure_breakable`, critical
  `Fracture_01`) AND keeps the Plan 4 data (the server-side scripting component, the client swapper, the Ruling 15
  On/Off chain, the `EmissiveScriptStatus` slot). `write_all` runs the Programmable patches first, then
  `ensure_breakable` (or `make_non_breakable` for the four tray exceptions).
- `fracture.DAMAGED_SLOTS` maps `EmissiveScriptStatus` to `EmissiveOffBroken`, like every other emissive slot.
  The swapper still lists NonFractured and Fractured only.
- `test_programmable_patches_hold_with_or_without_breakable`: its non_breakable run now forces the Programmable
  through `make_non_breakable`. The breakable run is the shipped path.
- Generated files were taken from main, then regenerated:
  - the Programmable re-exported windowed, so all three models carry `EmissiveScriptStatus`;
  - check_placement unchanged;
  - re-staged and installed; the dry run then shows 0 changes.
- The KVM's auto-merged compositions had the BreakableBlockComponent both kept and Removed. Main's copies were
  restored and re-staged.
- The in-game checklist renumbers Scripts to section 12 (Cable trays keep 11) and adds a damaged-Programmable item.

## Plan 2 Task 10: visual-improvement pass (2026-10-18)

The audit, with its findings ranked and an evidence shot per finding: `Source/Model/review/plan2-visual-audit.md`. The renders are in `preview/p2-task-10/` (`before/`, `after/`, `pairs/`, plus the contact and reference sheets from `p2t10_sheet.py`).

Every part added has a purpose:

- **Cable-end caps** (`tray_kit._cable_cap`): a cut cable is solid, so the end of a run shows the bundle's section, not a hollow sweep.
  - The caps sit 1.5 mm inside each port plane, so at a joint they are buried in the continuous strand skin.
  - They are LOD0 only, and every piece has them except the four budget-bound Full pieces (`tray_xsec.CAP_SKIP`).
- **Breakout tie** (Tee, Moderate and Full; `tray_bends._breakout_tie`): installers tie a fan-out where a branch leaves its run, here 0.12 m past the M0 split collar.
- **Landing seat** (`tray_plan.ENTRY_SEAT = 0`): the landing collar and the Chute's foot and top plates bear on what they land on. They sit on their ENTRY plane, and the rack's own 1 mm `ENTRY_DROP` keeps the faces apart.
- **Removed:** the Full Drop's split collars are not drawn. They are hidden inside the dressed top layer (P2-25, −400 tris). The plan keeps them.
- **Rod-hanger icons:** rendered brighter (`ROD_ICON_EXPOSURE`).
- **Round 2 (P2-28, P2-29):**
  - Every piece is capped (`CAP_SKIP` is empty; the cap triangles sit outside the plan's LOD0 budgets).
  - The LOD0 strands shade by their own radial normal through the opt-in per-loop normal hook of `tools/se2model` (`normals.py`, `objects.apply_loop_normals`), so the lay no longer bands.

## Plan 2 summary: cable trays (2026-10-18, Task 11)

Plan: `../../docs/superpowers/plans/2026-10-17-data-center-cable-trays.md`; ledger and per-task reports: `../../docs/superpowers/sdd/data-center-cable-trays/`. The in-game list and the rulings for you to confirm are in INGAME-CHECKLIST.md section 11.

### The family

38 blocks: 7 shapes x 4 densities (StraightS, StraightL, TurnH, TurnUp, TurnDown, Tee, Cross; Empty, Low, Moderate, Full) = 28, plus Drop x3 (Low, Moderate, Full), Reducer x3 (Full to Moderate, Moderate to Low, Low to Empty), Chute x1 and Rods x3 (0.25, 1.0, 2.0 m). One style (wire basket; `tray_plan` keeps a `style` argument). Clone sources: WallInsertPipes (all except rods), StructuralSupportStraight (rods). PCU 5, `AutoRotateFace: null`.

### Build menu and costs

Subcategory "Data Center": groups "Cable Trays: Empty / Low / Moderate / Full" (Order 300..600) and "Cable Tray Supports" (700). Costs (P2-26) scale with run length: one unit (1 Steel Plate + 1 Construction, plus 1 Steel Plate optional) per 0.5 m: Short 1, Long 3, Turn 2, Cross 4, Drop and Reducer 2, Rods 1/2/3 Steel Plate. Details in the Task 9 section.

### Contract summary (`dc/tray_lanes.py`, `dc/tray_plan.py`, `dc/tray_bends.py`)

- Joint rule: ports join when their origins coincide, their normals are opposite and their floor normals are equal ("floor to floor"). Mirror-symmetric lanes, so one block serves either hand and either direction.
- Lanes nest: Empty = none, Low = data L1+/-, Moderate adds fibre M0 and power M2+/-, Full adds data F1+/- and black power F3+/-. Data bundles are the paintable `PaintedMetalColorable`; fibre is yellow, power grey and black.
- The basket and hardware are fixed BrushedMetal and not paintable (P2-21). The Tee is a real tray tee (P2-18).
- Racks: tray centreline +0.125 m in front of the rack centre, bottom plane 0.5 m above the full-rack top; waterfalls land in top-entry brush plates (Task 1) over the front managers.
- Proved offline: every port pair joins in both 180 degree variants, density nesting, reducer chains, vertical jogs, built-mesh bundle clearance and port positions.

### Rulings (Plan 2)

P2-1 one style; P2-2 38 blocks; P2-15 catalogue gating; P2-16 split-collar contact widened; P2-18 real tray tee; P2-19 bend radii 0.05 m smaller; P2-20 junction walls step down to 0.10 at the ports; P2-21 fixed silver basket; P2-22 3-LOD chains; P2-23, P2-25, P2-28 LOD0 budget overages (TurnH Full 4512, Drop Full about 6050, caps on every piece); P2-24 flush struts on TurnUp/TurnDown; P2-26 length-scaled costs; P2-27 fracture models; P2-29 radial-normal hook in `tools/se2model`.

### Known limits

- Not seen in game yet: placement, snapping, auto-rotate, the LOD pops, fracture and damaged models, the Chute and rods, costs.
- Tray steel is not paintable; only the data cables take paint.
- Four blocks are non-breakable: the three Hanger Rods and the Chute (disjoint members; Havok connects fracture colliders only within 0.1 m).
- A mixed-density joint ends the extra lanes at the port; a Reducer is the tidy way to step down.
- No cabling inside the racks' vertical managers (the waterfall ends at the brush plate); an option for Plan 3.
- The Damaged models are capped at 2x their Fractured model's triangles (Task 9c).
- Rack subparts (door leaves, side skins, fan tray) are not fracture zones: they stay when the column under them breaks.
- Save compatibility (Task 9c): the server and rack fracture zone ids changed (6U servers: 01 is now the core, 03 the
  rear; racks: 8 / 4 new zones). Damage stored in a pre-T9c save maps onto different zones, or is dropped for ids that
  no longer exist (BreakableBlockValidator V8). Acceptable: the mod is unpublished.
- A rod hanger may stack on another (the Up hints repeat the coupler rectangles).
- Rod icons read as two hairlines at 64 px.

## Plan 3 Task 1: room interface, containment rails, PDU columns, label pads (2026-10-18)

The room interface lives in `dc/dims.py` (`RF_H`, `RF_TILE`, `RF_DECK_T`, `AISLE_WIDTHS`, `CONTAIN_RAIL_Y`,
`CONTAIN_RAIL_DZ`, `ROOF_CLEAR`, `PDU_COL_X/Y`, `PDU_ENVELOPE`, `PDU_RECEPTACLE`, `LABEL_X/Y`, `ROD_PLATE`). The build
measures it back (`build_report` `geometry`: `contain_rails`, `pdu_receptacles`, `pdu_envelope_clear`, `pdu_band`,
`up_mount_rects`, `down_mount_rects`; `placement.faces[*].plane_groups`); `Tests/test_room_interface.py` checks it.

- **PDU envelope (measured on the built LOD0):** the largest box in the rear column clear of the frame over the slot
  band: x 0.292..0.420 (2 mm outside the 19" rail's outer face 0.290; 2 mm inside the corner post's inner face
  0.4225, which also clears the side casing 0.432 and the hinge brackets from 0.440), |y| 0.377..0.596 (2 mm behind
  the PDU bulkhead face 0.3745; 2 mm inside the frame plane YK 0.598, so 4 mm from the rear leaves' back face 0.600).
  128 x 219 mm. The alternative (x to 0.428 under the post, |y| to 0.521) is smaller (136 x 144 mm).
- **PDU band** (`rack.pdu_band`): local z 0.25 .. ZT on the full rack; on the half rack 0.25 .. H - CAP (1.13): its
  top corner caps (0.12 m armour) and the roof rail reach into the column's top cell, so the 24U strip stops under
  them. The count includes the RackSide subpart (both placements).
- **Rear PDU strips reconciled:** visual pass 2's built-in rear strip + cord bundle (`_rear_pdu`) and the rear finger
  combs are REMOVED. The column is free (`FREE_CELLS`) for the Plan 3 Task 7 zero-U strip blocks (Feed A = +x, B =
  -x); a strip baked into the rack would sit inside every placed strip. The side columns' physics boxes start at
  y = -SLOT_HALF_D. The rear opening of an empty rack now shows the bulkhead, its keyholes and the FEED plate.
- **Directions:** every rack's staged block definition says `MountPointGeneratorSettings.Directions = "All"`
  (`integration.RACK_MOUNTS`; the open rack's cloned wall panel had no Forward; the door template already resolved
  to All).
- **Costs:** the open 42U rack's occupancy falls 152 -> 136 cells, so its recipe is one SteelPlate lighter.
- **Part -> purpose:**

| part | purpose |
| containment rail (Colorable box rail, two lips round a Darker clamp channel, full racks front + back, z ZT+0.170..0.238, |y| 0.600..0.624) | aisle-containment roof support: the roof panels' edges bear on it (real racks take containment brackets on top) |
| clamp pads (Darker, every 0.25 m) + MetalDull clamp screws on top | where the roof panel clamps grip, one per mount cell |
| Darker standoffs (rail to the tray header) | carry the rail clear of the header, label and lamp |
| Yellow "CONTAINMENT" tag in the channel | marks the rail as the containment interface |
| PDU bulkhead (Colorable, the column's back wall on the bracket plane y = -0.375) | the zero-U PDU's mounting face: keyhole slots (one per slot) take the strip's buttons |
| FEED A / FEED B plate (Darker, white stencils) | which feed the column carries (A right, B left from the hot aisle) |
| plinth receptacle (Darker gland plate, Yellow coupling ring, 5 MetalDull contacts, 2 screws, feed letter) | the PDU's power feed: the strip's inlet plug seats in the twist-lock socket |
| cleared rear column | the zero-U PDU mounting space |
| top rims (full rack rim hints; half rack `top_front` / `top_back` over its roof headers) | rack label and accessory mounting (`LABEL_X x LABEL_Y`) |

- **Hints:** `contain_front/back` (full racks: the only Forward / Backward mounts on the box planes), `pdu_seat_A/B`
  (plinth top under each column), `pdu_bracket_A/B` (the column's rear face, inner Backward mounts), half rack
  `top_front/back`.
- **Exported + fractures:** the 42U front / back rail band splits into 3 groups by fracture zone (tray / columns);
  coverage is unchanged (4 cells).
- Placement summaries after Plan 3 Task 1 (`test_rack_unchanged_except_entries` reads the LAST line per rack):

DC_Rack42_Open: groups F/B/L/R/U/D = 1 / 3 / 4 / 4 / 5 / 4; plane coverage = 10% / 10% / 84% / 84% / 40% / 100%; occupied 136/200 box cells, 64 empty, 0 outside
DC_Rack24_Open: groups F/B/L/R/U/D = 0 / 2 / 3 / 3 / 7 / 1; plane coverage = 0% / 0% / 84% / 84% / 60% / 100%; occupied 68/100 box cells, 32 empty, 0 outside

## Plan 3 Task 2: room catalogue, clones, the room layout and the preview room (2026-10-18)
- **Catalogue:** 19 room blocks in `catalog.ROOM` (families in `ROOM_FAMILIES`: floor, crac, pdu_cabinet, pdu_strip,
  contain_door, contain_roof, sign). They are in `CATALOGUE`/`BY_NAME`, NOT in `PIPELINE_FAMILIES`: each family joins
  the pipeline (staging, menu, icons, recipes) in its own definitions task, as the trays did in Plan 2 Task 5.
  `build_dc.BUILDERS` maps every room family to `_not_yet` (raises `NotImplementedError(family)` before anything is
  built); each task swaps in its builder.
- **Names:** `names.NAMES` covers the whole catalogue (`test_names_for_every_block` now compares with `CATALOGUE`).
- **Clones:** all 19 cloned (`.clonemap.json`). `clone.ALSO`: `CatwalkSquareBase_250` (P3-17), `NarrowLCD50` (P3-18),
  and for Gyroscope250 only the space-dropping rename: the CRAC's powerable definition is
  `DC_CRAC_PowerableBlockDefinition.partialdef` (the vanilla name has a space; P3-15). Its generic subpart files
  (`S1..S3_ModelComponentDefinition`, `S1..S3RotationAnimation`, `SubParts.def`, `SubpartMarker.def`) keep their names;
  `DC_CRAC_GyroscopeDefinition.partialdef` is still there for T6 to drop. DeckPanel250 has no second prefix.
- **Worktree-safe cloning:** `clone._copy` now runs se2mod's own `cmd_copy` in-process with its mod lookup pinned to
  `config.MOD_DIR`. The CLI resolves the mod by name under `mods/` (= `mods/DataCenter`), which from a worktree would
  have written into main. se2mod.py itself is unchanged.
- **Unwired clones are in Assets:** until each family's task, a room clone is a vanilla copy (vanilla models, own
  kind in no menu group, not unlocked). The CRAC clone still carries the gyro component until T6 strips it.
- **Materials:** `FrostedGlass` and `WindowGlassThin` in `material_guids.py` (P3-19).
- **Room layout (`dc/room.py`, pure Python):** world = Blender axes, aisle centred on y = 0, z = 0 on the deck.
  `Placed(name, origin, yaw, tag)`; `world_cells`, `occupied`, `conflicts`, `pure_report` (racks: `rack.FREE_CELLS`;
  trays: the cells their cable plan leaves empty, which is what lets the rack label stand between a Drop's two
  waterfalls). Row = A1 A2 CRAC A3 A4 PDU (PDU cabinet at the east end); row A at y < 0, B at y > 0; the door is
  the 0.25 m slice beyond each row end, yaw 1 / 3 (front out of the aisle), its sign in the next slice on the
  header band; roofs one per 1.0 m; the hanging sign mid-aisle at tray height on a turned Rods_100; ceiling 4.50 m.
  Perforated tiles along the rows only: in the cold aisle, or in the walkways for a hot aisle.
- **Preview room (`dc/preview_room.py`):** `room_scene`, `CAMERAS` (aisle_eye, door_outside, overhead, rack_top,
  photo1, end_row), `render_task`. Built blocks are real, unbuilt ones ghosts in their exact boxes. The hall's
  lights: suspended linear luminaires (`LUM_W` 32 W area lights) over the aisle and walkways, plus a soft fill
  under the roof plane standing in for the roof's LED strip (`ROOF_W`); T4 may make that strip real.
  Sheets: `python3 Source/Model/room_sheet.py` (plan + section per width and aisle, and the contact sheet).

## Plan 3 Task 3: raised-floor tiles (Solid / Perf x 0.5 / 1.0 m) (2026-10-18)
- **Builder:** `dc/floor.py` (`build`, `collision`, `tiles`, `lines`, `pedestals`, `screws`); `build_dc.build_floor`
  measures `geometry` = `deck_top_z`, `seam_inset`, `internal_seam`, `lip_reach`, `under_clear`, `up_mount_rects`,
  `down_mount_rects`. Every block is a grid of identical 0.5 m tiles (1 or 2 x 2), so mixed floors read as one grid.
- **Heights:** deck top 0.5 mm under the cell-top plane (`DECK_TOP` 0.1245 in the block frame), `RF_DECK_T` 32 mm deep;
  a rack's feet (its lowest vertex on its bottom plane) stand 0.5 mm over it at any seam offset (`test_floor_under_rack_plinth`).
- **Seams:** every tile's top edges stand 1 mm in (2 mm hairline, the same inside a 1.0 m block as between blocks). A
  3 mm Darker seal pan under each tile reaches the tile edges exactly: it closes the seam against plenum air bypass,
  and it makes the measured LOD0 bounds 0.5 / 1.0 m (with the deck 1 mm in, the 0.5 m block measured 0.498 m and
  Keen's checker would drop to the small-model material table: 4 / 3 / 1). Its outer faces are the only geometry on a
  shared plane; neighbours' faces there are back to back and hidden.
- **Pedestals:** a grid of `lines()`: 0.10 m in from each block edge, and ON every internal tile seam (shared, as a real
  floor): 4 in the 0.5 m block, 9 in the 1.0 m. Base plates 0.12 m (40 mm from the side planes) carry the Down mount
  hints: all 4 bottom cells of the 0.5 m block mount, the 4 corner cells of the 1.0 m block. Each tile's 4 screws sit
  over a pedestal head (on the head centre at a block edge, 28 mm toward the tile on a shared head).
- **Part -> purpose:**

  | part | material | purpose |
  | --- | --- | --- |
  | top skin (two plates, panel line) | Colorable | walking surface and rack load; takes the paint |
  | edge trim with corner gussets | Darker | the tile's load frame |
  | seal pan / core | Darker | closes the seam (bypass air); the lift-cup floors |
  | lift-cup spots (2 per tile) | recess | a suction lifter grips there to lift the tile out |
  | hold-down screws (4 per tile) | Darker | fix the tile to its pedestal heads |
  | perforated insert | MetalPerforationSteel | cold-air supply from the plenum |
  | slotted damper plate | Darker | meters the airflow (bars seen through the holes) |
  | slotted adjuster spindle | Darker | turns the damper from above with a key |
  | AIRFLOW stencil + Yellow arrow | CleanWhite / Yellow | which way to turn to open |
  | pedestal: base, anchor bolts, tube, jack, lock nut, head | MetalDull | carries the deck; the jack sets the height, the nut locks it |
  | gasket pad on each head | FracturedMaterial01 | hidden under the deck; the torn bond once the deck breaks off |
  | stringers | Brushed | lateral bracing between the heads |
  | earth strap (clamp, braid, lug), one per block | MetalDull / Brushed | bonds the floor grid to earth |

- **Breakable (user direction), not the plan's "unfractured" (P3-10):** two physics boxes = two fracture zones,
  deck (Fracture_01, from the deck's underside up) and understructure (Fracture_02). The plan's physics budget for
  the floor was 1 box; 2 boxes cover exactly the same cell box. Materials are kept apart per zone, so the Fractured
  model has <= 8 mesh parts (Perf: 5 deck incl. the hidden stencil + 3 under; Solid: 2 + 3). The catwalk clone keeps
  its BreakableBlockComponent; `make_non_breakable` does not run (`keeps_breakable`: 2 zones). `export_models.
  UNFRACTURED_FAMILIES` is unchanged. Vanilla `FracturedMaterial01` (`material_guids`) on the gasket pads only.
- **Staging ahead of the menu:** `catalog.STAGED_ROOM_FAMILIES = ("floor",)`, `catalog.STAGED` = BLOCKS + those room
  blocks; `integration.write_all` / `built_names` use STAGED, the menu, icon and recipe loops keep BLOCKS. A staged room
  block gets our names on its cloned kind (still in the vanilla Catwalks tile), no recipe patch and NO initial unlock
  until Task 10. `integration.floor_patch`: PCU 5, mount directions All. The floor's cloned model definition gets the
  centred ParticleEffects dummy (`patch_effects_dummy`, as the rod hangers).
- **Budgets (LOD0..3 tris / materials):** Solid_050 2496 / 312 / 84 / 12 (5, 4, 3, 1); Perf_050 2985 / 422 / 106 / 12
  (8, 6, 4, 1); Solid_100 6436 / 940 / 244 / 12; Perf_100 8332 / 1380 / 332 / 12 (67 % of 12499 on LOD0).
- **Provenance:** all geometry generated; vanilla materials only (MetalPerforationSteel, FracturedMaterial01, the
  CleanWhite glyph atlas).
- **Previews:** `DC_PREVIEW=plan3-t3` (`dc/preview_p3t3.py`) into `preview/p3-task-3/`; contact sheet
  `python3 Source/Model/p3t3_sheet.py`.

## Plan 3 Task 4: containment roof panels (1.0 / 1.5 / 2.0 m aisles) (2026-10-18)
- **Builder:** `dc/contain.py` (`build`, `collision`, `edge_mount_rects`, `bays`, `pane`, `mullion_ys`, `clamp_xs`);
  `build_dc.build_contain_roof` measures `geometry` = `underside_z`, `top_z`, `frame_underside_z`, `x_extent`,
  `y_extent`, `edge_mount_rects` (per edge: +-y over x, +-x over y), `clamps` (per long edge: centre x, face y, z span),
  `led`, `pane_top_z`, `top_band_max_inset`, `bays`, `zone_split_z`. Block frame: x +-0.5 (one rack pitch along the
  row), y +-W/2 (across the aisle), z +-0.125 = the racks' ZT .. rack top.
- **Couplings (Tests/test_containment.py, on the measured racks placed by room.reference_room):** the +-y edge mount
  hints lie on the racks' faces and overlap their contain_* rail band over the full 1.0 m and 0.226 m in z; the
  clamps' faces stand 1 mm inside the roof's planes, so 2.2 mm from the rail pads (pads 1.2 mm inside the rack's);
  one clamp per rail pad (`rack.CONTAIN_PADS`, x = +-0.125, +-0.375). Caps 0.5 mm under the rack-top plane (flush);
  render x +-0.499 = the rack's, so a run at 1.0 m pitch leaves a 2 mm hairline (gaskets 1 mm inside each plane).
  The underside (bolt heads) is 143 mm over ZT: a popped KVM in the top slot and the rack doors (any angle) stay
  under it (`test_roof_clears_kvm_and_rack_doors`).
- **Up-face rule:** the top is flush, but nothing may mount on Up (or Down). Keen's mount generator counts a cell when
  >= 4 of its 8 rays (ring radius 0.0825 m) hit within 20 mm of the plane. Every top member therefore stays within
  `RAY_FREE` = 48.8 mm of the cell plane it sits on (long caps 36 mm, end caps 38 mm, mullion caps 48 mm wide over
  cell boundaries: the mullions are every 0.5 m), and the panes' top is 23.5 mm under the plane. Measured: Up 0 / Down
  0 groups; each edge 1 group, 100 % (also with the fracture hulls).
- **Part -> purpose:**

  | part | material | purpose |
  | --- | --- | --- |
  | perimeter beams (long + end), chamfered underside | Colorable | carry the panes from rail to rail |
  | cross mullion (x = 0), long mullions (every 0.5 m) | Colorable | split the glazing into 0.5 m bays (a pane one crew member lifts out) |
  | glazing caps over every member | Colorable | retain the panes from above (the top seen from the tray deck) |
  | panes, one per bay | FrostedGlass | close the aisle (the air stays in) but let the hall light through |
  | rail clamps (L: jaw + flange), one per rail pad, 2 bolts | Darker / MetalDull | grip the rack's rail pads: the panel cannot lift or slide along the row |
  | bulb gaskets on both short edges | Darker | seal the joint to the next panel or the door header |
  | corner gussets under the frame, 2 bolts | Darker / MetalDull | keep the welded frame square |
  | per bay: 2 drop ledges + latch bar + fusible link + lug | MetalDull | FIRE RELEASE: the pane's end rests on hinged ledges held up by a fusible link; when it melts the pane swings down and the sprinklers reach the racks |
  | FIRE RELEASE tag under the end beam (per bay) | Darker + CleanWhite stencil | tells the crew what the link is (reads from below) |
  | LED batten under the cross mullion (housing, end caps, screws, feed gland) | Darker / EmissiveWhite / MetalDull | lights the contained aisle (a roof shades the hall luminaires): one batten per rack pitch |
  | glazing beds on every member | FracturedMaterial01 | hidden under the caps; the torn bond once the glazing breaks off |

- **Drop side:** the panes rest on the long beams and mullions under the caps' lips (7 mm), but stop 3 mm short of
  the end beams, where they sit on the drop ledges: the end caps have no lip, so a released pane is free to swing
  down about its mullion edge. That is why the release hardware is on the end beams.
- **Breakable (user direction, not P3-10's "unfractured"):** two physics slabs = two fracture zones, split at the
  panes' bed `ZS` 0.096: Fracture_01 glazing (panes + caps: FrostedGlass, Colorable), Fracture_02 frame (Colorable,
  Darker, MetalDull, FracturedMaterial01 + _Hide: the stencil and the EmissiveWhite diffuser). Every Darker /
  MetalDull face stays under ZS (the clamp jaws stop at ZS - 0.5 mm), so the Fractured model has exactly 8 mesh
  parts. The DeckPanel250 clone keeps its BreakableBlockComponent (`keeps_breakable`: 2 zones);
  `test_definition_validators.py` passes with it. Physics boxes 2 (the plan's roof budget).
- **Materials:** `EmissiveWhite` (8ffced10, vanilla static white emissive, as HangarDoor_Base.model maps it) added to
  `material_guids`; FrostedGlass (P3-19) carries the panes. The roof is not powered (DeckPanel250 is decor), so the
  LED is always lit, like vanilla's hangar-door light strips.
- **Staging:** `catalog.STAGED_ROOM_FAMILIES` += `contain_roof` (no menu / unlock / recipe until Task 10, kind keeps
  the cloned DeckPanel tile). `integration.roof_patch`: PCU 5, mount directions All, and the cloned
  DeckPanel250_PlacementDefinition with `AutoRotateFace` null (the deck's "Down" would flip a panel aimed at a rail).
  The centred ParticleEffects dummy is added (`patch_effects_dummy`, as the floor and rod hangers); the clone's
  ParticleDirection dummy already sits at our block centre (0.125, 0, 0.125).
- **Budgets (LOD0..3 tris; materials 7 / 5 / 4 / 1):** 100: 3352 / 992 / 276 / 12 (27 % of 12305); 150: 4156 / 1272 /
  324 / 12; 200: 4960 / 1552 / 372 / 12 (38 % of 13042).
- **Provenance:** all geometry generated; vanilla materials only (FrostedGlass, EmissiveWhite, FracturedMaterial01,
  the CleanWhite glyph atlas).
- **Previews:** `DC_PREVIEW=plan3-t4` (`dc/preview_p3t4.py`) into `preview/p3-task-4/`; contact sheet
  `python3 Source/Model/p3t4_sheet.py`. The reference room now lights the aisle with each built roof's own LED
  batten (`preview_room._roof_leds`, an area light under every diffuser) instead of T2's stand-in fill; the
  FrostedGlass stand-in (`preview_mats` "Frosted") fakes the transmitted hall light with a little emission.

## Plan 3 Task 5: containment end-of-aisle sliding doors (1.0 / 1.5 / 2.0 m aisles) (2026-10-18)
- **Builder:** `dc/contain.py` door section (`build_door`, `build_leaf`, `door_collision`, `door_leaves` -> `Leaf(name,
  model, side, closed, open)`, `leaf_box`, `leaf_boxes`, `detector_box`, `back_mount_rects`, `header_rects`,
  `pocket_x`, `use_box`); `build_dc.build_contain_door` builds the frame (fit_lods) and the two leaf subparts
  (`build_generic_subparts`) and measures `geometry` = `frame_min_y` / `frame_max_y` (the mounting faces stay 1 mm
  inside), `frame_min_z`, `header_underside_z`, `opening_clear`, `back_mount_rects`, `header_rects`, `pocket_x`,
  `travel`, `leaves` (per model: measured bounds, collision box, closed / open AABB). Block frame: x across (2W,
  opening |x| <= W/2, pockets W/2..W), -Y = the row-end plane (the aisle side; the end racks' side panels behind the
  pockets), +Y = the room, z = -1.25 the floor top .. +1.25 the rack tops; the header is ZT..H = the roof band.
- **Mechanism (vanilla, read-only check of the decompiled 2.4 code):** `DoorBlockColliderDefinition.
  CollectDoorLeavesColliders` walks `SubPartsProvider.GetDoorSubParts()` (= the ConditionalSubParts prefabs), and for
  every prefab whose composite has a `DoorSegmentTransformSLERP` AND a `ModelComponent` with a non-null `Collider` it
  adds that collider at the block model's `ClosedPositionDummy`; `DoorBlockColliderComponent` compounds them with the
  frame collider only while `DoorState == Closed` and the block is Functional (mid-travel and open: frame only). The
  collider comes from the leaf `.model`'s `CollisionShapesAsset` (vanilla: `NarrowSlidingDoor_LeftDoor.hkt`). So
  `export_models.export_subparts` now takes `collision={sub: [boxes]}` and writes `<name>_<sub>_collision.gltf/.bin`
  (one box per leaf, exported like a block's collision), and `integration.subpart_model_asset(geom, collision_guid)`
  references it. Leaves are therefore REAL obstacles when closed (P3-2 holds; unverified in game).
- **Motion (P3-16):** each leaf is W/2 + 30 mm wide (the overlap split 15 mm per side: 15 mm past the centre line,
  15 mm behind its post); closed the leaves meet at x = 0 with shiplap (rebated) tongues; open = the closed dummy
  translated by W/2 - 15 mm along x (identity orientation, the vanilla slide), so a parked leaf spans W/2 - 30 mm
  .. W (its geometry stops 1.5 mm short), its leading edge 20 mm behind the post's face. Each leaf keeps the clone's
  own spawn (= Closed) and Open dummy types (LeftDoor* / RightDoor*). Leaf model origin = its nominal centre across,
  ON THE TRACK (z = ZH, `LEAF_ORIGIN_Z`): the Closed dummy then lies inside the lintel's fracture hull, its
  `SupportingFracture` (Fracture_01; the Open dummies have none, as vanilla).
- **Definitions (`integration.stage_contain_door`, `patch_contain_door_dummies`, `door_patch`):** leaf model
  components -> our models (with collision) + a `DoorUse` box over each leaf; ConditionalSubParts = {Closed type:
  leaf client prefab}, MeshPartsToHideWhenActive []; dummies: Particles / ParticleDirection to the block centre, the
  Closed / Open pairs, the `DoorwayObstructionDetector` (scale = 2 x half) over the opening, TerminalFront01 /
  TerminalBack01 (vanilla frame UseDoor boxes) dropped; detector QueryHalfExtents (W/2, 1.125, 0.125);
  OpeningDuration 10 000 000 (1.0 s); BlockMaterialSwapper on our models with no mesh parts (no status lamp);
  CriticalFractures = Fracture_01..07 (the frame round the opening; the sill is not critical); the Closed dummies'
  SupportingFracture = Fracture_01; DamagedModel = our own Damaged model; PCU 150 (the template's, stated) and mounts All. The vanilla DoorSliding sound is kept. Recipe: none yet
  (`write_all` now costs only `catalog.BLOCKS`; the room blocks get theirs with the menu in Task 10).
- **Couplings (Tests/test_containment.py):** both doors of the reference room, cold and hot, every width: the -Y
  back-plate hints lie on the end units' side planes and overlap the racks' `side_*` mount hints by 0.5 W x 2.25 m
  (>= 1.1 m^2); the frame stays >= 1 mm off that plane; the end racks' leaves over their 0..85 deg sweep (measured
  hulls) stay >= 15 mm from the door (it lies wholly beyond the row-end plane); the header's -Y rect lies on the end
  roof panel's +-x edge plane and overlaps its gasket band by W x 0.226 m; the door stands on the floor top with
  tiles under its whole footprint (END_MARGIN), its top flush with the roof's.
- **Part -> purpose:**

  | part | material | purpose |
  | --- | --- | --- |
  | header box beam (fascia, back board, soffit, top plate, end caps) | Colorable | carries the track over the opening and both pockets |
  | top-hung C-track (walls + flanges) in the header | Brushed | the leaves' carriages roll on its flanges |
  | end stops on the track flanges | Darker | set the open travel (rubber buffers) |
  | seal-seat lip on the header's -Y face, flush bolts | Darker / MetalDull | the roof run's end gasket bears on it (roof support / seal) |
  | fascia (+Y), threaded inserts, panel lines over the posts | Colorable / MetalDull / Darker | the aisle sign (T8) mounts here |
  | spring closer per leaf under the room-side soffit (body, plate, tension cap, drive rod, arm into the slot), "SELF-CLOSING" | Darker / Brushed / MetalDull / CleanWhite | keeps the aisle sealed: the leaves run back shut |
  | posts: split jambs round the leaf slot, seal-retainer screws | Colorable / MetalDull | guide the leaf into its pocket, carry the header |
  | brush seals in the jamb slots and the pocket end stiles | Darker | air separation where the leaf passes |
  | armoured corner caps (foot and head, aisle and room side) with yellow trim | Darker / Yellow / MetalDull | carts and trolleys knock post corners |
  | pocket cover (+Y, two panels, screws) with kick plate and "KEEP CLOSED" plate | Colorable / Darker / MetalDull / CleanWhite | hides the parked leaf (no aisle intrusion), takes the scuffs, tells the crew |
  | pocket back plate on the rack side (-Y) + 4 slotted angle brackets each | Darker / Brushed / MetalDull | bolts the frame to the end rack's side panel (slots take the rack-to-rack tolerance) |
  | slotted pocket end stile | Colorable / Darker | closes the pocket, seals the parked leaf's tail |
  | threshold (ramped lips, guide slot, floor anchors), through both pockets | MetalDull | floor guide: the leaves' shoes run in its slot; low enough to roll a cart over |
  | fracture beds on the pocket tops | FracturedMaterial01 | hidden under the header; the torn joint once the header is shot off |
  | leaf frame (stiles, kick rail, push rail, top rail) | Colorable | the aluminium leaf, takes the paint |
  | two panes per leaf in Darker gaskets | WindowGlassThin / Darker | see into / out of the aisle, keep the air in |
  | shiplap meeting tongue + meeting seal | Colorable / Darker | the closed leaves overlap 2 x 15 mm: no gap at the centre line |
  | flush vertical pull, both faces (recess liner, bar on two posts, grip) | Darker / Brushed / Darker | a pocket door needs a flush pull (it passes the jamb seals) |
  | yellow chevrons round the pull zone only | Stickers02 | the pinch point where the leaves meet |
  | carriages: hanger, top bracket, 2 rollers, axles | Darker / MetalDull / Brushed | hang the leaf from the track |
  | floor brush, 2 guide shoes | Darker | seal the floor gap; keep the leaf's foot in the threshold slot |

- **Tests:** `test_definition_validators.model_colliders` and `test_integration.test_every_block_staged` now take a
  block's own Damaged model when it has one; `test_integration`'s zone count reads `colliders.fracture_zones`.
- **Faces (measured, exported model):** F (+Y) 1 group = the header row only (10 %: the pocket kit stays > 20 mm off
  the +Y plane, so it never mounts); B (-Y) 55 % (back plates + header row); L / R 100 % (the end caps and pocket end
  stiles: harmless); Up / Down 100 %. Occupied 64 / 88 / 112 cells: the opening's inner columns between the post
  boxes and above the sill row stay free.
- **Breakable (user direction; docs/guides/vanilla-fracture-models.md applied):**
  - **Zones (8, the vanilla door frame's count):** Fracture_01 the lintel (the header over the opening and the posts:
    the track the closed leaves hang from), 02..04 / 05..07 each pocket tower in three pieces (bottom, middle, top +
    the header over its pocket), 08 the sill (the threshold between the posts). `contain.door_zones`; the export
    takes them from `door_collision(...)["fracture"]` (`export_models.fracture_zones`), the intact model keeps 4
    physics boxes. The guide's size table asks 12-15 for > 2.5 m; the door is mostly an opening (a 2 m to 4 m frame
    round a hole), so it follows the vanilla door (8) and stays inside the builder's table.
  - **Seams at real joints:** the lintel ends over the posts (x = +-(W/2 + 35 mm), the fascia's old panel lines),
    the pocket towers at the covers' panel lines (z = POCKET_SPLITS, 0.80 / 1.55 m over the floor), the threshold at
    the posts' faces. Every member crossing a seam is built in pieces that stop `SEAM_EPS` (20 um) short of it (the
    intact model stays seamless) and `_cap_seams` turns the cut faces into break faces: FracturedMaterial01 at 0.40
    UV/m (box projection; measured 0.400 by `build_dc.cut_uv_density`), 128 cap faces on LOD0 and LOD1. The cover
    panels part at their own panel joints; the pocket towers' tops keep a FracturedMaterial01 bed under the header.
  - **Hulls shaped to the solid:** boxes of each piece (the pockets to the caps' faces at y +0.1085, the top pieces
    through the header, the sill only the 8 mm threshold); they touch, so the 0.1 m connectivity holds. Health
    (volume, criticals x 2): lintel ~9.5 %, each pocket piece 12-18 %, the sill < 0.2 % (an 8 mm threshold: the one
    cheap piece). `CriticalFractures` = the 7 frame zones (not the sill): the criticals stay in the largest island
    whichever single zone dies (tested).
  - **Recognised by the builder:** collider names = the Group names (Fracture_01..08), every ColliderMeshGroups entry
    an existing group (the exporter lists only existing ones), 8 zones (2..16, <= the size table).
  - **Damaged model (vanilla "Deformed"), its own:** `export_models.export_damaged` copies the Fractured LOD objects
    (the same objects, groups, construction properties: exactly the same `Fracture_NN-Material` mesh parts, tested),
    densifies long edges (budget 1.5 x, <= the fractured triangle limit) and dents every vertex with a smooth
    position-based noise (nothing tears; faded to 0 within 8 mm of the bounds: mount faces and bounds stay put):
    mean 6.2-6.7 mm, p90 ~12 mm, max ~20 mm (vanilla 5-15 / 10-25 / 30-70). Its own collision (the same zone hulls and
    names). Staged as `Models/Damaged/<name>_Damaged.model` (the BlockModelDefinition's DamagedModel; the swapper lists
    all three). No material swaps: the frame has no lamp or glass. The floor and roof are untouched (a later pass).
  - Fractured LOD0 = NF LOD0 triangles (the seams cut along members' ends, no new geometry); 42 mesh parts.
- **LODs:** LOD0 carries the real fasteners (cover and seal-retainer screws, threshold anchors), so every width's
  LOD0 is past Keen's table bias (a light LOD0 would shift the limits one row and squeeze LOD2 to ~200 tris): 100:
  7112 / 2156 / 600 / 12 (46 % of 15571); 150: 7376 / 2156 / 600 / 72 / 12; 200: 7640 / 2156 / 600 / 72 / 12 (40 %).
  Damaged: 8988-9356 / ~3050 / ~890 / (~100) / 12. Leaves: 1720 / 284 / 12, 6 / 6 / 1 materials. Frame materials
  7 / 7 / 4 / (3) / 1.
- **Provenance:** all geometry generated; vanilla materials only (WindowGlassThin, Stickers02, FracturedMaterial01,
  the CleanWhite glyph atlas); the mechanism is the cloned vanilla door.
- **Previews:** `DC_PREVIEW=plan3-t5` (`dc/preview_p3t5.py`) into `preview/p3-task-5/`; contact sheet
  `python3 Source/Model/p3t5_sheet.py`. `preview_room.contain_door` places a built door with its leaves at an open
  fraction (`room_scene(..., contain_open=f)`); `preview_mats` "GlassThin" is the WindowGlassThin stand-in (clear).

## Plan 3: main merge (cable trays T9–T11, T9b/T9c fractures): the room's fracture unified on main's pipeline (2026-10-18)

This section SUPERSEDES the fracture bullets of Plan 3 Tasks 3, 4 and 5 above (the layer splits, the gasket pads,
glazing beds and pocket-top beds in FracturedMaterial01, `door_zones` / `_cap_seams` / `export_damaged`).

- **One pipeline.** The floor, roof and door are planned blocks of `dc/fracture.py` (`_floor`, `_roof`, `_door`), cut
  and capped by `dc/fracture_mesh.py`, exported by `export_models._export_planned` with shaped hulls and their own
  Damaged model (≤ 2× the Fractured triangles). Removed: `export_models` `DAMAGED_FAMILIES` / `DENT` / `densify` /
  `dent` / `export_damaged` and the `boxes["fracture"]` zones; `contain` `door_zones` / `critical_zones` /
  `seam_planes` / `_segs` / `SEAM_EPS` / `_cap_seams` / `frac_uvs` / `LAST_CAPS` / `LEAF_SUPPORT`;
  `build_dc.cut_uv_density` (the UV check is `fracture_rules.cut_uv_density`, on the files). Kept: the door's leaf
  collision (`export_subparts(collision=)`, `export_block(subpart_collision=)`), now on main's exporter.
- **Door:** the members are built WHOLE across the joints; the plan's 8 zones (lintel; three pieces per pocket tower;
  sill) are half-space regions, the 6 seams straight at the joints (`JAG["contain_door"]` amp 0), `ROOM_LONG_CUT`
  0.04 for the hardware. Criticals Fracture_01..07 and the Closed dummies' `SupportingFracture` (Fracture_01) come from
  the plan via export.json (`integration.stage_contain_door` / `patch_contain_door_dummies`). Task 5's dent is
  `fracture.DENT["contain_door"]`. The sill is now ONE solid section (base, both ramped lips, the guide slot): the
  welded base-plus-lips shared edges and left the sill's cut open (no cap).
- **Floor (the queued refinement, guide 10.3 (2)):** in plane, full thickness: the 0.5 m tile in 2 halves along its
  panel line (y = 0), the 1.0 m block in its 4 tiles at the real joints (each with its quarter of the
  understructure; a shared pedestal's round column goes whole to one tile, its head and base plates are cut and
  capped). The gasket pads are now Darker rubber pads. No critical zone.
- **Roof (guide 10.4 (b)):** in plane by 0.5 m bays, along the mullions (a member centred on its mullion goes whole,
  beams / caps / tape across are cut and capped). Keen's table on the MEASURED edge: the 1.0 m panel is 0.998 m (gaskets
  and clamps 1 mm inside), so 3 zones (the -y row one zone, the +y row's two bays); 1.5 m: 4 zones (6 bays > Keen's 5:
  the middle panes crack at y = 0); 2.0 m: 8 (a zone per bay). The glazing beds are now Darker glazing tape. The
  Damaged .model maps FrostedGlass to vanilla `WindowGlassBroken` (`DAMAGED_SLOTS`, `material_guids`).
- **Damaged dents on a top face:** `DENT[...]["unpin"] = ("+z",)` for the floor and roof: on that bounding face only
  the outward component stays pinned, so the walking deck / the roof caps can dent inward.
- **Room jag** (floor, roof): amp 8 mm at frequency 4 (the caps' UVs are projected on the seam plane; a steeper jag
  on a thin plate or pane stretched them to 0.24–0.28 UV/m).
- **Tests:** `test_fracture_refine.py`, `test_fracture_rules.py` and `test_fracture_plan.py` now cover the 10 staged
  room blocks (60 breakable blocks, 120 models): recognition, connectivity, own Damaged ≤ 2×, cap UV 0.40 ± 0.04,
  hull fill ≥ 0.85, placement with fractures. Previews: `p3fr_preview.py` / `p3fr_sheet.py` →
  `preview/p3-fracture-refine/` (git-ignored).
- **Old previews:** `preview_p3t3/4/5` take their zones from `fracture.plan` now; they render the built (uncut) LOD0,
  so they show no break faces.

## Plan 3 Task 6: the in-row cooler DC_CRAC (2026-10-18)
- **Shipped chain: P3-1 as the risk spike amended it (P3-15), no fallback.** A Gyroscope250 clone with the gyroscope
  stripped (`integration.crac_patch`): the template-inserted `GyroscopeComponent` (key `c232d09e`) is Removed from
  the cloned server composition (its Update dropped, later indices shifted, tag slot `GyroscopeComponent` in
  RemovedKeys) and from the server prefab's ObjectBuilders (the KVM On/Off delta form); the clone's
  `DC_CRAC_GyroscopeDefinition.partialdef` (44 MN m torque) is deleted and `clone.DROP` drops it on any re-clone.
  Kept as cloned: the `PowerableBlockDefinition` (ConsumedResource Amount 25, priority 6: a real grid load; PCU 30
  stated; mounts All), the PowerableBlockComponent (terminal On/Off, Working), the FunctionalBlockAnimationController
  (server and client), ConditionalSubParts, the BlockMaterialSwapper and the BlockEffects hum (`GyroscopeMID` while
  Working). No staged or installed CRAC file names or references the GyroscopeDefinition type (tested).
- **Fans (`integration.stage_crac`, `_stage_rotor`, `patch_crac_dummies`):** one rotor subpart `CracFan` (model,
  dummy type, model component, InfiniteRotation, composite, prefab; `_stage_fan` is now `_stage_rotor` with the
  racks' FAN_ANIM) spawned by the cloned ConditionalSubParts (`SubParts.def`: CracFan type -> the rotor prefab; the
  vanilla gimbal prefab and its `MeshPartsToHideWhenActive` Fracture15 list unbound / cleared) at three dummies
  `CracFan1..3` (the vanilla `RotatingSubpart` dummy dropped). InfiniteRotation about game +Z (the block's forward
  axis, Blender -y), 600 deg/s, AngularSpeedup 300 (a 2 s linear soft start), AngularSlowdown 150 (a 4 s coast):
  `InfiniteRotationAnimationComponent` ramps CurrentAngularSpeed linearly toward the target at those rates (decompiled
  2.4), which is the whole of the "feel" data allows. Seven blades: 600 deg/s turns 10 deg per 60 fps frame (20 at 30
  fps), well under half the 51 deg blade pitch, so the rotor never strobes. Each blade is swept (the tip trails),
  twisted 40 -> 22 deg and cambered, the leading edge upstream, so the turn direction pushes air into the cold aisle.
- **Lamps / terminal:** the RUN lamp is the model's `EmissiveOff` slot; the swapper lights it `EmissiveGreen` on our
  NonFractured and Fractured models (`EmissiveOff` + every `Fracture_NN_Hide-EmissiveOff`; the Damaged model maps the
  lamp to EmissiveOffBroken and is not swapped). The ALARM lamp is an unlit Yellow lens (never swapped). The clone's
  `TerminalFront01` dummy (On/Off) sits on the controller display (aim box 0.40 x 0.31 m), supported by the controller
  zone; `Particles` at the block centre.
- **Builder:** `dc/crac.py` (`build`, `collision`, `fan_points`, `rotor`, `subparts_for`); `build_dc.build_crac`
  and `crac_geometry` (contain_rails, up / down mount rects, top_entries, front_max_y / back_min_y outside the rail
  band, flange_top_z, per-fan tip / guard clearances). Reuses the rack's builders for every room interface: plinth
  feet and side skins, corner posts and caps, `_contain_rail`, `_entry_fitting` (with the rack's one-tuft brush lips:
  the combed LOD0 lips cost 1k tris). Collision: plinth, body, top band (3 boxes, every cell); hints = the full
  rack's minus the slot's (sides, bottom, rims, contain_front / back), box for box (tested).
- **Part -> purpose:** the table in `dc/crac.py`'s docstring (plinth nameplate; condensate pan lip and float switch;
  hinged fan door with three hinges and a recessed latch; hot-swap fan modules F1-F3 with venturi, finger guard and
  external-rotor motor; perforated side supply grilles; CAUTION ROTATING FANS; controller with display, RUN / ALARM,
  MODE / SET, vent; rear filter door: four louvred return grilles over pleated filters, FILTER tabs, quarter-turn
  latches; RETURN AIR + filter DP gauge; CHW S / CHW R stubs with insulation, ball valves, blind flanges whose bolt
  heads end 1 mm under the top plane; COND stub; the rack's brush plates for a Drop; side panels with lift-off grips;
  the rating plate).
- **Faces:** Forward / Backward mount on the rail band only (1 group, 10 %); Left / Right 100 %; Up the rims; Down
  100 %. Everything outside the rail band stays behind rack.YK (the rack's own clamp screws and cap trims aside).
- **Budgets (LOD0 -> last):** 13948 / 3636 / 1168 / 120 / 12 tris (87 % / 98 % / 91 % / 77 % of Keen's; the 42U
  rack runs at 91 % LOD0); 8 materials (Colorable, Darker, Brushed, MetalDull, Yellow, white stencil, EmissiveOff,
  MetalPerforationSteel). The bevel goes on the frame / Darker shell parts only; the three door plates (full of
  openings) and the small Darker kit are unbevelled parts (`panel`, `fine`): the bevel there cost ~4k tris. Rotor:
  864 / 228 / 12.
- **Fracture (`fracture._crac`, guide 10.3 (3)):** 9 zones: 01 coil core (critical, 38 % health, every other zone
  its neighbour), 02-04 the fan sections F1-F3 (critical: ConditionalSubParts only despawns rotors when the block
  stops being Functional, so a dead fan section must stop the block, as vanilla Gyroscope250's criticals sit under
  its rotating rings; 11 % each), 05 controller (supports TerminalFront01), 06 / 07 the filter door's halves, 08
  plinth, 09 top band. Seams straight on real joints (door rails between the modules, the controller's shadow gap, the
  grille's middle rail, the core faces at y 0.10 / -0.35, the plinth top and the slot band's top). Fans' dummies
  supported by their sections. Break faces in every zone but the plinth and the top band (bolted joints: nothing
  crosses those seams). Own Damaged model (dent mean 6.7 mm, max 25 mm). Fractured LOD0 14888 tris.
- **Couplings (tested):** the roof mounts on the CRAC (INROW now includes it) in every aisle width, cold and hot;
  contain rails, mount rects and top entries equal the full rack's.
- **Not verified in game:** the strip loads (no `GyroscopeComponent` / definition errors) and the block has no torque;
  the On/Off terminal and the 25-unit draw; the rotors spin, ramp and coast; the RUN lamp swap; the fracture and
  critical behaviour (a dead fan section stops the unit).

## Plan 3 Task 7: PDU cabinet and zero-U rack PDU strips (Feed A / B, 42U / 24U) (2026-10-18)
- **Builder:** `dc/pdu.py` (`build_cabinet` / `cabinet_collision`, `build_strip` / `strip_collision`, `strip_feed`,
  `strip_directions`, `outlets_local`, `banks`, `tag_slot`); `build_dc.build_pdu` measures `geometry`: cabinet =
  `top_entries`, `contain_rails`, `up_mount_rects` / `down_mount_rects`, `front_max_y` / `back_min_y`; strip =
  `inlet_plug` [x, y, z_bottom], `envelope_bounds`, `outlets` (dims), `outlet_housings` (measured), `feed`, `top_z`.
- **Both decorative** (P3-7: no vanilla power-junction block), WallInsertPanel clones, PCU 5, breakable.
- **Cabinet (P3-6):** the rack footprint; reuses the rack's own builders (`rack._plinth`, `_corners`, `_contain_rail`,
  `_entry_fitting`), so the plinth, posts, caps, containment rail and the top-entry brush plates are the rack's to the
  vertex: `test_cabinet_shares_rack_interface` (rails, top entries, rim / bottom rects within 1 mm), a Drop lands in it
  (`test_tray_build.LANDINGS` += the cabinet), the roof panels mount on it (`test_containment.INROW` += the cabinet).
  Physics: plinth / body / top band (3 boxes); mount hints = the full rack's flush ones (sides, bottom, rim, rail
  band); Directions All. Front layout follows the v1 06d mockup (panelboard style).
- **Strips (P3-20):** one cell, placed at `rack.PDU_CELLS`; everything inside `dims.PDU_ENVELOPE` (Feed B mirrored in
  x; text and digits are added after the mirror so they read) over `rack.pdu_band` (the 24U body stops 4 mm under
  local z 1.13). Hints: Down (plug seat) + Forward (the face on the bracket plane rack y = -SLOT_HALF_D) →
  Directions "Forward, Down" (final review I1, 2026-10-19: now Down only, see "Final review fixes"); the cloned placer's AutoRotateFace is nulled (the panel's "Down" would lay a strip aimed
  at the bulkhead on its back). The inlet plug's bottom is the plinth-top plane, 0.8 mm over the socket face.
- **Live-cabling hook (backlog):** `dims.PDU_OUTLET_X / _Z / _FACE_Y / pdu_outlets()` (per slot an outlet pair at
  slot z 0.100) and `dims.SERVER_PSU_X / SERVER_INLET_B / SERVER_INLET_FACE_Y / server_inlets()` (`dc/server.py`
  `_rear` now reads them; geometry unchanged). No cords between strip and server are built (only the parked jumpers).
- **Part → purpose:**

  | part | material | purpose |
  | --- | --- | --- |
  | cabinet meter: L1 / L2 / L3, lit 3-digit amps, 10-segment bars | Darker / EmissiveGreen / CleanWhite | the incomer's load per phase |
  | rotary isolator: Yellow escutcheon, Darker hub + bar handle, ON / OFF tabs, padlock hasp | Yellow / Darker / MetalDull | isolates the whole cabinet; lock-off for maintenance |
  | DANGER HIGH VOLTAGE + 400 V placard | vanilla Stickers02 `danger_hv` on Darker | the incomer voltage |
  | 2 x 12 branch breakers on a busbar, Brushed toggles (ON = inward), Yellow trip tabs, numbers 1-24 (odd left) | Darker / Brushed / Yellow | branch protection: one breaker per rack feed |
  | hinged breaker cover: shadow-gap outline, 3 hinge knuckles, key lock + pull | Colorable / Brushed / MetalDull | keeps the dead-front closed and locked |
  | top band: the rack's brush plates (dims.TOP_ENTRY), trough, cable cleats, PDU 1 label + lamp | rack's | cables in from / out to the overhead tray; supply present |
  | rear: two bolted lift-off panels (grab handles), louvred vent, gland plates with blanked glands | Colorable / Darker / MetalDull | busbar heat to the hot aisle; alternative bottom-rear cable entries |
  | strip body: extruded profile, T-slot grooves, end caps, Colorable face plate per bank | Darker / Colorable | the PDU (busbar and outlet housing) |
  | per slot: 2 locking outlets, lit status LEDs, slot number tab | Darker / EmissiveGreen | feed the slot's two server PSUs |
  | jumper cords: plug + latch + boot, cord looping into the channel, parked under a strap | Rubber / MetalDull / Darker | pre-dressed cords; no free end |
  | cord channel: Colorable U-channel, lips, Darker straps with buckles, Brushed clips | Colorable / Darker | holds the parked cords |
  | bank head (per 4 slots): breaker + Yellow trip tab, 3-digit ammeter, BANK n / 16A | Colorable / Darker / EmissiveGreen | bank protection and load |
  | feed tag: band (A Yellow, B the paint) + letter plate | Yellow or Colorable / Darker | A / B redundancy at a glance |
  | inlet: gland, heavy cord, boot, twist-lock plug with coupling ring | Rubber / Darker / MetalDull | the strip's supply from the plinth receptacle |
  | brackets: Brushed standoffs, button heads in the bulkhead keyholes | Brushed / MetalDull | hang the strip on the column |

- **Fracture (`fracture._pdu_cabinet` / `_pdu_strip`):** cabinet 8 zones (the rack pattern: plinth halves, body
  lower / upper at the isolator-panel / cover joint z 0.79 m, each halved at x = 0 between the breaker columns, top
  band halves), no critical zone; strip 3 sections (42U) / 2 (24U) along the run, seams between a slot's outlets and
  the next head (no cord, outlet, plug or bracket is cut), Fracture_01 = the bottom with the plug, no critical zone.
  Both have their own Damaged models (EmissiveGreen → EmissiveOffBroken). `test_fracture_refine` / `_rules` cover them
  (65 blocks, 130 models).
- **Budgets (LOD tris):** cabinet 13574 / 3184 / 712 / 48 / 12 (84 % / 86 % / 56 % of Keen's; the rack is at 90 /
  85 %), 8 materials; 42U strip 6602 / 1266 / 188 / 12 (63 %), 24U 3862 / 800 / 12 (70 % / 84 %).
- **Clone source / update intel:** built on WallInsertPanel (the plan's source). The 2026-10-19 update announces a
  vanilla circuit-breaker cabinet (docs/research/se2-upcoming-update-hostile-encounters.md): check it as a possible
  better clone source (and kit parts) for the cabinet after the update.
- **Previews:** `DC_PREVIEW=plan3-t7` (`dc/preview_p3t7.py`) into `preview/p3-task-7/` (untracked); contact sheet
  `python3 Source/Model/p3t7_sheet.py`. The T6 CRAC is still a ghost in these room shots.

## Plan 3 Task 8: signs and labels (aisle sign, hanging aisle sign, rack label) (2026-10-18)
- **Builder:** `dc/signs.py` (`build`, `collision`, `screens` -> `Screen(face, center, size, slot, normal, up)`,
  `rod_plates`, `back_mount_rects` / `up_mount_rects` / `down_mount_rects`, `mount_direction`);
  `build_dc.build_sign` (fit_lods) measures `geometry` = `screens` (per LCD slot: the built quad's centre, size along
  the face, normal, beside the planned one), `rod_plates`, the mount rects and `mount_direction`. All three are
  `LCDNarrow50` clones (P3-8), editable vanilla LCDs, breakable. Block frame: x along the sign, +Y = front.
  - `DC_Sign_Aisle` 1.0 x 0.25 x 0.25: mounts **Backward only**, on a wall or on a containment door's header fascia
    (the header band is exactly its cell; its back plate's 4 bolts at x +-0.42, z +-0.075 are the fascia's threaded
    inserts, `contain.py`). Screen 0.80 x 0.20 (4:1).
  - `DC_Sign_AisleHang` 1.0 x 0.25 x 0.5, double-faced, centred on y = 0: mounts **Up only**, under a rod hanger.
    Screens 0.64 x 0.16 (4:1) back to back. Two MetalDull rod plates (ROD_PLATE 0.034 square, top 1 mm under the top
    plane) at **x = +-ROD_S on the sign's centre line**.
  - `DC_Sign_Rack` 0.5 x 0.25 x 0.25: mounts **Down only**, on a rack's top front (or back) edge, on the rack's label
    pad (`dims.LABEL_X / LABEL_Y`: the full rack's rim band, the half rack's top_front / back pads), between the
    Drop's waterfall columns (|x| <= 0.219 vs the waterfalls' 0.336). Screen 0.34 x 0.17 (2:1), face tilted 15 deg
    down (the label sits ~2.8 m up).
- **T2 carry (the hanger orientation), resolved:** a rod hanger's two rods are at its local **y** = +-ROD_S
  (`tray_plan._rods`: x = the piece's centre). Placed at the same yaw as the sign (Task 2's room) they sat across the
  sign's 0.5 m depth, at its centre. The sign's plates are along its 1.0 m face (two drop rods 0.464 m apart are
  how a long sign is hung level), so the hanger is placed **turned 90 deg to the sign** (`room._trays`: sign yaw 1,
  hanger yaw 0, like every tray hanger in the room). The rods block is square in plan, so the player just turns it.
  The bracket is a T-bar header: a Darker capping rail along the sign's top carries two Darker lifting lugs; per rod
  a clevis on the lug's pin, a turnbuckle (two threaded stubs, an open body with hex bosses: it levels the sign), the
  coupler nut and the rod plate. The sign's Up hints are the hanger's Down coupler hints turned into the sign's
  frame (the same diagonal one-cell pattern, `tray._column_collision`), so the same two cells mount on both.
- **LCD surfaces (P3-18, `functional.SIGN_LCD`, `integration.patch_lcd(spec, surfaces, G)`):** `patch_lcd` now takes
  a list of surface dicts (the status server keeps its call with one). Each surface keeps the cloned
  `DefaultScreenMaterial` (8a35c12c, the one every vanilla LCD uses) and `UseOnlineTexture`; the first keeps the
  cloned delta key, a second gets its own stable key (`asset_guids.json` "lcdsurface/<name>/1").
  - aisle signs: `LCDScreen_Off_4` (and the hanging sign's `LCDScreen_Off_4_Back`), 1024 x 256, AspectRatio 4, the
    slots mapped to vanilla **LCDScreen_Off_4.0** (fa0a1f34): the 4:1 off-screen material vanilla ControlSeat250
    maps its 4:1 CustomDisplay04 to, so the resolution, aspect and texture agree.
  - rack label: LCDNarrow50's native 2:1 (512 x 256, AspectRatio 2) on `LCDScreen_Off` -> vanilla LCDScreen_Off_2.0
    (bd7f946b), as the status server.
  - **Double-faced:** the hanging sign has TWO surfaces (LcdMultiPanelDefinition.Surfaces is a list: ControlSeat250
    has 8; `LcdMultiPanelComponent.Init` makes a state per surface, filling missing ones with defaults), named
    "Front Face" / "Back Face" (`DefaultDisplayName`). The player edits each in the terminal. Recorded: the second
    LCD surface was used, not a static plate.
  - **No default text:** `LcdPanelSurface` has only MeshPartName, Resolution, DefaultScreenMaterial, AspectRatio,
    UseOnlineTexture and DefaultDisplayName, so "AISLE" / "RACK" cannot be set in the definition (a pre-filled
    server-prefab SurfaceState could, but is untestable offline: not done). The player types the text; the names
    are "Aisle Sign", "Front Face" / "Back Face", "Rack Label". The previews overlay sample text (preview only).
  - The `LcdPanel` dummy (vanilla UseTerminal type, name kept) moves over the front screen (`integration.
    sign_dummies`); on the hanging sign it is deep enough to reach both faces. Its `SupportingFracture` is the zone
    holding the screen's centre (Fracture_01).
- **Definitions (`integration.sign_patch`):** PCU 35 (P3-11, as LCDNarrow50), `MountPointGeneratorSettings.
  Directions` = the one mounting face (Backward / Up / Down), so a sign never mounts by its screen. Staged with
  `catalog.STAGED_ROOM_FAMILIES += ("sign",)`; menu, recipe, icon and unlock with Task 10 (the clones keep
  LCDNarrow50's tile / icon until then).
- **Hot / cold:** by the frame's paint (Colorable housing and bezel); the previews use blue (cold) and red (hot).
- **Faces (measured):** only the mounting face mounts: Aisle B 1 group, Hang U 2 groups, Rack D 1 group; every other
  face 0 (parts on non-mounting faces stay > 20 mm off the plane where the mount rays reach; the thin hanging sign's
  faces miss the rays at |y| >= 0.049).
- **Fracture (`fracture._sign`, guide 10.3 (2) "panels split in plane"; vanilla LCDNarrow50: 2 zones, none
  critical):** the 1.0 m signs in 3 tiles along x (seams at x = +-0.16, `SIGN_SEAM_X`; Keen's table: 3 at the
  ~0.97 m measured edge), the label in 2 halves (2 at 0.44 m); housing, bezel, liner, back plate and the screen are
  cut (break faces in FracturedMaterial01 at 0.40 UV/m; the open screen quad gets no cap), bolts / hangers /
  stencils go whole; no critical zone. Own Damaged model (screens -> vanilla LCDScreen_Off broken state:
  `fracture.DAMAGED_SLOTS`). Not an "unfractured" exception (P3-10 superseded by the user's breakable direction).
- **Budgets:** Aisle LOD0 1224 / 6489 tris (3 LODs), Hang 1744 / 6028 (3), Rack 870 / 4252 (3; its LOD0 is held to
  Keen's 4-material cap for a 0.44 m model: Colorable, Darker, MetalDull, LCD; no stencil). One physics box each.
- **Couplings (Tests/test_signs.py):** the aisle sign on both doors of the reference room, every width (back plane on
  the door's +Y plane, back rect inside the header's +Y rect, centred); the back bolts = the fascia inserts; the
  hanging sign's plates under the turned hanger's rods (1 mm) and its Up hints = the hanger's coupler hints; Review
  Focus 4: on every full rack (cold / hot, every width) the label misses the Drop's occupied cells and the roof's,
  on a half rack it sits between the Chute's ladders; its foot's hint lies on the rack's pad (>= 95 %, 42U and 24U,
  front and back); no vertex of a built Drop (Low / Moderate / Full) inside the label's cells.
- **Part -> purpose:**

  | part | material | purpose |
  | --- | --- | --- |
  | housing (45 deg clipped corners) | Colorable | the display's enclosure (panel, backlight, driver board); takes the hot / cold paint |
  | bezel ring, proud of the housing | Colorable | protects the screen's edge |
  | sloped liner inside the bezel window | Darker | shades the screen (contrast under hall light), seals the panel edge |
  | screen | LCDScreen_Off_4.0 / _2.0 (the LCD surface) | what the player writes on |
  | armoured end caps + their bolts and washers | Darker / MetalDull | knock armour on the ends; the bolts clamp the bezel to the housing |
  | bezel gasket (aisle sign) | Darker | seals the bezel to the housing (the dark line round the frame) |
  | AISLE tab with white stencil | Darker / CleanWhite | names the sign's kind when the screen is off or unpowered |
  | backlight vent slots (top / bottom; label top) | Darker | backlight heat out, cool air in |
  | back plate + 4 flush bolts (aisle sign) | Darker / MetalDull | hangs it on a wall / the door header's threaded inserts |
  | cable gland + nut (aisle sign end cap; label rear) | Darker / MetalDull | the display's power / data feed |
  | top rail (hanging sign) | Darker | the T-bar header: carries the lugs, closes the double-faced housing |
  | lifting lugs + pins, clevis, turnbuckles, coupler nuts, rod plates | Darker / MetalDull | carry the sign on the hanger's two rods and level it |
  | wedge body, face 15 deg down (label) | Colorable | a lectern: the face looks down to the aisle from the rack top |
  | foot + 2 bolts on washers (label) | Darker / MetalDull | bolts to the rack's top rim (the label pad) |
  | rear service cover + 2 screws (label) | Darker / MetalDull | the driver board's service hatch |
- **Previews:** `preview/p3-task-8/` (untracked; `DC_PREVIEW=plan3-t8`, `dc/preview_p3t8.py`, contact sheet
  `python3 Source/Model/p3t8_sheet.py`). The room scene (`preview_room.built_sign`) paints built signs for the aisle
  and overlays the sample text.

## Plan 3 Task 10: build menu, names, costs, unlock and icons for the 19 room pieces (2026-10-18)

- **Pipeline:** every room family joined `catalog.PIPELINE_FAMILIES`, so `BLOCKS == CATALOGUE == STAGED` (73 blocks).
  `build_dc.py -- all`, `check_placement all` and `export_models` now include the room pieces (closes the T3 review
  minor). Task 9 (cable looms) did not run: no loom group, order or sizes.
- **Menu (Ruling P3-12):** four tiles after "Cable Tray Supports": "Raised Floor" (Order 800: Solid, Perforated; each
  0.5 / 1.0 m, owned by the 1.0 m tile), "Room Cooling & Power" (900: CRAC, PDU Cabinet, Rack PDU Feed A, Feed B; the
  strips 24U / 42U, owned by the 42U), "Aisle Containment" (1000: Door, Roof; 1.0 / 1.5 / 2.0 m, owned by the 2.0 m)
  and "Signs & Labels" (1100: Aisle Sign, Hanging Aisle Sign, Rack Label). Multi-size kinds have their own tile text
  (`names.KIND_NAMES`). The cloned vanilla tiles (Catwalks, Gyroscopes, Doors, Deck Panels, LCDs) are left; all 19 blocks
  and their 11 kinds are in the initial unlock.
- **Costs:** `recipes.SOURCES` gained CatwalkSquareBase250 (1 Steel Plate, game scale 6), Gyroscope250 (8 SP, 1 CC,
  3 Motor, 2 Wire + 6 SP; scale 3), DeckPanel250 (1 SP; scale 6) and LCDNarrow50 (LCDPanel50's recipe; scale 1), read
  from the SDK (the test follows the Copy chains; the cell box is the union of the glTF colliders). SlidingDoorNarrow250
  got its cells (10, 10, 2) from the FBX bounds (scale 2; it has no glTF collider). The containment doors cost from the
  wall-panel frame plus one door mechanism (`door_sides` = 1). Every room block's game scale is 1; Solid and Perforated
  tiles of a size cost the same; the CRAC keeps the gyroscope's 3 Motors. The hanging sign is the priciest sign
  (8 cells, two screens: 10 Electronic Parts) by the same volume rule.
- **Localisation (the main log's "LOCALIZATION WARNING: Could not find key Data Center" and the "Unrecognized value"
  validation warnings):** every Name / Description / Tooltip / UIData.Name is a LocKey. `dc/texts.py` stages
  `DataCenter/Texts/DataCenter_en-US.def` (a CultureInfoAssetDefinition on the vanilla en-US CultureId, ContentId
  "DataCenterTexts") and `DataCenter/Texts/en-US/DataCenter.loc-texts` with every display string the package stages,
  key == English text. Keys equal the text on purpose: in 2.4 the base culture is read once at game start and a mod's
  World-set definitions arrive with the world, so the runtime lookup may still miss (and then shows the key, i.e. the
  right words); the definition validation rebuilds the texts from the loaded culture definitions and finds them. A
  Core-set texts definition would load at start but breaks a mod pushed with a world (the Core set is already mounted).
- **Icons:** the core rig (`preview_task10.icons`), with room framings: floor and roof 3/4 from above (roof at exposure
  -1.25 so the frosted panes keep their mullions), CRAC and PDU cabinet as the racks, doors front 3/4 with the leaves
  half open, the PDU strips from behind and leaned 38 deg across the tile (an upright 0.25 x 2 m strip is a hairline),
  signs nearly frontal with sample text. Sizes of one kind are drawn at different fills.
  Command: `DC_PREVIEW=task10 DC_T10_PART=icons blender -b --python Source/Model/build_dc.py -- "DC_Floor_*" DC_CRAC
  "DC_PDU_*" "DC_Contain_*" "DC_Sign_*"`; sheets: `python3 Source/Model/icon_sheet.py room` / `room_menu`.

## Plan 3 Task 11: visual-improvement pass (2026-10-18)

Audit: `Source/Model/review/plan3-visual-audit.md` (finding -> evidence shot -> fix -> after shot); shots
`preview/plan3-task-11/{before,after}/` (`DC_PREVIEW=plan3-t11 DC_T11_PHASE=before|after`, dc/preview_p3t11.py).

- **Z-fight audit ported from main (4f7288a5)**: `dc/zfight.py` and `style.hazard_triangle` unchanged (the main merge
  brings `Tests/test_zfight.py` and the racks' own fixes); `dc/zfight_room.py` adds the containment door's sliding
  leaves (closed / open against the frame, leaf vs leaf, inside each leaf, every LOD) and the stencil-backing rule
  (every white stencil glyph on a non-paint plate). `build_dc.py` records both in `build_report.json` "zfight";
  `Tests/test_room_zfight.py` checks the 19 room blocks.
- **Fixed by it:** the containment leaves' pinch-zone chevrons and LOD1 pull plate (0.2-0.3 mm over the stile:
  now 0.6 mm), the pull recess walls' coplanar corner overlaps (end walls between the side walls); the PDU strips'
  BANK / 16A labels (0.2 mm over the label strip: 0.6 mm); the CRAC's and the PDU cabinet's CONTAINMENT rail tag
  (`rack._contain_rail(tag_lift=)`; **the racks keep 0 until the main merge**: rack geometry is not changed here);
  the CRAC's white stencils on paint (controller RUN / ALARM / MODE / SET legend and title, CONDENSATE PAN) now on
  Darker plates.
- **CRAC rear (user direction):** the lower half of the hot-aisle face is a bolted service bay with two blanked
  **O2 / COOLANT SERVICE** ports; the filter door keeps the upper half (two grilles). The ports are Keen's small
  conveyor port frame (kit part, `dc/crac_ports.py`: `O2Generator250.fbx` `ConveyorPortSmall_Border_low.001`, LOD1
  `O2Generator250_LOD1.fbx` `ConveyorPortSmall_Border_low.003`, read-only import; geometry, normals and first UV
  unchanged, the extra UV layers dropped; LOD2+ ours) with our
  bolted Darker blind plate in place of the hatch (the hatch's ConveyorsAtlas face would be a 9th material, and its
  latch handle goes with the hatch). Dummies `conveyor_port_o2_1` (z 0.5) / `_2` (z 1.0) on the rear cell face,
  centred on 2 x 2 cell patches, oriented like vanilla's ConveyorBack, small-port scale (0.5, 0.5, 0.05), supported
  by Fracture_06 (the bay), typed with our own inert `ServicePort` dummy type: nothing snaps, no mount point. To turn
  them on later (data only): set their Type to vanilla UseConveyor (`integration.CRAC_PORT_TYPE_ON`), add the conveyor
  (and vent) components and mount points; the frame's face stands in the 2.7 cm keep-out (a conveyor end would meet
  the cell face 2.7 cm in front of it).
- **CRAC budget:** LOD0 14350 / 16072 (89 %), LOD1 3468 / 3696 (94 %, was 98 %), LOD2 1220 / 1282, LOD3 144 / 156;
  paid by: LOD1 drops the 6 mm feet, the 18-24 mm labels and the port tags; LOD1 water stubs 6 / 8 segments; LOD2 bay
  as blocks; 4 blind-plate bolts.
- **CRAC hum:** set explicitly through `integration.patch_hum` (`HUM_CRAC`, still vanilla GyroscopeMID: 2.4 has no
  fan loop; O2H2Generator is the alternative to try in game). The vanilla gimbal's dead subpart chain (S1-S3,
  gimbal prefab / composite, SubpartMarker) is dropped (`clone.GIMBAL` in `clone.DROP`).
- **CRAC header:** the unnamed Yellow square beside "CRAC 01" is gone (Yellow only at hazards).
- **Contained aisles (T8 carry), guidance:** the roof covers the rack tops' aisle edge, so in a CONTAINED aisle mount
  the rack labels on the rack-top edge facing the OPEN aisle (`room.rack_label(u, -1)`; the label's back-pad mount
  existed since Task 8) and sign the contained aisle on its doors' headers (DC_Sign_Aisle). No under-roof sign: the
  only free volume there is the rack doors' 85 deg sweep (0.457 m into the aisle up to 2.246 m), see the audit.

Part -> purpose (new parts):
| part | purpose |
|---|---|
| service bay panel (bolted, Colorable) | closes the lower rear; carries the service connections, removable for service |
| port frame (vanilla small conveyor port, Yellow) | the standard 0.4 m conveyor / duct flange (life-support O2 loop, coolant top-up) |
| blind plate (Darker, 4 bolts, BLANKED / DO NOT REMOVE) | caps the unused port (airtight, no conveyor today) |
| O2 / COOLANT SERVICE label, PORT 1 / 2 tags (Darker plates) | names the connections for the engineer |
| controller legend plate / title strip (Darker) | the lamp and key legends read on any paint |
| condensate label plate (Darker) | idem for CONDENSATE PAN |

## Plan 4 Task 9: KVM use-to-toggle (data-only, Ruling P4-8a) (2026-10-18)

Use on the KVM's drawer pops the console out or stows it. Pure data, so it works the same with scripts off (the FBAC's
data-only motion) and on (the KVM sequencer, with its door interlock): the use action only flips the Ruling 15 state,
`PowerableBlockComponent.Enabled`, and Working (and with it the pop-out) follows.

**The vanilla pattern (Step 1).**
- Dummy type `System/DummyTypes/UsePowerable.def` (`504d93cd-9f8f-47b5-9be6-6fb633b93ee1`).
- `System/UseActions/UseActionBindings.def:14` maps it to `System/UseActions/UsePowerableAction.def`
  (`a514581d`, UseActionType `UsePowerableAction`, EnableText / DisableText `UseFunctionalEnable` / `UseFunctionalDisable`
  = "Press {Control:InteractPrimary} to enable / disable").
- `Game2.Client/.../Interaction/UsePowerableAction.cs:42-47`: `InteractPrimaryStart` sets `Enabled = !Enabled` (a synced
  property, `PowerableBlockComponent.cs:257-271`); `:49-69`: the hint is the block's DisplayName over that text, live
  while hovering.
- Vanilla blocks using it: GravityGenerator500 and Reactor250 / Reactor750 (`ButtonTop01`, 0.25 x 0.25 x 0.07-0.08,
  each with a SupportingFracture), in their `*_BlockModelDefinition.partialdef`.
- No sound: the action plays none and BlockEffects has no on-toggle event (its `OnUseAudio` is the Working loop, which
  on the KVM is the server hum, so the hum starting or stopping is the audible feedback).

**How a use box is found** (why the layout is what it is):
- `RaycastEntityDetectorComponent.cs:108-280`: the use ray must hit the block's collider (the precise collider for
  blocks); the dummies of that block's model and of its descendants whose box the eye-to-hit line crosses are
  candidates. Subparts have no collision, so a ray through the popped drawer or screen runs on to the KVM's face.
- `InteractorEntityComponent.cs:83-117`: candidates by descending index (the later dummy wins a tie); skipped when its
  SupportingFracture is dead, its type is unbound, or the block is not Functional.
- A use box on a subpart model would not work: `UsePowerableAction` reads `PowerableBlockComponent` from the dummy's own
  entity (`:30, :38`), which a subpart lacks. The boxes are on the block model.
- A custom hint ("Press F to pop out the console") would need our own UsePowerableDefinition plus an entry in vanilla's
  single global UseActionBindings dictionary (an Override of a vanilla definition every mod shares, delta encoding of a
  dictionary unverified). Not done: the vanilla wording under the block's name is clear enough.

**The layout** (`dc/functional.py` KVM_TOGGLE, KVM_TOGGLE_BOX, KVM_TERMINAL_BOX; `integration.patch_kvm_dummies`):

| box | type | face band (b) | width (a) | depth (d) |
|---|---|---|---|---|
| KvmToggle (new, last dummy) | UsePowerable 504d93cd | -0.125 .. -0.026: the bezel's bottom rail and the bay mouth (stowed fascia, pull bar, latch tabs) | +-0.212 | -0.0275 .. 0.0325 (fascia back to past the pull bar) |
| Terminal (shrunk from the whole face) | UseTerminal b15d441f | -0.015 .. 0.119: the modules above the header lip and the bezel's top rail | +-0.212 | +-0.025 (vanilla) |

- The 11 mm header lip between them belongs to neither, so the boxes never overlap.
- Stowed: the pull bar pops it out; the OSD and the port keys open the terminal (from any height).
- Out: the screen stands in front of the upper modules, so aiming at the screen opens the terminal (a console behaves
  like one); the lid's bottom edge, the hinge over the drawer, reaches the drawer band and stows it.
  `dc/functional.kvm_use_target` models it; `test_kvm_use_targets_feel_natural` holds it for eyes level with the KVM
  up to 0.6 m above it. The screen's upper half covers the slot above, so rays through it reach the neighbour's face
  (its terminal), as Task 8 concern 5 noted. From well below a high KVM, the hinge target is out of reach: use the
  terminal's On/Off.
- SupportingFracture: the toggle is supported by the zone holding it (`fracture.Plan.zone_at` over the export
  manifest's zones): since Task 9c's 3-zone servers (Fracture_01 the critical core, Fracture_02 the front service
  module, Fracture_03 the rear) that is Fracture_02, the FRONT module (not the critical zone), as vanilla supports its
  ButtonTop01 boxes. The KVM's Terminal (and the functional servers' Terminal / LcdPanel) are supported by the same
  front zone (Task 9c, the manifest's "supporting"). None on a non-breakable build (the validator forbids it).
- A thin face slab cannot misfire from a distance: a deep box covering the popped drawer was rejected, because a ray
  aimed at the stowed upper panel from below would cross it and select the toggle.

**Tests.** `Tests/test_kvm_programmable.py` `test_kvm_use_toggle_dummy` (the vanilla binding, the type, the boxes over the
fascia and the modules, disjoint, inside the face, last, supported by the front zone (as is the Terminal), none on the subparts) and
`test_kvm_use_targets_feel_natural`; `test_functional_servers.test_interaction_dummy_on_face` now covers both boxes.
Mutations that fail them: the old whole-face Terminal, a toggle over the bay only, no support, the Terminal type on
the toggle, a toggle too shallow for the pull bar.

**Previews** (local, not tracked): `Source/Model/preview/plan4/kvm_use_boxes_{front,3q}.png` (stowed and out, the boxes
as ghosts) and `kvm_use_rays_side.png` (use rays from a standing eye through the out lid, coloured by the box they get).
`DC_PREVIEW=plan4 DC_SHOTS=kvm_use blender -b --python Source/Model/build_dc.py -- DC_Srv_KVM` (`dc/preview_use_boxes.py`).

**In game:** INGAME-CHECKLIST §12f (both modes) and a "Decisions to confirm" line.

## Plan 4 Task 11: polish pass (2026-10-18)

No behaviour change in the game: the motion, the tuning and every decision are as Task 9 left them. The CoreTests
dump after the refactor is byte-identical to the one before (all 9 files). Report: the scripts SDD folder,
`task-11-report.md` (every carried Minor, fixed or left, with the reason).

- **One responsibility per file, every file at most 200 lines.** `CompositionSurgery` is a partial class over
  `CompositionSurgery.cs` (apply, roll back, shared validation), `.Add.cs` and `.Swap.cs` (the two preparations), with
  `SurgeryEdit.cs` and `CompositionReflection.cs` (the two reflection targets) beside it. The Programmable lamp's
  reflection moved to `SwapperReflection.cs`; both seams use `DcReflection.cs` (Find, Unwrap). The KVM:
  `KvmInjector.cs` (what to edit) and `KvmInjectorPostProcessors.cs` (when); `KvmPartDefinitions.cs`,
  `KvmPartComponent.cs` (the base) and `KvmPartDrivers.cs` (drawer, screen) replace `KvmPartComponents.cs`;
  `KvmRackLink.cs` (state, view) and `KvmRackLink.Lookup.cs` (resolution), with the GUID table in `KvmRackTable.cs`;
  the core's `KvmMotion` over `KvmMotion.cs` (stepping, settling), `.Sequence.cs` (gates, beat, stops) and
  `.Spring.cs` (the integrator), with `KvmPose.cs`, and `KvmInterlock.cs` out of `KvmSequencerCore.cs`.
- **No allocation in a job.** `KvmSequencerCore` builds both motion paths up front and a path change switches between
  them (it used to allocate a new motion); CoreTests `runtime.update_allocates_nothing` (20000 frames, door flicker,
  path switches: 0 bytes; it fails with 5104 bytes on the old code). The door mapping moved into
  `KvmRackLink.FrontDoor`. The `Entity.Has` conditionals are static method groups (compiler-cached delegates). The only
  job-path allocations left are the fault log lines, at most `MaxFaults` per part or sequencer.
- **Log lines.** One per injection: `CompositionSurgery.Apply` logs `<what>: N edit(s): a; b; c` (the KVM's three
  per-edit lines and its `KVM: scripted` summary are now that one line; INGAME-CHECKLIST §12e updated). One per fault
  kind (DcLog.Once keys), none per frame.
- **Warning hygiene** (`Tests/CompileCheck/run.sh all`; `--docs` now lists the doc-comment warnings too):
  - KN023 (static state): 3 + 7 → 0. Session state lives in singletons, the pattern the analyzer allows: `DcLog`'s
    once-memory, `KvmInjector`'s outcome, the two reflection seams (`CompositionReflection`, `SwapperReflection`);
    `Entity.Has` conditionals are method groups.
  - KN026 (catch Exception): 10 + 13 → 9 + 10. Removed where no exception can arise (`Describe` reads two
    auto-properties; `WorkingOrFalse` reads a field-backed getter, null-checked) or where a catch only duplicated the
    job's own (`KvmPartComponent.Drive`); the two reflection `Find`s are one (`DcReflection.Find`). The rest are the
    plan's defensive boundaries (every job, scene listener and post-processor body; the transaction's rollback; the
    log itself), which must catch everything: kept. An always-true exception filter would silence the analyzer but
    not change the code, so none is used.
  - KN041: 2, kept (the plan's names `KvmDrawerPart` / `KvmScreenPart`).
  - CS8509: 4, in the game's own generator output for the two `[Serialize]` definitions (not our code).
  - Doc comments: 4 + 2 of ours → 0 (`<inheritdoc/>` on the overrides, the `OnceGate` constructor); the 120 left are
    all in generator output.
- **The in-game probe compiles offline.** `Tests/CompileCheck/run.sh probe Source/Model/review/probe_scripts.csx`
  compiles a probe the way the SeMcp2 plugin does (its default usings and its `__REPL__.Run()` iterator wrapper,
  accessibility checks off) against every managed Game2 DLL (`Tests/CompileCheck/ProbeCheck.cs`): 0 errors, 0
  warnings. A planted bad type name fails it at the right .csx line.
- **Dump freshness by content.** A passing `CoreTests --dump` stamps `core_sources.sha256` (the SHA-256 of
  `Scripts/Client/Core/*.cs` then `Scripts/Simulation/Shared/Core/*.cs`, the two folders CoreTests compiles; CRLF read
  as LF; the shared folder was added after the Task 11 review); `dc/kvm_motion.core_sources_digest` computes the same, and the
  freshness tests compare the two instead of mtimes. The conftest `trajectories` fixture regenerates a stale or
  absent dump (about 3 s), so the Task 6 geometry checks run on a fresh clone too (the dump is untracked).
- **Data-only check.** Script tests carry the `scripts` marker (`test_scripts_layout`, `test_kvm_runtime`,
  `test_kvm_sequence`, three in `test_programmable_data`); without `Scripts/` they skip and every data test runs.
- **Lint.** `bare_has_calls` skipped generic commas only by luck: a `.Has(out Dictionary<A, B> x)` with no conditional
  passed. It now tracks type-argument brackets in the `out` declaration; `test_has_lint_bites` covers nested generics.
- **Small carries.** `functional.KVM_FACE_PLANE_Y` is now `subparts.FACE_Y` itself (Task 9 M3, one source). The 60 Hz
  check of `kvm.reversal_is_continuous` is named a sanity bound (Task 5 M3); the 240 Hz checks carry the weight.
- **Left as is (see the report):** the close's soft landing (StopPreload 0.025: 5 cm/s, the last 4 cm in 0.35 s; the
  user approved this feel), `ForceInstantiation` on the post-processors (the pattern proven in an earlier prototype; dropping it
  cannot be verified offline), the Programmable prefabs' per-bundle versions (Game2 2.4.0.95 beside VRage 2.3.0.467
  is correct: each bundle states the format of its own content, vanilla mixes them too, and VRage has migrations
  between those versions that a blanket 2.4.0.95 would skip), the PSU lamps staying amber (a user decision).

## Plan 4 Task 12: enabling scripts (docs) (2026-10-18)

The player-facing text is README.md, "Enabling scripts (optional)" (what `-loadScripts` is, how to launch, ON versus OFF,
multiplayer, troubleshooting); its developer half is "Developer notes: scripts". This section is the maintainer's
summary. Every command below was run in this plan except the ones marked "in game".

- **The switch.** Mod C# compiles and loads only with `-loadScripts` (`GameApp.cs:330-333`); without it the whitelist and
  MetaDatas are empty and `Scripts/` is silently ignored. `se2mod.py play DataCenter [--native]` appends it whenever the
  mod has `Scripts/` (`se2mod.py`, `cmd_play` / `play_native`). `se2mod.py build` hides `Scripts/` from the SDK builder.
- **Architecture in brief.** Two script assemblies (`DataCenter.Simulation`, `DataCenter.Client`); load-time
  `[DefinitionPostProcessor]` surgery only (no script type ever reaches a server entity or a save); the KVM is a
  client-only sequencer with its own part-driver definitions (P4-3, P4-10); the Programmable's scripting component is
  in the data (P4-1 A'); all motion maths is game-free (`Scripts/Client/Core`) and tested natively.
- **Rulings as shipped.** P4-1 A' (component always in the data; Run with scripts off is a compile error, text kept),
  P4-2 (Programmable as a terminal-listed On/Off blade), P4-3 (client-only KVM), P4-4 (door interlock, fast stow; no
  door-time change was needed), P4-5, P4-6 (GUIDs generated), P4-7 (status lamp green; PSU lamps stay amber), P4-8a (KVM
  Use-to-toggle), P4-8b (fan tray, done in core), P4-9 deferred (85 degree cap), P4-10 (own definition types), P4-11
  (feel beats the settle budgets), P4-12 (42U top slot uses the data-only path), P4-13 (the interlock checks the door on
  the KVM's face side only).
- **Reflection and engine points to re-check after every game update.** The composition `Assign(Builder)` and prefab
  `_entity` (CompositionSurgery), the `InGameScriptingDefinition` / `BlockMaterialSwapperDefinition` fields (status
  lamp), the door state and `OpenRatio` reads (KvmRackLink), the ChildTransform and OnUpdateRigidAnimation job groups,
  `Entity.Has(out T)` (engine assertion if unguarded; lint-tested). The ranked list is
  `docs/reference/our-game-dependencies.md` (checker: `docs/reference/check_dependencies.py`).
- **Workflow commands.** `bash Tests/CompileCheck/run.sh all` (0 errors, Simulation then Client);
  `cd Tests/CoreTests && dotnet run -c Release` (`OK: N checks`; `-- --dump <dir>` writes the trajectory CSVs, `routing.json`
  and `core_sources.sha256`; `--verbose` prints measurements); `python3 -m pytest -q Tests`; previews
  `DC_PREVIEW=plan4 blender -b --python Source/Model/build_dc.py -- <block>`; the in-game probe
  `tools/scripts/se2game.py exec -f Source/Model/review/probe_scripts.csx` (in game).
- **Post-update re-check (Hostile Encounters, `docs/research/se2-upcoming-update-hostile-encounters.md`).** Scripting is
  not announced for it. After updating: CompileCheck (whitelist or API drift shows as compile errors), CoreTests, the
  dependency checker, then the in-game checklist section 12 with scripts ON. The new damage system may also change the
  fracture and breakable validators the Programmable and KVM rely on (section 10 of the checklist).
- **Never** print or paste the se-mcp plugin's `SeMcp2.cfg` or its token; `se2game.py` reads it itself.

## Plan 4 Task 13: the in-game checklist (2026-10-18)

INGAME-CHECKLIST.md section 12 is one ordered pass (12.0 to 12.9) that consolidates the old 12 to 12f items and every
in-game check carried by the task reports and reviews. Its "Decisions to confirm" list is at the top of the section.
The digest of the core sources now includes `Scripts/Simulation/Shared/Core` (Task 11 review minor), tested by
`test_core_digest_covers_shared_core`.

## Placement fix: servers into racks (2026-10-18)

Report: ../../docs/superpowers/sdd/data-center-ingame/placement-fix-report.md. The placer targets the first OCCUPIED
cell its ray crosses (BlockPlacementAlignment.cs:478-547), so the front-zone occupancy sealed every slot.
- Rack collision: no occupancy hints; a 2 cm physics rear stop plate 3 mm behind each slot's back plane (claims the
  rear-zone cells); the slot's mount hints (rails, slot floor, slot ceiling) only on its REAR row; the plinth deck
  and the tray floor's underside 25 mm off the slot planes (no render mounts); rear stop brackets (render) on the rear
  rails. The plate is not in any fracture zone (fracture.UNFRACTURED_BOXES).
- Servers: mount directions without Up (integration.SERVER_MOUNTS / UPS_MOUNTS, deco servers too): otherwise a server
  one cell forward validates on top of a seated server below.
- KVM rack link: falls back to the rack BESIDE the KVM (KvmFrontCell.Beside / Contains) when the front cell is no rack.
- dc/placer_emu.py emulates the placer; Tests/test_rack_targeting.py, test_rack_placement.py use it / the report.

## Merge main -> plan3-room (2026-10-19)

Merge 4cc1dae3 (main f5211380: Plan 4 scripts, Plan 2 final, the in-game fixes) plus one follow-up commit. Report:
`../../docs/superpowers/sdd/data-center-room/merge-main-report.md`.

- **Racks: both sides kept.** Room T1's PDU column (bulkhead, FEED plate, plinth receptacle; the baked rear strip
  stays removed, Ruling P3-20) on main's placement fix (rear stop, rear-row keyed mounts, MOUNT_CLEAR deck / tray floor,
  rear stop brackets, the open front-zone row). `rack.OPENING_CELLS` (new); `rack.FREE_CELLS` = slots + opening row +
  both PDU columns. Occupancy 42U 120/200 (was 136 on each side), 24U 60/100. Golden summaries and costs re-recorded
  (Rack42 Open: 9 Steel Plate + 7 Construction, plus 7 Steel Plate). The half rack's front label pad now sits over two
  free cells (the top slot's opening row), so its Up plane loses them (50 %, 6 groups): a rack label on a half rack
  mounts on the back pad only (see the report's concerns).
- **Z-fight (main's test_zfight on the merged racks):** the CONTAINMENT tag lift 0.6 mm is now `_contain_rail`'s
  default (`rack.CONTAIN_TAG_LIFT`; T11 deferred R2). Room T1's FEED A/B + ZERO-U PDU stencils sat 0.1 mm over their
  plate and the receptacle letter 0.1 mm over the gland plate: the stencils now stand 0.6 mm proud (still 1.5 mm
  outside the PDU envelope) and the gland plate's top drops 0.5 mm (the socket, measured, is unchanged).
- **Controller ruling: no baked rack ID.** The front header / half-rack kick plate say "RACK" beside a blank Brushed
  write-on tag (`rack.id_tag`, riveted, geometry only); the side hatch placard says "RACK ID" over a larger blank tag;
  the half rack's roof plate says "RACK" with a blank tag over the barcode. The ID is the editable rack-label LCD
  (DC_Sign_Rack). `test_racks_carry_no_baked_id`; test_zfight's side-panel label set updated.
- **ConditionalSubParts rule on door-like room blocks:** `test_conditional_subparts_are_bound` now runs on every block
  whose DoorPartsProvider references a ConditionalSubParts definition (the 4 door racks and the 3 containment doors,
  discovered from the package; `test_conditional_subparts_cover_door_like_blocks` pins them). The KVM's and the CRAC's
  ConditionalSubParts are client-composition only (not server-walked) and stay out. All pass.
- Re-exported the 6 racks (windowed), check_placement on them plus the 19 room blocks (their placement_exported.json
  gain main's fbx_sha256 provenance), build_integration, install (0 problems), worktree build 0.
- Previews: `DC_PREVIEW=merge` (dc/preview_merge.py) -> Source/Model/preview/merge-main/.

## Plan 3 Task 12: cost balance, the neutral CRAC header, the hero hall (2026-10-19)

- **Cost balance (`dc/recipes.py`, module doc; `test_room_cost_balance`).** The volume rule left three outliers. Each
  is now a rule that names what is paid for:
  - **Signs pay per screen face.** Each face costs one vanilla LCD50 recipe (3 Electronic Parts, 2 Wire, 2 Glass,
    plus 3 Steel Plate), per `SIGN_FACES`. Vanilla prices its LCDs per screen, not by area: the narrow LCD, the 0.5 m
    and the 2.5 m LCD share one recipe, and the 5 m LCD doubles it. The hanging sign drops from 3.4x a vanilla LCD
    (10 / 7 / 7 + 10) to 2x, which is vanilla's LCD500. The aisle sign and the rack label each cost 1x.
  - **In-row units pay the rack frame plus a kit.** The CRAC and the PDU cabinet stand on the rack's footprint and
    frame (Decision 6). Each pays the 42U open rack's frame (`INROW_FRAME`, by the volume rule: 9 Steel Plate,
    7 Construction, plus 7 Steel Plate) plus its machinery (`INROW_KIT`):
    - CRAC: the gyroscope's 3 Motor and 2 Wire (its fans and wiring);
    - cabinet: 1 Electronic Parts and 2 Wire (meter, breakers, busbars).

    Before, the decorative cabinet cost 23 Steel Plate from the wall panel's heavy mix at 200 cells, against 14 for
    the powered CRAC from the gyroscope's light mix. Now both carry the frame's 16 plates, and the CRAC is dearer
    (710 against 640 kg of items).
  - **Frame floor (`FRAME_FLOOR`).** No rack costs less, by item mass, than the dearest server it can hold. The
    shortfall is paid in the frame's optional Steel Plate. The 24U Open rack was the only one under it (370 against
    the Timer's 375) and goes from 4 to 5 optional plates (405).
  - Every block's game scale stays 1.
- **CRAC header:** "CRAC 01" is now the neutral "CRAC" caption (`crac.UNIT_CAPTION`) with a blank riveted Brushed
  write-on tag (`rack.id_tag`, LOD0) on the Darker plate, the racks' treatment. The z-fight audit is clean, and the
  LOD budget is unchanged at LOD1 (the tag is LOD0 only). DC_CRAC was re-exported (`test_crac_caption_is_neutral`,
  `test_crac_carries_no_baked_id`).
- **The hero hall (`room.two_aisle_room`, `dc/preview_p3t12.py`).** Three rows: a contained 1.5 m cold aisle (rows A
  and B face it) and a contained 1.0 m hot aisle (row B's and row C's backs). The layout is the two reference rooms
  with the hot one shifted onto row B, on one raised floor. Previews are in `preview/plan3-task-12/` (not
  committed):

  ```
  DC_PREVIEW=plan3-t12 blender -b --python Source/Model/build_dc.py -- "DC_Rack42_SplitFront" "DC_Srv_*"
    "DC_Tray_Drop_Full" "DC_Tray_StraightS_Full" "DC_TrayRods_100" "DC_Floor_*" DC_CRAC "DC_PDU_*"
    DC_Contain_Door_150 DC_Contain_Roof_150 DC_Contain_Door_100 DC_Contain_Roof_100 "DC_Sign_*"
  ```
- **Finding: doors on a shared row (`room.shared_row_doors_fit`).** A row between two contained aisles carries both
  aisles' end doors on its end racks. Each door's leaf pocket reaches W/2 beyond its aisle, so the two pockets share
  the row's 1.25 m depth. These pairs fit: 1.5 + 1.0, 1.0 + 1.0 and 1.0 + 1.5. Two 1.5 m aisles, or any pair with a
  2.0 m aisle, collide (cell conflicts). This is documented for players, and `two_aisle_room` refuses those pairs.
- **Probe:** `Source/Model/review/probe_mountpoints_room.csx` is the Data Center probe (itself adapted from an earlier prototype's,
  which is never edited) with the room blocks' names; it compiles (`Tests/CompileCheck/run.sh probe`, 0 errors).
- **Docs:**
  - `INGAME-CHECKLIST.md` opens with the 2026-10-19 test session and gains §13 Room pieces: the room decisions,
    items 1-16 (15 N/A, no looms), and the T7 and T8 details folded in.
  - `README.md` gains a Room Pieces section.
  - `Tests/test_room_docs.py` pins all of it.

## Plan 3 summary: room pieces (2026-10-19, Task 12)

19 blocks in four build-menu tiles after Cable Tray Supports: **Raised Floor** (Solid / Perforated x 0.5 / 1.0 m),
**Room Cooling & Power** (CRAC, PDU Cabinet, Rack PDU Feed A / B x 24U / 42U), **Aisle Containment** (Door, Roof x
1.0 / 1.5 / 2.0 m) and **Signs & Labels** (Aisle Sign, Hanging Aisle Sign, Rack Label). Task 9 (cable looms in the
vertical managers) did not run (parked; the loom group is absent).

### Decisions 1-14 (Rulings P3-1..14) and how they shipped

1. **CRAC = a Gyroscope250 clone with the GyroscopeComponent removed (P3-1, amended by P3-15).** It shipped with no
   fallback (see the shipped chain below).
2. **Containment doors = SlidingDoorNarrow250 clones**, 2W wide in the 0.25 m slice just beyond the row end, bolted to
   the end racks' sides. Leaves are W/2 + 30 mm with 15 mm overlap per side, each with its own collision asset, so they
   block while closed (P3-16). OpeningDuration is 1.0 s and the sound is the vanilla DoorSliding.
3. **Roof panels = DeckPanel250 clones**, 1.0 m x W. They mount on the racks' containment rail, the door header and each
   other. AutoRotateFace is null, the panes are FrostedGlass with FIRE RELEASE links, and they go on full-rack rows only.
4. **The rack change (T1):** a containment rail and Forward/Backward hints in the top band. The rear PDU columns are
   freed, with a plinth receptacle. The half rack gets top-rim label pads. The baked rear strip was removed for the
   placed strips (P3-20).
5. **Raised floor = CatwalkSquareBase250 clones**, 0.25 m high, Solid or 25 % Perforated, in 0.5 and 1.0 m tiles
   (`clone.ALSO` CatwalkSquareBase_250, P3-17).
6. **In-row units share the rack footprint** (4 x 10 x 5 cells): the CRAC and the PDU cabinet carry the rack's own
   plinth, corners, rail and top-entry brush plates.
7. **PDUs are decorative:** a floor PDU cabinet (WallInsertPanel chain) and zero-U strips, Feed A in the right column
   and Feed B mirrored in the left (seen from the rear), in 42U and 24U lengths. Each inlet seats in the plinth
   receptacle. Outlet and inlet positions are single-sourced in `dims.py`, ready for future cords.
8. **Signs = LCDNarrow50 clones:** the Aisle Sign (4:1, 1024 x 256), the Hanging Aisle Sign (two surfaces, hung on a
   1.0 m Hanger Rod) and the Rack Label (2:1). Their editable LCDs need `clone.ALSO` NarrowLCD50 (P3-18). Hot and cold
   are shown by the frame's paint.
9. **Looms (optional):** not built. Task 9 is parked.
10. **"Unfractured" was superseded** by the user's breakable direction. Every room block fractures on main's
    `dc/fracture.py` plan, with its own Damaged model (floor in-plane, roof per bay; counts per family).
11. **PCU as the vanilla source:** floor 5, roof 5, PDUs 5, signs 35, CRAC 30, doors 150.
12. **Build menu:** four tiles (orders 800-1100); the loom tile is absent (P3-12).
13. **Glazing:** vanilla FrostedGlass (roof) and WindowGlassThin (door leaves), with the material GUIDs added
    (P3-19). The MetalPerforationSteel fallback was not needed offline; check it in game.
14. **Animation:** the CRAC fans use InfiniteRotation on Working (600 deg/s, a 2 s soft start, a 4 s coast), and the
    door leaves use DoorSegmentTransformSLERP. The discharge louvres were rejected (the RotationAnimation load bug,
    Q1).

### Shipped CRAC chain

Gyroscope250 is cloned with its **GyroscopeComponent** removed from the server composition and the server prefab (the
same delta form as the KVM's On/Off), and its GyroscopeDefinition file is dropped. The clone keeps:
- the PowerableBlockDefinition: ConsumedResource Amount 25, priority 6, a real grid load;
- terminal On/Off and Working;
- the FunctionalBlockAnimationController and ConditionalSubParts, which spawn three `CracFan` InfiniteRotation rotors;
- the BlockMaterialSwapper, which lights the RUN lamp while Working;
- the BlockEffects hum (GyroscopeMID, set explicitly).

The ControlPanel25 fallback was not needed. Task 11 added two decorative O2 / COOLANT SERVICE ports (vanilla small
conveyor-port frames, blanked) with inert dummies `conveyor_port_o2_1/2` for a future data-only switch-on. Task 12
made the header neutral ("CRAC" and a blank tag).

### Provenance (`build_report.json` "provenance" per block)

- All geometry is generated by `dc/floor.py`, `contain.py`, `crac.py`, `pdu.py` and `signs.py`. The in-row units reuse
  `dc/rack.py`'s plinth, corners, rail and brush plates.
- Vanilla kit parts: the CRAC's small conveyor-port frame (`O2Generator250.fbx` ConveyorPortSmall_Border, read-only
  import).
- Vanilla materials: MetalPerforationSteel, FrostedGlass, WindowGlassThin, EmissiveWhite, Rubber, FracturedMaterial01
  (the break faces), and the AtlasDecal_Stickers02 chevrons and hazard placards.
- Glyphs: AtlasFont_BarlowCondensed_CleanWhite.
- Mechanisms are the cloned vanilla blocks: Gyroscope250, SlidingDoorNarrow250, LCDNarrow50, DeckPanel250,
  CatwalkSquareBase250 and WallInsertPanel.
- No assets come from other mods.

### Budgets (LOD triangles / the limit, `se2model.limits`; materials LOD0 -> last)

| Block | LOD0 | LOD1 | LOD2 | LOD3 | Materials | Colliders |
|---|---|---|---|---|---|---|
| Floor Solid 0.5 m | 2496 / 8437 (30 %) | 312 / 1421 | 84 / 236 | - | 4 -> 1 | 2 |
| Floor Perf 1.0 m | 8332 / 12499 (67 %) | 1380 / 2208 | 332 / 508 | - | 7 -> 1 | 2 |
| CRAC | 14414 / 16072 (90 %) | 3464 / 3696 (94 %) | 1220 / 1282 (95 %) | 144 / 156 | 8 -> 1 | 3 |
| PDU Cabinet | 13574 / 16072 (84 %) | 3184 / 3696 (86 %) | 712 / 1282 | 48 / 156 | 8 -> 1 | 3 |
| Rack PDU 42U | 6602 / 10460 (63 %) | 1266 / 1749 (72 %) | 188 / 329 | - | 8 -> 1 | 1 |
| Rack PDU 24U | 3862 / 5524 (70 %) | 800 / 947 (84 %) | - | - | 8 -> 1 | 1 |
| Door 1.5 m | 5464 / 17402 (31 %) | 1284 / 4251 | 288 / 1570 | 72 / 197 | 6 -> 1 | 4 |
| Roof 2.0 m | 4960 / 13042 (38 %) | 1552 / 2434 (64 %) | 372 / 625 | - | 6 -> 1 | 2 |
| Aisle Sign | 1224 / 6489 (19 %) | 284 / 1104 | - | - | 5 -> 1 | 1 |
| Hanging Aisle Sign | 1744 / 6028 (29 %) | 488 / 1029 | - | - | 6 -> 1 | 1 |
| Rack Label | 870 / 4252 (20 %) | 266 / 741 | - | - | 4 -> 1 | 1 |

The last LOD of every block is the 12-triangle box. Over the 70 % aim: the CRAC (LOD0-2) and the PDU cabinet and strips
(LOD1). All are within the limits.

### Builder findings (Plan 3)

- **Spaces in vanilla file names:** Gyroscope250's block-definition file name contains a space. The clone writes
  `DC_CRAC_PowerableBlockDefinition.partialdef`.
- **Second FBX prefixes:** a second FBX prefix needs `clone.ALSO` (CatwalkSquareBase_250, NarrowLCD50).
- **Cost-source cell box:** the cell box of a cost source with several convex colliders is the union of its glTF
  colliders on the 0.25 m grid. The sliding door has none (a Havok .hkt), so its FBX bounds are used.
- **Door leaf colliders:** they need a collision asset per leaf subpart (P3-16).
- **ConditionalSubParts:** a block whose DoorPartsProvider references ConditionalSubParts must bind every subpart
  prefab. The merge's `test_conditional_subparts_are_bound` covers the 4 door racks and the 3 containment doors.
- **Z-fight audit (`dc/zfight.py`, `zfight_room.py`):**
  - Decals sit at least 0.6 mm over their plate (`CONTAIN_TAG_LIFT`).
  - Sliding leaves are never coplanar with their frame.
  - White stencils sit only on non-paint (Darker or Yellow) plates.
  - IDs are geometry (`rack.id_tag`), never decals.
- **LCD surfaces:** two surfaces on one LCD clone work through MeshPartName. A 4:1 aspect needs the explicit
  1024 x 256 resolution and AspectRatio 4 (P3-18).
- **Fracture counts:** they are per family (`ROOM_EXPECT`), never a hard-coded total (69 blocks and 138 models
  before Task 12).
- **FBX re-exports are not byte-stable:** the header's CreationTime and FileId change on every export. Commit FBX
  only for blocks whose geometry changed.
- **Shared-row doors:** see `room.shared_row_doors_fit` (Task 12 finding).

### Cost balance

See Plan 3 Task 12 above and the `dc/recipes.py` module doc:
- signs cost per screen face;
- in-row units cost the 42U frame plus their kit;
- racks are floored at the dearest server.

### Known limits and carries

- In game, everything is unverified (INGAME-CHECKLIST.md §13). The test session on 2026-10-19 comes first.
- On a 24U rack, the rack label mounts on the back pad only (the front pad's cells were freed for the top slot). A
  dedicated half-rack front mount is a later option.
- In a contained aisle, the rack-top labels and the hanging sign sit above the roof. Label the open edge and sign the
  doors (T11 guidance).
- After the "Hostile Encounters" update (2026-10-19), re-validate the fracture and damage data against the new damage
  system before testing.
- Looms (Task 9) and neighbour-aware live cords are in the ideas backlog.

## Final review fixes (2026-10-19)

Review: `docs/superpowers/sdd/data-center-room/final-review.md`; report: `final-fixes-report.md` beside it.

- **I1, PDU strips seat only at the column bottom.** The strips mounted Forward (brackets on the bulkhead) and Down
  (plug on the plinth). The placer centres the strip on the aimed cell, so on a 24U rack an aim at the upper half of
  the column raised it one or two cells, out through the open top, and it validated on the bulkhead (any one mount
  cell is enough). The suggested fix (cut the rack's `pdu_bracket` hint to the bottom row) does not work: measured
  with `build_dc.py` on DC_Rack24_Open, the column still mounts Backward on all 4 cells, because the bulkhead's render
  face lies 0.5 mm inside the bracket plane and the generator samples the render (20 mm tolerance). So the strip now
  mounts **Down only** (`pdu.strip_collision` drops the bracket hint; `strip_directions` = "Down"). A raised strip's
  bottom faces an empty column cell and stays red; the seat validates on the plinth's `pdu_seat`. On the 42U this
  also removes a second mis-seat the new test found: a strip behind the rack hung by its Forward face on the rear
  containment rail band. `Tests/test_pdu_targeting.py` (placer_emu, all 6 racks x 2 feeds x 3 neighbourhoods):
  the plinth-top aim and the bulkhead aim at the strip's centre cell seat it; over the aim fan no validating ghost
  touches the rack box except the seat; a ghost outside stands on the rack top (Down on an Up face, expected).
  It fails on HEAD's data (24U: 594 mis-seats per rack and feed; 42U: 81 hung on the rear rail band). Unchanged by
  the fix and recorded in the checklist: a strip still stands on any Up face (floor tile, rack top, an empty slot's
  floor if aimed into a server slot), and a player can turn it before placing.
  Re-exported the 4 strips (only the NonFractured collision changes: the hint node; the Fractured / Damaged files
  and export.json's dent stats were restored from HEAD, their re-export is churn: Blender name suffixes and a dent
  that differs run to run), check_placement on them, build_integration, install `--apply` (12 files), build.
- **M1, placer_emu sees the rack's outside.** `build_dc.build_rack` writes `placement.mount_cells` (every mount cell,
  the box faces included; trays already had it) and `placer_emu.rack_block` uses it (it refuses a report without).
  `test_no_aim_mis_seats` now also classifies ghosts wholly outside the box: a high, close aim at the top slot can
  meet the rack's outside first and place a server on the top or, on a full rack, hung on the containment rail band.
  Asserted: such a ghost is held only by outer-face mount cells and never reaches into the box. Nothing else showed.
- **M2:** `test_no_client_types_on_server_compositions` (test_definition_validators) ports
  `ConveyorGraphPostProcessor.ValidateClientTypes`: over all PrefabBindings, no type a server composition inserts is
  from a client assembly, and no type a client composition inserts is `[ServerOnly]` (types resolved in
  `tools/decompiled`; skipped without it).
- **M3:** the 24U golden in `test_tray_rack_interface` now says the front label pad not mounting is an accepted
  regression with a pending follow-up, so re-recording it later is expected.
- **M4 / M5:** checklist §13.2 and the test-session list updated (strips: Down only, seat at the column bottom,
  stand on any Up face; two contained 1.5 m aisles cannot share a row, use 1.0 m).
- **Tests stage into a per-run temp dir** (`Tests/conftest.py` redirects `config.STAGE_ASSETS` before
  `dc.integration` is imported), so concurrent pytest runs no longer race on `Source/Model/integration/Assets`
  (build_integration.py and install.sh still use it; `install.sh` takes `DC_STAGE_SRC` for the dry-run test).
  `Guids.save` writes asset_guids.json atomically (temp file + rename).

## Plan 5 Task 2: the stage generator in the mod (2026-10-19)

- **Ruling DB-1: `Source/Model/dc/construction.py` is the mod's stage generator.** It is a fork of
  `tools/se2model/construction.py`, which is left unchanged and is **superseded for the Data Center** (`tools/` is not
  versioned, so a fix there could not be committed per task; the earlier prototype keeps its own copy).
  `dc/integration.py` imports `dc.construction`.
- **G9, the stage-1.0 damaged-only hide (Decision 2).** `generate_stages(..., damaged_hide=())` writes one
  `ApplyOnlyWhenDamaged` hide per `damaged_hide` part, and `integration.patch_model_def` passes
  `construction.scaffold_parts(parts)` (the sorted Scaffold-type FR LOD0 mesh parts). No block has a scaffold yet
  (Task 6 adds it), so every block's last stage is now `PartChanges._data == []`: the stray hide of `"Chrome"`, a mesh
  part no block has, is gone. The empty form is vanilla's own: 36 of the 223 `BuildProgressModels` lists in
  `tools/vanilla-ref/Blocks` end with `[]` (TrussBlock50, InteriorWallCornerWithSide250, the piston stages, ...);
  `Tests/test_stages.py::test_empty_last_stage_form_is_vanilla`.
- **4.0 presets** (SDK `System/Configurations/ConstructionPresets/*`, GUIDs checked against the SDK files):
  `windowglass` T = S = `83c075f5` (Task 5's glass role), `subpartconstruct` T = S = `851d4d6e` (Task 8's stand-ins).
  The SDK's `GratingMetallic` (T `2cc33fe2`, S []) is **left out**: no role and no later task uses it (preflight D5;
  the dedupe ruling forbids unused presets). Add it with its first user (e.g. a Perf-floor grating role).
- **Proof:** `test_installed_stages_regenerate` (every block's installed stages == `generate_stages` from
  export.json with its seed) and `test_installed_stages_match_baseline_except_last` (the R3 hash equals the Task 1
  baseline for all 73 blocks; the last stage keeps ratio and model, its changes are []). The evaluated part states of
  every shot are equal before and after except the absent `Chrome` key at `done_damaged`, so the renders cannot
  change; the t2 sheets' non-zero pixel columns are EEVEE noise (a re-render of the same inputs differs by up to 4 %).
- Rebuilt: build_integration, install `--apply` (73 BMDs overwritten), SDK build (`Exiting with 0.` twice). A first
  SDK build attempt died on a Wine `UnauthorizedAccessException` in `Content.tmp` (a temp dir created without the
  execute bit); the retry passed and the leftover `Content.tmp/` was removed.
- Part -> purpose: no geometry changes in this task.

## Plan 5 Task 3: the damage look (G4) and fragility (G8) (2026-10-19)

- **G4, the Deformed metals.** `fracture.DAMAGED_SLOTS` now also maps `PaintedMetalColorable` ->
  `PaintedMetalColorableDeformed` (`d8847d2a`), `PaintedMetalDarker` -> `PaintedMetalDarkerDeformed` (`ea15e749`, a
  Copy `.partialdef` of the Colorable one with its own textures), `BrushedMetal` -> `BrushedMetalDeformed` (`d2d76bf2`)
  and `Chrome` -> `ChromeDeformed` (`4418666d`), all 4.0 `PBRParallaxMaterialDefinition`s under the SDK's
  `BlockMaterials/` (GUIDs checked against the files: `test_material_guids_are_vanilla_definitions`, which now reads a
  Copy `.partialdef`'s Manipulator Guid, ruling R7). Vanilla does the same: of the 269 Deformed models in
  `tools/vanilla-ref`, Colorable maps to `d8847d2a` in 249/264, Darker to `ea15e749` in 239/251, BrushedMetal to
  `d2d76bf2` in 87/97, Chrome to `4418666d` in 131/134 (e.g. `Timer50_Deformed.model`;
  `test_deformed_remap_is_vanilla_majority`). The slot names (mesh parts) are unchanged, so the player colour stays
  on the Colorable one through its colour mask. Reach: 69 Damaged models; Darker on 69, BrushedMetal on 63, Colorable
  on 62; no block has a Chrome slot yet (the mapping is kept for the first one). `export.json`'s `damaged.slots`
  (informational, written by the Blender export) still lists the old table until the next `--export`.
- **G8, fragility** (`integration.FRAGILITY`: the SDK's `Blocks/Shared/Fragility/` Structural `c748fae2`, Functional
  `eaaa3a8d`, Windows `060b61a3`):
  - **DC_Srv_Programmable -> Functional.** `patch_programmable_functional` no longer carries the structural template's
    Fragility (`STRUCTURAL_DEF_VALUES` dropped it) and writes Functional, the `PowerableBlockDefinition` template's
    own value, which every vanilla powerable block (Timer50, ControlPanel25, ...) resolves to. Change for the player:
    MaxHPMassMultiplier 0.8 (was 1.0), projectile damage x0.5 past a 2.4 flat reduction (was x1 past 4): it now
    takes damage like the other functional servers (Timer, EventCtl, KVM, Status, UPS).
  - **Containment roofs -> Windows** (controller ruling): `roof_patch` writes it, as vanilla glazing does
    (`WallInsertWindowFlat150`, `WindowFlat250`, ...): projectile x1.25 past 2.5, explosions x0. With it
    `patch_roof_effects` re-bases the roof's cloned `_StructuralBlockEffectsComponentDefinition` Copy (same GUID,
    still bound in the client composition) from the generic structural effects `9be983e4` onto vanilla's Windows
    BlockEffects `30c64f59` (glass-shatter fracture / death effect `99e7ae3b`, DamageGlassBlock / DestroyGlassBlock),
    and drops the inherited DeckPanel250 `OnDestroyedAudio` (DestroyBlockTiny) so the glass audio applies, as vanilla
    `WindowFlat250`'s Copy (which sets only the construction-state dummy).
  - Resolved per block (`test_fragility_per_archetype`): Functional 17 (door racks 4, Timer, EventCtl, KVM, Status,
    UPS, Programmable, doors 3, CRAC, signs 3), Windows 3 (roofs), Structural 53.
- **Previews:** `preview_mats.deformed_mat` renders the four Deformed materials from the game's `_cm` / `_add` DDS
  (read only, cached in `$DC_TEXCACHE`), paint through the colour mask as the decal atlases.
- In-game (deferred): a shot rack / server shows scratched paint with the player colour; the Programmable's
  time-to-kill under rifle fire; a grenade on a roof (Windows: explosion x0) and the glass-shatter death.
- Part -> purpose: no geometry changes in this task.

## Plan 5 Task 4: damage effects: UPS dummies (G3), spark bands (G7), KVM and Programmable (2026-10-19)

- **Where effects play (R15, decompiled 4.0.0.3151, `tools/decompiled-current`).** A damage band's looped effect
  spawns once per model dummy of its Dummy type (`Game2.Client/.../Effects/BlockEffectsComponent.cs:536`
  `GetDummies`); each instance is stopped when its dummy's `SupportingFracture` zone is dead (`:474-:496`) and spawns
  stopped if the zone is already dead (`:557-:562`). The one-shot death effect (`OnBlockDestroyed`, `:410-:414`) and
  the fracture effect's orientation (`:360`) use `GetDummyTransform` (`BlockEffectsComponentBase.cs:136-:143`) ->
  `ModelComponentDefinition.TryGetDummy` (`VRage.Game/.../Models/ModelComponentDefinition.cs:435-:445`): the FIRST
  dummy of the type in `Dummies` order, with no `SupportingFracture` check. So Decision 8 holds as planned: the centre
  `ParticleEffects` dummy may be supported by a zone and stays the death-effect origin; the per-zone dummies are
  appended after it and never move it (`test_every_band_dummy_exists`).
- **One constant** for the ParticleEffects dummy type: `dc.effects.PARTICLE_EFFECTS_TYPE` (`e9f28118`);
  `integration` imports it (its two copies `PARTICLE_EFFECTS` / `PARTICLE_EFFECTS_TYPE` are gone), as do
  `functional` and `state_view`.
- **G3, the UPS.** `functional.ups_dummies` adds `ParticleEffects 0` / `ParticleEffects 1` (named like the bays'
  `CellSlot <i>`), identity, at the centre of each bay's cell volume (`CELL_DEPTH` / 2 behind the mouth: game z -0.2075
  front, +0.1745 rear); `patch_ups_dummies` supports each like its bay's CellSlot (Fracture_01 front, Fracture_02
  rear). The inherited Production bands (sparks < 95 %, smoke 90-65 %, fire < 65 %) now have a dummy to play on; each
  bay's effects stop with its zone. Controller ruling (follow-up): an unsupported centre `ParticleEffects` comes FIRST,
  as vanilla 4.0 Battery50's, so the death explosion and the fracture effect's orientation play from the block
  centre (before this task: the block origin, no dummy at all); its band effects run until the block dies. The
  unnamed ConstructionStagesParticles dummy stays.
- **G7, spark bands** (`dc/effects.py`, `integration.patch_spark_effects`): the 36 `spark_kind` blocks' cloned
  Structural BlockEffects Copy inserts the vanilla 4.0 band verbatim, read at build time from `tools/vanilla-ref`
  (byte-identical to the 4.0 SDK: `test_spark_sources_are_the_4_0_sdk`), with stable keys `band/<name>/spark(/fx)`:
  - `cable` (27 breakable trays with cables): CableStraight250's, 0-0.99 ElectricalDamageMedium `2113ece5` x1;
  - `breaker` (PDU cabinet, 4 strips, Compute / Storage / Switch / Blank): CircuitBreaker's, 0-0.99
    ElectricalDamageSmall `617b0925` x1. The Empty trays and the non-breakable Chute get none.
- **Spark dummies follow zones** (`patch_spark_dummies`, from `patch_model_def`): the cloned centre `ParticleEffects`
  keeps its key and the block-centre position and gains `SupportingFracture` = the zone whose hull AABB holds the
  centre (largest share on a tie). Long blocks (`effects.per_zone`: trays, the PDU cabinet, the 42U strips) get one
  `ParticleEffects_<zone>` per other zone at that zone's AABB centre (Task 9 refines these onto the cable boxes, R11).
  Controller ruling (follow-up): at most `effects.MAX_EMITTERS` = 3 ParticleEffects-type dummies per block (vanilla
  CircuitBreaker: 1). A block with more zones groups them along its longest axis into the zones below / around /
  above the centre zone; each outer group's emitter sits on its largest zone. PDU cabinet: bottom (01-04, on 03),
  middle (the centre, on 05), top (07 / 08, on 07); Tee / Cross: the centre and the two long-axis arms (the stem /
  short-axis arms spark from the centre dummy). `test_spark_emitters_capped`.
- **KVM** (controller ruling): `patch_kvm_effects` sets the clone's `OnDamagedBlockParticleEffect` delta to 4.0
  ControlPanel25's verbatim (band 0: upper 0.99, ElectricalDamageSmall x0.3, 2.4 key `92d61473` removed); it resolves
  to exactly vanilla ControlPanel25's bands. It replaces the KVM's SmokeSmall set swap (`patch_particle_sets` is now
  UPS-only); the KVM's OnUseAudio hum and the other cloned keys are kept.
- **Programmable**: `patch_programmable_effects` re-bases its Structural BlockEffects Copy (own GUID kept) onto the
  vanilla Timer template `2cad179b` (DC_Srv_Timer's own): sparks < 95 %, smoke 90-65 %, fire < 65 %, the GridExplosions
  death at x0.5 and the Timer's audio (OnUseAudio BatteriesInsertRemove, ExplosionBlockBattery), as a vanilla Timer.
- In-game (deferred): the UPS sparks below 95 %, smokes 90-65 % and burns below 65 %; a tray sparks from the first
  scratch and a section's sparks stop when it falls off; the KVM sparks; the Programmable smokes and burns.
- Part -> purpose: no geometry. Each spark dummy marks where the live conductors are: the cable run of a tray section,
  the breaker / outlet rows of a PDU section, the PSU of a deco server, a UPS bay's cell contacts.

## Plan 5 Task 5: construction roles per face; the roof glass builds as glass (G11) (2026-10-19)

- **Mechanism** (`dc/fracture.py`): every face of a cut Fractured model gets a construction role, `role_of(family,
  part, material)`: `hide` when the material is a decal / stencil / lamp / screen (`HIDE_PREFIXES`, moved here from
  `export_models`; `is_hide` is the one hide test, `role_of` calls it), else `glass` for `GLASS_MATERIALS`, else the
  first role whose `ROLES[family][role]` names the part (exact name, as `KEEP_WHOLE`), else `skin`. `ROLE_PROPS` is
  guide B1 verbatim; `ROLE_SUFFIX` gives the group: skin and glass `Fracture_NN`, `_Hide`, `_Support`, `_Frame`.
  `ROLES` is `{}` for every family here (the family tasks fill it), so only skin, hide and glass occur.
  - `fracture_mesh.cut_object` writes the role as the face int layer `dc_role` (stripped before export);
    `export_models.keep_zone(ob, zi, role)` splits each zone into one object per present role and `_group` gives
    each its group and props; the skin carries `ColliderMeshGroups` = the zone plus every present suffixed group.
  - `fracture.skin_carrier` (R16(b)): a lower LOD without skin faces promotes its first present role in `ROLE_IDS`
    order to carry the zone (as the old hide-only promotion did); a zone with no LOD0 skin face fails by name with
    the roles it has (support-only / glass-only zones cannot reach the importer, which would drop every fracture).
  - The scaffold's damaged-only hide (`construction.scaffold_parts`, Task 2) is a different thing (the stage-1.0
    `ApplyOnlyWhenDamaged` list of Scaffold-type parts) and is untouched.
  - `construction.preset_of` raises on an unknown non-empty preset name (Task 2 review M3: a typo no longer builds
    silently without construction materials).
- **G11, the roof glass**: the roofs' `FrostedGlass` panes are now their own object in the zone's group with the
  `WindowGlass` preset, so the panes show the 83c075f5 glass construction material through both sequences instead of
  the metal build-up. Mesh-part names are unchanged (`Fracture_NN-FrostedGlass`), so saves are unaffected; FR / DM
  triangle counts are unchanged; only the objects per LOD grow (Roof_100 9 -> 12, 150 12 -> 16, 200 24 -> 32).
  The roofs are the only blocks whose stages change (`test_roles_refactor_is_identity`: with the glass props put
  back, their stage hash is the baseline's).
- **export.json**: `fractured.role_tris` (LOD0 triangles per role) and `fractured.role_bounds` (zone -> role -> AABB,
  Blender frame, LOD0).
- **R18, measured shares (LOD0, of the role triangles; the break faces are not a role)**. These are the data the
  later share thresholds (Task 8 support, Task 9 / 10 hide) must be set from; no threshold is set here:
  - racks 1.1 % hide (all six); trays 0.0-1.0 %; rods 0 %; floors 0.0-0.6 %; doors 1.4-1.5 %;
  - servers: Timer 6.6, EventCtl 11.7, KVM 6.0, UPS 6.2, Status 4.4, Programmable 3.6, Compute 8.3, Storage 10.8,
    Switch 7.9, Blank 3.1 %;
  - CRAC 4.6 %; PDU cabinet 3.6 %; PDU strips 1.8-1.9 % (so a ">= 20 % hide" PDU bound does not hold);
  - signs: Aisle 3.8, AisleHang 5.1, Rack 2.3 %;
  - roofs: hide 2.9 / 3.2 / 3.6 %, glass 1.3 / 5.3 / 1.6 % (100 / 150 / 200).
- **Exports committed**: only the three roofs' Fractured / Damaged files and every block's `export.json` (the new
  role keys). A full re-export also rewrote every other block's FR / DM files; those were put back to the committed
  bytes because nothing this task changed reaches them (their FR content equals the committed one apart from the
  Geometry datablock names). The fresh export also showed pre-existing drift of the committed exports from today's
  source: the DM dents (stats in `damaged.dent`) and `damaged.slots` (Task 3 concern 3) differ on every block, and
  the PDU cabinet's FR LOD0 comes out at 21 456 triangles (committed: 21 464) with its NF vertex order changed; left
  for the controller (the roofs' DM carries today's dent).
- In-game (deferred): a roof under construction shows its panes as glass from the first weld.
- Part -> purpose: no new geometry. The glass role marks glazing that is set in place as glass, not built up.

## Plan 5 Task 6: the construction scaffold (G1, part 1); export determinism; wholesale re-export (2026-10-19)

- **The scaffold** (`dc/scaffold.py`, pure; `fracture_mesh.scaffold_object`; `export_models._plan_scaffold`): every
  cut block's Fractured model carries one ungrouped `BrushedMetal` object, `Scaffold / AlwaysVisible / Scaffolding`
  (vanilla's most common form): see-through `BrushedMetal_Scaffold` (4050183d) from the first weld, hidden at 0.3,
  and hidden on a finished block that is shot by the stage-1.0 `ApplyOnlyWhenDamaged` entry (Task 2's
  `scaffold_parts` now finds it). It is FR-only: never in the Damaged model (the DM copy leaves it out) and never in
  a zone hull (planned after `shape_hulls`, no collider of its own).
  - **Part -> purpose:** the construction cage the welders work from; removed at 30 %.
  - **Form:** a lattice of straight open tubes (`se2model.geom.cylinder`, `cap=False`) on the surface of a union of
    boxes: every box's 12 edges plus each face's grid lines, faces split into equal bays of about the pitch. Lines
    on a face two boxes share inside the union are dropped, collinear pieces merged into one tube, near-coincident
    faces (within a tube diameter) snapped to one, members deduplicated to 1 mm, and every member pulled inside the
    union by its radius, ends included. Boxes: the FR LOD0's render bounds clipped to the block's cells (a server's
    rack ears overhang its cells), and where it fills the cell set 4 mm proud of it (fix round 1 below); a cable tray instead gets its
    zone hulls' boxes clipped the same way, so a Tee, a Cross or a bend is caged along its own outline.
  - **Pitch:** the natural bay first (`natural_pitch`: one cell, 0.25 m, on a block of 1 m or more; half a cell
    below), else the smallest coarser pitch that fits the budget; a finer bay only when the natural one stays under
    MIN_SHARE (5 %) and the budget allows it. A first cut at "the densest pitch that fits" put a 12.5 cm lattice on
    the 2.5 m racks: it read as wire mesh, not scaffolding (t6a previews), hence the natural bay.
  - **Tubes:** radius 10 mm on a block of 1 m or more, else 6 mm; 8 sides at LOD0 (a coarser pitch before fewer
    sides); square (4) only when no 8-sided cage fits at any pitch (Cross_Empty, Reducer_Low, StraightS_Empty,
    Tee_Empty). The 6-sided grid of the plan text stays under 5 % of FR LOD0 on the servers, the PDU cabinet and
    several full trays; 8 sides reach it without a finer, mesh-like lattice. (Fix round 1 dropped 6 sides: a
    hexagon reaches only 0.87 r on one perpendicular axis, so a proud face fell 0.8-1.3 mm short of the cell + 4 mm;
    8 and 4 sides have a vertex on both axes.) LOD1 carries the same cage with 4 sides at the smallest pitch >= LOD0's
    that fits 90 % of the LOD1 budget, or none (the PDU cabinet: its LOD1 is at 91 % of budget already).
  - **Budget (Decision 4):** LOD0 cage <= min(20 % of FR LOD0, budget[0] - FR LOD0 - 10 % of budget[0], the LOD-row
    margin `row_margin`). `_plan_scaffold` re-plans with a lower cap (a coarser pitch, never a different cut) if the
    cage would change Keen's LOD count or the NF-row side, a guard only: the ceiling already keeps FR LOD0 + cage <= 0.9 x
    budget[0] <= 0.87 x the row, and within the row margin.
  - **R6 groundwork (stand-ins, Task 8):** `scaffold.plan(..., reserve=(lod0, lod1))` counts triangles still to be
    added to the FR (the baked stand-ins) as already there: the budget and the 5 % floor are computed on FR + reserve,
    and LOD1's room shrinks by reserve[1]. Task 8 passes its stand-in triangles there (or bakes them before the plan,
    which `_plan_scaffold` then sees in `res`).
  - **R5, blocks without a scaffold** (`test_scaffold.NO_ROOM`, exactly these): `DC_Tray_StraightL_Empty`,
    `DC_Tray_StraightS_Low`, `DC_Tray_TurnH_Empty`, `DC_Tray_TurnUp_Empty`. Their cut FR LOD0 already sits at its LOD
    row (budget 25 / 90 / -182 / -137 triangles: not even a 4-sided edges-only cage fits). Measured and fitting:
    StraightS_Empty and Tee_Empty (square tubes). The 4 unfractured blocks (rods, Chute) have no Fractured stages to
    hide a cage in and get none.
  - **Shipped (after fix round 1; LOD0 pitch / sides, share of FR LOD0 without the cage):** racks 0.25 m / 8,
    6.5-6.7 %; servers 0.125 / 8, 6.3-10.6 %; PDU cabinet 0.25 / 8, 1 216 tris, 5.7 % (Decision 4's ceiling 3 742; no
    LOD1 cage); PDU strips 8.5-13.4 %; CRAC 7.9 %; floors 6.3-18.9 %; roofs 12.8-14.6 %; doors 11.6-19.1 %; signs
    15.2-19.3 %; trays 9.0-19.8 % (4 of them 4-sided, above). Every caged block is in [5 %, 20 %]
    (`test_every_cut_block_has_scaffold`), every one but the PDU cabinet also at LOD1.
  - export.json `fractured.scaffold` = {pitch, pitches per LOD, radius, sides per LOD, boxes, members, tris per LOD}
    (null without one); the states sheet shows its share.
- **Stage lists:** every caged block gains `BrushedMetal` SetMaterial 4050183d at 0 and ShowPart false at 0.3, and the
  last stage's damaged-only hide `BrushedMetal`; with the scaffold's changes removed the stages hash to the Task 1
  baseline (roofs aside: G11), `Tests/test_stages.py` (stage-0 key form: fix round 1 below). `test_roles_refactor_is_identity` is retired (its roof glass
  check lives on as `test_roof_glass_builds_as_glass`).
- **R7 tests updated to the new truth:** `test_own_damaged_model` (DM parts = FR parts minus the scaffold; the
  DAMAGED_TRIS_X bound on FR without it), `test_exported_break_faces` (per LOD, DM materials = FR materials minus at
  most BrushedMetal, and only on an LOD that has a cage: 15 blocks had no BrushedMetal in FR before),
  `test_damaged_model_maps_broken_materials` (the DM .model's slots are the FR's minus the scaffold's BrushedMetal).
- **Task 5 review M1 / M2:** `test_role_manifest` asserts equality: role triangles == FR LOD0 - break faces -
  scaffold, on every block. `fracture.check_role_tables` / `TABLE_ROLES`: a role table may name only the suffixed
  roles (hide, support, frame); `role_of` reads only those (a glass or skin entry would give two meshes one mesh-part
  name).
- **Export determinism (controller ruling after Task 5):** Blender's `mathutils.noise.noise_vector` draws a random
  offset per process (two `blender -b` runs print different vectors for one point; `noise.noise` does not), so every
  export dented the Damaged models differently (vertices up to ~15 mm apart; the FR was already identical between
  runs). `fracture_mesh.dent` now calls `noise.seed_set(fracture.dent_seed(name))` (CRC-32 of the block name): two
  exports give FBX content identical in every model (`test_export_is_deterministic`, opt-in `DC_BLENDER_EXPORT=1`:
  it exports into temp dirs through `DC_MODELS_DIR` / `DC_REPORT_PATH`). No other random source exists in the build
  (`random` is unused; `noise.noise`, the ragged break, is process-stable).
- **The PDU cabinet's 8-triangle drift** (FR LOD0 21 464 committed, 21 456 from today's source): source drift, not
  nondeterminism. Exports of the cabinet from `f36f9ca3` (its last export) and `18ffa4ee` give 21 464, from the merge
  `4cc1dae3` (main's Plan 2 final / placement fixes into plan3-room) 21 456; swapping only `dc/rack.py` from
  `4cc1dae3` into `18ffa4ee` reproduces 21 456. The cabinet builds its plinth with `rack._plinth` (pdu.py:930), and
  the merge lowered the plinth core and deck by `MOUNT_CLEAR` (the deck from 0.236-0.244 to 0.217-0.225; the rack's
  tray floor rose by the same, `zc = ZT + MOUNT_CLEAR`). The merge re-exported the 6 racks but not the cabinet, so
  its committed NF / FR / DM predate it. (Corrected in fix round 1: the first version of this note claimed the NF was
  content-identical; it is not.) This task's re-export refreshes all three: NonFractured LOD0-2 keep their triangle
  counts with 43 vertices moved 19 mm down (the deck), the only NF or subpart FBX whose content changed; at the
  plinth seam zones 01 / 02 each lose 2 skin and 2 cap triangles. Accepted: today's source is right. In-game
  (deferred): the cabinet's plinth deck look and its mount at the plinth.
- **Wholesale re-export (Task 5 M5):** all 73 blocks exported fresh, every `export.json` regenerated (no merged
  keys); all FR / DM files, metas and staged assets committed.
- **Fix round 1 (review of 0ce6fb76):**
  - **The cage stands proud where the block fills its cell** (controller ruling, vanilla measured: Timer50 +4.0 mm,
    Gyroscope250 +6.6, WallInsertPanel +4.3, LCD50 +8.0, batteries +0.4..2.5 past the cell face).
    `scaffold.OUTSET = 0.004`: every envelope face within `FILLS` (2 mm) of its cell face moves to the cell face +
    OUTSET (`reach_cells`; a tray's zone boxes likewise), the inset stays the tube radius, so the tubes' outer surface
    is 4 mm past the cell face: on rack sides, floor decks, roof glass and server shells the cage reads outside the
    skin instead of hiding behind it. It reaches 4 mm into a neighbour cell, as vanilla's (no collider; a finished
    neighbour's skin hides it). The LOD-count check runs on the FR's own size, cage included (`_fit_scaffold`; it
    gives up the proud faces of as few axes as it must if a proud cage would change the count: only DC_Sign_Aisle,
    whose thin 1 m slab asks for one more LOD (the table is keyed on the surface) when grown on both y and z; it
    stands proud on x and y, not z; `fractured.scaffold.proud` records the axes), and
    `test_scaffold_keeps_lod_count` uses `fractured.size`. The FR is up to 2 x (OUTSET + FILLS) larger than the NF
    (`test_exported_lods_follow_keen`); `test_scaffold_inside_cells` bounds the cage by the cell + OUTSET and checks it
    stands >= 3.5 mm proud on every face the skin fills.
  - `construction.generate_stages` writes every time as a float, so a stage's Key no longer depends on which part's
    event came first; `test_stages` compares the installed stages minus the scaffold's changes with the baseline,
    putting stage 0 back in its old int-0 form for the 4 blocks that had it (CRAC, the 3 signs; the roofs too, hash
    exempt).
  - `fracture.dent_seed` is never 0 (Blender's `seed_set(0)` seeds from the clock).
  - `_restore_unchanged` covers the FR and DM folders too: a re-export no longer rewrites FBX / glTF whose content
    did not change.
  - `scaffold._snap_boxes` keeps the outermost value of the group at the union's outline (a proud face stays
    proud; the mean of a proud and a non-proud hull face pulled it back on the Drop trays).
  - The NO_ROOM check compares each budget with the block's real least cage (4-sided edges-only on its own boxes,
    >= 96 triangles); the determinism test includes the PDU cabinet and passed during this round's re-export.
- **R12:** `check_placement.py` takes one name or glob per argument (`catalog.expand`, fnmatch over the catalogue;
  a pattern matching nothing fails).
- In-game (deferred): weld one block per family beside its analogue (5 / 20 / 40 / 70 / 100 %): the cage shows to
  30 % and is gone from 30 %; grind back below 30 %: the cage returns; shoot a finished block: no cage.

## Plan 5 Task 7: Damaged models at vanilla density (G5); dented debris for the unfractured blocks (G12) (2026-10-20)

- **Ratio (Decision 6):** `fracture.DAMAGED_TRIS_X = {"default": 1.2, "floor": 1.5, "contain_roof": 1.5}`,
  `damaged_tris_x(family)`. A Damaged LOD (every LOD but the LastLOD box) is densified to at most that x its Fractured
  LOD's triangles WITHOUT the scaffold (the DM copy already left the cage out; the cap's base is that copy), within the
  fractured budget. Task 9c's x 2.0 is gone; vanilla Deformed / Fractured median is 1.0. Shipped DM LOD0 / (FR LOD0 -
  scaffold): 1.20 on racks, servers, PDUs, CRAC, doors, signs; 1.50 on floors and roofs; trays 1.005-1.20 (a light
  tray's densify runs out of long edges first); rods 1.16-1.20.
- **The two densest light trays:** `DC_Tray_Reducer_Low` DM LOD0 3 574 -> 2 142, `DC_Tray_Tee_Empty` 5 174 -> 3 102,
  each at its x 1.2 cap derived from its manifest (`test_two_trays_back_under_ratio`). The plan's "builder's two
  over-limit tray warnings" were a misreading: Keen's fractured limit (~15.4k / ~22.5k triangles here) was never
  exceeded, before or after, and the SDK log had no such warning. Nothing was "fixed" there; the ratio is the change.
- **Floor:** `test_dm_ratio` also asserts DM >= 1.15 x base (or within 4 triangles of that LOD's budget: the PDU
  cabinet's LOD1, the 42U racks' LOD3) and DM <= budget at every LOD. Exempt, exactly (`LIGHT_LODS`, block / LOD /
  ratio): TurnH_Empty 0 1.005, TurnUp_Empty 0 1.026 and 1 1.042, StraightL_Empty 0 1.125 and 1 1.125, StraightL_Low
  2 1.147, StraightS_Empty 1 1.056, TurnDown_Empty 2 1.042: light trays whose LOD has no edge left longer than the
  DENT max_edge, where densify stops (minimum 1.005).
- **The dents still read** (`fracture.MIN_DENT_MM = 1.5`, `test_dents_still_read`): mean vertex displacement after
  this task, per family: racks 6.1-7.6 mm, servers 5.8-8.6, PDU cabinet 7.9, PDU strips 2.1-2.5, CRAC 6.6, doors
  6.4-6.6, floors 4.5-5.5, roofs 4.6-5.2, signs 2.4-3.3, trays 3.2-5.8. No family needed a higher ratio (previews t7).
  The parallax Deformed materials (Task 3) carry the small-scale damage, as vanilla's do.
- **G12, dented debris for the unfractured blocks** (`export_models._export_unfractured_damaged`): the 3 rod hangers
  and the Chute (non-breakable, no zones, fracture.UNFRACTURED) get a `Damaged/` model: a copy of their Fractured LODs
  (the same mesh parts: they have no scaffold), densified to x 1.2 and dented with `DENT["trayrods"]` (rods) /
  `DENT["tray"]` (the Chute's ladders), seeded by the block name; colliders: a copy of the Fractured plain physics
  boxes (`<name>_Damaged_<box>`). `integration.stage_models` stages it and `patch_model_def` points `DamagedModel` at
  it (it pointed at the FractureModel). Vanilla precedent: the non-breakable ControlPanel25 and Sensor25 ship a
  Deformed model too. Dents: rods 2.4-3.2 mm mean, Chute 3.7. Part -> purpose: the bent hanger rods / ladder rails
  a destroyed or shot hanger leaves (no new parts).
- **Task 3 review M1, the `<Block>_LastLOD` slot is not Deformed-remapped:** vanilla does the same. Of the 269 vanilla
  4.0 Deformed models (tools/vanilla-ref), 196 have a `*_LastLOD` slot with a sibling NF / FR model naming it: 194
  keep exactly the sibling's LastLOD material, 2 differ (MedBay500, WindowTriangleSide250: another LastLOD bake, not a
  Deformed material); 49 have no LastLOD slot. So the distant LOD of a damaged block keeps its normal LastLOD paint.
  `test_lastlod_slot_keeps_its_material` pins it (DM LastLOD ref == FR's on every block).
- **Re-export churn:** `_restore_unchanged` compares a collision glTF without Blender's `.NNN` suffixes on mesh names
  (`_gltf_key`): the hull meshes are named `Fracture_01.047` in a 73-block session and `Fracture_01` in a one-block
  run; only node names bind colliders. This re-export rewrote only Damaged files and export.json; no NF / FR file.
- **R7:** `test_own_damaged_model` uses `damaged_tris_x(family)`; `test_tray_integration` no longer asserts the
  unfractured blocks lack a Damaged model; `test_deformed_remap` counts 73 Damaged models.
- **Previews:** `states_preview` renders an extra `debris` shot (`state_view.DEBRIS_SHOT`: the whole Damaged model in
  its Deformed materials) for a block without zones but with a Damaged model; `states_sheet` adds the column when a
  row has it.
- In-game (deferred): dents read on a shot rack, tray and floor; a destroyed rod hanger / Chute leaves dented debris
  (and whether the game shows a non-breakable block's DamagedModel at all);
  roof damaged panes at x 1.5 read flatter than the x 2.0 look (t3 vs t7 previews; the broken-glass cracks remain;
  1.5 is the Decision 6 ceiling); the rod-hanger debris dents are faint (2.4-3.2 mm mean on 25 mm rods): if they
  should read as bent, raise `DENT["trayrods"]` amp.

## Plan 5 Task 8: server supports; the baked KVM drawer stand-in (G6) (2026-10-20)
- **Server supports** (`fracture.ROLES["server"] = {"support": ("ear", "slide", "screw")}`): all three are mounting
  hardware in `dc/server.py` (`_ears`: the L-bracket flange on the 19" rail plus the leg riveted to the body; `_slides`:
  the server-side inner slide members; `screw`: the ears' captive thumbscrews over the rail's square holes, added in
  fix round 1), so none went back to skin. Part -> purpose: "the ears and slides are the
  server's mounting hardware, welded first". They export as `Fracture_NN_Support` (the Support preset). Support share
  of FR LOD0 (600 tris on the 6U servers, 960 on the UPS): Blank 7.5 %, Compute 4.6, EventCtl 5.1, KVM 5.7, Programmable
  5.2, Status 5.9, Storage 4.8, Switch 4.8, Timer 6.0, UPS 8.7; within [3 %, 25 %]. Vanilla: Timer50 11 %, Battery50
  8 %. Ours sit lower because the mounting hardware is thin. Where a zone's only BrushedMetal faces were slides,
  that zone's skin part `Fracture_NN-BrushedMetal` is gone: Timer zone 01; Blank zones 01 and 03. Its faces are now
  in `Fracture_NN_Support-BrushedMetal`. `test_stages` rebuilds the pre-Task-8 parts (`_before_task8`), and the
  regenerated stages hash to the baseline on every block.
- **Stand-ins** (Decision 9; `fracture.StandIn` / `STANDINS`, `export_models.bake_standins`): the KVM's drawer (FR
  LOD0 gets the drawer's LOD1, FR LOD1 its LOD2) and its lid (the lid's LOD1 for both), split over the zones they sit
  in (fix round 1; vanilla Gyroscope50 / O2H2Generator250 / WindTurbine750 spread one subpart's stand-ins likewise):
  - **Zone rule:** `StandIn.zone = None` (both KVM stand-ins) puts each face in the zone holding its centroid
    (`Zone.violation`, `Plan.zone_index`'s rule, as the block's own faces), uncut, no break faces; an explicit zone is
    an override. The drawer: fascia in the front module `Fracture_02`, tray in the core `Fracture_01`, tail in the rear
    chassis `Fracture_03` (13 parts on the hide list).
  - **Seam refinement** (superseded by the final fix round: the KVM stand-ins are cut along the seams with caps, as
    the racks'; the refinement code is gone) (`_standin_mesh`): an auto-zoned stand-in's edges whose ends lie in different zones are halved
    `STANDIN_SEAM_SPLITS = 4` times first, so a big face (the lid's LOD1 box top, centroid just in front of the seam)
    cannot bridge a dead neighbour: no FR LOD0 stand-in face reaches more than 1.5 cm past its zone (test: 2 cm).
  - **Lower LODs:** a LOD1 face only goes to a zone whose LOD0 has that stand-in part (the stages and the hide list
    are LOD0's), else the nearest such zone, so the 12-tri drawer box at LOD1 can reach up to 0.34 m into a neighbour
    (distance LOD only). Both are in
  the CLOSED pose: no slide, the lid folded flat on the keyboard. Each is moved by its pivot, `subparts.HINGE`
  (`StandIn.at`). The KVM is placed with its drawer shut (79378423). Part -> purpose: "the drawer parked closed (shown
  while the KVM is not working)".
  - **How they are baked:** from the in-memory built subpart objects (R6), the same ones `export_subparts` writes.
  - **Slots:** each is renamed `<Mat>_Subpart`. The material is split into `Fracture_02` / `Fracture_02_Hide` (the
    `HIDE_PREFIXES` materials).
  - **Props:** `Default / AlwaysVisible / SubpartConstruct`, which gives `851d4d6e` at 0 and at 0.3.
  - **Damaged model:** the DM copy keeps them, dented with their zone.
  - **Triangle budget:** they add 856 triangles to FR LOD0 and 112 to LOD1 (seam refinement included; 448 / 24
    unrefined). KVM FR LOD0 is 10 554 against a budget of 20 950, and the LOD count is unchanged (4).
  - **Scaffold:** the stand-ins are counted as `reserve` in the scaffold plan and in the over-budget check.
  - **Manifest:** `export.json` `fractured.standins` records the parts, the triangles per LOD and the items.
  - **`role_tris`** excludes them (they are not the block's own faces).
- **Slot resolution (Review Focus 5):**
  - `material_guids.guid` resolves `<Mat>_Subpart` to the base slot's GUID.
  - `fracture.damaged_slot` maps a slot, or its `_Subpart` base, to the `DAMAGED_SLOTS` target, else to itself.
  - The Damaged `.model` remap (`integration.model_asset`) uses it.
- **ConditionalSubParts:** `MeshPartsToHideWhenActive` = `integration.standin_parts(man)` (the sorted FR `_Subpart`
  parts), written in vanilla's keyed form: `[{"Key": guid, "Value": part}]`, as in Reactor250. The keys are stable,
  `hide/<block>/<part>` in `asset_guids.json`. A bare string list fails the SDK project load ("Unexpected token
  'String', expected 'StartObject'").
- **Vanilla stand-in groups** (tools/vanilla-ref, every `MeshPartsToHideWhenActive`): mostly the zone's own group
  (246) or `_Hide` (255); `_Support` 102 and `_Frame` 66 also occur. We use the zone and `_Hide`, per the plan.
- **Was a known limit, fixed in round 1:** the drawer was all in `Fracture_02` and bridged the dead core in the
  `broken` preview; split by zone it no longer does. With the front module dead (`battered`) the KVM is still
  Functional (only the core is critical), so the real drawer spawns and no stand-in shows.
- In-game (deferred): a KVM under construction, or with a dead core, shows a closed drawer; a Functional KVM's
  drawer moves, and the stand-in hides while the subparts are spawned; player paint shows on a damaged stand-in.

## Plan 5 Task 9: cable trays (35) and rod hangers (3): cables arrive on completion, hangers as supports (2026-10-20)

- **The Parts follow what the pieces are** (`dc/tray_kit.py Parts`). Before this task the Darker `tie` Part mixed the
  cable dressing (straps, split collars, saddle clamps) with the strut channels that carry the basket and the tray
  furniture, and `hw` held the strap buckles and collar bolts. Split (geometry, triangle counts, materials and cuts
  unchanged: NF / FR / DM triangles identical on all 38 blocks, so the DM ratios and `LIGHT_LODS` are unchanged):
  - `wire`: the basket (skin);
  - `cable`: the bundles and their end boots (hide);
  - `tie`: the cable dressing, straps, split collars, saddle clamps (hide);
  - `tiehw` (new, `KEEP_WHOLE` like `hw` was): the strap buckles and split-collar bolts (hide);
  - `hw`: rods, nuts, washers, rod and splice plates, waterfall-guide clamps, saddle feet (support);
  - `strut` (new): the trapeze / floor strut channel; on the rod hanger its ceiling channel and anchor plate (support);
  - `guide` (new): the waterfall guide, the landing brush collar, the crossover saddle deck, the Chute ladder's
    brush foot plate (skin; fix round 1);
  - `trim`, `card`, `solid`: skin; `stencil`: hide by material.
- **`fracture.ROLES["tray"] = {"hide": ("cable", "tie", "tiehw"), "support": ("hw", "strut")}`.**
  `build_dc.junction_geometry` reads the saddle deck from `_guide`.
- **Purpose lines:**
  - cables (and their straps, collars, clamps) are pulled into the finished tray: `_Hide`, shown on completion, as
    vanilla CableStraight250 (65 % `_Hide`);
  - hangers carry it: rods, rod plates, couplers and the strut channels are `_Support`, there from the start;
  - the basket, its trim and the tray furniture the cables ride on (waterfall guide, brush collar, saddle) are the
    skin that builds up through the sequences.
- **Measured (R18), share of FR LOD0 (break faces and scaffold included):**
  - hide: Full 42.1-60.3 %, Moderate 38.5-55.3 %, Low 23.7-48.5 %, Empty 0-0.6 % (stencils only). Test floors:
    Full 40 %, Moderate 35 % (the brief's 40 % fails on StraightS_Moderate, 38.5 %), Low 20 %, Empty < 10 %.
  - support: 1.7 % (Tee_Full) to 24.5 % (StraightS_Low); test range 1.5-30 %.
- **Sparks on the cables:** `effects.zone_dummies(prefer_role="hide")` puts each `ParticleEffects_<zone>` at the
  centre of the zone's `role_bounds[zone]["hide"]` box (else the hull's centre); `patch_spark_dummies` passes it for
  trays. The centre `ParticleEffects` dummy is unchanged (R11, the death effect).
- **Scaffold:** already the zone hulls' boxes for trays (Task 6, `scaffold.boxes_for`); `test_tray_scaffold_follows_shape`
  pins it for the Tee and the Cross.
- **Rod hangers and the Chute** are unfractured (no zones): their roles come from the material only, so the tray
  table does not apply (`test_role_manifest` now expects support only on cut blocks); `ROLES["trayrods"]` stays empty.
- **Drop:** with the cables hidden, a waterfall zone under construction shows only its landing brush collar (on the
  rack's brush plate below) and guide clamps until completion.
- In-game (deferred): weld a Full tray (the cables, straps and buckles appear last); shoot one section (its sparks,
  on its cables, stop when it falls).
- Build note: Task 9 ran in parallel with Tasks 10 and 11: trays and rods exported only; `install.sh` dry run (0
  problems); the SDK build and `install.sh --apply` are deferred to the merge, so `test_installed_stages_regenerate`
  fails on the stale installed Assets until then (it passes against the staged package).

## Plan 5 Task 10: the room blocks' construction roles; the door sill's hull (G10) (2026-10-20)
- **Role tables (`fracture.ROLES`), part names confirmed in the builders.** Part -> purpose:
  - floor `ped` + `pedplate` (dc/floor.py `_pedestal`: tube, jack, lock nut, anchor bolts; base and head plates):
    "the pedestals stand on the slab and carry the deck" -> `_Support`. (The plan named only `ped`; the base and
    head plates are the same pedestal.) Support share 44-58 % of the LOD0 role triangles (the pedestals are round).
  - roof `frame` + `clamp` (contain.py `_frame` beams and mullions, `_clamps` rail brackets): "the frame the panes
    sit on and the clamps onto the racks' rail pads" -> `_Support` (22-31 %); the panes stay glass by material.
  - sign `hw`: "the bolts and hangers the sign hangs on" -> `_Support` (20-42 %).
  - PDU cabinet `hw` (the four levelling feet, the bolts) -> `_Support` (10.8 %); `lamp`, `sticker` and the new
    `breaker` part -> `_Hide` (12.1 %, was 3.6 %): "the 24 branch breakers are fitted last". `dc/pdu.py _breakers`
    now builds the breaker bodies, toggle slots, toggles and trip tabs (every LOD) on the `breaker` Part; the busbar
    and the circuit-number strips stay skin. The NF is unchanged in mesh parts (materials), its FBX bytes changed.
  - PDU strips `hw` + `steel` (pdu.py `_brackets`: the standoff brackets and their keyhole button heads; the plan
    named only `hw`) -> `_Support` (12-17 %); `lamp`, `cord`, `plug` -> `_Hide` (47-52 %): "the jumper cords and
    the inlet plug are plugged in last" (CircuitBreaker: 48 % `_Hide`).
  - doors: no table (vanilla doors have no support).
- **The hide threshold:** the plan's "cabinet hide >= 20 %" is replaced by the measured 12.1 % (test floor 10 %),
  per the controller's R18 ruling.
- **G10, `fracture.MIN_ZONE_SHARE = 0.01`, `MIN_HULL_T = 0.02` (fix round 1, controller ruling):** after
  `shape_hulls`, a zone whose health share (Keen's rule) is under 1 % gets an axis box (`fracture.lift_small_zones`
  / `min_share_box`): its LOD0 geometry's box, thickened on its thinnest axis to >= 2 cm and to the share, but never
  more than `MIN_HULL_T` beyond its own geometry; a zone that would need more makes the export raise, by name (re-zone
  it or exempt it). No spreading to the cells or seams: the hull is a LIVE collider. After any zone dies the Fractured
  collision becomes the block's physics (`BreakableComponent.SetFractureState` -> `CustomCollider`; a broken door's
  `DoorBlockColliderComponent.GetDoorCollider` returns it, no leaves), each dead zone's debris piece and the re-weld
  overlap check (`IsFractureSpaceOccupied`). The manifest flags a lifted zone `min_share`. No block is lifted today.
  - **`fracture.MIN_SHARE_EXEMPT = {("contain_door", "Fracture_08")}`:** the three doors' 8 mm sill keeps its shaped
    hull (0.06 % of the health, <= 1 cm over the floor, y +-0.06). Why: it is the one non-critical door zone; its
    death changes no function (the door stays Functional, only the doorway's `sill_down` mount drops); audit G10 is
    rated Low; reaching 1 % by volume needs a 6-7 cm box across the doorway, an invisible step in a broken door's
    walkway (round 0 did that: reverted). Health cannot be weighted any other way (`PostProcessPrefabs`: volume x the
    global critical multiplier; making the sill critical changes the critical list). Accepted cost: the sill can die
    early. In-game check (deferred): walk through a broken door (no step); shoot the sill (dies early: accepted).
- **Tests:** `Tests/test_room_states.py`; `test_stages._role_and_standin_parts` also takes out `_Hide` parts whose
  material is not a hide material (the table hides); `test_construction_roles` role-table set check is exact (merge: server, tray, crac and the room families).
- In-game (deferred): weld a roof (frame first, panes read as glass); weld a PDU cabinet (the breakers and lamps
  appear at the end); weld a floor (pedestals first).

## Plan 5 Task 11: the CRAC's construction roles and parked fan stand-ins (G6) (2026-10-20)
- **CRAC supports** (`fracture.ROLES["crac"] = {"support": ("hw", "pipe")}`), confirmed in `dc/crac.py`:
  - `hw`: the levelling feet under the plinth, the fixing bolts of the fan modules, panels and nameplates, the door
    hinges and latches and the CHW valve levers. Part -> purpose: "the mounting hardware that carries and fixes the
    cooler, welded first". (The fan modules' venturi lips left `hw` in Task 13: see below.)
  - `pipe`: the CHW supply / return valve bodies, stubs and blind flanges and the condensate stub in the top well.
    Part -> purpose: "the coolant stubs where the facility's pipework lands".
  - They export as `Fracture_NN_Support` (the Support preset). The support share of FR LOD0 is 3 208 triangles,
    18.7 % (vanilla Timer50 11 %, Battery50 8 %; the servers 4.6-8.7 %); Task 13 moved the venturi lips out: 2 824
    triangles, 16.4 %. The lamps in `hw` stay `_Hide` (hide by material).
- **Venturi lips** (Task 13, Task 11 review ruling): the three fan modules' lip rings (the round fan-orifice trim,
  `crac._fan_module`; at LOD2 the fan disc that stands for lip and fan) are their own part `lip`, not in
  `ROLES["crac"]`, so they are skin and build with the housing they trim instead of appearing with the first weld.
  Part -> purpose: "the orifice trim of each fan module". Kept whole (`KEEP_WHOLE["crac"]`) as before. The lips were
  384 of the 3 208 support triangles (not ~3k as estimated in the Task 11 review). Baseline: the ruling allowed an
  `nf_parts` refresh of `Tests/golden/states_baseline.json`, but none is needed: NF mesh parts are per material and
  the lips keep MetalDull, which the NF still has (`test_zone_names_match_baseline[DC_CRAC]` passes unchanged). The
  FR and DM lose `Fracture_02/04_Support` at LOD1 and `Fracture_02/03/04_Support` at LOD2 (the lips, or the LOD2 fan
  discs, were those zones' only supports there); stage
  definitions are unchanged (install: 9 FBX overwritten, nothing else).
- **Fan stand-ins** (Decision 9; `fracture.STANDINS["DC_CRAC"]`): three `StandIn("CracFan", zone, (1, 2), at)`,
  one per fan section (`Fracture_02`, `_03`, `_04`, the zones supporting CracFan1..3). Each sits at its own rotor pivot
  (`(0, crac.ROTOR_Y, FAN_ZC[k] - H / 2)` = `crac.fan_points`, the CracFan1..3 dummies, identity orientation). Each is
  the rotor's LOD1 (228 tris) in FR LOD0 and its LOD2 box (12 tris) in FR LOD1. Part -> purpose: "fans parked (no
  power)": the rotors standing still in their shrouds while the cooler is under construction or a fan section is dead.
  - **Zones:** explicit (the brief's), so there is no seam refinement. The rotor (tip radius 0.196 m) sits well inside
    its section: the seams between sections are on the door rails 0.26 m from each fan centre, and the section's
    back plane (the core's front, y 0.10) is 0.39 m behind the blades. `test_crac_fan_standins` asserts the Task 8 per-face rule (every face in
    its centroid's zone, no vertex more than 2 cm past it). The zones are convex, so that vertex bound covers every
    edge and face too, including one crossing a third zone between two in-zone vertices.
  - **Mesh parts:** `Fracture_0{2,3,4}-{MetalDull,PaintedMetalDarker}_Subpart` (6), distinct by zone, so one subpart
    with three stand-ins gives three disjoint part sets. `bake_standins` already keyed its parts by stand-in index
    (M5), so it needed no change.
  - **Triangles:** FR LOD0 16 518 -> 17 202 (+684; budget 28 006); FR LOD1 4 648 -> 4 684 (+36); the LOD count is
    unchanged (5). DM LOD0 18 360 -> 19 180 (it keeps them, dented with their zone). The scaffold is unchanged
    (1 216 / 608): the reserve fits.
  - **ConditionalSubParts:** `stage_crac` writes `MeshPartsToHideWhenActive = hide_when_active(spec, man, G)`
    (`standin_parts(man)` in vanilla's keyed form, stable `hide/DC_CRAC/<part>` keys). Before, it was cleared.
  - In-game (deferred): a CRAC that is unpowered, under construction or has a dead fan section shows still fans in
    all three bays. Note that an unpowered but intact CRAC is still Functional, so its spawned rotors simply coast
    to a stop; the stand-ins show only while it is not Functional. A Working CRAC's stand-ins hide while the rotors
    spin. Player paint shows on a damaged stand-in.

## Plan 5 Task 12: the racks' construction roles; side panels and fan tray as ConditionalSubParts (G2, Ruling DB-10) (2026-10-20)
- **Ruling DB-10: Path A** (user-approved "A with fallback to B"). Evidence (decompiled 4.0.0.3151,
  `.superpowers/sdd/.../task-12-spike.md`):
  - the door's server-side `DoorBlockColliderDefinition.SubPartsProvider` -> `ConditionalSubPartsDoorPartsProviderDefinition`
    -> `ConditionalSubPartsDefinition.SubParts` is followed by `BindingsBasedClientServerInfo`'s SERVER walk
    (`BindingsBasedClientServerInfo.cs:194-263`), which stops only at a binding's ClientPrefab (`:134-135, 222-230`);
    `ConveyorGraphPostProcessor.ValidateClientTypes` (`:162-205`) then rejects any client type it reached (the
    2026-10-18 rotor failure). So every entry is a BOUND client prefab whose server side holds no client type;
  - `ConditionalSubPartsComponent` spawns iff `FunctionalBlockComponent.Functional` (`ConditionalSubPartsComponent.cs:
    159-224`): `EffectiveBuildProgress >= MinFunctionalBuildProgress` (1.0 without optional items) and no dead
    critical zone; power, Enabled and Working play no part;
  - `CollectSubparts` overwrites only the spawned root's ChildTransform (`ConditionalSubPartsDefinition.cs:265-286`):
    nested children keep their offsets, and one dummy type with two dummies spawns two copies.
  - The gate is `Tests/test_clientserver_walk.py` (Task 12a, the offline port of the walk + validator), run on the
    real installed package (`test_datacenter_package_passes`), with a control that un-binds the tray and fails.
- **Rack supports** (`fracture.ROLES["rack"] = {"support": ("frame", "rail", "slide", "contain")}`), confirmed in
  `dc/rack.py`: `frame` = the corner posts, plinth frame, roof rails and the rear PDU bulkhead; `rail` = the 19"
  mounting rails; `slide` = the server slides; `contain` = the containment rail. Part -> purpose: "posts and rails
  first": the structure the rack is built on. Support share of FR LOD0: 15.5-15.6 % (42U, 3 788 tris), 15.4-15.5 %
  (24U, 2 484 tris); vanilla Smelter250 24 %.
- **Subparts** (`integration.stage_rack_subparts`): RackSide (one entry; dummies `RackSideR` at the block origin and
  `RackSideL` turned 180 deg, the side's dummy type) and, on the 42U racks, RackFanTray (dummy `RackFanTray` at
  `doors.fan_tray_point`) are ConditionalSubParts entries. Each is bound (`bind_subpart`:
  `Subparts/<rack>_<sub>_{Binding,ServerComposition,Server}.def`): the server composition is vanilla
  SlideDoorNarrow_250_LeftDoor's minus the door segments (ModelComponent = the subpart's own model component,
  ChildTransform, Hierarchy), one server prefab with Hierarchy `Children: []`. The two rotors are Hierarchy children
  of the TRAY's client prefab (`_rotor_children`, Gyroscope50_Subparts nesting), never on the server side; the
  block-level `RackFan1/2` dummies are gone. The static client-prefab children (Task 9 / visual pass 2) are removed
  (`clear_rack_static_children`). Door racks add the entries to the door's own ConditionalSubParts; open racks get
  the Ruling 15 chain (`onto_powerable` from the structural CubeBlockComponent, `ConsumedResource` null,
  STRUCTURAL_DEF_VALUES carried, Fragility kept Structural) plus a client-only ConditionalSubPartsComponent (and on
  the 42U the FunctionalBlockAnimationController, so the rotors follow Working / On-Off like the door racks').
  Part -> purpose: "side panels and fan tray parked as stand-ins until the rack is complete".
- **Stand-ins** (`fracture.STANDINS[<rack>]`): the side LOD1 twice (`StandIn.yaw`, new: 0 / 180 deg) and the tray
  LOD1, all zone None (split by centroid, seam-refined with `StandIn.seam_splits` 6, new: 4 halvings left a side
  vertex 2.7 cm past its zone): FR LOD0 +4 656 (42U) / +1 696 (24U), FR LOD1 +636 / +224. 42U FR LOD0 24 208-24 464
  (budget 28 006), 24U 16 030-16 126 (24 618); LOD counts unchanged (5 / 4). The DM keeps them (27 588-27 894 /
  18 154-18 272). The 42U racks' LOD1 scaffold dropped from 608 to 320 tris (the LOD1 budget, Decision 4).
  (Superseded by Task 13 fix round 1: the stand-ins are cut, not seam-refined; the numbers after the cut are in the
  Task 13 section.)
  `bake_standins` now keeps a skin's ColliderMeshGroups in role order when a stand-in adds a zone's `_Hide` group.
- **Side LOD1 fix:** `louvre_panel` halves the slat count at LOD1, which doubled the tilted slats' width: the side
  model's LOD1 vent slats stood 17 mm proud of the render inset XO (FR size 1.028 m wide). `rack_side._vents` keeps
  LOD0's count at LOD1 (also improves the shipped subpart's LOD1).
  The rotors get no stand-in of their own (the tray's LOD1 shows the housings).
- **Behaviour change:** sides and tray now exist only on a Functional rack, i.e. complete AND undamaged: Functional
  needs EffectiveBuildProgress (BuildProgress x integrity remapped over the destruction threshold) >=
  MinFunctionalBuildProgress = 1.0 (`FunctionalBlockComponent.cs:728`, `CubeBlockComponent.cs:4048-4054`,
  `CubeBlockDefinition.cs:2243, 2518-2525`). So under construction, after any grinding and after ANY damage (one hit)
  the real sides and tray despawn, the tray fans stop and the stand-ins show, on door and open racks alike (fix
  round 1: an earlier note claimed a damaged open rack stays Functional; it does not). The KVM's drawer and the
  CRAC's fans follow the same rule.
- **On/Off on every rack for consistency; on the 24U open rack it has no visible effect** (user ruling, fix round 1,
  M6). All six racks are terminal-listed with On/Off, draw no power and are built On
  (`test_every_rack_is_terminal_listed_with_on_off`): the open racks through the Ruling 15 chain (ConsumedResource
  null), the door racks as cloned from SlidingDoorNarrow250 (PowerableBlockComponent, ConsumedResource amount 0, so
  they still need a powered grid to be Working: their fans stop with the grid off; the open 42U's spin regardless).
  On the 42U racks Off stops the tray fans; the sides and tray follow Functional, not On/Off. In-game first-load test: INGAME-CHECKLIST "Next session".

## Plan 5 Task 13: visual pass, fix round 1 (2026-10-20)
- **Hidden parts' break caps** (`fracture_mesh.build_caps`, `export_models._split_cut`): a cap of a part hidden under
  construction (role hide: the trays' cables and ties) is tagged `dc_role` = hide and goes to the zone's `_Hide`
  group with its part (Default / AlwaysHidden), not the zone's own `Fracture_NN-FracturedMaterial01` (Split /
  HiddenUntilSecondSequenceStart). Before, those caps stood as loose discs in the empty basket from 30 % to
  completion. New mesh parts: `Fracture_NN_Hide-FracturedMaterial01` on the 27 cabled trays and `DC_Contain_Roof_100`.
  If a zone has no hide piece at that LOD (promoted to skin), they go to the skin's group. Test:
  `Tests/test_cut_caps.py`. `KEEP_WHOLE` is unchanged: a whole cable would hang over a dead zone.
- **Door cage** (`scaffold.HULL_BOXES`): a containment door's cage is built on its zone hulls' boxes (posts and
  lintel), as a tray's, so the doorway stays open like vanilla SlidingDoorNarrow250's U-shaped cage. The 7.5 mm sill
  strip (thinner than 2.5 cm) gets no box, so no tube lies across the threshold. Test:
  `test_scaffold.py::test_door_cage_leaves_opening_clear`.
- **Rack stand-in caps** (`StandIn.cut`, `export_models._cut_standin`): the side and fan-tray stand-ins are now cut
  along the rack's seams (`fracture_mesh.cut_object`: bisected straight (`ragged=False`), never edge-split)
  instead of seam-refined. Each zone's cross-sections are closed by `build_caps`, baked as
  `<zone>-FracturedMaterial01_Subpart` (SubpartConstruct, in the hide-when-active list), so a broken side has no raw
  edge. The per-face zone check still applies to every non-cap stand-in face. A cap lies on its seam, so it gets
  only the 2 cm bound. Test: `test_rack_states.py::test_rack_standins_capped`. Part -> purpose: "the break faces
  of the parked side panels".
  Triangles after the cut (these replace the Task 12 numbers): stand-ins FR LOD0 2 560 / LOD1 220 (42U), 1 120 / 128
  (24U); FR LOD0 22 112-22 368 (42U, budget 28 006) and 15 454-15 550 (24U, budget 24 618), cage included; the 42U
  LOD1 cage is back to 608 triangles.

## Plan 5 final review fix round (2026-10-20)
- **I1, Path B is a switch** (`config.RACK_PATH`, Ruling DB-10 above and INGAME-CHECKLIST "Next session"): the old
  instruction "revert 10455382" conflicted in about 330 files, because later commits build on it.
- **M4, the KVM stand-ins are cut** (`StandIn("KvmDrawer"/"KvmScreen", None, ..., cut=True)`), as the racks': when one
  of the KVM's zones dies, the surviving drawer piece is closed by a `FracturedMaterial01_Subpart` cap instead of
  showing a raw edge. `StandIn` now requires `cut` exactly when `zone` is None; the seam refinement
  (`seam_splits`) is gone. KVM: stand-ins FR LOD0 580 / LOD1 60 (was 856 / 112), 16 hidden parts (was 13), FR LOD0
  10 278 (budget 20 950), LOD count 4. The per-face zone check and the 2 cm bound still hold
  (`test_kvm_standins` uses the shared `_standin_faces_in_zone` / `_hide_list_matches`).
- **M5:** the budget table's DM limit is the enforced one (the fractured budget).
- **M6:** removed the uncalled `state_view.all_def_guids` / `write_baseline` (the golden baseline is never
  regenerated) and `construction.stage_state_at` (`state_view.part_state` replaced it). The 6 orphan
  `hide/DC_Rack42_*/Fracture_07-*_Subpart` keys stay in asset_guids.json (append-only registry).
- **M9:** the opt-in determinism test also exports `DC_Rack24_Open` (cut stand-ins); it passed (2026-10-20).

## Visual fix 2026-10-20: rack-top clips, the Feed A band, broken interiors, size-free names
In-game report (DC_Rack42_Open from below beside DC_PDU_Rack42_A; a shot DC_PDU_Cabinet; a damaged DC_CRAC).
- **Containment rail clips** (`rack.contain_rail_boxes`): the clamp pads were exactly as tall as the rail (top and
  bottom faces in the rail's top / bottom planes) and sat in its back plane: Darker pad vs Colorable rail z-fight.
  The pads keep the band CONTAIN_Z (measured contain_rails and the roof's mount band unchanged); the rail body now
  stands CONTAIN_WRAP (3 mm) inside it, so each pad is a clip whose jaws wrap the rail; the pad's back face is buried
  2 mm in the rail; the standoff (38 mm wide, down to 1 mm above the clip's jaw) reads as the clip's bracket to the
  header. Affects the six racks, the CRAC and the PDU cabinet (they share `_contain_rail`).
- **Feed A band** (`pdu.feed_band_outline`): the band stood 1.5 mm off the body, exactly as proud as the 1.5 mm face
  plate (FACEPLATE_T): its front lay in the plate's plane, so only the side wraps showed, as loose yellow tabs. Now
  1.5 mm proud of the plate. The per-outlet LEDs sat 0.1 mm proud of the plate: now 0.6 mm.
- **24U roof rails** (`rack._roof`): their end faces lay in the side-skin plane where the spawned RackSide panel's
  outer face is (subpart-vs-block z-fight at the spawned pose): 2 mm inside now.
- **Audits** (dc/zfight.py, build_report "zfight"): `coplanar` = VISIBLE same-facing coplanar overlaps in the close
  models (block and subpart LOD0 / LOD1; buried overlaps, e.g. a plate's back face on its body, are skipped by a probe
  ray, `_visible`); `subpart_frame` = the Path A subparts at their spawned pose (sides at 0 / 180 deg, the fan tray)
  against the block. Tests/test_zfight.py fails on any different-material pair not in KNOWN_COPLANAR (the
  pre-existing ones, follow-ups below) and checks the two in-game cases by name.
- **Interiors** (superseded the same day by "Broken interiors: Keen's way", below; dc/interior.py, export.json
  fractured.interior; Tests/test_interior.py for the cabinet and the CRAC): the cabinet now holds its panelboard (gear plate, uprights, L1-L3 / N riser on insulators, breaker chassis
  pans, DIN rails and the breakers' rear bodies, the isolator body and links, CTs, meter body, incomer from the rear
  gland, branch looms to the top brush plates, PE / N bar); the CRAC's solid Darker core is gone: plenum walls, a fan
  wall with an orifice per fan, the CHW coil (fin pack with perforated faces, tube sheets, return bends, headers),
  insulated CHW pipes to the well, the 3-way control valve and actuator, the drip tray and drain, the condensate pump
  and riser to the COND stub, the EC fan drives, the control board and the filter rack. It is a chilled-water unit,
  so there is no compressor (the facility's chiller does the refrigeration). The racks' (and the cabinet's) solid
  plinth core is a load frame now (the plinth halves left a 0.09 m^2 flat cap). Their NF LOD0 guard rose from 90 %
  to 98 % of Keen's limit (CRAC 15 662, cabinet 15 206 of 16 072); every LOD within Keen's limits, 8 materials.
- **Names** (dc/names.py): no block name carries a size (the kind's size selector does that); descriptions keep
  them; no two kinds share a name (Tests/test_room_menu.py test_no_size_in_block_names).
- **se2diag "0 dead zones" on the cabinet**: the cabinet has no stand-ins and its hide list (lamps, sticker,
  breakers) holds no skin, so a missing section can only be a dead fracture zone; the probe counts
  `FractureIntegrity.IsDead` (Integrity <= 0) in DamagedFractures, which is the right field. Open: re-check in game
  that the diagnosed block is the broken one (health 0.67 fits one body zone's share).
- **Follow-ups** (the catalogue-wide audits): visible coplanar pairs of different materials in KNOWN_COPLANAR (rack
  plinth side skin vs corner caps; top-entry Yellow edge vs frame; 24U PDU socket ring vs gland plate; contain roof
  cap vs glass and tape vs bolts; door frame vs Darker trim; server core vs bezel trims; tray guide vs basket; rod
  strut vs trim): move the thinner part 0.5 mm proud, one per block. Empty interiors: the 6U servers (solid Darker
  core tub: hollow it, add a mainboard, heatsinks, DIMMs, drive cage, PSU), the KVM (core and rear zones: the same
  chassis work); the trays, floors, doors, roofs and signs are open frames or panels (no interior to show).

## Broken interiors: Keen's way (2026-10-20)
The standard for every Rioku Labs block (user decision 2026-10-20), replacing the modelled machines of the visual fix
above. **A fracture zone's inside is a solid core whose exposed faces are vanilla FracturedMaterial01** (0f2772fd:
torn wiring, boards, connectors; what the servers' cut faces already show; FracturedMaterial03, shredded sheet metal,
is the option where it fits), **plus only a few large, recognisable parts a hole shows**. No zone opens onto an
empty hollow, and the inside is not modelled machinery.
- **Mechanism** (`fracture.CORE_PARTS`, `fracture_mesh._as_core` / `_core_to_caps`): a family's `core` part is Darker
  in the NonFractured model (nothing sees it; the 8-material cap holds); in the cut Fractured / Damaged LODs every
  face of it takes FracturedMaterial01 with box UVs at 0.4 UV/m (CUT_UV_PER_M, as the caps) and joins its zone's
  break-face object (Split / HiddenUntilSecondSequenceStart / Fracture, as vanilla's cut faces). Where two seams
  cross one solid its cut loops stay open at the crossing (no cap), so a core spanning both is split into one block
  per zone standing clear of the seams (the cabinet); a core crossed by parallel seams is one block, cut and capped
  (the CRAC's front core).
- **CRAC**: the coil fills the core zone (Darker fin pack, its perforated faces 2 mm behind both seams: a dead fan
  section or filter door shows the coil face); one front core behind the fan modules (the modules' orifice walls are
  the fan wall; a 4 mm Darker baffle closes the core where the orifices and grilles look in), one rear core behind
  the filters and port frames (its baffle behind the louvres); LOD2 one core box. The plinth core's top is 2 mm under
  the plinth seam (in the seam plane it went to the body zones, so a dead fan section took the plinth's lid along);
  a 4 mm floor pan under the top band (a dead body zone showed the band's hollow). Removed: CHW pipes, valve,
  actuator, drip tray, pump and riser, EC drives, control board, filter rack, the separate fan wall.
- **PDU cabinet**: four core blocks (one per body section, 4 mm off x = 0, 45 mm round PANEL_JOINT_Z where the seam
  snaps), filling the pocket behind the cover under and over the parts kept: the busbar riser (L1-L3, N on three
  insulators) and the breaker rows (chassis pans, the 24 breakers' rear bodies). Removed: gear plate, uprights,
  isolator body and links, CTs, meter body, incomer, looms, cleats, PE / N bar, DIN rails.
- **Plinths**: the racks' (and the cabinet's) load frame (597f7c6e) is the solid core again: a plinth half's break
  showed 17 cm of nothing behind the seam; now the other half's FracturedMaterial01 cap.
- **Gate** (`dc/interior.py`, Tests/test_interior.py): per zone the `cover` of its seams when it dies (rays from a
  3 cm grid on each seam plane into the neighbours must meet a face within 10 cm: a core face, a cap or a part; an
  exposing zone needs >= 0.8; the plinth halves' seam too) and the exposing zones' interior detail <= 800 tris. The
  597f7c6e models scored 0.03-0.32 (CRAC 1692 / cabinet 2342 detail tris); now CRAC 0.85-1.0 (202), cabinet
  0.88-0.93 (627). The big flat FracturedMaterial01 plane is Keen's look: `cap_plane_m2` is informational.
- **Budgets** (the project cap back to 90 % of Keen's LOD0 limit, 16 072): CRAC NF 15 662 -> 14 146 (88.0 %), cabinet
  15 086 -> 14 066 (87.5 %); every LOD, Fractured and Damaged model within Keen's limits, 8 materials. For the CRAC's
  headroom its fan guard rings and motor faces went from 16 to 12 sides (a 3.6 mm wire reads round at 12).
- Previews (not committed): resources/previews/DataCenter/interiors-keen/{before,after}/, the fix-rack-top shot list.

## Plan 5 summary: damage and build states (Tasks 1-14, 2026-10-19 to 2026-10-20)

What the plan changed, in one place. The per-task sections above hold the evidence. In-game checks are in
INGAME-CHECKLIST.md section 14; nothing here has been run in game yet (previews and tests only).

**Build states.** A fractured block now builds like a vanilla one: a blue construction cage (the scaffold) until 30 %,
the supports and frame in solid metal from 30 %, the skin ghosting in with its zone, and the hide parts (lamps,
stencils, screens, cables) only at completion. A finished block that is shot, or ground back and welded again, never
shows the cage (the stage-1.0 `ApplyOnlyWhenDamaged` hide names exactly the scaffold parts). **Damage states.** Every
Damaged model uses the 4.0 Deformed materials and is densified to vanilla density; the blocks have spark, smoke and
fire bands at the right health, and the parked moving parts (drawer, fans, side panels) show as baked stand-ins
whenever the block is not Functional.

### Role tables (`dc/fracture.ROLES`, by family; part names as in the builders)

| Family | support (built first, Fracture_NN_Support) | hide (appears at completion) | frame / glass |
|---|---|---|---|
| rack | frame, rail, slide, contain | stencils, lamps by material | none |
| server | ear, slide, screw | stencils, lamps, screens by material | none |
| tray (35) | hw, strut | cable, tie, tiehw | none |
| trayrods, Chute | none (unfractured) | none | none |
| crac | hw, pipe | stencils, lamps by material | none (the lips are skin) |
| floor | ped, pedplate | none | none |
| contain_roof | frame, clamp | none | the panes are glass (WindowGlass) |
| contain_door | none | none | none |
| pdu_cabinet | hw | lamp, sticker, breaker | none |
| pdu_strip | hw, steel | lamp, cord, plug | none |
| sign | hw | screens, stencils by material | none |

A material in `HIDE_PREFIXES` (decal, font, emissive, terminal, LCD) is always hide; a glass material is always glass;
everything else is skin. Zone ids never change, so saved `DamagedFractures` still bind.

### Part -> purpose, per family (no greebles: every added or retagged part has a job)

- **Scaffold (every cut block):** the construction cage the welders work from; removed at 30 %. Never in the Damaged
  model or a zone hull.
- **Racks:** frame, rails, slides and the containment rail are the posts and rails that carry everything; the side
  panels and fan tray are parked as stand-ins until the rack is complete; the stand-ins' cut faces are the break faces
  of those parked panels.
- **Servers:** ears and slides are the mounting hardware; the thumbscrews are the captive screws that fix the server
  in the rack; the KVM drawer and lid are parked closed.
- **Cable trays:** hangers and struts are the mounts that carry the basket; the cables, ties and boots are laid last.
- **CRAC:** hw is the mounting hardware that carries and fixes the cooler; pipes are the coolant stubs where the
  facility's pipework lands; the lips are the orifice trim of each fan module; the fans are parked until it runs.
- **Floor:** the pedestals carry the tile and go in first. **Roof:** the frame and clamps carry the panes.
- **PDU cabinet / strips:** feet and brackets are the mount; breakers, lamps, cords and plugs are fitted at the end.
- **Signs:** hangers and bolts carry the panel; the screen and stencils are fitted at the end.

### Rulings (Plan 5; recorded in docs/research/update-4.0/progress.md)

- **Ruling DB-1:** the stage generator is the mod's own `dc/construction.py` (`tools/se2model/construction.py` is
  left unchanged and is superseded for this mod).
- **Ruling DB-2:** the stage-1.0 `ApplyOnlyWhenDamaged` hide names exactly the block's Scaffold-type parts.
- **Ruling DB-3:** the scaffold is an ungrouped BrushedMetal lattice in FR LOD0 (and LOD1 when it fits), never in the
  DM or a hull; boxes = the render envelope for box-like families and the zone hull AABBs for trays and doors.
  `scaffold.OUTSET` = 4 mm: where the skin fills the cell the cage stands 4 mm proud, as vanilla (measured on
  Timer50, Gyroscope250, LCD50).
- **Ruling DB-4:** the scaffold's LOD0 triangles are at most min(0.20 x FR LOD0, FR budget[0] - FR LOD0 - 0.10 x
  budget[0], the LOD-row margin) and at least 0.05 x FR LOD0 when that fits (PDU cabinet <= 3 742, 42U racks <= ~3.7k).
- **Ruling DB-5:** construction roles are per face (table above); zone names never change.
- **Ruling DB-6:** Damaged models densify to at most x1.2 of FR LOD0 without the scaffold (floors and roofs x1.5),
  floor ratio 1.15 except eight listed light LODs. Applied without waiting for an in-game gate.
- **Ruling DB-7:** spark bands copy vanilla 4.0 verbatim (trays CableStraight250 `2113ece5`; PDUs and deco servers
  CircuitBreaker `617b0925`; KVM ControlPanel25 x0.3; Programmable re-based on the Timer template `2cad179b`, which
  brings the Timer's audio and death effect x0.5). The Empty trays and the Chute get no band.
- **Ruling DB-8:** spark dummies follow zones: the centre `ParticleEffects` keeps its key and position and gains
  `SupportingFracture`; long blocks get one dummy per other zone, at most 3 emitters per block (the cabinet
  03/05/07); the UPS gets an unsupported centre dummy first (the death effect comes from the first dummy in order,
  decompile `BlockEffectsComponent.cs:410-414`) and one dummy per bay.
- **Ruling DB-9:** stand-ins exist only in FR and DM (vanilla Gyroscope250: 17 `_Subpart` parts in FR, 16 in DM, 0 in
  NF); each is the subpart's next-lower LOD in the owning zone; they are listed in the keyed
  `MeshPartsToHideWhenActive` (a plain list broke the SDK load). Per-face zone split, never one part across zones.
- **Ruling DB-10:** Path A, see the Task 12 section. Path B (the fallback if Path A fails the world load) is a
  switch: `RACK_PATH = "B"` in `Source/Model/dc/config.py` stages the side panels, the fan tray and its rotors as
  static children of the rack's client prefab again (exactly the pre-Task-12 structure, no new GUIDs), drops the
  rack stand-ins (`fracture.rack_standins`) and keeps On/Off on every rack. `Tests/test_rack_path_b.py` stages the B
  package on every suite run, compares its children with the pre-Task-12 commit's and walks it through the
  client/server gate; the Path A pins carry the `path_a` marker and skip under B. The commands (switch, `git rm` of
  the 58 Path A rack definitions, the rack pipeline) are in INGAME-CHECKLIST.md "Next session".
- **Later rulings:** Programmable fragility Functional (max HP x0.8); the containment roofs use Windows fragility with
  the vanilla Windows effects (destroy audio dropped); `MIN_ZONE_SHARE` 1 % with `MIN_SHARE_EXEMPT` for the three
  doors' sill zone (Fracture_08, hull clamped to at most 1 cm (the visible threshold), so a broken door leaves no step);
  `MIN_HULL_T` 2 cm; All six racks are terminal-listed with On/Off (the 24U open rack: no visible effect); the CRAC's
  venturi lips are their own skin part; hidden parts' break caps go to their `_Hide` group; the door cage follows the
  zone hulls (doorway open); rack stand-ins are cut straight along the seams with closed caps; hide-share thresholds
  come from measurements (R18), not guesses; the committed exports are byte-stable (name-seeded dents).

### Per-block triangle budget (generated from `export.json`; LOD0 triangles)

NF = plain model; FR LOD0 includes the scaffold and the stand-ins; the limits are Keen's (FR x1.83425); the DM column
is the Damaged model, and its limit is the one the build enforces (the fractured budget, `test_damaged_geometry`). The four unfractured blocks (Chute, three Hanger Rods) have no cage and carry a debris DM.
Regenerate with `python3 Source/Model/dc/budget_table.py`; `Tests/test_states_docs.py` fails when it is stale.

<!-- budget-table:begin (generated by Source/Model/dc/budget_table.py; do not edit) -->
| Block | NF | FR LOD0 | FR limit | Scaffold | Stand-ins | DM LOD0 | DM limit | FR LODs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DC_Rack42_Open | 14 744 | 22 112 | 28 006 | 1 216 | 2 560 | 25 072 | 28 006 | 5 |
| DC_Rack42_SplitFront | 14 816 | 22 240 | 28 006 | 1 216 | 2 560 | 25 226 | 28 006 | 5 |
| DC_Rack42_SplitFrontRear | 14 888 | 22 368 | 28 006 | 1 216 | 2 560 | 25 380 | 28 006 | 5 |
| DC_Rack24_Open | 12 590 | 15 454 | 24 618 | 896 | 1 120 | 17 464 | 24 618 | 4 |
| DC_Rack24_SplitFront | 12 638 | 15 502 | 24 618 | 896 | 1 120 | 17 524 | 24 618 | 4 |
| DC_Rack24_SplitFrontRear | 12 686 | 15 550 | 24 618 | 896 | 1 120 | 17 582 | 24 618 | 4 |
| DC_Srv_Timer | 8 176 | 10 002 | 20 950 | 768 | - | 11 077 | 20 950 | 4 |
| DC_Srv_EventCtl | 10 050 | 11 876 | 20 950 | 768 | - | 13 326 | 20 950 | 4 |
| DC_Srv_KVM | 7 712 | 10 278 | 20 950 | 768 | 580 | 11 409 | 20 950 | 4 |
| DC_Srv_UPS | 8 866 | 11 068 | 21 345 | 896 | - | 12 204 | 21 345 | 4 |
| DC_Srv_Status | 8 388 | 10 214 | 20 950 | 768 | - | 11 333 | 20 950 | 4 |
| DC_Srv_Programmable | 9 736 | 11 562 | 20 955 | 768 | - | 12 950 | 20 955 | 4 |
| DC_Srv_Compute | 11 186 | 13 012 | 20 950 | 768 | - | 14 689 | 20 950 | 4 |
| DC_Srv_Storage | 10 622 | 12 448 | 20 950 | 768 | - | 14 014 | 20 950 | 4 |
| DC_Srv_Switch | 10 814 | 12 640 | 20 950 | 768 | - | 14 244 | 20 950 | 4 |
| DC_Srv_Blank | 6 222 | 8 032 | 20 953 | 768 | - | 8 714 | 20 953 | 4 |
| DC_Tray_StraightS_Empty | 760 | 1 212 | 1 371 | 192 | - | 1 222 | 1 371 | 3 |
| DC_Tray_StraightS_Low | 1 080 | 1 144 | 1 371 | - | - | 1 368 | 1 371 | 3 |
| DC_Tray_StraightS_Moderate | 1 560 | 2 544 | 14 626 | 384 | - | 2 590 | 14 626 | 4 |
| DC_Tray_StraightS_Full | 1 760 | 3 144 | 14 626 | 512 | - | 3 156 | 14 626 | 4 |
| DC_Tray_StraightL_Empty | 1 320 | 1 840 | 2 072 | - | - | 2 070 | 2 072 | 3 |
| DC_Tray_StraightL_Low | 2 152 | 3 520 | 21 481 | 576 | - | 3 530 | 21 481 | 4 |
| DC_Tray_StraightL_Moderate | 3 400 | 5 176 | 21 481 | 576 | - | 5 518 | 21 481 | 4 |
| DC_Tray_StraightL_Full | 3 744 | 6 448 | 21 481 | 960 | - | 6 582 | 21 481 | 4 |
| DC_Tray_TurnH_Empty | 1 824 | 1 928 | 1 940 | - | - | 1 938 | 1 940 | 3 |
| DC_Tray_TurnH_Low | 2 632 | 3 524 | 20 910 | 480 | - | 3 650 | 20 910 | 4 |
| DC_Tray_TurnH_Moderate | 3 844 | 5 132 | 20 910 | 672 | - | 5 350 | 20 910 | 4 |
| DC_Tray_TurnH_Full | 4 800 | 6 808 | 20 910 | 1 120 | - | 6 822 | 20 910 | 4 |
| DC_Tray_TurnUp_Empty | 1 824 | 1 824 | 1 874 | - | - | 1 872 | 1 874 | 3 |
| DC_Tray_TurnUp_Low | 2 632 | 3 540 | 20 183 | 512 | - | 3 630 | 20 183 | 4 |
| DC_Tray_TurnUp_Moderate | 3 844 | 4 956 | 20 183 | 512 | - | 5 330 | 20 183 | 4 |
| DC_Tray_TurnUp_Full | 4 800 | 6 184 | 20 183 | 512 | - | 6 804 | 20 183 | 4 |
| DC_Tray_TurnDown_Empty | 1 824 | 2 468 | 16 589 | 384 | - | 2 498 | 16 589 | 4 |
| DC_Tray_TurnDown_Low | 2 576 | 3 484 | 16 589 | 512 | - | 3 564 | 16 589 | 4 |
| DC_Tray_TurnDown_Moderate | 3 704 | 4 816 | 16 589 | 512 | - | 5 162 | 16 589 | 4 |
| DC_Tray_TurnDown_Full | 4 768 | 6 664 | 16 589 | 1 024 | - | 6 766 | 16 589 | 4 |
| DC_Tray_Tee_Empty | 1 816 | 3 092 | 21 330 | 504 | - | 3 102 | 21 330 | 4 |
| DC_Tray_Tee_Low | 2 912 | 4 932 | 21 330 | 752 | - | 5 014 | 21 330 | 4 |
| DC_Tray_Tee_Moderate | 4 820 | 7 304 | 21 330 | 896 | - | 7 686 | 21 330 | 4 |
| DC_Tray_Tee_Full | 6 932 | 10 692 | 21 330 | 992 | - | 11 638 | 21 330 | 4 |
| DC_Tray_Cross_Empty | 2 700 | 4 124 | 21 681 | 592 | - | 4 236 | 21 681 | 4 |
| DC_Tray_Cross_Low | 4 224 | 6 644 | 21 681 | 1 072 | - | 6 684 | 21 681 | 4 |
| DC_Tray_Cross_Moderate | 6 536 | 9 568 | 21 681 | 1 072 | - | 10 192 | 21 681 | 4 |
| DC_Tray_Cross_Full | 8 040 | 11 888 | 21 730 | 1 072 | - | 12 976 | 21 730 | 4 |
| DC_Tray_Drop_Low | 4 652 | 5 660 | 22 107 | 864 | - | 5 752 | 22 107 | 4 |
| DC_Tray_Drop_Moderate | 5 516 | 6 524 | 22 107 | 864 | - | 6 790 | 22 107 | 4 |
| DC_Tray_Drop_Full | 6 340 | 7 348 | 22 107 | 864 | - | 7 778 | 22 107 | 4 |
| DC_Tray_Reducer_Low | 1 392 | 2 044 | 14 626 | 256 | - | 2 142 | 14 626 | 4 |
| DC_Tray_Reducer_Moderate | 1 992 | 3 104 | 14 626 | 512 | - | 3 108 | 14 626 | 4 |
| DC_Tray_Reducer_Full | 2 716 | 4 100 | 14 626 | 512 | - | 4 302 | 14 626 | 4 |
| DC_Tray_Chute | 1 672 | 1 672 | 3 919 | - | - | 2 004 | 3 919 | 3 |
| DC_TrayRods_025 | 380 | 380 | 1 283 | - | - | 454 | 1 283 | 2 |
| DC_TrayRods_100 | 380 | 380 | 2 975 | - | - | 454 | 2 975 | 3 |
| DC_TrayRods_200 | 380 | 380 | 838 | - | - | 440 | 838 | 2 |
| DC_Floor_Solid_050 | 2 496 | 3 320 | 14 701 | 320 | - | 4 498 | 14 701 | 4 |
| DC_Floor_Perf_050 | 2 985 | 4 035 | 14 701 | 640 | - | 5 089 | 14 701 | 4 |
| DC_Floor_Solid_100 | 6 436 | 7 840 | 21 779 | 576 | - | 10 894 | 21 779 | 4 |
| DC_Floor_Perf_100 | 8 332 | 9 736 | 21 779 | 576 | - | 13 738 | 21 779 | 4 |
| DC_CRAC | 14 146 | 17 054 | 28 006 | 1 216 | 684 | 19 002 | 28 006 | 5 |
| DC_PDU_Cabinet | 14 066 | 23 328 | 28 006 | 1 216 | - | 26 532 | 28 006 | 5 |
| DC_PDU_Rack42_A | 6 602 | 8 138 | 18 226 | 640 | - | 8 994 | 18 226 | 4 |
| DC_PDU_Rack42_B | 6 666 | 8 202 | 18 226 | 640 | - | 9 072 | 18 226 | 4 |
| DC_PDU_Rack24_A | 3 862 | 4 886 | 9 625 | 576 | - | 5 170 | 9 625 | 3 |
| DC_PDU_Rack24_B | 3 926 | 4 950 | 9 625 | 576 | - | 5 246 | 9 625 | 3 |
| DC_Contain_Door_100 | 5 200 | 7 232 | 27 132 | 864 | - | 7 638 | 27 132 | 4 |
| DC_Contain_Door_150 | 5 464 | 7 560 | 30 323 | 928 | - | 7 956 | 30 323 | 5 |
| DC_Contain_Door_200 | 5 728 | 7 888 | 33 514 | 992 | - | 8 272 | 33 514 | 5 |
| DC_Contain_Roof_100 | 3 352 | 4 534 | 21 441 | 576 | - | 5 934 | 21 441 | 4 |
| DC_Contain_Roof_150 | 4 156 | 5 972 | 22 082 | 704 | - | 7 901 | 22 082 | 4 |
| DC_Contain_Roof_200 | 4 960 | 7 328 | 22 725 | 832 | - | 9 742 | 22 725 | 4 |
| DC_Sign_Aisle | 1 224 | 2 576 | 11 306 | 384 | - | 2 628 | 11 306 | 3 |
| DC_Sign_AisleHang | 1 744 | 2 904 | 10 503 | 384 | - | 3 022 | 10 503 | 3 |
| DC_Sign_Rack | 870 | 1 582 | 7 409 | 256 | - | 1 588 | 7 409 | 3 |
<!-- budget-table:end -->
