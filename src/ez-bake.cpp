#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "constants.h"
#include "parsefloat.h"

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
tempCArray temperatures;
int isUnsafe = 0;
float currentSetpointC = 0;
uint8_t loopsSinceStateChange = DEBOUNCE_LOOPS;
bool lastHeaterState = false;
bool targetHeaterState = false;
float tmp = 0;

void setup(void) {
  Serial.begin(SERIAL_BAUDRATE);
  sensors.begin();
  pinMode(OUTPUT_PIN, OUTPUT);
  // Write last heater state to the pin on startup so it is always correct
  digitalWrite(OUTPUT_PIN, lastHeaterState);

  const uint8_t NUM_THERMOCOUPLES = sensors.getDeviceCount();
  temperatures.resize(NUM_THERMOCOUPLES, 0);
}

bool areAllTemperaturesValid() {
  for (auto& reading: temperatures) {
    if (reading == DEVICE_DISCONNECTED ||
        reading < MIN_LEGAL_TEMP_C ||
        reading > MAX_LEGAL_TEMP_C) {
      return false;
    }
  }
  return true;
}

void readThermocouples() {
  const uint8_t NUM_THERMOCOUPLES = temperatures.size();
  sensors.requestTemperatures();
  for (int8_t i = 0; i < NUM_THERMOCOUPLES; i++ ) {
    temperatures[i] = sensors.getTempCByIndex(i);
  }
}

void serialPrintSummary(bool targetHeaterState, float currentSetpointC, int isUnsafe) {
  for (auto& reading: temperatures) {
      Serial.print(reading);
      Serial.print(" ");
  }
  Serial.print(targetHeaterState);
  Serial.print(" ");
  Serial.print(currentSetpointC);
  Serial.print(" ");
  Serial.print(isUnsafe);
  Serial.println();
}

bool getHeaterControlState(float setpointC) {
  // Get the mean temperature
  float meanTemperatureC = 0;
  float validTempCounts = 0;
  for (auto& reading: temperatures) {
      if (!isnan(reading)){
        meanTemperatureC += reading;
        validTempCounts++;
      }
  }
  meanTemperatureC /= validTempCounts;

  // Simple bang-bang control
  return meanTemperatureC < setpointC;
}

void loop(void) {
  if (isUnsafe) {
    digitalWrite(OUTPUT_PIN, LOW);
  }

    // Accepts an "estop" command from the user. Interprets any temp over 1000C as a shut-down command
    checkForNewString();
    tmp = processInput();
    if (tmp >= 0){
      if ((tmp < MAX_LEGAL_TEMP_C) && !isUnsafe)    // Input temp has to be bounded between [0, MAX_LEGAL_TEMP_C) degrees
        currentSetpointC = tmp;
      if (tmp > 1000){
        isUnsafe = 1;   // isUnsafe == 1 means that the controller received an erroneous setpoint, to be interpreted as an estop condition
        currentSetpointC = 0;
      }
    }

  readThermocouples();   // Reads all thermocouples
  
  if (!areAllTemperaturesValid()) {
    isUnsafe = 2;   // isUnsafe == 2 means that the controller detected a fault condition
    currentSetpointC = 0;
  }

  if (!isUnsafe){
    targetHeaterState = getHeaterControlState(currentSetpointC);
    loopsSinceStateChange = min(loopsSinceStateChange + 1, DEBOUNCE_LOOPS);
    if (targetHeaterState == lastHeaterState || loopsSinceStateChange < DEBOUNCE_LOOPS) {
      targetHeaterState = lastHeaterState; // Either we don't want to change our control state, or aren't allowed to yet. Updated so that the heater state can be printed out along with the sensor summaries on every loop
    }
  }
  else
    targetHeaterState = 0;

  serialPrintSummary(targetHeaterState, currentSetpointC, isUnsafe);    // Moving this line down so the heater status can be printed after the bang-bang calculation

  // Adding a conditional so that the heater state can be printed out at every iteration - avoids breaking out of loop() if the state is not updated
  if ((targetHeaterState != lastHeaterState) && !isUnsafe){
    digitalWrite(OUTPUT_PIN, targetHeaterState);
    loopsSinceStateChange = 0;
    lastHeaterState = targetHeaterState;
  }
}