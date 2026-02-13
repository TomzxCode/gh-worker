"""Plan command implementation."""

import asyncio
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import structlog

from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.executor.parallel import ParallelExecutor
from gh_worker.github.client import GHClient
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


def _get_repo_commit_hash(repo_path: Path) -> str | None:
    """Get current HEAD commit hash if path is a git repository."""
    if not repo_path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


@dataclass
class PlanTask:
    """Task for generating a plan for an issue."""

    repository: Repository
    issue_number: int
    description_file: Path


async def generate_plan_for_issue(
    task: PlanTask,
    plan_store: PlanStore,
    issue_store: IssueStore,
    repository_path: Path | None,
    agent_name: str,
    agent_config: dict,
) -> None:
    """Generate a plan for a single issue.

    Args:
        task: PlanTask with issue information
        plan_store: PlanStore instance
        issue_store: IssueStore instance
        repository_path: Base path for cloned repositories
        agent_name: Name of agent to use
        agent_config: Agent configuration

    Raises:
        Exception: If plan generation fails
    """
    logger.info(
        "Generating plan",
        repository=task.repository.full_name,
        issue_number=task.issue_number,
        agent=agent_name,
    )

    plan_file, metadata = plan_store.start_plan_generation(task.repository, task.issue_number)
    metadata.agent = agent_name
    plan_store.update_metadata(metadata)

    try:
        # Load issue content
        issue_content = task.description_file.read_text()

        # Get agent
        registry = get_registry()
        agent = registry.get(agent_name, agent_config)

        # Validate agent environment (skip for mock agent)
        if agent_name != "mock":
            is_valid, error_msg = await agent.validate_environment()
            if not is_valid:
                logger.error(
                    "Agent environment invalid",
                    agent=agent_name,
                    error=error_msg,
                )
                raise RuntimeError(f"Agent environment validation failed: {error_msg}")

        # Determine repository path and set up worktree for planning (latest origin/main)
        repo_path = (
            repository_path / task.repository.owner / task.repository.name
            if repository_path
            else Path.cwd()
        )
        worktree_path: Path | None = None
        gh_client: GHClient | None = None

        # For non-mock agents with repository_path: clone if needed, fetch, create worktree
        if agent_name != "mock" and repository_path:
            gh_client = GHClient(repository_path)
            if not repo_path.exists():
                # Clone on-demand when repository wasn't cloned during add
                try:
                    gh_client.clone_repo(task.repository)
                    logger.info(
                        "Repository cloned for planning",
                        repository=task.repository.full_name,
                        path=str(repo_path),
                    )
                except Exception as e:
                    logger.error(
                        "Repository clone failed",
                        repository=task.repository.full_name,
                        path=repo_path,
                        error=str(e),
                    )
                    raise FileNotFoundError(
                        f"Repository not found at {repo_path}. Clone failed: {e}"
                    ) from e

            try:
                gh_client.fetch_repository(task.repository)

                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                worktree_path = (
                    repository_path
                    / "plan-worktrees"
                    / task.repository.owner
                    / task.repository.name
                    / f"issue-{task.issue_number}-{timestamp}"
                )
                repo_path = gh_client.create_planning_worktree(task.repository, worktree_path)
                logger.info(
                    "Using planning worktree",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    worktree_path=str(worktree_path),
                )
            except Exception as e:
                logger.error(
                    "Planning worktree creation failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    error=str(e),
                )
                logger.info(
                    "Falling back to direct repository",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                worktree_path = None
                gh_client = None
                repo_path = repository_path / task.repository.owner / task.repository.name

        # Skip repository path check for mock agent
        if agent_name != "mock" and not repo_path.exists():
            logger.error(
                "Repository not found",
                repository=task.repository.full_name,
                path=repo_path,
            )
            raise FileNotFoundError(f"Repository not found at {repo_path}")

        try:
            # Callback to persist session_id as soon as we get it (enables monitor during plan)
            def on_session_id(sid: str) -> None:
                metadata.session_id = sid
                plan_store.update_metadata(metadata)

            # Generate plan
            result = await agent.plan(
                issue_content=issue_content,
                repository_path=str(repo_path) if agent_name != "mock" else "",
                on_session_id=on_session_id,
            )

            if not result.success:
                logger.error(
                    "Plan generation failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    error=result.error,
                )
                raise RuntimeError(f"Plan generation failed: {result.error}")

            # Get model from agent config or agent instance (ensure string for serialization)
            model_val = agent_config.get("model") or getattr(agent, "model", None)
            model = model_val if isinstance(model_val, str) else None

            # Get repository commit hash for plan metadata
            commit_hash = _get_repo_commit_hash(repo_path)

            # Complete plan: write content and update metadata
            plan_store.complete_plan(
                plan_file,
                metadata,
                result.output,
                agent=agent_name,
                model=model,
                commit_hash=commit_hash,
                session_id=result.session_id,
            )

            logger.info(
                "Plan generated",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                agent=agent_name,
                plan_path=str(plan_file),
            )
        finally:
            # Remove planning worktree when done
            if worktree_path and gh_client:
                try:
                    gh_client.remove_worktree(task.repository, worktree_path)
                    logger.info(
                        "Planning worktree removed",
                        repository=task.repository.full_name,
                        issue_number=task.issue_number,
                        worktree_path=str(worktree_path),
                    )
                except Exception as e:
                    logger.warning(
                        "Planning worktree removal failed",
                        repository=task.repository.full_name,
                        issue_number=task.issue_number,
                        worktree_path=str(worktree_path),
                        error=str(e),
                    )
    except Exception:
        # Clean up metadata stub on failure (only .yaml was created, no .md yet)
        try:
            plan_file.with_suffix(".yaml").unlink(missing_ok=True)
        except OSError:
            pass
        raise


def find_issues_needing_plans(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None = None,
    force: bool = False,
    assignee_filter: str | None = None,
) -> list[PlanTask]:
    """Find issues that need plans generated.

    Args:
        repository: Repository to check
        issue_store: IssueStore instance
        plan_store: PlanStore instance
        issue_numbers: Optional list of specific issue numbers to check
        force: If True, generate plan even if one already exists
        assignee_filter: If set, only include issues assigned to this user (substring match)

    Returns:
        List of PlanTask objects for issues needing plans
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

        # Check if plan already exists (unless force is True)
        if not force and plan_store.has_plan(repository, issue_number):
            logger.debug(
                "Issue has plan",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        # Check if issue description exists
        issue_dir = issue_store.get_issue_dir(repository, issue_number)
        description_file = issue_dir / "description.md"

        if not description_file.exists():
            logger.warning(
                "Issue description missing",
                repository=repository.full_name,
                issue_number=issue_number,
            )
            continue

        tasks.append(
            PlanTask(
                repository=repository,
                issue_number=issue_number,
                description_file=description_file,
            )
        )

    return tasks


async def plan_command_async(
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
    """Execute plan command asynchronously.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to plan
        all_repos: Generate plans for all repositories
        parallelism: Number of parallel executions
        force: Generate plan even if one already exists
        assignee: Filter by assignee (substring match). Use @me for current user
        config_path: Path to config file
        agent: Agent to use (e.g., 'mock', 'claude-code', 'opencode', 'gemini', 'codex')
            Uses config default if None
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
    max_workers = parallelism if parallelism is not None else app_config.plan.parallelism

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

    # Find all issues needing plans
    all_tasks = []
    for repository in repositories:
        tasks = find_issues_needing_plans(
            repository,
            issue_store,
            plan_store,
            issue_numbers,
            force,
            assignee_filter,
        )
        all_tasks.extend(tasks)

    if not all_tasks:
        logger.info("No issues need plans generated")
        return

    # Get agent configuration (use override if provided, otherwise use config default)
    agent_name = agent if agent is not None else app_config.agent.default
    agent_config = {
        "claude_code_path": app_config.agent.claude_code_path,
        "opencode_path": app_config.agent.opencode_path,
        "model": model if model is not None else app_config.agent.model,
    }

    logger.info(
        "Generating plans",
        total_issues=len(all_tasks),
        agent=agent_name,
        parallelism=max_workers,
    )

    # Create task function
    async def task_func(task: PlanTask):
        return await generate_plan_for_issue(
            task,
            plan_store,
            issue_store,
            app_config.repository_path,
            agent_name,
            agent_config,
        )

    # Execute in parallel
    executor = ParallelExecutor(max_workers)
    results = await executor.execute(all_tasks, task_func, "plan_generation")

    # Report results
    successes = sum(1 for r in results if r.success)
    failures = len(results) - successes

    logger.info("Completed", successes=successes, failures=failures)

    if failures > 0:
        logger.info("Failed issues:")
        for result in results:
            if not result.success:
                logger.error(
                    "Failed issue",
                    repository=result.item.repository.full_name,
                    issue_number=result.item.issue_number,
                    error=result.error,
                )


def plan_command(
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
    """Execute plan command.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to plan
        all_repos: Generate plans for all repositories
        parallelism: Number of parallel executions
        force: Generate plan even if one already exists
        assignee: Filter by assignee (substring match). Use @me for current user
        config_path: Path to config file
        agent: Agent to use (e.g., 'mock', 'claude-code', 'opencode', 'gemini', 'codex')
            Uses config default if None
        model: Override model to use (agent-specific). Uses config default if None
    """
    asyncio.run(
        plan_command_async(
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
