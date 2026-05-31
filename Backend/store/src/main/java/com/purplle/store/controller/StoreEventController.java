package com.purplle.store.controller;

import com.purplle.store.model.StoreEvent;
import com.purplle.store.repository.StoreEventRepository;
import com.purplle.store.service.AnalyticsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*") // allows React dashboard on port 3000
public class StoreEventController {

    @Autowired
    private StoreEventRepository repo;

    @Autowired
    private AnalyticsService analyticsService;

  
    // POST /api/events — Python detector posts here
    @PostMapping("/events")
    public ResponseEntity<StoreEvent> saveEvent(@RequestBody StoreEvent event) {
        StoreEvent saved = repo.save(event);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    // POST /api/events/batch — optional: post all events at once from events.json
    @PostMapping("/events/batch")
    public ResponseEntity<Map<String, Object>> saveBatch(@RequestBody List<StoreEvent> events) {
        List<StoreEvent> saved = repo.saveAll(events);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(Map.of("saved", saved.size(), "message", "Batch import successful"));
    }

   
    // GET /api/events — all raw events
    @GetMapping("/events")
    public ResponseEntity<List<StoreEvent>> getAllEvents() {
        return ResponseEntity.ok(repo.findAll());
    }

    // GET /api/events?camera=CAM_3
    @GetMapping(value = "/events", params = "camera")
    public ResponseEntity<List<StoreEvent>> getByCamera(@RequestParam String camera) {
        return ResponseEntity.ok(repo.findByCameraId(camera));
    }

 
    // GET /api/metrics — footfall, conversion rate, GMV, peak count
    @GetMapping("/metrics")
    public ResponseEntity<Map<String, Object>> getMetrics() {
        return ResponseEntity.ok(analyticsService.getMetrics());
    }

    // GET /api/funnel — entry → browse → billing → purchase funnel
    @GetMapping("/funnel")
    public ResponseEntity<Map<String, Object>> getFunnel() {
        return ResponseEntity.ok(analyticsService.getFunnel());
    }

    // GET /api/alerts — all anomaly events with breakdown
    @GetMapping("/alerts")
    public ResponseEntity<Map<String, Object>> getAlerts() {
        return ResponseEntity.ok(analyticsService.getAlerts());
    }

    // GET /api/analytics/hourly — average people count by hour (for bar chart)
    @GetMapping("/analytics/hourly")
    public ResponseEntity<List<Map<String, Object>>> getHourly() {
        return ResponseEntity.ok(analyticsService.getHourlyAnalytics());
    }

    // GET /api/analytics/zones — per-zone summary
    @GetMapping("/analytics/zones")
    public ResponseEntity<List<Map<String, Object>>> getZones() {
        return ResponseEntity.ok(analyticsService.getZoneAnalytics());
    }

    // Health check
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "ok", "service", "Store Intelligence API"));
    }
}