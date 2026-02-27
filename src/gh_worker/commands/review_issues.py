"""Review issues command implementation - review code implementations."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import structlog

from gh_worker.agents.base import AgentEventType
from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.executor.parallel import ParallelExecutor
from gh_worker.github.client import GHClient
from gh_worker.models.plan import PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


@dataclass
class ReviewTask:
    """Task for reviewing an implementation."""

    repository: Repository
    issue_number: int
    plan_file: Path
    plan_content: str
    description_file: Path
    branch_name: str
    implementation_path: Path


async def review_issue(
    task: ReviewTask,
    plan_store: PlanStore,
    issue_store: IssueStore,
    repository_path: Path | None,
    agent_name: str,
    agent_config: dict,
) -> None:
    """Review a single implementation.

    Args:
        task: ReviewTask with issue information
        plan_store: PlanStore instance
        issue_store: IssueStore instance
        repository_path: Base path for cloned repositories
        agent_name: Name of agent to use
        agent_config: Agent configuration

    Raises:
        Exception: If review fails
    """
    logger.info(
        "Reviewing issue",
        repository=task.repository.full_name,
        issue_number=task.issue_number,
    )

    # Load plan metadata (optional)
    plan_result = plan_store.get_latest_plan(task.repository, task.issue_number)
    metadata = None
    if plan_result:
        _, metadata = plan_result

    # Load issue content
    issue_content = task.description_file.read_text()

    # Get agent
    registry = get_registry()
    agent = registry.get(agent_name, agent_config)

    # Update status and record agent/model in metadata (if plan exists)
    if metadata:
        metadata.status = PlanStatus.REVIEW_IN_PROGRESS
        metadata.agent = agent_name
        model_val = agent_config.get("model") or getattr(agent, "model", None)
        metadata.model = model_val if isinstance(model_val, str) else None
        plan_store.update_metadata(metadata)

    # Validate agent environment
    is_valid, error_msg = await agent.validate_environment()
    if not is_valid:
        logger.error(
            "Agent environment invalid",
            agent=agent_name,
            error=error_msg,
        )
        if metadata:
            metadata.status = PlanStatus.REVIEW_FAILED
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
            "Repository not found",
            repository=task.repository.full_name,
            path=repo_path,
        )
        metadata.status = PlanStatus.REVIEW_FAILED
        metadata.error_message = f"Repository not found at {repo_path}"
        plan_store.update_metadata(metadata)
        raise FileNotFoundError(f"Repository not found at {repo_path}")

    try:
        # Stream review events
        session_id = None
        completion_content = ""

        async for event in agent.review(
            issue_content=issue_content,
            plan_content=task.plan_content,
            repository_path=str(task.implementation_path),
            issue_number=task.issue_number,
            branch_name=task.branch_name,
        ):
            # Log event
            logger.debug(
                "Review event",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                event_type=event.type.value,
                content=event.content,
            )

            # Extract session ID if present
            if event.metadata and "session_id" in event.metadata:
                session_id = event.metadata["session_id"]

            # Check for completion or failure
            if event.type == AgentEventType.COMPLETION:
                completion_content = event.content or ""
                logger.info(
                    "Agent review completed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                break

            elif event.type == AgentEventType.FAILURE:
                if metadata:
                    metadata.status = PlanStatus.REVIEW_FAILED
                    metadata.error_message = event.content
                    plan_store.update_metadata(metadata)

                logger.error(
                    "Review failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    error=event.content,
                )
                raise RuntimeError(f"Review failed: {event.content}")

        # Mark review as completed (if plan exists)
        if metadata:
            metadata.status = PlanStatus.REVIEW_COMPLETED
            if session_id:
                metadata.session_id = session_id
            plan_store.update_metadata(metadata)

        # Write review outcome to review.md
        issue_dir = issue_store.get_issue_dir(task.repository, task.issue_number)
        review_file = issue_dir / "review.md"
        review_file.write_text(completion_content)
        logger.info(
            "Review outcome written to file",
            repository=task.repository.full_name,
            issue_number=task.issue_number,
            review_file=str(review_file),
        )

    except Exception as e:
        if metadata:
            metadata.status = PlanStatus.REVIEW_FAILED
            metadata.error_message = str(e)
            plan_store.update_metadata(metadata)
        raise


def find_implementations_waiting_review(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None = None,
    force: bool = False,
    assignee_filter: str | None = None,
) -> list[ReviewTask]:
    """Find implementations that need review.

    Args:
        repository: Repository to check
        issue_store: IssueStore instance
        plan_store: PlanStore instance
        issue_numbers: Optional list of specific issue numbers to check
        force: If True, review even if already reviewed
        assignee_filter: If set, only include issues assigned to this user (substring match)

    Returns:
        List of ReviewTask objects for implementations needing review
    """
    tasks = []

    if issue_numbers:
        issues_to_check = issue_numbers
    else:
        issues_to_check = issue_store.list_issues(repository)

    for issue_number in issues_to_check:
        # Filter by assignee when assignee_filter is set
        if assignee_filter:
            assignees = issue_store.get_issue_assignees(repository, issue_number)
            assignees_str = ",".join(assignees).lower()
            if assignee_filter.lower() not in assignees_str:
                logger.debug(
                    "Issue not assigned to filter",
                    repository=repository.full_name,
                    issue_number=issue_number,
                )
                continue

        # Check if plan exists - if so, use plan metadata
        plan_result = plan_store.get_latest_plan(repository, issue_number)
        branch_name: str | None = None
        plan_content = ""
        plan_file: Path | None = None
        metadata = None

        if plan_result:
            plan_file, metadata = plan_result

            # Skip if already reviewed (unless force is True)
            if not force and metadata.status in (
                PlanStatus.REVIEW_COMPLETED,
                PlanStatus.REVIEW_IN_PROGRESS,
            ):
                logger.debug(
                    "Implementation already reviewed or in review",
                    repository=repository.full_name,
                    issue_number=issue_number,
                )
                continue

            # Get branch name from metadata if available
            if metadata.branch_name:
                branch_name = metadata.branch_name

            # Load plan content if available
            if plan_file.exists():
                plan_content = plan_file.read_text()

        # If no branch name from plan, try to get from GitHub PR
        # Also get PR description for use as plan content if no plan exists
        if not branch_name:
            from gh_worker.github.client import GHClient

            gh_client = GHClient()
            try:
                pr_info = gh_client._run_command(
                    [
                        "pr",
                        "view",
                        str(issue_number),
                        "--repo",
                        repository.full_name,
                        "--json",
                        "headRefName,title,body",
                    ],
                )
                if pr_info.strip():
                    import json

                    pr_data = json.loads(pr_info)
                    branch_name = pr_data.get("headRefName")
                    # If no plan content exists, use PR title and body as plan
                    if not plan_content:
                        pr_title = pr_data.get("title", "")
                        pr_body = pr_data.get("body", "")
                        plan_content = f"# {pr_title}\n\n{pr_body}"
                    logger.debug(
                        "Found PR from GitHub",
                        repository=repository.full_name,
                        issue_number=issue_number,
                        branch_name=branch_name,
                    )
            except Exception as e:
                logger.debug(
                    "Failed to get PR from GitHub",
                    repository=repository.full_name,
                    issue_number=issue_number,
                    error=str(e),
                )

        # Still no branch name - skip this issue
        if not branch_name:
            logger.debug(
                "No branch name found for review",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Get or create description file
        issue_dir = issue_store.get_issue_dir(repository, issue_number)
        description_file = issue_dir / "description.md"

        # If description file doesn't exist and we got PR info, create it
        if not description_file.exists() and plan_content:
            description_file.parent.mkdir(parents=True, exist_ok=True)
            description_file.write_text(plan_content)
            logger.debug(
                "Created description file from PR info",
                repository=repository.full_name,
                issue_number=issue_number,
            )

        # If still no description file, skip this issue
        if not description_file.exists():
            logger.debug(
                "No description file found for review",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue
            from gh_worker.github.client import GHClient

            gh_client = GHClient()
            try:
                pr_info = gh_client._run_command(
                    [
                        "pr",
                        "view",
                        str(issue_number),
                        "--repo",
                        repository.full_name,
                        "--json",
                        "headRefName,title,body",
                    ],
                )
                if pr_info.strip():
                    import json

                    pr_data = json.loads(pr_info)
                    branch_name = pr_data.get("headRefName")
                    # If no plan content exists, use PR title and body as plan
                    if not plan_content:
                        pr_title = pr_data.get("title", "")
                        pr_body = pr_data.get("body", "")
                        plan_content = f"# {pr_title}\n\n{pr_body}"
                    logger.debug(
                        "Found PR from GitHub",
                        repository=repository.full_name,
                        issue_number=issue_number,
                        branch_name=branch_name,
                    )
            except Exception as e:
                logger.debug(
                    "Failed to get PR from GitHub",
                    repository=repository.full_name,
                    issue_number=issue_number,
                    error=str(e),
                )

        # Still no branch name - skip this issue
        if not branch_name:
            logger.debug(
                "No branch name found for review",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Determine implementation path (create worktree if needed)
        from gh_worker.config.manager import ConfigManager
        from gh_worker.github.client import GHClient

        config = ConfigManager()
        app_config = config.load()

        if not app_config.repository_path:
            logger.warning(
                "Repository path not configured",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Try worktree path first
        worktree_path = (
            app_config.repository_path
            / "worktrees"
            / repository.owner
            / repository.name
            / branch_name
        )

        if worktree_path.exists():
            implementation_path = worktree_path
        else:
            # Worktree doesn't exist, need to create it
            repo_path = app_config.repository_path / repository.owner / repository.name
            if not repo_path.exists():
                # Repository doesn't exist, need to clone it
                gh_client = GHClient(app_config.repository_path)
                try:
                    gh_client.clone_repo(repository)
                    logger.info(
                        "Repository cloned for review",
                        repository=repository.full_name,
                        issue_number=issue_number,
                        repo_path=str(repo_path),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to clone repository for review",
                        repository=repository.full_name,
                        issue_number=issue_number,
                        error=str(e),
                    )
                    continue

            gh_client = GHClient(app_config.repository_path)
            try:
                # Fetch the PR ref specifically to get the branch
                gh_client.fetch_pr_ref(repository, issue_number, branch_name)
                # Create worktree for the PR branch
                implementation_path = gh_client.create_worktree(
                    repository, branch_name, worktree_path
                )
                logger.info(
                    "Created worktree for review",
                    repository=repository.full_name,
                    issue_number=issue_number,
                    branch_name=branch_name,
                    worktree_path=str(worktree_path),
                )
            except Exception as e:
                logger.warning(
                    "Failed to create worktree for review",
                    repository=repository.full_name,
                    issue_number=issue_number,
                    branch_name=branch_name,
                    error=str(e),
                )
                continue

        tasks.append(
            ReviewTask(
                repository=repository,
                issue_number=issue_number,
                plan_file=plan_file or description_file,  # Fallback to description if no plan
                plan_content=plan_content,
                description_file=description_file,
                branch_name=branch_name,
                implementation_path=implementation_path,
            )
        )

    return tasks


async def review_command_async(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    all_repos: bool = False,
    parallelism: int | None = None,
    force: bool = False,
    assignee: str | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
) -> None:
    """Execute review command asynchronously.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to review
        all_repos: Review implementations for all repositories
        parallelism: Number of parallel executions
        force: Review even if already reviewed
        assignee: Filter by assignee (substring match). Use @me for current user
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
        model: Override model to use (agent-specific). Uses config default if None
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
        return

    assignee_filter = assignee
    if assignee == "@me":
        gh_client = GHClient(app_config.repository_path)
        if not gh_client.check_auth():
            logger.error("gh CLI not authenticated. Run: gh auth login")
            return
        current_user = gh_client.get_current_user()
        if not current_user:
            logger.error("Could not determine current user. Run: gh auth login")
            return
        assignee_filter = current_user

    issue_store = IssueStore(app_config.issues_path)
    plan_store = PlanStore(app_config.issues_path)

    # Determine parallelism
    max_workers = parallelism if parallelism is not None else app_config.implement.parallelism

    # Determine which repositories to process
    if all_repos:
        repositories = issue_store.list_repositories()
        if not repositories:
            logger.warning(
                "No repositories found. Use 'gh-worker repositories add' to add repositories."
            )
            return
    elif repo:
        try:
            repositories = [issue_store.resolve_repo(repo)]
        except ValueError as e:
            logger.error("Invalid repository", repo=repo, error=str(e))
            return
    else:
        logger.error("Specify --repo or --all-repos")
        return

    # Find all implementations needing review
    all_tasks = []
    for repository in repositories:
        tasks = find_implementations_waiting_review(
            repository,
            issue_store,
            plan_store,
            issue_numbers,
            force,
            assignee_filter,
        )
        all_tasks.extend(tasks)

    if not all_tasks:
        logger.info("No implementations need review")
        return

    logger.info(
        "Reviewing implementations",
        total_issues=len(all_tasks),
        parallelism=max_workers,
    )

    # Agent config: CLI override > review.agent/model > implement.agent/model > agent.default/model
    agent_name = (
        agent
        if agent is not None
        else (
            app_config.implement.agent if app_config.implement.agent else app_config.agent.default
        )
    )
    model_val = (
        model
        if model is not None
        else (
            app_config.implement.model
            if app_config.implement.model is not None
            else app_config.agent.model
        )
    )
    agent_config = {
        "claude_code_path": app_config.agent.claude_code_path,
        "opencode_path": app_config.agent.opencode_path,
        "model": model_val,
    }

    # Create task function
    async def task_func(task: ReviewTask):
        return await review_issue(
            task,
            plan_store,
            issue_store,
            app_config.repository_path,
            agent_name,
            agent_config,
        )

    # Execute in parallel
    executor = ParallelExecutor(max_workers)
    results = await executor.execute(all_tasks, task_func, "review")

    # Report results
    successes = sum(1 for r in results if r.success)
    failures = len(results) - successes

    logger.info("Completed", successes=successes, failures=failures)

    if failures > 0:
        logger.info("Failed reviews:")
        for result in results:
            if not result.success:
                logger.error(
                    "Failed review",
                    repository=result.item.repository.full_name,
                    issue_number=result.item.issue_number,
                    error=result.error,
                )


def review_command(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    all_repos: bool = False,
    parallelism: int | None = None,
    force: bool = False,
    assignee: str | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
) -> None:
    """Execute review command.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to review
        all_repos: Review implementations for all repositories
        parallelism: Number of parallel executions
        force: Review even if already reviewed
        assignee: Filter by assignee (substring match). Use @me for current user
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
        model: Override model to use (agent-specific). Uses config default if None
    """
    asyncio.run(
        review_command_async(
            repo=repo,
            issue_numbers=issue_numbers,
            all_repos=all_repos,
            parallelism=parallelism,
            force=force,
            assignee=assignee,
            config_path=config_path,
            agent=agent,
            model=model,
        )
    )
