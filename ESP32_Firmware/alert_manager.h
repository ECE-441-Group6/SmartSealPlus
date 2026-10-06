/* Declares local alert functions. */
#ifndef ALERT_MANAGER_H
#define ALERT_MANAGER_H

#include "sensor_manager.h"

void initAlerts();
void processAlerts(SensorData data);

#endif