"""Repository data model."""

from dataclasses import dataclass


@dataclass
class Repository:
    """Represents a GitHub repository."""

    owner: str
    name: str

    @classmethod
    def from_string(cls, repo_string: str) -> "Repository":
        """Create Repository from string format.

        Args:
            repo_string: Repository string in 'owner/repo' format

        Returns:
            Repository instance

        Raises:
            ValueError: If repo_string is not in correct format
        """
        parts = repo_string.split("/")
        if len(parts) != 2:
            raise ValueError(f"Repository must be in 'owner/repo' format, got: {repo_string}")

        owner, name = parts
        if not owner or not name:
            raise ValueError(f"Repository owner and name cannot be empty, got: {repo_string}")

        return cls(owner=owner.strip(), name=name.strip())

    def __str__(self) -> str:
        """String representation in 'owner/repo' format.

        Returns:
            Repository string
        """
        return f"{self.owner}/{self.name}"

    @property
    def full_name(self) -> str:
        """Get full repository name.

        Returns:
            Full repository name in 'owner/repo' format
        """
        return str(self)
