import base64
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESCCM

from Gateway import ble_scanner
from Gateway.XIAO import ble_scanner as xiao_ble_scanner
from Gateway.ble_scanner import parse_advertisement


def encrypted_packet(seal_id, key, sequence=1):
    plaintext = bytes([seal_id]) + sequence.to_bytes(4, "little")
    plaintext += (52).to_bytes(2, "little", signed=True)
    plaintext += bytes([0, 100, 0])
    nonce = b"nonce01"
    return bytes([2]) + nonce + AESCCM(key, tag_length=6).encrypt(
        nonce, plaintext, b"\x02"
    )


class TestEncryptedPackets(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.registry_path = Path(self.directory.name) / "keys.json"
        self.key = b"correct-key-1234"
        self.other_key = b"incorrect-key123"
        self.registry_path.write_text(json.dumps({
            "seals": {"1": {
                "key": base64.b64encode(self.key).decode("ascii")
            }}
        }), encoding="utf-8")
        self.old_registry = os.environ.get("SMARTSEAL_KEY_REGISTRY")
        os.environ["SMARTSEAL_KEY_REGISTRY"] = str(self.registry_path)

    def tearDown(self):
        if self.old_registry is None:
            os.environ.pop("SMARTSEAL_KEY_REGISTRY", None)
        else:
            os.environ["SMARTSEAL_KEY_REGISTRY"] = self.old_registry

    def test_registered_key_is_accepted(self):
        self.assertEqual(parse_advertisement(encrypted_packet(1, self.key))["seal_id"], 1)

    def test_incorrect_key_is_rejected(self):
        self.assertIsNone(parse_advertisement(encrypted_packet(1, self.other_key)))

    def test_unknown_seal_is_rejected(self):
        self.assertIsNone(parse_advertisement(encrypted_packet(2, self.key)))

    def test_changing_seal_id_is_rejected(self):
        packet = encrypted_packet(1, self.key)
        forged = encrypted_packet(2, self.key)
        self.assertIsNone(parse_advertisement(forged))
        self.assertIsNotNone(parse_advertisement(packet))

    def test_missing_gateway_registry_fails_closed(self):
        os.environ.pop("SMARTSEAL_KEY_REGISTRY", None)
        self.assertIsNone(parse_advertisement(encrypted_packet(1, self.key)))

    def test_gateway_scanners_receive_xiao_manufacturer_advertisement(self):
        device = SimpleNamespace(name="Xiao_Recorder")
        advertisement = SimpleNamespace(
            local_name=None,
            service_uuids=[],
            manufacturer_data={
                0x5353: encrypted_packet(1, self.key)
            },
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

        self.assertEqual(gateway_packet["seal_id"], 1)
        self.assertEqual(xiao_packet["seal_id"], 1)

    def test_xiao_scanner_ignores_other_manufacturer_ids(self):
        device = SimpleNamespace(name="Xiao_Recorder")
        advertisement = SimpleNamespace(
            local_name="Xiao_Recorder",
            manufacturer_data={
                0x1234: encrypted_packet(1, self.key)
            },
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
