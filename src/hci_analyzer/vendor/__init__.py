"""Vendor-specific HCI command discovery support."""

from hci_analyzer.vendor.discovery import (
    FieldCandidate,
    VendorAnalysis,
    VendorCapture,
    analyze_captures,
    build_definition_draft,
    load_vendor_captures,
    parse_annotations,
)
from hci_analyzer.vendor.console_definitions import (
    LoadedVendorDefinitions,
    decode_vendor_parameters,
    encode_vendor_parameters,
    load_vendor_console_definitions,
)

__all__ = [
    "FieldCandidate",
    "VendorAnalysis",
    "VendorCapture",
    "analyze_captures",
    "build_definition_draft",
    "load_vendor_captures",
    "parse_annotations",
    "LoadedVendorDefinitions",
    "decode_vendor_parameters",
    "encode_vendor_parameters",
    "load_vendor_console_definitions",
]
