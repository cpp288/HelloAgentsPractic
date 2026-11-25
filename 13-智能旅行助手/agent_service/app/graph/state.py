"""LangGraph 状态定义。

queue 不是业务状态，只是本次请求的事件出口：
节点通过它把进度事件推给 FastAPI 的流式响应。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class PlanState(TypedDict, total=False):
    request: dict[str, Any]
    queue: Any
    attractions: list[dict[str, Any]]
    weather: list[dict[str, Any]]
    hotels: list[dict[str, Any]]
    degraded: Annotated[list[str], operator.add]
    draft: Any


class PlanError(Exception):
    """不可恢复的业务错误，code 会被透传给 Java。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
