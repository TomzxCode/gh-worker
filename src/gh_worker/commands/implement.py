"""Implement command implementation."""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import structlog

from gh_worker.agents.base import AgentEventType
from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.executor.parallel import ParallelExecutor
from gh_worker.models.plan import PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


@dataclass
class ImplementTask:
    """Task for implementing a plan for an issue."""

    repository: Repository
    issue_number: int
    plan_file: Path
    plan_content: str
    description_file: Path


async def implement_issue(
    task: ImplementTask,
    plan_store: PlanStore,
    repository_path: Path | None,
    agent_name: str,
    agent_config: dict,
) -> None:
    """Implement a plan for a single issue.

    Args:
        task: ImplementTask with issue information
        plan_store: PlanStore instance
        repository_path: Base path for cloned repositories
        agent_name: Name of agent to use
        agent_config: Agent configuration

    Raises:
        Exception: If implementation fails
    """
    logger.info(
        "implementing_issue",
        repository=task.repository.full_name,
        issue_number=task.issue_number,
    )

    # Load plan metadata
    plan_result = plan_store.get_latest_plan(task.repository, task.issue_number)
    if not plan_result:
        raise RuntimeError("Plan not found")

    _, metadata = plan_result

    # Update status to in_progress
    metadata.status = PlanStatus.IN_PROGRESS
    plan_store.update_metadata(metadata)

    # Load issue content
    issue_content = task.description_file.read_text()

    # Get agent
    registry = get_registry()
    agent = registry.get(agent_name, agent_config)

    # Validate agent environment
    is_valid, error_msg = await agent.validate_environment()
    if not is_valid:
        logger.error(
            "agent_environment_invalid",
            agent=agent_name,
            error=error_msg,
        )
        metadata.status = PlanStatus.FAILED
        metadata.error_message = f"Agent environment validation failed: {error_msg}"
        plan_store.update_metadata(metadata)
        raise RuntimeError(f"Agent environment validation failed: {error_msg}")

    # Determine repository path
    if repository_path:
        repo_path = repository_path / task.repository.owner / task.repository.name
    else:
        repo_path = Path.cwd()

    if not repo_path.exists():
        logger.error(
            "repository_not_found",
            repository=task.repository.full_name,
            path=repo_path,
        )
        metadata.status = PlanStatus.FAILED
        metadata.error_message = f"Repository not found at {repo_path}"
        plan_store.update_metadata(metadata)
        raise FileNotFoundError(f"Repository not found at {repo_path}")

    # Create branch name with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"issue-{task.issue_number}-{timestamp}"
    metadata.branch_name = branch_name

    try:
        # Stream implementation events
        session_id = None
        pr_url = None

        async for event in agent.implement(
            issue_content=issue_content,
            plan_content=task.plan_content,
            repository_path=str(repo_path),
            issue_number=task.issue_number,
            branch_name=branch_name,
        ):
            # Log event
            logger.debug(
                "implementation_event",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                event_type=event.type.value,
                content=event.content[:100] if len(event.content) > 100 else event.content,
            )

            # Extract session ID if present
            if event.metadata and "session_id" in event.metadata:
                session_id = event.metadata["session_id"]

            # Extract PR URL if present
            if event.metadata and "pr_url" in event.metadata:
                pr_url = event.metadata["pr_url"]
            elif event.type == AgentEventType.OUTPUT:
                # Try to extract PR URL from content
                url_match = re.search(r"https://github\.com/[^/]+/[^/]+/pull/\d+", event.content)
                if url_match:
                    pr_url = url_match.group(0)

            # Check for completion or failure
            if event.type == AgentEventType.COMPLETION:
                metadata.status = PlanStatus.COMPLETED
                metadata.completed_at = datetime.now()
                if session_id:
                    metadata.session_id = session_id
                if pr_url:
                    metadata.pr_url = pr_url
                plan_store.update_metadata(metadata)

                logger.info(
                    "implementation_completed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    pr_url=pr_url,
                )
                return

            elif event.type == AgentEventType.FAILURE:
                metadata.status = PlanStatus.FAILED
                metadata.error_message = event.content
                plan_store.update_metadata(metadata)

                logger.error(
                    "implementation_failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    error=event.content,
                )
                raise RuntimeError(f"Implementation failed: {event.content}")

        # If we finish the loop without explicit completion/failure, mark as completed
        metadata.status = PlanStatus.COMPLETED
        metadata.completed_at = datetime.now()
        if session_id:
            metadata.session_id = session_id
        if pr_url:
            metadata.pr_url = pr_url
        plan_store.update_metadata(metadata)

        logger.info(
            "implementation_completed",
            repository=task.repository.full_name,
            issue_number=task.issue_number,
        )

    except Exception as e:
        metadata.status = PlanStatus.FAILED
        metadata.error_message = str(e)
        plan_store.update_metadata(metadata)
        raise


def find_issues_needing_implementation(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None = None,
    force: bool = False,
) -> list[ImplementTask]:
    """Find issues that need implementation.

    Args:
        repository: Repository to check
        issue_store: IssueStore instance
        plan_store: PlanStore instance
        issue_numbers: Optional list of specific issue numbers to check
        force: If True, implement even if already completed

    Returns:
        List of ImplementTask objects for issues needing implementation
    """
    tasks = []

    if issue_numbers:
        issues_to_check = issue_numbers
    else:
        issues_to_check = issue_store.list_issues(repository)

    for issue_number in issues_to_check:
        # Check if plan exists
        plan_result = plan_store.get_latest_plan(repository, issue_number)
        if not plan_result:
            logger.debug(
                "issue_has_no_plan",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        plan_file, metadata = plan_result

        # Skip if already completed (unless force is True)
        if not force and metadata.status == PlanStatus.COMPLETED:
            logger.debug(
                "issue_already_implemented",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Skip if currently in progress (unless explicitly requested)
        if metadata.status == PlanStatus.IN_PROGRESS and issue_numbers is None:
            logger.debug(
                "issue_in_progress",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Check if issue description exists
        issue_dir = issue_store.get_issue_dir(repository, issue_number)
        description_file = issue_dir / "description.md"

        if not description_file.exists():
            logger.warning(
                "issue_description_missing",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Load plan content
        plan_content = plan_file.read_text()

        tasks.append(
            ImplementTask(
                repository=repository,
                issue_number=issue_number,
                plan_file=plan_file,
                plan_content=plan_content,
                description_file=description_file,
            )
        )

    return tasks


async def implement_command_async(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    all_repos: bool = False,
    parallelism: int | None = None,
    force: bool = False,
    config_path: Path | None = None,
) -> None:
    """Execute implement command asynchronously.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to implement
        all_repos: Implement plans for all repositories
        parallelism: Number of parallel executions
        force: Implement even if already completed
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("issues_path_not_configured")
        print("Error: issues-path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    plan_store = PlanStore(app_config.issues_path)

    # Determine parallelism
    max_workers = parallelism if parallelism is not None else app_config.implement.parallelism

    # Determine which repositories to process
    if all_repos:
        repositories = issue_store.list_repositories()
        if not repositories:
            logger.warning("no_repositories_found")
            print("No repositories found. Use 'gh-worker add' to add repositories.")
            return
    elif repo:
        repositories = [Repository.from_string(repo)]
    else:
        logger.error("no_repository_specified")
        print("Error: Specify --repo or --all-repos")
        return

    # Find all issues needing implementation
    all_tasks = []
    for repository in repositories:
        tasks = find_issues_needing_implementation(
            repository, issue_store, plan_store, issue_numbers, force
        )
        all_tasks.extend(tasks)

    if not all_tasks:
        logger.info("no_issues_needing_implementation")
        print("No issues need implementation")
        return

    logger.info(
        "starting_implementation",
        total_issues=len(all_tasks),
        parallelism=max_workers,
    )
    print(f"Implementing {len(all_tasks)} issues (parallelism: {max_workers})")

    # Get agent configuration
    agent_name = app_config.agent.default
    agent_config = {
        "claude_code_path": app_config.agent.claude_code_path,
    }

    # Create task function
    async def task_func(task: ImplementTask):
        return await implement_issue(
            task, plan_store, app_config.repository_path, agent_name, agent_config
        )

    # Execute in parallel
    executor = ParallelExecutor(max_workers)
    results = await executor.execute(all_tasks, task_func, "implementation")

    # Report results
    successes = sum(1 for r in results if r.success)
    failures = len(results) - successes

    print(f"\nCompleted: {successes} implementations successful, {failures} failures")

    if failures > 0:
        print("\nFailed issues:")
        for result in results:
            if not result.success:
                print(
                    f"  - {result.item.repository.full_name}#{result.item.issue_number}: "
                    f"{result.error}"
                )


def implement_command(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    all_repos: bool = False,
    parallelism: int | None = None,
    force: bool = False,
    config_path: Path | None = None,
) -> None:
    """Execute implement command.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to implement
        all_repos: Implement plans for all repositories
        parallelism: Number of parallel executions
        force: Implement even if already completed
        config_path: Path to config file
    """
    asyncio.run(
        implement_command_async(
            repo=repo,
            issue_numbers=issue_numbers,
            all_repos=all_repos,
            parallelism=parallelism,
            force=force,
            config_path=config_path,
        )
    )
