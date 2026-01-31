"""Config command implementation."""

from pathlib import Path
from typing import Any

import structlog

from gh_worker.config.manager import ConfigManager

logger = structlog.get_logger()


def config_command(key: str, value: str | None = None, config_path: Path | None = None) -> None:
    """Execute config command.

    Args:
        key: Configuration key (e.g., 'issues-path', 'plan.parallelism')
        value: Value to set (if None, gets the current value)
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)

    # Convert hyphenated keys to underscored for compatibility
    key = key.replace("-", "_")

    if value is None:
        # Get value
        try:
            result = manager.get(key)
            print(result)
        except KeyError as e:
            logger.error("config_key_not_found", key=key, error=str(e))
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
            if isinstance(typed_value, str) and typed_value.lower() in ("true", "false", "1", "0", "yes", "no"):
                typed_value = typed_value.lower() in ("true", "1", "yes")

            manager.set(key, typed_value)
            print(f"Set {key} = {typed_value}")
            logger.info("config_updated", key=key, value=str(typed_value))
        except (KeyError, ValueError) as e:
            logger.error("failed_to_set_config", key=key, value=value, error=str(e))
            print(f"Error: {e}")
