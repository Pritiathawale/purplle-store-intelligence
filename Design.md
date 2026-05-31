# System Design — Purplle Store Intelligence System

## Overview

An end-to-end pipeline that processes raw CCTV footage from the Brigade Road, Bangalore Purplle store and produces real-time store analytics, footfall metrics, and conversion rate insights.

---

## Architecture

```
[CCTV Videos (.mp4)]
        ↓
[Python AI Service — detector.py]
  - YOLOv8n person detection
  - Per-camera event generation
  - Entry/exit heuristics
        ↓ POST /api/events (JSON)
[Java Spring Boot Backend]
  - REST API layer
  - Business logic (funnel, conversion, anomaly)
  - Persistence (PostgreSQL)
        ↓ GET /api/metrics, /api/funnel, /api/alerts
[React Dashboard]
  - Live footfall counter
  - Conversion rate display
  - Alerts feed
  - Hourly heatmap chart
```

---

## Components

### 1. Python AI Service (`ai-service/detector.py`)
- **Model**: YOLOv8n (nano) — chosen for speed on CPU hardware without GPU
- **Input**: One `.mp4` per camera zone, specified via `--camera` argument
- **Output**: Structured JSON event stream with per-frame people count, entry detection, bounding boxes, and alert classification
- **Camera zones supported**: `entrance`, `makeup_zone`, `skin_zone`, `billing`, `floor`
- **Entry counting**: Heuristic-based — count increases at entrance camera are treated as new entries. Acknowledged limitation documented in CHOICES.md.

### 2. Spring Boot Backend (`backend/`)
- **Framework**: Spring Boot 3, Java 17
- **Database**: PostgreSQL (via JPA/Hibernate)
- **Key endpoints**:
  - `POST /api/events` — ingest detection events from Python service
  - `GET /api/metrics` — footfall, conversion rate, avg dwell time
  - `GET /api/funnel` — entry → zone browse → billing → purchase funnel
  - `GET /api/alerts` — anomaly events (overcrowding, empty store, long queue)
  - `GET /api/analytics/hourly` — people count aggregated by hour
  - `GET /api/analytics/salesperson` — sales performance from transaction data

### 3. React Dashboard (`frontend/`)
- **Framework**: React 18, Recharts
- **Features**: Live count cards, hourly bar chart, alert table, conversion rate gauge

---

## Data Sources

| Source | File | Used For |
|---|---|---|
| CCTV footage | 5 × .mp4 files | Footfall counting, zone activity |
| Sales transactions | Brigade_Bangalore_10_April_26.csv | Conversion denominator (24 orders, 21 unique buyers) |
| Store layout | Brigade_Road_Store_Layout.xlsx | Camera zone identification |

---

## Key Metric: Conversion Rate

```
Conversion Rate = (Unique Buyers / Total Footfall) × 100

Unique Buyers   = from CSV: 21 unique customer_numbers on April 10, 2026
Total Footfall  = from CCTV: count of people entering via entrance camera
```

---

## Event Schema

```json
{
  "cameraId": "entrance",
  "timestamp": "2026-04-10T12:15:00",
  "peopleCount": 3,
  "entryCount": 2,
  "totalEntriesSoFar": 14,
  "alert": "OVERCROWDING",
  "detections": [
    { "bbox": [120.0, 45.0, 280.0, 410.0], "confidence": 0.87 }
  ]
}
```

---

## Deployment

```bash
docker compose up
```

Services: `ai-service` (Python), `backend` (Spring Boot + PostgreSQL), `frontend` (React)