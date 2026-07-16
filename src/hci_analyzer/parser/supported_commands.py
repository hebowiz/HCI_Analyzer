"""Decode the HCI Supported Commands bit field."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib.resources import files
from typing import Final, Iterable


PHY_TEST_SCOPES: Final[frozenset[str]] = frozenset(
    {"PHY_TEST_CORE", "PHY_TEST_CS"}
)


@dataclass(slots=True, frozen=True)
class SupportedCommandDefinition:
    """Describe one bit in the Supported Commands response."""

    octet: int
    bit: int
    scope: str
    command: str

    @property
    def key(self) -> str:
        """Return the command name used by the parser and console."""
        return normalize_command_name(self.command)

    def to_dict(self, *, supported: bool) -> dict[str, object]:
        """Return a JSON-compatible support result."""
        return {
            "octet": self.octet,
            "bit": self.bit,
            "scope": self.scope,
            "command": self.command,
            "supported": supported,
            "is_phy_test_command": self.scope in PHY_TEST_SCOPES,
        }


def normalize_command_name(name: str) -> str:
    """Normalize specification-style version names for application lookups."""
    return name.replace(" [v", "[v")


def _load_definitions() -> tuple[SupportedCommandDefinition, ...]:
    resource = files("hci_analyzer.parser").joinpath("supported_commands.csv")
    definitions: list[SupportedCommandDefinition] = []
    with resource.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if "-" in row["octet"] or "-" in row["bit"]:
                continue
            definitions.append(
                SupportedCommandDefinition(
                    octet=int(row["octet"]),
                    bit=int(row["bit"]),
                    scope=row["scope"],
                    command=row["command"],
                )
            )
    return tuple(definitions)


SUPPORTED_COMMAND_DEFINITIONS: Final[tuple[SupportedCommandDefinition, ...]] = (
    _load_definitions()
)
SUPPORTED_COMMANDS_BY_POSITION: Final[
    dict[tuple[int, int], SupportedCommandDefinition]
] = {
    (definition.octet, definition.bit): definition
    for definition in SUPPORTED_COMMAND_DEFINITIONS
}
SUPPORTED_COMMANDS_BY_NAME: Final[dict[str, SupportedCommandDefinition]] = {
    definition.key: definition
    for definition in SUPPORTED_COMMAND_DEFINITIONS
    if definition.command.startswith("HCI_")
}


def is_supported(data: bytes, octet: int, bit: int) -> bool:
    """Return whether a Supported Commands bit is set."""
    return octet < len(data) and bool(data[octet] & (1 << bit))


def support_for_commands(
    data: bytes, command_names: Iterable[str]
) -> dict[str, bool]:
    """Return support flags for selected application command names."""
    result: dict[str, bool] = {}
    for name in command_names:
        normalized = normalize_command_name(name)
        definition = SUPPORTED_COMMANDS_BY_NAME.get(normalized)
        result[normalized] = (
            is_supported(data, definition.octet, definition.bit)
            if definition is not None
            else normalized == "HCI_Read_Local_Supported_Commands[v1]"
        )
    return result


def decode_supported_commands(data: bytes) -> dict[str, object]:
    """Classify every set bit and summarize command support by scope."""
    entries: list[dict[str, object]] = []
    by_scope: dict[str, list[str]] = {}

    for octet, octet_value in enumerate(data):
        if octet_value == 0:
            continue
        for bit in range(8):
            if not octet_value & (1 << bit):
                continue
            definition = SUPPORTED_COMMANDS_BY_POSITION.get((octet, bit))
            if definition is None:
                scope = "RESERVED" if octet >= 50 else "OTHER_STANDARD"
                command = "Reserved for future use" if octet >= 50 else "Unknown"
                entry = {
                    "octet": octet,
                    "bit": bit,
                    "scope": scope,
                    "command": command,
                    "supported": True,
                    "is_phy_test_command": False,
                }
            else:
                scope = definition.scope
                command = definition.command
                entry = definition.to_dict(supported=True)
            entries.append(entry)
            by_scope.setdefault(scope, []).append(command)

    application_names = (
        "HCI_LE_CS_Test",
        "HCI_LE_CS_Test_End",
        "HCI_LE_Receiver_Test[v1]",
        "HCI_LE_Transmitter_Test[v1]",
        "HCI_LE_Test_End",
        "HCI_LE_Receiver_Test[v2]",
        "HCI_LE_Transmitter_Test[v2]",
        "HCI_LE_Receiver_Test[v3]",
        "HCI_LE_Transmitter_Test[v3]",
        "HCI_LE_Transmitter_Test[v4]",
        "HCI_Read_Local_Supported_Commands[v1]",
        "HCI_Read_Local_Supported_Commands[v2]",
    )
    return {
        "set_bit_count": len(entries),
        "supported_commands_by_scope": by_scope,
        "supported_command_entries": entries,
        "application_command_support": support_for_commands(
            data, application_names
        ),
    }
