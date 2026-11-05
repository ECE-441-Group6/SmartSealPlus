"""Load and validate SmartSeal per-device encryption keys."""

import base64
import json
import os
from pathlib import Path

KEY_LENGTH = 16
REGISTRY_ENVIRONMENT_VARIABLE = "SMARTSEAL_KEY_REGISTRY"


class KeyRegistryError(RuntimeError):
    """Raised when the gateway key registry is missing or invalid."""


def load_key_registry(path=None):
    registry_path = path or os.getenv(REGISTRY_ENVIRONMENT_VARIABLE)
    if not registry_path:
        raise KeyRegistryError(
            f"{REGISTRY_ENVIRONMENT_VARIABLE} is not configured"
        )

    try:
        with Path(registry_path).open(encoding="utf-8") as registry_file:
            document = json.load(registry_file)
    except (OSError, json.JSONDecodeError) as error:
        raise KeyRegistryError("Could not load SmartSeal key registry") from error

    entries = document.get("seals") if isinstance(document, dict) else None
    if not isinstance(entries, dict) or not entries:
        raise KeyRegistryError("SmartSeal key registry must contain seals")

    keys_by_seal = {}
    for raw_seal_id, entry in entries.items():
        try:
            seal_id = int(raw_seal_id)
        except (TypeError, ValueError) as error:
            raise KeyRegistryError("SmartSeal seal IDs must be integers") from error
        if seal_id < 1 or str(seal_id) != str(raw_seal_id):
            raise KeyRegistryError("SmartSeal seal IDs must be positive integers")
        if not isinstance(entry, dict) or not isinstance(entry.get("key"), str):
            raise KeyRegistryError(f"Missing key for seal {seal_id}")
        try:
            key = base64.b64decode(entry["key"], validate=True)
        except (ValueError, TypeError) as error:
            raise KeyRegistryError(f"Invalid key encoding for seal {seal_id}") from error
        if len(key) != KEY_LENGTH:
            raise KeyRegistryError(f"Invalid key length for seal {seal_id}")
        keys_by_seal[seal_id] = key

    return keys_by_seal
