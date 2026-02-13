"""Work orchestrator for running sync -> plan -> implement cycles."""

import asyncio
from datetime import datetime
from pathlib import Path

import structlog

from gh_worker.commands.implement import implement_command_async
from gh_worker.commands.issues_list import issues_list_command
from gh_worker.commands.plan import plan_command_async
from gh_worker.commands.sync import sync_command
from gh_worker.config.manager import ConfigManager
from gh_worker.utils.time import parse_duration

logger = structlog.get_logger()


class WorkOrchestrator:
    """Orchestrates sync -> plan -> implement workflow cycles."""

    def __init__(
        self,
        config_path: Path | None = None,
        repos: list[str] | None = None,
        since: str | None = None,
        issue_numbers: list[int] | None = None,
        agent: str | None = None,
    ):
        """Initialize WorkOrchestrator.

        Args:
            config_path: Path to config file
            repos: List of repositories to process
            since: Only process issues updated since this timestamp
            issue_numbers: Specific issue numbers to process
            agent: Override agent to use (uses config default if None)
        """
        self.config_path = config_path
        self.repos = repos
        self.since = since
        self.issue_numbers = issue_numbers
        self.agent = agent
        self.config_manager = ConfigManager(config_path)

    async def run_cycle(self) -> None:
        """Run a single sync -> plan -> implement cycle.

        Raises:
            Exception: If any phase of the cycle fails
        """
        logger.info("Starting work cycle")

        # Load configuration
        app_config = self.config_manager.load()

        if not app_config.issues_path:
            logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
            return

        # Phase 1: Sync
        logger.info("Work cycle phase", phase="sync")
        if self.repos:
            for repo in self.repos:
                sync_command(
                    repo=repo,
                    all_repos=False,
                    since=self.since,
                    issue_numbers=self.issue_numbers,
                    search=None,
                    config_path=self.config_path,
                )
        else:
            sync_command(
                repo=None,
                all_repos=True,
                since=self.since,
                issue_numbers=self.issue_numbers,
                search=None,
                config_path=self.config_path,
            )

        # Phase 2: List issues (show what we're working on)
        logger.info("Work cycle phase", phase="list")
        if self.repos:
            for repo in self.repos:
                issues_list_command(
                    repo=repo,
                    all_repos=False,
                    issue_numbers=self.issue_numbers,
                    config_path=self.config_path,
                )
        else:
            issues_list_command(
                repo=None,
                all_repos=True,
                issue_numbers=self.issue_numbers,
                config_path=self.config_path,
            )

        # Phase 3: Plan
        logger.info("Work cycle phase", phase="plan")
        if self.repos:
            for repo in self.repos:
                await plan_command_async(
                    repo=repo,
                    issue_numbers=self.issue_numbers,
                    all_repos=False,
                    parallelism=None,  # Use config default
                    force=False,
                    config_path=self.config_path,
                    agent=self.agent,
                )
        else:
            await plan_command_async(
                repo=None,
                issue_numbers=self.issue_numbers,
                all_repos=True,
                parallelism=None,  # Use config default
                force=False,
                config_path=self.config_path,
                agent=self.agent,
            )

        # Phase 4: Implement
        logger.info("Work cycle phase", phase="implement")
        if self.repos:
            for repo in self.repos:
                await implement_command_async(
                    repo=repo,
                    issue_numbers=self.issue_numbers,
                    all_repos=False,
                    parallelism=None,  # Use config default
                    force=False,
                    config_path=self.config_path,
                    agent=self.agent,
                )
        else:
            await implement_command_async(
                repo=None,
                issue_numbers=self.issue_numbers,
                all_repos=True,
                parallelism=None,  # Use config default
                force=False,
                config_path=self.config_path,
                agent=self.agent,
            )

        logger.info("Work cycle completed")

    async def run_once(self) -> None:
        """Run a single work cycle and exit."""
        logger.info("Running one-shot mode")
        await self.run_cycle()

    async def run_continuous(self, frequency: str) -> None:
        """Run work cycles continuously at specified frequency.

        Args:
            frequency: Frequency string (e.g., '10m', '1h', '1d')
        """
        logger.info("Running continuous mode", frequency=frequency)

        # Parse frequency
        try:
            interval = parse_duration(frequency)
        except ValueError as e:
            logger.error(
                "Invalid frequency format",
                frequency=frequency,
                error=str(e),
                expected_format="10m, 1h, 2d, or 1h30m",
            )
            return

        logger.info(
            "Running continuously",
            frequency=frequency,
            interval_seconds=interval.total_seconds(),
        )

        cycle_count = 0
        while True:
            cycle_count += 1
            logger.info(
                "Starting work cycle",
                cycle=cycle_count,
                at=datetime.now().isoformat(),
            )

            try:
                await self.run_cycle()
            except Exception as e:
                logger.error("Work cycle failed", cycle=cycle_count, error=str(e))
                logger.info("Continuing to next cycle")

            # Wait for next cycle
            logger.info(
                "Waiting for next cycle",
                frequency=frequency,
                interval_seconds=interval.total_seconds(),
            )
            await asyncio.sleep(interval.total_seconds())
