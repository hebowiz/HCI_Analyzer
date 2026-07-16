"""Window for previewing and exporting an HCI sequence diagram."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from hci_analyzer.sequence.diagram import HciSequenceDiagram


class SequenceDiagramWindow:
    """Display a Markdown-style preview in an independent window."""

    def __init__(self, parent: tk.Misc, diagram: HciSequenceDiagram) -> None:
        self._diagram = diagram
        self._window = tk.Toplevel(parent)
        self._window.title(f"HCI Markdown Preview - {diagram.source_path.name}")
        self._window.geometry("1100x760")
        self._window.minsize(800, 560)
        self._window.columnconfigure(0, weight=1)
        self._window.rowconfigure(0, weight=1)

        self._status = tk.StringVar(
            value=f"{len(diagram.messages)} HCI messages"
        )
        self._canvas: tk.Canvas

        self._build_preview()
        self._build_export_controls()

    def _build_preview(self) -> None:
        preview = ttk.Frame(self._window)
        preview.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            preview,
            background="white",
            highlightthickness=1,
            highlightbackground="#C8C8C8",
        )
        vertical = ttk.Scrollbar(
            preview,
            orient="vertical",
            command=self._canvas.yview,
        )
        horizontal = ttk.Scrollbar(
            preview,
            orient="horizontal",
            command=self._canvas.xview,
        )
        self._canvas.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self._draw_markdown_preview()

    def _draw_markdown_preview(self) -> None:
        width = 1000
        title_height = 78
        diagram_top = title_height + 100
        row_height = 58
        height = diagram_top + max(len(self._diagram.messages), 1) * row_height + 45
        host_x = 220
        controller_x = 780
        self._canvas.configure(scrollregion=(0, 0, width, height))

        self._canvas.create_text(
            30,
            35,
            text=f"HCI Sequence Diagram: {self._diagram.source_path.name}",
            anchor="w",
            font=("Segoe UI", 16, "bold"),
            fill="#111111",
        )
        self._draw_actor(host_x, title_height + 12, "Host")
        self._draw_actor(controller_x, title_height + 12, "Controller")
        self._canvas.create_line(
            host_x,
            title_height + 48,
            host_x,
            height - 45,
            fill="#777777",
            dash=(5, 5),
        )
        self._canvas.create_line(
            controller_x,
            title_height + 48,
            controller_x,
            height - 45,
            fill="#777777",
            dash=(5, 5),
        )

        for index, message in enumerate(self._diagram.messages):
            y = diagram_top + index * row_height
            if message.direction == "host_to_controller":
                start_x, end_x = host_x, controller_x
            else:
                start_x, end_x = controller_x, host_x
            self._canvas.create_line(
                start_x,
                y,
                end_x,
                y,
                fill="#333333",
                width=2,
                arrow=tk.LAST,
            )
            self._canvas.create_text(
                width // 2,
                y - 12,
                text=message.label,
                width=700,
                anchor="s",
                justify=tk.CENTER,
                font=("Consolas", 10),
                fill="#111111",
            )

    def _draw_actor(self, x: int, y: int, label: str) -> None:
        self._canvas.create_rectangle(
            x - 70,
            y,
            x + 70,
            y + 36,
            fill="#E8F0FE",
            outline="#356AC3",
            width=2,
        )
        self._canvas.create_text(
            x,
            y + 18,
            text=label,
            font=("Segoe UI", 11, "bold"),
        )

    def _build_export_controls(self) -> None:
        controls = ttk.Frame(self._window)
        controls.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))
        ttk.Button(
            controls,
            text="MarkdownとPNGを保存",
            command=self._save_outputs,
        ).pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self._status).pack(
            side=tk.LEFT,
            padx=(12, 0),
        )
        ttk.Button(
            controls,
            text="閉じる",
            command=self._window.destroy,
        ).pack(side=tk.RIGHT)

    def _save_outputs(self) -> None:
        try:
            markdown, screenshot = self._diagram.save_preview_outputs()
        except OSError as exc:
            self._show_save_error(exc)
            return
        self._status.set(
            f"保存しました: {markdown.name}, {screenshot.name}"
        )

    def _show_save_error(self, exc: OSError) -> None:
        self._status.set(f"保存エラー: {exc}")
        messagebox.showerror(
            "保存エラー",
            str(exc),
            parent=self._window,
        )
