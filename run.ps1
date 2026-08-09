param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "The local environment is missing. Run .\setup.ps1 first."
}

Push-Location $root
try {
    & $python -m languagelab.cli @Arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
