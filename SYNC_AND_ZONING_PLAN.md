# Followville — Sync Discrepancy Diagnosis & Scaling Plan
> **Historical planning document.** Its 2026-07-10 diagnosis is useful context,
> but it is not an operating guide. The guarded Git/iCloud source split in
> `AGENTS.md`, `CLAUDE.md`, and the current growth scripts supersedes its
> proposed workflow. Do not execute old `wip` or iCloud-only steps from here.

*Written 2026-07-10. Spec/planning document only — no implementation yet. Per your usual pattern, hand this to a separate Fable build session once you and Zach agree on the approach.*

## 0. Status check
Day 9 (population 134, 136 buildings) is confirmed live at `followville-kappa.vercel.app` — `world_state.json` served from the live site matches the local copy exactly.

## 1. Do I agree with your read of what's gone wrong? Yes — with one addition.

You're right that the core problem is **AIs building on top of stale/backup copies instead of the real latest version**. Reading through today's files, I can point to the actual mechanism:

**Root cause: the iCloud folder is being used as a live, shared working directory for files that get edited constantly, by multiple machines, multiple AI sessions, possibly at the same time.** iCloud (like Dropbox/Google Drive) resolves same-file conflicts by silently renaming the loser to `filename 2.ext`, `filename(1).ext`, etc. — it never merges, never blocks, never alerts anyone. So when two sessions touch `world_state.json`, `neighborhood_blender.py`, `CLAUDE.md`, or `TEAM_LOG.md` close together, one of them gets orphaned into a numbered copy, and whichever AI opens the folder next has no reliable way to know which numbered file (if any) is the real one — it has to guess from timestamps and content. That guess is sometimes wrong, and a wrong guess is exactly "building on top of a backup."

This is already partially diagnosed and partially fixed in your own docs — `world_state.json`/`town.glb` were moved off iCloud onto a plain git clone on Windows (`NEIGHBORHOOD_STATE_DIR`), and today Zach built `pull_latest`/`share_progress`/`deploy_website` scripts to make GitHub the real handoff mechanism for everything else. **But that fix is incomplete in three ways:**

1. **It's opt-in, not enforced.** Nothing stops an AI session (like this one, today) from just reading/editing files straight in the iCloud folder without running `pull_latest` first. That's exactly what happened in this conversation — I read the folder as-is and never pulled.
2. **It's not verified on Mac.** The Windows side (`NEIGHBORHOOD_STATE_DIR`, `grow_windows.ps1`) has been tested; the Mac equivalent (`NEIGHBORHOOD_REPO_DIR`) is explicitly marked "written from Windows, never tested on an actual Mac" in your own docs.
3. **Docs still live and get edited in the iCloud folder itself**, so `CLAUDE.md`/`TEAM_LOG.md`/`neighborhood_blender.py` still hit the same race even after the fix — which is why there are 11 numbered copies of `CLAUDE.md` sitting in this folder right now.

**One thing I'd add to your diagnosis: you're maintaining two nearly-identical doc files by hand** — `AGENTS.md` (for Codex/GPT sessions) and `CLAUDE.md` (for Claude sessions) — with the same "Current canon" section that has to be updated identically, in two places, every single day. That's a second, independent source of drift on top of the iCloud race: even a perfectly-synced folder still needs someone to remember to edit both files in lockstep.

## 2. Fix for the sync/coordination problem

**A. Make the git clone the *only* place anything gets edited — retire the iCloud folder as a working directory.**
Right now git is bolted onto the side of the iCloud workflow ("pull into iCloud folder, work there, push back out"). The more robust version: everyone (human or AI) works directly in the local git clone (`~/followville_repo` / `C:\Users\cadet\followville_repo`), and the iCloud folder stops being a place code/docs get edited at all. This removes the race condition instead of managing it. Practically: point Cade's and Zach's AI sessions at the git clone path, not the iCloud path, going forward.

**B. Merge `AGENTS.md` and `CLAUDE.md` into one file.**
Keep one canonical doc (say `PROJECT.md`), with `AGENTS.md`/`CLAUDE.md` reduced to a one-line pointer at the top ("see PROJECT.md") if a given AI vendor insists on that specific filename. One doc, one "Current canon" section, no drift.

**C. Enforce the pull, don't just offer it.**
Add a check at the top of `grow_windows.bat`/`grow.sh` (and any doc-editing routine) that refuses to proceed if the local clone is behind `origin` — right now the scripts *can* pull first, but nothing stops skipping straight to editing. A hard fail ("you're 3 commits behind, run pull_latest first") turns "forgot to sync" from a silent data-loss risk into a loud, impossible-to-miss error — which is exactly the git philosophy you already chose for `world_state.json`, just extended everywhere.

**D. A lightweight "who's working right now" signal.**
You said you're open to AIs checking a message app or website automatically — that's more infrastructure than you need for the actual problem. The cheapest fix: a single `SESSION_LOCK` file in the repo (name, machine, start time), created at the start of a session and deleted at the end. Any AI starting a session checks it first; if it's set and recent, it says so instead of barreling ahead. This is the automatable version of "take turns," and it costs nothing to build (no external service, no scheduled polling) — TEAM_LOG.md stays as the plain-English "what happened" record, the lock file solves the "is someone else in here right now" problem TEAM_LOG was never designed for.

**E. Make the CI check catch bad state, not just bad geometry.**
`check_town_glb.py`/the GitHub Action already reject a broken `town.glb`. Extend the same Action to sanity-check `world_state.json` on every push: day number never decreases, no duplicate `seed` values, no two buildings claiming the same `gx`/`gy` (off-grid buildings excluded). That turns "someone pushed on top of a stale backup" into an automatic, loud CI failure instead of a silent population count that's wrong until someone notices.

## 3. The "my AI didn't know that was a website-only change" problem

You caught a second, distinct bug while I was writing this up: Zach's AI recently added backdrop mountains and clouds, but only inside the website's Three.js scene (`town.html`) — not through Blender. Your own docs say the web viewer is supposed to be a direct, drift-proof export of what Blender built ("real geometry... pixel-for-pixel the same model Blender rendered, no drift, no manually-ported shapes to keep in sync"). The mountains/clouds change quietly broke that promise: it's a piece of the world that exists on the website but not in `world_state.json`, not in `neighborhood_blender.py`, and not in any video. So when your AI later went to update things, it had no way to know that change even happened — it wasn't lying dormant in a numbered iCloud copy like the sync-race bugs above, it was just never recorded anywhere your AI would think to look, because there's currently no concept of "this change is website-presentation-only, not world canon."

**Why this matters more as you scale:** every time someone (human or AI) makes something look nicer directly in `town.html` instead of through Blender, the website silently drifts further from being "the same city as the videos." At some point the two stop being one project with two views and start being two different cities that happen to share a population counter.

**Two ways to fix it — pick one as a rule, not case-by-case:**

**Option A — everything visual goes through Blender, even decoration.** Add the mountains/clouds/sky as ordinary objects in Blender's `WORLD` collection (marked non-claimable, no grid position, purely environmental — same idea as `pond`/`parkdistrict` already being special-cased), so `export_web.py` picks them up automatically and they show up identically in both the rendered videos and the website. This keeps the single-source-of-truth promise fully intact — nothing exists in one place but not the other, ever.

**Option B — formally split "world canon" from "website presentation," and log which one every change touches.** If some things really are website-only by design (they already exist — the claim UI, name tags, the joystick/touch controls, the session-aware landing page buttons — none of those belong in a Blender render), stop treating that as an implicit judgment call and make it explicit:
- Add a "**Website-only vs World canon**" list to the merged canon doc (see 2B) that's kept current: two short bullet lists, "these files/features are Blender-derived and must match `world_state.json`" vs "these are website-only presentation, not exported from Blender, on purpose."
- Every `TEAM_LOG.md` entry gets a one-word tag at the start — `[WORLD]`, `[WEB]`, or `[BOTH]` — so any AI scanning the log for "what did I miss" can instantly tell which entries are even relevant to the surface it's about to touch, instead of discovering the gap the hard way like today.

Given you want the website and videos to actually be the same city, I'd lean Option A for anything that's genuinely part of the town's geography (mountains, sky, terrain) and reserve Option B only for things that are inherently interactive/UI and could never make sense in a rendered video anyway (name tags, claim prompts, controls).

**Clarified by Cade, 2026-07-10: "same world" is about geometry, not visual quality.** The
Blender-rendered videos should keep looking better than the website — richer materials, real
lighting, depth of field, all the things offline EEVEE/Cycles can do that a real-time browser
scene can't. Option A only requires that the *geometry* (what exists, where) comes from
Blender and matches on both ends via town.glb; the two renderers are still free to shade/light
that same geometry very differently. So: build new geography in Blender first (for a shared,
single-source-of-truth layout), then let the website's Three.js materials stay lighter/faster
than the Blender render on purpose — that's not drift, it's two renderers doing their best
with the same underlying city.

## 4. Fix for the "growth is a manual headache" problem

This is a real, separate problem from sync — even with perfect sync, someone still has to hand-invent the layout every day (today's overlapping-road issue happened *inside* a single AI's single generation, not because of a sync bug — it's a planning/geometry problem).

**A. Stop hand-authoring a new one-off script every growth day.**
`day8_grow_and_render.command`, `day9_grow_and_still.bat`, etc. are each written fresh, by whichever AI is on duty, for that one day only. That's exactly the kind of throwaway code most likely to have a bug nobody catches (like Fable's road math today). Replace them with one permanent, parameterized script (`grow_day.sh --count N`) that always does the same validated thing — new "creative" ideas (a park ring, a curving lane) become a reviewed, tested *option* inside `neighborhood_blender.py` itself, not a one-off command file.

**B. Pre-plan the road network instead of improvising it per batch.**
Right now each "district" (grid, park ring, lane) invents its own road geometry from scratch, in whatever AI session happens to build it that day — that's why a road math error could ship at all. The fix: define a small number of reusable "district templates" (grid extension, ring, future ones) as tested, unit-checked functions in the generator — checked once for "does every road segment connect with no gaps and no overlaps" — and growth days just place the next template instance, they don't invent new road math live.

**C. A population-tier housing plan, decided now, not improvised at each milestone.**
Your instinct here is right, and it's the same fix as 3B applied to *building type* instead of roads: write down the tiers in advance so nobody has to make a judgment call under time pressure. A starting point to react to/edit together with Zach:

- 0–500 pop: single-family houses (current behavior)
- 500–2,000: apartment buildings introduced, each holding ~10–20 followers, mixed in alongside remaining single houses
- 2,000–10,000: your existing skyscraper milestone, now the dominant new-building type
- 10,000+: your existing stadium milestone stays as a landmark, not a housing type

This slots directly into the milestone system you already have (500/2,000/10,000 are already special-cased in the code) — it's an extension of an existing pattern, not new architecture.

## 5. Suggested next step
This is a three-part build (cross-machine sync infra, the world-canon/website-presentation split, and generator/zoning logic) — worth splitting into separate Fable sessions once you and Zach have looked this over and told me what to change. Order matters: do the sync fix (section 2) first, since everything else needs a reliable single copy to build on; the canon/website split (section 3) next, since it's mostly a documentation + one Blender-collection change; and the zoning/tier system (section 4) last, since it's the most speculative and easiest to get wrong if it's built on top of a workflow you're about to replace.
