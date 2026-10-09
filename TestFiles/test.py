import asyncio 
from bleak import BleakClient, BleakScanner 
 
DEVICE_NAME = "ESP32_Sensor" 
 
SERVICE_UUID = "12345678-1234-1234-1234-1234567890ab" 
 
CHARACTERISTIC_UUID = ( 
   "abcdefab-1234-1234-1234-abcdefabcdef" 
) 
 
 
def handle_notification(sender, data): 
   message = data.decode("utf-8", errors="replace").strip() 
 
   if message: 
       print(message, flush=True) 
 
 
async def main(): 
   while True: 
       print(f"Scanning for {DEVICE_NAME}...") 
 
       device = await BleakScanner.find_device_by_name( 
           DEVICE_NAME, 
           timeout=10.0 
       ) 
 
       if device is None: 
           print("ESP32 not found. Retrying...") 
           await asyncio.sleep(2) 
           continue 
 
       try: 
           print(f"Connecting to {device.address}...") 
 
           async with BleakClient(device) as client: 
               print("Connected to ESP32") 
               print("Timestamp_ms,ADC_Value,Voltage_mV") 
 
               await client.start_notify( 
                   CHARACTERISTIC_UUID, 
                   handle_notification 
               ) 
 
               while client.is_connected: 
                   await asyncio.sleep(1) 
 
       except Exception as error: 
           print(f"BLE error: {error}") 
 
       print("Disconnected. Reconnecting...") 
       await asyncio.sleep(2) 
 
 
if __name__ == "__main__": 
   try: 
       asyncio.run(main()) 
   except KeyboardInterrupt: 
       print("Receiver stopped.") 