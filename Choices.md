# Engineering Choices & Trade-offs — Purplle Store Intelligence System

## 1. Model Choice: YOLOv8n over larger YOLO variants

**Decision**: Use YOLOv8 nano (`yolov8n.pt`) instead of YOLOv8m or YOLOv8l.

**Reasoning**:
- Challenge runs on laptop hardware without GPU
- Nano model processes frames at ~15–20 FPS on CPU vs ~1–2 FPS for larger variants
- For retail store density (typically 2–15 people in frame), nano accuracy is sufficient
- Larger model would have caused processing timeouts on 5 concurrent video files

**Trade-off accepted**: ~5% lower detection accuracy vs nano in crowded scenes. Mitigated by processing at 2 frames/second (FRAME_SKIP=15 at 30fps), which still captures all meaningful in-store events.

---

## 2. Entry Detection: Heuristic vs Centroid Tracking

**Decision**: Use count-increase heuristic at entrance camera instead of full centroid tracking with boundary line crossing.

**Reasoning**:
- Full centroid tracking requires DeepSORT or ByteTrack — additional complexity with diminishing accuracy returns for single-camera retail use
- Count-increase at the entrance camera (people_count[t] - people_count[t-1] > 0) provides a reasonable footfall estimate without tracking identity
- This aligns with how most retail footfall sensors (IR beam counters) work in practice

**Trade-off accepted**: Over-counts if multiple people enter simultaneously. Under-counts if someone immediately exits and re-enters. Documented for reviewer transparency.

**Production path**: Would implement ByteTrack for ID-persistent tracking + virtual entry/exit line to resolve double-counting.

---

## 3. Architecture: Separate Python service vs integrated Java CV

**Decision**: Computer vision runs as an isolated Python script, separate from the Spring Boot backend.

**Reasoning**:
- YOLOv8 and OpenCV are Python-native; Java CV libraries (JavaCV, DL4J) have limited YOLO support
- This separation is common in production systems (ML inference service + application backend)
- Allows independent scaling: CV processing can be run on a GPU node while the API layer runs on standard compute

**Trade-off accepted**: Two-process architecture instead of one monolith. Mitigated by simple REST communication between the services.

---

## 4. Re-entry Handling

**Decision**: Acknowledge re-entry as a known limitation; do not implement cross-camera identity tracking.

**Reasoning**:
- Resolving re-entry requires face recognition or persistent person re-identification across cameras — raises privacy concerns and adds significant complexity
- For the conversion rate metric, approximate footfall (with potential re-entry inflation) is still directionally useful
- Industry standard retail footfall counters (Axis, RetailNext) also do not resolve re-entry by default

**Assumption stated**: Each entry event counted is treated as a unique visit for the purpose of this challenge.

---

## 5. Database: PostgreSQL over MongoDB

**Decision**: Use PostgreSQL (relational) over a document store.

**Reasoning**:
- Event data has a well-defined schema that doesn't change per event type
- Aggregation queries (hourly counts, conversion rate JOIN with sales data) are more natural in SQL
- Spring Data JPA gives strong typing and query safety without boilerplate
- The sales transaction CSV data is tabular — natural fit for relational model

---

## 6. Staff Detection: Not filtered

**Decision**: No staff exclusion logic implemented.

**Reasoning**:
- Distinguishing staff from customers requires either badge detection (CV-hard) or a designated staff zone (layout-specific)
- The Brigade Road store layout shows staff typically near the billing counter — a billing zone camera heuristic could partially exclude them
- Chosen to document this limitation transparently rather than implement a brittle heuristic

**Impact on metrics**: Footfall numbers will be slightly inflated due to staff movement. Conversion rate will appear slightly lower than actual.

---

## 7. Frame Sampling Rate: Every 15th frame

**Decision**: Process 1 frame every 15 frames (approximately 2 frames/second for 30fps video).

**Reasoning**:
- Person count in a retail store changes slowly — sampling at 2fps captures all meaningful events
- Reduces processing time by 15x, making it feasible to process 5 video files in reasonable time on CPU
- Anomaly detection (overcrowding) uses sustained count over multiple frames — a single missed frame doesn't affect alert accuracy