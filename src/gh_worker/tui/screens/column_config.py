"""Column configuration modal for issues table."""

from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label


def _safe_id(key: str) -> str:
    """Convert column key to a valid CSS id (no # or spaces)."""
    return "col-" + key.replace("#", "num").replace(" ", "-").lower()


class ColumnConfigModal(ModalScreen[list[str] | None]):
    """Modal to configure which columns are visible in the issues table."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, visible_columns: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._visible_columns = set(visible_columns)

    def compose(self):
        """Compose modal content."""
        from gh_worker.tui.widgets.issue_table import ALL_COLUMN_SPECS

        with Vertical():
            yield Label("Select columns to display", id="modal-title")
            with VerticalScroll(id="column-checkboxes"):
                for label, key in ALL_COLUMN_SPECS:
                    yield Checkbox(label, value=key in self._visible_columns, id=_safe_id(key))
            with Horizontal(id="modal-buttons"):
                yield Button("Select all", id="modal-select-all", variant="default")
                yield Button("Deselect all", id="modal-deselect-all", variant="default")
                yield Button("Cancel", id="modal-cancel", variant="default")
                yield Button("Apply", id="modal-apply", variant="primary")

    def on_mount(self) -> None:
        """Focus the apply button on mount."""
        self.query_one("#modal-apply", Button).focus()

    def action_cancel(self) -> None:
        """Cancel and dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        from gh_worker.tui.widgets.issue_table import ALL_COLUMN_SPECS

        if event.button.id == "modal-cancel":
            self.dismiss(None)
        elif event.button.id == "modal-apply":
            visible = []
            for _, key in ALL_COLUMN_SPECS:
                try:
                    cb = self.query_one(f"#{_safe_id(key)}", Checkbox)
                    if cb.value:
                        visible.append(key)
                except Exception:
                    pass
            if visible:
                self.dismiss(visible)
            else:
                self.notify("At least one column must be visible", severity="warning")
        elif event.button.id == "modal-select-all":
            for _, key in ALL_COLUMN_SPECS:
                try:
                    self.query_one(f"#{_safe_id(key)}", Checkbox).value = True
                except Exception:
                    pass
        elif event.button.id == "modal-deselect-all":
            for _, key in ALL_COLUMN_SPECS:
                try:
                    self.query_one(f"#{_safe_id(key)}", Checkbox).value = False
                except Exception:
                    pass
