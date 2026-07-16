"""Tests for UART H4 stream framing."""

import unittest

from hci_analyzer.parser.h4_stream import H4StreamDecoder


class H4StreamDecoderTests(unittest.TestCase):
    def test_split_frame_and_initial_noise(self) -> None:
        decoder = H4StreamDecoder()

        first = decoder.feed(bytes.fromhex("FF AA 01 34 20"))
        second = decoder.feed(bytes.fromhex("04 13 25 00 01"))

        self.assertEqual(first.discarded_noise, [bytes.fromhex("FF AA")])
        self.assertEqual(first.frames, [])
        self.assertEqual(
            second.frames, [bytes.fromhex("01 34 20 04 13 25 00 01")]
        )

    def test_multiple_command_and_event_frames(self) -> None:
        decoder = H4StreamDecoder()
        chunk = decoder.feed(
            bytes.fromhex("01 1F 20 00 04 0E 06 01 1F 20 00 34 12")
        )

        self.assertEqual(len(chunk.frames), 2)
        self.assertEqual(chunk.frames[0], bytes.fromhex("01 1F 20 00"))
        self.assertEqual(
            chunk.frames[1], bytes.fromhex("04 0E 06 01 1F 20 00 34 12")
        )

    def test_resynchronizes_after_false_indicator_in_startup_noise(self) -> None:
        decoder = H4StreamDecoder()
        chunk = decoder.feed(
            bytes.fromhex("01 AA BB FF 01 1F 20 00")
        )

        self.assertEqual(
            chunk.discarded_noise, [bytes.fromhex("01 AA BB FF")]
        )
        self.assertEqual(chunk.frames, [bytes.fromhex("01 1F 20 00")])

    def test_acl_frame_boundary_is_preserved(self) -> None:
        decoder = H4StreamDecoder()
        chunk = decoder.feed(bytes.fromhex("02 01 20 03 00 AA BB CC"))

        self.assertEqual(chunk.frames, [bytes.fromhex("02 01 20 03 00 AA BB CC")])

    def test_maximum_length_event_frame_is_preserved(self) -> None:
        decoder = H4StreamDecoder()
        frame = bytes.fromhex("04 0E FF 01 10 10 00") + bytes(251)

        chunk = decoder.feed(frame)

        self.assertEqual(chunk.frames, [frame])


if __name__ == "__main__":
    unittest.main()
