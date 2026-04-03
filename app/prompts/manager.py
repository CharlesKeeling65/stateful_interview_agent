from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any

import yaml

from app.prompts.schemas import PromptDefinition, RenderedPrompt


class PromptManager:
    def __init__(self, prompt_directory: Path | None = None):
        self.prompt_directory = prompt_directory or Path(__file__).resolve().parent / "assets"
        self._prompts = self._load_prompts()

    def _load_prompts(self) -> dict[str, PromptDefinition]:
        prompts: dict[str, PromptDefinition] = {}
        for prompt_path in sorted(self.prompt_directory.glob("*.yaml")):
            with prompt_path.open("r", encoding="utf-8") as handle:
                parsed = yaml.safe_load(handle) or {}
            definition = PromptDefinition.model_validate(parsed)
            prompts[definition.id] = definition
        return prompts

    def get(self, prompt_id: str) -> PromptDefinition:
        try:
            return self._prompts[prompt_id]
        except KeyError as exc:
            raise ValueError(f"Unknown prompt id: {prompt_id}") from exc

    def render(self, prompt_id: str, variables: dict[str, Any]) -> RenderedPrompt:
        definition = self.get(prompt_id)
        missing = [
            variable_name
            for variable_name in definition.required_variables
            if variable_name not in variables or variables[variable_name] is None
        ]
        if missing:
            raise ValueError(
                f"Prompt {prompt_id} is missing required variables: {', '.join(sorted(missing))}"
            )

        self._assert_no_unresolved_fields(definition.system_template, variables, prompt_id)
        self._assert_no_unresolved_fields(definition.user_template, variables, prompt_id)

        return RenderedPrompt(
            prompt_id=definition.id,
            version=definition.version,
            variables=variables,
            messages=[
                {
                    "role": "system",
                    "content": definition.system_template.format(**variables).strip(),
                },
                {
                    "role": "user",
                    "content": definition.user_template.format(**variables).strip(),
                },
            ],
        )

    def render_messages(self, prompt_id: str, variables: dict[str, Any]) -> list[dict[str, str]]:
        return self.render(prompt_id, variables).messages

    @staticmethod
    def _assert_no_unresolved_fields(
        template: str, variables: dict[str, Any], prompt_id: str
    ) -> None:
        formatter = Formatter()
        missing_fields = []
        for _, field_name, _, _ in formatter.parse(template):
            if field_name and field_name not in variables:
                missing_fields.append(field_name)
        if missing_fields:
            raise ValueError(
                f"Prompt {prompt_id} contains unresolved template fields: {', '.join(sorted(set(missing_fields)))}"
            )


@lru_cache(maxsize=1)
def get_prompt_manager() -> PromptManager:
    return PromptManager()
