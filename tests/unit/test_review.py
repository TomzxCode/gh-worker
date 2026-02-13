"""Unit tests for review commands."""

from gh_worker.commands.review import (
    _find_implementations_waiting_review,
    _find_issues_with_approved_plans,
    _find_issues_with_plans_waiting_review,
    unapprove_plan_command,
)
from gh_worker.models.plan import PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore


class TestFindIssuesWithPlansWaitingReview:
    """Tests for _find_issues_with_plans_waiting_review."""

    def test_finds_pending_plans(self, tmp_path):
        """Test finding issues with plans waiting for review."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        for issue_number in [1, 2]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        items = _find_issues_with_plans_waiting_review(
            repository, issue_store, plan_store, None, None
        )
        assert len(items) == 2

    def test_skips_approved_plans(self, tmp_path):
        """Test that approved plans are skipped."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")
        _, metadata = plan_store.get_latest_plan(repository, 1)
        metadata.status = PlanStatus.APPROVED
        plan_store.update_metadata(metadata)

        items = _find_issues_with_plans_waiting_review(
            repository, issue_store, plan_store, None, None
        )
        assert len(items) == 0


class TestFindImplementationsWaitingReview:
    """Tests for _find_implementations_waiting_review."""

    def test_finds_completed_without_pr(self, tmp_path):
        """Test finding implementations completed but no PR."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")
        _, metadata = plan_store.get_latest_plan(repository, 1)
        metadata.status = PlanStatus.COMPLETED
        metadata.branch_name = "issue-1-20240101-120000"
        plan_store.update_metadata(metadata)

        items = _find_implementations_waiting_review(
            repository, issue_store, plan_store, None, None
        )
        assert len(items) == 1

    def test_skips_when_pr_exists(self, tmp_path):
        """Test that implementations with PR are skipped."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")
        _, metadata = plan_store.get_latest_plan(repository, 1)
        metadata.status = PlanStatus.COMPLETED
        metadata.branch_name = "issue-1-20240101-120000"
        metadata.pr_url = "https://github.com/owner/repo/pull/1"
        plan_store.update_metadata(metadata)

        items = _find_implementations_waiting_review(
            repository, issue_store, plan_store, None, None
        )
        assert len(items) == 0


class TestFindIssuesWithApprovedPlans:
    """Tests for _find_issues_with_approved_plans."""

    def test_finds_approved_plans(self, tmp_path):
        """Test finding issues with approved plans."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")
        _, metadata = plan_store.get_latest_plan(repository, 1)
        metadata.status = PlanStatus.APPROVED
        plan_store.update_metadata(metadata)

        items = _find_issues_with_approved_plans(repository, issue_store, plan_store, [1])
        assert len(items) == 1

    def test_skips_pending_plans(self, tmp_path):
        """Test that pending plans are skipped."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")

        items = _find_issues_with_approved_plans(repository, issue_store, plan_store, [1])
        assert len(items) == 0


class TestUnapprovePlanCommand:
    """Tests for unapprove_plan_command."""

    def test_unapproves_plan(self, tmp_path, monkeypatch):
        """Test that unapprove reverts status to pending."""
        monkeypatch.setenv("HOME", str(tmp_path))
        config_dir = tmp_path / ".config" / "gh-worker"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.yaml"
        config_file.write_text(f"issues_path: {tmp_path}\n")

        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")
        _, metadata = plan_store.get_latest_plan(repository, 1)
        metadata.status = PlanStatus.APPROVED
        plan_store.update_metadata(metadata)

        result = unapprove_plan_command("owner/repo", 1, config_path=config_dir / "config.yaml")
        assert result is True

        _, metadata = plan_store.get_latest_plan(repository, 1)
        assert metadata.status == PlanStatus.PENDING

    def test_returns_false_when_no_approved_plan(self, tmp_path, monkeypatch):
        """Test that unapprove returns False when plan is not approved."""
        monkeypatch.setenv("HOME", str(tmp_path))
        config_dir = tmp_path / ".config" / "gh-worker"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.yaml"
        config_file.write_text(f"issues_path: {tmp_path}\n")

        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_path)
        plan_store = PlanStore(tmp_path)

        issue_dir = issue_store.get_issue_dir(repository, 1)
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "description.md").write_text("Issue 1")
        plan_store.create_plan(repository, 1, "Plan 1")
        # Plan is PENDING, not APPROVED

        result = unapprove_plan_command("owner/repo", 1, config_path=config_dir / "config.yaml")
        assert result is False
