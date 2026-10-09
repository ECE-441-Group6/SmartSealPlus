#cd ~/SmartSealPlus/TestFiles
#~/gps-venv/bin/python gps_readable.py
import serial
import pynmea2

PORT = "/dev/ttyAMA0"
BAUD = 9600

print("SmartSeal+ Human-Readable GPS Monitor")
print("Waiting for GPS data...\n")

try:
    with serial.Serial(PORT, BAUD, timeout=2) as gps:
        while True:
            line = gps.readline().decode(
                "ascii", errors="replace"
            ).strip()

            if not line.startswith("$"):
                continue

            try:
                msg = pynmea2.parse(line)
            except pynmea2.ParseError:
                continue

            if msg.sentence_type == "GGA":
                quality = int(msg.gps_qual or 0)
                satellites = int(msg.num_sats or 0)

                print("-" * 40)
                print("GPS fix:", "VALID" if quality > 0 else "NO FIX")
                print("Satellites used:", satellites)

                if quality > 0:
                    print(f"Latitude:  {msg.latitude:.6f}°")
                    print(f"Longitude: {msg.longitude:.6f}°")
                    print(f"Latitude direction:  {msg.lat_dir}")
                    print(f"Longitude direction: {msg.lon_dir}")

                    if msg.altitude:
                        print(
                            f"Altitude: {msg.altitude} "
                            f"{msg.altitude_units}"
                        )
                else:
                    print("Coordinates unavailable until GPS fix.")

except KeyboardInterrupt:
    print("\nGPS monitor stopped.")

except serial.SerialException as error:
    print(f"Serial error: {error}")
