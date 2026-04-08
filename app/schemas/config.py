from pydantic import BaseModel, Field


class ConfigPathRead(BaseModel):
    opencode_config: str
    env_file: str


class ConfigSectionRead(BaseModel):
    base_url: str | None = None
    api_key_masked: str = ""
    has_api_key: bool = False
    source: str | None = None


class EnvEntryRead(BaseModel):
    key: str
    value: str
    is_secret: bool = False
    has_value: bool = False


class ConfigSnapshotResponse(BaseModel):
    paths: ConfigPathRead
    opencode_mindflow: ConfigSectionRead
    effective_anthropic: ConfigSectionRead
    env_entries: list[EnvEntryRead] = Field(default_factory=list)


class OpencodeMindflowUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None


class EnvEntryUpdate(BaseModel):
    key: str
    value: str


class EnvEntriesUpdate(BaseModel):
    entries: list[EnvEntryUpdate] = Field(default_factory=list)
