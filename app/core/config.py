from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Stateful Interview Agent"
    app_env: str = "dev"
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_llm_payloads: bool = True
    log_artifacts_enabled: bool = False
    log_pretty_json: bool = False
    log_text_preview_chars: int = 240

    openai_api_key: str
    openai_base_url: str = "https://api.scnet.cn/api/llm/v1"
    openai_model: str = "MiniMax-M2.5"
    openai_embedding_model: str | None = None
    duplicate_guard_use_embeddings: bool = False
    duplicate_guard_embedding_threshold: float = 0.9

    interview_min_turns: int = 35
    interview_max_turns: int = 40

    database_url: str = "sqlite:///./data/app.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
