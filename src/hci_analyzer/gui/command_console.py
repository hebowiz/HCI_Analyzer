"""Tkinter window for command selection, parameter editing, and TX/RX logs."""

from collections.abc import Callable
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import ConsoleCommandDefinition
from hci_analyzer.serial.transport import TransportEvent


class CommandConsoleWindow:
    """Present serial controls and a schema-generated command form."""

    def __init__(
        self,
        on_connect: Callable[[], None],
        on_disconnect: Callable[[], None],
        on_command_selected: Callable[[int], None],
        on_preview: Callable[[Mapping[str, Any]], None],
        on_send: Callable[[Mapping[str, Any]], None],
        on_clear_log: Callable[[], None],
    ) -> None:
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_command_selected = on_command_selected
        self._on_preview = on_preview
        self._on_send = on_send
        self._on_clear_log = on_clear_log

    def run(self) -> None:
        """Start the Tkinter event loop."""
        raise NotImplementedError

    def set_serial_ports(self, ports: list[str]) -> None:
        """Populate the serial-port selector."""
        raise NotImplementedError

    def set_command_definitions(
        self, definitions: tuple[ConsoleCommandDefinition, ...]
    ) -> None:
        """Populate category, command, and version selectors."""
        raise NotImplementedError

    def show_parameter_form(self, definition: ConsoleCommandDefinition) -> None:
        """Generate editors for every parameter in the selected command."""
        raise NotImplementedError

    def get_connection_settings(self) -> tuple[str, int]:
        """Return the selected port and baud rate."""
        raise NotImplementedError

    def get_parameter_values(self) -> dict[str, Any]:
        """Return all values currently entered in the parameter form."""
        raise NotImplementedError

    def show_packet_preview(self, frame: bytes) -> None:
        """Display the generated UART HCI packet as hexadecimal text."""
        raise NotImplementedError

    def show_validation_issues(self, issues: Mapping[str, str]) -> None:
        """Display field validation state and update send availability."""
        raise NotImplementedError

    def append_transport_event(self, event: TransportEvent) -> None:
        """Append a timestamped TX, RX, system, or error entry."""
        raise NotImplementedError

    def clear_log(self) -> None:
        """Clear the in-memory GUI log."""
        raise NotImplementedError

    def set_connected_state(self, connected: bool) -> None:
        """Enable or disable controls based on connection state."""
        raise NotImplementedError

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        """Set the window-close callback."""
        raise NotImplementedError

