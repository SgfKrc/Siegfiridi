<#
.SYNOPSIS
    Finish a release archive from an already-built Siegfridi onedir.

.EXAMPLE
    .\scripts\finish-release.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$Distribution = Join-Path $Root 'dist\Siegfridi'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
$Executable = Join-Path $Distribution 'Siegfridi.exe'
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Missing packaged executable: $Executable"
}
$VersionOutput = (& $Executable --version).Trim()
if ($VersionOutput -notmatch '^0\.1\.0$') {
    throw "Packaged executable smoke test failed: $VersionOutput"
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
Write-Host "Archive ready: $Archive" -ForegroundColor Green
Write-Host "Archive SHA-256: $ArchiveHash" -ForegroundColor Green
