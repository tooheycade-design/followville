# Followville deep quality review

Local experiment only. No canon, identity, claim, address, population, or production data changes.

## Geometry correction pass — July 17

- Removed the browser-generated duplicate curb/crosswalk layer. Downtown now
  renders only the authored GLB public realm, eliminating curb depth fighting.
- Subdivided every revealed suburban road to at most two-metre spans and made
  both ribbon edges sample the continuous terrain independently. Exhaustive QA
  covered 571 spans; minimum midpoint asphalt clearance is 0.188 m.
- Raised hillside pad caps four centimetres into every house foundation rather
  than ending on the same plane. All 115 planned homes retain at least 0.080 m
  terrain clearance and exactly 0.040 m pad/foundation overlap.
- Rebuilt townhouse doors as flush framed glazing, added the missing sidelight,
  aligned storefront glass and mullions to one façade plane, and removed the
  block-like projecting sign.
- Chrome inspections passed from storefront front/left/right, steep road,
  hillside-foundation, and downtown-street viewpoints. Browser console had no
  warnings or errors; the dense downtown street stabilized at 51 FPS at 1.58
  render scale during the final check.

## Screenshot regression pass — July 17

- Root cause: the terrain-conforming road helper replaced authored elevation
  with regional terrain elevation even when its inputs were local coordinates
  inside the Kaleidoscope Crest asset. The later parent transform applied a
  second spatial offset, producing the long skyline beam and malformed pink
  access road shown in Zach's 10:20 screenshots.
- The road helper now has an explicit `terrain_conform` mode. Only world-space
  suburban roads and paths enable it; the feature access road preserves its
  authored 0–2.74 m local grade.
- The townhouse storefront opening is now filled to the lintel and both side
  piers, with dynamically sized glazing and mullions rather than fixed-width
  panes that could leave black gaps.
- Prevention exists in two independent places: Blender aborts every web export
  if feature-road vertices leave their authored vertical range, and
  `check_town_glb.py` repeats the check against the finished binary.
- Wide Chrome views matching the failure areas passed for Kaleidoscope Crest,
  the downtown perimeter skyline, and the oblique storefront façade.

## Root-cause findings from Zach's screenshots

1. The salmon block in the road was a redundant second parked-car system. Its batched body exported, but its supporting silhouette read poorly at street level. The original project already had better cars. The entire redundant system was removed.
2. First-floor glass was layered directly over a solid wall. Transparency could only tint the wall, never show a room. Downtown homes now use a real ground-floor shell with an open front, side/rear structure, floor, ceiling, transparent glazing, counter, shelves, display objects, lighting, hardware, and framing.
3. Transparency had been applied to nearly every material containing `window` or `glass`. That caused sorting and overdraw across the whole city. Only water, storefront, tower-podium, and transit-shelter materials remain blended/transmissive.
4. Lighting was overfilled: strong sun, hemisphere light, fill light, and exposure compressed the scene toward white. Exposure and ambient/fill energy were reduced while directional sunlight was preserved for shape and contrast.

## Ten-role review

### Environment art director

- Preserve blockiness as the art language, but require every silhouette to identify its purpose immediately.
- Rejected the duplicate box-car silhouette and retained the project's established vehicle assets.

### Storefront architect

- A transparent façade needs a room behind it, structural piers around it, believable ceiling/floor depth, and a clear entry bay.
- Added those elements rather than treating glass as a material-only problem.

### Materials artist

- Upper-story windows work better as reflective tinted panels at this scale.
- True transmission is reserved for first-floor glazing where the player can inspect modeled contents.

### Lighting artist

- Reduced ambient fill and exposure instead of simply darkening albedo colors.
- Preserved a directional key light and ACES highlight rolloff for stronger form and less washout.

### Technical art director

- Removed low-value transparency and shadow casting before reducing geometry quality.
- Kept the procedural reflection environment because it has no network download and materially improves premium glass.

### Performance engineer

- Added adaptive internal render scale from 1.00–1.70 based on sustained measured FPS.
- Excluded glass, windows, lamps, signs, paving details, and broad ground surfaces from the shadow-casting pass while preserving major architecture/tree shadows.
- Chrome storefront audit settled at 60 FPS at the full 1.70 scale after shader compilation.
- Replaced twelve hash/noise evaluations per shaded fragment with a two-wave analytic grain, preserving visible material breakup while cutting the dominant full-screen shader cost.
- Tightened the player-focused shadow region from 250 m to 172 m, reduced its map to 1536², and removed sub-0.82 m objects from the shadow pass.

### Gameplay engineer

- Walking surfaces, curb steps, road grades, and home colliders remain independent of visual glass/interior changes.
- Storefront contents remain behind the existing building collision boundary.
- Corrected the Blender-Y to Three-Z spawn calculation so the player starts on the road center rather than six meters into grass.

### Urban designer

- Streets retain crosswalks, curbs, transit, trees, and street furniture, but duplicated vehicle clutter was removed.
- Props must occupy a plausible curb/furnishing zone and leave the pedestrian clear zone readable.

### Customer-experience lead

- A player approaching a first floor now sees depth and a reason to look inside.
- High-quality rendering adapts silently instead of requiring players to understand graphics settings.

### CEO / product director

- The quality target is not maximum object count. It is consistent intent, readable purpose, responsive movement, and details that survive close inspection.
- Future passes should prioritize authored destinations and interiors over indiscriminate citywide transparency or prop duplication.

## Acceptance targets

- No malformed duplicate road objects.
- First-floor glazing visibly reveals modeled interior depth.
- No global transparency rule for ordinary windows or vehicle glass.
- No washed-out daylight exposure.
- Adaptive renderer records both `data-render-fps` and `data-render-scale`.
- All protected city-state and walking invariants continue to pass.

## Final measured results

- Dense downtown `#walk` route: 58 FPS at 1.64 render scale, 3,659 render calls, 374,318 submitted triangles.
- Close storefront audit: 60 FPS at the full 1.70 render scale, 871 render calls, 218,108 submitted triangles.
- GLB transparency reduced to exactly four intentional materials: water, storefront, tower podium, and transit shelter.
- GLB audit found zero removed duplicate `city_parked_*` or parking-bay nodes.
- 259/259 home visuals mapped; all terrain, road, curb, storybook, statue, and hill-clearance browser audits passed.

## Terrain intrusion and façade attachment correction

- Replaced the circular-only downtown terrain cutout with a protected rectangular
  urban datum, covering every Day 15 grid corner and the full elementary-school
  campus. A nine-percent grade cap blends the platform into the original hills
  without invalidating any of the 538 deterministic future road segments.
- Rebuilt the Kaleidoscope access road as a full-width, edge-sampled terrain
  ribbon. Both asphalt edges now remain above the meadow while the authored
  climb and player surface stay aligned.
- Rebuilt suburban junctions with shared terrain-following cover meshes and
  reduced road/shoulder slab thickness to remove triangular gaps and chunky ends.
- Reduced storefront canopy projection, closed the door/transom gaps, aligned
  first-floor glass, and rebuilt side windows with masonry-embedded panes and
  four actual frame rails.
- Verified the school, feature road, suburban junction, storefront front, and
  townhouse side elevations in Chrome. All local browser datasets passed at
  53 FPS in the final close façade view, with no console warnings or errors.
