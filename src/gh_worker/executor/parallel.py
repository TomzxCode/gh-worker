"""Parallel executor for running tasks with concurrency limiting."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class TaskResult[T, R]:
    """Result of a parallel task execution."""

    item: T
    success: bool
    result: R | None = None
    error: str | None = None


class ParallelExecutor:
    """Executor for running tasks in parallel with concurrency limiting."""

    def __init__(self, max_workers: int = 1):
        """Initialize parallel executor.

        Args:
            max_workers: Maximum number of concurrent tasks
        """
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)

    async def execute(
        self,
        items: list[T],
        task_func: Callable[[T], Awaitable[R]],
        task_name: str = "task",
    ) -> list[TaskResult[T, R]]:
        """Execute tasks in parallel with concurrency limiting.

        Args:
            items: List of items to process
            task_func: Async function to call for each item
            task_name: Name for logging purposes

        Returns:
            List of TaskResult objects (one per item)
        """
        if not items:
            logger.info("no_items_to_execute", task_name=task_name)
            return []

        logger.info(
            "starting_parallel_execution",
            task_name=task_name,
            total_items=len(items),
            max_workers=self.max_workers,
        )

        tasks = [self._execute_single(item, task_func, task_name) for item in items]
        results = await asyncio.gather(*tasks)

        successes = sum(1 for r in results if r.success)
        failures = len(results) - successes

        logger.info(
            "completed_parallel_execution",
            task_name=task_name,
            total=len(results),
            successes=successes,
            failures=failures,
        )

        return results

    async def _execute_single(
        self, item: T, task_func: Callable[[T], Awaitable[R]], task_name: str
    ) -> TaskResult[T, R]:
        """Execute a single task with semaphore limiting.

        Args:
            item: Item to process
            task_func: Async function to call
            task_name: Name for logging purposes

        Returns:
            TaskResult for this item
        """
        async with self._semaphore:
            try:
                logger.debug("starting_task", task_name=task_name, item=str(item))
                result = await task_func(item)
                logger.debug("task_succeeded", task_name=task_name, item=str(item))
                return TaskResult(item=item, success=True, result=result)
            except Exception as e:
                logger.error(
                    "task_failed",
                    task_name=task_name,
                    item=str(item),
                    error=str(e),
                    exc_info=True,
                )
                return TaskResult(item=item, success=False, error=str(e))
