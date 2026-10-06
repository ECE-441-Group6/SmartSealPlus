# Determines whether incoming information should trigger an alert, such as tampering or temperature outside the allowed range.
TEMP_HIGH = 8
TEMP_LOW = 2

def process_alerts(packet):
    alerts = []

    if packet["tamper"]:
        alerts.append("TAMPER DETECTED")

    if packet["temperature"] > TEMP_HIGH:
        alerts.append("HIGH TEMPERATURE")

    if packet["temperature"] < TEMP_LOW:
        alerts.append("LOW TEMPERATURE")

    if packet["vibration"]:
        alerts.append("VIBRATION EVENT")

    return alerts