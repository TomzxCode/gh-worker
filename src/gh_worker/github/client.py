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

    def create_worktree(
        self, repository: Repository, branch_name: str, worktree_path: Path
    ) -> Path:
        """Create a git worktree for a branch.

        Args:
            repository: Repository object
            branch_name: Branch name to create/checkout
            worktree_path: Path where worktree should be created

        Returns:
            Path to the created worktree

        Raises:
            RuntimeError: If worktree creation fails
        """
        repo_path = self._get_repo_path(repository)

        if not repo_path.exists():
            raise FileNotFoundError(f"Repository not found at {repo_path}")

        # Ensure parent directory exists
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine base branch (main/master) for creating new branches
        base_branch = None
        try:
            # Try to get current branch
            current_branch = self._run_git_command(
                ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path
            ).strip()
            base_branch = current_branch
        except RuntimeError:
            # If that fails, try common default branches
            for default_branch in ["main", "master"]:
                try:
                    # Check if branch exists locally
                    self._run_git_command(
                        ["rev-parse", "--verify", default_branch], cwd=repo_path
                    )
                    base_branch = default_branch
                    break
                except RuntimeError:
                    # Try remote branch
                    try:
                        self._run_git_command(
                            ["rev-parse", "--verify", f"origin/{default_branch}"],
                            cwd=repo_path,
                        )
                        base_branch = default_branch
                        break
                    except RuntimeError:
                        continue
            if not base_branch:
                raise RuntimeError("Could not determine base branch for worktree")

        # Check if branch already exists
        try:
            self._run_git_command(
                ["rev-parse", "--verify", branch_name], cwd=repo_path
            )
            branch_exists = True
        except RuntimeError:
            branch_exists = False

        # Create worktree with branch
        if branch_exists:
            # Branch exists, checkout existing branch in worktree
            args = ["worktree", "add", str(worktree_path), branch_name]
        else:
            # Branch doesn't exist, create new branch in worktree from base branch
            args = ["worktree", "add", "-b", branch_name, str(worktree_path), base_branch]

        try:
            self._run_git_command(args, cwd=repo_path)
            logger.info(
                "worktree_created",
                repository=repository.full_name,
                branch=branch_name,
                worktree_path=str(worktree_path),
            )
            return worktree_path
        except RuntimeError as e:
            logger.error(
                "worktree_creation_failed",
                repository=repository.full_name,
                branch=branch_name,
                error=str(e),
            )
            raise RuntimeError(f"Failed to create worktree: {e}") from e

    def remove_worktree(self, repository: Repository, worktree_path: Path) -> None:
        """Remove a git worktree.

        Args:
            repository: Repository object
            worktree_path: Path to the worktree to remove

        Raises:
            RuntimeError: If worktree removal fails
        """
        repo_path = self._get_repo_path(repository)

        if not repo_path.exists():
            logger.warning(
                "repository_not_found_for_worktree_removal",
                repository=repository.full_name,
                path=str(repo_path),
            )
            return

        if not worktree_path.exists():
            logger.debug(
                "worktree_path_already_removed",
                worktree_path=str(worktree_path),
            )
            return

        args = ["worktree", "remove", str(worktree_path)]
        try:
            self._run_git_command(args, cwd=repo_path)
            logger.info(
                "worktree_removed",
                repository=repository.full_name,
                worktree_path=str(worktree_path),
            )
        except RuntimeError as e:
            logger.error(
                "worktree_removal_failed",
                repository=repository.full_name,
                worktree_path=str(worktree_path),
                error=str(e),
            )
            # Try force removal if normal removal fails
            try:
                args = ["worktree", "remove", "--force", str(worktree_path)]
                self._run_git_command(args, cwd=repo_path)
                logger.info(
                    "worktree_force_removed",
                    repository=repository.full_name,
                    worktree_path=str(worktree_path),
                )
            except RuntimeError as force_error:
                logger.error(
                    "worktree_force_removal_failed",
                    repository=repository.full_name,
                    worktree_path=str(worktree_path),
                    error=str(force_error),
                )
                raise RuntimeError(f"Failed to remove worktree: {force_error}") from force_error

    def _run_git_command(self, args: list[str], cwd: Path | None = None) -> str:
        """Run git command.

        Args:
            args: Command arguments
            cwd: Working directory

        Returns:
            Command output

        Raises:
            RuntimeError: If command fails
        """
        cmd = ["git"] + args
        logger.debug("running_git_command", command=" ".join(cmd), cwd=str(cwd) if cwd else None)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, cwd=cwd, timeout=300
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = f"Git command failed: {' '.join(cmd)}"
            if e.stderr:
                error_msg += f"\n{e.stderr}"
            logger.error(
                "git_command_failed", command=" ".join(cmd), stderr=e.stderr, returncode=e.returncode
            )
            raise RuntimeError(error_msg) from e
        except subprocess.TimeoutExpired as e:
            error_msg = f"Git command timed out after 300s: {' '.join(cmd)}"
            logger.error("git_command_timeout", command=" ".join(cmd))
            raise RuntimeError(error_msg) from e

    def get_current_commit_sha(self, repo_path: Path, branch_name: str | None = None) -> str:
        """Get the current commit SHA for a branch or HEAD.

        Args:
            repo_path: Path to repository
            branch_name: Optional branch name (if None, uses HEAD)

        Returns:
            Commit SHA string

        Raises:
            RuntimeError: If unable to get commit SHA
        """
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository not found at {repo_path}")

        if branch_name:
            args = ["rev-parse", branch_name]
        else:
            args = ["rev-parse", "HEAD"]

        output = self._run_git_command(args, cwd=repo_path)
        commit_sha = output.strip()
        logger.debug(
            "current_commit_sha",
            repo_path=str(repo_path),
            branch=branch_name,
            commit_sha=commit_sha,
        )
        return commit_sha

    def has_commits_on_branch(
        self, repository: Repository, branch_name: str, repo_path: Path | None = None
    ) -> bool:
        """Check if branch has commits that are not on the base branch.

        Args:
            repository: Repository object
            branch_name: Branch name to check
            repo_path: Optional path to repository (uses _get_repo_path if None)

        Returns:
            True if branch has commits, False otherwise
        """
        if repo_path is None:
            repo_path = self._get_repo_path(repository)

        if not repo_path.exists():
            return False

        try:
            # Check if branch exists
            self._run_git_command(["rev-parse", "--verify", branch_name], cwd=repo_path)
        except RuntimeError:
            # Branch doesn't exist
            return False

        try:
            # Get base branch (main or master)
            base_branch = None
            for default_branch in ["main", "master"]:
                try:
                    self._run_git_command(
                        ["rev-parse", "--verify", default_branch], cwd=repo_path
                    )
                    base_branch = default_branch
                    break
                except RuntimeError:
                    try:
                        self._run_git_command(
                            ["rev-parse", "--verify", f"origin/{default_branch}"], cwd=repo_path
                        )
                        base_branch = default_branch
                        break
                    except RuntimeError:
                        continue

            if not base_branch:
                logger.warning("could_not_determine_base_branch", repository=repository.full_name)
                # If we can't determine base branch, check if branch has any commits
                output = self._run_git_command(
                    ["rev-list", "--count", branch_name], cwd=repo_path
                )
                return int(output.strip()) > 0

            # Check if branch has commits ahead of base branch
            output = self._run_git_command(
                ["rev-list", "--count", f"{base_branch}..{branch_name}"], cwd=repo_path
            )
            commit_count = int(output.strip())
            logger.debug(
                "branch_commit_check",
                repository=repository.full_name,
                branch=branch_name,
                base_branch=base_branch,
                commit_count=commit_count,
            )
            return commit_count > 0
        except RuntimeError as e:
            logger.error(
                "failed_to_check_branch_commits",
                repository=repository.full_name,
                branch=branch_name,
                error=str(e),
            )
            return False

    def stage_all_changes(self, repo_path: Path) -> None:
        """Stage all changes in the repository.

        Args:
            repo_path: Path to repository

        Raises:
            RuntimeError: If staging fails
        """
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository not found at {repo_path}")

        args = ["add", "."]
        try:
            self._run_git_command(args, cwd=repo_path)
            logger.info("changes_staged", repo_path=str(repo_path))
        except RuntimeError as e:
            logger.error("staging_failed", repo_path=str(repo_path), error=str(e))
            raise RuntimeError(f"Failed to stage changes: {e}") from e

    def create_commit(self, repo_path: Path, commit_message: str) -> str:
        """Create a commit with the given message.

        Args:
            repo_path: Path to repository
            commit_message: Commit message

        Returns:
            Commit SHA of the created commit

        Raises:
            RuntimeError: If commit fails
        """
        if not repo_path.exists():
            raise FileNotFoundError(f"Repository not found at {repo_path}")

        args = ["commit", "-m", commit_message]
        try:
            self._run_git_command(args, cwd=repo_path)
            # Get the commit SHA
            commit_sha = self.get_current_commit_sha(repo_path)
            logger.info(
                "commit_created",
                repo_path=str(repo_path),
                commit_sha=commit_sha,
                message_length=len(commit_message),
            )
            return commit_sha
        except RuntimeError as e:
            logger.error(
                "commit_failed",
                repo_path=str(repo_path),
                error=str(e),
                message_length=len(commit_message),
            )
            raise RuntimeError(f"Failed to create commit: {e}") from e

    def push_branch(
        self, repository: Repository, branch_name: str, repo_path: Path | None = None
    ) -> None:
        """Push branch to remote.

        Args:
            repository: Repository object
            branch_name: Branch name to push
            repo_path: Optional path to repository (uses _get_repo_path if None)

        Raises:
            RuntimeError: If push fails
        """
        if repo_path is None:
            repo_path = self._get_repo_path(repository)

        if not repo_path.exists():
            raise FileNotFoundError(f"Repository not found at {repo_path}")

        # Get remote name (usually 'origin')
        try:
            remotes_output = self._run_git_command(["remote"], cwd=repo_path)
            remotes = remotes_output.strip().split("\n")
            remote = remotes[0] if remotes else "origin"
        except RuntimeError:
            remote = "origin"

        args = ["push", "-u", remote, branch_name]
        try:
            self._run_git_command(args, cwd=repo_path)
            logger.info(
                "branch_pushed",
                repository=repository.full_name,
                branch=branch_name,
                remote=remote,
            )
        except RuntimeError as e:
            logger.error(
                "branch_push_failed",
                repository=repository.full_name,
                branch=branch_name,
                error=str(e),
            )
            raise RuntimeError(f"Failed to push branch {branch_name}: {e}") from e
