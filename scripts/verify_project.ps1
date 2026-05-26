param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Virtualenv Python not found: $Python. Create the venv and install dependencies first."
}

Write-Host "Using Python: $Python"
& $Python -c "import sys; print(sys.executable)"
& $Python -c "import thesis_agent; print(thesis_agent.__file__)"

Write-Host "Installing editable dev package..."
& $Python -m pip install -e ".[dev]"

Write-Host "Running tests..."
& $Python -m pytest -q

Write-Host "Compiling source with isolated pycache..."
& $Python -X pycache_prefix=.tmp\compile_pycache -m compileall src app.py

Write-Host "Project verification completed successfully."
