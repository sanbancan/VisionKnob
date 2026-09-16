# Modulino controller sketch

This sketch sends controller events over USB serial at `115200` baud:

```json
{"event":"ready","value":0}
{"event":"button","value":0}
{"event":"knob","value":12}
{"event":"heartbeat","value":0}
```

It accepts these newline-terminated commands from the computer:

```text
{"command":"ready"}
{"command":"processing"}
{"command":"success"}
{"command":"error"}
{"command":"vibrate"}
```

## Upload

1. Install the Arduino IDE and the `Modulino` library.
2. Open `modulino_controller.ino`.
3. Select the Arduino Uno Q board and its port.
4. Upload the sketch.
5. Open Serial Monitor at `115200` baud.
6. Press the buttons or turn the knob and check for JSON events.

## Streamlit integration

Start the Streamlit app while the Uno Q remains connected, then enter the board's serial port in the sidebar. The app sends newline-terminated JSON commands at `115200` baud:

```json
{"command":"ready"}
{"command":"processing"}
{"command":"success"}
{"command":"error"}
```

The sketch shows ready/processing/success/error with the pixel ring and uses the vibration motor for success and error. In the Streamlit app, turn the knob to select an image, press button 0 to submit the typed question, and press button 1 to advance to the next image.

The sketch assumes `ModulinoPixels`, `ModulinoButtons`, and `ModulinoKnob` are connected through the Modulino/I2C connectors.

## Vibration motor safety

`VIBRATION_PIN` is set to GPIO 9 as a placeholder. Connect that pin to a transistor or MOSFET gate, not directly to the motor. Use a suitable motor supply, common ground, and a flyback diode across the motor.

If the installed Modulino library exposes different method names for your library version, use the library's built-in examples to adjust `begin`, `update`, `isPressed`, `getPosition`, or `set` calls.
