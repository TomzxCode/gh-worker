# Parallel Execution

## Overview

The parallel execution system provides controlled concurrency for processing multiple items (issues, plans, repositories) simultaneously. It uses asyncio with semaphore-based limiting to prevent resource exhaustion while maximizing throughput for I/O-bound operations.

## Architecture

### ParallelExecutor Class

Generic executor for parallel task execution, located in [src/gh_worker/executor/parallel.py](src/gh_worker/executor/parallel.py).

**Initialization:**

- `max_workers` - Maximum number of concurrent tasks (default: 1)

**Methods:**

- `execute()` - Run tasks in parallel with concurrency limiting
- `_execute_single()` - Execute individual task with semaphore control

**Type Parameters:**

- `T` - Type of input items
- `R` - Type of task results

### TaskResult

Result container for individual task execution.

**Fields:**

- `item: T` - The input item that was processed
- `success: bool` - Whether task completed successfully
- `result: R | None` - Task result (if successful)
- `error: str | None` - Error message (if failed)

## Concurrency Control

### Semaphore Limiting

Uses asyncio.Semaphore to control concurrent execution:

- Initialized with `max_workers` count
- Each task acquires semaphore before execution
- Semaphore released after task completes (success or failure)
- Blocks additional tasks when limit reached

### Execution Flow

1. Create task list for all items
1. Launch all tasks with `asyncio.gather()`
1. Each task acquires semaphore
1. Execute task function
1. Release semaphore
1. Return TaskResult
1. Gather all results
1. Return complete result list

### Worker Configuration

- Configurable via `max_workers` parameter
- Defaults to 1 (sequential execution)
- Typical values: 1-10 depending on resource constraints
- Higher values increase throughput but consume more resources

## Task Execution

### Task Function

Required signature: `async (T) -> R`

- Takes single item of type T
- Returns result of type R
- Can be any async callable

### Error Isolation

- Exceptions caught per task
- Failed tasks don't affect other tasks
- Errors converted to TaskResult with success=False
- Error message and stack trace logged

### Result Collection

- All tasks collected via `asyncio.gather()`
- Returns list of TaskResult objects
- Order matches input order (deterministic)
- Includes both successes and failures

## Logging

### Execution Lifecycle

Logs at key points:

- Start: Total items, max workers
- Per task: Start and completion (debug level)
- Completion: Total, successes, failures

### Structured Fields

- `task_name` - Descriptive name for logging
- `total_items` - Number of items to process
- `max_workers` - Concurrency limit
- `total` - Total tasks completed
- `successes` - Number of successful tasks
- `failures` - Number of failed tasks
- `item` - Item being processed (converted to string)
- `error` - Error message for failures
- `exc_info` - Full exception traceback

## Requirements

### Concurrency Management

**MUST:**

- Use asyncio.Semaphore for concurrency limiting
- Acquire semaphore before task execution
- Release semaphore after task completes (success or failure)
- Support configurable max_workers parameter
- Launch all tasks with asyncio.gather()
- Return results in input order

**SHOULD:**

- Default to sequential execution (max_workers=1)
- Log execution start with item count and worker limit
- Log completion with success/failure counts
- Use context manager for semaphore (async with)

**MAY:**

- Support dynamic worker adjustment
- Implement adaptive concurrency based on performance
- Provide progress callbacks or hooks
- Support task prioritization

### Error Handling

**MUST:**

- Catch all exceptions per task
- Convert exceptions to TaskResult with success=False
- Include error message in TaskResult
- Log task failures with full context
- Continue processing other tasks on failure
- Return TaskResult for all items (success or failure)

**SHOULD:**

- Log exception traceback for debugging
- Include item identifier in error logs
- Use structured logging for machine parsing
- Log at appropriate levels (debug for start, error for failures)

**MAY:**

- Implement retry logic per task
- Classify errors by type or severity
- Support error aggregation or summaries
- Provide error hooks or callbacks

### Task Execution

**MUST:**

- Accept async callable as task function
- Pass item to task function
- Await task function result
- Return TaskResult with item and result
- Handle both success and failure cases

**SHOULD:**

- Support generic type parameters (T, R)
- Validate task function signature
- Log task start and completion
- Use descriptive task names for logging

**MAY:**

- Support sync task functions (wrap with asyncio)
- Provide task timeout functionality
- Support task cancellation
- Implement task dependency handling

### Result Handling

**MUST:**

- Return list of TaskResult objects
- Preserve input order in results
- Include all items in results (no filtering)
- Populate success/result for successful tasks
- Populate success/error for failed tasks

**SHOULD:**

- Provide summary statistics (success/failure counts)
- Log result summary after completion
- Make results easy to filter or process

**MAY:**

- Support result streaming (yield as completed)
- Provide result aggregation utilities
- Support result callbacks
- Implement result caching

### Logging and Monitoring

**MUST:**

- Log execution start and completion
- Include task counts in logs
- Use structured logging with consistent fields
- Log errors with exception info

**SHOULD:**

- Log at appropriate levels (info, debug, error)
- Include task name in all log entries
- Provide progress visibility for long operations
- Log individual task start/completion at debug level

**MAY:**

- Support custom log formatters
- Provide execution metrics (timing, throughput)
- Implement monitoring hooks
- Support distributed tracing

## Usage Examples

### Basic Parallel Execution

```python
from gh_worker.executor.parallel import ParallelExecutor

executor = ParallelExecutor(max_workers=3)

async def process_issue(issue_number: int) -> str:
    # Simulate some async work
    await asyncio.sleep(1)
    return f"Processed issue {issue_number}"

issues = [1, 2, 3, 4, 5]
results = await executor.execute(
    items=issues,
    task_func=process_issue,
    task_name="process_issues"
)

for result in results:
    if result.success:
        print(f"Success: {result.result}")
    else:
        print(f"Failed: {result.error}")
```

### Plan Generation

```python
async def generate_plan(issue: Issue) -> PlanMetadata:
    agent = get_agent()
    result = await agent.plan(issue.content, repo_path, issue.number)
    return save_plan(result)

executor = ParallelExecutor(max_workers=config.plan.parallelism)
results = await executor.execute(
    items=issues,
    task_func=generate_plan,
    task_name="generate_plans"
)
```

### Result Processing

```python
results = await executor.execute(items, task_func, "my_task")

# Count successes and failures
success_count = sum(1 for r in results if r.success)
failure_count = len(results) - success_count

print(f"Completed: {success_count} succeeded, {failure_count} failed")

# Process successful results
successful_items = [r.item for r in results if r.success]
successful_results = [r.result for r in results if r.success]

# Log failures
for result in results:
    if not result.success:
        print(f"Failed to process {result.item}: {result.error}")
```

### Sequential Execution

```python
# max_workers=1 for sequential processing
executor = ParallelExecutor(max_workers=1)
results = await executor.execute(items, task_func, "sequential_task")
```

### Error Handling

```python
async def risky_task(item: int) -> str:
    if item % 2 == 0:
        raise ValueError(f"Item {item} is even!")
    return f"Processed {item}"

executor = ParallelExecutor(max_workers=3)
results = await executor.execute([1, 2, 3, 4], risky_task, "risky_task")

# Results will include both successes and failures
for result in results:
    print(f"Item {result.item}: {'OK' if result.success else result.error}")
```

## Performance Considerations

### Optimal Worker Count

- I/O-bound tasks: Higher concurrency (5-10 workers)
- CPU-bound tasks: Lower concurrency (1-2 workers)
- Rate-limited APIs: Match rate limit (e.g., 1-3 workers)
- Resource constraints: Consider memory and connections

### Resource Usage

- Each worker may hold open connections
- Memory usage scales with worker count
- Semaphore overhead minimal (asyncio built-in)
- Task overhead depends on task function

### Throughput

- Linear improvement up to resource limits
- Diminishing returns beyond optimal worker count
- Network latency dominates for I/O tasks
- Contention increases with worker count

## Extension Points

The parallel execution system can be extended to support:

- Task queues with prioritization
- Dynamic worker scaling
- Task dependencies or ordering constraints
- Distributed execution across machines
- Progress reporting and monitoring
- Task timeouts and cancellation
- Resource-aware scheduling
- Batch processing with checkpointing
