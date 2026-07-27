"""Logic tests for Vendor Discovery GUI state preservation."""

import unittest
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

from hci_analyzer.gui.vendor_discovery import (
    VendorDiscoveryWindow,
    _activate_modal_dialog,
    _centered_position,
    _matches_opcode_filter,
)
from hci_analyzer.vendor.discovery import VendorCapture
from hci_analyzer.vendor.live_capture import DiscoveryCapture
from hci_analyzer.vendor.project import (
    UserParameter,
    VendorDiscoveryProject,
)


class VendorDiscoveryWindowTests(unittest.TestCase):
    def test_opcode_filter_keeps_command_and_related_event_only(self) -> None:
        vendor = VendorCapture(
            capture_id="vendor:1",
            source_path=Path("<live>"),
            line_number=1,
            timestamp="2026-07-27T12:00:00",
            source="Port1",
            opcode=0xFC41,
            parameters=b"",
            raw_data=bytes.fromhex("01 41 FC 00"),
        )
        command = DiscoveryCapture(
            capture_id="vendor:1",
            timestamp=vendor.timestamp,
            source=vendor.source,
            protocol="HCI Vendor",
            raw_data=vendor.raw_data,
            vendor_capture=vendor,
        )
        related_event = DiscoveryCapture(
            capture_id="event:2",
            timestamp=vendor.timestamp,
            source=vendor.source,
            protocol="HCI Event",
            raw_data=bytes.fromhex("04 0E 04 01 41 FC 00"),
            related_opcode=0xFC41,
        )
        unrelated_event = DiscoveryCapture(
            capture_id="event:3",
            timestamp=vendor.timestamp,
            source=vendor.source,
            protocol="HCI Event",
            raw_data=bytes.fromhex("04 FF 00"),
        )

        self.assertTrue(_matches_opcode_filter(command, 0xFC41))
        self.assertTrue(_matches_opcode_filter(related_event, 0xFC41))
        self.assertFalse(_matches_opcode_filter(unrelated_event, 0xFC41))
        self.assertFalse(_matches_opcode_filter(command, 0xFC42))

    def test_parameter_selection_is_restored_after_tree_refresh(self) -> None:
        window = object.__new__(VendorDiscoveryWindow)
        parameter = UserParameter(
            name="phy",
            display_name="PHY",
            kind="enum",
            choices=["LE_1M", "LE_2M"],
        )
        window._active_opcode = 0xFC41
        window._projects = {
            0xFC41: VendorDiscoveryProject(
                opcode=0xFC41,
                parameters=[parameter],
            )
        }
        window._parameter_rows = {"parameter:1": "phy"}
        window._parameter_tree = Mock()
        window._parameter_tree.selection.return_value = ("parameter:1",)
        window._parameter_tree.get_children.return_value = ("parameter:1",)

        window._refresh_parameter_tree()

        window._parameter_tree.selection_set.assert_called_once_with(
            "parameter:1"
        )
        inserted_values = window._parameter_tree.insert.call_args.kwargs[
            "values"
        ]
        self.assertEqual(inserted_values[2], "選択値（Enum）")
        self.assertEqual(inserted_values[3], "未解析")

    def test_known_value_assignment_preserves_selected_captures(self) -> None:
        window = object.__new__(VendorDiscoveryWindow)
        parameter = UserParameter(
            name="channel",
            display_name="Channel",
            kind="unsigned",
        )
        first = self._vendor_entry("vendor:1")
        second = self._vendor_entry("vendor:2")
        window._active_opcode = 0xFC41
        window._selected_parameter = Mock(return_value=parameter)
        window._selected_capture_entries = Mock(
            return_value=[first, second]
        )
        window._known_value_variable = Mock()
        window._known_value_variable.get.return_value = "19"
        window._refresh_capture_tree_selection = Mock()
        window._refresh_parameter_tree = Mock()
        window._status_variable = Mock()

        window._assign_known_value()

        self.assertEqual(first.vendor_capture.annotations["channel"], "19")
        self.assertEqual(second.vendor_capture.annotations["channel"], "19")
        window._refresh_capture_tree_selection.assert_called_once_with(
            select_capture_ids=("vendor:1", "vendor:2")
        )

    @staticmethod
    def _vendor_entry(capture_id: str) -> DiscoveryCapture:
        vendor = VendorCapture(
            capture_id=capture_id,
            source_path=Path("<live>"),
            line_number=1,
            timestamp="2026-07-27T12:00:00",
            source="Port1",
            opcode=0xFC41,
            parameters=b"\x13",
            raw_data=bytes.fromhex("01 41 FC 01 13"),
        )
        return DiscoveryCapture(
            capture_id=capture_id,
            timestamp=vendor.timestamp,
            source=vendor.source,
            protocol="HCI Vendor",
            raw_data=vendor.raw_data,
            vendor_capture=vendor,
        )

    def test_analysis_result_text_is_forced_to_ascii(self) -> None:
        window = object.__new__(VendorDiscoveryWindow)
        window._report_text = Mock()

        window._set_report("Result: PHY=LE 1M / 日本語")

        inserted = window._report_text.insert.call_args.args[1]
        self.assertTrue(inserted.isascii())
        self.assertIn("[localized message omitted]", inserted)
        window._report_text.configure.assert_called_with(state=tk.DISABLED)

    def test_parameter_dialog_position_is_centered_on_parent(self) -> None:
        position = _centered_position(
            parent_x=100,
            parent_y=80,
            parent_width=1200,
            parent_height=800,
            dialog_width=400,
            dialog_height=300,
            screen_width=1920,
            screen_height=1080,
        )

        self.assertEqual(position, (500, 330))

    def test_centered_dialog_position_is_clamped_to_screen(self) -> None:
        position = _centered_position(
            parent_x=1700,
            parent_y=900,
            parent_width=400,
            parent_height=300,
            dialog_width=500,
            dialog_height=400,
            screen_width=1920,
            screen_height=1080,
        )

        self.assertEqual(position, (1420, 680))

    def test_modal_dialog_is_raised_and_given_input_focus(self) -> None:
        dialog = Mock()
        input_widget = Mock()

        _activate_modal_dialog(dialog, input_widget)

        dialog.wait_visibility.assert_called_once_with()
        dialog.lift.assert_called_once_with()
        dialog.grab_set.assert_called_once_with()
        dialog.focus_force.assert_called_once_with()
        input_widget.focus_set.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
