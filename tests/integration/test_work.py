"""Integration tests for work command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gh_worker.commands.work import work_command_async
from gh_worker.config.manager import ConfigManager
from gh_worker.config.schema import AppConfig
from gh_worker.executor.orchestrator import WorkOrchestrator


@pytest.fixture
def tmp_config_path(tmp_path):
    """Fixture for temporary config path."""
    config_path = tmp_path / "config.yaml"
    config_manager = ConfigManager(config_path)

    # Set up minimal config
    app_config = AppConfig(
        issues_path=tmp_path / "issues",
        repository_path=tmp_path / "repos",
    )
    config_manager.save(app_config)

    return config_path


@pytest.fixture
def tmp_issues_path(tmp_path):
    """Fixture for temporary issues path."""
    issues_path = tmp_path / "issues"
    issues_path.mkdir(parents=True, exist_ok=True)
    return issues_path


@pytest.fixture
def tmp_repository_path(tmp_path):
    """Fixture for temporary repository path."""
    repos_path = tmp_path / "repos"
    repos_path.mkdir(parents=True, exist_ok=True)
    return repos_path


class TestWorkOrchestrator:
    """Tests for WorkOrchestrator class."""

    async def test_run_cycle_single_repo(
        self, tmp_config_path, tmp_issues_path, tmp_repository_path
    ):
        """Test running a single work cycle with one repository."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo"],
            since=None,
            issue_numbers=None,
        )

        with (
            patch("gh_worker.executor.orchestrator.sync_command") as mock_sync,
            patch("gh_worker.executor.orchestrator.plan_command_async") as mock_plan,
            patch("gh_worker.executor.orchestrator.implement_command_async") as mock_implement,
        ):
            await orchestrator.run_cycle()

            # Verify sync was called
            mock_sync.assert_called_once_with(
                repo="owner/repo",
                all_repos=False,
                since=None,
                issue_numbers=None,
                search=None,
                config_path=tmp_config_path,
            )

            # Verify plan was called
            mock_plan.assert_called_once_with(
                repo="owner/repo",
                issue_numbers=None,
                all_repos=False,
                parallelism=None,
                force=False,
                config_path=tmp_config_path,
                agent=None,
            )

            # Verify implement was called
            mock_implement.assert_called_once_with(
                repo="owner/repo",
                issue_numbers=None,
                all_repos=False,
                parallelism=None,
                force=False,
                config_path=tmp_config_path,
                agent=None,
            )

    async def test_run_cycle_multiple_repos(self, tmp_config_path):
        """Test running a single work cycle with multiple repositories."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo1", "owner/repo2"],
            since=None,
            issue_numbers=None,
        )

        with (
            patch("gh_worker.executor.orchestrator.sync_command") as mock_sync,
            patch("gh_worker.executor.orchestrator.plan_command_async") as mock_plan,
            patch("gh_worker.executor.orchestrator.implement_command_async") as mock_implement,
        ):
            await orchestrator.run_cycle()

            # Verify sync was called for both repos
            assert mock_sync.call_count == 2
            mock_sync.assert_any_call(
                repo="owner/repo1",
                all_repos=False,
                since=None,
                issue_numbers=None,
                search=None,
                config_path=tmp_config_path,
            )
            mock_sync.assert_any_call(
                repo="owner/repo2",
                all_repos=False,
                since=None,
                issue_numbers=None,
                search=None,
                config_path=tmp_config_path,
            )

            # Verify plan was called for both repos
            assert mock_plan.call_count == 2
            assert mock_implement.call_count == 2

    async def test_run_cycle_all_repos(self, tmp_config_path):
        """Test running a work cycle for all repositories."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=None,
            since=None,
            issue_numbers=None,
        )

        with (
            patch("gh_worker.executor.orchestrator.sync_command") as mock_sync,
            patch("gh_worker.executor.orchestrator.plan_command_async") as mock_plan,
            patch("gh_worker.executor.orchestrator.implement_command_async") as mock_implement,
        ):
            await orchestrator.run_cycle()

            # Verify sync was called with all_repos=True
            mock_sync.assert_called_once_with(
                repo=None,
                all_repos=True,
                since=None,
                issue_numbers=None,
                search=None,
                config_path=tmp_config_path,
            )

            # Verify plan was called with all_repos=True
            mock_plan.assert_called_once_with(
                repo=None,
                issue_numbers=None,
                all_repos=True,
                parallelism=None,
                force=False,
                config_path=tmp_config_path,
                agent=None,
            )

            # Verify implement was called with all_repos=True
            mock_implement.assert_called_once_with(
                repo=None,
                issue_numbers=None,
                all_repos=True,
                parallelism=None,
                force=False,
                config_path=tmp_config_path,
                agent=None,
            )

    async def test_run_cycle_with_filters(self, tmp_config_path):
        """Test running a work cycle with filters."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo"],
            since="2024-01-01T00:00:00Z",
            issue_numbers=[1, 2, 3],
        )

        with (
            patch("gh_worker.executor.orchestrator.sync_command") as mock_sync,
            patch("gh_worker.executor.orchestrator.plan_command_async") as mock_plan,
            patch("gh_worker.executor.orchestrator.implement_command_async") as mock_implement,
        ):
            await orchestrator.run_cycle()

            # Verify filters were passed
            mock_sync.assert_called_once()
            args = mock_sync.call_args
            assert args.kwargs["since"] == "2024-01-01T00:00:00Z"
            assert args.kwargs["issue_numbers"] == [1, 2, 3]

            mock_plan.assert_called_once()
            args = mock_plan.call_args
            assert args.kwargs["issue_numbers"] == [1, 2, 3]

            mock_implement.assert_called_once()
            args = mock_implement.call_args
            assert args.kwargs["issue_numbers"] == [1, 2, 3]

    async def test_run_once(self, tmp_config_path):
        """Test running work once."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo"],
        )

        with patch.object(orchestrator, "run_cycle", new_callable=AsyncMock) as mock_run_cycle:
            await orchestrator.run_once()

            # Verify run_cycle was called exactly once
            mock_run_cycle.assert_called_once()

    async def test_run_continuous_single_cycle(self, tmp_config_path):
        """Test running work continuously (with early termination)."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo"],
        )

        cycle_count = 0

        async def mock_run_cycle():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 2:
                # Stop after 2 cycles
                raise KeyboardInterrupt("Test stop")

        async def mock_sleep(seconds):
            # Don't actually sleep in test
            pass

        with (
            patch.object(orchestrator, "run_cycle", new_callable=AsyncMock) as mock_cycle,
            patch(
                "gh_worker.executor.orchestrator.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep_patch,
        ):
            mock_cycle.side_effect = mock_run_cycle
            mock_sleep_patch.side_effect = mock_sleep

            with pytest.raises(KeyboardInterrupt):
                await orchestrator.run_continuous("10m")

            # Verify run_cycle was called twice
            assert mock_cycle.call_count == 2

            # Verify sleep was called with correct duration (600 seconds = 10 minutes)
            mock_sleep_patch.assert_called_with(600.0)

    async def test_run_continuous_handles_errors(self, tmp_config_path):
        """Test that run_continuous handles errors gracefully."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo"],
        )

        cycle_count = 0

        async def mock_run_cycle():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count == 1:
                # First cycle fails
                raise RuntimeError("Test error")
            elif cycle_count >= 2:
                # Stop after second cycle
                raise KeyboardInterrupt("Test stop")

        async def mock_sleep(seconds):
            # Don't actually sleep in test
            pass

        with (
            patch.object(orchestrator, "run_cycle", new_callable=AsyncMock) as mock_cycle,
            patch(
                "gh_worker.executor.orchestrator.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep_patch,
        ):
            mock_cycle.side_effect = mock_run_cycle
            mock_sleep_patch.side_effect = mock_sleep

            with pytest.raises(KeyboardInterrupt):
                await orchestrator.run_continuous("1h")

            # Verify run_cycle was called twice (once failed, once succeeded)
            assert mock_cycle.call_count == 2

    async def test_run_continuous_invalid_frequency(self, tmp_config_path):
        """Test running continuous with invalid frequency."""
        orchestrator = WorkOrchestrator(
            config_path=tmp_config_path,
            repos=["owner/repo"],
        )

        with patch.object(orchestrator, "run_cycle", new_callable=AsyncMock) as mock_run_cycle:
            # Should handle invalid frequency gracefully
            await orchestrator.run_continuous("invalid")

            # Should not run cycle if frequency is invalid
            mock_run_cycle.assert_not_called()

    async def test_run_cycle_missing_issues_path(self, tmp_path):
        """Test run_cycle with missing issues_path configuration."""
        config_path = tmp_path / "config.yaml"
        config_manager = ConfigManager(config_path)

        # Create config without issues_path
        app_config = AppConfig()
        config_manager.save(app_config)

        orchestrator = WorkOrchestrator(
            config_path=config_path,
            repos=["owner/repo"],
        )

        with patch("gh_worker.executor.orchestrator.sync_command") as mock_sync:
            await orchestrator.run_cycle()

            # Should not call sync if issues_path is not configured
            mock_sync.assert_not_called()


class TestWorkCommand:
    """Tests for work_command function."""

    async def test_work_command_once(self, tmp_config_path):
        """Test work command in one-shot mode."""
        with patch("gh_worker.commands.work.WorkOrchestrator") as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.run_once = AsyncMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            await work_command_async(
                once=True,
                frequency=None,
                repos=["owner/repo"],
                since=None,
                issue_numbers=None,
                config_path=tmp_config_path,
            )

            # Verify orchestrator was created with correct parameters
            mock_orchestrator_class.assert_called_once_with(
                config_path=tmp_config_path,
                repos=["owner/repo"],
                since=None,
                issue_numbers=None,
                agent=None,
            )

            # Verify run_once was called
            mock_orchestrator.run_once.assert_called_once()

            # Verify run_continuous was not called
            assert (
                not hasattr(mock_orchestrator, "run_continuous")
                or mock_orchestrator.run_continuous.call_count == 0
            )

    async def test_work_command_continuous_with_frequency(self, tmp_config_path):
        """Test work command in continuous mode with explicit frequency."""
        with patch("gh_worker.commands.work.WorkOrchestrator") as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.run_continuous = AsyncMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            await work_command_async(
                once=False,
                frequency="30m",
                repos=["owner/repo"],
                since=None,
                issue_numbers=None,
                config_path=tmp_config_path,
            )

            # Verify run_continuous was called with correct frequency
            mock_orchestrator.run_continuous.assert_called_once_with("30m")

    async def test_work_command_continuous_with_config_frequency(self, tmp_config_path):
        """Test work command in continuous mode using config frequency."""
        # Update config with custom frequency
        config_manager = ConfigManager(tmp_config_path)
        app_config = config_manager.load()
        app_config.sync.frequency = "2h"
        config_manager.save(app_config)

        with patch("gh_worker.commands.work.WorkOrchestrator") as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.run_continuous = AsyncMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            await work_command_async(
                once=False,
                frequency=None,  # Should use config frequency
                repos=None,
                since=None,
                issue_numbers=None,
                config_path=tmp_config_path,
            )

            # Verify run_continuous was called with config frequency
            mock_orchestrator.run_continuous.assert_called_once_with("2h")

    async def test_work_command_with_all_filters(self, tmp_config_path):
        """Test work command with all filters specified."""
        with patch("gh_worker.commands.work.WorkOrchestrator") as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.run_once = AsyncMock()
            mock_orchestrator_class.return_value = mock_orchestrator

            await work_command_async(
                once=True,
                frequency=None,
                repos=["owner/repo1", "owner/repo2"],
                since="2024-01-01T00:00:00Z",
                issue_numbers=[1, 2, 3],
                config_path=tmp_config_path,
            )

            # Verify orchestrator was created with all filters
            mock_orchestrator_class.assert_called_once_with(
                config_path=tmp_config_path,
                repos=["owner/repo1", "owner/repo2"],
                since="2024-01-01T00:00:00Z",
                issue_numbers=[1, 2, 3],
                agent=None,
            )
