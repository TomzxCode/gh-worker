"""Integration tests for sync command."""

from unittest.mock import MagicMock, patch

import pytest

from gh_worker.commands.sync import sync_command, sync_repository
from gh_worker.config.manager import ConfigManager
from gh_worker.config.schema import AppConfig
from gh_worker.github.client import GHClient
from gh_worker.models.repository import Repository
from gh_worker.storage.issue_store import IssueStore


@pytest.fixture
def tmp_config_path(tmp_path):
    """Fixture for temporary config path."""
    return tmp_path / "config.yaml"


@pytest.fixture
def tmp_issues_path(tmp_path):
    """Fixture for temporary issues path."""
    return tmp_path / "issues"


@pytest.fixture
def mock_gh_client():
    """Fixture for mocked GitHub client."""
    client = MagicMock(spec=GHClient)
    client.check_auth.return_value = True
    return client


@pytest.fixture
def sample_issue_data():
    """Fixture for sample issue data from GitHub."""
    return {
        "number": 123,
        "title": "Test Issue",
        "body": "Issue description",
        "state": "open",
        "createdAt": "2024-01-01T12:00:00Z",
        "updatedAt": "2024-01-02T12:00:00Z",
        "author": {"login": "testuser"},
        "labels": [{"name": "bug"}],
        "url": "https://github.com/owner/repo/issues/123",
    }


class TestSyncRepository:
    """Tests for sync_repository function."""

    def test_sync_repository_basic(self, tmp_issues_path, mock_gh_client, sample_issue_data):
        """Test basic repository sync."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)

        mock_gh_client.list_issues.return_value = [sample_issue_data]

        count = sync_repository(repository, issue_store, mock_gh_client)

        assert count == 1
        mock_gh_client.list_issues.assert_called_once()

        # Verify issue was saved
        issue_dir = issue_store.get_issue_dir(repository, 123)
        assert (issue_dir / "description.md").exists()
        assert (issue_dir / ".updated-at").exists()

    def test_sync_repository_with_issue_numbers(
        self, tmp_issues_path, mock_gh_client, sample_issue_data
    ):
        """Test sync with specific issue numbers."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)

        mock_gh_client.get_issue.return_value = sample_issue_data

        count = sync_repository(repository, issue_store, mock_gh_client, issue_numbers=[123])

        assert count == 1
        mock_gh_client.get_issue.assert_called_once_with(repository, 123)

    def test_sync_repository_updates_timestamp(
        self, tmp_issues_path, mock_gh_client, sample_issue_data
    ):
        """Test that repository timestamp is updated."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)

        mock_gh_client.list_issues.return_value = [sample_issue_data]

        sync_repository(repository, issue_store, mock_gh_client)

        # Verify repo timestamp was updated
        updated_at = issue_store.get_repo_updated_at(repository)
        assert updated_at is not None

    def test_sync_repository_assigned_to_me(
        self, tmp_issues_path, mock_gh_client, sample_issue_data
    ):
        """Test sync with assigned_to_me passes flag to list_issues."""
        repository = Repository(owner="owner", name="repo")
        issue_store = IssueStore(tmp_issues_path)

        mock_gh_client.list_issues.return_value = [sample_issue_data]

        sync_repository(repository, issue_store, mock_gh_client, assigned_to_me=True)

        mock_gh_client.list_issues.assert_called_once_with(
            repository, since=None, search=None, assigned_to_me=True
        )


class TestSyncCommand:
    """Tests for sync_command function."""

    def test_sync_command_single_repo(
        self, tmp_config_path, tmp_issues_path, mock_gh_client, sample_issue_data
    ):
        """Test syncing a single repository."""
        # Set up config
        config = ConfigManager(tmp_config_path)
        app_config = AppConfig(issues_path=tmp_issues_path)
        config.save(app_config)

        # Mock GHClient
        with patch("gh_worker.commands.sync.GHClient", return_value=mock_gh_client):
            mock_gh_client.list_issues.return_value = [sample_issue_data]

            sync_command(repo="owner/repo", config_path=tmp_config_path)

            mock_gh_client.list_issues.assert_called_once()

    def test_sync_command_all_repos(
        self, tmp_config_path, tmp_issues_path, mock_gh_client, sample_issue_data
    ):
        """Test syncing all repositories."""
        # Set up config
        config = ConfigManager(tmp_config_path)
        app_config = AppConfig(issues_path=tmp_issues_path)
        config.save(app_config)

        # Create repository directories
        issue_store = IssueStore(tmp_issues_path)
        repo1 = Repository(owner="owner1", name="repo1")
        repo2 = Repository(owner="owner2", name="repo2")
        issue_store.get_repo_dir(repo1).mkdir(parents=True, exist_ok=True)
        issue_store.get_repo_dir(repo2).mkdir(parents=True, exist_ok=True)

        # Mock GHClient
        with patch("gh_worker.commands.sync.GHClient", return_value=mock_gh_client):
            mock_gh_client.list_issues.return_value = [sample_issue_data]

            sync_command(all_repos=True, config_path=tmp_config_path)

            assert mock_gh_client.list_issues.call_count == 2

    def test_sync_command_no_config(self, tmp_config_path, mock_gh_client, capsys):
        """Test sync command with missing configuration."""
        sync_command(repo="owner/repo", config_path=tmp_config_path)

        captured = capsys.readouterr()
        assert "issues-path not configured" in captured.out

    def test_sync_command_not_authenticated(self, tmp_config_path, tmp_issues_path, capsys):
        """Test sync command when not authenticated."""
        # Set up config
        config = ConfigManager(tmp_config_path)
        app_config = AppConfig(issues_path=tmp_issues_path)
        config.save(app_config)

        # Mock GHClient with auth failure
        mock_client = MagicMock(spec=GHClient)
        mock_client.check_auth.return_value = False

        with patch("gh_worker.commands.sync.GHClient", return_value=mock_client):
            sync_command(repo="owner/repo", config_path=tmp_config_path)

            captured = capsys.readouterr()
            assert "not authenticated" in captured.out
