"""Agent/model confirmation modal for plan and implement actions."""

from pathlib import Path

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select


class AgentConfirmModal(ModalScreen[tuple[str, str | None] | None]):
    """Modal to confirm agent and model before running plan or implement."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(
        self,
        action: str,
        config_path: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.action = action
        self.config_path = config_path

    def compose(self):
        """Compose modal content."""
        from gh_worker.agents.registry import get_registry
        from gh_worker.config.manager import ConfigManager

        config = ConfigManager(self.config_path)
        app_config = config.load()
        default_agent = app_config.agent.default
        default_model = app_config.agent.model or ""

        registry = get_registry()
        agent_options = [(name, name) for name in registry.list_agents()]
        initial_agent = (
            default_agent
            if default_agent in registry.list_agents()
            else (agent_options[0][1] if agent_options else None)
        )

        with Vertical():
            yield Label(
                f"Confirm {self.action.capitalize()} — select agent and model",
                id="modal-title",
            )
            yield Label("Agent", classes="modal-label")
            yield Select(agent_options, value=initial_agent, id="modal-agent")
            yield Label("Model (optional override)", classes="modal-label")
            yield Input(
                value=default_model,
                placeholder="Leave blank for agent default",
                id="modal-model",
            )
            with Horizontal(id="modal-buttons"):
                yield Button("Cancel", id="modal-cancel", variant="default")
                yield Button("Confirm", id="modal-confirm", variant="primary")

    def on_mount(self) -> None:
        """Focus the confirm button on mount."""
        self.query_one("#modal-confirm", Button).focus()

    def action_cancel(self) -> None:
        """Cancel and dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "modal-cancel":
            self.dismiss(None)
        elif event.button.id == "modal-confirm":
            agent_select = self.query_one("#modal-agent", Select)
            model_input = self.query_one("#modal-model", Input)
            agent_val = agent_select.value
            agent = str(agent_val) if agent_val not in (Select.BLANK, None) else None
            model_val = model_input.value.strip() or None
            if agent:
                self.dismiss((agent, model_val))
            else:
                self.dismiss(None)
