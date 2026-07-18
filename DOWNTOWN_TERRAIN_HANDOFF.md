# Followville Downtown + Terrain Handoff for Cade

Date: 2026-07-17

Status: completed local Day 15 design branch; not committed, pushed, or published.

Base commit: `fa73b14` (`Simplify town pause menu`)

Local branch: `codex/downtown-terrain-concept`

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
