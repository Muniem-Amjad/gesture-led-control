# Gesture Control System

A real-time hand gesture control system that uses a camera to detect finger count and control LEDs accordingly. The system uses Python with MediaPipe for hand detection and communicates with an Arduino (via Wokwi simulator or real hardware) to control 3 LEDs through a web-based dashboard.

---

## Project Overview

- Camera captures live video feed
- **MediaPipe** detects hand landmarks and counts raised fingers in real time
- Python Flask backend processes finger count and sends commands to Arduino via Serial (RFC2217)
- Arduino controls **3 LEDs** based on detected finger count
- A **web dashboard** runs on `localhost:5000` showing live camera feed, LED status, finger count, FPS, connection status, and activity log

### LED Behavior

| Fingers Shown | LED 1 | LED 2 | LED 3 |
|---------------|-------|-------|-------|
| 0 / No Hand   | OFF   | OFF   | OFF   |
| 1 Finger      | ON    | OFF   | OFF   |
| 2 Fingers     | ON    | ON    | OFF   |
| 3 Fingers     | ON    | ON    | ON    |
| 4+ Fingers    | OFF   | OFF   | OFF   (Out of Range) |

---

## Requirements

### System Requirements
- Windows 10/11
- Python 3.9 or higher
- Google Chrome or any modern web browser
- VS Code with Wokwi extension

### Python Libraries

Install all required libraries using:

```bash
pip install flask opencv-python mediapipe pyserial numpy
```

| Library | Purpose |
|--------|---------|
| `flask` | Web dashboard backend |
| `opencv-python` | Camera capture and frame processing |
| `mediapipe` | Hand landmark detection |
| `pyserial` | Serial communication with Arduino |
| `numpy` | Frame/image array handling |

### Additional File Required
- `hand_landmarker.task` — MediaPipe hand landmark model file  
  Download from: [MediaPipe Models](https://developers.google.com/mediapipe/solutions/vision/hand_landmarker)  
  Place it in the **root of the project folder** (same folder as `app.py`)

---

## Wokwi Simulator Setup

1. Install **VS Code** from [https://code.visualstudio.com](https://code.visualstudio.com)
2. Open VS Code and go to Extensions (`Ctrl+Shift+X`)
3. Search for **Wokwi** and install the extension
4. Get a free Wokwi license at [https://wokwi.com](https://wokwi.com) and activate it in VS Code
5. Open the project folder in VS Code
6. The `diagram.json` and `sketch.ino` files define the Arduino circuit with 3 LEDs
7. Press `F1` → type **Wokwi: Start Simulator** → press Enter to launch the simulation

> ⚠️ Make sure the Wokwi simulator is **running before** you start the system in the dashboard, otherwise the serial connection will fail.

---

## How to Run

### Step 1 — Start Wokwi Simulator
- Open the project folder in VS Code
- Press `F1` → **Wokwi: Start Simulator**
- Wait for the simulator to load and show the Arduino circuit

### Step 2 — Start the Flask App
- Double click `START_GESTURE_SYSTEM.bat`  
  *(This will start the Flask server and open the dashboard in your browser automatically)*

  **Or** run manually:
  ```bash
  python app.py
  ```
  Then open your browser and go to: `http://localhost:5000`

### Step 3 — Start the System
- In the web dashboard, click **▶ Start System**
- The system will:
  - Start the camera
  - Load the hand detection model
  - Connect to the Wokwi simulator via serial

### Step 4 — Show Fingers to Camera
- Hold your hand in front of the camera
- The system detects 1, 2, or 3 fingers and turns on LEDs accordingly
- Showing 4 or more fingers displays **"Out of Range"** and turns all LEDs OFF

### Step 5 — Stop the System
- Click **⏹ Stop System** to stop detection and camera
- Click **⏻ Close All** to fully shut down Flask and close all background processes

---

## Project Structure

```
gesture_con/
├── app.py                    # Main Flask backend + detection logic
├── hand_landmarker.task      # MediaPipe hand landmark model
├── START_GESTURE_SYSTEM.bat  # One-click launcher
├── diagram.json              # Wokwi circuit diagram
├── sketch.ino                # Arduino LED control code
├── templates/
│   └── index.html            # Web dashboard UI
├── static/                   # Static assets (CSS, JS, icons)
└── .vscode/
    ├── tasks.json            # VS Code auto-task config
    └── settings.json         # VS Code workspace settings
```

---

##  How Serial Communication Works

- Wokwi simulator exposes a virtual serial port at `localhost:4000` using **RFC2217** protocol
- Python connects to this port and sends a number (`0`, `1`, `2`, or `3`) to the Arduino
- Arduino reads the number and turns on the corresponding LEDs

---

##  Notes

- This project was tested on **Windows** with a standard USB webcam
- The system also works with a **real Arduino UNO** connected via USB — just change the serial port in `app.py` from `rfc2217://localhost:4000` to your COM port (e.g., `COM3`)
- If the camera shows a black screen, try restarting the bat file
- Make sure no other application is using the camera before starting

---

##  Author

Made by Muniem Amjad-using Python, MediaPipe, Arduino, and Flask.