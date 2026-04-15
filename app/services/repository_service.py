from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.project import ProjectSession

REPOSITORY_SOURCE_TYPES = {"none", "local_path", "git_url"}
REPO_CACHE_ROOT = Path("data/repo_cache")
IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".turbo",
    ".idea",
    ".vscode",
}
TEXT_FILE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".java",
    ".go",
    ".rb",
    ".rs",
    ".swift",
    ".kt",
    ".kts",
    ".php",
    ".cs",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".md",
    ".txt",
    ".ini",
    ".cfg",
    ".env",
    ".sql",
    ".html",
    ".css",
    ".scss",
    ".less",
    ".xml",
}
LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".cs": "C#",
    ".scala": "Scala",
    ".sh": "Shell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".md": "Markdown",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
}
KEY_FILE_CANDIDATES = (
    "README.md",
    "README_zh.md",
    "pyproject.toml",
    "package.json",
    "pnpm-workspace.yaml",
    "turbo.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "app/main.py",
    "main.py",
    "frontend/src/App.tsx",
)
SYMBOL_PATTERNS = [
    re.compile(r"^\s*class\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE),
    re.compile(r"^\s*def\s+([a-zA-Z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    re.compile(r"^\s*async\s+def\s+([a-zA-Z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?class\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?interface\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE),
    re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\(", re.MULTILINE),
]


class RepositoryConfigurationError(ValueError):
    pass


@dataclass
class RepositoryWorkspace:
    source_type: str
    source_label: str
    root_path: Path
    commit_sha: str | None
    cache_path: str | None
    manifest: dict[str, Any]


def normalize_repository_payload(repository: dict[str, Any] | None) -> dict[str, str | None]:
    repository = repository or {}
    source_type = str(repository.get("source_type") or "none").strip().lower()
    if source_type not in REPOSITORY_SOURCE_TYPES:
        raise RepositoryConfigurationError(
            "Repository source_type must be one of: none, local_path, git_url."
        )

    local_path = normalize_optional_text(repository.get("local_path"))
    git_url = normalize_optional_text(repository.get("git_url"))
    git_ref = normalize_optional_text(repository.get("git_ref"))

    if source_type == "local_path":
        if not local_path:
            raise RepositoryConfigurationError("A local repository path is required.")
        return {
            "source_type": source_type,
            "local_path": str(Path(local_path).expanduser().resolve()),
            "git_url": None,
            "git_ref": None,
        }

    if source_type == "git_url":
        if not git_url:
            raise RepositoryConfigurationError("A repository URL is required.")
        return {
            "source_type": source_type,
            "local_path": None,
            "git_url": git_url,
            "git_ref": git_ref,
        }

    return {
        "source_type": "none",
        "local_path": None,
        "git_url": None,
        "git_ref": None,
    }


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def apply_repository_configuration(project: ProjectSession, repository: dict[str, Any] | None) -> None:
    normalized = normalize_repository_payload(repository)
    project.repo_source_type = str(normalized["source_type"])
    project.repo_local_path = normalized["local_path"]
    project.repo_git_url = normalized["git_url"]
    project.repo_git_ref = normalized["git_ref"]
    if normalized["source_type"] == "none":
        project.repo_cache_path = None
        project.repo_commit_sha = None
        project.repo_manifest_json = "{}"


def resolve_project_repository(project: ProjectSession, *, persist: bool = True) -> RepositoryWorkspace | None:
    if project.repo_source_type == "none":
        return None

    if project.repo_source_type == "local_path":
        root_path = Path(project.repo_local_path or "").expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise RepositoryConfigurationError(f"Local repository path does not exist: {root_path}")
        cache_path = None
        source_label = str(root_path)
    elif project.repo_source_type == "git_url":
        git_url = project.repo_git_url or ""
        if not git_url:
            raise RepositoryConfigurationError("Repository URL is missing.")
        root_path = ensure_git_repository_cached(
            project_id=project.id,
            git_url=git_url,
            git_ref=project.repo_git_ref,
        )
        cache_path = str(root_path)
        source_label = git_url
    else:
        raise RepositoryConfigurationError(f"Unsupported repository source type: {project.repo_source_type}")

    manifest = build_repository_manifest(root_path)
    commit_sha = try_read_git_commit_sha(root_path)
    workspace = RepositoryWorkspace(
        source_type=project.repo_source_type,
        source_label=source_label,
        root_path=root_path,
        commit_sha=commit_sha,
        cache_path=cache_path,
        manifest=manifest,
    )

    if persist:
        project.repo_cache_path = cache_path
        project.repo_commit_sha = commit_sha
        project.repo_manifest_json = json.dumps(manifest, ensure_ascii=True, sort_keys=True)
    return workspace


def ensure_git_repository_cached(*, project_id: int, git_url: str, git_ref: str | None) -> Path:
    REPO_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{git_url}|{git_ref or ''}".encode("utf-8")).hexdigest()[:12]
    target = REPO_CACHE_ROOT / f"project-{project_id}-{digest}"
    if not target.exists():
        clone_command = [
            "git",
            "clone",
            "--filter=blob:none",
            "--depth",
            "1",
        ]
        if git_ref:
            clone_command.extend(["--branch", git_ref])
        clone_command.extend([git_url, str(target)])
        run_subprocess(clone_command, cwd=None)
    return target


def list_repository_files(root_path: Path) -> list[str]:
    if shutil_which("rg"):
        try:
            result = run_subprocess(
                ["rg", "--files", str(root_path)],
                cwd=None,
                allow_failure=False,
            )
            files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return [
                str(Path(file_path).relative_to(root_path))
                if Path(file_path).is_absolute()
                else file_path
                for file_path in files
                if not is_ignored_path(file_path)
            ]
        except Exception:
            pass

    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRECTORIES]
        for filename in filenames:
            absolute = Path(dirpath) / filename
            relative = absolute.relative_to(root_path)
            if is_ignored_path(relative.as_posix()):
                continue
            files.append(relative.as_posix())
    files.sort()
    return files


def build_repository_manifest(root_path: Path) -> dict[str, Any]:
    files = list_repository_files(root_path)
    language_counts: dict[str, int] = {}
    top_level_directories: set[str] = set()
    symbol_count = 0

    for relative_path in files[:1200]:
        path = Path(relative_path)
        if len(path.parts) > 1:
            top_level_directories.add(path.parts[0])
        suffix = path.suffix.lower()
        language = LANGUAGE_BY_SUFFIX.get(suffix)
        if language:
            language_counts[language] = language_counts.get(language, 0) + 1
        if is_probably_text_file(path):
            absolute_path = root_path / path
            try:
                content = absolute_path.read_text(encoding="utf-8")
            except Exception:
                continue
            symbol_count += len(extract_symbols_from_text(content))

    key_files = [candidate for candidate in KEY_FILE_CANDIDATES if (root_path / candidate).exists()]
    if not key_files:
        key_files = files[:8]

    return {
        "root_path": str(root_path),
        "file_count": len(files),
        "language_counts": dict(sorted(language_counts.items(), key=lambda item: (-item[1], item[0]))),
        "top_level_directories": sorted(top_level_directories)[:12],
        "key_files": key_files[:12],
        "symbol_count": symbol_count,
        "last_indexed_at": datetime.now(timezone.utc).isoformat(),
        "files_list": files[:2000],
    }


def search_repository_code(
    root_path: Path,
    query: str,
    *,
    limit: int = 8,
    literal: bool = True,
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    hits: list[dict[str, Any]] = []
    lowered_query = query.lower()

    for relative_path in list_repository_files(root_path):
        if lowered_query in relative_path.lower():
            hits.append(
                {
                    "path": relative_path,
                    "line_no": 1,
                    "line_text": f"path match for {relative_path}",
                }
            )
            if len(hits) >= limit:
                return hits[:limit]

    if shutil_which("rg"):
        command = ["rg", "-n", "--color", "never", "--max-count", "1"]
        if literal:
            command.append("-F")
        command.extend([query, str(root_path)])
        try:
            result = run_subprocess(command, cwd=None, allow_failure=True)
            for line in result.stdout.splitlines():
                parsed = parse_rg_match_line(root_path, line)
                if parsed:
                    hits.append(parsed)
                if len(hits) >= limit:
                    break
        except Exception:
            hits = []

    if hits:
        return hits[:limit]

    for relative_path in list_repository_files(root_path):
        absolute_path = root_path / relative_path
        if not is_probably_text_file(absolute_path):
            continue
        try:
            content = absolute_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            if lowered_query in line.lower():
                hits.append(
                    {
                        "path": relative_path,
                        "line_no": line_no,
                        "line_text": line.strip(),
                    }
                )
                break
        if len(hits) >= limit:
            break
    return hits[:limit]


def read_repository_snippet(
    root_path: Path,
    relative_path: str,
    *,
    center_line: int | None = None,
    window: int = 18,
    max_lines: int = 48,
) -> dict[str, Any] | None:
    target = root_path / relative_path
    if not target.exists() or not target.is_file():
        return None
    if not is_probably_text_file(target):
        return None
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    if center_line is None:
        start = 1
    else:
        start = max(1, center_line - window)
    end = min(len(lines), start + max_lines - 1)
    snippet_lines = lines[start - 1:end]
    snippet = "\n".join(f"{index}: {text}" for index, text in enumerate(snippet_lines, start=start))
    return {
        "path": relative_path,
        "start_line": start,
        "end_line": end,
        "content": snippet,
        "symbols": extract_symbols_from_text("\n".join(snippet_lines))[:8],
    }


def trace_repository_symbol(root_path: Path, symbol: str, *, limit: int = 8) -> dict[str, Any]:
    definition_hits = search_repository_code(root_path, f"def {symbol}", limit=2)
    if not definition_hits:
        definition_hits = search_repository_code(root_path, f"function {symbol}", limit=2)
    if not definition_hits:
        definition_hits = search_repository_code(root_path, f"class {symbol}", limit=2)
    call_hits = search_repository_code(root_path, f"{symbol}(", limit=limit)
    return {
        "symbol": symbol,
        "definitions": definition_hits[:2],
        "calls": call_hits[:limit],
    }


def extract_symbols_from_text(text: str) -> list[str]:
    symbols: list[str] = []
    for pattern in SYMBOL_PATTERNS:
        symbols.extend(pattern.findall(text))
    deduplicated: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        if symbol not in seen:
            seen.add(symbol)
            deduplicated.append(symbol)
    return deduplicated


def try_read_git_commit_sha(root_path: Path) -> str | None:
    try:
        result = run_subprocess(["git", "rev-parse", "HEAD"], cwd=root_path, allow_failure=True)
    except Exception:
        return None
    commit = result.stdout.strip()
    return commit or None


def run_subprocess(
    command: list[str],
    *,
    cwd: Path | None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 and not allow_failure:
        raise RepositoryConfigurationError(
            completed.stderr.strip() or f"Command failed: {' '.join(command)}"
        )
    return completed


def parse_rg_match_line(root_path: Path, line: str) -> dict[str, Any] | None:
    parts = line.split(":", 2)
    if len(parts) != 3:
        return None
    path_part, line_no_part, content = parts
    try:
        line_no = int(line_no_part)
    except ValueError:
        return None
    path = Path(path_part)
    relative_path = path.relative_to(root_path).as_posix() if path.is_absolute() else path.as_posix()
    return {
        "path": relative_path,
        "line_no": line_no,
        "line_text": content.strip(),
    }


def format_repository_manifest(manifest: dict[str, Any], *, source_label: str, commit_sha: str | None) -> str:
    language_counts = manifest.get("language_counts", {})
    languages = (
        ", ".join(f"{language} ({count})" for language, count in list(language_counts.items())[:6])
        or "Unknown"
    )
    top_level = ", ".join(manifest.get("top_level_directories", [])[:8]) or "None"
    key_files = ", ".join(manifest.get("key_files", [])[:8]) or "None"
    return "\n".join(
        [
            f"Repository source: {source_label}",
            f"Commit: {commit_sha or 'unknown'}",
            f"Files indexed: {manifest.get('file_count', 0)}",
            f"Languages: {languages}",
            f"Top-level directories: {top_level}",
            f"Key files: {key_files}",
            f"Indexed symbols: {manifest.get('symbol_count', 0)}",
        ]
    )


def is_probably_text_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    return suffix in TEXT_FILE_EXTENSIONS or path.name in {"Dockerfile", ".env", "Makefile"}


def is_ignored_path(path_value: str) -> bool:
    normalized = path_value.replace("\\", "/")
    return any(f"/{ignored}/" in f"/{normalized}/" for ignored in IGNORED_DIRECTORIES)


def shutil_which(command: str) -> str | None:
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(folder) / command
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
