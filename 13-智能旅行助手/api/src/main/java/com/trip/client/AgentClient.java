package com.trip.client;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trip.api.dto.CreateTripRequest;
import com.trip.config.AgentProperties;

/**
 * Java → Python 的 NDJSON 流客户端。
 * 不用 java.net.http.HttpClient（它默认发 Expect: 100-continue，uvicorn/FastAPI 某版本下没正确响应 100，导致请求体丢失）。
 * 改用 HttpURLConnection，简单可靠。
 */
@Component
public class AgentClient {

    private static final Logger log = LoggerFactory.getLogger(AgentClient.class);

    private final AgentProperties properties;
    private final ObjectMapper objectMapper;

    public AgentClient(AgentProperties properties, ObjectMapper objectMapper) {
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public void streamPlan(CreateTripRequest request, String traceId, Consumer<JsonNode> onEvent) {
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("city", request.city());
            payload.put("start_date", request.startDate().toString());
            payload.put("end_date", request.endDate().toString());
            payload.put("days", request.resolvedDays());
            payload.put("preferences", nullSafe(request.preferences()));
            payload.put("budget_level", nullSafe(request.budgetLevel(), "中等"));
            payload.put("transportation", nullSafe(request.transportation(), "公共交通"));
            payload.put("accommodation", nullSafe(request.accommodation(), "经济型酒店"));

            String body = objectMapper.writeValueAsString(payload);
            log.debug("调用 Agent POST {} body={}", properties.baseUrl() + "/internal/v1/plans", body);

            URI uri = URI.create(properties.baseUrl() + "/internal/v1/plans");
            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) uri.toURL().openConnection();
            try {
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(properties.timeoutSeconds() * 1000);
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setInstanceFollowRedirects(false);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setRequestProperty("Accept", "application/x-ndjson");
                conn.setRequestProperty("X-Internal-Token", properties.internalToken());
                conn.setRequestProperty("X-Trace-Id", traceId == null ? "" : traceId);
                // 关键：显式关闭 100-continue
                conn.setRequestProperty("Expect", "");

                byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
                try (var out = conn.getOutputStream()) {
                    out.write(bytes);
                }

                int code = conn.getResponseCode();
                if (code != 200) {
                    String detail = "";
                    try (InputStream err = conn.getErrorStream()) {
                        if (err != null) {
                            detail = new String(err.readAllBytes(), StandardCharsets.UTF_8);
                        }
                    }
                    throw new AgentException("AGENT_UNAVAILABLE",
                            "Agent 返回 " + code + ": " + detail, null);
                }

                try (InputStream in = conn.getInputStream();
                     BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        if (line.isBlank()) {
                            continue;
                        }
                        JsonNode event = objectMapper.readTree(line);
                        log.debug("Agent 事件 type={}", event.path("type").asText());
                        onEvent.accept(event);
                    }
                }
            } finally {
                conn.disconnect();
            }
        } catch (AgentException e) {
            throw e;
        } catch (Exception e) {
            throw new AgentException("AGENT_UNAVAILABLE", "调用 Agent 失败: " + e.getMessage(), e);
        }
    }

    private static String nullSafe(String value) {
        return value == null ? "" : value;
    }

    private static String nullSafe(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
