<div align="center">

**中文** · [English](./README.en.md)

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
- [接入自己的论文库](#接入自己的论文库)
- [常用命令](#常用命令)

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
- OpenAI-compatible API：填写兼容 Chat Completions 的 base URL、model 和 API key。

Ollama 模型示例：

```powershell
ollama pull <your-model-name>
ollama list
```

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

