# Code Detail Queue And Coverage Balancing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an internal sub-question queue for compound questioning during the `Code Detail Completion` stage, rebalance deep-dive coverage across repository files using explicit importance and exploration metrics, and expose the new state through the existing debug API surfaces plus the analytics UI.

**Architecture:** Keep the existing five-stage model exactly as the repo defines it: `Panorama Mapping`, `Architecture Understanding`, `Code Detail Completion`, `Use Cases & Scenarios`, and `Final Wrap-up`. Preserve the one-question-per-turn UX, but extend `coverage_state` into a richer orchestration snapshot. Add a queue layer between planning and question drafting only for `Code Detail Completion` turns, plus a repository file map that stores per-file importance, exploration progress, evidence turns, and tree placement. During `Code Detail Completion`, planner selection should first consume valid queued sub-questions, then only synthesize a new question group when the queue is empty.

**Tech Stack:** FastAPI, SQLAlchemy models with JSON-backed project state, service-layer orchestration in `app/services`, graph execution in `app/graphs`, React + TypeScript + Vite frontend analytics UI, unittest/pytest-style backend tests, Vitest frontend tests.

### Task 1: Extend the orchestration state model

**Files:**
- Modify: `app/services/coverage_service.py`
- Modify: `app/schemas/debug.py`
- Modify: `frontend/src/types/api.ts`
- Test: `tests/test_framework_orchestration.py`

**Step 1: Write failing backend tests for the new state shape**

Add tests that assert `rebuild_coverage_state()` returns new top-level structures such as:
- `question_queue`
- `repo_file_coverage`
- `repo_tree_summary`
- version bump plus backward-compatible defaults

Also add a regression test that loading an older coverage blob still returns the new default fields.

**Step 2: Add the default and normalization structures**

In `app/services/coverage_service.py`, extend `default_coverage_state()` and `load_coverage_state()` with:
- `version: 3`
- `question_queue`: queue metadata plus queued sub-questions
- `repo_file_coverage`: per-file metrics map
- `repo_tree_summary`: compact tree data for UI/debug use

Keep all fields JSON-serializable and `ensure_ascii=True`.

**Step 3: Add debug and frontend typings**

Expand `CoverageDebugResponse` and related frontend types to include the new queue and file coverage structures. Do not use untyped `dict`/`Record` where a stable schema is feasible.

**Step 4: Run targeted tests**

Run: `uv run python -m unittest tests.test_framework_orchestration`
Expected: new coverage-shape tests pass.

### Task 2: Add a compound-question decomposition service for `Code Detail Completion`

**Files:**
- Create: `app/services/question_queue_service.py`
- Modify: `app/services/question_planner.py`
- Modify: `app/services/question_validator.py`
- Modify: `app/prompts/assets/next_question_code_detail.yaml`
- Test: `tests/test_framework_orchestration.py`
- Test: `tests/test_interview_nodes.py`

**Step 1: Write failing tests for code-detail split planning**

Cover these cases:
- a compound `Code Detail Completion` target becomes 2-3 sub-questions
- each queued item is independently understandable without the parent text
- queue items keep the same stage and intent family
- planner still returns one visible next question only

**Step 2: Implement queue decomposition**

Create `question_queue_service.py` with helpers such as:
- `detect_compound_question_candidate(...)`
- `decompose_code_detail_question_group(...)`
- `normalize_sub_question_text(...)`
- `renumber_sub_question_queue(...)`

Use either deterministic heuristics plus planner context, or a narrowly scoped LLM prompt if needed, but the final queue objects must be normalized by code before persistence.

**Step 3: Tighten validation**

Update validation so queued sub-questions must:
- be self-contained
- remain implementation-specific
- avoid overlap with one another
- avoid yes/no framing
- avoid requiring the previous queued sibling for interpretation

**Step 4: Keep the user-facing contract**

Do not change the output prompt contract of “one visible question per turn.” The queue is internal state; only the next eligible queued item becomes the visible `Qn` question for the next turn.

### Task 3: Consume, prune, and renumber the queue after each answer in `Code Detail Completion`

**Files:**
- Modify: `app/graphs/interview_nodes.py`
- Modify: `app/api/routes/projects.py`
- Modify: `app/services/coverage_service.py`
- Create or modify: `app/services/question_queue_service.py`
- Test: `tests/test_interview_nodes.py`
- Test: `tests/test_run_trace_api.py`

**Step 1: Write failing lifecycle tests**

Add tests for:
- queue item A asked at `Q12`, queue item B becomes next
- the answer to A implicitly covers B, so B is removed
- the next visible question skips to the next remaining queue item
- when the queue becomes empty, planner falls back to normal fresh planning for the next `Code Detail Completion` question

**Step 2: Implement answer-aware queue pruning**

Add logic that evaluates the latest answer against pending queued items using:
- target artifact overlap
- keyword/signature overlap
- explicit answer-analysis anchors
- semantic redundancy checks already used elsewhere

If a queued item is already answered, mark it removed and do not surface it.

**Step 3: Renumber safely**

Queued items should store stable internal IDs and a display-facing turn offset. After pruning, regenerate display labels so the next surfaced question matches the visible `Qn` turn number without gaps.

**Step 4: Preserve regeneration behavior**

Ensure current-question regeneration works when the source question came from the queue rather than from a fresh planner decision, and keep `question_plan` / `coverage_state` metadata aligned with the regenerated visible question.

### Task 4: Build repository file importance and exploration metrics

**Files:**
- Create: `app/services/repo_file_coverage_service.py`
- Modify: `app/services/coverage_service.py`
- Modify: `app/services/context_engineering.py`
- Modify: `app/services/repo_grounding_service.py`
- Test: `tests/test_context_retrieval.py`
- Test: `tests/test_framework_orchestration.py`

**Step 1: Write failing tests for file metrics**

Cover:
- importance inferred from the repository manifest plus answered turns from `Panorama Mapping` and `Architecture Understanding`
- exploration rising when a file is targeted or answered
- exploration not rising merely because the file exists in the repo
- importance and exploration both present for planner-visible candidates

**Step 2: Define scoring inputs**

In `repo_file_coverage_service.py`, compute per-file metrics using signals such as:
- repository manifest key files
- top-level placement and filename patterns
- explicit mentions in panorama/architecture answers
- presence in selected repo grounding paths
- evidence turn count
- recent question frequency
- unresolved branch association

Recommended fields per file:
- `path`
- `importance_score`
- `exploration_score`
- `coverage_gap_score`
- `times_asked`
- `times_answered`
- `last_turn_no`
- `linked_branch_ids`
- `tree_depth`

**Step 3: Generate a compact tree model**

Produce a stable tree payload grouped by directories so the frontend can render a vertically scrollable repo tree without needing the full manifest every time.

### Task 5: Rebalance `Code Detail Completion` planning across files

**Files:**
- Modify: `app/services/question_planner.py`
- Modify: `app/services/coverage_service.py`
- Modify: `app/services/repetition_guard.py` if needed
- Test: `tests/test_framework_orchestration.py`

**Step 1: Write failing planner tests**

Add tests proving:
- the planner avoids repeatedly drilling into one hot file when other important files remain underexplored
- high-importance low-exploration files beat low-importance overexplored files
- recent-question avoidance still works with the new scoring
- a queue item tied to a file inherits that file’s balancing logic

**Step 2: Replace the branch-only chooser with blended scoring**

Keep branch evidence, but for `Code Detail Completion` compute a combined rank using:
- file importance
- file exploration deficit
- branch unresolved status
- recency penalties
- recent question signature penalties

Recommended principle:
- select `argmax(importance_weight * importance + gap_weight * (1 - exploration) + unresolved_bonus - recency_penalty)`

Do not overfit constants. Keep the scoring legible and testable.

**Step 3: Update planner reasoning**

`why_this_question` and debug metadata should explain both:
- why this file/path matters
- why it is underexplored enough to deserve the next turn

### Task 6: Expose queue and file metrics through debug APIs and analytics data loading

**Files:**
- Modify: `app/api/routes/debug.py`
- Modify: `app/schemas/debug.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/hooks/useProject.ts`

**Step 1: Extend the existing typed debug responses**

Extend `/debug/projects/{project_id}/coverage` and `/debug/projects/{project_id}/state` to include:
- active queue summary
- pending sub-questions
- current queue parent/group metadata
- top file importance/exploration rankings
- compact tree payload

**Step 2: Decide fetch strategy**

Do not add heavy polling everywhere. Prefer loading the coverage/debug payload only for the selected project and only where the UI or analytics calculations actually need it.

### Task 7: Add analytics UI for repository importance and exploration

**Files:**
- Modify: `frontend/src/components/StatsDashboard.tsx`
- Create: `frontend/src/components/RepositoryCoverageTree.tsx`
- Modify: `frontend/src/utils/analytics.ts`
- Modify: `frontend/src/i18n.ts`
- Test: `frontend/src/components/StatsDashboard.test.tsx`
- Test: `frontend/src/utils/analytics.test.ts`

**Step 1: Add failing UI tests**

Cover:
- tree renders with both importance and exploration legends
- long paths remain readable with horizontal space priority
- panel is scrollable vertically
- analytics summary shows top underexplored important files

**Step 2: Add a compact repository coverage panel**

Render a right-side or lower-priority analytics panel that:
- shows the repo tree
- uses one color channel for importance and another for exploration
- allows vertical scrolling
- preserves most of the filename/path width

Do not let this panel dominate the page.

**Step 3: Add summary metrics**

In analytics, add small derived stats such as:
- important files count
- underexplored important files count
- median exploration score
- concentration ratio of questions on top 1 / top 3 files

### Task 8: Update prompting, docs, and operator guidance

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md` and `README_zh.md` if the feature becomes user-visible
- Add or update: `docs/plans/2026-04-15-code-detail-queue-and-coverage-balancing.md`

**Step 1: Keep prompt constraints aligned**

Document that:
- user-facing output remains one question at a time
- internal decomposition is allowed only in the `Code Detail Completion` stage
- queue items must remain independent after splitting
- file balancing is a required planner objective, not a best-effort heuristic

**Step 2: Verify bilingual copy**

If queue/file metrics become visible in UI labels, add both English and Chinese strings.

### Task 9: End-to-end verification

**Files:**
- Test: `tests/test_framework_orchestration.py`
- Test: `tests/test_interview_nodes.py`
- Test: `tests/test_run_trace_api.py`
- Test: `tests/test_context_retrieval.py`
- Test: `frontend/src/components/StatsDashboard.test.tsx`
- Test: `frontend/src/utils/analytics.test.ts`

**Step 1: Backend verification**

Run:
```bash
uv run python -m unittest tests.test_framework_orchestration tests.test_interview_nodes tests.test_run_trace_api tests.test_context_retrieval
```

Expected:
- queue lifecycle tests pass
- planner balancing tests pass
- debug payload shape tests pass

**Step 2: Frontend verification**

Run:
```bash
npm test --prefix frontend -- --run StatsDashboard analytics
```

Expected:
- repository coverage panel tests pass
- analytics derivation tests pass

**Step 3: Manual product verification**

Use one real project and confirm:
- a compound code-detail topic is split into 2-3 queued sub-questions
- only one sub-question is shown to the user at a time
- answering the first can prune the second if it is already covered
- the next few `Code Detail Completion` turns rotate toward other important underexplored files
- analytics shows both importance and exploration clearly
