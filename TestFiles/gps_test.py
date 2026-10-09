#cd ~/SmartSealPlus/TestFiles
#python3 gps_test.py
#GPS to Pi Pins
#3.3V to Pin 1
#Tx to Pin 10
#Rx to Pin 8
#GND to Pin 6
import serial
from datetime import datetime

PORT = "/dev/ttyAMA0"
BAUD = 9600

print("SmartSeal+ Ultimate GPS Breakout v3 Test")
print(f"GPS port: {PORT} at {BAUD} baud")
print("Waiting for GPS data...\n")

try:
    with serial.Serial(PORT, BAUD, timeout=2) as gps:
        while True:
            raw = gps.readline().decode(
                "ascii", errors="replace"
            ).strip()

            if not raw:
                continue

            print(raw)

            fields = raw.split(",")

            if raw.startswith("$GPGGA") or raw.startswith("$GNGGA"):
                if len(fields) > 6:
                    fix_quality = fields[6]
                    satellites = fields[7] if len(fields) > 7 else "?"
                    print(
                        f"GPS fix quality: {fix_quality}; "
                        f"satellites used: {satellites}"
                    )

                if len(fields) > 5 and fields[2] and fields[4]:
                    print(
                        f"Latitude raw: {fields[2]} {fields[3]}, "
                        f"Longitude raw: {fields[4]} {fields[5]}"
                    )

except KeyboardInterrupt:
    print("\nGPS test stopped.")

except serial.SerialException as error:
    print(f"Serial error: {error}")
