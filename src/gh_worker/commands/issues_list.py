"""Issues list command implementation."""

from pathlib import Path

import structlog
from rich.console import Console
from rich.table import Table

from gh_worker.config.manager import ConfigManager
from gh_worker.github.client import GHClient
from gh_worker.models.plan import PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


# Plan status values for display
PLAN_NONE = "none"
PLAN_BEING_GENERATED = "being generated"
PLAN_WAITING_FOR_REVIEW = "waiting for local review"
PLAN_APPROVED = "approved"

# Implementation status values for display
IMPL_NONE = "none"
IMPL_BEING_GENERATED = "being generated"
IMPL_WAITING_FOR_REVIEW = "waiting for local review"
IMPL_PR_OPENED = "PR opened"
IMPL_MERGED = "merged"
IMPL_FAILED = "failed"


def _get_plan_status(plan_store: PlanStore, repository: Repository, issue_number: int) -> str:
    """Get plan status for display."""
    plan_result = plan_store.get_latest_plan(repository, issue_number)
    if not plan_result:
        return PLAN_NONE
    plan_file, metadata = plan_result
    if not plan_file.exists():
        return PLAN_BEING_GENERATED  # metadata exists but .md doesn't = generating or failed
    if metadata.status == PlanStatus.PENDING:
        return PLAN_WAITING_FOR_REVIEW
    return PLAN_APPROVED


def _get_implementation_status(
    plan_store: PlanStore, repository: Repository, issue_number: int
) -> str:
    """Get implementation status for display."""
    plan_result = plan_store.get_latest_plan(repository, issue_number)
    if not plan_result:
        return IMPL_NONE
    _, metadata = plan_result
    if metadata.status.value == "in_progress":
        return IMPL_BEING_GENERATED
    if metadata.status.value == "failed":
        return IMPL_FAILED
    if metadata.status.value == "completed":
        if getattr(metadata, "merged_at", None):
            return IMPL_MERGED
        if metadata.pr_url:
            return IMPL_PR_OPENED
        return IMPL_WAITING_FOR_REVIEW
    return IMPL_NONE


def _matches_filters(
    title: str,
    author: str | None,
    assignees: list[str],
    plan_status: str,
    implementation_status: str,
    state: str | None,
    title_filter: str | None,
    author_filter: str | None,
    assignee_filter: str | None,
    plan_filter: str | None,
    implementation_filter: str | None,
    state_filter: str | None,
) -> bool:
    """Check if issue matches all specified filters (case-insensitive substring match)."""
    if title_filter and title_filter.lower() not in (title or "").lower():
        return False
    if author_filter:
        author_str = (author or "").lower()
        if author_filter.lower() not in author_str:
            return False
    if assignee_filter:
        assignees_str = ",".join(assignees).lower()
        if assignee_filter.lower() not in assignees_str:
            return False
    if plan_filter and plan_filter.lower() != plan_status.lower():
        return False
    if implementation_filter and implementation_filter.lower() != implementation_status.lower():
        return False
    if state_filter and (state or "").lower() != state_filter.lower():
        return False
    return True


def _get_issue_title(issue_dir: Path) -> str:
    """Extract issue title from description.md.

    Args:
        issue_dir: Path to issue directory

    Returns:
        Issue title or placeholder if not found
    """
    description_file = issue_dir / "description.md"
    if not description_file.exists():
        return "(no description)"

    first_line = description_file.read_text().splitlines()[0]
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return first_line.strip() or "(no title)"


def issues_list_command(
    repo: str | None = None,
    all_repos: bool = False,
    issue_numbers: list[int] | None = None,
    title: str | None = None,
    author: str | None = None,
    assignee: str | None = None,
    plan: str | None = None,
    implementation: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Execute issues list command.

    Args:
        repo: Repository to list issues for (e.g., 'owner/repo')
        all_repos: List issues from all repositories
        issue_numbers: Only list these specific issue numbers
        title: Filter by title (substring match)
        author: Filter by author (substring match)
        assignee: Filter by assignee (substring match)
        plan: Filter by plan status (none, being generated, waiting for local review, approved)
        implementation: Filter by implementation status (none, being generated,
            waiting for local review, PR opened, merged, failed)
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    plan_store = PlanStore(app_config.issues_path)

    if repo:
        try:
            repository = issue_store.resolve_repo(repo)
        except ValueError as e:
            logger.error("Invalid repository", repo=repo, error=str(e))
            return
        repositories = [repository]
    elif all_repos:
        repositories = issue_store.list_repositories()
    else:
        logger.error("Specify --repo <owner/repo> or --all-repos")
        return

    if not repositories:
        logger.info("No repositories under management.")
        return

    # Resolve @me to current user for author/assignee filters
    author_filter = author
    assignee_filter = assignee
    if author == "@me" or assignee == "@me":
        gh_client = GHClient()
        if not gh_client.check_auth():
            logger.error("gh CLI not authenticated. Run: gh auth login")
            return
        current_user = gh_client.get_current_user()
        if not current_user:
            logger.error("Could not determine current user. Run: gh auth login")
            return
        if author == "@me":
            author_filter = current_user
        if assignee == "@me":
            assignee_filter = current_user

    table = Table(show_header=True, header_style="bold")
    table.add_column("Repository", style="cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title")
    table.add_column("Author", style="dim")
    table.add_column("Assignees", style="dim")
    table.add_column("Plan", style="green")
    table.add_column("Implementation", style="green")

    issue_numbers_filter = set(issue_numbers) if issue_numbers else None

    for repository in sorted(repositories, key=lambda r: r.full_name):
        repo_issue_numbers = issue_store.list_issues(repository)
        if not repo_issue_numbers:
            continue

        if issue_numbers_filter is not None:
            repo_issue_numbers = [n for n in repo_issue_numbers if n in issue_numbers_filter]
        if not repo_issue_numbers:
            continue

        for issue_number in sorted(repo_issue_numbers):
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_title = _get_issue_title(issue_dir)
            issue_author = issue_store.get_issue_author(repository, issue_number)
            issue_assignees = issue_store.get_issue_assignees(repository, issue_number)
            plan_status = _get_plan_status(plan_store, repository, issue_number)
            implementation_status = _get_implementation_status(plan_store, repository, issue_number)
            issue_state = issue_store.get_issue_state(repository, issue_number)

            if not _matches_filters(
                issue_title,
                issue_author,
                issue_assignees,
                plan_status,
                implementation_status,
                issue_state,
                title,
                author_filter,
                assignee_filter,
                plan,
                implementation,
                None,  # state_filter - CLI doesn't support state filter yet
            ):
                continue

            if len(issue_title) > 60:
                issue_title = issue_title[:57] + "..."
            assignees_str = ", ".join(issue_assignees) if issue_assignees else "—"

            table.add_row(
                repository.full_name,
                str(issue_number),
                issue_title,
                issue_author or "—",
                assignees_str,
                "—" if plan_status == "none" else plan_status,
                "—" if implementation_status == "none" else implementation_status,
            )

    console = Console()
    console.print(table)
