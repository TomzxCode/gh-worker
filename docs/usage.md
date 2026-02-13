# Usage Guide

This guide covers all gh-worker commands and common workflows. New to ghw? Start with the [Walkthrough Guide](walkthrough.md) for a step-by-step tutorial.

## Global Options

All commands support the following global options:

- `--log-level` - Set logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO
- `--config-path` - Path to config file (default: `~/.config/gh-worker/config.yaml`)

**Examples**:

```bash
# Enable debug logging
ghw --log-level DEBUG issues sync --repo owner/repo

# Use custom config file
ghw issues sync --repo owner/repo --config-path /path/to/config.yaml
```

## Commands Overview

gh-worker provides the following commands (in help order):

- [`init`](#init-command) - Initialize configuration interactively
- [`repositories`](#repositories-commands) - Manage tracked repositories (add, list, remove)
- [`issues`](#issues-commands) - Sync, plan, review, implement, and list issues (sync, list, plan, review, implement)
- [`monitor`](#monitor-command) - Monitor ongoing implementations
- [`work`](#work-command) - Run complete workflow (sync → plan → implement)
- [`config`](#config-command) - Manage configuration

## Command Reference

### Init Command

Initialize gh-worker configuration interactively.

```bash
ghw init
```

This command guides you through setting up gh-worker by:

1. Prompting for required configuration (issues-path, repository-path)
1. Validating paths and creating directories
1. Setting sensible defaults for parallelism and agents
1. Saving configuration to `~/.config/gh-worker/config.yaml`

**Examples**:

```bash
# Initialize with default config location
ghw init

# Initialize with custom config location
ghw init --config-path /path/to/config.yaml
```

**What Gets Configured**:

- `issues-path` - Where to store synced issues
- `repository-path` - Where to clone repositories
- `plan.parallelism` - How many plans to generate concurrently (default: 1)
- `implement.parallelism` - How many implementations to run concurrently (default: 1)
- `implement.use_worktree` - Use git worktree for implementations (default: True)
- `implement.push_branch` - Auto-push branches after implementation (default: False)
- `implement.create_pr` - Auto-create PRs after implementation (default: False)
- `agent.default` - Default LLM agent to use (default: "claude-code")

### Config Command

Manage gh-worker configuration.

```bash
# List all configuration values
ghw config --list

# Get a value (provide only the key)
ghw config <key>

# Set a value (provide key and value)
ghw config <key> <value>
```

**List All Configuration Values**:

```bash
# Output all keys and values in key=value format
ghw config --list
```

**Get Configuration Value**:

```bash
# Get issues path
ghw config issues-path

# Get nested value using dot notation
ghw config plan.parallelism
```

**Set Configuration Value**:

```bash
# Set issues path
ghw config issues-path ~/gh-worker/issues

# Set nested value
ghw config plan.parallelism 3

# Set boolean values
ghw config implement.use_worktree true
```

**Notes**:
- The command automatically detects whether you're getting or setting based on the number of arguments
- Use dot notation for nested configuration keys (e.g., `plan.parallelism`)
- Boolean values should be specified as `true` or `false` (lowercase)

### Repositories Commands

Manage tracked repositories with `ghw repositories`:

```bash
ghw repositories add <repo> [<repo2> ...]
ghw repositories list
ghw repositories remove <repo> [<repo2> ...]
```

#### add

Add repositories to track.

1. Creates the necessary directory structure
1. Initializes issue storage in `issues-path`
1. Optionally clones to `repository-path` with `--clone` (otherwise cloned on-demand when running `ghw issues plan` or `ghw issues implement`)

**Examples**:

```bash
# Add a single repository (no clone by default)
ghw repositories add owner/repo

# Add and clone immediately
ghw repositories add owner/repo --clone

# Add multiple repositories
ghw repositories add owner/repo1 owner/repo2 owner/repo3
```

#### list

List all repositories under management (repositories with a directory under `issues-path`).

**Examples**:

```bash
# List all tracked repositories
ghw repositories list

# Use custom config
ghw repositories list --config-path /path/to/config.yaml
```

#### remove

Remove repositories from tracking.

1. Removes the repository directory from `issues-path` (including all synced issues and plans)
2. By default, keeps the cloned repository in `repository-path` (use `--no-keep-clone` to also remove it)

**Examples**:

```bash
# Remove a single repository (keeps clone by default)
ghw repositories remove owner/repo

# Remove multiple repositories
ghw repositories remove owner/repo1 owner/repo2

# Also remove the cloned repository
ghw repositories remove owner/repo --no-keep-clone
```

### Issues Commands

Sync, plan, and implement issues with `ghw issues`:

```bash
ghw issues sync [--repo REPO | --all-repos] [OPTIONS]
ghw issues list [--repo REPO | --all-repos] [OPTIONS]
ghw issues plan [--repo REPO] [OPTIONS]
ghw issues review plan [--repo REPO] <issue-number> [OPTIONS]
ghw issues review implementation [--repo REPO] <issue-number> [OPTIONS]
ghw issues implement [--repo REPO] [OPTIONS]
```

#### sync

Sync GitHub issues to local files for processing.

#### Sync a Specific Repository

```bash
ghw issues sync --repo <owner/repo>
```

**Examples**:

```bash
# Sync all issues (open and closed)
ghw issues sync --repo owner/repo

# Sync issues updated in last 7 days
ghw issues sync --repo owner/repo --since 7d

# Sync issues updated in last 2 hours
ghw issues sync --repo owner/repo --since 2h

# Sync specific issues
ghw issues sync --repo owner/repo --issue-numbers 42 43 44

# Filter by assignee (use @me for current user)
ghw issues sync --repo owner/repo --assignee @me

# Force refresh all issues (re-fetch and update description.md)
ghw issues sync --repo owner/repo --force
```

#### Sync All Repositories

```bash
ghw issues sync --all-repos
```

This syncs all repositories you've added with the `add` command.

#### Sync with Search Query

```bash
ghw issues sync --repo owner/repo --search "label:bug is:open"
```

Uses GitHub's search syntax to filter issues.

#### Time-Based Sync

The `--since` flag accepts duration strings:

```bash
# Last hour
ghw issues sync --repo owner/repo --since 1h

# Last 30 minutes
ghw issues sync --repo owner/repo --since 30m

# Last 7 days
ghw issues sync --repo owner/repo --since 7d

# Last 2 weeks
ghw issues sync --repo owner/repo --since 14d
```

#### list

List synced issues with plan and implementation status in a table.

```bash
# List issues for a repository
ghw issues list --repo owner/repo

# List issues from all repositories
ghw issues list --all-repos

# Filter by title (substring match)
ghw issues list --repo owner/repo --title "bug"

# Filter by author (use @me for current user)
ghw issues list --repo owner/repo --author @me

# Filter by assignee (use @me for current user)
ghw issues list --repo owner/repo --assignee @me

# Filter by plan status: none, being generated, waiting for local review, approved
ghw issues list --repo owner/repo --plan approved

# Filter by implementation status: none, being generated, waiting for local review, PR opened, merged, failed
ghw issues list --repo owner/repo --implementation none
```

#### plan

Generate implementation plans for synced issues using LLM agents.

#### Generate Plans for a Repository

```bash
ghw issues plan --repo <owner/repo>
```

This generates plans for all issues in the repository that don't already have plans.

#### Generate Plans for All Repositories

```bash
ghw issues plan --all-repos
```

This generates plans for all repositories you've added with the `add` command.

**Examples**:

```bash
# Generate plans with default parallelism
ghw issues plan --repo owner/repo

# Generate plans with custom parallelism
ghw issues plan --repo owner/repo --parallelism 5
```

#### Generate Plan for Specific Issues

```bash
ghw issues plan --repo owner/repo --issue-numbers 42 43
```

**Use Cases**:

- Regenerate a plan after issue updates
- Generate plans for specific high-priority issues
- Test plan generation on a single issue

#### Parallelism

Control how many issues are planned concurrently:

```bash
# Plan 5 issues in parallel
ghw issues plan --repo owner/repo --parallelism 5
```

The parallelism value overrides the configured default for this execution.

#### Force Regeneration

Force plan generation even if a plan already exists:

```bash
# Regenerate plan for an issue
ghw issues plan --repo owner/repo --issue-numbers 42 --force
```

#### Agent Override

Use a different agent for planning:

```bash
# Use Cursor agent instead of default
ghw issues plan --repo owner/repo --agent cursor-agent

# Use mock agent for testing
ghw issues plan --repo owner/repo --agent mock

# Filter by assignee (use @me for current user)
ghw issues plan --repo owner/repo --assignee @me
```

#### review plan

Review and approve implementation plans before running the implement step.

```bash
# Review a plan (creates worktree with plan symlinked)
ghw issues review plan --repo owner/repo 42

# Approve a plan
ghw issues review plan --repo owner/repo 42 --approve
```

#### review implementation

Approve implementations that completed without auto-push/PR: push the branch and create a pull request.

```bash
# Push branch and create PR (default)
ghw issues review implementation --repo owner/repo 42

# Push branch only (no PR)
ghw issues review implementation --repo owner/repo 42 --no-pr

# Create PR only (branch already pushed)
ghw issues review implementation --repo owner/repo 42 --no-push
```

#### implement

Execute implementation plans and create pull requests using git worktree for isolated development.

#### Implement Planned Issues for a Repository

```bash
ghw issues implement --repo <owner/repo>
```

This implements all issues in the repository that have plans but haven't been implemented yet.

#### Implement Plans for All Repositories

```bash
ghw issues implement --all-repos
```

This implements planned issues for all repositories you've added with the `add` command.

**Examples**:

```bash
# Implement with default parallelism
ghw issues implement --repo owner/repo

# Implement with custom parallelism
ghw issues implement --repo owner/repo --parallelism 2

# Use different agent
ghw issues implement --repo owner/repo --agent cursor-agent
```

#### Implement Specific Issues

```bash
ghw issues implement --repo owner/repo --issue-numbers 42
```

**Use Cases**:

- Implement a specific high-priority issue
- Re-implement after manual changes
- Test implementation on a single issue

#### Git Worktree Support

By default, gh-worker uses git worktree to create isolated workspaces for each implementation:

```bash
# Use worktree (default behavior)
ghw issues implement --repo owner/repo --use-worktree

# Disable worktree (work directly in main repo)
ghw issues implement --repo owner/repo --use-worktree=false
```

**Benefits of Worktree**:

- Parallel implementations don't conflict
- Main repository stays clean
- Easy to switch between implementations
- Automatic cleanup after completion

#### PR Automation

Control whether branches are pushed and PRs are created automatically:

```bash
# Push branch but don't create PR
ghw issues implement --repo owner/repo --push-branch

# Push branch and create PR automatically
ghw issues implement --repo owner/repo --push-branch --create-pr

# Keep worktree after implementation (for debugging)
ghw issues implement --repo owner/repo --delete-worktree=false
```

**Examples**:

```bash
# Full automation: worktree, push, and create PR
ghw issues implement --repo owner/repo --use-worktree --push-branch --create-pr

# Manual PR creation: implement and push only
ghw issues implement --repo owner/repo --push-branch
```

#### What Happens During Implementation

1. Agent validation checks if required CLI tools are available
1. Creates a git worktree for isolated development (if enabled)
1. Agent reads the issue and plan
1. Creates a new branch (e.g., `issue-42-fix-login-bug`)
1. Makes code changes according to the plan
1. Agent generates and creates a commit with descriptive message
1. Pushes the branch to GitHub (if `--push-branch` enabled)
1. Creates a pull request with implementation details (if `--create-pr` enabled)
1. Deletes the worktree (if `--delete-worktree` enabled, default)

#### Force Re-implementation

Force implementation even if the issue was already completed:

```bash
# Re-implement an issue
ghw issues implement --repo owner/repo --issue-numbers 42 --force
```

#### Agent Override

Override the default agent for specific implementations:

```bash
# Use Claude Code agent
ghw issues implement --repo owner/repo --agent claude-code

# Use Cursor agent
ghw issues implement --repo owner/repo --agent cursor-agent

# Use mock agent (for testing)
ghw issues implement --repo owner/repo --agent mock

# Filter by assignee (use @me for current user)
ghw issues implement --repo owner/repo --assignee @me
```

### Monitor Command

Monitor an ongoing LLM agent session (plan or implementation) in real-time.

```bash
ghw monitor --repo <owner/repo> --issue-number <number>
```

**Examples**:

```bash
# Monitor issue #42
ghw monitor --repo owner/repo --issue-number 42
```

**What You'll See**:

- Agent status updates
- Tool usage (file reads, edits, command execution)
- Progress indicators
- Error messages
- Completion status

**Use Cases**:

- Watch long-running plan generation or implementations
- Debug implementation issues
- Understand what the agent is doing

**Note**: Monitor requires a session ID in the plan metadata. It works for implementations; support for monitoring plan generation depends on the agent.

### Work Command

Run the complete workflow: sync → plan → implement.

#### Run Once

Process all pending issues once and exit:

```bash
ghw work --once --repos owner/repo
```

**Examples**:

```bash
# Process one repository
ghw work --once --repos owner/repo

# Process multiple repositories
ghw work --once --repos owner/repo1 owner/repo2

# Process recent issues only
ghw work --once --repos owner/repo --since 1d

# Process specific issues
ghw work --once --repos owner/repo --issue-numbers 42 43
```

#### Continuous Mode

Run continuously, processing issues at regular intervals:

```bash
ghw work --repos owner/repo
```

**Examples**:

```bash
# Use default frequency (from config)
ghw work --repos owner/repo

# Use custom frequency
ghw work --repos owner/repo --frequency 30m

# Process multiple repositories
ghw work --repos owner/repo1 owner/repo2 --frequency 15m
```

In continuous mode, gh-worker will:

1. Sync issues
1. Generate plans for new issues
1. Implement planned issues
1. Wait for the specified frequency
1. Repeat

**Stop Continuous Mode**: Press Ctrl+C to gracefully stop.

## Common Workflows

### Quick Start Workflow

Set up and process a repository:

```bash
# 1. Initialize configuration (interactive)
ghw init

# OR configure manually
ghw config issues-path ~/gh-worker/issues
ghw config repository-path ~/gh-worker/repos

# 2. Add repository
ghw repositories add owner/repo

# 3. Sync issues
ghw issues sync --repo owner/repo

# 4. Generate plans
ghw issues plan --repo owner/repo

# 5. (Optional) Review and approve plans
ghw issues review plan --repo owner/repo 42 --approve

# 6. Implement with full automation
ghw issues implement --repo owner/repo --push-branch --create-pr
```

### Daily Issue Processing

Process new issues from the last day:

```bash
# Sync, plan, and implement recent issues
ghw work --once --repos owner/repo --since 1d
```

**Schedule with Cron**:

```bash
# Add to crontab (run daily at 9 AM)
0 9 * * * /path/to/ghw work --once --repos owner/repo --since 1d
```

### Continuous Monitoring

Monitor and process issues continuously:

```bash
# Check every 30 minutes
ghw work --repos owner/repo --frequency 30m
```

**Run as a Service** (systemd example):

```ini
# /etc/systemd/system/gh-worker.service
[Unit]
Description=gh-worker continuous mode
After=network.target

[Service]
Type=simple
User=youruser
ExecStart=/path/to/ghw work --repos owner/repo --frequency 30m
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Batch Processing

Process a batch of specific issues:

```bash
# Sync specific issues
ghw issues sync --repo owner/repo --issue-numbers 42 43 44 45 46

# Generate plans in parallel
ghw issues plan --repo owner/repo --issue-numbers 42 43 44 45 46 --parallelism 3

# Implement sequentially (safer for complex changes)
ghw issues implement --repo owner/repo --issue-numbers 42 43 44 45 46 --parallelism 1
```

### Review-Before-Implement Workflow

Generate plans, review and approve them, then implement:

```bash
# 1. Sync issues
ghw issues sync --repo owner/repo

# 2. Generate plans
ghw issues plan --repo owner/repo

# 3. Review and approve plans
ghw issues review plan --repo owner/repo 42 --approve
ghw issues review plan --repo owner/repo 43 --approve

# 4. Implement approved issues
ghw issues implement --repo owner/repo --issue-numbers 42 43
```

### Bug Triage Workflow

Process issues with specific labels:

```bash
# Sync bugs only
ghw issues sync --repo owner/repo --search "label:bug is:open"

# Generate plans
ghw issues plan --repo owner/repo

# Review and implement selectively
ghw issues implement --repo owner/repo --issue-numbers 42
```

### High-Parallelism Processing

Process many issues quickly:

```bash
# Sync all issues
ghw issues sync --repo owner/repo

# Generate plans with high parallelism
ghw issues plan --repo owner/repo --parallelism 5

# Implement with moderate parallelism
ghw issues implement --repo owner/repo --parallelism 2
```

## Best Practices

### Start Small

When starting with a new repository:

1. Sync a few issues: `ghw issues sync --repo owner/repo --issue-numbers 1 2 3`
1. Generate one plan: `ghw issues plan --repo owner/repo --issue-numbers 1`
1. Review the plan manually
1. Implement if satisfied: `ghw issues implement --repo owner/repo --issue-numbers 1`

### Use Appropriate Parallelism

- **Planning**: Can be parallelized more aggressively (3-5)
- **Implementation**: Keep lower to avoid conflicts (1-2)

### Review Plans Before Implementation

Use the review command to approve plans before implementing:

```bash
# Review and approve a plan
ghw issues review plan --repo owner/repo 42 --approve
```

Or inspect plans manually:

```bash
# View a plan
cat ~/gh-worker/issues/owner/repo/42/plan-*.md
```

### Monitor Long-Running Implementations

For complex issues, monitor progress:

```bash
# In one terminal: implement
ghw issues implement --repo owner/repo --issue-numbers 42

# In another terminal: monitor
ghw monitor --repo owner/repo --issue-number 42
```

### Use Time-Based Sync

Instead of syncing all issues, sync recent ones:

```bash
# Last week's issues
ghw issues sync --repo owner/repo --since 7d
```

### Organize by Repository

Keep separate issue and repository paths for different projects:

```bash
# Project 1
ghw config issues-path ~/gh-worker/project1/issues
ghw config repository-path ~/gh-worker/project1/repos

# Project 2
ghw config issues-path ~/gh-worker/project2/issues
ghw config repository-path ~/gh-worker/project2/repos
```

## Troubleshooting

### No Issues Synced

Check that you have access to the repository:

```bash
gh repo view owner/repo
```

### Plans Not Generated

Verify the agent is working:

```bash
# For Claude Code
claude-code --version

# For Cursor agent
cursor-agent --version

# Check agent configuration
ghw config agent.default

# Try using a different agent
ghw issues plan --repo owner/repo --agent cursor-agent
```

### Implementation Fails

Check the agent output:

```bash
# Monitor the implementation
ghw monitor --repo owner/repo --issue-number 42
```

Review logs in the issue directory:

```bash
ls -la ~/gh-worker/issues/owner/repo/42/
```

### Rate Limiting

If you hit GitHub API rate limits:

1. Reduce parallelism
1. Increase sync frequency
1. Use `--since` to sync fewer issues

## Next Steps

- [Configuration](configuration.md) - Configure gh-worker
- [Agents](agents.md) - Understand the agent system
- [Architecture](architecture.md) - Technical deep dive
- [Troubleshooting](troubleshooting.md) - Solve common issues
