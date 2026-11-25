package com.trip.api.dto;

import java.util.List;
import java.util.Map;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record UpdateAttractionsRequest(
        @NotNull(message = "attractions 不能为空")
        @Size(max = 20, message = "单日景点最多 20 个")
        List<Map<String, Object>> attractions) {
}
