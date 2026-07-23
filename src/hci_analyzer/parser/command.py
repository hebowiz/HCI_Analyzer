"""HCI Command packet parser."""

from typing import Any

from hci_analyzer.models import H4PacketIndicator, ParseError, ParseResult
from hci_analyzer.parser.registry import (
    COMMAND_DEFINITIONS,
    CTE_TYPE_NAMES,
    MODULATION_INDEX_NAMES,
    PACKET_PAYLOAD_NAMES,
    RECEIVER_PHY_NAMES,
    TRANSMITTER_PHY_NAMES,
    CommandDefinition,
    command_display_name,
)


class HciCommandParser:
    """Decode supported LE RF PHY Test command packets."""

    def parse(self, frame: bytes) -> ParseResult:
        """Parse one complete H4 HCI Command frame."""
        if len(frame) < 4:
            return self._error(frame, "TRUNCATED_HEADER", "HCI Command header is incomplete")
        if frame[0] != H4PacketIndicator.COMMAND:
            return self._error(frame, "INVALID_INDICATOR", "Packet indicator is not 0x01")

        opcode = int.from_bytes(frame[1:3], "little")
        parameter_total_length = frame[3]
        actual_parameter_length = len(frame) - 4
        common = self._common_fields(opcode, parameter_total_length)

        if actual_parameter_length != parameter_total_length:
            return self._error(
                frame,
                "PACKET_LENGTH_MISMATCH",
                "Parameter_Total_Length does not match the received frame",
                {
                    **common,
                    "expected_frame_length": 4 + parameter_total_length,
                    "actual_frame_length": len(frame),
                    "actual_parameter_length": actual_parameter_length,
                },
            )

        definition = COMMAND_DEFINITIONS.get(opcode)
        if definition is None:
            if common["ogf"] == 0x3F:
                params = frame[4:]
                return ParseResult(
                    True,
                    "HCI_Command",
                    frame,
                    decoded={
                        **common,
                        "command_name": f"Vendor_Specific_Command_0x{opcode:04X}",
                        "display_name": f"Vendor Specific Command 0x{opcode:04X}",
                        "vendor_specific": True,
                        "parameters": {
                            "raw_hex": params.hex(" ").upper(),
                            "raw_bytes": list(params),
                        },
                    },
                )
            return self._error(
                frame,
                "UNKNOWN_OPCODE",
                f"Unsupported HCI command opcode 0x{opcode:04X}",
                common,
            )

        params = frame[4:]
        expected_length = self._expected_parameter_length(definition, params)
        if isinstance(expected_length, ParseError):
            expected_length.details.update(common)
            return ParseResult(False, "HCI_Command", frame, error=expected_length)
        if parameter_total_length != expected_length:
            return self._error(
                frame,
                "PARAMETER_LENGTH_MISMATCH",
                "Command parameter length does not match its definition",
                {
                    **common,
                    "expected_parameter_length": expected_length,
                    "actual_parameter_length": parameter_total_length,
                },
            )

        decoded = {
            **common,
            "command_name": definition.name,
            "version": definition.version,
            "display_name": command_display_name(opcode),
            "parameters": self._decode_parameters(opcode, params),
        }
        return ParseResult(True, "HCI_Command", frame, decoded=decoded)

    @staticmethod
    def _common_fields(opcode: int, parameter_total_length: int) -> dict[str, Any]:
        return {
            "packet_indicator": "0x01",
            "opcode": f"0x{opcode:04X}",
            "opcode_value": opcode,
            "ogf": (opcode >> 10) & 0x3F,
            "ocf": opcode & 0x03FF,
            "parameter_total_length": parameter_total_length,
        }

    @staticmethod
    def _expected_parameter_length(
        definition: CommandDefinition, params: bytes
    ) -> int | ParseError:
        if definition.fixed_parameter_length is not None:
            return definition.fixed_parameter_length

        index = definition.variable_length_field_index
        base = definition.variable_length_base
        if index is None or base is None:
            return ParseError("INVALID_DEFINITION", "Command length definition is incomplete")
        if len(params) <= index:
            return ParseError(
                "MISSING_VARIABLE_LENGTH_FIELD",
                "Variable-length command does not contain its length field",
                {"variable_length_field_index": index},
            )
        return base + params[index]

    def _decode_parameters(self, opcode: int, params: bytes) -> dict[str, Any]:
        if opcode in (0x201D, 0x2033, 0x204F):
            return self._decode_receiver(opcode, params)
        if opcode in (0x201E, 0x2034, 0x2050, 0x207B):
            return self._decode_transmitter(opcode, params)
        return {}

    @staticmethod
    def _channel(value: int, field_name: str) -> dict[str, Any]:
        return {
            field_name: value,
            f"{field_name}_hex": f"0x{value:02X}",
            "frequency_mhz": 2402 + (2 * value),
            "in_defined_range": 0x00 <= value <= 0x27,
        }

    def _decode_receiver(self, opcode: int, params: bytes) -> dict[str, Any]:
        decoded = self._channel(params[0], "rx_channel")
        if opcode == 0x201D:
            return decoded
        decoded.update(
            {
                "phy": params[1],
                "phy_name": RECEIVER_PHY_NAMES.get(params[1], "Reserved/Unknown"),
                "modulation_index": params[2],
                "modulation_index_name": MODULATION_INDEX_NAMES.get(
                    params[2], "Reserved/Unknown"
                ),
            }
        )
        if opcode == 0x204F:
            pattern_length = params[6]
            decoded.update(
                {
                    "expected_cte_length": params[3],
                    "expected_cte_length_us": (
                        None if params[3] == 0 else params[3] * 8
                    ),
                    "expected_cte_type": params[4],
                    "expected_cte_type_name": CTE_TYPE_NAMES.get(
                        params[4], "Reserved/Unknown"
                    ),
                    "slot_durations_us": params[5],
                    "switching_pattern_length": pattern_length,
                    "antenna_ids": list(params[7 : 7 + pattern_length]),
                }
            )
        return decoded

    def _decode_transmitter(self, opcode: int, params: bytes) -> dict[str, Any]:
        decoded = self._channel(params[0], "tx_channel")
        decoded.update(
            {
                "test_data_length": params[1],
                "packet_payload": params[2],
                "packet_payload_name": PACKET_PAYLOAD_NAMES.get(
                    params[2], "Reserved/Unknown"
                ),
            }
        )
        if opcode == 0x201E:
            decoded.update({"phy": 0x01, "phy_name": "LE 1M PHY (implicit)"})
            return decoded

        decoded.update(
            {
                "phy": params[3],
                "phy_name": TRANSMITTER_PHY_NAMES.get(
                    params[3], "Reserved/Unknown"
                ),
            }
        )
        if opcode in (0x2050, 0x207B):
            pattern_length = params[6]
            decoded.update(
                {
                    "cte_length": params[4],
                    "cte_length_us": None if params[4] == 0 else params[4] * 8,
                    "cte_type": params[5],
                    "cte_type_name": CTE_TYPE_NAMES.get(
                        params[5], "Reserved/Unknown"
                    ),
                    "switching_pattern_length": pattern_length,
                    "antenna_ids": list(params[7 : 7 + pattern_length]),
                }
            )
            if opcode == 0x207B:
                tx_power = params[7 + pattern_length]
                decoded.update(
                    {
                        "tx_power_level_raw": tx_power,
                        "tx_power_level": self._decode_tx_power(tx_power),
                    }
                )
        return decoded

    @staticmethod
    def _decode_tx_power(value: int) -> int | str:
        if value == 0x7E:
            return "minimum"
        if value == 0x7F:
            return "maximum"
        return int.from_bytes(bytes([value]), "little", signed=True)

    @staticmethod
    def _error(
        frame: bytes,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ParseResult:
        return ParseResult(
            False,
            "HCI_Command",
            frame,
            error=ParseError(code, message, details or {}),
        )
