"""Human-readable summaries for parsed HCI commands and events."""

from __future__ import annotations

from typing import Any

from hci_analyzer.models import ParseResult


HCI_STATUS_NAMES = {
    0x00: "Success",
    0x01: "Unknown HCI Command",
    0x02: "Unknown Connection Identifier",
    0x05: "Authentication Failure",
    0x07: "Memory Capacity Exceeded",
    0x0C: "Command Disallowed",
    0x11: "Unsupported Feature or Parameter Value",
    0x12: "Invalid HCI Command Parameters",
    0x1A: "Unsupported Remote Feature",
    0x1F: "Unspecified Error",
}

PACKET_STATUS_NAMES = {
    0x00: "CRC OK",
    0x01: "CRC error; samples may be invalid",
    0x02: "Insufficient resources; samples may be incomplete",
}


def format_parse_summary(
    result: ParseResult,
    *,
    response_time_ms: float | None = None,
    iq_sample_preview_limit: int = 5,
) -> list[str]:
    """Return a readable SUMMARY block for one parser result."""
    if not result.success:
        return _format_error(result)
    if result.packet_type == "HCI_Command":
        return _format_command(result.decoded)
    if result.packet_type == "HCI_Event":
        return _format_event(
            result.decoded,
            response_time_ms=response_time_ms,
            iq_sample_preview_limit=iq_sample_preview_limit,
        )
    return [
        "SUMMARY",
        _field("Packet", result.packet_type or "Unknown"),
    ]


def _format_command(decoded: dict[str, Any]) -> list[str]:
    name = _display_name(decoded.get("display_name") or decoded.get("command_name"))
    lines = [
        "SUMMARY",
        _field("Command", name),
        _field("Opcode", decoded.get("opcode", "-")),
    ]
    params = decoded.get("parameters")
    if not isinstance(params, dict):
        return lines

    if name.startswith("HCI_LE_Transmitter_Test"):
        lines.extend(_format_transmitter_parameters(params))
    elif name.startswith("HCI_LE_Receiver_Test"):
        lines.extend(_format_receiver_parameters(params, name))
    elif name == "HCI_LE_Test_End":
        lines.append(_field("Purpose", "End the current LE Direct Test Mode test"))
    elif name == "HCI_Reset":
        lines.append(_field("Purpose", "Reset the Controller to standby state"))
    elif name.startswith("HCI_Read_Local_Supported_Commands"):
        length = 64 if "[v1]" in name else 251
        lines.append(
            _field("Purpose", f"Read the {length}-octet Supported Commands field")
        )
    elif params:
        lines.extend(_format_generic_parameters(params))
    return lines


def _format_transmitter_parameters(params: dict[str, Any]) -> list[str]:
    lines = [
        _channel_field("TX Channel", params, "tx_channel"),
        _field("Data Length", f"{params.get('test_data_length', '-')} bytes"),
        _enum_field(
            "Payload",
            params.get("packet_payload_name", "Unknown"),
            params.get("packet_payload"),
        ),
        _enum_field("PHY", params.get("phy_name", "Unknown"), params.get("phy")),
    ]
    if "cte_length" in params:
        lines.append(
            _duration_field(
                "CTE Length",
                params.get("cte_length"),
                params.get("cte_length_us"),
            )
        )
        lines.append(
            _enum_field(
                "CTE Type",
                params.get("cte_type_name", "Unknown"),
                params.get("cte_type"),
            )
        )
        lines.extend(_format_switching_pattern(params))
    if "tx_power_level" in params:
        power = params["tx_power_level"]
        raw = params.get("tx_power_level_raw")
        if power == "minimum":
            text = "Minimum supported power"
        elif power == "maximum":
            text = "Maximum supported power"
        else:
            text = f"{power} dBm"
        lines.append(_enum_field("TX Power", text, raw))
    return lines


def _format_receiver_parameters(
    params: dict[str, Any], command_name: str
) -> list[str]:
    lines = [_channel_field("RX Channel", params, "rx_channel")]
    if "[v1]" in command_name:
        lines.append(_field("PHY", "LE 1M PHY (implicit)"))
        return lines
    lines.extend(
        [
            _enum_field("PHY", params.get("phy_name", "Unknown"), params.get("phy")),
            _enum_field(
                "Modulation Index",
                params.get("modulation_index_name", "Unknown"),
                params.get("modulation_index"),
            ),
        ]
    )
    if "expected_cte_length" in params:
        lines.append(
            _duration_field(
                "Expected CTE Length",
                params.get("expected_cte_length"),
                params.get("expected_cte_length_us"),
            )
        )
        lines.append(
            _enum_field(
                "Expected CTE Type",
                params.get("expected_cte_type_name", "Unknown"),
                params.get("expected_cte_type"),
            )
        )
        lines.append(
            _field(
                "Slot Duration",
                f"{params.get('slot_durations_us', '-')} us",
            )
        )
        lines.extend(_format_switching_pattern(params))
    return lines


def _format_switching_pattern(params: dict[str, Any]) -> list[str]:
    antenna_ids = params.get("antenna_ids", [])
    count = params.get("switching_pattern_length", len(antenna_ids))
    ids = ", ".join(str(value) for value in antenna_ids) or "-"
    return [
        _field("Switching Pattern", f"{count} antennas"),
        _field("  Antenna IDs", ids),
    ]


def _format_event(
    decoded: dict[str, Any],
    *,
    response_time_ms: float | None,
    iq_sample_preview_limit: int,
) -> list[str]:
    event_name = decoded.get("event_name", "Unknown HCI Event")
    if event_name in ("HCI_Command_Complete", "HCI_Command_Status"):
        return _format_command_response(decoded, response_time_ms)
    if decoded.get("subevent_name") == "HCI_LE_Connectionless_IQ_Report":
        return _format_iq_report(decoded, iq_sample_preview_limit)

    lines = ["SUMMARY", _field("Event", event_name)]
    if "subevent_name" in decoded:
        lines.append(_field("Subevent", decoded["subevent_name"]))
    if "parameters_hex" in decoded:
        lines.append(_field("Parameters", decoded["parameters_hex"] or "-"))
    if "subevent_parameters_hex" in decoded:
        lines.append(
            _field("Parameters", decoded["subevent_parameters_hex"] or "-")
        )
    return lines


def _format_command_response(
    decoded: dict[str, Any], response_time_ms: float | None
) -> list[str]:
    event_name = decoded.get("event_name", "HCI Event")
    status = decoded.get("status")
    lines = [
        "SUMMARY",
        _field("Event", event_name),
        _field(
            "For Command",
            f"{_display_name(decoded.get('command_name'))} "
            f"({decoded.get('command_opcode', '-')})",
        ),
        _field("Status", _status_text(status)),
    ]
    if response_time_ms is not None:
        lines.append(_field("Response Time", f"{response_time_ms:.1f} ms"))

    if decoded.get("rf_test_event") == "LE_Packet_Report":
        lines.append(_field("Received Packets", decoded.get("num_packets", "-")))
    if decoded.get("response_type") == "Supported_Commands":
        lines.extend(_format_supported_commands(decoded))
    if decoded.get("vendor_specific"):
        lines.append(
            _field(
                "Return Parameters",
                decoded.get("return_parameters_hex", "-") or "-",
            )
        )
    if event_name == "HCI_Command_Status":
        completion = (
            "Command accepted; completion event may follow"
            if status == 0
            else "Command was not started"
        )
        lines.append(_field("Completion", completion))
    return lines


def _format_supported_commands(decoded: dict[str, Any]) -> list[str]:
    lines = [
        _field(
            "Response",
            "Supported Commands, "
            f"{decoded.get('supported_commands_length', '-')} octets",
        ),
        _field("Set Bits", decoded.get("set_bit_count", "-")),
        "",
        "  Application Commands:",
    ]
    support = decoded.get("application_command_support", {})
    if isinstance(support, dict):
        for command, supported in support.items():
            state = "Supported" if supported else "Unsupported"
            lines.append(f"    {state:<11} {_display_name(command)}")

    by_scope = decoded.get("supported_commands_by_scope", {})
    if isinstance(by_scope, dict):
        lines.append("")
        lines.append(
            _field(
                "Other Standard Commands",
                len(by_scope.get("OTHER_STANDARD", [])),
            )
        )
        lines.append(
            _field("Previously Used Bits", len(by_scope.get("PREVIOUSLY_USED", [])))
        )
        lines.append(_field("Reserved Bits", len(by_scope.get("RESERVED", []))))
    return lines


def _format_iq_report(
    decoded: dict[str, Any], preview_limit: int
) -> list[str]:
    params = decoded.get("parameters", {})
    if not isinstance(params, dict):
        params = {}
    packet_status = params.get("packet_status")
    lines = [
        "SUMMARY",
        _field("Event", decoded.get("subevent_name", "HCI LE Meta Event")),
        _field("Sync Handle", _hex_value(params.get("sync_handle"), 4)),
        _field("Channel Index", params.get("channel_index", "-")),
        _field("RSSI", f"{params.get('rssi_dbm', '-')} dBm"),
        _field("RSSI Antenna", params.get("rssi_antenna_id", "-")),
        _field("CTE Type", _cte_type_name(params.get("cte_type"))),
        _field("Slot Duration", f"{params.get('slot_durations_us', '-')} us"),
        _field(
            "Packet Status",
            _enum_text(
                PACKET_STATUS_NAMES.get(packet_status, "Unknown"),
                packet_status,
            ),
        ),
        _field("Event Counter", params.get("event_counter", "-")),
        _field("IQ Samples", f"{params.get('sample_count', 0)} pairs"),
    ]
    samples = params.get("samples", [])
    if isinstance(samples, list) and samples:
        lines.append("  Sample Preview:")
        for index, sample in enumerate(samples[:preview_limit]):
            lines.append(
                f"    #{index:<3} I={sample.get('i', 0):>4}  "
                f"Q={sample.get('q', 0):>4}"
            )
        remaining = len(samples) - preview_limit
        if remaining > 0:
            lines.append(f"    ... {remaining} more samples")
    return lines


def _format_error(result: ParseResult) -> list[str]:
    error = result.error
    if error is None:
        return ["SUMMARY", _field("Error", "Unknown parser error")]
    lines = [
        "SUMMARY",
        _field("Error", error.code),
        _field("Message", error.message),
    ]
    if error.details:
        lines.extend(_format_generic_parameters(error.details))
    return lines


def _format_generic_parameters(params: dict[str, Any]) -> list[str]:
    return [
        _field(_humanize(key), value)
        for key, value in params.items()
        if not isinstance(value, (dict, list))
    ]


def _field(label: str, value: object) -> str:
    return f"  {label:<23}: {value}"


def _channel_field(
    label: str, params: dict[str, Any], channel_key: str
) -> str:
    channel = params.get(channel_key, "-")
    frequency = params.get("frequency_mhz")
    text = f"{channel}"
    if frequency is not None:
        text += f" ({frequency} MHz)"
    return _field(label, text)


def _duration_field(label: str, raw: object, microseconds: object) -> str:
    if microseconds is None:
        return _field(label, f"None (value={raw})")
    return _field(label, f"{microseconds} us (value={raw})")


def _enum_field(label: str, name: object, value: object) -> str:
    return _field(label, _enum_text(name, value))


def _enum_text(name: object, value: object) -> str:
    if isinstance(value, int):
        return f"{name} (0x{value:02X})"
    return str(name)


def _status_text(status: object) -> str:
    if not isinstance(status, int):
        return "Unknown"
    name = HCI_STATUS_NAMES.get(status, "Unknown HCI status")
    prefix = "" if status == 0 else "ERROR - "
    return f"{prefix}{name} (0x{status:02X})"


def _cte_type_name(value: object) -> str:
    names = {
        0x00: "AoA CTE",
        0x01: "AoD CTE with 1 us slots",
        0x02: "AoD CTE with 2 us slots",
    }
    return _enum_text(names.get(value, "Unknown"), value)


def _display_name(value: object) -> str:
    return str(value or "Unknown").replace("[v", " [v")


def _hex_value(value: object, width: int) -> str:
    return f"0x{value:0{width}X}" if isinstance(value, int) else "-"


def _humanize(value: str) -> str:
    return value.replace("_", " ").title()
