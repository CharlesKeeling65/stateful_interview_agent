# OpenCode Plan Mode Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose OpenCode auto-conversation in the frontend with always-on Plan mode, per-question human gating, project-bound session visibility, and automatic answer retrieval/fill after approval.

**Architecture:** Keep the project as the source of truth for the bound `opencode_session_id`, and add explicit backend endpoints for session bootstrap and gated question dispatch. In the frontend, replace fire-and-forget auto-answering with a visible Plan-mode controller that shows the current session, the generated question, and three human actions: send, edit then send, or skip.

**Tech Stack:** FastAPI, SQLAlchemy, React 19, TypeScript, Vite, Vitest, Testing Library.

### Task 1: Extend OpenCode backend contract

**Files:**
- Modify: `app/services/opencode_session_service.py`
- Modify: `app/services/opencode_execution_service.py`
- Modify: `app/api/routes/projects.py`
- Modify: `app/schemas/project.py`
- Modify: `app/schemas/turn.py`

**Steps:**
1. Add a response shape for OpenCode session bootstrap and gated dispatch.
2. Add a route that ensures a project-bound OpenCode session exists and returns its `session_id`.
3. Add a route that sends a chosen question to OpenCode in Plan mode and returns the resulting answer text.
4. Reuse the existing answer persistence path so fetched text lands in the latest turn consistently.
5. Preserve current behavior for manual mode and surface actionable HTTP errors.

### Task 2: Add failing frontend tests first

**Files:**
- Create or modify: `frontend/src/components/AnswerComposer.test.tsx`
- Create or modify: `frontend/src/components/CreateProjectForm.test.tsx`
- Modify: `frontend/src/hooks/useProject.ts`
- Modify: `frontend/src/types/api.ts`

**Steps:**
1. Add a test covering Plan-mode project creation defaults for OpenCode.
2. Add a test covering the gating panel showing session id and send/edit/skip actions.
3. Add a test covering automatic answer fill after approved OpenCode send.
4. Run the targeted Vitest cases and confirm they fail for the expected missing behavior.

### Task 3: Implement frontend Plan-mode UX

**Files:**
- Modify: `frontend/src/components/CreateProjectForm.tsx`
- Modify: `frontend/src/components/AnswerComposer.tsx`
- Modify: `frontend/src/hooks/useProject.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/i18n.ts`

**Steps:**
1. Default new projects to OpenCode + automation enabled + `agent_mode = "plan"`.
2. Show project-bound `opencode_session_id` in the frontend, with a lazy ensure action if absent.
3. When a new question exists without an answer, show Plan-mode actions: send, edit then send, skip.
4. After send, fetch the OpenCode answer, save it through the normal backend path, refresh the project, and show errors inline.
5. Keep answer text editable locally so the user can inspect or overwrite before saving if needed.

### Task 4: Verify the integrated flow

**Files:**
- Modify as needed: frontend test files only

**Steps:**
1. Run focused frontend tests for the creation form and answer composer.
2. Run a broader frontend test pass if the focused suite succeeds.
3. Summarize any backend behavior left unverified by automation.
