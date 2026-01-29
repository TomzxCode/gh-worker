"""Agent session management."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class SessionStatus(Enum):
    """Status of an agent session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentSession:
    """Represents an agent execution session."""

    session_id: str
    agent_name: str
    issue_number: int
    repository: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    task_type: str  # "plan" or "implement"
    branch_name: str | None = None
    pr_url: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary.

        Returns:
            Dictionary representation
        """
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSession":
        """Create session from dictionary.

        Args:
            data: Dictionary with session data

        Returns:
            AgentSession instance
        """
        data = data.copy()
        data["status"] = SessionStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class SessionStore:
    """Store and manage agent sessions."""

    def __init__(self, base_path: Path):
        """Initialize the session store.

        Args:
            base_path: Base directory for session storage
        """
        self.base_path = Path(base_path)
        self.sessions_dir = self.base_path / ".sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session.

        Args:
            session_id: Session ID

        Returns:
            Path to session file
        """
        return self.sessions_dir / f"{session_id}.json"

    def save(self, session: AgentSession):
        """Save a session to disk.

        Args:
            session: Session to save
        """
        session_path = self._get_session_path(session.session_id)
        logger.info("saving_session", session_id=session.session_id, path=str(session_path))

        with open(session_path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def load(self, session_id: str) -> AgentSession | None:
        """Load a session from disk.

        Args:
            session_id: Session ID to load

        Returns:
            AgentSession if found, None otherwise
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            logger.warning("session_not_found", session_id=session_id)
            return None

        logger.info("loading_session", session_id=session_id)

        with open(session_path) as f:
            data = json.load(f)

        return AgentSession.from_dict(data)

    def update_status(
        self,
        session_id: str,
        status: SessionStatus,
        error: str | None = None,
        branch_name: str | None = None,
        pr_url: str | None = None,
    ):
        """Update session status.

        Args:
            session_id: Session ID to update
            status: New status
            error: Error message if status is FAILED
            branch_name: Branch name if available
            pr_url: PR URL if available
        """
        session = self.load(session_id)
        if session is None:
            logger.error("cannot_update_session", session_id=session_id, reason="not_found")
            return

        session.status = status
        session.updated_at = datetime.now()

        if error is not None:
            session.error = error
        if branch_name is not None:
            session.branch_name = branch_name
        if pr_url is not None:
            session.pr_url = pr_url

        self.save(session)

    def list_sessions(
        self,
        repository: str | None = None,
        status: SessionStatus | None = None,
        task_type: str | None = None,
    ) -> list[AgentSession]:
        """List sessions with optional filters.

        Args:
            repository: Filter by repository (e.g., "owner/repo")
            status: Filter by status
            task_type: Filter by task type ("plan" or "implement")

        Returns:
            List of matching sessions
        """
        sessions = []

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)
                session = AgentSession.from_dict(data)

                # Apply filters
                if repository and session.repository != repository:
                    continue
                if status and session.status != status:
                    continue
                if task_type and session.task_type != task_type:
                    continue

                sessions.append(session)

            except Exception as e:
                logger.error("failed_to_load_session", file=str(session_file), error=str(e))

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions

    def delete(self, session_id: str):
        """Delete a session.

        Args:
            session_id: Session ID to delete
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            logger.warning("cannot_delete_session", session_id=session_id, reason="not_found")
            return

        logger.info("deleting_session", session_id=session_id)
        session_path.unlink()

    def create_session(
        self,
        session_id: str,
        agent_name: str,
        issue_number: int,
        repository: str,
        task_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSession:
        """Create a new session.

        Args:
            session_id: Unique session ID
            agent_name: Name of the agent
            issue_number: Issue number
            repository: Repository (e.g., "owner/repo")
            task_type: Task type ("plan" or "implement")
            metadata: Additional metadata

        Returns:
            Created AgentSession
        """
        now = datetime.now()
        session = AgentSession(
            session_id=session_id,
            agent_name=agent_name,
            issue_number=issue_number,
            repository=repository,
            status=SessionStatus.PENDING,
            created_at=now,
            updated_at=now,
            task_type=task_type,
            metadata=metadata,
        )

        self.save(session)
        return session

    def get_active_sessions(self, repository: str | None = None) -> list[AgentSession]:
        """Get all active (running or pending) sessions.

        Args:
            repository: Filter by repository

        Returns:
            List of active sessions
        """
        all_sessions = self.list_sessions(repository=repository)
        return [
            s for s in all_sessions if s.status in (SessionStatus.PENDING, SessionStatus.RUNNING)
        ]
