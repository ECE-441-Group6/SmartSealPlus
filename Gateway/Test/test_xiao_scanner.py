import asyncio
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from Gateway.XIAO import ble_scanner


class HangingScanner:
    def __init__(self, detection_callback):
        self.detection_callback = detection_callback

    async def start(self):
        await asyncio.Event().wait()


class XiaoScannerTests(unittest.TestCase):
    def test_scanner_start_timeout_reports_error_and_returns(self):
        output = io.StringIO()
        with (
            patch.object(ble_scanner, "BleakScanner", HangingScanner),
            patch.object(ble_scanner, "SCAN_START_TIMEOUT", 0.01),
            redirect_stdout(output),
        ):
            result = asyncio.run(ble_scanner.scan_real_ble())

        self.assertIsNone(result)
        self.assertIn("BLE scanner did not start", output.getvalue())


if __name__ == "__main__":
    unittest.main()
