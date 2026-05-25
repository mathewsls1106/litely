"""Vertical 2: Componentes UI de Textual - Solo presentación"""

from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class InputModal(ModalScreen):
    """Modal genérico para entrada de texto."""

    def __init__(self, prompt: str, initial_value: str = ""):
        super().__init__()
        self.prompt_text = prompt
        self.initial_value = initial_value

    def compose(self):
        with Container(classes="modal-container"):
            yield Label(self.prompt_text)
            yield Input(value=self.initial_value, id="input")
            with Horizontal(classes="buttons"):
                yield Button("Confirm", variant="success", id="confirm")
                yield Button("Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            input_val = self.query_one("#input", Input).value
            self.dismiss(input_val)
        else:
            self.dismiss(None)


class ConfirmModal(ModalScreen):
    """Modal de confirmación genérico."""

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self):
        with Container(classes="modal-container"):
            yield Label(self.message)
            with Horizontal(classes="buttons"):
                yield Button("Yes", variant="success", id="yes")
                yield Button("No", variant="error", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")