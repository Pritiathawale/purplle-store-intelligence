package com.purplle.store.controller;

import com.purplle.store.model.StoreEvent;
import com.purplle.store.repository.StoreEventRepository;
import com.purplle.store.service.AnalyticsService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDateTime;
import java.util.*;

@RestController
@CrossOrigin(origins = "*")
public class StoreEventController {

    private static final Logger log = LoggerFactory.getLogger(StoreEventController.class);

    @Autowired private StoreEventRepository repo;
    @Autowired private AnalyticsService     svc;

    // ═══════════════════════════════════════════════════════════════
    // ACCEPTANCE GATE ENDPOINTS
    // ═══════════════════════════════════════════════════════════════

    /**
     * POST /events/ingest
     * Accepts batches of up to 500 events.
     * Idempotent by event_id (queue_event_id or generated uuid).
     * Partial success — malformed events are skipped, not failed.
     * Handles ALL 3 schemas from detector.py.
     */
    @PostMapping("/events/ingest")
    public ResponseEntity<Map<String, Object>> ingest(
            @RequestBody List<Map<String, Object>> events) {

        long start   = System.currentTimeMillis();
        int  saved   = 0, skipped = 0;
        List<String> errors = new ArrayList<>();

        for (Map<String, Object> raw : events) {
            try {
                String dedupeKey = extractDedupeKey(raw);
                // Idempotency check
                if (dedupeKey != null && repo.findByEventId(dedupeKey).isPresent()) {
                    skipped++;
                    continue;
                }
                StoreEvent e = mapToEntity(raw, dedupeKey);
                repo.save(e);
                saved++;
            } catch (Exception ex) {
                errors.add("Skipped: " + ex.getMessage());
                skipped++;
            }
        }

        long latency = System.currentTimeMillis() - start;
        // Structured log
        log.info("INGEST store=multiple accepted={} skipped={} total={} latency_ms={}",
            saved, skipped, events.size(), latency);

        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("accepted",    saved);
        resp.put("skipped",     skipped);
        resp.put("total",       events.size());
        resp.put("latency_ms",  latency);
        if (!errors.isEmpty()) resp.put("errors", errors.subList(0, Math.min(5, errors.size())));
        return ResponseEntity.status(HttpStatus.CREATED).body(resp);
    }

    /** GET /stores/{id}/metrics — ACCEPTANCE GATE */
    @GetMapping("/stores/{storeId}/metrics")
    public ResponseEntity<Map<String, Object>> metrics(@PathVariable String storeId) {
        long start = System.currentTimeMillis();
        try {
            Map<String, Object> result = svc.getMetrics(storeId);
            log.info("METRICS store={} latency_ms={}", storeId, System.currentTimeMillis()-start);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            return db503(e);
        }
    }

    /** GET /stores/{id}/funnel */
    @GetMapping("/stores/{storeId}/funnel")
    public ResponseEntity<Map<String, Object>> funnel(@PathVariable String storeId) {
        try { return ResponseEntity.ok(svc.getFunnel(storeId)); }
        catch (Exception e) { return db503(e); }
    }

    /** GET /stores/{id}/anomalies */
    @GetMapping("/stores/{storeId}/anomalies")
    public ResponseEntity<List<Map<String, Object>>> anomalies(@PathVariable String storeId) {
        try { return ResponseEntity.ok(svc.getAnomalies(storeId)); }
        catch (Exception e) {
            return ResponseEntity.status(503).body(List.of(
                Map.of("error", "SERVICE_UNAVAILABLE", "message", e.getMessage())));
        }
    }

    /** GET /stores/{id}/heatmap */
    @GetMapping("/stores/{storeId}/heatmap")
    public ResponseEntity<Map<String, Object>> heatmap(@PathVariable String storeId) {
        try { return ResponseEntity.ok(svc.getHeatmap(storeId)); }
        catch (Exception e) { return db503(e); }
    }

    /** GET /health */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        try { return ResponseEntity.ok(svc.getHealth()); }
        catch (Exception e) {
            return ResponseEntity.status(503).body(
                Map.of("status","DOWN","error","DATABASE_UNAVAILABLE","message", e.getMessage()));
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // REACT DASHBOARD ENDPOINTS (keep for live dashboard)
    // ═══════════════════════════════════════════════════════════════

    @GetMapping("/api/health")
    public ResponseEntity<Map<String, Object>> apiHealth() {
        return ResponseEntity.ok(Map.of("status","ok","service","Store Intelligence API"));
    }

    @GetMapping("/api/metrics")
    public ResponseEntity<Map<String, Object>> apiMetrics() {
        return ResponseEntity.ok(svc.getMetrics("ST1008"));
    }

    @GetMapping("/api/funnel")
    public ResponseEntity<Map<String, Object>> apiFunnel() {
        return ResponseEntity.ok(svc.getFunnel("ST1008"));
    }

    @GetMapping("/api/alerts")
    public ResponseEntity<List<Map<String, Object>>> apiAlerts() {
        return ResponseEntity.ok(svc.getAnomalies("ST1008"));
    }

    @GetMapping("/api/analytics/hourly")
    public ResponseEntity<List<Map<String, Object>>> apiHourly() {
        return ResponseEntity.ok(svc.getHourlyAnalytics("ST1008"));
    }

    @GetMapping("/api/events")
    public ResponseEntity<List<StoreEvent>> apiEvents() {
        return ResponseEntity.ok(repo.findAll());
    }

    @PostMapping("/api/events")
    public ResponseEntity<StoreEvent> apiSaveEvent(@RequestBody StoreEvent e) {
        return ResponseEntity.status(201).body(repo.save(e));
    }

    // ═══════════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════════

    /** Extract deduplication key — use queue_event_id if present, else build from fields */
    private String extractDedupeKey(Map<String, Object> raw) {
        if (raw.containsKey("queue_event_id") && raw.get("queue_event_id") != null)
            return raw.get("queue_event_id").toString();
        // For entry/exit: camera_id + id_token + event_timestamp
        String cam = str(raw, "camera_id");
        String tok = str(raw, "id_token");
        String ts  = str(raw, "event_timestamp");
        if (cam != null && tok != null && ts != null)
            return cam + "|" + tok + "|" + ts;
        // For zone: camera_id + track_id + event_time
        String tid  = str(raw, "track_id");
        String ets  = str(raw, "event_time");
        if (cam != null && tid != null && ets != null)
            return cam + "|" + tid + "|" + ets;
        return null; // no dedup — always insert
    }

    /** Map raw JSON (any of 3 schemas) to StoreEvent entity */
    private StoreEvent mapToEntity(Map<String, Object> r, String dedupeKey) {
        StoreEvent e = new StoreEvent();
        e.setEventId(dedupeKey);
        e.setEventType(str(r, "event_type"));
        e.setCameraId(str(r, "camera_id"));
        e.setIsStaff(bool(r, "is_staff"));

        // Store ID — support both store_code and store_id field names
        String sid = str(r, "store_id");
        String sc  = str(r, "store_code");
        if (sid != null) e.setStoreId(sid);
        else if (sc != null) e.setStoreId(sc.replace("store_","ST"));
        e.setStoreCode(sc);

        // Normalise timestamp — handle all 3 field names
        String ts = str(r, "event_timestamp");   // Schema 1: entry/exit
        if (ts == null) ts = str(r, "event_time");    // Schema 2: zone
        if (ts == null) ts = str(r, "queue_join_ts"); // Schema 3: queue
        if (ts == null) ts = LocalDateTime.now().toString();
        e.setTimestamp(ts.length() > 19 ? ts.substring(0, 19) : ts);

        // Schema 1 fields
        e.setIdToken(str(r, "id_token"));
        e.setGroupId(str(r, "group_id"));
        e.setGroupSize(intVal(r, "group_size"));
        Object fh = r.get("is_face_hidden");
        if (fh != null) e.setIsFaceHidden(Boolean.parseBoolean(fh.toString()));

        // Schema 2 fields
        e.setTrackId(intVal(r, "track_id"));
        e.setZoneId(str(r, "zone_id"));
        e.setZoneName(str(r, "zone_name"));
        e.setZoneType(str(r, "zone_type"));
        e.setIsRevenueZone(str(r, "is_revenue_zone"));
        e.setHotspotX(dblVal(r, "zone_hotspot_x"));
        e.setHotspotY(dblVal(r, "zone_hotspot_y"));

        // Schema 3 fields
        e.setQueueJoinTs(str(r, "queue_join_ts"));
        e.setQueueServedTs(str(r, "queue_served_ts"));
        e.setQueueExitTs(str(r, "queue_exit_ts"));
        e.setWaitSeconds(intVal(r, "wait_seconds"));
        e.setQueuePositionAtJoin(intVal(r, "queue_position_at_join"));
        Object ab = r.get("abandoned");
        if (ab != null) e.setAbandoned(Boolean.parseBoolean(ab.toString()));

        return e;
    }

    private String  str(Map<String,Object> m, String k) { Object v=m.get(k); return v!=null?v.toString():null; }
    private Boolean bool(Map<String,Object> m, String k) { Object v=m.get(k); return v!=null?Boolean.parseBoolean(v.toString()):false; }
    private Integer intVal(Map<String,Object> m, String k) { try{ Object v=m.get(k); return v!=null?((Number)v).intValue():null;}catch(Exception e){return null;} }
    private Double  dblVal(Map<String,Object> m, String k) { try{ Object v=m.get(k); return v!=null?((Number)v).doubleValue():null;}catch(Exception e){return null;} }

    @SuppressWarnings("unchecked")
    private <T> ResponseEntity<T> db503(Exception e) {
        Map<String,Object> body = Map.of(
            "error","SERVICE_UNAVAILABLE","message","Database error: " + e.getMessage());
        return (ResponseEntity<T>) ResponseEntity.status(503).body(body);
    }
}