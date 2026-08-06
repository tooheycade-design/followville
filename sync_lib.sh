# sync_lib.sh — shared by share_progress.command and deploy_website.command
# (Mac). Not meant to be run directly; sourced by those two scripts.
#
# WHY THIS EXISTS (2026-07-10): both scripts used to blindly `cp` every
# git-tracked file from this iCloud folder over the repo clone, then commit
# and push whatever resulted. That has no concept of "did someone else change
# this file since I last synced" -- so if Cade added a feature to town.html
# that only ever existed in HIS local iCloud folder, and Zach's Mac then
# pushed a graphics update to town.html that was based on an OLDER pull,
# Zach's blind copy silently overwrote Cade's feature. No conflict, no
# warning, nothing to see -- it just vanished. Confirmed via git history that
# this is exactly what happened to Cade's profile-picture feature: no trace
# of it anywhere in the repo's commits, reflog, or dangling objects, meaning
# it was local-only and got clobbered before ever being committed.
#
# The fix: do a real 3-way comparison per tracked file, using THIS CLONE'S
# OWN prior HEAD (captured before the fetch/reset that just ran) as the
# common ancestor -- exactly what `git merge` does natively, just applied
# here because the iCloud folder itself isn't a git working tree.

# safe_copy_tracked_files SRC REPO PREV_COMMIT
# Sets on return: $COPIED (count), $CONFLICT_FILES (space-separated list),
# $MERGED_FILES (space-separated list, auto-merged cleanly), $REFRESHED_FILES
# (space-separated list where the iCloud copy was stale and got updated FROM
# the repo instead of overwriting the repo with it).
safe_copy_tracked_files() {
  local SRC="$1" REPO="$2" PREV="$3"
  COPIED=0
  CONFLICT_FILES=""
  MERGED_FILES=""
  REFRESHED_FILES=""
  local f

  for f in $(cd "$REPO" && git ls-files); do
    [ -f "$SRC/$f" ] || continue

    if [ ! -f "$REPO/$f" ]; then
      # repo doesn't have this file at all yet (e.g. brand new) -- no
      # existing content to lose, safe to add
      mkdir -p "$REPO/$(dirname "$f")"
      cp "$SRC/$f" "$REPO/$f"
      COPIED=$((COPIED + 1))
      continue
    fi

    if cmp -s "$SRC/$f" "$REPO/$f"; then
      continue  # already identical, nothing to do
    fi

    if ! (cd "$REPO" && git cat-file -e "$PREV:$f" 2>/dev/null); then
      # file didn't exist at our last known sync point either -- both sides
      # are introducing it fresh, low risk, just take ours
      cp "$SRC/$f" "$REPO/$f"
      COPIED=$((COPIED + 1))
      continue
    fi

    if (cd "$REPO" && git show "$PREV:$f") | cmp -s - "$REPO/$f"; then
      # repo's freshly-pulled content == our last known base -> nobody else
      # changed this file since we last synced -> this diff is purely ours
      cp "$SRC/$f" "$REPO/$f"
      COPIED=$((COPIED + 1))
      continue
    fi

    # upstream DID change this file since our last sync. Did we change it too?
    if (cd "$REPO" && git show "$PREV:$f") | cmp -s - "$SRC/$f"; then
      # we didn't touch it locally -- the newer upstream version is correct.
      # Do NOT overwrite it with our stale local copy (this is the exact bug
      # that dropped Cade's feature). Refresh our local copy instead so the
      # iCloud folder stops being stale for this file.
      cp "$REPO/$f" "$SRC/$f"
      REFRESHED_FILES="$REFRESHED_FILES $f"
      continue
    fi

    # BOTH sides changed this file since the last sync. Binary files can't be
    # text-merged -- always treat as a conflict rather than risk mangling one.
    case "$f" in
      *.glb|*.png|*.jpg|*.jpeg|*.mp4|*.zip|*.blend|*.blend1)
        CONFLICT_FILES="$CONFLICT_FILES $f"
        continue
        ;;
    esac

    local tmp_base tmp_theirs tmp_ours
    tmp_base=$(mktemp); tmp_theirs=$(mktemp); tmp_ours=$(mktemp)
    (cd "$REPO" && git show "$PREV:$f") > "$tmp_base"
    cp "$REPO/$f" "$tmp_theirs"
    cp "$SRC/$f" "$tmp_ours"
    if git merge-file -q "$tmp_ours" "$tmp_base" "$tmp_theirs" >/dev/null 2>&1; then
      cp "$tmp_ours" "$REPO/$f"
      cp "$tmp_ours" "$SRC/$f"
      COPIED=$((COPIED + 1))
      MERGED_FILES="$MERGED_FILES $f"
    else
      CONFLICT_FILES="$CONFLICT_FILES $f"
    fi
    rm -f "$tmp_base" "$tmp_theirs" "$tmp_ours"
  done
}
