package com.trip.api.dto;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateTripRequest(
        @NotBlank(message = "城市不能为空") @Size(max = 32, message = "城市名称过长") String city,
        @NotNull(message = "开始日期不能为空") LocalDate startDate,
        @NotNull(message = "结束日期不能为空") LocalDate endDate,
        @Min(value = 1, message = "天数至少 1 天") @Max(value = 15, message = "天数最多 15 天") Integer days,
        @Size(max = 200, message = "偏好描述过长") String preferences,
        @Size(max = 16) String budgetLevel,
        @Size(max = 16) String transportation,
        @Size(max = 32) String accommodation) {

    public int resolvedDays() {
        if (days != null) {
            return days;
        }
        return (int) ChronoUnit.DAYS.between(startDate, endDate) + 1;
    }
}
