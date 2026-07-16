"""HCI Event packet parser."""

from typing import Any

from hci_analyzer.models import H4PacketIndicator, ParseError, ParseResult
from hci_analyzer.parser.registry import (
    COMMAND_COMPLETE_RETURN_LENGTHS,
    COMMAND_DEFINITIONS,
    EVENT_NAMES,
    LE_META_EVENT_NAMES,
    command_display_name,
    decode_supported_command_bits,
)


class HciEventParser:
    """Decode HCI events related to LE RF PHY tests."""

    def parse(self, frame: bytes) -> ParseResult:
        """Parse one complete H4 HCI Event frame."""
        if len(frame) < 3:
            return self._error(frame, "TRUNCATED_HEADER", "HCI Event header is incomplete")
        if frame[0] != H4PacketIndicator.EVENT:
            return self._error(frame, "INVALID_INDICATOR", "Packet indicator is not 0x04")

        event_code = frame[1]
        parameter_total_length = frame[2]
        actual_parameter_length = len(frame) - 3
        common = {
            "packet_indicator": "0x04",
            "event_code": f"0x{event_code:02X}",
            "event_code_value": event_code,
            "event_name": EVENT_NAMES.get(event_code, "Unknown HCI Event"),
            "parameter_total_length": parameter_total_length,
        }
        if actual_parameter_length != parameter_total_length:
            return self._error(
                frame,
                "PACKET_LENGTH_MISMATCH",
                "Event parameter length does not match the received frame",
                {
                    **common,
                    "expected_frame_length": 3 + parameter_total_length,
                    "actual_frame_length": len(frame),
                    "actual_parameter_length": actual_parameter_length,
                },
            )

        params = frame[3:]
        if event_code == 0x0E:
            return self._parse_command_complete(frame, common, params)
        if event_code == 0x0F:
            return self._parse_command_status(frame, common, params)
        if event_code == 0x3E:
            return self._parse_le_meta_event(frame, common, params)

        return ParseResult(
            True,
            "HCI_Event",
            frame,
            decoded={**common, "parameters_hex": params.hex(" ").upper()},
        )

    def _parse_command_complete(
        self, frame: bytes, common: dict[str, Any], params: bytes
    ) -> ParseResult:
        if len(params) < 3:
            return self._error(
                frame,
                "TRUNCATED_COMMAND_COMPLETE",
                "HCI_Command_Complete requires at least 3 parameters",
                common,
            )
        opcode = int.from_bytes(params[1:3], "little")
        definition = COMMAND_DEFINITIONS.get(opcode)
        if definition is None:
            return self._unknown_opcode(frame, common, opcode)

        return_params = params[3:]
        expected_return_length = COMMAND_COMPLETE_RETURN_LENGTHS.get(opcode, 1)
        if len(return_params) != expected_return_length:
            return self._error(
                frame,
                "RETURN_PARAMETER_LENGTH_MISMATCH",
                "Command Complete return parameter length is invalid",
                {
                    **common,
                    "opcode": f"0x{opcode:04X}",
                    "expected_return_parameter_length": expected_return_length,
                    "actual_return_parameter_length": len(return_params),
                },
            )

        status = return_params[0]
        decoded: dict[str, Any] = {
            **common,
            "num_hci_command_packets": params[0],
            "command_opcode": f"0x{opcode:04X}",
            "command_opcode_value": opcode,
            "command_name": command_display_name(opcode),
            "status": status,
            "status_hex": f"0x{status:02X}",
            "status_name": "command succeeded" if status == 0 else "command failed",
        }
        if opcode == 0x201F:
            decoded["rf_test_event"] = "LE_Packet_Report"
            decoded["num_packets"] = int.from_bytes(return_params[1:3], "little")
        elif opcode in (0x1002, 0x1010):
            supported_commands = return_params[1:]
            decoded.update(
                {
                    "response_type": "Supported_Commands",
                    "supported_commands_length": len(supported_commands),
                    "supported_commands_hex": supported_commands.hex(" ").upper(),
                    "supported_commands": list(supported_commands),
                    "relevant_command_support": decode_supported_command_bits(
                        supported_commands
                    ),
                }
            )
        else:
            decoded["rf_test_event"] = "LE_Status"
        return ParseResult(True, "HCI_Event", frame, decoded=decoded)

    def _parse_command_status(
        self, frame: bytes, common: dict[str, Any], params: bytes
    ) -> ParseResult:
        if len(params) != 4:
            return self._error(
                frame,
                "COMMAND_STATUS_LENGTH_MISMATCH",
                "HCI_Command_Status requires exactly 4 parameters",
                {**common, "actual_parameter_length": len(params)},
            )
        opcode = int.from_bytes(params[2:4], "little")
        if opcode not in COMMAND_DEFINITIONS:
            return self._unknown_opcode(frame, common, opcode)
        status = params[0]
        return ParseResult(
            True,
            "HCI_Event",
            frame,
            decoded={
                **common,
                "status": status,
                "status_hex": f"0x{status:02X}",
                "status_name": "command succeeded" if status == 0 else "command failed",
                "num_hci_command_packets": params[1],
                "command_opcode": f"0x{opcode:04X}",
                "command_opcode_value": opcode,
                "command_name": command_display_name(opcode),
            },
        )

    def _parse_le_meta_event(
        self, frame: bytes, common: dict[str, Any], params: bytes
    ) -> ParseResult:
        if not params:
            return self._error(
                frame,
                "MISSING_SUBEVENT_CODE",
                "HCI LE Meta Event does not contain a subevent code",
                common,
            )
        subevent_code = params[0]
        subevent_params = params[1:]
        decoded: dict[str, Any] = {
            **common,
            "subevent_code": f"0x{subevent_code:02X}",
            "subevent_code_value": subevent_code,
            "subevent_name": LE_META_EVENT_NAMES.get(
                subevent_code, "Unknown LE Meta Event"
            ),
        }
        if subevent_code == 0x15:
            iq_result = self._decode_connectionless_iq_report(subevent_params)
            if isinstance(iq_result, ParseError):
                iq_result.details.update(decoded)
                return ParseResult(False, "HCI_Event", frame, error=iq_result)
            decoded["parameters"] = iq_result
        else:
            decoded["subevent_parameters_hex"] = subevent_params.hex(" ").upper()
        return ParseResult(True, "HCI_Event", frame, decoded=decoded)

    @staticmethod
    def _decode_connectionless_iq_report(
        params: bytes,
    ) -> dict[str, Any] | ParseError:
        if len(params) < 12:
            return ParseError(
                "TRUNCATED_IQ_REPORT",
                "Connectionless IQ Report fixed parameters are incomplete",
                {"minimum_length": 12, "actual_length": len(params)},
            )
        sample_count = params[11]
        expected_length = 12 + (sample_count * 2)
        if len(params) != expected_length:
            return ParseError(
                "IQ_SAMPLE_LENGTH_MISMATCH",
                "IQ sample count does not match the event length",
                {
                    "sample_count": sample_count,
                    "expected_length": expected_length,
                    "actual_length": len(params),
                },
            )
        sample_bytes = params[12:]
        samples = [
            {
                "i": int.from_bytes(sample_bytes[index : index + 1], "little", signed=True),
                "q": int.from_bytes(
                    sample_bytes[index + 1 : index + 2], "little", signed=True
                ),
            }
            for index in range(0, len(sample_bytes), 2)
        ]
        rssi_raw = int.from_bytes(params[3:5], "little", signed=True)
        return {
            "sync_handle": int.from_bytes(params[0:2], "little"),
            "channel_index": params[2],
            "rssi_raw": rssi_raw,
            "rssi_dbm": rssi_raw / 10,
            "rssi_antenna_id": params[5],
            "cte_type": params[6],
            "slot_durations_us": params[7],
            "packet_status": params[8],
            "event_counter": int.from_bytes(params[9:11], "little"),
            "sample_count": sample_count,
            "samples": samples,
        }

    def _unknown_opcode(
        self, frame: bytes, common: dict[str, Any], opcode: int
    ) -> ParseResult:
        return self._error(
            frame,
            "UNKNOWN_OPCODE",
            f"Event refers to unsupported HCI command opcode 0x{opcode:04X}",
            {**common, "command_opcode": f"0x{opcode:04X}"},
        )

    @staticmethod
    def _error(
        frame: bytes,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ParseResult:
        return ParseResult(
            False,
            "HCI_Event",
            frame,
            error=ParseError(code, message, details or {}),
        )
