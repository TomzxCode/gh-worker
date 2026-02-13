"""Async workers for running commands in background."""

from pathlib import Path

from gh_worker.commands.add import add_command
from gh_worker.commands.implement import implement_command_async
from gh_worker.commands.plan import plan_command_async
from gh_worker.commands.review import (
    review_implementation_command,
    review_plan_command,
    unapprove_plan_command,
)
from gh_worker.commands.sync import sync_command


def run_clone(
    repo: str,
    config_path: Path | None = None,
) -> tuple[bool, str]:
    """Clone a tracked repository. Returns (success, message)."""
    try:
        add_command(repos=[repo], config_path=config_path, clone=True)
        return True, f"Cloned {repo}"
    except Exception as e:
        return False, str(e)


def run_sync(
    repo: str | None = None,
    all_repos: bool = False,
    config_path: Path | None = None,
) -> tuple[bool, str]:
    """Run sync command. Returns (success, message)."""
    try:
        sync_command(
            repo=repo,
            all_repos=all_repos,
            since=None,
            issue_numbers=None,
            search=None,
            assignee=None,
            force=False,
            config_path=config_path,
        )
        return True, "Sync completed"
    except Exception as e:
        return False, str(e)


async def run_plan(
    repo: str | None = None,
    all_repos: bool = False,
    issue_numbers: list[int] | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
) -> tuple[bool, str]:
    """Run plan command. Returns (success, message)."""
    try:
        await plan_command_async(
            repo=repo,
            issue_numbers=issue_numbers,
            all_repos=all_repos,
            parallelism=None,
            force=False,
            config_path=config_path,
            agent=agent,
            model=model,
        )
        return True, "Plan completed"
    except Exception as e:
        return False, str(e)


async def run_implement(
    repo: str | None = None,
    all_repos: bool = False,
    issue_numbers: list[int] | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
) -> tuple[bool, str]:
    """Run implement command. Returns (success, message)."""
    try:
        await implement_command_async(
            repo=repo,
            issue_numbers=issue_numbers,
            all_repos=all_repos,
            parallelism=None,
            force=False,
            config_path=config_path,
            agent=agent,
            model=model,
        )
        return True, "Implement completed"
    except Exception as e:
        return False, str(e)


def run_review_plan(
    repo: str,
    issue_number: int,
    *,
    approve: bool = False,
    config_path: Path | None = None,
) -> tuple[bool, str, Path | None]:
    """Run review plan command. Returns (success, message, worktree_path)."""
    try:
        worktree_path = review_plan_command(
            repo=repo,
            issue_number=issue_number,
            approve=approve,
            config_path=config_path,
        )
        if worktree_path is not None:
            return True, f"Plan worktree ready: {worktree_path}", worktree_path
        return True, "Review plan completed", None
    except Exception as e:
        return False, str(e), None


def run_unapprove_plan(
    repo: str,
    issue_number: int,
    *,
    config_path: Path | None = None,
) -> tuple[bool, str]:
    """Run unapprove plan command. Returns (success, message)."""
    try:
        ok = unapprove_plan_command(
            repo=repo,
            issue_number=issue_number,
            config_path=config_path,
        )
        return ok, "Plan unapproved" if ok else "No approved plan for this issue"
    except Exception as e:
        return False, str(e)


def run_review_implementation(
    repo: str,
    issue_number: int,
    *,
    push_branch: bool = True,
    create_pr: bool = True,
    config_path: Path | None = None,
) -> tuple[bool, str]:
    """Run review implementation command. Returns (success, message)."""
    try:
        review_implementation_command(
            repo=repo,
            issue_number=issue_number,
            push_branch=push_branch,
            create_pr=create_pr,
            config_path=config_path,
        )
        return True, "Implementation reviewed (branch pushed, PR created)"
    except Exception as e:
        return False, str(e)
