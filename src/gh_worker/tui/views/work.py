"""Work view - run sync/plan/implement cycles with status."""

from pathlib import Path

from textual.containers import Container, Vertical
from textual.widgets import Button, Label, Static

from gh_worker.tui.data import get_repositories
from gh_worker.tui.widgets.activity_log import ActivityLog


class WorkView(Container):
    """Work view with cycle controls and status."""

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path
        self._stop_requested = False
        self._running = False

    def compose(self):
        """Compose work view layout."""
        yield Label("Work mode", classes="section-title")
        with Vertical():
            yield Button("Work --once", id="work-once", variant="primary")
            yield Button("Work continuous", id="work-continuous")
        yield Label("Status", classes="section-title")
        yield Static("Idle", id="work-status")
        yield Button("Stop", id="work-stop", variant="error")
        yield Label("Cycle log", classes="section-title")
        yield ActivityLog(id="work-cycle-log")

    def on_mount(self) -> None:
        """Hide Stop button initially."""
        self._update_ui()

    def _update_ui(self) -> None:
        """Update UI based on running state."""
        try:
            stop_btn = self.query_one("#work-stop", Button)
            stop_btn.display = self._running
            stop_btn.disabled = not self._running
            once_btn = self.query_one("#work-once", Button)
            once_btn.disabled = self._running
            cont_btn = self.query_one("#work-continuous", Button)
            cont_btn.disabled = self._running
        except Exception:
            pass

    def _log(self, msg: str) -> None:
        """Append to cycle log."""
        try:
            log = self.query_one("#work-cycle-log", ActivityLog)
            log.append_line(msg)
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        """Update status display."""
        try:
            status = self.query_one("#work-status", Static)
            status.update(msg)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        bid = event.button.id
        if bid == "work-once":
            self._run_work_once()
        elif bid == "work-continuous":
            self._run_work_continuous()
        elif bid == "work-stop":
            self._stop_requested = True
            self._log("Stop requested, will exit after current cycle")

    def _run_work_once(self) -> None:
        """Run work --once in worker."""
        from gh_worker.executor.orchestrator import WorkOrchestrator

        self._stop_requested = False
        self._running = True
        self._update_ui()
        self._set_status("Running...")
        self._log("Work --once started")

        repos = self._get_repos()

        async def _work() -> str:
            orch = WorkOrchestrator(
                config_path=self.config_path,
                repos=repos,
                agent=None,
            )
            await orch.run_once()
            return "Cycle completed"

        self.run_worker(
            _work(),
            name="work-once",
            group="work",
            exit_on_error=False,
            exclusive=True,
        )

    def _run_work_continuous(self) -> None:
        """Run work continuous in worker."""
        from gh_worker.config.manager import ConfigManager
        from gh_worker.executor.orchestrator import WorkOrchestrator

        self._stop_requested = False
        self._running = True
        self._update_ui()
        self._set_status("Running continuous...")
        self._log("Work continuous started")

        config = ConfigManager(self.config_path)
        app_config = config.load()
        frequency = app_config.sync.frequency
        repos = self._get_repos()

        async def _work() -> str:
            orch = WorkOrchestrator(
                config_path=self.config_path,
                repos=repos,
                agent=None,
            )
            await orch.run_continuous(
                frequency,
                stop_requested=lambda: self._stop_requested,
            )
            return "Stopped"

        self.run_worker(
            _work(),
            name="work-continuous",
            group="work",
            exit_on_error=False,
            exclusive=True,
        )

    def _get_repos(self) -> list[str] | None:
        """Get repos list from config (simplified - could use session state)."""
        repos = get_repositories(self.config_path)
        return [r.full_name for r in repos] if repos else None

    def on_worker_state_changed(self, event) -> None:
        """Handle worker completion."""
        from textual.worker import WorkerState

        if event.worker.state not in (
            WorkerState.SUCCESS,
            WorkerState.ERROR,
            WorkerState.CANCELLED,
        ):
            return
        self._running = False
        self._update_ui()
        self._set_status("Idle")
        if event.worker.state == WorkerState.SUCCESS:
            result = event.worker.result
            msg = result if isinstance(result, str) else str(result) if result else "Done"
            self._log(f"Completed: {msg}")
        elif event.worker.state == WorkerState.ERROR:
            err = getattr(event.worker, "error", None)
            self._log(f"Error: {err}")
