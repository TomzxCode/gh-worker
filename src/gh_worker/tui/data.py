"""Data loading helpers for TUI."""

from pathlib import Path

from gh_worker.commands.issues_list import (
    _get_implementation_status,
    _get_issue_title,
    _get_plan_status,
    _matches_filters,
)
from gh_worker.config.manager import ConfigManager
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore


def get_repositories(config_path: Path | None = None) -> list[Repository]:
    """Get list of tracked repositories."""
    config = ConfigManager(config_path)
    app_config = config.load()
    if not app_config.issues_path:
        return []
    issue_store = IssueStore(app_config.issues_path)
    return sorted(issue_store.list_repositories(), key=lambda r: r.full_name)


def get_issues(
    repo: str | None = None,
    all_repos: bool = False,
    title_filter: str | None = None,
    plan_filter: str | None = None,
    implementation_filter: str | None = None,
    assignee_filter: str | None = None,
    author_filter: str | None = None,
    state_filter: str | None = None,
    config_path: Path | None = None,
) -> list[tuple[Repository, int, str, str | None, list[str], str, str, str | None]]:
    """Get issues as (repo, issue_number, title, author, assignees, plan_status,
    impl_status, state).
    """
    config = ConfigManager(config_path)
    app_config = config.load()
    if not app_config.issues_path:
        return []

    issue_store = IssueStore(app_config.issues_path)
    plan_store = PlanStore(app_config.issues_path)

    if repo:
        try:
            repository = issue_store.resolve_repo(repo)
            repositories = [repository]
        except ValueError:
            return []
    elif all_repos:
        repositories = issue_store.list_repositories()
    else:
        return []

    result: list[tuple[Repository, int, str, str | None, list[str], str, str, str | None]] = []
    for repository in sorted(repositories, key=lambda r: r.full_name):
        for issue_number in sorted(issue_store.list_issues(repository)):
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            title = _get_issue_title(issue_dir)
            author = issue_store.get_issue_author(repository, issue_number)
            assignees = issue_store.get_issue_assignees(repository, issue_number)
            plan_status = _get_plan_status(plan_store, repository, issue_number)
            impl_status = _get_implementation_status(plan_store, repository, issue_number)
            state = issue_store.get_issue_state(repository, issue_number)

            if not _matches_filters(
                title,
                author,
                assignees,
                plan_status,
                impl_status,
                state,
                title_filter,
                author_filter,
                assignee_filter,
                plan_filter,
                implementation_filter,
                state_filter,
            ):
                continue

            result.append(
                (
                    repository,
                    issue_number,
                    title,
                    author,
                    assignees,
                    plan_status,
                    impl_status,
                    state,
                )
            )

    return result


def get_issue_description(
    repository: Repository, issue_number: int, config_path: Path | None = None
) -> str:
    """Get issue description content."""
    config = ConfigManager(config_path)
    app_config = config.load()
    if not app_config.issues_path:
        return ""
    issue_store = IssueStore(app_config.issues_path)
    issue_dir = issue_store.get_issue_dir(repository, issue_number)
    desc_file = issue_dir / "description.md"
    if not desc_file.exists():
        return ""
    return desc_file.read_text()


def is_repo_cloned(repository: Repository, repository_path: Path | None) -> bool:
    """Check if repository is cloned."""
    if not repository_path:
        return False
    repo_path = repository_path / repository.owner / repository.name
    return repo_path.exists()
