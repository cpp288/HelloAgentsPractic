package com.trip.infra;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

public interface TripRepository extends JpaRepository<TripEntity, String> {

    Optional<TripEntity> findByJobId(String jobId);

    Optional<TripEntity> findByJobIdAndAnonId(String jobId, String anonId);
}
