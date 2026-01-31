# Troubleshooting

Common issues and their solutions when using gh-worker.

## Installation Issues

### Command Not Found: ghw

**Symptom**: Running `ghw` returns "command not found"

**Solution**:

1. Verify installation:

```bash
uv pip list | grep gh-worker
```

2. Ensure Python's script directory is in PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Reload shell
source ~/.bashrc  # or source ~/.zshrc
```

3. Reinstall if needed:

```bash
# Install with uv
uv tool install https://github.com/tomzxcode/gh-worker.git
```

### GitHub CLI Not Authenticated

**Symptom**: Errors mentioning "authentication required" or "not logged in"

**Solution**:

```bash
# Authenticate with GitHub
gh auth login

# Verify authentication
gh auth status

# If needed, refresh authentication
gh auth refresh
```

### Claude Code CLI Not Found

**Symptom**: "claude-code: command not found" or agent validation errors

**Solution**:

1. Install Claude Code CLI from [claude.ai/code](https://claude.ai/code)

1. Verify installation:

```bash
claude-code --version
```

3. If installed but not in PATH, specify the full path:

```bash
ghw config agent.claude_code_path /full/path/to/claude-code
```

4. Or use a different agent:

```bash
ghw config agent.default opencode
```

## Configuration Issues

### Configuration File Not Found

**Symptom**: "Configuration file not found" errors

**Solution**:

```bash
# Create config directory
mkdir -p ~/.config/gh-worker

# Initialize configuration
ghw config issues-path ~/gh-worker/issues
ghw config repository-path ~/gh-worker/repos
```

### Invalid Configuration Values

**Symptom**: Validation errors when setting config values

**Solution**:

```bash
# Check current value
ghw config plan.parallelism

# Set valid value (>= 1)
ghw config plan.parallelism 1

# For paths, use absolute paths or ~
ghw config issues-path ~/gh-worker/issues  # Good
ghw config issues-path ./issues           # May cause issues
```

### Permission Denied on Config Directory

**Symptom**: Can't write to `~/.config/gh-worker`

**Solution**:

```bash
# Fix permissions
mkdir -p ~/.config/gh-worker
chmod 755 ~/.config/gh-worker

# Or use a custom config path
ghw --config-path /writable/path/config.yaml sync --repo owner/repo
```

## Sync Issues

### No Issues Synced

**Symptom**: `ghw sync` completes but no issues are stored

**Causes and Solutions**:

1. **No open issues in repository**:

```bash
# Check repository has issues
gh issue list --repo owner/repo
```

2. **Wrong repository name**:

```bash
# Verify repository exists and you have access
gh repo view owner/repo
```

3. **Time filter too restrictive**:

```bash
# Try without --since
ghw sync --repo owner/repo

# Or use longer timeframe
ghw sync --repo owner/repo --since 30d
```

4. **Search query excludes all issues**:

```bash
# Verify search query
gh issue list --repo owner/repo --search "your-search-query"
```

### Rate Limiting

**Symptom**: "API rate limit exceeded" errors

**Solutions**:

1. Reduce sync frequency:

```bash
ghw config sync.frequency 1h  # Sync less often
```

2. Reduce parallelism:

```bash
ghw config plan.parallelism 1
```

3. Use time-based sync:

```bash
ghw sync --repo owner/repo --since 1d  # Only recent issues
```

4. Check rate limit status:

```bash
gh api rate_limit
```

### Repository Clone Failed

**Symptom**: Errors during repository cloning

**Solutions**:

1. Verify access:

```bash
gh repo view owner/repo
```

2. Check disk space:

```bash
df -h ~/gh-worker/repos
```

3. Remove and re-clone:

```bash
rm -rf ~/gh-worker/repos/owner/repo
ghw add owner/repo
```

## Plan Generation Issues

### Plans Not Generated

**Symptom**: `ghw plan` completes but no plans are created

**Causes and Solutions**:

1. **No issues to plan**:

```bash
# Verify issues exist
ls ~/gh-worker/issues/owner/repo/
```

2. **Plans already exist**:

```bash
# Check for existing plans
find ~/gh-worker/issues/owner/repo -name "plan-*.md"

# Force regenerate by deleting old plans
rm ~/gh-worker/issues/owner/repo/42/plan-*.md
ghw plan --repo owner/repo --issue-numbers 42
```

3. **Agent not available**:

```bash
# Verify agent
claude-code --version

# Or switch agent
ghw config agent.default claude-code
```

### Plan Generation Hangs

**Symptom**: Plan generation starts but never completes

**Solutions**:

1. Check agent is responsive:

```bash
claude-code --version
```

2. Check network connectivity (for cloud agents)

1. Monitor logs:

```bash
ghw --log-level DEBUG plan --repo owner/repo
```

4. Reduce parallelism:

```bash
ghw plan --repo owner/repo --parallelism 1
```

### Plan Quality Issues

**Symptom**: Generated plans are incomplete or incorrect

**Solutions**:

1. Ensure issue descriptions are detailed:

   - Include clear problem statement
   - Provide reproduction steps
   - Add context about the codebase

1. Regenerate with more context:

```bash
# Delete old plan
rm ~/gh-worker/issues/owner/repo/42/plan-*.md

# Add more context to issue description
gh issue edit 42 --body "..." --repo owner/repo

# Resync and replan
ghw sync --repo owner/repo --issue-numbers 42
ghw plan --repo owner/repo --issue-numbers 42
```

## Implementation Issues

### Implementation Fails Immediately

**Symptom**: `ghw implement` fails right after starting

**Causes and Solutions**:

1. **No plan exists**:

```bash
# Generate plan first
ghw plan --repo owner/repo --issue-numbers 42
```

2. **Repository not clean**:

```bash
cd ~/gh-worker/repos/owner/repo
git status
git stash  # Or commit changes
```

3. **Agent not available**:

```bash
claude-code --version
```

### Implementation Hangs

**Symptom**: Implementation starts but never completes

**Solutions**:

1. Monitor in another terminal:

```bash
ghw monitor --repo owner/repo --issue-number 42
```

2. Check agent process:

```bash
ps aux | grep claude-code
```

3. Check repository state:

```bash
cd ~/gh-worker/repos/owner/repo
git status
git log --oneline -5
```

4. Increase timeout (if configurable):

```bash
# Implementation-specific timeout configuration
```

### Tests Fail During Implementation

**Symptom**: Implementation fails because tests don't pass

**Solutions**:

1. Review test output in agent logs

1. Run tests manually:

```bash
cd ~/gh-worker/repos/owner/repo
pytest  # Or your test command
```

3. Fix test issues and retry:

```bash
# Fix tests
ghw implement --repo owner/repo --issue-numbers 42
```

### Branch Already Exists

**Symptom**: "Branch already exists" error

**Solutions**:

```bash
cd ~/gh-worker/repos/owner/repo

# Option 1: Delete existing branch
git branch -D issue-42-branch-name
git push origin --delete issue-42-branch-name

# Option 2: Check out and update existing branch
git checkout issue-42-branch-name
```

### Pull Request Creation Failed

**Symptom**: Implementation succeeds but PR creation fails

**Solutions**:

1. Verify GitHub CLI permissions:

```bash
gh auth status
```

2. Check repository permissions:

```bash
gh repo view owner/repo
```

3. Create PR manually:

```bash
cd ~/gh-worker/repos/owner/repo
gh pr create --title "Fix issue #42" --body "..."
```

## Monitoring Issues

### Monitor Shows No Output

**Symptom**: `ghw monitor` runs but shows nothing

**Causes and Solutions**:

1. **Wrong issue number**:

```bash
# Verify issue is being implemented
ls ~/gh-worker/issues/owner/repo/42/
```

2. **Session not found**:

```bash
# Implementation may not have started
ghw implement --repo owner/repo --issue-numbers 42
```

3. **Session completed**:
   - Monitor can't show output for completed sessions
   - Check implementation results instead

## Work Command Issues

### Work Command Stops After One Iteration

**Symptom**: `ghw work` runs once then exits

**Solution**:

Remove `--once` flag for continuous mode:

```bash
# This runs once and exits
ghw work --once --repos owner/repo

# This runs continuously
ghw work --repos owner/repo
```

### Work Command Frequency Not Respected

**Symptom**: Work command runs more/less frequently than configured

**Solutions**:

1. Check configuration:

```bash
ghw config sync.frequency
```

2. Specify frequency explicitly:

```bash
ghw work --repos owner/repo --frequency 30m
```

3. Monitor logs to verify timing:

```bash
ghw --log-level DEBUG work --repos owner/repo
```

## Performance Issues

### Slow Execution

**Causes and Solutions**:

1. **Low parallelism**:

```bash
ghw config plan.parallelism 3
ghw config implement.parallelism 2
```

2. **Network latency**:

   - Check internet connection
   - Use closer/faster agent endpoints

1. **Large repository**:

   - Repository cloning and operations take longer
   - Consider shallow clones (if implemented)

1. **Resource constraints**:

```bash
# Check system resources
top
df -h
```

### High Memory Usage

**Solutions**:

1. Reduce parallelism:

```bash
ghw config plan.parallelism 1
ghw config implement.parallelism 1
```

2. Process issues in batches:

```bash
# Instead of all at once
ghw plan --repo owner/repo --issue-numbers 1 2 3
ghw plan --repo owner/repo --issue-numbers 4 5 6
```

## File System Issues

### Disk Space Full

**Symptom**: "No space left on device" errors

**Solutions**:

1. Check disk space:

```bash
df -h ~/gh-worker
```

2. Clean old plans:

```bash
find ~/gh-worker/issues -name "plan-*.md" -mtime +30 -delete
```

3. Remove old repositories:

```bash
rm -rf ~/gh-worker/repos/unused-repo
```

4. Move to larger disk:

```bash
ghw config issues-path /larger-disk/gh-worker/issues
ghw config repository-path /larger-disk/gh-worker/repos
```

### Permission Denied

**Symptom**: Can't read/write files in gh-worker directories

**Solutions**:

```bash
# Fix ownership
sudo chown -R $USER:$USER ~/gh-worker

# Fix permissions
chmod -R u+rwX ~/gh-worker
```

## Logging and Debugging

### Enable Debug Logging

For detailed troubleshooting:

```bash
ghw --log-level DEBUG <command>
```

### View Recent Logs

```bash
# View structured logs
ghw --log-level DEBUG sync --repo owner/repo 2>&1 | less
```

### Check Agent Logs

Agent-specific logs may be in different locations:

```bash
# Claude Code (example)
# Check agent documentation for log location
```

## Getting Help

If you can't resolve your issue:

1. **Check existing issues**: [GitHub Issues](https://github.com/tomzxcode/gh-worker/issues)

1. **Create a new issue** with:

   - gh-worker version
   - Python version
   - Operating system
   - Complete error message
   - Steps to reproduce
   - Debug logs

1. **Include diagnostics**:

```bash
# System info
python --version
ghw --version
gh --version
claude-code --version  # If using Claude Code

# Configuration
ghw config issues-path
ghw config repository-path
ghw config agent.default
```

## Next Steps

- [Usage Guide](usage.md) - Command usage and workflows
- [Configuration](configuration.md) - Configuration options
- [Architecture](architecture.md) - Technical deep dive
- [Agents](agents.md) - Agent system details
