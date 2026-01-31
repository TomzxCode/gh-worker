# Installation

This guide walks you through installing gh-worker and its dependencies.

## Prerequisites

Before installing gh-worker, ensure you have the following:

### Python 3.12+

gh-worker requires Python 3.12 or later (latest LTS version).

```bash
# Check your Python version
python --version
```

If you need to install or upgrade Python, visit [python.org](https://www.python.org/downloads/).

### uv Package Manager

gh-worker uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### GitHub CLI

The [GitHub CLI](https://cli.github.com/) is required for interacting with GitHub repositories and issues.

```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
sudo apt install gh

# Linux (other)
# See https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Windows
winget install GitHub.cli

# Verify installation
gh --version
```

### Authenticate GitHub CLI

You must authenticate the GitHub CLI with your GitHub account:

```bash
# Authenticate with GitHub
gh auth login

# Verify authentication
gh auth status
```

Follow the prompts to complete authentication. You'll need:

- A GitHub account
- Permissions to access the repositories you want to manage

### Claude Code CLI (Optional)

If you plan to use the default Claude Code agent, install the [Claude Code CLI](https://claude.ai/code):

```bash
# Follow installation instructions at:
# https://claude.ai/code

# Verify installation
claude-code --version
```

## Install gh-worker

### From Source

Install with uv:

```bash
# Install with uv
uv tool install https://github.com/tomzxcode/gh-worker.git
```

### Verify Installation

After installation, verify that gh-worker is available:

```bash
# Check that the command is available
ghw --help

# Or use the full name
gh-worker --help

# Check version info
ghw --version
```

Both `ghw` (short alias) and `gh-worker` (full name) are available as commands.

## Post-Installation Setup

### Configure Base Paths

Set up the base paths where gh-worker will store data:

```bash
# Set the path where issues will be stored
ghw config issues-path ~/gh-worker/issues

# Set the path where repositories will be cloned
ghw config repository-path ~/gh-worker/repos
```

These directories will be created automatically when you start using gh-worker.

### Configure Agent (Optional)

If you're using a custom agent or want to change the default:

```bash
# Set the default agent
ghw config agent.default claude-code

# If Claude Code is not in your PATH, specify its location
ghw config agent.claude_code_path /path/to/claude-code
```

### Verify Setup

Verify that everything is configured correctly:

```bash
# Check configuration
ghw config issues-path
ghw config repository-path

# Check GitHub authentication
gh auth status

# Check agent availability (for Claude Code)
claude-code --version
```

## Troubleshooting

### Command Not Found: ghw

If you get a "command not found" error, ensure that Python's script directory is in your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Reload your shell
source ~/.bashrc  # or source ~/.zshrc
```

### GitHub CLI Not Authenticated

If you see authentication errors:

```bash
# Re-authenticate
gh auth login

# Check status
gh auth status
```

### Permission Denied

If you encounter permission errors when creating directories:

```bash
# Ensure the parent directory is writable
mkdir -p ~/gh-worker
chmod 755 ~/gh-worker
```

### Claude Code Not Found

If the Claude Code agent can't be found:

1. Verify it's installed: `claude-code --version`
1. If it's installed but not in PATH, set the full path:
   ```bash
   ghw config agent.claude_code_path /full/path/to/claude-code
   ```
1. Or switch to a different agent:
   ```bash
   ghw config agent.default opencode
   ```

## Upgrading

To upgrade gh-worker to the latest version:

```bash
# Install with uv
uv tool install https://github.com/tomzxcode/gh-worker.git
```

## Uninstalling

To remove gh-worker:

```bash
# Uninstall the package
uv pip uninstall gh-worker

# Optionally, remove data directories
rm -rf ~/gh-worker
rm -rf ~/.config/gh-worker
```

## Next Steps

Now that gh-worker is installed, proceed to:

- [Configuration](configuration.md) - Configure gh-worker for your needs
- [Usage Guide](usage.md) - Learn how to use gh-worker
- [Quick Start](index.md#quick-start) - Get started quickly
