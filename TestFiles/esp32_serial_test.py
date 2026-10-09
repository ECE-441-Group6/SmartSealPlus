#Work in progress
import glob
import serial
import time

ports = (
    glob.glob("/dev/ttyACM*")
    + glob.glob("/dev/ttyUSB*")
)

if not ports:
    print("No ESP32 serial port found.")
    print("Check the USB cable and run lsusb.")
    raise SystemExit(1)

port = ports[0]
print(f"Opening {port}")

try:
    with serial.Serial(port, 115200, timeout=2) as ser:
        time.sleep(2)
        print("Listening for ESP32 messages...")
        while True:
            line = ser.readline().decode(
                "utf-8", errors="replace"
            ).strip()
            if line:
                print(line)
except KeyboardInterrupt:
    print("\nTest stopped.")
except serial.SerialException as e:
    print(f"Serial error: {e}")