"""Agent 层对外（仅内网）接口：NDJSON 流式返回进度与最终行程。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.agents.planner import Planner
from app.graph.build import build_graph
from app.graph.state import PlanError
from app.logging_config import setup_logging, trace_id_var
from app.schemas.models import TripPlanRequest
from app.settings import get_settings
from app.tools.amap import AmapClient

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

GRAPH_TIMEOUT_SECONDS = 110


class TraceIdMiddleware:
    """把上游 X-Trace-Id 写入 contextvar，并回写到响应头。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        trace_id = Headers(scope=scope).get("x-trace-id") or format(int(time.time() * 1000), "x").upper()
        token = trace_id_var.set(trace_id)

        async def send_with_trace(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Trace-Id"] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace)
        finally:
            trace_id_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AmapClient(settings)
    planner = Planner(settings)
    app.state.client = client
    app.state.graph = build_graph(client, planner)
    logger.info(
        "Agent 服务启动 mock_llm=%s mock_tools=%s model=%s",
        settings.use_mock_llm,
        settings.use_mock_tools,
        settings.llm_model,
    )
    try:
        yield
    finally:
        await client.close()


app = FastAPI(title="Trip Agent Service", lifespan=lifespan)
app.add_middleware(TraceIdMiddleware)


@app.get("/internal/v1/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mock_llm": settings.use_mock_llm,
        "mock_tools": settings.use_mock_tools,
        "model": settings.llm_model,
    }


@app.post("/internal/v1/plans", response_model=None)
async def create_plan(
    payload: TripPlanRequest,
    request: Request,
    x_internal_token: str | None = Header(default=None),
    x_trace_id: str | None = Header(default=None),
):
    if x_internal_token != settings.internal_token:
        return JSONResponse(status_code=401, content={"code": "UNAUTHORIZED", "message": "内部鉴权失败"})

    graph = request.app.state.graph
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    logger.info(
        "收到规划请求 city=%s %s~%s days=%s trace=%s",
        payload.city,
        payload.start_date,
        payload.end_date,
        payload.days,
        trace_id_var.get(),
    )

    async def produce() -> None:
        started = time.perf_counter()
        queue.put_nowait(
            {
                "type": "trace",
                "source": "python",
                "tag": "Agent",
                "text": (
                    f"收到规划请求：{payload.city} {payload.start_date}~{payload.end_date}"
                    f"（{payload.days} 天），trace={trace_id_var.get()}"
                ),
                "level": "info",
                "ts": _now_ms(),
            }
        )
        queue.put_nowait(
            {
                "type": "trace",
                "source": "python",
                "tag": "调度",
                "text": "LangGraph 调度器启动：fan-out 3 个 Agent（景点 / 天气 / 酒店）并行执行",
                "level": "info",
                "ts": _now_ms(),
            }
        )
        queue.put_nowait(
            {
                "type": "trace",
                "source": "python",
                "tag": "调度",
                "text": "fan-in 等待：三路 Agent 全部返回后进入 synthesize 汇总",
                "level": "info",
                "ts": _now_ms(),
            }
        )
        try:
            queue.put_nowait({"type": "stage", "stage": "fanout_start", "ts": _now_ms()})
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {
                        "request": payload.model_dump(mode="json"),
                        "queue": queue,
                        "degraded": [],
                    }
                ),
                timeout=GRAPH_TIMEOUT_SECONDS,
            )
            draft = result.get("draft")
            if draft is None:
                raise PlanError("EMPTY_RESULT", "行程生成结果为空")
            elapsed = int((time.perf_counter() - started) * 1000)
            queue.put_nowait(
                {
                    "type": "trace",
                    "source": "python",
                    "tag": "Agent",
                    "text": f"LangGraph 执行完成：{len(draft.days)} 天行程（{elapsed} ms），输出 final",
                    "level": "ok",
                    "ts": _now_ms(),
                }
            )
            queue.put_nowait({"type": "final", "payload": draft.model_dump(mode="json")})
            logger.info("规划完成 city=%s days=%s", draft.city, len(draft.days))
        except PlanError as exc:
            logger.warning("规划失败 code=%s message=%s", exc.code, exc.message)
            queue.put_nowait(
                {
                    "type": "trace",
                    "source": "python",
                    "tag": "Agent",
                    "text": f"规划失败：{exc.code} {exc.message}",
                    "level": "error",
                    "ts": _now_ms(),
                }
            )
            queue.put_nowait({"type": "error", "code": exc.code, "message": exc.message})
        except asyncio.TimeoutError:
            logger.error("规划超时")
            queue.put_nowait(
                {
                    "type": "trace",
                    "source": "python",
                    "tag": "Agent",
                    "text": f"规划超时（>{GRAPH_TIMEOUT_SECONDS}s）",
                    "level": "error",
                    "ts": _now_ms(),
                }
            )
            queue.put_nowait({"type": "error", "code": "TIMEOUT", "message": "行程生成超时"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("规划未知异常")
            queue.put_nowait(
                {
                    "type": "trace",
                    "source": "python",
                    "tag": "Agent",
                    "text": f"未处理异常：{str(exc)[:160]}",
                    "level": "error",
                    "ts": _now_ms(),
                }
            )
            queue.put_nowait({"type": "error", "code": "INTERNAL", "message": str(exc)})
        finally:
            queue.put_nowait(None)

    producer = asyncio.create_task(produce())

    async def stream() -> AsyncIterator[str]:
        try:
            yield _line({"type": "stage", "stage": "accepted", "ts": _now_ms()})
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield _line(event)
        finally:
            if not producer.done():
                producer.cancel()

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _line(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"


def _now_ms() -> int:
    return int(time.time() * 1000)
