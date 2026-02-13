"""List command implementation."""

from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.storage.issue_store import IssueStore

logger = structlog.get_logger()


def list_command(config_path: Path | None = None) -> None:
    """Execute list command.

    Args:
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    repositories = issue_store.list_repositories()

    if not repositories:
        logger.info("No repositories under management.")
        return

    for repo in sorted(repositories, key=lambda r: r.full_name):
        logger.info("Repository", repository=repo.full_name)
