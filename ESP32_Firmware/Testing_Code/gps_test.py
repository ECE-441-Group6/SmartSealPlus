#cd ~/SmartSealPlus/TestFiles
#python3 gps_test.py
#GPS to Pi Pins
#3.3V to Pin 1
#Tx to Pin 10
#Rx to Pin 8
#GND to Pin 6

import serial
import pynmea2
from datetime import datetime

PORT = "/dev/ttyAMA0"
BAUD = 9600

print("Starting SmartSeal+ GPS test...")
print("Waiting for GPS data and satellite fix.")
print("Press Ctrl+C to stop.\n")

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

            if isinstance(msg, pynmea2.types.talker.GGA):
                print(f"Time: {msg.timestamp}")
                print(f"Fix quality: {msg.gps_qual}")
                print(f"Satellites: {msg.num_sats}")

                if int(msg.gps_qual or 0) > 0:
                    print(f"Latitude:  {msg.latitude}")
                    print(f"Longitude: {msg.longitude}")
                    print(f"Altitude:  {msg.altitude} m")
                    print("GPS FIX ACQUIRED")
                else:
                    print("NO FIX YET")

                print("-" * 35)

            elif isinstance(msg, pynmea2.types.talker.RMC):
                if msg.status == "A":
                    print("Valid RMC position:")
                    print(f"Latitude:  {msg.latitude}")
                    print(f"Longitude: {msg.longitude}")
                    print(f"Date: {msg.datestamp}")
                    print("-" * 35)

except serial.SerialException as exc:
    print(f"Serial port error: {exc}")
except KeyboardInterrupt:
    print("\nGPS test stopped.")
