# Team log — Followville

Plain-English log of who added/changed what, in order. Not a technical changelog
(see WEB_VIEWER_CHANGELOG.md for that) — just enough so Cade and Zach (and whichever
AI is helping each of them) can see what the other did on their turn.

## How to use this
- Whoever finishes a turn (Cade or Zach) adds ONE line before handing off, in this format:
  `YYYY-MM-DD — Name — [TAG] what changed (one line)`
- **Start every entry with a tag — added 2026-07-10:** `[WORLD]` (changed Blender-authoritative
  stuff: world_state.json, neighborhood_blender.py, anything that should look the same in the
  rendered videos and on the website), `[WEB]` (website-only presentation -- UI, controls,
  decorative additions made straight in index.html/town.html that were never added to Blender),
  or `[BOTH]`. This exists because a `[WEB]`-only change (backdrop mountains/clouds, added
  2026-07-09) shipped with no way for the next AI to know it wasn't also in Blender -- see
  CLAUDE.md's Collaboration section for the full reasoning.
- If an AI made the change, say so, e.g. "via his Claude" or "via Cade's Claude" —
  that's the whole "tracking" mechanism, no git needed.
- Newest entries at the top.
- Take turns — don't both have neighborhood.blend open / Google Drive syncing changes
  from both sides at the same time. Check Drive's synced before you start your turn.

## Log

2026-07-19 - Zach (via Mac Codex) - [WORLD] Completed Day 18 from 301 to 321 followers with one guarded +20 growth at Twin Oaks addresses 158-177, finishing Acorn Court and opening Lantern Court; regenerated and pushed exact Day 18 full/six-district assets, inserted all 20 claimable rows, built reusable cinematic and fast-drone replay cameras plus a temporary state-free Godzilla destruction layer with atomic breath, explosions, smoke, shockwaves, debris and collapsing buildings, and rendered/reviewed five standalone 12-second portrait MP4s (growth, clean matched angle, destruction twin, whole-city sky view, fast drone).

2026-07-18 - Cade (via Windows Codex) - [WEB] Made phone gameplay landscape-only with a polished portrait rotation screen, automatic pause/resume across rotation, and a much smaller passive landscape chat feed that expands only when opened; focused mobile automation and portrait/landscape visual QA passed without changing Day 17 state, population, buildings, claims, ownership, GLBs, Blender, or Supabase.

2026-07-18 - Cade (via Windows Codex) - [WORLD] Completed Day 17 from 272 to 301 followers with one guarded +29 growth at Twin Oaks addresses 129-157, synchronized full and six-district web assets, preserved the exact 31-claim/30-account ownership snapshot, widened the whole-town portrait camera after visual QA caught edge clipping, reviewed finished entire-town and downtown showcase videos plus the only animated all-29 growth video, and prepared the three standalone MP4s for Cade's email delivery.

2026-07-18 - Cade (via Windows Codex) - [BOTH] Finished the current play-quality pass: the third-person camera now reaches near-vertical up/down views without ground trapping, far district detail unloads past 112m and restores lightweight silhouettes, claim labels measure each real GLB roof including tall/storybook homes, downtown storefront glass is flush, and persistent chat appears as a compact top-left walking feed; replay rebuild plus GLB and focused browser validation passed without changing Day 16 / 272 / 275, addresses, claims, ownership, world state, or Supabase.

2026-07-17 - Cade and Zach (via their Codex AIs) - [BOTH] Integrated Zach's approved downtown/terrain design package onto Cade's current Day 16 build: rebuilt the thirteen-metre downtown grid, sidewalks/curbs/crossings, storefront public realm, skyline massing, regional terrain, terrain-following suburban roads and foundation pads; regenerated the full GLB plus all six streamed chunks with canonical browser walk surfaces; preserved Day 16 / 272 population / 275 buildings, addresses 1-128, every claim/owner, Supabase, and world_state.json; visually reviewed downtown/perimeter/storybook/school views and retained a responsive balanced graphics path with optional maintainer ultra effects.

2026-07-17 - Cade (via Windows Codex) - [WEB] Added a small grounded avatar jump using Space on desktop and a dedicated mobile JUMP button beside RUN; the follow camera rises with the player, airborne repeat jumps are blocked, and multiplayer visitors see the vertical motion. Focused desktop camera/movement and mobile two-thumb control flows passed without changing Day 16 state, population, geometry, claims, ownership, Supabase, GLBs, or Blender assets.

2026-07-17 - Cade (via Windows Codex) - [WEB] Corrected Avatar System v1 around the approved compact animated characters: the public Tailor now offers only the 37 complete characters plus body color/height, legacy tall modular selections normalize safely and no modular GLB loads, the follow rig initializes in streamed/full paths, desktop uses Mac-safe cursor-locked right-drag orbit plus true eye-height first-person mouse-look after wheel/trackpad zoom, mobile supports camera drag while moving plus pinch zoom, camera-relative A/D are corrected, and the obsolete center white-dot crosshair is removed. Bare legacy `town.html` entry now returns to the current map-preview/Today homepage. Focused desktop/mobile/fallback browser flows passed without changing Day 16 state, population, geometry, claims, ownership, Supabase data, or Blender assets.

2026-07-17 - Cade (via Windows Codex) - [BOTH] Completed Day 16 from 259 to 272 followers with 13 ordinary claimable homes at plan IDs 116-128, finishing Overlook Circle/Willow Hills and opening Twin Oaks Drive; synchronized the full GLB plus six streamed district chunks, inserted all 13 Supabase rows without changing the 30 existing claims, reviewed a completed-town overhead and an all-13 whole-town rise video, validated live Day 16/272/275 state and all eight browser stories, and emailed the two standalone MP4s to tooheycade@gmail.com.

2026-07-17 - Cade (via Windows Codex) - [BOTH] Completed the guarded Day 15 maintenance pass: growth now always runs the Git generator against an exactly matched authoritative iCloud Blender scene (never a stale/missing iCloud script), GUI generation rejects stale embedded code, obsolete deploy/share instructions are visibly retired, expansion/handoff docs match Day 15 through planned address 115, and live seed 73 now matches its canonical Day 9 house and is publicly claimable. Only that Supabase house row changed; the exact snapshot retained all 30 claims across 29 accounts with identical owners/customizations, while world state, population 259, all 262 buildings, geometry, and generated assets remained unchanged.

2026-07-16 - Cade (via Windows Codex) - [BOTH] Added production district streaming for the Blender-authored web town: exports now create a hashed compressed base plus five exact building chunks while retaining the full GLB fallback, distant homes keep lightweight silhouettes, proximity/map/home teleports load their detailed district first, Windows/Mac growth stages every asset, overlapping spawn avatars no longer clip through the first-person camera, and hash/262-building validation plus eight desktop/mobile/fallback browser flows and streamed-vs-full visual QA passed without changing Day 15 state, population, buildings, addresses, claims, ownership, or visible Blender content.

2026-07-16 - Cade (via Windows Codex) - [WEB] Kept the existing interactive 3D town map but replaced its default 259-house sidebar with eight self-updating street groups, made street rows focus the relevant 3D neighborhood and 3D house clicks teleport directly, strengthened exact/partial `@owner`, house-number, and street search, grouped newest/claimed views by street, and passed all five Playwright flows plus desktop/mobile visual browser QA without changing Blender, GLB, world state, population, claims, or ownership.

2026-07-16 - Cade (via Windows Codex) - [WEB] Simplified the new in-town pause overlay to action choices only (resume, map, optional home management, and leave town), removing the unnecessary position-saved heading and explanation; behavior and camera preservation are unchanged.

2026-07-16 - Cade (via Windows Codex) - [BOTH] Rebuilt all ten Kaleidoscope Crest lamps as uninterrupted curved shared-vertex posts with attached banner brackets, replaced the provisional center statue with a connected multi-angle-reviewed hero model whose striped hat/limbs/tail/details no longer float, matched its collider to the 2.18m pedestal, changed Escape into a true position-preserving pause with an explicit resume/leave choice, and exposed the safe confirmed per-house unclaim flow through clear manage-home buttons; GLB integrity, seven Blender proof views, final browser visual QA, and all five Playwright flows passed without changing Day 15 state, population, addresses, claims, or owners.

2026-07-16 - Cade (via Windows Codex) - [BOTH] Tightened all ten Kaleidoscope Crest house hitboxes to the actual wall geometry so their merged lawns/paths/fences/flowers/mailboxes remain walkable, rebuilt the steep uphill lane markings as meshes that physically follow the road slope, connected every crooked center lamp with a solid joint and base, replaced the center tree with a detailed blocky Cat in the Hat statue on its own compact pedestal collider, and passed Blender close-view QA, GLB validation, browser runtime audits, and all five Playwright flows without changing Day 15 population, buildings, addresses, claims, or ownership.

2026-07-16 - Cade (via Windows Codex) - [BOTH] Completed Day 15 from 244 to 259 followers with 15 claimable homes: ten original crooked-storybook houses on the landscaped Kaleidoscope Crest/Wanderlight Loop hill and five ordinary Overlook Circle houses; blended its bright access into the old road, made sloped markings conform and remain evenly spaced, made the hill/ramp walkable for local and multiplayer visitors, fixed aerial road/lake flashing with depth-safe cameras, rebuilt/validated the GLB and public maps, visually reviewed three standalone scene videos (whole-town/all-15 rise, close ten-home feature rise, and finished street-level feature tour), and emailed the three separate MP4 attachments to Cade and Zach without a combined edit.

2026-07-16 - Cade (via Windows Codex) - [WEB] Fixed the newest Overlook Circle houses cutting through two website backdrop mountains by replacing the fixed hill ring with growth-aware per-hill clearance, visually checked Houses #239 and #247, and added a browser regression that requires every hill footprint to clear every current building; no house, road, Blender terrain, GLB, state, population, address, or claim changed.

2026-07-16 - Cade (via Windows Codex) - [WEB] Added a self-updating Today in Followville activity and clean permanent `/house/:id` share addresses on top of the existing live world/map data, highlighted the newest homes, added native-share/clipboard visit cards, and installed five Playwright browser regressions in GitHub Actions for homepage, Today, shared/invalid houses, and chat/map/Escape navigation; this establishes stable place/activity IDs for future roleplay without changing Blender, GLB, state, population, buildings, or claims.

2026-07-16 - Cade (via Windows Codex) - [WEB] Removed the last legacy-home path from normal desktop walking: pressing Escape or otherwise leaving pointer-lock now returns to the redesigned `index.html` rather than revealing the old in-town intro. Escape inside the town map or chat still closes that overlay and remains in the rendered town without pointer-lock; clicking the canvas recaptures mouse-look. No world, house, claim, account, map, multiplayer, or Blender data changed.

2026-07-15 - Cade (via Windows Codex) - [WEB] Fixed the redesigned homepage's Walk action opening the legacy in-town intro: it now routes through `town.html#walk`, removes the route marker after load, and starts directly in the rendered neighborhood. Desktop visitors can click the town canvas for mouse-look; mobile keeps the existing joystick/look controls. No world, house, claim, account, map, or multiplayer data changed.

2026-07-15 - Cade (via Windows Codex) - [WEB] Fixed the live map revealing the older in-town start screen after being opened from the redesigned homepage: a `town.html#map` entry now returns to `index.html` when the map is closed with its button, Escape, or backdrop, while selecting Visit still enters the 3D town and in-game map close behavior remains unchanged. No world, house, claim, or account data changed.

2026-07-15 - Cade (via Windows Codex) - [WEB] Restyled the organized homepage to feel authored rather than AI-generated: removed oversized pill badges, rounded icon tiles, stacked cream cards, and pervasive glass blur; replaced them with a restrained editorial headline, plain ruled Walk/Claim links, unboxed stats, a nearly square paper-plan map frame, simpler copy, and compact mobile navigation while preserving the live map, routes, cache safeguards, background loop, account behavior, and all world data.

2026-07-15 - Cade (via Windows Codex) - [WEB] Fixed intermittent old homepage versions on computer browsers after proving Vercel's bare `/` and `/index.html` routes were serving different deployments: bare `/` now redirects to the uncached `/index.html`, both routes receive `no-store`/`no-cache` headers, matching HTML directives remain, and a targeted `pageshow` reload handles Chrome/Safari back/forward memory; the dashboard/map UI and all world data remain unchanged.

2026-07-15 - Cade (via Windows Codex) - [WEB] Reorganized the homepage from a narrow vertical button stack into a responsive destination dashboard: desktop now places Walk/Claim cards beside a large live isometric town preview, mobile keeps all choices compact above the fold, and the preview redraws built homes, landmarks, and currently visible roads from the existing `world_state.json` stats request so growth updates it automatically; no Blender, GLB, state, population, building, claim, or new image/data source changes.

2026-07-15 - Cade (via Windows Codex) - [WEB] Added a responsive, lightweight isometric 3D town map reachable from the homepage, start screen, in-town button, and desktop M key, with rotate/pan/zoom, instanced colored homes, built-road geometry, search by house/owner/street, newest/school/claimed/my-home filters, and visit teleport; it automatically derives 244 homes, three landmarks, established Founder Park roads, only currently revealed planned roads, and live owner names from existing world/claim data, retains a flat WebGL fallback, and changes no Blender, GLB, state, population, buildings, or claims.

2026-07-15 - Cade (via Windows Codex) - [BOTH] Replaced the plain landing/loading screens with an optimized 12-second Day 14 sidewalk loop aimed at a current Overlook Circle house while two staggered cars drive past, added poster/reduced-motion/data-saver fallbacks and pause-on-walk/tab behavior, and added a reusable render-only `housefront` camera without changing the saved world, GLB, population, buildings, or claims.

2026-07-15 - Cade (via Windows Codex) - [WORLD] Completed Day 14 from 226 to 244 followers with 18 validated houses at plan IDs 93-110, finished Foxglove Court and began Overlook Circle without revealing its future cul-de-sac, synced all 18 homes to claiming, rendered/reviewed rise-overhead plus static-town-overhead plus a temporary England v Argentina #10 supporter scene and a combined 30.13-second Reel cut, emailed all four videos to tooheycade@gmail.com in two messages, kept the fan set out of the saved Blender/web model, and guarded repo-based Windows growth from leaving `main` for stale `wip`.

2026-07-15 - Cade (via Windows Codex) - [WEB] Temporarily removed homeowner yard decorations from the town and customizer while preserving every saved yard choice in Supabase for a future redesign; house colors, claims, Blender/GLB, state, population, and buildings remain unchanged.

2026-07-15 - Cade (via Windows Codex) - [BOTH] Rebuilt founder house #29 with its structure set back 1.3m and its drive/walk still curb-connected; fixed multi-material facade measurement so driveway/mailbox triangles cannot squeeze decorations, fitted the saved full-depth two-person bench between path and mailbox, kept custom trees round in X/Z, and passed all 904 house/decor placements plus current/full-plan collision audits without changing state, population, buildings, seeds, or claims.

2026-07-15 - Cade (via Windows Codex) - [WEB] Fixed house #29's decorations intersecting its double-garage porch/door by measuring each home's full exported structural silhouette and prioritizing the side opposite the actual door material; visually checked #29's tree, bench, and flag and revalidated all 904 placements with zero house/curb intersections.

2026-07-15 - Cade (via Windows Codex) - [WEB] Corrected broken-looking homeowner decorations: pieces now occupy a door/garage-aware side-lawn zone, corner lots steer away from their second road, benches face the street, flags clear porch covers, and tight lots preserve full height/width; visually checked bench/flag/tree at Cade's castle and revalidated all 904 placements.

2026-07-15 - Cade (via Windows Codex) - [WEB] Moved homeowner yard pieces into each home's measured front-yard strip without crossing the curb (including tight founder and corner lots), and replaced oversized circular web hitboxes with oriented house/car footprints plus trunk-only tree collisions; runtime-tested all four decorations across all 226 homes and left Blender/state/GLB unchanged.

2026-07-15 - Cade (via Windows Codex) - [WEB] Allowed trusted admins `cade.toohey` and `stellar.kehler` to own two houses while normal accounts remain capped at one; added per-home visit/customize/unclaim controls and concurrency-safe Supabase enforcement, preserved all 27 claims, and moved yard decorations inward from every road-facing lot edge so Burj/founder decorations no longer land in streets.

2026-07-15 - Cade (via Windows Codex) - [WEB] Built Homeowner Mode: claimed owners can preview/save approved exterior, roof/accent, and door colors plus one lightweight yard piece; added a validated owner-only Supabase RPC and realtime town updates, preserved all 27 existing claims, mapped all 226 homes with per-house material isolation, and left Blender/state/GLB unchanged.

2026-07-14 - Cade (via Windows Codex) - [BOTH] Completed Day 13 from 186 to 226 followers with 40 validated houses at plan IDs 53-92, finished Creekside Bend and began Willow Hills, added reusable newest-district/newest-street cameras, cleared procedural nature from newly revealed roads/lots, rendered and reviewed static street plus house-appearance plus static overhead videos, rebuilt/validated the 6.1 MB GLB, matched all 40 new Supabase rows, and emailed the three videos to zachkehler@gmail.com.

2026-07-14 - Cade (via Windows Codex) - [WEB] Made the temporary multiplayer smiley faces unmistakable at gameplay distance by adding a light circular face panel, larger dark eyes, and a thicker forward-facing smile to every player marker.

2026-07-14 - Cade (via Windows Codex) - [WEB] Improved multiplayer usability: T, /, or Enter now opens focused desktop chat without the Escape/start-screen interruption, Enter sends and restores walking, player markers have forward-facing 3D smiley faces, and admin data is organized into Accounts/Claims and Multiplayer/Chat tabs with compact scrollable sections.

2026-07-14 - Cade (via Windows Codex) - [WEB] Added secure live website multiplayer: online count, visible moving visitor markers and names, signed-in persistent town chat with speech bubbles, plus admin online/session-duration/chat logs; migrated RLS-protected Supabase tables and authenticated RPCs without changing Blender, population, buildings, or existing house claims.

2026-07-13 - Cade (via Windows Codex) - [BOTH] Fixed the three-upper-window `side_garage_two` design that looked half-loaded: its main two-story wall and roof now span the complete facade instead of an offset 70% section; visually checked the corrected real-world house and every other two-story type, reran the zero-overlap 366-address audit, and rebuilt/validated the web model without changing state or claims.

2026-07-13 - Cade (via Windows Codex) - [BOTH] Replaced all 176 ordinary and park-ring home visuals with an optimized 15-design suburban library and six stable color palettes, including complete lots with clear driveways and landscaping; preserved every seed/claim and all world-state values, collision-checked all current homes plus the full 366-address reserve, rebuilt/validated the 6.0 MB web model, and raised website name tags above taller roofs.

2026-07-13 - Cade (via Codex) - [WORLD] Rerendered and visually reviewed the complete Day 12 delivery set after the final playground/wheel corrections (houses appearing, elementary school appearing, and finished town overhead), copied the replacement MP4s to Cade's Codex outputs folder, and emailed all three corrected videos to tooheycade@gmail.com.

2026-07-13 - Cade (via Codex) - [WORLD] Corrected the school-equipment/car follow-up after Cade caught remaining geometry errors: rebuilt the swings with endpoint-aligned connected A-frames and chains, rebuilt the slide rails and exit to follow the chute exactly, and gave the two sides of every car opposite inward tire rotations so all four wheels sit at the front/rear axles and protrude outside the body; verified the playground from above and the side plus both sides of an isolated car before publishing.

2026-07-13 - Cade (via Codex) - [WORLD] Rebuilt the elementary school's rear playground as a finished fenced safety-surface yard with connected roofed towers, a correctly joined deck-to-ground slide, swings, climbing equipment, stepping pods, and ground games; also rotated every ordinary car tire upright, added visible hubs, regenerated the Blender/GLB world, and visually checked close views of both fixes without changing Day 12 or population 186.

2026-07-13 - Cade (via Codex) - [WORLD] Grew Day 12 from 169 to 186 followers with 17 validated Creekside Bend houses (addresses 36-52), completed Heron Court, began Pebble Court, and added a detailed non-claimable full-block elementary school campus; rendered and reviewed separate house-rise, school-rise, and finished overhead videos, validated Blender/GLB, and synced all 18 new records to claiming.

2026-07-13 - Cade (via Codex) - [WORLD] Rebuilt staged suburban roads as continuous shared-vertex meshes so turns cannot gap, and matched established roads with the same width, asphalt, height, and yellow center-dash rhythm; rebuilt and visually reviewed Blender/GLB without changing Day 11 or population 169.

2026-07-13 - Cade (via Codex) - [WORLD] Corrected the suburban placement system: realigned all 35 built planned houses to face their roads, moved the house intersecting Heron Court, sealed curved-road joints, and added permanent facing/road/cul-de-sac/state-drift validation for all 366 planned addresses; Day 11 and population 169 stayed unchanged.

2026-07-12 - Cade (via Codex) - [WORLD] Fixed Day 11 cul-de-sac and pond video flicker by delaying each turnaround until its connecting road is complete and replacing overlapping flat surfaces with shallow solid geometry; rerendered and reviewed both corrected videos.

2026-07-12 - Cade (via Codex) - [WORLD] Grew Followville from 155 to 169 followers with 14 new Creekside Bend houses and only their required winding-road extension, rendered and reviewed a house-loading video plus finished overhead video, validated the web model, and synced every new home to claiming.

2026-07-11 - Cade (via Codex) - [WORLD] Grew Followville from 134 to 155 followers with 21 new Creekside Bend houses and only their required winding road/cul-de-sac pieces, rendered a house-loading video plus a finished overhead video, validated the web model, and synced all new homes to claiming.

2026-07-11 - Cade (via Codex) - [WORLD] Planned and built the hidden next-366-house suburban reserve: six terrain-shaped neighborhoods, winding staged roads, and 18 cul-de-sacs; terrain is visible now, while each future road segment and ordinary house appears only when its growth address is reached, without moving anything already built.

2026-07-10 — Cade (via Windows Claude Cowork) — [BOTH] Added the ability for a
  follower to give up (unclaim) their house, at Cade's request ("people need the
  option to unclaim, one house per user still"). New `unclaim_house()` Postgres
  RPC in supabase_schema.sql -- deletes the caller's own `claims` row, which
  frees the house for anyone (including them) to claim again; the existing
  `claims.user_id` UNIQUE constraint that already enforces one-house-per-account
  keeps enforcing it afterward, so no new concurrency logic was needed, this is
  just claim_house() in reverse. town.html: the account panel (click your
  `@handle ✓` button once you have a house) now shows an "unclaim this house"
  option behind a one-step "are you sure" confirm card (new `attemptUnclaim()`,
  `confirmingUnclaim` state, wired into the existing `renderAuthCard()` flow --
  no new top-level UI, reuses the existing modal). Also documented in
  CLAIMING_SETUP.md (a migration note: existing installs just need to re-run
  the whole `supabase_schema.sql` in the Supabase SQL Editor once, safe since
  everything in it is `IF NOT EXISTS`/`CREATE OR REPLACE`). **Cade: one thing
  still needed from you** -- this session can't reach the Supabase SQL Editor
  itself, so `unclaim_house()` exists in the pushed schema file but hasn't
  actually been created in the live database yet. Paste all of
  `supabase_schema.sql` into the SQL Editor and hit Run (same one-time step as
  the original setup, safe to re-run) before the button will work live.

2026-07-10 — Cade (via Windows Claude Cowork) — [BOTH] Confirmed day 9 (pop 134, 136
  buildings) live on followville-kappa.vercel.app, matching world_state.json exactly. At
  Cade's request, diagnosed the recurring "AI builds on a stale/backup copy" problem and
  wrote up a fix plan in a new file, SYNC_AND_ZONING_PLAN.md (root cause: the iCloud folder
  is used as a live shared working directory for files multiple machines/AI sessions edit
  concurrently; iCloud resolves collisions by silently renaming the loser to a numbered
  copy instead of merging or erroring, so the next session has to guess which copy is
  real -- a wrong guess is exactly "building on a backup"). Corrected a misunderstanding on
  my part along the way: Cade uses Claude (Cowork, Windows); Zach (Mac) uses Claude too
  (Sonnet/Opus/Fable) AND sometimes OpenAI's Codex/GPT models. Also clarified: the day-9
  "curving lane" attempt with the overlapping roads (world_state 5.json/grow_day9_growth.txt,
  never shipped) was Cade using Claude Fable directly to preview that day's growth, not a
  separate AI experimenting on its own -- Fable's road math was just wrong.
  Then found and fixed what this sandboxed session actually could reach: this iCloud
  folder's own `.git` was completely broken (`HEAD`/`config`/`refs/heads/main` had all been
  renamed away by the same race, plus a stale `index.lock`) -- restored those, which is a
  DIFFERENT git-internal-file instance of the race than the `refs/remotes/origin/main`
  duplicate Zach's session found and fixed the same day (see both writeups in CLAUDE.md's
  Day 9 canon / Collaboration section). Could not get `git fetch`/`push` fully working from
  inside that sandbox (a couple of objects read as corrupt -- looks like a sandbox-only
  limitation, not real data loss), so used computer-use (Win+R -> a `.bat` script) to push
  through the real `C:\Users\cadet\followville_repo` clone instead once Cade said "you have
  access to the terminal and whatever you need" -- confirmed pushed to `main`. Along the
  way, nearly clobbered Zach's much-more-current CLAUDE.md/TEAM_LOG.md with a stale local
  copy (the push script's file-copy step happened to fail first, by luck, catching it) --
  refreshed from the real repo before finishing. Added the `[WORLD]`/`[WEB]`/`[BOTH]` TEAM_LOG
  tag convention above and in CLAUDE.md, plus Cade's clarification there that "same world"
  means same geometry, not same visual quality -- the Blender videos are supposed to keep
  looking better than the website; only what's built and where has to match via town.glb.

2026-07-10 — Zach (via Claude) — fixed a typo'd Supabase account handle at Zach's request:
  instagram_handle was "stellarkehler", corrected to "stellar.kehler". The normal signup
  RPC refuses handle changes once an account is verified, so this went straight to the
  profiles table with the service-role key (fix_stellarkehler_handle.command, kept for
  reference). Only instagram_handle changed — verification_status, is_admin, and the
  claimed house are untouched. Confirmed live via public_claims (what the floating name
  tag actually reads). Worth flagging: this account's claimed house (house_id 2) is the
  Burj Khalifa founder house, not an actual "skyscraper" building — the skyscraper
  milestone building doesn't exist in the town yet (unlocks at 2,000 population; we're at
  134). If a real skyscraper is wanted sooner, that'd need a deliberate special-placement
  decision from Cade, not something to do quietly as a side effect of a handle fix.

2026-07-10 — Zach (via Claude) — made the day-9 layout condense automatic going forward,
  per Zach's request ("make the condensed automatic unless otherwise specified"). Until
  today, dense block-filling only happened via the one-off condense_day9.py script (see
  the entry right below this one) — regular growth still used the old pure-radial lot
  order, which scatters new buildings across many blocks instead of filling any one
  solid, and would have gone back to looking sparse again after a few more growth days.
  Promoted that script's block-filling logic into neighborhood_blender.py itself as a new
  sorted_lots_filling() function, and made find_free_lots() use it by default for every
  building type (houses, apartments, parks, pond clusters, all of it) — no code
  invocation is required anymore, it just happens. Kept the old scattered look available
  on purpose, opt-in only: pass --scatter on the CLI for a specific run if that messier
  spread-out look is ever wanted again. Verified the new lot-picker's behavior directly
  against the real world_state.json (pure Python, no Blender needed): simulated adding 40
  houses to the current town landed them in 6 blocks under the new default vs. 13 blocks
  under the old scatter order for the exact same input, with zero collisions, zero
  dead-center placements, and custom/founder blocks still correctly avoided. Not yet
  exercised on a real growth day (that needs Blender, which only runs via a real machine)
  — next real +N day is the live test; if anything looks off compared to how day 9 turned
  out, --scatter is the immediate fallback while it gets sorted out. Pushed to main
  (docs) — condense_day9.py itself is now mostly historical/reference, no longer needed
  for routine growth.

2026-07-10 — Zach (via Claude) — finished and shipped day 9 (population 134, 136
  buildings), picking up from the in-progress entry below. Three real code fixes, all
  permanent (full writeup in CLAUDE.md's Day 9 canon entry and the "House-facing rules"
  section — read those before touching growth/camera code again):
  (1) fixed a real bug where every block's dead-center lot (no road frontage on any side)
  was still being handed to regular houses, stranding them — Cade's screenshots of a
  "house in the middle of the square" were this bug, not a one-off. find_free_lots() now
  skips that lot for good.
  (2) retuned the render cameras (default/overhead orbit, the --hero close-up, and --cam
  street) for a more cinematic look per Zach's feedback — these are the new defaults, no
  need to touch them again unless something looks off compared to today's videos.
  (3) condensed day 9's 64 new houses only (never touching founders, claimed houses, or
  anything from an earlier day — Zach's explicit call) into the sparse/half-empty blocks
  left over from earlier growth days, via a one-off script (condense_day9.py, kept in the
  folder for reference). This was a ONE-TIME cleanup, not automatic — day 10 will scatter
  again over time unless find_free_lots() itself gets the same block-filling logic later.
  Rendered and Zach-approved three final videos with fireworks left out on purpose:
  day_009_hero_fixed, day_009_street_walkin, day_009_overhead_condensed (this last one
  uses +0 instead of replay so the houses-rising animation doesn't play — Zach's cutting
  it into a longer video). Deployed live via deploy_website.command (commit c2ab97e on
  main) and confirmed the live site's world_state.json shows day 9/pop 134/136 buildings.
  **Heads up for Cade before his next growth day:** the town looking dense right now is
  from the one-time condense script, not a permanent behavior — if blocks start looking
  sparse again after a few more growth days, that's expected until someone gives
  find_free_lots() the same block-fill-first ordering permanently.

2026-07-10 — Cade (via Codex) — made a standalone transparent 70-to-134 follower counter animation and matching 134 hold image for the next reel.

2026-07-10 — Zach (via Claude) — grew the town to day 9, population 134 (+64 houses), per
  Cade's go-ahead to build from the day-8/pop-70 state rather than a broken concurrent
  day-9 attempt on Cade's end (he'd added a road that looked terrible and told Zach to
  ignore it — a one-time call, not a standing policy). Filled the empty grid, kept every
  founder/claimed house untouched, and mixed in random house variety (skyscraper/castle/
  toilet excluded from the random pool per Cade's request). While pushing this to `wip`,
  found and fixed a real bug in the new conflict-aware sync scripts themselves (see the
  two entries below dated 2026-07-10) that had briefly reverted several tracked docs/
  scripts — restored them from `main` before re-sharing. Video renders: hero shot
  succeeded; the overhead shot failed and needs a re-render — in progress.

2026-07-10 — Zach (via Claude) — found and fixed the actual cause of Cade's profile-picture
  feature vanishing: share_progress/deploy_website were blindly overwriting whole tracked
  files with whatever was in the iCloud folder, with zero awareness of whether the OTHER
  side had changed that file since last sync. Confirmed via full git history search that
  the feature was never committed anywhere — it was local-only on Cade's end and got
  clobbered before it was ever captured. Rewrote the copy step (sync_lib.sh on Mac,
  sync_push.ps1 on Windows) to do a real 3-way merge per file, same idea as `git merge`:
  auto-combine non-overlapping changes from both sides, and refuse to guess (leave the file
  out, flag it loudly) when both sides changed the same spot. Also found and fixed a fresh
  case of the numbered-conflict-copy bug, this time inside `.git` itself
  (`refs/remotes/origin/main 2`). Windows side is unverified on a real PC — treat next use
  as a test, and if Cade's profile-picture code is still sitting in `.pull_backups/` on his
  machine, it should be recoverable from there.

2026-07-10 — Zach (via Claude) — the merge-detection fix above had its own bug, caught the
  same night before it did lasting damage: the "prior known state" used for the 3-way
  comparison was captured right after cloning, which lands on the repo's default branch
  (main) rather than whichever branch was actually being pushed (wip) — so the first real
  run compared local files against the wrong branch's history and concluded upstream had
  changed things it hadn't, silently reverting grow.sh, deploy_website.bat/.command,
  .gitignore, CLAUDE.md, and TEAM_LOG.md back to older content. Fixed by capturing that
  reference point from the branch actually being worked on, after fetching but before
  checking it out. Restored all the reverted files from main (which was never touched by
  the bug). Also gave deploy_website.command the same explicit "checkout main first" safety
  net deploy_website.bat already had.

2026-07-10 — Zach (via Claude) — fixed a road gap in the park district Zach spotted in the
  web preview ("a road belongs there to get into the circle"): build_district_roads() in
  neighborhood_blender.py builds a connector from the grid to the OUTER ring road, and
  separately a spur from the INNER ring to the gazebo's walking loop, but nothing ever
  bridged the outer ring to the inner ring themselves — a bare ~14-unit strip of grass
  between the two concentric rings with no way to drive/walk from one to the other. Added
  one more road segment that starts exactly where the connector ends and hands off exactly
  where the spur begins, closing the gap with no seam. Verified by querying the actual
  object positions in the open Blender session: connector [69,95] + new "radial" [95,112]
  + spur [112,124] now form one continuous stretch. Re-exported town.glb with the fix —
  reload the local preview to see it. Not yet committed/pushed (still sitting as an
  uncommitted change on top of the `wip` branch already on GitHub).

2026-07-09 — Zach (via Claude) — fixed two real bugs and started moving collaboration off
  iCloud sync onto git, at Zach's request ("work off each other's stuff, not copies").
  Bugs fixed in neighborhood_blender.py/export_web.py (both now the canonical files):
  (1) Cade's three rounds of fireworks/park-camera fixes from earlier today had landed in
  numbered iCloud conflict copies (neighborhood_blender 5/6/7.py) instead of the real
  neighborhood_blender.py, so the live script still had the original buggy version —
  promoted file 7 (a clean superset, verified via diff) to canonical, old version backed
  up as neighborhood_blender_prefix_backup_20260709.py. (2) Found why fireworks looked
  like permanent floating debris on the website: export_web.py's pancaked-houses fix
  force-resets EVERY object in the WORLD collection to scale (1,1,1) before baking
  town.glb, which also permanently un-shrinks the "fw"-named firework burst particles at
  their fully-exploded positions (fireworks are meant to be invisible except for a few
  animated frames, video-only). Fix: export_web.py now deletes all "fw"/"fw.NNN" objects
  before the scale-reset/export step. Verified with --celebrate on: 0 firework objects
  survive into the export now (was previously baking dozens in). Neither fix touched
  world_state.json — day 8/pop 70 unchanged.
  Collaboration change (in progress, not finished — see below): the plan is to stop
  relying on iCloud's file sync to hand work between Cade and Zach (it's the root cause
  of the conflict-copy bug above and others documented in this file) and use git instead —
  pull before starting a session, push when done, same pattern grow_windows.ps1 already
  uses for world_state.json/town.glb, just extended to the code/docs too. Work that isn't
  approved to deploy yet (like today's park district + graphics upgrade) goes to a `wip`
  branch instead of `main`, so it can be pulled and built on without going live; `main`
  stays "what's actually deployed." Created the `wip` branch locally and staged .gitignore
  additions to stop the numbered conflict copies from cluttering `git status` going
  forward, but could NOT commit/push from this AI session — this iCloud folder's own
  `.git` has a stale `.git/index.lock` (dated 2026-07-07) that the sandboxed AI session
  can't delete (permission denied at the OS level, likely specific to how this session's
  sandbox mounts the iCloud folder, not a real problem on an actual Mac). **Whoever picks
  this up next (Zach, in Terminal, has real filesystem permissions):**
  ```
  cd "~/Library/Mobile Documents/com~apple~CloudDocs/neighborhood"
  rm -f .git/index.lock   # only if the next command complains it exists
  git checkout wip 2>/dev/null || git checkout -b wip
  git add -u
  git add AGENTS.md CLAIMING_SETUP.md FOLLOWVILLE_ACCOUNTS_MASTER_PROMPT.md MASTER_PROMPT_ZACH.md admin.html check_town_glb.py check_town_glb.yml deploy_website.command supabase_schema.sql sync_houses.py grow_windows.bat grow_windows.ps1 preview_website.bat preview_website.ps1 deploy_website.bat .gitignore
  git commit -m "WIP: day 8 park district + graphics upgrade + fireworks/version-drift fixes"
  git push -u origin wip
  ```
  After that, tell Cade (via TEAM_LOG) to `git fetch && git checkout wip` on his end
  instead of trusting iCloud to hand him these files.

2026-07-09 — Zach (via Codex) — added a local scalable building-detail pass to the website: clearer facade and roof edges, window mullions, brass door hardware, siding/shingle/wood patterns, and occasional flower boxes; previewed successfully and not deployed.

2026-07-09 — Zach (via Codex) — strengthened the local website graphics after review: richer color and shadows, visible curb/sidewalk finishing, distant low-poly hills and clouds, and scalable instanced street detail; previewed successfully and not deployed.

2026-07-09 — Zach (via Codex) — made a local same-camera before/after comparison of the original and upgraded website graphics so the material and sky changes can be reviewed clearly; nothing deployed.

2026-07-09 — Zach (via Codex) — locally upgraded the walkable website's materials, lighting, and sky for a richer painted low-poly look, plus added a founder-district screenshot view; previewed successfully and did not deploy anything.

2026-07-09 -- Zach (via Claude) -- grew the town to day 8, population 70 (+41 houses).
  Built a whole new circular park district east of town: central park with a gazebo,
  ring roads, and the 41 new houses arranged in two rings around it, every door facing
  the park -- with more variety than the grid houses (two-story homes, townhouses, new
  pastel colors). Rendered three videos with celebration fireworks (houses+park rising,
  a higher/wider overhead drone of the whole town, and an in-park showcase orbit), all
  auto-copied to the Desktop. After Zach's review: re-shot the overhead + in-park videos
  as calm 12-second showcases of the finished town (only the hero shows houses rising)
  and turned the new lighting's brightness back down (it was washing things out). Also upgraded the lighting for all future videos (softer
  shadows, sky fill light). Note: this Mac's iCloud copy had fallen behind again --
  reconciled world_state.json/generator/docs from GitHub (day 7) before growing, and
  backed up the day-7 state first. Website NOT pushed yet -- waiting for Zach to confirm
  the videos look right, then deploying.

2026-07-09 — Cade (via Windows Claude) — set Cade's new building-icon image as the site
  logo (landing page profile photo): downscaled to 512px as logo.png (old one kept as
  logo_previous.png, original upload kept as logo_candidate.png). Found why the live site
  had been showing the emoji fallback instead of any logo: deploy_website.bat copied the
  file to UPPERCASE "LOGO.png" while index.html requests lowercase "logo.png", and Vercel
  is case-sensitive — fixed the deploy script to use the lowercase name (the stale
  LOGO.png in the repo is harmless, left in place per the no-deletions rule).
  ── STATE OF THE PROJECT after today (handoff summary for the next AI) ──
  Everything about claimable homes is LIVE and verified end to end. The complete picture:
  * Live site followville-kappa.vercel.app: index.html (landing; session-aware buttons,
    admin button for admins, logo), town.html (walkable town + full account/claim UI),
    admin.html (admin moderation page, server-side gated), town.glb + world_state.json
    (from the git repo clone, pushed automatically by growth runs).
  * Backend: Supabase project "followville" (ref bposhxtidoyulallvhdp, org "The Human
    Archive"). Canonical schema = supabase_schema.sql (both original section and the
    "WEB ADMIN ACCESS" migration have been run). Keys: legacy anon key is public (in
    town.html/index.html/admin.html); legacy service-role key ONLY in supabase_sync.env
    (iCloud folder, gitignored, never deploy).
  * Residents so far: @cade.toohey (admin, owns house #5 the castle), @stellarkehler
    (admin, verified, no house yet). Verification is manual until Meta app review
    (CLAIMING_SETUP.md §4 has the webhook plan).
  * Daily ops: grow_windows.bat +N grows the town AND git-pushes state AND syncs new
    buildings into Supabase houses (HOUSES_SYNC_OK in grow_log.txt); deploy_website.bat
    pushes doc/code/HTML changes; admin approvals happen on the live Admin page (or
    admin.bat locally). Docs: CLAIMING_SETUP.md is the feature manual, CLAUDE.md's
    "Claimable homes" section is the summary. Known quirks worth reading before working
    here: the iCloud conflict-copy race (CLAUDE.md Third AI section — hit 5+ times today,
    recovery pattern documented) and the Blender-glTF axis flip (blender +y = three -z,
    documented in town.html's claims module).

2026-07-09 — Cade (via Windows Claude) — took the admin page live, properly gated: added an
  is_admin flag (currently @cade.toohey and @stellarkehler), rebuilt every admin action as a
  database function that checks that flag server-side (so only admin accounts can approve/
  reject/revoke — anyone else who finds admin.html gets "No access" and the database refuses
  them), and put an "Admin" button on the homepage that only admins see. Along the way found
  and fixed a real security gap from the original schema: Postgres grants function-execute
  to PUBLIC by default and the original only revoked anon/authenticated, which had left
  admin_verify callable with just the public site key — everything is now revoked from
  PUBLIC explicitly (verified: anon key gets "permission denied"). admin.bat/local mode
  still works unchanged. Also updated deploy_website.bat's whitelist (admin.html now
  deploys; admin.bat and supabase_sync.env stay local).

2026-07-09 — Cade (via Windows Claude) — polished the claiming experience after Cade's first
  real playtest, and approved the first two residents (@cade.toohey → the castle, and new
  user @stellarkehler, verified via DM code). Fixes: name tags were floating over the street
  (Blender's GLB export mirrors the north-south axis — verified against town.glb itself and
  corrected), tags are now smaller, sit just above each house's actual roof, and only appear
  when you're near; the claim prompt now only shows when you're right at a house's front
  door AND looking at it, with a floating "[E] claim this house" tag over that exact house;
  the landing page is session-aware (shows "Go to my home" + "logged in as @handle · log
  out" when appropriate); "go to my home" spawns you facing your own front door. Also built
  admin.bat/admin.html — a LOCAL-ONLY one-click admin page (approve/reject verifications,
  revoke claims) that reads the secret key from supabase_sync.env at runtime, so it can
  never work on the live site; never add it to deploy_website.bat's whitelist.

2026-07-09 — Cade (via Windows Claude) — took claimable homes LIVE: created the Supabase
  project (followville, in "The Human Archive" org) through Cade's browser, ran the schema,
  turned off email-confirmation for smooth signups, wired the anon key into town.html and
  the service-role key into supabase_sync.env (secret, local only), backfilled all 30
  buildings into the houses table, deployed, and verified the live site + database end to
  end. Followers can now sign up and claim houses at followville-kappa.vercel.app — Cade
  approves each Instagram verification by hand for now (CLAIMING_SETUP.md §3: check DMs for
  the code, then `select admin_verify('handle');` in the Supabase SQL editor). Also fixed
  the "website won't load" confusion (double-clicking town.html can't fetch data over
  file:// — use preview_website.bat) and added the new files to deploy_website.bat's
  whitelist.

2026-07-09 — Cade (via Windows Claude) — built the "claimable homes" feature: followers can
  now create an account on the site, verify their Instagram handle with a one-time DM code
  (manually approved by Cade until Meta's app review goes through), and claim exactly one
  house in the town — first come first served, enforced by the database so two people can
  never grab the same house, with live updates in every open browser. New files:
  supabase_schema.sql (run once in Supabase), sync_houses.py + a sync step inside
  grow_windows.ps1/grow.sh (new buildings automatically become claimable after each growth
  day), and CLAIMING_SETUP.md (the full setup + admin guide). town.html got the whole
  account/claim UI (sign up, verification code screen, walk-up-and-press-E claiming, name
  tags floating over claimed houses, "go to my home" spawn); index.html got a "Claim your
  home" button. NOT live yet — Cade still needs to create the Supabase project and paste
  in the keys (15-minute checklist in CLAIMING_SETUP.md §1). Until then the site behaves
  exactly as before. Also: TEAM_LOG.md's plain filename had been eaten by the iCloud race
  again — restored from the freshest conflict copy (TEAM_LOG 7.md) while writing this.

2026-07-09 — Cade (via Windows Claude) — installed Blender's official MCP add-on (from
  blender.org/lab/mcp-server) into the Windows Blender 5.1 install, enabled "Allow Online
  Access" in Blender's System preferences (required for the add-on's local server to run),
  and started the MCP bridge on localhost:9876. This lets this session (and future ones)
  inspect the live Blender scene directly (materials, object hierarchy, scale, etc.) instead
  of only driving Blender headlessly via grow_windows.bat or round-tripping through
  town.glb + pygltflib. Heads up for whoever opens neighborhood.blend next: the add-on's own
  security notice says it lets any connected AI run unsandboxed Python inside Blender with no
  guardrails against data loss/exfiltration -- Cade explicitly approved installing it anyway
  on this everyday PC (not a VM), so if that tradeoff ever needs revisiting, disable/remove
  the "MCP" add-on in Edit > Preferences > Add-ons.
  Also confirmed something worth knowing: neighborhood.blend's saved scene is stale (still
  shows roughly the day-4 state, missing the day 5-7 houses and the pond) because growth has
  been headless-only since day 4 and nothing has re-saved the .blend since. This does NOT
  affect world_state.json, town.glb, or the live site (those are correct/current, built fresh
  by the headless pipeline each run) -- it only matters if someone opens the .blend in the
  GUI expecting to see the current town.

2026-07-09 — Cade (via Windows Claude) — verified the new git-backed grow pipeline end to end
  (test_git_pipeline3.txt): git pull succeeded, Blender read/wrote world_state.json + town.glb
  from C:\Users\cadet\followville_repo via NEIGHBORHOOD_STATE_DIR (state_file in the RESULT line
  confirms it), the sanity check passed (no SANITY_CHECK_FAILED), and git add/commit/push ran
  automatically, correctly reporting NOCHANGES since this was a no-op replay of the already-
  committed day 7 state. Log ended in ALL_DONE. Hit the iCloud race one more time on the way in
  (neighborhood_blender.py's plain filename had been renamed to a numbered conflict copy again --
  restored from the freshest copy) and again on TEAM_LOG.md itself while writing this entry --
  another data point for why the git-backed approach above is the right fix, not a patch.

2026-07-09 — Cade (via Windows Claude) — root-caused the recurring iCloud sync race for real
  this time, instead of just working around it. world_state.json/town.glb now live
  authoritatively in the git repo clone (C:\Users\cadet\followville_repo), not in this iCloud
  folder: neighborhood_blender.py/export_web.py gained a NEIGHBORHOOD_STATE_DIR env-var
  override (unset = old behavior, fully backward compatible), and grow_windows.ps1 now does
  git pull -> point Blender at the repo clone -> git add/commit/push automatically after every
  growth run. Growing the town and publishing its state are one step now instead of two --
  this also kills the "forgot to deploy, site stuck a day behind" failure mode from 2026-07-07.
  Updated deploy_website.bat to stop copying world_state.json/town.glb (it would've stomped
  the fresher git-committed copies) and preview_website.ps1 to serve those two files from the
  repo clone so local preview still works. Added the same opt-in pattern to grow.sh via
  NEIGHBORHOOD_REPO_DIR for Mac -- untested from here, needs a Mac session to verify before
  relying on it. Also built check_town_glb.py (standalone, no-Blender pygltflib check for the
  exact pancaked-scale bug from yesterday) and wired it in twice: once inside export_web.py
  itself (fails the Blender run outright if it finds anything squashed) and once as a GitHub
  Action (.github/workflows/check_town_glb.yml, had a Fable subagent draft the workflow YAML)
  that runs on every push to main -- so a bad export can't reach the live site undetected even
  if the in-Blender check somehow gets bypassed later. Full writeup in CLAUDE.md under "Where
  world_state.json + town.glb actually live now."

2026-07-08 — Cade (via Windows Claude) — found and fixed the real cause of the "pancaked
  houses" bug Cade reported on the live day-7 site (pond + 3 new houses showing up flat,
  as if caught mid-rise). It wasn't the frame_end jump (that fix from 2026-07-05 was still
  needed but not enough) — it was that export_web.py's scale reset only overrides the
  Python-side value; the new buildings still had live rise-animation keyframes attached,
  and Blender's duplicates_make_real() re-applies that animation during export, silently
  baking the mid-rise scale back in. Confirmed directly in the deployed town.glb with
  pygltflib (37 mesh parts squashed to scale 0.001). Fix: export_web.py now also calls
  obj.animation_data_clear() before realizing instances, so there's no animation left to
  reassert anything. Re-exported town.glb (verified 0 squashed nodes, was 37), redeployed
  via deploy_website.bat, confirmed the push landed on origin/main (commit 630e634). Full
  writeup in CLAUDE.md's Web viewer section (new 2026-07-08 PITFALL note) in case this
  pattern ever resurfaces.

2026-07-08 — Cade (via Windows Claude) — grew the town to day 7, population 29 (30
  buildings): added a brand-new "pond" building type with animated ducks
  (build_pond/build_duck/animate_ducks in neighborhood_blender.py, new --pond flag) and
  clustered the 3 new houses around it in a shared 2x2 patch. Rendered a hero shot of the
  pond+houses appearing (day_007_hero_0001-0160.mp4) and a final overhead/drone shot of
  the whole town (day_007_overhead_0001-0160.mp4), both copied to the Desktop. Deployed
  live via deploy_website.bat, confirmed the push landed on origin/main (commit bcf77d0).
  Hit a nasty iCloud sync issue along the way — world_state.json's plain filename kept
  getting renamed to a numbered conflict copy between separate command launches, causing
  one render to silently run against an empty town. Documented the cause and the fix
  (combine the restore + the next action into one script) in CLAUDE.md's Third AI section
  — worth reading if anything like this happens again.

2026-07-07 — Cade (via Windows Claude) — set up real deploying from Windows: installed
2026-07-07 — Zach (via Claude) — set up a real GitHub Desktop clone at ~/Documents/GitHub/followville
  (Separate from the shared iCloud folder, same idea as Cade's Windows deploy_website.bat setup) to
  Find out whether Cade's collaborator invite gives write access, not just read. This line is the
  Test: if it shows up on GitHub after a push, write access is confirmed.

  Git, cloned the GitHub repo, and built `deploy_website.bat` (one-click push: copies the
  current site files in, commits, pushes -- Vercel redeploys automatically). Used it for
  the first time to push the day 6 growth + the new street-cam feature -- the live site
  (followville-kappa.vercel.app) had been stuck showing day 5 since the last Mac push;
  it's now correctly showing day 6/population 26, confirmed in a real browser. Cade did
  one manual GitHub sign-in in his own browser for the first push (normal one-time step,
  this session never saw the credentials); future pushes should be silent.

2026-07-07 — Cade (via Windows Claude) — added a new street-view camera mode
  (`--cam street`) to neighborhood_blender.py: instead of orbiting overhead, the camera
  now drives straight down the town's oldest street (the road past the founder blocks)
  at eye level, aimed far ahead so the heading stays steady the whole way -- a proper
  "walking/driving down the street" shot rather than an orbit. Made the clip length for
  this mode at least 12 seconds so it actually feels slow. Rendered via grow_windows.bat
  in safe `replay` mode (doesn't touch world_state.json/the .blend) --
  day_006_street_0001-0360.mp4, copied to the Desktop. Cade confirmed it looks good.

2026-07-07 — Cade (via Windows Claude) — grew the town for real from Windows for the
  first time: day 5 -> day 6, population 22 -> 26 (4 new houses), using
  grow_windows.bat. Rendered a hero shot of the 4 new houses rising
  (day_006_hero_0001-0160.mp4) and a final overhead shot of the whole town at its new
  size (day_006_overhead_0001-0142.mp4), both auto-copied to the Desktop -- same
  multi-shot pattern as the Mac workflow (real growth quietly, then replay --hero
  --render for the close-up, then +0 --cam overhead --render for the wide shot). Both
  renders finished in under 90 seconds each (much faster than the 10-15 min the Mac
  docs estimate -- this PC's EEVEE render is quick). world_state.json now correctly
  shows day 6/pop 26/26 buildings.

2026-07-07 — Cade (via Windows Claude) — ran a real (safe) end-to-end test of
  grow_windows.bat: `replay` mode, which never touches world_state.json/the .blend by
  design. First attempt failed for a dumb reason (PowerShell treated a harmless Blender
  DeprecationWarning on stderr as a fatal error) -- fixed and reran, got ALL_DONE, town.glb
  refreshed with a fresh timestamp, world_state.json/.blend untouched (verified by hash/
  timestamp). Then built preview_website.bat + preview_website.ps1 (a tiny PowerShell-only
  local server, no Python/Node needed -- fetch() doesn't work over file://) and confirmed
  in a real browser that index.html and town.html both correctly show "day 5 / population
  22" and that town.glb genuinely loads over the wire (200 OK) -- the Blender-to-website
  pipeline is confirmed working end to end from Windows now.
2026-07-07 — Cade (via Windows Claude) — built grow_windows.bat + grow_windows.ps1: a
  Windows equivalent of grow.sh that runs Blender headlessly (--background, no GUI, no
  clicking) via blender.exe at "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe".
  Same +N/-N/=N/replay syntax and extras as grow.sh. Hit and fixed one real bug along the
  way: Windows PowerShell 5.1 misreads em-dash characters in .ps1 files without a BOM,
  which broke a string and crashed the script — both files are plain ASCII now (see
  WEB_VIEWER_CHANGELOG.md). Verified the wiring works (usage message shows correctly with
  no args) but have NOT yet run it against the real world_state.json — that needs Cade's
  go-ahead first. Meant to be launched via Win+R (types fine there) or double-click, not by
  typing into a Command Prompt window (blocked for this session).
2026-07-07 — Cade (via Windows Claude) — correction to my earlier entry today: Blender
  IS actually installed on this Windows PC, and with screen-control access I can open it
  and click around (unlike the Mac AIs, which only ever ran it headlessly via grow.sh).
  Used that to open neighborhood.blend, check the Scripting tab, and rule out one
  hypothesis for the old "20 vs 3 house_d4" bug from WEB_VIEWER_CHANGELOG.md #9 (the
  embedded script copy already has the safe auto-run guard, so it's not silently
  rebuilding on open). Didn't save any changes to the .blend. Still don't have a safe,
  non-GUI way to run actual growth days from here — see updated CLAUDE.md note.
2026-07-07 — Cade (via Windows Claude) — set up a third AI session on Cade's Windows PC,
  working from the same iCloud-synced folder. Documented in CLAUDE.md that this session
  can edit docs/web viewer but has no Blender, so growth days/renders still run on a Mac.
2026-07-05 — Cade (via Claude) — added mobile touch controls (joystick + drag-to-look)
  to town.html, fixed the "pancaked houses" export bug, simplified landing page text.
  Set up this shared team-log + Google Drive collaboration workflow for Zach.
2026-07-06 -- Cade (via Claude) -- grew the town to day 5, population 22 (22 houses). Rendered a hero shot of the new houses appearing and a final overhead shot, both copied to the Desktop. Caught and fixed an accidental double-run of the render script that briefly corrupted the state to day 6/pop 28; restored from a day-4 backup before redoing it cleanly. Also corrected a 1-off population/house-count mismatch by hand-editing the pop field to match the 22 built houses.
