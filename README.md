# Stateful Interview Agent

[中文说明 / Chinese README](README_zh.md)

Stateful Interview Agent is a local full-stack application for running structured, long-form project interviews against a target repository or system. Instead of treating each prompt as an isolated turn, it maintains durable interview state, plans the next question against explicit coverage goals, records human review signals, and exposes execution traces for each generation run.

## Overview

The project is designed for a "Code Understand" style deliverable: the goal is not to propose changes first, but to build a high-quality understanding transcript of an existing project through progressive questioning.

The current system is built around a rubric-aligned interview trajectory:

1. Panorama Mapping
2. Architecture Understanding
3. Code Detail Completion
4. Use Cases & Scenarios
5. Final Wrap-up

The default flow stays in `understand_current_code` mode, so later turns are constrained to explain the current implementation rather than drifting into redesign or refactor planning.

## Core Capabilities

- Persistent project/session management backed by SQLite.
- Stateful multi-turn interview progression with LangGraph orchestration.
- Stage-aware question generation with explicit planner and validator layers.
- Bilingual operator console with Chinese/English switching built into the top navigation.
- Older-turn summarization plus retrieval-oriented compact context assembly.
- Framework-aware coverage tracking across panorama, architecture, code detail, use cases, and human collaboration.
- Real human review input that can redirect the next question, rewrite the current question, and is preserved in the transcript.
- Current-question regeneration that replays the same planning/generation logic as `/next`, but overwrites the current question instead of advancing the turn.
- Per-turn question version history, diff views, regeneration counts, and human-intervention token accounting.
- Token usage tracking for generation and summarization operations.
- Structured JSONL logging and UI-oriented run traces for both `/next` generation and current-question regeneration.
- Local operator console for transcript review, run-trace inspection, analytics, export, and project management.

## Project Innovations

This project is not just a CRUD wrapper around an LLM. Its main innovations are in orchestration and inspectability:

- Rubric-aware interview planning  
  The interview is driven by an explicit understanding framework rather than plain prompt chaining. Coverage state, stage gates, planner decisions, and validators work together to keep the transcript aligned with a Code Understand deliverable.

- Durable LangGraph session semantics mapped to project sessions  
  LangGraph thread identity is bound to `project-{project_id}`, which lets workflow state, turn history, and session continuity line up cleanly with persistent project records.

- Retrieval-oriented question generation for long interviews  
  The system does not simply dump all previous turns back into the model. Older turns are summarized, branch/topic coverage is tracked, and only high-value context is retrieved for the next question.

- Hard separation between understanding mode and change-proposal drift  
  The default main flow is constrained to explain the current implementation. Planner, validator, and prompt assets explicitly resist drifting into "what should be changed" style questions.

- Real human-in-the-loop review as orchestration input  
  Human review is not only UI decoration. Verdicts, redirection, preferred focus, notes, stage correction, and phase-readiness signals are stored, surfaced in the transcript, and consumed by planning logic.

- Regeneration as a first-class replay of the main workflow  
  Rewriting the current question is not a side prompt. The system replays the same planner/validator chain used by `/next`, grounded on the previous answered turn, then persists the result as a new question version on the current turn.

- Versioned question history with inspectable diffs  
  Each turn can keep multiple generated question versions. The UI shows version history, textual diffs, regeneration counts, and human-intervention token cost so operators can understand exactly what changed after a review intervention.

- Stage correction with non-regression guardrails  
  Human stage corrections now update both project and turn state, and later automatic planning is clamped so it does not silently fall back to an earlier stage unless a human explicitly moves it again.

- Execution-trace UX built on a dedicated run model  
  Each `/next` call and current-question rewrite becomes a first-class run with step timing, status, and method metadata, so the operator can inspect active and historical orchestration behavior without reading raw logs.

- Layered observability  
  The project keeps both structured backend logging for engineering inspection and a separate UI-oriented run-trace abstraction for operator-facing execution visibility.

## High-Level Architecture

- FastAPI exposes project, turn, status, transcript, run-trace, and debug endpoints.
- SQLAlchemy models persist project sessions, turns, LLM usage, and generation runs in SQLite.
- LangGraph orchestrates `/next` generation via explicit state, nodes, and conditional control flow.
- Prompt assets are stored as typed YAML definitions and rendered through a prompt manager.
- Service-layer components handle planning, validation, coverage rebuilding, summarization, retrieval/context engineering, run tracing, and usage accounting.
- Vite + React + TypeScript + Tailwind CSS provide the local operator UI.

## Current Architecture Highlights

- `coverage_state` persists branch/topic evidence and framework coverage.
- `question_plan_json` stores why a question was selected, including phase, intent, framework gap, branch selection, and whether human review was applied.
- `question_versions` preserve every version of a question, including regeneration kind, review metadata, and usage attribution.
- `agent_runs` and `agent_run_steps` store UI-facing execution traces per generation run.
- Structured logs are written as JSONL under `logs/`, separate from the run-trace API contract.

## Question Generation Pipeline

The main `/next` workflow is intentionally layered so the system can spend fewer tokens on avoidable retries:

1. `load_context` restores the project, latest answered turn, coverage snapshot, and any active human-review signal.
2. `decide_progress` determines whether the interview should continue and which stage owns the next turn.
3. `plan_question` picks the next target branch / framework gap / repository artifact and can now emit `decomposition_mode` plus `subquestion_specs` for complex code-detail topics.
4. `review_question_plan` checks confidence, drift, mode compliance, and human gates before drafting.
5. `draft_question` rebuilds compact context, attaches repo grounding, drafts exactly one visible question, and persists any deferred code-detail sub-questions into the internal queue.
6. `persist` stores the new turn, version metadata, token usage, and run trace.

Inside question drafting, the code-detail path now includes two token-saving control points:

- Planner-level decomposition: complex implementation topics are split into queued single-focus follow-ups before the writer model has to generate them.
- Validator-driven repair: low-risk failures such as yes/no framing or line-number references are repaired locally before the system escalates to a second LLM rewrite or a full regenerate.

This keeps the UX at one visible question per turn while reducing both token waste and regeneration pressure.

## Recent Improvements

Recent repository changes have focused on making long interviews cheaper, more inspectable, and less repetitive:

- Repository-aware coverage balancing tracks file importance, exploration progress, and coverage gaps so code-detail planning rotates toward underexplored important files.
- Internal sub-question queues let the system unfold complex code-detail investigations across multiple turns without exposing compound questions to the operator.
- The code-detail prompt, validator, and postprocessor are now aligned around one visible question per turn.
- Current-question regeneration reuses the same planner / validator stack as `/next`, so manual correction stays consistent with the main workflow.
- Run-trace and debug surfaces expose queue state, file-coverage summaries, planner reasoning, and next-question context assembly.
- Question planning is now graph-aware: answered code-detail turns form a `question_graph`, open next-step candidates are held in an `investigation_frontier`, and planning can follow parent/sibling/upstream/downstream links instead of generating isolated prompts.
- Developer-intent balancing tracks real programmer investigation modes such as `trace_execution`, `investigate_failure`, `inspect_inputs_outputs`, and `follow_state_change`, then uses under-coverage pressure to avoid repetitive questioning angles.
- Network diagnostics now surface isolated-question ratio, repeated opening clusters, frontier depletion, intent collapse, and degradation reasons in both debug APIs and the analytics UI.

## Question Network Model

The code-detail system now treats long investigations as a lightweight question network instead of a flat list of unrelated turns:

- `question_graph`
  Stores answered question nodes plus graph edges derived from artifact continuity, follow-up cues, and same-concept transitions.
- `investigation_frontier`
  Stores ranked next-step candidates with `parent_node_id`, `relation_type`, `developer_intent`, `depth_kind`, and breadth metadata.
- `developer_intent_coverage`
  Tracks whether the interview is overusing one style of question and under-covering other high-value developer intents.
- `question_network_stats`
  Computes connectivity, breadth/depth transitions, intent diversity, dominant intent ratio, repeated opening clusters, and related diagnostics.

This remains an internal planning surface. The product contract is unchanged: the operator still sees exactly one visible question per turn.

## Feature Summary

- Project/session management
  - Create, list, select, rename, update, and delete interview projects.
  - Persist selected project context in the frontend.

- Interview orchestration
  - Start an interview and generate the first question.
  - Submit an answer and generate one next question at a time.
  - Rewrite the current question from the previous answered turn without advancing the turn number.
  - Enforce stage-aware, understanding-oriented question generation.
  - Prevent silent stage regression after a human has moved the interview forward.

- Coverage and memory
  - Summarize older answered turns.
  - Track framework gaps and branch evidence.
  - Reduce duplicate or semantically redundant questioning.

- Human collaboration
  - Collect human review signals from the UI.
  - Support stage correction, verdict redirection, preferred focus, and note-driven question rewrites.
  - Keep question version history, diffs, regeneration counts, and applied-change summaries visible in transcript history.

- Trace and observability
  - Track per-run execution steps and durations.
  - Expose cumulative generation time and run counts.
  - Emit structured JSONL logs for backend observability.
  - Inspect queue state, file coverage, planner reasoning, and next-question context through dedicated debug endpoints.

- Operator experience
  - Provide a bilingual workspace with stable top navigation.
  - Offer a dedicated analytics page with token, runtime, regeneration, and stage-movement visualizations.

## Tech Stack

- Backend
  - FastAPI
  - SQLAlchemy
  - Pydantic / Pydantic Settings
  - SQLite

- Workflow / orchestration
  - LangGraph

- LLM integration
  - OpenAI-compatible Chat Completions API
  - Anthropic provider support
  - OpenCode provider support
  - Optional embedding-based duplicate checking

- Frontend
  - Vite
  - React
  - TypeScript
  - Tailwind CSS v4

## Project Structure

```text
stateful_interview_agent/
├─ app/
│  ├─ api/routes/              # FastAPI routes
│  ├─ core/                    # config, DB, LLM client, app wiring
│  ├─ graphs/                  # LangGraph state, nodes, graph assembly
│  ├─ logging/                 # structured JSONL logging subsystem
│  ├─ models/                  # SQLAlchemy models
│  ├─ prompts/                 # typed prompt assets and renderer
│  ├─ schemas/                 # request/response schemas
│  └─ services/                # planner, validator, coverage, retrieval, run trace, usage
├─ frontend/
│  ├─ src/api/                 # typed frontend API client
│  ├─ src/components/          # UI panels, transcript cards, trace sections
│  ├─ src/hooks/               # session orchestration hooks
│  ├─ src/types/               # frontend API contracts
│  └─ src/utils/               # formatting, exports, normalization
├─ tests/                      # backend tests
├─ .ref_docs/                  # local reference material
├─ logs/                       # runtime logs (gitignored)
├─ pyproject.toml
├─ uv.lock
├─ README.md
└─ README_zh.md
```

## Reference Docs

The repository currently keeps local reference material under [`.ref_docs/`](.ref_docs/). The most concrete checked-in example is:

- [`.ref_docs/问题.md`](.ref_docs/%E9%97%AE%E9%A2%98.md)  
  A structured interview-question reference that now also notes the newer workflow features: bilingual UI, current-question regeneration, question version history, diff inspection, and analytics-oriented operator feedback.

Additional implementation notes for recent product iterations are stored under [`docs/plans/`](docs/plans/) as change-focused planning records.

## Setup

### 1. Install backend dependencies

```bash
uv sync
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
```

### 3. Configure environment variables

Create a root `.env` file:

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
QUESTION_GRAPH_ENABLED=true
GRAPH_FRONTIER_PLANNING_ENABLED=true
DEVELOPER_INTENT_BALANCING_ENABLED=true
GRAPH_CONTINUITY_VALIDATION_ENABLED=true
```

Feature flags for the question-network layer:

- `QUESTION_GRAPH_ENABLED`: rebuild graph/frontier/intent/network stats inside `coverage_state`.
- `GRAPH_FRONTIER_PLANNING_ENABLED`: let the planner prefer connected frontier candidates before older branch/file heuristics.
- `DEVELOPER_INTENT_BALANCING_ENABLED`: apply under-coverage pressure so planning rotates across developer-like question intents.
- `GRAPH_CONTINUITY_VALIDATION_ENABLED`: require code-detail questions to carry graph-linkage metadata such as `developer_intent` and `relation_type`.

### 4. Start the backend

```bash
uv run uvicorn app.main:app --reload
```

Backend default URL:

```text
http://127.0.0.1:8000
```

### 5. Start the frontend

```bash
cd frontend
npm run dev
```

Frontend default URL:

```text
http://127.0.0.1:5173
```

### 6. Start both backend and frontend together

If you want one development entrypoint from the repo root, use:

```bash
uv run python main.py
```

This root-level `main.py` starts both:

- the FastAPI backend with the current Python interpreter
- the Vite frontend with `npm run dev`

This is the safest way to run the project inside a `uv`-managed environment because:

- `uv run python main.py` uses the project environment created by `uv sync`
- the backend process inherits that same interpreter via `sys.executable`
- you do not need to manually activate `.venv` first

If you have already activated the environment yourself, this also works:

```bash
python main.py
```

or directly:

```bash
.venv/bin/python main.py
```

On Windows PowerShell, the equivalent is typically:

```powershell
uv run python .\main.py
```

## Development Workflow

A practical local workflow for this repository is:

1. Run `uv sync` at the repo root and `npm install` under `frontend/`.
2. Start the stack with either separate backend/frontend commands or `uv run python main.py`.
3. Create a project in the UI, optionally attach repository context, and use the debug routes to inspect coverage and planner behavior while iterating.
4. Run targeted backend tests for orchestration logic and frontend tests or builds for UI changes.
5. Use run traces plus debug endpoints for workflow inspection, and use JSONL logs for backend-level debugging.

When debugging question quality, the highest-signal surfaces are:

- `/debug/projects/{project_id}/state`
  Inspect `question_graph`, `investigation_frontier`, `developer_intent_coverage`, queue state, and repository coverage in one snapshot.
- `/debug/projects/{project_id}/question-network-summary`
  Inspect `connected_ratio`, `frontier_count`, `repeat_opening_clusters`, `top_intents`, `undercovered_intents`, `top_relation_types`, `diagnostic_flags`, and `degradation_reasons`.
- Analytics UI
  Inspect the `Question network` panel for isolated-question count, frontier health, top intents, relation mix, and network diagnostics without reading raw JSON.

Useful success metrics after graph-aware planning is enabled:

- low isolated-question count relative to node count
- sustained non-zero frontier count during deep code-detail work
- multiple developer intents represented instead of one dominant angle
- repeated opening clusters kept under control
- visible breadth and depth transitions across related artifacts rather than repetitive same-file loops

Useful commands:

```bash
uv run python -m unittest tests.test_framework_orchestration tests.test_interview_nodes -v
uv run python -m unittest tests.test_question_planner tests.test_question_generation_repair -v
cd frontend && npm test
cd frontend && npm run build
```

## Packaging

The project can now be packaged for Windows and Ubuntu Linux without requiring a preinstalled Python runtime.

Packaging model:

- Build the frontend into static files.
- Bundle the FastAPI server, prompt assets, and frontend build with PyInstaller.
- Keep `.env`, `data/`, and `logs/` outside the executable so operators can reconfigure the app after packaging.

### Runtime behavior

- Source mode still works as before: run the backend from the repo root and use the Vite dev server.
- Packaged mode uses the executable directory as the writable runtime root.
- Relative paths like `./data/app.db` and `./logs` are resolved against that runtime root.
- If `frontend/dist` is bundled, FastAPI serves it directly and the frontend falls back to same-origin API calls.

### Shared build steps

1. Build the frontend:

```bash
cd frontend
npm install
npm run build
cd ..
```

1. Install build tooling:

```bash
uv sync --extra build
```

### Windows packaging

1. Build the Windows bundle on Windows:

```bash
uv run pyinstaller packaging/windows/stateful_interview_agent.spec
```

1. Copy your runtime files next to `dist/StatefulInterviewAgent/StatefulInterviewAgent.exe`:

```text
dist/StatefulInterviewAgent/
├─ StatefulInterviewAgent.exe
├─ .env
├─ data/
└─ logs/
```

### Ubuntu Linux packaging

1. Build the Linux bundle on Ubuntu Linux. Use an older baseline such as Ubuntu 22.04 rather than `ubuntu-latest`, otherwise PyInstaller may bundle a `libpython` that requires a newer glibc than the target machine provides:

```bash
uv run pyinstaller packaging/linux/stateful_interview_agent.spec
```

1. Copy your runtime files next to `dist/StatefulInterviewAgent/StatefulInterviewAgent`:

```text
dist/StatefulInterviewAgent/
├─ StatefulInterviewAgent
├─ .env
├─ data/
└─ logs/
```

### Linux runtime example

After downloading `StatefulInterviewAgent-linux.tar.gz` from GitHub Releases:

```bash
tar -xzf StatefulInterviewAgent-linux.tar.gz
cd StatefulInterviewAgent
cp .env.example .env
chmod +x StatefulInterviewAgent
./StatefulInterviewAgent
```

By default, the packaged Linux app:

- reads configuration from `./.env`
- stores SQLite data under `./data/`
- writes logs under `./logs/`

If you want to override those defaults:

```bash
STATEFUL_AGENT_ENV_FILE=/etc/stateful-interview-agent.env \
STATEFUL_AGENT_RUNTIME_DIR=/var/lib/stateful-interview-agent \
./StatefulInterviewAgent
```

### GitHub Actions release artifacts

- Windows workflow uploads the `StatefulInterviewAgent-windows` artifact and publishes `StatefulInterviewAgent-windows.zip` on tagged releases.
- Linux workflow uploads the `StatefulInterviewAgent-linux` artifact and publishes `StatefulInterviewAgent-linux.tar.gz` on tagged releases.

### Configurable environment files

- Default source-mode env file: repo-root `.env`
- Default packaged-mode env file: executable-directory `.env`
- Override path explicitly with `STATEFUL_AGENT_ENV_FILE`
- Override the writable runtime directory with `STATEFUL_AGENT_RUNTIME_DIR`

## Environment Variables

Defined in [app/core/config.py](app/core/config.py).

- `OPENAI_API_KEY`: required API key.
- `OPENAI_BASE_URL`: OpenAI-compatible API base URL.
- `OPENAI_MODEL`: chat completions model used for question generation and summarization.
- `OPENAI_EMBEDDING_MODEL`: optional embedding model for semantic duplicate checks.
- `DUPLICATE_GUARD_USE_EMBEDDINGS`: enable optional embedding-assisted duplicate detection.
- `DUPLICATE_GUARD_EMBEDDING_THRESHOLD`: cosine-similarity threshold for embedding duplicate checks.
- `APP_HOST`: backend listen host, used by the packaged launcher.
- `APP_PORT`: backend listen port, used by the packaged launcher.
- `INTERVIEW_MIN_TURNS`: minimum interview target before the goal is considered reached.
- `INTERVIEW_MAX_TURNS`: hard upper bound for interview turns.
- `INTERVIEW_PANORAMA_TURNS`: explicit panorama-stage turn budget.
- `INTERVIEW_ARCHITECTURE_TURNS`: explicit architecture-stage turn budget.
- `INTERVIEW_CODE_DETAIL_MIN_TURNS`: explicit lower bound for code-detail turns.
- `INTERVIEW_CODE_DETAIL_MAX_TURNS`: explicit upper bound for code-detail turns.
- `INTERVIEW_USE_CASE_TURNS`: explicit use-case-stage turn budget.
- `QUESTION_GRAPH_ENABLED`: enable graph reconstruction and network diagnostics in `coverage_state`.
- `GRAPH_FRONTIER_PLANNING_ENABLED`: enable graph-frontier ranking during code-detail planning.
- `DEVELOPER_INTENT_BALANCING_ENABLED`: enable intent under-coverage bonuses during frontier ranking.
- `GRAPH_CONTINUITY_VALIDATION_ENABLED`: require graph metadata on code-detail questions.
- `DATABASE_URL`: SQLAlchemy database URL.
- `LOG_LEVEL`: backend log level.
- `LOG_DIR`: log root directory.
- `LOG_LLM_PAYLOADS`: whether to log LLM payload previews.
- `LOG_ARTIFACTS_ENABLED`: whether to dump larger prompt/context artifacts.
- `LOG_PRETTY_JSON`: JSON formatting option for local debugging.
- `LOG_TEXT_PREVIEW_CHARS`: text preview length stored in logs.
- `STATEFUL_AGENT_ENV_FILE`: optional absolute path to an external env file.
- `STATEFUL_AGENT_RUNTIME_DIR`: optional writable runtime root for `.env`, SQLite, and logs.

## Typical Workflow

1. Create a project with a meaningful title and system prompt.
2. Optionally configure repository grounding so the planner can target real files and symbols.
3. Start the interview to generate `Q1`.
4. Review the initial stage, transcript baseline, and status card in the UI.
5. Paste the latest answer into the composer.
6. Optionally provide a human review signal:
   - sufficient / insufficient / drifted
   - continue / redirect
   - preferred next focus
   - note
   - stage correction
   - phase ready
7. Submit the answer and watch the execution trace update live.
8. If the newly drafted current question is still not right, rewrite it from the previous answer without advancing the turn:
   - store the review on the current turn
   - optionally correct the stage
   - generate a new question version
   - inspect the applied-change summary and version diff
9. Review the generated question, transcript state, analytics panel, status panel, run trace, queue summary, and repository-coverage summary.
10. Continue until the interview reaches wrap-up readiness.

## Debugging And Inspection

The repository exposes two complementary inspection layers:

- Structured logs in `logs/` for backend engineering and incident-style debugging.
- Run-trace plus debug endpoints for operator-facing workflow inspection.

The most useful inspection routes during development are:

- `GET /debug/projects/{id}/coverage`
  Full coverage state, including framework gaps, branch evidence, queue state, and repository file coverage metrics.
- `GET /debug/projects/{id}/queue-summary`
  Compact summary of queued internal sub-questions during complex code-detail work.
- `GET /debug/projects/{id}/file-coverage-summary`
  Importance vs exploration ranking for tracked repository files.
- `POST /debug/projects/{id}/next-context`
  Preview the assembled context bundle and planner decision used to draft the next question.
- `GET /projects/{id}/runs/latest`
  The latest orchestration run trace with step labels, timings, and status.

This split is intentional: logs are append-only backend artifacts, while run traces and debug responses are stable API contracts for tooling and the UI.

## API Overview

### Main project/session endpoints

- `POST /projects`  
  Create a project session.

- `GET /projects`  
  List recent projects.

- `GET /projects/{id}`  
  Fetch a project.

- `PATCH /projects/{id}`  
  Update project metadata such as title or system prompt.

- `DELETE /projects/{id}`  
  Delete a project session.

### Interview flow endpoints

- `POST /projects/{id}/start`  
  Generate the first question.

- `POST /projects/{id}/answer`  
  Persist an answer only.

- `POST /projects/{id}/next`  
  Persist an answer and generate the next question.

- `POST /projects/{id}/turns/{turn_id}/regenerate-question`  
  Replay next-question generation from the previous answered turn, overwrite the current question as a new version, and return `applied_changes` describing what actually took effect.

- `GET /projects/{id}/turns`  
  Fetch ordered turn history, including question-version metadata, regeneration counters, and human-intervention token summaries.

- `GET /projects/{id}/transcript`  
  Fetch reconstructed transcript text.

- `GET /projects/{id}/status`  
  Fetch runtime/session status, usage summary, and cumulative generation timing.

### Run trace endpoints

- `GET /projects/{id}/runs`
- `GET /projects/{id}/runs/latest`
- `GET /projects/{id}/runs/{run_id}`

These endpoints expose UI-oriented execution traces for each generation run, including both `/next` and current-question regeneration.

### Debug endpoints

- `GET /debug/llm`
- `GET /debug/projects/{id}/coverage`
- `POST /debug/projects/{id}/next-context`

These are useful for inspecting coverage state, planner decisions, prompt rendering, and context assembly.

## Logs and Runtime Inspection

Structured backend logs are written under `logs/` as JSONL files. Typical categories include:

- `logs/requests/`
- `logs/workflow/`
- `logs/llm/`
- `logs/retrieval/`
- `logs/persistence/`
- `logs/errors/`

Use logs for engineering inspection. Use the run-trace API/UI for operator-facing execution progress.

## Screenshots

The repository currently contains a general frontend asset:

- [frontend/src/assets/hero.png](frontend/src/assets/hero.png)

If you want real product screenshots later, a good convention is `docs/screenshots/`.

## Known Limitations / Future Work

- SQLite keeps the setup simple, but a more durable production deployment would benefit from a stronger database and migration story.
- Duplicate-question suppression is much stronger than before, but still relies on a hybrid of structural rules and optional embeddings rather than full semantic planning.
- The default system is optimized for local operator use; authentication and multi-user isolation are intentionally out of scope.
- Run-trace updates currently use polling rather than SSE/WebSocket streaming.
- The framework coverage model is rubric-oriented and inspectable, but still partly heuristic rather than fully learned.
- Historical records created before the latest regeneration fixes may still need normalization when read back from the database; the API now repairs common versioning artifacts, but the legacy data model remains visible in older projects.
