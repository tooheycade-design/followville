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
git pull origin main

STEP="git identity"
git config user.name  >/dev/null 2>&1 || git config user.name  "Zach Kehler"
git config user.email >/dev/null 2>&1 || git config user.email "zachkehler@gmail.com"

STEP="copy tracked files from iCloud folder"
COPIED=0
for f in $(git ls-files); do
  if [ -f "$SRC/$f" ]; then
    cp "$SRC/$f" "$REPO/$f"
    COPIED=$((COPIED + 1))
  fi
done
# new Mac tooling worth tracking alongside grow.sh
for extra in day8_grow_and_render.command deploy_website.command; do
  [ -f "$SRC/$extra" ] && cp "$SRC/$extra" "$REPO/$extra" && git add "$extra"
done
echo "copied $COPIED tracked files"

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
