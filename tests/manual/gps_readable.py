#cd ~/SmartSealPlus/TestFiles
#python3 gps_readable.py
import math

import serial
import pynmea2

PORT = "/dev/ttyAMA0"
BAUD = 9600
MAX_NMEA_LINE_BYTES = 256

print("SmartSeal+ Human-Readable GPS Monitor")
print("Waiting for GPS data...\n")

try:
    with serial.Serial(PORT, BAUD, timeout=2) as gps:
        while True:
            raw_line = gps.readline()
            if not raw_line or len(raw_line) > MAX_NMEA_LINE_BYTES:
                continue

            try:
                line = raw_line.decode("ascii").strip()
            except UnicodeDecodeError:
                continue

            if not line.startswith("$"):
                continue

            try:
                # Require the checksum so damaged or incomplete NMEA data is
                # never presented as a valid reading.
                msg = pynmea2.parse(line, checksums="required")
            except (pynmea2.ParseError, ValueError, TypeError):
                continue

            if msg.sentence_type == "GGA":
                try:
                    quality = int(msg.gps_qual or 0)
                    satellites = int(msg.num_sats or 0)
                except (TypeError, ValueError):
                    continue

                print("-" * 40)
                print("GPS fix:", "VALID" if quality > 0 else "NO FIX")
                print("Satellites used:", satellites)

                if quality > 0:
                    try:
                        latitude = float(msg.latitude)
                        longitude = float(msg.longitude)
                    except (TypeError, ValueError):
                        print("Coordinates unavailable: invalid GPS data.")
                        continue

                    if (
                        not math.isfinite(latitude)
                        or not math.isfinite(longitude)
                        or not -90 <= latitude <= 90
                        or not -180 <= longitude <= 180
                    ):
                        print("Coordinates unavailable: invalid GPS data.")
                        continue

                    print(f"Latitude:  {latitude:.6f}°")
                    print(f"Longitude: {longitude:.6f}°")
                    print(f"Latitude direction:  {msg.lat_dir}")
                    print(f"Longitude direction: {msg.lon_dir}")

                    try:
                        altitude = float(msg.altitude)
                    except (TypeError, ValueError):
                        altitude = None
                    if altitude is not None and math.isfinite(altitude):
                        print(f"Altitude: {altitude} {msg.altitude_units}")
                else:
                    print("Coordinates unavailable until GPS fix.")

except KeyboardInterrupt:
    print("\nGPS monitor stopped.")

except serial.SerialException as error:
    print(f"Serial error: {error}")
