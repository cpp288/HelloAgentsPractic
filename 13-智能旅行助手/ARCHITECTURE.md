# 智能旅行助手 · 项目架构设计

> **定位**：把第 13 章的单体 Python 后端，重构为「Java 业务层（轻量）+ Python Agent 层（重点）」的双服务架构。
> **适用前提**：后端团队更擅长 Java，且不需要为多 Agent 编排单独引入 Java 侧生态。
> **配套阅读**：[README.md](README.md)（章节总结）、[README.md](../../README.md)（项目索引）

| 项 | 值 |
|---|---|
| 文档版本 | v1.0 |
| 编写日期 | 2026-11-25 |
| 参考案例 | Hello-Agents 第 13 章 智能旅行助手 |
| JDK / Python | JDK 21+（虚拟线程） / Python 3.12+ |
| Agent 框架 | LangGraph + Pydantic v2 |
| 业务框架 | Spring Boot 3.x + MySQL 8 + Redis |

---

## 1. 目标与非目标

### 1.1 目标

1. 业务层能复用团队既有的 Java 工程能力（事务、限流、幂等、监控），不因为 AI 而降低工程质量。
2. Agent 层专注「LLM 决策 + 工具编排」，不掺业务逻辑，可独立迭代、独立扩容。
3. 两层之间**契约先行**，任一层的实现可以被子团队并行开发而不互相阻塞。
4. 端到端可观测：一次请求的 trace 能贯穿 Java → Python → LLM → 外部 API。

### 1.2 非目标（本期明确不做）

- **用户注册 / 登录 / 账号体系**（本期打开即用，无身份概念，详见 4.3）
- 多租户、计费、用户成长体系
- 容器化部署（本期用本机命令启动，见第 11 节）
- 分布式任务调度（Temporal / XXL-Job）
- 会话式多轮对话（本期是「一次性生成行程」）
- 自己训练模型、RAG 检索（景点信息走 MCP 实时查询）

---

## 2. 四条设计原则

| # | 原则 | 落地方式 |
|---|---|---|
| 1 | **确定性归 Java，不确定性归 Python** | 求和、校验、权限、幂等、图片抓取归 Java；只有「该调什么工具、怎么组织行程」归 Python |
| 2 | **Agent 层无状态，状态归 Java** | Java 持有 `trip` / `job` 表；Python 进程可随时重启，不存任何会话 |
| 3 | **契约先行，不手抄 DTO** | Python 产出 OpenAPI → `openapi-generator` 生成 Java client，字段只定义一次 |
| 4 | **Python 不做重复计算** | LLM 只产出结构化明细，金额由 Java 用整数（分）精确求和，避免模型算术错误 |

> 原则 1 和 4 是整套架构的价值核心：教材把预算交给 LLM 在提示词里算（13.6.1），这是最容易被低估的缺陷。

---

## 3. 总体架构

```
                         ┌──────────────────────────┐
                         │   Web (Next.js 16 / Vue3) │
                         └────────────┬─────────────┘
                                      │ HTTPS + SSE
                    ┌─────────────────▼──────────────────┐
                    │        业务层  Spring Boot (Java)   │
                    │  限流 · 任务编排 · 结果落库 · 匿名会话  │
                    │  预算精确计算 · 行程编辑 · 导出         │
                    │  图片增强（虚拟线程并发）                │
                    └─────────────────┬──────────────────┘
                                      │ 内网 HTTP / OpenAPI
                                      │ NDJSON 流（进度 + 结果）
                    ┌─────────────────▼──────────────────┐
                    │      Agent 层  FastAPI (Python)     │
                    │  LangGraph 状态图 · 三路并发采集       │
                    │  结构化输出校验 · 提示词 · 工具适配     │
                    └─────────────────┬──────────────────┘
                                      │ MCP 协议
                    ┌─────────────────▼──────────────────┐
                    │  高德 MCP Server   │  Unsplash API   │
                    │        LLM API     │   （直连）       │
                    └────────────────────────────────────┘
```

### 3.1 职责边界

| 能力 | 归属 | 判断依据 |
|---|---|---|
| 限流 / 幂等 / 匿名会话标识 | Java | 纯工程问题，不需要真实账号 |
| 行程持久化、编辑、版本 | Java | 事务与一致性 |
| **预算求和** | **Java** | 算术必须确定，LLM 不可信 |
| 字段校验（对外） | Java | 边界防护 |
| 景点 / 天气 / 酒店检索 | Python | 需要 Agent 决策用哪个工具、什么关键词 |
| 行程编排与文案生成 | Python | 需要 LLM |
| 景点配图抓取 | Java | 确定性 HTTP 调用，不需要 LLM |
| 进度事件生产 | Python | 只有它知道阶段推进 |
| 进度事件转发 / 回放 | Java | 面向浏览器，需要断线重连 |
| 导出 PNG / PDF | Java | 服务端渲染，规避 html2canvas 截 Canvas 的问题 |

---

## 4. 业务层设计（Java，轻量）

### 4.1 技术栈

| 组件 | 选型 | 用途 |
|---|---|---|
| 框架 | Spring Boot 3.x | Web / DI / 配置 |
| 运行时 | JDK 21+ | **虚拟线程**处理并发 IO |
| 持久化 | **MySQL 8 + Spring Data JPA**（团队习惯 MyBatis-Plus 可平替） | 行程、任务、进度事件 |
| 缓存 | Redis（本机已有） | 幂等键、限流计数、热点数据 |
| 接口文档 | springdoc-openapi | 对外 API 文档 |
| 契约生成 | openapi-generator-maven-plugin | 生成 Python 服务的 client |
| 弹性 | Resilience4j | 熔断、重试、限流 |
| 可观测 | Micrometer + OTel | 指标、trace |
| 导出 | Playwright(Java) 或静态地图 API | 服务端截图 |

> 刻意不引入：消息队列、分布式锁、服务注册中心。单体两个服务用不上。

### 4.2 包结构

```
com.trip
├── api/           # Controller：对外 REST + SSE
├── client/        # generated/（OpenAPI 生成）+ AgentClient 封装
├── domain/        # TripPlan 聚合、Budget 计算、编辑规则
├── service/       # TripApplicationService（编排 Java 侧的流程）
├── infra/         # 仓储、Redis、图片增强、导出
└── config/        # 线程池、超时、Resilience4j、OTel
```

### 4.3 对外接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/trips` | 创建规划任务，返回 `202 + jobId`（不阻塞） |
| GET | `/api/trips/{jobId}/events` | SSE，推送进度；支持 `Last-Event-ID` 断线续传 |
| GET | `/api/trips/{jobId}` | 查询最终行程 |
| PATCH | `/api/trips/{jobId}/days/{dayIndex}/attractions` | 编辑行程（服务端重算预算） |
| POST | `/api/trips/{jobId}/export?format=png\|pdf` | 导出 |

**为什么是 202 + jobId 而不是同步等？** 生成耗时 30~75 秒，超过多数网关的默认超时。异步化后：浏览器可断线重连、可并发、可重试，Java 也能把耗时观测做准。

**无账号设计（打开即用）**：不做注册登录。前端首次访问生成一个 `anonId`（UUID，写 localStorage + Cookie），每次请求带 `X-Anon-Id` 头；Java 用它做**行程归属、限流计数、幂等去重**，不做任何认证授权。行程列表按 `anonId` 过滤，换设备即换身份——本期定位是单机工具，够用且零门槛。

对应的接口收敛为 5 个，没有 `/login`、`/token` 之类：

| 关注点 | 做法 |
|---|---|
| 身份 | `X-Anon-Id`（可伪造，只影响数据归属，不影响安全） |
| 防刷 | 按 `anonId + IP` 双维度限流（Bucket4j + Redis） |
| 越权 | 不做校验，但查询/编辑必须同时匹配 `anon_id`，避免串数据 |
| 迁移 | 将来接入账号时，只需把 `anon_id` 绑定到 `user_id`，表结构不用改 |

### 4.4 预算计算（关键代码）

```java
/** 金额统一用「分」存储，避免浮点误差 */
public record Budget(long attractionsCents, long hotelsCents,
                     long mealsCents, long transportCents) {

    public long totalCents() {
        return Math.addExact(Math.addExact(attractionsCents, hotelsCents),
                             Math.addExact(mealsCents, transportCents));
    }
}
```

编辑行程（删除某景点）后，只重算受影响的分项，不重新调 LLM —— 这是把预算放在 Java 的直接收益。

### 4.5 图片增强（虚拟线程并发）

```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<?>> tasks = attractions.stream()
        .map(a -> executor.submit(() -> a.setImageUrl(imageService.find(a, city))))
        .toList();
    for (var f : tasks) f.get(5, TimeUnit.SECONDS);  // 单张超时不影响整体
}
```

单张失败不影响行程返回，`imageUrl` 留空即可。

### 4.6 表设计（MySQL 8）

```sql
-- 任务表：一次规划请求一行
CREATE TABLE trip_job (
  id            CHAR(26)     NOT NULL PRIMARY KEY COMMENT 'ULID',
  anon_id       VARCHAR(64)  NOT NULL COMMENT '匿名会话标识',
  status        VARCHAR(16)  NOT NULL COMMENT 'PENDING/RUNNING/SUCCEEDED/FAILED',
  request_json  JSON         NOT NULL,
  error_code    VARCHAR(32)  NULL,
  created_at    DATETIME(3)  NOT NULL,
  updated_at    DATETIME(3)  NOT NULL,
  KEY idx_anon_created (anon_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 行程表：生成结果，编辑时 version + 1
CREATE TABLE trip (
  id            CHAR(26)     NOT NULL PRIMARY KEY,
  job_id        CHAR(26)     NOT NULL,
  anon_id       VARCHAR(64)  NOT NULL,
  city          VARCHAR(64)  NOT NULL,
  start_date    DATE         NOT NULL,
  end_date      DATE         NOT NULL,
  plan_json     JSON         NOT NULL COMMENT '完整 TripPlan，整体读写',
  budget_json   JSON         NOT NULL COMMENT 'Java 计算的分项与合计（单位：分）',
  version       INT          NOT NULL DEFAULT 1,
  updated_at    DATETIME(3)  NOT NULL,
  UNIQUE KEY uk_job (job_id),
  KEY idx_anon (anon_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 进度事件：支撑 SSE 的 Last-Event-ID 续传
CREATE TABLE trip_event (
  job_id        CHAR(26)     NOT NULL,
  seq           INT          NOT NULL,
  type          VARCHAR(24)  NOT NULL,
  payload_json  JSON         NOT NULL,
  created_at    DATETIME(3)  NOT NULL,
  PRIMARY KEY (job_id, seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

设计说明：

- **只建三张表**。行程的 days/attractions/meals 全部放在 `plan_json` 里，不拆关联表——本期没有任何按景点聚合的查询需求，拆表只会换来一堆 JOIN
- 金额一律存整数「分」，与 `Budget` 记录一致
- `trip_event` 生成完成后整单删除或保留 24h，作用是把「断线重连」从 Redis 转移到 MySQL，少一个依赖
- JPA 映射：Hibernate 6 用 `@JdbcTypeCode(SqlTypes.JSON)` 把 `plan_json` 映射成 `String` 或 `JsonNode`
- 建库：`CREATE DATABASE trip_planner DEFAULT CHARSET utf8mb4;`

---

## 5. Agent 层设计（Python，重点）

### 5.1 技术栈

| 组件 | 选型 | 用途 |
|---|---|---|
| Web | FastAPI + Uvicorn | 内网接口、NDJSON 流式响应 |
| 编排 | **LangGraph** | 状态图、三路并发、失败隔离、可加 checkpoint |
| 数据模型 | **Pydantic v2** | 入参/出参校验，`field_validator` 清洗外部脏数据 |
| LLM 接入 | OpenAI 兼容 SDK / LangChain | 支持 DeepSeek、Qwen 等 |
| 工具 | MCP Client（stdio 本地 / Streamable HTTP 线上） | 高德 16 个工具 |
| 观测 | Langfuse（或 LangSmith）+ OTel | 每次 LLM 调用、工具调用留痕 |

### 5.2 目录结构

```
agent_service/
├── app/
│   ├── main.py              # FastAPI 入口，/internal/v1/plans
│   ├── graph/
│   │   ├── build.py         # LangGraph 组装
│   │   ├── state.py         # PlanState (TypedDict)
│   │   └── nodes.py         # 四个节点实现
│   ├── agents/              # 提示词与 Agent 封装
│   ├── tools/
│   │   ├── mcp_amap.py      # MCP 连接与工具缓存
│   │   └── unsplash.py      # 直连 HTTP（非 MCP）
│   ├── schemas/             # Pydantic 模型（TripPlan 等）
│   └── settings.py          # 环境变量
└── pyproject.toml
```

### 5.3 LangGraph 图：三路并发 + 单点汇合

```python
from langgraph.graph import StateGraph, START, END

class PlanState(TypedDict, total=False):
    request: TripPlanRequest
    attractions: list[Attraction]
    weather: list[WeatherInfo]
    hotels: list[Hotel]
    draft: TripPlanDraft | None
    degraded: list[str]      # 记录降级的子任务

g = StateGraph(PlanState)
g.add_node("search_attractions", search_attractions)
g.add_node("query_weather", query_weather)
g.add_node("search_hotels", search_hotels)
g.add_node("synthesize", synthesize)      # PlannerAgent

# 三个节点同一个 superstep 出发 → 自动并行
g.add_edge(START, "search_attractions")
g.add_edge(START, "query_weather")
g.add_edge(START, "search_hotels")
for node in ("search_attractions", "query_weather", "search_hotels"):
    g.add_edge(node, "synthesize")
g.add_edge("synthesize", END)
```

对比教材的串行 `plan_trip()`：三路独立任务串行执行等于把延迟白叠 3 倍。并发后采集阶段从约 45s 压到约 20s（受最慢一路约束）。

### 5.4 节点职责

| 节点 | 调用 | 超时 | 失败策略 |
|---|---|---|---|
| `search_attractions` | `amap_maps_text_search` | 20s | **核心**，失败则整单失败 |
| `query_weather` | `amap_maps_weather` | 10s | 降级：返回空天气列表 |
| `search_hotels` | `amap_maps_text_search` | 20s | 降级：返回空酒店列表 |
| `synthesize` | LLM（无工具） | 45s | 失败重试 1 次，仍失败则整单失败 |

「核心 / 可选」的区分必须在代码里显式表达，而不是靠提示词祈祷。

### 5.5 结构化输出：不靠提示词许愿

```python
draft = llm.with_structured_output(TripPlanDraft).invoke(prompt)
# 失败自动重试，最多 2 次，并把校验错误回灌给模型
```

- 用 JSON Schema / function calling 约束，而不是「请输出 JSON」+ 正则解析
- Pydantic 校验失败时，把 `ValidationError` 内容拼进重试提示词（自修复）
- 金额字段只允许模型给「单价」，总量由 Java 汇总

### 5.6 MCP 接入

```python
# 本地开发：stdio 起子进程
mcp = MCPClient.stdio(command="uvx", args=["amap-mcp-server"],
                      env={"AMAP_API_KEY": settings.amap_key})

# 线上：连独立的 Streamable HTTP 服务（2026-07 规范后 MCP 协议层无状态，可直接水平扩容）
mcp = MCPClient.http(url=settings.amap_mcp_url, headers={"Authorization": ...})
```

- **全进程共用一个 MCP 连接**，三个节点共享（对应教材 13.4.3 的结论）
- 缓存挂在 MCP 适配层：`poi:{city}:{keywords}` TTL 24h，`weather:{city}:{date}` TTL 3h
- Unsplash 不进 MCP：它是确定性数据，归 Java 的图片增强环节

---

## 6. 接口契约

### 6.1 内部接口：Java → Python

```
POST /internal/v1/plans
Header: X-Trace-Id, X-Internal-Token
Content-Type: application/json
Accept: application/x-ndjson
```

**为什么用 NDJSON 流而不是「同步 JSON + 另一个进度通道」**：一次请求同时拿到进度和结果，Java 不用引入 Redis 订阅，Python 也不用回调 Java，是这套轻量架构里最省事的选择。

请求体：

```json
{
  "city": "北京",
  "start_date": "2026-12-01",
  "end_date": "2026-12-03",
  "days": 3,
  "preferences": "历史文化",
  "budget_level": "中等",
  "transportation": "公共交通",
  "accommodation": "经济型酒店"
}
```

响应流（每行一个事件）：

```
{"type":"stage","stage":"fanout_start","ts":1733...}
{"type":"agent_result","agent":"attractions","count":12,"latency_ms":8420}
{"type":"agent_result","agent":"weather","count":3,"latency_ms":2100}
{"type":"degraded","agent":"hotels","reason":"tool_timeout"}
{"type":"stage","stage":"synthesize","ts":...}
{"type":"final","payload":{ ...TripPlanDraft... }}
```

### 6.2 事件类型约定

| type | 触发时机 | Java 侧动作 |
|---|---|---|
| `stage` | 阶段切换 | 转发为 SSE，更新 job 状态 |
| `agent_result` | 单个子 Agent 完成 | 转发 + 记录耗时指标 |
| `degraded` | 某路降级 | 转发 + 在结果里标注 |
| `final` | 生成完成 | 落库、触发图片增强、关闭流 |
| `error` | 不可恢复 | 落库失败原因、推送错误 |

### 6.3 对外 SSE 事件（Java → 浏览器）

```
id: 7
event: progress
data: {"stage":"synthesize","percent":72,"text":"正在生成行程"}

event: done
data: {"jobId":"...","tripId":"..."}
```

Java 负责把 Python 的细粒度事件**翻译成用户能懂的语言并折算百分比**（教材里那个"模拟进度条"到这里就变成真进度了）。

### 6.4 错误模型

| 场景 | Java 返回 | 用户可见文案 |
|---|---|---|
| 入参不合法 | 400 | 具体字段错误 |
| 城市无景点数据 | 422 | 换个城市或关键词试试 |
| LLM 超时 | 504 | 生成超时，请重试 |
| 某路降级 | 200 | 正常返回 + 「天气信息暂不可用」提示 |
| 内部服务不可用 | 502 | 服务繁忙 |

不可重试错误（4xx）与可重试错误（502/504）必须在 `code` 上区分，前端据此决定是否给「重试」按钮。

---

## 7. 数据流时序

### 7.1 成功路径（时间预算）

```
浏览器            Java                     Python                   外部
  │ POST /api/trips │                         │                      │
  ├────────────────▶│ 建 job(PENDING)         │                      │
  │◀── 202 jobId ───┤                         │                      │
  │ GET /events     │                         │                      │
  ├────────────────▶│ POST /internal/plans    │                      │
  │                 ├────────────────────────▶│ 三路并发 ────────────▶│ 高德
  │                 │                         │   (≤20s)             │
  │                 │◀── agent_result ×3 ─────┤                      │
  │◀─ progress ─────┤                         │ Planner(≤45s) ──────▶│ LLM
  │                 │◀── final ───────────────┤                      │
  │                 │ 图片增强(虚拟线程, ≤5s) ─────────────────────▶│ Unsplash
  │                 │ 预算求和 + 落库          │                      │
  │◀── done ────────┤                         │                      │
```

**总预算 75 秒**，硬超时 120 秒（Java 侧 Resilience4j TimeLimiter）。

### 7.2 降级路径

```
weather 超时 → PlanState.degraded += ["weather"]
              → synthesize 照常执行（提示词声明"缺天气时不要编造"）
              → 结果 weather_info 为空
              → Java 返回 200 + warning 字段
              → 前端隐藏天气卡片
```

---

## 8. 关键设计决策

| 决策 | 教材做法 | 本方案 | 理由 |
|---|---|---|---|
| 编排并发度 | 4 个 Agent 串行 | 三路并发 + 单点汇合 | 三个采集任务无依赖，串行浪费 2/3 等待时间 |
| 预算计算 | PlannerAgent 提示词内估算 | Java 整数求和 | LLM 算术不可靠且不报错 |
| 输出解析 | 提示词要 JSON + 正则 | `with_structured_output` + 校验重试 | 正则解析是最脆弱的环节 |
| 进度反馈 | 前端 `setInterval` 假进度 | 后端 NDJSON → SSE 真事件 | 假进度掩盖真实耗时，无法定位瓶颈 |
| 状态归属 | 单体进程内变量 | Java 持久化，Python 无状态 | 便于扩容与重启 |
| MCP 传输 | 一律 `npx` 子进程 | 本地 stdio / 线上 Streamable HTTP | 2026-07 规范后协议层无状态，可水平扩容 |
| 图片获取 | 路由内同步串行 | Java 虚拟线程并发 | 12 张图串行要 10s+ |
| 导出 | html2canvas（截不到地图） | 服务端 Playwright / 静态地图 API | 教材自己承认的方案缺陷 |

---

## 9. 可靠性与成本

### 9.1 超时矩阵

| 环节 | 超时 | 重试 |
|---|---|---|
| 单次 LLM 调用 | 45s | 1 次（指数退避 + 抖动） |
| 单次 MCP 工具调用 | 20s | 1 次（仅网络类错误） |
| 采集阶段整体 | 25s | 不重试（走降级） |
| 图片抓取单张 | 5s | 0 |
| Java → Python 整体 | 120s | 用户手动重试 |

### 9.2 成本控制

| 手段 | 说明 |
|---|---|
| 模型分层 | 天气/酒店抽取用小模型，Planner 用大模型 |
| 结果缓存 | POI 24h、天气 3h、图片 URL 7d |
| 提示词复用 | Planner 的静态部分前置，命中 prompt caching |
| 幂等 | Java 用 `(city, dates, preferences)` 哈希做 10 分钟幂等，防重复点击烧钱 |

---

## 10. 观测与安全

**追踪链**：浏览器 → Java 生成 `traceId` → 放 `X-Trace-Id` 头 → Python 透传到 Langfuse 与 LLM 调用 → 一个 ID 看全链路。

| 关键指标 | 归属 |
|---|---|
| 请求量 / P95 延迟 / 错误率 | Java (Micrometer) |
| 各子 Agent 耗时、降级次数 | Python (自定义 metric) |
| Token 消耗、单次成本 | Langfuse |
| 工具调用成功率 | MCP 适配层 |

**安全边界**：

- LLM / 高德 / Unsplash 的 Key **只存在于 Python 与 Java 各自的环境变量**，前端零接触
- Java↔Python 用 `X-Internal-Token` 共享密钥；Python 只监听 `127.0.0.1:8000`，不对外
- 对外只暴露 Java（8080）
- **本期无账号体系**：`anonId` 只用于数据归属，不承担鉴权职责，因此所有涉及行程的读写都必须显式带 `anon_id` 条件，避免不同浏览器串数据
- 用户输入（城市、偏好）在拼进提示词前做长度与字符白名单校验，防提示词注入

---

## 11. 本地运行与日志

本期不做容器化，全部以本机进程方式启动：MySQL 与 Redis 用你机器上现成的服务，两个后端各自 `java`/`uvicorn` 起进程，日志同时输出到控制台和文件，靠 traceId 串联。

### 11.1 依赖与端口

| 依赖 | 说明 |
|---|---|
| MySQL 8.x | 本机已有，建库 `trip_planner`，字符集 utf8mb4 |
| Redis | 本机已有，用于幂等键与限流计数 |
| JDK 21+ | 虚拟线程 |
| Python 3.12+ | Agent 层 |
| Node.js 20+ | 前端 |

| 服务 | 端口 | 监听地址 |
|---|---|---|
| web | 3000（Vue 项目为 5173） | 0.0.0.0 |
| api | 8080 | 0.0.0.0（唯一对外入口） |
| agent | 8000 | 127.0.0.1 |
| MySQL / Redis | 3306 / 6379 | 本机现成服务 |

### 11.2 启动命令

```bash
# 0. 一次性初始化（表结构见 4.6）
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS trip_planner DEFAULT CHARSET utf8mb4;"
mysql -uroot -p trip_planner < api/src/main/resources/schema.sql

# 1. Agent 层（先起，Java 依赖它）
cd agent_service
python -m venv .venv && source .venv/bin/activate
pip install -e .
mkdir -p logs
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload 2>&1 | tee logs/agent.log

# 2. 业务层
cd api
mkdir -p logs
mvn spring-boot:run -Dspring-boot.run.profiles=local 2>&1 | tee logs/api.log

# 3. 前端
cd web
npm install && npm run dev
```

启动自检顺序：`curl 127.0.0.1:8000/internal/v1/health`（agent 就绪）→ `curl 127.0.0.1:8080/actuator/health`（api 就绪，含 MySQL/Redis 探针）→ 打开前端。

### 11.3 日志规范（一次请求可追踪）

**核心要求：一次生成请求在三个进程里的所有日志，都能用同一个 traceId grep 出来。**

| 层 | 生成/传递 | 输出 |
|---|---|---|
| 前端 | 请求头带 `X-Trace-Id`（ULID），失败提示里回显后 8 位 | 浏览器控制台 |
| Java | Filter 读 `X-Trace-Id`，没有就新建，写入 MDC；调 Python 时透传 | 控制台 + `logs/api.log` |
| Python | Middleware 读 `X-Trace-Id`，写入 `contextvar`，日志 Filter 注入 | 控制台 + `logs/agent.log` |
| LLM 调用 | 同一 traceId 作为 Langfuse 的 trace 名 | Langfuse 控制台 |

Java（logback-spring.xml）关键片段：

```xml
<appender name="FILE" class="ch.qos.logback.core.FileAppender">
  <file>logs/api.log</file>
  <encoder>
    <pattern>%d{HH:mm:ss.SSS} %-5level [%X{traceId:-}] %logger{36} - %msg%n</pattern>
  </encoder>
</appender>
```

Python 侧等价做法：

```python
logging.basicConfig(
    format="%(asctime)s %(levelname)-5s [%(trace_id)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/agent.log")],
)
```

排查方式：

```bash
# 用户报错 → 取页面上的 trace 后 8 位 → 全链路一次捞出
grep "A1B2C3D4" logs/api.log logs/agent.log
```

日志级别约定：

- 本地默认 `com.trip=DEBUG`、Python `INFO`
- Agent 每个节点进入/退出各打一条（含 `latency_ms`），这是排查「哪一步慢」的主要依据
- **LLM 的完整 prompt/response 只在 DEBUG 下打印，且对 api key 打码**；生产默认关闭
- 高德/Unsplash 的原始响应不落盘，只记状态码与耗时

### 11.4 配置

| 变量（api） | 示例 |
|---|---|
| `spring.datasource.url` | `jdbc:mysql://127.0.0.1:3306/trip_planner?useSSL=false&serverTimezone=Asia/Shanghai&characterEncoding=utf8` |
| `spring.datasource.username` / `password` | 本机 MySQL 账号 |
| `spring.data.redis.host` / `port` | `127.0.0.1` / `6379` |
| `agent.base-url` | `http://127.0.0.1:8000` |
| `internal.token` | 与 agent 侧一致 |

| 变量（agent） | 示例 |
|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 模型接入 |
| `AMAP_API_KEY` / `AMAP_MCP_URL` | 高德密钥与 MCP 地址 |
| `UNSPLASH_ACCESS_KEY` | 图片服务 |
| `INTERNAL_TOKEN` | 内部鉴权 |
| `LANGFUSE_*` | 观测（可选，本地可关） |

配置载体：Java 用 `application-local.yml`，Python 用 `.env`，两者都在 `.gitignore` 中。MySQL 连接池用 HikariCP，本地默认 10 个连接足够。

---

## 12. 落地顺序

| 里程碑 | 交付物 | 验收标准 |
|---|---|---|
| **M1 契约冻结** | OpenAPI 定义 + Java/Python 双侧骨架 | Python 返回**固定 fixture**，Java 全链路跑通（可并行开工） |
| **M2 单 Agent 打通** | `search_attractions` + MCP 高德 | 能搜到真实景点列表，trace 可查 |
| **M3 三路并发** | 三个节点并发 + 降级 | 采集阶段 P95 < 25s，天气失败不影响出结果 |
| **M4 结构化生成** | `synthesize` + 校验重试 | 连续 20 次调用 JSON 合规率 100% |
| **M5 真进度** | NDJSON → SSE | 前端进度条与后端 stage 事件一一对应 |
| **M6 增强功能** | 预算求和、编辑、图片、导出 | 删景点后预算立即正确；导出含地图 |

> M1 的 fake agent 是这套架构能不能并行开发的关键：**先让契约能跑，再让模型变聪明**。

---

## 13. 与教材的对应关系

| 教材小节 | 本方案对应 | 变化 |
|---|---|---|
| 13.2 Pydantic 数据模型 | 保留（Python 侧），Java 侧由 OpenAPI 生成 | 不手抄 DTO |
| 13.3 四 Agent 协作 | LangGraph 五个节点（三采集 + 一汇合 + 入口） | 串行 → 并发 |
| 13.4 MCP 集成 | 保留，增加 Transport 切换与结果缓存 | stdio → 可切 Streamable HTTP |
| 13.5 前端 | 保留思路 | 建议 Next.js 16 |
| 13.6.1 预算计算 | 移到 Java | LLM 估算 → 确定性求和 |
| 13.6.2 加载进度 | NDJSON → SSE | 模拟 → 真实 |
| 13.6.4 导出 | 服务端渲染 | 修复地图导出缺陷 |

---

## 14. 修订记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-11-25 | 初版：Java 业务层 + Python Agent 层双层架构 |
| v1.1 | 2026-11-25 | ① 移除账号体系，改为 `anonId` 匿名会话；② 关系库 Postgres → **MySQL 8**（复用本机服务）；③ 取消 Docker，改为本机命令启动 + traceId 贯穿的日志方案 |
