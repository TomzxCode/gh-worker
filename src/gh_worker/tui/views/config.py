"""Config view - view and edit configuration."""

from pathlib import Path
from typing import Any

from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Button, Input, Label, Select, Static

from gh_worker.config.manager import ConfigManager

# Config keys that use a dropdown with predefined options
AGENT_DEFAULT_KEY = "agent.default"
AGENT_OVERRIDE_KEYS = ("plan.agent", "implement.agent")
BOOLEAN_KEYS = (
    "implement.use_worktree",
    "implement.push_branch",
    "implement.create_pr",
    "implement.delete_worktree",
)


def _get_options_for_key(key: str) -> list[tuple[str, Any]] | None:
    """Return dropdown options for keys with predefined values, or None for freeform."""
    if key == AGENT_DEFAULT_KEY:
        from gh_worker.agents.registry import get_registry

        agents = sorted(get_registry().list_agents())
        return [(name, name) for name in agents]
    if key in AGENT_OVERRIDE_KEYS:
        from gh_worker.agents.registry import get_registry

        agents = sorted(get_registry().list_agents())
        return [("(none)", None)] + [(name, name) for name in agents]
    if key in BOOLEAN_KEYS:
        return [("false", False), ("true", True)]
    return None


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


def _key_to_id(key: str) -> str:
    """Convert config key to a valid widget id."""
    return f"config-{key.replace('.', '-')}"


class ConfigView(Container):
    """Config view with key/value form - each row has the appropriate control type."""

    def __init__(self, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_path = config_path
        self._config_manager: ConfigManager | None = None
        self._config_keys: list[str] = []

    def compose(self):
        """Compose config view layout."""
        yield Label("Configuration", classes="section-title")
        yield Static("", id="config-path")
        yield Button("Open in editor", id="config-open-editor")
        yield Label("Settings", classes="section-title")
        yield ScrollableContainer(id="config-entries")

    def on_mount(self) -> None:
        """Load config and build form on mount."""
        self._config_manager = ConfigManager(self.config_path)
        self._refresh_config_path()
        self._refresh_entries()

    def _refresh_config_path(self) -> None:
        """Update config path display."""
        if self._config_manager:
            path_static = self.query_one("#config-path", Static)
            path_static.update(f"Config file: {self._config_manager.config_path}")

    def _refresh_entries(self) -> None:
        """Build or refresh the config form entries."""
        if not self._config_manager:
            return
        data = self._config_manager.list_all()
        self._config_keys = sorted(data.keys())

        container = self.query_one("#config-entries", ScrollableContainer)
        container.remove_children()
        for key in self._config_keys:
            value = data[key]
            value_str = _format_config_value(value)
            options = _get_options_for_key(key)
            row_id = _key_to_id(key)

            if options is not None:
                if key in AGENT_OVERRIDE_KEYS and (value is None or value_str == "(none)"):
                    initial: Any = None
                elif key in BOOLEAN_KEYS:
                    initial = bool(value)
                else:
                    opt_values = [opt[1] for opt in options]
                    initial = value if value in opt_values else options[0][1]
                widget = Select(options, value=initial, id=row_id)
            else:
                widget = Input(value=value_str, id=row_id)

            row = Horizontal(classes="config-row")
            container.mount(row)
            row.mount(Label(key, classes="config-key"))
            row.mount(widget)

    def _id_to_key(self, widget_id: str) -> str | None:
        """Convert widget id back to config key."""
        if not widget_id.startswith("config-"):
            return None
        return widget_id[7:].replace("-", ".")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submit - save config value."""
        key = self._id_to_key(event.input.id)
        if not key or key not in self._config_keys:
            return
        value = event.input.value.strip()
        try:
            typed = _parse_config_value(key, value)
            self._config_manager.set(key, typed)
            self.notify(f"Updated {key}")
            self._refresh_entries()
        except (KeyError, ValueError) as e:
            self.notify(f"Error: {e}", severity="error")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change - save config value."""
        key = self._id_to_key(event.select.id)
        if not key or key not in self._config_keys:
            return
        value = event.value
        try:
            current = self._config_manager.get(key)
            if value == current:
                return
            self._config_manager.set(key, value)
            self.notify(f"Updated {key}")
            self._refresh_entries()
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
                self._refresh_entries()
                self.notify("Config reloaded")
            except FileNotFoundError:
                self.notify(f"Editor not found: {editor}", severity="error")
