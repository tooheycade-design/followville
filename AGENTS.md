# FOLLOWVILLE — agent instructions

**Read `CLAUDE.md`. It is the full manual for this project and it applies to
you.** This file used to be a near-copy of it with "Claude" replaced by "Codex";
the two drifted apart, so there is now one manual and this pointer.

`HISTORY.md` holds the complete historical record — the day-by-day canon, the
incident write-ups, and both files as they stood on 2026-07-31. Nothing was
deleted, only moved.

**Then run `check_toolchain.py` before doing anything else.** It tells you what
this session can actually do rather than what the docs claim, and prints the fix
for anything missing:

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_toolchain.py
```

Sign your `TEAM_LOG.md` line with which AI and machine made the change, e.g.
"Cade (via Windows Codex)". A session that only read things does not need a log
entry — the log is who changed what.

---

The handful below are repeated here so they cannot be missed even if the manual
is not read. **They are a summary, not the whole set** — `CLAUDE.md` has the
rest, and you are expected to have read it.

- **`world_state.json` is the city's only memory.** Never edit or delete it
  casually. Back it up before anything risky. It lives in the Git repo
  (`C:\Users\cadet\followville_repo`), never in iCloud.
- **Git is the only source.** The authoritative Blend is the tracked
  `neighborhood.blend` in this repo. Grow only through the guarded launchers
  (`grow_windows.bat`, `grow.sh`), which refuse to run unless the repo is clean
  `main` and matches `origin/main`. `--no-git`, iCloud state/scene copies and
  unguarded Blender growth are retired, not fallbacks.
- **Before committing anything that moves a landmark or a road**, run
  `check_world_geometry.py` and then `check_world_geometry.py --self-test`, with
  the Blender Python — see `CLAUDE.md`'s Environment section for the path, why
  the `python` on PATH will not work, and why PowerShell 5.1 cannot chain them
  with `&&`. Declare new landmarks and authored roads in `world_layout.py`, or
  the audit cannot defend them.
- **Never place two independently rendered visible faces on the same plane.**
  Fix depth conflicts by physically separating geometry, not with
  `polygonOffset`. Review every new repeated asset head-on *and* from both
  oblique sides.
- **Codex and Claude sometimes run on the same task at once.** `git fetch` and
  read incoming commits before you commit, and re-read shared files immediately
  before editing them.
- Add one line to `TEAM_LOG.md` before handing off, tagged `[WORLD]`, `[WEB]`
  or `[BOTH]`.
