"""Load the per-seal AES keys used to authenticate BLE advertisements."""

import json
import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESCCM


def _decode_hex(value, field, seal_id, length):
    if not isinstance(value, str):
        raise RuntimeError(f"Seal {seal_id}: {field} must be a hex string.")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as error:
        raise RuntimeError(f"Seal {seal_id}: {field} must be hexadecimal.") from error
    if len(decoded) != length:
        raise RuntimeError(
            f"Seal {seal_id}: {field} must be exactly {length} bytes "
            f"({length * 2} hexadecimal characters)."
        )
    return decoded


def load_seal_keys(key_path=None):
    """Return ``{seal_id: (AESCCM, nonce_prefix)}`` from Gateway/keys.json.

    The old top-level SMARTSEAL_AES_KEY/SMARTSEAL_NONCE_PREFIX format remains
    supported as seal 1, so existing one-seal deployments keep working.
    """
    # Load secrets from the ignored local file, never from the example template.
    key_path = Path(key_path) if key_path else Path(__file__).with_name("keys.json")
    try:
        if os.name == "posix" and stat.S_IMODE(key_path.stat().st_mode) & 0o077:
            raise RuntimeError(
                f"{key_path} must not be accessible by group or other users; "
                "run chmod 600 on the key file."
            )
        with key_path.open(encoding="utf-8") as key_file:
            configuration = json.load(key_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load seal keys from {key_path}.") from error

    if not isinstance(configuration, dict):
        raise RuntimeError(f"{key_path} must contain a JSON object.")

    if "seals" in configuration:
        seals = configuration["seals"]
        if not isinstance(seals, dict) or not seals:
            raise RuntimeError("The 'seals' setting must be a non-empty object.")
    elif {
        "SMARTSEAL_AES_KEY", "SMARTSEAL_NONCE_PREFIX"
    }.issubset(configuration):
        seals = {"1": configuration}
    else:
        raise RuntimeError(
            "keys.json must contain a 'seals' object keyed by seal ID, "
            "or the legacy key fields for seal 1."
        )

    result = {}
    nonce_domains = set()
    for configured_id, values in seals.items():
        try:
            seal_id = int(configured_id)
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"Invalid seal ID in keys.json: {configured_id!r}.") from error
        if str(seal_id) != str(configured_id) or not 1 <= seal_id <= 255:
            raise RuntimeError(f"Seal ID {configured_id!r} must be between 1 and 255.")
        if not isinstance(values, dict):
            raise RuntimeError(f"Seal {seal_id} configuration must be an object.")

        aes_key = _decode_hex(
            values.get("SMARTSEAL_AES_KEY"), "SMARTSEAL_AES_KEY", seal_id, 16
        )
        nonce_prefix = _decode_hex(
            values.get("SMARTSEAL_NONCE_PREFIX"),
            "SMARTSEAL_NONCE_PREFIX",
            seal_id,
            9,
        )
        # Reject identical key/nonce domains across seal IDs; CCM nonce reuse
        # with one AES key can reveal plaintext and undermine authentication.
        nonce_domain = (aes_key, nonce_prefix)
        if nonce_domain in nonce_domains:
            raise RuntimeError(
                f"Seal {seal_id} reuses another seal's AES key and nonce prefix."
            )
        nonce_domains.add(nonce_domain)
        result[seal_id] = (AESCCM(aes_key, tag_length=8), nonce_prefix)

    return result
