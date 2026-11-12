"""Provision a unique key for the sensorless multi-seal test transmitter."""

import argparse
import base64
import json
import os
import secrets
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = Path(
    os.getenv(
        "SMARTSEAL_KEY_REGISTRY",
        str(REPOSITORY_ROOT / "Gateway" / "keys.json"),
    )
)
DEFAULT_FIRMWARE_HEADER = (
    REPOSITORY_ROOT
    / "XIAOnRF8540"
    / "SmartSeal_Encrypted_Test"
    / "secrets_test.h"
)


def _format_bytes(value):
    rows = []
    for offset in range(0, len(value), 8):
        row = ", ".join(f"0x{byte:02X}" for byte in value[offset:offset + 8])
        rows.append(f"  {row}")
    return ",\n".join(rows)


def _stage_private_file(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
            output_file.write(contents)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def provision_seal(seal_id, registry_path, firmware_header):
    if not 1 <= seal_id <= 255:
        raise ValueError("Seal ID must be between 1 and 255.")

    registry_path = Path(registry_path).expanduser().resolve()
    firmware_header = Path(firmware_header).expanduser().resolve()
    if firmware_header.exists():
        raise FileExistsError(
            f"{firmware_header} already exists; refusing to overwrite it."
        )

    try:
        configuration = json.loads(
            registry_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Could not read key registry {registry_path}."
        ) from error

    if not isinstance(configuration, dict):
        raise ValueError("Key registry must contain a JSON object.")

    if "SMARTSEAL_AES_KEY" not in configuration:
        raise ValueError(
            "The existing gateway key registry must include "
            "SMARTSEAL_AES_KEY."
        )
    if "SMARTSEAL_NONCE_PREFIX" not in configuration:
        raise ValueError(
            "The existing gateway key registry must include "
            "SMARTSEAL_NONCE_PREFIX."
        )
    if str(seal_id) in configuration:
        raise ValueError(
            f"Seal ID {seal_id} already has a key in the registry."
        )

    try:
        primary_key = bytes.fromhex(configuration["SMARTSEAL_AES_KEY"])
        nonce_prefix = bytes.fromhex(
            configuration["SMARTSEAL_NONCE_PREFIX"]
        )
        legacy_seal_id = int(
            configuration.get("SMARTSEAL_LEGACY_SEAL_ID", 1)
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Existing gateway key configuration is invalid.") from error

    if len(primary_key) != 16 or len(nonce_prefix) != 9:
        raise ValueError(
            "Existing gateway key must be 16 bytes and nonce prefix 9 bytes."
        )
    if not 1 <= legacy_seal_id <= 255:
        raise ValueError("Legacy seal ID must be between 1 and 255.")
    if seal_id == legacy_seal_id:
        raise ValueError(
            f"Seal ID {seal_id} is already assigned to the existing seal."
        )

    new_key = secrets.token_bytes(16)
    configuration["SMARTSEAL_LEGACY_SEAL_ID"] = legacy_seal_id
    # Keep the existing primary seal's entry aligned with its firmware key.
    configuration[str(legacy_seal_id)] = base64.b64encode(
        primary_key
    ).decode("ascii")
    configuration[str(seal_id)] = base64.b64encode(new_key).decode("ascii")

    header_contents = (
        "#pragma once\n\n"
        "#include <stdint.h>\n\n"
        f"constexpr uint8_t SEAL_ID = {seal_id};\n"
        "constexpr uint8_t AES_KEY[16] = {\n"
        f"{_format_bytes(new_key)}\n"
        "};\n"
        "constexpr uint8_t NONCE_PREFIX[9] = {\n"
        f"{_format_bytes(nonce_prefix)}\n"
        "};\n"
    )

    registry_temporary = None
    header_temporary = None
    try:
        registry_temporary = _stage_private_file(
            registry_path,
            json.dumps(configuration, indent=2) + "\n",
        )
        header_temporary = _stage_private_file(
            firmware_header, header_contents
        )
        os.replace(header_temporary, firmware_header)
        try:
            os.replace(registry_temporary, registry_path)
        except Exception:
            firmware_header.unlink(missing_ok=True)
            raise
    finally:
        if registry_temporary is not None:
            registry_temporary.unlink(missing_ok=True)
        if header_temporary is not None:
            header_temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a unique AES key for the sensorless multi-seal XIAO "
            "transmitter and register it with the gateway."
        )
    )
    parser.add_argument("--seal-id", type=int, default=2)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--firmware-header",
        type=Path,
        default=DEFAULT_FIRMWARE_HEADER,
    )
    arguments = parser.parse_args()

    provision_seal(
        arguments.seal_id,
        arguments.registry,
        arguments.firmware_header,
    )
    print(f"Provisioned seal {arguments.seal_id}.")
    print(f"Gateway registry updated: {arguments.registry}")
    print(f"Firmware secrets header created: {arguments.firmware_header}")
    print("Keep both files private; the firmware header contains seal key material.")


if __name__ == "__main__":
    main()
