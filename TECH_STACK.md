# 技术栈

Thesis RAG Assistant 是一个面向个人论文资料库的 RAG 应用。项目会将 PDF 或示例文档转换为可检索的本地知识库，并在检索结果基础上完成论文搜索、PDF 预览、引用溯源问答和选题分析。

## 1. 技术栈概览

| 层级 | 技术 / 设计 |
| --- | --- |
| UI | Streamlit |
| 语言 | Python 3.11+ |
| PDF 解析 | PyMuPDF |
| Demo 输入 | Markdown 示例数据 |
| 本地论文库输入 | 用户 PDF 文件夹 |
| 切片 | 固定切片（fixed chunk）+ 结构化切片（structured chunk） |
| 检索 | 关键词检索（TF-IDF）、向量检索（vector retrieval）、混合检索（hybrid retrieval） |
| 向量库 | 本地 Chroma-style vector store |
| 默认向量化方式 | hash embedding |
| 模型调用 | Ollama / OpenAI-compatible API |
| 配置管理 | profile |
| 版本记录 | snapshot |

## 2. RAG 工作流

系统先通过检索模块召回相关论文内容，再拼接受控上下文，最后交给 Ollama 或 OpenAI-compatible API 生成回答。

```text
用户 query
-> TF-IDF / vector / hybrid 检索
-> 论文级去重
-> 引用映射
-> prompt 拼装
-> Ollama / API 生成回答
-> 引用校验与 UI 展示
```

## 3. 数据前处理

Demo 模式使用仓库内的 Markdown 示例数据：

```text
data/samples/*.md
-> fixed chunks
-> TF-IDF index

data/samples/*.md
-> structured chunks
-> structured TF-IDF index
-> vector store
-> 知识库快照（snapshot）
```

Internal 模式使用用户选择的 PDF 文件夹：

```text
PDF root
-> catalog.csv
-> text extraction
-> fixed chunks + structured chunks
-> TF-IDF index + vector store
-> 知识库快照（snapshot）
-> 配置档案（profile）
```

## 4. 主要生成物

| 生成物 | 作用 |
| --- | --- |
| `catalog.csv` | 论文身份和元数据，包括 `doc_id`、标题、年份、PDF 路径等 |
| `chunks.jsonl` | 固定切片（fixed chunk）结果 |
| `structured_chunks.jsonl` | 结构化切片（structured chunk）结果 |
| `tfidf_index.pkl` | query 到 chunk 的关键词检索索引 |
| `structured_tfidf_index.pkl` | 基于结构化切片的关键词检索索引 |
| `vector/chroma/` | 本地向量库（vector store） |
| `kb_snapshot_manifest.json` | 当前知识库快照（snapshot） |
| `kb_snapshot_history.json` | 知识库快照历史 |
| `profile.json` | 一套论文库 profile |
| `current_profile.json` | 当前启用的 profile |

`catalog.csv` 负责论文身份和元数据；`tfidf_index.pkl` 负责 query 到 chunk 的关键词检索；profile 表示当前使用哪套论文库；snapshot 表示当前论文库运行资产是哪一版。

## 5. Chunk 策略

固定切片（fixed chunk）使用字符窗口：

```text
chunk_size = 500
overlap = 80
step = 420
```

结构化切片（structured chunk）采用章节感知（section-aware）的切片方式：

```text
chunk_size = 700
overlap = 100
```

structured chunk 会保留 `section_title`、`section_type`、`heading_path`、`display_text`、`embedding_text` 等字段，用于检索上下文构造、来源展示和引用映射。

## 6. 检索策略

- 关键词检索（TF-IDF）：使用字符级 n-gram，用于关键词相关性检索。
- 向量检索（vector retrieval）：使用 hash embedding 与余弦相似度计算相似性。
- 混合检索（hybrid retrieval）：融合 TF-IDF 与 vector 分数。

检索结果保留 chunk 级引用 ID（citation）、doc_id、标题、分数和元数据，后续由 UI 与 RAG 服务整理为论文级来源。

## 7. 两种上下文模式

当前结果回答使用页面上已经显示的论文结果，适合围绕当前检索列表继续追问。

AI 重新检索回答会根据用户问题重新检索 chunk，再按论文级去重。这个模式中的 Top K 表示论文数量，而不是原始 chunk 数量。

## 8. 论文级去重与引用映射

底层检索是 chunk 级，最终展示和 RAG 来源是论文级。论文级去重（paper-level deduplication）用于把同一篇论文的多个命中 chunk 聚合为同一条论文来源。

底层 citation 使用 `doc_id#chunk_id`。

回答中的 `[1]`、`[2]`、`[3]` 是临时引用编号，用于映射回具体论文来源。

```text
[1] -> doc_id#chunk_id
[2] -> doc_id#chunk_id
[3] -> doc_id#chunk_id
```

引用映射（citation mapping）让 UI 可以把模型回答关联回具体论文来源和规范引用（canonical citation）。

## 9. LLM 调用

项目支持两类模型调用：

- Ollama
- OpenAI-compatible API

模型连接信息通过 `configure_llm.ps1` 配置，并由本地 LLM 配置档案（LLM profile）在启动时注入运行环境。

## 10. Profile 与 Snapshot

Profile 管理当前使用哪套论文库，记录 PDF root、catalog、chunks、index、vector、snapshot 等路径。

Snapshot 记录这套论文库运行资产的版本，包括构建时间、资产路径、chunk 数量、文档数量和向量化方式（embedding provider）。

Snapshot 对应知识库运行资产版本，Git 版本对应源码版本，二者分层管理。
