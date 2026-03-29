# gh-worker CLI User State Diagram

This document describes the transitions a user goes through while using the gh-worker CLI, including both the setup workflow and the issue lifecycle.

## 1. Setup & Configuration Flow

```mermaid
flowchart LR
    A[Uninitialized] -->|init| B[Configured]
    B -->|repositories add| C[Repos Tracked]
    C -->|issues sync| D[Issues Synced]
    D -->|issues list| E[Ready to Plan]
    B <-->|config| F[Any State]
```

## 2. Issue Lifecycle (Plan & Implementation States)

Each synced issue progresses through plan and implementation states. The user invokes commands that trigger transitions.

### Plan States

| State | Description | User Action to Enter | Next State |
|-------|-------------|----------------------|------------|
| **none** | No plan exists | (initial after sync) | being generated |
| **being generated** | LLM is creating plan | `issues plan` or `work` | waiting for local review |
| **waiting for local review** | Plan file exists, needs approval | (automatic when plan completes) | approved |
| **approved** | User approved plan | `plans approve` | — |

### Implementation States

| State | Description | User Action to Enter | Next State |
|-------|-------------|----------------------|------------|
| **none** | No implementation | (initial) | being generated |
| **being generated** | LLM is implementing | `issues implement` or `work` | waiting for local review / PR opened / failed |
| **waiting for local review** | Code done locally, no PR yet | (automatic when implementation completes without push) | PR opened |
| **review in progress** | LLM is reviewing the implementation | `issues review` | reviewed / review failed |
| **reviewed** | Review completed | (automatic when review completes) | PR opened |
| **PR opened** | Branch pushed, PR created | `implementations review` or auto from implement | merged |
| **merged** | PR merged to main | (external: merge on GitHub) | — |
| **failed** | Implementation failed | (automatic on error) | being generated |
| **review failed** | Review failed | (automatic on error) | — |

### State Diagram (Issue Lifecycle)

```mermaid
flowchart TD
    subgraph PLAN["PLAN PHASE"]
        P1[none] -->|issues plan / work| P2[being generated]
        P2 -->|plan completes| P3[waiting for local review]
        P3 -->|plans approve| P4[approved]
        P4 -->|plans unapprove| P3
    end

    subgraph IMPL["IMPLEMENTATION PHASE"]
        I1[none] -->|issues implement / work| I2[being generated]
        I2 -->|completes, no push| I3[waiting for local review]
        I2 -->|implementation fails| I6[failed]
        I6 -->|issues implement --force| I2
        I3 -->|issues review| I4[review in progress]
        I4 -->|review completes| I5[reviewed]
        I4 -->|review fails| I7[review failed]
        I5 -->|implementations review| I8[PR opened]
        I2 -->|completes with push + PR| I8
        I8 -->|merge on GitHub| I9[merged]
    end

    P4 --> I1
```

## 3. User Command Flow (Typical Workflow)

```mermaid
flowchart TD
    subgraph Setup["First-time setup"]
        direction TD
        S1[init] --> S2[config] --> S3[repositories add] --> S4["config issues-path / repository-path"]
    end

    subgraph Manual["Per-issue workflow (manual)"]
        direction TD
        M1[issues sync] --> M2[issues list] --> M3[issues plan] --> M4[plans approve] --> M5[issues implement]
        M5 -->|no push/PR| M6[issues review]
        M6 --> M7[implementations review] --> M8[PR opened on GitHub]
        M5 -->|auto push/PR| M8
        M8 --> M9[merge on GitHub] --> M10[merged]
    end

    subgraph Auto["Automated workflow"]
        direction TD
        A1[work] -->|"sync → plan → implement loop"| A1
    end
```

## 4. Monitor & Work Commands

| Command | Purpose | User State |
|---------|---------|------------|
| `monitor <repo> <issue>` | Watch LLM progress during plan or implement | User is waiting; plan/implementation **being generated** |
| `work [--once]` | Run full cycle (sync → plan → implement) | Automated; may run continuously |

## 5. Summary: All CLI Commands by Category

| Category | Commands | Transitions |
|----------|----------|-------------|
| **Setup** | `init`, `config` | Uninitialized → Configured |
| **Repos** | `repositories add`, `list`, `remove` | Configured → Repos Tracked |
| **Sync** | `issues sync` | Repos → Issues Synced |
| **Inspect** | `issues list` | View current plan/implementation state |
| **Plan** | `issues plan` | none → being generated → waiting for review |
| **Review** | `plans review`, `plans approve`, `plans unapprove` | waiting for review ↔ approved |
| **Implement** | `issues implement` | approved → being generated → waiting for review / PR opened / failed |
| **Review Impl** | `issues review`, `implementations review` | waiting for review → reviewed → PR opened |
| **Automate** | `work` | Runs sync → plan → implement cycle |
| **Monitor** | `monitor` | Observe being generated |
