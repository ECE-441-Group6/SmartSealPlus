"""ESP32-specific SmartSeal+ gateway entry point."""

from Gateway.gateway_main import run_gateway
from Gateway.ESP32.ble_scanner import scan_ble


if __name__ == "__main__":
    run_gateway(scanner=scan_ble)
