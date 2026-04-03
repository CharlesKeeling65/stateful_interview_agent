from app.services.coverage_service import default_framework_coverage, framework_gaps_for_stage


PANORAMA_STAGE = "Panorama Mapping"
ARCHITECTURE_STAGE = "Architecture Understanding"
CODE_DETAIL_STAGE = "Code Detail Completion"
USE_CASE_STAGE = "Use Cases & Scenarios"
WRAP_UP_STAGE = "Final Wrap-up"


def determine_stage_by_turn(turn_no: int) -> str:
    if 1 <= turn_no <= 5:
        return PANORAMA_STAGE
    elif 6 <= turn_no <= 10:
        return ARCHITECTURE_STAGE
    elif 11 <= turn_no <= 32:
        return CODE_DETAIL_STAGE
    else:
        return USE_CASE_STAGE


def decide_next_stage(
    *,
    next_turn_no: int,
    coverage_state: dict,
    current_stage: str,
    max_turns: int,
    human_review_signal: dict | None = None,
) -> dict:
    framework = coverage_state.get("framework", default_framework_coverage())
    stage_turn_counts = framework.get("stage_turn_counts", {})
    remaining_turns = max_turns - next_turn_no + 1
    wrap_up_ready = framework.get("wrap_up_ready", False)

    panorama_gaps = framework_gaps_for_stage(coverage_state, PANORAMA_STAGE)
    architecture_gaps = framework_gaps_for_stage(coverage_state, ARCHITECTURE_STAGE)
    code_detail_gaps = framework_gaps_for_stage(coverage_state, CODE_DETAIL_STAGE)
    use_case_gaps = framework_gaps_for_stage(coverage_state, USE_CASE_STAGE)
    collaboration_gaps = framework.get("gaps", {}).get("human_collaboration", [])
    human_phase_ready = bool((human_review_signal or {}).get("phase_ready"))

    if wrap_up_ready and remaining_turns <= 1:
        return {
            "next_stage": WRAP_UP_STAGE,
            "reason": "Framework coverage is broadly complete and only the final wrap-up turn remains.",
            "gaps": [],
        }

    panorama_turns = stage_turn_counts.get(PANORAMA_STAGE, 0)
    if current_stage == PANORAMA_STAGE and human_phase_ready and panorama_turns >= 2:
        return {
            "next_stage": ARCHITECTURE_STAGE,
            "reason": "A human marked panorama coverage as sufficiently complete, so the interview can move into architecture understanding.",
            "gaps": architecture_gaps,
        }
    if panorama_turns < 2 or panorama_gaps:
        return {
            "next_stage": PANORAMA_STAGE,
            "reason": f"Panorama coverage still has gaps: {', '.join(panorama_gaps[:3]) or 'need at least two panorama turns'}.",
            "gaps": panorama_gaps,
        }

    architecture_turns = stage_turn_counts.get(ARCHITECTURE_STAGE, 0)
    if current_stage == ARCHITECTURE_STAGE and human_phase_ready and architecture_turns >= 2:
        return {
            "next_stage": CODE_DETAIL_STAGE,
            "reason": "A human marked architecture coverage as sufficiently complete, so the interview can move into code detail.",
            "gaps": code_detail_gaps,
        }
    if architecture_turns < 3 or architecture_gaps:
        return {
            "next_stage": ARCHITECTURE_STAGE,
            "reason": f"Architecture understanding is not complete yet: {', '.join(architecture_gaps[:3]) or 'need more architecture turns'}.",
            "gaps": architecture_gaps,
        }

    if remaining_turns <= 2 and use_case_gaps:
        return {
            "next_stage": USE_CASE_STAGE,
            "reason": f"Only a few turns remain, so use-case coverage must be completed: {', '.join(use_case_gaps[:3])}.",
            "gaps": use_case_gaps,
        }

    if remaining_turns <= 1:
        return {
            "next_stage": WRAP_UP_STAGE,
            "reason": "The interview is at the final turn and should prepare for wrap-up.",
            "gaps": [],
        }

    code_detail_turns = stage_turn_counts.get(CODE_DETAIL_STAGE, 0)
    total_completed_turns = sum(stage_turn_counts.values())
    code_detail_share = (
        code_detail_turns / total_completed_turns if total_completed_turns > 0 else 0.0
    )
    target_code_detail_turns = max(8, int(max_turns * 0.45))
    code_detail_is_dominant = code_detail_turns >= 8 and code_detail_share >= 0.55

    if code_detail_is_dominant and use_case_gaps and remaining_turns <= max(10, max_turns // 4):
        return {
            "next_stage": USE_CASE_STAGE,
            "reason": (
                "Code-detail coverage has already dominated the interview, so the remaining turns "
                f"should complete use-case evidence: {', '.join(use_case_gaps[:3])}."
            ),
            "gaps": use_case_gaps,
        }

    if code_detail_gaps:
        if current_stage == CODE_DETAIL_STAGE and human_phase_ready and code_detail_turns >= max(6, max_turns // 5):
            return {
                "next_stage": USE_CASE_STAGE,
                "reason": "A human marked the current code-detail phase as sufficiently complete, so the remaining turns should collect scenario evidence.",
                "gaps": use_case_gaps,
            }
        return {
            "next_stage": CODE_DETAIL_STAGE,
            "reason": (
                "Code detail coverage must dominate the remaining interview turns. "
                f"Outstanding code-detail gaps: {', '.join(code_detail_gaps[:4]) or 'more implementation depth needed'}."
            ),
            "gaps": code_detail_gaps,
        }

    if code_detail_turns < target_code_detail_turns and not use_case_gaps:
        return {
            "next_stage": CODE_DETAIL_STAGE,
            "reason": (
                "Code-detail coverage is still growing, but scenario coverage is already complete, "
                "so the interview can spend another turn in implementation detail."
            ),
            "gaps": code_detail_gaps,
        }

    if use_case_gaps:
        return {
            "next_stage": USE_CASE_STAGE,
            "reason": f"Use-case and scenario coverage is still incomplete: {', '.join(use_case_gaps[:3])}.",
            "gaps": use_case_gaps,
        }

    if wrap_up_ready or (current_stage == USE_CASE_STAGE and human_phase_ready and not use_case_gaps):
        return {
            "next_stage": WRAP_UP_STAGE,
            "reason": "Framework coverage is complete enough to move into final wrap-up.",
            "gaps": [],
        }

    return {
        "next_stage": USE_CASE_STAGE if use_case_gaps else CODE_DETAIL_STAGE,
        "reason": (
            "Human collaboration gaps remain visible in the record and the remaining turns should stay inspectable."
            if collaboration_gaps and use_case_gaps
            else "Defaulting to code detail to keep implementation coverage dominant."
        ),
        "gaps": use_case_gaps if use_case_gaps else code_detail_gaps,
    }


def get_stage_instruction(stage: str) -> str:
    instructions = {
        PANORAMA_STAGE: (
            "Focus on the overall purpose, target users, project boundaries, "
            "major modules, and high-level workflow. Avoid deep implementation details."
        ),
        ARCHITECTURE_STAGE: (
            "Focus on module responsibilities, collaboration mechanisms, "
            "core call chains, system organization, and architectural rationale."
        ),
        CODE_DETAIL_STAGE: (
            "Focus on concrete files, classes, functions, methods, execution paths, "
            "error handling, third-party libraries, and implementation mechanisms."
        ),
        USE_CASE_STAGE: (
            "Focus on real usage scenarios, user roles, input/output patterns, "
            "configuration points, extension points, limitations, and boundary conditions."
        ),
        WRAP_UP_STAGE: (
            "Focus on final wrap-up readiness, missing evidence call-outs, and clean handoff preparation."
        ),
    }
    return instructions.get(stage, "")
