# Converts raw BLE advertisement bytes into useful information such as seal ID, temperature, and tamper status.
def parse_packet(packet):
    # Extract the fields shared by the ESP32 advertisement and gateway logic.
    try:
        return {
            "seal_id": packet["seal_id"],
            "temperature": packet["temperature"],
            "tamper": packet["tamper"],
            "vibration": packet["vibration"]
        }

    except Exception as e:
        # Invalid or incomplete advertisements are ignored by the main loop.
        print(f"Packet Error: {e}")
        return None