"""Planner：把采集结果编排成结构化行程。

- 未配置 LLM Key → 确定性 Mock 方案，保证全链路可跑
- 配置了 Key → with_structured_output + 校验重试
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any, Callable

from app.schemas.models import (
    Attraction,
    DayPlan,
    Hotel,
    Meal,
    TripPlanDraft,
    TripPlanRequest,
    WeatherInfo,
)
from app.settings import Settings

logger = logging.getLogger(__name__)

TRANSPORT_COST = {"公共交通": 40.0, "地铁": 30.0, "打车": 120.0, "自驾": 150.0, "步行": 10.0}

# 高德 POI 通常不返回房价，住宿缺价时按住宿档位估算，避免预算里住宿为 0
ACCOMMODATION_PRICE = (
    ("青旅", 120.0),
    ("民宿", 420.0),
    ("经济", 280.0),
    ("舒适", 450.0),
    ("豪华", 900.0),
)
DEFAULT_HOTEL_PRICE = 350.0


def estimate_hotel_price(accommodation: str) -> float:
    for key, price in ACCOMMODATION_PRICE:
        if key in (accommodation or ""):
            return price
    return DEFAULT_HOTEL_PRICE


class Planner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm = None
        self._structured = None

    @property
    def mode_label(self) -> str:
        if self._settings.use_mock_llm:
            return "MockPlanner（模板生成）"
        return f"LLM {self._settings.llm_model}"

    async def build(
        self,
        request: TripPlanRequest,
        attractions: list[dict[str, Any]],
        weather: list[dict[str, Any]],
        hotels: list[dict[str, Any]],
        degraded: list[str],
        on_trace: Callable[[str, str, str], None] | None = None,
    ) -> TripPlanDraft:
        if self._settings.use_mock_llm:
            logger.info("使用 MockPlanner 生成行程（未配置 LLM Key 或 LLM_MOCK=true）")
            return self._mock_plan(request, attractions, weather, hotels, degraded, on_trace)
        return await asyncio.to_thread(
            self._llm_plan, request, attractions, weather, hotels, degraded, on_trace
        )

    # ---------- Mock ----------
    def _mock_plan(
        self,
        request: TripPlanRequest,
        attractions: list[dict[str, Any]],
        weather: list[dict[str, Any]],
        hotels: list[dict[str, Any]],
        degraded: list[str],
        on_trace: Callable[[str, str, str], None] | None = None,
    ) -> TripPlanDraft:
        dates = _dates(request)
        transport_cost = TRANSPORT_COST.get(request.transportation, 50.0)
        chunks = _split(attractions, len(dates))

        days: list[DayPlan] = []
        for i, d in enumerate(dates):
            items = [Attraction(**a) for a in chunks[i]]
            is_last = i == len(dates) - 1
            hotel = None
            if not is_last and hotels:
                h = hotels[i % len(hotels)]
                hotel = Hotel(**h)
            names = "、".join(a.name for a in items) or "自由活动"
            days.append(
                DayPlan(
                    day_index=i,
                    date=d.isoformat(),
                    theme=f"第 {i + 1} 天 · {names}",
                    attractions=items,
                    meals=[
                        Meal(type="早餐", name="酒店自助早餐", description="就近解决，节省时间", estimated_cost=30),
                        Meal(type="午餐", name=f"{request.city}特色餐厅", description="选景区周边评价较好的本地菜", estimated_cost=70),
                        Meal(type="晚餐", name=f"{request.city}本地菜馆", description="避开景区正门，往居民区走更实惠", estimated_cost=90),
                    ],
                    hotel=hotel,
                    transportation=request.transportation,
                    transportation_cost=transport_cost,
                    notes="返程日，不含住宿" if is_last else "景点顺序可按当天体力调整",
                )
            )

        warnings = list(degraded)
        draft = TripPlanDraft(
            city=request.city,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            summary=(
                f"{request.city} {len(dates)} 天行程，按「{request.preferences or '经典景点'}」偏好编排；"
                f"住宿为{request.accommodation}，市内交通以{request.transportation}为主。"
                "预算为单人估算，不含往返大交通。"
            ),
            days=days,
            weather_info=[WeatherInfo(**w) for w in weather],
            warnings=warnings,
        )
        estimated = _fill_hotel_prices(draft, request)
        if estimated:
            message = (
                f"{estimated} 晚住宿缺少价格，已按「{request.accommodation}」"
                f"约 ¥{estimate_hotel_price(request.accommodation):.0f}/晚估算"
            )
            draft.warnings.append(message)
            if on_trace:
                on_trace("降级", message, "warn")
        return draft

    # ---------- LLM ----------
    def _llm_plan(
        self,
        request: TripPlanRequest,
        attractions: list[dict[str, Any]],
        weather: list[dict[str, Any]],
        hotels: list[dict[str, Any]],
        degraded: list[str],
        on_trace: Callable[[str, str, str], None] | None = None,
    ) -> TripPlanDraft:
        from langchain_core.messages import HumanMessage, SystemMessage

        if self._structured is None:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self._settings.llm_model,
                api_key=self._settings.llm_api_key,
                base_url=self._settings.llm_base_url,
                timeout=self._settings.llm_timeout,
                temperature=0.3,
            )
            # 用 json_mode（response_format=json_object）而不是默认的 json_schema：
            # DeepSeek 等兼容 OpenAI 的服务不支持 json_schema，会返回 400
            # "This response_format type is unavailable now"
            self._structured = self._llm.with_structured_output(
                TripPlanDraft, method="json_mode"
            )

        dates = _dates(request)
        system = SystemMessage(
            content=(
                "你是资深旅行规划师。只能使用给定候选数据里的景点与酒店，不得编造不存在的景点；"
                "天气只能来自给定天气数据，缺失就留空并在 warnings 说明。"
                "ticket_price 为单人门票（元），可用你的常识填写；price_per_night 为每晚房价（元）；"
                "estimated_cost 为单人餐费（元）；transportation_cost 为当天市内交通（元）。只输出单价，不要算总和。"
                "行程要松紧合理，同一天景点应地理相近。所有文案用简体中文。\n"
                "只输出一个 JSON 对象，不要 Markdown 代码块、不要任何解释。JSON 结构：\n"
                '{"city": str, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "summary": str, '
                '"days": [{"day_index": int, "date": "YYYY-MM-DD", "theme": str, '
                '"attractions": [{"name": str, "address": str, "visit_duration": str, '
                '"description": str, "ticket_price": float}], '
                '"meals": [{"type": str, "name": str, "description": str, "estimated_cost": float}], '
                '"hotel": {"name": str, "address": str, "price_per_night": float, "rating": str} | null, '
                '"transportation": str, "transportation_cost": float, "notes": str}], '
                '"weather_info": [{"date": "YYYY-MM-DD", "day_weather": str, "night_weather": str, '
                '"day_temp": int, "night_temp": int, "wind": str}], "warnings": [str]}'
            )
        )
        human = HumanMessage(
            content=(
                f"需求：城市={request.city}，{request.start_date} 至 {request.end_date}，共 {request.days} 天，"
                f"偏好={request.preferences or '无'}，预算档位={request.budget_level}，"
                f"市内交通={request.transportation}，住宿={request.accommodation}。\n"
                f"日期列表：{[d.isoformat() for d in dates]}\n"
                f"候选景点：{attractions}\n候选酒店：{hotels}\n天气：{weather}\n降级项：{degraded}"
            )
        )
        messages = [system, human]

        last_error: Exception | None = None
        for attempt in range(1, 3):
            started = time.perf_counter()
            try:
                if on_trace:
                    on_trace(
                        "LLM",
                        f"第 {attempt} 次请求：model={self._settings.llm_model}，"
                        f"{len(messages)} 条消息，等待模型返回",
                        "info",
                    )
                draft = self._structured.invoke(messages)
                elapsed = int((time.perf_counter() - started) * 1000)
                if on_trace:
                    on_trace("LLM", f"第 {attempt} 次返回，schema 校验通过（{elapsed} ms）", "ok")
                return self._normalize(draft, request, dates, weather, degraded, on_trace)
            except Exception as exc:  # noqa: BLE001 - 校验/网络错误都回灌重试
                last_error = exc
                logger.warning("结构化输出第 %s 次失败: %s", attempt, exc)
                if on_trace:
                    on_trace("LLM", f"第 {attempt} 次输出不合规：{str(exc)[:160]}", "warn")
                messages.append(
                    HumanMessage(content=f"上次输出不符合要求：{exc}。请修正后重新输出完整行程。")
                )
        raise RuntimeError(f"LLM 生成行程失败: {last_error}")

    def _normalize(
        self,
        draft: TripPlanDraft,
        request: TripPlanRequest,
        dates: list[date],
        weather: list[dict[str, Any]],
        degraded: list[str],
        on_trace: Callable[[str, str, str], None] | None = None,
    ) -> TripPlanDraft:
        draft.city = request.city
        draft.start_date = dates[0].isoformat()
        draft.end_date = dates[-1].isoformat()
        days: list[DayPlan] = list(draft.days[: len(dates)])
        while len(days) < len(dates):
            days.append(
                DayPlan(
                    day_index=len(days),
                    date=dates[len(days)].isoformat(),
                    theme="自由活动",
                    meals=[
                        Meal(type="午餐", name="当地餐厅", description="", estimated_cost=70),
                        Meal(type="晚餐", name="当地餐厅", description="", estimated_cost=90),
                    ],
                )
            )
        for i, day in enumerate(days):
            day.day_index = i
            day.date = dates[i].isoformat()
        draft.days = days
        if not draft.weather_info and weather:
            draft.weather_info = [WeatherInfo(**w) for w in weather]
        draft.warnings = list({*draft.warnings, *degraded})
        estimated = _fill_hotel_prices(draft, request)
        if estimated:
            message = (
                f"{estimated} 晚住宿缺少价格，已按「{request.accommodation}」"
                f"约 ¥{estimate_hotel_price(request.accommodation):.0f}/晚估算"
            )
            draft.warnings.append(message)
            if on_trace:
                on_trace("降级", message, "warn")
        return draft


def _fill_hotel_prices(draft: TripPlanDraft, request: TripPlanRequest) -> int:
    """住宿缺价时按档位补一个估算值，返回补价晚数。"""
    price = estimate_hotel_price(request.accommodation)
    estimated = 0
    for day in draft.days:
        hotel = day.hotel
        if hotel is not None and (hotel.price_per_night is None or hotel.price_per_night <= 0):
            hotel.price_per_night = price
            estimated += 1
    return estimated


def _dates(request: TripPlanRequest) -> list[date]:
    return [request.start_date + timedelta(days=i) for i in range(request.days)]


def _split(items: list[Any], parts: int) -> list[list[Any]]:
    """把景点均匀切成 parts 份，保持原有顺序。"""
    if parts <= 0:
        return []
    size, extra = divmod(len(items), parts)
    result, start = [], 0
    for i in range(parts):
        end = start + size + (1 if i < extra else 0)
        result.append(items[start:end])
        start = end
    return result
