#!/usr/bin/env bash
# 前端（Vite + Vue3）进程管理：首次启动自动 npm install
# 用法: ./web.sh {start|stop|restart|status|logs}
set -euo pipefail

NAME=web
PORT=5173

source "$(dirname "$0")/_common.sh"

HEALTH="http://localhost:$PORT/"
APP_DIR="$ROOT/web"
LOG_FILE="$APP_DIR/logs/web.log"

start_service() {
  mkdir -p "$APP_DIR/logs"
  if [ ! -d "$APP_DIR/node_modules" ]; then
    log "首次启动，安装依赖（npmmirror 镜像）"
    ( cd "$APP_DIR" && npm install --registry=https://registry.npmmirror.com )
  fi

  log "启动 vite dev :$PORT"
  spawn "$APP_DIR" npm run dev

  if wait_http "$HEALTH"; then
    log "启动成功 http://localhost:$PORT"
  else
    warn "健康检查超时，最后 20 行日志："
    tail -n 20 "$LOG_FILE" || true
    exit 1
  fi
}

ACTION="${1:-start}"
case "$ACTION" in
  start)
    [ -z "$(port_pids "$PORT")" ] || die "端口 $PORT 已被占用，先执行 ./web.sh stop"
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
