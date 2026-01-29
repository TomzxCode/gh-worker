"""Path utilities for XDG Base Directory specification."""

from pathlib import Path


def get_config_dir() -> Path:
    """Get configuration directory using XDG Base Directory spec.

    Returns:
        Path to configuration directory (~/.config/gh-worker)
    """
    xdg_config_home = Path.home() / ".config"
    config_dir = xdg_config_home / "gh-worker"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Get data directory using XDG Base Directory spec.

    Returns:
        Path to data directory (~/.local/share/gh-worker)
    """
    xdg_data_home = Path.home() / ".local" / "share"
    data_dir = xdg_data_home / "gh-worker"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_cache_dir() -> Path:
    """Get cache directory using XDG Base Directory spec.

    Returns:
        Path to cache directory (~/.cache/gh-worker)
    """
    xdg_cache_home = Path.home() / ".cache"
    cache_dir = xdg_cache_home / "gh-worker"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir
