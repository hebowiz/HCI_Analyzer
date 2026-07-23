"""Load and compare vendor-specific HCI commands captured in Analyzer JSONL."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


VENDOR_OGF = 0x3F


@dataclass(slots=True)
class VendorCapture:
    """One vendor command and any responses associated with it."""

    capture_id: str
    source_path: Path
    line_number: int
    timestamp: str
    source: str
    opcode: int
    parameters: bytes
    raw_data: bytes
    annotations: dict[str, str] = field(default_factory=dict)
    responses: list[bytes] = field(default_factory=list)

    @property
    def ocf(self) -> int:
        return self.opcode & 0x03FF


@dataclass(slots=True, frozen=True)
class FieldCandidate:
    """One possible byte layout for a user-labelled parameter."""

    name: str
    offset: int
    data_type: str
    size: int
    confidence: str
    sample_count: int
    distinct_value_count: int


@dataclass(slots=True, frozen=True)
class VendorAnalysis:
    """Comparison result for captures sharing one vendor opcode."""

    opcode: int
    capture_count: int
    parameter_lengths: tuple[int, ...]
    changed_offsets: tuple[int, ...]
    candidates: dict[str, tuple[FieldCandidate, ...]]
    warnings: tuple[str, ...] = ()


def load_vendor_captures(
    paths: Iterable[Path],
) -> tuple[list[VendorCapture], list[str]]:
    """Load vendor commands from one or more Analyzer JSONL files."""
    captures: list[VendorCapture] = []
    errors: list[str] = []
    pending: dict[int, list[VendorCapture]] = {}
    latest_capture: VendorCapture | None = None

    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue

        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(record, dict):
                errors.append(f"{path}:{line_number}: JSON record is not an object")
                continue

            raw = _record_raw_bytes(record)
            if raw is None or not raw:
                continue
            if raw[0] == 0x01:
                capture = _vendor_command_capture(
                    path,
                    line_number,
                    record,
                    raw,
                )
                if capture is None:
                    continue
                captures.append(capture)
                pending.setdefault(capture.opcode, []).append(capture)
                latest_capture = capture
                continue
            if raw[0] != 0x04:
                continue

            response_opcode = _response_opcode(raw)
            if response_opcode is not None and _is_vendor_opcode(response_opcode):
                candidates = pending.get(response_opcode, [])
                if candidates:
                    capture = candidates.pop(0)
                    capture.responses.append(raw)
                continue
            if len(raw) >= 3 and raw[1] == 0xFF and latest_capture is not None:
                latest_capture.responses.append(raw)

    return captures, errors


def parse_annotations(text: str) -> dict[str, str]:
    """Parse comma, semicolon, or newline separated name=value annotations."""
    annotations: dict[str, str] = {}
    if not text.strip():
        return annotations
    for item in re.split(r"[,;\n]+", text):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Annotation must use name=value: {item}")
        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not value:
            raise ValueError(f"Annotation name and value are required: {item}")
        annotations[name] = value
    return annotations


def analyze_captures(captures: Iterable[VendorCapture]) -> VendorAnalysis:
    """Infer byte-layout candidates from user-labelled captures."""
    selected = list(captures)
    if not selected:
        raise ValueError("At least one vendor command capture is required")
    opcode = selected[0].opcode
    if any(item.opcode != opcode for item in selected):
        raise ValueError("All captures must use the same opcode")

    parameter_lengths = tuple(sorted({len(item.parameters) for item in selected}))
    changed_offsets = _changed_offsets(selected)
    field_names = sorted(
        {
            name
            for capture in selected
            for name in capture.annotations
        }
    )
    candidates: dict[str, tuple[FieldCandidate, ...]] = {}
    warnings: list[str] = []
    for name in field_names:
        labelled = [
            (capture, capture.annotations[name])
            for capture in selected
            if name in capture.annotations
        ]
        if len(labelled) < 2:
            candidates[name] = ()
            warnings.append(
                f"{name}: at least two labelled captures are required"
            )
            continue
        inferred = _infer_numeric_candidates(name, labelled)
        if not inferred:
            inferred = _infer_enum_candidates(name, labelled)
        candidates[name] = tuple(inferred)
        if not inferred:
            warnings.append(f"{name}: no exact byte-layout candidate was found")

    if len(parameter_lengths) > 1:
        warnings.append(
            "Parameter lengths differ; the command may contain a variable-length field"
        )
    return VendorAnalysis(
        opcode=opcode,
        capture_count=len(selected),
        parameter_lengths=parameter_lengths,
        changed_offsets=changed_offsets,
        candidates=candidates,
        warnings=tuple(warnings),
    )


def build_definition_draft(
    analysis: VendorAnalysis,
    command_name: str,
    captures: Iterable[VendorCapture] = (),
) -> dict[str, Any]:
    """Build a review-required external command definition draft."""
    evidence = [
        capture for capture in captures if capture.opcode == analysis.opcode
    ]
    name = command_name.strip() or f"Vendor_Command_0x{analysis.opcode:04X}"
    fields: list[dict[str, Any]] = []
    for field_name, candidates in analysis.candidates.items():
        item: dict[str, Any] = {
            "name": field_name,
            "review_required": True,
            "candidates": [
                {
                    "offset": candidate.offset,
                    "type": candidate.data_type,
                    "size": candidate.size,
                    "confidence": candidate.confidence,
                    "sample_count": candidate.sample_count,
                    "distinct_value_count": candidate.distinct_value_count,
                }
                for candidate in candidates
            ],
        }
        if candidates:
            selected = candidates[0]
            item.update(
                {
                    "offset": selected.offset,
                    "type": selected.data_type,
                    "size": selected.size,
                    "confidence": selected.confidence,
                }
            )
            default = _field_default(field_name, selected, evidence)
            if default is not None:
                item["default"] = default
            if selected.data_type == "enum_u8":
                choices = _enum_choices(field_name, selected.offset, evidence)
                if choices:
                    item["choices"] = choices
        fields.append(item)

    parameter_length = (
        analysis.parameter_lengths[0]
        if len(analysis.parameter_lengths) == 1
        else None
    )
    return {
        "schema_version": 1,
        "kind": "hci_vendor_command_definition_draft",
        "review_required": True,
        "commands": [
            {
                "opcode": f"0x{analysis.opcode:04X}",
                "ogf": VENDOR_OGF,
                "ocf": analysis.opcode & 0x03FF,
                "name": name,
                "parameter_length": parameter_length,
                "parameter_template_hex": (
                    evidence[0].parameters.hex(" ").upper()
                    if evidence
                    else None
                ),
                "parameters": fields,
                "response": {"kind": "unknown"},
            }
        ],
    }


def format_analysis_report(
    captures: Iterable[VendorCapture],
    analysis: VendorAnalysis,
) -> str:
    """Render a concise text report for the discovery GUI."""
    selected = list(captures)
    lines = [
        f"Opcode: 0x{analysis.opcode:04X}  "
        f"OGF: 0x{VENDOR_OGF:02X}  OCF: 0x{analysis.opcode & 0x03FF:03X}",
        f"Captures: {analysis.capture_count}",
        "Parameter lengths: "
        + ", ".join(str(value) for value in analysis.parameter_lengths),
        "Changed byte offsets: "
        + (
            ", ".join(str(value) for value in analysis.changed_offsets)
            if analysis.changed_offsets
            else "none"
        ),
        "",
        "BYTE MATRIX",
    ]
    for index, capture in enumerate(selected, start=1):
        annotation = ", ".join(
            f"{key}={value}" for key, value in capture.annotations.items()
        )
        lines.append(
            f"{index:>3}: {capture.parameters.hex(' ').upper():<48} "
            f"{annotation or '-'}"
        )
    lines.extend(["", "FIELD CANDIDATES"])
    if not analysis.candidates:
        lines.append("No annotations. Add name=value labels to at least two captures.")
    for name, candidates in analysis.candidates.items():
        lines.append(f"{name}:")
        if not candidates:
            lines.append("  no exact candidate")
            continue
        for candidate in candidates:
            lines.append(
                "  "
                f"offset={candidate.offset} type={candidate.data_type} "
                f"size={candidate.size} confidence={candidate.confidence} "
                f"samples={candidate.sample_count} "
                f"distinct={candidate.distinct_value_count}"
            )
    if analysis.warnings:
        lines.extend(["", "WARNINGS"])
        lines.extend(f"- {warning}" for warning in analysis.warnings)
    return "\n".join(lines)


def _vendor_command_capture(
    path: Path,
    line_number: int,
    record: dict[str, Any],
    raw: bytes,
) -> VendorCapture | None:
    if len(raw) < 4:
        return None
    opcode = int.from_bytes(raw[1:3], "little")
    if not _is_vendor_opcode(opcode):
        return None
    parameter_length = raw[3]
    if len(raw) != 4 + parameter_length:
        return None
    return VendorCapture(
        capture_id=f"{path.resolve()}:{line_number}",
        source_path=path,
        line_number=line_number,
        timestamp=str(record.get("timestamp", "")),
        source=str(record.get("source", "")),
        opcode=opcode,
        parameters=raw[4:],
        raw_data=raw,
    )


def _record_raw_bytes(record: dict[str, Any]) -> bytes | None:
    raw_value = record.get("raw_data")
    result = record.get("result")
    if not raw_value and isinstance(result, dict):
        raw_value = result.get("raw_data")
    if not isinstance(raw_value, str):
        return None
    try:
        return bytes.fromhex(raw_value)
    except ValueError:
        return None


def _response_opcode(raw: bytes) -> int | None:
    if len(raw) >= 6 and raw[1] == 0x0E:
        return int.from_bytes(raw[4:6], "little")
    if len(raw) >= 7 and raw[1] == 0x0F:
        return int.from_bytes(raw[5:7], "little")
    return None


def _is_vendor_opcode(opcode: int) -> bool:
    return ((opcode >> 10) & 0x3F) == VENDOR_OGF


def _changed_offsets(captures: list[VendorCapture]) -> tuple[int, ...]:
    maximum = max(len(capture.parameters) for capture in captures)
    changed: list[int] = []
    for offset in range(maximum):
        values = {
            capture.parameters[offset]
            if offset < len(capture.parameters)
            else None
            for capture in captures
        }
        if len(values) > 1:
            changed.append(offset)
    return tuple(changed)


def _infer_numeric_candidates(
    name: str,
    labelled: list[tuple[VendorCapture, str]],
) -> list[FieldCandidate]:
    numeric_values: list[tuple[VendorCapture, int]] = []
    for capture, value in labelled:
        try:
            numeric_values.append((capture, _parse_integer(value)))
        except ValueError:
            return []

    type_specs = (
        ("uint8", 1, False, "little"),
        ("int8", 1, True, "little"),
        ("uint16_le", 2, False, "little"),
        ("int16_le", 2, True, "little"),
        ("uint16_be", 2, False, "big"),
        ("int16_be", 2, True, "big"),
        ("uint32_le", 4, False, "little"),
        ("int32_le", 4, True, "little"),
        ("uint32_be", 4, False, "big"),
        ("int32_be", 4, True, "big"),
    )
    minimum_length = min(len(capture.parameters) for capture, _ in numeric_values)
    distinct = len({value for _, value in numeric_values})
    candidates: list[FieldCandidate] = []
    for data_type, size, signed, byte_order in type_specs:
        if size > minimum_length:
            continue
        for offset in range(minimum_length - size + 1):
            decoded = [
                int.from_bytes(
                    capture.parameters[offset : offset + size],
                    byte_order,
                    signed=signed,
                )
                for capture, _ in numeric_values
            ]
            expected = [value for _, value in numeric_values]
            if decoded != expected:
                continue
            candidates.append(
                FieldCandidate(
                    name=name,
                    offset=offset,
                    data_type=data_type,
                    size=size,
                    confidence=_confidence(len(numeric_values), distinct),
                    sample_count=len(numeric_values),
                    distinct_value_count=distinct,
                )
            )
    return sorted(candidates, key=_candidate_sort_key)


def _infer_enum_candidates(
    name: str,
    labelled: list[tuple[VendorCapture, str]],
) -> list[FieldCandidate]:
    minimum_length = min(len(capture.parameters) for capture, _ in labelled)
    distinct_labels = {value for _, value in labelled}
    if len(distinct_labels) < 2:
        return []
    candidates: list[FieldCandidate] = []
    for offset in range(minimum_length):
        by_label: dict[str, set[int]] = {}
        for capture, label in labelled:
            by_label.setdefault(label, set()).add(capture.parameters[offset])
        if any(len(values) != 1 for values in by_label.values()):
            continue
        encoded_values = {next(iter(values)) for values in by_label.values()}
        if len(encoded_values) != len(by_label):
            continue
        candidates.append(
            FieldCandidate(
                name=name,
                offset=offset,
                data_type="enum_u8",
                size=1,
                confidence=_confidence(len(labelled), len(distinct_labels)),
                sample_count=len(labelled),
                distinct_value_count=len(distinct_labels),
            )
        )
    return candidates


def _confidence(sample_count: int, distinct_count: int) -> str:
    if sample_count >= 4 and distinct_count >= 3:
        return "high"
    if sample_count >= 2 and distinct_count >= 2:
        return "medium"
    return "low"


def _field_default(
    name: str,
    candidate: FieldCandidate,
    captures: list[VendorCapture],
) -> int | None:
    for capture in captures:
        if name not in capture.annotations:
            continue
        if candidate.data_type == "enum_u8":
            return capture.parameters[candidate.offset]
        try:
            return _parse_integer(capture.annotations[name])
        except ValueError:
            return None
    return None


def _enum_choices(
    name: str,
    offset: int,
    captures: list[VendorCapture],
) -> dict[str, str]:
    choices: dict[str, str] = {}
    for capture in captures:
        label = capture.annotations.get(name)
        if label is None or offset >= len(capture.parameters):
            continue
        choices[str(capture.parameters[offset])] = label
    return choices


def _parse_integer(value: str) -> int:
    text = value.strip()
    signless = text[1:] if text.startswith(("+", "-")) else text
    base = 16 if signless.lower().startswith("0x") else 10
    return int(text, base)


def _candidate_sort_key(candidate: FieldCandidate) -> tuple[int, int, int, int]:
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    endian_order = 0 if candidate.data_type.endswith("_le") else 1
    type_order = {
        "uint8": 0,
        "int8": 1,
        "uint16_le": 2,
        "int16_le": 3,
        "uint16_be": 4,
        "int16_be": 5,
        "uint32_le": 6,
        "int32_le": 7,
        "uint32_be": 8,
        "int32_be": 9,
    }
    return (
        confidence_order[candidate.confidence],
        candidate.size,
        endian_order,
        type_order.get(candidate.data_type, 99),
    )
