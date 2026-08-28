<#
.SYNOPSIS
    Fetch and verify the CC0 SP Bamboo Flute source package.

.DESCRIPTION
    The package is an SFZ/WAV source library. It is intentionally kept
    separate from the FluidSynth SF2/SF3 runtime packs until it is converted
    and mapped by the project.

.EXAMPLE
    .\scripts\fetch-oriental-source.ps1
    .\scripts\fetch-oriental-source.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$SourceDir = Join-Path $Root 'assets\packs\sources\sp-bamboo-flute'
$Commit = 'bffe30a67a29c8b2dc691e1a45af78b801d57ce6'
$ArchiveUrl = "https://codeload.github.com/NeoSoundFonts/SP-Bamboo-Flute/zip/$Commit"
$ExpectedArchive = 'd95532de4402ee490bec40d487c19d3a53fd02e84b147a3a98dc94fe4d857f51'
$ArchivePath = Join-Path ([System.IO.Path]::GetTempPath()) "sp-bamboo-flute-$Commit.zip"
$ExtractDir = Join-Path ([System.IO.Path]::GetTempPath()) "sp-bamboo-flute-$Commit"

New-Item -ItemType Directory -Path $SourceDir -Force | Out-Null
if ($Force -or -not (Test-Path -LiteralPath (Join-Path $SourceDir 'LICENSE')) -or -not (Test-Path -LiteralPath $ArchivePath)) {
    Invoke-WebRequest -Uri $ArchiveUrl -OutFile $ArchivePath
}

$ActualArchive = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchivePath).Hash.ToLowerInvariant()
if ($ActualArchive -ne $ExpectedArchive) {
    throw "SP Bamboo Flute archive SHA-256 mismatch: expected $ExpectedArchive, got $ActualArchive"
}

New-Item -ItemType Directory -Path $ExtractDir -Force | Out-Null
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractDir -Force
$ExtractedRoot = Join-Path $ExtractDir "SP-Bamboo-Flute-$Commit"
if (-not (Test-Path -LiteralPath $ExtractedRoot)) {
    throw "Expected extracted source directory does not exist: $ExtractedRoot"
}
Copy-Item -Path (Join-Path $ExtractedRoot '*') -Destination $SourceDir -Recurse -Force

$license = Get-Content -Raw -LiteralPath (Join-Path $SourceDir 'LICENSE')
if ($license -notmatch 'CC0 1\.0 Universal') {
    throw 'The fetched source package does not contain the expected CC0 1.0 license text'
}

Write-Host "Verified SP Bamboo Flute source commit $Commit" -ForegroundColor Green
Write-Host "Archive SHA-256: $ActualArchive"
Write-Host "Source format: SFZ/WAV (not directly loadable by FluidSynth)"
