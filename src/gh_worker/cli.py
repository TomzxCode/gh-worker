"""CLI entry point using cyclopts."""

from pathlib import Path
from typing import Annotated

import cyclopts
from cyclopts import Parameter

from gh_worker.agents.registry import get_registry
from gh_worker.utils.logging import setup_logging

# Get list of available agents for choices
available_agents = ", ".join(sorted(get_registry().list_agents()))

app = cyclopts.App(name="gh-worker", help="Automated GitHub issue handling with LLM agents")


@app.meta.default
def main(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    log_level: Annotated[str, Parameter(help="Log level (DEBUG, INFO, WARNING, ERROR)")] = "INFO",
) -> None:
    """gh-worker: Automated GitHub issue handling with LLM agents."""
    setup_logging(log_level)
    app(tokens)


@app.command(sort_key=0)
def init(
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
) -> None:
    """Initialize configuration interactively."""
    from gh_worker.commands.init import init_command

    init_command(config_path=config_path)


@app.command(sort_key=5)
def config(
    key: Annotated[
        str | None,
        Parameter(help="Configuration key (e.g., 'issues-path', 'plan.parallelism')"),
    ] = None,
    value: Annotated[
        str | None, Parameter(help="Value to set (if None, gets the current value)")
    ] = None,
    list_: Annotated[
        bool, Parameter(name="--list", help="List all set configuration values")
    ] = False,
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
) -> None:
    """Manage configuration."""
    from gh_worker.commands.config import config_command

    config_command(
        key=key,
        value=value,
        list_all=list_,
        config_path=config_path,
    )


repositories_app = cyclopts.App(name="repositories", help="Manage tracked repositories")
app.command(repositories_app)
app["repositories"].sort_key = 1


@repositories_app.command
def add(
    repos: Annotated[list[str], Parameter(help="Repository names (e.g., 'owner/repo')")],
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
) -> None:
    """Add repositories to track."""
    from gh_worker.commands.add import add_command

    add_command(
        repos=repos,
        config_path=config_path,
    )


@repositories_app.command
def list_(
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
) -> None:
    """List all repositories under management."""
    from gh_worker.commands.list import list_command

    list_command(config_path=config_path)


@repositories_app.command
def remove(
    repos: Annotated[list[str], Parameter(help="Repository names (e.g., 'owner/repo')")],
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
    keep_clone: Annotated[
        bool,
        Parameter(help="Keep the cloned repository in repository-path"),
    ] = True,
) -> None:
    """Remove repositories from tracking."""
    from gh_worker.commands.remove import remove_command

    remove_command(
        repos=repos,
        config_path=config_path,
        keep_clone=keep_clone,
    )


issues_app = cyclopts.App(name="issues", help="Sync, plan, and implement issues")
app.command(issues_app)
app["issues"].sort_key = 2


@issues_app.command
def sync(
    repo: Annotated[str | None, Parameter(help="Repository to sync (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to sync")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="Sync all repositories")] = False,
    assigned_to_me: Annotated[
        bool, Parameter(help="Only sync issues assigned to the current user")
    ] = False,
    since: Annotated[
        str | None, Parameter(help="Only sync issues updated since this timestamp")
    ] = None,
    search: Annotated[str | None, Parameter(help="GitHub search query")] = None,
    force: Annotated[
        bool,
        Parameter(
            help="Refresh all issues (re-fetch and update description.md)"
        ),
    ] = False,
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
) -> None:
    """Sync GitHub issues to local files."""
    from gh_worker.commands.sync import sync_command

    sync_command(
        repo=repo,
        all_repos=all_repos,
        since=since,
        issue_numbers=issue_numbers,
        search=search,
        assigned_to_me=assigned_to_me,
        force=force,
        config_path=config_path,
    )


@issues_app.command
def plan(
    repo: Annotated[str | None, Parameter(help="Repository (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to plan")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="Generate plans for all repositories")] = False,
    parallelism: Annotated[int | None, Parameter(help="Number of parallel executions")] = None,
    force: Annotated[bool, Parameter(help="Generate plan even if one already exists")] = False,
    assigned_to_me: Annotated[
        bool, Parameter(help="Only plan issues assigned to the current user")
    ] = False,
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + f". Uses config default if None.",
        ),
    ] = None,
) -> None:
    """Generate implementation plans for issues."""
    from gh_worker.commands.plan import plan_command

    plan_command(
        repo=repo,
        issue_numbers=issue_numbers,
        all_repos=all_repos,
        parallelism=parallelism,
        force=force,
        assigned_to_me=assigned_to_me,
        config_path=config_path,
        agent=agent,
    )


@issues_app.command
def implement(
    repo: Annotated[str | None, Parameter(help="Repository (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to implement")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="Implement plans for all repositories")] = False,
    parallelism: Annotated[int | None, Parameter(help="Number of parallel executions")] = None,
    force: Annotated[bool, Parameter(help="Implement even if already completed")] = False,
    assigned_to_me: Annotated[
        bool, Parameter(help="Only implement issues assigned to the current user")
    ] = False,
    use_worktree: Annotated[
        bool | None,
        Parameter(help="Use git worktree for isolated implementation (overrides config)"),
    ] = None,
    push_branch: Annotated[
        bool | None,
        Parameter(help="Push branch to remote after implementation (overrides config)"),
    ] = None,
    create_pr: Annotated[
        bool | None,
        Parameter(help="Create pull request after implementation (overrides config)"),
    ] = None,
    delete_worktree: Annotated[
        bool | None,
        Parameter(help="Delete worktree after implementation (overrides config)"),
    ] = None,
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + ". Uses config default if None."
        ),
    ] = None,
) -> None:
    """Implement plans and create PRs."""
    from gh_worker.commands.implement import implement_command

    implement_command(
        repo=repo,
        issue_numbers=issue_numbers,
        all_repos=all_repos,
        parallelism=parallelism,
        force=force,
        assigned_to_me=assigned_to_me,
        use_worktree=use_worktree,
        push_branch=push_branch,
        create_pr=create_pr,
        delete_worktree=delete_worktree,
        config_path=config_path,
        agent=agent,
    )


@app.command(sort_key=3)
def monitor(
    repo: Annotated[str, Parameter(help="Repository (e.g., 'owner/repo')")],
    issue_number: Annotated[int, Parameter(help="Issue number to monitor")],
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + ". Uses config default if None."
        ),
    ] = None,
) -> None:
    """Monitor LLM agent session progress."""
    from gh_worker.commands.monitor import monitor_command

    monitor_command(
        repo=repo,
        issue_number=issue_number,
        config_path=config_path,
        agent=agent,
    )


@app.command(sort_key=4)
def work(
    once: Annotated[bool, Parameter(help="Run once and exit (default: continuous mode)")] = False,
    frequency: Annotated[
        str | None, Parameter(help="Sync frequency (e.g., '10m', '1h', '1d')")
    ] = None,
    repos: Annotated[list[str] | None, Parameter(help="Repositories to process")] = None,
    since: Annotated[
        str | None, Parameter(help="Only process issues updated since this timestamp")
    ] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to process")
    ] = None,
    config_path: Annotated[
        Path | None,
        Parameter(help="Path to config file (default: ~/.config/gh-worker/config.yaml)"),
    ] = None,
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + ". Uses config default if None."
        ),
    ] = None,
) -> None:
    """Run sync, plan, implement workflow."""
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
