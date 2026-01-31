# Agent Framework

## Overview

The agent framework provides a pluggable abstraction layer for integrating various LLM agents (Claude Code, OpenCode, Gemini, Codex) into the gh-worker system. It defines a standard interface for agent operations and manages agent lifecycle, registration, and instantiation.

## Architecture

### Core Components

#### BaseAgent (Abstract Class)

The foundation for all agent implementations, located in [src/gh_worker/agents/base.py](src/gh_worker/agents/base.py).

**Key Methods:**

- `plan()` - Generate implementation plans for GitHub issues
- `implement()` - Execute plans and create pull requests (streaming)
- `monitor()` - Track ongoing agent sessions
- `commit()` - Commit changes with a descriptive message (streaming)
- `validate_environment()` - Verify agent prerequisites and return (is_valid, error_message)

**Properties:**

- `name` - Unique identifier for the agent
- `requires_cli` - Boolean indicating if external CLI tool is needed

#### AgentRegistry

Centralized registry for managing agent implementations, located in [src/gh_worker/agents/registry.py](src/gh_worker/agents/registry.py).

**Capabilities:**

- Register/unregister agent classes
- Set and retrieve default agent
- Instantiate agents with configuration
- List available agents
- Check agent registration status

#### Event System

Agents communicate progress through structured events:

**AgentEventType:**

- `OUTPUT` - Regular output from agent
- `ERROR` - Error messages
- `STATUS` - Status updates
- `TOOL_USE` - Tool usage notifications
- `COMPLETION` - Successful task completion
- `FAILURE` - Task failure
- `RESULT` - Final result/output to extract

**Data Structures:**

- `AgentEvent` - Single event with type, content, and optional metadata
- `AgentResult` - Final result with success status, output, session_id, branch_name, pr_url, error, and metadata

### Built-in Agents

#### ClaudeCodeAgent

Concrete implementation using the claude-code CLI tool, located in [src/gh_worker/agents/claude_code.py](src/gh_worker/agents/claude_code.py).

**Features:**

- CLI subprocess management with streaming I/O
- Plan generation with file output (PLAN.md)
- Implementation with branch creation and PR workflow
- Commit generation with descriptive messages
- Session ID extraction from output
- Environment validation (CLI availability check)

**Configuration:**

- `cli_path` - Path to claude-code executable (defaults to "claude-code")

#### CursorAgent

Concrete implementation using the cursor-agent CLI tool, located in [src/gh_worker/agents/cursor_agent.py](src/gh_worker/agents/cursor_agent.py).

**Features:**

- CLI subprocess management with streaming I/O
- Supports both `cursor-agent` and `agent` CLI names
- Plan generation with structured output
- Implementation with file modification tracking
- Commit generation capabilities
- Environment validation with helpful installation messages

**Configuration:**

- `cli_path` or `cursor_agent_path` - Path to cursor-agent executable (defaults to auto-detection)
- `model` - Model to use for generation (optional)
- `api_key` - API key for authentication (optional)

#### MockAgent

Test agent implementation for testing without external dependencies, located in [src/gh_worker/agents/mock.py](src/gh_worker/agents/mock.py).

**Features:**

- Configurable success/failure modes
- Simulated streaming output
- No external CLI dependencies
- Useful for unit testing and development

**Configuration:**

- `fail_plan` - Boolean to simulate plan failure (default: False)
- `fail_implement` - Boolean to simulate implementation failure (default: False)
- `plan_delay` - Delay in seconds for plan generation (default: 0)
- `implement_delay` - Delay in seconds for implementation (default: 0)

#### Stub Agents

Placeholder implementations for future integration:

- **CodexAgent** - OpenAI Codex integration
- **GeminiAgent** - Google Gemini integration
- **OpenCodeAgent** - OpenCode integration

### Global Registry

A singleton registry instance is accessible via `get_registry()`, providing application-wide agent management. The registry can be reset for testing purposes using `reset_registry()`.

## Data Flow

### Planning Phase

1. Agent receives issue content, repository path, and issue number
1. Constructs planning prompt with requirements and structure
1. Invokes LLM (via CLI or API)
1. Returns `AgentResult` with generated plan and optional session ID

### Implementation Phase

1. Agent receives issue content, plan, repository path, issue number, and branch name
1. Constructs implementation prompt with step-by-step instructions
1. Streams execution via `AsyncIterator[AgentEvent]`
1. Yields events for output, tool usage, errors, and status
1. Completes with `COMPLETION` or `FAILURE` event

### Commit Phase

1. Agent receives repository path, issue number, and branch name
1. Generates descriptive commit message based on changes
1. Streams commit process via `AsyncIterator[AgentEvent]`
1. Yields events for commit status and results
1. Completes with `COMPLETION` or `FAILURE` event

### Monitoring Phase

1. Agent receives session ID for ongoing work
1. Connects to session (implementation-dependent)
1. Streams events from the session
1. Returns status updates and progress

## Error Handling

- Configuration errors raise `ValueError` or `TypeError`
- Missing agents raise `KeyError` with available agent list
- Environment validation returns tuple of (is_valid, error_message)
- Runtime errors yield `AgentEvent` with type `ERROR` or `FAILURE`
- CLI failures raise `RuntimeError` with stderr output

## Requirements

### Agent Implementations

**MUST:**

- Implement all abstract methods from `BaseAgent`
- Return `AgentResult` from `plan()`
- Yield `AgentEvent` objects from `implement()`, `monitor()`, and `commit()`
- Provide unique `name` property
- Specify `requires_cli` property accurately
- Handle exceptions and convert to appropriate event types
- Accept configuration dictionary in `__init__`
- Implement `validate_environment()` returning (bool, str | None) tuple

**SHOULD:**

- Implement `validate_environment()` for runtime checks
- Include session IDs in results when available
- Provide structured metadata in events and results
- Stream output for long-running operations
- Log operations using structlog
- Use async/await for all I/O operations

**MAY:**

- Support custom configuration parameters
- Extract additional metadata from output (branch names, PR URLs)
- Implement session monitoring if supported by underlying tool
- Provide progress estimates or completion percentages
- Cache or reuse sessions across operations

### Agent Registry

**MUST:**

- Prevent duplicate agent registrations (raise `ValueError`)
- Validate agent classes are subclasses of `BaseAgent`
- Maintain at least one default agent if any agents are registered
- Raise `KeyError` for unregistered agents with helpful error message
- Thread-safe for concurrent access to global registry

**SHOULD:**

- Log all registration, unregistration, and instantiation operations
- Automatically set first registered agent as default
- Preserve default agent when possible during unregistration
- Provide clear error messages with available agent lists

**MAY:**

- Support agent aliases or alternative names
- Validate agent configuration schemas
- Provide agent capability discovery (e.g., supports monitoring)
- Cache agent instances for reuse

### Event System

**MUST:**

- Include event type for all events
- Provide non-empty content for meaningful events
- Use appropriate event types (OUTPUT, ERROR, STATUS, TOOL_USE, COMPLETION, FAILURE)
- Emit COMPLETION or FAILURE event at end of implementation

**SHOULD:**

- Include metadata for contextual information
- Use consistent field names in metadata
- Preserve issue numbers and identifiers in metadata
- Timestamp events if needed for debugging

**MAY:**

- Include progress indicators in metadata
- Provide structured error details in ERROR events
- Support event filtering or subscription patterns
- Include tool names and parameters in TOOL_USE events

## Usage Examples

### Registering a Custom Agent

```python
from gh_worker.agents.registry import get_registry
from gh_worker.agents.base import BaseAgent

class MyAgent(BaseAgent):
    # Implementation...
    pass

registry = get_registry()
registry.register("my-agent", MyAgent, default=True)
```

### Using an Agent

```python
from gh_worker.agents.registry import get_registry

registry = get_registry()
agent = registry.get("claude-code", config={"cli_path": "/usr/local/bin/claude-code"})

# Validate environment
is_valid, error = await agent.validate_environment()
if not is_valid:
    print(f"Environment error: {error}")
    return

# Generate plan
result = await agent.plan(issue_content, repo_path, issue_num)
if result.success:
    print(f"Plan: {result.output}")

# Implement (streaming)
async for event in agent.implement(issue_content, plan, repo_path, issue_num, branch):
    if event.type == AgentEventType.OUTPUT:
        print(event.content)
    elif event.type == AgentEventType.ERROR:
        print(f"Error: {event.content}")
```

## Extension Points

New agents can be integrated by:

1. Subclassing `BaseAgent`
1. Implementing all abstract methods
1. Registering with the global registry
1. Optionally providing configuration schema

The framework supports both CLI-based agents (like ClaudeCodeAgent) and API-based agents, streaming and non-streaming modes, and synchronous or asynchronous execution patterns.
