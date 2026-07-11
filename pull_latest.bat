@echo off
REM Followville -- bring Zach's (or your own past session's) latest work from
REM GitHub into this iCloud folder. Run this FIRST, every session, before
REM editing anything. Companion to deploy_website.bat (pushes the other
REM direction, to main) and share_progress.bat (pushes WIP without deploying).
REM
REM Why this exists (2026-07-10): editing files directly in this iCloud
REM folder and trusting iCloud Drive itself to sync them to Zach's machine is
REM exactly what caused the repeated "numbered conflict copy" bugs documented
REM in CLAUDE.md, plus a nastier one on 2026-07-09: this folder's own .git
REM (on Zach's Mac) got corrupted by stale lock files that iCloud even synced
REM onto another machine. This script sidesteps all of that by using GitHub
REM as the sync layer instead of iCloud: it updates a plain, non-iCloud-synced
REM local clone (C:\Users\cadet\followville_repo, same one deploy_website.bat
REM uses) and copies the result INTO this folder. iCloud still syncs this
REM folder to Zach as always, but "did I get Zach's real latest work" is now
REM answered by git/GitHub, never by hoping iCloud's file rename won.
REM
REM Run via double-click (pulls "main"), or Win+R with an argument to pull a
REM different branch, e.g.:
REM   "C:\Users\cadet\iCloudDrive\neighborhood\pull_latest.bat" wip
REM Progress + a final ALL_DONE / ALL_FAILED go to pull_log.txt next to this
REM file.
REM
REM NOTE: keep this file plain ASCII (no em-dashes/curly quotes) -- cmd.exe's
REM console codepage mangles non-ASCII characters in echoed text.

setlocal
set SRC=C:\Users\cadet\iCloudDrive\neighborhood
set DST=C:\Users\cadet\followville_repo
set LOG=%SRC%\pull_log.txt
set BRANCH=%1
if "%BRANCH%"=="" set BRANCH=main

echo === pull_latest started %DATE% %TIME% (branch: %BRANCH%) === > "%LOG%"

if not exist "%DST%\.git" (
  echo -- cloning repo (first run) -- >> "%LOG%"
  git clone https://github.com/tooheycade-design/followville "%DST%" >> "%LOG%" 2>&1
)

cd /d "%DST%"
if errorlevel 1 (
  echo ERROR: could not cd into %DST% >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

echo -- git fetch -- >> "%LOG%"
git fetch origin >> "%LOG%" 2>&1

echo -- checkout %BRANCH% -- >> "%LOG%"
git checkout %BRANCH% >> "%LOG%" 2>&1
if errorlevel 1 (
  git checkout -b %BRANCH% origin/%BRANCH% >> "%LOG%" 2>&1
)
git reset --hard origin/%BRANCH% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: could not check out origin/%BRANCH% -- does that branch exist? >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

echo -- copying tracked files into this folder -- >> "%LOG%"
REM asks git itself what's tracked, same reasoning as deploy_website.bat's
REM 2026-07-10 fix -- never goes stale as new files get added to the repo.
for /f "delims=" %%F in ('git ls-files') do (
  if not exist "%SRC%\%%~pF" mkdir "%SRC%\%%~pF" >nul 2>&1
  copy /y "%DST%\%%F" "%SRC%\%%F" >> "%LOG%" 2>&1
)

echo ALL_DONE >> "%LOG%"
echo.
echo Done -- see pull_log.txt next to this script for the full result.
timeout /t 8
