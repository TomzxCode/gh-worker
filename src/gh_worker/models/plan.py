"""Plan data model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class PlanStatus(Enum):
    """Status of a plan."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanMetadata:
    """Metadata for an implementation plan."""

    issue_number: int
    repository: str
    created_at: datetime
    status: PlanStatus = PlanStatus.PENDING
    session_id: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
    plan_file: Path | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization.

        Returns:
            Dictionary representation
        """
        return {
            "issue_number": self.issue_number,
            "repository": self.repository,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "session_id": self.session_id,
            "branch_name": self.branch_name,
            "pr_url": self.pr_url,
            "error_message": self.error_message,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanMetadata":
        """Create from dictionary (YAML deserialization).

        Args:
            data: Dictionary from YAML

        Returns:
            PlanMetadata instance
        """
        return cls(
            issue_number=data["issue_number"],
            repository=data["repository"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=PlanStatus(data.get("status", "pending")),
            session_id=data.get("session_id"),
            branch_name=data.get("branch_name"),
            pr_url=data.get("pr_url"),
            error_message=data.get("error_message"),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
        )

    def save(self, path: Path) -> None:
        """Save metadata to YAML file.

        Args:
            path: Path to metadata file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, sort_keys=False, default_flow_style=False)

    @classmethod
    def load(cls, path: Path) -> "PlanMetadata":
        """Load metadata from YAML file.

        Args:
            path: Path to metadata file

        Returns:
            PlanMetadata instance
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
