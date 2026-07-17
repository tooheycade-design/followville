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

# 2026-07-17: the Git clone is the only executable source for code/state/web
# assets. The shared iCloud folder owns only the authoritative Blender scene.
# A generator beside the Blend is never executed or required because iCloud may
# rename it; the repository generator is the sole source. Override paths only
# for a deliberate machine setup.
$RepoDir = if ($env:FOLLOWVILLE_REPO_DIR) {
    $env:FOLLOWVILLE_REPO_DIR
} else {
    "C:\Users\cadet\followville_repo"
}
$SharedDir = if ($env:FOLLOWVILLE_SHARED_DIR) {
    $env:FOLLOWVILLE_SHARED_DIR
} else {
    "C:\Users\cadet\iCloudDrive\neighborhood"
}

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
$PreflightOnly = $false
$preflightIdx = $ArgList.IndexOf('--preflight-only')
if ($preflightIdx -ge 0) {
    $PreflightOnly = $true
    $ArgList.RemoveAt($preflightIdx)
}
$noGitIdx = $ArgList.IndexOf('--no-git')
if ($noGitIdx -ge 0) {
    Write-Host "ERROR: --no-git was retired. Followville growth must use the authoritative Git state."
    exit 1
}

if ($ArgList.Count -lt 1 -and -not $PreflightOnly) {
    Write-Host "Usage: grow_windows.bat +N | -N | =N | replay [options] [--preflight-only]"
    exit 1
}

$Change = if ($PreflightOnly -and $ArgList.Count -eq 0) { '<preflight>' } else { $ArgList[0] }
$Extra = @()
if ($ArgList.Count -gt 1) { $Extra = @($ArgList.GetRange(1, $ArgList.Count - 1)) }

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

function Assert-FollowvilleInputs([bool]$PullMain) {
    if (-not (Test-Path -LiteralPath $Blender -PathType Leaf)) {
        throw "Blender not found at: $Blender"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $RepoDir '.git'))) {
        throw "Authoritative repository is missing or is not a Git clone: $RepoDir"
    }

    $RepoGenerator = Join-Path $RepoDir 'neighborhood_blender.py'
    $RepoBlend = Join-Path $RepoDir 'neighborhood.blend'
    $SharedBlend = Join-Path $SharedDir 'neighborhood.blend'
    $Required = @(
        $RepoGenerator,
        (Join-Path $RepoDir 'export_web.py'),
        (Join-Path $RepoDir 'world_state.json'),
        (Join-Path $RepoDir 'town.glb'),
        (Join-Path $RepoDir 'town_manifest.json'),
        (Join-Path $RepoDir 'town_chunks\base.glb'),
        $RepoBlend,
        $SharedBlend
    )
    foreach ($file in $Required) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Missing required Followville file: $file"
        }
    }

    Push-Location $RepoDir
    try {
        $Branch = (Invoke-Git @('branch', '--show-current')).Trim()
        if ($script:LastGitExit -ne 0 -or $Branch -ne 'main') {
            throw "Production growth requires the repository on clean branch main; current branch is '$Branch'."
        }
        $TrackedStatus = (Invoke-Git @('status', '--porcelain', '--untracked-files=no')).Trim()
        if ($script:LastGitExit -ne 0 -or $TrackedStatus) {
            throw "Tracked repository changes are present. Commit or intentionally resolve them before growing; no files were changed."
        }
        if ($PullMain) {
            Log-Line "-- git pull --ff-only (authoritative repo, before growing) --"
            $PullOutput = Invoke-Git @('pull', '--ff-only', 'origin', 'main')
            $PullOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
            if ($script:LastGitExit -ne 0) {
                throw "git pull --ff-only failed. Resolve Git before any growth."
            }
        }
        $Head = (Invoke-Git @('rev-parse', 'HEAD')).Trim()
        $OriginMain = (Invoke-Git @('rev-parse', 'origin/main')).Trim()
        if (-not $Head -or $Head -ne $OriginMain) {
            throw "Local main does not match origin/main. Pull or resolve the branch before growing."
        }
    }
    finally {
        Pop-Location
    }

    $RepoBlendHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $RepoBlend).Hash
    $SharedBlendHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SharedBlend).Hash
    if ($RepoBlendHash -ne $SharedBlendHash) {
        throw "Repository and iCloud neighborhood.blend differ. Reconcile the authoritative scene before growing."
    }

    $env:FOLLOWVILLE_REPO_DIR = $RepoDir
    $env:NEIGHBORHOOD_REPO_DIR = $RepoDir
    $env:NEIGHBORHOOD_STATE_DIR = $RepoDir
    Log-Line "PREFLIGHT_OK repo=$RepoDir shared=$SharedDir commit=$Head"
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
        $StateFile = Join-Path $RepoDir 'world_state.json'
        $State = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
        if (-not $State.buildings -or @($State.buildings).Count -eq 0) {
            throw "world_state.json at $StateFile has no buildings (empty-default fallback? refusing to sync)"
        }
        $Headers = @{ apikey = $SbKey; Authorization = "Bearer $SbKey" }
        $Existing = Invoke-RestMethod -Uri ($SbUrl.TrimEnd('/') + '/rest/v1/houses?select=id&limit=100000') -Headers $Headers -Method Get
        $ExistingIds = @{}
        foreach ($row in @($Existing)) { $ExistingIds[[int64]$row.id] = $true }
        # keep in sync with NON_CLAIMABLE_TYPES in sync_houses.py
        $NonClaimable = @('pond', 'park', 'parkdistrict', 'lanestreet', 'plaza', 'streetlight', 'car', 'elementaryschool')
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
    Assert-FollowvilleInputs (-not $PreflightOnly)
    if ($PreflightOnly) {
        Log-Line "ALL_DONE"
        Write-Host "PREFLIGHT_OK"
        exit 0
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

    $BlendFile   = Join-Path $SharedDir 'neighborhood.blend'
    $GeneratorPy = Join-Path $RepoDir 'neighborhood_blender.py'
    $ExportPy    = Join-Path $RepoDir 'export_web.py'

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

    $GlbDir = $RepoDir
    if ($Output | Select-String -Pattern '^export_web\.py: wrote') {
        Log-Line ("WEB " + (Join-Path $GlbDir 'town.glb'))
        $RequiredWebAssets = @(
            (Join-Path $GlbDir 'town.glb'),
            (Join-Path $GlbDir 'town_manifest.json'),
            (Join-Path $GlbDir 'town_chunks\base.glb')
        )
        foreach ($WebAsset in $RequiredWebAssets) {
            if (-not (Test-Path -LiteralPath $WebAsset -PathType Leaf)) {
                throw "Web export reported success but required asset is missing: $WebAsset"
            }
        }
    }
    else {
        throw "WEB_EXPORT_FAILED -- export_web.py did not confirm a complete export"
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

    Log-Line "-- git add/commit/push (state + full/streamed town assets) --"
    Push-Location $RepoDir
    try {
        $AddOutput = Invoke-Git @('add', 'world_state.json', 'town.glb', 'town_manifest.json', 'town_chunks')
        $AddOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
        if ($script:LastGitExit -ne 0) {
            throw "git add failed after growing. State/assets remain local; resolve Git before another growth."
        }

        $PrevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & git diff --cached --quiet
        $DiffExit = $LASTEXITCODE
        $ErrorActionPreference = $PrevEAP
        if ($DiffExit -gt 1) {
            throw "git diff failed after staging growth assets. Resolve Git before another growth."
        }
        $NothingToCommit = ($DiffExit -eq 0)

        if ($NothingToCommit) {
            Log-Line "NOCHANGES -- state and town assets already match the last commit"
        }
        else {
            $CommitMsg = "Grow: $Change (auto-committed by grow_windows.ps1 $(Get-Date -Format o))"
            $CommitOutput = Invoke-Git @('commit', '-m', $CommitMsg)
            $CommitOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
            if ($script:LastGitExit -ne 0) {
                throw "git commit failed after growing. State/assets remain staged; resolve Git before another growth."
            }
            $PushOutput = Invoke-Git @('push', 'origin', 'main')
            $PushOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
            if ($script:LastGitExit -ne 0) {
                throw "git push failed after growing -- state/assets are committed locally. Resolve the push before another growth."
            }
            Log-Line "PUSHED $CommitMsg"
        }
    }
    finally {
        Pop-Location
    }

    Log-Line "-- houses table sync (claimable homes, see CLAIMING_SETUP.md) --"
    Sync-Houses

    Log-Line "HANDOFF_SYNC_SKIPPED (authoritative main already contains the growth assets)"

    Log-Line "ALL_DONE"
}
catch {
    Log-Line ("ERROR: " + $_.Exception.Message)
    Log-Line "ALL_FAILED"
    exit 1
}
