"""Persistent user settings for the HCI Command Console."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hci_analyzer.config import DEFAULT_BAUD_RATE, SUPPORTED_BAUD_RATES


DEFAULT_SETTINGS_PATH = Path.home() / ".hci_analyzer" / "command_console.json"


@dataclass(slots=True, frozen=True)
class CommandConsoleSettings:
    """Last selected serial connection settings."""

    port: str = ""
    baud_rate: int = DEFAULT_BAUD_RATE


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
        if not isinstance(port, str):
            port = ""
        if not isinstance(baud_rate, int) or baud_rate not in SUPPORTED_BAUD_RATES:
            baud_rate = DEFAULT_BAUD_RATE
        return CommandConsoleSettings(port=port, baud_rate=baud_rate)

    def save(self, settings: CommandConsoleSettings) -> None:
        """Persist settings atomically enough for this small local file."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "port": settings.port,
            "baud_rate": settings.baud_rate,
        }
        self._file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
