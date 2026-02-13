"""Dashboard view - repos, issues, quick actions, activity."""

from pathlib import Path

from textual.containers import Container, Horizontal, HorizontalScroll, Vertical
from textual.widgets import Button, DataTable, Input, Label, Select
from textual.worker import Worker, WorkerState

from gh_worker.commands.issues_list import (
    IMPL_BEING_GENERATED,
    IMPL_FAILED,
    IMPL_MERGED,
    IMPL_NONE,
    IMPL_PR_OPENED,
    IMPL_WAITING_FOR_REVIEW,
    PLAN_APPROVED,
    PLAN_BEING_GENERATED,
    PLAN_NONE,
    PLAN_WAITING_FOR_REVIEW,
)
from gh_worker.tui.data import get_issues, get_repositories
from gh_worker.tui.state import load_state, save_state
from gh_worker.tui.widgets.activity_log import ActivityLog
from gh_worker.tui.widgets.issue_table import IssueTable
from gh_worker.tui.widgets.quick_actions import QuickActions

PLAN_OPTIONS = [
    ("all", None),
    (PLAN_NONE, PLAN_NONE),
    (PLAN_BEING_GENERATED, PLAN_BEING_GENERATED),
    (PLAN_WAITING_FOR_REVIEW, PLAN_WAITING_FOR_REVIEW),
    (PLAN_APPROVED, PLAN_APPROVED),
]

IMPL_OPTIONS = [
    ("all", None),
    (IMPL_NONE, IMPL_NONE),
    (IMPL_BEING_GENERATED, IMPL_BEING_GENERATED),
    (IMPL_WAITING_FOR_REVIEW, IMPL_WAITING_FOR_REVIEW),
    (IMPL_PR_OPENED, IMPL_PR_OPENED),
    (IMPL_MERGED, IMPL_MERGED),
    (IMPL_FAILED, IMPL_FAILED),
]

STATE_OPTIONS = [
    ("all", None),
    ("open", "open"),
    ("closed", "closed"),
]


class DashboardView(Container):
    """Dashboard with repos list, issues table, quick actions, and activity log."""

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path
        self._selected_repo: str | None = None
        self._repos: list[str] = []
        self._issues_table: IssueTable | None = None

    def compose(self):
        """Compose dashboard layout."""
        with Horizontal():
            with Vertical(id="left-panel"):
                yield Label("Repositories", classes="section-title")
                yield DataTable(id="repos-list", cursor_type="row")
            with Vertical(id="right-panel"):
                yield Label("Issues", classes="section-title")
                with HorizontalScroll(id="dashboard-filters"):
                    with Horizontal():
                        yield Input(placeholder="Title", id="filter-title")
                        yield Input(placeholder="Author", id="filter-author")
                        yield Input(placeholder="Assignee", id="filter-assignee")
                        yield Select(
                            PLAN_OPTIONS, prompt="Plan", allow_blank=True, id="filter-plan"
                        )
                        yield Select(
                            IMPL_OPTIONS, prompt="Impl", allow_blank=True, id="filter-impl"
                        )
                        yield Select(
                            STATE_OPTIONS, prompt="State", allow_blank=True, id="filter-state"
                        )
                self._issues_table = IssueTable(id="issues-table")
                yield self._issues_table
        yield QuickActions(id="quick-actions")
        yield Label("Activity", classes="section-title")
        yield ActivityLog(id="activity-log")

    def on_mount(self) -> None:
        """Load data on mount."""
        state = load_state()
        try:
            title_input = self.query_one("#filter-title", Input)
            if state.get("title_filter"):
                title_input.value = state["title_filter"]
            plan_select = self.query_one("#filter-plan", Select)
            plan_val = state.get("plan_filter")
            if plan_val in (
                None,
                PLAN_NONE,
                PLAN_BEING_GENERATED,
                PLAN_WAITING_FOR_REVIEW,
                PLAN_APPROVED,
            ):
                plan_select.value = plan_val
            impl_select = self.query_one("#filter-impl", Select)
            impl_val = state.get("implementation_filter")
            if impl_val in (
                None,
                IMPL_NONE,
                IMPL_BEING_GENERATED,
                IMPL_WAITING_FOR_REVIEW,
                IMPL_PR_OPENED,
                IMPL_MERGED,
                IMPL_FAILED,
            ):
                impl_select.value = impl_val
            state_select = self.query_one("#filter-state", Select)
            state_val = state.get("state_filter")
            if state_val in (None, "open", "closed"):
                state_select.value = state_val
            author_input = self.query_one("#filter-author", Input)
            if state.get("author_filter"):
                author_input.value = state["author_filter"]
            assignee_input = self.query_one("#filter-assignee", Input)
            if state.get("assignee_filter"):
                assignee_input.value = state["assignee_filter"]
        except Exception:
            pass
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh repositories and issues."""
        state = load_state()
        repos = get_repositories(self.config_path)
        self._repos = [r.full_name for r in repos]
        self._selected_repo = state.get("last_repo")
        if self._selected_repo not in self._repos and self._repos:
            self._selected_repo = self._repos[0]

        repos_table = self.query_one("#repos-list", DataTable)
        repos_table.clear(columns=True)
        repos_table.add_column("Repository")
        for repo_name in self._repos:
            repos_table.add_row(repo_name, key=repo_name)

        self._refresh_issues()

    def _refresh_issues(self) -> None:
        """Refresh issues table for selected repo."""
        if not self._issues_table or not self._selected_repo:
            return
        state = load_state()
        issues = get_issues(
            repo=self._selected_repo,
            title_filter=state.get("title_filter"),
            plan_filter=state.get("plan_filter"),
            implementation_filter=state.get("implementation_filter"),
            assignee_filter=state.get("assignee_filter"),
            author_filter=state.get("author_filter"),
            state_filter=state.get("state_filter"),
            config_path=self.config_path,
        )
        rows = [
            (
                repo.full_name,
                issue_number,
                title,
                author,
                assignees,
                plan_status,
                impl_status,
                state,
            )
            for (
                repo,
                issue_number,
                title,
                author,
                assignees,
                plan_status,
                impl_status,
                state,
            ) in issues
        ]
        self._issues_table.clear_and_populate(rows)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle plan/impl filter change."""
        val = event.select.value
        filter_val = str(val) if val is not Select.BLANK and val else None
        if event.select.id == "filter-plan":
            save_state(plan_filter=filter_val)
        elif event.select.id == "filter-impl":
            save_state(implementation_filter=filter_val)
        elif event.select.id == "filter-state":
            save_state(state_filter=filter_val)
        self._refresh_issues()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle filter input - save and refresh."""
        save_state(
            title_filter=self.query_one("#filter-title", Input).value.strip() or None,
            author_filter=self.query_one("#filter-author", Input).value.strip() or None,
            assignee_filter=self.query_one("#filter-assignee", Input).value.strip() or None,
        )
        self._refresh_issues()

    def on_data_table_row_selected(self, event) -> None:
        """Handle repo selection."""
        if event.control.id != "repos-list":
            return
        row_key = event.row_key
        if row_key is not None:
            self._selected_repo = str(row_key)
            save_state(last_repo=self._selected_repo)
            self._refresh_issues()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle quick action button presses."""
        bid = event.button.id
        if bid is None:
            return
        if bid == "sync":
            self._run_sync()
        elif bid == "plan":
            self._run_plan()
        elif bid == "implement":
            self._run_implement()
        elif bid == "work-once":
            self._run_work_once()
        elif bid == "monitor":
            self._run_monitor()

    def _run_sync(self) -> None:
        """Run sync in worker."""
        from gh_worker.tui.workers import run_sync

        def _sync() -> tuple[bool, str]:
            return run_sync(
                repo=self._selected_repo if self._selected_repo else None,
                all_repos=not bool(self._selected_repo),
                config_path=self.config_path,
            )

        self.run_worker(
            _sync,
            name="sync",
            group="commands",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self._log_activity("Sync started...")
        self._set_running(True)

    def _run_plan(self) -> None:
        """Run plan in worker."""
        from gh_worker.tui.workers import run_plan

        async def _plan() -> tuple[bool, str]:
            return await run_plan(
                repo=self._selected_repo if self._selected_repo else None,
                all_repos=not bool(self._selected_repo),
                config_path=self.config_path,
            )

        self.run_worker(
            _plan(),
            name="plan",
            group="commands",
            exit_on_error=False,
            exclusive=True,
        )
        self._log_activity("Plan started...")
        self._set_running(True)

    def _run_implement(self) -> None:
        """Run implement in worker."""
        from gh_worker.tui.workers import run_implement

        async def _implement() -> tuple[bool, str]:
            return await run_implement(
                repo=self._selected_repo if self._selected_repo else None,
                all_repos=not bool(self._selected_repo),
                config_path=self.config_path,
            )

        self.run_worker(
            _implement(),
            name="implement",
            group="commands",
            exit_on_error=False,
            exclusive=True,
        )
        self._log_activity("Implement started...")
        self._set_running(True)

    def _run_work_once(self) -> None:
        """Run work --once in worker."""
        from gh_worker.executor.orchestrator import WorkOrchestrator

        async def _work() -> str:
            orch = WorkOrchestrator(
                config_path=self.config_path,
                repos=[self._selected_repo] if self._selected_repo else None,
                agent=None,
            )
            await orch.run_once()
            return "Work cycle completed"

        self.run_worker(
            _work(),
            name="work",
            group="commands",
            exit_on_error=False,
            exclusive=True,
        )
        self._log_activity("Work --once started...")
        self._set_running(True)

    def _run_monitor(self) -> None:
        """Open Monitor screen for selected repo and issue."""
        if not self._selected_repo:
            self.notify("Select a repository first", severity="warning")
            return
        table = self.query_one("#issues-table", IssueTable)
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            if row_key is None:
                self.notify("Select an issue first", severity="warning")
                return
            # Row key is "owner/repo#issue_number"
            parts = str(row_key).rsplit("#", 1)
            if len(parts) != 2:
                self.notify("Select an issue first", severity="warning")
                return
            repo_name, issue_str = parts
            issue_number = int(issue_str)
        except (ValueError, TypeError):
            self.notify("Select an issue first", severity="warning")
            return

        from gh_worker.tui.screens.monitor import MonitorScreen

        self.app.push_screen(
            MonitorScreen(
                repo=repo_name,
                issue_number=issue_number,
                config_path=self.config_path,
            )
        )

    def _log_activity(self, msg: str) -> None:
        """Append to activity log."""
        log = self.query_one("#activity-log", ActivityLog)
        log.append_line(msg)

    def _set_running(self, running: bool) -> None:
        """Enable/disable quick action buttons."""
        actions = self.query_one("#quick-actions", QuickActions)
        actions.set_running(running)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker completion."""
        if event.worker.state not in (
            WorkerState.SUCCESS,
            WorkerState.ERROR,
            WorkerState.CANCELLED,
        ):
            return
        self._set_running(False)
        if event.worker.state == WorkerState.SUCCESS:
            result = event.worker.result
            if isinstance(result, tuple):
                success, msg = result
                self._log_activity(f"Done: {msg}" if success else f"Failed: {msg}")
            else:
                msg = result if isinstance(result, str) else str(result) if result else "Completed"
                self._log_activity(f"Done: {msg}")
        elif event.worker.state == WorkerState.ERROR:
            err = getattr(event.worker, "error", None)
            self._log_activity(f"Error: {err}")
        self.refresh_data()
