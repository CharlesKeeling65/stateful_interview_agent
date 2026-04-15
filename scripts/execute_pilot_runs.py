#!/usr/bin/env python3
"""
Pilot Run Execution Script

Execute 12 pilot sessions as specified in experiment_assets/run_manifest.csv.
This script handles complete session execution (not just single turns) with retry logic.
"""

import argparse
import csv
import dataclasses
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
MANIFEST_PATH = Path("/Users/wyb/File/Study/agent_article/paper_agent_workspace/experiment_assets/run_manifest.csv")
SOURCE_DIR = Path("/Users/wyb/File/Programming/Git_Code/stateful_interview_agent")
RESULTS_DIR = Path("/Users/wyb/File/Study/agent_article/paper_agent_workspace/results/pilot_runs")
MAX_RETRIES = 3
SLEEP_BETWEEN_RUNS = 5  # seconds


@dataclasses.dataclass
class ManifestRow:
    run_id: str
    repo_id: str
    task_id: str
    system_id: str
    system_config_id: str
    replicate_id: str
    repo_snapshot_ref: str
    task_file: str
    gold_file: str
    coverage_schema_ref: str
    turn_annotation_file: str
    final_annotation_file: str
    output_root: str
    db_snapshot_path: str
    logs_root: str
    results_core_csv: str
    results_turns_csv: str
    results_ablations_csv: str
    status: str
    execution_status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    runner_version: str
    random_seed: Optional[str]
    owner: str
    notes: str


def load_manifest() -> List[ManifestRow]:
    """Load manifest CSV and return all planned runs."""
    rows = []
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("status") != "planned":
                continue
            rows.append(ManifestRow(
                run_id=row["run_id"],
                repo_id=row["repo_id"],
                task_id=row["task_id"],
                system_id=row["system_id"],
                system_config_id=row["system_config_id"],
                replicate_id=row["replicate_id"],
                repo_snapshot_ref=row["repo_snapshot_ref"],
                task_file=row["task_file"],
                gold_file=row["gold_file"],
                coverage_schema_ref=row["coverage_schema_ref"],
                turn_annotation_file=row["turn_annotation_file"],
                final_annotation_file=row["final_annotation_file"],
                output_root=row["output_root"],
                db_snapshot_path=row["db_snapshot_path"],
                logs_root=row["logs_root"],
                results_core_csv=row["results_core_csv"],
                results_turns_csv=row["results_turns_csv"],
                results_ablations_csv=row["results_ablations_csv"],
                status=row["status"],
                execution_status=row["execution_status"],
                started_at=row.get("started_at"),
                completed_at=row.get("completed_at"),
                runner_version=row["runner_version"],
                random_seed=row.get("random_seed"),
                owner=row["owner"],
                notes=row["notes"],
            ))
    return rows


def setup_sandbox(run_row: ManifestRow) -> None:
    """Clean sandbox environment for independent runs."""
    print(f"[{run_row.run_id}] Setting up sandbox...")
    
    # Create output directory
    output_dir = Path(run_row.output_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logs directory
    logs_dir = Path(run_row.logs_root)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean any existing database
    if Path(run_row.db_snapshot_path).exists():
        Path(run_row.db_snapshot_path).unlink()
    
    # Copy fresh database snapshot if available
    source_db = SOURCE_DIR / "data" / "app.db"
    if source_db.exists():
        shutil.copy2(source_db, run_row.db_snapshot_path)
        print(f"[{run_row.run_id}] Copied fresh database snapshot")
    else:
        print(f"[{run_row.run_id}] WARNING: No source database found at {source_db}")


def execute_single_turn(run_row: ManifestRow, project_id: int) -> Dict:
    """Execute a single turn using the runner."""
    cmd = [
        str(SOURCE_DIR / ".venv/bin/python"),
        "-m", "app.runner",
        "--run-manifest", str(MANIFEST_PATH),
        "--run-id", run_row.run_id,
        "--project-id", str(project_id),
    ]
    
    result = subprocess.run(
        cmd,
        cwd=SOURCE_DIR,
        capture_output=True,
        text=True,
        timeout=300  # 5 minutes per turn
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Turn execution failed: {result.stderr}")
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Invalid JSON output: {result.stdout}")


def check_session_complete(project_id: int, db_path: str) -> bool:
    """Check if interview session is complete."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check project status
        cursor.execute("SELECT status FROM project_sessions WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            return False
        
        return row[0] == "finished"
    finally:
        if conn:
            conn.close()


def execute_complete_session(run_row: ManifestRow) -> bool:
    """Execute a complete interview session until finished or error."""
    print(f"[{run_row.run_id}] Starting complete session execution...")
    
    setup_sandbox(run_row)
    
    # Get project ID from database
    conn = None
    try:
        conn = sqlite3.connect(run_row.db_snapshot_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM project_sessions ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("No project found in database")
        project_id = row[0]
    finally:
        if conn:
            conn.close()
    
    turn_count = 0
    max_turns = 50  # Safety limit
    
    while turn_count < max_turns:
        try:
            print(f"[{run_row.run_id}] Executing turn {turn_count + 1}...")
            
            # Execute single turn
            result = execute_single_turn(run_row, project_id)
            turn_count += 1
            
            # Check if session is complete
            if check_session_complete(project_id, run_row.db_snapshot_path):
                print(f"[{run_row.run_id}] Session completed after {turn_count} turns")
                return True
            
            # Small delay between turns
            time.sleep(1)
            
        except Exception as e:
            print(f"[{run_row.run_id}] Turn {turn_count + 1} failed: {e}")
            raise
    
    print(f"[{run_row.run_id}] Session stopped at {turn_count} turns (max limit reached)")
    return False


def update_manifest_status(run_row: ManifestRow, success: bool, error_msg: str = "") -> None:
    """Update manifest with execution status and timestamps."""
    timestamp = datetime.now().isoformat()
    
    # Read current manifest
    rows = []
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    
    # Update the specific row
    for row in rows:
        if row["run_id"] == run_row.run_id:
            row["execution_status"] = "completed" if success else "failed"
            row["started_at"] = run_row.started_at or timestamp
            row["completed_at"] = timestamp
            if error_msg:
                row["notes"] = f"{row['notes']} | Error: {error_msg}"
            break
    
    # Write back
    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"[{run_row.run_id}] Manifest updated: {success and 'completed' or 'failed'}")


def verify_stateless_qa_behavior(run_row: ManifestRow) -> None:
    """Verify stateless_qa baseline behavior (3-turn window, coverage reset)."""
    if run_row.system_id != "stateless_qa":
        return
    
    print(f"[{run_row.run_id}] Verifying stateless_qa behavior...")
    
    # Check logs for coverage reset events
    logs_dir = Path(run_row.logs_root)
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.jsonl"))
        coverage_reset_count = 0
        three_turn_window_used = False
        
        for log_file in log_files:
            with log_file.open("r") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        if event.get("event") == "coverage.persist.complete":
                            if event.get("output", {}).get("system_id") == "stateless_qa":
                                coverage_reset_count += 1
                        
                        # Check for 3-turn window usage in context building
                        if "3-turn window" in str(event):
                            three_turn_window_used = True
                            
                    except json.JSONDecodeError:
                        continue
        
        print(f"[{run_row.run_id}] Coverage resets: {coverage_reset_count}")
        print(f"[{run_row.run_id}] 3-turn window detected: {three_turn_window_used}")
        
        if coverage_reset_count == 0:
            print(f"[{run_row.run_id}] WARNING: No coverage resets detected for stateless_qa")
        
        if not three_turn_window_used:
            print(f"[{run_row.run_id}] WARNING: 3-turn window usage not confirmed in logs")


def execute_pilot_run(run_row: ManifestRow) -> bool:
    """Execute a single pilot run with retry logic."""
    print(f"\n{'='*60}")
    print(f"EXECUTING: {run_row.run_id} ({run_row.system_id})")
    print(f"{'='*60}")
    
    for attempt in range(MAX_RETRIES):
        try:
            # Record start time
            timestamp = datetime.now().isoformat()
            run_row.started_at = timestamp
            
            # Execute complete session
            success = execute_complete_session(run_row)
            
            # Verify baseline behavior if applicable
            if success:
                verify_stateless_qa_behavior(run_row)
            
            # Update manifest
            update_manifest_status(run_row, success)
            
            if success:
                print(f"[{run_row.run_id}] SUCCESS")
                return True
            else:
                print(f"[{run_row.run_id}] Incomplete session (not fatal)")
                return True
                
        except Exception as e:
            print(f"[{run_row.run_id}] Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"[{run_row.run_id}] Retrying...")
                time.sleep(SLEEP_BETWEEN_RUNS)
            else:
                print(f"[{run_row.run_id}] All attempts failed")
                update_manifest_status(run_row, False, str(e))
                return False
    
    return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Execute 12-session pilot run")
    parser.add_argument("--run-id", help="Execute specific run ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be executed")
    args = parser.parse_args()
    
    # Load manifest
    try:
        manifest_rows = load_manifest()
    except Exception as e:
        print(f"Failed to load manifest: {e}")
        return 1
    
    if not manifest_rows:
        print("No planned runs found in manifest")
        return 0
    
    if args.run_id:
        # Execute specific run
        matching_rows = [r for r in manifest_rows if r.run_id == args.run_id]
        if not matching_rows:
            print(f"Run ID {args.run_id} not found in manifest")
            return 1
        rows_to_execute = matching_rows
    else:
        # Execute all planned runs
        rows_to_execute = manifest_rows
    
    print(f"Found {len(rows_to_execute)} planned runs to execute")
    
    if args.dry_run:
        print("\nDry run - would execute:")
        for row in rows_to_execute:
            print(f"  - {row.run_id}: {row.system_id} ({row.repo_id})")
        return 0
    
    # Execute runs
    successful_runs = 0
    total_runs = len(rows_to_execute)
    
    for i, run_row in enumerate(rows_to_execute, 1):
        print(f"\n[{i}/{total_runs}] Processing {run_row.run_id}")
        
        if execute_pilot_run(run_row):
            successful_runs += 1
        
        # Sleep between runs to avoid state leakage
        if i < total_runs:
            print(f"Waiting {SLEEP_BETWEEN_RUNS}s before next run...")
            time.sleep(SLEEP_BETWEEN_RUNS)
    
    print(f"\n{'='*60}")
    print(f"PILOT RUN SUMMARY")
    print(f"{'='*60}")
    print(f"Total runs: {total_runs}")
    print(f"Successful: {successful_runs}")
    print(f"Failed: {total_runs - successful_runs}")
    print(f"Success rate: {successful_runs/total_runs*100:.1f}%")
    
    return 0 if successful_runs == total_runs else 1


if __name__ == "__main__":
    sys.exit(main())