# Zach's Mac handoff — guarded Followville workflow

Read `AGENTS.md`, `CLAUDE.md`, and the newest `TEAM_LOG.md` entries from the
Git repository before doing anything. `CLAIMING_SETUP.md` is required for
account or ownership work.

## Authoritative split

- Git clone: executable code, canonical `world_state.json`, complete/streamed
  web assets, and current documentation.
- Shared iCloud folder: authoritative `neighborhood.blend` plus verified
  plain-name handoff mirrors.
- Numbered iCloud conflict copies are history/recovery material, never scripts
  to execute.

## First Mac preflight

Confirm Blender and Zach's clone path, then set both locations explicitly:

```bash
export FOLLOWVILLE_REPO_DIR="$HOME/Documents/GitHub/followville"
export FOLLOWVILLE_SHARED_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/neighborhood"
cd "$FOLLOWVILLE_REPO_DIR"
./grow.sh --preflight-only
```

The preflight must report `PREFLIGHT_OK`. It intentionally aborts if:

- the repository is missing, dirty, not on `main`, or differs from
  `origin/main`;
- the repository generator or shared iCloud Blend is missing;
- the repository and shared Blend copies differ;
- Blender is missing.

Do not bypass a failed preflight and do not use the retired iCloud-only or
`--no-git` workflow. If this Mac has not yet passed the current preflight, ask
Cade to run the growth from Windows instead.

## Production growth

Only after Cade and Zach confirm that one person is running today's growth:

```bash
./grow.sh +N --render
```

The generator and exporter run from Git against the shared Blend in one
Blender process. State/full GLB/manifest/chunks are committed and pushed to
`main` together, then Supabase receives insert-only rows for new buildings.
Confirm the GitHub Action and live state after the push.

## Hard rules

- Never edit/delete/reset canonical `world_state.json`.
- Never run a second growth for the same day.
- Never commit or expose `supabase_sync.env`.
- Never use `share_progress.*` or `deploy_website.*` for routine repo-based
  growth; those scripts are legacy recovery/handoff tools.
- Inspect rendered visual work before calling it finished.
- Add one concise `TEAM_LOG.md` entry for completed work.
