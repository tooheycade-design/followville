# Follower Neighborhood -- tiny local web server, for previewing index.html /
# town.html on this machine. Called by preview_website.bat.
#
# Why this exists: the site uses fetch() to load world_state.json and
# town.glb, and browsers block fetch() against file:// URLs (see CLAUDE.md's
# "Web viewer" section). Needs a real http:// origin. Uses .NET's
# HttpListener directly so there's no dependency on Python or Node being
# installed -- just plain Windows PowerShell, which is already confirmed
# present on this machine.
#
# Auto-stops after $TimeoutMinutes so a forgotten server doesn't run forever.
# Refresh the browser after a new grow.sh / grow_windows.bat run to see the
# updated town -- no need to restart this server, it just serves whatever is
# currently on disk.
#
# NOTE: keep this file plain ASCII (see grow_windows.ps1 for why -- Windows
# PowerShell 5.1 misreads non-ASCII characters in a BOM-less .ps1 file).

$Dir = $PSScriptRoot
$Port = 8000
$TimeoutMinutes = 20

# 2026-07-08: world_state.json and town.glb now live authoritatively in the
# git repo clone (see grow_windows.ps1's NEIGHBORHOOD_STATE_DIR change), not
# necessarily here in the iCloud folder anymore. Serve those two specific
# files from the repo clone if they exist there, so local preview still shows
# the real current state after a grow_windows.bat run; everything else
# (index.html, town.html, etc.) still serves from $Dir as before.
$RepoDir = "C:\Users\cadet\followville_repo"
$RepoOverrideFiles = @("world_state.json", "town.glb")

$Mime = @{
    ".html" = "text/html"
    ".htm"  = "text/html"
    ".js"   = "application/javascript"
    ".json" = "application/json"
    ".glb"  = "model/gltf-binary"
    ".gltf" = "model/gltf+json"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".jpeg" = "image/jpeg"
    ".ico"  = "image/x-icon"
    ".mp4"  = "video/mp4"
}

$Listener = New-Object System.Net.HttpListener
$Listener.Prefixes.Add("http://localhost:$Port/")
try {
    $Listener.Start()
}
catch {
    Write-Host "Could not start server on port $Port -- it may already be in use."
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host "Serving $Dir"
Write-Host "Open http://localhost:$Port/ in a browser (auto-opens if launched via preview_website.bat)."
Write-Host "Auto-stops in $TimeoutMinutes minutes. Close this window to stop it sooner."
Write-Host ""

$Deadline = (Get-Date).AddMinutes($TimeoutMinutes)

while ($Listener.IsListening -and (Get-Date) -lt $Deadline) {
    $ContextTask = $Listener.GetContextAsync()
    while (-not $ContextTask.AsyncWaitHandle.WaitOne(500)) {
        if ((Get-Date) -ge $Deadline) { break }
    }
    if (-not $ContextTask.IsCompleted) { continue }

    $Context = $ContextTask.Result
    $Request = $Context.Request
    $Response = $Context.Response

    try {
        $LocalPath = [Uri]::UnescapeDataString($Request.Url.LocalPath)
        if ($LocalPath -eq "/") { $LocalPath = "/index.html" }
        $RelativePath = $LocalPath.TrimStart("/") -replace "/", "\"
        $FilePath = Join-Path $Dir $RelativePath
        $FullDir = (Resolve-Path $Dir).Path

        if ($RepoOverrideFiles -contains $RelativePath) {
            $RepoFilePath = Join-Path $RepoDir $RelativePath
            if (Test-Path -LiteralPath $RepoFilePath -PathType Leaf) {
                $FilePath = $RepoFilePath
                $FullDir = (Resolve-Path $RepoDir).Path
            }
        }

        if ((Test-Path -LiteralPath $FilePath -PathType Leaf) -and
            ((Resolve-Path $FilePath).Path).StartsWith($FullDir)) {
            $Ext = [System.IO.Path]::GetExtension($FilePath).ToLower()
            $ContentType = $Mime[$Ext]
            if (-not $ContentType) { $ContentType = "application/octet-stream" }
            $Bytes = [System.IO.File]::ReadAllBytes($FilePath)
            $Response.ContentType = $ContentType
            $Response.ContentLength64 = $Bytes.Length
            $Response.OutputStream.Write($Bytes, 0, $Bytes.Length)
            Write-Host "200 $LocalPath"
        }
        else {
            $Response.StatusCode = 404
            $NotFound = [System.Text.Encoding]::UTF8.GetBytes("404 Not Found: $LocalPath")
            $Response.OutputStream.Write($NotFound, 0, $NotFound.Length)
            Write-Host "404 $LocalPath"
        }
    }
    catch {
        Write-Host ("ERROR serving " + $Request.Url + ": " + $_.Exception.Message)
        try {
            $Response.StatusCode = 500
        } catch {}
    }
    finally {
        $Response.OutputStream.Close()
    }
}

$Listener.Stop()
Write-Host "Server stopped."
