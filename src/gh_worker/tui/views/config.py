"""Config view - view and edit configuration."""

from pathlib import Path
from typing import Any

from textual.containers import Container
from textual.widgets import Button, DataTable, Input, Label, Static

from gh_worker.config.manager import ConfigManager


def _parse_config_value(key: str, value: str) -> Any:
    """Parse string value to appropriate type for config key."""
    val_lower = value.strip().lower()
    if val_lower in ("(none)", "none", ""):
        return None
    if "path" in key.lower():
        return Path(value).expanduser().resolve()
    if "parallelism" in key.lower():
        return int(value)
    if val_lower in ("true", "false", "1", "0", "yes", "no"):
        return val_lower in ("true", "1", "yes")
    return value.strip()


def _format_config_value(value: Any) -> str:
    """Format config value for display."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class ConfigView(Container):
    """Config view with key/value table and edit capability."""

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path
        self._config_manager: ConfigManager | None = None
        self._config_data: list[tuple[str, str]] = []
        self._selected_key: str | None = None

    def compose(self):
        """Compose config view layout."""
        yield Label("Configuration", classes="section-title")
        yield Static("", id="config-path")
        yield Button("Open in editor", id="config-open-editor")
        yield Label("Settings", classes="section-title")
        yield DataTable(id="config-table", cursor_type="row")
        yield Input(placeholder="Edit value (Enter to save)", id="config-edit-input")

    def on_mount(self) -> None:
        """Load config on mount."""
        self._config_manager = ConfigManager(self.config_path)
        self._refresh_config_path()
        self._refresh_table()

    def _refresh_config_path(self) -> None:
        """Update config path display."""
        if self._config_manager:
            path_static = self.query_one("#config-path", Static)
            path_static.update(f"Config file: {self._config_manager.config_path}")

    def _refresh_table(self) -> None:
        """Refresh config table from ConfigManager."""
        if not self._config_manager:
            return
        data = self._config_manager.list_all()
        self._config_data = [(k, _format_config_value(v)) for k, v in sorted(data.items())]

        table = self.query_one("#config-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Key", "Value")
        for key, val in self._config_data:
            table.add_row(key, val, key=key)

    def on_data_table_row_selected(self, event) -> None:
        """Handle row selection - show current value in input for editing."""
        row_key = event.row_key
        if row_key is None:
            return
        self._selected_key = str(row_key)
        for k, v in self._config_data:
            if k == self._selected_key:
                inp = self.query_one("#config-edit-input", Input)
                inp.value = v
                inp.placeholder = f"Edit {k} (Enter to save)"
                break

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submit - save config value."""
        inp = event.input
        if inp.id != "config-edit-input":
            return
        key = self._selected_key
        if not key:
            return
        value = inp.value.strip()
        try:
            typed = _parse_config_value(key, value)
            self._config_manager.set(key, typed)
            self.notify(f"Updated {key}")
            self._refresh_table()
        except (KeyError, ValueError) as e:
            self.notify(f"Error: {e}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Open in editor button."""
        if event.button.id == "config-open-editor" and self._config_manager:
            import os
            import subprocess

            editor = os.environ.get("EDITOR", "vim")
            path = self._config_manager.config_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.touch()
            try:
                subprocess.run([editor, str(path)], check=False)
                self._config_manager.load()
                self._refresh_table()
                self.notify("Config reloaded")
            except FileNotFoundError:
                self.notify(f"Editor not found: {editor}", severity="error")
