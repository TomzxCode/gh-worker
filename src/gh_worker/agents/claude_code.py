"""Claude Code agent implementation."""

import asyncio
import json
import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
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
    """Agent that uses the claude CLI tool."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Claude Code agent.

        Args:
            config: Agent configuration (e.g., model, temperature)
        """
        super().__init__(config)
        logger.debug("initializing_claude_code_agent", config=config)
        # Support both cli_path and claude_code_path config keys
        if config:
            cli_path = config.get("cli_path") or config.get("claude_code_path")
        else:
            cli_path = None

        # Default to claude (without file reference)
        if not cli_path:
            cli_path = "claude"
            logger.debug("using_default_cli_path", cli_path=cli_path)

        self.cli_path = cli_path
        logger.debug("cli_path_set", cli_path=self.cli_path)
        # Parse the command: if it contains @, split into command and args
        self._parse_cli_command()

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "claude-code"

    def _parse_cli_command(self):
        """Parse the CLI command string into executable and arguments.

        Handles formats like:
        - "claude-code" -> ["claude-code"]
        - "claude@path/to/file.py" -> ["claude", "@path/to/file.py"]
        """
        logger.debug("parsing_cli_command", cli_path=self.cli_path)
        if "@" in self.cli_path:
            parts = self.cli_path.split("@", 1)
            self.cli_executable = parts[0]
            self.cli_args = [f"@{parts[1]}"]
            logger.debug(
                "cli_command_parsed",
                executable=self.cli_executable,
                args=self.cli_args,
            )
        else:
            self.cli_executable = self.cli_path
            self.cli_args = []
            logger.debug(
                "cli_command_parsed",
                executable=self.cli_executable,
                args=self.cli_args,
            )

    @property
    def requires_cli(self) -> bool:
        """Return whether this agent requires an external CLI tool."""
        return True

    async def validate_environment(self) -> tuple[bool, str | None]:
        """Validate that claude CLI is available.

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug("validating_environment", executable=self.cli_executable)
        cli_location = shutil.which(self.cli_executable)
        logger.debug("cli_location_check", executable=self.cli_executable, found=cli_location)
        if cli_location is None:
            error_msg = f"claude CLI not found at '{self.cli_executable}'. Please install it first."
            logger.debug("environment_validation_failed", error=error_msg)
            return (False, error_msg)
        logger.debug("environment_validation_success", cli_path=cli_location)
        return True, None

    async def plan(
        self, issue_content: str, repository_path: str
    ) -> AgentResult:
        """Generate an implementation plan for an issue using claude.

        Args:
            issue_content: The full issue description
            repository_path: Path to the cloned repository

        Returns:
            AgentResult with the generated plan
        """
        logger.info(
            "generating_plan",
            repository_path=repository_path,
        )

        prompt = self._build_plan_prompt(issue_content)
        logger.debug(
            "plan_prompt_built",
            prompt_length=len(prompt),
        )

        try:
            # Run claude in the repository directory with streaming
            logger.debug("running_claude_code_for_plan")
            output = None
            session_id = None
            async for event in self._run_claude_code_streaming(prompt, repository_path):
                # Extract result from RESULT event
                if event.type == AgentEventType.RESULT:
                    output = event.content
                    logger.debug(
                        "result_extracted",
                        output_length=len(output) if output else 0,
                    )

                # Extract session_id from event metadata if present
                if event.metadata and "session_id" in event.metadata:
                    session_id = event.metadata["session_id"]
                    logger.debug(
                        "session_id_found_in_event",
                        session_id=session_id,
                    )

            if output is None:
                logger.warning("no_result_event_found")
                return AgentResult(
                    success=False,
                    output="",
                    error="No result event found in agent output",
                )

            logger.debug(
                "claude_code_output_received",
                output_length=len(output),
            )

            # Extract session ID from output if not found in events
            if not session_id:
                session_id = self._extract_session_id(output)
                logger.debug(
                    "session_id_extracted_from_output",
                    session_id=session_id,
                )

            return AgentResult(
                success=True,
                output=output,
                session_id=session_id,
            )
        except Exception as e:
            logger.error("plan_generation_failed", error=str(e))
            logger.debug("plan_generation_exception", exc_info=True)
            return AgentResult(
                success=False,
                output="",
                error=str(e),
            )

    async def implement(
        self,
        issue_content: str,
        plan_content: str,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Implement the plan using claude.

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
        logger.debug(
            "implement_prompt_built",
            issue_number=issue_number,
            branch_name=branch_name,
            prompt_length=len(prompt),
            plan_length=len(plan_content),
        )

        try:
            # Stream output from claude
            logger.debug("starting_claude_code_streaming", issue_number=issue_number)
            event_count = 0
            async for event in self._run_claude_code_streaming(prompt, repository_path):
                event_count += 1
                logger.debug(
                    "streaming_event_received",
                    issue_number=issue_number,
                    event_type=event.type.value,
                    event_count=event_count,
                )
                yield event

            logger.debug(
                "streaming_completed",
                issue_number=issue_number,
                total_events=event_count,
            )
            yield AgentEvent(
                type=AgentEventType.COMPLETION,
                content="Implementation completed",
                metadata={"issue_number": issue_number, "branch": branch_name},
            )

        except Exception as e:
            logger.error("implementation_failed", error=str(e), issue_number=issue_number)
            logger.debug("implementation_exception", exc_info=True)
            yield AgentEvent(
                type=AgentEventType.FAILURE,
                content=f"Implementation failed: {e}",
                metadata={"issue_number": issue_number, "error": str(e)},
            )

    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Monitor an ongoing claude session.

        Args:
            session_id: The session ID to monitor

        Yields:
            AgentEvent objects from the session
        """
        logger.info("monitoring_session", session_id=session_id)
        logger.debug("monitor_not_implemented", session_id=session_id)

        # Note: claude CLI may not support session monitoring directly
        # This would need to be implemented based on the actual CLI capabilities
        yield AgentEvent(
            type=AgentEventType.STATUS,
            content=f"Monitoring session {session_id} (not yet implemented)",
            metadata={"session_id": session_id},
        )

    def _build_plan_prompt(self, issue_content: str) -> str:
        """Build the prompt for plan generation.

        Args:
            issue_content: The issue description

        Returns:
            Formatted prompt string
        """
        prompt = f"""Please create a detailed implementation plan for the following issue:

{issue_content}

Create a comprehensive plan that includes:
1. Analysis of the requirements
2. Step-by-step implementation approach
3. Files that need to be created or modified
4. Testing strategy
5. Any potential risks or considerations
"""
        logger.debug(
            "plan_prompt_built",
            issue_content_length=len(issue_content),
            prompt_length=len(prompt),
        )
        return prompt

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
        prompt = f"""Please implement the following GitHub issue according to the plan provided:

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
        logger.debug(
            "implement_prompt_built",
            issue_number=issue_number,
            branch_name=branch_name,
            issue_content_length=len(issue_content),
            plan_content_length=len(plan_content),
            prompt_length=len(prompt),
        )
        return prompt

    async def _run_claude_code(self, prompt: str, cwd: str) -> str:
        """Run claude CLI and return the full output.

        Args:
            prompt: The prompt to send to claude
            cwd: Working directory for the command

        Returns:
            Complete output from claude

        Raises:
            RuntimeError: If the command fails
        """
        # Build command with --print for non-interactive mode
        # Pass prompt as argument for better compatibility
        cmd = [self.cli_executable] + self.cli_args + ["--print", prompt]
        logger.debug(
            "executing_claude_code_command",
            command=cmd,
            cwd=cwd,
            prompt_length=len(prompt),
        )
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        logger.debug("waiting_for_claude_code_process", pid=process.pid)
        stdout, stderr = await process.communicate()

        logger.debug(
            "claude_code_process_completed",
            returncode=process.returncode,
            stdout_length=len(stdout) if stdout else 0,
            stderr_length=len(stderr) if stderr else 0,
        )

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.debug("claude_code_command_failed", returncode=process.returncode, error=error_msg)
            raise RuntimeError(f"claude failed: {error_msg}")

        output = stdout.decode()
        logger.debug("claude_code_output_decoded", output_length=len(output))
        return output

    async def _run_claude_code_streaming(self, prompt: str, cwd: str) -> AsyncIterator[AgentEvent]:
        """Run claude CLI and stream output.

        Args:
            prompt: The prompt to send to claude
            cwd: Working directory for the command

        Yields:
            AgentEvent objects with output chunks
        """
        # Build command with --print and --output-format=stream-json for streaming
        # Pass prompt as argument for better compatibility
        cmd = [
            self.cli_executable
        ] + self.cli_args + [
            "--print",
            "--output-format=stream-json",
            "--verbose",
            prompt,
        ]
        logger.debug(
            "executing_claude_code_streaming_command",
            command=cmd,
            cwd=cwd,
            prompt_length=len(prompt),
        )
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        logger.debug("claude_code_streaming_process_started", pid=process.pid)

        # Stream stdout (JSON lines format)
        line_count = 0
        json_parse_errors = 0
        event_count = 0
        event_counts_by_type = {}
        result_parts = []  # Collect output for RESULT event
        if process.stdout:
            while True:
                line = await process.stdout.readline()
                if not line:
                    logger.debug("streaming_complete_no_more_lines", line_count=line_count)
                    break

                line_count += 1
                content = line.decode().rstrip()
                if not content:
                    logger.debug("skipping_empty_line", line_number=line_count)
                    continue

                logger.debug("processing_stream_line", line_number=line_count, content=content)

                try:
                    # Parse JSON line from stream-json format
                    data = json.loads(content)
                    logger.debug("json_line_parsed", line_number=line_count, data_keys=list(data.keys()))

                    # Extract text content from the message.content array
                    # Structure: {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '...'}]}, ...}
                    text_content = None
                    message = data.get("message", {})
                    if message:
                        content_blocks = message.get("content", [])
                        # Extract text from all content blocks
                        text_parts = []
                        for block in content_blocks:
                            if isinstance(block, dict):
                                block_type = block.get("type")
                                if block_type == "text":
                                    text_parts.append(block.get("text", ""))
                                elif block_type == "tool_use":
                                    # Handle tool use blocks
                                    tool_name = block.get("name", "unknown")
                                    tool_input = block.get("input", {})
                                    text_parts.append(f"[Using tool: {tool_name}]")
                                    if tool_input:
                                        text_parts.append(str(tool_input))

                        if text_parts:
                            text_content = "".join(text_parts)

                    if text_content:
                        # Determine event type based on data structure
                        event_type = AgentEventType.OUTPUT
                        data_type = data.get("type", "")

                        if data_type == "error":
                            event_type = AgentEventType.ERROR
                        elif data_type == "tool_use" or any(
                            block.get("type") == "tool_use"
                            for block in message.get("content", [])
                            if isinstance(block, dict)
                        ):
                            event_type = AgentEventType.TOOL_USE
                        elif "error" in text_content.lower():
                            event_type = AgentEventType.ERROR

                        # Collect output for RESULT event (exclude errors and tool use)
                        if event_type == AgentEventType.OUTPUT:
                            result_parts.append(text_content)

                        # Extract session_id from JSON data if present
                        metadata = {}
                        session_id = data.get("session_id")
                        if session_id:
                            metadata["session_id"] = session_id

                        event_count += 1
                        event_counts_by_type[event_type.value] = event_counts_by_type.get(event_type.value, 0) + 1

                        logger.info(
                            "claude_code_streaming_event",
                            event_number=event_count,
                            event_type=event_type.value,
                            content_length=len(text_content),
                            content=text_content,
                            has_session_id=bool(session_id),
                            session_id=session_id if session_id else None,
                            line_number=line_count,
                        )
                        yield AgentEvent(
                            type=event_type,
                            content=text_content,
                            metadata=metadata if metadata else None,
                        )
                    else:
                        logger.debug("no_text_content_in_json", line_number=line_count, data=data)
                except json.JSONDecodeError as e:
                    json_parse_errors += 1
                    logger.debug(
                        "json_decode_error_fallback_to_text",
                        line_number=line_count,
                        error=str(e),
                        content=content,
                    )
                    # Fallback: if not JSON, treat as plain text
                    if content:
                        event_type = AgentEventType.OUTPUT
                        if "error" in content.lower():
                            event_type = AgentEventType.ERROR
                        elif "using tool" in content.lower() or "tool:" in content.lower():
                            event_type = AgentEventType.TOOL_USE

                        # Collect output for RESULT event (exclude errors and tool use)
                        if event_type == AgentEventType.OUTPUT:
                            result_parts.append(content)

                        event_count += 1
                        event_counts_by_type[event_type.value] = event_counts_by_type.get(event_type.value, 0) + 1

                        logger.info(
                            "claude_code_streaming_event",
                            event_number=event_count,
                            event_type=event_type.value,
                            content_length=len(content),
                            content=content,
                            line_number=line_count,
                            is_fallback=True,
                        )
                        yield AgentEvent(
                            type=event_type,
                            content=content,
                        )

        logger.debug(
            "waiting_for_streaming_process_completion",
            line_count=line_count,
            json_parse_errors=json_parse_errors,
        )
        # Wait for completion
        await process.wait()

        logger.debug(
            "streaming_process_completed",
            returncode=process.returncode,
            line_count=line_count,
            json_parse_errors=json_parse_errors,
        )

        # Check for errors
        if process.returncode != 0:
            stderr_output = ""
            if process.stderr:
                stderr_output = await process.stderr.read()
                stderr_output = stderr_output.decode()

            logger.debug(
                "streaming_process_failed",
                returncode=process.returncode,
                stderr_length=len(stderr_output) if stderr_output else 0,
            )
            if stderr_output:
                event_count += 1
                event_counts_by_type[AgentEventType.ERROR.value] = event_counts_by_type.get(AgentEventType.ERROR.value, 0) + 1

                error_content = f"Process failed with exit code {process.returncode}: {stderr_output}"
                logger.info(
                    "claude_code_streaming_event",
                    event_number=event_count,
                    event_type=AgentEventType.ERROR.value,
                    content_length=len(error_content),
                    content=error_content,
                    returncode=process.returncode,
                )
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    content=error_content,
                )
        else:
            # Emit RESULT event with collected output on successful completion
            if result_parts:
                result_content = "\n".join(result_parts)
                event_count += 1
                event_counts_by_type[AgentEventType.RESULT.value] = event_counts_by_type.get(AgentEventType.RESULT.value, 0) + 1

                logger.info(
                    "claude_code_streaming_event",
                    event_number=event_count,
                    event_type=AgentEventType.RESULT.value,
                    content_length=len(result_content),
                )
                yield AgentEvent(
                    type=AgentEventType.RESULT,
                    content=result_content,
                )

        # Log summary of all events
        logger.info(
            "claude_code_streaming_completed",
            total_events=event_count,
            events_by_type=event_counts_by_type,
            total_lines=line_count,
            json_parse_errors=json_parse_errors,
            returncode=process.returncode,
        )

    def _extract_session_id(self, output: str) -> str | None:
        """Extract session ID from claude output.

        Args:
            output: Output from claude

        Returns:
            Session ID if found, None otherwise
        """
        logger.debug("extracting_session_id", output_length=len(output))

        # First, try to extract from JSON structures in the output
        # Look for JSON lines with session_id field
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                session_id = data.get("session_id")
                if session_id:
                    logger.debug("session_id_found_in_json", session_id=session_id)
                    return session_id
            except (json.JSONDecodeError, AttributeError):
                # Not JSON, continue to next line
                continue

        # Fallback: Try to find session ID pattern in text (adjust based on actual claude output)
        patterns = [
            r"session[_\s]id[:\s]+([a-f0-9-]+)",
            r"session[:\s]+([a-f0-9-]+)",
            r"id[:\s]+([a-f0-9-]+)",
        ]

        for i, pattern in enumerate(patterns):
            logger.debug("trying_session_id_pattern", pattern_index=i, pattern=pattern)
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                session_id = match.group(1)
                logger.debug("session_id_found", pattern_index=i, session_id=session_id)
                return session_id

        logger.debug("session_id_not_found", patterns_tried=len(patterns))
        return None
