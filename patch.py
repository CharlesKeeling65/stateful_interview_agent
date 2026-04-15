import re

fname = 'app/graphs/interview_nodes.py'
with open(fname, 'r') as f:
    code = f.read()

# Add force_llm_generation to generate_question_for_state
code = code.replace("    review_result: dict | None = None,\n) -> dict:", "    review_result: dict | None = None,\n    force_llm_generation: bool = False,\n) -> dict:")

# Add parameter to draft_question_from_answered_history
code = code.replace("    review_result: dict | None = None,\n) -> dict:", "    review_result: dict | None = None,\n    force_llm_generation: bool = False,\n) -> dict:")

# Update recursive call in draft_question_from_answered_history
code = code.replace("planner_decision_override=planner_decision_override,\n        review_result=review_result,\n    )", "planner_decision_override=planner_decision_override,\n        review_result=review_result,\n        force_llm_generation=force_llm_generation,\n    )")

with open(fname, 'w') as f:
    f.write(code)

