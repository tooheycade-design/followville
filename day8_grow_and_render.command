#!/bin/bash
# DAY 8 — park district: +41 houses around a circular park, 3 videos + fireworks.
# Double-click to run. Everything logs to render_log.txt (ends ALL_DONE/ALL_FAILED).
# Videos auto-copy to the Desktop as each render finishes.
cd "$(dirname "$0")"

if [ "${1:-}" != "--inner" ]; then
  nohup "$0" --inner >/dev/null 2>&1 &
  echo "Day 8 build started in the background."
  echo "Progress: render_log.txt in this folder (ends with ALL_DONE)."
  echo "Videos will appear on the Desktop as each one finishes."
  echo "You can close this window."
  exit 0
fi

exec > render_log.txt 2>&1
echo "=== DAY 8 RUN started $(date) ==="
B="/Applications/Blender.app/Contents/MacOS/Blender"
if [ ! -x "$B" ]; then
  echo "ERROR: Blender not found at $B"
  echo "ALL_FAILED"
  exit 1
fi
set -e
trap 'echo "ALL_FAILED (step: $STEP)"' ERR

STEP="backup state"
cp world_state.json "world_state_day7_backup_$(date +%Y%m%d).json"
echo "backed up world_state.json (day 7)"

STEP="refresh embedded script text in .blend"
"$B" --background neighborhood.blend --python _refresh_text.py
echo "embedded script refreshed"

STEP="growth +41 park district"
echo "--- GROWTH: +41 ring houses around new circular park (day 8, pop 70) ---"
bash ./grow.sh +41 --parkring --time day

STEP="shot 1 hero (houses+park rising, fireworks)"
echo "--- SHOT 1/3: hero rise + fireworks ---"
bash ./grow.sh replay --hero --render --celebrate --time day --tag hero

STEP="shot 2 overhead (whole town, fireworks)"
echo "--- SHOT 2/3: overhead drone, whole town ---"
bash ./grow.sh replay --cam overhead --render --celebrate --time day --tag overhead

STEP="shot 3 in-park showcase (fireworks)"
echo "--- SHOT 3/3: in-park showcase ---"
bash ./grow.sh replay --cam park --render --celebrate --time day --tag park

echo "=== finished $(date) ==="
echo "ALL_DONE"
