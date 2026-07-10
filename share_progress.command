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

STEP="copy tracked files from iCloud folder"
COPIED=0
for f in $(git ls-files); do
  if [ -f "$SRC/$f" ]; then
    mkdir -p "$REPO/$(dirname "$f")"
    cp "$SRC/$f" "$REPO/$f"
    COPIED=$((COPIED + 1))
  fi
done
echo "copied $COPIED tracked files"

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
