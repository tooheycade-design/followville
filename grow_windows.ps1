# Follower Neighborhood -- Windows headless growth runner (does the real work).
# Called by grow_windows.bat -- you normally don't run this file directly.
#
# Mirrors grow.sh exactly: same argument syntax, same "generator + web export in
# ONE Blender session" approach, same RESULT/STILL/VIDEO/WEB output lines, same
# "copy newest render to Desktop" behavior. Runs Blender with --background, so
# no GUI ever opens and nothing can be accidentally clicked/typed into it.
#
# Progress + full Blender output goes to grow_log.txt (or --log <name> if given,
# e.g. for multi-shot days like the Mac --tag convention) next to this script.
# The log's last line is ALL_DONE on success or ALL_FAILED on error -- matching
# this project's existing "cheap-model watches the log file, don't poll with
# the expensive model" convention (see CLAUDE.md).
#
# Deliberately has NO param() block: the first argument is often something
# like "-3", and PowerShell's normal parameter binder tries to interpret any
# dash-prefixed token as a named parameter before falling back to positional
# binding -- which breaks for values like "-3". Reading directly from $args
# sidesteps that entirely; nothing here is ever parsed as a named parameter.
#
# NOTE: this file must stay plain ASCII. Windows PowerShell 5.1 (not the newer
# pwsh Core) reads .ps1 files without a BOM using the legacy system codepage,
# so "fancy" characters like em-dashes or curly quotes get mis-decoded and can
# break string literals (hit this exact bug once already -- see WEB_VIEWER_
# CHANGELOG.md / TEAM_LOG.md 2026-07-07 entries). Stick to -- and "straight"
# quotes only.

$ErrorActionPreference = "Stop"
$Dir = $PSScriptRoot
$Blender = "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"

# 2026-07-08: world_state.json + town.glb now live authoritatively in the git
# repo clone, not in this iCloud-synced folder -- Blender reads/writes them
# there directly via NEIGHBORHOOD_STATE_DIR (see state_path() in
# neighborhood_blender.py / export_web.py). This is the real fix for the
# repeated iCloud sync race (world_state.json's plain filename randomly
# getting renamed to a numbered conflict copy mid-session -- see CLAUDE.md).
# git doesn't have that failure mode: a "git pull" either gets you the latest
# committed state or fails loudly, it never silently hands you an empty file.
# Pass --no-git to fall back to the old behavior (state next to the .blend,
# in this iCloud folder, no git pull/push) if this ever needs troubleshooting.
$RepoDir = "C:\Users\cadet\followville_repo"

# pull an optional "--log <name>" out of $args by hand; everything else passes
# straight through to Blender untouched, in original order
$ArgList = [System.Collections.ArrayList]::new()
$ArgList.AddRange([string[]]$args)
$LogName = "grow_log.txt"
$logIdx = $ArgList.IndexOf('--log')
if ($logIdx -ge 0 -and $logIdx -lt $ArgList.Count - 1) {
    $LogName = $ArgList[$logIdx + 1]
    $ArgList.RemoveAt($logIdx + 1)
    $ArgList.RemoveAt($logIdx)
}
$UseGit = $true
$noGitIdx = $ArgList.IndexOf('--no-git')
if ($noGitIdx -ge 0) {
    $UseGit = $false
    $ArgList.RemoveAt($noGitIdx)
}

if ($ArgList.Count -lt 1) {
    Write-Host "Usage: grow_windows.bat +N | -N | =N | replay [--render|--still|--apartments N|--parks N|--trees N|--followers N] [--log NAME]"
    exit 1
}

$Change = $ArgList[0]
$Extra = @()
if ($ArgList.Count -gt 1) { $Extra = $ArgList.GetRange(1, $ArgList.Count - 1) }

$LogFile = Join-Path $Dir $LogName

function Log-Line([string]$line) {
    $line | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# git writes ordinary progress info to stderr (e.g. "From https://github.com/...",
# push summaries) -- with $ErrorActionPreference = "Stop" (set above), merging
# stderr via 2>&1 turns each such line into a terminating error the instant
# it's touched, even though git itself succeeded. Same bug class already fixed
# for the Blender call below; every git invocation needs the same treatment.
# Returns the combined output as a single string; sets $script:LastGitExit.
function Invoke-Git {
    param([string[]]$GitArgs)
    $PrevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $result = & git @GitArgs 2>&1
    $script:LastGitExit = $LASTEXITCODE
    $ErrorActionPreference = $PrevEAP
    return ($result | Out-String)
}

# 2026-07-09: claimable-homes feature (see CLAIMING_SETUP.md). After a growth
# day, every new building in world_state.json must also become a row in the
# Supabase `houses` table or it can never be claimed on the site. This is the
# "don't forget to wire step B into the pipeline" step -- done in PowerShell
# (not Python) so it adds zero new dependencies on this PC. Insert-only: rows
# already in the table are never touched, so manual `claimable` edits survive.
# Skipped harmlessly until supabase_sync.env exists next to this script.
# A failure here does NOT fail the run (the town itself grew + pushed fine),
# but logs HOUSES_SYNC_FAILED loudly -- log watchers should check for it.
function Sync-Houses {
    $EnvFile = Join-Path $Dir 'supabase_sync.env'
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Log-Line "HOUSES_SYNC_SKIPPED (no supabase_sync.env -- claimable-homes sync not configured)"
        return
    }
    try {
        $Cfg = @{}
        Get-Content -LiteralPath $EnvFile | ForEach-Object {
            $t = $_.Trim()
            if ($t -and -not $t.StartsWith('#') -and $t.Contains('=')) {
                $kv = $t.Split('=', 2)
                $Cfg[$kv[0].Trim()] = $kv[1].Trim()
            }
        }
        $SbUrl = $Cfg['SUPABASE_URL']
        $SbKey = $Cfg['SUPABASE_SERVICE_ROLE_KEY']
        if (-not $SbUrl -or -not $SbKey) {
            throw "supabase_sync.env is missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
        }
        $StateDir = if ($UseGit) { $RepoDir } else { $Dir }
        $StateFile = Join-Path $StateDir 'world_state.json'
        $State = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
        if (-not $State.buildings -or @($State.buildings).Count -eq 0) {
            throw "world_state.json at $StateFile has no buildings (empty-default fallback? refusing to sync)"
        }
        $Headers = @{ apikey = $SbKey; Authorization = "Bearer $SbKey" }
        $Existing = Invoke-RestMethod -Uri ($SbUrl.TrimEnd('/') + '/rest/v1/houses?select=id&limit=100000') -Headers $Headers -Method Get
        $ExistingIds = @{}
        foreach ($row in @($Existing)) { $ExistingIds[[int64]$row.id] = $true }
        # keep in sync with NON_CLAIMABLE_TYPES in sync_houses.py
        $NonClaimable = @('pond', 'park', 'parkdistrict', 'lanestreet', 'plaza', 'streetlight', 'car')
        $NewRows = @()
        foreach ($b in $State.buildings) {
            if ($ExistingIds.ContainsKey([int64]$b.seed)) { continue }
            $DayBuilt = 0
            if ($b.PSObject.Properties['day']) { $DayBuilt = $b.day }
            $NewRows += [pscustomobject]@{
                id            = [int64]$b.seed
                gx            = $b.gx
                gy            = $b.gy
                building_type = $b.type
                day_built     = $DayBuilt
                claimable     = ($NonClaimable -notcontains $b.type)
            }
        }
        if (@($NewRows).Count -eq 0) {
            Log-Line ("HOUSES_SYNC_OK (inserted 0 -- already up to date, " + @($State.buildings).Count + " buildings)")
            return
        }
        # -InputObject with an explicit @() keeps a 1-element array serialized
        # as a JSON array (plain piping into ConvertTo-Json would unwrap it)
        $Body = ConvertTo-Json -InputObject @($NewRows) -Depth 4
        $PostHeaders = @{ apikey = $SbKey; Authorization = "Bearer $SbKey"; Prefer = 'resolution=ignore-duplicates,return=minimal' }
        Invoke-RestMethod -Uri ($SbUrl.TrimEnd('/') + '/rest/v1/houses?on_conflict=id') -Headers $PostHeaders -Method Post -ContentType 'application/json' -Body $Body | Out-Null
        Log-Line ("HOUSES_SYNC_OK (inserted " + @($NewRows).Count + ", " + @($State.buildings).Count + " total buildings in world_state)")
    }
    catch {
        Log-Line ("HOUSES_SYNC_FAILED " + $_.Exception.Message)
        Log-Line "WARNING: the town grew and pushed fine, but the claimable-homes database was NOT updated -- new houses won't be claimable on the site. Fix and run: python sync_houses.py (or re-run a replay) -- see CLAIMING_SETUP.md."
    }
}

"=== grow_windows.ps1 started $(Get-Date -Format o) ===" | Out-File -FilePath $LogFile -Encoding utf8
Log-Line "Change requested: $Change"
if ($Extra.Count -gt 0) { Log-Line ("Extra args: " + ($Extra -join ' ')) }

try {
    if (-not (Test-Path -LiteralPath $Blender)) {
        throw "Blender not found at: $Blender (edit the `$Blender path near the top of grow_windows.ps1 if it moved or was upgraded)"
    }

    if ($UseGit) {
        if (-not (Test-Path -LiteralPath (Join-Path $RepoDir '.git'))) {
            throw "$RepoDir is not a git clone -- run clone_repo.bat first, or pass --no-git to use the old iCloud-folder-only behavior."
        }
        Log-Line "-- git pull (repo clone, before growing) --"
        Push-Location $RepoDir
        $PullOutput = Invoke-Git @('pull', 'origin', 'main')
        Pop-Location
        $PullOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
        if ($script:LastGitExit -ne 0) {
            throw "git pull failed in $RepoDir -- see $LogFile. Not safe to grow on top of a state we might not have the latest copy of; resolve the git issue first (or pass --no-git for the old behavior)."
        }
        $env:NEIGHBORHOOD_STATE_DIR = $RepoDir
    }
    else {
        Remove-Item Env:\NEIGHBORHOOD_STATE_DIR -ErrorAction SilentlyContinue
    }

    switch -Regex ($Change) {
        '^\+(\d+)$' { $Flags = @('--gained', $Matches[1]) }
        '^-(\d+)$'  { $Flags = @('--lost', $Matches[1]) }
        '^=(\d+)$'  { $Flags = @('--pop', $Matches[1]) }
        '^replay$'  { $Flags = @('--replay') }
        default {
            throw "Usage: grow_windows.bat +N | -N | =N | replay [--render|--still|--apartments N|--parks N|--trees N|--followers N]"
        }
    }

    $BlendFile   = Join-Path $Dir 'neighborhood.blend'
    $GeneratorPy = Join-Path $Dir 'neighborhood_blender.py'
    $ExportPy    = Join-Path $Dir 'export_web.py'

    foreach ($f in @($BlendFile, $GeneratorPy, $ExportPy)) {
        if (-not (Test-Path -LiteralPath $f)) { throw "Missing required file: $f" }
    }

    # generator + web export in ONE Blender session, so the export always sees
    # the freshly rebuilt world -- never the stale scene saved inside the .blend
    $AllArgs = @(
        '--background', $BlendFile,
        '--python', $GeneratorPy,
        '--python', $ExportPy,
        '--'
    ) + $Flags + $Extra

    Log-Line ("Running: `"$Blender`" " + ($AllArgs -join ' '))

    # Blender/Python print harmless warnings (e.g. DeprecationWarning) to
    # stderr. With $ErrorActionPreference = "Stop" (set above), merging
    # stderr via 2>&1 turns each such line into a terminating PowerShell
    # error the moment it's touched -- aborting the whole script even though
    # Blender itself hasn't failed. Relax it just for this one call, then
    # restore it so our own throw/catch logic below still works as intended.
    $PrevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $Output = & $Blender @AllArgs 2>&1
    $BlenderExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PrevEAP

    $Output | Out-String | Out-File -FilePath $LogFile -Append -Encoding utf8

    if ($BlenderExitCode -ne 0) {
        Log-Line "BLENDER_EXIT_CODE $BlenderExitCode"
        throw "Blender exited with code $BlenderExitCode -- see $LogFile"
    }

    $ResultLines = $Output | Select-String -Pattern '^(RESULT|STILL|VIDEO)\b'
    if (-not $ResultLines) {
        throw "No RESULT/STILL/VIDEO line in Blender output -- see $LogFile"
    }
    $ResultLines | ForEach-Object { Log-Line $_.Line }

    $GlbDir = if ($UseGit) { $RepoDir } else { $Dir }
    if ($Output | Select-String -Pattern '^export_web\.py: wrote') {
        Log-Line ("WEB " + (Join-Path $GlbDir 'town.glb'))
    }
    else {
        Log-Line "WEB_EXPORT_FAILED"
    }

    if ($Output | Select-String -Pattern '^VIDEO') {
        $RendersDir = Join-Path $Dir 'renders'
        $Newest = Get-ChildItem -Path $RendersDir -Filter *.mp4 -ErrorAction SilentlyContinue |
                  Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($Newest) {
            $DesktopDir = [Environment]::GetFolderPath('Desktop')
            Copy-Item -Path $Newest.FullName -Destination $DesktopDir -Force
            Log-Line ("DESKTOP " + (Join-Path $DesktopDir $Newest.Name))
        }
    }

    if ($UseGit) {
        Log-Line "-- git add/commit/push (world_state.json + town.glb) --"
        Push-Location $RepoDir
        (Invoke-Git @('add', 'world_state.json', 'town.glb')) | Out-File -FilePath $LogFile -Append -Encoding utf8

        $PrevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & git diff --cached --quiet
        $NothingToCommit = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $PrevEAP

        if ($NothingToCommit) {
            Log-Line "NOCHANGES -- world_state.json/town.glb already match the last commit"
        }
        else {
            $CommitMsg = "Grow: $Change (auto-committed by grow_windows.ps1 $(Get-Date -Format o))"
            (Invoke-Git @('commit', '-m', $CommitMsg)) | Out-File -FilePath $LogFile -Append -Encoding utf8
            $PushOutput = Invoke-Git @('push', 'origin', 'main')
            $PushOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
            if ($script:LastGitExit -ne 0) {
                Pop-Location
                throw "git push failed after growing -- world_state.json/town.glb are committed LOCALLY in $RepoDir but not pushed. See $LogFile, then push manually once fixed (e.g. network/auth issue) -- do not re-run a growth day on top of this without resolving it first."
            }
            Log-Line "PUSHED $CommitMsg"
        }
        Pop-Location
    }

    Log-Line "-- houses table sync (claimable homes, see CLAIMING_SETUP.md) --"
    Sync-Houses

    # 2026-07-10: auto-share progress to wip after every successful growth run,
    # mirroring grow.sh's matching block (see CLAUDE.md's Collaboration
    # section). world_state.json/town.glb are already pushed straight to main
    # above via NEIGHBORHOOD_STATE_DIR, so share_progress.bat only needs to
    # carry the OTHER tracked files (docs/code) -- it was fixed on 2026-07-10
    # to skip those two files for exactly that reason. Best-effort: a failure
    # here does NOT fail this growth run, since the town itself already grew
    # and (if -UseGit) pushed successfully above.
    $ShareScript = Join-Path $Dir 'share_progress.bat'
    if (Test-Path -LiteralPath $ShareScript) {
        Log-Line "-- auto-sharing progress to wip --"
        $PrevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & cmd.exe /c "`"$ShareScript`"" 2>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
        $ShareExit = $LASTEXITCODE
        $ErrorActionPreference = $PrevEAP
        if ($ShareExit -ne 0) {
            Log-Line "AUTO_SHARE_FAILED -- growth itself succeeded and was saved; see share_progress_log.txt"
        }
    }
    else {
        Log-Line "AUTO_SHARE_SKIPPED (share_progress.bat not found)"
    }

    Log-Line "ALL_DONE"
}
catch {
    Log-Line ("ERROR: " + $_.Exception.Message)
    Log-Line "ALL_FAILED"
    exit 1
}
