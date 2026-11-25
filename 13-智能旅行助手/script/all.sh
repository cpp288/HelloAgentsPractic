#!/usr/bin/env bash
# 一键管理三个服务：agent(Python) → api(Java) → web(Vue)
# 用法: ./all.sh {start|stop|restart|status}
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ACTION="${1:-status}"
SERVICES=(agent api web)

case "$ACTION" in
  start|restart)
    for s in "${SERVICES[@]}"; do
      "$DIR/$s.sh" "$ACTION"
    done
    ;;
  stop|status)
    # 停止按反序：web → api → agent
    for ((i = ${#SERVICES[@]} - 1; i >= 0; i--)); do
      "$DIR/${SERVICES[$i]}.sh" "$ACTION"
    done
    ;;
  *)
    printf '用法: %s {start|stop|restart|status}\n' "$(basename "$0")"
    printf '单服务操作: ./agent.sh | ./api.sh | ./web.sh  {start|stop|restart|status|logs}\n'
    exit 1
    ;;
esac
