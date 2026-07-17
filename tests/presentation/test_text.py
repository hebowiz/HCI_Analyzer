"""Tests for ASCII-safe log text and exception formatting."""

import unittest

import serial

from hci_analyzer.presentation.text import (
    ascii_safe_text,
    format_exception_for_log,
)


class LogTextTests(unittest.TestCase):
    def test_pyserial_wrapped_windows_error_is_structured(self) -> None:
        error = serial.SerialException(
            "Cannot configure port. Original message: "
            "OSError(22, 'パラメーターが間違っています。', None, 87)"
        )

        text = format_exception_for_log(error)

        self.assertEqual(text, "SerialException; errno=22; winerror=87")
        self.assertTrue(text.isascii())

    def test_ascii_exception_message_is_retained_without_os_codes(self) -> None:
        self.assertEqual(
            format_exception_for_log(ValueError("invalid value")),
            "ValueError; invalid value",
        )

    def test_non_ascii_fallback_uses_readable_marker(self) -> None:
        text = ascii_safe_text("Error: パラメーターが不正です")

        self.assertEqual(text, "Error: [localized message omitted]")
        self.assertTrue(text.isascii())


if __name__ == "__main__":
    unittest.main()
