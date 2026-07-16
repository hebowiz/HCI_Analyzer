"""Public parser facade for bytes and hexadecimal text."""

from hci_analyzer.models import ParseResult
from hci_analyzer.parser.command import HciCommandParser
from hci_analyzer.parser.event import HciEventParser


class HciParser:
    """Dispatch complete H4 frames to command or event parsers."""

    def __init__(
        self,
        command_parser: HciCommandParser | None = None,
        event_parser: HciEventParser | None = None,
    ) -> None:
        self._command_parser = command_parser
        self._event_parser = event_parser

    def parse_bytes(self, data: bytes) -> ParseResult:
        """Parse a complete H4 frame supplied as bytes."""
        raise NotImplementedError

    def parse_hex_string(self, text: str) -> ParseResult:
        """Parse a complete H4 frame supplied as hexadecimal text."""
        raise NotImplementedError

