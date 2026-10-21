# Data Center: in-game checklist

Everything below was verified offline only (tests, the placement checker, the SDK build, decompiled 2.4.0.95 code).
Run it once in game before calling the core plan done. Tick each box, and note anything unexpected next to it
(with a screenshot path).

## Next session: rack subparts first-load test (do this FIRST)

Plan 5 Task 12 (Ruling DB-10 Path A, G2) moved the racks' side panels (RackSide, spawned twice) and the 42U racks'
fan tray (RackFanTray, with its two rotors nested under it) from static client-prefab children to **bound
ConditionalSubParts entries**. They spawn only while the rack is Functional (fully built, no dead critical zone);
until then the Fractured / Damaged models show baked stand-ins (the subparts' LOD1, `<Mat>_Subpart` slots). The open
racks also gained the Ruling 15 On/Off chain (terminal-listed, On/Off, no power draw). The offline walk gate
(`Tests/test_clientserver_walk.py`) passes on the installed package, but a **bound non-leaf** ConditionalSubParts
entry has no vanilla precedent, and the 2026-10-18 failure of this class broke the **world load**. So this block goes
before everything else in the session. If any step fails, stop, keep the log, and report; the fallback is Path B
(next paragraph).

**Setup.** SE2 closed. From `mods/DataCenter` (the merged main, not a worktree): `bash
Source/Model/integration/install.sh --apply`, then from the workspace root `python3 tools/scripts/se2mod.py build
DataCenter` (both were run after the plan5 merge; repeat only if the tree changed). Launch (scripts on):
`python3 tools/scripts/se2mod.py play DataCenter --native`.

**Path B fallback (Ruling DB-10), if a step fails.** Path B is a switch, not a revert: `RACK_PATH` in
`Source/Model/dc/config.py`. With `"B"` the side panels, the fan tray and its rotors go back to static children of
the rack's client prefab (exactly the pre-Task-12 structure), the racks get no stand-ins, and every rack keeps
On/Off. `Tests/test_rack_path_b.py` stages the B package on every suite run and walks it through the client/server
gate. With SE2 closed, from `mods/DataCenter`:

```bash
sed -i 's/^RACK_PATH = "A"$/RACK_PATH = "B"/' Source/Model/dc/config.py
# Path A's own rack definitions (install.sh replaces files but never deletes a definition): 58 files
git rm -q -- 'Assets/DataCenter/DC_Rack*/Subparts/*_'{RackSide,RackFanTray}_{Binding,Server,ServerComposition}'.def*' \
             'Assets/DataCenter/DC_Rack*_Open/Subparts/*_ConditionalSubPartsDefinition.def*'
R="DC_Rack42_Open DC_Rack42_SplitFront DC_Rack42_SplitFrontRear DC_Rack24_Open DC_Rack24_SplitFront DC_Rack24_SplitFrontRear"
blender --python Source/Model/build_dc.py -- $R --no-render --export     # windowed (the VRAGE add-on); no stand-ins
blender -b --python Source/Model/check_placement.py -- $R
python3 Source/Model/build_integration.py
bash Source/Model/integration/install.sh && bash Source/Model/integration/install.sh --apply   # expect 0 problems
pgrep -x Modern.bin; pgrep -f 'SpaceEngineers2\.exe|VRAGE3\.ModHUB\.exe|VRage\.Editor\.exe'  # both print nothing
(cd ../.. && python3 tools/scripts/se2mod.py build DataCenter)          # "Exiting with 0." twice
python3 -m pytest -q Tests                                               # the Path A pins (marker path_a) skip
```

Then commit (Assets/, asset_guids.json, build_report.json, the rack Models) and rerun steps 1-8 below. Under B,
steps 3-7 change: the sides and the tray are always there (no stand-ins, no swap at 100 %); step 4's On/Off still
stops the rotors. Back to Path A: set `"A"` again and re-run the same commands without the `git rm` (the staging
writes Path A's definitions again).

**The two log lines that mean failure.** After each load (and at the end), grep the newest game log
(`~/.config/SpaceEngineers2/Temp/Logs/SpaceEngineers2_<date>_<time>....log`, not `_Render`):

```bash
L=$(ls -t ~/.config/SpaceEngineers2/Temp/Logs/SpaceEngineers2_*.log | grep -v _Render | head -1)
grep -n "should not be on server compositions" "$L"     # ConveyorGraphPostProcessor.ValidateClientTypes: a client
                                                         # component reached a server composition (the 10-18 class)
grep -n "Definition that is linked from" "$L"            # BindingsBasedClientServerInfo: a binding's server prefab /
                                                         # composite is missing
grep -n -i "datacenter\|DC_Rack" "$L" | grep -i -E "error|exception|unsatisfied|not found"   # anything else on ours
```

Pass = all three print nothing.

- [ ] **1. Fresh world.** New creative world, large-grid station with power. Place one of each rack: 42U Open,
      42U Split Front, 42U Split Front + Rear, 24U Open, 24U Split Front, 24U Split Front + Rear. Save. Grep the log:
      clean. Each finished rack shows both side panels (the PDU hatch, placard and coolant conduit on each side; the
      left one turned, hatch toward the rear) and, on the 42U racks, the fan tray with spinning rotors.
- [ ] **2. Reload an existing save with racks** (a COPY of the 2026-10-19 test world, built before Task 12). It
      loads; the racks show their side panels and trays (nothing doubled: no second side panel inside the first,
      no tray z-fighting); grep the log: clean.
- [ ] **3. Weld a door rack 0 -> 100 %** (42U Split Front, survival or creative with welding). Below 100 % the sides
      and the tray show as stand-ins in the construction material, building with the frame (the posts and rails are
      solid from about 30 %). At 100 % the stand-ins vanish and the real side panels and tray appear in the same
      place (no jump, no gap), and the tray rotors spin (the rack is On and the grid powered).
- [ ] **4. Weld an open rack 0 -> 100 %** (42U Open): the same swap at 100 %; the rotors spin. It is now in the grid
      console (G) with On/Off: switch it Off -> the rotors stop (the panels stay); On -> they spin again.
- [ ] **5. Grind slightly** (one grinder tick on each of the two racks): the real sides and tray despawn and the
      stand-ins return at once (the rack is no longer Functional). Weld back to 100 %: the real ones return.
- [ ] **6. One hit** (one rifle round on each complete rack, a door rack and an open rack): ANY health loss ends
      Functional (EffectiveBuildProgress = BuildProgress x integrity must stay 1.0: FunctionalBlockComponent.cs:728,
      CubeBlockComponent.cs:4048-4054), so on BOTH racks the real sides and tray despawn at once, the tray fans stop
      and the stand-ins show (dented with their zone). Weld the damage back to full: the real ones return.
- [ ] **7. Shoot a column zone** (a side column; on a door rack it is critical) until it breaks off, on both racks:
      the sides and tray are already stand-ins (step 6); the dead column's stand-in goes with the column, the
      surviving zones keep theirs, and nothing floats where the dead column was.
- [ ] **8. Final log check** (the three greps above): clean. Note the log file name here.

## Test session 2026-10-19 (start here once the first-load test above passes)

One pass over the combined build (main + room pieces). Work top to bottom; details are in the numbered sections.

**Launch** (workspace root). The launcher refuses while SE2 is `already running`: quit fully between runs.
1. Scripts ON: `python3 tools/scripts/se2mod.py play DataCenter --native`
2. Scripts OFF: the same plus `--no-scripts` (the data-only fallback). Do the re-tests below in both modes.

**Re-test last night's bugs** (creative, large-grid station with power):
- [ ] Servers place INTO rack slots: aim at the back of an empty slot (the rear stop): green, seated. Aiming at
      the front third of a rail stays red (no wrong-depth seat). 24U top slot: aim left of the middle or from above.
      No stacking servers on top of each other outside a rack (by design now). Details: §2.
- [ ] Rack side labels readable, and no flicker on the side labels or the door meeting edges.
- [ ] KVM: places stowed (Off), is listed in the grid console (G) with On/Off, Use on the drawer toggles it. Both modes.
- [ ] 42U split-door racks: the tray fans spin only when powered (grid off: they stop).
- [ ] Front + Rear door racks: front and rear still open together, both sides (known engine limit, accepted).

**New: the room pieces** (§13 Room pieces; items 1-16). Highlights:
- [ ] CRAC stand-ins (Plan 5 Task 11): one hit on a complete CRAC (any health loss ends
      Functional) despawns the three spinning rotors and the parked fan stand-ins show in all three bays; weld back
      to full: the rotors return.
- [ ] CRAC: draws power, fans spin only while On and powered. Its rear O2 / COOLANT SERVICE ports are decorative
      (blanked; nothing snaps to them).
- [ ] Racks and the CRAC carry neutral placards ("RACK" / "RACK ID" / "CRAC" + a blank tag): no baked IDs. Give each
      rack its ID with a Rack Label (editable LCD); on a 24U it fits only on the rack's back pad.
- [ ] In a contained aisle, mount rack labels on the rack-top edge facing the open aisle; sign the aisle on its door
      headers.
- [ ] PDU strips (fixed after the final review, I1): they seat only at the column bottom, on the plinth socket. Aim
      at the plinth top in the rear corner (or the middle of the column): green, seated. Aiming higher up the column
      stays red, and on a 24U rack no green strip may stick out of the rack top. A strip mounts by its plug (Down)
      only, so it also stands on any Up face (a floor tile, a rack top, an empty slot's floor if you aim it into a
      server slot): that is expected (as before the fix).
- [ ] Two contained 1.5 m aisles cannot share a row: the second aisle's door will not place (their leaf pockets
      collide, and the game shows no reason). Make one of them 1.0 m (§13, doors on a shared row).

**Capture** for every finding: a screenshot (F4, or `tools/scripts/se2game.py shot`), the time, and at the end the
newest log in `~/.config/SpaceEngineers2/Temp/Logs` (the `SpaceEngineers2_<date>_<time>....log`, not `_Render`).

**Game update:** "Hostile Encounters" lands 2026-10-19 17:00 UTC (10:00 PDT). Test before it, or set Steam to update
on launch only. If the game has updated, do not test the mod: wait until the controller has run the update diff.

## Decisions to confirm

These were decided during the build, not by you. Each is recorded in the design doc's "Amendments (implementation
rulings)" (`docs/design/2026-10-17-data-center-design.md`). Confirm or reject each one during the pass:

- [ ] **Rack width 1.0 m** (4 cells, not the approved 0.75 m) and **server depth 0.75 m** (3 cells, not about 1.0 m). Rulings 6 and 7.
- [ ] **Rack ears overlap side by side.** Two standalone servers placed next to each other overlap their ears by about 7.6 cm (servers are rack-first). Ruling 8.
- [ ] **The UPS's second cell bay is on the back** (cell 1 front, cell 2 rear). Ruling 13.
- [ ] **The KVM spawns Off (stowed)** since the 2026-10-18 in-game fix (vanilla blocks spawn On; the KVM's prefab overrides it) and is listed in the grid console with On/Off. Switched On, it **pops out through closed rack doors** with scripts off (nothing couples it to the door state). Ruling 15.
- [ ] **Costs:** the decorative servers cost the rounding minimum (1 + 1, plus 1); the Programmable server costs the same as a blanking panel; the door racks are lighter (Mostly Hollow, so they have the open frame's HP). Task 10.
- [ ] **The door leaves have no collider.** A closed door is visual only: you can step into the 0.25 m door zone. Task 9.
- [ ] **KVM use-to-toggle** (Plan 4 Task 9): Use on the KVM's drawer pops it out or stows it, Use on the upper modules (or, out, on the screen) opens the terminal. The hint is vanilla's ("Press F to enable / disable" under the block's name), not a KVM-specific wording, and there is no click sound (vanilla's UsePowerable has none; the hum starting or stopping is the feedback). See §12.5.

**Setup.** Close SE2, then install and build:
- `bash Source/Model/integration/install.sh --apply`
- `tools/scripts/se2mod.py build DataCenter`

Start a **creative** world with the mod (`se2mod.py play DataCenter --native`) on a large-grid station, with a battery
or reactor on the grid. Do the survival section in a **survival** world.

The cable tray checks and their decisions to confirm are in section 11.

## 0. Smoke test (right after the world loads)

- [ ] No errors in the game log about DataCenter definitions. If there are any, stop here and report them first.

## 1. Build menu (Task 10)

- [ ] The Automation category has a **Data Center** subcategory with seven tiles, in this order: **Server Racks**, **Rack Servers**, **Cable Trays: Empty**, **Cable Trays: Low**, **Cable Trays: Moderate**, **Cable Trays: Full**, **Cable Tray Supports** (group `Order` 100..700; Plan 2 Task 9).
- [ ] Each Cable Trays tile lists Straight, Horizontal Turn, Turn Up, Turn Down, Tee, Cross, Rack Drop, Reducer (Empty: no Rack Drop, no Reducer). Straight offers two sizes (Short 0.5 m, Long 1.5 m).
- [ ] **Cable Tray Supports** lists Hanger Rods (three sizes: 0.25, 1.0, 2.0 m) and Long Drop Chute.
- [ ] No cable tray appears under the vanilla Structural > Walls (Pipes) or Trusses tiles.
- [ ] Tray names read "Cable Tray, Straight (Full)" etc., with no length in the name; the game's size selector tells the Straight and Hanger Rods sizes apart, and the descriptions give the lengths.
- [ ] **Server Racks** contains three kinds, in this order: Open Frame, Split Front Doors, Front + Rear Doors.
- [ ] Each rack kind offers **two sizes**. Size 1 is the 24U rack and size 2 is the 42U rack.
- [ ] The names read "Server Rack (Open Frame)", "Server Rack (Split Front Doors)" and "Server Rack (Front + Rear Doors)" for both sizes (no "24U" / "42U" in the name); the descriptions still say 42U / 24U.
- [ ] No Data Center block name carries a size: servers read "Compute Server", "KVM Console", "UPS" (no "6U" / "12U"); "Rack PDU (Feed A)", "Raised Floor (Solid)", "Containment Door", "Containment Roof", "Cable Tray, Hanger Rods".
- [ ] **Rack Servers** contains 10 kinds, in this order: Timer, Event Controller, KVM, Status, UPS, Programmable, Compute, Storage, Switch, Blank.
- [ ] No Data Center block still appears under the vanilla Wall Panel, Door, Timer, Battery, LCD or Control Panel tiles.
- [ ] Every block shows its own icon, not a vanilla icon and not the "unknown" icon.
- [ ] The icons sit well beside vanilla icons: tone, angle and size.
- [ ] Each icon can be told apart at toolbar size. Drag one of each to the toolbar to check.
- [ ] Search finds the blocks by "rack", "server", "UPS" and "KVM".

## 2. Placement and the mount-point probe

- [ ] Place racks in a row: 42U and 24U, all three variants, flush side by side, with no gaps and no z-fighting on the shared sides.
- [ ] Place a second row facing the first across a 1.5 m aisle (6 cells).
- [ ] Slot every server type into a rack: Timer, Event Controller, KVM, Status, UPS (12U, two slots), Programmable, Compute, Storage, Switch, Blank.
  - [ ] Each server snaps into a slot and sits on the rails.
  - [ ] The ears land on the rack posts.
  - [ ] Placement fix (2026-10-18): aim from the aisle at the back of an empty slot (the rear stop): the ghost is green
        and fills the slot. Also aim at the rear third of a rail and at the rear of the slot floor / of the server
        below: green, same seat.
  - [ ] Aim at the FRONT third of a rail or of the server below: the ghost sits one cell forward and is RED (no
        mount point). It must never turn green one cell forward.
  - [ ] Turned round (face to the rear) a server also seats (Ruling P4-13).
  - [ ] Top slot of a 24U, aiming right of the slot's middle: the ghost pops up out of the open top (known residual;
        aim left of the middle or from above).
  - [ ] A KVM in a 42U SplitFront slot still waits for the front doors (rack link finds the rack beside it).
  - [ ] Nothing builds onto a server's top any more (no Up mount); a server still sits on a floor.
- [ ] Place a server in the top slot of a 24U rack: it sits under the 5 mm roof without visible overlap.
- [ ] Run the probe: `tools/scripts/se2game.py exec -f mods/DataCenter/Source/Model/review/probe_mountpoints.csx`. It must match the offline checker:
  - [ ] 42U racks: groups F/B/L/R/U/D 1/3/4/4/5/2, 120 occupied cells (placement fix + Plan 3's freed PDU columns
        and containment rail; `build_report.json` "summary" is the reference);
  - [ ] 24U racks: 0/2/3/3/6/1, 60 occupied cells;
  - [ ] servers: 6 occupied cells; UPS: 12.
- [ ] The probe's DisplaySize shows 2.5 for 42U, 1.25 for 24U and 0.75 for every server, and the RelativeBlockSize values are 1 (24U) and 2 (42U).
- [ ] A server's front face takes no block (mount directions without Forward, Ruling 12). The UPS front and back take no block either.

## 3. Doors (Task 9)

- [ ] Use a leaf: both leaves swing **outward toward the aisle**, about the outer hinges, to about 85°. The rear leaves on Front + Rear open toward the rear.
- [ ] Neighbouring racks with every door open: the leaves do not clip each other (30 mm clearance at 85°).
- [ ] **One handle leaf toggles both leaves.** The passive leaf has no handle but also toggles the door: every leaf carries a UseDoor box. Decide whether that is acceptable.
- [ ] **The leaves have no collider.** You can walk into the 0.25 m door zone of a closed door; only the server faces stop you. Decide whether that is acceptable.
- [ ] **The perforation renders see-through** (MetalPerforationSteel, a construction-stage material, two-sided) on both sides of the leaf and on the tray floors. The servers and LEDs show behind a closed door.
- [ ] The vanilla DoorSliding sound on a swing door is acceptable.
- [ ] The doorway detector stops a closing door when a player stands in the leaves' path.
- [ ] Doors on an **unpowered grid** (no battery or reactor, grid switched on): the doors still open, the fans spin and the hum plays. Working = Functional + grid on + Enabled; consumption is Amount 0.

## 4. Tray fans and hum (Task 9)

- [ ] 42U door racks: the two tray fans spin while the rack is Working and stop when the grid is switched off.
- [ ] **The door-rack fan tray exists only while Functional.** Under construction or broken, the fan lane shows bare openings. Acceptable?
- [ ] 42U Open rack: **the fans always spin**, even while under construction (static children with no controller). Acceptable?
- [ ] **The hum mix**: the door racks play GyroscopeSM, the KVM plays the LCD sound, and the Timer, UPS, Event Controller and Status keep their vanilla loops.
  - [ ] A full row is not too loud or too droning.
  - [ ] The loops stop when the grid is switched off.

## 5. KVM (Task 8)

These items are the **scripts OFF** (data-only) KVM. With `-loadScripts` the KVM is the scripted one of §12.5: the
door interlock and the load-bug fix below then no longer apply.

- [ ] A new KVM spawns **Off** (stowed; 2026-10-18 fix). Switch it On: the drawer slides 0.45 m and the screen folds up **+100° about +X**, toward the operator, not into the rack. Switching it Off stows it.
- [ ] The screen moves with the drawer: it spawns as the drawer's child at the hinge.
- [ ] The terminal still opens when the KVM is Off (aim at the upper modules: since Plan 4 Task 9 the drawer band is the On/Off use box, §12.5).
- [ ] **The KVM pops out through closed doors.** Behind closed front doors, a KVM that is On pokes through the leaves. Expected (no data-only interlock); switch it Off or open the doors. Note how it looks.
- [ ] Load bug: after a world reload or repair, a KVM that is On may show **stowed** until it is toggled.
- [ ] A popped KVM in a top slot covers 0.13 m of the slot above. In a 42U top slot it reaches into the tray; in a 24U top slot it reaches through the roof.
- [ ] The Programmable shell's amber status lamp (EmissiveAmber, used as a model material) renders amber.
- [ ] **Stand-ins (Plan 5 Task 8).** Under construction the closed drawer and lid show in
      the bay (construction material). One hit on a complete KVM (any health loss ends Functional) despawns the real
      drawer and screen and the closed stand-ins show at once; weld it back to full: the real ones return.
      Shoot one KVM zone (the front module) until it breaks off: the surviving drawer piece in the core is closed by
      a break face where it was cut (no raw edge, nothing floating; final review M4).

## 6. UPS (Task 7)

- [ ] Insert and remove cells **by aiming at the slot and pressing Use**: Cell 1 on the front bay, Cell 2 on the rear bay.
  - [ ] On a Front + Rear rack, the rear doors must be open to reach Cell 2.
- [ ] The cell orientation matches vanilla Battery50 in both bays.
- [ ] The inventory shows **two slots** of 25 kg, Power Cells only.
- [ ] With 2 full cells, the capacity reads **360000** (2 × Battery50), and charge and discharge follow the doubled rates.
- [ ] A new UPS ships with 2 cells at 30 % (mirrors vanilla).

## 7. Functional servers (Task 6)

- [ ] **Timer:**
  - [ ] the indicator states work: Idle, Counting (blinking COUNT lamp) and not powered;
  - [ ] the terminal shows "SERVER TERMINAL";
  - [ ] the timer triggers actions like a vanilla Timer50.
- [ ] **Event controller:** the T and F lamp rows light with the True and False states.
- [ ] **Status display:** the LCD shows text across its whole 2:1 screen (1024 × 512).
- [ ] **On the completed block,** the screen and lamp slots that live in AlwaysHidden construction objects show.

## 8. Reload

- [ ] Save, quit and reload the world. Racks, servers, door states, UPS cells and their charge, and the timer and LCD settings all persist.
- [ ] No new errors in the game log about DataCenter definitions after the reload.

## 9. Survival costs (Ruling 10, Task 10)

- [ ] In survival, open each block's component list in the build menu. It must match NOTES.md "Task 10: costs" (the probe's Items line too):
  - [ ] Rack42 Open: 9 Steel Plate + 7 Construction, plus 7 Steel Plate optional (merge main -> plan3-room: 120 occupied cells);
  - [ ] Compute: 1 + 1, plus 1;
  - [ ] UPS: 9 Construction + 1 Electronic Parts, plus 4 Construction;
  - [ ] cable trays (Ruling P2-26, one unit = 1 Steel Plate + 1 Construction, plus 1 Steel Plate, per 0.5 m of run): Straight Short 1 unit, Straight Long 3, Horizontal Turn 2, Cross 4, Rack Drop 2;
  - [ ] Hanger Rods 0.25 / 1.0 / 2.0 m: 1 / 2 / 3 Steel Plate.
  - [ ] Room and rack balance (Plan 3 Task 12): Rack24 Open 6 Steel Plate + 4 Construction, plus 5 Steel Plate (the frame floor: never under the Timer server); CRAC 9 Steel Plate + 7 Construction + 3 Motor + 2 Wire, plus 7 Steel Plate; PDU Cabinet 9 + 7 + 1 Electronic Parts + 2 Wire, plus 7; Aisle Sign and Rack Label 3 Electronic Parts + 2 Wire + 2 Glass, plus 3 Steel Plate (one vanilla LCD); Hanging Aisle Sign twice that.
- [ ] Welding a block stops at its functional stage until the critical items are in, as on vanilla blocks.
- [ ] The door racks feel as tough as the open racks: both are Mostly Hollow now.

## 10. Damage, grinding, LOD and paint (final review)

- [ ] **Grinding:** grind one block of each family (rack, decorative server, functional server). The components come back.
- [ ] **Damage:** damage a rack (Task 9c). It dents (its own Damaged model), then breaks in chunks: full rack 8 (plinth and top tray halves, each column's lower and upper half), half rack 4 (plinth, columns, roof); FracturedMaterial01 on the cuts. On a door rack a dead column zone makes the door Broken (critical).
- [ ] **Half-rack roof:** break the half rack's roof zone. Anything mounted on its top centre loses that mount.
- [ ] **Rack subparts:** note how the door leaves and side skins behave when the column under them breaks (they are subparts, not fracture zones).
- [ ] **Servers (Task 9c):** shoot a 6U server's front: the face module breaks off first and its terminal / LCD stops responding while the server keeps working; destroying the core (middle) makes it Broken.
- [ ] **UPS destroyed with cells inside:** note whether the cells drop or vanish (Task 7 deferral).
- [ ] **LOD:** walk away from a row. The LOD0 to LOD3 switches are not jarring, and the interim LastLOD box takes the block paint: a black rack must not turn grey at a distance.
- [ ] **Construction and damage look (Plan 5):** the stages are no longer ghost-only. Under construction each block shows a
      see-through cage until 30 % and solid supports from 30 %; a shot block keeps no cage and shows Deformed paint and its
      stand-ins. Checked in section 14 (Damage and build states (4.0)) below.
- [ ] **Paint:** paint a rack and a server in a non-default colour. The Colorable parts follow; the black parts stay black.

## 11. Cable trays (Plan 2, Tasks 1-10 and 9b)

Offline only so far (tests, the contract sweeps, the SDK build, the offline definition validators). Nothing in this section has been seen in game yet.
Needs: the 38 tray blocks are in the **Data Center** subcategory (see section 1 for the menu). Start in a creative world with a row of racks:
4 full 42U racks side by side plus 1 half rack (24U), and a second row across a 1.5 m aisle. Use Data Center > Cable Trays: Full unless a step says otherwise.

### Cable tray decisions to confirm

Recorded in `docs/superpowers/sdd/data-center-cable-trays/progress.md` and the plan's "Decisions". Approve or reject each:

- [ ] **P2-1, one style.** Only the wire basket, 7 shapes x 4 densities. No ladder style (`tray_plan` keeps a `style` argument so one can be added later).
- [ ] **P2-2, 38 blocks.** The 28 (7 shapes x 4 densities) plus 10: Rack Drop x3 (no Empty Drop, there is no lane to feed it), Reducer x3 (each steps down one level and they chain), Long Drop Chute x1, Hanger Rods x3 (0.25, 1.0, 2.0 m).
- [ ] **P2-18, the "real tray tee".** The branch-side lanes turn into the branch from both ends, the far side runs straight, the fibre lane is one split collar, and there is no saddle. This replaces the brief's pass-through "tap" tee (impossible at Full density).
- [ ] **P2-21, the fixed silver basket.** The basket wire and hardware are a fixed galvanised metal (BrushedMetal) and are **not paintable**. Only the data cables follow the block paint (the power cables, fibre and steel keep their own colours). A painted basket would always match the painted data cables. Are you happy with silver baskets? Flipping back to a paintable basket is a one-line change.
- [ ] **P2-23, P2-25, P2-28, the LOD0 triangle-budget overages.** TurnH Full is 4512 tris (the per-metre guide is 3000/m for a 1 m fitting), Drop Full about 6000 (a Drop on every rack), and all Full pieces carry cable-end caps (+16 tris per bundle end, about +10 % LOD0 on StraightS, StraightL, Cross and TurnDown Full). All stay inside Keen's limits and LOD1/LOD2 meet the per-metre budget. Accept if the frame time check below is fine.
- [ ] **P2-26, length-scaled costs.** One unit = 1 Steel Plate + 1 Construction (+ 1 Steel Plate optional) per 0.5 m of run: Straight Short 1 unit, Long 3, Turn 2, Cross 4, Drop and Reducer as 1 m runs (2). Rods cost 1 / 2 / 3 Steel Plate. Survival balance is your call.
- [ ] **The 4 non-breakable blocks.** The three Hanger Rods and the Chute cannot be given fracture zones (their rods, rails and rungs are disjoint members; Havok needs fracture colliders connected within 0.1 m). They are indestructible-by-damage decor and can only be ground down. The other 34 trays break. Acceptable?
- [ ] **Other rulings, for the record (no action unless you disagree):** P2-19 bend radii 0.05 m smaller than first planned; P2-22 three light pieces use a 3-LOD chain; P2-24 TurnUp/TurnDown struts run flush across the full 0.5 m; the trays clone the vanilla decorative Pipes insert (the Hanger Rods clone the vanilla strut); PCU is 5 per tray block; tray blocks use `AutoRotateFace: null`; manager cabling inside the racks is deferred to Plan 3.

### 11.1 Placing a run over a rack row

- [ ] Place a **Straight Long (Full)** above the first rack. Its tray should hang 0.5 m above the rack top, centred 0.125 m in front of the rack centre.
- [ ] Chain Straight Long and Short pieces along the whole row of 5 racks, then a **Rack Drop** over each rack: the run reads as continuous with one strap rhythm (a strap every 0.25 m, no doubled strap at a joint).
- [ ] Look along the run from the end and from the aisle: the bundles line up across every joint (no steps, gaps or overlap of cable at a joint).
- [ ] Check frame time with a 50 m Full run in view, and compare it with an empty scene (record both fps).
- [ ] PCU: each tray block shows 5 in the info screen.

### 11.2 Snapping and joints (floor to floor)

- [ ] Pieces snap end to end only when both floors face the same way ("floor to floor"). An upside-down tray must refuse to snap, not join with a lane mismatch.
- [ ] A piece used backwards (rotated 180 degrees about the floor normal) joins its neighbour with lane-for-lane matches. TurnH used as a left and a right turn (both hands).
- [ ] **Placement auto-rotate:** aim a tray at a ceiling and at a floor. It must not flip upside down (`AutoRotateFace: null`). Placement uses `AlignWithMountPoints=true` (kept from the vanilla Pipes placer): check that it snaps to the mount faces sensibly, not to some unexpected side.
- [ ] A **vertical jog**: TurnUp, two or three riser Straights, then TurnDown rotated 180 degrees. Every block lands on the grid and the lanes line up at both bends.
- [ ] **A mixed-density joint without a reducer** (Full to Low): the shared lanes match and the extra lanes simply end at the port (documented behaviour, not a bug).
- [ ] **Reducer chain** Full, Moderate, Low, Empty: every step has no loose cable ends, and the reducer's rubber boots and clamp read as intended.
- [ ] The Reducer is directional: placed backwards it steps the density up the other way and still joins.

### 11.3 Every shape (Empty, Low, Moderate, Full)

- [ ] **StraightS, StraightL:** each density at 0.5 m and 1.5 m. At Full the cable load is visible above the 0.10 m wall (data bundles nest over the power bundles).
- [ ] **TurnH:** both hands; smooth bend, straps on radial lines, cables not kinked (the 15 degree facets are visible at LOD0, judge them).
- [ ] **Tee:** the branch lanes turn into the branch from both ends, and the yellow fibre is a single collar plus a breakout tie 0.12 m past it. Check there is no smeared or fused cable near the collar (the branch cable is fused to the fibre bundle for about 0.19 m).
- [ ] **Cross:** the crossing bundles ride a crossover saddle with its "X-OVER" stencil and the through bundles are not touched. The four corner cells are free for other blocks (Tee and Cross), with an up to 8 mm graze of the junction fillet into those cells: place a block into a corner cell and check for visible clipping.
- [ ] **TurnUp riser and TurnDown:** the strut runs flush across the full 0.5 m, so check the neighbour joins without a visible seam, and a riser run of 3 or more joints lines up.
- [ ] **Junction walls** step from 0.15 m at the junction down to 0.10 m at the ports: neighbouring straights meet flush with no visible lip.
- [ ] Strap buckles read as dark/dull metal, not bright squares (previews used a brighter stand-in).

### 11.4 Drops over racks, and the Chute on a 24U

- [ ] **Rack Drop over 4 full racks:** the two waterfalls land in the brush plates over the front cable managers of each rack. The landing collar sits 1 mm above the plate, so check for a visible gap at the landing.
- [ ] Open the rack doors (they swing to 85 degrees) under a Drop: the doors do not hit the waterfalls or the Drop.
- [ ] **Drop plus Chute onto the half rack (24U):** the Chute foot plate seats in the half rack's roof grommet brush lips and the waterfalls follow the ladder rails with no poke-through into the rack.
- [ ] A Drop at Low and at Moderate density lands just as well.
- [ ] The waterfalls peel off the data lane at a natural angle, with no cable overlap near the split collar.
- [ ] Drop Full LOD0 is heavy (a Drop on every rack): look for hitching with 5 racks of Drops in view.
- [ ] The Drop's underside mounts (landing collars) snap onto the rack top and onto the Chute top plate; the Drop does not snap anywhere else.

### 11.5 Rod hangers at ceiling heights

- [ ] Ceiling-hung Full run on **Hanger Rods 1.0 m** under a ceiling 1.25 m above the tray: the rod hanger's couplers mate only with the tray's rod plates (not with any other face), and the rods snap only on the plates. Repeat with the 0.25 m and 2.0 m hangers and with a mix.
- [ ] A hanger stacked on another hanger: the Up hints repeat the coupler rectangles, so this may snap. Does it look wrong (anchor plate and ceiling channel mid-rod)? Note it.
- [ ] Rods reach a ceiling and the ceiling channel looks fastened; the hanger icons on the toolbar are faint thin lines (known; a stylised icon is a design call).
- [ ] The Hanger Rods placer: no unexpected auto-rotate, and no particle-effect / dummy error in the log.

### 11.6 Mounting: ceiling, wall, floor

- [ ] **Mount faces:** a tray attaches only through hardware: ports to each other, the rod plates (Up face), the strut end plates (across faces) and the strut bottom (Down). It must not attach to the open top of the basket.
- [ ] **Ceiling-hung** (on rods), **wall-mounted** (a run along a wall on its strut end plates) and **floor-standing** (a run on its floor struts) all work.
- [ ] Walk under a ceiling run: the 0.5 m clearance above a rack does not block a rack door or the player.

### 11.7 Densities and paint

- [ ] The four densities read apart in the viewport: Empty (basket only), Low (2 data bundles), Moderate (adds yellow fibre and grey power), Full (adds a second data layer and black power).
- [ ] **Paint** the data bundles in blue, teal and black: only the data cables (two bundles at Low, four at Full) change colour. The fibre (yellow), the grey and black power bundles and the steel basket do **not** change.
- [ ] **Silver basket:** the fixed silver basket always contrasts with the painted data cables. This is the P2-21 decision (see above); confirm you are happy with it.
- [ ] Repaint a whole run (all densities) in one colour: no mismatched colour at a joint.

### 11.8 LOD pops

- [ ] Walk away from a **20 m Full run** (with turns): note each LOD switch. The straps, cable lay and bundle layers reduce without a jarring pop, and the basket card at far range matches the basket (no colour pop, since the basket is a fixed colour).
- [ ] The **3-LOD pieces**, where LOD1 is the flat card: Empty and Low pieces, StraightS Moderate, Reducer Low and StraightL Low. Judge the LOD1 pop (P2-22).
- [ ] The bends' last LOD is an angular L-shaped chamfer: check it is not obtrusive at the last-LOD range.
- [ ] Junction walls at range stand at 0.10 m (the 0.15 m step disappears at LOD2).
- [ ] The custom split normals (the radial cable shading) import cleanly: the cable highlights run smoothly along each strand and do not band every 0.25 m.

### 11.9 End caps

- [ ] A **free end** of a run (Straight with nothing attached, an unused Tee branch, a Cross leg) shows solid cable ends (the cut section of each bundle), not hollow star-shaped strands with silver pins.
- [ ] At a **joint** the caps are invisible (buried 1.5 mm inside the strand skin) and show no coplanar flicker.
- [ ] The hairlines: a 2 mm gap between the rod coupler washer and the tray's rod plate, and a 1 mm landing gap at the Drop collar, are not visible at normal viewing distance.

### 11.10 Construction stages

- [ ] **Weld** each of Straight, Turn, Tee, Cross, Drop, Chute and a Hanger Rod from nothing: below 30 % the zone-shaped cage shows, from 30 % the hangers and struts are solid, and the cables, ties and boots arrive at completion (the Chute and Rods are unfractured and keep the old ghost stages). The finished model appears at the end. Details: section 14.1.
- [ ] **Grind** one tray block of each shape back to nothing, and the components come back (cost per 11 above).
- [ ] The cost lines match section 9 (Straight Short 1 unit, Long 3, Turn 2, Cross 4, Drop 2, Rods 1/2/3).

### 11.11 Breaking and damage

- [ ] **Zones break off:** damage a Straight, a Turn, a Tee, a Cross and a Drop (grinder or weapon). Zones (2 to 4 per block) break off, with the vanilla fracture material on the break faces.
- [ ] **Damaged model:** a partly damaged block switches to the dented Damaged model (Task 9c: at most 2x the Fractured triangles; watch for a hitch on the switch).
- [ ] **Colliders (Task 9c):** once a bend or a Drop has lost a zone, walk and shoot through its inner corner / beside its waterfalls: the colliders now follow the solid, so there is no invisible wall there.
- [ ] **Critical zone (functional blocks only: servers, UPS, door racks):** killing the critical zone does NOT destroy the block; it marks it Broken (a functional block stops). The block is destroyed only when its overall integrity drops below 30 % (DestructionThreshold). Check both. Cable trays and open racks are structural and have no critical zone (Ruling P2-30): they never show Broken, they just die at 30 % integrity.
- [ ] **Non-breakable:** the three Hanger Rods and the Chute take damage but never fracture; the Chute and rods can only be ground. Note anything surprising.
- [ ] The light pieces (StraightS Low, TurnH Empty, TurnUp Empty) break cleanly. TurnUp Empty has no break faces (open 6 mm wire ends only) and that is expected.
- [ ] A Drop broken off a rack falls cleanly and the rack beneath is undamaged.
- [ ] **Old saves:** a grid saved with the hotfix build (breakable removed) now carries the BreakableBlockComponent. Load such a world and watch the first load for errors.

### 11.12 Save and reload

- [ ] Build a mixed run (all shapes, Drops, a Chute, Rods), save, reload: every block and every joint is where it was.
- [ ] No tray-related definition errors in the log on load (the earlier world-load failure came from missing fracture models; the offline validator test covers it now).

### 11.13 Mount-point probe

- [ ] Place one of each tray block, then run the probe: `tools/scripts/se2game.py exec -f mods/DataCenter/Source/Model/review/probe_mountpoints.csx` (it now matches `DC_Tray`, which includes `DC_TrayRods`, as well as the racks and servers). Paste its output next to this item. Compare it with `Source/Model/build_report.json` (bounding box, occupied cells and mount groups per face).

## 12. Scripts (Plan 4): one ordered pass

Everything here is verified offline only (CompileCheck, CoreTests, pytest, the decompiled 2.4.0.95 code). Follow it top
to bottom in one session; each part builds on the one before. Use a **copy** of a test world for 12.6. Paths are
relative to `mods/DataCenter`; `PROBE` below is `tools/scripts/se2game.py exec -f Source/Model/review/probe_scripts.csx`
(run from the workspace root; it reads the plugin's connection settings itself, never paste or print them). Fix any
compile error the probe shows and note it. The log is the game's log file; "no `[DataCenter]` lines" means none at all.

### Decisions to confirm (scripts)

Decided during Plan 4, not by you (ledger `docs/superpowers/sdd/data-center-scripts/progress.md`). Confirm or reject:

- [ ] **P4-1 = A': the Programmable's scripting component is always in the data.** Saves are identical with scripts on or off and your script text survives; the cost is that with scripts OFF a Run ends in a compile error instead of the editor being absent.
- [ ] **P4-12: the top slot of a 42U rack uses the data-only KVM motion** (slide and fold together), because the containment rail above would otherwise be touched by the fold's mid-arc. That one slot is less polished than the others; no placement restriction.
- [ ] **P4-13: the door interlock looks only at the door on the KVM's face side.** A KVM facing a side with no leaves is never held back (the same as scripts OFF).
- [ ] **The PSU lamps (two on the rear) stay amber** with scripts on; only the SCRIPT STATUS lamp and the LCD bar go green.
- [ ] **The KVM motion timings:** open about 2.35 s to settle (drawer slide about 1.1 s with a peak under 0.9 m/s, a beat, then the fold with a ~1 degree bounce), close about 1.8 s, fast stow about 0.6 s, door-open delay 0.15 s. Too slow, too fast, too bouncy? Knobs: `Scripts/Client/Core/KvmMotionTuning.cs` (e.g. `StopPreload` 0.025 to 0.03 if the close's last 4 cm feels sluggish). P4-11.
- [ ] **The generic Use hint:** Use on the KVM shows vanilla's "Press F to enable / disable" under the block's name and the screen shows "open terminal", not KVM-specific wording; there is no click sound (the hum starting or stopping is the feedback). P4-8a.

### 12.0 Setup

- [ ] Quit the game. Close the SDK. `pgrep -x Modern.bin` prints nothing.
- [ ] `bash Source/Model/integration/install.sh --apply`, then `tools/scripts/se2mod.py build DataCenter` (expect `Exiting with 0.` twice).
- [ ] **Test world** (creative, large-grid station with a reactor or battery): a KVM in a **42U SplitFront** rack (doors closed, KVM On); one in a **42U Open** rack (slot 5); one in the **top slot (8) of a 42U** rack; one in the top slot of a **24U** rack; one **FrontRear** rack with a KVM facing the rear; one **standalone** KVM; two Programmables; two KVMs one above the other in a rack.

### 12.1 Scripts OFF first (about 10 minutes; the control run)

Launch **without** `-loadScripts`: `tools/scripts/se2mod.py play DataCenter --native --no-scripts` (no need to move `Scripts/` aside any more; without the flag native `play` adds the switch whenever `Scripts/` exists).

- [ ] World loads, no crash. No `[DataCenter]` log lines.
- [ ] **Programmable (terminal G):** listed with On/Off; Off and On both work; aiming at the management strip (right-hand) opens the terminal, aiming at a sled does not. The LCD reads "SCRIPT HOST" / "PRG-06", the lamp legend "SCRIPT" / "STATUS".
- [ ] **LED:** the SCRIPT STATUS lamp, the LCD status bar and the rear PSU lamps are all the same amber, On or Off.
- [ ] **Script editor present with the starter program.** Press **Run, Check and Debug**: each ends in a compile error shown in the panel; nothing crashes (the game stays up and responsive). The script text is still there afterwards.
- [ ] **KVM, data-only:** Off then On: drawer and screen move together, linearly; the KVM pops out through the closed SplitFront doors (known and accepted, Ruling 15); a KVM that loaded On after a world load may show the old load bug. Use on the drawer pull bar toggles it (12.5 covers the details).
- [ ] Save the world, quit (keep this save for 12.6).
- [ ] Core §3 to §5 items still hold (doors, tray fans, KVM, as in sections 3 to 5).

### 12.2 Launch with scripts ON

Launch with `-loadScripts`: `tools/scripts/se2mod.py play DataCenter --native` (the Steam form: add `-loadScripts` to Launch Options). Load the same world.

- [ ] **No script load error:** the log has no `Error when loading scripts for DataCenter`.
- [ ] **Injection lines:** `[DataCenter] script the KVM: 3 edit(s): ...`, `[DataCenter] programmable status lamp: 'EmissiveScriptStatus' -> EmissiveGreen while Working, on 2 model(s) ...` and `[DataCenter] programmable: scripting available on '...' (component in data, Route A')`. No `keeps the data-only motion` line, no `left amber` line, no `could not ...` line.
- [ ] **No validator noise:** the one Info line "Model is set, but no meshparts" from the empty BlockMaterialSwapper may appear; there is no error or exception mentioning `BlockMaterialSwapper`, `MaterialReplacements` or `InGameScriptingComponent`. The world loaded with the Programmables' mixed bundle versions (Game2 2.4.0.95 beside VRage 2.3.0.467) without a load error.
- [ ] **No engine assertion:** no `Assertion Failure` line mentioning `Use of Entity.Has` (check again at exit; a diagnostic report on exit means fail).
- [ ] Pre-Plan-4 Programmables in an old test world still exist (no `EOB Migration FAILED`); their paint, build progress and damage reset to the prefab defaults (expected).

### 12.3 The probe

- [ ] Run `PROBE` with the world loaded and a Programmable and KVMs placed. Every line reads `ok`: the switch is on, `DataCenter.Simulation` and `DataCenter.Client` are loaded, the reflection targets exist (from the game and from inside the mod).
- [ ] Section 5 (Programmable): `ProgrammableLedInjector.ReflectionTargetsFound: True`; `InGameScriptingComponent` present on the server entity and absent on the client; `status part 'EmissiveScriptStatus' mapped to green` equals the switch.
- [ ] Section 6 lists the `[DataCenter]` log lines.
- [ ] Section 7 (KVM): `KvmInjector.State: Applied`; `server entities with a DataCenter script component: 0`; each KVM's target matches the door rule and its path matches its slot (`link path DataOnly` only for the 42U slot-8 KVM); the drawer offset equals travel x slide (error < 1 mm); the screen orientation equals rest x the fold (|dot| > 0.99999). Re-run it later in 12.5, mid-motion states vary.
- [ ] **7c, the surgery refusal paths:** every line `ok`: a null prefab, a missing dependency, a shared composition, a missing type and a wrong definition type are `Refused`; the KVM prefab and the drawer are `AlreadyDone`. Each refusal logs one `could not ...` line; nothing else changes.

### 12.4 The Programmable, scripts ON

- [ ] **Script editor with the starter program** ("PRG-06 script host"); its first lines tell the player that Run needs `-loadScripts`. **Check** reports success. **Run** runs it without an error.
- [ ] **No double run:** a program that logs in `Update` logs once per update, not twice.
- [ ] **LED green:** with the Programmable On, the SCRIPT STATUS lamp and the LCD status bar are green; the two rear PSU lamps stay amber. Compare with `Source/Model/preview/plan4/programmable_scripts_on_*.png`.
- [ ] **Off and on:** switch it Off (amber), On (green), from the terminal and from the toolbar. Grind it below functional (amber while not Working), weld it back (green once Working). A Programmable placed after the load behaves the same.
- [ ] **Far LOD:** step back to LOD2: the LCD window quad is green, nothing flickers between LODs.
- [ ] **Damaged:** damage one to its Damaged model (On): the lamp and bar show vanilla's broken emissive, not green; Fractured zones still go green while Working. Break off the front module (`Fracture_01`, critical): destroyed, and the log mentions neither `InGameScriptingComponent` nor `BlockMaterialSwapper`.
- [ ] **Run in a running world:** leave a script running (`Running = true`), save (kept for 12.6).

### 12.5 The KVM, scripts ON

Watch the log for `[DataCenter]` lines throughout; none may be a fault line.

- [ ] **The sequence (Open rack):** switch it Off and On. On: the drawer slides out (about 1.1 s, soft landing), a short beat, then the screen folds up with a ~1 degree settle. Off: the screen folds flat first, then the drawer slides home. Compare with `Source/Model/preview/plan4/kvm_open_3q.gif` (local render).
- [ ] **Fold direction:** the screen folds up toward the operator (+100 degrees about +X), not down into the keyboard. If wrong, flip `KvmMotionTuning.LidAxisSign` (and the data's sign for scripts off).
- [ ] **Reversal:** toggle mid-slide and mid-fold: it reverses smoothly from where it is, never jumps or restarts. Reversing to Out with the lid half-up should not drive it back flat visibly before lifting (carry M2); note it if it does.
- [ ] **Use toggle:** aim at the drawer pull bar, press F: pops out or stows through the sequencer (slide, a beat, fold; fold first on the way in). Use on the upper modules (or the screen when out) opens the terminal. The terminal's On/Off flips with it, and a toolbar On/Off reflects it.
- [ ] **Door interlock (SplitFront, doors closed):** an On KVM stays **stowed** (no poke-through). Open the doors: it pops about 0.15 s after they read fully Open (probe: target `Out`, `door open` > 0.15 s). Close the doors while it is out: it **fast-stows** (about 0.6 s) and no leaf passes through the drawer or screen. Repeat closing from mid-motion. Optional: slow-motion check with `tools/scripts/se2game.py shot` during the close.
- [ ] **Face side (P4-13):** in a closed SplitFront rack a KVM facing the **rear** (no rear leaves) **deploys** while On; one facing the front stays stowed. In a closed FrontRear rack both stay stowed. Probe: `face side -1`, `door off the face (ignored, P4-13): True` for the first. If the front-facing one deploys and the rear-facing one waits instead, the data's front is the block's Backward: flip the generated bits (`dc/script_guids.py door_side_bits`).
- [ ] **42U top slot (P4-12):** the top-slot KVM moves slide-and-fold together (data-only path) and its lid never rises into the containment rail above. The 24U top-slot KVM runs the full sequence.
- [ ] **Standalone KVM:** out while On, in while Off (no rack, no waiting).
- [ ] **Reload and snap (the load bug):** with the Open-rack and standalone KVMs On and the doors open, save and reload: they show **out at once**, no animation; the closed-door KVM shows stowed. Repeat after flying away beyond draw distance and back (streaming).
- [ ] **Weld during play:** grind a KVM below functional (the drawer vanishes) and weld it back: it **animates** out, not a snap. Place a new KVM and weld it up: the same. (A KVM whose Working arrives more than 1 s after the load, e.g. a power network settling or a multiplayer join, animates out rather than snapping: that is the entry window, note how often.)
- [ ] **Destruction safety:** grind away the rack under an out KVM, and grind the KVM itself mid-motion: no crash, no log spam; an orphaned KVM behaves as standalone.
- [ ] **No toggle while not functional:** a KVM ground below functional shows no use hint on the drawer band; weld it back, the toggle returns.
- [ ] **Damage:** shoot the KVM's front until its front service module (Fracture_02, not the critical core) breaks: the toggle and Terminal hints disappear with it while the core may still stand.
- [ ] **Two KVMs one above the other:** aiming at the lower KVM's screen top may open the **upper** server's terminal (the lid covers 0.13 m of the slot above). Expected; note it.
- [ ] Re-run `PROBE` (section 7) once with the KVMs settled: all `ok`.

### 12.6 Save round trip (on a COPY of a test world only)

- [ ] **Scripts ON, save:** the Programmable with a script running, KVMs out. Save.
- [ ] **Quit, load with scripts OFF** (as 12.1): the world loads, the blocks are intact, no errors, no `EOB Migration FAILED`; the running Programmable shows a compile error, no crash. Save again.
- [ ] **Quit, load with scripts ON again:** the Programmable's script text survived both trips. The KVMs show their right state.
- [ ] **Reverse order:** a world first saved with scripts OFF, then loaded and saved with scripts ON, then loaded OFF: the script text survives and the world loads every time.

### 12.7 Multiplayer (if a second client is available)

- [ ] **Same setting on both:** host and client both with scripts: a client's Use toggles the KVM for everyone; each sees the sequenced motion.
- [ ] **Mixed:** host with scripts, client without, and the reverse. No error on either side; each client shows its own motion (scripted or vanilla) of the same KVM state. The differences are visual only.

### 12.8 The fault-pass probe (opt-in; do last, it faults one KVM until reload)

- [ ] Set `kvmFaultPass = true` in the probe and run it once: forgetting the rack, poisoning the cache with a child entity and running the drawer's job on a scratch transform each report `ok` with no exception; after three injected faults the targeted KVM is `Faulted` and snaps to its end pose. It stays faulted until the world is reloaded; the others are unaffected. Set it back to `false`.

### 12.9 Publishing (after the first Workshop or mod.io upload)

- [ ] The downloaded package contains `Scripts/` (subscribe on a second profile, or inspect the workshop folder read-only). Without it, scripts never run for subscribers.

### Cross-check: where each ruling and review focus is covered

P4-1 12.1, 12.4, 12.6 | P4-2 12.1 | P4-3 12.5 | P4-4 12.5 | P4-7 12.4 | P4-8a 12.5 | P4-10 12.3 (7c) | P4-12 12.5 |
P4-13 12.5 | Focus 1 (mid-motion) 12.5 reversal | Focus 2 (doors closing) 12.5 interlock | Focus 3 (load, repair) 12.5 reload and weld |
Focus 4 (missing state) 12.5 destruction, 12.8 | Focus 5 (pause, hitches) CoreTests (also: pause the game mid-motion; it must freeze, then resume).

## 13. Room pieces (Plan 3)

Build menu: Automation > Data Center, four tiles after Cable Tray Supports: **Raised Floor** (Solid, Perforated; 0.5 /
1.0 m), **Room Cooling & Power** (CRAC, PDU Cabinet, Rack PDU Feed A / Feed B; 24U / 42U), **Aisle Containment**
(Door, Roof; 1.0 / 1.5 / 2.0 m aisles) and **Signs & Labels** (Aisle Sign, Hanging Aisle Sign, Rack Label). Verified
offline only (tests, the placement checker, the SDK build); the hero renders are in
`Source/Model/preview/plan3-task-12/` (local, not in git).

### 13.0 Decisions to confirm (room)

Decided during Plan 3 (rulings P3-1..20, NOTES.md "Plan 3 summary"). Confirm or reject:

- [ ] **The CRAC cools nothing** (2.4 has no air or cooling system): it is a real powered load (25 in the power
      screen) whose fans spin and lamp lights only while On and powered. Its rear **O2 / COOLANT SERVICE** ports are
      **decorative** (blanked vanilla small conveyor-port frames; nothing snaps, no mount point) and are laid out to be
      switched on by data if Keen adds air vents.
- [ ] **No baked IDs:** racks say "RACK" (front header, kick plate, half-rack roof) and "RACK ID" (side hatch), the
      CRAC says "CRAC", each beside a blank riveted write-on tag. IDs come from the editable Rack Label / signs.
- [ ] **Contained aisles hide the rack-top labels:** the roof covers the rack tops' aisle edge, so mount labels on the
      edge facing the open aisle and sign the contained aisle on its door headers (T11 guidance; no new block).
- [ ] **Doors on a shared row:** a row between a contained cold and a contained hot aisle carries both aisles' end
      doors; their leaf pockets (W/2 each) share the row's 1.25 m depth, so this works for 1.5 + 1.0 m (or 1.0 + 1.0,
      1.0 + 1.5) aisles but not two 1.5 m or any 2.0 m aisle (`room.shared_row_doors_fit`).
- [ ] **Costs (Task 12 balance):** signs cost one vanilla LCD per screen face (the hanging sign two); the CRAC and the
      PDU cabinet cost the 42U open rack frame plus their kit (CRAC 3 Motor + 2 Wire, cabinet 1 Electronic Parts + 2
      Wire); no rack costs less than the dearest server (24U Open: 6 Steel Plate + 4 Construction, plus 5 Steel Plate).
- [ ] **Everything breaks** (user direction, not P3-10's "unfractured"): floor, roof, strips and signs fracture too.

**Setup:** a creative world with power (battery or reactor), the mod loaded (see the test session above). One test
room for all items: a 6 x 8 m raised floor, two rows facing a 1.5 m aisle, trays on rods over them.

### 13.1 The sixteen items

1. [ ] **Floor:** lay a 6 x 8 m raised floor of mixed tiles (Solid and Perforated, 0.5 and 1.0 m). Racks, the CRAC and the PDU Cabinet snap flush on it at tile seams and across them (offset 0, 0.25 or 0.5 m from a tile edge).
2. [ ] **Rows and roof:** build a 1.5 m cold aisle of two rows (racks + CRAC + PDU Cabinet). Roof panels (Aisle Containment > Roof 1.5 m) snap onto the containment rails over every unit, on both rows.
3. [ ] **Doors at both ends:** each bolts to the end racks' sides just beyond the row end; it opens and closes on use, blocks the player while closed, re-opens on an obstacle, plays the sliding sound, and keeps its state after a save and reload.
4. [ ] **Hot aisle and widths:** repeat 2-3 as a hot aisle (rack backs facing it), and with 1.0 and 2.0 m aisles.
5. [ ] **Clearances:** pop a KVM in a top slot and open the rack doors to 85 deg under the roof: nothing clips the roof or the door frame.
6. [ ] **CRAC:**
   - [ ] shows its load in the power screen;
   - [ ] fans spin and the RUN lamp lights only when powered and On;
   - [ ] stops on Off and when power is removed (2 s soft start, 4 s coast);
   - [ ] hum level (vanilla GyroscopeMID) is acceptable in a full row;
   - [ ] the fan state after a reload (load bug Q1 does not apply to InfiniteRotation; confirm).
7. [ ] **Rack PDU strips Feed A and Feed B** in a full (42U) and a half (24U) rack: they seat on the plinth receptacle and clear closed rear doors, the UPS rear bay and the servers (13.2).
8. [ ] **PDU Cabinet:** a Drop over the cabinet lands in its brush plates.
9. [ ] **Signs:**
   - [ ] type "AISLE 1 COLD" on the Aisle Sign on a door header, on a Hanging Aisle Sign on a `DC_TrayRods_100` under a tray, and "RACK A-01" on Rack Labels between the waterfalls;
   - [ ] in a contained aisle, put the rack labels on the rack-top edge facing the open aisle (the roof hides the aisle edge) and confirm the door-header sign is the readable one;
   - [ ] on a 24U rack the label mounts on the back pad only (13.3);
   - [ ] readability at 15 m, and the hanging sign's back face;
   - [ ] paint the frames blue (cold) and red (hot).
10. [ ] **Glass** looks right on the roof (FrostedGlass) and the door leaves (WindowGlassThin); else apply the Decision 13 fallback (MetalPerforationSteel).
11. [ ] **Weld and Grind** the construction stages of each family (floor, CRAC, cabinet, strip, door, roof, sign).
12. [ ] **Damage and destroy:** every room block breaks into its zones with the vanilla break faces and shows its Damaged model; the CRAC's fan sections are critical (a broken fan stops it); doors keep their criticals.
13. [ ] **PCU** per block in the info screen: floor 5, roof 5, sign 35, CRAC 30, door 150, PDU 5.
14. [ ] **LOD** transitions across a 20 m room; record the frame time with the full room in view against an empty scene.
15. [ ] N/A for this build: Task 9 (cable looms) did not run, so there are no looms to check.
16. [ ] **Probe:** place one of each room block and run `tools/scripts/se2game.py exec -f mods/DataCenter/Source/Model/review/probe_mountpoints_room.csx`; paste its output here and compare with `Source/Model/build_report.json` ("summary": groups per face, occupied cells; e.g. CRAC 1/1/1/1/4/1 and 200/200, Door 1.5 m 1/3/1/1/1/2 and 88/120) and the costs in NOTES.md (Items line).

### 13.2 PDU Cabinet and Rack PDU strips (Task 7 detail)

- [ ] Place a **PDU Cabinet** in a rack row (on the raised floor): it sits flush with the racks, its sides mount to them, a containment roof panel mounts on its rail, and a Drop lands in its top brush plates.
- [ ] Place **Rack PDU (Feed A) / (Feed B)**, 42U size, in a 42U rack's rear columns (aim at the plinth top in the rear corner): the strip snaps into the column (it mounts Down, on the plinth; its back rests on the bulkhead), its plug sits on the yellow socket, and nothing clashes with servers or the rear doors (open and close them).
- [ ] The same with the **24U** strips in a 24U rack (the strip stops under the top corner caps).
- [ ] A strip mounts only by its plug (Directions Down; Forward was dropped after the final review, I1, because it let a strip aimed up the column seat raised): in a rack it seats only at the column bottom, never raised (on a 24U rack nothing green sticks out of the top). With its Down mount it also stands on any Up face, such as a floor tile, a rack top or an empty server slot's floor (aimed into the slot): expected, not a defect (unchanged by the fix). It keeps its orientation when placed (AutoRotateFace off).
- [ ] Paint: the cabinet panels, the strips' face plates and cord channels, and Feed B's band take the paint; Feed A's band stays yellow.
- [ ] Break / grind: the cabinet breaks into up to 8 pieces, a 42U strip into 3, a 24U into 2; the Damaged models switch the lit lamps off. No load errors.
- [ ] LODs: walk away from a populated rack with both strips and from the cabinet: no jarring pops.

### 13.3 Signs and labels (Task 8 detail)

- [ ] **Aisle Sign on a containment door:** place it on the room side of a door's header (Backward face): it snaps flush and centred, its four back bolts on the header's threaded inserts. It does not mount by any other face (screen, ends, top, bottom).
- [ ] **Aisle Sign on a wall:** mounts by its back on any wall; nowhere else.
- [ ] **Edit the text:** aim at the screen, open the terminal: one surface, "Aisle Sign"; type "AISLE 1 COLD". The text fills the 4:1 screen without stretching (1024 x 256, AspectRatio 4) and the off-screen texture looks right (vanilla LCDScreen_Off_4.0).
- [ ] **Hanging Aisle Sign:** place a Hanger Rods 100 under a ceiling, turned so its two rods run along the sign's face, then the sign under it (Up face): the rod couplers sit on the sign's two rod plates. It mounts by nothing but its top.
- [ ] **Both faces:** the terminal lists two surfaces, "Front Face" and "Back Face"; set different texts and read each from its side. Aiming at either face opens the terminal.
- [ ] **Rack Label:** on a 42U rack's top front edge, between the Drop's two waterfalls (Down face on the rim); also on the back edge. On a **24U rack only the back pad** takes it (merge ruling: the placement fix freed the front pad's cells for the top slot's opening; a dedicated half-rack front mount may come later): check it mounts there, and that the front edge refuses it. Type "RACK 1.01": the 2:1 screen (512 x 256) reads from the aisle floor (the face tilts 15 deg down).
- [ ] **Hot / cold paint:** paint the frames blue in the cold aisle and red in the hot one; the screens, liners and end caps stay dark.
- [ ] **Power:** the signs work like a vanilla Narrow LCD (power and On/Off as vanilla; PCU 35).
- [ ] **Break them:** each 1.0 m sign breaks into 3 tiles (the middle one carries the screen: the display dies with it), the label into 2 halves; the break faces show the vanilla fracture material; a damaged sign shows the dented Damaged model with a broken screen.
- [ ] **Reload:** both faces' texts, the paint and the placement survive a save and reload.

## 14. Damage and build states (4.0)

**Status: Not yet run in game.** Plan 5 (vanilla-like construction and damage) was verified with tests, the offline
client/server walk, the SDK build and Blender previews only. Run it on native SE2 4.0 (Pulsar + LinuxCompat 1.1.0):
`python3 tools/scripts/se2mod.py play DataCenter --native`; logs in `~/.config/SpaceEngineers2/Temp/Logs`. Proton
currently renders SE2 4.0 all-purple on this machine, so do not use it for the look checks.

**Do the rack first-load test at the top of this file first** ("Next session", before everything else in this file): it is the one check whose failure breaks the
world load, and its fallback (Path B: `RACK_PATH = "B"`, the recipe there) changes what the rest of this section
tests.

**Setup.** SE2 closed; `bash Source/Model/integration/install.sh --apply`, then `tools/scripts/se2mod.py build
DataCenter` (both run after the plan5 merge, from `mods/DataCenter`; repeat only if the tree changed). Creative world, large-grid station with power,
one of each family laid out beside its vanilla analogue: Battery150 or Timer50 (servers, UPS), Gyroscope250 (CRAC,
KVM), CableStraight250 (trays), CatwalkSquareBase250 (floor), WindowFlat250 (roof), SlidingDoorNarrow250 (doors),
CircuitBreaker (PDU), LCDFlat50 (signs). Previews of every state are in
`resources/previews/DataCenter/dmg/dmg-build/after/sheets/` (local, not in git): compare against them.

**Blocks the checks name:** `DC_Srv_UPS` (bays, sparks), `DC_Srv_KVM` (drawer stand-in), `DC_CRAC` (fan stand-ins,
unpowered case), `DC_Contain_Roof_100` (glass build, Windows fragility), `DC_Contain_Door_100` (cage, sill), the
six `DC_Rack*` racks (first-load test), and one block of each other family.

**After every load and at the end**, grep the newest game log (`SpaceEngineers2_<date>_<time>....log`, not `_Render`):

```bash
L=$(ls -t ~/.config/SpaceEngineers2/Temp/Logs/SpaceEngineers2_*.log | grep -v _Render | head -1)
grep -n "should not be on server compositions\|Definition that is linked from" "$L"
grep -n -i "datacenter\|DC_" "$L" | grep -i -E "error|exception|unsatisfied|not found"
```

Pass = nothing printed.

### 14.1 Construction look (guide section 7, items 1-3)

- [ ] **Side by side.** Weld the vanilla analogue and one of our blocks from nothing; screenshot at about 5, 20, 40, 70
      and 100 %. The cage (blue, see-through) shows only below 30 %; at 30 % the supports and frame are solid
      metal and the cage is gone; the skin ghosts in with its zone; lamps, stencils, screens and cables appear only
      at completion. Do this for one block of every family: rack, server, UPS, KVM, tray (Full), CRAC, floor, roof,
      door, PDU cabinet, PDU strip, sign.
- [ ] **Cage proud of the skin.** The cage stands 4 mm outside the cell where the block fills it (vanilla does the
      same, measured). Look for flicker or clipping where it meets the skin below 30 % on rack sides, floor decks, roof
      glass and server shells. The NF-to-FR size difference is up to 12 mm: no visible pop when the model swaps.
- [ ] **See-through material.** The cage reads through the real construction material as it does in the previews.
- [ ] **The finished look at the functional threshold.** A block with critical items shows its finished look once the
      critical items are in, before the optional ones are welded.
- [ ] **Never a cage on a finished block.** Shoot a finished block: no cage. Grind one back below 30 %: the cage
      returns; weld it up again: gone at 30 %. A finished, damaged block shows no cage.
- [ ] **Door cage.** A containment door under construction shows a U-shaped cage (posts and lintel) and the doorway is
      open, as the vanilla sliding door.
- [ ] **Roof glass.** A roof under construction shows its panes as glass from the first weld; the frame is solid at 30 %.
- [ ] **Cables arrive last.** Weld a Full tray: the basket and hangers are solid at 30 %; the cables, ties and strap
      buckles appear only at completion, and no loose cable ends or collar rings float in the empty basket (the
      Drop's brush-collar rings stand alone until completion by design).
- [ ] **Other late parts.** PDU cabinet: breakers, lamps and sticker at the end. Floor: pedestals first. Sign: screen
      and stencils at the end.
- [ ] **LOD.** Walk away from a block under construction: the cage and supports do not pop at the LOD switches
      (the 42U racks' LOD1 cage is 608 triangles).

### 14.2 Damage look and fragility (guide section 7, items 4-5, 9)

- [ ] **Deformed paint.** Shoot a rack, a server, a tray, a floor tile: the painted metal looks scratched or gouged on
      the damaged zones, the player's paint colour is kept, the dents read (compare Gyroscope250).
- [ ] **Broken interiors (Keen's way, NOTES.md).** Break a PDU cabinet section (shoot one breaker column) and a CRAC
      fan section and its filter door: each hole shows a solid inside with the torn-wiring break texture
      (FracturedMaterial01, as Gyroscope250's), the cabinet's busbars and breaker backs in front of it, the CRAC's
      perforated coil face; never an empty dark box. Break a 42U rack's plinth front half: the rear half shows the
      same texture, not a hollow.
- [ ] **Fragility.** A rifle against a Structural block (a tray) and a Functional one (a server) of similar mass; time
      to kill and Ineffective hits. The Programmable's time to kill under rifle fire (it is Functional now, max HP x0.8).
- [ ] **Roof glass.** A grenade on a roof does nothing (Windows fragility, explosion x0). A rifle breaks the glass
      with the glass-shatter death; the damaged panes read as broken glass (they are flatter than the x2.0 look: they
      are at the x1.5 ceiling; say if it is too flat).
- [ ] **LCDs.** A screen's content disappears on the first zone damage and returns after full repair (signs, KVM
      terminal, status display).
- [ ] **Non-breakable.** A destroyed Hanger Rod or Chute leaves dented debris; note whether the game shows the
      Damaged model of a non-breakable block at all. The rod-hanger dents are faint (2.4-3.2 mm); if they should read
      as bent, raise `DENT["trayrods"]`.
- [ ] **Colliders and sill.** Break a containment door's frame: walk through the doorway with no step (the sill zone is
      exempt from the 1 % minimum share and clamped to the visible 8 mm threshold). Shooting the sill kills it early
      (accepted).

### 14.3 Damage effects (guide section 7, item 7)

- [ ] **UPS.** Sparks below 95 %, smoke 90-65 %, fire below 65 %, from each bay's cell contacts; each bay's effects
      stop with its zone. The death effect plays from the block centre.
- [ ] **Trays.** A tray sparks from the first scratch, on its cables; a section's sparks stop when it falls off. The
      Empty trays and the Chute never spark.
- [ ] **PDUs and deco servers** spark small (CircuitBreaker band); the cabinet with up to 3 emitters at once may read
      busy: say so (the alternative is one emitter).
- [ ] **KVM** sparks (ControlPanel25 band at x0.3). **Programmable** smokes and burns (Timer template), with the
      Timer's audio and a death effect at x0.5.
- [ ] **Single-centre-dummy blocks** (Task 4 note): a block with one centre emitter stops sparking when the zone holding
      that emitter dies while other zones live. Note which blocks this visibly affects.
- [ ] **A band whose dummy is missing shows nothing**, and nothing errors in the log.

### 14.4 Subparts and stand-ins (guide section 7, item 8)

A block is Functional only while fully built with no dead critical zone **and no health loss at all** (any hit ends
Functional: EffectiveBuildProgress = BuildProgress x integrity must stay 1.0). The stand-ins show whenever it is not
Functional, and hide when the real subparts spawn.

- [ ] **Racks (all six)**, after the first-load test: under construction, after one grinder tick, after one rifle round
      and with a dead column, the real side panels and the 42U fan tray are gone, the fans stop and the stand-ins show
      (dented with their zone, with closed cut faces where a seam crosses them); weld back to full and the real ones
      return with no jump. A dead column takes its stand-in with it; nothing floats where it was.
- [ ] **KVM.** Under construction, with a dead core, or after one hit: the closed drawer and lid show in the bay
      (construction material); a Functional KVM's drawer moves and the stand-in hides.
- [ ] **CRAC.** Under construction, after one hit, or with a dead fan section: the three parked fan stand-ins show; weld
      back to full: the rotors return and spin while On and powered. **An unpowered but intact CRAC is still
      Functional**: its rotors coast to a stop, the stand-ins do not show.
- [ ] **On/Off on every rack.** All six racks are in the grid console (G) with On/Off. Off stops the 42U fan rotors;
      the panels stay (they follow Functional, not On/Off); on the 24U open rack it does nothing visible. The door racks
      still need a powered grid to run their fans; the open 42U's fans spin regardless.
- [ ] **Paint.** Paint a rack, the KVM and the CRAC, then shoot them: the stand-ins take the player colour (and the
      Deformed look on the damaged model).

### 14.5 Penetration (guide section 7, item 6; not built, observe only)

- [ ] Fire through an open rack's gaps, through glass, and through two thin blocks in a row; note what the game does.
      Nothing in the mod models penetration.

### 14.6 Final

- [ ] Save, reload, repeat a few states (a half-built block, a shot rack): the state is kept and the log is clean.
- [ ] Frame time with a full hall of damaged and half-built blocks in view against an empty scene.

### Decisions to confirm (Plan 5)

These were decided during the build, not by you. Each is recorded in NOTES.md ("Plan 5 summary") and in
`docs/research/update-4.0/progress.md`. Confirm or reject each:

- [ ] **Ruling DB-1, the stage generator lives in the mod** (`dc/construction.py`); the `tools/se2model` copy is left
      unchanged and is superseded for this mod.
- [ ] **Ruling DB-2, the damaged-only hide names the scaffold only**; with no scaffold the last stage is empty.
- [ ] **Ruling DB-3, the scaffold** is a BrushedMetal lattice cage in FR LOD0 (LOD1 when it fits), never in the DM or a
      hull; trays and doors use their zone hulls; **OUTSET 4 mm** (the cage stands 4 mm proud, as vanilla).
- [ ] **Ruling DB-4, the scaffold budget** (at most 20 % of FR LOD0 and within the LOD margin; the PDU cabinet at most
      3 742, the 42U racks about 3.7k). Four tiny trays have no cage (StraightS_Low, StraightL_Empty, TurnH_Empty,
      TurnUp_Empty: no room for a minimum cage).
- [ ] **Ruling DB-5, roles per face**: support / frame / hide / glass map onto vanilla's groups; zone names never change.
- [ ] **Ruling DB-6, Damaged models at x1.2 of FR LOD0** (floors and roofs x1.5), applied without an in-game gate; the
      roof panes read flatter than before.
- [ ] **Ruling DB-7, vanilla spark bands copied verbatim**; the KVM gets ControlPanel25's band at x0.3; the Programmable
      is re-based on the Timer template (its audio and death effect x0.5 come with it).
- [ ] **Ruling DB-8, spark dummies follow zones**, at most 3 emitters per block; the UPS gets a centre dummy first plus
      one per bay.
- [ ] **Ruling DB-9, stand-ins exist only in FR and DM**, in the owning zone, in the keyed hide-when-active list.
- [ ] **Ruling DB-10, the racks' side panels and fan tray are ConditionalSubParts (Path A)** with stand-ins; they exist
      only while the rack is Functional. Path B (static children, no stand-ins) is `RACK_PATH = "B"` in
      `Source/Model/dc/config.py` plus the recipe under "Next session". The 42U racks' stand-ins take 2 560 of
      their FR LOD0 triangles (cut along the seams, with caps).
- [ ] **Roof fragility is Windows** (vanilla glazing; explosions do nothing to it; its destroy sound is the glass
      one). Revertable: set the roof back to Structural.
- [ ] **Programmable fragility is Functional, max HP x0.8** (was 1.0).
- [ ] **All six racks have On/Off in the terminal**, even where it does nothing visible (24U open).
- [ ] **The door sill zone is exempt from the minimum zone share** and clamped to the visible threshold, so it can die
      early while a broken door leaves no step.
- [ ] **The CRAC's venturi lips are a separate skin part**, built with the housing; its support share is 16.4 %.
