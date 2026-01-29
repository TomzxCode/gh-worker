"""Plan command implementation."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import structlog

from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.executor.parallel import ParallelExecutor
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


@dataclass
class PlanTask:
    """Task for generating a plan for an issue."""

    repository: Repository
    issue_number: int
    description_file: Path


async def generate_plan_for_issue(
    task: PlanTask,
    plan_store: PlanStore,
    repository_path: Path | None,
    agent_name: str,
    agent_config: dict,
) -> None:
    """Generate a plan for a single issue.

    Args:
        task: PlanTask with issue information
        plan_store: PlanStore instance
        repository_path: Base path for cloned repositories
        agent_name: Name of agent to use
        agent_config: Agent configuration

    Raises:
        Exception: If plan generation fails
    """
    logger.info(
        "generating_plan",
        repository=task.repository.full_name,
        issue_number=task.issue_number,
    )

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
        raise FileNotFoundError(f"Repository not found at {repo_path}")

    # Generate plan
    result = await agent.plan(
        issue_content=issue_content,
        repository_path=str(repo_path),
        issue_number=task.issue_number,
    )

    if not result.success:
        logger.error(
            "plan_generation_failed",
            repository=task.repository.full_name,
            issue_number=task.issue_number,
            error=result.error,
        )
        raise RuntimeError(f"Plan generation failed: {result.error}")

    # Save plan
    plan_store.create_plan(task.repository, task.issue_number, result.output)

    logger.info(
        "plan_generated",
        repository=task.repository.full_name,
        issue_number=task.issue_number,
    )


def find_issues_needing_plans(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None = None,
) -> list[PlanTask]:
    """Find issues that need plans generated.

    Args:
        repository: Repository to check
        issue_store: IssueStore instance
        plan_store: PlanStore instance
        issue_numbers: Optional list of specific issue numbers to check

    Returns:
        List of PlanTask objects for issues needing plans
    """
    tasks = []

    if issue_numbers:
        issues_to_check = issue_numbers
    else:
        issues_to_check = issue_store.list_issues(repository)

    for issue_number in issues_to_check:
        # Check if plan already exists
        if plan_store.has_plan(repository, issue_number):
            logger.debug(
                "issue_has_plan",
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
    parallelism: int | None = None,
    config_path: Path | None = None,
) -> None:
    """Execute plan command asynchronously.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to plan
        parallelism: Number of parallel executions
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
    max_workers = parallelism if parallelism is not None else app_config.plan.parallelism

    # Determine which repositories to process
    if repo:
        repositories = [Repository.from_string(repo)]
    else:
        repositories = issue_store.list_repositories()
        if not repositories:
            logger.warning("no_repositories_found")
            print("No repositories found. Use 'gh-worker add' to add repositories.")
            return

    # Find all issues needing plans
    all_tasks = []
    for repository in repositories:
        tasks = find_issues_needing_plans(repository, issue_store, plan_store, issue_numbers)
        all_tasks.extend(tasks)

    if not all_tasks:
        logger.info("no_issues_needing_plans")
        print("No issues need plans generated")
        return

    logger.info(
        "starting_plan_generation",
        total_issues=len(all_tasks),
        parallelism=max_workers,
    )
    print(f"Generating plans for {len(all_tasks)} issues (parallelism: {max_workers})")

    # Get agent configuration
    agent_name = app_config.agent.default
    agent_config = {
        "claude_code_path": app_config.agent.claude_code_path,
    }

    # Create task function
    async def task_func(task: PlanTask):
        return await generate_plan_for_issue(
            task, plan_store, app_config.repository_path, agent_name, agent_config
        )

    # Execute in parallel
    executor = ParallelExecutor(max_workers)
    results = await executor.execute(all_tasks, task_func, "plan_generation")

    # Report results
    successes = sum(1 for r in results if r.success)
    failures = len(results) - successes

    print(f"\nCompleted: {successes} plans generated, {failures} failures")

    if failures > 0:
        print("\nFailed issues:")
        for result in results:
            if not result.success:
                print(
                    f"  - {result.item.repository.full_name}#{result.item.issue_number}: "
                    f"{result.error}"
                )


def plan_command(
    repo: str | None = None,
    issue_numbers: list[int] | None = None,
    parallelism: int | None = None,
    config_path: Path | None = None,
) -> None:
    """Execute plan command.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to plan
        parallelism: Number of parallel executions
        config_path: Path to config file
    """
    asyncio.run(
        plan_command_async(
            repo=repo,
            issue_numbers=issue_numbers,
            parallelism=parallelism,
            config_path=config_path,
        )
    )
