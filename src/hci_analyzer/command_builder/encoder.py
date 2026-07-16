"""Encode validated parameter values into UART HCI Command packets."""

from dataclasses import dataclass
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import ConsoleCommandDefinition


@dataclass(slots=True, frozen=True)
class EncodedCommand:
    """One encoded H4 command ready for serial transmission."""

    definition: ConsoleCommandDefinition
    parameter_values: Mapping[str, Any]
    parameters: bytes
    frame: bytes


class HciCommandEncoder:
    """Build H4 command packets from declarative command definitions."""

    def encode(
        self,
        definition: ConsoleCommandDefinition,
        parameter_values: Mapping[str, Any],
    ) -> EncodedCommand:
        """Validate and encode one selected command."""
        raise NotImplementedError

