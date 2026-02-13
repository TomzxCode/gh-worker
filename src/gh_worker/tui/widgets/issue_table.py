"""Issues DataTable widget."""

from textual.widgets import DataTable


class IssueTable(DataTable):
    """DataTable for displaying issues with status columns."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.add_columns(
            "#", "Repository", "Title", "Author", "Assignees", "Plan", "Implementation"
        )

    def clear_and_populate(
        self,
        rows: list[tuple[str, int, str, str | None, list[str], str, str]],
    ) -> None:
        """Clear table and populate with issue rows.

        Args:
            rows: List of (repo_full_name, issue_number, title, author, assignees,
                  plan_status, impl_status)
        """
        self.clear()
        for (
            repo_full_name,
            issue_number,
            title,
            author,
            assignees,
            plan_status,
            impl_status,
        ) in rows:
            author_str = author or "—"
            assignees_str = ", ".join(assignees) if assignees else "—"
            if len(assignees_str) > 20:
                assignees_str = assignees_str[:17] + "..."
            plan_display = "—" if plan_status == "none" else plan_status
            impl_display = "—" if impl_status == "none" else impl_status
            if len(title) > 50:
                title = title[:47] + "..."
            if len(repo_full_name) > 25:
                repo_display = repo_full_name[:22] + "..."
            else:
                repo_display = repo_full_name
            row_key = f"{repo_full_name}#{issue_number}"
            self.add_row(
                str(issue_number),
                repo_display,
                title,
                author_str,
                assignees_str,
                plan_display,
                impl_display,
                key=row_key,
            )
