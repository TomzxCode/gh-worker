# CLI Interface

## Overview

The command-line interface provides a comprehensive set of commands for managing GitHub issue automation. Built using cyclopts, it supports configuration management, repository tracking, issue synchronization, plan generation, implementation, session monitoring, and complete workflow orchestration.

## Architecture

### Application Structure

CLI implemented using cyclopts framework in [src/gh_worker/cli.py](src/gh_worker/cli.py).

**Application:**

- Name: `gh-worker`
- Description: "Automated GitHub issue handling with LLM agents"
- Framework: cyclopts

**Global Options:**

- `--log-level` - Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO

### Command Hierarchy

```
gh-worker
├── config       - Configuration management
├── add          - Add repositories
├── sync         - Sync issues from GitHub
├── plan         - Generate implementation plans
├── implement    - Implement plans and create PRs
├── monitor      - Monitor agent sessions
└── work         - Run complete workflow
```

## Commands

### config

Manage application configuration.

**Syntax:**

```bash
gh-worker config <key> [value] [--config-path PATH]
```

**Arguments:**

- `key` (required) - Configuration key (e.g., "issues-path", "plan.parallelism")
- `value` (optional) - Value to set (omit to get current value)

**Options:**

- `--config-path PATH` - Custom config file path (default: ~/.config/gh-worker/config.yaml)

**Examples:**

```bash
# Get value
gh-worker config issues-path

# Set value
gh-worker config issues-path /var/gh-worker/issues
gh-worker config plan.parallelism 3
gh-worker config agent.default claude-code
```

**Behavior:**

- Get mode: Display current value
- Set mode: Update value and save configuration
- Supports dotted key paths for nested values

### add

Add repositories to track.

**Syntax:**

```bash
gh-worker add <repo>... [--config-path PATH]
```

**Arguments:**

- `repos` (required) - One or more repository names (format: "owner/repo")

**Options:**

- `--config-path PATH` - Custom config file path

**Examples:**

```bash
gh-worker add octocat/hello-world
gh-worker add octocat/hello-world octocat/spoon-knife
```

**Behavior:**

- Initializes repository in storage
- Creates directory structure
- Validates repository access via GitHub CLI

### sync

Synchronize GitHub issues to local storage.

**Syntax:**

```bash
gh-worker sync [--repo REPO | --all-repos] [OPTIONS]
```

**Arguments:**

- `--repo REPO` - Specific repository to sync (format: "owner/repo")
- `--all-repos` - Sync all tracked repositories

**Options:**

- `--since TIMESTAMP` - Only sync issues updated after timestamp (ISO 8601)
- `--issue-numbers NUM...` - Specific issue numbers to sync
- `--search QUERY` - GitHub search query
- `--config-path PATH` - Custom config file path

**Examples:**

```bash
# Sync specific repository
gh-worker sync --repo octocat/hello-world

# Sync all repositories
gh-worker sync --all-repos

# Sync with timestamp filter
gh-worker sync --repo octocat/hello-world --since 2024-01-01T00:00:00Z

# Sync specific issues
gh-worker sync --repo octocat/hello-world --issue-numbers 42 73 101

# Search query
gh-worker sync --repo octocat/hello-world --search "is:open label:bug"
```

**Behavior:**

- Fetches issues from GitHub via CLI
- Saves to local storage as markdown
- Updates repository and issue timestamps
- Supports incremental sync with `--since`

### plan

Generate implementation plans for issues.

**Syntax:**

```bash
gh-worker plan [--repo REPO] [OPTIONS]
```

**Arguments:**

- `--repo REPO` - Specific repository (format: "owner/repo")

**Options:**

- `--issue-numbers NUM...` - Specific issue numbers to plan
- `--parallelism N` - Number of parallel plan generations
- `--config-path PATH` - Custom config file path

**Examples:**

```bash
# Plan all issues in repository
gh-worker plan --repo octocat/hello-world

# Plan specific issues
gh-worker plan --repo octocat/hello-world --issue-numbers 42 73

# Parallel planning
gh-worker plan --repo octocat/hello-world --parallelism 3

# Plan all repositories
gh-worker plan
```

**Behavior:**

- Uses configured agent (default: claude-code)
- Generates plans for issues without existing plans
- Saves plans with timestamps and metadata
- Parallelizes based on configuration or `--parallelism`

### implement

Execute plans and create pull requests.

**Syntax:**

```bash
gh-worker implement [--repo REPO] [OPTIONS]
```

**Arguments:**

- `--repo REPO` - Specific repository (format: "owner/repo")

**Options:**

- `--issue-numbers NUM...` - Specific issue numbers to implement
- `--parallelism N` - Number of parallel implementations
- `--config-path PATH` - Custom config file path

**Examples:**

```bash
# Implement all planned issues
gh-worker implement --repo octocat/hello-world

# Implement specific issues
gh-worker implement --repo octocat/hello-world --issue-numbers 42

# Parallel implementation
gh-worker implement --repo octocat/hello-world --parallelism 2

# Implement all repositories
gh-worker implement
```

**Behavior:**

- Only implements issues with completed plans
- Uses configured agent for implementation
- Creates branches and pull requests
- Streams agent output to console
- Updates plan metadata with results (PR URL, branch name, status)

### monitor

Monitor ongoing agent session.

**Syntax:**

```bash
gh-worker monitor --repo REPO --issue-number NUM [--config-path PATH]
```

**Arguments:**

- `--repo REPO` (required) - Repository (format: "owner/repo")
- `--issue-number NUM` (required) - Issue number to monitor

**Options:**

- `--config-path PATH` - Custom config file path

**Examples:**

```bash
gh-worker monitor --repo octocat/hello-world --issue-number 42
```

**Behavior:**

- Retrieves session ID from plan metadata
- Connects to agent session
- Streams session events to console
- Shows progress, tool usage, and output

### work

Run complete sync → plan → implement workflow.

**Syntax:**

```bash
gh-worker work [--once | --frequency FREQ] [OPTIONS]
```

**Arguments:**

- `--once` - Run single cycle and exit (default: continuous)
- `--frequency FREQ` - Sync frequency for continuous mode (e.g., "10m", "1h", "1d")

**Options:**

- `--repos REPO...` - Specific repositories to process
- `--since TIMESTAMP` - Only process issues updated after timestamp
- `--issue-numbers NUM...` - Specific issue numbers to process
- `--config-path PATH` - Custom config file path

**Examples:**

```bash
# Single cycle, all repositories
gh-worker work --once

# Continuous mode, 30 minute intervals
gh-worker work --frequency 30m

# Specific repositories, hourly
gh-worker work --frequency 1h --repos octocat/hello-world octocat/spoon-knife

# Single cycle with filters
gh-worker work --once --repos octocat/hello-world --issue-numbers 42 73
```

**Behavior:**

- Executes sync → plan → implement in sequence
- Continuous mode runs indefinitely at specified frequency
- Single-shot mode runs once and exits
- Continues on errors (logs and proceeds)
- Supports repository and issue filtering

## Global Behavior

### Configuration Loading

All commands load configuration from:

1. Custom path via `--config-path` (if provided)
1. Default: `~/.config/gh-worker/config.yaml`

### Logging

- Configurable log level: DEBUG, INFO (default), WARNING, ERROR
- Uses structlog for structured logging
- Logs to stderr, command output to stdout

### Error Handling

- Invalid arguments cause usage message
- Configuration errors display helpful messages
- GitHub CLI errors propagate with context
- Non-zero exit codes on failure

### Output Format

- Human-readable text output
- Progress messages to stdout
- Errors to stderr
- Structured logs to stderr (if enabled)

## Requirements

### Command Interface

**MUST:**

- Use cyclopts framework for argument parsing
- Support all documented commands and options
- Provide help text for all commands and options
- Accept `--config-path` option on all commands
- Return non-zero exit code on errors

**SHOULD:**

- Validate argument formats before execution
- Provide clear error messages for invalid input
- Show progress for long-running operations
- Use consistent naming conventions (kebab-case for options)

**MAY:**

- Support command aliases or shortcuts
- Provide shell completion
- Support interactive mode
- Add --dry-run option for testing

### Argument Parsing

**MUST:**

- Parse repository names in "owner/repo" format
- Accept multiple repositories where applicable
- Accept multiple issue numbers as list
- Parse ISO 8601 timestamps for `--since`
- Parse frequency strings (e.g., "10m", "1h", "1d")
- Handle both short and long option formats

**SHOULD:**

- Validate repository name format
- Validate timestamp format before execution
- Provide examples in help text
- Support both flag and value options

**MAY:**

- Support repository patterns or wildcards
- Parse relative timestamps ("yesterday", "last week")
- Support issue number ranges

### Configuration Integration

**MUST:**

- Load configuration from file or defaults
- Support dotted key paths in config command
- Save configuration changes immediately
- Validate configuration before use

**SHOULD:**

- Create config directory if missing
- Display current value in get mode
- Show success message after set
- Validate key exists before set

**MAY:**

- Support configuration templates
- Provide config validation command
- Support environment variable overrides
- Show all config values with no arguments

### Error Messages

**MUST:**

- Display clear error messages to stderr
- Include context (command, arguments)
- Suggest fixes for common errors
- Exit with non-zero code on error

**SHOULD:**

- Use consistent error format
- Provide actionable suggestions
- Include relevant documentation links
- Log errors with structured data

**MAY:**

- Support verbose error mode
- Provide error codes
- Format errors with colors
- Support JSON error output

### Output and Logging

**MUST:**

- Write command output to stdout
- Write errors and logs to stderr
- Support configurable log level
- Use structured logging internally

**SHOULD:**

- Show progress for long operations
- Provide summary at completion
- Use clear, consistent formatting
- Suppress debug logs by default

**MAY:**

- Support JSON output format
- Provide quiet mode (minimal output)
- Support colored output
- Stream agent output in real-time

## Usage Patterns

### Initial Setup

```bash
# Configure paths
gh-worker config issues-path /var/gh-worker/issues
gh-worker config repository-path /var/gh-worker/repos

# Add repositories
gh-worker add octocat/hello-world octocat/spoon-knife

# Verify configuration
gh-worker config issues-path
```

### Manual Workflow

```bash
# Sync issues
gh-worker sync --all-repos

# Generate plans
gh-worker plan

# Implement plans
gh-worker implement
```

### Automated Workflow

```bash
# Single run
gh-worker work --once

# Continuous (every hour)
gh-worker work --frequency 1h
```

### Targeted Operations

```bash
# Single repository
gh-worker sync --repo octocat/hello-world
gh-worker plan --repo octocat/hello-world
gh-worker implement --repo octocat/hello-world

# Specific issues
gh-worker plan --repo octocat/hello-world --issue-numbers 42 73
gh-worker implement --repo octocat/hello-world --issue-numbers 42
```

## Extension Points

The CLI can be extended to support:

- Additional commands (list, status, cleanup, etc.)
- Interactive mode with prompts
- Shell completion (bash, zsh, fish)
- Configuration wizards
- Output format options (JSON, YAML, table)
- Plugin system for custom commands
- Remote operation (SSH, cloud)
