# Codex handoff -- current through Day 12

Updated 2026-07-14 for Cade's next Claude/Codex session.

## Open the authoritative project

The live project is `C:\Users\cadet\followville_repo`, not the old binary/state
copies in `C:\Users\cadet\iCloudDrive\neighborhood`. Start by reading
`AGENTS.md`, `CLAUDE.md`, and the newest entries in `TEAM_LOG.md` from the repo.
Run `git pull origin main` in the repo before changing anything.

Do not replace the repo's `world_state.json`, `town.glb`, or
`neighborhood.blend` with similarly named iCloud copies. The iCloud folder has
historical/conflict copies and is only a shared handoff/bootstrap location now.

## Current canon

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
- Day 12, population/followers 186, 189 buildings.
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

The corrected Day 12 house-rise, school-rise, and town-overhead MP4s are in:

`C:\Users\cadet\Documents\Codex\2026-07-11\th\outputs`

They were visually reviewed and emailed to `tooheycade@gmail.com` with subject
`Followville Day 12 -- corrected videos`.

## Git checkpoints

- `408ddab` -- final connected playground equipment and correct wheel placement.
- `8984740` -- logged the corrected Day 12 video delivery.

Read newer commits if present; `origin/main` remains authoritative.
