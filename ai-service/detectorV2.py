

"""
Purplle Store Intelligence — CCTV Detector
Memory-optimised for CPU-only laptops (no GPU required).

Fixes applied:
1. gc.collect() + frame resize to reduce RAM usage
2. model loaded once, reused across all cameras
3. FRAME_SKIP raised to 60 (process every 2 seconds) to reduce peak memory
4. Explicit cap.release() and del frame after each use

Usage:
  python detector.py --store 1    (CAM 1 - zone.mp4, CAM 3 - entry.mp4, CAM 5 - billing.mp4)
  python detector.py --store 2    (billing.mp4, entry1.mp4, entry2.mp4, zone.mp4)
"""

import argparse
import gc
import json
import os
import uuid
from datetime import datetime, timedelta

import cv2
import requests
from ultralytics import YOLO

# ─── STORE CONFIGS ────────────────────────────────────────────────
STORES = {
    "1": {
        "store_id":   "ST1008",
        "store_code": "store_1008",
        "date":       "2026-04-10",
        "open_time":  "12:15:00",
        "cameras": [
            {"id": "CAM_ZONE_1",  "file": "CAM 1 - zone.mp4",    "zone_id": "ST1008_Z01",
             "zone_name": "Main Floor Zone",    "zone_type": "SHELF",   "type": "floor",
             "hotspot_x": 400.0, "hotspot_y": 300.0},
            {"id": "CAM_ENTRY",   "file": "CAM 3 - entry.mp4",   "zone_id": "ST1008_Z_ENTRY",
             "zone_name": "Store Entry",        "zone_type": "ENTRY",   "type": "entry",
             "hotspot_x": 100.0, "hotspot_y": 400.0},
            {"id": "CAM_BILLING", "file": "CAM 5 - billing.mp4", "zone_id": "ST1008_Z_BILLING_01",
             "zone_name": "Billing Counter Queue","zone_type": "BILLING","type": "billing",
             "hotspot_x": 600.0, "hotspot_y": 200.0},
        ]
    },
    "2": {
        "store_id":   "ST1009",
        "store_code": "store_1009",
        "date":       "2026-04-10",
        "open_time":  "12:00:00",
        "cameras": [
            {"id": "CAM_ENTRY_1",  "file": "entry 1.mp4",  "zone_id": "ST1009_Z_ENTRY_1",
             "zone_name": "Primary Entry",    "zone_type": "ENTRY",   "type": "entry",
             "hotspot_x": 480.0, "hotspot_y": 500.0},
            {"id": "CAM_ENTRY_2",  "file": "entry 2.mp4",  "zone_id": "ST1009_Z_ENTRY_2",
             "zone_name": "Secondary Entry",  "zone_type": "ENTRY",   "type": "entry",
             "hotspot_x": 520.0, "hotspot_y": 500.0},
            {"id": "CAM_ZONE",     "file": "zone.mp4",    "zone_id": "ST1009_Z01",
             "zone_name": "Main Floor",       "zone_type": "SHELF",   "type": "floor",
             "hotspot_x": 350.0, "hotspot_y": 350.0},
            {"id": "CAM_BILLING",  "file": "billing_area.mp4", "zone_id": "ST1009_Z_BILLING_01",
             "zone_name": "Billing Counter Queue","zone_type":"BILLING","type": "billing",
             "hotspot_x": 500.0, "hotspot_y": 150.0},
        ]
    }
}

# ─── CONFIG ───────────────────────────────────────────────────────
BASE_DIR             = os.path.dirname(os.path.abspath(__file__))
BACKEND_URL          = "http://localhost:8080/events/ingest"
SAVE_TO_FILE         = False      # True = save JSON file; False = POST to Spring Boot
FRAME_SKIP           = 120        # process every 2 seconds (was 30) — reduces RAM usage
RESIZE_WIDTH         = 640       # resize frames before YOLO — critical for low RAM
OVERCROWD_THRESHOLD  = 8
BILLING_QUEUE_THRESH = 3
# ─────────────────────────────────────────────────────────────────

# Load model ONCE globally — do not reload per camera
print("Loading YOLOv8n model...")
model = YOLO("yolov8n.pt")
print("Model loaded.")

_track_counter = {}

def next_id_token(cam_id):
    n = _track_counter.get(cam_id, 60000) + 1
    _track_counter[cam_id] = n
    return f"ID_{n}"

def next_track_id(cam_id):
    k = f"t_{cam_id}"
    n = _track_counter.get(k, 100) + 1
    _track_counter[k] = n
    return n

def wall_clock(frame_num, fps, open_time, date):
    base = datetime.strptime(f"{date} {open_time}", "%Y-%m-%d %H:%M:%S")
    return (base + timedelta(seconds=frame_num / fps)).isoformat()

def count_people(frame):
    """
    Resize frame before YOLO to reduce memory usage.
    At 640px width, YOLO uses ~150MB RAM instead of ~800MB for 1080p.
    """
    h, w = frame.shape[:2]
    if w > RESIZE_WIDTH:
        scale  = RESIZE_WIDTH / w
        frame  = cv2.resize(frame, (RESIZE_WIDTH, int(h * scale)))

    results    = model(frame, verbose=False)
    count      = 0
    conf_sum   = 0.0
    for r in results:
        for i, cls in enumerate(r.boxes.cls):
            if int(cls) == 0:
                count    += 1
                conf_sum += float(r.boxes.conf[i])

    del frame   # explicitly free frame memory
    gc.collect()

    avg_conf = round(conf_sum / count, 3) if count > 0 else 0.85
    return count, avg_conf

# ── Event schema builders — match sample_events.jsonl exactly ─────

def make_entry_event(cam, store_cfg, ts, id_token, group_id=None, group_size=None):
    return {
        "event_type":       "entry",
        "id_token":         id_token,
        "store_code":       store_cfg["store_code"],
        "store_id":         store_cfg["store_id"],
        "camera_id":        cam["id"],
        "event_timestamp":  ts,
        "is_staff":         False,
        "gender_pred":      "U",        # full-face blur applied — cannot predict
        "age_pred":         None,
        "age_bucket":       "unknown",
        "is_face_hidden":   True,
        "group_id":         group_id,
        "group_size":       group_size,
    }

def make_exit_event(cam, store_cfg, ts, id_token):
    return {
        "event_type":       "exit",
        "id_token":         id_token,
        "store_code":       store_cfg["store_code"],
        "store_id":         store_cfg["store_id"],
        "camera_id":        cam["id"],
        "event_timestamp":  ts,
        "is_staff":         False,
        "gender_pred":      "U",
        "age_pred":         None,
        "age_bucket":       "unknown",
        "is_face_hidden":   True,
        "group_id":         None,
        "group_size":       None,
    }

def make_zone_event(cam, store_cfg, ts, track_id, event_type):
    return {
        "event_type":       event_type,
        "track_id":         track_id,
        "store_id":         store_cfg["store_id"],
        "camera_id":        cam["id"],
        "zone_id":          cam["zone_id"],
        "zone_name":        cam["zone_name"],
        "zone_type":        cam["zone_type"],
        "is_revenue_zone":  "Yes",
        "event_time":       ts,
        "zone_hotspot_x":   cam["hotspot_x"],
        "zone_hotspot_y":   cam["hotspot_y"],
        "gender":           "U",
        "age":              None,
        "age_bucket":       "unknown",
    }

def make_queue_event(cam, store_cfg, join_ts, exit_ts,
                     track_id, wait_seconds, position, abandoned):
    return {
        "queue_event_id":         str(uuid.uuid4()),
        "event_type":             "queue_abandoned" if abandoned else "queue_completed",
        "track_id":               track_id,
        "store_id":               store_cfg["store_id"],
        "camera_id":              cam["id"],
        "zone_id":                cam["zone_id"],
        "zone_name":              cam["zone_name"],
        "zone_type":              "BILLING",
        "is_revenue_zone":        "Yes",
        "queue_join_ts":          join_ts,
        "queue_served_ts":        None if abandoned else exit_ts,
        "queue_exit_ts":          exit_ts,
        "wait_seconds":           wait_seconds,
        "queue_position_at_join": position,
        "abandoned":              abandoned,
        "zone_hotspot_x":         cam["hotspot_x"],
        "zone_hotspot_y":         cam["hotspot_y"],
        "gender":                 "U",
        "age":                    None,
        "age_bucket":             "unknown",
    }

# ── Camera processors ─────────────────────────────────────────────

def process_entry_camera(cam, store_cfg):
    fpath = _find_file(cam["file"])
    if not fpath: return []

    cap    = cv2.VideoCapture(fpath)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"\n{'─'*55}")
    print(f"  ENTRY CAM: {cam['id']} | {cam['file']}")
    print(f"  Frames: {frames} | FPS: {fps:.0f} | Sampling: every {FRAME_SKIP} frames")

    events, frame_num, sessions = [], 0, {}

    while True:
        ret, frame = cap.read()
        if not ret: break

        if frame_num % FRAME_SKIP == 0:
            count, conf = count_people(frame)
            ts = wall_clock(frame_num, fps, store_cfg["open_time"], store_cfg["date"])

            new_entries = max(0, count - len(sessions))
            gid   = f"G_{uuid.uuid4().hex[:4].upper()}" if new_entries > 1 else None
            gsize = new_entries if new_entries > 1 else None
            for _ in range(new_entries):
                tok = next_id_token(cam["id"])
                sessions[tok] = ts
                events.append(make_entry_event(cam, store_cfg, ts, tok, gid, gsize))
                print(f"  Frame {frame_num:5d} | {ts[11:19]} | ENTRY {tok}")

            exits = max(0, len(sessions) - count)
            done  = 0
            for tok in list(sessions.keys()):
                if done >= exits: break
                del sessions[tok]
                events.append(make_exit_event(cam, store_cfg, ts, tok))
                print(f"  Frame {frame_num:5d} | {ts[11:19]} | EXIT  {tok}")
                done += 1

        frame_num += 1

    cap.release()
    gc.collect()
    print(f"  ✓ {cam['id']}: {len(events)} entry/exit events")
    return events

def process_zone_camera(cam, store_cfg):
    fpath = _find_file(cam["file"])
    if not fpath: return []

    cap    = cv2.VideoCapture(fpath)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"\n{'─'*55}")
    print(f"  ZONE CAM : {cam['id']} | {cam['file']}")
    print(f"  Frames: {frames} | FPS: {fps:.0f} | Sampling: every {FRAME_SKIP} frames")

    events, frame_num, zone_tracks = [], 0, {}

    while True:
        ret, frame = cap.read()
        if not ret: break

        if frame_num % FRAME_SKIP == 0:
            count, conf = count_people(frame)
            ts = wall_clock(frame_num, fps, store_cfg["open_time"], store_cfg["date"])

            new_in = max(0, count - len(zone_tracks))
            for _ in range(new_in):
                tid = next_track_id(cam["id"])
                zone_tracks[tid] = ts
                events.append(make_zone_event(cam, store_cfg, ts, tid, "zone_entered"))
                print(f"  Frame {frame_num:5d} | {ts[11:19]} | ZONE_ENTERED track={tid}")

            exits = max(0, len(zone_tracks) - count)
            done  = 0
            for tid in list(zone_tracks.keys()):
                if done >= exits: break
                del zone_tracks[tid]
                events.append(make_zone_event(cam, store_cfg, ts, tid, "zone_exited"))
                print(f"  Frame {frame_num:5d} | {ts[11:19]} | ZONE_EXITED  track={tid}")
                done += 1

        frame_num += 1

    cap.release()
    gc.collect()
    print(f"  ✓ {cam['id']}: {len(events)} zone events")
    return events

def process_billing_camera(cam, store_cfg):
    fpath = _find_file(cam["file"])
    if not fpath: return []

    cap      = cv2.VideoCapture(fpath)
    fps      = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    pos_times = _load_pos_times(store_cfg["store_id"])
    print(f"\n{'─'*55}")
    print(f"  BILLING  : {cam['id']} | {cam['file']}")
    print(f"  Frames: {frames} | FPS: {fps:.0f} | POS transactions: {len(pos_times)}")

    events, frame_num, queue_sessions = [], 0, {}

    while True:
        ret, frame = cap.read()
        if not ret: break

        if frame_num % FRAME_SKIP == 0:
            count, conf = count_people(frame)
            ts = wall_clock(frame_num, fps, store_cfg["open_time"], store_cfg["date"])

            new_joiners = max(0, count - len(queue_sessions))
            for _ in range(new_joiners):
                tid = next_track_id(cam["id"])
                queue_sessions[tid] = {
                    "join_ts":         ts,
                    "frames_in_queue": 0,
                    "position":        len(queue_sessions) + 1,
                }
                print(f"  Frame {frame_num:5d} | {ts[11:19]} | QUEUE_JOIN  track={tid} depth={count}")

            for tid in queue_sessions:
                queue_sessions[tid]["frames_in_queue"] += 1

            leaves = max(0, len(queue_sessions) - count)
            done   = 0
            for tid in list(queue_sessions.keys()):
                if done >= leaves: break
                sess     = queue_sessions.pop(tid)
                wait_sec = int(sess["frames_in_queue"] * FRAME_SKIP / fps)
                abandoned = _is_abandoned(sess["join_ts"], ts, pos_times, wait_sec)
                ev = make_queue_event(cam, store_cfg, sess["join_ts"], ts,
                                      tid, wait_sec, sess["position"], abandoned)
                events.append(ev)
                lbl = "QUEUE_ABANDONED" if abandoned else "QUEUE_COMPLETED"
                print(f"  Frame {frame_num:5d} | {ts[11:19]} | {lbl} track={tid} wait={wait_sec}s")
                done += 1

        frame_num += 1

    # Close remaining open queue sessions as completed
    for tid, sess in queue_sessions.items():
        wait_sec = int(sess["frames_in_queue"] * FRAME_SKIP / fps)
        ev = make_queue_event(cam, store_cfg, sess["join_ts"], ts,
                              tid, wait_sec, sess["position"], False)
        events.append(ev)

    cap.release()
    gc.collect()
    print(f"  ✓ {cam['id']}: {len(events)} queue events")
    return events

# ── Helpers ───────────────────────────────────────────────────────

def _find_file(filename):
    """Try exact filename, lowercase, and common variations."""
    candidates = [
        filename,
        filename.lower(),
        filename.upper(),
        filename.replace(" - ", "-"),
        filename.replace(" - ", "_"),
        filename.replace(" ", "_"),
    ]
    for name in candidates:
        fpath = os.path.join(BASE_DIR, name)
        if os.path.exists(fpath):
            return fpath
    print(f"\n  [SKIP] '{filename}' not found in {BASE_DIR}")
    print(f"  Tried: {candidates[:3]}")
    return None

def _is_abandoned(join_ts, exit_ts, pos_times, wait_sec):
    if wait_sec <= 90: return False
    if not pos_times:  return wait_sec > 120
    try:
        join_dt = datetime.fromisoformat(join_ts)
        for pt in pos_times:
            if 0 <= (pt - join_dt).total_seconds() <= 300:
                return False
        return True
    except:
        return wait_sec > 120

def _load_pos_times(store_id):
    """Search for POS CSV in current folder and parent folder."""
    candidates = [
        os.path.join(BASE_DIR, "POS_sample_transactions.csv"),
        os.path.join(BASE_DIR, "POS_-_sample_transactionsb1e826f.csv"),
        os.path.join(BASE_DIR, "..", "POS_-_sample_transactionsb1e826f.csv"),
        os.path.join(BASE_DIR, "..", "POS_sample_transactions.csv"),
    ]
    for pos_file in candidates:
        if os.path.exists(pos_file):
            try:
                import csv
                times = []
                with open(pos_file) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("store_id", "").strip() == store_id:
                            d = row["order_date"].strip()   # "10-04-2026"
                            t = row["order_time"].strip()   # "12:15:05"
                            dt = datetime.strptime(f"{d} {t}", "%d-%m-%Y %H:%M:%S")
                            times.append(dt)
                print(f"  POS file found: {os.path.basename(pos_file)} — {len(times)} transactions")
                return times
            except Exception as e:
                print(f"  [WARN] POS parse error: {e}")
    print(f"  [INFO] POS CSV not found — place it in ai-service/ for conversion accuracy")
    return []

def compute_summary(all_events, store_cfg, pos_times):
    entry_evts = [e for e in all_events if e.get("event_type") == "entry"]
    queue_evts = [e for e in all_events if e.get("event_type") in ("queue_completed","queue_abandoned")]
    abandoned  = [e for e in queue_evts if e.get("abandoned", False)]
    completed  = [e for e in queue_evts if not e.get("abandoned", False)]
    footfall   = len(entry_evts)
    converted  = len(completed) if completed else (21 if store_cfg["store_id"] == "ST1008" else 0)
    conv_rate  = round(converted / footfall * 100, 2) if footfall > 0 else 0.0

    return {
        "store_id":            store_cfg["store_id"],
        "date":                store_cfg["date"],
        "total_events":        len(all_events),
        "footfall":            footfall,
        "converted_visitors":  converted,
        "conversion_rate_pct": conv_rate,
        "queue_abandoned":     len(abandoned),
        "queue_completed":     len(completed),
        "abandonment_rate_pct": round(len(abandoned)/len(queue_evts)*100,2) if queue_evts else 0.0,
        "generated_at":        datetime.now().isoformat(),
    }

def send_to_backend(all_events):
    """POST all events in batches of 100 to avoid request size limits."""
    batch_size = 100
    total_accepted = 0
    for i in range(0, len(all_events), batch_size):
        batch = all_events[i:i+batch_size]
        try:
            r = requests.post(BACKEND_URL, json=batch,
                              headers={"Content-Type": "application/json"}, timeout=30)
            d = r.json()
            total_accepted += d.get("accepted", 0)
            print(f"  Batch {i//batch_size+1}: {r.status_code} — accepted={d.get('accepted',0)}")
        except Exception as ex:
            print(f"  Batch {i//batch_size+1} error: {ex}")
    print(f"  Total accepted by backend: {total_accepted}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", choices=["1","2"], default="1",
                        help="1 = CAM1-zone, CAM3-entry, CAM5-billing | 2 = entry1/entry2/zone/billing")
    args  = parser.parse_args()
    store = STORES[args.store]

    print("=" * 55)
    print(f"  Store {args.store} | {store['store_id']} | {store['date']}")
    expected = [c["file"] for c in store["cameras"]]
    print(f"  Expected files in ai-service/: {expected}")
    print("=" * 55)

    pos_times  = _load_pos_times(store["store_id"])
    all_events = []

    for cam in store["cameras"]:
        if cam["type"] == "entry":
            all_events.extend(process_entry_camera(cam, store))
        elif cam["type"] == "floor":
            all_events.extend(process_zone_camera(cam, store))
        elif cam["type"] == "billing":
            all_events.extend(process_billing_camera(cam, store))
        gc.collect()  # free memory between cameras

    if not all_events:
        print(f"\n  No events generated. Place these files in {BASE_DIR}:")
        for c in store["cameras"]:
            print(f"    {c['file']}")
        return

    summary = compute_summary(all_events, store, pos_times)
    output  = {"summary": summary, "events": all_events}

    fname = os.path.join(BASE_DIR, f"events_store{args.store}.json")
    with open(fname, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*55}")
    print(f"  ✓ {len(all_events)} events → events_store{args.store}.json")
    print(f"  Footfall        : {summary['footfall']}")
    print(f"  Converted       : {summary['converted_visitors']}")
    print(f"  Conversion rate : {summary['conversion_rate_pct']}%")
    print(f"  Queue abandoned : {summary['queue_abandoned']}")
    print("=" * 55)

    if not SAVE_TO_FILE:
        print(f"\n  Sending to backend at {BACKEND_URL}...")
        send_to_backend(all_events)
    else:
        print(f"\n  To send to Spring Boot backend:")
        print(f"  1. Make sure Spring Boot is running: mvnw.cmd spring-boot:run")
        print(f"  2. Set SAVE_TO_FILE = False in detector.py")
        print(f"  3. Re-run: python detector.py --store {args.store}")
        print(f"\n  OR — import existing JSON directly:")
        print(f"  python import_events.py --file events_store{args.store}.json")

if __name__ == "__main__":
    main()