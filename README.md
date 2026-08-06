# Followville

Followville is the maintainers' persistent Blender town: one follower equals one
home.

- **`CLAUDE.md`** — the manual. Instructions only; read this first.
- **`AGENTS.md`** — a pointer to the manual plus the non-negotiables.
- **`TEAM_LOG.md`** — who changed what, newest first.
- **`HISTORY.md`** — the full historical record: every day's canon from Day 4
  on, the incidents, and the reasoning behind the rules. Nothing is loaded from
  it automatically; go there when a rule looks arbitrary.

## Authoritative locations

- Git repository: `C:\Users\cadet\followville_repo`
- Shared authoritative Blender scene:
  `C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend`
- Canonical city state: the repository's `world_state.json`
- Live website: <https://followville-kappa.vercel.app>

Code, state, manifests, GLBs, chunks, and current documentation come from Git.
The iCloud folder holds the shared Blender scene and verified handoff mirrors.
Do not use numbered iCloud conflict copies as executable source.

## Before any growth

On Windows, run the guarded launcher from the repository:

```text
grow_windows.bat --preflight-only
grow_windows.bat +N --render
```

On Mac, set `FOLLOWVILLE_REPO_DIR` to the local Git clone and run the repository
or mirrored `grow.sh`. The script refuses to run without a clean, current
`main` and matching repository/iCloud scene copies. It always executes the Git
generator; a generator beside the iCloud Blend is ignored and may be missing.

Never delete, reset, replace, or test against canonical `world_state.json`.
Never run a daily growth simultaneously on both machines.

## Historical note

Older setup instructions allowed direct Blender growth, iCloud-only state,
`--no-git`, manual `wip` auto-sharing, and deleting `world_state.json` to reset
a test town. Those workflows are retired and unsafe for the production city.
