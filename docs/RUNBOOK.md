# ThesisAgent Runtime Runbook

This runbook describes the release runtime workflow for a fresh local checkout. The scripts are PowerShell wrappers around existing local CLIs; they do not change retrieval, RAG, PDF, UI, or provider behavior.

## Four-Command Workflow

Run from the project root:

```powershell
.\scripts\setup_demo.ps1
.\scripts\run_demo.ps1
.\scripts\configure_internal.ps1
.\scripts\run_internal.ps1
```

`configure_llm.ps1` is optional for retrieval-only use, but recommended for AI answers. Without an LLM profile, the UI starts and prompts you to configure a model before generation.

## setup_demo.ps1

`setup_demo.ps1` prepares the demo environment and local demo runtime assets. It is idempotent: by default it reuses the existing `.venv`, complete demo assets, and snapshot metadata.

It does the following:

- checks whether `.venv` exists;
- creates `.venv` with `py -3.11 -m venv .venv`;
- falls back to `python -m venv .venv` if the Python launcher or Python 3.11 selector is unavailable;
- uses `.\.venv\Scripts\python.exe` for all Python commands;
- runs `python -m pip install --upgrade pip`;
- runs `python -m pip install -e .`;
- runs a native dependency preflight for NumPy, NumPy random, SciPy, and scikit-learn;
- calls `.\scripts\prepare_demo_assets.ps1` only when assets are missing or `-ForceRebuild` is set;
- calls `.\scripts\write_demo_snapshot.ps1` only when snapshot metadata is missing or `-ForceRebuild` is set;
- prints `.\scripts\run_demo.ps1` as the next step.

It does not start Streamlit, does not read internal/private paths, and does not call Ollama or any API provider.

Use rebuild only when you explicitly want to rebuild project-local demo runtime assets:

```powershell
.\scripts\setup_demo.ps1 -ForceRebuild
```

## run_demo.ps1

`run_demo.ps1` starts the synthetic demo UI.

It does the following:

- uses `.\.venv\Scripts\python.exe`;
- clears `KB_MODE` and all `LAB_*` variables from the process;
- sets `KB_MODE=demo`;
- checks for demo assets:
  - `data/index/tfidf_index.pkl`
  - `data/index/structured_tfidf_index.pkl`
  - `data/vector/chroma`
  - baseline and structured chunk JSONL files
- calls `setup_demo.ps1` when any demo runtime asset is missing, so dependency installation and native preflight run before index building;
- calls `write_demo_snapshot.ps1` when the demo snapshot manifest is missing;
- loads `.runtime/llm/current_profile.json` if it exists;
- prints `No LLM profile found. Run .\scripts\configure_llm.ps1 to enable AI answers.` if no LLM profile exists;
- starts `.\.venv\Scripts\python.exe -m streamlit run app.py`.

Users do not need to run manual ingest or build commands for the demo.

## prepare_demo_assets.ps1

`prepare_demo_assets.ps1` builds only demo runtime assets from `data/samples`. By default it fills in missing pieces and skips assets that already exist.

Generated files:

- `data/processed/chunks.jsonl`
- `data/index/tfidf_index.pkl`
- `data/processed/structured_chunks.jsonl`
- `data/index/structured_tfidf_index.pkl`
- `data/vector/chroma`

It uses the local hash embedding provider. It does not call Ollama or external APIs and does not touch internal/private paths.

Optional rebuild:

```powershell
.\scripts\prepare_demo_assets.ps1 -ForceRebuild
```

`-ForceRebuild` may remove only these generated demo assets:

- `data/processed`
- `data/index`
- `data/vector`
- `data/metadata/kb_snapshot_manifest.json`
- `data/metadata/kb_snapshot_history.json`
- `data/metadata/kb_snapshots`

It must not remove source, tests, docs, scripts, `.git`, `.venv`, `data/samples`, or `data/evaluation`.

All demo paths are resolved relative to the downloaded project folder. The scripts do not hardcode a drive letter or create timestamped runtime directories.

## write_demo_snapshot.ps1

`write_demo_snapshot.ps1` writes lightweight demo snapshot metadata:

- `data/metadata/kb_snapshot_manifest.json`
- `data/metadata/kb_snapshot_history.json`
- `data/metadata/kb_snapshots/`

If demo assets are missing, it stops and asks the user to run `setup_demo.ps1` or `run_demo.ps1`.

## configure_internal.ps1

`configure_internal.ps1` is the interactive wizard for a user-local thesis corpus.

It asks for:

- profile name, default `internal`;
- PDF root, for example `<your_pdf_root>`;
- language, default `ja`.
- work dir mode, default `project-local runtime workspace`.

The default workspace is `.runtime/internal/corpora/<profile_name>/` under the downloaded project folder. Choose `custom work dir` only if you explicitly want an advanced external work directory.

Profile names cannot be empty and may contain only letters, numbers, dash, and underscore. If `.runtime/internal/profiles/<profile_name>.json` already exists, the wizard prints:

- reuse
- overwrite
- choose-another
- cancel

The default is not to overwrite. Choosing overwrite requires typing `YES` again.

The PDF root must exist, must be a directory, and must contain at least one `.pdf` filename. The wizard checks filenames only; it does not read PDF contents for validation.

The default project-local workspace may be missing. If it is missing, it is created only after the final `YES`. The workspace must not equal the PDF root. Original PDFs are never copied into `.runtime`.

It derives:

- `work_dir = .runtime\internal\corpora\<profile_name>`
- `catalog_path = <work_dir>\catalog.csv`
- `chunks_path = <work_dir>\processed\chunks.jsonl`
- `index_path = <work_dir>\processed\tfidf_index.pkl`
- `structured_chunks_path = <work_dir>\processed\structured_chunks.jsonl`
- `structured_index_path = <work_dir>\processed\structured_tfidf_index.pkl`
- `vector_path = <work_dir>\vector\chroma`
- `snapshot_manifest_path = <work_dir>\kb_snapshot_manifest.json`
- `snapshot_history_path = <work_dir>\kb_snapshot_history.json`
- `snapshot_record_dir = <work_dir>\kb_snapshots`

The wizard prints a summary and continues only after the user types `YES`.

If the profile workspace already contains corpus assets, the wizard prints:

- reuse existing assets
- build missing assets only
- force rebuild
- cancel

`build missing assets only` is the default. `reuse existing assets` writes only profile/current-profile metadata and requires the baseline catalog/chunks/index to already exist. `force rebuild` requires a second `YES` and may remove only generated assets inside the selected profile workspace: `catalog.csv`, `processed/`, `vector/`, `kb_snapshot*.json`, and `kb_snapshots/`. It never deletes the PDF root, another profile workspace, source files, tests, docs, scripts, `.git`, `.venv`, `data/samples`, or `data/evaluation`.

After confirmation, it:

- creates the work directory if needed;
- generates `catalog.csv` with `thesis_agent.cli.sync_catalog` when the catalog is missing;
- runs ingest when baseline chunks are missing;
- builds the baseline TF-IDF index when missing;
- attempts structured chunks and structured TF-IDF index generation;
- builds a hash vector index when missing;
- writes an internal snapshot;
- writes `.runtime/internal/profiles/<profile_name>.json`;
- updates `.runtime/internal/current_profile.json`;
- generates `scripts/set_internal_env.local.ps1`;
- prints `.\scripts\run_internal.ps1`.

Structured chunks/index and vector assets are helpful but not mandatory for UI startup. Baseline catalog, chunks, and TF-IDF index are required.

## configure_llm.ps1

`configure_llm.ps1` is the interactive wizard for local AI answer provider settings.

It asks for:

- profile name, default `local_llm`;
- provider: `ollama` or `api`.

For Ollama it asks for:

- Ollama Base URL, default `http://localhost:11434`;
- whether to check `/api/tags` and list installed models;
- Ollama Model;
- temperature, default `0.2`;
- `num_ctx`, default `4096`;
- `num_predict`, default `1200`.

For API it asks for:

- API Base URL;
- API Model;
- API Key as password input;
- temperature, default `0.2`;
- `max_tokens`, default `2000`.

It prints a summary before saving. API keys are shown as `****`, not in clear text. It continues only after the user types `YES`.

Generated ignored files:

- `.runtime/llm/current_profile.json`
- `.runtime/llm/profiles/<profile_name>.json`
- `scripts/set_llm_env.local.ps1`

`configure_llm.ps1` may call Ollama `/api/tags` only when the user agrees. It does not call model generation and does not call API providers.

## run_internal.ps1

`run_internal.ps1` starts the UI with the active internal profile.

It does the following:

- uses `.\.venv\Scripts\python.exe`;
- reads `.runtime/internal/profiles/*.json`;
- asks the user to run `.\scripts\configure_internal.ps1` if no current profile and no profiles exist;
- uses the only profile automatically when exactly one profile exists;
- when multiple profiles exist, lists them and lets the user press Enter for the current profile or enter a number/name to switch;
- supports `.\scripts\run_internal.ps1 -Profile <profile_name>`;
- updates `.runtime/internal/current_profile.json` with the selected profile;
- exports `KB_MODE=internal`;
- exports the profile paths as `LAB_*` environment variables;
- loads `.runtime/llm/current_profile.json` when it exists;
- exports LLM profile settings as `LLM_DEFAULT_PROVIDER`, `OLLAMA_*`, or `API_LLM_*`;
- verifies required paths:
  - PDF root
  - catalog
  - chunks
  - TF-IDF index
- refuses to start if required baseline assets are missing;
- warns, but still starts, if structured chunks/index are missing;
- warns, but still starts, if vector assets are missing;
- starts `.\.venv\Scripts\python.exe -m streamlit run app.py`.

## Changing To Another Local Corpus

Run the wizard again:

```powershell
.\scripts\configure_internal.ps1
```

Use a new profile name to keep the old profile, or reuse the same profile name to overwrite that profile metadata. The script updates only the active profile pointer. It does not delete old work directories, catalogs, chunks, indexes, vectors, or snapshots.

Old databases are not deleted when you switch corpus. Re-run `configure_internal.ps1`, choose a different profile name, and the new profile workspace becomes available after confirmation. `run_internal.ps1` lets you choose the active profile at launch.

## Profile Storage

Ignored local profile files:

- `.runtime/internal/current_profile.json`
- `.runtime/internal/profiles/<profile_name>.json`
- `.runtime/internal/corpora/<profile_name>/`
- `scripts/set_internal_env.local.ps1`

The JSON profile is the source of truth for `run_internal.ps1`. The corpus workspace may contain private extracted text, indexes, vectors, and snapshot metadata, so `.runtime/` is ignored. The local env script is kept as a convenience for users who want to inspect or source `LAB_*` variables manually.

Example template:

```powershell
Copy-Item .\scripts\set_internal_env.example.ps1 .\scripts\set_internal_env.local.ps1
```

The example file contains placeholders only. The `.local.ps1` file is ignored.

## Switching LLM Profiles

Run:

```powershell
.\scripts\configure_llm.ps1
```

Use a new profile name to keep the previous provider settings, or reuse the same profile name to update it. The wizard updates `.runtime/llm/current_profile.json`, which both `run_demo.ps1` and `run_internal.ps1` load on startup.

To switch Ollama model, choose provider `ollama` and enter a different installed model name. Use:

```powershell
ollama list
```

Example only:

```powershell
ollama pull qwen3.5:9b-q4_K_M
```

This is only an example. Use any local Ollama model you have installed, and configure it with `.\scripts\configure_llm.ps1`, `--ollama-model`, or `OLLAMA_MODEL`. The committed runtime does not assume this model.

To use Ollama running on another machine, configure the Base URL with that machine's LAN address, for example:

```powershell
http://<your-lan-ip>:11434
```

To switch API provider, choose provider `api` and enter the new base URL, model, and API key.

## Generated And Ignored Files

Ignored runtime files include:

- `.venv/`
- `.env`
- `.env.*`
- `.runtime/`
- `scripts/set_internal_env.local.ps1`
- `scripts/set_llm_env.local.ps1`
- `data/processed/`
- `data/index/`
- `data/vector/`
- `data/chroma/`
- `data/metadata/kb_snapshot_manifest.json`
- `data/metadata/kb_snapshot_history.json`
- `data/metadata/kb_snapshots/`
- `outputs/`
- `.pytest_cache/`
- `.tmp/`
- `tests/`
- `data/evaluation/`
- `chroma_db/`
- `*.pyc`
- `*.pyo`
- `*.pkl`
- `*.joblib`

Committed safe data remains:

- `data/samples/`

## Demo vs Internal

Demo mode:

- uses synthetic committed samples;
- generates runtime assets inside the repository;
- clears all `LAB_*` variables;
- uses hash embeddings;
- never calls Ollama/API during setup or startup.

Internal mode:

- uses a user-entered local PDF root;
- stores runtime assets in `.runtime/internal/corpora/<profile_name>/` by default;
- reads real PDFs only after the user confirms the wizard with `YES`;
- stores active profile metadata under `.runtime/`;
- uses hash embeddings for local vector indexing;
- never calls Ollama/API during indexing or startup.

## Providers

Ollama and API providers are UI generation options only. They are not called by setup, indexing, tests, or page load. The UI sends selected retrieved text context to the chosen provider only after the user clicks a generation action. PDF files are not uploaded.

The UI reads provider defaults from the ignored LLM profile loaded by `run_demo.ps1` or `run_internal.ps1`. If no profile exists, it shows a configuration prompt instead of assuming a personal model.

## Troubleshooting

### venv not found

Run:

```powershell
.\scripts\setup_demo.ps1
```

If `configure_internal.ps1` finds no `.venv`, it can run `setup_demo.ps1` or create the environment after an explicit prompt.

### Wrong Python

Use the script-managed interpreter:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Avoid direct `streamlit run app.py` on machines with multiple Python or Anaconda environments. The runtime scripts use `.\.venv\Scripts\python.exe -m streamlit run app.py`.

### Demo index missing

Run:

```powershell
.\scripts\run_demo.ps1
```

It will call `setup_demo.ps1` automatically when assets are missing. To rebuild only demo runtime assets:

```powershell
.\scripts\setup_demo.ps1 -ForceRebuild
```

If only one runtime asset is missing, `prepare_demo_assets.ps1` can fill in that missing piece without deleting the rest.

### NumPy/SciPy DLL blocked

If setup fails during the native dependency preflight with a message such as `DLL load failed while importing mtrand`, NumPy/SciPy native extensions could not load. Windows application control policy may have blocked a DLL.

Try recreating `.venv` in a trusted folder, or adjust the security policy. Then rerun:

```powershell
.\scripts\setup_demo.ps1
```

The script stops before demo asset building in this case, so the error is not treated as a demo index problem.

### Internal profile missing

Run:

```powershell
.\scripts\configure_internal.ps1
```

Then run:

```powershell
.\scripts\run_internal.ps1
```

### Internal index missing

Re-run:

```powershell
.\scripts\configure_internal.ps1
```

`run_internal.ps1` will not start without baseline chunks and TF-IDF index. Structured assets can be missing because the UI has fallback behavior.

### PDF preview issues

PDF Preview/Open/Download are separate UI actions. Preview requires the active environment to include the Streamlit PDF packages installed by `setup_demo.ps1`. If preview support is missing:

```powershell
.\.venv\Scripts\python.exe -m pip install "streamlit[pdf]" streamlit-pdf
```

Open/Download can still work when preview falls back.

### Ollama timeout

Ollama is not called automatically. If a user selects Ollama and clicks generate, make sure the local Ollama server is running and the selected model is available. For small local models, reduce context size or retrieval top K if responses time out.

### Ollama model missing

Run:

```powershell
ollama list
.\scripts\configure_llm.ps1
```

Choose an installed model. The UI does not ship with a hardcoded personal model.

### Ollama server not running or wrong base URL

Start Ollama locally, or rerun `configure_llm.ps1` and set the correct base URL. For another machine on your LAN, use that machine's reachable address, such as `http://<your-lan-ip>:11434`.

### API key/base URL/model errors

API mode is optional. Configure the API base URL, model, and key in the UI before clicking generate. The app uses an OpenAI-compatible chat-completions request through local settings and environment variables; keys must not be committed.

If the API key is missing, rerun:

```powershell
.\scripts\configure_llm.ps1
```

If the API model is not found, confirm the provider's model name and update the LLM profile.

## Developer Validation

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q --basetemp=.tmp\pytest-tmp
python -X pycache_prefix=.tmp\compile_pycache -m compileall src app.py
```
