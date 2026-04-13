from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.runtime import (
    get_env_file_path,
    get_runtime_root,
    normalize_database_url,
    resolve_runtime_path,
)

RUNTIME_ROOT = get_runtime_root()


class Settings(BaseSettings):
    app_name: str = "Stateful Interview Agent"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_llm_payloads: bool = True
    log_artifacts_enabled: bool = False
    log_pretty_json: bool = False
    log_text_preview_chars: int = 240
    max_question_length: int = 480

    llm_provider: Literal["openai_compatible", "anthropic", "opencode"] = (
        "openai_compatible"
    )

    openai_api_key: str = ""
    openai_base_url: str = "https://api.scnet.cn/api/llm/v1"
    openai_model: str = "MiniMax-M2.5"
    openai_embedding_model: str | None = None

    anthropic_api_key: str = ""
    anthropic_base_url: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_max_tokens: int = 4096

    opencode_base_url: str = "http://localhost:4096"
    opencode_timeout_seconds: float = 180.0
    opencode_model: str = "mindflow/claude-opus-4-6"
    duplicate_guard_use_embeddings: bool = False
    duplicate_guard_embedding_threshold: float = 0.9

    interview_min_turns: int = 36
    interview_max_turns: int = 37
    interview_panorama_turns: int = 1
    interview_architecture_turns: int = 2
    interview_code_detail_min_turns: int = 31
    interview_code_detail_max_turns: int = 32
    interview_use_case_turns: int = 2

    database_url: str = "sqlite:///./data/app.db"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return normalize_database_url(value, RUNTIME_ROOT)

    @field_validator("log_dir", mode="after")
    @classmethod
    def validate_log_dir(cls, value: str) -> str:
        return resolve_runtime_path(value, RUNTIME_ROOT)

    @model_validator(mode="after")
    def validate_interview_turn_plan(self) -> "Settings":
        if self.interview_min_turns > self.interview_max_turns:
            raise ValueError("INTERVIEW_MIN_TURNS must be less than or equal to INTERVIEW_MAX_TURNS")
        if self.interview_panorama_turns < 1:
            raise ValueError("INTERVIEW_PANORAMA_TURNS must be at least 1")
        if self.interview_architecture_turns < 1:
            raise ValueError("INTERVIEW_ARCHITECTURE_TURNS must be at least 1")
        if self.interview_use_case_turns < 1:
            raise ValueError("INTERVIEW_USE_CASE_TURNS must be at least 1")
        if self.interview_code_detail_min_turns < 1:
            raise ValueError("INTERVIEW_CODE_DETAIL_MIN_TURNS must be at least 1")
        if self.interview_code_detail_max_turns < self.interview_code_detail_min_turns:
            raise ValueError(
                "INTERVIEW_CODE_DETAIL_MAX_TURNS must be greater than or equal to INTERVIEW_CODE_DETAIL_MIN_TURNS"
            )

        fixed_turns = (
            self.interview_panorama_turns
            + self.interview_architecture_turns
            + self.interview_use_case_turns
        )
        expected_min_turns = fixed_turns + self.interview_code_detail_min_turns
        expected_max_turns = fixed_turns + self.interview_code_detail_max_turns

        if self.interview_min_turns != expected_min_turns:
            raise ValueError(
                "INTERVIEW_MIN_TURNS must equal panorama + architecture + code_detail_min + use_case turns"
            )
        if self.interview_max_turns != expected_max_turns:
            raise ValueError(
                "INTERVIEW_MAX_TURNS must equal panorama + architecture + code_detail_max + use_case turns"
            )

        return self


settings = Settings(_env_file=get_env_file_path())
