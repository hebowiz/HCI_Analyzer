"""Main Tkinter window."""

import json
import tkinter as tk
from collections.abc import Callable
from tkinter import scrolledtext, ttk

from hci_analyzer.config import (
    ANALYZER_DEFAULT_WINDOW_SIZE,
    ANALYZER_MINIMUM_WINDOW_SIZE,
    APP_NAME,
    DEFAULT_BAUD_RATE,
    SUPPORTED_BAUD_RATES,
)
from hci_analyzer.models import LogRecord
from hci_analyzer.presentation.text import ascii_safe_text
from hci_analyzer.sequence.diagram import HciSequenceDiagram
from hci_analyzer.gui.sequence_window import SequenceDiagramWindow


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
        self._root = tk.Tk()
        self._root.title(APP_NAME)
        self._root.geometry(
            f"{ANALYZER_DEFAULT_WINDOW_SIZE[0]}x"
            f"{ANALYZER_DEFAULT_WINDOW_SIZE[1]}"
        )
        self._root.minsize(*ANALYZER_MINIMUM_WINDOW_SIZE)
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(2, weight=1)

        self._port_one_combo: ttk.Combobox
        self._port_two_combo: ttk.Combobox
        self._baud_rate_combo: ttk.Combobox
        self._log_text: scrolledtext.ScrolledText
        self._manual_hex_entry: ttk.Entry
        self._start_button: ttk.Button
        self._stop_button: ttk.Button
        self._refresh_button: ttk.Button
        self._status_variable = tk.StringVar(value="停止中")
        self._sequence_windows: list[SequenceDiagramWindow] = []
        self._build_controls()

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self._root.mainloop()

    def set_serial_ports(
        self,
        ports: list[str],
        preferred_port_one: str | None = None,
        preferred_port_two: str | None = None,
    ) -> None:
        """Populate both serial-port selectors."""
        current_one = self._port_one_combo.get()
        current_two = self._port_two_combo.get()
        self._port_one_combo.configure(values=ports)
        self._port_two_combo.configure(values=ports)
        if preferred_port_one in ports:
            self._port_one_combo.set(preferred_port_one)
        elif current_one in ports:
            self._port_one_combo.set(current_one)
        elif ports:
            self._port_one_combo.set(ports[0])
        else:
            self._port_one_combo.set("")
        if preferred_port_two in ports:
            self._port_two_combo.set(preferred_port_two)
        elif current_two in ports:
            self._port_two_combo.set(current_two)
        elif len(ports) > 1:
            self._port_two_combo.set(ports[1])
        elif ports:
            self._port_two_combo.set(ports[0])
        else:
            self._port_two_combo.set("")

    def set_baud_rate(self, baud_rate: int) -> None:
        """Restore the shared serial baud rate."""
        selected = (
            baud_rate if baud_rate in SUPPORTED_BAUD_RATES else DEFAULT_BAUD_RATE
        )
        self._baud_rate_combo.set(str(selected))

    def append_record(self, record: LogRecord) -> None:
        """Display a timestamped record in the shared log area."""
        timestamp = record.timestamp.isoformat(timespec="milliseconds")
        raw_hex = record.raw_data.hex(" ").upper() or "-"
        prefix = (
            f"[{timestamp}] [{record.source}] [{record.direction.value}] "
            f"[{record.kind.value}]"
        )
        lines = [f"{prefix} RAW: {raw_hex}"]
        if record.result is not None:
            if record.result.success:
                detail = record.result.decoded
            elif record.result.error is not None:
                detail = {
                    "error_code": record.result.error.code,
                    "message": record.result.error.message,
                    "details": record.result.error.details,
                }
            else:
                detail = {"error": "Unknown parser error"}
            lines.append(json.dumps(detail, ensure_ascii=False, sort_keys=True))
        elif record.message:
            lines.append(record.message)

        self._log_text.configure(state=tk.NORMAL)
        safe_lines = [ascii_safe_text(line) for line in lines]
        self._log_text.insert(tk.END, "\n".join(safe_lines) + "\n")
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def set_monitoring_state(self, active: bool) -> None:
        """Update controls for started or stopped monitoring."""
        selector_state = tk.DISABLED if active else "readonly"
        self._port_one_combo.configure(state=selector_state)
        self._port_two_combo.configure(state=selector_state)
        self._baud_rate_combo.configure(state=selector_state)
        self._refresh_button.configure(
            state=tk.DISABLED if active else tk.NORMAL
        )
        self._start_button.configure(
            state=tk.DISABLED if active else tk.NORMAL
        )
        self._stop_button.configure(
            state=tk.NORMAL if active else tk.DISABLED
        )
        self._status_variable.set("解析中" if active else "停止中")

    def get_monitor_settings(self) -> tuple[str, str, int]:
        """Return the two selected ports and shared baud rate."""
        return (
            self._port_one_combo.get().strip(),
            self._port_two_combo.get().strip(),
            int(self._baud_rate_combo.get()),
        )

    def set_refresh_handler(self, callback: Callable[[], None]) -> None:
        """Set the serial-port refresh callback."""
        self._refresh_button.configure(command=callback)

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        """Set the window-close callback."""
        self._root.protocol("WM_DELETE_WINDOW", callback)

    def set_window_size(self, width: int, height: int) -> None:
        """Restore the window width and height."""
        width = min(
            max(width, ANALYZER_MINIMUM_WINDOW_SIZE[0]),
            self._root.winfo_screenwidth(),
        )
        height = min(
            max(height, ANALYZER_MINIMUM_WINDOW_SIZE[1]),
            self._root.winfo_screenheight(),
        )
        self._root.geometry(f"{width}x{height}")

    def get_window_size(self) -> tuple[int, int]:
        """Return the current window width and height."""
        self._root.update_idletasks()
        return self._root.winfo_width(), self._root.winfo_height()

    def show_sequence_diagram(self, diagram: HciSequenceDiagram) -> None:
        """Open a new window containing the generated HCI sequence."""
        self._sequence_windows.append(SequenceDiagramWindow(self._root, diagram))

    def after(self, milliseconds: int, callback: Callable[[], None]) -> None:
        """Schedule work on the Tkinter UI thread."""
        self._root.after(milliseconds, callback)

    def destroy(self) -> None:
        """Destroy the application window."""
        self._root.destroy()

    def _build_controls(self) -> None:
        serial_frame = ttk.LabelFrame(self._root, text="シリアルモニター")
        serial_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        serial_frame.columnconfigure(1, weight=1)
        serial_frame.columnconfigure(3, weight=1)

        ttk.Label(serial_frame, text="ポート1").grid(
            row=0, column=0, padx=(8, 4), pady=8
        )
        self._port_one_combo = ttk.Combobox(serial_frame, state="readonly", width=18)
        self._port_one_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(serial_frame, text="ポート2").grid(
            row=0, column=2, padx=(0, 4), pady=8
        )
        self._port_two_combo = ttk.Combobox(serial_frame, state="readonly", width=18)
        self._port_two_combo.grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(serial_frame, text="ボーレート").grid(
            row=0, column=4, padx=(0, 4), pady=8
        )
        self._baud_rate_combo = ttk.Combobox(
            serial_frame,
            state="readonly",
            width=12,
            values=[str(value) for value in SUPPORTED_BAUD_RATES],
        )
        self._baud_rate_combo.set(str(DEFAULT_BAUD_RATE))
        self._baud_rate_combo.grid(row=0, column=5, padx=(0, 10), pady=8)

        self._refresh_button = ttk.Button(serial_frame, text="ポート更新")
        self._refresh_button.grid(row=0, column=6, padx=(0, 8), pady=8)
        self._start_button = ttk.Button(
            serial_frame, text="解析開始", command=self._on_start
        )
        self._start_button.grid(row=0, column=7, padx=(0, 6), pady=8)
        self._stop_button = ttk.Button(
            serial_frame, text="解析終了", command=self._on_stop, state=tk.DISABLED
        )
        self._stop_button.grid(row=0, column=8, padx=(0, 8), pady=8)
        ttk.Label(serial_frame, textvariable=self._status_variable).grid(
            row=0, column=9, padx=(0, 8), pady=8
        )

        manual_frame = ttk.LabelFrame(self._root, text="Hex String 手動解析")
        manual_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        manual_frame.columnconfigure(0, weight=1)
        self._manual_hex_entry = ttk.Entry(manual_frame)
        self._manual_hex_entry.grid(
            row=0, column=0, sticky="ew", padx=(8, 6), pady=8
        )
        self._manual_hex_entry.bind("<Return>", self._manual_parse_from_event)
        ttk.Button(
            manual_frame, text="解析", command=self._manual_parse
        ).grid(row=0, column=1, padx=(0, 8), pady=8)

        log_frame = ttk.LabelFrame(self._root, text="受信データ / 解析結果")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self._log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 10),
        )
        self._log_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    def _manual_parse(self) -> None:
        text = self._manual_hex_entry.get()
        self._on_manual_parse(text)

    def _manual_parse_from_event(self, _event: tk.Event) -> None:
        self._manual_parse()
