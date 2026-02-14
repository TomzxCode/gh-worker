"""Issues DataTable widget."""

from rich.text import Text
from textual import events
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

# Column keys for sorting (must match add_columns)
COL_ISSUE_NUM = "#"
COL_REPOSITORY = "Repository"
COL_TITLE = "Title"
COL_AUTHOR = "Author"
COL_ASSIGNEES = "Assignees"
COL_MILESTONE = "Milestone"
COL_STATE = "State"
COL_PLAN = "Plan"
COL_IMPLEMENTATION = "Implementation"

# (label, key) in display order - used for column config
ALL_COLUMN_SPECS: list[tuple[str, str]] = [
    ("#", COL_ISSUE_NUM),
    ("Repository", COL_REPOSITORY),
    ("Title", COL_TITLE),
    ("Author", COL_AUTHOR),
    ("Assignees", COL_ASSIGNEES),
    ("Milestone", COL_MILESTONE),
    ("State", COL_STATE),
    ("Plan", COL_PLAN),
    ("Implementation", COL_IMPLEMENTATION),
]


def _numeric_sort_key(val: str) -> int:
    """Sort key for issue numbers - parses as int for correct ordering."""
    s = str(val).strip()
    return int(s) if s.isdigit() else 0


class _ReverseStr:
    """Wrapper that inverts string comparison for descending sort."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = str(value)

    def __lt__(self, other: "_ReverseStr") -> bool:
        return self.value > other.value


def _default_visible_columns() -> list[str]:
    """Default list of visible column keys."""
    return [key for _, key in ALL_COLUMN_SPECS]


class IssueTable(DataTable):
    """DataTable for displaying issues with status columns."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "cell"
        self._visible_columns: list[str] = _default_visible_columns()
        self._sort_columns: list[tuple[str, bool]] = []  # (column_key, reverse)
        self._last_header_click_shift = False
        self._apply_columns(self._visible_columns)

    async def _on_click(self, event: events.Click) -> None:
        """Capture shift state for header clicks before delegating."""
        meta = event.style.meta or {}
        if "row" in meta and "column" in meta:
            row_index = meta["row"]
            if self.show_header and row_index == -1:
                self._last_header_click_shift = event.shift
        await super()._on_click(event)

    def _apply_columns(self, visible_columns: list[str]) -> None:
        """Set visible columns. Removes all columns and re-adds only visible ones."""
        valid = {key for _, key in ALL_COLUMN_SPECS}
        visible = [k for k in visible_columns if k in valid]
        if not visible:
            visible = _default_visible_columns()
        self._visible_columns = visible
        # Remove existing columns (snapshot keys before mutating)
        for col in list(self.ordered_columns):
            self.remove_column(col.key)
        # Add visible columns in spec order
        for label, key in ALL_COLUMN_SPECS:
            if key in self._visible_columns:
                self.add_column(label, key=key)

    def get_visible_columns(self) -> list[str]:
        """Return the list of visible column keys."""
        return list(self._visible_columns)

    def set_visible_columns(self, visible_columns: list[str] | None) -> None:
        """Update visible columns. None means all columns."""
        if visible_columns is None:
            visible_columns = _default_visible_columns()
        if visible_columns != self._visible_columns:
            self._apply_columns(visible_columns)

    def clear_and_populate(
        self,
        rows: list[tuple[str, int, str, str | None, list[str], str, str, str | None, str | None]],
        visible_columns: list[str] | None = None,
    ) -> None:
        """Clear table and populate with issue rows.

        Args:
            rows: List of (repo_full_name, issue_number, title, author, assignees,
                  plan_status, impl_status, state, milestone)
            visible_columns: Column keys to show, or None to keep current
        """
        if visible_columns is not None and visible_columns != self._visible_columns:
            self._apply_columns(visible_columns)
        self.clear()
        for (
            repo_full_name,
            issue_number,
            title,
            author,
            assignees,
            plan_status,
            impl_status,
            state,
            milestone,
        ) in rows:
            author_str = author or "—"
            assignees_str = ", ".join(assignees) if assignees else "—"
            if len(assignees_str) > 20:
                assignees_str = assignees_str[:17] + "..."
            milestone_display = milestone or "—"
            if len(milestone_display) > 15:
                milestone_display = milestone_display[:12] + "..."
            plan_display = "—" if plan_status == "none" else plan_status
            impl_display = "—" if impl_status == "none" else impl_status
            state_display = state or "—"
            if len(title) > 50:
                title = title[:47] + "..."
            if len(repo_full_name) > 25:
                repo_display = repo_full_name[:22] + "..."
            else:
                repo_display = repo_full_name
            row_key = f"{repo_full_name}#{issue_number}"
            all_values = {
                COL_ISSUE_NUM: str(issue_number),
                COL_REPOSITORY: repo_display,
                COL_TITLE: title,
                COL_AUTHOR: author_str,
                COL_ASSIGNEES: assignees_str,
                COL_MILESTONE: milestone_display,
                COL_STATE: state_display,
                COL_PLAN: plan_display,
                COL_IMPLEMENTATION: impl_display,
            }
            row_values = [all_values[k] for k in self._visible_columns]
            self.add_row(*row_values, key=row_key)
        self._apply_sort()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header click. Shift+click adds to sort, click toggles or replaces."""
        if event.control != self:
            return
        col_key = event.column_key
        key_str = col_key.value if isinstance(col_key, ColumnKey) else str(col_key)
        shift = self._last_header_click_shift

        # If column is already in sort: toggle its direction (works with or without shift)
        for i, (k, rev) in enumerate(self._sort_columns):
            if k == key_str:
                if rev:
                    self._sort_columns.pop(i)
                else:
                    self._sort_columns[i] = (k, True)
                self._apply_sort()
                return

        if shift:
            self._sort_columns.append((key_str, False))
        else:
            self._sort_columns = [(key_str, False)]
        self._apply_sort()

    def _update_header_labels(self) -> None:
        """Update column headers to show sort direction (↑ asc, ↓ desc) and order (1, 2, …)."""
        sort_map = {k: (i + 1, rev) for i, (k, rev) in enumerate(self._sort_columns)}
        show_order = len(self._sort_columns) > 1
        for column in self.ordered_columns:
            key_str = column.key.value if hasattr(column.key, "value") else str(column.key)
            base = key_str
            if key_str in sort_map:
                order, rev = sort_map[key_str]
                arrow = " ↓" if rev else " ↑"
                order_str = f" {order}" if show_order else ""
                column.label = Text(base + order_str + arrow)
            else:
                column.label = Text(base)

    def _apply_sort(self) -> None:
        """Apply current sort state to the table."""
        self._update_header_labels()
        if not self._sort_columns or self.row_count == 0:
            self.refresh()
            return
        # Single sort with composite key - DataTable.sort() uses _data.items()
        # so multiple sort() calls would lose previous order.
        # Use ColumnKey from table to match row_data dict keys
        col_key_map = {}
        for c in self.ordered_columns:
            k = c.key.value if hasattr(c.key, "value") and c.key.value else str(c.key)
            if k:
                col_key_map[k] = c.key
        sort_col_keys = []
        for k, _ in self._sort_columns:
            if k in col_key_map:
                sort_col_keys.append(col_key_map[k])

        if not sort_col_keys:
            self.refresh()
            return

        def composite_key(vals: str | tuple) -> tuple:
            if len(sort_col_keys) == 1:
                vals = (vals,)
            result = []
            for i, (col, rev) in enumerate(self._sort_columns):
                if col not in col_key_map or i >= len(vals):
                    continue
                val = vals[i]
                s = str(val).strip() if val is not None else ""
                if col == COL_ISSUE_NUM:
                    v = _numeric_sort_key(s)
                    result.append(-v if rev else v)
                else:
                    result.append(_ReverseStr(s) if rev else s)
            return tuple(result)

        self.sort(*sort_col_keys, key=composite_key, reverse=False)
