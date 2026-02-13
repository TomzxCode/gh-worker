"""Sync command implementation."""

from datetime import UTC, datetime
from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.github.client import GHClient
from gh_worker.models.issue import Issue
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore

logger = structlog.get_logger()


def sync_repository(
    repository: Repository,
    issue_store: IssueStore,
    gh_client: GHClient,
    since: str | None = None,
    issue_numbers: list[int] | None = None,
    search: str | None = None,
) -> int:
    """Sync issues for a single repository.

    Args:
        repository: Repository to sync
        issue_store: IssueStore instance
        gh_client: GHClient instance
        since: Only sync issues updated after this timestamp
        issue_numbers: Specific issue numbers to sync
        search: GitHub search query

    Returns:
        Number of issues synced
    """
    logger.info("syncing_repository", repository=repository.full_name)

    if issue_numbers:
        issues_data = []
        for issue_number in issue_numbers:
            try:
                issue_data = gh_client.get_issue(repository, issue_number)
                issues_data.append(issue_data)
            except Exception as e:
                logger.error("failed_to_get_issue", issue_number=issue_number, error=str(e))
    else:
        # Get timestamp for filtering
        since_filter = since
        if not since_filter:
            repo_updated_at = issue_store.get_repo_updated_at(repository)
            if repo_updated_at:
                since_filter = repo_updated_at.isoformat()

        issues_data = gh_client.list_issues(repository, since=since_filter, search=search)

    # Save issues
    count = 0
    latest_update = datetime.min.replace(tzinfo=UTC)
    for issue_data in issues_data:
        issue = Issue.from_gh_json(issue_data, repository.full_name)
        issue_store.save_issue(issue)
        count += 1

        if issue.updated_at > latest_update:
            latest_update = issue.updated_at

    # Update repository timestamp
    if count > 0:
        issue_store.set_repo_updated_at(repository, latest_update)

    logger.info("synced_repository", repository=repository.full_name, count=count)
    return count


def sync_command(
    repo: str | None = None,
    all_repos: bool = False,
    since: str | None = None,
    issue_numbers: list[int] | None = None,
    search: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Execute sync command.

    Args:
        repo: Repository to sync (e.g., 'owner/repo')
        all_repos: Sync all repositories
        since: Only sync issues updated since this timestamp
        issue_numbers: Specific issue numbers to sync
        search: GitHub search query
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("issues_path_not_configured")
        print("Error: issues-path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    gh_client = GHClient(app_config.repository_path)

    if not gh_client.check_auth():
        logger.error("gh_not_authenticated")
        print("Error: gh CLI not authenticated. Run: gh auth login")
        return

    if all_repos:
        repositories = issue_store.list_repositories()
        if not repositories:
            logger.warning("no_repositories_found")
            print("No repositories found. Use 'gh-worker repositories add' to add repositories.")
            return

        total = 0
        for repository in repositories:
            count = sync_repository(
                repository, issue_store, gh_client, since, issue_numbers, search
            )
            total += count

        print(f"Synced {total} issues across {len(repositories)} repositories")

    elif repo:
        repository = Repository.from_string(repo)
        count = sync_repository(repository, issue_store, gh_client, since, issue_numbers, search)
        print(f"Synced {count} issues from {repository.full_name}")

    else:
        logger.error("no_repository_specified")
        print("Error: Specify --repo or --all-repos")
