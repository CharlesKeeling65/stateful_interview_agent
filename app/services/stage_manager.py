from app.services.coverage_service import (
    default_framework_coverage,
    framework_gaps_for_stage,
    normalize_framework_coverage,
)


PANORAMA_STAGE = "Panorama Mapping"
ARCHITECTURE_STAGE = "Architecture Understanding"
CODE_DETAIL_STAGE = "Code Detail Completion"
USE_CASE_STAGE = "Use Cases & Scenarios"
WRAP_UP_STAGE = "Final Wrap-up"

STAGE_ALIASES = {
    "panorama": PANORAMA_STAGE,
    "panorama_mapping": PANORAMA_STAGE,
    "panorama mapping": PANORAMA_STAGE,
    "architecture": ARCHITECTURE_STAGE,
    "architecture_understanding": ARCHITECTURE_STAGE,
    "architecture understanding": ARCHITECTURE_STAGE,
    "code_detail": CODE_DETAIL_STAGE,
    "code_detail_completion": CODE_DETAIL_STAGE,
    "code detail": CODE_DETAIL_STAGE,
    "code detail completion": CODE_DETAIL_STAGE,
    "use_case": USE_CASE_STAGE,
    "use_cases": USE_CASE_STAGE,
    "use_case_scenarios": USE_CASE_STAGE,
    "use cases & scenarios": USE_CASE_STAGE,
    "use cases and scenarios": USE_CASE_STAGE,
    "final_wrap_up": WRAP_UP_STAGE,
    "final wrap-up": WRAP_UP_STAGE,
    "wrap_up": WRAP_UP_STAGE,
    "wrap up": WRAP_UP_STAGE,
}

STAGE_SEQUENCE = [
    PANORAMA_STAGE,
    ARCHITECTURE_STAGE,
    CODE_DETAIL_STAGE,
    USE_CASE_STAGE,
    WRAP_UP_STAGE,
]


def normalize_stage_name(value: str | None) -> str | None:
    if not value:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    normalized = candidate.lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())

    if candidate in {
        PANORAMA_STAGE,
        ARCHITECTURE_STAGE,
        CODE_DETAIL_STAGE,
        USE_CASE_STAGE,
        WRAP_UP_STAGE,
    }:
        return candidate

    return STAGE_ALIASES.get(normalized) or STAGE_ALIASES.get(normalized.replace(" ", "_"))


def stage_rank(stage: str | None) -> int:
    normalized = normalize_stage_name(stage)
    if not normalized:
        return -1
    try:
        return STAGE_SEQUENCE.index(normalized)
    except ValueError:
        return -1


def clamp_stage_not_before_current(candidate_stage: str, current_stage: str) -> str:
    if stage_rank(candidate_stage) < stage_rank(current_stage):
        return normalize_stage_name(current_stage) or current_stage
    return candidate_stage


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
    framework = normalize_framework_coverage(
        coverage_state.get("framework", default_framework_coverage())
    )
    stage_turn_counts = framework.get("stage_turn_counts", {})
    remaining_turns = max_turns - next_turn_no + 1
    wrap_up_ready = framework.get("wrap_up_ready", False)

    panorama_gaps = framework_gaps_for_stage(coverage_state, PANORAMA_STAGE)
    architecture_gaps = framework_gaps_for_stage(coverage_state, ARCHITECTURE_STAGE)
    code_detail_gaps = framework_gaps_for_stage(coverage_state, CODE_DETAIL_STAGE)
    use_case_gaps = framework_gaps_for_stage(coverage_state, USE_CASE_STAGE)
    collaboration_gaps = framework.get("gaps", {}).get("human_collaboration", [])
    human_phase_ready = bool((human_review_signal or {}).get("phase_ready"))
    human_direction = (human_review_signal or {}).get("direction")
    preferred_focus = ((human_review_signal or {}).get("preferred_next_focus") or "").strip().lower()
    explicit_use_case_request = preferred_focus in {"scenario", "use_case", "use cases", "actors", "inputs", "outputs", "boundary"}

    panorama_required = {"purpose", "target_users", "major_modules", "high_level_workflow"}
    architecture_required = {
        "module_responsibilities",
        "collaboration_mechanisms",
        "key_call_chains",
        "system_structure",
    }
    code_detail_required = {
        "specific_files_count",
        "specific_methods_count",
        "execution_paths_count",
        "error_handling_points_count",
    }
    use_case_required = {
        "representative_scenarios_count",
        "actors_roles_count",
        "input_output_patterns_count",
        "boundary_conditions_count",
    }

    panorama_turns = stage_turn_counts.get(PANORAMA_STAGE, 0)
    panorama_critical_gaps = [gap for gap in panorama_gaps if gap in panorama_required]
    if current_stage == PANORAMA_STAGE and human_phase_ready and panorama_turns >= 2 and len(panorama_critical_gaps) <= 1:
        return {
            "next_stage": clamp_stage_not_before_current(ARCHITECTURE_STAGE, current_stage),
            "reason": "A human marked panorama coverage as sufficiently complete, so the interview can move into architecture understanding.",
            "gaps": architecture_gaps,
        }
    if panorama_turns < 2 or panorama_critical_gaps or len(panorama_gaps) > 1:
        return {
            "next_stage": clamp_stage_not_before_current(PANORAMA_STAGE, current_stage),
            "reason": f"Panorama coverage still has macro gaps: {', '.join((panorama_critical_gaps or panorama_gaps)[:3]) or 'need at least two panorama turns'}.",
            "gaps": panorama_gaps,
        }

    architecture_turns = stage_turn_counts.get(ARCHITECTURE_STAGE, 0)
    architecture_critical_gaps = [gap for gap in architecture_gaps if gap in architecture_required]
    if current_stage == ARCHITECTURE_STAGE and human_phase_ready and architecture_turns >= 3 and len(architecture_critical_gaps) <= 1:
        return {
            "next_stage": clamp_stage_not_before_current(CODE_DETAIL_STAGE, current_stage),
            "reason": "A human marked architecture coverage as sufficiently complete, so the interview can move into code detail.",
            "gaps": code_detail_gaps,
        }
    if architecture_turns < 3 or architecture_critical_gaps or len(architecture_gaps) > 1:
        return {
            "next_stage": clamp_stage_not_before_current(ARCHITECTURE_STAGE, current_stage),
            "reason": f"Architecture understanding is not complete yet: {', '.join((architecture_critical_gaps or architecture_gaps)[:3]) or 'need more architecture turns'}.",
            "gaps": architecture_gaps,
        }

    if remaining_turns <= 2 and use_case_gaps and (current_stage != ARCHITECTURE_STAGE or explicit_use_case_request):
        return {
            "next_stage": clamp_stage_not_before_current(USE_CASE_STAGE, current_stage),
            "reason": f"Only a few turns remain, so use-case coverage must be completed: {', '.join(use_case_gaps[:3])}.",
            "gaps": use_case_gaps,
        }

    if remaining_turns <= 1:
        return {
            "next_stage": clamp_stage_not_before_current(WRAP_UP_STAGE, current_stage),
            "reason": "The interview is at the final turn and should prepare for wrap-up.",
            "gaps": [],
        }

    code_detail_turns = stage_turn_counts.get(CODE_DETAIL_STAGE, 0)
    total_completed_turns = sum(stage_turn_counts.values())
    code_detail_share = (
        code_detail_turns / total_completed_turns if total_completed_turns > 0 else 0.0
    )
    target_code_detail_turns = max(10, int(max_turns * 0.65))
    code_detail_is_dominant = code_detail_turns >= 8 and code_detail_share >= 0.55
    code_detail_core_gaps = [gap for gap in code_detail_gaps if gap in code_detail_required]
    use_case_core_gaps = [gap for gap in use_case_gaps if gap in use_case_required]
    architecture_can_enter_use_cases = (
          current_stage != ARCHITECTURE_STAGE
          or explicit_use_case_request
          or code_detail_is_dominant
          or code_detail_turns >= target_code_detail_turns
      )

    if use_case_core_gaps and (remaining_turns <= max(4, len(use_case_core_gaps) + 1)) and architecture_can_enter_use_cases:
        return {
            "next_stage": clamp_stage_not_before_current(USE_CASE_STAGE, current_stage),
            "reason": (
                "The interview is entering its closing window, so the remaining turns must complete "
                f"the missing scenario contract: {', '.join(use_case_core_gaps[:3])}."
            ),
            "gaps": use_case_core_gaps,
        }

    if wrap_up_ready and remaining_turns <= 1 and not use_case_core_gaps:
        return {
            "next_stage": clamp_stage_not_before_current(WRAP_UP_STAGE, current_stage),
            "reason": "Framework coverage is broadly complete and only the final wrap-up turn remains.",
            "gaps": [],
        }

    if code_detail_core_gaps:
        if (
            current_stage == CODE_DETAIL_STAGE
            and human_phase_ready
            and code_detail_turns >= max(8, max_turns // 4)
            and not use_case_core_gaps
        ):
            return {
                "next_stage": clamp_stage_not_before_current(USE_CASE_STAGE, current_stage),
                "reason": "A human marked the current code-detail phase as sufficiently complete, so the remaining turns should collect scenario evidence.",
                "gaps": use_case_gaps,
            }
        return {
            "next_stage": clamp_stage_not_before_current(CODE_DETAIL_STAGE, current_stage),
            "reason": (
                "Code detail coverage must dominate the remaining interview turns. "
                f"Outstanding code-detail gaps: {', '.join(code_detail_core_gaps[:4]) or 'more implementation depth needed'}."
            ),
            "gaps": code_detail_core_gaps,
        }

    if (
        code_detail_turns < target_code_detail_turns
        and not use_case_core_gaps
        and human_direction != "redirect"
    ):
        return {
            "next_stage": clamp_stage_not_before_current(CODE_DETAIL_STAGE, current_stage),
            "reason": (
                "Code-detail should still dominate the transcript, and the current implementation coverage "
                "has not yet reached the target depth."
            ),
            "gaps": code_detail_gaps,
        }

    if use_case_core_gaps and architecture_can_enter_use_cases:
        return {
            "next_stage": clamp_stage_not_before_current(USE_CASE_STAGE, current_stage),
            "reason": f"Use-case and scenario coverage is still incomplete: {', '.join(use_case_core_gaps[:3])}.",
            "gaps": use_case_core_gaps,
        }

    if wrap_up_ready or (current_stage == USE_CASE_STAGE and human_phase_ready and not use_case_gaps):
        return {
            "next_stage": clamp_stage_not_before_current(WRAP_UP_STAGE, current_stage),
            "reason": "Framework coverage is complete enough to move into final wrap-up.",
            "gaps": [],
        }

    return {
        "next_stage": clamp_stage_not_before_current(
            USE_CASE_STAGE if (use_case_gaps and architecture_can_enter_use_cases) else CODE_DETAIL_STAGE,
            current_stage,
        ),
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
