"""Main TUI application."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from gh_worker.tui.data import get_repositories
from gh_worker.tui.state import load_state, save_state
from gh_worker.tui.views.config import ConfigView
from gh_worker.tui.views.dashboard import DashboardView
from gh_worker.tui.views.issues import IssuesView
from gh_worker.tui.views.repos import ReposView
from gh_worker.tui.views.work import WorkView
from gh_worker.utils.logging import setup_logging_for_tui

VALID_TAB_IDS = {"dashboard", "repos", "issues", "work", "config"}


class GhWorkerApp(App):
    """gh-worker TUI application."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        height: 1;
    }

    TabbedContent {
        height: 1fr;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        height: 1;
    }

    #left-panel {
        width: 25;
        min-width: 20;
        border: solid $primary;
        padding: 1;
    }

    #right-panel {
        width: 1fr;
        border: solid $primary;
        padding: 1;
    }

    #activity-log {
        height: 8;
        min-height: 4;
        border: solid $primary;
        padding: 1;
    }

    #issues-view {
        layout: vertical;
    }

    #issues-view #issues-table {
        height: auto;
        max-height: 40%;
    }

    #issues-view #issue-description {
        height: 1fr;
        min-height: 10;
    }

    #issues-view #issue-actions {
        height: 3;
    }

    #quick-actions {
        height: 3;
    }

    #filters-row {
        height: 3;
    }

    #filters-row Select {
        min-width: 10;
        max-width: 20;
    }

    #filters-row Input {
        min-width: 10;
        max-width: 18;
    }

    #dashboard-filters {
        height: 3;
    }

    #dashboard-filters Select {
        min-width: 10;
        max-width: 20;
    }

    #dashboard-filters Input {
        min-width: 10;
        max-width: 18;
    }

    #config-view #config-table-container {
        height: auto;
        max-height: 50%;
        position: relative;
    }

    #config-view #config-table {
        height: auto;
    }

    #config-view #config-inline-edit {
        display: none;
    }

    /* Select dropdown: show full text without wrapping */
    Select > SelectOverlay {
        min-width: 40;
        overflow-x: auto;
    }

    Select > SelectOverlay .option-list--option {
        text-wrap: nowrap;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path

    def compose(self) -> ComposeResult:
        """Compose the application."""
        yield Header(show_clock=False)
        state = load_state()
        last_tab = state.get("last_tab")
        if last_tab not in VALID_TAB_IDS:
            last_tab = "dashboard"
        with TabbedContent("Dashboard", "Repos", "Issues", "Work", "Config", initial=last_tab):
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardView(config_path=self.config_path, id="dashboard-view")
            with TabPane("Repos", id="repos"):
                yield ReposView(config_path=self.config_path, id="repos-view")
            with TabPane("Issues", id="issues"):
                yield IssuesView(config_path=self.config_path, id="issues-view")
            with TabPane("Work", id="work"):
                yield WorkView(config_path=self.config_path, id="work-view")
            with TabPane("Config", id="config"):
                yield ConfigView(config_path=self.config_path, id="config-view")
        yield Footer()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Save active tab when user switches tabs."""
        pane = event.pane
        if pane and pane.id and pane.id in VALID_TAB_IDS:
            save_state(last_tab=pane.id)

    def on_mount(self) -> None:
        """Check config on mount."""
        # Route logging through Textual so plan/implement output doesn't overwrite the TUI
        setup_logging_for_tui()

        repos = get_repositories(self.config_path)
        if not repos:
            self.notify(
                "No repositories. Run 'ghw repositories add owner/repo' first.", severity="warning"
            )
