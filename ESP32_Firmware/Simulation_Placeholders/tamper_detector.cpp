/* Generates a simulated POF/photodetector state until the sensor is connected. */
#include <Arduino.h>
#include "tamper_detector.h"

void initTamperDetector()
{
}

bool tamperDetected()
{
    return random(0, 20) == 0;
}