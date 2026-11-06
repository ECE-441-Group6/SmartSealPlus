"""Generate a per-seal key for the gateway and XIAO firmware."""

import argparse
import base64
import json
import os
import secrets
import tempfile
from pathlib import Path

try:
    from .key_registry import KeyRegistryError, load_key_registry
except ImportError:
    from key_registry import KeyRegistryError, load_key_registry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            os.chmod(temporary_path, 0o600)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _render_firmware_header(seal_id, key):
    key_bytes = ", ".join(f"0x{byte:02X}" for byte in key)
    return (
        "#pragma once\n\n"
        "#include <stdint.h>\n\n"
        f"constexpr uint8_t SMARTSEAL_SEAL_ID = {seal_id};\n"
        "constexpr uint8_t SMARTSEAL_ENCRYPTION_KEY[16] = {\n"
        f"  {key_bytes}\n"
        "};\n"
    )


def provision_key(seal_id, registry_path, firmware_header):
    if not 1 <= seal_id <= 255:
        raise KeyRegistryError("seal ID must be between 1 and 255")

    if registry_path.exists():
        registry = load_key_registry(registry_path)
    else:
        registry = {}
    key = secrets.token_bytes(16)
    registry[seal_id] = key

    registry_json = {
        str(key_seal_id): base64.b64encode(value).decode("ascii")
        for key_seal_id, value in sorted(registry.items())
    }
    _atomic_write(
        registry_path,
        json.dumps(registry_json, indent=2) + "\n",
    )
    _atomic_write(
        firmware_header,
        _render_firmware_header(seal_id, key),
    )
    return key


def main():
    parser = argparse.ArgumentParser(
        description="Generate a fresh AES-128 key for one XIAO seal"
    )
    parser.add_argument("seal_id", type=int)
    parser.add_argument(
        "--registry",
        type=Path,
        default=PROJECT_ROOT / "Gateway" / "keys.json",
    )
    parser.add_argument(
        "--firmware-header",
        type=Path,
        default=PROJECT_ROOT
        / "XIAOnRF8540"
        / "Advertising"
        / "secrets.h",
    )
    args = parser.parse_args()

    try:
        provision_key(args.seal_id, args.registry, args.firmware_header)
    except (KeyRegistryError, OSError) as error:
        parser.error(str(error))
    print(f"Provisioned seal {args.seal_id}. Keep both generated files private.")
    print(f"Gateway registry: {args.registry}")
    print(f"Firmware header: {args.firmware_header}")


if __name__ == "__main__":
    main()
