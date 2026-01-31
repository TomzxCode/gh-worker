# Command Implementation

## Overview

Commands implement the business logic for CLI operations. Each command follows a consistent pattern: load configuration, validate settings, execute operations (often in parallel), and report results. Commands are thin wrappers that orchestrate interactions between storage, GitHub client, and agents.

## Architecture

### Command Pattern

All commands located in [src/gh_worker/commands/](src/gh_worker/commands/) follow a standard structure:

**Entry Point:**

- `{command}_command()` - Main function called by CLI
- Accepts command-specific parameters
- Takes optional `config_path` parameter

**Helper Functions:**

- `{operation}_repository()` - Per-repository operation
- `{operation}_issue()` - Per-issue operation

**Common Flow:**

1. Load configuration
1. Validate required settings
1. Initialize clients and stores
1. Resolve repository/issue scope
1. Execute operations (parallel if configured)
1. Report results

### Available Commands

#### init

Initializes configuration interactively.

**Location:** [src/gh_worker/commands/init.py](src/gh_worker/commands/init.py)

**Operations:**

- Interactive configuration setup
- Prompts for required settings (issues-path, repository-path)
- Validates paths and creates directories
- Generates initial config file at `~/.config/gh-worker/config.yaml`
- Sets sensible defaults for parallelism and agent configuration

**Example:**

```bash
gh-worker init
```

**Flow:**

1. Check if config already exists and prompt for overwrite
1. Prompt for issues-path with validation
1. Prompt for repository-path with validation
1. Create directories if they don't exist
1. Set default configuration values
1. Save configuration to YAML file
1. Display success message with config location

#### config

Manages application configuration.

**Location:** [src/gh_worker/commands/config.py](src/gh_worker/commands/config.py)

**Operations:**

- Get configuration value
- Set configuration value
- Uses dotted key paths

**Example:**

```bash
gh-worker config issues-path /var/gh-worker/issues
gh-worker config plan.parallelism 3
```

#### add

Adds repositories to track.

**Location:** [src/gh_worker/commands/add.py](src/gh_worker/commands/add.py)

**Operations:**

- Parse repository names
- Validate repository access
- Initialize storage structure
- Create repository metadata

**Example:**

```bash
gh-worker add octocat/hello-world
```

#### sync

Synchronizes issues from GitHub to local storage.

**Location:** [src/gh_worker/commands/sync.py](src/gh_worker/commands/sync.py)

**Operations:**

- Fetch issues from GitHub (all or specific)
- Convert from GitHub JSON to Issue model
- Save to IssueStore
- Update repository timestamps for incremental sync
- Support filters: since, issue_numbers, search

**Helper Function:**

- `sync_repository()` - Sync single repository

**Flow:**

1. Load configuration and validate issues_path
1. Initialize GHClient and IssueStore
1. Resolve repositories (specific, all, or from storage)
1. For each repository:
   - Get since timestamp (from parameter or last sync)
   - Fetch issues (specific numbers or all matching filters)
   - Save each issue to storage
   - Track latest update timestamp
   - Update repository timestamp
1. Report total issues synced

#### plan

Generates implementation plans using LLM agents.

**Location:** [src/gh_worker/commands/plan.py](src/gh_worker/commands/plan.py)

**Operations:**

- Find issues without plans
- Use agent to generate plans
- Save plans with metadata
- Support parallel execution

**Helper Functions:**

- `plan_issue()` - Generate plan for single issue
- `plan_command()` - Sync wrapper
- `plan_command_async()` - Async implementation

**Flow:**

1. Load configuration and validate paths
1. Initialize agent, GHClient, IssueStore, PlanStore
1. Clone repositories
1. Resolve issues (specific numbers or all without plans)
1. Create ParallelExecutor with configured parallelism
1. For each issue in parallel:
   - Read issue content
   - Call agent.plan()
   - Save plan content and metadata
   - Log results
1. Report success/failure counts

#### implement

Executes plans and creates pull requests with git worktree support.

**Location:** [src/gh_worker/commands/implement.py](src/gh_worker/commands/implement.py)

**Operations:**

- Find issues with completed plans
- Use agent to implement plans
- Create branches using git worktree for isolation (configurable)
- Optionally push branches to remote
- Optionally create pull requests
- Update plan metadata with results
- Support parallel execution with streaming
- Clean up worktrees after completion (configurable)

**CLI Flags:**

- `--use-worktree` - Use git worktree for isolated implementation (overrides config, default: True)
- `--push-branch` - Push branch to remote after implementation (overrides config, default: False)
- `--create-pr` - Create pull request after implementation (overrides config, default: False)
- `--delete-worktree` - Delete worktree after implementation (overrides config, default: True)
- `--agent` - Override agent to use (e.g., "cursor-agent", "mock")

**Helper Functions:**

- `implement_issue()` - Implement single issue with worktree management
- `implement_command()` - Sync wrapper
- `implement_command_async()` - Async implementation

**Flow:**

1. Load configuration and validate paths
1. Initialize agent (with optional override), GHClient, IssueStore, PlanStore
1. Validate agent environment
1. Resolve issues with plans (specific numbers or all pending)
1. Create ParallelExecutor with configured parallelism
1. For each issue in parallel:
   - Load issue and plan
   - Update metadata status to IN_PROGRESS
   - Create git worktree if enabled (isolated workspace)
   - Call agent.implement() (streaming)
   - Stream events to console
   - Optionally commit changes using agent.commit()
   - Optionally push branch to remote
   - Optionally create PR using gh CLI
   - Update metadata with results (branch, PR URL, status)
   - Clean up worktree if enabled
   - Log completion
1. Report success/failure counts

#### monitor

Monitors ongoing agent sessions.

**Location:** [src/gh_worker/commands/monitor.py](src/gh_worker/commands/monitor.py)

**Operations:**

- Retrieve session ID from plan metadata
- Connect to agent session
- Stream session events
- Display progress

**Flow:**

1. Load configuration
1. Initialize agent and PlanStore
1. Load plan metadata for issue
1. Extract session ID
1. Call agent.monitor() (streaming)
1. Display events to console

#### work

Orchestrates complete sync → plan → implement workflow.

**Location:** [src/gh_worker/commands/work.py](src/gh_worker/commands/work.py)

**Operations:**

- Create WorkOrchestrator
- Run single cycle or continuous mode
- Handle errors and continue

**Flow:**

1. Create WorkOrchestrator with parameters
1. If once mode: await orchestrator.run_once()
1. If continuous: await orchestrator.run_continuous(frequency)
1. Orchestrator handles sync → plan → implement phases

## Common Patterns

### Configuration Loading

```python
config = ConfigManager(config_path)
app_config = config.load()

if not app_config.issues_path:
    print("Error: issues-path not configured.")
    return
```

### Repository Resolution

```python
if repo:
    repositories = [Repository.from_string(repo)]
elif all_repos:
    repositories = issue_store.list_repositories()
else:
    print("Error: Specify --repo or --all-repos")
    return
```

### Parallel Execution

```python
executor = ParallelExecutor(
    max_workers=parallelism or app_config.plan.parallelism
)

results = await executor.execute(
    items=issues,
    task_func=plan_issue,
    task_name="plan_issues"
)
```

### Error Handling

```python
try:
    result = gh_client.get_issue(repository, issue_number)
except Exception as e:
    logger.error("operation_failed", error=str(e))
    print(f"Error: {e}")
```

### Result Reporting

```python
success_count = sum(1 for r in results if r.success)
failure_count = len(results) - success_count

print(f"Completed: {success_count} succeeded, {failure_count} failed")
```

## Requirements

### Command Structure

**MUST:**

- Accept optional config_path parameter
- Load and validate configuration
- Initialize required clients and stores
- Handle missing configuration gracefully
- Report results to stdout
- Log operations with structured logging
- Return or exit with appropriate status

**SHOULD:**

- Validate input parameters
- Provide helpful error messages
- Support both specific and bulk operations
- Use parallel execution for multiple items
- Track and report success/failure counts
- Log start and completion

**MAY:**

- Support dry-run mode
- Provide progress indicators
- Support resume/retry for failed items
- Cache or reuse resources

### Configuration Integration

**MUST:**

- Load configuration via ConfigManager
- Validate required settings (paths, etc.)
- Use configuration defaults
- Allow parameter overrides
- Handle missing configuration file

**SHOULD:**

- Print helpful messages for missing config
- Show configuration commands in errors
- Log configuration values used
- Support custom config paths

**MAY:**

- Validate configuration before execution
- Support environment variable overrides
- Provide configuration recommendations

### Repository and Issue Scope

**MUST:**

- Support specific repository via parameter
- Support all repositories via flag
- Support specific issue numbers
- Resolve repositories from storage
- Validate repository format

**SHOULD:**

- Handle repository not found gracefully
- Skip missing issues with warning
- Support empty repository lists
- Log repository and issue counts

**MAY:**

- Support repository patterns
- Implement issue filters (labels, state)
- Provide issue discovery
- Support repository aliases

### Parallel Execution

**MUST:**

- Use ParallelExecutor for multi-item operations
- Support configurable parallelism
- Default to configuration value
- Allow parameter override
- Handle per-item errors without stopping

**SHOULD:**

- Log parallelism settings
- Report per-item results
- Aggregate success/failure counts
- Stream output for long operations

**MAY:**

- Support adaptive parallelism
- Implement rate limiting
- Provide progress tracking
- Support cancellation

### Error Handling

**MUST:**

- Catch and log exceptions
- Continue processing other items on error
- Report errors to user
- Use appropriate log levels
- Preserve error context

**SHOULD:**

- Classify errors by severity
- Provide actionable error messages
- Include troubleshooting hints
- Log full tracebacks for debugging

**MAY:**

- Implement retry logic
- Support error recovery
- Aggregate error reports
- Provide error statistics

### Output and Logging

**MUST:**

- Print summary results
- Log all operations with structured fields
- Write errors to stderr
- Write results to stdout
- Use consistent formatting

**SHOULD:**

- Provide progress updates for long operations
- Show item counts (total, processed, failed)
- Use clear, concise messages
- Include timestamps in logs

**MAY:**

- Support JSON output format
- Provide verbose mode
- Support colored output
- Stream real-time progress

## Usage Examples

### Sync Command

```python
def sync_command(repo, all_repos, since, issue_numbers, search, config_path):
    # Load configuration
    config = ConfigManager(config_path)
    app_config = config.load()

    # Validate
    if not app_config.issues_path:
        print("Error: issues-path not configured")
        return

    # Initialize
    gh_client = GHClient()
    issue_store = IssueStore(app_config.issues_path)

    # Resolve repositories
    if repo:
        repositories = [Repository.from_string(repo)]
    elif all_repos:
        repositories = issue_store.list_repositories()
    else:
        print("Error: Specify --repo or --all-repos")
        return

    # Sync each repository
    total = 0
    for repository in repositories:
        count = sync_repository(
            repository, issue_store, gh_client,
            since, issue_numbers, search
        )
        total += count

    print(f"Synced {total} issues across {len(repositories)} repositories")
```

### Plan Command (Async)

```python
async def plan_command_async(repo, issue_numbers, parallelism, config_path):
    # Load configuration and initialize
    config = ConfigManager(config_path)
    app_config = config.load()

    agent = get_agent(app_config)
    plan_store = PlanStore(app_config.issues_path)

    # Clone repository
    gh_client = GHClient(app_config.repository_path)
    repository = Repository.from_string(repo)
    repo_path = gh_client.clone_repo(repository)

    # Find issues without plans
    issues = [
        num for num in issue_numbers
        if not plan_store.has_plan(repository, num)
    ]

    # Plan in parallel
    executor = ParallelExecutor(
        max_workers=parallelism or app_config.plan.parallelism
    )

    async def plan_issue(issue_num):
        # Generate and save plan
        result = await agent.plan(issue_content, repo_path, issue_num)
        plan_store.create_plan(repository, issue_num, result.output)
        return result

    results = await executor.execute(issues, plan_issue, "plan")

    # Report
    success = sum(1 for r in results if r.success)
    print(f"Generated {success}/{len(results)} plans")
```

## Extension Points

Commands can be extended to support:

- Additional GitHub operations (releases, workflows)
- Custom workflow phases
- Webhooks and event triggers
- Batch operations with checkpointing
- Dry-run and preview modes
- Interactive prompts
- Progress bars and status displays
- Export and reporting formats
- Integration with external tools
- Custom agents or backends
