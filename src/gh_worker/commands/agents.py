"""Agent management commands."""

from pathlib import Path

import structlog

from gh_worker.agents.registry import get_registry
from gh_worker.config.manager import ConfigManager
from gh_worker.config.schema import NamedAgent

logger = structlog.get_logger()


def default_command(
    agent: str | None = None,
    model: str | None = None,
    list_all: bool = False,
    config_path: Path | None = None,
) -> None:
    """Set or list default models per agent type.

    Args:
        agent: Agent type (e.g., 'claude-code', 'cursor-agent')
        model: Model to set as default for the agent
        list_all: If True, list all default models
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)
    config = manager.load()

    if list_all:
        if not config.agent.defaults:
            logger.info("No default models configured")
            return
        for agent_name, model_name in sorted(config.agent.defaults.items()):
            logger.info("Default model", agent=agent_name, model=model_name)
        return

    if agent is None:
        logger.error("Agent name is required (or use --list to list all)")
        return

    if model is None:
        logger.error("Model is required")
        return

    # Validate agent exists
    registry = get_registry()
    if not registry.is_registered(agent):
        logger.error(
            "Unknown agent",
            agent=agent,
            available=", ".join(sorted(registry.list_agents())),
        )
        return

    config.agent.defaults[agent] = model
    manager.save(config)
    logger.info("Default model set", agent=agent, model=model)


def create_command(
    name: str,
    agent: str,
    model: str | None,
    config_path: Path | None = None,
) -> None:
    """Create a named agent configuration.

    Args:
        name: Name for the agent configuration
        agent: Base agent type (e.g., 'claude-code', 'cursor-agent')
        model: Model to use (optional, uses agent default if not specified)
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)
    config = manager.load()

    if name in config.agent.named:
        logger.error("Named agent already exists", name=name)
        return

    # Validate agent exists
    registry = get_registry()
    if not registry.is_registered(agent):
        logger.error(
            "Unknown agent",
            agent=agent,
            available=", ".join(sorted(registry.list_agents())),
        )
        return

    config.agent.named[name] = NamedAgent(agent=agent, model=model)
    manager.save(config)
    logger.info("Named agent created", name=name, agent=agent, model=model)


def list_command(config_path: Path | None = None) -> None:
    """List all named agent configurations.

    Args:
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)
    config = manager.load()

    if not config.agent.named:
        logger.info("No named agents configured")
        return

    for name, named_agent in sorted(config.agent.named.items()):
        model_str = named_agent.model or "(default)"
        logger.info("Named agent", name=name, agent=named_agent.agent, model=model_str)


def delete_command(name: str, config_path: Path | None = None) -> None:
    """Delete a named agent configuration.

    Args:
        name: Name of the agent configuration to delete
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)
    config = manager.load()

    if name not in config.agent.named:
        logger.error("Named agent not found", name=name)
        return

    del config.agent.named[name]
    manager.save(config)
    logger.info("Named agent deleted", name=name)


def update_command(
    name: str,
    agent: str | None = None,
    model: str | None = None,
    config_path: Path | None = None,
) -> None:
    """Update a named agent configuration.

    Args:
        name: Name of the agent configuration to update
        agent: New base agent type (optional)
        model: New model to use (optional)
        config_path: Path to config file
    """
    manager = ConfigManager(config_path)
    config = manager.load()

    if name not in config.agent.named:
        logger.error("Named agent not found", name=name)
        return

    if agent is None and model is None:
        logger.error("At least one of agent or model must be provided")
        return

    # Validate agent exists if provided
    if agent is not None:
        registry = get_registry()
        if not registry.is_registered(agent):
            logger.error(
                "Unknown agent",
                agent=agent,
                available=", ".join(sorted(registry.list_agents())),
            )
            return
        config.agent.named[name].agent = agent

    if model is not None:
        config.agent.named[name].model = model

    manager.save(config)
    logger.info(
        "Named agent updated",
        name=name,
        agent=config.agent.named[name].agent,
        model=config.agent.named[name].model,
    )
