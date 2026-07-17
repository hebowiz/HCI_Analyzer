"""Persistent user settings for the HCI Command Console."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hci_analyzer.config import (
    COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE,
    COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE,
    DEFAULT_BAUD_RATE,
    DEFAULT_RESPONSE_TIMEOUT_SECONDS,
    SUPPORTED_BAUD_RATES,
    SUPPORTED_RESPONSE_TIMEOUT_SECONDS,
)


DEFAULT_SETTINGS_PATH = Path.home() / ".hci_analyzer" / "command_console.json"


@dataclass(slots=True, frozen=True)
class CommandConsoleSettings:
    """Last selected serial connection settings."""

    port: str = ""
    baud_rate: int = DEFAULT_BAUD_RATE
    response_timeout_seconds: int = DEFAULT_RESPONSE_TIMEOUT_SECONDS
    window_width: int = COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE[0]
    window_height: int = COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE[1]


class CommandConsoleSettingsStore:
    """Load and save Command Console settings as JSON."""

    def __init__(self, file_path: Path = DEFAULT_SETTINGS_PATH) -> None:
        self._file_path = file_path

    def load(self) -> CommandConsoleSettings:
        """Load settings, falling back to defaults for invalid data."""
        try:
            payload: Any = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return CommandConsoleSettings()
        if not isinstance(payload, dict):
            return CommandConsoleSettings()

        port = payload.get("port", "")
        baud_rate = payload.get("baud_rate", DEFAULT_BAUD_RATE)
        response_timeout_seconds = payload.get(
            "response_timeout_seconds", DEFAULT_RESPONSE_TIMEOUT_SECONDS
        )
        if not isinstance(port, str):
            port = ""
        if not isinstance(baud_rate, int) or baud_rate not in SUPPORTED_BAUD_RATES:
            baud_rate = DEFAULT_BAUD_RATE
        if (
            not isinstance(response_timeout_seconds, int)
            or isinstance(response_timeout_seconds, bool)
            or response_timeout_seconds not in SUPPORTED_RESPONSE_TIMEOUT_SECONDS
        ):
            response_timeout_seconds = DEFAULT_RESPONSE_TIMEOUT_SECONDS
        width, height = _valid_window_size(
            payload.get("window_width"),
            payload.get("window_height"),
        )
        return CommandConsoleSettings(
            port=port,
            baud_rate=baud_rate,
            response_timeout_seconds=response_timeout_seconds,
            window_width=width,
            window_height=height,
        )

    def save(self, settings: CommandConsoleSettings) -> None:
        """Persist settings atomically enough for this small local file."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "port": settings.port,
            "baud_rate": settings.baud_rate,
            "response_timeout_seconds": settings.response_timeout_seconds,
            "window_width": settings.window_width,
            "window_height": settings.window_height,
        }
        self._file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _valid_window_size(width: object, height: object) -> tuple[int, int]:
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or width < COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE[0]
        or height < COMMAND_CONSOLE_MINIMUM_WINDOW_SIZE[1]
    ):
        return COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE
    return width, height
