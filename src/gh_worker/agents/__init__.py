"""Agent abstraction layer for LLM agents."""

from gh_worker.agents.base import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    BaseAgent,
)
from gh_worker.agents.claude_code import ClaudeCodeAgent
from gh_worker.agents.cursor_agent import CursorAgent
from gh_worker.agents.registry import AgentRegistry, get_registry, reset_registry
from gh_worker.agents.session import AgentSession, SessionStatus, SessionStore

__all__ = [
    "AgentEvent",
    "AgentEventType",
    "AgentResult",
    "BaseAgent",
    "ClaudeCodeAgent",
    "CursorAgent",
    "AgentRegistry",
    "get_registry",
    "reset_registry",
    "AgentSession",
    "SessionStatus",
    "SessionStore",
]
