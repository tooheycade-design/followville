#!/bin/bash
# Follower Neighborhood — one-line city control
#
#   ./grow.sh +5              add 5 houses (5 followers gained)
#   ./grow.sh -3              remove 3 houses (3 followers lost)
#   ./grow.sh =50             set TOTAL population to 50 (adds/removes the difference)
#   ./grow.sh replay          re-animate the last day, change nothing
#
# Extras (append after the number):
#   --render                  render the day's 9:16 video (renders/day_XXX_*.mp4)
#   --still                   render a single preview PNG instead
#   --apartments N            add N apartment complexes (big milestone days)
#   --parks N | --trees N     community additions
#   --followers N             population change differs from house count
#                             (e.g. +0 --apartments 1 --followers 2000)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
B="/Applications/Blender.app/Contents/MacOS/Blender"

# 2026-07-08 (untested on Mac -- written from the Windows side, see CLAUDE.md's
# iCloud race-condition writeup for the full story): grow_windows.ps1 now has
# world_state.json/town.glb live authoritatively in a git repo clone instead
# of this iCloud-synced folder, since a file that gets read-modified-written
# every growth day is exactly the wrong kind of file to leave in iCloud's sync
# path (it kept randomly losing its plain filename to a numbered conflict
# copy mid-session). grow.sh can opt into the same fix: set
# NEIGHBORHOOD_REPO_DIR to your local git clone of the followville repo (e.g.
# export NEIGHBORHOOD_REPO_DIR="$HOME/Documents/GitHub/followville") before
# running this script. Leave it unset and nothing here changes at all -- this
# is fully backward compatible, opt-in only, since Cade's and Zach's Mac repo
# clone paths aren't the same and neither has been verified from this Windows
# session.
if [ -n "${NEIGHBORHOOD_REPO_DIR:-}" ]; then
  if [ ! -d "$NEIGHBORHOOD_REPO_DIR/.git" ]; then
    echo "NEIGHBORHOOD_REPO_DIR is set to $NEIGHBORHOOD_REPO_DIR but that's not a git clone -- aborting rather than guessing." >&2
    exit 1
  fi
  echo "-- git pull ($NEIGHBORHOOD_REPO_DIR) --"
  (cd "$NEIGHBORHOOD_REPO_DIR" && git pull origin main)
  export NEIGHBORHOOD_STATE_DIR="$NEIGHBORHOOD_REPO_DIR"
fi

ARG="${1:-}"; shift || true
case "$ARG" in
  +*) FLAGS=(--gained "${ARG#+}") ;;
  -*) FLAGS=(--lost "${ARG#-}") ;;
  =*) FLAGS=(--pop "${ARG#=}") ;;
  replay) FLAGS=(--replay) ;;
  *) echo "Usage: grow.sh +N | -N | =N | replay [--render|--still|--apartments N|--parks N|--trees N|--followers N]"; exit 1 ;;
esac

# generator + web export in ONE Blender session, so the export always sees the
# freshly rebuilt world — never the stale scene saved inside the .blend file
OUT="$("$B" --background "$DIR/neighborhood.blend" --python "$DIR/neighborhood_blender.py" --python "$DIR/export_web.py" -- "${FLAGS[@]}" "$@" 2>&1)" || { echo "$OUT" | tail -20; exit 1; }
echo "$OUT" | grep -E "^(RESULT|STILL|VIDEO)" || { echo "$OUT" | tail -20; exit 1; }
GLB_DIR="${NEIGHBORHOOD_REPO_DIR:-$DIR}"
# 2026-07-09: pure-bash match instead of `echo | grep -q` -- with pipefail, grep -q
# exiting early can SIGPIPE the echo and make the whole pipeline "fail" even on a
# match (this produced a false WEB_EXPORT_FAILED and silently skipped Desktop copies)
if [[ "$OUT" == *"export_web.py: wrote"* ]]; then echo "WEB $GLB_DIR/town.glb"; else echo "WEB_EXPORT_FAILED"; fi

if [ -n "${NEIGHBORHOOD_REPO_DIR:-}" ]; then
  (
    cd "$NEIGHBORHOOD_REPO_DIR"
    git add world_state.json town.glb
    if git diff --cached --quiet; then
      echo "NOCHANGES -- world_state.json/town.glb already match the last commit"
    else
      git commit -m "Grow: $ARG (auto-committed by grow.sh $(date -u +%FT%TZ))"
      git push origin main
      echo "PUSHED"
    fi
  )
fi

# if a video was rendered, drop a copy on the Desktop for easy AirDrop -> Instagram
if [[ "$OUT" == *$'\n'"VIDEO "* ]]; then  # 2026-07-09: was `echo|grep -q` -- see SIGPIPE note above
  NEWEST="$(ls -t "$DIR"/renders/*.mp4 2>/dev/null | head -1)"
  if [ -n "$NEWEST" ]; then
    cp "$NEWEST" "$HOME/Desktop/"
    echo "DESKTOP $HOME/Desktop/$(basename "$NEWEST")"
  fi
fi

# 2026-07-09: claimable-homes feature (see CLAIMING_SETUP.md). New buildings in
# world_state.json must also become rows in the Supabase `houses` table or they
# can never be claimed on the site. Insert-only + idempotent; skipped harmlessly
# until supabase_sync.env exists next to this script. A failure here doesn't
# fail the run (the town itself grew fine) but prints HOUSES_SYNC_FAILED loudly.
if [ -f "$DIR/supabase_sync.env" ]; then
  echo "-- houses table sync (claimable homes) --"
  python3 "$DIR/sync_houses.py" || echo "WARNING: new houses won't be claimable on the site until sync_houses.py succeeds -- see CLAIMING_SETUP.md"
else
  echo "HOUSES_SYNC_SKIPPED (no supabase_sync.env -- claimable-homes sync not configured)"
fi

# 2026-07-10: auto-share progress to wip after every successful growth run, so
# Cade (or his AI) can pull_latest.command wip and see it without a second
# manual step -- reuses share_progress.command's own push-to-wip logic (never
# main; deploying stays a deliberate, separate step via deploy_website.command).
# Best-effort: a failure here does NOT fail this grow run, since the town
# itself already grew and saved successfully above -- only the "share it" step
# is at risk. Check share_progress_log.txt if you see AUTO_SHARE_FAILED.
# NOTE: if NEIGHBORHOOD_REPO_DIR is ever adopted here (see the top of this
# file), share_progress.command will need the same world_state.json/town.glb
# exclusion share_progress.bat got on 2026-07-10 -- today it still copies both
# files straight from this iCloud folder, which is correct ONLY because Mac
# growth (without NEIGHBORHOOD_REPO_DIR) writes them here directly.
if [ -x "$DIR/share_progress.command" ]; then
  echo "-- auto-sharing progress to wip --"
  "$DIR/share_progress.command" || echo "AUTO_SHARE_FAILED -- growth itself succeeded and was saved; see share_progress_log.txt"
else
  echo "AUTO_SHARE_SKIPPED (share_progress.command not found/executable)"
fi
