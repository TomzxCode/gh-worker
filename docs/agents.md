# Agents

gh-worker uses a pluggable agent system that allows different LLM providers to handle planning and implementation tasks.

## Overview

Agents are LLM-powered assistants that:

- **Plan**: Analyze issues and generate implementation plans
- **Implement**: Execute plans by writing code, running tests, and creating pull requests
- **Monitor**: Provide real-time feedback during execution

## Architecture

The agent system is built on a flexible plugin architecture:

```
BaseAgent (Abstract)
├── ClaudeCodeAgent ✅
├── CursorAgent ✅
├── MockAgent ✅
├── OpenCodeAgent 🚧
├── GeminiAgent 🚧
└── CodexAgent 🚧
```

All agents implement the same interface, making them interchangeable.

## Available Agents

### Claude Code (Default)

Uses the [Claude Code CLI](https://claude.ai/code) tool from Anthropic.

**Status**: ✅ Fully implemented

**Features**:

- Advanced code understanding
- Multi-file editing
- Automatic test execution
- Git integration
- Real-time streaming output

**Prerequisites**:

- Claude Code CLI installed
- Claude Code authentication

**Configuration**:

```bash
ghw config agent.default claude-code

# Optional: specify custom path
ghw config agent.claude_code_path /path/to/claude-code
```

**Example Usage**:

```bash
# Use explicitly
ghw issues plan --repo owner/repo --agent claude-code

# Or set as default
ghw config agent.default claude-code
ghw issues plan --repo owner/repo
```

### Cursor Agent

Uses the [Cursor Agent CLI](https://github.com/cursor-ai/cursor-agent) tool.

**Status**: ✅ Fully implemented

**Features**:

- Fast code generation
- Supports both `cursor-agent` and `agent` CLI names
- Plan and implementation generation
- Commit message generation
- Auto-detects CLI availability

**Prerequisites**:

- Cursor Agent CLI installed (`npm install -g @cursor/agent`)
- API key configured (if required)

**Configuration**:

```bash
ghw config agent.default cursor-agent

# Optional: specify custom path
ghw config agent.cursor_agent_path /path/to/cursor-agent

# Optional: specify model
ghw config agent.cursor.model gpt-4
```

**Example Usage**:

```bash
# Use explicitly
ghw issues plan --repo owner/repo --agent cursor-agent

# Or set as default
ghw config agent.default cursor-agent
ghw issues plan --repo owner/repo

# With implementation
ghw issues implement --repo owner/repo --agent cursor-agent
```

### Mock Agent

A test agent for development and testing without external dependencies.

**Status**: ✅ Fully implemented

**Features**:

- No external CLI required
- Configurable success/failure modes
- Simulated delays for testing
- Useful for development and CI/CD

**Configuration**:

```bash
# Set as default (not recommended for production)
ghw config agent.default mock

# Configure behavior
ghw config agent.mock.fail_plan false
ghw config agent.mock.fail_implement false
ghw config agent.mock.plan_delay 0
ghw config agent.mock.implement_delay 0
```

**Example Usage**:

```bash
# Use for testing
ghw issues plan --repo owner/repo --agent mock

# Test implementation workflow
ghw issues implement --repo owner/repo --agent mock
```

### OpenCode

OpenCode agent for open-source LLM integration.

**Status**: 🚧 Placeholder (not yet implemented)

**Planned Features**:

- Open-source LLM support
- Self-hosted deployment
- Customizable prompts

### Gemini

Google's Gemini agent.

**Status**: 🚧 Placeholder (not yet implemented)

**Planned Features**:

- Google Gemini API integration
- Large context window
- Multimodal capabilities

### Codex

OpenAI's Codex agent.

**Status**: 🚧 Placeholder (not yet implemented)

**Planned Features**:

- OpenAI Codex API integration
- GPT-4 code generation
- ChatGPT integration

## Agent Interface

All agents implement the `BaseAgent` interface:

### Methods

#### `plan(issue_content, repository_path)`

Generate an implementation plan for an issue.

**Parameters**:

- `issue_content` (str): Full issue description
- `repository_path` (str): Path to cloned repository

**Returns**: `AgentResult` with generated plan

**Example**:

```python
from gh_worker.agents.registry import get_registry

registry = get_registry()
agent = registry.get("claude-code")

result = await agent.plan(
    issue_content="Fix login bug",
    repository_path="/path/to/repo"
)

print(result.output)  # The plan
```

#### `implement(issue_content, plan_content, repository_path, issue_number, branch_name)`

Implement a plan and create changes.

**Parameters**:

- `issue_content` (str): Full issue description
- `plan_content` (str): Generated plan
- `repository_path` (str): Path to cloned repository
- `issue_number` (int): Issue number
- `branch_name` (str): Branch to create

**Yields**: `AgentEvent` objects during execution

**Example**:

```python
async for event in agent.implement(
    issue_content="Fix login bug",
    plan_content="1. Update auth.py...",
    repository_path="/path/to/repo",
    issue_number=42,
    branch_name="issue-42-fix-login"
):
    print(f"{event.type}: {event.content}")
```

#### `commit(repository_path, issue_number, branch_name)`

Commit changes with a descriptive message.

**Parameters**:

- `repository_path` (str): Path to cloned repository
- `issue_number` (int): Issue number
- `branch_name` (str): Branch name

**Yields**: `AgentEvent` objects during commit

**Example**:

```python
async for event in agent.commit(
    repository_path="/path/to/repo",
    issue_number=42,
    branch_name="issue-42-fix-login"
):
    print(f"{event.type}: {event.content}")
```

#### `monitor(session_id)`

Monitor an ongoing agent session.

**Parameters**:

- `session_id` (str): Session ID to monitor

**Yields**: `AgentEvent` objects from the session

**Example**:

```python
async for event in agent.monitor(session_id="abc123"):
    print(f"{event.type}: {event.content}")
```

#### `validate_environment()`

Validate that the agent's environment is properly configured.

**Returns**: `(is_valid, error_message)`

**Example**:

```python
is_valid, error = await agent.validate_environment()
if not is_valid:
    print(f"Agent not ready: {error}")
```

## Agent Registry

The agent registry manages available agents and provides a central access point.

### Get Registry

```python
from gh_worker.agents.registry import get_registry

registry = get_registry()
```

### Register an Agent

```python
from gh_worker.agents.base import BaseAgent
from gh_worker.agents.registry import get_registry

class CustomAgent(BaseAgent):
    # Implementation...
    pass

registry = get_registry()
registry.register("custom", CustomAgent, default=False)
```

### Get an Agent

```python
# Get default agent
agent = registry.get()

# Get specific agent
agent = registry.get("claude-code")

# Get with configuration
agent = registry.get("claude-code", config={"timeout": 300})
```

### List Agents

```python
agents = registry.list_agents()
print(agents)  # ['claude-code', 'opencode', 'gemini', 'codex']
```

### Check Registration

```python
if registry.is_registered("claude-code"):
    print("Claude Code is available")
```

## Agent Events

During implementation, agents emit events that describe what's happening.

### Event Types

```python
from gh_worker.agents.base import AgentEventType

AgentEventType.OUTPUT      # Regular output
AgentEventType.ERROR       # Error message
AgentEventType.STATUS      # Status update
AgentEventType.TOOL_USE    # Tool being used
AgentEventType.COMPLETION  # Task completed
AgentEventType.FAILURE     # Task failed
AgentEventType.RESULT      # Final result/output to extract
```

### Event Structure

```python
from gh_worker.agents.base import AgentEvent

event = AgentEvent(
    type=AgentEventType.STATUS,
    content="Analyzing codebase...",
    metadata={"progress": 0.25}
)
```

### Handling Events

```python
async for event in agent.implement(...):
    match event.type:
        case AgentEventType.OUTPUT:
            print(event.content)
        case AgentEventType.ERROR:
            print(f"Error: {event.content}", file=sys.stderr)
        case AgentEventType.STATUS:
            print(f"Status: {event.content}")
        case AgentEventType.COMPLETION:
            print("Success!")
        case AgentEventType.FAILURE:
            print(f"Failed: {event.content}")
```

## Agent Results

The `AgentResult` class represents the outcome of an agent operation.

### Structure

```python
from gh_worker.agents.base import AgentResult

result = AgentResult(
    success=True,
    output="Implementation plan...",
    session_id="abc123",
    branch_name="issue-42-fix-login",
    pr_url="https://github.com/owner/repo/pull/43",
    error=None,
    metadata={"duration": 120.5}
)
```

### Fields

- `success` (bool): Whether the operation succeeded
- `output` (str): The primary output (plan, implementation log, etc.)
- `session_id` (str | None): Session ID for monitoring
- `branch_name` (str | None): Created branch name
- `pr_url` (str | None): Pull request URL
- `error` (str | None): Error message if failed
- `metadata` (dict | None): Additional metadata

## Creating Custom Agents

You can create custom agents by subclassing `BaseAgent`:

```python
from gh_worker.agents.base import BaseAgent, AgentResult, AgentEvent, AgentEventType
from collections.abc import AsyncIterator

class MyCustomAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "my-custom-agent"

    @property
    def requires_cli(self) -> bool:
        return False  # Or True if you need an external CLI

    async def plan(
        self,
        issue_content: str,
        repository_path: str
    ) -> AgentResult:
        # Generate plan using your LLM
        plan = await self._generate_plan(issue_content)

        return AgentResult(
            success=True,
            output=plan,
            session_id=None,
            error=None
        )

    async def implement(
        self,
        issue_content: str,
        plan_content: str,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        # Implement the plan
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content="Starting implementation..."
        )

        # ... do work ...

        yield AgentEvent(
            type=AgentEventType.COMPLETION,
            content="Implementation complete"
        )

    async def commit(
        self,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        # Commit changes
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content="Committing changes..."
        )

    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        # Monitor session
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content="Monitoring..."
        )

    async def validate_environment(self) -> tuple[bool, str | None]:
        # Validate your agent's dependencies
        try:
            # Check API keys, dependencies, etc.
            return True, None
        except Exception as e:
            return False, str(e)
```

### Register Your Custom Agent

```python
from gh_worker.agents.registry import get_registry

registry = get_registry()
registry.register("my-custom-agent", MyCustomAgent)

# Use it
ghw config agent.default my-custom-agent
```

## Agent Configuration

Agents can receive configuration through the registry:

```python
# Pass configuration when getting agent
agent = registry.get("claude-code", config={
    "timeout": 300,
    "max_retries": 3,
    "custom_prompt": "..."
})
```

The configuration dictionary is passed to the agent's `__init__` method and stored in `self.config`.

## Best Practices

### Agent Selection

- **Claude Code**: Best for comprehensive implementations, complex refactoring, test execution
- **Cursor Agent**: Best for fast code generation, quick fixes, simple implementations
- **Mock Agent**: Best for testing, CI/CD, development without external dependencies
- **OpenCode**: Best for open-source projects, self-hosted deployments (when available)
- **Gemini**: Best for large codebases with big context needs (when available)
- **Codex**: Best for OpenAI ecosystem integration (when available)

### Error Handling

Always handle agent errors gracefully:

```python
result = await agent.plan(...)
if not result.success:
    logger.error("Plan failed", error=result.error)
    # Handle error
```

### Resource Management

Agents may use significant resources:

- Limit parallelism for implementation
- Monitor system resources
- Set appropriate timeouts

### Validation

Validate agent environment before use:

```python
is_valid, error = await agent.validate_environment()
if not is_valid:
    raise RuntimeError(f"Agent not ready: {error}")
```

## Troubleshooting

### Agent Not Found

```bash
# List available agents
ghw agents list  # (if command exists)

# Or check configuration
ghw config agent.default
```

### Agent Validation Fails

For Claude Code:

```bash
# Check CLI is installed
claude-code --version

# Authenticate
claude-code auth
```

For Cursor Agent:

```bash
# Check CLI is installed
cursor-agent --version
# or
agent --version

# Install if needed
npm install -g @cursor/agent
```

### Slow Performance

- Reduce parallelism
- Use faster agents for simple tasks
- Check network connectivity

## Future Development

Planned improvements:

- Additional agent implementations (OpenCode, Gemini, Codex)
- Agent-specific configuration options
- Agent performance metrics
- Custom prompt templates
- Multi-agent workflows

## Next Steps

- [Architecture](architecture.md) - Understand the technical architecture
- [Usage Guide](usage.md) - Learn command usage
- [Configuration](configuration.md) - Configure agents
