@echo off
REM Followville -- push the live website (GitHub -> Vercel auto-deploy).
REM
REM What this does: copies the current, known-tracked project files from this
REM iCloud folder into the local git clone at C:\Users\cadet\followville_repo,
REM commits whatever changed, and pushes to origin/main so Vercel redeploys.
REM
REM Run via double-click, or Win+R with this file's full path -- no arguments
REM needed. Progress + a final ALL_DONE / ALL_FAILED go to deploy_log.txt next
REM to this file.
REM
REM Only copies the specific files the repo already tracks (see .gitignore in
REM the repo) -- it will NOT push renders/, debug logs, or one-off scripts
REM created during Claude sessions.
REM
REM 2026-07-08: world_state.json and town.glb are DELIBERATELY left OUT of the
REM copy list below. Since that date, grow_windows.ps1 writes those two files
REM straight into this git clone itself (via NEIGHBORHOOD_STATE_DIR) and
REM commits/pushes them right after growing -- see CLAUDE.md's iCloud race-
REM condition writeup for why. If this script copied them from the iCloud
REM folder too, it would silently overwrite the fresher git-committed copies
REM with whatever stale copy happens to be sitting in iCloud (which, under the
REM new pipeline, may not even be kept up to date there anymore). This script
REM now only handles the OTHER tracked files -- docs, code, the web viewer HTML.

setlocal
set SRC=C:\Users\cadet\iCloudDrive\neighborhood
set DST=C:\Users\cadet\followville_repo
set LOG=%SRC%\deploy_log.txt

echo === deploy_website started %DATE% %TIME% === > "%LOG%"

if not exist "%DST%\.git" (
  echo ERROR: %DST% is not a git clone. Run clone_repo.bat first, or re-clone manually. >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

cd /d "%DST%"

echo -- git pull -- >> "%LOG%"
git pull origin main >> "%LOG%" 2>&1

echo -- copying tracked files (world_state.json/town.glb excluded, see note above) -- >> "%LOG%"
REM 2026-07-09: added the claimable-homes files (CLAIMING_SETUP.md,
REM supabase_schema.sql, sync_houses.py). supabase_sync.env is deliberately
REM NOT here -- it holds the secret service-role key and must never be pushed.
REM 2026-07-09b: admin.html added -- safe to deploy since the web admin
REM migration: it holds no secrets and every admin action is gated by
REM profiles.is_admin inside the database itself. admin.bat stays local-only.
for %%F in (AI_HANDOFF.md admin.html CLAUDE.md CLAIMING_SETUP.md export_web.py grow.sh index.html neighborhood.blend neighborhood_blender.py README.md supabase_schema.sql sync_houses.py TEAM_LOG.md town.html WEB_VIEWER_CHANGELOG.md diag_investigate.py _patch_bootstrap.py _refresh_text.py _setup_bootstrap.py .gitignore) do (
  if exist "%SRC%\%%F" copy /y "%SRC%\%%F" "%DST%\%%F" >> "%LOG%" 2>&1
)
REM 2026-07-09: index.html loads "logo.png" (lowercase) and Vercel is
REM case-sensitive -- the old copy-to-LOGO.png meant the live logo 404'd and
REM the emoji fallback showed instead. Copy to the lowercase name index.html
REM actually asks for. (The stale LOGO.png left in the repo is harmless.)
if exist "%SRC%\logo.png" copy /y "%SRC%\logo.png" "%DST%\logo.png" >> "%LOG%" 2>&1

echo -- git add -- >> "%LOG%"
git add -A >> "%LOG%" 2>&1

git diff --cached --quiet
if %errorlevel%==0 (
  echo NOCHANGES -- nothing to deploy, live site already matches this folder >> "%LOG%"
  echo ALL_DONE >> "%LOG%"
  goto :eof
)

set MSG=Update town (deployed %DATE% %TIME%)

echo -- git commit -- >> "%LOG%"
git commit -m "%MSG%" >> "%LOG%" 2>&1

echo -- git push -- >> "%LOG%"
git push origin main >> "%LOG%" 2>&1
if errorlevel 1 (
  echo PUSH_FAILED >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

echo PUSHED: %MSG% >> "%LOG%"
echo ALL_DONE >> "%LOG%"
