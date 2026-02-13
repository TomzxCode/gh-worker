"""Unit tests for storage layer."""

import time
from datetime import datetime

import pytest

from gh_worker.models.issue import Issue
from gh_worker.models.plan import PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore


@pytest.fixture
def tmp_issues_path(tmp_path):
    """Fixture for temporary issues path."""
    return tmp_path / "issues"


@pytest.fixture
def issue_store(tmp_issues_path):
    """Fixture for IssueStore."""
    return IssueStore(tmp_issues_path)


@pytest.fixture
def plan_store(tmp_issues_path):
    """Fixture for PlanStore."""
    return PlanStore(tmp_issues_path)


@pytest.fixture
def sample_issue():
    """Fixture for sample issue."""
    return Issue(
        number=123,
        title="Test Issue",
        body="Issue description",
        state="open",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 2, 12, 0, 0),
        author="testuser",
        labels=["bug"],
        assignees=[],
        url="https://github.com/owner/repo/issues/123",
        repository="owner/repo",
    )


@pytest.fixture
def sample_repo():
    """Fixture for sample repository."""
    return Repository(owner="owner", name="repo")


class TestIssueStore:
    """Tests for IssueStore."""

    def test_get_issue_dir(self, issue_store, sample_repo):
        """Test getting issue directory path."""
        issue_dir = issue_store.get_issue_dir(sample_repo, 123)
        assert issue_dir == issue_store.issues_path / "owner" / "repo" / "123"

    def test_get_repo_dir(self, issue_store, sample_repo):
        """Test getting repository directory path."""
        repo_dir = issue_store.get_repo_dir(sample_repo)
        assert repo_dir == issue_store.issues_path / "owner" / "repo"

    def test_save_issue(self, issue_store, sample_issue):
        """Test saving issue to file system."""
        issue_store.save_issue(sample_issue)

        repo = Repository.from_string(sample_issue.repository)
        issue_dir = issue_store.get_issue_dir(repo, sample_issue.number)

        description_file = issue_dir / "description.md"
        assert description_file.exists()

        content = description_file.read_text()
        assert "# Test Issue" in content
        assert "Issue description" in content

        updated_at_file = issue_dir / ".updated-at"
        assert updated_at_file.exists()

    def test_get_updated_at(self, issue_store, sample_issue, sample_repo):
        """Test getting issue updated timestamp."""
        issue_store.save_issue(sample_issue)

        updated_at = issue_store.get_updated_at(sample_repo, sample_issue.number)
        assert updated_at == sample_issue.updated_at

    def test_get_updated_at_not_found(self, issue_store, sample_repo):
        """Test getting updated timestamp for non-existent issue."""
        updated_at = issue_store.get_updated_at(sample_repo, 999)
        assert updated_at is None

    def test_set_repo_updated_at(self, issue_store, sample_repo):
        """Test setting repository updated timestamp."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        issue_store.set_repo_updated_at(sample_repo, timestamp)

        repo_dir = issue_store.get_repo_dir(sample_repo)
        updated_at_file = repo_dir / ".updated-at"
        assert updated_at_file.exists()

        retrieved = issue_store.get_repo_updated_at(sample_repo)
        assert retrieved == timestamp

    def test_list_issues(self, issue_store, sample_issue, sample_repo):
        """Test listing issues for a repository."""
        # Save multiple issues
        for i in [1, 2, 3]:
            issue = Issue(
                number=i,
                title=f"Issue {i}",
                body="Description",
                state="open",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                author="user",
                labels=[],
                assignees=[],
                url=f"https://github.com/owner/repo/issues/{i}",
                repository="owner/repo",
            )
            issue_store.save_issue(issue)

        issues = issue_store.list_issues(sample_repo)
        assert issues == [1, 2, 3]

    def test_list_issues_empty(self, issue_store, sample_repo):
        """Test listing issues for repository with no issues."""
        issues = issue_store.list_issues(sample_repo)
        assert issues == []

    def test_list_repositories(self, issue_store, sample_issue):
        """Test listing all repositories."""
        # Save issues for multiple repos
        issue1 = sample_issue
        issue_store.save_issue(issue1)

        issue2 = Issue(
            number=456,
            title="Test Issue 2",
            body="Description",
            state="open",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author="user",
            labels=[],
            assignees=[],
            url="https://github.com/other/project/issues/456",
            repository="other/project",
        )
        issue_store.save_issue(issue2)

        repos = issue_store.list_repositories()
        repo_strings = [repo.full_name for repo in repos]
        assert "owner/repo" in repo_strings
        assert "other/project" in repo_strings


class TestPlanStore:
    """Tests for PlanStore."""

    def test_get_issue_dir(self, plan_store, sample_repo):
        """Test getting issue directory path."""
        issue_dir = plan_store.get_issue_dir(sample_repo, 123)
        assert issue_dir == plan_store.issues_path / "owner" / "repo" / "123"

    def test_create_plan(self, plan_store, sample_repo):
        """Test creating a new plan."""
        content = "# Implementation Plan\n\nThis is a test plan."
        metadata = plan_store.create_plan(sample_repo, 123, content)

        assert metadata.issue_number == 123
        assert metadata.repository == "owner/repo"
        assert metadata.status == PlanStatus.PENDING
        assert metadata.plan_file is not None

        # Verify plan file exists
        assert metadata.plan_file.exists()
        assert metadata.plan_file.read_text() == content

        # Verify metadata file exists
        metadata_file = metadata.plan_file.with_suffix(".yaml")
        assert metadata_file.exists()

    def test_get_latest_plan(self, plan_store, sample_repo):
        """Test getting the latest plan for an issue."""
        # Create multiple plans
        plan_store.create_plan(sample_repo, 123, "Plan 1")
        plan_store.create_plan(sample_repo, 123, "Plan 2")

        result = plan_store.get_latest_plan(sample_repo, 123)
        assert result is not None

        plan_file, metadata = result
        assert plan_file.read_text() == "Plan 2"
        assert metadata.issue_number == 123

    def test_get_latest_plan_not_found(self, plan_store, sample_repo):
        """Test getting latest plan when none exists."""
        result = plan_store.get_latest_plan(sample_repo, 999)
        assert result is None

    def test_list_plans(self, plan_store, sample_repo):
        """Test listing all plans for an issue."""
        # Create multiple plans
        plan_store.create_plan(sample_repo, 123, "Plan 1")
        time.sleep(1)
        plan_store.create_plan(sample_repo, 123, "Plan 2")

        plans = plan_store.list_plans(sample_repo, 123)
        assert len(plans) == 2

        # Should be sorted newest first
        assert plans[0][0].read_text() == "Plan 2"
        assert plans[1][0].read_text() == "Plan 1"

    def test_list_plans_empty(self, plan_store, sample_repo):
        """Test listing plans when none exist."""
        plans = plan_store.list_plans(sample_repo, 123)
        assert plans == []

    def test_update_metadata(self, plan_store, sample_repo):
        """Test updating plan metadata."""
        metadata = plan_store.create_plan(sample_repo, 123, "Plan content")

        # Update metadata
        metadata.status = PlanStatus.COMPLETED
        metadata.pr_url = "https://github.com/owner/repo/pull/456"
        plan_store.update_metadata(metadata)

        # Retrieve and verify
        result = plan_store.get_latest_plan(sample_repo, 123)
        assert result is not None
        _, retrieved_metadata = result

        assert retrieved_metadata.status == PlanStatus.COMPLETED
        assert retrieved_metadata.pr_url == "https://github.com/owner/repo/pull/456"

    def test_has_plan(self, plan_store, sample_repo):
        """Test checking if issue has plans."""
        assert not plan_store.has_plan(sample_repo, 123)

        # Create .updated-at file before creating plan
        issue_dir = plan_store.get_issue_dir(sample_repo, 123)
        issue_dir.mkdir(parents=True, exist_ok=True)
        updated_at_file = issue_dir / ".updated-at"
        # Set updated_at to a time before plan creation (use a fixed past timestamp)
        updated_at_file.write_text(datetime(2024, 1, 1, 12, 0, 0).isoformat())

        plan_store.create_plan(sample_repo, 123, "Plan content")

        assert plan_store.has_plan(sample_repo, 123)

    def test_has_plan_no_matching_timestamp(self, plan_store, sample_repo):
        """Test that has_plan returns False when .updated-at is newer than all plans."""
        from datetime import timezone

        issue_dir = plan_store.get_issue_dir(sample_repo, 123)
        issue_dir.mkdir(parents=True, exist_ok=True)

        # Create a plan with an old timestamp
        metadata = plan_store.create_plan(sample_repo, 123, "Old plan")
        # Backdate the plan so it's older than .updated-at
        metadata.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        plan_store.update_metadata(metadata)

        # Set .updated-at to a time after the plan was created
        updated_at_file = issue_dir / ".updated-at"
        updated_at_file.write_text(datetime(2025, 1, 1, 12, 0, 0).isoformat())

        # Should return False because plan is older than .updated-at
        assert not plan_store.has_plan(sample_repo, 123)
