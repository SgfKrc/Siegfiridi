<#
.SYNOPSIS
    Fetch and verify the CC0 FreePats Ocarina SF2.

.DESCRIPTION
    The release is distributed as a 7z archive. The optional `assets` extra
    provides py7zr for extraction; the extracted SF2 remains a local asset.

.EXAMPLE
    .\scripts\fetch-freepats-ocarina.ps1
    .\scripts\fetch-freepats-ocarina.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$PackDir = Join-Path $Root 'assets\packs'
$Target = Join-Path $PackDir 'Ocarina-20241002.sf2'
$ArchiveUrl = 'https://github.com/freepats/ocarina1/releases/download/2024-10-02/Ocarina-SF2-20241002.7z'
$ExpectedArchive = '1d48403208a38555503bbd9f65d09815ee4edb10ba01e9a345935ae44c38179c'
$ExpectedSoundfont = 'e92c42a68cb738663748ce512dfbc7f18c3c3ea38d12df9ce165b249e6da6bc6'
$ArchivePath = Join-Path ([System.IO.Path]::GetTempPath()) 'Ocarina-SF2-20241002.7z'
$ExtractDir = Join-Path ([System.IO.Path]::GetTempPath()) 'siegfridi-ocarina-extract'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

New-Item -ItemType Directory -Path $PackDir -Force | Out-Null
if ($Force -or -not (Test-Path -LiteralPath $ArchivePath)) {
    Invoke-WebRequest -Uri $ArchiveUrl -OutFile $ArchivePath
}
$ActualArchive = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchivePath).Hash.ToLowerInvariant()
if ($ActualArchive -ne $ExpectedArchive) {
    throw "FreePats Ocarina archive SHA-256 mismatch: expected $ExpectedArchive, got $ActualArchive"
}

$Extractor = Join-Path $PSScriptRoot 'extract-7z.py'
& $Python $Extractor $ArchivePath $ExtractDir $PackDir
if ($LASTEXITCODE -ne 0) {
    throw 'Could not extract the FreePats Ocarina archive; install the optional assets extra with: python -m pip install -e ".[assets]"'
}

$ActualSoundfont = (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash.ToLowerInvariant()
if ($ActualSoundfont -ne $ExpectedSoundfont) {
    throw "FreePats Ocarina SF2 SHA-256 mismatch: expected $ExpectedSoundfont, got $ActualSoundfont"
}
$license = Get-Content -Raw -LiteralPath (Join-Path $PackDir 'FreePats-Ocarina.CC0.txt')
if ($license -notmatch 'CC0 1\.0 Universal') {
    throw 'The fetched Ocarina archive does not contain the expected CC0 1.0 license text'
}
Write-Host "Verified Ocarina-20241002.sf2 ($ActualSoundfont)" -ForegroundColor Green
Write-Host "Archive SHA-256: $ActualArchive"
