"""Definitions of supported LE RF PHY Test commands and events."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CommandDefinition:
    """Static metadata for one supported HCI command version."""

    opcode: int
    name: str
    version: str | None
    fixed_parameter_length: int | None = None


COMMAND_DEFINITIONS: dict[int, CommandDefinition] = {}

