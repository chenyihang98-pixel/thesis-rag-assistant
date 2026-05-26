# Copy this file to scripts/set_internal_env.local.ps1 and fill in your local paths.
# The local file is ignored by Git.
# configure_internal.ps1 normally generates the local file from the active profile.

$env:KB_MODE = "internal"
$env:LAB_PDF_ROOT = "<your_pdf_root>"
$env:LAB_CATALOG_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\catalog.csv"
$env:LAB_CHUNKS_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\processed\chunks.jsonl"
$env:LAB_INDEX_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\processed\tfidf_index.pkl"
$env:LAB_STRUCTURED_CHUNKS_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\processed\structured_chunks.jsonl"
$env:LAB_STRUCTURED_INDEX_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\processed\structured_tfidf_index.pkl"
$env:LAB_VECTOR_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\vector\chroma"
$env:LAB_SNAPSHOT_MANIFEST_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\kb_snapshot_manifest.json"
$env:LAB_SNAPSHOT_HISTORY_PATH = "<project_root>\.runtime\internal\corpora\<profile_name>\kb_snapshot_history.json"
$env:LAB_SNAPSHOT_RECORD_DIR = "<project_root>\.runtime\internal\corpora\<profile_name>\kb_snapshots"
