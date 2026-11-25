"""LangGraph 节点：三路并发采集 + 单点汇合。

失败隔离在这里显式表达：
- 景点是核心数据，失败整单失败
- 天气 / 酒店失败只降级，不阻塞出结果
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Callable

from app.agents.planner import Planner
from app.graph.state import PlanError, PlanState
from app.schemas.models import TripPlanRequest
from app.tools.amap import AmapClient

logger = logging.getLogger(__name__)


def emit(state: PlanState, event: dict[str, Any]) -> None:
    queue = state.get("queue")
    if queue is not None:
        queue.put_nowait(event)


def _now_ms() -> int:
    return int(time.time() * 1000)


def trace(state: PlanState, tag: str, text: str, level: str = "info") -> None:
    """执行追踪事件：只在 SSE 里展示，不落库。"""
    emit(
        state,
        {
            "type": "trace",
            "source": "python",
            "tag": tag,
            "text": text,
            "level": level,
            "ts": _now_ms(),
        },
    )


def _tool_detail(client: AmapClient, path: str, params: str) -> str:
    if client.mock:
        return "内置样例数据"
    return f"高德 REST {path} {params}"


def make_attractions_node(client: AmapClient) -> Callable:
    async def search_attractions(state: PlanState) -> dict[str, Any]:
        req = TripPlanRequest(**state["request"])
        trace(
            state,
            "景点",
            f"Agent·景点 启动（三路并行）· 检索：{req.city} · 数据源 "
            + _tool_detail(
                client,
                "/v3/place/text",
                f"(city={req.city}, keywords={req.preferences or '景点'} 景点, types=110000)",
            ),
        )
        start = time.perf_counter()
        logger.info("节点开始 search_attractions city=%s", req.city)
        try:
            attractions = await asyncio.wait_for(
                client.search_attractions(req.city, req.preferences), timeout=20
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("search_attractions 失败")
            trace(state, "景点", f"检索失败（核心数据，整单失败）：{str(exc)[:120]}", "error")
            raise PlanError("ATTRACTIONS_FAILED", f"景点检索失败: {exc}") from exc
        if not attractions:
            raise PlanError("NO_ATTRACTIONS", f"{req.city} 未检索到景点数据")

        latency = int((time.perf_counter() - start) * 1000)
        logger.info("节点结束 search_attractions count=%s latency_ms=%s", len(attractions), latency)
        sample = "、".join(a.get("name", "") for a in attractions[:3])
        trace(
            state,
            "景点",
            f"检索完成：{len(attractions)} 个候选（{latency} ms）｜示例：{sample}",
            "ok",
        )
        emit(
            state,
            {
                "type": "agent_result",
                "agent": "attractions",
                "count": len(attractions),
                "latency_ms": latency,
            },
        )
        return {"attractions": attractions}

    return search_attractions


def make_weather_node(client: AmapClient) -> Callable:
    async def query_weather(state: PlanState) -> dict[str, Any]:
        req = TripPlanRequest(**state["request"])
        dates = [(req.start_date + timedelta(days=i)).isoformat() for i in range(req.days)]
        trace(
            state,
            "天气",
            f"Agent·天气 启动（三路并行）· 查询 {len(dates)} 天 · 数据源 "
            + _tool_detail(client, "/v3/weather/weatherInfo", f"(city={req.city}, extensions=all)"),
        )
        start = time.perf_counter()
        logger.info("节点开始 query_weather city=%s", req.city)
        try:
            weather = await asyncio.wait_for(client.query_weather(req.city, dates), timeout=10)
        except Exception as exc:  # noqa: BLE001
            logger.warning("query_weather 降级: %s", exc)
            trace(state, "天气", f"查询失败，降级为空天气：{str(exc)[:120]}", "warn")
            emit(state, {"type": "degraded", "agent": "weather", "reason": str(exc)[:120]})
            return {"weather": [], "degraded": ["weather"]}

        latency = int((time.perf_counter() - start) * 1000)
        logger.info("节点结束 query_weather count=%s latency_ms=%s", len(weather), latency)
        if weather:
            sample = "；".join(
                f"{w.get('date', '')[-5:]} {w.get('day_weather', '')} "
                f"{w.get('night_temp', '?')}~{w.get('day_temp', '?')}℃"
                for w in weather[:3]
            )
            trace(
                state,
                "天气",
                f"查询完成：{len(weather)} 天（{latency} ms）｜{sample}",
                "ok",
            )
        else:
            trace(
                state,
                "天气",
                f"查询完成：0 天（超出高德预报窗口），行程继续生成（{latency} ms）",
                "warn",
            )
        emit(
            state,
            {
                "type": "agent_result",
                "agent": "weather",
                "count": len(weather),
                "latency_ms": latency,
            },
        )
        return {"weather": weather}

    return query_weather


def make_hotels_node(client: AmapClient) -> Callable:
    async def search_hotels(state: PlanState) -> dict[str, Any]:
        req = TripPlanRequest(**state["request"])
        trace(
            state,
            "酒店",
            f"Agent·酒店 启动（三路并行）· 检索：{req.accommodation} · 数据源 "
            + _tool_detail(
                client,
                "/v3/place/text",
                f"(city={req.city}, keywords={req.accommodation}, types=100000)",
            ),
        )
        start = time.perf_counter()
        logger.info("节点开始 search_hotels city=%s", req.city)
        try:
            hotels = await asyncio.wait_for(
                client.search_hotels(req.city, req.accommodation), timeout=20
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("search_hotels 降级: %s", exc)
            trace(state, "酒店", f"检索失败，降级为无酒店：{str(exc)[:120]}", "warn")
            emit(state, {"type": "degraded", "agent": "hotels", "reason": str(exc)[:120]})
            return {"hotels": [], "degraded": ["hotels"]}

        latency = int((time.perf_counter() - start) * 1000)
        logger.info("节点结束 search_hotels count=%s latency_ms=%s", len(hotels), latency)
        missing_price = sum(1 for h in hotels if not h.get("price_per_night"))
        detail = f"，其中 {missing_price} 个无房价，稍后按档位估算" if missing_price else ""
        sample = "、".join(
            f"{h.get('name', '')}（¥{h['price_per_night']:.0f}/晚）"
            if h.get("price_per_night")
            else f"{h.get('name', '')}（无报价）"
            for h in hotels[:3]
        )
        trace(
            state,
            "酒店",
            f"检索完成：{len(hotels)} 个候选（{latency} ms）{detail}｜示例：{sample}",
            "ok",
        )
        emit(
            state,
            {
                "type": "agent_result",
                "agent": "hotels",
                "count": len(hotels),
                "latency_ms": latency,
            },
        )
        return {"hotels": hotels}

    return search_hotels


def make_synthesize_node(planner: Planner) -> Callable:
    async def synthesize(state: PlanState) -> dict[str, Any]:
        req = TripPlanRequest(**state["request"])
        attractions = state.get("attractions") or []
        weather = state.get("weather") or []
        hotels = state.get("hotels") or []
        degraded = state.get("degraded") or []
        done = 3 - len(degraded)
        trace(
            state,
            "汇合",
            f"fan-in 完成：{done}/3 个 Agent 返回（景点 {len(attractions)} · 天气 {len(weather)}"
            f" · 酒店 {len(hotels)}）"
            + (f"，降级 {','.join(degraded)}" if degraded else "，无降级"),
            "warn" if degraded else "ok",
        )
        emit(state, {"type": "stage", "stage": "synthesize", "ts": _now_ms()})
        trace(
            state,
            "LLM",
            f"调用 {planner.mode_label} 编排 {req.days} 天行程，候选输入 {len(attractions) + len(hotels)} 条",
        )
        start = time.perf_counter()
        logger.info("节点开始 synthesize city=%s", req.city)
        try:
            draft = await planner.build(
                req,
                attractions,
                weather,
                hotels,
                degraded,
                on_trace=lambda tag, text, level="info": trace(state, tag, text, level),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("synthesize 失败")
            trace(state, "LLM", f"编排失败：{str(exc)[:160]}", "error")
            raise PlanError("LLM_FAILED", f"行程生成失败: {exc}") from exc

        latency = int((time.perf_counter() - start) * 1000)
        logger.info("节点结束 synthesize days=%s latency_ms=%s", len(draft.days), latency)
        trace(state, "编排", f"编排完成：{len(draft.days)} 天行程（{latency} ms）", "ok")
        return {"draft": draft}

    return synthesize
