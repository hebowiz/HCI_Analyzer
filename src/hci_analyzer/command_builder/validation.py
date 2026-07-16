"""Validate values entered in generated command parameter forms."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import ConsoleCommandDefinition
from hci_analyzer.command_builder.definitions import ParameterDefinition, ParameterKind


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
        normalized: dict[str, Any] = {}
        issues: list[ValidationIssue] = []

        for parameter in definition.parameters:
            if (
                definition.opcode == 0x207B
                and parameter.name == "TX_Power_Level"
                and normalized.get("TX_Power_Mode") in (1, 2)
            ):
                continue
            value = parameter_values.get(parameter.name, parameter.default)
            if parameter.kind == ParameterKind.INTEGER_ARRAY:
                self._validate_array(parameter, value, normalized, issues)
            else:
                self._validate_scalar(parameter, value, normalized, issues)

        if definition.opcode == 0x207B:
            mode = normalized.get("TX_Power_Mode")
            if mode in (1, 2):
                normalized["TX_Power_Level"] = 0x7E if mode == 1 else 0x7F

        parameter_length = self._parameter_length(definition, normalized)
        if parameter_length > 0xFF:
            issues.append(
                ValidationIssue(
                    "PARAMETER_TOTAL_LENGTH_OVERFLOW",
                    "Parameter Total Length exceeds 255 octets.",
                )
            )
        return ValidationResult(not issues, normalized, issues)

    def _validate_scalar(
        self,
        parameter: ParameterDefinition,
        value: Any,
        normalized: dict[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        try:
            number = self._parse_integer(value)
        except (TypeError, ValueError):
            issues.append(
                ValidationIssue(
                    "INVALID_INTEGER",
                    f"{parameter.label} must be an integer.",
                    parameter.name,
                )
            )
            return

        if parameter.choices and number not in parameter.choices:
            issues.append(
                ValidationIssue(
                    "INVALID_ENUM",
                    f"{parameter.label} has an unsupported value.",
                    parameter.name,
                )
            )
            return
        if parameter.minimum is not None and number < parameter.minimum:
            issues.append(self._range_issue(parameter))
            return
        if parameter.maximum is not None and number > parameter.maximum:
            issues.append(self._range_issue(parameter))
            return
        if parameter.allowed_values and number not in parameter.allowed_values:
            issues.append(
                ValidationIssue(
                    "OUT_OF_RANGE",
                    f"{parameter.label} must be 0 or between 2 and 20.",
                    parameter.name,
                )
            )
            return
        normalized[parameter.name] = number

    def _validate_array(
        self,
        parameter: ParameterDefinition,
        value: Any,
        normalized: dict[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        if isinstance(value, str):
            values: list[Any] = [
                item.strip() for item in value.replace(";", ",").split(",") if item.strip()
            ]
        elif isinstance(value, (list, tuple)):
            values = list(value)
        else:
            issues.append(
                ValidationIssue(
                    "INVALID_ARRAY_ITEM",
                    f"{parameter.label} must be a list of integers.",
                    parameter.name,
                )
            )
            return

        if not 2 <= len(values) <= 75:
            issues.append(
                ValidationIssue(
                    "ARRAY_LENGTH",
                    f"{parameter.label} must contain between 2 and 75 items.",
                    parameter.name,
                )
            )
            return

        parsed: list[int] = []
        for item in values:
            try:
                number = self._parse_integer(item)
            except (TypeError, ValueError):
                issues.append(
                    ValidationIssue(
                        "INVALID_ARRAY_ITEM",
                        f"{parameter.label} contains a non-integer value.",
                        parameter.name,
                    )
                )
                return
            if not 0 <= number <= 0xFF:
                issues.append(
                    ValidationIssue(
                        "INVALID_ARRAY_ITEM",
                        f"{parameter.label} items must be between 0 and 255.",
                        parameter.name,
                    )
                )
                return
            parsed.append(number)
        normalized[parameter.name] = parsed

    @staticmethod
    def _parse_integer(value: Any) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            text = value.strip()
            return int(text, 16) if text.lower().startswith("0x") else int(text, 10)
        raise TypeError

    @staticmethod
    def _range_issue(parameter: ParameterDefinition) -> ValidationIssue:
        return ValidationIssue(
            "OUT_OF_RANGE",
            f"{parameter.label} must be between {parameter.minimum} and "
            f"{parameter.maximum}.",
            parameter.name,
        )

    @staticmethod
    def _parameter_length(
        definition: ConsoleCommandDefinition, values: Mapping[str, Any]
    ) -> int:
        if definition.opcode == 0x201D:
            return 1
        if definition.opcode == 0x2033:
            return 3
        if definition.opcode == 0x204F:
            return 7 + len(values.get("Antenna_IDs", []))
        if definition.opcode == 0x201E:
            return 3
        if definition.opcode == 0x2034:
            return 4
        if definition.opcode == 0x2050:
            return 7 + len(values.get("Antenna_IDs", []))
        if definition.opcode == 0x207B:
            return 8 + len(values.get("Antenna_IDs", []))
        return 0
