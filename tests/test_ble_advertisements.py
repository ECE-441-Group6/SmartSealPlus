import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from Gateway import ble_scanner
from Gateway.XIAO import ble_scanner as xiao_ble_scanner
from Gateway.ble_scanner import parse_advertisement


def sensor_packet(seal_id=1, sequence=1, temperature=5.2, tamper=False, vibration=0):
    return (
        bytes([0xA5, 1, seal_id])
        + sequence.to_bytes(4, "little")
        + round(temperature * 10).to_bytes(2, "little", signed=True)
        + bytes([int(tamper)])
        + int(round(vibration * 100)).to_bytes(2, "little")
    )


class TestBleAdvertisements(unittest.TestCase):
    def test_decodes_pre_security_sensor_packet(self):
        packet = parse_advertisement(
            sensor_packet(sequence=42, temperature=5.2, vibration=1.0)
        )
        self.assertEqual(
            packet,
            {
                "seal_id": 1,
                "event_sequence": 42,
                "temperature": 5.2,
                "tamper": False,
                "vibration": 1.0,
            },
        )

    def test_decodes_raw_manufacturer_field(self):
        packet = parse_advertisement(b"\x53\x53" + sensor_packet(sequence=9))
        self.assertEqual(packet["event_sequence"], 9)

    def test_rejects_bad_marker_version_and_length(self):
        packet = sensor_packet()
        self.assertIsNone(parse_advertisement(bytes([0xA4]) + packet[1:]))
        self.assertIsNone(parse_advertisement(packet[:1] + bytes([2]) + packet[2:]))
        self.assertIsNone(parse_advertisement(packet[:-1]))
        self.assertIsNone(parse_advertisement(packet + b"\x00"))

    def test_gateway_scanners_receive_xiao_manufacturer_advertisement(self):
        payload = sensor_packet(sequence=7, vibration=1.0)
        device = SimpleNamespace(name="Xiao_Recorder")
        advertisement = SimpleNamespace(
            local_name=None,
            service_uuids=[],
            service_data={},
            manufacturer_data={0x5353: payload},
        )

        class FakeScanner:
            def __init__(self, detection_callback):
                self.detection_callback = detection_callback

            async def start(self):
                self.detection_callback(device, advertisement)

            async def stop(self):
                pass

        with (
            patch.object(ble_scanner, "BleakScanner", FakeScanner),
            patch.object(ble_scanner, "SCAN_TIMEOUT", 0.001),
            patch.object(xiao_ble_scanner, "BleakScanner", FakeScanner),
            patch.object(xiao_ble_scanner, "SCAN_TIMEOUT", 0.1),
        ):
            gateway_packet = asyncio.run(ble_scanner.scan_real_ble())
            xiao_packet = asyncio.run(xiao_ble_scanner.scan_real_ble())

        self.assertEqual(gateway_packet["event_sequence"], 7)
        self.assertEqual(xiao_packet["event_sequence"], 7)

    def test_xiao_scanner_accepts_payloads_from_raw_manufacturer_fields(self):
        device = SimpleNamespace(name="Xiao_Recorder")
        advertisement = SimpleNamespace(
            local_name="Xiao_Recorder",
            service_data={},
            manufacturer_data={0x1234: sensor_packet()},
        )

        class FakeScanner:
            def __init__(self, detection_callback):
                self.detection_callback = detection_callback

            async def start(self):
                self.detection_callback(device, advertisement)

            async def stop(self):
                pass

        with (
            patch.object(xiao_ble_scanner, "BleakScanner", FakeScanner),
            patch.object(xiao_ble_scanner, "SCAN_TIMEOUT", 0.001),
        ):
            packet = asyncio.run(xiao_ble_scanner.scan_real_ble())

        self.assertEqual(packet["seal_id"], 1)


if __name__ == "__main__":
    unittest.main()
