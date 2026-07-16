"""Definitions and display mappings for supported LE RF PHY tests."""

from dataclasses import dataclass
from typing import Final


@dataclass(slots=True, frozen=True)
class CommandDefinition:
    """Static metadata for one supported HCI command version."""

    opcode: int
    name: str
    version: str | None
    fixed_parameter_length: int | None = None
    variable_length_field_index: int | None = None
    variable_length_base: int | None = None


COMMAND_DEFINITIONS: Final[dict[int, CommandDefinition]] = {
    0x201D: CommandDefinition(0x201D, "HCI_LE_Receiver_Test", "v1", 1),
    0x2033: CommandDefinition(0x2033, "HCI_LE_Receiver_Test", "v2", 3),
    0x204F: CommandDefinition(
        0x204F,
        "HCI_LE_Receiver_Test",
        "v3",
        variable_length_field_index=6,
        variable_length_base=7,
    ),
    0x201E: CommandDefinition(0x201E, "HCI_LE_Transmitter_Test", "v1", 3),
    0x2034: CommandDefinition(0x2034, "HCI_LE_Transmitter_Test", "v2", 4),
    0x2050: CommandDefinition(
        0x2050,
        "HCI_LE_Transmitter_Test",
        "v3",
        variable_length_field_index=6,
        variable_length_base=7,
    ),
    0x207B: CommandDefinition(
        0x207B,
        "HCI_LE_Transmitter_Test",
        "v4",
        variable_length_field_index=6,
        variable_length_base=8,
    ),
    0x201F: CommandDefinition(0x201F, "HCI_LE_Test_End", None, 0),
}

RECEIVER_PHY_NAMES: Final[dict[int, str]] = {
    0x01: "LE 1M PHY",
    0x02: "LE 2M PHY",
    0x03: "LE Coded PHY",
}

TRANSMITTER_PHY_NAMES: Final[dict[int, str]] = {
    0x01: "LE 1M PHY",
    0x02: "LE 2M PHY",
    0x03: "LE Coded PHY with S=8",
    0x04: "LE Coded PHY with S=2",
}

PACKET_PAYLOAD_NAMES: Final[dict[int, str]] = {
    0x00: "PRBS9",
    0x01: "repeated 11110000",
    0x02: "repeated 10101010",
    0x03: "PRBS15",
    0x04: "repeated 11111111",
    0x05: "repeated 00000000",
    0x06: "repeated 00001111",
    0x07: "repeated 01010101",
}

MODULATION_INDEX_NAMES: Final[dict[int, str]] = {
    0x00: "standard modulation index",
    0x01: "stable modulation index",
}

CTE_TYPE_NAMES: Final[dict[int, str]] = {
    0x00: "AoA CTE",
    0x01: "AoD CTE with 1 us slots",
    0x02: "AoD CTE with 2 us slots",
}

EVENT_NAMES: Final[dict[int, str]] = {
    0x0E: "HCI_Command_Complete",
    0x0F: "HCI_Command_Status",
    0x3E: "HCI_LE_Meta_Event",
}

LE_META_EVENT_NAMES: Final[dict[int, str]] = {
    0x15: "HCI_LE_Connectionless_IQ_Report",
    0x31: "HCI_LE_CS_Subevent_Result",
    0x32: "HCI_LE_CS_Subevent_Result_Continue",
    0x33: "HCI_LE_CS_Test_End_Complete",
}


def command_display_name(opcode: int) -> str | None:
    """Return the version-qualified command name for an opcode."""
    definition = COMMAND_DEFINITIONS.get(opcode)
    if definition is None:
        return None
    if definition.version is None:
        return definition.name
    return f"{definition.name}[{definition.version}]"
