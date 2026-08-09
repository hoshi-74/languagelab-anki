param(
    [string]$Python
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (-not $Python) {
    if ($env:CODEX_PYTHON -and (Test-Path -LiteralPath $env:CODEX_PYTHON)) {
        $Python = $env:CODEX_PYTHON
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = (Get-Command python).Source
    } else {
        $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
        if (Test-Path -LiteralPath $codexPython) {
            $Python = $codexPython
        }
    }
}

if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    throw "Python was not found. Run .\setup.ps1 -Python <path-to-python.exe> with Python 3.10+."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv (Join-Path $root ".venv")
}

& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
& $venvPython -m languagelab.cli self-check
