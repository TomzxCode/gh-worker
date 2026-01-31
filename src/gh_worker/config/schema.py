"""Configuration schema using Pydantic models."""

from pathlib import Path

from pydantic import BaseModel, Field


class PlanConfig(BaseModel):
    """Configuration for plan command."""

    parallelism: int = Field(default=1, ge=1, description="Number of parallel plan executions")


class ImplementConfig(BaseModel):
    """Configuration for implement command."""

    parallelism: int = Field(default=1, ge=1, description="Number of parallel implementations")
    use_worktree: bool = Field(
        default=True, description="Use git worktree for isolated implementation branches"
    )
    push_branch: bool = Field(
        default=False, description="Push branch to remote after implementation"
    )
    create_pr: bool = Field(
        default=False, description="Create pull request after implementation"
    )
    delete_worktree: bool = Field(
        default=True, description="Delete worktree after implementation completes"
    )


class SyncConfig(BaseModel):
    """Configuration for sync command."""

    frequency: str = Field(default="1h", description="Sync frequency (e.g., '10m', '1h', '1d')")


class AgentConfig(BaseModel):
    """Configuration for LLM agents."""

    default: str = Field(default="claude-code", description="Default agent to use")
    claude_code_path: str | None = Field(default=None, description="Path to claude-code binary")


class AppConfig(BaseModel):
    """Application configuration."""

    issues_path: Path | None = Field(default=None, description="Path to store issue files")
    repository_path: Path | None = Field(default=None, description="Path to clone repositories")
    plan: PlanConfig = Field(default_factory=PlanConfig)
    implement: ImplementConfig = Field(default_factory=ImplementConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
