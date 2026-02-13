"""Tests for agent implementations."""

import pytest

from gh_worker.agents.base import AgentEventType
from gh_worker.agents.claude_code import ClaudeCodeAgent
from gh_worker.agents.codex import CodexAgent
from gh_worker.agents.gemini import GeminiAgent
from gh_worker.agents.opencode import OpenCodeAgent
from gh_worker.agents.registry import AgentRegistry, get_registry, reset_registry


class TestAgentRegistry:
    """Test AgentRegistry functionality."""

    @pytest.fixture(autouse=True)
    def reset_global_registry(self):
        """Reset global registry before each test."""
        reset_registry()
        yield
        reset_registry()

    def test_registry_initialization(self):
        """Test that registry initializes with built-in agents."""
        registry = AgentRegistry()
        agents = registry.list_agents()

        assert "claude-code" in agents
        assert "opencode" in agents
        assert "gemini" in agents
        assert "codex" in agents

    def test_default_agent(self):
        """Test default agent is claude-code."""
        registry = AgentRegistry()
        assert registry.get_default_agent() == "claude-code"

    def test_register_new_agent(self):
        """Test registering a new agent."""
        registry = AgentRegistry()

        class CustomAgent(ClaudeCodeAgent):
            @property
            def name(self) -> str:
                return "custom"

        registry.register("custom", CustomAgent)
        assert "custom" in registry.list_agents()

    def test_register_duplicate_agent(self):
        """Test that registering duplicate agent raises error."""
        registry = AgentRegistry()

        with pytest.raises(ValueError, match="already registered"):
            registry.register("claude-code", ClaudeCodeAgent)

    def test_get_agent_instance(self):
        """Test getting an agent instance."""
        registry = AgentRegistry()
        agent = registry.get("claude-code")

        assert isinstance(agent, ClaudeCodeAgent)
        assert agent.name == "claude-code"

    def test_get_nonexistent_agent(self):
        """Test getting a nonexistent agent raises error."""
        registry = AgentRegistry()

        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent")

    def test_unregister_agent(self):
        """Test unregistering an agent."""
        registry = AgentRegistry()

        registry.unregister("opencode")
        assert "opencode" not in registry.list_agents()

    def test_set_default_agent(self):
        """Test setting a different default agent."""
        registry = AgentRegistry()

        registry.set_default_agent("opencode")
        assert registry.get_default_agent() == "opencode"

    def test_global_registry(self):
        """Test global registry singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2


class TestClaudeCodeAgent:
    """Test ClaudeCodeAgent functionality."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = ClaudeCodeAgent()

        assert agent.name == "claude-code"
        assert agent.requires_cli is True

    def test_agent_with_config(self):
        """Test agent initialization with config."""
        config = {"cli_path": "/usr/local/bin/claude"}
        agent = ClaudeCodeAgent(config)

        assert agent.cli_path == "/usr/local/bin/claude"

    @pytest.mark.asyncio
    async def test_validate_environment_no_cli(self):
        """Test environment validation when CLI is not available."""
        agent = ClaudeCodeAgent({"cli_path": "/nonexistent/path"})

        is_valid, error = await agent.validate_environment()

        assert is_valid is False
        assert error is not None
        assert "not found" in error


class TestOpenCodeAgent:
    """Test OpenCode agent implementation."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = OpenCodeAgent()

        assert agent.name == "opencode"
        assert agent.requires_cli is True

    def test_agent_with_config(self):
        """Test agent initialization with config."""
        config = {"cli_path": "/usr/local/bin/opencode"}
        agent = OpenCodeAgent(config)

        assert agent.cli_path == "/usr/local/bin/opencode"

    @pytest.mark.asyncio
    async def test_validate_environment_no_cli(self):
        """Test environment validation when CLI is not available."""
        agent = OpenCodeAgent({"cli_path": "/nonexistent/opencode"})

        is_valid, error = await agent.validate_environment()

        assert is_valid is False
        assert error is not None
        assert "not found" in error

    @pytest.mark.asyncio
    async def test_opencode_agent_plan_returns_result(self, tmp_path):
        """Test that OpenCode agent plan returns a result (may fail if opencode not installed)."""
        agent = OpenCodeAgent()
        result = await agent.plan("Test issue", str(tmp_path))

        # OpenCode agent is implemented - should not return placeholder error
        assert "not yet implemented" not in (result.error or "")
        # Result is either success (plan generated) or failure (opencode not installed, etc.)
        assert result.success or result.error is not None

    @pytest.mark.asyncio
    async def test_opencode_agent_implement_yields_events(self, tmp_path):
        """Test that OpenCode agent implement yields events (not placeholder)."""
        agent = OpenCodeAgent()
        events = []

        async for event in agent.implement("Test issue", "Test plan", str(tmp_path), 1, "branch"):
            events.append(event)

        assert len(events) > 0
        # OpenCode agent is implemented - should not return placeholder error
        assert not any("not yet implemented" in (e.content or "") for e in events)


class TestPlaceholderAgents:
    """Test placeholder agent implementations."""

    @pytest.mark.asyncio
    async def test_gemini_agent_plan_fails(self):
        """Test that Gemini agent plan returns error."""
        agent = GeminiAgent()
        result = await agent.plan("Test issue", "/tmp/repo")

        assert result.success is False
        assert "not yet implemented" in result.error

    @pytest.mark.asyncio
    async def test_gemini_agent_validate_environment(self):
        """Test Gemini agent environment validation."""
        agent = GeminiAgent()
        is_valid, error = await agent.validate_environment()

        assert is_valid is False
        assert "API key" in error

    @pytest.mark.asyncio
    async def test_codex_agent_plan_fails(self):
        """Test that Codex agent plan returns error."""
        agent = CodexAgent()
        result = await agent.plan("Test issue", "/tmp/repo")

        assert result.success is False
        assert "not yet implemented" in result.error

    @pytest.mark.asyncio
    async def test_codex_agent_validate_environment(self):
        """Test Codex agent environment validation."""
        agent = CodexAgent()
        is_valid, error = await agent.validate_environment()

        assert is_valid is False
        assert "API key" in error
