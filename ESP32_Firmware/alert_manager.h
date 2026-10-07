/* Declares local alert functions for the buzzer, LEDs, and event logging. */
#ifndef ALERT_MANAGER_H
#define ALERT_MANAGER_H

#include "sensor_manager.h"

void initAlerts();
void processAlerts(SensorData data);

#endif