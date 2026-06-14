param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo = "OctopusGarage/git-auto-sync"
$InstallDir = if ($env:GIT_AUTO_SYNC_DIR) { $env:GIT_AUTO_SYNC_DIR } else { Join-Path $HOME ".git-auto-sync" }
$BinDir = Join-Path $HOME ".local\bin"
$ConfigPath = Join-Path $HOME ".git-auto-sync\config.toml"
$Version = if ($env:GIT_AUTO_SYNC_VERSION) { $env:GIT_AUTO_SYNC_VERSION } else { "latest" }
$OriginalPath = $env:Path

function Info($Message) {
    Write-Host "=> $Message" -ForegroundColor Blue
}

function Fail($Message) {
    Write-Error "xx $Message"
    exit 1
}

# 1. uv
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Info "Installing uv..."
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    $PreviousUvInstallDir = $env:UV_INSTALL_DIR
    if (-not $env:UV_INSTALL_DIR) {
        $env:UV_INSTALL_DIR = $BinDir
    }
    try {
        Invoke-RestMethod "https://astral.sh/uv/install.ps1" | Invoke-Expression
    }
    finally {
        $env:UV_INSTALL_DIR = $PreviousUvInstallDir
    }
    $env:Path = "$BinDir;$env:Path"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Fail "uv install failed - see https://docs.astral.sh/uv/"
}
$UvBin = (Get-Command uv -ErrorAction Stop).Source

# 2. resolve the release tag from public GitHub releases
if ($Version -eq "latest") {
    try {
        $releaseHtml = Invoke-WebRequest -Uri "https://github.com/$Repo/releases/latest" -MaximumRedirection 10
        $escapedRepo = [regex]::Escape($Repo)
        $match = [regex]::Match($releaseHtml.Content, "/$escapedRepo/releases/tag/(v[0-9]+\.[0-9]+\.[0-9]+)")
        if (-not $match.Success) {
            Fail "Couldn't resolve the latest release tag from releases page."
        }
        $Tag = $match.Groups[1].Value
    }
    catch {
        Fail "Couldn't resolve the latest release tag."
    }
}
else {
    $Tag = $Version
}
if (-not $Tag.StartsWith("v")) {
    Fail "Couldn't resolve a release tag (got '$Tag')."
}

# 3. download + extract the release bundle into INSTALL_DIR.
$Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
try {
    Info "Downloading $Tag..."
    $Package = "git-auto-sync-$Tag-release.tar.gz"
    $Archive = Join-Path $Tmp "release.tar.gz"
    $ExtractDir = Join-Path $Tmp "extract"
    New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

    try {
        Invoke-WebRequest -Uri "https://github.com/$Repo/releases/download/$Tag/$Package" -OutFile $Archive
        if (Get-Command tar -ErrorAction SilentlyContinue) {
            tar -xzf $Archive -C $ExtractDir
        }
        else {
            throw "tar unavailable"
        }
    }
    catch {
        Info "Release bundle not found or incompatible. Falling back to source zip..."
        $ZipPath = Join-Path $Tmp "release.zip"
        Invoke-WebRequest -Uri "https://github.com/$Repo/archive/refs/tags/$Tag.zip" -OutFile $ZipPath
        Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
    }

    if (Test-Path -LiteralPath (Join-Path $InstallDir ".git")) {
        Remove-Item -LiteralPath (Join-Path $InstallDir ".git") -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $SourceDir = (Get-ChildItem -LiteralPath $ExtractDir -Directory | Select-Object -First 1).FullName
    Get-ChildItem -LiteralPath $SourceDir -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $InstallDir -Recurse -Force
    }
}
finally {
    Remove-Item -LiteralPath $Tmp -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. dependencies
Info "Syncing dependencies..."
Push-Location $InstallDir
try {
    & $UvBin sync
}
finally {
    Pop-Location
}

# 5. global launcher, so `git-auto-sync ...` works from anywhere
Info "Installing launcher to $BinDir\git-auto-sync.cmd..."
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$Launcher = Join-Path $BinDir "git-auto-sync.cmd"
$LauncherText = @"
@echo off
set "GIT_AUTO_SYNC_UV=$UvBin"
"$UvBin" run --project "$InstallDir" git-auto-sync %*
"@
Set-Content -LiteralPath $Launcher -Value $LauncherText -Encoding ASCII

if (($env:Path -split ";") -notcontains $BinDir) {
    $env:Path = "$BinDir;$env:Path"
}

# 6. guided setup. Non-interactive fallback runs: git-auto-sync init --yes
if (Test-Path -LiteralPath $ConfigPath) {
    Info "Existing config found at $ConfigPath; skipping guided setup."
    Info "Run 'git-auto-sync init' to reconfigure."
}
else {
    Info "Starting guided setup..."
    if ([Environment]::UserInteractive) {
        & $Launcher init
    }
    else {
        & $Launcher init --yes
    }
}

& $Launcher --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "Smoke check failed: git-auto-sync launcher is not executable."
}
Info "Smoke check passed: $(& $Launcher --version)"

Info "Done. Installed $Tag at $InstallDir"
Info "Update later with: git-auto-sync update"
if (($OriginalPath -split ";") -notcontains $BinDir) {
    Info "Add $BinDir to your PATH to use the 'git-auto-sync' command."
}
