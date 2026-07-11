#!/bin/bash
# One-off: copy the three finished day-8 videos to the Desktop
# (grow.sh's auto-copy silently skipped -- fixed for future runs).
cd "$(dirname "$0")"
{
  echo "=== copy started $(date) ==="
  for f in renders/day_008_hero_0001-0347.mp4 \
           renders/day_008_overhead_0001-0347.mp4 \
           renders/day_008_park_0001-0360.mp4; do
    cp "$f" "$HOME/Desktop/" && echo "COPIED $(basename "$f")"
  done
  echo "COPY_ALL_DONE"
} > copy_videos_log.txt 2>&1
exit 0
