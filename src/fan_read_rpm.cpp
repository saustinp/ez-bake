#include <Arduino.h>

int fanTachPin = 2;

float hz;
int pulse_duration, last_pulse_duration=10000; // Initialize to 10ms
int rpm = 0;
int tmp_rpm = 0;
bool measureFanBool;
int last_rpm = rpm;

void isr() {
  if (measureFanBool){
    pulse_duration = pulseIn(fanTachPin, HIGH);
  }
  measureFanBool = 0;
}

void setup() {
  // initialize serial communications at 9600 bps:
  Serial.begin(9600);

  // analogWriteFrequency(analogOutPin, 25000);
  pinMode(fanTachPin, INPUT);
}

void loop() {

  measureFanBool = 1;
  attachInterrupt(digitalPinToInterrupt(fanTachPin), isr, FALLING);
  delay(100);
  detachInterrupt(digitalPinToInterrupt(fanTachPin));

  if (pulse_duration < 1000){
    pulse_duration = last_pulse_duration;
  }
  last_pulse_duration = pulse_duration;
  
  hz = 1/(pulse_duration/1000000.)/2; // Decimal point forces conversion to an integer
  tmp_rpm = hz/2*60;
  tmp_rpm = tmp_rpm - (tmp_rpm%10);

  if ((tmp_rpm > 10) && (tmp_rpm < 3150)){
    rpm = tmp_rpm;
  }

  // Serial.print("\t Fan RPM = ");
  if (rpm != last_rpm)
    Serial.println(rpm);
    last_rpm = rpm;

}
