# FOLLOWER NEIGHBORHOOD — project memory (read me first)

Cade's Instagram project: a persistent 3D low-poly town in Blender. Every follower = a house.
Daily reels show the town growing. THE CITY'S MEMORY IS world_state.json — NEVER edit/delete
it casually; back it up before risky operations. **As of 2026-07-09, on Windows this file (and
town.glb) live in the git repo clone (`C:\Users\cadet\followville_repo`), NOT in this iCloud
folder, by default — see "Where world_state.json + town.glb actually live now" below before
you go looking for it here.**

## Current canon (update this section each day!)
- 2026-07-15 final house #29 lot correction (Cade via Codex): founder house 29's
  structure is authored 1.3m farther back while its driveway and walk remain
  connected to the curb. The web clearance pass now measures only the actual
  structural material triangles inside each optimized multi-material house mesh;
  driveway/mailbox geometry can no longer inflate the facade boundary. #29 uses
  its open side lawn beyond the entrance: its saved bench is a proportional,
  full-depth two-person bench between the path and mailbox, and trees scale
  equally across both horizontal axes instead of flattening toward the road.
  Street renders and all 904 house/decoration cases passed with zero house,
  curb, or lot-edge violations. Blender + web model changed; day/population,
  229 buildings, seeds, and claims are unchanged.
- 2026-07-15 yard-decoration presentation correction (Cade via Codex): pieces
  now use a side-lawn planting zone instead of the front-door centerline.
  Founder doors and normal-house garage sides steer the piece to the clear side;
  corner lots steer away from their second road. Benches rotate 180 degrees to
  face the street and flags sit curbward so poles clear porch covers. Tight lots
  compress only front-to-back, preserving normal decoration height/width. Cade's
  castle bench/flag/tree were rendered and visually checked; all 904 current
  house/decoration combinations still clear both façade and curb. Web-only.
- 2026-07-15 front-yard placement + accurate web collisions (Cade via Codex):
  homeowner decorations now read each GLB home's real facing and façade, then
  fit between the building and its curb. Tight founder lots constrain the
  piece's depth instead of crossing the street; corner lots cannot offset toward a
  second road. The browser collision system now uses oriented rectangular
  footprints for all 226 homes and 16 cars, three separate school-wing boxes,
  and only the actual cylinders of 77 existing tree trunks (plus customized
  yard-tree trunks), never foliage. Runtime QA tested all four decorations on
  all 226 homes with no house/curb overlap. Web-only: Blender/state/GLB unchanged.
- 2026-07-15 admin two-home allowance (Cade via Codex):
  trusted `profiles.is_admin` accounts may own two houses while every normal
  account remains capped at one. The live admins are `cade.toohey` and
  `stellar.kehler`. The account panel shows 1/2 or 2/2 homes and lets an admin
  visit, customize, or unclaim either home independently. Supabase enforces
  the limit with a profile-row lock plus a claims trigger, and the RPCs target
  an explicit owned house ID. All 27 claims stayed unchanged. This is
  web/backend-only; Blender/state/GLB were not modified.
- 2026-07-15 Homeowner Mode (Cade via Codex): every signed-in claimed-house
  owner can now open `customize my home`, choose an exterior color, roof/accent
  color, door color, and one lightweight yard piece (flowers, tree, bench, or
  flag), preview the result, and save it. The approved palette IDs live in the
  existing `claims.customization` JSONB field; the owner-only
  `update_my_customization(bigint,jsonb)` RPC validates/normalizes every value
  and updates only the caller-owned house ID. Existing claim Realtime updates
  make saved looks visible to all visitors. Web materials are cloned per house
  before recoloring so shared Blender materials cannot recolor neighbors.
  All 27 existing claims remain unchanged and no Blender/state/GLB data moved.
- Day 13, population 226, 229 buildings (grown 2026-07-14 via Cade's
  Codex: +40 ordinary houses at planned addresses 53-92). Creekside Bend
  completed with the final two Pebble Court homes; Willow Hills began with
  20 homes on Willow Rise and 18 on Foxglove Court. Only the road sections
  required by those homes are revealed. Separate finished-street,
  house-appearance, and finished-overhead videos were rendered and reviewed;
  only the house-appearance video animates buildings. The new `newgrowth` and
  `newstreet` cameras keep future daily shots centered on the newest planned
  district/street. Nature scatter now clears automatically from revealed
  suburban roads, cul-de-sacs, and occupied planned lots. The final GLB passed
  validation, all 40 database rows matched Supabase, and the three videos were
  emailed to `zachkehler@gmail.com`.
- 2026-07-14 website multiplayer (Cade via Codex): `town.html` now uses
  Supabase Realtime Presence for online players and Broadcast for live movement.
  Visitors see lightweight player markers and name labels; signed-in followers
  can send persistent town chat with speech bubbles. Admins can review current
  signed-in players, session start/end/duration history, and chat history in
  `admin.html`. Database identity, session, and chat writes are authenticated
  RPCs with RLS and narrow public-read columns; guests cannot forge them. This
  is website/backend-only: Blender, `town.glb`, population, buildings, and all
  existing house claims are unchanged.
  Follow-up controls/UI: desktop chat opens with `T`, `/`, or Enter without
  showing the start screen; Enter sends and immediately restores walking.
  Remote markers have a forward-facing 3D smiley, and the admin page is split
  into Accounts/Claims and Multiplayer/Chat tabs with compact scrolling lists.
- 2026-07-13 suburban-house replacement (Cade via Codex): every ordinary
  `house` and `ringhouse` now draws from one optimized library of 15
  distinct suburban designs and six coordinated color palettes (90 stable
  variants). Houses include their own driveway, walk, mailbox, porch/stoop,
  garage, windows, trim, and driveway-safe landscaping. Existing building
  seeds, positions, types, population, and day are unchanged, so all claims
  remain attached to the same homes. Planned lots use audited compact scales
  where needed; oriented-box validation reports zero overlaps across all 176
  current ordinary/ring homes and all 366 reserved future addresses. Each
  variant is batched to one mesh to keep the website smooth.
  Follow-up fix: `side_garage_two` now has a full-width two-story body and
  main roof; its former offset 70% body left the third upstairs window over
  empty space and looked like half the house had failed to load.
- Day 12, population 186, 189 buildings (grown 2026-07-13 via Cade's Codex:
  +17 ordinary houses at planned addresses 36-52 in Creekside Bend, plus the
  non-population Followville Elementary School). Heron Court completed and
  Pebble Court began with only their required continuous road ribbons. The
  school is a detailed full-block campus with classroom wings, clocked glass
  entrance, bus loop and bus, crosswalk, landscaping, flag court, and fenced
  playground. Separate house-rise, school-rise, and finished overhead videos
  rendered and passed sampled-frame review; GLB validated and all 18 new DB
  records synced, with the school explicitly non-claimable.
  Final 2026-07-13 corrections: the playground now uses connected A-frame
  swings with attached chains/seats and an endpoint-aligned slide/rails/exit;
  ordinary cars have four upright tires placed at the front/rear axles and
  protruding outside the body. Both sides of an isolated car and two playground
  angles passed visual review. The full Day 12 video set was rerendered from
  this corrected world and emailed to tooheycade@gmail.com.
- Day 11, population 169, 171 buildings (grown 2026-07-12 via Cade's Codex:
  +14 ordinary houses, planned addresses 22-35 in Creekside Bend). The winding
  street extended only as far as today's houses. Growth/loading and finished
  overhead videos rendered and passed visual review; town.glb validated clean;
  all 14 new houses synced to Supabase.
  Post-render correction: cul-de-sac bulbs now wait until their connecting road
  is complete, and pond/bulb surfaces use shallow solid geometry to prevent
  depth flicker. Corrected growth and overhead videos were rerendered and reviewed.
  Placement correction on 2026-07-13: all 35 planned houses were realigned to
  face their roads, the house in the Heron Court branch was relocated, and
  road-bend joints were sealed. Permanent full-plan collision/facing/state-drift
  validation now protects all 366 addresses. Population and day were unchanged.
  Road upgrade on 2026-07-13: staged suburban streets now build as continuous
  mitered meshes instead of separate rotated boxes, eliminating turn gaps, and
  use the same width/material/center-dash rhythm as established town roads.
- Day 10, population 155, 157 buildings (grown 2026-07-11 via Cade's Codex:
  +21 ordinary houses, planned addresses 1-21 in Creekside Bend). The staged
  curving entrance road and first cul-de-sac appeared only as required by the
  new houses. Growth/loading and finished overhead videos were rendered and
  approved; town.glb validated clean; all 21 houses synced to Supabase.
- 2026-07-11 structural reserve (Cade via Codex): `neighborhood_plan.py`
  deterministically plans the next 366 ordinary houses (population 135-500)
  across six curved-road districts with 18 cul-de-sacs. Undeveloped hills,
  meadows, and ponds are visible now; planned roads and houses create no object
  until ordinary +N growth consumes their exact addresses. Existing geometry
  never moves. See `NEIGHBORHOOD_EXPANSION_PLAN.md`. The legacy pop-500 plaza
  is intentionally suppressed when this houses-only reserve completes.
- Day 9, population 134, 136 buildings (grown 2026-07-10 via Zach's Mac Claude: +64 houses,
  regular grid only -- no new custom house type or feature flag this time). LIVE on the
  website as of 2026-07-10 (deploy_website.command, commit `c2ab97e` on `main`, confirmed
  by reading world_state.json straight off followville-kappa.vercel.app). Three things
  changed in the CODE itself (permanent -- apply to every future growth day, not just
  this one):
  * **Landlocked-house bug fixed** in `find_free_lots()`: every 3x3 block's dead-center
    lot (`ix==1, iy==1` within the block) has zero road frontage on any side, but the
    lot-picker was still handing it to regular houses, stranding them with no street
    access -- Cade flagged this with screenshots ("house in the middle of the square, you
    can't get access to it from the street"). Fixed by skipping that lot in the `size==1`
    branch. One PRE-EXISTING landlocked building was deliberately left alone (the day-7
    pond, built before this fix existed) -- don't "fix" it later without checking with
    Cade first, since moving it could disturb its neighboring day-7 houses too. Also:
    never hand-place a building on a dead-center lot via `--special TYPE@gx,gy` either.
  * **Camera framing retuned** in `build_stage()` -- the default/overhead orbit distance
    and angle, the separate `--hero` close-up formula (`hdist`), and the `--cam street`
    window (now a FIXED founder-centered span instead of the whole grid width, so it
    doesn't slow down as the town keeps growing) were all tightened for a more cinematic
    look, at Zach's request ("make sure you see everything... make it look cinematic",
    "don't go absurdly slow, make sure you see cool stuff"). These are the new defaults
    going forward -- nothing else needs to change them again. If you DO retune any of
    these, compare a frame against `day_009_hero_fixed`/`day_009_overhead_condensed` on
    the same machine first, not `day_007`/`day_008` (those used the old looser numbers).
  * **Layout condensed for day 9's batch** -- by day 9 several older blocks had gone
    sparse (one house plus some trees, lots of empty grass) because `find_free_lots()`'s
    lot order used to be pure radial distance from the city center, which scatters
    rather than fills block-by-block. Zach asked for this cleaned up, but ONLY for that
    day's 64 new houses -- no founder home, no pre-day-9 house, no pond/park/ringhouse
    was allowed to move (his explicit call: "if you own that house, it doesn't change").
    Done via a standalone one-off script, `condense_day9.py` (kept in this folder for
    reference), which re-laid-out just that day's batch in block-filling spiral order
    into free lots, skipping the dead-center lot and every occupied/protected footprint.
  * **UPDATE, later the same day (2026-07-10):** block-fill is now the PERMANENT default
    lot order, not a one-off -- Zach asked for the condensed look to happen automatically
    from now on instead of needing a manual script each time. `find_free_lots()` gained a
    `fill_mode` param; the new `sorted_lots_filling()` (blocks in spiral order from the
    city center, filling each block's lots before moving to the next -- basically
    `condense_day9.py`'s logic promoted into the real pipeline) is now used by default
    for every growth day, houses/parks/apartments/pond-clusters alike. The OLD scattered
    look (`sorted_lots()`, pure per-lot radial distance) is still there and still works --
    pass `--scatter` on the CLI to opt into it for a specific run if that messier look is
    ever wanted on purpose. Verified in isolation against the live day-9 state (no
    Blender needed, pure lot-math): a simulated +40 houses landed in 6 blocks under the
    new default vs. 13 blocks under the old scatter order for the same input -- no
    collisions, no dead-center placements, custom-home blocks still respected. condense_day9.py
    itself is now mostly historical (kept for reference) since the pipeline does this
    automatically going forward.
  * Fireworks deliberately left OUT of the final day-9 videos (Zach: "you still have
    fireworks going off..."); `--celebrate` itself is unchanged and still works if a
    future day wants fireworks again.
  * Three final videos rendered and approved by Zach, each with its own `--tag` so they
    sit on the Desktop alongside earlier days' videos instead of overwriting them:
    `day_009_hero_fixed` (angled establishing shot), `day_009_street_walkin` (first-person
    walk down the founder-district street, `--cam street`), `day_009_overhead_condensed`
    (calm overhead showcase of the finished, condensed town -- rendered with `+0`, not
    `replay`, specifically so the houses-rising animation does NOT play: Zach is cutting
    this into a longer video and didn't want a "growth reveal" moment in this shot).
- **2026-07-10, later still (Cade's Windows Claude Cowork session) -- a THIRD, independent
  instance of the git-internal-file iCloud race, complementary to the `refs/remotes/origin/main`
  one Zach's session already found and fixed the same day (see Collaboration section):** this
  iCloud folder's own `.git` was completely non-functional from this session's sandboxed bash
  ("not a git repository") because its plain `HEAD` and `config` files, `refs/heads/main`, the
  `index`, and `FETCH_HEAD` had ALL been hit by the same rename-to-numbered-copy race that hits
  `world_state.json`/`CLAUDE.md`, plus a stale `index.lock` and one loose git object that read as
  corrupt. Restored `HEAD`/`config`/`refs/heads/main` and cleared the locks (Read the broken file
  with the file tool, Write it straight back -- bash's own `cat`/`git`/Python `open()` all failed
  on these specific files with `Invalid argument`, but the file tools worked fine, going through
  a different, real-materializing path). This got `git status` working again from the sandbox but
  NOT `git fetch`/`push` (a couple of objects still read as corrupt from inside that sandbox
  specifically -- looks like a limitation of how that particular session's Linux mount handles
  some of iCloud's binary placeholders, not real data loss). Actually pushed this session's fixes
  by using computer-use to run a `.bat` (via Win+R) through the clean `C:\Users\cadet\followville_repo`
  clone instead -- confirmed working end to end. Also found and restored: the plain `CLAUDE.md`,
  `TEAM_LOG.md`, and `world_state.json` filenames in this iCloud folder had themselves been renamed
  away (again) at the very start of that session, before any of the above. **Near-miss worth
  knowing about:** a first attempt to push a LOCAL, STALE copy of `CLAUDE.md`/`TEAM_LOG.md` (from
  before Zach's day-9 doc updates existed) almost overwrote everything in this Day 9 canon entry
  and the Collaboration section below -- avoided only because the copy step happened to fail
  ("system cannot find the file specified", the SAME iCloud race striking a third time, on the
  real Windows machine this time, not just the sandbox). Lesson for any future doc-repair session:
  always refresh your local copy from the repo clone (`copy /y C:\Users\cadet\followville_repo\CLAUDE.md ...`)
  immediately before editing, not just once at the start -- don't trust that a local copy made
  even a few minutes earlier is still the latest, on either side of this project.
- Day 8, population 70, 72 buildings (grown 2026-07-09 via Zach's Mac Claude: +41 houses
  around a NEW CIRCULAR PARK DISTRICT east of town + fireworks + a lighting upgrade).
  New that day, all in neighborhood_blender.py:
  * `--parkring` flag: gained houses become "ringhouse" buildings laid out on two rings
    around a "parkdistrict" building (circular park: gazebo, paths, flowers, benches,
    trees + two ring roads with dashes/lamps + connector road to the grid). These are
    OFF-GRID: they carry exact `px`/`py`/`rot` fields in world_state.json (see build_pos());
    footprint() reserves every grid lot under the district circle so nothing collides.
  * "ringhouse" asset (10 variants): cottages / two-story homes / skinny townhouses in
    bolder pastels (RING_WALLS) -- intentional variety vs the regular grid houses.
  * `--cam park`: slow low orbit inside the park (min 12s), for showcase shots.
  * `--celebrate` now centers fireworks on TODAY'S new batch when there is one
    (falls back to the founders' custom homes otherwise).
  * Lighting upgrade (all time-of-day moods): softer sun shadow edges,
    a weak shadow-free sky-colored fill sun, higher-res shadows/AO/samples in
    setup_render (all best-effort try/except). LIGHTING SAGA, final numbers (set on
    Cade's PC the same night, after the Mac-rendered videos still looked washed out):
    sun 1.0x @ 4.5 deg, fill 0.07x, sky 1.0x -- i.e. back to the approved day-7 look
    plus a subtle shaded-side lift. Don't re-boost any of these without comparing a
    frame against day_007_hero on the same machine first.
  * CORRECTION to the para above (Cade's Windows Claude, same night): Zach's Mac run
    never actually produced the reshoot -- all three videos on his Desktop were replay
    (everything rising) + bright lighting, and his --cam park path orbited at r~29.5,
    straight THROUGH the inner ring houses (r=30.5) -- that was the "camera clipping"
    Cade reported. Fixed park cam: r=20, h=8.5 (between park trees <=13.8 and the
    houses). Fireworks made daylight-visible (emission 9->30, bigger particles). The
    real final videos (hero rising+fireworks, park + overhead calm +0 showcases) were
    rendered on Cade's PC via day8_shots.bat. His day-8 state itself was great and was
    published through the git-backed flow (his Mac had run without NEIGHBORHOOD_REPO_DIR,
    so day 8 initially existed only in iCloud). Claiming-side follow-ups: parkdistrict
    set non-claimable (both sync scripts' type lists updated), and town.html claiming
    understands off-grid px/py/rot buildings now.
  * day8_grow_and_render.command = the double-clickable one-shot that ran it all
    (backup -> _refresh_text -> grow +41 --parkring -> 3 renders, logs to render_log.txt).
  * _refresh_text.py fixed: derives the project folder from the opened .blend instead of
    a hardcoded ~/Documents path that only existed on one machine.
  * Latent bug fixed: milestone additions were 2-tuples in a 3-tuple loop (would have
    crashed the day pop crossed 500).
- Day 7, population 29, 30 buildings (grown 2026-07-08 via Windows Claude: +3 houses + 1 pond).
  New pond+ducks feature: a "pond" building (SIZE 1, `build_pond`/`ASSET_VARIANTS["pond"]`)
  clusters with new houses in a shared free 2x2 patch via `--pond` (see main()'s `pond_extras`
  block); ducks are NOT saved to world_state (spawned fresh each run by `animate_ducks`,
  analogous to `animate_traffic`, using each pond building's own seed). Rendered hero shot
  (`replay --hero --render --tag hero`) + overhead/drone shot (`replay --cam overhead --render
  --tag overhead`), then deployed live. Live site initially showed the pond+3 new houses
  pancaked flat — root-caused and fixed same day (export_web.py now calls
  `obj.animation_data_clear()` before realizing instances; see the Web viewer section's
  2026-07-08 PITFALL note below for the full story), re-exported, redeployed, confirmed live.
  Sunset fireworks marked the founder era complete (day 4).
- Web viewer shipped day 4 (index.html + town.glb, see Web viewer section).
- FOUNDERS (first 10 residents, custom houses, all built):
  1 mushroom  2 casino  3 cat  4 castle  5 Eiffel home  6 hydrangea flower
  7 Burj Khalifa  8 giant toilet (next to Burj, faces east)  9 beach house  10 cottage
- Founder district = blocks around the center. Regular houses NEVER build in blocks
  containing custom houses (enforced in code).

## Daily workflow (Terminal, no Blender GUI needed)
  cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/neighborhood
  ./grow.sh +N --render              # N followers gained -> N houses + video
  ./grow.sh -N | "=TOTAL" | replay   # losses / set total / re-animate
Flags: --special TYPEhouse[@gx,gy] --followers N --hero --celebrate --parkring
       --cam overhead|street|park --tag NAME --time day|sunset|night --season X --still
       (--cam street: added 2026-07-07 — eye-level flythrough down the town's oldest
       street past the founder blocks, instead of the default overhead orbit; runs at
       least 12s so it reads as "slow". See build_stage() in neighborhood_blender.py.)
       (--scatter: added 2026-07-10 — new houses/buildings default to filling sparse
       blocks solid before starting the next one (see Day 9 canon above); pass --scatter
       to opt into the old scattered-across-many-blocks look for a specific run instead.)
Videos auto-copy to Desktop. Multi-shot days: hero shot (replay --hero --render --tag hero)
+ overhead/final (+0 --cam overhead --render --tag overhead).

## House-facing rules
- Houses auto-face their nearest road. Override: set "face": "s|e|n|w" on the building
  in world_state.json (camera looks from the SOUTH-EAST: s and e faces are visible).
- Every block's dead-center lot (the middle of its 3x3 grid) has zero road frontage and
  is never buildable -- `find_free_lots()` skips it as of 2026-07-10 (see Day 9 canon
  above for the story). Don't hand-place a building there via `--special TYPE@gx,gy`
  either -- it'll be just as landlocked as the ones this fix removed.

## Adding custom house models (Fable-level work)
Edit neighborhood_blender.py: write build_X_house() using add_box/add_ngon_cone/
add_prism_roof + mat(), register in SIZE and ASSET_VARIANTS, then
--special xhouse[@gx,gy]. Match the cute pastel style. After script changes run:
  /Applications/Blender.app/Contents/MacOS/Blender --background neighborhood.blend --python _refresh_text.py

## Cost discipline
- ONE preview still per day max (--still), then render.
- Renders take 10-15 min each: run via nohup job writing render_log.txt (ends "ALL_DONE"),
  and hand the log-watching to a HAIKU subagent. Never poll with the expensive model.
- Routine +N days need no preview at all.

## Web viewer (index.html + town.glb)
A first-person browser version of the town lives in index.html, next to world_state.json.
Real geometry, not a hand-ported copy: grow.sh now runs export_web.py (a second headless
Blender pass) after every build, which bakes the actual "WORLD" collection Blender just
built to town.glb (realizes collection-instances to real meshes via duplicates_make_real,
then exports GLB, Y-up, no animation/camera/lights). index.html loads town.glb with
Three.js's GLTFLoader — pixel-for-pixel the same model Blender rendered, no drift, no
manually-ported shapes to keep in sync, and any brand-new custom house type in
neighborhood_blender.py "just works" on the web the next time grow.sh runs, zero web-code
changes needed. world_state.json is still fetched separately, just for the day/population
HUD text. Collision colliders are computed automatically from each top-level object's
bounding box in the loaded GLB — no per-house-type radius to maintain either.

Fallback: if town.glb is missing (e.g. before the first export ever ran), index.html falls
back to an OLDER procedural JS approximation (the BUILDERS map, ~line 160-500) that
hand-rebuilds simplified house shapes from world_state.json alone, no Blender needed. This
is a safety net only — it's visually approximate and NOT kept in sync with new Blender
house types. Prefer fixing/regenerating town.glb over touching the JS builders.

Serve via a local server (`python3 -m http.server` in this folder — fetch() needs http://,
not file://) to preview locally. For the actual live site, see "Deploying the live site"
below — growing the town does NOT push those changes live by itself.
It always shows the CURRENT town only (no time-travel yet). Usernames on houses are a
planned feature, not wired up — needs a `username` field added to buildings in
world_state.json first.

## Deploying the live site (GitHub + Vercel) — READ THIS, it's the thing that got missed
Live URL: `https://followville-kappa.vercel.app`. Repo:
`https://github.com/tooheycade-design/followville`. Vercel auto-redeploys on every push
to `main` — but nothing pushes automatically on its own.

**Growing the town (`grow.sh` / `grow_windows.bat`) does NOT push to GitHub or update the
live site.** Neither script contains a single git command — they only ever touch files in
this local iCloud folder. Deploying is a separate, manual step, and it's easy to forget:
on 2026-07-07 the live site was still showing "day 5" a full day after the local town had
already grown to day 6, because nobody had pushed in between. **After growing the town,
always also check/push the live site — don't assume it updates itself.**
- **Windows:** `deploy_website.bat` (built 2026-07-07) does this in one click — copies the
  current tracked files (index.html, town.html, town.glb, world_state.json,
  neighborhood_blender.py, grow.sh, export_web.py, the .md docs, etc.) into a local git
  clone at `C:\Users\cadet\followville_repo`, commits, and pushes. Progress + a final
  `ALL_DONE`/`ALL_FAILED` land in `deploy_log.txt`. See the "Third AI" section below for
  the full setup story (installing git, cloning, one-time GitHub sign-in, etc.).
- **Mac:** no equivalent script was found in this folder as of 2026-07-07 — the repo
  already had prior commits (e.g. "Day 5: population 22, 22 buildings") before any AI
  touched git here, so it looks like Cade has just been running `git add / commit / push`
  by hand from a Mac terminal after growing. **If you're Zach's Claude reading this:**
  check with Cade whether he already has a routine for this before assuming there isn't
  one — and if there really isn't one, consider offering to build a `deploy_website.sh`
  mirroring this same idea (copy tracked files, commit, push, log ALL_DONE) so this stops
  getting missed.

## Where world_state.json + town.glb actually live now (2026-07-09)
This section supersedes most of the "combined restore + launch script" workaround described
in the iCloud race-condition gotcha further down (that workaround still applies to plain docs
like this one, which haven't moved — see below). The race itself was: `world_state.json`'s
plain filename in this iCloud folder kept getting silently renamed to a numbered conflict copy
between separate command launches, because it's a file that gets read-modified-written every
single growth day, and that's exactly the wrong kind of file to leave in an iCloud/Dropbox-style
sync path. The actual fix isn't a smarter workaround, it's removing the file from iCloud's sync
path entirely and using git instead — a `git pull` either gets you the latest committed state or
fails loudly; it never silently hands you an empty file the way iCloud's conflict-copy renaming did.

**How it works now (Windows):**
- `neighborhood_blender.py`'s `state_path()` and `export_web.py`'s town.glb output path both
  check an environment variable, `NEIGHBORHOOD_STATE_DIR`. If set, `world_state.json`/`town.glb`
  are read/written there instead of "next to the .blend" (the old default). Unset = old
  behavior, unchanged — this is fully backward compatible.
- `grow_windows.ps1` sets `NEIGHBORHOOD_STATE_DIR` to `C:\Users\cadet\followville_repo` (the git
  clone) before every Blender invocation. Before that, it does `git pull origin main` in the
  clone — if the pull fails, the whole run aborts loudly rather than growing on top of state we
  might not have the latest copy of. After Blender succeeds, it `git add`s `world_state.json` +
  `town.glb`, commits (message: `Grow: <change> (auto-committed by grow_windows.ps1 <timestamp>)`),
  and pushes to `origin/main` automatically — growing the town and publishing its new state are
  now ONE step, not two. (This also closes the *other* recurring problem, "forgot to deploy,
  live site stuck a day behind" — see the old note below.)
- Pass `--no-git` to `grow_windows.bat`/`.ps1` to fall back to the pre-2026-07-09 behavior
  (state next to the `.blend`, in this iCloud folder, no git pull/push) if this ever needs
  troubleshooting.
- `deploy_website.bat` no longer copies `world_state.json`/`town.glb` from this iCloud folder —
  doing so would silently overwrite the fresher git-committed copies with a stale iCloud copy.
  It still handles every OTHER tracked file (docs, code, the HTML). Growing (`grow_windows.bat`)
  publishes state; `deploy_website.bat` publishes everything else (docs/code changes made
  directly in this iCloud folder, outside of a growth run).
- `preview_website.ps1` (local preview server) was updated to serve `world_state.json`/`town.glb`
  from the repo clone if present there, and everything else from this iCloud folder as before —
  so local preview still shows the real current state after a `grow_windows.bat` run.
- **Mac (`grow.sh`):** the equivalent opt-in exists — set `NEIGHBORHOOD_REPO_DIR` (e.g.
  `export NEIGHBORHOOD_REPO_DIR="$HOME/Documents/GitHub/followville"`) before running `grow.sh`,
  and it mirrors the same pull/env-var/commit-push pattern. **This was written from the Windows
  session and has NOT been tested on an actual Mac** — Cade's and Zach's Mac repo clone paths
  weren't known/verifiable from here. Leave `NEIGHBORHOOD_REPO_DIR` unset and `grow.sh` behaves
  exactly as before (fully backward compatible); whoever's on a Mac should verify this once
  before relying on it, and update this note with what was actually found.
- **Docs (this file, TEAM_LOG.md, etc.) have NOT moved** — they're far less frequently
  read-modified-written than `world_state.json` was, but they DO still occasionally get hit by
  the same iCloud race (it happened again mid-edit while writing this very section, 2026-07-09 —
  see the recovery pattern in the gotcha note below). If this becomes a recurring problem for
  docs too, the same fix applies: move their canonical copy into the git repo clone as well.

**Also added 2026-07-08/09, closing the OTHER half of the pancaked-houses problem (that it shipped
silently for a full day before anyone noticed):** `export_web.py` now has an in-Blender check
right after `duplicates_make_real()` — if ANY realized object has a near-zero scale on any axis,
it raises and fails the whole Blender process, which `grow_windows.ps1`/`grow.sh` already treat as
fatal (`ALL_FAILED`). A second, independent copy of the same check lives in a standalone script,
`check_town_glb.py` (needs only `pip install pygltflib`, no Blender required), wired into a
GitHub Action (`.github/workflows/check_town_glb.yml`) that runs on every push to `main` — so
even a bad export that somehow bypassed the in-Blender check (a hand-edited file, a future
refactor that drops it, etc.) can't reach the live site without GitHub itself flagging the push
red. Verify it's working by checking the Actions tab on the GitHub repo after any push.

## Claimable homes (accounts) — built 2026-07-09, see CLAIMING_SETUP.md
Followers can sign up on the site, verify their Instagram handle (DM-code, manually
approved by Cade until Meta app review), and claim exactly ONE house. Backend:
Supabase (Postgres+Auth+Realtime) — schema in `supabase_schema.sql`, run once in the
Supabase SQL editor. One-house-per-account and one-account-per-house are enforced by
DB unique constraints via the `claim_house()` RPC (first commit wins, loser gets a
clean error, Realtime updates every open browser). `town.html` has the whole
account/claim UI; it stays 100% dormant until `SUPABASE_URL`/`SUPABASE_ANON_KEY` are
pasted in near the top of its script. **Pipeline integration (don't lose this):**
`grow_windows.ps1` (Sync-Houses function) and `grow.sh` (sync_houses.py call) now
sync new world_state.json buildings into the Supabase `houses` table after each
growth — insert-only/idempotent, needs `supabase_sync.env` (SECRET, gitignored,
NOT in the deploy whitelist) next to the scripts. Log lines: HOUSES_SYNC_OK /
HOUSES_SYNC_FAILED / HOUSES_SYNC_SKIPPED in grow_log.txt. Everything is claimable
incl. founder houses (Cade's call, 2026-07-09) except ponds/parks/plazas/schools.
Admin (verify/reject/revoke) = the "Admin" button on the LIVE homepage (visible
only to accounts with profiles.is_admin = true — currently cade.toohey and
stellar.kehler; every action is re-checked server-side inside the SQL functions,
so the page itself is safe to be public). admin.bat still works locally too
(same admin.html, service key from supabase_sync.env). See CLAIMING_SETUP.md §3.
Setup status: LIVE as of 2026-07-09. Supabase project "followville"
(ref bposhxtidoyulallvhdp, in Cade's "The Human Archive" org) created, schema run,
email-confirmation OFF, legacy anon key pasted into town.html (deployed, commit
c180164), service-role key in supabase_sync.env (local only), all 30 buildings
backfilled into `houses`. Verified end to end: anon REST reads houses (30 rows),
public_claims readable, profiles hidden from anon. Still TODO someday: enable
CAPTCHA (Auth -> Attack Protection, needs a Cloudflare Turnstile account) and the
automated Instagram DM webhook (CLAIMING_SETUP.md §4). To approve verifications:
CLAIMING_SETUP.md §3 (SQL editor, `select admin_verify('handle');`).

## Milestones (auto-built when population crosses)
500 fountain plaza | 2,000 skyscraper | 10,000 stadium

## Web viewer (Followville)
index.html = the landing/home page (logo, tagline, live day/population stats, "Walk the
town" button). town.html = the actual first-person walkable town (Three.js GLTFLoader);
town.glb = exported geometry. Landing page stats are pulled straight from world_state.json's
own `day`/`pop` fields on a ~45s poll — no calendar/date math anywhere, since day/pop should
ONLY change when the town is actually regrown via grow.sh, never on a timer. Population is
intentionally NOT derived from building count (a future apartment building could hold many
followers in one building) — always read `state.pop` directly, never `buildings.length`.
Logo image expected at logo.png next to index.html (falls back to an emoji if missing).

grow.sh auto-exports town.glb after every growth — generator and export_web.py MUST run in
the SAME blender invocation (--python a.py --python b.py). PITFALL (fixed, don't reintroduce):
the GUI City-panel Grow button saves the .blend including built objects; a separate export
launch would read that stale scene. Blend was purged + resaved clean on day 4.

PITFALL (fixed, don't reintroduce): export_web.py must jump to the animation's final frame
(scene.frame_set(scene.frame_end)) before realizing/exporting, or newly-risen houses can get
baked mid-rise ("pancaked" flat to the ground) — the daily rise animation scales buildings
from scale.z≈0.001 up to 1 over the clip, and export_apply=True bakes whatever frame is current.

PITFALL (fixed 2026-07-08, don't reintroduce — this is the REAL fix for the "pancaked houses"
bug, the frame_end jump above was necessary but not sufficient): the frame_end jump only sets
which frame the SCENE is on: it does nothing to remove the actual keyframe animation still
attached to that day's new buildings. `duplicates_make_real()` forces Blender to re-evaluate
the depsgraph, and if an object still carries a live Action with scale keyframes (which every
NEW building does — that's exactly what `animate_rise()` just gave it), that re-evaluation
reasserts the F-curve's value and silently overwrites a plain `obj.scale = (1,1,1)` Python
assignment right back to whatever the curve says. Confirmed directly in the deployed day-7
town.glb via pygltflib: the pond and all 3 new houses (this run's only animated objects) came
out with every mesh part at scale `(1, 0.001, 1)` — the exact frame-1 "not risen yet" value —
baked as orphaned top-level nodes with no parent, while every older building (which has NO
animation data in a later day's Blender session, since `animate_rise()` is only ever called
on the day a building is born) exported fine. That's why it only ever hits the NEWEST batch
and looked so mysterious — it's invisible until the next growth day adds something new.
The fix, in export_web.py's WORLD-collection loop, right before `duplicates_make_real()`:
call `obj.animation_data_clear()` on every object (in addition to, not instead of, the
existing scale-reset and frame_end jump — keep all three). Clearing animation_data removes
the Action outright, so there is no F-curve left that could ever reassert a stale value,
regardless of depsgraph evaluation order. Verified fixed by re-running export_web.py and
checking town.glb with pygltflib: 37 squashed (scale≈0.001) nodes before the fix, 0 after.

## Collaboration (Cade + Zach) — READ THIS FIRST, EVERY SESSION

**As of 2026-07-10, GitHub is the real sync mechanism between Cade and Zach, not iCloud
Drive's file sync.** This folder still lives in an iCloud Drive synced folder shared
between them, and iCloud still syncs it as before — but relying on that sync alone to
hand work between machines is exactly what caused the repeated "numbered conflict copy"
bugs documented throughout this file (world_state.json, CLAUDE.md, neighborhood_blender.py
all hit this), plus a worse one on 2026-07-09: a corrupted `.git` lock file got synced by
iCloud from one machine to the other and blocked git entirely on both sides. GitHub doesn't
have this failure mode — a `git pull` either gets you the real latest state or fails
loudly, it never silently hands you stale or half-written files.

**The routine, every session, both people (or whichever AI is helping them):**
1. **Start of session:** double-click `pull_latest.command` (Mac) / `pull_latest.bat`
   (Windows). Pulls `main` by default; pass `wip` as an argument to pull work that isn't
   deployed yet instead (e.g. `./pull_latest.command wip`).
2. **Do your work** in this folder as always — grow the town, edit code/docs, whatever.
3. **End of session**, depending on whether it's ready to go live:
   - Ready to deploy → double-click `deploy_website.command` / `deploy_website.bat`
     (pushes to `main`, Vercel redeploys automatically).
   - Not ready yet, but want the other person able to pull it and keep building →
     double-click `share_progress.command` / `share_progress.bat` (pushes to `wip`,
     does NOT touch the live site).
4. Add ONE line to TEAM_LOG.md before handing off (plain-English, not technical) — still
   the "who changed what" narrative record. Check TEAM_LOG.md at the start of a session
   too, same as always.

**2026-07-10: growing the town now auto-shares to `wip` — step 3 above became partly
automatic.** `grow.sh` (Mac) and `grow_windows.bat`/`.ps1` (Windows) each call
`share_progress.command`/`.bat` themselves right after a successful growth run, so a plain
`./grow.sh +5 --render` (or the Windows equivalent) both grows the town AND pushes it to
`wip` in one step — you don't have to remember the manual double-click just to let the
other person see today's growth. This is best-effort: if the push fails (e.g. a network
hiccup, or `origin/wip` moved since you last pulled), the growth run still succeeds and
is saved locally — you'll see `AUTO_SHARE_FAILED` in the log, and can re-run
`share_progress.command`/`.bat` by hand once fixed. **You still need to `deploy_website`
yourself when it's ready to go live** — auto-share only ever pushes to `wip`, on purpose,
so a day you're not happy with yet never accidentally reaches the live site. On Windows,
auto-share only pushes the OTHER tracked files (docs/code) — `world_state.json`/`town.glb`
are already pushed straight to `main` by the existing `NEIGHBORHOOD_STATE_DIR` mechanism a
few steps earlier in the same run, and `share_progress.bat` was fixed the same day to skip
those two files so it can't undo that push with a stale iCloud copy (see its own comments).
**Not yet verified on Cade's actual Windows PC** — built and reasoned through the same way
the rest of the Windows tooling was, but the first real `+N`/`-N` growth day after this
change should be treated as a test of the auto-share step specifically.

**2026-07-10, later the same day: share_progress/deploy_website stopped blind-copying files.**
Both scripts used to just `cp` every tracked file from this iCloud folder over the repo
clone and commit whatever resulted — no check for whether the OTHER person had changed
that same file since this machine last synced. That's exactly how Cade's profile-picture
feature got silently dropped: it only ever existed as a local, uncommitted edit to
`town.html` on his end, and a later push from Zach's side (based on an older pull) blindly
overwrote it — no conflict, no warning, it just vanished. Checked the full git history
(all commits, reflog, dangling objects) to confirm it was never captured anywhere; likely
recoverable from `.pull_backups/` on Cade's PC if he ran `pull_latest.bat` after making
that edit. Fix: `sync_lib.sh` (Mac, sourced by share_progress.command/deploy_website.command)
and `sync_push.ps1` (Windows, called by share_progress.bat/deploy_website.bat, which are now
thin wrappers around it — same reasoning as `grow_windows.bat` wrapping `grow_windows.ps1`)
now do a real 3-way comparison per tracked file against this clone's own prior HEAD (captured
before that run's fetch), same principle as `git merge`: if only you changed a file, push it;
if only upstream changed it, keep upstream's version and refresh your local copy instead of
overwriting upstream; if BOTH changed it, attempt `git merge-file` (works cleanly when the
edits don't overlap — e.g. one person's feature added at the top, another's at the bottom);
if that fails or the file is binary (`.glb`/`.png`/etc.), leave it OUT of the push entirely
and print which file(s) need a human to look at, rather than guessing. Validated the core
merge/conflict mechanism in a scratch repo before wiring it in. **Windows side
(`sync_push.ps1`) is unverified on an actual PC**, same caveat as the rest of this project's
Windows tooling — first real run is the test. Also found and fixed, while investigating:
this iCloud folder's own `.git` had a numbered-conflict-copy of `refs/remotes/origin/main`
(the same corruption bug that's hit `world_state.json`/`CLAUDE.md` all week, this time on a
git internal file) — deleted the stale duplicate.

**2026-07-10, still later the same night: the fix above had its own bug, and it fired for
real.** `PREV_COMMIT` (the 3-way merge base) was captured right after clone/before checkout
— but a fresh clone's HEAD lands on the DEFAULT branch (`main`), not necessarily the branch
being pushed to (`wip`). The first time `share_progress.command` ran against a brand new
`~/followville_repo` clone, it captured `PREV_COMMIT` from `main` (which had all of that
night's fixes) but then compared it against `wip`'s much older tip — concluded "upstream
changed, you didn't" for `grow.sh`, `deploy_website.bat`/`.command`, `.gitignore`, `CLAUDE.md`,
and `TEAM_LOG.md`, and silently overwrote all of them with old `wip`-branch content. Exactly
the class of bug this whole fix was built to prevent, just relocated. Fixed in `sync_lib.sh`'s
callers and `sync_push.ps1`: `PREV_COMMIT` now comes from `git rev-parse "$BRANCH"` (the
clone's own local ref for the branch actually being worked on), captured after fetch but
before the reset — empty (safe fallback to plain copy) on a branch this clone has never
checked out before. Restored the reverted files from `main` (which was never touched, since
the bug only affected the separate clone + this iCloud folder's copies). Also gave
`deploy_website.command` the same explicit `git checkout main` safety net
`deploy_website.bat` already had, since it never got that fix on the Mac side.

**Tag every TEAM_LOG entry with what it touched — added 2026-07-10 (Cade's Windows Claude
Cowork session).** Start each entry with `[WORLD]`, `[WEB]`, or `[BOTH]`: `[WORLD]` = changed
something Blender-authoritative (world_state.json, neighborhood_blender.py, anything that
should show up identically in both the rendered videos and town.glb); `[WEB]` = website-only
presentation (UI, controls, decorative additions made directly in index.html/town.html that
were never added to Blender, e.g. the backdrop mountains/clouds Zach's Codex session added
2026-07-09 -- purely visual on the site, don't expect to find them in a render or in
neighborhood_blender.py); `[BOTH]` = touched both. This exists because of exactly that
mountains/clouds case: a website-only change shipped with no way for the next AI to know it
wasn't also in Blender, so it looked "missing" instead of "on purpose." If you're adding new
scenery/geography that should look the same in videos and on the web, prefer building it in
Blender (WORLD collection) so export_web.py carries it over automatically -- reserve pure
`[WEB]` changes for things that could never make sense in a rendered video anyway (name tags,
claim UI, touch controls, session-aware buttons).

**Clarified by Cade, 2026-07-10: "same world" means same geometry, NOT same visual quality.**
The Blender-rendered videos are allowed -- expected -- to look noticeably better than the
website: richer materials, real lighting/shadows/AO, depth of field, post-processing, all the
things EEVEE/Cycles can afford that a real-time in-browser Three.js scene can't. What must stay
identical between the two is the WORLD ITSELF -- which buildings exist, where they are, what
shape they are (i.e. town.glb's geometry, exported straight from Blender's WORLD collection,
same as always). So: any new geography (mountains, terrain, whatever) still goes into Blender
first so it's real, shared, single-source-of-truth geometry -- but once it's in both places,
the website's Three.js materials/lighting for that same geometry are free to be simpler/faster
than what the Blender render uses, on purpose. That's not drift, that's two different renderers
doing their best with the same underlying model -- same city, different image quality. Don't
chase "make the website graphics as good as the video" -- chase "make sure the website has the
same buildings in the same places as the video."

None of these scripts need you to know or type any git commands — that's the whole point.
They all use a plain, non-iCloud-synced local clone (`~/followville_repo` on Mac,
`C:\Users\cadet\followville_repo` on Windows — the same one `deploy_website.*` already
used) as the actual git workspace, and just copy files in and out of it. If a script's log
ends `ALL_FAILED`, that's real and worth reading — don't just re-run it and hope.

**IMPORTANT — pull_latest/share_progress only ever move already-committed, already-pushed
content.** They will happily overwrite whatever's in this folder with whatever's on GitHub
(after backing up anything that differs, to `.pull_backups/`) — so if you've made local
edits you haven't shared yet, run `share_progress.command`/`.bat` BEFORE running
`pull_latest`, or you'll be pulling your own older work back on top of your newer work.
(Learned this one the hard way while building these scripts — a same-session test pull of
`wip` briefly clobbered a `main`-only merge fix that hadn't been pushed to `wip` yet. No
data was actually lost since it all still existed on GitHub's `main`, but it's a real sharp
edge worth knowing about.)

Take turns as before (don't both have neighborhood.blend open at the same time), but the
"did I actually get the other person's latest work" question is now answered by step 1
above, not by eyeballing whether iCloud's sync icon looks done.

### Third AI: "Cade Claude on Windows" (Cowork)
As of 2026-07-07, Cade also works this project from a Windows PC, via Claude in Cowork mode.
That session is a THIRD AI with access to this same folder — alongside Cade's Mac Claude and
Zach's Mac Claude. It reaches the project through the same iCloud Drive sync (folder path on
this machine: `C:\Users\cadet\iCloudDrive\neighborhood`), so the same rules apply: take turns,
check iCloud is fully synced before starting, add a TEAM_LOG.md line before handing off (sign
it "Cade (via Windows Claude)" so it's clear which AI/machine made the change).

**What's different about the Windows session — corrected 2026-07-07:** its file/bash tools
run inside a sandboxed Linux shell that only sees this mounted folder (no Blender there,
no path to launch one) — but this machine ALSO has a separate screen-control tool
(computer-use) that, once Cade grants access, can see the real Windows desktop and drive
it with actual clicks/keystrokes. **Blender 5.1 is installed on this PC.** Verified
2026-07-07: with that access granted, this session opened `neighborhood.blend` in the real
Blender GUI, used the Scripting tab to inspect the embedded generator script, and closed
back out without saving. So:
- It CAN open Blender and click around the GUI (File > Open Recent, Scripting tab, etc.) —
  useful for inspection/diagnosis. This is something the Mac Claude sessions have never
  done, since they only ever drive Blender headlessly via `grow.sh`.
- It should NOT drive the GUI City panel to run growth days. Simulated clicks are fragile —
  one stray keypress during testing briefly flagged the file as having unsaved changes with
  no visible edit. For a file where `world_state.json`/the `.blend` is the city's only
  memory, that risk isn't worth it.
- **`grow_windows.bat` + `grow_windows.ps1` now exist** (built 2026-07-07) — a proper headless
  Windows equivalent of `grow.sh`: same `+N`/`-N`/`=N`/`replay` syntax and extras, runs
  `blender.exe --background` (no GUI, nothing to click), writes progress + the final
  RESULT/STILL/VIDEO lines to `grow_log.txt` ending `ALL_DONE`/`ALL_FAILED`. Best launched via
  Win+R (typing works there) with something like
  `"C:\Users\cadet\iCloudDrive\neighborhood\grow_windows.bat" +5 --render` — typing directly
  into a visible Command Prompt/Terminal window is blocked for this session, so that's the
  practical way to pass arguments without a human at the keyboard. **Verified working
  2026-07-07** with a real `replay` run (safe — never touches `world_state.json`/the
  `.blend` by design): got `ALL_DONE`, `town.glb` refreshed, state file untouched (checked
  by hash). Still get Cade's go-ahead before the first real `+N`/`-N`/`=N` growth day from
  here. Two gotchas already hit and fixed: (1) keep both files plain ASCII — Windows
  PowerShell 5.1 misreads em-dashes/curly quotes in a BOM-less `.ps1` and can crash
  mid-string; (2) `$ErrorActionPreference = "Stop"` plus `2>&1` on the Blender call turns
  even harmless stderr output (e.g. a Python `DeprecationWarning`) into a fatal PowerShell
  error — the script now relaxes that just around the Blender invocation.
- **`preview_website.bat` + `preview_website.ps1` also exist** (built 2026-07-07) — a tiny
  PowerShell-only local HTTP server (no Python/Node dependency) for previewing
  `index.html`/`town.html` on this machine, since their `fetch()` calls don't work over
  `file://`. Auto-opens the default browser to `http://localhost:8000/`; auto-stops after
  20 minutes. Verified working: landing page and `town.html` both correctly showed live
  "day 5 / population 22" from `world_state.json`, and `town.glb` loaded over the wire
  (200 OK) — confirms the Blender-to-website pipeline is intact from Windows.
- It CAN safely do everything else: edit/read docs (README, CLAUDE.md, AI_HANDOFF.md,
  TEAM_LOG.md, WEB_VIEWER_CHANGELOG.md), tweak the web viewer (`index.html`, `town.html`),
  inspect `world_state.json` and `town.glb` (read-only unless Cade explicitly asks for a
  hand-edit — see the "never edit/delete casually" rule at the top of this file), open
  Blender read-only for diagnosis (always "Ignore"/"Don't Save" on any prompt), and general
  planning/writing tasks.
- If asked to "grow the town" or render a video, it should say so and offer either: point
  Cade to running `grow.sh` on a Mac, or offer to build the headless `.bat` wrapper above —
  rather than attempting the GUI-clicking approach for a real growth day.
- **Deploying to the live site** (see "Deploying the live site" section above for why this
  matters — growing the town alone does NOT push). **`deploy_website.bat` now exists**
  (built 2026-07-07) — a one-click push script that copies this iCloud folder's
  known-tracked files (index.html, town.html, town.glb, world_state.json,
  neighborhood_blender.py, grow.sh, export_web.py, the .md docs, etc. — NOT renders/,
  debug logs, or one-off scripts) into a local git clone at
  `C:\Users\cadet\followville_repo`, commits, and pushes to `origin/main`. Progress + a
  final `ALL_DONE`/`ALL_FAILED` go to `deploy_log.txt`. Git itself wasn't installed on
  this PC before — added via `winget install --id Git.Git -e --source winget`; the clone
  was made with `git clone https://github.com/tooheycade-design/followville
  C:\Users\cadet\followville_repo`. First real push (2026-07-07, the day 6 + street-cam
  update) needed a one-time `git config --global user.name/user.email` (now set) and one
  interactive GitHub sign-in via the browser (Git Credential Manager popped up a normal
  github.com login page for Cade to complete himself — this session never sees or handles
  the credentials). Later pushes should be silent unless that browser login expires.
  Verified working end to end: pushed day 6/pop 26 + the new street-cam feature, confirmed
  live on `followville-kappa.vercel.app` within about a minute (stats and `town.glb` both
  updated).
  - **Gotcha:** run Windows commands here as a `.bat` file (write it, then launch via
    Win+R), never as one long `cmd /c "...with nested quotes..."` string typed directly
    into Win+R — a complex one-liner with nested `"` silently mis-parses and the command
    chain just stops partway with no visible error, which looked exactly like a hung
    `git clone` the first time this was tried (it wasn't hung; the quoting broke).
  - **Bigger gotcha, hit hard on 2026-07-08 (day 7 pond growth day) — READ THIS:**
    `world_state.json`'s plain filename is NOT stable between two separate Win+R-launched
    `.bat` invocations, even seconds apart, even with no other person actively editing
    anything. The pattern: run #1 (`grow_windows.bat +3 --pond`) correctly grows and saves
    the town (day 7 confirmed in `grow_log.txt`'s RESULT line) — then run #2 (a `replay`
    call to render a shot) comes back with `"day": 0, "population": 0, "buildings": 0`,
    i.e. `load_state()` found nothing and fell back to the empty default. Checked via
    Notepad's File > Open dialog (the most authoritative "does Windows itself see this
    file" test — more reliable than File Explorer's status icons, which kept showing a
    stuck blue "syncing" bar on a file that Notepad said flatly did not exist): the plain
    `world_state.json` really was gone, and iCloud had spun up a numbered conflict copy
    (`world_state 3.json`, `world_state 4.json`, ...) holding the correct day-7 content
    instead. This happened repeatedly, not once — restoring the plain filename (Write tool,
    or a `copy` command) and then waiting even ~30-45s before the next Blender launch was
    NOT enough; iCloud renamed it away again in that gap every time. The same thing then hit
    THIS FILE (`CLAUDE.md`) mid-edit while writing up this very lesson — and it hit again on
    2026-07-08 during the pancaked-houses fix, mid-edit for the SAME `CLAUDE.md` file for the
    exact same reason (an Edit call landed on `CLAUDE 4.md` instead of the plain filename;
    recovered by reading the fully-edited conflict copy and Write-ing it straight to the
    canonical path, per the fix below — no data was lost, just an extra round-trip).
    **The fix that actually worked:** stop doing "restore the file" and "launch Blender" as
    two separate tool calls with a gap between them. Instead write ONE `.bat` that does the
    `copy /y "world_state N.json" "world_state.json"` restore AND the
    `call grow_windows.bat replay ...` (or `call deploy_website.bat`) launch back-to-back,
    then run that single combined `.bat` via one Win+R. With no round-trip back through
    Claude's tools in between, the race window closes and Blender reliably sees the correct
    file. Used this pattern for both shot renders and the deploy step on day 7 — all three
    worked first time once combined this way. For a plain doc edit (no Blender involved,
    like this file), there's no combined-script equivalent — when an Edit call reports the
    canonical path doesn't exist, just find whichever `CLAUDE N.md` conflict copy has the
    edit, finish editing THAT copy, then `Write` its full final content straight back to the
    canonical path in one shot (not another `Edit`) to close out the recovery in a single
    tool call. If this happens again: find whichever `world_state N.json` / `CLAUDE N.md`
    conflict copy has the freshest/correct content (check timestamps + open a few to
    compare), then always pair its restore with the next action in one script (for
    Blender/deploy work) or do a single `Write` of the finished content (for doc edits).
  - **Another gotcha, same day:** `grow_log.txt` (and possibly other plain-named files read
    via the Linux-sandbox bash mount) can appear STALE/frozen mid-write from that mount's
    point of view — `tail`/`wc -l` kept returning the exact same byte count across several
    checks 15-25s apart even while the underlying Blender process was still actively running
    and had in fact already finished. Bash's `ls`/`stat` metadata for this same mount was ALSO
    seen showing a day-old mtime for `town.glb` even once its actual just-written content was
    already fresh and correct. **Lesson: for this iCloud-synced folder, don't trust bash's
    view of file freshness (`ls`, `stat`, `tail`, `wc -l`) as proof that a write hasn't
    happened yet.** If a Windows-side process should have finished, verify by reading the
    file's actual CONTENT through a tool that does a real fresh read (the Read tool, or a
    Python script that opens and parses the file, e.g. `pygltflib` on `town.glb`) rather than
    concluding from a stale directory-listing/log-tail that the process is still running or
    stuck.

## Files
neighborhood.blend (scene; GUI panel: N key -> City tab) | neighborhood_blender.py (generator)
grow.sh (CLI) | world_state.json (THE CITY) | renders/ (videos) | AI_HANDOFF.md (cheap-model manual)
TEAM_LOG.md (plain-English "who changed what" between Cade & Zach, see Collaboration section)
world_state_*_backup.json = old test states, ignorable.

Windows-only tooling (permanent, keep): grow_windows.bat/.ps1, preview_website.bat/.ps1,
deploy_website.bat — see "Third AI" section above for what each does.

check_town_glb.py (permanent, keep, cross-platform — no Blender needed, just
`pip install pygltflib`): standalone sanity check for town.glb (catches pancaked/squashed-scale
exports and world_state.json/town.glb mismatches). Runs as part of export_web.py automatically,
and again independently via the `.github/workflows/check_town_glb.yml` GitHub Action on every
push to main. See "Where world_state.json + town.glb actually live now" above.

condense_day9.py (2026-07-10, now mostly historical -- kept for reference, NOT part of the
regular pipeline, not auto-run by grow.sh): the one-off layout fix that repositioned
day-9's 64 new houses into a denser block-filling order without touching any older or
founder building. Its `sorted_block_fill_order()` logic was promoted the same day into
`neighborhood_blender.py` itself as `sorted_lots_filling()`, which is now the permanent
DEFAULT lot order for every growth day going forward (see Day 9 canon's "UPDATE" bullet
above and `--scatter` in the Daily workflow flags list) -- so a manual condense pass
should no longer be needed. Still worth keeping around as a reference/fallback in case
`sorted_lots_filling()` ever needs re-deriving.

Day-9 one-off render scripts (safe to ignore/delete, same category as the other one-off
.command scripts below -- all superseded, kept only as a paper trail): render_day9_cinecheck.command,
redo_day9_fixed.command, render_day9_final.command, render_day9_street.command,
render_day9_overhead_condensed.command, plus their matching *_log.txt outputs. The
world_state.json/town.glb/videos they produced are already live/on the Desktop; nothing
needs to be re-run.

Windows-only scratch files (safe to ignore, not tracked by git, not part of the deploy
whitelist — leftover from building/debugging the above on 2026-07-07): clone_repo.bat,
cleanup_procs.bat, check_repo.bat, inspect_repo.bat, inspect_repo2.bat, git_config.bat, and
their matching .txt log outputs, plus deploy_check.txt, git_install.txt, proc_check.txt,
proc_check2.txt, grow_log.txt, grow_step1_growth.txt, grow_step2_hero.txt,
grow_step3_overhead.txt, grow_street.txt. Also from 2026-07-08 (day 7 pond growth day, see
the `world_state.json` race gotcha above): fix_and_hero.bat, fix_and_overhead.bat,
fix_and_deploy.bat (the combined restore-copy + launch scripts that fixed the race),
check_push_status.bat/.txt, restore_canonical.bat/.txt, pull_and_check.bat/.txt,
check_remote.bat/.txt, list_folder.bat, fix_reexport.bat (re-exports town.glb after the
2026-07-08 pancaked-houses fix; safe replay-mode, no world_state.json/blend changes),
install_ci_check.bat/.txt (one-off script from 2026-07-09 that copied check_town_glb.py +
check_town_glb.yml into the git repo clone and pushed them — already ran, safe to ignore/delete
once confirmed the GitHub Action shows up on the repo's Actions tab), check_town_glb.yml (the
GitHub Action source file, kept here for reference — the live copy that matters is the one
already pushed to `.github/workflows/check_town_glb.yml` inside the git repo clone),
check_town_glb_setup_note.txt (Fable-written setup note for the above, safe to ignore once read).
Nobody has deleted these per the "never delete without approval" rule at the top of this
file — ask Cade before cleaning them up.

Numbered/parenthesized conflict copies (`world_state 2.json`, `CLAUDE(1).md`, etc.) are
iCloud sync artifacts, not intentional files — see the race-condition gotcha in the Third AI
section for why they keep appearing and how to recover from them. Don't delete these either
without checking their content first (one of them may hold the only copy of the current
canonical state, as happened on day 7).
