# Edit Repository During Active Project Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let operators add or update repository settings while a project is already in progress, and make the refreshed repository context visible immediately without auto-regenerating the current question.

**Architecture:** Reuse the existing `PATCH /projects/{id}` backend capability. Add a repository settings editor to the status rail, wire it to the existing frontend update flow, then refresh project details so repository manifest, commit, and key files update immediately after save.

**Tech Stack:** FastAPI, React, TypeScript, Vitest

### Task 1: Add a failing UI test for repository editing

**Files:**
- Create: `frontend/src/components/StatusPanel.test.tsx`

**Step 1: Write the failing test**

Render the status panel with an in-progress project that currently has no repository. Assert that the user can open repository settings, enter a local path, save, and that the component calls the provided update callback with the expected repository payload.

**Step 2: Run test to verify it fails**

Run: `npm test -- --run src/components/StatusPanel.test.tsx`

Expected: FAIL because the status panel does not yet expose repository editing controls.

### Task 2: Implement repository editing in the status rail

**Files:**
- Modify: `frontend/src/components/StatusPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/hooks/useProject.ts`
- Modify: `frontend/src/i18n.ts`

**Step 1: Write minimal implementation**

Add a repository settings editor with:
- source type switch
- local path input
- git URL input
- git ref input
- save and cancel actions

Wire save to the existing `updateProject(projectId, payload)` path and refresh the selected project after success.

**Step 2: Run test to verify it passes**

Run: `npm test -- --run src/components/StatusPanel.test.tsx`

Expected: PASS.

### Task 3: Run verification and commit

**Files:**
- Modify only the files above

**Step 1: Run verification**

Run: `npm test`
Run: `npm run lint`
Run: `npm run build`

**Step 2: Commit**

```bash
git add docs/plans/2026-04-05-edit-repository-during-project-plan.md frontend/src/components/StatusPanel.test.tsx frontend/src/components/StatusPanel.tsx frontend/src/App.tsx frontend/src/hooks/useProject.ts frontend/src/i18n.ts
git commit -m "feat: edit repository settings during active projects"
```
