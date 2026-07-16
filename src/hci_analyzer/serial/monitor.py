"""Background monitoring for two receive-only serial ports."""

from collections.abc import Callable

from hci_analyzer.models import LogRecord, SerialPortConfig

RecordCallback = Callable[[LogRecord], None]


class SerialPortWorker:
    """Receive bytes from one serial port on a background thread."""

    def __init__(
        self,
        config: SerialPortConfig,
        on_record: RecordCallback,
    ) -> None:
        self._config = config
        self._on_record = on_record

    def start(self) -> None:
        """Open the port and start its receive thread."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop reception and close the port."""
        raise NotImplementedError


class DualSerialMonitor:
    """Own and coordinate the two serial receive workers."""

    def __init__(self, on_record: RecordCallback) -> None:
        self._on_record = on_record
        self._workers: list[SerialPortWorker] = []

    def start(
        self,
        first_port: SerialPortConfig,
        second_port: SerialPortConfig,
    ) -> None:
        """Start monitoring two configured ports."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop all active workers."""
        raise NotImplementedError

