"""CLI entry point using cyclopts."""

from pathlib import Path
from typing import Annotated

import cyclopts
from cyclopts import Parameter

from gh_worker.utils.logging import setup_logging

app = cyclopts.App(name="gh-worker", help="Automated GitHub issue handling with LLM agents")


@app.meta.default
def main(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    log_level: str = "INFO",
) -> None:
    """gh-worker: Automated GitHub issue handling with LLM agents.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    setup_logging(log_level)
    app(tokens)


@app.command
def init(
    config_path: Path | None = None,
) -> None:
    """Initialize configuration interactively.

    Args:
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
    """
    from gh_worker.commands.init import init_command

    init_command(config_path=config_path)


@app.command
def config(
    key: str,
    value: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Manage configuration.

    Args:
        key: Configuration key (e.g., 'issues-path', 'plan.parallelism')
        value: Value to set (if None, gets the current value)
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
    """
    from gh_worker.commands.config import config_command

    config_command(
        key=key,
        value=value,
        config_path=config_path,
    )


@app.command
def add(
    repos: list[str],
    config_path: Path | None = None,
) -> None:
    """Add repositories to track.

    Args:
        repos: Repository names (e.g., 'owner/repo')
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
    """
    from gh_worker.commands.add import add_command

    add_command(
        repos=repos,
        config_path=config_path,
    )


@app.command
def sync(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    *,
    all_repos: bool = False,
    since: str | None = None,
    search: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Sync GitHub issues to local files.

    Args:
        repo: Repository to sync (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to sync
        all_repos: Sync all repositories
        since: Only sync issues updated since this timestamp
        search: GitHub search query
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
    """
    from gh_worker.commands.sync import sync_command

    sync_command(
        repo=repo,
        all_repos=all_repos,
        since=since,
        issue_numbers=issue_numbers,
        search=search,
        config_path=config_path,
    )


@app.command
def plan(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    *,
    all_repos: bool = False,
    parallelism: int | None = None,
    force: bool = False,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Generate implementation plans for issues.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to plan
        all_repos: Generate plans for all repositories
        parallelism: Number of parallel executions
        force: Generate plan even if one already exists
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
        agent: Agent to use (e.g., 'mock', 'claude-code', 'opencode', 'gemini', 'codex')
            Uses config default if None. Use 'mock' for quick testing without LLM calls.
    """
    from gh_worker.commands.plan import plan_command

    plan_command(
        repo=repo,
        issue_numbers=issue_numbers,
        all_repos=all_repos,
        parallelism=parallelism,
        force=force,
        config_path=config_path,
        agent=agent,
    )


@app.command
def implement(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    *,
    all_repos: bool = False,
    parallelism: int | None = None,
    force: bool = False,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Implement plans and create PRs.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to implement
        all_repos: Implement plans for all repositories
        parallelism: Number of parallel executions
        force: Implement even if already completed
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
        agent: Override agent to use (e.g., 'claude-code', 'opencode', 'gemini', 'codex')
    """
    from gh_worker.commands.implement import implement_command

    implement_command(
        repo=repo,
        issue_numbers=issue_numbers,
        all_repos=all_repos,
        parallelism=parallelism,
        force=force,
        config_path=config_path,
        agent=agent,
    )


@app.command
def monitor(
    repo: str,
    issue_number: int,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Monitor LLM agent session progress.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_number: Issue number to monitor
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
        agent: Override agent to use (e.g., 'claude-code', 'opencode', 'gemini', 'codex')
    """
    from gh_worker.commands.monitor import monitor_command

    monitor_command(
        repo=repo,
        issue_number=issue_number,
        config_path=config_path,
        agent=agent,
    )


@app.command
def work(
    once: bool = False,
    frequency: str | None = None,
    repos: list[str] | None = None,
    since: str | None = None,
    issue_numbers: list[int] | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Run sync, plan, implement workflow.

    Args:
        once: Run once and exit (default: continuous mode)
        frequency: Sync frequency (e.g., '10m', '1h', '1d')
        repos: Repositories to process
        since: Only process issues updated since this timestamp
        issue_numbers: Specific issue numbers to process
        config_path: Path to config file (default: ~/.config/gh-worker/config.yaml)
        agent: Override agent to use (e.g., 'claude-code', 'opencode', 'gemini', 'codex')
    """
    from gh_worker.commands.work import work_command

    work_command(
        once=once,
        frequency=frequency,
        repos=repos,
        since=since,
        issue_numbers=issue_numbers,
        config_path=config_path,
        agent=agent,
    )


if __name__ == "__main__":
    app.meta()
