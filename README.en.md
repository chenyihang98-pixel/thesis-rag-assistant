<div align="center">

[中文](./README.md) · **English** · [Tech Stack](./TECH_STACK.md)

# Thesis RAG Assistant

#### Search and RAG assistant for personal thesis paper collections

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)
![RAG](https://img.shields.io/badge/RAG-retrieval--augmented-2E7D32)
![Ollama](https://img.shields.io/badge/Ollama-supported-111111)
![OpenAI-compatible API](https://img.shields.io/badge/OpenAI--compatible-API-6A5ACD)
![Windows PowerShell](https://img.shields.io/badge/Windows-PowerShell-0078D4)

</div>

Thesis RAG Assistant is a search and RAG assistant for personal thesis paper collections. It supports paper search, PDF preview, AI answers grounded in retrieved papers, topic analysis, and integration with Ollama or OpenAI-compatible APIs.

## Index

- [Demo Quick Start](#demo-quick-start)
- [Configure LLM](#configure-llm)
- [LLM Configuration Examples](#llm-configuration-examples)
- [Use Your Own Corpus](#use-your-own-corpus)
- [Corpus Configuration Examples](#corpus-configuration-examples)
- [Common Commands](#common-commands)
- [Tech Stack](./TECH_STACK.md)

## Demo Quick Start

```powershell
.\scripts\setup_demo.ps1
.\scripts\run_demo.ps1
```

## Configure LLM

To enable AI answers, run the local configuration wizard:

```powershell
.\scripts\configure_llm.ps1
```

Supported options:

- Ollama: use a local or LAN Ollama service.
- OpenAI-compatible API: enter a Chat Completions-compatible base URL, model, and local credential.

Ollama model example:

```powershell
ollama pull <your-model-name>
ollama list
```

## LLM Configuration Examples

`configure_llm.ps1` is an interactive wizard. Enter the model name exactly as shown by `ollama list` or by your API provider.

### Ollama Example

```text
profile name: local_ollama
provider: ollama
Ollama Base URL: http://localhost:11434
Ollama Model: [your-model-name]
temperature: 0.2
num_ctx: 4096
num_predict: 1200
confirm: YES
```

| Field | What to enter |
| --- | --- |
| profile name | A local profile name, such as `local_ollama` |
| Ollama Base URL | Usually `http://localhost:11434` on the same machine |
| Ollama Model | The model name shown by `ollama list` |
| temperature | Generation randomness, commonly `0.2` |
| num_ctx / num_predict | Context size and response length limit |

### API Example

```text
profile name: api_llm
provider: api
API Base URL: [your-api-base-url]
API Model: [your-model-name]
API Credential: [your-api-credential]
temperature: 0.2
max_tokens: 2000
confirm: YES
```

| Field | What to enter |
| --- | --- |
| API Base URL | The OpenAI-compatible endpoint from your provider |
| API Model | The model name from your provider |
| API Credential | Your local credential; the wizard hides the input |
| max_tokens | Maximum tokens for one answer |

## Use Your Own Corpus

Run the internal corpus wizard:

```powershell
.\scripts\configure_internal.ps1
.\scripts\run_internal.ps1
```

The wizard asks for a profile name, PDF root, and language. Different profiles can point to different paper collections. You can also start a specific profile:

```powershell
.\scripts\run_internal.ps1 -Profile <profile_name>
```

## Corpus Configuration Examples

`configure_internal.ps1` creates a separate local corpus workspace for each profile.

```text
profile name: my_corpus
PDF root: C:\path\to\pdfs
language: ja
work dir mode: project-local runtime workspace
confirm: YES
```

| Field | What to enter |
| --- | --- |
| profile name | A corpus name, such as `my_corpus` |
| PDF root | The folder that contains your PDF files |
| language | Main paper language, such as `ja`, `zh`, or `en` |
| work dir mode | The default project workspace: `.runtime/internal/corpora/[profile_name]` |

## Common Commands

```powershell
# Prepare demo environment
.\scripts\setup_demo.ps1

# Run demo UI
.\scripts\run_demo.ps1

# Configure LLM
.\scripts\configure_llm.ps1

# Configure your paper corpus
.\scripts\configure_internal.ps1

# Run your corpus UI
.\scripts\run_internal.ps1
```
