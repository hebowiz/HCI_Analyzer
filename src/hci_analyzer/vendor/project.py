"""Incremental, user-defined vendor command analysis projects."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from hci_analyzer.vendor.discovery import FieldCandidate, VendorCapture
from hci_analyzer.vendor.console_definitions import SUPPORTED_FIELD_TYPES
from hci_analyzer.vendor.live_capture import DiscoveryCapture


PARAMETER_KINDS = (
    "auto",
    "unsigned",
    "signed",
    "enum",
    "boolean",
    "bit_field",
    "raw_bytes",
)
MANUAL_FIELD_TYPES = tuple(SUPPORTED_FIELD_TYPES)


@dataclass(slots=True)
class UserParameter:
    """Semantic parameter definition entered by the user."""

    name: str
    display_name: str
    kind: str = "auto"
    unit: str = ""
    description: str = ""
    choices: list[str] = field(default_factory=list)
    status: str = "not_analyzed"
    candidates: list[dict[str, object]] = field(default_factory=list)
    confirmed_candidate: dict[str, object] | None = None

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.name):
            raise ValueError(
                "Parameter name must use letters, digits, and underscores"
            )
        if not self.display_name.strip():
            raise ValueError("Display name is required")
        if self.kind not in PARAMETER_KINDS:
            raise ValueError(f"Unsupported parameter kind: {self.kind}")
        if self.kind in ("enum", "boolean") and len(self.choices) < 2:
            raise ValueError("Enum and Boolean parameters require at least two choices")

    def set_candidates(self, candidates: Iterable[FieldCandidate]) -> None:
        self.candidates = [
            {
                "offset": candidate.offset,
                "type": candidate.data_type,
                "size": candidate.size,
                "confidence": candidate.confidence,
                "sample_count": candidate.sample_count,
                "distinct_value_count": candidate.distinct_value_count,
            }
            for candidate in candidates
            if _candidate_matches_kind(candidate, self.kind)
        ]
        self.confirmed_candidate = None
        self.status = "candidate" if self.candidates else "not_found"

    def confirm_first_candidate(self) -> None:
        self.confirm_candidate(0)

    def confirm_candidate(self, index: int) -> None:
        """Confirm one explicitly selected inference candidate."""
        if not self.candidates:
            raise ValueError("No candidate is available to confirm")
        if not 0 <= index < len(self.candidates):
            raise ValueError("Candidate index is out of range")
        self.confirmed_candidate = dict(self.candidates[index])
        self.status = "confirmed"

    def set_manual_candidate(self, offset: int, data_type: str) -> None:
        """Confirm a user-specified byte offset and encoding type."""
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("Offset must be a non-negative integer")
        if data_type not in SUPPORTED_FIELD_TYPES:
            raise ValueError(f"Unsupported field type: {data_type}")
        size = SUPPORTED_FIELD_TYPES[data_type][0]
        if self.kind == "unsigned" and not data_type.startswith("uint"):
            raise ValueError("Unsigned parameters require a uint field type")
        if self.kind == "signed" and not data_type.startswith("int"):
            raise ValueError("Signed parameters require an int field type")
        if self.kind in ("enum", "boolean") and data_type != "enum_u8":
            raise ValueError("Enum and Boolean parameters require enum_u8")
        if self.kind in ("bit_field", "raw_bytes"):
            raise ValueError(
                "Bit field and raw byte manual layouts are not supported yet"
            )
        self.confirmed_candidate = {
            "offset": offset,
            "type": data_type,
            "size": size,
            "confidence": "manual",
            "sample_count": 0,
            "distinct_value_count": 0,
            "source": "manual",
        }
        self.status = "confirmed"


@dataclass(slots=True)
class VendorDiscoveryProject:
    """Accumulated command identity and parameter inference decisions."""

    opcode: int | None = None
    command_name: str = ""
    parameters: list[UserParameter] = field(default_factory=list)

    def add_parameter(self, parameter: UserParameter) -> None:
        parameter.validate()
        if any(item.name == parameter.name for item in self.parameters):
            raise ValueError(f"Parameter already exists: {parameter.name}")
        self.parameters.append(parameter)

    def replace_parameter(self, original_name: str, parameter: UserParameter) -> None:
        parameter.validate()
        if any(
            item.name == parameter.name and item.name != original_name
            for item in self.parameters
        ):
            raise ValueError(f"Parameter already exists: {parameter.name}")
        for index, existing in enumerate(self.parameters):
            if existing.name == original_name:
                self.parameters[index] = parameter
                return
        raise ValueError(f"Unknown parameter: {original_name}")

    def remove_parameter(self, name: str) -> bool:
        before = len(self.parameters)
        self.parameters = [item for item in self.parameters if item.name != name]
        return len(self.parameters) != before

    def parameter(self, name: str) -> UserParameter | None:
        return next((item for item in self.parameters if item.name == name), None)

    def set_manual_layout(
        self,
        name: str,
        offset: int,
        data_type: str,
        parameter_length: int,
    ) -> None:
        """Set and immediately validate a manual layout against the command."""
        parameter = self.parameter(name)
        if parameter is None:
            raise ValueError(f"Unknown parameter: {name}")
        previous_candidate = (
            dict(parameter.confirmed_candidate)
            if parameter.confirmed_candidate is not None
            else None
        )
        previous_status = parameter.status
        parameter.set_manual_candidate(offset, data_type)
        try:
            _validate_confirmed_layouts(self.parameters, parameter_length)
        except ValueError:
            parameter.confirmed_candidate = previous_candidate
            parameter.status = previous_status
            raise


def save_project(
    path: Path,
    project: VendorDiscoveryProject,
    captures: Iterable[DiscoveryCapture],
) -> None:
    """Save semantic definitions, inference state, and capture evidence."""
    payload = {
        "schema_version": 1,
        "kind": "hci_vendor_discovery_project",
        "opcode": f"0x{project.opcode:04X}" if project.opcode is not None else None,
        "command_name": project.command_name,
        "parameters": [asdict(parameter) for parameter in project.parameters],
        "captures": [_capture_to_dict(capture) for capture in captures],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_project(path: Path) -> tuple[VendorDiscoveryProject, list[DiscoveryCapture]]:
    """Load a previously saved incremental discovery project."""
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Project root must be a JSON object")
    if payload.get("kind") != "hci_vendor_discovery_project":
        raise ValueError("Not a Vendor Discovery project")
    opcode_value = payload.get("opcode")
    opcode = int(opcode_value, 0) if isinstance(opcode_value, str) else None
    project = VendorDiscoveryProject(
        opcode=opcode,
        command_name=str(payload.get("command_name", "")),
    )
    raw_parameters = payload.get("parameters", [])
    if not isinstance(raw_parameters, list):
        raise ValueError("Project parameters must be an array")
    for raw_parameter in raw_parameters:
        if not isinstance(raw_parameter, dict):
            raise ValueError("Project parameter must be an object")
        raw_choices = raw_parameter.get("choices", [])
        raw_candidates = raw_parameter.get("candidates", [])
        if not isinstance(raw_choices, list):
            raise ValueError("Project parameter choices must be an array")
        if not isinstance(raw_candidates, list):
            raise ValueError("Project parameter candidates must be an array")
        parameter = UserParameter(
            name=str(raw_parameter.get("name", "")),
            display_name=str(raw_parameter.get("display_name", "")),
            kind=str(raw_parameter.get("kind", "auto")),
            unit=str(raw_parameter.get("unit", "")),
            description=str(raw_parameter.get("description", "")),
            choices=[
                str(value)
                for value in raw_choices
            ],
            status=str(raw_parameter.get("status", "not_analyzed")),
            candidates=[
                dict(value)
                for value in raw_candidates
                if isinstance(value, dict)
            ],
            confirmed_candidate=(
                dict(raw_parameter["confirmed_candidate"])
                if isinstance(raw_parameter.get("confirmed_candidate"), dict)
                else None
            ),
        )
        project.add_parameter(parameter)
    raw_captures = payload.get("captures", [])
    if not isinstance(raw_captures, list):
        raise ValueError("Project captures must be an array")
    captures = [
        _capture_from_dict(item, index)
        for index, item in enumerate(raw_captures, start=1)
        if isinstance(item, dict)
    ]
    return project, captures


def build_console_definition(
    project: VendorDiscoveryProject,
    captures: Iterable[VendorCapture],
) -> dict[str, object]:
    """Build a Console-compatible definition from confirmed project fields."""
    evidence = list(captures)
    if project.opcode is None:
        raise ValueError("Project opcode is not selected")
    if not project.command_name.strip():
        raise ValueError("Command name is required")
    if not evidence:
        raise ValueError("At least one capture is required")
    lengths = {len(capture.parameters) for capture in evidence}
    if len(lengths) != 1:
        raise ValueError("Console export requires one fixed parameter length")
    fields: list[dict[str, object]] = []
    occupied: dict[int, str] = {}
    for parameter in project.parameters:
        candidate = parameter.confirmed_candidate
        if candidate is None:
            continue
        field: dict[str, object] = {
            "name": parameter.name,
            "label": parameter.display_name,
            "offset": candidate["offset"],
            "type": candidate["type"],
            "size": candidate["size"],
        }
        if parameter.unit:
            field["unit"] = parameter.unit
        offset = int(candidate["offset"])
        data_type = str(candidate["type"])
        size = int(candidate["size"])
        if data_type not in SUPPORTED_FIELD_TYPES:
            raise ValueError(
                f"Confirmed parameter {parameter.name} has unsupported type "
                f"{data_type}"
            )
        expected_size = SUPPORTED_FIELD_TYPES[data_type][0]
        if size != expected_size:
            raise ValueError(
                f"Confirmed parameter {parameter.name} size does not match "
                f"{data_type}"
            )
        parameter_length = next(iter(lengths))
        if offset < 0 or offset + size > parameter_length:
            raise ValueError(
                f"Confirmed parameter {parameter.name} exceeds the parameter "
                "template"
            )
        for byte_index in range(offset, offset + size):
            if byte_index in occupied:
                raise ValueError(
                    f"Confirmed parameters {occupied[byte_index]} and "
                    f"{parameter.name} overlap at byte {byte_index}"
                )
            occupied[byte_index] = parameter.name
        signed = data_type.startswith("int")
        byte_order = "big" if data_type.endswith("_be") else "little"
        field["default"] = int.from_bytes(
            evidence[0].parameters[offset : offset + size],
            byte_order,
            signed=signed,
        )
        if data_type == "enum_u8":
            choices: dict[str, str] = {}
            for capture in evidence:
                label = capture.annotations.get(parameter.name)
                if label is not None and offset < len(capture.parameters):
                    choices[str(capture.parameters[offset])] = label
            if choices:
                if str(field["default"]) not in choices:
                    field["default"] = int(next(iter(choices)))
                field["choices"] = choices
        fields.append(field)
    if not fields:
        raise ValueError("At least one confirmed parameter is required")
    return {
        "schema_version": 1,
        "kind": "hci_vendor_command_definition",
        "review_required": False,
        "commands": [
            {
                "opcode": f"0x{project.opcode:04X}",
                "ogf": 0x3F,
                "ocf": project.opcode & 0x03FF,
                "name": project.command_name.strip(),
                "parameter_length": lengths.pop(),
                "parameter_template_hex": evidence[0].parameters.hex(" ").upper(),
                "parameters": fields,
                "response": {"kind": "unknown"},
            }
        ],
    }


def _candidate_matches_kind(candidate: FieldCandidate, kind: str) -> bool:
    if kind == "auto":
        return True
    if kind == "unsigned":
        return candidate.data_type.startswith("uint")
    if kind == "signed":
        return candidate.data_type.startswith("int")
    if kind in ("enum", "boolean"):
        return candidate.data_type == "enum_u8"
    return False


def _validate_confirmed_layouts(
    parameters: Iterable[UserParameter],
    parameter_length: int,
) -> None:
    occupied: dict[int, str] = {}
    for parameter in parameters:
        candidate = parameter.confirmed_candidate
        if candidate is None:
            continue
        data_type = str(candidate.get("type", ""))
        if data_type not in SUPPORTED_FIELD_TYPES:
            raise ValueError(
                f"Confirmed parameter {parameter.name} has unsupported type "
                f"{data_type}"
            )
        offset = int(candidate.get("offset", -1))
        size = SUPPORTED_FIELD_TYPES[data_type][0]
        if offset < 0 or offset + size > parameter_length:
            raise ValueError(
                f"Confirmed parameter {parameter.name} exceeds the parameter "
                "template"
            )
        for byte_index in range(offset, offset + size):
            if byte_index in occupied:
                raise ValueError(
                    f"Confirmed parameters {occupied[byte_index]} and "
                    f"{parameter.name} overlap at byte {byte_index}"
                )
            occupied[byte_index] = parameter.name


def _capture_to_dict(capture: DiscoveryCapture) -> dict[str, object]:
    base: dict[str, object] = {
        "capture_id": capture.capture_id,
        "timestamp": capture.timestamp,
        "source": capture.source,
        "protocol": capture.protocol,
        "raw_hex": capture.raw_data.hex(" ").upper(),
    }
    if capture.vendor_capture is not None:
        base.update(
            {
                "opcode": f"0x{capture.vendor_capture.opcode:04X}",
                "parameters_hex": capture.vendor_capture.parameters.hex(" ").upper(),
                "annotations": dict(capture.vendor_capture.annotations),
                "responses_hex": [
                    response.hex(" ").upper()
                    for response in capture.vendor_capture.responses
                ],
            }
        )
    else:
        base.update(
            {
                "race_type": capture.race_type,
                "race_command_id": capture.race_command_id,
                "race_payload_hex": capture.race_payload.hex(" ").upper(),
            }
        )
    return base


def _capture_from_dict(
    item: dict[str, Any],
    index: int,
) -> DiscoveryCapture:
    protocol = str(item.get("protocol", ""))
    raw = bytes.fromhex(str(item.get("raw_hex", "")))
    capture_id = str(item.get("capture_id") or f"project:{index}")
    timestamp = str(item.get("timestamp", ""))
    source = str(item.get("source", ""))
    if protocol == "HCI Vendor":
        opcode = int(str(item.get("opcode")), 0)
        parameters = bytes.fromhex(str(item.get("parameters_hex", "")))
        annotations = item.get("annotations", {})
        raw_responses = item.get("responses_hex", [])
        if not isinstance(raw_responses, list):
            raise ValueError("Project capture responses_hex must be an array")
        vendor = VendorCapture(
            capture_id=capture_id,
            source_path=Path("<project>"),
            line_number=index,
            timestamp=timestamp,
            source=source,
            opcode=opcode,
            parameters=parameters,
            raw_data=raw,
            annotations=(
                {str(key): str(value) for key, value in annotations.items()}
                if isinstance(annotations, dict)
                else {}
            ),
            responses=[
                bytes.fromhex(str(value))
                for value in raw_responses
            ],
        )
        return DiscoveryCapture(
            capture_id=capture_id,
            timestamp=timestamp,
            source=source,
            protocol=protocol,
            raw_data=raw,
            vendor_capture=vendor,
        )
    return DiscoveryCapture(
        capture_id=capture_id,
        timestamp=timestamp,
        source=source,
        protocol="RACE",
        raw_data=raw,
        race_type=_optional_int(item.get("race_type")),
        race_command_id=_optional_int(item.get("race_command_id")),
        race_payload=bytes.fromhex(str(item.get("race_payload_hex", ""))),
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
