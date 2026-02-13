# Data Models

## Overview

The data models provide structured representations of core domain objects: GitHub issues, implementation plans, and repositories. Built using dataclasses, they support serialization, validation, and conversion between different formats (JSON, YAML, markdown).

## Models

### Issue

Represents a GitHub issue with all metadata, located in [src/gh_worker/models/issue.py](src/gh_worker/models/issue.py).

**Fields:**

- `number: int` - Issue number
- `title: str` - Issue title
- `body: str` - Issue description/content
- `state: str` - Issue state ("open", "closed")
- `created_at: datetime` - Creation timestamp
- `updated_at: datetime` - Last update timestamp
- `author: str` - Issue author username
- `labels: list[str]` - List of label names
- `url: str` - GitHub URL for the issue
- `repository: str` - Repository in "owner/repo" format

**Methods:**

- `from_gh_json(data, repository)` - Create from GitHub CLI JSON
- `to_markdown()` - Convert to markdown format

**JSON Conversion:**
Parses GitHub CLI JSON output:

- Handles missing fields (body defaults to "")
- Converts ISO 8601 timestamps (with "Z" suffix)
- Extracts author login (handles missing author)
- Extracts label names from label objects
- Requires repository parameter (not in GitHub JSON)

**Markdown Format:**

```markdown
# {title}

**Issue**: #{number}
**Repository**: {repository}
**State**: {state}
**Author**: {author}
**Created**: {created_at}
**Updated**: {updated_at}
**URL**: {url}
**Labels**: {label1, label2, ...}

---

{body}
```

### PlanMetadata

Tracks implementation plan status and results, located in [src/gh_worker/models/plan.py](src/gh_worker/models/plan.py).

**Fields:**

- `issue_number: int` - Associated issue number
- `repository: str` - Repository in "owner/repo" format
- `created_at: datetime` - Plan creation timestamp
- `status: PlanStatus` - Current status (enum)
- `session_id: str | None` - Agent session ID (optional)
- `branch_name: str | None` - Implementation branch (optional)
- `pr_url: str | None` - Pull request URL (optional)
- `error_message: str | None` - Error details if failed (optional)
- `completed_at: datetime | None` - Completion timestamp (optional)
- `merged_at: datetime | None` - PR merge timestamp (optional)
- `agent: str | None` - Agent name used (optional)
- `model: str | None` - Model used by agent (optional)
- `commit_hash: str | None` - Repository commit when plan was generated (optional)
- `plan_file: Path | None` - Path to plan file (not serialized)

**Methods:**

- `to_dict()` - Convert to dictionary for YAML
- `from_dict(data)` - Create from dictionary
- `save(path)` - Save to YAML file
- `load(path)` - Load from YAML file

**Status Lifecycle:**

1. `PENDING` - Plan created, waiting for review/approval
1. `APPROVED` - Plan approved, ready for implementation
1. `IN_PROGRESS` - Implementation in progress
1. `COMPLETED` - Successfully implemented (may have PR or be waiting for review)
1. `FAILED` - Implementation failed

### PlanStatus

Enumeration for plan status values.

**Values:**

- `PENDING = "pending"`
- `APPROVED = "approved"`
- `IN_PROGRESS = "in_progress"`
- `COMPLETED = "completed"`
- `FAILED = "failed"`

**Serialization:**

- Uses enum value (string) for YAML
- Parsed back to enum on deserialization

### Repository

Simple repository identifier with parsing and formatting, located in [src/gh_worker/models/repository.py](src/gh_worker/models/repository.py).

**Fields:**

- `owner: str` - Repository owner (user or organization)
- `name: str` - Repository name

**Methods:**

- `from_string(repo_string)` - Parse "owner/repo" string
- `__str__()` - Format as "owner/repo"
- `full_name` - Property returning "owner/repo" format

**Validation:**

- Requires exactly one "/" separator
- Owner and name must be non-empty
- Strips whitespace from owner and name

## Serialization

### Issue → Markdown

Uses `to_markdown()` method:

1. Creates title header
1. Adds metadata fields
1. Includes labels if present
1. Separates metadata from body with "---"
1. Appends full issue body

**Use Case:**

- Storage in description.md files
- Human-readable issue archives
- Issue templates

### GitHub JSON → Issue

Uses `from_gh_json()` classmethod:

1. Parses required fields (number, title, state, timestamps, URL)
1. Handles optional fields (body, author, labels)
1. Converts ISO 8601 timestamps with timezone
1. Extracts nested data (author login, label names)
1. Adds repository context

**Timestamp Handling:**

- Replaces "Z" suffix with "+00:00" (UTC)
- Uses `datetime.fromisoformat()`
- Results in timezone-aware datetime objects

### PlanMetadata → YAML

Uses `to_dict()` and `save()`:

1. Converts all fields to dictionary
1. Serializes datetimes to ISO 8601 strings
1. Converts enum to value (string)
1. Handles None values
1. Writes YAML with human-readable formatting

**YAML Example:**

```yaml
issue_number: 42
repository: octocat/hello-world
created_at: '2024-01-15T14:30:22.123456+00:00'
status: completed
session_id: abc123
branch_name: fix-issue-42
pr_url: https://github.com/octocat/hello-world/pull/43
error_message: null
completed_at: '2024-01-15T15:45:30.987654+00:00'
merged_at: null
agent: claude-code
model: claude-sonnet-4
commit_hash: abc123def456
```

### YAML → PlanMetadata

Uses `from_dict()` and `load()`:

1. Reads YAML file
1. Parses dictionary
1. Converts timestamps from ISO 8601
1. Parses enum from string value
1. Handles missing optional fields (defaults to None)
1. Creates PlanMetadata instance

### Repository Parsing

Uses `from_string()`:

1. Split on "/" delimiter
1. Validate exactly 2 parts
1. Validate non-empty owner and name
1. Strip whitespace
1. Create Repository instance

**Valid Formats:**

- "owner/repo"
- "owner / repo" (whitespace stripped)

**Invalid Formats:**

- "repo" (missing owner)
- "owner/repo/subpath" (too many parts)
- "/repo" (empty owner)
- "owner/" (empty name)

## Requirements

### Issue Model

**MUST:**

- Include all fields from GitHub API (number, title, body, state, timestamps, author, labels, URL)
- Support creation from GitHub CLI JSON
- Support conversion to markdown
- Use timezone-aware datetime for timestamps
- Handle missing or null fields (body, author)
- Store repository association

**SHOULD:**

- Preserve all GitHub metadata
- Use human-readable markdown format
- Handle empty label lists gracefully
- Strip unnecessary whitespace

**MAY:**

- Support markdown → Issue parsing
- Provide HTML conversion
- Support custom fields or extensions
- Implement issue comparison or diffing

### PlanMetadata Model

**MUST:**

- Track issue association (issue_number, repository)
- Support status lifecycle (PENDING → APPROVED → IN_PROGRESS → COMPLETED/FAILED)
- Store agent results (session_id, branch_name, pr_url)
- Record timestamps (created_at, completed_at)
- Support YAML serialization and deserialization
- Handle optional fields gracefully

**SHOULD:**

- Use enum for status values
- Serialize timestamps in ISO 8601 format
- Create parent directories on save
- Validate status transitions
- Log metadata changes

**MAY:**

- Support metadata versioning or history
- Implement computed properties (duration, etc.)
- Provide metadata validation
- Support custom metadata fields

### Repository Model

**MUST:**

- Store owner and name separately
- Support parsing from "owner/repo" string
- Format as "owner/repo" string
- Validate format (exactly one "/", non-empty parts)
- Strip whitespace from owner and name

**SHOULD:**

- Raise ValueError for invalid formats
- Provide descriptive error messages
- Support equality comparison
- Implement hash for use in sets/dicts

**MAY:**

- Support alternative formats (URLs, SSH)
- Validate owner and name patterns
- Provide repository metadata (description, stars, etc.)
- Support organization vs. user distinction

### Serialization

**MUST:**

- Use appropriate formats for each model (JSON, YAML, markdown)
- Handle datetime serialization consistently (ISO 8601)
- Support bidirectional conversion where applicable
- Preserve all data during round-trip
- Handle missing or null values

**SHOULD:**

- Use human-readable formats where possible
- Validate data on deserialization
- Provide clear error messages for invalid data
- Support partial deserialization (optional fields)

**MAY:**

- Support multiple serialization formats per model
- Implement schema validation
- Provide serialization hooks or callbacks
- Support compression or encoding

### Validation

**MUST:**

- Validate required fields are present
- Check data types match declarations
- Validate format constraints (repository format, enum values)
- Raise appropriate exceptions for invalid data

**SHOULD:**

- Validate field values (non-negative numbers, valid URLs)
- Check timestamp ordering (created_at < updated_at)
- Validate state transitions (plan status)
- Provide validation error details

**MAY:**

- Implement custom validators per field
- Support validation policies or rules
- Provide validation summaries
- Support relaxed validation modes

## Usage Examples

### Create Issue from GitHub JSON

```python
from gh_worker.models.issue import Issue

# GitHub CLI JSON output
gh_json = {
    "number": 42,
    "title": "Add authentication",
    "body": "We need to add user authentication...",
    "state": "open",
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2024-01-15T14:30:00Z",
    "author": {"login": "octocat"},
    "labels": [{"name": "feature"}, {"name": "priority-high"}],
    "url": "https://github.com/octocat/hello-world/issues/42"
}

issue = Issue.from_gh_json(gh_json, repository="octocat/hello-world")
print(issue.title)  # "Add authentication"
print(issue.labels)  # ["feature", "priority-high"]
```

### Convert Issue to Markdown

```python
markdown = issue.to_markdown()
with open("issue-42.md", "w") as f:
    f.write(markdown)
```

### Create and Save Plan Metadata

```python
from gh_worker.models.plan import PlanMetadata, PlanStatus
from datetime import datetime
from pathlib import Path

metadata = PlanMetadata(
    issue_number=42,
    repository="octocat/hello-world",
    created_at=datetime.now(),
    status=PlanStatus.PENDING
)

metadata.save(Path("issue-42/plan.yaml"))
```

### Update Plan Status

```python
# Load existing metadata
metadata = PlanMetadata.load(Path("issue-42/plan.yaml"))

# Update status
metadata.status = PlanStatus.IN_PROGRESS
metadata.session_id = "abc123"

# Save changes
metadata.save(Path("issue-42/plan.yaml"))

# Mark as completed
metadata.status = PlanStatus.COMPLETED
metadata.branch_name = "fix-issue-42"
metadata.pr_url = "https://github.com/octocat/hello-world/pull/43"
metadata.completed_at = datetime.now()
metadata.save(Path("issue-42/plan.yaml"))
```

### Parse Repository

```python
from gh_worker.models.repository import Repository

# From string
repo = Repository.from_string("octocat/hello-world")
print(repo.owner)  # "octocat"
print(repo.name)  # "hello-world"
print(repo.full_name)  # "octocat/hello-world"

# Create directly
repo = Repository(owner="octocat", name="hello-world")
print(str(repo))  # "octocat/hello-world"
```

### Handle Invalid Repository

```python
try:
    repo = Repository.from_string("invalid-format")
except ValueError as e:
    print(f"Error: {e}")
    # Error: Repository must be in 'owner/repo' format, got: invalid-format
```

## Extension Points

The data models can be extended to support:

- Additional GitHub entities (pull requests, comments, reviews)
- Custom metadata fields
- Validation frameworks (pydantic, marshmallow)
- Alternative serialization formats (JSON, protobuf, msgpack)
- Schema evolution and migration
- Computed or derived fields
- Relationships between models
- Event sourcing or audit trails
