import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import serial
import time
from collections import Counter

model_path = 'hand_landmarker.task'

# ── Serial connection ────────────────────────────────────────────────────────
# arduino = serial.Serial(
#     port='COM4',       # Virtual serial pair: COM3 (Python) <-> COM4 (Proteus)
#     baudrate=9600,
#     timeout=1,
#     rtscts=False,
#     dsrdtr=False
# )
arduino = serial.serial_for_url('rfc2217://localhost:4000', baudrate=9600, timeout=2)
time.sleep(3)
arduino.reset_input_buffer()
arduino.reset_output_buffer()

# ✅ Startup connection check
if arduino.is_open:
    # print("[OK] Serial port COM3 opened successfully")
    print("[OK] Connected to Wokwi via RFC2217 port 4000")
else:
    print("[ERROR] Could not open COM3 — check Virtual Serial Port Driver pairing")
    exit()

# ── MediaPipe setup ──────────────────────────────────────────────────────────
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=1
)
detector = vision.HandLandmarker.create_from_options(options)

# ── Camera ───────────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Camera not found")
    exit()

# ── State variables ──────────────────────────────────────────────────────────
last_sent        = -1
last_time        = 0
buffer           = []
frame_count      = 0
last_fingers     = None
last_display_text  = ""
last_landmark_points = []

COOLDOWN_SEC = 0.3   # seconds between sends (was 4.0 — reduced for responsiveness)

# ── Finger counter ───────────────────────────────────────────────────────────
def count_fingers(hand_landmarks):
    """
    Counts raised fingers: index, middle, ring, pinky.
    Returns 0-3 (capped at 3 for 3-LED system).
    Thumb is intentionally excluded.
    """
    count = 0
    if hand_landmarks[8].y  < hand_landmarks[6].y:   # index
        count += 1
    if hand_landmarks[12].y < hand_landmarks[10].y:  # middle
        count += 1
    if hand_landmarks[16].y < hand_landmarks[14].y:  # ring
        count += 1
    if hand_landmarks[20].y < hand_landmarks[18].y:  # pinky
        count += 1
    return min(count, 3)

# ── Send command with echo readback ─────────────────────────────────────────
def send_command(value):
    """Send finger count to Arduino and read back OK echo for confirmation."""
    try:
        arduino.reset_input_buffer()
        arduino.write((str(value) + '\n').encode())
        arduino.flush()
        time.sleep(0.1)

        # ✅ Read echo reply from ATmega (e.g. "OK:1")
        response = arduino.readline().decode().strip()
        if response:
            print(f"[SENT] {value}  |  [REPLY] {response}")
        else:
            print(f"[SENT] {value}  |  [REPLY] <no response — check Proteus is running>")
    except serial.SerialException as e:
        print(f"[SERIAL ERROR] {e}")

# ── Main loop ────────────────────────────────────────────────────────────────
while True:
    success, img = cap.read()
    if not success:
        continue

    img = cv2.flip(img, 1)
    frame_count += 1

    # Run detection every 6th frame for performance
    if frame_count % 2 == 0:
        img_rgb   = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        result    = detector.detect(mp_image)

        if result.hand_landmarks:
            landmarks    = result.hand_landmarks[0]
            fingers      = count_fingers(landmarks)

            # Majority-vote buffer (smooths out flickering)
            buffer.append(fingers)
            if len(buffer) > 3:
                buffer.pop(0)
            last_fingers      = Counter(buffer).most_common(1)[0][0]
            last_display_text = f'Fingers: {last_fingers}'

            # Save landmark dot positions for drawing on every frame
            h, w, _ = img.shape
            last_landmark_points = [
                (int(lm.x * w), int(lm.y * h)) for lm in landmarks
            ]

        else:
            # No hand detected — send 0 to turn all LEDs off (once)
            if last_fingers is not None and last_sent != 0:
                send_command(0)
                last_sent = 0
                last_time = time.time()

            buffer.clear()
            last_fingers         = None
            last_display_text    = 'No Hand'
            last_landmark_points = []

        # ✅ Send command when finger count changes and cooldown elapsed
        current_time = time.time()
        if (last_fingers is not None
                and last_fingers != last_sent
                and (current_time - last_time) > COOLDOWN_SEC):

            send_command(last_fingers)
            last_sent = last_fingers
            last_time = current_time

    # ── Draw landmarks on every frame (no blinking) ──────────────────────────
    for (cx, cy) in last_landmark_points:
        cv2.circle(img, (cx, cy), 5, (0, 255, 0), -1)

    # ── HUD text ─────────────────────────────────────────────────────────────
    color = (0, 0, 255) if last_display_text == 'No Hand' else (0, 255, 0)
    if last_display_text:
        cv2.putText(img, last_display_text, (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

    # ── LED indicator boxes (visual feedback on screen) ──────────────────────
    for i, label in enumerate(['LED1', 'LED2', 'LED3']):
        active = (last_sent == i + 1)
        box_color = (0, 255, 0) if active else (50, 50, 50)
        cv2.rectangle(img, (10 + i * 90, 70), (90 + i * 90, 110), box_color, -1)
        cv2.putText(img, label, (18 + i * 90, 97),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.imshow("Gesture Control", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ── Cleanup ──────────────────────────────────────────────────────────────────
cap.release()
cv2.destroyAllWindows()
arduino.close()
print("[DONE] Serial port closed")