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
echo "$OUT" | grep -q "^export_web.py: wrote" && echo "WEB $DIR/town.glb" || echo "WEB_EXPORT_FAILED"

# if a video was rendered, drop a copy on the Desktop for easy AirDrop -> Instagram
if echo "$OUT" | grep -q "^VIDEO"; then
  NEWEST="$(ls -t "$DIR"/renders/*.mp4 2>/dev/null | head -1)"
  if [ -n "$NEWEST" ]; then
    cp "$NEWEST" "$HOME/Desktop/"
    echo "DESKTOP $HOME/Desktop/$(basename "$NEWEST")"
  fi
fi
