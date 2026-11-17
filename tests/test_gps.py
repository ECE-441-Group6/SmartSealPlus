#!/usr/bin/env python3

import serial

PORT = "/dev/serial0"
BAUD = 9600


def to_decimal_degrees(value, direction):
    """Convert an NMEA latitude or longitude field to decimal degrees."""
    if not value or not direction:
        return None

    degree_digits = 2 if direction in ("N", "S") else 3
    degrees = int(value[:degree_digits])
    minutes = float(value[degree_digits:])
    result = degrees + minutes / 60

    if direction in ("S", "W"):
        result = -result

    return result


def main():
    print(f"Reading GPS from {PORT} at {BAUD} baud. Press Ctrl+C to stop.")

    try:
        with serial.Serial(PORT, BAUD, timeout=2) as gps:
            while True:
                raw = gps.readline()
                if not raw:
                    print("No GPS data received.")
                    continue

                sentence = raw.decode("ascii", errors="replace").strip()
                fields = sentence.split(",")

                # GGA sentences contain fix quality, satellite count, and position.
                # This accepts both GP... and GN... talker IDs.
                if not fields[0].endswith("GGA") or len(fields) < 8:
                    continue

                try:
                    fix_quality = int(fields[6] or "0")
                    satellites = int(fields[7] or "0")
                except ValueError:
                    print(f"Could not parse GPS sentence: {sentence}")
                    continue

                has_fix = fix_quality > 0 and satellites > 0

                if has_fix:
                    quality_names = {
                        1: "GPS",
                        2: "DGPS",
                        4: "RTK fixed",
                        5: "RTK float",
                        6: "estimated/dead reckoning",
                    }
                    quality = quality_names.get(fix_quality, f"quality {fix_quality}")
                    lat = to_decimal_degrees(fields[2], fields[3])
                    lon = to_decimal_degrees(fields[4], fields[5])

                    print(
                        f"FIX: YES | {quality} | satellites: {satellites} | "
                        f"latitude: {lat} | longitude: {lon}",
                        flush=True,
                    )
                else:
                    print(
                        f"FIX: NO | fix quality: {fix_quality} | "
                        f"satellites: {satellites}",
                        flush=True,
                    )

    except serial.SerialException as exc:
        print(f"Could not open/read {PORT}: {exc}")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()