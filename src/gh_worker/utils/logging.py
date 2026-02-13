"""Logging configuration using structlog."""

import logging
import sys

import structlog


def setup_logging_for_tui(level: str = "INFO") -> None:
    """Configure logging for TUI mode - routes output through Textual instead of stdout.

    Use this when running the TUI to prevent plan/implement logger output from
    writing over the TUI display.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove any existing handlers (e.g. StreamHandler writing to stdout)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # TextualHandler routes logs through the active Textual app when one exists,
    # avoiding stdout/stderr interference with the TUI
    from textual.logging import TextualHandler

    handler = TextualHandler(stderr=True, stdout=False)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
