# ghw Walkthrough Guide

This guide walks you through using **ghw** (gh-worker) from first setup to creating your first pull request. Follow along step-by-step to automate GitHub issue handling with LLM agents.

## What You'll Accomplish

By the end of this walkthrough, you will:

1. Configure ghw for your environment
2. Add a repository and sync its issues
3. Generate an implementation plan using an AI agent
4. Optionally review and approve the plan
5. Implement the plan and create a pull request

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.12+** and **[uv](https://github.com/astral-sh/uv)** installed
- **[GitHub CLI](https://cli.github.com/)** (`gh`) installed and authenticated
- **An LLM agent** (e.g., [Claude Code CLI](https://claude.ai/code) or Cursor Agent)

See the [Installation Guide](installation.md) for setup instructions.

---

## Step 1: Install ghw

Install gh-worker using uv:

```bash
uv tool install https://github.com/tomzxcode/gh-worker.git
```

Verify the installation:

```bash
ghw --help
```

You can use either `ghw` or `gh-worker` (short alias vs full name).

---

## Step 2: Initialize Configuration

Run the interactive setup:

```bash
ghw init
```

This will prompt you for:

| Setting | What it does | Example |
|---------|--------------|---------|
| **Issues path** | Where synced issues and plans are stored | `~/gh-worker/issues` |
| **Repository path** | Where repositories are cloned | `~/gh-worker/repos` |
| **Plan parallelism** | How many plans to generate at once | `1` (start conservative) |
| **Implement parallelism** | How many implementations to run at once | `1` |
| **Use worktree** | Isolated git worktrees per implementation | `true` (recommended) |
| **Auto-push branch** | Push branches after implementation | `false` (review first) |
| **Auto-create PR** | Create PRs after implementation | `false` (review first) |
| **Default agent** | LLM agent to use | `claude-code` |

**Tip:** Start with conservative defaults. You can enable auto-push and auto-create PR once you're comfortable with the workflow.

Configuration is saved to `~/.config/gh-worker/config.yaml`

---

## Step 3: Add a Repository

Add a repository you want to process. For this walkthrough, use a repository you have access to:

```bash
ghw repositories add owner/repo
```

Replace `owner/repo` with your GitHub username and repository name (e.g., `tomzxcode/my-project`).

**Optional:** Add `--clone` to clone the repository immediately. Otherwise, it will be cloned on-demand when you run `plan` or `implement`.

List your tracked repositories:

```bash
ghw repositories list
```

---

## Step 4: Sync Issues

Sync issues from GitHub to local storage:

```bash
ghw issues sync --repo owner/repo
```

This fetches all issues (open and closed) and stores them under your issues path:

```
~/gh-worker/issues/owner/repo/
├── 42/
│   ├── description.md    # Issue content
│   └── .updated-at       # Sync timestamp
├── 43/
│   └── ...
└── .updated-at
```

**Useful sync options:**

```bash
# Sync only issues updated in the last 7 days
ghw issues sync --repo owner/repo --since 7d

# Sync specific issues
ghw issues sync --repo owner/repo --issue-numbers 42 43

# Sync issues assigned to you
ghw issues sync --repo owner/repo --assignee @me
```

---

## Step 5: List Issues

See what you've synced:

```bash
ghw issues list --repo owner/repo
```

You'll see a table with issue numbers, titles, authors, and plan/implementation status.

**Filter the list:**

```bash
# Only issues without plans
ghw issues list --repo owner/repo --plan none

# Only issues ready for implementation
ghw issues list --repo owner/repo --plan approved --implementation none
```

---

## Step 6: Generate a Plan

Generate an implementation plan for one or more issues:

```bash
ghw issues plan --repo owner/repo --issue-numbers 42
```

Replace `42` with an issue number from your list. The LLM agent will:

1. Read the issue description
2. Clone the repository (if needed)
3. Analyze the codebase
4. Generate a detailed implementation plan

**What to expect:** Plan generation can take a few minutes. The agent creates a markdown file in the issue directory:

```
~/gh-worker/issues/owner/repo/42/
├── description.md
├── plan-20250213T143022.md
└── .plan-20250213T143022.yaml
```

**Monitor progress** (in another terminal):

```bash
ghw monitor --repo owner/repo --issue-number 42
```

**Generate plans for multiple issues:**

```bash
ghw issues plan --repo owner/repo --issue-numbers 42 43 44 --parallelism 2
```

---

## Step 7: Review the Plan (Optional)

Before implementing, review the generated plan:

```bash
ghw plans review --repo owner/repo 42
```

This creates a git worktree with the plan symlinked so you can inspect it in context.

**Approve the plan** when ready:

```bash
ghw plans approve --repo owner/repo 42
```

Approved plans are eligible for implementation. You can also edit the plan file directly before approving.

---

## Step 8: Implement

Execute the plan and create a pull request:

```bash
ghw issues implement --repo owner/repo --issue-numbers 42
```

The agent will:

1. Create a git worktree (isolated workspace)
2. Create a branch (e.g., `issue-42-fix-login-bug`)
3. Implement the changes per the plan
4. Commit with a descriptive message

**With full automation** (push + create PR):

```bash
ghw issues implement --repo owner/repo --issue-numbers 42 --push-branch --create-pr
```

**Without automation** (review first):

```bash
ghw issues implement --repo owner/repo --issue-numbers 42
# Then manually push and create PR:
ghw implementations review --repo owner/repo 42
```

---

## Step 9: Review Implementation (If Not Auto-Pushed)

If you didn't use `--push-branch --create-pr`, push the branch and create the PR manually:

```bash
ghw implementations review --repo owner/repo 42
```

This pushes the branch and opens a pull request on GitHub.

---

## Next Steps

### Run the Full Workflow Automatically

Use `ghw work` to run sync → plan → implement in one command:

```bash
# Run once
ghw work --once --repo owner/repo

# Run continuously (checks every 30 minutes)
ghw work --repo owner/repo --frequency 30m
```

### Process Multiple Repositories

```bash
ghw repositories add owner/repo1 owner/repo2
ghw issues sync --all-repos
ghw issues plan --all-repos
ghw issues implement --all-repos
```

### Try Different Agents

```bash
# Use Cursor Agent instead of Claude Code
ghw issues plan --repo owner/repo --agent cursor-agent
ghw issues implement --repo owner/repo --agent cursor-agent

# Use mock agent (for testing, no external deps)
ghw issues plan --repo owner/repo --agent mock
```

### Configure for Automation

Once you're comfortable, enable auto-push and PR creation:

```bash
ghw config implement.push_branch true
ghw config implement.create_pr true
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ghw init` | Initialize configuration |
| `ghw repositories add owner/repo` | Add repository |
| `ghw repositories list` | List tracked repos |
| `ghw issues sync --repo owner/repo` | Sync issues |
| `ghw issues list --repo owner/repo` | List issues |
| `ghw issues plan --repo owner/repo` | Generate plans |
| `ghw plans approve --repo owner/repo 42` | Approve plan |
| `ghw issues implement --repo owner/repo` | Implement plans |
| `ghw implementations review --repo owner/repo 42` | Push & create PR |
| `ghw monitor --repo owner/repo --issue-number 42` | Monitor progress |
| `ghw work --once --repo owner/repo` | Full workflow |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ghw` not found | Ensure `~/.local/bin` is in your PATH (uv installs there) |
| `gh auth status` fails | Run `gh auth login` |
| Agent not found | Install agent CLI (e.g., `claude-code` or `cursor-agent`) |
| No issues synced | Verify repo access with `gh repo view owner/repo` |
| Plan generation fails | Try `--agent mock` to test, or check agent logs |

See [Troubleshooting](troubleshooting.md) for more help.

---

## Further Reading

- [Usage Guide](usage.md) - Complete command reference
- [Configuration](configuration.md) - Configure gh-worker in detail
- [Agents](agents.md) - Understand the agent system
