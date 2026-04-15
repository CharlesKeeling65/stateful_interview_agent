import sys

fname = 'app/graphs/interview_nodes.py'
with open(fname, 'r') as f:
    content = f.read()

content = content.replace("coverage_state = rebuild_coverage_state(turns)", "coverage_state = rebuild_coverage_state(turns, project)")
content = content.replace("refreshed_coverage_state = rebuild_coverage_state(all_turns)", "refreshed_coverage_state = rebuild_coverage_state(all_turns, project)")
content = content.replace("refreshed_coverage_state = rebuild_coverage_state([*all_turns, next_turn])", "refreshed_coverage_state = rebuild_coverage_state([*all_turns, next_turn], project)")

with open(fname, 'w') as f:
    f.write(content)

