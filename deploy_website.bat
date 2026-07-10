@echo off
REM Followville -- push the live website (GitHub -> Vercel auto-deploy).
REM
REM 2026-07-10: this used to do the copy/commit/push itself in batch with a
REM blind file-copy loop (world_state.json/town.glb excluded on purpose, see
REM below). Rewritten to call sync_push.ps1, which does the same
REM conflict-aware 3-way comparison as sync_lib.sh (the Mac equivalent)
REM instead of blindly overwriting -- see sync_push.ps1's own comments for
REM why (it's what silently dropped Cade's profile-picture feature before
REM this fix).
REM
REM Run via double-click, or Win+R with this file's full path -- no arguments
REM needed. Progress + a final ALL_DONE / ALL_FAILED go to deploy_log.txt next
REM to this file.
REM
REM world_state.json and town.glb are still handled correctly without a
REM special-case exclusion: since 2026-07-08, grow_windows.ps1 writes those
REM two files straight into the git clone (via NEIGHBORHOOD_STATE_DIR) and
REM commits/pushes them to "main" itself, right after growing -- see
REM CLAUDE.md's iCloud race-condition writeup for why. sync_push.ps1's
REM conflict-aware comparison means that if this iCloud folder's copy of
REM those two files is stale relative to what grow_windows.ps1 already
REM pushed, it leaves the fresher pushed version alone instead of overwriting
REM it (the "REFRESHED_FROM_UPSTREAM" case in sync_push.ps1) -- so the old
REM hard-coded exclusion isn't needed anymore.
REM
REM NOTE: keep this file plain ASCII (no em-dashes/curly quotes) -- cmd.exe's
REM console codepage mangles non-ASCII characters in echoed text.

setlocal
set SRC=C:\Users\cadet\iCloudDrive\neighborhood
set LOG=%SRC%\deploy_log.txt

echo === deploy_website started %DATE% %TIME% === > "%LOG%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_push.ps1" -Branch main -Src "%SRC%" -CommitMessagePrefix "Update town" >> "%LOG%" 2>&1

findstr /C:"ALL_DONE" "%LOG%" >nul
if errorlevel 1 (
  echo ALL_FAILED >> "%LOG%"
) else (
  echo PUSHED -- Vercel will redeploy followville-kappa.vercel.app in ~1 minute >> "%LOG%"
)

echo.
echo Done -- see deploy_log.txt next to this script for the full result.
timeout /t 8
