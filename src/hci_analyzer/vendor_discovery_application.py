"""Application coordination for real-time Vendor Command Discovery."""

from __future__ import annotations

import queue

from hci_analyzer.gui.vendor_discovery import VendorDiscoveryWindow
from hci_analyzer.models import LogRecord, SerialPortConfig
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.serial.monitor import DualSerialMonitor
from hci_analyzer.serial.ports import list_serial_ports
from hci_analyzer.vendor_settings import (
    VendorDiscoverySettings,
    VendorDiscoverySettingsStore,
)


class VendorDiscoveryApplication:
    """Compose the Discovery GUI with Analyzer's dual-port monitor."""

    def __init__(self) -> None:
        self._parser = HciParser(prefer_race=True)
        self._record_queue: queue.Queue[LogRecord] = queue.Queue()
        self._monitor = DualSerialMonitor(self._record_queue.put, self._parser)
        self._settings_store = VendorDiscoverySettingsStore()
        self._saved_settings = self._settings_store.load()
        self._window = VendorDiscoveryWindow(
            on_start=self._start_monitoring,
            on_stop=self._stop_monitoring,
            on_refresh=self._refresh_ports,
            on_close=self._close,
        )
        self._monitoring = False

    def run(self) -> None:
        self._window.set_window_size(
            self._saved_settings.window_width,
            self._saved_settings.window_height,
        )
        self._window.set_baud_rate(self._saved_settings.baud_rate)
        self._window.set_group_duplicates(self._saved_settings.group_duplicates)
        self._refresh_ports(
            self._saved_settings.port_one,
            self._saved_settings.port_two,
        )
        self._window.after(50, self._drain_records)
        self._window.run()

    def _refresh_ports(
        self,
        preferred_port_one: str | None = None,
        preferred_port_two: str | None = None,
    ) -> None:
        try:
            self._window.set_serial_ports(
                list_serial_ports(),
                preferred_port_one,
                preferred_port_two,
            )
        except Exception as exc:
            self._window.show_error("ポート列挙エラー", exc)

    def _start_monitoring(self) -> None:
        if self._monitoring:
            return
        try:
            first, second, baud_rate = self._window.get_monitor_settings()
            if not first or not second:
                raise ValueError("2つのポート選択欄を指定してください")
            self._monitor.start(
                SerialPortConfig(first, baud_rate, f"Port1:{first}"),
                SerialPortConfig(second, baud_rate, f"Port2:{second}"),
            )
        except Exception as exc:
            self._monitor.stop()
            self._window.show_error("取得開始エラー", exc)
            return
        self._monitoring = True
        self._window.set_monitoring_state(True)

    def _stop_monitoring(self) -> None:
        if not self._monitoring:
            return
        self._monitor.stop()
        self._consume_pending_records()
        self._monitoring = False
        self._window.set_monitoring_state(False)

    def _drain_records(self) -> None:
        self._consume_pending_records()
        self._window.after(50, self._drain_records)

    def _consume_pending_records(self) -> None:
        while True:
            try:
                record = self._record_queue.get_nowait()
            except queue.Empty:
                return
            self._window.add_monitor_record(record)

    def _close(self) -> None:
        if self._monitoring:
            self._stop_monitoring()
        try:
            port_one, port_two, baud_rate = self._window.get_monitor_settings()
            width, height = self._window.get_window_size()
            self._settings_store.save(
                VendorDiscoverySettings(
                    port_one=port_one,
                    port_two=port_two,
                    baud_rate=baud_rate,
                    window_width=width,
                    window_height=height,
                    group_duplicates=self._window.get_group_duplicates(),
                )
            )
        except Exception as exc:
            self._window.show_error("設定保存エラー", exc)
        self._window.destroy()
