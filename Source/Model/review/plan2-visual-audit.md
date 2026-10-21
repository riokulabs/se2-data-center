# Plan 2 Task 10: visual-pass audit (cable trays)

The audit set is in `mods/DataCenter/Source/Model/preview/p2-task-10/`. It was rendered with `DC_PREVIEW=plan2-t10 DC_PREVIEW_SUB=before|after`, using `dc/preview_trays.py render_audit`.

**Before** was rendered from a `git archive` of HEAD, with only the new shot catalogue copied in. **After** is the working tree. Both sets use the same 66 cameras:

- every shape at Full and Low at 1 m and 3 m, plus the Chute and the 1.0 m rods;
- free run ends and a joint;
- the lay at 1 m;
- the Tee breakout;
- the Drop split, climb and guide;
- the landing collar and the Chute foot;
- the long mixed run over a populated rack row: 3/4, aisle eye level, worm's eye, and the v2 mockup 05b camera;
- the junction network;
- the vanilla line-ups.

Sheets:

- `contact_before.jpg` and `contact_after.jpg`;
- `refs_before.jpg` and `refs_after.jpg` (photos 01, 02 and 04 beside our run shots and the vanilla line-ups);
- `pairs/` (one before/after pair per shot, plus `contact_pairs.jpg` and `icons_before_after.png`).

Format: finding → evidence shot → fix → after shot. Findings are ranked by impact.

| # | Sev | Finding | Evidence | Fix | After |
|---|---|---|---|---|---|
| 1 | H | **Hollow run ends (V-T7b).** At any free port the LOD0 bundles show open 3-faced strand sweeps: hollow star profiles you can see through, with the floor-wire ends ("silver pins") behind them. Every shape and density shows this, and it is the first thing seen at a run end, an unused Tee branch or a Cross arm. | `end_free_Full_square`, `end_free_Low_square`, all `shape_*_1m` | LOD0 **cable-end caps** (`tray_kit._cable_cap`). Each bundle's own section closes it: the hexagon of the hidden centre cable plus the six 3-faced strand lobes. That is 16 triangles, the minimum that closes the section. The caps are flat-shaded and sit **1.5 mm inside** the port plane, so nothing touches the port plane. At a joint the two caps face away from each other 3 mm apart, wholly inside the continuous closed strand skin: they are invisible and cannot z-fight (`joint_Full`). Measured on the built mesh (`build_dc.port_caps`; `test_port_caps`: 7 faces per bundle end per port). **Not on 4 Full pieces** (StraightS, StraightL, Cross, TurnDown): with caps their LOD0 breaks the plan budgets (`test_cap_skip_is_budget_bound`). See the report's concern 1. | `end_free_Low_square`, `shape_*_Low_*`, `shape_Tee_Full_1m` |
| 2 | M | **Tee M0 branch smear (M-3).** The branch M0 peels on the left turning group's outer arc (r 0.36), so it stays inside its parent for about 0.19 m past the 3 cm collar and reads as one fused yellow mass. Peel_r ≤ 0.2 is **impossible**: the branch would cross the left group's L1+ arc (centre distance 0.226 m against radii 0.275 and 0.2), and the contract pins peel_r = FIL_Y − J_Y. | `tee_collar_Moderate`, `tee_branch_Moderate` | A **breakout tie** (`tray_bends._breakout_tie`): one Darker band 0.12 m past the collar, round M0, the peeling branch and (at Full) the F1- nested on M0, in one plane. Cable installers tie a fan-out where it leaves the run, so the fused stretch now reads as a held breakout (collar, then tie, then fan-out). LOD0 only. It is the one strap off the 0.25 m rhythm, by purpose (`test_tee_breakout_tie`). | `tee_collar_Moderate`, `tee_collar_Full` |
| 3 | M | **Landing collars and the Chute foot float** over the brush-plate frames: 2 mm (collar 1 mm inset plus the rack's 1 mm `ENTRY_DROP`). The Chute's top plate and the Drop's collar also left a 2 mm hairline. | `land_collar_low`, `land_chute_foot_low` | `tray_plan.ENTRY_SEAT = 0`: the collar and the Chute's foot and top plates sit **on** their ENTRY planes. An ENTRY plane is an interface like a port (the waterfall already ends on it). The rack keeps its own 1 mm, so there is still no coplanar face, and the gap is now 1 mm. Collar on the Chute: flush contact. The bristle tips were raised so their ragged ends stay over the plane (render within bounds). Tests: `test_within_cells` (collars and ladder plates may touch only their ENTRY plane), `test_chute_ladders`, `test_landing_collars_seat`. | `land_collar_low`, `land_chute_foot_low`, `land_collar_34` |
| 4 | L | **Drop Full LOD0 6452 tris (P2-25).** Its two split collars on L1+ lie wholly inside the dressed top layer and the nest of bundles round L1+. They cannot be seen from above or from the aisle, and only a 3 cm dark band shows through the floor wires from below. | `drop_full_split`, `drop_full_climb` | The plan keeps the collars (the SPLIT rule). At Full it marks them `hidden` and the kit skips them: −400 tris. With its caps (+288) the Drop Full is now **6340** (`test_drop_full_hidden_collars`). The Low and Moderate collars, which are visible, stay. The brush collars stay (they are visible at every landing). | `drop_full_split`, `drop_low_split` |
| 5 | L | **Lay-twist shading bands** every 0.25 m at 1 m. Each 30° lay segment's quads are sheared and twisted, and the face-area weighted normals put a diagonal highlight in each segment. | `lay_1m` | **Not fixed.** The cheap fixes are out of reach: more segments break the StraightS budget, and a per-loop radial custom normal needs a change in the shared `tools/se2model` export (`objects.finalize_mesh` re-weights every normal). | `lay_1m` (unchanged) |
| 6 | L | **Rod-hanger icons faint at 64 px (T9).** The 5 mm rods over 1–2 m become sub-pixel lines, and the 2-rod pair is already at its widest separation in this view. Vanilla TrussFrame_Long has the same limit. | `pairs/icons_before_after.png` | The rod icons render at exposure +0.6 instead of the core −0.55 (`preview_task10.ROD_ICON_EXPOSURE`), so the pair reads brighter on the dark tile. Partial: thin is thin. | `pairs/icons_before_after.png` |
| 7 | L | The strap buckles read as bright squares in the previews. | `tee_collar_*`, `drop_full_climb` | No change: they use the TRAY_HW (BrushedMetal) preview stand-in, and Keen's metal will be darker → in-game check. | — |
| 8 | L | Side-on at range (`run_mockup05b`, `run_aisle_eye`) the cable load reads thinner than photo 04's overflowing baskets, because the 0.10 m walls hide most of it. | `refs_before.jpg` | No change: this is by design (the SE-ify rule, and the lane contract's bundle top at 0.087 m). The waterfalls carry the read, as in photo 01. | — |

## Checked and passing (no finding)

- **Bundle readability:** at 1 m and 3 m the colours stay distinct (blue data, yellow fibre, grey and black power), and the 7-cable texture is visible at LOD0.
- **Strap rhythm:** continuous across every joint (`joint_Full`, `run_junctions_Full`).
- **Wire chunkiness:** judged by eye against the vanilla line-up (`vanilla_compare`); unchanged since the T4 audit.
- **Yellow restraint:** yellow is only the M0 fibre lane, the strut end caps and the density tags (judged by eye; not measured against WallInsertPipes).
- **Seams at joints:** none. The caps never show at a joint.
- **Waterfall:** the arc over the moulded guide and the plumb fall match photo 01 (`drop_full_guide`, `run_aisle_eye`).
- **Rod forest:** density against photo 04 is plausible at one pair per trapeze (`run_row_34`).
- **Crossover saddle:** reads as purposeful (`shape_Cross_*`).
- **Reducer boots:** read as sealed ends (`shape_Reducer_*`).
- **Anti-goal #1:** no bundle ends in mid-air in any shot. Free ends exist only where a player leaves a port open, and they now read as cut cable on the capped pieces.

## Side effects (deliberate)

The caps lift two pieces over Keen's next LOD0 row:

- StraightS Moderate: 1400 → 1560;
- StraightL Low: 2088 → 2152.

Both now get the 4-LOD chain (a mid LOD), which removes the P2-22 LOD1 pop for them. `CHAINS` was re-pinned.
