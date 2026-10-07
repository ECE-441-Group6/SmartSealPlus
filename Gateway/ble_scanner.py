# Reads BLE advertisements from nearby ESP32-C3 SmartSeals.
# The simulator uses this same packet shape until real BLE hardware is available.
import random

def scan_ble():
    """Return one simulated ESP32 sensor advertisement.

    Replace this function with a real BLE scan that decodes advertisements
    from the ESP32 when hardware communication is implemented.
    """
    # Random values let the complete gateway and dashboard flow be exercised
    # without an ESP32 or a Bluetooth adapter.
    return {
        "seal_id": 1,
        "temperature": round(random.uniform(1.0, 10.0), 1),
        "tamper": random.choice([True, False]),
        "vibration": random.choice([True, False]),
    }