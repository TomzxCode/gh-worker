"""Issue data model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Issue:
    """Represents a GitHub issue."""

    number: int
    title: str
    body: str
    state: str
    created_at: datetime
    updated_at: datetime
    author: str
    labels: list[str]
    url: str
    repository: str

    @classmethod
    def from_gh_json(cls, data: dict[str, Any], repository: str) -> "Issue":
        """Create Issue from GitHub CLI JSON output.

        Args:
            data: JSON data from gh CLI
            repository: Repository name (e.g., 'owner/repo')

        Returns:
            Issue instance
        """
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=data["state"],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00")),
            author=data["author"]["login"] if data.get("author") else "unknown",
            labels=[label["name"] for label in data.get("labels", [])],
            url=data["url"],
            repository=repository,
        )

    def to_markdown(self) -> str:
        """Convert issue to markdown format.

        Returns:
            Markdown representation of the issue
        """
        lines = [
            f"# {self.title}",
            "",
            f"**Issue**: #{self.number}",
            f"**Repository**: {self.repository}",
            f"**State**: {self.state}",
            f"**Author**: {self.author}",
            f"**Created**: {self.created_at.isoformat()}",
            f"**Updated**: {self.updated_at.isoformat()}",
            f"**URL**: {self.url}",
        ]

        if self.labels:
            lines.append(f"**Labels**: {', '.join(self.labels)}")

        lines.extend(["", "---", "", self.body])

        return "\n".join(lines)
