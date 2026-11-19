#!/usr/bin/env python3
"""Read one GPS fix and resolve it to a nearby place using OpenStreetMap."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import serial

PORT = "/dev/serial0"
BAUD = 9600
SERIAL_TIMEOUT_SECONDS = 2
LOOKUP_TIMEOUT_SECONDS = 10
MAX_NMEA_LINE_BYTES = 256
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
# Public Nominatim requires an identifying User-Agent. Keep this a one-shot,
# user-run lookup rather than querying once per GPS sentence.
USER_AGENT = "SmartSealGPSLocation/1.0 (Raspberry Pi diagnostic)"


def parse_gga(sentence):
    """Return (fix_quality, satellites, latitude, longitude) or None."""
    if not sentence.startswith("$") or "*" not in sentence:
        return None

    body, checksum_text = sentence[1:].rsplit("*", 1)
    if len(checksum_text) != 2:
        return None
    try:
        expected_checksum = int(checksum_text, 16)
    except ValueError:
        return None

    actual_checksum = 0
    for character in body:
        actual_checksum ^= ord(character)
    if actual_checksum != expected_checksum:
        return None

    fields = body.split(",")
    if len(fields) < 8 or not fields[0].endswith("GGA"):
        return None

    try:
        quality = int(fields[6] or "0")
        satellites = int(fields[7] or "0")
        latitude = to_decimal_degrees(fields[2], fields[3])
        longitude = to_decimal_degrees(fields[4], fields[5])
    except (TypeError, ValueError):
        return None

    if (
        quality <= 0
        or satellites <= 0
        or latitude is None
        or longitude is None
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None

    return quality, satellites, latitude, longitude


def to_decimal_degrees(value, direction):
    """Convert NMEA degrees/minutes coordinates to signed decimal degrees."""
    if not value or direction not in ("N", "S", "E", "W"):
        return None

    degree_digits = 2 if direction in ("N", "S") else 3
    degrees = int(value[:degree_digits])
    minutes = float(value[degree_digits:])
    if not 0 <= minutes < 60:
        return None

    result = degrees + minutes / 60
    return -result if direction in ("S", "W") else result


def reverse_geocode(latitude, longitude):
    """Resolve coordinates using one OpenStreetMap Nominatim request."""
    query = urlencode(
        {
            "format": "jsonv2",
            "lat": f"{latitude:.6f}",
            "lon": f"{longitude:.6f}",
            "zoom": "18",
            "addressdetails": "1",
        }
    )
    request = Request(
        f"{NOMINATIM_URL}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urlopen(request, timeout=LOOKUP_TIMEOUT_SECONDS) as response:
        # Bound the response size before parsing remote data.
        payload = response.read(64 * 1024 + 1)
    if len(payload) > 64 * 1024:
        raise ValueError("Location service response was too large.")

    result = json.loads(payload.decode("utf-8"))
    return result.get("display_name") or "No nearby place name found."


def read_fix():
    print(f"Reading GPS from {PORT} at {BAUD} baud; waiting for a fix.")
    print("Keep the antenna facing up with a clear view of the sky. Press Ctrl+C to stop.")

    with serial.Serial(PORT, BAUD, timeout=SERIAL_TIMEOUT_SECONDS) as gps:
        while True:
            raw_line = gps.readline()
            if not raw_line or len(raw_line) > MAX_NMEA_LINE_BYTES:
                continue
            try:
                sentence = raw_line.decode("ascii").strip()
            except UnicodeDecodeError:
                continue

            fix = parse_gga(sentence)
            if fix is not None:
                return fix


def main():
    try:
        quality, satellites, latitude, longitude = read_fix()
        print(f"GPS fix quality: {quality}; satellites: {satellites}")
        print(f"Coordinates: {latitude:.6f}, {longitude:.6f}")
        print("Looking up nearby place name (internet required)...")

        try:
            place = reverse_geocode(latitude, longitude)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
            print(f"Could not look up place name: {error}")
            print("The GPS coordinates above are still available.")
            return 1

        print(f"Approximate location: {place}")
        print("Location data © OpenStreetMap contributors")
        print("https://www.openstreetmap.org/copyright")
        return 0
    except serial.SerialException as error:
        print(f"Could not open/read {PORT}: {error}")
        return 1
    except KeyboardInterrupt:
        print("\nStopped before a GPS fix was received.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
