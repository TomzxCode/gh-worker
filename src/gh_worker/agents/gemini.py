"""Gemini agent implementation (placeholder)."""

from collections.abc import AsyncIterator
from typing import Any

import structlog

from gh_worker.agents.base import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    BaseAgent,
)

logger = structlog.get_logger()


class GeminiAgent(BaseAgent):
    """Agent that uses Google Gemini (placeholder implementation)."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Gemini agent.

        Args:
            config: Agent configuration
        """
        super().__init__(config)
        self.api_key = config.get("api_key") if config else None
        self.model = config.get("model", "gemini-pro") if config else "gemini-pro"

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "gemini"

    @property
    def requires_cli(self) -> bool:
        """Return whether this agent requires an external CLI tool."""
        return False

    async def validate_environment(self) -> tuple[bool, str | None]:
        """Validate that the Gemini environment is properly configured.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.api_key:
            return (
                False,
                "Gemini API key not configured. Please set 'api_key' in agent config.",
            )
        return True, None

    async def plan(
        self, issue_content: str, repository_path: str
    ) -> AgentResult:
        """Generate an implementation plan for an issue using Gemini.

        Args:
            issue_content: The full issue description
            repository_path: Path to the cloned repository

        Returns:
            AgentResult with the generated plan
        """
        logger.warning(
            "gemini_agent_not_implemented",
            message="Gemini agent is a placeholder and not yet implemented",
        )

        return AgentResult(
            success=False,
            output="",
            error="Gemini agent is not yet implemented. Please use claude-code instead.",
            metadata={"agent": "gemini"},
        )

    async def implement(
        self,
        issue_content: str,
        plan_content: str,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Implement the plan using Gemini.

        Args:
            issue_content: The full issue description
            plan_content: The generated plan
            repository_path: Path to the cloned repository
            issue_number: Issue number
            branch_name: Branch to create for the implementation

        Yields:
            AgentEvent objects as the implementation progresses
        """
        logger.warning(
            "gemini_agent_not_implemented",
            issue_number=issue_number,
            message="Gemini agent is a placeholder and not yet implemented",
        )

        yield AgentEvent(
            type=AgentEventType.ERROR,
            content="Gemini agent is not yet implemented. Please use claude-code instead.",
            metadata={"issue_number": issue_number, "agent": "gemini"},
        )

    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Monitor an ongoing Gemini session.

        Args:
            session_id: The session ID to monitor

        Yields:
            AgentEvent objects from the session
        """
        logger.warning("gemini_agent_not_implemented", session_id=session_id)

        yield AgentEvent(
            type=AgentEventType.ERROR,
            content="Gemini agent is not yet implemented. Please use claude-code instead.",
            metadata={"session_id": session_id, "agent": "gemini"},
        )
