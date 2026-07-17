# Codex handoff -- current through Day 15

Updated 2026-07-17 for Cade's next Claude/Codex session.

## Open the authoritative project

The executable project is `C:\Users\cadet\followville_repo`: code, canonical
`world_state.json`, complete/streamed web assets, and current documentation come
from Git. Start by reading `AGENTS.md`, `CLAUDE.md`, and the newest entries in
`TEAM_LOG.md` there, then compare local `main` with `origin/main`.

The shared authoritative Blender scene is
`C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend`; the repo Blend is
a synchronized safety copy. Growth uses the generator/exporter from Git and
that iCloud scene in one guarded Blender session. Never execute a numbered
iCloud conflict copy, use iCloud-only state, or run the retired `--no-git`
workflow.

## Current canon

- A Day 15 maintenance pass hardens the shared Blender workflow before any new
  growth: production launchers require clean/current Git, match the repo and
  iCloud Blend mirrors, and execute only the repository generator. A generator
  beside the iCloud Blend is ignored because iCloud may rename it. During the
  maintenance repair, iCloud immediately renamed the restored exact mirror to
  `neighborhood_blender 19.py`; it was preserved as history, and routine growth
  no longer depends on any plain-name iCloud generator.
  Direct GUI growth rejects a stale embedded generator. The current refresh
  tool backs up the Blend and embeds the repo source with its hash/revision.
  No population, building, geometry, state, or generated asset changes belong
  to this maintenance.

- The seed 73 Supabase metadata repair is live. The row now matches canonical
  state (`house`, `-3,-3`, Day 9, claimable) and is visible through the public
  API. Only house row 73 changed; the exact before/after snapshot retained all
  30 claims across 29 accounts with identical owners and customizations.

- The website now streams deterministic Blender districts while keeping the
  complete town as a safety fallback. `town_manifest.json` hashes a compressed
  shared base and five `town_chunks/*.glb` district assets; the browser loads
  2,800,996 bytes of detailed geometry at startup instead of the 7,916,952-byte
  monolith, uses lightweight silhouettes for distant homes, and awaits the
  destination district before map or owned-home teleports. Any manifest or
  initial-chunk failure automatically loads `town.glb`. Future growth must
  commit `world_state.json`, `town.glb`, `town_manifest.json`, and
  `town_chunks/` together (the Windows and Mac scripts now do this). The
  standalone validator checks every hash plus exact one-to-one coverage of all
  262 canonical buildings. Eight Playwright flows include streaming, remote
  teleport, full fallback, and iPhone touch/map recovery. This infrastructure
  did not alter day, population, buildings, addresses, claims, or Blender
  visuals.

- Day 15 is population 259 with 262 total buildings. It added 15 claimable
  homes: ten `storybookhouse` seeds 248-257 on Wanderlight Loop in the new
  Kaleidoscope Crest feature district, plus five ordinary seeds 258-262 at
  Overlook Circle plan IDs 111-115 in Willow Hills. The feature hill, garden,
  road, lamps, and flowers are permanent Blender/GLB content and appear only
  once feature homes exist. The access road now joins the old grid as matching
  asphalt, widens through a muted transition, then becomes pink; its dashes
  conform to the ramp. Website walking mirrors the raised hill/ramp surface
  for local and remote players and is guarded by
  `data-storybook-walkable="pass"`. All 15 database rows are claimable.
  The approved Day 15 delivery is three standalone videos, never one combined
  edit: `--cam wholeoverhead` for the full-town/all-15 rise;
  `--cam newgrowth --focus-type storybookhouse` for the close ten-home feature
  rise; and `--cam storybookstreet --focus-type finished` for the completed
  street-level tour with every home present from frame one. Keep the 10m near
  plane on all aerial cameras: it fixed the prior moving-shot road/pond
  flashing caused by depth-precision loss. All three were visually reviewed
  and emailed as separate MP4 attachments to Cade and Zach.
- Kaleidoscope Crest received a post-delivery finish pass without changing any
  building record or claim. `storybookhouse` collisions are now derived only
  from `NB_story_wall*` material vertices at player height, excluding the
  merged lawn/path/fence/flower/mailbox geometry. The access-ramp dashes are
  shallow surface meshes sampled from both ends of the 3D road centerline.
  All ten crooked lamps are single continuous shared-ring tubes with attached
  globes and banner brackets. A polished Cat in the Hat public-art statue
  replaces the center tree: continuous curved limbs/tail/fingers, embedded
  face and bow layers, one six-band shared-ring hat, an interlocking pedestal,
  and an accurate 2.18m base collider. It remains part of the conditional
  Kaleidoscope street asset. Preserve the Playwright requirements for
  `data-storybook-hitboxes="pass"` and `data-kaleidoscope-statue="pass"`.
- Website backdrop mountains now move outward independently when town growth
  approaches them. The old fixed 282-310m ring intersected Day 14 Overlook
  Circle Houses #230-247; `addTownAtmosphere()` now gives every current building
  at least 18m clearance from each hill's conservative footprint and exposes a
  Playwright-checked runtime audit. This is web scenery only—do not move the
  houses or edit Blender terrain to solve it.
- The public website now has stable roleplay-ready place/activity routes.
  `Today in Followville` is computed from the latest day in
  `world_state.json`; `/today` opens that day's homes in the live map with a
  current district/street summary and visual highlight. Every home can be
  shared at `/house/:id` from its selection card. These routes reuse building
  seeds, world data, and `public_claims`; future interiors/jobs/events should
  attach to those identities instead of creating parallel coordinates or a
  second place table. Vercel rewrites both clean routes to `town.html`, and its
  root `<base>` is required for assets under `/house/:id`. Browser regressions
  live in `tests/` and run in CI; use `pnpm test:e2e` after navigation changes.
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
  The homepage Walk link is `town.html#walk`; this explicitly bypasses the
  legacy in-town start screen and starts in the rendered neighborhood. Desktop
  canvas clicks capture mouse-look, and mobile retains its touch controls.
  Desktop Escape while walking opens a real pause overlay without changing the
  camera position. `resume` restores that exact location, while
  `leave town` explicitly returns to `index.html`. Escape inside map/chat still
  closes that overlay rather than leaving town. Signed-in homeowners have
  visible `manage my home(s) / unclaim` entry points on the town/start screen
  and pause menu; each selected home still uses the existing confirmation step.
  When opened through the homepage's `town.html#map` deep-link, closing it,
  pressing Escape, or clicking its backdrop returns to the redesigned homepage
  instead of exposing the older in-town start screen. Visiting a selected map
  result still enters the town and disables that return-home behavior.
  Its normal sidebar is an eight-row street directory (seven named streets plus
  `Original town`), not a 259-house list. Street rows focus their part of the
  existing 3D scene; clicking a rendered 3D house teleports immediately. Search
  accepts `@owner`, house ID, and street/district, ranks exact and partial owner
  matches well, and keeps individual Visit/Share results. Newest and claimed
  filters group by street; landmarks and signed-in homes remain individual.
  Instanced map geometry must remain derived from the current
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

Day 15's approved delivery is three separate reviewed MP4s: whole-town/all-15
rise, Kaleidoscope ten-home rise, and finished storybook-street tour. Do not
replace them with the older combined Day 14 reel pattern. The newest production
code delivery is district streaming plus the avatar camera guard and the CI
timeout follow-up; it did not change town content.

## Git checkpoints

- `7446a16` -- production district streaming and streamed/full validation.
- `40421eb` -- nearby multiplayer avatars no longer clip the camera.
- `fbdef0e` -- CI allowance for the eight streamed Three.js regressions.

Read newer commits if present; `origin/main` remains authoritative.
