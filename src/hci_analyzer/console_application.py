"""Top-level coordination for the HCI Command Console."""

from hci_analyzer.command_builder.encoder import HciCommandEncoder
from hci_analyzer.command_builder.validation import CommandValidator
from hci_analyzer.gui.command_console import CommandConsoleWindow
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.serial.transport import HciSerialTransport


class HciCommandConsoleApplication:
    """Compose command selection, encoding, serial transport, and logging UI."""

    def __init__(self) -> None:
        self._parser: HciParser
        self._encoder: HciCommandEncoder
        self._validator: CommandValidator
        self._transport: HciSerialTransport
        self._window: CommandConsoleWindow

    def run(self) -> None:
        """Start the Command Console event loop."""
        raise NotImplementedError

