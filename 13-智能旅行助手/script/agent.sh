#!/usr/bin/env bash
# Agent 层（FastAPI + LangGraph）进程管理
# 用法: ./agent.sh {start|stop|restart|status|logs}
set -euo pipefail

NAME=agent
PORT=8000

source "$(dirname "$0")/_common.sh"

HEALTH="http://127.0.0.1:$PORT/internal/v1/health"
APP_DIR="$ROOT/agent_service"
LOG_FILE="$APP_DIR/logs/agent.log"
PY="$APP_DIR/.venv/bin/python"

start_service() {
  [ -x "$PY" ] || die "未找到 $PY，请先执行: cd agent_service && python3 -m venv .venv && .venv/bin/pip install -e ."
  mkdir -p "$APP_DIR/logs"

  log "启动 uvicorn :$PORT"
  spawn "$APP_DIR" "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"

  if wait_http "$HEALTH"; then
    log "启动成功 http://127.0.0.1:$PORT/internal/v1/health"
  else
    warn "健康检查超时，最后 20 行日志："
    tail -n 20 "$LOG_FILE" || true
    exit 1
  fi
}

ACTION="${1:-start}"
case "$ACTION" in
  start)
    [ -z "$(port_pids "$PORT")" ] || die "端口 $PORT 已被占用，先执行 ./agent.sh stop"
    start_service
    ;;
  stop) stop_service ;;
  restart)
    stop_service
    start_service
    ;;
  status) show_status ;;
  logs) tail_log ;;
  *) usage_common ;;
esac
