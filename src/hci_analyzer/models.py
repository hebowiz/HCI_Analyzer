"""Shared data structures used by the analyzer layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any


class H4PacketIndicator(IntEnum):
    """UART HCI H4 packet indicators."""

    COMMAND = 0x01
    ACL_DATA = 0x02
    SYNCHRONOUS_DATA = 0x03
    EVENT = 0x04
    ISO_DATA = 0x05


class TrafficDirection(str, Enum):
    """Logical traffic direction shown in logs."""

    HOST_TO_CONTROLLER = "host_to_controller"
    CONTROLLER_TO_HOST = "controller_to_host"
    UNKNOWN = "unknown"
    MANUAL = "manual"


class RecordKind(str, Enum):
    """Kinds of records emitted by the application."""

    PACKET = "packet"
    ERROR = "error"
    NOISE = "noise"
    SYSTEM = "system"


@dataclass(slots=True, frozen=True)
class SerialPortConfig:
    """Configuration for one monitored serial port."""

    port: str
    baud_rate: int
    label: str


@dataclass(slots=True)
class ParseError:
    """Structured parser error."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    """Structured result returned by command and event parsers."""

    success: bool
    packet_type: str | None
    raw_data: bytes
    decoded: dict[str, Any] = field(default_factory=dict)
    error: ParseError | None = None


@dataclass(slots=True)
class LogRecord:
    """One GUI and JSONL log entry."""

    timestamp: datetime
    source: str
    direction: TrafficDirection
    kind: RecordKind
    raw_data: bytes = b""
    result: ParseResult | None = None
    message: str | None = None


@dataclass(slots=True, frozen=True)
class LogSession:
    """Information about one analysis session."""

    started_at: datetime
    file_path: Path

