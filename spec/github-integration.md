# GitHub Integration

## Overview

The GitHub integration layer provides a Python wrapper around the GitHub CLI (`gh`) for performing repository operations. It handles issue management, pull request creation, repository cloning, and authentication, with automatic retry logic for transient failures.

## Architecture

### GHClient Class

Primary interface for GitHub operations, located in [src/gh_worker/github/client.py](src/gh_worker/github/client.py).

**Initialization:**

- `repository_path` - Base directory for cloning repositories (optional, required for clone/PR operations)

**Core Methods:**

- `list_issues()` - Fetch issues with filtering and pagination
- `get_issue()` - Retrieve specific issue by number
- `create_pr()` - Create pull request from branch
- `clone_repo()` - Clone repository to local filesystem
- `check_auth()` - Verify GitHub CLI authentication status

**Internal Methods:**

- `_run_command()` - Execute gh CLI commands with retry and error handling
- `_get_repo_path()` - Resolve local repository path

## Operations

### Issue Listing

Retrieves issues from a repository with multiple filtering options.

**Parameters:**

- `repository` - Repository object (owner/name)
- `state` - Issue state filter: "open", "closed", or "all" (default: "open")
- `since` - ISO 8601 timestamp for filtering by update time (client-side filtering)
- `search` - GitHub search query string

**Fields Retrieved:**

- number, title, body, state
- createdAt, updatedAt
- author, labels, url

**Behavior:**

- Fetches up to 1000 issues per request
- `since` filtering performed client-side after fetch
- Returns list of issue dictionaries

### Issue Retrieval

Fetches a single issue by number.

**Parameters:**

- `repository` - Repository object
- `issue_number` - Issue number to retrieve

**Returns:**

- Issue dictionary with same fields as `list_issues()`

### Pull Request Creation

Creates a pull request in a repository.

**Parameters:**

- `repository` - Repository object
- `title` - PR title
- `body` - PR description
- `head` - Source branch name
- `base` - Target branch name (default: "main")

**Behavior:**

- Executes in repository working directory
- Requires repository to be cloned locally
- Returns PR URL as string

### Repository Cloning

Clones a repository to the local filesystem.

**Parameters:**

- `repository` - Repository object

**Behavior:**

- Checks if repository already exists (skips clone if present)
- Creates parent directories as needed
- Clones to `{repository_path}/{owner}/{name}/`
- Returns path to cloned repository

**Requirements:**

- `repository_path` must be set during client initialization
- Raises `ValueError` if repository_path is not set

### Authentication Check

Verifies GitHub CLI is authenticated.

**Returns:**

- `True` if authenticated
- `False` if not authenticated or gh CLI unavailable

## Error Handling

### Retry Logic

All CLI commands use the `@retry` decorator with:

- Maximum 3 attempts
- Initial delay of 1 second
- Exponential backoff factor of 2.0

Retries are triggered by:

- Network errors
- Rate limiting
- Transient GitHub API errors

### Exception Handling

- `subprocess.CalledProcessError` - Converted to `RuntimeError` with stderr details
- `subprocess.TimeoutExpired` - Converted to `RuntimeError` after 300 seconds
- `ValueError` - Raised for invalid configuration or missing parameters

### Error Logging

All failures logged with structured fields:

- `command` - Full command string
- `stderr` - Error output from gh CLI
- `returncode` - Process exit code
- `cwd` - Working directory (if applicable)

## Command Execution

### Process Management

- Subprocess execution with `capture_output=True`
- 300-second timeout for all operations
- Text mode output (decoded strings)
- Check mode enabled (raises on non-zero exit)

### Command Structure

All commands follow the pattern:

```
gh [subcommand] [action] [flags] [arguments]
```

Examples:

- `gh issue list --repo owner/name --state open`
- `gh pr create --title "Title" --body "Body" --head branch`
- `gh repo clone owner/name /path/to/clone`

## Date Handling

### Timestamp Filtering

The `since` parameter uses ISO 8601 format with timezone handling:

- Accepts timestamps with "Z" suffix (UTC)
- Converts to timezone-aware datetime
- Filters issues where `updatedAt > since`
- Filtering performed client-side (not passed to gh CLI)

## Repository Path Management

### Directory Structure

Cloned repositories stored in:

```
{repository_path}/
  {owner}/
    {repo_name}/
```

Example: `/var/gh-worker/repos/octocat/hello-world/`

### Path Resolution

- `_get_repo_path()` constructs path from repository object
- Validates `repository_path` is set
- Returns absolute Path object

## Requirements

### GitHub CLI Integration

**MUST:**

- Use GitHub CLI (`gh`) for all GitHub operations
- Execute commands with 300-second timeout
- Capture both stdout and stderr
- Log all command executions with structured logging
- Retry transient failures (network, rate limiting)
- Raise `RuntimeError` for command failures with stderr context
- Return structured data (JSON parsed to dictionaries)

**SHOULD:**

- Check for existing clones before re-cloning
- Create parent directories for clones
- Include helpful error messages with failed commands
- Use timezone-aware datetime for timestamp comparisons
- Log repository paths for debugging

**MAY:**

- Support alternative base branches for PRs
- Provide custom timeout values
- Cache authentication status
- Support additional issue/PR fields
- Implement batch operations

### Issue Operations

**MUST:**

- Support state filtering (open, closed, all)
- Return up to 1000 issues per list operation
- Include issue number, title, body, state, timestamps, author, labels, and URL
- Parse JSON output from gh CLI
- Handle missing or null fields gracefully

**SHOULD:**

- Filter by update timestamp when `since` provided
- Support GitHub search queries
- Return consistent data structure across list and get operations
- Log issue counts and filter criteria

**MAY:**

- Support pagination for >1000 issues
- Cache issue data for repeated queries
- Support label-based filtering
- Provide issue sorting options

### Pull Request Operations

**MUST:**

- Create PR from head branch to base branch
- Accept title and body parameters
- Execute in repository working directory
- Return PR URL on success
- Raise error if repository not cloned

**SHOULD:**

- Default base branch to "main"
- Validate branch exists before PR creation
- Log PR creation with repository and branch details

**MAY:**

- Support draft PR creation
- Allow label assignment during creation
- Support reviewer assignment
- Provide PR template integration

### Repository Operations

**MUST:**

- Clone repositories to configured path
- Create directory structure (owner/name)
- Skip cloning if repository exists
- Return path to cloned repository
- Raise `ValueError` if repository_path not set

**SHOULD:**

- Create parent directories automatically
- Log clone operations with paths
- Verify clone success before returning
- Handle concurrent clone attempts safely

**MAY:**

- Support shallow clones for performance
- Provide repository update/pull operations
- Clean up failed partial clones
- Support clone depth configuration

### Authentication

**MUST:**

- Check authentication status via gh CLI
- Return boolean result
- Handle auth check failures gracefully

**SHOULD:**

- Cache authentication status for short duration
- Log authentication failures
- Provide helpful error messages for auth issues

**MAY:**

- Support multiple authentication methods
- Validate authentication scopes
- Provide authentication setup guidance
- Support token-based authentication directly

## Usage Examples

### List Open Issues

```python
from gh_worker.github.client import GHClient
from gh_worker.models.repository import Repository

client = GHClient()
repo = Repository(owner="octocat", name="hello-world")

issues = client.list_issues(repo, state="open")
for issue in issues:
    print(f"#{issue['number']}: {issue['title']}")
```

### Get Specific Issue

```python
issue = client.get_issue(repo, issue_number=42)
print(issue['body'])
```

### Clone and Create PR

```python
from pathlib import Path

client = GHClient(repository_path=Path("/var/gh-worker/repos"))

# Clone repository
repo_path = client.clone_repo(repo)

# Create PR
pr_url = client.create_pr(
    repository=repo,
    title="Fix bug in authentication",
    body="This PR fixes the auth issue described in #42",
    head="fix-auth-bug",
    base="main"
)
print(f"Created PR: {pr_url}")
```

### Check Authentication

```python
if not client.check_auth():
    print("Please authenticate: gh auth login")
    exit(1)
```

## Extension Points

The client can be extended to support:

- Additional GitHub CLI commands (releases, workflows, etc.)
- Custom retry strategies per operation
- Alternative Git providers (GitLab, Bitbucket)
- Direct API integration (bypassing gh CLI)
- Webhook handling and event processing
