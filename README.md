# Stateful Interview Agent

Stateful Interview Agent is a local full-stack application for running long-form, structured project interviews against a target codebase or system. Instead of generating disconnected follow-up prompts, it persists interview state across turns, advances through predefined stages, and produces one next question at a time from cumulative context.

## Project Overview

This project exists to solve a common orchestration problem: multi-turn technical interviews become repetitive, lose context, or drift away from a clear methodology when they are handled as plain prompt chaining. Here, each interview is stored as a durable project session with explicit turn history, stage tracking, transcript reconstruction, and status inspection.

Core capabilities:

- Create and manage persistent interview projects.
- Start a session and generate the first question.
- Submit each answer and generate the next stage-aware question.
- Persist turns and rebuild transcript/status at any time.
- Inspect the live runtime session through a local web UI.

## High-Level Architecture

- FastAPI exposes the project/session API.
- SQLAlchemy persists projects and interview turns in SQLite.
- LangGraph orchestrates the interview lifecycle using explicit state, nodes, and conditional edges.
- Vite + React + TypeScript + Tailwind CSS provide a local operator console for managing the interview loop.

The LangGraph thread identity is mapped to the project session via `thread_id = project-{project_id}`, which lets the orchestration semantics align with your durable project state.

## Feature Summary

- Project session management: create, list, select, and inspect saved project sessions.
- Stateful interview progression: each next question is generated from the full accumulated Q&A history.
- Stage-based question generation: interview flow advances across Panorama Mapping, Architecture Understanding, Code Detail Completion, and Use Cases & Scenarios.
- LangGraph orchestration: workflow logic is modeled as state + nodes + conditional edges.
- Runtime transcript/status UI: the frontend shows turn history, transcript preview, current stage, and progress indicators.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic Settings
- Frontend: Vite, React, TypeScript, Tailwind CSS v4
- LLM integration style: OpenAI-compatible API configuration through environment variables
- Persistence layer: SQLite
- Workflow/orchestration layer: LangGraph

## Project Structure

```text
stateful_interview_agent/
├─ app/
│  ├─ api/routes/              # FastAPI endpoints
│  ├─ core/                    # config, DB setup, LLM client wiring
│  ├─ graphs/                  # LangGraph state, nodes, graph composition
│  ├─ models/                  # SQLAlchemy persistence models
│  ├─ schemas/                 # request/response schemas
│  └─ services/                # question generation, transcript, lifecycle helpers
├─ frontend/
│  ├─ src/api/                 # typed frontend API layer
│  ├─ src/components/          # UI panels and form components
│  ├─ src/hooks/               # project/session orchestration hook
│  ├─ src/types/               # frontend API types
│  ├─ src/utils/               # display normalization, export, formatting helpers
│  └─ src/assets/              # local frontend assets
├─ src/stateful_interview_agent/
│  └─ __init__.py              # package entry stub
├─ pyproject.toml              # backend dependency and project config
├─ uv.lock                     # backend lockfile
└─ README.md
```

## Setup Instructions

### 1. Backend install

From the repository root:

```bash
uv sync
```

### 2. Frontend install

```bash
cd frontend
npm install
```

### 3. Environment variables

Create a root `.env` file:

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.scnet.cn/api/llm/v1
OPENAI_MODEL=MiniMax-M2.5
APP_NAME=Stateful Interview Agent
APP_ENV=dev
INTERVIEW_MIN_TURNS=35
INTERVIEW_MAX_TURNS=40
DATABASE_URL=sqlite:///./data/app.db
```

### 4. Start the backend

```bash
uv run uvicorn app.main:app --reload
```

Backend default address:

```text
http://127.0.0.1:8000
```

### 5. Start the frontend

```bash
cd frontend
npm run dev
```

Frontend default address:

```text
http://127.0.0.1:5173
```

## Environment Variables

Current settings are defined in [app/core/config.py](/Users/wyb/File/Programming/Git_Code/stateful_interview_agent/app/core/config.py).

- `OPENAI_API_KEY`: required; API key for the configured model provider.
- `OPENAI_BASE_URL`: optional; OpenAI-compatible base URL.
- `OPENAI_MODEL`: optional; model name for question generation.
- `APP_NAME`: optional; FastAPI title.
- `APP_ENV`: optional; environment label returned by `/health`.
- `INTERVIEW_MIN_TURNS`: optional; minimum target threshold before the goal is considered reached.
- `INTERVIEW_MAX_TURNS`: optional; hard cap for the interview.
- `DATABASE_URL`: optional; SQLAlchemy database URL. Defaults to local SQLite.

## Usage Walkthrough

1. Open the frontend in the browser.
2. Create a new project and provide the system prompt.
3. Click `Start Interview` to generate the first question.
4. Paste the latest answer into the composer.
5. Click `Submit Answer & Generate Next`.
6. Watch the turn cards, transcript preview, and runtime snapshot update.
7. Continue until the session reaches the finish condition.

## API Overview

Main endpoints:

- `POST /projects`: create a project session.
- `GET /projects`: list recent project sessions.
- `GET /projects/{id}`: fetch a single project.
- `POST /projects/{id}/start`: generate the first interview question.
- `POST /projects/{id}/next`: submit an answer and generate the next question.
- `GET /projects/{id}/status`: fetch current interview runtime status.
- `GET /projects/{id}/turns`: fetch ordered turns for the project.
- `GET /projects/{id}/transcript`: fetch reconstructed transcript text.
- `GET /health`: backend health check.

## Screenshots

The repo currently includes a general frontend asset:

- [frontend/src/assets/hero.png](/Users/wyb/File/Programming/Git_Code/stateful_interview_agent/frontend/src/assets/hero.png)

If you want real application screenshots later, a good convention is to store them under `docs/screenshots/` and link them from this section.

## Known Limitations / Future Work

- Transcript/question cleanup is currently frontend display normalization only; upstream generator formatting could still be improved.
- Transcript export is client-side only and does not create backend artifacts.
- Project selection persistence is lightweight browser storage only.
- There is no authentication or multi-user separation because the current target is a local operator workflow.
- LangGraph checkpoint persistence is in-memory; a durable external checkpointer would be a natural next improvement.
