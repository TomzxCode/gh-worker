# Storage System

## Overview

The storage system provides file-based persistence for GitHub issues and implementation plans using a hierarchical directory structure. It manages issue metadata, plan versions, and timestamps for incremental synchronization, all organized by repository and issue number.

## Architecture

### Directory Structure

```
{issues_path}/
  {owner}/
    {repo_name}/
      .updated-at                    # Repository last sync timestamp
      {issue_number}/
        description.md               # Issue content in markdown
        .updated-at                  # Issue last update timestamp
        plan-20240115-143022.md      # Implementation plan (versioned)
        plan-20240115-143022.yaml    # Plan metadata
        plan-20240116-091544.md      # Newer plan version
        plan-20240116-091544.yaml    # Newer plan metadata
```

### Store Components

#### IssueStore

Manages issue storage and retrieval, located in [src/gh_worker/storage/issue_store.py](src/gh_worker/storage/issue_store.py).

**Methods:**

- `save_issue()` - Persist issue to filesystem
- `load_issue()` - Retrieve issue from filesystem (placeholder)
- `get_updated_at()` - Get issue last update timestamp
- `set_repo_updated_at()` - Set repository last sync timestamp
- `get_repo_updated_at()` - Get repository last sync timestamp
- `list_issues()` - List all issue numbers for repository
- `list_repositories()` - List all repositories in store
- `get_issue_dir()` - Resolve issue directory path
- `get_repo_dir()` - Resolve repository directory path

#### PlanStore

Manages plan storage and versioning, located in [src/gh_worker/storage/plan_store.py](src/gh_worker/storage/plan_store.py).

**Methods:**

- `create_plan()` - Create new plan with metadata
- `get_latest_plan()` - Retrieve most recent plan for issue
- `list_plans()` - List all plans for issue (sorted newest first)
- `update_metadata()` - Update plan metadata
- `has_plan()` - Check if issue has any plans
- `get_issue_dir()` - Resolve issue directory path

## Data Storage

### Issue Storage

**Files:**

- `description.md` - Issue content formatted as markdown
- `.updated-at` - ISO 8601 timestamp of last issue update

**Format:**
Issues saved using `Issue.to_markdown()` method, preserving:

- Title
- Number
- State
- Labels
- Author
- Creation and update timestamps
- Full body content

**Timestamps:**

- Stored in ISO 8601 format (e.g., "2024-01-15T14:30:22.123456+00:00")
- Parsed using `datetime.fromisoformat()`
- Used for incremental sync filtering

### Plan Storage

**Files:**

- `plan-YYYYMMDD-HHMMSS.md` - Plan content with timestamp in filename
- `plan-YYYYMMDD-HHMMSS.yaml` - Associated metadata

**Versioning:**

- Multiple plans per issue supported
- Filename includes creation timestamp
- Sorted reverse chronologically (newest first)
- Latest plan retrieved by filename sort

**Metadata:**
Stored as YAML with fields:

- `issue_number` - Associated issue number
- `repository` - Full repository name (owner/name)
- `created_at` - Plan creation timestamp
- `status` - Plan status (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- `session_id` - Agent session ID (optional)
- `branch_name` - Implementation branch (optional)
- `pr_url` - Pull request URL (optional)
- `error` - Error message if failed (optional)

### Repository Metadata

**Files:**

- `.updated-at` - Last sync timestamp for repository

**Purpose:**

- Enables incremental sync (only fetch issues updated since last sync)
- Updated after successful sync operation
- Stored at repository level, not per-issue

## Path Resolution

### Issue Directory Path

```
{issues_path}/{owner}/{repo_name}/{issue_number}/
```

Example: `/var/gh-worker/issues/octocat/hello-world/42/`

### Repository Directory Path

```
{issues_path}/{owner}/{repo_name}/
```

Example: `/var/gh-worker/issues/octocat/hello-world/`

### Plan File Path

```
{issue_dir}/plan-{timestamp}.md
```

Example: `/var/gh-worker/issues/octocat/hello-world/42/plan-20240115-143022.md`

## Discovery Operations

### List Issues

Scans repository directory for subdirectories with numeric names:

1. Check if repository directory exists
1. Iterate over directory contents
1. Filter for directories with `isdigit()` names
1. Convert to integers and sort
1. Return sorted list

### List Repositories

Scans issues path for owner/repo structure:

1. Iterate over top-level directories (owners)
1. Skip hidden directories (starting with ".")
1. For each owner, iterate over subdirectories (repos)
1. Skip hidden directories
1. Create Repository objects with owner/name
1. Return list of repositories

### List Plans

Finds all plan files for an issue:

1. Glob for `plan-*.md` files in issue directory
1. Sort reverse chronologically
1. Load metadata from corresponding `.yaml` files
1. Create default metadata if `.yaml` missing (using file mtime)
1. Return list of (plan_file, metadata) tuples

## Metadata Management

### Plan Metadata Creation

1. Generate timestamp-based filename
1. Write plan content to markdown file
1. Create PlanMetadata object with default status (PENDING)
1. Save metadata to YAML file
1. Return metadata object

### Plan Metadata Updates

1. Validate metadata has plan_file set
1. Resolve metadata file path (same name, .yaml extension)
1. Save metadata to YAML using `PlanMetadata.save()`

### Fallback Metadata

If metadata file missing:

- Use file modification time as created_at
- Set status to PENDING
- Other fields remain None

## Requirements

### Directory Structure

**MUST:**

- Create directories with `parents=True, exist_ok=True`
- Use owner/repo/issue hierarchy
- Store timestamps in hidden `.updated-at` files
- Use numeric directory names for issues
- Support multiple plans per issue with unique filenames

**SHOULD:**

- Skip hidden directories (starting with ".") in discovery
- Use consistent path separators (Path objects)
- Create parent directories automatically
- Handle missing directories gracefully (return empty lists)

**MAY:**

- Implement directory locking for concurrent access
- Compress old plans to save space
- Provide directory cleanup utilities
- Support symbolic links or alternative layouts

### Issue Storage

**MUST:**

- Save issues as markdown using `Issue.to_markdown()`
- Store update timestamps in ISO 8601 format
- Update repository timestamp after sync
- Create issue directories automatically
- Support timestamp retrieval for individual issues

**SHOULD:**

- Preserve all issue fields in markdown
- Use UTF-8 encoding for all files
- Handle filesystem errors gracefully
- Log storage operations

**MAY:**

- Implement issue loading from markdown (currently placeholder)
- Cache issue data in memory
- Support issue deletion
- Provide issue update detection

### Plan Storage

**MUST:**

- Version plans with timestamp in filename (YYYYMMDD-HHMMSS)
- Store plan content and metadata separately
- Use markdown for content, YAML for metadata
- Return latest plan by filename sort
- Create default metadata if missing
- Support metadata updates

**SHOULD:**

- Sort plans reverse chronologically
- Validate metadata on save
- Log plan creation and updates
- Handle missing metadata gracefully

**MAY:**

- Implement plan archiving or deletion
- Support plan comparison or diffing
- Provide plan rollback functionality
- Track plan revisions or lineage

### Timestamp Management

**MUST:**

- Use ISO 8601 format for all timestamps
- Store in UTC or with timezone information
- Parse using `datetime.fromisoformat()`
- Handle "Z" suffix for UTC timestamps

**SHOULD:**

- Use timezone-aware datetime objects
- Validate timestamp format on read
- Preserve microsecond precision

**MAY:**

- Support alternative timestamp formats
- Provide timestamp conversion utilities
- Track multiple timestamp types (created, updated, accessed)

### Discovery Operations

**MUST:**

- Return empty lists for missing directories (not errors)
- Filter for directories only (not files)
- Skip hidden directories (starting with ".")
- Validate numeric directory names for issues
- Sort results consistently

**SHOULD:**

- Handle permission errors gracefully
- Log discovery operations for debugging
- Return stable, deterministic results

**MAY:**

- Cache discovery results with TTL
- Support filtering or search criteria
- Provide pagination for large result sets
- Implement watch/notification for changes

### Metadata Management

**MUST:**

- Save metadata as YAML
- Load metadata using `PlanMetadata.load()`
- Create default metadata if file missing
- Validate metadata has plan_file before update
- Store plan_file path in metadata

**SHOULD:**

- Use human-readable YAML formatting
- Preserve metadata field order
- Handle malformed metadata files gracefully
- Log metadata operations

**MAY:**

- Validate metadata schema on load
- Support metadata migration between versions
- Provide metadata search or query
- Track metadata change history

## Usage Examples

### Save Issue

```python
from gh_worker.storage.issue_store import IssueStore
from gh_worker.models.issue import Issue
from pathlib import Path

store = IssueStore(Path("/var/gh-worker/issues"))
issue = Issue(...)  # Issue object from GitHub API

store.save_issue(issue)
```

### Get Repository Last Sync

```python
from gh_worker.models.repository import Repository

repo = Repository(owner="octocat", name="hello-world")
last_sync = store.get_repo_updated_at(repo)

if last_sync:
    print(f"Last synced: {last_sync.isoformat()}")
```

### Create Plan

```python
from gh_worker.storage.plan_store import PlanStore

plan_store = PlanStore(Path("/var/gh-worker/issues"))
plan_content = "## Implementation Plan\n\n1. Step one\n2. Step two"

metadata = plan_store.create_plan(repo, issue_number=42, content=plan_content)
print(f"Plan created: {metadata.plan_file}")
```

### Get Latest Plan

```python
result = plan_store.get_latest_plan(repo, issue_number=42)

if result:
    plan_file, metadata = result
    plan_content = plan_file.read_text()
    print(f"Status: {metadata.status}")
    print(f"Content:\n{plan_content}")
```

### List All Plans

```python
plans = plan_store.list_plans(repo, issue_number=42)

for plan_file, metadata in plans:
    print(f"{plan_file.name}: {metadata.status} ({metadata.created_at})")
```

### Update Plan Metadata

```python
from gh_worker.models.plan import PlanStatus

# Get latest plan
_, metadata = plan_store.get_latest_plan(repo, issue_number=42)

# Update status
metadata.status = PlanStatus.IN_PROGRESS
metadata.session_id = "abc123"

# Save changes
plan_store.update_metadata(metadata)
```

### List Repositories

```python
repositories = store.list_repositories()

for repo in repositories:
    issues = store.list_issues(repo)
    print(f"{repo.full_name}: {len(issues)} issues")
```

## Extension Points

The storage system can be extended to support:

- Alternative backends (database, cloud storage)
- Compression for old issues/plans
- Full-text search across issues and plans
- Atomic operations with transactions
- Concurrent access with locking
- Issue and plan archiving/deletion
- Storage quotas and cleanup policies
- Backup and restore utilities
