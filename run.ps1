param(
    [double] $Interval,
    [switch] $Once,
    [string] $SymbolsFile,
    [switch] $VerboseOutput,
    [switch] $InstallDeps
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if ($InstallDeps) {
    Write-Host "Installing/updating dependencies..." -ForegroundColor Cyan
    python -m pip install -r requirements.txt
}

$cliArgs = @()
if ($Interval)       { $cliArgs += @("--interval", $Interval) }
if ($Once)           { $cliArgs += "--once" }
if ($SymbolsFile)    { $cliArgs += @("--symbols-file", $SymbolsFile) }
if ($VerboseOutput)  { $cliArgs += "--verbose" }

python -m nifty_pricing_mirror.cli @cliArgs
