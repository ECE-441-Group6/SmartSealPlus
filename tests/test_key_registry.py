import base64
import json
import tempfile
import unittest
from pathlib import Path

from Gateway.key_registry import KeyRegistryError, load_key_registry


class TestKeyRegistry(unittest.TestCase):
    def test_loads_base64_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keys.json"
            path.write_text(json.dumps({
                "seals": {
                    "7": {"key": base64.b64encode(b"7" * 16).decode()}
                }
            }), encoding="utf-8")
            self.assertEqual(load_key_registry(path), {7: b"7" * 16})

    def test_rejects_invalid_key_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keys.json"
            path.write_text(json.dumps({
                "seals": {"1": {"key": base64.b64encode(b"short").decode()}}
            }), encoding="utf-8")
            with self.assertRaises(KeyRegistryError):
                load_key_registry(path)

    def test_missing_path_fails_closed(self):
        with self.assertRaises(KeyRegistryError):
            load_key_registry("")
