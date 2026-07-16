"""Tests for bidirectional serial command transport."""

import threading
import time
import unittest
from unittest.mock import patch

from hci_analyzer.models import SerialPortConfig
from hci_analyzer.serial.transport import HciSerialTransport, TransportEventKind


class _FakeSerial:
    def __init__(self, *args, response: bytes = b"", **kwargs) -> None:
        self.is_open = True
        self._response_template = response
        self._receive_buffer = bytearray()
        self.written = bytearray()
        self._lock = threading.Lock()

    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self._receive_buffer)

    def write(self, data: bytes) -> int:
        with self._lock:
            self.written.extend(data)
            self._receive_buffer.extend(self._response_template)
        return len(data)

    def read(self, size: int) -> bytes:
        time.sleep(0.001)
        with self._lock:
            data = bytes(self._receive_buffer[:size])
            del self._receive_buffer[:size]
            return data

    def flush(self) -> None:
        return None

    def cancel_read(self) -> None:
        return None

    def close(self) -> None:
        self.is_open = False


class HciSerialTransportTests(unittest.TestCase):
    def test_command_complete_is_linked_to_transaction(self) -> None:
        events = []
        fake = _FakeSerial(response=bytes.fromhex("04 0E 04 01 34 20 00"))
        with patch("hci_analyzer.serial.transport.serial.Serial", return_value=fake):
            transport = HciSerialTransport(events.append)
            transport.connect(SerialPortConfig("COM1", 115200, "Console:COM1"))
            transaction_id = transport.send(
                bytes.fromhex("01 34 20 04 13 25 00 01"),
                expected_opcode=0x2034,
            )
            self._wait_for(
                lambda: any(
                    event.kind == TransportEventKind.RECEIVED for event in events
                )
            )
            received = next(
                event
                for event in events
                if event.kind == TransportEventKind.RECEIVED
            )
            self.assertEqual(received.transaction_id, transaction_id)
            self.assertFalse(transport._get_pending())
            transport.disconnect()

    def test_second_send_is_rejected_while_pending(self) -> None:
        events = []
        fake = _FakeSerial()
        with patch("hci_analyzer.serial.transport.serial.Serial", return_value=fake):
            transport = HciSerialTransport(events.append)
            transport.connect(SerialPortConfig("COM1", 115200, "Console:COM1"))
            frame = bytes.fromhex("01 1F 20 00")
            transport.send(frame, expected_opcode=0x201F, response_timeout_seconds=1)
            with self.assertRaises(RuntimeError):
                transport.send(frame, expected_opcode=0x201F)
            transport.disconnect()

    def test_response_timeout_clears_pending_transaction(self) -> None:
        events = []
        fake = _FakeSerial()
        with patch("hci_analyzer.serial.transport.serial.Serial", return_value=fake):
            transport = HciSerialTransport(events.append)
            transport.connect(SerialPortConfig("COM1", 115200, "Console:COM1"))
            transaction_id = transport.send(
                bytes.fromhex("01 1F 20 00"),
                expected_opcode=0x201F,
                response_timeout_seconds=0.02,
            )
            self._wait_for(
                lambda: any(
                    event.kind == TransportEventKind.RESPONSE_TIMEOUT
                    for event in events
                )
            )
            timeout_event = next(
                event
                for event in events
                if event.kind == TransportEventKind.RESPONSE_TIMEOUT
            )
            self.assertEqual(timeout_event.transaction_id, transaction_id)
            self.assertIsNone(transport._get_pending())
            transport.disconnect()

    @staticmethod
    def _wait_for(predicate, timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        raise AssertionError("Timed out waiting for transport event")


if __name__ == "__main__":
    unittest.main()
