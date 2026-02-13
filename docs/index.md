# gh-worker

**Automated GitHub issue handling with LLM agents**

gh-worker is a CLI tool that automates the entire lifecycle of GitHub issue resolution, from syncing issues to generating implementation plans and creating pull requests using LLM agents.

## Overview

gh-worker streamlines software development workflows by automating routine issue handling tasks:

- **Sync** issues from GitHub to local storage
- **Plan** implementations using AI agents (Claude Code, OpenCode, Gemini, Codex)
- **Review** and approve plans before implementation
- **Implement** plans automatically and create pull requests
- **Monitor** ongoing plan or implementation progress in real-time

## Key Features

### Automated Issue Processing

Automatically sync GitHub issues to local files, making them available for processing by LLM agents.

### AI-Powered Planning

Generate comprehensive implementation plans using state-of-the-art LLM agents that understand your codebase and issue requirements.

### Parallel Execution

Process multiple issues concurrently with configurable parallelism for both planning and implementation phases.

### Continuous Workflow

Run sync → plan → implement cycles continuously with configurable frequencies, or execute on-demand for specific issues.

### Pluggable Architecture

Support for multiple LLM agents through a flexible plugin system. Ships with built-in support for:

- Claude Code (default)
- Cursor Agent
- OpenCode
- Google Gemini (placeholder)
- OpenAI Codex (placeholder)

### File-Based Storage

Simple, transparent file-based storage system that makes it easy to inspect, version control, and manage issue data and plans.

### Robust Error Handling

Automatic retry logic with exponential backoff for transient failures, ensuring reliable operation in production environments.

## Quick Start

```bash
# Install with uv
uv tool install https://github.com/tomzxcode/gh-worker.git

# Initialize configuration (interactive setup)
ghw init

# Add a repository
ghw repositories add owner/repo

# Sync issues
ghw issues sync --repo owner/repo

# Generate plans
ghw issues plan --repo owner/repo

# Review and approve plans (optional)
ghw issues review plan --repo owner/repo 42 --approve

# Implement
ghw issues implement --repo owner/repo
```

For a step-by-step tutorial, see the [Walkthrough Guide](walkthrough.md). For detailed instructions, see the [Installation](installation.md) and [Usage](usage.md) guides.

## Architecture

gh-worker is built with a modular architecture:

- **CLI Layer**: Built with cyclopts for a clean command-line interface
- **Storage Layer**: File-based storage for issues and plans
- **Agent Layer**: Pluggable LLM agent system
- **Execution Layer**: Parallel execution orchestration
- **GitHub Layer**: Wrapper around GitHub CLI for repository operations

For technical details, see the [Architecture](architecture.md) documentation.

## Use Cases

### Automated Issue Triage

Automatically generate implementation plans for new issues, helping maintainers quickly understand the scope and complexity of bug reports and feature requests.

### Batch Processing

Process multiple issues in parallel, ideal for cleaning up issue backlogs or handling routine maintenance tasks.

### Continuous Integration

Run gh-worker continuously to automatically handle issues as they arrive, creating a fully automated issue-to-PR pipeline.

### Development Assistance

Use gh-worker as a development assistant that generates implementation plans you can review and modify before execution.

## Next Steps

- [Walkthrough Guide](walkthrough.md) - Step-by-step tutorial from setup to first PR
- [Installation Guide](installation.md) - Get gh-worker up and running
- [Configuration](configuration.md) - Configure gh-worker for your workflow
- [Usage Guide](usage.md) - Learn the commands and workflows
- [Agents](agents.md) - Understand the agent system
- [Architecture](architecture.md) - Technical deep dive

## Requirements

- Python 3.12 or later
- [uv](https://github.com/astral-sh/uv) package manager
- [GitHub CLI](https://cli.github.com/) authenticated with your account
- [Claude Code CLI](https://claude.ai/code) (for the default agent)

## License

MIT License - See [LICENSE](../LICENSE) for details.

## Support

For issues, questions, or contributions:

- GitHub Issues: [gh-worker issues](https://github.com/tomzxcode/gh-worker/issues)
- Repository: [gh-worker](https://github.com/tomzxcode/gh-worker)
