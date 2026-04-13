import os
import unittest
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.core.config import Settings, settings
from app.services.stage_manager import decide_next_stage


class StageConfigurationTests(unittest.TestCase):
    def test_settings_expose_explicit_stage_turn_targets(self):
        configured = Settings(
            _env_file=None,
            interview_min_turns=36,
            interview_max_turns=37,
            interview_panorama_turns=1,
            interview_architecture_turns=2,
            interview_code_detail_min_turns=31,
            interview_code_detail_max_turns=32,
            interview_use_case_turns=2,
        )

        self.assertEqual(configured.interview_min_turns, 36)
        self.assertEqual(configured.interview_max_turns, 37)
        self.assertEqual(configured.interview_panorama_turns, 1)
        self.assertEqual(configured.interview_architecture_turns, 2)
        self.assertEqual(configured.interview_code_detail_min_turns, 31)
        self.assertEqual(configured.interview_code_detail_max_turns, 32)
        self.assertEqual(configured.interview_use_case_turns, 2)

    def test_stage_controller_can_leave_panorama_after_one_turn(self):
        coverage_state = {
            "framework": {
                "panorama": {
                    "purpose": True,
                    "target_users": True,
                    "boundaries": True,
                    "major_modules": True,
                    "high_level_workflow": True,
                    "initial_module_relationships": True,
                },
                "architecture": {
                    "architecture_style_or_organization": False,
                    "module_responsibilities": False,
                    "collaboration_mechanisms": False,
                    "key_call_chains": False,
                    "system_structure": False,
                    "design_rationale_or_quality_attributes": False,
                },
                "code_detail": {},
                "use_cases": {},
                "human_collaboration": {},
                "stage_turn_counts": {
                    "Panorama Mapping": 1,
                    "Architecture Understanding": 0,
                },
                "gaps": {
                    "panorama": [],
                    "architecture": ["module_responsibilities", "key_call_chains"],
                    "code_detail": [],
                    "use_cases": [],
                    "human_collaboration": [],
                },
                "wrap_up_ready": False,
            }
        }

        with patch.object(settings, "interview_panorama_turns", 1, create=True):
            decision = decide_next_stage(
                next_turn_no=2,
                coverage_state=coverage_state,
                current_stage="Panorama Mapping",
                max_turns=36,
            )

        self.assertEqual(decision["next_stage"], "Architecture Understanding")


if __name__ == "__main__":
    unittest.main()
