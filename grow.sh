#!/bin/bash
# Followville guarded Mac growth runner.
#
# Code/state/web assets always come from the Git repository. The authoritative
# neighborhood.blend comes from the shared iCloud folder. No iCloud-only state
# fallback exists: a missing/stale path aborts before Blender starts.
set -euo pipefail

BLENDER="${FOLLOWVILLE_BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
REPO="${FOLLOWVILLE_REPO_DIR:-${NEIGHBORHOOD_REPO_DIR:-}}"
SHARED="${FOLLOWVILLE_SHARED_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/neighborhood}"
PREFLIGHT_ONLY=0

ARGS=()
for value in "$@"; do
  case "$value" in
    --preflight-only) PREFLIGHT_ONLY=1 ;;
    --no-git)
      echo "ERROR: --no-git was retired. Followville growth must use the authoritative Git state." >&2
      exit 1
      ;;
    *) ARGS+=("$value") ;;
  esac
done
set -- "${ARGS[@]}"

if [ -z "$REPO" ]; then
  echo "FOLLOWVILLE_REPO_DIR (or NEIGHBORHOOD_REPO_DIR) is required. Refusing iCloud-only growth." >&2
  exit 1
fi
if [ ! -d "$REPO/.git" ]; then
  echo "Configured repository is not a Git clone: $REPO" >&2
  exit 1
fi

REQUIRED=(
  "$REPO/neighborhood_blender.py"
  "$REPO/export_web.py"
  "$REPO/world_state.json"
  "$REPO/town.glb"
  "$REPO/town_manifest.json"
  "$REPO/town_chunks/base.glb"
  "$REPO/neighborhood.blend"
  "$SHARED/neighborhood.blend"
)
for file in "${REQUIRED[@]}"; do
  [ -f "$file" ] || { echo "Missing required Followville file: $file" >&2; exit 1; }
done
[ -x "$BLENDER" ] || { echo "Blender not found or not executable: $BLENDER" >&2; exit 1; }

BRANCH="$(git -C "$REPO" branch --show-current)"
[ "$BRANCH" = "main" ] || { echo "Production growth requires clean branch main; current branch is $BRANCH" >&2; exit 1; }
[ -z "$(git -C "$REPO" status --porcelain --untracked-files=no)" ] || {
  echo "Tracked repository changes are present. Commit or resolve them before growing." >&2
  exit 1
}

if [ "$PREFLIGHT_ONLY" -eq 0 ]; then
  echo "-- git pull --ff-only ($REPO) --"
  git -C "$REPO" pull --ff-only origin main
fi

HEAD="$(git -C "$REPO" rev-parse HEAD)"
ORIGIN_MAIN="$(git -C "$REPO" rev-parse origin/main)"
[ "$HEAD" = "$ORIGIN_MAIN" ] || { echo "Local main does not match origin/main." >&2; exit 1; }
cmp -s "$REPO/neighborhood.blend" "$SHARED/neighborhood.blend" || {
  echo "Repository and iCloud neighborhood.blend differ. Reconcile the scene before growing." >&2
  exit 1
}

export FOLLOWVILLE_REPO_DIR="$REPO"
export NEIGHBORHOOD_REPO_DIR="$REPO"
export NEIGHBORHOOD_STATE_DIR="$REPO"
echo "PREFLIGHT_OK repo=$REPO shared=$SHARED commit=$HEAD"
if [ "$PREFLIGHT_ONLY" -eq 1 ]; then
  exit 0
fi

ARG="${1:-}"
shift || true
case "$ARG" in
  +*) FLAGS=(--gained "${ARG#+}") ;;
  -*) FLAGS=(--lost "${ARG#-}") ;;
  =*) FLAGS=(--pop "${ARG#=}") ;;
  replay) FLAGS=(--replay) ;;
  *)
    echo "Usage: grow.sh +N | -N | =N | replay [options] [--preflight-only]" >&2
    exit 1
    ;;
esac

# Generator + export remain in one Blender process; the freshly rebuilt WORLD
# is exported before the process exits.
OUT="$("$BLENDER" --background "$SHARED/neighborhood.blend" \
  --python "$REPO/neighborhood_blender.py" \
  --python "$REPO/export_web.py" -- "${FLAGS[@]}" "$@" 2>&1)" || {
    echo "$OUT" | tail -20
    exit 1
  }
echo "$OUT" | grep -E "^(RESULT|STILL|VIDEO)" || { echo "$OUT" | tail -20; exit 1; }

if [[ "$OUT" == *"export_web.py: wrote"* ]]; then
  for asset in "$REPO/town.glb" "$REPO/town_manifest.json" "$REPO/town_chunks/base.glb"; do
    [ -f "$asset" ] || { echo "WEB_EXPORT_FAILED -- missing $asset" >&2; exit 1; }
  done
  echo "WEB $REPO/town.glb"
else
  echo "WEB_EXPORT_FAILED -- export_web.py did not confirm a complete export" >&2
  exit 1
fi

(
  cd "$REPO"
  git add world_state.json town.glb town_manifest.json town_chunks
  if git diff --cached --quiet; then
    echo "NOCHANGES -- state and town assets already match the last commit"
  else
    git commit -m "Grow: $ARG (auto-committed by grow.sh $(date -u +%FT%TZ))"
    git push origin main
    echo "PUSHED"
  fi
)

if [[ "$OUT" == *$'\n'"VIDEO "* ]]; then
  NEWEST="$(ls -t "$SHARED"/renders/*.mp4 2>/dev/null | head -1 || true)"
  if [ -n "$NEWEST" ]; then
    cp "$NEWEST" "$HOME/Desktop/"
    echo "DESKTOP $HOME/Desktop/$(basename "$NEWEST")"
  fi
fi

SYNC_ENV=""
if [ -f "$REPO/supabase_sync.env" ]; then
  SYNC_ENV="$REPO/supabase_sync.env"
elif [ -f "$SHARED/supabase_sync.env" ]; then
  SYNC_ENV="$SHARED/supabase_sync.env"
fi
if [ -n "$SYNC_ENV" ]; then
  echo "-- houses table sync (claimable homes) --"
  set -a
  # shellcheck disable=SC1090
  . "$SYNC_ENV"
  set +a
  python3 "$REPO/sync_houses.py" || echo "WARNING: houses sync failed; see CLAIMING_SETUP.md"
else
  echo "HOUSES_SYNC_SKIPPED (no supabase_sync.env -- claimable-homes sync not configured)"
fi

echo "HANDOFF_SYNC_SKIPPED (authoritative main already contains the growth assets)"
