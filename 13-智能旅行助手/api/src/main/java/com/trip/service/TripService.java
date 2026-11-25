package com.trip.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.trip.api.ApiException;
import com.trip.api.dto.CreateTripRequest;
import com.trip.api.dto.JobCreatedResponse;
import com.trip.client.AgentClient;
import com.trip.domain.Budget;
import com.trip.domain.BudgetCalculator;
import com.trip.infra.ExportRenderer;
import com.trip.infra.ImageEnhancer;
import com.trip.infra.TripEntity;
import com.trip.infra.TripEventEntity;
import com.trip.infra.TripEventRepository;
import com.trip.infra.TripJobEntity;
import com.trip.infra.TripJobRepository;
import com.trip.infra.TripRepository;

@Service
public class TripService {

    private static final Logger log = LoggerFactory.getLogger(TripService.class);

    private static final String PENDING = "PENDING";
    private static final String RUNNING = "RUNNING";
    private static final String SUCCEEDED = "SUCCEEDED";
    private static final String FAILED = "FAILED";
    private static final Set<String> TERMINAL = Set.of(SUCCEEDED, FAILED);

    private final TripJobRepository jobRepository;
    private final TripRepository tripRepository;
    private final TripEventRepository eventRepository;
    private final AgentClient agentClient;
    private final ExecutorService tripExecutor;
    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final ImageEnhancer imageEnhancer;
    private final ExportRenderer exportRenderer;
    private final int rateLimitPerMinute;
    private final int idempotencyMinutes;

    private final Map<String, JobStream> streams = new ConcurrentHashMap<>();

    public TripService(TripJobRepository jobRepository,
                       TripRepository tripRepository,
                       TripEventRepository eventRepository,
                       AgentClient agentClient,
                       ExecutorService tripExecutor,
                       StringRedisTemplate redis,
                       ObjectMapper objectMapper,
                       ImageEnhancer imageEnhancer,
                       ExportRenderer exportRenderer,
                       @Value("${app.rate-limit-per-minute:10}") int rateLimitPerMinute,
                       @Value("${app.idempotency-minutes:10}") int idempotencyMinutes) {
        this.jobRepository = jobRepository;
        this.tripRepository = tripRepository;
        this.eventRepository = eventRepository;
        this.agentClient = agentClient;
        this.tripExecutor = tripExecutor;
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.imageEnhancer = imageEnhancer;
        this.exportRenderer = exportRenderer;
        this.rateLimitPerMinute = rateLimitPerMinute;
        this.idempotencyMinutes = idempotencyMinutes;
    }

    // ---------------- 创建任务 ----------------

    public JobCreatedResponse createJob(String anonId, String clientIp, CreateTripRequest request) {
        if (request.endDate().isBefore(request.startDate())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_DATE_RANGE", "结束日期不能早于开始日期");
        }
        checkRateLimit(anonId, clientIp);

        String requestJson;
        try {
            requestJson = objectMapper.writeValueAsString(request);
        } catch (Exception e) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "BAD_REQUEST", "请求序列化失败");
        }

        String idempotencyKey = "trip:idem:" + sha256(requestJson);
        String newJobId = newId();
        try {
            Boolean first = redis.opsForValue()
                    .setIfAbsent(idempotencyKey, newJobId, Duration.ofMinutes(idempotencyMinutes));
            if (Boolean.FALSE.equals(first)) {
                String existing = redis.opsForValue().get(idempotencyKey);
                TripJobEntity old = existing == null ? null : jobRepository.findById(existing).orElse(null);
                if (old != null && !FAILED.equals(old.getStatus())) {
                    log.info("命中幂等 key，复用任务 jobId={}", existing);
                    return new JobCreatedResponse(existing, false);
                }
                // 上一次失败的任务不参与幂等复用，否则用户重试只会拿回同一个失败结果
                if (old != null) {
                    log.info("上次任务失败（jobId={}），重新创建", existing);
                    redis.opsForValue().set(idempotencyKey, newJobId,
                            Duration.ofMinutes(idempotencyMinutes));
                }
            }
        } catch (Exception e) {
            log.warn("Redis 幂等不可用，继续创建任务: {}", e.getMessage());
        }

        TripJobEntity job = new TripJobEntity();
        job.setId(newJobId);
        job.setAnonId(anonId);
        job.setStatus(PENDING);
        job.setRequestJson(requestJson);
        LocalDateTime now = LocalDateTime.now();
        job.setCreatedAt(now);
        job.setUpdatedAt(now);
        jobRepository.save(job);

        String traceId = MDC.get("traceId");
        log.info("创建任务 jobId={} city={} days={}", newJobId, request.city(), request.resolvedDays());

        JobStream created = streamFor(newJobId);
        publishTrace(created, "Java",
                "参数校验通过：" + request.startDate() + " ~ " + request.endDate()
                        + "（" + request.resolvedDays() + " 天）", "info");
        publishTrace(created, "Java", "任务已入库（PENDING），提交虚拟线程异步生成", "info");

        tripExecutor.submit(() -> generate(newJobId, anonId, request, traceId));
        return new JobCreatedResponse(newJobId, true);
    }

    // ---------------- 生成 ----------------

    private void generate(String jobId, String anonId, CreateTripRequest request, String traceId) {
        String previousTrace = MDC.get("traceId");
        MDC.put("traceId", traceId == null ? "-" : traceId);
        JobStream stream = streamFor(jobId);
        try {
            updateStatus(jobId, RUNNING, null, null);
            publishTrace(stream, "Java", "开始调用 Python Agent：POST /internal/v1/plans（NDJSON 流）", "info");
            agentClient.streamPlan(request, traceId, event -> handleEvent(jobId, anonId, stream, event));
            if (!stream.finished) {
                failJob(jobId, stream, "AGENT_UNAVAILABLE", "Agent 流意外结束");
            }
        } catch (Exception e) {
            log.error("调用 Agent 失败 jobId={}", jobId, e);
            failJob(jobId, stream, "AGENT_UNAVAILABLE", "服务繁忙，请稍后重试");
        } finally {
            if (previousTrace == null) {
                MDC.remove("traceId");
            } else {
                MDC.put("traceId", previousTrace);
            }
        }
    }

    private void handleEvent(String jobId, String anonId, JobStream stream, JsonNode event) {
        String type = event.path("type").asText("");
        switch (type) {
            case "stage" -> {
                String stage = event.path("stage").asText("");
                Map<String, Object> payload = switch (stage) {
                    case "accepted" -> progress("accepted", 5, "已受理，正在准备规划");
                    case "fanout_start" -> progress("fanout_start", 10, "正在并行检索景点、天气与酒店");
                    case "synthesize" -> progress("synthesize", 70, "正在编排每日行程");
                    default -> null;
                };
                if (payload != null) {
                    publish(jobId, stream, "progress", payload);
                }
            }
            case "agent_result" -> {
                String agent = event.path("agent").asText("");
                int count = event.path("count").asInt(0);
                Map<String, Object> payload = switch (agent) {
                    case "attractions" -> progress("attractions", 40, "景点检索完成，共 " + count + " 个候选");
                    case "weather" -> progress("weather", 50, "天气查询完成");
                    case "hotels" -> progress("hotels", 60, "酒店检索完成，共 " + count + " 个候选");
                    default -> null;
                };
                if (payload != null) {
                    publish(jobId, stream, "progress", payload);
                }
            }
            case "degraded" -> {
                String agent = event.path("agent").asText("");
                String label = switch (agent) {
                    case "weather" -> "天气";
                    case "hotels" -> "酒店";
                    default -> agent;
                };
                publish(jobId, stream, "progress", progress("degraded", 62, label + "信息暂不可用，继续生成行程"));
            }
            case "trace" -> {
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("tag", event.path("tag").asText("Agent"));
                payload.put("text", event.path("text").asText(""));
                payload.put("level", event.path("level").asText("info"));
                payload.put("source", "python");
                payload.put("ts", event.path("ts").asLong(System.currentTimeMillis()));
                publishTransient(stream, "trace", payload);
            }
            case "final" -> finalizeTrip(jobId, anonId, stream, event.path("payload"));
            case "error" -> failJob(jobId, stream,
                    event.path("code").asText("INTERNAL"),
                    event.path("message").asText("生成失败"));
            default -> log.debug("忽略未知事件 type={}", type);
        }
    }

    private void finalizeTrip(String jobId, String anonId, JobStream stream, JsonNode payload) {
        try {
            publish(jobId, stream, "progress", progress("final", 95, "正在计算预算并保存行程"));
            publishTrace(stream, "Java", "收到 final：解析行程 JSON，开始补图与预算计算", "info");

            String planJson = objectMapper.writeValueAsString(payload);
            planJson = imageEnhancer.enhance(planJson, payload.path("city").asText(""),
                    (tag, text, level) -> publishTrace(stream, tag, text, level));
            JsonNode plan = objectMapper.readTree(planJson);
            Budget budget = BudgetCalculator.calculate(plan);
            publishTrace(stream, "Java",
                    "预算计算完成：门票 ¥" + formatYuan(budget.attractionsCents())
                            + " · 住宿 ¥" + formatYuan(budget.hotelsCents())
                            + " · 餐饮 ¥" + formatYuan(budget.mealsCents())
                            + " · 交通 ¥" + formatYuan(budget.transportCents())
                            + " · 合计 ¥" + formatYuan(budget.totalCents()), "info");

            TripEntity trip = new TripEntity();
            trip.setId(newId());
            trip.setJobId(jobId);
            trip.setAnonId(anonId);
            trip.setCity(plan.path("city").asText(""));
            trip.setStartDate(LocalDate.parse(plan.path("start_date").asText()));
            trip.setEndDate(LocalDate.parse(plan.path("end_date").asText()));
            trip.setPlanJson(planJson);
            trip.setBudgetJson(objectMapper.writeValueAsString(budget));
            trip.setVersion(1);
            LocalDateTime now = LocalDateTime.now();
            trip.setCreatedAt(now);
            trip.setUpdatedAt(now);
            tripRepository.save(trip);

            updateStatus(jobId, SUCCEEDED, null, null);
            publishTrace(stream, "Java", "行程写入 trip 表（version=1），任务置为 SUCCEEDED", "ok");

            Map<String, Object> done = new LinkedHashMap<>();
            done.put("jobId", jobId);
            done.put("tripId", trip.getId());
            done.put("version", trip.getVersion());
            publish(jobId, stream, "done", done);
            stream.finished = true;
            completeEmitters(stream);
            log.info("行程生成完成 jobId={} tripId={} totalCents={}", jobId, trip.getId(), budget.totalCents());
        } catch (Exception e) {
            log.error("保存行程失败 jobId={}", jobId, e);
            failJob(jobId, stream, "SAVE_FAILED", "行程保存失败");
        }
    }

    private void failJob(String jobId, JobStream stream, String code, String message) {
        if (stream.finished) {
            return;
        }
        stream.finished = true;
        updateStatus(jobId, FAILED, code, message);
        publishTrace(stream, "Java", "任务失败：" + code + " " + message, "error");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("code", code);
        payload.put("message", message);
        payload.put("traceId", MDC.get("traceId"));
        publish(jobId, stream, "error", payload);
        completeEmitters(stream);
        log.warn("任务失败 jobId={} code={} message={}", jobId, code, message);
    }

    // ---------------- SSE ----------------

    public SseEmitter subscribe(String jobId, String anonId, long lastEventId) {
        TripJobEntity job = requireJob(jobId);
        if (!job.getAnonId().equals(anonId)) {
            throw notFound();
        }
        SseEmitter emitter = new SseEmitter(600_000L);
        JobStream stream = streamFor(jobId);
        synchronized (stream.lock) {
            List<TripEventEntity> history =
                    eventRepository.findByJobIdAndSeqGreaterThanOrderBySeqAsc(jobId, (int) lastEventId);
            for (TripEventEntity event : history) {
                try {
                    emitter.send(SseEmitter.event()
                            .id(String.valueOf(event.getSeq()))
                            .name(event.getType())
                            .data(event.getPayloadJson()));
                } catch (IOException e) {
                    emitter.complete();
                    return emitter;
                }
            }
            if (TERMINAL.contains(job.getStatus()) || stream.finished) {
                // 历史事件已写入 emitter 缓冲区；延迟完成，确保返回前数据能刷出
                CompletableFuture.delayedExecutor(300, TimeUnit.MILLISECONDS).execute(emitter::complete);
                return emitter;
            }
            // 追踪日志只存内存：中途刷新页面时补发已产生的行
            for (String traceJson : new ArrayList<>(stream.traces)) {
                try {
                    emitter.send(SseEmitter.event().name("trace").data(traceJson));
                } catch (IOException e) {
                    emitter.complete();
                    return emitter;
                }
            }
            stream.emitters.add(emitter);
            emitter.onCompletion(() -> removeEmitter(stream, emitter));
            emitter.onTimeout(() -> {
                removeEmitter(stream, emitter);
                emitter.complete();
            });
            emitter.onError(ex -> removeEmitter(stream, emitter));
        }
        log.info("SSE 订阅 jobId={} lastEventId={}", jobId, lastEventId);
        return emitter;
    }

    // ---------------- 查询 / 编辑 / 导出 ----------------

    public Map<String, Object> getJob(String jobId, String anonId) {
        TripJobEntity job = requireJob(jobId);
        if (!job.getAnonId().equals(anonId)) {
            throw notFound();
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("jobId", jobId);
        result.put("status", job.getStatus());
        try {
            if (job.getRequestJson() != null) {
                result.put("request", objectMapper.readTree(job.getRequestJson()));
            }
        } catch (Exception e) {
            log.warn("请求快照解析失败 jobId={}", jobId);
        }
        if (job.getErrorCode() != null) {
            result.put("errorCode", job.getErrorCode());
            result.put("errorMessage", job.getErrorMessage());
        }
        tripRepository.findByJobId(jobId).ifPresent(trip -> {
            result.put("tripId", trip.getId());
            result.put("version", trip.getVersion());
            try {
                result.put("plan", objectMapper.readTree(trip.getPlanJson()));
                result.put("budget", objectMapper.readTree(trip.getBudgetJson()));
            } catch (Exception e) {
                log.error("行程 JSON 解析失败 tripId={}", trip.getId(), e);
            }
        });
        return result;
    }

    public Map<String, Object> updateAttractions(String jobId, String anonId, int dayIndex,
                                                 List<Map<String, Object>> attractions) {
        TripEntity trip = tripRepository.findByJobIdAndAnonId(jobId, anonId)
                .orElseThrow(TripService::notFound);
        try {
            JsonNode plan = objectMapper.readTree(trip.getPlanJson());
            JsonNode days = plan.path("days");
            if (dayIndex < 0 || dayIndex >= days.size()) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "DAY_NOT_FOUND", "天数下标不存在");
            }
            ObjectNode day = (ObjectNode) days.get(dayIndex);
            day.set("attractions", objectMapper.valueToTree(attractions));
            // 主题由景点推导，编辑后同步刷新，避免展示与列表不一致
            List<String> names = attractions.stream()
                    .map(item -> String.valueOf(item.getOrDefault("name", "")))
                    .filter(name -> !name.isBlank())
                    .limit(3)
                    .toList();
            day.put("theme", names.isEmpty() ? "自由活动" : String.join("、", names));
            Budget budget = BudgetCalculator.calculate(plan);
            trip.setPlanJson(objectMapper.writeValueAsString(plan));
            trip.setBudgetJson(objectMapper.writeValueAsString(budget));
            trip.setVersion(trip.getVersion() + 1);
            trip.setUpdatedAt(LocalDateTime.now());
            tripRepository.save(trip);
            log.info("行程已编辑 jobId={} dayIndex={} version={}", jobId, dayIndex, trip.getVersion());

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("tripId", trip.getId());
            result.put("version", trip.getVersion());
            result.put("plan", plan);
            result.put("budget", budget);
            return result;
        } catch (ApiException e) {
            throw e;
        } catch (Exception e) {
            log.error("编辑行程失败 jobId={}", jobId, e);
            throw new ApiException(HttpStatus.BAD_REQUEST, "EDIT_FAILED", "行程编辑失败");
        }
    }

    public byte[] exportHtml(String jobId, String anonId) {
        TripEntity trip = tripRepository.findByJobIdAndAnonId(jobId, anonId)
                .orElseThrow(TripService::notFound);
        try {
            JsonNode plan = objectMapper.readTree(trip.getPlanJson());
            Budget budget = objectMapper.readValue(trip.getBudgetJson(), Budget.class);
            return exportRenderer.render(plan, budget).getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            log.error("导出失败 jobId={}", jobId, e);
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "EXPORT_FAILED", "导出失败");
        }
    }

    // ---------------- 内部工具 ----------------

    private void checkRateLimit(String anonId, String clientIp) {
        String key = "trip:rl:" + anonId + ":" + clientIp;
        try {
            Long count = redis.opsForValue().increment(key);
            if (count != null && count == 1L) {
                redis.expire(key, Duration.ofMinutes(1));
            }
            if (count != null && count > rateLimitPerMinute) {
                throw new ApiException(HttpStatus.TOO_MANY_REQUESTS, "RATE_LIMITED", "请求过于频繁，请稍后再试");
            }
        } catch (ApiException e) {
            throw e;
        } catch (Exception e) {
            log.warn("Redis 限流不可用，跳过: {}", e.getMessage());
        }
    }

    private void updateStatus(String jobId, String status, String errorCode, String errorMessage) {
        try {
            jobRepository.findById(jobId).ifPresent(job -> {
                job.setStatus(status);
                job.setErrorCode(errorCode);
                job.setErrorMessage(errorMessage);
                job.setUpdatedAt(LocalDateTime.now());
                jobRepository.save(job);
            });
        } catch (Exception e) {
            log.error("更新任务状态失败 jobId={} status={}", jobId, status, e);
        }
    }

    private void publish(String jobId, JobStream stream, String type, Object payload) {
        String json;
        try {
            json = objectMapper.writeValueAsString(payload);
        } catch (Exception e) {
            log.error("事件序列化失败 jobId={} type={}", jobId, type, e);
            return;
        }
        synchronized (stream.lock) {
            stream.seq++;
            int seq = stream.seq;
            try {
                TripEventEntity entity = new TripEventEntity();
                entity.setJobId(jobId);
                entity.setSeq(seq);
                entity.setType(type);
                entity.setPayloadJson(json);
                entity.setCreatedAt(LocalDateTime.now());
                eventRepository.save(entity);
            } catch (Exception e) {
                log.warn("事件落库失败 jobId={} seq={}: {}", jobId, seq, e.getMessage());
            }
            broadcast(stream, seq, type, json);
        }
    }

    /** 执行追踪：只广播、不落库（trip_event 只存可续传的进度/终态事件） */
    private void publishTrace(JobStream stream, String tag, String text, String level) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("tag", tag);
        payload.put("text", text);
        payload.put("level", level);
        payload.put("source", "java");
        payload.put("ts", System.currentTimeMillis());
        publishTransient(stream, "trace", payload);
    }

    private void publishTransient(JobStream stream, String type, Object payload) {
        String json;
        try {
            json = objectMapper.writeValueAsString(payload);
        } catch (Exception e) {
            log.warn("追踪事件序列化失败: {}", e.getMessage());
            return;
        }
        synchronized (stream.lock) {
            stream.traces.add(json);
            if (stream.traces.size() > 400) {
                stream.traces.remove(0);
            }
            if (stream.emitters.isEmpty()) {
                return;
            }
            List<SseEmitter> dead = new ArrayList<>();
            for (SseEmitter emitter : stream.emitters) {
                try {
                    emitter.send(SseEmitter.event().name(type).data(json));
                } catch (Exception e) {
                    dead.add(emitter);
                }
            }
            stream.emitters.removeAll(dead);
        }
    }

    private static void broadcast(JobStream stream, int seq, String type, String json) {
        if (stream.emitters.isEmpty()) {
            return;
        }
        List<SseEmitter> dead = new ArrayList<>();
        for (SseEmitter emitter : stream.emitters) {
            try {
                emitter.send(SseEmitter.event().id(String.valueOf(seq)).name(type).data(json));
            } catch (Exception e) {
                dead.add(emitter);
            }
        }
        stream.emitters.removeAll(dead);
    }

    private static void completeEmitters(JobStream stream) {
        for (SseEmitter emitter : stream.emitters) {
            try {
                emitter.complete();
            } catch (Exception ignored) {
                // 连接已断开，忽略
            }
        }
        stream.emitters.clear();
    }

    private static void removeEmitter(JobStream stream, SseEmitter emitter) {
        synchronized (stream.lock) {
            stream.emitters.remove(emitter);
        }
    }

    private JobStream streamFor(String jobId) {
        return streams.computeIfAbsent(jobId, key -> {
            JobStream stream = new JobStream();
            Integer max = eventRepository.maxSeq(key);
            stream.seq = max == null ? 0 : max;
            return stream;
        });
    }

    private TripJobEntity requireJob(String jobId) {
        return jobRepository.findById(jobId).orElseThrow(TripService::notFound);
    }

    private static ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "TRIP_NOT_FOUND", "行程不存在或已失效");
    }

    private static Map<String, Object> progress(String stage, int percent, String text) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("stage", stage);
        map.put("percent", percent);
        map.put("text", text);
        return map;
    }

    private static String formatYuan(long cents) {
        if (cents % 100 == 0) {
            return String.valueOf(cents / 100);
        }
        return String.format(java.util.Locale.ROOT, "%.2f", cents / 100.0);
    }

    private static String newId() {
        String time = Long.toString(System.currentTimeMillis(), 36).toUpperCase();
        String random = UUID.randomUUID().toString().replace("-", "").toUpperCase();
        return (time + random).substring(0, 26);
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            return Integer.toHexString(value.hashCode());
        }
    }

    private static final class JobStream {
        private final Object lock = new Object();
        private final List<SseEmitter> emitters = new ArrayList<>();
        private final List<String> traces = new ArrayList<>();
        private int seq;
        private volatile boolean finished;
    }
}
