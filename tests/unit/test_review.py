"""Unit tests for review commands."""

import pytest

from gh_worker.commands.review import (
    _find_implementations_waiting_review,
    _find_issues_with_plans_waiting_review,
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
