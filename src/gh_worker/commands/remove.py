"""Remove command implementation."""

import shutil
from pathlib import Path

import structlog

from gh_worker.config.manager import ConfigManager
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore

logger = structlog.get_logger()


def remove_command(
    repos: list[str],
    config_path: Path | None = None,
    keep_clone: bool = True,
) -> None:
    """Execute remove command.

    Args:
        repos: Repository names (e.g., 'owner/repo') to remove from tracking
        config_path: Path to config file
        keep_clone: If True, keep the cloned repository in repository-path
    """
    config = ConfigManager(config_path)
    app_config = config.load()

    if not app_config.issues_path:
        logger.error("Issues path not configured")
        print("Error: issues-path not configured. Run: gh-worker config issues-path <path>")
        return

    issue_store = IssueStore(app_config.issues_path)

    for repo_str in repos:
        try:
            repository = Repository.from_string(repo_str)
            repo_dir = issue_store.get_repo_dir(repository)

            if not repo_dir.exists():
                logger.warning("Repository not tracked", repository=repository.full_name)
                print(f"Repository {repository.full_name} is not under management.")
                continue

            # Remove issues/plans directory
            shutil.rmtree(repo_dir)
            logger.info("Removed repository", repository=repository.full_name)
            print(f"Removed repository: {repository.full_name}")

            # Optionally remove cloned repository
            if not keep_clone and app_config.repository_path:
                clone_path = Path(app_config.repository_path) / repository.owner / repository.name
                if clone_path.exists():
                    shutil.rmtree(clone_path)
                    logger.info("Removed clone", path=str(clone_path))
                    print(f"Removed clone: {clone_path}")

        except ValueError as e:
            logger.error("Invalid repository format", repo=repo_str, error=str(e))
            print(f"Error: {e}")
        except OSError as e:
            logger.error("Failed to remove repository", repo=repo_str, error=str(e))
            print(f"Error: Failed to remove repository {repo_str}: {e}")
