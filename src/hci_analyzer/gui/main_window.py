"""Main Tkinter window."""

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from hci_analyzer.models import LogRecord


class MainWindow:
    """Present port controls, logs, and manual hexadecimal parsing."""

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_manual_parse: Callable[[str], None],
    ) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_manual_parse = on_manual_parse
        self._root: tk.Tk
        self._port_one_combo: ttk.Combobox
        self._port_two_combo: ttk.Combobox
        self._baud_rate_combo: ttk.Combobox
        self._log_text: tk.Text
        self._manual_hex_entry: ttk.Entry

    def run(self) -> None:
        """Start the Tkinter event loop."""
        raise NotImplementedError

    def set_serial_ports(self, ports: list[str]) -> None:
        """Populate both serial-port selectors."""
        raise NotImplementedError

    def append_record(self, record: LogRecord) -> None:
        """Display a timestamped record in the shared log area."""
        raise NotImplementedError

    def set_monitoring_state(self, active: bool) -> None:
        """Update controls for started or stopped monitoring."""
        raise NotImplementedError

