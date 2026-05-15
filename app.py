import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import serial
import time
import threading
import subprocess
import sys
import os
from collections import deque, Counter
from flask import Flask, Response, jsonify, render_template
import json
import base64
import numpy as np

# ── Flask App ──────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Global State ───────────────────────────────────────────────────────────
state = {
    "running": False,
    "finger_count": 0,
    "leds": [False, False, False],
    "fps": 0,
    "serial_connected": False,
    "wokwi_connected": False,
    "log": [],
    "landmarks": [],
    "gesture_label": "No Hand Detected"
}

arduino = None
stop_event = threading.Event()
camera_thread = None
detection_thread = None

# Shared frame buffer
latest_frame = None
latest_frame_lock = threading.Lock()
processed_frame = None
processed_frame_lock = threading.Lock()

# ── Logging ────────────────────────────────────────────────────────────────
def add_log(message, level="info"):
    entry = {
        "time": time.strftime("%H:%M:%S"),
        "message": message,
        "level": level
    }
    state["log"].insert(0, entry)
    if len(state["log"]) > 50:
        state["log"].pop()
    print(f"[{entry['time']}] {message}")

# ── Serial Connection ──────────────────────────────────────────────────────
def connect_serial(max_attempts=10, delay=3):
    global arduino
    add_log("Waiting for Wokwi to initialize...", "info")
    
    for attempt in range(1, max_attempts + 1):
        try:
            add_log(f"Serial connection attempt {attempt}/{max_attempts}...", "info")
            arduino = serial.serial_for_url(
                'rfc2217://localhost:4000',
                baudrate=9600,
                timeout=2
            )
            time.sleep(2)  # Let connection stabilize
            
            # Test the connection
            arduino.write(b'0\n')
            time.sleep(0.5)
            response = arduino.readline().decode('utf-8', errors='ignore').strip()
            
            state["serial_connected"] = True
            state["wokwi_connected"] = True
            add_log(f"Connected to Wokwi simulator!", "success")
            return True
            
        except Exception as e:
            add_log(f"Attempt {attempt} failed: {str(e)[:50]}", "warning")
            if arduino:
                try:
                    arduino.close()
                except:
                    pass
                arduino = None
            
            if attempt < max_attempts:
                add_log(f"Retrying in {delay} seconds...", "info")
                time.sleep(delay)
    
    state["serial_connected"] = False
    state["wokwi_connected"] = False
    add_log("Could not connect to Wokwi. Make sure simulator is running.", "error")
    return False

# ── Send to Arduino ────────────────────────────────────────────────────────
def send_to_arduino(value):
    global arduino
    if arduino is None or not state["serial_connected"]:
        return
    try:
        arduino.write(f"{value}\n".encode())
        arduino.flush()
        
        # Update LED state
        state["leds"] = [
            value >= 1,
            value >= 2,
            value >= 3
        ]
    except Exception as e:
        state["serial_connected"] = False
        state["wokwi_connected"] = False
        add_log(f"Serial error: {str(e)[:50]}", "error")
        arduino = None

# ── Camera Thread ──────────────────────────────────────────────────────────
def camera_capture_thread():
    global latest_frame
    
    add_log("Starting camera...", "info")
    
    # Try different camera indices
    cap = None
    for idx in [0, 1, 2]:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            add_log(f"Camera {idx} opened successfully!", "success")
            break
        cap.release()
    
    if not cap or not cap.isOpened():
        add_log("ERROR: Could not open any camera!", "error")
        return
    
    # Camera settings - lower res = faster processing = less lag
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    fps_counter = 0
    fps_start = time.time()
    
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue
        
        frame = cv2.flip(frame, 1)
        
        with latest_frame_lock:
            latest_frame = frame.copy()
        
        fps_counter += 1
        elapsed = time.time() - fps_start
        if elapsed >= 1.0:
            state["fps"] = round(fps_counter / elapsed, 1)
            fps_counter = 0
            fps_start = time.time()
        
        time.sleep(0.01)  # ~30fps cap, prevents CPU overload
    
    cap.release()
    add_log("Camera stopped.", "info")

# ── Detection Thread ───────────────────────────────────────────────────────
def detection_thread_func():
    global processed_frame
    
    model_path = 'hand_landmarker.task'
    if not os.path.exists(model_path):
        add_log(f"ERROR: {model_path} not found!", "error")
        return
    
    add_log("Loading hand detection model...", "info")
    
    base_options = mp.tasks.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    detector = vision.HandLandmarker.create_from_options(options)
    add_log("Hand detection model loaded!", "success")
    
    finger_buffer = deque(maxlen=1)
    last_sent = -99
    last_drawn_frame = None

    # Fingertip and PIP joint indices (index, middle, ring, pinky)
    TIPS = [8, 12, 16, 20]
    PIPS = [6, 10, 14, 18]
    
    while not stop_event.is_set():
        with latest_frame_lock:
            frame = latest_frame.copy() if latest_frame is not None else None
        
        if frame is None:
            time.sleep(0.015)
            continue
        
        h, w = frame.shape[:2]

        # Detect on small frame for speed
        small = cv2.resize(frame, (320, 240))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = detector.detect(mp_image)
        
        draw_frame = frame.copy()

        if result.hand_landmarks:
            lm = result.hand_landmarks[0]

            # Draw landmarks on full-size frame
            for lm_point in lm:
                cx, cy = int(lm_point.x * w), int(lm_point.y * h)
                cv2.circle(draw_frame, (cx, cy), 5, (0, 255, 100), -1)

            # Draw connections
            connections = [
                (0,1),(1,2),(2,3),(3,4),
                (0,5),(5,6),(6,7),(7,8),
                (0,9),(9,10),(10,11),(11,12),
                (0,13),(13,14),(14,15),(15,16),
                (0,17),(17,18),(18,19),(19,20),
                (5,9),(9,13),(13,17)
            ]
            for s, e in connections:
                x1, y1 = int(lm[s].x * w), int(lm[s].y * h)
                x2, y2 = int(lm[e].x * w), int(lm[e].y * h)
                cv2.line(draw_frame, (x1, y1), (x2, y2), (0, 200, 80), 2)

            state["landmarks"] = [{"x": p.x, "y": p.y} for p in lm]

            # Count fingers: tip above PIP = finger is up
            finger_count = 0
            for tip, pip in zip(TIPS, PIPS):
                if lm[tip].y < lm[pip].y:
                    finger_count += 1

            finger_buffer.append(finger_count)
            stable_count = Counter(finger_buffer).most_common(1)[0][0]

            state["finger_count"] = stable_count

            if stable_count > 3:
                state["gesture_label"] = "Out of Range"
                state["leds"] = [False, False, False]
                state["finger_count"] = 0
                cv2.putText(draw_frame, "OUT OF RANGE", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                send_to_arduino(0)
                if last_sent != -99:
                    add_log("Out of Range — LEDs OFF", "warning")
                last_sent = -99
            else:
                state["gesture_label"] = f"{stable_count} Finger{'s' if stable_count != 1 else ''} Detected"
                cv2.putText(draw_frame, f"Fingers: {stable_count}", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 2)
                # ── ACTIVITY LOG FIX ──────────────────────────────────────
                # If coming back from out-of-range (last_sent == -99),
                # force resend and log even if count is same as before
                if stable_count != last_sent or last_sent == -99:
                    send_to_arduino(stable_count)
                    last_sent = stable_count
                    if stable_count == 0:
                        add_log("No fingers — LEDs OFF", "info")
                    else:
                        add_log(f"{stable_count} finger(s) detected → LEDs updated", "info")
        else:
            state["gesture_label"] = "No Hand Detected"
            state["finger_count"] = 0
            state["landmarks"] = []
            cv2.putText(draw_frame, "No Hand", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 255), 2)
            if last_sent != 0:
                send_to_arduino(0)
                last_sent = 0
                state["leds"] = [False, False, False]
            finger_buffer.clear()

        last_drawn_frame = draw_frame
        with processed_frame_lock:
            processed_frame = draw_frame.copy()

        time.sleep(0.015)
    
    detector.close()
    add_log("Detection stopped.", "info")

# ── Video Stream Generator ─────────────────────────────────────────────────
def generate_frames():
    while True:
        with processed_frame_lock:
            frame = processed_frame.copy() if processed_frame is not None else None
        
        if frame is None:
            # Send placeholder black frame
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Starting camera...", (160, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)
            frame = placeholder
        
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.033)  # ~30fps stream

# ── Flask Routes ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/state')
def get_state():
    return jsonify({
        "running": state["running"],
        "finger_count": state["finger_count"],
        "leds": state["leds"],
        "fps": state["fps"],
        "serial_connected": state["serial_connected"],
        "wokwi_connected": state["wokwi_connected"],
        "log": state["log"][:10],
        "gesture_label": state["gesture_label"],
        "landmarks": state["landmarks"]
    })

@app.route('/api/start', methods=['POST'])
def start_system():
    global camera_thread, detection_thread, stop_event
    
    if state["running"]:
        return jsonify({"status": "already_running"})
    
    add_log("=== Starting Gesture Control System ===", "info")
    stop_event.clear()
    state["running"] = True
    
    # Start camera thread
    camera_thread = threading.Thread(target=camera_capture_thread, daemon=True)
    camera_thread.start()
    
    # Start detection thread
    detection_thread = threading.Thread(target=detection_thread_func, daemon=True)
    detection_thread.start()
    
    # Connect serial in background
    serial_thread = threading.Thread(target=connect_serial, daemon=True)
    serial_thread.start()
    
    return jsonify({"status": "started"})

@app.route('/api/stop', methods=['POST'])
def stop_system():
    global arduino
    
    add_log("=== Stopping system ===", "info")
    stop_event.set()
    state["running"] = False
    state["serial_connected"] = False
    state["wokwi_connected"] = False
    state["leds"] = [False, False, False]
    state["finger_count"] = 0
    state["fps"] = 0
    state["gesture_label"] = "System Stopped"
    
    if arduino:
        try:
            arduino.write(b'0\n')
            time.sleep(0.2)
            arduino.close()
        except:
            pass
        arduino = None
    
    add_log("System stopped successfully.", "info")
    return jsonify({"status": "stopped"})

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Close All — stops system, kills all CMDs, stops Wokwi simulation"""
    global arduino

    # Stop serial
    stop_event.set()
    if arduino:
        try:
            arduino.write(b'0\n')
            arduino.close()
        except:
            pass

    def kill_everything():
        time.sleep(1)

        # Kill all CMD windows
        try:
            subprocess.run(
                'taskkill /f /fi "WINDOWTITLE eq Gesture*" /im cmd.exe',
                shell=True, timeout=3
            )
        except:
            pass

        try:
            subprocess.run(
                'taskkill /f /im cmd.exe',
                shell=True, timeout=3
            )
        except:
            pass

        # Finally kill this Flask process
        os.kill(os.getpid(), 9)

    threading.Thread(target=kill_everything, daemon=True).start()
    return jsonify({"status": "shutdown"})

# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "="*50)
    print("  GESTURE CONTROL SYSTEM - DASHBOARD")
    print("="*50)
    print("  Dashboard: http://localhost:5000")
    print("  Click 'Start System' in the dashboard")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)