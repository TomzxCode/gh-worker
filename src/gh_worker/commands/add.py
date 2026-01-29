"""Add command implementation."""

from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.github.client import GHClient
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore

logger = structlog.get_logger()


def add_command(repos: list[str], config_path: Path | None = None) -> None:
    """Execute add command.

    Args:
        repos: Repository names (e.g., 'owner/repo')
        config_path: Path to config file
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("issues_path_not_configured")
        print("Error: issues-path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)
    gh_client = GHClient(app_config.repository_path)

    if not gh_client.check_auth():
        logger.error("gh_not_authenticated")
        print("Error: gh CLI not authenticated. Run: gh auth login")
        return

    for repo_str in repos:
        try:
            repository = Repository.from_string(repo_str)

            # Create issue directory structure
            repo_dir = issue_store.get_repo_dir(repository)
            repo_dir.mkdir(parents=True, exist_ok=True)

            logger.info("created_repository_directory", repository=repository.full_name)
            print(f"Added repository: {repository.full_name}")

            # Clone repository if repository_path is configured
            if app_config.repository_path:
                try:
                    gh_client.clone_repo(repository)
                    print(f"Cloned repository to: {gh_client._get_repo_path(repository)}")
                except Exception as e:
                    logger.warning("failed_to_clone_repository", error=str(e))
                    print(f"Warning: Failed to clone repository: {e}")
            else:
                print(
                    "Note: repository-path not configured. "
                    "Set it to enable automatic cloning of repositories. "
                    "Run: gh-worker config repository-path <path>"
                )

        except ValueError as e:
            logger.error("invalid_repository_format", repo=repo_str, error=str(e))
            print(f"Error: {e}")
        except Exception as e:
            logger.error("failed_to_add_repository", repo=repo_str, error=str(e))
            print(f"Error: Failed to add repository {repo_str}: {e}")
