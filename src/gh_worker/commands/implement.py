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
from gh_worker.github.client import GHClient
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
    use_worktree: bool = True,
    push_branch: bool = False,
    create_pr: bool = False,
    delete_worktree: bool = True,
) -> None:
    """Implement a plan for a single issue.

    Args:
        task: ImplementTask with issue information
        plan_store: PlanStore instance
        repository_path: Base path for cloned repositories
        agent_name: Name of agent to use
        agent_config: Agent configuration
        use_worktree: If True, create a git worktree for isolated implementation
        push_branch: If True, push branch to remote after implementation
        create_pr: If True, create pull request after implementation
        delete_worktree: If True, delete worktree after implementation completes

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

    # Load issue content
    issue_content = task.description_file.read_text()

    # Get agent
    registry = get_registry()
    agent = registry.get(agent_name, agent_config)

    # Update status and record agent/model in metadata
    metadata.status = PlanStatus.IN_PROGRESS
    metadata.agent = agent_name
    model_val = agent_config.get("model") or getattr(agent, "model", None)
    metadata.model = model_val if isinstance(model_val, str) else None
    plan_store.update_metadata(metadata)

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
        # Clone on-demand when repository wasn't cloned during add
        if repository_path:
            try:
                gh_client = GHClient(repository_path)
                gh_client.clone_repo(task.repository)
                logger.info(
                    "repository_cloned_for_implementation",
                    repository=task.repository.full_name,
                    path=str(repo_path),
                )
            except Exception as e:
                logger.error(
                    "repository_clone_failed",
                    repository=task.repository.full_name,
                    path=repo_path,
                    error=str(e),
                )
                metadata.status = PlanStatus.FAILED
                metadata.error_message = f"Repository not found at {repo_path}. Clone failed: {e}"
                plan_store.update_metadata(metadata)
                raise FileNotFoundError(
                    f"Repository not found at {repo_path}. Clone failed: {e}"
                ) from e
        else:
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

    # Handle worktree creation if enabled
    worktree_path: Path | None = None
    gh_client: GHClient | None = None
    actual_repo_path = repo_path

    if use_worktree:
        if not repository_path:
            logger.warning(
                "worktree_requires_repository_path",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
            )
            logger.info(
                "falling_back_to_direct_repository",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
            )
        else:
            try:
                gh_client = GHClient(repository_path)
                # Create worktree path: worktrees/owner/repo/issue-{number}-{timestamp}
                worktree_path = (
                    repository_path
                    / "worktrees"
                    / task.repository.owner
                    / task.repository.name
                    / branch_name
                )
                actual_repo_path = gh_client.create_worktree(
                    task.repository, branch_name, worktree_path
                )
                logger.info(
                    "using_worktree",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    worktree_path=str(worktree_path),
                    branch_name=branch_name,
                )
            except Exception as e:
                logger.error(
                    "worktree_creation_failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    error=str(e),
                )
                logger.info(
                    "falling_back_to_direct_repository",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                # Fall back to direct repository if worktree creation fails
                worktree_path = None
                gh_client = None
                actual_repo_path = repo_path

    # Record initial commit SHA before implementation starts
    initial_commit_sha: str | None = None
    if not gh_client:
        if repository_path:
            gh_client = GHClient(repository_path)
        else:
            # Can't track commits without repository_path
            logger.warning(
                "cannot_track_commits_no_repository_path",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
            )
    else:
        # Ensure gh_client is available (it was created for worktree)
        pass

    if gh_client:
        try:
            initial_commit_sha = gh_client.get_current_commit_sha(actual_repo_path, branch_name)
            logger.info(
                "initial_commit_recorded",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                branch_name=branch_name,
                initial_commit_sha=initial_commit_sha,
            )
        except Exception as e:
            logger.warning(
                "failed_to_record_initial_commit",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                branch_name=branch_name,
                error=str(e),
            )
            # Continue anyway - we'll try to verify commits later

    try:
        # Stream implementation events
        session_id = None
        pr_url = None

        async for event in agent.implement(
            issue_content=issue_content,
            plan_content=task.plan_content,
            repository_path=str(actual_repo_path),
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
                # Agent implementation completed, but we'll handle commit verification
                # and push/PR creation after the event loop
                logger.info(
                    "agent_implementation_completed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                break

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

        # If we finish the loop without explicit completion/failure, continue to commit step
        pass

    except Exception as e:
        metadata.status = PlanStatus.FAILED
        metadata.error_message = str(e)
        plan_store.update_metadata(metadata)
        raise

    # After agent implementation completes, ask agent for commit message and execute commit
    try:
        logger.info(
            "requesting_commit_message",
            repository=task.repository.full_name,
            issue_number=task.issue_number,
            branch_name=branch_name,
        )

        # Collect commit message from agent
        commit_message_parts = []

        async for event in agent.commit(
            repository_path=str(actual_repo_path),
            issue_number=task.issue_number,
            branch_name=branch_name,
        ):
            # Log event
            logger.debug(
                "commit_message_event",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                event_type=event.type.value,
                content=event.content[:100] if len(event.content) > 100 else event.content,
            )

            # Collect output content for commit message
            if event.type == AgentEventType.OUTPUT or event.type == AgentEventType.RESULT:
                commit_message_parts.append(event.content)

            # Check for completion or failure
            if event.type == AgentEventType.COMPLETION:
                logger.info(
                    "commit_message_received",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                break

            elif event.type == AgentEventType.FAILURE:
                error_msg = f"Failed to generate commit message: {event.content}"
                logger.error(
                    "commit_message_failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    error=event.content,
                )
                metadata.status = PlanStatus.FAILED
                metadata.error_message = error_msg
                plan_store.update_metadata(metadata)
                raise RuntimeError(error_msg)

        # Extract commit message from collected content
        commit_message = "\n".join(commit_message_parts).strip()

        if not commit_message:
            error_msg = "No commit message received from agent"
            logger.error(
                "no_commit_message",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
            )
            metadata.status = PlanStatus.FAILED
            metadata.error_message = error_msg
            plan_store.update_metadata(metadata)
            raise RuntimeError(error_msg)

        logger.info(
            "commit_message_extracted",
            repository=task.repository.full_name,
            issue_number=task.issue_number,
            message_length=len(commit_message),
        )

        # Ensure we have a GHClient for git operations
        if not gh_client:
            if repository_path:
                gh_client = GHClient(repository_path)
            else:
                error_msg = "Cannot commit without repository_path"
                logger.error(
                    "cannot_commit_no_repository_path",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                metadata.status = PlanStatus.FAILED
                metadata.error_message = error_msg
                plan_store.update_metadata(metadata)
                raise RuntimeError(error_msg)

        # Stage all changes
        try:
            gh_client.stage_all_changes(actual_repo_path)
            logger.info(
                "changes_staged",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
            )
        except Exception as e:
            error_msg = f"Failed to stage changes: {e}"
            logger.error(
                "staging_failed",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                error=str(e),
            )
            metadata.status = PlanStatus.FAILED
            metadata.error_message = error_msg
            plan_store.update_metadata(metadata)
            raise RuntimeError(error_msg) from e

        # Create commit with the generated message
        try:
            commit_sha = gh_client.create_commit(actual_repo_path, commit_message)
            logger.info(
                "commit_created",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                branch_name=branch_name,
                commit_sha=commit_sha,
            )
        except Exception as e:
            error_msg = f"Failed to create commit: {e}"
            logger.error(
                "commit_creation_failed",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                error=str(e),
            )
            metadata.status = PlanStatus.FAILED
            metadata.error_message = error_msg
            plan_store.update_metadata(metadata)
            raise RuntimeError(error_msg) from e

    except Exception as e:
        metadata.status = PlanStatus.FAILED
        metadata.error_message = str(e)
        plan_store.update_metadata(metadata)
        raise

    # After commit, verify commits and handle push/PR
    try:
        # Ensure we have a GHClient for git operations
        if not gh_client:
            if repository_path:
                gh_client = GHClient(repository_path)
            else:
                # Can't verify commits or push without repository_path
                logger.warning(
                    "cannot_verify_commits_no_repository_path",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                )
                metadata.status = PlanStatus.COMPLETED
                metadata.completed_at = datetime.now()
                if session_id:
                    metadata.session_id = session_id
                plan_store.update_metadata(metadata)
                return

        # Verify that commits were created by comparing commit SHA before and after
        if initial_commit_sha is None:
            # Fallback to old method if we couldn't record initial commit
            logger.warning(
                "using_fallback_commit_check",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                branch_name=branch_name,
            )
            repo_path_for_git_ops = repo_path
            has_commits = gh_client.has_commits_on_branch(
                task.repository, branch_name, actual_repo_path
            )
            if not has_commits:
                error_msg = (
                    f"No commits found on branch {branch_name}. "
                    "The agent was asked to commit changes but no commits were created."
                )
                logger.error(
                    "no_commits_found",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    branch_name=branch_name,
                )
                metadata.status = PlanStatus.FAILED
                metadata.error_message = error_msg
                plan_store.update_metadata(metadata)
                raise RuntimeError(error_msg)
        else:
            # Compare commit SHA before and after implementation
            try:
                current_commit_sha = gh_client.get_current_commit_sha(actual_repo_path, branch_name)
                commits_were_made = current_commit_sha != initial_commit_sha

                logger.info(
                    "commit_sha_comparison",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    branch_name=branch_name,
                    initial_commit_sha=initial_commit_sha,
                    current_commit_sha=current_commit_sha,
                    commits_were_made=commits_were_made,
                )

                if not commits_were_made:
                    error_msg = (
                        f"No commits were made during implementation. "
                        f"Branch {branch_name} is still at commit {initial_commit_sha[:8]}. "
                        "The agent was asked to commit changes but no commits were created."
                    )
                    logger.error(
                        "no_commits_made",
                        repository=task.repository.full_name,
                        issue_number=task.issue_number,
                        branch_name=branch_name,
                        initial_commit_sha=initial_commit_sha,
                        current_commit_sha=current_commit_sha,
                    )
                    metadata.status = PlanStatus.FAILED
                    metadata.error_message = error_msg
                    plan_store.update_metadata(metadata)
                    raise RuntimeError(error_msg)
            except Exception as e:
                logger.error(
                    "failed_to_verify_commits",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    branch_name=branch_name,
                    error=str(e),
                )
                # If we can't verify commits, fail the implementation
                error_msg = f"Failed to verify commits were created: {e}"
                metadata.status = PlanStatus.FAILED
                metadata.error_message = error_msg
                plan_store.update_metadata(metadata)
                raise RuntimeError(error_msg) from e

        repo_path_for_git_ops = repo_path

        logger.info(
            "commits_verified",
            repository=task.repository.full_name,
            issue_number=task.issue_number,
            branch_name=branch_name,
        )

        # Push branch if enabled
        push_succeeded = False
        if push_branch:
            try:
                # Push from the main repo path (branches are tracked there)
                gh_client.push_branch(task.repository, branch_name, repo_path_for_git_ops)
                push_succeeded = True
                logger.info(
                    "branch_pushed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    branch_name=branch_name,
                )
            except Exception as push_error:
                error_msg = f"Failed to push branch: {push_error}"
                logger.error(
                    "branch_push_failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    branch_name=branch_name,
                    error=str(push_error),
                )
                # Don't fail the whole implementation if push fails, but log it
                metadata.error_message = f"Implementation completed but push failed: {push_error}"

        # Create PR if enabled
        if create_pr:
            # Only create PR if branch was successfully pushed (PR creation requires remote branch)
            if push_succeeded:
                try:
                    pr_url = gh_client.create_pr(
                        repository=task.repository,
                        title=f"Implement issue #{task.issue_number}",
                        body=f"Implements issue #{task.issue_number}\n\n{issue_content[:500]}...",
                        head=branch_name,
                    )
                    logger.info(
                        "pr_created",
                        repository=task.repository.full_name,
                        issue_number=task.issue_number,
                        branch_name=branch_name,
                        pr_url=pr_url,
                    )
                except Exception as pr_error:
                    error_msg = f"Failed to create PR: {pr_error}"
                    logger.error(
                        "pr_creation_failed",
                        repository=task.repository.full_name,
                        issue_number=task.issue_number,
                        branch_name=branch_name,
                        error=str(pr_error),
                    )
                    # Don't fail the whole implementation if PR creation fails
                    if not metadata.error_message:
                        metadata.error_message = (
                            f"Implementation completed but PR creation failed: {pr_error}"
                        )
            else:
                logger.info(
                    "pr_creation_skipped_branch_not_pushed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    branch_name=branch_name,
                )

        # Mark as completed
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

    except Exception as e:
        # If commit verification or push/PR creation fails, mark as failed
        metadata.status = PlanStatus.FAILED
        metadata.error_message = str(e)
        plan_store.update_metadata(metadata)
        raise
    finally:
        # Clean up worktree if it was created and deletion is enabled
        if worktree_path and gh_client and delete_worktree:
            try:
                gh_client.remove_worktree(task.repository, worktree_path)
                logger.info(
                    "worktree_cleaned_up",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    worktree_path=str(worktree_path),
                )
            except Exception as cleanup_error:
                logger.warning(
                    "worktree_cleanup_failed",
                    repository=task.repository.full_name,
                    issue_number=task.issue_number,
                    worktree_path=str(worktree_path),
                    error=str(cleanup_error),
                )
        elif worktree_path and not delete_worktree:
            logger.info(
                "worktree_preserved",
                repository=task.repository.full_name,
                issue_number=task.issue_number,
                worktree_path=str(worktree_path),
            )


def find_issues_needing_implementation(
    repository: Repository,
    issue_store: IssueStore,
    plan_store: PlanStore,
    issue_numbers: list[int] | None = None,
    force: bool = False,
    assignee_filter: str | None = None,
    require_approved: bool = True,
) -> list[ImplementTask]:
    """Find issues that need implementation.

    Args:
        repository: Repository to check
        issue_store: IssueStore instance
        plan_store: PlanStore instance
        issue_numbers: Optional list of specific issue numbers to check
        force: If True, implement even if already completed
        assignee_filter: If set, only include issues assigned to this user (substring match)

    Returns:
        List of ImplementTask objects for issues needing implementation
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
                    "issue_not_assigned_to_filter",
                    repository=repository.full_name,
                    issue_number=issue_number,
                )
                continue

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

        # Skip if plan not approved (unless force is True)
        # Allow IN_PROGRESS and FAILED when explicitly requested (issue_numbers) for retry/continue
        if require_approved and metadata.status == PlanStatus.PENDING:
            logger.debug(
                "plan_not_approved",
                repository=repository.full_name,
                issue_number=issue_number,
                status=metadata.status.value,
            )
            continue

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
    assignee: str | None = None,
    use_worktree: bool | None = None,
    push_branch: bool | None = None,
    create_pr: bool | None = None,
    delete_worktree: bool | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Execute implement command asynchronously.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to implement
        all_repos: Implement plans for all repositories
        parallelism: Number of parallel executions
        force: Implement even if already completed
        assignee: Filter by assignee (substring match). Use @me for current user
        use_worktree: Override worktree usage (uses config default if None)
        push_branch: Override push branch setting (uses config default if None)
        create_pr: Override create PR setting (uses config default if None)
        delete_worktree: Override delete worktree setting (uses config default if None)
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("issues_path_not_configured")
        print("Error: issues-path not configured. Run: gh-worker config issues-path <path>")
        return

    assignee_filter = assignee
    if assignee == "@me":
        gh_client = GHClient(app_config.repository_path)
        if not gh_client.check_auth():
            logger.error("gh_not_authenticated")
            print("Error: gh CLI not authenticated. Run: gh auth login")
            return
        current_user = gh_client.get_current_user()
        if not current_user:
            logger.error("could_not_get_current_user")
            print("Error: Could not determine current user. Run: gh auth login")
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
            logger.warning("no_repositories_found")
            print("No repositories found. Use 'gh-worker repositories add' to add repositories.")
            return
    elif repo:
        try:
            repositories = [issue_store.resolve_repo(repo)]
        except ValueError as e:
            logger.error("invalid_repository", repo=repo, error=str(e))
            print(f"Error: {e}")
            return
    else:
        logger.error("no_repository_specified")
        print("Error: Specify --repo or --all-repos")
        return

    # Find all issues needing implementation (require approved plans unless force)
    all_tasks = []
    for repository in repositories:
        tasks = find_issues_needing_implementation(
            repository,
            issue_store,
            plan_store,
            issue_numbers,
            force,
            assignee_filter,
            require_approved=not force,
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

    # Get agent configuration (use override if provided, otherwise use config default)
    agent_name = agent if agent is not None else app_config.agent.default
    agent_config = {
        "claude_code_path": app_config.agent.claude_code_path,
        "opencode_path": app_config.agent.opencode_path,
    }

    # Determine settings (CLI override > config > default)
    use_worktree_flag = (
        use_worktree if use_worktree is not None else app_config.implement.use_worktree
    )
    push_branch_flag = push_branch if push_branch is not None else app_config.implement.push_branch
    create_pr_flag = create_pr if create_pr is not None else app_config.implement.create_pr
    delete_worktree_flag = (
        delete_worktree if delete_worktree is not None else app_config.implement.delete_worktree
    )

    # Create task function
    async def task_func(task: ImplementTask):
        return await implement_issue(
            task,
            plan_store,
            app_config.repository_path,
            agent_name,
            agent_config,
            use_worktree=use_worktree_flag,
            push_branch=push_branch_flag,
            create_pr=create_pr_flag,
            delete_worktree=delete_worktree_flag,
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
    assignee: str | None = None,
    use_worktree: bool | None = None,
    push_branch: bool | None = None,
    create_pr: bool | None = None,
    delete_worktree: bool | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Execute implement command.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_numbers: Specific issue numbers to implement
        all_repos: Implement plans for all repositories
        parallelism: Number of parallel executions
        force: Implement even if already completed
        assignee: Filter by assignee (substring match). Use @me for current user
        use_worktree: Override worktree usage (uses config default if None)
        push_branch: Override push branch setting (uses config default if None)
        create_pr: Override create PR setting (uses config default if None)
        delete_worktree: Override delete worktree setting (uses config default if None)
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
    """
    asyncio.run(
        implement_command_async(
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
            config_path=config_path,
            agent=agent,
        )
    )
