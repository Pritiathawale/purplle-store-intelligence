package com.purplle.store.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * Flexible entity that stores ALL 3 event schema types from detector.py:
 * - entry/exit (Schema 1): id_token, store_code, event_timestamp
 * - zone_entered/zone_exited (Schema 2): track_id, store_id, zone_id, event_time
 * - queue_completed/queue_abandoned (Schema 3): queue_event_id, queue_join_ts
 */
@Entity
@Table(name = "store_events")
public class StoreEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // ── Common fields ──────────────────────────────────────────────
    private String eventId;       // uuid for deduplication (queue_event_id or generated)
    private String eventType;     // entry|exit|zone_entered|zone_exited|queue_completed|queue_abandoned
    private String storeId;       // ST1008 or ST1009
    private String storeCode;     // store_1008
    private String cameraId;
    private String timestamp;     // normalised timestamp for all event types
    private Boolean isStaff;

    // ── Entry/Exit fields (Schema 1) ───────────────────────────────
    private String idToken;       // visitor ID: ID_60001
    private String groupId;
    private Integer groupSize;
    private Boolean isFaceHidden;

    // ── Zone fields (Schema 2) ─────────────────────────────────────
    private Integer trackId;
    private String zoneId;
    private String zoneName;
    private String zoneType;
    private String isRevenueZone;
    private Double hotspotX;
    private Double hotspotY;

    // ── Queue fields (Schema 3) ────────────────────────────────────
    private String queueJoinTs;
    private String queueServedTs;
    private String queueExitTs;
    private Integer waitSeconds;
    private Integer queuePositionAtJoin;
    private Boolean abandoned;

    // ── People count (from detector for analytics) ─────────────────
    private Integer peopleCount;

    @Column(updatable = false)
    private LocalDateTime receivedAt = LocalDateTime.now();

    // ── Getters & Setters ──────────────────────────────────────────
    public Long getId()                         { return id; }
    public String getEventId()                  { return eventId; }
    public void setEventId(String v)            { this.eventId = v; }
    public String getEventType()                { return eventType; }
    public void setEventType(String v)          { this.eventType = v; }
    public String getStoreId()                  { return storeId; }
    public void setStoreId(String v)            { this.storeId = v; }
    public String getStoreCode()                { return storeCode; }
    public void setStoreCode(String v)          { this.storeCode = v; }
    public String getCameraId()                 { return cameraId; }
    public void setCameraId(String v)           { this.cameraId = v; }
    public String getTimestamp()                { return timestamp; }
    public void setTimestamp(String v)          { this.timestamp = v; }
    public Boolean getIsStaff()                 { return isStaff; }
    public void setIsStaff(Boolean v)           { this.isStaff = v; }
    public String getIdToken()                  { return idToken; }
    public void setIdToken(String v)            { this.idToken = v; }
    public String getGroupId()                  { return groupId; }
    public void setGroupId(String v)            { this.groupId = v; }
    public Integer getGroupSize()               { return groupSize; }
    public void setGroupSize(Integer v)         { this.groupSize = v; }
    public Boolean getIsFaceHidden()            { return isFaceHidden; }
    public void setIsFaceHidden(Boolean v)      { this.isFaceHidden = v; }
    public Integer getTrackId()                 { return trackId; }
    public void setTrackId(Integer v)           { this.trackId = v; }
    public String getZoneId()                   { return zoneId; }
    public void setZoneId(String v)             { this.zoneId = v; }
    public String getZoneName()                 { return zoneName; }
    public void setZoneName(String v)           { this.zoneName = v; }
    public String getZoneType()                 { return zoneType; }
    public void setZoneType(String v)           { this.zoneType = v; }
    public String getIsRevenueZone()            { return isRevenueZone; }
    public void setIsRevenueZone(String v)      { this.isRevenueZone = v; }
    public Double getHotspotX()                 { return hotspotX; }
    public void setHotspotX(Double v)           { this.hotspotX = v; }
    public Double getHotspotY()                 { return hotspotY; }
    public void setHotspotY(Double v)           { this.hotspotY = v; }
    public String getQueueJoinTs()              { return queueJoinTs; }
    public void setQueueJoinTs(String v)        { this.queueJoinTs = v; }
    public String getQueueServedTs()            { return queueServedTs; }
    public void setQueueServedTs(String v)      { this.queueServedTs = v; }
    public String getQueueExitTs()              { return queueExitTs; }
    public void setQueueExitTs(String v)        { this.queueExitTs = v; }
    public Integer getWaitSeconds()             { return waitSeconds; }
    public void setWaitSeconds(Integer v)       { this.waitSeconds = v; }
    public Integer getQueuePositionAtJoin()     { return queuePositionAtJoin; }
    public void setQueuePositionAtJoin(Integer v){ this.queuePositionAtJoin = v; }
    public Boolean getAbandoned()               { return abandoned; }
    public void setAbandoned(Boolean v)         { this.abandoned = v; }
    public Integer getPeopleCount()             { return peopleCount; }
    public void setPeopleCount(Integer v)       { this.peopleCount = v; }
    public LocalDateTime getReceivedAt()        { return receivedAt; }
}