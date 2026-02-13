"""OpenCode agent implementation."""

import asyncio
import json
import shutil
import tempfile
from collections.abc import AsyncIterator, Callable
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


class OpenCodeAgent(BaseAgent):
    """Agent that uses the OpenCode CLI (opencode run)."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the OpenCode agent.

        Args:
            config: Agent configuration (e.g., cli_path, opencode_path)
        """
        super().__init__(config)
        logger.debug("Initializing opencode agent", config=config)
        cli_path = None
        if config:
            cli_path = config.get("cli_path") or config.get("opencode_path")

        if not cli_path:
            cli_path = "opencode"
            logger.debug("Using default CLI path", cli_path=cli_path)

        self.cli_path = cli_path
        self.cli_executable = cli_path
        self.cli_args: list[str] = []
        logger.debug("CLI path set", cli_path=self.cli_path)

    @property
    def name(self) -> str:
        """Return the agent name."""
        return "opencode"

    @property
    def requires_cli(self) -> bool:
        """Return whether this agent requires an external CLI tool."""
        return True

    async def validate_environment(self) -> tuple[bool, str | None]:
        """Validate that OpenCode CLI is available.

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.debug("Validating environment", executable=self.cli_executable)
        cli_location = shutil.which(self.cli_executable)
        logger.debug(
            "cli_location_check",
            executable=self.cli_executable,
            found=cli_location,
        )
        if cli_location is None:
            error_msg = (
                f"OpenCode CLI not found at '{self.cli_executable}'. "
                "Please install it first. Try: npm i -g opencode-ai"
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
        """Generate an implementation plan for an issue using OpenCode.

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

        temp_dir = tempfile.mkdtemp()
        plan_file_path = str(Path(temp_dir) / "PLAN.md")
        logger.debug(
            "temp_dir_generated",
            temp_dir=temp_dir,
            plan_file_path=plan_file_path,
        )

        prompt = self._build_plan_prompt(issue_content, plan_file_path)
        logger.debug(
            "plan_prompt_built",
            prompt_length=len(prompt),
            temp_dir=temp_dir,
        )

        try:
            agent_output = None
            session_id = None

            async for event in self._run_opencode_streaming(
                prompt,
                repository_path,
                agent="build",
            ):
                if event.type == AgentEventType.RESULT:
                    agent_output = event.content
                    logger.debug(
                        "result_extracted",
                        output_length=len(agent_output) if agent_output else 0,
                    )
                if event.metadata and "session_id" in event.metadata:
                    session_id = event.metadata["session_id"]
                    if on_session_id:
                        on_session_id(session_id)
                    logger.debug("Session ID found in event", session_id=session_id)

            if not session_id and agent_output:
                session_id = self._extract_session_id(agent_output)
                if session_id and on_session_id:
                    on_session_id(session_id)
                logger.debug(
                    "session_id_extracted_from_output",
                    session_id=session_id,
                )

            try:
                with open(plan_file_path, encoding="utf-8") as f:
                    plan_content = f.read()
                logger.debug(
                    "plan_file_read",
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
                    metadata={"agent": "opencode"},
                )
            except Exception as e:
                logger.error(
                    "plan_file_read_error",
                    plan_file_path=plan_file_path,
                    error=str(e),
                )
                return AgentResult(
                    success=False,
                    output="",
                    error=f"Failed to read plan file: {e}",
                    metadata={"agent": "opencode"},
                )

            return AgentResult(
                success=True,
                output=plan_content,
                session_id=session_id,
                metadata={"agent": "opencode"},
            )
        except Exception as e:
            logger.error("Plan generation failed", error=str(e))
            logger.debug("Plan generation exception", exc_info=True)
            return AgentResult(
                success=False,
                output="",
                error=str(e),
                metadata={"agent": "opencode"},
            )
        finally:
            try:
                shutil.rmtree(temp_dir)
                logger.debug("Temp dir cleaned up", temp_dir=temp_dir)
            except Exception as e:
                logger.warning(
                    "temp_dir_cleanup_failed",
                    temp_dir=temp_dir,
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
        """Implement the plan using OpenCode.

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
            event_count = 0
            async for event in self._run_opencode_streaming(prompt, repository_path, agent="build"):
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
            logger.error(
                "implementation_failed",
                error=str(e),
                issue_number=issue_number,
            )
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
        """Commit changes with a descriptive message using OpenCode.

        Args:
            repository_path: Path to the cloned repository
            issue_number: Issue number
            branch_name: Branch name

        Yields:
            AgentEvent objects as the commit progresses
        """
        logger.info(
            "starting_commit",
            issue_number=issue_number,
            branch_name=branch_name,
            repository_path=repository_path,
        )

        prompt = self._build_commit_prompt(issue_number, branch_name)
        logger.debug(
            "commit_prompt_built",
            issue_number=issue_number,
            branch_name=branch_name,
            prompt_length=len(prompt),
        )

        try:
            event_count = 0
            async for event in self._run_opencode_streaming(prompt, repository_path, agent="build"):
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
                content="Commit completed",
                metadata={"issue_number": issue_number, "branch": branch_name},
            )

        except Exception as e:
            logger.error(
                "commit_failed",
                error=str(e),
                issue_number=issue_number,
            )
            logger.debug("Commit exception", exc_info=True)
            yield AgentEvent(
                type=AgentEventType.FAILURE,
                content=f"Commit failed: {e}",
                metadata={"issue_number": issue_number, "error": str(e)},
            )

    async def monitor(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Monitor an ongoing OpenCode session.

        Args:
            session_id: The session ID to monitor

        Yields:
            AgentEvent objects from the session
        """
        logger.info("Monitoring session", session_id=session_id)
        logger.debug("Monitor not implemented", session_id=session_id)

        yield AgentEvent(
            type=AgentEventType.STATUS,
            content=f"Monitoring session {session_id} (not yet implemented)",
            metadata={"session_id": session_id},
        )

    def _build_plan_prompt(self, issue_content: str, plan_file_path: str) -> str:
        """Build the prompt for plan generation."""
        return f"""Please create a detailed implementation plan for the following issue:

{issue_content}

Create a comprehensive plan that includes:
1. Analysis of the requirements
2. Step-by-step implementation approach
3. Files that need to be created or modified
4. Testing strategy
5. Any potential risks or considerations

Write the plan to the following file: {plan_file_path}
"""

    def _build_implement_prompt(
        self,
        issue_content: str,
        plan_content: str,
        issue_number: int,
        branch_name: str,
    ) -> str:
        """Build the prompt for implementation."""
        return f"""Please implement the following GitHub issue according to the plan provided:

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

    def _build_commit_prompt(self, issue_number: int, branch_name: str) -> str:
        """Build the prompt for generating a commit message."""
        return f"""Please generate a descriptive commit message for the changes made.

You are working on branch {branch_name} for issue #{issue_number}.

Requirements:
- The commit message should be clear and descriptive
- It should explain what was implemented
- It should reference issue #{issue_number}
- Provide only the commit message text, nothing else

Please provide the commit message.
"""

    async def _run_opencode_streaming(
        self,
        prompt: str,
        cwd: str,
        agent: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run OpenCode CLI and stream output.

        Args:
            prompt: The prompt to send to OpenCode
            cwd: Working directory for the command
            agent: Agent to use (e.g., "build", "plan")

        Yields:
            AgentEvent objects with output chunks
        """
        cmd = [
            self.cli_executable,
            "run",
            "--format",
            "json",
            prompt,
        ]

        if agent:
            cmd.extend(["--agent", agent])

        logger.debug(
            "executing_opencode_streaming_command",
            command=cmd,
            cwd=cwd,
            prompt_length=len(prompt),
        )

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            limit=10 * 2**20,
        )
        logger.debug("Opencode streaming process started", pid=process.pid)

        line_count = 0
        json_parse_errors = 0
        event_count = 0
        result_parts: list[str] = []
        session_id: str | None = None

        if process.stdout:
            while True:
                line = await process.stdout.readline()
                if not line:
                    logger.debug(
                        "streaming_complete_no_more_lines",
                        line_count=line_count,
                    )
                    break

                line_count += 1
                content = line.decode().rstrip()
                if not content:
                    logger.debug("Skipping empty line", line_number=line_count)
                    continue

                logger.debug(
                    "processing_stream_line",
                    line_number=line_count,
                    content=content[:200],
                )

                try:
                    data = json.loads(content)
                    event_type_str = data.get("type", "")
                    event_session_id = data.get("sessionID")
                    if event_session_id:
                        session_id = event_session_id

                    metadata: dict[str, Any] = {}
                    if session_id:
                        metadata["session_id"] = session_id

                    if event_type_str == "error":
                        error_data = data.get("error", {})
                        error_msg = str(error_data)
                        if isinstance(error_data, dict) and "message" in error_data:
                            error_msg = str(error_data.get("message", error_msg))
                        event_count += 1
                        logger.info(
                            "opencode_streaming_event",
                            event_number=event_count,
                            event_type=AgentEventType.ERROR.value,
                            content_length=len(error_msg),
                        )
                        yield AgentEvent(
                            type=AgentEventType.ERROR,
                            content=error_msg,
                            metadata=metadata if metadata else None,
                        )
                        continue

                    if event_type_str == "tool_use":
                        part = data.get("part", {})
                        tool_name = part.get("tool", "unknown")
                        text_content = f"[Using tool: {tool_name}]"
                        event_count += 1
                        logger.info(
                            "opencode_streaming_event",
                            event_number=event_count,
                            event_type=AgentEventType.TOOL_USE.value,
                            content_length=len(text_content),
                        )
                        yield AgentEvent(
                            type=AgentEventType.TOOL_USE,
                            content=text_content,
                            metadata=metadata if metadata else None,
                        )
                        continue

                    if event_type_str == "text":
                        part = data.get("part", {})
                        text_content = part.get("text", "").strip()
                        if text_content:
                            result_parts.append(text_content)
                            event_count += 1
                            logger.info(
                                "opencode_streaming_event",
                                event_number=event_count,
                                event_type=AgentEventType.OUTPUT.value,
                                content_length=len(text_content),
                            )
                            yield AgentEvent(
                                type=AgentEventType.OUTPUT,
                                content=text_content,
                                metadata=metadata if metadata else None,
                            )
                        continue

                    if event_type_str in ("step_start", "step_finish"):
                        event_count += 1
                        yield AgentEvent(
                            type=AgentEventType.STATUS,
                            content=f"Step: {event_type_str}",
                            metadata=metadata if metadata else None,
                        )
                        continue

                except json.JSONDecodeError as e:
                    json_parse_errors += 1
                    logger.debug(
                        "json_decode_error",
                        line_number=line_count,
                        error=str(e),
                        content=content[:100],
                    )
                    if content.strip():
                        result_parts.append(content)
                        event_count += 1
                        yield AgentEvent(
                            type=AgentEventType.OUTPUT,
                            content=content,
                        )

        logger.debug(
            "waiting_for_streaming_process_completion",
            line_count=line_count,
            json_parse_errors=json_parse_errors,
        )
        await process.wait()

        logger.debug(
            "streaming_process_completed",
            returncode=process.returncode,
            line_count=line_count,
            json_parse_errors=json_parse_errors,
        )

        if process.returncode != 0:
            stderr_output = ""
            if process.stderr:
                stderr_output = (await process.stderr.read()).decode()

            logger.debug(
                "streaming_process_failed",
                returncode=process.returncode,
                stderr_length=len(stderr_output),
            )
            if stderr_output:
                error_content = (
                    f"Process failed with exit code {process.returncode}: {stderr_output}"
                )
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    content=error_content,
                )
        else:
            if result_parts:
                result_content = "\n".join(result_parts)
                yield AgentEvent(
                    type=AgentEventType.RESULT,
                    content=result_content,
                    metadata={"session_id": session_id} if session_id else None,
                )

        logger.info(
            "opencode_streaming_completed",
            total_events=event_count,
            total_lines=line_count,
            json_parse_errors=json_parse_errors,
            returncode=process.returncode,
        )

    def _extract_session_id(self, output: str) -> str | None:
        """Extract session ID from OpenCode output."""
        logger.debug("Extracting session ID", output_length=len(output))

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                sid = data.get("sessionID") or data.get("session_id")
                if sid:
                    logger.debug("Session ID found in JSON", session_id=sid)
                    return sid
            except (json.JSONDecodeError, AttributeError):
                continue

        return None
