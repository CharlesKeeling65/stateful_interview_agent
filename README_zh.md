# Stateful Interview Agent

[English README](README.md)

Stateful Interview Agent 是一个本地全栈应用，用于针对目标仓库或系统执行结构化、长上下文的软件项目访谈。它不是把每一轮都当成孤立提示词，而是持续维护访谈状态、依据覆盖缺口规划下一问、记录人工评审信号，并为每次生成过程提供可检查的执行轨迹。

## 项目简介

这个项目的目标是支撑一种更接近“Code Understand”交付物的访谈方式：核心任务不是先讨论“应该怎么改”，而是通过逐步追问，形成一份对现有项目实现足够深入、结构清晰、可交付的理解型 transcript。

当前系统围绕如下阶段组织访谈：

1. 全景地图构建
2. 架构理解
3. 代码细节补全
4. 用例与场景
5. 最终收口

默认主流程始终运行在 `understand_current_code` 模式下，因此后期问题会被约束为解释“当前代码如何工作”，而不是滑向重构设计或修改建议。

## 核心能力

- 基于 SQLite 的持久化项目/会话管理。
- 基于 LangGraph 的多轮状态化访谈编排。
- 带 planner 和 validator 的阶段感知问题生成。
- 内置中英文切换的双语 operator console。
- 长访谈下的历史摘要与检索式上下文压缩。
- 面向 rubric 的 coverage state，覆盖 panorama / architecture / code detail / use cases / human collaboration。
- 真正进入工作流的人类评审输入，而不是只停留在 UI 层的装饰信息。
- 支持“基于上一轮回答重写当前问题”，而不是只能一路推进到下一问。
- 每个 turn 支持问题版本历史、版本差异对比、重生成次数和人工介入 token 统计。
- 对提问、摘要等 LLM 调用的 token 使用统计。
- 针对 `/next` 和“重写当前问题”两类流程的 run trace / execution trace。
- 本地 operator console，用于检查 transcript、状态、统计页、执行轨迹和导出结果。

## 项目创新点

本项目的创新主要不在“调一个 prompt”，而在于把代码理解型访谈做成了可编排、可检查、可交付的系统：

- 面向 rubric 的访谈编排  
  系统不是简单根据上一轮回答续写，而是围绕显式的理解框架推进。coverage state、阶段控制、planner、validator 一起约束访谈节奏，使输出更接近真正的 Code Understand 交付物。

- 将 LangGraph 的 durable execution 语义映射到项目会话  
  通过 `thread_id = project-{project_id}` 把图执行线程和项目会话绑定，使工作流状态、轮次历史和持久化项目语义对齐。

- 面向长访谈的检索式上下文工程  
  系统不会把全部历史原文直接塞回模型，而是结合历史摘要、branch/topic evidence、coverage gap 和当前阶段，选择更高价值的上下文来生成下一问。

- 对“理解当前代码”和“提出修改方案”做硬分离  
  默认主流程严格保持在 `understand_current_code` 模式。planner、validator 和 prompt 资产都明确限制问题不要滑向“应该改什么、怎么重构、怎么改测试”。

- 将 human-in-the-loop 变成真实工作流输入  
  用户在前端输入的 sufficiency、redirect、preferred focus、note、stage correction、phase ready 等信号会被持久化、展示，并直接影响问题规划。

- 将“重生成当前问题”改造成主流程回放  
  当前问题的重写不再是旁路 prompt，而是基于“上一轮已回答内容”重新跑一遍 `/next` 的规划与校验链路，只是不新增 turn，而是把结果写成当前 turn 的新版本。

- 版本化问题历史与差异检查  
  每一问都可以保留多个问题版本。前端可以查看版本历史、前后 diff、重生成次数，以及人工介入带来的 token 成本，便于追溯人工纠偏是否真正生效。

- 阶段纠偏与防回退约束  
  人工纠正阶段后，项目与 turn 的阶段状态会同步更新，后续自动规划也不会再悄悄回退到更早阶段，除非再次进行人工纠偏。

- 面向 UI 的运行轨迹模型  
  每次 `/next` 和“重写当前问题”都会被建模为一个独立 run，包含 step、状态、耗时、method/tool 信息，让操作者可以像看 agent trace 一样理解系统正在做什么。

- 双层可观测性  
  后端保留结构化 JSONL 日志，便于工程排查；同时又提供独立的 run-trace API，专门服务前端执行态展示，而不是把原始日志直接暴露给 UI。

## 高层架构

- FastAPI 提供项目、turn、status、transcript、run trace 和 debug 接口。
- SQLAlchemy 在 SQLite 中持久化项目会话、访谈轮次、LLM usage 和 generation run。
- LangGraph 负责 `/next` 的状态、节点和条件流编排。
- Prompt 资产以带类型约束的 YAML 文件管理，并通过 prompt manager 渲染。
- 服务层负责 planner、validator、coverage rebuild、摘要、上下文检索、run trace 和 usage tracking。
- Vite + React + TypeScript + Tailwind CSS 提供本地 operator UI。

## 当前架构亮点

- `coverage_state` 同时保存 branch/topic evidence 和 rubric-oriented framework coverage。
- `question_plan_json` 会保存“为什么选这题”，包括 phase、intent、framework gap、branch 选择和 human review 是否生效。
- `question_versions` 会保留问题版本历史，包括版本来源、人工评审、token 使用和差异对比基础数据。
- `agent_runs` / `agent_run_steps` 为每次 `/next` 生成提供 UI 友好的执行轨迹。
- 后端结构化日志写入 `logs/`，与 run-trace API 分层，不直接拿日志当 UI 协议。

## 功能概览

- 项目/会话管理
  - 创建、列出、选择、重命名、更新和删除项目。
  - 前端持久化当前选择的项目。

- 访谈编排
  - 启动访谈并生成第一问。
  - 提交回答并按轮生成下一问。
  - 基于上一轮回答重写当前问题，但不推进 turn 编号。
  - 按阶段约束提问，并保持在“理解当前代码”模式。
  - 人工推进到更后阶段后，自动流程不会静默回退。

- 记忆与覆盖
  - 对旧回答生成摘要。
  - 跟踪 framework gap 和 branch evidence。
  - 尽量避免语义重复提问。

- 人机协作
  - 前端收集 human review signal。
  - 支持阶段纠偏、方向重定向、焦点控制和 note 驱动的问题重写。
  - transcript 中可见版本历史、diff、人工介入摘要和实际生效项。

- 轨迹与可观测性
  - 展示每次 run 的步骤与耗时。
  - 展示累计生成耗时与 run 次数。
  - 输出结构化 JSONL backend logs。

- 操作台体验
  - 顶部导航统一承载页面切换和语言切换。
  - 新增 analytics 页，以图表方式展示 token、耗时、重生成压力和阶段迁移。

## 技术栈

- 后端
  - FastAPI
  - SQLAlchemy
  - Pydantic / Pydantic Settings
  - SQLite

- 工作流 / 编排
  - LangGraph

- LLM 集成
  - OpenAI-compatible Chat Completions API
  - 可选 embedding 辅助重复问题判重

- 前端
  - Vite
  - React
  - TypeScript
  - Tailwind CSS v4

## 项目结构

```text
stateful_interview_agent/
├─ app/
│  ├─ api/routes/              # FastAPI 路由
│  ├─ core/                    # 配置、数据库、LLM client、应用初始化
│  ├─ graphs/                  # LangGraph state、nodes、graph 组装
│  ├─ logging/                 # 结构化 JSONL 日志子系统
│  ├─ models/                  # SQLAlchemy 模型
│  ├─ prompts/                 # Prompt 资产与渲染层
│  ├─ schemas/                 # 请求/响应 schema
│  └─ services/                # planner、validator、coverage、retrieval、run trace 等
├─ frontend/
│  ├─ src/api/                 # 类型化 API client
│  ├─ src/components/          # 面板、turn 卡片、trace 展示组件
│  ├─ src/hooks/               # 前端会话 orchestration hooks
│  ├─ src/types/               # 前端类型定义
│  └─ src/utils/               # 格式化、导出、文本清洗
├─ tests/                      # 后端测试
├─ .ref_docs/                  # 本地参考文档
├─ logs/                       # 运行日志目录（gitignored）
├─ pyproject.toml
├─ uv.lock
├─ README.md
└─ README_zh.md
```

## 参考文档

当前仓库里真实存在的本地参考资料位于 [`.ref_docs/`](.ref_docs/) 下。与当前产品能力最直接相关的是：

- [`.ref_docs/问题.md`](.ref_docs/%E9%97%AE%E9%A2%98.md)  
  一个结构化访谈问题样例文档，现已补充说明双语 UI、当前问题重写、版本历史、diff 检查和 analytics 视角等新能力。

最近几轮功能迭代的实现思路与改造计划则记录在 [`docs/plans/`](docs/plans/) 中。

## 安装与启动

### 1. 安装后端依赖

```bash
uv sync
```

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 配置环境变量

在仓库根目录创建 `.env`：

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.scnet.cn/api/llm/v1
OPENAI_MODEL=MiniMax-M2.5
OPENAI_EMBEDDING_MODEL=
DUPLICATE_GUARD_USE_EMBEDDINGS=false
DUPLICATE_GUARD_EMBEDDING_THRESHOLD=0.9
APP_NAME=Stateful Interview Agent
APP_ENV=dev
INTERVIEW_MIN_TURNS=36
INTERVIEW_MAX_TURNS=37
INTERVIEW_PANORAMA_TURNS=1
INTERVIEW_ARCHITECTURE_TURNS=2
INTERVIEW_CODE_DETAIL_MIN_TURNS=31
INTERVIEW_CODE_DETAIL_MAX_TURNS=32
INTERVIEW_USE_CASE_TURNS=2
DATABASE_URL=sqlite:///./data/app.db
LOG_LEVEL=INFO
LOG_DIR=./logs
LOG_LLM_PAYLOADS=true
LOG_ARTIFACTS_ENABLED=false
LOG_PRETTY_JSON=false
LOG_TEXT_PREVIEW_CHARS=240
```

### 4. 启动后端

```bash
uv run uvicorn app.main:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

### 5. 启动前端

```bash
cd frontend
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

## Windows 打包

这个项目现在可以打成 Windows 可执行分发包，目标机器不需要预装 Python。

打包形态如下：

- 先把前端构建成静态文件。
- 用 PyInstaller 打包 FastAPI 服务、prompt 资产和前端构建产物。
- 将 `.env`、`data/`、`logs/` 保持在 exe 外部，便于交付后继续修改配置。

### 运行时行为

- 源码模式保持不变：在仓库根目录启动后端，同时用 Vite dev server 跑前端。
- 打包模式下，可执行文件所在目录会作为默认可写运行根目录。
- `./data/app.db`、`./logs` 这类相对路径会自动解析到该运行根目录下。
- 如果 `frontend/dist` 被打进包里，FastAPI 会直接托管前端静态资源，前端也会优先走同源 API。

### 打包步骤

1. 构建前端：

```bash
cd frontend
npm install
npm run build
cd ..
```

2. 安装打包依赖：

```bash
uv sync --extra build
```

3. 在 Windows 上执行打包：

```bash
uv run pyinstaller packaging/windows/stateful_interview_agent.spec
```

如果需要 Linux 发布包，请不要在过新的发行版或 `ubuntu-latest` 上构建。PyInstaller 会把当前环境的 `libpython` 一起带进产物，构建机 glibc 太新时，目标机器会报 `GLIBC_x.y not found`。建议固定在 Ubuntu 22.04 这类更低基线环境上执行 Linux 打包。

4. 将运行时文件放到 `dist/StatefulInterviewAgent/StatefulInterviewAgent.exe` 同目录：

```text
dist/StatefulInterviewAgent/
├─ StatefulInterviewAgent.exe
├─ .env
├─ data/
└─ logs/
```

### 可配置的环境文件

- 源码模式默认读取仓库根目录 `.env`
- 打包模式默认读取 exe 同目录 `.env`
- 可通过 `STATEFUL_AGENT_ENV_FILE` 显式指定 env 文件路径
- 可通过 `STATEFUL_AGENT_RUNTIME_DIR` 显式指定可写运行目录

## 环境变量说明

定义位置见 [app/core/config.py](app/core/config.py)。

- `OPENAI_API_KEY`：必填，模型服务 API key。
- `OPENAI_BASE_URL`：OpenAI-compatible base URL。
- `OPENAI_MODEL`：问题生成与摘要使用的 chat model。
- `OPENAI_EMBEDDING_MODEL`：可选，embedding 判重模型。
- `DUPLICATE_GUARD_USE_EMBEDDINGS`：是否开启 embedding 辅助判重。
- `DUPLICATE_GUARD_EMBEDDING_THRESHOLD`：embedding 相似度阈值。
- `APP_HOST`：后端监听地址，打包启动器会读取它。
- `APP_PORT`：后端监听端口，打包启动器会读取它。
- `INTERVIEW_MIN_TURNS`：达到最小访谈目标的轮次下限。
- `INTERVIEW_MAX_TURNS`：访谈轮次硬上限。
- `INTERVIEW_PANORAMA_TURNS`：全景阶段显式轮次配置。
- `INTERVIEW_ARCHITECTURE_TURNS`：架构阶段显式轮次配置。
- `INTERVIEW_CODE_DETAIL_MIN_TURNS`：代码细节阶段最少轮次。
- `INTERVIEW_CODE_DETAIL_MAX_TURNS`：代码细节阶段最多轮次。
- `INTERVIEW_USE_CASE_TURNS`：用例阶段显式轮次配置。
- `DATABASE_URL`：数据库连接串。
- `LOG_LEVEL`：日志级别。
- `LOG_DIR`：日志目录。
- `LOG_LLM_PAYLOADS`：是否记录 LLM payload preview。
- `LOG_ARTIFACTS_ENABLED`：是否输出更大的 prompt/context artifact。
- `LOG_PRETTY_JSON`：本地调试用 JSON 格式开关。
- `LOG_TEXT_PREVIEW_CHARS`：日志文本预览长度。
- `STATEFUL_AGENT_ENV_FILE`：可选，显式指定外部 env 文件路径。
- `STATEFUL_AGENT_RUNTIME_DIR`：可选，显式指定可写运行目录。

## 典型使用流程

1. 创建一个项目，填写有意义的标题和 system prompt。
2. 启动访谈，生成 `Q1`。
3. 将回答粘贴到 composer 中。
4. 可选填写 human review signal：
   - sufficient / insufficient / drifted
   - continue / redirect
   - preferred next focus
   - note
   - stage correction
   - phase ready
5. 提交答案，观察 execution trace 实时更新。
6. 如果当前生成的问题仍然不合适，可以基于上一轮回答重写当前问题，而不推进 turn：
   - 保存本轮人工评审
   - 可选纠正阶段
   - 生成当前问题的新版本
   - 检查实际生效项和版本 diff
7. 检查当前问题、transcript、analytics、status panel 和 run trace。
8. 持续推进，直到系统进入 wrap-up readiness。

## API 概览

### 主项目/会话接口

- `POST /projects`  
  创建项目。

- `GET /projects`  
  获取最近项目列表。

- `GET /projects/{id}`  
  获取单个项目。

- `PATCH /projects/{id}`  
  更新项目标题或 system prompt。

- `DELETE /projects/{id}`  
  删除项目。

### 访谈流程接口

- `POST /projects/{id}/start`  
  生成第一问。

- `POST /projects/{id}/answer`  
  仅保存回答。

- `POST /projects/{id}/next`  
  保存回答并生成下一问。

- `POST /projects/{id}/turns/{turn_id}/regenerate-question`  
  基于上一轮已回答内容重跑问题生成流程，覆盖当前问题并追加一个新版本，同时返回 `applied_changes` 说明哪些人工纠偏真正生效。

- `GET /projects/{id}/turns`  
  获取 turn 历史，包括问题版本信息、重生成计数和人工介入 token 汇总。

- `GET /projects/{id}/transcript`  
  获取 transcript 文本。

- `GET /projects/{id}/status`  
  获取运行状态、usage summary 和累计生成耗时。

### Run Trace 接口

- `GET /projects/{id}/runs`
- `GET /projects/{id}/runs/latest`
- `GET /projects/{id}/runs/{run_id}`

这些接口服务于前端 execution trace 展示，覆盖 `/next` 和“重写当前问题”两类运行。

### Debug 接口

- `GET /debug/llm`
- `GET /debug/projects/{id}/coverage`
- `POST /debug/projects/{id}/next-context`

可用于检查 coverage、planner 决策、prompt 渲染和上下文组装。

## 日志与运行检查

后端结构化日志会以 JSONL 写入 `logs/`，常见目录包括：

- `logs/requests/`
- `logs/workflow/`
- `logs/llm/`
- `logs/retrieval/`
- `logs/persistence/`
- `logs/errors/`

工程排查用日志；操作者查看执行进度更适合 run-trace UI/API。

## 截图

仓库中当前包含一个通用前端资源：

- [frontend/src/assets/hero.png](frontend/src/assets/hero.png)

如果后续加入真实产品截图，建议统一放在 `docs/screenshots/`。

## 已知限制 / 后续方向

- 目前使用 SQLite，适合本地开发与单人使用；若要走更长期的生产部署，需要更强数据库和迁移方案。
- 重复问题抑制已经比早期版本强很多，但依然是“结构化规则 + 可选 embedding”的混合方案，不是完整语义规划系统。
- 默认目标是本地 operator workflow，因此没有做认证和多用户隔离。
- active run 目前使用 polling，而不是 SSE / WebSocket。
- framework coverage 模型已经明显更贴近 rubric，但仍然部分依赖启发式，而非完全 learned planner。
- 对于旧项目中在早期版本产生的脏历史数据，API 已经会在读取时自动做一部分归一化修复，但底层存量数据仍可能保留早期版本痕迹。
