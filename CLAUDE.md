# Project instructions

- Do not repeatedly inspect git sync state or run git divergence checks unless the user is explicitly asking for git synchronization, push/pull, rebase, merge, or remote troubleshooting.
- For normal feature work, stay focused on the requested implementation instead of proactively checking branch sync.
- For code-detail orchestration work, preserve the product contract of showing exactly one user-facing question per turn, but allow internal planning to create and manage a multi-step sub-question queue.
- When a strong model proposes a compound code-detail question, split it into 2-3 independently understandable sub-questions before asking the next turn; each queued sub-question must be self-contained, lightly edited if needed, and renumbered consistently with the visible `Qn` sequence.
- Queue management must be answer-aware: after each human answer, remove any queued sub-question that has already been implicitly answered, compact the remaining queue, and only generate a fresh parent question group when the current split queue is exhausted.
- Do not let code-detail exploration over-concentrate on a single file. Any planner changes in this area must introduce explicit file-level `importance` and `exploration` metrics and use both signals to rebalance which files get deep-dive questions next.
- Treat repository coverage as a first-class product surface. Backend changes should expose queue state and file exploration metrics through typed APIs, and frontend analytics/debug views should visualize the repository tree with both importance and exploration status.
- Keep `coverage_state` changes backward compatible. If you introduce new JSON fields or version bumps, provide default migration behavior so older projects still load cleanly.
