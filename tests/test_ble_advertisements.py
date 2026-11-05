import asyncio
import base64
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESCCM

from Gateway import ble_scanner
from Gateway import provision_seal_key
from Gateway.XIAO import ble_scanner as xiao_ble_scanner
from Gateway.key_registry import KeyRegistryError, load_key_registry


KEY = bytes(range(16))
NONCE = bytes(range(10))
KEYS = {1: KEY}


def encrypted_packet(
    *,
    seal_id=1,
    sequence=1,
    temperature=5.2,
    tamper=False,
    vibration=0,
    key=KEY,
    nonce=NONCE,
):
    plaintext = (
        bytes([seal_id])
        + sequence.to_bytes(4, "little")
        + round(temperature * 10).to_bytes(2, "little", signed=True)
        + bytes([int(tamper)])
        + int(round(vibration * 100)).to_bytes(2, "little")
    )
    return bytes([2]) + nonce + AESCCM(key, tag_length=8).encrypt(
        nonce,
        plaintext,
        b"\x02",
    )


def write_registry(path, registry):
    path.write_text(json.dumps(registry), encoding="utf-8")
    path.chmod(0o600)


class TestBleAdvertisements(unittest.TestCase):
    def test_decodes_authenticated_registered_packet(self):
        packet = ble_scanner.parse_advertisement(
            encrypted_packet(sequence=42, temperature=5.2, vibration=1.0),
            KEYS,
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

    def test_accepts_raw_manufacturer_field_with_company_id(self):
        packet = ble_scanner.parse_advertisement(
            b"\x53\x53" + encrypted_packet(sequence=9),
            KEYS,
        )
        self.assertEqual(packet["event_sequence"], 9)

    def test_rejects_wrong_key_and_unknown_seal(self):
        wrong_key = {1: bytes(reversed(KEY))}
        unknown_seal = {2: KEY}
        self.assertIsNone(
            ble_scanner.parse_advertisement(encrypted_packet(), wrong_key)
        )
        self.assertIsNone(
            ble_scanner.parse_advertisement(encrypted_packet(), unknown_seal)
        )

    def test_rejects_authenticated_seal_id_mismatch(self):
        forged_id = encrypted_packet(seal_id=2, key=KEY)
        self.assertIsNone(ble_scanner.parse_advertisement(forged_id, KEYS))

    def test_rejects_modified_ciphertext_or_authentication_tag(self):
        packet = encrypted_packet()
        for offset in (9, len(packet) - 1):
            tampered_packet = bytearray(packet)
            tampered_packet[offset] ^= 0x01
            self.assertIsNone(
                ble_scanner.parse_advertisement(tampered_packet, KEYS)
            )

    def test_rejects_plaintext_legacy_and_malformed_packets(self):
        legacy = (
            bytes([0xA5, 1, 1])
            + (1).to_bytes(4, "little")
            + (52).to_bytes(2, "little", signed=True)
            + b"\x00\x00\x00"
        )
        for payload in (
            legacy,
            b"S:1,E:1,T:5.2,A:0,V:0",
            b"\x02",
            encrypted_packet()[:-1],
            encrypted_packet() + b"\x00",
            bytes([3]) + encrypted_packet()[1:],
        ):
            self.assertIsNone(ble_scanner.parse_advertisement(payload, KEYS))

    def test_rejects_invalid_authenticated_sensor_fields(self):
        invalid_plaintext = (
            b"\x01" + (1).to_bytes(4, "little")
            + (52).to_bytes(2, "little", signed=True)
            + b"\x02\x00\x00"
        )
        invalid_packet = bytes([2]) + NONCE + AESCCM(
            KEY, tag_length=8
        ).encrypt(NONCE, invalid_plaintext, b"\x02")
        self.assertIsNone(
            ble_scanner.parse_advertisement(invalid_packet, KEYS)
        )

    def test_registry_requires_environment_variable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyRegistryError):
                load_key_registry()
            with self.assertRaises(KeyRegistryError):
                asyncio.run(ble_scanner.scan_real_ble())

    def test_registry_validates_base64_length_and_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keys.json"
            write_registry(path, {"1": base64.b64encode(KEY).decode("ascii")})
            self.assertEqual(load_key_registry(path), KEYS)

            path.write_text('{"1":"not base64!"}', encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaises(KeyRegistryError):
                load_key_registry(path)

            path.write_text('{"1":"AQ=="}', encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaises(KeyRegistryError):
                load_key_registry(path)

            path.write_text("{invalid json", encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaises(KeyRegistryError):
                load_key_registry(path)

            write_registry(path, {"1": base64.b64encode(KEY).decode("ascii")})
            path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
            if os.name == "posix":
                with self.assertRaises(KeyRegistryError):
                    load_key_registry(path)

    def test_provisioning_updates_both_private_key_files(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "keys.json"
            header = Path(directory) / "secrets.h"
            provisioned_key = provision_seal_key.provision_key(
                7, registry, header
            )
            self.assertEqual(len(provisioned_key), 16)
            self.assertEqual(
                load_key_registry(registry),
                {7: provisioned_key},
            )
            self.assertIn("SMARTSEAL_SEAL_ID = 7", header.read_text())
            self.assertEqual(registry.stat().st_mode & 0o777, 0o600)
            self.assertEqual(header.stat().st_mode & 0o777, 0o600)

    def test_provisioning_requires_explicit_replacement_of_invalid_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "keys.json"
            header = Path(directory) / "secrets.h"
            registry.write_text('{"seals":{"1":{"key":"invalid"}}}')
            registry.chmod(0o600)

            with self.assertRaises(KeyRegistryError):
                provision_seal_key.provision_key(1, registry, header)

            generated_key = provision_seal_key.provision_key(
                1,
                registry,
                header,
                replace_invalid_registry=True,
            )

            self.assertEqual(load_key_registry(registry), {1: generated_key})
            self.assertIn("SMARTSEAL_SEAL_ID = 1", header.read_text())

    def test_ble_scanners_accept_only_company_id_and_authenticated_packets(self):
        payload = encrypted_packet(sequence=7, vibration=1.0)
        device = SimpleNamespace(name="SmartSeal-XIAO")
        valid_advertisement = SimpleNamespace(
            local_name=None,
            service_uuids=[],
            service_data={},
            manufacturer_data={0x5353: payload},
        )
        wrong_company_advertisement = SimpleNamespace(
            local_name="SmartSeal-XIAO",
            service_uuids=[],
            service_data={},
            manufacturer_data={0x1234: payload},
        )

        class FakeScanner:
            advertisement = valid_advertisement

            def __init__(self, detection_callback):
                self.detection_callback = detection_callback

            async def start(self):
                self.detection_callback(device, self.advertisement)

            async def stop(self):
                pass

        with (
            patch.object(ble_scanner, "BleakScanner", FakeScanner),
            patch.object(xiao_ble_scanner, "BleakScanner", FakeScanner),
            patch.object(ble_scanner, "SCAN_TIMEOUT", 0.001),
            patch.object(xiao_ble_scanner, "SCAN_TIMEOUT", 0.001),
            patch.object(ble_scanner, "load_key_registry", return_value=KEYS),
            patch.object(xiao_ble_scanner, "load_key_registry", return_value=KEYS),
        ):
            gateway_packet = asyncio.run(ble_scanner.scan_real_ble())
            xiao_packet = asyncio.run(xiao_ble_scanner.scan_real_ble())
            FakeScanner.advertisement = wrong_company_advertisement
            rejected_gateway_packet = asyncio.run(ble_scanner.scan_real_ble())
            rejected_xiao_packet = asyncio.run(xiao_ble_scanner.scan_real_ble())

        self.assertEqual(gateway_packet["event_sequence"], 7)
        self.assertEqual(xiao_packet["event_sequence"], 7)
        self.assertIsNone(rejected_gateway_packet)
        self.assertIsNone(rejected_xiao_packet)


if __name__ == "__main__":
    unittest.main()
