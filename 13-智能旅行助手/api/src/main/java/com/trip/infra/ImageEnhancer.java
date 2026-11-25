package com.trip.infra;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

/**
 * 景点配图增强：确定性 HTTP 调用，归 Java。
 * 未配置 UNSPLASH_ACCESS_KEY 时直接跳过，image_url 留空，前端用占位样式。
 */
@Component
public class ImageEnhancer {

    private static final Logger log = LoggerFactory.getLogger(ImageEnhancer.class);

    /** 把配图过程写进执行追踪（只走 SSE，不落库） */
    public interface Trace {
        void emit(String tag, String text, String level);
    }

    private record Found(String url, String id, String author) {
    }

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(3))
            .build();

    @Value("${app.unsplash-access-key:}")
    private String accessKey;

    public ImageEnhancer(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public String enhance(String planJson, String city, Trace trace) {
        if (accessKey == null || accessKey.isBlank()) {
            trace.emit("配图", "未配置 UNSPLASH_ACCESS_KEY，跳过 Unsplash 配图（前端用渐变占位）", "warn");
            return planJson;
        }
        long started = System.currentTimeMillis();
        try {
            JsonNode plan = objectMapper.readTree(planJson);
            List<ObjectNode> targets = new ArrayList<>();
            for (JsonNode day : plan.path("days")) {
                for (JsonNode attraction : day.path("attractions")) {
                    if (attraction instanceof ObjectNode node
                            && (node.path("image_url").isNull() || node.path("image_url").asText("").isBlank())) {
                        targets.add(node);
                    }
                }
            }
            if (targets.isEmpty()) {
                trace.emit("配图", "所有景点已有图片，跳过 Unsplash 调用", "info");
                return planJson;
            }

            int total = targets.size();
            trace.emit("配图", "调用 Unsplash /search/photos 为 " + total
                    + " 个景点配图（虚拟线程并行，单张 5s 超时）", "info");

            AtomicInteger matched = new AtomicInteger();
            try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
                List<Future<?>> futures = new ArrayList<>();
                for (ObjectNode node : targets) {
                    String name = node.path("name").asText("");
                    futures.add(executor.submit(() -> {
                        Found found = findImage(name, city);
                        if (found != null) {
                            node.put("image_url", found.url());
                            matched.incrementAndGet();
                            trace.emit("配图", "「" + name + "」→ photo " + found.id()
                                    + "（by " + found.author() + "）", "info");
                        } else {
                            trace.emit("配图", "「" + name + "」未匹配到图片", "warn");
                        }
                    }));
                }
                for (Future<?> future : futures) {
                    try {
                        future.get(5, TimeUnit.SECONDS);
                    } catch (Exception e) {
                        log.debug("配图单张超时/失败，忽略: {}", e.getMessage());
                    }
                }
            }

            long cost = System.currentTimeMillis() - started;
            trace.emit("配图", "Unsplash 配图完成：成功 " + matched.get() + "/" + total + "（" + cost + " ms）",
                    matched.get() == total ? "ok" : "warn");
            return objectMapper.writeValueAsString(plan);
        } catch (Exception e) {
            log.warn("配图增强失败，返回原行程: {}", e.getMessage());
            trace.emit("配图", "配图异常，保留占位图：" + e.getMessage(), "error");
            return planJson;
        }
    }

    private Found findImage(String name, String city) {
        try {
            String query = URLEncoder.encode(name + " " + city, StandardCharsets.UTF_8);
            String uri = "https://api.unsplash.com/search/photos?per_page=1&query=" + query
                    + "&client_id=" + URLEncoder.encode(accessKey, StandardCharsets.UTF_8);
            HttpRequest request = HttpRequest.newBuilder(URI.create(uri))
                    .timeout(Duration.ofSeconds(4))
                    .GET()
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                log.debug("Unsplash 返回 {} name={}", response.statusCode(), name);
                return null;
            }
            JsonNode results = objectMapper.readTree(response.body()).path("results");
            if (results.isArray() && !results.isEmpty()) {
                JsonNode first = results.get(0);
                String url = first.path("urls").path("small").asText("");
                if (url.isBlank()) {
                    return null;
                }
                return new Found(
                        url,
                        first.path("id").asText("unknown"),
                        first.path("user").path("name").asText("unknown"));
            }
        } catch (Exception e) {
            log.debug("Unsplash 查询失败 name={}: {}", name, e.getMessage());
        }
        return null;
    }
}
