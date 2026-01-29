"""Claude Code agent implementation."""

import asyncio
import re
import shutil
from collections.abc import AsyncIterator
from typing import Any

import structlog

from gh_worker.agents.base import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    BaseAgent,
)

logger = structlog.get_logger()


class ClaudeCodeAgent(BaseAgent):
    """Agent that uses the claude-code CLI tool."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Claude Code agent.

        Args:
            config: Agent configuration (e.g., model, temperature)
        """
        super().__init__(config)
        self.cli_path = config.get("cli_path", "claude-code") if config else "claude-code"

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "claude-code"

    @property
    def requires_cli(self) -> bool:
        """Return whether this agent requires an external CLI tool."""
        return True

    async def validate_environment(self) -> tuple[bool, str | None]:
        """Validate that claude-code CLI is available.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if shutil.which(self.cli_path) is None:
            return (
                False,
                f"claude-code CLI not found at '{self.cli_path}'. Please install it first.",
            )
        return True, None

    async def plan(
        self, issue_content: str, repository_path: str, issue_number: int
    ) -> AgentResult:
        """Generate an implementation plan for an issue using claude-code.

        Args:
            issue_content: The full issue description
            repository_path: Path to the cloned repository
            issue_number: Issue number

        Returns:
            AgentResult with the generated plan
        """
        logger.info(
            "generating_plan",
            issue_number=issue_number,
            repository_path=repository_path,
        )

        prompt = self._build_plan_prompt(issue_content, issue_number)

        try:
            # Run claude-code in the repository directory
            output = await self._run_claude_code(prompt, repository_path)

            # Extract session ID if present
            session_id = self._extract_session_id(output)

            return AgentResult(
                success=True,
                output=output,
                session_id=session_id,
                metadata={"issue_number": issue_number},
            )
        except Exception as e:
            logger.error("plan_generation_failed", error=str(e), issue_number=issue_number)
            return AgentResult(
                success=False,
                output="",
                error=str(e),
                metadata={"issue_number": issue_number},
            )

    async def implement(
        self,
        issue_content: str,
        plan_content: str,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Implement the plan using claude-code.

        Args:
            issue_content: The full issue description
            plan_content: The generated plan
            repository_path: Path to the cloned repository
            issue_number: Issue number
            branch_name: Branch to create for the implementation

        Yields:
            AgentEvent objects as the implementation progresses
        """
        logger.info(
            "starting_implementation",
            issue_number=issue_number,
            branch_name=branch_name,
            repository_path=repository_path,
        )

        prompt = self._build_implement_prompt(
            issue_content, plan_content, issue_number, branch_name
        )

        try:
            # Stream output from claude-code
            async for event in self._run_claude_code_streaming(prompt, repository_path):
                yield event

            yield AgentEvent(
                type=AgentEventType.COMPLETION,
                content="Implementation completed",
                metadata={"issue_number": issue_number, "branch": branch_name},
            )

        except Exception as e:
            logger.error("implementation_failed", error=str(e), issue_number=issue_number)
            yield AgentEvent(
                type=AgentEventType.FAILURE,
                content=f"Implementation failed: {e}",
                metadata={"issue_number": issue_number, "error": str(e)},
            )

    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Monitor an ongoing claude-code session.

        Args:
            session_id: The session ID to monitor

        Yields:
            AgentEvent objects from the session
        """
        logger.info("monitoring_session", session_id=session_id)

        # Note: claude-code CLI may not support session monitoring directly
        # This would need to be implemented based on the actual CLI capabilities
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content=f"Monitoring session {session_id} (not yet implemented)",
            metadata={"session_id": session_id},
        )

    def _build_plan_prompt(self, issue_content: str, issue_number: int) -> str:
        """Build the prompt for plan generation.

        Args:
            issue_content: The issue description
            issue_number: Issue number

        Returns:
            Formatted prompt string
        """
        return f"""Please create a detailed implementation plan for the following GitHub issue:

Issue #{issue_number}:
{issue_content}

Create a comprehensive plan that includes:
1. Analysis of the requirements
2. Step-by-step implementation approach
3. Files that need to be created or modified
4. Testing strategy
5. Any potential risks or considerations

Write the plan to a file named 'PLAN.md' in the repository root.
"""

    def _build_implement_prompt(
        self, issue_content: str, plan_content: str, issue_number: int, branch_name: str
    ) -> str:
        """Build the prompt for implementation.

        Args:
            issue_content: The issue description
            plan_content: The generated plan
            issue_number: Issue number
            branch_name: Branch name for the implementation

        Returns:
            Formatted prompt string
        """
        return f"""Please implement the following GitHub issue according to the plan provided:

Issue #{issue_number}:
{issue_content}

Implementation Plan:
{plan_content}

Steps:
1. Create and checkout branch: {branch_name}
2. Implement the changes according to the plan
3. Run tests to ensure everything works
4. Commit the changes with a descriptive message
5. Create a pull request

Please proceed with the implementation.
"""

    async def _run_claude_code(self, prompt: str, cwd: str) -> str:
        """Run claude-code CLI and return the full output.

        Args:
            prompt: The prompt to send to claude-code
            cwd: Working directory for the command

        Returns:
            Complete output from claude-code

        Raises:
            RuntimeError: If the command fails
        """
        process = await asyncio.create_subprocess_exec(
            self.cli_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate(input=prompt.encode())

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"claude-code failed: {error_msg}")

        return stdout.decode()

    async def _run_claude_code_streaming(self, prompt: str, cwd: str) -> AsyncIterator[AgentEvent]:
        """Run claude-code CLI and stream output.

        Args:
            prompt: The prompt to send to claude-code
            cwd: Working directory for the command

        Yields:
            AgentEvent objects with output chunks
        """
        process = await asyncio.create_subprocess_exec(
            self.cli_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        # Send the prompt
        if process.stdin:
            process.stdin.write(prompt.encode())
            await process.stdin.drain()
            process.stdin.close()

        # Stream stdout
        if process.stdout:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                content = line.decode().rstrip()
                if content:
                    # Check for special patterns
                    if "error" in content.lower():
                        event_type = AgentEventType.ERROR
                    elif "using tool" in content.lower() or "tool:" in content.lower():
                        event_type = AgentEventType.TOOL_USE
                    else:
                        event_type = AgentEventType.OUTPUT

                    yield AgentEvent(
                        type=event_type,
                        content=content,
                    )

        # Wait for completion
        await process.wait()

        # Check for errors
        if process.returncode != 0:
            stderr_output = ""
            if process.stderr:
                stderr_output = await process.stderr.read()
                stderr_output = stderr_output.decode()

            if stderr_output:
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    content=f"Process failed with exit code {process.returncode}: {stderr_output}",
                )

    def _extract_session_id(self, output: str) -> str | None:
        """Extract session ID from claude-code output.

        Args:
            output: Output from claude-code

        Returns:
            Session ID if found, None otherwise
        """
        # Try to find session ID pattern (adjust based on actual claude-code output)
        patterns = [
            r"session[_\s]id[:\s]+([a-f0-9-]+)",
            r"session[:\s]+([a-f0-9-]+)",
            r"id[:\s]+([a-f0-9-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)

        return None
