#include <SPI.h>
#include "SdFat.h"

// ===========================================================
// SD CARD
// ===========================================================
//
// Adafruit microSD Card BFF
//
// Default BFF CS connection:
// TX = XIAO D6
//
// XIAO nRF52840 SPI:
// D8  = SCK
// D9  = MISO
// D10 = MOSI
//
// ===========================================================

#define SD_CS_PIN TX

SdFat SD;
File logFile;


// ===========================================================
// ADC INPUT
// ===========================================================

#define ANALOG_PIN A0


// ===========================================================
// BUTTON AND LED
// ===========================================================

// Button 1:
// Momentary pushbutton between D2 and GND.
//
// INPUT_PULLUP:
// Released = HIGH
// Pressed  = LOW
#define BUTTON_PIN 2


// Button 2:
// Momentary pushbutton between D3 and GND.
//
// INPUT_PULLUP:
// Released = HIGH
// Pressed  = LOW
//
// The value written to the CSV is inverted so:
// CSV 0 = released
// CSV 1 = pressed
#define BUTTON2_PIN 3


// LED:
// LED + resistor from D4 to GND
#define LED_PIN 4


// LED 2:
// LED + resistor from D5 to GND
#define LED2_PIN 5


// ===========================================================
// SAMPLING SETTINGS
// ===========================================================

const int SAMPLE_INTERVAL_MS = 10;     // 10 ms = 100 Hz
const int FLUSH_INTERVAL_MS  = 5000;   // Flush every 5 seconds


// ===========================================================
// ADC SETTINGS
// ===========================================================

const int ADC_MAX_VALUE = 4095;  // Approximate ADC reference range used for the voltage calculation.
const float ADC_REFERENCE_MV = 3300.0;


// ===========================================================
// TIMING
// ===========================================================

unsigned long lastSampleTime  = 0;
unsigned long lastFlushTime   = 0;
unsigned long recordStartTime = 0;


// ===========================================================
// LOGGING STATE
// ===========================================================

bool isLogging = false;


// ===========================================================
// TEMPORARY FILE
// ===========================================================

const char* TEMP_LOG_PATH = "/datalog.csv";


// ===========================================================
// FORWARD DECLARATIONS
// ===========================================================

void printMenu();
void deleteAllCsvFiles();
void listAllCsvFiles();

void startLogging(bool fromButton);
void stopLogging(bool fromButton);


// ===========================================================
// SETUP
// ===========================================================

void setup() {

  Serial.begin(115200);

  // Give USB serial a moment to initialize.
  delay(300);


  // ---------------------------------------------------------
  // Startup message
  // ---------------------------------------------------------

  Serial.println();
  Serial.println("XIAO nRF52840 ADC Logger");
  Serial.println("ADC + Button 2 Logger");
  Serial.println("==============================");


  // ---------------------------------------------------------
  // SPI / SD CARD
  // ---------------------------------------------------------

  Serial.println("Initializing SD card...");

  // Start the XIAO's hardware SPI bus.
  SPI.begin();

  //Configure SD card
  SdSpiConfig sdConfig(
    SD_CS_PIN,
    SHARED_SPI,
    SD_SCK_MHZ(16)    // 16 MHz is a conservative SPI speed and is generally reliable for SD cards.
  );


  if (!SD.begin(sdConfig)) {

    Serial.println("SD card initialization failed!");

    Serial.println();
    Serial.println("Check:");
    Serial.println("  - SD card inserted");
    Serial.println("  - SD card formatted as FAT32");
    Serial.println("  - BFF connected correctly");
    Serial.println("  - BFF CS jumper is still on TX");
    Serial.println("  - SPI pins are D8/D9/D10");

    while (true) {
      delay(1000);
    }
  }


  Serial.println("SD card initialized.");


  // ---------------------------------------------------------
  // ADC
  // ---------------------------------------------------------

  analogReadResolution(12);
  pinMode(ANALOG_PIN, INPUT);


  // ---------------------------------------------------------
  // BUTTON SETUP
  // ---------------------------------------------------------

  // Button 1:
  // D2 -> button -> GND
  //
  // Released = HIGH
  // Pressed  = LOW
  pinMode(BUTTON_PIN, INPUT_PULLUP);


  // Button 2:
  // D3 -> button -> GND
  //
  // Released = HIGH
  // Pressed  = LOW
  pinMode(BUTTON2_PIN, INPUT_PULLUP);


  // ---------------------------------------------------------
  // LED SETUP
  // ---------------------------------------------------------

  pinMode(LED_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);


  // LEDs off at startup
  digitalWrite(LED_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);


  // ---------------------------------------------------------
  // PRINT MENU
  // ---------------------------------------------------------

  printMenu();
}


// ===========================================================
// MAIN LOOP
// ===========================================================

void loop() {


  // =========================================================
  // 1. BUTTON 1 HANDLING
  //
  // Button 1 toggles recording:
  //
  // Press -> START
  // Press -> STOP
  // =========================================================

  static int lastReading = HIGH;
  static int stableState = HIGH;

  static unsigned long lastDebounceTime = 0;

  const unsigned long debounceDelay = 50;


  int reading = digitalRead(BUTTON_PIN);


  // Detect raw button change
  if (reading != lastReading) {

    lastDebounceTime = millis();
  }


  // Wait until button has been stable
  if ((millis() - lastDebounceTime) > debounceDelay) {


    // Has stable state changed?
    if (reading != stableState) {

      stableState = reading;


      // Button pressed
      //
      // INPUT_PULLUP:
      // LOW = pressed
      if (stableState == LOW) {


        // Not currently recording
        if (!isLogging) {

          startLogging(true);
        }


        // Currently recording
        else {

          stopLogging(true);
        }
      }
    }
  }


  lastReading = reading;


  // =========================================================
  // 2. SERIAL COMMANDS
  // =========================================================

  if (Serial.available()) {


    char cmd = Serial.read();


    // -------------------------------------------------------
    // START RECORDING
    //
    // Command: s
    // -------------------------------------------------------

    if (cmd == 's' || cmd == 'S') {


      if (!isLogging) {

        startLogging(false);
      }

      else {

        Serial.println("Already recording.");
      }
    }


    // -------------------------------------------------------
    // STOP RECORDING
    //
    // Command: x
    // -------------------------------------------------------

    else if (cmd == 'x' || cmd == 'X') {


      if (isLogging) {

        stopLogging(false);
      }

      else {

        Serial.println("Not recording.");
      }
    }


    // -------------------------------------------------------
    // DELETE SPECIFIC FILE
    //
    // Command: c
    // -------------------------------------------------------

    else if (cmd == 'c' || cmd == 'C') {


      if (isLogging) {

        Serial.println(
          "Stop recording first with 'x' or button."
        );
      }


      else {

        Serial.println();
        Serial.println("Enter filename to delete");
        Serial.println("(without or with .csv):");
        Serial.println("Example: steamtrap_12s");


        // Wait for filename
        while (!Serial.available()) {

          delay(10);
        }


        String fname =
          Serial.readStringUntil('\n');

        fname.trim();


        if (fname.length() == 0) {

          Serial.println("Cancelled.");
        }


        else {


          // Make sure filename begins with /
          if (!fname.startsWith("/")) {

            fname = "/" + fname;
          }


          // Add .csv if necessary
          if (!fname.endsWith(".csv")) {

            fname += ".csv";
          }


          Serial.print("Deleting: ");
          Serial.println(fname);


          if (SD.exists(fname.c_str()) &&
              SD.remove(fname.c_str())) {

            Serial.println("File deleted.");
          }


          else {

            Serial.println(
              "File not found or delete failed."
            );
          }
        }
      }
    }


    // -------------------------------------------------------
    // DELETE ALL CSV FILES
    //
    // Command: a
    // -------------------------------------------------------

    else if (cmd == 'a' || cmd == 'A') {


      if (isLogging) {

        Serial.println("Stop recording first.");
      }


      else {

        Serial.println();
        Serial.println(
          "Type 'YES' to delete ALL CSV files:"
        );


        while (!Serial.available()) {

          delay(10);
        }


        String conf =
          Serial.readStringUntil('\n');

        conf.trim();


        if (conf == "YES") {

          deleteAllCsvFiles();
        }


        else {

          Serial.println("Cancelled.");
        }
      }
    }


    // -------------------------------------------------------
    // LIST ALL CSV FILES
    //
    // Command: b
    // -------------------------------------------------------

    else if (cmd == 'b' || cmd == 'B') {


      if (isLogging) {

        Serial.println(
          "[!] Listing while recording: "
          "file sizes may be changing."
        );
      }


      listAllCsvFiles();
    }


    // -------------------------------------------------------
    // PRINT MENU
    //
    // Command: m
    // -------------------------------------------------------

    else if (cmd == 'm' || cmd == 'M') {

      printMenu();
    }
  }


  // =========================================================
  // 3. LOGGING LOOP
  // =========================================================

  if (isLogging) {


    unsigned long nowMs = millis();


    // -------------------------------------------------------
    // ADC + BUTTON 2 SAMPLE
    // -------------------------------------------------------

    if (
      nowMs - lastSampleTime >=
      (unsigned long)SAMPLE_INTERVAL_MS
    ) {


      lastSampleTime = nowMs;


      // -----------------------------------------------------
      // READ ADC
      // -----------------------------------------------------

      int val = analogRead(ANALOG_PIN);


      // Convert ADC count to approximate millivolts.
      //
      // 0    -> 0 mV
      // 4095 -> approximately 3300 mV
      //
      // This is an approximate conversion.
      int voltage_mV =
        (int)(
          ((float)val /
           (float)ADC_MAX_VALUE) *
          ADC_REFERENCE_MV
        );


      // -----------------------------------------------------
      // READ BUTTON 2
      // -----------------------------------------------------

      int button2State =
        digitalRead(BUTTON2_PIN);


      // -----------------------------------------------------
      // LED 2
      //
      // Physical button:
      //
      // HIGH = released
      // LOW  = pressed
      // -----------------------------------------------------

      if (button2State == LOW) {

        digitalWrite(LED2_PIN, HIGH);
      }

      else {

        digitalWrite(LED2_PIN, LOW);
      }


      // -----------------------------------------------------
      // WRITE CSV ROW
      //
      // Format:
      //
      // Timestamp_ms,ADC_Value,Voltage_mV,Button2
      //
      // Button2 is inverted:
      //
      // Physical released HIGH -> CSV 0
      // Physical pressed  LOW  -> CSV 1
      // -----------------------------------------------------

      if (logFile) {

        logFile.printf(
          "%lu,%d,%d,%d\n",
          nowMs,
          val,
          voltage_mV,
          !button2State
        );
      }
    }


    // -------------------------------------------------------
    // PERIODIC FLUSH
    // -------------------------------------------------------

    if (
      nowMs - lastFlushTime >=
      (unsigned long)FLUSH_INTERVAL_MS
    ) {


      lastFlushTime = nowMs;


      if (logFile) {

        logFile.flush();
      }
    }
  }
}


// ===========================================================
// START LOGGING
//
// Used by:
//   - Serial 's'
//   - Button 1
// ===========================================================

void startLogging(bool fromButton) {


  // Open temporary file
  logFile =
    SD.open(TEMP_LOG_PATH, FILE_WRITE);


  if (logFile) {


    // -------------------------------------------------------
    // CSV HEADER
    // -------------------------------------------------------

    logFile.println(
      "Timestamp_ms,ADC_Value,Voltage_mV,Button2"
    );


    // -------------------------------------------------------
    // ENABLE LOGGING
    // -------------------------------------------------------

    isLogging = true;


    // -------------------------------------------------------
    // INITIALIZE TIMING
    // -------------------------------------------------------

    recordStartTime = millis();

    lastFlushTime = millis();

    lastSampleTime = millis();


    // -------------------------------------------------------
    // TURN LED ON
    // -------------------------------------------------------

    digitalWrite(LED_PIN, HIGH);


    // -------------------------------------------------------
    // TELL USER HOW RECORDING STARTED
    // -------------------------------------------------------

    if (fromButton) {

      Serial.println();
      Serial.println(
        ">>> RECORDING STARTED (button) <<<"
      );
    }

    else {

      Serial.println();
      Serial.println(
        ">>> RECORDING STARTED (serial) <<<"
      );
    }


    Serial.print("Temp file: ");
    Serial.println(TEMP_LOG_PATH);


    Serial.println(
      "Button 2 logging is active."
    );
  }


  else {

    Serial.println(
      "Error: could not open temp log file."
    );
  }
}


// ===========================================================
// STOP LOGGING
//
// Used by:
//   - Serial 'x'
//   - Button 1
// ===========================================================

void stopLogging(bool fromButton) {


  if (!isLogging) {

    return;
  }


  // ---------------------------------------------------------
  // STOP LOGGING
  // ---------------------------------------------------------

  isLogging = false;


  // ---------------------------------------------------------
  // FLUSH AND CLOSE FILE
  // ---------------------------------------------------------

  if (logFile) {

    logFile.flush();

    logFile.close();
  }


  // ---------------------------------------------------------
  // CALCULATE RECORDING DURATION
  // ---------------------------------------------------------

  unsigned long recordEnd =
    millis();


  unsigned long durationSec =
    (recordEnd - recordStartTime) / 1000;


  // ---------------------------------------------------------
  // TURN LED OFF
  // ---------------------------------------------------------

  digitalWrite(LED_PIN, LOW);


  // ---------------------------------------------------------
  // TELL USER HOW RECORDING STOPPED
  // ---------------------------------------------------------

  if (fromButton) {

    Serial.println();
    Serial.println(
      ">>> RECORDING STOPPED (button) <<<"
    );
  }

  else {

    Serial.println();
    Serial.println(
      ">>> RECORDING STOPPED (serial) <<<"
    );
  }


  // ---------------------------------------------------------
  // PRINT DURATION
  // ---------------------------------------------------------

  Serial.print("Recording duration: ");
  Serial.print(durationSec);
  Serial.println(" s");


  // ---------------------------------------------------------
  // DETERMINE FILENAME
  // ---------------------------------------------------------

  String baseName;


  if (fromButton) {


    // Button recordings automatically use:
    //
    // btnlog_12s.csv

    baseName = "btnlog";
  }


  else {


    // Ask user for filename

    Serial.println(
      "Enter base filename "
      "(no extension, e.g. steamtrap):"
    );


    while (!Serial.available()) {

      delay(10);
    }


    baseName =
      Serial.readStringUntil('\n');

    baseName.trim();


    if (baseName.length() == 0) {

      baseName = "recording";
    }
  }


  // ---------------------------------------------------------
  // BUILD FINAL FILENAME
  //
  // Example:
  //
  // /steamtrap_12s.csv
  // ---------------------------------------------------------

  String finalPath = "/";

  finalPath += baseName;

  finalPath += "_";

  finalPath += String(durationSec);

  finalPath += "s.csv";


  Serial.print("Saving as: ");
  Serial.println(finalPath);


  // ---------------------------------------------------------
  // RENAME TEMPORARY FILE
  // ---------------------------------------------------------

  if (
    SD.rename(
      TEMP_LOG_PATH,
      finalPath.c_str()
    )
  ) {

    Serial.println(
      "Saved successfully."
    );
  }


  else {

    Serial.println(
      "Rename failed! "
      "Temp file may still exist as /datalog.csv"
    );
  }
}


// ===========================================================
// LIST ALL CSV FILES
// ===========================================================

void listAllCsvFiles() {


  Serial.println();
  Serial.println(
    "=== CSV FILES ON SD CARD ==="
  );


  File root =
    SD.open("/");


  if (!root) {

    Serial.println(
      "Failed to open filesystem."
    );

    return;
  }


  bool foundAny = false;


  while (true) {


    File file =
      root.openNextFile();


    if (!file) {

      break;
    }


    String name =
      file.name();


    bool isDir =
      file.isDirectory();


    file.close();


    // Only display CSV files
    if (
      !isDir &&
      name.endsWith(".csv")
    ) {

      Serial.println(name);

      foundAny = true;
    }
  }


  root.close();


  if (!foundAny) {

    Serial.println(
      "[no CSV files found]"
    );
  }


  Serial.println(
    "=============================="
  );

  Serial.println();
}


// ===========================================================
// DELETE ALL CSV FILES
// ===========================================================

void deleteAllCsvFiles() {


  Serial.println(
    "Deleting all .csv files in root..."
  );


  File root =
    SD.open("/");


  if (!root) {

    Serial.println(
      "Failed to open root directory."
    );

    return;
  }


  while (true) {


    File file =
      root.openNextFile();


    if (!file) {

      break;
    }


    String name =
      file.name();


    bool isDir =
      file.isDirectory();


    file.close();


    // Only delete CSV files
    if (
      !isDir &&
      name.endsWith(".csv")
    ) {


      if (!name.startsWith("/")) {

        name = "/" + name;
      }


      Serial.print("Deleting: ");
      Serial.print(name);


      if (
        SD.remove(name.c_str())
      ) {

        Serial.println(
          " -> OK"
        );
      }


      else {

        Serial.println(
          " -> FAILED"
        );
      }
    }
  }


  root.close();


  Serial.println(
    "Done deleting all .csv files."
  );

  Serial.println();
}


// ===========================================================
// SERIAL MENU
// ===========================================================

void printMenu() {


  Serial.println(
    "================================="
  );


  Serial.println(
    "Commands (when USB is connected):"
  );


  Serial.println(
    "  s = START recording (serial)"
  );


  Serial.println(
    "  x = STOP + name file (serial)"
  );


  Serial.println(
    "  b = LIST all CSV files"
  );


  Serial.println(
    "  c = DELETE one file"
  );


  Serial.println(
    "  a = DELETE ALL CSV files "
    "(requires 'YES')"
  );


  Serial.println(
    "  m = Menu"
  );


  Serial.println();


  Serial.println(
    "Hardware controls:"
  );


  Serial.println(
    "  Button 1 D2 = start/stop"
  );


  Serial.println(
    "  Button 2 D3 = logged input"
  );


  Serial.println(
    "  LED D4      = ON while recording"
  );


  Serial.println(
    "  LED D5      = ON while button 2 is pressed"
  );


  Serial.println();


  Serial.println(
    "SD card:"
  );


  Serial.println(
    "  CS  = TX / D6"
  );


  Serial.println(
    "  SCK = D8"
  );


  Serial.println(
    "  MISO = D9"
  );


  Serial.println(
    "  MOSI = D10"
  );


  Serial.println();


  Serial.println(
    "Button 2:"
  );


  Serial.println(
    "  Released = HIGH (physical)"
  );


  Serial.println(
    "  Pressed  = LOW  (physical)"
  );


  Serial.println(
    "  CSV = 0 when released"
  );


  Serial.println(
    "  CSV = 1 when pressed"
  );


  Serial.println(
    "================================="
  );
}
