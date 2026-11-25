#!/usr/bin/env bash
# 公共函数：日志着色、PID/端口管理、健康检查。由 agent.sh / api.sh / web.sh 引用，不要直接执行。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_DIR="$SCRIPT_DIR/.run"
mkdir -p "$RUN_DIR"

if [ -t 1 ]; then
  C_INFO=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_INFO=; C_WARN=; C_ERR=; C_RESET=
fi

log()  { printf '%s[%s]%s %s\n' "$C_INFO" "$NAME" "$C_RESET" "$*"; }
warn() { printf '%s[%s]%s %s\n' "$C_WARN" "$NAME" "$C_RESET" "$*"; }
die()  { printf '%s[%s]%s %s\n' "$C_ERR" "$NAME" "$C_RESET" "$*" >&2; exit 1; }

port_pids() { lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null || true; }

alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }

pid_file() { printf '%s/%s.pid' "$RUN_DIR" "$NAME"; }

# 后台常驻启动：双 fork 脱离当前会话，日志追加到 $LOG_FILE
# 用法: spawn <工作目录> <命令...>
spawn() {
  local dir="$1"
  shift
  python3 "$SCRIPT_DIR/_daemonize.py" \
    --cwd "$dir" --log "$LOG_FILE" --pid "$(pid_file)" -- "$@"
}

# 先按 pid 文件停，再按端口兜底（npm/mvn 会 fork 子进程，端口更可靠）
stop_service() {
  local pid pids i
  pid="$(cat "$(pid_file)" 2>/dev/null || true)"
  if alive "$pid"; then
    kill "$pid" 2>/dev/null || true
  fi

  pids="$(port_pids "$PORT")"
  if [ -n "$pids" ]; then
    warn "端口 $PORT 被占用，发送 TERM: $(echo "$pids" | tr '\n' ' ')"
    echo "$pids" | xargs kill 2>/dev/null || true
    for i in $(seq 1 25); do
      sleep 0.2
      [ -z "$(port_pids "$PORT")" ] && break
    done
    pids="$(port_pids "$PORT")"
    if [ -n "$pids" ]; then
      warn "未退出，强制 KILL: $(echo "$pids" | tr '\n' ' ')"
      echo "$pids" | xargs kill -9 2>/dev/null || true
      sleep 0.3
    fi
  fi

  rm -f "$(pid_file)"
  log "已停止"
}

# 轮询直到 HTTP 可访问（4xx 也算起来了，5xx/连不上继续等）
wait_http() {
  local url="$1" i code
  for i in $(seq 1 60); do
    code="$(curl -s -o /dev/null -m 1 -w '%{http_code}' "$url" 2>/dev/null || true)"
    if [ -n "$code" ] && [ "$code" != "000" ] && [ "${code:0:1}" != "5" ]; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

show_status() {
  local pid pids code
  pid="$(cat "$(pid_file)" 2>/dev/null || true)"
  pids="$(port_pids "$PORT")"
  # 手工/其他方式启动时没有 pid 文件，直接用端口占用进程兜底
  if [ -z "$pid" ] && [ -n "$pids" ]; then
    pid="$(echo "$pids" | head -n 1)"
  fi
  if alive "$pid" || [ -n "$pids" ]; then
    code="$(curl -s -o /dev/null -m 1 -w '%{http_code}' "$HEALTH" 2>/dev/null || echo 000)"
    log "运行中  pid=${pid:-?}  port=$PORT  health=$code  log=$LOG_FILE"
  else
    warn "未运行  port=$PORT"
  fi
}

tail_log() {
  [ -f "$LOG_FILE" ] || die "日志不存在: $LOG_FILE"
  log "跟踪 $LOG_FILE（Ctrl+C 退出，不影响服务）"
  tail -n 80 -f "$LOG_FILE"
}

usage_common() {
  printf '用法: %s {start|stop|restart|status|logs}\n' "$(basename "$0")"
  printf '  start/restart 会先构建再启动；api.sh 可加 --skip-build 跳过 mvn package\n'
}
