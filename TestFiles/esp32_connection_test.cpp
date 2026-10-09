/*ESP Dev Module*/

/*To configure the ESP32 development environment on Windows:
Connect the ESP32-WROOM-32 development board to the computer using a USB data cable.
Install the CP210x USB-to-UART Bridge VCP driver from the official Silicon Labs website.
Open Windows Device Manager and verify that the board appears under Ports (COM & LPT).
Open Arduino IDE and install the Espressif ESP32 board package through Boards Manager if it is not already installed.
Select Tools → Board → esp32 → ESP32 Dev Module and select the assigned port under Tools → Port. The port may differ between computers; my current port is COM4.
Set Upload Speed to 115200.*/

/*Open Arduino IDE and upload the basic serial test sketch.
Open Serial Monitor and set the baud rate to 115200.
Confirm that the board prints SmartSeal+ ESP32 Hardware Test, ESP32-WROOM-32 is running!, and repeated ESP32 status: OK messages.*/

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("SmartSeal+ ESP32 Hardware Test");
  Serial.println("ESP32-WROOM-32 is running!");
}

void loop() {
  Serial.println("ESP32 status: OK");
  delay(2000);
}
