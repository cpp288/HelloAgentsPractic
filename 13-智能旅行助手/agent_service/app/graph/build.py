from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.planner import Planner
from app.graph.nodes import (
    make_attractions_node,
    make_hotels_node,
    make_synthesize_node,
    make_weather_node,
)
from app.graph.state import PlanState
from app.tools.amap import AmapClient


def build_graph(client: AmapClient, planner: Planner):
    """三路采集节点从 START 同时出发 → 同一 superstep 自动并发 → synthesize 汇合。"""
    graph = StateGraph(PlanState)
    graph.add_node("search_attractions", make_attractions_node(client))
    graph.add_node("query_weather", make_weather_node(client))
    graph.add_node("search_hotels", make_hotels_node(client))
    graph.add_node("synthesize", make_synthesize_node(planner))

    graph.add_edge(START, "search_attractions")
    graph.add_edge(START, "query_weather")
    graph.add_edge(START, "search_hotels")
    for node in ("search_attractions", "query_weather", "search_hotels"):
        graph.add_edge(node, "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
