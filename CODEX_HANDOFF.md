# Codex handoff -- current through Day 14

Updated 2026-07-15 for Cade's next Claude/Codex session.

## Open the authoritative project

The live project is `C:\Users\cadet\followville_repo`, not the old binary/state
copies in `C:\Users\cadet\iCloudDrive\neighborhood`. Start by reading
`AGENTS.md`, `CLAUDE.md`, and the newest entries in `TEAM_LOG.md` from the repo.
Run `git pull origin main` in the repo before changing anything.

Do not replace the repo's `world_state.json`, `town.glb`, or
`neighborhood.blend` with similarly named iCloud copies. The iCloud folder has
historical/conflict copies and is only a shared handoff/bootstrap location now.

## Current canon

- The homepage is an organized destination dashboard: desktop places compact
  Walk/Claim cards beside a large isometric town preview, while mobile keeps
  all three destinations above the fold. That preview redraws from
  `world_state.json` whenever the existing live stats refresh; do not replace
  it with a stale screenshot or separate map file. Its `Explore the map` card
  opens `town.html#map`. `vercel.json` redirects bare `/` to `/index.html`,
  deliberately sends `no-store` on both routes, and `index.html` reloads when
  restored from browser back/forward memory. Preserve all three safeguards so
  deployments do not intermittently show the prior homepage. Homepage styling
  should stay restrained and editorial: a sharp paper map, ruled text links,
  unboxed stats, and almost no glass blur or pill UI. Avoid returning to generic
  rounded icon cards. The same live,
  lightweight isometric 3D map opens from the town start screen, the in-game
  `town map` button, or `M`; it supports rotate, pan, zoom, and fit-to-town.
  When opened through the homepage's `town.html#map` deep-link, closing it,
  pressing Escape, or clicking its backdrop returns to the redesigned homepage
  instead of exposing the older in-town start screen. Visiting a selected map
  result still enters the town and disables that return-home behavior.
  It searches house IDs, claimed handles, streets/districts, newest homes,
  landmarks, and signed-in owned homes, and its Visit action teleports to the
  location. Instanced map geometry must remain derived from the current
  `world_state.json`; planned road lines use only built houses, so future empty
  roads remain hidden, while the already-built Founder Park rings and connector
  are reconstructed from their existing homes. `public_claims` supplies live
  owner names. Do not add a separate map JSON/database table, manual
  coordinates, or a second copy of the full town GLB.
- Day 14 is complete: population/followers 244, 247 buildings, and 18 new
  ordinary homes at plan IDs 93-110. IDs 93-95 completed Foxglove Court;
  IDs 96-110 began Overlook Circle. Its road is revealed only as far as those
  homes and its future turnaround remains hidden. The 18 new claimable rows
  were inserted into Supabase.
- The landing page and in-town loading/start screen use
  `assets/town-loop.mp4`, a 12-second Day 14 sidewalk view of a current
  Overlook Circle house with two staggered passing cars. Its poster is
  `assets/town-loop-poster.jpg`. The source comes from render-only camera mode
  `--cam housefront`; it does not mutate the blend, GLB, state, or claims.
  Reduced-motion/data-saver visitors receive the poster, and the intro video
  pauses during walking and on hidden tabs.
- `--cam newgrowthoverhead` is the preferred tight top-down daily rise shot.
  `--cam football` builds the temporary England v Argentina fan vignette used
  on Day 14. That set must remain render-only: do not export or save it into the
  permanent blend/GLB. The final saved `neighborhood.blend` was rebuilt without
  the set, and the validated `town.glb` contains no fan-scene object names.
- When `grow_windows.ps1` is run from the authoritative repo, it now skips the
  old iCloud-to-`wip` auto-share hook. The hook switched the working clone to
  stale `wip` after the Day 14 `main` push; the state/model push itself was
  unaffected. Keep repo-based daily work on `main`.
- Homeowner yard decorations are temporarily disabled. `town.html` does not
  render flowers/trees/benches/flags and does not show their chooser. Keep
  `YARD_DECORATIONS_ENABLED = false` until Cade approves a redesign. Existing
  stored `customization.yard` values remain normalized and preserved so this
  pause does not destroy homeowner data; exterior/roof/door colors still work.
- Founder house #29's structure is now authored 1.3m farther back, with its
  driveway and walk extended to remain connected to the curb. Yard clearance
  reads the selected structural material triangles inside the merged GLB mesh,
  so curb-anchored driveway/mailbox parts no longer make the house look deeper
  than it is. The saved bench is a full-depth two-person bench fitted on the
  open side lawn between entry path and mailbox; custom trees keep equal X/Z
  scale instead of becoming flat. Blender and GLB changed; world state, Day 13,
  population 226, 229 buildings, seeds, and claims did not.
- Admin accounts now have a database-enforced two-home allowance; normal
  accounts still have one. The live handles are `cade.toohey` and
  `stellar.kehler`. `town.html` lists both homes and targets visit, customize,
  and unclaim actions by house ID. Existing claims were not reassigned.
- Web yard decorations now occupy the real front-yard strip: `town.html` reads
  the GLB root's actual facing, measures the complete exported structural
  silhouette (including roofs, doors, garages, glass, and trim) and curb setback,
  then uses a side-lawn planting zone rather than the doorway centerline.
  Standard homes use their door material and founder homes use their door meshes
  to choose the side opposite the entrance; corner lots still prioritize the
  side away from the second road.
  Benches face the street, flags sit curbward to clear porch covers, and tight
  lots compress only front-to-back rather than shrinking the whole decoration.
- Web collisions are shape-aware. All 226 homes and 16 cars have oriented box
  footprints, the school has three independent wing boxes, and each tree blocks
  only at its measured trunk (77 existing GLB trunks plus homeowner yard trees),
  not at the canopy. The collision system itself remains browser-side.
- Day 13 is complete: population/followers 226, 229 buildings, with 40 new
  ordinary houses at suburban plan IDs 53-92. The batch finished Creekside
  Bend (2 Pebble Court homes) and started Willow Hills (20 Willow Rise and 18
  Foxglove Court homes). Supabase has all 229 rows and the 40 Day 13 IDs match.
- Homeowner Mode is live in the code/database as of 2026-07-15: every claimed
  owner can preview and save an exterior, roof/accent, and door color plus one
  yard piece. Saved palette IDs use the existing `claims.customization` field
  and flow to all open visitors over the current claim Realtime subscription.
  The owner-only RPC validates every option and cannot target another claim.
  All 27 pre-existing claims remain attached and unchanged; Blender/state/GLB
  were not modified.
- `--cam newgrowth` frames the newest day's largest district for rise videos;
  `--cam newstreet` follows the newest day's busiest curved street. The street
  path keys every road sample, uses local tangent aiming, and avoids roof/house
  clipping on bends.
- Procedural nature now clears from active suburban road ribbons, cul-de-sac
  bulbs, and occupied planned lots, preventing trees or rocks from remaining
  in newly developed roads. Future unrevealed areas keep their terrain/nature.
- Website multiplayer is implemented: Supabase Realtime Presence tracks online
  visitors, Broadcast carries movement, and the town renders lightweight remote
  markers/name labels. Signed-in users can send persistent chat; guests can read
  it. Admins have online-player, session-duration, and chat-history logs.
- Desktop chat opens with `T`, `/`, or Enter while keeping the town visible;
  Enter sends and restores pointer-lock walking. Remote markers use a 3D smiley
  to show facing direction. Admin data is split into two tabs with bounded,
  scrollable sections rather than one long page.
- Multiplayer database writes go only through authenticated, identity-derived
  RPCs. RLS and column grants expose only safe public identity/chat fields.
  Guests cannot create sessions, identities, or messages. Blender state and
  existing claims are not modified by multiplayer.
- Day 12 finished at population/followers 186 and 189 buildings.
- All 176 ordinary and park-ring homes now use a deterministic optimized
  library of 15 suburban designs and six coordinated palettes. Existing seeds,
  positions, claims, day, and population are unchanged. Each lot includes a
  clear driveway, walk, mailbox, porch/stoop, garage, and safe landscaping.
- Planned-house compact scales are preserved by `nb_rest_scale`; the oriented
  collision audit passes all current homes and all 366 reserved addresses.
- The `side_garage_two` partial-body bug is fixed: all three upstairs windows
  now sit on a complete full-width two-story facade and roof.
- Day 12 added 17 ordinary Creekside Bend houses at plan IDs 36-52 and one
  non-population, non-claimable Followville Elementary School.
- The hidden 366-house suburban reserve remains deterministic and staged;
  roads appear only as their associated houses appear.
- The school has classroom wings, glass entrance, bus loop/bus, landscaping,
  clock, flag court, and a finished fenced playground.
- Final playground correction: connected A-frame swing supports, chains and
  seats; slide chute, rails, and ground exit share exact endpoints.
- Final car correction: four upright tires per car at the front/rear axles,
  with opposite inward rotations on the two sides so every tire protrudes
  outside the body. Both car sides were rendered in isolation and checked.
- `neighborhood.blend` and `town.glb` were regenerated and validated.
- Supabase contains all 189 world records; the school is non-claimable.
- The live Vercel model was hash-checked against the local corrected GLB.

## Latest delivery

The Day 14 rise-overhead, completed-town overhead, football scene, and combined
Reel MP4s are in:

`C:\Users\cadet\Documents\Codex\2026-07-11\th\outputs`

They were visually reviewed and copied to Cade's Desktop. Only
`day_014_houses_appearing_overhead_0001-0244.mp4` contains house-rise animation;
`day_014_reel_cut.mp4` joins rise, football scene, then static town overhead.
All four were emailed to `tooheycade@gmail.com` in two messages with subjects
`Followville Day 14 videos -- 244 followers (1 of 2)` and `(2 of 2)`.

## Git checkpoints

- `df0c971` -- Day 14 population 244 state and permanent GLB.
- `44e2449` -- top-down growth camera and temporary supporter-scene generator.
- The final handoff commit after `df0c971` includes the saved Day 14 blend,
  final GLB rebuild, documentation, and Windows growth guard.
- `408ddab` -- final connected playground equipment and correct wheel placement.
- `8984740` -- logged the corrected Day 12 video delivery.

Read newer commits if present; `origin/main` remains authoritative.
