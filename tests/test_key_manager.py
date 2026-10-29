"""Automated tests for SmartSeal+ secure key management."""

import os
import unittest
from unittest.mock import patch

from Gateway.key_manager import generate_secret_key, get_device_key


class TestKeyManager(unittest.TestCase):

    def setUp(self):
        self.test_key = "a1" * 32

    def test_generate_key_length(self):
        key = generate_secret_key()
        self.assertEqual(len(key), 64)

    def test_generate_key_is_hexadecimal(self):
        key = generate_secret_key()
        self.assertEqual(len(bytes.fromhex(key)), 32)

    def test_generated_keys_are_different(self):
        key1 = generate_secret_key()
        key2 = generate_secret_key()
        self.assertNotEqual(key1, key2)

    def test_load_valid_device_key(self):
        with patch.dict(os.environ, {"SMARTSEAL_KEY_1": self.test_key}):
            key = get_device_key(1)
            self.assertEqual(key, bytes.fromhex(self.test_key))

    def test_different_devices_have_different_keys(self):
        with patch.dict(os.environ, {
            "SMARTSEAL_KEY_1": "a1" * 32,
            "SMARTSEAL_KEY_2": "b2" * 32,
        }):
            self.assertNotEqual(get_device_key(1), get_device_key(2))

    def test_missing_key_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                get_device_key(1)

    def test_short_key_rejected(self):
        with patch.dict(os.environ, {"SMARTSEAL_KEY_1": "abcd"}):
            with self.assertRaises(ValueError):
                get_device_key(1)

    def test_non_hex_key_rejected(self):
        with patch.dict(os.environ, {"SMARTSEAL_KEY_1": "z" * 64}):
            with self.assertRaises(ValueError):
                get_device_key(1)

    def test_invalid_seal_id_rejected(self):
        for seal_id in (0, -1, "1", True):
            with self.subTest(seal_id=seal_id):
                with self.assertRaises(ValueError):
                    get_device_key(seal_id)

    def test_uppercase_hex_key_accepted(self):
        key_hex = "AB" * 32

        with patch.dict(os.environ, {"SMARTSEAL_KEY_3": key_hex}):
            self.assertEqual(
                get_device_key(3),
                bytes.fromhex(key_hex),
            )


if __name__ == "__main__":
    unittest.main()