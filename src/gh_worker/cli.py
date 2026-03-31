"""CLI entry point using cyclopts."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import cyclopts
from cyclopts import Group, Parameter

from gh_worker.agents.registry import get_registry
from gh_worker.utils.logging import setup_logging
from gh_worker.utils.paths import get_config_dir


DEFAULT_CONFIG_PATH = get_config_dir() / "config.yaml"


@dataclass
class CLIContext:
    config_path: Path = DEFAULT_CONFIG_PATH
    log_level: str = "INFO"


_ctx = CLIContext()


def _parse_log_level() -> str:
    """Parse --log-level from argv for initial setup."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log-level", default="INFO")
    args, _ = parser.parse_known_args()
    return args.log_level.upper()


# Setup logging early so import-time logs (e.g. registering_agent) don't spam
setup_logging(_parse_log_level())

# Get list of available agents for choices
available_agents = ", ".join(sorted(get_registry().list_agents()))

app = cyclopts.App(name="gh-worker", help="Automated GitHub issue handling with LLM agents")

_global_params_group = Group("Global Parameters", sort_key=-1)


def _print_all_help() -> None:
    """Print help for every command and subcommand."""
    HELP_INTERNAL = {"help-print", "version-print"}

    def _collect_paths(a: cyclopts.App, path: list[str]) -> list[list[str]]:
        paths: list[list[str]] = []
        if path:
            paths.append(path)
        for sub in a.subapps:
            name = sub.name[0] if sub.name else None
            if name is None or name in HELP_INTERNAL:
                continue
            # Subapp names for nested commands are prefixed with the parent name
            # (e.g. "plans-review" under "plans"). Strip the prefix to get the CLI token.
            if path:
                parent = path[-1]
                cli_name = name[len(parent) + 1 :] if name.startswith(parent + "-") else name
            else:
                cli_name = name
            paths.extend(_collect_paths(sub, path + [cli_name]))
        return paths

    app.help_print(tokens=[])
    for sub in app.subapps:
        name = sub.name[0] if sub.name else None
        if name is None or name in HELP_INTERNAL:
            continue
        for path in _collect_paths(sub, [name]):
            print()
            app.help_print(tokens=path)


@app.meta.default
def main(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    log_level: Annotated[
        str, Parameter(help="Log level (DEBUG, INFO, WARNING, ERROR)", group=_global_params_group)
    ] = "INFO",
    config_path: Annotated[
        Path,
        Parameter(help="Path to config file", group=_global_params_group),
    ] = DEFAULT_CONFIG_PATH,
) -> None:
    """gh-worker: Automated GitHub issue handling with LLM agents."""
    _ctx.log_level = log_level
    _ctx.config_path = config_path
    setup_logging(log_level)
    app(tokens)


@app.command(sort_key=1)
def init() -> None:
    """Initialize configuration interactively."""
    from gh_worker.commands.init import init_command

    init_command(config_path=_ctx.config_path)


@app.command(sort_key=8)
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
) -> None:
    """Manage configuration."""
    from gh_worker.commands.config import config_command

    config_command(
        key=key,
        value=value,
        list_all=list_,
        config_path=_ctx.config_path,
    )


repositories_app = cyclopts.App(name="repositories", help="Manage tracked repositories")
app.command(repositories_app)
app["repositories"].sort_key = 2

plans_app = cyclopts.App(name="plans", help="Review, approve, or unapprove implementation plans")
app.command(plans_app)
app["plans"].sort_key = 4


@repositories_app.command
def add(
    repos: Annotated[list[str], Parameter(help="Repository names (e.g., 'owner/repo')")],
    clone: Annotated[
        bool,
        Parameter(help="Clone the repository to repository-path (default: no)"),
    ] = False,
) -> None:
    """Add repositories to track."""
    from gh_worker.commands.add import add_command

    add_command(
        repos=repos,
        config_path=_ctx.config_path,
        clone=clone,
    )


@repositories_app.command
def list_() -> None:
    """List all repositories under management."""
    from gh_worker.commands.list import list_command

    list_command(config_path=_ctx.config_path)


@repositories_app.command
def remove(
    repos: Annotated[list[str], Parameter(help="Repository names (e.g., 'owner/repo')")],
    keep_clone: Annotated[
        bool,
        Parameter(help="Keep the cloned repository in repository-path"),
    ] = True,
) -> None:
    """Remove repositories from tracking."""
    from gh_worker.commands.remove import remove_command

    remove_command(
        repos=repos,
        config_path=_ctx.config_path,
        keep_clone=keep_clone,
    )


issues_app = cyclopts.App(name="issues", help="Sync, plan, and implement issues")
app.command(issues_app)
app["issues"].sort_key = 3


@issues_app.command(sort_key=0)
def sync(
    repo: Annotated[str | None, Parameter(help="Repository to sync (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to sync")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="Sync all repositories")] = False,
    assignee: Annotated[
        str | None,
        Parameter(help="Filter by assignee (substring match). Use @me for current user"),
    ] = None,
    since: Annotated[
        str | None, Parameter(help="Only sync issues updated since this timestamp")
    ] = None,
    search: Annotated[str | None, Parameter(help="GitHub search query")] = None,
    force: Annotated[
        bool,
        Parameter(help="Refresh all issues (re-fetch and update description.md)"),
    ] = False,
) -> None:
    """Sync GitHub issues to local files."""
    from gh_worker.commands.sync import sync_command

    sync_command(
        repo=repo,
        all_repos=all_repos,
        since=since,
        issue_numbers=issue_numbers,
        search=search,
        assignee=assignee,
        force=force,
        config_path=_ctx.config_path,
    )


@issues_app.command(name="list", sort_key=1)
def issues_list(
    repo: Annotated[str | None, Parameter(help="Repository to list (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Only list these specific issue numbers")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="List issues from all repositories")] = False,
    title: Annotated[
        str | None,
        Parameter(help="Filter by title (substring match)"),
    ] = None,
    author: Annotated[
        str | None,
        Parameter(help="Filter by author (substring match). Use @me for current user"),
    ] = None,
    assignee: Annotated[
        str | None,
        Parameter(help="Filter by assignee (substring match). Use @me for current user"),
    ] = None,
    plan: Annotated[
        str | None,
        Parameter(help="Filter by plan: none, being generated, waiting for local review, approved"),
    ] = None,
    implementation: Annotated[
        str | None,
        Parameter(
            help="Filter by implementation: none, being generated, waiting for local review, "
            "PR opened, merged, failed"
        ),
    ] = None,
) -> None:
    """List synced issues with plan and implementation status."""
    from gh_worker.commands.issues_list import issues_list_command

    issues_list_command(
        repo=repo,
        all_repos=all_repos,
        issue_numbers=issue_numbers,
        title=title,
        author=author,
        assignee=assignee,
        plan=plan,
        implementation=implementation,
        config_path=_ctx.config_path,
    )


@issues_app.command(sort_key=2)
def plan(
    repo: Annotated[str | None, Parameter(help="Repository (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to plan")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="Generate plans for all repositories")] = False,
    parallelism: Annotated[int | None, Parameter(help="Number of parallel executions")] = None,
    force: Annotated[bool, Parameter(help="Generate plan even if one already exists")] = False,
    assignee: Annotated[
        str | None,
        Parameter(help="Filter by assignee (substring match). Use @me for current user"),
    ] = None,
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + ". Uses config default if None.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        Parameter(
            help="Override model to use (agent-specific). Uses config default if None.",
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
        assignee=assignee,
        config_path=_ctx.config_path,
        agent=agent,
        model=model,
    )


implementations_app = cyclopts.App(
    name="implementations", help="Review implementations (push branch, create PR)"
)
app.command(implementations_app)
app["implementations"].sort_key = 5


@plans_app.command
def approve(
    repo: Annotated[str, Parameter(help="Repository (e.g., 'owner/repo')")],
    issue_number: Annotated[int, Parameter(help="Issue number to approve")],
) -> None:
    """Mark the plan as approved."""
    from gh_worker.commands.review import review_plan_command

    review_plan_command(
        repo=repo,
        issue_number=issue_number,
        approve=True,
        config_path=_ctx.config_path,
    )


@plans_app.command
def unapprove(
    repo: Annotated[str, Parameter(help="Repository (e.g., 'owner/repo')")],
    issue_number: Annotated[int, Parameter(help="Issue number to unapprove")],
) -> None:
    """Revert plan status to pending (waiting for review)."""
    from gh_worker.commands.review import unapprove_plan_command

    unapprove_plan_command(
        repo=repo,
        issue_number=issue_number,
        config_path=_ctx.config_path,
    )


@plans_app.command(name="review")
def plans_review(
    repo: Annotated[str, Parameter(help="Repository (e.g., 'owner/repo')")],
    issue_number: Annotated[int, Parameter(help="Issue number to review")],
) -> None:
    """Create worktree with plan symlinked for editing."""
    from gh_worker.commands.review import review_plan_command

    review_plan_command(
        repo=repo,
        issue_number=issue_number,
        approve=False,
        config_path=_ctx.config_path,
    )


@implementations_app.command(name="review")
def implementations_review(
    repo: Annotated[str, Parameter(help="Repository (e.g., 'owner/repo')")],
    issue_number: Annotated[int, Parameter(help="Issue number to review")],
    *,
    push: Annotated[
        bool,
        Parameter(help="Push branch to remote"),
    ] = True,
    pr: Annotated[
        bool,
        Parameter(help="Create pull request"),
    ] = True,
) -> None:
    """Approve implementations: push branch and create PR."""
    from gh_worker.commands.review import review_implementation_command

    review_implementation_command(
        repo=repo,
        issue_number=issue_number,
        push_branch=push,
        create_pr=pr,
        config_path=_ctx.config_path,
    )


@issues_app.command(name="review", sort_key=6)
def issues_review(
    repo: Annotated[str | None, Parameter(help="Repository (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to review")
    ] = None,
    *,
    all_repos: Annotated[
        bool, Parameter(help="Review implementations for all repositories")
    ] = False,
    parallelism: Annotated[int | None, Parameter(help="Number of parallel executions")] = None,
    force: Annotated[bool, Parameter(help="Review even if already reviewed")] = False,
    assignee: Annotated[
        str | None,
        Parameter(help="Filter by assignee (substring match). Use @me for current user"),
    ] = None,
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + ". Uses config default if None."
        ),
    ] = None,
    model: Annotated[
        str | None,
        Parameter(
            help="Override model to use (agent-specific). Uses config default if None.",
        ),
    ] = None,
) -> None:
    """Review completed implementations."""
    from gh_worker.commands.review_issues import review_command

    review_command(
        repo=repo,
        issue_numbers=issue_numbers,
        all_repos=all_repos,
        parallelism=parallelism,
        force=force,
        assignee=assignee,
        config_path=_ctx.config_path,
        agent=agent,
        model=model,
    )


@issues_app.command(sort_key=4)
def implement(
    repo: Annotated[str | None, Parameter(help="Repository (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to implement")
    ] = None,
    *,
    all_repos: Annotated[bool, Parameter(help="Implement plans for all repositories")] = False,
    parallelism: Annotated[int | None, Parameter(help="Number of parallel executions")] = None,
    force: Annotated[bool, Parameter(help="Implement even if already completed")] = False,
    assignee: Annotated[
        str | None,
        Parameter(help="Filter by assignee (substring match). Use @me for current user"),
    ] = None,
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
    agent: Annotated[
        str | None,
        Parameter(
            help="Override agent to use. Choices: "
            + available_agents
            + ". Uses config default if None."
        ),
    ] = None,
    model: Annotated[
        str | None,
        Parameter(
            help="Override model to use (agent-specific). Uses config default if None.",
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
        assignee=assignee,
        use_worktree=use_worktree,
        push_branch=push_branch,
        create_pr=create_pr,
        delete_worktree=delete_worktree,
        config_path=_ctx.config_path,
        agent=agent,
        model=model,
    )


@app.command(sort_key=6)
def monitor(
    repo: Annotated[str, Parameter(help="Repository (e.g., 'owner/repo')")],
    issue_number: Annotated[int, Parameter(help="Issue number to monitor")],
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
        config_path=_ctx.config_path,
        agent=agent,
    )


@app.command(sort_key=0)
def tui() -> None:
    """Launch the TUI dashboard."""
    from gh_worker.tui.app import GhWorkerApp

    app = GhWorkerApp(config_path=_ctx.config_path)
    app.run()


@app.command(sort_key=7)
def work(
    repo: Annotated[str | None, Parameter(help="Repository (e.g., 'owner/repo')")] = None,
    issue_numbers: Annotated[
        list[int] | None, Parameter(help="Specific issue numbers to process")
    ] = None,
    *,
    once: Annotated[bool, Parameter(help="Run once and exit (default: continuous mode)")] = False,
    frequency: Annotated[
        str | None, Parameter(help="Sync frequency (e.g., '10m', '1h', '1d')")
    ] = None,
    since: Annotated[
        str | None, Parameter(help="Only process issues updated since this timestamp")
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
        repos=[repo] if repo else None,
        since=since,
        issue_numbers=issue_numbers,
        config_path=_ctx.config_path,
        agent=agent,
    )


def cli() -> None:
    """Entry point that handles --help --all before cyclopts processes flags."""
    argv = sys.argv[1:]
    if ("--help" in argv or "-h" in argv) and "--all" in argv:
        _print_all_help()
    else:
        app.meta()


if __name__ == "__main__":
    cli()
