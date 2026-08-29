<#
.SYNOPSIS
    Build and smoke-test the Windows PyInstaller distribution.

.EXAMPLE
    .\scripts\build.ps1
    .\scripts\build.ps1 -Clean
#>
[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

if ($Clean) {
    foreach ($path in @((Join-Path $Root 'build'), (Join-Path $Root 'dist'))) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }
}

$FluidSynthBin = $env:SIEGFRIDI_FLUIDSYNTH_DIR
if (-not $FluidSynthBin -and (Test-Path -LiteralPath 'C:\tools\fluidsynth\bin')) {
    $FluidSynthBin = 'C:\tools\fluidsynth\bin'
}
if ($FluidSynthBin) {
    $env:SIEGFRIDI_FLUIDSYNTH_DIR = $FluidSynthBin
}

$ImportCheck = & $Python -c "import importlib.util; required = ('PyInstaller', 'basic_pitch', 'fluidsynth'); missing = [name for name in required if importlib.util.find_spec(name) is None]; import sys; sys.exit('Missing build dependencies: ' + ', '.join(missing)) if missing else None"
if ($LASTEXITCODE -ne 0) {
    throw 'Install the complete build environment with: python -m pip install -e ".[all]"'
}

$OrientalSoundFont = Join-Path $Root 'assets\packs\oriental-project-v0.1.sf2'
$OrientalManifest = Join-Path $Root 'assets\packs\oriental-project-v01.json'
Write-Host 'Generating the original CC0 Oriental Project SoundFont...'
& $Python (Join-Path $Root 'scripts\build-oriental-pack.py') --output $OrientalSoundFont --manifest $OrientalManifest
if ($LASTEXITCODE -ne 0) { throw 'Oriental Project SoundFont generation failed' }

$GothicSoundFont = Join-Path $Root 'assets\packs\dark-gothic-v0.1.sf2'
$GothicManifest = Join-Path $Root 'assets\packs\dark-gothic-v01.json'
Write-Host 'Generating the original CC0 Dark Gothic SoundFont...'
& $Python (Join-Path $Root 'scripts\build-gothic-pack.py') --output $GothicSoundFont --manifest $GothicManifest
if ($LASTEXITCODE -ne 0) { throw 'Dark Gothic SoundFont generation failed' }

$Spec = Join-Path $Root 'packaging\siegfridi.spec'
& $Python -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }

$Distribution = Join-Path $Root 'dist\Siegfridi'
$Executable = Join-Path $Distribution 'Siegfridi.exe'
if (-not (Test-Path -LiteralPath $Executable)) { throw "Missing packaged executable: $Executable" }

& $Python (Join-Path $Root 'scripts\write-package-manifest.py') $Distribution (Join-Path $Distribution 'package-manifest.json')
if ($LASTEXITCODE -ne 0) { throw 'Package manifest generation failed' }

$VersionOutput = & $Executable --version
if ($LASTEXITCODE -ne 0 -or $VersionOutput -notmatch '^0\.1\.0$') {
    throw "Packaged executable smoke test failed: $VersionOutput"
}
$PreviousQtPlatform = $env:QT_QPA_PLATFORM
$env:QT_QPA_PLATFORM = 'offscreen'
$UiSmoke = Start-Process -FilePath $Executable -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 10
    if ($UiSmoke.HasExited) {
        throw "Packaged UI smoke test exited early with code $($UiSmoke.ExitCode)"
    }
    $UiProcess = Get-Process -Id $UiSmoke.Id -ErrorAction Stop
    if (-not $UiProcess.Responding) {
        throw 'Packaged UI smoke test process is not responding'
    }
} finally {
    if (-not $UiSmoke.HasExited) {
        Stop-Process -Id $UiSmoke.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -eq $PreviousQtPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $PreviousQtPlatform
    }
}
$PackageReport = Join-Path $Root 'dist\Siegfridi-package-report.json'
& $Python (Join-Path $Root 'scripts\verify-package.py') $Distribution --version $VersionOutput --report $PackageReport
if ($LASTEXITCODE -ne 0) { throw 'Packaged directory verification failed' }
$Archive = Join-Path $Root ("dist\Siegfridi-{0}-win64.zip" -f $VersionOutput)
if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
Compress-Archive -Path $Distribution -DestinationPath $Archive -CompressionLevel Optimal
$ArchiveHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
$ReleaseReport = [ordered]@{
    application = 'siegfridi'
    version = $VersionOutput
    directory = 'Siegfridi'
    archive = [IO.Path]::GetFileName($Archive)
    archive_sha256 = $ArchiveHash
    package_report = [IO.Path]::GetFileName($PackageReport)
}
$ReleaseReport | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'dist\Siegfridi-release.json') -Encoding utf8
"$ArchiveHash  $([IO.Path]::GetFileName($Archive))" | Set-Content -LiteralPath (Join-Path $Root 'dist\Siegfridi-release.sha256') -Encoding ascii
Write-Host "Package ready: $Distribution" -ForegroundColor Green
Write-Host "Smoke test: siegfridi --version -> $VersionOutput" -ForegroundColor Green
Write-Host "Archive ready: $Archive" -ForegroundColor Green
Write-Host "Archive SHA-256: $ArchiveHash" -ForegroundColor Green
