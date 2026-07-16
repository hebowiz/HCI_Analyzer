"""Validate values entered in generated command parameter forms."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import ConsoleCommandDefinition


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """One field-level or command-level validation issue."""

    code: str
    message: str
    parameter_name: str | None = None


@dataclass(slots=True)
class ValidationResult:
    """Result of validating one command form."""

    valid: bool
    normalized_values: dict[str, Any] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)


class CommandValidator:
    """Validate and normalize values using a command definition."""

    def validate(
        self,
        definition: ConsoleCommandDefinition,
        parameter_values: Mapping[str, Any],
    ) -> ValidationResult:
        """Validate all parameters for one command."""
        raise NotImplementedError

