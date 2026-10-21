# Plan 3 Task 11: visual-pass audit (room pieces)

The audit set is in `Source/Model/preview/plan3-task-11/` (a symlink into `resources/previews/`: not committed). It was
rendered with `DC_PREVIEW=plan3-t11 DC_T11_PHASE=before|after` (`dc/preview_p3t11.py`) from the build list
`"DC_Floor_*" DC_CRAC "DC_PDU_*" "DC_Contain_*" "DC_Sign_*" DC_Rack42_SplitFront "DC_Srv_*" DC_Tray_Drop_Full
DC_Tray_StraightS_Full DC_TrayRods_100`.

**Before** was rendered from a snapshot of HEAD 76db7593 plus only the new shot module and the ported z-fight audit
(which adds measurements, no geometry). **After** is the working tree. Both sets use the same 48 cameras:

- `room_photo1` / `room_photo1_black`: the photo 1 camera (`docs/ideas/reference/datacenter/01`);
- `room_photo4` / `room_photo4_black`: the photo 4 camera (`04-rod-hung-basket-over-racks.jpg`: high at a row's end,
  down along the rack tops with their labels and the trays on rods, the walkway on the right). It uses the hot room,
  whose row B faces its outer walkway (fix round 1: rendered in both phases, before from 76db7593's code);
- `room_hero06`: the v1 / v2 mockup `06-room-hero` camera (inside the aisle, lens 17);
- `room_eye_west` / `room_eye_east`, `room_hot_eye_west` / `room_hot_eye_east`: the contained aisle at 1.7 m eye
  height from both ends, cold and hot rooms;
- `room_door_outside`, `room_overhead`, `room_end_row`, plus `room_inside_up` (in the contained aisle, looking up at
  the rack tops) and `room_labels_open_side` (the rack tops from the open hot walkway);
- the coupling joints at about 0.5 m: `joint_rack_top`, `joint_door_pocket`, `joint_roof_clamp`, `joint_pdu_inlet`,
  `joint_floor_seam`;
- each room block beside its vanilla clone source at the same scale and light, front and back
  (`vs_<block>_front|back`, 10 blocks), and `vanilla_sources` (all of them in one line beside a 42U rack);
- the fix close-ups: `crac_rear`, `crac_rear_close`, `crac_controller`, `rail_tag`, `door_pull_closed` /
  `door_pull_open`, `pdu_bank_head`, `crac_lods`.

Sheets: `contact_before.jpg`, `contact_after.jpg`, and `pairs/<shot>.jpg` (before | after) for every shot a fix
changed.

Besides the eye, this pass measured every room block. The z-fight audit from main (commit 4f7288a5) is ported unchanged
(`dc/zfight.py`, `style.hazard_triangle`). `dc/zfight_room.py` adds the containment door's sliding leaves and the
stencil-contrast rule. Both are recorded in `build_report.json` "zfight" and checked by `Tests/test_room_zfight.py`
(19 blocks). **Before:** 9 of the 19 room blocks failed (CRAC, PDU cabinet, the four rack PDU strips, the three
containment doors). **After:** all 19 are clean.

Format: finding → evidence shot → fix → after shot. Findings are ranked by impact.

| # | Sev | Finding | Evidence | Fix | After |
|---|---|---|---|---|---|
| 1 | H | **The CRAC had no service connections** (user direction, 2026-10-18). Its hot-aisle face was four identical louvred filter sections. Nothing showed where a station's life-support or coolant loop would connect, and there was nothing to "turn on" once SE2 gets air vents and airtightness. | `crac_rear`, `crac_rear_close`, `vs_DC_CRAC_back` | **Rear service bay.** The lower half of the rear (z 0.262 to 1.242) is now a bolted Colorable panel. It carries two blanked **O2 / COOLANT SERVICE** ports.<br>- Each port is Keen's small conveyor port frame as a kit part (`dc/crac_ports.py`): `O2Generator250.fbx` `ConveyorPortSmall_Border_low.001`, and the LOD1 file's `.003`. They are imported read-only; their geometry, normals and first UV layer are unchanged (the extra UV layers are dropped). Provenance is in `build_report` and NOTES. LOD2+ is ours.<br>- In place of the hatch sits our bolted Darker blind plate: 4 bolts, "BLANKED / DO NOT REMOVE". The hatch's ConveyorsAtlas face would be a 9th material, and its latch handle goes with the hatch.<br>- The panel openings follow the frame's measured chamfer (`CLIP` 0.054).<br>- A PORT 1 / 2 tag and the label sit on Darker plates.<br>- The filter door keeps the upper half (two grilles). The joint is the old grille rail (z 1.25), which is also fracture seam `zr`: Fracture_06 is the bay, Fracture_07 the filter door.<br>**Future turn-on (data only):**<br>- Dummies `conveyor_port_o2_1` (z 0.5) and `conveyor_port_o2_2` (z 1.0) sit on the rear **cell face**, centred on 2 x 2 cell patches (x and z on cell lines), oriented like vanilla's ConveyorBack, with small-port scale (0.5, 0.5, 0.05). They are supported by the bay.<br>- Their dummy type is our own inert `ServicePort`, so nothing snaps and there are no mount points or conveyor components.<br>- To turn them on later: switch the type to UseConveyor (`integration.CRAC_PORT_TYPE_ON`), add the components, and add the mount points.<br>Tests: `test_crac_service_ports_on_cell_faces`, `_add_no_mount_points`, `test_crac_service_port_dummies`, `test_crac_service_ports_kit_provenance`. | `pairs/crac_rear.jpg`, `pairs/crac_rear_close.jpg`, `room_hot_eye_west` |
| 2 | H | **White stencils straight on the light paint** (main's in-game lesson c). The CRAC controller's RUN / ALARM / MODE / SET legends and its "CRAC CONTROLLER" title were on the keen-grey Colorable panel, and so was CONDENSATE PAN on the rear kick panel. They are barely legible at 1 m, and on a white paint they vanish. | `crac_controller`, `crac_rear_close` | Each now sits on a Darker plate: a lamp and key legend plate (the lamps and keys stand on it), a title strip, and a condensate label plate. A new **measured rule** (`zfight_room.stencil_backing`): for every white stencil glyph of every room block (all LODs and subparts), the face directly behind it must not be paint. Before, the CRAC had 9 offending stencils; after, there are 0 in all 19 blocks (`test_room_stencils_on_dark_backing`). The PDU cabinet, PDU strips, doors, roofs, floors and signs already passed. | `pairs/crac_controller.jpg`, `pairs/crac_rear_close.jpg` |
| 3 | H | **Containment door leaves z-fight** (main's lessons a and b, on our sliding leaves). The leaf frame check found:<br>- the pinch-zone chevrons, 0.3 mm over the stile face (coplanar);<br>- at LOD1, the flush Darker pull plate 0.2 mm over the stile (34 000 mm² coplanar);<br>- the pull recess's end walls overlapping the side walls' corners (419 mm² coplanar per leaf).<br>All of these were present in every door, at LOD0 and LOD1, on both leaves. | `door_pull_closed` (these faults are sub-mm, so they show in game as flicker, not in a still) | The chevrons and the LOD1 plate now sit 0.6 mm proud (`contain.STRIPE_D`, `PULL_PLATE`), and the end walls run between the side walls. The new audit (`zfight_room.contain_door_check`) also places each leaf **closed and open** (contain.leaf_centre_x, matching the collision boxes: `test_contain_door_leaf_audit_poses`) against the frame, and the two closed leaves against each other. Both checks were already clean and stay clean. Tests: `test_contain_door_leaves_have_no_coplanar_faces`. | `pairs/door_pull_closed.jpg` |
| 4 | M | **Decal labels coplanar with their plates.**<br>- PDU strips: BANK 1 / BANK 2 / 16A sat 0.2 mm over the bank head's label strip (all four strips).<br>- CRAC and PDU cabinet: the CONTAINMENT rail tag sat 0.2 mm over its Darker plate (`rack._contain_rail`, shared with the racks). | `pdu_bank_head`, `rail_tag` | The strip labels now sit 0.6 mm proud. The rail tag gets a `tag_lift` (0.6 mm), which the CRAC and the cabinet pass. **The racks keep 0** (no rack geometry change in this task): see deferred R2. Test: `test_room_decals_clear_of_coplanar_geometry` (19 blocks). | `pairs/rail_tag.jpg`, `pairs/pdu_bank_head.jpg` |
| 5 | M | **Rack labels and the hanging sign are invisible from inside a contained aisle** (the T8 carry). The roof clamps to the rack's top band, so the rack tops and anything mounted on them (labels, Drops, the hanging sign at tray height) sit above the roof plane. From inside, the labels show only as ghosts through the frosted panes. | `room_inside_up`, `room_hero06`, `joint_roof_clamp` | **Guidance, no new block** (the call). Under the roof, the only free volume is the rack doors' sweep: at 85° the leaves reach 0.457 m into the aisle, up to 2.246 m. A sign hung there would block doors in a 1.0 m aisle and would only be safe on a rack's centre line. The roof cell itself has no LCD chain. So:<br>- **mount the rack labels on the rack-top edge facing the OPEN aisle.** Task 8 already supports this back-pad mount; `room.rack_label(u, -1)` places it, and `reference_room(label_side="open")` builds it, choosing the pad from the aisle type (`room.label_pad`: the back pad for a contained cold aisle, the front pad for a contained hot one; fix round 1, which corrected the hot case);<br>- sign a contained aisle on its doors' headers (DC_Sign_Aisle, both ends, already in the room);<br>- hang the hanging sign over open aisles.<br>Tests: `test_contained_aisle_labels_go_on_the_open_side` calls `reference_room(w, aisle, label_side="open")` for every aisle width, cold and hot. It checks that there is no cell conflict in the room, that the label is on the rack's top plane over the expected pad, and that its screen faces away from the contained aisle. `test_reference_room_label_sides` checks the default "front", "aisle" and "open". In-game guidance goes to Task 12's checklist. | `pairs/room_labels_open_side.jpg`, `pairs/room_inside_up.jpg` (no more ghost labels over the roof), `pairs/room_eye_west.jpg` |
| 6 | L | **Unnamed Yellow square on the CRAC's ID plate** ("the cold-side tag"). A reviewer can't name it, and it breaks Yellow restraint (Yellow only at hazards). | `rail_tag`, `room_inside_up` | Removed, and "CRAC 01" re-centred. CRAC icon re-rendered. | `pairs/rail_tag.jpg`, `pairs/room_inside_up.jpg` |
| 7 | L | **CRAC LOD1 at 98 % of Keen's limit** (T6). The ports added more. | `crac_lods` | Budget paid elsewhere:<br>- LOD1 drops the 6 mm feet, the 18-24 mm labels (RUN / ALARM, FILTER, CONDENSATE PAN, port tags and label: unreadable at LOD1 range) and uses 6 / 8-segment water pipes;<br>- LOD2 draws the bay as blocks;<br>- 4 blind-plate bolts;<br>- no latch handle.<br>Now **LOD0 14 350 / 16 072 (89 %), LOD1 3 468 / 3 696 (94 %)**, LOD2 1 220 / 1 282, LOD3 144 / 156, and still 8 materials (`test_crac_faces_and_limits` holds LOD0 ≤ 90 %). | `pairs/crac_lods.jpg` |
| 8 | L | **The CRAC kept the vanilla gimbal's dead subpart chain** (T6 review minor 1): S1–S3 rotations and model components, the S2 / S3 composites, the gimbal prefab and composite, and SubpartMarker. They are unbound and reference only each other. | `Assets/DataCenter/DC_CRAC/Subparts/` | Dropped through `clone.GIMBAL` in `clone.DROP`. The stale Content outputs were removed and rebuilt; the content caches no longer name them. `test_room_clones` now asserts that they are gone and that the CracFan chain and `SubParts.def` stay. | (definitions) |
| 9 | L | **The CRAC hum was inherited, not chosen** (T6 review minor 2). | `DC_CRAC_BlockEffectsComponentDefinition` | Set explicitly through `integration.patch_hum` (`HUM_CRAC`), like the racks' and servers'. It is still vanilla GyroscopeMID: vanilla 2.4's 40 OnUseAudio loops include no fan or air-handler loop, and MID is the deeper whir, suited to three 0.4 m fans against the racks' SM. Try O2H2Generator in game. Test: `test_crac_hum_explicit`. | (definitions) |
| 11 | L | **Photo 4 match: the frosted roof panes read as bright floor tiles from above** (fix round 1, the photo 4 camera). From a high camera at a row's end, the photo 4 composition reads well: the rack labels on the front edges face the walkway and are legible down the row, the trays hang on their rods, and the rack tops sit at the photo's height. The containment roof next to the row, lit from below by its LED battens, shows its FrostedGlass stand-in as uniform near-white panes, which read more like ceiling tiles than glazing at this angle. **No change**: this is the preview's FrostedGlass stand-in (`preview_mats`), and the in-game material is vanilla FrostedGlass. Check in game whether the roof reads as glass from above (Task 12 checklist). The labels confirm finding 5's guidance: in the hot room the racks' fronts are the open side, and the front pad is where the labels belong. | `room_photo4`, `room_photo4_black` | (no fix) | `pairs/room_photo4.jpg` |
| 10 | L | **Roof clearance tested on full racks only** (T6 review minor 4). | `Tests/test_containment.py` | `test_roof_clears_kvm_and_rack_doors` now iterates every in-row unit (`INROW`: the full racks, the CRAC and the PDU cabinet). The CRAC and cabinet take the rack's top plane, and their render mesh stays inside the cell planes (nothing reaches the aisle under the roof). | (test) |

## Checklist (Step 2)

| Item | Result |
|---|---|
| SE-ify: paint reads as the player's colour | PASS. The bodies are Colorable (`room_photo1_black`: every room piece takes black). The new bay panel is Colorable. |
| SE-ify: bevels as chunky as vanilla | PASS. The cabinets and doors use the rack's `CHAMFER_LARGE` corner caps (`vs_DC_CRAC_front`, `vs_DC_PDU_Cabinet_front`). The port frame is Keen's own. |
| SE-ify: Keen-style stencils | PASS after #2. Stencils are AtlasFont CleanWhite on Darker plates; the measured rule now holds in all 19 blocks. |
| SE-ify: lamps few and large | PASS. CRAC: RUN and ALARM only. Cabinet: its lamp column. |
| SE-ify: yellow restraint | PASS after #6. Yellow is used for the pinch-zone chevrons, the hazard rails and the conveyor port frames. Yellow port frames are Keen's port convention (every vanilla small port is a Yellow frame), so a reviewer reads them as ports. |
| Purpose: every part nameable | PASS after #1 and #6. The new parts' part-to-purpose list is in NOTES ("Plan 3 Task 11"). |
| Photo 4 matched camera (rack tops, labels, trays) | PASS with one observation (finding 11): the labels read down the row from the walkway, and the trays hang on their rods. The frosted roof reads pale from above, which is a preview stand-in issue to check in game. |
| CRAC reads as the photo 1 cooler | PASS (`room_photo1_black`). The three 0.4 m fan modules, deep venturis and finger guards read as an in-row cooler at aisle distance. |
| Floor reads as a raised floor at 10 m | PASS (`room_overhead`): the tile grid is visible, the perforated tiles are distinct, and no catwalk look. |
| Containment: glass reads as glass; door sturdy | PASS (`room_door_outside`, `door_pull_closed`). The aluminium stiles, mid rail and kick plate read sturdy. The roof's FrostedGlass reads as frosted panes. |
| Signs legible at 15 m | PASS (Task 8's `p3-task-8/legibility_15m.png`; no sign geometry changed). |
| PDU strips read at the rack rear | PASS (`joint_pdu_inlet`, `room_hot_eye_*`). |
| LOD pop | LOD counts follow Keen's `optimal_lods` from the measured LOD0 (`assemble.fit_lods`). No new pops; the CRAC's LOD1 / LOD2 drop the same classes of detail as vanilla (`crac_lods`). |
| Wear matches Keen materials | PASS (vanilla materials only). |
| Anti-goals: scale against racks and a 1.8 m figure; no cable ends in mid-air | PASS (`vs_*`, `room_*`; a 0.4 m port is the vanilla small port's size). |

## Deferred to the main merge (rack geometry is not changed in this task)

- **R1 (M): every rack's front header reads "A1"** (a static stencil on the tray header). Inside a contained aisle it is
  the only visible rack ID, and it repeats on every rack (`room_inside_up`, `room_eye_east`). Main is changing the
  racks: blank it, or turn it into the in-aisle rack-ID surface. It sits under the roof edge and is visible from inside.
- **R2 (L): the racks' CONTAINMENT rail tag** is 0.2 mm over its plate (this branch's Task 1 rail; main has no rail
  yet). At the merge, set `rack._contain_rail(tag_lift=0.0006)` as the default and run main's `Tests/test_zfight.py`
  (it audits every built block) over the merged racks.
- **R3: the z-fight port.** `dc/zfight.py` and `style.hazard_triangle` are byte-identical to 4f7288a5. The
  `build_dc.py` hook is main's with room additions: main's import line becomes `from dc import zfight, zfight_room`,
  and about 8 lines go inside main's loop hunk (the stencil backing, `zf.update(contain_door_check)`, the extra `bad`
  rows; `build_dc.py:1203-1211`). Main has also changed `build_dc.py` since (1042efce). **Expect a real but mechanical
  conflict there**: keep main's lines and re-add the room ones. Main brings `test_zfight.py` and its rack-side fixes.

## Noted for Task 12 (cost balance, the T10 review)

- The hanging aisle sign costs about 3x a vanilla LCD50. The PDU cabinet has more steel than the CRAC. Left as is.
