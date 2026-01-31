# Error Handling and Retry Logic

## Overview

The error handling system provides robust retry mechanisms for transient failures with exponential backoff. It distinguishes between transient errors (network issues, timeouts, rate limits) and permanent errors (authentication, validation), retrying only when appropriate.

## Architecture

### Retry Decorators

Two decorator variants for sync and async functions, located in [src/gh_worker/utils/retry.py](src/gh_worker/utils/retry.py).

**Synchronous:**

- `@retry()` - Decorator for synchronous functions
- Uses `time.sleep()` for delays

**Asynchronous:**

- `@async_retry()` - Decorator for async functions
- Uses `asyncio.sleep()` for delays

### RetryError Exception

Custom exception raised when all retry attempts exhausted.

**Fields:**

- `message` - Descriptive error message
- `last_exception` - The final exception that caused failure

**Behavior:**

- Wraps the last exception
- Provides context about retry attempts
- Preserves original exception for debugging

## Transient Error Detection

### Error Classification

Function `is_transient_error()` determines if error should be retried.

**Transient Error Types:**

- `subprocess.TimeoutExpired` - Process timeouts
- `ConnectionError` - Network connection issues
- `OSError` - Operating system errors (often network-related)

**Transient Error Indicators (in error message):**

- "timeout"
- "connection"
- "network"
- "temporary"
- "rate limit"
- "too many requests"
- "503" (Service Unavailable)
- "502" (Bad Gateway)
- "504" (Gateway Timeout)

**Classification Logic:**

1. Check exception type
1. Convert exception message to lowercase
1. Search for indicator keywords
1. Return True if any indicator found

### Non-Transient Errors

Examples of errors that should NOT be retried:

- Authentication failures (401, 403)
- Validation errors (400, 422)
- Not found errors (404)
- Syntax errors in code
- Configuration errors
- Permission errors

## Retry Parameters

### Configuration Options

**max_attempts** (default: 3)

- Maximum number of execution attempts
- Includes initial attempt
- Range: 1-N (1 means no retries)

**initial_delay** (default: 1.0 seconds)

- Delay before first retry
- Should be short for quick recoveries
- Typical range: 0.5-5.0 seconds

**backoff_factor** (default: 2.0)

- Multiplier for delay after each retry
- 2.0 means exponential doubling
- Typical range: 1.5-3.0

**max_delay** (default: 60.0 seconds)

- Maximum delay between retries
- Caps exponential growth
- Prevents excessively long waits

**transient_only** (default: True)

- Only retry transient errors
- False means retry all errors
- Recommended: True for production

## Retry Algorithm

### Exponential Backoff

```
Attempt 1: Execute immediately
Attempt 2: Wait initial_delay seconds
Attempt 3: Wait initial_delay * backoff_factor seconds
Attempt N: Wait min(previous_delay * backoff_factor, max_delay) seconds
```

**Example with defaults:**

```
Attempt 1: 0s delay (initial)
Attempt 2: 1s delay
Attempt 3: 2s delay
Total time: ~3 seconds
```

**Example with 5 attempts:**

```
Attempt 1: 0s delay
Attempt 2: 1s delay
Attempt 3: 2s delay
Attempt 4: 4s delay
Attempt 5: 8s delay
Total time: ~15 seconds
```

### Execution Flow

1. Attempt execution
1. If success: Return result
1. If error:
   - Check if transient (if transient_only=True)
   - If non-transient: Raise immediately
   - If out of attempts: Break and raise RetryError
   - Log retry attempt
   - Sleep for delay duration
   - Calculate next delay (exponential backoff)
   - Repeat from step 1
1. If all attempts exhausted: Raise RetryError

## Logging

### Log Levels and Events

**Warning Level:**

- Retry attempts (before retry)
- Includes attempt number, delay, error

**Error Level:**

- Non-transient errors (not retried)
- Max attempts reached
- Final failure

**Structured Fields:**

- `function` - Function name being retried
- `attempt` - Current attempt number
- `max_attempts` - Total attempts configured
- `delay` - Delay before next retry
- `error` - Error message
- `error_type` - Exception class name
- `exc_info` - Full traceback (for debugging)

## Requirements

### Retry Logic

**MUST:**

- Support configurable max_attempts, delays, and backoff
- Implement exponential backoff with max_delay cap
- Distinguish transient from permanent errors (if transient_only=True)
- Raise RetryError after exhausting attempts
- Log all retry attempts with structured data
- Preserve original exception in RetryError
- Support both sync and async functions

**SHOULD:**

- Default to sensible retry parameters (3 attempts, 1s delay, 2x backoff)
- Log at appropriate levels (warning for retries, error for failures)
- Include function name and error type in logs
- Provide full traceback for debugging
- Use decorator pattern for clean application

**MAY:**

- Support custom transient error classifiers
- Implement jitter for retry delays
- Provide per-exception-type retry strategies
- Support retry callbacks or hooks
- Track retry statistics

### Error Classification

**MUST:**

- Identify common transient error types
- Check error messages for transient indicators
- Support subprocess, network, and OS errors
- Handle HTTP status codes (502, 503, 504)
- Recognize rate limiting errors

**SHOULD:**

- Use case-insensitive message matching
- Support multiple indicator keywords
- Return boolean result
- Handle errors without messages gracefully

**MAY:**

- Support custom error classifiers
- Provide error categorization (network, auth, validation)
- Learn from error patterns
- Support configurable indicator lists

### Exponential Backoff

**MUST:**

- Start with initial_delay
- Multiply by backoff_factor after each retry
- Cap delay at max_delay
- Use actual sleep/delay functions
- Calculate delays before sleeping

**SHOULD:**

- Use reasonable default values
- Support fractional delays (sub-second)
- Prevent negative or zero delays
- Log actual delay used

**MAY:**

- Implement jittered backoff (add randomness)
- Support alternative backoff strategies (linear, fibonacci)
- Provide backoff visualization or estimation
- Support adaptive backoff based on error type

### Exception Handling

**MUST:**

- Catch all exceptions during execution
- Re-raise non-transient errors immediately (if transient_only=True)
- Wrap final exception in RetryError
- Preserve stack traces
- Include descriptive error messages

**SHOULD:**

- Log exception details before retrying
- Include attempt number in error context
- Provide clear messages about retry exhaustion
- Use exception chaining (raise ... from ...)

**MAY:**

- Support exception translation
- Provide exception aggregation for multiple failures
- Implement exception callbacks
- Support exception filtering

### Decorator Implementation

**MUST:**

- Use functools.wraps to preserve function metadata
- Support both positional and keyword arguments
- Work with sync and async functions separately
- Return same type as decorated function
- Support type hints and generics

**SHOULD:**

- Validate decorator parameters
- Provide clear error messages for misuse
- Support nested decorators
- Minimize performance overhead

**MAY:**

- Support class methods and static methods
- Provide decorator composition helpers
- Support conditional retry (based on arguments)
- Implement decorator caching

## Usage Examples

### Basic Usage

```python
from gh_worker.utils.retry import retry

@retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
def fetch_data_from_api():
    response = requests.get("https://api.example.com/data")
    response.raise_for_status()
    return response.json()

# Will retry on connection errors, timeouts, rate limits
data = fetch_data_from_api()
```

### Async Usage

```python
from gh_worker.utils.retry import async_retry

@async_retry(max_attempts=5, initial_delay=2.0)
async def query_database():
    async with database.connection() as conn:
        return await conn.fetch("SELECT * FROM items")

# Async retry with exponential backoff
items = await query_database()
```

### Custom Parameters

```python
@retry(
    max_attempts=5,
    initial_delay=0.5,
    backoff_factor=3.0,
    max_delay=30.0,
    transient_only=True
)
def unreliable_operation():
    # Your code here
    pass
```

### Retry All Errors

```python
# Retry even non-transient errors (use with caution)
@retry(max_attempts=3, transient_only=False)
def operation_that_needs_many_retries():
    # This will retry ALL exceptions
    pass
```

### Error Handling

```python
from gh_worker.utils.retry import retry, RetryError

@retry(max_attempts=3)
def flaky_api_call():
    # Call external API
    pass

try:
    result = flaky_api_call()
except RetryError as e:
    print(f"Failed after all retries: {e}")
    print(f"Last exception: {e.last_exception}")
    # Handle permanent failure
```

### GitHub CLI Example

```python
@retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
def _run_command(self, args: list[str]) -> str:
    """Run gh CLI command with automatic retry."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        check=True,
        timeout=300
    )
    return result.stdout
```

## Integration Points

### GitHub Client

- All GitHub CLI commands use @retry decorator
- Handles network failures and rate limiting
- 3 attempts with exponential backoff

### Agent Operations

- Plan generation may use retry for LLM API calls
- Implementation streaming handles transient failures
- Session monitoring recovers from temporary disconnects

### Storage Operations

- File I/O may retry on transient OS errors
- Network storage backends benefit from retry logic

## Extension Points

The error handling system can be extended to support:

- Circuit breaker pattern (stop after repeated failures)
- Bulkhead pattern (isolate failures)
- Fallback strategies (alternative implementations)
- Health checks (pre-retry validation)
- Metrics and monitoring (retry rates, failure types)
- Distributed tracing (retry spans)
- Per-service retry policies
- Custom backoff strategies (jitter, fibonacci, polynomial)
