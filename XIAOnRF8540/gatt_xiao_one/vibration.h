
#ifndef VIBRATION_H
#define VIBRATION_H

void vibrationBegin();

int readVibrationADC();

float vibrationADCToVolts(int adcValue);

#endif
