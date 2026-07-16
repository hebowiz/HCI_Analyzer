"""Top-level application coordination."""

import queue
from datetime import datetime

from hci_analyzer.config import LOG_DIRECTORY
from hci_analyzer.gui.main_window import MainWindow
from hci_analyzer.logging.jsonl_logger import JsonlLogger
from hci_analyzer.models import (
    LogRecord,
    ParseError,
    ParseResult,
    RecordKind,
    SerialPortConfig,
    TrafficDirection,
)
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.serial.monitor import DualSerialMonitor
from hci_analyzer.serial.ports import list_serial_ports


class HciAnalyzerApplication:
    """Compose the GUI, parser, serial monitor, and JSONL logger."""

    def __init__(self) -> None:
        self._parser = HciParser()
        self._record_queue: queue.Queue[LogRecord] = queue.Queue()
        self._monitor = DualSerialMonitor(self._record_queue.put, self._parser)
        self._logger = JsonlLogger(LOG_DIRECTORY)
        self._window = MainWindow(
            on_start=self._start_monitoring,
            on_stop=self._stop_monitoring,
            on_manual_parse=self._manual_parse,
        )
        self._window.set_refresh_handler(self._refresh_ports)
        self._window.set_close_handler(self._close)
        self._monitoring = False

    def run(self) -> None:
        """Start the application event loop."""
        self._refresh_ports()
        self._window.after(50, self._drain_records)
        self._window.run()

    def _refresh_ports(self) -> None:
        try:
            self._window.set_serial_ports(list_serial_ports())
        except Exception as exc:
            self._handle_record(self._application_error("PORT_ENUMERATION_ERROR", exc))

    def _start_monitoring(self) -> None:
        if self._monitoring:
            return
        try:
            first, second, baud_rate = self._window.get_monitor_settings()
            if not first or not second:
                raise ValueError("2つのシリアルポートを選択してください")
            if first == second:
                raise ValueError("異なる2つのシリアルポートを選択してください")

            session = self._logger.start_session()
            self._monitor.start(
                SerialPortConfig(first, baud_rate, f"Port1:{first}"),
                SerialPortConfig(second, baud_rate, f"Port2:{second}"),
            )
            self._monitoring = True
            self._window.set_monitoring_state(True)
            self._handle_record(
                LogRecord(
                    timestamp=datetime.now().astimezone(),
                    source="Application",
                    direction=TrafficDirection.UNKNOWN,
                    kind=RecordKind.SYSTEM,
                    message=(
                        f"Monitoring started: {first}, {second}, {baud_rate} baud; "
                        f"log={session.file_path}"
                    ),
                )
            )
        except Exception as exc:
            self._monitor.stop()
            self._monitoring = False
            self._window.set_monitoring_state(False)
            self._handle_record(self._application_error("MONITOR_START_ERROR", exc))
            self._logger.close()

    def _stop_monitoring(self) -> None:
        if not self._monitoring:
            return
        self._monitor.stop()
        self._consume_pending_records()
        self._handle_record(
            LogRecord(
                timestamp=datetime.now().astimezone(),
                source="Application",
                direction=TrafficDirection.UNKNOWN,
                kind=RecordKind.SYSTEM,
                message="Monitoring stopped",
            )
        )
        self._logger.close()
        self._monitoring = False
        self._window.set_monitoring_state(False)

    def _manual_parse(self, text: str) -> None:
        result = self._parser.parse_hex_string(text)
        self._handle_record(
            LogRecord(
                timestamp=datetime.now().astimezone(),
                source="Manual",
                direction=TrafficDirection.MANUAL,
                kind=RecordKind.PACKET if result.success else RecordKind.ERROR,
                raw_data=result.raw_data,
                result=result,
            )
        )

    def _drain_records(self) -> None:
        self._consume_pending_records()
        self._window.after(50, self._drain_records)

    def _consume_pending_records(self) -> None:
        while True:
            try:
                record = self._record_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_record(record)

    def _handle_record(self, record: LogRecord) -> None:
        self._window.append_record(record)
        if self._logger.session is not None:
            try:
                self._logger.write(record)
            except Exception as exc:
                self._window.append_record(
                    self._application_error("LOG_WRITE_ERROR", exc)
                )

    def _close(self) -> None:
        if self._monitoring:
            self._stop_monitoring()
        else:
            self._logger.close()
        self._window.destroy()

    @staticmethod
    def _application_error(code: str, exc: Exception) -> LogRecord:
        return LogRecord(
            timestamp=datetime.now().astimezone(),
            source="Application",
            direction=TrafficDirection.UNKNOWN,
            kind=RecordKind.ERROR,
            result=ParseResult(
                False,
                None,
                b"",
                error=ParseError(code, str(exc), {"exception": type(exc).__name__}),
            ),
        )
