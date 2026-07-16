"""HCI Command packet parser."""

from hci_analyzer.models import ParseResult


class HciCommandParser:
    """Decode supported LE RF PHY Test command packets."""

    def parse(self, frame: bytes) -> ParseResult:
        """Parse one complete H4 HCI Command frame."""
        raise NotImplementedError

