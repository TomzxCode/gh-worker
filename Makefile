.PHONY: help install format format-check lint lint-fix test test-unit test-integration ci docs-serve docs-build build clean run

# Default target
help:
	@echo "gh-worker Makefile"
	@echo ""
	@echo "Development:"
	@echo "  install          Install/sync dependencies (uv sync)"
	@echo "  format           Format code with ruff"
	@echo "  format-check     Check formatting (CI)"
	@echo "  lint             Run ruff check"
	@echo "  lint-fix         Run ruff check with --fix"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  ci               Run full CI (lint + format-check + test)"
	@echo ""
	@echo "Documentation:"
	@echo "  docs-serve       Serve docs locally (mkdocs serve)"
	@echo "  docs-build       Build docs static site"
	@echo ""
	@echo "Build & Run:"
	@echo "  build            Build the package"
	@echo "  run              Run ghw (usage: make run ARGS='issues list')"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean            Remove caches and build artifacts"

# Development
install:
	uv sync --dev

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

test:
	uv run pytest

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest tests/integration/

ci: format-check lint test

# Documentation
docs-serve:
	uv run mkdocs serve

docs-build:
	uv run mkdocs build

# Build & Run
build:
	uv build

run:
	uv run ghw $(ARGS)

# Maintenance
clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
