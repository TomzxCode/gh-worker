"""Scrollable activity log widget."""

from textual.widgets import RichLog


class ActivityLog(RichLog):
    """Scrollable log for activity and monitor output."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.auto_scroll = True

    def append_line(self, text: str) -> None:
        """Append a line to the log."""
        self.write(text, expand=False)
