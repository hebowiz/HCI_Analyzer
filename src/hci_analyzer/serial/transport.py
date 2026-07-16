"""Bidirectional serial transport for sending commands and receiving events."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from hci_analyzer.models import ParseResult, SerialPortConfig


class TransportEventKind(str, Enum):
    """Kinds of events emitted by the bidirectional transport."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TRANSMITTED = "transmitted"
    RECEIVED = "received"
    ERROR = "error"
    RESPONSE_TIMEOUT = "response_timeout"


@dataclass(slots=True, frozen=True)
class TransportEvent:
    """One transport event consumed by the Command Console."""

    timestamp: datetime
    kind: TransportEventKind
    source: str
    raw_data: bytes = b""
    parsed: ParseResult | None = None
    transaction_id: int | None = None
    message: str | None = None


TransportEventCallback = Callable[[TransportEvent], None]


class HciSerialTransport:
    """Own a serial port and perform queued command TX and event RX."""

    def __init__(self, on_event: TransportEventCallback) -> None:
        self._on_event = on_event

    @property
    def connected(self) -> bool:
        """Return whether the serial transport is connected."""
        raise NotImplementedError

    def connect(self, config: SerialPortConfig) -> None:
        """Open the serial port and start background transport processing."""
        raise NotImplementedError

    def disconnect(self) -> None:
        """Stop background processing and close the serial port."""
        raise NotImplementedError

    def send(
        self,
        frame: bytes,
        *,
        expected_opcode: int | None = None,
        response_timeout_seconds: float | None = None,
    ) -> int:
        """Queue a command and return its transaction identifier."""
        raise NotImplementedError

