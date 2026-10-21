# Changelog

All notable changes to Data Center are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Block names no longer carry sizes: the build menu's size selector already tells a kind's sizes apart. The racks
  read "Server Rack (Open Frame)", "Server Rack (Split Front Doors)" and "Server Rack (Front + Rear Doors)" at 24U and
  42U; the servers drop "6U" ("Compute Server", "KVM Console", ...) and "UPS 12U" is "UPS"; "Rack PDU (Feed A)" /
  "(Feed B)", "Raised Floor (Solid)" / "(Perforated)", "Containment Door", "Containment Roof", "Cable Tray, Hanger
  Rods", and both straight trays are "Cable Tray, Straight (<load>)". Descriptions keep the sizes. Block IDs are
  unchanged, so saves keep working.

### Fixed

- The clamps on the racks' containment rail no longer flicker against the rail, and the dark block under each clamp
  now reads as the clamp's standoff bracket.
- The yellow Feed A band on the rack PDU strips shows in full instead of flickering behind the face plate; the
  outlet LEDs no longer flicker either.
- The 24U racks' roof rails no longer flicker against the side panels.
- A broken PDU cabinet or in-row cooler no longer opens onto an empty dark box: like the vanilla blocks, a broken
  section shows a solid inside with torn wiring and boards, plus the parts you would recognise there (the cabinet's
  busbars and breaker rows, the cooler's fans and cooling coil).
- A broken rack or PDU cabinet plinth half shows the other half's solid inside instead of a hollow.

## [0.9.0] - 2026-10-20

First Workshop release, built for Space Engineers 2 4.0.0.3151.

### Added

- 6 server racks: 42U (8 slots) and 24U (4 slots), each as Open Frame, Split Front Doors or Front + Rear Doors.
- 10 rack servers: Timer, Event Controller, KVM Console, Status Display, UPS (12U, two Power Cell bays) and
  Programmable work like their vanilla blocks; Compute, Storage, Network Switch and Blanking Panel are decorative.
- 38 cable-tray blocks: 7 shapes in 4 cable densities, Drops and Reducers, a Long Drop Chute and 3 Hanger Rods.
- 19 room pieces: raised floor tiles, an in-row cooler (CRAC), a PDU cabinet, rack PDU strips, aisle containment
  doors and roof panels for 1.0, 1.5 and 2.0 m aisles, and editable aisle signs and rack labels.
- Building and damage like the game's own 4.0 blocks. While a block is welded, a construction cage shows until it is
  30 % built; then the mounts and frame are built first and lamps, screens, labels and cables are added last. A
  finished block that is damaged or ground back does not show the cage again.
- Damage zones for every block except the Hanger Rods and the Chute. Every block, those four included, has a damaged
  model with the game's scratched-metal look, and the blocks spark, smoke and burn as they lose health.
- While a block is not fully built, or is damaged, its moving and add-on parts (rack side panels and fan trays, the
  KVM drawer, the CRAC fans) are shown as still copies in their closed position. The real parts come back when the
  block is repaired.
- All six racks, the Open Frame ones included, are in the terminal with On/Off. The 42U racks' fans stop when the rack
  is Off.
- Optional scripts (start the game with `-loadScripts`): a sequenced KVM drawer motion, the KVM waiting for the rack
  doors, the right KVM state after a world load, and a working Programmable server with a green status lamp.
