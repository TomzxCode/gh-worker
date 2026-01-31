# Configuration Management

## Overview

The configuration system provides type-safe, persistent settings management using Pydantic models and YAML serialization. It follows the XDG Base Directory specification for configuration file placement and supports dotted-path access for nested settings.

## Architecture

### Schema Definition

Configuration schema defined using Pydantic models in [src/gh_worker/config/schema.py](src/gh_worker/config/schema.py).

**Model Hierarchy:**

```
AppConfig (root)
├── issues_path: Path
├── repository_path: Path
├── plan: PlanConfig
│   └── parallelism: int
├── implement: ImplementConfig
│   └── parallelism: int
├── sync: SyncConfig
│   └── frequency: str
└── agent: AgentConfig
    ├── default: str
    └── claude_code_path: str | None
```

### Configuration Models

#### AppConfig

Root configuration containing all application settings.

**Fields:**

- `issues_path` - Directory for storing issue files (default: None)
- `repository_path` - Directory for cloning repositories (default: None)
- `plan` - Plan command configuration
- `implement` - Implementation command configuration
- `sync` - Sync command configuration
- `agent` - Agent configuration

#### PlanConfig

Settings for plan generation.

**Fields:**

- `parallelism` - Number of parallel plan executions (default: 1, minimum: 1)

#### ImplementConfig

Settings for plan implementation.

**Fields:**

- `parallelism` - Number of parallel implementations (default: 1, minimum: 1)

#### SyncConfig

Settings for issue synchronization.

**Fields:**

- `frequency` - Sync interval (default: "1h", examples: "10m", "1h", "1d")

#### AgentConfig

Settings for LLM agents.

**Fields:**

- `default` - Default agent name (default: "claude-code")
- `claude_code_path` - Path to claude-code binary (default: None, uses PATH)

### Configuration Manager

Handles persistence and access, implemented in [src/gh_worker/config/manager.py](src/gh_worker/config/manager.py).

**Core Methods:**

- `load()` - Load configuration from disk (returns defaults if file missing)
- `save()` - Persist configuration to disk
- `get()` - Retrieve value by dotted key path
- `set()` - Update value by dotted key path (auto-saves)

**Internal Methods:**

- `_default_config_path()` - Resolve XDG-compliant config path

## File Format

### Location

Configuration stored at: `~/.config/gh-worker/config.yaml`

Follows XDG Base Directory specification:

- Respects `$XDG_CONFIG_HOME` if set
- Falls back to `~/.config`
- Creates directory structure automatically

### YAML Structure

```yaml
issues_path: /var/gh-worker/issues
repository_path: /var/gh-worker/repos
plan:
  parallelism: 3
implement:
  parallelism: 2
sync:
  frequency: 30m
agent:
  default: claude-code
  claude_code_path: /usr/local/bin/claude-code
```

### Serialization

- Path objects converted to strings in JSON mode
- Keys not sorted (preserves logical grouping)
- Block style formatting (no flow style)
- Null values omitted for optional fields

## Access Patterns

### Dotted Key Path

Configuration values accessed via dot-separated paths:

- `plan.parallelism` - Accesses `config.plan.parallelism`
- `agent.default` - Accesses `config.agent.default`
- `issues_path` - Accesses `config.issues_path`

### Resolution Logic

1. Split key by "." into parts
1. Traverse object hierarchy using `getattr()`
1. Raise `KeyError` if any part not found
1. Return final value

### Setting Values

1. Load configuration if not cached
1. Traverse to parent object
1. Set attribute on parent
1. Automatically save to disk

## Validation

### Pydantic Validation

All configuration validated through Pydantic:

- Type checking (int, str, Path, etc.)
- Range constraints (parallelism >= 1)
- Default value provision
- Field descriptions for documentation

### Error Handling

- Invalid types raise `ValidationError`
- Missing required fields raise `ValidationError`
- Invalid keys raise `KeyError`
- File I/O errors propagate as filesystem exceptions

## Default Behavior

### Missing Configuration File

When config file doesn't exist:

1. Returns `AppConfig()` with all defaults
1. Does not create file automatically
1. File created only on first `save()` call

### Default Values

- Parallelism: 1 (sequential execution)
- Sync frequency: "1h" (hourly)
- Agent: "claude-code"
- Paths: None (must be configured for relevant operations)

## Requirements

### Configuration Schema

**MUST:**

- Use Pydantic models for all configuration structures
- Provide default values for all non-required fields
- Validate field types and constraints
- Support serialization to/from dictionaries
- Include field descriptions
- Use Path type for filesystem paths

**SHOULD:**

- Group related settings into nested models
- Use descriptive field names
- Provide examples in descriptions
- Set reasonable default values
- Validate ranges for numeric fields (e.g., parallelism >= 1)

**MAY:**

- Add computed properties for derived values
- Provide field aliases for compatibility
- Support environment variable overrides
- Include field examples in schema

### Configuration Manager

**MUST:**

- Follow XDG Base Directory specification
- Load configuration from `~/.config/gh-worker/config.yaml`
- Create parent directories automatically on save
- Parse YAML using safe_load
- Support dotted key path access (get/set)
- Auto-save after set operations
- Return defaults when file missing (not error)
- Cache loaded configuration

**SHOULD:**

- Create directory structure with appropriate permissions
- Use human-readable YAML formatting
- Preserve key order in output
- Handle Path serialization correctly
- Provide clear error messages for invalid keys

**MAY:**

- Support custom config file paths
- Provide config validation command
- Support config migration between versions
- Allow config inheritance or includes

### YAML Serialization

**MUST:**

- Use block style (not flow style)
- Convert Path objects to strings
- Handle None/null values correctly
- Preserve nested structure

**SHOULD:**

- Maintain logical key grouping
- Use consistent indentation (2 spaces)
- Omit null values for cleaner output

**MAY:**

- Include comments in generated YAML
- Support multi-document YAML files
- Provide YAML validation

### Dotted Path Access

**MUST:**

- Split paths on "." delimiter
- Traverse nested objects using attribute access
- Raise KeyError for invalid paths with full path in message
- Support both get and set operations
- Auto-save after set operations

**SHOULD:**

- Lazy-load configuration on first access
- Provide helpful error messages with valid path hints
- Validate path exists before setting

**MAY:**

- Support array indexing in paths (e.g., "items[0].name")
- Provide path validation function
- Support wildcard or glob patterns for bulk operations

### Validation

**MUST:**

- Validate types match schema
- Enforce constraints (min/max values)
- Reject invalid configurations with clear errors
- Validate on load and set operations

**SHOULD:**

- Provide detailed validation error messages
- Suggest corrections for common mistakes
- Validate path existence for filesystem paths

**MAY:**

- Support custom validators per field
- Provide validation summary for multiple errors
- Support strict vs. lenient validation modes

## Usage Examples

### Load Configuration

```python
from gh_worker.config.manager import ConfigManager

manager = ConfigManager()
config = manager.load()

print(config.plan.parallelism)  # 1
print(config.agent.default)  # "claude-code"
```

### Save Configuration

```python
from gh_worker.config.schema import AppConfig, PlanConfig
from pathlib import Path

config = AppConfig(
    issues_path=Path("/var/gh-worker/issues"),
    repository_path=Path("/var/gh-worker/repos"),
    plan=PlanConfig(parallelism=3)
)

manager.save(config)
```

### Get Value by Dotted Path

```python
parallelism = manager.get("plan.parallelism")
agent_name = manager.get("agent.default")
```

### Set Value by Dotted Path

```python
# Automatically saves after setting
manager.set("plan.parallelism", 5)
manager.set("agent.default", "opencode")
manager.set("sync.frequency", "15m")
```

### Custom Config Path

```python
from pathlib import Path

manager = ConfigManager(config_path=Path("/etc/gh-worker/config.yaml"))
config = manager.load()
```

## Extension Points

The configuration system can be extended to support:

- Per-repository configuration overrides
- Environment variable expansion in values
- Configuration templates or presets
- Configuration validation command
- Configuration migration utilities
- Remote configuration backends
- Encrypted sensitive values
- Configuration change notifications
