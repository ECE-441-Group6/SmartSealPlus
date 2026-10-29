# Determines whether incoming information should trigger an alert.

TEMP_HIGH = 8 #85   #temp values in f so it does always trigger an alert when the temp above room temp
TEMP_LOW = 2   #40

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