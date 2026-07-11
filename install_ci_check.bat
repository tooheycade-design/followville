@echo off
REM Installs the town.glb sanity-check script + its GitHub Action into the
REM actual git repo clone, then commits and pushes so GitHub picks it up.
setlocal
set SRC=C:\Users\cadet\iCloudDrive\neighborhood
set DST=C:\Users\cadet\followville_repo
set LOG=%SRC%\install_ci_check_log.txt

echo === install_ci_check started %DATE% %TIME% === > "%LOG%"

if not exist "%DST%\.git" (
  echo ERROR: %DST% is not a git clone. >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

cd /d "%DST%"

echo -- git pull -- >> "%LOG%"
git pull origin main >> "%LOG%" 2>&1

if not exist "%DST%\.github" mkdir "%DST%\.github"
if not exist "%DST%\.github\workflows" mkdir "%DST%\.github\workflows"

echo -- copying check script + workflow -- >> "%LOG%"
copy /y "%SRC%\check_town_glb.py" "%DST%\check_town_glb.py" >> "%LOG%" 2>&1
copy /y "%SRC%\check_town_glb.yml" "%DST%\.github\workflows\check_town_glb.yml" >> "%LOG%" 2>&1

echo -- git add -- >> "%LOG%"
git add check_town_glb.py .github\workflows\check_town_glb.yml >> "%LOG%" 2>&1

git diff --cached --quiet
if %errorlevel%==0 (
  echo NOCHANGES >> "%LOG%"
  echo ALL_DONE >> "%LOG%"
  goto :eof
)

echo -- git commit -- >> "%LOG%"
git commit -m "Add town.glb CI sanity check (GitHub Action safety net)" >> "%LOG%" 2>&1

echo -- git push -- >> "%LOG%"
git push origin main >> "%LOG%" 2>&1
if errorlevel 1 (
  echo PUSH_FAILED >> "%LOG%"
  echo ALL_FAILED >> "%LOG%"
  goto :eof
)

echo PUSHED >> "%LOG%"
echo ALL_DONE >> "%LOG%"
