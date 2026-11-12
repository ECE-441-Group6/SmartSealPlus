import base64
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESCCM

from Gateway import database
from Gateway import ble_scanner
from Gateway import gateway_main
from Gateway.provision_test_seal import provision_seal


class MultiSealTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_name = database.DB_NAME
        database.DB_NAME = Path(self.temp_dir.name) / "smartseal.db"
        database.init_database()

    def tearDown(self):
        database.DB_NAME = self.old_db_name
        self.temp_dir.cleanup()

    def encrypted_packet(self, seal_id, sequence, key):
        sequence_bytes = sequence.to_bytes(4, "little")
        header = bytes((0xA5, 3, seal_id)) + sequence_bytes
        temperature = int(21.5 * 10).to_bytes(2, "little", signed=True)
        plaintext = temperature + bytes((0, 0, 0, 0))
        nonce = ble_scanner.NONCE_PREFIX + sequence_bytes
        encrypted = AESCCM(key, tag_length=8).encrypt(
            nonce, plaintext, header
        )
        return header + encrypted

    def test_gateway_parses_and_stores_packets_from_two_seals(self):
        first_key = bytes.fromhex("11" * 16)
        second_key = bytes.fromhex("22" * 16)
        with patch.object(
            ble_scanner,
            "AES_BY_SEAL",
            {
                1: AESCCM(first_key, tag_length=8),
                2: AESCCM(second_key, tag_length=8),
            },
        ):
            scan_results = [
                ble_scanner.parse_advertisement(
                    self.encrypted_packet(1, 7, first_key)
                ),
                ble_scanner.parse_advertisement(
                    self.encrypted_packet(2, 7, second_key)
                ),
            ]
            calls = 0

            def scanner():
                nonlocal calls
                calls += 1
                if calls == 1:
                    return scan_results
                raise KeyboardInterrupt

            with redirect_stdout(io.StringIO()):
                gateway_main.run_gateway(interval=0, scanner=scanner)

        events = database.get_latest_events()
        self.assertEqual({event[2] for event in events}, {1, 2})


class TestSealProvisioningTests(unittest.TestCase):
    def test_provisioned_key_is_registered_without_changing_primary_key(self):
        primary_key = bytes.fromhex("11" * 16)
        registry = {
            "SMARTSEAL_AES_KEY": primary_key.hex(),
            "SMARTSEAL_NONCE_PREFIX": "00" * 9,
            "1": base64.b64encode(bytes.fromhex("33" * 16)).decode("ascii"),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            registry_path = Path(temporary_directory) / "keys.json"
            firmware_header = Path(temporary_directory) / "secrets.h"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")

            provision_seal(2, registry_path, firmware_header)

            updated_registry = json.loads(
                registry_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                base64.b64decode(updated_registry["1"]), primary_key
            )
            self.assertEqual(
                len(base64.b64decode(updated_registry["2"])), 16
            )
            self.assertIn("SEAL_ID = 2", firmware_header.read_text())

            with patch.dict(
                os.environ,
                {"SMARTSEAL_KEY_REGISTRY": str(registry_path)},
            ):
                _, ciphers = ble_scanner._load_key_configuration()
            self.assertEqual(set(ciphers), {1, 2})


if __name__ == "__main__":
    unittest.main()
