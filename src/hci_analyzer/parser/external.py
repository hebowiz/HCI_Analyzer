"""Validate H4 envelopes for externally defined commands and responses."""

from hci_analyzer.models import ParseResult


def parse_external_envelope(frame: bytes, opcodes: frozenset[int]) -> ParseResult | None:
    """Accept only complete frames for explicitly registered external opcodes."""
    if len(frame) >= 4 and frame[0] == 0x01 and len(frame) == 4 + frame[3]:
        opcode = int.from_bytes(frame[1:3], "little")
        if opcode not in opcodes:
            return None
        return ParseResult(True, "HCI_Command", frame, decoded={
            "packet_indicator": "0x01", "opcode": f"0x{opcode:04X}",
            "opcode_value": opcode, "ogf": opcode >> 10, "ocf": opcode & 0x03FF,
            "parameter_total_length": frame[3],
            "vendor_specific": opcode >> 10 == 0x3F,
            "command_name": f"External_Command_0x{opcode:04X}",
            "parameters": {"raw_hex": frame[4:].hex(" ").upper()},
        })
    if len(frame) < 3 or frame[0] != 0x04 or len(frame) != 3 + frame[2]:
        return None
    if frame[1] == 0x0E and len(frame) >= 6:
        opcode = int.from_bytes(frame[4:6], "little")
        fields = {
            "event_name": "HCI_Command_Complete",
            "num_hci_command_packets": frame[3],
            "return_parameters": list(frame[6:]),
            "return_parameters_hex": frame[6:].hex(" ").upper(),
        }
        if len(frame) > 6:
            fields["status"] = frame[6]
    elif frame[1] == 0x0F and len(frame) == 7:
        opcode = int.from_bytes(frame[5:7], "little")
        fields = {
            "event_name": "HCI_Command_Status", "status": frame[3],
            "num_hci_command_packets": frame[4],
        }
    else:
        return None
    if opcode not in opcodes:
        return None
    return ParseResult(True, "HCI_Event", frame, decoded={
        "packet_indicator": "0x04", "event_code": f"0x{frame[1]:02X}",
        "event_code_value": frame[1], "parameter_total_length": frame[2],
        "command_opcode": f"0x{opcode:04X}", "command_opcode_value": opcode,
        "command_name": f"External_Command_0x{opcode:04X}",
        "vendor_specific": opcode >> 10 == 0x3F, **fields,
    })
