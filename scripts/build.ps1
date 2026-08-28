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
Write-Host "Package ready: $Distribution" -ForegroundColor Green
Write-Host "Smoke test: siegfridi --version -> $VersionOutput" -ForegroundColor Green
