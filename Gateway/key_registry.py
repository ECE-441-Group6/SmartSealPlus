"""Load and validate per-seal AES-CCM keys for BLE advertisements."""

import base64
import json
import os
import stat
from pathlib import Path


class KeyRegistryError(ValueError):
    """Raised when the gateway key registry is missing or invalid."""


def load_key_registry(registry_path=None):
    """Load {seal_id: 16-byte key} from the configured JSON registry."""
    if registry_path is None:
        configured_path = os.environ.get("SMARTSEAL_KEY_REGISTRY")
        if not configured_path:
            raise KeyRegistryError(
                "SMARTSEAL_KEY_REGISTRY must point to a key registry JSON file"
            )
        registry_path = configured_path

    path = Path(registry_path).expanduser()
    try:
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise KeyRegistryError("key registry must be a regular file")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise KeyRegistryError(
                f"key registry permissions are too broad: {path} "
                "(run chmod 600 on the file)"
            )
        content = path.read_text(encoding="utf-8")
    except KeyRegistryError:
        raise
    except OSError as error:
        raise KeyRegistryError(
            f"cannot read key registry {path}: {error}"
        ) from error

    def reject_duplicate_keys(pairs):
        parsed = {}
        for key, value in pairs:
            if key in parsed:
                raise KeyRegistryError(
                    f"duplicate key registry entry: {key}"
                )
            parsed[key] = value
        return parsed

    try:
        document = json.loads(content, object_pairs_hook=reject_duplicate_keys)
    except KeyRegistryError:
        raise
    except json.JSONDecodeError as error:
        raise KeyRegistryError(
            f"key registry is not valid JSON: {error}"
        ) from error

    if not isinstance(document, dict) or not document:
        raise KeyRegistryError("key registry must be a non-empty JSON object")

    keys = {}
    for seal_id_text, encoded_key in document.items():
        if (
            not isinstance(seal_id_text, str)
            or not seal_id_text.isascii()
            or not seal_id_text.isdecimal()
            or len(seal_id_text) > 3
        ):
            raise KeyRegistryError("registry seal IDs must be decimal strings")
        seal_id = int(seal_id_text)
        if (
            not 1 <= seal_id <= 255
            or str(seal_id) != seal_id_text
            or seal_id in keys
        ):
            raise KeyRegistryError(
                f"invalid or duplicate registry seal ID: {seal_id_text}"
            )
        if not isinstance(encoded_key, str):
            raise KeyRegistryError(
                f"key for seal {seal_id} must be a Base64 string"
            )
        try:
            key = base64.b64decode(encoded_key, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise KeyRegistryError(
                f"key for seal {seal_id} is not valid Base64"
            ) from error
        if len(key) != 16:
            raise KeyRegistryError(
                f"key for seal {seal_id} must decode to exactly 16 bytes"
            )
        keys[seal_id] = key

    return keys
