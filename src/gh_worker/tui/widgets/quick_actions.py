"""Quick action buttons widget."""

from textual.containers import Horizontal, HorizontalScroll
from textual.widgets import Button


class QuickActions(HorizontalScroll):
    """Horizontal container of action buttons."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._sync_btn: Button | None = None
        self._plan_btn: Button | None = None
        self._implement_btn: Button | None = None
        self._work_btn: Button | None = None

    def compose(self):
        """Create action buttons."""
        with Horizontal():
            self._sync_btn = Button("Sync", id="sync", variant="default")
            self._plan_btn = Button("Plan", id="plan", variant="default")
            self._implement_btn = Button("Implement", id="implement", variant="default")
            self._work_btn = Button("Work --once", id="work-once", variant="primary")
            self._monitor_btn = Button("Monitor", id="monitor", variant="default")
            yield self._sync_btn
            yield self._plan_btn
            yield self._implement_btn
            yield self._work_btn
            yield self._monitor_btn

    def set_running(self, running: bool) -> None:
        """Enable or disable buttons based on running state."""
        disabled = running
        if self._sync_btn:
            self._sync_btn.disabled = disabled
        if self._plan_btn:
            self._plan_btn.disabled = disabled
        if self._implement_btn:
            self._implement_btn.disabled = disabled
        if self._work_btn:
            self._work_btn.disabled = disabled
        if self._monitor_btn:
            self._monitor_btn.disabled = disabled
