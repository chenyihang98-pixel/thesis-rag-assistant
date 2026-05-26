param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing .\.venv\Scripts\python.exe. Create the venv and run: python -m pip install -e `".[dev]`""
}

function Invoke-PythonCommand {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python command failed: $($Arguments -join ' ')"
    }
}

Write-Host "Repository: $RepoRoot"
Write-Host "Python executable: $Python"
Invoke-PythonCommand @("--version")
Invoke-PythonCommand @("-c", "import sys, thesis_agent; print('sys.executable=' + sys.executable); print('thesis_agent=' + thesis_agent.__file__)")
Invoke-PythonCommand @("-c", "import streamlit; print('streamlit import ok')")

Write-Host "Demo runtime assets:"
foreach ($Path in @("data\samples","data\processed\chunks.jsonl","data\index\tfidf_index.pkl","data\vector\chroma","data\metadata\kb_snapshot_manifest.json")) {
    if (Test-Path -LiteralPath (Join-Path $RepoRoot $Path)) { Write-Host "  OK      $Path" } else { Write-Host "  missing $Path" }
}

Write-Host "Internal LAB_* settings:"
foreach ($Name in @("LAB_PDF_ROOT","LAB_CATALOG_PATH","LAB_CHUNKS_PATH","LAB_INDEX_PATH","LAB_STRUCTURED_CHUNKS_PATH","LAB_STRUCTURED_INDEX_PATH","LAB_VECTOR_PATH","LAB_SNAPSHOT_MANIFEST_PATH","LAB_SNAPSHOT_HISTORY_PATH","LAB_SNAPSHOT_RECORD_DIR")) {
    $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($Value)) { Write-Host "  unset   $Name"; continue }
    if (Test-Path -LiteralPath $Value) { Write-Host "  OK      $Name" } else { Write-Host "  missing $Name" }
}
