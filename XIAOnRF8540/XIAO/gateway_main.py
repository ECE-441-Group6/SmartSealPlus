"""XIAO-specific SmartSeal+ gateway entry point."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from Gateway.gateway_main import run_gateway
from Gateway.XIAO.ble_scanner import scan_ble


if __name__ == "__main__":
    run_gateway(scanner=scan_ble)
