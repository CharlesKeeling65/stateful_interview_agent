# Analytics Visual Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the analytics page so project metrics are presented through richer, more intuitive visualizations such as trend lines, stacked bars, gantt-like stage bands, and a stage transition network.

**Architecture:** Extend the existing frontend analytics aggregation layer so the dashboard can derive chart-ready series from already loaded `project`, `status`, and `turns` data. Keep rendering local to the React dashboard with SVG/CSS primitives instead of introducing a heavy chart library, preserving bundle simplicity and styling control.

**Tech Stack:** React, TypeScript, Tailwind utility classes, Vitest, existing frontend i18n utilities.

### Task 1: Add failing analytics aggregation tests

**Files:**
- Modify: `frontend/src/utils/analytics.test.ts`
- Modify: `frontend/src/utils/analytics.ts`

**Step 1: Write the failing test**

Add tests asserting that analytics output includes:
- per-turn token trend data
- cumulative token totals per turn
- stage transition edges between consecutive turns
- stage segments with duration/share values for gantt-like rendering

**Step 2: Run test to verify it fails**

Run: `npm test -- src/utils/analytics.test.ts`
Expected: FAIL because the new analytics fields do not exist yet.

**Step 3: Write minimal implementation**

Implement the smallest aggregation changes in `frontend/src/utils/analytics.ts` that satisfy the new test shape and values.

**Step 4: Run test to verify it passes**

Run: `npm test -- src/utils/analytics.test.ts`
Expected: PASS.

### Task 2: Redesign the analytics dashboard with richer charts

**Files:**
- Modify: `frontend/src/components/StatsDashboard.tsx`
- Modify: `frontend/src/i18n.ts`

**Step 1: Write the failing test**

Add a component-level assertion or text-level expectation if needed for new chart headings and empty states. Keep the test small and focused on user-visible behavior.

**Step 2: Run test to verify it fails**

Run: `npm test -- src/utils/analytics.test.ts`
Expected: Existing/new expectations expose the missing UI copy or missing chart bindings.

**Step 3: Write minimal implementation**

Replace the current simple bars with a richer visual system:
- radial or pie-like token composition
- line/area style token trend across turns
- stacked or cumulative turn bars
- gantt-like stage occupancy band
- stage transition network using SVG nodes and weighted paths

**Step 4: Run test to verify it passes**

Run: `npm test -- src/utils/analytics.test.ts`
Expected: PASS.

### Task 3: Verify and commit

**Files:**
- Review modified files above

**Step 1: Run focused tests**

Run: `npm test -- src/utils/analytics.test.ts`
Expected: PASS.

**Step 2: Run broader frontend verification**

Run: `npm test`
Expected: PASS.

Run: `npm run lint`
Expected: PASS.

Run: `npm run build`
Expected: PASS.

**Step 3: Commit**

```bash
git add frontend/src/utils/analytics.ts frontend/src/utils/analytics.test.ts frontend/src/components/StatsDashboard.tsx frontend/src/i18n.ts docs/plans/2026-04-04-analytics-visual-upgrade.md
git commit -m "feat: upgrade analytics visualizations"
```
