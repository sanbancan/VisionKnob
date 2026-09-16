## Image RAG with Gemma and GenieX

This app stores uploaded images locally, retrieves the most relevant images using their filenames and notes, and sends those images with your question to the locally running Gemma VLM through GenieX.

### Setup

From PowerShell in this directory:

```powershell
\.venv\Scripts\python.exe -m pip install -e .
geniex serve --host 127.0.0.1:18181
```

Leave the GenieX server running, then open a second terminal:

```powershell
\.venv\Scripts\python.exe -m streamlit run src/proj_1/app.py
```

Open the local URL printed by Streamlit. The default model is `qualcomm/Gemma-4-E4B-it:W4A16`; override it in the sidebar if your cached model ID differs.

### Arduino Uno Q controller

Upload `arduino/modulino_controller/modulino_controller.ino` to the Uno Q with the Modulino library installed. Keep the board connected over USB, then enter its serial port in the Streamlit sidebar, for example `COM5`. The app uses `115200` baud and sends `processing`, `success`, and `error` status commands to the sketch. Leave the port field empty to run without an Arduino.

### How retrieval works

Each image is saved in `data/images/` with an optional note. A question is matched against image filenames and notes, and the best matches are attached to the VLM request. If no text matches, the app sends the newest images so the model can still inspect them.

### Conversational questions

The app keeps the current conversation in Streamlit session state. Follow-up questions can refer to earlier answers, for example:

```text
What is in this image?
What color is it?
Does it look like an outdoor photo?
```

Use **Clear conversation** in the sidebar to start a fresh chat. Images are not sent again as part of old turns; the image retrieved for the newest question is attached to that turn.
