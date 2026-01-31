"""Agent registry for managing LLM agent implementations."""

from typing import Any

import structlog

from gh_worker.agents.base import BaseAgent
from gh_worker.agents.claude_code import ClaudeCodeAgent
from gh_worker.agents.codex import CodexAgent
from gh_worker.agents.cursor_agent import CursorAgent
from gh_worker.agents.gemini import GeminiAgent
from gh_worker.agents.mock import MockAgent
from gh_worker.agents.opencode import OpenCodeAgent

logger = structlog.get_logger()


class AgentRegistry:
    """Registry for managing available LLM agents."""

    def __init__(self):
        """Initialize the agent registry."""
        self._agents: dict[str, type[BaseAgent]] = {}
        self._default_agent: str | None = None

        # Register built-in agents
        self._register_builtin_agents()

    def _register_builtin_agents(self):
        """Register built-in agent implementations."""
        self.register("claude-code", ClaudeCodeAgent, default=True)
        self.register("cursor-agent", CursorAgent)
        self.register("opencode", OpenCodeAgent)
        self.register("gemini", GeminiAgent)
        self.register("codex", CodexAgent)
        self.register("mock", MockAgent)

    def register(
        self,
        name: str,
        agent_class: type[BaseAgent],
        default: bool = False,
    ):
        """Register an agent implementation.

        Args:
            name: Agent name (e.g., "claude-code", "opencode")
            agent_class: The agent class to register
            default: Whether this should be the default agent

        Raises:
            ValueError: If the agent name is already registered
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered")

        if not issubclass(agent_class, BaseAgent):
            raise TypeError("Agent class must be a subclass of BaseAgent")

        logger.debug("registering_agent", name=name, default=default)
        self._agents[name] = agent_class

        if default or self._default_agent is None:
            self._default_agent = name

    def unregister(self, name: str):
        """Unregister an agent implementation.

        Args:
            name: Agent name to unregister

        Raises:
            KeyError: If the agent is not registered
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")

        logger.info("unregistering_agent", name=name)
        del self._agents[name]

        if self._default_agent == name:
            self._default_agent = next(iter(self._agents.keys()), None)

    def get(self, name: str | None = None, config: dict[str, Any] | None = None) -> BaseAgent:
        """Get an agent instance by name.

        Args:
            name: Agent name (uses default if None)
            config: Configuration to pass to the agent

        Returns:
            Instantiated agent

        Raises:
            KeyError: If the agent is not registered
            ValueError: If no default agent is set and name is None
        """
        if name is None:
            if self._default_agent is None:
                raise ValueError("No default agent is set")
            name = self._default_agent

        if name not in self._agents:
            raise KeyError(
                f"Agent '{name}' is not registered. "
                f"Available agents: {', '.join(self._agents.keys())}"
            )

        agent_class = self._agents[name]
        logger.info("creating_agent_instance", name=name)
        return agent_class(config)

    def list_agents(self) -> list[str]:
        """List all registered agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def get_default_agent(self) -> str | None:
        """Get the name of the default agent.

        Returns:
            Default agent name or None if not set
        """
        return self._default_agent

    def set_default_agent(self, name: str):
        """Set the default agent.

        Args:
            name: Agent name to set as default

        Raises:
            KeyError: If the agent is not registered
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")

        logger.info("setting_default_agent", name=name)
        self._default_agent = name

    def is_registered(self, name: str) -> bool:
        """Check if an agent is registered.

        Args:
            name: Agent name to check

        Returns:
            True if registered, False otherwise
        """
        return name in self._agents


# Global registry instance
_global_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance.

    Returns:
        The global AgentRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def reset_registry():
    """Reset the global registry (primarily for testing)."""
    global _global_registry
    _global_registry = None
