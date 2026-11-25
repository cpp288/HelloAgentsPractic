package com.trip.api;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import com.trip.api.dto.CreateTripRequest;
import com.trip.api.dto.JobCreatedResponse;
import com.trip.api.dto.UpdateAttractionsRequest;
import com.trip.service.TripService;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/trips")
public class TripController {

    private final TripService tripService;

    public TripController(TripService tripService) {
        this.tripService = tripService;
    }

    /** 创建规划任务：立即返回 202 + jobId，不阻塞等待生成。 */
    @PostMapping
    public ResponseEntity<JobCreatedResponse> create(@Valid @RequestBody CreateTripRequest request,
                                                     @RequestHeader(value = "X-Anon-Id", required = false) String anonId,
                                                     HttpServletRequest httpRequest) {
        JobCreatedResponse response =
                tripService.createJob(resolveAnonId(anonId), httpRequest.getRemoteAddr(), request);
        return ResponseEntity.accepted().body(response);
    }

    /** SSE 进度流，支持 Last-Event-ID 断线续传（EventSource 不能带自定义头，故兼容 anonId 查询参数）。 */
    @GetMapping(value = "/{jobId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter events(@PathVariable String jobId,
                             @RequestHeader(value = "X-Anon-Id", required = false) String anonId,
                             @RequestHeader(value = "Last-Event-ID", required = false) String lastEventId,
                             @RequestParam(value = "anonId", required = false) String anonIdParam,
                             @RequestParam(value = "lastEventId", required = false) String lastEventIdParam) {
        String resolvedAnon = anonId == null || anonId.isBlank() ? anonIdParam : anonId;
        String resolvedLast = lastEventId == null || lastEventId.isBlank() ? lastEventIdParam : lastEventId;
        return tripService.subscribe(jobId, resolveAnonId(resolvedAnon), parseLastEventId(resolvedLast));
    }

    /** 查询任务与最终行程（含 Java 计算的预算）。 */
    @GetMapping("/{jobId}")
    public Map<String, Object> get(@PathVariable String jobId,
                                   @RequestHeader(value = "X-Anon-Id", required = false) String anonId) {
        return tripService.getJob(jobId, resolveAnonId(anonId));
    }

    /** 编辑某天景点：服务端重算预算并 version + 1。 */
    @PatchMapping("/{jobId}/days/{dayIndex}/attractions")
    public Map<String, Object> updateAttractions(@PathVariable String jobId,
                                                 @PathVariable int dayIndex,
                                                 @Valid @RequestBody UpdateAttractionsRequest request,
                                                 @RequestHeader(value = "X-Anon-Id", required = false) String anonId) {
        List<Map<String, Object>> attractions = request.attractions();
        return tripService.updateAttractions(jobId, resolveAnonId(anonId), dayIndex, attractions);
    }

    /** 导出：服务端渲染 HTML，可直接打印为 PDF。 */
    @PostMapping(value = "/{jobId}/export", produces = "text/html;charset=UTF-8")
    public ResponseEntity<byte[]> export(@PathVariable String jobId,
                                         @RequestHeader(value = "X-Anon-Id", required = false) String anonId) {
        byte[] html = tripService.exportHtml(jobId, resolveAnonId(anonId));
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType("text", "html", StandardCharsets.UTF_8));
        headers.setContentDisposition(ContentDisposition.attachment().filename("trip-plan.html").build());
        return ResponseEntity.ok().headers(headers).body(html);
    }

    private static String resolveAnonId(String anonId) {
        return anonId == null || anonId.isBlank() ? "anonymous" : anonId.trim();
    }

    private static long parseLastEventId(String value) {
        if (value == null || value.isBlank()) {
            return 0;
        }
        try {
            return Long.parseLong(value.trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
