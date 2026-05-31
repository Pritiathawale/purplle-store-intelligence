package com.purplle.store.model;

import jakarta.persistence.*;

import java.time.LocalDateTime;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@Setter
@NoArgsConstructor
@Table(name = "store_events")
public class StoreEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Matches Python event fields exactly
    private String cameraId;
    private String zone;
    private Integer peopleCount;
    private String timestamp; // ISO string from Python e.g. "2026-04-10T12:15:00"
    private Double videoTimestamp;
    private Integer frameNumber;
    private String alert; // "OVERCROWDING" / "EMPTY_ENTRANCE" / "LONG_QUEUE" / null

    // Auto-set when record is saved
    @Column(updatable = false)
    private LocalDateTime receivedAt = LocalDateTime.now();

}