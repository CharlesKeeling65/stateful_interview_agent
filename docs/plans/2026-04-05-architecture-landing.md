# Architecture Landing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fully land the existing mode/task-board/reviewer/human-gate/scenario architecture into the live interview flow end to end.

**Architecture:** Keep the current services and schemas, but move them onto the real runtime path. The main work is to thread project mode, rubric task board, scenario status, reviewer decisions, human gates, and transcript events through the graph nodes, persistence layer, APIs, and frontend without introducing another architecture layer.

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, Pydantic, React, TypeScript, pytest/unittest, Vite

### Task 1: Define missing end-to-end behavior in tests

**Files:**
- Modify: `tests/test_project_api_flow.py`
- Modify: `tests/test_collaboration_orchestration.py`
- Modify: `tests/test_run_trace_api.py`

**Step 1: Write failing integration tests**

Add tests that cover:
- default project mode is `understand_current_code`
- planner/reviewer pipeline influences the next turn
- default mode rejects modification-planning questions
- pending human gate is persisted and can be resolved through the API loop
- rubric task board affects next phase/priority
- scenario completeness blocks premature wrap-up
- debug API exposes mode/task-board/reviewer/gate/scenario state
- transcript and turn payloads expose collaboration rationale and events

**Step 2: Run focused tests to verify they fail**

Run: `uv run python -m unittest tests.test_project_api_flow tests.test_collaboration_orchestration tests.test_run_trace_api`

Expected: failures around reviewer integration, gate persistence, debug visibility, or transcript/event data

### Task 2: Land runtime orchestration in the graph

**Files:**
- Modify: `app/graphs/interview_state.py`
- Modify: `app/graphs/interview_graph.py`
- Modify: `app/graphs/interview_nodes.py`
- Modify: `app/services/question_planner.py`
- Modify: `app/services/question_reviewer.py`
- Modify: `app/services/question_validator.py`

**Step 1: Extend graph state for runtime orchestration**

Add state fields for:
- `agent_mode`
- `task_board`
- `review_result`
- `pending_gate`
- `scenario_status`
- `event_log`

**Step 2: Insert reviewer node into the live graph**

Change the graph from:
- `load_context -> decide_progress -> draft_question -> persist`

To:
- `load_context -> decide_progress -> plan_question -> review_plan -> draft_question -> persist`

With conditional routing so reviewer rejection can:
- trigger a pending gate
- override planner priority
- re-plan with reviewer feedback

**Step 3: Make question generation consume the reviewed plan**

Ensure the writer uses the reviewer-approved plan rather than re-running planner logic independently.

### Task 3: Make task board, scenario coverage, and gates authoritative

**Files:**
- Modify: `app/services/rubric_task_service.py`
- Modify: `app/services/scenario_service.py`
- Modify: `app/services/stage_manager.py`
- Modify: `app/graphs/interview_nodes.py`

**Step 1: Keep task board synchronized with turn evidence**

Update task board state whenever answers are persisted and use it when selecting the next focus.

**Step 2: Enforce phase progression with real completion signals**

Use task board and scenario status to gate stage transitions, especially:
- panorama -> architecture
- architecture -> code detail
- code detail -> use cases
- use cases -> wrap-up

**Step 3: Make human gates operational**

Persist pending gate JSON on the project, accept a user decision payload, clear or resolve the gate, and feed the resolution back into planning/reviewer logic.

### Task 4: Finish API, debug, transcript, and persistence wiring

**Files:**
- Modify: `app/api/routes/projects.py`
- Modify: `app/api/routes/debug.py`
- Modify: `app/models/project.py`
- Modify: `app/models/turn.py`
- Modify: `app/schemas/project.py`
- Modify: `app/schemas/turn.py`
- Modify: `app/schemas/debug.py`
- Modify: `app/services/transcript_event_service.py`
- Modify: `app/services/transcript_service.py`

**Step 1: Expose runtime state through APIs**

Return mode, pending gate, task board summary, scenario status, reviewer result, and rationale fields where appropriate.

**Step 2: Persist transcript event evidence**

Write AI question, human answer, human review, gate, drift, and phase events into turn event logs and surface them through transcript/debug responses.

### Task 5: Complete frontend human-in-the-loop UX

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useProject.ts`
- Modify: `frontend/src/components/StatusPanel.tsx`
- Modify: `frontend/src/components/TranscriptPanel.tsx`
- Modify: `frontend/src/components/TurnCard.tsx`

**Step 1: Surface pending human gates**

Show a compact gate panel with options and optional focus text, and submit the resolution through the existing next-step flow.

**Step 2: Improve transcript collaboration evidence**

Show mode, phase, gap/task target, human input, drift repair, and rationale cleanly without adding decorative UI.

### Task 6: Verify the landed behavior

**Files:**
- Modify as needed based on failures

**Step 1: Run focused backend tests**

Run: `uv run python -m unittest tests.test_project_api_flow tests.test_collaboration_orchestration tests.test_run_trace_api`

**Step 2: Run broader backend verification**

Run: `uv run python -m unittest`

**Step 3: Run frontend verification**

Run: `npm test -- --runInBand`

**Step 4: Run frontend build**

Run: `npm run build`

**Step 5: Fix remaining issues and re-run the failing command**

