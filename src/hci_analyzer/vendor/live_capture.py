"""Real-time capture storage for HCI commands, events, and RACE packets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from hci_analyzer.models import LogRecord
from hci_analyzer.vendor.discovery import VendorCapture


@dataclass(slots=True)
class DiscoveryCapture:
    """One chronologically captured item shown by Vendor Discovery."""

    capture_id: str
    timestamp: str
    source: str
    protocol: str
    raw_data: bytes
    vendor_capture: VendorCapture | None = None
    hci_event_name: str | None = None
    related_opcode: int | None = None
    hci_event_parameters: bytes = b""
    race_type: int | None = None
    race_command_id: int | None = None
    race_payload: bytes = b""

    @property
    def analyzable(self) -> bool:
        """Return whether this item can participate in HCI parameter inference."""
        return self.vendor_capture is not None

    @property
    def opcode(self) -> int | None:
        """Return the command or related-response opcode, if applicable."""
        if self.vendor_capture is not None:
            return self.vendor_capture.opcode
        return self.related_opcode

    @property
    def identifier(self) -> str:
        """Return a compact protocol-specific identifier."""
        if self.vendor_capture is not None:
            return f"0x{self.vendor_capture.opcode:04X}"
        if self.protocol == "HCI Event":
            if self.related_opcode is not None:
                return (
                    f"{self.hci_event_name or 'HCI Event'} / "
                    f"0x{self.related_opcode:04X}"
                )
            return self.hci_event_name or "HCI Event"
        if self.protocol == "RACE" and self.race_command_id is not None:
            return f"Type 0x{self.race_type:02X} / ID 0x{self.race_command_id:04X}"
        return "-"

    @property
    def parameters(self) -> bytes:
        """Return the bytes displayed as command parameters or payload."""
        if self.vendor_capture is not None:
            return self.vendor_capture.parameters
        if self.protocol == "HCI Event":
            return self.hci_event_parameters
        return self.race_payload

    def group_key(self) -> tuple[object, ...]:
        """Return the key used by the optional duplicate-grouped view."""
        return (
            self.protocol,
            self.opcode,
            self.hci_event_name,
            self.race_type,
            self.race_command_id,
            self.parameters,
        )


@dataclass(slots=True, frozen=True)
class DiscoveryCaptureGroup:
    """One row in chronological or duplicate-grouped display mode."""

    entries: tuple[DiscoveryCapture, ...]

    @property
    def first(self) -> DiscoveryCapture:
        return self.entries[0]

    @property
    def count(self) -> int:
        return len(self.entries)


class LiveCaptureStore:
    """Maintain captured commands in arrival order with reversible removal."""

    def __init__(self) -> None:
        self._entries: list[DiscoveryCapture] = []
        self._removed_stack: list[list[tuple[int, DiscoveryCapture]]] = []
        self._next_id = 1
        self._pending_by_opcode: dict[int, list[VendorCapture]] = {}
        self._latest_vendor: VendorCapture | None = None

    @property
    def entries(self) -> tuple[DiscoveryCapture, ...]:
        """Return all active captures in chronological order."""
        return tuple(self._entries)

    @property
    def can_restore(self) -> bool:
        return bool(self._removed_stack)

    def add_record(self, record: LogRecord) -> DiscoveryCapture | None:
        """Add a supported parsed record and return the displayed capture."""
        result = record.result
        if result is None:
            return None
        if result.packet_type == "HCI_Event" and record.raw_data[:1] == b"\x04":
            related_opcode = self._associate_response(record.raw_data)
            decoded = result.decoded
            if not decoded and result.error is not None:
                decoded = result.error.details
            event_name = str(decoded.get("event_name") or "Unknown HCI Event")
            if decoded.get("subevent_name"):
                event_name = str(decoded["subevent_name"])
            entry = DiscoveryCapture(
                capture_id=self._new_id("event"),
                timestamp=record.timestamp.isoformat(timespec="milliseconds"),
                source=record.source,
                protocol="HCI Event",
                raw_data=record.raw_data,
                hci_event_name=event_name,
                related_opcode=related_opcode,
                hci_event_parameters=(
                    record.raw_data[3:] if len(record.raw_data) >= 3 else b""
                ),
            )
            self._append_chronological(entry)
            return entry
        if result.packet_type == "HCI_Command":
            raw = record.raw_data
            if len(raw) < 4 or raw[0] != 0x01 or len(raw) != 4 + raw[3]:
                return None
            opcode = int.from_bytes(raw[1:3], "little")
            parameters = record.raw_data[4:] if len(record.raw_data) >= 4 else b""
            vendor = VendorCapture(
                capture_id=self._new_id("vendor"),
                source_path=Path("<live>"),
                line_number=self._next_id - 1,
                timestamp=record.timestamp.isoformat(timespec="milliseconds"),
                source=record.source,
                opcode=opcode,
                parameters=parameters,
                raw_data=record.raw_data,
            )
            entry = DiscoveryCapture(
                capture_id=vendor.capture_id,
                timestamp=vendor.timestamp,
                source=vendor.source,
                protocol="HCI Vendor" if opcode >> 10 == 0x3F else "HCI Command",
                raw_data=record.raw_data,
                vendor_capture=vendor,
            )
            self._append_chronological(entry)
            self._pending_by_opcode.setdefault(opcode, []).append(vendor)
            if opcode >> 10 == 0x3F:
                self._latest_vendor = vendor
            return entry
        if not result.success:
            return None
        if result.packet_type == "RACE":
            decoded = result.decoded
            entry = DiscoveryCapture(
                capture_id=self._new_id("race"),
                timestamp=record.timestamp.isoformat(timespec="milliseconds"),
                source=record.source,
                protocol="RACE",
                raw_data=record.raw_data,
                race_type=_integer_value(decoded.get("type")),
                race_command_id=_integer_value(decoded.get("command_id")),
                race_payload=record.raw_data[6:] if len(record.raw_data) >= 6 else b"",
            )
            self._append_chronological(entry)
            return entry
        return None

    def add_vendor_captures(
        self,
        captures: Iterable[VendorCapture],
    ) -> list[DiscoveryCapture]:
        """Append captures loaded from legacy Analyzer JSONL."""
        added: list[DiscoveryCapture] = []
        for capture in sorted(captures, key=lambda item: item.timestamp):
            capture.capture_id = self._new_id("vendor")
            entry = DiscoveryCapture(
                capture_id=capture.capture_id,
                timestamp=capture.timestamp,
                source=capture.source,
                protocol=(
                    "HCI Vendor" if capture.opcode >> 10 == 0x3F else "HCI Command"
                ),
                raw_data=capture.raw_data,
                vendor_capture=capture,
            )
            self._append_chronological(entry)
            added.append(entry)
        return added

    def replace_entries(self, entries: Iterable[DiscoveryCapture]) -> None:
        """Replace the current session, as when opening a saved project."""
        self._entries = sorted(
            entries,
            key=lambda entry: (entry.timestamp, entry.capture_id),
        )
        self._removed_stack.clear()
        self._pending_by_opcode.clear()
        self._latest_vendor = None
        self._next_id = len(self._entries) + 1

    def groups(self, *, group_duplicates: bool = False) -> list[DiscoveryCaptureGroup]:
        """Return rows, preserving arrival order by default."""
        if not group_duplicates:
            return [DiscoveryCaptureGroup((entry,)) for entry in self._entries]
        grouped: dict[tuple[object, ...], list[DiscoveryCapture]] = {}
        order: list[tuple[object, ...]] = []
        for entry in self._entries:
            key = entry.group_key()
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(entry)
        return [
            DiscoveryCaptureGroup(tuple(grouped[key]))
            for key in order
        ]

    def remove(self, capture_ids: Iterable[str]) -> int:
        """Remove selected captures while retaining one-step-at-a-time undo data."""
        selected = set(capture_ids)
        removed = [
            (index, entry)
            for index, entry in enumerate(self._entries)
            if entry.capture_id in selected
        ]
        if not removed:
            return 0
        self._entries = [
            entry for entry in self._entries if entry.capture_id not in selected
        ]
        self._removed_stack.append(removed)
        return len(removed)

    def restore_last_removed(self) -> int:
        """Restore the most recently removed set at its original positions."""
        if not self._removed_stack:
            return 0
        removed = self._removed_stack.pop()
        for index, entry in sorted(removed, key=lambda item: item[0]):
            self._entries.insert(min(index, len(self._entries)), entry)
        return len(removed)

    def vendor_opcodes(self) -> tuple[int, ...]:
        """Return all HCI command opcodes (legacy public method name)."""
        return tuple(
            sorted(
                {
                    entry.vendor_capture.opcode
                    for entry in self._entries
                    if entry.vendor_capture is not None
                }
            )
        )

    def vendor_captures(self, opcode: int) -> list[VendorCapture]:
        """Return standard or vendor command captures for the selected opcode."""
        return [
            entry.vendor_capture
            for entry in self._entries
            if entry.opcode == opcode and entry.vendor_capture is not None
        ]

    def _associate_response(self, raw_data: bytes) -> int | None:
        opcode = _response_opcode(raw_data)
        if opcode is not None:
            pending = self._pending_by_opcode.get(opcode, [])
            if pending:
                pending.pop(0).responses.append(raw_data)
            return opcode
        if (
            len(raw_data) >= 3
            and raw_data[0] == 0x04
            and raw_data[1] == 0xFF
            and self._latest_vendor is not None
        ):
            self._latest_vendor.responses.append(raw_data)
            return self._latest_vendor.opcode
        return opcode

    def _new_id(self, prefix: str) -> str:
        existing = {entry.capture_id for entry in self._entries}
        while True:
            capture_id = f"{prefix}:{self._next_id}"
            self._next_id += 1
            if capture_id not in existing:
                return capture_id

    def _append_chronological(self, entry: DiscoveryCapture) -> None:
        self._entries.append(entry)
        self._entries.sort(
            key=lambda item: (item.timestamp, item.capture_id),
        )


def _response_opcode(raw: bytes) -> int | None:
    if len(raw) < 3 or raw[0] != 0x04 or len(raw) != 3 + raw[2]:
        return None
    if len(raw) >= 6 and raw[0] == 0x04 and raw[1] == 0x0E:
        return int.from_bytes(raw[4:6], "little")
    if len(raw) >= 7 and raw[0] == 0x04 and raw[1] == 0x0F:
        return int.from_bytes(raw[5:7], "little")
    return None


def _integer_value(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None
