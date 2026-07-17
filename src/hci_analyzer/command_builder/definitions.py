"""Declarative command and parameter definitions for the console UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from hci_analyzer.parser.registry import (
    CTE_TYPE_NAMES,
    MODULATION_INDEX_NAMES,
    PACKET_PAYLOAD_NAMES,
    RECEIVER_PHY_NAMES,
    TRANSMITTER_PHY_NAMES,
)


class ParameterKind(str, Enum):
    """Supported parameter editor types."""

    INTEGER = "integer"
    SIGNED_INTEGER = "signed_integer"
    ENUM = "enum"
    BOOLEAN = "boolean"
    BIT_FIELD = "bit_field"
    BYTE_ARRAY = "byte_array"
    INTEGER_ARRAY = "integer_array"
    HEX_BYTES = "hex_bytes"


class ResponseKind(str, Enum):
    """Expected response flow for a command."""

    COMMAND_COMPLETE = "command_complete"
    COMMAND_STATUS = "command_status"
    COMMAND_STATUS_THEN_EVENT = "command_status_then_event"
    NONE = "none"


@dataclass(slots=True, frozen=True)
class ParameterDefinition:
    """Describe one parameter and the editor used to collect its value."""

    name: str
    label: str
    kind: ParameterKind
    size: int | None = 1
    minimum: int | None = None
    maximum: int | None = None
    default: Any = None
    choices: Mapping[int, str] = field(default_factory=dict)
    description: str = ""
    unit: str | None = None
    length_from: str | None = None
    derived: bool = False
    allowed_values: tuple[int, ...] = ()


@dataclass(slots=True, frozen=True)
class ConsoleCommandDefinition:
    """Describe one selectable command and all of its parameters."""

    opcode: int
    name: str
    version: str | None
    category: str
    parameters: tuple[ParameterDefinition, ...] = ()
    response_kind: ResponseKind = ResponseKind.COMMAND_COMPLETE
    completion_event_code: int | None = None

    @property
    def display_name(self) -> str:
        """Return a version-qualified name for selection controls."""
        if self.version is None:
            return self.name
        return f"{self.name}[{self.version}]"


LE_RF_PHY_TEST = "LE RF PHY Test"
CONTROLLER_AND_BASEBAND = "Controller & Baseband"
INFORMATIONAL_PARAMETERS = "Informational Parameters"

CHANNEL_DEFAULT = 19
DATA_LENGTH_DEFAULT = 37
CTE_LENGTH_VALUES = (0, *range(2, 21))
SLOT_DURATION_NAMES = {0x01: "1 us", 0x02: "2 us"}


def _integer(
    name: str,
    label: str,
    minimum: int,
    maximum: int,
    default: int,
    *,
    description: str = "",
    unit: str | None = None,
    allowed_values: tuple[int, ...] = (),
) -> ParameterDefinition:
    return ParameterDefinition(
        name=name,
        label=label,
        kind=ParameterKind.INTEGER,
        minimum=minimum,
        maximum=maximum,
        default=default,
        description=description,
        unit=unit,
        allowed_values=allowed_values,
    )


def _enum(
    name: str,
    label: str,
    choices: Mapping[int, str],
    default: int,
    *,
    description: str = "",
) -> ParameterDefinition:
    return ParameterDefinition(
        name=name,
        label=label,
        kind=ParameterKind.ENUM,
        default=default,
        choices=choices,
        description=description,
    )


CHANNEL_PARAMETER_RX = _integer(
    "RX_Channel",
    "RX Channel",
    0,
    39,
    CHANNEL_DEFAULT,
    description="N = (F - 2402) / 2",
)
CHANNEL_PARAMETER_TX = _integer(
    "TX_Channel",
    "TX Channel",
    0,
    39,
    CHANNEL_DEFAULT,
    description="N = (F - 2402) / 2",
)
TEST_DATA_LENGTH = _integer(
    "Test_Data_Length", "Test Data Length", 0, 255, DATA_LENGTH_DEFAULT, unit="bytes"
)
PACKET_PAYLOAD = _enum(
    "Packet_Payload", "Packet Payload", PACKET_PAYLOAD_NAMES, 0
)
RX_PHY = _enum("PHY", "PHY", RECEIVER_PHY_NAMES, 1)
TX_PHY = _enum("PHY", "PHY", TRANSMITTER_PHY_NAMES, 1)
MODULATION_INDEX = _enum(
    "Modulation_Index", "Modulation Index", MODULATION_INDEX_NAMES, 0
)
EXPECTED_CTE_LENGTH = _integer(
    "Expected_CTE_Length",
    "Expected CTE Length",
    0,
    20,
    2,
    unit="8 us units",
    allowed_values=CTE_LENGTH_VALUES,
)
CTE_LENGTH = _integer(
    "CTE_Length",
    "CTE Length",
    0,
    20,
    2,
    unit="8 us units",
    allowed_values=CTE_LENGTH_VALUES,
)
EXPECTED_CTE_TYPE = _enum(
    "Expected_CTE_Type", "Expected CTE Type", CTE_TYPE_NAMES, 0
)
CTE_TYPE = _enum("CTE_Type", "CTE Type", CTE_TYPE_NAMES, 1)
SLOT_DURATIONS = _enum(
    "Slot_Durations", "Slot Durations", SLOT_DURATION_NAMES, 1
)
ANTENNA_IDS = ParameterDefinition(
    name="Antenna_IDs",
    label="Antenna IDs",
    kind=ParameterKind.INTEGER_ARRAY,
    minimum=0,
    maximum=255,
    default=(1, 2),
    description="Switching Pattern Length is generated from the item count.",
)
TX_POWER_MODE = _enum(
    "TX_Power_Mode",
    "TX Power Mode",
    {0: "Numeric", 1: "Minimum", 2: "Maximum"},
    0,
)
TX_POWER_LEVEL = ParameterDefinition(
    name="TX_Power_Level",
    label="TX Power",
    kind=ParameterKind.SIGNED_INTEGER,
    minimum=-127,
    maximum=20,
    default=0,
    unit="dBm",
    description="Used only when TX Power Mode is Numeric.",
)


CONSOLE_COMMAND_DEFINITIONS: tuple[ConsoleCommandDefinition, ...] = (
    ConsoleCommandDefinition(
        0x201E,
        "HCI_LE_Transmitter_Test",
        "v1",
        LE_RF_PHY_TEST,
        (CHANNEL_PARAMETER_TX, TEST_DATA_LENGTH, PACKET_PAYLOAD),
    ),
    ConsoleCommandDefinition(
        0x2034,
        "HCI_LE_Transmitter_Test",
        "v2",
        LE_RF_PHY_TEST,
        (CHANNEL_PARAMETER_TX, TEST_DATA_LENGTH, PACKET_PAYLOAD, TX_PHY),
    ),
    ConsoleCommandDefinition(
        0x2050,
        "HCI_LE_Transmitter_Test",
        "v3",
        LE_RF_PHY_TEST,
        (
            CHANNEL_PARAMETER_TX,
            TEST_DATA_LENGTH,
            PACKET_PAYLOAD,
            TX_PHY,
            CTE_LENGTH,
            CTE_TYPE,
            ANTENNA_IDS,
        ),
    ),
    ConsoleCommandDefinition(
        0x207B,
        "HCI_LE_Transmitter_Test",
        "v4",
        LE_RF_PHY_TEST,
        (
            CHANNEL_PARAMETER_TX,
            TEST_DATA_LENGTH,
            PACKET_PAYLOAD,
            TX_PHY,
            CTE_LENGTH,
            CTE_TYPE,
            ANTENNA_IDS,
            TX_POWER_MODE,
            TX_POWER_LEVEL,
        ),
    ),
    ConsoleCommandDefinition(
        0x201D,
        "HCI_LE_Receiver_Test",
        "v1",
        LE_RF_PHY_TEST,
        (CHANNEL_PARAMETER_RX,),
    ),
    ConsoleCommandDefinition(
        0x2033,
        "HCI_LE_Receiver_Test",
        "v2",
        LE_RF_PHY_TEST,
        (CHANNEL_PARAMETER_RX, RX_PHY, MODULATION_INDEX),
    ),
    ConsoleCommandDefinition(
        0x204F,
        "HCI_LE_Receiver_Test",
        "v3",
        LE_RF_PHY_TEST,
        (
            CHANNEL_PARAMETER_RX,
            RX_PHY,
            MODULATION_INDEX,
            EXPECTED_CTE_LENGTH,
            EXPECTED_CTE_TYPE,
            SLOT_DURATIONS,
            ANTENNA_IDS,
        ),
    ),
    ConsoleCommandDefinition(
        0x201F,
        "HCI_LE_Test_End",
        None,
        LE_RF_PHY_TEST,
        (),
    ),
    ConsoleCommandDefinition(
        0x0C03,
        "HCI_Reset",
        None,
        CONTROLLER_AND_BASEBAND,
        (),
    ),
    ConsoleCommandDefinition(
        0x1002,
        "HCI_Read_Local_Supported_Commands",
        "v1",
        INFORMATIONAL_PARAMETERS,
        (),
    ),
    ConsoleCommandDefinition(
        0x1010,
        "HCI_Read_Local_Supported_Commands",
        "v2",
        INFORMATIONAL_PARAMETERS,
        (),
    ),
)

COMMAND_DEFINITIONS_BY_OPCODE = {
    definition.opcode: definition for definition in CONSOLE_COMMAND_DEFINITIONS
}
