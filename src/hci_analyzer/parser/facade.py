"""Public parser facade for bytes and hexadecimal text."""

import re

from hci_analyzer.models import H4PacketIndicator, ParseError, ParseResult
from hci_analyzer.parser.command import HciCommandParser
from hci_analyzer.parser.event import HciEventParser
from hci_analyzer.parser.race import RaceParser, race_frame_length


class HciParser:
    """Dispatch complete H4 frames to command or event parsers."""

    def __init__(
        self,
        command_parser: HciCommandParser | None = None,
        event_parser: HciEventParser | None = None,
        *,
        prefer_race: bool = True,
    ) -> None:
        self._command_parser = command_parser or HciCommandParser()
        self._event_parser = event_parser or HciEventParser()
        self._race_parser = RaceParser()
        self._prefer_race = prefer_race

    def parse_bytes(self, data: bytes) -> ParseResult:
        """Parse a complete H4 frame supplied as bytes."""
        if not isinstance(data, bytes):
            return self._error(
                b"",
                "INVALID_INPUT_TYPE",
                "Input must be bytes",
                {"input_type": type(data).__name__},
            )
        if not data:
            return self._error(data, "EMPTY_INPUT", "Input is empty")

        indicator = data[0]
        if indicator == H4PacketIndicator.COMMAND:
            return self._command_parser.parse(data)
        if indicator == H4PacketIndicator.EVENT:
            return self._event_parser.parse(data)
        if (
            indicator == H4PacketIndicator.ISO_DATA
            and self._prefer_race
            and race_frame_length(data) is not None
        ):
            return self._race_parser.parse(data)
        if indicator in (
            H4PacketIndicator.ACL_DATA,
            H4PacketIndicator.SYNCHRONOUS_DATA,
            H4PacketIndicator.ISO_DATA,
        ):
            return self._parse_data_packet(data)
        return self._error(
            data,
            "UNKNOWN_PACKET_INDICATOR",
            f"Unknown H4 packet indicator 0x{indicator:02X}",
        )

    def parse(self, data: bytes | str) -> dict[str, object]:
        """Parse bytes or hexadecimal text and return a plain dictionary."""
        if isinstance(data, bytes):
            return self.parse_bytes(data).to_dict()
        if isinstance(data, str):
            return self.parse_hex_string(data).to_dict()
        return self._error(
            b"",
            "INVALID_INPUT_TYPE",
            "Input must be bytes or a hexadecimal string",
            {"input_type": type(data).__name__},
        ).to_dict()

    def parse_hex_string(self, text: str) -> ParseResult:
        """Parse a complete H4 frame supplied as hexadecimal text."""
        if not isinstance(text, str):
            return self._error(
                b"",
                "INVALID_INPUT_TYPE",
                "Hex input must be a string",
                {"input_type": type(text).__name__},
            )
        normalized = re.sub(r"[\s,;:_-]+", "", text.strip())
        normalized = re.sub(r"0[xX]", "", normalized)
        if not normalized:
            return self._error(b"", "EMPTY_INPUT", "Hex input is empty")
        if len(normalized) % 2:
            return self._error(
                b"",
                "INVALID_HEX_STRING",
                "Hex input must contain an even number of digits",
            )
        try:
            data = bytes.fromhex(normalized)
        except ValueError:
            return self._error(
                b"",
                "INVALID_HEX_STRING",
                "Hex input contains a non-hexadecimal character",
            )
        return self.parse_bytes(data)

    def _parse_data_packet(self, data: bytes) -> ParseResult:
        indicator = data[0]
        packet_names = {
            H4PacketIndicator.ACL_DATA: "HCI_ACL_Data",
            H4PacketIndicator.SYNCHRONOUS_DATA: "HCI_Synchronous_Data",
            H4PacketIndicator.ISO_DATA: "HCI_ISO_Data",
        }
        header_lengths = {
            H4PacketIndicator.ACL_DATA: 5,
            H4PacketIndicator.SYNCHRONOUS_DATA: 4,
            H4PacketIndicator.ISO_DATA: 5,
        }
        minimum = header_lengths[H4PacketIndicator(indicator)]
        if len(data) < minimum:
            return self._error(
                data, "TRUNCATED_HEADER", f"{packet_names[indicator]} header is incomplete"
            )
        if indicator == H4PacketIndicator.ACL_DATA:
            payload_length = int.from_bytes(data[3:5], "little")
        elif indicator == H4PacketIndicator.SYNCHRONOUS_DATA:
            payload_length = data[3]
        else:
            payload_length = int.from_bytes(data[3:5], "little") & 0x3FFF
        expected = minimum + payload_length
        if len(data) != expected:
            return self._error(
                data,
                "PACKET_LENGTH_MISMATCH",
                "HCI data packet length does not match the frame",
                {"expected_frame_length": expected, "actual_frame_length": len(data)},
            )
        handle_flags = int.from_bytes(data[1:3], "little")
        return ParseResult(
            True,
            packet_names[indicator],
            data,
            decoded={
                "packet_indicator": f"0x{indicator:02X}",
                "handle_and_flags": f"0x{handle_flags:04X}",
                "payload_length": payload_length,
                "payload_hex": data[minimum:].hex(" ").upper(),
                "detail_decoding": "not implemented",
            },
        )

    @staticmethod
    def _error(
        data: bytes,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> ParseResult:
        return ParseResult(
            False,
            None,
            data,
            error=ParseError(code, message, details or {}),
        )
