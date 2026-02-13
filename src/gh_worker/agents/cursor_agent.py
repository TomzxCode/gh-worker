"""Cursor Agent implementation."""

import asyncio
import json
import re
import shutil
import tempfile
from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

from gh_worker.agents.base import (
    AgentEvent,
    AgentEventType,
    AgentResult,
    BaseAgent,
)

logger = structlog.get_logger()


class CursorAgent(BaseAgent):
    """Agent that uses the cursor-agent CLI tool."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Cursor Agent.

        Args:
            config: Agent configuration (e.g., cli_path, model, api_key)
        """
        super().__init__(config)
        logger.debug("Initializing cursor agent", config=config)

        # Support both cli_path and cursor_agent_path config keys
        if config:
            cli_path = config.get("cli_path") or config.get("cursor_agent_path")
            self.model = config.get("model")
            self.api_key = config.get("api_key")
        else:
            cli_path = None
            self.model = None
            self.api_key = None

        # Default to cursor-agent (try both cursor-agent and agent)
        if not cli_path:
            # Try cursor-agent first, then agent
            if shutil.which("cursor-agent"):
                cli_path = "cursor-agent"
            elif shutil.which("agent"):
                cli_path = "agent"
            else:
                cli_path = "cursor-agent"  # Default fallback
            logger.debug("Using default CLI path", cli_path=cli_path)

        self.cli_path = cli_path
        logger.debug("CLI path set", cli_path=self.cli_path)

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "cursor-agent"

    @property
    def requires_cli(self) -> bool:
        """Return whether this agent requires an external CLI tool."""
        return True

    async def validate_environment(self) -> tuple[bool, str | None]:
        """Validate that cursor-agent CLI is available.

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug("Validating environment", executable=self.cli_path)
        cli_location = shutil.which(self.cli_path)
        logger.debug("CLI location check", executable=self.cli_path, found=cli_location)
        if cli_location is None:
            error_msg = (
                f"cursor-agent CLI not found at '{self.cli_path}'. "
                "Please install it first. Try: npm install -g @cursor/agent"
            )
            logger.debug("Environment validation failed", error=error_msg)
            return (False, error_msg)
        logger.debug("Environment validation success", cli_path=cli_location)
        return True, None

    async def plan(
        self,
        issue_content: str,
        repository_path: str,
        *,
        on_session_id: Callable[[str], None] | None = None,
    ) -> AgentResult:
        """Generate an implementation plan for an issue using cursor-agent.

        Args:
            issue_content: The full issue description
            repository_path: Path to the cloned repository

        Returns:
            AgentResult with the generated plan
        """
        logger.info(
            "Generating plan",
            repository_path=repository_path,
        )

        # Generate a temporary file path for the plan
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        plan_file_path = temp_file.name
        temp_file.close()
        logger.debug("Plan file path generated", plan_file_path=plan_file_path)

        prompt = self._build_plan_prompt(issue_content, plan_file_path)
        prompt_length = len(prompt)
        issue_content_length = len(issue_content)

        logger.debug(
            "Plan prompt built",
            prompt_length=prompt_length,
            issue_content_length=issue_content_length,
            plan_file_path=plan_file_path,
        )

        # Warn if prompt is very large (likely to cause issues)
        if prompt_length > 100000:  # ~100KB
            logger.warning(
                "Large prompt detected",
                prompt_length=prompt_length,
                issue_content_length=issue_content_length,
                message="Prompt is very large and may exceed CLI tool limits",
            )

        try:
            # Run cursor-agent in plan mode with streaming
            logger.debug("Running cursor agent for plan")
            agent_output = None
            session_id = None
            async for event in self._run_cursor_agent_streaming(
                prompt, repository_path, mode="plan"
            ):
                # Extract result from RESULT event (for session_id extraction)
                if event.type == AgentEventType.RESULT:
                    agent_output = event.content
                    logger.debug(
                        "Result extracted",
                        output_length=len(agent_output) if agent_output else 0,
                    )

                # Extract session_id from event metadata if present
                if event.metadata and "session_id" in event.metadata:
                    session_id = event.metadata["session_id"]
                    if on_session_id:
                        on_session_id(session_id)
                    logger.debug(
                        "Session ID found in event",
                        session_id=session_id,
                    )

            # Extract session ID from output if not found in events
            if not session_id and agent_output:
                session_id = self._extract_session_id(agent_output)
                if session_id and on_session_id:
                    on_session_id(session_id)
                logger.debug(
                    "Session ID extracted from output",
                    session_id=session_id,
                )

            # Read the plan from the generated file
            try:
                with open(plan_file_path, encoding="utf-8") as f:
                    plan_content = f.read()
                logger.debug(
                    "Plan file read",
                    plan_file_path=plan_file_path,
                    content_length=len(plan_content),
                )
            except FileNotFoundError:
                logger.warning("Plan file not found", plan_file_path=plan_file_path)
                return AgentResult(
                    success=False,
                    output="",
                    error=(
                        f"Plan file not found at {plan_file_path}. "
                        "The agent may not have written the plan to the file."
                    ),
                )
            except Exception as e:
                logger.error("Plan file read error", plan_file_path=plan_file_path, error=str(e))
                return AgentResult(
                    success=False,
                    output="",
                    error=f"Failed to read plan file: {e}",
                )

            return AgentResult(
                success=True,
                output=plan_content,
                session_id=session_id,
            )
        except Exception as e:
            error_msg = str(e)
            # Check if this is the chunking error
            if "separator" in error_msg.lower() and "chunk" in error_msg.lower():
                logger.error(
                    "Plan generation failed (chunking error)",
                    error=error_msg,
                    prompt_length=prompt_length,
                    issue_content_length=issue_content_length,
                    message=(
                        "Prompt is too large for the CLI tool to process. "
                        "Consider truncating or summarizing the issue content."
                    ),
                )
                enhanced_error = (
                    f"Prompt too large for processing (length: {prompt_length} chars, "
                    f"issue content: {issue_content_length} chars). "
                    f"Original error: {error_msg}"
                )
            else:
                logger.error(
                    "Plan generation failed",
                    error=error_msg,
                    prompt_length=prompt_length,
                    issue_content_length=issue_content_length,
                )
                enhanced_error = error_msg

            logger.debug("Plan generation exception", exc_info=True)
            return AgentResult(
                success=False,
                output="",
                error=enhanced_error,
            )

    async def implement(
        self,
        issue_content: str,
        plan_content: str,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Implement the plan using cursor-agent.

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
            "Starting implementation",
            issue_number=issue_number,
            branch_name=branch_name,
            repository_path=repository_path,
        )

        prompt = self._build_implement_prompt(
            issue_content, plan_content, issue_number, branch_name
        )
        logger.debug(
            "Implement prompt built",
            issue_number=issue_number,
            branch_name=branch_name,
            prompt_length=len(prompt),
            plan_length=len(plan_content),
        )

        try:
            # Stream output from cursor-agent
            logger.debug("Starting cursor agent streaming", issue_number=issue_number)
            event_count = 0
            async for event in self._run_cursor_agent_streaming(prompt, repository_path):
                event_count += 1
                logger.debug(
                    "Streaming event received",
                    issue_number=issue_number,
                    event_type=event.type.value,
                    event_count=event_count,
                )
                yield event

            logger.debug(
                "Streaming completed",
                issue_number=issue_number,
                total_events=event_count,
            )
            yield AgentEvent(
                type=AgentEventType.COMPLETION,
                content="Implementation completed",
                metadata={"issue_number": issue_number, "branch": branch_name},
            )

        except Exception as e:
            logger.error("Implementation failed", error=str(e), issue_number=issue_number)
            logger.debug("Implementation exception", exc_info=True)
            yield AgentEvent(
                type=AgentEventType.FAILURE,
                content=f"Implementation failed: {e}",
                metadata={"issue_number": issue_number, "error": str(e)},
            )

    async def commit(
        self,
        repository_path: str,
        issue_number: int,
        branch_name: str,
    ) -> AsyncIterator[AgentEvent]:
        """Commit changes with a descriptive message using cursor-agent.

        Args:
            repository_path: Path to the cloned repository
            issue_number: Issue number
            branch_name: Branch name

        Yields:
            AgentEvent objects as the commit progresses
        """
        logger.info(
            "Starting commit",
            issue_number=issue_number,
            branch_name=branch_name,
            repository_path=repository_path,
        )

        prompt = self._build_commit_prompt(issue_number, branch_name)
        logger.debug(
            "Commit prompt built",
            issue_number=issue_number,
            branch_name=branch_name,
            prompt_length=len(prompt),
        )

        try:
            # Stream output from cursor-agent
            logger.debug("Starting cursor agent streaming for commit", issue_number=issue_number)
            event_count = 0
            async for event in self._run_cursor_agent_streaming(prompt, repository_path):
                event_count += 1
                logger.debug(
                    "Streaming event received",
                    issue_number=issue_number,
                    event_type=event.type.value,
                    event_count=event_count,
                )
                yield event

            logger.debug(
                "Streaming completed",
                issue_number=issue_number,
                total_events=event_count,
            )
            yield AgentEvent(
                type=AgentEventType.COMPLETION,
                content="Commit completed",
                metadata={"issue_number": issue_number, "branch": branch_name},
            )

        except Exception as e:
            logger.error("Commit failed", error=str(e), issue_number=issue_number)
            logger.debug("Commit exception", exc_info=True)
            yield AgentEvent(
                type=AgentEventType.FAILURE,
                content=f"Commit failed: {e}",
                metadata={"issue_number": issue_number, "error": str(e)},
            )

    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Monitor an ongoing cursor-agent session.

        Args:
            session_id: The session ID (chat ID) to monitor

        Yields:
            AgentEvent objects from the session
        """
        logger.info("Monitoring session", session_id=session_id)

        # Use --resume to continue the session
        try:
            async for event in self._run_cursor_agent_streaming(
                "",  # Empty prompt when resuming
                None,  # No specific workspace needed
                resume_session_id=session_id,
            ):
                yield event
        except Exception as e:
            logger.error("Monitoring failed", error=str(e), session_id=session_id)
            yield AgentEvent(
                type=AgentEventType.ERROR,
                content=f"Failed to monitor session: {e}",
                metadata={"session_id": session_id, "error": str(e)},
            )

    def _build_plan_prompt(self, issue_content: str, plan_file_path: str) -> str:
        """Build the prompt for plan generation.

        Args:
            issue_content: The issue description
            plan_file_path: Path to the file where the plan should be written

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

Write the plan to the following file: {plan_file_path}
"""
        logger.debug(
            "Plan prompt built",
            issue_content_length=len(issue_content),
            prompt_length=len(prompt),
            plan_file_path=plan_file_path,
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
1. Implement the changes according to the plan
2. Run tests to ensure everything works

Note: You are already on branch {branch_name}. Do not create or checkout branches.
Do not commit changes yet - that will be done separately after implementation.

Please proceed with the implementation.
"""
        logger.debug(
            "Implement prompt built",
            issue_number=issue_number,
            branch_name=branch_name,
            issue_content_length=len(issue_content),
            plan_content_length=len(plan_content),
            prompt_length=len(prompt),
        )
        return prompt

    def _build_commit_prompt(self, issue_number: int, branch_name: str) -> str:
        """Build the prompt for generating a commit message.

        Args:
            issue_number: Issue number
            branch_name: Branch name

        Returns:
            Formatted prompt string
        """
        prompt = f"""Please generate a descriptive commit message for the changes made.

You are working on branch {branch_name} for issue #{issue_number}.

Requirements:
- The commit message should be clear and descriptive
- It should explain what was implemented
- It should reference issue #{issue_number}
- Provide only the commit message text, nothing else

Please provide the commit message.
"""
        logger.debug(
            "Commit prompt built",
            issue_number=issue_number,
            branch_name=branch_name,
            prompt_length=len(prompt),
        )
        return prompt

    async def _run_cursor_agent_streaming(
        self,
        prompt: str,
        cwd: str | None,
        mode: str | None = None,
        resume_session_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run cursor-agent CLI and stream output.

        Args:
            prompt: The prompt to send to cursor-agent
            cwd: Working directory for the command (None for resume)
            mode: Execution mode (e.g., "plan", "ask")
            resume_session_id: Session ID to resume (if provided)

        Yields:
            AgentEvent objects with output chunks
        """
        # Build command with --print and --output-format=stream-json for streaming
        cmd = [self.cli_path, "--print", "--output-format=stream-json"]

        # Add workspace if cwd is provided
        if cwd:
            cmd.extend(["--workspace", cwd])

        # Add model if configured
        if self.model:
            cmd.extend(["--model", self.model])

        # Add API key if configured
        if self.api_key:
            cmd.extend(["--api-key", self.api_key])

        # Add mode if specified
        if mode:
            cmd.extend(["--mode", mode])

        # Add resume if session ID is provided
        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])

        # Add prompt if provided (not when resuming)
        if prompt and not resume_session_id:
            cmd.append(prompt)

        logger.debug(
            "Executing cursor agent streaming command",
            command=cmd,
            cwd=cwd,
            prompt_length=len(prompt) if prompt else 0,
            mode=mode,
            resume_session_id=resume_session_id,
        )

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd if cwd else None,
            limit=10 * 2**20,  # 10MB buffer limit to prevent chunk separator errors
        )
        logger.debug("Cursor agent streaming process started", pid=process.pid)

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
                    logger.debug("Streaming complete, no more lines", line_count=line_count)
                    break

                line_count += 1
                content = line.decode().rstrip()
                if not content:
                    logger.debug("Skipping empty line", line_number=line_count)
                    continue

                logger.debug("Processing stream line", line_number=line_count, content=content)

                try:
                    # Parse JSON line from stream-json format
                    data = json.loads(content)
                    logger.debug(
                        "JSON line parsed", line_number=line_count, data_keys=list(data.keys())
                    )

                    # Extract text content from the message structure
                    # Structure may vary, so we'll handle different formats
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

                    # Also check for direct text content
                    if not text_content:
                        text_content = data.get("text") or data.get("content")

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

                        # Extract session_id/chat_id from JSON data if present
                        metadata = {}
                        session_id = (
                            data.get("session_id") or data.get("chat_id") or data.get("chatId")
                        )
                        if session_id:
                            metadata["session_id"] = session_id

                        event_count += 1
                        event_counts_by_type[event_type.value] = (
                            event_counts_by_type.get(event_type.value, 0) + 1
                        )

                        logger.info(
                            "Cursor agent streaming event",
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
                        logger.debug("No text content in JSON", line_number=line_count, data=data)

                except json.JSONDecodeError as e:
                    json_parse_errors += 1
                    logger.debug(
                        "JSON decode error, fallback to text",
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
                        event_counts_by_type[event_type.value] = (
                            event_counts_by_type.get(event_type.value, 0) + 1
                        )

                        logger.info(
                            "Cursor agent streaming event",
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
            "Waiting for streaming process completion",
            line_count=line_count,
            json_parse_errors=json_parse_errors,
        )
        # Wait for completion
        await process.wait()

        logger.debug(
            "Streaming process completed",
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
                "Streaming process failed",
                returncode=process.returncode,
                stderr_length=len(stderr_output) if stderr_output else 0,
            )
            if stderr_output:
                event_count += 1
                event_counts_by_type[AgentEventType.ERROR.value] = (
                    event_counts_by_type.get(AgentEventType.ERROR.value, 0) + 1
                )

                error_content = (
                    f"Process failed with exit code {process.returncode}: {stderr_output}"
                )
                logger.info(
                    "cursor_agent_streaming_event",
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
                event_counts_by_type[AgentEventType.RESULT.value] = (
                    event_counts_by_type.get(AgentEventType.RESULT.value, 0) + 1
                )

                logger.info(
                    "cursor_agent_streaming_event",
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
            "Cursor agent streaming completed",
            total_events=event_count,
            events_by_type=event_counts_by_type,
            total_lines=line_count,
            json_parse_errors=json_parse_errors,
            returncode=process.returncode,
        )

    def _extract_session_id(self, output: str) -> str | None:
        """Extract session ID (chat ID) from cursor-agent output.

        Args:
            output: Output from cursor-agent

        Returns:
            Session ID if found, None otherwise
        """
        logger.debug("Extracting session ID", output_length=len(output))

        # First, try to extract from JSON structures in the output
        # Look for JSON lines with session_id, chat_id, or chatId field
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                session_id = data.get("session_id") or data.get("chat_id") or data.get("chatId")
                if session_id:
                    logger.debug("Session ID found in JSON", session_id=session_id)
                    return session_id
            except (json.JSONDecodeError, AttributeError):
                # Not JSON, continue to next line
                continue

        # Fallback: Try to find session ID pattern in text
        patterns = [
            r"session[_\s]id[:\s]+([a-f0-9-]+)",
            r"chat[_\s]id[:\s]+([a-f0-9-]+)",
            r"chatId[:\s]+([a-f0-9-]+)",
            r"session[:\s]+([a-f0-9-]+)",
            r"id[:\s]+([a-f0-9-]+)",
        ]

        for i, pattern in enumerate(patterns):
            logger.debug("Trying session ID pattern", pattern_index=i, pattern=pattern)
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                session_id = match.group(1)
                logger.debug("Session ID found", pattern_index=i, session_id=session_id)
                return session_id

        logger.debug("Session ID not found", patterns_tried=len(patterns))
        return None
