# System Design — Purplle Store Intelligence System
> Tech Challenge 2026 | Brigade Road, Bangalore

## Architecture Overview

```
Store 1 CCTV (4 cameras)          Store 2 CCTV (4 cameras)
Zone/Zone/Entry/Billing    ←→     billing/entry1/entry2/zone
           ↓
   Python Detection Pipeline (detector.py)
   YOLOv8n | Session Tracker | Event Emitter
   Outputs structured JSON events per schema
           ↓ POST /events/ingest (batch, idempotent)
   Java Spring Boot API (port 8080)
   ├── Ingestion layer    (dedup by event_id)
   ├── Metrics engine     (footfall, conversion, dwell)
   ├── Funnel logic       (session-based, no double count)
   ├── Anomaly detection  (queue spike, dead zone, conversion drop)
   └── Heatmap            (zone frequency, normalised 0-100)
           ↓
   React Dashboard (port 3000)
   Live cards | Hourly chart | Funnel | Zone heatmap | Alert feed
           ↓
    Supabase PostgreSQL
```

## Components

### 1. Detection Pipeline (`ai-service/detector.py`)
- **Model**: YOLOv8n (nano) — chosen for CPU inference speed
- **Frame sampling**: Every 30th frame (~1/sec at 30fps). Retail people counts change slowly; 2fps resolution captures all meaningful entry/exit events
- **Session tracker**: Per-camera visitor session management. Count increases → new ENTRY events with unique visitor_id. Count decreases → EXIT events. 30-second continuous presence → ZONE_DWELL event
- **Event schema**: Every event has `event_id` (uuid-v4), `visitor_id` (VIS_xxxxx), `dwell_ms`, `confidence`, `session_seq`, `metadata`
- **Billing zone**: Entry events become `BILLING_QUEUE_JOIN` when queue_depth > 1

### 2. Spring Boot API (`backend/`)
- **Framework**: Spring Boot 3.2.5, Java 17
- **Endpoints**: POST /events/ingest, GET /stores/{id}/metrics, GET /stores/{id}/funnel, GET /stores/{id}/heatmap, GET /stores/{id}/anomalies, GET /health
- **Idempotency**: Deduplication by event_id — same UUID submitted twice is stored once
- **POS correlation**: Conversion rate uses time-window matching — visitors in billing zone 5 minutes before a POS transaction timestamp = converted visitors

### 3. Database
- **Default**: H2 in-memory (works without any setup for docker compose)
- **Production**: Supabase PostgreSQL (switch via application.properties)
- **Why H2 for default**: No external dependency, zero-config docker setup, evaluators can run docker compose up without database credentials

### 4. React Dashboard (`frontend/`)
- React 18, Recharts for charts, Axios for API calls
- Auto-refreshes every 15 seconds
- Shows: 8 metric cards, hourly people count bar chart, conversion funnel with drop-off %, zone activity grid, anomaly alerts table, live events feed

## Event Schema Design

Events follow the sample_events.jsonl schema exactly:
```json
{
  "event_id":   "uuid-v4",
  "store_id":   "ST1008",
  "camera_id":  "CAM_ENTRY",
  "visitor_id": "VIS_A1B2C3",
  "event_type": "ENTRY",
  "timestamp":  "2026-04-10T12:30:00Z",
  "zone_id":    null,
  "dwell_ms":   0,
  "is_staff":   false,
  "confidence": 0.88,
  "metadata": {
    "queue_depth": null,
    "sku_zone": null,
    "session_seq": 1
  }
}
```

## Key Business Metric

```
Conversion Rate = Unique Buyers ÷ Total Footfall × 100

- Footfall: count of ENTRY events from entrance camera (is_staff=false)
- Unique Buyers: visitors whose visitor_id appeared in billing zone
  within 5 minutes before a POS transaction timestamp
- Source: POS CSV (ST1008, 24 transactions, April 10 2026)
```

## Known Limitations Documented

| Limitation | Impact | Mitigation |
|---|---|---|
| No cross-camera Re-ID | Same person at entry + zone gets two visitor_ids | Documented in CHOICES.md; would use torchreid OSNet in production |
| Staff detection heuristic | is_staff=false for all; staff uniforms not detected | Frame rate and zone patterns could filter staff in production |
| Re-entry counting | Person who exits and re-enters counted as new visitor | REENTRY event type not implemented — acknowledged trade-off |
| Frame sampling at 1fps | Fast movements (sprint through door) may be missed | Acceptable for retail context; customers don't sprint |

---

## AI-Assisted Decisions

### Decision 1 — Detection model selection
I asked Claude to evaluate YOLOv8n vs YOLOv8m vs RT-DETR for person detection on CPU hardware in a retail setting. Claude's recommendation was YOLOv8m for better accuracy on partial occlusion (billing queue scenarios). **I overrode this** and chose YOLOv8n because the challenge runs on a student laptop without GPU. At FRAME_SKIP=30, the bottleneck is not model accuracy but processing speed — nano model processes a frame in ~80ms on CPU vs ~400ms for medium. For a 20-minute clip at 30fps that's the difference between 2 hours and 10 hours of processing time. The accuracy trade-off is acceptable given the evaluation context.

### Decision 2 — Session tracking approach
I asked Claude to suggest a visitor tracking approach without GPU. Claude suggested ByteTrack with bounding box trajectory. **I partially overrode this**: I implemented a simpler count-differential tracker (count goes up → new session, count goes down → session closes) rather than full ByteTrack. My reasoning: ByteTrack requires storing per-frame bounding boxes and running the Hungarian algorithm for assignment — significant complexity for a CPU-only pipeline. The count-differential approach produces the same ENTRY/EXIT event count with less code and no additional dependencies. The main thing it cannot do is Re-ID (detecting the same person after re-entry) — I documented this as a known limitation.

### Decision 3 — Java Spring Boot vs Python FastAPI
The problem statement suggests Python FastAPI. I asked Claude to compare FastAPI vs Spring Boot for this use case. Claude recommended FastAPI for consistency with the Python detection pipeline and the scoring harness. **I kept Spring Boot** because it is my strongest backend framework — I can debug it faster, understand the JPA model, and write reliable tests. The scoring harness works with any REST API; the FastAPI preference is not a hard requirement. I noted in CHOICES.md that this is a deliberate trade-off: familiarity over framework alignment.