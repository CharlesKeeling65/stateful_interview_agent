# UX And Bilingual Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the frontend information architecture and reading flow, add English/Chinese language switching, and keep the UI aligned with backend data semantics.

**Architecture:** Introduce a lightweight client-side i18n layer and shared display helpers, then refactor the workspace into a clearer narrative layout: overview and actions on top, readable turn cards in the center, and metrics/export in the side rail. Keep backend contracts unchanged and translate only presentation copy plus selected enum labels.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4

### Task 1: Baseline Inspection

**Files:**
- Review: `frontend/src/App.tsx`
- Review: `frontend/src/hooks/useProject.ts`
- Review: `frontend/src/types/api.ts`
- Review: `frontend/src/components/*.tsx`
- Review: `frontend/package.json`

**Step 1: Confirm current scripts and clean git state**

Run: `git status --short`
Expected: empty output

**Step 2: Confirm frontend verification commands**

Run: `cat frontend/package.json`
Expected: `build` and `lint` scripts available

**Step 3: Identify user-facing copy and backend-driven labels**

Review the components and collect:
- fixed English copy
- stage/status/verdict labels driven by API
- places where raw backend data is shown without presentation guidance

### Task 2: Add Presentation Foundations

**Files:**
- Create: `frontend/src/i18n.ts`
- Modify: `frontend/src/utils/format.ts`
- Modify: `frontend/src/utils/status.ts`
- Modify: `frontend/src/types/api.ts`

**Step 1: Write the failing expectation mentally and structurally**

Expected behavior:
- every visible action label and section label can be rendered in English and Chinese
- date and duration formatting respects the selected locale
- backend enum-like values can be displayed with human-friendly translated labels

**Step 2: Implement minimal i18n primitives**

Add:
- locale type
- translation dictionary
- label helpers for stage, status, human review, question plan, and trace states
- formatting helpers for locale-aware timestamps and durations

**Step 3: Keep implementation presentation-only**

Do not change:
- API requests
- persisted backend payload shape
- business logic in `useProject`

**Step 4: Commit**

```bash
git add docs/plans/2026-04-04-ux-bilingual-refresh.md frontend/src/i18n.ts frontend/src/utils/format.ts frontend/src/utils/status.ts frontend/src/types/api.ts
git commit -m "feat: add bilingual presentation foundations"
```

### Task 3: Refactor Layout And Reading Flow

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/components/ProjectSidebar.tsx`
- Modify: `frontend/src/components/CreateProjectForm.tsx`
- Modify: `frontend/src/components/TranscriptPanel.tsx`
- Modify: `frontend/src/components/TurnCard.tsx`
- Modify: `frontend/src/components/StatusPanel.tsx`
- Modify: `frontend/src/components/AnswerComposer.tsx`
- Modify: `frontend/src/components/ExecutionTraceSection.tsx`
- Modify: `frontend/src/components/TokenUsagePanel.tsx`

**Step 1: Introduce a top-level language switcher and overview strip**

Show:
- bilingual toggle
- current session context
- concise summary metrics

**Step 2: Improve turn readability**

Change turn cards to:
- clearer separation between question, answer, rationale, review, and trace
- softer hierarchy for metadata
- translated badges and explanatory copy
- better collapsed-answer affordance

**Step 3: Improve action clarity**

Change composer and side panels to:
- explain the next action in plain language
- reduce repetitive jargon
- connect token estimates and trace output back to user intent

**Step 4: Preserve responsive behavior**

Keep:
- desktop multi-column workspace
- mobile stacking
- scroll containment for long transcript history

**Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/index.css frontend/src/components/ProjectSidebar.tsx frontend/src/components/CreateProjectForm.tsx frontend/src/components/TranscriptPanel.tsx frontend/src/components/TurnCard.tsx frontend/src/components/StatusPanel.tsx frontend/src/components/AnswerComposer.tsx frontend/src/components/ExecutionTraceSection.tsx frontend/src/components/TokenUsagePanel.tsx
git commit -m "feat: redesign frontend reading flow and bilingual ui"
```

### Task 4: Verification

**Files:**
- Review: `frontend/src/**/*`

**Step 1: Run lint**

Run: `npm run lint`
Working directory: `frontend`
Expected: success

**Step 2: Run build**

Run: `npm run build`
Working directory: `frontend`
Expected: success

**Step 3: Fix any type or lint regressions**

Only touch files needed to make verification pass.

**Step 4: Commit verification fixes if needed**

```bash
git add <fixed-files>
git commit -m "fix: polish bilingual ux implementation"
```

### Task 5: Final Git Breakdown

**Step 1: Keep commit scopes separate**

Use separate commits for:
- presentation foundations
- layout and bilingual UX refresh
- verification polish

**Step 2: Provide the resulting commit list to the user**

Run: `git log --oneline -3`
Expected: the new stepwise commits visible at the top
