"""HCI Event packet parser."""

from hci_analyzer.models import ParseResult


class HciEventParser:
    """Decode HCI events related to LE RF PHY tests."""

    def parse(self, frame: bytes) -> ParseResult:
        """Parse one complete H4 HCI Event frame."""
        raise NotImplementedError

