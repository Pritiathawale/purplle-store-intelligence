import json
import os
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(BASE_DIR, "test_video.mp4")
OUTPUT_FILE = os.path.join(BASE_DIR, "events.json")
# VIDEO_PATH = r"d:\\purplle-store-intelligence\\ai-service\\test_video.mp4"       # path to your video file
BACKEND_URL = "http://localhost:8080/events"  # Spring Boot endpoint
SAVE_TO_FILE = True                 # set False once backend is running
# OUTPUT_FILE = "events.json"         # local output for Day 1 testing
FRAME_SKIP = 15                     # process every 15th frame (speeds things up)
OVERCROWD_THRESHOLD = 10            # alert if more than this many people detected
# ──────────────────────────────────────────────────────────────────────────────

model = YOLO("yolov8n.pt")  # 'n' = nano model, fast and light, downloads automatically

def count_people(frame):
    """Run YOLO on a frame and return count of detected persons."""
    results = model(frame, verbose=False)
    count = 0
    for result in results:
        for cls in result.boxes.cls:
            if int(cls) == 0:  # class 0 = person in COCO dataset
                count += 1
    return count

def determine_alert(people_count):
    """Return alert type based on people count."""
    if people_count > OVERCROWD_THRESHOLD:
        return "OVERCROWDING"
    elif people_count == 0:
        return "EMPTY_STORE"
    else:
        return None

def build_event(people_count, frame_number, fps):
    """Build the event JSON object."""
    alert = determine_alert(people_count)
    # Calculate approximate timestamp in video
    video_seconds = frame_number / fps if fps > 0 else 0
    event = {
        "peopleCount": people_count,
        "timestamp": datetime.now().isoformat(),
        "videoTimestamp": round(video_seconds, 2),
        "frameNumber": frame_number,
        "alert": alert
    }
    return event

def send_to_backend(event):
    """POST event to Spring Boot backend."""
    try:
        response = requests.post(
            BACKEND_URL,
            json=event,
            headers={"Content-Type": "application/json"},
            timeout=3
        )
        if response.status_code == 201 or response.status_code == 200:
            print(f"  ✓ Sent to backend: count={event['peopleCount']}")
        else:
            print(f"  ✗ Backend error {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("  ✗ Backend not running yet — event not sent")

def process_video():
    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        print(f"ERROR: Cannot open video '{VIDEO_PATH}'")
        print("Make sure the video file is in the same folder as detector.py")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video loaded: {total_frames} frames at {fps:.1f} FPS")
    print(f"Processing every {FRAME_SKIP}th frame...\n")

    all_events = []
    frame_number = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Only process every Nth frame
        if frame_number % FRAME_SKIP == 0:
            people_count = count_people(frame)
            event = build_event(people_count, frame_number, fps)
            all_events.append(event)

            alert_str = f" ⚠ ALERT: {event['alert']}" if event["alert"] else ""
            print(f"Frame {frame_number:5d} | People: {people_count:3d}{alert_str}")

            # Send to backend if it's running (Day 2 onwards)
            if not SAVE_TO_FILE:
                send_to_backend(event)

        frame_number += 1

    cap.release()

    # Save all events to JSON file (Day 1 mode)
    if SAVE_TO_FILE:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(all_events, f, indent=2)
        print(f"\n✓ Done! {len(all_events)} events saved to {OUTPUT_FILE}")
        print(f"  Total alerts: {sum(1 for e in all_events if e['alert'])}")

        # Print summary
        counts = [e["peopleCount"] for e in all_events]
        if counts:
            print(f"  Max people seen: {max(counts)}")
            print(f"  Avg people: {sum(counts)/len(counts):.1f}")

if __name__ == "__main__":
    process_video()