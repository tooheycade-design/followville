@echo off
REM Follower Neighborhood -- Windows growth runner (headless, no Blender GUI).
REM SAFE SOURCE SPLIT (2026-07-17): code/state/assets always come from the Git
REM repo; the authoritative neighborhood.blend comes from the shared iCloud
REM folder. The PowerShell preflight refuses stale/missing mirrors before
REM Blender starts. The retired --no-git/iCloud-only mode is not supported.
REM Windows equivalent of grow.sh. Same syntax as the Mac version:
REM
REM   grow_windows.bat +5              add 5 houses (5 followers gained)
REM   grow_windows.bat -3              remove 3 houses (3 followers lost)
REM   grow_windows.bat =50             set TOTAL population to 50
REM   grow_windows.bat replay          re-animate the last day, change nothing
REM
REM Extras (append after the number, same as grow.sh):
REM   --render                  render the day's 9:16 video
REM   --still                   render a single preview PNG instead
REM   --apartments N | --parks N | --trees N | --special TYPEhouse[@gx,gy]
REM   --followers N             population change differs from house count
REM   --cam overhead | --tag NAME | --time day|sunset|night | --season X
REM   --hero | --celebrate
REM   --preflight-only          validate paths/Git/mirrors; do not run Blender
REM
REM HOW TO RUN WITHOUT TYPING IN A TERMINAL WINDOW:
REM   Press Win+R, then type (or paste) something like:
REM     "C:\Users\cadet\followville_repo\grow_windows.bat" +5 --render
REM   and press Enter. A console window will open and run Blender headlessly --
REM   nothing to click inside it. Progress + full output goes to grow_log.txt
REM   next to this script; its last line is ALL_DONE when finished (or
REM   ALL_FAILED if something went wrong) -- check that file rather than
REM   watching the console.
REM
REM This just forwards everything to grow_windows.ps1 (PowerShell handles the
REM actual logic -- argument parsing, running Blender, log parsing).
REM
REM NOTE: keep this file plain ASCII (no em-dashes/curly quotes) -- cmd.exe's
REM console codepage mangles non-ASCII characters in echoed text.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0grow_windows.ps1" %*

echo.
echo Done -- see grow_log.txt next to this script for the full result.
REM timeout instead of pause on purpose: pause waits for a keypress, which
REM blocks forever if this was launched non-interactively (e.g. by an AI
REM driving the screen rather than a human at the keyboard). This just gives
REM a human a few seconds to read the console before it closes on its own.
timeout /t 8
