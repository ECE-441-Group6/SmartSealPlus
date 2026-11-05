import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from Gateway import ble_scanner
from Gateway.XIAO import ble_scanner as xiao_ble_scanner
from Gateway.ble_scanner import parse_advertisement


def sensor_packet(seal_id=1, sequence=1, temperature=5.2, tamper=False, vibration=0):
    temperature_tenths = (
        0x7FFF if temperature is None else round(temperature * 10)
    )
    return (
        bytes([1, seal_id])
        + sequence.to_bytes(4, "little")
        + temperature_tenths.to_bytes(2, "little", signed=True)
        + bytes([int(tamper)])
        + int(round(vibration * 100)).to_bytes(2, "little")
    )


class TestBleAdvertisements(unittest.TestCase):
    def test_decodes_plaintext_sensor_packet(self):
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

    def test_decodes_missing_temperature(self):
        packet = parse_advertisement(sensor_packet(temperature=None))
        self.assertIsNone(packet["temperature"])

    def test_decodes_raw_manufacturer_field(self):
        packet = parse_advertisement(b"\x53\x53" + sensor_packet(sequence=9))
        self.assertEqual(packet["event_sequence"], 9)

    def test_decodes_without_a_key_registry(self):
        old_registry = os.environ.pop("SMARTSEAL_KEY_REGISTRY", None)
        try:
            packet = parse_advertisement(sensor_packet())
        finally:
            if old_registry is not None:
                os.environ["SMARTSEAL_KEY_REGISTRY"] = old_registry
        self.assertEqual(packet["seal_id"], 1)

    def test_rejects_bad_version_length_and_boolean_fields(self):
        packet = sensor_packet()
        self.assertIsNone(parse_advertisement(bytes([2]) + packet[1:]))
        self.assertIsNone(parse_advertisement(packet[:-1]))
        self.assertIsNone(parse_advertisement(packet + b"\x00"))
        self.assertIsNone(parse_advertisement(packet[:8] + b"\x02" + packet[9:]))

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

    def test_xiao_scanner_ignores_other_manufacturer_ids(self):
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

        self.assertIsNone(packet)


if __name__ == "__main__":
    unittest.main()
