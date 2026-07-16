"""Declarative command and parameter definitions for the console UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


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
    description: str = ""

    @property
    def display_name(self) -> str:
        """Return a version-qualified name for selection controls."""
        if self.version is None:
            return self.name
        return f"{self.name}[{self.version}]"


# Detailed command schemas will be populated during the implementation phase.
CONSOLE_COMMAND_DEFINITIONS: tuple[ConsoleCommandDefinition, ...] = ()

