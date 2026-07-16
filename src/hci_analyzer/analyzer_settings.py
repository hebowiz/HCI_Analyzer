"""Persistent user settings for the HCI Analyzer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hci_analyzer.config import (
    ANALYZER_DEFAULT_WINDOW_SIZE,
    ANALYZER_MINIMUM_WINDOW_SIZE,
    DEFAULT_BAUD_RATE,
    SUPPORTED_BAUD_RATES,
)


DEFAULT_SETTINGS_PATH = Path.home() / ".hci_analyzer" / "analyzer.json"


@dataclass(slots=True, frozen=True)
class AnalyzerSettings:
    """Last HCI Analyzer serial and window settings."""

    port_one: str = ""
    port_two: str = ""
    baud_rate: int = DEFAULT_BAUD_RATE
    window_width: int = ANALYZER_DEFAULT_WINDOW_SIZE[0]
    window_height: int = ANALYZER_DEFAULT_WINDOW_SIZE[1]


class AnalyzerSettingsStore:
    """Load and save HCI Analyzer settings as JSON."""

    def __init__(self, file_path: Path = DEFAULT_SETTINGS_PATH) -> None:
        self._file_path = file_path

    def load(self) -> AnalyzerSettings:
        """Load settings, falling back to defaults for invalid data."""
        try:
            payload: Any = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return AnalyzerSettings()
        if not isinstance(payload, dict):
            return AnalyzerSettings()

        port_one = payload.get("port_one", "")
        port_two = payload.get("port_two", "")
        baud_rate = payload.get("baud_rate", DEFAULT_BAUD_RATE)
        if not isinstance(port_one, str):
            port_one = ""
        if not isinstance(port_two, str):
            port_two = ""
        if not isinstance(baud_rate, int) or baud_rate not in SUPPORTED_BAUD_RATES:
            baud_rate = DEFAULT_BAUD_RATE
        width, height = _valid_window_size(
            payload.get("window_width"),
            payload.get("window_height"),
            ANALYZER_DEFAULT_WINDOW_SIZE,
            ANALYZER_MINIMUM_WINDOW_SIZE,
        )
        return AnalyzerSettings(
            port_one=port_one,
            port_two=port_two,
            baud_rate=baud_rate,
            window_width=width,
            window_height=height,
        )

    def save(self, settings: AnalyzerSettings) -> None:
        """Persist Analyzer settings."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "port_one": settings.port_one,
            "port_two": settings.port_two,
            "baud_rate": settings.baud_rate,
            "window_width": settings.window_width,
            "window_height": settings.window_height,
        }
        self._file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _valid_window_size(
    width: object,
    height: object,
    default: tuple[int, int],
    minimum: tuple[int, int],
) -> tuple[int, int]:
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or width < minimum[0]
        or height < minimum[1]
    ):
        return default
    return width, height
