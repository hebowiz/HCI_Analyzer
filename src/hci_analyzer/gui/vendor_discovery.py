"""Tkinter GUI for comparing captured vendor-specific HCI commands."""

from __future__ import annotations

import json
import tkinter as tk
from collections import defaultdict
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from hci_analyzer.vendor.discovery import (
    VendorAnalysis,
    VendorCapture,
    analyze_captures,
    build_definition_draft,
    format_analysis_report,
    load_vendor_captures,
    parse_annotations,
)


class VendorDiscoveryWindow:
    """Present JSONL loading, capture annotation, inference, and export."""

    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title("HCI Vendor Command Discovery")
        self._root.geometry("1180x780")
        self._root.minsize(900, 620)
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(2, weight=1)
        self._root.rowconfigure(4, weight=1)

        self._captures: list[VendorCapture] = []
        self._captures_by_opcode: dict[int, list[VendorCapture]] = {}
        self._opcode_display_to_value: dict[str, int] = {}
        self._tree_item_to_capture: dict[str, VendorCapture] = {}
        self._current_analysis: VendorAnalysis | None = None

        self._opcode_variable = tk.StringVar()
        self._annotation_variable = tk.StringVar()
        self._command_name_variable = tk.StringVar()
        self._status_variable = tk.StringVar(
            value="Analyzer JSONLを読み込んでください"
        )
        self._build_window()

    def run(self) -> None:
        """Start the Vendor Discovery event loop."""
        self._root.mainloop()

    def _build_window(self) -> None:
        file_frame = ttk.LabelFrame(self._root, text="入力")
        file_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        file_frame.columnconfigure(3, weight=1)
        ttk.Button(
            file_frame,
            text="JSONL読込",
            command=self._load_jsonl,
        ).grid(row=0, column=0, padx=(8, 12), pady=8)
        ttk.Label(file_frame, text="Vendor Opcode").grid(
            row=0, column=1, padx=(0, 4), pady=8
        )
        self._opcode_combo = ttk.Combobox(
            file_frame,
            textvariable=self._opcode_variable,
            state="readonly",
            width=34,
        )
        self._opcode_combo.grid(row=0, column=2, padx=(0, 12), pady=8)
        self._opcode_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._show_selected_opcode(),
        )
        ttk.Label(
            file_frame,
            textvariable=self._status_variable,
        ).grid(row=0, column=3, sticky="w", padx=(0, 8), pady=8)

        annotation_frame = ttk.LabelFrame(
            self._root,
            text="選択キャプチャの既知パラメーター",
        )
        annotation_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        annotation_frame.columnconfigure(1, weight=1)
        ttk.Label(annotation_frame, text="name=value").grid(
            row=0, column=0, padx=(8, 6), pady=8
        )
        self._annotation_entry = ttk.Entry(
            annotation_frame,
            textvariable=self._annotation_variable,
        )
        self._annotation_entry.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 6),
            pady=8,
        )
        self._annotation_entry.bind(
            "<Return>",
            lambda _event: self._save_annotation(),
        )
        ttk.Button(
            annotation_frame,
            text="注釈を反映",
            command=self._save_annotation,
        ).grid(row=0, column=2, padx=(0, 8), pady=8)
        ttk.Label(
            annotation_frame,
            text="例: channel=19, power=-10, mode=tx",
        ).grid(row=1, column=1, sticky="w", padx=(0, 6), pady=(0, 8))

        capture_frame = ttk.LabelFrame(self._root, text="Vendor Command Captures")
        capture_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        capture_frame.columnconfigure(0, weight=1)
        capture_frame.rowconfigure(0, weight=1)
        columns = (
            "index",
            "timestamp",
            "source",
            "parameters",
            "annotations",
            "responses",
        )
        self._capture_tree = ttk.Treeview(
            capture_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "index": "#",
            "timestamp": "Timestamp",
            "source": "Source",
            "parameters": "Command Parameters",
            "annotations": "Known Values",
            "responses": "Responses",
        }
        widths = {
            "index": 45,
            "timestamp": 190,
            "source": 120,
            "parameters": 280,
            "annotations": 280,
            "responses": 80,
        }
        for column in columns:
            self._capture_tree.heading(column, text=headings[column])
            self._capture_tree.column(
                column,
                width=widths[column],
                stretch=column in ("parameters", "annotations"),
                anchor="w",
            )
        self._capture_tree.grid(row=0, column=0, sticky="nsew")
        self._capture_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._load_selected_annotation(),
        )
        vertical = ttk.Scrollbar(
            capture_frame,
            orient=tk.VERTICAL,
            command=self._capture_tree.yview,
        )
        horizontal = ttk.Scrollbar(
            capture_frame,
            orient=tk.HORIZONTAL,
            command=self._capture_tree.xview,
        )
        self._capture_tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        action_frame = ttk.Frame(self._root)
        action_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        action_frame.columnconfigure(1, weight=1)
        ttk.Label(action_frame, text="Command Name").grid(
            row=0, column=0, padx=(0, 6), pady=4
        )
        ttk.Entry(
            action_frame,
            textvariable=self._command_name_variable,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(
            action_frame,
            text="差分・型候補を解析",
            command=self._analyze,
        ).grid(row=0, column=2, padx=(0, 6), pady=4)
        self._export_button = ttk.Button(
            action_frame,
            text="定義案JSON出力",
            command=self._export_definition,
            state=tk.DISABLED,
        )
        self._export_button.grid(row=0, column=3, pady=4)

        report_frame = ttk.LabelFrame(self._root, text="解析結果")
        report_frame.grid(
            row=4,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(5, 10),
        )
        report_frame.columnconfigure(0, weight=1)
        report_frame.rowconfigure(0, weight=1)
        self._report_text = scrolledtext.ScrolledText(
            report_frame,
            wrap=tk.NONE,
            state=tk.DISABLED,
            font=("Consolas", 10),
        )
        self._report_text.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=6,
            pady=6,
        )

    def _load_jsonl(self) -> None:
        selected = filedialog.askopenfilenames(
            parent=self._root,
            title="Analyzer JSONLを選択",
            initialdir="logs",
            filetypes=(
                ("JSON Lines", "*.jsonl"),
                ("All files", "*.*"),
            ),
        )
        if not selected:
            return
        captures, errors = load_vendor_captures(Path(item) for item in selected)
        self._captures = captures
        grouped: dict[int, list[VendorCapture]] = defaultdict(list)
        for capture in captures:
            grouped[capture.opcode].append(capture)
        self._captures_by_opcode = dict(grouped)
        self._opcode_display_to_value.clear()
        display_values: list[str] = []
        for opcode, items in sorted(self._captures_by_opcode.items()):
            display = (
                f"0x{opcode:04X} / OCF 0x{opcode & 0x03FF:03X} "
                f"({len(items)} captures)"
            )
            self._opcode_display_to_value[display] = opcode
            display_values.append(display)
        self._opcode_combo.configure(values=display_values)
        if display_values:
            self._opcode_variable.set(display_values[0])
            self._show_selected_opcode()
        else:
            self._opcode_variable.set("")
            self._clear_tree()
            self._set_report(
                "Vendor Specific Command (OGF 0x3F) was not found."
            )
        status = (
            f"{len(selected)} files / {len(captures)} captures / "
            f"{len(errors)} read errors"
        )
        self._status_variable.set(status)
        if errors:
            messagebox.showwarning(
                "JSONL読込警告",
                "\n".join(errors[:10]),
                parent=self._root,
            )

    def _show_selected_opcode(self) -> None:
        opcode = self._selected_opcode()
        if opcode is None:
            return
        self._current_analysis = None
        self._export_button.configure(state=tk.DISABLED)
        self._command_name_variable.set(f"Vendor_Command_0x{opcode:04X}")
        self._clear_tree()
        for index, capture in enumerate(
            self._captures_by_opcode.get(opcode, []),
            start=1,
        ):
            item_id = f"capture_{index}"
            self._tree_item_to_capture[item_id] = capture
            annotations = ", ".join(
                f"{name}={value}"
                for name, value in capture.annotations.items()
            )
            self._capture_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    index,
                    capture.timestamp,
                    capture.source,
                    capture.parameters.hex(" ").upper() or "-",
                    annotations or "-",
                    len(capture.responses),
                ),
            )
        children = self._capture_tree.get_children()
        if children:
            self._capture_tree.selection_set(children[0])
            self._capture_tree.focus(children[0])
            self._load_selected_annotation()
        self._set_report(
            "Add known name=value annotations to captures, then run analysis."
        )

    def _save_annotation(self) -> None:
        capture = self._selected_capture()
        if capture is None:
            messagebox.showinfo(
                "注釈",
                "キャプチャを1行選択してください。",
                parent=self._root,
            )
            return
        try:
            capture.annotations = parse_annotations(
                self._annotation_variable.get()
            )
        except ValueError as exc:
            messagebox.showerror("注釈エラー", str(exc), parent=self._root)
            return
        item_id = self._capture_tree.selection()[0]
        values = list(self._capture_tree.item(item_id, "values"))
        values[4] = (
            ", ".join(
                f"{name}={value}"
                for name, value in capture.annotations.items()
            )
            or "-"
        )
        self._capture_tree.item(item_id, values=values)
        self._current_analysis = None
        self._export_button.configure(state=tk.DISABLED)

    def _load_selected_annotation(self) -> None:
        capture = self._selected_capture()
        if capture is None:
            self._annotation_variable.set("")
            return
        self._annotation_variable.set(
            ", ".join(
                f"{name}={value}"
                for name, value in capture.annotations.items()
            )
        )

    def _analyze(self) -> None:
        opcode = self._selected_opcode()
        if opcode is None:
            messagebox.showinfo(
                "解析",
                "Vendor Opcodeを選択してください。",
                parent=self._root,
            )
            return
        captures = self._captures_by_opcode.get(opcode, [])
        try:
            analysis = analyze_captures(captures)
        except ValueError as exc:
            messagebox.showerror("解析エラー", str(exc), parent=self._root)
            return
        self._current_analysis = analysis
        self._set_report(format_analysis_report(captures, analysis))
        self._export_button.configure(state=tk.NORMAL)

    def _export_definition(self) -> None:
        analysis = self._current_analysis
        if analysis is None:
            return
        captures = self._captures_by_opcode.get(analysis.opcode, [])
        default_directory = Path("vendor_definitions")
        try:
            default_directory.mkdir(parents=True, exist_ok=True)
            initial_directory = str(default_directory.resolve())
        except OSError:
            initial_directory = (
                str(captures[0].source_path.parent) if captures else "."
            )
        path_text = filedialog.asksaveasfilename(
            parent=self._root,
            title="ベンダーコマンド定義案を保存",
            initialdir=initial_directory,
            initialfile=f"vendor_0x{analysis.opcode:04X}_definition_draft.json",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"),),
        )
        if not path_text:
            return
        draft = build_definition_draft(
            analysis,
            self._command_name_variable.get(),
            captures,
        )
        try:
            Path(path_text).write_text(
                json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            messagebox.showerror(
                "保存エラー",
                f"{type(exc).__name__}: {exc}",
                parent=self._root,
            )
            return
        self._status_variable.set(f"Definition draft saved: {path_text}")

    def _selected_opcode(self) -> int | None:
        return self._opcode_display_to_value.get(self._opcode_variable.get())

    def _selected_capture(self) -> VendorCapture | None:
        selection = self._capture_tree.selection()
        if not selection:
            return None
        return self._tree_item_to_capture.get(selection[0])

    def _clear_tree(self) -> None:
        for item_id in self._capture_tree.get_children():
            self._capture_tree.delete(item_id)
        self._tree_item_to_capture.clear()
        self._annotation_variable.set("")

    def _set_report(self, text: str) -> None:
        self._report_text.configure(state=tk.NORMAL)
        self._report_text.delete("1.0", tk.END)
        self._report_text.insert("1.0", text)
        self._report_text.configure(state=tk.DISABLED)
