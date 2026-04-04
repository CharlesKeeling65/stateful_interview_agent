# Current Question Regeneration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let humans review the currently displayed unanswered question, regenerate that same turn without advancing the interview, preserve all question versions, and track regeneration counts plus human-intervention token cost.

**Architecture:** Add a per-turn question-version history model and a dedicated regeneration endpoint for the latest unanswered turn. Keep the existing `/next` flow for answer submission unchanged, but persist an initial question version on normal generation and append new versions on explicit human-guided regeneration.

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph-adjacent orchestration helpers, React 19, TypeScript, Vite

### Task 1: Lock Behavior With Tests

**Files:**
- Modify: `tests/test_project_api_flow.py`

**Step 1: Write failing API test for current-question regeneration**

Cover:
- latest unanswered turn can be regenerated in place
- turn number does not change
- new question version is appended
- regeneration count increases
- human-intervention regeneration token totals are tracked

**Step 2: Run targeted test to verify failure**

Run: `uv run python -m unittest tests.test_project_api_flow.ProjectApiFlowTests.test_regenerate_current_question_tracks_versions_and_usage`
Expected: FAIL because endpoint/schema/fields do not exist yet

**Step 3: Commit**

```bash
git add tests/test_project_api_flow.py
git commit -m "test: cover current question regeneration flow"
```

### Task 2: Add Backend Data Model And Schema

**Files:**
- Create: `app/models/question_version.py`
- Modify: `app/models/__init__.py`
- Modify: `app/models/turn.py`
- Modify: `app/core/database.py`
- Modify: `app/schemas/turn.py`
- Modify: `app/schemas/project.py`

**Step 1: Add persisted question-version history**

Store:
- `turn_id`
- `version_no`
- `question_text`
- `question_plan_json`
- `human_review_json`
- aggregated token counts
- generation kind
- created time

**Step 2: Extend turn read model**

Expose:
- current question version number
- total regeneration count
- human-intervention regeneration usage summary
- question version list

**Step 3: Add SQLite schema backfill**

Ensure:
- new table is created for existing local databases
- old turns can lazily seed an initial version before first regeneration

### Task 3: Implement Regeneration Endpoint

**Files:**
- Modify: `app/api/routes/projects.py`
- Modify: `app/services/question_generator.py`
- Modify: `app/services/usage_service.py`
- Modify: `app/graphs/interview_nodes.py` or shared helper module if refactored

**Step 1: Add dedicated endpoint**

Suggested route:
- `POST /projects/{project_id}/turns/{turn_id}/regenerate-question`

Behavior:
- only latest unanswered turn can be regenerated
- explicit human review payload is accepted
- a run trace is created for the regeneration action

**Step 2: Reuse generation pipeline without advancing turn number**

Keep:
- same `turn_no`
- same `stage`

Regenerate:
- question text
- question plan

Persist:
- appended question version
- aggregated usage for this regeneration
- `question_regeneration` usage rows

**Step 3: Return updated turn and usage summary**

### Task 4: Add Frontend Controls

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/hooks/useProject.ts`
- Modify: `frontend/src/components/TranscriptPanel.tsx`
- Modify: `frontend/src/components/TurnCard.tsx`
- Modify: `frontend/src/components/AnswerComposer.tsx`
- Modify: `frontend/src/i18n.ts`

**Step 1: Add current-question review action**

For the latest unanswered turn:
- show human review inputs
- submit regenerate-current-question

**Step 2: Display version history and metrics**

Show:
- current version number
- total regeneration count
- human intervention regeneration token total
- collapsible question history list

**Step 3: Keep answer submission flow intact**

After regeneration:
- answer composer still submits the answer for the current turn
- `/next` still advances to the next turn only after an answer is provided

### Task 5: Verify And Commit

**Step 1: Run backend targeted tests**

Run: `uv run python -m unittest tests.test_project_api_flow`
Expected: PASS

**Step 2: Run frontend verification**

Run: `npm run lint`
Run: `npm test`
Run: `npm run build`
Working directory: `frontend`
Expected: PASS

**Step 3: Commit by layer**

```bash
git add app tests
git commit -m "feat: support current question regeneration"
```

```bash
git add frontend
git commit -m "feat: expose question regeneration controls in ui"
```
