"""Load reviewed vendor command definitions for HCI Command Console."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import (
    VENDOR_SPECIFIC,
    ConsoleCommandDefinition,
    ParameterDefinition,
    ParameterKind,
    ResponseKind,
)


SUPPORTED_FIELD_TYPES = {
    "uint8": (1, False, "little"),
    "int8": (1, True, "little"),
    "uint16_le": (2, False, "little"),
    "int16_le": (2, True, "little"),
    "uint16_be": (2, False, "big"),
    "int16_be": (2, True, "big"),
    "uint32_le": (4, False, "little"),
    "int32_le": (4, True, "little"),
    "uint32_be": (4, False, "big"),
    "int32_be": (4, True, "big"),
    "uint48_le": (6, False, "little"),
    "int48_le": (6, True, "little"),
    "uint48_be": (6, False, "big"),
    "int48_be": (6, True, "big"),
    "enum_u8": (1, False, "little"),
    "enum_u16_le": (2, False, "little"),
    "enum_u16_be": (2, False, "big"),
    "enum_u24_le": (3, False, "little"),
    "enum_u24_be": (3, False, "big"),
    "enum_u32_le": (4, False, "little"),
    "enum_u32_be": (4, False, "big"),
}
@dataclass(slots=True, frozen=True)
class LoadedVendorDefinitions:
    """Validated external definitions and their review state."""

    definitions: tuple[ConsoleCommandDefinition, ...]
    review_required: bool
    source_path: Path


def load_vendor_console_definitions(path: Path) -> LoadedVendorDefinitions:
    """Load and validate one Vendor Discovery JSON definition file."""
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read definition file: {type(exc).__name__}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Definition file contains invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Definition root must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("Only vendor definition schema_version 1 is supported")
    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("Definition must contain a non-empty commands array")

    root_review_required = payload.get("review_required") is True
    definitions: list[ConsoleCommandDefinition] = []
    seen_selection_keys: set[tuple[str, str | None]] = set()
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            raise ValueError(f"commands[{index}] must be an object")
        definition = _load_command(
            command,
            path,
            root_review_required,
            index,
        )
        selection_key = (definition.name, definition.version)
        if selection_key in seen_selection_keys:
            raise ValueError(
                "Duplicate command selection name: "
                f"{definition.display_name}"
            )
        seen_selection_keys.add(selection_key)
        definitions.append(definition)
    return LoadedVendorDefinitions(
        definitions=tuple(definitions),
        review_required=any(item.review_required for item in definitions),
        source_path=path,
    )


def encode_vendor_parameters(
    definition: ConsoleCommandDefinition,
    values: Mapping[str, Any],
) -> bytes:
    """Encode fields over a captured parameter template."""
    if not definition.vendor_specific or definition.parameter_template is None:
        raise ValueError("Vendor definition does not contain a parameter template")
    encoded = bytearray(definition.parameter_template)
    for parameter in definition.parameters:
        offset = parameter.byte_offset
        encoding_type = parameter.encoding_type
        if offset is None or encoding_type not in SUPPORTED_FIELD_TYPES:
            raise ValueError(f"{parameter.label} has no supported byte encoding")
        size, signed, byte_order = SUPPORTED_FIELD_TYPES[encoding_type]
        try:
            raw = int(values[parameter.name]).to_bytes(
                size,
                byte_order,
                signed=signed,
            )
        except (KeyError, OverflowError, ValueError) as exc:
            raise ValueError(f"{parameter.label} cannot be encoded") from exc
        encoded[offset : offset + size] = raw
    return bytes(encoded)


def decode_vendor_parameters(
    definition: ConsoleCommandDefinition,
    data: bytes,
) -> dict[str, Any]:
    """Decode reviewed fields while preserving the complete parameter RAW."""
    decoded: dict[str, Any] = {
        "raw_hex": data.hex(" ").upper(),
        "raw_bytes": list(data),
    }
    for parameter in definition.parameters:
        offset = parameter.byte_offset
        encoding_type = parameter.encoding_type
        if offset is None or encoding_type not in SUPPORTED_FIELD_TYPES:
            continue
        size, signed, byte_order = SUPPORTED_FIELD_TYPES[encoding_type]
        if offset + size > len(data):
            continue
        value = int.from_bytes(
            data[offset : offset + size],
            byte_order,
            signed=signed,
        )
        decoded[parameter.name] = _display_number(
            value,
            size,
            parameter.number_format,
        )
        if parameter.choices and value in parameter.choices:
            decoded[f"{parameter.name}_name"] = parameter.choices[value]
    return decoded


def _load_command(
    command: dict[str, Any],
    path: Path,
    root_review_required: bool,
    index: int,
) -> ConsoleCommandDefinition:
    opcode = _parse_opcode(command.get("opcode"), index)
    if ((opcode >> 10) & 0x3F) != 0x3F:
        raise ValueError(f"commands[{index}] opcode is not Vendor Specific")
    name = command.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"commands[{index}] name is required")
    raw_version = command.get("version")
    if raw_version is None:
        version = None
    elif isinstance(raw_version, str) and raw_version.strip():
        version = raw_version.strip()
    else:
        raise ValueError(f"commands[{index}].version must be a non-empty string")
    parameter_length = command.get("parameter_length")
    if (
        not isinstance(parameter_length, int)
        or isinstance(parameter_length, bool)
        or not 0 <= parameter_length <= 0xFF
    ):
        raise ValueError(
            f"commands[{index}] parameter_length must be between 0 and 255"
        )
    template = _parse_template(
        command.get("parameter_template_hex"),
        parameter_length,
        index,
    )
    raw_parameters = command.get("parameters", [])
    if not isinstance(raw_parameters, list):
        raise ValueError(f"commands[{index}] parameters must be an array")

    parameters: list[ParameterDefinition] = []
    occupied: dict[int, str] = {}
    parameter_names: set[str] = set()
    for parameter_index, item in enumerate(raw_parameters):
        parameter = _load_parameter(
            item,
            command_index=index,
            parameter_index=parameter_index,
            parameter_length=parameter_length,
            template=template,
        )
        assert parameter.byte_offset is not None
        assert parameter.encoding_type is not None
        if parameter.name in parameter_names:
            raise ValueError(
                f"commands[{index}] contains duplicate parameter name "
                f"{parameter.name}"
            )
        parameter_names.add(parameter.name)
        size = SUPPORTED_FIELD_TYPES[parameter.encoding_type][0]
        for byte_index in range(parameter.byte_offset, parameter.byte_offset + size):
            if byte_index in occupied:
                raise ValueError(
                    f"commands[{index}] parameters {occupied[byte_index]} and "
                    f"{parameter.name} overlap at byte {byte_index}"
                )
            occupied[byte_index] = parameter.name
        parameters.append(parameter)

    response = command.get("response", {})
    response_kind = _response_kind(response)
    review_required = (
        root_review_required
        or command.get("review_required") is True
        or any(
            isinstance(item, dict) and item.get("review_required") is True
            for item in raw_parameters
        )
    )
    return ConsoleCommandDefinition(
        opcode=opcode,
        name=name.strip(),
        version=version,
        category=VENDOR_SPECIFIC,
        parameters=tuple(parameters),
        response_kind=response_kind,
        vendor_specific=True,
        parameter_template=template,
        review_required=review_required,
        external_source=str(path),
    )


def _load_parameter(
    item: Any,
    *,
    command_index: int,
    parameter_index: int,
    parameter_length: int,
    template: bytes,
) -> ParameterDefinition:
    location = f"commands[{command_index}].parameters[{parameter_index}]"
    if not isinstance(item, dict):
        raise ValueError(f"{location} must be an object")
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{location}.name is required")
    offset = item.get("offset")
    if not isinstance(offset, int) or isinstance(offset, bool):
        raise ValueError(f"{location}.offset must be an integer")
    encoding_type = item.get("type")
    if encoding_type not in SUPPORTED_FIELD_TYPES:
        raise ValueError(f"{location}.type is unsupported: {encoding_type}")
    size, signed, byte_order = SUPPORTED_FIELD_TYPES[encoding_type]
    if offset < 0 or offset + size > parameter_length:
        raise ValueError(f"{location} exceeds the parameter template")

    minimum, maximum = _integer_range(size, signed)
    choices = _parse_choices(item.get("choices"), location)
    if any(not minimum <= choice <= maximum for choice in choices):
        raise ValueError(f"{location}.choices contains a value outside the type range")
    kind = ParameterKind.ENUM if choices else (
        ParameterKind.SIGNED_INTEGER if signed else ParameterKind.INTEGER
    )
    raw_default = item.get("default")
    if raw_default is None:
        default = int.from_bytes(
            template[offset : offset + size],
            byte_order,
            signed=signed,
        )
    else:
        try:
            default = _parse_integer_value(raw_default)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location}.default must be an integer, decimal string, "
                "or hexadecimal string"
            ) from exc
    if not minimum <= default <= maximum:
        raise ValueError(f"{location}.default is outside the type range")
    if choices and default not in choices:
        raise ValueError(f"{location}.default is not present in choices")
    label = item.get("label", name)
    if not isinstance(label, str) or not label.strip():
        label = name
    unit = item.get("unit")
    if not isinstance(unit, str):
        unit = None
    number_format = item.get("number_format", "decimal")
    if number_format not in ("decimal", "hex"):
        raise ValueError(
            f"{location}.number_format must be decimal or hex"
        )
    return ParameterDefinition(
        name=name.strip(),
        label=label.strip(),
        kind=kind,
        size=size,
        minimum=minimum,
        maximum=maximum,
        default=default,
        choices=choices,
        unit=unit,
        byte_offset=offset,
        encoding_type=encoding_type,
        number_format=number_format,
    )


def _parse_opcode(value: Any, command_index: int) -> int:
    try:
        opcode = int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"commands[{command_index}] opcode is invalid") from exc
    if not 0 <= opcode <= 0xFFFF:
        raise ValueError(f"commands[{command_index}] opcode is outside 16 bits")
    return opcode


def _parse_template(value: Any, length: int, command_index: int) -> bytes:
    if not isinstance(value, str):
        raise ValueError(
            f"commands[{command_index}] parameter_template_hex is required"
        )
    try:
        template = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(
            f"commands[{command_index}] parameter_template_hex is invalid"
        ) from exc
    if len(template) != length:
        raise ValueError(
            f"commands[{command_index}] template length does not match "
            "parameter_length"
        )
    return template


def _parse_choices(value: Any, location: str) -> dict[int, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{location}.choices must be an object")
    choices: dict[int, str] = {}
    for raw_key, raw_label in value.items():
        try:
            key = _parse_integer_value(raw_key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{location}.choices contains an invalid value") from exc
        if not isinstance(raw_label, str) or not raw_label:
            raise ValueError(f"{location}.choices labels must be strings")
        choices[key] = raw_label
    return choices


def _parse_integer_value(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Boolean is not an integer value")
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise TypeError("Value is not an integer or string")
    text = value.strip()
    if not text:
        raise ValueError("Integer string is empty")
    signless = text[1:] if text.startswith(("+", "-")) else text
    base = 16 if signless.lower().startswith("0x") else 10
    return int(text, base)


def _display_number(
    value: int,
    size: int,
    number_format: str,
) -> int | str:
    if number_format != "hex":
        return value
    sign = "-" if value < 0 else ""
    return f"{sign}0x{abs(value):0{size * 2}X}"


def _integer_range(size: int, signed: bool) -> tuple[int, int]:
    bits = size * 8
    if signed:
        return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return 0, (1 << bits) - 1


def _response_kind(value: Any) -> ResponseKind:
    if not isinstance(value, dict):
        return ResponseKind.COMMAND_COMPLETE
    raw_kind = value.get("kind", "command_complete")
    if raw_kind == "unknown":
        return ResponseKind.COMMAND_COMPLETE
    try:
        return ResponseKind(raw_kind)
    except ValueError as exc:
        raise ValueError(f"Unsupported response kind: {raw_kind}") from exc
