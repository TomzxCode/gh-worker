"""Monitor command implementation."""

import asyncio
from pathlib import Path

import structlog

from gh_worker.agents.base import AgentEventType
from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore

logger = structlog.get_logger()


async def monitor_command_async(
    repo: str,
    issue_number: int,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Execute monitor command asynchronously.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_number: Issue number to monitor
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
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
        logger.error("Error", error=str(e))
        return

    # Get latest plan and metadata
    plan_result = plan_store.get_latest_plan(repository, issue_number)
    if not plan_result:
        logger.error(
            "No plan found",
            repository=repository.full_name,
            issue_number=issue_number,
        )
        logger.error(
            "No plan found",
            repository=repository.full_name,
            issue_number=issue_number,
        )
        return

    _, metadata = plan_result

    if not metadata.session_id:
        logger.error(
            "No session ID found. Plan or implementation may not have started yet.",
            repository=repository.full_name,
            issue_number=issue_number,
        )
        return

    logger.info(
        "Monitoring session",
        repository=repository.full_name,
        issue_number=issue_number,
        session_id=metadata.session_id,
    )

    # Get agent: override > agent that created the session (from metadata) > config default
    # Session IDs are agent-specific, so we must use the same agent that ran plan/implement
    registry = get_registry()
    agent_name = (
        agent
        if agent is not None
        else (metadata.agent if metadata.agent else app_config.agent.default)
    )
    agent_config = {
        "claude_code_path": app_config.agent.claude_code_path,
        "opencode_path": app_config.agent.opencode_path,
    }
    agent = registry.get(agent_name, agent_config)

    # Validate agent environment
    is_valid, error_msg = await agent.validate_environment()
    if not is_valid:
        logger.error(
            "Agent environment validation failed",
            agent=agent_name,
            error=error_msg,
        )
        return

    try:
        # Stream events from the agent session
        async for event in agent.monitor(metadata.session_id):
            # Format output based on event type
            if event.type == AgentEventType.OUTPUT:
                logger.info("Event output", content=event.content)
            elif event.type == AgentEventType.ERROR:
                logger.error("Event error", content=event.content)
            elif event.type == AgentEventType.STATUS:
                logger.info("Status", content=event.content)
            elif event.type == AgentEventType.TOOL_USE:
                logger.info("Tool use", content=event.content)
            elif event.type == AgentEventType.COMPLETION:
                logger.info("Completed", content=event.content)
                break
            elif event.type == AgentEventType.FAILURE:
                logger.error("Failed", content=event.content)
                break

    except KeyboardInterrupt:
        logger.info("Monitor interrupted")
        logger.info("Monitoring interrupted by user")
    except Exception as e:
        logger.error("Monitor failed", error=str(e))
        logger.error("Monitoring failed", error=str(e))


def monitor_command(
    repo: str,
    issue_number: int,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Execute monitor command.

    Args:
        repo: Repository (e.g., 'owner/repo')
        issue_number: Issue number to monitor
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
    """
    asyncio.run(
        monitor_command_async(
            repo=repo,
            issue_number=issue_number,
            config_path=config_path,
            agent=agent,
        )
    )
