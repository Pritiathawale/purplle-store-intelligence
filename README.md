# Purplle Store Intelligence System
**Tech Challenge 2026 — Brigade Road, Bangalore (Store ST1008)**

End-to-end retail analytics pipeline: raw CCTV footage → AI detection → REST API → live dashboard.

---

## Quick Start (5 commands)

```bash
git clone https://github.com/Pritiathawale/purplle-store-intelligence
cd purplle-store-intelligence
cd ai-service && pip install -r requirements.txt && python detector.py
cd ..
docker compose up
```

Dashboard: http://localhost:3000  
API: http://localhost:8080

---

## Running the Detection Pipeline

Place the 5 camera .mp4 files in `ai-service/`:
```
ai-service/CAM 1.mp4   → makeup_zone
ai-service/CAM 2.mp4   → skin_zone
ai-service/CAM 3.mp4   → entrance
ai-service/CAM 4.mp4   → floor
ai-service/CAM 5.mp4   → billing
```

Run the detector (saves events to events.json):
```bash
cd ai-service
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
python detector.py
```

To stream events to the running API instead:
```bash
# Change SAVE_TO_FILE = False in detector.py, then:
python detector.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /events/ingest | Ingest events batch (up to 500) |
| GET | /stores/{id}/metrics | Footfall, conversion rate, dwell |
| GET | /stores/{id}/funnel | 4-stage conversion funnel |
| GET | /stores/{id}/anomalies | Queue spikes, dead zones, alerts |
| GET | /stores/{id}/heatmap | Zone activity 0–100 score |
| GET | /health | Service health + stale feed check |

**Store ID for this dataset:** `ST1008`

Example:
```bash
curl http://localhost:8080/stores/ST1008/metrics
curl http://localhost:8080/stores/ST1008/funnel
curl http://localhost:8080/stores/ST1008/anomalies
curl http://localhost:8080/health
```

---

## Architecture

```
CCTV Videos (.mp4)
      ↓
Python AI Service (YOLOv8n + OpenCV)
  - Person detection per frame
  - Entry/exit counting at entrance camera
  - Zone activity per department camera
  - Alert generation (overcrowding, queue)
      ↓ POST /events/ingest
Java Spring Boot API
  - Event ingestion with idempotency
  - Real-time metrics computation
  - Funnel + session analytics
  - Anomaly detection
      ↓
React Dashboard (localhost:3000)
  - Live metric cards
  - Hourly chart, funnel, zone heatmap
  - Alert feed
```

---

## Dataset

| File | Description |
|------|-------------|
| CAM 1–5.mp4 | CCTV footage: makeup, skin, entrance, floor, billing |
| POS_sample_transactions.csv | 101 transactions, store ST1008, April 10 2026 |
| sample_events.jsonl | 13 reference events for schema validation |
| Store_1_layout.png | Floor plan — F.O.H zones, cash counter location |

---

## Tech Stack

- **Detection**: Python 3.11, YOLOv8n (ultralytics), OpenCV
- **Backend**: Java 17, Spring Boot 3.2.5, Spring Data JPA
- **Database**:  Supabase PostgreSQL (prod)
- **Frontend**: React 18, Recharts, Axios
- **Container**: Docker + docker compose

---

## Design Decisions

See [DESIGN.md](./DESIGN.md) and [CHOICES.md](./CHOICES.md) for full reasoning.