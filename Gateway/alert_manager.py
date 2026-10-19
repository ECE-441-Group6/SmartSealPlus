# Determines whether incoming information should trigger an alert.

TEMP_HIGH = 8.0
TEMP_LOW = 2.0

def process_alerts(packet):
    alerts = []

    # Check for tampering.
    if packet["tamper"]:
        alerts.append("TAMPER DETECTED")

    # Check for temperatures outside the allowed range.
    if packet["temperature"] > TEMP_HIGH:
        alerts.append("HIGH TEMPERATURE")

    if packet["temperature"] < TEMP_LOW:
        alerts.append("LOW TEMPERATURE")

    # Check for vibration events.
    if packet["vibration"]:
        alerts.append("VIBRATION EVENT")

    return alerts