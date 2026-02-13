"""Issue storage management."""

import re
from datetime import datetime
from pathlib import Path

from gh_worker.models.issue import Issue
from gh_worker.models.repository import Repository


class IssueStore:
    """Manages file-based storage for GitHub issues."""

    def __init__(self, issues_path: Path):
        """Initialize issue store.

        Args:
            issues_path: Base path for storing issues
        """
        self.issues_path = Path(issues_path)

    def get_issue_dir(self, repository: Repository, issue_number: int) -> Path:
        """Get directory path for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Path to issue directory
        """
        return self.issues_path / repository.owner / repository.name / str(issue_number)

    def get_repo_dir(self, repository: Repository) -> Path:
        """Get directory path for a repository.

        Args:
            repository: Repository object

        Returns:
            Path to repository directory
        """
        return self.issues_path / repository.owner / repository.name

    def save_issue(self, issue: Issue) -> None:
        """Save issue to file system.

        Args:
            issue: Issue to save
        """
        repo = Repository.from_string(issue.repository)
        issue_dir = self.get_issue_dir(repo, issue.number)
        issue_dir.mkdir(parents=True, exist_ok=True)

        # Save issue as markdown
        description_file = issue_dir / "description.md"
        description_file.write_text(issue.to_markdown())

        # Update timestamp
        updated_at_file = issue_dir / ".updated-at"
        updated_at_file.write_text(issue.updated_at.isoformat())

    def load_issue(self, repository: Repository, issue_number: int) -> Issue | None:
        """Load issue from file system.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Issue object or None if not found
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        description_file = issue_dir / "description.md"

        if not description_file.exists():
            return None

        # For now, return None as we'd need to parse the markdown
        # This is a simplified implementation
        return None

    def get_issue_author(self, repository: Repository, issue_number: int) -> str | None:
        """Get author for an issue from its description file.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Author username or None if not found
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        description_file = issue_dir / "description.md"

        if not description_file.exists():
            return None

        content = description_file.read_text()
        match = re.search(r"\*\*Author\*\*:\s*(.+)", content)
        if not match:
            return None

        return match.group(1).strip() or None

    def get_issue_assignees(self, repository: Repository, issue_number: int) -> list[str]:
        """Get assignees for an issue from its description file.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            List of assignee usernames, empty if not found or no assignees
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        description_file = issue_dir / "description.md"

        if not description_file.exists():
            return []

        content = description_file.read_text()
        match = re.search(r"\*\*Assignees\*\*:\s*(.+)", content)
        if not match:
            return []

        return [a.strip() for a in match.group(1).split(",") if a.strip()]

    def get_updated_at(self, repository: Repository, issue_number: int) -> datetime | None:
        """Get the last updated timestamp for an issue.

        Args:
            repository: Repository object
            issue_number: Issue number

        Returns:
            Last updated datetime or None if not found
        """
        issue_dir = self.get_issue_dir(repository, issue_number)
        updated_at_file = issue_dir / ".updated-at"

        if not updated_at_file.exists():
            return None

        timestamp_str = updated_at_file.read_text().strip()
        return datetime.fromisoformat(timestamp_str)

    def set_repo_updated_at(self, repository: Repository, timestamp: datetime) -> None:
        """Set the last updated timestamp for a repository.

        Args:
            repository: Repository object
            timestamp: Timestamp to set
        """
        repo_dir = self.get_repo_dir(repository)
        repo_dir.mkdir(parents=True, exist_ok=True)

        updated_at_file = repo_dir / ".updated-at"
        updated_at_file.write_text(timestamp.isoformat())

    def get_repo_updated_at(self, repository: Repository) -> datetime | None:
        """Get the last updated timestamp for a repository.

        Args:
            repository: Repository object

        Returns:
            Last updated datetime or None if not found
        """
        repo_dir = self.get_repo_dir(repository)
        updated_at_file = repo_dir / ".updated-at"

        if not updated_at_file.exists():
            return None

        timestamp_str = updated_at_file.read_text().strip()
        return datetime.fromisoformat(timestamp_str)

    def list_issues(self, repository: Repository) -> list[int]:
        """List all issue numbers for a repository.

        Args:
            repository: Repository object

        Returns:
            List of issue numbers
        """
        repo_dir = self.get_repo_dir(repository)

        if not repo_dir.exists():
            return []

        issue_numbers = []
        for item in repo_dir.iterdir():
            if item.is_dir() and item.name.isdigit():
                issue_numbers.append(int(item.name))

        return sorted(issue_numbers)

    def list_repositories(self) -> list[Repository]:
        """List all repositories in the issues path.

        Returns:
            List of Repository objects
        """
        repositories = []

        if not self.issues_path.exists():
            return repositories

        for owner_dir in self.issues_path.iterdir():
            if not owner_dir.is_dir() or owner_dir.name.startswith("."):
                continue

            for repo_dir in owner_dir.iterdir():
                if not repo_dir.is_dir() or repo_dir.name.startswith("."):
                    continue

                repositories.append(Repository(owner=owner_dir.name, name=repo_dir.name))

        return repositories

    def resolve_repo(self, repo: str) -> Repository:
        """Resolve a repository string to a Repository, with partial matching.

        Supports:
        - 'owner/repo': parsed directly when no suffix match
        - 'r/repo-name' or 'repo-name': match by repo name (exact)
        - 'owner_suffix/repo-name': match owner ending with prefix, repo name exact.
          e.g. 'y/repo' -> my/repo, 'ner/repo' -> owner/repo

        Args:
            repo: Repository string (e.g., 'owner/repo', 'r/repo', 'y/repo')

        Returns:
            Resolved Repository

        Raises:
            ValueError: If format is invalid, no match, or multiple matches
        """
        tracked = self.list_repositories()

        if repo.startswith("r/"):
            repo_name = repo[2:]
            matches = [r for r in tracked if r.name == repo_name]
        elif "/" in repo:
            parts = repo.split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Repository must be in 'owner/repo' format, got: {repo}")

            owner_suffix = parts[0]
            repo_name = parts[1]
            matches = [
                r for r in tracked
                if r.name == repo_name and r.owner.endswith(owner_suffix)
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(
                    f"Multiple repositories match '{repo}': "
                    f"{', '.join(r.full_name for r in matches)}. "
                    "Use 'owner/repo' to disambiguate."
                )
            # 0 matches: try parsing as explicit owner/repo (sync may create it)
            try:
                return Repository.from_string(repo)
            except ValueError:
                raise ValueError(
                    f"No tracked repository matches '{repo}'. "
                    "Use 'owner/repo' format or add the repository first."
                )
        else:
            matches = [r for r in tracked if r.name == repo]

        if len(matches) == 1:
            return matches[0]
        if len(matches) == 0:
            raise ValueError(
                f"No tracked repository matches '{repo}'. "
                "Use 'owner/repo' format or add the repository first."
            )
        raise ValueError(
            f"Multiple repositories match '{repo}': "
            f"{', '.join(r.full_name for r in matches)}. Use 'owner/repo' to disambiguate."
        )
