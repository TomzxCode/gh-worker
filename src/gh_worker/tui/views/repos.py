"""Repositories view - add/remove repos."""

from pathlib import Path

from textual.containers import Container, Horizontal
from textual.widgets import Button, DataTable, Input, Label

from gh_worker.config.manager import ConfigManager
from gh_worker.tui.data import get_repositories, is_repo_cloned


class ReposView(Container):
    """Repositories view with add/remove."""

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path
        self._selected_repo: str | None = None
        self._repos_cloned: dict[str, bool] = {}

    def compose(self):
        """Compose repos view."""
        yield Label("Add repository", classes="section-title")
        yield Input(placeholder="owner/repo", id="repo-input")
        yield Button("Add", id="repo-add")
        yield Label("Tracked repositories", classes="section-title")
        yield DataTable(id="repos-table", cursor_type="row")
        with Horizontal(id="repos-actions"):
            yield Button("Clone", id="repo-clone")
            yield Button("Remove", id="repo-remove")

    def on_mount(self) -> None:
        """Load repos on mount."""
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh repos table."""
        config = ConfigManager(self.config_path)
        app_config = config.load()
        repos = get_repositories(self.config_path)
        self._repos_cloned.clear()
        table = self.query_one("#repos-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Repository", "Clone path", "Cloned")
        for repo in repos:
            cloned = is_repo_cloned(repo, app_config.repository_path)
            self._repos_cloned[repo.full_name] = cloned
            path = ""
            if app_config.repository_path:
                path = str(app_config.repository_path / repo.owner / repo.name)
            table.add_row(
                repo.full_name,
                path or "(not configured)",
                "yes" if cloned else "no",
                key=repo.full_name,
            )
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Enable/disable Clone and Remove based on selection."""
        try:
            actions = self.query_one("#repos-actions", Horizontal)
            clone_btn = actions.query_one("#repo-clone", Button)
            remove_btn = actions.query_one("#repo-remove", Button)
            if self._selected_repo:
                clone_btn.disabled = self._repos_cloned.get(self._selected_repo, True)
                remove_btn.disabled = False
            else:
                clone_btn.disabled = True
                remove_btn.disabled = True
        except Exception:
            pass

    def on_data_table_row_selected(self, event) -> None:
        """Handle repo row selection."""
        if event.control.id != "repos-table":
            return
        row_key = event.row_key
        if row_key is not None:
            self._selected_repo = str(row_key)
            self._update_action_buttons()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        bid = event.button.id
        if bid == "repo-add":
            inp = self.query_one("#repo-input", Input)
            repo_str = inp.value.strip()
            if not repo_str:
                self.notify("Enter owner/repo", severity="warning")
                return
            try:
                from gh_worker.commands.add import add_command

                add_command(repos=[repo_str], config_path=self.config_path, clone=False)
                self.notify(f"Added {repo_str}")
                inp.value = ""
                self._refresh_table()
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")
        elif bid == "repo-clone" and self._selected_repo:
            self._run_clone(self._selected_repo)
        elif bid == "repo-remove" and self._selected_repo:
            self._run_remove(self._selected_repo)

    def _run_clone(self, repo_str: str) -> None:
        """Clone selected repository."""
        from gh_worker.tui.workers import run_clone

        def _clone() -> tuple[bool, str]:
            return run_clone(repo=repo_str, config_path=self.config_path)

        self.run_worker(
            _clone,
            name="clone",
            group="commands",
            exit_on_error=False,
            exclusive=True,
            thread=True,
        )
        self.notify(f"Cloning {repo_str}...")

    def _run_remove(self, repo_str: str) -> None:
        """Remove selected repository from tracking."""
        from gh_worker.commands.remove import remove_command

        try:
            remove_command(repos=[repo_str], config_path=self.config_path, keep_clone=True)
            self.notify(f"Removed {repo_str}")
            self._selected_repo = None
            self._refresh_table()
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def on_worker_state_changed(self, event) -> None:
        """Handle clone worker completion."""
        from textual.worker import WorkerState

        if event.worker.name == "clone" and event.worker.state in (
            WorkerState.SUCCESS,
            WorkerState.ERROR,
        ):
            self._refresh_table()
