"""Generic framing support for RACE packets carried beside HCI H4 traffic."""

from __future__ import annotations

from hci_analyzer.models import ParseError, ParseResult


RACE_HEAD = 0x05
RACE_MIN_LENGTH = 0x0002
RACE_MAX_LENGTH = 0x0200
RACE_HEADER_LENGTH = 4
RACE_COMMAND_ID_LENGTH = 2


def race_frame_length(data: bytes | bytearray, offset: int = 0) -> int | None:
    """Return the total RACE frame length when a valid header is available."""
    if len(data) - offset < RACE_HEADER_LENGTH or data[offset] != RACE_HEAD:
        return None
    body_length = int.from_bytes(data[offset + 2 : offset + 4], "little")
    if not RACE_MIN_LENGTH <= body_length <= RACE_MAX_LENGTH:
        return None
    return RACE_HEADER_LENGTH + body_length


class RaceParser:
    """Decode only the public RACE envelope; payload interpretation is deferred."""

    def parse(self, data: bytes) -> ParseResult:
        """Parse one complete RACE frame."""
        if len(data) < RACE_HEADER_LENGTH:
            return self._error(
                data,
                "TRUNCATED_HEADER",
                "RACE header is incomplete",
            )
        if data[0] != RACE_HEAD:
            return self._error(
                data,
                "INVALID_RACE_HEAD",
                f"RACE Head must be 0x{RACE_HEAD:02X}",
                {"actual_head": f"0x{data[0]:02X}"},
            )

        body_length = int.from_bytes(data[2:4], "little")
        if not RACE_MIN_LENGTH <= body_length <= RACE_MAX_LENGTH:
            return self._error(
                data,
                "RACE_LENGTH_OUT_OF_RANGE",
                "RACE Length is outside the configured range",
                {
                    "length": body_length,
                    "minimum": RACE_MIN_LENGTH,
                    "maximum": RACE_MAX_LENGTH,
                },
            )

        expected_length = RACE_HEADER_LENGTH + body_length
        if len(data) != expected_length:
            return self._error(
                data,
                "PACKET_LENGTH_MISMATCH",
                "RACE Length does not match the frame",
                {
                    "expected_frame_length": expected_length,
                    "actual_frame_length": len(data),
                },
            )

        command_id = int.from_bytes(data[4:6], "little")
        payload = data[6:]
        return ParseResult(
            True,
            "RACE",
            data,
            decoded={
                "protocol": "RACE",
                "head": f"0x{data[0]:02X}",
                "type": data[1],
                "type_hex": f"0x{data[1]:02X}",
                "length": body_length,
                "command_id": command_id,
                "command_id_hex": f"0x{command_id:04X}",
                "payload_length": len(payload),
                "payload_hex": payload.hex(" ").upper(),
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
