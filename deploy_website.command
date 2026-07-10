#!/bin/bash
# deploy_website.command — Mac version of deploy_website.bat (2026-07-09).
# Pushes the current town to GitHub -> Vercel auto-redeploys the live site.
# Double-click to run. Logs to deploy_log.txt (ends ALL_DONE / ALL_FAILED).
#
# What it does: clones (first time) or pulls the followville repo into
# ~/followville_repo, copies this folder's repo-tracked files in, commits, pushes.
# First push may need a one-time GitHub sign-in (a prompt from git itself).
cd "$(dirname "$0")"
SRC="$(pwd)"
LOG="$SRC/deploy_log.txt"
exec > >(tee "$LOG") 2>&1
set -e
trap 'echo "ALL_FAILED (step: $STEP)"' ERR

echo "=== DEPLOY (Mac) started $(date) ==="
REPO="$HOME/followville_repo"

STEP="clone or update repo"
if [ ! -d "$REPO/.git" ]; then
  git clone https://github.com/tooheycade-design/followville "$REPO"
fi
cd "$REPO"
# 2026-07-10: captured BEFORE the pull below -- see sync_lib.sh for why.
PREV_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"
git pull origin main

STEP="git identity"
git config user.name  >/dev/null 2>&1 || git config user.name  "Zach Kehler"
git config user.email >/dev/null 2>&1 || git config user.email "zachkehler@gmail.com"

STEP="copy tracked files from iCloud folder (conflict-aware, see sync_lib.sh)"
source "$SRC/sync_lib.sh"
safe_copy_tracked_files "$SRC" "$REPO" "$PREV_COMMIT"
# new Mac tooling worth tracking alongside grow.sh
for extra in day8_grow_and_render.command deploy_website.command sync_lib.sh; do
  [ -f "$SRC/$extra" ] && cp "$SRC/$extra" "$REPO/$extra" && git add "$extra"
done
echo "copied $COPIED tracked files"
[ -n "$MERGED_FILES" ]    && echo "AUTO_MERGED:$MERGED_FILES (both sides had changed these since your last sync, but in non-overlapping places -- merged cleanly, nothing lost)"
[ -n "$REFRESHED_FILES" ] && echo "REFRESHED_FROM_UPSTREAM:$REFRESHED_FILES (your local copy was stale and unchanged by you -- updated it from the newer shared version instead of overwriting the shared version with your stale copy)"
if [ -n "$CONFLICT_FILES" ]; then
  echo "CONFLICTS_DETECTED:$CONFLICT_FILES"
  echo "The file(s) above were changed on BOTH sides since your last sync and could not be auto-merged. They were left OUT of this deploy so nobody's work gets silently overwritten -- exactly what happened to Cade's profile-picture feature before this fix. Compare $SRC/<file> against $REPO/<file>, decide what the merged result should be, save it to both, then re-run this script. Check the log for CONFLICTS_DETECTED before assuming ALL_DONE means everything went out."
fi

STEP="commit"
git add -A
if git diff --cached --quiet; then
  echo "NOCHANGES -- repo already matches this folder"
else
  DAY=$(python3 -c "import json;s=json.load(open('world_state.json'));print('Day %d: population %d, %d buildings'%(s['day'],s['pop'],len(s['buildings'])))")
  git commit -m "$DAY -- circular park district, lighting upgrade (pushed from Zach's Mac)"
  STEP="push (may need one-time GitHub sign-in)"
  git push origin main
  echo "PUSHED -- Vercel will redeploy followville-kappa.vercel.app in ~1 minute"
fi
echo "ALL_DONE"
