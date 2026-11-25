package com.trip.infra;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TripEventRepository extends JpaRepository<TripEventEntity, TripEventId> {

    List<TripEventEntity> findByJobIdAndSeqGreaterThanOrderBySeqAsc(String jobId, int seq);

    @Query("select coalesce(max(e.seq), 0) from TripEventEntity e where e.jobId = :jobId")
    Integer maxSeq(@Param("jobId") String jobId);
}
