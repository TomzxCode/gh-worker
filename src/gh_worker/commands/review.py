"""Review command implementation."""

from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.github.client import GHClient
from gh_worker.models.plan import PlanMetadata, PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


def _find_issues_with_plans_waiting_review(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None,
    assignee_filter: str | None,
) -> list[tuple[Path, PlanMetadata]]:
    """Find issues with plans waiting for local review (status PENDING, plan file exists)."""
    results = []

    if issue_numbers:
        issues_to_check = issue_numbers
    else:
        issues_to_check = issue_store.list_issues(repository)

    for issue_number in issues_to_check:
        if assignee_filter:
            assignees = issue_store.get_issue_assignees(repository, issue_number)
            assignees_str = ",".join(assignees).lower()
            if assignee_filter.lower() not in assignees_str:
                continue

        plan_result = plan_store.get_latest_plan(repository, issue_number)
        if not plan_result:
            continue

        plan_file, metadata = plan_result
        if not plan_file.exists():
            continue
        if metadata.status != PlanStatus.PENDING:
            continue

        results.append((plan_file, metadata))

    return results


def _find_implementations_waiting_review(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None,
    assignee_filter: str | None,
) -> list[tuple[Path, PlanMetadata]]:
    """Find implementations waiting for local review (COMPLETED, no PR, has branch)."""
    results = []

    if issue_numbers:
        issues_to_check = issue_numbers
    else:
        issues_to_check = issue_store.list_issues(repository)

    for issue_number in issues_to_check:
        if assignee_filter:
            assignees = issue_store.get_issue_assignees(repository, issue_number)
            assignees_str = ",".join(assignees).lower()
            if assignee_filter.lower() not in assignees_str:
                continue

        plan_result = plan_store.get_latest_plan(repository, issue_number)
        if not plan_result:
            continue

        _, metadata = plan_result
        if metadata.status != PlanStatus.COMPLETED:
            continue
        if metadata.pr_url:
            continue
        if not metadata.branch_name:
            continue

        plan_file, _ = plan_result
        results.append((plan_file, metadata))

    return results


def review_plan_command(
    repo: str,
    issue_number: int,
    *,
    approve: bool = False,
    config_path: Path | None = None,
) -> None:
    """Create a worktree with the plan symlinked for review, or approve a plan.

    By default, creates a planning worktree and symlinks the plan file so the
    user can open it in their editor and iterate. With --approve, skips
    worktree creation and only updates the plan status to approved.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_number: Issue number to review
        approve: If True, only update plan status (skip worktree+symlink)
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured")
        logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    plan_store = PlanStore(app_config.issues_path)

    try:
        repository = issue_store.resolve_repo(repo)
    except ValueError as e:
        logger.error("Invalid repository", repo=repo, error=str(e))
        logger.error(f"Error: {e}")
        return

    items = _find_issues_with_plans_waiting_review(
        repository, issue_store, plan_store, [issue_number], None
    )
    if not items:
        logger.info("No plan waiting for review for this issue")
        return

    plan_file, metadata = items[0]

    if approve:
        metadata.status = PlanStatus.APPROVED
        plan_store.update_metadata(metadata)
        logger.info(f"Approved plan: {repository.full_name}#{metadata.issue_number}")
        return

    if not app_config.repository_path:
        logger.error("Repository path not configured")
        logger.error("Repository path not configured. Run: gh-worker config repository-path <path>")
        return

    repo_path = app_config.repository_path / repository.owner / repository.name
    gh_client = GHClient(app_config.repository_path)

    # Ensure repository exists
    if not repo_path.exists():
        try:
            gh_client.clone_repo(repository)
            logger.info(
                "Repository cloned for review",
                repository=repository.full_name,
                path=str(repo_path),
            )
        except Exception as e:
            logger.error(
                "Repository clone failed",
                repository=repository.full_name,
                path=str(repo_path),
                error=str(e),
            )
            logger.error(f"Repository not found at {repo_path}. Clone failed: {e}")
            return

    # Use plan timestamp for deterministic worktree path (reuse existing worktree)
    plan_timestamp = metadata.created_at.strftime("%Y%m%d-%H%M%S")
    worktree_path = (
        app_config.repository_path
        / "plan-worktrees"
        / repository.owner
        / repository.name
        / f"issue-{metadata.issue_number}-{plan_timestamp}"
    )

    # Create worktree only if it doesn't exist (same as ghw issues plan)
    if not worktree_path.exists():
        try:
            gh_client.fetch_repository(repository)
            gh_client.create_planning_worktree(repository, worktree_path)
            logger.info(
                "Review plan worktree created",
                repository=repository.full_name,
                issue_number=metadata.issue_number,
                worktree_path=str(worktree_path),
            )
        except Exception as e:
            logger.error(
                "Review plan worktree failed",
                repository=repository.full_name,
                issue_number=metadata.issue_number,
                error=str(e),
            )
            logger.error(f"Failed to create worktree: {e}")
            return

    # Symlink plan into worktree (use absolute path for portability)
    plan_symlink = worktree_path / "plan.md"
    try:
        if plan_symlink.exists():
            plan_symlink.unlink()
        plan_symlink.symlink_to(plan_file.resolve())
    except OSError as e:
        logger.error(
            "Plan symlink failed",
            plan_file=str(plan_file),
            worktree_path=str(worktree_path),
            error=str(e),
        )
        logger.error(f"Failed to symlink plan: {e}")
        return

    logger.info(f"Worktree: {worktree_path}")
    logger.info(f"Plan (symlinked): {plan_symlink}")


def review_implementation_command(
    repo: str,
    issue_number: int,
    *,
    push_branch: bool = True,
    create_pr: bool = True,
    config_path: Path | None = None,
) -> None:
    """Approve an implementation waiting for review: push branch and create PR.

    For an implementation that is completed locally (no PR yet), pushes the
    branch to remote and creates a pull request.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_number: Issue number to review
        push_branch: Push branch to remote (default: True)
        create_pr: Create pull request after push (default: True)
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured")
        logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
        return

    if not app_config.repository_path:
        logger.error("Repository path not configured")
        logger.error("Repository path not configured. Run: gh-worker config repository-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    plan_store = PlanStore(app_config.issues_path)
    gh_client = GHClient(app_config.repository_path)

    try:
        repository = issue_store.resolve_repo(repo)
    except ValueError as e:
        logger.error("Invalid repository", repo=repo, error=str(e))
        logger.error(f"Error: {e}")
        return

    items = _find_implementations_waiting_review(
        repository, issue_store, plan_store, [issue_number], None
    )
    if not items:
        logger.info("No implementation waiting for review for this issue")
        return

    repo_path = app_config.repository_path / repository.owner / repository.name
    _plan_file, metadata = items[0]

    try:
        if push_branch:
            gh_client.push_branch(repository, metadata.branch_name, repo_path)
            logger.info(
                "Branch pushed",
                repository=repository.full_name,
                issue_number=metadata.issue_number,
                branch_name=metadata.branch_name,
            )

        pr_url = None
        if create_pr and push_branch:
            description_file = (
                issue_store.get_issue_dir(repository, metadata.issue_number) / "description.md"
            )
            issue_content = description_file.read_text() if description_file.exists() else ""
            body = f"Implements issue #{metadata.issue_number}\n\n{issue_content[:500]}..."
            pr_url = gh_client.create_pr(
                repository=repository,
                title=f"Implement issue #{metadata.issue_number}",
                body=body,
                head=metadata.branch_name,
            )
            metadata.pr_url = pr_url
            logger.info(
                "PR created",
                repository=repository.full_name,
                issue_number=metadata.issue_number,
                pr_url=pr_url,
            )

        plan_store.update_metadata(metadata)
        logger.info(
            f"Reviewed implementation: {repository.full_name}#{metadata.issue_number}"
            + (f" -> {pr_url}" if pr_url else "")
        )
    except Exception as e:
        logger.error(
            "Review implementation failed",
            repository=repository.full_name,
            issue_number=metadata.issue_number,
            error=str(e),
        )
        logger.error(f"Failed {repository.full_name}#{metadata.issue_number}: {e}")
