# Repository Coverage and Planning Rebalance

This document explains the repository-aware planning system implemented in April 2026. This system ensures that the interview agent systematically explores important files in the repository during the `Code Detail Completion` stage.

## 1. Metric System

The system tracks two primary metrics for every file in the repository:

### Structural Importance (`importance_score`)
Calculated statically based on the repository structure:
- **Depth**: Files deeper in the tree get slightly lower baseline importance.
- **Location**: Files in `src/`, `app/`, or `lib/` get a significant boost (+0.3). Tests, docs, and hidden directories are penalized.
- **Extensions**: Source code files (`.py`, `.ts`, `.go`, etc.) are prioritized over configuration or text files.
- **Scale**: Normalized from `0.0` to `1.0`.

### Exploration Progress (`exploration_score`)
Calculated dynamically based on the interview history:
- **Asks**: Each time the planner targets a file, its exploration score potential increases.
- **Answers**: Each time a file is mentioned in an answer summary or RAG evidence, its exploration score increments (capped at 1.0).
- **Scale**: `0.0` (unexplored) to `1.0` (fully covered).

## 2. Coverage Gap and Rebalancing

The **Coverage Gap** is defined as:
`Gap = max(0, Importance - Exploration)`

When the interview enters the `Code Detail Completion` stage, the `QuestionPlanner` performs the following rebalancing:

1.  **Identify Gaps**: It calculates the gap for all tracked repository files.
2.  **Filter High-Value Targets**: Files with a gap `> 0.2` are considered "underexplored but important".
3.  **Inject Constraints**: The top 3 files by gap are injected into the LLM prompt as **Constraints**.
    - *Example Constraint*: `Prioritize asking about unexplored but highly important files: app/core/logic.py, app/db/session.py`
4.  **Target Selection**: If the planner doesn't have a specific branch to follow, it will force the `target_label` to be the highest-gap file.

## 3. Transparency and Debugging

The system exposes these metrics through the **Analytics Dashboard**:
- **Directory Tree Summary**: Shows aggregated exploration progress for each directory.
- **Top Coverage Gaps**: Lists specific files that the planner is currently trying to "hit" next, ordered by importance.
- **Planner Queue**: Shows the exact sub-questions the planner has decomposed if it's currently unfolding a complex topic.

## 4. Operational Guidance

For operators/human reviewers:
- **Low Exploration on Important Files**: If the dashboard shows a high gap on a critical file, the agent *should* eventually rotate to it. If it doesn't, use the **Human Review** panel to provide an explicit **Preferred Next Focus**.
- **Regeneration**: If the agent generates a question that ignores the rebalancing constraints, use **Regenerate Current Question** with a note like "Focus on the gaps in the core logic first."
