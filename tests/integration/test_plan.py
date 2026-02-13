"""Integration tests for plan command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gh_worker.agents.base import AgentResult
from gh_worker.commands.plan import (
    PlanTask,
    find_issues_needing_plans,
    generate_plan_for_issue,
)
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
    agent.plan = AsyncMock(
        return_value=AgentResult(
            success=True,
            output="# Implementation Plan\n\nThis is a test plan.",
        )
    )
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


class TestFindIssuesNeedingPlans:
    """Tests for find_issues_needing_plans function."""

    def test_find_issues_without_plans(self, tmp_issues_path):
        """Test finding issues that don't have plans yet."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issue directories with description files
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")

        tasks = find_issues_needing_plans(repository, issue_store, plan_store)

        assert len(tasks) == 3
        assert all(isinstance(task, PlanTask) for task in tasks)
        assert [task.issue_number for task in tasks] == [1, 2, 3]

    def test_skip_issues_with_existing_plans(self, tmp_issues_path):
        """Test that issues with existing plans are skipped."""
        from datetime import datetime

        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")
            # Create .updated-at file for each issue (use fixed past timestamp)
            (issue_dir / ".updated-at").write_text(datetime(2024, 1, 1, 12, 0, 0).isoformat())

        # Create plan for issue 2 (plan will be created with current timestamp,
        # which is >= the .updated-at timestamp)
        plan_store.create_plan(repository, 2, "Existing plan")

        tasks = find_issues_needing_plans(repository, issue_store, plan_store)

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

    def test_filter_by_issue_numbers(self, tmp_issues_path):
        """Test filtering by specific issue numbers."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            (issue_dir / "description.md").write_text(f"Issue {issue_number}")

        tasks = find_issues_needing_plans(repository, issue_store, plan_store, issue_numbers=[1, 3])

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

    def test_skip_issues_without_description(self, tmp_issues_path):
        """Test that issues without description files are skipped."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issue directories, but only add description to some
        for issue_number in [1, 2, 3]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            if issue_number in [1, 3]:
                (issue_dir / "description.md").write_text(f"Issue {issue_number}")

        tasks = find_issues_needing_plans(repository, issue_store, plan_store)

        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

    def test_filter_by_assigned_to_me(self, tmp_issues_path):
        """Test filtering by assigned_to_me only includes assigned issues."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)
        plan_store = PlanStore(tmp_issues_path)

        # Create issues with different assignees (using markdown format from Issue.to_markdown)
        for issue_number, assignees in [(1, "alice"), (2, "bob"), (3, "alice, bob")]:
            issue_dir = issue_store.get_issue_dir(repository, issue_number)
            issue_dir.mkdir(parents=True, exist_ok=True)
            content = f"# Issue {issue_number}\n\n**Assignees**: {assignees}\n\n---\n\nBody"
            (issue_dir / "description.md").write_text(content)

        # Only alice's issues (1 and 3)
        tasks = find_issues_needing_plans(
            repository,
            issue_store,
            plan_store,
            assigned_to_me=True,
            current_user="alice",
        )
        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [1, 3]

        # Only bob's issues (2 and 3)
        tasks = find_issues_needing_plans(
            repository,
            issue_store,
            plan_store,
            assigned_to_me=True,
            current_user="bob",
        )
        assert len(tasks) == 2
        assert [task.issue_number for task in tasks] == [2, 3]


class TestGeneratePlanForIssue:
    """Tests for generate_plan_for_issue function."""

    async def test_generate_plan_success(
        self, tmp_issues_path, tmp_repository_path, mock_agent, sample_issue_content
    ):
        """Test successful plan generation."""
        repository = Repository(owner="owner", name="repo")
        plan_store = PlanStore(tmp_issues_path)

        # Create repository directory
        repo_path = tmp_repository_path / repository.owner / repository.name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create issue description
        issue_dir = tmp_issues_path / repository.owner / repository.name / "123"
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        task = PlanTask(
            repository=repository,
            issue_number=123,
            description_file=description_file,
        )

        with patch("gh_worker.commands.plan.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            issue_store = IssueStore(tmp_issues_path)
            await generate_plan_for_issue(
                task, plan_store, issue_store, tmp_repository_path, "test-agent", {}
            )

            # Verify agent was called
            mock_agent.validate_environment.assert_called_once()
            mock_agent.plan.assert_called_once()

            # Verify plan was saved
            plan_result = plan_store.get_latest_plan(repository, 123)
            assert plan_result is not None
            plan_file, metadata = plan_result
            assert plan_file.exists()
            assert "Implementation Plan" in plan_file.read_text()

    async def test_generate_plan_agent_validation_failure(
        self, tmp_issues_path, tmp_repository_path, mock_agent, sample_issue_content
    ):
        """Test plan generation with agent validation failure."""
        repository = Repository(owner="owner", name="repo")
        plan_store = PlanStore(tmp_issues_path)

        # Create repository directory
        repo_path = tmp_repository_path / repository.owner / repository.name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create issue description
        issue_dir = tmp_issues_path / repository.owner / repository.name / "123"
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        task = PlanTask(
            repository=repository,
            issue_number=123,
            description_file=description_file,
        )

        # Make validation fail
        mock_agent.validate_environment = AsyncMock(return_value=(False, "Test error"))

        with patch("gh_worker.commands.plan.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            issue_store = IssueStore(tmp_issues_path)
            with pytest.raises(RuntimeError, match="Agent environment validation failed"):
                await generate_plan_for_issue(
                    task, plan_store, issue_store, tmp_repository_path, "test-agent", {}
                )

    async def test_generate_plan_repository_not_found(
        self, tmp_issues_path, tmp_repository_path, mock_agent, sample_issue_content
    ):
        """Test plan generation when repository doesn't exist."""
        repository = Repository(owner="owner", name="repo")
        plan_store = PlanStore(tmp_issues_path)

        # Create issue description but NOT the repository directory
        issue_dir = tmp_issues_path / repository.owner / repository.name / "123"
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        task = PlanTask(
            repository=repository,
            issue_number=123,
            description_file=description_file,
        )

        with patch("gh_worker.commands.plan.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            issue_store = IssueStore(tmp_issues_path)
            with pytest.raises(FileNotFoundError, match="Repository not found"):
                await generate_plan_for_issue(
                    task, plan_store, issue_store, tmp_repository_path, "test-agent", {}
                )

    async def test_generate_plan_agent_failure(
        self, tmp_issues_path, tmp_repository_path, mock_agent, sample_issue_content
    ):
        """Test plan generation when agent returns failure."""
        repository = Repository(owner="owner", name="repo")
        plan_store = PlanStore(tmp_issues_path)

        # Create repository directory
        repo_path = tmp_repository_path / repository.owner / repository.name
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create issue description
        issue_dir = tmp_issues_path / repository.owner / repository.name / "123"
        issue_dir.mkdir(parents=True, exist_ok=True)
        description_file = issue_dir / "description.md"
        description_file.write_text(sample_issue_content)

        task = PlanTask(
            repository=repository,
            issue_number=123,
            description_file=description_file,
        )

        # Make plan generation fail
        mock_agent.plan = AsyncMock(
            return_value=AgentResult(
                success=False,
                output="",
                error="Test failure",
            )
        )

        with patch("gh_worker.commands.plan.get_registry") as mock_registry:
            mock_registry.return_value.get.return_value = mock_agent

            issue_store = IssueStore(tmp_issues_path)
            with pytest.raises(RuntimeError, match="Plan generation failed"):
                await generate_plan_for_issue(
                    task, plan_store, issue_store, tmp_repository_path, "test-agent", {}
                )
