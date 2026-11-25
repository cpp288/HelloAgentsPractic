package com.trip.domain;

import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * 预算由 Java 确定性求和：LLM 只给单价/明细，不算总数。
 * 最后一天视为返程日，不计住宿。
 */
public final class BudgetCalculator {

    private BudgetCalculator() {
    }

    public static Budget calculate(JsonNode plan) {
        JsonNode days = plan.path("days");
        long attractions = 0;
        long hotels = 0;
        long meals = 0;
        long transport = 0;
        List<Budget.DayCost> dayCosts = new ArrayList<>();

        for (int i = 0; i < days.size(); i++) {
            JsonNode day = days.get(i);
            long dayAttractions = 0;
            for (JsonNode attraction : day.path("attractions")) {
                dayAttractions = Math.addExact(dayAttractions, cents(attraction.path("ticket_price")));
            }
            long dayHotels = (i == days.size() - 1) ? 0 : cents(day.path("hotel").path("price_per_night"));
            long dayMeals = 0;
            for (JsonNode meal : day.path("meals")) {
                dayMeals = Math.addExact(dayMeals, cents(meal.path("estimated_cost")));
            }
            long dayTransport = cents(day.path("transportation_cost"));
            long dayTotal = Math.addExact(Math.addExact(dayAttractions, dayHotels),
                    Math.addExact(dayMeals, dayTransport));

            dayCosts.add(new Budget.DayCost(i, day.path("date").asText(""),
                    dayAttractions, dayHotels, dayMeals, dayTransport, dayTotal));

            attractions = Math.addExact(attractions, dayAttractions);
            hotels = Math.addExact(hotels, dayHotels);
            meals = Math.addExact(meals, dayMeals);
            transport = Math.addExact(transport, dayTransport);
        }

        long total = Math.addExact(Math.addExact(attractions, hotels), Math.addExact(meals, transport));
        return new Budget(attractions, hotels, meals, transport, total, "CNY", "单人", dayCosts);
    }

    private static long cents(JsonNode value) {
        if (value == null || value.isMissingNode() || value.isNull()) {
            return 0;
        }
        return Math.round(value.asDouble(0) * 100);
    }
}
