package com.trip.infra;

import org.springframework.data.jpa.repository.JpaRepository;

public interface TripJobRepository extends JpaRepository<TripJobEntity, String> {
}
