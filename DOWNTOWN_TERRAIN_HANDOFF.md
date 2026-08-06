# Followville Downtown + Terrain Handoff for Cade

Date: 2026-07-17

## Cade integration result

Status: semantically integrated onto current Day 16 on
`codex/downtown-terrain-merge`, rebuilt from the authoritative iCloud Blend,
validated, and prepared for production review. The supplied Day 15 `town.glb`
was deliberately not used.

Current canon after integration is Day 16 / population 272 / 275 buildings,
with ordinary addresses 1-128 built. `world_state.json` remained byte-for-byte
unchanged, and no Supabase, claim, ownership, or customization operation was
performed. The complete GLB and all six streamed chunks were regenerated from
the merged source, and the manifest now carries the shared walk-surface data.

The filename supplied by Zach was the only matching ZIP in the iCloud folder,
but its measured SHA-256 was
`C10B8D816C27BB567D891F64D269D32BFBC38EFBC6CC5A209F16A46F69D080D7`,
not the separately provided `84c64f...` value. Cade explicitly authorized
continuing. The archive was treated only as an untrusted source transplant;
its files were reviewed and its obsolete Day 15 binary was excluded.

Browser integration preserves district streaming, the full fallback, Avatar
System v1, multiplayer, maps, camera, mobile controls, and jumping. Public
graphics use the actual rebuilt Blender geometry in balanced mode; the costly
browser-only facade overlays, procedural material shaders, and dynamic shadows
are available only through `?graphics=ultra`. The local preview CSP was fixed
to allow Draco WebAssembly decoding locally.

## 2026-07-18 production follow-up

The integrated Day 16 geometry received one focused correction before the
next growth run: ground-floor storefront glass and the decorative tower podium
glass were moved inward so their exterior faces sit flush with their facades.
The complete GLB, streamed base, affected original-town chunk, and manifest
were regenerated in replay mode from the authoritative iCloud Blend. The web
side now unloads detailed districts beyond 112m after loading at 70m, measures
claim labels from real roof bounds, supports near-vertical camera pitch without
ground obstruction, and keeps persistent chat in a top-left walking feed.
`world_state.json`, Day 16 / 272 / 275, addresses, claims, owners, and Supabase
were unchanged.

Historical package status (superseded): Zach's source package originated as an
unpublished Day 15 design branch. It has since been integrated, rebuilt against
Day 16, and published through the normal repository workflow. Do not deploy the
package's old binary or use its branch as current state.

Original package base: `fa73b14` (`Simplify town pause menu`)

Original package branch: `codex/downtown-terrain-concept`

Latest authoritative main observed during handoff: `5515226`
(`Keep little avatars and correct player controls`), Day 16 / population 272 /
275 buildings. That newer main includes district streaming and Avatar System v1.

## Canon preserved

- Day 15
- Population 259
- Buildings 262
- All addresses, ownership, claims, and Supabase records unchanged
- `world_state.json` byte-for-byte unchanged
- All 366 deterministic future houses and 538 planned road segments preserved

## What changed

- Rebuilt the downtown public realm with a wider thirteen-metre lot grid,
  continuous sidewalks, curbs, crossings, ramps, paving, plazas, street trees,
  lamps, benches, transit furniture, and more deliberate building spacing.
- Added one continuous browser-walkable terrain system with a protected flat
  downtown datum and grade-limited transitions into rolling suburban hills.
- Rebuilt winding suburban road ribbons, shoulders, intersections, colliders,
  house foundation pads, and terrain alignment.
- Rebuilt the Kaleidoscope access road so both edges follow terrain and remain
  visible above grass while preserving the authored climb and feature loop.
- Improved downtown massing, lighting, materials, storefront transparency,
  modeled interiors, doors, canopies, and wall-embedded side windows.
- Added adaptive rendering/performance tuning and offline local-preview QA routes.

## Merge guidance for Cade's AI

1. Start from `5515226` or newer. Preserve Day 16, all Avatar System v1 files,
   third-person controls, `avatar-system.js`, Avatar Studio UI, profile saving,
   multiplayer avatar rendering, and all district-streaming/LOD work.
2. Review/overlay the supplied source files. Resolve `town.html`,
   `export_web.py`, and `check_town_glb.py` semantically because Cade's district
   pipeline may also edit those files.
3. The geometry source is primarily `neighborhood_blender.py`,
   `downtown_visuals.py`, `downtown_visual_plan.py`, and `world_layout.py`.
4. Run `python3 check_downtown_visuals.py` before rebuilding.
5. Rebuild in replay mode after the semantic merge; do not run real growth.
6. Run `check_town_glb.py`, website tests, and browser QA before publishing.
7. The supplied `town.glb` is a Day 15 visual-review artifact only. Do **not**
   replace the current Day 16 `town.glb`, `town_manifest.json`, or district
   chunks with it. Regenerate the complete fallback and every affected chunk
   from the merged Day 16 source instead of binary-merging GLBs.

## Files supplied

Modified tracked files:

- `neighborhood_blender.py`
- `town.html`
- `export_web.py`
- `check_town_glb.py`
- `town.glb`

New implementation and QA files:

- `downtown_visuals.py`
- `downtown_visual_plan.py`
- `world_layout.py`
- `check_downtown_visuals.py`
- `local_preview_server.py`
- `DEEP_QUALITY_REVIEW.md`
- `QUALITY_PASSES.md`
- `DOWNTOWN_TERRAIN_HANDOFF.md`

## Validation completed

- Replay Blender rebuild: Day 15 / population 259 / 262 buildings.
- `check_town_glb.py`: passed; no squashed nodes and state consistent.
- `check_downtown_visuals.py`: passed; 366 future houses and 538 future roads.
- `git diff --check`: passed.
- `git diff --exit-code -- world_state.json`: passed (unchanged).
- Chrome local QA: terrain, road surface, curb, hill clearance, storybook
  walkability/hitboxes, statue, and all 259 home mappings passed.
- Close façade Chrome audit: 53 FPS, no browser warnings or errors.
- Visual inspection completed from school, feature-road, suburban-junction,
  storefront-front, townhouse-side, foundation, perimeter, and walk views.

## Important

Nothing in this handoff has been pushed or deployed. The live site is unchanged.
The ZIP is a source transplant package, not a branch that should overwrite
current main wholesale.
