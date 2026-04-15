# Cycle 003 Scripts

## Overview

This directory contains the Cycle 003 extraction entrypoints.

- `extract_metrics.py`
  - Reads the SQLite interview database plus structured runtime logs.
  - Emits:
    - `results/metrics_core.csv`
    - `results/metrics_turns.csv`
    - `results/metrics_ablations.csv`
- `generate_latex_tables.py`
  - Reads the CSV outputs and writes publication-oriented LaTeX tables.

## Commands

```bash
python scripts/extract_metrics.py \
  --db-path /Users/wyb/File/Programming/Git_Code/stateful_interview_agent/data/app.db \
  --logs-root /Users/wyb/File/Programming/Git_Code/stateful_interview_agent/logs \
  --output-dir results
```

```bash
python scripts/generate_latex_tables.py \
  --input-dir results \
  --output-dir results/tables
```

## Notes

- This pass retains `sqlite3` rather than migrating to SQLAlchemy session queries.
- Reason: the extraction is read-only, offline, and designed to run even when the full application dependency graph is not initialized.
- A SQLAlchemy migration would require:
  - importing the application model layer as a stable library interface,
  - normalizing runtime/config bootstrap side effects,
  - and making the extractor resilient to partial application environments.

## Metric Status

- True measurements from persisted runtime state:
  - `framework_coverage_pct`
  - `panorama_coverage_pct`
  - `architecture_coverage_pct`
  - `detail_coverage_pct`
  - `use_cases_coverage_pct`
  - `total_duration_ms`
  - `total_llm_tokens`
  - `human_gate_count`
  - `human_gate_rate`
  - `repo_grounding_count`
  - `regenerated`
  - `llm_tokens_this_turn`
- Heuristic proxies:
  - `redundancy_rate`
  - `question_relevance_score`
  - `avg_relevance_score`
  - `progressive_depth_score`
  - `avg_coherence_score`
  - `coverage_delta`
  - `turns_to_80pct_coverage`
