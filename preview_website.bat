@echo off
REM Follower Neighborhood -- local website preview.
REM Starts a tiny local HTTP server (plain PowerShell, no Python/Node needed)
REM and opens the site in your default browser, so fetch() of
REM world_state.json and town.glb works (browsers block fetch() over
REM file://, see CLAUDE.md's "Web viewer" section).
REM
REM Run via double-click, or Win+R with this file's full path -- no
REM arguments needed. A second console window opens for the server itself
REM (title "Followville local server"); it auto-stops after 20 minutes, or
REM close that window to stop it sooner.
REM
REM After a new grow.sh / grow_windows.bat run, just refresh the browser --
REM no need to restart this server, it serves whatever's currently on disk.

start "Followville local server" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0preview_website.ps1"
timeout /t 2 >nul
start "" http://localhost:8000/index.html
