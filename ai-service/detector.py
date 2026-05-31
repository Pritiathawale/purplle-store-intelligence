import json
import os
from datetime import datetime, timedelta

import cv2
import requests
from ultralytics import YOLO

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CAMERAS = [
    {"id": "CAM_1", "file": "CAM 1.mp4",  "zone": "makeup_zone"},
    {"id": "CAM_2", "file": "CAM 2.mp4",  "zone": "skin_zone"},
    {"id": "CAM_3", "file": "CAM 3.mp4",  "zone": "entrance"},
    {"id": "CAM_4", "file": "CAM 4.mp4",  "zone": "floor"},
    {"id": "CAM_5", "file": "CAM 5.mp4",  "zone": "billing"},
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# VIDEO_PATH = os.path.join(BASE_DIR, "test_video.mp4")
OUTPUT_FILE = os.path.join(BASE_DIR, "events.json")
# VIDEO_PATH = r"d:\\purplle-store-intelligence\\ai-service\\test_video.mp4"       # path to your video file
BACKEND_URL = "http://localhost:8080/api/events"  # Spring Boot endpoint
SAVE_TO_FILE = False                 
# OUTPUT_FILE = "events.json"         # local output for Day 1 testing
FRAME_SKIP = 30                     # process every 15th frame (speeds things up)
OVERCROWD_THRESHOLD = 8            # alert if more than this many people detected
EMPTY_THRESH  = 0
BILLING_QUEUE_THRESH = 5       # alert if billing zone has > 5 people
# Store operating hours from CSV data (12:15 – 21:39)
STORE_OPEN  = "12:15:00"
STORE_CLOSE = "21:39:00"

# Video base date from dataset
VIDEO_DATE = "2026-04-10"

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

# def determine_alert(people_count):
    # """Return alert type based on people count."""
    # if people_count > OVERCROWD_THRESHOLD:
        # return "OVERCROWDING"
    # elif people_count == 0:
        # return "EMPTY_STORE"
    # else:
        # return None
    
def get_alert(people_count, zone):
    """Determine alert type based on count and zone."""
    if people_count > OVERCROWD_THRESHOLD:
        return "OVERCROWDING"
    if zone == "entrance" and people_count == EMPTY_THRESH:
        return "EMPTY_ENTRANCE"
    if zone == "billing" and people_count > BILLING_QUEUE_THRESH:
        return "LONG_QUEUE"
    return None

def build_event(camera_id, zone, people_count, frame_number, fps,  video_date):
    """Build the event JSON object."""
    # Calculate approximate timestamp in video
    video_seconds = frame_number / fps if fps > 0 else 0

    # Approximate wall-clock time based on frame position in the ~2min clip
    # We anchor CAM clips to store open time for realistic timestamps
    base_time = datetime.strptime(f"{video_date} {STORE_OPEN}", "%Y-%m-%d %H:%M:%S")
    wall_time  = base_time + timedelta(seconds=video_seconds)
 
    return {
        "cameraId":      camera_id,
        "zone":          zone,
        "peopleCount":   people_count,
        "timestamp":     wall_time.isoformat(),
        "videoTimestamp": round(video_seconds, 2),
        "frameNumber":   frame_number,
        "alert":         get_alert(people_count, zone)
    }

def send_to_backend(event):
    """POST event to Spring Boot backend."""
    try:
        response = requests.post(
            BACKEND_URL,
            json=event,
            headers={"Content-Type": "application/json"},
            timeout=3
        )
        status = "✓" if response.status_code in (200, 201) else f"✗ HTTP {response.status_code}"
        print(f"  {status} → backend")
    except requests.exceptions.ConnectionError:
        print("  ✗ Backend not running — skipping POST")
        

def process_camera(cam_config):
    """Process one camera file and return its events."""
    cam_id  = cam_config["id"]
    zone    = cam_config["zone"]
    fpath  = os.path.join(BASE_DIR, cam_config["file"])

    if not os.path.exists(fpath):
        print(f"  [SKIP] '{cam_config['file']}' not found — place .mp4 files next to detector.py")
        return []

    cap = cv2.VideoCapture(fpath)
    if not cap.isOpened():
        print(f"  [ERROR] Cannot open {fpath}")
        return []

    fps          = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s   = total_frames / fps

    print(f"\n{'─'*55}")
    print(f"  Camera : {cam_id}  Zone: {zone}")
    print(f"  File   : {cam_config['file']}")
    print(f"  Frames : {total_frames}  FPS: {fps:.1f}  Duration: {duration_s:.1f}s")
    print(f"  Sampling: every {FRAME_SKIP} frames (~{fps/FRAME_SKIP:.1f} checks/sec)")
    print(f"{'─'*55}")

    events       = []
    frame_number = 0
    max_count    = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_number % FRAME_SKIP == 0:
            count  = count_people(frame)
            event  = build_event(cam_id, zone, count, frame_number, fps, VIDEO_DATE)
            events.append(event)
            max_count = max(max_count, count)

            alert_str = f"  ⚠  {event['alert']}" if event["alert"] else ""
            print(f"  Frame {frame_number:5d} | {event['timestamp'][11:19]} | People: {count:3d}{alert_str}")

            if not SAVE_TO_FILE:
                send_to_backend(event)

        frame_number += 1

    cap.release()

    alerts = sum(1 for e in events if e["alert"])
    counts = [e["peopleCount"] for e in events]
    avg    = sum(counts) / len(counts) if counts else 0

    print(f"\n  ✓ {cam_id} done — {len(events)} events | max: {max_count} | avg: {avg:.1f} | alerts: {alerts}")
    return events


def compute_summary(all_events):
    """Compute store-level summary stats from all camera events."""
    if not all_events:
        return {}
 
    counts     = [e["peopleCount"] for e in all_events]
    all_alerts = [e for e in all_events if e["alert"]]
 
    # Footfall: cumulative peak counts at entrance camera
    # (each new "peak" above the rolling max = new person entered)
    entrance_events = [e for e in all_events if e["zone"] == "entrance"]
    visitor_estimate = _estimate_footfall(entrance_events)
 
    # Conversion rate: from CSV we know 21 unique buyers on April 10
    unique_buyers   = 21
    conversion_rate = round((unique_buyers / visitor_estimate * 100), 2) if visitor_estimate > 0 else 0
 
    return {
        "date":               VIDEO_DATE,
        "storeId":            "ST1008",
        "storeName":          "Brigade_Bangalore",
        "totalEvents":        len(all_events),
        "averagePeopleCount": round(sum(counts) / len(counts), 2),
        "maxPeopleCount":     max(counts),
        "totalAlerts":        len(all_alerts),
        "alertBreakdown":     _count_by_field(all_alerts, "alert"),
        "visitorEstimate":    visitor_estimate,
        "uniqueBuyers":       unique_buyers,
        "conversionRatePct":  conversion_rate,
        "cameraSummaries":    _camera_summaries(all_events),
        "generatedAt":        datetime.now().isoformat()
    }
 
 
def _estimate_footfall(entrance_events):
    """
    Estimate total people who entered by counting upward steps in people count.
    E.g. 0→2→3→1→4 = entries at frames where count rose: +2, +1, +1 = 4 entries.
    This is a heuristic — documented in CHOICES.md.
    """
    total_entries = 0
    prev = 0
    for e in entrance_events:
        curr = e["peopleCount"]
        if curr > prev:
            total_entries += (curr - prev)
        prev = curr
    # If no entrance camera data, fall back to max seen
    return total_entries if total_entries > 0 else max(
        (e["peopleCount"] for e in entrance_events), default=0
    )
 
 
def _count_by_field(events, field):
    counts = {}
    for e in events:
        val = e.get(field, "UNKNOWN")
        counts[val] = counts.get(val, 0) + 1
    return counts
 
 
def _camera_summaries(all_events):
    cams = {}
    for e in all_events:
        cid = e["cameraId"]
        if cid not in cams:
            cams[cid] = {"counts": [], "alerts": 0, "zone": e["zone"]}
        cams[cid]["counts"].append(e["peopleCount"])
        if e["alert"]:
            cams[cid]["alerts"] += 1
    result = {}
    for cid, data in cams.items():
        c = data["counts"]
        result[cid] = {
            "zone":     data["zone"],
            "events":   len(c),
            "maxCount": max(c),
            "avgCount": round(sum(c) / len(c), 2),
            "alerts":   data["alerts"]
        }
    return result
 
 
# ─── MAIN ─────────────────────────────────────────────────────────────────────
 
def main():
    print("=" * 55)
    print("  Purplle Store Intelligence — CCTV Processor")
    print(f"  Store: Brigade Road, Bangalore | {VIDEO_DATE}")
    print("=" * 55)
 
    all_events = []
    for cam in CAMERAS:
        events = process_camera(cam)
        all_events.extend(events)
 
    if not all_events:
        print("\n  No events generated — check that .mp4 files are present.")
        return
 
    summary = compute_summary(all_events)
 
    output = {
        "summary": summary,
        "events":  all_events
    }
 
    if SAVE_TO_FILE:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n{'='*55}")
        print(f"  ✓ {len(all_events)} total events saved → events.json")
        print(f"  Visitor estimate  : {summary.get('visitorEstimate', 'N/A')}")
        print(f"  Unique buyers     : {summary.get('uniqueBuyers', 21)}")
        print(f"  Conversion rate   : {summary.get('conversionRatePct', 0)}%")
        print(f"  Total alerts      : {summary.get('totalAlerts', 0)}")
        print("=" * 55)
    else:
        print(f"\n  ✓ All events POSTed to {BACKEND_URL}")
 
 
if __name__ == "__main__":
    main()






























































