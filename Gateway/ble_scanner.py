# Continuously scans for BLE advertisements sent by nearby ESP32-C3 SmartSeals.
#def scan_ble():

    # dummy packet

#    return {
 #       "seal_id": 1,
  #      "temperature": 4.5,
   #     "tamper": False,
    #    "vibration": False
    #}

# since we dont have ESP32-C3 devices, we will simulate BLE packets with random values for testing purposes

import random


def scan_ble():

    return {
        "seal_id": 1,
        "temperature": round(random.uniform(1,10),1),
        "tamper": random.choice([True, False]),
        "vibration": random.choice([True, False])
    }