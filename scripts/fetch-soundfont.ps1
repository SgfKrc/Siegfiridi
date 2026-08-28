<#
.SYNOPSIS
    Fetch and verify the permitted FluidR3_GM fallback SoundFont.

.EXAMPLE
    .\scripts\fetch-soundfont.ps1
    .\scripts\fetch-soundfont.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$PackDir = Join-Path $Root 'assets\packs'
$Target = Join-Path $PackDir 'FluidR3_GM.sf2'
$Expected = '74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0'
$DownloadUrl = 'https://github.com/pianobooster/fluid-soundfont/releases/download/v3.1/FluidR3_GM.sf2'
$LicenseUrl = 'https://raw.githubusercontent.com/pianobooster/fluid-soundfont/v3.1/COPYING'
$SourceUrl = 'https://raw.githubusercontent.com/pianobooster/fluid-soundfont/v3.1/README'

New-Item -ItemType Directory -Path $PackDir -Force | Out-Null
if ($Force -or -not (Test-Path -LiteralPath $Target)) {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $Target
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) {
    throw "FluidR3_GM SHA-256 mismatch: expected $Expected, got $Actual"
}

foreach ($item in @(
    @{ Url = $LicenseUrl; Path = (Join-Path $PackDir 'FluidR3_GM.COPYING') },
    @{ Url = $SourceUrl; Path = (Join-Path $PackDir 'FluidR3_GM.SOURCE.txt') }
)) {
    if ($Force -or -not (Test-Path -LiteralPath $item.Path)) {
        Invoke-WebRequest -Uri $item.Url -OutFile $item.Path
    }
}

Write-Host "Verified FluidR3_GM.sf2 ($Actual)" -ForegroundColor Green
