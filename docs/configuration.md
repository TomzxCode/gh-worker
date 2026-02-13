# Configuration

gh-worker uses a YAML configuration file to store settings. This guide covers all configuration options and how to manage them.

## Configuration File

The configuration file is stored at:

```
~/.config/gh-worker/config.yaml
```

This follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) for configuration files.

## Managing Configuration

### Initial Setup with `ghw init`

For first-time setup, run `ghw init` to configure gh-worker interactively. It prompts for required paths and sets sensible defaults.

```bash
ghw init
```

### Using the CLI

To view or change configuration after setup, use the `config` command:

```bash
# List all configuration values
ghw config --list

# Get a configuration value (provide only the key)
ghw config <key>

# Set a configuration value (provide key and value)
ghw config <key> <value>
```

The command automatically detects whether you're getting or setting based on the number of arguments.

### Using Dot Notation

For nested configuration values, use dot notation:

```bash
# Set nested values
ghw config plan.parallelism 5
ghw config implement.parallelism 2
ghw config agent.default claude-code

# Get nested values
ghw config plan.parallelism
```

### Viewing All Configuration

To view all configuration values via the CLI:

```bash
ghw config --list
```

This outputs all keys and values in `key=value` format (e.g., `plan.parallelism=3`).

Alternatively, you can view the raw YAML file:

```bash
cat ~/.config/gh-worker/config.yaml
```

## Configuration Options

### Base Paths

#### `issues-path`

Path where synced issues are stored.

```bash
ghw config issues-path ~/gh-worker/issues
```

- **Type**: Path
- **Required**: Yes
- **Default**: None

**Directory Structure**:

```
issues-path/
└── owner/
    └── repo/
        ├── .updated-at
        └── 42/
            ├── description.md
            ├── .updated-at
            ├── plan-<timestamp>.md
            └── .plan-<timestamp>.yaml
```

#### `repository-path`

Path where repositories are cloned.

```bash
ghw config repository-path ~/gh-worker/repos
```

- **Type**: Path
- **Required**: Yes
- **Default**: None

**Directory Structure**:

```
repository-path/
└── owner/
    └── repo/  # Git repository
```

### Plan Configuration

Configuration for the `plan` command.

#### `plan.parallelism`

Number of issues to plan in parallel.

```bash
ghw config plan.parallelism 3
```

- **Type**: Integer
- **Required**: No
- **Default**: 1
- **Range**: >= 1

Higher values enable processing multiple issues concurrently, but may increase resource usage and API rate limits.

#### `plan.agent`

Agent to use for planning. Overrides `agent.default` when set.

```bash
ghw config plan.agent claude-code
```

- **Type**: String
- **Required**: No
- **Default**: null (uses `agent.default`)

Use this to run planning with a different agent than implementation (e.g., `claude-code` for plans, `cursor-agent` for implementation).

#### `plan.model`

Model to use for planning. Overrides `agent.model` when set.

```bash
ghw config plan.model claude-sonnet-4-20250514
```

- **Type**: String
- **Required**: No
- **Default**: null (uses `agent.model` or agent default)

**Recommendations**:

- Local development: 1-2
- CI/CD environments: 2-3
- High-performance servers: 3-5

### Implement Configuration

Configuration for the `implement` command.

#### `implement.parallelism`

Number of issues to implement in parallel.

```bash
ghw config implement.parallelism 2
```

- **Type**: Integer
- **Required**: No
- **Default**: 1
- **Range**: >= 1

Implementation is typically more resource-intensive than planning. Use lower values to prevent system overload.

#### `implement.agent`

Agent to use for implementation. Overrides `agent.default` when set.

```bash
ghw config implement.agent cursor-agent
```

- **Type**: String
- **Required**: No
- **Default**: null (uses `agent.default`)

Use this to run implementation with a different agent than planning (e.g., `claude-code` for plans, `cursor-agent` for implementation).

#### `implement.model`

Model to use for implementation. Overrides `agent.model` when set.

```bash
ghw config implement.model gpt-4
```

- **Type**: String
- **Required**: No
- **Default**: null (uses `agent.model` or agent default)

**Recommendations**:

- Local development: 1
- CI/CD environments: 1-2
- High-performance servers: 2-3

#### `implement.use_worktree`

Use git worktree for isolated implementation branches.

```bash
ghw config implement.use_worktree true
```

- **Type**: Boolean
- **Required**: No
- **Default**: true

When enabled, each implementation creates an isolated git worktree, allowing parallel implementations without conflicts.

#### `implement.push_branch`

Automatically push branches to remote after implementation.

```bash
ghw config implement.push_branch true
```

- **Type**: Boolean
- **Required**: No
- **Default**: false

When enabled, branches are pushed to the remote repository after successful implementation.

#### `implement.create_pr`

Automatically create pull requests after implementation.

```bash
ghw config implement.create_pr true
```

- **Type**: Boolean
- **Required**: No
- **Default**: false

When enabled, pull requests are created automatically after successful implementation and push.

#### `implement.delete_worktree`

Delete worktree after implementation completes.

```bash
ghw config implement.delete_worktree true
```

- **Type**: Boolean
- **Required**: No
- **Default**: true

When enabled, the git worktree is removed after implementation. Set to false for debugging.

### Sync Configuration

Configuration for the `sync` command.

#### `sync.frequency`

Default sync frequency for continuous mode.

```bash
ghw config sync.frequency 10m
```

- **Type**: Duration string
- **Required**: No
- **Default**: "1h"
- **Format**: `<number><unit>` where unit is `m` (minutes), `h` (hours), or `d` (days)

**Examples**:

- `10m` - Every 10 minutes
- `1h` - Every hour
- `6h` - Every 6 hours
- `1d` - Every day

### Agent Configuration

Configuration for LLM agents.

#### `agent.default`

Default agent to use for planning and implementation.

```bash
ghw config agent.default claude-code
```

- **Type**: String
- **Required**: No
- **Default**: "claude-code"
- **Options**:
  - `claude-code` - Claude Code CLI agent
  - `cursor-agent` - Cursor Agent CLI
  - `mock` - Mock agent for testing
  - `opencode` - OpenCode agent (uses `opencode run` CLI)
  - `gemini` - Google Gemini agent (placeholder)
  - `codex` - OpenAI Codex agent (placeholder)

#### `agent.claude_code_path`

Custom path to the claude-code binary (if not in PATH).

```bash
ghw config agent.claude_code_path /custom/path/to/claude-code
```

- **Type**: Path
- **Required**: No
- **Default**: None (uses PATH)

Only needed if claude-code is installed in a non-standard location.

#### `agent.cursor_agent_path`

Custom path to the cursor-agent binary (if not in PATH).

```bash
ghw config agent.cursor_agent_path /custom/path/to/cursor-agent
```

- **Type**: Path
- **Required**: No
- **Default**: None (uses PATH)

Only needed if cursor-agent is installed in a non-standard location.

#### `agent.opencode_path`

Custom path to the opencode binary (if not in PATH).

```bash
ghw config agent.opencode_path /custom/path/to/opencode
```

- **Type**: Path
- **Required**: No
- **Default**: None (uses PATH)

Only needed if opencode is installed in a non-standard location.

## Example Configuration File

Here's a complete example configuration file:

```yaml
# ~/.config/gh-worker/config.yaml

# Base paths
issues-path: /home/user/gh-worker/issues
repository-path: /home/user/gh-worker/repos

# Plan configuration
plan:
  parallelism: 3

# Implement configuration
implement:
  parallelism: 2
  use_worktree: true
  push_branch: false
  create_pr: false
  delete_worktree: true

# Sync configuration
sync:
  frequency: 30m

# Agent configuration
agent:
  default: claude-code
  claude_code_path: null  # Use PATH
  opencode_path: null  # Use PATH
```

## Environment-Specific Configuration

### Development

Recommended settings for local development:

```bash
ghw config issues-path ~/gh-worker/dev/issues
ghw config repository-path ~/gh-worker/dev/repos
ghw config plan.parallelism 1
ghw config implement.parallelism 1
ghw config sync.frequency 1h
```

### Production

Recommended settings for production servers:

```bash
ghw config issues-path /var/lib/gh-worker/issues
ghw config repository-path /var/lib/gh-worker/repos
ghw config plan.parallelism 3
ghw config implement.parallelism 2
ghw config sync.frequency 10m
```

### CI/CD

Recommended settings for CI/CD environments:

```bash
ghw config issues-path ./gh-worker/issues
ghw config repository-path ./gh-worker/repos
ghw config plan.parallelism 2
ghw config implement.parallelism 1
```

## Configuration Validation

gh-worker validates configuration values when they're set or used:

- Paths must be absolute or relative to home directory
- Parallelism values must be >= 1
- Frequency strings must match the format `<number><unit>`
- Agent names must be registered in the agent registry

If validation fails, you'll see a clear error message explaining the issue.

## Custom Configuration File

You can use a custom configuration file location:

```bash
# Specify config file for a single command
ghw --config-path /custom/path/config.yaml issues sync --repo owner/repo

# Or set an environment variable
export GH_WORKER_CONFIG=/custom/path/config.yaml
ghw issues sync --repo owner/repo
```

## Troubleshooting

### Configuration Not Found

If gh-worker can't find your configuration:

```bash
# Create the directory
mkdir -p ~/.config/gh-worker

# Set initial values
ghw config issues-path ~/gh-worker/issues
ghw config repository-path ~/gh-worker/repos
```

### Invalid Configuration Values

If you get validation errors:

```bash
# Check current value
ghw config plan.parallelism

# Fix the value
ghw config plan.parallelism 1
```

### Reset Configuration

To reset all configuration:

```bash
# Remove the config file
rm ~/.config/gh-worker/config.yaml

# Reconfigure from scratch
ghw config issues-path ~/gh-worker/issues
ghw config repository-path ~/gh-worker/repos
```

## Next Steps

- [Usage Guide](usage.md) - Learn how to use gh-worker
- [Agents](agents.md) - Understand the agent system
- [Architecture](architecture.md) - Technical details
