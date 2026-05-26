<div align="center">

[中文](./README.md) · **English**

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
- [Use Your Own Corpus](#use-your-own-corpus)
- [Common Commands](#common-commands)

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
- OpenAI-compatible API: enter a Chat Completions-compatible base URL, model, and API key.

Ollama model example:

```powershell
ollama pull <your-model-name>
ollama list
```

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

