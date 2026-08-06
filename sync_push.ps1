# sync_push.ps1 -- Windows port of sync_lib.sh's conflict-aware copy logic.
# Shared by share_progress.bat (-Branch wip) and deploy_website.bat (-Branch main).
#
# WHY THIS EXISTS (2026-07-10): share_progress.bat/deploy_website.bat used to
# blindly copy every git-tracked file from the iCloud folder over the repo
# clone, then commit and push whatever resulted -- no check for whether
# someone else had changed that same file since this machine last synced. On
# 2026-07-10 this silently dropped a profile-picture feature Cade had added
# to town.html: his local edit was never committed anywhere, and a later
# blind-copy push from the other side overwrote it with no warning at all.
# See sync_lib.sh (the Mac equivalent) for the full writeup and the same fix,
# ported here so both machines behave the same way.
#
# The fix: a real 3-way comparison per tracked file, using THIS CLONE'S OWN
# prior HEAD (captured before the fetch/reset that runs here) as the common
# ancestor -- the same thing `git merge` does natively, applied here because
# the iCloud folder itself isn't a git working tree.
#
# NOT YET VERIFIED ON AN ACTUAL WINDOWS MACHINE as of 2026-07-10 -- built and
# reasoned through the same way the rest of this project's Windows tooling
# was (see grow_windows.ps1's own history of that). Treat the first real run
# as a test. Keep this file plain ASCII -- see grow_windows.ps1's own note on
# why (PowerShell 5.1 without a BOM mis-decodes em-dashes/curly quotes).

param(
    [Parameter(Mandatory=$true)][ValidateSet('wip','main')][string]$Branch,
    [Parameter(Mandatory=$true)][string]$Src,
    [string]$Repo = "C:\Users\cadet\followville_repo",
    [string]$CommitMessagePrefix = "Update"
)

$ErrorActionPreference = "Stop"
$BinaryExt = @('.glb', '.png', '.jpg', '.jpeg', '.mp4', '.zip', '.blend', '.blend1')

function Invoke-Git {
    param([string[]]$GitArgs)
    $PrevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $result = & git @GitArgs 2>&1
    $script:LastGitExit = $LASTEXITCODE
    $ErrorActionPreference = $PrevEAP
    return ($result | Out-String)
}

function Files-Equal($a, $b) {
    if (-not (Test-Path -LiteralPath $a)) { return $false }
    if (-not (Test-Path -LiteralPath $b)) { return $false }
    return (Get-FileHash -LiteralPath $a -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $b -Algorithm SHA256).Hash
}

if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) {
    Write-Host "-- cloning repo (first run) --"
    git clone https://github.com/tooheycade-design/followville $Repo
}

Push-Location $Repo
try {
    Write-Host "-- git fetch --"
    Invoke-Git @('fetch', 'origin') | Out-Null

    # 2026-07-10 BUGFIX (see sync_lib.sh's matching note -- this hit Zach's
    # Mac the same day this script was written): must be this clone's own
    # LOCAL $Branch ref, captured after fetch but before the checkout/reset
    # below -- NOT `git rev-parse HEAD` taken right after clone, which lands
    # on the DEFAULT branch ("main"), not necessarily $Branch ("wip" or
    # "main"). Comparing local files against a base taken from the wrong
    # branch's history is exactly what silently reverted several files back
    # to an old wip-branch snapshot the first time this ran against a fresh
    # clone. Empty if this clone has never checked out $Branch before (fresh
    # clone, or first-ever push of this branch from this machine) --
    # the copy loop below then just trusts the local folder.
    $PrevCommit = (Invoke-Git @('rev-parse', $Branch)).Trim()
    if ($script:LastGitExit -ne 0) { $PrevCommit = "" }

    Write-Host "-- checkout $Branch --"
    $HasRemoteBranch = $true
    Invoke-Git @('rev-parse', '--verify', "origin/$Branch") | Out-Null
    if ($script:LastGitExit -ne 0) { $HasRemoteBranch = $false }

    if ($HasRemoteBranch) {
        Invoke-Git @('checkout', $Branch) | Out-Null
        if ($script:LastGitExit -ne 0) { Invoke-Git @('checkout', '-b', $Branch, "origin/$Branch") | Out-Null }
        Invoke-Git @('reset', '--hard', "origin/$Branch") | Out-Null
    }
    else {
        Invoke-Git @('checkout', 'main') | Out-Null
        Invoke-Git @('reset', '--hard', 'origin/main') | Out-Null
        Invoke-Git @('checkout', '-b', $Branch) | Out-Null
    }

    Write-Host "-- copying tracked files (conflict-aware) --"
    $Copied = 0
    $MergedFiles = @()
    $RefreshedFiles = @()
    $ConflictFiles = @()
    $TrackedFiles = (& git ls-files) -split "`n" | Where-Object { $_ -ne "" }

    foreach ($f in $TrackedFiles) {
        $srcPath = Join-Path $Src $f
        $repoPath = Join-Path $Repo $f
        if (-not (Test-Path -LiteralPath $srcPath)) { continue }

        if (-not (Test-Path -LiteralPath $repoPath)) {
            $dir = Split-Path $repoPath -Parent
            if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Copy-Item -LiteralPath $srcPath -Destination $repoPath -Force
            $Copied++
            continue
        }

        if (Files-Equal $srcPath $repoPath) { continue }

        if ([string]::IsNullOrEmpty($PrevCommit)) {
            # no known prior sync point (fresh clone) -- fall back to plain copy
            Copy-Item -LiteralPath $srcPath -Destination $repoPath -Force
            $Copied++
            continue
        }

        Invoke-Git @('cat-file', '-e', "${PrevCommit}:$f") | Out-Null
        if ($script:LastGitExit -ne 0) {
            # file did not exist at our last sync point either -- low risk
            Copy-Item -LiteralPath $srcPath -Destination $repoPath -Force
            $Copied++
            continue
        }

        $baseFile = [System.IO.Path]::GetTempFileName()
        $PrevEAP2 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & git show "${PrevCommit}:$f" 2>$null | Set-Content -LiteralPath $baseFile -Encoding Byte -ErrorAction SilentlyContinue
        # Set-Content -Encoding Byte on piped text output can mangle binary
        # content; for binary files we don't rely on base content anyway (see
        # the isBinary branch below), so this is only load-bearing for text.
        $ErrorActionPreference = $PrevEAP2

        $remoteUnchanged = Files-Equal $baseFile $repoPath
        if ($remoteUnchanged) {
            Copy-Item -LiteralPath $srcPath -Destination $repoPath -Force
            $Copied++
            Remove-Item -LiteralPath $baseFile -ErrorAction SilentlyContinue
            continue
        }

        $localUnchanged = Files-Equal $baseFile $srcPath
        if ($localUnchanged) {
            # upstream changed it, we did not -- take upstream's version, and
            # refresh our local iCloud copy so it stops being stale. Do NOT
            # overwrite the repo with our stale local copy -- this exact step
            # is what silently dropped Cade's profile-picture feature before
            # this fix.
            Copy-Item -LiteralPath $repoPath -Destination $srcPath -Force
            $RefreshedFiles += $f
            Remove-Item -LiteralPath $baseFile -ErrorAction SilentlyContinue
            continue
        }

        $ext = [System.IO.Path]::GetExtension($f).ToLower()
        if ($BinaryExt -contains $ext) {
            $ConflictFiles += $f
            Remove-Item -LiteralPath $baseFile -ErrorAction SilentlyContinue
            continue
        }

        $theirsFile = [System.IO.Path]::GetTempFileName()
        $oursFile = [System.IO.Path]::GetTempFileName()
        Copy-Item -LiteralPath $repoPath -Destination $theirsFile -Force
        Copy-Item -LiteralPath $srcPath -Destination $oursFile -Force

        $PrevEAP3 = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & git merge-file -q $oursFile $baseFile $theirsFile 2>$null
        $MergeExit = $LASTEXITCODE
        $ErrorActionPreference = $PrevEAP3

        if ($MergeExit -eq 0) {
            Copy-Item -LiteralPath $oursFile -Destination $repoPath -Force
            Copy-Item -LiteralPath $oursFile -Destination $srcPath -Force
            $Copied++
            $MergedFiles += $f
        }
        else {
            $ConflictFiles += $f
        }
        Remove-Item -LiteralPath $baseFile, $theirsFile, $oursFile -ErrorAction SilentlyContinue
    }

    # sync_push.ps1/sync_lib.sh themselves need to be tracked too, same
    # reasoning as the "new tooling" block in deploy_website.command
    foreach ($extra in @('sync_push.ps1', 'sync_lib.sh')) {
        $extraSrc = Join-Path $Src $extra
        if (Test-Path -LiteralPath $extraSrc) {
            Copy-Item -LiteralPath $extraSrc -Destination (Join-Path $Repo $extra) -Force
            Invoke-Git @('add', $extra) | Out-Null
        }
    }

    Write-Host "copied $Copied tracked files"
    if ($MergedFiles.Count -gt 0) { Write-Host ("AUTO_MERGED: " + ($MergedFiles -join ', ') + " (both sides changed these since last sync, but in non-overlapping places -- merged cleanly)") }
    if ($RefreshedFiles.Count -gt 0) { Write-Host ("REFRESHED_FROM_UPSTREAM: " + ($RefreshedFiles -join ', ') + " (local copy was stale and unchanged locally -- updated from the newer shared version)") }
    if ($ConflictFiles.Count -gt 0) {
        Write-Host ("CONFLICTS_DETECTED: " + ($ConflictFiles -join ', '))
        Write-Host "The file(s) above were changed on BOTH sides since the last sync and could not be auto-merged. They were left OUT of this push so nobody's work gets silently overwritten. Compare the iCloud copy against $Repo\<file>, decide what the merged result should be, save it to both, then re-run this script."
    }

    Invoke-Git @('add', '-A') | Out-Null
    & git diff --cached --quiet
    $NothingToCommit = ($LASTEXITCODE -eq 0)

    if ($NothingToCommit) {
        Write-Host "NOCHANGES -- $Branch already matches this folder"
    }
    else {
        $Msg = "$CommitMessagePrefix (pushed from Windows $(Get-Date -Format o))"
        Invoke-Git @('commit', '-m', $Msg) | Out-Null
        Invoke-Git @('push', 'origin', $Branch) | Out-Null
        if ($script:LastGitExit -ne 0) {
            Write-Host "PUSH_FAILED"
            exit 1
        }
        Write-Host "PUSHED to $Branch"
    }
    Write-Host "ALL_DONE"
}
finally {
    Pop-Location
}
