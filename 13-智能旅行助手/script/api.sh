#!/usr/bin/env bash
# Java 业务层（Spring Boot）进程管理：每次 start/restart 都会重新打包
# 用法: ./api.sh {start|stop|restart|status|logs} [--skip-build]
set -euo pipefail

NAME=api
PORT=8080

source "$(dirname "$0")/_common.sh"

HEALTH="http://127.0.0.1:$PORT/actuator/health"
APP_DIR="$ROOT/api"
LOG_FILE="$APP_DIR/logs/api.log"
JAR="$APP_DIR/target/trip-api-0.1.0.jar"

SKIP_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
  esac
done

build() {
  log "构建 mvn package（改完 Java 代码后自动生效）"
  ( cd "$APP_DIR" && mvn -q clean package -DskipTests )
  log "构建完成"
}

start_service() {
  mkdir -p "$APP_DIR/logs"
  if [ "$SKIP_BUILD" = "1" ]; then
    warn "已指定 --skip-build，使用现有 jar"
  else
    build
  fi
  [ -f "$JAR" ] || die "未找到 $JAR"

  log "启动 java -jar $(basename "$JAR") :$PORT"
  spawn "$APP_DIR" java -jar "$JAR"

  if wait_http "$HEALTH"; then
    log "启动成功 http://127.0.0.1:$PORT/actuator/health"
  else
    warn "健康检查超时，最后 30 行日志："
    tail -n 30 "$LOG_FILE" || true
    exit 1
  fi
}

ACTION="${1:-start}"
case "$ACTION" in
  start)
    [ -z "$(port_pids "$PORT")" ] || die "端口 $PORT 已被占用，先执行 ./api.sh stop"
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
