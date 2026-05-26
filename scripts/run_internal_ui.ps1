param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { Write-Error "Missing .\.venv\Scripts\python.exe." }
$env:KB_MODE = "internal"

function Assert-EnvPathExists {
    param([string]$Name, [switch]$Required)
    $Value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($Value)) { if ($Required) { Write-Error "$Name is required." }; return }
    if (-not (Test-Path -LiteralPath $Value)) { if ($Required) { Write-Error "Path configured by $Name does not exist." } else { Write-Warning "Optional path configured by $Name does not exist." }; return }
    Write-Host "OK $Name"
}

Assert-EnvPathExists -Name "LAB_PDF_ROOT" -Required
Assert-EnvPathExists -Name "LAB_CATALOG_PATH" -Required
Assert-EnvPathExists -Name "LAB_CHUNKS_PATH" -Required
Assert-EnvPathExists -Name "LAB_INDEX_PATH" -Required
Assert-EnvPathExists -Name "LAB_STRUCTURED_CHUNKS_PATH"
Assert-EnvPathExists -Name "LAB_STRUCTURED_INDEX_PATH"
Assert-EnvPathExists -Name "LAB_VECTOR_PATH"
Assert-EnvPathExists -Name "LAB_SNAPSHOT_MANIFEST_PATH"
Assert-EnvPathExists -Name "LAB_SNAPSHOT_HISTORY_PATH"
Assert-EnvPathExists -Name "LAB_SNAPSHOT_RECORD_DIR"
Write-Host "Starting internal UI. This script does not rebuild indexes or read PDF contents."
& $Python -m streamlit run app.py
if ($LASTEXITCODE -ne 0) { Write-Error "Streamlit exited with code $LASTEXITCODE" }
