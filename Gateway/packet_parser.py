# Converts raw BLE advertisement bytes into useful information such as seal ID, temperature, and tamper status.
def parse_packet(packet):

    try:
        return {
            "seal_id": packet["seal_id"],
            "temperature": packet["temperature"],
            "tamper": packet["tamper"],
            "vibration": packet["vibration"]
        }

    except Exception as e:
        print(f"Packet Error: {e}")
        return None