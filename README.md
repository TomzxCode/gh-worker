# gh-worker

Automated GitHub issue handling with LLM agents. This CLI tool syncs issues from GitHub, generates implementation plans using LLMs, and executes those plans to create pull requests automatically.

## Features

- **Automated Issue Sync**: Sync GitHub issues to local files for processing
- **LLM-Powered Planning**: Generate comprehensive implementation plans using AI agents
- **Automated Implementation**: Execute plans and create pull requests automatically
- **Git Worktree Support**: Isolated implementation branches using git worktree for parallel development
- **PR Automation**: Automated branch pushing and pull request creation
- **Parallel Execution**: Process multiple issues concurrently with configurable parallelism
- **Continuous Workflow**: Run sync → plan → implement cycles continuously or on-demand
- **Pluggable Agents**: Support for multiple LLM agents (Claude Code, Cursor Agent, Mock, OpenCode, Gemini, Codex)
- **Interactive Setup**: Quick configuration with the `init` command
- **Agent Override**: Switch between agents at runtime for different tasks
- **Robust Error Handling**: Automatic retry logic with exponential backoff for transient failures

## Installation

### Prerequisites

- Python 3.12 or later (latest LTS)
- [uv](https://github.com/astral-sh/uv) package manager
- [GitHub CLI](https://cli.github.com/) (`gh`) authenticated with your GitHub account
- [Claude Code CLI](https://claude.ai/code) (for using the default Claude Code agent)

### Install gh-worker

```bash
# Install with uv
uv tool install https://github.com/tomzxcode/gh-worker.git
```

After installation, the tool is available as both `gh-worker` and `ghw` (shorter alias).

### Verify Installation

```bash
# Check that gh CLI is authenticated
gh auth status

# Verify gh-worker is installed
ghw --help
```

## Quick Start

### Commands

```
ghw init                    Initialize configuration
ghw repositories add        Add repositories to track
ghw repositories list      List tracked repositories
ghw repositories remove    Remove repositories from tracking
ghw issues sync             Sync issues from GitHub
ghw issues list             List synced issues with plan/impl status
ghw issues plan             Generate implementation plans
ghw issues implement        Implement plans and create PRs
ghw monitor                 Monitor ongoing implementations
ghw work                    Run sync → plan → implement workflow
ghw config                  Manage configuration
```

### Global Options

All commands support the following global options:

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR)
ghw --log-level DEBUG <command>

# Use custom config file
ghw <command> --config-path /path/to/config.yaml
```

### 1. Initialize Configuration

Use the interactive setup:

```bash
ghw init
```

This will guide you through setting up:
- Issues storage path
- Repository clone path
- Parallelism settings
- Git worktree options
- PR automation preferences
- Default agent selection

**Or configure manually:**

```bash
# Set the path where issues will be stored
ghw config issues-path ~/gh-worker/issues

# Set the path where repositories will be cloned
ghw config repository-path ~/gh-worker/repos

# (Optional) Configure parallelism for plan generation
ghw config plan.parallelism 3

# (Optional) Configure parallelism for implementation
ghw config implement.parallelism 2

# (Optional) Enable git worktree for isolated implementations
ghw config implement.use_worktree true

# (Optional) Auto-push branches after implementation
ghw config implement.push_branch true

# (Optional) Auto-create PRs after implementation
ghw config implement.create_pr true
```

### 2. Add a Repository

Add a repository to track:

```bash
ghw repositories add owner/repo
```

This creates the necessary directory structure. Use `--clone` to clone immediately, or the repository will be cloned on-demand when you run `ghw issues plan` or `ghw issues implement`.

### 3. List and Manage Repositories

```bash
# List all repositories under management
ghw repositories list

# Remove a repository from tracking (keeps clone by default)
ghw repositories remove owner/repo

# Also remove the cloned repository
ghw repositories remove owner/repo --no-keep-clone
```

### 4. Sync Issues

Sync issues from GitHub:

```bash
# Sync all open issues for a repository
ghw issues sync --repo owner/repo

# Sync specific issues
ghw issues sync --repo owner/repo --issue-numbers 42 43

# Sync issues updated in the last 7 days
ghw issues sync --repo owner/repo --since 7d

# Sync all repositories
ghw issues sync --all-repos
```

### 5. List Issues

List synced issues with plan and implementation status:

```bash
# List issues for a repository
ghw issues list --repo owner/repo

# List issues from all repositories
ghw issues list --all-repos

# Filter by title, author, assignee, plan status, or impl status
ghw issues list --repo owner/repo --plan approved --impl none
```

### 6. Generate Plans

Generate implementation plans for synced issues using LLM agents:

```bash
# Generate plans for all issues without plans
ghw issues plan --repo owner/repo

# Generate plan for specific issue
ghw issues plan --repo owner/repo --issue-numbers 42

# Use custom parallelism
ghw issues plan --repo owner/repo --parallelism 5

# Regenerate plan even if one exists
ghw issues plan --repo owner/repo --issue-numbers 42 --force

# Use different agent
ghw issues plan --repo owner/repo --agent cursor-agent
```

### 7. Implement Plans

Execute plans and create pull requests with git worktree support:

```bash
# Implement all planned issues
ghw issues implement --repo owner/repo

# Implement specific issue
ghw issues implement --repo owner/repo --issue-numbers 42

# Use custom parallelism
ghw issues implement --repo owner/repo --parallelism 2

# Full automation: worktree, push, and create PR
ghw issues implement --repo owner/repo --use-worktree --push-branch --create-pr

# Use different agent
ghw issues implement --repo owner/repo --agent cursor-agent

# Implement and keep worktree for debugging
ghw issues implement --repo owner/repo --delete-worktree=false

# Force re-implementation even if already completed
ghw issues implement --repo owner/repo --issue-numbers 42 --force
```

### 8. Monitor Progress

Monitor an ongoing implementation:

```bash
ghw monitor --repo owner/repo --issue-number 42
```

### 9. Run Full Workflow

Run the complete sync → plan → implement workflow:

```bash
# Run once and exit
ghw work --once --repos owner/repo

# Run continuously (with default frequency)
ghw work --repos owner/repo

# Run with custom frequency
ghw work --repos owner/repo --frequency 30m

# Process specific issues
ghw work --once --repos owner/repo --issue-numbers 42 43
```

## Configuration

Configuration is stored in `~/.config/gh-worker/config.yaml` (XDG compliant).

### Configuration Options

```yaml
issues-path: ~/gh-worker/issues  # Where issues are stored
repository-path: ~/gh-worker/repos  # Where repos are cloned

plan:
  parallelism: 3  # Number of parallel plan generations

implement:
  parallelism: 2  # Number of parallel implementations
  use_worktree: true  # Use git worktree for isolated implementations
  push_branch: false  # Auto-push branches after implementation
  create_pr: false  # Auto-create PRs after implementation
  delete_worktree: true  # Delete worktree after completion

agent:
  default: claude-code  # Default LLM agent (claude-code, cursor-agent, mock)
  claude_code_path: null  # Optional custom path to claude-code CLI

sync:
  frequency: 1h  # How often to sync in continuous mode
```

### Managing Configuration

```bash
# Initialize interactively
ghw init

# List all configuration values
ghw config --list

# Get a value (omit the second argument)
ghw config issues-path

# Set a value (provide both key and value)
ghw config issues-path /custom/path

# Set nested values using dot notation
ghw config plan.parallelism 5

# Configure worktree and PR automation
ghw config implement.use_worktree true
ghw config implement.push_branch true
ghw config implement.create_pr true

# Change default agent
ghw config agent.default cursor-agent
```

## File Structure

gh-worker uses a file-based storage system:

```
~/.config/gh-worker/
└── config.yaml                      # Configuration

~/gh-worker/
├── issues/
│   └── owner/
│       └── repo/
│           ├── .updated-at          # Last sync timestamp
│           └── 42/                  # Issue number
│               ├── description.md   # Issue content
│               ├── .updated-at      # Issue update timestamp
│               ├── plan-<timestamp>.md  # Implementation plan
│               └── .plan-<timestamp>.yaml  # Plan metadata
└── repos/
    └── owner/
        └── repo/                    # Cloned repository
```

## Agents

gh-worker supports multiple LLM agents through a pluggable architecture:

### Available Agents

- **claude-code** (default): Uses the Claude Code CLI tool for comprehensive implementations
- **cursor-agent**: Uses the Cursor Agent CLI for fast code generation
- **mock**: Test agent for development and CI/CD (no external dependencies)
- **opencode**: OpenCode agent (uses `opencode run` CLI)
- **gemini**: Google Gemini agent (placeholder, not yet implemented)
- **codex**: OpenAI Codex agent (placeholder, not yet implemented)

### Configuring Agents

```bash
# Set the default agent
ghw config agent.default claude-code

# Use different agent at runtime
ghw issues plan --repo owner/repo --agent cursor-agent
ghw issues implement --repo owner/repo --agent cursor-agent

# Configure agent-specific settings
ghw config agent.claude_code_path /custom/path/to/claude-code
ghw config agent.opencode_path /custom/path/to/opencode
```

### Agent Requirements

- **claude-code**: [Claude Code CLI](https://claude.ai/code) installed and authenticated
- **cursor-agent**: Cursor Agent CLI (`npm install -g @cursor/agent`)
- **mock**: No external dependencies (built-in)

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=gh_worker --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_agents.py

# Run specific test
uv run pytest tests/unit/test_agents.py::TestAgentRegistry::test_registry_initialization
```

### Linting and Formatting

```bash
# Check code
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Project Structure

```
gh-worker/
├── src/gh_worker/
│   ├── cli.py                    # CLI entry point
│   ├── config/                   # Configuration management
│   ├── commands/                 # Command implementations
│   ├── models/                   # Data models
│   ├── storage/                  # File-based storage
│   ├── agents/                   # LLM agent abstraction
│   ├── github/                   # GitHub CLI wrapper
│   ├── executor/                 # Parallel execution
│   └── utils/                    # Utilities
├── tests/                        # Tests
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
├── pyproject.toml                # Project configuration
└── README.md                     # This file
```

## Troubleshooting

### GitHub CLI Not Authenticated

```bash
gh auth login
```

### Claude Code CLI Not Found

Install the Claude Code CLI from [claude.ai/code](https://claude.ai/code).

### Cursor Agent CLI Not Found

Install the Cursor Agent CLI:

```bash
npm install -g @cursor/agent
```

Verify installation:

```bash
cursor-agent --version
# or
agent --version
```

### Permission Denied Errors

Ensure the configured paths are writable:

```bash
mkdir -p ~/gh-worker/issues ~/gh-worker/repos
chmod 755 ~/gh-worker
```

### Issues Not Syncing

Check that the repository name is correct and you have access:

```bash
gh repo view owner/repo
```

### Plans Not Generated

Verify the agent CLI is working:

```bash
# For Claude Code
claude-code --version

# For Cursor Agent
cursor-agent --version

# Try a different agent
ghw issues plan --repo owner/repo --agent mock
```

## Examples

### Process New Issues Daily

```bash
# In a cron job or systemd timer
ghw work --once --repos owner/repo --since 1d
```

### Continuous Monitoring

```bash
# Run continuously, checking every 30 minutes
ghw work --repos owner/repo --frequency 30m
```

### Manual Workflow

```bash
# 1. Initialize configuration
ghw init

# 2. Sync recent issues
ghw issues sync --repo owner/repo --since 7d

# 3. Generate plans
ghw issues plan --repo owner/repo

# 4. Review plans in ~/gh-worker/issues/owner/repo/*/plan-*.md

# 5. Implement a specific issue with full automation
ghw issues implement --repo owner/repo --issue-numbers 42 --push-branch --create-pr

# 6. Monitor progress
ghw monitor --repo owner/repo --issue-number 42
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Run tests before submitting: `uv run pytest`
2. Format code with ruff: `uv run ruff format src/ tests/`
3. Check for linting issues: `uv run ruff check src/ tests/`
4. Write tests for new features
5. Update documentation as needed

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/tomzxcode/gh-worker).
