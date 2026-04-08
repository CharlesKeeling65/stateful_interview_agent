import json
import os
from pathlib import Path

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = PROJECT_ROOT / ".env"
PRIMARY_OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode.json"
FALLBACK_OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
OPENCODE_CONFIG_ENV_VAR = "STATEFUL_INTERVIEW_OPENCODE_CONFIG_PATH"
SECRET_MARKER = "••••••••"


def get_opencode_config_path() -> Path:
    configured_path = os.getenv(OPENCODE_CONFIG_ENV_VAR, "").strip()
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    if PRIMARY_OPENCODE_CONFIG_PATH.exists():
        return PRIMARY_OPENCODE_CONFIG_PATH
    return FALLBACK_OPENCODE_CONFIG_PATH


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return SECRET_MARKER
    return f"{value[:4]}{SECRET_MARKER}{value[-4:]}"


def is_secret_key(key: str) -> bool:
    normalized = key.upper()
    return any(token in normalized for token in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))


def read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8") or "{}")


def write_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=True, indent=4, sort_keys=True),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_env_map() -> dict[str, str]:
    if not ENV_FILE_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_map(values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    ENV_FILE_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def get_mindflow_options() -> dict[str, str]:
    config = read_json_file(get_opencode_config_path())
    provider = config.get("provider", {}) if isinstance(config, dict) else {}
    mindflow = provider.get("mindflow", {}) if isinstance(provider, dict) else {}
    options = mindflow.get("options", {}) if isinstance(mindflow, dict) else {}
    return options if isinstance(options, dict) else {}


def set_mindflow_options(*, base_url: str | None = None, api_key: str | None = None) -> Path:
    path = get_opencode_config_path()
    config = read_json_file(path)
    provider = config.setdefault("provider", {})
    mindflow = provider.setdefault("mindflow", {"npm": "@ai-sdk/anthropic"})
    options = mindflow.setdefault("options", {})
    if base_url is not None:
        options["baseURL"] = base_url
    if api_key is not None:
        options["apiKey"] = api_key
    write_json_file(path, config)
    return path


def resolve_effective_anthropic_config() -> dict[str, str | None]:
    mindflow = get_mindflow_options()
    api_key = mindflow.get("apiKey") or settings.anthropic_api_key or None
    base_url = mindflow.get("baseURL") or settings.anthropic_base_url or None
    source = "opencode.mindflow" if mindflow.get("apiKey") or mindflow.get("baseURL") else ".env"
    return {
        "api_key": api_key,
        "base_url": base_url,
        "source": source,
    }


def get_config_snapshot() -> dict:
    env_map = read_env_map()
    mindflow = get_mindflow_options()
    effective = resolve_effective_anthropic_config()
    return {
        "paths": {
            "opencode_config": str(get_opencode_config_path()),
            "env_file": str(ENV_FILE_PATH),
        },
        "opencode_mindflow": {
            "base_url": mindflow.get("baseURL", ""),
            "api_key_masked": mask_secret(mindflow.get("apiKey")),
            "has_api_key": bool(mindflow.get("apiKey")),
        },
        "effective_anthropic": {
            "base_url": effective["base_url"],
            "api_key_masked": mask_secret(effective["api_key"]),
            "has_api_key": bool(effective["api_key"]),
            "source": effective["source"],
        },
        "env_entries": [
            {
                "key": key,
                "value": mask_secret(value) if is_secret_key(key) else value,
                "is_secret": is_secret_key(key),
                "has_value": bool(value),
            }
            for key, value in env_map.items()
        ],
    }


def update_env_entries(entries: list[dict[str, str]]) -> None:
    env_map = read_env_map()
    for entry in entries:
        key = entry.get("key", "").strip()
        if not key:
            continue
        value = entry.get("value", "")
        env_map[key] = value
    write_env_map(env_map)
