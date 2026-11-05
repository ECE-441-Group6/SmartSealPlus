#ifndef THERMISTOR_H
#define THERMISTOR_H

void thermistorBegin();

bool readThermistor(float &temperatureC, float &temperatureF);

#endif

