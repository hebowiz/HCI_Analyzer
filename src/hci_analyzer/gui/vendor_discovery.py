"""Tkinter GUI for live vendor-HCI command discovery and incremental inference."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from typing import Callable

from hci_analyzer.config import (
    DEFAULT_BAUD_RATE,
    SUPPORTED_BAUD_RATES,
)
from hci_analyzer.models import LogRecord
from hci_analyzer.presentation.text import ascii_safe_text
from hci_analyzer.vendor.discovery import (
    VendorAnalysis,
    analyze_captures,
    build_definition_draft,
    format_analysis_report,
    load_vendor_captures,
)
from hci_analyzer.vendor.live_capture import (
    DiscoveryCapture,
    LiveCaptureStore,
)
from hci_analyzer.vendor.project import (
    MANUAL_FIELD_TYPES,
    NUMBER_FORMATS,
    PARAMETER_KINDS,
    UserParameter,
    VendorDiscoveryProject,
    build_console_definition,
    load_project,
    save_project,
)
from hci_analyzer.vendor_settings import (
    VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE,
    VENDOR_DISCOVERY_MINIMUM_WINDOW_SIZE,
)

PARAMETER_KIND_LABELS = {
    "auto": "自動判定",
    "unsigned": "符号なし整数",
    "signed": "符号付き整数",
    "enum": "選択値（Enum）",
    "boolean": "真偽値",
    "bit_field": "ビットフィールド",
    "raw_bytes": "RAWバイト列",
}
PARAMETER_KIND_VALUES = {
    label: value for value, label in PARAMETER_KIND_LABELS.items()
}
NUMBER_FORMAT_LABELS = {
    "decimal": "10進",
    "hex": "16進",
}
NUMBER_FORMAT_VALUES = {
    label: value for value, label in NUMBER_FORMAT_LABELS.items()
}
PARAMETER_STATUS_LABELS = {
    "not_analyzed": "未解析",
    "candidate": "候補あり",
    "not_found": "候補なし",
    "confirmed": "確定済み",
}
CONFIDENCE_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "manual": "手動",
}


def _matches_opcode_filter(entry: DiscoveryCapture, opcode: int) -> bool:
    """Return whether a capture belongs to the selected Vendor opcode."""
    if entry.vendor_capture is not None:
        return entry.vendor_capture.opcode == opcode
    return entry.protocol == "HCI Event" and entry.related_opcode == opcode


class VendorDiscoveryWindow:
    """Present live capture, filtering, user fields, inference, and export."""

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_refresh = on_refresh
        self._root = tk.Tk()
        self._root.title("HCI ベンダーコマンド解析")
        self._root.geometry(
            f"{VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE[0]}x"
            f"{VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE[1]}"
        )
        self._root.minsize(*VENDOR_DISCOVERY_MINIMUM_WINDOW_SIZE)
        self._root.protocol("WM_DELETE_WINDOW", on_close)
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(2, weight=3)
        self._root.rowconfigure(4, weight=1)
        self._root.rowconfigure(6, weight=2)

        self._store = LiveCaptureStore()
        self._projects: dict[int, VendorDiscoveryProject] = {}
        self._active_opcode: int | None = None
        self._opcode_display_to_value: dict[str, int] = {}
        self._capture_rows: dict[str, tuple[DiscoveryCapture, ...]] = {}
        self._parameter_rows: dict[str, str] = {}
        self._current_analysis: VendorAnalysis | None = None

        self._opcode_variable = tk.StringVar()
        self._command_name_variable = tk.StringVar()
        self._known_value_variable = tk.StringVar()
        self._group_duplicates_variable = tk.BooleanVar(value=False)
        self._filter_selected_opcode_variable = tk.BooleanVar(value=False)
        self._status_variable = tk.StringVar(value="停止中")
        self._build_window()

    def run(self) -> None:
        self._root.mainloop()

    def after(self, milliseconds: int, callback: Callable[[], None]) -> None:
        self._root.after(milliseconds, callback)

    def destroy(self) -> None:
        self._root.destroy()

    def set_window_size(self, width: int, height: int) -> None:
        width = min(
            max(width, VENDOR_DISCOVERY_MINIMUM_WINDOW_SIZE[0]),
            self._root.winfo_screenwidth(),
        )
        height = min(
            max(height, VENDOR_DISCOVERY_MINIMUM_WINDOW_SIZE[1]),
            self._root.winfo_screenheight(),
        )
        self._root.geometry(f"{width}x{height}")

    def get_window_size(self) -> tuple[int, int]:
        self._root.update_idletasks()
        return self._root.winfo_width(), self._root.winfo_height()

    def set_serial_ports(
        self,
        ports: list[str],
        preferred_port_one: str | None = None,
        preferred_port_two: str | None = None,
    ) -> None:
        current_one = self._port_one_combo.get()
        current_two = self._port_two_combo.get()
        self._port_one_combo.configure(values=ports)
        self._port_two_combo.configure(values=ports)
        self._port_one_combo.set(
            _preferred_port(ports, preferred_port_one, current_one, 0)
        )
        self._port_two_combo.set(
            _preferred_port(ports, preferred_port_two, current_two, 1)
        )

    def set_baud_rate(self, baud_rate: int) -> None:
        selected = (
            baud_rate if baud_rate in SUPPORTED_BAUD_RATES else DEFAULT_BAUD_RATE
        )
        self._baud_combo.set(str(selected))

    def get_monitor_settings(self) -> tuple[str, str, int]:
        return (
            self._port_one_combo.get().strip(),
            self._port_two_combo.get().strip(),
            int(self._baud_combo.get()),
        )

    def set_monitoring_state(self, active: bool) -> None:
        selector_state = tk.DISABLED if active else "readonly"
        self._port_one_combo.configure(state=selector_state)
        self._port_two_combo.configure(state=selector_state)
        self._baud_combo.configure(state=selector_state)
        self._refresh_button.configure(
            state=tk.DISABLED if active else tk.NORMAL
        )
        self._start_button.configure(
            state=tk.DISABLED if active else tk.NORMAL
        )
        self._stop_button.configure(
            state=tk.NORMAL if active else tk.DISABLED
        )
        self._status_variable.set("取得中" if active else "停止中")

    def set_group_duplicates(self, enabled: bool) -> None:
        self._group_duplicates_variable.set(enabled)
        self._refresh_capture_tree()

    def get_group_duplicates(self) -> bool:
        return self._group_duplicates_variable.get()

    def add_monitor_record(self, record: LogRecord) -> None:
        """Consume one monitor record on the Tkinter main thread."""
        added = self._store.add_record(record)
        if added is not None:
            self._refresh_all_views(select_capture_id=added.capture_id)
            self._status_variable.set(
                f"{len(self._store.entries)}件の項目を取得"
            )
            return
        if record.result is not None and not record.result.success:
            error = record.result.error
            if error is not None:
                self._status_variable.set(f"{error.code}: {error.message}")
        elif record.result is not None and record.result.packet_type == "HCI_Event":
            self._refresh_capture_tree()

    def show_error(self, title: str, exc: Exception) -> None:
        messagebox.showerror(
            title,
            f"{type(exc).__name__}: {exc}",
            parent=self._root,
        )

    def _build_window(self) -> None:
        self._build_serial_frame()
        self._build_input_frame()
        self._build_capture_frame()
        self._build_capture_action_frame()
        self._build_parameter_frame()
        self._build_command_action_frame()
        self._build_report_frame()

    def _build_serial_frame(self) -> None:
        frame = ttk.LabelFrame(self._root, text="リアルタイムシリアル取得")
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ttk.Label(frame, text="ポート1").grid(
            row=0, column=0, padx=(8, 4), pady=8
        )
        self._port_one_combo = ttk.Combobox(
            frame, state="readonly", width=12
        )
        self._port_one_combo.grid(row=0, column=1, padx=(0, 10), pady=8)
        ttk.Label(frame, text="ポート2").grid(
            row=0, column=2, padx=(0, 4), pady=8
        )
        self._port_two_combo = ttk.Combobox(
            frame, state="readonly", width=12
        )
        self._port_two_combo.grid(row=0, column=3, padx=(0, 10), pady=8)
        ttk.Label(frame, text="ボーレート").grid(
            row=0, column=4, padx=(0, 4), pady=8
        )
        self._baud_combo = ttk.Combobox(
            frame,
            state="readonly",
            width=12,
            values=[str(value) for value in SUPPORTED_BAUD_RATES],
        )
        self._baud_combo.set(str(DEFAULT_BAUD_RATE))
        self._baud_combo.grid(row=0, column=5, padx=(0, 10), pady=8)
        self._refresh_button = ttk.Button(
            frame, text="ポート更新", command=self._on_refresh
        )
        self._refresh_button.grid(row=0, column=6, padx=(0, 6), pady=8)
        self._start_button = ttk.Button(
            frame, text="取得開始", command=self._on_start
        )
        self._start_button.grid(row=0, column=7, padx=(0, 6), pady=8)
        self._stop_button = ttk.Button(
            frame,
            text="取得終了",
            command=self._on_stop,
            state=tk.DISABLED,
        )
        self._stop_button.grid(row=0, column=8, padx=(0, 10), pady=8)
        ttk.Label(frame, textvariable=self._status_variable).grid(
            row=0, column=9, sticky="w", padx=(0, 8), pady=8
        )

    def _build_input_frame(self) -> None:
        frame = ttk.LabelFrame(self._root, text="キャプチャーとプロジェクト")
        frame.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        ttk.Button(frame, text="JSONL読込", command=self._load_jsonl).grid(
            row=0, column=0, padx=(8, 6), pady=8
        )
        ttk.Button(frame, text="プロジェクトを開く", command=self._open_project).grid(
            row=0, column=1, padx=(0, 6), pady=8
        )
        ttk.Button(frame, text="プロジェクト保存", command=self._save_project).grid(
            row=0, column=2, padx=(0, 12), pady=8
        )
        ttk.Label(frame, text="解析対象Opcode").grid(
            row=0, column=3, padx=(0, 4), pady=8
        )
        self._opcode_combo = ttk.Combobox(
            frame,
            textvariable=self._opcode_variable,
            state="readonly",
            width=34,
        )
        self._opcode_combo.grid(row=0, column=4, padx=(0, 12), pady=8)
        self._opcode_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._select_opcode(),
        )
        ttk.Checkbutton(
            frame,
            text="重複キャプチャーをまとめる",
            variable=self._group_duplicates_variable,
            command=self._refresh_capture_tree,
        ).grid(row=0, column=5, padx=(0, 8), pady=8)
        ttk.Checkbutton(
            frame,
            text="選択Opcodeのみ表示",
            variable=self._filter_selected_opcode_variable,
            command=self._refresh_capture_tree,
        ).grid(row=0, column=6, padx=(0, 8), pady=8)

    def _build_capture_frame(self) -> None:
        frame = ttk.LabelFrame(
            self._root,
            text="検出フレーム（標準は時系列表示）",
        )
        frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = (
            "index",
            "timestamp",
            "source",
            "protocol",
            "identifier",
            "parameters",
            "known",
            "responses",
            "count",
        )
        self._capture_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        headings = {
            "index": "#",
            "timestamp": "タイムスタンプ",
            "source": "取得元",
            "protocol": "プロトコル",
            "identifier": "Opcode / Event / Command ID",
            "parameters": "パラメーター / Payload",
            "known": "既知値",
            "responses": "応答数",
            "count": "件数",
        }
        widths = {
            "index": 45,
            "timestamp": 190,
            "source": 120,
            "protocol": 90,
            "identifier": 175,
            "parameters": 270,
            "known": 240,
            "responses": 75,
            "count": 55,
        }
        for column in columns:
            self._capture_tree.heading(column, text=headings[column])
            self._capture_tree.column(
                column,
                width=widths[column],
                stretch=column in ("parameters", "known"),
                anchor="w",
            )
        self._capture_tree.grid(row=0, column=0, sticky="nsew")
        self._capture_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._capture_selection_changed(),
        )
        self._capture_tree.bind("<Delete>", lambda _event: self._remove_selected())
        vertical = ttk.Scrollbar(
            frame, orient=tk.VERTICAL, command=self._capture_tree.yview
        )
        horizontal = ttk.Scrollbar(
            frame, orient=tk.HORIZONTAL, command=self._capture_tree.xview
        )
        self._capture_tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

    def _build_capture_action_frame(self) -> None:
        frame = ttk.Frame(self._root)
        frame.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        ttk.Button(
            frame,
            text="選択項目を除外",
            command=self._remove_selected,
        ).grid(row=0, column=0, padx=(0, 6))
        self._restore_button = ttk.Button(
            frame,
            text="除外を元に戻す",
            command=self._restore_removed,
            state=tk.DISABLED,
        )
        self._restore_button.grid(row=0, column=1, padx=(0, 16))
        ttk.Label(frame, text="選択パラメーターの既知値").grid(
            row=0, column=2, padx=(0, 4)
        )
        ttk.Entry(
            frame,
            textvariable=self._known_value_variable,
            width=24,
        ).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(
            frame,
            text="選択キャプチャーへ設定",
            command=self._assign_known_value,
        ).grid(row=0, column=4)

    def _build_parameter_frame(self) -> None:
        frame = ttk.LabelFrame(self._root, text="ユーザー定義パラメーター")
        frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(frame)
        toolbar.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=6,
            pady=(4, 6),
        )
        ttk.Button(toolbar, text="追加", command=self._add_parameter).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="編集", command=self._edit_parameter).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="削除", command=self._delete_parameter).pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Button(
            toolbar,
            text="選択項目を解析",
            command=self._analyze_parameter,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            toolbar,
            text="配置を手動設定...",
            command=self._set_manual_layout,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            toolbar,
            text="候補を確定...",
            command=self._confirm_parameter,
        ).pack(side=tk.LEFT)
        columns = ("name", "display", "kind", "status", "layout")
        self._parameter_tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=5,
        )
        for column, heading, width in (
            ("name", "内部名", 150),
            ("display", "表示名", 180),
            ("kind", "種類", 130),
            ("status", "状態", 110),
            ("layout", "確定した配置", 260),
        ):
            self._parameter_tree.heading(column, text=heading)
            self._parameter_tree.column(
                column,
                width=width,
                stretch=column in ("display", "layout"),
                anchor="w",
            )
        self._parameter_tree.grid(row=1, column=0, sticky="nsew")
        self._parameter_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._parameter_selection_changed(),
        )
        scrollbar = ttk.Scrollbar(
            frame,
            orient=tk.VERTICAL,
            command=self._parameter_tree.yview,
        )
        scrollbar.grid(row=1, column=1, sticky="ns")
        self._parameter_tree.configure(yscrollcommand=scrollbar.set)

    def _build_command_action_frame(self) -> None:
        frame = ttk.Frame(self._root)
        frame.grid(row=5, column=0, sticky="ew", padx=10, pady=4)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="コマンド名").grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Entry(
            frame,
            textvariable=self._command_name_variable,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(
            frame,
            text="全既知値を解析",
            command=self._analyze_all,
        ).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(
            frame,
            text="定義案を出力",
            command=self._export_draft,
        ).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(
            frame,
            text="Console定義を出力",
            command=self._export_console_definition,
        ).grid(row=0, column=4)

    def _build_report_frame(self) -> None:
        frame = ttk.LabelFrame(self._root, text="解析結果")
        frame.grid(
            row=6,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(4, 10),
        )
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self._report_text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.NONE,
            state=tk.DISABLED,
            font=("Consolas", 10),
        )
        self._report_text.grid(
            row=0, column=0, sticky="nsew", padx=6, pady=6
        )

    def _load_jsonl(self) -> None:
        selected = filedialog.askopenfilenames(
            parent=self._root,
            title="AnalyzerのJSONLを選択",
            initialdir="logs",
            filetypes=(("JSON Lines", "*.jsonl"), ("すべてのファイル", "*.*")),
        )
        if not selected:
            return
        captures, errors = load_vendor_captures(Path(item) for item in selected)
        self._store.add_vendor_captures(captures)
        self._refresh_all_views()
        self._status_variable.set(
            f"{len(selected)}ファイルから{len(captures)}件を読み込みました"
        )
        if errors:
            messagebox.showwarning(
                "JSONL読込警告",
                "\n".join(errors[:10]),
                parent=self._root,
            )

    def _open_project(self) -> None:
        path_text = filedialog.askopenfilename(
            parent=self._root,
            title="ベンダー解析プロジェクトを開く",
            initialdir="vendor_projects",
            filetypes=(("解析プロジェクト", "*.json"),),
        )
        if not path_text:
            return
        try:
            project, captures = load_project(Path(path_text))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.show_error("プロジェクト読込エラー", exc)
            return
        self._store.replace_entries(captures)
        self._projects.clear()
        if project.opcode is not None:
            self._projects[project.opcode] = project
        self._active_opcode = None
        self._refresh_all_views()
        self._select_opcode(project.opcode)
        self._status_variable.set(f"プロジェクトを開きました: {path_text}")

    def _save_project(self) -> None:
        project = self._current_project()
        if project is None:
            messagebox.showinfo(
                "プロジェクト保存",
                "先にVendor Opcodeを選択してください。",
                parent=self._root,
            )
            return
        self._sync_project_name(project)
        directory = Path("vendor_projects")
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.show_error("プロジェクト保存エラー", exc)
            return
        path_text = filedialog.asksaveasfilename(
            parent=self._root,
            title="ベンダー解析プロジェクトを保存",
            initialdir=str(directory.resolve()),
            initialfile=f"vendor_0x{project.opcode:04X}_project.json",
            defaultextension=".json",
            filetypes=(("解析プロジェクト", "*.json"),),
        )
        if not path_text:
            return
        try:
            save_project(Path(path_text), project, self._store.entries)
        except (OSError, ValueError) as exc:
            self.show_error("プロジェクト保存エラー", exc)
            return
        self._status_variable.set(f"プロジェクトを保存しました: {path_text}")

    def _refresh_all_views(self, select_capture_id: str | None = None) -> None:
        self._refresh_opcode_values()
        self._refresh_capture_tree(select_capture_id)
        self._refresh_parameter_tree()

    def _refresh_opcode_values(self) -> None:
        current = self._active_opcode
        values: list[str] = []
        self._opcode_display_to_value.clear()
        for opcode in self._store.vendor_opcodes():
            count = len(self._store.vendor_captures(opcode))
            display = (
                f"0x{opcode:04X} / OCF 0x{opcode & 0x03FF:03X} "
                f"({count}件)"
            )
            values.append(display)
            self._opcode_display_to_value[display] = opcode
        self._opcode_combo.configure(values=values)
        selected_display = next(
            (
                display
                for display, opcode in self._opcode_display_to_value.items()
                if opcode == current
            ),
            None,
        )
        if selected_display is not None:
            self._opcode_variable.set(selected_display)
        elif values:
            self._opcode_variable.set(values[0])
            self._select_opcode(self._opcode_display_to_value[values[0]])
        else:
            self._opcode_variable.set("")
            self._active_opcode = None
            self._command_name_variable.set("")

    def _refresh_capture_tree(self, select_capture_id: str | None = None) -> None:
        self._refresh_capture_tree_selection(
            select_capture_ids=(
                (select_capture_id,) if select_capture_id is not None else ()
            )
        )

    def _refresh_capture_tree_selection(
        self,
        *,
        select_capture_ids: tuple[str, ...] = (),
    ) -> None:
        for item_id in self._capture_tree.get_children():
            self._capture_tree.delete(item_id)
        self._capture_rows.clear()
        target_ids = set(select_capture_ids)
        selected_rows: list[str] = []
        groups = self._store.groups(
            group_duplicates=self._group_duplicates_variable.get()
        )
        if (
            self._filter_selected_opcode_variable.get()
            and self._active_opcode is not None
        ):
            groups = [
                group
                for group in groups
                if any(
                    _matches_opcode_filter(entry, self._active_opcode)
                    for entry in group.entries
                )
            ]
        for index, group in enumerate(groups, start=1):
            first = group.first
            item_id = f"row:{index}"
            self._capture_rows[item_id] = group.entries
            if target_ids.intersection(
                entry.capture_id for entry in group.entries
            ):
                selected_rows.append(item_id)
            vendor = first.vendor_capture
            annotations = (
                ", ".join(
                    f"{name}={value}"
                    for name, value in vendor.annotations.items()
                )
                if vendor is not None
                else "-"
            )
            responses: object = len(vendor.responses) if vendor is not None else "-"
            self._capture_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    index,
                    first.timestamp,
                    first.source,
                    first.protocol,
                    first.identifier,
                    first.parameters.hex(" ").upper() or "-",
                    annotations or "-",
                    responses,
                    group.count,
                ),
            )
        if selected_rows:
            self._capture_tree.selection_set(*selected_rows)
            self._capture_tree.focus(selected_rows[0])
            self._capture_tree.see(selected_rows[0])
        self._restore_button.configure(
            state=tk.NORMAL if self._store.can_restore else tk.DISABLED
        )

    def _refresh_parameter_tree(
        self,
        select_parameter_name: str | None = None,
    ) -> None:
        if select_parameter_name is None:
            selection = self._parameter_tree.selection()
            if selection:
                select_parameter_name = self._parameter_rows.get(selection[0])
        for item_id in self._parameter_tree.get_children():
            self._parameter_tree.delete(item_id)
        self._parameter_rows.clear()
        project = self._current_project()
        if project is None:
            return
        selected_item_id: str | None = None
        for index, parameter in enumerate(project.parameters, start=1):
            item_id = f"parameter:{index}"
            self._parameter_rows[item_id] = parameter.name
            if parameter.name == select_parameter_name:
                selected_item_id = item_id
            candidate = parameter.confirmed_candidate
            source = (
                "（手動）"
                if candidate is not None and candidate.get("source") == "manual"
                else ""
            )
            layout = (
                f"オフセット={candidate['offset']} "
                f"型={candidate['type']} サイズ={candidate['size']}{source}"
                if candidate is not None
                else "-"
            )
            self._parameter_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    parameter.name,
                    parameter.display_name,
                    PARAMETER_KIND_LABELS.get(parameter.kind, parameter.kind),
                    PARAMETER_STATUS_LABELS.get(
                        parameter.status,
                        parameter.status,
                    ),
                    layout,
                ),
            )
        if selected_item_id is not None:
            self._parameter_tree.selection_set(selected_item_id)
            self._parameter_tree.focus(selected_item_id)
            self._parameter_tree.see(selected_item_id)

    def _select_opcode(self, opcode: int | None = None) -> None:
        if self._active_opcode is not None:
            existing = self._projects.get(self._active_opcode)
            if existing is not None:
                self._sync_project_name(existing)
        if opcode is None:
            opcode = self._opcode_display_to_value.get(
                self._opcode_variable.get()
            )
        if opcode is None:
            return
        self._active_opcode = opcode
        project = self._projects.setdefault(
            opcode,
            VendorDiscoveryProject(
                opcode=opcode,
                command_name=f"Vendor_Command_0x{opcode:04X}",
            ),
        )
        self._command_name_variable.set(project.command_name)
        self._current_analysis = None
        self._refresh_capture_tree()
        self._refresh_parameter_tree()
        self._set_report(
            "Define a parameter, assign known values to selected captures, "
            "then analyze the field."
        )

    def _capture_selection_changed(self) -> None:
        entries = self._selected_capture_entries()
        parameter = self._selected_parameter()
        if len(entries) != 1 or parameter is None:
            return
        vendor = entries[0].vendor_capture
        if vendor is not None:
            self._known_value_variable.set(
                vendor.annotations.get(parameter.name, "")
            )

    def _parameter_selection_changed(self) -> None:
        self._capture_selection_changed()

    def _remove_selected(self) -> None:
        entries = self._selected_capture_entries()
        if not entries:
            return
        count = self._store.remove(entry.capture_id for entry in entries)
        self._refresh_all_views()
        self._status_variable.set(
            f"{count}件を除外しました。「除外を元に戻す」で復元できます"
        )

    def _restore_removed(self) -> None:
        count = self._store.restore_last_removed()
        self._refresh_all_views()
        self._status_variable.set(f"{count}件を復元しました")

    def _assign_known_value(self) -> None:
        parameter = self._selected_parameter()
        opcode = self._active_opcode
        if parameter is None or opcode is None:
            messagebox.showinfo(
                "既知値の設定",
                "ユーザー定義パラメーターを1つ選択してください。",
                parent=self._root,
            )
            return
        value = self._known_value_variable.get().strip()
        if not value:
            messagebox.showerror(
                "既知値の設定",
                "選択したキャプチャーで使用した値を入力してください。",
                parent=self._root,
            )
            return
        if parameter.choices and value not in parameter.choices:
            messagebox.showerror(
                "既知値の設定",
                "次の選択肢から入力してください: "
                + ", ".join(parameter.choices),
                parent=self._root,
            )
            return
        selected_entries = self._selected_capture_entries()
        selected = [
            entry.vendor_capture
            for entry in selected_entries
            if entry.opcode == opcode and entry.vendor_capture is not None
        ]
        if not selected:
            messagebox.showinfo(
                "既知値の設定",
                "解析対象OpcodeのVendor HCIキャプチャーを1件以上選択して"
                "ください。RACEは表示のみで解析対象外です。",
                parent=self._root,
            )
            return
        for capture in selected:
            capture.annotations[parameter.name] = value
        parameter.status = "not_analyzed"
        parameter.candidates.clear()
        parameter.confirmed_candidate = None
        self._refresh_capture_tree_selection(
            select_capture_ids=tuple(
                entry.capture_id for entry in selected_entries
            )
        )
        self._refresh_parameter_tree(parameter.name)
        self._status_variable.set(
            f"{len(selected)}件へ {parameter.name}={value} を設定しました"
        )

    def _add_parameter(self) -> None:
        project = self._current_project()
        if project is None:
            messagebox.showinfo(
                "パラメーター追加",
                "先にVendor Opcodeを選択してください。",
                parent=self._root,
            )
            return
        parameter = _ParameterDialog(self._root).show()
        if parameter is None:
            return
        try:
            project.add_parameter(parameter)
        except ValueError as exc:
            self.show_error("パラメーターエラー", exc)
            return
        self._refresh_parameter_tree(parameter.name)

    def _edit_parameter(self) -> None:
        project = self._current_project()
        parameter = self._selected_parameter()
        if project is None or parameter is None:
            return
        updated = _ParameterDialog(self._root, parameter).show()
        if updated is None:
            return
        try:
            project.replace_parameter(parameter.name, updated)
        except ValueError as exc:
            self.show_error("パラメーターエラー", exc)
            return
        if updated.name != parameter.name:
            for capture in self._store.vendor_captures(project.opcode or 0):
                if parameter.name in capture.annotations:
                    capture.annotations[updated.name] = capture.annotations.pop(
                        parameter.name
                    )
        self._refresh_all_views()
        self._refresh_parameter_tree(updated.name)

    def _delete_parameter(self) -> None:
        project = self._current_project()
        parameter = self._selected_parameter()
        if project is None or parameter is None:
            return
        if not messagebox.askyesno(
            "パラメーター削除",
            f"パラメーター「{parameter.display_name}」を削除しますか？",
            parent=self._root,
        ):
            return
        project.remove_parameter(parameter.name)
        for capture in self._store.vendor_captures(project.opcode or 0):
            capture.annotations.pop(parameter.name, None)
        self._refresh_all_views()

    def _analyze_parameter(self) -> None:
        project = self._current_project()
        parameter = self._selected_parameter()
        if project is None or parameter is None or project.opcode is None:
            return
        captures = self._store.vendor_captures(project.opcode)
        try:
            analysis = analyze_captures(captures)
        except ValueError as exc:
            self.show_error("解析エラー", exc)
            return
        parameter.set_candidates(
            analysis.candidates.get(parameter.name, ())
        )
        self._current_analysis = analysis
        self._refresh_parameter_tree(parameter.name)
        report = format_analysis_report(captures, analysis)
        self._set_report(
            f"TARGET PARAMETER: {parameter.name} ({parameter.kind})\n\n"
            + report
        )

    def _confirm_parameter(self) -> None:
        parameter = self._selected_parameter()
        if parameter is None:
            return
        selected_index = 0
        if len(parameter.candidates) > 1:
            options = "\n".join(
                f"{index + 1}: オフセット={candidate['offset']} "
                f"型={candidate['type']} サイズ={candidate['size']} "
                f"信頼度={CONFIDENCE_LABELS.get(candidate['confidence'], candidate['confidence'])}"
                for index, candidate in enumerate(parameter.candidates)
            )
            choice = simpledialog.askinteger(
                "候補の確定",
                options + "\n\n確定する候補番号を入力してください:",
                parent=self._root,
                minvalue=1,
                maxvalue=len(parameter.candidates),
            )
            if choice is None:
                return
            selected_index = choice - 1
        try:
            parameter.confirm_candidate(selected_index)
        except ValueError as exc:
            self.show_error("候補確定エラー", exc)
            return
        self._refresh_parameter_tree(parameter.name)
        self._status_variable.set(
            f"パラメーター「{parameter.display_name}」を確定しました"
        )

    def _set_manual_layout(self) -> None:
        parameter = self._selected_parameter()
        if parameter is None:
            messagebox.showinfo(
                "配置の手動設定",
                "ユーザー定義パラメーターを1つ選択してください。",
                parent=self._root,
            )
            return
        result = _ManualLayoutDialog(self._root, parameter).show()
        if result is None:
            return
        offset, data_type = result
        project = self._current_project()
        if project is None or project.opcode is None:
            return
        captures = self._store.vendor_captures(project.opcode)
        if not captures:
            messagebox.showinfo(
                "配置の手動設定",
                "配置を検証するためのキャプチャーがありません。",
                parent=self._root,
            )
            return
        try:
            project.set_manual_layout(
                parameter.name,
                offset,
                data_type,
                min(len(capture.parameters) for capture in captures),
            )
        except ValueError as exc:
            self.show_error("配置設定エラー", exc)
            return
        self._refresh_parameter_tree(parameter.name)
        self._status_variable.set(
            f"パラメーター「{parameter.display_name}」の配置を手動設定しました"
        )

    def _analyze_all(self) -> None:
        project = self._current_project()
        if project is None or project.opcode is None:
            return
        captures = self._store.vendor_captures(project.opcode)
        try:
            analysis = analyze_captures(captures)
        except ValueError as exc:
            self.show_error("解析エラー", exc)
            return
        self._current_analysis = analysis
        self._set_report(format_analysis_report(captures, analysis))

    def _export_draft(self) -> None:
        project = self._current_project()
        if project is None or project.opcode is None:
            return
        captures = self._store.vendor_captures(project.opcode)
        try:
            analysis = analyze_captures(captures)
        except ValueError as exc:
            self.show_error("定義案出力エラー", exc)
            return
        self._sync_project_name(project)
        draft = build_definition_draft(
            analysis,
            project.command_name,
            captures,
        )
        self._save_definition_payload(
            draft,
            f"vendor_0x{project.opcode:04X}_definition_draft.json",
        )

    def _export_console_definition(self) -> None:
        project = self._current_project()
        if project is None or project.opcode is None:
            return
        self._sync_project_name(project)
        try:
            definition = build_console_definition(
                project,
                self._store.vendor_captures(project.opcode),
            )
        except ValueError as exc:
            self.show_error("Console定義出力エラー", exc)
            return
        self._save_definition_payload(
            definition,
            f"vendor_0x{project.opcode:04X}_definition.json",
        )

    def _save_definition_payload(
        self,
        payload: dict[str, object],
        initial_file: str,
    ) -> None:
        directory = Path("vendor_definitions")
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.show_error("定義保存エラー", exc)
            return
        path_text = filedialog.asksaveasfilename(
            parent=self._root,
            title="ベンダーコマンド定義を保存",
            initialdir=str(directory.resolve()),
            initialfile=initial_file,
            defaultextension=".json",
            filetypes=(("JSON", "*.json"),),
        )
        if not path_text:
            return
        try:
            Path(path_text).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self.show_error("定義保存エラー", exc)
            return
        self._status_variable.set(f"定義を保存しました: {path_text}")

    def _selected_capture_entries(self) -> list[DiscoveryCapture]:
        result: list[DiscoveryCapture] = []
        seen: set[str] = set()
        for item_id in self._capture_tree.selection():
            for entry in self._capture_rows.get(item_id, ()):
                if entry.capture_id not in seen:
                    seen.add(entry.capture_id)
                    result.append(entry)
        return result

    def _selected_parameter(self) -> UserParameter | None:
        project = self._current_project()
        selection = self._parameter_tree.selection()
        if project is None or not selection:
            return None
        name = self._parameter_rows.get(selection[0])
        return project.parameter(name) if name is not None else None

    def _current_project(self) -> VendorDiscoveryProject | None:
        if self._active_opcode is None:
            return None
        return self._projects.get(self._active_opcode)

    def _sync_project_name(self, project: VendorDiscoveryProject) -> None:
        project.command_name = (
            self._command_name_variable.get().strip()
            or f"Vendor_Command_0x{project.opcode:04X}"
        )

    def _set_report(self, text: str) -> None:
        safe_text = ascii_safe_text(text)
        self._report_text.configure(state=tk.NORMAL)
        self._report_text.delete("1.0", tk.END)
        self._report_text.insert("1.0", safe_text)
        self._report_text.configure(state=tk.DISABLED)


class _ParameterDialog:
    """Small modal editor for one user-defined semantic parameter."""

    def __init__(
        self,
        parent: tk.Tk,
        parameter: UserParameter | None = None,
    ) -> None:
        self._parent = parent
        self._parameter = parameter
        self._result: UserParameter | None = None

    def show(self) -> UserParameter | None:
        dialog = tk.Toplevel(self._parent)
        dialog.title("ユーザー定義パラメーター")
        dialog.transient(self._parent)
        dialog.resizable(False, False)
        name = tk.StringVar(value=self._parameter.name if self._parameter else "")
        display = tk.StringVar(
            value=self._parameter.display_name if self._parameter else ""
        )
        initial_kind = self._parameter.kind if self._parameter else "auto"
        kind = tk.StringVar(
            value=PARAMETER_KIND_LABELS.get(initial_kind, initial_kind)
        )
        unit = tk.StringVar(value=self._parameter.unit if self._parameter else "")
        initial_number_format = (
            self._parameter.number_format if self._parameter else "decimal"
        )
        number_format = tk.StringVar(
            value=NUMBER_FORMAT_LABELS[initial_number_format]
        )
        choices = tk.StringVar(
            value=(
                ", ".join(self._parameter.choices)
                if self._parameter
                else ""
            )
        )
        description = tk.StringVar(
            value=self._parameter.description if self._parameter else ""
        )
        fields = (
            ("内部名", name, "entry"),
            ("表示名", display, "entry"),
            ("種類", kind, "kind"),
            ("単位", unit, "entry"),
            ("JSON数値表記", number_format, "number_format"),
            ("選択肢（カンマ区切り）", choices, "entry"),
            ("説明（入力値は value）", description, "entry"),
        )
        initial_focus: tk.Widget | None = None
        for row, (label, variable, editor) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(
                row=row, column=0, sticky="e", padx=(10, 6), pady=5
            )
            if editor == "kind":
                widget = ttk.Combobox(
                    dialog,
                    textvariable=variable,
                    values=[
                        PARAMETER_KIND_LABELS[value]
                        for value in PARAMETER_KINDS
                    ],
                    state="readonly",
                    width=34,
                )
            elif editor == "number_format":
                widget = ttk.Combobox(
                    dialog,
                    textvariable=variable,
                    values=[
                        NUMBER_FORMAT_LABELS[value]
                        for value in NUMBER_FORMATS
                    ],
                    state="readonly",
                    width=34,
                )
            else:
                widget = ttk.Entry(dialog, textvariable=variable, width=37)
            widget.grid(row=row, column=1, padx=(0, 10), pady=5)
            if initial_focus is None:
                initial_focus = widget

        def accept() -> None:
            selected_kind = PARAMETER_KIND_VALUES.get(kind.get(), kind.get())
            selected_number_format = NUMBER_FORMAT_VALUES.get(
                number_format.get(),
                number_format.get(),
            )
            preserve_inference = (
                self._parameter is not None
                and selected_kind == self._parameter.kind
                and [
                    value.strip()
                    for value in choices.get().split(",")
                    if value.strip()
                ]
                == self._parameter.choices
            )
            candidate = UserParameter(
                name=name.get().strip(),
                display_name=display.get().strip(),
                kind=selected_kind,
                unit=unit.get().strip(),
                number_format=selected_number_format,
                description=description.get().strip(),
                choices=[
                    value.strip()
                    for value in choices.get().split(",")
                    if value.strip()
                ],
                status=(
                    self._parameter.status
                    if preserve_inference
                    else "not_analyzed"
                ),
                candidates=(
                    list(self._parameter.candidates)
                    if preserve_inference
                    else []
                ),
                confirmed_candidate=(
                    dict(self._parameter.confirmed_candidate)
                    if (
                        preserve_inference
                        and self._parameter.confirmed_candidate is not None
                    )
                    else None
                ),
            )
            try:
                candidate.validate()
            except ValueError as exc:
                messagebox.showerror(
                    "パラメーターエラー", str(exc), parent=dialog
                )
                return
            self._result = candidate
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.grid(
            row=len(fields),
            column=0,
            columnspan=2,
            pady=(8, 10),
        )
        ttk.Button(button_frame, text="決定", command=accept).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(
            button_frame, text="キャンセル", command=dialog.destroy
        ).grid(row=0, column=1, padx=4)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        _center_dialog(dialog, self._parent)
        _activate_modal_dialog(dialog, initial_focus)
        self._parent.wait_window(dialog)
        return self._result


class _ManualLayoutDialog:
    """Modal editor for a confirmed field offset and encoding type."""

    def __init__(self, parent: tk.Tk, parameter: UserParameter) -> None:
        self._parent = parent
        self._parameter = parameter
        self._result: tuple[int, str] | None = None

    def show(self) -> tuple[int, str] | None:
        dialog = tk.Toplevel(self._parent)
        dialog.title("配置の手動設定")
        dialog.transient(self._parent)
        dialog.resizable(False, False)
        candidate = self._parameter.confirmed_candidate or {}
        offset = tk.StringVar(value=str(candidate.get("offset", 0)))
        data_type = tk.StringVar(
            value=str(candidate.get("type", _default_manual_type(self._parameter)))
        )

        ttk.Label(dialog, text="パラメーター").grid(
            row=0, column=0, sticky="e", padx=(10, 6), pady=6
        )
        ttk.Label(
            dialog,
            text=f"{self._parameter.display_name} ({self._parameter.name})",
        ).grid(row=0, column=1, sticky="w", padx=(0, 10), pady=6)
        ttk.Label(dialog, text="オフセット").grid(
            row=1, column=0, sticky="e", padx=(10, 6), pady=6
        )
        offset_entry = ttk.Entry(dialog, textvariable=offset, width=24)
        offset_entry.grid(
            row=1, column=1, sticky="w", padx=(0, 10), pady=6
        )
        ttk.Label(dialog, text="型").grid(
            row=2, column=0, sticky="e", padx=(10, 6), pady=6
        )
        ttk.Combobox(
            dialog,
            textvariable=data_type,
            values=MANUAL_FIELD_TYPES,
            state="readonly",
            width=22,
        ).grid(row=2, column=1, sticky="w", padx=(0, 10), pady=6)
        def accept() -> None:
            try:
                parsed_offset = int(offset.get().strip(), 0)
                probe = UserParameter(
                    name=self._parameter.name,
                    display_name=self._parameter.display_name,
                    kind=self._parameter.kind,
                    choices=list(self._parameter.choices),
                )
                probe.set_manual_candidate(parsed_offset, data_type.get())
            except ValueError as exc:
                messagebox.showerror(
                    "配置設定エラー",
                    str(exc),
                    parent=dialog,
                )
                return
            self._result = parsed_offset, data_type.get()
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=3, column=0, columnspan=2, pady=(8, 10))
        ttk.Button(buttons, text="決定", command=accept).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(
            buttons,
            text="キャンセル",
            command=dialog.destroy,
        ).grid(row=0, column=1, padx=4)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        _center_dialog(dialog, self._parent)
        _activate_modal_dialog(dialog, offset_entry)
        self._parent.wait_window(dialog)
        return self._result


def _preferred_port(
    ports: list[str],
    preferred: str | None,
    current: str,
    fallback_index: int,
) -> str:
    if preferred in ports:
        return str(preferred)
    if current in ports:
        return current
    if ports:
        return ports[min(fallback_index, len(ports) - 1)]
    return ""


def _default_manual_type(parameter: UserParameter) -> str:
    if parameter.kind == "signed":
        return "int8"
    if parameter.kind in ("enum", "boolean"):
        return "enum_u8"
    return "uint8"


def _center_dialog(dialog: tk.Toplevel, parent: tk.Tk) -> None:
    """Place a completed dialog at the center of its parent window."""
    parent.update_idletasks()
    dialog.update_idletasks()
    width = dialog.winfo_reqwidth()
    height = dialog.winfo_reqheight()
    x, y = _centered_position(
        parent_x=parent.winfo_rootx(),
        parent_y=parent.winfo_rooty(),
        parent_width=parent.winfo_width(),
        parent_height=parent.winfo_height(),
        dialog_width=width,
        dialog_height=height,
        screen_width=dialog.winfo_screenwidth(),
        screen_height=dialog.winfo_screenheight(),
    )
    dialog.geometry(f"{width}x{height}+{x}+{y}")


def _activate_modal_dialog(
    dialog: tk.Toplevel,
    initial_focus: tk.Widget | None = None,
) -> None:
    """Bring a modal dialog forward and move keyboard focus into it."""
    dialog.wait_visibility()
    dialog.lift()
    dialog.grab_set()
    dialog.focus_force()
    if initial_focus is not None:
        initial_focus.focus_set()


def _centered_position(
    *,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    dialog_width: int,
    dialog_height: int,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    """Calculate a parent-centered position clamped to the visible screen."""
    x = parent_x + (parent_width - dialog_width) // 2
    y = parent_y + (parent_height - dialog_height) // 2
    return (
        min(max(0, x), max(0, screen_width - dialog_width)),
        min(max(0, y), max(0, screen_height - dialog_height)),
    )
