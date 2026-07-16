"""Build Mermaid sequence diagrams and preview images from Analyzer JSONL logs."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFont


SequenceDirection = Literal["host_to_controller", "controller_to_host"]


@dataclass(slots=True, frozen=True)
class SequenceMessage:
    """One Host/Controller message in the generated sequence."""

    direction: SequenceDirection
    label: str
    raw_hex: str
    opcode: int | None = None
    response_to_index: int | None = None


@dataclass(slots=True, frozen=True)
class HciSequenceDiagram:
    """A parsed HCI sequence with export helpers."""

    source_path: Path
    messages: tuple[SequenceMessage, ...]

    def to_mermaid(self) -> str:
        """Return Mermaid sequenceDiagram source."""
        lines = [
            "sequenceDiagram",
            "    participant Host",
            "    participant Controller",
        ]
        for message in self.messages:
            label = _mermaid_text(message.label)
            if message.direction == "host_to_controller":
                lines.append(f"    Host->>Controller: {label}")
            else:
                lines.append(f"    Controller-->>Host: {label}")
        return "\n".join(lines) + "\n"

    def to_markdown(self) -> str:
        """Return a Markdown document containing the Mermaid diagram."""
        return (
            f"# HCI Sequence Diagram: {self.source_path.name}\n\n"
            "```mermaid\n"
            f"{self.to_mermaid()}"
            "```\n"
        )

    def to_svg(self) -> str:
        """Render a standalone SVG without requiring Mermaid CLI."""
        width = 1000
        top = 70
        row_height = 58
        bottom = 45
        height = top + max(len(self.messages), 1) * row_height + bottom
        host_x = 220
        controller_x = 780
        elements = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}">'
            ),
            "<defs>",
            '<marker id="arrow" markerWidth="10" markerHeight="7" '
            'refX="9" refY="3.5" orient="auto">',
            '<polygon points="0 0, 10 3.5, 0 7" fill="#333"/>',
            "</marker>",
            "</defs>",
            '<rect width="100%" height="100%" fill="white"/>',
            _svg_actor(host_x, "Host"),
            _svg_actor(controller_x, "Controller"),
            (
                f'<line x1="{host_x}" y1="48" x2="{host_x}" y2="{height-bottom}" '
                'stroke="#777" stroke-width="1" stroke-dasharray="5,5"/>'
            ),
            (
                f'<line x1="{controller_x}" y1="48" x2="{controller_x}" '
                f'y2="{height-bottom}" stroke="#777" stroke-width="1" '
                'stroke-dasharray="5,5"/>'
            ),
        ]
        for index, message in enumerate(self.messages):
            y = top + index * row_height
            if message.direction == "host_to_controller":
                start_x, end_x = host_x, controller_x
            else:
                start_x, end_x = controller_x, host_x
            elements.append(
                f'<line x1="{start_x}" y1="{y}" x2="{end_x}" y2="{y}" '
                'stroke="#333" stroke-width="1.5" marker-end="url(#arrow)"/>'
            )
            elements.extend(_svg_label(message.label, width // 2, y - 9))
        elements.append("</svg>")
        return "\n".join(elements) + "\n"

    def save_markdown(self, path: Path) -> Path:
        """Save the Markdown representation to an explicitly selected path."""
        return _write_text(path, self.to_markdown())

    def save_screenshot(self, path: Path) -> Path:
        """Render the complete Markdown preview as a PNG image."""
        width = 1000
        title_height = 78
        diagram_top = title_height + 100
        row_height = 58
        bottom = 45
        height = diagram_top + max(len(self.messages), 1) * row_height + bottom
        host_x = 220
        controller_x = 780

        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        title_font = _image_font(22, bold=True)
        actor_font = _image_font(16, bold=True)
        message_font = _image_font(13, monospace=True)

        draw.text(
            (30, 24),
            f"HCI Sequence Diagram: {self.source_path.name}",
            fill="#111111",
            font=title_font,
        )
        _draw_image_actor(draw, host_x, title_height + 12, "Host", actor_font)
        _draw_image_actor(
            draw,
            controller_x,
            title_height + 12,
            "Controller",
            actor_font,
        )
        life_bottom = height - bottom
        draw.line(
            (host_x, title_height + 48, host_x, life_bottom),
            fill="#777777",
            width=1,
        )
        draw.line(
            (controller_x, title_height + 48, controller_x, life_bottom),
            fill="#777777",
            width=1,
        )

        for index, message in enumerate(self.messages):
            y = diagram_top + index * row_height
            if message.direction == "host_to_controller":
                start_x, end_x = host_x, controller_x
            else:
                start_x, end_x = controller_x, host_x
            _draw_image_arrow(draw, start_x, end_x, y)
            _draw_centered_image_text(
                draw,
                message.label,
                width // 2,
                y - 25,
                message_font,
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="PNG")
        return path

    def save_preview_outputs(self) -> tuple[Path, Path]:
        """Save Markdown and PNG beside the source JSONL using automatic names."""
        base = self.source_path.with_name(f"{self.source_path.stem}_sequence")
        markdown = self.save_markdown(base.with_suffix(".md"))
        screenshot = self.save_screenshot(base.with_suffix(".png"))
        return markdown, screenshot

    def save(
        self,
        output_directory: Path,
        *,
        write_mmd: bool,
        write_md: bool,
        write_svg: bool,
    ) -> list[Path]:
        """Write selected output formats and return their paths."""
        output_directory.mkdir(parents=True, exist_ok=True)
        base = output_directory / f"{self.source_path.stem}_sequence"
        outputs: list[Path] = []
        if write_mmd:
            outputs.append(_write_text(base.with_suffix(".mmd"), self.to_mermaid()))
        if write_md:
            outputs.append(_write_text(base.with_suffix(".md"), self.to_markdown()))
        if write_svg:
            outputs.append(_write_text(base.with_suffix(".svg"), self.to_svg()))
        return outputs


def load_hci_sequence(path: Path) -> HciSequenceDiagram:
    """Load one Analyzer JSONL log and build its message sequence."""
    messages: list[SequenceMessage] = []
    pending_commands: dict[int, list[int]] = {}

    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            direction = _normalize_direction(record.get("direction"))
            if direction is None:
                continue
            raw_hex = str(record.get("raw_data") or "").strip().upper()
            result = record.get("result")
            result = result if isinstance(result, dict) else {}

            if direction == "host_to_controller":
                label, opcode = _command_label(result, raw_hex)
                message = SequenceMessage(direction, label, raw_hex, opcode)
                messages.append(message)
                if opcode is not None:
                    pending_commands.setdefault(opcode, []).append(len(messages) - 1)
                continue

            label, opcode = _event_label(result, raw_hex)
            response_to = None
            if opcode is not None:
                candidates = pending_commands.get(opcode)
                if candidates:
                    response_to = candidates.pop()
                command_name = _command_name_from_result(result)
                if command_name:
                    label = f"{label} for {_display_name(command_name)}"
                else:
                    label = f"{label} for opcode 0x{opcode:04X}"
            messages.append(
                SequenceMessage(
                    direction,
                    label,
                    raw_hex,
                    opcode,
                    response_to,
                )
            )
    return HciSequenceDiagram(path, tuple(messages))


def _normalize_direction(value: object) -> SequenceDirection | None:
    normalized = str(value or "").strip().lower()
    aliases = {
        "host_to_controller": "host_to_controller",
        "host_to_ctrl": "host_to_controller",
        "controller_to_host": "controller_to_host",
        "ctrl_to_host": "controller_to_host",
    }
    return aliases.get(normalized)  # type: ignore[return-value]


def _command_label(result: dict[str, Any], raw_hex: str) -> tuple[str, int | None]:
    decoded = _decoded(result)
    error_details = _error_details(result)
    opcode = _int_value(decoded.get("opcode_value"))
    if opcode is None:
        opcode = _int_value(error_details.get("opcode_value"))
    if opcode is None:
        opcode = _raw_command_opcode(raw_hex)
    name = decoded.get("display_name") or decoded.get("command_name")
    if name:
        params = decoded.get("parameters")
        summary = _parameter_summary(params if isinstance(params, dict) else {})
        label = _display_name(str(name))
        if summary:
            label += f" ({summary})"
        return label, opcode
    if opcode is not None:
        prefix = "Vendor Command" if (opcode >> 10) == 0x3F else "Unknown Command"
        return f"{prefix} 0x{opcode:04X} [{_raw_label(raw_hex)}]", opcode
    return f"HCI Command [{_raw_label(raw_hex)}]", None


def _event_label(result: dict[str, Any], raw_hex: str) -> tuple[str, int | None]:
    decoded = _decoded(result)
    error_details = _error_details(result)
    event_name = decoded.get("event_name")
    event_code = _raw_event_code(raw_hex)
    opcode = _int_value(decoded.get("command_opcode_value"))
    if opcode is None:
        opcode = _hex_or_int(error_details.get("command_opcode"))
    if opcode is None:
        opcode = _raw_response_opcode(raw_hex)

    inferred_response_name = {
        0x0E: "HCI_Command_Complete",
        0x0F: "HCI_Command_Status",
    }.get(event_code)
    if event_name in ("HCI_Command_Complete", "HCI_Command_Status") or (
        not event_name and inferred_response_name is not None
    ):
        response_name = str(event_name or inferred_response_name)
        status = decoded.get("status")
        if not isinstance(status, int):
            status = _raw_event_status(raw_hex)
        suffix = f", status=0x{status:02X}" if isinstance(status, int) else ""
        return f"{response_name}{suffix}", opcode
    if event_name == "HCI_LE_Meta_Event" or (
        not event_name and event_code == 0x3E
    ):
        subevent = decoded.get("subevent_name")
        if subevent and subevent != "Unknown LE Meta Event":
            return str(subevent), None
        code = decoded.get("subevent_code")
        if code is None:
            code = _raw_meta_subevent(raw_hex)
        return f"HCI_LE_Meta_Event subevent={code or 'unknown'}", None
    if event_name and event_name != "Unknown HCI Event":
        return str(event_name), opcode
    if event_code == 0xFF:
        return f"Vendor Event [{_raw_label(raw_hex)}]", None
    if event_code is not None:
        return f"Unknown Event 0x{event_code:02X} [{_raw_label(raw_hex)}]", opcode
    return f"HCI Event [{_raw_label(raw_hex)}]", opcode


def _command_name_from_result(result: dict[str, Any]) -> str | None:
    decoded = _decoded(result)
    value = decoded.get("command_name")
    return str(value) if value else None


def _decoded(result: dict[str, Any]) -> dict[str, Any]:
    value = result.get("decoded")
    return value if isinstance(value, dict) else {}


def _error_details(result: dict[str, Any]) -> dict[str, Any]:
    error = result.get("error")
    if not isinstance(error, dict):
        return {}
    details = error.get("details")
    return details if isinstance(details, dict) else {}


def _parameter_summary(params: dict[str, Any]) -> str:
    preferred = (
        ("tx_channel", "TX Ch"),
        ("rx_channel", "RX Ch"),
        ("frequency_mhz", "MHz"),
        ("test_data_length", "Len"),
        ("phy_name", "PHY"),
        ("num_packets", "Packets"),
    )
    parts: list[str] = []
    for key, label in preferred:
        if key not in params:
            continue
        value = params[key]
        if key == "frequency_mhz":
            parts.append(f"{value} MHz")
        else:
            parts.append(f"{label}={value}")
    return ", ".join(parts[:4])


def _raw_bytes(raw_hex: str) -> bytes:
    try:
        return bytes.fromhex(raw_hex)
    except ValueError:
        return b""


def _raw_command_opcode(raw_hex: str) -> int | None:
    raw = _raw_bytes(raw_hex)
    if len(raw) >= 3 and raw[0] == 0x01:
        return int.from_bytes(raw[1:3], "little")
    return None


def _raw_event_code(raw_hex: str) -> int | None:
    raw = _raw_bytes(raw_hex)
    return raw[1] if len(raw) >= 2 and raw[0] == 0x04 else None


def _raw_response_opcode(raw_hex: str) -> int | None:
    raw = _raw_bytes(raw_hex)
    if len(raw) >= 6 and raw[0:2] == b"\x04\x0E":
        return int.from_bytes(raw[4:6], "little")
    if len(raw) >= 7 and raw[0:2] == b"\x04\x0F":
        return int.from_bytes(raw[5:7], "little")
    return None


def _raw_meta_subevent(raw_hex: str) -> str | None:
    raw = _raw_bytes(raw_hex)
    if len(raw) >= 4 and raw[0:2] == b"\x04\x3E":
        return f"0x{raw[3]:02X}"
    return None


def _raw_event_status(raw_hex: str) -> int | None:
    raw = _raw_bytes(raw_hex)
    if len(raw) >= 7 and raw[0:2] == b"\x04\x0E":
        return raw[6]
    if len(raw) >= 4 and raw[0:2] == b"\x04\x0F":
        return raw[3]
    return None


def _raw_label(raw_hex: str, limit: int = 48) -> str:
    if not raw_hex:
        return "no raw data"
    return raw_hex if len(raw_hex) <= limit else f"{raw_hex[:limit]}..."


def _int_value(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _hex_or_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _display_name(value: str) -> str:
    return value.replace("[v", " [v")


def _mermaid_text(value: str) -> str:
    return value.replace("\n", " ").replace(":", "&#58;")


def _svg_actor(x: int, label: str) -> str:
    return (
        f'<rect x="{x-70}" y="12" width="140" height="36" rx="5" '
        'fill="#E8F0FE" stroke="#356AC3"/>'
        f'<text x="{x}" y="35" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="15">'
        f"{html.escape(label)}</text>"
    )


def _svg_label(label: str, x: int, y: int) -> list[str]:
    escaped = html.escape(label)
    max_chars = 90
    chunks = [
        escaped[index : index + max_chars]
        for index in range(0, len(escaped), max_chars)
    ] or [""]
    return [
        f'<text x="{x}" y="{y + offset * 14}" text-anchor="middle" '
        'font-family="Consolas, monospace" font-size="12" fill="#111">'
        f"{chunk}</text>"
        for offset, chunk in enumerate(chunks[:2])
    ]


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _image_font(
    size: int,
    *,
    bold: bool = False,
    monospace: bool = False,
) -> ImageFont.ImageFont:
    candidates: tuple[str, ...]
    if monospace:
        candidates = ("consola.ttf", "DejaVuSansMono.ttf")
    elif bold:
        candidates = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
    else:
        candidates = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_image_actor(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    font: ImageFont.ImageFont,
) -> None:
    draw.rounded_rectangle(
        (x - 70, y, x + 70, y + 36),
        radius=5,
        fill="#E8F0FE",
        outline="#356AC3",
        width=2,
    )
    box = draw.textbbox((0, 0), label, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    draw.text(
        (x - text_width / 2, y + (36 - text_height) / 2 - box[1]),
        label,
        fill="#111111",
        font=font,
    )


def _draw_image_arrow(
    draw: ImageDraw.ImageDraw,
    start_x: int,
    end_x: int,
    y: int,
) -> None:
    draw.line((start_x, y, end_x, y), fill="#333333", width=2)
    direction = 1 if end_x > start_x else -1
    draw.polygon(
        (
            (end_x, y),
            (end_x - direction * 12, y - 6),
            (end_x - direction * 12, y + 6),
        ),
        fill="#333333",
    )


def _draw_centered_image_text(
    draw: ImageDraw.ImageDraw,
    label: str,
    center_x: int,
    y: int,
    font: ImageFont.ImageFont,
) -> None:
    visible = label if len(label) <= 100 else f"{label[:97]}..."
    box = draw.textbbox((0, 0), visible, font=font)
    text_width = box[2] - box[0]
    draw.text(
        (center_x - text_width / 2, y),
        visible,
        fill="#111111",
        font=font,
    )
