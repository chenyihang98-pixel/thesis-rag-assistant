<div align="center">

**中文** · [English](./README.en.md) · [技术栈](./TECH_STACK.md)

# Thesis RAG Assistant

#### 面向个人论文资料库的检索与 RAG 问答工具

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)
![RAG](https://img.shields.io/badge/RAG-retrieval--augmented-2E7D32)
![Ollama](https://img.shields.io/badge/Ollama-supported-111111)
![OpenAI-compatible API](https://img.shields.io/badge/OpenAI--compatible-API-6A5ACD)
![Windows PowerShell](https://img.shields.io/badge/Windows-PowerShell-0078D4)

</div>

Thesis RAG Assistant 是一个面向个人论文资料库的检索与 RAG 问答工具。它可以用于论文检索、PDF 预览、基于检索结果的 AI 回答、选题分析，并支持 Ollama 本地模型与 OpenAI-compatible API。

## 目录

- [Demo 快速开始](#demo-快速开始)
- [配置 LLM](#配置-llm)
- [LLM 配置填写示例](#llm-配置填写示例)
- [接入自己的论文库](#接入自己的论文库)
- [论文库配置填写示例](#论文库配置填写示例)
- [常用命令](#常用命令)
- [技术栈](./TECH_STACK.md)

## Demo 快速开始

```powershell
.\scripts\setup_demo.ps1
.\scripts\run_demo.ps1
```

## 配置 LLM

如需使用 AI 回答，运行本地配置向导：

```powershell
.\scripts\configure_llm.ps1
```

支持两种方式：

- Ollama：使用本机或局域网中的 Ollama 服务。
- OpenAI-compatible API：填写兼容 Chat Completions 的 base URL、model 和访问凭据。

Ollama 模型示例：

```powershell
ollama pull <your-model-name>
ollama list
```

## LLM 配置填写示例

`configure_llm.ps1` 是交互式向导，按提示填写即可。模型名需要与 `ollama list` 或 API 平台显示的名称一致。

### Ollama 示例

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

| 字段 | 填写方式 |
| --- | --- |
| profile name | 本地配置名称，例如 `local_ollama` |
| Ollama Base URL | 本机通常是 `http://localhost:11434` |
| Ollama Model | `ollama list` 中显示的模型名 |
| temperature | 生成随机性，常用 `0.2` |
| num_ctx / num_predict | 上下文长度与回答长度上限 |

### API 示例

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

| 字段 | 填写方式 |
| --- | --- |
| API Base URL | 服务商提供的 OpenAI-compatible 地址 |
| API Model | 服务商提供的模型名 |
| API Credential | 你的本地访问凭据，向导会隐藏输入 |
| max_tokens | 单次回答的最大 token 数 |

## 接入自己的论文库

运行 internal corpus 向导：

```powershell
.\scripts\configure_internal.ps1
.\scripts\run_internal.ps1
```

向导会询问 profile name、PDF root 和 language。不同 profile 可对应不同论文库；启动时也可以指定 profile：

```powershell
.\scripts\run_internal.ps1 -Profile <profile_name>
```

## 论文库配置填写示例

`configure_internal.ps1` 会为每个 profile 创建独立的本地论文库工作区。

```text
profile name: my_corpus
PDF root: C:\path\to\pdfs
language: ja
work dir mode: project-local runtime workspace
confirm: YES
```

| 字段 | 填写方式 |
| --- | --- |
| profile name | 论文库名称，例如 `my_corpus` |
| PDF root | 存放 PDF 的文件夹路径 |
| language | 主要论文语言，例如 `ja`、`zh` 或 `en` |
| work dir mode | 默认使用项目内的 `.runtime/internal/corpora/[profile_name]` |

## 常用命令

```powershell
# 准备 demo 环境
.\scripts\setup_demo.ps1

# 启动 demo UI
.\scripts\run_demo.ps1

# 配置 LLM
.\scripts\configure_llm.ps1

# 配置自己的论文库
.\scripts\configure_internal.ps1

# 启动自己的论文库 UI
.\scripts\run_internal.ps1
```

