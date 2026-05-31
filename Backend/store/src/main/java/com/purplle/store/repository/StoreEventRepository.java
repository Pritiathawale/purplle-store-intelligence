package com.purplle.store.repository;

import com.purplle.store.model.StoreEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface StoreEventRepository extends JpaRepository<StoreEvent, Long> {

    // All events for a specific camera
    List<StoreEvent> findByCameraId(String cameraId);

    // All events for a specific zone
    List<StoreEvent> findByZone(String zone);

    // All alert events (non-null alert field)
    List<StoreEvent> findByAlertIsNotNull();

    // All entrance camera events — used for footfall
    List<StoreEvent> findByZoneOrderByTimestampAsc(String zone);
    
    // Max people count across all events — peak occupancy
    @Query("SELECT MAX(e.peopleCount) FROM StoreEvent e")
    Integer findMaxPeopleCount();

    // Average people count — store busy-ness
    @Query("SELECT AVG(e.peopleCount) FROM StoreEvent e")
    Double findAvgPeopleCount();

    // Count of overcrowding alerts
    @Query("SELECT COUNT(e) FROM StoreEvent e WHERE e.alert = 'OVERCROWDING'")
    Long countOvercrowdingAlerts();

   
    @Query("SELECT SUBSTRING(e.timestamp, 12, 2) as hour, AVG(e.peopleCount) as avg " +
            "FROM StoreEvent e GROUP BY SUBSTRING(e.timestamp, 12, 2) ORDER BY hour")
    List<Object[]> findHourlyAveragePeopleCount();

    // Per-zone summary
    @Query("SELECT e.zone, MAX(e.peopleCount), AVG(e.peopleCount), COUNT(e) " +
            "FROM StoreEvent e GROUP BY e.zone")
    List<Object[]> findZoneSummary();
}