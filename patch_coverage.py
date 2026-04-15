import sys

fname = 'app/services/coverage_service.py'
with open(fname, 'r') as f:
    content = f.read()

# Add calculate_structural_importance function
import_str = "from typing import Any"
if_str = """
def calculate_structural_importance(path: str) -> float:
    depth = path.count("/")
    score = 0.9 ** depth
    
    if path.startswith("src/") or path.startswith("app/") or path.startswith("lib/"):
        score += 0.2
    if path.startswith("tests/") or path.startswith("docs/") or path.startswith("scripts/"):
        score -= 0.4
    
    if path.endswith((".json", ".yaml", ".yml", ".toml", ".ini")):
        score -= 0.3
    elif path.endswith(".md") and not path.lower().endswith("readme.md"):
        score -= 0.5
        
    return max(0.0, min(1.0, score))

"""
content = content.replace("from typing import Any\n", "from typing import Any\n" + if_str)


# Update rebuild_coverage_state signature
content = content.replace("def rebuild_coverage_state(turns: list[InterviewTurn]) -> dict[str, Any]:", "def rebuild_coverage_state(turns: list[InterviewTurn], project: ProjectSession | None = None) -> dict[str, Any]:")

# Initialize repo_file_coverage
state_init = """    repo_file_coverage = {}
    if project:
        manifest = project.repo_manifest_data
        files_list = manifest.get("files_list", [])
        for fpath in files_list:
            if fpath not in repo_file_coverage:
                repo_file_coverage[fpath] = {
                    "path": fpath,
                    "importance_score": calculate_structural_importance(fpath),
                    "exploration_score": 0.0,
                    "coverage_gap_score": 0.0,
                    "times_asked": 0,
                    "times_answered": 0,
                    "last_turn_no": None,
                    "linked_branch_ids": [],
                    "tree_depth": fpath.count("/"),
                }
"""

content = content.replace("    question_queue = {\"status\": \"empty\", \"items\": []}", "    question_queue = {\"status\": \"empty\", \"items\": []}\n" + state_init)

# Track inside loop
track_logic = """
        plan = turn.question_plan or {}
        repo_paths = plan.get("repo_selected_paths", [])
        for path in repo_paths:
            if path not in repo_file_coverage:
                repo_file_coverage[path] = {
                    "path": path,
                    "importance_score": calculate_structural_importance(path),
                    "exploration_score": 0.0,
                    "coverage_gap_score": 0.0,
                    "times_asked": 0,
                    "times_answered": 0,
                    "last_turn_no": None,
                    "linked_branch_ids": [],
                    "tree_depth": path.count("/"),
                }
            repo_file_coverage[path]["times_asked"] += 1
            if turn.answer_text:
                repo_file_coverage[path]["times_answered"] += 1
                repo_file_coverage[path]["last_turn_no"] = turn.turn_no
                repo_file_coverage[path]["exploration_score"] = min(1.0, repo_file_coverage[path]["exploration_score"] + 0.4)
                
"""
content = content.replace("        if not turn.answer_text:", track_logic + "        if not turn.answer_text:")

# Return repo_file_coverage
content = content.replace("\"repo_file_coverage\": {},", "\"repo_file_coverage\": repo_file_coverage,")


with open(fname, 'w') as f:
    f.write(content)

