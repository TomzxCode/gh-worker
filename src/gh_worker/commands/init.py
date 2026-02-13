"""Init command implementation for setting up configuration."""

from pathlib import Path
from typing import Any

import structlog

from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.github.client import GHClient

logger = structlog.get_logger()


def _prompt_with_default(prompt: str, default: Any | None = None, required: bool = True) -> str:
    """Prompt user for input with optional default value.

    Args:
        prompt: Prompt text
        default: Default value to show
        required: Whether input is required

    Returns:
        User input or default value
    """
    if default is not None:
        prompt_text = f"{prompt} [{default}]: "
    elif not required:
        prompt_text = f"{prompt} (optional): "
    else:
        prompt_text = f"{prompt}: "

    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        if default is not None:
            return str(default)
        if not required:
            return ""
        logger.info("This field is required. Please enter a value.")


def _prompt_path(prompt: str, default: Path | None = None, required: bool = True) -> Path | None:
    """Prompt user for a path with optional default value.

    Args:
        prompt: Prompt text
        default: Default path to show
        required: Whether path is required

    Returns:
        Path object or None if not required and not provided
    """
    default_str = str(default) if default else None
    value = _prompt_with_default(prompt, default_str, required)
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _prompt_int(prompt: str, default: int | None = None, min_value: int = 1) -> int:
    """Prompt user for an integer with optional default value.

    Args:
        prompt: Prompt text
        default: Default integer value
        min_value: Minimum allowed value

    Returns:
        Integer value
    """
    while True:
        default_str = str(default) if default is not None else None
        value = _prompt_with_default(prompt, default_str, required=True)
        try:
            int_value = int(value)
            if int_value < min_value:
                logger.info(f"Value must be at least {min_value}")
                continue
            return int_value
        except ValueError:
            logger.info("Please enter a valid integer")


def _prompt_choice(prompt: str, choices: list[str], default: str | None = None) -> str:
    """Prompt user to choose from a list of options.

    Args:
        prompt: Prompt text
        choices: List of available choices
        default: Default choice

    Returns:
        Selected choice
    """
    choices_str = ", ".join(choices)
    if default:
        prompt_text = f"{prompt} ({choices_str}) [{default}]: "
    else:
        prompt_text = f"{prompt} ({choices_str}): "

    while True:
        value = input(prompt_text).strip()
        if not value and default:
            return default
        if value in choices:
            return value
        logger.info(f"Please choose one of: {', '.join(choices)}")


def init_command(config_path: Path | None = None) -> None:
    """Execute init command to set up configuration interactively.

    Args:
        config_path: Path to config file
    """
    logger.info("Welcome to gh-worker configuration setup!")
    logger.info("This will guide you through setting up your configuration.")

    manager = ConfigManager(config_path)
    config = manager.load()

    # Check if config already exists
    if manager.config_path.exists():
        logger.info(f"Configuration file already exists at: {manager.config_path}")
        overwrite = input("Do you want to update it? (y/N): ").strip().lower()
        if overwrite != "y":
            logger.info("Configuration setup cancelled.")
            return

    # Check GitHub authentication
    logger.info("Checking GitHub CLI authentication...")
    gh_client = GHClient()
    if not gh_client.check_auth():
        logger.warning(
            "GitHub CLI is not authenticated. Run 'gh auth login' "
            "to authenticate before using gh-worker."
        )
    else:
        logger.info("GitHub CLI is authenticated.")

    # Prompt for issues_path
    logger.info("Configuration Options:")
    issues_path = _prompt_path(
        "Issues storage path",
        default=config.issues_path,
        required=True,
    )
    if issues_path:
        issues_path.mkdir(parents=True, exist_ok=True)
        config.issues_path = issues_path

    # Prompt for repository_path
    repository_path = _prompt_path(
        "Repository clone path",
        default=config.repository_path,
        required=False,
    )
    if repository_path:
        repository_path.mkdir(parents=True, exist_ok=True)
        config.repository_path = repository_path

    # Prompt for agent configuration
    logger.info("Agent Configuration:")
    registry = get_registry()
    available_agents = registry.list_agents()
    default_agent = (
        config.agent.default if config.agent.default in available_agents else available_agents[0]
    )
    agent_name = _prompt_choice("Default agent", available_agents, default=default_agent)
    config.agent.default = agent_name

    # Prompt for claude-code path if using claude-code
    if agent_name == "claude-code":
        claude_code_path = _prompt_with_default(
            "Path to claude-code binary",
            default=config.agent.claude_code_path,
            required=False,
        )
        config.agent.claude_code_path = claude_code_path if claude_code_path else None

    # Prompt for parallelism settings
    logger.info("Performance Settings:")
    plan_parallelism = _prompt_int(
        "Plan parallelism (number of parallel plan executions)",
        default=config.plan.parallelism,
    )
    config.plan.parallelism = plan_parallelism

    implement_parallelism = _prompt_int(
        "Implement parallelism (number of parallel implementations)",
        default=config.implement.parallelism,
    )
    config.implement.parallelism = implement_parallelism

    # Prompt for sync frequency
    sync_frequency = _prompt_with_default(
        "Sync frequency (e.g., '10m', '1h', '1d')",
        default=config.sync.frequency,
        required=True,
    )
    config.sync.frequency = sync_frequency

    # Save configuration
    logger.info("Saving configuration...")
    manager.save(config)
    logger.info(f"Configuration saved to: {manager.config_path}")
    logger.info("Setup complete! You can now use gh-worker commands.")
    logger.info("Next steps:")
    logger.info("  1. Add repositories: gh-worker repositories add owner/repo")
    logger.info("  2. Sync issues: gh-worker issues sync --all-repos")
    logger.info("  3. Generate plans: gh-worker issues plan --all-repos")
    logger.info("  4. Implement: gh-worker issues implement --all-repos")
