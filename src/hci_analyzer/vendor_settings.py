"""Persistent settings for real-time Vendor Command Discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hci_analyzer.analyzer_settings import (
    AnalyzerSettingsStore,
    _valid_window_size,
)
from hci_analyzer.config import DEFAULT_BAUD_RATE, SUPPORTED_BAUD_RATES


VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE = (1280, 860)
VENDOR_DISCOVERY_MINIMUM_WINDOW_SIZE = (980, 700)
DEFAULT_SETTINGS_PATH = Path.home() / ".hci_analyzer" / "vendor_discovery.json"


@dataclass(slots=True, frozen=True)
class VendorDiscoverySettings:
    port_one: str = ""
    port_two: str = ""
    baud_rate: int = DEFAULT_BAUD_RATE
    window_width: int = VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE[0]
    window_height: int = VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE[1]
    group_duplicates: bool = False


class VendorDiscoverySettingsStore:
    """Load Discovery settings, seeding serial values from Analyzer."""

    def __init__(
        self,
        file_path: Path = DEFAULT_SETTINGS_PATH,
        analyzer_store: AnalyzerSettingsStore | None = None,
    ) -> None:
        self._file_path = file_path
        self._analyzer_store = analyzer_store or AnalyzerSettingsStore()

    def load(self) -> VendorDiscoverySettings:
        try:
            payload: Any = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            analyzer = self._analyzer_store.load()
            return VendorDiscoverySettings(
                port_one=analyzer.port_one,
                port_two=analyzer.port_two,
                baud_rate=analyzer.baud_rate,
            )
        if not isinstance(payload, dict):
            return VendorDiscoverySettings()
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
            VENDOR_DISCOVERY_DEFAULT_WINDOW_SIZE,
            VENDOR_DISCOVERY_MINIMUM_WINDOW_SIZE,
        )
        return VendorDiscoverySettings(
            port_one=port_one,
            port_two=port_two,
            baud_rate=baud_rate,
            window_width=width,
            window_height=height,
            group_duplicates=payload.get("group_duplicates") is True,
        )

    def save(self, settings: VendorDiscoverySettings) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(
            json.dumps(
                {
                    "port_one": settings.port_one,
                    "port_two": settings.port_two,
                    "baud_rate": settings.baud_rate,
                    "window_width": settings.window_width,
                    "window_height": settings.window_height,
                    "group_duplicates": settings.group_duplicates,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
