"""Work command implementation."""

import asyncio
from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.executor.orchestrator import WorkOrchestrator

logger = structlog.get_logger()


async def work_command_async(
    once: bool = False,
    frequency: str | None = None,
    repos: list[str] | None = None,
    since: str | None = None,
    issue_numbers: list[int] | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Execute work command asynchronously.

    Args:
        once: Run once and exit (default: continuous mode)
        frequency: Sync frequency (e.g., '10m', '1h', '1d')
        repos: Repositories to process
        since: Only process issues updated since this timestamp
        issue_numbers: Specific issue numbers to process
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
    """
    # Determine frequency
    if not once and frequency is None:
        # Load from config
        config = ConfigManager(config_path)
        app_config = config.load()
        frequency = app_config.sync.frequency

    # Create orchestrator
    orchestrator = WorkOrchestrator(
        config_path=config_path,
        repos=repos,
        since=since,
        issue_numbers=issue_numbers,
        agent=agent,
    )

    # Run in appropriate mode
    if once:
        logger.info("executing_work_once")
        await orchestrator.run_once()
    else:
        logger.info("executing_work_continuous", frequency=frequency)
        await orchestrator.run_continuous(frequency)


def work_command(
    once: bool = False,
    frequency: str | None = None,
    repos: list[str] | None = None,
    since: str | None = None,
    issue_numbers: list[int] | None = None,
    config_path: Path | None = None,
    agent: str | None = None,
) -> None:
    """Execute work command.

    Args:
        once: Run once and exit (default: continuous mode)
        frequency: Sync frequency (e.g., '10m', '1h', '1d')
        repos: Repositories to process
        since: Only process issues updated since this timestamp
        issue_numbers: Specific issue numbers to process
        config_path: Path to config file
        agent: Override agent to use (uses config default if None)
    """
    asyncio.run(
        work_command_async(
            once=once,
            frequency=frequency,
            repos=repos,
            since=since,
            issue_numbers=issue_numbers,
            config_path=config_path,
            agent=agent,
        )
    )
