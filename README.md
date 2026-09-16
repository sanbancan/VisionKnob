# VisionKnob

VisionKnob is a local image-understanding assistant controlled through an Arduino UNO Q and Modulino hardware. Select an image with the Modulino Knob, type a question in Streamlit, and press Button A to submit it to a locally running Gemma vision model through GenieX.

## What it does

- Stores an image library locally in `data/images/`.
- Retrieves and analyzes the image selected with the physical knob.
- Runs Gemma inference through a local GenieX server.
- Uses Modulino Pixels for ready, processing, success, and error feedback.
- Uses Button A to submit a question and Button B to advance to the next image.
- Sends button, knob, and heartbeat events from the UNO Q over USB serial.

## Architecture

```text
Modulino Knob + Buttons + Pixels
			  |
		  I2C / Qwiic
			  |
		  Arduino UNO Q
			  |
		  USB serial, 115200 baud
			  |
		  Streamlit app
			  |
	   GenieX / Gemma VLM
```

Inference is local by default. The Streamlit app calls `http://127.0.0.1:18181/v1/chat/completions` and uses the model `qualcomm/Gemma-4-E4B-it:W4A16` unless overridden in the sidebar.

## Requirements

- Windows, macOS, or Linux
- Python 3.13 or newer
- GenieX with a cached Gemma vision model
- Arduino UNO Q
- Modulino library
- Modulino Pixels, Knob, and Buttons
- Arduino IDE 2 or Arduino CLI for uploading the sketch

## Python setup

From the project directory, create or activate the virtual environment and install the project:

```powershell
\.venv\Scripts\python.exe -m pip install -e .
```

Start GenieX in one terminal:

```powershell
geniex serve --host 127.0.0.1:18181
```

Start Streamlit in another terminal:

```powershell
\.venv\Scripts\python.exe -m streamlit run src/proj_1/app.py
```

Open the URL printed by Streamlit, usually [http://localhost:8501](http://localhost:8501).

## Arduino UNO Q setup

1. Connect the UNO Q to the computer with USB.
2. Connect the Modulino nodes to the UNO Q Qwiic/Modulino connector.
3. Install the **Arduino UNO Q Zephyr Core** in Arduino IDE Boards Manager.
4. Install the **Arduino_Modulino** library.
5. Open `arduino/modulino_controller/modulino_controller.ino`.
6. Select **Arduino UNO Q** and the board's port.
7. Compile and upload the sketch.

If the UNO Q core is not visible, add this URL under **File > Preferences > Additional Boards Manager URLs**:

```text
https://downloads.arduino.cc/packages/package_zephyr_index.json
```

The sketch uses USB serial at `115200` baud. On Windows, the board may appear as `COM3` or another COM port.

## Hardware controls

- **Knob:** selects the active image. Turn clockwise or counterclockwise to move through the library.
- **Button A:** submits the question currently typed in the Streamlit `Question` field.
- **Button B:** advances to the next image.
- **Button C:** reserved for a future action.
- **Pixels:** green ready, yellow processing, green success, and red error.

The app must have the UNO Q port entered in the sidebar, such as `COM3`. Do not keep Arduino Serial Monitor open at the same time because it can lock the serial port.

## Project layout

```text
src/proj_1/app.py                         Streamlit application
arduino/modulino_controller/              UNO Q firmware and documentation
data/images/                               Local image library
data/index.json                            Image metadata and descriptions
pitch/VisionKnob_Pitch_Deck.pptx           Pitch deck with speaker notes
pitch/create_deck.py                       Pitch deck generator
```
**Real-world applications**

- **Accessibility:** Hands-free or low-vision image exploration using physical controls and audio/display feedback.
- **Field inspection:** Inspect plants, equipment, construction sites, or landscapes without relying on cloud connectivity.
- **Education:** Teach computer vision, embedded systems, Arduino, and AI through a tactile interface.
- **Healthcare support:** Privately analyze forms, labels, or visual records locally, subject to medical validation.
- **Manufacturing:** Identify defects or verify parts while keeping factory images on-site.
- **Retail and inventory:** Ask questions about product images, packaging, or stock conditions.
- **Agriculture:** Inspect crops, leaves, soil, or field conditions at the edge.
- **Museums and archives:** Explore large local image collections using a physical browsing controller.
- **Emergency response:** Analyze images in environments with limited or unreliable internet.
- **Privacy-sensitive organizations:** Support local visual search where images cannot be uploaded to external AI services.

The strongest initial use cases are **education, accessibility, field inspection, and privacy-sensitive visual search** because they directly benefit from the physical controls and local inference.

## Troubleshooting

### GenieX connection refused

Start the GenieX server and confirm that `http://127.0.0.1:18181` opens before asking a question.

### Arduino port unavailable

Close Arduino Serial Monitor, Arduino IDE serial tools, and any other program using the port. Reconnect the UNO Q and check **Tools > Port** again.

### Board platform not found

Install the UNO Q Zephyr Core from Boards Manager using the additional package URL above.

### Images are not analyzed correctly

Confirm that the intended image is shown as **Selected image** in Streamlit before pressing Button A. The selected image is the image attached to the GenieX request.
