#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_INPUT_DIR = Path("/Users/wyb/File/Study/agent_article/paper_agent_workspace/results")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "tables"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate LaTeX tables from extracted Cycle 003 CSV outputs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def format_cell(value: str | None) -> str:
    if value in (None, ""):
        return "N/A"
    return str(value)


def pretty_name(config: str) -> str:
    mapping = {
        "full_system": "Full System",
        "no_planner": "- No Planner",
        "no_coverage_state": "- No Coverage State",
        "no_human_review": "- No Human Review",
        "no_retrieval": "- No Retrieval",
    }
    return mapping.get(config, config.replace("_", " ").title())


def render_main_results(ablation_rows: list[dict[str, str]]) -> str:
    lines = [
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Main Results: Stateful Interview Agent extraction snapshot}",
        "\\label{tab:main_results}",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "\\textbf{System} & \\textbf{Coverage\\%} & \\textbf{Redundancy} & \\textbf{Relevance} & \\textbf{Turns to 80\\%} & \\textbf{Human Gates} \\\\",
        "\\midrule",
    ]
    for row in ablation_rows:
        lines.append(
            f"{pretty_name(row['ablation_config'])} & "
            f"{format_cell(row.get('framework_coverage_pct'))} & "
            f"{format_cell(row.get('redundancy_rate'))} & "
            f"{format_cell(row.get('avg_relevance_proxy_rate'))} & "
            f"{format_cell(row.get('turns_to_80pct_coverage'))} & "
            f"{format_cell(row.get('human_gate_rate'))} \\\\"
        )
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ablation_rows = load_csv(args.input_dir / "metrics_ablations.csv")
    tex = render_main_results(ablation_rows)
    output_path = args.output_dir / "main_results.tex"
    output_path.write_text(tex, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
