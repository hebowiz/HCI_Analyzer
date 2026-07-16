"""Application-level configuration constants."""

from pathlib import Path


APP_NAME = "HCI LE RF PHY Analyzer"
LOG_DIRECTORY = Path("logs")

SUPPORTED_BAUD_RATES = (
    9_600,
    19_200,
    38_400,
    57_600,
    115_200,
    230_400,
    460_800,
    921_600,
    1_000_000,
    1_500_000,
    2_000_000,
    3_000_000,
)

DEFAULT_BAUD_RATE = 115_200

