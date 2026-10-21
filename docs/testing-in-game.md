# Testing in game

The offline tests check geometry, definitions and the build, but some things only show in the game: how a block
looks next to vanilla, how it places, welds, breaks and sounds. Use this list after any change to models,
definitions or scripts, and before a release.

## Load the mod locally

1. Close the game, the HUB and the Editor (`pgrep -x Modern.bin` prints nothing).
2. Install and build (see `docs/model-pipeline.md`):

   ```bash
   bash Source/Model/integration/install.sh --apply
   python3 ../../tools/scripts/se2mod.py build DataCenter
   ```

   The build log should end with `Exiting with 0.` twice and show no warnings for `Assets\DataCenter\...`.
3. Launch with the mod enabled. With `se2mod.py`, `play DataCenter` adds `-loadScripts` when the mod has a
   `Scripts/` folder; add `--no-scripts` for the data-only run. On Steam, add or remove `-loadScripts` in the launch
   options.
4. Use a creative, large-grid station with power. Put one vanilla block beside each family for comparison
   (Battery or Timer for servers, Gyroscope for the CRAC and KVM, a cable block for trays, a sliding door, an LCD).

Keep the newest game log (`~/.config/SpaceEngineers2/Temp/Logs/SpaceEngineers2_<date>_<time>.log`, not the
`_Render` one) and a screenshot for anything unexpected. After each load, this should print nothing:

```bash
L=$(ls -t ~/.config/SpaceEngineers2/Temp/Logs/SpaceEngineers2_*.log | grep -v _Render | head -1)
grep -n -i "datacenter\|DC_" "$L" | grep -i -E "error|exception|unsatisfied|not found"
```

## In-game probes

`Tests/InGame/` holds C# snippets that print what the game actually loaded. Run them with a world loaded through
a game console plugin that can execute code (for example `tools/scripts/se2game.py exec -f <file>`):

- `probe_mountpoints.csx`: per placed rack, server and tray, its bounding box, occupied cells, mount groups per face,
  display size, mass and cost. Compare with `build_report.json` and `check_placement.py`.
- `probe_mountpoints_room.csx`: the same for the room pieces.
- `probe_scripts.csx`: whether `-loadScripts` is on, both script assemblies loaded, the reflection targets exist, and
  the state of each Programmable and KVM. Every line should read `ok`. It has an opt-in fault pass
  (`kvmFaultPass = true`) that leaves one KVM faulted until the world is reloaded.

`bash Tests/CompileCheck/run.sh probe Tests/InGame/probe_scripts.csx` compiles a probe offline first.

## Checklist

### Build menu and names

- [ ] Automation > Data Center shows its groups in order: Server Racks, Rack Servers, the four Cable Trays densities,
      Cable Tray Supports, then the room groups (Raised Floor, Room Cooling & Power, Aisle Containment, Signs & Labels).
- [ ] Names carry no size ("Compute Server", "Server Rack (Open Frame)", "Cable Tray, Straight (Full)"); the size
      selector tells the sizes apart and the descriptions give them.
- [ ] No Data Center block shows up under a vanilla tile.
- [ ] Every block has its own icon, readable at toolbar size and in tone with vanilla icons.
- [ ] Search finds blocks by "rack", "server", "UPS", "KVM" and "tray".

### Placement

- [ ] Racks of both sizes and all three kinds place flush in a row with no gaps and no flicker on shared sides.
- [ ] Every server seats in a rack slot when aimed at the back of an empty slot. Aiming at the front third of a rail
      stays red. A server turned to face the rear also seats. The 12U UPS takes two slots.
- [ ] A server in the top slot of a 24U rack sits under the roof without overlap.
- [ ] Nothing builds onto a server's front or top.
- [ ] Trays join floor to floor, hang on Hanger Rods 0.5 m above the rack top, mount on walls and stand on floors.
- [ ] Rack PDU strips seat at the bottom of the rear corner columns; a strip never sticks out of a 24U rack's top.
- [ ] Containment doors place just beyond a row end; roof panels snap onto the containment rail and door header.
- [ ] The probe's numbers match `build_report.json`.

### Behavior

- [ ] Rack doors swing outward toward the aisle to about 85 degrees without clipping a neighbor's leaves.
- [ ] Tray fans and the CRAC fans spin only while the block is working and powered; the hum stops with the grid.
- [ ] Timer, Event Controller, Status Display and Programmable behave like their vanilla counterparts.
- [ ] UPS: insert and remove a Power Cell in each bay with Use; two full cells give twice a Battery's capacity.
- [ ] KVM: a new one places stowed (Off); On slides the drawer out and folds the screen up toward the operator.
- [ ] Signs and Rack Labels are editable LCDs; the text fills the screen.
- [ ] Paint a rack and a server: painted parts follow the color, black parts stay black.

### Scripts on and off

- [ ] With scripts off: the world loads, the KVM slides and folds together, and the Programmable's Run ends in a
      normal compile error without a crash.
- [ ] With scripts on: no `Error when loading scripts for DataCenter`, and `[DataCenter]` lines appear at load.
- [ ] The KVM stays stowed behind closed doors, comes out shortly after they open, and stows fast when they close.
- [ ] The Programmable runs a script, and its SCRIPT STATUS lamp is green while On and working, amber otherwise.
- [ ] A world saved with scripts on loads with them off and the other way round; script text survives.

### Construction stages

- [ ] Weld one block of each family from nothing beside its vanilla analog. A see-through cage shows below 30 %;
      from 30 % the frame is solid; lamps, screens, labels and cables appear only when the block is complete.
- [ ] A finished block that is shot or ground slightly never shows the cage again.
- [ ] Moving parts (rack side panels and fan trays, KVM drawer, CRAC fans) show as still copies whenever the block is
      not fully built and undamaged, and the real parts return after repair.
- [ ] No visible pop at LOD switches while under construction.

### Damage and broken interiors

- [ ] Damaged blocks dent and look scratched, and keep the player's paint.
- [ ] Shoot each family until zones break off. Every break shows the game's fracture texture on a solid inside,
      never an empty box or floating parts. A 6U server's front module breaks first and the server keeps working
      until its core goes.
- [ ] Sparks, smoke and fire come from believable spots (UPS bays, tray cables) and stop with their zone.
- [ ] Screens go dark on the first damage and come back after full repair.
- [ ] Containment roof glass shatters under rifle fire and ignores a grenade, like vanilla windows.
- [ ] Grinding returns the components.

### Costs

- [ ] Each block's component list in survival matches `Source/Model/dc/recipes.py`, and welding stops at the
      functional stage until the critical items are in.

### Save and reload

- [ ] Save, quit and reload: racks, servers, door states, UPS cells and charge, timer and LCD settings persist.
- [ ] No new errors in the log after the reload.

## Reporting

Open an issue with the game version, Windows, Proton or native Linux, whether scripts were on, a screenshot and the
relevant log lines.
