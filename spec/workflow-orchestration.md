# Workflow Orchestration

## Overview

The workflow orchestrator manages the complete automation cycle: syncing issues from GitHub, generating implementation plans using LLM agents, and executing those plans to create pull requests. It supports both single-shot and continuous execution modes with configurable frequency.

## Architecture

### WorkOrchestrator Class

Central coordinator for the sync → plan → implement workflow, located in [src/gh_worker/executor/orchestrator.py](src/gh_worker/executor/orchestrator.py).

**Initialization Parameters:**

- `config_path` - Path to configuration file (optional)
- `repos` - List of repository names to process (optional, defaults to all)
- `since` - Timestamp filter for issues (optional)
- `issue_numbers` - Specific issues to process (optional)

**Methods:**

- `run_cycle()` - Execute one complete workflow cycle
- `run_once()` - Run single cycle and exit
- `run_continuous()` - Run cycles repeatedly at specified frequency

## Workflow Phases

### Phase 1: Sync

Fetches issues from GitHub and stores them locally.

**Operations:**

1. Load application configuration
1. Validate `issues_path` is configured
1. Call `sync_command()` for each repository (or all repositories)
1. Pass through filters: `since`, `issue_numbers`
1. Update repository metadata with last sync timestamp

**Behavior:**

- If `repos` specified, sync each repository individually
- If `repos` not specified, sync all registered repositories
- Continues to next phase even if some repositories fail
- Logs phase transition and prints status messages

### Phase 2: Plan

Generates implementation plans using configured LLM agent.

**Operations:**

1. Call `plan_command_async()` for each repository (or all)
1. Use `parallelism` from configuration (if not overridden)
1. Generate plans for issues without existing plans
1. Save plans to storage with metadata
1. Extract session IDs for monitoring

**Behavior:**

- Respects `issue_numbers` filter if provided
- Uses configured agent (default: claude-code)
- Parallelizes plan generation based on config
- Continues to implement phase even if some plans fail
- Logs plan generation results

### Phase 3: Implement

Executes plans and creates pull requests.

**Operations:**

1. Call `implement_command_async()` for each repository (or all)
1. Use `parallelism` from configuration (if not overridden)
1. Stream agent output during implementation
1. Create branches and pull requests
1. Update plan metadata with results (status, PR URL, branch name)

**Behavior:**

- Only implements issues with completed plans
- Respects `issue_numbers` filter if provided
- Parallelizes implementations based on config
- Streams progress to console
- Logs implementation results and PR URLs

## Execution Modes

### Single-Shot Mode

Executes one complete cycle and exits.

**Usage:** `await orchestrator.run_once()`

**Behavior:**

1. Run one sync → plan → implement cycle
1. Log completion
1. Return control to caller

**Use Cases:**

- Manual invocation
- CI/CD integration
- Scheduled cron jobs
- One-time processing

### Continuous Mode

Runs cycles repeatedly at specified intervals.

**Usage:** `await orchestrator.run_continuous("1h")`

**Behavior:**

1. Parse frequency string using `parse_duration()`
1. Enter infinite loop
1. For each iteration:
   - Log cycle number and timestamp
   - Execute `run_cycle()`
   - Catch and log errors (continue to next cycle)
   - Sleep for specified interval
   - Repeat

**Frequency Formats:**

- Minutes: "10m", "30m"
- Hours: "1h", "2h"
- Days: "1d", "7d"
- Combined: "1h30m", "2d12h"

**Error Handling:**

- Invalid frequency format terminates continuous mode
- Cycle errors logged but don't stop execution
- Each cycle is independent (isolated errors)

## Configuration Integration

### Configuration Loading

Configuration loaded at start of each cycle:

```python
app_config = self.config_manager.load()
```

### Required Settings

- `issues_path` - Must be configured for all operations
- Missing `issues_path` terminates cycle with error message

### Optional Settings

- `plan.parallelism` - Number of concurrent plan generations
- `implement.parallelism` - Number of concurrent implementations
- `agent.default` - Agent to use for planning and implementation

### Configuration Validation

- Checks for required paths
- Provides helpful error messages with configuration commands
- Logs validation failures

## Repository Filtering

### All Repositories

When `repos` is `None` or empty:

- Processes all repositories in storage
- Discovered via `IssueStore.list_repositories()`
- Each repository processed in sequence

### Specific Repositories

When `repos` contains repository names:

- Processes only specified repositories
- Each repository processed in sequence
- Format: "owner/name" (e.g., "octocat/hello-world")

### Issue Filtering

When `issue_numbers` specified:

- Only processes specified issues
- Applies across all phases
- Format: List of integers (e.g., [42, 73, 101])

## Logging and Output

### Structured Logging

All operations logged with structlog fields:

- `phase` - Current workflow phase (sync, plan, implement)
- `cycle` - Cycle number in continuous mode
- `frequency` - Configured frequency string
- `interval_seconds` - Parsed interval duration

### Console Output

Phase transitions printed to stdout:

```
=== Syncing issues ===
=== Generating plans ===
=== Implementing plans ===
=== Work cycle completed ===
```

Continuous mode includes:

- Cycle number and timestamp header
- Frequency and interval information
- Error messages for failed cycles
- Wait messages between cycles

## Error Handling

### Configuration Errors

- Missing `issues_path` terminates cycle with message
- Invalid frequency format terminates continuous mode
- Other config issues propagate to caller

### Phase Errors

- Sync errors logged, plan phase continues
- Plan errors logged, implement phase continues
- Implement errors logged, cycle completes

### Continuous Mode Errors

- Cycle errors caught and logged
- Next cycle starts after interval
- Individual cycle failures don't stop orchestrator
- Keyboard interrupt (Ctrl+C) terminates gracefully

## Requirements

### Orchestrator Lifecycle

**MUST:**

- Execute phases in order: sync → plan → implement
- Load configuration at start of each cycle
- Validate required configuration (issues_path)
- Pass filters (repos, since, issue_numbers) to all phases
- Log phase transitions and cycle status
- Support both single-shot and continuous modes

**SHOULD:**

- Continue to next phase even if some operations fail
- Provide clear console output for phase transitions
- Log cycle numbers in continuous mode
- Catch and isolate cycle errors in continuous mode

**MAY:**

- Support phase skipping or custom workflows
- Provide pause/resume functionality
- Support dynamic configuration updates
- Implement cycle scheduling (cron-like)

### Configuration Integration

**MUST:**

- Load configuration at start of each cycle
- Check for required settings (issues_path)
- Use configuration defaults for parallelism
- Terminate gracefully on configuration errors

**SHOULD:**

- Provide helpful error messages with fix instructions
- Log configuration values used
- Reload configuration on each cycle

**MAY:**

- Watch configuration file for changes
- Support environment variable overrides
- Provide configuration validation before cycle start

### Continuous Mode

**MUST:**

- Parse frequency using `parse_duration()`
- Run cycles in infinite loop until interrupted
- Sleep between cycles using asyncio.sleep()
- Catch and log cycle errors without stopping
- Log cycle number and timestamps

**SHOULD:**

- Provide clear frequency format error messages
- Print interval information before starting
- Allow graceful shutdown (handle signals)
- Track cycle statistics (success/failure counts)

**MAY:**

- Support dynamic frequency adjustments
- Implement backoff on repeated failures
- Provide cycle history or audit log
- Support max cycle count limit

### Error Handling

**MUST:**

- Continue to next phase on non-fatal errors
- Log all errors with structured fields
- Provide error messages to console
- Isolate cycle errors in continuous mode

**SHOULD:**

- Classify errors by severity (warning vs. fatal)
- Provide actionable error messages
- Include context in error logs (repo, issue number)

**MAY:**

- Implement retry logic for transient failures
- Send notifications on critical errors
- Maintain error statistics
- Support error recovery strategies

### Repository and Issue Filtering

**MUST:**

- Process all repositories when `repos` is None
- Process only specified repositories when `repos` provided
- Apply `issue_numbers` filter across all phases
- Pass `since` filter to sync phase

**SHOULD:**

- Validate repository names before processing
- Log repository and issue counts
- Handle missing repositories gracefully

**MAY:**

- Support repository patterns or wildcards
- Implement issue number ranges
- Provide repository prioritization
- Support label-based filtering

## Usage Examples

### Single-Shot Execution

```python
from gh_worker.executor.orchestrator import WorkOrchestrator

orchestrator = WorkOrchestrator(
    repos=["octocat/hello-world"],
    since="2024-01-01T00:00:00Z"
)

await orchestrator.run_once()
```

### Continuous Execution

```python
orchestrator = WorkOrchestrator(
    repos=["octocat/hello-world", "octocat/spoon-knife"]
)

# Run every 30 minutes
await orchestrator.run_continuous("30m")
```

### Process All Repositories

```python
orchestrator = WorkOrchestrator()  # No repos specified

await orchestrator.run_once()
```

### Process Specific Issues

```python
orchestrator = WorkOrchestrator(
    repos=["octocat/hello-world"],
    issue_numbers=[42, 73, 101]
)

await orchestrator.run_once()
```

### Custom Configuration

```python
from pathlib import Path

orchestrator = WorkOrchestrator(
    config_path=Path("/etc/gh-worker/config.yaml"),
    repos=["octocat/hello-world"]
)

await orchestrator.run_once()
```

## Extension Points

The orchestrator can be extended to support:

- Custom workflow phases or order
- Phase-specific error handlers
- Cycle hooks (pre/post cycle callbacks)
- Dynamic repository discovery
- Parallel repository processing
- Workflow pause/resume
- Dry-run mode for testing
- Webhook triggers for immediate processing
- Multi-agent orchestration (different agents per phase)
