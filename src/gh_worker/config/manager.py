"""Configuration manager for persisting and loading configuration."""

from pathlib import Path
from typing import Any

import yaml

from .schema import AppConfig


class ConfigManager:
    """Manages configuration persistence using YAML format."""

    def __init__(self, config_path: Path | None = None):
        """Initialize the configuration manager.

        Args:
            config_path: Path to configuration file. If None, uses default path.
        """
        self.config_path = config_path or self._default_config_path()
        self._config: AppConfig | None = None

    def _default_config_path(self) -> Path:
        """Get default configuration path using XDG Base Directory spec.

        Returns:
            Path to configuration file (~/.config/gh-worker/config.yaml)
        """
        xdg_config = Path.home() / ".config"
        config_dir = xdg_config / "gh-worker"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.yaml"

    def load(self) -> AppConfig:
        """Load configuration from disk.

        Returns:
            Loaded AppConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        if not self.config_path.exists():
            # Return default config if file doesn't exist
            self._config = AppConfig()
            return self._config

        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}

        self._config = AppConfig(**data)
        return self._config

    def save(self, config: AppConfig) -> None:
        """Save configuration to disk.

        Args:
            config: AppConfig instance to save
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, handling Path objects
        data = config.model_dump(mode="json")

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

        self._config = config

    def get(self, key: str) -> Any:
        """Get a configuration value by dotted key.

        Args:
            key: Dotted key path (e.g., 'plan.parallelism')

        Returns:
            Configuration value

        Raises:
            KeyError: If key doesn't exist
        """
        if self._config is None:
            self._config = self.load()

        parts = key.split(".")
        value: Any = self._config
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                raise KeyError(f"Configuration key not found: {key}")
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by dotted key.

        Args:
            key: Dotted key path (e.g., 'plan.parallelism')
            value: Value to set

        Raises:
            KeyError: If key path doesn't exist
        """
        if self._config is None:
            self._config = self.load()

        parts = key.split(".")
        if len(parts) == 1:
            # Top-level key
            setattr(self._config, parts[0], value)
        else:
            # Nested key
            obj: Any = self._config
            for part in parts[:-1]:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    raise KeyError(f"Configuration key not found: {key}")
            setattr(obj, parts[-1], value)

        self.save(self._config)
