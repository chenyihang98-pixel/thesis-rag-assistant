param([string]$Notes = "demo runtime snapshot")

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing .\.venv\Scripts\python.exe. Run .\scripts\setup_demo.ps1 first."
}

Remove-Item -LiteralPath "Env:KB_MODE" -ErrorAction SilentlyContinue
$env:KB_MODE = "demo"
foreach ($Name in @(
    "LAB_PDF_ROOT",
    "LAB_CATALOG_PATH",
    "LAB_CHUNKS_PATH",
    "LAB_INDEX_PATH",
    "LAB_STRUCTURED_CHUNKS_PATH",
    "LAB_STRUCTURED_INDEX_PATH",
    "LAB_VECTOR_PATH",
    "LAB_SNAPSHOT_MANIFEST_PATH",
    "LAB_SNAPSHOT_HISTORY_PATH",
    "LAB_SNAPSHOT_RECORD_DIR"
)) {
    Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
}

function Resolve-ProjectPath {
    param([string]$RelativePath)
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativePath))
}

foreach ($Required in @(
    "data\processed\chunks.jsonl",
    "data\index\tfidf_index.pkl",
    "data\processed\structured_chunks.jsonl",
    "data\index\structured_tfidf_index.pkl",
    "data\vector\chroma"
)) {
    $Full = Resolve-ProjectPath $Required
    if (-not (Test-Path -LiteralPath $Full)) {
        Write-Error "Missing demo asset: $Required. Run .\scripts\setup_demo.ps1 or .\scripts\run_demo.ps1 first."
    }
}

& $Python -m thesis_agent.cli.write_kb_snapshot_manifest `
    --mode demo `
    --snapshot-kind demo `
    --chunks-path data/processed/chunks.jsonl `
    --index-path data/index/tfidf_index.pkl `
    --structured-chunks-path data/processed/structured_chunks.jsonl `
    --structured-index-path data/index/structured_tfidf_index.pkl `
    --vector-path data/vector/chroma `
    --output data/metadata/kb_snapshot_manifest.json `
    --history-output data/metadata/kb_snapshot_history.json `
    --record-dir data/metadata/kb_snapshots `
    --embedding-provider hash `
    --notes $Notes

if ($LASTEXITCODE -ne 0) {
    Write-Error "Snapshot command failed."
}

Write-Host "Demo snapshot metadata is ready."
