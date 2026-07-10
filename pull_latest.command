#!/bin/bash
# pull_latest.command — brings Cade's (or your own past session's) latest
# work from GitHub into this iCloud folder. Run this FIRST, every session,
# before editing anything. Companion to deploy_website.command (pushes the
# other direction) and share_progress.command (pushes WIP without deploying).
#
# Why this exists (2026-07-10): editing files directly in this iCloud folder
# and trusting iCloud Drive itself to sync them to Cade's machine is exactly
# what caused the repeated "numbered conflict copy" bugs documented in
# CLAUDE.md, plus a nastier one: this folder's own .git got corrupted by
# stale lock files that iCloud even synced onto another machine. This script
# sidesteps all of that by using GitHub as the sync layer instead of iCloud:
# it updates a plain, non-iCloud-synced local clone (~/followville_repo) and
# copies the result INTO this folder. iCloud still syncs this folder to Cade
# as always, but the actual "did I get Cade's real latest work" question is
# now answered by git/GitHub, never by hoping iCloud's file rename won.
#
# Double-click to run. Optional: pass a branch name (defaults to "main") if
# you want to pull down WIP work instead, e.g. from Terminal:
#   ./pull_latest.command wip
# Logs to pull_log.txt (ends ALL_DONE / ALL_FAILED).
cd "$(dirname "$0")"
DST="$(pwd)"
LOG="$DST/pull_log.txt"
exec > >(tee "$LOG") 2>&1
set -e
trap 'echo "ALL_FAILED (step: $STEP)"' ERR

echo "=== PULL LATEST (Mac) started $(date) ==="
REPO="$HOME/followville_repo"
BRANCH="${1:-main}"
echo "branch: $BRANCH"

STEP="clone or update repo"
if [ ! -d "$REPO/.git" ]; then
  git clone https://github.com/tooheycade-design/followville "$REPO"
fi
cd "$REPO"
git fetch origin

STEP="git identity"
git config user.name  >/dev/null 2>&1 || git config user.name  "Zach Kehler"
git config user.email >/dev/null 2>&1 || git config user.email "zachkehler@gmail.com"

STEP="checkout branch"
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
git reset --hard "origin/$BRANCH"

STEP="back up anything this pull is about to overwrite"
BACKUP="$DST/.pull_backups/$(date +%Y%m%d_%H%M%S)"
BACKED_UP=0
for f in $(git ls-files); do
  if [ -f "$DST/$f" ] && ! cmp -s "$REPO/$f" "$DST/$f"; then
    mkdir -p "$BACKUP/$(dirname "$f")"
    cp "$DST/$f" "$BACKUP/$f"
    BACKED_UP=$((BACKED_UP + 1))
  fi
done
if [ "$BACKED_UP" -gt 0 ]; then
  echo "backed up $BACKED_UP locally-different file(s) to .pull_backups/ before overwriting -- check there if anything looks lost"
fi

STEP="copy tracked files into this folder"
COPIED=0
for f in $(git ls-files); do
  mkdir -p "$DST/$(dirname "$f")"
  cp "$REPO/$f" "$DST/$f"
  COPIED=$((COPIED + 1))
done
echo "copied $COPIED tracked files from origin/$BRANCH into this folder"
echo "ALL_DONE"
