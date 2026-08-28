<#
.SYNOPSIS
    Run the PySide6 workbench directly from the checkout.

.EXAMPLE
    .\scripts\run-dev.ps1
    .\scripts\run-dev.ps1 -Offscreen
#>
[CmdletBinding()]
param(
    [switch]$Offscreen
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
$env:PYTHONPATH = Join-Path $Root 'src'
if ($Offscreen) {
    $env:QT_QPA_PLATFORM = 'offscreen'
}
& $Python -m siegfridi @args
exit $LASTEXITCODE
