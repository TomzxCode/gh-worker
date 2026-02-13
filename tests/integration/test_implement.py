"""Integration tests for implement command."""

import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gh_worker.agents.base import AgentEvent, AgentEventType
from gh_worker.commands.implement import (
    ImplementTask,
    find_issues_needing_implementation,
    implement_issue,
)
from gh_worker.models.plan import PlanStatus
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore
from gh_worker.storage.plan_store import PlanStore


@pytest.fixture
def tmp_config_path(tmp_path):
    """Fixture for temporary config path."""
    return tmp_path / "config.yaml"


@pytest.fixture
def tmp_issues_path(tmp_path):
    """Fixture for temporary issues path."""
    return tmp_path / "issues"


@pytest.fixture
def tmp_repository_path(tmp_path):
    """Fixture for temporary repository path."""
    return tmp_path / "repos"


@pytest.fixture
def mock_agent():
    """Fixture for mocked agent."""
    agent = MagicMock()
    agent.name = "test-agent"
    agent.requires_cli = False
    agent.validate_environment = AsyncMock(return_value=(True, None))

    async def mock_implement(*args, **kwargs):
        """Mock implement that yields events and creates a file for commit."""
        repository_path = kwargs.get("repository_path", args[2] if len(args) > 2 else "")
        if repository_path:
            from pathlib import Path
            (Path(repository_path) / "implemented.py").write_text("# Implementation by agent\n")
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content="Starting implementation",
        )
        yield AgentEvent(
            type=AgentEventType.OUTPUT,
            content="Implementing changes",
        )
        yield AgentEvent(
            type=AgentEventType.COMPLETION,
            content="Implementation completed",
            metadata={
                "session_id": "test-session-123",
                "pr_url": "https://github.com/owner/repo/pull/1",
            },
        )

    async def mock_commit(*args, **kwargs):
        """Mock commit that yields commit message events."""
        yield AgentEvent(
            type=AgentEventType.OUTPUT,
            content="Fix: implement test changes",
        )
        yield AgentEvent(
            type=AgentEventType.COMPLETION,
            content="Commit completed",
        )

    agent.implement = mock_implement
    agent.commit = mock_commit
    return agent


@pytest.fixture
def sample_issue_content():
    """Fixture for sample issue content."""
    return """# Test Issue

**Issue**: #123
**Repository**: owner/repo
**State**: open
**Author**: testuser
**Created**: 2024-01-01T12:00:00+00:00
**Updated**: 2024-01-02T12:00:00+00:00
**URL**: https://github.com/owner/repo/issues/123
**Labels**: bug

---

This is a test issue description.
"""


@pytest.fixture
def sample_plan_content():
    """Fixture for sample plan content."""
    return """# Implementation Plan

## Overview
This is a test implementation plan.

## Steps
1. Step 1
2. Step 2
3. Step 3
"""


class TestFindIssuesNeedingImplementation:
    """Tests for find_issues_needing_implementation function."""

    def test_find_issues_with_pending_plans(self, tmp_issues_path):
        """Test finding issues that have pending plans."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues with plans
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        tasks = find_issues_needing_implementation(repository, issue_store, plan_store)

        assert len(tasks) == 3
        assert all(isinstance(task, ImplementTask) for task in tasks)
        assert [task.issue_number for task in tasks] == [1, 2, 3]

    def test_skip_completed_implementations(self, tmp_issues_path):
        """Test that issues with completed implementations are skipped."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues with plans
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        # Mark issue 2 as completed
        _, metadata = plan_store.get_latest_plan(repository, 2)
        metadata.status = PlanStatus.COMPLETED
        plan_store.update_metadata(metadata)

        tasks = find_issues_needing_implementation(repository, issue_store, plan_store)

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

    def test_skip_in_progress_implementations(self, tmp_issues_path):
        """Test that issues in progress are skipped (unless explicitly requested)."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues with plans
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        # Mark issue 2 as in progress
        _, metadata = plan_store.get_latest_plan(repository, 2)
        metadata.status = PlanStatus.IN_PROGRESS
        plan_store.update_metadata(metadata)

        tasks = find_issues_needing_implementation(repository, issue_store, plan_store)

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

    def test_include_in_progress_when_explicitly_requested(self, tmp_issues_path):
        """Test that in-progress issues are included when explicitly requested."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues with plans
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        # Mark issue 2 as in progress
        _, metadata = plan_store.get_latest_plan(repository, 2)
        metadata.status = PlanStatus.IN_PROGRESS
        plan_store.update_metadata(metadata)

        tasks = find_issues_needing_implementation(
            repository, issue_store, plan_store, issue_numbers=[2]
        )

        assert len(tasks) == 1
        assert tasks[0].issue_number == 2

    def test_skip_issues_without_plans(self, tmp_issues_path):
        """Test that issues without plans are skipped."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues but only add plans to some
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            if issue_number in [1, 3]:
                plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        tasks = find_issues_needing_implementation(repository, issue_store, plan_store)

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

    def test_filter_by_issue_numbers(self, tmp_issues_path):
        """Test filtering by specific issue numbers."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues with plans
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            plan_store.create_plan(repository, issue_number, f"Plan {issue_number}")

        tasks = find_issues_needing_implementation(
            repository, issue_store, plan_store, issue_numbers=[1, 3]
        )

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]


class TestImplementIssue:
    """Tests for implement_issue function."""

    async def test_implement_success(
        self,
        tmp_issues_path,
        tmp_repository_path,
        mock_agent,
        sample_issue_content,
        sample_plan_content,
    ):
        """Test successful implementation."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create repository directory and initialize git repo
        repo_path = tmp_repository_path / repository.owner / repository.name
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
        (repo_path / "README.md").write_text("# Test repo")
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@test.com", "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@test.com"},
        )

        # Create issue and plan
        issue_dir = issue_store.get_issue_dir(repository, 123)
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        plan_store.create_plan(repository, 123, sample_plan_content)
        plan_file, _ = plan_store.get_latest_plan(repository, 123)

        task = ImplementTask(
            repository=repository,
            issue_number=123,
            plan_file=plan_file,
            plan_content=sample_plan_content,
            description_file=description_file,
        )

        with patch("gh_worker.commands.implement.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            await implement_issue(task, plan_store, tmp_repository_path, "test-agent", {})

            # Verify agent was called
            mock_agent.validate_environment.assert_called_once()

            # Verify metadata was updated
            _, metadata = plan_store.get_latest_plan(repository, 123)
            assert metadata.status == PlanStatus.COMPLETED
            assert metadata.branch_name is not None
            assert metadata.branch_name.startswith("issue-123-")
            assert metadata.session_id == "test-session-123"
            assert metadata.pr_url == "https://github.com/owner/repo/pull/1"
            assert metadata.completed_at is not None

    async def test_implement_agent_validation_failure(
        self,
        tmp_issues_path,
        tmp_repository_path,
        mock_agent,
        sample_issue_content,
        sample_plan_content,
    ):
        """Test implementation with agent validation failure."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create repository directory
        repo_path = tmp_repository_path / repository.owner / repository.name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create issue and plan
        issue_dir = issue_store.get_issue_dir(repository, 123)
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        plan_store.create_plan(repository, 123, sample_plan_content)
        plan_file, _ = plan_store.get_latest_plan(repository, 123)

        task = ImplementTask(
            repository=repository,
            issue_number=123,
            plan_file=plan_file,
            plan_content=sample_plan_content,
            description_file=description_file,
        )

        # Make validation fail
        mock_agent.validate_environment = AsyncMock(return_value=(False, "Test error"))

        with patch("gh_worker.commands.implement.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            with pytest.raises(RuntimeError, match="Agent environment validation failed"):
                await implement_issue(task, plan_store, tmp_repository_path, "test-agent", {})

            # Verify metadata was updated with failure
            _, metadata = plan_store.get_latest_plan(repository, 123)
            assert metadata.status == PlanStatus.FAILED
            assert metadata.error_message is not None

    async def test_implement_repository_not_found(
        self,
        tmp_issues_path,
        tmp_repository_path,
        mock_agent,
        sample_issue_content,
        sample_plan_content,
    ):
        """Test implementation when repository doesn't exist."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issue and plan but NOT the repository directory
        issue_dir = issue_store.get_issue_dir(repository, 123)
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        plan_store.create_plan(repository, 123, sample_plan_content)
        plan_file, _ = plan_store.get_latest_plan(repository, 123)

        task = ImplementTask(
            repository=repository,
            issue_number=123,
            plan_file=plan_file,
            plan_content=sample_plan_content,
            description_file=description_file,
        )

        with patch("gh_worker.commands.implement.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            with pytest.raises(FileNotFoundError, match="Repository not found"):
                await implement_issue(task, plan_store, tmp_repository_path, "test-agent", {})

            # Verify metadata was updated with failure
            _, metadata = plan_store.get_latest_plan(repository, 123)
            assert metadata.status == PlanStatus.FAILED
            assert metadata.error_message is not None

    async def test_implement_with_failure_event(
        self,
        tmp_issues_path,
        tmp_repository_path,
        mock_agent,
        sample_issue_content,
        sample_plan_content,
    ):
        """Test implementation when agent returns failure event."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create repository directory
        repo_path = tmp_repository_path / repository.owner / repository.name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create issue and plan
        issue_dir = issue_store.get_issue_dir(repository, 123)
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        plan_store.create_plan(repository, 123, sample_plan_content)
        plan_file, _ = plan_store.get_latest_plan(repository, 123)

        task = ImplementTask(
            repository=repository,
            issue_number=123,
            plan_file=plan_file,
            plan_content=sample_plan_content,
            description_file=description_file,
        )

        # Mock agent that yields failure event
        async def mock_implement_failure(*args, **kwargs):
            yield AgentEvent(
                type=AgentEventType.STATUS,
                content="Starting implementation",
            )
            yield AgentEvent(
                type=AgentEventType.FAILURE,
                content="Test failure message",
            )

        mock_agent.implement = mock_implement_failure

        with patch("gh_worker.commands.implement.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            with pytest.raises(RuntimeError, match="Implementation failed: Test failure message"):
                await implement_issue(task, plan_store, tmp_repository_path, "test-agent", {})

            # Verify metadata was updated with failure
            _, metadata = plan_store.get_latest_plan(repository, 123)
            assert metadata.status == PlanStatus.FAILED
            assert metadata.error_message == "Implementation failed: Test failure message"
