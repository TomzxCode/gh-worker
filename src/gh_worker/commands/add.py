"""Add command implementation."""

from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.github.client import GHClient
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore

logger = structlog.get_logger()


def add_command(
    repos: list[str],
    config_path: Path | None = None,
    clone: bool = False,
) -> None:
    """Execute add command.

    Args:
        repos: Repository names (e.g., 'owner/repo')
        config_path: Path to config file
        clone: If True, clone the repository to repository-path
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured")
        logger.error("Issues path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    gh_client = GHClient(app_config.repository_path)

    if not gh_client.check_auth():
        logger.error("gh CLI not authenticated")
        logger.error("gh CLI not authenticated. Run: gh auth login")
        return

    for repo_str in repos:
        try:
            repository = Repository.from_string(repo_str)

            # Create issue directory structure
            repo_dir = issue_store.get_repo_dir(repository)
            repo_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Created repository directory", repository=repository.full_name)
            logger.info(f"Added repository: {repository.full_name}")

            # Clone repository only if --clone was passed and repository_path is configured
            if clone and app_config.repository_path:
                try:
                    gh_client.clone_repo(repository)
                    logger.info(f"Cloned repository to: {gh_client._get_repo_path(repository)}")
                except Exception as e:
                    logger.warning("Failed to clone repository", error=str(e))
                    logger.warning(f"Failed to clone repository: {e}")
            elif clone and not app_config.repository_path:
                logger.info(
                    "Repository-path not configured. Set it to enable cloning. "
                    "Run: gh-worker config repository-path <path>"
                )
            elif app_config.repository_path:
                logger.info(
                    "Repository not cloned. Use --clone to clone now, "
                    "or it will be cloned when you run 'ghw issues plan'."
                )

        except ValueError as e:
            logger.error("Invalid repository format", repo=repo_str, error=str(e))
        except Exception as e:
            logger.error("Failed to add repository", repo=repo_str, error=str(e))
