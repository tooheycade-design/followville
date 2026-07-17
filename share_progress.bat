@echo off
REM LEGACY 2026-07-17: recovery/handoff only. Do not run during normal
REM repo-based growth; it can switch the clone to wip. Use reviewed Git work
REM from the authoritative repo instead.
REM Followville -- push your current work to the shared "wip" branch on
REM GitHub WITHOUT deploying it to the live site (that's deploy_website.bat's
REM job, and it only ever touches "main"). Run this whenever you want Zach
REM (or his AI) to be able to pull_latest.bat and see/build on what you've
REM got so far, before it's ready to go live.
REM
REM 2026-07-10: this used to do the copy/commit/push itself in batch with a
REM blind file-copy loop. Rewritten to call sync_push.ps1, which does the
REM same conflict-aware 3-way comparison as sync_lib.sh (the Mac equivalent)
REM instead of blindly overwriting -- see sync_push.ps1's own comments for
REM why (it's what silently dropped Cade's profile-picture feature before
REM this fix). Batch is bad at that kind of logic, same reason
REM grow_windows.bat delegates to grow_windows.ps1 for anything nontrivial.
REM
REM Run via double-click, or Win+R. Progress + a final ALL_DONE / ALL_FAILED
REM go to share_progress_log.txt next to this file.
REM
REM NOTE: keep this file plain ASCII (no em-dashes/curly quotes) -- cmd.exe's
REM console codepage mangles non-ASCII characters in echoed text.

setlocal
set SRC=C:\Users\cadet\iCloudDrive\neighborhood
set LOG=%SRC%\share_progress_log.txt

echo === share_progress started %DATE% %TIME% (branch: wip) === > "%LOG%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_push.ps1" -Branch wip -Src "%SRC%" -CommitMessagePrefix "WIP update" >> "%LOG%" 2>&1

findstr /C:"ALL_DONE" "%LOG%" >nul
if errorlevel 1 (
  echo ALL_FAILED >> "%LOG%"
)

echo.
echo Done -- see share_progress_log.txt next to this script for the full result.
if "%NEIGHBORHOOD_NO_PAUSE%"=="1" goto :eof
timeout /t 8
