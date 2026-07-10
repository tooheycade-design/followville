#!/bin/bash
# share_progress.command — pushes your current work to the shared "wip"
# branch on GitHub WITHOUT deploying it to the live site (that's what
# deploy_website.command is for, and it only ever touches "main"). Run this
# whenever you want Cade (or his AI) to be able to pull_latest.command and
# see/build on what you've got so far, before it's ready to go live.
#
# Same underlying machinery as deploy_website.command and pull_latest.command
# (the non-iCloud clone at ~/followville_repo) -- see pull_latest.command's
# comment for why that matters. Double-click to run. Logs to
# share_progress_log.txt (ends ALL_DONE / ALL_FAILED).
cd "$(dirname "$0")"
SRC="$(pwd)"
LOG="$SRC/share_progress_log.txt"
exec > >(tee "$LOG") 2>&1
set -e
trap 'echo "ALL_FAILED (step: $STEP)"' ERR

echo "=== SHARE PROGRESS (wip branch, Mac) started $(date) ==="
REPO="$HOME/followville_repo"
BRANCH="wip"

STEP="clone or update repo"
if [ ! -d "$REPO/.git" ]; then
  git clone https://github.com/tooheycade-design/followville "$REPO"
fi
cd "$REPO"
# 2026-07-10: captured BEFORE fetch/reset below -- this is "what this clone
# last knew" and becomes the 3-way merge base for safe_copy_tracked_files
# (see sync_lib.sh). Empty on a brand new clone, which is fine -- the
# function falls back to plain copying when there's no meaningful history yet.
PREV_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "")"
git fetch origin

STEP="git identity"
git config user.name  >/dev/null 2>&1 || git config user.name  "Zach Kehler"
git config user.email >/dev/null 2>&1 || git config user.email "zachkehler@gmail.com"

STEP="checkout wip (branching from origin/main if wip doesn't exist yet)"
if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
  git reset --hard "origin/$BRANCH"
else
  git checkout main
  git reset --hard origin/main
  git checkout -b "$BRANCH"
fi

STEP="copy tracked files from iCloud folder (conflict-aware, see sync_lib.sh)"
source "$SRC/sync_lib.sh"
safe_copy_tracked_files "$SRC" "$REPO" "$PREV_COMMIT"
echo "copied $COPIED tracked files"
[ -n "$MERGED_FILES" ]    && echo "AUTO_MERGED:$MERGED_FILES (both sides had changed these since your last sync, but in non-overlapping places -- merged cleanly, nothing lost)"
[ -n "$REFRESHED_FILES" ] && echo "REFRESHED_FROM_UPSTREAM:$REFRESHED_FILES (your local copy was stale and unchanged by you -- updated it from the newer shared version instead of overwriting the shared version with your stale copy)"
if [ -n "$CONFLICT_FILES" ]; then
  echo "CONFLICTS_DETECTED:$CONFLICT_FILES"
  echo "The file(s) above were changed on BOTH sides since your last sync and could not be auto-merged (either they're binary, or the edits genuinely overlap). They were left OUT of this push so nobody's work gets silently overwritten -- exactly what happened to Cade's profile-picture feature before this fix. Compare $SRC/<file> against $REPO/<file>, decide what the merged result should be, save it to both, then re-run this script."
fi

# 2026-07-10: sync_lib.sh itself isn't tracked yet on a machine's first run
# after this fix, so the loop above (which only walks already-tracked files)
# can't pick it up on its own -- force it in explicitly, same pattern
# deploy_website.command already uses for new Mac tooling.
if [ -f "$SRC/sync_lib.sh" ]; then
  cp "$SRC/sync_lib.sh" "$REPO/sync_lib.sh"
  git add sync_lib.sh
fi

STEP="commit"
git add -A
if git diff --cached --quiet; then
  echo "NOCHANGES -- wip already matches this folder"
else
  DAY=$(python3 -c "import json;s=json.load(open('world_state.json'));print('Day %d: population %d, %d buildings'%(s['day'],s['pop'],len(s['buildings'])))" 2>/dev/null || echo "WIP update")
  git commit -m "$DAY (wip, pushed from Zach's Mac, not deployed)"
  STEP="push"
  git push origin "$BRANCH"
  echo "PUSHED to $BRANCH -- NOT live, Cade can pull_latest.command wip to see it"
fi
echo "ALL_DONE"
