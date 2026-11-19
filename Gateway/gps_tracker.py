"""Read the latest valid GPS fix without blocking BLE packet processing."""

import math
import os
import threading
import time

import serial

GPS_PORT = os.getenv("SMARTSEAL_GPS_PORT", "/dev/serial0")
GPS_BAUD = int(os.getenv("SMARTSEAL_GPS_BAUD", "9600"))
GPS_FIX_MAX_AGE_SECONDS = 30
GPS_MAX_LINE_BYTES = 256


def _parse_gga(line):
    if not line.startswith("$") or "*" not in line:
        return None
    body, checksum_text = line[1:].rsplit("*", 1)
    if len(checksum_text) != 2:
        return None
    try:
        expected = int(checksum_text, 16)
        fields = body.split(",")
        if len(fields) < 8 or not fields[0].endswith("GGA"):
            return None
        quality = int(fields[6] or "0")
        satellites = int(fields[7] or "0")
        latitude = _nmea_coordinate(fields[2], fields[3])
        longitude = _nmea_coordinate(fields[4], fields[5])
    except (TypeError, ValueError):
        return None

    checksum = 0
    for char in body:
        checksum ^= ord(char)
    if (
        checksum != expected
        or quality <= 0
        or satellites <= 0
        or latitude is None
        or longitude is None
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None
    return latitude, longitude


def _nmea_coordinate(value, direction):
    if not value or direction not in ("N", "S", "E", "W"):
        return None
    degree_digits = 2 if direction in ("N", "S") else 3
    degrees = int(value[:degree_digits])
    minutes = float(value[degree_digits:])
    if not 0 <= minutes < 60:
        return None
    coordinate = degrees + minutes / 60
    return -coordinate if direction in ("S", "W") else coordinate


class GPSLocationTracker:
    """Maintain a thread-safe, short-lived GPS fix from a serial receiver."""

    def __init__(self, port=GPS_PORT, baud=GPS_BAUD):
        self.port = port
        self.baud = baud
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._fix = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._read_loop,
            name="smartseal-gps-reader",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def latest_fix(self):
        with self._lock:
            fix = self._fix
        if fix is None or time.monotonic() - fix[2] > GPS_FIX_MAX_AGE_SECONDS:
            return None
        return {"gps_latitude": fix[0], "gps_longitude": fix[1]}

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=2) as gps:
                    while not self._stop.is_set():
                        raw_line = gps.readline()
                        if not raw_line or len(raw_line) > GPS_MAX_LINE_BYTES:
                            continue
                        try:
                            line = raw_line.decode("ascii").strip()
                        except UnicodeDecodeError:
                            continue
                        coordinates = _parse_gga(line)
                        if coordinates is not None:
                            with self._lock:
                                self._fix = (*coordinates, time.monotonic())
            except (serial.SerialException, OSError) as error:
                if not self._stop.is_set():
                    print(f"GPS unavailable on {self.port}: {error}; retrying.")
                    self._stop.wait(10)
