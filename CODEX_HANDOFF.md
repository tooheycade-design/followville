# Codex handoff -- current through Day 13

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

The Day 13 finished-street, house-appearance, and finished-overhead MP4s are in:

`C:\Users\cadet\Documents\Codex\2026-07-11\th\outputs`

They were visually reviewed and emailed to `zachkehler@gmail.com` with subject
`Followville Day 13 videos -- 226 followers`. Only the house-appearance MP4
contains building-rise animation.

## Git checkpoints

- Day 13 state/model/log commit: read the newest `origin/main` commit after
  this handoff entry; it includes population 226 and the final corrected GLB.
- `408ddab` -- final connected playground equipment and correct wheel placement.
- `8984740` -- logged the corrected Day 12 video delivery.

Read newer commits if present; `origin/main` remains authoritative.
