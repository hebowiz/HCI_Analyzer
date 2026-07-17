"""Bidirectional serial transport for sending commands and receiving events."""

import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import serial

from hci_analyzer.models import ParseResult, SerialPortConfig
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.parser.h4_stream import H4StreamDecoder
from hci_analyzer.presentation.text import format_exception_for_log


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
    response_time_ms: float | None = None
    message: str | None = None


TransportEventCallback = Callable[[TransportEvent], None]


@dataclass(slots=True)
class _PendingTransaction:
    transaction_id: int
    frame: bytes
    opcode: int | None
    timeout_seconds: float
    sent_at_monotonic: float | None = None


class HciSerialTransport:
    """Own a serial port and perform queued command TX and event RX."""

    def __init__(
        self,
        on_event: TransportEventCallback,
        parser: HciParser | None = None,
    ) -> None:
        self._on_event = on_event
        self._parser = parser or HciParser()
        self._decoder = H4StreamDecoder()
        self._serial: serial.Serial | None = None
        self._config: SerialPortConfig | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._tx_queue: queue.Queue[_PendingTransaction] = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._pending: _PendingTransaction | None = None
        self._next_transaction_id = 1
        self._connected = False

    @property
    def connected(self) -> bool:
        """Return whether the serial transport is connected."""
        with self._lock:
            return self._connected

    def connect(self, config: SerialPortConfig) -> None:
        """Open the serial port and start background transport processing."""
        with self._lock:
            if self._connected:
                raise RuntimeError("Serial transport is already connected")

        port = serial.Serial(
            port=config.port,
            baudrate=config.baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
            write_timeout=1.0,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

        self._decoder.reset()
        self._stop_event.clear()
        self._clear_tx_queue()
        with self._lock:
            self._serial = port
            self._config = config
            self._pending = None
            self._connected = True
        self._thread = threading.Thread(
            target=self._worker_loop,
            name=f"hci-console-{config.port}",
            daemon=True,
        )
        self._thread.start()
        self._emit(
            TransportEventKind.CONNECTED,
            source=config.label,
            message=f"Connected to {config.port} at {config.baud_rate} baud",
        )

    def disconnect(self) -> None:
        """Stop background processing and close the serial port."""
        self._stop_event.set()
        port = self._serial
        if port is not None:
            try:
                port.cancel_read()
            except (AttributeError, serial.SerialException):
                pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._close_port()

    def send(
        self,
        frame: bytes,
        *,
        expected_opcode: int | None = None,
        response_timeout_seconds: float | None = None,
    ) -> int:
        """Queue a command and return its transaction identifier."""
        if not frame or frame[0] != 0x01:
            raise ValueError("Only complete H4 Command packets can be sent")
        timeout = 3.0 if response_timeout_seconds is None else response_timeout_seconds
        if timeout <= 0:
            raise ValueError("Response timeout must be greater than zero")

        with self._lock:
            if not self._connected:
                raise RuntimeError("Serial transport is not connected")
            if self._pending is not None:
                raise RuntimeError("A command response is already pending")
            transaction_id = self._next_transaction_id
            self._next_transaction_id += 1
            pending = _PendingTransaction(
                transaction_id,
                bytes(frame),
                expected_opcode,
                timeout,
            )
            self._pending = pending
        try:
            self._tx_queue.put_nowait(pending)
        except queue.Full:
            with self._lock:
                if self._pending is pending:
                    self._pending = None
            raise RuntimeError("The command transmit queue is full")
        return transaction_id

    def _worker_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._transmit_queued()
                self._receive_available()
                self._check_timeout()
        except (serial.SerialException, OSError) as exc:
            self._emit(
                TransportEventKind.ERROR,
                source=self._source,
                message=(
                    "Serial transport error: "
                    f"{format_exception_for_log(exc)}"
                ),
            )
        finally:
            pending = self._take_pending()
            if pending is not None and self._stop_event.is_set():
                self._emit(
                    TransportEventKind.ERROR,
                    source=self._source,
                    raw_data=pending.frame,
                    transaction_id=pending.transaction_id,
                    message="Pending transaction cancelled by disconnect",
                )
            leftover = self._decoder.take_pending_data()
            if leftover:
                self._emit(
                    TransportEventKind.ERROR,
                    source=self._source,
                    raw_data=leftover,
                    message="Disconnected with an incomplete H4 frame",
                )
            self._close_port()

    def _transmit_queued(self) -> None:
        try:
            pending = self._tx_queue.get_nowait()
        except queue.Empty:
            return
        port = self._serial
        if port is None:
            raise serial.SerialException("Serial port is not open")
        written = port.write(pending.frame)
        if written != len(pending.frame):
            raise serial.SerialTimeoutException(
                f"Partial serial write: {written}/{len(pending.frame)} bytes"
            )
        port.flush()
        pending.sent_at_monotonic = time.monotonic()
        parsed = self._parser.parse_bytes(pending.frame)
        self._emit(
            TransportEventKind.TRANSMITTED,
            source=self._source,
            raw_data=pending.frame,
            parsed=parsed,
            transaction_id=pending.transaction_id,
        )

    def _receive_available(self) -> None:
        port = self._serial
        if port is None:
            return
        waiting = port.in_waiting
        data = port.read(waiting or 1)
        if not data:
            return
        chunk = self._decoder.feed(data)
        for noise in chunk.discarded_noise:
            self._emit(
                TransportEventKind.ERROR,
                source=self._source,
                raw_data=noise,
                message="Discarded bytes before an H4 packet indicator",
            )
        for frame in chunk.frames:
            parsed = self._parser.parse_bytes(frame)
            transaction_id, response_time_ms = self._match_transaction(parsed)
            self._emit(
                TransportEventKind.RECEIVED,
                source=self._source,
                raw_data=frame,
                parsed=parsed,
                transaction_id=transaction_id,
                response_time_ms=response_time_ms,
            )

    def _match_transaction(
        self, parsed: ParseResult
    ) -> tuple[int | None, float | None]:
        pending = self._get_pending()
        if pending is None or not parsed.success:
            return None, None
        decoded = parsed.decoded
        opcode = decoded.get("command_opcode_value")
        if opcode != pending.opcode:
            return None, None

        event_name = decoded.get("event_name")
        response_time_ms = (
            (time.monotonic() - pending.sent_at_monotonic) * 1000
            if pending.sent_at_monotonic is not None
            else None
        )
        if event_name == "HCI_Command_Complete":
            self._clear_pending_if(pending)
            return pending.transaction_id, response_time_ms
        if event_name == "HCI_Command_Status":
            status = decoded.get("status")
            if status != 0:
                self._clear_pending_if(pending)
            return pending.transaction_id, response_time_ms
        return None, None

    def _check_timeout(self) -> None:
        pending = self._get_pending()
        if pending is None or pending.sent_at_monotonic is None:
            return
        if time.monotonic() - pending.sent_at_monotonic < pending.timeout_seconds:
            return
        if self._clear_pending_if(pending):
            self._emit(
                TransportEventKind.RESPONSE_TIMEOUT,
                source=self._source,
                raw_data=pending.frame,
                transaction_id=pending.transaction_id,
                message=f"No response received within {pending.timeout_seconds:.1f} seconds",
            )

    def _get_pending(self) -> _PendingTransaction | None:
        with self._lock:
            return self._pending

    def _take_pending(self) -> _PendingTransaction | None:
        with self._lock:
            pending, self._pending = self._pending, None
            return pending

    def _clear_pending_if(self, pending: _PendingTransaction) -> bool:
        with self._lock:
            if self._pending is not pending:
                return False
            self._pending = None
            return True

    def _close_port(self) -> None:
        with self._lock:
            port = self._serial
            config = self._config
            was_connected = self._connected
            self._serial = None
            self._config = None
            self._connected = False
            self._thread = None
        if port is not None and port.is_open:
            port.close()
        if was_connected:
            self._emit(
                TransportEventKind.DISCONNECTED,
                source=config.label if config else "Serial",
                message="Serial port disconnected",
            )

    def _clear_tx_queue(self) -> None:
        while True:
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                return

    @property
    def _source(self) -> str:
        config = self._config
        return config.label if config is not None else "Serial"

    def _emit(
        self,
        kind: TransportEventKind,
        *,
        source: str,
        raw_data: bytes = b"",
        parsed: ParseResult | None = None,
        transaction_id: int | None = None,
        response_time_ms: float | None = None,
        message: str | None = None,
    ) -> None:
        self._on_event(
            TransportEvent(
                timestamp=datetime.now().astimezone(),
                kind=kind,
                source=source,
                raw_data=raw_data,
                parsed=parsed,
                transaction_id=transaction_id,
                response_time_ms=response_time_ms,
                message=message,
            )
        )
