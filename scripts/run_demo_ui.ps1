param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { Write-Error "Missing .\.venv\Scripts\python.exe." }
$env:KB_MODE = "demo"
foreach ($Name in @("LAB_PDF_ROOT","LAB_CATALOG_PATH","LAB_CHUNKS_PATH","LAB_INDEX_PATH","LAB_STRUCTURED_CHUNKS_PATH","LAB_STRUCTURED_INDEX_PATH","LAB_VECTOR_PATH","LAB_SNAPSHOT_MANIFEST_PATH","LAB_SNAPSHOT_HISTORY_PATH","LAB_SNAPSHOT_RECORD_DIR")) {
    Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "data\index\tfidf_index.pkl"))) {
    Write-Error "Missing data\index\tfidf_index.pkl. Run .\scripts\prepare_demo_assets.ps1 first."
}
& $Python -m streamlit run app.py
if ($LASTEXITCODE -ne 0) { Write-Error "Streamlit exited with code $LASTEXITCODE" }
