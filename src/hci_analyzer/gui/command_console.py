"""Tkinter window for command selection, parameter editing, and TX/RX logs."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import (
    ConsoleCommandDefinition,
    ParameterDefinition,
    ParameterKind,
)
from hci_analyzer.config import (
    COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE,
    COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE,
    DEFAULT_BAUD_RATE,
    DEFAULT_RESPONSE_TIMEOUT_SECONDS,
    SUPPORTED_BAUD_RATES,
    SUPPORTED_RESPONSE_TIMEOUT_SECONDS,
)
from hci_analyzer.presentation.transport_log import format_transport_event
from hci_analyzer.serial.transport import TransportEvent, TransportEventKind


class _IntegerArrayEditor:
    """Small row-based editor for a variable-length integer array."""

    def __init__(
        self,
        parent: ttk.Frame,
        values: list[int],
        on_change: Callable[[], None],
    ) -> None:
        self._parent = parent
        self._on_change = on_change
        self._variables: list[tk.StringVar] = []
        self.set_values(values)

    def get_values(self) -> list[str]:
        return [variable.get() for variable in self._variables]

    def set_values(self, values: list[int] | tuple[int, ...]) -> None:
        for child in self._parent.winfo_children():
            child.destroy()
        self._variables.clear()
        for value in values:
            self._append_row(str(value), notify=False)
        self._render_add_button()

    def _append_row(self, value: str = "1", *, notify: bool = True) -> None:
        row_index = len(self._variables)
        variable = tk.StringVar(value=value)
        variable.trace_add("write", lambda *_args: self._on_change())
        self._variables.append(variable)
        ttk.Label(self._parent, text=str(row_index)).grid(
            row=row_index, column=0, padx=(0, 4), pady=2
        )
        ttk.Entry(self._parent, textvariable=variable, width=10).grid(
            row=row_index, column=1, sticky="w", pady=2
        )
        ttk.Button(
            self._parent,
            text="削除",
            command=lambda index=row_index: self._delete_row(index),
        ).grid(row=row_index, column=2, padx=(4, 0), pady=2)
        if notify:
            self._render_all()
            self._on_change()

    def _delete_row(self, index: int) -> None:
        if not 0 <= index < len(self._variables):
            return
        del self._variables[index]
        self._render_all()
        self._on_change()

    def _render_all(self) -> None:
        values = [variable.get() for variable in self._variables]
        for child in self._parent.winfo_children():
            child.destroy()
        self._variables = []
        for value in values:
            self._append_row(value, notify=False)
        self._render_add_button()

    def _render_add_button(self) -> None:
        ttk.Button(
            self._parent, text="追加", command=lambda: self._append_row("1")
        ).grid(row=len(self._variables), column=1, sticky="w", pady=(4, 2))


class CommandConsoleWindow:
    """Present serial controls and a schema-generated command form."""

    def __init__(
        self,
        on_connect: Callable[[], None],
        on_disconnect: Callable[[], None],
        on_command_selected: Callable[[int], None],
        on_preview: Callable[[Mapping[str, Any]], None],
        on_send: Callable[[Mapping[str, Any]], None],
        on_quick_send: Callable[[int], None],
        on_clear_log: Callable[[], None],
        on_reset: Callable[[], None] | None = None,
        on_reset_command_support: Callable[[], None] | None = None,
        on_load_vendor_definitions: Callable[[], None] | None = None,
    ) -> None:
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_command_selected = on_command_selected
        self._on_preview = on_preview
        self._on_send = on_send
        self._on_quick_send = on_quick_send
        self._on_clear_log = on_clear_log
        self._on_reset = on_reset or (lambda: None)
        self._on_reset_command_support = on_reset_command_support or (lambda: None)
        self._on_load_vendor_definitions = (
            on_load_vendor_definitions or (lambda: None)
        )
        self._refresh_handler: Callable[[], None] = lambda: None

        self._root = tk.Tk()
        self._root.title("HCI Command Console")
        self._root.geometry(
            f"{COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE[0]}x"
            f"{COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE[1]}"
        )
        self._root.minsize(*COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE)
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(3, weight=1)

        self._definitions: tuple[ConsoleCommandDefinition, ...] = ()
        self._definition_lookup: dict[tuple[str, str, str], ConsoleCommandDefinition] = {}
        self._current_definition: ConsoleCommandDefinition | None = None
        self._parameter_vars: dict[str, tk.StringVar] = {}
        self._enum_display_to_value: dict[str, dict[str, int]] = {}
        self._enum_full_descriptions: dict[str, dict[int, str]] = {}
        self._enum_detail_labels: dict[str, ttk.Label] = {}
        self._array_editors: dict[str, _IntegerArrayEditor] = {}
        self._error_labels: dict[str, ttk.Label] = {}
        self._parameter_widgets: dict[str, tk.Widget] = {}
        self._events: list[TransportEvent] = []
        self._connected = False
        self._busy = False
        self._preview_valid = False
        self._selected_command_supported: bool | None = None
        self._command_support: dict[int, bool] = {}
        self._suspend_change_callback = False

        self._port_variable = tk.StringVar()
        self._baud_variable = tk.StringVar(value=str(DEFAULT_BAUD_RATE))
        self._response_timeout_variable = tk.StringVar(
            value=str(DEFAULT_RESPONSE_TIMEOUT_SECONDS)
        )
        self._status_variable = tk.StringVar(value="未接続")
        self._category_variable = tk.StringVar()
        self._command_variable = tk.StringVar()
        self._version_variable = tk.StringVar()
        self._opcode_variable = tk.StringVar(value="-")
        self._preview_variable = tk.StringVar(value="-")
        self._support_variable = tk.StringVar(value="対応状況: 未取得")
        self._filter_variable = tk.StringVar(value="すべて")
        self._build_window()

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self._root.mainloop()

    def set_serial_ports(
        self, ports: list[str], preferred_port: str | None = None
    ) -> None:
        """Populate the serial-port selector."""
        current = self._port_variable.get()
        self._port_combo.configure(values=ports)
        if preferred_port in ports:
            self._port_variable.set(preferred_port)
        elif current in ports:
            self._port_variable.set(current)
        elif ports:
            self._port_variable.set(ports[0])
        else:
            self._port_variable.set("")

    def set_baud_rate(self, baud_rate: int) -> None:
        """Set the selected baud rate."""
        selected = (
            baud_rate if baud_rate in SUPPORTED_BAUD_RATES else DEFAULT_BAUD_RATE
        )
        self._baud_variable.set(str(selected))

    def set_response_timeout_seconds(self, timeout_seconds: int) -> None:
        """Set the response timeout, falling back to the default if invalid."""
        selected = (
            timeout_seconds
            if timeout_seconds in SUPPORTED_RESPONSE_TIMEOUT_SECONDS
            else DEFAULT_RESPONSE_TIMEOUT_SECONDS
        )
        self._response_timeout_variable.set(str(selected))

    def set_command_definitions(
        self, definitions: tuple[ConsoleCommandDefinition, ...]
    ) -> None:
        """Populate category, command, and version selectors."""
        self._definitions = definitions
        self._definition_lookup = {
            (item.category, item.name, item.version or "none"): item
            for item in definitions
        }
        categories = list(dict.fromkeys(item.category for item in definitions))
        self._category_combo.configure(values=categories)
        if categories:
            self._category_variable.set(categories[0])
            self._populate_commands()

    def show_parameter_form(self, definition: ConsoleCommandDefinition) -> None:
        """Generate editors for every parameter in the selected command."""
        self._current_definition = definition
        self._selected_command_supported = self._command_support.get(
            definition.opcode
        )
        self._opcode_variable.set(f"0x{definition.opcode:04X}")
        self._update_support_text()
        self._parameter_canvas.yview_moveto(0.0)
        for child in self._parameter_frame.winfo_children():
            child.destroy()
        self._parameter_vars.clear()
        self._enum_display_to_value.clear()
        self._enum_full_descriptions.clear()
        self._enum_detail_labels.clear()
        self._array_editors.clear()
        self._error_labels.clear()
        self._parameter_widgets.clear()

        if not definition.parameters:
            ttk.Label(self._parameter_frame, text="パラメーターはありません。").grid(
                row=0, column=0, sticky="w", pady=8
            )

        for index, parameter in enumerate(definition.parameters):
            self._create_parameter_row(index, parameter)
        self._parameter_frame.columnconfigure(1, weight=1)
        self._root.after_idle(lambda: self._parameter_canvas.yview_moveto(0.0))
        self._notify_values_changed()

    def get_connection_settings(self) -> tuple[str, int]:
        """Return the selected port and baud rate."""
        return self._port_variable.get().strip(), int(self._baud_variable.get())

    def get_response_timeout_seconds(self) -> float:
        """Return the response timeout selected for the next command."""
        return float(self._response_timeout_variable.get())

    def choose_vendor_definition_files(self) -> tuple[Path, ...]:
        """Ask the user to select external vendor definition JSON files."""
        selected = filedialog.askopenfilenames(
            parent=self._root,
            title="Vendor Command定義を選択",
            initialdir="vendor_definitions",
            filetypes=(("JSON", "*.json"), ("All files", "*.*")),
        )
        return tuple(Path(item) for item in selected)

    def confirm_review_required_definitions(self, names: list[str]) -> bool:
        """Confirm loading inferred definitions that still require review."""
        command_names = "\n".join(f"- {name}" for name in names)
        return messagebox.askyesno(
            "未確定Vendor定義の読込",
            "選択した定義はreview_required=trueです。\n"
            "推定結果が誤っているとControllerへ意図しないCommandを送信する"
            "可能性があります。\n\n"
            f"{command_names}\n\n"
            "内容を確認済みとして読み込みますか？",
            parent=self._root,
        )

    def get_parameter_values(self) -> dict[str, Any]:
        """Return all values currently entered in the parameter form."""
        values: dict[str, Any] = {}
        for name, variable in self._parameter_vars.items():
            display_mapping = self._enum_display_to_value.get(name)
            if display_mapping is not None:
                values[name] = display_mapping.get(variable.get(), variable.get())
            else:
                values[name] = variable.get()
        for name, editor in self._array_editors.items():
            values[name] = editor.get_values()
        return values

    def set_parameter_values(self, values: Mapping[str, Any]) -> None:
        """Set the generated form from cached or default values."""
        self._suspend_change_callback = True
        try:
            for name, value in values.items():
                if name in self._array_editors:
                    self._array_editors[name].set_values(list(value))
                    continue
                variable = self._parameter_vars.get(name)
                if variable is None:
                    continue
                display_mapping = self._enum_display_to_value.get(name)
                if display_mapping is not None:
                    display = next(
                        (
                            label
                            for label, enum_value in display_mapping.items()
                            if enum_value == value
                        ),
                        str(value),
                    )
                    variable.set(display)
                else:
                    variable.set(str(value))
        finally:
            self._suspend_change_callback = False
        self._notify_values_changed()

    def show_packet_preview(self, frame: bytes) -> None:
        """Display the generated UART HCI packet as hexadecimal text."""
        self._preview_variable.set(frame.hex(" ").upper() if frame else "-")
        self._preview_valid = bool(frame)
        self._update_send_state()

    def show_validation_issues(self, issues: Mapping[str, str]) -> None:
        """Display field validation state and update send availability."""
        for name, label in self._error_labels.items():
            label.configure(text=issues.get(name, ""))
        command_message = issues.get("__command__", "")
        self._command_error_label.configure(text=command_message)
        self._preview_valid = not issues
        self._update_send_state()

    def append_transport_event(self, event: TransportEvent) -> None:
        """Append a timestamped TX, RX, system, or error entry."""
        self._events.append(event)
        if self._event_matches_filter(event):
            self._append_event_text(event)

    def clear_log(self) -> None:
        """Clear the in-memory GUI log."""
        self._events.clear()
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def set_connected_state(self, connected: bool) -> None:
        """Enable or disable controls based on connection state."""
        self._connected = connected
        selector_state = tk.DISABLED if connected else "readonly"
        self._port_combo.configure(state=selector_state)
        self._baud_combo.configure(state=selector_state)
        self._refresh_button.configure(
            state=tk.DISABLED if connected else tk.NORMAL
        )
        self._connect_button.configure(
            state=tk.DISABLED if connected else tk.NORMAL
        )
        self._disconnect_button.configure(
            state=tk.NORMAL if connected else tk.DISABLED
        )
        self._status_variable.set("接続中" if connected else "未接続")
        self._update_send_state()

    def set_busy_state(self, busy: bool) -> None:
        """Disable command transmission while a response is pending."""
        self._busy = busy
        self._response_timeout_combo.configure(
            state=tk.DISABLED if busy else "readonly"
        )
        self._vendor_load_button.configure(
            state=tk.DISABLED if busy else tk.NORMAL
        )
        self._update_send_state()

    def set_command_support(self, support: Mapping[int, bool]) -> None:
        """Apply Controller capability results to command transmission."""
        self._command_support = dict(support)
        definition = self._current_definition
        self._selected_command_supported = (
            self._command_support.get(definition.opcode)
            if definition is not None
            else None
        )
        self._update_support_text()
        self._update_send_state()

    def set_refresh_handler(self, callback: Callable[[], None]) -> None:
        self._refresh_handler = callback
        self._refresh_button.configure(command=callback)

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        """Set the window-close callback."""
        self._root.protocol("WM_DELETE_WINDOW", callback)

    def set_window_size(self, width: int, height: int) -> None:
        """Restore the window width and height."""
        width = min(
            max(width, COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE[0]),
            self._root.winfo_screenwidth(),
        )
        height = min(
            max(height, COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE[1]),
            self._root.winfo_screenheight(),
        )
        self._root.geometry(f"{width}x{height}")

    def get_window_size(self) -> tuple[int, int]:
        """Return the current window width and height."""
        self._root.update_idletasks()
        return self._root.winfo_width(), self._root.winfo_height()

    def after(self, milliseconds: int, callback: Callable[[], None]) -> None:
        self._root.after(milliseconds, callback)

    def destroy(self) -> None:
        self._root.destroy()

    def _build_window(self) -> None:
        connection = ttk.LabelFrame(self._root, text="接続設定")
        connection.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ttk.Label(connection, text="Port").grid(row=0, column=0, padx=(8, 4), pady=8)
        self._port_combo = ttk.Combobox(
            connection,
            textvariable=self._port_variable,
            state="readonly",
            width=14,
        )
        self._port_combo.grid(row=0, column=1, sticky="w", pady=8)
        ttk.Label(connection, text="Baud").grid(row=0, column=2, padx=(12, 4), pady=8)
        self._baud_combo = ttk.Combobox(
            connection,
            textvariable=self._baud_variable,
            values=[str(value) for value in SUPPORTED_BAUD_RATES],
            state="readonly",
            width=12,
        )
        self._baud_combo.grid(row=0, column=3, pady=8)
        self._refresh_button = ttk.Button(connection, text="更新")
        self._refresh_button.grid(row=0, column=4, padx=(8, 4), pady=8)
        self._connect_button = ttk.Button(
            connection, text="接続", command=self._on_connect
        )
        self._connect_button.grid(row=0, column=5, padx=4, pady=8)
        self._disconnect_button = ttk.Button(
            connection,
            text="切断",
            command=self._on_disconnect,
            state=tk.DISABLED,
        )
        self._disconnect_button.grid(row=0, column=6, padx=4, pady=8)
        ttk.Label(connection, textvariable=self._status_variable).grid(
            row=0, column=7, padx=(8, 8), pady=8
        )
        ttk.Button(
            connection,
            text="コマンド対応初期化",
            command=self._on_reset_command_support,
        ).grid(row=0, column=8, padx=(8, 8), pady=8)
        ttk.Label(connection, text="Timeout").grid(
            row=0, column=9, padx=(8, 4), pady=8
        )
        self._response_timeout_combo = ttk.Combobox(
            connection,
            textvariable=self._response_timeout_variable,
            values=tuple(str(value) for value in SUPPORTED_RESPONSE_TIMEOUT_SECONDS),
            state="readonly",
            width=4,
        )
        self._response_timeout_combo.grid(
            row=0, column=10, padx=(0, 4), pady=8
        )
        ttk.Label(connection, text="s").grid(
            row=0, column=11, padx=(0, 8), pady=8
        )
        self._vendor_load_button = ttk.Button(
            connection,
            text="Vendor定義読込",
            command=self._on_load_vendor_definitions,
        )
        self._vendor_load_button.grid(
            row=0,
            column=12,
            padx=(8, 8),
            pady=8,
        )

        command_area = ttk.Frame(self._root)
        command_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        command_area.columnconfigure(1, weight=1)

        selection = ttk.LabelFrame(command_area, text="コマンド選択")
        selection.grid(row=0, column=0, sticky="nsw", padx=(0, 5))
        ttk.Label(selection, text="Category").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2)
        )
        self._category_combo = ttk.Combobox(
            selection, textvariable=self._category_variable, state="readonly", width=28
        )
        self._category_combo.grid(row=1, column=0, padx=8, pady=(0, 6))
        self._category_combo.bind("<<ComboboxSelected>>", self._on_category_changed)
        ttk.Label(selection, text="Command").grid(
            row=2, column=0, sticky="w", padx=8, pady=(4, 2)
        )
        self._command_combo = ttk.Combobox(
            selection, textvariable=self._command_variable, state="readonly", width=28
        )
        self._command_combo.grid(row=3, column=0, padx=8, pady=(0, 6))
        self._command_combo.bind("<<ComboboxSelected>>", self._on_command_changed)
        ttk.Label(selection, text="Version").grid(
            row=4, column=0, sticky="w", padx=8, pady=(4, 2)
        )
        self._version_combo = ttk.Combobox(
            selection, textvariable=self._version_variable, state="readonly", width=28
        )
        self._version_combo.grid(row=5, column=0, padx=8, pady=(0, 6))
        self._version_combo.bind("<<ComboboxSelected>>", self._on_version_changed)
        ttk.Label(selection, text="Opcode").grid(
            row=6, column=0, sticky="w", padx=8, pady=(4, 2)
        )
        ttk.Label(selection, textvariable=self._opcode_variable).grid(
            row=7, column=0, sticky="w", padx=8, pady=(0, 8)
        )
        ttk.Label(
            selection,
            textvariable=self._support_variable,
            wraplength=220,
        ).grid(row=8, column=0, sticky="w", padx=8, pady=(0, 8))

        parameters_group = ttk.LabelFrame(command_area, text="パラメーター設定")
        parameters_group.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        parameters_group.columnconfigure(0, weight=1)
        self._parameter_canvas = tk.Canvas(
            parameters_group, height=300, highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            parameters_group,
            orient="vertical",
            command=self._parameter_canvas.yview,
        )
        self._parameter_frame = ttk.Frame(self._parameter_canvas, padding=8)
        self._parameter_frame.bind(
            "<Configure>",
            lambda _event: self._parameter_canvas.configure(
                scrollregion=self._parameter_canvas.bbox("all")
            ),
        )
        self._parameter_canvas.create_window(
            (0, 0), window=self._parameter_frame, anchor="nw"
        )
        self._parameter_canvas.configure(yscrollcommand=scrollbar.set)
        self._parameter_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        for widget in (self._parameter_canvas, self._parameter_frame):
            widget.bind("<MouseWheel>", self._scroll_parameter_canvas)
            widget.bind("<Button-4>", self._scroll_parameter_canvas)
            widget.bind("<Button-5>", self._scroll_parameter_canvas)

        preview = ttk.LabelFrame(self._root, text="Packet Preview")
        preview.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        preview.columnconfigure(0, weight=1)
        ttk.Entry(
            preview,
            textvariable=self._preview_variable,
            state="readonly",
            font=("Consolas", 10),
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        self._command_error_label = ttk.Label(preview, foreground="#B00020")
        self._command_error_label.grid(
            row=1, column=0, sticky="w", padx=8, pady=(0, 4)
        )

        preview_actions = ttk.Frame(preview)
        preview_actions.grid(
            row=2, column=0, sticky="ew", padx=8, pady=(0, 8)
        )
        preview_actions.columnconfigure(0, weight=1)
        ttk.Button(
            preview_actions, text="初期値", command=self._on_reset
        ).grid(row=0, column=1, padx=4)
        self._quick_reset_button = ttk.Button(
            preview_actions,
            text="HCI_Reset",
            command=lambda: self._on_quick_send(0x0C03),
            state=tk.DISABLED,
            width=14,
        )
        self._quick_reset_button.grid(row=0, column=2, padx=(12, 4))
        self._quick_test_end_button = ttk.Button(
            preview_actions,
            text="HCI_Test_End",
            command=lambda: self._on_quick_send(0x201F),
            state=tk.DISABLED,
            width=16,
        )
        self._quick_test_end_button.grid(row=0, column=3, padx=4)
        self._send_button = ttk.Button(
            preview_actions,
            text="コマンド送信",
            command=self._request_send,
            state=tk.DISABLED,
            width=18,
        )
        self._send_button.grid(row=0, column=4, padx=(12, 0))

        log_group = ttk.LabelFrame(self._root, text="送受信ログ")
        log_group.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))
        log_group.columnconfigure(0, weight=1)
        log_group.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(log_group)
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        ttk.Label(toolbar, text="表示").pack(side=tk.LEFT)
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self._filter_variable,
            values=("すべて", "TX", "RX", "エラー"),
            state="readonly",
            width=10,
        )
        filter_combo.pack(side=tk.LEFT, padx=4)
        filter_combo.bind("<<ComboboxSelected>>", lambda _event: self._render_log())
        ttk.Button(
            toolbar,
            text="ログクリア",
            command=lambda: (self.clear_log(), self._on_clear_log()),
        ).pack(side=tk.RIGHT)
        self._log_text = scrolledtext.ScrolledText(
            log_group,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 10),
        )
        self._log_text.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

    def _create_parameter_row(
        self, row: int, parameter: ParameterDefinition
    ) -> None:
        ttk.Label(self._parameter_frame, text=parameter.label).grid(
            row=row * 3, column=0, sticky="nw", padx=(0, 8), pady=(3, 0)
        )
        if parameter.kind == ParameterKind.INTEGER_ARRAY:
            frame = ttk.Frame(self._parameter_frame)
            frame.grid(row=row * 3, column=1, sticky="w", pady=(3, 0))
            editor = _IntegerArrayEditor(
                frame, list(parameter.default), self._notify_values_changed
            )
            self._array_editors[parameter.name] = editor
            widget: tk.Widget = frame
        elif parameter.kind == ParameterKind.ENUM:
            display_to_value = {
                f"{self._short_enum_label(parameter.name, value, label)} "
                f"(0x{value:02X})": value
                for value, label in parameter.choices.items()
            }
            default_display = next(
                label
                for label, value in display_to_value.items()
                if value == parameter.default
            )
            variable = tk.StringVar(value=default_display)
            variable.trace_add("write", lambda *_args: self._notify_values_changed())
            widget = ttk.Combobox(
                self._parameter_frame,
                textvariable=variable,
                values=list(display_to_value),
                state="readonly",
                width=24,
            )
            widget.grid(row=row * 3, column=1, sticky="w", pady=(3, 0))
            self._parameter_vars[parameter.name] = variable
            self._enum_display_to_value[parameter.name] = display_to_value
            self._enum_full_descriptions[parameter.name] = dict(parameter.choices)
            detail = ttk.Label(
                self._parameter_frame,
                foreground="#555555",
                wraplength=520,
            )
            detail.grid(
                row=(row * 3) + 1,
                column=1,
                columnspan=3,
                sticky="w",
                pady=(1, 0),
            )
            self._enum_detail_labels[parameter.name] = detail
        else:
            variable = tk.StringVar(value=str(parameter.default))
            variable.trace_add("write", lambda *_args: self._notify_values_changed())
            widget = ttk.Entry(
                self._parameter_frame,
                textvariable=variable,
                width=24,
            )
            widget.grid(row=row * 3, column=1, sticky="w", pady=(3, 0))
            self._parameter_vars[parameter.name] = variable

        self._parameter_widgets[parameter.name] = widget
        if parameter.unit:
            ttk.Label(self._parameter_frame, text=parameter.unit).grid(
                row=row * 3, column=2, sticky="w", padx=(6, 0), pady=(3, 0)
            )
        error = ttk.Label(self._parameter_frame, foreground="#B00020")
        error.grid(
            row=(row * 3) + 2,
            column=1,
            columnspan=3,
            sticky="w",
            pady=(0, 2),
        )
        self._error_labels[parameter.name] = error

    def _populate_commands(self) -> None:
        category = self._category_variable.get()
        commands = list(
            dict.fromkeys(
                definition.name
                for definition in self._definitions
                if definition.category == category
            )
        )
        self._command_combo.configure(values=commands)
        if commands:
            self._command_variable.set(commands[0])
            self._populate_versions()

    def _populate_versions(self) -> None:
        category = self._category_variable.get()
        command = self._command_variable.get()
        versions = [
            definition.version or "none"
            for definition in self._definitions
            if definition.category == category and definition.name == command
        ]
        self._version_combo.configure(values=versions)
        if versions:
            self._version_variable.set(
                self._preferred_version(command, versions)
            )
            self._select_definition()

    @staticmethod
    def _preferred_version(command: str, versions: list[str]) -> str:
        """Choose the initial version for a selected command."""
        if (
            command == "HCI_Read_Local_Supported_Commands"
            and "v1" in versions
        ):
            return "v1"
        return "v2" if "v2" in versions else versions[0]

    def _select_definition(self) -> None:
        key = (
            self._category_variable.get(),
            self._command_variable.get(),
            self._version_variable.get(),
        )
        definition = self._definition_lookup.get(key)
        if definition is not None:
            self._on_command_selected(definition.opcode)

    def _on_category_changed(self, _event: tk.Event) -> None:
        self._populate_commands()

    def _on_command_changed(self, _event: tk.Event) -> None:
        self._populate_versions()

    def _on_version_changed(self, _event: tk.Event) -> None:
        self._select_definition()

    def _notify_values_changed(self) -> None:
        if self._suspend_change_callback or self._current_definition is None:
            return
        self._update_enum_details()
        self._update_conditional_widgets()
        self._on_preview(self.get_parameter_values())

    def _update_enum_details(self) -> None:
        for name, detail_label in self._enum_detail_labels.items():
            variable = self._parameter_vars.get(name)
            display_mapping = self._enum_display_to_value.get(name)
            descriptions = self._enum_full_descriptions.get(name)
            if variable is None or display_mapping is None or descriptions is None:
                continue
            value = display_mapping.get(variable.get())
            if value is None:
                detail_label.configure(text="")
                continue
            description = descriptions.get(value, "")
            detail_label.configure(
                text=f"選択値: {description} (0x{value:02X})"
            )

    @staticmethod
    def _short_enum_label(name: str, value: int, full_label: str) -> str:
        labels: dict[str, dict[int, str]] = {
            "PHY": {
                0x01: "LE 1M",
                0x02: "LE 2M",
                0x03: "LE Coded / S=8",
                0x04: "LE Coded S=2",
            },
            "Modulation_Index": {
                0x00: "Standard",
                0x01: "Stable",
            },
            "Packet_Payload": {
                0x00: "PRBS9",
                0x01: "11110000",
                0x02: "10101010",
                0x03: "PRBS15",
                0x04: "11111111",
                0x05: "00000000",
                0x06: "00001111",
                0x07: "01010101",
            },
            "Expected_CTE_Type": {
                0x00: "AoA",
                0x01: "AoD 1 us",
                0x02: "AoD 2 us",
            },
            "CTE_Type": {
                0x00: "AoA",
                0x01: "AoD 1 us",
                0x02: "AoD 2 us",
            },
            "TX_Power_Mode": {
                0x00: "Numeric",
                0x01: "Minimum",
                0x02: "Maximum",
            },
        }
        return labels.get(name, {}).get(value, full_label)

    def _update_conditional_widgets(self) -> None:
        mode_variable = self._parameter_vars.get("TX_Power_Mode")
        power_widget = self._parameter_widgets.get("TX_Power_Level")
        mapping = self._enum_display_to_value.get("TX_Power_Mode")
        if mode_variable is None or power_widget is None or mapping is None:
            return
        numeric_mode = mapping.get(mode_variable.get()) == 0
        power_widget.configure(state=tk.NORMAL if numeric_mode else tk.DISABLED)

    def _request_send(self) -> None:
        self._on_send(self.get_parameter_values())

    def _scroll_parameter_canvas(self, event: tk.Event) -> str:
        """Scroll parameter content when the wheel is used over its blank area."""
        button_number = getattr(event, "num", None)
        if button_number == 4:
            units = -1
        elif button_number == 5:
            units = 1
        else:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return "break"
            units = -max(1, abs(delta) // 120) if delta > 0 else max(
                1, abs(delta) // 120
            )
        self._parameter_canvas.yview_scroll(units, "units")
        return "break"

    def _update_send_state(self) -> None:
        enabled = (
            self._connected
            and not self._busy
            and self._preview_valid
            and self._selected_command_supported is not False
        )
        self._send_button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
        quick_enabled = self._connected and not self._busy
        self._quick_reset_button.configure(
            state=(
                tk.NORMAL
                if quick_enabled
                and self._command_support.get(0x0C03) is not False
                else tk.DISABLED
            )
        )
        self._quick_test_end_button.configure(
            state=(
                tk.NORMAL
                if quick_enabled
                and self._command_support.get(0x201F) is not False
                else tk.DISABLED
            )
        )

    def _update_support_text(self) -> None:
        if self._selected_command_supported is True:
            self._support_variable.set("対応状況: Controller対応")
        elif self._selected_command_supported is False:
            self._support_variable.set(
                "対応状況: Controller未対応（送信できません）"
            )
        else:
            self._support_variable.set("対応状況: 未取得")

    def _event_matches_filter(self, event: TransportEvent) -> bool:
        selected = self._filter_variable.get()
        if selected == "すべて":
            return True
        if selected == "TX":
            return event.kind == TransportEventKind.TRANSMITTED
        if selected == "RX":
            return event.kind == TransportEventKind.RECEIVED
        return event.kind in (
            TransportEventKind.ERROR,
            TransportEventKind.RESPONSE_TIMEOUT,
        )

    def _render_log(self) -> None:
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)
        for event in self._events:
            if self._event_matches_filter(event):
                self._append_event_text(event)

    def _append_event_text(self, event: TransportEvent) -> None:
        lines = format_transport_event(event)
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, "\n".join(lines) + "\n")
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)
