# Data Center

Space Engineers 2 mod: data-centre server racks and rack-mount servers, with the look of real 19-inch racks and
the function of vanilla automation blocks.

## Server Racks

Build menu: Automation > Data Center > Server Racks. Each kind comes in two sizes: 24U (4 slots) and 42U (8 slots,
with an overhead cable tray and fans).

- **Open Frame:** no doors.
- **Split Front Doors:** hinged perforated leaves that swing 85° toward the aisle.
- **Front + Rear Doors:** the same leaves on the front and the back.

## Rack Servers

Build menu: Automation > Data Center > Rack Servers. Servers are 6U (one slot) unless noted.

| Server | Behaves like |
|---|---|
| Timer | vanilla Timer |
| Event Controller | vanilla Event Controller |
| KVM Console | a control panel; switch it On and the drawer and screen pop out |
| Status Display | an LCD |
| UPS (12U, two slots) | a battery with two Power Cell bays, front and back; swap cells by aiming at a bay and pressing Use |
| Programmable | On/Off blade with a programmable block; its program runs when the game has scripts enabled, and then its SCRIPT STATUS lamp is green while On (amber otherwise) |
| Compute, Storage, Network Switch, Blanking Panel | decorative |

## Cable Trays

Build menu: Automation > Data Center > Cable Trays: Empty / Low / Moderate / Full, and Cable Tray Supports.
Overhead wire-basket cable trays for the rack rows: 38 blocks. The basket is fixed silver; the data cables follow the block paint.

- **Densities** (one tile per density): Empty (basket only), Low (2 data bundles), Moderate (adds yellow fibre and grey power), Full (adds a second data layer and black power).
- **Shapes** (each density): Straight (Short 0.5 m, Long 1.5 m), Horizontal Turn, Turn Up, Turn Down, Tee, Cross, Rack Drop and Reducer (Low, Moderate and Full only).
- **Reducer:** steps the density down one level (Full to Moderate, Moderate to Low, Low to Empty). They chain. Joining two densities without a reducer also works: the shared lanes match and the extra lanes end.
- **Drop:** a 1 m piece that carries two waterfalls of cable down into a full rack's front cable managers. Over a half rack (24U), put a **Long Drop Chute** under the Drop.
- **Hanger Rods** (0.25, 1.0, 2.0 m): hang a run from the ceiling. They snap only onto the tray's rod plates. Hang height is 0.5 m above the rack top (the tray's lowest plane), centred 0.125 m in front of the rack centre.
- **Joints:** pieces join floor to floor only. Both trays must have their floors facing the same way; an upside-down tray does not join. Every piece also works backwards, and a Horizontal Turn gives both hands.
- **Mounting:** ceiling-hung on rods, wall-mounted on the strut end plates, or floor-standing. Nothing mounts on the open top of the basket.
- **Damage:** the trays break into zones and show a damaged model. The Hanger Rods and the Chute do not break.
- **Costs** scale with the length of run (one unit per 0.5 m; see NOTES.md, Plan 2 Task 9). Each tray block is 5 PCU.

## Room Pieces

Build menu: Automation > Data Center: **Raised Floor**, **Room Cooling & Power**, **Aisle Containment** and **Signs &
Labels** (19 blocks). Build a hall in this order:

- **Lay the floor first.** Raised-floor tiles (Solid or Perforated, 0.5 or 1.0 m, 0.25 m high) carry everything else:
  racks, the CRAC, the PDU cabinet and the doors stand on the tiles' top, at or across tile seams. Put the perforated
  tiles where the cold air comes up (a cold aisle, or the walkway in front of a hot aisle's racks).
- **Rows:** racks, the in-row **CRAC** cooler and the **PDU Cabinet** share one footprint (1.0 m wide, 1.25 m deep,
  2.5 m tall), so a row stays on a 1.0 m pitch. Face two rows' fronts across a cold aisle, or their backs across a hot
  one.
- **Aisle widths:** 1.0, 1.5 m or 2.0 m (4, 6 or 8 cells between the rows). Doors and roofs come in each width.
- **Doors:** the sliding containment door goes in the 0.25 m slice just **beyond the row end**, its frame bolted to the
  two end racks' sides; its leaves park in front of those sides. It is a real door (it blocks you while closed).
  A row between a contained cold and a contained hot aisle carries both aisles' doors at its ends; their pockets share
  its 1.25 m depth, so pair a 1.5 m with a 1.0 m aisle (or two 1.0 m aisles), not two 1.5 m or any 2.0 m.
- **Roof:** roof panels (1.0 m along the row x the aisle width) snap onto the containment rail along the top of
  full-rack rows (42U racks, CRAC, PDU cabinet) and onto the door header. Half racks (24U) are not contained.
- **The CRAC draws power** (25, priority as a vanilla gyroscope): its fans spin and its RUN lamp lights only while it is
  On and powered; the fans take 2 s to spin up and coast down over 4 s when it stops. It does not cool anything (the
  game has no cooling); its rear **O2 / COOLANT SERVICE** ports are decorative (blanked, nothing connects to them).
- **Power distribution:** the PDU Cabinet is decorative (vanilla has no power-junction block); a cable tray Drop over
  it lands in its top brush plates. Zero-U **Rack PDU** strips go in a rack's rear corner columns, **Feed A** in the
  right-hand column and **Feed B** in the left (seen from the rear), 42U or 24U length; aim at the plinth top in the
  rear corner.
- **Signs are editable LCDs** (Signs & Labels): type the text in the terminal. The **Aisle Sign** (1.0 m) mounts on a
  wall or on a door header; the double-faced **Hanging Aisle Sign** hangs from a 1.0 m Hanger Rod under the ceiling;
  the **Rack Label** sits on a rack's top edge. Show hot or cold with the frame's paint: red for a hot aisle, blue for
  a cold one.
- **Rack IDs:** racks and the CRAC carry neutral placards ("RACK", "RACK ID", "CRAC" beside a blank tag); give each
  rack its ID with a Rack Label. On a 42U it mounts on the front pad (between a Drop's waterfalls) or the back pad; on a
  24U only on the **back pad**. In a **contained** aisle the roof hides the rack tops' aisle edge: put the labels on
  the edge facing the **open aisle**, and sign the contained aisle on its door headers.
- **Damage:** every room piece breaks into zones and shows a damaged model. PCU: floor, roof and PDUs 5, signs 35,
  CRAC 30, doors 150.
- **Costs** scale like the rest of the mod; signs cost one vanilla LCD per screen face, and the CRAC and the PDU
  cabinet cost a 42U open rack's frame plus their own parts (NOTES.md, Plan 3 summary).

## Building and damage

The blocks build and break the way the game's own blocks do in 4.0. While you weld one, a see-through cage shows its
outline until it is 30 % built; after that the mounts and frame are solid metal and the rest fills in, with lamps,
screens and cables added last. A block that has been shot or ground back does not show the cage again once it is
finished. Damaged blocks use the game's scratched-metal look and spark, smoke and burn as they lose health. Moving and
add-on parts (rack side panels and fan trays, the KVM drawer, the CRAC fans) are shown as still, built-in copies in
their closed position whenever the block is not fully built and undamaged; the real parts come back when you repair
it. This has been checked with tests
and renders only; it has not been run in game yet (INGAME-CHECKLIST.md, section 14).

## Enabling scripts (optional)

The mod ships C# scripts (`Scripts/`). **They do nothing unless the game is started with `-loadScripts`**, so the mod
works fully without them; scripts only add polish. SE2 does not run mod scripts by default (it is an opt-in switch
while Keen's mod scripting is not official), and without the switch the game silently ignores the folder. When Keen
enables mod scripting officially, the scripts will work without the switch.

### How to launch with scripts

- **Steam (Windows, or Linux through Proton):** Library > Space Engineers 2 > Properties > Launch Options, add
  `-loadScripts`. Remove it to go back.
- **Native Linux through Pulsar (this workspace):** `tools/scripts/se2mod.py play DataCenter --native`. `play` adds
  `-loadScripts` by itself when the mod has a `Scripts/` folder (the Steam/Proton form, `se2mod.py play DataCenter`,
  does the same).

### Scripts ON versus OFF

| | Scripts OFF (default) | Scripts ON (`-loadScripts`) |
|---|---|---|
| KVM Console motion | the data's simultaneous slide-and-fold, linear | the drawer slides out, a short beat, then the screen folds up with a soft settle; off: fold first, then slide home. Toggling mid-motion reverses smoothly |
| KVM and rack doors | it pops out through closed leaves | behind closed doors it stays stowed; it pops about 0.15 s after the doors are fully open, and fast-stows when they start to close. Only a door on the KVM's own face side counts |
| KVM after a load or a stream-in | the vanilla load bug (it can show the wrong state) | shows the right state at once; a KVM finished by welding animates out |
| KVM in the top slot of a 42U rack | data-only motion | the same data-only motion on purpose (the containment rail sits just above the lid), so that one slot is less polished |
| KVM Use to toggle (aim at the drawer, press F) | works | works (through the sequencer) |
| Programmable: On/Off, terminal listing | works | works |
| Programmable: Script editor, Check, Run | the editor and your script text are kept, but **Run, Check and Debug end in a normal compile error** (nothing crashes) | works as a programmable block |
| Programmable: SCRIPT STATUS lamp and LCD bar | amber | green while On and working, amber otherwise (the two rear PSU lamps stay amber) |

Saves are identical in both modes: the Programmable always carries its scripting component in the data, so a world
saved with scripts loads without them and the reverse, and your script text survives the round trip. Everything the
KVM script changes is client-only visual state and is never saved.

### Multiplayer

Every player and the server should use the same setting. A mixed setup is expected to work, because the differences are
visual (each client shows its own KVM motion for the same server state), but it is lightly tested.

### Troubleshooting

- **Nothing changed:** the game was started without `-loadScripts`. Check the launch options, and that the log has
  `[DataCenter]` lines at world load (for example `[DataCenter] script the KVM: 3 edit(s): ...`).
- **`Error when loading scripts for DataCenter` in the game log:** the scripts did not compile (usually after a game
  update changed an API). The mod then behaves exactly like scripts OFF. Report it with the log lines.
- **A `[DataCenter]` line saying something "keeps the data-only motion" or "could not ...":** a reflection target or
  a definition was not found; that feature fell back to its data-only behaviour, once, and the game is unaffected.
- **Probe:** with a world loaded, `tools/scripts/se2game.py exec -f Source/Model/review/probe_scripts.csx` prints one
  line per check (`ok` or what is wrong): the switch, both assemblies, the reflection targets, the Programmable and the
  KVM state. It reads the plugin's connection settings itself; never paste or share those settings.

## Developer notes: scripts

- **CompileCheck:** `bash Tests/CompileCheck/run.sh all` compiles both script assemblies the way the game does (under
  wine, with the game's whitelist and generators). Expect `OK: 0 errors` twice. `run.sh probe
  Source/Model/review/probe_scripts.csx` compiles the in-game probe.
- **CoreTests:** `cd Tests/CoreTests && dotnet run -c Release` runs the game-free cores (the KVM motion, the
  surgery and scripting rules); `-- --dump <dir>` also writes the trajectories the Python geometry tests and the
  previews use, stamped with a digest of the core sources.
- **Tests:** `python3 -m pytest -q Tests` (`-m "not build"` for quick loops).
- **Probe mode:** `probe_scripts.csx` has an opt-in fault pass (`kvmFaultPass = true`).
- **Dependency risks:** the scripts reflect into engine internals; the list and where each one is used is in
  `docs/reference/our-game-dependencies.md` (workspace root), and NOTES.md ("Plan 4").
- **After every game update:** re-run CompileCheck and CoreTests, run the probe in game, and re-check the reflection
  targets. After the "Hostile Encounters" update (new damage system; see
  `docs/research/se2-upcoming-update-hostile-encounters.md`) also re-run the in-game checklist section 12 and the
  fracture checks, and expect Pulsar and the Linux compat layer to need an update first.

## Costs

Costs scale with block size the way vanilla's do (see NOTES.md, Task 10).

## More

- Previews: generated locally under `Source/Model/preview/` (not tracked in git); marketing images go in `docs/media/`
- Developer notes: NOTES.md
- In-game test list: INGAME-CHECKLIST.md

## Licence

Copyright (C) 2026 Rioku Labs. Rioku Labs' own models, textures, definitions, scripts and tools in this repo are free software under the GNU General Public License v3.0 (see `LICENSE`).

Space Engineers 2, its Mod SDK and the vanilla assets this mod reuses are (c) Keen Software House and are not covered by this licence. This is an unofficial mod, not affiliated with Keen Software House.
