# knowledgebase · LLM Wiki 知识库框架

> 一套**零运行时依赖**的 Python 知识库引擎：把"原始资料 → AI 编译的结构化知识 → 可维护规则"拆成 Raw / Wiki / Schema 三层，配套 Web 管理台与自动化，让个人知识库**可长期增量维护、且不会悄悄退化**。

[English version below ↓](#english)

---

## 一句话定位

为"个人知识库"造一套**有结构、可自检、人机协同**的维护框架——AI 负责把资料编译成互链知识页，人保留最终裁决权（尤其是观点冲突时）。

## 为什么做（问题）

个人知识库常见的死法有三种：
1. **变成垃圾堆**——资料越塞越多，没有结构，检索靠翻。
2. **悄悄退化**——资料互相矛盾、引用断链、页面成孤儿，没人发现。
3. **被 AI 覆盖**——自动编译直接覆盖旧结论，历史上下文丢失。

本框架的答案是 Karpathy 提出的 **LLM Wiki 三层架构** + 把"检查"设为系统一等公民。

## 架构

```
Raw 层   原始资料（文章/论文/对话/笔记），只读真相源
  │  (AI 增量编译)
Wiki 层  结构化互链知识页（Markdown + [[双链]]），index.json 为目录
  │  (遵循 Schema 规则)
Schema 层  维护规则集（对应 LLM Wiki 的 AGENTS.md）
```

- **存储引擎 `WikiStore`**：页面读写、双链/反链、孤儿、冲突、编译标记，纯标准库实现。
- **编译引擎 `KBCompiler`**：注入 duck-typed LLM provider，增量编译新资料为 Wiki 页。
- **维护调度 `WikiMaintainer`**：后台体检 / 自动编译存量（纯逻辑，不绑 GUI/网络）。
- **关系图谱 `build_wiki_graph`**：纯函数产出节点/边/悬空链，UI 自行渲染。
- **规则 `schema`**：默认规则集 + `load/save_kb_schema`，可配置冲突策略。

## 核心能力

| 能力 | 说明 |
|---|---|
| 增量编译 | 只编新增/改动资料，不重跑全库 |
| 冲突双记 | 新旧观点及来源/时间/适用范围同时保留，**不直接覆盖** |
| 自动体检 | 查空双链、孤儿页、冲突页，输出明细 |
| 关系图谱 | 可视化知识网络与断点 |
| Obsidian 原生 | 页面写入 YAML frontmatter，可被 Obsidian 直接打开 |
| 零依赖 | 仅标准库，任意项目 `import knowledgebase` 复用 |

## 真实落地（不是 demo）

桌面 AI 宠物 `desktop_pet.py`（约 9000 行单文件应用）**直接集成本包**作为知识引擎：
- `self.wiki = kb_pkg.WikiStore(base_dir=.../wiki)` 接管知识落盘；
- 经 `KBCompiler` 桥接 LLM 做入库即编译；
- 设置面板编辑 Schema 规则，编译时由 LLM 遵循。

当前生产实例管理 **71 页**个人知识库（concepts 39 / topics 16 / entities 15 / sources 1），是真实跑起来的知识引擎，而非示例数据。

## 配套组件

- **Web 管理台**（`knowledgebase-webui`，FastAPI + Vue 3）：Wiki 列表 / 图谱可视化 / Schema 编辑 / 体检报告 / **人工冲突裁决** 五个视图，前端零图表库依赖（SVG 直绘）。
- **自动化**（WorkBuddy）：每日 07:30 增量编译、每周六 21:30 体检，把"检查"自动化。

## 工程指标

- 核心包 **823 行** / 5 模块，**33 个单元测试零回归**。
- 零运行时依赖（仅标准库）。
- 关注点分离：核心逻辑全在包内，Web 层是薄壳，不在 API 里重复实现业务。

## 技术栈

Python 3.10+（零依赖核心包）· FastAPI（薄后端）· Vue 3 + Vite（SPA）· SVG（图谱渲染）· WorkBuddy 自动化。

## 快速开始

```bash
pip install -e .          # 开发模式，改源码即时生效
```

```python
import knowledgebase as kb

wiki = kb.WikiStore(base_dir="./my_wiki")
wiki.write_page("concepts", "向量数据库", "RAG 常配合 [[RAG]] 使用。",
                sources=["某资料"], tags=["检索"])

compiler = kb.KBCompiler(wiki, my_provider)   # my_provider 签名: complete(prompt, on_done, on_error)
compiler.compile_item("新资料标题", "来源", "正文…")

report = wiki.health()                         # 空链 / 孤儿 / 冲突明细
nodes, edges, danglers = kb.build_wiki_graph(wiki.index)
```

## 设计取舍（诚实标注）

- **单用户规模**：`WikiStore` 启动期加载 `index.json`，多写者并发会读到旧索引——定位是个人/单机知识库，非多租户服务。
- **LLM 编排在外部**：包提供结构、存储、体检与图谱；"编译"的智能由外部 agent / 自动化注入 provider 完成，包不绑定任何模型服务。
- **冲突不自动消解**：AI 只标记冲突并列出分歧点，最终裁决权留给人工——这是防知识退化的关键红线。

## 许可证

MIT

---

# English

# knowledgebase · LLM Wiki Knowledge-Base Framework

> A **zero-runtime-dependency** Python engine that splits "raw material → AI-compiled structured knowledge → maintainable rules" into a Raw / Wiki / Schema three-layer architecture, shipped with a web console and automations so a personal knowledge base stays **incrementally maintainable and does not silently degrade**.

## One-line positioning

A **structured, self-auditing, human-in-the-loop** maintenance framework for personal knowledge bases — the AI compiles material into interlinked knowledge pages, while the human keeps the final say (especially on conflicting viewpoints).

## Why (the problem)

Personal knowledge bases typically die in three ways: (1) they become a dumping ground with no structure; (2) they silently degrade — contradictory sources, broken links, orphan pages nobody notices; (3) they get overwritten by AI auto-compilation, losing historical context. The answer here is Karpathy's **LLM Wiki three-layer architecture**, with "checking" promoted to a first-class citizen of the system.

## Architecture

```
Raw      Raw material (articles/papers/chats/notes) — read-only source of truth
  │  (AI incremental compile)
Wiki     Structured interlinked pages (Markdown + [[wikilinks]]); index.json is the catalog
  │  (follows Schema rules)
Schema   Maintenance rule set (the AGENTS.md of LLM Wiki)
```

- **`WikiStore`** — page read/write, wikilinks/backlinks, orphans, conflicts, compile flags. Pure stdlib.
- **`KBCompiler`** — injects a duck-typed LLM provider; incrementally compiles new material into Wiki pages.
- **`WikiMaintainer`** — background health-check / auto-compile of backlog (pure logic, no GUI/network binding).
- **`build_wiki_graph`** — pure function returning nodes/edges/danglers for the UI to render.
- **`schema`** — default rule set + `load/save_kb_schema`, configurable conflict policy.

## Core capabilities

| Capability | Notes |
|---|---|
| Incremental compile | Only compiles new/changed material; never re-runs the whole base |
| Conflict dual-record | Old & new views + sources/time/scope preserved; **never auto-overwritten** |
| Auto health-check | Reports broken links, orphan pages, conflict pages with detail |
| Relationship graph | Visualizes the knowledge network and its gaps |
| Obsidian-native | Pages carry YAML frontmatter; openable directly in Obsidian |
| Zero dependencies | Stdlib only; `import knowledgebase` from any project |

## Real-world deployment (not a demo)

The desktop AI pet `desktop_pet.py` (~9,000-line single-file app) **integrates this package as its knowledge engine**:
- `self.wiki = kb_pkg.WikiStore(base_dir=.../wiki)` owns knowledge persistence;
- bridges `KBCompiler` to an LLM for compile-on-ingest;
- a settings panel edits the Schema rules the LLM follows at compile time.

The production instance currently manages **71 pages** (concepts 39 / topics 16 / entities 15 / sources 1) — a real, running engine, not sample data.

## Companion components

- **Web console** (`knowledgebase-webui`, FastAPI + Vue 3): Wiki list / graph visualization / Schema editor / health report / **human conflict resolution** — five views, zero chart-library dependency (raw SVG).
- **Automations** (WorkBuddy): daily 07:30 incremental compile, Saturday 21:30 health-check — "checking" automated.

## Engineering metrics

- Core package **823 LOC** / 5 modules, **33 unit tests, zero regressions**.
- Zero runtime dependencies (stdlib only).
- Clean separation of concerns: all logic lives in the package; the web layer is a thin shell that does not re-implement business logic.

## Tech stack

Python 3.10+ (zero-dep core) · FastAPI (thin backend) · Vue 3 + Vite (SPA) · SVG (graph render) · WorkBuddy automations.

## Quick start

```bash
pip install -e .
```

```python
import knowledgebase as kb

wiki = kb.WikiStore(base_dir="./my_wiki")
wiki.write_page("concepts", "Vector DB", "RAG often pairs with [[RAG]].",
                sources=["some source"], tags=["retrieval"])

compiler = kb.KBCompiler(wiki, my_provider)  # my_provider: complete(prompt, on_done, on_error)
compiler.compile_item("New title", "source", "body…")

report = wiki.health()                        # broken links / orphans / conflicts
nodes, edges, danglers = kb.build_wiki_graph(wiki.index)
```

## Design trade-offs (stated honestly)

- **Single-user scale**: `WikiStore` loads `index.json` at startup; concurrent multi-writer would read a stale index. Positioned as a personal/single-machine KB, not a multi-tenant service.
- **LLM orchestration is external**: the package provides structure, storage, health-check and graph; the "compile" intelligence is injected via an external provider by an agent/automation. The package binds to no specific model service.
- **Conflicts are never auto-resolved**: the AI only flags conflicts and lists the diverging points; the final ruling stays with the human — the red line that prevents knowledge degradation.

## License

MIT
