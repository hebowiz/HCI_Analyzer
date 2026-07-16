"""Encode validated parameter values into UART HCI Command packets."""

from dataclasses import dataclass
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import ConsoleCommandDefinition
from hci_analyzer.command_builder.validation import CommandValidator
from hci_analyzer.parser.facade import HciParser


@dataclass(slots=True, frozen=True)
class EncodedCommand:
    """One encoded H4 command ready for serial transmission."""

    definition: ConsoleCommandDefinition
    parameter_values: Mapping[str, Any]
    parameters: bytes
    frame: bytes


class HciCommandEncoder:
    """Build H4 command packets from declarative command definitions."""

    def __init__(
        self,
        validator: CommandValidator | None = None,
        parser: HciParser | None = None,
    ) -> None:
        self._validator = validator or CommandValidator()
        self._parser = parser or HciParser()

    def encode(
        self,
        definition: ConsoleCommandDefinition,
        parameter_values: Mapping[str, Any],
    ) -> EncodedCommand:
        """Validate and encode one selected command."""
        validation = self._validator.validate(definition, parameter_values)
        if not validation.valid:
            messages = "; ".join(issue.message for issue in validation.issues)
            raise ValueError(messages)

        values = validation.normalized_values
        parameters = self._encode_parameters(definition.opcode, values)
        if len(parameters) > 0xFF:
            raise ValueError("Parameter Total Length exceeds 255 octets")
        frame = (
            b"\x01"
            + definition.opcode.to_bytes(2, "little")
            + bytes([len(parameters)])
            + parameters
        )
        parsed = self._parser.parse_bytes(frame)
        if not parsed.success:
            message = parsed.error.message if parsed.error else "Parser rejected frame"
            raise ValueError(f"Encoded command self-check failed: {message}")
        return EncodedCommand(definition, dict(values), parameters, frame)

    @staticmethod
    def _encode_parameters(opcode: int, values: Mapping[str, Any]) -> bytes:
        if opcode == 0x201D:
            return bytes([values["RX_Channel"]])
        if opcode == 0x2033:
            return bytes(
                [
                    values["RX_Channel"],
                    values["PHY"],
                    values["Modulation_Index"],
                ]
            )
        if opcode == 0x204F:
            antennas = bytes(values["Antenna_IDs"])
            return bytes(
                [
                    values["RX_Channel"],
                    values["PHY"],
                    values["Modulation_Index"],
                    values["Expected_CTE_Length"],
                    values["Expected_CTE_Type"],
                    values["Slot_Durations"],
                    len(antennas),
                ]
            ) + antennas
        if opcode == 0x201E:
            return bytes(
                [
                    values["TX_Channel"],
                    values["Test_Data_Length"],
                    values["Packet_Payload"],
                ]
            )
        if opcode == 0x2034:
            return bytes(
                [
                    values["TX_Channel"],
                    values["Test_Data_Length"],
                    values["Packet_Payload"],
                    values["PHY"],
                ]
            )
        if opcode in (0x2050, 0x207B):
            antennas = bytes(values["Antenna_IDs"])
            parameters = bytes(
                [
                    values["TX_Channel"],
                    values["Test_Data_Length"],
                    values["Packet_Payload"],
                    values["PHY"],
                    values["CTE_Length"],
                    values["CTE_Type"],
                    len(antennas),
                ]
            ) + antennas
            if opcode == 0x207B:
                power = values["TX_Power_Level"]
                if power not in (0x7E, 0x7F):
                    power &= 0xFF
                parameters += bytes([power])
            return parameters
        if opcode in (0x201F, 0x1002, 0x1010):
            return b""
        raise ValueError(f"Unsupported command opcode 0x{opcode:04X}")
