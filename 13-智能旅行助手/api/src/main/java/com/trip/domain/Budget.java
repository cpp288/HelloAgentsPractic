package com.trip.domain;

import java.util.List;

/**
 * 金额统一用「分」的整数，避免浮点误差；总和用 Math.addExact 防溢出。
 */
public record Budget(
        long attractionsCents,
        long hotelsCents,
        long mealsCents,
        long transportCents,
        long totalCents,
        String currency,
        String unit,
        List<DayCost> days) {

    public record DayCost(
            int dayIndex,
            String date,
            long attractionsCents,
            long hotelsCents,
            long mealsCents,
            long transportCents,
            long totalCents) {
    }
}
