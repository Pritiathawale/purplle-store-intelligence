package com.purplle.store.repository;

import com.purplle.store.model.StoreEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface StoreEventRepository extends JpaRepository<StoreEvent, Long> {

    // Deduplication — find by eventId
    Optional<StoreEvent> findByEventId(String eventId);

    // By store
    List<StoreEvent> findByStoreId(String storeId);

    // Entry events (footfall) — exclude staff
    @Query("SELECT e FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType = 'entry' AND (e.isStaff = false OR e.isStaff IS NULL)")
    List<StoreEvent> findEntryEvents(@Param("sid") String storeId);

    // Exit events
    @Query("SELECT e FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType = 'exit'")
    List<StoreEvent> findExitEvents(@Param("sid") String storeId);

    // Zone events
    @Query("SELECT e FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType IN ('zone_entered','zone_exited')")
    List<StoreEvent> findZoneEvents(@Param("sid") String storeId);

    // Queue events
    @Query("SELECT e FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType IN ('queue_completed','queue_abandoned')")
    List<StoreEvent> findQueueEvents(@Param("sid") String storeId);

    // Abandoned queue events
    @Query("SELECT e FROM StoreEvent e WHERE e.storeId = :sid AND e.abandoned = true")
    List<StoreEvent> findAbandonedQueue(@Param("sid") String storeId);

    // Completed queue (converted visitors)
    @Query("SELECT e FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType = 'queue_completed'")
    List<StoreEvent> findCompletedQueue(@Param("sid") String storeId);

    // Zone dwell — avg wait per zone
    @Query("SELECT e.zoneName, AVG(e.waitSeconds) FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType = 'queue_completed' GROUP BY e.zoneName")
    List<Object[]> findAvgDwellPerZone(@Param("sid") String storeId);

    // Hourly people count for chart
    @Query("SELECT SUBSTRING(e.timestamp, 12, 2), COUNT(e) FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType = 'entry' GROUP BY SUBSTRING(e.timestamp, 12, 2) ORDER BY 1")
    List<Object[]> findHourlyEntries(@Param("sid") String storeId);

    // Zone visit frequency
    @Query("SELECT e.zoneName, e.zoneId, COUNT(e) FROM StoreEvent e WHERE e.storeId = :sid AND e.eventType = 'zone_entered' GROUP BY e.zoneName, e.zoneId")
    List<Object[]> findZoneVisitFrequency(@Param("sid") String storeId);

    // Last event timestamp (for health/stale feed check)
    @Query("SELECT MAX(e.timestamp) FROM StoreEvent e WHERE e.storeId = :sid")
    String findLastEventTimestamp(@Param("sid") String storeId);
}