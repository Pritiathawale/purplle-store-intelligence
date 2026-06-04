# Engineering Choices — Purplle Store Intelligence System

## Decision 1: Detection Model — YOLOv8n

**Options considered**: YOLOv8n (nano), YOLOv8m (medium), YOLOv8l (large), RT-DETR, MediaPipe Pose

**What AI suggested**: Claude recommended YOLOv8m for better handling of partial occlusion in crowded billing scenarios, citing ~5% mAP improvement over nano on COCO person class.

**What I chose**: YOLOv8n (nano)

**Why**: The challenge runs on a student laptop without a GPU. Processing times matter:
- YOLOv8n: ~80ms/frame on CPU
- YOLOv8m: ~400ms/frame on CPU
- YOLOv8l: ~800ms/frame on CPU

At 30fps with FRAME_SKIP=30 (1 sample/sec), a 20-minute clip has ~1200 frames to process.
- Nano: ~96 seconds per camera = ~6 minutes for 4 cameras
- Medium: ~480 seconds = ~32 minutes for 4 cameras

For a hackathon submission where I need to demo the full pipeline, nano is the only practical choice. In a production deployment with GPU inference (typical retail CCTV systems use NVIDIA T4), I would upgrade to YOLOv8m or RT-DETR.

**Trade-off accepted**: ~5% lower detection accuracy on partial occlusion. Mitigated by: (1) retail store people counts are low (2-15 persons), so absolute error is small; (2) confidence scores are included in every event — evaluators can see degraded confidence rather than suppressed events.

---

## Decision 2: Event Schema Design

**Options considered**:
1. Minimal schema (just event_type + timestamp + count)
2. Full schema matching sample_events.jsonl exactly
3. Extended schema with additional fields (age_pred, gender_pred, group_id)

**What AI suggested**: Claude suggested the extended schema (option 3) matching the full sample_events.jsonl including gender_pred and age_pred from a hypothetical face analysis model.

**What I chose**: Option 2 — full schema matching sample_events.jsonl, without the demographic inference fields

**Why**: The videos have full-face blur applied (stated in the problem). Any age/gender prediction on blurred faces would produce meaningless noise with near-random confidence. Including these fields with fabricated values would be dishonest and would fail schema validation if the harness checks confidence calibration. I implemented the fields that can be derived from YOLOv8 detection (bounding box position → zone_hotspot_x/y, detection confidence, person count for queue_depth) and excluded fields that require face analysis.

**Schema decisions**:
- `event_id`: uuid-v4, generated at emit time — globally unique, enables idempotency
- `visitor_id`: VIS_{6-char hex} — short enough to read in logs, unique per session
- `dwell_ms`: tracked in SessionTracker, accumulated from frame sampling intervals
- `session_seq`: ordinal position within a visitor's session — helps detect Re-ID failures
- `metadata.queue_depth`: populated only for BILLING_QUEUE_JOIN events

---

## Decision 3: API Backend — Java Spring Boot vs Python FastAPI

**Options considered**:
1. Python FastAPI (problem statement suggested layout uses this)
2. Java Spring Boot (my primary backend framework)
3. Node.js Express

**What AI suggested**: Claude recommended FastAPI for consistency with the Python detection pipeline, lower deployment complexity (one language), and the scoring harness having "best coverage for FastAPI" (quoted from the problem statement FAQ).

**What I chose**: Java Spring Boot 3.2.5

**Why**: I disagreed with the AI suggestion on this one. My reasoning:

1. **Familiarity**: I can debug Spring Boot JPA issues faster than Python SQLAlchemy edge cases. Under time pressure, framework familiarity is more valuable than theoretical consistency.

2. **The scoring harness is language-agnostic**: The FAQ explicitly states "Go and Node.js are acceptable." The FastAPI preference is a suggestion, not a requirement. The harness calls REST endpoints — it doesn't care what generated the JSON.

3. **JPA type safety**: Spring Data JPA gives compile-time query validation. A typo in a JPQL query fails at startup, not at runtime during evaluation. This matters for a submission I can't iterate on after the deadline.

**Trade-off accepted**: Two-language codebase (Python for detection, Java for API). Mitigated by clear separation — the Python script only POSTs JSON to an HTTP endpoint. There is no shared code or FFI boundary.

**Where AI was right**: Claude was correct that FastAPI would have been faster to prototype. If I were doing this again with a week of runway, I would use FastAPI for a single-language stack. The Spring Boot choice was pragmatic for the constraint of a 4-day window.

---

## Decision 4: Storage — H2 In-Memory vs PostgreSQL

**Options considered**: H2 (in-memory), SQLite (file), Supabase PostgreSQL, local PostgreSQL

**What I chose**: H2 in-memory as default, Supabase PostgreSQL as configurable option

**Why H2 as default**: The acceptance gate requires `docker compose up` to start the API with no manual steps. If I set PostgreSQL as the default, evaluators need to either have a local PostgreSQL or wait for Supabase to be provisioned. H2 starts instantly inside the JVM with zero configuration. For the 20-minute demo clip scenario, the data volume (a few thousand events) fits easily in memory.

**Why Supabase as option**: For a live demo where data must survive API restarts, Supabase gives a free hosted PostgreSQL. Switch is one `application.properties` change — no code changes needed.

**Limitation**: H2 data is lost on restart. This means re-running detector.py after restarting Spring Boot. Documented in README.