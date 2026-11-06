import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESCCM

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

    def test_plaintext_rejected_by_default(self):
        forged = "S:1,E:999,T:5.0,A:1,V:0"
        self.assertIsNone(parse_advertisement(forged))
        self.assertIsNone(
            parse_advertisement(forged, keys_by_seal={1: self.key})
        )

    def test_legacy_binary_rejected_by_default(self):
        forged = bytes([
            0xA5, 1, 1, 7, 0, 0, 0, 0x32, 0, 1, 0, 0
        ])
        self.assertIsNone(parse_advertisement(forged))
        self.assertIsNone(
            parse_advertisement(forged, keys_by_seal={1: self.key})
        )

    def test_missing_gateway_registry_fails_closed(self):
        os.environ.pop("SMARTSEAL_KEY_REGISTRY", None)
        self.assertIsNone(parse_advertisement(encrypted_packet(1, self.key)))
