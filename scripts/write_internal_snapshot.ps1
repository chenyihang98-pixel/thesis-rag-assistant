param([string]$Notes = "internal runtime snapshot")

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { Write-Error "Missing .\.venv\Scripts\python.exe." }

$LocalEnv = Join-Path $ScriptDir "set_internal_env.local.ps1"
if (Test-Path -LiteralPath $LocalEnv) {
    . $LocalEnv
}
if ($env:KB_MODE -ne "internal") {
    Write-Error "KB_MODE must be internal. Load scripts\set_internal_env.local.ps1 first."
}

function Get-RequiredEnvPath { param([string]$Name); $Value = [Environment]::GetEnvironmentVariable($Name, "Process"); if ([string]::IsNullOrWhiteSpace($Value)) { Write-Error "$Name is required." }; if (-not (Test-Path -LiteralPath $Value)) { Write-Error "Path configured by $Name does not exist." }; return $Value }
function Get-OptionalExistingEnvPath { param([string]$Name); $Value = [Environment]::GetEnvironmentVariable($Name, "Process"); if ([string]::IsNullOrWhiteSpace($Value)) { return $null }; if (-not (Test-Path -LiteralPath $Value)) { Write-Warning "Skipping $Name because path does not exist."; return $null }; return $Value }

$CatalogPath = Get-RequiredEnvPath "LAB_CATALOG_PATH"
$ChunksPath = Get-RequiredEnvPath "LAB_CHUNKS_PATH"
$IndexPath = Get-RequiredEnvPath "LAB_INDEX_PATH"
$OutputPath = [Environment]::GetEnvironmentVariable("LAB_SNAPSHOT_MANIFEST_PATH", "Process")
if ([string]::IsNullOrWhiteSpace($OutputPath)) { Write-Error "LAB_SNAPSHOT_MANIFEST_PATH is required." }
$Args = @("-m","thesis_agent.cli.write_kb_snapshot_manifest","--mode","internal","--snapshot-kind","internal","--catalog-path",$CatalogPath,"--chunks-path",$ChunksPath,"--index-path",$IndexPath,"--output",$OutputPath,"--embedding-provider","hash","--notes",$Notes)
$StructuredChunksPath = Get-OptionalExistingEnvPath "LAB_STRUCTURED_CHUNKS_PATH"; if ($StructuredChunksPath) { $Args += @("--structured-chunks-path",$StructuredChunksPath) }
$StructuredIndexPath = Get-OptionalExistingEnvPath "LAB_STRUCTURED_INDEX_PATH"; if ($StructuredIndexPath) { $Args += @("--structured-index-path",$StructuredIndexPath) }
$VectorPath = Get-OptionalExistingEnvPath "LAB_VECTOR_PATH"; if ($VectorPath) { $Args += @("--vector-path",$VectorPath) }
$HistoryPath = [Environment]::GetEnvironmentVariable("LAB_SNAPSHOT_HISTORY_PATH", "Process"); if (-not [string]::IsNullOrWhiteSpace($HistoryPath)) { $Args += @("--history-output",$HistoryPath) }
$RecordDir = [Environment]::GetEnvironmentVariable("LAB_SNAPSHOT_RECORD_DIR", "Process"); if (-not [string]::IsNullOrWhiteSpace($RecordDir)) { $Args += @("--record-dir",$RecordDir) }
Write-Host "Writing internal snapshot metadata only. This script does not rebuild indexes or read PDF contents."
& $Python @Args
if ($LASTEXITCODE -ne 0) { Write-Error "Snapshot command failed." }
