"""Generate a per-seal key and matching local firmware configuration."""

import argparse
import base64
import json
import secrets
from pathlib import Path


def provision_key(seal_id, registry_path, firmware_header):
    if seal_id < 1:
        raise ValueError("seal_id must be positive")
    key = secrets.token_bytes(16)

    registry = {"seals": {}}
    path = Path(registry_path)
    if path.exists():
        with path.open(encoding="utf-8") as registry_file:
            registry = json.load(registry_file)
    registry.setdefault("seals", {})[str(seal_id)] = {
        "key": base64.b64encode(key).decode("ascii")
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as registry_file:
        json.dump(registry, registry_file, indent=2)
        registry_file.write("\n")

    header = (
        "#pragma once\n\n"
        "#include <stdint.h>\n\n"
        "constexpr uint8_t SMARTSEAL_ENCRYPTION_KEY[16] = {\n"
        + ", ".join(f"0x{value:02X}" for value in key)
        + "\n};\n"
    )
    firmware_path = Path(firmware_header)
    firmware_path.parent.mkdir(parents=True, exist_ok=True)
    firmware_path.write_text(header, encoding="ascii")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("seal_id", type=int)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--firmware-header", required=True)
    args = parser.parse_args()
    provision_key(args.seal_id, args.registry, args.firmware_header)


if __name__ == "__main__":
    main()
