"""GitHub CLI client wrapper."""

import json
import subprocess
from pathlib import Path
from typing import Any

import structlog

from gh_worker.models.repository import Repository
from gh_worker.utils.retry import retry

logger = structlog.get_logger()


class GHClient:
    """Wrapper for GitHub CLI operations."""

    def __init__(self, repository_path: Path | None = None):
        """Initialize GitHub client.

        Args:
            repository_path: Base path for cloning repositories
        """
        self.repository_path = repository_path

    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _run_command(self, args: list[str], cwd: Path | None = None) -> str:
        """Run gh CLI command.

        Args:
            args: Command arguments
            cwd: Working directory

        Returns:
            Command output

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        cmd = ["gh"] + args
        logger.debug("running_gh_command", command=" ".join(cmd), cwd=str(cwd) if cwd else None)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=cwd, timeout=300
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            # Enhance error message with stderr output
            error_msg = f"GitHub CLI command failed: {' '.join(cmd)}"
            if e.stderr:
                error_msg += f"\n{e.stderr}"
            logger.error(
                "gh_command_failed", command=" ".join(cmd), stderr=e.stderr, returncode=e.returncode
            )
            raise RuntimeError(error_msg) from e
        except subprocess.TimeoutExpired as e:
            error_msg = f"GitHub CLI command timed out after 300s: {' '.join(cmd)}"
            logger.error("gh_command_timeout", command=" ".join(cmd))
            raise RuntimeError(error_msg) from e

    def list_issues(
        self,
        repository: Repository,
        state: str = "open",
        since: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """List issues from a repository.

        Args:
            repository: Repository object
            state: Issue state (open, closed, all)
            since: Only return issues updated after this date
            search: Search query

        Returns:
            List of issue data dictionaries
        """
        args = [
            "issue",
            "list",
            "--repo",
            repository.full_name,
            "--state",
            state,
            "--json",
            "number,title,body,state,createdAt,updatedAt,author,labels,url",
            "--limit",
            "1000",
        ]

        if search:
            args.extend(["--search", search])

        output = self._run_command(args)
        issues = json.loads(output)

        if since:
            from datetime import datetime

            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            issues = [
                issue
                for issue in issues
                if datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00")) > since_dt
            ]

        return issues

    def get_issue(self, repository: Repository, issue_number: int) -> dict[str, Any]:
        """Get a specific issue.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Issue data dictionary
        """
        args = [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repository.full_name,
            "--json",
            "number,title,body,state,createdAt,updatedAt,author,labels,url",
        ]

        output = self._run_command(args)
        return json.loads(output)

    def create_pr(
        self, repository: Repository, title: str, body: str, head: str, base: str = "main"
    ) -> str:
        """Create a pull request.

        Args:
            repository: Repository object
            title: PR title
            body: PR description
            head: Head branch
            base: Base branch

        Returns:
            PR URL
        """
        repo_path = self._get_repo_path(repository)

        args = [
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--head",
            head,
            "--base",
            base,
        ]

        output = self._run_command(args, cwd=repo_path)
        return output.strip()

    def clone_repo(self, repository: Repository) -> Path:
        """Clone a repository.

        Args:
            repository: Repository object

        Returns:
            Path to cloned repository

        Raises:
            ValueError: If repository_path is not set
        """
        if not self.repository_path:
            raise ValueError("repository_path must be set to clone repositories")

        repo_path = self._get_repo_path(repository)

        if repo_path.exists():
            logger.info("repository_already_exists", path=str(repo_path))
            return repo_path

        repo_path.parent.mkdir(parents=True, exist_ok=True)

        args = ["repo", "clone", repository.full_name, str(repo_path)]
        self._run_command(args)

        logger.info("repository_cloned", path=str(repo_path))
        return repo_path

    def _get_repo_path(self, repository: Repository) -> Path:
        """Get path to repository clone.

        Args:
            repository: Repository object

        Returns:
            Path to repository

        Raises:
            ValueError: If repository_path is not set
        """
        if not self.repository_path:
            raise ValueError("repository_path must be set")

        return Path(self.repository_path) / repository.owner / repository.name

    def check_auth(self) -> bool:
        """Check if gh CLI is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            self._run_command(["auth", "status"])
            return True
        except subprocess.CalledProcessError:
            return False
