@echo off
REM Followville -- push your current work to the shared "wip" branch on
REM GitHub WITHOUT deploying it to the live site (that's deploy_website.bat's
REM job, and it only ever touches "main"). Run this whenever you want Zach
REM (or his AI) to be able to pull_latest.bat and see/build on what you've
REM got so far, before it's ready to go live.
REM
REM Same underlying machinery as deploy_website.bat and pull_latest.bat (the
REM non-iCloud clone at C:\Users\cadet\followville_repo) -- see
REM pull_latest.bat's comment for why that matters.
REM
REM Run via double-click, or Win+R. Progress + a final ALL_DONE / ALL_FAILED
REM go to share_progress_log.txt next to this file.
REM
REM NOTE: keep this file plain ASCII (no em-dashes/curly quotes) -- cmd.exe's
REM console codepage mangles non-ASCII characters in echoed text.

setlocal
set SRC=C:\Users\cadet\iCloudDrive\neighborhood
set DST=C:\Users\cadet\followville_repo
set LOG=%SRC%\share_progress_log.txt
set BRANCH=wip

echo === share_progress started %DATE% %TIME% (branch: %BRANCH%) === > "%LOG%"

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

echo -- checkout %BRANCH% (branching from origin/main if it does not exist yet) -- >> "%LOG%"
git rev-parse --verify origin/%BRANCH% >nul 2>&1
if errorlevel 1 (
  git checkout main >> "%LOG%" 2>&1
  git reset --hard origin/main >> "%LOG%" 2>&1
  git checkout -b %BRANCH% >> "%LOG%" 2>&1
) else (
  git checkout %BRANCH% >> "%LOG%" 2>&1
  if errorlevel 1 git checkout -b %BRANCH% origin/%BRANCH% >> "%LOG%" 2>&1
  git reset --hard origin/%BRANCH% >> "%LOG%" 2>&1
)

echo -- copying tracked files from iCloud folder -- >> "%LOG%"
for /f "delims=" %%F in ('git ls-files') do (
  if exist "%SRC%\%%F" copy /y "%SRC%\%%F" "%DST%\%%F" >> "%LOG%" 2>&1
)

echo -- git add -- >> "%LOG%"
git add -A >> "%LOG%" 2>&1

git diff --cached --quiet
if %errorlevel%==0 (
  echo NOCHANGES -- wip already matches this folder >> "%LOG%"
  echo ALL_DONE >> "%LOG%"
  goto :eof
)

set MSG=WIP update (pushed from Cade's PC, not deployed)

echo -- git commit -- >> "%LOG%"
git commit -m "%MSG%" >> "%LOG%" 2>&1

echo -- git push -- >> "%LOG%"
git push origin %BRANCH% >> "%LOG%" 2>&1
if errorlevel 1 (
  echo PUSH_FAILED >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

echo PUSHED to %BRANCH% -- NOT live, Zach can pull_latest.bat wip to see it >> "%LOG%"
echo ALL_DONE >> "%LOG%"
echo.
echo Done -- see share_progress_log.txt next to this script for the full result.
timeout /t 8
