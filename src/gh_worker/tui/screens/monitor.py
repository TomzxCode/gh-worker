"""Monitor screen - stream agent events for plan/implement."""

from pathlib import Path

from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static


class MonitorEventMessage(Message):
    """Message sent when monitor receives an event from agent."""

    def __init__(self, event_type: str, content: str) -> None:
        self.event_type = event_type
        self.content = content
        super().__init__()


class MonitorScreen(Screen):
    """Screen for monitoring agent session output."""

    def __init__(
        self,
        repo: str,
        issue_number: int,
        config_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.repo = repo
        self.issue_number = issue_number
        self.config_path = config_path

    def compose(self):
        """Compose monitor screen."""
        yield Header()
        yield Static(
            f"Monitor: {self.repo} #{self.issue_number}",
            id="monitor-title",
        )
        yield RichLog(id="monitor-log", auto_scroll=True)
        yield Button("Close", id="monitor-close", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Start monitoring on mount."""
        self.run_worker(
            self._run_monitor(),
            name="monitor",
            group="monitor",
            exit_on_error=False,
        )

    async def _run_monitor(self) -> None:
        """Run monitor and stream events to UI."""
        from gh_worker.agents.base import AgentEventType
        from gh_worker.agents.registry import get_registry
        from gh_worker.config.manager import ConfigManager
        from gh_worker.storage.issue_store import IssueStore
        from gh_worker.storage.plan_store import PlanStore

        config = ConfigManager(self.config_path)
        app_config = config.load()
        if not app_config.issues_path:
            self.post_message(MonitorEventMessage("ERROR", "Issues path not configured"))
            return

        issue_store = IssueStore(app_config.issues_path)
        plan_store = PlanStore(app_config.issues_path)

        try:
            repository = issue_store.resolve_repo(self.repo)
        except ValueError as e:
            self.post_message(MonitorEventMessage("ERROR", str(e)))
            return

        plan_result = plan_store.get_latest_plan(repository, self.issue_number)
        if not plan_result:
            self.post_message(MonitorEventMessage("ERROR", "No plan found"))
            return

        _, metadata = plan_result
        if not metadata.session_id:
            self.post_message(
                MonitorEventMessage("ERROR", "No session ID - plan/implement may not have started")
            )
            return

        registry = get_registry()
        agent_name = metadata.agent or app_config.agent.default
        agent_config = {
            "claude_code_path": app_config.agent.claude_code_path,
            "opencode_path": app_config.agent.opencode_path,
        }
        agent = registry.get(agent_name, agent_config)

        is_valid, error_msg = await agent.validate_environment()
        if not is_valid:
            self.post_message(MonitorEventMessage("ERROR", f"Agent invalid: {error_msg}"))
            return

        try:
            async for event in agent.monitor(metadata.session_id):
                if event.type == AgentEventType.OUTPUT:
                    self.post_message(MonitorEventMessage("OUTPUT", event.content))
                elif event.type == AgentEventType.ERROR:
                    self.post_message(MonitorEventMessage("ERROR", event.content))
                elif event.type == AgentEventType.STATUS:
                    self.post_message(MonitorEventMessage("STATUS", event.content))
                elif event.type == AgentEventType.TOOL_USE:
                    self.post_message(MonitorEventMessage("TOOL", event.content))
                elif event.type == AgentEventType.COMPLETION:
                    self.post_message(MonitorEventMessage("COMPLETION", event.content))
                    break
                elif event.type == AgentEventType.FAILURE:
                    self.post_message(MonitorEventMessage("FAILURE", event.content))
                    break
        except Exception as e:
            self.post_message(MonitorEventMessage("ERROR", str(e)))

    def on_monitor_event_message(self, event: MonitorEventMessage) -> None:
        """Handle monitor event - append to log."""
        log = self.query_one("#monitor-log", RichLog)
        prefix = f"{event.event_type:8} "
        log.write(f"{prefix}{event.content}", expand=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Close button."""
        if event.button.id == "monitor-close":
            self.dismiss()
