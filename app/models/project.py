import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectSession(Base):
    __tablename__ = "project_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(100), default="Panorama Mapping")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    repo_source_type: Mapped[str] = mapped_column(String(32), default="none")
    repo_local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_git_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_git_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repo_cache_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    repo_manifest_json: Mapped[str] = mapped_column(Text, default="{}")
    coverage_state: Mapped[str] = mapped_column(
        Text,
        default='{"version": 1, "branch_count": 0, "updated_through_turn_no": 0, "branches": []}',
    )
    agent_mode: Mapped[str] = mapped_column(String(50), default="understand_current_code")
    rubric_task_board: Mapped[str] = mapped_column(Text, default="{}")
    pending_gate_json: Mapped[str] = mapped_column(Text, default="null")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    turns = relationship(
        "InterviewTurn", back_populates="project", cascade="all, delete-orphan"
    )
    llm_usages = relationship(
        "LLMUsage", back_populates="project", cascade="all, delete-orphan"
    )
    agent_runs = relationship(
        "AgentRun", back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def total_prompt_tokens(self) -> int:
        return sum(usage.prompt_tokens for usage in self.llm_usages)

    @property
    def total_completion_tokens(self) -> int:
        return sum(usage.completion_tokens for usage in self.llm_usages)

    @property
    def total_tokens(self) -> int:
        return sum(usage.total_tokens for usage in self.llm_usages)

    @property
    def estimated_total_tokens(self) -> int:
        return sum(usage.total_tokens for usage in self.llm_usages if usage.is_estimated)

    @property
    def coverage_state_data(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.coverage_state) if self.coverage_state else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("version", 1)
        parsed.setdefault("branch_count", len(parsed.get("branches", [])))
        parsed.setdefault("updated_through_turn_no", 0)
        parsed.setdefault("branches", [])
        return parsed

    @property
    def repo_manifest_data(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.repo_manifest_json) if self.repo_manifest_json else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("root_path", None)
        parsed.setdefault("file_count", 0)
        parsed.setdefault("language_counts", {})
        parsed.setdefault("top_level_directories", [])
        parsed.setdefault("key_files", [])
        parsed.setdefault("symbol_count", 0)
        parsed.setdefault("last_indexed_at", None)
        return parsed

    @property
    def repository(self) -> dict[str, Any]:
        return {
            "source_type": self.repo_source_type or "none",
            "local_path": self.repo_local_path,
            "git_url": self.repo_git_url,
            "git_ref": self.repo_git_ref,
            "cache_path": self.repo_cache_path,
            "commit_sha": self.repo_commit_sha,
        }

    @property
    def repository_manifest(self) -> dict[str, Any]:
        return self.repo_manifest_data

    @property
    def cumulative_generation_time_ms(self) -> int:
        return sum(run.duration_ms or 0 for run in self.agent_runs if run.status == "completed")

    @property
    def run_count(self) -> int:
        return sum(1 for run in self.agent_runs if run.status == "completed")

    @property
    def average_run_duration_ms(self) -> int:
        completed_runs = [run.duration_ms or 0 for run in self.agent_runs if run.status == "completed"]
        if not completed_runs:
            return 0
        return int(sum(completed_runs) / len(completed_runs))

    @property
    def rubric_task_board_data(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.rubric_task_board) if self.rubric_task_board else {}
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("version", 1)
        parsed.setdefault("phases", {})
        parsed.setdefault("phase_status", {})
        parsed.setdefault("current_phase", "panorama_mapping")
        return parsed

    @property
    def pending_gate(self) -> dict[str, Any] | None:
        if not self.pending_gate_json or self.pending_gate_json == "null":
            return None
        try:
            parsed = json.loads(self.pending_gate_json)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @property
    def rubric_task_board_summary(self) -> dict[str, Any]:
        board = self.rubric_task_board_data
        phases = board.get("phases", {})
        incomplete_task_count = 0
        completed_task_count = 0
        for tasks in phases.values():
            for task in tasks or []:
                status = (task or {}).get("status")
                if status == "completed":
                    completed_task_count += 1
                else:
                    incomplete_task_count += 1
        return {
            "current_phase": board.get("current_phase", "panorama_mapping"),
            "phase_status": board.get("phase_status", {}),
            "incomplete_task_count": incomplete_task_count,
            "completed_task_count": completed_task_count,
        }
