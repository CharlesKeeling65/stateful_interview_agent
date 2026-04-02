def determine_stage_by_turn(turn_no: int) -> str:
    if 1 <= turn_no <= 5:
        return "Panorama Mapping"
    elif 6 <= turn_no <= 10:
        return "Architecture Understanding"
    elif 11 <= turn_no <= 32:
        return "Code Detail Completion"
    else:
        return "Use Cases & Scenarios"


def get_stage_instruction(stage: str) -> str:
    instructions = {
        "Panorama Mapping": (
            "Focus on the overall purpose, target users, project boundaries, "
            "major modules, and high-level workflow. Avoid deep implementation details."
        ),
        "Architecture Understanding": (
            "Focus on module responsibilities, collaboration mechanisms, "
            "core call chains, system organization, and architectural rationale."
        ),
        "Code Detail Completion": (
            "Focus on concrete files, classes, functions, methods, execution paths, "
            "error handling, third-party libraries, and implementation mechanisms."
        ),
        "Use Cases & Scenarios": (
            "Focus on real usage scenarios, user roles, input/output patterns, "
            "configuration points, extension points, limitations, and boundary conditions."
        ),
    }
    return instructions.get(stage, "")
