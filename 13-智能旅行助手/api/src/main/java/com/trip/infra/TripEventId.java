package com.trip.infra;

import java.io.Serializable;

public class TripEventId implements Serializable {

    private String jobId;
    private int seq;

    public TripEventId() {
    }

    public TripEventId(String jobId, int seq) {
        this.jobId = jobId;
        this.seq = seq;
    }

    public String getJobId() {
        return jobId;
    }

    public void setJobId(String jobId) {
        this.jobId = jobId;
    }

    public int getSeq() {
        return seq;
    }

    public void setSeq(int seq) {
        this.seq = seq;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof TripEventId other)) {
            return false;
        }
        return seq == other.seq && java.util.Objects.equals(jobId, other.jobId);
    }

    @Override
    public int hashCode() {
        return java.util.Objects.hash(jobId, seq);
    }
}
