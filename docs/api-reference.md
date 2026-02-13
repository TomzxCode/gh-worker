# API Reference

This document provides a reference for gh-worker's Python API, useful when integrating gh-worker into other tools or building custom extensions.

## CLI Module

### `gh_worker.cli`

Main CLI application entry point.

#### `app`

The cyclopts application instance.

```python
from gh_worker.cli import app

# Run the CLI programmatically
app(["sync", "--repo", "owner/repo"])
```

## Commands

### `gh_worker.commands.sync`

#### `sync_command(repo, all_repos, since, issue_numbers, search, assignee, force, config_path)`

Sync GitHub issues to local storage.

**Parameters**:

- `repo` (str | None): Repository to sync (format: "owner/repo")
- `all_repos` (bool): Sync all configured repositories
- `since` (str | None): Only sync issues updated since (e.g., "7d", "2h")
- `issue_numbers` (list[int] | None): Specific issue numbers to sync
- `search` (str | None): GitHub search query
- `assignee` (str | None): Filter by assignee (substring match, use @me for current user)
- `force` (bool): Refresh all issues (re-fetch and update description.md)
- `config_path` (Path | None): Custom config file path

**Example**:

```python
from gh_worker.commands.sync import sync_command

sync_command(
    repo="owner/repo",
    all_repos=False,
    since="7d",
    issue_numbers=None,
    search=None,
    config_path=None
)
```

### `gh_worker.commands.issues_list`

#### `issues_list_command(repo, all_repos, title, author, assignee, plan, implementation, config_path)`

List synced issues with plan and implementation status.

**Parameters**:

- `repo` (str | None): Repository to list (format: "owner/repo")
- `all_repos` (bool): List issues from all repositories
- `title` (str | None): Filter by title (substring match)
- `author` (str | None): Filter by author (substring match, use @me for current user)
- `assignee` (str | None): Filter by assignee (substring match, use @me for current user)
- `plan` (str | None): Filter by plan status: none, being generated, waiting for local review, approved
- `implementation` (str | None): Filter by implementation status: none, being generated, waiting for local review, PR opened, merged, failed
- `config_path` (Path | None): Custom config file path

**Example**:

```python
from gh_worker.commands.issues_list import issues_list_command

issues_list_command(
    repo="owner/repo",
    all_repos=False,
    title=None,
    author=None,
    assignee=None,
    plan=None,
    implementation=None,
    config_path=None
)
```

### `gh_worker.commands.plan`

#### `plan_command(repo, issue_numbers, all_repos, parallelism, force, assignee, config_path, agent)`

Generate implementation plans for issues.

**Parameters**:

- `repo` (str | None): Repository (format: "owner/repo")
- `issue_numbers` (list[int] | None): Specific issues to plan
- `all_repos` (bool): Generate plans for all repositories
- `parallelism` (int | None): Number of parallel executions
- `force` (bool): Generate plan even if one already exists
- `assignee` (str | None): Filter by assignee (substring match, use @me for current user)
- `config_path` (Path | None): Custom config file path
- `agent` (str | None): Override agent to use

**Example**:

```python
from gh_worker.commands.plan import plan_command

plan_command(
    repo="owner/repo",
    issue_numbers=[42, 43],
    parallelism=3,
    config_path=None
)
```

### `gh_worker.commands.implement`

#### `implement_command(repo, issue_numbers, all_repos, parallelism, force, assignee, use_worktree, push_branch, create_pr, delete_worktree, config_path, agent)`

Implement plans and create pull requests.

**Parameters**:

- `repo` (str | None): Repository (format: "owner/repo")
- `issue_numbers` (list[int] | None): Specific issues to implement
- `all_repos` (bool): Implement plans for all repositories
- `parallelism` (int | None): Number of parallel executions
- `force` (bool): Implement even if already completed
- `assignee` (str | None): Filter by assignee (substring match, use @me for current user)
- `use_worktree` (bool | None): Use git worktree (overrides config)
- `push_branch` (bool | None): Push branch after implementation (overrides config)
- `create_pr` (bool | None): Create PR after implementation (overrides config)
- `delete_worktree` (bool | None): Delete worktree after implementation (overrides config)
- `config_path` (Path | None): Custom config file path
- `agent` (str | None): Override agent to use

**Example**:

```python
from gh_worker.commands.implement import implement_command

implement_command(
    repo="owner/repo",
    issue_numbers=[42],
    parallelism=1,
    config_path=None
)
```

### `gh_worker.commands.monitor`

#### `monitor_command(repo, issue_number, config_path, agent)`

Monitor an ongoing agent session.

**Parameters**:

- `repo` (str): Repository (format: "owner/repo")
- `issue_number` (int): Issue number to monitor
- `config_path` (Path | None): Custom config file path
- `agent` (str | None): Override agent to use

**Example**:

```python
from gh_worker.commands.monitor import monitor_command

monitor_command(
    repo="owner/repo",
    issue_number=42,
    config_path=None
)
```

### `gh_worker.commands.work`

#### `work_command(once, frequency, repos, since, issue_numbers, config_path, agent)`

Run complete workflow (sync → plan → implement).

**Parameters**:

- `once` (bool): Run once and exit
- `frequency` (str | None): Sync frequency (e.g., "10m", "1h")
- `repos` (list[str] | None): Repositories to process
- `since` (str | None): Only process issues updated since
- `issue_numbers` (list[int] | None): Specific issues to process
- `config_path` (Path | None): Custom config file path
- `agent` (str | None): Override agent to use

**Example**:

```python
from gh_worker.commands.work import work_command

work_command(
    once=True,
    frequency=None,
    repos=["owner/repo"],
    since="1d",
    issue_numbers=None,
    config_path=None,
    agent=None
)
```

## Agents

### `gh_worker.agents.base`

Base classes and interfaces for agents.

#### `BaseAgent`

Abstract base class for all agents.

**Methods**:

##### `plan(issue_content, repository_path, issue_number) -> AgentResult`

Generate an implementation plan.

**Parameters**:

- `issue_content` (str): Full issue description
- `repository_path` (str): Path to cloned repository
- `issue_number` (int): Issue number

**Returns**: `AgentResult`

##### `implement(issue_content, plan_content, repository_path, issue_number, branch_name) -> AsyncIterator[AgentEvent]`

Implement the plan.

**Parameters**:

- `issue_content` (str): Full issue description
- `plan_content` (str): Generated plan
- `repository_path` (str): Path to cloned repository
- `issue_number` (int): Issue number
- `branch_name` (str): Branch to create

**Yields**: `AgentEvent`

##### `monitor(session_id) -> AsyncIterator[AgentEvent]`

Monitor an ongoing session.

**Parameters**:

- `session_id` (str): Session ID to monitor

**Yields**: `AgentEvent`

##### `validate_environment() -> tuple[bool, str | None]`

Validate agent environment.

**Returns**: `(is_valid, error_message)`

**Properties**:

- `name` (str): Agent name
- `requires_cli` (bool): Whether agent requires external CLI

#### `AgentResult`

Result of an agent operation.

**Attributes**:

- `success` (bool): Whether operation succeeded
- `output` (str): Primary output
- `session_id` (str | None): Session ID
- `branch_name` (str | None): Created branch name
- `pr_url` (str | None): Pull request URL
- `error` (str | None): Error message if failed
- `metadata` (dict[str, Any] | None): Additional metadata

#### `AgentEvent`

Event emitted during agent execution.

**Attributes**:

- `type` (AgentEventType): Event type
- `content` (str): Event content
- `metadata` (dict[str, Any] | None): Additional metadata

#### `AgentEventType`

Enum of event types.

**Values**:

- `OUTPUT`: Regular output
- `ERROR`: Error message
- `STATUS`: Status update
- `TOOL_USE`: Tool usage
- `COMPLETION`: Task completed
- `FAILURE`: Task failed

**Example**:

```python
from gh_worker.agents.base import BaseAgent, AgentResult, AgentEvent, AgentEventType

class CustomAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "custom"

    @property
    def requires_cli(self) -> bool:
        return False

    async def plan(self, issue_content, repository_path, issue_number):
        # Generate plan
        return AgentResult(
            success=True,
            output="Implementation plan...",
            error=None
        )

    async def implement(self, issue_content, plan_content, repository_path, issue_number, branch_name):
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content="Starting..."
        )
        # Do work
        yield AgentEvent(
            type=AgentEventType.COMPLETION,
            content="Done"
        )

    async def monitor(self, session_id):
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content="Monitoring..."
        )
```

### `gh_worker.agents.registry`

Agent registry for managing agent implementations.

#### `get_registry() -> AgentRegistry`

Get the global agent registry instance.

**Returns**: `AgentRegistry`

**Example**:

```python
from gh_worker.agents.registry import get_registry

registry = get_registry()
agent = registry.get("claude-code")
```

#### `AgentRegistry`

Registry for managing agents.

**Methods**:

##### `register(name, agent_class, default=False)`

Register an agent implementation.

**Parameters**:

- `name` (str): Agent name
- `agent_class` (type[BaseAgent]): Agent class
- `default` (bool): Set as default agent

##### `get(name=None, config=None) -> BaseAgent`

Get an agent instance.

**Parameters**:

- `name` (str | None): Agent name (uses default if None)
- `config` (dict[str, Any] | None): Configuration for agent

**Returns**: `BaseAgent` instance

##### `list_agents() -> list[str]`

List all registered agent names.

**Returns**: List of agent names

##### `is_registered(name) -> bool`

Check if agent is registered.

**Parameters**:

- `name` (str): Agent name

**Returns**: `bool`

##### `get_default_agent() -> str | None`

Get default agent name.

**Returns**: Default agent name or None

##### `set_default_agent(name)`

Set the default agent.

**Parameters**:

- `name` (str): Agent name

**Example**:

```python
from gh_worker.agents.registry import get_registry
from gh_worker.agents.base import BaseAgent

class MyAgent(BaseAgent):
    # Implementation...
    pass

registry = get_registry()
registry.register("my-agent", MyAgent)

agent = registry.get("my-agent", config={"timeout": 300})
result = await agent.plan("Issue content", "/path/to/repo", 42)
```

## Storage

### `gh_worker.storage.issue_store`

#### `IssueStore`

Manages issue file storage.

**Methods**:

##### `save_issue(repo, issue_number, content)`

Save issue to disk.

**Parameters**:

- `repo` (str): Repository name
- `issue_number` (int): Issue number
- `content` (str): Issue content

##### `load_issue(repo, issue_number) -> str`

Load issue from disk.

**Parameters**:

- `repo` (str): Repository name
- `issue_number` (int): Issue number

**Returns**: Issue content

##### `list_issues(repo) -> list[int]`

List all issue numbers for a repository.

**Parameters**:

- `repo` (str): Repository name

**Returns**: List of issue numbers

### `gh_worker.storage.plan_store`

#### `PlanStore`

Manages plan file storage.

**Methods**:

##### `save_plan(repo, issue_number, content, metadata)`

Save plan to disk.

**Parameters**:

- `repo` (str): Repository name
- `issue_number` (int): Issue number
- `content` (str): Plan content
- `metadata` (dict): Plan metadata

##### `load_plan(repo, issue_number) -> tuple[str, dict]`

Load latest plan from disk.

**Parameters**:

- `repo` (str): Repository name
- `issue_number` (int): Issue number

**Returns**: `(content, metadata)` tuple

##### `list_plans(repo, issue_number) -> list[Path]`

List all plans for an issue.

**Parameters**:

- `repo` (str): Repository name
- `issue_number` (int): Issue number

**Returns**: List of plan file paths

## Configuration

### `gh_worker.config.schema`

Pydantic models for configuration.

#### `AppConfig`

Main application configuration.

**Attributes**:

- `issues_path` (Path | None): Issues storage path
- `repository_path` (Path | None): Repository clone path
- `plan` (PlanConfig): Plan configuration
- `implement` (ImplementConfig): Implement configuration
- `sync` (SyncConfig): Sync configuration
- `agent` (AgentConfig): Agent configuration

#### `PlanConfig`

Plan command configuration.

**Attributes**:

- `parallelism` (int): Parallel execution count (>= 1)

#### `ImplementConfig`

Implement command configuration.

**Attributes**:

- `parallelism` (int): Parallel execution count (>= 1)

#### `SyncConfig`

Sync command configuration.

**Attributes**:

- `frequency` (str): Default sync frequency (e.g., "10m", "1h")

#### `AgentConfig`

Agent configuration.

**Attributes**:

- `default` (str): Default agent name
- `claude_code_path` (str | None): Custom claude-code path

**Example**:

```python
from gh_worker.config.schema import AppConfig, PlanConfig

config = AppConfig(
    issues_path=Path("~/gh-worker/issues"),
    repository_path=Path("~/gh-worker/repos"),
    plan=PlanConfig(parallelism=3)
)
```

### `gh_worker.config.manager`

Configuration file management.

#### `ConfigManager`

Manages configuration file I/O.

**Methods**:

##### `load() -> AppConfig`

Load configuration from file.

**Returns**: `AppConfig`

##### `save(config)`

Save configuration to file.

**Parameters**:

- `config` (AppConfig): Configuration to save

##### `get(key) -> Any`

Get configuration value by key.

**Parameters**:

- `key` (str): Config key (supports dot notation)

**Returns**: Configuration value

##### `set(key, value)`

Set configuration value.

**Parameters**:

- `key` (str): Config key (supports dot notation)
- `value` (Any): Value to set

## Models

### `gh_worker.models.issue`

#### `Issue`

Issue data model.

**Attributes**:

- `number` (int): Issue number
- `title` (str): Issue title
- `body` (str): Issue body/description
- `state` (str): Issue state (open, closed)
- `labels` (list[str]): Issue labels
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### `gh_worker.models.plan`

#### `Plan`

Plan data model.

**Attributes**:

- `issue_number` (int): Issue number
- `content` (str): Plan content
- `created_at` (datetime): Creation timestamp
- `agent` (str): Agent that created the plan
- `metadata` (dict): Additional metadata

### `gh_worker.models.repository`

#### `Repository`

Repository data model.

**Attributes**:

- `owner` (str): Repository owner
- `name` (str): Repository name
- `path` (Path): Local clone path

## Utilities

### `gh_worker.utils.retry`

#### `retry(max_attempts=3, backoff_factor=2.0, exceptions=(Exception,))`

Decorator for automatic retry with exponential backoff.

**Parameters**:

- `max_attempts` (int): Maximum retry attempts
- `backoff_factor` (float): Backoff multiplier
- `exceptions` (tuple): Exceptions to catch

**Example**:

```python
from gh_worker.utils.retry import retry

@retry(max_attempts=3, backoff_factor=2.0)
async def flaky_operation():
    # May fail transiently
    pass
```

### `gh_worker.utils.time`

#### `parse_duration(duration_str) -> int`

Parse duration string to seconds.

**Parameters**:

- `duration_str` (str): Duration (e.g., "10m", "1h", "7d")

**Returns**: Duration in seconds

**Example**:

```python
from gh_worker.utils.time import parse_duration

seconds = parse_duration("30m")  # 1800
seconds = parse_duration("2h")   # 7200
```

### `gh_worker.utils.logging`

#### `setup_logging(log_level="INFO")`

Configure structured logging.

**Parameters**:

- `log_level` (str): Log level (DEBUG, INFO, WARNING, ERROR)

**Example**:

```python
from gh_worker.utils.logging import setup_logging

setup_logging("DEBUG")
```

## Next Steps

- [Architecture](architecture.md) - Understand the architecture
- [Agents](agents.md) - Learn about the agent system
- [Usage Guide](usage.md) - Command usage examples
