"""Issues view - filter and browse issues with actions."""

import os
import subprocess
import webbrowser
from pathlib import Path

from textual.containers import Container, Horizontal, HorizontalScroll
from textual.widgets import Button, Input, Label, RichLog, Select

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
from gh_worker.tui.screens.column_config import ColumnConfigModal
from gh_worker.tui.state import load_state, save_state
from gh_worker.tui.widgets.activity_log import ActivityLog
from gh_worker.tui.widgets.issue_table import IssueTable

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


class IssuesView(Container):
    """Issues view with filters and detail."""

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path
        self._selected_repo: str | None = None
        self._selected_issue: tuple[str, int] | None = None
        self._issue_status: dict[str, tuple[str, str]] = {}  # row_key -> (plan_status, impl_status)
        self._visible_columns: list[str] | None = None  # None = all

    def compose(self):
        """Compose issues view."""
        yield Label("Filters", classes="section-title")
        repos = get_repositories(self.config_path)
        repo_options = [("all", None)] + [(r.full_name, r.full_name) for r in repos]
        with HorizontalScroll(id="filters-row"):
            with Horizontal():
                yield Select(repo_options, prompt="Repo", allow_blank=True, id="filter-repo")
                yield Input(placeholder="Title", id="filter-title")
                yield Input(placeholder="Author", id="filter-author")
                yield Input(placeholder="Assignee", id="filter-assignee")
                yield Input(placeholder="Milestone", id="filter-milestone")
                yield Select(PLAN_OPTIONS, prompt="Plan", allow_blank=True, id="filter-plan")
                yield Select(IMPL_OPTIONS, prompt="Impl", allow_blank=True, id="filter-impl")
                yield Select(STATE_OPTIONS, prompt="State", allow_blank=True, id="filter-state")
                yield Button("Columns", id="filter-columns")
                yield Button("Sync", id="filter-sync")
                yield Button("Refresh", id="filter-refresh")
        yield Label("Issues", classes="section-title")
        yield IssueTable(id="issues-table")
        yield Label("Description", classes="section-title")
        yield RichLog(id="issue-description")
        with Horizontal(id="issue-actions"):
            yield Button("Plan", id="action-plan")
            yield Button("Implement", id="action-implement")
            yield Button("Monitor", id="action-monitor")
            yield Button("Review plan", id="action-review-plan")
            yield Button("Approve plan", id="action-approve-plan")
            yield Button("Unapprove plan", id="action-unapprove-plan")
            yield Button("Review implementation", id="action-review-impl")

    def on_mount(self) -> None:
        """Load issues on mount."""
        state = load_state()
        self._selected_repo = state.get("last_repo")
        repos = get_repositories(self.config_path)
        if not self._selected_repo and repos:
            self._selected_repo = repos[0].full_name

        # Refresh repo options (in case repos were added from Repos tab)
        try:
            repo_select = self.query_one("#filter-repo", Select)
            repo_options = [("all", None)] + [(r.full_name, r.full_name) for r in repos]
            repo_select.set_options(repo_options)
        except Exception:
            pass

        # Restore filter values from state (only if valid)
        try:
            repo_select = self.query_one("#filter-repo", Select)
            last_repo = state.get("last_repo")
            if last_repo is None or (repos and any(r.full_name == last_repo for r in repos)):
                repo_select.value = last_repo if last_repo else None
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
            milestone_input = self.query_one("#filter-milestone", Input)
            if state.get("milestone_filter"):
                milestone_input.value = state["milestone_filter"]
            cols = state.get("issue_columns")
            if isinstance(cols, list) and cols:
                self._visible_columns = cols
        except Exception:
            pass

        self._refresh_issues()

    def _get_filter_values(
        self,
    ) -> tuple[
        str | None,
        bool,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
    ]:
        """Get filter values. Returns (repo, all_repos, title, plan, impl, assignee,
        author, state, milestone).
        """
        try:
            repo_select = self.query_one("#filter-repo", Select)
            title_input = self.query_one("#filter-title", Input)
            author_input = self.query_one("#filter-author", Input)
            assignee_input = self.query_one("#filter-assignee", Input)
            milestone_input = self.query_one("#filter-milestone", Input)
            plan_select = self.query_one("#filter-plan", Select)
            impl_select = self.query_one("#filter-impl", Select)
            state_select = self.query_one("#filter-state", Select)
            repo_val = repo_select.value
            if repo_val is Select.BLANK or repo_val is None:
                repo_val = None
            title_val = title_input.value.strip() or None
            author_val = author_input.value.strip() or None
            assignee_val = assignee_input.value.strip() or None
            milestone_val = milestone_input.value.strip() or None
            plan_val = plan_select.value
            if plan_val is Select.BLANK or plan_val is None:
                plan_val = None
            impl_val = impl_select.value
            if impl_val is Select.BLANK or impl_val is None:
                impl_val = None
            state_val = state_select.value
            if state_val is Select.BLANK or state_val is None:
                state_val = None
            return (
                str(repo_val) if repo_val else None,
                repo_val is None,
                title_val,
                str(plan_val) if plan_val else None,
                str(impl_val) if impl_val else None,
                assignee_val,
                author_val,
                str(state_val) if state_val else None,
                milestone_val,
            )
        except Exception:
            return (
                self._selected_repo,
                not bool(self._selected_repo),
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )

    def _refresh_issues(self) -> None:
        """Refresh issues table."""
        (
            repo,
            all_repos,
            title_filter,
            plan_filter,
            impl_filter,
            assignee_filter,
            author_filter,
            state_filter,
            milestone_filter,
        ) = self._get_filter_values()
        issues = get_issues(
            repo=repo,
            all_repos=all_repos,
            title_filter=title_filter,
            plan_filter=plan_filter,
            implementation_filter=impl_filter,
            assignee_filter=assignee_filter,
            author_filter=author_filter,
            state_filter=state_filter,
            milestone_filter=milestone_filter,
            config_path=self.config_path,
        )
        self._issue_status.clear()
        table = self.query_one("#issues-table", IssueTable)
        rows = []
        for (
            repo,
            issue_number,
            title,
            author,
            assignees,
            plan_status,
            impl_status,
            state,
            milestone,
        ) in issues:
            row_key = f"{repo.full_name}#{issue_number}"
            self._issue_status[row_key] = (plan_status, impl_status)
            rows.append(
                (
                    repo.full_name,
                    issue_number,
                    title,
                    author,
                    assignees,
                    plan_status,
                    impl_status,
                    state,
                    milestone,
                )
            )
        table.clear_and_populate(rows, visible_columns=self._visible_columns)
        self._update_action_buttons()

    def _show_issue_description(self, row_key) -> None:
        """Show description for the given issue row key (owner/repo#number)."""
        if row_key is None:
            return
        # RowKey has .value; fall back to str() for plain strings
        key_str = getattr(row_key, "value", None) or str(row_key)
        try:
            parts = str(key_str).rsplit("#", 1)
            if len(parts) != 2:
                return
            repo_name, issue_str = parts
            issue_number = int(issue_str)
        except (ValueError, TypeError):
            return
        self._selected_issue = (repo_name, issue_number)
        from gh_worker.models.repository import Repository
        from gh_worker.tui.data import get_issue_description

        repo = Repository.from_string(repo_name)
        desc = get_issue_description(repo, issue_number, self.config_path)
        log = self.query_one("#issue-description", RichLog)
        log.clear()
        log.write(desc or "(no description)", expand=False)
        self._update_action_buttons()

    def on_data_table_cell_highlighted(self, event) -> None:
        """Handle cell highlight (arrow keys / hover) - show description."""
        table = event.control
        if table.id != "issues-table":
            return
        row_key, _ = table.coordinate_to_cell_key(event.coordinate)
        self._show_issue_description(row_key)

    def on_data_table_cell_selected(self, event) -> None:
        """Handle cell selection - open browser if # column clicked, else show description."""
        table = event.control
        if table.id != "issues-table":
            return
        row_key, column_key = table.coordinate_to_cell_key(event.coordinate)
        # Column "#" is the issue number - clicking it opens the issue URL in browser
        if column_key == "#" and row_key:
            self._open_issue_in_browser(row_key)
        else:
            self._show_issue_description(row_key)

    def _open_issue_in_browser(self, row_key) -> None:
        """Open the GitHub issue URL in the default browser."""
        key_str = getattr(row_key, "value", None) or str(row_key)
        try:
            parts = str(key_str).rsplit("#", 1)
            if len(parts) != 2:
                return
            repo_name, issue_str = parts
            issue_number = int(issue_str)
        except (ValueError, TypeError):
            return
        url = f"https://github.com/{repo_name}/issues/{issue_number}"
        try:
            webbrowser.open(url)
            self.notify(f"Opened {url}")
        except webbrowser.Error:
            self.notify("Could not open browser", severity="error")

    def _update_action_buttons(self) -> None:
        """Enable/disable action buttons based on selected issue status."""
        plan_status = ""
        impl_status = ""
        if self._selected_issue:
            repo_name, issue_number = self._selected_issue
            row_key = f"{repo_name}#{issue_number}"
            plan_status, impl_status = self._issue_status.get(row_key, ("", ""))

        try:
            actions = self.query_one("#issue-actions", Horizontal)
            for bid in [
                "action-plan",
                "action-implement",
                "action-monitor",
                "action-review-plan",
                "action-approve-plan",
                "action-unapprove-plan",
                "action-review-impl",
            ]:
                btn = actions.query_one(f"#{bid}", Button)
                if bid in ("action-review-plan", "action-approve-plan"):
                    btn.disabled = plan_status != PLAN_WAITING_FOR_REVIEW
                elif bid == "action-unapprove-plan":
                    btn.disabled = plan_status != PLAN_APPROVED
                elif bid == "action-review-impl":
                    btn.disabled = impl_status != IMPL_WAITING_FOR_REVIEW
                else:
                    btn.disabled = not self._selected_issue
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle filter selection change."""
        val = event.select.value
        filter_val = str(val) if val is not Select.BLANK and val else None
        if event.select.id == "filter-repo":
            save_state(last_repo=filter_val)
            self._selected_repo = filter_val
        elif event.select.id == "filter-plan":
            save_state(plan_filter=filter_val)
        elif event.select.id == "filter-impl":
            save_state(implementation_filter=filter_val)
        elif event.select.id == "filter-state":
            save_state(state_filter=filter_val)
        self._refresh_issues()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle filter input (title, author, assignee, milestone)."""
        save_state(
            title_filter=self.query_one("#filter-title", Input).value.strip() or None,
            author_filter=self.query_one("#filter-author", Input).value.strip() or None,
            assignee_filter=self.query_one("#filter-assignee", Input).value.strip() or None,
            milestone_filter=self.query_one("#filter-milestone", Input).value.strip() or None,
        )
        self._refresh_issues()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "filter-columns":
            self._open_column_config()
            return
        if event.button.id == "filter-sync":
            self._run_sync()
            return
        if event.button.id == "filter-refresh":
            state_select = self.query_one("#filter-state", Select)
            state_val = state_select.value
            state_filter = str(state_val) if state_val not in (Select.BLANK, None) else None
            save_state(
                title_filter=self.query_one("#filter-title", Input).value.strip() or None,
                author_filter=self.query_one("#filter-author", Input).value.strip() or None,
                assignee_filter=self.query_one("#filter-assignee", Input).value.strip() or None,
                milestone_filter=self.query_one("#filter-milestone", Input).value.strip() or None,
                state_filter=state_filter,
            )
            self._refresh_issues()
            self.notify("Refreshed")
            return
        if not self._selected_issue:
            return
        repo_name, issue_number = self._selected_issue
        bid = event.button.id
        if bid == "action-plan":
            self._run_plan(repo_name, issue_number)
        elif bid == "action-implement":
            self._run_implement(repo_name, issue_number)
        elif bid == "action-monitor":
            self._open_monitor(repo_name, issue_number)
        elif bid == "action-review-plan":
            self._run_review_plan(repo_name, issue_number)
        elif bid == "action-approve-plan":
            self._run_approve_plan(repo_name, issue_number)
        elif bid == "action-unapprove-plan":
            self._run_unapprove_plan(repo_name, issue_number)
        elif bid == "action-review-impl":
            self._run_review_implementation(repo_name, issue_number)

    def _open_column_config(self) -> None:
        """Open column configuration modal."""
        table = self.query_one("#issues-table", IssueTable)
        visible = table.get_visible_columns()

        async def _config() -> None:
            result = await self.app.push_screen_wait(ColumnConfigModal(visible_columns=visible))
            if result is not None:
                self._visible_columns = result
                save_state(issue_columns=result)
                self._refresh_issues()
                self.notify("Columns updated")

        self.run_worker(_config(), name="column-config", exit_on_error=False, exclusive=False)

    def _run_sync(self) -> None:
        """Run sync for filtered repositories."""
        from gh_worker.tui.workers import run_sync

        repo, all_repos, *_ = self._get_filter_values()
        if not all_repos and not repo:
            self.notify("Select a repository or 'all' to sync", severity="warning")
            return

        def _sync() -> tuple[bool, str]:
            return run_sync(
                repo=repo,
                all_repos=all_repos,
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
        self.notify("Sync started...")

    def _run_plan(self, repo: str, issue_number: int) -> None:
        """Run plan for selected issue (after agent/model confirmation)."""
        from gh_worker.tui.screens.agent_confirm import AgentConfirmModal
        from gh_worker.tui.workers import run_plan

        async def _plan() -> tuple[bool, str]:
            result = await self.app.push_screen_wait(
                AgentConfirmModal(action="plan", config_path=self.config_path)
            )
            if result is None:
                return True, "Cancelled"
            agent, model = result
            self.notify("Plan started...")
            return await run_plan(
                repo=repo,
                all_repos=False,
                issue_numbers=[issue_number],
                config_path=self.config_path,
                agent=agent,
                model=model,
            )

        self.run_worker(
            _plan(),
            name="plan",
            group="commands",
            exit_on_error=False,
            exclusive=True,
        )

    def _run_implement(self, repo: str, issue_number: int) -> None:
        """Run implement for selected issue (after agent/model confirmation)."""
        from gh_worker.tui.screens.agent_confirm import AgentConfirmModal
        from gh_worker.tui.workers import run_implement

        async def _implement() -> tuple[bool, str]:
            result = await self.app.push_screen_wait(
                AgentConfirmModal(action="implement", config_path=self.config_path)
            )
            if result is None:
                return True, "Cancelled"
            agent, model = result
            self.notify("Implement started...")
            return await run_implement(
                repo=repo,
                all_repos=False,
                issue_numbers=[issue_number],
                config_path=self.config_path,
                agent=agent,
                model=model,
            )

        self.run_worker(
            _implement(),
            name="implement",
            group="commands",
            exit_on_error=False,
            exclusive=True,
        )

    def _open_monitor(self, repo: str, issue_number: int) -> None:
        """Open Monitor screen for selected issue."""
        from gh_worker.tui.screens.monitor import MonitorScreen

        self.app.push_screen(
            MonitorScreen(
                repo=repo,
                issue_number=issue_number,
                config_path=self.config_path,
            )
        )

    def _run_review_plan(self, repo: str, issue_number: int) -> None:
        """Run review plan and open worktree in $EDITOR."""
        from gh_worker.tui.workers import run_review_plan

        def _review() -> tuple[bool, str, Path | None]:
            return run_review_plan(
                repo=repo,
                issue_number=issue_number,
                approve=False,
                config_path=self.config_path,
            )

        self.run_worker(
            _review,
            name="review-plan",
            group="commands",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self.notify("Review plan started...")

    def _run_approve_plan(self, repo: str, issue_number: int) -> None:
        """Approve plan for selected issue (no worktree/editor)."""
        from gh_worker.tui.workers import run_review_plan

        def _approve() -> tuple[bool, str, Path | None]:
            return run_review_plan(
                repo=repo,
                issue_number=issue_number,
                approve=True,
                config_path=self.config_path,
            )

        self.run_worker(
            _approve,
            name="approve-plan",
            group="commands",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self.notify("Approving plan...")

    def _run_unapprove_plan(self, repo: str, issue_number: int) -> None:
        """Unapprove plan for selected issue."""
        from gh_worker.tui.workers import run_unapprove_plan

        def _unapprove() -> tuple[bool, str]:
            return run_unapprove_plan(
                repo=repo,
                issue_number=issue_number,
                config_path=self.config_path,
            )

        self.run_worker(
            _unapprove,
            name="unapprove-plan",
            group="commands",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self.notify("Unapproving plan...")

    def _run_review_implementation(self, repo: str, issue_number: int) -> None:
        """Run review implementation (push branch, create PR)."""
        from gh_worker.tui.workers import run_review_implementation

        def _review() -> tuple[bool, str]:
            return run_review_implementation(
                repo=repo,
                issue_number=issue_number,
                push_branch=True,
                create_pr=True,
                config_path=self.config_path,
            )

        self.run_worker(
            _review,
            name="review-impl",
            group="commands",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self.notify("Review implementation started...")

    def _log_activity(self, msg: str) -> None:
        """Append to dashboard activity log."""
        try:
            log = self.app.query_one("#activity-log", ActivityLog)
            log.append_line(msg)
        except Exception:
            pass

    def on_worker_state_changed(self, event) -> None:
        """Handle worker completion - refresh and optionally open editor."""
        from textual.worker import WorkerState

        if event.worker.state not in (
            WorkerState.SUCCESS,
            WorkerState.ERROR,
            WorkerState.CANCELLED,
        ):
            return
        if event.worker.name == "sync":
            if event.worker.state == WorkerState.SUCCESS:
                result = event.worker.result
                if isinstance(result, tuple):
                    success, msg = result
                    activity_msg = "Sync completed" if success else f"Failed: {msg}"
                    self._log_activity(activity_msg)
                    self.notify(activity_msg, severity="error" if not success else "information")
            elif event.worker.state == WorkerState.ERROR:
                err = getattr(event.worker, "error", None)
                err_msg = f"Sync failed: {err}" if err else "Sync failed"
                self._log_activity(err_msg)
                self.notify(err_msg, severity="error")
            elif event.worker.state == WorkerState.CANCELLED:
                self._log_activity("Sync cancelled")
                self.notify("Sync cancelled")
        if event.worker.name == "review-plan" and event.worker.state == WorkerState.SUCCESS:
            result = event.worker.result
            if isinstance(result, tuple) and len(result) >= 3:
                _success, _msg, worktree_path = result
                if worktree_path and worktree_path.exists():
                    editor = os.environ.get("EDITOR", "vim")
                    try:
                        subprocess.Popen([editor, str(worktree_path)])
                        self.notify(f"Opened worktree in {editor}")
                    except FileNotFoundError:
                        self.notify(f"Editor not found: {editor}", severity="error")
        if event.worker.name == "approve-plan" and event.worker.state == WorkerState.SUCCESS:
            result = event.worker.result
            if isinstance(result, tuple) and len(result) >= 2:
                success, msg = result[0], result[1]
                if success:
                    self.notify("Plan approved")
                else:
                    self.notify(msg or "Approve failed", severity="error")
        if event.worker.name == "unapprove-plan" and event.worker.state == WorkerState.SUCCESS:
            result = event.worker.result
            if isinstance(result, tuple) and len(result) >= 2:
                success, msg = result[0], result[1]
                if success:
                    self.notify("Plan unapproved")
                else:
                    self.notify(msg or "Unapprove failed", severity="error")
        self._refresh_issues()
