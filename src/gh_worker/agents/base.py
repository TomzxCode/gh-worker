"""Base agent interface for LLM agents."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AgentEventType(Enum):
    """Types of events that can be emitted by an agent."""

    OUTPUT = "output"  # Regular output from the agent
    ERROR = "error"  # Error message
    STATUS = "status"  # Status update (e.g., "Starting...", "Completed")
    TOOL_USE = "tool_use"  # Agent is using a tool
    COMPLETION = "completion"  # Task completed successfully
    FAILURE = "failure"  # Task failed
    RESULT = "result"  # Final result/output to extract


@dataclass
class AgentEvent:
    """Event emitted by an agent during execution."""

    type: AgentEventType
    content: str
    metadata: dict[str, Any] | None = None


@dataclass
class AgentResult:
    """Result of an agent execution."""

    success: bool
    output: str
    session_id: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class BaseAgent(ABC):
    """Base class for all LLM agents."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the agent with configuration.

        Args:
            config: Agent-specific configuration
        """
        self.config = config or {}

    @abstractmethod
    async def plan(
        self, issue_content: str, repository_path: str
    ) -> AgentResult:
        """Generate an implementation plan for an issue.

        Args:
            issue_content: The full issue description
            repository_path: Path to the cloned repository

        Returns:
            AgentResult with the generated plan
        """
        pass

    @abstractmethod
    async def implement(
        self,
        issue_content: str,
        plan_content: str,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Implement the plan and create a PR.

        Args:
            issue_content: The full issue description
            plan_content: The generated plan
            repository_path: Path to the cloned repository
            issue_number: Issue number
            branch_name: Branch to create for the implementation

        Yields:
            AgentEvent objects as the implementation progresses
        """
        pass

    @abstractmethod
    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Monitor an ongoing agent session.

        Args:
            session_id: The session ID to monitor

        Yields:
            AgentEvent objects from the session
        """
        pass

    @abstractmethod
    async def commit(
        self,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Commit changes with a descriptive message.

        Args:
            repository_path: Path to the cloned repository
            issue_number: Issue number
            branch_name: Branch name

        Yields:
            AgentEvent objects as the commit progresses
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the agent name."""
        pass

    @property
    @abstractmethod
    def requires_cli(self) -> bool:
        """Return whether this agent requires an external CLI tool."""
        pass

    async def validate_environment(self) -> tuple[bool, str | None]:
        """Validate that the agent's environment is properly configured.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None
