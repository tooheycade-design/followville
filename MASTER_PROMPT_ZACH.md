# Master prompt: today's growth day + Insta post, from Zach's Mac
Paste this whole document as the first message to Zach's Claude (Fable). It is the
Mac-specific delta — everything else is already documented in this folder.

## Read these first, in this order (all in this same folder)
1. `CLAUDE.md` — the project memory. Pay special attention to two sections:
   "Where world_state.json + town.glb actually live now" (state moved from iCloud
   into the git repo on 2026-07-09) and "Claimable homes (accounts)".
2. `TEAM_LOG.md` — the top entry is a full STATE OF THE PROJECT handoff summary
   of everything built on 2026-07-09 (accounts/claiming went LIVE, admin page,
   security notes). Skim the other 2026-07-09 entries for detail.
3. `CLAIMING_SETUP.md` — only if you need to touch the accounts/claiming feature.

## Who you're working for
Zach — the second collaborator (see CLAUDE.md's Collaboration section). He has:
GitHub write access (confirmed by a past test push), a repo clone made with GitHub
Desktop at `~/Documents/GitHub/followville` (verify the path), the @followville
Instagram, and — probably — Blender on this Mac (VERIFY before promising a growth
day: `ls /Applications/Blender.app` — grow.sh expects it there).
Zach also owns @stellarkehler, which is one of the two ADMIN accounts on the live
site — relevant for approving new residents (see "While you're at it" below).

## The critical Mac-specific thing (read carefully — untested on a real Mac)
Since 2026-07-09, `world_state.json` + `town.glb` live authoritatively in the GIT
REPO, not in this iCloud folder. On Windows that's automatic; on Mac it's OPT-IN
via an env var, and it has NEVER been tested on a real Mac. You are the test.

**Do NOT run a real growth (`+N`) without this** — you'd grow the town into the
iCloud folder only, the live site would never see it, and the Supabase houses
table and git state would diverge.

The safe sequence:
```bash
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/neighborhood
export NEIGHBORHOOD_REPO_DIR="$HOME/Documents/GitHub/followville"  # verify path first!
./grow.sh replay          # SAFE dry run: never changes world_state.json/.blend
```
Check that: git pull ran, the RESULT line's state file points into the repo clone
(not iCloud), it ends without errors, `git log` in the clone shows nothing weird,
and `HOUSES_SYNC_OK` (or SKIPPED) printed. If the replay behaves, run the real day:
```bash
./grow.sh +N --render     # N = today's follower gain; video auto-copies to Desktop
```
After a real growth, confirm three things: (1) `git log` in the clone shows the
auto-commit "Grow: +N ..." AND it pushed (live site stats update ~1 min later);
(2) `HOUSES_SYNC_OK` printed — that's the new-buildings → website-claiming sync
(it reads `supabase_sync.env`, which reaches this Mac via iCloud — if that file is
missing, iCloud hasn't finished syncing; wait, don't improvise); (3) the town.glb
GitHub Action check is green on the repo's Actions tab.
Then UPDATE CLAUDE.md's "Mac (grow.sh)" note from "untested" to what you found,
and add a TEAM_LOG.md line signed "Zach (via his Claude)".

If Blender is NOT on this Mac: don't fake it — post from an existing render or
ask Cade to run `grow_windows.bat +N --render` on his PC instead.

## Multi-shot renders for the reel (same as always)
Real growth quietly, then `./grow.sh replay --hero --render --tag hero` for the
close-up and `./grow.sh +0 --cam overhead --render --tag overhead` for the wide
shot. Both copy to the Desktop for AirDrop → Instagram. One preview still max
(cost discipline, see CLAUDE.md).

## While you're at it (new since yesterday — the site has accounts now)
Followers can claim houses at followville-kappa.vercel.app. If today's post brings
signups, they'll DM verification codes (like `FV-3A7K2C`) to @followville. To
approve: log into the site as @stellarkehler → an "Admin" button appears on the
homepage → check each DM really came from the listed handle → click approve.
That's the whole flow. Worth mentioning the claim feature in today's caption —
it's brand new and this is the growth loop it was built for.

## Don'ts
* Don't hand-edit `world_state.json` or the `.blend` (city's only memory).
* Don't commit/push `supabase_sync.env` anywhere — it's the secret admin key
  (it's gitignored; leave it that way).
* Don't run growth days simultaneously with Cade — take turns, confirm iCloud
  shows fully synced before starting (Collaboration section of CLAUDE.md).
* iCloud may rename plain-named files to conflict copies mid-session
  ("world_state 3.json", "CLAUDE 7.md"...). Recovery pattern is documented in
  CLAUDE.md's Third AI section — read it BEFORE it happens to you.
