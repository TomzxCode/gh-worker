"""Config command implementation."""

from pathlib import Path
from typing import Any

import structlog

from gh_worker.config.manager import ConfigManager

logger = structlog.get_logger()


def config_command(
    key: str | None = None,
    value: str | None = None,
    list_all: bool = False,
    config_path: Path | None = None,
) -> None:
    """Execute config command.

    Args:
        key: Configuration key (e.g., 'issues-path', 'plan.parallelism')
        value: Value to set (if None, gets the current value)
        list_all: If True, list all configuration values
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)

    if list_all:
        for k, v in sorted(manager.list_all().items()):
            print(f"{k}={v}")
        return

    if key is None:
        logger.error("Config key required")
        print("Error: Configuration key is required (or use --list to list all)")
        return

    # Convert hyphenated keys to underscored for compatibility
    key = key.replace("-", "_")

    if value is None:
        # Get value
        try:
            result = manager.get(key)
            print(result)
        except KeyError as e:
            logger.error("Config key not found", key=key, error=str(e))
            print(f"Error: {e}")
    else:
        # Set value
        try:
            # Try to convert value to appropriate type
            typed_value: Any = value

            # Handle Path types
            if "path" in key.lower():
                typed_value = Path(value).expanduser().resolve()

            # Handle integer types
            if "parallelism" in key.lower():
                typed_value = int(value)

            # Handle boolean types
            if isinstance(typed_value, str) and typed_value.lower() in (
                "true",
                "false",
                "1",
                "0",
                "yes",
                "no",
            ):
                typed_value = typed_value.lower() in ("true", "1", "yes")

            manager.set(key, typed_value)
            print(f"Set {key} = {typed_value}")
            logger.info("Config updated", key=key, value=str(typed_value))
        except (KeyError, ValueError) as e:
            logger.error("Failed to set config", key=key, value=value, error=str(e))
            print(f"Error: {e}")
