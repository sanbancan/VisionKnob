#include <Modulino.h>

// Change this pin to the GPIO connected to your transistor/MOSFET gate.
const int VIBRATION_PIN = 9;
const unsigned long HEARTBEAT_INTERVAL_MS = 5000;

ModulinoPixels pixels;
ModulinoButtons buttons;
ModulinoKnob knob;
unsigned long lastHeartbeat = 0;
int lastKnobPosition = 0;

void sendEvent(const char* eventName, int value = 0) {
  Serial.print("{\"event\":\"");
  Serial.print(eventName);
  Serial.print("\",\"value\":");
  Serial.print(value);
  Serial.println("}");
}

void setPixels(uint8_t red, uint8_t green, uint8_t blue) {
  for (int index = 0; index < 8; index++) {
    pixels.set(index, red, green, blue);
  }
  pixels.show();
}

void vibrate(unsigned long durationMs) {
  digitalWrite(VIBRATION_PIN, HIGH);
  delay(durationMs);
  digitalWrite(VIBRATION_PIN, LOW);
}

void handleCommand(String command) {
  command.trim();

  if (command == "{\"command\":\"ready\"}") {
    setPixels(0, 30, 0);
    sendEvent("ready");
  } else if (command == "{\"command\":\"processing\"}") {
    setPixels(30, 20, 0);
    sendEvent("processing");
  } else if (command == "{\"command\":\"success\"}") {
    setPixels(0, 40, 0);
    vibrate(150);
    sendEvent("success");
  } else if (command == "{\"command\":\"error\"}") {
    setPixels(40, 0, 0);
    vibrate(600);
    sendEvent("error");
  } else if (command.startsWith("{\"command\":\"vibrate\"")) {
    vibrate(150);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(VIBRATION_PIN, OUTPUT);
  digitalWrite(VIBRATION_PIN, LOW);

  Modulino.begin();
  pixels.begin();
  buttons.begin();
  knob.begin();
  lastKnobPosition = knob.get();

  setPixels(0, 30, 0);
  sendEvent("ready");
}

void loop() {
  buttons.update();

  if (buttons.isPressed(0)) {
    sendEvent("button", 0);
  }
  if (buttons.isPressed(1)) {
    sendEvent("button", 1);
  }

  int knobDirection = knob.getDirection();
  if (knobDirection != 0) {
    lastKnobPosition += knobDirection;
    sendEvent("knob", lastKnobPosition);
  }

  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }

  if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = millis();
    sendEvent("heartbeat");
  }
}
