"""Session persistence for TUI state."""

import json
from pathlib import Path

# Sentinel: pass this as default to mean "don't update this key"
_UNCHANGED = object()


def _state_path() -> Path:
    """Get path to tui-state.json."""
    xdg_config = Path.home() / ".config"
    config_dir = xdg_config / "gh-worker"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "tui-state.json"


def load_state() -> dict:
    """Load session state from disk.

    Returns:
        Dict with keys: last_repo, title_filter, plan_filter, implementation_filter,
        assignee_filter, author_filter
    """
    path = _state_path()
    if not path.exists():
        return {
            "last_repo": None,
            "title_filter": None,
            "plan_filter": None,
            "implementation_filter": None,
            "assignee_filter": None,
            "author_filter": None,
            "last_tab": None,
        }

    try:
        data = json.loads(path.read_text())
        return {
            "last_repo": data.get("last_repo"),
            "title_filter": data.get("title_filter"),
            "plan_filter": data.get("plan_filter"),
            "implementation_filter": data.get("implementation_filter"),
            "assignee_filter": data.get("assignee_filter"),
            "author_filter": data.get("author_filter"),
            "last_tab": data.get("last_tab"),
        }
    except (json.JSONDecodeError, OSError):
        return {
            "last_repo": None,
            "title_filter": None,
            "plan_filter": None,
            "implementation_filter": None,
            "assignee_filter": None,
            "author_filter": None,
            "last_tab": None,
        }


def save_state(
    last_repo: str | None = _UNCHANGED,
    title_filter: str | None = _UNCHANGED,
    plan_filter: str | None = _UNCHANGED,
    implementation_filter: str | None = _UNCHANGED,
    assignee_filter: str | None = _UNCHANGED,
    author_filter: str | None = _UNCHANGED,
    last_tab: str | None = _UNCHANGED,
) -> None:
    """Save session state to disk.

    Args:
        last_repo: Last selected repository (owner/repo), or None for "all"
        title_filter: Last title filter (substring match)
        plan_filter: Last plan status filter, or None for "all"
        implementation_filter: Last implementation status filter, or None for "all"
        assignee_filter: Last assignee filter
        author_filter: Last author filter
        last_tab: Last active tab id
    """
    path = _state_path()
    data: dict = {}

    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if last_repo is not _UNCHANGED:
        data["last_repo"] = last_repo
    if title_filter is not _UNCHANGED:
        data["title_filter"] = title_filter
    if plan_filter is not _UNCHANGED:
        data["plan_filter"] = plan_filter
    if implementation_filter is not _UNCHANGED:
        data["implementation_filter"] = implementation_filter
    if assignee_filter is not _UNCHANGED:
        data["assignee_filter"] = assignee_filter
    if author_filter is not _UNCHANGED:
        data["author_filter"] = author_filter
    if last_tab is not _UNCHANGED:
        data["last_tab"] = last_tab

    path.write_text(json.dumps(data, indent=2))
