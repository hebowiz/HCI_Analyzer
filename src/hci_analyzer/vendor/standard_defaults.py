"""Seed editable Discovery projects from known HCI layouts and captured bytes."""

from hci_analyzer.command_builder.definitions import (
    COMMAND_DEFINITIONS_BY_OPCODE,
    ParameterKind,
)
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.vendor.discovery import VendorCapture, default_command_name
from hci_analyzer.vendor.project import UserParameter, VendorDiscoveryProject


def create_discovery_project(capture: VendorCapture) -> VendorDiscoveryProject:
    """Initialize once; never overwrite subsequent user edits on new captures.

    Known variable arrays are expanded at their captured size. Unknown layouts
    use raw octets, without claiming to know their semantics.
    """
    project = VendorDiscoveryProject(
        opcode=capture.opcode, command_name=default_command_name(capture.opcode)
    )
    if capture.opcode >> 10 == 0x3F:
        return project

    definition = COMMAND_DEFINITIONS_BY_OPCODE.get(capture.opcode)
    parsed = HciParser().parse_bytes(capture.raw_data)
    if definition is None or not parsed.success:
        for offset, value in enumerate(capture.parameters):
            project.add_parameter(_field(
                f"Parameter_{offset}", f"Byte {offset}", offset, value,
                number_format="hex",
            ))
        return project

    offset = 0
    for parameter in definition.parameters:
        # This editor is synthetic; the wire contains only TX_Power_Level.
        if parameter.name == "TX_Power_Mode":
            continue
        if parameter.kind == ParameterKind.INTEGER_ARRAY:
            count = capture.parameters[offset]
            project.add_parameter(_field(
                "Switching_Pattern_Length", "Switching Pattern Length",
                offset, count,
            ))
            offset += 1
            for index in range(count):
                project.add_parameter(_field(
                    f"{parameter.name}_{index}", f"{parameter.label}[{index}]",
                    offset, capture.parameters[offset],
                ))
                offset += 1
            continue
        raw = capture.parameters[offset]
        signed = parameter.kind == ParameterKind.SIGNED_INTEGER
        value = int.from_bytes(bytes([raw]), "little", signed=signed)
        choices = dict(parameter.choices)
        if choices and value not in choices:
            choices[value] = f"Unknown_0x{raw:02X}"
        project.add_parameter(_field(
            parameter.name, parameter.label, offset, value,
            signed=signed, choices=choices, unit=parameter.unit or "",
            description=parameter.description,
        ))
        offset += 1
    return project


def _field(
    name: str, label: str, offset: int, value: int, *,
    signed: bool = False, choices: dict[int, str] | None = None,
    unit: str = "", description: str = "", number_format: str = "decimal",
) -> UserParameter:
    choices = choices or {}
    parameter = UserParameter(
        name=name, display_name=label,
        kind="enum" if choices else "signed" if signed else "unsigned",
        choices=list(choices.values()),
        choice_values={label: value for value, label in choices.items()},
        default=f"0x{value:02X}" if number_format == "hex" else str(value),
        unit=unit, description=description, number_format=number_format,
    )
    parameter.set_manual_candidate(
        offset, "enum_u8" if choices else "int8" if signed else "uint8"
    )
    parameter.confirmed_candidate["source"] = "standard_default"
    return parameter
