# Answer Preprocessing Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When an answer is saved, immediately derive a compact summary, retrieval chunks, and stage-aware key points so later question generation can reuse structured memory instead of relying on raw answer text alone.

**Architecture:** Persist one structured `answer_analysis` payload on each answered turn. Build it at save time by combining the existing answer summary LLM result with deterministic chunking and stage-aware sentence extraction, then feed those artifacts back into coverage rebuilding and generation context assembly. Surface the extracted key points in the workspace so operators can see what the system will reuse.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React, Vitest, unittest

### Task 1: Add failing backend tests for saved-answer preprocessing

**Files:**
- Modify: `tests/test_project_api_flow.py`
- Modify: `tests/test_context_retrieval.py`

**Step 1: Write the failing test**

Add one API flow test asserting that saving an answer now returns persisted `answer_summary`, `answer_analysis.key_points`, and `answer_analysis.rag_chunks`.

Add one context test asserting that panorama and architecture key points plus unresolved follow-up anchors appear in the generated context.

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_project_api_flow tests.test_context_retrieval`

Expected: FAIL because `answer_analysis` does not yet exist and retrieval context does not include the new answer-memory content.

### Task 2: Implement answer preprocessing persistence

**Files:**
- Modify: `app/models/turn.py`
- Modify: `app/core/database.py`
- Modify: `app/schemas/turn.py`
- Modify: `app/services/summarization_service.py`
- Modify: `app/api/routes/projects.py`

**Step 1: Write minimal implementation**

Add a new JSON text column/property for `answer_analysis`. Build a save-time helper that:
- refreshes `answer_summary` immediately
- chunks the answer into retrieval-sized slices
- extracts stage-aware key points and follow-up anchors, with extra breadth for `Panorama Mapping` and `Architecture Understanding`

**Step 2: Run targeted tests**

Run: `uv run python -m unittest tests.test_project_api_flow tests.test_context_retrieval`

Expected: PASS for the new answer preprocessing behavior.

### Task 3: Feed answer memory back into coverage and generation

**Files:**
- Modify: `app/services/coverage_service.py`
- Modify: `app/services/context_engineering.py`

**Step 1: Write minimal implementation**

Prefer `answer_analysis` artifacts when:
- extracting branch keywords and unresolved points
- building recent context
- building retrieved branch context for later question generation

Ensure panorama and architecture stages preserve breadth before code-detail narrowing.

**Step 2: Run focused tests**

Run: `uv run python -m unittest tests.test_context_retrieval tests.test_framework_orchestration`

Expected: PASS, with no regressions in existing coverage heuristics.

### Task 4: Surface the saved answer memory in the UI

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/components/TurnCard.tsx`
- Modify: `frontend/src/i18n.ts`

**Step 1: Write minimal implementation**

Expose key points and retrieval chunk counts on answered turn cards so operators can inspect what the system will carry into future questions.

**Step 2: Run frontend verification**

Run: `npm test`
Run: `npm run lint`
Run: `npm run build`

Expected: PASS.

### Task 5: Verify and commit

**Files:**
- No new product files required beyond the implementation above

**Step 1: Run full verification**

Run: `uv run python -m unittest tests.test_project_api_flow tests.test_context_retrieval tests.test_framework_orchestration tests.test_history_compression tests.test_repository_grounding`
Run: `npm test`
Run: `npm run lint`
Run: `npm run build`

**Step 2: Check affected scope**

Run the available git diff / change-scope verification for touched files before committing.

**Step 3: Commit**

```bash
git add docs/plans/2026-04-05-answer-preprocessing-memory-plan.md app/models/turn.py app/core/database.py app/schemas/turn.py app/services/summarization_service.py app/services/coverage_service.py app/services/context_engineering.py app/api/routes/projects.py frontend/src/types/api.ts frontend/src/components/TurnCard.tsx frontend/src/i18n.ts tests/test_project_api_flow.py tests/test_context_retrieval.py
git commit -m "feat: persist answer preprocessing artifacts"
```
