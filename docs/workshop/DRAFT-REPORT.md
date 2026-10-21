# Workshop publish files: draft report (2026-10-20)

Nothing was uploaded. Only the dry run (`tools/se2publish/se2publish.sh publish DataCenter`) was run.

## Files

| File | Notes |
|---|---|
| `docs/workshop/publish.toml` | title "Data Center", tags `Block`, summary blank, first visibility Unlisted |
| `docs/workshop/description.bbcode` | 7126 bytes counting newlines as CRLF (7030 with LF); limit 8000, warning at 7500. Validator: no errors |
| `docs/workshop/thumb.jpg` | 1280x720 JPEG, 266,915 bytes. From `resources/showcase/img/datacenter-cold-aisle-black-racks.jpg` (scaled from 1920x1080, no crop), with the R4 flask mark (`png/r4-mark-1024.png`, 64 px, 90 % opacity) bottom right. No text, no Keen logos. Encoded with `se2publish.sh thumb` |
| `CHANGELOG.md` | Keep a Changelog, section `[1.0.0] - 2026-10-20`; change note 1101 bytes |

Block counts come from `Source/Model/dc/catalog.py` (CATALOGUE = 73): racks 6, servers 10, trays 38 (28 shapes x
densities, 3 Drops, 3 Reducers, 1 Chute, 3 Hanger Rods), room 19 (floor 4, CRAC 1, PDU cabinet 1, rack PDU strips 4,
doors 3, roofs 3, signs 3).

Script extras were checked against `Scripts/` (the KVM sequencer, door interlock, spawn policy, ProgrammableLedInjector,
ProgrammableCheck) and the README "Scripts ON versus OFF" table. There is no other server automation in the scripts.

## Dry run

`READY FOR UPLOAD: yes` at commit 748dfeba. Manifest: 6611 files, 177,453,002 bytes (Assets, Content, .vrgproj,
35 Scripts files from HEAD, thumb.jpg). Warnings: only that the plan5 worktrees (`DataCenter-dmg`, `-dmg-t10`,
`-t11`, `-t12a`) share the project GUID (never publish from them; don't load them while testing the Workshop copy).
The dry run does not compile the scripts: run `bash Tests/CompileCheck/run.sh all` before a real upload.

## Images to host

The description links these placeholder URLs. Make each from the named source, about 1260 px wide (the description
shows images at up to 630 px), JPEG under about 500 KB, served over HTTPS:

| URL | Source in `resources/showcase/img/` |
|---|---|
| `https://rioku.dev/media/data-center/cold-aisle-v1.jpg` | `datacenter-cold-aisle-black-racks.jpg` |
| `https://rioku.dev/media/data-center/hall-overhead-v1.jpg` | `datacenter-hall-overhead.jpg` |
| `https://rioku.dev/media/data-center/rack-42u-front-v1.jpg` | `rack-42u-front-loaded.jpg` |
| `https://rioku.dev/media/data-center/kvm-console-v1.jpg` | `kvm-console-open.jpg` |

## Open questions

1. **Licence.** The repo has no LICENSE file. The description says "licence TBD" and must be fixed before going public.
2. **Image hosting.** rioku.dev/media/data-center/ does not exist yet; the four images above need uploading (or the URLs
   changing). The showcase images are offline renders, not in-game screenshots; consider saying so or replacing them.
3. **Version.** The `.vrgproj` Version is null; the CHANGELOG uses 1.0.0. The website still says "in testing", the
   in-game checklist is unticked and in-game tests so far were on 2.4.0.95, not 4.0.0.3151. 0.x may be more honest.
4. **Script extras.** Listed from the code and README only; none verified in game on 4.0.0.3151 (checklist §12, §14).
5. **Known issues** are the accepted limits from NOTES and the checklist. Re-checked after the plan5-damage merge: the
   Hanger Rods and the Chute now have damaged models but still no zones; the description and CHANGELOG say so.
6. **Safe to remove from a world** and **multiplayer** status are not known; the description says only that multiplayer
   has had little testing.
7. **GitHub link** `https://github.com/riokulabs/se2-data-center` is assumed public by release time.
