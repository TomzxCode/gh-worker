"""Unit tests for data models."""

from datetime import datetime

import pytest

from gh_worker.models.issue import Issue
from gh_worker.models.plan import PlanMetadata, PlanStatus
from gh_worker.models.repository import Repository


class TestRepository:
    """Tests for Repository model."""

    def test_from_string_valid(self):
        """Test parsing valid repository string."""
        repo = Repository.from_string("owner/repo")
        assert repo.owner == "owner"
        assert repo.name == "repo"

    def test_from_string_with_whitespace(self):
        """Test parsing repository string with whitespace."""
        repo = Repository.from_string(" owner / repo ")
        assert repo.owner == "owner"
        assert repo.name == "repo"

    def test_from_string_invalid_format(self):
        """Test parsing invalid repository string."""
        with pytest.raises(ValueError, match="must be in 'owner/repo' format"):
            Repository.from_string("invalid")

    def test_from_string_empty_parts(self):
        """Test parsing repository string with empty parts."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Repository.from_string("/repo")

        with pytest.raises(ValueError, match="cannot be empty"):
            Repository.from_string("owner/")

    def test_str_representation(self):
        """Test string representation."""
        repo = Repository(owner="owner", name="repo")
        assert str(repo) == "owner/repo"

    def test_full_name_property(self):
        """Test full_name property."""
        repo = Repository(owner="owner", name="repo")
        assert repo.full_name == "owner/repo"


class TestIssue:
    """Tests for Issue model."""

    def test_from_gh_json(self):
        """Test creating Issue from GitHub JSON."""
        data = {
            "number": 123,
            "title": "Test Issue",
            "body": "Issue description",
            "state": "open",
            "createdAt": "2024-01-01T12:00:00Z",
            "updatedAt": "2024-01-02T12:00:00Z",
            "author": {"login": "testuser"},
            "labels": [{"name": "bug"}, {"name": "enhancement"}],
            "assignees": [{"login": "alice"}, {"login": "bob"}],
            "url": "https://github.com/owner/repo/issues/123",
        }

        issue = Issue.from_gh_json(data, "owner/repo")

        assert issue.number == 123
        assert issue.title == "Test Issue"
        assert issue.body == "Issue description"
        assert issue.state == "open"
        assert issue.author == "testuser"
        assert issue.labels == ["bug", "enhancement"]
        assert issue.assignees == ["alice", "bob"]
        assert issue.url == "https://github.com/owner/repo/issues/123"
        assert issue.repository == "owner/repo"

    def test_from_gh_json_missing_optional_fields(self):
        """Test creating Issue with missing optional fields."""
        data = {
            "number": 123,
            "title": "Test Issue",
            "state": "open",
            "createdAt": "2024-01-01T12:00:00Z",
            "updatedAt": "2024-01-02T12:00:00Z",
            "url": "https://github.com/owner/repo/issues/123",
        }

        issue = Issue.from_gh_json(data, "owner/repo")

        assert issue.body == ""
        assert issue.author == "unknown"
        assert issue.labels == []
        assert issue.assignees == []

    def test_to_markdown(self):
        """Test converting Issue to markdown."""
        issue = Issue(
            number=123,
            title="Test Issue",
            body="Issue description",
            state="open",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0),
            author="testuser",
            labels=["bug"],
            assignees=["alice", "bob"],
            url="https://github.com/owner/repo/issues/123",
            repository="owner/repo",
        )

        markdown = issue.to_markdown()

        assert "# Test Issue" in markdown
        assert "**Issue**: #123" in markdown
        assert "**Repository**: owner/repo" in markdown
        assert "**State**: open" in markdown
        assert "**Author**: testuser" in markdown
        assert "**Labels**: bug" in markdown
        assert "**Assignees**: alice, bob" in markdown
        assert "Issue description" in markdown


class TestPlanMetadata:
    """Tests for PlanMetadata model."""

    def test_to_dict(self):
        """Test converting PlanMetadata to dictionary."""
        metadata = PlanMetadata(
            issue_number=123,
            repository="owner/repo",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            status=PlanStatus.COMPLETED,
            session_id="session-123",
            branch_name="issue-123",
            pr_url="https://github.com/owner/repo/pull/456",
        )

        data = metadata.to_dict()

        assert data["issue_number"] == 123
        assert data["repository"] == "owner/repo"
        assert data["status"] == "completed"
        assert data["session_id"] == "session-123"
        assert data["branch_name"] == "issue-123"
        assert data["pr_url"] == "https://github.com/owner/repo/pull/456"

    def test_from_dict(self):
        """Test creating PlanMetadata from dictionary."""
        data = {
            "issue_number": 123,
            "repository": "owner/repo",
            "created_at": "2024-01-01T12:00:00",
            "status": "completed",
            "session_id": "session-123",
            "branch_name": "issue-123",
            "pr_url": "https://github.com/owner/repo/pull/456",
        }

        metadata = PlanMetadata.from_dict(data)

        assert metadata.issue_number == 123
        assert metadata.repository == "owner/repo"
        assert metadata.status == PlanStatus.COMPLETED
        assert metadata.session_id == "session-123"
        assert metadata.branch_name == "issue-123"
        assert metadata.pr_url == "https://github.com/owner/repo/pull/456"

    def test_from_dict_defaults(self):
        """Test creating PlanMetadata with default values."""
        data = {
            "issue_number": 123,
            "repository": "owner/repo",
            "created_at": "2024-01-01T12:00:00",
        }

        metadata = PlanMetadata.from_dict(data)

        assert metadata.status == PlanStatus.PENDING
        assert metadata.session_id is None
        assert metadata.branch_name is None
        assert metadata.pr_url is None
        assert metadata.commit_hash is None

    def test_commit_hash_roundtrip(self):
        """Test commit_hash serialization and deserialization."""
        data = {
            "issue_number": 123,
            "repository": "owner/repo",
            "created_at": "2024-01-01T12:00:00",
            "commit_hash": "abc123def456",
        }

        metadata = PlanMetadata.from_dict(data)
        assert metadata.commit_hash == "abc123def456"

        serialized = metadata.to_dict()
        assert serialized["commit_hash"] == "abc123def456"
