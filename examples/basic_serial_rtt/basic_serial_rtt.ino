#include <Arduino.h>
#include <SerialRTT.h>

void setup() {
  SerialRTT.begin();
  SerialRTT.println("[SerialRTT] ready");
}

void loop() {
  static uint32_t counter = 0;

  SerialRTT.print("counter=");
  SerialRTT.print(counter++);
  SerialRTT.print(" uptime_ms=");
  SerialRTT.println(millis());

  delay(500);
}
