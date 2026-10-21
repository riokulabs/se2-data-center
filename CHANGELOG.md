# Changelog

All notable changes to Data Center are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-10-20

First Workshop release, built for Space Engineers 2 4.0.0.3155. Find it in the build menu under
Automation > Data Center.

### Added

- 6 server racks (Open Frame, Split Front Doors, Front + Rear Doors; 42U and 24U).
- 10 rack servers. Timer, Event Controller, KVM Console, Status Display, UPS and Programmable work like their vanilla
  blocks; Compute, Storage, Network Switch and Blanking Panel are decorative.
- 38 cable trays in 4 cable densities, with Drops, Reducers, a Long Drop Chute and Hanger Rods.
- 19 room pieces: raised floor, an in-row cooler (CRAC), a PDU cabinet, rack PDU strips, aisle containment doors and
  roofs, aisle signs and rack labels.
- Building and damage like the game's own blocks: a construction cage until 30 %, damaged models, sparks, smoke and
  fire. A broken section shows a solid inside with torn wiring and the big parts you would expect there, never an
  empty box.
- Optional scripts (start the game with `-loadScripts`): smoother KVM drawer motion, the KVM waits for the rack
  doors, and a working Programmable server.

### Changed

- Block names no longer carry sizes ("Server Rack (Open Frame)", "Compute Server", "UPS"); pick the size with the
  build menu's size selector. Block IDs are unchanged, so test worlds keep working.

### Fixed

- Flicker on the rack-top rail clips, the 24U roof rails, the Feed A band and the outlet lights of the rack PDU
  strips.
- A broken rack or PDU cabinet plinth no longer shows a hollow.

### For modders

- Open source under the GNU GPL v3.0: https://github.com/riokulabs/se2-data-center. Pull requests welcome (one-time
  contributor agreement and signed-off commits; see CONTRIBUTING.md).
- New offline test gates for z-fighting and broken interiors; CI runs ruff and the offline tests.
