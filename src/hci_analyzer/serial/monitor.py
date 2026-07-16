"""Background monitoring for two receive-only serial ports."""

import threading
from collections.abc import Callable
from datetime import datetime

import serial

from hci_analyzer.models import (
    H4PacketIndicator,
    LogRecord,
    ParseError,
    ParseResult,
    RecordKind,
    SerialPortConfig,
    TrafficDirection,
)
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.parser.h4_stream import H4StreamDecoder

RecordCallback = Callable[[LogRecord], None]


class SerialPortWorker:
    """Receive bytes from one serial port on a background thread."""

    def __init__(
        self,
        config: SerialPortConfig,
        on_record: RecordCallback,
        parser: HciParser | None = None,
    ) -> None:
        self._config = config
        self._on_record = on_record
        self._parser = parser or HciParser()
        self._decoder = H4StreamDecoder()
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Open the port and start its receive thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._decoder.reset()
        self._stop_event.clear()
        self._serial = serial.Serial(
            port=self._config.port,
            baudrate=self._config.baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        self._thread = threading.Thread(
            target=self._receive_loop,
            name=f"hci-serial-{self._config.label}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop reception and close the port."""
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
        if port is not None and port.is_open:
            port.close()
        self._serial = None
        self._thread = None

    def _receive_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                port = self._serial
                if port is None:
                    break
                waiting = port.in_waiting
                data = port.read(waiting or 1)
                if data:
                    self._process_bytes(data)
        except (serial.SerialException, OSError) as exc:
            self._on_record(
                LogRecord(
                    timestamp=datetime.now().astimezone(),
                    source=self._config.label,
                    direction=TrafficDirection.UNKNOWN,
                    kind=RecordKind.ERROR,
                    result=ParseResult(
                        False,
                        None,
                        b"",
                        error=ParseError(
                            "SERIAL_READ_ERROR",
                            str(exc),
                            {"port": self._config.port},
                        ),
                    ),
                )
            )
        finally:
            pending = self._decoder.take_pending_data()
            if pending:
                self._on_record(
                    LogRecord(
                        timestamp=datetime.now().astimezone(),
                        source=self._config.label,
                        direction=TrafficDirection.UNKNOWN,
                        kind=RecordKind.ERROR,
                        raw_data=pending,
                        result=ParseResult(
                            False,
                            None,
                            pending,
                            error=ParseError(
                                "INCOMPLETE_H4_FRAME",
                                "Serial monitoring ended with an incomplete H4 frame",
                                {"received_length": len(pending)},
                            ),
                        ),
                    )
                )

    def _process_bytes(self, data: bytes) -> None:
        chunk = self._decoder.feed(data)
        for noise in chunk.discarded_noise:
            self._on_record(
                LogRecord(
                    timestamp=datetime.now().astimezone(),
                    source=self._config.label,
                    direction=TrafficDirection.UNKNOWN,
                    kind=RecordKind.NOISE,
                    raw_data=noise,
                    message="Discarded bytes before an H4 packet indicator",
                )
            )
        for frame in chunk.frames:
            parsed = self._parser.parse_bytes(frame)
            self._on_record(
                LogRecord(
                    timestamp=datetime.now().astimezone(),
                    source=self._config.label,
                    direction=self._direction_for(frame),
                    kind=RecordKind.PACKET if parsed.success else RecordKind.ERROR,
                    raw_data=frame,
                    result=parsed,
                )
            )

    @staticmethod
    def _direction_for(frame: bytes) -> TrafficDirection:
        if not frame:
            return TrafficDirection.UNKNOWN
        if frame[0] == H4PacketIndicator.COMMAND:
            return TrafficDirection.HOST_TO_CONTROLLER
        if frame[0] == H4PacketIndicator.EVENT:
            return TrafficDirection.CONTROLLER_TO_HOST
        return TrafficDirection.UNKNOWN


class DualSerialMonitor:
    """Own and coordinate the two serial receive workers."""

    def __init__(
        self, on_record: RecordCallback, parser: HciParser | None = None
    ) -> None:
        self._on_record = on_record
        self._parser = parser or HciParser()
        self._workers: list[SerialPortWorker] = []

    def start(
        self,
        first_port: SerialPortConfig,
        second_port: SerialPortConfig,
    ) -> None:
        """Start monitoring two configured ports."""
        if first_port.port == second_port.port:
            raise ValueError("The same serial port cannot be selected twice")
        self.stop()
        workers = [
            SerialPortWorker(first_port, self._on_record, self._parser),
            SerialPortWorker(second_port, self._on_record, self._parser),
        ]
        started: list[SerialPortWorker] = []
        try:
            for worker in workers:
                worker.start()
                started.append(worker)
        except Exception:
            for worker in started:
                worker.stop()
            raise
        self._workers = workers

    def stop(self) -> None:
        """Stop all active workers."""
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.stop()
